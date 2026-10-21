"""The PG target runner contract against real 16.15 and 15.19 servers."""

import time

import pytest

from surprise.experiments import pg_instance
from surprise.harness.oracles.pg_target import OLD_DSN_ENV, TARGET_DSN_ENV, PostgresTargetRunner
from surprise.harness.oracles.registry import REFERENCE_ENGINES, TARGET_ENGINES, runner_factory_for


@pytest.fixture(scope="module")
def dsns(tmp_path_factory):
    with pg_instance.running(tmp_path_factory.mktemp("s16-target")) as values:
        yield values


@pytest.fixture
def runner(dsns):
    instance = PostgresTargetRunner()
    try:
        yield instance
    finally:
        instance.close()


def test_missing_dsn_and_repr(monkeypatch):
    monkeypatch.delenv(TARGET_DSN_ENV, raising=False)
    with pytest.raises(ConnectionError, match=TARGET_DSN_ENV):
        PostgresTargetRunner()
    with pytest.raises(ConnectionError, match="CUSTOM_PG_DSN"):
        PostgresTargetRunner(env="CUSTOM_PG_DSN")
    candidate = PostgresTargetRunner("password=secret-dsn")
    assert "secret" not in repr(candidate) and "password" not in repr(candidate)
    assert candidate.backend_pid is None
    candidate.close()


def test_versions_factory_and_lazy_schema(runner):
    assert TARGET_ENGINES == ("duckdb", "datafusion", "postgres")
    assert REFERENCE_ENGINES == ("duckdb", "datafusion", "sqlite", "postgres")
    assert runner_factory_for("postgres") is PostgresTargetRunner
    assert runner.engine_version == "16.15"
    result = runner.run("SELECT 1 AS n, 'Infinity'::float8 AS f, NULL AS empty")
    assert result.ok and result.rows == [[1, "float:+inf", None]]
    assert result.columns == ["n", "f", "empty"]
    assert runner.run("SELECT current_schema()").rows[0][0].startswith("coevo_t_")
    old = PostgresTargetRunner(env=OLD_DSN_ENV)
    try:
        assert old.engine_version == "15.19"
    finally:
        old.close()


def test_setup_schema_isolation_autocommit_and_cleanup(runner, dsns):
    second = PostgresTargetRunner(dsns["target"])
    try:
        statements = ["CREATE TABLE t(a int)", "INSERT INTO t VALUES (1), (2)", "VACUUM t"]
        assert runner.setup(statements) == [(statement, None) for statement in statements]
        schema = runner.run("SELECT current_schema()").rows[0][0]
        assert second.run("SELECT * FROM t").error
        assert second.setup(["CREATE TABLE t(a int)", "INSERT INTO t VALUES (9)"])[1][1] is None
        assert runner.run("SELECT * FROM t ORDER BY a").rows == [[1], [2]]
        assert second.run("SELECT * FROM t").rows == [[9]]
        plan = runner.explain_plan("SELECT * FROM t")
        assert isinstance(plan, list) and "Plan" in plan[0]
        assert runner.explain_plan("SELECT * FROM missing_table") is None
        runner.setup([])
        assert second.run(f"SELECT count(*) FROM pg_namespace WHERE nspname = '{schema}'").rows == [[0]]
        schema = runner.run("SELECT current_schema()").rows[0][0]
        runner.close()
        runner.close()
        assert runner.backend_pid is None
        assert second.run(f"SELECT count(*) FROM pg_namespace WHERE nspname = '{schema}'").rows == [[0]]
    finally:
        second.close()


@pytest.mark.parametrize("statement", [
    "BEGIN", "START TRANSACTION", "COMMIT", "END", "ROLLBACK", "ABORT", "SAVEPOINT a",
    "RELEASE a", "PREPARE TRANSACTION 'a'", "COMMIT PREPARED 'a'", "ROLLBACK PREPARED 'a'",
    "SET search_path TO public", 'SET SESSION "search_path" = public',
    "SET LOCAL search_path TO public", 'RESET "search_path"', "SET ROLE coevo", "RESET ROLE",
    "SET SESSION AUTHORIZATION coevo", "RESET SESSION AUTHORIZATION", "RESET ALL", "DISCARD ALL",
    "/* nested /* comment */ comment */ BEGIN", "SET /* comment */ ROLE coevo",
    "SELECT 1; SELECT 2", "SELECT 1;;", "SELECT 'unterminated",
])
def test_refusals_do_not_reach_backend(runner, statement):
    # No connection or schema is created for a refused statement.
    result = runner.run(statement)
    assert result.error.startswith("NotApplicable:")
    assert runner.backend_pid is None
    outcomes = runner.setup([statement, "SELECT 1"])
    assert outcomes[0] == (statement, result.error)
    assert outcomes[1] == ("SELECT 1", None)


@pytest.mark.parametrize("statement", [
    "SELECT '; COMMIT'", "SELECT $$; BEGIN; SET ROLE coevo$$", "SELECT $tag$; SET search_path TO public$tag$",
    "/* a /* b */ c */ SELECT 1; -- trailing comment", "SELECT E'\\\'; COMMIT'",
    'SELECT 1 AS "a; BEGIN"',
])
def test_scanner_preserves_quotes_and_comments(runner, statement):
    assert runner.run(statement).ok


@pytest.mark.parametrize("statement", [
    "COPY t FROM PROGRAM 'echo 1'", "ALTER SYSTEM SET work_mem = '1MB'",
    "SELECT pg_read_file('postgresql.conf')", "CREATE ROLE s16_intruder",
])
def test_target_has_no_superuser_powers(runner, statement):
    assert runner.setup(["CREATE TABLE t(a int)"]) == [("CREATE TABLE t(a int)", None)]
    result = runner.run(statement)
    assert result.error and not result.error.startswith("NotApplicable")
    assert "permission denied" in result.error.lower() or "superuser" in result.error.lower()
    assert runner.run("SELECT 1").ok


def test_timeout_recovers(runner):
    started = time.monotonic()
    result = runner.run("SELECT pg_sleep(20)", timeout_s=0.15)
    assert result.timed_out and result.error.startswith("TimeoutError:")
    assert time.monotonic() - started < 6
    assert runner.run("SELECT 1").rows == [[1]]


def test_backend_loss_preserves_schema_and_options(runner, dsns):
    runner.setup(["CREATE TABLE t(a int)", "INSERT INTO t VALUES (7)", "SET enable_hashjoin = off"])
    schema = runner.run("SELECT current_schema()").rows[0][0]
    killer = PostgresTargetRunner(dsns["target"])
    try:
        assert killer.run(f"SELECT pg_terminate_backend({runner.backend_pid})").rows == [[True]]
        lost = runner.run("SELECT * FROM t")
        assert not lost.ok and lost.is_internal_error
        assert runner.run("SELECT * FROM t").rows == [[7]]
        assert runner.run("SELECT current_schema()").rows == [[schema]]
        assert runner.run("RESET enable_hashjoin").ok
        assert runner.run("SHOW enable_hashjoin").rows == [["off"]]
        assert killer.run(f"SELECT pg_terminate_backend({runner.backend_pid})").rows == [[True]]
        runner.close()  # Reconnect even when the loss has not yet been observed.
        assert killer.run(f"SELECT count(*) FROM pg_namespace WHERE nspname = '{schema}'").rows == [[0]]
    finally:
        killer.close()


def test_setup_settings_become_reset_defaults(runner):
    settings = ["SET SESSION enable_hashjoin TO off", "SET enable_hashjoin = on",
                "SET enable_hashjoin = off", "SET work_mem TO '64kB'",
                "SET application_name = 'space and \\backslash'",
                "SET enable_mergejoin TO DEFAULT", "SET LOCAL enable_nestloop TO off"]
    assert all(error is None for _, error in runner.setup(settings))
    assert runner.run("SET enable_hashjoin = on").ok
    assert runner.run("RESET enable_hashjoin").ok
    assert runner.run("SHOW enable_hashjoin").rows == [["off"]]
    assert runner.run("RESET work_mem").ok
    assert runner.run("SHOW work_mem").rows == [["64kB"]]
    assert runner.run("RESET application_name").ok
    assert runner.run("SHOW application_name").rows == [["space and \\backslash"]]
    runner.setup([])
    assert runner.run("SHOW enable_hashjoin").rows == [["on"]]


@pytest.mark.parametrize("objects, query, expected", [
    (["CREATE TEMP TABLE tt(a int)", "INSERT INTO tt VALUES (3)"], "SELECT * FROM tt", [[3]]),
    (["CREATE TEMP VIEW tv AS SELECT 4 AS a"], "SELECT * FROM tv", [[4]]),
    (["CREATE TEMP SEQUENCE ts"], "SELECT nextval('ts')", [[1]]),
    (["PREPARE p AS SELECT 5"], "EXECUTE p", [[5]]),
    (["DECLARE c CURSOR WITH HOLD FOR SELECT 6"], "FETCH ALL FROM c", [[6]]),
    (["LISTEN s16_channel"], "SELECT * FROM pg_listening_channels()", [["s16_channel"]]),
])
def test_session_objects_prevent_reconnect(runner, objects, query, expected):
    statements = objects + ["SET enable_seqscan = off"]
    assert all(error is None for _, error in runner.setup(statements))
    assert runner.run(query).rows == expected


def test_errors_stable_and_redacted(runner, dsns):
    other = PostgresTargetRunner(dsns["target"])
    try:
        statements = ["CREATE TABLE t(a int)", "INSERT INTO t VALUES ('x')", "CREATE TABLE t(a int)"]
        first = runner.setup(statements)
        second = other.setup(statements)
        assert first == second
        assert first[1][1].startswith("InvalidTextRepresentation:")
        assert all("coevo_t_" not in error for _, error in first if error)
        assert dsns["target"] not in str(first)
        assert not runner.run("SELECT 1/0").is_internal_error
    finally:
        other.close()
