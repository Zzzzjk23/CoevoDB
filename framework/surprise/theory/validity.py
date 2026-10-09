"""Validity model K^v: how often an experiment class is invalid under an oracle."""

from __future__ import annotations

from typing import Any

from surprise.features.phi import Phi
from surprise.features.registry import Registry
from surprise.features.units import unit_parts
from surprise.harness.contracts import LABELS, ORACLE_IDS

from .constants import VALIDITY_PRIOR_INVALID, VALIDITY_PRIOR_TESTS


def experiment_class(phi: Phi, registry: Registry | None = None) -> str:
    """``engine|construct``. The construct is read from the statement layer."""
    return f"{phi.engine}|{unit_parts(phi, registry)[0]}"


def _count(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name}: expected a non-negative integer, got {value!r}")
    return value


class Validity:
    """Invalid rate of one experiment class under one oracle, with reasons kept apart."""

    def __init__(self) -> None:
        # class -> oracle -> (tested, invalid, reason -> count)
        self._cells: dict[str, dict[str, tuple[int, int, dict[str, int]]]] = {}

    def observe(self, experiment_class: str, oracle: str, y: str, invalid_reason: str | None = None) -> None:
        """Count one experiment. An invalid outcome must name its reason; other labels must not."""
        if not isinstance(experiment_class, str) or experiment_class == "":
            raise ValueError(f"experiment_class: expected a non-empty string, got {experiment_class!r}")
        if oracle not in ORACLE_IDS:
            raise ValueError(f"oracle: must be one of {ORACLE_IDS}, got {oracle!r}")
        if y not in LABELS:
            raise ValueError(f"y: must be one of {LABELS}, got {y!r}")
        if y == "invalid":
            if not isinstance(invalid_reason, str) or invalid_reason == "":
                raise ValueError(f"invalid_reason: required when y is 'invalid', got {invalid_reason!r}")
        elif invalid_reason is not None:
            raise ValueError(f"invalid_reason: must be absent unless y is 'invalid', got {invalid_reason!r}")
        tested, invalid, reasons = self._cell(experiment_class, oracle)
        reasons = dict(reasons)
        tested += 1
        if y == "invalid":
            invalid += 1
            reason = invalid_reason
            reasons[reason] = reasons.get(reason, 0) + 1
        self._cells.setdefault(experiment_class, {})[oracle] = (tested, invalid, reasons)

    def counts(self, experiment_class: str, oracle: str) -> tuple[int, int]:
        """``(tested, invalid)``. An untried pair is ``(0, 0)``."""
        tested, invalid, _reasons = self._cell(experiment_class, oracle)
        return (tested, invalid)

    def reasons(self, experiment_class: str, oracle: str) -> dict[str, int]:
        """Invalid-reason counts, sorted by reason. An untried pair is empty."""
        _tested, _invalid, reasons = self._cell(experiment_class, oracle)
        return {name: reasons[name] for name in sorted(reasons)}

    def rate(self, experiment_class: str, oracle: str) -> float:
        """Invalid rate. The prior is 0.1 when the pair has not been tried."""
        tested, invalid = self.counts(experiment_class, oracle)
        return float((invalid + VALIDITY_PRIOR_INVALID) / (tested + VALIDITY_PRIOR_TESTS))

    def to_dict(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Classes, oracles, and reasons sorted at each level."""
        exported: dict[str, dict[str, dict[str, Any]]] = {}
        for experiment_class in sorted(self._cells):
            exported[experiment_class] = {}
            for oracle in sorted(self._cells[experiment_class]):
                tested, invalid, reasons = self._cells[experiment_class][oracle]
                exported[experiment_class][oracle] = {
                    "tested": tested,
                    "invalid": invalid,
                    "reasons": {name: reasons[name] for name in sorted(reasons)},
                }
        return exported

    @classmethod
    def from_dict(cls, data: Any) -> Validity:
        """Restore a detached model. ``reasons`` must add up to ``invalid``."""
        if not isinstance(data, dict):
            raise ValueError(f"validity: expected an object, got {data!r}")
        restored = cls()
        for experiment_class, oracles in data.items():
            if not isinstance(experiment_class, str) or experiment_class == "":
                raise ValueError(f"validity: expected a non-empty class, got {experiment_class!r}")
            if not isinstance(oracles, dict):
                raise ValueError(f"validity: {experiment_class!r} must map oracles to rows, got {oracles!r}")
            restored._cells[experiment_class] = {}
            for oracle, row in oracles.items():
                if oracle not in ORACLE_IDS:
                    raise ValueError(f"validity: unknown oracle {oracle!r}")
                if not isinstance(row, dict) or set(row) != {"tested", "invalid", "reasons"}:
                    raise ValueError(
                        f"validity: {experiment_class!r}/{oracle!r} must have tested, invalid, reasons, got {row!r}"
                    )
                tested = _count(row["tested"], "tested")
                invalid = _count(row["invalid"], "invalid")
                if invalid > tested:
                    raise ValueError(
                        f"validity: invalid {invalid} exceeds tested {tested} for {experiment_class!r}/{oracle!r}"
                    )
                reasons = _reasons(row["reasons"], invalid)
                restored._cells[experiment_class][oracle] = (tested, invalid, reasons)
        return restored

    def _cell(self, experiment_class: str, oracle: str) -> tuple[int, int, dict[str, int]]:
        return self._cells.get(experiment_class, {}).get(oracle, (0, 0, {}))


def _reasons(value: object, invalid: int) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ValueError(f"reasons: expected an object, got {value!r}")
    reasons: dict[str, int] = {}
    for name, count in value.items():
        if not isinstance(name, str) or name == "":
            raise ValueError(f"reasons: expected a non-empty reason, got {name!r}")
        reasons[name] = _count(count, "reasons")
    if sum(reasons.values()) != invalid:
        raise ValueError(f"reasons: counts add up to {sum(reasons.values())}, invalid is {invalid}")
    return reasons
