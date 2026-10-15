"""Pure scoring for Hunter candidates: D, U, novelty, and expected surprise."""

from __future__ import annotations

import math
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass

from surprise.features.registry import default_registry
from surprise.features.units import unit_of
from .constants import ADJACENT_FACTOR, EXPLORE_EVERY, NOVELTY_FLOOR, PROBE_HALF
from surprise.theory.constants import RESIDUAL_PRIOR_FAILS, RESIDUAL_PRIOR_TESTS
from surprise.theory.predict import Prediction


@dataclass(frozen=True)
class Score:
    """Value of one (phi, oracle) pair under the current theory."""

    prediction: Prediction
    D: float
    U: float
    adjacent: bool
    probes: int
    value: float


def binary_entropy(p: float) -> float:
    """Binary entropy in bits. Degenerate probabilities carry no uncertainty."""
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return float(-(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p)))


def optimistic_rate(tested: int, unexplained: int) -> float:
    """Upper residual rate: prior mean plus one standard error, capped at 0.5."""
    rho = (unexplained + RESIDUAL_PRIOR_FAILS) / (tested + RESIDUAL_PRIOR_TESTS)
    return float(min(0.5, rho + math.sqrt(rho * (1.0 - rho) / (tested + 1))))


def uncertainty(tested: int, unexplained: int, adjacent: bool) -> float:
    """Residual uncertainty U, with an optimistic bump for a neighbouring unit."""
    rate = optimistic_rate(tested, unexplained)
    if adjacent:
        rate = min(0.5, ADJACENT_FACTOR * rate)
    return binary_entropy(rate)


def disagreement(zone: str) -> float:
    """Version-space disagreement D: one bit only between S and G."""
    if zone == "pending":
        return 1.0
    if zone in ("confirmed", "unexplored"):
        return 0.0
    raise ValueError(f"unknown zone: {zone!r}")


def downweight(probes: int) -> float:
    """1 / (1 + probes / PROBE_HALF): over-probed hypotheses lose value."""
    return float(1.0 / (1.0 + probes / PROBE_HALF))


def value(p_invalid: float, D: float, U: float, beta: float, probes: int) -> float:
    """P_valid * (D + beta * U) * downweight(probes)."""
    return float((1.0 - p_invalid) * (D + beta * U) * downweight(probes))


def jaccard(a: frozenset, b: frozenset) -> float:
    """Jaccard similarity. Two empty sets are identical."""
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return float(len(a & b) / len(union))


def novelty(features: frozenset, recent: Iterable[frozenset]) -> float:
    """1 minus the highest Jaccard similarity with a recent feature set."""
    window = list(recent)
    if not window:
        return 1.0
    return float(1.0 - max(jaccard(features, other) for other in window))


def accept_probability(nov: float) -> float:
    """Floor plus remaining mass times novelty."""
    return float(NOVELTY_FLOOR + (1.0 - NOVELTY_FLOOR) * nov)


def is_explore_slot(index: int) -> bool:
    """Every EXPLORE_EVERY-th choice, counting from 1, is reserved for exploration."""
    return index >= 1 and index % EXPLORE_EVERY == 0


def adjacent(unit: str, units: Iterable[str]) -> bool:
    """True when ``unit`` shares engine and construct with a known unit, but is not that unit."""
    known = list(units)
    if unit in known:
        return False
    parts = unit.split("|")
    if len(parts) < 3:
        return False
    engine, construct = parts[0], parts[2]
    for other in known:
        other_parts = other.split("|")
        if len(other_parts) >= 3 and other_parts[0] == engine and other_parts[2] == construct:
            return True
    return False


def hypothesis_units(wb, registry=None) -> frozenset[str]:
    """Units of every stored positive of every hypothesis. Missing record ids are skipped."""
    active = default_registry() if registry is None else registry
    by_id = {seen.record_id: seen for seen in wb.records()}
    found: list[str] = []
    seen_units: set[str] = set()
    for hypothesis in wb.theory.hypotheses:
        for record_id in hypothesis.positives:
            seen = by_id.get(record_id)
            if seen is None:
                continue
            unit = unit_of(seen.phi, seen.label.oracle, active)
            if unit not in seen_units:
                seen_units.add(unit)
                found.append(unit)
    return frozenset(found)


def score(wb, phi, oracle, *, beta: float, probes: Mapping[str, int], units: Collection[str]) -> Score:
    """Score one (phi, oracle) pair. U is computed only in the unexplored zone."""
    prediction = wb.predict(phi, oracle)
    d_bits = disagreement(prediction.zone)
    if prediction.zone == "unexplored":
        tested, unexplained = wb.theory.residual.counts(prediction.unit)
        is_adj = adjacent(prediction.unit, units)
        u_bits = uncertainty(tested, unexplained, is_adj)
    else:
        is_adj = False
        u_bits = 0.0
    n_probes = 0 if prediction.hypothesis_id is None else int(probes.get(prediction.hypothesis_id, 0))
    return Score(
        prediction=prediction,
        D=float(d_bits),
        U=float(u_bits),
        adjacent=bool(is_adj),
        probes=n_probes,
        value=value(prediction.p_invalid, d_bits, u_bits, beta, n_probes),
    )
