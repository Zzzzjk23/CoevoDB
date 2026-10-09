"""Builders for the S6 theory tests."""

from __future__ import annotations

from surprise.features.phi import Phi, make_phi
from surprise.harness.contracts import IdentityEvidence, Label
from surprise.theory.contracts import Hypothesis

SELECT = "ast:stmt:select"
EXC_ALL = "ast:set_op:except_all"
INT_ALL = "ast:set_op:intersect_all"
UNI_ALL = "ast:set_op:union_all"
EXC = "ast:set_op:except"
SET_ALL = "ast:set_op:all"
SET_OP = "ast:set_op"
L_DUPS = "data:setop:left_has_dups"
L_NULL = "data:setop:left_has_null"
R_NULL = "data:setop:right_has_null"
D_SETOP = "data:setop"
T_DUPS = "data:table:dup_rows"
T_NULL = "data:table:has_null"
D_TABLE = "data:table"
INT = "data:type:integer"
SRC = "plan:DataSourceExec"
HJ = "plan:HashJoinExec"
UNION_EXEC = "plan:UnionExec"
JOIN = "ast:join:inner"

ALL_OK = {"ast": "ok", "plan": "ok", "data": "ok"}
AST_ONLY = {"ast": "ok", "plan": "skipped", "data": "skipped"}
NO_DATA = {"ast": "ok", "plan": "ok", "data": "unavailable"}
AST_FALLBACK = {"ast": "fallback", "plan": "skipped", "data": "skipped"}

X1 = (EXC_ALL, SELECT, L_DUPS, L_NULL, R_NULL, T_DUPS, T_NULL, INT, SRC, HJ)
X3 = (EXC_ALL, SELECT, L_NULL, R_NULL, T_NULL, INT, SRC, HJ)
X4 = (INT_ALL, SELECT, L_DUPS, L_NULL, R_NULL, T_DUPS, T_NULL, INT, SRC, HJ)
X5 = (UNI_ALL, SELECT, L_DUPS, L_NULL, R_NULL, T_DUPS, T_NULL, INT, SRC, UNION_EXEC)
X6 = (EXC, SELECT, L_DUPS, L_NULL, R_NULL, T_DUPS, T_NULL, INT, SRC, HJ)
X7 = (EXC_ALL, SELECT, L_DUPS, T_DUPS, INT, SRC, HJ)
PLAIN = (SELECT, INT, SRC)
JOINQ = (SELECT, JOIN, T_NULL, INT, SRC, HJ)

S_HAND = tuple(sorted((EXC_ALL, L_DUPS)))
TOP = ((),)


def phi(features, *, engine="datafusion", layers=None) -> Phi:
    return make_phi(engine, features, dict(ALL_OK if layers is None else layers))


def hypothesis(**overrides) -> Hypothesis:
    fields = dict(
        hypothesis_id="h-test",
        engine="datafusion",
        interventions=(),
        plan_delta=(),
        versions={},
        specific=S_HAND,
        general=TOP,
        positives=(),
        negatives=(),
        source="hand-written",
        status="active",
        oracle="cross_dbms",
        fail_kind="wrong_result",
        error_class=None,
        behavior_shape="missing_only",
    )
    fields.update(overrides)
    return Hypothesis(**fields)


def fail_label(*, oracle="cross_dbms", fail_kind="wrong_result", error_class=None,
               behavior=None, switches=(), cve=None) -> Label:
    return Label(
        y="fail",
        oracle=oracle,
        fail_kind=fail_kind,
        identity=IdentityEvidence(
            switches=switches,
            error_class=error_class,
            behavior={} if behavior is None else behavior,
        ),
        cve={} if cve is None else cve,
    )
