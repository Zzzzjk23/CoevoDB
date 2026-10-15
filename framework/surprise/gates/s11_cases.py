"""Fixed values for the S11 gate (data only; ``gates/all.py`` does not run this file).

The metric constants are pinned the way the S6-S10 gates pin theirs. Hand-computed
expectations sit next to the inputs they belong to.
"""
from __future__ import annotations

# ---- constants ---------------------------------------------------------------------------------

METRICS_CONSTANTS = {
    "HIGH_SURPRISE_BITS": 4.0,
    "CALIBRATION_EDGES": (0.0, 0.05, 0.2, 0.4, 0.6, 0.8, 0.95, 1.0),
    "CIAO_MAX_GENERATIONS": 12,
    "CIAO_BATCH_SAMPLE": 200,
    "CURVE_WINDOW": 100,
    "TEETH_AMPLITUDE": 0.25,
    "TEETH_WIDTH": 5,
}
ROLE_CONSTANTS = {"REQUEST_DEADLINE_S": 600.0}
PURE_LLM_CONSTANTS = {
    "PURE_LLM_TIER": "fast",
    "PURE_LLM_TEMPERATURE": 0.8,
    "PURE_LLM_MAX_TOKENS": 16000,
    "PURE_LLM_CASES_PER_CALL": 4,   # 8 cases left no room in 16000 tokens: 3 of 4 recorded replies were cut (S11)
}
PURE_LLM_MIN_TOPICS = 8

RQ_KEYS = ("rq1", "rq2", "rq3", "rq4", "rq5", "rq6", "cost")

# ---- fixes -------------------------------------------------------------------------------------

STORE_TRANSIENT_FAILURES = 3          # os.replace raises PermissionError this many times, then works
DEADLINE_TEST_S = 1.5                 # deadline given to the transport under test
DEADLINE_SLACK_S = 3.0                # it must give up within deadline + slack
DUMMY_KEY = "sk-s11-gate-not-a-key"   # put in the environment only while the transport is tested

# ---- stats (hand-computed) ---------------------------------------------------------------------

# x, y -> (U of x, method, p). Exact: no ties and len(x) + len(y) <= 20. U(x) counts pairs x > y,
# plus one half per tie. Exact two-sided p = min(1, 2 * min(P(U <= u), P(U >= u))).
MWU_EXACT = [
    ((1, 2, 3), (4, 5, 6), 0.0, "exact", 0.1),
    ((4, 5, 6), (1, 2, 3), 9.0, "exact", 0.1),
    ((1, 4), (2, 3), 2.0, "exact", 1.0),
    ((1, 5, 9), (2, 3, 4, 6), 7.0, "exact", 6 / 7),
]
# Ties force the asymptotic method: normal approximation with tie correction and continuity
# correction (scipy's method="asymptotic", use_continuity=True). The gate computes p itself.
MWU_TIES = [((1, 2, 2, 3), (2, 3, 4, 4, 5)), ((0, 0), (0, 1))]
MWU_LARGE = (tuple(range(0, 22, 2)), tuple(range(1, 23, 2)))     # 11 + 11 > 20, no ties: asymptotic
MWU_SAME = ((2, 2), (2, 2))                                       # every value equal: p 1.0, A12 0.5
A12 = [
    ((1, 2, 3), (1, 2, 3), 0.5),
    ((3, 4), (1, 2), 1.0),
    ((1, 2), (2, 3), 0.125),
]
MEDIAN = [((), None), ((3, 1, 2), 2.0), ((1, 2, 3, 4), 2.5), ((5,), 5.0)]

# ---- rq6 (hand-computed) ---------------------------------------------------------------------

CLASSIFY = [
    ({"a", "b"}, {"a", "b"}, "match"),
    ({"a"}, {"a", "b"}, "too_wide"),
    ({"a", "b", "c"}, {"a", "b"}, "too_narrow"),
    ({"a", "c"}, {"a", "b"}, "mixed"),
]
PARTITION_TRUTH = {"a": 1, "b": 1, "c": 2, "d": 2, "only_truth": 3}
PARTITION_PRED = {"a": "X", "b": "X", "c": "X", "d": "Y", "only_pred": "Z"}
PARTITION_EXPECTED = {"items": 4, "precision": 1 / 3, "recall": 0.5, "f1": 0.4, "ari": 0.0}
PARTITION_NONE_PRED = {"a": None, "b": None, "c": "X", "d": "X"}   # None = a singleton each
PARTITION_NONE_EXPECTED = {"items": 4, "precision": 1.0, "recall": 0.5}

F2_FIX = {
    "name": "F2",
    "engine": "duckdb",
    "key": "fix|duckdb|window_self_join",
    "fix": "https://github.com/duckdb/duckdb/pull/24685",
    "conditions": ("ast:window_spec:partition", "ast:window_trait:dup_partition_key", "ast:window_trait:multiple"),
}

# ---- runs --------------------------------------------------------------------------------------

# The short DuckDB run shared by runmetrics, rq6 and dedup.
SHORT_RUN = {"seed": 51, "experiments": 30, "engines": ("duckdb",), "bootstrap": (("F1", "plan_variant"),)}
# The arms runs (small: three oracles, a dozen choices).
ARMS_RUN = {"seed": 61, "experiments": 12, "engines": ("duckdb",),
            "oracles": ("plan_variant", "tlp", "norec"), "bootstrap": (("F1", "plan_variant"),)}
# The M3 cache (gates/s10_llm/m3) replayed for a shorter run: conjectures and their bets settle early.
LLM_RUN = {"seed": 0, "experiments": 14, "engines": ("datafusion",),
           "oracles": ("cross_dbms", "tlp", "norec", "equivalent_query"),
           "roles": ("implementer", "conjecturer", "prior", "translator", "vocab_inventor", "oracle_inventor"),
           "bootstrap": (("DF-A", "cross_dbms"),)}
# The recorded pure-LLM run (gates/s11_llm/pure_llm), replayed offline.
PURE_RUN = {"seed": 0, "engine": "duckdb", "experiments": 16, "max_calls": 6}
# Rows of progress.jsonl that the replay must reproduce exactly (elapsed_s is dropped).

# ---- coverage ----------------------------------------------------------------------------------

COVERAGE = {"prefix": "duckdb:test/issues/", "limit": 4, "oracles": ("plan_variant", "equivalent_query")}
OLD_FULL_VENV = "duckdb-1.1.3-full"

# ---- sqlancer: the transcribed row of docs/FINAL_REPORT.md (strong baseline) -------------------

SQLANCER = {
    "tool": "SQLancer 2.0.0 @9eb1db82",
    "runs": 35,
    "total_bugs": 0,
    "engines": {
        "duckdb": {"version": "1.5.5", "oracles": 6, "bugs": 0},
        "postgres": {"version": "16.2", "oracles": 5, "bugs": 0},
        "sqlite3": {"version": "3.49.1", "oracles": 5, "bugs": 0},
    },
}

# ---- grid (M4 smoke) ---------------------------------------------------------------------------

GRID_CONFIG = {
    "schema": 1,
    "name": "s11-smoke",
    "budget": {"minutes": 1.0},
    "seeds": [0, 1],
    "repeats": 1,
    "reference": "surprise",
    "window": 10,
    "arms": [
        {"name": "surprise", "kind": "surprise", "engines": ["duckdb"]},
        {"name": "old", "kind": "old_coevodb", "mode": "no_llm"},
    ],
}
GRID_CELLS = ("surprise/s0-r0", "surprise/s1-r0", "old/s0-r0", "old/s1-r0")
FIGURES = ("rq1_families.png", "rq2_surprise.png", "rq2_calibration.png", "rq3_llm.png",
           "rq4_quality.png", "rq5_ciao.png", "rq6_recall.png")
REPORT_KEYS = ("schema", "grid", "reference", "arms", "cells", "rq1", "rq2", "rq3", "rq4", "rq5", "rq6",
               "stats", "external")
RESUME_MAX_S = 60.0
