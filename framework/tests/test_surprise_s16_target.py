"""The PG target runner contract against real 16.15 and 15.19 servers."""

import time
from types import SimpleNamespace

import psycopg2
from psycopg2 import sql
import pytest

from surprise.experiments import pg_instance
from surprise.harness.oracles import pg_target
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


@pytest.mark.parametrize("value", [None, ""])
def test_default_factory_requires_configured_target(monkeypatch, value):
    if value is None:
        monkeypatch.delenv(TARGET_DSN_ENV, raising=False)
    else:
        monkeypatch.setenv(TARGET_DSN_ENV, value)
    with pytest.raises(ValueError, match=TARGET_DSN_ENV) as caught:
        runner_factory_for("postgres")
    assert "surprise.experiments.pg_instance" in str(caught.value)
    assert "passfile=" not in str(caught.value)
    assert TARGET_ENGINES == ("duckdb", "datafusion", "postgres")


def test_default_factory_with_dsn_returns_class_without_exposing_it(monkeypatch):
    marker = "configured-target-dsn-marker"
    monkeypatch.setenv(TARGET_DSN_ENV, marker)
    factory = runner_factory_for("postgres")
    assert factory is PostgresTargetRunner
    assert marker not in repr(factory())


@pytest.fixture
def retry_clock(monkeypatch):
    clock = SimpleNamespace(elapsed=0.0, pauses=[])

    def sleep(seconds):
        clock.pauses.append(seconds)
        clock.elapsed += seconds

    monkeypatch.setattr(pg_target, "time", SimpleNamespace(
        monotonic=lambda: clock.elapsed, sleep=sleep,
    ))
    return clock


def test_reconnect_retries_recovery_and_restores_session(runner, monkeypatch, retry_clock):
    assert all(error is None for _, error in runner.setup([
        "CREATE TABLE retry_t(a int)", "INSERT INTO retry_t VALUES (7)",
        "SET enable_hashjoin = off",
    ]))
    # _connect runs outside the query worker, so fake only its clock, not SQL.
    schema = runner._schema
    runner._conn.close()
    real_connect = psycopg2.connect
    calls = []
    failures = ["the database system is in recovery mode",
                "the database system is starting up", "Connection refused"]

    def recovering_connect(dsn, **kwargs):
        calls.append(kwargs)
        if len(calls) <= len(failures):
            raise psycopg2.OperationalError(failures[len(calls) - 1])
        return real_connect(dsn, **kwargs)

    monkeypatch.setattr(psycopg2, "connect", recovering_connect)
    connection = runner._connect()
    assert connection.autocommit
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_schema(), current_setting('enable_hashjoin'), a FROM retry_t")
        assert cursor.fetchall() == [(schema, "off", 7)]
    assert len(calls) == 4 and retry_clock.pauses == [0.5, 0.5, 0.5]
    assert all(1 <= call["connect_timeout"] <= 10 for call in calls)
    assert all("enable_hashjoin=off" in call["options"] for call in calls)
    assert not runner._lost


@pytest.mark.parametrize("message", [
    "the database system is in recovery mode", "the database system is starting up",
    "Connection refused",
])
def test_connection_retries_stop_at_thirty_seconds(monkeypatch, retry_clock, message):
    candidate = PostgresTargetRunner("host=127.0.0.1 dbname=postgres")
    calls = []

    def unavailable(*args, **kwargs):
        calls.append(kwargs)
        raise psycopg2.OperationalError(message)

    monkeypatch.setattr(psycopg2, "connect", unavailable)
    with pytest.raises(psycopg2.OperationalError, match=message):
        candidate._connect()
    assert retry_clock.elapsed == 30.0
    assert len(calls) == 60 and retry_clock.pauses == [0.5] * 60
    assert candidate._conn is None and candidate._lost
    candidate.close()


def test_connect_timeout_respects_remaining_retry_budget(monkeypatch, retry_clock):
    candidate = PostgresTargetRunner("host=127.0.0.1 dbname=postgres")
    timeouts = []

    def unavailable(*args, **kwargs):
        timeouts.append(kwargs["connect_timeout"])
        retry_clock.elapsed += kwargs["connect_timeout"]
        raise psycopg2.OperationalError("Connection refused")

    monkeypatch.setattr(psycopg2, "connect", unavailable)
    with pytest.raises(psycopg2.OperationalError, match="Connection refused"):
        candidate._connect()
    assert timeouts == [10, 10, 9]
    assert retry_clock.elapsed == 30.0
    candidate.close()


@pytest.mark.parametrize("message", [
    "password authentication failed for user coevo_target", "no password supplied",
    "no pg_hba.conf entry for host", "pg_hba.conf rejects connection for host",
])
def test_authentication_failure_does_not_retry(monkeypatch, retry_clock, message):
    candidate = PostgresTargetRunner("host=127.0.0.1 dbname=postgres")
    calls = []

    def rejected(*args, **kwargs):
        calls.append(kwargs)
        raise psycopg2.OperationalError(message)

    monkeypatch.setattr(psycopg2, "connect", rejected)
    with pytest.raises(psycopg2.OperationalError, match=message):
        candidate._connect()
    assert len(calls) == 1 and retry_clock.pauses == []
    assert candidate._conn is None
    candidate.close()


@pytest.mark.parametrize("detected", [False, True])
def test_close_during_recovery_never_raises(runner, dsns, monkeypatch, retry_clock, detected):
    # Keep real SQL and a real killed backend; inject only the recovery interval.
    runner._ensure_schema()
    schema = runner._schema
    original_connection = runner._conn
    real_connect = psycopg2.connect
    killer = real_connect(dsns["target"])
    killer.autocommit = True
    try:
        with killer.cursor() as cursor:
            cursor.execute("SELECT pg_terminate_backend(%s)", (runner.backend_pid,))
            assert cursor.fetchone() == (True,)
        if detected:
            try:
                with original_connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
            except psycopg2.OperationalError:
                runner._lost = True
            assert runner._lost
        attempts = []

        def recovering(*args, **kwargs):
            attempts.append(kwargs)
            raise psycopg2.OperationalError("the database system is in recovery mode")

        with monkeypatch.context() as fault:
            fault.setattr(psycopg2, "connect", recovering)
            runner.close()
            runner.close()
        assert len(attempts) == 60 and retry_clock.elapsed == 30.0
        assert original_connection.closed and runner._conn is None
        assert runner._schema is None and runner.backend_pid is None
        with killer.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_namespace WHERE nspname = %s", (schema,))
            assert cursor.fetchone() == (1,)  # Residue is allowed when recovery prevents cleanup.
            cursor.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
    finally:
        killer.close()


def test_close_suppresses_connection_close_failure():
    candidate = PostgresTargetRunner("host=127.0.0.1 dbname=postgres")
    attempts = []

    def broken_close():
        attempts.append(True)
        raise RuntimeError("connection close failed")

    candidate._conn = SimpleNamespace(close=broken_close)
    candidate.close()
    candidate.close()
    assert attempts == [True] and candidate._conn is None
