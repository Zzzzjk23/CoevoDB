"""Adapters for TLP, NoREC, and plan variant: forms, three-valued labels, stability."""

from __future__ import annotations

import copy
import json

import pytest

from oracles.db_runner import QueryResult
from oracles.plan_variant import PlanVariantOracle
from surprise.gates.s02_cases import CASES
from surprise.harness.contracts import SqlCase
from surprise.harness.oracles import IMPLEMENTED, judge
from surprise.harness.oracles.forms import full_query, split_grouped
from targets.duckdb_runner import DuckDBRunner

_SETUP = (
    "CREATE TABLE t(a INTEGER, b INTEGER, c VARCHAR)",
    "INSERT INTO t VALUES (1, 10, '5'), (2, 0, 'x'), (3, -4, '7'), (NULL, 3, NULL), (5, NULL, '0')",
)


def _case(query: str, predicate: str | None = "a > 1", setup: tuple[str, ...] = _SETUP,
          engine: str = "duckdb") -> SqlCase:
    return SqlCase(engine=engine, setup=setup, query=query, predicate=predicate)


def _named(name: str) -> SqlCase:
    setup, query, predicate = CASES[name]
    return SqlCase(engine="duckdb", setup=setup, query=query, predicate=predicate)


class _Injecting:
    """Real DuckDB runner that answers selected statements with a canned result."""

    def __init__(self, when, result: QueryResult) -> None:
        self._inner = DuckDBRunner()
        self._when = when
        self._result = result
        self.no_optimizer = False
        self.closed = 0

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        stripped = sql.strip().upper()
        if stripped.startswith("PRAGMA DISABLE_OPTIMIZER"):
            self.no_optimizer = True
        elif stripped.startswith("PRAGMA ENABLE_OPTIMIZER"):
            self.no_optimizer = False
        if self._when(self, sql):
            return copy.copy(self._result)
        return self._inner.run(sql, timeout_s=timeout_s)

    def close(self) -> None:
        self.closed += 1
        self._inner.close()

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


def _factory(when, result: QueryResult, created: list | None = None):
    def factory():
        runner = _Injecting(when, result)
        if created is not None:
            created.append(runner)
        return runner

    return factory


def _internal() -> QueryResult:
    return QueryResult(error="InternalException: INTERNAL Error: injected", is_internal_error=True)


def _binder() -> QueryResult:
    return QueryResult(error="BinderException: Binder Error: injected")


def _timeout() -> QueryResult:
    return QueryResult(error="TimeoutError: injected", timed_out=True)


def _kind(label) -> str | None:
    return label.fail_kind if label.y == "fail" else label.invalid_reason


# ---- forms ------------------------------------------------------------------


def test_split_grouped_accepts_group_by_and_distinct_shapes() -> None:
    plain = split_grouped("SELECT b FROM t GROUP BY b")
    assert plain is not None
    assert (plain.select_list, plain.from_tail, plain.group_by, plain.base_where) == (
        "b", "FROM t", "b", None,
    )

    folded = split_grouped("  select B, c from t where b IS NOT NULL group by b, c; ")
    assert folded is not None
    assert folded.select_list == "B, c"
    assert folded.from_tail == "from t"
    assert folded.group_by == "b, c"
    assert folded.base_where == "b IS NOT NULL"

    quoted = split_grouped("SELECT c FROM t WHERE c <> 'GROUP BY' GROUP BY c")
    assert quoted is not None
    assert quoted.base_where == "c <> 'GROUP BY'"

    nested = split_grouped("SELECT b FROM (SELECT b FROM t WHERE a > 0) s GROUP BY b")
    assert nested is not None
    assert nested.base_where is None
    assert "WHERE a > 0" in nested.from_tail

    distinct = split_grouped("SELECT DISTINCT c FROM t WHERE a > 1")
    assert distinct is not None
    assert distinct.group_by is None
    assert distinct.select_list == "c"
    assert distinct.from_tail == "FROM t"
    assert distinct.base_where == "a > 1"

    bare_distinct = split_grouped("SELECT DISTINCT c FROM t;")
    assert bare_distinct is not None
    assert bare_distinct.base_where is None


def test_split_grouped_rejects_other_shapes() -> None:
    rejected = [
        "SELECT a FROM t",
        "SELECT b, COUNT(*) FROM t GROUP BY b",
        "SELECT b FROM t GROUP BY c",
        "SELECT DISTINCT ON (c) c FROM t",
        "SELECT DISTINCT c FROM t GROUP BY c",
        "SELECT b FROM t GROUP BY b ORDER BY b",
        "SELECT b FROM t GROUP BY b HAVING b > 0",
        "SELECT b FROM t GROUP BY b LIMIT 1",
        "SELECT b FROM t GROUP BY b UNION SELECT b FROM t GROUP BY b",
        "WITH s AS (SELECT b FROM t) SELECT b FROM s GROUP BY b",
        "SELECT row_number() OVER () AS b FROM t GROUP BY b",
        "",
        "SELECT FROM t GROUP BY",
    ]
    for query in rejected:
        assert split_grouped(query) is None, query


def test_full_query_covers_absent_predicate_grouped_and_injected_where() -> None:
    untouched = _case("SELECT b FROM t GROUP BY b", None)
    assert full_query(untouched) == untouched.query
    assert full_query(_case("SELECT a, b FROM t", "   ")) == "SELECT a, b FROM t"

    grouped = _case("SELECT b FROM t GROUP BY b", "a > 1")
    assert full_query(grouped) == "SELECT b FROM t WHERE (a > 1) GROUP BY b"
    both = _case("SELECT b, c FROM t WHERE b IS NOT NULL GROUP BY b, c", "a > 1")
    assert full_query(both) == (
        "SELECT b, c FROM t WHERE (b IS NOT NULL) AND (a > 1) GROUP BY b, c"
    )
    distinct = _case("SELECT DISTINCT c FROM t", "a > 1")
    assert full_query(distinct) == "SELECT DISTINCT c FROM t WHERE (a > 1)"

    injected = _case("SELECT a, b FROM t", "a > 1")
    assert full_query(injected) == "SELECT a, b FROM t WHERE (a > 1)"
    already = _case("SELECT a FROM t WHERE a > 0", "b > 1")
    assert full_query(already) == "SELECT a FROM t WHERE (a > 0) AND (b > 1)"
    illegal = _case("SELECT b, COUNT(*) FROM t GROUP BY b", "a > 1")
    assert full_query(illegal) == "SELECT b, COUNT(*) FROM t GROUP BY b WHERE (a > 1)"


# ---- shared screening -------------------------------------------------------


def test_screening_order_and_runner_lifetime() -> None:
    broken = _case("SELECT random()", "a > 0", setup=("INSERT INTO no_such_table VALUES (1)",))
    label = judge(broken, "plan_variant")
    assert (label.y, label.invalid_reason) == ("invalid", "setup_error")
    assert label.detail["error"]
    assert label.detail["full_query"] == full_query(broken)

    limited = _case("SELECT a FROM t LIMIT 2", None)
    for oracle in IMPLEMENTED:
        limited_label = judge(limited, oracle)
        assert (limited_label.y, limited_label.invalid_reason) == ("invalid", "nondeterministic"), oracle
        assert "form" not in limited_label.detail

    random_group = _case("SELECT b FROM t GROUP BY b", "random() < 0.5")
    random_label = judge(random_group, "norec")
    assert random_label.invalid_reason == "nondeterministic"

    created: list[_Injecting] = []
    factory = _factory(lambda _runner, _sql: False, QueryResult(), created)
    judge(_case("SELECT a, b FROM t"), "tlp", runner_factory=factory)
    assert len(created) == 2 and all(runner.closed == 1 for runner in created)

    created.clear()
    judge(_case("SELECT a, b FROM t", None), "tlp", runner_factory=factory)
    assert len(created) == 1 and created[0].closed == 1

    def explode() -> None:
        raise RuntimeError("runner exploded")

    with pytest.raises(RuntimeError, match="runner exploded"):
        judge(_case("SELECT a, b FROM t"), "tlp", runner_factory=explode)


def test_judge_rejects_unknown_oracle_and_engine_and_is_stable() -> None:
    plain = _case("SELECT a, b FROM t")
    with pytest.raises(ValueError):
        judge(plain, "TLP")
    with pytest.raises(ValueError):
        judge(plain, "no_such_oracle")
    alien = SqlCase(engine="sqlite", setup=plain.setup, query=plain.query, predicate=plain.predicate)
    with pytest.raises(ValueError):
        judge(alien, "tlp")

    first = judge(plain, "tlp")
    second = judge(plain, "tlp")
    assert first.to_dict() == second.to_dict()
    assert first.cve == {}
    assert "elapsed" not in json.dumps(first.to_dict())
    bug = judge(_named("metrics_small"), "tlp")
    assert bug.to_dict() == judge(_named("metrics_small"), "tlp").to_dict()

    df = _case("SELECT a, b FROM t", engine="datafusion")
    df_first = judge(df, "tlp")
    assert (df_first.y, df_first.fail_kind, df_first.invalid_reason) == ("pass", None, None)
    assert df_first.to_dict() == judge(df, "tlp").to_dict()
    assert df_first.cve == {}
    assert "elapsed" not in json.dumps(df_first.to_dict())

    df_setup = judge(
        _case("SELECT a, b FROM t", engine="datafusion",
              setup=("INSERT INTO no_such_table VALUES (1)",)),
        "plan_variant",
    )
    assert (df_setup.y, df_setup.invalid_reason) == ("invalid", "setup_error")
    assert df_setup.detail["error"]

    df_skipped = judge(_case("SELECT a, b FROM t", None, engine="datafusion"), "tlp")
    assert (df_skipped.y, df_skipped.invalid_reason) == ("invalid", "not_applicable")

    def explode() -> None:
        raise RuntimeError("runner exploded")

    with pytest.raises(RuntimeError, match="runner exploded"):
        judge(df, "tlp", runner_factory=explode)


# ---- tlp --------------------------------------------------------------------


def test_tlp_where_pass_fail_and_invalid_reasons() -> None:
    plain = _case("SELECT a, b FROM t")
    passed = judge(plain, "tlp")
    assert (passed.y, passed.fail_kind, passed.invalid_reason) == ("pass", None, None)
    assert passed.detail["form"] == "where"
    assert passed.detail["full_query"] == full_query(plain)
    assert passed.identity.switches == () and passed.identity.behavior == {}

    assert judge(_case("SELECT a, b FROM t", None), "tlp").invalid_reason == "not_applicable"
    assert judge(_case("SELECT COUNT(*) FROM t"), "tlp").invalid_reason == "not_applicable"
    assert judge(_case("SELECT b, COUNT(*) FROM t GROUP BY b"), "tlp").invalid_reason == "not_applicable"
    assert judge(_named("bad_column"), "tlp").invalid_reason == "query_error"
    assert judge(_named("broken_setup"), "tlp").invalid_reason == "setup_error"

    value_dependent = judge(_named("vd_partial"), "tlp")
    assert value_dependent.invalid_reason == "value_dependent_error"
    assert value_dependent.detail["form"] == "where"
    assert value_dependent.detail["error"]

    bug = judge(_named("metrics_small"), "tlp")
    assert (bug.y, bug.fail_kind) == ("fail", "wrong_result")
    assert bug.detail["form"] == "where"
    assert bug.identity.behavior == {"missing": 1, "extra": 0}
    assert bug.identity.error_class is None and bug.identity.switches == ()
    assert bug.detail["candidate_kind"] and bug.detail["q1"]

    full = full_query(plain)

    def null_partition(_runner, sql: str) -> bool:
        return "IS NULL" in sql.upper()

    crash = judge(plain, "tlp", runner_factory=_factory(null_partition, _internal()))
    assert (crash.y, crash.fail_kind) == ("fail", "crash")
    assert crash.identity.error_class == "InternalException"
    assert crash.identity.behavior == {} and crash.detail["form"] == "where"

    stalled = judge(plain, "tlp", runner_factory=_factory(null_partition, _timeout()))
    assert (stalled.y, stalled.invalid_reason) == ("invalid", "timeout")
    assert "error" not in stalled.detail

    def not_partition(_runner, sql: str) -> bool:
        upper = sql.upper()
        return "NOT (" in upper and "IS NULL" not in upper

    mismatch = judge(plain, "tlp", runner_factory=_factory(not_partition, _binder()))
    assert (mismatch.y, mismatch.fail_kind) == ("fail", "error_mismatch")
    assert mismatch.identity.error_class == "BinderException"

    empty = QueryResult(rows=[], columns=["a", "b"])
    shortened = judge(plain, "tlp", runner_factory=_factory(null_partition, empty))
    assert shortened.fail_kind == "wrong_result"
    assert shortened.identity.behavior == {"missing": 1, "extra": 0}


def test_tlp_groupby_and_distinct() -> None:
    grouped = judge(_case("SELECT b FROM t GROUP BY b"), "tlp")
    assert grouped.y == "pass" and grouped.detail["form"] == "groupby"
    filtered = judge(_case("SELECT b, c FROM t WHERE b IS NOT NULL GROUP BY b, c"), "tlp")
    assert filtered.y == "pass" and filtered.detail["form"] == "groupby"
    distinct = judge(_case("SELECT DISTINCT c FROM t"), "tlp")
    assert distinct.y == "pass" and distinct.detail["form"] == "distinct"

    value_dependent = judge(_named("vd_grouped"), "tlp")
    assert value_dependent.invalid_reason == "value_dependent_error"
    assert value_dependent.detail["form"] == "groupby"

    def null_partition(_runner, sql: str) -> bool:
        return "IS NULL" in sql.upper()

    grouped_case = _case("SELECT b FROM t GROUP BY b")
    hit = judge(grouped_case, "tlp", runner_factory=_factory(null_partition, QueryResult(rows=[])))
    assert (hit.y, hit.fail_kind) == ("fail", "wrong_result")
    assert hit.detail["form"] == "groupby"
    assert hit.identity.behavior == {"missing": 1, "extra": 0}

    crash = judge(grouped_case, "tlp", runner_factory=_factory(null_partition, _internal()))
    assert crash.fail_kind == "crash" and crash.identity.error_class == "InternalException"


# ---- norec ------------------------------------------------------------------


def test_norec_pass_fail_and_invalid_reasons() -> None:
    plain = _case("SELECT a, b FROM t")
    passed = judge(plain, "norec")
    assert passed.y == "pass"
    assert passed.detail["full_query"] == full_query(plain)
    assert "form" not in passed.detail
    assert judge(_case("SELECT COUNT(*) FROM t"), "norec").y == "pass"
    assert judge(_case("SELECT DISTINCT c FROM t"), "norec").y == "pass"
    assert judge(_case("SELECT b FROM t GROUP BY b"), "norec").invalid_reason == "not_applicable"
    assert judge(_case("SELECT a, b FROM t", None), "norec").invalid_reason == "not_applicable"
    assert judge(_named("bad_column"), "norec").invalid_reason == "query_error"
    assert judge(_named("vd_partial"), "norec").y == "pass"

    bug = judge(_named("metrics_small"), "norec")
    assert (bug.y, bug.fail_kind) == ("fail", "wrong_result")
    assert bug.identity.behavior == {"missing": 1, "extra": 0}
    assert bug.identity.switches == ()

    def reference(_runner, sql: str) -> bool:
        return sql.upper().startswith("SELECT SUM(CASE")

    shifted = judge(plain, "norec", runner_factory=_factory(reference, QueryResult(rows=[[99]])))
    assert shifted.fail_kind == "wrong_result"
    assert shifted.identity.behavior == {"missing": 96, "extra": 0}

    def probe(_runner, sql: str) -> bool:
        compact = " ".join(sql.split()).upper()
        return compact.startswith("SELECT COUNT(*)") and "WHERE" not in compact

    crash = judge(plain, "norec", runner_factory=_factory(probe, _internal()))
    assert crash.fail_kind == "crash" and crash.identity.error_class == "InternalException"

    stalled = judge(plain, "norec", runner_factory=_factory(reference, _timeout()))
    assert stalled.invalid_reason == "timeout"


# ---- plan variant -----------------------------------------------------------


def test_plan_variant_pass_fail_skip_and_baseline_errors() -> None:
    plain = _case("SELECT a, b FROM t")
    full = full_query(plain)
    passed = judge(plain, "plan_variant")
    assert passed.y == "pass"
    assert passed.detail["variants_compared"] >= 1
    assert isinstance(passed.detail["variants_skipped"], list)
    assert passed.identity.switches == ()

    no_predicate = _case("SELECT a, b FROM t", None)

    def baseline_only(_runner, sql: str) -> bool:
        return sql == no_predicate.query

    forced = judge(no_predicate, "plan_variant", runner_factory=_factory(baseline_only, _internal()))
    assert (forced.y, forced.fail_kind) == ("fail", "crash")
    assert forced.identity.switches == ()
    assert forced.invalid_reason is None

    illegal = judge(_case("SELECT b, COUNT(*) FROM t GROUP BY b"), "plan_variant")
    assert illegal.invalid_reason == "query_error"
    assert "error" in illegal.detail
    assert illegal.detail["variants_compared"] == 0

    def under_no_optimizer(runner, sql: str) -> bool:
        return runner.no_optimizer and sql == full

    mismatch = judge(plain, "plan_variant", runner_factory=_factory(under_no_optimizer, _binder()))
    assert (mismatch.y, mismatch.fail_kind) == ("fail", "error_mismatch")
    assert mismatch.identity.switches == ("no_optimizer",)
    assert mismatch.identity.error_class == "BinderException"

    crash = judge(plain, "plan_variant", runner_factory=_factory(under_no_optimizer, _internal()))
    assert crash.fail_kind == "crash"
    assert crash.identity.switches == ("no_optimizer",)
    assert crash.identity.error_class == "InternalException"

    skipped = judge(plain, "plan_variant", runner_factory=_factory(under_no_optimizer, _timeout()))
    assert skipped.y == "pass"
    assert "no_optimizer" in skipped.detail["variants_skipped"]
    assert skipped.detail["variants_compared"] >= 1

    bug = judge(_named("inv_delim"), "plan_variant")
    assert (bug.y, bug.fail_kind) == ("fail", "wrong_result")
    assert bug.identity.switches == ("no_optimizer",)
    assert bug.identity.behavior == {"missing": 0, "extra": 2}
    assert bug.to_dict() == judge(_named("inv_delim"), "plan_variant").to_dict()


def test_plan_variant_invalid_when_nothing_was_compared() -> None:
    plain = _case("SELECT a FROM t", "a > 1")
    full = full_query(plain)
    seen = {"n": 0}

    def after_baseline(_runner, sql: str) -> bool:
        if sql != full:
            return False
        seen["n"] += 1
        return seen["n"] > 1

    value_error = QueryResult(error="ConversionException: Conversion Error: could not convert")
    invalid = judge(plain, "plan_variant", runner_factory=_factory(after_baseline, value_error))
    assert invalid.invalid_reason == "value_dependent_error"
    assert invalid.detail["variants_compared"] == 0
    assert len(invalid.detail["variants_skipped"]) == len(PlanVariantOracle(engine="duckdb").variants)
    assert invalid.detail["error"]

    seen["n"] = 0
    stalled = judge(plain, "plan_variant", runner_factory=_factory(after_baseline, _timeout()))
    assert stalled.invalid_reason == "timeout"
    assert stalled.detail["variants_compared"] == 0
    assert "error" not in stalled.detail


def test_plan_variant_skips_a_guard_rail_refusal() -> None:
    plain = _case("SELECT a, b FROM t")
    full = full_query(plain)

    class _Asof(_Injecting):
        def __init__(self) -> None:
            super().__init__(lambda _runner, _sql: False, QueryResult())
            self.asof = False

        def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
            upper = sql.strip().upper()
            if upper.startswith("SET DEBUG_ASOF_IEJOIN=TRUE"):
                self.asof = True
            elif upper.startswith("RESET DEBUG_ASOF_IEJOIN"):
                self.asof = False
            if self.asof and sql == full:
                return QueryResult(error="NotImplementedException: IEJoin requires numeric keys")
            return self._inner.run(sql, timeout_s=timeout_s)

    label = judge(plain, "plan_variant", runner_factory=_Asof)
    assert label.y == "pass"
    assert "asof_iejoin" in label.detail["variants_skipped"]
    assert label.detail["variants_compared"] >= 1
