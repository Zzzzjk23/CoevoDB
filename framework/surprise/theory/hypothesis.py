"""Version-space updates on one hypothesis, and the deterministic start of a family."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from surprise.features.phi import Phi
from surprise.features.registry import Registry
from surprise.harness.cve.shape import behavior_shape

from .constants import VS_MAX_GENERAL
from .contracts import Hypothesis
from .vspace import (
    _canonical,
    _drop_redundant,
    _registry,
    covers,
    generalize,
    reduce_conjunction,
    specialize,
)


@dataclass(frozen=True)
class Update:
    """A hypothesis after one example, and the name of what the example did."""

    hypothesis: Hypothesis
    outcome: str


def _layer_status(phi: Phi, layer: str) -> str | None:
    layers = getattr(phi, "layers", None)
    if not isinstance(layers, Mapping):
        return None
    status = layers.get(layer)
    return status if isinstance(status, str) else None


def position(
    hypothesis: Hypothesis,
    phi: Phi,
    oracle: str | None,
    registry: Registry | None = None,
) -> str:
    """Where ``phi`` sits relative to ``hypothesis`` for this oracle.

    ``out_of_scope`` when the engine or the oracle differs, ``undetermined``
    when S mentions a layer this phi did not compute, then ``confirmed``,
    ``pending``, or ``outside``.
    """
    if hypothesis.engine != phi.engine or hypothesis.oracle != oracle:
        return "out_of_scope"
    for literal in hypothesis.specific:
        layer = literal.split(":", 1)[0]
        if _layer_status(phi, layer) not in ("ok", "fallback"):
            return "undetermined"
    active = _registry(registry)
    if covers(hypothesis.specific, phi, active):
        return "confirmed"
    for member in hypothesis.general:
        if covers(member, phi, active):
            return "pending"
    return "outside"


def _append(records: tuple[str, ...], record_id: str) -> tuple[str, ...]:
    if record_id in records:
        return records
    return (*records, record_id)


def apply_positive(
    hypothesis: Hypothesis,
    phi: Phi,
    record_id: str,
    registry: Registry | None = None,
) -> Update:
    """Generalise S with a positive example, or record a duplicate inside S."""
    active = _registry(registry)
    where = position(hypothesis, phi, hypothesis.oracle, active)
    if where == "confirmed":
        return Update(
            replace(hypothesis, positives=_append(hypothesis.positives, record_id)),
            "duplicate",
        )
    if where == "pending":
        kept = tuple(member for member in hypothesis.general if covers(member, phi, active))
        return Update(
            replace(
                hypothesis,
                specific=generalize(hypothesis.specific, phi, active),
                general=_canonical(kept),
                positives=_append(hypothesis.positives, record_id),
            ),
            "generalized",
        )
    return Update(hypothesis, where)


def apply_negative(
    hypothesis: Hypothesis,
    phi: Phi,
    record_id: str,
    registry: Registry | None = None,
) -> Update:
    """Specialise G with a negative example, or record a pass that lands inside S."""
    active = _registry(registry)
    where = position(hypothesis, phi, hypothesis.oracle, active)
    if where == "confirmed":
        return Update(
            replace(
                hypothesis,
                negatives=_append(hypothesis.negatives, record_id),
                contradictions=_append(hypothesis.contradictions, record_id),
            ),
            "contradiction",
        )
    if where == "pending":
        general = specialize(hypothesis.general, hypothesis.specific, phi, active)
        truncated = hypothesis.truncated
        if len(general) > VS_MAX_GENERAL:
            general = general[:VS_MAX_GENERAL]
            truncated = True
        return Update(
            replace(
                hypothesis,
                general=general,
                negatives=_append(hypothesis.negatives, record_id),
                truncated=truncated,
            ),
            "specialized",
        )
    return Update(hypothesis, where)


def converged(hypothesis: Hypothesis, registry: Registry | None = None) -> bool:
    """True when G, reduced and with redundant members dropped, is exactly S."""
    active = _registry(registry)
    reduced = [reduce_conjunction(member, active) for member in hypothesis.general]
    kept = _drop_redundant(reduced, active)
    return len(kept) == 1 and kept[0] == reduce_conjunction(hypothesis.specific, active)


def _ran_profile(label: Any) -> dict[str, Any]:
    if getattr(label, "y", None) != "fail":
        raise ValueError("new_family requires a fail label")
    cve = getattr(label, "cve", None)
    profile = cve.get("profile") if isinstance(cve, dict) else None
    if not isinstance(profile, dict) or profile.get("status") != "ran":
        raise ValueError("new_family requires a profile with status 'ran'")
    return profile


def _strings(value: Any, name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{name}: expected a list or tuple of strings, got {value!r}")
    if not all(isinstance(item, str) for item in value):
        raise ValueError(f"{name}: expected strings, got {value!r}")
    return tuple(value)


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name}: expected a string, got {value!r}")
    return value


def new_family(
    hypothesis_id: str,
    phi: Phi,
    label: Any,
    record_id: str,
    *,
    negatives: Iterable[tuple[Phi, str]] = (),
    source: str = "deterministic",
    registry: Registry | None = None,
) -> Hypothesis:
    """Start one active hypothesis from a profiled failure, then replay passes.

    ``negatives`` is a sequence of ``(phi, record_id)`` pairs. Each is applied
    with :func:`apply_negative`, so a pass that G already excludes leaves no trace.
    """
    profile = _ran_profile(label)
    active = _registry(registry)
    identity = getattr(label, "identity", None)
    behavior = getattr(identity, "behavior", {})
    error_class = getattr(identity, "error_class", None)
    family = Hypothesis(
        hypothesis_id=hypothesis_id,
        engine=phi.engine,
        interventions=_strings(profile.get("fix_set"), "fix_set"),
        plan_delta=_strings(profile.get("plan_diff"), "plan_diff"),
        versions={
            "ladder": _text(profile.get("version_ladder"), "version_ladder"),
            "fix_kind": _text(profile.get("fix_kind"), "fix_kind"),
            "witness_switches": list(_strings(profile.get("witness_switches"), "witness_switches")),
        },
        specific=reduce_conjunction(phi.features, active),
        general=((),),
        positives=(record_id,),
        negatives=(),
        source=source,
        status="active",
        oracle=getattr(label, "oracle", None),
        fail_kind=getattr(label, "fail_kind", None),
        error_class=error_class,
        behavior_shape=behavior_shape(behavior if isinstance(behavior, dict) else {}),
    )
    if isinstance(negatives, str) or not isinstance(negatives, Iterable):
        raise ValueError(f"negatives: expected a sequence of pairs, got {negatives!r}")
    for item in negatives:
        if isinstance(item, str) or not isinstance(item, tuple) or len(item) != 2:
            raise ValueError(f"negatives: expected (phi, record_id) pairs, got {item!r}")
        example, seen = item
        family = apply_negative(family, example, seen, active).hypothesis
    return family


def attribution_request(hypothesis: Hypothesis) -> dict[str, Any]:
    """Mapping the harness tier-2 attribution test accepts for this hypothesis."""
    request: dict[str, Any] = {
        "hypothesis_id": hypothesis.hypothesis_id,
        "engine": hypothesis.engine,
        "interventions": list(hypothesis.interventions),
    }
    if not hypothesis.interventions:
        request["fail_kind"] = hypothesis.fail_kind
        request["error_class"] = hypothesis.error_class
        request["behavior_shape"] = hypothesis.behavior_shape
    return request
