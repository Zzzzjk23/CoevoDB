"""Per-run RQ1–RQ6 metrics: hand numbers, a short real loop, and a read-only directory."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from surprise.features import FeatureDef, default_registry
from surprise.harness.contracts import ExperimentRecord, SqlCase
from surprise.harness.ledger import Ledger
from surprise.metrics.boundary import classify, load_fix_conditions
from surprise.metrics.constants import as_dict
from surprise.metrics.curve import surprise_curve
from surprise.metrics.dups import duplicate_rate, identity_key, new_families
from surprise.metrics.partition import pair_agreement
from surprise.metrics.recall import score
from surprise.metrics.rq import label_key, ledger_families, old_metrics, run_metrics, theory_lengths
from surprise.metrics.rq import ciao
from surprise.metrics.rundata import RunData
from surprise.theory.length import theory_length
from surprise.theory.workbench import Workbench
from surprise.gates.s06 import fail_label, invalid_label, pass_label
from surprise.gates.s11_cases import (
    F2_FIX,
    PARTITION_EXPECTED,
    PARTITION_NONE_EXPECTED,
    PARTITION_NONE_PRED,
    PARTITION_PRED,
    PARTITION_TRUTH,
)
from test_surprise_s06_common import PLAIN, TOP, X1, hypothesis, phi

F2_SPECIFIC = (
    "ast:window_spec:partition",
    "ast:window_trait:dup_partition_key",
    "ast:window_trait:multiple",
)
_WHEN = "2020-01-01T00:00:00+00:00"


def _digest(root: Path) -> dict[str, str]:
    found = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            found[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def _case(engine: str = "duckdb") -> SqlCase:
    return SqlCase(engine=engine, setup=(), query="SELECT 1")


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
        case=_case(engine),
        label=label,
        purpose=purpose,
        created_at=_WHEN,
        spec=spec,
        phi=phi_dict,
        p_t=p_t,
    )


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _ledger(root: Path, records: list[ExperimentRecord], *, run_id: str = "run-1", manifest: dict | None = None) -> None:
    ledger = Ledger(root / "ledger.sqlite")
    try:
        ledger.start_run(run_id, {} if manifest is None else manifest)
        for record in records:
            ledger.append(record)
    finally:
        ledger.close()


def _run(
    root: Path,
    records: list[ExperimentRecord],
    *,
    config: dict | None = None,
    report: dict | None = None,
    progress: list[dict] | None = None,
    manifest: dict | None = None,
    run_id: str = "run-1",
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    body = {"seed": 1, "engines": ["duckdb"], "oracles": ["plan_variant"]} if config is None else config
    _write_json(root / "config.json", body)
    if report is not None:
        _write_json(root / "report.json", report)
    if progress:
        _write_jsonl(root / "progress.jsonl", progress)
    _ledger(root, records, run_id=run_id, manifest=manifest)
    return root


def _marker_registry(path: Path):
    registry = default_registry()
    registry.register(
        FeatureDef(
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
    )
    registry.accept("ast:expr:gate_marker", {"by": "test"})
    registry.save(path)
    return registry


def test_constants_keep_python_types() -> None:
    got = as_dict()
    assert set(got) == {
        "HIGH_SURPRISE_BITS",
        "CALIBRATION_EDGES",
        "CIAO_MAX_GENERATIONS",
        "CIAO_BATCH_SAMPLE",
        "CURVE_WINDOW",
        "TEETH_AMPLITUDE",
        "TEETH_WIDTH",
    }
    assert got["HIGH_SURPRISE_BITS"] == 4.0 and type(got["HIGH_SURPRISE_BITS"]) is float
    assert got["CALIBRATION_EDGES"] == (0.0, 0.05, 0.2, 0.4, 0.6, 0.8, 0.95, 1.0)
    assert type(got["CALIBRATION_EDGES"]) is tuple
    assert got["CIAO_MAX_GENERATIONS"] == 12 and type(got["CIAO_MAX_GENERATIONS"]) is int
    assert got["CIAO_BATCH_SAMPLE"] == 200 and type(got["CIAO_BATCH_SAMPLE"]) is int
    assert got["CURVE_WINDOW"] == 100 and type(got["CURVE_WINDOW"]) is int
    assert got["TEETH_AMPLITUDE"] == 0.25 and type(got["TEETH_AMPLITUDE"]) is float
    assert got["TEETH_WIDTH"] == 5 and type(got["TEETH_WIDTH"]) is int
    got["CURVE_WINDOW"] = 1
    assert as_dict()["CURVE_WINDOW"] == 100


def test_label_key_and_ledger_families() -> None:
    profiled = _record("run-1", 1, fail_label("f1"))
    assert label_key(profiled) == "fix|duckdb|deliminator,filter_pushdown"
    assert label_key(profiled) == identity_key(
        "duckdb",
        ["deliminator", "filter_pushdown"],
        profiled.label.fail_kind,
        profiled.label.identity.error_class,
        profiled.label.cve["profile"]["behavior_shape"],
    )
    assert label_key(_record("run-1", 1, fail_label("f1_raw"))) is None
    assert label_key(_record("run-1", 1, pass_label())) is None
    shaped = _record("run-1", 1, fail_label("df_missing"))
    assert label_key(shaped) is not None and label_key(shaped).startswith("shape|duckdb|")

    later = _record("run-1", 3, fail_label("df_missing"))
    again = _record("run-1", 2, fail_label("f1"))
    missing = _record("run-1", 4, pass_label())
    families = ledger_families(
        [later, again, profiled, missing],
        [
            {"record_id": "run-1:1", "elapsed_s": 1.0},
            {"record_id": "run-1:1", "elapsed_s": 4.5},
            {"record_id": "run-1:3"},
        ],
    )
    assert [row["seq"] for row in families] == [1, 3]
    assert families[0]["elapsed_s"] == 4.5
    assert families[1]["elapsed_s"] is None
    assert families[0]["key"] == "fix|duckdb|deliminator,filter_pushdown"
    assert ledger_families([profiled])[0]["elapsed_s"] is None


def test_brier_calibration_edges_and_high_surprise(tmp_path: Path) -> None:
    # p = 0 and p = 1 stay in the bins. surprise_bits rejects them, so they are not high-surprise.
    specs = [
        (1, 0.0, pass_label(), None),
        (2, 0.05, fail_label("f1"), "new_family"),
        (3, 0.5, pass_label(), None),
        (4, 0.9, pass_label(), None),
        (5, 0.95, fail_label("f1"), "old"),
        (6, 1.0, fail_label("f1"), None),
        (7, 0.95, pass_label(), "other"),
    ]
    records = [
        _record("run-1", seq, label, p_t=p_t) for seq, p_t, label, _triage in specs
    ]
    records.append(_record("run-1", 8, invalid_label("query_error"), p_t=0.01))
    records.append(_record("run-1", 9, invalid_label("timeout", "tlp")))
    progress = []
    for seq, _p, _label, triage in specs:
        if triage is not None:
            progress.append({"record_id": f"run-1:{seq}", "elapsed_s": float(seq), "triage": triage})
    progress.insert(0, {"record_id": "run-1:2", "elapsed_s": 0.25, "triage": "old"})
    root = _run(
        tmp_path / "cal",
        records,
        report={"status": "budget_experiments", "wall_s": 3600.0},
        progress=progress,
    )
    before = _digest(root)
    prices = {"deepseek-flash": {"input": 0.1, "output": 0.2}}
    known = {"engines": {}, "items": []}
    metrics = run_metrics(root, known=known, prices=prices)
    again = run_metrics(root, known=known, prices=prices)
    assert metrics == again
    assert _digest(root) == before

    rq2 = metrics["rq2"]
    assert rq2["valid"] == 7
    outcomes = [0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0]
    probs = [0.0, 0.05, 0.5, 0.9, 0.95, 1.0, 0.95]
    assert rq2["brier"] == pytest.approx(sum((p - y) ** 2 for p, y in zip(probs, outcomes)) / 7)
    rate = 3 / 7
    assert rq2["brier_reference"] == pytest.approx(rate * (1.0 - rate))
    # p of 0 or 1, and invalid rows, have no surprise. The rest are -log2 of the outcome probability.
    scored = [-math.log2(0.05), -math.log2(0.5), -math.log2(0.1), -math.log2(0.95), -math.log2(0.05)]
    assert rq2["mean_surprise"] == pytest.approx(sum(scored) / len(scored))
    bins = {(row["lo"], row["hi"]): row for row in rq2["calibration"]}
    assert len(rq2["calibration"]) == 7
    assert bins[(0.0, 0.05)]["count"] == 1 and bins[(0.0, 0.05)]["fail_rate"] == 0.0
    assert bins[(0.05, 0.2)]["count"] == 1 and bins[(0.05, 0.2)]["mean_p"] == pytest.approx(0.05)
    assert bins[(0.8, 0.95)]["count"] == 1 and bins[(0.8, 0.95)]["mean_p"] == pytest.approx(0.9)
    last = bins[(0.95, 1.0)]
    assert last["count"] == 3
    assert last["mean_p"] == pytest.approx((0.95 + 1.0 + 0.95) / 3)
    assert last["fail_rate"] == pytest.approx(2 / 3)
    assert bins[(0.2, 0.4)] == {"lo": 0.2, "hi": 0.4, "count": 0, "mean_p": None, "fail_rate": None}
    high = rq2["high_surprise"]
    assert high == {"threshold": 4.0, "count": 2, "new_family": 1, "share": 0.5}
    assert rq2["window"] == 100 and rq2["curve"] == [] and rq2["teeth"] == []

    rq1 = metrics["rq1"]
    assert rq1["executions"] == 9 and rq1["family_count"] == 1
    assert rq1["families_per_1000"] == pytest.approx(1000 / 9)
    assert rq1["families_per_hour"] == pytest.approx(1.0)
    assert rq1["first_family"] == {"seq": 2, "elapsed_s": 2.0}
    assert rq1["families"][0]["elapsed_s"] == 2.0
    assert metrics["rq4"]["invalid"]["count"] == 2
    assert metrics["rq4"]["invalid"]["by_reason"] == {"query_error": 1, "timeout": 1}
    assert metrics["rq4"]["invalid"]["by_oracle"] == {"cross_dbms": 1, "tlp": 1}
    assert metrics["rq6"]["recall"] is None and metrics["rq6"]["boundary"] is None
    assert metrics["cost"]["usd"] == 0.0
    assert metrics["rq3"]["calls"]["total"] == 0
    assert metrics["rq3"]["calls_per_family"] == 0.0
    assert metrics["rq3"]["conjectures"]["survival_rate"] is None
    assert metrics["rq3"]["predictions"]["accuracy"] is None
    assert metrics["rq3"]["pure_llm"] is None


def test_theory_lengths_and_ciao_generations(tmp_path: Path) -> None:
    fresh = Workbench.create(tmp_path / "fresh")
    lengths = theory_lengths(fresh)
    assert lengths == [{"generation": 0, "length": 0.0, "hypotheses": 0, "live": True}]
    assert ciao(fresh) is None

    wb = Workbench.create(tmp_path / "ciao")
    ids: dict[int, list[str]] = {0: [], 1: [], 2: []}
    for generation in range(3):
        for index in range(100):
            record_id = f"g{generation}-{index:03d}"
            ids[generation].append(record_id)
            label = invalid_label() if generation == 1 else pass_label()
            wb.observe(phi(PLAIN), label, record_id)
        wb.checkpoint(f"close-{generation}")
    lengths = theory_lengths(wb)
    assert [row["generation"] for row in lengths] == [0, 1, 2, 3]
    assert lengths[-1]["live"] is True and lengths[-1]["length"] == theory_length(wb.theory)
    for generation in range(3):
        closed = wb.store.load_generation(generation)
        assert lengths[generation]["live"] is False
        assert lengths[generation]["length"] == theory_length(closed)
        assert lengths[generation]["hypotheses"] == len(closed.hypotheses)

    matrix = ciao(wb)
    assert matrix is not None
    assert matrix["generations"] == [0, 1, 2, 3] and matrix["batches"] == [0, 1, 2, 3]
    for row in matrix["matrix"]:
        assert row[1] is None and row[3] is None
    assert matrix["matrix"][0][0] == wb.surprise_under(0, ids[0])
    assert matrix["matrix"][2][0] == wb.surprise_under(2, ids[0])
    picked = ciao(wb, max_generations=3)
    assert picked is not None and picked["generations"] == [0, 2, 3]
    assert picked["matrix"][0][2] is None
    present = [picked["matrix"][i][i] for i in range(3) if picked["matrix"][i][i] is not None]
    assert picked["diagonal_mean"] == pytest.approx(sum(present) / len(present))


def test_ciao_samples_evenly(tmp_path: Path) -> None:
    wb = Workbench.create(tmp_path / "sample")
    ids = []
    for index in range(10):
        record_id = f"s{index}"
        ids.append(record_id)
        features = X1 if index in (0, 3, 6, 9) else PLAIN
        wb.observe(phi(features), pass_label(), record_id)
    wb.theory.put(hypothesis())
    sampled = [ids[index] for index in (0, 3, 6, 9)]
    assert wb.surprise_under(0, sampled) != wb.surprise_under(0, ids)
    matrix = ciao(wb, sample=4)
    assert matrix is not None
    assert matrix["generations"] == [0]
    assert matrix["matrix"][0][0] == wb.surprise_under(0, sampled)
    assert matrix["diagonal_mean"] == matrix["matrix"][0][0]
    assert matrix["below_mean"] is None and matrix["above_mean"] is None


def test_rq3_from_handwritten_books(tmp_path: Path) -> None:
    vocab = tmp_path / "vocabulary.json"
    _marker_registry(vocab)
    records = [
        _record(
            "run-1",
            1,
            fail_label("f1"),
            phi_dict={"features": ["ast:expr:gate_marker"]},
        ),
        _record("run-1", 2, pass_label()),
    ]
    root = _run(
        tmp_path / "llm",
        records,
        config={
            "seed": 4,
            "engines": ["duckdb"],
            "oracles": ["plan_variant"],
            "vocabulary": str(vocab),
            "llm": {"roles": ["conjecturer", "translator"]},
        },
        report={"status": "budget_experiments", "wall_s": 10.0},
        progress=[{"record_id": "run-1:1", "lane": "implement", "rule": "llm:new-oracle", "triage": "new_family"}],
    )
    _write_jsonl(
        root / "llm" / "conjectures.jsonl",
        [
            {"type": "conjecture", "status": "registered", "conjecture_id": "c1", "predictions": [{}, {}]},
            {"type": "conjecture", "status": "registered", "conjecture_id": "c2", "predictions": [{}]},
            {"type": "conjecture", "status": "rejected", "conjecture_id": "c3", "predictions": [{}, {}, {}]},
            {"type": "settle", "conjecture_id": "c1", "state": "broken", "record_id": "run-1:1"},
            {"type": "settle", "conjecture_id": "c2", "state": "kept", "record_id": "run-1:2"},
            {"type": "settle", "conjecture_id": "c1", "state": "kept", "record_id": "run-1:2"},
        ],
    )
    _write_jsonl(
        root / "llm" / "translations.jsonl",
        [
            {"type": "translation", "translation_id": "t1"},
            {"type": "settle", "translation_id": "t1", "state": "kept", "record_id": "run-1:1"},
            {"type": "settle", "translation_id": "t2", "state": "void", "record_id": "run-1:2"},
        ],
    )
    _write_jsonl(
        root / "llm" / "calls.jsonl",
        [
            {"role": "conjecturer", "model": "deepseek-flash", "source": "cache", "input_tokens": 100, "output_tokens": 20},
            {"role": "translator", "model": "deepseek-flash", "source": "network", "input_tokens": 50, "output_tokens": 10},
        ],
    )
    prices = {"deepseek-flash": {"input": 0.1, "output": 0.2}}
    metrics = run_metrics(root, prices=prices)
    conjectures = metrics["rq3"]["conjectures"]
    assert conjectures["registered"] == 2 and conjectures["rejected"] == 1
    assert conjectures["with_settled"] == 2 and conjectures["survived"] == 1
    assert conjectures["survival_rate"] == pytest.approx(0.5)
    predictions = metrics["rq3"]["predictions"]
    assert predictions["total"] == 3 and predictions["kept"] == 2 and predictions["broken"] == 1
    assert predictions["void"] == 0 and predictions["open"] == 0
    assert predictions["accuracy"] == pytest.approx(2 / 3)
    translations = metrics["rq3"]["translations"]
    assert translations == {"total": 2, "kept": 1, "broken": 0, "accuracy": 1.0}
    timeline = metrics["rq3"]["timeline"]
    assert [(row["seq"], row["source"], row["kept"]) for row in timeline] == [
        (1, "conjecture", False),
        (1, "translation", True),
        (2, "conjecture", True),
        (2, "conjecture", True),
    ]
    assert [row["accuracy"] for row in timeline] == pytest.approx([0.0, 0.5, 2 / 3, 0.75])
    assert metrics["rq3"]["families_via"] == {
        "implement": 1,
        "bet": 0,
        "translate": 0,
        "llm_rule": 1,
        "invented_feature": 1,
    }
    calls = metrics["rq3"]["calls"]
    assert list(calls["by_role"]) == ["conjecturer", "translator"]
    assert calls["by_role"]["conjecturer"] == {"calls": 1, "network": 0, "input_tokens": 100, "output_tokens": 20}
    assert calls["by_role"]["translator"]["network"] == 1
    assert calls["total"] == 2 and calls["network"] == 1
    assert calls["input_tokens"] == 150 and calls["output_tokens"] == 30
    assert metrics["rq3"]["calls_per_family"] == pytest.approx(2.0)
    assert metrics["rq3"]["tokens_per_family"] == pytest.approx(180.0)
    assert metrics["run"]["llm_roles"] == ["conjecturer", "translator"]
    assert metrics["cost"]["llm_calls"] == 2
    assert metrics["cost"]["usd"] == pytest.approx(0.000021)
    assert metrics["cost"]["per_family"]["usd"] == pytest.approx(0.000021)
    with pytest.raises(ValueError):
        run_metrics(root, prices={})


def test_classify_and_fix_conditions(tmp_path: Path) -> None:
    assert classify(set(), set()) == "match"
    assert classify(set(), {"a"}) == "too_wide"
    assert classify({"a", "b"}, {"a", "b"}) == "match"
    assert classify({"a"}, {"a", "b"}) == "too_wide"
    assert classify({"a", "b", "c"}, {"a", "b"}) == "too_narrow"
    assert classify({"a", "c"}, {"a", "b"}) == "mixed"
    entries = load_fix_conditions()
    assert len(entries) == 1
    entry = entries[0]
    assert entry["name"] == "F2" and entry["engine"] == "duckdb"
    assert entry["key"] == F2_FIX["key"] and entry["fix"] == F2_FIX["fix"]
    assert tuple(sorted(entry["conditions"])) == F2_FIX["conditions"]
    assert entry["evidence"]
    entry["conditions"].append("extra")
    assert "extra" not in load_fix_conditions()[0]["conditions"]

    def _broken(**overrides) -> None:
        payload = {
            "schema": 1,
            "entries": [{
                "name": "F2",
                "engine": "duckdb",
                "key": F2_FIX["key"],
                "fix": F2_FIX["fix"],
                "evidence": "because",
                "conditions": list(F2_SPECIFIC),
            }],
        }
        payload.update({key: value for key, value in overrides.items() if key in ("schema", "entries")})
        if "schema" not in overrides and "entries" not in overrides:
            payload["entries"][0].update(overrides)
        path = tmp_path / "broken.json"
        _write_json(path, payload)
        with pytest.raises(ValueError):
            load_fix_conditions(path)

    _broken(conditions=["ast:not_a_feature"])
    _broken(conditions=[])
    _broken(evidence="")
    row = {
        "name": "F2",
        "engine": "duckdb",
        "key": F2_FIX["key"],
        "fix": F2_FIX["fix"],
        "conditions": list(F2_SPECIFIC),
    }
    _write_json(tmp_path / "missing.json", {"schema": 1, "entries": [row]})
    with pytest.raises(ValueError):
        load_fix_conditions(tmp_path / "missing.json")
    _write_json(tmp_path / "schema.json", {"schema": True, "entries": []})
    with pytest.raises(ValueError):
        load_fix_conditions(tmp_path / "schema.json")


def test_pair_agreement_matches_the_hand_examples() -> None:
    got = pair_agreement(PARTITION_PRED, PARTITION_TRUTH)
    assert got["items"] == 4 and got["tp"] == 1 and got["fp"] == 2 and got["fn"] == 1 and got["tn"] == 2
    for name, value in PARTITION_EXPECTED.items():
        assert got[name] == pytest.approx(value)
    none = pair_agreement(PARTITION_NONE_PRED, PARTITION_TRUTH)
    assert none["items"] == 4 and none["tp"] == 1 and none["fp"] == 0 and none["fn"] == 1 and none["tn"] == 4
    for name, value in PARTITION_NONE_EXPECTED.items():
        assert none[name] == pytest.approx(value)
    assert none["ari"] == pytest.approx(4 / 7)
    both = pair_agreement({"a": 1, "b": 1}, {"a": "x", "b": "x", "ignored": 9})
    assert both["tp"] == 1 and both["fp"] == 0 and both["fn"] == 0 and both["tn"] == 0
    assert both["precision"] == 1.0 and both["recall"] == 1.0 and both["f1"] == 1.0
    assert both["ari"] is None and both["items"] == 2
    single = pair_agreement({"a": 1}, {"a": 1})
    assert single["tp"] == single["fp"] == single["fn"] == single["tn"] == 0
    assert single["precision"] is None and single["recall"] is None and single["f1"] is None
    assert single["ari"] is None


def test_old_metrics_from_bug_reports(tmp_path: Path) -> None:
    root = tmp_path / "old"
    inner = root / "inner"
    inner.mkdir(parents=True)
    _write_json(
        root / "old_run.json",
        {
            "mode": "hunt",
            "seed": 7,
            "wall_s": 1800.0,
            "ended": "killed",
            "run_dir": "inner",
        },
    )
    _write_jsonl(
        inner / "bugs.jsonl",
        [
            {"root_key": "same", "candidate": {"kind": "bug"}, "signature": None},
            {"root_key": "same", "candidate": {"kind": "bug"}, "signature": None},
            {
                "root_key": "other",
                "candidate": {"kind": "bug"},
                "signature": {"engine": "duckdb", "fix_kind": "single", "fix_set": ["window_self_join"]},
            },
        ],
    )
    metrics = old_metrics(root)
    assert metrics["run"] == {
        "run_id": None,
        "kind": "old_coevodb",
        "seed": 7,
        "mode": "hunt",
        "engines": None,
        "oracles": None,
        "status": "killed",
        "experiments": None,
        "wall_s": 1800.0,
        "arm": None,
        "llm_roles": None,
    }
    families = metrics["rq1"]["families"]
    assert [row["seq"] for row in families] == [1, 3]
    assert families[0]["key"] == "sigma|same" and families[0]["record_id"] == "same"
    assert families[1]["key"] == "fix|duckdb|window_self_join"
    assert metrics["rq1"]["family_count"] == 2
    assert metrics["rq1"]["executions"] is None and metrics["rq1"]["families_per_1000"] is None
    assert metrics["rq1"]["families_per_hour"] == pytest.approx(4.0)
    assert metrics["rq1"]["theory_families"] is None
    assert metrics["rq1"]["duplicate_rate"] == pytest.approx(1 / 3)
    assert metrics["rq2"] is None and metrics["rq3"] is None and metrics["rq4"] is None
    assert metrics["rq5"] is None and metrics["rq6"] is None
    assert metrics["cost"]["wall_s"] == 1800.0 and metrics["cost"]["per_family"] is None
    assert metrics["cost"]["llm_calls"] is None and metrics["cost"]["usd"] is None


def test_old_metrics_without_bugs_file_is_zero_reports(tmp_path: Path) -> None:
    root = tmp_path / "old"
    inner = root / "inner"
    inner.mkdir(parents=True)
    _write_json(
        root / "old_run.json",
        {
            "mode": "no_llm",
            "seed": 1,
            "wall_s": 3600.0,
            "ended": "killed",
            "run_dir": "inner",
        },
    )
    metrics = old_metrics(root)
    assert not (inner / "bugs.jsonl").exists()
    assert metrics["rq1"]["family_count"] == 0
    assert metrics["rq1"]["families_per_hour"] == 0.0
    assert metrics["rq1"]["duplicate_rate"] is None


def test_frozen_theory_uses_ledger_keys(tmp_path: Path) -> None:
    records = [_record("run-1", 1, fail_label("f1")), _record("run-1", 2, fail_label("f1"))]
    frozen = _run(
        tmp_path / "frozen",
        records,
        config={"seed": 1, "engines": ["duckdb"], "arm": {"freeze": "theory"}},
        report={"status": "budget_experiments", "wall_s": 10.0},
    )
    Workbench.create(frozen / "theory")
    frozen_metrics = run_metrics(frozen)
    assert frozen_metrics["rq1"]["theory_families"] is None
    assert frozen_metrics["rq1"]["duplicate_rate"] == pytest.approx(0.5)
    assert frozen_metrics["rq4"]["theory_length"][-1]["live"] is True
    assert frozen_metrics["rq5"]["arm"] == {"freeze": "theory"}

    plain = _run(tmp_path / "plain", records, report={"status": "budget_experiments", "wall_s": 10.0})
    Workbench.create(plain / "theory")
    plain_metrics = run_metrics(plain)
    assert plain_metrics["rq1"]["theory_families"] == []
    assert plain_metrics["rq1"]["duplicate_rate"] is None
    assert plain_metrics["rq4"]["duplicate_rate"] is None


def test_boundary_recall_and_one_theory_family(tmp_path: Path) -> None:
    root = _run(
        tmp_path / "f2",
        [_record("run-1", 1, pass_label("plan_variant"), p_t=0.2)],
        report={"status": "budget_experiments", "wall_s": 1.0},
    )
    wb = Workbench.create(root / "theory")
    wb.theory.put(
        hypothesis(
            hypothesis_id="h-f2",
            engine="duckdb",
            oracle="plan_variant",
            interventions=("window_self_join",),
            specific=F2_SPECIFIC,
            general=TOP,
        )
    )
    wb.store.save(wb.theory)
    known = {
        "engines": {},
        "items": [
            {"name": "F2", "y": "fail", "key": "fix|duckdb|window_self_join"},
            {"name": "ghost", "y": "fail", "key": "fix|duckdb|not_a_fix"},
        ],
    }
    before = _digest(root)
    metrics = run_metrics(root, known=known)
    assert _digest(root) == before
    opened = Workbench.open(root / "theory")
    specific = set(opened.theory.hypotheses[0].specific)
    conditions = set(F2_SPECIFIC)
    rows = metrics["rq6"]["boundary"]
    assert len(rows) == 1 and rows[0]["name"] == "F2"
    assert rows[0]["classification"] == classify(specific, conditions) == "match"
    assert rows[0]["missing"] == sorted(conditions - specific)
    assert rows[0]["extra"] == sorted(specific - conditions)
    assert metrics["rq6"]["recall"] == score(known, root / "theory")
    assert metrics["rq6"]["recall"]["recall"] == pytest.approx(0.5)
    keys = [row["key"] for row in new_families(root / "theory")]
    assert metrics["rq1"]["theory_families"] == keys
    assert metrics["rq1"]["duplicate_rate"] == 0.0
    assert metrics["rq1"]["family_count"] == 0
    assert metrics["cost"]["per_family"] == {"executions": None, "llm_calls": None, "tokens": None, "usd": None}


def test_pure_llm_counts_its_own_expect(tmp_path: Path) -> None:
    records = [
        _record("run-1", 1, pass_label("plan_variant"), spec={"expect": "pass"}, purpose="pure_llm"),
        _record("run-1", 2, pass_label("plan_variant"), spec={"expect": "fail"}, purpose="pure_llm"),
        _record("run-1", 3, invalid_label("query_error", "plan_variant"), spec={"expect": "pass"}, purpose="pure_llm"),
        _record("run-1", 4, pass_label("plan_variant"), spec={"expect": "maybe"}, purpose="pure_llm"),
    ]
    root = _run(
        tmp_path / "pure",
        records,
        config={"seed": 3, "engine": "duckdb"},
        manifest={"baseline": "pure_llm"},
    )
    data = RunData.open(root)
    assert data.kind == "pure_llm" and data.records[0].spec["expect"] == "pass"
    metrics = run_metrics(root)
    assert metrics["run"]["kind"] == "pure_llm" and metrics["run"]["engines"] == ["duckdb"]
    assert metrics["rq2"]["brier"] is None and metrics["rq2"]["valid"] == 0
    assert metrics["rq2"]["mean_surprise"] is None
    assert metrics["rq3"]["pure_llm"] == {"total": 4, "kept": 1, "broken": 2, "accuracy": pytest.approx(1 / 3)}


def test_extended_vocabulary_opens(tmp_path: Path) -> None:
    vocab = tmp_path / "vocabulary.json"
    registry = _marker_registry(vocab)
    root = _run(
        tmp_path / "vocab",
        [_record("run-1", 1, pass_label())],
        config={"seed": 1, "engines": ["datafusion"], "vocabulary": str(vocab)},
    )
    wb = Workbench.create(root / "theory", registry=registry)
    wb.theory.put(hypothesis(hypothesis_id="h-marker", specific=("ast:expr:gate_marker",), general=TOP))
    wb.store.save(wb.theory)
    data = RunData.open(root)
    assert data.registry.digest() == registry.digest()
    assert data.workbench() is not None
    metrics = run_metrics(root)
    assert metrics["rq1"]["family_count"] == 0
    assert metrics["rq1"]["theory_families"] == ["shape|datafusion|wrong_result|-|missing_only"]


def test_missing_ledger_is_not_created(tmp_path: Path) -> None:
    root = tmp_path / "none"
    root.mkdir()
    _write_json(root / "config.json", {"seed": 1})
    with pytest.raises(FileNotFoundError):
        RunData.open(root)
    assert not (root / "ledger.sqlite").exists()

    twin = tmp_path / "twin"
    twin.mkdir()
    _write_json(twin / "config.json", {"seed": 1})
    ledger = Ledger(twin / "ledger.sqlite")
    try:
        ledger.start_run("a", {})
        ledger.start_run("b", {})
    finally:
        ledger.close()
    with pytest.raises(ValueError):
        RunData.open(twin)


def test_real_loop_is_read_only_and_matches_the_ledger(tmp_path: Path) -> None:
    from surprise.experiments.loop import run
    from surprise.gates.s04 import load

    out = tmp_path / "real"
    run(
        out,
        seed=1,
        engines=("duckdb",),
        oracles=("plan_variant",),
        max_experiments=0,
        bootstrap=[{"case": load("F1").to_dict(), "oracle": "plan_variant", "rule": None}],
    )
    before = _digest(out)
    first = run_metrics(out, window=5)
    second = run_metrics(out, window=5)
    assert first == second
    assert _digest(out) == before
    data = RunData.open(out)
    keys = [row["key"] for row in new_families(out / "theory")]
    assert first["rq1"]["theory_families"] == keys
    assert first["rq1"]["duplicate_rate"] == duplicate_rate(keys)
    wb = data.workbench()
    assert wb is not None
    tally = {"accepted": 0, "rejected": 0, "rolled_back": 0}
    paired = []
    for edit in wb.edits():
        if edit.decision in tally:
            tally[edit.decision] += 1
        if edit.decision == "accepted" and edit.surprise_delta_in is not None and edit.surprise_delta_out is not None:
            paired.append(edit)
    assert first["rq4"]["edits"] == tally
    if paired:
        mean_in = sum(edit.surprise_delta_in for edit in paired) / len(paired)
        mean_out = sum(edit.surprise_delta_out for edit in paired) / len(paired)
        assert first["rq4"]["in_out"]["edits"] == len(paired)
        assert first["rq4"]["in_out"]["gap"] == pytest.approx(mean_out - mean_in)
    else:
        assert first["rq4"]["in_out"] == {"edits": 0, "mean_in": None, "mean_out": None, "gap": None}
    assert first["rq2"]["curve"] == surprise_curve(data.records, window=5)
    assert first["rq6"]["recall"] is None
    assert isinstance(first["rq6"]["boundary"], list)
