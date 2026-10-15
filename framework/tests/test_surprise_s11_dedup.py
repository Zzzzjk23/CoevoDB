"""Offline dedup: sigma against the pre-execution membership test, on a short real run."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from diagnosis.signature import SignatureEngine
from surprise.experiments.loop import run
from surprise.gates.s04 import load
from surprise.metrics.dedup import compare_dedup, main
from surprise.metrics.rq import label_key
from surprise.metrics.rundata import RunData


@pytest.fixture(scope="module")
def f1_run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One real loop: the F1 bootstrap plus two further experiments."""
    out = tmp_path_factory.mktemp("dedup") / "run"
    run(
        out,
        seed=1,
        engines=("duckdb",),
        oracles=("plan_variant",),
        max_experiments=2,
        bootstrap=[{"case": load("F1").to_dict(), "oracle": "plan_variant", "rule": None}],
    )
    return out


@pytest.fixture(scope="module")
def compared(f1_run: Path) -> dict:
    before = _digest(f1_run)
    result = compare_dedup(f1_run)
    after = _digest(f1_run)
    return {"path": f1_run, "before": before, "after": after, "result": result}


def test_every_field_matches_the_ledger(compared: dict) -> None:
    path: Path = compared["path"]
    result = compared["result"]
    data = RunData.open(path)
    failures = [record for record in data.records if record.label.y == "fail"]
    progress = {row["record_id"]: row for row in data.progress}
    assert result["run"] == str(path.resolve())
    assert Path(result["run"]).is_absolute()
    assert result["failures"] == len(failures) > 0
    assert result["skipped"] == sum(1 for row in result["rows"] if row["truth_key"] is None)
    assert result["truth_duplicates"] == sum(1 for row in result["rows"] if row["truth_dup"] is True)
    assert set(result) == {
        "run",
        "failures",
        "skipped",
        "truth_duplicates",
        "sigma",
        "membership",
        "attribution_executions",
        "rows",
    }
    rows = result["rows"]
    assert [row["record_id"] for row in rows] == [record.record_id for record in failures]
    assert [row["seq"] for row in rows] == [record.seq for record in failures]
    sigma = SignatureEngine(runner_factory=lambda: None, checker=None)
    truth_seen: set[str] = set()
    sigma_seen: set[str] = set()
    counts = {"sigma": [0, 0, 0], "membership": [0, 0, 0]}
    sigma_executions = 0
    attribution = 0
    for record, row in zip(failures, rows):
        assert set(row) == {
            "record_id",
            "seq",
            "zone",
            "member_dup",
            "profile",
            "truth_key",
            "truth_dup",
            "minimal",
            "error_class",
            "sigma_key",
            "sigma_dup",
            "reprofiled",
        }
        assert row["zone"] == progress[record.record_id]["zone"]
        assert row["member_dup"] is (row["zone"] == "confirmed")
        assert row["error_class"] == record.label.identity.error_class
        assert isinstance(row["reprofiled"], bool)
        attribution += _attribution_executions(record.label)
        if not row["reprofiled"]:
            if _profile_ran(record.label):
                assert row["truth_key"] == label_key(record)
                assert row["profile"]["status"] == "ran"
                if record.label.cve["minimize"]["status"] == "ran":
                    assert row["minimal"] == record.label.cve["minimize"]["case"]
                else:
                    assert row["minimal"] == record.case.to_dict()
            else:
                assert row["truth_key"] is None
                assert row["sigma_key"] is None
                assert row["profile"] is None
        else:
            assert isinstance(row["profile"], dict) and row["profile"]["status"] == "ran"
            assert isinstance(row["truth_key"], str) and row["truth_key"] != ""
            assert set(row["minimal"]) >= {"engine", "setup", "query", "predicate"}
        if row["truth_key"] is None:
            assert row["truth_dup"] is None
            assert row["sigma_key"] is None
            assert row["sigma_dup"] is None
        else:
            assert row["truth_dup"] is (row["truth_key"] in truth_seen)
            truth_seen.add(row["truth_key"])
            assert isinstance(row["sigma_key"], str) and row["sigma_key"] != ""
            assert row["sigma_key"] == _sigma_key(sigma, row)
            assert row["sigma_dup"] is (row["sigma_key"] in sigma_seen)
            sigma_seen.add(row["sigma_key"])
            sigma_executions += int(row["profile"]["executions"])
            _tally(counts, "sigma", row["sigma_dup"], row["truth_dup"])
            _tally(counts, "membership", row["member_dup"], row["truth_dup"])
    assert result["attribution_executions"] == attribution
    assert result["sigma"]["executions"] == sigma_executions
    assert result["membership"]["executions"] == 0
    for name, (tp, fp, fn) in counts.items():
        part = result[name]
        assert set(part) == {"tp", "fp", "fn", "precision", "recall", "executions"}
        assert part["tp"] == tp and part["fp"] == fp and part["fn"] == fn
        assert part["precision"] == (None if tp + fp == 0 else tp / (tp + fp))
        assert part["recall"] == (None if tp + fn == 0 else tp / (tp + fn))
    again = compare_dedup(path, limit=1, reprofile=False)
    assert again["failures"] == 1
    assert again["rows"][0]["record_id"] == rows[0]["record_id"]
    assert again["rows"][0]["seq"] == rows[0]["seq"]
    if not rows[0]["reprofiled"]:
        assert again["rows"][0] == rows[0]
    none = compare_dedup(path, limit=0, reprofile=False)
    assert none["failures"] == 0 and none["rows"] == [] and none["skipped"] == 0
    assert none["truth_duplicates"] == 0
    assert none["sigma"]["precision"] is None and none["sigma"]["recall"] is None
    assert none["membership"]["executions"] == 0 and none["attribution_executions"] == 0
    with pytest.raises(ValueError):
        compare_dedup(path, limit=-1)


def test_directory_is_not_modified(compared: dict) -> None:
    assert compared["before"] == compared["after"]
    assert compared["before"] == _digest(compared["path"])


def test_cli_writes_the_same_row(compared: dict, tmp_path: Path) -> None:
    out = tmp_path / "dedup.json"
    assert main([str(compared["path"]), "--out", str(out), "--limit", "1", "--no-reprofile"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["failures"] == 1
    assert payload["rows"][0]["record_id"] == compared["result"]["rows"][0]["record_id"]
    assert _digest(compared["path"]) == compared["after"]


def test_reprofile_false_skips_an_unprofiled_failure(compared: dict, tmp_path: Path) -> None:
    copied = tmp_path / "run"
    shutil.copytree(compared["path"], copied)
    record_id = _clear_profile(copied)
    before = _digest(copied)
    result = compare_dedup(copied, reprofile=False)
    assert _digest(copied) == before
    row = next(item for item in result["rows"] if item["record_id"] == record_id)
    assert row["reprofiled"] is False
    assert row["profile"] is None
    assert row["truth_key"] is None and row["truth_dup"] is None
    assert row["sigma_key"] is None and row["sigma_dup"] is None
    assert result["skipped"] >= 1
    data = RunData.open(copied)
    record = next(item for item in data.records if item.record_id == record_id)
    assert row["error_class"] == record.label.identity.error_class
    assert row["minimal"] == record.case.to_dict()
    assert row["zone"] == data.row(record_id)["zone"]
    assert row["member_dup"] is (row["zone"] == "confirmed")


def test_version_mismatch_raises_before_writing(compared: dict, tmp_path: Path) -> None:
    copied = tmp_path / "run"
    shutil.copytree(compared["path"], copied)
    _clear_profile(copied, version="0.0.0")
    before = _digest(copied)
    with pytest.raises(ValueError, match="0.0.0"):
        compare_dedup(copied, reprofile=True)
    assert _digest(copied) == before


def _tally(counts: dict[str, list[int]], name: str, decided: bool, truth: bool) -> None:
    if decided and truth:
        counts[name][0] += 1
    elif decided:
        counts[name][1] += 1
    elif truth:
        counts[name][2] += 1


def _sigma_key(engine: SignatureEngine, row: dict) -> str:
    profile = row["profile"]
    minimal = row["minimal"]
    candidate = SimpleNamespace(
        r1_summary=None,
        r2_summary=None,
        notes=row["error_class"] or "",
        schema_sqls=[],
        inserts=[],
        q1="",
        q2="",
    )
    signed = engine._signature(
        fix_kind=profile["fix_kind"],
        fix_set=list(profile["fix_set"]),
        plan_diff=list(profile["plan_diff"]),
        nu=profile["version_ladder"],
        executions=int(profile["executions"]),
        candidate=candidate,
        minimal={
            "schema_sqls": list(minimal["setup"]),
            "inserts": [],
            "q1": minimal["query"],
            "q2": minimal["predicate"] or "",
        },
    )
    return signed["key"]


def _profile_ran(label) -> bool:
    profile = label.cve.get("profile") if isinstance(label.cve, dict) else None
    return isinstance(profile, dict) and profile.get("status") == "ran"


def _attribution_executions(label) -> int:
    attribution = label.cve.get("attribution") if isinstance(label.cve, dict) else None
    if not isinstance(attribution, dict):
        return 0
    executions = attribution.get("executions")
    if isinstance(executions, bool) or not isinstance(executions, int):
        return 0
    return executions


def _clear_profile(root: Path, *, version: str | None = None) -> str:
    """Drop the first failure's profile. Optionally rewrite the recorded DuckDB version."""
    connection = sqlite3.connect(root / "ledger.sqlite")
    try:
        found = connection.execute(
            "SELECT record_id, record_json FROM records WHERE y = 'fail' ORDER BY seq LIMIT 1"
        ).fetchone()
        assert found is not None
        record_id, blob = found
        payload = json.loads(blob)
        payload["label"]["cve"]["profile"] = {"status": "skipped", "reason": "attributed"}
        payload["label"]["cve"]["minimize"] = {"status": "skipped", "reason": "attributed"}
        connection.execute(
            "UPDATE records SET record_json = ? WHERE record_id = ?",
            (json.dumps(payload), record_id),
        )
        if version is not None:
            run_id, manifest_blob = connection.execute("SELECT run_id, manifest_json FROM runs").fetchone()
            manifest = json.loads(manifest_blob)
            manifest["environment"]["engines"]["duckdb"] = version
            connection.execute(
                "UPDATE runs SET manifest_json = ? WHERE run_id = ?",
                (json.dumps(manifest), run_id),
            )
        connection.commit()
    finally:
        connection.close()
    return record_id


def _digest(root: Path) -> dict[str, str]:
    found = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            found[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found
