"""Residual model R: unexplained failures per phi unit."""

from __future__ import annotations

from typing import Any

from .constants import RESIDUAL_PRIOR_FAILS, RESIDUAL_PRIOR_TESTS

_OUTCOMES = ("pass", "fail")


def _count(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name}: expected a non-negative integer, got {value!r}")
    return value


class Residual:
    """How often each unit was tested, and how often it failed with no hypothesis."""

    def __init__(self) -> None:
        self._counts: dict[str, tuple[int, int]] = {}

    def observe(self, unit: str, y: str) -> None:
        """Count one valid outcome. ``fail`` is an unexplained failure."""
        if not isinstance(unit, str) or unit == "":
            raise ValueError(f"unit: expected a non-empty string, got {unit!r}")
        if y not in _OUTCOMES:
            raise ValueError(f"y: expected one of {_OUTCOMES}, got {y!r}")
        tested, unexplained = self._counts.get(unit, (0, 0))
        tested += 1
        if y == "fail":
            unexplained += 1
        self._counts[unit] = (tested, unexplained)

    def counts(self, unit: str) -> tuple[int, int]:
        """``(tested, unexplained)``. An unseen unit is ``(0, 0)``."""
        if not isinstance(unit, str):
            return (0, 0)
        return self._counts.get(unit, (0, 0))

    def rate(self, unit: str) -> float:
        """Residual failure rate. Strictly inside (0, 1), prior 0.01 when untested."""
        tested, unexplained = self.counts(unit)
        return float((unexplained + RESIDUAL_PRIOR_FAILS) / (tested + RESIDUAL_PRIOR_TESTS))

    def to_dict(self) -> dict[str, dict[str, int]]:
        """Seen units only, sorted by name."""
        return {
            unit: {"tested": tested, "unexplained": unexplained}
            for unit, (tested, unexplained) in sorted(self._counts.items())
        }

    @classmethod
    def from_dict(cls, data: Any) -> Residual:
        """Restore a detached residual. Reject a row whose counts cannot have happened."""
        if not isinstance(data, dict):
            raise ValueError(f"residual: expected an object, got {data!r}")
        restored = cls()
        for unit, row in data.items():
            if not isinstance(unit, str) or unit == "":
                raise ValueError(f"residual: expected a non-empty unit name, got {unit!r}")
            if not isinstance(row, dict) or set(row) != {"tested", "unexplained"}:
                raise ValueError(f"residual: {unit!r} must have tested and unexplained, got {row!r}")
            tested = _count(row["tested"], "tested")
            unexplained = _count(row["unexplained"], "unexplained")
            if unexplained > tested:
                raise ValueError(
                    f"residual: unexplained {unexplained} exceeds tested {tested} for {unit!r}"
                )
            restored._counts[unit] = (tested, unexplained)
        return restored
