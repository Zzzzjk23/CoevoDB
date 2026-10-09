"""Whether a failure is a positive example of one hypothesis."""

from __future__ import annotations

from typing import Any

from surprise.harness.cve.shape import behavior_shape

from .contracts import Hypothesis


def _mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    return None


def _attribution_consistent(hypothesis: Hypothesis, cve: dict[str, Any]) -> bool | None:
    """The bool from a tier-2 test of this hypothesis, or None when there is none."""
    attribution = _mapping(cve.get("attribution"))
    if attribution is None or attribution.get("status") != "ran":
        return None
    if attribution.get("hypothesis_id") != hypothesis.hypothesis_id:
        return None
    consistent = attribution.get("consistent")
    if not isinstance(consistent, bool):
        return None
    return consistent


def _fix_set_agrees(hypothesis: Hypothesis, cve: dict[str, Any]) -> bool | None:
    profile = _mapping(cve.get("profile"))
    if profile is None or profile.get("status") != "ran":
        return None
    fix_set = profile.get("fix_set")
    if isinstance(fix_set, str) or not isinstance(fix_set, (list, tuple)):
        return None
    if not all(isinstance(item, str) for item in fix_set):
        return None
    return set(fix_set) == set(hypothesis.interventions)


def identity_match(hypothesis: Hypothesis, label: Any) -> bool | None:
    """True when this failure has the same identity as ``hypothesis``.

    A tier-2 attribution of this hypothesis decides. Otherwise a hypothesis
    that names interventions compares fix sets, and one that does not compares
    ``fail_kind``, ``error_class`` and ``behavior_shape``. ``None`` means the
    identity cannot be decided. ``label.y`` other than ``fail`` raises
    ``ValueError``.
    """
    if getattr(label, "y", None) != "fail":
        raise ValueError(f"identity_match requires a fail label, got {getattr(label, 'y', None)!r}")
    cve = _mapping(getattr(label, "cve", None))
    if cve is not None:
        consistent = _attribution_consistent(hypothesis, cve)
        if consistent is not None:
            return consistent
    if hypothesis.interventions:
        if cve is None:
            return None
        return _fix_set_agrees(hypothesis, cve)
    identity = getattr(label, "identity", None)
    behavior = getattr(identity, "behavior", {})
    return (
        hypothesis.fail_kind == getattr(label, "fail_kind", None)
        and hypothesis.error_class == getattr(identity, "error_class", None)
        and hypothesis.behavior_shape == behavior_shape(behavior if isinstance(behavior, dict) else {})
    )
