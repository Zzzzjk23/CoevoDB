"""Zones, surprise, and the six-way triage."""

from __future__ import annotations

import dataclasses
import json
import math

import pytest

from surprise.features.units import unit_of
from surprise.theory import TRIAGE_KINDS, ZONES, Prediction, Theory, surprise_bits, triage
from surprise.theory.constants import (
    P_CONFIRMED,
    P_PENDING,
    RESIDUAL_PRIOR_FAILS,
    RESIDUAL_PRIOR_TESTS,
    TRIAGE_HIGH_BITS,
    TRIAGE_LOW_BITS,
    VALIDITY_PRIOR_INVALID,
    VALIDITY_PRIOR_TESTS,
)

from test_surprise_s06_common import (
    AST_ONLY,
    EXC_ALL,
    HJ,
    INT,
    INT_ALL,
    L_DUPS,
    PLAIN,
    SELECT,
    SRC,
    T_DUPS,
    X1,
    X3,
    X4,
    X5,
    hypothesis,
    phi,
)

R_DUPS = "data:setop:right_has_dups"
X8 = (EXC_ALL, SELECT, L_DUPS, R_DUPS, T_DUPS, INT, SRC, HJ)
S_X4 = tuple(sorted(X4))
PRIOR = RESIDUAL_PRIOR_FAILS / RESIDUAL_PRIOR_TESTS
K_PRIOR = VALIDITY_PRIOR_INVALID / VALIDITY_PRIOR_TESTS
ORACLE = "cross_dbms"

SURPRISE_CASES = (
    (PRIOR, "fail", -math.log2(PRIOR)),
    (0.95, "pass", -math.log2(0.05)),
    (0.5, "fail", 1.0),
    (0.5, "pass", 1.0),
    (0.95, "fail", -math.log2(0.95)),
    (PRIOR, "pass", -math.log2(1 - PRIOR)),
)
SURPRISE_BAD = (
    (0.0, "fail"),
    (1.0, "pass"),
    (-0.1, "fail"),
    (1.5, "fail"),
    (0.5, "maybe"),
    ("0.5", "fail"),
    (True, "fail"),
    (float("nan"), "fail"),
)
TRIAGE_CASES = (
    ("fail", 6.6439, "new_family"),
    ("pass", 4.3219, "unexpected_pass"),
    ("fail", 1.0, "boundary_move"),
    ("pass", 1.0, "boundary_move"),
    ("fail", 0.074, "duplicate"),
    ("pass", 0.0145, "no_information"),
    ("invalid", None, "invalid"),
    ("fail", TRIAGE_HIGH_BITS, "new_family"),
    ("pass", TRIAGE_HIGH_BITS, "unexpected_pass"),
    ("fail", 2, "new_family"),
    ("fail", 1.9999, "boundary_move"),
    ("pass", TRIAGE_LOW_BITS, "boundary_move"),
    ("fail", 0.4999, "duplicate"),
    ("pass", 0.0, "no_information"),
    ("fail", 40.0, "new_family"),
)
TRIAGE_BAD = (
    ("invalid", 1.0),
    ("pass", None),
    ("fail", -0.1),
    ("fail", float("nan")),
    ("fail", float("inf")),
    ("maybe", 1.0),
    ("pass", "1.0"),
    ("pass", True),
)


def test_zone_and_triage_names() -> None:
    assert ZONES == ("confirmed", "pending", "unexplored")
    assert TRIAGE_KINDS == (
        "new_family",
        "unexpected_pass",
        "boundary_move",
        "duplicate",
        "no_information",
        "invalid",
    )


@pytest.mark.parametrize(("probability", "outcome", "expected"), SURPRISE_CASES)
def test_surprise_bits_has_the_five_magnitudes(probability: float, outcome: str, expected: float) -> None:
    assert surprise_bits(probability, outcome) == pytest.approx(expected)


def test_invalid_has_no_surprise() -> None:
    assert surprise_bits(0.5, "invalid") is None


@pytest.mark.parametrize(("probability", "outcome"), SURPRISE_BAD)
def test_surprise_bits_rejects(probability: object, outcome: str) -> None:
    with pytest.raises(ValueError):
        surprise_bits(probability, outcome)  # type: ignore[arg-type]


@pytest.mark.parametrize(("outcome", "bits", "kind"), TRIAGE_CASES)
def test_triage_bands_and_thresholds(outcome: str, bits: float | None, kind: str) -> None:
    assert triage(outcome, bits) == kind


@pytest.mark.parametrize(("outcome", "bits"), TRIAGE_BAD)
def test_triage_rejects(outcome: object, bits: object) -> None:
    with pytest.raises(ValueError):
        triage(outcome, bits)  # type: ignore[arg-type]


def test_empty_theory_explores_and_splits_the_three_outcomes() -> None:
    theory = Theory()
    example = phi(X1)
    before = theory.to_dict()
    prediction = theory.predict(example, ORACLE)
    assert theory.to_dict() == before
    assert (prediction.zone, prediction.hypothesis_id, prediction.confirmed, prediction.pending) == (
        "unexplored",
        None,
        (),
        (),
    )
    assert (prediction.engine, prediction.oracle, prediction.unit, prediction.experiment_class) == (
        "datafusion",
        ORACLE,
        unit_of(example, ORACLE),
        "datafusion|set_op_all",
    )
    assert prediction.p_fail_valid == pytest.approx(PRIOR)
    assert prediction.p_invalid == pytest.approx(K_PRIOR)
    assert prediction.p_fail == pytest.approx((1 - K_PRIOR) * PRIOR)
    assert prediction.p_pass == pytest.approx((1 - K_PRIOR) * (1 - PRIOR))
    assert prediction.p_fail + prediction.p_pass + prediction.p_invalid == pytest.approx(1.0)
    assert prediction.surprise("fail") == pytest.approx(surprise_bits(PRIOR, "fail"))
    assert prediction.surprise("pass") == pytest.approx(surprise_bits(PRIOR, "pass"))
    assert prediction.surprise("invalid") is None
    exported = prediction.to_dict()
    assert json.loads(json.dumps(exported)) == exported
    assert {
        "engine",
        "oracle",
        "unit",
        "experiment_class",
        "zone",
        "hypothesis_id",
        "confirmed",
        "pending",
        "p_fail_valid",
        "p_invalid",
        "p_fail",
        "p_pass",
    } <= set(exported)


def test_confirmed_beats_pending_and_lists_keep_creation_order() -> None:
    theory = Theory()
    theory.put(hypothesis(hypothesis_id="h-a", specific=(EXC_ALL, L_DUPS), general=((L_DUPS,),)))
    theory.put(
        hypothesis(
            hypothesis_id="h-b",
            specific=S_X4,
            general=((INT_ALL,), (T_DUPS,)),
            behavior_shape="extra_only",
        )
    )
    theory.put(
        hypothesis(
            hypothesis_id="h-duck",
            specific=(SELECT,),
            general=((),),
            engine="duckdb",
            oracle="plan_variant",
        )
    )
    expectations = (
        (X1, "confirmed", "h-a", ("h-a",), ("h-b",), P_CONFIRMED),
        (X8, "confirmed", "h-a", ("h-a",), ("h-b",), P_CONFIRMED),
        (X4, "confirmed", "h-b", ("h-b",), ("h-a",), P_CONFIRMED),
        (X5, "pending", "h-a", (), ("h-a", "h-b"), P_PENDING),
        (X3, "unexplored", None, (), (), PRIOR),
        (PLAIN, "unexplored", None, (), (), PRIOR),
    )
    for features, zone, owner, confirmed, pending, probability in expectations:
        got = theory.predict(phi(features), ORACLE)
        assert (got.zone, got.hypothesis_id, got.confirmed, got.pending) == (zone, owner, confirmed, pending)
        assert got.p_fail_valid == pytest.approx(probability)
    foreign = theory.predict(phi(X1), "tlp")
    assert foreign.zone == "unexplored"
    assert foreign.unit == unit_of(phi(X1), "tlp")
    assert theory.predict(phi(PLAIN, engine="duckdb"), "plan_variant").zone == "confirmed"
    partial = phi((EXC_ALL, SELECT), layers=AST_ONLY)
    undetermined = theory.predict(partial, ORACLE)
    assert undetermined.zone == "unexplored"
    assert undetermined.hypothesis_id is None
    assert undetermined.unit == unit_of(partial, ORACLE)


def test_rho_and_validity_are_read_from_the_public_models() -> None:
    theory = Theory()
    theory.put(hypothesis(hypothesis_id="h-a", specific=(EXC_ALL, L_DUPS), general=((L_DUPS,),)))
    plain = theory.predict(phi(PLAIN), ORACLE)
    for _ in range(9):
        theory.residual.observe(plain.unit, "pass")
    theory.residual.observe(plain.unit, "fail")
    drifted = theory.predict(phi(PLAIN), ORACLE)
    assert drifted.p_fail_valid == pytest.approx(2 / 110)
    assert theory.predict(phi(X3), ORACLE).p_fail_valid == pytest.approx(PRIOR)
    theory.validity.observe(plain.experiment_class, ORACLE, "invalid", "query_error")
    assert theory.predict(phi(PLAIN), ORACLE).p_invalid == pytest.approx(2 / 11)
    assert theory.predict(phi(X3), ORACLE).p_invalid == pytest.approx(K_PRIOR)


def test_predict_rejects() -> None:
    theory = Theory()
    example = phi(X1)
    with pytest.raises(ValueError):
        theory.predict(example, "no_such_oracle")
    with pytest.raises(ValueError):
        theory.predict(dataclasses.replace(example, vocab="0" * 64), ORACLE)
    with pytest.raises(ValueError):
        theory.predict(example.to_dict(), ORACLE)  # type: ignore[arg-type]


def test_document_table_follows_surprise_at_the_prior() -> None:
    theory = Theory()
    theory.put(hypothesis(hypothesis_id="h-a", specific=(EXC_ALL, L_DUPS), general=((L_DUPS,),)))
    where = {"confirmed": X1, "pending": X4, "unexplored": PLAIN}
    table = {
        ("unexplored", "fail"): "new_family",
        ("confirmed", "pass"): "unexpected_pass",
        ("pending", "fail"): "boundary_move",
        ("pending", "pass"): "boundary_move",
        ("confirmed", "fail"): "duplicate",
        ("unexplored", "pass"): "no_information",
    }
    for (zone, outcome), kind in table.items():
        prediction = theory.predict(phi(where[zone]), ORACLE)
        assert prediction.zone == zone
        assert triage(outcome, prediction.surprise(outcome)) == kind


def test_prediction_rejects_a_probability_on_the_boundary() -> None:
    with pytest.raises(ValueError):
        Prediction(
            engine="datafusion",
            oracle=ORACLE,
            unit="u",
            experiment_class="datafusion|plain",
            zone="unexplored",
            hypothesis_id=None,
            confirmed=(),
            pending=(),
            p_fail_valid=0.0,
            p_invalid=0.1,
        )
