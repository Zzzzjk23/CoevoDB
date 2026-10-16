"""S12 gate: Phase 7 close-out (the old main loop moves, the prototypes are archived).

Usage (from ``framework/``)::

    python -m surprise.gates.s12                     # everything
    python -m surprise.gates.s12 --only layout moves

Exit code 0 = pass. Groups, following the S12 section of SESSIONS.md and the user's choice of
plan A for the shared primitives (DECISIONS, "S12 准备"):

``layout``     the old main loop's own files live under ``surprise/baselines/coevodb_v1/``,
               ``coevo/`` and ``repair_bench/`` under ``archive/``; nothing else is in those two
               trees and nothing is left at the old paths; ``framework/main.py`` only forwards to
               the moved entry point; the shared primitives stay where they were, once;
``moves``      every old-code file of the base (tracked ``.py`` outside ``surprise/``, old tests
               included) equals its base version except for import paths and the declared
               location anchors; files that stay in place change only if they are listed as
               import-edited; the non-Python files of the moved trees are byte-identical;
``imports``    no file imports an old location; every first-party import resolves (or already
               failed at the base); the moved modules import in a fresh interpreter; the edited
               scripts answer --help; the coevo smoke script runs from the archive;
``isolation``  the no-LLM loop imports none of the moved LLM modules under their new names; the
               harness imports neither ``archive`` nor the old loop; nothing in ``surprise/``
               outside the baseline itself imports it;
``old_arm``    the old CoevoDB answers --help at its new location and through ``main.py`` exactly
               as the base did; a short ``no_llm`` run at the new location writes the same
               artifacts as the base code; the ``old_no_llm`` arm runs for a minute and its
               metrics read;
``docs``       the READMEs, ``framework/AGENTS.md`` and the new architecture doc are updated: every
               repository path they name exists, and each says what it must.

"s01 to s11 still pass" is the rest of ``python -m surprise.gates.all``. Tables live in
``s12_cases.py``. Output is ASCII only. No group makes a network call.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Iterable

from . import s12_cases as C
from .s06 import GateFailure, _ascii, require

FRAMEWORK = Path(__file__).resolve().parents[2]
REPO = FRAMEWORK.parent


# ---- helpers ------------------------------------------------------------------------------------

def clean_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k.upper() != "DEEPSEEK_API_KEY"}


def run(argv: list[str], *, cwd: Path, timeout: float = 600.0) -> subprocess.CompletedProcess:
    return subprocess.run([str(a) for a in argv], cwd=cwd, env=clean_env(), timeout=timeout,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          encoding="utf-8", errors="replace")


def tail(text: str, lines: int = 6) -> str:
    return " | ".join(line.strip() for line in text.strip().splitlines()[-lines:])


def git(*args: str, binary: bool = False) -> Any:
    proc = subprocess.run(["git", *args], cwd=REPO, capture_output=True, timeout=300)
    require(proc.returncode == 0, f"git {' '.join(args)}: {proc.stderr.decode('utf-8', 'replace')[-300:]}")
    return proc.stdout if binary else proc.stdout.decode("utf-8", "replace")


def lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


_BASE_FILES: list[str] | None = None


def base_files() -> list[str]:
    """Tracked files of framework/ at the base, relative to framework/."""
    global _BASE_FILES
    if _BASE_FILES is None:
        out = git("ls-tree", "-r", "--name-only", C.BASE, "--", "framework")
        _BASE_FILES = sorted(line[len("framework/"):] for line in out.splitlines() if line.startswith("framework/"))
    return _BASE_FILES


def base_bytes(path: str) -> bytes:
    return lf(git("show", f"{C.BASE}:framework/{path}", binary=True))


def files_now() -> list[str]:
    """Files of framework/ now: tracked or untracked-but-not-ignored, and present on disk."""
    out = git("-C", "framework", "ls-files", "--cached", "--others", "--exclude-standard")
    return sorted({p for p in out.splitlines() if p and (FRAMEWORK / p).is_file()})


def now_bytes(path: str) -> bytes:
    return lf((FRAMEWORK / path).read_bytes())


def module_of(path: str) -> str:
    parts = path[:-3].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def package_of(path: str) -> str:
    module = module_of(path)
    return module if path.endswith("__init__.py") else module.rpartition(".")[0]


def known_modules(paths: Iterable[str]) -> set[str]:
    """Module names of the .py files plus every directory above them (packages or namespaces)."""
    known: set[str] = set()
    for path in paths:
        if not path.endswith(".py"):
            continue
        module = module_of(path)
        if module:
            known.add(module)
        parts = path.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            known.add(".".join(parts[:i]))
    return known


def resolve_relative(module: str | None, level: int, package: str) -> str:
    if not level:
        return module or ""
    base = package.split(".") if package else []
    if level > 1:
        base = base[: len(base) - (level - 1)]
    prefix = ".".join(base)
    if module:
        return f"{prefix}.{module}" if prefix else module
    return prefix


def _prefix_map(name: str, table: dict[str, str]) -> str:
    best = ""
    for old in table:
        if (name == old or name.startswith(old + ".")) and len(old) > len(best):
            best = old
    return table[best] + name[len(best):] if best else name


def to_old(name: str) -> str:
    return _prefix_map(name, {new: old for old, new in C.MODULE_MOVES.items()})


def names_old_location(name: str) -> bool:
    """True when ``name`` is a moved old module or lives under a moved old package."""
    return any(name == old or name.startswith(old + ".") for old in C.MODULE_MOVES)


def imports_in(source: str, package: str) -> list[tuple[int, str, list[str]]]:
    """(line, absolute module, imported names) of every import in ``source``."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((node.lineno, alias.name, []))
        elif isinstance(node, ast.ImportFrom):
            module = resolve_relative(node.module, node.level, package)
            found.append((node.lineno, module, [a.name for a in node.names]))
    return found


def canonical(source: str, package: str, *, current: bool) -> str:
    """The AST of ``source`` with every import replaced by its absolute, pre-move form."""
    mapper = to_old if current else (lambda name: name)

    class Canon(ast.NodeTransformer):
        def visit_Import(self, node: ast.Import) -> ast.AST:
            items = [[mapper(a.name), a.asname] for a in node.names]
            return ast.Expr(ast.Constant("IMPORT " + json.dumps(items)))

        def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.AST:
            module = mapper(resolve_relative(node.module, node.level, package))
            items = [[a.name, a.asname] for a in node.names]
            return ast.Expr(ast.Constant("FROM " + json.dumps([module, items])))

    return ast.dump(Canon().visit(ast.parse(source)))


def docstring_only(path: Path) -> bool:
    body = ast.parse(path.read_text(encoding="utf-8")).body
    return (len(body) == 1 and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str) and body[0].value.value.strip() != "")


def old_code() -> list[str]:
    """Old-code .py files of the base: everything outside surprise/ except the surprise tests."""
    return [p for p in base_files() if p.endswith(".py") and not p.startswith("surprise/")
            and not re.match(r"tests/test_surprise_", p)]


def tmpdir(tag: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=f"s12-{tag}-"))


def export_base(target: Path) -> Path:
    """Write the base's old-loop files under ``target``; returns the exported framework/."""
    blob = git("archive", "--format=tar", C.BASE, "--", *C.BASE_EXPORT, binary=True)
    with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
        tar.extractall(target, filter="data")
    return target / "framework"


# ---- layout -------------------------------------------------------------------------------------

def check_layout() -> str:
    now = set(files_now())
    for old, new in C.MOVES.items():
        require(new in now, f"{new} (moved from {old}) is missing")
        if old != C.FORWARDER:
            require(not (FRAMEWORK / old).exists(), f"{old} is still at its old path")
    for folder in ("coevo", "repair_bench", "guidelines", "coverage"):
        left = sorted(p for p in now if p.startswith(folder + "/"))
        on_disk = sorted(str(p.relative_to(FRAMEWORK).as_posix()) for p in (FRAMEWORK / folder).rglob("*.py")) \
            if (FRAMEWORK / folder).exists() else []
        require(not left and not on_disk, f"{folder}/ still holds files: {(left + on_disk)[:5]}")
    for old in ("evolution", "agents"):
        stray = sorted(p for p in now if p.startswith(old + "/") and p not in C.SHARED_FILES)
        require(not stray, f"{old}/ holds more than its shared primitives: {stray}")
    v1 = {p for p in now if p.startswith(C.V1 + "/")}
    require(v1 == set(C.V1_FILES), f"{C.V1}/ must hold exactly the moved files and the new __init__.py files; "
                                   f"extra {sorted(v1 - C.V1_FILES)}, missing {sorted(C.V1_FILES - v1)}")
    arch = {p for p in now if p.startswith("archive/")}
    require(arch == set(C.ARCHIVE_FILES), f"archive/ must hold exactly the archived files, __init__.py and README.md; "
                                          f"extra {sorted(arch - C.ARCHIVE_FILES)}, missing {sorted(C.ARCHIVE_FILES - arch)}")
    for path in C.NEW_INITS:
        require(path not in base_files(), f"{path} already existed at the base")
        require(docstring_only(FRAMEWORK / path), f"{path} must hold a docstring and nothing else")
    readme = (FRAMEWORK / "archive" / "README.md").read_text(encoding="utf-8")
    require("coevo" in readme and "repair_bench" in readme, "archive/README.md says what is archived")

    # framework/main.py forwards and does nothing else.
    tree = ast.parse((FRAMEWORK / C.FORWARDER).read_text(encoding="utf-8"))
    body = list(tree.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant):
        body = body[1:]
    shape = [type(node).__name__ for node in body]
    require(shape == ["Import", "If"], f"main.py: expected a docstring, `import runpy` and one `if __name__` block; got {shape}")
    require([a.name for a in body[0].names] == ["runpy"] and body[0].names[0].asname is None, "main.py imports runpy only")
    guard = body[1]
    require(ast.unparse(guard.test) in ("__name__ == '__main__'", '__name__ == "__main__"') and not guard.orelse,
            "main.py: the forwarder runs under `if __name__ == \"__main__\":` with no else")
    require(len(guard.body) == 1 and isinstance(guard.body[0], ast.Expr) and isinstance(guard.body[0].value, ast.Call),
            "main.py: the guard holds one call")
    call = guard.body[0].value
    require(ast.unparse(call.func) == "runpy.run_module", "main.py calls runpy.run_module")
    require(len(call.args) == 1 and isinstance(call.args[0], ast.Constant) and call.args[0].value == C.FORWARD_TARGET,
            f"main.py forwards to {C.FORWARD_TARGET}")
    keywords = {k.arg: getattr(k.value, "value", None) for k in call.keywords}
    require(keywords == {"run_name": "__main__", "alter_sys": True},
            f"main.py: run_module(..., run_name='__main__', alter_sys=True); got {keywords}")

    # Shared primitives: at their old paths, once.
    for path in C.SHARED_FILES:
        require(path in now, f"shared primitive {path} is missing")
    for folder in C.SHARED_DIRS:
        require(any(p.startswith(folder + "/") for p in now), f"shared directory {folder}/ is missing")
    digests: dict[str, list[str]] = {}
    for path in now:
        if path.endswith(".py"):
            data = now_bytes(path)
            if len(data.strip()) >= 80:
                digests.setdefault(hashlib.sha256(data).hexdigest(), []).append(path)
    shared = [p for p in now if p.endswith(".py") and (p in C.SHARED_FILES or p.split("/")[0] in C.SHARED_DIRS)]
    copies = sorted({tuple(paths) for paths in digests.values() if len(paths) > 1 and any(p in shared for p in paths)})
    require(not copies, f"shared primitives exist more than once: {copies[:3]}")
    names = {Path(p).name for p in C.SHARED_FILES if not p.endswith("__init__.py")}
    clashes = sorted(p for p in now if (p.startswith(C.V1 + "/") or p.startswith("archive/"))
                     and (Path(p).name in names or p.split("/")[-2] in C.SHARED_DIRS))
    require(not clashes, f"copies of shared primitives under the moved trees: {clashes}")

    ignore = (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    require("framework/archive/repair_bench/runs/" in ignore and "framework/repair_bench/runs/" not in ignore,
            ".gitignore ignores framework/archive/repair_bench/runs/ instead of framework/repair_bench/runs/")
    moved = sum(1 for old in C.MOVES if old != C.FORWARDER) + 1
    return (f"{moved} files moved ({len(C.V1_FILES) - 3} into coevodb_v1, {len(C.ARCHIVE_FILES) - 2} into archive), "
            f"main.py forwards to {C.FORWARD_TARGET}; {len(C.SHARED_FILES)} shared files and "
            f"{len(C.SHARED_DIRS)} shared directories in place, no copies")


# ---- moves --------------------------------------------------------------------------------------

def check_moves() -> str:
    anchors: dict[str, list[tuple[str, str]]] = {}
    for path, before, after in C.ANCHORS:
        anchors.setdefault(path, []).append((before, after))
    problems: list[str] = []
    unchanged = moved = edited = 0
    for old in old_code():
        new = C.MOVES.get(old, old)
        if not (FRAMEWORK / new).is_file():
            problems.append(f"{old}: gone (expected at {new})")
            continue
        before = base_bytes(old).decode("utf-8")
        after = now_bytes(new).decode("utf-8")
        for text_before, text_after in anchors.get(new, ()):
            if before.count(text_before) != 1 or after.count(text_after) != 1:
                problems.append(f"{new}: location anchor `{text_after.strip()}` expected once")
                continue
            before = before.replace(text_before, text_after)
        if new == old and before == after:
            unchanged += 1
            continue
        if new == old and old not in C.IMPORT_EDITED:
            problems.append(f"{old}: changed but stays in place and is not listed as import-edited")
            continue
        try:
            same = canonical(before, package_of(old), current=False) == canonical(after, package_of(new), current=True)
        except SyntaxError as exc:
            problems.append(f"{new}: does not parse: {exc}")
            continue
        if not same:
            problems.append(f"{new}: differs from {C.BASE}:{old} beyond import paths")
        elif new == old:
            edited += 1
        else:
            moved += 1
    for old, new in C.MOVES.items():
        if old.endswith(".py"):
            continue
        if not (FRAMEWORK / new).is_file() or now_bytes(new) != base_bytes(old):
            problems.append(f"{new}: not byte-identical to {C.BASE}:{old}")
        else:
            moved += 1
    require(not problems, f"{len(problems)} old-code files changed beyond their imports: {problems[:6]}")
    return (f"{len(old_code())} old .py files of {C.BASE} checked: {moved} moved files (incl. non-Python) equal "
            f"modulo import paths and {len(C.ANCHORS)} anchors, {edited} import-edited in place, {unchanged} untouched")


# ---- imports ------------------------------------------------------------------------------------

def check_imports() -> str:
    now = files_now()
    base = base_files()
    known_now = known_modules(now)
    known_base = known_modules(base)
    first_party = {m.split(".")[0] for m in known_now | known_base}
    inverse_files = {new: old for old, new in C.MOVES.items()}

    def unresolved(path: str, source: str, known: set[str]) -> set[str]:
        out = set()
        for _, module, _names in imports_in(source, package_of(path)):
            if module and module.split(".")[0] in first_party and module not in known:
                out.add(module)
        return out

    base_unresolved: dict[str, set[str]] = {}
    for path in base:
        if path.endswith(".py"):
            try:
                base_unresolved[path] = unresolved(path, base_bytes(path).decode("utf-8"), known_base)
            except SyntaxError:
                base_unresolved[path] = set()
    stale: list[str] = []
    dangling: list[str] = []
    scanned = 0
    for path in now:
        if not path.endswith(".py"):
            continue
        source = now_bytes(path).decode("utf-8")
        try:
            found = imports_in(source, package_of(path))
        except SyntaxError as exc:
            dangling.append(f"{path}: does not parse ({exc})")
            continue
        scanned += 1
        for line, module, _names in found:
            if module and names_old_location(module) and module.split(".")[0] in first_party:
                stale.append(f"{path}:{line} imports {module}")
        was = base_unresolved.get(inverse_files.get(path, path), set())
        for module in sorted(unresolved(path, source, known_now)):
            if to_old(module) not in was and module not in was:
                dangling.append(f"{path} imports {module}")
    require(not stale, f"{len(stale)} imports of old locations: {stale[:6]}")
    require(not dangling, f"{len(dangling)} first-party imports do not resolve: {dangling[:6]}")

    targets = sorted({module_of(new) for new in C.MOVES.values() if new.endswith(".py")} |
                     {"evolution", "evolution.dce", "agents", "agents.bug_fixer", "llm", "llm.ledger"})
    probe = ("import importlib, json\nbad = []\n"
             f"for name in {targets!r}:\n"
             "    try:\n        importlib.import_module(name)\n"
             "    except Exception as exc:\n        bad.append(f'{name}: {type(exc).__name__}: {exc}')\n"
             "print('IMPORTS=' + json.dumps(bad))\n")
    proc = run([sys.executable, "-c", probe], cwd=FRAMEWORK, timeout=300)
    match = re.search(r"^IMPORTS=(.*)$", proc.stdout, re.M)
    require(proc.returncode == 0 and match, f"import probe failed: {tail(proc.stderr)}")
    bad = json.loads(match.group(1))
    require(not bad, f"moved modules do not import: {bad[:4]}")

    for script in C.HELP_SCRIPTS:
        proc = run([sys.executable, script, "--help"], cwd=FRAMEWORK, timeout=300)
        require(proc.returncode == 0 and "usage" in proc.stdout.lower(),
                f"{script} --help: exit {proc.returncode}: {tail(proc.stdout + proc.stderr)}")
    proc = run([sys.executable, "test_simple.py"], cwd=FRAMEWORK, timeout=600)
    require(proc.returncode == 0 and "executed=" in proc.stdout,
            f"test_simple.py (coevo smoke from archive/): exit {proc.returncode}: {tail(proc.stdout + proc.stderr)}")
    return (f"{scanned} files scanned: no import of an old location, every first-party import resolves; "
            f"{len(targets)} moved or shared modules import; {len(C.HELP_SCRIPTS)} scripts answer --help; "
            f"coevo smoke: {proc.stdout.strip().splitlines()[-1]}")


# ---- isolation ----------------------------------------------------------------------------------

def _loaded_after(imports: str, names: tuple[str, ...]) -> list[str]:
    probe = (f"import sys, json\n{imports}\n"
             f"names = {list(names)!r}\n"
             "bad = sorted(m for m in sys.modules if any(m == n or m.startswith(n + '.') for n in names))\n"
             "print('LOADED=' + json.dumps(bad))\n")
    proc = run([sys.executable, "-c", probe], cwd=FRAMEWORK, timeout=300)
    match = re.search(r"^LOADED=(.*)$", proc.stdout, re.M)
    require(proc.returncode == 0 and match, f"probe failed: {tail(proc.stderr)}")
    return json.loads(match.group(1))


def check_isolation() -> str:
    loop = _loaded_after("import " + ", ".join(C.S8_IMPORTS), C.LLM_MODULES_NEW)
    require(not loop, f"the no-LLM loop imports the old loop under its new name: {loop}")
    harness = ("import pkgutil, importlib, surprise.harness\n"
               "for info in pkgutil.walk_packages(surprise.harness.__path__, 'surprise.harness.'):\n"
               "    importlib.import_module(info.name)\n")
    labelled = _loaded_after(harness, C.HARNESS_FORBIDDEN_NEW)
    require(not labelled, f"the harness imports the archive or the old loop: {labelled}")
    users = []
    for path in files_now():
        if not path.endswith(".py") or not path.startswith("surprise/") or path.startswith(C.V1 + "/") \
                or path.startswith("surprise/gates/"):
            continue
        for line, module, _ in imports_in(now_bytes(path).decode("utf-8"), package_of(path)):
            if module == "surprise.baselines.coevodb_v1" or module.startswith("surprise.baselines.coevodb_v1."):
                users.append(f"{path}:{line}")
    require(not users, f"surprise/ imports the old loop: {users}")
    return (f"no-LLM loop loads none of {len(C.LLM_MODULES_NEW)} moved LLM modules; every harness module "
            f"imported without {list(C.HARNESS_FORBIDDEN_NEW)}; nothing in surprise/ imports coevodb_v1")


# ---- old arm ------------------------------------------------------------------------------------

def _run_dir(results: Path) -> Path:
    runs = [p for p in results.iterdir() if p.is_dir()] if results.is_dir() else []
    require(len(runs) == 1, f"expected one run directory under {results}, found {[p.name for p in runs]}")
    return runs[0]


_VOLATILE = re.compile(r"(time|elapsed|_s$|_ms$|stamp|date|duration|wall|started|finished|ended|pid|dir|path)", re.I)


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("<volatile>" if _VOLATILE.search(k) else _scrub(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


def _artifacts(run_dir: Path) -> dict[str, Any]:
    """The run's files, parsed where they are JSON, with timing and location fields blanked."""
    out: dict[str, Any] = {}
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(run_dir).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace").replace(str(run_dir), "<run>")
        if path.suffix == ".json":
            out[rel] = _scrub(json.loads(text))
        elif path.suffix == ".jsonl":
            out[rel] = [_scrub(json.loads(line)) for line in text.splitlines() if line.strip()]
        elif path.suffix in (".log", ".txt"):
            out[rel] = "<log>"
        else:
            out[rel] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return out


def check_old_arm() -> str:
    from surprise.baselines import old_no_llm

    work = tmpdir("oldarm")
    try:
        base_fw = export_base(work / "base")
        helps = {
            "base": run([sys.executable, "main.py", "--help"], cwd=base_fw),
            "new": run([sys.executable, "-m", C.FORWARD_TARGET, "--help"], cwd=FRAMEWORK),
            "forwarder": run([sys.executable, "main.py", "--help"], cwd=FRAMEWORK),
        }
        for name, proc in helps.items():
            require(proc.returncode == 0 and "usage:" in proc.stdout, f"--help ({name}): exit {proc.returncode}: {tail(proc.stderr)}")
        require(helps["new"].stdout == helps["base"].stdout, "--help at the new location differs from the base")
        require(helps["forwarder"].stdout == helps["base"].stdout, "main.py --help (forwarder) differs from the base")
        require(all(mode in helps["new"].stdout for mode in old_no_llm.OLD_MODES), "--help lists every old mode")

        runs = {}
        for name, argv, cwd in (
                ("base", [sys.executable, "main.py"], base_fw),
                ("new", [sys.executable, "-m", C.FORWARD_TARGET], FRAMEWORK)):
            results = work / f"results-{name}"
            started = time.monotonic()
            proc = run([*argv, *C.OLD_RUN_ARGS, "--results-root", results], cwd=cwd, timeout=1800)
            require(proc.returncode == 0, f"old loop ({name}) exit {proc.returncode}: {tail(proc.stderr)}")
            runs[name] = (_run_dir(results), time.monotonic() - started)
        base_art, new_art = _artifacts(runs["base"][0]), _artifacts(runs["new"][0])
        require(sorted(base_art) == sorted(new_art), f"run files differ: base {sorted(base_art)}, new {sorted(new_art)}")
        differ = [name for name in base_art if base_art[name] != new_art[name]]
        require(not differ, f"the run at the new location differs from the base in {differ}")
        require(base_art, "the old loop wrote no artifacts")

        arm = work / "arm"
        started = time.monotonic()
        proc = run([sys.executable, "-m", "surprise.baselines.old_no_llm", "--out", arm,
                    "--minutes", str(C.OLD_ARM_MINUTES), "--seed", "0"], cwd=FRAMEWORK,
                   timeout=60 * C.OLD_ARM_MINUTES + 600)
        took = time.monotonic() - started
        require(proc.returncode == 0, f"old_no_llm exit {proc.returncode}: {tail(proc.stdout + proc.stderr)}")
        meta = json.loads((arm / "old_run.json").read_text(encoding="utf-8"))
        arm_dir = _run_dir(arm / "results")
        require(any(arm_dir.iterdir()), "the old arm wrote nothing")
        from surprise.metrics import rq

        metrics = rq.old_metrics(arm)
        require(isinstance(metrics, dict), "old_metrics reads the arm")
        return (f"--help identical at the new location, through main.py and at {C.BASE}; "
                f"{len(base_art)} artifacts of a 2-iteration no_llm run equal to the base "
                f"({runs['base'][1]:.0f}s / {runs['new'][1]:.0f}s); old_no_llm arm {took:.0f}s, "
                f"ended {meta.get('ended')}, metrics keys {sorted(metrics)[:4]}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ---- docs ---------------------------------------------------------------------------------------

_TOKEN = re.compile(r"`([^`\s]+)`|\]\(([^)\s]+)\)")
_PATHLIKE = re.compile(r"^[A-Za-z0-9_.\-/]+$")
_EXTS = (".py", ".md", ".json", ".jsonl", ".yml", ".yaml", ".sql", ".txt", ".toml", ".cfg", ".c", ".tsv")


def doc_paths(text: str) -> list[str]:
    found = []
    for match in _TOKEN.finditer(text):
        token = (match.group(1) or match.group(2) or "").split("#", 1)[0].rstrip(".,;:")
        if not token or "://" in token or not _PATHLIKE.match(token) or token.startswith("-"):
            continue
        if "/" not in token and (not token.endswith(_EXTS) or token.startswith(".")):
            continue
        if re.match(r"^\d", token) or token.count(".") > 3 and "/" not in token:
            continue
        if token.startswith("python") or token in ("/", "./", "../"):
            continue
        found.append(token)
    return found


def check_docs() -> str:
    problems = []
    names = 0
    for doc in C.DOCS:
        path = REPO / doc
        if not path.is_file():
            problems.append(f"{doc}: missing")
            continue
        text = path.read_text(encoding="utf-8")
        if doc in C.DOCS_UPDATED:
            before = git("show", f"{C.BASE}:{doc}", binary=True)
            if lf(before) == lf(path.read_bytes()):
                problems.append(f"{doc}: not updated")
        for needle in C.REQUIRED_MENTIONS.get(doc, ()):
            if needle not in text:
                problems.append(f"{doc}: does not mention {needle!r}")
        for token in doc_paths(text):
            clean = token.lstrip("./") if token.startswith("./") else token
            if any(clean == p or clean.startswith(p.rstrip("/") + "/") for p in C.UNTRACKED_PREFIXES):
                continue
            names += 1
            roots = (path.parent, REPO, FRAMEWORK)
            if not any((root / clean).exists() for root in roots):
                problems.append(f"{doc}: names `{token}`, which does not exist")
    require(not problems, f"{len(problems)} doc problems: {problems[:40]}")
    return f"{len(C.DOCS)} docs updated; {names} repository paths named, all exist; required mentions present"


GROUPS: dict[str, Callable[[], str]] = {
    "layout": check_layout,
    "moves": check_moves,
    "imports": check_imports,
    "isolation": check_isolation,
    "old_arm": check_old_arm,
    "docs": check_docs,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S12 gate (Phase 7 close-out)")
    parser.add_argument("--only", nargs="+", choices=list(GROUPS), metavar="GROUP",
                        help="run only these groups (the gate proper is all of them)")
    args = parser.parse_args(argv)
    selected = args.only or list(GROUPS)
    failed = 0
    for name in selected:
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
    print(f"S12 GATE{scope}: {'PASS' if not failed else 'FAIL'}"
          f" ({len(selected) - failed}/{len(selected)} groups passed)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
