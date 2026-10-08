"""Hash, manifest, and verify command for the surprise harness.

Temporary trees go through ``root`` and ``patterns``. Nothing here writes a
tracked file.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from surprise.harness.constants import as_dict
from surprise.harness.manifest import (
    HASHED_PATHS,
    MANIFEST_SCHEMA,
    build_manifest,
    file_digest,
    harness_hash,
    verify_manifest,
)

FRAMEWORK = Path(__file__).resolve().parents[1]
PATTERNS = (
    "surprise/harness/**/*.py",
    "oracles/tlp.py",
    "targets/duckdb_runner.py",
)
EXPECTED = (
    "oracles/tlp.py",
    "surprise/harness/a.py",
    "surprise/harness/nested/b.py",
    "targets/duckdb_runner.py",
)


def _fake_tree(root: Path) -> Path:
    files = {
        "surprise/harness/a.py": b"a = 1\n",
        "surprise/harness/nested/b.py": b"b = 2\r\n",
        "surprise/harness/__pycache__/a.cpython-313.py": b"cached = True\n",
        "surprise/harness/note.txt": b"not hashed\n",
        "oracles/tlp.py": b"def tlp():\r\n    return 1\r\n",
        "oracles/extra.py": b"not in the pattern\n",
        "targets/duckdb_runner.py": b"RUNNER = 1\n",
    }
    for relative, data in files.items():
        path = root.joinpath(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return root


def _wrap(info: dict) -> dict:
    return {
        "harness": {
            "algorithm": info["algorithm"],
            "hash": info["hash"],
            "files": dict(info["files"]),
        }
    }


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "surprise.harness.manifest", *args],
        cwd=FRAMEWORK,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _aggregate(files: dict[str, str]) -> str:
    blob = b"".join(f"{path}\0{files[path]}\n".encode("utf-8") for path in sorted(files))
    return hashlib.sha256(blob).hexdigest()


def test_file_digest_ignores_line_endings_and_tracks_content(tmp_path: Path) -> None:
    lf = tmp_path / "lf.py"
    crlf = tmp_path / "crlf.py"
    other = tmp_path / "other.py"
    bare_cr = tmp_path / "cr.py"
    lf.write_bytes(b"a = 1\nb = 2\n")
    crlf.write_bytes(b"a = 1\r\nb = 2\r\n")
    other.write_bytes(b"a = 1\nb = 3\n")
    bare_cr.write_bytes(b"a\rb\n")

    expected = hashlib.sha256(b"a = 1\nb = 2\n").hexdigest()
    assert file_digest(lf) == expected
    assert file_digest(crlf) == expected
    assert file_digest(other) != expected
    assert file_digest(bare_cr) == hashlib.sha256(b"a\rb\n").hexdigest()


def test_pattern_expansion_skips_pycache_and_duplicates(tmp_path: Path) -> None:
    root = _fake_tree(tmp_path)
    info = harness_hash(root=root, patterns=PATTERNS)
    again = harness_hash(root=root, patterns=PATTERNS + ("oracles/tlp.py",))

    assert info["algorithm"] == "sha256"
    assert tuple(info["files"]) == EXPECTED
    assert again["files"] == info["files"]
    assert info["hash"] == _aggregate(info["files"])
    assert all(len(digest) == 64 for digest in info["files"].values())
    assert "surprise/harness/__pycache__/a.cpython-313.py" not in info["files"]
    assert "oracles/extra.py" not in info["files"]
    assert "surprise/harness/note.txt" not in info["files"]

    cached = root / "surprise" / "harness" / "__pycache__" / "a.cpython-313.py"
    cached.write_bytes(b"cached = False\n")
    (root / "oracles" / "extra.py").write_bytes(b"still ignored\n")
    assert harness_hash(root=root, patterns=PATTERNS) == info

    (root / "oracles" / "tlp.py").write_bytes(b"def tlp():\n    return 2\n")
    changed = harness_hash(root=root, patterns=PATTERNS)
    assert changed["hash"] != info["hash"]
    assert changed["files"]["oracles/tlp.py"] != info["files"]["oracles/tlp.py"]
    assert changed["files"]["surprise/harness/a.py"] == info["files"]["surprise/harness/a.py"]


def test_harness_hash_is_stable_across_processes(tmp_path: Path) -> None:
    root = _fake_tree(tmp_path)
    local = harness_hash(root=root, patterns=PATTERNS)
    assert harness_hash(root=root, patterns=PATTERNS) == local

    script = (
        "import json\n"
        "from surprise.harness.manifest import harness_hash\n"
        "root, patterns = json.loads(input())\n"
        "print(json.dumps(harness_hash(root=root, patterns=patterns), sort_keys=True))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        input=json.dumps([str(root), list(PATTERNS)]),
        cwd=FRAMEWORK,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == local


def test_missing_literal_raises_and_empty_glob_does_not(tmp_path: Path) -> None:
    root = _fake_tree(tmp_path)
    with pytest.raises(FileNotFoundError, match="oracles/absent.py"):
        harness_hash(root=root, patterns=("oracles/absent.py",))

    empty = harness_hash(root=root, patterns=("no/such/**/*.py",))
    assert empty["files"] == {}
    assert empty["hash"] == hashlib.sha256(b"").hexdigest()

    with pytest.raises(FileNotFoundError, match="oracles/tlp_groupby.py"):
        build_manifest("fake-root", root=root)


def test_verify_reports_each_kind_of_change(tmp_path: Path) -> None:
    changed_root = _fake_tree(tmp_path / "changed")
    changed_manifest = _wrap(harness_hash(root=changed_root, patterns=PATTERNS))
    (changed_root / "surprise" / "harness" / "a.py").write_bytes(b"a = 9\n")
    changed_now = harness_hash(root=changed_root, patterns=PATTERNS)
    recorded = changed_manifest["harness"]["hash"]
    assert verify_manifest(changed_manifest, root=changed_root, patterns=PATTERNS) == [
        "changed: surprise/harness/a.py",
        f"hash mismatch: manifest {recorded[:12]} current {changed_now['hash'][:12]}",
    ]

    deleted_root = _fake_tree(tmp_path / "deleted")
    deleted_manifest = _wrap(harness_hash(root=deleted_root, patterns=PATTERNS))
    (deleted_root / "surprise" / "harness" / "nested" / "b.py").unlink()
    deleted_now = harness_hash(root=deleted_root, patterns=PATTERNS)
    recorded = deleted_manifest["harness"]["hash"]
    assert verify_manifest(deleted_manifest, root=deleted_root, patterns=PATTERNS) == [
        "missing: surprise/harness/nested/b.py",
        f"hash mismatch: manifest {recorded[:12]} current {deleted_now['hash'][:12]}",
    ]

    added_root = _fake_tree(tmp_path / "added")
    added_manifest = _wrap(harness_hash(root=added_root, patterns=PATTERNS))
    (added_root / "surprise" / "harness" / "c.py").write_bytes(b"c = 3\n")
    added_now = harness_hash(root=added_root, patterns=PATTERNS)
    recorded = added_manifest["harness"]["hash"]
    assert verify_manifest(added_manifest, root=added_root, patterns=PATTERNS) == [
        "added: surprise/harness/c.py",
        f"hash mismatch: manifest {recorded[:12]} current {added_now['hash'][:12]}",
    ]

    both_root = _fake_tree(tmp_path / "both")
    both_manifest = _wrap(harness_hash(root=both_root, patterns=PATTERNS))
    (both_root / "surprise" / "harness" / "a.py").write_bytes(b"a = 4\n")
    (both_root / "surprise" / "harness" / "c.py").write_bytes(b"c = 5\n")
    both_now = harness_hash(root=both_root, patterns=PATTERNS)
    recorded = both_manifest["harness"]["hash"]
    assert verify_manifest(both_manifest, root=both_root, patterns=PATTERNS) == [
        "changed: surprise/harness/a.py",
        "added: surprise/harness/c.py",
        f"hash mismatch: manifest {recorded[:12]} current {both_now['hash'][:12]}",
    ]

    hash_root = _fake_tree(tmp_path / "hash")
    hash_info = harness_hash(root=hash_root, patterns=PATTERNS)
    hash_manifest = _wrap(hash_info)
    hash_manifest["harness"]["hash"] = "f" * 64
    assert verify_manifest(hash_manifest, root=hash_root, patterns=PATTERNS) == [
        f"hash mismatch: manifest {'f' * 12} current {hash_info['hash'][:12]}",
    ]

    # A rewritten per-file digest leaves the stored aggregate alone, so the
    # aggregate line stays quiet while the path is still reported.
    quiet_root = _fake_tree(tmp_path / "quiet")
    quiet_manifest = _wrap(harness_hash(root=quiet_root, patterns=PATTERNS))
    quiet_manifest["harness"]["files"]["oracles/tlp.py"] = "0" * 64
    assert verify_manifest(quiet_manifest, root=quiet_root, patterns=PATTERNS) == [
        "changed: oracles/tlp.py",
    ]

    literal_root = _fake_tree(tmp_path / "literal")
    literal_manifest = _wrap(harness_hash(root=literal_root, patterns=PATTERNS))
    (literal_root / "oracles" / "tlp.py").unlink()
    with pytest.raises(FileNotFoundError, match="oracles/tlp.py"):
        verify_manifest(literal_manifest, root=literal_root, patterns=PATTERNS)

    ghost_root = _fake_tree(tmp_path / "ghost")
    ghost_manifest = _wrap(harness_hash(root=ghost_root, patterns=PATTERNS))
    ghost_manifest["harness"]["files"]["oracles/\u5e7d\u7075.py"] = "1" * 64
    ghost_problems = verify_manifest(ghost_manifest, root=ghost_root, patterns=PATTERNS)
    assert ghost_problems == ["missing: oracles/\\u5e7d\\u7075.py"]
    assert all(problem.isascii() for problem in ghost_problems)

    clean_root = _fake_tree(tmp_path / "clean")
    clean = _wrap(harness_hash(root=clean_root, patterns=PATTERNS))
    assert verify_manifest(clean, root=clean_root, patterns=PATTERNS) == []


def test_verify_rejects_a_malformed_manifest(tmp_path: Path) -> None:
    root = _fake_tree(tmp_path)
    valid = _wrap(harness_hash(root=root, patterns=PATTERNS))
    assert verify_manifest(valid, root=root, patterns=PATTERNS) == []

    bad = [
        {},
        {"harness": None},
        {"harness": []},
        {"harness": {}},
        {"harness": {"files": {}}},
        {"harness": {"hash": "abc"}},
        {"harness": {"files": [], "hash": "abc"}},
        {"harness": {"files": {}, "hash": 1}},
    ]
    for manifest in bad:
        with pytest.raises(ValueError):
            verify_manifest(manifest, root=root, patterns=PATTERNS)


def test_build_manifest_on_the_real_tree() -> None:
    before = datetime.now(timezone.utc)
    manifest = build_manifest("unit-test")
    after = datetime.now(timezone.utc)

    assert set(manifest) == {
        "schema",
        "run_id",
        "created_at",
        "harness",
        "constants",
        "environment",
        "git_commit",
    }
    assert manifest["schema"] == MANIFEST_SCHEMA == 1
    assert manifest["run_id"] == "unit-test"
    created = datetime.fromisoformat(manifest["created_at"])
    assert created.tzinfo is not None and created.utcoffset() == timedelta(0)
    assert before <= created <= after
    assert manifest["harness"] == harness_hash()
    assert manifest["constants"] == as_dict()
    assert manifest["environment"] == {
        "python": platform.python_version(),
        "platform": sys.platform,
        "engines": {
            "duckdb": importlib.metadata.version("duckdb"),
            "datafusion": importlib.metadata.version("datafusion"),
            "sqlite": sqlite3.sqlite_version,
        },
    }
    proc = subprocess.run(
        ["git", "-C", str(FRAMEWORK), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    expected_commit = proc.stdout.strip() if proc.returncode == 0 else None
    assert manifest["git_commit"] == expected_commit
    assert expected_commit is not None and len(expected_commit) >= 40

    encoded = json.dumps(manifest)
    assert encoded.isascii()
    assert json.loads(encoded) == manifest
    secret = os.environ.get("DEEPSEEK_API_KEY")
    if secret:
        assert secret not in encoded
    assert verify_manifest(manifest) == []

    covered = {
        path.relative_to(FRAMEWORK).as_posix()
        for path in (FRAMEWORK / "surprise" / "harness").rglob("*.py")
        if "__pycache__" not in path.parts
    }
    covered.update(pattern for pattern in HASHED_PATHS if not any(char in pattern for char in "*?["))
    assert covered <= set(manifest["harness"]["files"])


def test_cli_hash_write_and_verify(tmp_path: Path) -> None:
    hashed = _cli("hash")
    assert hashed.returncode == 0
    assert hashed.stdout == harness_hash()["hash"] + "\n"
    assert hashed.stdout.isascii()

    destination = tmp_path / "manifest.json"
    written = _cli("write", str(destination), "--run-id", "cli-run")
    assert written.returncode == 0
    assert written.stdout == ""
    raw = destination.read_bytes()
    assert b"\r" not in raw
    text = raw.decode("ascii")
    loaded = json.loads(text)
    assert text == json.dumps(loaded, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    assert loaded["run_id"] == "cli-run"
    assert loaded["harness"] == harness_hash()
    assert list(loaded) == sorted(loaded)

    manual = tmp_path / "manual.json"
    default_id = _cli("write", str(manual))
    assert default_id.returncode == 0
    assert json.loads(manual.read_text(encoding="utf-8"))["run_id"] == "manual"

    escaped = tmp_path / "escaped.json"
    non_ascii = _cli("write", str(escaped), "--run-id", "\u624b\u518c")
    assert non_ascii.returncode == 0
    escaped_bytes = escaped.read_bytes()
    assert escaped_bytes.isascii()
    assert json.loads(escaped_bytes.decode("ascii"))["run_id"] == "\u624b\u518c"

    verified = _cli("verify", str(destination))
    assert verified.returncode == 0
    assert verified.stdout == f"OK {loaded['harness']['hash']}\n"

    tampered = json.loads(text)
    tampered["harness"]["files"]["oracles/tlp.py"] = "0" * 64
    bad = tmp_path / "tampered.json"
    bad.write_bytes(json.dumps(tampered).encode("utf-8"))
    rejected = _cli("verify", str(bad))
    assert rejected.returncode == 1
    assert rejected.stdout == "changed: oracles/tlp.py\nMISMATCH (1 problems)\n"

    shifted = json.loads(text)
    shifted["harness"]["hash"] = "a" * 64
    shifted_path = tmp_path / "shifted.json"
    shifted_path.write_bytes(json.dumps(shifted).encode("utf-8"))
    mismatch = _cli("verify", str(shifted_path))
    current = loaded["harness"]["hash"][:12]
    assert mismatch.returncode == 1
    assert mismatch.stdout == (
        f"hash mismatch: manifest {'a' * 12} current {current}\nMISMATCH (1 problems)\n"
    )

    absent = _cli("verify", str(tmp_path / "\u6ca1\u6709.json"))
    assert absent.returncode == 2
    assert absent.stdout.startswith("ERROR:")
    assert absent.stdout.isascii()
    assert "Traceback" not in absent.stderr

    junk = tmp_path / "junk.json"
    junk.write_bytes(b"{")
    broken = _cli("verify", str(junk))
    assert broken.returncode == 2
    assert broken.stdout.startswith("ERROR:")
    assert broken.stdout.isascii()

    empty = tmp_path / "empty.json"
    empty.write_bytes(b"{}")
    unstructured = _cli("verify", str(empty))
    assert unstructured.returncode == 2
    assert unstructured.stdout.startswith("ERROR:")
    assert "harness" in unstructured.stdout

    array = tmp_path / "array.json"
    array.write_bytes(b"[]")
    not_object = _cli("verify", str(array))
    assert not_object.returncode == 2
    assert not_object.stdout.startswith("ERROR:")
