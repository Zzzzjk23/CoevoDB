"""Empty and always-true regexes stay out of the vocabulary registry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from surprise.features.registry import Registry, default_registry
from surprise.features.vocabulary import FeatureDef
from surprise.gates.s10_cases import VOCAB_GOOD, VOCAB_PARENT


def _leaf(feature_id: str, pattern: str, *, parent: str = "ast:expr") -> FeatureDef:
    return FeatureDef(
        feature_id=feature_id,
        kind="leaf",
        parent=parent,
        layer="ast",
        description="registry regex check",
        source="llm:test",
        definition={"kind": "regex", "pattern": pattern},
        accepted=False,
        acceptance=None,
    )


def test_empty_and_always_true_patterns_are_refused() -> None:
    registry = default_registry()
    patterns = ("", "a*", "(?:)", "a?", ".*", "(?:a)?", "(?i)a*")
    for index, pattern in enumerate(patterns):
        with pytest.raises(ValueError, match="empty"):
            registry.register(_leaf(f"ast:expr:empty_{index}", pattern))
    assert registry.ids() == default_registry().ids()


def test_patterns_that_need_a_character_still_register(tmp_path: Path) -> None:
    registry = default_registry()
    patterns = ("x", "marker", r"\bgate_marker\b", "a+", VOCAB_GOOD["pattern"])
    ids = []
    for index, pattern in enumerate(patterns):
        parent = "ast:expr" if index < 4 else VOCAB_PARENT
        feature_id = f"{parent}:kept_{index}"
        registry.register(_leaf(feature_id, pattern, parent=parent))
        ids.append(feature_id)
        stored = registry.get(feature_id)
        assert stored.accepted is False
        assert stored.definition == {"kind": "regex", "pattern": pattern}
    path = tmp_path / "vocabulary.json"
    registry.save(path)
    loaded = Registry.load(path)
    for feature_id, pattern in zip(ids, patterns):
        assert loaded.get(feature_id).definition["pattern"] == pattern
    text = path.read_text(encoding="utf-8").replace('"pattern": "x"', '"pattern": ""', 1)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        Registry.load(path)
    tautology = json.loads(text)
    tautology["invented"][0]["definition"]["pattern"] = "a*"
    path.write_text(json.dumps(tautology), encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        Registry.load(path)
