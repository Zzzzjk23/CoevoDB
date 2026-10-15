"""Surprise curve of one run, and the teeth of that curve.

A tooth is a window that is a local high point: within ``width`` windows it
has risen by at least ``amplitude`` bits and then fallen by that much. On a
flat top the leftmost index is the tooth.
"""

from __future__ import annotations

from collections.abc import Sequence

from surprise.harness.contracts import ExperimentRecord
from surprise.theory.predict import surprise_bits


def record_surprise(record: ExperimentRecord) -> float | None:
    """Surprise of one execution, in bits. Invalid outcomes and missing predictions are ``None``."""
    if record.label.y == "invalid" or record.p_t is None:
        return None
    return surprise_bits(record.p_t, record.label.y)


def surprise_curve(records: Sequence[ExperimentRecord], window: int = 100) -> list[float | None]:
    """Mean surprise of each whole window, in the order given. A short tail is dropped.

    A window whose executions are all invalid, or all without ``p_t``, is ``None``.
    """
    if isinstance(window, bool) or not isinstance(window, int) or window < 1:
        raise ValueError(f"window: expected an integer >= 1, got {window!r}")
    curve: list[float | None] = []
    for start in range(0, len(records) - window + 1, window):
        values = [
            value
            for value in (record_surprise(record) for record in records[start : start + window])
            if value is not None
        ]
        curve.append(None if not values else sum(values) / len(values))
    return curve


def _present(curve: Sequence[float | None], start: int, stop: int) -> list[float]:
    """Non-None values on the half-open index interval, ignoring indexes outside the curve."""
    found: list[float] = []
    for index in range(max(start, 0), min(stop, len(curve))):
        value = curve[index]
        if value is not None:
            found.append(value)
    return found


def teeth(curve: Sequence[float | None], amplitude: float = 0.25, width: int = 5) -> list[int]:
    """Indexes of teeth, ascending.

    Index ``k`` is a tooth when ``curve[k]`` is a number, both sides have a
    number inside ``width`` windows, it is strictly above every value on the
    left and at least as high as every value on the right, and it stands at
    least ``amplitude`` bits above the lowest value on each side.
    """
    found: list[int] = []
    limit = amplitude - 1e-12
    for index, value in enumerate(curve):
        if value is None:
            continue
        left = _present(curve, index - width, index)
        right = _present(curve, index + 1, index + width + 1)
        if not left or not right:
            continue
        if value <= max(left) or value < max(right):
            continue
        if value - min(left) < limit or value - min(right) < limit:
            continue
        found.append(index)
    return found
