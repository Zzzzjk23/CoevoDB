"""evaluate appends one ledger record for every accepted execution."""

from __future__ import annotations

import copy
from datetime import datetime

import pytest

from oracles.db_runner import QueryResult
from surprise.harness.contracts import SqlCase
from surprise.harness.evaluate import evaluate
from surprise.harness.ledger import Ledger, LedgerError
from surprise.harness.oracles import judge
from targets.duckdb_runner import DuckDBRunner

_SETUP = (
    "CREATE TABLE t(a INTEGER, b INTEGER)",
    "INSERT INTO t VALUES (1, 10), (2, 0), (NULL, 3)",
)


def _case(query: str = "SELECT a, b FROM t", predicate: str | None = "a > 0",
          engine: str = "duckdb") -> SqlCase:
    return SqlCase(engine=engine, setup=_SETUP, query=query, predicate=predicate)


class _Injecting:
    def __init__(self, when, result: QueryResult) -> None:
        self._inner = DuckDBRunner()
        self._when = when
        self._result = result

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        if self._when(sql):
            return copy.copy(self._result)
        return self._inner.run(sql, timeout_s=timeout_s)

    def close(self) -> None:
        self._inner.close()

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


def test_each_call_appends_one_record_matching_judge(tmp_path) -> None:
    path = tmp_path / "ledger.sqlite"
    ledger = Ledger(path)
    try:
        ledger.start_run("run-1", {"source": "test"})
        case = _case()
        record = evaluate(
            case, "tlp", ledger=ledger, run_id="run-1", purpose="explore",
            spec={"engine": "duckdb", "oracle": "tlp"}, phi={"ast": ["SELECT"]},
            theory_version="T0", p_t=0.25,
        )
        assert ledger.count(run_id="run-1") == 1
        assert (record.run_id, record.seq, record.record_id, record.purpose) == (
            "run-1", 1, "run-1:1", "explore",
        )
        assert record.case == case
        assert record.theory_version == "T0"
        assert record.p_t == 0.25
        assert record.surprise is None
        assert record.spec == {"engine": "duckdb", "oracle": "tlp"}
        assert record.phi == {"ast": ["SELECT"]}
        datetime.fromisoformat(record.created_at)
        assert record.created_at.endswith("+00:00")
        assert record.label.to_dict() == judge(case, "tlp").to_dict()

        invalid = evaluate(
            _case(predicate=None), "norec", ledger=ledger, run_id="run-1", purpose="explore",
        )
        assert invalid.seq == 2
        assert invalid.label.invalid_reason == "not_applicable"
        assert invalid.label.to_dict() == judge(_case(predicate=None), "norec").to_dict()
        assert ledger.records(run_id="run-1") == [record, invalid]

        def null_partition(sql: str) -> bool:
            return "IS NULL" in sql.upper()

        def factory():
            return _Injecting(
                null_partition,
                QueryResult(
                    error="InternalException: INTERNAL Error: injected",
                    is_internal_error=True,
                ),
            )

        failed = evaluate(
            case, "tlp", ledger=ledger, run_id="run-1", purpose="confirm", runner_factory=factory,
        )
        assert failed.seq == 3
        assert (failed.label.y, failed.label.fail_kind) == ("fail", "crash")
        assert failed.label.to_dict() == judge(case, "tlp", runner_factory=factory).to_dict()
        assert ledger.count() == 3
        stored = [record, invalid, failed]
    finally:
        ledger.close()

    reopened = Ledger(path)
    try:
        assert reopened.records(run_id="run-1") == stored
    finally:
        reopened.close()


def test_judge_exception_is_recorded_as_harness_error(tmp_path) -> None:
    ledger = Ledger(tmp_path / "ledger.sqlite")
    try:
        ledger.start_run("run-1", {})

        def explode():
            raise RuntimeError("runner exploded")

        broken = evaluate(
            _case(), "plan_variant", ledger=ledger, run_id="run-1", purpose="explore",
            runner_factory=explode,
        )
        assert (broken.label.y, broken.label.invalid_reason) == ("invalid", "harness_error")
        assert broken.label.detail == {"exception": "RuntimeError: runner exploded"}
        assert broken.surprise is None
        assert ledger.count(run_id="run-1") == 1
        assert ledger.records(run_id="run-1") == [broken]
    finally:
        ledger.close()


def test_rejected_calls_leave_no_record_and_do_not_run(tmp_path) -> None:
    ledger = Ledger(tmp_path / "ledger.sqlite")
    try:
        ledger.start_run("run-1", {})
        calls = {"n": 0}

        def factory():
            calls["n"] += 1
            return DuckDBRunner()

        case = _case()
        with pytest.raises(ValueError):
            evaluate(case, "no_such_oracle", ledger=ledger, run_id="run-1", purpose="explore",
                     runner_factory=factory)
        alien = SqlCase(engine="sqlite", setup=case.setup, query=case.query, predicate=case.predicate)
        with pytest.raises(ValueError):
            evaluate(alien, "tlp", ledger=ledger, run_id="run-1", purpose="explore",
                     runner_factory=factory)
        with pytest.raises(LedgerError):
            evaluate(case, "tlp", ledger=ledger, run_id="never-started", purpose="explore",
                     runner_factory=factory)
        assert calls["n"] == 0
        assert ledger.count() == 0
    finally:
        ledger.close()


def test_unstorable_arguments_are_rejected_before_execution(tmp_path) -> None:
    ledger = Ledger(tmp_path / "ledger.sqlite")
    try:
        ledger.start_run("run-1", {})
        calls = {"n": 0}

        def factory():
            calls["n"] += 1
            return DuckDBRunner()

        case = _case()
        rejected = (
            {"purpose": ""},
            {"purpose": "explore", "p_t": 1.5},
            {"purpose": "explore", "spec": {"weights": {1, 2}}},
        )
        for kwargs in rejected:
            with pytest.raises(ValueError):
                evaluate(
                    case, "tlp", ledger=ledger, run_id="run-1", runner_factory=factory, **kwargs,
                )
        assert calls["n"] == 0
        assert ledger.count() == 0
    finally:
        ledger.close()
