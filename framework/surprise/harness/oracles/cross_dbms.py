"""Cross-DBMS oracle: three independent engines, and the target must be the only outlier.

``scripts.cross_engine.classify_divergence`` still names the plurality. A fail
is recorded only when that plurality exists and the target is its unique
dissenter. Ties, several dissenters, and a dissenter that is not the target
are ``invalid / non_unique_outlier``. Version aliases are not engines.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable

from oracles.db_runner import QueryResult
from oracles.errors import is_value_dependent_error
from oracles.normalize import is_internal_error, loose_bag, normalize_rows
from scripts.cross_engine import classify_divergence

from surprise.harness.contracts import IdentityEvidence, Label, SqlCase

from .common import invalid_label, pass_label
from .forms import full_query
from .pg_reference import PostgresReferenceRunner, is_readonly_query
from .registry import REFERENCE_ENGINES, OracleOptions, register

_ORACLE = "cross_dbms"
_QUORUM = 3
_SCHEMA_LEAK = re.compile(r"coevo_ref_[0-9a-fA-F]+")
_SECRET = re.compile(r"(?i)(password\s*=\s*)\S+")
_VERSION_ALIAS = re.compile(
    r"(^|[_-])old($|[_-])|(^|[_-])\d+\.\d+",
    re.IGNORECASE,
)
_KNOWN_VERSION_ALIASES = frozenset({
    "duckdb_old",
    "datafusion_old",
    "duckdb-1.1.3",
    "datafusion-50.0.0",
})

Factory = Callable[[], Any]


@dataclass(frozen=True)
class _Execution:
    result: QueryResult
    version: str


def default_reference_factories(target_engine: str) -> dict[str, Factory]:
    """Independent engines other than ``target_engine``.

    The map is the default used when options omit ``reference_factories``.
    An empty map supplied by the caller is not filled in here.
    """
    if target_engine not in REFERENCE_ENGINES:
        raise ValueError(
            f"target_engine: must be one of {REFERENCE_ENGINES}, got {target_engine!r}"
        )
    factories = _runner_factories()
    return {
        engine: factories[engine]
        for engine in REFERENCE_ENGINES
        if engine != target_engine
    }


def collect_reference_results(
    case: SqlCase,
    reference_factories: dict[str, Any],
    *,
    timeout_s: float,
) -> dict[str, QueryResult]:
    """Run ``case`` on each reference factory.

    The target engine is not included. A reference that fails setup or
    execution is returned as an error ``QueryResult`` and is not dropped.
    Unknown ids, the target id, and version aliases raise ``ValueError``
    before any factory is called.
    """
    _validate_reference_factories(reference_factories, case.engine)
    executions = _collect_executions(case, reference_factories, timeout_s=timeout_s)
    return {engine: execution.result for engine, execution in executions.items()}


def judge_case(
    case: SqlCase,
    *,
    factory: Factory,
    timeout_s: float,
    options: OracleOptions,
) -> Label:
    """Label ``case`` by a quorum of independent engines."""
    full = full_query(case)
    if not is_readonly_query(full):
        return invalid_label(_ORACLE, "not_applicable", full)

    target, setup_error = _run_target(case, factory, timeout_s)
    participants = {
        case.engine: _participant(target.result, target.version),
    }
    if setup_error is not None:
        return invalid_label(
            _ORACLE,
            "setup_error",
            full,
            error=setup_error,
            extra=_evidence([], [], participants),
        )

    failure = _target_failure(target.result)
    if failure is not None:
        kind, reason = failure
        if kind == "crash":
            return _crash_label(full, target.result, participants)
        return invalid_label(
            _ORACLE,
            reason,
            full,
            error=target.result.error,
            extra=_evidence([], [], participants),
        )

    supplied = options.reference_factories
    factories = default_reference_factories(case.engine) if supplied is None else supplied
    for engine, execution in _collect_executions(case, factories, timeout_s=timeout_s).items():
        participants[engine] = _participant(execution.result, execution.version)
    return _adjudicate(case.engine, full, participants)


def _adjudicate(target_engine: str, full: str, participants: dict[str, dict[str, Any]]) -> Label:
    votes = {
        engine: _signature_from_bag(participants[engine]["bag"])
        for engine in sorted(participants)
        if participants[engine]["ok"]
    }
    voters = sorted(votes)
    if len(votes) < _QUORUM:
        return invalid_label(
            _ORACLE,
            "insufficient_engines",
            full,
            extra=_evidence(voters, [], participants),
        )

    # Insertion order is the sorted engine id, so a plurality tie does not
    # depend on dict order. The class is not itself a fail.
    odd, cls = classify_divergence(votes)
    outliers = sorted(odd)
    if len(set(votes.values())) == 1:
        return pass_label(
            _ORACLE, full, extra=_evidence(voters, [], participants)
        )
    if cls == "majority" and outliers == [target_engine]:
        behavior = _difference(
            _majority_bag(votes, participants, target_engine),
            participants[target_engine]["bag"],
        )
        return Label(
            y="fail",
            oracle=_ORACLE,
            fail_kind="wrong_result",
            identity=IdentityEvidence(behavior=behavior),
            detail=_detail(full, _evidence(voters, outliers, participants)),
        )
    return invalid_label(
        _ORACLE,
        "non_unique_outlier",
        full,
        extra=_evidence(voters, outliers, participants),
    )


def _run_target(case: SqlCase, factory: Factory, timeout_s: float) -> tuple[_Execution, str | None]:
    runner = factory()
    try:
        version = _version_of(case.engine, runner)
        outcomes = runner.setup(list(case.setup))
        setup_error = _first_setup_error(outcomes)
        if setup_error is not None:
            return _Execution(QueryResult(error=setup_error), version), setup_error
        result = runner.run(full_query(case), timeout_s=timeout_s)
        if not isinstance(result, QueryResult):
            raise RuntimeError("target run did not return QueryResult")
        if result.error is not None:
            result.error = _stable_text(result.error)
        return _Execution(result, version), None
    finally:
        runner.close()


def _collect_executions(
    case: SqlCase,
    reference_factories: dict[str, Any],
    *,
    timeout_s: float,
) -> dict[str, _Execution]:
    _validate_reference_factories(reference_factories, case.engine)
    executions: dict[str, _Execution] = {}
    for engine in sorted(reference_factories):
        executions[engine] = _run_reference(
            engine, reference_factories[engine], case, timeout_s
        )
    return executions


def _run_reference(engine: str, factory: Factory, case: SqlCase, timeout_s: float) -> _Execution:
    """One reference. Failures become error results; ``close`` still runs."""
    runner: Any = None
    version = "unknown"
    execution: _Execution | None = None
    try:
        runner = factory()
        version = _version_of(engine, runner)
        outcomes = runner.setup(list(case.setup))
        setup_error = _first_setup_error(outcomes)
        if setup_error is not None:
            execution = _Execution(QueryResult(error=setup_error), version)
        else:
            result = runner.run(full_query(case), timeout_s=timeout_s)
            if not isinstance(result, QueryResult):
                execution = _Execution(
                    QueryResult(error="reference run did not return QueryResult"),
                    version,
                )
            else:
                if result.error is not None:
                    result.error = _stable_text(result.error)
                execution = _Execution(result, version)
    except Exception as exc:
        execution = _Execution(
            QueryResult(error=_stable_text(f"{type(exc).__name__}: {exc}")),
            version,
        )
    finally:
        if runner is not None:
            try:
                runner.close()
            except Exception:
                # The recorded result stays. A raising close must not erase a bag
                # that already executed, and must not escape into the target label.
                if execution is None:
                    execution = _Execution(
                        QueryResult(error="reference close failed"),
                        version,
                    )
    assert execution is not None
    return execution


def _validate_reference_factories(reference_factories: Any, target_engine: str) -> None:
    if not isinstance(reference_factories, dict):
        raise ValueError(
            "reference_factories: expected a dict or None, "
            f"got {reference_factories!r}"
        )
    for engine_id, factory in reference_factories.items():
        _reject_reference_id(engine_id, target_engine)
        if not callable(factory):
            raise ValueError(
                f"reference_factories: factory for {engine_id!r} must be callable, "
                f"got {factory!r}"
            )


def _reject_reference_id(engine_id: Any, target_engine: str) -> None:
    if not isinstance(engine_id, str):
        raise ValueError(
            f"reference_factories: engine ids must be strings, got {engine_id!r}"
        )
    if engine_id in _KNOWN_VERSION_ALIASES or _VERSION_ALIAS.search(engine_id):
        raise ValueError(
            f"reference_factories: {engine_id!r} is a version alias, "
            "not an independent engine"
        )
    if engine_id == target_engine:
        raise ValueError(
            f"reference_factories: target engine {target_engine!r} "
            "cannot appear as a reference"
        )
    if engine_id not in REFERENCE_ENGINES:
        raise ValueError(f"reference_factories: unknown engine {engine_id!r}")


def _runner_factories() -> dict[str, Factory]:
    from targets.datafusion_runner import DataFusionRunner
    from targets.duckdb_runner import DuckDBRunner
    from targets.sqlite_runner import SQLiteRunner

    return {
        "duckdb": DuckDBRunner,
        "datafusion": DataFusionRunner,
        "sqlite": SQLiteRunner,
        "postgres": PostgresReferenceRunner,
    }


def _version_of(engine: str, runner: Any) -> str:
    value: Any = None
    try:
        value = getattr(runner, "engine_version", None)
        if callable(value):
            value = value()
    except Exception:
        value = None
    if isinstance(value, str) and value.strip():
        return _stable_text(value.strip()) or "unknown"
    try:
        return _library_version(engine)
    except Exception:
        return "unknown"


def _library_version(engine: str) -> str:
    if engine == "duckdb":
        import duckdb

        return str(duckdb.__version__)
    if engine == "datafusion":
        import datafusion

        return str(datafusion.__version__)
    if engine == "sqlite":
        import sqlite3

        return str(sqlite3.sqlite_version)
    return "unknown"


def _first_setup_error(outcomes: Any) -> str | None:
    for item in outcomes:
        _statement, error = item
        if error is not None:
            return _stable_text(str(error))
    return None


def _target_failure(result: QueryResult) -> tuple[str, str] | None:
    """A target that did not return a bag. ``None`` means it can vote."""
    if result.timed_out:
        return ("invalid", "timeout")
    if result.is_internal_error or is_internal_error(result.error):
        return ("crash", "crash")
    if result.ok:
        return None
    if is_value_dependent_error(result.error):
        return ("invalid", "value_dependent_error")
    return ("invalid", "query_error")


def _is_vote(result: QueryResult) -> bool:
    if result.timed_out or not result.ok:
        return False
    if result.is_internal_error or is_internal_error(result.error):
        return False
    return True


def _signature(rows: Any) -> tuple[tuple[str, int], ...]:
    bag = loose_bag(normalize_rows(rows))
    return tuple(sorted((str(key), int(count)) for key, count in bag.items()))


def _signature_from_bag(bag: list[list[Any]]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted((str(key), int(count)) for key, count in bag))


def _participant(result: QueryResult, version: str) -> dict[str, Any]:
    voted = _is_vote(result)
    return {
        "ok": voted,
        "version": version,
        "error": result.error,
        "timed_out": bool(result.timed_out),
        "internal": bool(result.is_internal_error or is_internal_error(result.error)),
        "bag": [[key, count] for key, count in _signature(result.rows)] if voted else [],
    }


def _majority_bag(
    votes: dict[str, tuple[tuple[str, int], ...]],
    participants: dict[str, dict[str, Any]],
    target_engine: str,
) -> list[list[Any]]:
    """Loose bag of one reference that sits in the plurality, not the target."""
    top = Counter(votes.values()).most_common(1)[0][0]
    for engine in sorted(votes):
        if engine != target_engine and votes[engine] == top:
            return participants[engine]["bag"]
    raise RuntimeError("unique target outlier has no majority reference")


def _difference(majority_bag: list[list[Any]], target_bag: list[list[Any]]) -> dict[str, int]:
    """Counts of loose rows in the majority but not the target, and the reverse.

    ``missing`` is what the target dropped relative to the agreeing references.
    ``extra`` is what the target returned that those references did not.
    """
    left: Counter[str] = Counter({str(key): int(count) for key, count in majority_bag})
    right: Counter[str] = Counter({str(key): int(count) for key, count in target_bag})
    return {
        "missing": int(sum((left - right).values())),
        "extra": int(sum((right - left).values())),
    }


def _crash_label(full: str, result: QueryResult, participants: dict[str, dict[str, Any]]) -> Label:
    error = result.error or ""
    error_class = error.split(":", 1)[0] if error else None
    return Label(
        y="fail",
        oracle=_ORACLE,
        fail_kind="crash",
        identity=IdentityEvidence(error_class=error_class, behavior={}),
        detail=_detail(full, _evidence([], [], participants), error=error or None),
    )


def _evidence(
    voters: list[str],
    outliers: list[str],
    participants: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    ordered = {engine: participants[engine] for engine in sorted(participants)}
    return {
        "voters": list(voters),
        "outliers": list(outliers),
        "participants": ordered,
    }


def _detail(full: str, extra: dict[str, Any], error: str | None = None) -> dict[str, Any]:
    detail = {"full_query": full, **extra}
    if error is not None:
        detail["error"] = error
    return detail


def _stable_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = _SCHEMA_LEAK.sub("coevo_ref", value)
    return _SECRET.sub(r"\1<hidden>", text)


register(_ORACLE, judge_case)
