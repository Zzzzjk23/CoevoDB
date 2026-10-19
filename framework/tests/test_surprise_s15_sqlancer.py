"""SQLancer parsing, common CVE identity, report cells and real process lifecycle."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from surprise.baselines import sqlancer_run as sq
from surprise.harness.ledger import Ledger
from surprise.metrics import report as grid_report
from surprise.metrics.rq import label_key, run_metrics
from surprise.metrics.rundata import RunData

DATA = Path(__file__).parent / "data" / "sqlancer"
FRAMEWORK = Path(__file__).resolve().parents[1]
FIXTURES = {
    "norec_mismatch.log": ("mismatch", "NOREC", None),
    "tool_error_sqlexception.log": ("tool_error", None, "tool_error"),
    "tool_error_unsupported.log": ("tool_error", None, "tool_error"),
    "unexpected_error_ddl.log": ("unexpected_error", None, "not_a_query"),
    "tlp_mismatch.log": ("mismatch", "WHERE", None),
    "norec_join.log": ("mismatch", "NOREC", None),
    "unexpected_error_select.log": ("unexpected_error", "NOREC", None),
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", FIXTURES)
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_classification_and_line_endings(tmp_path, name, newline):
    path = tmp_path / name
    path.write_bytes((DATA / name).read_text(encoding="utf-8").replace("\n", newline).encode("utf-8"))
    parsed = sq.parse_log(path)
    kind, oracle, reason = FIXTURES[name]
    assert parsed.row["kind"] == kind
    assert parsed.row["sqlancer_oracle"] == oracle
    assert parsed.row["reason"] == reason
    assert parsed.row["converted"] is (reason is None)
    assert parsed.row["record_id"] is None
    assert parsed.row["database_version"] in ("v1.1.3", "v1.5.5")
    assert isinstance(parsed.row["seed"], int)
    reference = sq.parse_log(DATA / name)
    assert parsed.row == reference.row
    assert parsed.case == reference.case


def test_source_fragments():
    norec = sq.parse_log(DATA / "norec_mismatch.log").case
    assert norec.query == "SELECT * FROM t1 a"
    assert norec.predicate == "NOT EXISTS (SELECT 1 FROM t1 b WHERE b.ch = a.ch AND b.id <> a.id)"
    assert len(norec.setup) == 4
    assert all(not part.endswith(";") for part in norec.setup)
    join = sq.parse_log(DATA / "norec_join.log").case
    assert join.query == "SELECT * FROM t1 AS a LEFT JOIN t1 b ON (a.id = b.id)"
    assert join.predicate == "(a.ch = 'FROM WHERE') AND EXISTS (SELECT 1 FROM t1 c WHERE c.id = b.id)"
    tlp = sq.parse_log(DATA / "tlp_mismatch.log").case
    assert tlp.query == "SELECT a.id,  a.ch FROM t1 AS a"
    assert tlp.predicate == "(a.id > 0)"
    unexpected = sq.parse_log(DATA / "unexpected_error_select.log").case
    assert unexpected.query == "SELECT * FROM t1 a"
    assert unexpected.predicate == "((a.id)::INTEGER > 0)"


@pytest.mark.parametrize("query", [
    "SELECT COUNT(*) FROM t1 WHERE id > 0 GROUP BY id",
    "SELECT COUNT(*) FROM t1 WHERE id > 0 HAVING count(*) > 0",
    "SELECT id FROM t1 WHERE id > 0 ORDER BY id",
    "SELECT id FROM t1 WHERE id > 0 LIMIT 1",
    "SELECT DISTINCT id FROM t1 WHERE id > 0",
    "SELECT row_number() OVER () FROM t1 WHERE id > 0",
    "SELECT id FROM t1 WHERE id > 0 UNION ALL SELECT id FROM t1",
    "SELECT id FROM t1",
    "SELECT id FROM",
])
def test_unsupported_shapes(tmp_path, query):
    text = (DATA / "unexpected_error_select.log").read_text(encoding="utf-8")
    path = tmp_path / "shape.log"
    path.write_text(text.replace("SELECT a.id FROM t1 a WHERE ((a.id)::INTEGER > 0)", query), encoding="utf-8")
    parsed = sq.parse_log(path)
    assert parsed.case is None
    assert parsed.row["reason"] == "unsupported_shape"


def test_tlp_query_lines_and_content_mismatch(tmp_path):
    text = (DATA / "tlp_mismatch.log").read_text(encoding="utf-8")
    # Content mismatch's second message embeds a commented query and cardinality.
    text = text.replace("The size of the result sets mismatch (2 and 1)!", "The content of the result sets mismatch!")
    text = "\n".join(line for line in text.splitlines() if not line.startswith(("--First query", "--Second query")))
    path = tmp_path / "content.log"
    path.write_text(text, encoding="utf-8")
    parsed = sq.parse_log(path)
    assert parsed.row["kind"] == "mismatch"
    assert parsed.case.query == "SELECT a.id,  a.ch FROM t1 AS a"
    assert parsed.case.predicate == "(a.id > 0)"


def test_classpath_overrides(tmp_path):
    names = ["override/duckdb_jdbc-1.5.5.0.jar", "override/extra-2.jar", "sqlancer-2.0.0.jar",
             "lib/duckdb_jdbc-1.3.0.0.jar", "lib/extra-1.0.jar", "lib/other-1.0.jar"]
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    assert [p.relative_to(tmp_path).as_posix() for p in sq.classpath(tmp_path)] == [
        "override/duckdb_jdbc-1.5.5.0.jar", "override/extra-2.jar", "sqlancer-2.0.0.jar", "lib/other-1.0.jar"]


def test_tool_environment_and_fallback(tmp_path, monkeypatch):
    java = tmp_path / "jdk" / "custom java.exe"
    java.parent.mkdir()
    java.touch()
    home = tmp_path / "custom sqlancer"
    home.mkdir()
    monkeypatch.setenv("COEVO_JAVA", str(java))
    monkeypatch.setenv("COEVO_SQLANCER_HOME", str(home))
    assert sq.find_tools() == (java, home)
    monkeypatch.delenv("COEVO_JAVA")
    monkeypatch.delenv("COEVO_SQLANCER_HOME")
    monkeypatch.setattr(sq, "checkout_root", lambda: tmp_path)
    java = tmp_path / ".orch/jdk/test/bin" / ("java.exe" if os.name == "nt" else "java")
    java.parent.mkdir(parents=True)
    java.touch()
    home = tmp_path / ".orch/sqlancer"
    home.mkdir()
    assert sq.find_tools() == (java, home)
    twin = tmp_path / ".orch/jdk/second/bin" / java.name
    twin.parent.mkdir(parents=True)
    twin.touch()
    with pytest.raises(RuntimeError, match="expected one"):
        sq.find_tools()


def test_replay_and_grid_report(tmp_path, monkeypatch):
    logs = tmp_path / "logs"
    logs.mkdir()
    for name in list(FIXTURES)[:4]:
        (logs / name).write_bytes((DATA / name).read_bytes())
    (logs / "ignored-cur.log").write_text("not a report", encoding="utf-8")
    cell = tmp_path / "grid/cells/sqlancer/s7-r0"
    original_run = sq.subprocess.run

    def no_java(command, **kwargs):
        assert command[0] == "git", "replay must not start Java"
        return original_run(command, **kwargs)

    monkeypatch.setattr(sq.subprocess, "run", no_java)
    result = sq.run(cell, seed=7, replay_logs=logs)
    monkeypatch.setattr(sq.subprocess, "run", original_run)
    stats = result["sqlancer"]
    assert result["status"] == "replayed"
    assert result["executions"] is None and stats["pid"] is None
    assert result["labels"] == {"fail": 1}
    assert stats["kinds"] == {"mismatch": 1, "unexpected_error": 1, "tool_error": 2}
    assert (stats["reports"], stats["converted"], stats["judged"], stats["unjudged"]) == (4, 1, 1, 0)
    with Ledger(cell / "ledger.sqlite") as ledger:
        record, = ledger.records(run_id=result["run_id"])
        manifest = ledger.run_manifest(result["run_id"])
    assert record.label.y == "fail"
    assert record.purpose == "sqlancer"
    assert label_key(record) == "fix|duckdb|deliminator,filter_pushdown"
    assert manifest["baseline"] == "sqlancer"
    assert manifest["sqlancer"]["jdbc"] == stats["jdbc"]
    assert RunData.open(cell).kind == "sqlancer"
    assert run_metrics(cell)["rq1"]["family_count"] == 1
    rows = [json.loads(line) for line in (cell / "sqlancer/reports.jsonl").read_text().splitlines()]
    assert [row["log"] for row in rows] == sorted(list(FIXTURES)[:4])
    assert next(row for row in rows if row["converted"])["record_id"] == record.record_id
    progress, = [json.loads(line) for line in (cell / "progress.jsonl").read_text().splitlines()]
    assert progress["record_id"] == record.record_id and progress["y"] == "fail"
    (cell / "cell.json").write_text(json.dumps({"status": "done"}), encoding="utf-8")
    config = {"schema": 1, "name": "sqlancer", "reference": "sqlancer", "seeds": [7], "repeats": 1,
              "window": 10, "arms": [{"name": "sqlancer", "kind": "sqlancer", "run": True}]}
    grid = tmp_path / "grid"
    (grid / "grid.json").write_text(json.dumps(config), encoding="utf-8")
    report = grid_report.build(grid)
    assert report["arms"]["sqlancer"]["cells"] == ["sqlancer/s7-r0"]
    assert report["rq1"]["arms"]["sqlancer"]["families_per_hour"]["n"] == 1
    assert report["rq1"]["arms"]["sqlancer"]["family_count"]["median"] == 1
    assert report["external"]["sqlancer"]["engine"] == "duckdb"


@pytest.mark.parametrize("kwargs", [
    {}, {"max_minutes": 0}, {"max_minutes": float("nan")}, {"max_minutes": float("inf")},
    {"threads": 0}, {"engine": "sqlite"}, {"oracles": ["TLP"]}, {"run_id": ""},
])
def test_argument_errors(tmp_path, kwargs):
    with pytest.raises(sq.UsageError):
        sq.run(tmp_path / "out", seed=7, **kwargs)
    assert not (tmp_path / "out").exists()


def test_real_run_60_seconds(tmp_path):
    report = sq.run(tmp_path / "live", seed=7, max_minutes=1)
    assert report["status"] == "budget_minutes"
    assert report["executions"] >= 1000
    assert 60 <= report["wall_s"] < 120
    assert report["sqlancer"]["commit"] == "ab328b756bf5d923b9d93959af3432546efe56fd"
    assert "duckdb_jdbc-1.5.5.0.jar" in report["sqlancer"]["jdbc"]
    assert not any("1.3.0.0" in name for name in report["sqlancer"]["jdbc"])
    assert len(report["sqlancer"]["jar_sha256"]) == 64
    assert report["sqlancer"]["java"]


def test_real_interrupt_cleans_java(tmp_path):
    from surprise.gates.s15 import pid_alive

    out = tmp_path / "interrupt"
    env = {k: v for k, v in os.environ.items() if k.upper() != "DEEPSEEK_API_KEY"}
    proc = subprocess.Popen([sys.executable, "-m", "surprise.baselines.sqlancer_run", "--out", str(out),
                             "--seed", "3", "--max-minutes", "5"], cwd=FRAMEWORK, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
    try:
        time.sleep(20)
        assert proc.poll() is None
        proc.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
        stdout, stderr = proc.communicate(timeout=60)
        assert proc.returncode == 130, (stdout, stderr)
        report = read(out / "report.json")
        assert report["status"] == "interrupted"
        assert isinstance(report["sqlancer"]["pid"], int)
        assert not pid_alive(report["sqlancer"]["pid"])
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)
