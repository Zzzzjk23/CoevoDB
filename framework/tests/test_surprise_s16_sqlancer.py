"""PostgreSQL SQLancer conversion, real replay/lifecycle and credential hygiene."""

import io
import json
import os
from contextlib import contextmanager
from pathlib import Path
import subprocess
import sys

import psycopg2
import pytest
from psycopg2.extensions import parse_dsn

from surprise.baselines import sqlancer_run as sq
from surprise.experiments import pg_instance as P
from surprise.harness.ledger import Ledger

DATA = Path(__file__).parent / "data" / "s16"
LOGS = DATA / "sqlancer"
FRAMEWORK = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name,kind,oracle,reason", [
    ("pg_norec_mismatch.log", "mismatch", "NOREC", None),
    ("pg_tlp_mismatch.log", "mismatch", "WHERE", None),
    ("pg_unexpected_error.log", "unexpected_error", None, "not_a_query"),
    ("pg_tool_error.log", "tool_error", None, "tool_error"),
])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_pg_classification(tmp_path, name, kind, oracle, reason, newline):
    path = tmp_path / name
    path.write_bytes((LOGS / name).read_text(encoding="utf-8").replace("\n", newline).encode())
    parsed = sq.parse_log(path, "postgres")
    assert parsed.row == {
        "log": name, "kind": kind, "sqlancer_oracle": oracle,
        "database_version": "16.15", "seed": 7,
        "oracle": {"NOREC": "norec", "WHERE": "tlp"}.get(oracle),
        "converted": reason is None, "reason": reason, "record_id": None,
    }
    if parsed.case:
        assert parsed.case.engine == "postgres"
        assert parsed.case.setup[0].startswith("CREATE TABLE t0")
        assert len(parsed.case.setup) == 4
        assert parsed.case.query == ("SELECT * FROM t0" if oracle == "NOREC" else "SELECT t0.c0 FROM t0")
        assert parsed.case.predicate == ("((t0.c0)>(1))" if oracle == "NOREC" else "(t0.c0) IS NOT NULL")


def test_pg_dialect_and_setup_boundaries(tmp_path):
    text = (LOGS / "pg_norec_mismatch.log").read_text(encoding="utf-8")
    predicate = "t0.c0::text ~ $$WHERE; FROM UNION$$ AND EXISTS (SELECT 1 WHERE TRUE)"
    text = text.replace("((t0.c0)>(1))", predicate)
    setup = ["DISCARD PLANS", "RESET ALL", "BEGIN", "ROLLBACK", "DROP TABLE other",
             "INSERT INTO t0 VALUES (4)", "SET LOCAL statement_timeout = 5000"]
    text += "\n" + ";\n".join(setup) + ";\n"
    path = tmp_path / "dialect.log"
    path.write_text(text, encoding="utf-8")
    case = sq.parse_log(path, "postgres").case
    assert case.query == "SELECT * FROM t0"
    assert case.predicate == predicate
    assert case.setup[4:] == tuple(setup)
    assert all(not statement.startswith(("\\", "CREATE DATABASE", "DROP DATABASE")) for statement in case.setup)


def test_duckdb_parser_output_unchanged():
    before = json.loads((DATA / "duckdb_sqlancer_before.json").read_text(encoding="utf-8"))
    for name, expected in before.items():
        path = DATA.parent / "sqlancer" / name
        for parsed in (sq.parse_log(path), sq.parse_log(path, "duckdb")):
            assert {"row": parsed.row, "case": parsed.case.to_dict() if parsed.case else None} == expected


def test_pg_cli_replay_certifies_and_cleans_up(tmp_path):
    out = tmp_path / "replay"
    env = {k: v for k, v in os.environ.items()
           if k.upper() not in ("DEEPSEEK_API_KEY", P.TARGET_DSN_ENV, P.OLD_DSN_ENV)}
    proc = subprocess.run([sys.executable, "-m", "surprise.baselines.sqlancer_run", "--out", str(out),
                           "--seed", "7", "--engine", "postgres", "--replay-logs", str(LOGS)],
                          cwd=FRAMEWORK, env=env, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout == "replayed None\n"
    report = json.loads((out / "report.json").read_text())
    assert report["engine"] == "postgres" and report["labels"] == {"pass": 2}
    stats = report["sqlancer"]
    assert stats["kinds"] == {"mismatch": 2, "unexpected_error": 1, "tool_error": 1}
    assert (stats["reports"], stats["converted"], stats["judged"], stats["unjudged"]) == (4, 2, 2, 0)
    assert stats["command"] is None and stats["pid"] is None
    assert "postgresql-42.5.1.jar" in stats["jdbc"]
    with Ledger(out / "ledger.sqlite") as ledger:
        manifest = ledger.run_manifest(report["run_id"])
        records = list(ledger.records(run_id=report["run_id"]))
    assert manifest["environment"]["engines"]["postgres"] == "16.15"
    assert manifest["environment"]["old_engines"]["postgres"] == "15.19"
    assert len(records) == 2
    for record in records:
        assert record.case.engine == "postgres" and record.purpose == "sqlancer"
        assert record.label.y == "pass" and record.label.invalid_reason is None
    assert P.stop_all(out) == []
    for kind in P.KINDS:
        assert not (out / "pg" / kind / "data").exists()
        assert not (out / "pg" / kind / "pgpass").exists()


def test_real_pg_run_command_entry_database_and_cleanup(tmp_path, monkeypatch):
    for name in (P.TARGET_DSN_ENV, P.OLD_DSN_ENV):
        monkeypatch.delenv(name, raising=False)
    original = sq._postgres_options
    credentials = []

    def inspect(dsn):
        options = original(dsn)
        # An existing entry database must also be accepted.
        assert original(dsn) == options
        credentials.append(options[-1])
        parsed = parse_dsn(dsn)
        assert options[:-1] == ["--host", "127.0.0.1", "--port", parsed["port"],
                               "--username", "coevo_target", "--password"]
        connection = psycopg2.connect(dsn)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = 'test'")
                assert cursor.fetchone() == ("coevo_target",)
        finally:
            connection.close()
        return options

    monkeypatch.setattr(sq, "_postgres_options", inspect)
    out = tmp_path / "live"
    report = sq.run(out, seed=7, engine="postgres", max_minutes=1)
    assert report["status"] == "budget_minutes"
    assert report["executions"] >= 1000
    command = report["sqlancer"]["command"]
    assert command[command.index("--password") + 1] == "<hidden>"
    assert command[command.index("postgres") + 1:] == ["--oracle", "NOREC", "--oracle", "WHERE"]
    assert "postgresql-42.5.1.jar" in report["sqlancer"]["jdbc"]
    assert P.stop_all(out) == []
    assert not list(out.rglob("pgpass")) and not list(out.rglob("postmaster.pid"))
    # Do not let a failing assertion itself disclose the generated credential.
    for path in out.rglob("*"):
        if path.is_file() and any(value.encode() in path.read_bytes() for value in credentials):
            raise AssertionError("a run artifact contains an unredacted credential")


def test_stdout_is_redacted_before_writing():
    destination = io.StringIO()
    sq._redact_stdout(io.StringIO("--password fixture-token\nExecuted 12 queries\n"), destination, "fixture-token")
    assert destination.getvalue() == "--password <hidden>\nExecuted 12 queries\n"


def test_java_startup_and_cleanup_errors_hide_credentials(tmp_path, monkeypatch):
    closed = []

    @contextmanager
    def instances(directory, *, old):
        assert directory == tmp_path / "out" / "pg" and old is True
        try:
            yield {"target": "fixture-dsn", "old": "fixture-old-dsn"}
        finally:
            closed.append(True)

    original_popen = sq.subprocess.Popen

    def fail_java(command, **kwargs):
        if "sqlancer.Main" in command:
            raise OSError("cannot launch --password fixture-token")
        return original_popen(command, **kwargs)

    def fail_cleanup(proc):
        assert proc is None
        raise RuntimeError("cleanup --password fixture-token")

    monkeypatch.setattr(P, "ensure", instances)
    monkeypatch.setattr(sq, "_postgres_options", lambda _: ["--password", "fixture-token"])
    monkeypatch.setattr(sq, "_postgres_versions", lambda *_: None)
    monkeypatch.setattr(sq.subprocess, "Popen", fail_java)
    monkeypatch.setattr(sq, "_stop_java", fail_cleanup)
    with pytest.raises(RuntimeError, match="cannot launch --password <hidden>"):
        sq.run(tmp_path / "out", seed=7, engine="postgres", max_minutes=1)
    assert closed == [True]
    error = (tmp_path / "out" / "error.txt").read_text()
    assert "fixture-token" not in error and "cleanup --password <hidden>" in error
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert report["status"] == "error"
    assert report["sqlancer"]["command"][-5:] == ["postgres", "--oracle", "NOREC", "--oracle", "WHERE"]
    assert "fixture-token" not in json.dumps(report)
