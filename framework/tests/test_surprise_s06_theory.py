"""Learning one label: hypothesis updates, new families, and the saved state."""

from __future__ import annotations

import hashlib
import json

import pytest

from surprise.features.units import unit_of
from surprise.harness.contracts import Label
from surprise.theory import Prediction, Theory, apply_negative, apply_positive, experiment_class
from surprise.theory.constants import P_CONFIRMED

from test_surprise_s06_common import (
    AST_ONLY,
    D_SETOP,
    EXC_ALL,
    INT_ALL,
    L_DUPS,
    PLAIN,
    SELECT,
    SET_ALL,
    X1,
    X3,
    X4,
    X5,
    fail_label,
    hypothesis,
    phi,
)

ORACLE = "cross_dbms"
MISSING = {"missing": 1, "extra": 0}
EXTRA = {"missing": 0, "extra": 3}
WHERE = {"confirmed": X1, "pending": X5, "outside": PLAIN}


def _pass(oracle: str = ORACLE) -> Label:
    return Label(y="pass", oracle=oracle)


def _invalid(reason: str = "query_error", oracle: str = ORACLE) -> Label:
    return Label(y="invalid", oracle=oracle, invalid_reason=reason)


def _profiled(behavior: dict[str, int] | None = None) -> Label:
    profile = {
        "status": "ran",
        "reason": None,
        "fix_kind": "non_optimizer",
        "fix_set": [],
        "plan_diff": [],
        "version_ladder": "longstanding",
        "witness_switches": [],
    }
    return fail_label(behavior=MISSING if behavior is None else behavior, cve={"profile": profile})


def _branch_hypothesis(identity: str):
    fields: dict[str, object] = {
        "hypothesis_id": "h-a",
        "specific": (EXC_ALL, L_DUPS),
        "general": ((L_DUPS,),),
    }
    if identity == "mismatch":
        fields["behavior_shape"] = "extra_only"
    elif identity == "unknown":
        fields["interventions"] = ("filter_pushdown",)
    return hypothesis(**fields)


def _expected_outcome(y: str, where: str, identity: str) -> str | None:
    if y == "pass":
        return {"confirmed": "contradiction", "pending": "specialized", "outside": None}[where]
    if identity == "unknown":
        return None if where == "outside" else "unknown_identity"
    if identity == "match":
        return {"confirmed": "duplicate", "pending": "generalized", "outside": "outside"}[where]
    return {"confirmed": "contradiction", "pending": "specialized", "outside": None}[where]


@pytest.mark.parametrize("identity", ["match", "mismatch", "unknown"])
@pytest.mark.parametrize("where", ["confirmed", "pending", "outside"])
@pytest.mark.parametrize("y", ["pass", "fail"])
def test_observe_follows_position_and_identity(y: str, where: str, identity: str) -> None:
    theory = Theory()
    theory.put(_branch_hypothesis(identity))
    original = theory.get("h-a")
    example = phi(WHERE[where])
    label = _pass() if y == "pass" else fail_label(behavior=MISSING)
    obs = theory.observe(example, label, "r1")
    outcome = _expected_outcome(y, where, identity)
    zone = {"confirmed": "confirmed", "pending": "pending", "outside": "unexplored"}[where]
    assert obs.prediction.zone == zone
    assert obs.y == y
    assert (obs.effects == () if outcome is None else obs.effects == (("h-a", outcome),))
    absorbed = y == "fail" and identity == "match" and where in ("confirmed", "pending")
    if outcome in (None, "outside", "unknown_identity"):
        assert theory.get("h-a") == original
    elif y == "pass" or identity == "mismatch":
        update = apply_negative(original, example, "r1")
        assert update.outcome == outcome
        assert theory.get("h-a") == update.hypothesis
    else:
        update = apply_positive(original, example, "r1")
        assert update.outcome == outcome
        assert theory.get("h-a") == update.hypothesis
    unit = unit_of(example, ORACLE)
    if y == "fail" and not absorbed:
        assert obs.opened is None and obs.unexplained is True
        assert theory.residual.counts(unit) == (1, 1)
    elif y == "pass" and where == "outside":
        assert obs.unexplained is False and theory.residual.counts(unit) == (1, 0)
    else:
        assert obs.unexplained is False and obs.opened is None
        assert theory.residual.counts(unit) == (0, 0)
    assert theory.validity.counts(experiment_class(example), ORACLE) == (1, 0)
    remembered = theory.to_dict()["passes"]
    if y == "pass":
        assert remembered["datafusion|cross_dbms"][0]["record_id"] == "r1"
    else:
        assert remembered == {}


def test_effects_follow_creation_order_and_a_match_absorbs_the_failure() -> None:
    theory = Theory()
    theory.put(hypothesis(hypothesis_id="h1", specific=(SELECT,), general=((SELECT,),)))
    theory.put(
        hypothesis(
            hypothesis_id="h-out",
            specific=(INT_ALL,),
            general=((INT_ALL,),),
            behavior_shape="missing_only",
        )
    )
    obs = theory.observe(phi(PLAIN), fail_label(behavior=MISSING), "r1")
    assert obs.effects == (("h1", "duplicate"), ("h-out", "outside"))
    assert obs.opened is None and obs.unexplained is False
    assert theory.get("h1").positives == ("r1",)
    assert theory.get("h-out").positives == ()
    assert theory.residual.to_dict() == {}


def test_a_profiled_failure_opens_one_family_and_replays_passes() -> None:
    theory = Theory()
    theory.observe(phi(PLAIN), _pass(), "p1")
    obs = theory.observe(phi(X1), _profiled(), "f1")
    assert obs.opened == "h1"
    assert obs.unexplained is False
    assert obs.triage == "new_family"
    family = theory.get("h1")
    assert family.positives == ("f1",)
    assert "p1" in family.negatives
    assert family.behavior_shape == "missing_only"
    assert theory.residual.counts(unit_of(phi(X1), ORACLE)) == (0, 0)
    assert theory.to_dict()["next_id"] == 2


def test_a_matching_profiled_failure_does_not_open_another_family() -> None:
    theory = Theory()
    theory.put(hypothesis(hypothesis_id="h-a", specific=(SELECT,), general=((SELECT,),)))
    obs = theory.observe(phi(PLAIN), _profiled(), "r1")
    assert obs.effects == (("h-a", "duplicate"),)
    assert obs.opened is None
    assert [item.hypothesis_id for item in theory.hypotheses] == ["h-a"]
    assert theory.residual.to_dict() == {}


def test_an_identity_mismatch_is_a_counterexample_and_still_opens_a_family() -> None:
    theory = Theory()
    theory.put(
        hypothesis(
            hypothesis_id="h-a",
            specific=(SELECT,),
            general=((SELECT,),),
            behavior_shape="extra_only",
        )
    )
    obs = theory.observe(phi(PLAIN), _profiled(), "r1")
    assert obs.effects == (("h-a", "contradiction"),)
    assert obs.opened == "h1"
    assert theory.get("h-a").contradictions == ("r1",)
    assert theory.get("h1").positives == ("r1",)
    assert theory.get("h1").behavior_shape == "missing_only"


def test_outside_agreement_does_not_absorb_a_profiled_failure() -> None:
    theory = Theory()
    theory.put(
        hypothesis(
            hypothesis_id="h-a",
            specific=(INT_ALL,),
            general=((INT_ALL,),),
            behavior_shape="missing_only",
        )
    )
    obs = theory.observe(phi(PLAIN), _profiled(), "r1")
    assert obs.effects == (("h-a", "outside"),)
    assert theory.get("h-a").positives == ()
    assert obs.opened == "h1"
    assert obs.unexplained is False


def test_a_failure_without_a_usable_profile_enters_the_residual() -> None:
    theory = Theory()
    raw = theory.observe(phi(PLAIN), fail_label(behavior=MISSING), "u1")
    assert raw.opened is None and raw.unexplained is True
    assert raw.triage == "new_family"
    skipped = fail_label(behavior=MISSING, cve={"profile": {"status": "skipped"}})
    mistyped = fail_label(behavior=MISSING, cve={"profile": "ran"})
    theory.observe(phi(X3), skipped, "u2")
    theory.observe(phi(X4), mistyped, "u3")
    assert [item.hypothesis_id for item in theory.hypotheses] == []
    assert theory.residual.counts(unit_of(phi(PLAIN), ORACLE)) == (1, 1)
    assert sum(row["unexplained"] for row in theory.residual.to_dict().values()) == 3


def test_the_same_passing_phi_is_remembered_once() -> None:
    theory = Theory()
    example = phi(PLAIN)
    theory.observe(example, _pass(), "a")
    theory.observe(example, _pass(), "b")
    remembered = theory.to_dict()["passes"]["datafusion|cross_dbms"]
    assert [row["record_id"] for row in remembered] == ["a"]
    assert remembered[0]["phi"] == example.to_dict()
    assert theory.residual.counts(unit_of(example, ORACLE)) == (2, 0)


def test_a_confirmed_pass_is_remembered_and_stays_out_of_the_residual() -> None:
    theory = Theory()
    theory.put(hypothesis(hypothesis_id="h-a", specific=(SELECT,), general=((SELECT,),)))
    theory.observe(phi(PLAIN), _pass(), "a")
    assert theory.residual.to_dict() == {}
    assert theory.to_dict()["passes"]["datafusion|cross_dbms"][0]["record_id"] == "a"
    assert theory.get("h-a").contradictions == ("a",)


def test_invalid_touches_only_the_validity_model() -> None:
    theory = Theory()
    theory.put(hypothesis(hypothesis_id="h-a", specific=(SELECT,), general=((SELECT,),)))
    theory.observe(phi(X3), _pass(), "p1")
    before = {key: value for key, value in theory.to_dict().items() if key != "validity"}
    version = theory.version
    obs = theory.observe(phi(PLAIN), _invalid("timeout"), "i1")
    assert obs.triage == "invalid" and obs.surprise is None and obs.effects == ()
    assert obs.opened is None and obs.unexplained is False
    assert {key: value for key, value in theory.to_dict().items() if key != "validity"} == before
    assert theory.version != version
    assert theory.validity.counts("datafusion|plain", ORACLE) == (1, 1)
    assert theory.validity.reasons("datafusion|plain", ORACLE) == {"timeout": 1}


@pytest.mark.parametrize(
    "call",
    [
        lambda theory: theory.observe(phi(PLAIN).to_dict(), _pass(), "z"),
        lambda theory: theory.observe(phi(PLAIN), _pass().to_dict(), "z"),
        lambda theory: theory.observe(phi(PLAIN), _pass(), ""),
        lambda theory: theory.observe(phi(PLAIN), _pass(), "z", prediction=theory.predict(phi(PLAIN), "tlp")),
        lambda theory: theory.observe(dataclasses_replace_vocab(), _pass(), "z"),
    ],
)
def test_a_rejected_observe_does_not_change_state(call) -> None:
    theory = Theory()
    theory.observe(phi(X1), _profiled(), "f1")
    before = theory.to_dict()
    version = theory.version
    with pytest.raises(ValueError):
        call(theory)
    assert theory.to_dict() == before
    assert theory.version == version


def dataclasses_replace_vocab():
    import dataclasses

    return dataclasses.replace(phi(PLAIN), vocab="0" * 64)


def test_an_explicit_prediction_is_the_one_made_beforehand() -> None:
    left, right = Theory(), Theory()
    script = (
        (X1, _profiled(), "p1"),
        (X3, _pass(), "p2"),
        (X4, _profiled(EXTRA), "p3"),
    )
    for features, label, record in script:
        example = phi(features)
        prediction = left.predict(example, ORACLE)
        observed = left.observe(example, label, record, prediction=prediction)
        other = right.observe(example, label, record)
        assert observed.to_dict() == other.to_dict()
        assert observed.prediction == prediction
    fresh = Theory()
    example = phi(PLAIN)
    early = fresh.predict(example, ORACLE)
    for _ in range(30):
        fresh.residual.observe(early.unit, "fail")
    stale = fresh.observe(example, _pass(), "late", prediction=early)
    assert stale.surprise == pytest.approx(early.surprise("pass"))
    assert fresh.residual.counts(early.unit) == (31, 30)
    crafted = Prediction(
        engine="datafusion",
        oracle=ORACLE,
        unit=early.unit,
        experiment_class=early.experiment_class,
        zone="confirmed",
        hypothesis_id=None,
        confirmed=(),
        pending=(),
        p_fail_valid=P_CONFIRMED,
        p_invalid=early.p_invalid,
    )
    held = Theory()
    observed = held.observe(example, _pass(), "held", prediction=crafted)
    assert observed.surprise == pytest.approx(crafted.surprise("pass"))
    assert held.residual.to_dict() == {}
    assert held.to_dict()["passes"]["datafusion|cross_dbms"][0]["record_id"] == "held"


def test_ids_skip_occupied_numbers_and_are_not_recycled() -> None:
    theory = Theory()
    kept = hypothesis(
        hypothesis_id="h2",
        specific=(INT_ALL,),
        general=((INT_ALL,),),
        behavior_shape="extra_only",
    )
    theory.put(kept)
    first = theory.observe(phi(PLAIN), _profiled(), "f1")
    assert first.opened == "h1"
    assert theory.to_dict()["next_id"] == 2
    blocking = Theory()
    for number in (1, 3):
        blocking.put(
            hypothesis(
                hypothesis_id=f"h{number}",
                specific=(INT_ALL,),
                general=((INT_ALL,),),
                behavior_shape="missing_only",
            )
        )
    opened = blocking.observe(phi(PLAIN), _profiled(), "f1")
    assert opened.effects == (("h1", "outside"), ("h3", "outside"))
    assert opened.opened == "h2"
    assert blocking.to_dict()["next_id"] == 3
    again = blocking.observe(phi((SELECT,), layers=AST_ONLY), _profiled(), "f2")
    assert again.opened == "h4"
    assert blocking.to_dict()["next_id"] == 5
    assert [item.hypothesis_id for item in blocking.hypotheses] == ["h1", "h3", "h2", "h4"]


def test_put_canonicalises_replaces_and_rejects() -> None:
    theory = Theory()
    theory.put(
        hypothesis(
            hypothesis_id="h-a",
            specific=(L_DUPS, EXC_ALL, SET_ALL),
            general=((D_SETOP, L_DUPS), ()),
        )
    )
    theory.put(hypothesis(hypothesis_id="h-b", specific=(SELECT,), general=((SELECT,),)))
    stored = theory.get("h-a")
    assert tuple(stored.specific) == tuple(sorted((EXC_ALL, L_DUPS)))
    assert tuple(tuple(member) for member in stored.general) == ((),)
    theory.put(hypothesis(hypothesis_id="h-a", specific=(EXC_ALL, L_DUPS), general=((L_DUPS,),), source="rewritten"))
    assert [item.hypothesis_id for item in theory.hypotheses] == ["h-a", "h-b"]
    assert tuple(tuple(member) for member in theory.get("h-a").general) == ((L_DUPS,),)
    assert theory.get("h-a").source == "rewritten"
    rejected = (
        hypothesis(oracle=None),
        hypothesis(hypothesis_id=""),
        hypothesis(engine=""),
        hypothesis(specific=("ast:no_such_feature",)),
        hypothesis(specific=(EXC_ALL, L_DUPS), general=((INT_ALL,),)),
        hypothesis(specific=(EXC_ALL, L_DUPS), general=(("nope:x",),)),
        "h-a",
    )
    before = theory.to_dict()
    for item in rejected:
        with pytest.raises(ValueError):
            theory.put(item)
    assert theory.to_dict() == before
    with pytest.raises(KeyError):
        theory.get("h-missing")


def test_state_round_trips_and_learns_the_same_way_afterwards() -> None:
    theory = Theory()
    theory.put(
        hypothesis(
            hypothesis_id="h5",
            specific=(INT_ALL,),
            general=((INT_ALL,),),
            behavior_shape="missing_only",
        )
    )
    theory.observe(phi(PLAIN), _profiled(), "f1")
    theory.observe(phi(X3), _pass(), "p1")
    theory.observe(phi(PLAIN), _invalid(), "i1")
    theory.observe(phi(X5), fail_label(behavior=MISSING), "u1")
    state = theory.to_dict()
    assert json.loads(json.dumps(state)) == state
    assert set(state) == {"schema", "vocab", "hypotheses", "residual", "validity", "passes", "next_id"}
    restored = Theory.from_dict(json.loads(json.dumps(state)))
    assert restored.to_dict() == state
    assert restored.version == theory.version
    restored.residual.observe("some-other-unit", "pass")
    assert theory.residual.counts("some-other-unit") == (0, 0)
    restored = Theory.from_dict(state)
    tail = (
        (X4, _profiled(EXTRA), "s1"),
        (X1, fail_label(behavior=MISSING), "s2"),
        (PLAIN, _pass(), "s3"),
    )
    for features, label, record in tail:
        example = phi(features)
        assert theory.observe(example, label, record).to_dict() == restored.observe(example, label, record).to_dict()
    assert restored.to_dict() == theory.to_dict()


def test_version_names_the_canonical_state() -> None:
    theory = Theory()
    blob = json.dumps(theory.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    assert theory.version == "T-" + digest[:12]
    assert theory.version == Theory().version
    theory.observe(phi(PLAIN), _pass(), "p1")
    assert theory.version != Theory().version
    assert theory.version == Theory.from_dict(theory.to_dict()).version


@pytest.mark.parametrize(
    "bad",
    [
        {},
        [],
        None,
    ],
)
def test_from_dict_rejects_a_bad_state(bad: object) -> None:
    with pytest.raises(ValueError):
        Theory.from_dict(bad)


def test_from_dict_rejects_a_changed_schema_vocab_or_key() -> None:
    state = Theory().to_dict()
    for bad in ({**state, "schema": 2}, {**state, "vocab": "0" * 64}, {**state, "extra": 1}):
        with pytest.raises(ValueError):
            Theory.from_dict(bad)
