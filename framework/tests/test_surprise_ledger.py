"""Append-only SQLite ledger: filters, order, rejection, and reopen."""

from __future__ import annotations

import sqlite3
from dataclasses import replace

import pytest

from surprise.harness.contracts import SCHEMA_VERSION, ExperimentRecord, Label, SqlCase
from surprise.harness.ledger import Ledger, LedgerError

_MUTATORS = ("delete", "update", "remove", "clear", "truncate")


def _case() -> SqlCase:
    return SqlCase(
        engine="duckdb",
        setup=("CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1)"),
        query="SELECT a FROM t WHERE a > 0",
        predicate="a > 0",
    )


def _record(
    record_id: str,
    run_id: str,
    seq: int,
    *,
    oracle: str = "tlp",
    y: str = "pass",
    theory_version: str | None = None,
    purpose: str = "explore",
) -> ExperimentRecord:
    if y == "fail":
        label = Label(y="fail", oracle=oracle, fail_kind="wrong_result")
    elif y == "invalid":
        label = Label(y="invalid", oracle=oracle, invalid_reason="not_applicable")
    else:
        label = Label(y="pass", oracle=oracle)
    return ExperimentRecord(
        record_id=record_id,
        run_id=run_id,
        seq=seq,
        case=_case(),
        label=label,
        purpose=purpose,
        created_at=f"2026-10-08T12:00:0{seq}+00:00",
        theory_version=theory_version,
        spec={"engine": "duckdb", "oracle": oracle} if seq == 1 else None,
        phi={"ast": ["SELECT"]} if y == "fail" else None,
        p_t=0.5 if y == "fail" else None,
        surprise=1.0 if y == "fail" else None,
    )


def _open_populated(path):
    """run-b is created before run-a. Append order is not creation-then-seq order."""
    ledger = Ledger(path)
    ledger.start_run("run-b", {"note": "第二", "flags": ["a", "b"]})
    ledger.start_run("run-a", {"note": "first", "n": 1})
    rows = [
        _record("b2", "run-b", 2, oracle="norec", y="fail", theory_version="T0"),
        _record("a3", "run-a", 3, oracle="plan_variant", y="pass", theory_version=None),
        _record("b1", "run-b", 1, oracle="tlp", y="pass", theory_version="T0"),
        _record("a1", "run-a", 1, oracle="tlp", y="invalid", theory_version="T1"),
        _record("a2", "run-a", 2, oracle="norec", y="invalid", theory_version="T1", purpose="confirm"),
    ]
    for row in rows:
        ledger.append(row)
    ordered = [
        _record("b1", "run-b", 1, oracle="tlp", y="pass", theory_version="T0"),
        _record("b2", "run-b", 2, oracle="norec", y="fail", theory_version="T0"),
        _record("a1", "run-a", 1, oracle="tlp", y="invalid", theory_version="T1"),
        _record("a2", "run-a", 2, oracle="norec", y="invalid", theory_version="T1", purpose="confirm"),
        _record("a3", "run-a", 3, oracle="plan_variant", y="pass", theory_version=None),
    ]
    return ledger, ordered


def test_write_filter_order_and_counts(tmp_path):
    path = tmp_path / "ledger.sqlite"
    ledger, ordered = _open_populated(path)
    try:
        assert ledger.run_ids() == ["run-b", "run-a"]
        assert ledger.run_manifest("run-a") == {"note": "first", "n": 1}
        assert ledger.run_manifest("run-b") == {"note": "第二", "flags": ["a", "b"]}
        seen = ledger.run_manifest("run-a")
        seen["n"] = 99
        assert ledger.run_manifest("run-a") == {"note": "first", "n": 1}

        assert ledger.next_seq("run-b") == 3
        assert ledger.next_seq("run-a") == 4
        empty = Ledger(path)
        try:
            empty.start_run("run-c", {})
            assert empty.next_seq("run-c") == 1
        finally:
            empty.close()

        assert ledger.records() == ordered
        assert ledger.count() == 5
        assert ledger.records(run_id="run-a") == ordered[2:]
        assert ledger.count(run_id="run-a") == 3
        assert ledger.records(theory_version="T1") == ordered[2:4]
        assert ledger.count(theory_version="T1") == 2
        assert ledger.records(y="fail") == ordered[1:2]
        assert ledger.count(y="fail") == 1
        assert ledger.records(oracle="tlp") == [ordered[0], ordered[2]]
        assert ledger.count(oracle="tlp") == 2
        assert ledger.records(run_id="run-a", y="pass") == ordered[4:]
        assert ledger.count(run_id="run-a", y="pass") == 1
        assert ledger.records(theory_version="T0", oracle="norec") == ordered[1:2]
        assert ledger.records(run_id="run-a", theory_version="T1", y="invalid", oracle="norec") == [
            ordered[3]
        ]
        assert ledger.count(run_id="run-a", theory_version="T1", y="invalid", oracle="norec") == 1
        assert any(row.theory_version is None for row in ledger.records())
        assert all(row.theory_version == "T1" for row in ledger.records(theory_version="T1"))

        assert ledger.label_counts() == {"pass": 2, "fail": 1, "invalid": 2}
        assert ledger.label_counts(run_id="run-a") == {"pass": 1, "fail": 0, "invalid": 2}
        assert ledger.label_counts(theory_version="T0") == {"pass": 1, "fail": 1, "invalid": 0}
        assert ledger.records(run_id="missing") == []
        assert ledger.label_counts(run_id="missing") == {"pass": 0, "fail": 0, "invalid": 0}
    finally:
        ledger.close()


def test_rejected_writes_leave_no_row(tmp_path):
    path = tmp_path / "ledger.sqlite"
    ledger, ordered = _open_populated(path)
    try:
        duplicate = ordered[0]
        other_run = replace(duplicate, run_id="run-a", seq=9, record_id=duplicate.record_id)
        same_seq = replace(ordered[2], record_id="a-extra")
        orphan = replace(ordered[0], record_id="orphan", run_id="never", seq=1)
        before = ledger.count()
        runs_before = ledger.run_ids()
        for call in (
            lambda: ledger.append(duplicate),
            lambda: ledger.append(other_run),
            lambda: ledger.append(same_seq),
            lambda: ledger.append(orphan),
            lambda: ledger.append("not a record"),
            lambda: ledger.start_run("run-a", {}),
            lambda: ledger.start_run("", {}),
            lambda: ledger.start_run("run-z", ["not", "an", "object"]),
            lambda: ledger.run_manifest("missing"),
            lambda: ledger.next_seq("missing"),
        ):
            with pytest.raises(LedgerError):
                call()
            assert ledger.count() == before
            assert ledger.run_ids() == runs_before
            assert ledger.records() == ordered
    finally:
        ledger.close()


def test_second_connection_sees_a_committed_append(tmp_path):
    path = tmp_path / "ledger.sqlite"
    ledger = Ledger(path)
    other = None
    try:
        ledger.start_run("run-a", {"k": "v"})
        other = Ledger(path)
        assert other.records() == []
        row = _record("a1", "run-a", 1, y="pass", theory_version="T0")
        ledger.append(row)
        assert other.records() == [row]
        assert other.run_manifest("run-a") == {"k": "v"}
        assert other.count() == 1
    finally:
        if other is not None:
            other.close()
        ledger.close()


def test_reopen_keeps_records_and_manifests(tmp_path):
    path = tmp_path / "ledger.sqlite"
    ledger, ordered = _open_populated(path)
    ledger.close()
    reopened = Ledger(path)
    try:
        assert reopened.records() == ordered
        assert reopened.run_manifest("run-b") == {"note": "第二", "flags": ["a", "b"]}
        assert reopened.run_ids() == ["run-b", "run-a"]
        assert reopened.label_counts() == {"pass": 2, "fail": 1, "invalid": 2}
    finally:
        reopened.close()


def test_close_releases_the_file_and_is_idempotent(tmp_path):
    path = tmp_path / "ledger.sqlite"
    with Ledger(path) as ledger:
        ledger.start_run("run-a", {})
        assert not any(hasattr(ledger, name) for name in _MUTATORS)
        assert not any(hasattr(Ledger, name) for name in _MUTATORS)
    ledger.close()
    path.unlink()
    assert not path.exists()


def test_schema_version_mismatch_is_rejected(tmp_path):
    path = tmp_path / "ledger.sqlite"
    ledger = Ledger(path)
    ledger.start_run("run-a", {"n": 1})
    ledger.close()

    conn = sqlite3.connect(path)
    try:
        found = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        assert found == (str(SCHEMA_VERSION),)
        conn.execute("UPDATE meta SET value = '99' WHERE key = 'schema_version'")
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(LedgerError) as caught:
        Ledger(path)
    assert "99" in str(caught.value)
    assert str(SCHEMA_VERSION) in str(caught.value)
    path.unlink()
    assert not path.exists()


def test_a_foreign_sqlite_file_is_rejected_and_unlocked(tmp_path):
    path = tmp_path / "other.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE notes (body TEXT)")
    conn.commit()
    conn.close()
    with pytest.raises(LedgerError):
        Ledger(path)
    path.unlink()
    assert not path.exists()


def test_methods_after_close_raise(tmp_path):
    path = tmp_path / "ledger.sqlite"
    ledger = Ledger(path)
    ledger.close()
    row = _record("a1", "run-a", 1)
    for call in (
        lambda: ledger.start_run("run-a", {}),
        lambda: ledger.append(row),
        lambda: ledger.records(),
        lambda: ledger.count(),
        lambda: ledger.label_counts(),
        lambda: ledger.run_ids(),
        lambda: ledger.run_manifest("run-a"),
        lambda: ledger.next_seq("run-a"),
    ):
        with pytest.raises(LedgerError):
            call()
