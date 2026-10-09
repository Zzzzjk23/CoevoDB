"""Check whether a phi satisfies a spec."""
from __future__ import annotations

from dataclasses import dataclass

from surprise.theory.contracts import Spec

from .phi import Phi
from .registry import Registry, default_registry
from .vocabulary import layer_of


@dataclass(frozen=True)
class SpecCheck:
    """Result of ``check_spec``: missing, forbidden, and undetermined ids are sorted."""

    ok: bool
    engine_ok: bool
    missing: tuple[str, ...]
    forbidden: tuple[str, ...]
    undetermined: tuple[str, ...]


def check_spec(phi: Phi, spec: Spec, registry: Registry | None = None) -> SpecCheck:
    """``phi |= spec``. Unknown ids, or non-data ``data_properties``, raise ``ValueError``."""
    active = default_registry() if registry is None else registry
    for group_name in ("required", "forbidden", "data_properties"):
        for feature_id in getattr(spec, group_name):
            if not active.known(feature_id):
                raise ValueError(f"unknown feature in {group_name}: {feature_id}")
    for feature_id in spec.data_properties:
        if layer_of(feature_id) != "data":
            raise ValueError(f"data_properties must be data-layer ids: {feature_id}")

    closed = active.closure(phi.features)
    missing: set[str] = set()
    forbidden: set[str] = set()
    undetermined: set[str] = set()

    for feature_id in (*spec.required, *spec.data_properties):
        if feature_id in closed:
            continue
        if _computed(phi, feature_id):
            missing.add(feature_id)
        else:
            undetermined.add(feature_id)

    for feature_id in spec.forbidden:
        if feature_id in closed:
            forbidden.add(feature_id)
        elif not _computed(phi, feature_id):
            undetermined.add(feature_id)

    engine_ok = spec.engine == phi.engine
    missing_t = tuple(sorted(missing))
    forbidden_t = tuple(sorted(forbidden))
    undetermined_t = tuple(sorted(undetermined))
    return SpecCheck(
        ok=engine_ok and not missing_t and not forbidden_t and not undetermined_t,
        engine_ok=engine_ok,
        missing=missing_t,
        forbidden=forbidden_t,
        undetermined=undetermined_t,
    )


def _computed(phi: Phi, feature_id: str) -> bool:
    return phi.layers[layer_of(feature_id)] in ("ok", "fallback")
