"""Module-level runners a child process can import by name.

Pytest's prepend import mode loads this file as ``test_surprise_s04_runners``.
Process isolation resolves ``runner_factory`` from that module name.
"""

from __future__ import annotations

import os
import time
from typing import Any

from oracles.db_runner import QueryResult
from targets.duckdb_runner import DuckDBRunner

EXIT_MARK = "770077"
SLEEP_MARK = "880088"
EXIT_CODE = 77


class OkTarget:
    """Returns one row for every statement. A pass under plan variant."""

    calls: list[str] = []

    def setup(self, statements: Any) -> list[tuple[str, None]]:
        self.calls.append("setup")
        return [(statement, None) for statement in statements]

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        self.calls.append("run")
        return QueryResult(rows=[[1]])

    def close(self) -> None:
        self.calls.append("close")


class KeyProbe:
    """Reports whether the API key is visible. The value itself is never read."""

    def setup(self, statements: Any) -> list[tuple[str, None]]:
        return [(statement, None) for statement in statements]

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        present = 1 if "DEEPSEEK_API_KEY" in os.environ else 0
        return QueryResult(rows=[[present]])

    def close(self) -> None:
        pass


class ExitingRunner(DuckDBRunner):
    """Kills the process, without a Python exception, on the marked query."""

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        if EXIT_MARK in sql:
            os._exit(EXIT_CODE)
        return super().run(sql, timeout_s=timeout_s)


class SleepingRunner(DuckDBRunner):
    """Ignores the statement timeout and sleeps on the marked query."""

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        if SLEEP_MARK in sql:
            time.sleep(600)
        return super().run(sql, timeout_s=timeout_s)


class ExitingReference:
    """A reference engine whose process dies while answering."""

    engine_version = "fixture"

    def setup(self, statements: Any) -> list[tuple[str, None]]:
        return [(statement, None) for statement in statements]

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        os._exit(78)

    def close(self) -> None:
        pass


class AgreeReference:
    """A reference engine that agrees with ``OkTarget``."""

    engine_version = "fixture"

    def setup(self, statements: Any) -> list[tuple[str, None]]:
        return [(statement, None) for statement in statements]

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        return QueryResult(rows=[[1]])

    def close(self) -> None:
        pass
