"""Pure-LLM baseline: scripted replies, budgets, and a cache replay."""

from __future__ import annotations

import importlib.metadata
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

from surprise.baselines import pure_llm
from surprise.baselines.pure_llm import (
    PURE_LLM_CASES_PER_CALL,
    PURE_LLM_MAX_TOKENS,
    PURE_LLM_TEMPERATURE,
    PURE_LLM_TIER,
    PURE_LLM_TOPICS,
    UsageError,
)
from surprise.harness.ledger import Ledger
from surprise.roles.constants import TIERS
from surprise.roles.gateway import Completion

FRAMEWORK = Path(__file__).resolve().parents[1]
GOOD_SETUP = ["CREATE TABLE t(a INT, b INT)", "INSERT INTO t VALUES (1, 10), (2, 20), (NULL, 30)"]


class Script:
    """Transport stand-in. Records prompts and returns canned replies."""

    def __init__(self, replies: list) -> None:
        self.replies = list(replies)
        self.prompts: list[str] = []
        self.seen: list[tuple] = []

    def complete(self, *, model: str, prompt: str, temperature: float, max_tokens: int, role: str):
        self.prompts.append(prompt)
        self.seen.append((model, temperature, max_tokens, role))
        reply = self.replies.pop(0)
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return Completion(text=text, input_tokens=len(prompt) // 4, output_tokens=len(text) // 4)


def _good(oracle: str, predicate: str = "a > 1", expect: str = "pass") -> dict:
    return {
        "setup": GOOD_SETUP,
        "query": "SELECT a, b FROM t",
        "predicate": predicate,
        "oracle": oracle,
        "expect": expect,
    }


def _lines(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _records(out: Path):
    ledger = Ledger(out / "ledger.sqlite")
    try:
        run_ids = ledger.run_ids()
        assert len(run_ids) == 1
        return run_ids[0], ledger.records(run_id=run_ids[0]), ledger.run_manifest(run_ids[0])
    finally:
        ledger.close()


def test_constants_match_the_planned_values() -> None:
    assert PURE_LLM_TIER == "fast" and type(PURE_LLM_TIER) is str
    assert PURE_LLM_TEMPERATURE == 0.8 and type(PURE_LLM_TEMPERATURE) is float
    assert PURE_LLM_MAX_TOKENS == 16000 and type(PURE_LLM_MAX_TOKENS) is int
    assert PURE_LLM_CASES_PER_CALL == 8 and type(PURE_LLM_CASES_PER_CALL) is int
    assert isinstance(PURE_LLM_TOPICS, tuple)
    assert len(PURE_LLM_TOPICS) >= 8 and len(set(PURE_LLM_TOPICS)) == len(PURE_LLM_TOPICS)
    assert all(isinstance(topic, str) and topic.strip() for topic in PURE_LLM_TOPICS)
    assert TIERS[PURE_LLM_TIER]


def test_scripted_replies_follow_the_gate(tmp_path: Path) -> None:
    first = {
        "prediction": "both pass",
        "cases": [
            _good("tlp"),
            _good("norec"),
            {**_good("tlp"), "oracle": "bogus"},
            {**_good("tlp"), "setup": "not a list"},
        ],
    }
    second = {"cases": [_good("tlp")]}
    third = {"prediction": "pass", "cases": [_good("tlp", "b > 15"), _good("norec", "b > 15")]}
    script = Script([first, second, third])
    out = tmp_path / "run"
    report = pure_llm.run(
        out,
        seed=3,
        engine="duckdb",
        oracles=("tlp", "norec"),
        max_experiments=10,
        max_calls=3,
        cache=tmp_path / "cache",
        transport=script,
    )
    assert len(script.prompts) == 3
    assert script.seen[0] == (TIERS["fast"], 0.8, 16000, "pure_llm")
    assert report["status"] == "llm_exhausted" and report["experiments"] == 4 and report["calls"] == 4
    assert report["run_id"] == "pure-s3" and report["seed"] == 3 and report["engine"] == "duckdb"
    assert report["labels"].get("pass", 0) + report["labels"].get("fail", 0) + report["labels"].get("invalid", 0) == 4
    assert report["llm"]["by_role"]["pure_llm"]["calls"] == 4
    run_id, records, manifest = _records(out)
    assert run_id == "pure-s3"
    assert len(records) == 4
    assert all(record.purpose == "pure_llm" and record.p_t is None and record.theory_version is None for record in records)
    assert [record.label.oracle for record in records] == ["tlp", "norec", "tlp", "norec"]
    assert all(record.phi is not None for record in records)
    assert [record.spec["batch"] for record in records] == [0, 0, 2, 2]
    assert [record.spec["index"] for record in records] == [0, 1, 0, 1]
    assert all(record.spec["expect"] == "pass" and record.spec["topic"] for record in records)
    assert manifest["baseline"] == "pure_llm"
    assert manifest["pure_llm"]["PURE_LLM_TIER"] == "fast"
    book = _lines(out / "llm" / "pure_llm.jsonl")
    assert [row["status"] for row in book] == ["ok", "rejected", "ok"]
    assert book[0]["skipped"] == 2 and book[0]["cases"] == 2
    assert book[0]["reasons"] == {"oracle": 1, "setup": 1}
    assert book[1]["cases"] == 0 and book[1]["skipped"] == 0
    progress = _lines(out / "progress.jsonl")
    assert len(progress) == 4
    assert all(row["expect"] == "pass" and row["y"] in ("pass", "fail", "invalid") for row in progress)
    assert [row["record_id"] for row in progress] == [record.record_id for record in records]
    assert [row["kind"] for row in progress] == [
        None if record.label.y == "pass" else record.label.fail_kind or record.label.invalid_reason
        for record in records
    ]
    calls = _lines(out / "llm" / "calls.jsonl")
    assert [row["status"] for row in calls] == ["ok", "rejected", "ok", "blocked"]
    version = importlib.metadata.version("duckdb")
    drawn = random.Random(3)
    first_topic = drawn.choice(PURE_LLM_TOPICS)
    second_topic = drawn.choice(PURE_LLM_TOPICS)
    assert script.prompts[0] != script.prompts[1]
    assert "duckdb" in script.prompts[0].lower()
    assert version in script.prompts[0]
    assert "tlp" in script.prompts[0] and "norec" in script.prompts[0]
    assert "Batch: 0" in script.prompts[0] and "Batch: 1" in script.prompts[1]
    assert "Seed: 3" in script.prompts[0]
    assert f"Topic for this batch: {first_topic}." in script.prompts[0]
    assert f"Topic for this batch: {second_topic}." in script.prompts[1]
    config = json.loads((out / "config.json").read_text(encoding="utf-8"))
    assert config["seed"] == 3 and config["engine"] == "duckdb"
    assert config["oracles"] == ["tlp", "norec"]
    assert config["max_experiments"] == 10 and config["max_minutes"] is None
    assert config["run_id"] == "pure-s3"
    assert config["llm"]["network"] is True and config["llm"]["max_calls"] == 3
    assert config["llm"]["cache"] == str(tmp_path / "cache")

    script2 = Script([first, second, third])
    pure_llm.run(
        tmp_path / "run2",
        seed=3,
        engine="duckdb",
        oracles=("tlp", "norec"),
        max_experiments=10,
        max_calls=3,
        cache=tmp_path / "cache2",
        transport=script2,
    )
    assert script2.prompts == script.prompts

    script3 = Script([first])
    budget = pure_llm.run(
        tmp_path / "run3",
        seed=3,
        engine="duckdb",
        oracles=("tlp", "norec"),
        max_experiments=1,
        max_calls=3,
        cache=tmp_path / "cache3",
        transport=script3,
    )
    assert budget["status"] == "budget_experiments" and budget["experiments"] == 1
    _, stopped, _ = _records(tmp_path / "run3")
    assert [record.label.oracle for record in stopped] == ["tlp"]


def test_bad_cases_are_counted_and_not_executed(tmp_path: Path) -> None:
    reply = {
        "prediction": "none of these run",
        "cases": [
            {**_good("tlp"), "query": ""},
            {**_good("tlp"), "predicate": 1},
            {**_good("tlp"), "expect": "maybe"},
            "nope",
        ],
    }
    script = Script([reply])
    out = tmp_path / "bad"
    report = pure_llm.run(
        out,
        seed=1,
        engine="duckdb",
        oracles=("tlp",),
        max_experiments=5,
        max_calls=1,
        transport=script,
    )
    assert report["status"] == "llm_exhausted" and report["experiments"] == 0 and report["calls"] == 2
    row = _lines(out / "llm" / "pure_llm.jsonl")
    assert len(row) == 1
    assert row[0]["status"] == "ok" and row[0]["cases"] == 0 and row[0]["skipped"] == 4
    assert row[0]["reasons"] == {"query": 1, "predicate": 1, "expect": 1, "not_object": 1}


def test_error_reply_continues_to_the_next_batch(tmp_path: Path) -> None:
    class Flaky(Script):
        def complete(self, *, model, prompt, temperature, max_tokens, role):
            if not self.prompts:
                self.prompts.append(prompt)
                raise RuntimeError("transport down")
            return super().complete(
                model=model, prompt=prompt, temperature=temperature, max_tokens=max_tokens, role=role
            )

    script = Flaky([_reply_ok([_good("tlp")])])
    out = tmp_path / "flaky"
    report = pure_llm.run(
        out,
        seed=2,
        engine="duckdb",
        oracles=("tlp",),
        max_experiments=5,
        max_calls=2,
        transport=script,
    )
    assert report["status"] == "llm_exhausted" and report["experiments"] == 1
    assert [row["status"] for row in _lines(out / "llm" / "pure_llm.jsonl")] == ["error", "ok"]


def _reply_ok(cases: list) -> dict:
    return {"prediction": "pass", "cases": cases}


def test_expect_does_not_become_the_label(tmp_path: Path) -> None:
    script = Script([_reply_ok([_good("tlp", expect="fail")])])
    out = tmp_path / "expect"
    pure_llm.run(
        out,
        seed=4,
        engine="duckdb",
        oracles=("tlp",),
        max_experiments=1,
        transport=script,
    )
    _, records, _ = _records(out)
    assert len(records) == 1
    assert records[0].label.y == "pass"
    assert records[0].spec["expect"] == "fail"
    assert _lines(out / "progress.jsonl")[0]["expect"] == "fail"
    assert _lines(out / "progress.jsonl")[0]["y"] == "pass"


def test_offline_cache_miss_stops(tmp_path: Path) -> None:
    out = tmp_path / "miss"
    report = pure_llm.run(out, seed=5, engine="duckdb", oracles=("tlp",), max_experiments=3, offline=True)
    assert report["status"] == "llm_exhausted" and report["experiments"] == 0 and report["calls"] == 1
    assert _lines(out / "llm" / "pure_llm.jsonl") == []
    calls = _lines(out / "llm" / "calls.jsonl")
    assert len(calls) == 1 and calls[0]["status"] == "miss"
    config = json.loads((out / "config.json").read_text(encoding="utf-8"))
    assert config["llm"]["network"] is False
    assert config["llm"]["cache"] == str(out / "llm" / "cache")


def test_offline_replay_hits_the_cache(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    script = Script([_reply_ok([_good("tlp")])])
    first = pure_llm.run(
        tmp_path / "first",
        seed=9,
        engine="duckdb",
        oracles=("tlp",),
        max_experiments=1,
        cache=cache,
        transport=script,
    )
    assert first["status"] == "budget_experiments" and first["experiments"] == 1
    assert len(script.prompts) == 1
    second = pure_llm.run(
        tmp_path / "second",
        seed=9,
        engine="duckdb",
        oracles=("tlp",),
        max_experiments=1,
        cache=cache,
        offline=True,
    )
    assert second["status"] == "budget_experiments" and second["experiments"] == 1
    calls = _lines(tmp_path / "second" / "llm" / "calls.jsonl")
    assert calls and all(row["source"] == "cache" and row["status"] != "miss" for row in calls)


def test_minute_budget_stops_the_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    now = {"t": 0.0}
    monkeypatch.setattr(pure_llm, "_monotonic", lambda: now["t"])
    real = pure_llm.evaluate_final

    def wrapped(*args, **kwargs):
        record = real(*args, **kwargs)
        now["t"] = 120.0
        return record

    monkeypatch.setattr(pure_llm, "evaluate_final", wrapped)
    script = Script([_reply_ok([_good("tlp"), _good("norec")])])
    out = tmp_path / "minutes"
    report = pure_llm.run(
        out,
        seed=6,
        engine="duckdb",
        oracles=("tlp", "norec"),
        max_experiments=10,
        max_minutes=1,
        transport=script,
    )
    assert report["status"] == "budget_minutes" and report["experiments"] == 1
    assert [row["oracle"] for row in _lines(out / "progress.jsonl")] == ["tlp"]

    zero = pure_llm.run(
        tmp_path / "zero",
        seed=6,
        engine="duckdb",
        oracles=("tlp",),
        max_minutes=0,
        transport=Script([_reply_ok([_good("tlp")])]),
    )
    assert zero["status"] == "budget_minutes" and zero["experiments"] == 0 and zero["calls"] == 0


def test_zero_experiment_budget_makes_no_call(tmp_path: Path) -> None:
    script = Script([_reply_ok([_good("tlp")])])
    report = pure_llm.run(
        tmp_path / "zero",
        seed=1,
        engine="duckdb",
        oracles=("tlp",),
        max_experiments=0,
        transport=script,
    )
    assert report["status"] == "budget_experiments" and report["experiments"] == 0
    assert script.prompts == []


def test_usage_errors(tmp_path: Path) -> None:
    with pytest.raises(UsageError):
        pure_llm.run(tmp_path / "none", seed=1)
    with pytest.raises(ValueError):
        pure_llm.run(tmp_path / "neg", seed=1, max_experiments=-1, offline=True)
    with pytest.raises(ValueError):
        pure_llm.run(tmp_path / "bool", seed=True, max_experiments=1, offline=True)
    with pytest.raises(ValueError):
        pure_llm.run(tmp_path / "oracle", seed=1, oracles=("nope",), max_experiments=1, offline=True)
    filled = tmp_path / "filled"
    filled.mkdir()
    (filled / "busy").write_text("x", encoding="utf-8")
    script = Script([_reply_ok([_good("tlp")])])
    with pytest.raises(ValueError):
        pure_llm.run(filled, seed=1, max_experiments=1, transport=script)
    assert script.prompts == []
    not_dir = tmp_path / "file"
    not_dir.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        pure_llm.run(not_dir, seed=1, max_experiments=1, offline=True)
    assert not (tmp_path / "none").exists()

    assert pure_llm.main(["--out", str(tmp_path / "cli")]) == 2
    assert pure_llm.main(["--out", str(tmp_path / "cli2"), "--seed", "1"]) == 2
    assert not (tmp_path / "cli2").exists()


def test_cli_offline_miss_exits_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "cli"
    code = pure_llm.main(
        ["--out", str(out), "--seed", "1", "--max-experiments", "2", "--llm-offline", "--oracle", "tlp"]
    )
    assert code == 0
    assert capsys.readouterr().out.strip() == "llm_exhausted 0"
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "llm_exhausted" and report["experiments"] == 0
    assert report["oracles"] == ["tlp"]


def test_module_usage_exits_two() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "surprise.baselines.pure_llm"],
        cwd=FRAMEWORK,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.returncode == 2


def test_run_exception_is_written_and_reraised(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("pure-llm-boom")

    monkeypatch.setattr(pure_llm, "evaluate_final", boom)
    out = tmp_path / "boom"
    with pytest.raises(RuntimeError, match="pure-llm-boom"):
        pure_llm.run(
            out,
            seed=1,
            engine="duckdb",
            oracles=("tlp",),
            max_experiments=2,
            transport=Script([_reply_ok([_good("tlp")])]),
        )
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "error"
    assert report["error"]["type"] == "RuntimeError"
    text = (out / "error.txt").read_text(encoding="utf-8")
    assert "RuntimeError" in text and "pure-llm-boom" in text
    reopened = Ledger(out / "ledger.sqlite")
    reopened.close()


def test_report_failure_keeps_the_original_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args, **kwargs):
        raise ValueError("drive-boom")

    def report_boom(state):
        raise RuntimeError("report-boom")

    monkeypatch.setattr(pure_llm, "evaluate_final", boom)
    monkeypatch.setattr(pure_llm, "_write_report", report_boom)
    out = tmp_path / "both"
    with pytest.raises(ValueError, match="drive-boom"):
        pure_llm.run(
            out,
            seed=1,
            engine="duckdb",
            oracles=("tlp",),
            max_experiments=2,
            transport=Script([_reply_ok([_good("tlp")])]),
        )
    text = (out / "error.txt").read_text(encoding="utf-8")
    assert "ValueError" in text and "drive-boom" in text
    assert "RuntimeError" in text and "report-boom" in text
