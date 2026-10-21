"""Tables for gates/s16.py (PostgreSQL target, first harness unfreeze).

PostgreSQL behaviour below was measured by the orchestrator on 2026-10-21, before the work packages
existed, on scratch instances initialised like the pinned reference (UTF8, C, Australia/Sydney):
EDB 16.15 and 15.19 on Windows, through a prototype autocommit runner as the non-superuser target
role, with the old ``PlanVariantOracle`` and the tier-3 reproduction procedure of
``harness/cve/criterion.py``. See HANDOFF S16 for the numbers.
"""

from __future__ import annotations

BASE_TAG = "s19-deploy-5"
DONE_TAG = "s16-done"

# ---- environment ------------------------------------------------------------------------------------

TARGET_VERSION = "16.15"
OLD_VERSION = "15.19"
TARGET_DSN_ENV = "COEVO_TARGET_PG_DSN"
OLD_DSN_ENV = "COEVO_OLD_PG_DSN"
BIN_ENV = {"target": "COEVO_PG_BIN", "old": "COEVO_PG_OLD_BIN"}
TARGET_ROLE = "coevo_target"
# Server settings every instance carries, compared with current_setting() (the reference's values, SERVER.md 2).
SETTINGS = {
    "server_encoding": "UTF8",
    "TimeZone": "Australia/Sydney",
    "DateStyle": "ISO, MDY",
    "default_text_search_config": "pg_catalog.english",
    "lc_messages": "C",
    "fsync": "off",
    "autovacuum": "off",
    "listen_addresses": "127.0.0.1",
}
DATABASE_LOCALE = ("C", "C")  # pg_database.datcollate, datctype of the target database

# ---- the target runner ------------------------------------------------------------------------------

T_SETUP = (
    "CREATE TABLE t(a INT, b INT)",
    "INSERT INTO t VALUES (1, 2), (3, 4), (5, NULL)",
)
T_QUERY = "SELECT a, b FROM t WHERE b > 2"
# Statements the runner refuses before they reach the server (error text starts with NotApplicable).
REFUSED = (
    "BEGIN",
    "START TRANSACTION",
    "COMMIT",
    "ROLLBACK",
    "SAVEPOINT s1",
    "RELEASE SAVEPOINT s1",
    "SET search_path TO public",
    "RESET search_path",
    "SET ROLE coevo",
    "SET SESSION AUTHORIZATION coevo",
    "RESET ALL",
    "DISCARD ALL",
    "SELECT 1; SELECT 2",
)
# Executed, and refused by the server because the target role is not a superuser.
NOT_SUPERUSER = (
    "COPY t FROM PROGRAM 'echo 1'",
    "ALTER SYSTEM SET work_mem = '1MB'",
    "CREATE ROLE s16_intruder",
    "SELECT pg_read_file('postgresql.conf')",
)
SLOW_QUERY = "SELECT count(*) FROM generate_series(1, 5000000000)"

# ---- PG-F (postgres/PG-F_memoize_param.sql), with ANALYZE so 16.15 picks the Memoize plan --------------

PGF_TABLES = (
    "CREATE TABLE t0(ten int PRIMARY KEY)",
    "CREATE TABLE t1(unique1 int, hundred int, twenty int)",
    "CREATE TABLE t2(hundred int, x int)",
    "CREATE INDEX t1u ON t1(unique1)",
    "CREATE INDEX t2h ON t2(hundred)",
    "INSERT INTO t0 SELECT generate_series(0,9)",
    "INSERT INTO t1 SELECT i, i%10, i%5 FROM generate_series(0,999) i",
    "INSERT INTO t2 SELECT i%10, i  FROM generate_series(0,999) i",
)
PGF_ANALYZE = ("ANALYZE t0", "ANALYZE t1", "ANALYZE t2")
PGF_SETS = (
    "SET enable_seqscan = off",
    "SET enable_mergejoin = off",
    "SET enable_hashjoin = off",
    "SET work_mem = '64kB'",
)
PGF_QUERY = ("SELECT t0.ten, (SELECT count(*) FROM t1 JOIN t2 ON t2.hundred + t0.ten = t1.unique1 "
             "WHERE t1.twenty = t0.ten) FROM t0 ORDER BY 1")
PGF_WRONG = [[0, 200], [1, 100], [2, 100], [3, 100], [4, 100], [5, 100], [6, 0], [7, 0], [8, 0], [9, 0]]
PGF_RIGHT = [[0, 200], [1, 200], [2, 200], [3, 200], [4, 200], [5, 0], [6, 0], [7, 0], [8, 0], [9, 0]]
# Measured identity of PG-F (plan variant, tier 3).
PGF_PROFILE = {
    "witness_switches": ["no_memoize"],
    "fix_kind": "single",
    "fix_set": ["enable_memoize"],
    "plan_diff_has": "MEMOIZE",
    "version_ladder": "longstanding",  # 15.19 returns the same wrong rows
    "behavior_shape": "both",          # five rows missing, five extra
}
# The single-thread rerun prelude for PostgreSQL (CVE tier 1), from diagnosis.bisect.
SINGLE_THREAD_PRELUDE = ("SET max_parallel_workers_per_gather = 0",)

# ---- seven oracles on PostgreSQL ---------------------------------------------------------------------

# A marker literal the injecting fixtures look for. It never changes a result on any engine.
MARK = "616161"
MARKED_SETUP = T_SETUP
MARKED_QUERY = f"SELECT a, b FROM t WHERE b > 2 AND {MARK} = {MARK}"
MARKED_PREDICATE_CASE = ("SELECT a, b FROM t", f"b > 2 AND {MARK} = {MARK}")

# name -> (setup, query, predicate). Engine is always postgres.
CASES = {
    "plain": (T_SETUP, T_QUERY, None),
    "plain_pred": (T_SETUP, "SELECT a, b FROM t", "b > 2"),
    "marked": (MARKED_SETUP, MARKED_QUERY, None),
    "marked_pred": (MARKED_SETUP, MARKED_PREDICATE_CASE[0], MARKED_PREDICATE_CASE[1]),
    "PG-F": (PGF_TABLES + PGF_ANALYZE + PGF_SETS, PGF_QUERY, None),
    "PG-F_as_written": (PGF_TABLES + PGF_SETS, PGF_QUERY, None),
    "PG-F_no_sets": (PGF_TABLES + PGF_ANALYZE, PGF_QUERY, None),
    "PG-A": (("CREATE COLLATION nd (provider = icu, locale = 'und-u-ks-level2', deterministic = false)",
              "CREATE TABLE excl_t (s text COLLATE nd, EXCLUDE USING spgist (s WITH =))",
              "INSERT INTO excl_t VALUES ('a')",
              "INSERT INTO excl_t VALUES ('A')"), "SELECT * FROM excl_t", None),
    "PG-B": ((), "SELECT '-2562047788:00:54.775808'::interval", None),
    "PG-C": ((), "SELECT '23:59:59.9'::time + interval '9223372036854775000 microseconds'", None),
    "PG-G": ((), "SELECT * FROM pg_input_error_info('25:00:00', 'bit')", None),
    "superuser_type": (("CREATE TYPE s16t", "CREATE FUNCTION s16t_in(cstring) RETURNS s16t AS 'int4in' LANGUAGE internal"),
                       "SELECT 1", None),
    "copy_program": (("CREATE TABLE t(a INT)", "COPY t FROM PROGRAM 'echo 1'"), "SELECT a FROM t", None),
    "begin_in_setup": (("BEGIN", "CREATE TABLE t(a INT)"), "SELECT a FROM t", None),
    "random": (T_SETUP, "SELECT a, random() FROM t", None),
    "slow": ((), SLOW_QUERY, None),
    "server_version": ((), "SELECT current_setting('server_version_num')", None),
    "underscore": ((), "SELECT '1_000'::int", None),
    "no_table": ((), "SELECT 1", None),
    "indexable": (("CREATE TABLE t(a INT, b INT)",
                   "INSERT INTO t SELECT i, i % 7 FROM generate_series(1, 200) i"),
                  "SELECT a, b FROM t WHERE b > 3", None),
}

# Every oracle must label these cases with one of the three values (never harness_error).
EVERY_ORACLE_CASES = ("plain", "plain_pred", "PG-F", "PG-A", "PG-B", "no_table", "indexable")

# ---- M1 through evaluate_final -----------------------------------------------------------------------

# Real defects: fail, with the measured identity.
CONFIRMED = {"PG-F": "plan_variant"}
# Injected through gates/s16_fixtures.py: name -> (case, oracle, factory attribute, expected fail kind).
INJECTED = {
    "tlp_extra": ("marked_pred", "tlp", "TlpExtraRunner", "wrong_result"),
    "norec_count": ("marked_pred", "norec", "NorecCountRunner", "wrong_result"),
    "cross_drop": ("marked", "cross_dbms", "DropRowRunner", "wrong_result"),
    "version_drop": ("marked", "version_differential", "DropRowRunner", "wrong_result"),
    "index_drop": ("indexable_marked", "index_presence", "IndexDropRunner", "wrong_result"),
}
CASES["indexable_marked"] = (CASES["indexable"][0], f"SELECT a, b FROM t WHERE b > 3 AND {MARK} = {MARK}", None)
# Invalid, with the reason.
INVALID = {
    ("PG-B", "plan_variant"): "value_dependent_error",
    ("PG-C", "cross_dbms"): "insufficient_engines",
    ("PG-G", "cross_dbms"): "insufficient_engines",
    ("superuser_type", "plan_variant"): "setup_error",
    ("copy_program", "plan_variant"): "setup_error",
    ("begin_in_setup", "plan_variant"): "setup_error",
    ("random", "plan_variant"): "nondeterministic",
    ("slow", "plan_variant"): "timeout",
    ("server_version", "version_differential"): "direction_unknown",
    ("underscore", "version_differential"): "value_dependent_error",
    ("no_table", "index_presence"): "not_applicable",
}
# Pass: ordinary queries, the known defects these oracles cannot see, and PG-F where it does not reproduce.
PASS = (
    ("plain", "plan_variant"),
    ("plain", "cross_dbms"),
    ("plain", "version_differential"),
    ("plain", "equivalent_query"),
    ("plain_pred", "tlp"),
    ("plain_pred", "norec"),
    ("indexable", "index_presence"),
    ("PG-A", "plan_variant"),
    ("PG-F_as_written", "plan_variant"),
    ("PG-F", "version_differential"),
)
# seeds/pg_recall.py: defects fixed during 16.x (and 15.19); on 16.15 the plan variant passes them.
RECALL_PASS = (
    "pg18284_lateral_outer_join_null",
    "pg18344_bool_partprune_isnot",
    "pg18305_window_runcond_subplan",
    "pg16_datebin_neg_stride",
    "pg16_money_overflow",
    "pg16_numeric_trunc_clamp",
)
# postgres/ repros that 16.15 plus these oracles cannot label fail (recorded, not hidden).
RECALL_GAPS = {
    "PG-A": "the constraint is not enforced; every result-comparing oracle sees the same rows (pass)",
    "PG-B": "the reparse error is a value-dependent error (invalid)",
    "PG-C": "only DuckDB votes (DataFusion overflows, SQLite has no time type): fewer than three engines",
    "PG-D": "two SERIALIZABLE sessions in a fixed order; a single-session case cannot express it",
    "PG-E": "two SERIALIZABLE sessions in a fixed order; a single-session case cannot express it",
    "PG-F": "as written 16.15 plans without Memoize (pass); with ANALYZE it fails with fix set enable_memoize",
    "PG-G": "a diagnostic-only mismatch; the reference engines lack pg_input_error_info",
}

# ---- seeds ----------------------------------------------------------------------------------------------

PG_SEEDS = 308
MIN_SEED_SETUPS_OK = 95   # measured 102 on 16.15
MIN_SEED_QUERIES_OK = 85  # measured 93

# ---- replay (EXPERIMENT.md 8) ---------------------------------------------------------------------------

# The long run pinned at the base tag (S19 code, the harness before the unfreeze). S16's own long run is
# written next to it (results/s08/longrun-s16), so this directory is not moved.
REPLAY_RUN = "results/s08/longrun"
REPLAY_LEDGER_SHA256 = "22724758fe8d1de02a3313fd6eab7d6cbb18ef61c38cec1463cd89d14b8e4c51"
REPLAY_FULL = 2000
REPLAY_LIVE = 200
REPLAY_EVIDENCE = "replay_longrun.json"

# ---- phi, the loop, the grid and the report (third wave) ------------------------------------------------

PHI_CASES = ("PG-F", "plain_pred", "indexable", "PG-A")
# PG-F's plan as 16.15 prints it (EXPLAIN (FORMAT JSON) node types, spaces as underscores).
PGF_PLAN_LEAVES = ("plan:MEMOIZE", "plan:NESTED_LOOP", "plan:INDEX_SCAN", "plan:AGGREGATE", "plan:INDEX_ONLY_SCAN")
LOOP_SEED = 7
LOOP_EXPERIMENTS = 40
LOOP_MAX_HARNESS_ERROR = 0.10
GRID_MINUTES = 1.0
GRID_SEEDS = (7, 8)
KNOWN_CASES = "known_pg_cases.json"
PGF_KEY = "fix|postgres|enable_memoize"

# ---- SQLancer's PostgreSQL mode ---------------------------------------------------------------------------

# gates/s16_data/sqlancer: one real log from a 10-minute local run against 16.15 (SQLancer's own
# UnsupportedOperationException, the only kind that run produced), three written in the same format.
# Every log carries SQLancer's psql meta-commands and database statements, which the converter drops.
SQLANCER_FIXTURES = {
    "pg_norec_mismatch.log": {"kind": "mismatch", "sqlancer_oracle": "NOREC", "oracle": "norec", "converted": True,
                              "database_version": "16.15"},
    "pg_tlp_mismatch.log": {"kind": "mismatch", "sqlancer_oracle": "WHERE", "oracle": "tlp", "converted": True,
                            "database_version": "16.15"},
    "pg_unexpected_error.log": {"kind": "unexpected_error", "converted": False},
    "pg_tool_error_unsupported.log": {"kind": "tool_error", "converted": False},
}
SQLANCER_CASES = {
    "pg_norec_mismatch.log": {
        "engine": "postgres",
        "setup": ["CREATE TABLE t0(c0 INT)", "INSERT INTO t0(c0) VALUES(1)", "INSERT INTO t0(c0) VALUES(2)",
                  "INSERT INTO t0(c0) VALUES(3)"],
        "query": "SELECT * FROM t0",
        "predicate": "((t0.c0)>(1))",
    },
    "pg_tlp_mismatch.log": {
        "engine": "postgres",
        "setup": ["CREATE TABLE t0(c0 TEXT)", "INSERT INTO t0(c0) VALUES('a')", "INSERT INTO t0(c0) VALUES(NULL)",
                  "INSERT INTO t0(c0) VALUES('b')"],
        "query": "SELECT t0.c0 FROM t0",
        "predicate": "(t0.c0) IS NOT NULL",
    },
}
SQLANCER_LIVE_MINUTES = 5.0
SQLANCER_MIN_EXECUTIONS = 10_000  # one thread did about 200 queries per second locally
PG_JDBC = "postgresql-42.5.1.jar"

# ---- roles ----------------------------------------------------------------------------------------------

PG_SOURCE_DIR = "postgresql-16.15"
PG_SOURCE_COMMIT = "7d3e000c5961a544302072058a1184e9a588837b"  # tag REL_16_15
PG_RELEASE_NOTES = "doc/src/sgml/release-16.sgml"
# The PostgreSQL checkout is optional and lives outside roles/constants.py: the existing tests and the S9
# gate pin open_sources() and SOURCE_DIRS to DuckDB and DataFusion, and a missing optional checkout must
# not take the DuckDB and DataFusion readers down with it (open_sources() fails as a whole).
EXTRA_SOURCE_DIRS = {"postgres": PG_SOURCE_DIR}
EXTRA_SOURCE_COMMITS = {"postgres": PG_SOURCE_COMMIT}
# A memoize hypothesis must reach these PostgreSQL files.
PG_MEMOIZE_FILES = ("src/backend/executor/nodeMemoize.c",)

# ---- scope ----------------------------------------------------------------------------------------------

# Harness files the first unfreeze may change (user's consent: SESSIONS S16, batch unfreezing).
HARNESS_CHANGED = (
    "framework/surprise/harness/oracles/pg_target.py",
    "framework/surprise/harness/oracles/registry.py",
    "framework/surprise/harness/oracles/index_presence.py",
    "framework/surprise/harness/oracles/version_differential.py",
    "framework/surprise/harness/cve/certify.py",
    "framework/surprise/harness/cve/tier3.py",
    "framework/surprise/harness/manifest.py",
)
ALLOWED_CHANGES = HARNESS_CHANGED + (
    "framework/surprise/docs/",
    "framework/surprise/gates/s16.py",
    "framework/surprise/gates/s16_cases.py",
    "framework/surprise/gates/s16_fixtures.py",
    "framework/surprise/gates/s16_data/",
    # re-frozen after the unfreeze; S8 long run re-pinned after harness/ and experiments/ changed
    "framework/surprise/gates/s04_frozen.json",
    "framework/surprise/gates/s08_runs.json",
    "framework/surprise/experiments/pg_instance.py",
    "framework/surprise/experiments/loop.py",
    "framework/surprise/experiments/grid.py",
    "framework/surprise/baselines/pure_llm.py",
    "framework/surprise/baselines/sqlancer_run.py",
    "framework/surprise/features/plan.py",
    "framework/surprise/features/data.py",
    "framework/surprise/hunter/operators.py",
    "framework/surprise/metrics/",
    "framework/surprise/roles/source.py",
    "framework/surprise/roles/runtime.py",
    "framework/surprise/roles/prior.py",
    "framework/surprise/roles/conjecturer.py",
    "framework/surprise/roles/sources_map.py",
    "framework/surprise/roles/implementer.py",
    "framework/tests/test_surprise_s16_",
    "framework/tests/data/s16/",
    "docs/recall_repros_pg.json",
)
# Not touched by S16 (beyond HARNESS_CHANGED).
FROZEN_PATHS = (
    "framework/surprise/harness",
    "framework/oracles",
    "framework/targets",
    "framework/diagnosis",
    "framework/surprise/theory",
    "framework/surprise/diagnoser",
    "framework/seeds",
    "postgres",
)
