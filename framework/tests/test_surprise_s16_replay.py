"""Old-ledger replay: real DuckDB records, streaming sampling and CVE evidence."""

from __future__ import annotations

import copy
import json
import shutil
import sqlite3
import subprocess
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from surprise.experiments.loop import run
from surprise.harness.contracts import IdentityEvidence, Label, SqlCase
from surprise.harness.manifest import file_digest, harness_hash
from surprise.metrics import replay
from surprise.metrics.rundata import RunData

FRAMEWORK = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def duck_run(tmp_path_factory):
    directory = tmp_path_factory.mktemp("replay") / "run"
    case = SqlCase(
        engine="duckdb",
        setup=("CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1), (2), (NULL)"),
        query="SELECT a FROM t",
        predicate="a > 1",
    )
    bootstrap = [
        {"case": case.to_dict(), "oracle": oracle, "rule": None}
        for oracle in ["tlp"] * 4 + ["norec"] * 3
    ]
    bootstrap += [
        {"case": replace(case, predicate=None).to_dict(), "oracle": "tlp", "rule": None}
        for _ in range(2)
    ]
    result = run(
        directory, seed=16, engines=("duckdb",), oracles=("tlp", "norec"),
        max_experiments=0, bootstrap=bootstrap, llm=None,
    )
    assert result["experiments"] == 9
    data = RunData.open(directory)
    assert Counter(f"{r.label.oracle}|{r.label.y}" for r in data.iter_records()) == {
        "tlp|pass": 4, "norec|pass": 3, "tlp|invalid": 2,
    }
    return directory


def _cli(directory, output, *, sample=6, seed=16, workers=1):
    proc = subprocess.run(
        [sys.executable, "-m", "surprise.metrics.replay", str(directory),
         "--sample", str(sample), "--seed", str(seed), "--out", str(output),
         "--workers", str(workers)],
        cwd=FRAMEWORK, capture_output=True, text=True, timeout=120,
    )
    return proc, json.loads(output.read_text(encoding="ascii")) if output.exists() else None


def _change_record(directory, seq, change):
    with sqlite3.connect(directory / "ledger.sqlite") as conn:
        body = json.loads(conn.execute("SELECT record_json FROM records WHERE seq = ?", (seq,)).fetchone()[0])
        change(body)
        conn.execute(
            "UPDATE records SET record_json = ?, y = ? WHERE seq = ?",
            (json.dumps(body), body["label"]["y"], seq),
        )
    return body


def test_allocation_and_seeded_streaming_sample(duck_run):
    data = RunData.open(duck_run)
    selected, strata = replay.sample_records(data, 6, 16)
    repeated, again = replay.sample_records(data, 6, 16)
    assert [r.record_id for r in selected] == [r.record_id for r in repeated]
    assert strata == again == {
        "tlp|pass": {"records": 4, "sampled": 3},
        "norec|pass": {"records": 3, "sampled": 2},
        "tlp|invalid": {"records": 2, "sampled": 1},
    }
    assert [r.seq for r in selected] == sorted(r.seq for r in selected)
    assert all(r.label.detail == {} for r in selected)
    assert len({tuple(r.seq for r in replay.sample_records(data, 6, seed)[0]) for seed in range(8)}) > 1
    all_records, all_strata = replay.sample_records(data, 99, 16)
    assert [r.seq for r in all_records] == list(range(1, 10))
    assert all(row["sampled"] == row["records"] for row in all_strata.values())
    assert data._materialized is None


def test_sampling_uses_two_slim_iterator_passes(duck_run):
    record = next(RunData.open(duck_run).iter_records())

    class Stream:
        def __init__(self):
            self.calls = []

        def iter_records(self, *, keep_detail):
            self.calls.append(keep_detail)
            for seq in range(1, 1001):
                yield replace(record, seq=seq, record_id=f"r{seq}")

    stream = Stream()
    selected, strata = replay.sample_records(stream, 7, 3)
    assert stream.calls == [False, False]
    assert len(selected) == 7
    assert strata == {"tlp|pass": {"records": 1000, "sampled": 7}}


def test_largest_remainders_minimum_and_ties():
    assert replay._allocation({"a": 5, "b": 3, "c": 2}, 6) == {"a": 3, "b": 2, "c": 1}
    assert replay._allocation({"a": 98, "b": 1, "c": 1}, 3) == {"a": 1, "b": 1, "c": 1}
    assert replay._allocation({"b": 3, "a": 3}, 3) == {"a": 2, "b": 1}
    assert replay._allocation({}, 10) == {}
    with pytest.raises(ValueError, match="nonempty strata"):
        replay._allocation({"a": 5, "b": 2}, 1)


def test_cli_same_and_worker_independence(duck_run, tmp_path):
    before = file_digest(duck_run / "ledger.sqlite")
    first, one = _cli(duck_run, tmp_path / "one.json")
    second, two = _cli(duck_run, tmp_path / "two.json", workers=2)
    assert first.returncode == second.returncode == 0, (first.stderr, second.stderr)
    assert first.stdout == second.stdout == "replay sampled=6 same=6 invalid_kept=0 different=0\n"
    assert first.stdout.isascii()
    assert one.pop("elapsed_s") >= 0
    assert two.pop("elapsed_s") >= 0
    assert one == two
    assert one["schema"] == 1
    assert one["harness"] == harness_hash()["hash"]
    assert one["source"] == {"run_dir": str(duck_run.resolve()), "ledger_sha256": before, "records": 9}
    assert (one["sample"], one["seed"], one["sampled"]) == (6, 16, 6)
    assert one["same"] == 6 and one["different"] == []
    assert one["attribution_not_replayed"] == 0
    assert file_digest(duck_run / "ledger.sqlite") == before
    payload = (tmp_path / "one.json").read_text(encoding="ascii")
    assert payload == json.dumps(json.loads(payload), sort_keys=True, ensure_ascii=True, indent=2) + "\n"


def test_cli_reports_only_the_tampered_record(duck_run, tmp_path):
    original_digest = file_digest(duck_run / "ledger.sqlite")
    copied = tmp_path / "copy"
    shutil.copytree(duck_run, copied)

    def tamper(body):
        body["label"].update(y="invalid", invalid_reason="query_error")

    changed = _change_record(copied, 1, tamper)
    proc, result = _cli(copied, tmp_path / "different.json", sample=99, workers=2)
    assert proc.returncode == 1, proc.stderr
    assert result["same"] == 8
    assert len(result["different"]) == 1
    diff = result["different"][0]
    assert (diff["record_id"], diff["seq"], diff["oracle"]) == (changed["record_id"], 1, "tlp")
    assert diff["fields"] == {"y": ["invalid", "pass"], "invalid_reason": ["query_error", None]}
    assert file_digest(duck_run / "ledger.sqlite") == original_digest


def test_cli_relaxed_invalid_and_attribution_counts(duck_run, tmp_path):
    copied = tmp_path / "copy"
    shutil.copytree(duck_run, copied)
    for seq, reason in ((8, "unstable_rerun"), (9, "timeout")):
        _change_record(copied, seq, lambda body, reason=reason: body["label"].update(invalid_reason=reason))

    def attributed(body):
        body["label"]["cve"].update(
            attribution={"status": "ran", "consistent": True}, tier=2,
            minimize={"status": "skipped", "reason": "attributed"},
            profile={"status": "skipped", "reason": "attributed"},
        )

    _change_record(copied, 1, attributed)
    proc, result = _cli(copied, tmp_path / "relaxed.json", sample=99)
    assert proc.returncode == 0, proc.stderr
    assert result["different"] == [] and result["same"] == 9
    assert result["invalid_kept"] == 2
    assert result["attribution_not_replayed"] == 1


@pytest.mark.parametrize("reason", ["unstable_rerun", "timeout"])
def test_relaxed_invalid_requires_invalid(reason):
    old = Label(y="invalid", oracle="tlp", invalid_reason=reason)
    new = Label(y="invalid", oracle="norec", invalid_reason="query_error", cve={"anything": True})
    assert replay.compare_labels(old, new) == {}
    assert replay.compare_labels(old, Label(y="pass", oracle="tlp")) == {"y": ["invalid", "pass"]}
    assert replay.compare_labels(old, Label(y="fail", oracle="tlp", fail_kind="crash")) == {"y": ["invalid", "fail"]}


def _profiled():
    return Label(
        y="fail", oracle="plan_variant", fail_kind="wrong_result",
        identity=IdentityEvidence(switches=("join",), behavior={"shape": [1, 2]}),
        cve={"tier": 3, "rerun": {"status": "ran", "attempts": 3},
             "premise": {"violations": []}, "attribution": {"status": "skipped", "reason": "not_requested"},
             "minimize": {"status": "ran", "query": "SELECT 1"},
             "profile": {"status": "ran", "fix_set": ["join"]}},
    )


@pytest.mark.parametrize("field", ["rerun", "premise", "minimize", "profile", "attribution", "tier"])
def test_cve_evidence_changes_are_detected(field):
    old = _profiled()
    changed = copy.deepcopy(old.cve)
    changed[field] = 4 if field == "tier" else {"status": "changed"}
    assert replay.compare_labels(old, replace(old, cve=changed)) == {f"cve.{field}": [old.cve[field], changed[field]]}


@pytest.mark.parametrize("field,value", [
    ("oracle", "tlp"), ("fail_kind", "crash"),
    ("identity", IdentityEvidence(switches=("other",))),
    ("identity", IdentityEvidence(error_class="internal")),
    ("identity", IdentityEvidence(behavior={"shape": [2, 1]})),
])
def test_label_and_entire_identity_are_compared(field, value):
    old = _profiled()
    changes = replay.compare_labels(old, replace(old, **{field: value}))
    assert set(changes) == {field}


def test_detail_is_ignored_and_attributed_profile_still_checked():
    old = _profiled()
    assert replay.compare_labels(old, replace(old, detail={"engine_version": "changed"})) == {}
    attributed = {**old.cve, "attribution": {"status": "ran", "consistent": False}}
    old = replace(old, cve=attributed)
    new = replace(old, cve={**old.cve, "tier": 1, "attribution": {"status": "skipped"}})
    assert replay.compare_labels(old, new) == {}
    new = replace(new, cve={**new.cve, "profile": {"status": "skipped"}})
    assert replay.compare_labels(old, new) == {"cve.profile": [old.cve["profile"], {"status": "skipped"}]}


def test_certify_arguments_and_exception(duck_run, monkeypatch):
    record = next(RunData.open(duck_run).iter_records())
    record = replace(record, label=_profiled(), spec={"rule": "known_rule", "hypothesis": "not_replayed"})
    calls = []

    def certify(*args, **kwargs):
        calls.append((args, kwargs))
        return record.label

    monkeypatch.setattr(replay.cve, "certify", certify)
    assert replay._replay_record(record) == {}
    assert calls == [((record.case, "plan_variant"), {"diagnose": True, "rewrite_rule": "known_rule"})]
    record = replace(record, spec=None, label=Label(y="pass", oracle="tlp"))
    assert replay._replay_record(record) == {}
    assert calls[-1] == ((record.case, "tlp"), {"diagnose": False, "rewrite_rule": None})

    def broken(*args, **kwargs):
        raise RuntimeError("replay failed")

    monkeypatch.setattr(replay.cve, "certify", broken)
    assert replay._replay_record(record) == {"exception": "RuntimeError: replay failed"}


def test_source_run_dir_relative_to_framework(duck_run, tmp_path, monkeypatch):
    # Simulate framework-contained artifacts without writing outside tmp_path.
    monkeypatch.setattr(replay, "_FRAMEWORK", duck_run.parent)
    result = replay.replay(duck_run, sample=3, seed=16)
    assert result["source"]["run_dir"] == "run"
    assert result["different"] == []
    assert replay._run_dir(FRAMEWORK / "results" / "s08" / "longrun") == str((FRAMEWORK / "results" / "s08" / "longrun").resolve())
    monkeypatch.setattr(replay, "_FRAMEWORK", FRAMEWORK)
    assert replay._run_dir(FRAMEWORK / "results" / "s08" / "longrun") == "results/s08/longrun"


@pytest.mark.parametrize("extra", [["--sample", "0"], ["--workers", "0"], ["--sample", "1"]])
def test_cli_usage_errors(duck_run, tmp_path, extra):
    proc = subprocess.run(
        [sys.executable, "-m", "surprise.metrics.replay", str(duck_run),
         "--sample", "6", "--seed", "16", "--out", str(tmp_path / "bad.json"), *extra],
        cwd=FRAMEWORK, capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 2
    assert "error:" in proc.stderr
    assert not (tmp_path / "bad.json").exists()
