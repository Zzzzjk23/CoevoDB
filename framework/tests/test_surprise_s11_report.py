"""Mann-Whitney, A12, and the one-command RQ1-RQ6 report."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import pytest

from surprise.baselines import sqlancer
from surprise.experiments import grid, loop
from surprise.gates.s06 import fail_label, pass_label
from surprise.gates.s11 import ref_mwu
from surprise.gates.s11_cases import A12, FIGURES, MEDIAN, MWU_EXACT, MWU_LARGE, MWU_SAME, MWU_TIES
from surprise.metrics.report import build
from surprise.metrics.rq import old_metrics, run_metrics
from surprise.metrics.stats import a12, mann_whitney_u, median, summarize
from test_surprise_s11_metrics import _record, _run

FRAMEWORK = Path(__file__).resolve().parents[1]
PNG = b"\x89PNG\r\n\x1a\n"
_REQUIRED = {
    "schema",
    "grid",
    "reference",
    "arms",
    "cells",
    "rq1",
    "rq2",
    "rq3",
    "rq4",
    "rq5",
    "rq6",
    "stats",
    "external",
}


def _scipy_mwu():
    try:
        from scipy.stats import mannwhitneyu
    except ImportError:
        return None
    return mannwhitneyu


def test_median_and_summarize() -> None:
    for values, expected in MEDIAN:
        got = median(list(values))
        if expected is None:
            assert got is None
        else:
            assert got == pytest.approx(expected)
    assert summarize([3.0, None, 1.0, 2.0]) == {"n": 3, "median": 2.0, "min": 1.0, "max": 3.0}
    assert summarize([]) == {"n": 0, "median": None, "min": None, "max": None}
    assert summarize([None, None]) == {"n": 0, "median": None, "min": None, "max": None}


def test_a12_hand_values() -> None:
    for left, right, expected in A12:
        assert a12(list(left), list(right)) == pytest.approx(expected)
    assert a12(list(MWU_SAME[0]), list(MWU_SAME[1])) == pytest.approx(0.5)
    assert a12([], [1.0]) is None
    assert a12([1.0], []) is None


def test_mann_whitney_hand_values() -> None:
    for left, right, score, method, probability in MWU_EXACT:
        got = mann_whitney_u(list(left), list(right))
        assert got["method"] == method == "exact"
        assert got["u"] == pytest.approx(score)
        assert got["p"] == pytest.approx(probability, abs=1e-12)
        reference = ref_mwu(left, right)
        assert reference[0] == pytest.approx(score)
        assert reference[1] == method
        assert reference[2] == pytest.approx(probability, abs=1e-12)
    for left, right in MWU_TIES + [MWU_LARGE]:
        score, method, probability = ref_mwu(left, right)
        got = mann_whitney_u(list(left), list(right))
        assert method == "asymptotic"
        assert got["method"] == "asymptotic"
        assert got["u"] == pytest.approx(score)
        assert got["p"] == pytest.approx(probability, abs=1e-9)
    same = mann_whitney_u(list(MWU_SAME[0]), list(MWU_SAME[1]))
    assert same["p"] == pytest.approx(1.0)
    assert same["method"] == "asymptotic"
    assert mann_whitney_u([], [1.0]) is None
    assert mann_whitney_u([1.0], []) is None


def test_mann_whitney_matches_scipy_when_installed() -> None:
    mannwhitneyu = _scipy_mwu()
    if mannwhitneyu is None:
        return
    for left, right, _score, method, probability in MWU_EXACT:
        theirs = mannwhitneyu(list(left), list(right), alternative="two-sided", method="exact")
        assert float(theirs.pvalue) == pytest.approx(probability, abs=1e-12)
        assert method == "exact"
    for left, right in MWU_TIES + [MWU_LARGE, MWU_SAME]:
        got = mann_whitney_u(list(left), list(right))
        theirs = mannwhitneyu(
            list(left), list(right), alternative="two-sided", method="asymptotic", use_continuity=True,
        )
        assert got["p"] == pytest.approx(float(theirs.pvalue), abs=1e-9)
        assert got["u"] == pytest.approx(float(theirs.statistic), abs=1e-9)


def test_exact_mann_whitney_is_fast_at_the_size_limit() -> None:
    left = list(range(0, 20, 2))
    right = list(range(1, 20, 2))
    started = time.perf_counter()
    got = mann_whitney_u(left, right)
    assert time.perf_counter() - started < 0.5
    assert got["method"] == "exact"
    assert 0.0 <= got["p"] <= 1.0
    assert a12(left, right) == pytest.approx(got["u"] / (len(left) * len(right)))
    mannwhitneyu = _scipy_mwu()
    if mannwhitneyu is None:
        return
    theirs = mannwhitneyu(left, right, alternative="two-sided", method="exact")
    assert got["p"] == pytest.approx(float(theirs.pvalue), abs=1e-12)
    assert got["u"] == pytest.approx(float(theirs.statistic), abs=1e-9)


def _config(tmp_path: Path, body: dict) -> dict:
    path = tmp_path / "source.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return grid.load_config(path)


def _dump(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _cell(directory: Path, arm: str, kind: str, seed: int, rep: int, status: str) -> None:
    _dump(directory / "cell.json", {
        "arm": arm,
        "kind": kind,
        "seed": seed,
        "rep": rep,
        "status": status,
        "returncode": 0 if status == "done" else 1,
    })


def _old(directory: Path, seed: int, wall_s: float, keys: list[str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "run").mkdir(exist_ok=True)
    rows = [
        {"root_key": key, "candidate": {"kind": "bug"}, "signature": None}
        for key in keys
    ]
    (directory / "run" / "bugs.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8",
    )
    _dump(directory / "old_run.json", {
        "mode": "no_llm",
        "seed": seed,
        "wall_s": wall_s,
        "ended": "budget",
        "run_dir": "run",
    })
    _cell(directory, "old", "old_coevodb", seed, 0, "done")


def _digest(root: Path) -> dict[str, str]:
    report = root / "report"
    found = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path == report or report in path.parents:
            continue
        found[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def _pngs(directory: Path) -> None:
    for name in FIGURES:
        path = directory / "figures" / name
        assert path.is_file(), name
        blob = path.read_bytes()
        assert blob[:8] == PNG
        assert len(blob) > 1000


def test_report_on_failed_cells_and_sqlancer(tmp_path: Path) -> None:
    config = _config(tmp_path, {
        "schema": 1,
        "name": "fast-report",
        "budget": {"minutes": 1},
        "seeds": [0],
        "reference": "old",
        "window": 1,
        "arms": [
            {"name": "old", "kind": "old_coevodb"},
            {"name": "surprise", "kind": "surprise", "freeze": "theory", "hunter": "random"},
            {"name": "paired", "kind": "surprise", "theory_from": "base@1", "select_from": "other@2"},
            {"name": "q", "kind": "sqlancer", "engine": "sqlite3"},
        ],
    })
    root = tmp_path / "grid"
    _dump(root / "grid.json", config)
    _old(root / "cells" / "old" / "s0-r0", 0, 3600.0, ["same", "same"])
    _cell(root / "cells" / "surprise" / "s0-r0", "surprise", "surprise", 0, 0, "failed")
    _cell(root / "cells" / "paired" / "s0-r0", "paired", "surprise", 0, 0, "failed")
    dedup = tmp_path / "dedup.json"
    _dump(dedup, {"schema": 1, "kept": 3})
    _dump(root / "extras" / "coverage.json", {"rows": 4, "hit": True})
    before = _digest(root)
    report = build(root, dedup=dedup)
    assert _digest(root) == before
    assert not (root / "cells" / "old" / "s0-r0" / "metrics.json").exists()
    text = (root / "report" / "report.json").read_text(encoding="utf-8")
    assert json.loads(text) == report
    again = build(root, dedup=dedup)
    assert (root / "report" / "report.json").read_text(encoding="utf-8") == text
    assert again == report
    assert set(report) == _REQUIRED | {"extras"}
    assert report["schema"] == 1 and report["grid"] == "fast-report" and report["reference"] == "old"
    assert report["extras"] == {
        "dedup": {"schema": 1, "kept": 3},
        "coverage": {"rows": 4, "hit": True},
    }
    assert report["external"] == {"sqlancer": sqlancer.metrics(sqlancer.load(), engine="duckdb")}
    assert report["arms"]["q"]["cells"] == []
    assert report["arms"]["q"]["options"]["engine"] == "sqlite3"
    assert report["cells"]["surprise/s0-r0"]["metrics"] is None
    assert report["cells"]["paired/s0-r0"]["status"] == "failed"
    assert report["cells"]["old/s0-r0"]["metrics"] == old_metrics(root / "cells" / "old" / "s0-r0")
    assert report["rq1"]["arms"]["old"]["family_count"] == {"n": 1, "median": 1.0, "min": 1.0, "max": 1.0}
    assert report["rq1"]["arms"]["old"]["families_per_hour"]["median"] == pytest.approx(1.0)
    assert report["rq1"]["arms"]["q"]["family_count"]["n"] == 1
    assert report["rq1"]["arms"]["q"]["family_count"]["median"] == pytest.approx(0.0)
    assert report["rq1"]["arms"]["surprise"]["family_count"]["n"] == 0
    assert report["rq1"]["curves"]["old/s0-r0"] == [[60.0, 1]]
    pair = [row for row in report["stats"] if row["metric"] == "family_count" and row["a"] == "old" and row["b"] == "q"]
    assert len(pair) == 1 and pair[0]["n_a"] == 1 and pair[0]["n_b"] == 1
    assert pair[0]["p"] is not None and pair[0]["a12"] is not None
    assert [row["rq"] for row in report["stats"]] == sorted(row["rq"] for row in report["stats"])
    assert all(row["a"] != "surprise" and row["b"] != "surprise" for row in report["stats"])
    frozen = report["rq5"]["freezing"]
    assert len(frozen) == 1 and frozen[0]["arm"] == "surprise"
    assert frozen[0]["freeze"] == "theory" and frozen[0]["hunter"] == "random" and frozen[0]["vs"] == "old"
    assert frozen[0]["delta"] == {
        "family_count": None,
        "families_per_hour": None,
        "brier": None,
        "mean_surprise": None,
    }
    assert report["rq5"]["ciao"] == {}
    paired = report["rq5"]["pairing"]
    assert len(paired) == 1
    assert paired[0]["arm"] == "paired" and paired[0]["theory_from"] == "base@1"
    assert paired[0]["select_from"] == "other@2"
    assert paired[0]["family_count"]["n"] == 0 and paired[0]["mean_surprise"]["median"] is None
    assert report["rq6"]["partition"] is None
    assert report["rq6"]["boundary"]["old/s0-r0"] is None
    markdown = (root / "report" / "report.md").read_text(encoding="utf-8")
    assert all(f"RQ{index}" in markdown for index in range(1, 7))
    assert "figures/rq1_families.png" in markdown and "figures/rq6_recall.png" in markdown
    _pngs(root / "report")
    proc = subprocess.run(
        [sys.executable, "-m", "surprise.metrics.report", str(root), "--out", str(tmp_path / "cli"), "--dedup", str(dedup)],
        cwd=FRAMEWORK,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    cli = json.loads((tmp_path / "cli" / "report.json").read_text(encoding="utf-8"))
    assert "coverage" in cli["extras"] and cli["extras"]["dedup"] == report["extras"]["dedup"]


def test_killed_old_cell_without_bugs_file_counts_as_zero(tmp_path: Path) -> None:
    config = _config(tmp_path, {
        "schema": 1,
        "name": "killed-old",
        "budget": {"minutes": 1},
        "seeds": [0],
        "reference": "old",
        "window": 1,
        "arms": [{"name": "old", "kind": "old_coevodb"}],
    })
    root = tmp_path / "grid"
    cell = root / "cells" / "old" / "s0-r0"
    (cell / "results" / "run").mkdir(parents=True)
    _dump(cell / "old_run.json", {
        "mode": "no_llm",
        "seed": 0,
        "wall_s": 60.0,
        "ended": "killed",
        "run_dir": "results/run",
        "reports": 0,
    })
    _cell(cell, "old", "old_coevodb", 0, 0, "done")
    _dump(root / "grid.json", config)
    before = _digest(root)
    report = build(root)
    assert _digest(root) == before
    assert not (cell / "results" / "run" / "bugs.jsonl").exists()
    metrics = report["cells"]["old/s0-r0"]["metrics"]
    assert metrics["rq1"]["family_count"] == 0
    assert metrics["rq1"]["families"] == []
    assert metrics["rq1"]["families_per_hour"] == pytest.approx(0.0)
    assert metrics["rq1"]["duplicate_rate"] is None
    assert metrics["rq1"]["first_family"] is None
    assert report["rq1"]["arms"]["old"]["families_per_hour"]["n"] == 1
    assert report["rq1"]["curves"]["old/s0-r0"] == [[1.0, 0]]


def test_report_build_on_two_real_runs(tmp_path: Path) -> None:
    config = _config(tmp_path, {
        "schema": 1,
        "name": "report-fixture",
        "budget": {"experiments": 1},
        "seeds": [0, 1],
        "reference": "surprise",
        "window": 1,
        "arms": [
            {
                "name": "surprise",
                "kind": "surprise",
                "engines": ["duckdb"],
                "oracles": ["tlp"],
                "hunter": "random",
                "budget": {"experiments": 1},
            },
            {"name": "old", "kind": "old_coevodb", "budget": {"minutes": 1}},
            {"name": "paired", "kind": "surprise", "theory_from": "base@head", "select_from": "other@2"},
        ],
    })
    root = tmp_path / "grid"
    _dump(root / "grid.json", config)
    for seed in (0, 1):
        cell = root / "cells" / "surprise" / f"s{seed}-r0"
        loop.run(cell, seed=seed, engines=("duckdb",), oracles=("tlp",), max_experiments=1)
        _cell(cell, "surprise", "surprise", seed, 0, "done")
    _old(root / "cells" / "old" / "s0-r0", 0, 3600.0, ["same", "same"])
    _old(root / "cells" / "old" / "s1-r0", 1, 1800.0, ["one", "two"])
    _cell(root / "cells" / "old" / "s1-r0", "old", "old_coevodb", 1, 0, "done")
    paired_mean = (-math.log2(0.25) + -math.log2(0.75)) / 2.0
    for seed in (0, 1):
        cell = root / "cells" / "paired" / f"s{seed}-r0"
        _run(
            cell,
            [
                _record("run-1", 1, fail_label("f1"), p_t=0.25),
                _record("run-1", 2, pass_label(), p_t=0.25),
            ],
            report={"status": "budget_experiments", "wall_s": 60.0},
        )
        _cell(cell, "paired", "surprise", seed, 0, "done")
    before = _digest(root)
    report = build(root)
    assert _digest(root) == before
    assert "extras" not in report
    text = (root / "report" / "report.json").read_text(encoding="utf-8")
    assert build(root) and (root / "report" / "report.json").read_text(encoding="utf-8") == text
    assert json.loads(text) == report
    assert set(report) == _REQUIRED
    for seed in (0, 1):
        cell = root / "cells" / "surprise" / f"s{seed}-r0"
        assert report["cells"][f"surprise/s{seed}-r0"]["metrics"] == run_metrics(cell, window=1)
        assert not (cell / "metrics.json").exists()
    assert report["cells"]["old/s0-r0"]["metrics"]["rq1"]["family_count"] == 1
    assert report["cells"]["old/s1-r0"]["metrics"]["rq1"]["family_count"] == 2
    assert report["rq1"]["arms"]["old"]["family_count"]["median"] == pytest.approx(1.5)
    assert report["rq1"]["arms"]["old"]["families_per_hour"]["median"] == pytest.approx(2.5)
    assert report["rq1"]["arms"]["old"]["duplicate_rate"]["median"] == pytest.approx(0.25)
    assert report["rq1"]["curves"]["old/s0-r0"] == [[60.0, 1]]
    assert report["rq1"]["curves"]["old/s1-r0"] == [[30.0, 2]]
    surprise_counts = [
        report["cells"][f"surprise/s{seed}-r0"]["metrics"]["rq1"]["family_count"] for seed in (0, 1)
    ]
    assert report["rq1"]["arms"]["surprise"]["family_count"] == summarize(surprise_counts)
    hours = []
    for seed, wall_count in ((0, None), (1, None)):
        del wall_count
        metrics = report["cells"][f"surprise/s{seed}-r0"]["metrics"]
        hours.append(metrics["rq1"]["families_per_hour"])
        families = metrics["rq1"]["families"]
        curve = []
        cumulative = 0
        for family in families:
            cumulative += 1
            if family["elapsed_s"] is not None:
                curve.append([family["elapsed_s"] / 60.0, cumulative])
        assert report["rq1"]["curves"][f"surprise/s{seed}-r0"] == curve
    row = next(
        item for item in report["stats"]
        if item["metric"] == "families_per_hour" and item["a"] == "surprise" and item["b"] == "old"
    )
    assert row["n_a"] == 2 and row["n_b"] == 2
    present = [value for value in hours if value is not None]
    old_hours = [1.0, 4.0]
    if present:
        test = mann_whitney_u(present, old_hours)
        assert row["u"] == pytest.approx(test["u"])
        assert row["p"] == pytest.approx(test["p"])
        assert row["method"] == test["method"]
        assert row["a12"] == pytest.approx(a12(present, old_hours))
    keys = [(item["rq"], item["metric"], item["a"], item["b"]) for item in report["stats"]]
    assert keys == sorted(keys)
    frozen = next(item for item in report["rq5"]["freezing"] if item["arm"] == "surprise")
    assert frozen["hunter"] == "random" and frozen["vs"] == "surprise" and frozen["freeze"] is None
    for section, metric in (
        ("rq1", "family_count"),
        ("rq1", "families_per_hour"),
        ("rq2", "mean_surprise"),
    ):
        median_value = report[section]["arms"]["surprise"][metric]["median"]
        if median_value is None:
            assert frozen["delta"][metric] is None
        else:
            assert frozen["delta"][metric] == pytest.approx(0.0)
    assert [item["arm"] for item in report["rq5"]["pairing"]] == ["paired"]
    paired_summary = report["rq5"]["pairing"][0]["mean_surprise"]
    assert paired_summary["n"] == 2
    assert paired_summary["median"] == pytest.approx(paired_mean)
    assert report["rq2"]["arms"]["paired"]["mean_surprise"] == paired_summary
    assert report["rq6"]["partition"] is None
    assert report["external"]["sqlancer"]["family_count"] == 0
    saved = json.loads((root / "grid.json").read_text(encoding="utf-8"))
    for arm in saved["arms"]:
        assert report["arms"][arm["name"]]["options"] == arm
        assert report["arms"][arm["name"]]["kind"] == arm["kind"]
    markdown = (root / "report" / "report.md").read_text(encoding="utf-8")
    for index, title in (
        (1, "RQ1 发现"),
        (2, "RQ2 校准"),
        (3, "RQ3 LLM 猜想"),
        (4, "RQ4 Harness"),
        (5, "RQ5 协同进化"),
        (6, "RQ6 理论质量"),
    ):
        assert title in markdown
        assert f"RQ{index}" in markdown
    _pngs(root / "report")
