"""Diagnoser revisions and the Hunter loop without an LLM."""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from surprise.diagnoser import Diagnoser, constants
from surprise.diagnoser.constants import CHECKPOINT_EVERY, COMPRESS_EVERY
from surprise.features.registry import default_registry
from surprise.gates.s04 import load
from surprise.gates.s06 import fail_label, pass_label, phi
from surprise.gates.s08 import _normal, check_rows, code_digests as gate_digests, open_run
from surprise.harness.contracts import ORACLE_IDS, ExperimentRecord, SqlCase
from surprise.harness.ledger import Ledger
from surprise.metrics.curve import surprise_curve, teeth
from surprise.metrics.dups import new_families
from surprise.theory import Workbench, common_conjunction, reduce_conjunction
from surprise.theory.constants import BETA
from surprise.experiments.loop import UsageError, code_digests, main, run

FRAMEWORK = Path(__file__).resolve().parents[1]
_NULL_SCORE = ("hypothesis", "parent", "target", "value", "D", "U", "adjacent", "probes")
_REPORT_KEYS = {
    "run_id",
    "seed",
    "engines",
    "oracles",
    "beta",
    "status",
    "experiments",
    "choices",
    "started_at",
    "finished_at",
    "wall_s",
    "labels",
    "lanes",
    "triage",
    "hypotheses",
    "families",
    "edits",
    "curve",
    "teeth",
    "new_families",
    "extractor",
}


def _case() -> SqlCase:
    return SqlCase(engine="datafusion", setup=("CREATE TABLE t(a INT)",), query="SELECT a FROM t")


def _opened(directory: Path):
    bench = Workbench.create(directory / "theory")
    outcome = bench.observe(phi("x1"), fail_label("df_missing"), "r1")
    assert outcome.observation.opened
    return bench, outcome


def _minimize(label, case: SqlCase, *, status="ran", reproduced=True, body=None):
    cve = dict(label.cve)
    cve["minimize"] = {
        "status": status,
        "reason": None,
        "reproduced": reproduced,
        "case": case.to_dict() if body is None else body,
    }
    return dataclasses.replace(label, cve=cve)


def _record(label, case: SqlCase, record_id: str = "r1") -> ExperimentRecord:
    return ExperimentRecord(
        record_id=record_id,
        run_id="diag",
        seq=1,
        case=case,
        label=label,
        purpose="bootstrap",
        created_at="2020-01-01T00:00:00+00:00",
    )


def _diagnoser(fake):
    return Diagnoser(phi=fake, registry=default_registry())


def _f1_bootstrap(directory: Path) -> Path:
    item = {"case": load("F1").to_dict(), "oracle": "plan_variant", "rule": None}
    path = directory / "bootstrap.json"
    path.write_text(json.dumps([item]), encoding="utf-8")
    return path


def test_constants_match_the_plan_and_round_trip() -> None:
    have = constants.as_dict()
    assert have == {"COMPRESS_EVERY": 100, "CHECKPOINT_EVERY": 100}
    assert type(have["COMPRESS_EVERY"]) is int
    assert type(have["CHECKPOINT_EVERY"]) is int
    detached = constants.as_dict()
    detached["COMPRESS_EVERY"] = 0
    assert constants.as_dict()["COMPRESS_EVERY"] == 100


def test_after_accepts_a_tighter_s(tmp_path: Path) -> None:
    bench, outcome = _opened(tmp_path)
    case = _case()
    before = bench.theory.get(outcome.observation.opened)
    registry = default_registry()
    expected = common_conjunction(before.specific, reduce_conjunction(phi("x7").features, registry), registry)
    assert expected and expected != reduce_conjunction(before.specific, registry)
    seen: list[SqlCase] = []

    def fake(case_in: SqlCase):
        seen.append(case_in)
        return phi("x7")

    edits = _diagnoser(fake).after(bench, _record(_minimize(fail_label("df_missing"), case), case), outcome)
    assert len(edits) == 1
    edit = edits[0]
    assert edit.decision == "accepted"
    assert edit.proposer == "diagnoser"
    assert edit.kind == "revise"
    assert edit.payload["removes"] == [before.hypothesis_id]
    assert seen == [case]
    stored = bench.theory.get(edit.payload["adds"][0])
    assert tuple(stored.specific) == expected
    assert stored.source == "diagnoser"
    assert edit.rationale == (
        f"the minimised reproduction of r1 keeps {len(expected)} of the {len(before.specific)} literals of S"
    )
    assert bench.edits()[-1].edit_id == edit.edit_id


def test_after_skips_when_s_does_not_shrink(tmp_path: Path) -> None:
    bench, outcome = _opened(tmp_path)
    case = _case()
    edits = _diagnoser(lambda _case: phi("x1")).after(
        bench, _record(_minimize(fail_label("df_missing"), case), case), outcome
    )
    assert edits == ()
    assert bench.edits() == ()


def test_after_skips_without_a_reproduced_minimum(tmp_path: Path) -> None:
    bench, outcome = _opened(tmp_path)
    case = _case()
    base = fail_label("df_missing")

    def boom(_case):
        raise AssertionError("phi must not run")

    diag = _diagnoser(boom)
    variants = [
        base,
        _minimize(base, case, status="skipped"),
        _minimize(base, case, reproduced=False),
        _minimize(base, case, body={}),
        _minimize(base, case, reproduced=1),
    ]
    for label in variants:
        assert diag.after(bench, _record(label, case), outcome) == ()
    assert bench.edits() == ()


def test_after_skips_when_nothing_opened_or_the_family_is_gone(tmp_path: Path) -> None:
    bench, outcome = _opened(tmp_path)
    case = _case()
    label = _minimize(fail_label("df_missing"), case)
    passed = bench.observe(phi("plain"), pass_label(), "r-pass")
    assert passed.observation.opened is None

    def boom(_case):
        raise AssertionError("phi must not run")

    diag = _diagnoser(boom)
    assert diag.after(bench, _record(label, case, "r-pass"), passed) == ()
    bench.theory.remove(outcome.observation.opened)
    assert diag.after(bench, _record(label, case), outcome) == ()
    assert bench.edits() == ()


def test_after_returns_an_edit_the_acceptance_test_rejects(tmp_path: Path) -> None:
    bench, outcome = _opened(tmp_path)
    bench.observe(phi("x7"), pass_label(), "r2")
    case = _case()
    edits = _diagnoser(lambda _case: phi("x7")).after(
        bench, _record(_minimize(fail_label("df_missing"), case), case), outcome
    )
    assert len(edits) == 1
    edit = edits[0]
    assert edit.decision == "rolled_back"
    assert edit.payload.get("reason") is not None
    assert edit.payload.get("rollback") is None
    assert bench.edits() == (edit,)
    assert bench.theory.get(outcome.observation.opened).source != "diagnoser"


def test_periodic_compress_and_checkpoint(tmp_path: Path) -> None:
    bench = Workbench.create(tmp_path / "theory")
    diag = _diagnoser(lambda _case: None)
    compressed: list[int] = []
    notes: list[str] = []
    real_compress = bench.compress
    real_checkpoint = bench.checkpoint

    def compress():
        compressed.append(1)
        return real_compress()

    def checkpoint(note: str) -> int:
        notes.append(note)
        return real_checkpoint(note)

    bench.compress = compress
    bench.checkpoint = checkpoint
    assert diag.periodic(bench, COMPRESS_EVERY - 1) == ()
    assert compressed == [] and notes == [] and bench.generation == 0
    assert diag.periodic(bench, COMPRESS_EVERY) == ()
    assert compressed == [1]
    assert notes == [f"after {COMPRESS_EVERY} experiments"]
    assert bench.generation == 1
    assert CHECKPOINT_EVERY == COMPRESS_EVERY
    again = diag.periodic(bench, CHECKPOINT_EVERY * 2)
    assert again == ()
    assert notes[-1] == f"after {CHECKPOINT_EVERY * 2} experiments"
    assert bench.generation == 2


def test_code_digests_match_the_gate() -> None:
    found = code_digests()
    assert found == gate_digests()
    assert "surprise/diagnoser/diagnoser.py" in found
    assert "surprise/experiments/loop.py" in found
    assert all("/" in path and "\\" not in path for path in found)


def test_import_does_not_load_a_model_client() -> None:
    script = (
        "import json, sys\n"
        "import surprise.diagnoser, surprise.experiments.loop\n"
        "names = ('openai', 'httpx', 'anthropic', 'agents', 'llm', 'guidelines', 'evolution.co_evolution')\n"
        "print(json.dumps(sorted(name for name in names if name in sys.modules)))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=FRAMEWORK,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-400:]
    assert json.loads(proc.stdout.strip().splitlines()[-1]) == []


def test_rejects_missing_budget_and_a_nonempty_directory(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    assert main(["--out", str(missing), "--seed", "1"]) == 2
    assert not missing.exists()
    assert main(["--out", str(tmp_path / "no-seed"), "--max-experiments", "1"]) == 2
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "keep").write_text("x", encoding="utf-8")
    assert main(["--out", str(occupied), "--seed", "1", "--max-experiments", "1"]) == 2
    assert (occupied / "keep").read_text(encoding="utf-8") == "x"
    bad = tmp_path / "boot.json"
    bad.write_text("{}", encoding="utf-8")
    assert main(["--out", str(tmp_path / "bad"), "--seed", "1", "--max-experiments", "1", "--bootstrap", str(bad)]) == 2
    with pytest.raises(UsageError):
        run(tmp_path / "api", seed=1)


def test_short_run_matches_ledger_progress_and_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "run"
    boot = _f1_bootstrap(tmp_path)
    code = main(
        [
            "--out",
            str(out),
            "--seed",
            "7",
            "--engine",
            "duckdb",
            "--max-experiments",
            "4",
            "--bootstrap",
            str(boot),
            "--run-id",
            "loop-test",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0, captured.err[-800:]
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "budget_experiments"
    assert report["experiments"] == 5
    assert report["choices"] == 4
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert lines[-1] == "budget_experiments 5"
    assert len(lines) == 6
    _assert_run(out, report, seed=7, experiments=5, choices=4, run_id="loop-test")


def test_max_minutes_stops_before_a_choice(tmp_path: Path) -> None:
    out = tmp_path / "empty"
    out.mkdir()
    item = json.loads(_f1_bootstrap(tmp_path).read_text(encoding="utf-8"))
    report = run(
        out,
        seed=3,
        max_experiments=10,
        max_minutes=0,
        bootstrap=item,
        run_id="minutes",
    )
    assert report["status"] == "budget_minutes"
    assert report["choices"] == 0
    assert report["experiments"] == 1
    stored = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert stored["status"] == "budget_minutes"
    assert stored["experiments"] == 1
    progress = [json.loads(line) for line in (out / "progress.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(progress) == 1
    assert progress[0]["lane"] == "bootstrap"
    config = json.loads((out / "config.json").read_text(encoding="utf-8"))
    assert config["max_minutes"] == 0
    assert config["max_experiments"] == 10
    assert config["run_id"] == "minutes"


def test_two_processes_agree_without_elapsed(tmp_path: Path) -> None:
    boot = _f1_bootstrap(tmp_path)

    def once(name: str, hashseed: str) -> Path:
        out = tmp_path / name
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = hashseed
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "surprise.experiments.loop",
                "--out",
                str(out),
                "--seed",
                "11",
                "--engine",
                "duckdb",
                "--max-experiments",
                "3",
                "--bootstrap",
                str(boot),
                "--run-id",
                "det",
            ],
            cwd=FRAMEWORK,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=240,
        )
        assert proc.returncode == 0, proc.stderr[-800:]
        return out

    first = open_run(once("a", "1"))
    second = open_run(once("b", "2"))
    left = [{key: value for key, value in row.items() if key != "elapsed_s"} for row in first["progress"]]
    right = [{key: value for key, value in row.items() if key != "elapsed_s"} for row in second["progress"]]
    assert len(left) == len(right) == 4
    for index, (row_a, row_b) in enumerate(zip(left, right)):
        assert row_a == row_b, index
    assert _normal(first) == _normal(second)


def _assert_run(out: Path, report: dict, *, seed: int, experiments: int, choices: int, run_id: str) -> None:
    assert set(report) == _REPORT_KEYS
    assert report["run_id"] == run_id
    assert report["seed"] == seed
    assert report["engines"] == ["duckdb"]
    assert report["oracles"] == list(ORACLE_IDS)
    assert report["beta"] == BETA
    assert report["experiments"] == experiments
    assert report["choices"] == choices
    assert sum(report["labels"].values()) == experiments
    assert sum(report["lanes"].values()) == experiments
    assert sum(report["triage"].values()) == experiments
    assert set(report["edits"]) == {"accepted", "rejected", "rolled_back"}
    opened = open_run(out)
    assert check_rows(opened, out)["bootstrap"] == 1
    assert [row["record_id"] for row in opened["progress"]] == [record.record_id for record in opened["records"]]
    assert len(opened["records"]) == experiments
    first = opened["progress"][0]
    assert set(first) == {
        "seq",
        "record_id",
        "index",
        "slot",
        "lane",
        "oracle",
        "rule",
        "case_digest",
        "hypothesis",
        "parent",
        "op",
        "target",
        "zone",
        "predicted",
        "p_fail_valid",
        "p_invalid",
        "D",
        "U",
        "adjacent",
        "probes",
        "value",
        "y",
        "kind",
        "surprise",
        "triage",
        "opened",
        "owner",
        "rolled_back",
        "bets",
        "edits",
        "pool",
        "theory_version",
        "elapsed_s",
    }
    assert first["lane"] == "bootstrap" and first["slot"] == "bootstrap" and first["index"] == 0
    assert first["op"] == "bootstrap" and first["pool"] == {}
    for key in _NULL_SCORE:
        assert first[key] is None
    assert [row["index"] for row in opened["progress"][1:]] == list(range(1, choices + 1))
    for row in opened["progress"]:
        assert isinstance(row["theory_version"], str) and row["theory_version"].startswith("T-")
        assert isinstance(row["elapsed_s"], float)
    section = opened["manifest"]["hunter"]
    assert section["diagnoser"] == constants.as_dict()
    assert section["code"] == code_digests()
    assert section["beta"] == BETA
    assert sum(report["edits"].values()) == len(opened["wb"].edits())
    assert report["hypotheses"] == len(opened["wb"].theory.hypotheses)
    assert report["families"] == len(opened["wb"].families())
    assert report["curve"] == surprise_curve(opened["records"], 100)
    assert report["teeth"] == teeth(report["curve"])
    assert report["new_families"] == len(new_families(out / "theory"))
    assert isinstance(report["extractor"], dict) and report["extractor"]["calls"] >= experiments
    config = json.loads((out / "config.json").read_text(encoding="utf-8"))
    assert config["seed"] == seed and config["run_id"] == run_id
    assert config["max_experiments"] == choices
    assert config["beta"] == BETA
    ledger = Ledger(out / "ledger.sqlite")
    try:
        assert ledger.run_ids() == [run_id]
    finally:
        ledger.close()
