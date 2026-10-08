"""Tier-1 CVE: isolated execution, premises, reruns, and the final label."""

from __future__ import annotations

import json
import re
import time
from datetime import date
from typing import Any, Callable

import pytest

from oracles.db_runner import QueryResult
from surprise.harness.constants import CVE_RERUN_ATTEMPTS, CVE_RERUN_EXTENDED
from surprise.harness.contracts import IdentityEvidence, Label, SqlCase
from surprise.harness.cve import CVE_STEPS, behavior_shape, certify, execute_isolated
from surprise.harness.cve.premise import categories_conflict, check_premises
from surprise.harness.evaluate import evaluate_final
from surprise.harness.ledger import Ledger, LedgerError
from surprise.harness.manifest import build_manifest
from surprise.harness.oracles import judge
from targets.duckdb_runner import DuckDBRunner

import test_surprise_s04_runners as runners

_T_SETUP = (
    "CREATE TABLE t(a INTEGER, b INTEGER, c VARCHAR)",
    "INSERT INTO t VALUES (1, 10, '5'), (2, 0, 'x'), (3, -4, '7'), (NULL, 3, NULL), (5, NULL, '0')",
)
_F3_SETUP = (
    "CREATE TABLE ev(id INT, ts INT)",
    "CREATE TABLE px(id INT, ts INT, p INT)",
    "INSERT INTO ev VALUES (1,5),(1,9),(2,5)",
    "INSERT INTO px VALUES (1,5,10),(1,5,20),(1,8,30),(2,4,40)",
)
_ASOF_NO_TIES = (
    "CREATE TABLE ev(id INT, ts INT)",
    "CREATE TABLE px(id INT, ts INT, p INT)",
    "INSERT INTO ev VALUES (1,5),(1,9),(2,5)",
    "INSERT INTO px VALUES (1,5,10),(1,8,30),(2,4,40)",
)
_ASOF = (
    "SELECT px.p FROM ev ASOF JOIN px ON ev.id = px.id AND ev.ts >= px.ts "
    "ORDER BY ev.id, ev.ts, px.p"
)
_ASOF_FILTER = (
    "SELECT r.p FROM ev l ASOF JOIN px r ON l.id = r.id AND l.ts >= r.ts "
    "AND r.p > 0 ORDER BY l.id, l.ts, r.p"
)
_ASOF_SUBQUERY = (
    "SELECT * FROM (SELECT px.p FROM ev ASOF JOIN px "
    "ON ev.id = px.id AND ev.ts >= px.ts) q ORDER BY q.p"
)
_F10_SETUP = (
    "CREATE TABLE t1(id INT, ch VARCHAR, v INT)",
    "INSERT INTO t1 VALUES (1,'A',10),(2,'A',20),(3,'A',20),(4,'B',30),(5,'B',10),(6,'B',40),"
    "(7,'C',30),(NULL,'C',20)",
)
_F10_QUERY = (
    "SELECT ntile(2 ORDER BY v) OVER "
    "(ORDER BY v ROWS BETWEEN 2 FOLLOWING AND 1 FOLLOWING) FROM t1"
)
_F11_SETUP = (
    "CREATE TABLE t(a INT, b INT)",
    "INSERT INTO t VALUES (1,10),(2,20)",
    "CREATE TABLE s(a INT, b INT)",
    "INSERT INTO s VALUES (1,100)",
)
_F11_QUERY = "MERGE INTO t USING s ON t.a = s.a WHEN NOT MATCHED BY SOURCE THEN DELETE"
_WRITE_SETUP = (
    "CREATE TABLE t(a INT, b INT)",
    "INSERT INTO t VALUES (1,10),(2,20),(3,30)",
)
_HUGE = (
    "SELECT count(*) FROM range(100000000) a, range(100000000) b "
    "WHERE a.range + b.range < 0"
)
_SINGLE_THREAD = re.compile(r"\bthreads\s*(=|\bto\b)\s*1\b", re.IGNORECASE)
_RESET_THREADS = re.compile(r"\breset\s+threads\b", re.IGNORECASE)


def _shape(label: Label, isolation: str) -> dict[str, Any]:
    cve = label.cve
    assert cve["schema"] == 1
    assert cve["tier"] in (0, 1)
    assert cve["isolation"] == isolation
    raw = cve["raw"]
    assert set(raw) == {"y", "fail_kind", "invalid_reason", "identity"}
    assert raw["y"] in ("pass", "fail", "invalid")
    for name in CVE_STEPS:
        step = cve[name]
        assert step["status"] in ("ran", "skipped")
        if step["status"] == "skipped":
            assert isinstance(step["reason"], str) and step["reason"]
        else:
            assert step["reason"] is None
    json.dumps(label.to_dict())
    return cve


def _skipped(cve: dict[str, Any], reason: str) -> None:
    for name in CVE_STEPS:
        assert cve[name] == {"status": "skipped", "reason": reason}


def test_behavior_shape_and_steps() -> None:
    assert CVE_STEPS == ("rerun", "premise", "attribution", "minimize", "profile")
    assert behavior_shape({"missing": 1, "extra": 0}) == "missing_only"
    assert behavior_shape({"missing": 0, "extra": 2}) == "extra_only"
    assert behavior_shape({"missing": 1, "extra": 1}) == "both"
    assert behavior_shape({"missing": 0, "extra": 0}) == "none"
    assert behavior_shape({}) == "none"
    assert behavior_shape({"missing": True, "extra": False}) == "none"


def test_categories_conflict_on_value_kinds() -> None:
    text = [[json.dumps(["2020-01-02"]), 1]]
    temporal = [[json.dumps([["temporal", "2020-01-02T00:00:00"]]), 1]]
    number = [[json.dumps([["num", 1.0]]), 1]]
    nan = [[json.dumps(["float:nan"]), 1]]
    nulls = [[json.dumps([None]), 2]]
    assert categories_conflict(text, temporal) is True
    assert categories_conflict(number, nan) is False
    assert categories_conflict(nulls, number) is False
    assert categories_conflict([], number) is False
    assert categories_conflict([[json.dumps([1]), 1]], [[json.dumps([1, 2]), 1]]) is True


def test_asof_probe_groups_the_right_hand_key() -> None:
    seen: list[str] = []

    def probe(sql: str) -> tuple[str, Any]:
        seen.append(sql)
        return "ok", 1

    case = SqlCase("duckdb", _F3_SETUP, _ASOF)
    label = Label(
        y="fail",
        oracle="plan_variant",
        fail_kind="wrong_result",
        identity=IdentityEvidence(),
        detail={},
    )
    held = check_premises(case, "plan_variant", label, probe)
    assert held["violations"] == []
    assert seen
    runner = DuckDBRunner()
    try:
        runner.setup(list(_F3_SETUP))
        tied = runner.run(seen[0])
        runner.setup(list(_ASOF_NO_TIES))
        free = runner.run(seen[0])
    finally:
        runner.close()
    assert tied.ok and int(tied.rows[0][0]) > 1
    assert free.ok and int(free.rows[0][0]) == 1

    def tied_probe(sql: str) -> tuple[str, Any]:
        return "ok", 2

    violated = check_premises(case, "plan_variant", label, tied_probe)
    assert violated["violations"] == ["unspecified_semantics"]
    assert [item["name"] for item in violated["checks"]] == [
        "side_effecting_statement",
        "unspecified_semantics",
        "incomparable_results",
    ]


def test_unparseable_asof_is_a_violation() -> None:
    def probe(sql: str) -> tuple[str, Any]:
        raise AssertionError("an unparseable join must not be probed")

    case = SqlCase("duckdb", (), "SELECT * FROM ev ASOF JOIN (SELECT * FROM px) ON ev.id = px.id")
    label = Label(y="fail", oracle="plan_variant", fail_kind="wrong_result")
    result = check_premises(case, "plan_variant", label, probe)
    assert result["violations"] == ["unspecified_semantics"]


def _fail_label() -> Label:
    return Label(y="fail", oracle="plan_variant", fail_kind="wrong_result")


def test_asof_on_clause_must_be_join_keys_only() -> None:
    """A right-table filter, a top-level OR, or a bare column is unparseable."""
    seen: list[str] = []

    def probe(sql: str) -> tuple[str, Any]:
        seen.append(sql)
        return "ok", 1

    label = _fail_label()
    filtered = SqlCase("duckdb", _F3_SETUP, _ASOF_FILTER)
    result = check_premises(filtered, "plan_variant", label, probe)
    assert result["violations"] == ["unspecified_semantics"]
    assert seen == []

    disjunction = SqlCase(
        "duckdb", (),
        "SELECT r.p FROM ev l ASOF JOIN px r ON l.id = r.id OR l.ts >= r.ts",
    )
    bare = SqlCase(
        "duckdb", (),
        "SELECT r.p FROM ev l ASOF JOIN px r ON l.id = r.id AND l.ts >= ts",
    )
    for case in (disjunction, bare):
        again = check_premises(case, "plan_variant", label, probe)
        assert again["violations"] == ["unspecified_semantics"]
    assert seen == []


def test_asof_inside_a_subquery_still_groups_the_join_key() -> None:
    seen: list[str] = []

    def probe(sql: str) -> tuple[str, Any]:
        seen.append(sql)
        return "ok", 1

    case = SqlCase("duckdb", _F3_SETUP, _ASOF_SUBQUERY)
    held = check_premises(case, "plan_variant", _fail_label(), probe)
    assert held["violations"] == []
    assert len(seen) == 1
    group = seen[0].split("GROUP BY", 1)[1]
    assert '"id"' in group and '"ts"' in group and '"p"' not in group
    assert "ORDER BY" not in seen[0].upper()

    runner = DuckDBRunner()
    try:
        runner.setup(list(_F3_SETUP))
        tied = runner.run(seen[0])
    finally:
        runner.close()
    assert tied.ok and int(tied.rows[0][0]) > 1

    def tied_probe(sql: str) -> tuple[str, Any]:
        return "ok", int(tied.rows[0][0])

    violated = check_premises(case, "plan_variant", _fail_label(), tied_probe)
    assert violated["violations"] == ["unspecified_semantics"]


def _scripted(
    query: str,
    wrong_rows: list[list[Any]],
    correct_rows: list[list[Any]],
    *,
    reproduces: Callable[[int], bool] = lambda n: True,
    single_thread_reproduces: bool = True,
    permute: bool = False,
) -> tuple[Callable[[], Any], dict[str, Any]]:
    """Fake a plan-variant miss while ``PRAGMA disable_optimizer`` is on.

    ``reproduces(n)`` counts those default-thread executions from 1. A
    one-thread session uses ``single_thread_reproduces`` and does not count.
    """
    state: dict[str, Any] = {
        "default_runs": 0,
        "single_runs": 0,
        "hits": 0,
        "runners": 0,
        "reversed": 0,
    }

    class Scripted:
        def __init__(self) -> None:
            self._no_optimizer = False
            self._single = False
            state["runners"] += 1
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

        def setup(self, statements: Any) -> list[tuple[str, None]]:
            self._no_optimizer = False
            self._single = False
            statements = list(statements)
            for statement in statements:
                self._observe(statement)
            return [(statement, None) for statement in statements]

        def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
            self._observe(sql)
            result = QueryResult(rows=[list(row) for row in correct_rows])
            if sql.strip().rstrip(";") == query and self._no_optimizer and result.ok:
                if self._single:
                    state["single_runs"] += 1
                    fake = single_thread_reproduces
                else:
                    state["default_runs"] += 1
                    fake = reproduces(state["default_runs"])
                if fake:
                    state["hits"] += 1
                    result = QueryResult(rows=[list(row) for row in wrong_rows])
            if self._reverse and result.ok:
                result.rows = list(reversed(result.rows))
                state["reversed"] += 1
            return result

        def close(self) -> None:
            pass

    return Scripted, state


def _inline_scripted(script: dict[str, Any] | None = None) -> tuple[Label, dict[str, Any]]:
    query = "SELECT a, b FROM t WHERE a > 1"
    correct = [[2, 0], [3, -4]]
    wrong = [[2, 0]]
    options = dict(script or {})
    if options.get("permute"):
        wrong = [[2, 0], [9, 9]]
    factory, state = _scripted(query, wrong, correct, **options)
    case = SqlCase("duckdb", _T_SETUP, query)
    label = certify(case, "plan_variant", runner_factory=factory, isolation="inline")
    return label, state


def test_scripted_rerun_branches() -> None:
    label, state = _inline_scripted()
    cve = _shape(label, "inline")
    assert (label.y, label.fail_kind) == ("fail", "wrong_result")
    assert label.identity.switches == ("no_optimizer",)
    rerun = cve["rerun"]
    assert rerun["attempts"] == CVE_RERUN_ATTEMPTS
    assert rerun["reproduced"] == CVE_RERUN_ATTEMPTS
    assert rerun["stable"] is True and rerun["extended"] is False
    assert rerun["single_thread"] == {"ran": True, "reproduced": True}
    assert rerun["distinct_outcomes"] == 1
    assert cve["tier"] == 1
    assert cve["premise"]["violations"] == []
    assert cve["premise"]["status"] == "ran"
    _skipped_tail(cve)
    assert state["default_runs"] == 1 + CVE_RERUN_ATTEMPTS
    assert state["single_runs"] == 1
    assert state["runners"] == 2 * (1 + CVE_RERUN_ATTEMPTS + 1)

    again, _ = _inline_scripted()
    fresh, _ = _inline_scripted()
    assert again.to_dict() == fresh.to_dict()

    parallel, parallel_state = _inline_scripted({"single_thread_reproduces": False})
    cve = _shape(parallel, "inline")
    assert (parallel.y, parallel.fail_kind) == ("fail", "wrong_result")
    rerun = cve["rerun"]
    assert rerun["extended"] is True
    assert rerun["attempts"] == CVE_RERUN_ATTEMPTS + CVE_RERUN_EXTENDED
    assert rerun["reproduced"] == rerun["attempts"]
    assert rerun["stable"] is True
    assert rerun["single_thread"] == {"ran": True, "reproduced": False}
    assert parallel_state["single_runs"] == 1
    assert parallel_state["default_runs"] == 1 + CVE_RERUN_ATTEMPTS + CVE_RERUN_EXTENDED

    missed, _ = _inline_scripted({
        "single_thread_reproduces": False,
        "reproduces": lambda n: n != CVE_RERUN_ATTEMPTS + 3,
    })
    cve = _shape(missed, "inline")
    assert (missed.y, missed.invalid_reason) == ("invalid", "unstable_rerun")
    rerun = cve["rerun"]
    assert rerun["attempts"] == CVE_RERUN_ATTEMPTS + CVE_RERUN_EXTENDED
    assert rerun["reproduced"] == rerun["attempts"] - 1
    assert rerun["stable"] is False and rerun["extended"] is True
    assert rerun["distinct_outcomes"] == 2
    assert missed.identity == IdentityEvidence()
    assert cve["raw"]["y"] == "fail"
    assert cve["tier"] == 1

    once, _ = _inline_scripted({"reproduces": lambda n: n <= 2})
    cve = _shape(once, "inline")
    assert once.invalid_reason == "unstable_rerun"
    rerun = cve["rerun"]
    assert rerun["attempts"] == CVE_RERUN_ATTEMPTS
    assert rerun["reproduced"] == 1
    assert rerun["extended"] is False
    assert rerun["single_thread"] == {"ran": False, "reproduced": None}
    assert rerun["distinct_outcomes"] == 2

    never, never_state = _inline_scripted({"reproduces": lambda n: n == 1})
    rerun = never.cve["rerun"]
    assert never.invalid_reason == "unstable_rerun"
    assert rerun["reproduced"] == 0 and rerun["attempts"] == CVE_RERUN_ATTEMPTS
    assert never_state["single_runs"] == 0
    assert never_state["default_runs"] == 1 + CVE_RERUN_ATTEMPTS

    flipped, flipped_state = _inline_scripted({"permute": True})
    cve = _shape(flipped, "inline")
    assert (flipped.y, flipped.fail_kind) == ("fail", "wrong_result")
    assert cve["rerun"]["stable"] is True
    assert cve["rerun"]["reproduced"] == cve["rerun"]["attempts"]
    assert flipped_state["reversed"] > 0


def _skipped_tail(cve: dict[str, Any]) -> None:
    for name in ("attribution", "minimize", "profile"):
        assert cve[name] == {"status": "skipped", "reason": "not_requested"}


def test_pass_and_invalid_do_not_rerun() -> None:
    case = SqlCase("duckdb", _T_SETUP, "SELECT a, b FROM t", "a > 1")
    label = certify(case, "tlp", isolation="inline")
    cve = _shape(label, "inline")
    assert label.y == "pass" and cve["tier"] == 0
    _skipped(cve, "not_a_candidate")
    assert label.detail == judge(case, "tlp").detail
    assert certify(case, "tlp", isolation="inline").to_dict() == label.to_dict()

    query = "SELECT a FROM t"
    calls = {"n": 0}

    class Broken:
        def setup(self, statements: Any) -> list[tuple[str, None]]:
            return [(statement, None) for statement in statements]

        def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
            if sql.strip().rstrip(";") == query:
                return QueryResult(error="BinderException: missing")
            return QueryResult(rows=[])

        def close(self) -> None:
            pass

    def factory() -> Broken:
        calls["n"] += 1
        return Broken()

    invalid_case = SqlCase("duckdb", _T_SETUP, query)
    invalid = certify(invalid_case, "plan_variant", runner_factory=factory, isolation="inline")
    cve = _shape(invalid, "inline")
    assert (invalid.y, invalid.invalid_reason) == ("invalid", "query_error")
    assert cve["tier"] == 0
    _skipped(cve, "not_a_candidate")
    assert invalid.detail == judge(invalid_case, "plan_variant", runner_factory=Broken).detail
    assert calls["n"] == 2


def test_premises_on_real_statements() -> None:
    f3 = SqlCase("duckdb", _F3_SETUP, _ASOF)
    tied = certify(f3, "plan_variant", isolation="inline")
    cve = _shape(tied, "inline")
    assert (tied.y, tied.invalid_reason) == ("invalid", "unspecified_semantics")
    assert cve["tier"] == 1 and cve["raw"]["y"] == "fail"
    assert cve["premise"]["violations"] == ["unspecified_semantics"]
    assert cve["rerun"] == {"status": "skipped", "reason": "premise_violated"}
    assert tied.identity == IdentityEvidence()

    factory, _state = _duckdb_scripted(_ASOF, [[10], [30]])
    free = certify(
        SqlCase("duckdb", _ASOF_NO_TIES, _ASOF),
        "plan_variant",
        runner_factory=factory,
        isolation="inline",
    )
    cve = _shape(free, "inline")
    assert (free.y, free.fail_kind) == ("fail", "wrong_result")
    assert cve["premise"]["violations"] == []
    assert cve["rerun"]["status"] == "ran"

    # r.p > 0 is not a join key. Tied or not, the ON clause is unparseable.
    filtered = certify(SqlCase("duckdb", _F3_SETUP, _ASOF_FILTER), "plan_variant", isolation="inline")
    cve = _shape(filtered, "inline")
    assert (filtered.y, filtered.invalid_reason) == ("invalid", "unspecified_semantics")
    assert cve["tier"] == 1 and cve["raw"]["y"] == "fail"
    assert cve["rerun"] == {"status": "skipped", "reason": "premise_violated"}

    filtered_factory, _filtered_state = _duckdb_scripted(_ASOF_FILTER, [[10], [30]])
    filtered_free = certify(
        SqlCase("duckdb", _ASOF_NO_TIES, _ASOF_FILTER),
        "plan_variant",
        runner_factory=filtered_factory,
        isolation="inline",
    )
    cve = _shape(filtered_free, "inline")
    assert (filtered_free.y, filtered_free.invalid_reason) == ("invalid", "unspecified_semantics")
    assert cve["raw"]["y"] == "fail"
    assert cve["rerun"]["status"] == "skipped"

    deleted = certify(
        SqlCase("duckdb", _WRITE_SETUP, "DELETE FROM t WHERE a = 1 RETURNING a"),
        "plan_variant",
        isolation="inline",
    )
    assert deleted.invalid_reason == "side_effecting_statement"
    assert deleted.cve["rerun"]["status"] == "skipped"
    assert deleted.cve["premise"]["violations"] == ["side_effecting_statement"]

    updated = certify(
        SqlCase("duckdb", _WRITE_SETUP, "UPDATE t SET b = b + 1 WHERE a = 2 RETURNING b"),
        "plan_variant",
        isolation="inline",
    )
    assert updated.invalid_reason == "side_effecting_statement"

    dated = certify(
        SqlCase("datafusion", (), "SELECT DATE '2020-01-02' AS d"),
        "cross_dbms",
        isolation="inline",
    )
    cve = _shape(dated, "inline")
    assert dated.invalid_reason == "incomparable_results"
    assert cve["premise"]["violations"] == ["incomparable_results"]
    assert cve["rerun"]["status"] == "skipped"
    assert cve["raw"]["y"] == "fail"


def test_writing_crash_and_comparable_numbers_stay_fail() -> None:
    class CrashWrite:
        def __init__(self) -> None:
            self._no_optimizer = False

        def setup(self, statements: Any) -> list[tuple[str, None]]:
            self._no_optimizer = False
            return [(statement, None) for statement in statements]

        def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
            if sql.strip().upper().startswith("PRAGMA DISABLE_OPTIMIZER"):
                self._no_optimizer = True
                return QueryResult(rows=[])
            if sql.strip().upper().startswith("DELETE") and self._no_optimizer:
                return QueryResult(error="INTERNAL Error: boom", is_internal_error=True)
            if sql.strip().upper().startswith("DELETE"):
                return QueryResult(rows=[[1]])
            return QueryResult(rows=[])

        def close(self) -> None:
            pass

    crashed = certify(
        SqlCase("duckdb", _WRITE_SETUP, "DELETE FROM t WHERE a = 1 RETURNING a"),
        "plan_variant",
        runner_factory=CrashWrite,
        isolation="inline",
    )
    assert (crashed.y, crashed.fail_kind) == ("fail", "crash")
    assert crashed.cve["premise"]["violations"] == []
    assert crashed.cve["rerun"]["stable"] is True

    class Target:
        engine_version = "target"

        def setup(self, statements: Any) -> list[tuple[str, None]]:
            return [(statement, None) for statement in statements]

        def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
            if "SELECT" in sql.upper():
                return QueryResult(rows=[[None], [None]])
            return QueryResult(rows=[])

        def close(self) -> None:
            pass

    class Reference:
        engine_version = "reference"

        def setup(self, statements: Any) -> list[tuple[str, None]]:
            return [(statement, None) for statement in statements]

        def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
            if "SELECT" in sql.upper():
                return QueryResult(rows=[[1], [2], [None]])
            return QueryResult(rows=[])

        def close(self) -> None:
            pass

    compared = certify(
        SqlCase("datafusion", (), "SELECT v FROM t"),
        "cross_dbms",
        isolation="inline",
        runner_factory=Target,
        reference_factories={"duckdb": Reference, "postgres": Reference, "sqlite": Reference},
    )
    assert (compared.y, compared.fail_kind) == ("fail", "wrong_result")
    assert compared.cve["premise"]["violations"] == []

    class TextTarget(Target):
        def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
            if "SELECT" in sql.upper():
                return QueryResult(rows=[["2020-01-02"]])
            return QueryResult(rows=[])

    class TemporalReference(Reference):
        def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
            if "SELECT" in sql.upper():
                return QueryResult(rows=[[date(2020, 1, 2)]])
            return QueryResult(rows=[])

    text = certify(
        SqlCase("datafusion", (), "SELECT d FROM t"),
        "cross_dbms",
        isolation="inline",
        runner_factory=TextTarget,
        reference_factories={
            "duckdb": TemporalReference,
            "postgres": TemporalReference,
            "sqlite": TemporalReference,
        },
    )
    assert text.invalid_reason == "incomparable_results"
    assert text.cve["rerun"]["status"] == "skipped"


def _duckdb_scripted(query: str, wrong_rows: list[list[Any]]) -> tuple[Callable[[], Any], dict[str, Any]]:
    state: dict[str, Any] = {"hits": 0}

    class Scripted:
        def __init__(self) -> None:
            self._inner = DuckDBRunner()
            self._no_optimizer = False
            self._single = False

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
            self._no_optimizer = False
            self._single = False
            return self._inner.setup(list(statements))

        def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
            self._observe(sql)
            result = self._inner.run(sql, timeout_s=timeout_s)
            if sql.strip().rstrip(";") == query and self._no_optimizer and result.ok:
                state["hits"] += 1
                result = QueryResult(rows=[list(row) for row in wrong_rows], columns=list(result.columns))
            return result

        def close(self) -> None:
            self._inner.close()

        def __getattr__(self, name: str) -> Any:
            return getattr(self._inner, name)

    return Scripted, state


def test_execute_isolated_statuses_and_prelude() -> None:
    plain = SqlCase("duckdb", _T_SETUP, "SELECT a, b FROM t")
    done = execute_isolated(plain)
    assert done.status == "ok" and done.error is None and done.exit_code is None
    local = DuckDBRunner()
    try:
        local.setup(list(plain.setup))
        expected = local.run("SELECT a, b FROM t")
    finally:
        local.close()
    assert QueryResult(rows=done.rows).bag() == expected.bag()
    json.dumps(done.to_dict())

    broken = execute_isolated(SqlCase("duckdb", _T_SETUP, "SELECT missing FROM t"))
    assert broken.status == "error" and broken.rows == [] and broken.exit_code is None
    assert "Binder" in (broken.error or "")

    started = time.monotonic()
    hung = execute_isolated(SqlCase("duckdb", (), _HUGE), timeout_s=120.0, wall_timeout_s=3.0)
    assert hung.status == "timeout" and hung.rows == []
    assert time.monotonic() - started < 30

    interrupted = execute_isolated(SqlCase("duckdb", (), _HUGE), timeout_s=1.0, wall_timeout_s=60.0)
    assert interrupted.status == "timeout"

    dead = execute_isolated(SqlCase("duckdb", _F10_SETUP, _F10_QUERY))
    assert dead.status == "crash" and dead.rows == [] and dead.exit_code not in (None, 0)

    silent = execute_isolated(
        SqlCase("duckdb", (), f"SELECT {runners.ZERO_EXIT_MARK}"),
        runner_factory=runners.ZeroExitRunner,
    )
    assert silent.status == "crash" and silent.rows == [] and silent.exit_code == 0

    merge = SqlCase("duckdb", _F11_SETUP, _F11_QUERY)
    assert execute_isolated(merge).status == "ok"
    forced = execute_isolated(merge, prelude=("SET disabled_optimizers='build_side_probe_side'",))
    assert forced.status == "error" and "INTERNAL" in (forced.error or "")


def test_process_isolation_pass_crash_hang_and_reference() -> None:
    runners.OkTarget.calls.clear()
    case = SqlCase("duckdb", (), "SELECT 1")
    first = certify(case, "plan_variant", runner_factory=runners.OkTarget)
    second = certify(case, "plan_variant", runner_factory=runners.OkTarget)
    assert first.to_dict() == second.to_dict()
    cve = _shape(first, "process")
    assert first.y == "pass" and cve["tier"] == 0
    _skipped(cve, "not_a_candidate")
    assert runners.OkTarget.calls == []

    crashing = SqlCase("duckdb", _T_SETUP, f"SELECT a FROM t WHERE a > {runners.EXIT_MARK}")
    crashed = certify(crashing, "plan_variant", runner_factory=runners.ExitingRunner)
    cve = _shape(crashed, "process")
    assert (crashed.y, crashed.fail_kind) == ("fail", "crash")
    assert crashed.identity.error_class == "ProcessExit"
    assert crashed.identity.behavior == {"exit_code": runners.EXIT_CODE}
    assert cve["tier"] == 1 and cve["rerun"]["stable"] is True
    assert cve["rerun"]["reproduced"] == cve["rerun"]["attempts"] == CVE_RERUN_ATTEMPTS
    assert cve["premise"]["violations"] == []

    started = time.monotonic()
    hung = certify(
        SqlCase("duckdb", _T_SETUP, f"SELECT a FROM t WHERE a > {runners.SLEEP_MARK}"),
        "plan_variant",
        runner_factory=runners.SleepingRunner,
        wall_timeout_s=3.0,
    )
    cve = _shape(hung, "process")
    assert (hung.y, hung.invalid_reason) == ("invalid", "timeout")
    assert cve["tier"] == 0 and cve["raw"]["invalid_reason"] == "timeout"
    _skipped(cve, "timeout")
    assert time.monotonic() - started < 20

    orphan = certify(
        SqlCase("datafusion", (), "SELECT 1"),
        "cross_dbms",
        runner_factory=runners.OkTarget,
        reference_factories={"duckdb": runners.ExitingReference, "postgres": runners.AgreeReference},
    )
    cve = _shape(orphan, "process")
    assert orphan.invalid_reason == "unattributed_crash"
    assert orphan.identity == IdentityEvidence()
    assert cve["tier"] == 1 and cve["raw"]["y"] == "fail"
    assert cve["raw"]["identity"]["error_class"] == "ProcessExit"
    _skipped(cve, "unattributed_crash")


def test_child_does_not_inherit_the_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "unit-test-dummy")
    done = execute_isolated(SqlCase("duckdb", (), "SELECT 1"), runner_factory=runners.KeyProbe)
    assert done.status == "ok"
    assert done.rows == [[0]]


def test_rejected_requests_do_not_execute() -> None:
    opened: list[int] = []

    def never() -> Any:
        opened.append(1)
        raise AssertionError("factory must not be called")

    case = SqlCase("duckdb", (), "SELECT 1")
    with pytest.raises(ValueError):
        execute_isolated(case, runner_factory=never)
    with pytest.raises(ValueError):
        certify(case, "no_such_oracle", isolation="inline", runner_factory=never)
    with pytest.raises(ValueError):
        certify(case, "tlp", isolation="thread", runner_factory=never)
    with pytest.raises(ValueError):
        certify(case, "tlp", runner_factory=never)
    with pytest.raises(NotImplementedError):
        certify(case, "tlp", hypothesis={"id": "later"}, isolation="inline", runner_factory=never)
    with pytest.raises(NotImplementedError):
        certify(case, "tlp", diagnose=True, isolation="inline", runner_factory=never)
    assert opened == []


def test_evaluate_final_ledger(tmp_path: Any) -> None:
    ledger = Ledger(tmp_path / "ledger.sqlite")
    try:
        ledger.start_run("run-1", {"source": "s04"})
        case = SqlCase("duckdb", _T_SETUP, "SELECT a, b FROM t", "a > 1")
        record = evaluate_final(
            case, "tlp", ledger=ledger, run_id="run-1", purpose="explore", isolation="inline",
        )
        assert ledger.count(run_id="run-1") == 1
        assert record.label.y == "pass"
        assert record.label.cve["schema"] == 1
        assert ledger.records(run_id="run-1") == [record]

        def explode() -> Any:
            raise RuntimeError("runner exploded")

        broken = evaluate_final(
            case, "tlp", ledger=ledger, run_id="run-1", purpose="explore",
            runner_factory=explode, isolation="inline",
        )
        assert ledger.count(run_id="run-1") == 2
        assert (broken.label.y, broken.label.invalid_reason) == ("invalid", "harness_error")
        assert broken.label.cve["tier"] == 0
        assert broken.label.cve["raw"]["invalid_reason"] == "harness_error"
        _skipped(broken.label.cve, "harness_error")
        assert broken.label.detail["exception"].startswith("RuntimeError:")

        before = ledger.count()
        with pytest.raises(ValueError):
            evaluate_final(case, "tlp", ledger=ledger, run_id="run-1", purpose="", isolation="inline")
        with pytest.raises(ValueError):
            evaluate_final(
                case, "tlp", ledger=ledger, run_id="run-1", purpose="explore",
                p_t=1.5, isolation="inline",
            )
        with pytest.raises(LedgerError):
            evaluate_final(
                case, "tlp", ledger=ledger, run_id="never-started", purpose="explore",
                isolation="inline",
            )
        with pytest.raises(NotImplementedError):
            evaluate_final(
                case, "tlp", ledger=ledger, run_id="run-1", purpose="explore",
                diagnose=True, isolation="inline",
            )
        with pytest.raises(ValueError):
            evaluate_final(
                case, "tlp", ledger=ledger, run_id="run-1", purpose="explore",
                runner_factory=explode, isolation="process",
            )
        assert ledger.count() == before
    finally:
        ledger.close()


def test_manifest_environment_fields() -> None:
    environment = build_manifest("s04-unit")["environment"]
    assert environment["old_engines"] == {"duckdb": "1.1.3", "datafusion": "50.0.0"}
    postgres = environment["references"]["postgres"]
    assert isinstance(postgres, str) and postgres.startswith("16.")
    packages = environment["packages"]
    for name in ("duckdb", "datafusion", "pyarrow", "psycopg2-binary"):
        assert isinstance(packages.get(name), str) and packages[name]
    for key in ("python", "platform", "engines"):
        assert key in environment
