"""Upstream regression replay: select, label, and compare two engine versions."""

from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path

import pytest

from surprise.harness.contracts import ORACLE_IDS, SqlCase
from surprise.harness.cve.certify import certify
from surprise.metrics.coverage import compare, main, replay, select

_PREFIX = "duckdb:test/issues/"


def test_select_keeps_file_order_and_limit() -> None:
    corpus = json.loads((Path(__file__).resolve().parents[1] / "seeds" / "corpus.json").read_text(encoding="utf-8"))
    want = [item for item in corpus if item["source"].startswith(_PREFIX)]
    assert want
    assert select(_PREFIX) == want
    assert select(_PREFIX, 3) == want[:3]
    assert select(_PREFIX, 0) == []
    assert select("no-such-prefix/") == []
    head = select(limit=4)
    assert len(head) == 4
    assert all(item["source"].startswith("duckdb:test/") for item in head)
    with pytest.raises(ValueError):
        select(_PREFIX, -1)


def test_replay_is_repeatable_and_matches_certify() -> None:
    seeds = select(_PREFIX, 3)
    first = replay(seeds, ["plan_variant"], prefix=_PREFIX, limit=3)
    second = replay(seeds, ["plan_variant"], prefix=_PREFIX, limit=3)
    assert first == second
    assert first["engine"] == "duckdb"
    assert first["version"] == importlib.metadata.version("duckdb")
    assert first["prefix"] == _PREFIX
    assert first["limit"] == 3
    assert first["oracles"] == ["plan_variant"]
    assert [item["index"] for item in first["items"]] == [0, 1, 2]
    assert {item["source"] for item in first["items"]} == {seed["source"] for seed in seeds}
    for item in first["items"]:
        assert set(item) == {"index", "source", "oracle", "y", "fail_kind", "invalid_reason"}
        assert item["oracle"] == "plan_variant"
        assert item["y"] in ("pass", "fail", "invalid")
        seed = seeds[item["index"]]
        case = SqlCase(engine="duckdb", setup=tuple(seed["setup_sqls"]), query=seed["query"], predicate=None)
        label = certify(case, "plan_variant")
        assert item["y"] == label.y
        assert item["fail_kind"] == label.fail_kind
        assert item["invalid_reason"] == label.invalid_reason
        assert item["source"] == seed["source"]


def test_compare_classifies_the_three_lists() -> None:
    seeds = select(_PREFIX, 2)
    new = replay(seeds, ["tlp"], prefix=_PREFIX, limit=2)
    old = json.loads(json.dumps(new))
    old["version"] = "1.1.3"
    same = compare(old, new)
    assert same["old_version"] == "1.1.3"
    assert same["new_version"] == new["version"]
    entry = same["oracles"]["tlp"]
    assert entry["fail_old_pass_new"] == []
    assert entry["fail_new_only"] == []
    assert entry["fail_both"] == [item["index"] for item in new["items"] if item["y"] == "fail"]
    assert entry["old"] == entry["new"]

    old["items"][0]["y"] = "fail"
    old["items"][0]["fail_kind"] = "wrong_result"
    old["items"][0]["invalid_reason"] = None
    new["items"][0]["y"] = "pass"
    new["items"][0]["fail_kind"] = None
    new["items"][0]["invalid_reason"] = None
    if len(new["items"]) > 1:
        old["items"][1]["y"] = "pass"
        old["items"][1]["fail_kind"] = None
        new["items"][1]["y"] = "fail"
        new["items"][1]["fail_kind"] = "wrong_result"
        new["items"][1]["invalid_reason"] = None
    flipped = compare(old, new)
    lists = flipped["oracles"]["tlp"]
    assert lists["fail_old_pass_new"] == [0]
    assert lists["fail_both"] == []
    assert lists["fail_new_only"] == ([1] if len(new["items"]) > 1 else [])
    assert lists["old"]["fail"] == 1
    assert lists["new"]["pass"] == 1
    if len(new["items"]) > 1:
        assert lists["new"]["fail"] == 1
        assert lists["old"]["pass"] == 1

    old["prefix"] = "other/"
    with pytest.raises(ValueError):
        compare(old, new)


def test_cli_run_and_compare(tmp_path: Path) -> None:
    new_path = tmp_path / "new.json"
    assert main(["run", "--out", str(new_path), "--prefix", _PREFIX, "--limit", "2", "--oracle", "plan_variant"]) == 0
    new = json.loads(new_path.read_text(encoding="utf-8"))
    assert new["version"] == importlib.metadata.version("duckdb")
    assert len(new["items"]) == 2
    assert new["oracles"] == ["plan_variant"]
    direct = replay(select(_PREFIX, 2), ["plan_variant"], prefix=_PREFIX, limit=2)
    assert [(item["index"], item["oracle"], item["y"]) for item in new["items"]] == [
        (item["index"], item["oracle"], item["y"]) for item in direct["items"]
    ]
    old_path = tmp_path / "old.json"
    old = json.loads(json.dumps(new))
    old["version"] = "1.1.3"
    old_path.write_text(json.dumps(old), encoding="utf-8")
    out = tmp_path / "compare.json"
    assert main(["compare", str(old_path), str(new_path), "--out", str(out)]) == 0
    merged = json.loads(out.read_text(encoding="utf-8"))
    assert merged == compare(old, new)
    assert main(["run", "--out", str(tmp_path / "all.json"), "--prefix", _PREFIX, "--limit", "0"]) == 0
    every = json.loads((tmp_path / "all.json").read_text(encoding="utf-8"))
    assert every["oracles"] == list(ORACLE_IDS)
    assert every["items"] == []
    assert every["limit"] == 0
