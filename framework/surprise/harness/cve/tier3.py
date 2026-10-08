"""Tier 3: minimise a confirmed candidate, then build its profile.

The old minimiser is called as a plain function. Nothing here constructs an
agent or an LLM client. ``agents.bug_fixer`` is imported only when this tier
runs, so a tier-1 judgement does not load it.
"""

from __future__ import annotations

from typing import Any

from diagnosis.bisect import all_off_prelude, compute_fix_set, interventions_for, plan_diff_ops

from surprise.harness.constants import CVE_BISECT_MAX_EXECUTIONS, CVE_MINIMIZE_MAX_EXECUTIONS
from surprise.harness.contracts import Label, SqlCase

from .criterion import (
    RunContext,
    executed_predicate,
    executed_query,
    is_insert,
    load_factory,
    load_references,
    order_like,
    reproduces,
)
from .premise import check_premises

_PARSER_MARKERS = ("Parser Error", "Binder Error", "Catalog Error", "syntax error")


class _Checker:
    """The ``reproduces`` shape ``BugFixer._minimize`` and the fix-set search call."""

    def __init__(self, context: RunContext, engine: str, original: tuple[str, ...]) -> None:
        self.executions = 0
        self.context = context
        self.engine = engine
        self.original = original

    def reproduces(
        self,
        candidate: Any,
        schema_sqls: list[str],
        inserts: list[str],
        q1: str | None = None,
        q2: str | None = None,
        timeout_s: float = 10.0,
        prelude_sqls: list[str] | None = None,
    ) -> bool:
        del candidate, timeout_s
        self.executions += 1
        query = q1 if q1 is not None else ""
        setup = order_like(self.original, list(schema_sqls), list(inserts))
        return reproduces(self.context, self.engine, setup, query, q2, list(prelude_sqls or []))


def diagnose_case(
    case: SqlCase,
    oracle: str,
    label: Label,
    *,
    factory: Any,
    timeout_s: float,
    rewrite_rule: str | None = None,
    paired_query: str | None = None,
    old_python: str | None = None,
    reference_factories: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Minimise ``case`` and, when it still reproduces and meets the premises, profile it.

    The returned dict is JSON-safe. ``kind`` is ``profiled``, ``not_reproduced``,
    or ``premise``.
    """
    context = RunContext(
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
    checker = _Checker(context, case.engine, case.setup)
    query = executed_query(case, oracle)
    q2 = paired_query
    schema = [statement for statement in case.setup if not is_insert(statement)]
    inserts = [statement for statement in case.setup if is_insert(statement)]
    setup, query, q2 = _minimize(checker, case, oracle, schema, inserts, query, q2)
    minimized = SqlCase(
        engine=case.engine,
        setup=tuple(setup),
        query=query,
        predicate=context.predicate,
    )
    still = checker.reproduces(None, _schema_of(setup), _inserts_of(setup), query, q2)
    minimize = {
        "reproduced": still,
        "setup_before": len(case.setup),
        "setup_after": len(setup),
        "case": minimized.to_dict(),
        "executions": checker.executions,
    }
    if not still:
        return {"kind": "not_reproduced", "minimize": minimize, "invalid_reason": "not_reproduced_minimized"}

    premise = check_premises(minimized, oracle, label, _probe(factory, setup, timeout_s))
    if premise["violations"]:
        return {
            "kind": "premise",
            "minimize": minimize,
            "premise": premise,
            "invalid_reason": premise["violations"][0],
        }
    profile = _profile(context, minimized, label, query, q2)
    return {"kind": "profiled", "minimize": minimize, "profile": profile}


def _minimize(
    checker: _Checker,
    case: SqlCase,
    oracle: str,
    schema: list[str],
    inserts: list[str],
    query: str,
    q2: str | None,
) -> tuple[list[str], str, str | None]:
    # Imported here so tier-1 children never load the agent module.
    import agents.bug_fixer as bug_fixer
    from oracles.models import KIND_EQUIV, KIND_PLAN_VARIANT, Candidate

    kind = KIND_EQUIV if oracle == "equivalent_query" and q2 else KIND_PLAN_VARIANT
    candidate = Candidate(
        id="cve",
        kind=kind,
        schema_sqls=list(schema),
        inserts=list(inserts),
        q1=query,
        q2=q2,
    )
    holder = _Holder(checker)
    reduced = bug_fixer.BugFixer._minimize(holder, candidate)
    schema = list(reduced["schema_sqls"])
    inserts = list(reduced["inserts"])
    query = str(reduced["q1"])
    q2 = reduced.get("q2")
    setup = order_like(case.setup, schema, inserts)
    setup = _drop_setup(checker, setup, query, q2 if isinstance(q2, str) else None)
    return setup, query, q2 if isinstance(q2, str) else None


def _drop_setup(checker: _Checker, setup: list[str], query: str, q2: str | None) -> list[str]:
    """Drop setup statements that are not needed for the discrepancy. Bounded by a constant."""
    kept = list(setup)
    used = 0
    while True:
        removed = False
        index = 0
        while index < len(kept):
            if used >= CVE_MINIMIZE_MAX_EXECUTIONS:
                return kept
            reduced = kept[:index] + kept[index + 1 :]
            used += 1
            schema = _schema_of(reduced)
            inserts = _inserts_of(reduced)
            if checker.reproduces(None, schema, inserts, query, q2):
                kept = reduced
                removed = True
            else:
                index += 1
        if not removed:
            return kept


def _profile(
    context: RunContext,
    case: SqlCase,
    label: Label,
    query: str,
    q2: str | None,
) -> dict[str, Any]:
    setup = list(case.setup)

    def fails(prelude: list[str]) -> bool:
        return reproduces(context, case.engine, setup, query, q2, prelude)

    local = None
    runner = context.factory()
    try:
        runner.setup(list(setup))
        local = runner.run(query, timeout_s=context.timeout_s)
        names = [name for name, _prelude in interventions_for(case.engine, runner)]
        fix = compute_fix_set(fails, case.engine, runner, max_executions=CVE_BISECT_MAX_EXECUTIONS)
        fix_kind, fix_set = _apply_pervasive(str(fix["fix_kind"]), list(fix["fix_set"]), len(names))
        plan_diff = plan_diff_ops(runner, query, case.engine, all_off_prelude(case.engine, names))
    finally:
        close = getattr(runner, "close", None)
        if close is not None:
            try:
                close()
            except Exception:
                pass
    local_rows = None
    if local is not None and getattr(local, "error", None) is None and not bool(getattr(local, "timed_out", False)):
        local_rows = list(getattr(local, "rows", []) or [])
    ladder = _version_ladder(case.engine, setup, query, local_rows, context.timeout_s)
    shape = behavior_shape_of(label)
    return {
        "fix_kind": fix_kind,
        "fix_set": fix_set,
        "plan_diff": list(plan_diff),
        "version_ladder": ladder,
        "error_class": label.identity.error_class,
        "behavior_shape": shape,
        "witness_switches": list(label.identity.switches),
        "executions": int(fix["executions"]),
    }


def behavior_shape_of(label: Label) -> str | None:
    from .shape import behavior_shape

    if label.fail_kind != "wrong_result":
        return None
    return behavior_shape(label.identity.behavior)


def _apply_pervasive(fix_kind: str, fix_set: list[str], basis_size: int) -> tuple[str, list[str]]:
    """Match ``SignatureEngine.compute``: a wide fix set is ``pervasive`` and cleared."""
    if fix_kind in ("single", "minimal_set") and len(fix_set) > max(6, basis_size // 4):
        return "pervasive", []
    return fix_kind, sorted(fix_set)


def _version_ladder(
    engine: str,
    setup: list[str],
    query: str,
    local_rows: list[Any] | None,
    timeout_s: float,
) -> str:
    """Old-engine marker, using the S3 version worker instead of ``bin/python``."""
    from oracles.normalize import loose_bag

    from surprise.harness.oracles.version_differential import _query_old, _resolve_old_python

    if engine not in ("duckdb", "datafusion"):
        return "unavailable"
    try:
        python = _resolve_old_python(engine, None)
    except (KeyError, OSError):
        return "unavailable"
    if python is None:
        return "unavailable"
    try:
        remote = _query_old(python, engine, list(setup), query, timeout_s)
    except Exception:
        return "unknown"
    if remote.protocol_error or remote.setup_error:
        return "unknown"
    if remote.error:
        err = str(remote.error)
        for marker in _PARSER_MARKERS:
            if marker in err:
                return "unknown"
        return "recent"
    if local_rows is None:
        return "unknown"
    if loose_bag(remote.rows) == loose_bag(local_rows):
        return "longstanding"
    return "recent"


def diagnose_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Run tier 3 for one worker payload. The child executes the target SQL."""
    case = SqlCase.from_dict(payload.get("case"))
    label = Label.from_dict(payload.get("label"))
    oracle = payload.get("oracle")
    timeout_s = payload.get("timeout_s")
    if not isinstance(oracle, str) or isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)):
        raise ValueError("malformed diagnose payload")

    def _text(name: str) -> str | None:
        value = payload.get(name)
        return value if isinstance(value, str) else None

    outcome = diagnose_case(
        case,
        oracle,
        label,
        factory=load_factory(payload),
        timeout_s=float(timeout_s),
        rewrite_rule=_text("rewrite_rule"),
        paired_query=_text("paired_query"),
        old_python=_text("old_python"),
        reference_factories=load_references(payload),
    )
    return {"op": "diagnose", **outcome}


def _schema_of(setup: list[str]) -> list[str]:
    return [statement for statement in setup if not is_insert(statement)]


def _inserts_of(setup: list[str]) -> list[str]:
    return [statement for statement in setup if is_insert(statement)]


def _probe(factory: Any, setup: list[str], timeout_s: float):
    def probe(sql: str) -> tuple[str, Any]:
        runner = factory()
        try:
            try:
                outcomes = runner.setup(list(setup))
            except Exception as exc:
                return "error", f"{type(exc).__name__}: {exc}"
            for item in outcomes or []:
                error = item[1] if isinstance(item, (list, tuple)) and len(item) >= 2 else None
                if error is not None:
                    return "error", str(error)
            try:
                result = runner.run(sql, timeout_s=timeout_s)
            except Exception as exc:
                return "error", f"{type(exc).__name__}: {exc}"
        finally:
            close = getattr(runner, "close", None)
            if close is not None:
                try:
                    close()
                except Exception:
                    pass
        if bool(getattr(result, "timed_out", False)):
            return "timeout", None
        if getattr(result, "error", None) is not None:
            return "error", result.error
        rows = getattr(result, "rows", []) or []
        value = rows[0][0] if rows and rows[0] else None
        return "ok", value

    return probe


class _Holder:
    """The only object ``BugFixer._minimize`` reads is ``checker``."""

    def __init__(self, checker: _Checker) -> None:
        self.checker = checker
