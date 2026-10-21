"""Native PostgreSQL oracle and CVE contracts on disposable 16.15/15.19 servers."""

import json
import subprocess

import pytest

from oracles.db_runner import QueryResult
from surprise.experiments import pg_instance
from surprise.harness import manifest
from surprise.harness.contracts import SqlCase
from surprise.harness.cve.certify import _single_thread_prelude
from surprise.harness.cve.tier3 import _version_ladder
from surprise.harness.oracles import judge
from surprise.harness.oracles.index_presence import judge_case as judge_index
from surprise.harness.oracles.pg_target import OLD_DSN_ENV, TARGET_DSN_ENV, PostgresTargetRunner
from surprise.harness.oracles.registry import OracleOptions
from surprise.harness.oracles.version_differential import _query_old_postgres


SETUP = (
    "CREATE TABLE t(a int, b text)",
    "INSERT INTO t VALUES (1, 'one'), (2, 'two'), (3, 'three')",
)
QUERY = "SELECT a, b FROM t WHERE a = 2"


@pytest.fixture(scope="module")
def dsns(tmp_path_factory):
    with pg_instance.running(tmp_path_factory.mktemp("s16-oracles")) as values:
        yield values


def index(case=None, factory=PostgresTargetRunner):
    return judge_index(case or SqlCase("postgres", SETUP, QUERY), factory=factory,
                       timeout_s=2, options=OracleOptions())


class IndexedFailure(PostgresTargetRunner):
    """Only corrupt a SELECT while the real server has a variant index."""

    fault = "rows"

    def run(self, statement, timeout_s=10):
        result = super().run(statement, timeout_s=timeout_s)
        if statement == QUERY and result.ok:
            indexes = super().run(
                "SELECT count(*) FROM pg_indexes WHERE schemaname = current_schema()",
                timeout_s=timeout_s,
            )
            assert indexes.ok
            if indexes.rows[0][0]:
                if self.fault == "rows":
                    result.rows = []
                elif self.fault == "timeout":
                    return QueryResult(error="TimeoutError: injected", timed_out=True)
                elif self.fault == "value":
                    return QueryResult(error="DivisionByZero: division by zero")
                elif self.fault == "crash":
                    return QueryResult(error="InternalError: injected", is_internal_error=True)
                else:
                    return QueryResult(error="UndefinedFunction: injected")
        return result


def test_native_indexes_and_wrong_result(dsns):
    passed = judge(SqlCase("postgres", SETUP, QUERY), "index_presence")
    assert passed.y == "pass"
    assert len(passed.detail["index_variants_compared"]) >= 4
    assert passed.detail["index_variants_compared"][0] == "t.btree_a"
    failed = judge(SqlCase("postgres", SETUP, QUERY), "index_presence", runner_factory=IndexedFailure)
    assert failed.y == "fail" and failed.fail_kind == "wrong_result"
    assert failed.identity.switches == ("t.btree_a",)
    assert failed.identity.behavior == {"missing": 1, "extra": 0}
    assert failed.detail["index_variants_compared"] == ["t.btree_a"]


@pytest.mark.parametrize("fault,kind,reason", [
    ("crash", "crash", None), ("error", "error_mismatch", None),
    ("timeout", None, "timeout"), ("value", None, "value_error"),
])
def test_index_variant_failures_and_skips(dsns, fault, kind, reason):
    class Fault(IndexedFailure):
        pass

    Fault.fault = fault
    instances = []

    def factory():
        runner = Fault()
        instances.append(runner)
        return runner

    label = index(factory=factory)
    if kind:
        assert label.y == "fail" and label.fail_kind == kind
        assert label.identity.switches == ("t.btree_a",)
    else:
        assert label.y == "invalid" and label.invalid_reason == "not_applicable"
        assert label.detail["applicability"] == "no_index_path"
        assert any(item["reason"] == reason for item in label.detail["index_variants_skipped"])
    assert all(runner.backend_pid is None and runner._schema is None for runner in instances)


@pytest.mark.parametrize("case,reason,applicability", [
    (SqlCase("postgres", (), "SELECT 1"), "not_applicable", "no_base_table"),
    (SqlCase("postgres", SETUP, "DELETE FROM t"), "not_applicable", "not_select"),
    (SqlCase("postgres", SETUP, "SELECT 1"), "not_applicable", "no_index_path"),
    (SqlCase("postgres", ("CREATE TABLE t(a missing_type)",), "SELECT * FROM t"), "setup_error", None),
    (SqlCase("postgres", SETUP, "SELECT 1 / (a-a) FROM t"), "value_dependent_error", None),
    (SqlCase("postgres", SETUP, "SELECT missing FROM t"), "query_error", None),
])
def test_index_invalid_cases(dsns, case, reason, applicability):
    label = index(case)
    assert label.y == "invalid" and label.invalid_reason == reason
    if applicability:
        assert label.detail["applicability"] == applicability
    assert label.detail["index_variants_compared"] == []


def test_index_setup_failure_always_tears_down(dsns):
    runners = []

    class RejectSetting(PostgresTargetRunner):
        cleaned = []

        def run(self, statement, timeout_s=10):
            if statement == "SET enable_seqscan = off":
                return QueryResult(error="InsufficientPrivilege: injected")
            if statement.startswith("DROP INDEX"):
                self.cleaned.append(statement)
            return super().run(statement, timeout_s=timeout_s)

    def factory():
        runner = RejectSetting()
        runners.append(runner)
        return runner

    label = index(factory=factory)
    assert label.y == "invalid" and label.invalid_reason == "not_applicable"
    assert any(item["reason"] == "setup_failed" for item in label.detail["index_variants_skipped"])
    assert len(runners[0].cleaned) >= 4


def test_version_agreement_and_ignored_python(dsns):
    label = judge(SqlCase("postgres", SETUP, QUERY), "version_differential", old_python="missing.exe")
    assert label.y == "pass"
    assert label.detail["old_version"] == "15.19"
    assert label.detail["new_version"] == "16.15"
    assert label.detail["old_rows"] == label.detail["new_rows"] == [[2, "two"]]


@pytest.mark.parametrize("query,reason", [
    ("SELECT '1_000'::int", "value_dependent_error"),
    ("SELECT current_setting('server_version_num')", "direction_unknown"),
])
def test_version_splits(dsns, query, reason):
    label = judge(SqlCase("postgres", (), query), "version_differential")
    assert label.y == "invalid" and label.invalid_reason == reason
    assert label.detail["old_version"] == "15.19"


def test_missing_old_server(dsns, monkeypatch):
    monkeypatch.delenv(OLD_DSN_ENV)
    label = judge(SqlCase("postgres", SETUP, QUERY), "version_differential")
    assert label.y == "invalid" and label.invalid_reason == "harness_error"
    assert label.detail["error"] == "old server is missing"
    assert _version_ladder("postgres", [], "SELECT 1", [[1]], 2) == "unavailable"


def test_old_server_results_errors_timeout(dsns):
    result = _query_old_postgres(list(SETUP), QUERY, 2)
    assert result.version == "15.19" and result.rows == [[2, "two"]]
    assert result.error is None and result.setup_error is None and result.protocol_error is None
    setup = _query_old_postgres(["CREATE TABLE t(a missing_type)"], "SELECT 1", 2)
    assert setup.setup_error and setup.error is None
    query = _query_old_postgres([], "SELECT missing", 2)
    assert query.error and query.setup_error is None
    with pytest.raises(subprocess.TimeoutExpired):
        _query_old_postgres([], "SELECT pg_sleep(1)", 0.01)


def test_single_thread_and_version_ladder(dsns):
    assert _single_thread_prelude("postgres") == ("SET max_parallel_workers_per_gather = 0",)
    assert _version_ladder("postgres", list(SETUP), QUERY, [[2, "two"]], 2) == "longstanding"
    assert _version_ladder("postgres", list(SETUP), QUERY, [], 2) == "recent"
    assert _version_ladder("postgres", [], "SELECT '1_000'::int", [[1000]], 2) == "recent"
    assert _version_ladder("postgres", [], "SELECT FROM", [], 2) == "unknown"
    assert _version_ladder("postgres", ["SELECT missing"], "SELECT 1", [[1]], 2) == "unknown"


def test_manifest_optional_pg_versions(dsns, monkeypatch):
    present = manifest.build_manifest("pg")
    env = present["environment"]
    assert env["engines"]["postgres"] == "16.15"
    assert env["old_engines"]["postgres"] == "15.19"
    serialized = json.dumps(present)
    assert all(dsn not in serialized for dsn in dsns.values())
    monkeypatch.delenv(TARGET_DSN_ENV)
    target_missing = manifest.build_manifest("pg")
    assert "postgres" not in target_missing["environment"]["engines"]
    assert target_missing["environment"]["old_engines"]["postgres"] == "15.19"
    monkeypatch.delenv(OLD_DSN_ENV)
    absent = manifest.build_manifest("pg")["environment"]
    assert set(absent["engines"]) == {"duckdb", "datafusion", "sqlite"}
    assert set(absent["old_engines"]) == {"duckdb", "datafusion"}
    assert absent == {**env, "engines": {k: v for k, v in env["engines"].items() if k != "postgres"},
                      "old_engines": {k: v for k, v in env["old_engines"].items() if k != "postgres"}}
    for name in (TARGET_DSN_ENV, OLD_DSN_ENV):
        monkeypatch.setenv(name, "host=127.0.0.1 port=1 connect_timeout=1")
        assert manifest._target_postgres_version(name) == {"postgres": None}
    result = _query_old_postgres([], "SELECT 1", 2)
    assert result.protocol_error == "old server execution failed"
    assert _version_ladder("postgres", [], "SELECT 1", [[1]], 2) == "unknown"
