"""Identity keys, families of a hand-fed workbench, and old bug reports."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from surprise.harness.contracts import Label
from surprise.metrics.dups import (
    compare,
    duplicate_rate,
    identity_key,
    main,
    new_families,
    old_reports,
)
from surprise.theory import Workbench
from test_surprise_s06_common import PLAIN, TOP, hypothesis

BASELINE = (
    Path(__file__).resolve().parents[1]
    / "surprise"
    / "docs"
    / "baseline"
    / "duckdb_no_llm_20261008_204923"
    / "bugs.jsonl"
)
FIX = "fix|duckdb|deliminator,filter_pushdown"
MISSING = "shape|datafusion|wrong_result|-|missing_only"
EXTRA = "shape|datafusion|wrong_result|-|extra_only"
ORPHAN = "shape|sqlite|crash|-|none"


def feed_store(root: Path) -> Workbench:
    """A store with one fix-set family, two copies of one shape, and a family that owns nothing."""
    from surprise.gates.s06 import fail_label, phi

    bench = Workbench.create(root)
    bench.theory.put(
        hypothesis(
            hypothesis_id="horphan",
            engine="sqlite",
            oracle="tlp",
            interventions=(),
            specific=PLAIN,
            general=TOP,
            fail_kind="crash",
            error_class=None,
            behavior_shape="none",
        )
    )
    bench.store.save(bench.theory)
    bench.observe(phi("plain"), Label(y="pass", oracle="cross_dbms"), "p1")
    bench.observe(phi("joinq", engine="duckdb"), fail_label("f1"), "d1")
    bench.observe(phi("x1"), fail_label("df_missing"), "r1")
    bench.observe(phi("joinq", engine="duckdb"), fail_label("f1", oracle="tlp"), "d2")
    bench.observe(phi("x1"), fail_label("df_missing", oracle="tlp"), "r2")
    bench.observe(phi("x4"), fail_label("df_extra"), "r3")
    bench.observe(phi("plain"), Label(y="invalid", oracle="cross_dbms", invalid_reason="query_error"), "i1")
    bench.observe(phi("x6"), fail_label("df_both"), "u1")
    return bench


def test_identity_key_shapes() -> None:
    assert identity_key("duckdb", ["filter_pushdown", "deliminator"], "crash", "X", "both") == FIX
    assert identity_key("duckdb", ("join_order",), None, None, None) == "fix|duckdb|join_order"
    assert identity_key("duckdb", [], "wrong_result", None, "missing_only") == MISSING.replace("datafusion", "duckdb")
    assert identity_key("duckdb", [], "", "", "") == "shape|duckdb|-|-|-"
    assert identity_key("datafusion", [], "wrong_result", None, "missing_only") == MISSING


def test_duplicate_rate() -> None:
    assert duplicate_rate([]) is None
    assert duplicate_rate(["a"]) == 0.0
    assert duplicate_rate(["a", "b"]) == 0.0
    assert duplicate_rate(["a", "a", "a", "b", "b"]) == 0.6


def test_new_families_follow_first_records(tmp_path: Path) -> None:
    root = tmp_path / "theory"
    bench = feed_store(root)
    rows = new_families(root)
    assert [row["key"] for row in rows] == [FIX, MISSING, MISSING, EXTRA, ORPHAN]
    assert [row["first_record"] for row in rows] == ["d1", "r1", "r2", "r3", None]
    assert [row["engine"] for row in rows] == ["duckdb", "datafusion", "datafusion", "datafusion", "sqlite"]
    fix = rows[0]
    assert fix["family"] == "duckdb|fix:deliminator+filter_pushdown"
    assert fix["hypotheses"] == list(bench.families()[fix["family"]])
    assert len(fix["hypotheses"]) == 2
    assert rows[-1]["family"] == "sqlite|horphan"
    assert rows[-1]["hypotheses"] == ["horphan"]
    assert bench.partition()["u1"] is None
    assert "u1" not in {row["first_record"] for row in rows}
    assert "p1" not in bench.partition() and "i1" not in bench.partition()
    assert duplicate_rate([row["key"] for row in rows]) == 0.2
    assert new_families(root) == rows


def test_new_families_of_an_empty_store(tmp_path: Path) -> None:
    root = tmp_path / "theory"
    Workbench.create(root)
    assert new_families(root) == []


def _report(root_key: str, *, signature: dict | None, kind: str = "plan_variant", origin: str = "hunter",
            iteration: object = 1) -> str:
    return json.dumps(
        {
            "candidate": {"kind": kind, "id": root_key},
            "iteration": iteration,
            "root_key": root_key,
            "signature": signature,
            "origin": origin,
        }
    )


def test_old_reports_empty_baseline_and_a_truncated_tail(tmp_path: Path) -> None:
    assert BASELINE.is_file()
    assert old_reports(BASELINE) == []

    fix = {"engine": "duckdb", "fix_kind": "single", "fix_set": ["filter_pushdown", "deliminator"]}
    minimal = {"engine": "datafusion", "fix_kind": "minimal_set", "fix_set": ["join_order"]}
    empty_fix = {"engine": "duckdb", "fix_kind": "single", "fix_set": []}
    pervasive = {"engine": "duckdb", "fix_kind": "pervasive", "fix_set": ["threads"]}
    lines = [
        _report("aa", signature=fix, iteration=3),
        "",
        "   ",
        _report("bb", signature=None, kind="norec", origin="dce", iteration="sweep"),
        _report("cc", signature=minimal, origin="dce"),
        _report("dd", signature=empty_fix),
        _report("ee", signature=pervasive),
        '{"root_key": "cut"',
    ]
    path = tmp_path / "bugs.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    reports = old_reports(path)
    assert [row["root_key"] for row in reports] == ["aa", "bb", "cc", "dd", "ee"]
    assert reports[0]["key"] == FIX
    assert reports[0]["fix_set"] == ["filter_pushdown", "deliminator"]
    assert reports[0]["fix_kind"] == "single" and reports[0]["engine"] == "duckdb"
    assert reports[0]["origin"] == "hunter" and reports[0]["iteration"] == 3
    assert reports[0]["kind"] == "plan_variant"
    assert reports[1]["key"] == "sigma|bb"
    assert reports[1]["engine"] == "duckdb" and reports[1]["fix_kind"] is None and reports[1]["fix_set"] == []
    assert reports[1]["origin"] == "dce" and reports[1]["iteration"] == "sweep" and reports[1]["kind"] == "norec"
    assert reports[2]["key"] == "fix|datafusion|join_order" and reports[2]["engine"] == "datafusion"
    assert reports[3]["key"] == "sigma|dd"
    assert reports[4]["key"] == "sigma|ee" and reports[4]["fix_set"] == ["threads"]
    assert duplicate_rate([row["key"] for row in reports]) == 0.0

    only_cut = tmp_path / "cut.jsonl"
    only_cut.write_text('{"root_key":', encoding="utf-8")
    assert old_reports(only_cut) == []


def test_old_reports_reject_a_broken_line_that_is_not_last(tmp_path: Path) -> None:
    path = tmp_path / "bugs.jsonl"
    good = _report("aa", signature=None)
    path.write_text(good + "\n{not-json\n" + good + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 2"):
        old_reports(path)


def test_dups_cli_reads_the_run_and_the_old_dir(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run = tmp_path / "run"
    feed_store(run / "theory")
    old = tmp_path / "old"
    bugs = old / "results" / "duckdb_no_llm_x"
    bugs.mkdir(parents=True)
    (bugs / "bugs.jsonl").write_text(
        _report("aa", signature={"engine": "duckdb", "fix_kind": "single", "fix_set": ["join_order"]})
        + "\n"
        + _report("bb", signature={"engine": "duckdb", "fix_kind": "single", "fix_set": ["join_order"]})
        + "\n"
        + '{"root',
        encoding="utf-8",
    )
    (old / "old_run.json").write_text(json.dumps({"run_dir": "results/duckdb_no_llm_x"}), encoding="utf-8")
    out = tmp_path / "compare.json"
    assert main(["--new", str(run), "--old", str(old), "--out", str(out)]) == 0
    written = out.read_text(encoding="utf-8")
    assert written.isascii()
    payload = json.loads(written)
    assert payload == compare(run, old)
    assert payload["new"]["rate"] == 0.2
    assert [row["key"] for row in payload["old"]["reports"]] == ["fix|duckdb|join_order", "fix|duckdb|join_order"]
    assert payload["old"]["rate"] == 0.5

    assert main(["--new", str(run), "--old", str(old)]) == 0
    printed = capsys.readouterr().out
    assert printed.isascii()
    assert json.loads(printed) == payload
