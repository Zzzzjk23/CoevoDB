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
_INTO = re.compile(r"\bINTO\b", re.IGNORECASE)
_CONNECTION_LOST = (
    "server closed the connection",
    "terminating connection",
    "connection not open",
    "could not receive data from server",
    "consuming input failed",
    "ssl connection has been closed",
)


def _ident_start(char: str) -> bool:
    return char.isalpha() or char == "_" or ord(char) > 127


def _ident_cont(char: str) -> bool:
    return _ident_start(char) or char.isdigit()


def _skip_trivia(sql: str, index: int) -> int | None:
    """Skip whitespace, line comments, and nested block comments. None if unclosed."""
    length = len(sql)
    while index < length:
        char = sql[index]
        nxt = sql[index + 1] if index + 1 < length else ""
        if char.isspace():
            index += 1
            continue
        if char == "-" and nxt == "-":
            index += 2
            while index < length and sql[index] != "\n":
                index += 1
            continue
        if char == "/" and nxt == "*":
            index += 2
            depth = 1
            while index < length and depth:
                here = sql[index]
                ahead = sql[index + 1] if index + 1 < length else ""
                if here == "/" and ahead == "*":
                    depth += 1
                    index += 2
                    continue
                if here == "*" and ahead == "/":
                    depth -= 1
                    index += 2
                    continue
                index += 1
            if depth:
                return None
            continue
        break
    return index


def _skip_quoted(sql: str, index: int, quote: str, *, escaped: bool) -> int | None:
    """Skip a '...', E'...', or \"...\" span. ``index`` is on the opening quote."""
    length = len(sql)
    index += 1
    while index < length:
        char = sql[index]
        if escaped and char == "\\":
            index += 2
            continue
        if char == quote:
            if index + 1 < length and sql[index + 1] == quote:
                index += 2
                continue
            return index + 1
        index += 1
    return None


def _try_skip_dollar(sql: str, index: int) -> int | None:
    """Skip a dollar-quoted span, or return ``index`` if this ``$`` is not a quote.

    None means the quote was opened and never closed. Dollar quotes are only
    recognised at a token boundary so ``foo$bar$baz`` stays one identifier.
    """
    if index > 0 and _ident_cont(sql[index - 1]):
        return index
    length = len(sql)
    cursor = index + 1
    if cursor < length and sql[cursor] == "$":
        tag = ""
        cursor += 1
    elif cursor < length and _ident_start(sql[cursor]):
        start = cursor
        cursor += 1
        while cursor < length and _ident_cont(sql[cursor]):
            cursor += 1
        if cursor >= length or sql[cursor] != "$":
            return index
        tag = sql[start:cursor]
        cursor += 1
    else:
        return index
    close = "$" + tag + "$"
    found = sql.find(close, cursor)
    if found < 0:
        return None
    return found + len(close)


def _prefixed_quote(sql: str, index: int) -> tuple[int, str, bool] | None:
    """Return (quote_index, quote_char, escaped) for E'...' / U&'...' / U&\"...\"."""
    length = len(sql)
    if index > 0 and _ident_cont(sql[index - 1]):
        return None
    if index + 1 < length and sql[index] in "Ee" and sql[index + 1] == "'":
        return (index + 1, "'", True)
    if (
        index + 2 < length
        and sql[index] in "Uu"
        and sql[index + 1] == "&"
        and sql[index + 2] in "'\""
    ):
        return (index + 2, sql[index + 2], True)
    return None


def _skip_atom(sql: str, index: int) -> int | None:
    """Advance over trivia, a quoted span, or one character. None if unclosed."""
    skipped = _skip_trivia(sql, index)
    if skipped is None:
        return None
    if skipped > index:
        return skipped
    length = len(sql)
    if index >= length:
        return index
    prefixed = _prefixed_quote(sql, index)
    if prefixed is not None:
        quote_at, quote, escaped = prefixed
        return _skip_quoted(sql, quote_at, quote, escaped=escaped)
    char = sql[index]
    if char == "'":
        return _skip_quoted(sql, index, "'", escaped=False)
    if char == '"':
        return _skip_quoted(sql, index, '"', escaped=False)
    if char == "$":
        end = _try_skip_dollar(sql, index)
        if end is None:
            return None
        if end > index:
            return end
    return index + 1


def _split_statements(sql: str) -> list[str] | None:
    """Top-level statements. None if the text cannot be scanned conservatively.

    One trailing semicolon is allowed. A second executable statement, an empty
    statement, or an unclosed quote/comment is rejected rather than inspected
    only up to the first semicolon.
    """
    length = len(sql)
    index = 0
    parts: list[str] = []
    while True:
        index = _skip_trivia(sql, index)
        if index is None:
            return None
        if index >= length:
            return parts
        if sql[index] == ";":
            return None
        start = index
        while index < length and sql[index] != ";":
            nxt = _skip_atom(sql, index)
            if nxt is None:
                return None
            if nxt == index:
                break
            index = nxt
        parts.append(sql[start:index])
        if index >= length:
            return parts
        if sql[index] != ";":
            return None
        index += 1


def _code_mask(sql: str) -> str | None:
    """Replace comments and quoted spans with spaces so keyword searches see code."""
    out: list[str] = []
    index = 0
    length = len(sql)
    while index < length:
        skipped = _skip_trivia(sql, index)
        if skipped is None:
            return None
        if skipped > index:
            out.append(" " * (skipped - index))
            index = skipped
            continue
        if sql[index] == ";":
            out.append(";")
            index += 1
            continue
        nxt = _skip_atom(sql, index)
        if nxt is None:
            return None
        if nxt > index + 1 or (nxt == index + 1 and sql[index] in "'\"$"):
            out.append(" " * (nxt - index))
            index = nxt
            continue
        out.append(sql[index])
        index += 1
    return "".join(out)


def _leading_keyword(statement: str) -> str:
    index = _skip_trivia(statement, 0)
    if index is None or index >= len(statement) or not _ident_start(statement[index]):
        return ""
    end = index + 1
    while end < len(statement) and _ident_cont(statement[end]):
        end += 1
    return statement[index:end].upper()


def is_readonly_query(statement: str) -> bool:
    """True for one read-only SELECT-shaped statement and nothing after it.

    A second executable statement is rejected before any runner sees the text.
    Quotes, nested comments, and dollar quotes are not statement separators.
    Unscanable input is rejected.
    """
    parts = _split_statements(statement)
    if parts is None or len(parts) != 1:
        return False
    code = _code_mask(parts[0])
    if code is None:
        return False
    head = _leading_keyword(parts[0])
    if head not in _ALLOWED_HEADS:
        return False
    if _MUTATING.search(code):
        return False
    if head == "SELECT" and _INTO.search(code):
        return False
    return True


def _setup_rejection(statement: str) -> str | None:
    """Why this setup element must not reach the backend, or None to execute it."""
    parts = _split_statements(statement)
    if parts is None:
        return "NotApplicable: statement could not be scanned"
    if not parts:
        return None
    if len(parts) != 1:
        return "NotApplicable: multiple statements"
    if _leading_keyword(parts[0]) in _TX_CONTROL:
        return "NotApplicable: transaction control is rejected"
    return None


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
            rejection = _setup_rejection(statement)
            if rejection is not None:
                outcomes.append((statement, rejection))
                continue
            parts = _split_statements(statement)
            if not parts:
                continue
            result = self._execute(parts[0], timeout_ms=_SETUP_TIMEOUT_MS, fetch=False)
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
