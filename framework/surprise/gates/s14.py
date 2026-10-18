"""S14 gate: the experiment server, and green on both platforms.

Usage (from ``framework/``)::

    python -m surprise.gates.s14                        # everything
    python -m surprise.gates.s14 --only env docs
    python -m surprise.gates.s14 --record DIR           # on the server: probe, pytest, gates.all -> DIR
    python -m surprise.gates.s14 --ingest-smoke GRID    # on Windows: copy the user's smoke grid into
                                                        # s14_evidence/smoke

Exit code 0 = pass. Groups, following the S14 section of SESSIONS.md:

``env``    the live environment matches the version table at the end of SERVER.md. On the server
           that includes the Linux-only rows: the JDK, no ``trust`` line in the PostgreSQL
           reference's pg_hba, the old code's default paths overridden, a clean tag checkout. On
           Windows the server's recorded probe (``s14_evidence/linux_env.json``) is checked against
           the same table, and the two platforms must agree on SQLite (source id, and compile options
           apart from the platform ones);
``linux``  (Windows) the server ran pytest and ``gates.all`` on the same code as this work tree,
           both green, with no more skips than Windows had;
``smoke``  (Windows) the user's one-minute smoke grid (SERVER.md 5.6) ran on the server on the same
           code: every cell done, the cell's manifest says Linux, carries the frozen harness hash and
           the pinned engine versions, and the grid report has every RQ section;
``docs``   SERVER.md has its sections in order, the runbook's commands exist, the smoke config
           loads and needs no network, HANDOFF.md has an S14 status row;
``scope``  S14 changed only the docs, its own gate files, the s03 gate's platform fix and the files
           of merged platform-fix packages; the harness and the frozen manifest are untouched.

On the server ``linux`` and ``smoke`` do not apply (they read what the server produces) and say so.
Output is ASCII only. No group makes a network call except to the local PostgreSQL reference.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import s14_cases as C
from .s06 import GateFailure, _ascii, require

FRAMEWORK = Path(__file__).resolve().parents[2]
REPO = FRAMEWORK.parent
GATES_DIR = Path(__file__).resolve().parent
EVIDENCE = REPO / C.EVIDENCE
LINUX = sys.platform.startswith("linux")
GATE_RE = re.compile(r"^s\d{2}\.py$")


# ---- helpers ------------------------------------------------------------------------------------

def git(*args: str, check: bool = True, cwd: Path = REPO) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, timeout=300)
    if check:
        require(proc.returncode == 0,
                f"git {' '.join(args)}: {proc.stderr.decode('utf-8', 'replace')[-300:]}")
    return proc.stdout.decode("utf-8", "replace")


def read(relative: str) -> str:
    path = REPO / relative
    require(path.is_file(), f"{relative}: missing")
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def load_json(path: Path, what: str) -> Any:
    require(path.is_file(), f"{what}: missing ({path.relative_to(REPO) if path.is_relative_to(REPO) else path})")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GateFailure(f"{what}: not JSON: {exc}") from exc


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def spec() -> dict[str, Any]:
    text = read(C.SERVER)
    require(C.SPEC_HEADING in text, f"SERVER.md: no heading {C.SPEC_HEADING!r}")
    tail = text.split(C.SPEC_HEADING, 1)[1]
    match = re.search(r"```json\n(.*?)\n```", tail, re.S)
    require(match is not None, "SERVER.md: no ```json block under the spec heading")
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise GateFailure(f"SERVER.md spec is not JSON: {exc}") from exc
    require(isinstance(data, dict) and data.get("schema") == 1, "spec: schema must be 1")
    for key in ("python", "sqlite", "venvs", "postgres", "src", "linux"):
        require(key in data, f"spec: missing {key!r}")
    return data


def checkout_root() -> Path:
    """The main checkout: ``.venv``, ``.src`` and ``.orch`` sit beside the git common directory."""
    proc = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                          cwd=REPO, capture_output=True, text=True, timeout=60)
    common = proc.stdout.strip()
    if proc.returncode == 0 and common:
        return Path(common).parent
    return REPO


def venv_dir(name: str) -> Path:
    override = os.environ.get("COEVO_VENVS")
    if name.startswith(".venvs/") and override:
        return Path(override) / name.split("/", 1)[1]
    return checkout_root() / name


def venv_python(root: Path) -> Path:
    for relative in ("Scripts/python.exe", "bin/python"):
        if (root / relative).exists():
            return root / relative
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run_python(python: Path, code: str, *args: str, timeout: float = 120.0) -> Any:
    require(python.exists(), f"interpreter missing: {python}")
    proc = subprocess.run([str(python), "-I", "-c", code, *args], cwd=FRAMEWORK, capture_output=True,
                          text=True, timeout=timeout)
    require(proc.returncode == 0, f"{python}: exit {proc.returncode}: {_ascii(proc.stderr[-400:])}")
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise GateFailure(f"{python}: no JSON on stdout: {_ascii(proc.stdout[-200:])}") from exc


_PACKAGES_CODE = (
    "import importlib.metadata as m, json, sys\n"
    "out = {}\n"
    "for name in sys.argv[1:]:\n"
    "    try:\n"
    "        out[name] = m.version(name)\n"
    "    except m.PackageNotFoundError:\n"
    "        out[name] = None\n"
    "print(json.dumps({'python': sys.version.split()[0], 'packages': out}))\n"
)

_SQLITE_CODE = (
    "import json, sqlite3\n"
    "c = sqlite3.connect(':memory:')\n"
    "print(json.dumps({'version': sqlite3.sqlite_version,\n"
    "                  'source_id': c.execute('select sqlite_source_id()').fetchone()[0],\n"
    "                  'compile_options': sorted(r[0] for r in c.execute('pragma compile_options'))}))\n"
)


# ---- probe --------------------------------------------------------------------------------------

def probe_postgres() -> dict[str, Any]:
    import psycopg2

    dsn = os.environ.get("COEVO_REFERENCE_PG_DSN") or C.PG_DSN
    try:
        connection = psycopg2.connect(dsn)
    except Exception as exc:  # noqa: BLE001 - report why the reference is unreachable
        raise GateFailure(f"PostgreSQL reference unreachable: {type(exc).__name__}: {_ascii(exc)[:200]}") from exc
    found: dict[str, Any] = {}
    try:
        connection.autocommit = True
        cursor = connection.cursor()
        for name in C.PG_SETTINGS:
            cursor.execute("select current_setting(%s)", (name,))
            found[name] = cursor.fetchone()[0]
        cursor.execute("select datcollate, datctype, datlocprovider from pg_database"
                       " where datname = current_database()")
        found["datcollate"], found["datctype"], found["datlocprovider"] = cursor.fetchone()
        cursor.execute("select collversion from pg_collation where collname = 'und-x-icu'")
        row = cursor.fetchone()
        found["icu_collversion"] = None if row is None else row[0]
        try:
            cursor.execute("select count(*) from pg_hba_file_rules where auth_method = 'trust'")
            found["trust_rules"] = int(cursor.fetchone()[0])
        except Exception:  # noqa: BLE001 - not a superuser: unknown, and the check fails on Linux
            found["trust_rules"] = None
        cursor.close()
    finally:
        connection.close()
    return found


def probe_java() -> dict[str, Any]:
    candidates = sorted((checkout_root() / ".orch" / "jdk").glob("*/bin/java"))
    if len(candidates) != 1:
        return {"java": None, "candidates": [str(path) for path in candidates]}
    proc = subprocess.run([str(candidates[0]), "-version"], capture_output=True, text=True, timeout=60)
    match = re.search(r'version "([^"]+)"', proc.stderr + proc.stdout)
    return {"java": match.group(1) if match else None, "path": str(candidates[0].relative_to(checkout_root()))}


def probe_overrides(names: list[str]) -> dict[str, Any]:
    paths = importlib.import_module("util.paths")
    attributes = {"COEVO_PGBLD": "PGBLD", "COEVO_OLD_VENV": "OLD_VENV", "COEVO_DUCKDB_SRC": "DUCKDB_SRC",
                  "COEVO_ARGUS_DIR": "ARGUS_DIR", "COEVO_KEYS_YML": "KEYS_YML"}
    found: dict[str, Any] = {}
    for name in names:
        value = os.environ.get(name)
        entry: dict[str, Any] = {"value": value, "resolved": str(getattr(paths, attributes.get(name, ""), "")) or None}
        if value:
            try:
                entry["exists"] = Path(value).exists()
            except OSError as exc:
                entry["exists"] = f"{type(exc).__name__}"
        found[name] = entry
    return found


def probe(table: dict[str, Any]) -> dict[str, Any]:
    """Everything the version table speaks about, measured on this machine."""
    venvs: dict[str, Any] = {}
    main_python = venv_python(venv_dir(".venv"))
    for name, expected in table["venvs"].items():
        python = venv_python(venv_dir(name))
        if not python.exists():
            venvs[name] = None
            continue
        venvs[name] = run_python(python, _PACKAGES_CODE, *sorted(expected))
    src = {}
    for name in table["src"]:
        path = checkout_root() / name
        src[name] = git("rev-parse", "HEAD", cwd=path).strip() if (path / ".git").exists() else None
    found: dict[str, Any] = {
        "schema": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "platform": sys.platform,
        "python": (venvs.get(".venv") or {}).get("python"),
        "sqlite": run_python(main_python, _SQLITE_CODE),
        "venvs": venvs,
        "postgres": probe_postgres(),
        "src": src,
        "git": {
            "commit": git("rev-parse", "HEAD").strip(),
            "tag": git("describe", "--tags", "--exact-match", "HEAD", check=False).strip() or None,
            "dirty": git("status", "--porcelain", "--untracked-files=no").strip(),
        },
    }
    if sys.platform.startswith("linux"):
        found["java"] = probe_java()
        found["overrides"] = probe_overrides(list(table["linux"]["old_code_overrides"]))
    return found


# ---- checks -------------------------------------------------------------------------------------

def check_probe(found: dict[str, Any], table: dict[str, Any], *, linux: bool, where: str) -> str:
    require(found.get("python") == table["python"], f"{where}: python {found.get('python')!r} != {table['python']!r}")
    sqlite = found.get("sqlite") or {}
    for key in ("version", "source_id"):
        require(sqlite.get(key) == table["sqlite"][key], f"{where}: sqlite {key} {sqlite.get(key)!r}")
    for name, expected in table["venvs"].items():
        got = (found.get("venvs") or {}).get(name)
        require(got is not None, f"{where}: {name} missing")
        require(got.get("python") == table["python"], f"{where}: {name} python {got.get('python')!r}")
        packages = got.get("packages") or {}
        wrong = {dist: packages.get(dist) for dist, version in expected.items() if packages.get(dist) != version}
        require(not wrong, f"{where}: {name} packages differ: {wrong} (expected {expected})")
    postgres = found.get("postgres") or {}
    wrong_pg = {key: postgres.get(key) for key, value in table["postgres"].items() if postgres.get(key) != value}
    require(not wrong_pg, f"{where}: PostgreSQL reference differs: {wrong_pg}")
    wrong_src = {name: (found.get("src") or {}).get(name) for name, commit in table["src"].items()
                 if (found.get("src") or {}).get(name) != commit}
    require(not wrong_src, f"{where}: source checkouts differ: {wrong_src}")
    if not linux:
        return f"{where}: python, sqlite, {len(table['venvs'])} venvs, PG reference, sources"
    rows = table["linux"]
    java = (found.get("java") or {}).get("java")
    require(java == rows["java"], f"{where}: JDK {java!r} != {rows['java']!r} ({found.get('java')})")
    require(postgres.get("trust_rules") == rows["pg_trust_rules"],
            f"{where}: pg_hba trust rules {postgres.get('trust_rules')!r}, expected {rows['pg_trust_rules']}")
    overrides = found.get("overrides") or {}
    for name in rows["old_code_overrides"]:
        entry = overrides.get(name) or {}
        value = entry.get("value")
        require(isinstance(value, str) and value, f"{where}: {name} is not set (see SERVER.md section 6)")
        require(not value.startswith(C.OLD_CODE_DEFAULT_ROOT), f"{where}: {name} still points into {C.OLD_CODE_DEFAULT_ROOT}")
        require(entry.get("exists") is False, f"{where}: {name}={value} exists or cannot be checked: {entry.get('exists')!r}")
        require(entry.get("resolved") == value, f"{where}: util.paths resolves {name} to {entry.get('resolved')!r}")
    git_state = found.get("git") or {}
    require(git_state.get("tag"), f"{where}: the checkout is not on a tag ({git_state.get('commit')})")
    require(git_state.get("dirty") == "", f"{where}: tracked files modified: {git_state.get('dirty')[:200]!r}")
    return (f"{where}: python, sqlite, {len(table['venvs'])} venvs, PG reference (no trust rules), "
            f"sources, JDK {java}, old-code overrides, clean checkout of {git_state.get('tag')}")


def _platform_free(options: list[str], prefixes: list[str]) -> list[str]:
    return sorted(option for option in options if not any(option.startswith(prefix) for prefix in prefixes))


def check_cross(windows: dict[str, Any], linux: dict[str, Any], table: dict[str, Any]) -> str:
    prefixes = list(table["sqlite"]["platform_options"])
    a = _platform_free(windows["sqlite"]["compile_options"], prefixes)
    b = _platform_free(linux["sqlite"]["compile_options"], prefixes)
    only_windows = sorted(set(a) - set(b))
    only_linux = sorted(set(b) - set(a))
    require(not only_windows and not only_linux,
            f"SQLite compile options differ: only Windows {only_windows}, only Linux {only_linux}")
    keys = set(table["postgres"]) | set(C.PG_SETTINGS) | {"datcollate", "datctype", "datlocprovider", "icu_collversion"}
    differ = sorted(key for key in keys if windows["postgres"].get(key) != linux["postgres"].get(key))
    require(not differ, f"PostgreSQL reference settings differ between platforms: {differ}")
    return f"SQLite compile options equal apart from {prefixes}; PG settings equal"


def code_equal(commit: str, what: str) -> None:
    """``commit`` holds the same code as this work tree (docs, evidence and CLAUDE.md aside)."""
    require(isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit or "") is not None,
            f"{what}: bad commit {commit!r}")
    proc = subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=REPO, capture_output=True, timeout=60)
    require(proc.returncode == 0, f"{what}: commit {commit[:12]} is not in this repository")
    excludes = [f":(exclude){path.rstrip('/')}" for path in C.NOT_CODE]
    names = git("diff", "--name-only", commit, "--", ".", *excludes).split()
    require(not names, f"{what}: code differs from {commit[:12]}: {names[:8]}")
    untracked = [path for path in git("ls-files", "--others", "--exclude-standard").split("\n") if path.strip()]
    stray = [path for path in untracked if not any(path.startswith(prefix) or path == prefix for prefix in C.NOT_CODE)]
    require(not stray, f"{what}: untracked files outside the docs and evidence: {stray[:8]}")


def gate_names() -> list[str]:
    return sorted(path.stem for path in GATES_DIR.iterdir() if GATE_RE.match(path.name))


def check_env() -> str:
    table = spec()
    live = probe(table)
    detail = check_probe(live, table, linux=LINUX, where="server" if LINUX else "windows")
    if LINUX:
        return detail
    recorded = load_json(EVIDENCE / "linux_env.json", "server probe")
    require(str(recorded.get("platform", "")).startswith("linux"), f"server probe platform {recorded.get('platform')!r}")
    detail_linux = check_probe(recorded, table, linux=True, where="server (recorded)")
    cross = check_cross(live, recorded, table)
    return f"{detail}; {detail_linux}; {cross}"


def check_linux() -> str:
    runs = load_json(EVIDENCE / "linux_runs.json", "server runs")
    probe_record = load_json(EVIDENCE / "linux_env.json", "server probe")
    commit = runs.get("commit")
    code_equal(commit, "server runs")
    require((probe_record.get("git") or {}).get("commit") == commit, "server probe and runs are from different commits")
    pytest = runs.get("pytest") or {}
    require(pytest.get("exit") == 0, f"server pytest exit {pytest.get('exit')!r}: {pytest.get('summary')!r}")
    require(pytest.get("failed") == 0 and pytest.get("errors") == 0, f"server pytest: {pytest.get('summary')!r}")
    require(isinstance(pytest.get("passed"), int) and pytest["passed"] > 0, f"server pytest: {pytest.get('summary')!r}")
    require(isinstance(pytest.get("skipped"), int) and pytest["skipped"] <= C.SKIP_MAX,
            f"server pytest skipped {pytest.get('skipped')!r} > {C.SKIP_MAX}")
    gates = runs.get("gates") or {}
    names = gate_names()
    results = gates.get("results") or {}
    require(gates.get("exit") == 0, f"server gates.all exit {gates.get('exit')!r}: {gates.get('summary')!r}")
    require(sorted(results) == names, f"server gates ran {sorted(results)}, this tree has {names}")
    failing = sorted(name for name, result in results.items() if result != "PASS")
    require(not failing, f"server gates failing: {failing}")
    expected = f"GATES: PASS ({len(names)}/{len(names)} passed)"
    require(gates.get("summary") == expected, f"server gates summary {gates.get('summary')!r} != {expected!r}")
    return (f"server at {runs.get('tag') or commit[:12]} (same code as this tree): pytest {pytest.get('summary')}; "
            f"{expected}")


def check_smoke() -> str:
    from surprise.experiments.grid import load_config

    from . import s11_cases

    root = EVIDENCE / "smoke"
    table = spec()
    grid = load_json(root / "grid.json", "smoke grid.json")
    expected = load_config(REPO / C.SMOKE_CONFIG)
    require(grid == expected, "smoke grid.json is not the config in SERVER.md 5.6")
    status = (root / "status.txt").read_text(encoding="utf-8").replace("\r\n", "\n").split("\n") \
        if (root / "status.txt").is_file() else []
    want = [f"{cell} done" for cell in C.SMOKE_CELLS] + [f"done {len(C.SMOKE_CELLS)}/{len(C.SMOKE_CELLS)}"]
    require([line for line in status if line] == want, f"smoke status {status!r} != {want!r}")
    frozen = load_json(REPO / C.FROZEN_MANIFEST, "frozen manifest")["harness"]["hash"]
    pg_version = table["postgres"]["server_version_num"]
    pg_text = f"{int(pg_version) // 10000}.{int(pg_version) % 10000}"
    for cell in C.SMOKE_CELLS:
        base = root / "cells" / cell
        info = load_json(base / "cell.json", f"{cell} cell.json")
        require(info.get("status") == "done" and info.get("returncode") == 0, f"{cell}: {info.get('status')} {info.get('returncode')}")
        wall = info.get("wall_s")
        require(isinstance(wall, (int, float)) and C.SMOKE_MIN_WALL_S <= wall <= C.SMOKE_MAX_WALL_S,
                f"{cell}: wall_s {wall!r} outside [{C.SMOKE_MIN_WALL_S}, {C.SMOKE_MAX_WALL_S}]")
        manifest = load_json(base / "manifest.json", f"{cell} manifest")
        environment = manifest.get("environment") or {}
        require(str(environment.get("platform", "")).startswith("linux"), f"{cell}: platform {environment.get('platform')!r}")
        require(environment.get("python") == table["python"], f"{cell}: python {environment.get('python')!r}")
        engines = environment.get("engines") or {}
        want_engines = {"duckdb": table["venvs"][".venv"]["duckdb"], "datafusion": table["venvs"][".venv"]["datafusion"],
                        "sqlite": table["sqlite"]["version"]}
        require(engines == want_engines, f"{cell}: engines {engines} != {want_engines}")
        old = environment.get("old_engines") or {}
        want_old = {"duckdb": table["venvs"][".venvs/duckdb-1.1.3"]["duckdb"],
                    "datafusion": table["venvs"][".venvs/datafusion-50.0.0"]["datafusion"]}
        require(old == want_old, f"{cell}: old engines {old} != {want_old}")
        require((environment.get("references") or {}).get("postgres") == pg_text,
                f"{cell}: PostgreSQL reference {environment.get('references')}")
        require((manifest.get("harness") or {}).get("hash") == frozen, f"{cell}: harness hash is not the frozen one")
        code_equal(manifest.get("git_commit"), f"{cell} manifest")
        run_report = load_json(base / "report.json", f"{cell} report.json")
        require(isinstance(run_report.get("experiments"), int) and run_report["experiments"] > 0,
                f"{cell}: experiments {run_report.get('experiments')!r}")
    report = load_json(root / "report.json", "smoke grid report")
    missing = [key for key in s11_cases.REPORT_KEYS if key not in report]
    require(not missing, f"smoke report misses {missing}")
    arms = sorted(arm["name"] for arm in expected["arms"])
    require(sorted(report["arms"]) == arms and report["reference"] == expected["reference"],
            f"smoke report arms {sorted(report['arms'])}, reference {report.get('reference')!r}")
    return (f"{len(C.SMOKE_CELLS)} cell(s) done on Linux with the frozen harness and pinned engines, "
            f"same code as this tree; report has {len(s11_cases.REPORT_KEYS)} sections")


def check_docs() -> str:
    from surprise.experiments.grid import load_config

    text = read(C.SERVER)
    position = -1
    for heading in C.SECTIONS:
        found = re.search(rf"^{re.escape(heading)}", text[position + 1:], re.M)
        require(found is not None, f"SERVER.md: heading {heading!r} missing or out of order")
        position += 1 + found.start()
    table = spec()
    runbook = text.split("## 5. 运行手册（用户）", 1)[1].split("## 6.", 1)[0]
    used = re.findall(r"\$PY -m ([A-Za-z0-9_.]+)(?: ([a-z]+))?", runbook)
    require(used, "runbook has no $PY -m commands")
    seen = set()
    for module, sub in used:
        require(module in C.RUNBOOK_COMMANDS, f"runbook uses unknown module {module}")
        require(importlib.util.find_spec(module) is not None, f"runbook module {module} does not exist")
        subs = C.RUNBOOK_COMMANDS[module]
        if subs:
            require(sub in subs, f"runbook: {module} {sub!r} is not one of {subs}")
        seen.add((module, sub if subs else ""))
    for module, subs in C.RUNBOOK_COMMANDS.items():
        for sub in subs or ("",):
            require((module, sub) in seen, f"runbook never uses {module} {sub}".rstrip())
            argv = [sys.executable, "-m", module, *([sub] if sub else []), "--help"]
            proc = subprocess.run(argv, cwd=FRAMEWORK, capture_output=True, text=True, timeout=300)
            require(proc.returncode == 0, f"{' '.join(argv[2:])}: exit {proc.returncode}")
    smoke_path = C.SMOKE_CONFIG.split("framework/", 1)[1]
    require(smoke_path in runbook, f"runbook does not run {smoke_path}")
    config = load_config(REPO / C.SMOKE_CONFIG)
    require(all(arm["network"] is False for arm in config["arms"]), "smoke grid has an arm that needs the network")
    require(config["budget"] == {"minutes": 1.0} and len(config["seeds"]) == 1 and config["repeats"] == 1,
            f"smoke grid is not one seed of one minute: {config['budget']} {config['seeds']}")
    require(any(arm["kind"] == "surprise" and arm["llm"] is None for arm in config["arms"]),
            "smoke grid has no surprise arm without LLM")
    handoff = read(C.HANDOFF)
    require(re.search(r"^\| S14 \|", handoff, re.M) is not None, "HANDOFF.md has no S14 status row")
    return (f"SERVER.md: {len(C.SECTIONS)} headings in order, spec with {len(table['venvs'])} venvs; "
            f"{len(used)} runbook commands exist; smoke config loads offline; HANDOFF has S14")


def check_scope() -> str:
    tags = git("tag", "--list", C.DONE_TAG).split()
    if C.DONE_TAG in tags:
        changed = git("diff", "--name-only", C.BASE_TAG, C.DONE_TAG).split("\n")
        frozen = git("diff", "--name-only", C.BASE_TAG, C.DONE_TAG, "--", *C.FROZEN_PATHS).split("\n")
        where = f"{C.BASE_TAG}..{C.DONE_TAG}"
    else:
        changed = git("diff", "--name-only", C.BASE_TAG).split("\n")
        changed += git("ls-files", "--others", "--exclude-standard").split("\n")
        frozen = git("diff", "--name-only", C.BASE_TAG, "--", *C.FROZEN_PATHS).split("\n")
        where = f"{C.BASE_TAG}..work tree"
    changed = sorted({path.strip() for path in changed if path.strip()})
    frozen = sorted({path.strip() for path in frozen if path.strip()})
    require(not frozen, f"frozen paths changed ({where}): {frozen[:10]}")
    outside = [path for path in changed
               if not any(path == allowed or (allowed.endswith("/") and path.startswith(allowed))
                          for allowed in C.ALLOWED_CHANGES)]
    require(not outside, f"changes outside the S14 scope ({where}): {outside[:10]}")
    require(C.SERVER in changed, f"{C.SERVER} is not among the changes ({where})")
    return f"{len(changed)} paths changed ({where}), all in scope; harness and frozen manifest untouched"


GROUPS = {
    "env": check_env,
    "linux": check_linux,
    "smoke": check_smoke,
    "docs": check_docs,
    "scope": check_scope,
}
WINDOWS_ONLY = ("linux", "smoke")


# ---- record and ingest --------------------------------------------------------------------------

_COUNT_RE = re.compile(r"(\d+) (passed|failed|skipped|errors?|xfailed|xpassed|deselected)")


def _pytest_counts(summary: str) -> dict[str, int]:
    counts = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    for number, word in _COUNT_RE.findall(summary):
        key = "errors" if word.startswith("error") else word
        counts[key] = counts.get(key, 0) + int(number)
    return counts


def record(out_dir: str) -> int:
    """On the server: probe, run pytest and gates.all, and write the evidence files to ``out_dir``."""
    require(LINUX, "--record runs on the server")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    table = spec()
    found = probe(table)
    write_json(out / "linux_env.json", found)
    try:
        env_detail = check_probe(found, table, linux=True, where="server")
        env_ok = True
    except GateFailure as exc:
        env_detail, env_ok = f"FAIL: {_ascii(exc)}", False
    print(f"[{'PASS' if env_ok else 'FAIL'}] env: {env_detail}", flush=True)
    env = {key: value for key, value in os.environ.items() if key.upper() != "DEEPSEEK_API_KEY"}
    started = time.monotonic()
    pytest = subprocess.run([sys.executable, *C.PYTEST_ARGS], cwd=FRAMEWORK, env=env, capture_output=True,
                            text=True, timeout=4 * 3600)
    pytest_s = time.monotonic() - started
    (out / "pytest.log").write_text(_ascii(pytest.stdout + pytest.stderr), encoding="ascii")
    lines = [line for line in pytest.stdout.splitlines() if line.strip()]
    summary = lines[-1].strip("= ").strip() if lines else ""
    counts = _pytest_counts(summary)
    print(f"pytest: exit {pytest.returncode}: {summary}", flush=True)
    started = time.monotonic()
    gates = subprocess.run([sys.executable, "-m", "surprise.gates.all"], cwd=FRAMEWORK, env=env,
                           capture_output=True, text=True, timeout=8 * 3600)
    gates_s = time.monotonic() - started
    (out / "gates.log").write_text(_ascii(gates.stdout + gates.stderr), encoding="ascii")
    results = dict(re.findall(r"^(s\d{2}): (PASS|FAIL \(exit -?\d+\))$", gates.stdout, re.M))
    summary_lines = re.findall(r"^GATES: .*$", gates.stdout, re.M)
    gates_summary = summary_lines[-1] if summary_lines else ""
    print(f"gates.all: exit {gates.returncode}: {gates_summary}", flush=True)
    runs = {
        "schema": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "commit": found["git"]["commit"],
        "tag": found["git"]["tag"],
        "env_ok": env_ok,
        "pytest": {"exit": pytest.returncode, "summary": summary, "seconds": round(pytest_s, 1), **counts,
                   "tail": [_ascii(line) for line in lines[-30:]]},
        "gates": {"exit": gates.returncode, "summary": gates_summary, "results": results,
                  "seconds": round(gates_s, 1)},
    }
    write_json(out / "linux_runs.json", runs)
    ok = env_ok and pytest.returncode == 0 and gates.returncode == 0
    print(f"S14 RECORD: {'PASS' if ok else 'FAIL'} -> {out}")
    return 0 if ok else 1


def ingest_smoke(grid_dir: str) -> int:
    """On Windows: copy what the smoke check reads from the user's grid into ``s14_evidence/smoke``."""
    from surprise.experiments.grid import status_text
    from surprise.harness.ledger import Ledger

    grid = Path(grid_dir)
    require((grid / "grid.json").is_file(), f"{grid}: no grid.json")
    target = EVIDENCE / "smoke"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    shutil.copyfile(grid / "grid.json", target / "grid.json")
    (target / "status.txt").write_text(status_text(grid), encoding="utf-8")
    for cell in C.SMOKE_CELLS:
        source = grid / "cells" / cell
        base = target / "cells" / cell
        base.mkdir(parents=True)
        for name in ("cell.json", "report.json", "config.json"):
            require((source / name).is_file(), f"{cell}: no {name}")
            shutil.copyfile(source / name, base / name)
        log = source.parent / f"{source.name}.log"
        if log.is_file():
            shutil.copyfile(log, base.parent / log.name)
        run_id = json.loads((source / "report.json").read_text(encoding="utf-8"))["run_id"]
        with Ledger(source / "ledger.sqlite") as ledger:
            write_json(base / "manifest.json", ledger.run_manifest(run_id))
    report = grid / "report" / "report.json"
    require(report.is_file(), f"{grid}: no report/report.json (run surprise.metrics.report first)")
    shutil.copyfile(report, target / "report.json")
    console = grid.parent / f"{grid.name}.log"
    if console.is_file():
        shutil.copyfile(console, target / "console.log")
    print(f"ingested {grid} -> {target.relative_to(REPO)}")
    return 0


# ---- main ---------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S14 gate (experiment server, two platforms)")
    parser.add_argument("--only", nargs="+", choices=list(GROUPS), metavar="GROUP",
                        help="run only these groups (the gate proper is all of them)")
    parser.add_argument("--record", metavar="DIR", help="on the server: write the evidence files to DIR")
    parser.add_argument("--ingest-smoke", metavar="GRID", help="on Windows: copy the smoke grid into the evidence")
    args = parser.parse_args(argv)
    try:
        if args.record:
            return record(args.record)
        if args.ingest_smoke:
            return ingest_smoke(args.ingest_smoke)
    except GateFailure as exc:
        print(f"error: {_ascii(exc)}", flush=True)
        return 1
    selected = args.only or list(GROUPS)
    failed = 0
    ran = 0
    for name in selected:
        if LINUX and name in WINDOWS_ONLY:
            print(f"[N/A] {name}: checked on Windows; it reads the records this server produces", flush=True)
            continue
        ran += 1
        started = time.monotonic()
        try:
            detail = GROUPS[name]()
            print(f"[PASS] {name}: {_ascii(detail)} ({time.monotonic() - started:.0f}s)", flush=True)
        except GateFailure as exc:
            failed += 1
            print(f"[FAIL] {name}: {_ascii(exc)}", flush=True)
        except Exception as exc:  # noqa: BLE001 - a crashing check is a failed check
            failed += 1
            print(f"[FAIL] {name}: {type(exc).__name__}: {_ascii(exc)}", flush=True)
    scope = "" if not args.only else f" [only: {', '.join(selected)}]"
    where = " on the server" if LINUX else ""
    print(f"S14 GATE{scope}{where}: {'PASS' if not failed else 'FAIL'}"
          f" ({ran - failed}/{ran} groups passed)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
