"""The phi container: engine, leaves, layer status, and vocabulary digest."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .registry import Registry, default_registry
from .vocabulary import LAYERS, layer_of

_AST_STATUS = frozenset({"ok", "fallback"})
_PLAN_DATA_STATUS = frozenset({"ok", "unavailable", "skipped"})


@dataclass(frozen=True)
class Phi:
    """A shared description of a statement, its plan, and the data it runs on."""

    engine: str
    features: tuple[str, ...]
    layers: Mapping[str, str]
    vocab: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "features", tuple(self.features))
        object.__setattr__(self, "layers", MappingProxyType(dict(self.layers)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": 1,
            "engine": self.engine,
            "features": list(self.features),
            "layers": dict(self.layers),
            "vocab": self.vocab,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Phi:
        if not isinstance(data, Mapping) or set(data) != {"schema", "engine", "features", "layers", "vocab"}:
            raise ValueError("phi keys must be exactly schema, engine, features, layers, vocab")
        if data["schema"] != 1:
            raise ValueError("phi schema must be 1")
        engine = data["engine"]
        vocab = data["vocab"]
        if not isinstance(engine, str) or not engine:
            raise ValueError("engine must be a non-empty string")
        if not isinstance(vocab, str) or not vocab:
            raise ValueError("vocab must be a non-empty string")
        features = data["features"]
        if not isinstance(features, list) or any(not isinstance(item, str) for item in features):
            raise ValueError("features must be a list of strings")
        if any(features[index] >= features[index + 1] for index in range(len(features) - 1)):
            raise ValueError("features must be strictly sorted")
        return cls(
            engine=engine,
            features=tuple(features),
            layers=_require_layers(data["layers"]),
            vocab=vocab,
        )


def make_phi(
    engine: str,
    features: Iterable[str],
    layers: Mapping[str, str],
    registry: Registry | None = None,
) -> Phi:
    """Validate and build a phi. ``vocab`` is the digest of ``registry``."""
    if not isinstance(engine, str) or not engine:
        raise ValueError("engine must be a non-empty string")
    if isinstance(features, str) or not isinstance(features, Iterable):
        raise ValueError("features must be a sequence of ids")
    leaves = tuple(sorted(set(features)))
    status = _require_layers(layers)
    active = default_registry() if registry is None else registry
    for feature_id in leaves:
        if not active.known(feature_id):
            raise ValueError(f"unknown feature: {feature_id}")
        definition = active.get(feature_id)
        if definition.kind != "leaf":
            raise ValueError(f"phi may only contain leaves: {feature_id}")
        if not definition.accepted:
            raise ValueError(f"unaccepted feature: {feature_id}")
        layer = layer_of(feature_id)
        if not _layer_available(layer, status[layer]):
            raise ValueError(f"feature {feature_id} belongs to a layer that was not computed")
    return Phi(engine=engine, features=leaves, layers=status, vocab=active.digest())


def _require_layers(layers: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(layers, Mapping) or set(layers) != set(LAYERS):
        raise ValueError("layers keys must be exactly ast, plan, data")
    ast_status = layers["ast"]
    if ast_status not in _AST_STATUS:
        raise ValueError(f"ast layer status must be ok or fallback, got {ast_status!r}")
    out = {"ast": ast_status}
    for name in ("plan", "data"):
        value = layers[name]
        if value not in _PLAN_DATA_STATUS:
            raise ValueError(f"{name} layer status must be ok, unavailable or skipped, got {value!r}")
        out[name] = value
    return out


def _layer_available(layer: str, status: str) -> bool:
    if layer == "ast":
        return status in _AST_STATUS
    return status == "ok"
