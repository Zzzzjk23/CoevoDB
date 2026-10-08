"""Index-presence oracle for DuckDB ART indexes.

The same statement is run on the same rows with no secondary index and again
after each ART index is created. Multiset equality is the contract. DataFusion
has no secondary indexes, so it is not applicable. PostgreSQL index SQL from
the old oracle is not reused: DuckDB ART indexes are plain ``CREATE INDEX``
statements, and this module does not change session or server settings.

``DuckDBRunner.setup`` opens a fresh connection, so schema setup runs once and
every later statement, including ``CREATE INDEX``, goes through ``run``. The
acceptance gate injects a wrong bag on ``run`` after a successful create.
"""

from __future__ import annotations

from dataclasses import dataclass

from oracles.db_runner import QueryResult, bags_equal
from oracles.errors import is_value_dependent_error
from oracles.index_variant import parse_tables
from oracles.models import (
    KIND_CRASH,
    KIND_ERROR_MISMATCH,
    Candidate,
    new_candidate_id,
)
from oracles.normalize import is_internal_error

from surprise.harness.contracts import Label, SqlCase

from .common import fail_label, invalid_label, multiset_difference, pass_label
from .forms import full_query
from .registry import OracleOptions, register
from .rewrites import is_read_only_query

ORACLE = "index_presence"


@dataclass(frozen=True)
class _Plan:
    name: str
    statement: str
    drop: str

    def public(self) -> dict[str, str]:
        return {"name": self.name, "statement": self.statement}


def judge_case(
    case: SqlCase, *, factory, timeout_s: float, options: OracleOptions
) -> Label:
    """Compare one read-only statement with and without DuckDB ART indexes."""
    del options  # shared signature; index presence has no rewrite options
    full = full_query(case)
    if case.engine != "duckdb":
        return invalid_label(ORACLE, "not_applicable", full, extra={"applicability": "no_secondary_index"})
    if not is_read_only_query(full):
        return invalid_label(ORACLE, "not_applicable", full, extra={"applicability": "not_select"})
    plans = _art_plans(case.setup)
    if not plans:
        return invalid_label(ORACLE, "not_applicable", full, extra={"applicability": "no_base_table"})

    runner = factory()
    try:
        return _judge_indexed(case, runner, timeout_s, full, plans)
    finally:
        runner.close()


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _art_plans(setup: tuple[str, ...]) -> list[_Plan]:
    """Deterministic ART plans, one per parsed base-table column."""
    plans: list[_Plan] = []
    for table in parse_tables(list(setup)):
        for column, _type_name in table.cols:
            name = f"art{len(plans)}_{table.name}_{column}"
            statement = (
                f"CREATE INDEX {_quote(name)} ON {_quote(table.name)}({_quote(column)})"
            )
            drop = f"DROP INDEX IF EXISTS {_quote(name)}"
            plans.append(_Plan(name, statement, drop))
    return plans


def _is_internal(result: QueryResult) -> bool:
    return bool(result.is_internal_error) or is_internal_error(result.error)


def _judge_indexed(case: SqlCase, runner, timeout_s: float, full: str, plans: list[_Plan]) -> Label:
    outcomes = runner.setup(list(case.setup))
    for _statement, error in outcomes:
        if error is not None:
            return invalid_label(ORACLE, "setup_error", full, error=error)

    baseline = runner.run(full, timeout_s=timeout_s)
    baseline_label = _baseline_label(case, full, baseline)
    if baseline_label is not None:
        return baseline_label

    created: list[dict[str, str]] = []
    value_error: str | None = None
    for plan in plans:
        create = runner.run(plan.statement, timeout_s=timeout_s)
        if create.timed_out:
            return invalid_label(ORACLE, "timeout", full)
        if _is_internal(create):
            return _crash(case, full, baseline, create, f"internal error creating {plan.name}", ())
        if not create.ok:
            # A failed create is not an indexed execution.
            continue
        try:
            variant = runner.run(full, timeout_s=timeout_s)
        finally:
            drop = runner.run(plan.drop, timeout_s=timeout_s)
        if _is_internal(drop):
            return _crash(case, full, baseline, drop, f"internal error dropping {plan.name}", (plan.name,))
        if drop.timed_out or variant.timed_out:
            return invalid_label(ORACLE, "timeout", full)
        verdict = _variant_label(case, full, baseline, variant, plan, created)
        if verdict is not None:
            return verdict
        if not variant.ok and is_value_dependent_error(variant.error):
            value_error = variant.error
        elif variant.ok and bags_equal(baseline, variant):
            created.append(plan.public())
        if not drop.ok:
            break

    if created:
        return pass_label(ORACLE, full, extra={"indexes_created": created})
    if value_error is not None:
        return invalid_label(ORACLE, "value_dependent_error", full, error=value_error)
    return invalid_label(ORACLE, "not_applicable", full, extra={"applicability": "no_art_index"})


def _baseline_label(case: SqlCase, full: str, baseline: QueryResult) -> Label | None:
    """Invalid or crash for the original statement. None means it returned rows."""
    if baseline.timed_out:
        return invalid_label(ORACLE, "timeout", full)
    if _is_internal(baseline):
        return _crash(case, full, baseline, None, "internal error on index-presence baseline", ())
    if baseline.ok:
        return None
    if is_value_dependent_error(baseline.error):
        return invalid_label(ORACLE, "value_dependent_error", full, error=baseline.error)
    return invalid_label(ORACLE, "query_error", full, error=baseline.error)


def _variant_label(
    case: SqlCase,
    full: str,
    baseline: QueryResult,
    variant: QueryResult,
    plan: _Plan,
    created: list[dict[str, str]],
) -> Label | None:
    """Fail label for a real indexed divergence. None means 'keep going'."""
    switches = (plan.name,)
    extra = {"indexes_created": created + [plan.public()]}
    if _is_internal(variant):
        return _crash(
            case, full, baseline, variant,
            f"internal error under index {plan.name}", switches, extra,
        )
    if variant.ok:
        if bags_equal(baseline, variant):
            return None
        behavior = multiset_difference(baseline, variant)
        behavior["index"] = plan.name
        behavior["statement"] = plan.statement
        candidate = _candidate(
            case, full, "index_presence", baseline, variant,
            f"result differs under ART index {plan.name}", plan.statement,
        )
        return fail_label(
            ORACLE, candidate, full, behavior=behavior, switches=switches, extra=extra,
        )
    if is_value_dependent_error(variant.error):
        return None
    candidate = _candidate(
        case, full, KIND_ERROR_MISMATCH, baseline, variant,
        f"index {plan.name} errors while the unindexed query succeeds", plan.statement,
    )
    return fail_label(ORACLE, candidate, full, switches=switches, extra=extra)


def _crash(
    case: SqlCase,
    full: str,
    baseline: QueryResult | None,
    failed: QueryResult | None,
    note: str,
    switches: tuple[str, ...],
    extra: dict | None = None,
) -> Label:
    candidate = _candidate(case, full, KIND_CRASH, baseline, failed, note, None)
    return fail_label(ORACLE, candidate, full, switches=switches, extra=extra)


def _candidate(
    case: SqlCase,
    full: str,
    kind: str,
    baseline: QueryResult | None,
    other: QueryResult | None,
    note: str,
    q2: str | None,
) -> Candidate:
    return Candidate(
        id=new_candidate_id("index", kind, full, note),
        kind=kind,
        schema_sqls=list(case.setup),
        inserts=[],
        q1=full,
        q2=q2,
        r1_summary=baseline.summary() if baseline is not None else {},
        r2_summary=other.summary() if other is not None else {},
        category=ORACLE,
        notes=note,
    )


register(ORACLE, judge_case)
