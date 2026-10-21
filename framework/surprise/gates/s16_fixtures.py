"""PostgreSQL runner fixtures for the S16 gate (``gates/all.py`` does not run this file).

Module-level subclasses of the harness target runner, so a CVE child process can import them by
name. Each one perturbs only statements that carry ``s16_cases.MARK`` and leaves every other
statement, and every reference engine, untouched. They exist to show that the new PostgreSQL code
paths turn a wrong target result into ``fail``; real PostgreSQL defects are in the M1 table.
"""
from __future__ import annotations

import re
from typing import Any

from oracles.db_runner import QueryResult
from surprise.harness.oracles.pg_target import PostgresTargetRunner

from .s16_cases import MARK

_CREATE_INDEX = re.compile(r"^\s*CREATE\s+(UNIQUE\s+)?INDEX\b", re.IGNORECASE)
_DROP_INDEX = re.compile(r"^\s*DROP\s+INDEX\b", re.IGNORECASE)
_EXPLAIN = re.compile(r"^\s*EXPLAIN\b", re.IGNORECASE)


def _copy(result: QueryResult, rows: list[list[Any]]) -> QueryResult:
    return QueryResult(rows=rows, columns=list(result.columns), error=result.error,
                       is_internal_error=result.is_internal_error, elapsed=result.elapsed,
                       timed_out=result.timed_out)


class DropRowRunner(PostgresTargetRunner):
    """Drops the last row of every successful marked statement."""

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        result = super().run(sql, timeout_s=timeout_s)
        if MARK in sql and result.ok and result.rows and not _EXPLAIN.match(sql):
            return _copy(result, [list(row) for row in result.rows[:-1]])
        return result


class TlpExtraRunner(PostgresTargetRunner):
    """Repeats the first row of the marked ``(p) IS NULL`` partition."""

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        result = super().run(sql, timeout_s=timeout_s)
        if MARK in sql and "IS NULL" in sql.upper() and result.ok and result.rows:
            return _copy(result, [list(row) for row in result.rows] + [list(result.rows[0])])
        return result


class NorecCountRunner(PostgresTargetRunner):
    """Adds one to the marked ``SELECT COUNT(*) ... WHERE`` form."""

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        result = super().run(sql, timeout_s=timeout_s)
        if MARK in sql and "COUNT(*)" in sql.upper() and result.ok and result.rows:
            first = list(result.rows[0])
            first[0] = int(first[0] or 0) + 1
            return _copy(result, [first] + [list(row) for row in result.rows[1:]])
        return result


class IndexDropRunner(PostgresTargetRunner):
    """Drops the last row of a marked query while a secondary index created here exists."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._indexes = 0

    def setup(self, statements):  # noqa: ANN001 - same signature as the runner
        self._indexes = 0
        return super().setup(statements)

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        result = super().run(sql, timeout_s=timeout_s)
        if result.ok and _CREATE_INDEX.match(sql):
            self._indexes += 1
        elif result.ok and _DROP_INDEX.match(sql):
            self._indexes = max(0, self._indexes - 1)
        elif (self._indexes and MARK in sql and result.ok and result.rows
              and not _EXPLAIN.match(sql)):
            return _copy(result, [list(row) for row in result.rows[:-1]])
        return result
