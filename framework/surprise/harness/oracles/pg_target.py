"""Autocommitted PostgreSQL target execution in a runner-owned schema."""

from __future__ import annotations

import os
import re
import threading
import time
import uuid
from collections.abc import Iterable

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import parse_dsn

from oracles.db_runner import QueryResult
from oracles.normalize import is_internal_error, normalize_rows
from .pg_reference import (
    _code_mask, _connection_lost, _ident_cont, _ident_start,
    _is_statement_timeout, _skip_atom, _skip_trivia, _split_statements,
)

TARGET_DSN_ENV = "COEVO_TARGET_PG_DSN"
OLD_DSN_ENV = "COEVO_OLD_PG_DSN"
_TRANSACTIONS = {"BEGIN", "START", "COMMIT", "END", "ROLLBACK", "ABORT",
                 "SAVEPOINT", "RELEASE"}
_CONNECT_RETRY_S = 30.0
_CONNECT_RETRY_DELAY_S = 0.5


def _authentication_failed(exc: psycopg2.OperationalError) -> bool:
    # libpq startup failures often have no SQLSTATE; also inspect its message.
    return bool((exc.pgcode or "").startswith("28") or any(marker in str(exc).lower() for marker in (
        "authentication failed", "no password supplied", "no pg_hba.conf entry",
        "pg_hba.conf rejects connection",
    )))


def _tokens(statement: str) -> list[str]:
    """Lexical atoms, preserving quoted identifiers while ignoring comments."""
    tokens = []
    index = 0
    while index < len(statement):
        index = _skip_trivia(statement, index)
        if index is None or index >= len(statement):
            break
        end = _skip_atom(statement, index)
        if end is None:
            break
        if end == index + 1 and _ident_start(statement[index]):
            while end < len(statement) and _ident_cont(statement[end]):
                end += 1
        tokens.append(statement[index:end])
        index = end
    return tokens


def _rejection(statement: str) -> str | None:
    parts = _split_statements(statement)
    if parts is None or len(parts) != 1:
        return "NotApplicable: expected one scannable statement"
    tokens = [token.strip('"').upper() for token in _tokens(parts[0])]
    head = tokens[0] if tokens else ""
    if head in _TRANSACTIONS or tokens[:2] == ["PREPARE", "TRANSACTION"]:
        return "NotApplicable: transaction control is rejected"
    if head == "DISCARD":
        return "NotApplicable: session isolation must be preserved"
    if head in {"SET", "RESET"}:
        rest = tokens[1:]
        if rest and rest[0] in {"SESSION", "LOCAL"}:
            rest = rest[1:]
        if rest and rest[0] in {"SEARCH_PATH", "ROLE", "AUTHORIZATION", "ALL"}:
            return "NotApplicable: session isolation must be preserved"
    return None


def _session_object(statement: str) -> bool:
    code = _code_mask(statement) or ""
    return bool(re.match(r"\s*(PREPARE|DECLARE|LISTEN)\b", code, re.I) or
                re.match(r"\s*CREATE\s+(?:GLOBAL\s+|LOCAL\s+)?TEMP(?:ORARY)?\b", code, re.I))


def _setting(statement: str) -> str | None:
    tokens = _tokens(statement)
    upper = [item.upper() for item in tokens]
    if not upper or upper[0] != "SET":
        return None
    index = 2 if len(upper) > 1 and upper[1] == "SESSION" else 1
    if len(tokens) <= index + 2 or upper[index] == "LOCAL":
        return None
    if upper[index + 1] not in {"=", "TO"} or upper[index + 2] == "DEFAULT":
        return None
    return tokens[index].strip('"').replace('""', '"')


def _option_atom(value: str) -> str:
    return "".join("\\" + char if char.isspace() or char == "\\" else char for char in value)


class PostgresTargetRunner:
    def __init__(self, dsn: str | None = None, *, env: str = TARGET_DSN_ENV) -> None:
        self._dsn = os.environ.get(env) if dsn is None else dsn
        if not self._dsn:
            raise ConnectionError(f"PostgreSQL target requires {env}")
        self._conn = None
        self._schema: str | None = None
        self._options = ""
        self._lost = False

    def __repr__(self) -> str:
        return "PostgresTargetRunner()"

    def _connect(self):
        if self._conn is None or self._conn.closed or self._lost:
            self._disconnect()
            deadline = time.monotonic() + _CONNECT_RETRY_S
            while True:
                try:
                    self._conn = psycopg2.connect(
                        self._dsn,
                        connect_timeout=max(1, min(10, int(deadline - time.monotonic()))),
                        **({"options": self._options} if self._options else {}),
                    )
                    self._conn.autocommit = True
                    if self._schema:
                        with self._conn.cursor() as cursor:
                            cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(self._schema)))
                    self._lost = False
                    break
                except psycopg2.OperationalError as exc:
                    self._disconnect()
                    self._lost = True
                    remaining = deadline - time.monotonic()
                    if _authentication_failed(exc) or remaining <= 0:
                        raise
                    time.sleep(min(_CONNECT_RETRY_DELAY_S, remaining))
                    if time.monotonic() >= deadline:
                        raise
        return self._conn

    def _disconnect(self) -> None:
        connection, self._conn = self._conn, None
        if connection is not None:
            try:
                connection.close()
            except Exception:
                # Cleanup must not replace an oracle's completed label.
                pass

    def _ensure_schema(self) -> None:
        connection = self._connect()
        if self._schema is None:
            name = "coevo_t_" + uuid.uuid4().hex
            with connection.cursor() as cursor:
                cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(name)))
                self._schema = name
                cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(name)))

    @property
    def backend_pid(self) -> int | None:
        if self._conn is None or self._conn.closed or self._lost:
            return None
        return self._conn.get_backend_pid()

    @property
    def engine_version(self) -> str:
        with self._connect().cursor() as cursor:
            cursor.execute("SHOW server_version")
            return cursor.fetchone()[0]

    def close(self) -> None:
        try:
            if self._schema:
                connection = self._connect()
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(self._schema)))
                except psycopg2.Error:
                    # Detect a killed backend on its first round trip, then reconnect.
                    self._lost = True
                    with self._connect().cursor() as cursor:
                        cursor.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(self._schema)))
        except Exception:
            # A crash can prevent cleanup; the cell's disposable instance owns
            # any remaining schema. Never turn a completed crash label into an error.
            pass
        finally:
            self._schema = None
            self._disconnect()
            self._lost = False

    def setup(self, statements: Iterable[str]) -> list[tuple[str, str | None]]:
        self.close()
        self._options = ""
        self._ensure_schema()
        outcomes = []
        settings = []
        session_objects = False
        for statement in statements:
            if not statement.strip():
                continue
            result = self.run(statement)
            outcomes.append((statement, result.error))
            if result.ok:
                session_objects |= _session_object(statement)
                name = _setting(statement)
                if name:
                    with self._connect().cursor() as cursor:
                        cursor.execute("SELECT current_setting(%s)", (name,))
                        settings.append((name, cursor.fetchone()[0]))
        if settings and not session_objects:
            base_options = parse_dsn(self._dsn).get("options", "")
            self._options = " ".join([base_options] + [
                "-c " + _option_atom(name + "=" + value) for name, value in settings
            ]).strip()
            self._conn.close()
            self._connect()
        return outcomes

    def _public_error(self, exc: BaseException) -> str:
        message = f"{type(exc).__name__}: {exc}".replace(self._dsn, "<dsn>")
        message = re.sub(r"coevo_t_[0-9a-f]{32}", "coevo_t", message)
        # libpq can quote individual DSN fields in authentication errors.
        try:
            password = parse_dsn(self._dsn).get("password")
        except psycopg2.Error:
            password = None
        if password:
            message = message.replace(password, "<hidden>")
        return re.sub(r"(?i)(password\s*=\s*)(?:'[^']*'|\S+)", r"\1<hidden>", message)

    def run(self, statement: str, timeout_s: float = 10.0) -> QueryResult:
        result = QueryResult()
        rejection = _rejection(statement)
        if rejection:
            result.error = rejection
            return result
        started = time.monotonic()

        def worker() -> None:
            try:
                self._ensure_schema()
                with self._conn.cursor() as cursor:
                    cursor.execute("SET statement_timeout = %s", (max(1, int(timeout_s * 1000)),))
                    cursor.execute(statement)
                    result.columns = [item[0] for item in (cursor.description or [])]
                    if cursor.description:
                        result.rows = normalize_rows(cursor.fetchall())
            except Exception as exc:  # Engine/transport failures are QueryResult data.
                result.error = self._public_error(exc)
                result.timed_out = _is_statement_timeout(exc)
                self._lost = (_connection_lost(result.error) or
                              isinstance(exc, (psycopg2.OperationalError, psycopg2.InterfaceError))
                              and bool(self._conn is None or self._conn.closed))
                result.is_internal_error = self._lost or is_internal_error(result.error)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        thread.join(max(0, timeout_s) + 5)
        if thread.is_alive():
            try:
                if self._conn is not None:
                    self._conn.cancel()
            except psycopg2.Error:
                self._lost = True
            thread.join(5)
            result.timed_out = True
            result.error = f"TimeoutError: exceeded {timeout_s}s"
        if result.timed_out and not str(result.error).startswith("TimeoutError:"):
            result.error = "TimeoutError: " + str(result.error)
        result.elapsed = time.monotonic() - started
        return result

    def explain_plan(self, statement: str) -> list | None:
        result = self.run("EXPLAIN (FORMAT JSON) " + statement)
        if result.ok and result.rows:
            return result.rows[0][0]
        return None
