"""Fixed cases for the S2 gate (data only; ``gates/all.py`` does not run this file).

Every expectation below was measured with the old oracles on DuckDB 1.5.5
before the adapters existed. ``EXPECT[case][oracle]`` is
``(y, fail_kind or invalid_reason or None)``.

Sources of the known failures:

* ``metrics_small`` is the minimised form of ledger entries AUTO-a8be20c9
  (TLP) and AUTO-ad38bad6 (NoREC) in ``docs/manual_findings.jsonl``: a
  correlated NOT EXISTS that keeps a row it must drop (family F1).
* ``inv_delim`` is the case in ``testing/test_new_components.py``
  (``test_catches_deliminator_bug``), same family seen by plan variant.
* ``recall_F1`` / ``recall_F2`` / ``recall_F7`` are read from
  ``docs/recall_repros.json`` at gate time (confirmed families).

F3 and F8 (unspecified semantics), F9 (debug setting) and F10 (kills the
process on this platform) are deliberately absent: they need the CVE pipeline
and process isolation that S4 adds.
"""
from __future__ import annotations

T_SETUP = (
    "CREATE TABLE t(a INTEGER, b INTEGER, c VARCHAR)",
    "INSERT INTO t VALUES (1, 10, '5'), (2, 0, 'x'), (3, -4, '7'), (NULL, 3, NULL), (5, NULL, '0')",
)
METRICS_SETUP = (
    "CREATE TABLE metrics (m_id INTEGER, k VARCHAR, v DOUBLE, d DATE)",
    "INSERT INTO metrics VALUES (2, '', -1e308, DATE '2021-06-15'), (3, NULL, NULL, NULL), "
    "(9, '', 0.0, DATE '2015-05-05')",
)
INV_SETUP = (
    "CREATE TABLE inv(item_id BIGINT, price DECIMAL(12,2), stock INTEGER)",
    "INSERT INTO inv VALUES (2,-0.01,-5),(7,-0.01,10),(4,0.00,0),(9,0.00,7)",
)
BROKEN_SETUP = (
    "CREATE TABLE t(a INTEGER)",
    "INSERT INTO no_such_table VALUES (1)",
)

_NOT_EXISTS = ("NOT EXISTS (SELECT 1 FROM metrics m2 WHERE m2.k = m.k AND m2.v < m.v "
               "AND m2.m_id <> m.m_id)")
_GUARDED_CAST = "c <> 'x' AND CAST(c AS INTEGER) > 0"

# name -> (setup, query, predicate)
CASES: dict[str, tuple[tuple[str, ...], str, str | None]] = {
    # ---- ordinary queries
    "plain": (T_SETUP, "SELECT a, b FROM t", "a > 1"),
    "plain_no_predicate": (T_SETUP, "SELECT a, b FROM t", None),
    "aggregate": (T_SETUP, "SELECT COUNT(*) FROM t", "a > 1"),
    "grouped": (T_SETUP, "SELECT b FROM t GROUP BY b", "a > 1"),
    "grouped_with_where": (T_SETUP, "SELECT b, c FROM t WHERE b IS NOT NULL GROUP BY b, c", "a > 1"),
    "distinct": (T_SETUP, "SELECT DISTINCT c FROM t", "a > 1"),
    "grouped_with_aggregate": (T_SETUP, "SELECT b, COUNT(*) FROM t GROUP BY b", "a > 1"),
    # ---- known failures
    "metrics_small": (METRICS_SETUP, f"SELECT m.m_id, m.k FROM metrics m WHERE {_NOT_EXISTS}",
                      "m.d IS NOT NULL"),
    "inv_delim": (INV_SETUP, "SELECT i.item_id FROM inv i",
                  "EXISTS (SELECT 1 FROM inv j WHERE j.price=i.price "
                  "AND j.item_id<>i.item_id AND j.stock>i.stock)"),
    # ---- value-dependent errors (evaluation order decides whether they fire)
    "vd_partial": (T_SETUP, "SELECT a FROM t", _GUARDED_CAST),
    "vd_grouped": (T_SETUP, "SELECT b FROM t GROUP BY b", _GUARDED_CAST),
    "vd_subquery": (T_SETUP, "SELECT a FROM t WHERE a IN (SELECT a FROM t WHERE c <> 'x')",
                    "CAST(c AS INTEGER) > 0"),
    "vd_overflow": (T_SETUP, "SELECT a FROM t", "a * 2147483647 > b"),
    # ---- other invalid inputs
    "bad_column": (T_SETUP, "SELECT a FROM t", "zzz > 1"),
    "nondeterministic_random": (T_SETUP, "SELECT a FROM t", "random() < 0.5"),
    "nondeterministic_limit": (T_SETUP, "SELECT a FROM t LIMIT 2", None),
    "broken_setup": (BROKEN_SETUP, "SELECT a FROM t", "a > 0"),
}

# Cases appended at gate time from docs/recall_repros.json: name -> family id.
RECALL_CASES = {"recall_F1": "F1", "recall_F2": "F2", "recall_F7": "F7"}

PASS = ("pass", None)
NA = ("invalid", "not_applicable")
VD = ("invalid", "value_dependent_error")
QERR = ("invalid", "query_error")
NONDET = ("invalid", "nondeterministic")
SETUP_ERR = ("invalid", "setup_error")
WRONG = ("fail", "wrong_result")

# case -> {oracle: (y, fail_kind | invalid_reason | None)}
EXPECT: dict[str, dict[str, tuple[str, str | None]]] = {
    "plain": {"tlp": PASS, "norec": PASS, "plan_variant": PASS},
    "plain_no_predicate": {"tlp": NA, "norec": NA, "plan_variant": PASS},
    "aggregate": {"tlp": NA, "norec": PASS, "plan_variant": PASS},
    "grouped": {"tlp": PASS, "norec": NA, "plan_variant": PASS},
    "grouped_with_where": {"tlp": PASS, "norec": NA, "plan_variant": PASS},
    "distinct": {"tlp": PASS, "norec": PASS, "plan_variant": PASS},
    # Not a form any oracle can fold the predicate into: the fallback puts the
    # WHERE after GROUP BY, the statement does not parse, the case is a bad test.
    "grouped_with_aggregate": {"tlp": NA, "norec": NA, "plan_variant": QERR},
    "metrics_small": {"tlp": WRONG, "norec": WRONG, "plan_variant": PASS},
    "inv_delim": {"tlp": PASS, "norec": PASS, "plan_variant": WRONG},
    "vd_partial": {"tlp": VD, "norec": PASS, "plan_variant": PASS},
    "vd_grouped": {"tlp": VD, "norec": NA, "plan_variant": PASS},
    "vd_subquery": {"tlp": VD, "norec": VD, "plan_variant": VD},
    "vd_overflow": {"tlp": VD, "norec": VD, "plan_variant": VD},
    "bad_column": {"tlp": QERR, "norec": QERR, "plan_variant": QERR},
    "nondeterministic_random": {"tlp": NONDET, "norec": NONDET, "plan_variant": NONDET},
    "nondeterministic_limit": {"tlp": NONDET, "norec": NONDET, "plan_variant": NONDET},
    "broken_setup": {"tlp": SETUP_ERR, "norec": SETUP_ERR, "plan_variant": SETUP_ERR},
    "recall_F1": {"tlp": NA, "norec": NA, "plan_variant": WRONG},
    "recall_F2": {"tlp": NA, "norec": NA, "plan_variant": WRONG},
    "recall_F7": {"tlp": NA, "norec": NA, "plan_variant": WRONG},
}

# TLP form the adapter must report in label.detail["form"] when it ran.
TLP_FORMS = {
    "plain": "where", "metrics_small": "where", "inv_delim": "where", "vd_partial": "where",
    "vd_subquery": "where", "vd_overflow": "where", "bad_column": "where",
    "grouped": "groupby", "grouped_with_where": "groupby", "vd_grouped": "groupby",
    "distinct": "distinct",
}

# full_query(case): the one statement that determinism screening and plan
# variant work on (predicate folded in before any GROUP BY).
FULL_QUERIES = {
    "plain": "SELECT a, b FROM t WHERE (a > 1)",
    "plain_no_predicate": "SELECT a, b FROM t",
    "grouped": "SELECT b FROM t WHERE (a > 1) GROUP BY b",
    "grouped_with_where": "SELECT b, c FROM t WHERE (b IS NOT NULL) AND (a > 1) GROUP BY b, c",
    "distinct": "SELECT DISTINCT c FROM t WHERE (a > 1)",
    "grouped_with_aggregate": "SELECT b, COUNT(*) FROM t GROUP BY b WHERE (a > 1)",
    "metrics_small": f"SELECT m.m_id, m.k FROM metrics m WHERE ({_NOT_EXISTS}) AND (m.d IS NOT NULL)",
}

# Identity evidence of the known failures: (switches, behavior missing, extra).
IDENTITY = {
    ("metrics_small", "tlp"): ((), 1, 0),
    ("metrics_small", "norec"): ((), 1, 0),
    ("inv_delim", "plan_variant"): (("no_optimizer",), 0, 2),
    ("recall_F1", "plan_variant"): (("no_optimizer",), None, None),
    ("recall_F2", "plan_variant"): (("no_optimizer",), None, None),
    ("recall_F7", "plan_variant"): (("no_optimizer",), None, None),
}
