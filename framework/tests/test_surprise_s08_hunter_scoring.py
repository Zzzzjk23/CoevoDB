"""Numeric scoring for the Hunter: entropy, D, U, novelty, adjacency, value."""

from __future__ import annotations

import math
import shutil
import tempfile

import pytest

from surprise.gates import s07 as G7
from surprise.gates import s08_cases as C
from surprise.hunter import constants as HC
from surprise.hunter import scoring as S
from surprise.theory import ZONES, constants as TC


def test_binary_entropy_bits_and_boundaries() -> None:
    assert S.binary_entropy(0.5) == pytest.approx(1.0)
    assert S.binary_entropy(0.0) == 0.0
    assert S.binary_entropy(1.0) == 0.0
    assert S.binary_entropy(-0.1) == 0.0
    assert S.binary_entropy(1.1) == 0.0
    p = 0.11
    assert S.binary_entropy(p) == pytest.approx(-(p * math.log2(p) + (1 - p) * math.log2(1 - p)))
    assert isinstance(S.binary_entropy(0.5), float)


def test_optimistic_rate_matches_the_gate_table() -> None:
    for (tested, unexplained), expected in C.OPTIMISTIC.items():
        got = S.optimistic_rate(tested, unexplained)
        assert got == pytest.approx(expected)
        assert isinstance(got, float)
        assert got <= 0.5
    rho = (0 + TC.RESIDUAL_PRIOR_FAILS) / (0 + TC.RESIDUAL_PRIOR_TESTS)
    assert S.optimistic_rate(0, 0) == pytest.approx(min(0.5, rho + math.sqrt(rho * (1 - rho) / 1)))


def test_uncertainty_adjacent_prior_and_cap() -> None:
    plain = S.uncertainty(0, 0, False)
    adj = S.uncertainty(0, 0, True)
    assert plain == pytest.approx(S.binary_entropy(C.OPTIMISTIC[(0, 0)]))
    assert adj == pytest.approx(S.binary_entropy(min(0.5, 2.0 * C.OPTIMISTIC[(0, 0)])))
    assert adj > plain > S.uncertainty(99, 0, False)
    assert S.uncertainty(100, 100, False) == pytest.approx(1.0)
    assert S.uncertainty(100, 100, True) == pytest.approx(1.0)


def test_disagreement_is_one_bit_in_pending_only() -> None:
    assert [S.disagreement(zone) for zone in ZONES] == [0.0, 1.0, 0.0]
    with pytest.raises(ValueError):
        S.disagreement("outside")


def test_downweight_and_value() -> None:
    assert S.downweight(0) == pytest.approx(1.0)
    assert S.downweight(50) == pytest.approx(0.5)
    assert S.downweight(150) == pytest.approx(0.25)
    assert S.value(0.1, 1.0, 0.0, 2.0, 0) == pytest.approx(0.9)
    assert S.value(0.2, 0.0, 0.5, 2.0, 50) == pytest.approx(0.8 * 1.0 * 0.5)
    assert S.value(0.3, 0.0, 0.0, 4.0, 0) == 0.0
    assert isinstance(S.value(0.1, 1.0, 0.0, 2.0, 0), float)


def test_jaccard_novelty_and_accept_probability() -> None:
    a, b = frozenset({"x", "y", "z"}), frozenset({"y", "z", "w"})
    assert S.jaccard(a, b) == pytest.approx(0.5)
    assert S.jaccard(frozenset(), frozenset()) == 1.0
    assert S.novelty(a, [b, frozenset({"q"})]) == pytest.approx(0.5)
    assert S.novelty(a, []) == 1.0
    assert S.novelty(a, [a]) == 0.0
    assert S.accept_probability(0.0) == pytest.approx(HC.NOVELTY_FLOOR)
    assert S.accept_probability(1.0) == pytest.approx(1.0)
    assert S.accept_probability(0.5) == pytest.approx(0.2 + 0.8 * 0.5)


def test_explore_slot_every_fifth_choice() -> None:
    assert [i for i in range(0, 21) if S.is_explore_slot(i)] == [5, 10, 15, 20]
    assert S.is_explore_slot(1) is False
    assert S.is_explore_slot(5) is True


def test_adjacent_same_engine_and_construct() -> None:
    unit = "duckdb|tlp|window|window|dups"
    assert S.adjacent("duckdb|norec|window|scan|plain", [unit])
    assert S.adjacent("duckdb|tlp|window|none|unknown", [unit])
    assert not S.adjacent(unit, [unit])
    assert not S.adjacent("duckdb|tlp|join|window|dups", [unit])
    assert not S.adjacent("datafusion|tlp|window|window|dups", [unit])
    assert not S.adjacent(unit, [])


def test_score_through_a_workbench_confirmed_pending_unexplored() -> None:
    tmp = tempfile.mkdtemp(prefix="s08-hunter-score-")
    try:
        wb, first = G7.opened_bench(tmp)
        units = S.hypothesis_units(wb)
        assert len(units) == 1
        assert next(iter(units)).startswith("datafusion|cross_dbms|")
        again = S.hypothesis_units(wb)
        assert again == units
        beta = 2.0
        conf = S.score(wb, G7.phi("x1"), "cross_dbms", beta=beta, probes={}, units=units)
        pend = S.score(wb, G7.phi("x3"), "cross_dbms", beta=beta, probes={first: 50}, units=units)
        other = S.score(wb, G7.phi("x1"), "tlp", beta=beta, probes={}, units=units)
        assert conf.prediction.zone == "confirmed" and conf.D == 0.0 and conf.U == 0.0 and conf.value == 0.0
        assert conf.adjacent is False and conf.probes == 0
        assert pend.prediction.zone == "pending" and pend.D == 1.0 and pend.U == 0.0 and pend.probes == 50
        assert pend.value == pytest.approx((1 - pend.prediction.p_invalid) * 1.0 * 0.5)
        assert other.prediction.zone == "unexplored" and other.adjacent and other.D == 0.0
        assert other.U == pytest.approx(S.uncertainty(0, 0, True))
        assert other.value == pytest.approx((1 - other.prediction.p_invalid) * beta * other.U)
        for item in (conf, pend, other):
            assert isinstance(item.D, float) and isinstance(item.U, float) and isinstance(item.value, float)
        skipped = S.hypothesis_units(wb)
        # a missing positive id is skipped: the opened family only has r1
        assert skipped == units
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
