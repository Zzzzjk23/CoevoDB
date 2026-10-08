"""Whether a candidate still reproduces under a prelude.

Plan variant compares the two witnessed forms on one fresh runner: the query
after the prelude, then the same query with the witnessing switch turned on.
Both succeeding with the same bag, or both failing with the same error class,
is agreement, so the candidate does not reproduce. The other six oracles
re-judge the reduced case; a ``fail`` label reproduces.

Every call opens its own runner and runs setup again. A writing statement such
as MERGE must not leak into the next trial.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from diagnosis.bisect import interventions_for, prelude_for_names

from surprise.harness.contracts import Label, SqlCase
from surprise.harness.oracles.forms import full_query
from surprise.harness.oracles.registry import runner_factory_for

from .hypothesis import ParsedHypothesis
from .session import run_judge
from .shape import behavior_shape

_INSERT = re.compile(r"^\s*insert\b", re.IGNORECASE)


@dataclass
class RunContext:
    """Everything one reproduction check needs besides the reduced SQL."""

    oracle: str
    factory: Any
    timeout_s: float
    switches: tuple[str, ...]
    predicate: str | None
    rewrite_rule: str | None = None
    paired_query: str | None = None
    old_python: str | None = None
    reference_factories: dict[str, Any] | None = None


def is_insert(sql: str) -> bool:
    """True when ``sql`` is an INSERT statement."""
    return _INSERT.match(sql) is not None


def order_like(original: tuple[str, ...] | list[str], schema: list[str], inserts: list[str]) -> list[str]:
    """Statements of ``original`` that are still in ``schema`` or ``inserts``, in that order."""
    schema_left = list(schema)
    insert_left = list(inserts)
    kept: list[str] = []
    for statement in original:
        pool = insert_left if is_insert(statement) else schema_left
        if statement in pool:
            pool.remove(statement)
            kept.append(statement)
    return kept


def executed_query(case: SqlCase, oracle: str) -> str:
    """The statement the reproduction check runs.

    Plan variant executes the folded query. The other oracles keep ``query``
    and ``predicate`` apart, because TLP and NoREC read them separately.
    """
    if oracle == "plan_variant":
        return full_query(case)
    return case.query


def executed_predicate(case: SqlCase, oracle: str) -> str | None:
    if oracle == "plan_variant":
        return None
    return case.predicate


def list_interventions(engine: str, factory: Any) -> list[str]:
    """Intervention names for ``engine``. DuckDB learns them by running one statement."""
    runner = factory()
    try:
        pairs = interventions_for(engine, runner)
    finally:
        close = getattr(runner, "close", None)
        if close is not None:
            try:
                close()
            except Exception:
                pass
    return [name for name, _prelude in pairs]


def reproduces(
    context: RunContext,
    engine: str,
    setup: list[str],
    query: str,
    q2: str | None,
    prelude: list[str],
) -> bool:
    """True when the witnessed forms still disagree under ``prelude``."""
    if context.oracle == "plan_variant" and context.switches:
        return _plan_variant_reproduces(context, engine, setup, query, prelude)
    return _rejudge_reproduces(context, engine, setup, query, q2, prelude)


def attribute(
    parsed: ParsedHypothesis,
    context: RunContext,
    engine: str,
    setup: list[str],
    query: str,
    q2: str | None,
    label: Label,
) -> dict[str, Any]:
    """One membership test. Profile comparisons execute nothing."""
    if parsed.interventions:
        prelude = prelude_for_names(engine, list(parsed.interventions))
        still = reproduces(context, engine, setup, query, q2, list(prelude))
        return {
            "hypothesis_id": parsed.hypothesis_id,
            "method": "fix_set",
            "consistent": not still,
            "executions": 1,
        }
    checks: list[bool] = []
    if parsed.has_fail_kind:
        checks.append(parsed.fail_kind == label.fail_kind)
    if parsed.has_error_class:
        checks.append(parsed.error_class == label.identity.error_class)
    if parsed.has_behavior_shape:
        checks.append(parsed.behavior_shape == behavior_shape(label.identity.behavior))
    if not checks:
        raise ValueError("hypothesis: an empty intervention list needs fail_kind, error_class, or behavior_shape")
    return {
        "hypothesis_id": parsed.hypothesis_id,
        "method": "profile",
        "consistent": all(checks),
        "executions": 0,
    }


def _plan_variant_reproduces(
    context: RunContext,
    engine: str,
    setup: list[str],
    query: str,
    prelude: list[str],
) -> bool:
    witness = _witness_statements(engine, context.switches)
    if not witness:
        return _rejudge_reproduces(context, engine, setup, query, None, prelude)
    runner = context.factory()
    try:
        if not _setup(runner, setup):
            return False
        for statement in prelude:
            _run(runner, statement, context.timeout_s)
        first = _run(runner, query, context.timeout_s)
        for statement in witness:
            _run(runner, statement, context.timeout_s)
        second = _run(runner, query, context.timeout_s)
    finally:
        _close(runner)
    return not _same_outcome(first, second)


def _rejudge_reproduces(
    context: RunContext,
    engine: str,
    setup: list[str],
    query: str,
    q2: str | None,
    prelude: list[str],
) -> bool:
    reduced = SqlCase(engine=engine, setup=tuple(setup), query=query, predicate=context.predicate)
    paired = q2 if q2 is not None else context.paired_query
    label, _transcript = run_judge(
        reduced,
        context.oracle,
        factory=context.factory,
        timeout_s=context.timeout_s,
        prelude=tuple(prelude),
        rewrite_rule=context.rewrite_rule,
        paired_query=paired,
        old_python=context.old_python,
        reference_factories=context.reference_factories,
    )
    return label.y == "fail"


def _witness_statements(engine: str, switches: tuple[str, ...]) -> list[str]:
    from oracles.plan_variant import PlanVariantOracle

    variants = {
        label: list(setup)
        for label, setup, _teardown in PlanVariantOracle(engine=engine).variants
    }
    statements: list[str] = []
    for name in switches:
        found = variants.get(name)
        if found:
            statements.extend(found)
    return statements


def _setup(runner: Any, statements: list[str]) -> bool:
    """False when a setup statement reports an error. A raised setup still propagates."""
    outcomes = runner.setup(list(statements))
    for item in outcomes or []:
        error = item[1] if isinstance(item, (list, tuple)) and len(item) >= 2 else None
        if error is not None:
            return False
    return True


def _run(runner: Any, sql: str, timeout_s: float) -> Any:
    return runner.run(sql, timeout_s=timeout_s)


def _same_outcome(first: Any, second: Any) -> bool:
    """True when both forms succeed with the same bag or fail with the same error class."""
    left = _classify(first)
    right = _classify(second)
    if left[0] == "ok" and right[0] == "ok":
        return left[1] == right[1]
    if left[0] == "error" and right[0] == "error":
        return left[1] == right[1]
    if left[0] == "timeout" and right[0] == "timeout":
        return True
    return False


def _classify(result: Any) -> tuple[str, Any]:
    if result is None:
        return ("error", "")
    if bool(getattr(result, "timed_out", False)):
        return ("timeout", None)
    error = getattr(result, "error", None)
    if error is not None:
        text = str(error)
        return ("error", text.split(":", 1)[0] if text else "")
    bag = result.bag() if hasattr(result, "bag") and callable(result.bag) else None
    return ("ok", bag)


def _close(runner: Any) -> None:
    close = getattr(runner, "close", None)
    if close is None:
        return
    try:
        close()
    except Exception:
        pass


def default_factory(engine: str) -> Any:
    return runner_factory_for(engine)


def load_factory(payload: dict[str, Any]) -> Any:
    """The runner factory named by a worker payload, or the engine default."""
    from surprise.harness.cve.isolate import load_callable

    ref = payload.get("runner_factory")
    if ref is None:
        ref = payload.get("factory")
    if isinstance(ref, str) and ref:
        return load_callable(ref)
    engine = payload.get("engine")
    if not isinstance(engine, str):
        case = payload.get("case")
        if isinstance(case, dict) and isinstance(case.get("engine"), str):
            engine = case["engine"]
    if not isinstance(engine, str):
        raise ValueError("engine missing")
    return runner_factory_for(engine)


def load_references(payload: dict[str, Any]) -> dict[str, Any] | None:
    refs = payload.get("reference_factories")
    if refs is None:
        return None
    if not isinstance(refs, dict):
        raise ValueError("reference_factories must be an object")
    from surprise.harness.cve.isolate import load_callable

    return {str(engine): load_callable(ref) for engine, ref in refs.items()}


def interventions_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    engine = payload.get("engine")
    if not isinstance(engine, str):
        raise ValueError("engine missing")
    return {"op": "interventions", "names": list_interventions(engine, load_factory(payload))}


def attribute_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    from .hypothesis import ParsedHypothesis

    case = SqlCase.from_dict(payload.get("case"))
    label = Label.from_dict(payload.get("label"))
    hypothesis = payload.get("hypothesis")
    if not isinstance(hypothesis, dict):
        raise ValueError("hypothesis payload must be an object")
    oracle = payload.get("oracle")
    timeout_s = payload.get("timeout_s")
    if not isinstance(oracle, str) or isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)):
        raise ValueError("malformed attribute payload")
    parsed = ParsedHypothesis.from_dict(hypothesis)
    context = _context_from_parts(
        oracle,
        load_factory(payload),
        float(timeout_s),
        label,
        case,
        rewrite_rule=payload.get("rewrite_rule") if isinstance(payload.get("rewrite_rule"), str) else None,
        paired_query=payload.get("paired_query") if isinstance(payload.get("paired_query"), str) else None,
        old_python=payload.get("old_python") if isinstance(payload.get("old_python"), str) else None,
        reference_factories=load_references(payload),
    )
    result = attribute(
        parsed,
        context,
        case.engine,
        list(case.setup),
        executed_query(case, oracle),
        context.paired_query,
        label,
    )
    return {"op": "attribute", **result}


def context_for(
    case: SqlCase,
    oracle: str,
    label: Label,
    *,
    factory: Any,
    timeout_s: float,
    rewrite_rule: str | None,
    paired_query: str | None,
    old_python: str | None,
    reference_factories: dict[str, Any] | None,
) -> RunContext:
    """A reproduction context for the original, not-yet-minimised case."""
    return _context_from_parts(
        oracle,
        factory,
        timeout_s,
        label,
        case,
        rewrite_rule=rewrite_rule,
        paired_query=paired_query,
        old_python=old_python,
        reference_factories=reference_factories,
    )


def _context_from_parts(
    oracle: str,
    factory: Any,
    timeout_s: float,
    label: Label,
    case: SqlCase,
    *,
    rewrite_rule: str | None,
    paired_query: str | None,
    old_python: str | None,
    reference_factories: dict[str, Any] | None,
) -> RunContext:
    return RunContext(
        oracle=oracle,
        factory=factory,
        timeout_s=timeout_s,
        switches=tuple(label.identity.switches),
        predicate=executed_predicate(case, oracle),
        rewrite_rule=rewrite_rule,
        paired_query=paired_query,
        old_python=old_python,
        reference_factories=reference_factories,
    )
