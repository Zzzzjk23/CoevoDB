"""Tables for the S12 gate (Phase 7 close-out).

The user chose plan A for S12 (DECISIONS, "S12 准备", 2026-10-16): old files that the surprise
framework imports, directly or through other old files, are shared primitives. They stay where
they are, once. Only the parts of the old main loop that nothing in ``surprise/`` reaches move
into ``surprise/baselines/coevodb_v1/``; ``coevo/`` and ``repair_bench/`` move into ``archive/``.
Paths are relative to ``framework/`` unless they say otherwise.
"""
from __future__ import annotations

# Everything is compared with the commit the session started from.
BASE = "s11-done-r2"

V1 = "surprise/baselines/coevodb_v1"

# Old path -> new path, one entry per tracked file.
MOVES: dict[str, str] = {
    "main.py": f"{V1}/main.py",
    "evolution/bandit.py": f"{V1}/evolution/bandit.py",
    "evolution/co_evolution.py": f"{V1}/evolution/co_evolution.py",
    "evolution/coverage.py": f"{V1}/evolution/coverage.py",
    "evolution/playbook.py": f"{V1}/evolution/playbook.py",
    "agents/bug_hunter.py": f"{V1}/agents/bug_hunter.py",
    "guidelines/__init__.py": f"{V1}/guidelines/__init__.py",
    "guidelines/llm_guideline.py": f"{V1}/guidelines/llm_guideline.py",
    "coverage/__init__.py": f"{V1}/coverage/__init__.py",
    "coverage/features.py": f"{V1}/coverage/features.py",
    "coverage/store.py": f"{V1}/coverage/store.py",
    **{f"coevo/{name}": f"archive/coevo/{name}" for name in (
        "__init__.py", "archive.py", "controller.py", "executor.py", "generator.py", "models.py",
        "policy.py", "repair.py")},
    **{f"repair_bench/{name}": f"archive/repair_bench/{name}" for name in (
        "run_bench.py", "run_localize.py",
        "cases/sqlite_c/code_excerpt.c", "cases/sqlite_c/reproducers.tsv",
        "cases/sqlite_c/sanity.tsv",
        "src_pristine/shell.c", "src_pristine/sqlite3.c", "src_pristine/sqlite3.h",
        "src_pristine/sqlite3ext.h")},
}

# Old module name (or package prefix) -> new one. Longest match wins.
MODULE_MOVES: dict[str, str] = {
    "main": f"surprise.baselines.coevodb_v1.main",
    "evolution.bandit": "surprise.baselines.coevodb_v1.evolution.bandit",
    "evolution.co_evolution": "surprise.baselines.coevodb_v1.evolution.co_evolution",
    "evolution.coverage": "surprise.baselines.coevodb_v1.evolution.coverage",
    "evolution.playbook": "surprise.baselines.coevodb_v1.evolution.playbook",
    "agents.bug_hunter": "surprise.baselines.coevodb_v1.agents.bug_hunter",
    "guidelines": "surprise.baselines.coevodb_v1.guidelines",
    "coverage": "surprise.baselines.coevodb_v1.coverage",
    "coevo": "archive.coevo",
    "repair_bench": "archive.repair_bench",
}

# Files that did not exist before S12. Each new __init__.py holds a docstring and nothing else.
NEW_INITS = (
    f"{V1}/__init__.py",
    f"{V1}/evolution/__init__.py",
    f"{V1}/agents/__init__.py",
    "archive/__init__.py",
)
NEW_OTHER = ("archive/README.md",)

# The only tracked files allowed under the two new trees.
V1_FILES = frozenset(new for new in MOVES.values() if new.startswith(V1 + "/")) | frozenset(
    p for p in NEW_INITS if p.startswith(V1 + "/"))
ARCHIVE_FILES = frozenset(new for new in MOVES.values() if new.startswith("archive/")) | frozenset(
    p for p in NEW_INITS + NEW_OTHER if p.startswith("archive/"))

# framework/main.py stays as a forwarder so `python main.py ...` (the S01 gate, the old_no_llm arm,
# scripts/gate2.py, scripts/coevo_curve.py, the READMEs) keeps working.
FORWARDER = "main.py"
FORWARD_TARGET = "surprise.baselines.coevodb_v1.main"

# A moved file may also re-anchor a path computed from its own location, so that it still points
# at the same directory as before the move. (new path, text at the base, text now).
ANCHORS: tuple[tuple[str, str, str], ...] = (
    (f"{V1}/main.py",
     "PROJECT_DIR = Path(__file__).resolve().parent\n",
     "PROJECT_DIR = Path(__file__).resolve().parents[3]\n"),
    ("archive/repair_bench/run_bench.py",
     "sys.path.insert(0, str(Path(__file__).resolve().parent.parent))\n",
     "sys.path.insert(0, str(Path(__file__).resolve().parents[2]))\n"),
    ("archive/repair_bench/run_localize.py",
     "sys.path.insert(0, str(Path(__file__).resolve().parent.parent))\n",
     "sys.path.insert(0, str(Path(__file__).resolve().parents[2]))\n"),
)

# Shared primitives: stay at these paths, exactly once (plan A).
SHARED_FILES = (
    "evolution/__init__.py", "evolution/dce.py",
    "agents/__init__.py", "agents/base_agent.py", "agents/bug_fixer.py", "agents/json_utils.py",
    "llm/__init__.py", "llm/ledger.py",
    "scripts/cross_engine.py",
)
SHARED_DIRS = ("oracles", "targets", "diagnosis", "seeds", "util")

# Old files that stay where they are but must import a moved module from its new place.
# Nothing else in them may change.
IMPORT_EDITED = (
    "evolution/__init__.py",
    "campaigns/pg_coldstart.py",
    "scripts/corpus_hunt.py", "scripts/flaky_mine.py", "scripts/llm_rule_gen.py",
    "scripts/make_playbook_seed.py", "scripts/make_playbook_seed_v2.py",
    "testing/test_new_components.py",
    "tests/test_diagnosis_dce.py", "tests/test_verified_loop.py",
    "test_simple.py",
)

# Scripts among them that answer --help without side effects (checked at the base, too).
HELP_SCRIPTS = ("scripts/corpus_hunt.py", "scripts/flaky_mine.py", "scripts/llm_rule_gen.py")

# The no-LLM loop of S8 must not import these. The S8 and S9 gates list the old names; after the
# move those names can no longer appear, so this gate checks the new ones.
LLM_MODULES_NEW = (
    "surprise.baselines.coevodb_v1",
    "surprise.baselines.coevodb_v1.agents.bug_hunter",
    "surprise.baselines.coevodb_v1.evolution.co_evolution",
    "surprise.baselines.coevodb_v1.guidelines",
)
# What the S8 gate imports for its no-LLM check.
S8_IMPORTS = (
    "surprise.hunter", "surprise.metrics", "surprise.baselines", "surprise.diagnoser",
    "surprise.experiments.loop", "surprise.metrics.curve", "surprise.metrics.dups",
    "surprise.metrics.recall", "surprise.baselines.old_no_llm",
)
# The labelling code never imports the prototype (S04 FORBIDDEN_IMPORTS has "coevo") nor the old loop.
HARNESS_FORBIDDEN_NEW = ("archive", "surprise.baselines.coevodb_v1")

# The short run of the old loop compared with the base code.
OLD_RUN_ARGS = ("--engine", "duckdb", "--mode", "no_llm", "--iterations", "2", "--seed", "0",
                "--label", "s12gate")
# Base files exported to run the base code (the old loop's whole import closure).
BASE_EXPORT = ("framework/main.py", "framework/config.yml", "framework/agents", "framework/coevo",
               "framework/coverage", "framework/diagnosis", "framework/evolution",
               "framework/guidelines", "framework/llm", "framework/oracles", "framework/scripts",
               "framework/seeds", "framework/targets", "framework/util")
OLD_ARM_MINUTES = 1

# ---- docs ------------------------------------------------------------------------------------
# Paths relative to the repository root.
DOCS = ("README.md", "framework/README.md", "framework/AGENTS.md", "framework/surprise/ARCHITECTURE.md")
# Must differ from the base (the architecture doc is new).
DOCS_UPDATED = ("README.md", "framework/README.md", "framework/AGENTS.md")
REQUIRED_MENTIONS: dict[str, tuple[str, ...]] = {
    "README.md": ("framework/surprise", "coevodb_v1"),
    "framework/README.md": (
        "surprise.experiments.loop", "surprise.experiments.grid", "surprise.metrics.report",
        "surprise.gates.all", "surprise/baselines/coevodb_v1", "archive/", "ARCHITECTURE.md",
        "pytest -q testing tests"),
    "framework/AGENTS.md": (
        "DEEPSEEK_API_KEY", "surprise/baselines/coevodb_v1", "ARCHITECTURE.md",
        # The PostgreSQL notes stay.
        "COEVO_PG_PREFIX", "autocommit=True", "pg_execdiff"),
    "framework/surprise/ARCHITECTURE.md": (
        *(f"surprise/{sub}/" for sub in ("harness", "features", "theory", "hunter", "diagnoser",
                                         "roles", "metrics", "experiments", "baselines", "gates")),
        "evolution/dce.py", "agents/bug_fixer.py", "agents/base_agent.py", "llm/ledger.py",
        "coevodb_v1", "archive/", "CVE", "HASHED_PATHS"),
}
# Path-like tokens under these first components are run artifacts or machine-local and are
# not tracked; the path check skips them.
UNTRACKED_PREFIXES = ("results", ".venv", ".venvs", ".orch", ".src", ".worktrees", "~", "pgbld", "../pgbld",
                      "repair_bench/runs", "archive/repair_bench/runs",
                      "framework/archive/repair_bench/runs", "framework/results")
