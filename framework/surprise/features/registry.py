"""Vocabulary registry: base features, open families, and invented leaves."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

from .vocabulary import BASE_FEATURES, FeatureDef, is_feature_id, layer_of

_CANONICAL_JSON = {"sort_keys": True, "separators": (",", ":"), "ensure_ascii": False}


class Registry:
    """Explicit feature definitions plus on-the-fly members of open families."""

    def __init__(self, definitions: dict[str, FeatureDef] | None = None) -> None:
        self._defs: dict[str, FeatureDef] = dict(definitions or {})

    def known(self, feature_id: str) -> bool:
        return feature_id in self._defs or self._family_of(feature_id) is not None

    def get(self, feature_id: str) -> FeatureDef:
        if feature_id in self._defs:
            return self._defs[feature_id]
        family_id = self._family_of(feature_id)
        if family_id is not None:
            return self._synthetic(feature_id, family_id)
        raise KeyError(feature_id)

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._defs))

    def layer(self, feature_id: str) -> str:
        return self.get(feature_id).layer

    def parent(self, feature_id: str) -> str | None:
        return self.get(feature_id).parent

    def ancestors(self, feature_id: str) -> tuple[str, ...]:
        out: list[str] = []
        current = self.parent(feature_id)
        seen: set[str] = set()
        while current is not None and current not in seen:
            seen.add(current)
            out.append(current)
            current = self.parent(current)
        return tuple(out)

    def children(self, class_id: str) -> tuple[str, ...]:
        return tuple(sorted(fid for fid, definition in self._defs.items() if definition.parent == class_id))

    def siblings(self, feature_id: str) -> tuple[str, ...]:
        if self._family_of(feature_id) is not None:
            return ()
        parent = self.get(feature_id).parent
        return tuple(
            sorted(
                fid
                for fid, definition in self._defs.items()
                if definition.parent == parent and definition.kind == "leaf" and fid != feature_id
            )
        )

    def closure(self, features: Iterable[str]) -> frozenset[str]:
        out: set[str] = set()
        for feature_id in features:
            out.add(feature_id)
            out.update(self.ancestors(feature_id))
        return frozenset(out)

    def register(self, definition: FeatureDef) -> None:
        checked = self._checked_invented(definition, allow_accepted=False)
        self._defs[checked.feature_id] = checked

    def accept(self, feature_id: str, acceptance: dict[str, Any]) -> None:
        if feature_id not in self._defs:
            raise KeyError(feature_id)
        current = self._defs[feature_id]
        if current.source == "base":
            raise ValueError("cannot accept a base feature")
        stored = _json_object(acceptance, "acceptance")
        self._defs[feature_id] = replace(current, accepted=True, acceptance=stored)

    def digest(self) -> str:
        blob = json.dumps([self._defs[fid].to_dict() for fid in sorted(self._defs)], **_CANONICAL_JSON)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def save(self, path: str | Path) -> None:
        invented = [
            self._defs[fid].to_dict()
            for fid in sorted(self._defs)
            if self._defs[fid].source != "base"
        ]
        Path(path).write_text(
            json.dumps({"invented": invented}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> Registry:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "invented" in payload:
            items = payload["invented"]
        elif isinstance(payload, list):
            items = payload
        else:
            raise ValueError("unrecognised registry file")
        registry = default_registry()
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("invented features must be objects")
            try:
                definition = FeatureDef.from_dict(item)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid invented feature: {exc}") from exc
            checked = registry._checked_invented(definition, allow_accepted=True)
            registry._defs[checked.feature_id] = checked
        return registry

    def _checked_invented(self, definition: FeatureDef, *, allow_accepted: bool) -> FeatureDef:
        feature_id = definition.feature_id
        if not is_feature_id(feature_id):
            raise ValueError(f"invalid feature id: {feature_id!r}")
        if self.known(feature_id):
            raise ValueError(f"already known: {feature_id}")
        if definition.kind != "leaf":
            raise ValueError("invented features must be leaves")
        if not isinstance(definition.source, str) or not definition.source or definition.source == "base":
            raise ValueError("invented features need a non-base source")
        if definition.layer != layer_of(feature_id):
            raise ValueError("layer must match the first segment of the id")
        if definition.layer != "ast":
            raise ValueError("this session only supports invented ast features")
        parent = self._defs.get(definition.parent) if definition.parent else None
        if parent is None or parent.kind != "class":
            raise ValueError("parent must be a registered class")
        if parent.layer != definition.layer:
            raise ValueError("parent must be in the same layer")
        regex = _require_regex_definition(definition.definition)
        if allow_accepted:
            if definition.accepted is True:
                stored = _json_object(definition.acceptance, "acceptance")
                return replace(definition, definition=regex, acceptance=stored)
            if definition.accepted is False:
                if definition.acceptance is not None:
                    raise ValueError("unaccepted features cannot have acceptance")
                return replace(definition, definition=regex)
            raise ValueError("accepted must be true or false")
        if definition.accepted is not False or definition.acceptance is not None:
            raise ValueError("invented features start unaccepted")
        return replace(definition, definition=regex)

    def _family_of(self, feature_id: str) -> str | None:
        if feature_id in self._defs or not is_feature_id(feature_id):
            return None
        parent_id, sep, token = feature_id.rpartition(":")
        if not sep or not token:
            return None
        parent = self._defs.get(parent_id)
        if parent is not None and parent.kind == "family":
            return parent_id
        return None

    def _synthetic(self, feature_id: str, family_id: str) -> FeatureDef:
        token = feature_id.rsplit(":", 1)[1]
        return FeatureDef(
            feature_id=feature_id,
            kind="leaf",
            parent=family_id,
            layer=layer_of(feature_id),
            description=f"Member {token} of open family {family_id}.",
            source="base",
            definition=None,
            accepted=True,
            acceptance=None,
        )


def default_registry() -> Registry:
    """A new registry that holds only the base vocabulary."""
    return Registry({definition.feature_id: definition for definition in BASE_FEATURES})


def _require_regex_definition(definition: Any) -> dict[str, str]:
    if not isinstance(definition, dict):
        raise ValueError("definition must be a regex dict")
    if definition.get("kind") != "regex":
        raise ValueError("only regex definitions are supported")
    pattern = definition.get("pattern")
    if not isinstance(pattern, str):
        raise ValueError("pattern must be a string")
    extra = set(definition) - {"kind", "pattern"}
    if extra:
        raise ValueError(f"unexpected definition keys: {sorted(extra)}")
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"pattern does not compile: {exc}") from exc
    return {"kind": "regex", "pattern": pattern}


def _json_object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not value:
        raise ValueError(f"{name} must be a non-empty JSON object")
    try:
        blob = json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} is not JSON-safe") from exc
    loaded = json.loads(blob)
    if not isinstance(loaded, dict):
        raise ValueError(f"{name} must be a JSON object")
    return loaded
