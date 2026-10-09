"""Fixed cases for the S7 gate (data only; ``gates/all.py`` does not run this file).

The real-engine part replays known reproductions and regenerated DCE probes
(``evolution/dce.py``). Everything here was measured on this machine before
dispatch: DuckDB 1.5.5 / 1.1.3, DataFusion 54.0.0 / 50.0.0, PostgreSQL 16.15.

``recall:<F>`` and the ``S4:`` references mean "take the case of that name from
``gates/s04_cases.py``", which reads docs/recall_repros.json where needed.
"""
from __future__ import annotations

from . import s04_cases as C4

# ---- constants S7 adds (PLAN decision 8: written into the manifest) --------------

CONSTANTS = {
    "MDL_HYPOTHESIS_BITS": 8.0,
    "MDL_LITERAL_BITS": 7.4,
    "ACCEPT_HOLDOUT_MAX": 1000,
    "ACCEPT_TOLERANCE_BITS": 1e-9,
}

EDIT_KINDS = ("add", "revise", "split", "merge", "retire")
REJECT_REASONS = ("negative_memory", "no_bets", "trigger", "holdout", "no_gain")
ROLLBACK_REASONS = ("bet_broken", "manual", "cascade")
BET_STATES = ("open", "kept", "broken", "void")

# ---- the manual ledger: adjudicated reproductions --------------------------------
#
# One row per statement the manual ledger (docs/FAMILY_LEDGER_155.md, docs/manual_findings.jsonl,
# the duckdb/*.sql and datafusion/*.sql files) assigns to a family. A row is
# (tag, manual family, source, query, oracle); ``source`` is an S4 case name, whose setup is reused,
# and ``query`` replaces that case's query when it is not None. Where a variant comes from:
#
#   F1_file      duckdb/F1_correlated_exists_delim.sql, the canonical two-EXISTS statement
#   F2_file      duckdb/F2_window_dup_partition.sql, first statement
#   F7_file      duckdb/F7_interval_cse.sql
#   F7_minus     the same file and the ledger: "Also fires for d - INTERVAL"
#   F9_distinct  FAMILY_LEDGER_155.md, F9: SELECT DISTINCT x, COUNT(*) OVER () FROM t
#   F11_update   duckdb/F11_merge_nmbs_rowid.sql: "Also fires with WHEN NOT MATCHED BY SOURCE THEN UPDATE"
#   DF-A_chain   datafusion/DF-A_except_all.sql: "Chained EXCEPT ALL collapses the same way"
#   DF-D_where   datafusion/DF-D_generated_column.sql: "SELECT b FROM t WHERE b > 0 -> empty"
#   DF-F_*       datafusion/DF-F_using_key_coalesce.sql: "Same defect on NATURAL JOIN and FULL JOIN"
#   DF-I_*       datafusion/DF-I_all_subquery.sql: "All six comparison ops reproduce"
#
# Left out on purpose: F6 (the witness data is not in the repository; the rebuilt case is F1's
# mechanism by S4's own measurement), F3 / F5 / F8 / F10 and DF-E / DF-G / DF-H / DF-J (not fail
# under the frozen harness, see HANDOFF "recall gaps"), F9's PARTITION BY form (passes here).
F1_FILE_QUERY = (
    "SELECT EXISTS (SELECT 1 FROM issue23979_s2 x WHERE x.o = l.o AND r.wh <> x.wh) AS correlated_exists, "
    "EXISTS (SELECT 1 FROM issue23979_s2 x WHERE x.o = l.o AND (r.wh + 0) <> x.wh) AS equivalent_rewrite "
    "FROM issue23979_l l LEFT JOIN issue23979_r r USING (o) JOIN issue23979_s2 s2 USING (o) ORDER BY l.o")

ADJUDICATED: list[tuple[str, str, str, str | None, str]] = [
    ("F1", "F1", "F1", None, "plan_variant"),
    ("F1_file", "F1", "F1", F1_FILE_QUERY, "plan_variant"),
    ("F2", "F2", "F2", None, "plan_variant"),
    ("F2_file", "F2", "F2_file", None, "plan_variant"),
    ("F7", "F7", "F7", None, "plan_variant"),
    ("F7_file", "F7", "F7_file", None, "plan_variant"),
    ("F7_minus", "F7", "F7_file",
     "SELECT d - INTERVAL '1 month' AS a, d - INTERVAL '30 days' AS b FROM t ORDER BY d", "plan_variant"),
    ("F9", "F9", "F9", None, "plan_variant"),
    ("F9_distinct", "F9", "F9", "SELECT DISTINCT x, COUNT(*) OVER () FROM t", "plan_variant"),
    ("F11", "F11", "F11", None, "plan_variant"),
    ("F11_update", "F11", "F11",
     "MERGE INTO t USING s ON t.a = s.a WHEN NOT MATCHED BY SOURCE THEN UPDATE SET b = 0", "plan_variant"),
    ("DF-A", "DF-A", "DF-A", None, "cross_dbms"),
    ("DF-A_chain", "DF-A", "DF-A",
     "SELECT v FROM t EXCEPT ALL SELECT v FROM u EXCEPT ALL SELECT v FROM u", "cross_dbms"),
    ("DF-B", "DF-B", "DF-B", None, "cross_dbms"),
    ("DF-D", "DF-D", "DF-D", None, "cross_dbms"),
    ("DF-D_where", "DF-D", "DF-D", "SELECT a FROM t WHERE b > 0 ORDER BY a", "cross_dbms"),
    ("DF-F", "DF-F", "DF-F", None, "cross_dbms"),
    ("DF-F_natural", "DF-F", "DF-F", "SELECT * FROM a NATURAL RIGHT JOIN b", "cross_dbms"),
    ("DF-F_full", "DF-F", "DF-F", "SELECT * FROM a FULL JOIN b USING (x)", "cross_dbms"),
    ("DF-F_natfull", "DF-F", "DF-F", "SELECT * FROM a NATURAL FULL JOIN b", "cross_dbms"),
    ("DF-I", "DF-I", "DF-I", None, "cross_dbms"),
    ("DF-I_ge", "DF-I", "DF-I", "SELECT a FROM t WHERE b >= ALL (SELECT w FROM u)", "cross_dbms"),
    ("DF-I_lt", "DF-I", "DF-I", "SELECT a FROM t WHERE b < ALL (SELECT w FROM u)", "cross_dbms"),
    ("DF-I_ne", "DF-I", "DF-I", "SELECT a FROM t WHERE b <> ALL (SELECT w FROM u)", "cross_dbms"),
]

# The order families are fed in, and how many regenerated DCE probes follow each family's first case.
# DataFusion verdicts cost about three times a DuckDB one (three reference engines, fresh processes).
REPLAY_ORDER = ("F1", "F2", "F7", "F9", "F11", "DF-A", "DF-B", "DF-D", "DF-F", "DF-I")
PROBES = {"F1": 6, "F2": 6, "F7": 4, "F9": 6, "F11": 4, "DF-A": 3, "DF-B": 2, "DF-D": 2, "DF-F": 3, "DF-I": 2}

# The five magnitudes of the framework document, as (zone, y) -> (triage kind, lowest, highest) in bits.
# The unexplored rows move a little with the residual counts: rho = (u + 1) / (n + 100).
MAGNITUDES = {
    ("unexplored", "fail"): ("new_family", 5.0, 7.5),
    ("confirmed", "pass"): ("unexpected_pass", 4.3, 4.4),
    ("pending", "fail"): ("boundary_move", 0.99, 1.01),
    ("pending", "pass"): ("boundary_move", 0.99, 1.01),
    ("confirmed", "fail"): ("duplicate", 0.07, 0.08),
    ("unexplored", "pass"): ("no_information", 0.0, 0.03),
}

# sigma, the family key of the old system (diagnosis/signature.py), as recorded by the manual ledger
# for two of the statements above: manual_findings.jsonl lists both keys as separate AUTO- entries
# of the one window_combine mechanism. The gate recomputes them from the CVE profile.
SIGMA_KNOWN = {"F9": "f50fc0f3", "F9_distinct": "13f4608a"}

S4_CASES = C4.CASES
