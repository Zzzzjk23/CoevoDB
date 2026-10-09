"""Hypothesis fields, identity, a new family, and the attribution request."""

from __future__ import annotations

import json

import pytest

from surprise.harness.contracts import Label
from surprise.harness.cve.hypothesis import parse_hypothesis
from surprise.harness.cve.shape import behavior_shape
from surprise.theory import Hypothesis, attribution_request, identity_match, new_family
from surprise.theory import contracts

from test_surprise_s06_common import (
    INT_ALL,
    JOINQ,
    L_DUPS,
    PLAIN,
    T_DUPS,
    X3,
    X4,
    fail_label,
    hypothesis,
    phi,
)

NEW_FIELDS = ("oracle", "fail_kind", "error_class", "behavior_shape", "contradictions", "truncated")


def _profiled(**overrides):
    profile = {
        "status": "ran",
        "reason": None,
        "fix_kind": "optimizer",
        "fix_set": ["deliminator", "filter_pushdown"],
        "plan_diff": ["-DELIM_JOIN", "+HASH_JOIN"],
        "version_ladder": "recent",
        "witness_switches": ["no_optimizer"],
        "error_class": "Ignored",
        "behavior_shape": "extra_only",
        "executions": 13,
    }
    profile.update(overrides)
    return fail_label(
        oracle="plan_variant",
        fail_kind="wrong_result",
        error_class="ProcessExit",
        behavior={"missing": 2, "extra": 0},
        switches=("deliminator", "filter_pushdown"),
        cve={"profile": profile},
    )


def test_new_fields_default_and_round_trip_with_and_without_the_keys() -> None:
    old = Hypothesis(
        hypothesis_id="h1",
        engine="duckdb",
        interventions=["deliminator", "filter_pushdown"],
        plan_delta=["HASH_JOIN"],
        versions={"1.1.3": "fail"},
        specific=["correlated_exists", "neq"],
        general=[["correlated_exists"], ["neq"]],
        positives=["run-1:1"],
        negatives=[],
        source="deterministic",
        status="proposed",
    )
    assert (old.oracle, old.fail_kind, old.error_class, old.behavior_shape, old.contradictions, old.truncated) == (
        None, None, None, None, (), False,
    )
    s2_era = {key: value for key, value in old.to_dict().items() if key not in NEW_FIELDS}
    assert set(NEW_FIELDS).isdisjoint(s2_era)
    assert Hypothesis.from_dict(s2_era) == old

    full = hypothesis(
        positives=("r1",),
        negatives=("r2", "r3"),
        contradictions=["r3"],
        truncated=True,
        versions={"ladder": "longstanding"},
    )
    assert full.contradictions == ("r3",)
    payload = full.to_dict()
    assert set(NEW_FIELDS) <= set(payload)
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload
    assert Hypothesis.from_dict(payload) == full
    assert Hypothesis.from_json(full.to_json()) == full
    assert contracts.Hypothesis is Hypothesis


def test_new_fields_reject_a_bad_oracle_type_string_and_flag() -> None:
    full = hypothesis()
    with pytest.raises(ValueError):
        hypothesis(oracle="no_such_oracle")
    with pytest.raises(ValueError):
        hypothesis(fail_kind=3)
    with pytest.raises(ValueError):
        hypothesis(error_class=3)
    with pytest.raises(ValueError):
        hypothesis(behavior_shape=3)
    with pytest.raises(ValueError):
        hypothesis(contradictions="r1")
    with pytest.raises(ValueError):
        hypothesis(truncated="yes")
    with pytest.raises(ValueError):
        hypothesis(truncated=1)
    accepted = hypothesis(oracle="tlp", fail_kind="", error_class=None, behavior_shape="none", truncated=False)
    assert accepted.oracle == "tlp"
    assert accepted.fail_kind == ""
    assert full.oracle == "cross_dbms"


def test_identity_prefers_this_hypothesis_attribution_then_the_fix_set_then_the_profile() -> None:
    plain = hypothesis()
    same = fail_label(behavior={"missing": 3, "extra": 0})
    assert identity_match(plain, same) is True
    assert identity_match(plain, fail_label(behavior={"missing": 0, "extra": 3})) is False
    assert identity_match(plain, fail_label(fail_kind="crash", error_class="ProcessExit", behavior={})) is False

    # The harness test of this hypothesis decides, even when the three fields disagree.
    attributed = fail_label(
        behavior={"missing": 0, "extra": 4},
        cve={"attribution": {"status": "ran", "hypothesis_id": "h-test", "consistent": True}},
    )
    assert identity_match(plain, attributed) is True
    denied = fail_label(
        behavior={"missing": 1, "extra": 0},
        cve={"attribution": {"status": "ran", "hypothesis_id": "h-test", "consistent": False}},
    )
    assert identity_match(plain, denied) is False

    # A test of another hypothesis, a skipped test, or a non-bool flag says nothing.
    other = fail_label(
        behavior={"missing": 0, "extra": 1},
        cve={"attribution": {"status": "ran", "hypothesis_id": "h-other", "consistent": True}},
    )
    assert identity_match(plain, other) is False
    skipped = fail_label(
        behavior={"missing": 2, "extra": 0},
        cve={"attribution": {"status": "skipped", "reason": "not_requested"}},
    )
    assert identity_match(plain, skipped) is True
    flagged = fail_label(
        behavior={"missing": 1, "extra": 0},
        cve={"attribution": {"status": "ran", "hypothesis_id": "h-test", "consistent": 1}},
    )
    assert identity_match(plain, flagged) is True

    # No cve keys at all: the three fields still answer, and nothing is raised.
    assert identity_match(plain, fail_label(behavior={"missing": 1}, cve={})) is True

    switched = hypothesis(
        interventions=("filter_pushdown", "deliminator"),
        oracle="plan_variant",
        engine="duckdb",
    )
    profiled = fail_label(
        oracle="plan_variant",
        cve={"profile": {"status": "ran", "fix_set": ["deliminator", "filter_pushdown", "deliminator"]}},
    )
    assert identity_match(switched, profiled) is True
    different = fail_label(oracle="plan_variant", cve={"profile": {"status": "ran", "fix_set": []}})
    assert identity_match(switched, different) is False
    assert identity_match(switched, fail_label(oracle="plan_variant")) is None
    malformed = fail_label(oracle="plan_variant", cve={"profile": {"status": "ran", "fix_set": "deliminator"}})
    assert identity_match(switched, malformed) is None

    # An attribution of this hypothesis still wins when a fix set is present.
    forced = fail_label(
        oracle="plan_variant",
        cve={
            "attribution": {"status": "ran", "hypothesis_id": "h-test", "consistent": False},
            "profile": {"status": "ran", "fix_set": ["filter_pushdown", "deliminator"]},
        },
    )
    assert identity_match(switched, forced) is False
    ignored = fail_label(
        oracle="plan_variant",
        cve={"attribution": {"status": "ran", "hypothesis_id": "h-other", "consistent": True}},
    )
    assert identity_match(switched, ignored) is None

    # With no interventions, a profile's fix set is not consulted.
    disguised = fail_label(
        behavior={"missing": 1, "extra": 0},
        cve={"profile": {"status": "ran", "fix_set": ["deliminator"]}},
    )
    assert identity_match(plain, disguised) is True

    with pytest.raises(ValueError):
        identity_match(plain, Label(y="pass", oracle="cross_dbms"))
    with pytest.raises(ValueError):
        identity_match(plain, Label(y="invalid", oracle="cross_dbms", invalid_reason="query_error"))


def test_new_family_copies_each_field_from_the_profile_and_the_label() -> None:
    label = _profiled()
    example = phi((INT_ALL, L_DUPS), engine="duckdb")
    family = new_family("h-new", example, label, "run:7")
    assert (family.hypothesis_id, family.engine, family.oracle) == ("h-new", "duckdb", "plan_variant")
    assert family.interventions == ("deliminator", "filter_pushdown")
    assert family.plan_delta == ("-DELIM_JOIN", "+HASH_JOIN")
    assert family.versions == {
        "ladder": "recent",
        "fix_kind": "optimizer",
        "witness_switches": ["no_optimizer"],
    }
    assert family.fail_kind == "wrong_result"
    # error_class and behavior_shape come from the label, not from the profile's copies.
    assert family.error_class == "ProcessExit"
    assert family.behavior_shape == behavior_shape({"missing": 2, "extra": 0}) == "missing_only"
    assert family.specific == tuple(sorted((INT_ALL, L_DUPS)))
    assert family.general == ((),)
    assert family.positives == ("run:7",)
    assert family.negatives == ()
    assert family.contradictions == ()
    assert family.truncated is False
    assert family.source == "deterministic"
    assert family.status == "active"


def test_new_family_rejects_a_pass_and_an_unprofiled_failure() -> None:
    example = phi(PLAIN)
    with pytest.raises(ValueError):
        new_family("h", example, Label(y="pass", oracle="cross_dbms"), "r")
    with pytest.raises(ValueError):
        new_family("h", example, fail_label(cve={"profile": {"status": "skipped", "reason": "not_requested"}}), "r")
    with pytest.raises(ValueError):
        new_family("h", example, fail_label(), "r")


def test_new_family_replays_earlier_passes_and_skips_one_g_already_excludes() -> None:
    label = fail_label(
        behavior={"missing": 0, "extra": 3},
        cve={"profile": {
            "status": "ran",
            "fix_kind": "non_optimizer",
            "fix_set": [],
            "plan_diff": [],
            "version_ladder": "longstanding",
            "witness_switches": [],
        }},
    )
    family = new_family(
        "h-new",
        phi(X4),
        label,
        "run:9",
        negatives=[(phi(PLAIN), "run:2"), (phi(X3), "run:3"), (phi(JOINQ), "run:4")],
        source="hand",
    )
    assert family.general == ((INT_ALL,), (L_DUPS,), (T_DUPS,))
    assert family.negatives == ("run:2", "run:3")
    assert family.contradictions == ()
    assert family.positives == ("run:9",)
    assert family.source == "hand"
    assert family.behavior_shape == "extra_only"


def test_attribution_request_names_interventions_or_the_three_identity_fields() -> None:
    bare = attribution_request(hypothesis(hypothesis_id="h2", error_class=None, behavior_shape="missing_only"))
    assert bare == {
        "hypothesis_id": "h2",
        "engine": "datafusion",
        "interventions": [],
        "fail_kind": "wrong_result",
        "error_class": None,
        "behavior_shape": "missing_only",
    }
    switched = attribution_request(
        hypothesis(
            hypothesis_id="h7",
            engine="duckdb",
            oracle="plan_variant",
            interventions=("filter_pushdown", "deliminator"),
        )
    )
    assert switched == {
        "hypothesis_id": "h7",
        "engine": "duckdb",
        "interventions": ["filter_pushdown", "deliminator"],
    }
    assert parse_hypothesis(bare, "datafusion").hypothesis_id == "h2"
    assert parse_hypothesis(switched, "duckdb").interventions == ("filter_pushdown", "deliminator")
