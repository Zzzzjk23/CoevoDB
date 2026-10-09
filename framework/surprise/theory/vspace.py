"""Conjunctions of phi literals: reduction, coverage, generalisation, specialisation.

A conjunction holds of a phi exactly when every id is in the closure of that
phi. There is no negation. Layer roots carry no condition and never appear in
a reduced conjunction.
"""

from __future__ import annotations

from collections.abc import Iterable

from surprise.features.phi import Phi
from surprise.features.registry import Registry, default_registry


def _registry(registry: Registry | None) -> Registry:
    return default_registry() if registry is None else registry


def _ids(value: object, registry: Registry, what: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Iterable):
        raise ValueError(f"{what}: expected a sequence of feature ids, got {value!r}")
    found: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{what}: expected strings, got {item!r}")
        if not registry.known(item):
            raise ValueError(f"{what}: unknown feature {item!r}")
        found.append(item)
    return tuple(found)


def _phi_features(phi: Phi, registry: Registry) -> tuple[str, ...]:
    features = getattr(phi, "features", None)
    return _ids(features, registry, "phi.features")


def _phi_closure(phi: Phi, registry: Registry) -> frozenset[str]:
    return registry.closure(_phi_features(phi, registry))


def _is_layer_root(registry: Registry, feature_id: str) -> bool:
    return registry.parent(feature_id) is None


def reduce_conjunction(ids: object, registry: Registry | None = None) -> tuple[str, ...]:
    """Sorted ids with layer roots and ancestors of a sibling id removed.

    The result is idempotent and does not depend on the input order.
    """
    active = _registry(registry)
    raw = _ids(ids, active, "ids")
    present = [feature_id for feature_id in raw if not _is_layer_root(active, feature_id)]
    implied: set[str] = set()
    for feature_id in present:
        implied.update(active.ancestors(feature_id))
    kept = {feature_id for feature_id in present if feature_id not in implied}
    return tuple(sorted(kept))


def covers(conjunction: object, phi: Phi, registry: Registry | None = None) -> bool:
    """True when every id of ``conjunction`` is in the closure of ``phi``."""
    active = _registry(registry)
    literals = _ids(conjunction, active, "conjunction")
    closed = _phi_closure(phi, active)
    return all(literal in closed for literal in literals)


def generalize(specific: object, phi: Phi, registry: Registry | None = None) -> tuple[str, ...]:
    """Least conjunction that still covers ``phi`` and is implied by ``specific``."""
    active = _registry(registry)
    shared = active.closure(_ids(specific, active, "specific")) & _phi_closure(phi, active)
    return reduce_conjunction(shared, active)


def _excluding_literal(feature_id: str, closed: frozenset[str], registry: Registry) -> str | None:
    """Most general literal on the chain from ``feature_id`` that ``closed`` lacks.

    The chain runs from the literal up to, but not including, the layer root.
    A closure is ancestor-closed, so the ids it misses are a prefix of that
    chain; the far end of the prefix is the one to add.
    """
    chain = [feature_id]
    for ancestor in registry.ancestors(feature_id):
        if _is_layer_root(registry, ancestor):
            continue
        chain.append(ancestor)
    chosen: str | None = None
    for node in chain:
        if node in closed:
            break
        chosen = node
    return chosen


def _drop_redundant(
    members: Iterable[tuple[str, ...]], registry: Registry
) -> list[tuple[str, ...]]:
    unique: list[tuple[str, ...]] = []
    for member in members:
        if member not in unique:
            unique.append(member)
    closures = [registry.closure(member) for member in unique]
    kept: list[tuple[str, ...]] = []
    for index, member in enumerate(unique):
        closed = closures[index]
        if any(
            other != member and all(literal in closed for literal in other) for other in unique
        ):
            continue
        kept.append(member)
    return kept


def _canonical(members: Iterable[tuple[str, ...]]) -> tuple[tuple[str, ...], ...]:
    return tuple(sorted(members, key=lambda member: (len(member), member)))


def specialize(
    general: object,
    specific: object,
    phi: Phi,
    registry: Registry | None = None,
) -> tuple[tuple[str, ...], ...]:
    """Every minimal way to make ``general`` exclude the negative example ``phi``.

    Raises ``ValueError`` when ``phi`` lies inside ``specific``: nothing more
    general than S can exclude it. This function does not apply the cap on G.
    """
    active = _registry(registry)
    boundary = reduce_conjunction(specific, active)
    if covers(boundary, phi, active):
        raise ValueError("negative example lies inside the specific boundary")
    closed = _phi_closure(phi, active)
    candidates: list[str] = []
    for feature_id in boundary:
        chosen = _excluding_literal(feature_id, closed, active)
        if chosen is not None and chosen not in candidates:
            candidates.append(chosen)
    if isinstance(general, str) or not isinstance(general, Iterable):
        raise ValueError(f"general: expected a sequence of conjunctions, got {general!r}")
    produced: list[tuple[str, ...]] = []
    for member in general:
        reduced = reduce_conjunction(member, active)
        if covers(reduced, phi, active):
            for candidate in candidates:
                produced.append(reduce_conjunction((*reduced, candidate), active))
        else:
            produced.append(reduced)
    return _canonical(_drop_redundant(produced, active))
