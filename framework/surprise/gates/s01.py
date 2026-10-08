"""S1 gate: Phase 0, frozen baseline and repository layout.

Usage (from ``framework/``)::

    python -m surprise.gates.s01

Exit code 0 = pass. Checks, following the S1 section of SESSIONS.md:

1. the tag ``v1-baseline`` still points at the baseline commit;
2. the ``surprise/`` skeleton exists and every subpackage imports;
3. every engine environment imports its engine and reports the expected
   version, each inside its own interpreter;
4. ``python main.py --help`` works;
5. pytest is green with at least the pre-reorganisation pass count;
6. the PG campaign scripts live in ``campaigns/`` and still start;
7. ``DuckDBRunner`` lives in ``targets/duckdb_runner.py``, with
   ``oracles/db_runner.py`` as the compatibility import, in every import order.

The engine venvs are not tracked. They sit in the main checkout, so when this
gate runs inside a git worktree it resolves them through the shared git
directory; ``COEVO_VENVS`` overrides the directory that holds them.
Output is ASCII only: the executors' shell garbles anything else.
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

FRAMEWORK = Path(__file__).resolve().parents[2]
CHECKOUT = FRAMEWORK.parent

BASELINE_TAG = "v1-baseline"
BASELINE_COMMIT = "55c55127dac26eed96abc10399c8a058859d793c"
# `pytest -q testing tests` before the reorganisation: 64 passed, 3 skipped.
BASELINE_PASSED = 64

SUBPACKAGES = ("harness", "features", "theory", "hunter", "diagnoser", "roles",
               "metrics", "experiments", "baselines", "gates")

# The interpreter running this gate is the main environment.
MAIN_ENGINES = {"duckdb": "1.5.5", "datafusion": "54.0.0"}
# venv directory name (under the venvs directory) -> {module: version}
SIDE_ENVS = {
    "duckdb-1.1.3": {"duckdb": "1.1.3"},
    "datafusion-50.0.0": {"datafusion": "50.0.0"},
}
OLD_DUCKDB_ENV = "duckdb-1.1.3"

PG_SCRIPT_COUNT = 41
# Campaign scripts that cannot answer --help; both behaved the same way in
# scripts/ before the move, so they are only checked for valid syntax.
NO_HELP = {
    "pg_repack_mvcc.py": "no argparse, runs its campaign at import",
    "pg_upgrade_mxact.py": "TypeError at module level (existing bug)",
}

# Import orders that must all work in a fresh interpreter: oracles and targets
# import each other once DuckDBRunner lives in targets/.
IMPORT_ORDERS = (
    "import oracles.db_runner, targets.duckdb_runner",
    "import targets.duckdb_runner, oracles.db_runner",
    "import targets, oracles",
    "from targets.postgres_runner import PostgresRunner",
    "from oracles import DuckDBRunner, QueryResult",
    "from oracles.db_runner import DuckDBRunner, QueryResult, bags_equal",
)
RUNNER_PROBE = """
import oracles.db_runner as shim
import targets.duckdb_runner as home
import targets.postgres_runner as pg
import targets.sqlite_runner as lite

assert shim.DuckDBRunner is home.DuckDBRunner, "re-export is a different class"
assert home.DuckDBRunner.__module__ == "targets.duckdb_runner", home.DuckDBRunner.__module__
assert pg.QueryResult is shim.QueryResult, "postgres runner sees another QueryResult"
assert lite.QueryResult is shim.QueryResult, "sqlite runner sees another QueryResult"
runner = shim.DuckDBRunner()
assert runner.setup(["CREATE TABLE t(a INTEGER)", "INSERT INTO t VALUES (1), (2), (NULL)"]) \\
    == [("CREATE TABLE t(a INTEGER)", None), ("INSERT INTO t VALUES (1), (2), (NULL)", None)]
result = runner.run("SELECT count(*), count(a), sum(a) FROM t")
assert isinstance(result, shim.QueryResult) and result.ok, result.error
assert result.rows == [[3, 2, 3]], result.rows
assert shim.bags_equal(result, runner.run("SELECT 3, 2, 3"))
assert runner.run("SELECT * FROM missing_table").error
runner.close()
print("PROBE_OK")
"""


class GateFailure(Exception):
    """A check did not hold; the message says what and why."""


def _env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k.upper() != "DEEPSEEK_API_KEY"}
    env.update(extra)
    return env


def _run(cmd: list[str], cwd: Path, timeout: float = 600.0,
         env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(c) for c in cmd], cwd=cwd, env=env or _env(), timeout=timeout,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        encoding="utf-8", errors="replace")


def _tail(text: str, lines: int = 6) -> str:
    return " | ".join(ln.strip() for ln in text.strip().splitlines()[-lines:])


def _git(*args: str) -> subprocess.CompletedProcess:
    return _run(["git", *args], CHECKOUT, timeout=60.0)


def venvs_dir() -> Path:
    override = os.environ.get("COEVO_VENVS")
    if override:
        return Path(override)
    # In a worktree the common git dir is <main checkout>/.git.
    proc = _git("rev-parse", "--path-format=absolute", "--git-common-dir")
    if proc.returncode == 0 and proc.stdout.strip():
        return Path(proc.stdout.strip()).parent / ".venvs"
    return CHECKOUT / ".venvs"


def venv_python(name: str) -> Path:
    root = venvs_dir() / name
    for candidate in (root / "Scripts" / "python.exe", root / "bin" / "python"):
        if candidate.is_file():
            return candidate
    raise GateFailure(f"no interpreter for environment {name} under {root}")


def engine_versions(python: Path | str, modules: list[str]) -> dict[str, str]:
    """Import `modules` in `python` and return their __version__.

    Runs isolated (-I) from an empty directory: the repository root holds
    `duckdb/` and `datafusion/` directories of repro SQL that would otherwise
    import as empty namespace packages and look like a working install.
    """
    code = ("import importlib, json; out = {}\n"
            f"for name in {modules!r}:\n"
            "    out[name] = getattr(importlib.import_module(name), '__version__', None)\n"
            "print('VERSIONS=' + json.dumps(out))")
    with tempfile.TemporaryDirectory() as empty:
        proc = _run([python, "-I", "-c", code], Path(empty), timeout=120.0)
    match = re.search(r"^VERSIONS=(.*)$", proc.stdout, re.M)
    if proc.returncode != 0 or not match:
        raise GateFailure(f"{python}: import failed: {_tail(proc.stdout)}")
    return json.loads(match.group(1))


# ---- checks -----------------------------------------------------------------

def check_baseline_tag() -> str:
    proc = _git("rev-parse", "-q", "--verify", f"refs/tags/{BASELINE_TAG}^{{commit}}")
    commit = proc.stdout.strip()
    if proc.returncode != 0 or commit != BASELINE_COMMIT:
        raise GateFailure(f"tag {BASELINE_TAG} is {commit or 'missing'}, "
                          f"expected {BASELINE_COMMIT}")
    return f"{BASELINE_TAG} -> {commit[:7]}"


def check_skeleton() -> str:
    surprise = FRAMEWORK / "surprise"
    wanted = [surprise / "__init__.py", surprise / "gates" / "all.py",
              *(surprise / sub / "__init__.py" for sub in SUBPACKAGES)]
    missing = [p.relative_to(FRAMEWORK).as_posix() for p in wanted if not p.is_file()]
    if missing:
        raise GateFailure("missing: " + ", ".join(missing))
    code = "import surprise\n" + "".join(f"import surprise.{s}\n" for s in SUBPACKAGES)
    proc = _run([sys.executable, "-c", code + "print(surprise.__file__)"], FRAMEWORK)
    if proc.returncode != 0:
        raise GateFailure("skeleton does not import: " + _tail(proc.stdout))
    return f"surprise/ + {len(SUBPACKAGES)} subpackages import"


def check_environments() -> str:
    seen = []
    main = engine_versions(sys.executable, [*MAIN_ENGINES, "sqlite3", "psycopg2"])
    for module, expected in MAIN_ENGINES.items():
        if main.get(module) != expected:
            raise GateFailure(f"main environment: {module} is {main.get(module)}, "
                              f"expected {expected}")
        seen.append(f"{module} {expected}")
    with tempfile.TemporaryDirectory() as empty:
        proc = _run([sys.executable, "-I", "-c",
                     "import sqlite3; print('SQLITE=' + sqlite3.sqlite_version)"],
                    Path(empty), timeout=60.0)
    match = re.search(r"^SQLITE=(\S+)$", proc.stdout, re.M)
    if not match:
        raise GateFailure("main environment: sqlite3 not usable: " + _tail(proc.stdout))
    seen.append(f"sqlite {match.group(1)}")
    for name, engines in SIDE_ENVS.items():
        found = engine_versions(venv_python(name), list(engines))
        for module, expected in engines.items():
            if found.get(module) != expected:
                raise GateFailure(f"environment {name}: {module} is {found.get(module)}, "
                                  f"expected {expected}")
            seen.append(f"{name}: {module} {expected}")
    return "; ".join(seen)


def check_main_help() -> str:
    proc = _run([sys.executable, "main.py", "--help"], FRAMEWORK, timeout=120.0)
    if proc.returncode != 0 or "usage:" not in proc.stdout:
        raise GateFailure(f"main.py --help exit {proc.returncode}: {_tail(proc.stdout)}")
    return "exit 0"


def check_pytest() -> str:
    proc = _run([sys.executable, "-m", "pytest", "-q", "testing", "tests"],
                FRAMEWORK, timeout=1800.0)
    match = re.search(r"(\d+) passed", proc.stdout)
    passed = int(match.group(1)) if match else 0
    if proc.returncode != 0:
        raise GateFailure(f"pytest exit {proc.returncode}: {_tail(proc.stdout, 12)}")
    if passed < BASELINE_PASSED:
        raise GateFailure(f"{passed} passed, baseline is {BASELINE_PASSED}")
    return f"{passed} passed (baseline {BASELINE_PASSED}): {_tail(proc.stdout, 1)}"


def check_campaigns() -> str:
    proc = _git("ls-tree", "-r", "--name-only", BASELINE_TAG, "--", "framework/scripts")
    names = sorted(Path(line).name for line in proc.stdout.splitlines()
                   if re.fullmatch(r"pg_\w+\.py", Path(line).name))
    if proc.returncode != 0 or len(names) != PG_SCRIPT_COUNT:
        raise GateFailure(f"expected {PG_SCRIPT_COUNT} pg_*.py at {BASELINE_TAG}, "
                          f"found {len(names)}: {_tail(proc.stdout, 2)}")
    campaigns, scripts = FRAMEWORK / "campaigns", FRAMEWORK / "scripts"
    not_moved = [n for n in names if not (campaigns / n).is_file()]
    if not_moved:
        raise GateFailure(f"{len(not_moved)} scripts not in campaigns/: "
                          + ", ".join(not_moved[:5]))
    left = sorted(p.name for p in scripts.glob("pg_*.py"))
    if left:
        raise GateFailure(f"{len(left)} pg_*.py still in scripts/: " + ", ".join(left[:5]))
    if (campaigns / "__init__.py").exists() != (scripts / "__init__.py").exists():
        raise GateFailure("campaigns/ and scripts/ must agree on having __init__.py "
                          "(both are namespace packages at the baseline)")
    broken = []
    for name in names:
        if name in NO_HELP:
            try:
                ast.parse((campaigns / name).read_text(encoding="utf-8"), filename=name)
            except SyntaxError as exc:
                broken.append(f"{name}: {exc}")
            continue
        help_run = _run([sys.executable, f"campaigns/{name}", "--help"], FRAMEWORK,
                        timeout=120.0)
        if help_run.returncode != 0 or "usage" not in help_run.stdout.lower():
            broken.append(f"{name}: exit {help_run.returncode}: {_tail(help_run.stdout, 2)}")
    if broken:
        raise GateFailure(f"{len(broken)} campaign scripts broken: " + " || ".join(broken[:4]))
    return (f"{len(names)} scripts in campaigns/, "
            f"{len(names) - len(NO_HELP)} answer --help, {len(NO_HELP)} syntax-checked")


def check_duckdb_runner() -> str:
    if not (FRAMEWORK / "targets" / "duckdb_runner.py").is_file():
        raise GateFailure("framework/targets/duckdb_runner.py does not exist")
    if not (FRAMEWORK / "oracles" / "db_runner.py").is_file():
        raise GateFailure("framework/oracles/db_runner.py (compatibility import) is gone")
    for order in IMPORT_ORDERS:
        proc = _run([sys.executable, "-c", order + RUNNER_PROBE], FRAMEWORK, timeout=120.0)
        if proc.returncode != 0 or "PROBE_OK" not in proc.stdout:
            raise GateFailure(f"after `{order}`: {_tail(proc.stdout, 4)}")
    # The version-differential oracle starts `python -m oracles._remote_exec`
    # in the old-DuckDB venv; that import now reaches targets/ as well.
    with tempfile.TemporaryDirectory() as empty:
        proc = _run([venv_python(OLD_DUCKDB_ENV), "-c",
                     "import oracles._remote_exec; print('REMOTE_OK')"],
                    Path(empty), timeout=120.0, env=_env(PYTHONPATH=str(FRAMEWORK)))
    if proc.returncode != 0 or "REMOTE_OK" not in proc.stdout:
        raise GateFailure(f"oracles._remote_exec does not import in {OLD_DUCKDB_ENV}: "
                          + _tail(proc.stdout, 4))
    return f"{len(IMPORT_ORDERS)} import orders ok; _remote_exec imports in {OLD_DUCKDB_ENV}"


CHECKS: list[tuple[str, Callable[[], str]]] = [
    ("baseline tag", check_baseline_tag),
    ("skeleton", check_skeleton),
    ("engine environments", check_environments),
    ("main.py --help", check_main_help),
    ("pytest", check_pytest),
    ("campaign scripts", check_campaigns),
    ("DuckDBRunner move", check_duckdb_runner),
]


def main() -> int:
    failed = 0
    for name, check in CHECKS:
        try:
            print(f"[PASS] {name}: {check()}", flush=True)
        except GateFailure as exc:
            failed += 1
            print(f"[FAIL] {name}: {exc}", flush=True)
        except Exception as exc:  # noqa: BLE001 - a crashing check is a failed check
            failed += 1
            print(f"[FAIL] {name}: {type(exc).__name__}: {exc}", flush=True)
    print(f"S01 GATE: {'PASS' if not failed else 'FAIL'}"
          f" ({len(CHECKS) - failed}/{len(CHECKS)} checks passed)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
