"""Runner fixtures for the S4 gate (``gates/all.py`` does not run this file).

Two kinds:

* Module-level classes. A child process can import them by name, so they can
  be passed as ``runner_factory`` / ``reference_factories`` under process
  isolation. They report through files named by environment variables,
  because the gate cannot see inside a child.
* ``scripted_factory``: a closure with shared state, for ``isolation="inline"``
  only. It makes a real DuckDB runner return chosen wrong rows on a schedule,
  so the rerun logic is tested without depending on a flaky engine bug.
"""
from __future__ import annotations

import ctypes
import os
import re
import signal
import time
import uuid
from typing import Any, Callable

from oracles.db_runner import QueryResult
from targets.duckdb_runner import DuckDBRunner

# One value per OS process: a module is imported once per process. Process ids
# are not used because Windows reuses them quickly.
PROCESS_TOKEN = uuid.uuid4().hex

TOKEN_LOG_ENV = "S04_GATE_TOKEN_LOG"
EXIT_MARK = "770077"
SLEEP_MARK = "880088"
EXIT_CODE = 77
REFERENCE_EXIT_CODE = 78


def die(code: int) -> None:
    """End this process at once with ``code``, running no exit handlers.

    ``os._exit`` still unloads the engine's library while its worker threads
    run; on Windows that ends the process with an access violation
    (0xC0000005) instead of ``code`` about once in two hundred times
    (measured: 2 of 400, then 0 of 600 with this function). A fixture whose
    exit code is part of the expectation has to die deterministically.
    """
    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        kernel32.TerminateProcess.restype = ctypes.c_int
        kernel32.TerminateProcess(kernel32.GetCurrentProcess(), code)
    else:
        os.kill(os.getpid(), signal.SIGKILL)
    os._exit(code)


class TokenLogRunner(DuckDBRunner):
    """A real DuckDB runner that records which process executed each statement."""

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        path = os.environ.get(TOKEN_LOG_ENV)
        if path:
            with open(path, "a", encoding="ascii") as handle:
                handle.write(PROCESS_TOKEN + "\n")
        return super().run(sql, timeout_s=timeout_s)


class ExitingRunner(DuckDBRunner):
    """Kills its own process, without a Python exception, on the marked query."""

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        if EXIT_MARK in sql:
            die(EXIT_CODE)
        return super().run(sql, timeout_s=timeout_s)


class SleepingRunner(DuckDBRunner):
    """Never returns from the marked query (a hang the statement timeout cannot see)."""

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        if SLEEP_MARK in sql:
            time.sleep(600)
        return super().run(sql, timeout_s=timeout_s)


class _ConstantReference:
    """A reference engine that answers every query with ``ROWS``."""

    ROWS: list[list[Any]] = []
    engine_version = "fixture"

    def setup(self, statements: Any) -> list[tuple[str, None]]:
        return [(statement, None) for statement in statements]

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        return QueryResult(rows=[list(row) for row in self.ROWS])

    def close(self) -> None:
        pass


class ExceptAllReference(_ConstantReference):
    """The correct bag of ``SELECT v FROM t EXCEPT ALL SELECT v FROM u`` (DF-A)."""

    ROWS = [[1], [2], [2]]


class ExitingReference(_ConstantReference):
    """A reference engine whose process dies while it runs the query."""

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        die(REFERENCE_EXIT_CODE)


_SINGLE_THREAD = re.compile(r"\bthreads\s*(=|\bto\b)\s*1\b", re.IGNORECASE)
_RESET_THREADS = re.compile(r"\breset\s+threads\b", re.IGNORECASE)


def scripted_factory(
    query: str,
    wrong_rows: list[list[Any]],
    *,
    reproduces: Callable[[int], bool] = lambda n: True,
    single_thread_reproduces: bool = True,
    permute: bool = False,
    stop_when_reduced_below: int | None = None,
) -> tuple[Callable[[], Any], dict[str, Any]]:
    """A runner factory that fakes a plan-variant discrepancy on ``query``.

    While ``PRAGMA disable_optimizer`` is in effect, ``query`` returns
    ``wrong_rows`` instead of its real rows:

    * in a session that was switched to one thread: when
      ``single_thread_reproduces`` is true;
    * otherwise: when ``reproduces(n)`` is true, where ``n`` counts these
      default-thread executions from 1 across every runner the factory made
      (one per oracle judgement: the raw one first, then each rerun).

    ``permute`` reverses the row order of every result in every second
    judgement; bags are unchanged. ``stop_when_reduced_below`` turns the fake discrepancy
    off for good once a setup with fewer statements than that is seen, which
    is what a minimiser does first. Returns ``(factory, state)``;
    ``state["hits"]`` counts the wrong answers given.
    """
    state: dict[str, Any] = {"default_runs": 0, "single_runs": 0, "hits": 0, "runners": 0,
                             "stopped": False, "reversed": 0}

    class Scripted:
        def __init__(self) -> None:
            self._inner = DuckDBRunner()
            self._no_optimizer = False
            self._single = False
            state["runners"] += 1
            # Fixed at creation: the runner of judgement k is created after k-1
            # judgements ran, so the orientation alternates per judgement
            # however many runners one judgement opens.
            self._reverse = permute and (state["default_runs"] + state["single_runs"]) % 2 == 1

        def _observe(self, sql: str) -> None:
            head = sql.strip().upper()
            if head.startswith("PRAGMA DISABLE_OPTIMIZER"):
                self._no_optimizer = True
            elif head.startswith("PRAGMA ENABLE_OPTIMIZER"):
                self._no_optimizer = False
            if _RESET_THREADS.search(sql):
                self._single = False
            elif _SINGLE_THREAD.search(sql):
                self._single = True

        def setup(self, statements: Any) -> Any:
            statements = list(statements)
            # setup() opens a new connection: session settings start over.
            self._no_optimizer = False
            self._single = False
            if stop_when_reduced_below is not None and len(statements) < stop_when_reduced_below:
                state["stopped"] = True
            for statement in statements:
                self._observe(statement)
            return self._inner.setup(statements)

        def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
            self._observe(sql)
            result = self._inner.run(sql, timeout_s=timeout_s)
            if sql.strip().rstrip(";") == query and self._no_optimizer and result.ok:
                if self._single:
                    state["single_runs"] += 1
                    fake = single_thread_reproduces and not state["stopped"]
                else:
                    state["default_runs"] += 1
                    fake = reproduces(state["default_runs"]) and not state["stopped"]
                if fake:
                    state["hits"] += 1
                    result = QueryResult(rows=[list(row) for row in wrong_rows],
                                         columns=list(result.columns))
            if self._reverse and result.ok:
                result.rows = list(reversed(result.rows))
                state["reversed"] += 1
            return result

        def close(self) -> None:
            self._inner.close()

        def __getattr__(self, name: str) -> Any:
            return getattr(self._inner, name)

    return Scripted, state
