"""Fixed cases for the S4 gate (data only; ``gates/all.py`` does not run this file).

Every expectation was measured on this machine before dispatch: DuckDB 1.5.5
and 1.1.3, DataFusion 54.0.0 and 50.0.0, PostgreSQL 16.15, SQLite 3.51.0. The
raw labels come from the S3 oracles, the fix sets from the old bisect
(``diagnosis.bisect.compute_fix_set``), the stability figures from fresh
processes. The per-family verdicts follow the M1 table in HANDOFF.md.

``recall:<F>`` in a case means "read setup and query from
docs/recall_repros.json at gate time".
"""
from __future__ import annotations

# ---- shared setups ---------------------------------------------------------

T_SETUP = (
    "CREATE TABLE t(a INTEGER, b INTEGER, c VARCHAR)",
    "INSERT INTO t VALUES (1, 10, '5'), (2, 0, 'x'), (3, -4, '7'), (NULL, 3, NULL), (5, NULL, '0')",
)
AB_SETUP = ("CREATE TABLE t(a INT, b INT)", "INSERT INTO t VALUES (1,1),(2,NULL),(3,3)")
ALL_SETUP = (
    "CREATE TABLE t(v INT)", "INSERT INTO t VALUES (1),(1),(2),(2),(2),(NULL)",
    "CREATE TABLE u(v INT)", "INSERT INTO u VALUES (1),(2),(NULL)",
)
F6_DATA = ("INSERT INTO orders VALUES (2, 1, -1e308, 'a', DATE '2021-06-15'), "
           "(3, NULL, NULL, NULL, NULL), (9, 1, 0.0, 'a', DATE '2015-05-05')")
F6_PREDICATE_QUERY = (
    "SELECT o1.order_id, o1.amount FROM orders o1 WHERE NOT EXISTS (SELECT 1 FROM orders o2 "
    "WHERE o2.acct_id = o1.acct_id AND o2.order_id <> o1.order_id AND o2.amount > o1.amount)")
F10_SETUP = (
    "CREATE TABLE t1(id INT, ch VARCHAR, v INT)",
    "INSERT INTO t1 VALUES (1,'A',10),(2,'A',20),(3,'A',20),(4,'B',30),(5,'B',10),(6,'B',40),"
    "(7,'C',30),(NULL,'C',20)",
)
F11_SETUP = ("CREATE TABLE t(a INT, b INT)", "INSERT INTO t VALUES (1,10),(2,20)",
             "CREATE TABLE s(a INT, b INT)", "INSERT INTO s VALUES (1,100)")
ASOF_QUERY = ("SELECT px.p FROM ev ASOF JOIN px ON ev.id = px.id AND ev.ts >= px.ts "
              "ORDER BY ev.id, ev.ts, px.p")
# The F3 data without the tied right-hand rows (1,5,10)/(1,5,20).
ASOF_NO_TIES = ("CREATE TABLE ev(id INT, ts INT)", "CREATE TABLE px(id INT, ts INT, p INT)",
                "INSERT INTO ev VALUES (1,5),(1,9),(2,5)",
                "INSERT INTO px VALUES (1,5,10),(1,8,30),(2,4,40)")
NOISE = ("CREATE TABLE zz_noise(k INT, w VARCHAR)", "INSERT INTO zz_noise VALUES (1, 'x'), (2, 'y')")

# name -> (engine, setup | "recall:<F>", query | None, predicate)
CASES: dict[str, tuple[str, object, str | None, str | None]] = {
    # ---- confirmed families
    "F1": ("duckdb", "recall:F1", None, None),
    "F2": ("duckdb", "recall:F2", None, None),
    "F7": ("duckdb", "recall:F7", None, None),
    "F9": ("duckdb", "recall:F9", None, None),
    "F11": ("duckdb", F11_SETUP,
            "MERGE INTO t USING s ON t.a = s.a WHEN NOT MATCHED BY SOURCE THEN DELETE", None),
    # F6: schema and query of the recall entry plus three rows (HANDOFF, M1 note 1).
    "F6": ("duckdb", "recall:F6+data", None, None),
    "F6_predicate": ("duckdb", "recall:F6+data", F6_PREDICATE_QUERY, "o1.placed IS NOT NULL"),
    "F2_file": ("duckdb", "recall:F2",
                "SELECT SUM(v) OVER (PARTITION BY a, b) AS w_ab, SUM(v) OVER (PARTITION BY a, a) AS w_aa "
                "FROM src ORDER BY b", None),
    "F7_file": ("duckdb", ("CREATE TABLE t(d DATE)",
                           "INSERT INTO t VALUES (DATE '2023-02-28'), (DATE '2024-01-31'), (DATE '2024-02-29')"),
                "SELECT d + INTERVAL '1 month' AS a, d + INTERVAL '30 days' AS b FROM t ORDER BY d", None),
    # ---- families that must end up invalid
    "F3": ("duckdb", "recall:F3", None, None),
    "F8": ("duckdb", "recall:F8", None, None),
    "F5": ("duckdb", "recall:F5", None, None),
    "F10_q1": ("duckdb", F10_SETUP,
               "SELECT ntile(2 ORDER BY v) OVER (ORDER BY v ROWS BETWEEN 2 FOLLOWING AND 1 FOLLOWING) FROM t1", None),
    "F10_q2": ("duckdb", F10_SETUP,
               "SELECT ntile(2 ORDER BY ch) OVER (ORDER BY ch ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING) FROM t1", None),
    "F10_q3": ("duckdb", F10_SETUP,
               "SELECT count(*) OVER (ORDER BY v ROWS BETWEEN 1 PRECEDING AND 5 PRECEDING) FROM t1", None),
    "F10_q4": ("duckdb", F10_SETUP,
               "SELECT row_number(ORDER BY v) OVER (PARTITION BY ch ORDER BY v, id ROWS BETWEEN 1 FOLLOWING "
               "AND 2 FOLLOWING) FROM t1", None),
    # ---- .sql variants that do not reproduce with the data in the file
    "F5_file": ("duckdb", ("CREATE TABLE ordered_probe(ord INT, flag INT)",
                           "INSERT INTO ordered_probe SELECT range, range % 2 FROM range(10)",
                           "CREATE TABLE boolean_keys(flag_key INT)", "INSERT INTO boolean_keys VALUES (0), (1)"),
                "WITH c AS (SELECT flag FROM ordered_probe ORDER BY ord OFFSET 2) "
                "SELECT * FROM c INNER JOIN boolean_keys ON flag <= flag_key", None),
    "F6_file": ("duckdb", ("CREATE TABLE f6_a(x INT, y INT)", "INSERT INTO f6_a VALUES (1,1),(2,2),(3,NULL),(NULL,4)",
                           "CREATE TABLE f6_b(x INT, y INT)", "INSERT INTO f6_b VALUES (1,1),(2,9),(NULL,3)"),
                "SELECT * FROM f6_a a WHERE NOT EXISTS (SELECT 1 FROM f6_b b WHERE b.x = a.x AND b.y <> a.y) "
                "AND a.x NOT IN (SELECT b.y FROM f6_b b WHERE b.x IS NULL) ORDER BY 1, 2", None),
    # ---- datafusion/*.sql
    "DF-A": ("datafusion", ALL_SETUP, "SELECT v FROM t EXCEPT ALL SELECT v FROM u", None),
    "DF-B": ("datafusion", ALL_SETUP, "SELECT v FROM t INTERSECT ALL SELECT v FROM u", None),
    "DF-D": ("datafusion", ("CREATE TABLE t(a INT, b INT GENERATED ALWAYS AS (a * 2) STORED)",
                            "INSERT INTO t(a) VALUES (1), (2), (3)"), "SELECT a, b FROM t ORDER BY a", None),
    "DF-E1": ("datafusion", ("CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1),(2)",
                             "CREATE TABLE u(a INT, w INT)", "INSERT INTO u VALUES (1,10),(2,20)"),
              "SELECT a, (SELECT w FROM u WHERE u.a = t.a) FROM t", None),
    "DF-E2": ("datafusion", (),
              "WITH RECURSIVE t(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM t WHERE n < 5) SELECT * FROM t", None),
    "DF-F": ("datafusion", ("CREATE TABLE a(x INT, y INT)", "INSERT INTO a VALUES (1, 10)",
                            "CREATE TABLE b(x INT, z INT)", "INSERT INTO b VALUES (2, 20)"),
             "SELECT * FROM a RIGHT JOIN b USING (x)", None),
    "DF-G": ("datafusion", (), "SELECT CAST(123456789012345678901234567890.123 AS DECIMAL(38,3))", None),
    "DF-H1": ("datafusion", (),
              "WITH RECURSIVE t AS (SELECT 1 AS n UNION ALL SELECT n + 1 FROM t WHERE n < 5) SELECT count(*) FROM t", None),
    "DF-H2": ("datafusion", (),
              "WITH RECURSIVE t AS (SELECT 1 AS n UNION SELECT n + 1 FROM t WHERE n < 5) SELECT count(*) FROM t", None),
    "DF-I": ("datafusion", ("CREATE TABLE t(a INT, b INT)", "INSERT INTO t VALUES (1,5),(2,15),(3,25),(NULL,10)",
                            "CREATE TABLE u(w INT)", "INSERT INTO u VALUES (10),(20)"),
             "SELECT a FROM t WHERE b > ALL (SELECT w FROM u)", None),
    "DF-J": ("datafusion", ("CREATE TABLE t(id INT, l INT[])", "INSERT INTO t VALUES (1, [10, 20]), (2, [30])"),
             "SELECT t.id, e.c FROM t, UNNEST(t.l) AS e(c)", None),
    # ---- ordinary queries and known false-positive classes
    "plain": ("duckdb", T_SETUP, "SELECT a, b FROM t", "a > 1"),
    "plain_df": ("datafusion", AB_SETUP, "SELECT a, b FROM t", "b > 1"),
    "plain_ab": ("duckdb", AB_SETUP, "SELECT a, b FROM t", "b > 1"),
    "vd_partial": ("duckdb", T_SETUP, "SELECT a FROM t", "c <> 'x' AND CAST(c AS INTEGER) > 0"),
    "vd_overflow": ("duckdb", T_SETUP, "SELECT a FROM t", "a * 2147483647 > b"),
    "unordered_limit": ("duckdb", T_SETUP, "SELECT a FROM t LIMIT 2", None),
    "rewrite_base": ("duckdb", AB_SETUP, "SELECT a FROM t WHERE b > 1", None),
    "asof_no_ties": ("duckdb", ASOF_NO_TIES, ASOF_QUERY, None),
    "date_df": ("datafusion", (), "SELECT DATE '2020-01-02' AS d", None),
    "date_duck": ("duckdb", ("CREATE TABLE t(d DATE)", "INSERT INTO t VALUES ('2020-01-02')"), "SELECT d FROM t", None),
    "delete_returning": ("duckdb", ("CREATE TABLE t(a INT, b INT)", "INSERT INTO t VALUES (1,10),(2,20),(3,30)"),
                         "DELETE FROM t WHERE a = 1 RETURNING a", None),
    "update_returning": ("duckdb", ("CREATE TABLE t(a INT, b INT)", "INSERT INTO t VALUES (1,10),(2,20),(3,30)"),
                         "UPDATE t SET b = b + 1 WHERE a = 2 RETURNING b", None),
    # Injection target for the inline checks: full_query(case) equals the query text.
    "inject": ("duckdb", T_SETUP, "SELECT a, b FROM t WHERE a > 1", None),
}

# Statements that kill a DuckDB 1.5.5 process on this platform (exit 0xC0000094).
FATAL = ("F10_q1", "F10_q2")

# ---- expectations ----------------------------------------------------------

DELIM = ["deliminator", "filter_pushdown"]

# Confirmed families after tier 3 (certify(..., diagnose=True)):
# case -> (oracle, fail_kind, identity.switches, profile.fix_set, version ladder, error_class)
# The version ladder is the old sigma's nu: longstanding = 1.1.3 returns the
# same rows as 1.5.5, recent = it differs, unknown = 1.1.3 cannot parse it.
CONFIRMED = {
    "F1": ("plan_variant", "wrong_result", DELIM, DELIM, "longstanding", None),
    "F2": ("plan_variant", "wrong_result", ["window_self_join"], ["window_self_join"], "recent", None),
    "F7": ("plan_variant", "wrong_result", ["common_subexpressions", "expression_rewriter"],
           ["common_subexpressions", "expression_rewriter"], "longstanding", None),
    # No stable optimizer fix set: identity stays the witnessing switch.
    "F9": ("plan_variant", "wrong_result", ["window_combine"], [], "longstanding", None),
    "F11": ("plan_variant", "crash", ["build_side_probe_side"], ["build_side_probe_side"], "unknown",
            "InternalException"),
    "F6": ("plan_variant", "wrong_result", DELIM, DELIM, "longstanding", None),
    "F6_predicate": ("tlp", "wrong_result", DELIM, DELIM, "longstanding", None),
    "F2_file": ("plan_variant", "wrong_result", ["window_self_join"], ["window_self_join"], "recent", None),
    "F7_file": ("plan_variant", "wrong_result", ["common_subexpressions", "expression_rewriter"],
                ["common_subexpressions", "expression_rewriter"], "longstanding", None),
}
# Families whose recall entry carries the fix set the bisect must land on.
RECALL_FIX_SETS = ("F1", "F2", "F7", "F9")

# DataFusion confirmed families at tier 1: case -> (fail_kind, behavior shape | None, error_class)
DF_CONFIRMED = {
    "DF-A": ("wrong_result", "missing_only", None),
    "DF-B": ("wrong_result", "extra_only", None),
    "DF-D": ("wrong_result", "both", None),
    "DF-F": ("wrong_result", "both", None),
    "DF-I": ("crash", None, "Exception"),
}

# case -> (oracle, invalid_reason). F5 is checked separately (it is flaky).
INVALID = {
    "F3": ("plan_variant", "unspecified_semantics"),
    "F8": ("plan_variant", "unstable_rerun"),
    "F10_q1": ("plan_variant", "nondeterministic"),
    "F10_q2": ("plan_variant", "nondeterministic"),
    "F10_q3": ("plan_variant", "nondeterministic"),
    "F10_q4": ("plan_variant", "nondeterministic"),
    "DF-E1": ("cross_dbms", "query_error"),
    "DF-E2": ("cross_dbms", "query_error"),
    "DF-H1": ("cross_dbms", "query_error"),
    "DF-H2": ("cross_dbms", "query_error"),
    "DF-J": ("cross_dbms", "query_error"),
    # known false-positive classes
    "vd_partial": ("tlp", "value_dependent_error"),
    "vd_overflow": ("plan_variant", "value_dependent_error"),
    "unordered_limit": ("plan_variant", "nondeterministic"),
    "date_df": ("cross_dbms", "incomparable_results"),
    "delete_returning": ("plan_variant", "side_effecting_statement"),
    "update_returning": ("plan_variant", "side_effecting_statement"),
}

# (case, oracle) pairs that must pass.
PASS = (
    ("F5_file", "plan_variant"), ("F6_file", "plan_variant"), ("F6_file", "index_presence"),
    ("DF-G", "cross_dbms"), ("asof_no_ties", "plan_variant"),
    ("plain", "tlp"), ("plain", "norec"), ("plain", "plan_variant"),
    ("plain_ab", "index_presence"), ("plain_ab", "version_differential"), ("plain_ab", "cross_dbms"),
    ("plain_df", "tlp"), ("plain_df", "norec"), ("plain_df", "plan_variant"),
    ("plain_df", "version_differential"), ("plain_df", "cross_dbms"),
)

# Confirmed upstream defects the frozen judging code cannot label fail (recorded, not hidden).
RECALL_GAPS = {
    "F10": "explicit window frames are screened as nondeterministic before execution",
    "F5": "flaky: invalid/unstable_rerun by the PLAN label rule",
    "DF-E": "planner rejects legal SQL: a query error is invalid",
    "DF-H": "panic text is not an internal-error marker of the old normalizer",
    "DF-J": "planner rejects legal SQL: a query error is invalid",
    "DF-G": "old loose normalization rounds DECIMAL to float",
}

NEW_INVALID_REASONS = ("unstable_rerun", "unspecified_semantics", "side_effecting_statement",
                       "incomparable_results", "unattributed_crash", "not_reproduced_minimized")
CVE_STEPS = ("rerun", "premise", "attribution", "minimize", "profile")
LADDER_VALUES = ("longstanding", "recent", "unknown", "unavailable")
SHAPES = ("missing_only", "extra_only", "both", "none")

# Hand-written known hypotheses for the tier-2 interface (no theory layer yet).
H_F1 = {"hypothesis_id": "h-f1", "engine": "duckdb", "interventions": DELIM}
H_DFA = {"hypothesis_id": "h-dfa", "engine": "datafusion", "interventions": [],
         "fail_kind": "wrong_result", "error_class": None, "behavior_shape": "missing_only"}
