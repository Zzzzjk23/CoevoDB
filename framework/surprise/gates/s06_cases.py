"""Tables for the S6 gate (theory T core).

The feature sets under ``PHI`` are the phi of the walk-through cases as measured
on DataFusion 54.0.0 (the ``walkthrough`` group re-extracts them and compares).
Every expected boundary below follows from the rules in the S6 section of
HANDOFF.md; none of it is tied to a family number or to SQL text.
"""
from __future__ import annotations

import itertools

# ---- constants (frozen once S6 closes; change only with the user's consent) ---

CONSTANTS = {
    "P_CONFIRMED": 0.95,            # P(fail | valid) inside the specific boundary S of a hypothesis
    "P_PENDING": 0.5,               # P(fail | valid) between S and G
    "RESIDUAL_PRIOR_FAILS": 1.0,    # rho_c = (unexplained + 1) / (tested + 100): an untested unit fails 1 time in 100
    "RESIDUAL_PRIOR_TESTS": 100.0,
    "VALIDITY_PRIOR_INVALID": 1.0,  # K^v = (invalid + 1) / (tested + 10)
    "VALIDITY_PRIOR_TESTS": 10.0,
    "TRIAGE_LOW_BITS": 0.5,         # below: duplicate / no information
    "TRIAGE_HIGH_BITS": 2.0,        # at or above: new family / unexpected pass
    "VS_MAX_GENERAL": 64,           # cap on the number of conjunctions in G
}

TRIAGE_KINDS = ("new_family", "unexpected_pass", "boundary_move", "duplicate", "no_information", "invalid")
ZONES = ("confirmed", "pending", "unexplored")

# ---- feature ids ---------------------------------------------------------------

SELECT = "ast:stmt:select"
EXC_ALL = "ast:set_op:except_all"
INT_ALL = "ast:set_op:intersect_all"
UNI_ALL = "ast:set_op:union_all"
EXC = "ast:set_op:except"
SET_ALL = "ast:set_op:all"
SET_OP = "ast:set_op"
L_DUPS = "data:setop:left_has_dups"
L_NULL = "data:setop:left_has_null"
R_DUPS = "data:setop:right_has_dups"
R_NULL = "data:setop:right_has_null"
D_SETOP = "data:setop"
T_DUPS = "data:table:dup_rows"
T_NULL = "data:table:has_null"
D_TABLE = "data:table"
INT = "data:type:integer"
SRC = "plan:DataSourceExec"
HJ = "plan:HashJoinExec"
UNION_EXEC = "plan:UnionExec"

ALL_OK = {"ast": "ok", "plan": "ok", "data": "ok"}
AST_ONLY = {"ast": "ok", "plan": "skipped", "data": "skipped"}
NO_DATA = {"ast": "ok", "plan": "ok", "data": "unavailable"}

# name -> leaves of phi. x1 is DF-A, x3 removes the left duplicates, x4 is DF-B, x5 swaps in UNION ALL,
# x6 is the distinct EXCEPT, x7 is DF-A without NULLs, x8 has as many duplicates on the right as on the left.
PHI: dict[str, tuple[str, ...]] = {
    "x1": (EXC_ALL, SELECT, L_DUPS, L_NULL, R_NULL, T_DUPS, T_NULL, INT, SRC, HJ),
    "x3": (EXC_ALL, SELECT, L_NULL, R_NULL, T_NULL, INT, SRC, HJ),
    "x4": (INT_ALL, SELECT, L_DUPS, L_NULL, R_NULL, T_DUPS, T_NULL, INT, SRC, HJ),
    "x5": (UNI_ALL, SELECT, L_DUPS, L_NULL, R_NULL, T_DUPS, T_NULL, INT, SRC, UNION_EXEC),
    "x6": (EXC, SELECT, L_DUPS, L_NULL, R_NULL, T_DUPS, T_NULL, INT, "plan:AggregateExec", SRC, HJ, "plan:RepartitionExec"),
    "x7": (EXC_ALL, SELECT, L_DUPS, T_DUPS, INT, SRC, HJ),
    "x8": (EXC_ALL, SELECT, L_DUPS, R_DUPS, T_DUPS, INT, SRC, HJ),
    "plain": (SELECT, INT, SRC),
    "joinq": (SELECT, "ast:join:inner", T_NULL, INT, SRC, HJ),
}

UNITS = {
    "x1": "datafusion|cross_dbms|set_op_all|join|dups",
    "x3": "datafusion|cross_dbms|set_op_all|join|nulls",
    "x4": "datafusion|cross_dbms|set_op_all|join|dups",
    "x5": "datafusion|cross_dbms|set_op_all|union|dups",
    "x6": "datafusion|cross_dbms|set_op|join|dups",
    "x8": "datafusion|cross_dbms|set_op_all|join|dups",
    "plain": "datafusion|cross_dbms|plain|scan|plain",
}
CLASSES = {"x1": "datafusion|set_op_all", "x6": "datafusion|set_op", "plain": "datafusion|plain"}


def sort_conj(*ids: str) -> tuple[str, ...]:
    return tuple(sorted(ids))


S_X1 = sort_conj(*PHI["x1"])
S_X4 = sort_conj(*PHI["x4"])
S_HAND = sort_conj(EXC_ALL, L_DUPS)   # the hand-written h2: "EXCEPT ALL and the left input has duplicate rows"
TOP = ((),)                           # the most general boundary: one empty conjunction

# ---- the conjunction language ---------------------------------------------------

# (ids, reduced form): sorted, unique, no layer root, no id implied by another one in the set.
REDUCE: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
    ((), ()),
    (("ast", "plan", "data"), ()),
    ((EXC_ALL, SET_ALL, SET_OP, "ast"), (EXC_ALL,)),
    ((L_DUPS, D_SETOP, SET_ALL), (SET_ALL, L_DUPS)),
    ((HJ, "plan"), (HJ,)),
    ((HJ, SRC, HJ, EXC_ALL), (EXC_ALL, SRC, HJ)),
    (("ast:fn:upper", "ast:fn"), ("ast:fn:upper",)),
    ((SET_ALL, "ast:set_op:distinct"), (SET_ALL, "ast:set_op:distinct")),
    ((L_DUPS, L_NULL, D_SETOP), (L_DUPS, L_NULL)),
    (PHI["x1"], S_X1),
]
REDUCE_BAD: list[object] = [("ast:no_such_feature",), ("nope:x",), EXC_ALL, (EXC_ALL, 3), ("ast:fn:",)]

# (conjunction, phi name, covered)
COVERS: list[tuple[tuple[str, ...], str, bool]] = [
    ((), "x1", True),
    ((), "plain", True),
    ((EXC_ALL,), "x1", True),
    ((SET_ALL,), "x1", True),
    ((SET_OP, D_SETOP), "x1", True),
    ((INT_ALL,), "x1", False),
    ((EXC_ALL, L_DUPS), "x3", False),
    ((EXC_ALL, L_DUPS), "x8", True),
    ((SET_ALL, L_DUPS), "x4", True),
    ((SET_ALL,), "x6", False),
    ((SET_OP,), "x6", True),
    ((D_TABLE,), "plain", False),
    ((HJ,), "x5", False),
]

# (specific, positive phi name, generalised specific)
GENERALIZE: list[tuple[tuple[str, ...], str, tuple[str, ...]]] = [
    (S_X1, "x1", S_X1),
    (S_X1, "x7", sort_conj(EXC_ALL, SELECT, L_DUPS, T_DUPS, INT, SRC, HJ)),
    (S_HAND, "x4", sort_conj(SET_ALL, L_DUPS)),                    # a sibling value climbs to the class
    (sort_conj(SET_ALL, L_DUPS), "x6", sort_conj(SET_OP, L_DUPS)),  # and one class further
    (S_HAND, "x3", sort_conj(EXC_ALL, D_SETOP)),                   # another set-operation property: the class remains
    (S_HAND, "plain", ()),
    (S_X1, "x5", sort_conj(SET_ALL, SELECT, L_DUPS, L_NULL, R_NULL, T_DUPS, T_NULL, INT, SRC)),
    ((), "x1", ()),
]

# (general, specific, negative phi name, specialised general). The negative is never covered by `specific`.
SPECIALIZE: list[tuple[tuple[tuple[str, ...], ...], tuple[str, ...], str, tuple[tuple[str, ...], ...]]] = [
    (TOP, S_HAND, "x3", ((L_DUPS,),)),
    (((L_DUPS,),), S_HAND, "x4", (sort_conj(EXC_ALL, L_DUPS),)),
    (TOP, S_X1, "x3", ((L_DUPS,), (T_DUPS,))),
    (((L_DUPS,), (T_DUPS,)), S_X1, "x4", (sort_conj(EXC_ALL, L_DUPS), sort_conj(EXC_ALL, T_DUPS))),
    # the most general excluding ancestor is taken, not the leaf
    (TOP, S_X1, "plain", ((SET_OP,), (D_SETOP,), (D_TABLE,), (HJ,))),
    (((SET_OP,), (D_SETOP,), (D_TABLE,), (HJ,)), S_X1, "joinq", ((SET_OP,), (D_SETOP,), (T_DUPS,))),
    (((SET_OP,), (D_SETOP,), (T_DUPS,)), S_X1, "x6", ((SET_ALL,),)),
    (((SET_ALL,),), S_X1, "x5", ((EXC_ALL,), sort_conj(SET_ALL, HJ))),
    (((EXC_ALL,), sort_conj(SET_ALL, HJ)), S_X1, "x3",
     (sort_conj(EXC_ALL, L_DUPS), sort_conj(EXC_ALL, T_DUPS), sort_conj(SET_ALL, L_DUPS, HJ), sort_conj(SET_ALL, T_DUPS, HJ))),
    ((sort_conj(EXC_ALL, L_DUPS), sort_conj(EXC_ALL, T_DUPS), sort_conj(SET_ALL, L_DUPS, HJ), sort_conj(SET_ALL, T_DUPS, HJ)),
     S_X1, "x4", (sort_conj(EXC_ALL, L_DUPS), sort_conj(EXC_ALL, T_DUPS))),
    # a member that already excludes the negative stays as it is
    (((INT_ALL,), (L_DUPS,), (T_DUPS,)), S_X4, "x1", ((INT_ALL,),)),
    (((EXC_ALL,),), S_X1, "x4", ((EXC_ALL,),)),
]

# ---- version-space sequences ------------------------------------------------------

# name -> (specific, general, steps). A step is (kind, phi name, outcome, specific after, general after);
# kind "+" applies a positive example, "-" a negative one. The record id of step i (from 1) is "r<i>".
SEQUENCES: dict[str, tuple[tuple[str, ...], tuple[tuple[str, ...], ...], list[tuple]]] = {
    "hand_written_h2": (S_HAND, TOP, [
        ("-", "x3", "specialized", S_HAND, ((L_DUPS,),)),
        ("-", "x4", "specialized", S_HAND, (S_HAND,)),
        ("-", "x8", "contradiction", S_HAND, (S_HAND,)),
        ("+", "x1", "duplicate", S_HAND, (S_HAND,)),
        ("+", "x7", "duplicate", S_HAND, (S_HAND,)),
        ("-", "plain", "outside", S_HAND, (S_HAND,)),
        ("+", "x4", "outside", S_HAND, (S_HAND,)),
    ]),
    "deterministic_h": (S_X1, TOP, [
        ("-", "x3", "specialized", S_X1, ((L_DUPS,), (T_DUPS,))),
        ("-", "x4", "specialized", S_X1, (sort_conj(EXC_ALL, L_DUPS), sort_conj(EXC_ALL, T_DUPS))),
        ("+", "x7", "generalized", sort_conj(EXC_ALL, SELECT, L_DUPS, T_DUPS, INT, SRC, HJ),
         (sort_conj(EXC_ALL, L_DUPS), sort_conj(EXC_ALL, T_DUPS))),
        ("+", "x1", "duplicate", sort_conj(EXC_ALL, SELECT, L_DUPS, T_DUPS, INT, SRC, HJ),
         (sort_conj(EXC_ALL, L_DUPS), sort_conj(EXC_ALL, T_DUPS))),
        ("-", "x8", "contradiction", sort_conj(EXC_ALL, SELECT, L_DUPS, T_DUPS, INT, SRC, HJ),
         (sort_conj(EXC_ALL, L_DUPS), sort_conj(EXC_ALL, T_DUPS))),
    ]),
    "class_climb": (S_HAND, TOP, [
        ("+", "x4", "generalized", sort_conj(SET_ALL, L_DUPS), TOP),
        ("+", "x6", "generalized", sort_conj(SET_OP, L_DUPS), TOP),
        ("-", "x3", "specialized", sort_conj(SET_OP, L_DUPS), ((L_DUPS,),)),
        ("-", "plain", "outside", sort_conj(SET_OP, L_DUPS), ((L_DUPS,),)),
        ("-", "x5", "contradiction", sort_conj(SET_OP, L_DUPS), ((L_DUPS,),)),
    ]),
    "carved_by_passes": (S_X1, TOP, [
        ("-", "plain", "specialized", S_X1, ((SET_OP,), (D_SETOP,), (D_TABLE,), (HJ,))),
        ("-", "joinq", "specialized", S_X1, ((SET_OP,), (D_SETOP,), (T_DUPS,))),
        ("-", "x6", "specialized", S_X1, ((SET_ALL,),)),
        ("-", "x5", "specialized", S_X1, ((EXC_ALL,), sort_conj(SET_ALL, HJ))),
        ("-", "x3", "specialized", S_X1,
         (sort_conj(EXC_ALL, L_DUPS), sort_conj(EXC_ALL, T_DUPS), sort_conj(SET_ALL, L_DUPS, HJ),
          sort_conj(SET_ALL, T_DUPS, HJ))),
        ("-", "x4", "specialized", S_X1, (sort_conj(EXC_ALL, L_DUPS), sort_conj(EXC_ALL, T_DUPS))),
        ("-", "plain", "outside", S_X1, (sort_conj(EXC_ALL, L_DUPS), sort_conj(EXC_ALL, T_DUPS))),
    ]),
    "positive_drops_a_branch": (S_X1, ((L_DUPS,), (T_NULL,), (HJ,)), [
        # x7 has no NULL: the member that needs one cannot be right any more
        ("+", "x7", "generalized", sort_conj(EXC_ALL, SELECT, L_DUPS, T_DUPS, INT, SRC, HJ), ((L_DUPS,), (HJ,))),
    ]),
}

# The cap on G: 14 unrelated literals, 7 passes that each lack one pair of them.
CAP_LEAVES = tuple(f"plan:P{index:02d}" for index in range(1, 15))
CAP_NEGATIVES = [tuple(leaf for leaf in CAP_LEAVES if leaf not in CAP_LEAVES[2 * i:2 * i + 2]) for i in range(7)]


def cap_general(negatives: int, keep: int | None = None) -> tuple[tuple[str, ...], ...]:
    """G after that many of ``CAP_NEGATIVES``: one literal of each pair, in canonical order."""
    members = sorted(tuple(sorted(choice)) for choice in
                     itertools.product(*(CAP_LEAVES[2 * i:2 * i + 2] for i in range(negatives))))
    return tuple(members if keep is None else members[:keep])


# ---- identity -----------------------------------------------------------------------

# Evidence a tier-3 profile carries, by name.
PROFILES = {
    "df_missing": dict(fix_set=(), plan_diff=(), ladder="longstanding", fix_kind="non_optimizer", witness=()),
    "df_extra": dict(fix_set=(), plan_diff=(), ladder="longstanding", fix_kind="non_optimizer", witness=()),
    "f1": dict(fix_set=("deliminator", "filter_pushdown"), plan_diff=("-DELIM_JOIN", "+HASH_JOIN"), ladder="recent",
               fix_kind="optimizer", witness=("no_optimizer",)),
    "f9": dict(fix_set=(), plan_diff=("-WINDOW",), ladder="unknown", fix_kind="unresolved", witness=("window_combine",)),
}

# name -> how to build a fail label: (oracle, fail_kind, error_class, behavior, switches, profile name or None)
FAILS = {
    "df_missing": ("cross_dbms", "wrong_result", None, {"missing": 3, "extra": 0}, (), "df_missing"),
    "df_missing_raw": ("cross_dbms", "wrong_result", None, {"missing": 1, "extra": 0}, (), None),
    "df_extra": ("cross_dbms", "wrong_result", None, {"missing": 0, "extra": 3}, (), "df_extra"),
    "df_both": ("cross_dbms", "wrong_result", None, {"missing": 2, "extra": 2}, (), None),
    "df_crash": ("cross_dbms", "crash", "ProcessExit", {"exit_code": 3221225620}, (), None),
    "f1": ("plan_variant", "wrong_result", None, {"missing": 1, "extra": 0}, ("deliminator", "filter_pushdown"), "f1"),
    "f1_raw": ("plan_variant", "wrong_result", None, {"missing": 1, "extra": 0}, ("no_optimizer",), None),
    "f9": ("plan_variant", "wrong_result", None, {"missing": 8, "extra": 8}, ("window_combine",), "f9"),
    "internal": ("plan_variant", "crash", "InternalException", {}, ("no_optimizer",), None),
}

# name -> identity of a hand-made hypothesis: (interventions, fail_kind, error_class, behavior_shape)
IDENTITIES = {
    "h_missing": ((), "wrong_result", None, "missing_only"),
    "h_extra": ((), "wrong_result", None, "extra_only"),
    "h_crash": ((), "crash", "ProcessExit", "none"),
    "h_f1": (("filter_pushdown", "deliminator"), "wrong_result", None, "missing_only"),
}

# (identity name, fail name, attribution on the label or None, expected). An attribution is
# (hypothesis id, consistent); the hypothesis under test always has the id "h-test".
IDENTITY: list[tuple[str, str, tuple[str, bool] | None, bool | None]] = [
    ("h_missing", "df_missing", None, True),
    ("h_missing", "df_missing_raw", None, True),         # the three fields need no profile
    ("h_missing", "df_extra", None, False),
    ("h_missing", "df_both", None, False),
    ("h_missing", "df_crash", None, False),
    ("h_extra", "df_extra", None, True),
    ("h_crash", "df_crash", None, True),
    ("h_crash", "internal", None, False),                # another error class
    ("h_missing", "df_extra", ("h-test", True), True),   # the harness test of this hypothesis decides
    ("h_missing", "df_missing", ("h-test", False), False),
    ("h_missing", "df_extra", ("h-other", True), False),  # a test of another hypothesis says nothing here
    ("h_f1", "f1", None, True),                          # same fix set, any order
    ("h_f1", "f9", None, False),                         # profiled, another fix set
    ("h_f1", "f1_raw", None, None),                      # no profile, no test of this hypothesis: unknown
    ("h_f1", "f1_raw", ("h-test", True), True),
    ("h_f1", "f1", ("h-test", False), False),
    ("h_f1", "f1_raw", ("h-other", True), None),
]

# ---- triage ----------------------------------------------------------------------------

# (y, bits, kind)
TRIAGE: list[tuple[str, float | None, str]] = [
    ("fail", 6.6439, "new_family"),
    ("pass", 4.3219, "unexpected_pass"),
    ("fail", 1.0, "boundary_move"),
    ("pass", 1.0, "boundary_move"),
    ("fail", 0.074, "duplicate"),
    ("pass", 0.0145, "no_information"),
    ("invalid", None, "invalid"),
    ("fail", 2.0, "new_family"),          # the thresholds belong to the higher band
    ("pass", 2.0, "unexpected_pass"),
    ("fail", 1.9999, "boundary_move"),
    ("pass", 0.5, "boundary_move"),
    ("fail", 0.4999, "duplicate"),
    ("pass", 0.0, "no_information"),
    ("fail", 40.0, "new_family"),
]
TRIAGE_BAD: list[tuple[object, object]] = [("invalid", 1.0), ("pass", None), ("fail", -0.1), ("fail", float("nan")),
                                          ("fail", float("inf")), ("maybe", 1.0), ("pass", "1.0"), ("pass", True)]

# (zone, y) -> kind, with the residual at its prior. This is the table of the framework document.
DOCUMENT_TABLE = {
    ("unexplored", "fail"): ("new_family", 6.6439),
    ("confirmed", "pass"): ("unexpected_pass", 4.3219),
    ("pending", "fail"): ("boundary_move", 1.0),
    ("pending", "pass"): ("boundary_move", 1.0),
    ("confirmed", "fail"): ("duplicate", 0.0740),
    ("unexplored", "pass"): ("no_information", 0.0145),
}

# ---- the DF-A -> DF-B walk-through on real engines -------------------------------------

T_TABLE = "CREATE TABLE t(v INT)"
U_TABLE = "CREATE TABLE u(v INT)"
U_ROWS = "INSERT INTO u VALUES (1),(2),(NULL)"
DUP_ROWS = "INSERT INTO t VALUES (1),(1),(2),(2),(2),(NULL)"
SQL = {
    "x1": ((T_TABLE, DUP_ROWS, U_TABLE, U_ROWS), "SELECT v FROM t EXCEPT ALL SELECT v FROM u"),
    "x3": ((T_TABLE, "INSERT INTO t VALUES (1),(2),(NULL)", U_TABLE, U_ROWS), "SELECT v FROM t EXCEPT ALL SELECT v FROM u"),
    "x4": ((T_TABLE, DUP_ROWS, U_TABLE, U_ROWS), "SELECT v FROM t INTERSECT ALL SELECT v FROM u"),
    "x5": ((T_TABLE, DUP_ROWS, U_TABLE, U_ROWS), "SELECT v FROM t UNION ALL SELECT v FROM u"),
    "x8": ((T_TABLE, "INSERT INTO t VALUES (1),(1)", U_TABLE, "INSERT INTO u VALUES (1),(1)"),
           "SELECT v FROM t EXCEPT ALL SELECT v FROM u"),
}
