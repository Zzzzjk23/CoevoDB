"""Ablation switches: frozen theory, frozen Diagnoser, random Hunter, cross-run pairing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from surprise.diagnoser import Diagnoser
from surprise.diagnoser.constants import CHECKPOINT_EVERY, COMPRESS_EVERY
from surprise.experiments.loop import UsageError, _PROGRESS_KEYS, main, run
from surprise.features import Phi
from surprise.features.registry import default_registry
from surprise.features.vocabulary import FeatureDef
from surprise.gates import s10_cases as C10
from surprise.gates.s04 import load
from surprise.gates.s06 import fail_label, phi
from surprise.harness.ledger import Ledger
from surprise.theory import Workbench
from surprise.theory.predict import surprise_bits

_ORACLES = ("plan_variant", "tlp", "norec")


def _f1() -> list[dict]:
    return [{"case": load("F1").to_dict(), "oracle": "plan_variant", "rule": None}]


def _rows(path: Path) -> list[dict]:
    found = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        row.pop("elapsed_s", None)
        found.append(row)
    return found


def _config(path: Path) -> dict:
    return json.loads((path / "config.json").read_text(encoding="utf-8"))


def _report(path: Path) -> dict:
    return json.loads((path / "report.json").read_text(encoding="utf-8"))


def _manifest(path: Path, run_id: str) -> dict:
    ledger = Ledger(path / "ledger.sqlite")
    try:
        return ledger.run_manifest(run_id)
    finally:
        ledger.close()


def _records(path: Path):
    ledger = Ledger(path / "ledger.sqlite")
    try:
        return ledger.records()
    finally:
        ledger.close()


def _go(out: Path, **kwargs):
    options = {
        "seed": 61,
        "engines": ("duckdb",),
        "oracles": _ORACLES,
        "max_experiments": 4,
    }
    options.update(kwargs)
    return run(out, **options)


def test_create_installs_a_theory_without_its_log(tmp_path: Path) -> None:
    source = Workbench.create(tmp_path / "source")
    outcome = source.observe(phi("x1"), fail_label("df_missing"), "r1")
    assert outcome.observation.opened
    version = source.theory.version
    copied = Workbench.create(tmp_path / "copy", theory=source.theory)
    assert copied.theory.version == version
    assert copied.theory.to_dict() == source.theory.to_dict()
    assert copied.records() == ()
    assert copied.edits() == ()
    assert copied.generation == 0
    assert (tmp_path / "copy" / "journal.jsonl").read_text(encoding="utf-8") == ""
    assert (tmp_path / "copy" / "edits.jsonl").read_text(encoding="utf-8") == ""
    reopened = Workbench.open(tmp_path / "copy")
    assert reopened.theory.version == version
    assert reopened.records() == ()
    plain = Workbench.create(tmp_path / "plain")
    assert plain.theory.version == Workbench.create(tmp_path / "plain2").theory.version


def test_checkpoint_only_does_not_compress(tmp_path: Path) -> None:
    bench = Workbench.create(tmp_path / "theory")
    diag = Diagnoser(phi=lambda _case: None, registry=default_registry())
    compressed: list[int] = []
    notes: list[str] = []
    real_checkpoint = bench.checkpoint

    def compress():
        compressed.append(1)
        return ()

    def checkpoint(note: str) -> int:
        notes.append(note)
        return real_checkpoint(note)

    bench.compress = compress
    bench.checkpoint = checkpoint
    assert diag.checkpoint_only(bench, CHECKPOINT_EVERY - 1) == ()
    assert compressed == [] and notes == [] and bench.generation == 0
    assert diag.checkpoint_only(bench, CHECKPOINT_EVERY) == ()
    assert compressed == []
    assert notes == [f"after {CHECKPOINT_EVERY} experiments"]
    assert bench.generation == 1
    assert diag.periodic(bench, COMPRESS_EVERY) == ()
    assert compressed == [1]
    assert notes[-1] == f"after {COMPRESS_EVERY} experiments"
    assert bench.generation == 2


def test_usage_errors_refuse_bad_switches(tmp_path: Path) -> None:
    base = tmp_path / "base"
    Workbench.create(base / "theory")
    cases = (
        {"freeze": "everything"},
        {"hunter": "greedy"},
        {"theory_from": "nowhere@x"},
        {"select_from": "no-at-sign"},
        {"theory_from": f"{base}@3"},
        {"theory_from": f"{base}@head@extra"},
        {
            "freeze": "diagnoser",
            "llm": {"roles": ["conjecturer"], "cache": str(tmp_path / "c"), "max_calls": 1},
        },
        {
            "freeze": "theory",
            "llm": {"roles": ["implementer", "vocab_inventor"], "cache": str(tmp_path / "c2"), "max_calls": 0},
        },
    )
    for kwargs in cases:
        with pytest.raises(UsageError):
            _go(tmp_path / "bad", max_experiments=1, oracles=("tlp",), **kwargs)
        assert not (tmp_path / "bad").exists()


def test_cli_bad_switches_exit_two(tmp_path: Path) -> None:
    out = tmp_path / "out"
    common = ["--out", str(out), "--seed", "1", "--max-experiments", "1", "--engine", "duckdb", "--oracle", "tlp"]
    assert main([*common, "--freeze", "nope"]) == 2
    assert main([*common, "--hunter", "greedy"]) == 2
    assert main([*common, "--theory-from", "nowhere@x"]) == 2
    assert main([*common, "--select-from", "missing@head"]) == 2
    assert not out.exists()


def test_explicit_defaults_match_an_omitted_arm(tmp_path: Path) -> None:
    bare = tmp_path / "bare"
    explicit = tmp_path / "explicit"
    shared = {"seed": 3, "max_experiments": 2, "oracles": ("plan_variant", "tlp"), "run_id": "plain"}
    _go(bare, **shared)
    _go(
        explicit,
        freeze=None,
        hunter="value",
        theory_from=None,
        select_from=None,
        **shared,
    )
    assert _rows(bare / "progress.jsonl") == _rows(explicit / "progress.jsonl")
    assert _config(bare) == _config(explicit)
    assert "arm" not in _config(bare)
    assert "arm" not in _report(bare)
    assert "arm" not in _manifest(bare, "plain")["hunter"]
    raw = json.loads((bare / "progress.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert tuple(raw) == _PROGRESS_KEYS
    assert "select_p" not in raw


def test_random_hunter_is_deterministic_and_recorded(tmp_path: Path) -> None:
    shared = {"seed": 5, "max_experiments": 4, "oracles": ("plan_variant", "tlp"), "run_id": "rand"}
    value = tmp_path / "value"
    first = tmp_path / "first"
    second = tmp_path / "second"
    _go(value, **shared)
    _go(first, hunter="random", **shared)
    _go(second, hunter="random", **shared)
    assert _rows(first / "progress.jsonl") == _rows(second / "progress.jsonl")
    assert [row["case_digest"] for row in _rows(first / "progress.jsonl")] != [
        row["case_digest"] for row in _rows(value / "progress.jsonl")
    ]
    arm = {
        "freeze": None,
        "hunter": "random",
        "theory_from": None,
        "select_from": None,
    }
    assert _config(first)["arm"] == arm
    assert _report(first)["arm"] == arm
    assert _manifest(first, "rand")["hunter"]["arm"] == arm
    chosen = [row for row in _rows(first / "progress.jsonl") if row["lane"] != "bootstrap"]
    assert chosen
    assert all(isinstance(row["value"], float) and isinstance(row["D"], float) for row in chosen)


def test_frozen_theory_does_not_learn(tmp_path: Path) -> None:
    out = tmp_path / "frozen"
    _go(out, freeze="theory", max_experiments=2, bootstrap=_f1(), run_id="frozen")
    empty = Workbench.create(tmp_path / "empty")
    head = Workbench.open(out / "theory")
    assert head.theory.version == empty.theory.version
    assert not head.theory.hypotheses
    assert head.records() == ()
    assert head.edits() == ()
    rows = _rows(out / "progress.jsonl")
    assert rows
    for row in rows:
        assert row["triage"] is None and row["opened"] is None and row["owner"] is None
        assert row["rolled_back"] == [] and row["edits"] == [] and row["bets"] == []
        assert row["theory_version"] == empty.theory.version
        assert row["surprise"] == surprise_bits(row["p_fail_valid"], row["y"])
    records = _records(out)
    fails = [record for record in records if record.label.y == "fail"]
    assert fails
    assert all(record.label.cve.get("tier") == 3 for record in fails)
    assert all(record.theory_version == empty.theory.version for record in records)
    assert _config(out)["arm"]["freeze"] == "theory"
    assert _report(out)["arm"]["freeze"] == "theory"


def test_frozen_diagnoser_opens_families_without_edits(tmp_path: Path) -> None:
    out = tmp_path / "still"
    _go(out, freeze="diagnoser", max_experiments=1, bootstrap=_f1(), run_id="still")
    bench = Workbench.open(out / "theory")
    assert bench.families()
    assert bench.edits() == ()
    assert all(row["edits"] == [] for row in _rows(out / "progress.jsonl"))
    assert any(row["opened"] for row in _rows(out / "progress.jsonl"))
    assert _config(out)["arm"]["freeze"] == "diagnoser"


def test_theory_from_and_select_from(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _go(source, max_experiments=0, bootstrap=_f1(), run_id="src")
    source_wb = Workbench.open(source / "theory")
    version = source_wb.theory.version
    assert source_wb.theory.hypotheses
    assert source_wb.records()

    started = tmp_path / "started"
    _go(started, max_experiments=1, theory_from=f"{source}@head", run_id="child", oracles=("plan_variant", "tlp"))
    child_records = _records(started)
    assert child_records[0].theory_version == version
    journal = (started / "theory" / "journal.jsonl").read_text(encoding="utf-8")
    assert "src:" not in journal
    recorded = _config(started)["arm"]["theory_from"]
    assert recorded["generation"] == "head"
    assert recorded["version"] == version
    assert Path(recorded["run"]) == source.resolve()
    assert _report(started)["arm"]["theory_from"] == recorded
    assert _manifest(started, "child")["hunter"]["arm"]["theory_from"] == recorded

    source_wb.checkpoint("test")
    generation = tmp_path / "generation"
    _go(generation, max_experiments=1, theory_from=f"{source}@0", run_id="gen", oracles=("tlp",))
    assert _records(generation)[0].theory_version == version
    assert _config(generation)["arm"]["theory_from"]["generation"] == 0
    with pytest.raises(UsageError):
        _go(tmp_path / "open-gen", max_experiments=1, theory_from=f"{source}@1", oracles=("tlp",))
    assert not (tmp_path / "open-gen").exists()

    paired = tmp_path / "paired"
    _go(
        paired,
        max_experiments=6,
        select_from=f"{source}@head",
        freeze="theory",
        run_id="pair",
        oracles=("plan_variant", "tlp"),
    )
    fresh = Workbench.create(tmp_path / "fresh")
    records = _records(paired)
    for record in records:
        want = fresh.predict(Phi.from_dict(record.phi), record.label.oracle).p_fail_valid
        assert record.p_t == pytest.approx(want, abs=1e-12)
    rows = _rows(paired / "progress.jsonl")
    assert all("select_p" in row and isinstance(row["select_p"], float) for row in rows)
    assert any(abs(row["select_p"] - row["p_fail_valid"]) > 1e-12 for row in rows)
    assert {row["lane"] for row in rows} & {"refine", "generalize"}
    select_wb = Workbench.open(paired / "select_theory")
    assert select_wb.theory.version == version
    assert select_wb.records() == ()
    assert select_wb.edits() == ()
    assert (paired / "select_theory" / "journal.jsonl").read_text(encoding="utf-8") == ""
    head = Workbench.open(paired / "theory")
    assert head.theory.version == fresh.theory.version
    assert not head.theory.hypotheses
    select_ref = _config(paired)["arm"]["select_from"]
    assert select_ref["generation"] == "head" and select_ref["version"] == version
    assert Path(select_ref["run"]) == source.resolve()


def test_a_source_theory_in_another_vocabulary_is_refused(tmp_path: Path) -> None:
    base = tmp_path / "base"
    Workbench.create(base / "theory")
    other = default_registry()
    other.register(
        FeatureDef(
            feature_id=C10.VOCAB_GOOD["id"],
            kind="leaf",
            parent=C10.VOCAB_PARENT,
            layer="ast",
            description="gate",
            source="llm:gate",
            definition={"kind": "regex", "pattern": C10.VOCAB_GOOD["pattern"]},
            accepted=False,
            acceptance=None,
        )
    )
    other.accept(C10.VOCAB_GOOD["id"], {"gate": True})
    path = tmp_path / "other-vocab.json"
    other.save(path)
    with pytest.raises(UsageError):
        _go(
            tmp_path / "bad-vocab",
            max_experiments=1,
            oracles=("tlp",),
            theory_from=f"{base}@head",
            vocabulary=str(path),
        )
    assert not (tmp_path / "bad-vocab").exists()


def test_frozen_run_accepts_prior_without_a_call(tmp_path: Path) -> None:
    out = tmp_path / "roles"
    report = _go(
        out,
        seed=1,
        max_experiments=0,
        oracles=("tlp",),
        freeze="diagnoser",
        llm={
            "roles": ["implementer", "prior"],
            "cache": str(tmp_path / "cache"),
            "max_calls": 0,
            "network": False,
        },
    )
    assert report["status"] == "budget_experiments"
    assert report["experiments"] == 0
    assert _config(out)["arm"]["freeze"] == "diagnoser"
    assert _config(out)["llm"]["roles"] == ["implementer", "prior"]
