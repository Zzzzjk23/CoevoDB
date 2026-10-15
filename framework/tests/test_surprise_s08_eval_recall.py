"""Known-bug certification and recall against a hand-fed theory."""

from __future__ import annotations

import importlib.metadata as importlib_metadata
import json

import pytest

from surprise.gates.s04 import load
from surprise.metrics.recall import known_bugs, main, score
from test_surprise_s08_eval_dups import EXTRA, FIX, MISSING, ORPHAN, feed_store

FIX_NAMES = ["deliminator", "filter_pushdown"]


def test_known_bugs_profiles_f1_on_this_duckdb() -> None:
    case = load("F1")
    found = known_bugs([{"name": "F1", "case": case.to_dict(), "oracle": "plan_variant", "rule": None}])
    assert found["engines"] == {
        "duckdb": importlib_metadata.version("duckdb"),
        "datafusion": importlib_metadata.version("datafusion"),
    }
    (item,) = found["items"]
    assert item["name"] == "F1"
    assert item["oracle"] == "plan_variant"
    assert item["y"] == "fail"
    assert item["fail_kind"] == "wrong_result"
    assert item["invalid_reason"] is None
    assert item["fix_set"] is not None and sorted(item["fix_set"]) == FIX_NAMES
    assert item["key"] == "fix|duckdb|deliminator,filter_pushdown"
    again = json.loads(json.dumps(found))
    assert again["items"][0]["key"] == item["key"]


def test_score_matches_family_keys_in_order(tmp_path) -> None:
    root = tmp_path / "theory"
    feed_store(root)
    known = {
        "engines": {"duckdb": "1.5.5", "datafusion": "54.0.0"},
        "items": [
            {"name": "F1", "y": "fail", "key": FIX},
            {"name": "skip", "y": "fail", "key": None},
            {"name": "plain", "y": "pass", "key": None},
            {"name": "F9", "y": "fail", "key": "shape|duckdb|wrong_result|-|both"},
            {"name": "orphan", "y": "fail", "key": ORPHAN},
            {"name": "dup", "y": "fail", "key": MISSING},
        ],
    }
    found = score(known, root)
    assert found == {
        "known": ["F1", "F9", "orphan", "dup"],
        "recalled": ["F1", "orphan", "dup"],
        "missed": ["F9"],
        "recall": 0.75,
        "families": 5,
        "first": {"F1": "d1", "orphan": None, "dup": "r1"},
    }
    assert EXTRA not in found["recalled"]
    assert score(known, root) == found
    assert json.dumps(found, ensure_ascii=True) == json.dumps(score(known, root), ensure_ascii=True)

    empty = score({"items": [{"name": "plain", "y": "pass", "key": None}]}, root)
    assert empty["known"] == [] and empty["recalled"] == [] and empty["missed"] == []
    assert empty["recall"] is None and empty["first"] == {} and empty["families"] == 5


def test_recall_cli_writes_score_and_known(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = tmp_path / "run"
    feed_store(run / "theory")
    known_path = tmp_path / "known.json"
    known_path.write_text(
        json.dumps({"items": [{"name": "F1", "y": "fail", "key": FIX}, {"name": "no", "y": "fail", "key": "shape|x|-|-|-"}]}),
        encoding="utf-8",
    )
    out = tmp_path / "recall.json"
    assert main(["score", "--known", str(known_path), "--run", str(run), "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert text.isascii() and "\n  " in text
    found = json.loads(text)
    assert found["recalled"] == ["F1"] and found["missed"] == ["no"] and found["recall"] == 0.5

    captured: dict = {}

    def fake(items):
        captured["items"] = items
        return {"engines": {"duckdb": "1.5.5", "datafusion": "54.0.0"}, "items": []}

    monkeypatch.setattr("surprise.metrics.recall.known_bugs", fake)
    cases = tmp_path / "cases.json"
    cases.write_text("[]", encoding="utf-8")
    known_out = tmp_path / "out-known.json"
    assert main(["known", "--cases", str(cases), "--out", str(known_out)]) == 0
    assert captured["items"] == []
    assert json.loads(known_out.read_text(encoding="utf-8"))["items"] == []
