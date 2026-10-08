"""Base vocabulary, registry, invented features, and the phi container."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from surprise.features import FeatureDef, Phi, Registry, default_registry, make_phi
from surprise.features.vocabulary import BASE_FEATURES
from surprise.gates.s05_cases import ANCESTORS, CORE_VOCAB, SIBLINGS


def _invented(**overrides) -> FeatureDef:
    fields = dict(
        feature_id="ast:expr:gate_marker",
        kind="leaf",
        parent="ast:expr",
        layer="ast",
        description="mentions gate_marker",
        source="llm:vocabulary_inventor:gate",
        definition={"kind": "regex", "pattern": r"\bgate_marker\b"},
        accepted=False,
        acceptance=None,
    )
    fields.update(overrides)
    return FeatureDef(**fields)


def test_feature_package_does_not_import_gates() -> None:
    root = Path(__file__).resolve().parents[1] / "surprise" / "features"
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "surprise.gates" not in text, path


def test_core_vocab_kind_parent_and_base_fields() -> None:
    registry = default_registry()
    assert len(CORE_VOCAB) == 166
    assert {item.feature_id for item in BASE_FEATURES} >= set(CORE_VOCAB)
    for feature_id, (kind, parent, _meaning) in CORE_VOCAB.items():
        assert registry.known(feature_id)
        definition = registry.get(feature_id)
        assert (definition.kind, definition.parent) == (kind, parent)
        assert definition.layer == feature_id.split(":", 1)[0] == registry.layer(feature_id)
        assert definition.source == "base"
        assert definition.accepted is True
        assert definition.definition is None
        assert definition.acceptance is None
        assert isinstance(definition.description, str) and definition.description
        assert FeatureDef.from_dict(definition.to_dict()) == definition
    for feature_id in registry.ids():
        parent = registry.get(feature_id).parent
        if parent is not None:
            assert registry.get(parent).kind in ("class", "family")


def test_open_families_one_extra_segment_only() -> None:
    registry = default_registry()
    for member, family in (("plan:HASH_JOIN", "plan"), ("plan:HashJoinExec", "plan"), ("ast:fn:upper", "ast:fn")):
        assert registry.known(member)
        definition = registry.get(member)
        assert (definition.kind, definition.parent, definition.layer) == (
            "leaf",
            family,
            member.split(":", 1)[0],
        )
        assert definition.source == "base"
        assert definition.accepted is True
        assert registry.siblings(member) == ()
    assert not registry.known("plan:a:b")
    assert registry.get("ast:fn").kind == "family"
    assert registry.get("plan").kind == "family"
    for stranger in ("ast:no_such_feature", "nope:x", "data:setop:middle_has_dups", "ast:fn:"):
        assert not registry.known(stranger)
        with pytest.raises((KeyError, ValueError)):
            registry.get(stranger)


def test_ancestors_siblings_children_closure() -> None:
    registry = default_registry()
    for feature_id, expected in ANCESTORS.items():
        assert registry.ancestors(feature_id) == expected
    for feature_id, expected in SIBLINGS.items():
        siblings = registry.siblings(feature_id)
        assert set(expected) <= set(siblings)
        assert feature_id not in siblings
        assert list(siblings) == sorted(siblings)
        assert all(registry.get(item).kind == "leaf" for item in siblings)
    children = registry.children("ast:set_op:all")
    assert set(children) >= {"ast:set_op:union_all", "ast:set_op:except_all", "ast:set_op:intersect_all"}
    assert list(children) == sorted(children)
    closure = registry.closure(["ast:set_op:except_all", "plan:HASH_JOIN", "data:setop:left_has_dups"])
    assert closure == frozenset(
        {
            "ast:set_op:except_all",
            "ast:set_op:all",
            "ast:set_op",
            "ast",
            "plan:HASH_JOIN",
            "plan",
            "data:setop:left_has_dups",
            "data:setop",
            "data",
        }
    )


def test_default_registry_is_isolated() -> None:
    left = default_registry()
    right = default_registry()
    left.register(_invented())
    assert left.known("ast:expr:gate_marker")
    assert not right.known("ast:expr:gate_marker")
    assert "ast:expr:gate_marker" not in default_registry().ids()


def test_register_rejects_each_reason() -> None:
    registry = default_registry()
    registry.register(_invented())
    cases = [
        _invented(),
        _invented(feature_id="not-an-id", parent="ast:expr"),
        _invented(feature_id="plan:HASH_JOIN", parent="plan", layer="plan"),
        _invented(feature_id="ast:expr:other_marker", kind="class"),
        _invented(feature_id="ast:expr:other_marker", source="base"),
        _invented(feature_id="ast:expr:other_marker", source=""),
        _invented(feature_id="plan:expr:x", parent="ast:expr", layer="ast"),
        _invented(feature_id="data:table:gate_empty", parent="data:table", layer="data"),
        _invented(feature_id="ast:nowhere:x", parent="ast:nowhere"),
        _invented(feature_id="ast:expr:cross", parent="data:table"),
        _invented(feature_id="ast:expr:case:deep", parent="ast:expr:case"),
        _invented(feature_id="ast:fn:gate_fn", parent="ast:fn"),
        _invented(feature_id="ast:expr:vague", definition=None),
        _invented(feature_id="ast:expr:wrong_kind", definition={"kind": "ast", "pattern": "x"}),
        _invented(feature_id="ast:expr:broken", definition={"kind": "regex", "pattern": "("}),
        _invented(feature_id="ast:expr:already", accepted=True),
        _invented(feature_id="ast:expr:already", acceptance={"x": 1}),
    ]
    for definition in cases:
        with pytest.raises(ValueError):
            registry.register(definition)
    assert registry.get("ast:expr:gate_marker").accepted is False
    assert "ast:expr:gate_marker" in registry.siblings("ast:expr:case")
    assert "ast:expr:gate_marker" in registry.children("ast:expr")


def test_accept_save_load_and_digest(tmp_path: Path) -> None:
    base = default_registry()
    digest = base.digest()
    assert len(digest) == 64 and digest == default_registry().digest()
    again = hashlib.sha256(
        json.dumps(
            [base.get(fid).to_dict() for fid in base.ids()],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    assert digest == again

    mine = default_registry()
    mine.register(_invented())
    after_register = mine.digest()
    assert after_register != digest
    acceptance = {"holdout": {"surprise_delta": -0.4, "records": 12}, "decided_by": "gate"}
    mine.accept("ast:expr:gate_marker", acceptance)
    accepted = mine.get("ast:expr:gate_marker")
    assert accepted.accepted is True
    assert accepted.acceptance == acceptance
    assert accepted.source.startswith("llm:")
    assert mine.digest() != after_register
    with pytest.raises((KeyError, ValueError)):
        mine.accept("ast:expr:case", acceptance)
    with pytest.raises((KeyError, ValueError)):
        mine.accept("ast:no_such_feature", acceptance)

    path = tmp_path / "invented.json"
    mine.save(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["invented"]
    loaded = Registry.load(path)
    assert loaded.digest() == mine.digest()
    assert loaded.get("ast:expr:gate_marker") == accepted
    assert set(CORE_VOCAB) <= set(loaded.ids())


def test_make_phi_sorts_validates_and_round_trips() -> None:
    digest = default_registry().digest()
    phi = make_phi(
        "duckdb",
        ("plan:HASH_JOIN", "ast:set_op:except_all", "ast:stmt:select", "ast:set_op:except_all"),
        {"ast": "ok", "plan": "ok", "data": "unavailable"},
    )
    assert phi.features == ("ast:set_op:except_all", "ast:stmt:select", "plan:HASH_JOIN")
    assert phi.engine == "duckdb"
    assert phi.vocab == digest
    assert dict(phi.layers) == {"ast": "ok", "plan": "ok", "data": "unavailable"}
    as_dict = phi.to_dict()
    assert set(as_dict) == {"schema", "engine", "features", "layers", "vocab"}
    assert as_dict["schema"] == 1
    assert json.loads(json.dumps(as_dict, sort_keys=True)) == as_dict
    assert Phi.from_dict(as_dict) == phi
    fallback = make_phi(
        "duckdb",
        ("ast:parse:fallback", "ast:clause:where"),
        {"ast": "fallback", "plan": "unavailable", "data": "unavailable"},
    )
    assert fallback.layers["ast"] == "fallback"


def test_make_phi_rejects_invalid_payloads() -> None:
    all_ok = {"ast": "ok", "plan": "ok", "data": "ok"}
    cases = [
        (("ast:no_such_feature",), all_ok),
        (("ast:set_op:all",), all_ok),
        (("plan",), all_ok),
        (("ast:stmt:select",), {"ast": "ok", "plan": "ok"}),
        (("ast:stmt:select",), {"ast": "ok", "plan": "maybe", "data": "ok"}),
        (("ast:stmt:select",), {"ast": "ok", "plan": "fallback", "data": "ok"}),
        (("ast:stmt:select", "plan:HASH_JOIN"), {"ast": "ok", "plan": "skipped", "data": "ok"}),
        (("ast:stmt:select",), {"ast": "skipped", "plan": "ok", "data": "ok"}),
    ]
    for features, layers in cases:
        with pytest.raises(ValueError):
            make_phi("duckdb", features, dict(layers))
    mine = default_registry()
    mine.register(_invented())
    with pytest.raises(ValueError):
        make_phi("duckdb", ("ast:expr:gate_marker",), all_ok, registry=mine)
    mine.accept("ast:expr:gate_marker", {"decided_by": "test"})
    accepted = make_phi("duckdb", ("ast:expr:gate_marker",), all_ok, registry=mine)
    assert "ast:expr:gate_marker" in accepted.features
    assert accepted.vocab == mine.digest()
