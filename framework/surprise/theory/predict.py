"""Prediction, surprise of a valid outcome, and the six-way triage."""

from __future__ import annotations

import math
from dataclasses import dataclass

from surprise.harness.contracts import LABELS

from .constants import TRIAGE_HIGH_BITS, TRIAGE_LOW_BITS

ZONES = ("confirmed", "pending", "unexplored")
TRIAGE_KINDS = (
    "new_family",
    "unexpected_pass",
    "boundary_move",
    "duplicate",
    "no_information",
    "invalid",
)


def _probability(value: object, name: str) -> float:
    """A real number strictly inside (0, 1). Booleans are not numbers here."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name}: expected a number strictly between 0 and 1, got {value!r}")
    if not 0.0 < value < 1.0:
        raise ValueError(f"{name}: expected a number strictly between 0 and 1, got {value!r}")
    return float(value)


def surprise_bits(p_fail_valid: float, y: str) -> float | None:
    """Surprise of a valid outcome, in bits, conditional on the outcome being valid.

    K^v is not folded in: an invalid experiment has no surprise. The five
    magnitudes in the framework document are ``-log2`` of 0.01, 0.05, 0.5, 0.95
    and 0.99.
    """
    if y not in LABELS:
        raise ValueError(f"y: must be one of {LABELS}, got {y!r}")
    probability = _probability(p_fail_valid, "p_fail_valid")
    if y == "invalid":
        return None
    if y == "fail":
        return -math.log2(probability)
    return -math.log2(1.0 - probability)


def triage(y: str, bits: float | None) -> str:
    """Classify one outcome by how large its surprise is.

    Both thresholds belong to the higher band: ``bits == 2`` is a new family
    or an unexpected pass, and ``bits == 0.5`` is a boundary move.
    """
    if y not in LABELS:
        raise ValueError(f"y: must be one of {LABELS}, got {y!r}")
    if y == "invalid":
        if bits is not None:
            raise ValueError(f"bits: an invalid outcome has no surprise, got {bits!r}")
        return "invalid"
    if bits is None or isinstance(bits, bool) or not isinstance(bits, (int, float)):
        raise ValueError(f"bits: expected a non-negative finite number, got {bits!r}")
    if not math.isfinite(bits) or bits < 0:
        raise ValueError(f"bits: expected a non-negative finite number, got {bits!r}")
    if bits >= TRIAGE_HIGH_BITS:
        return "new_family" if y == "fail" else "unexpected_pass"
    if bits >= TRIAGE_LOW_BITS:
        return "boundary_move"
    return "duplicate" if y == "fail" else "no_information"


def _names(value: object, name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{name}: expected a sequence of strings, got {value!r}")
    names: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{name}: expected strings, got {item!r}")
        names.append(item)
    return tuple(names)


@dataclass(frozen=True)
class Prediction:
    """What the theory expects before one experiment runs. It does not learn."""

    engine: str
    oracle: str
    unit: str
    experiment_class: str
    zone: str
    hypothesis_id: str | None
    confirmed: tuple[str, ...]
    pending: tuple[str, ...]
    p_fail_valid: float
    p_invalid: float

    def __post_init__(self) -> None:
        for name in ("engine", "oracle", "unit", "experiment_class"):
            value = getattr(self, name)
            if not isinstance(value, str) or value == "":
                raise ValueError(f"{name}: expected a non-empty string, got {value!r}")
        if self.zone not in ZONES:
            raise ValueError(f"zone: must be one of {ZONES}, got {self.zone!r}")
        if self.hypothesis_id is not None and (
            not isinstance(self.hypothesis_id, str) or self.hypothesis_id == ""
        ):
            raise ValueError(f"hypothesis_id: expected a string or None, got {self.hypothesis_id!r}")
        object.__setattr__(self, "confirmed", _names(self.confirmed, "confirmed"))
        object.__setattr__(self, "pending", _names(self.pending, "pending"))
        object.__setattr__(self, "p_fail_valid", _probability(self.p_fail_valid, "p_fail_valid"))
        object.__setattr__(self, "p_invalid", _probability(self.p_invalid, "p_invalid"))

    @property
    def p_fail(self) -> float:
        """``P_T(fail | x) = (1 - K^v(x)) * P(fail | valid)``."""
        return (1.0 - self.p_invalid) * self.p_fail_valid

    @property
    def p_pass(self) -> float:
        """Probability the experiment is valid and passes."""
        return (1.0 - self.p_invalid) * (1.0 - self.p_fail_valid)

    def surprise(self, y: str) -> float | None:
        """Surprise of ``y`` given this prediction. Invalid yields ``None``."""
        return surprise_bits(self.p_fail_valid, y)

    def to_dict(self) -> dict[str, object]:
        """The ten fields plus ``p_fail`` and ``p_pass``. Tuples become lists."""
        return {
            "engine": self.engine,
            "oracle": self.oracle,
            "unit": self.unit,
            "experiment_class": self.experiment_class,
            "zone": self.zone,
            "hypothesis_id": self.hypothesis_id,
            "confirmed": list(self.confirmed),
            "pending": list(self.pending),
            "p_fail_valid": self.p_fail_valid,
            "p_invalid": self.p_invalid,
            "p_fail": self.p_fail,
            "p_pass": self.p_pass,
        }
