"""Streaming run data: iter_records, run_metrics and dedup do not load the whole ledger."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from surprise.gates.s06 import fail_label, invalid_label, pass_label
from surprise.harness.contracts import ExperimentRecord, Label, SqlCase
from surprise.harness.ledger import Ledger
from surprise.metrics import rundata as rundata_mod
from surprise.metrics.curve import surprise_curve
from surprise.metrics.dedup import compare_dedup
from surprise.metrics.dups import duplicate_rate
from surprise.metrics.rq import (
    _brier,
    _calibration,
    _families_via,
    _high_surprise,
    _invalid,
    _llm_features,
    _mean,
    _profiled_keys,
    _pure_llm,
    _surprise,
    _valid,
    label_key,
    ledger_families,
    run_metrics,
)
from surprise.metrics.rundata import RunData

_WHEN = "2020-01-01T00:00:00+00:00"


def _digest(root: Path) -> dict[str, str]:
    found = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            found[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def _record(
    run_id: str,
    seq: int,
    label,
    *,
    p_t: float | None = None,
    phi_dict: dict | None = None,
    spec: dict | None = None,
    purpose: str = "explore",
    engine: str = "duckdb",
) -> ExperimentRecord:
    return ExperimentRecord(
        record_id=f"{run_id}:{seq}",
        run_id=run_id,
        seq=seq,
        case=SqlCase(engine=engine, setup=(), query="SELECT 1"),
        label=label,
        purpose=purpose,
        created_at=_WHEN,
        spec=spec,
        phi=phi_dict,
        p_t=p_t,
    )


def _with_detail(label: Label, detail: dict) -> Label:
    data = label.to_dict()
    data["detail"] = detail
    return Label.from_dict(data)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _run(
    root: Path,
    records: list[ExperimentRecord],
    *,
    config: dict | None = None,
    report: dict | None = None,
    progress: list[dict] | None = None,
    manifest: dict | None = None,
    books: dict[str, list[dict]] | None = None,
    run_id: str = "run-1",
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    body = {"seed": 1, "engines": ["duckdb"], "oracles": ["plan_variant"]} if config is None else config
    _write_json(root / "config.json", body)
    if report is not None:
        _write_json(root / "report.json", report)
    if progress:
        _write_jsonl(root / "progress.jsonl", progress)
    if books:
        for name, rows in books.items():
            _write_jsonl(root / "llm" / f"{name}.jsonl", rows)
    ledger = Ledger(root / "ledger.sqlite")
    try:
        ledger.start_run(run_id, {} if manifest is None else manifest)
        for record in records:
            ledger.append(record)
    finally:
        ledger.close()
    return root


def _ledger_records(root: Path) -> list[ExperimentRecord]:
    ledger = Ledger(root / "ledger.sqlite")
    try:
        run_id = ledger.run_ids()[0]
        return list(ledger.records(run_id=run_id))
    finally:
        ledger.close()


def _rich(tmp_path: Path) -> tuple[Path, list[ExperimentRecord]]:
    """Seven records inserted out of seq order, including calibration endpoints."""
    fat = _with_detail(
        fail_label("f1"),
        {
            "note": '","detail":"trap"',
            "inner": {"fail_kind": "trap", "detail": "nested"},
            "pad": "q" * 4000,
        },
    )
    records = [
        _record("run-1", 4, fail_label("f1"), p_t=0.95, purpose="generalize"),
        _record(
            "run-1",
            1,
            fat,
            p_t=0.05,
            phi_dict={"features": ["ast:clause:where", 3, "ast:stmt:select"], "engine": "duckdb"},
            purpose="explore",
        ),
        _record("run-1", 7, pass_label(), p_t=None),
        _record("run-1", 2, pass_label(), p_t=0.5),
        _record("run-1", 6, fail_label("f1"), p_t=1.0),
        _record("run-1", 3, invalid_label("query_error"), p_t=0.2),
        _record("run-1", 5, pass_label(), p_t=0.0),
    ]
    progress = [
        {"record_id": "run-1:1", "elapsed_s": 0.25, "triage": "old", "lane": "implement", "rule": "hand"},
        {
            "record_id": "run-1:1",
            "elapsed_s": 1.5,
            "triage": "new_family",
            "lane": "bet",
            "rule": "llm:invent",
        },
        {"record_id": "run-1:4", "elapsed_s": 4.0, "triage": "duplicate", "lane": "translate", "rule": None},
    ]
    books = {
        "conjectures": [
            {"type": "settle", "state": "kept", "record_id": "run-1:2", "conjecture_id": "c1"},
            {"type": "settle", "state": "broken", "record_id": "run-1:4", "conjecture_id": "c1"},
        ]
    }
    root = _run(
        tmp_path / "rich",
        records,
        report={"status": "budget_experiments", "wall_s": 3600.0},
        progress=progress,
        books=books,
    )
    return root, records


def test_iter_records_matches_the_ledger_and_open_does_not_read_them(tmp_path: Path, monkeypatch) -> None:
    root, _records = _rich(tmp_path)
    before = _digest(root)

    def boom(*_args, **_kwargs):
        raise AssertionError("Ledger.records was called")

    monkeypatch.setattr(Ledger, "records", boom)
    data = RunData.open(root)
    assert data.record_count == 7
    assert data.kind == "surprise"
    assert data._materialized is None
    streamed = list(data.iter_records())
    assert data._materialized is None
    assert _digest(root) == before
    monkeypatch.undo()

    expected = _ledger_records(root)
    assert streamed == expected
    assert [record.seq for record in streamed] == [1, 2, 3, 4, 5, 6, 7]
    assert data.records == expected
    assert data.records is data.records
    again = RunData.open(root)
    list(again.iter_records())
    assert again.records[0].label.detail["pad"].startswith("q")
    assert _digest(root) == before


def test_kind_is_pure_llm_sqlancer_or_surprise(tmp_path: Path) -> None:
    surprise = _run(tmp_path / "surprise", [_record("run-1", 1, pass_label())], manifest={"baseline": "other"})
    pure = _run(
        tmp_path / "pure",
        [_record("run-1", 1, pass_label(), spec={"expect": "pass"}, purpose="pure_llm")],
        config={"seed": 1, "engine": "duckdb"},
        manifest={"baseline": "pure_llm"},
    )
    sqlancer = _run(
        tmp_path / "sql",
        [_record("run-1", 1, pass_label())],
        config={"seed": 1, "engine": "sqlite", "oracles": ["norec"]},
        manifest={"baseline": "sqlancer"},
    )
    assert RunData.open(surprise).kind == "surprise"
    assert RunData.open(pure).kind == "pure_llm"
    assert RunData.open(sqlancer).kind == "sqlancer"
    assert run_metrics(pure)["run"]["engines"] == ["duckdb"]
    assert run_metrics(sqlancer)["run"]["engines"] == ["sqlite"]
    assert run_metrics(surprise)["run"]["engines"] == ["duckdb"]


def test_run_metrics_matches_the_materialized_helpers(tmp_path: Path, monkeypatch) -> None:
    root, _records = _rich(tmp_path)
    before = _digest(root)
    monkeypatch.setattr(rundata_mod, "_SLIM_ABOVE", 0)
    window = 4
    got = run_metrics(root, window=window)
    assert got == run_metrics(root, window=window)
    assert _digest(root) == before

    data = RunData.open(root)
    records = _ledger_records(root)
    progress = {
        row["record_id"]: row
        for row in data.progress
        if isinstance(row, dict) and isinstance(row.get("record_id"), str)
    }
    assert got["run"]["experiments"] == len(records)
    assert got["rq1"]["executions"] == len(records)
    assert got["rq1"]["families"] == ledger_families(records, data.progress)
    assert got["rq1"]["family_count"] == 1
    assert got["rq1"]["families"][0]["elapsed_s"] == 1.5
    assert got["rq1"]["families"][0]["seq"] == 1
    assert got["rq1"]["duplicate_rate"] == duplicate_rate(_profiled_keys(records))
    assert got["rq1"]["theory_families"] is None
    assert got["rq1"]["families_per_1000"] == 1000.0 / len(records)
    brier, reference = _brier(records)
    assert got["rq2"]["valid"] == len(_valid(records))
    assert got["rq2"]["brier"] == brier
    assert got["rq2"]["brier_reference"] == reference
    assert got["rq2"]["mean_surprise"] == _mean([_surprise(record) for record in records])
    assert got["rq2"]["calibration"] == _calibration(records)
    assert got["rq2"]["high_surprise"] == _high_surprise(records, progress)
    assert got["rq2"]["curve"] == surprise_curve(records, window=window)
    assert got["rq2"]["curve"] == surprise_curve(records, window=window)
    assert len(got["rq2"]["curve"]) == 1
    invented = _llm_features(data.registry)
    assert got["rq3"]["families_via"] == _families_via(records, progress, invented)
    assert got["rq3"]["pure_llm"] is None
    assert got["rq3"]["timeline"] == [
        {"seq": 2, "source": "conjecture", "kept": True, "accuracy": 1.0},
        {"seq": 4, "source": "conjecture", "kept": False, "accuracy": 0.5},
    ]
    assert got["rq4"]["invalid"] == _invalid(records, len(records))
    assert got["cost"]["executions"] == len(records)

    slim = list(data.iter_records(keep_detail=False))
    assert len(slim) == len(records)
    for full, narrow in zip(records, slim):
        left, right = full.to_dict(), narrow.to_dict()
        left["label"]["detail"] = {}
        assert right["label"]["detail"] == {}
        assert left == right
        assert label_key(full) == label_key(narrow)


def test_pure_llm_still_counts_expect(tmp_path: Path) -> None:
    records = [
        _record("run-1", 1, pass_label(), spec={"expect": "pass"}, purpose="pure_llm"),
        _record("run-1", 2, pass_label(), spec={"expect": "fail"}, purpose="pure_llm"),
        _record("run-1", 3, invalid_label(), spec={"expect": "pass"}, purpose="pure_llm"),
    ]
    root = _run(
        tmp_path / "pure",
        records,
        config={"seed": 3, "engine": "datafusion"},
        manifest={"baseline": "pure_llm"},
    )
    got = run_metrics(root)
    assert got["rq3"]["pure_llm"] == _pure_llm(_ledger_records(root))
    assert got["run"]["kind"] == "pure_llm"
    assert got["run"]["engines"] == ["datafusion"]


def test_sqlancer_executions_come_from_the_report(tmp_path: Path) -> None:
    records = [
        _record("run-1", 1, fail_label("f1"), p_t=0.4),
        _record("run-1", 2, invalid_label("timeout", "norec")),
    ]
    config = {"seed": 1, "engine": "duckdb", "oracles": ["norec"]}
    manifest = {"baseline": "sqlancer"}
    counted = _run(
        tmp_path / "counted",
        records,
        config=config,
        report={"status": "budget_minutes", "wall_s": 12.0, "executions": 5000},
        manifest=manifest,
    )
    metrics = run_metrics(counted)
    assert metrics["run"]["kind"] == "sqlancer"
    assert metrics["run"]["experiments"] == 5000
    assert metrics["run"]["engines"] == ["duckdb"]
    assert metrics["rq1"]["executions"] == 5000
    assert metrics["rq1"]["family_count"] == 1
    assert metrics["rq1"]["families_per_1000"] == 1000.0 / 5000
    assert metrics["rq4"]["invalid"]["count"] == 1
    assert metrics["rq4"]["invalid"]["rate"] == 1 / 5000
    assert metrics["cost"]["executions"] == 5000
    assert metrics["cost"]["per_family"]["executions"] == 5000.0
    assert metrics["rq2"]["valid"] == 1

    missing = _run(tmp_path / "missing", records, config=config, report={"status": "budget_minutes"}, manifest=manifest)
    blank = run_metrics(missing)
    assert blank["rq1"]["executions"] is None
    assert blank["run"]["experiments"] is None
    assert blank["rq1"]["families_per_1000"] is None
    assert blank["rq4"]["invalid"]["rate"] is None
    assert blank["rq4"]["invalid"]["count"] == 1
    assert blank["cost"]["executions"] is None
    assert blank["cost"]["per_family"]["executions"] is None
    assert blank["cost"]["per_family"]["llm_calls"] == 0.0
    assert blank["rq1"]["family_count"] == 1

    absent = _run(tmp_path / "absent", records, config=config, manifest=manifest)
    assert run_metrics(absent)["rq1"]["executions"] is None

    flagged = _run(
        tmp_path / "flag",
        records,
        config=config,
        report={"executions": True},
        manifest=manifest,
    )
    assert run_metrics(flagged)["rq1"]["executions"] is None

    zero = _run(
        tmp_path / "zero",
        records,
        config=config,
        report={"executions": 0, "wall_s": 1.0},
        manifest=manifest,
    )
    zero_metrics = run_metrics(zero)
    assert zero_metrics["rq1"]["executions"] == 0
    assert zero_metrics["rq1"]["families_per_1000"] is None
    assert zero_metrics["rq4"]["invalid"]["rate"] is None
    assert zero_metrics["cost"]["per_family"]["executions"] == 0.0


def test_dedup_keeps_failures_in_seq_order(tmp_path: Path) -> None:
    records = [
        _record("run-1", 3, fail_label("f1_raw")),
        _record("run-1", 1, pass_label()),
        _record("run-1", 4, invalid_label()),
        _record("run-1", 2, fail_label("f1")),
    ]
    root = _run(tmp_path / "dedup", records)
    before = _digest(root)
    result = compare_dedup(root, reprofile=False)
    limited = compare_dedup(root, limit=1, reprofile=False)
    assert _digest(root) == before
    fails = [record for record in _ledger_records(root) if record.label.y == "fail"]
    assert [row["seq"] for row in result["rows"]] == [record.seq for record in fails]
    assert [row["record_id"] for row in result["rows"]] == [record.record_id for record in fails]
    assert result["failures"] == 2
    assert result["rows"][0]["seq"] == 2
    assert [row["record_id"] for row in limited["rows"]] == [fails[0].record_id]
    assert limited["failures"] == 1


def test_run_metrics_matches_complete_pre_s15_output(tmp_path: Path) -> None:
    """Full reference dict from run_metrics at the package base commit."""
    root, _ = _rich(tmp_path)
    expected = {
        "run": {
            "run_id": "run-1",
            "kind": "surprise",
            "seed": 1,
            "engines": [
                "duckdb"
            ],
            "oracles": [
                "plan_variant"
            ],
            "status": "budget_experiments",
            "experiments": 7,
            "wall_s": 3600.0,
            "arm": None,
            "llm_roles": []
        },
        "rq1": {
            "executions": 7,
            "families": [
                {
                    "key": "fix|duckdb|deliminator,filter_pushdown",
                    "record_id": "run-1:1",
                    "seq": 1,
                    "elapsed_s": 1.5
                }
            ],
            "family_count": 1,
            "families_per_1000": 142.85714285714286,
            "families_per_hour": 1.0,
            "first_family": {
                "seq": 1,
                "elapsed_s": 1.5
            },
            "theory_families": None,
            "duplicate_rate": 0.6666666666666666
        },
        "rq2": {
            "valid": 5,
            "brier": 0.231,
            "brier_reference": 0.24,
            "mean_surprise": 1.7986428921103796,
            "calibration": [
                {
                    "lo": 0.0,
                    "hi": 0.05,
                    "count": 1,
                    "mean_p": 0.0,
                    "fail_rate": 0.0
                },
                {
                    "lo": 0.05,
                    "hi": 0.2,
                    "count": 1,
                    "mean_p": 0.05,
                    "fail_rate": 1.0
                },
                {
                    "lo": 0.2,
                    "hi": 0.4,
                    "count": 0,
                    "mean_p": None,
                    "fail_rate": None
                },
                {
                    "lo": 0.4,
                    "hi": 0.6,
                    "count": 1,
                    "mean_p": 0.5,
                    "fail_rate": 0.0
                },
                {
                    "lo": 0.6,
                    "hi": 0.8,
                    "count": 0,
                    "mean_p": None,
                    "fail_rate": None
                },
                {
                    "lo": 0.8,
                    "hi": 0.95,
                    "count": 0,
                    "mean_p": None,
                    "fail_rate": None
                },
                {
                    "lo": 0.95,
                    "hi": 1.0,
                    "count": 2,
                    "mean_p": 0.975,
                    "fail_rate": 1.0
                }
            ],
            "high_surprise": {
                "threshold": 4.0,
                "count": 1,
                "new_family": 1,
                "share": 1.0
            },
            "window": 4,
            "curve": [
                1.7986428921103796
            ],
            "teeth": []
        },
        "rq3": {
            "conjectures": {
                "registered": 0,
                "rejected": 0,
                "with_settled": 1,
                "survived": 0,
                "survival_rate": 0.0
            },
            "predictions": {
                "total": 0,
                "kept": 1,
                "broken": 1,
                "void": 0,
                "open": -2,
                "accuracy": 0.5
            },
            "translations": {
                "total": 0,
                "kept": 0,
                "broken": 0,
                "accuracy": None
            },
            "timeline": [
                {
                    "seq": 2,
                    "source": "conjecture",
                    "kept": True,
                    "accuracy": 1.0
                },
                {
                    "seq": 4,
                    "source": "conjecture",
                    "kept": False,
                    "accuracy": 0.5
                }
            ],
            "families_via": {
                "implement": 0,
                "bet": 1,
                "translate": 0,
                "llm_rule": 1,
                "invented_feature": 0
            },
            "calls": {
                "by_role": {},
                "total": 0,
                "network": 0,
                "input_tokens": 0,
                "output_tokens": 0
            },
            "calls_per_family": 0.0,
            "tokens_per_family": 0.0,
            "pure_llm": None
        },
        "rq4": {
            "invalid": {
                "count": 1,
                "rate": 0.14285714285714285,
                "by_reason": {
                    "query_error": 1
                },
                "by_oracle": {
                    "cross_dbms": 1
                }
            },
            "duplicate_rate": 0.6666666666666666,
            "theory_length": [],
            "edits": {
                "accepted": 0,
                "rejected": 0,
                "rolled_back": 0
            },
            "in_out": {
                "edits": 0,
                "mean_in": None,
                "mean_out": None,
                "gap": None
            }
        },
        "rq5": {
            "ciao": None,
            "arm": None
        },
        "rq6": {
            "recall": None,
            "boundary": None
        },
        "cost": {
            "executions": 7,
            "wall_s": 3600.0,
            "llm_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "usd": None,
            "per_family": {
                "executions": 7.0,
                "llm_calls": 0.0,
                "tokens": 0.0,
                "usd": None
            }
        }
    }
    assert run_metrics(root, window=4) == expected


@pytest.mark.parametrize("chunk_size", [1, 7, 64, 4096])
def test_metric_scan_keeps_fields_around_detail_across_chunks(tmp_path: Path, monkeypatch, chunk_size: int) -> None:
    record = _record(
        "run-1", 1,
        _with_detail(fail_label("f1"), {"nested": [{"detail": '\\"}{\\', "text": "中文"}], "pad": "x" * 4000}),
        p_t=0.2,
        spec={"fail_kind": "keep this suffix", "detail": {"keep": "中文"}},
    )
    payload = record.to_dict()
    payload["label"]["cve"]["detail"] = {"keep": True}
    payload["case"]["query"] = 'SELECT \'"label":{"detail":{"trap":"\\\\"}}\''
    record = ExperimentRecord.from_dict(payload)
    root = _run(tmp_path / "unicode # run", [record])
    # Valid noncanonical JSON: label.detail is last, with nested namesakes
    # before it and a namesake in spec after it. Split UTF-8 and escapes too.
    text = json.dumps(payload, ensure_ascii=False, indent=2).replace('"label"', '"\\u006cabel"')
    with sqlite3.connect(root / "ledger.sqlite") as conn:
        conn.execute("UPDATE records SET record_json = ?", (text,))
    before = _digest(root)
    monkeypatch.setattr(rundata_mod, "_SLIM_ABOVE", 0)
    monkeypatch.setattr(rundata_mod, "_CHUNK", chunk_size)
    data = RunData.open(root)
    expected = record.to_dict()
    expected["label"]["detail"] = {}
    assert [row.to_dict() for row in data.iter_records(keep_detail=False)] == [expected]
    assert list(data.iter_records()) == [record]
    assert _digest(root) == before


def test_metrics_and_dedup_do_not_materialize_records(tmp_path: Path, monkeypatch) -> None:
    root, _ = _rich(tmp_path)

    def materialized(_self):
        raise AssertionError("compatibility records property was accessed")

    monkeypatch.setattr(RunData, "records", property(materialized))
    assert run_metrics(root, window=4)["rq1"]["executions"] == 7
    assert compare_dedup(root, reprofile=False)["failures"] == 3


def test_empty_run_and_missing_ledger_are_read_only(tmp_path: Path) -> None:
    root = _run(tmp_path / "empty", [])
    before = _digest(root)
    data = RunData.open(root)
    assert data.record_count == 0
    assert list(data.iter_records()) == []
    metrics = run_metrics(root)
    assert metrics["rq1"]["executions"] == 0
    assert metrics["rq2"]["valid"] == 0
    assert metrics["rq2"]["brier_reference"] is None
    assert _digest(root) == before

    absent = tmp_path / "absent"
    _write_json(absent / "config.json", {})
    before = _digest(absent)
    with pytest.raises(FileNotFoundError):
        RunData.open(absent)
    assert _digest(absent) == before
