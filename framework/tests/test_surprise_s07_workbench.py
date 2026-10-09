"""Acceptance, bets, rollback, journal, ownership, and surprise by generation."""

from __future__ import annotations

import shutil
from dataclasses import replace

import pytest

from surprise.harness.contracts import IdentityEvidence, Label
from surprise.theory import (
    Proposal,
    Spec,
    StoreError,
    Theory,
    TheoryEdit,
    Workbench,
    surprise_bits,
    theory_length,
)
from surprise.theory.constants import MDL_LITERAL_BITS, P_CONFIRMED, P_PENDING

from test_surprise_s06_common import (
    EXC_ALL,
    INT_ALL,
    JOIN,
    JOINQ,
    L_DUPS,
    PLAIN,
    S_HAND,
    SELECT,
    SET_ALL,
    T_DUPS,
    UNI_ALL,
    X1,
    X3,
    X4,
    X5,
    X6,
    phi,
)

ENGINE = "datafusion"
ORACLE = "cross_dbms"
R_DUPS = "data:setop:right_has_dups"
X8 = (EXC_ALL, SELECT, L_DUPS, R_DUPS, T_DUPS, "data:type:integer", "plan:DataSourceExec", "plan:HashJoinExec")
PAYLOAD_KEYS = {
    "reason",
    "fingerprint",
    "trigger",
    "holdout",
    "length_delta",
    "removes",
    "removed",
    "adds",
    "added",
    "generation",
    "journal_seq",
    "bets_state",
    "rollback",
}


def pass_label(oracle: str = ORACLE) -> Label:
    return Label(y="pass", oracle=oracle)


def invalid_label() -> Label:
    return Label(y="invalid", oracle=ORACLE, invalid_reason="query_error")


def profiled(
    behavior: dict | None = None,
    *,
    oracle: str = ORACLE,
    fail_kind: str = "wrong_result",
    fix_set: tuple[str, ...] = (),
    plan_diff: tuple[str, ...] = (),
    ladder: str = "longstanding",
    fix_kind: str = "non_optimizer",
    witness: tuple[str, ...] = (),
    switches: tuple[str, ...] = (),
    attribution: tuple[str, bool] | None = None,
) -> Label:
    """A tier-3 failure. ``attribution`` replaces the skipped attribution block."""
    skipped = {"status": "skipped", "reason": "not_requested"}
    cve: dict = {
        "schema": 1,
        "attribution": dict(skipped),
        "profile": {
            "status": "ran",
            "reason": None,
            "fix_kind": fix_kind,
            "fix_set": list(fix_set),
            "plan_diff": list(plan_diff),
            "version_ladder": ladder,
            "witness_switches": list(witness),
        },
    }
    if attribution is not None:
        cve["attribution"] = {
            "status": "ran",
            "reason": None,
            "hypothesis_id": attribution[0],
            "method": "profile",
            "consistent": attribution[1],
            "executions": 0,
        }
    return Label(
        y="fail",
        oracle=oracle,
        fail_kind=fail_kind,
        identity=IdentityEvidence(
            switches=switches,
            error_class=None,
            behavior={"missing": 1} if behavior is None else behavior,
        ),
        cve=cve,
    )


def raw_fail(
    attribution: tuple[str, bool] | None = None,
    behavior: dict | None = None,
    *,
    oracle: str = ORACLE,
    switches: tuple[str, ...] = (),
) -> Label:
    """A failure with no profile. It does not open a family by itself."""
    skipped = {"status": "skipped", "reason": "not_requested"}
    cve: dict = {"attribution": dict(skipped), "profile": dict(skipped)}
    if attribution is not None:
        cve["attribution"] = {
            "status": "ran",
            "reason": None,
            "hypothesis_id": attribution[0],
            "method": "profile",
            "consistent": attribution[1],
            "executions": 0,
        }
    return Label(
        y="fail",
        oracle=oracle,
        fail_kind="wrong_result",
        identity=IdentityEvidence(
            switches=switches,
            error_class=None,
            behavior={"missing": 1} if behavior is None else behavior,
        ),
        cve=cve,
    )


def bet(required, forbidden=(), expect="fail", *, engine=ENGINE, oracle=ORACLE):
    return {
        "spec": Spec(
            engine=engine,
            oracle=oracle,
            required=tuple(required),
            forbidden=tuple(forbidden),
        ).to_dict(),
        "expect": expect,
    }


def revise(wb: Workbench, hypothesis_id: str, specific, bets=(), **overrides) -> Proposal:
    template = replace(
        wb.theory.get(hypothesis_id),
        specific=tuple(specific),
        source="hand-written",
    )
    fields = dict(
        kind="revise",
        rationale="why this edit",
        proposer="hand",
        removes=(hypothesis_id,),
        adds=(template,),
        bets=tuple(bets),
        trigger=("r1",),
    )
    fields.update(overrides)
    return Proposal(**fields)


def opened(tmp_path, name: str = "store") -> tuple[Workbench, str]:
    wb = Workbench.create(tmp_path / name)
    out = wb.observe(phi(X1), profiled(), "r1")
    assert out.observation.opened
    assert out.owner == out.observation.opened
    return wb, out.observation.opened


def _state(wb: Workbench) -> dict:
    return {
        "theory": wb.theory.to_dict(),
        "edits": [edit.to_dict() for edit in wb.edits()],
        "negatives": list(wb.negatives()),
        "partition": wb.partition(),
        "bets": [list(item) for item in wb.open_bets()],
        "generation": wb.generation,
        "records": [(seen.record_id, seen.phi.to_dict(), seen.label.to_dict()) for seen in wb.records()],
    }


def test_shorter_revision_is_accepted_and_assess_changes_nothing(tmp_path):
    wb, first = opened(tmp_path)
    before = wb.theory.to_dict()
    version = wb.theory.version
    proposal = revise(wb, first, S_HAND, bets=(bet([EXC_ALL], [L_DUPS], "pass"), bet([INT_ALL, L_DUPS])))
    verdict = wb.assess(proposal)
    assert verdict.accepted is True and verdict.reason is None
    assert verdict.delta_in == 0.0 and verdict.delta_out == 0.0
    assert verdict.delta_length == pytest.approx(-8 * MDL_LITERAL_BITS)
    assert verdict.holdout == ()
    assert wb.theory.to_dict() == before and wb.edits() == () and wb.negatives() == ()
    assert wb.generation == 0 and wb.theory.next_id == before["next_id"]

    edit = wb.propose(proposal)
    added = edit.payload["adds"][0]
    stored = wb.theory.get(added)
    assert edit.edit_id == "e1" and edit.decision == "accepted" and edit.proposer == "hand"
    assert edit.theory_version == version
    assert edit.surprise_delta_in == 0.0 and edit.surprise_delta_out == 0.0
    assert edit == wb.edit("e1") == TheoryEdit.from_dict(edit.to_dict())
    assert set(edit.payload) == PAYLOAD_KEYS
    assert edit.payload["reason"] is None and edit.payload["removes"] == [first]
    assert edit.payload["removed"] == [before["hypotheses"][0]]
    assert edit.payload["adds"] == [added] and edit.payload["added"] == [stored.to_dict()]
    assert edit.payload["trigger"] == ["r1"] and edit.payload["holdout"] == 0
    assert edit.payload["length_delta"] == pytest.approx(-8 * MDL_LITERAL_BITS)
    assert edit.payload["generation"] == 0 and edit.payload["journal_seq"] == 2
    assert edit.payload["rollback"] is None
    assert edit.payload["bets_state"] == [{"status": "open", "record_id": None}] * 2
    assert edit.payload["fingerprint"] == verdict.fingerprint
    assert tuple(stored.specific) == S_HAND and stored.positives == ("r1",)
    assert stored.hypothesis_id != first and wb.theory.next_id == before["next_id"] + 1
    assert theory_length(wb.theory) - theory_length(Theory.from_dict(before)) == pytest.approx(verdict.delta_length)
    assert wb.generation == 1 and wb.store.load().to_dict() == wb.theory.to_dict()
    journal = wb.store.journal()
    assert [entry["kind"] for entry in journal] == ["observe", "edit"]
    assert set(journal[0]) == {"kind", "seq", "record_id", "phi", "label"}
    assert set(journal[1]) == {"kind", "seq", "edit_id", "generation"}
    assert journal[1]["edit_id"] == "e1" and journal[1]["generation"] == 0
    assert wb.open_bets() == (("e1", 0, proposal.bets[0]), ("e1", 1, proposal.bets[1]))


def test_each_refusal_leaves_the_theory_and_the_id_counter_alone(tmp_path):
    wb, first = opened(tmp_path)
    accepted = wb.propose(revise(wb, first, S_HAND, bets=(bet(S_HAND),)))
    current = accepted.payload["adds"][0]
    wb.observe(phi(X3), pass_label(), "r2")
    state = wb.theory.to_dict()
    counter = wb.theory.next_id
    generation = wb.generation
    remembered = len(wb.negatives())

    held = revise(wb, current, (SET_ALL,), bets=(bet([SET_ALL]),))
    verdict = wb.assess(held)
    assert verdict.accepted is False and verdict.reason == "holdout"
    assert verdict.delta_in == 0.0
    assert verdict.delta_out == pytest.approx(surprise_bits(P_CONFIRMED, "pass") - surprise_bits(0.01, "pass"))
    assert verdict.delta_length == pytest.approx(-MDL_LITERAL_BITS)
    assert verdict.holdout == ("r2",)
    refused = wb.propose(held)
    assert refused.decision == "rolled_back" and refused.payload["reason"] == "holdout"
    assert refused.surprise_delta_in == 0.0
    assert refused.surprise_delta_out == pytest.approx(verdict.delta_out)
    assert refused.payload["holdout"] == 1 and refused.payload["adds"] == []
    assert refused.payload["generation"] is None and refused.payload["journal_seq"] is None
    assert refused.payload["length_delta"] == pytest.approx(verdict.delta_length)
    assert refused.payload["bets_state"] == [{"status": "void", "record_id": None}]
    assert wb.theory.to_dict() == state and wb.theory.next_id == counter and wb.generation == generation
    assert wb.store.load().to_dict() == state
    assert len(wb.negatives()) == remembered + 1
    memory = wb.negatives()[-1]
    assert memory["fingerprint"] == refused.payload["fingerprint"] and memory["edit_id"] == refused.edit_id
    assert memory["reason"] == "holdout" and memory["record_id"] is None and memory["kind"] == "revise"

    again = Proposal(
        kind="add",
        rationale="same claim, other clothes",
        proposer="llm",
        adds=(replace(wb.theory.get(current), specific=(SET_ALL,), source="hand-written"),),
        bets=(bet([SET_ALL]),),
    )
    memorised = wb.propose(again)
    assert memorised.payload["reason"] == "negative_memory"
    assert memorised.surprise_delta_in is None and memorised.surprise_delta_out is None
    assert memorised.payload["length_delta"] is None and memorised.payload["holdout"] == 0
    assert len(wb.negatives()) == remembered + 1
    assert wb.theory.next_id == counter and wb.theory.to_dict() == state

    triggered = wb.propose(revise(wb, current, (INT_ALL, L_DUPS), bets=(bet([INT_ALL, L_DUPS]),)))
    assert triggered.payload["reason"] == "trigger"
    assert triggered.surprise_delta_in == pytest.approx(
        surprise_bits(P_PENDING, "fail") - surprise_bits(P_CONFIRMED, "fail")
    )
    assert triggered.surprise_delta_in > 0.9
    assert triggered.surprise_delta_out == 0.0
    assert triggered.payload["length_delta"] == pytest.approx(0.0)
    assert wb.negatives()[-1]["edit_id"] == triggered.edit_id and wb.negatives()[-1]["reason"] == "trigger"
    assert wb.theory.to_dict() == state and wb.theory.next_id == counter

    same_trigger = Proposal(
        kind="add",
        rationale="the trigger claim again",
        proposer="other",
        adds=(replace(wb.theory.get(current), specific=(INT_ALL, L_DUPS), source="llm"),),
        bets=(bet([INT_ALL, L_DUPS]),),
    )
    assert wb.propose(same_trigger).payload["reason"] == "negative_memory"
    assert len(wb.negatives()) == remembered + 2

    sideways = wb.propose(revise(wb, current, (EXC_ALL, T_DUPS), bets=(bet([EXC_ALL, T_DUPS]),)))
    assert sideways.payload["reason"] == "no_gain"
    assert sideways.surprise_delta_in == 0.0 and sideways.surprise_delta_out == 0.0
    assert sideways.payload["length_delta"] == pytest.approx(0.0)
    assert len(wb.negatives()) == remembered + 2

    unbet = wb.propose(revise(wb, current, (L_DUPS,)))
    assert unbet.payload["reason"] == "no_bets"
    assert unbet.surprise_delta_in is None and unbet.surprise_delta_out is None
    assert unbet.payload["length_delta"] is None and unbet.payload["bets_state"] == []
    assert len(wb.negatives()) == remembered + 2
    assert [edit.edit_id for edit in wb.edits()] == ["e1", "e2", "e3", "e4", "e5", "e6", "e7"]
    assert wb.theory.to_dict() == state and wb.theory.next_id == counter
    assert wb.store.load().to_dict() == state


def test_misuse_raises_and_leaves_no_edit(tmp_path):
    wb, first = opened(tmp_path)
    edit = wb.propose(revise(wb, first, S_HAND, bets=(bet(S_HAND),)))
    current = edit.payload["adds"][0]
    wb.observe(phi(PLAIN), invalid_label(), "r-invalid")
    logged = len(wb.edits())
    state = wb.theory.to_dict()
    counter = wb.theory.next_id
    template = replace(wb.theory.get(current), specific=(L_DUPS,), source="hand-written")
    base = dict(kind="revise", rationale="x", proposer="hand", removes=(current,), adds=(template,), bets=(bet([L_DUPS]),))
    cases = [
        (KeyError, dict(removes=("h-none",))),
        (ValueError, dict(trigger=("r-none",))),
        (ValueError, dict(trigger=("r-invalid",))),
        (ValueError, dict(adds=(replace(template, oracle="tlp"),))),
        (ValueError, dict(adds=(replace(template, specific=("ast", "data")),))),
    ]
    for error, change in cases:
        with pytest.raises(error):
            wb.propose(Proposal(**{**base, **change}))
    with pytest.raises(ValueError):
        wb.propose({"kind": "revise"})
    with pytest.raises(KeyError):
        wb.edit("e-none")
    assert len(wb.edits()) == logged and wb.theory.to_dict() == state and wb.theory.next_id == counter
    with pytest.raises(ValueError):
        wb.observe(phi(X1), profiled(), "r1")
    assert wb.theory.to_dict() == state


def test_a_kept_bet_settles_once_and_a_later_pass_is_only_a_contradiction(tmp_path):
    wb, first = opened(tmp_path)
    edit = wb.propose(revise(wb, first, S_HAND, bets=(bet(S_HAND),)))
    added = edit.payload["adds"][0]
    kept = wb.observe(phi(X1), raw_fail(attribution=(added, True)), "r2")
    assert kept.bets == ((edit.edit_id, 0, "kept"),) and kept.rolled_back == ()
    assert wb.open_bets() == ()
    assert wb.edit(edit.edit_id).payload["bets_state"] == [{"status": "kept", "record_id": "r2"}]
    later = wb.observe(phi(X8), pass_label(), "r3")
    assert later.bets == () and later.rolled_back == ()
    assert wb.edit(edit.edit_id).decision == "accepted"
    assert "r3" in wb.theory.get(added).contradictions
    assert wb.store.load().to_dict() == wb.theory.to_dict()


def test_a_broken_bet_restores_the_snapshot_and_replays_later_records(tmp_path):
    wb, first = opened(tmp_path)
    before = wb.theory.to_dict()
    proposal = revise(wb, first, (L_DUPS,), bets=(bet([UNI_ALL, L_DUPS]),))
    edit = wb.propose(proposal)
    assert edit.decision == "accepted"
    assert edit.payload["length_delta"] == pytest.approx(-9 * MDL_LITERAL_BITS)
    out = wb.observe(phi(X5), pass_label(), "r2")
    assert out.bets == ((edit.edit_id, 0, "broken"),) and out.rolled_back == (edit.edit_id,)
    assert out.observation.prediction.zone == "confirmed"
    assert out.observation.surprise == pytest.approx(surprise_bits(P_CONFIRMED, "pass"))
    expected = Theory.from_dict({**before, "next_id": before["next_id"] + 1})
    expected.observe(phi(X5), pass_label(), "r2")
    assert wb.theory.to_dict() == expected.to_dict()
    assert wb.store.load().to_dict() == expected.to_dict()
    undone = wb.edit(edit.edit_id)
    assert undone.decision == "rolled_back"
    assert undone.payload["bets_state"] == [{"status": "broken", "record_id": "r2"}]
    assert undone.payload["rollback"] == {"reason": "bet_broken", "record_id": "r2", "generation": 1}
    memory = wb.negatives()[-1]
    assert memory["fingerprint"] == edit.payload["fingerprint"] and memory["reason"] == "bet_broken"
    assert memory["record_id"] == "r2" and memory["edit_id"] == edit.edit_id
    last = wb.store.journal()[-1]
    assert last["kind"] == "rollback" and last["cascade"] == [] and last["reason"] == "bet_broken"
    assert set(last) == {"kind", "seq", "edit_id", "reason", "generation", "cascade"}

    assert wb.propose(proposal).payload["reason"] == "negative_memory"
    clothed = Proposal(
        kind="add",
        rationale="same idea, new clothes",
        proposer="llm",
        adds=(replace(wb.theory.get(first), specific=(L_DUPS,), source="hand-written"),),
        bets=(bet([L_DUPS]),),
    )
    assert wb.propose(clothed).payload["reason"] == "negative_memory"
    assert len(wb.negatives()) == 1 and wb.theory.to_dict() == expected.to_dict()


def test_a_cascade_is_not_memorised_and_can_be_proposed_again(tmp_path):
    wb, first = opened(tmp_path)
    duck = phi(JOINQ, engine="duckdb")
    duck_label = profiled(
        oracle="plan_variant",
        fix_set=("deliminator", "filter_pushdown"),
        fix_kind="optimizer",
        ladder="recent",
        witness=("no_optimizer",),
        switches=("deliminator", "filter_pushdown"),
    )
    opened_duck = wb.observe(duck, duck_label, "d1").observation.opened
    assert opened_duck
    before = wb.theory.to_dict()
    first_edit = wb.propose(
        revise(wb, first, S_HAND, bets=(bet([EXC_ALL], [L_DUPS], "fail"),))
    )
    second = revise(
        wb,
        opened_duck,
        (JOIN,),
        bets=(bet([JOIN], engine="duckdb", oracle="plan_variant"),),
        trigger=(),
        rationale="any inner join",
    )
    second_edit = wb.propose(second)
    assert first_edit.decision == second_edit.decision == "accepted"
    live_next = wb.theory.next_id
    out = wb.observe(phi(X3), pass_label(), "r2")
    assert out.bets == ((first_edit.edit_id, 0, "broken"),)
    assert out.rolled_back == (first_edit.edit_id, second_edit.edit_id)
    expected = Theory.from_dict({**before, "next_id": live_next})
    expected.observe(phi(X3), pass_label(), "r2")
    assert wb.theory.to_dict() == expected.to_dict()
    fallen = wb.edit(second_edit.edit_id)
    assert fallen.decision == "rolled_back"
    assert fallen.payload["rollback"] == {
        "reason": "cascade",
        "record_id": None,
        "generation": wb.store.journal()[-1]["generation"],
    }
    assert wb.store.journal()[-1]["generation"] == 2
    assert fallen.payload["bets_state"] == [{"status": "void", "record_id": None}]
    assert [item["edit_id"] for item in wb.negatives()] == [first_edit.edit_id]
    assert wb.store.journal()[-1]["cascade"] == [second_edit.edit_id]
    assert wb.open_bets() == ()
    retry = wb.propose(second)
    assert retry.decision == "accepted" and retry.edit_id not in (first_edit.edit_id, second_edit.edit_id)
    assert retry.payload["adds"][0] not in second_edit.payload["adds"]
    kept = wb.observe(
        duck,
        raw_fail(attribution=(retry.payload["adds"][0], True), oracle="plan_variant", switches=("no_optimizer",)),
        "d2",
    )
    assert kept.bets == ((retry.edit_id, 0, "kept"),) and kept.rolled_back == ()


def test_manual_rollback_replays_observations_made_since_the_edit(tmp_path):
    wb, first = opened(tmp_path)
    before = wb.theory.to_dict()
    edit = wb.propose(revise(wb, first, S_HAND, bets=(bet(S_HAND),)))
    wb.observe(phi(PLAIN), pass_label(), "r2")
    with pytest.raises(ValueError):
        wb.rollback(edit.edit_id, reason="cascade")
    with pytest.raises(ValueError):
        wb.rollback("e-none")
    live_next = wb.theory.next_id
    done = wb.rollback(edit.edit_id)
    expected = Theory.from_dict({**before, "next_id": live_next})
    expected.observe(phi(PLAIN), pass_label(), "r2")
    assert wb.theory.to_dict() == expected.to_dict() == wb.store.load().to_dict()
    assert len(done) == 1 and done[0].edit_id == edit.edit_id and done[0].decision == "rolled_back"
    assert done[0].payload["rollback"]["reason"] == "manual"
    assert done[0].payload["rollback"]["record_id"] is None
    assert done[0].payload["bets_state"] == [{"status": "void", "record_id": None}]
    assert wb.negatives()[-1]["edit_id"] == edit.edit_id and wb.negatives()[-1]["reason"] == "manual"
    with pytest.raises(ValueError):
        wb.rollback(edit.edit_id)
    assert wb.checkpoint("after-rollback") == wb.generation - 1
    with pytest.raises(ValueError):
        wb.checkpoint("")


def test_reopen_matches_and_the_journal_drops_detail(tmp_path):
    wb, first = opened(tmp_path)
    wb.propose(revise(wb, first, S_HAND, bets=(bet([EXC_ALL], [L_DUPS], "pass"), bet([INT_ALL, L_DUPS]))))
    heavy = replace(profiled(), detail={"sql": "SELECT " + "x" * 80, "rows": [1, 2, 3]})
    wb.observe(phi(X1), heavy, "r2")
    wb.observe(phi(X3), pass_label(), "r3")
    assert wb.checkpoint("batch-1") == wb.generation - 1
    entries = wb.store.journal()
    observe = [entry for entry in entries if entry["kind"] == "observe"]
    assert all(set(entry) == {"kind", "seq", "record_id", "phi", "label"} for entry in observe)
    assert observe[1]["label"]["detail"] == {} and observe[1]["label"]["cve"] == heavy.cve
    assert observe[1]["phi"] == phi(X1).to_dict()
    assert set(entries[1]) == {"kind", "seq", "edit_id", "generation"}
    checkpoint = entries[-1]
    assert checkpoint["kind"] == "checkpoint" and checkpoint["note"] == "batch-1"
    assert set(checkpoint) == {"kind", "seq", "note", "generation"}
    saved = _state(wb)
    again = Workbench.open(wb.store.root)
    assert _state(again) == saved
    copy = tmp_path / "copy"
    shutil.copytree(wb.store.root, copy)
    twin = Workbench.open(copy)
    for example, label, record_id in (
        (phi(X4), raw_fail(), "r4"),
        (phi(X8), pass_label(), "r5"),
    ):
        left = wb.observe(example, label, record_id)
        right = twin.observe(example, label, record_id)
        assert left == right
    assert _state(twin) == _state(wb)
    assert [seen.record_id for seen in wb.records()][:3] == ["r1", "r2", "r3"]
    with pytest.raises(KeyError):
        wb.seen("r-none")
    with pytest.raises(ValueError):
        wb.observe(phi(X1), profiled(), "r1")


def test_owners_families_and_the_partition(tmp_path):
    wb = Workbench.create(tmp_path / "store")
    duck = phi(JOINQ, engine="duckdb")
    loose = wb.observe(
        duck,
        profiled(
            behavior={"missing": 8, "extra": 8},
            oracle="plan_variant",
            fix_kind="unresolved",
            plan_diff=("-WINDOW",),
            ladder="unknown",
            witness=("window_combine",),
            switches=("window_combine",),
        ),
        "d1",
    ).observation.opened
    fixed = wb.observe(
        duck,
        profiled(
            oracle="plan_variant",
            fix_set=("filter_pushdown", "deliminator"),
            fix_kind="optimizer",
            ladder="recent",
            witness=("no_optimizer",),
            switches=("deliminator", "filter_pushdown"),
        ),
        "d2",
    ).observation.opened
    other = wb.observe(
        duck,
        profiled(
            oracle="tlp",
            fix_set=("deliminator", "filter_pushdown"),
            fix_kind="optimizer",
            ladder="recent",
            witness=("no_optimizer",),
            switches=("deliminator", "filter_pushdown"),
        ),
        "d3",
    ).observation.opened
    datafusion = wb.observe(phi(X1), profiled(), "r1").observation.opened
    assert loose and fixed and other and datafusion
    key = "duckdb|fix:deliminator+filter_pushdown"
    assert wb.family_of(fixed) == wb.family_of(other) == key
    assert wb.family_of(loose) == f"duckdb|{loose}"
    assert wb.family_of(datafusion) == f"{ENGINE}|{datafusion}"
    assert wb.families() == {
        f"duckdb|{loose}": (loose,),
        key: (fixed, other),
        f"{ENGINE}|{datafusion}": (datafusion,),
    }
    both = raw_fail(
        attribution=(fixed, True),
        behavior={"missing": 2, "extra": 2},
        oracle="plan_variant",
        switches=("no_optimizer",),
    )
    owned = wb.observe(duck, both, "d4")
    assert owned.owner == fixed and wb.owner_of("d4") == fixed
    unexplained = wb.observe(phi(X6), raw_fail(behavior={"missing": 2, "extra": 2}), "r2")
    assert unexplained.owner is None and wb.owner_of("r2") is None
    passed = wb.observe(phi(PLAIN), pass_label(), "p1")
    assert passed.owner is None and "p1" not in wb.partition()
    assert wb.partition() == {
        "d1": f"duckdb|{loose}",
        "d2": key,
        "d3": key,
        "d4": key,
        "r1": f"{ENGINE}|{datafusion}",
        "r2": None,
    }
    with pytest.raises(KeyError):
        wb.owner_of("r-none")
    with pytest.raises(KeyError):
        wb.family_of("h-none")


def test_surprise_under_is_the_mean_static_surprise(tmp_path):
    wb, first = opened(tmp_path)
    wb.propose(revise(wb, first, S_HAND, bets=(bet(S_HAND),)))
    wb.observe(phi(X4), raw_fail(behavior={"missing": 0, "extra": 3}), "r2")
    closed = wb.checkpoint("marked")
    assert closed == 1 and wb.generation == 2
    old = ["r1", "r2"]
    for generation in range(wb.generation):
        past = wb.store.load_generation(generation)
        expected = sum(surprise_bits(past.predict(wb.seen(record).phi, ORACLE).p_fail_valid, "fail") for record in old) / 2
        assert wb.surprise_under(generation, old) == pytest.approx(expected)
    live = sum(surprise_bits(wb.predict(wb.seen(record).phi, ORACLE).p_fail_valid, "fail") for record in old) / 2
    assert wb.surprise_under(wb.generation, old) == pytest.approx(live)
    assert wb.surprise_under(0, ["r1"]) == pytest.approx(surprise_bits(P_CONFIRMED, "fail"))
    with pytest.raises(ValueError):
        wb.surprise_under(0, [])
    with pytest.raises((ValueError, KeyError)):
        wb.surprise_under(0, ["r-none"])
    wb.observe(phi(PLAIN), invalid_label(), "r-invalid")
    with pytest.raises(ValueError):
        wb.surprise_under(0, ["r-invalid"])
    with pytest.raises(StoreError):
        wb.surprise_under(wb.generation + 1, old)
