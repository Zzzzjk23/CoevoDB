"""Fixed cases for the S10 gate (data only; ``gates/all.py`` does not run this file).

Everything here was decided or measured on this machine before dispatch:
DuckDB 1.5.5, DataFusion 54.0.0, SQLite 3.51.0, PostgreSQL 16.15, and the two engine
source checkouts under ``<main checkout>/.src`` (pinned by the S9 gate).
"""
from __future__ import annotations

# ---- role names and switches -----------------------------------------------------------

S9_ROLES = ("implementer", "conjecturer")
NEW_ROLES = ("prior", "translator", "vocab_inventor", "oracle_inventor")
ROLES = S9_ROLES + NEW_ROLES

# Module of each new role; each exposes ``build(ctx) -> Role``.
PLUGINS = {
    "prior": "surprise.roles.prior",
    "translator": "surprise.roles.translator",
    "vocab_inventor": "surprise.roles.vocab_inventor",
    "oracle_inventor": "surprise.roles.oracle_inventor",
}

# Lanes the new roles add to the Hunter's pool (the S9 roles add "bet" and "implement").
TRANSLATE_LANE = "translate"
TRANSLATOR_OP = "translator"

# ---- constants (PLAN decision 8: in roles/constants.py, hence in the run manifest's llm section) ----

# The three long-answer roles take 16000 tokens (raised from 8000 after the M3 recording: deepseek-flash
# counts reasoning tokens against max_tokens, and the translator's and the oracle inventor's replies were
# cut off at 8000 with no JSON, the same lesson S9 learned for the conjecturer). The prior answers in ~3000.
CONSTANTS = {
    "REWRITE_LIBRARY_ENV": "SURPRISE_REWRITE_LIBRARY",
    # exploration prior
    "PRIOR_TIER": "fast",
    "PRIOR_TEMPERATURE": 0.2,
    "PRIOR_MAX_TOKENS": 8000,
    "PRIOR_UNITS_PER_CALL": 16,
    "PRIOR_CALLS_PER_CHOICE": 1,
    "PRIOR_STRENGTH": 100.0,
    "PRIOR_INITIAL_WEIGHT": 0.5,
    "PRIOR_MIN_SETTLED": 20,
    "PRIOR_EVIDENCE_PER_CONSTRUCT": 4,
    # migration translator
    "TRANSLATOR_TIER": "fast",
    "TRANSLATOR_TEMPERATURE": 0.2,
    "TRANSLATOR_MAX_TOKENS": 16000,
    "TRANSLATOR_ATTEMPTS": 2,
    "TRANSLATOR_PER_CHOICE": 1,
    # vocabulary inventor
    "VOCAB_TIER": "fast",
    "VOCAB_TEMPERATURE": 0.4,
    "VOCAB_MAX_TOKENS": 16000,
    "VOCAB_TRIGGER_CONTRADICTIONS": 2,
    "VOCAB_MIN_POSITIVES": 2,
    "VOCAB_HOLDOUT_DIVISOR": 3,
    "VOCAB_ATTEMPTS_PER_FAMILY": 1,
    "VOCAB_MAX_PATTERN_CHARS": 200,
    "VOCAB_MAX_CORPUS_SHARE": 0.5,
    "VOCAB_SCAN_TIMEOUT_S": 20.0,
    # oracle inventor
    "ORACLE_TIER": "fast",
    "ORACLE_TEMPERATURE": 0.6,
    "ORACLE_MAX_TOKENS": 16000,
    "ORACLE_EVERY": 100,
    "ORACLE_CALLS_PER_RUN": 3,
    "ORACLE_RULES_PER_CALL": 3,
    "ORACLE_ACCEPT_ENGINES": ["duckdb", "datafusion", "sqlite", "postgres"],
    "ORACLE_ACCEPT_MIN_ENGINES": 3,
    "ORACLE_ACCEPT_INSTANCES": 5,
    "ORACLE_SCAN_MAX": 200,
}

# Reference rate the prior is calibrated against: RESIDUAL_PRIOR_FAILS / RESIDUAL_PRIOR_TESTS (theory, S6).
PRIOR_REFERENCE_RATE = 1.0 / 100.0

# ---- the harness's second rewrite layer (user decision 2026-10-15) ---------------------------

LIBRARY = {
    "LIBRARY_ENV": "SURPRISE_REWRITE_LIBRARY",
    "LIBRARY_RULE_PREFIX": "llm:",
    "LIBRARY_KINDS": ("query_wrap", "predicate_wrap"),
    "LIBRARY_MIN_REFERENCES": 2,
    "LIBRARY_SCHEMA": 1,
}
# The only harness files the unfreeze may touch (paths relative to the repository root).
HARNESS_CHANGED = (
    "framework/surprise/harness/oracles/rewrites.py",
    "framework/surprise/harness/oracles/equivalent_query.py",
)
UNFREEZE_BASE = "s09-done-r2"
FROZEN_RULES = ("double_negation", "demorgan", "case_to_coalesce")

# apply_rule on the three frozen rules, measured on the frozen code at s09-done-r2.
FROZEN_RULE_OUTPUTS = {
    ("SELECT a FROM t WHERE a > 1 ORDER BY a", "double_negation"): "SELECT a FROM t WHERE NOT (NOT (a > 1)) ORDER BY a",
    ("SELECT a FROM t WHERE a > 1 ORDER BY a", "demorgan"): None,
    ("SELECT a FROM t WHERE a > 1 ORDER BY a", "case_to_coalesce"): None,
    ("SELECT * FROM t WHERE NOT (a = 1 AND b IS NULL)", "double_negation"):
        "SELECT * FROM t WHERE NOT (NOT (NOT (a = 1 AND b IS NULL)))",
    ("SELECT * FROM t WHERE NOT (a = 1 AND b IS NULL)", "demorgan"): "SELECT * FROM t WHERE (NOT (a = 1)) OR (NOT (b IS NULL))",
    ("SELECT * FROM t WHERE NOT (a = 1 AND b IS NULL)", "case_to_coalesce"): None,
    ("SELECT CASE WHEN x IS NOT NULL THEN x ELSE y END FROM t", "double_negation"): None,
    ("SELECT CASE WHEN x IS NOT NULL THEN x ELSE y END FROM t", "case_to_coalesce"): "SELECT COALESCE(x, y) FROM t",
    ("SELECT v FROM t EXCEPT ALL SELECT v FROM u", "double_negation"): None,
    ("SELECT a FROM t WHERE a BETWEEN 1 AND 3", "double_negation"): "SELECT a FROM t WHERE NOT (NOT (a BETWEEN 1 AND 3))",
    ("SELECT a FROM t WHERE a BETWEEN 1 AND 3", "demorgan"): None,
    ("SELECT a FROM t WHERE NOT (a = 1 OR b = 2) GROUP BY a", "demorgan"):
        "SELECT a FROM t WHERE (NOT (a = 1)) AND (NOT (b = 2)) GROUP BY a",
}

# template_problem(kind, template): None for a usable template, a reason string otherwise.
TEMPLATES_OK = (
    ("query_wrap", "SELECT * FROM ({q}) AS llm_sub"),
    ("query_wrap", "WITH llm_cte AS ({q}) SELECT * FROM llm_cte"),
    ("predicate_wrap", "({p}) IS TRUE"),
    ("predicate_wrap", "CASE WHEN {p} THEN TRUE ELSE FALSE END"),
)
TEMPLATES_BAD = (
    ("query_wrap", ""),                                         # empty
    ("query_wrap", "SELECT * FROM t"),                          # no placeholder
    ("query_wrap", "SELECT * FROM ({q}) AS a UNION ALL {q}"),   # placeholder twice
    ("query_wrap", "SELECT * FROM ({q}) AS a; SELECT 1"),       # a second statement
    ("query_wrap", "SELECT * FROM ({q}) AS a -- note"),         # comment
    ("query_wrap", "DELETE FROM t WHERE EXISTS ({q})"),         # DML
    ("query_wrap", "SELECT * FROM ({q}) AS a WHERE {p}"),       # placeholder of the other kind
    ("predicate_wrap", "{q} IS TRUE"),                          # wrong placeholder
    ("predicate_wrap", "({p}) IS TRUE}"),                       # stray brace
    ("sql_rewrite", "SELECT * FROM ({q}) AS a"),                # unknown kind
)
# apply_template(query, kind, template) compared with same_statement(); None = premises fail.
APPLY_CASES = (
    ("SELECT a FROM t WHERE a > 1", "query_wrap", "SELECT * FROM ({q}) AS llm_sub",
     "SELECT * FROM (SELECT a FROM t WHERE a > 1) AS llm_sub"),
    ("SELECT a FROM t WHERE a > 1 ORDER BY a", "predicate_wrap", "({p}) IS TRUE",
     "SELECT a FROM t WHERE (((a > 1)) IS TRUE) ORDER BY a"),
    ("SELECT a FROM t", "predicate_wrap", "({p}) IS TRUE", None),                       # no WHERE
    ("DELETE FROM t WHERE a > 1", "query_wrap", "SELECT * FROM ({q}) AS llm_sub", None),  # not read-only
    ("SELECT a FROM t WHERE a > 1; SELECT 2", "query_wrap", "SELECT * FROM ({q}) AS llm_sub", None),
)

# A DuckDB case for the harness layer: the query keeps two of four rows.
LIBRARY_CASE = {
    "engine": "duckdb",
    "setup": ("CREATE TABLE lib_t(a INTEGER, b INTEGER)",
              "INSERT INTO lib_t VALUES (1, 10), (2, 20), (3, 30), (NULL, 40)"),
    "query": "SELECT a, b FROM lib_t WHERE a > 1",
    "predicate": None,
}
LIBRARY_RULES = {
    # equivalent: references agree, DuckDB agrees -> pass
    "llm:wrap_sub": ("query_wrap", "SELECT * FROM ({q}) AS llm_sub"),
    "llm:is_true": ("predicate_wrap", "({p}) IS TRUE"),
    # not equivalent: every reference sees one row instead of two -> untrusted_rewrite
    "llm:first_row": ("query_wrap", "SELECT * FROM ({q}) AS llm_sub LIMIT 1"),
    # DuckDB 1.5.5 has no octet_length(VARCHAR); DataFusion, SQLite and PostgreSQL agree (measured).
    # An error on the rewritten side is not evidence of a bug -> untrusted_rewrite, never fail.
    "llm:octet": ("query_wrap", "SELECT * FROM ({q}) AS llm_sub WHERE octet_length('ab') = 2"),
}
# Expected (y, invalid_reason, detail["premise"]) of certify(LIBRARY_CASE, "equivalent_query", rewrite_rule=rule).
LIBRARY_EXPECT = {
    "llm:wrap_sub": ("pass", None, None),
    "llm:is_true": ("pass", None, None),
    "llm:first_row": ("invalid", "untrusted_rewrite", "reference_disagrees"),
    "llm:octet": ("invalid", "untrusted_rewrite", "rewrite_error"),
}
LIBRARY_PREMISES = ("reference_disagrees", "too_few_references", "rewrite_error")
# A frozen-rule judgement must not change when a library is present (detail measured at s09-done-r2).
FROZEN_DETAIL = {"full_query": "SELECT a, b FROM lib_t WHERE a > 1", "rule": "double_negation",
                 "rewritten": "SELECT a, b FROM lib_t WHERE NOT (NOT (a > 1))"}

# ---- exploration prior --------------------------------------------------------------------

# Units a prepare() call is given (engine|oracle|construct|plan class|data class, features.units).
PRIOR_UNITS = tuple(
    f"datafusion|cross_dbms|{construct}|{plan}|{data}"
    for construct, plan, data in (
        ("set_op_all", "join", "dups"), ("set_op_all", "join", "nulls"), ("set_op", "union", "plain"),
        ("window", "window", "plain"), ("window", "window", "nulls"), ("outer_join", "join", "nulls"),
        ("join", "join", "plain"), ("join", "join", "dups"), ("subquery", "join", "nulls"),
        ("correlated_subquery", "join", "plain"), ("aggregate", "aggregate", "plain"),
        ("aggregate", "aggregate", "nulls"), ("distinct", "aggregate", "dups"), ("plain", "scan", "plain"),
        ("plain", "scan", "nulls"), ("plain", "sort", "plain"), ("dml", "scan", "plain"),
        ("asof_join", "asof_join", "plain"), ("set_op_all", "union", "dups"), ("window", "sort", "dups"),
    )
)
# Scripted prices: set operations look risky, plain scans do not.
PRIOR_PRICES = {"set_op_all": 0.3, "set_op": 0.1, "window": 0.05}
PRIOR_DEFAULT_PRICE = 0.02

# ---- migration translator -----------------------------------------------------------------

# A DuckDB family translated to DataFusion (recorded once with a real call; s10_llm/translator).
TRANSLATOR_REAL = {"case": "F2", "oracle": "plan_variant", "source": "duckdb", "target": "datafusion"}

# ---- vocabulary inventor ------------------------------------------------------------------
#
# A hand-built EXCEPT ALL family on DataFusion (cross_dbms, no fix set): three failures share
# one identity (missing_only) and two passes fall inside S. What separates them is textual:
# every failure reads two different tables, every pass reads the same table on both sides.

VOCAB_REASONS = ("definition", "pattern", "scan", "train", "holdout")
VOCAB_ENGINE = "datafusion"
VOCAB_ORACLE = "cross_dbms"
VOCAB_PHI = ("ast:set_op:except_all", "ast:stmt:select", "data:setop:left_has_dups", "data:table:dup_rows",
             "data:type:integer")
VOCAB_SETUP = ("CREATE TABLE vt(v INT)", "INSERT INTO vt VALUES (1),(1),(2)",
               "CREATE TABLE vu(v INT)", "INSERT INTO vu VALUES (1)",
               "CREATE TABLE vw(v INT)", "INSERT INTO vw VALUES (2),(2),(3)")
VOCAB_RECORDS = (
    # (record id, y, query); the ids must never reach a prompt
    ("vocab-r1", "fail", "SELECT v FROM vt EXCEPT ALL SELECT v FROM vu"),
    ("vocab-r2", "pass", "SELECT v FROM vt EXCEPT ALL SELECT v FROM vt"),
    ("vocab-r3", "fail", "SELECT v FROM vw EXCEPT ALL SELECT v FROM vu"),
    ("vocab-r4", "fail", "SELECT v FROM vt EXCEPT ALL SELECT v FROM vw"),
    ("vocab-r5", "pass", "SELECT v FROM vw EXCEPT ALL SELECT v FROM vw"),
)
# Split (the last ceil(n / 3) of each kind, in record order, are held out):
VOCAB_TRAIN = ("vocab-r1", "vocab-r3", "vocab-r2")   # positives r1, r3; contradiction r2
VOCAB_HELD = ("vocab-r4", "vocab-r5")                # positive r4; contradiction r5
VOCAB_PARENT = "ast:set_op"
VOCAB_GOOD = {
    "id": "ast:set_op:except_all_two_tables",
    "pattern": r"from\s+(\w+)\s+except\s+all\s+select\s+\w+\s+from\s+(?!\1\b)\w+",
}
# Each bad pattern, with the acceptance step that must refuse it (the book's "reason").
# Checks run in this order: pattern -> scan (corpus share, wall time) -> train -> holdout.
VOCAB_BAD = {
    # matches the empty string
    "empty": (r"", "pattern"),
    # longer than VOCAB_MAX_PATTERN_CHARS
    "long": ("select" + r"\s+" * 100, "pattern"),
    # catastrophic backtracking on ordinary SQL from the seed corpus (measured: > 60 s)
    "catastrophic": (r"(\w+\s?)+$", "scan"),
    # matches every statement of the seed corpus
    "everything": (r"select", "scan"),
    # matches every record, so it excludes no training contradiction
    "no_exclusion": (r"except\s+all", "train"),
    # matches the training positives only: misses the held-out positive v4
    "train_only": (r"from\s+(vt|vw)\s+except\s+all\s+select\s+\w+\s+from\s+vu\b", "holdout"),
}
# Seed corpus statements the scan reads (seeds/corpus.json, every engine): measured here.
CORPUS_STATEMENTS = 1092

# The same situation on the real engines, as loop bootstrap items (DataFusion, cross_dbms;
# measured here): DF-A opens h1, the second failure is its positive, the two passes fall in S.
_T = ("CREATE TABLE t(v INT)", "INSERT INTO t VALUES (1),(1),(2),(2),(2),(NULL)",
      "CREATE TABLE u(v INT)", "INSERT INTO u VALUES (1),(2),(NULL)")
VOCAB_BOOT = (
    ("fail", _T, "SELECT v FROM t EXCEPT ALL SELECT v FROM u"),
    ("fail", _T + ("CREATE TABLE u2(v INT)", "INSERT INTO u2 VALUES (1),(NULL),(NULL)"),
     "SELECT v FROM t EXCEPT ALL SELECT v FROM u2"),
    ("pass", _T, "SELECT v FROM t EXCEPT ALL SELECT v FROM t"),
    ("pass", _T + ("CREATE TABLE t2(v INT)", "INSERT INTO t2 VALUES (1),(1),(2),(2),(2),(NULL)"),
     "SELECT v FROM t EXCEPT ALL SELECT v FROM t2"),
)

# ---- oracle inventor ----------------------------------------------------------------------

ORACLE_SCRIPT = (
    {"name": "wrap_sub", "kind": "query_wrap", "template": "SELECT * FROM ({q}) AS llm_sub",
     "argument": "A derived table returns exactly the rows of its query, so selecting all of them keeps the bag."},
    {"name": "first_row", "kind": "query_wrap", "template": "SELECT * FROM ({q}) AS llm_sub LIMIT 1",
     "argument": "deliberately wrong: LIMIT drops rows"},
    {"name": "drop_t", "kind": "query_wrap", "template": "DELETE FROM t WHERE EXISTS ({q})",
     "argument": "deliberately invalid: not read-only"},
)
ORACLE_ACCEPTED = ("llm:wrap_sub",)

# ---- M3: the loop with every role on, from DF-A, recorded once with real calls (s10_llm/m3) ----

M3_RUN = {
    "seed": 0,
    "engines": ("datafusion",),
    "oracles": ("cross_dbms", "tlp", "norec", "equivalent_query"),
    "max_experiments": 40,
    "roles": ROLES,
    "bootstrap": ({"case": "DF-A", "oracle": "cross_dbms", "rule": None},),
}
# DF-B, judged by the identity referee (metrics.dups.identity_key on a certified failure).
DF_B = {
    "case": "DF-B",
    "oracle": "cross_dbms",
    "features": ("ast:set_op:intersect_all", "data:setop:left_has_dups"),
    "role_lanes": ("bet", "implement", "translate"),
}
# Keys of report.json compared between the recorded run and the replay.
REPORT_COMPARED = ("status", "experiments", "labels", "lanes", "triage", "families", "edits", "new_families")
# Every role book the replay must reproduce line for line (the S9 ones plus the four new ones).
BOOKS = ("calls.jsonl", "conjectures.jsonl", "implementer.jsonl", "prior.jsonl", "translations.jsonl",
         "vocabulary.jsonl", "rewrites.jsonl")
