"""Append-only SQLite ledger of experiment records.

Rows are committed before :meth:`Ledger.append` and :meth:`Ledger.start_run`
return, so another connection can read them immediately and a crash afterwards
does not drop them. The ledger stores ``SCHEMA_VERSION`` and refuses a file
written by a different version.
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any

from .contracts import LABELS, SCHEMA_VERSION, ExperimentRecord

_SCHEMA = """
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    created_order INTEGER NOT NULL UNIQUE,
    manifest_json TEXT NOT NULL
);
CREATE TABLE records (
    record_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    oracle TEXT NOT NULL,
    y TEXT NOT NULL,
    theory_version TEXT,
    purpose TEXT NOT NULL,
    created_at TEXT NOT NULL,
    record_json TEXT NOT NULL,
    UNIQUE (run_id, seq),
    FOREIGN KEY (run_id) REFERENCES runs (run_id)
);
CREATE INDEX idx_records_run_id ON records (run_id);
CREATE INDEX idx_records_seq ON records (seq);
CREATE INDEX idx_records_oracle ON records (oracle);
CREATE INDEX idx_records_y ON records (y);
CREATE INDEX idx_records_theory_version ON records (theory_version);
CREATE INDEX idx_records_purpose ON records (purpose);
CREATE INDEX idx_records_created_at ON records (created_at);
"""

_REQUIRED_TABLES = frozenset({"meta", "runs", "records"})


class LedgerError(Exception):
    """A ledger read or append was rejected. A rejected append leaves no row."""


class Ledger:
    """An append-only experiment ledger backed by one SQLite file."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = path
        self._conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(os.fspath(path), isolation_level=None, timeout=30.0)
        except sqlite3.Error as exc:
            raise LedgerError(f"cannot open ledger {path!r}: {exc}") from exc
        self._conn = conn
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA synchronous = FULL")
            self._prepare()
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        conn = self._conn
        self._conn = None
        if conn is not None:
            conn.close()

    def __enter__(self) -> Ledger:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def start_run(self, run_id: str, manifest: dict) -> None:
        if not isinstance(run_id, str) or run_id == "":
            raise LedgerError(f"run_id: must be a non-empty string, got {run_id!r}")
        blob = _dump_manifest(manifest)

        def body() -> None:
            if self._fetchone("SELECT 1 FROM runs WHERE run_id = ?", (run_id,)) is not None:
                raise LedgerError(f"run_id: already exists: {run_id!r}")
            row = self._fetchone("SELECT COALESCE(MAX(created_order), 0) FROM runs")
            created_order = int(row[0]) + 1
            self._execute(
                "INSERT INTO runs (run_id, created_order, manifest_json) VALUES (?, ?, ?)",
                (run_id, created_order, blob),
            )

        self._in_transaction(body)

    def run_manifest(self, run_id: str) -> dict:
        row = self._fetchone("SELECT manifest_json FROM runs WHERE run_id = ?", (run_id,))
        if row is None:
            raise LedgerError(f"run_id: does not exist: {run_id!r}")
        data = json.loads(row[0])
        if not isinstance(data, dict):
            raise LedgerError(f"run_id: stored manifest is not a JSON object: {run_id!r}")
        return data

    def run_ids(self) -> list[str]:
        rows = self._fetchall("SELECT run_id FROM runs ORDER BY created_order")
        return [row[0] for row in rows]

    def next_seq(self, run_id: str) -> int:
        if self._fetchone("SELECT 1 FROM runs WHERE run_id = ?", (run_id,)) is None:
            raise LedgerError(f"run_id: does not exist: {run_id!r}")
        row = self._fetchone("SELECT MAX(seq) FROM records WHERE run_id = ?", (run_id,))
        if row[0] is None:
            return 1
        return int(row[0]) + 1

    def append(self, record: ExperimentRecord) -> None:
        if not isinstance(record, ExperimentRecord):
            raise LedgerError(f"record: expected ExperimentRecord, got {record!r}")
        payload = record.to_json()

        def body() -> None:
            if self._fetchone("SELECT 1 FROM runs WHERE run_id = ?", (record.run_id,)) is None:
                raise LedgerError(f"run_id: was not started: {record.run_id!r}")
            if (
                self._fetchone("SELECT 1 FROM records WHERE record_id = ?", (record.record_id,))
                is not None
            ):
                raise LedgerError(f"record_id: already exists: {record.record_id!r}")
            if (
                self._fetchone(
                    "SELECT 1 FROM records WHERE run_id = ? AND seq = ?",
                    (record.run_id, record.seq),
                )
                is not None
            ):
                raise LedgerError(
                    f"seq: already exists in run {record.run_id!r}: {record.seq!r}"
                )
            self._execute(
                """
                INSERT INTO records (
                    record_id, run_id, seq, oracle, y, theory_version, purpose, created_at,
                    record_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.record_id,
                    record.run_id,
                    record.seq,
                    record.label.oracle,
                    record.label.y,
                    record.theory_version,
                    record.purpose,
                    record.created_at,
                    payload,
                ),
            )

        self._in_transaction(body)

    def records(
        self,
        *,
        run_id: str | None = None,
        theory_version: str | None = None,
        y: str | None = None,
        oracle: str | None = None,
    ) -> list[ExperimentRecord]:
        where, params = _filters(run_id, theory_version, y, oracle, prefix="records.")
        rows = self._fetchall(
            "SELECT records.record_json FROM records "
            "JOIN runs ON runs.run_id = records.run_id"
            f"{where} ORDER BY runs.created_order, records.seq",
            params,
        )
        return [ExperimentRecord.from_json(row[0]) for row in rows]

    def count(
        self,
        *,
        run_id: str | None = None,
        theory_version: str | None = None,
        y: str | None = None,
        oracle: str | None = None,
    ) -> int:
        where, params = _filters(run_id, theory_version, y, oracle)
        row = self._fetchone(f"SELECT COUNT(*) FROM records{where}", params)
        return int(row[0])

    def label_counts(
        self,
        *,
        run_id: str | None = None,
        theory_version: str | None = None,
    ) -> dict[str, int]:
        where, params = _filters(run_id, theory_version, None, None)
        rows = self._fetchall(f"SELECT y, COUNT(*) FROM records{where} GROUP BY y", params)
        counts = {label: 0 for label in LABELS}
        for label, total in rows:
            if label in counts:
                counts[label] = int(total)
        return counts

    def _prepare(self) -> None:
        names = self._table_names()
        if not names:
            self._create_schema()
            return
        missing = _REQUIRED_TABLES - names
        if missing:
            raise LedgerError(f"schema: not a surprise ledger, missing tables {sorted(missing)}")
        self._require_current_version()

    def _create_schema(self) -> None:
        version = int(SCHEMA_VERSION)
        assert self._conn is not None
        self._conn.executescript(
            _SCHEMA + "INSERT INTO meta (key, value) VALUES ('schema_version', '%d');\n" % version
        )
        self._require_current_version()

    def _require_current_version(self) -> None:
        row = self._fetchone("SELECT value FROM meta WHERE key = 'schema_version'")
        if row is None:
            raise LedgerError("schema_version: missing from the ledger")
        raw = row[0]
        try:
            found = int(raw)
        except (TypeError, ValueError) as exc:
            raise LedgerError(f"schema_version: not an integer: {raw!r}") from exc
        if found != SCHEMA_VERSION:
            raise LedgerError(
                f"schema_version: ledger has {found}, this code expects {SCHEMA_VERSION}"
            )

    def _table_names(self) -> set[str]:
        rows = self._fetchall(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
        return {row[0] for row in rows}

    def _require_open(self) -> sqlite3.Connection:
        if self._conn is None:
            raise LedgerError("ledger is closed")
        return self._conn

    def _fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        cursor = self._require_open().execute(sql, params)
        try:
            return cursor.fetchone()
        finally:
            cursor.close()

    def _fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
        cursor = self._require_open().execute(sql, params)
        try:
            return cursor.fetchall()
        finally:
            cursor.close()

    def _execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        cursor = self._require_open().execute(sql, params)
        cursor.close()

    def _rollback(self) -> None:
        conn = self._conn
        if conn is None:
            return
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass

    def _in_transaction(self, body: Any) -> None:
        # Commit before returning so a second connection, and a later crash, both see the write.
        conn = self._require_open()
        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.Error as exc:
            raise LedgerError(f"cannot begin transaction: {exc}") from exc
        try:
            body()
        except LedgerError:
            self._rollback()
            raise
        except Exception as exc:
            self._rollback()
            raise LedgerError(f"ledger write failed: {exc}") from exc
        try:
            conn.execute("COMMIT")
        except sqlite3.Error as exc:
            self._rollback()
            raise LedgerError(f"commit failed: {exc}") from exc


def _dump_manifest(manifest: Any) -> str:
    if not isinstance(manifest, dict):
        raise LedgerError(f"manifest: expected a JSON object, got {manifest!r}")
    try:
        return json.dumps(manifest, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise LedgerError(f"manifest: not JSON-safe: {manifest!r}") from exc


def _filters(
    run_id: str | None,
    theory_version: str | None,
    y: str | None,
    oracle: str | None,
    *,
    prefix: str = "",
) -> tuple[str, tuple[Any, ...]]:
    clauses: list[str] = []
    params: list[Any] = []
    for column, value in (
        ("run_id", run_id),
        ("theory_version", theory_version),
        ("y", y),
        ("oracle", oracle),
    ):
        if value is not None:
            clauses.append(f"{prefix}{column} = ?")
            params.append(value)
    if not clauses:
        return "", tuple(params)
    return " WHERE " + " AND ".join(clauses), tuple(params)
