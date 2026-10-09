"""MDL merge, tighten, and split candidates, and the fixed point of compress()."""

from __future__ import annotations

from dataclasses import replace

from surprise.theory import Workbench, common_conjunction, reduce_conjunction

from test_surprise_s06_common import (
    EXC_ALL,
    INT_ALL,
    JOINQ,
    L_DUPS,
    S_HAND,
    SELECT,
    T_DUPS,
    UNI_ALL,
    X1,
    X3,
    X4,
    phi,
)
from test_surprise_s07_workbench import (
    ENGINE,
    ORACLE,
    R_DUPS,
    X8,
    bet,
    opened,
    pass_label,
    profiled,
    raw_fail,
    revise,
)

NO_PLAN = (EXC_ALL, SELECT, L_DUPS, T_DUPS, "data:type:integer")
NO_PLAN_LAYERS = {"ast": "ok", "plan": "unavailable", "data": "ok"}
Z_RIGHT = (EXC_ALL, SELECT, R_DUPS, "data:setop:right_has_null", "data:type:integer", "plan:DataSourceExec", "plan:HashJoinExec")
W_UNION = (UNI_ALL, SELECT, L_DUPS, "data:setop:left_has_null", "data:setop:right_has_null", T_DUPS, "data:table:has_null", "data:type:integer", "plan:DataSourceExec", "plan:HashJoinExec")


def test_compress_merges_two_hypotheses_of_one_identity_then_stops(tmp_path):
    wb, first = opened(tmp_path)
    blind = phi(NO_PLAN, layers=NO_PLAN_LAYERS)
    out = wb.observe(blind, profiled(), "r2")
    second = out.observation.opened
    assert second and out.observation.effects == ()
    assert wb.repair_candidates() == ()
    (candidate,) = wb.merge_candidates()
    shared = common_conjunction(wb.theory.get(first).specific, wb.theory.get(second).specific)
    assert candidate.kind == "merge" and candidate.proposer == "mdl" and candidate.trigger == ()
    assert candidate.removes == (first, second)
    assert tuple(candidate.adds[0].specific) == shared
    assert candidate.adds[0].source == "mdl"
    assert first in candidate.rationale and second in candidate.rationale
    verdict = wb.assess(candidate)
    assert verdict.accepted and verdict.delta_in == 0.0 and verdict.delta_out == 0.0
    assert verdict.delta_length is not None and verdict.delta_length < 0
    logged = len(wb.store.edit_history())
    (merged,) = wb.compress()
    assert len(wb.store.edit_history()) == logged + 1
    added = merged.payload["adds"][0]
    stored = wb.theory.get(added)
    assert merged.kind == "merge" and merged.decision == "accepted" and merged.proposer == "mdl"
    assert tuple(hypothesis.hypothesis_id for hypothesis in wb.theory.hypotheses) == (added,)
    assert stored.positives == ("r1", "r2") and tuple(stored.specific) == shared and stored.source == "mdl"
    assert wb.owner_of("r1") == wb.owner_of("r2") == added
    assert wb.partition() == {"r1": f"{ENGINE}|{added}", "r2": f"{ENGINE}|{added}"}
    assert wb.compress() == () and wb.merge_candidates() == () and wb.repair_candidates() == ()
    assert len(wb.store.edit_history()) == logged + 1 and wb.negatives() == ()


def test_a_known_pass_between_two_hypotheses_blocks_the_merge(tmp_path):
    wb, first = opened(tmp_path)
    wb.observe(phi(X3), pass_label(), "r2")
    out = wb.observe(phi(Z_RIGHT), profiled(), "r3")
    second = out.observation.opened
    assert second and (first, "outside") in out.observation.effects
    (candidate,) = wb.merge_candidates()
    verdict = wb.assess(candidate)
    assert candidate.removes == (first, second)
    assert verdict.accepted is False and verdict.reason == "holdout" and verdict.delta_out > 0
    logged = len(wb.store.edit_history())
    assert wb.compress() == ()
    assert len(wb.store.edit_history()) == logged and wb.negatives() == ()
    assert tuple(hypothesis.hypothesis_id for hypothesis in wb.theory.hypotheses) == (first, second)
    assert wb.partition() == {"r1": f"{ENGINE}|{first}", "r3": f"{ENGINE}|{second}"}


def test_repair_builds_a_revise_candidate_and_compress_is_a_fixed_point(tmp_path):
    wb, first = opened(tmp_path)
    edit = wb.propose(revise(wb, first, S_HAND, bets=(bet([EXC_ALL], [L_DUPS], "pass"), bet([INT_ALL, L_DUPS]))))
    current = edit.payload["adds"][0]
    wb.observe(phi(X8), pass_label(), "c0")
    (candidate,) = wb.repair_candidates()
    verdict = wb.assess(candidate)
    assert candidate.kind == "revise" and candidate.proposer == "mdl" and candidate.removes == (current,)
    assert candidate.trigger == ("c0",) and candidate.adds[0].source == "mdl"
    assert tuple(candidate.adds[0].specific) == reduce_conjunction(phi(X1).features)
    assert candidate.bets == (bet(candidate.adds[0].specific),)
    assert verdict.accepted is False and verdict.reason == "no_gain"
    assert verdict.delta_length is not None and verdict.delta_length > 0
    assert verdict.delta_in < 0 and verdict.delta_out == 0.0
    logged = len(wb.store.edit_history())
    assert wb.compress() == () and len(wb.store.edit_history()) == logged and wb.negatives() == ()
    assert wb.compress() == ()


def test_repair_builds_a_split_when_positives_cannot_share_a_conjunction(tmp_path):
    wb, first = opened(tmp_path)
    edit = wb.propose(revise(wb, first, (L_DUPS,), bets=(bet([INT_ALL, L_DUPS]),)))
    current = edit.payload["adds"][0]
    absorbed = wb.observe(phi(X4), raw_fail(attribution=(current, True)), "r2")
    assert absorbed.owner == current and absorbed.bets == ((edit.edit_id, 0, "kept"),)
    wb.observe(phi(W_UNION), pass_label(), "c0")
    (candidate,) = wb.repair_candidates()
    verdict = wb.assess(candidate)
    assert candidate.kind == "split" and candidate.removes == (current,)
    assert [tuple(item.specific) for item in candidate.adds] != [tuple(wb.theory.get(current).specific)]
    assert len(candidate.adds) == 2 and all(item.source == "mdl" for item in candidate.adds)
    assert candidate.trigger == ("c0",) and len(candidate.bets) == 2
    assert verdict.reason == "no_gain" and verdict.delta_in < 0 and verdict.delta_length is not None
    logged = len(wb.store.edit_history())
    assert wb.compress() == () and len(wb.store.edit_history()) == logged and wb.negatives() == ()

    duck = phi(JOINQ, engine="duckdb")
    older = wb.observe(
        duck,
        profiled(
            oracle="plan_variant",
            fix_set=("deliminator", "filter_pushdown"),
            fix_kind="optimizer",
            ladder="recent",
            witness=("no_optimizer",),
            switches=("deliminator", "filter_pushdown"),
        ),
        "d1",
    ).observation.opened
    younger = wb.observe(
        phi((SELECT, "ast:join:inner", "data:table:has_null", "data:type:integer"), engine="duckdb", layers=NO_PLAN_LAYERS),
        replace(
            profiled(
                oracle="plan_variant",
                fix_set=("filter_pushdown", "deliminator"),
                fix_kind="optimizer",
                ladder="recent",
                witness=("no_optimizer",),
                switches=("deliminator", "filter_pushdown"),
            ),
            identity=replace(
                profiled().identity,
                behavior={"missing": 1, "extra": 1},
                switches=("deliminator", "filter_pushdown"),
            ),
        ),
        "d2",
    ).observation.opened
    assert older and younger
    assert wb.theory.get(older).behavior_shape != wb.theory.get(younger).behavior_shape
    assert wb.family_of(older) == wb.family_of(younger)
    (pair,) = [item for item in wb.merge_candidates() if item.removes == (older, younger)]
    assert wb.assess(pair).accepted
    (merged,) = [item for item in wb.compress() if item.kind == "merge"]
    stored = wb.theory.get(merged.payload["adds"][0])
    assert stored.positives == ("d1", "d2") and stored.behavior_shape == "missing_only"
    assert wb.compress() == ()
