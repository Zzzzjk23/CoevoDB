"""Hand-written attribution hypotheses. The harness does not import the theory layer."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParsedHypothesis:
    """The fields tier 2 reads. Every other key on the input mapping is ignored."""

    hypothesis_id: str
    engine: str
    interventions: tuple[str, ...]
    fail_kind: str | None
    error_class: str | None
    behavior_shape: str | None
    has_fail_kind: bool
    has_error_class: bool
    has_behavior_shape: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "engine": self.engine,
            "interventions": list(self.interventions),
            "fail_kind": self.fail_kind,
            "error_class": self.error_class,
            "behavior_shape": self.behavior_shape,
            "has_fail_kind": self.has_fail_kind,
            "has_error_class": self.has_error_class,
            "has_behavior_shape": self.has_behavior_shape,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParsedHypothesis:
        interventions = data.get("interventions")
        if not isinstance(interventions, list) or not all(isinstance(item, str) for item in interventions):
            raise ValueError("hypothesis: interventions must be a list of strings")
        return cls(
            hypothesis_id=str(data["hypothesis_id"]),
            engine=str(data["engine"]),
            interventions=tuple(interventions),
            fail_kind=data.get("fail_kind"),
            error_class=data.get("error_class"),
            behavior_shape=data.get("behavior_shape"),
            has_fail_kind=bool(data.get("has_fail_kind")),
            has_error_class=bool(data.get("has_error_class")),
            has_behavior_shape=bool(data.get("has_behavior_shape")),
        )


def parse_hypothesis(hypothesis: Any, engine: str) -> ParsedHypothesis:
    """Validate ``hypothesis`` against ``engine``. Raise ``ValueError`` when it is unusable.

    This does not ask the engine which intervention names exist. Call
    :func:`ensure_known` with the names the engine reports.
    """
    if isinstance(hypothesis, (str, bytes)) or not isinstance(hypothesis, Mapping):
        raise ValueError("hypothesis: must be a mapping")
    hypothesis_id = hypothesis.get("hypothesis_id")
    if not isinstance(hypothesis_id, str) or hypothesis_id == "":
        raise ValueError("hypothesis: hypothesis_id must be a non-empty string")
    given_engine = hypothesis.get("engine")
    if not isinstance(given_engine, str) or given_engine == "":
        raise ValueError("hypothesis: engine must be a non-empty string")
    if given_engine != engine:
        raise ValueError(f"hypothesis: engine must be {engine!r}, got {given_engine!r}")
    if "interventions" not in hypothesis:
        raise ValueError("hypothesis: interventions is required")
    interventions = hypothesis.get("interventions")
    if not isinstance(interventions, list) or not all(isinstance(item, str) for item in interventions):
        raise ValueError("hypothesis: interventions must be a list of strings")

    has_fail_kind = "fail_kind" in hypothesis
    has_error_class = "error_class" in hypothesis
    has_behavior_shape = "behavior_shape" in hypothesis
    fail_kind = hypothesis.get("fail_kind") if has_fail_kind else None
    error_class = hypothesis.get("error_class") if has_error_class else None
    behavior_shape = hypothesis.get("behavior_shape") if has_behavior_shape else None
    if has_fail_kind and fail_kind is not None and not isinstance(fail_kind, str):
        raise ValueError("hypothesis: fail_kind must be a string or null")
    if has_error_class and error_class is not None and not isinstance(error_class, str):
        raise ValueError("hypothesis: error_class must be a string or null")
    if has_behavior_shape and behavior_shape is not None and not isinstance(behavior_shape, str):
        raise ValueError("hypothesis: behavior_shape must be a string or null")
    if not interventions and not (has_fail_kind or has_error_class or has_behavior_shape):
        raise ValueError("hypothesis: an empty intervention list needs fail_kind, error_class, or behavior_shape")
    return ParsedHypothesis(
        hypothesis_id=hypothesis_id,
        engine=given_engine,
        interventions=tuple(interventions),
        fail_kind=fail_kind if isinstance(fail_kind, str) else None,
        error_class=error_class if isinstance(error_class, str) else None,
        behavior_shape=behavior_shape if isinstance(behavior_shape, str) else None,
        has_fail_kind=has_fail_kind,
        has_error_class=has_error_class,
        has_behavior_shape=has_behavior_shape,
    )


def ensure_known(parsed: ParsedHypothesis, names: list[str]) -> None:
    """Raise ``ValueError`` when ``parsed`` names an intervention outside ``names``."""
    known = set(names)
    unknown = [name for name in parsed.interventions if name not in known]
    if unknown:
        raise ValueError(f"hypothesis: unknown interventions {unknown}")
