"""Tables for gates/s15.py (experiment infrastructure)."""

from __future__ import annotations

BASE_TAG = "s14-done-r2"
DONE_TAG = "s15-done"
DATA = "framework/surprise/gates/s15_data"

# ---- scope ----------------------------------------------------------------------------------------

ALLOWED_CHANGES = (
    "framework/surprise/experiments/",
    "framework/surprise/metrics/",
    "framework/surprise/roles/",
    "framework/surprise/baselines/",
    "framework/surprise/docs/",
    "framework/surprise/gates/s15.py",
    "framework/surprise/gates/s15_cases.py",
    "framework/surprise/gates/s15_data/",
    # S8 long run re-pinned after experiments/ changed (the S8 acceptance procedure).
    "framework/surprise/gates/s08_runs.json",
    "framework/tests/test_surprise_s15_",
    "framework/tests/data/sqlancer/",
    ".gitignore",
)
# Not touched by S15: the frozen harness and the layers below the experiments.
FROZEN_PATHS = (
    "framework/surprise/harness",
    "framework/surprise/gates/s04_frozen.json",
    "framework/surprise/theory",
    "framework/surprise/hunter",
    "framework/surprise/diagnoser",
    "framework/surprise/features",
    "framework/oracles",
    "framework/targets",
)

# ---- grid config ----------------------------------------------------------------------------------

UNLIMITED = "unlimited"
TIERS = ("fast", "strong")
MODELS = {"fast": "deepseek-flash", "strong": "deepseek-v4-pro"}
# New top-level keys and the value load_config fills in when a key is left out.
TOP_DEFAULTS = {"concurrency": 1, "cpus_per_cell": None, "engine_threads": None, "kill_grace_minutes": 10.0}
# Environment variable the grid sets to engine_threads: DuckDB 1.5.5 reads it on Linux as its default
# thread count (.src/duckdb-v1.5.5/src/main/config.cpp, DBConfig::GetSystemMaxThreads).
THREADS_ENV = "SLURM_CPUS_ON_NODE"
SQLANCER_DEFAULT_RUN = {"oracles": ["NOREC", "WHERE"], "threads": 1}
SQLANCER_MODULE = "surprise.baselines.sqlancer_run"
HARD_KILL_CONSTANT = "HARD_KILL_AFTER_S"

# ---- parallel smoke -------------------------------------------------------------------------------

PARALLEL_ARMS = (
    {"name": "nollm", "kind": "surprise", "engines": ["duckdb"]},
    {"name": "a3", "kind": "surprise", "engines": ["duckdb"], "hunter": "random"},
    {"name": "a4", "kind": "surprise", "engines": ["duckdb"], "freeze": "theory"},
    {"name": "a5", "kind": "surprise", "engines": ["duckdb"], "freeze": "diagnoser"},
)
PARALLEL_SEED = 7
PARALLEL_MINUTES = 1.0
PARALLEL_START_SPREAD_S = 20.0
PARALLEL_WALL_S = (55.0, 400.0)

# ---- stream ---------------------------------------------------------------------------------------

# A long run that no later session re-pins: the S10-code three-hour run kept by S11 (not in git).
STREAM_RUN = "framework/results/s08/longrun-s10code"
# run_metrics(STREAM_RUN) at s14-done-r2, before S15 (json.dumps sort_keys, compact separators).
STREAM_SHA256 = "2a6310744d89e0075ee14f4fac94a961093b9644e65b1ed118adbc87b56c458d"
STREAM_RECORDS = 9500
# Peak resident memory of run_metrics. Before S15: 3.3 GB on the S8 long run (8600 records).
STREAM_PEAK_MB = 800
# Doubling the ledger may add at most this much (24h is about 70k records, about 7x).
STREAM_GROWTH_MB = 120

# ---- LLM switches ---------------------------------------------------------------------------------

DEFAULT_MAX_CALLS = 200
CAP_ENV = "SURPRISE_LLM_MAX_CALLS"

# ---- SQLancer -------------------------------------------------------------------------------------

SQLANCER_COMMIT = "ab328b756bf5d923b9d93959af3432546efe56fd"
SQLANCER_PATCH = "framework/surprise/docs/sqlancer/log-each-select.patch"
DUCKDB_JDBC = "1.5.5.0"
DATABASE_VERSION = "v1.5.5"
# The log fixtures in s15_data/sqlancer. Three are real logs from SQLancer at the commit above against
# DuckDB 1.1.3 (2026-10-19); norec_mismatch.log is written by the orchestrator in SQLancer's format
# (Main.logException + NoRECOracle) around a NoREC failure that the S8 long run found on DuckDB 1.5.5.
SQLANCER_FIXTURES = {
    "norec_mismatch.log": {"kind": "mismatch", "sqlancer_oracle": "NOREC", "oracle": "norec", "converted": True},
    "unexpected_error_ddl.log": {"kind": "unexpected_error", "converted": False},
    "tool_error_sqlexception.log": {"kind": "tool_error", "converted": False},
    "tool_error_unsupported.log": {"kind": "tool_error", "converted": False},
}
NOREC_CASE = {
    "engine": "duckdb",
    "setup": [
        "CREATE TABLE t1 (id INTEGER, ch CHAR(1))",
        "INSERT INTO t1 VALUES (1, 'A')",
        "INSERT INTO t1 VALUES (2, 'B')",
        "INSERT INTO t1 VALUES (NULL, 'B')",
    ],
    "query": "SELECT * FROM t1 a",
    "predicate": "NOT EXISTS (SELECT 1 FROM t1 b WHERE b.ch = a.ch AND b.id <> a.id)",
}
# label_key of loop-s0:382 in STREAM_RUN (the same case, found by the loop).
NOREC_KEY = "fix|duckdb|deliminator,filter_pushdown"
SQLANCER_LIVE_MINUTES = 10.0
SQLANCER_MIN_EXECUTIONS = 10_000
SQLANCER_MAX_LOG_MB = 50

# ---- prices ---------------------------------------------------------------------------------------

PRICES_FILE = "framework/surprise/metrics/data/prices_deepseek.json"
# https://api-docs.deepseek.com/quick_start/pricing, read 2026-10-19 (USD per 1M tokens).
PRICES = {
    "source": "https://api-docs.deepseek.com/quick_start/pricing",
    "retrieved": "2026-10-19",
    "currency": "USD",
    "unit": "per 1M tokens",
    "peak_hours_utc": "01:00-04:00 and 06:00-10:00, Monday to Friday, excluding Chinese public holidays",
    "models": {
        "deepseek-flash": {
            "version": "DeepSeek-V4.1-Flash-1017",
            "input_cache_hit": {"peak": 0.006, "off_peak": 0.003},
            "input_cache_miss": {"peak": 0.3, "off_peak": 0.15},
            "output": {"peak": 1.2, "off_peak": 0.6},
        },
        "deepseek-v4-pro": {
            "version": "DeepSeek-V4-Pro-0813",
            "input_cache_hit": {"peak": 0.044, "off_peak": 0.022},
            "input_cache_miss": {"peak": 1.32, "off_peak": 0.66},
            "output": {"peak": 3.96, "off_peak": 1.98},
        },
    },
    # What a grid's "prices" takes: peak cache-miss input and peak output, so reported cost is an upper bound.
    "grid": {
        "deepseek-flash": {"input": 0.3, "output": 1.2},
        "deepseek-v4-pro": {"input": 1.32, "output": 3.96},
    },
}

# ---- archive --------------------------------------------------------------------------------------

ARCHIVE_MODULE = "surprise.experiments.archive"
# Kept in a pruned grid directory: the reports and the per-cell summaries.
ARCHIVE_KEEP = ("grid.json", "report", "cell.json", "config.json", "report.json", "error.txt")
ARCHIVE_DROP = ("ledger.sqlite", "theory", "progress.jsonl")

# ---- docs -----------------------------------------------------------------------------------------

SERVER = "framework/surprise/docs/SERVER.md"
HANDOFF = "framework/surprise/docs/HANDOFF.md"
SERVER_HEADINGS = ("### 5.7 并行网格", "### 5.8 归档", "## 8. SQLancer")
