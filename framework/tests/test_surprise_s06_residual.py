"""Residual counts, the validity model, and experiment classes."""

from __future__ import annotations

import json

import pytest

from surprise.theory import Residual, Validity, experiment_class
from surprise.theory.constants import (
    RESIDUAL_PRIOR_FAILS,
    RESIDUAL_PRIOR_TESTS,
    VALIDITY_PRIOR_INVALID,
    VALIDITY_PRIOR_TESTS,
)

from test_surprise_s06_common import AST_ONLY, EXC_ALL, PLAIN, SELECT, X1, X6, phi


def test_residual_counts_rate_and_keeps_units_apart() -> None:
    residual = Residual()
    unit, other = "datafusion|cross_dbms|plain|scan|plain", "duckdb|tlp|join|join|nulls"
    assert residual.counts(unit) == (0, 0)
    assert residual.rate(unit) == RESIDUAL_PRIOR_FAILS / RESIDUAL_PRIOR_TESTS
    for outcome in ["pass"] * 7 + ["fail"] * 2 + ["pass"]:
        residual.observe(unit, outcome)
    assert residual.counts(unit) == (10, 2)
    assert residual.rate(unit) == (2 + RESIDUAL_PRIOR_FAILS) / (10 + RESIDUAL_PRIOR_TESTS)
    assert residual.counts(other) == (0, 0)
    assert residual.rate(other) == RESIDUAL_PRIOR_FAILS / RESIDUAL_PRIOR_TESTS
    assert list(residual.to_dict()) == [unit]


def test_residual_rejects_without_counting() -> None:
    residual = Residual()
    residual.observe("unit", "pass")
    for unit, outcome in (("unit", "invalid"), ("unit", "maybe"), ("", "pass"), (None, "fail")):
        with pytest.raises(ValueError):
            residual.observe(unit, outcome)  # type: ignore[arg-type]
    assert residual.counts("unit") == (1, 0)


def test_residual_round_trip_is_detached_and_sorted() -> None:
    residual = Residual()
    residual.observe("b", "pass")
    residual.observe("a", "fail")
    exported = residual.to_dict()
    assert list(exported) == ["a", "b"]
    assert exported == {"a": {"tested": 1, "unexplained": 1}, "b": {"tested": 1, "unexplained": 0}}
    assert json.loads(json.dumps(exported)) == exported
    loaded = Residual.from_dict(exported)
    loaded.observe("a", "pass")
    assert residual.counts("a") == (1, 1)
    assert loaded.counts("a") == (2, 1)
    exported["a"]["tested"] = 9
    assert residual.counts("a") == (1, 1)


@pytest.mark.parametrize(
    "bad",
    [
        {"u": {"tested": 1, "unexplained": 2}},
        {"u": {"tested": -1, "unexplained": 0}},
        {"u": {"tested": True, "unexplained": 0}},
        {"u": {"tested": 1.0, "unexplained": 0}},
        {"u": {"tested": 1}},
        {"u": {"tested": 1, "unexplained": 0, "extra": 0}},
        {"": {"tested": 1, "unexplained": 0}},
        ["u"],
        None,
    ],
)
def test_residual_from_dict_rejects(bad: object) -> None:
    with pytest.raises(ValueError):
        Residual.from_dict(bad)


def test_residual_rate_stays_inside_the_open_unit_interval() -> None:
    failing, passing = Residual(), Residual()
    rates = [failing.rate("u"), passing.rate("u")]
    for _ in range(300):
        failing.observe("u", "fail")
        passing.observe("u", "pass")
        rates.append(failing.rate("u"))
        rates.append(passing.rate("u"))
    assert all(0.0 < rate < 1.0 for rate in rates)
    assert rates[0] < failing.rate("u")
    assert passing.rate("u") < rates[0]


def test_validity_counts_reasons_and_rate() -> None:
    validity = Validity()
    klass = "datafusion|set_op_all"
    assert validity.counts(klass, "tlp") == (0, 0)
    assert validity.reasons(klass, "tlp") == {}
    assert validity.rate(klass, "tlp") == VALIDITY_PRIOR_INVALID / VALIDITY_PRIOR_TESTS
    for outcome, reason in (
        ("pass", None),
        ("invalid", "not_applicable"),
        ("fail", None),
        ("invalid", "not_applicable"),
        ("invalid", "query_error"),
    ):
        validity.observe(klass, "tlp", outcome, reason)
    assert validity.counts(klass, "tlp") == (5, 3)
    assert validity.rate(klass, "tlp") == (3 + VALIDITY_PRIOR_INVALID) / (5 + VALIDITY_PRIOR_TESTS)
    assert validity.reasons(klass, "tlp") == {"not_applicable": 2, "query_error": 1}
    assert list(validity.reasons(klass, "tlp")) == ["not_applicable", "query_error"]
    assert validity.counts(klass, "cross_dbms") == (0, 0)
    assert validity.counts("datafusion|plain", "tlp") == (0, 0)


def test_validity_rejects_without_counting() -> None:
    validity = Validity()
    validity.observe("datafusion|plain", "tlp", "pass")
    rejected = (
        ("datafusion|plain", "nope", "pass", None),
        ("datafusion|plain", "tlp", "maybe", None),
        ("datafusion|plain", "tlp", "invalid", None),
        ("datafusion|plain", "tlp", "invalid", ""),
        ("datafusion|plain", "tlp", "pass", "timeout"),
        ("datafusion|plain", "tlp", "fail", "timeout"),
        ("", "tlp", "pass", None),
    )
    for args in rejected:
        with pytest.raises(ValueError):
            validity.observe(*args)
    assert validity.counts("datafusion|plain", "tlp") == (1, 0)
    assert validity.reasons("datafusion|plain", "tlp") == {}


def test_validity_round_trip_sorts_every_level() -> None:
    validity = Validity()
    validity.observe("b|x", "tlp", "invalid", "query_error")
    validity.observe("a|x", "cross_dbms", "pass")
    validity.observe("a|x", "tlp", "invalid", "timeout")
    validity.observe("a|x", "tlp", "invalid", "not_applicable")
    exported = validity.to_dict()
    assert list(exported) == ["a|x", "b|x"]
    assert list(exported["a|x"]) == ["cross_dbms", "tlp"]
    assert list(exported["a|x"]["tlp"]["reasons"]) == ["not_applicable", "timeout"]
    assert json.loads(json.dumps(exported)) == exported
    loaded = Validity.from_dict(json.loads(json.dumps(exported)))
    assert loaded.to_dict() == exported
    loaded.observe("a|x", "tlp", "pass")
    assert validity.counts("a|x", "tlp") == (2, 2)
    assert loaded.counts("a|x", "tlp") == (3, 2)


@pytest.mark.parametrize(
    "bad",
    [
        {"c": {"tlp": {"tested": 1, "invalid": 1, "reasons": {}}}},
        {"c": {"tlp": {"tested": 2, "invalid": 1, "reasons": {"query_error": 2}}}},
        {"c": {"tlp": {"tested": 1, "invalid": 2, "reasons": {"query_error": 2}}}},
        {"c": {"tlp": {"tested": 1, "invalid": 1, "reasons": {"": 1}}}},
        {"c": {"tlp": {"tested": True, "invalid": 0, "reasons": {}}}},
        {"c": {"nope": {"tested": 0, "invalid": 0, "reasons": {}}}},
        {"c": {"tlp": {"tested": 0, "invalid": 0}}},
        {"": {}},
        [],
    ],
)
def test_validity_from_dict_rejects(bad: object) -> None:
    with pytest.raises(ValueError):
        Validity.from_dict(bad)


def test_experiment_class_uses_only_the_statement_layer() -> None:
    assert experiment_class(phi(X1)) == "datafusion|set_op_all"
    assert experiment_class(phi(X6)) == "datafusion|set_op"
    assert experiment_class(phi(PLAIN)) == "datafusion|plain"
    assert experiment_class(phi((EXC_ALL, SELECT), engine="postgres", layers=AST_ONLY)) == "postgres|set_op_all"
