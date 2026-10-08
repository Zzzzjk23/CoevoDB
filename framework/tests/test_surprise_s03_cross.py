"""Cross-DBMS quorum and the PostgreSQL reference runner.

Real engines back the quorum cases. Fixed runners are used only where the
verdict depends on a constructed tie, a setup failure, or a target error.
"""

from __future__ import annotations

import json

import psycopg2
import pytest

from oracles.db_runner import QueryResult
from oracles.normalize import loose_bag
from surprise.harness.contracts import SqlCase
from surprise.harness.oracles import judge
from surprise.harness.oracles.cross_dbms import (
    collect_reference_results,
    default_reference_factories,
    judge_case,
)
from surprise.harness.oracles.pg_reference import PostgresReferenceRunner, is_readonly_query
from surprise.harness.oracles.registry import get_handler, make_options
from targets.duckdb_runner import DuckDBRunner

_SETUP = (
    "CREATE TABLE t(a INT, b INT)",
    "INSERT INTO t VALUES (1, 1), (2, NULL), (3, 3)",
)
_ALL = (
    "CREATE TABLE t(v INT)",
    "INSERT INTO t VALUES (1), (1), (2), (2), (2), (NULL)",
    "CREATE TABLE u(v INT)",
    "INSERT INTO u VALUES (1), (2), (NULL)",
)
_EXCEPT = "SELECT v FROM t EXCEPT ALL SELECT v FROM u"
_INTERSECT = "SELECT v FROM t INTERSECT ALL SELECT v FROM u"
_ADMIN = {
    "host": "127.0.0.1",
    "port": 55432,
    "user": "coevo",
    "dbname": "postgres",
    "connect_timeout": 5,
}


def _case(
    engine: str = "duckdb",
    query: str = "SELECT a, b FROM t",
    predicate: str | None = None,
    setup: tuple[str, ...] = _SETUP,
) -> SqlCase:
    return SqlCase(engine=engine, setup=setup, query=query, predicate=predicate)


def _fixed(
    rows: tuple[tuple, ...] | list | tuple = (),
    *,
    error: str | None = None,
    internal: bool = False,
    timed_out: bool = False,
    setup_error: str | None = None,
    version: str = "fixture",
):
    class Runner:
        engine_version = version
        ran = False

        def setup(self, statements):
            if setup_error is not None:
                text = statements[0] if statements else ""
                return [(text, setup_error)]
            return [(statement, None) for statement in statements]

        def run(self, sql, timeout_s=10.0):
            Runner.ran = True
            return QueryResult(
                rows=[list(row) for row in rows],
                error=error,
                is_internal_error=internal,
                timed_out=timed_out,
            )

        def close(self):
            pass

    return Runner


def _schemas() -> list[str]:
    conn = psycopg2.connect(**_ADMIN)
    try:
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(
            "SELECT nspname FROM pg_namespace WHERE nspname LIKE 'coevo_ref_%' ORDER BY 1"
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def _ok(outcomes) -> bool:
    return all(error is None for _statement, error in outcomes)


def test_handler_is_registered() -> None:
    assert get_handler("cross_dbms") is judge_case


def test_readonly_query_rejects_mutation_and_ignores_literals() -> None:
    assert is_readonly_query("SELECT v FROM t EXCEPT ALL SELECT v FROM u")
    assert is_readonly_query("SELECT v FROM t INTERSECT ALL SELECT v FROM u")
    assert is_readonly_query("SELECT 'INSERT' AS a FROM t")
    assert is_readonly_query("WITH x AS (SELECT 1) SELECT * FROM x")
    assert is_readonly_query("VALUES (1)")
    assert is_readonly_query("TABLE t")
    assert not is_readonly_query("INSERT INTO t VALUES (1)")
    assert not is_readonly_query("UPDATE t SET v = 1")
    assert not is_readonly_query("DELETE FROM t")
    assert not is_readonly_query("DROP TABLE t")
    assert not is_readonly_query("WITH x AS (SELECT 1) DELETE FROM t")
    assert not is_readonly_query("SELECT v INTO other FROM t")
    assert not is_readonly_query("COMMIT")
    assert not is_readonly_query("EXPLAIN SELECT 1")
    assert not is_readonly_query("SHOW server_version")


def test_default_factories_omit_the_target_and_reject_aliases() -> None:
    duck = default_reference_factories("duckdb")
    fusion = default_reference_factories("datafusion")
    assert set(duck) == {"datafusion", "sqlite", "postgres"}
    assert set(fusion) == {"duckdb", "sqlite", "postgres"}
    assert fusion["postgres"] is PostgresReferenceRunner
    assert all(callable(factory) for factory in duck.values())
    with pytest.raises(ValueError, match="duckdb_old"):
        default_reference_factories("duckdb_old")
    with pytest.raises(ValueError, match="mysql"):
        default_reference_factories("mysql")


def test_collect_rejects_unknown_target_and_version_alias_before_calling() -> None:
    called: list[str] = []

    def factory():
        called.append("called")
        return DuckDBRunner()

    case = _case("datafusion")
    with pytest.raises(ValueError, match="version alias"):
        collect_reference_results(case, {"duckdb_old": factory}, timeout_s=1)
    with pytest.raises(ValueError, match="version alias"):
        collect_reference_results(case, {"datafusion-50.0.0": factory}, timeout_s=1)
    with pytest.raises(ValueError, match="target engine"):
        collect_reference_results(
            _case("duckdb"), {"duckdb": factory}, timeout_s=1
        )
    with pytest.raises(ValueError, match="unknown engine"):
        collect_reference_results(case, {"mysql": factory}, timeout_s=1)
    with pytest.raises(ValueError, match="callable"):
        collect_reference_results(case, {"sqlite": object()}, timeout_s=1)
    assert called == []
    assert collect_reference_results(case, {}, timeout_s=1) == {}


def test_collect_runs_the_full_query_and_keeps_setup_failures() -> None:
    case = _case("datafusion", "SELECT a, b FROM t", predicate="a = 3")
    results = collect_reference_results(case, {"duckdb": DuckDBRunner}, timeout_s=5)
    assert set(results) == {"duckdb"}
    assert results["duckdb"].ok
    assert loose_bag(results["duckdb"].rows) == loose_bag([[3, 3]])

    broken = _fixed(setup_error="relation missing")
    failed = collect_reference_results(
        _case("datafusion"),
        {"sqlite": broken},
        timeout_s=5,
    )
    assert failed["sqlite"].ok is False
    assert failed["sqlite"].error == "relation missing"
    assert broken.ran is False


def test_collect_turns_reference_exceptions_into_error_results() -> None:
    class Boom:
        engine_version = "boom"
        closed = 0

        def setup(self, statements):
            return [(statement, None) for statement in statements]

        def run(self, sql, timeout_s=10.0):
            raise RuntimeError("disk gone")

        def close(self):
            Boom.closed += 1

    case = _case("datafusion")
    results = collect_reference_results(case, {"sqlite": Boom}, timeout_s=5)
    assert results["sqlite"].ok is False
    assert "RuntimeError" in (results["sqlite"].error or "")
    assert "disk gone" in (results["sqlite"].error or "")
    assert Boom.closed == 1


def test_pg_reference_matches_measured_all_bags_and_version() -> None:
    runner = PostgresReferenceRunner()
    try:
        assert runner.engine_version.startswith("16.")
        assert _ok(runner.setup(_ALL))
        except_all = runner.run(_EXCEPT)
        intersect_all = runner.run(_INTERSECT)
        assert except_all.ok and intersect_all.ok
        assert loose_bag(except_all.rows) == loose_bag([[1], [2], [2]])
        assert loose_bag(intersect_all.rows) == loose_bag([[1], [2], [None]])
    finally:
        runner.close()


def test_pg_runners_are_isolated_and_leave_no_schema() -> None:
    left = PostgresReferenceRunner()
    right = PostgresReferenceRunner()
    try:
        assert _schemas() == []
        assert _ok(left.setup(["CREATE TABLE t(v INT)", "INSERT INTO t VALUES (1)"]))
        assert _ok(right.setup(["CREATE TABLE t(v INT)", "INSERT INTO t VALUES (2)"]))
        assert _schemas() == []
        assert left.run("SELECT v FROM t").rows == [[1]]
        assert right.run("SELECT v FROM t").rows == [[2]]
        committed = left.setup(["CREATE TABLE t(v INT)", "INSERT INTO t VALUES (1)", "COMMIT"])
        assert committed[-1][1] is not None
        assert _schemas() == []
        assert left.run("SELECT v FROM t").rows == [[1]]
    finally:
        left.close()
        right.close()
    assert _schemas() == []
    left.close()


def test_pg_errors_do_not_stick_and_setup_resets() -> None:
    runner = PostgresReferenceRunner()
    try:
        assert _ok(runner.setup(["CREATE TABLE t(v INT)", "INSERT INTO t VALUES (1)"]))
        missing = runner.run("SELECT missing FROM t")
        assert not missing.ok and not missing.timed_out and not missing.is_internal_error
        assert runner.run("SELECT v FROM t").rows == [[1]]
        partial = runner.setup([
            "CREATE TABLE t(v INT)",
            "INSERT INTO t VALUES (1)",
            "INSERT INTO missing VALUES (9)",
        ])
        assert partial[0][1] is None and partial[1][1] is None and partial[2][1] is not None
        assert runner.run("SELECT v FROM t").rows == [[1]]
        assert _ok(runner.setup(["CREATE TABLE t(v INT)", "INSERT INTO t VALUES (4)"]))
        assert runner.run("SELECT v FROM t").rows == [[4]]
        runner.close()
        assert _ok(runner.setup(["CREATE TABLE t(v INT)", "INSERT INTO t VALUES (8)"]))
        assert runner.run("SELECT v FROM t").rows == [[8]]
        runner.close()
        runner.close()
    finally:
        runner.close()
    assert _schemas() == []


def test_pg_statement_timeout_then_reuse() -> None:
    runner = PostgresReferenceRunner()
    try:
        assert _ok(runner.setup(["CREATE TABLE t(v INT)", "INSERT INTO t VALUES (1)"]))
        timed = runner.run("SELECT pg_sleep(2)", timeout_s=0.4)
        assert timed.timed_out and not timed.ok
        assert not timed.is_internal_error
        again = runner.run("SELECT v FROM t")
        assert again.ok and again.rows == [[1]]
    finally:
        runner.close()


def test_pg_refuses_state_changing_statements_without_running_them() -> None:
    runner = PostgresReferenceRunner()
    try:
        assert _ok(runner.setup(["CREATE TABLE t(v INT)", "INSERT INTO t VALUES (1)"]))
        for statement in (
            "DELETE FROM t",
            "UPDATE t SET v = 2",
            "INSERT INTO t VALUES (3)",
            "DROP TABLE t",
            "SELECT v INTO t2 FROM t",
        ):
            refused = runner.run(statement)
            assert not refused.ok, statement
        assert runner.run("SELECT v FROM t").rows == [[1]]
        assert not runner.run("SELECT * FROM t2").ok
    finally:
        runner.close()


def test_explicit_dsn_wins_and_is_not_printed(monkeypatch, capsys) -> None:
    secret = "super-secret-password"
    monkeypatch.setenv(
        "COEVO_REFERENCE_PG_DSN",
        "host=127.0.0.1 port=1 user=coevo dbname=postgres connect_timeout=1",
    )
    runner = PostgresReferenceRunner(
        dsn="host=127.0.0.1 port=55432 user=coevo dbname=postgres connect_timeout=5"
    )
    try:
        assert runner.engine_version.startswith("16.")
        assert secret not in repr(runner)
    finally:
        runner.close()

    monkeypatch.setenv(
        "COEVO_REFERENCE_PG_DSN",
        f"host=127.0.0.1 port=1 user=coevo password={secret} dbname=postgres connect_timeout=1",
    )
    hidden = PostgresReferenceRunner()
    try:
        with pytest.raises(ConnectionError) as caught:
            hidden.engine_version
    finally:
        hidden.close()
    assert secret not in str(caught.value)
    captured = capsys.readouterr()
    assert secret not in captured.out
    assert secret not in captured.err


def test_quorum_fails_only_when_the_target_is_the_unique_outlier() -> None:
    import datafusion
    import duckdb
    import sqlite3

    fusion = _case("datafusion", _EXCEPT, setup=_ALL)
    failed = judge(fusion, "cross_dbms")
    assert failed.y == "fail" and failed.fail_kind == "wrong_result"
    assert failed.detail["outliers"] == ["datafusion"]
    assert set(failed.detail["voters"]) >= {"duckdb", "postgres", "datafusion"}
    assert "sqlite" not in failed.detail["voters"]
    assert failed.identity.behavior == {"missing": 3, "extra": 0}
    assert failed.identity.error_class is None
    assert failed.identity.switches == ()
    assert failed.cve == {}
    participants = failed.detail["participants"]
    assert participants["duckdb"]["version"] == duckdb.__version__
    assert participants["datafusion"]["version"] == datafusion.__version__
    assert participants["sqlite"]["version"] == sqlite3.sqlite_version
    assert participants["postgres"]["version"].startswith("16.")
    assert participants["sqlite"]["ok"] is False
    assert participants["datafusion"]["ok"] is True
    blob = json.dumps(failed.to_dict(), sort_keys=True)
    assert "coevo_ref_" not in blob
    assert "elapsed" not in blob
    assert failed.to_dict() == judge(fusion, "cross_dbms").to_dict()

    intersect = judge(_case("datafusion", _INTERSECT, setup=_ALL), "cross_dbms")
    assert intersect.y == "fail" and intersect.detail["outliers"] == ["datafusion"]
    assert intersect.identity.behavior == {"missing": 0, "extra": 3}

    agreed = judge(_case("duckdb", _EXCEPT, setup=_ALL), "cross_dbms")
    assert (agreed.y, agreed.invalid_reason) == ("invalid", "non_unique_outlier")
    assert agreed.detail["outliers"] == ["datafusion"]
    assert "duckdb" in agreed.detail["voters"]

    plain = judge(_case("duckdb"), "cross_dbms")
    plain_df = judge(_case("datafusion"), "cross_dbms")
    assert plain.y == "pass" and plain_df.y == "pass"
    assert plain.identity.behavior == {}
    assert set(plain.detail["voters"]) >= {"duckdb", "datafusion", "sqlite", "postgres"}
    assert plain.detail["outliers"] == []


def test_constructed_tie_multiple_outliers_and_target_in_majority() -> None:
    case = _case("datafusion", _EXCEPT, setup=_ALL)
    tie = judge(case, "cross_dbms", reference_factories={
        "duckdb": _fixed([[1]]),
        "postgres": _fixed([[1]]),
        "sqlite": _fixed([[2]]),
    }, runner_factory=_fixed([[2]]))
    assert tie.invalid_reason == "non_unique_outlier"
    assert tie.detail["outliers"] == ["duckdb", "postgres"]

    several = judge(case, "cross_dbms", runner_factory=_fixed([[0]]), reference_factories={
        "duckdb": _fixed([[1]]),
        "postgres": _fixed([[1]]),
        "sqlite": _fixed([[2]]),
    })
    assert several.invalid_reason == "non_unique_outlier"
    assert several.detail["outliers"] == ["datafusion", "sqlite"]

    majority = judge(case, "cross_dbms", runner_factory=_fixed([[1]]), reference_factories={
        "duckdb": _fixed([[1]]),
        "postgres": _fixed([[1]]),
        "sqlite": _fixed([[9]]),
    })
    assert majority.invalid_reason == "non_unique_outlier"
    assert majority.detail["outliers"] == ["sqlite"]
    assert majority.y == "invalid"

    unique = judge(case, "cross_dbms", runner_factory=_fixed([[9]]), reference_factories={
        "duckdb": _fixed([[1]]),
        "postgres": _fixed([[1]]),
        "sqlite": _fixed([[1]]),
    })
    assert unique.y == "fail" and unique.fail_kind == "wrong_result"
    assert unique.detail["outliers"] == ["datafusion"]
    assert unique.identity.behavior == {"missing": 1, "extra": 1}


def test_gate_fixtures_keep_real_datafusion_evidence() -> None:
    case = _case("datafusion", _EXCEPT, setup=_ALL)
    short = judge(case, "cross_dbms", reference_factories={
        "duckdb": _fixed([[1], [2], [2]]),
    })
    assert (short.y, short.invalid_reason) == ("invalid", "insufficient_engines")

    tied = judge(case, "cross_dbms", reference_factories={
        "duckdb": _fixed([[1]]),
        "postgres": _fixed([[1]]),
        "sqlite": _fixed([]),
    })
    assert tied.invalid_reason == "non_unique_outlier"

    split = judge(case, "cross_dbms", reference_factories={
        "duckdb": _fixed([[1]]),
        "postgres": _fixed([[1]]),
        "sqlite": _fixed([[2]]),
    })
    assert split.invalid_reason == "non_unique_outlier"
    with pytest.raises(ValueError):
        judge(case, "cross_dbms", reference_factories={"duckdb_old": _fixed([])})


def test_reference_setup_error_is_not_a_vote() -> None:
    broken = _fixed(setup_error="relation missing")
    passed = judge(
        _case("datafusion", _EXCEPT, setup=_ALL),
        "cross_dbms",
        runner_factory=_fixed([[1]]),
        reference_factories={
            "duckdb": _fixed([[1]]),
            "postgres": _fixed([[1]]),
            "sqlite": broken,
        },
    )
    assert passed.y == "pass"
    assert passed.detail["voters"] == ["datafusion", "duckdb", "postgres"]
    assert passed.detail["participants"]["sqlite"]["ok"] is False
    assert "relation missing" in passed.detail["participants"]["sqlite"]["error"]
    assert broken.ran is False

    only_two = judge(
        _case("datafusion"),
        "cross_dbms",
        runner_factory=_fixed([[1]]),
        reference_factories={
            "duckdb": _fixed([[1]]),
            "sqlite": _fixed(setup_error="relation missing"),
        },
    )
    assert only_two.invalid_reason == "insufficient_engines"
    assert only_two.detail["voters"] == ["datafusion", "duckdb"]


def test_target_errors_are_not_votes() -> None:
    called: list[str] = []

    def reference():
        called.append("called")
        raise AssertionError("reference should not run")

    refs = {"datafusion": reference, "sqlite": reference, "postgres": reference}
    syntax = judge(
        _case(),
        "cross_dbms",
        runner_factory=_fixed(error="ParserException: syntax error at or near ALL"),
        reference_factories=refs,
    )
    assert (syntax.y, syntax.invalid_reason) == ("invalid", "query_error")

    value = judge(
        _case(),
        "cross_dbms",
        runner_factory=_fixed(error="ConversionException: division by zero"),
        reference_factories=refs,
    )
    assert value.invalid_reason == "value_dependent_error"

    timed = judge(
        _case(),
        "cross_dbms",
        runner_factory=_fixed(error="TimeoutError: exceeded 1s", timed_out=True),
        reference_factories=refs,
    )
    assert timed.invalid_reason == "timeout"

    crashed = judge(
        _case(),
        "cross_dbms",
        runner_factory=_fixed(
            error="InternalException: INTERNAL catalog error",
            internal=True,
        ),
        reference_factories=refs,
    )
    assert crashed.y == "fail" and crashed.fail_kind == "crash"
    assert crashed.identity.error_class == "InternalException"
    assert crashed.identity.behavior == {}
    assert called == []

    handler = judge_case(
        _case(),
        factory=_fixed(setup_error="relation missing"),
        timeout_s=5,
        options=make_options(reference_factories=refs),
    )
    assert handler.invalid_reason == "setup_error"
    assert "relation missing" in handler.detail["error"]
    assert called == []


def test_state_changing_query_is_not_applicable_and_empty_refs_have_no_quorum() -> None:
    called: list[str] = []

    def reference():
        called.append("called")
        raise AssertionError("reference should not run")

    label = judge(
        _case(query="DELETE FROM t"),
        "cross_dbms",
        reference_factories={
            "datafusion": reference,
            "sqlite": reference,
            "postgres": reference,
        },
    )
    assert (label.y, label.invalid_reason) == ("invalid", "not_applicable")
    assert called == []

    alone = judge(_case(), "cross_dbms", reference_factories={})
    assert alone.invalid_reason == "insufficient_engines"
    assert alone.detail["voters"] == ["duckdb"]


def test_no_reference_schema_remains() -> None:
    assert _schemas() == []
