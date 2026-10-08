"""PostgreSQL reference runner for cross-engine comparison.

Each runner keeps an uncommitted transaction and a private schema. ``close``
rolls that transaction back, so tables and the schema never become visible to
other connections. This is not a PostgreSQL target engine.
"""

from __future__ import annotations

import os
import re
import time
import uuid
from typing import Iterable

import psycopg2
from psycopg2 import sql

from oracles.db_runner import QueryResult
from oracles.normalize import is_internal_error, normalize_rows

_DEFAULT_DSN = (
    "host=127.0.0.1 port=55432 user=coevo dbname=postgres connect_timeout=5"
)
_SCHEMA_PREFIX = "coevo_ref_"
_SAVEPOINT = "coevo_ref_sp"
_SETUP_TIMEOUT_MS = 10_000

_ALLOWED_HEADS = frozenset({"SELECT", "WITH", "VALUES", "TABLE"})
_TX_CONTROL = frozenset({
    "COMMIT", "ROLLBACK", "ABORT", "BEGIN", "START", "END", "SAVEPOINT", "RELEASE",
})
_MUTATING = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|"
    r"COPY|CALL|DO|VACUUM|ANALYZE|CLUSTER|REINDEX|COMMENT|REFRESH|REPLACE|"
    r"COMMIT|ROLLBACK|ABORT|BEGIN|SAVEPOINT|RELEASE)\b",
    re.IGNORECASE,
)
_CONNECTION_LOST = (
    "server closed the connection",
    "terminating connection",
    "connection not open",
    "could not receive data from server",
    "consuming input failed",
    "ssl connection has been closed",
)


def _scrub_sql(statement: str) -> str:
    """Drop comments and string literals so keyword checks see the statement shape."""
    out: list[str] = []
    index = 0
    length = len(statement)
    while index < length:
        char = statement[index]
        nxt = statement[index + 1] if index + 1 < length else ""
        if char == "-" and nxt == "-":
            index += 2
            while index < length and statement[index] != "\n":
                index += 1
            out.append(" ")
            continue
        if char == "/" and nxt == "*":
            index += 2
            while index + 1 < length and not (
                statement[index] == "*" and statement[index + 1] == "/"
            ):
                index += 1
            index = min(length, index + 2)
            out.append(" ")
            continue
        if char == "'":
            index += 1
            while index < length:
                if statement[index] == "'":
                    if index + 1 < length and statement[index + 1] == "'":
                        index += 2
                        continue
                    index += 1
                    break
                index += 1
            out.append(" '' ")
            continue
        out.append(char)
        index += 1
    return "".join(out)


def _statement_text(statement: str) -> str:
    text = _scrub_sql(statement).strip()
    while text.endswith(";"):
        text = text[:-1].strip()
    return text


def _leading_keyword(statement: str) -> str:
    match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", _statement_text(statement))
    if match is None:
        return ""
    return match.group(1).upper()


def is_readonly_query(statement: str) -> bool:
    """True for a single read-only SELECT shape.

    ``SELECT INTO``, data-modifying CTEs, and transaction control are rejected.
    String literals are ignored, so a quoted word cannot change the decision.
    """
    text = _statement_text(statement)
    if not text:
        return False
    head = _leading_keyword(text)
    if head not in _ALLOWED_HEADS:
        return False
    if _MUTATING.search(text):
        return False
    if head == "SELECT" and re.search(r"\bINTO\b", text, re.IGNORECASE):
        return False
    return True


def _resolve_dsn(dsn: str | None) -> str:
    if dsn is not None:
        return dsn
    env = os.environ.get("COEVO_REFERENCE_PG_DSN")
    if env:
        return env
    return _DEFAULT_DSN


class PostgresReferenceRunner:
    """One uncommitted PostgreSQL session used as an independent reference."""

    def __init__(self, dsn: str | None = None):
        self._dsn = _resolve_dsn(dsn)
        self._conn: psycopg2.extensions.connection | None = None
        self._schema: str | None = None
        self._version: str | None = None

    def __repr__(self) -> str:
        return "PostgresReferenceRunner(<dsn hidden>)"

    @property
    def engine_version(self) -> str:
        self._ensure_connection()
        return self._version or "unknown"

    def setup(self, schema_sqls: Iterable[str]) -> list[tuple[str, str | None]]:
        """Roll back any previous case and apply ``schema_sqls`` in a new transaction."""
        self._reset()
        outcomes: list[tuple[str, str | None]] = []
        for statement in schema_sqls:
            text = statement.strip().rstrip(";")
            if not text:
                continue
            if _leading_keyword(text) in _TX_CONTROL:
                outcomes.append((statement, "NotApplicable: transaction control is rejected"))
                continue
            result = self._execute(text, timeout_ms=_SETUP_TIMEOUT_MS, fetch=False)
            outcomes.append((statement, result.error))
            if self._schema is None:
                break
        return outcomes

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        """Run one read-only statement. State-changing SQL is refused unexecuted."""
        if not is_readonly_query(sql):
            return QueryResult(error="NotApplicable: state-changing or non-SELECT statement")
        if self._schema is None:
            self._reset()
        timeout_ms = max(1, int(round(float(timeout_s) * 1000)))
        return self._execute(sql, timeout_ms=timeout_ms, fetch=True)

    def close(self) -> None:
        """Roll the session back and drop the connection. A second call does nothing."""
        conn = self._conn
        self._conn = None
        self._schema = None
        if conn is None:
            return
        try:
            if conn.closed == 0:
                try:
                    conn.rollback()
                except Exception:
                    pass
                conn.close()
        except Exception:
            pass

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def _ensure_connection(self) -> None:
        if self._conn is not None and self._conn.closed == 0:
            return
        try:
            self._conn = psycopg2.connect(self._dsn)
        except Exception as exc:
            self._conn = None
            raise self._connection_failure(exc) from None
        self._conn.autocommit = False
        try:
            cursor = self._conn.cursor()
            cursor.execute("SHOW server_version")
            row = cursor.fetchone()
            self._version = str(row[0]) if row else "unknown"
            self._conn.rollback()
        except Exception:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
            raise

    def _connection_failure(self, exc: BaseException) -> ConnectionError:
        # The override DSN may contain a password. Keep it out of the message.
        name = type(exc).__name__
        code = getattr(exc, "pgcode", None)
        suffix = f" {code}" if code else ""
        return ConnectionError(f"PostgreSQL reference connection failed ({name}{suffix})")

    def _reconnect(self) -> None:
        self.close()
        self._ensure_connection()

    def _reset(self) -> None:
        self._ensure_connection()
        assert self._conn is not None
        try:
            self._conn.rollback()
        except Exception:
            self._reconnect()
            assert self._conn is not None
            self._conn.rollback()
        self._schema = None
        schema = _SCHEMA_PREFIX + uuid.uuid4().hex
        cursor = self._conn.cursor()
        cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        self._schema = schema

    def _execute(self, statement: str, *, timeout_ms: int, fetch: bool) -> QueryResult:
        result = QueryResult()
        started = time.monotonic()
        try:
            if self._schema is None or self._conn is None or self._conn.closed != 0:
                result.error = "OperationalError: PostgreSQL reference session is closed"
                result.is_internal_error = True
                return result
            cursor = self._conn.cursor()
            cursor.execute(sql.SQL("SAVEPOINT {}").format(sql.Identifier(_SAVEPOINT)))
            cursor.execute(
                sql.SQL("SET LOCAL statement_timeout = {}").format(sql.Literal(int(timeout_ms)))
            )
            cursor.execute(statement)
            if fetch and cursor.description is not None:
                result.rows = normalize_rows(cursor.fetchall())
                result.columns = [desc.name for desc in cursor.description]
            cursor.execute(sql.SQL("RELEASE SAVEPOINT {}").format(sql.Identifier(_SAVEPOINT)))
        except Exception as exc:
            self._recover()
            message = self._public_error(exc)
            result.error = message
            result.timed_out = _is_statement_timeout(exc)
            result.is_internal_error = _is_engine_internal(exc, message)
            if result.is_internal_error and _connection_lost(message):
                self._conn = None
                self._schema = None
        finally:
            result.elapsed = time.monotonic() - started
        return result

    def _recover(self) -> None:
        if self._conn is None or self._conn.closed != 0:
            self._schema = None
            return
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                sql.SQL("ROLLBACK TO SAVEPOINT {}").format(sql.Identifier(_SAVEPOINT))
            )
        except Exception:
            try:
                self._conn.rollback()
            except Exception:
                self._conn = None
            self._schema = None

    def _public_error(self, exc: BaseException) -> str:
        text = f"{type(exc).__name__}: {exc}"
        if self._dsn and self._dsn in text:
            text = text.replace(self._dsn, "<dsn>")
        text = re.sub(r"(?i)(password\s*=\s*)\S+", r"\1<hidden>", text)
        if self._schema:
            text = text.replace(self._schema, "coevo_ref")
        return text


def _is_statement_timeout(exc: BaseException) -> bool:
    if "statement timeout" in str(exc).lower():
        return True
    return getattr(exc, "pgcode", None) == "57014" and "timeout" in str(exc).lower()


def _connection_lost(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in _CONNECTION_LOST)


def _is_engine_internal(exc: BaseException, message: str) -> bool:
    if is_internal_error(message) or is_internal_error(str(exc)):
        return True
    return _connection_lost(message)
