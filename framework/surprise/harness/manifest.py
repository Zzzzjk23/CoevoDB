"""Run manifest: a hash of the labelling code, plus a command that checks it.

``file_digest`` normalises CRLF to LF before hashing. This checkout sets
``core.autocrlf``, so the same commit can appear as LF or CRLF on disk; the
digest has to agree either way. The aggregate hash is the SHA-256 of one
``relative-path\\0digest\\n`` record per file, in path order.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .constants import as_dict

MANIFEST_SCHEMA = 1
HASHED_PATHS = (
    "surprise/harness/**/*.py",
    "oracles/tlp.py", "oracles/tlp_groupby.py", "oracles/norec.py", "oracles/plan_variant.py",
    "oracles/errors.py", "oracles/determinism.py", "oracles/normalize.py", "oracles/models.py",
    "oracles/db_runner.py", "targets/duckdb_runner.py",
    "targets/datafusion_runner.py", "targets/sqlite_runner.py",
    "oracles/equivalence.py", "oracles/index_variant.py", "oracles/cross_engine.py",
    "oracles/differential.py", "oracles/_remote_exec.py", "scripts/cross_engine.py",
    "diagnosis/bisect.py",
)

# Old interpreters live beside the git common directory, same as version differential.
_OLD_VENVS = {
    "duckdb": "duckdb-1.1.3",
    "datafusion": "datafusion-50.0.0",
}
_PACKAGE_NAMES = ("duckdb", "datafusion", "pyarrow", "psycopg2-binary")
# Same default as harness.oracles.pg_reference. A connection failure stays None.
_DEFAULT_PG_DSN = (
    "host=127.0.0.1 port=55432 user=coevo dbname=postgres connect_timeout=5"
)

# framework/ is the directory that contains surprise/ and the legacy oracles/.
_FRAMEWORK_ROOT = Path(__file__).resolve().parents[2]
_GLOB_CHARS = frozenset("*?[")


def _framework_root() -> Path:
    return _FRAMEWORK_ROOT


def _ascii(text: str) -> str:
    """ASCII form of ``text``. Non-ASCII characters become ``\\uXXXX`` escapes."""
    return text.encode("ascii", "backslashreplace").decode("ascii")


def _ascii_line(text: str) -> str:
    flat = " ".join(str(text).split())
    return _ascii(flat)


def file_digest(path: str | Path) -> str:
    """SHA-256 hex digest of ``path``, with CRLF normalised to LF."""
    data = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def _is_glob(pattern: str) -> bool:
    return any(char in pattern for char in _GLOB_CHARS)


def _list_files(root: Path, patterns: tuple[str, ...]) -> list[str]:
    """Relative POSIX paths selected by ``patterns``, sorted and de-duplicated.

    A pattern with no wildcard that is not an existing file raises
    ``FileNotFoundError``. Files under ``__pycache__`` are dropped.
    """
    found: dict[str, None] = {}
    for pattern in patterns:
        if _is_glob(pattern):
            candidates = [match for match in root.glob(pattern) if match.is_file()]
        else:
            candidate = root / pattern
            if not candidate.is_file():
                raise FileNotFoundError(pattern)
            candidates = [candidate]
        for candidate in candidates:
            relative = candidate.relative_to(root)
            if "__pycache__" in relative.parts:
                continue
            found[relative.as_posix()] = None
    return sorted(found)


def harness_hash(*, root: str | Path | None = None, patterns: tuple[str, ...] | None = None) -> dict:
    """Hash every selected file and the sorted list of those digests.

    ``root`` defaults to the ``framework/`` directory next to this package.
    ``patterns`` defaults to :data:`HASHED_PATHS`. Both exist so tests can
    point at a temporary tree.
    """
    base = _framework_root() if root is None else Path(root)
    chosen = HASHED_PATHS if patterns is None else tuple(patterns)
    files: dict[str, str] = {}
    records: list[bytes] = []
    for relative in _list_files(base, chosen):
        digest = file_digest(base / relative)
        files[relative] = digest
        records.append(f"{relative}\0{digest}\n".encode("utf-8"))
    return {
        "algorithm": "sha256",
        "hash": hashlib.sha256(b"".join(records)).hexdigest(),
        "files": files,
    }


def _engine_version(distribution: str) -> str | None:
    """Installed distribution version, without importing the engine."""
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def _git_commit(root: Path) -> str | None:
    """HEAD of the repository that contains ``root``, or None if git cannot say."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    commit = proc.stdout.decode("ascii", "replace").strip()
    if not commit or not commit.isascii() or any(char.isspace() for char in commit):
        return None
    return commit


def _checkout_root() -> Path:
    return _FRAMEWORK_ROOT.parent


def _clean_env() -> dict[str, str]:
    """Process environment without the API key."""
    return {key: value for key, value in os.environ.items() if key.upper() != "DEEPSEEK_API_KEY"}


def _venvs_dir() -> Path:
    """Directory of versioned interpreters. ``COEVO_VENVS`` overrides the git-common location."""
    override = os.environ.get("COEVO_VENVS")
    if override:
        return Path(override)
    checkout = _checkout_root()
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=checkout,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=60,
            env=_clean_env(),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return checkout / ".venvs"
    common = proc.stdout.decode("utf-8", "replace").strip()
    if proc.returncode == 0 and common:
        return Path(common).parent / ".venvs"
    return checkout / ".venvs"


def _old_python(engine: str) -> Path | None:
    root = _venvs_dir() / _OLD_VENVS[engine]
    for relative in ("Scripts/python.exe", "bin/python"):
        candidate = root / relative
        if candidate.is_file():
            return candidate
    return None


def _old_engine_version(engine: str) -> str | None:
    """Version reported by the old venv, or None when that interpreter cannot say.

    The probe uses ``-I`` and an empty working directory so the checkout's
    ``duckdb/`` and ``datafusion/`` directories cannot shadow the real packages.
    """
    python = _old_python(engine)
    if python is None:
        return None
    code = f"import {engine}\nprint({engine}.__version__)\n"
    try:
        with tempfile.TemporaryDirectory(prefix="cve-old-") as empty:
            proc = subprocess.run(
                [str(python), "-I", "-c", code],
                cwd=empty,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=60,
                env=_clean_env(),
                check=False,
            )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    lines = [line.strip() for line in proc.stdout.decode("utf-8", "replace").splitlines() if line.strip()]
    if not lines:
        return None
    version = lines[-1]
    if not version.isascii() or any(char.isspace() for char in version):
        return None
    return version


def _postgres_server_version() -> str | None:
    """``server_version`` of the reference server, or None when it cannot be asked.

    The DSN is never included in a returned value.
    """
    dsn = os.environ.get("COEVO_REFERENCE_PG_DSN") or _DEFAULT_PG_DSN
    try:
        import psycopg2

        connection = psycopg2.connect(dsn)
        try:
            cursor = connection.cursor()
            cursor.execute("SHOW server_version")
            row = cursor.fetchone()
            cursor.close()
        finally:
            connection.close()
    except Exception:
        return None
    if not row or row[0] is None:
        return None
    version = str(row[0]).strip()
    if not version or not version.isascii():
        return None
    return version


def _package_versions() -> dict[str, str | None]:
    return {name: _engine_version(name) for name in _PACKAGE_NAMES}


def build_manifest(run_id: str, *, root: str | Path | None = None) -> dict:
    """JSON-safe description of one run and the harness that produced it."""
    base = _framework_root() if root is None else Path(root)
    return {
        "schema": MANIFEST_SCHEMA,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "harness": harness_hash(root=base),
        "constants": as_dict(),
        "environment": {
            "python": platform.python_version(),
            "platform": sys.platform,
            "engines": {
                "duckdb": _engine_version("duckdb"),
                "datafusion": _engine_version("datafusion"),
                "sqlite": sqlite3.sqlite_version,
            },
            "old_engines": {
                "duckdb": _old_engine_version("duckdb"),
                "datafusion": _old_engine_version("datafusion"),
            },
            "references": {"postgres": _postgres_server_version()},
            "packages": _package_versions(),
        },
        "git_commit": _git_commit(base),
    }


def _harness_record(manifest: dict) -> tuple[dict, str]:
    if not isinstance(manifest, dict):
        raise ValueError("manifest is not an object")
    harness = manifest.get("harness")
    if not isinstance(harness, dict):
        raise ValueError("manifest has no harness object")
    if "files" not in harness or "hash" not in harness:
        raise ValueError("manifest harness is missing files or hash")
    files = harness["files"]
    recorded = harness["hash"]
    if not isinstance(files, dict) or not isinstance(recorded, str):
        raise ValueError("manifest harness files or hash has the wrong type")
    return files, recorded


def verify_manifest(
    manifest: dict,
    *,
    root: str | Path | None = None,
    patterns: tuple[str, ...] | None = None,
) -> list[str]:
    """Compare ``manifest``'s harness record with a fresh hash of the disk.

    An empty list means nothing selected has changed. Findings are ASCII,
    file paths are in sorted order, and an aggregate mismatch is last.
    """
    recorded_files, recorded_hash = _harness_record(manifest)
    current = harness_hash(root=root, patterns=patterns)
    current_files = current["files"]
    problems: list[str] = []
    for path in sorted(set(recorded_files) | set(current_files)):
        # Newlines in a path would break the one-line-per-finding rule.
        safe = _ascii(path).replace("\n", "\\n").replace("\r", "\\r")
        on_record = path in recorded_files
        on_disk = path in current_files
        if on_record and on_disk:
            if recorded_files[path] != current_files[path]:
                problems.append(f"changed: {safe}")
        elif on_record:
            problems.append(f"missing: {safe}")
        else:
            problems.append(f"added: {safe}")
    if recorded_hash != current["hash"]:
        problems.append(_ascii(
            f"hash mismatch: manifest {recorded_hash[:12]} current {current['hash'][:12]}"
        ))
    return problems


def _print_error(reason: object) -> None:
    print(f"ERROR: {_ascii_line(reason)}")


def _verify_path(path: str) -> int:
    try:
        blob = Path(path).read_bytes()
    except OSError as exc:
        _print_error(exc)
        return 2
    try:
        text = blob.decode("utf-8")
    except UnicodeError as exc:
        _print_error(exc)
        return 2
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError as exc:
        _print_error(exc)
        return 2
    if not isinstance(loaded, dict):
        _print_error("manifest is not a JSON object")
        return 2
    try:
        problems = verify_manifest(loaded)
    except ValueError as exc:
        _print_error(exc)
        return 2
    if not problems:
        print(f"OK {loaded['harness']['hash']}")
        return 0
    for problem in problems:
        print(problem)
    print(f"MISMATCH ({len(problems)} problems)")
    return 1


def main(argv: list[str] | None = None) -> int:
    """``hash``, ``write``, and ``verify`` for the run manifest. See the module doc."""
    parser = argparse.ArgumentParser(prog="surprise.harness.manifest")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("hash", help="print the aggregate harness hash")
    write = commands.add_parser("write", help="write a manifest JSON file")
    write.add_argument("path")
    write.add_argument("--run-id", default="manual")
    verify = commands.add_parser("verify", help="compare a manifest file with the tree")
    verify.add_argument("path")
    args = parser.parse_args(argv)
    if args.command == "hash":
        print(harness_hash()["hash"])
        return 0
    if args.command == "write":
        manifest = build_manifest(args.run_id)
        payload = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
        Path(args.path).write_bytes(payload.encode("utf-8"))
        return 0
    return _verify_path(args.path)


if __name__ == "__main__":
    sys.exit(main())
