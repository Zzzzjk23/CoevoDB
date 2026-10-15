"""Median, Mann-Whitney U and Vargha-Delaney A12, from the standard library only.

The exact Mann-Whitney test is the two-sided exact distribution used when the
combined sample has no ties and at most 20 values. Every other case uses the
normal approximation with the tie correction and a continuity correction, the
same pair ``scipy.stats.mannwhitneyu(..., method="asymptotic", use_continuity=True)``
reports. ``scipy`` is not imported here.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any


def median(values: Sequence[float]) -> float | None:
    """Middle value. An even count averages the two middle values. Empty is ``None``."""
    if len(values) == 0:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return float(ordered[mid])
    return (float(ordered[mid - 1]) + float(ordered[mid])) / 2.0


def summarize(values: Sequence[float | None]) -> dict[str, Any]:
    """``n``, ``median``, ``min`` and ``max`` after dropping ``None``.

    An empty sample has ``n`` 0 and the other three ``None``.
    """
    present = [value for value in values if value is not None]
    if not present:
        return {"n": 0, "median": None, "min": None, "max": None}
    return {
        "n": len(present),
        "median": median(present),
        "min": float(min(present)),
        "max": float(max(present)),
    }


def a12(x: Sequence[float], y: Sequence[float]) -> float | None:
    """Vargha-Delaney A12 of ``x`` against ``y``. Either sample empty is ``None``."""
    if len(x) == 0 or len(y) == 0:
        return None
    return _pair_wins(x, y) / (len(x) * len(y))


def mann_whitney_u(x: Sequence[float], y: Sequence[float]) -> dict[str, Any] | None:
    """Two-sided Mann-Whitney U of ``x`` against ``y``.

    ``u`` counts pairs where a value of ``x`` is greater than a value of ``y``,
    plus one half for each tie. Either sample empty is ``None``. ``method`` is
    ``exact`` or ``asymptotic``. ``p`` is never greater than 1.
    """
    if len(x) == 0 or len(y) == 0:
        return None
    u = _pair_wins(x, y)
    n1 = len(x)
    n2 = len(y)
    combined = list(x) + list(y)
    if len(set(combined)) == len(combined) and n1 + n2 <= 20:
        return {"u": u, "p": _exact_p(n1, n2, u), "method": "exact"}
    return {"u": u, "p": _asymptotic_p(n1, n2, u, combined), "method": "asymptotic"}


def _pair_wins(x: Sequence[float], y: Sequence[float]) -> float:
    wins = 0.0
    for left in x:
        for right in y:
            if left > right:
                wins += 1.0
            elif left == right:
                wins += 0.5
    return wins


def _exact_p(n1: int, n2: int, observed: float) -> float:
    """Two-sided exact p from the null distribution of U.

    Values are processed from small to large. Placing the next value in ``x``
    makes it beat every value already placed in ``y``, which is the same count
    as enumerating the ``C(n1 + n2, n1)`` splits.
    """
    counts: dict[tuple[int, int], int] = {(0, 0): 1}
    for seen in range(n1 + n2):
        nxt: dict[tuple[int, int], int] = {}
        for (taken, score), ways in counts.items():
            in_y = seen - taken
            if taken < n1:
                key = (taken + 1, score + in_y)
                nxt[key] = nxt.get(key, 0) + ways
            if in_y < n2:
                key = (taken, score)
                nxt[key] = nxt.get(key, 0) + ways
        counts = nxt
    total = 0
    low = 0
    high = 0
    for (taken, score), ways in counts.items():
        if taken != n1:
            continue
        total += ways
        if score <= observed:
            low += ways
        if score >= observed:
            high += ways
    return min(1.0, 2.0 * min(low, high) / total)


def _asymptotic_p(n1: int, n2: int, u: float, combined: Sequence[float]) -> float:
    """Normal approximation with the tie correction and a continuity correction.

    The continuity correction moves the larger of ``U`` and ``n1*n2 - U`` half
    a unit toward the mean, then the two-sided p is ``min(1, 2 * (1 - Phi(z)))``.
    Every value equal makes ``sigma`` 0 and the p-value 1.
    """
    n = n1 + n2
    tie_counts: dict[float, int] = {}
    for value in combined:
        tie_counts[value] = tie_counts.get(value, 0) + 1
    tie_term = sum(count ** 3 - count for count in tie_counts.values())
    sigma = math.sqrt(n1 * n2 / 12.0 * ((n + 1) - tie_term / (n * (n - 1))))
    if sigma == 0.0:
        return 1.0
    mu = n1 * n2 / 2.0
    larger = max(u, n1 * n2 - u)
    z = (larger - mu - 0.5) / sigma
    return min(1.0, math.erfc(z / math.sqrt(2.0)))
