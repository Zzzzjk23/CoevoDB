"""Fixed cases for the S9 gate (data only; ``gates/all.py`` does not run this file).

Everything here was decided or measured on this machine before dispatch:
DuckDB 1.5.5, DataFusion 54.0.0, PostgreSQL 16.15, and the two engine source
checkouts under ``<main checkout>/.src`` (shallow clones of the release tags).
"""
from __future__ import annotations

# ---- constants (PLAN decision 8: written into the run manifest's llm section) -------

TIERS = {"fast": "deepseek-flash", "strong": "deepseek-v4-pro"}

CONSTANTS = {
    "TIERS": TIERS,
    "DEFAULT_MAX_CALLS": 200,
    "CAP_ENV": "SURPRISE_LLM_MAX_CALLS",
    "REQUIRED_FIELD": "prediction",
    "SOURCE_ROOT_ENV": "SURPRISE_SOURCE_ROOT",
    "SOURCE_DIRS": {"duckdb": "duckdb-v1.5.5", "datafusion": "datafusion-54.0.0"},
    "SOURCE_COMMITS": {
        "duckdb": "d8cdaa33fda8df955cc76ef58a280f68f4cd43fa",
        "datafusion": "45d943dfb8699dc9cb9ef2320e955b73e3e6c03b",
    },
    "SOURCE_MAX_FILE_BYTES": 2_000_000,
    "IMPLEMENTER_TIER": "fast",
    "IMPLEMENTER_TEMPERATURE": 0.2,
    "IMPLEMENTER_MAX_TOKENS": 2000,
    "IMPLEMENTER_ATTEMPTS": 2,
    "IMPLEMENTER_PER_CHOICE": 1,
    "CONJECTURER_TIER": "fast",
    "CONJECTURER_TEMPERATURE": 0.6,
    "CONJECTURER_MAX_TOKENS": 8000,
    "CONJECTURER_MAX_PREDICTIONS": 5,
    "SOURCE_MAX_FILES": 4,
    "SOURCE_MAX_LINES": 400,
}
GATEWAY_CONSTANTS = ("TIERS", "DEFAULT_MAX_CALLS", "CAP_ENV", "REQUIRED_FIELD", "SOURCE_ROOT_ENV",
                     "SOURCE_DIRS", "SOURCE_COMMITS", "SOURCE_MAX_FILE_BYTES")

STATUSES = ("ok", "rejected", "blocked", "miss", "error")
SOURCES = ("network", "cache")
LEDGER_KEYS = ("seq", "role", "tier", "model", "seed", "key", "prompt_sha256", "status", "source", "reason",
               "input_tokens", "output_tokens", "latency_s")
CACHE_ENTRY_KEYS = ("key", "prompt_sha256", "model", "seed", "role", "tier", "prompt", "text",
                    "input_tokens", "output_tokens", "temperature", "max_tokens", "created_at")
ROLE_TOTAL_KEYS = ("calls", "network", "cache", "ok", "rejected", "blocked", "miss", "error",
                   "input_tokens", "output_tokens")
ATTEMPT_STATUSES = ("ok", "spec_unmet", "bad_case", "rejected", "blocked", "miss", "error")
CONJECTURE_STATUSES = ("registered", "rejected", "blocked", "miss", "error")
PENDING_STATES = ("open", "kept", "broken")
ROLES = ("implementer", "conjecturer")

# Modules that mean "a model client or the old agent code is loaded" (the S8 list).
LLM_MODULES = ("openai", "httpx", "httpx2", "anthropic", "agents", "agents.base_agent", "agents.bug_hunter",
               "agents.bug_fixer", "llm", "llm.ledger", "evolution.co_evolution", "guidelines")

# ---- roles off: the loop is S8's loop ------------------------------------------------
#
# S8's long run (results/s08/longrun, seed 0, DuckDB, seven oracles) and a fresh
# 40-experiment run of the S8 code at s08-done-r2 agree on every progress row
# once ``elapsed_s`` is dropped. The hash is sha256 of
# json.dumps(rows, sort_keys=True, separators=(",", ":")) over those 40 rows.
OFF_PREFIX = {
    "seed": 0,
    "engines": ("duckdb",),
    "experiments": 40,
    "sha256": "640dfaa60ed68ab33cfc044ebb0ee0810d07096f02b96e32fabccdccd97ef559",
    "keys": ("D", "U", "adjacent", "bets", "case_digest", "edits", "elapsed_s", "hypothesis", "index", "kind",
             "lane", "op", "opened", "oracle", "owner", "p_fail_valid", "p_invalid", "parent", "pool",
             "predicted", "probes", "record_id", "rolled_back", "rule", "seq", "slot", "surprise", "target",
             "theory_version", "triage", "value", "y", "zone"),
}

# ---- implementer: the specs of the phi-check report -------------------------------
#
# For the ten families the S7 replay can feed (gates/s07_cases.py), three specs each,
# from the reduced phi of the family's first adjudicated statement (measured here):
#   whole     every ast- and data-layer literal of that S (plan literals left out: the
#             implementer writes SQL, it does not pick plans);
#   core      the family's characteristic literals, chosen by hand from that S;
#   boundary  core minus one literal, which becomes forbidden: a probe just outside S.
_FAMILIES = {
    # family: (engine, oracle, whole, core, dropped from core)
    "F1": ("duckdb", "plan_variant",
           ("ast:bool:and", "ast:clause:order_by", "ast:clause:where", "ast:cmp:eq", "ast:cmp:neq",
            "ast:corr_cmp:eq", "ast:corr_cmp:neq", "ast:expr:arith", "ast:join:inner", "ast:join:left",
            "ast:join_cond:using", "ast:join_trait:self", "ast:stmt:select", "ast:subquery:exists",
            "ast:subquery_pos:select", "ast:subquery_trait:correlated", "data:table:single_row",
            "data:type:integer"),
           ("ast:join:left", "ast:join_cond:using", "ast:subquery:exists", "ast:subquery_trait:correlated"),
           "ast:subquery_trait:correlated"),
    "F2": ("duckdb", "plan_variant",
           ("ast:clause:order_by", "ast:stmt:select", "ast:window_fn:aggregate", "ast:window_spec:partition",
            "ast:window_trait:dup_partition_key", "ast:window_trait:multiple", "data:type:integer"),
           ("ast:window_fn:aggregate", "ast:window_spec:partition", "ast:window_trait:dup_partition_key"),
           "ast:window_trait:dup_partition_key"),
    "F7": ("duckdb", "plan_variant",
           ("ast:clause:order_by", "ast:expr:arith", "ast:expr:date_arith", "ast:expr:interval",
            "ast:stmt:select", "data:type:date"),
           ("ast:expr:date_arith", "ast:expr:interval", "data:type:date"),
           "ast:expr:interval"),
    "F9": ("duckdb", "plan_variant",
           ("ast:clause:distinct", "ast:clause:order_by", "ast:cmp:eq", "ast:cmp:gt", "ast:expr:case",
            "ast:pred:is_null", "ast:stmt:select", "ast:window_fn:aggregate", "ast:window_spec:empty",
            "data:table:has_null", "data:type:integer"),
           ("ast:clause:distinct", "ast:window_fn:aggregate", "ast:window_spec:empty"),
           "ast:clause:distinct"),
    "F11": ("duckdb", "plan_variant",
            ("ast:cmp:eq", "ast:merge:delete", "ast:merge:not_matched_by_source", "ast:stmt:merge",
             "data:table:single_row", "data:type:integer"),
            ("ast:merge:delete", "ast:merge:not_matched_by_source", "ast:stmt:merge"),
            "ast:merge:not_matched_by_source"),
    "DF-A": ("datafusion", "cross_dbms",
             ("ast:set_op:except_all", "ast:stmt:select", "data:setop:left_has_dups", "data:setop:left_has_null",
              "data:setop:right_has_null", "data:table:dup_rows", "data:table:has_null", "data:type:integer"),
             ("ast:set_op:except_all", "data:setop:left_has_dups"),
             "data:setop:left_has_dups"),
    "DF-B": ("datafusion", "cross_dbms",
             ("ast:set_op:intersect_all", "ast:stmt:select", "data:setop:left_has_dups",
              "data:setop:left_has_null", "data:setop:right_has_null", "data:table:dup_rows",
              "data:table:has_null", "data:type:integer"),
             ("ast:set_op:intersect_all", "data:setop:left_has_dups"),
             "data:setop:left_has_dups"),
    "DF-D": ("datafusion", "cross_dbms",
             ("ast:clause:order_by", "ast:stmt:select", "data:table:has_null", "data:type:integer"),
             ("ast:clause:order_by", "data:table:has_null"),
             "data:table:has_null"),
    "DF-F": ("datafusion", "cross_dbms",
             ("ast:join:right", "ast:join_cond:using", "ast:stmt:select", "data:table:single_row",
              "data:type:integer"),
             ("ast:join:right", "ast:join_cond:using"),
             "ast:join:right"),
    "DF-I": ("datafusion", "cross_dbms",
             ("ast:clause:where", "ast:cmp:gt", "ast:stmt:select", "ast:subquery:all", "ast:subquery_pos:where",
              "data:table:has_null", "data:type:integer"),
             ("ast:subquery:all", "ast:subquery_pos:where", "data:table:has_null"),
             "data:table:has_null"),
}


def _specs() -> list[dict]:
    out: list[dict] = []
    for family, (engine, oracle, whole, core, dropped) in _FAMILIES.items():
        base = {"engine": engine, "oracle": oracle, "data_properties": []}
        out.append({"id": f"{family}/whole", "spec": {**base, "required": list(whole), "forbidden": []}})
        out.append({"id": f"{family}/core", "spec": {**base, "required": list(core), "forbidden": []}})
        out.append({"id": f"{family}/boundary",
                    "spec": {**base, "required": [x for x in core if x != dropped], "forbidden": [dropped]}})
    return out


IMPLEMENTER_SPECS = _specs()
IMPLEMENTER_SEED = 0
REPORT_KEYS = ("specs", "first_ok", "final_ok", "first_rate", "final_rate", "by_kind", "rows", "calls")
REPORT_ROW_KEYS = ("id", "status", "tries", "first_ok", "ok", "missing", "forbidden", "undetermined", "expect")

# ---- conjecturer on DF-A ------------------------------------------------------------

DFA_CASE = "DF-A"            # gates/s04_cases.py
DFA_ORACLE = "cross_dbms"
CONJECTURE_SEED = 0
# The DataFusion code that lowers EXCEPT ALL / INTERSECT ALL (both become a semi / anti join).
DFA_SOURCE_PATH = "datafusion/expr/src/logical_plan/builder.rs"
DFA_SOURCE_MARK = "fn intersect_or_except"
# A DuckDB fix set and the optimizer file the selection must include for it.
DUCKDB_FIX = ("filter_pushdown",)
DUCKDB_SOURCE_PATH = "src/optimizer/filter_pushdown.cpp"

# Scripted conjecturer replies on DF-A (role-logic checks; the real reply is pinned in s09_llm/dfa).
GOOD_TRIGGER = ["ast:set_op:except_all", "data:setop:left_has_dups"]
GOOD_PREDICTIONS = [
    {"required": ["ast:set_op:intersect_all", "data:setop:left_has_dups"], "forbidden": [], "data_properties": [],
     "expect": "fail", "why": "INTERSECT ALL goes through the same semi-join lowering"},
    {"required": ["ast:set_op:except_all"], "forbidden": ["data:setop:left_has_dups"], "data_properties": [],
     "expect": "pass", "why": "without duplicates on the left there is no multiplicity to lose"},
]
MECHANISM = "EXCEPT ALL is planned as a LeftAnti join, which drops every left row with a match and so loses multiplicities"

# ---- the loop with roles on, recorded once with real calls (s09_llm/loop) -----------

LOOP_RUN = {
    "seed": 0,
    "engines": ("datafusion",),
    "oracles": ("cross_dbms", "tlp", "norec"),
    "max_experiments": 20,
    "roles": ("implementer", "conjecturer"),
    "bootstrap": ({"case": "DF-A", "oracle": "cross_dbms", "rule": None},),
}
# Keys of report.json compared between the recorded run and the replay.
REPORT_COMPARED = ("status", "experiments", "labels", "lanes", "triage", "families")
