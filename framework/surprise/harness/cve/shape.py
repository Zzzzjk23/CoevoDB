"""Behavior-shape names shared by the CVE pipeline."""

from __future__ import annotations

CVE_STEPS = ("rerun", "premise", "attribution", "minimize", "profile")


def behavior_shape(behavior: dict) -> str:
    """``missing_only``, ``extra_only``, ``both``, or ``none``.

    An empty mapping is ``none``. Non-numeric counts are treated as zero.
    """
    missing = _count(behavior, "missing")
    extra = _count(behavior, "extra")
    if missing > 0 and extra == 0:
        return "missing_only"
    if extra > 0 and missing == 0:
        return "extra_only"
    if missing > 0 and extra > 0:
        return "both"
    return "none"


def _count(behavior: dict, name: str) -> int:
    if not isinstance(behavior, dict):
        return 0
    value = behavior.get(name, 0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(value)
