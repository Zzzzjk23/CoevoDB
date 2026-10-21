"""Final labels. Tier 1 reruns a fail; tier 2 attributes it; tier 3 minimises and profiles it."""

from __future__ import annotations

import builtins
import sys
from typing import Any

from diagnosis.bisect import prelude_for_names

from surprise.harness.constants import (
    CVE_ATTRIBUTION_WALL_TIMEOUT_S,
    CVE_PROFILE_WALL_TIMEOUT_S,
    CVE_RERUN_ATTEMPTS,
    CVE_RERUN_EXTENDED,
    CVE_WALL_TIMEOUT_S,
    QUERY_TIMEOUT_S,
)
from surprise.harness.contracts import IdentityEvidence, Label, SqlCase
from surprise.harness.oracles.forms import full_query
from surprise.harness.oracles.registry import make_options, runner_factory_for, validate_request

from .criterion import attribute, context_for, executed_query, list_interventions
from .hypothesis import ParsedHypothesis, ensure_known, parse_hypothesis
from .isolate import call_worker, ensure_importable, execute_isolated
from .premise import check_premises
from .session import judgement_signature, run_judge
from .tier3 import diagnose_case

_ATTRIBUTING = ("cross_dbms", "version_differential")
_SINGLE_THREAD = {"duckdb": ["threads"], "datafusion": ["target_par1"], "postgres": ["parallel"]}
_NOT_REQUESTED = {"status": "skipped", "reason": "not_requested"}
# Default-factory intervention names, filled from the child. A custom factory is not cached.
_DEFAULT_INTERVENTION_NAMES: dict[str, list[str]] = {}


def certify(
    case: SqlCase,
    oracle: str,
    *,
    hypothesis: Any = None,
    diagnose: bool = False,
    isolation: str = "process",
    runner_factory: Any = None,
    timeout_s: float = QUERY_TIMEOUT_S,
    wall_timeout_s: float | None = None,
    rewrite_rule: str | None = None,
    paired_query: str | None = None,
    old_python: str | None = None,
    reference_factories: dict[str, Any] | None = None,
) -> Label:
    """Return the final label. ``cve`` is always filled in.

    Illegal requests, a factory a child cannot import, and an unusable
    ``hypothesis`` raise ``ValueError`` before the original judgement. Tier 2
    and tier 3 run only after tier 1 has confirmed a fail. Other exceptions
    from ``judge`` propagate.
    """
    if isolation not in ("process", "inline"):
        raise ValueError(f"isolation: must be 'process' or 'inline', got {isolation!r}")
    options = make_options(
        rewrite_rule=rewrite_rule,
        paired_query=paired_query,
        old_python=old_python,
        reference_factories=reference_factories,
    )
    validate_request(case, oracle, options)
    factory_ref = None
    reference_refs = None
    if isolation == "process":
        if runner_factory is not None:
            factory_ref = ensure_importable(runner_factory, "runner_factory")
        if reference_factories is not None:
            reference_refs = {
                engine: ensure_importable(factory, f"reference_factories[{engine!r}]")
                for engine, factory in reference_factories.items()
            }
    wall = CVE_WALL_TIMEOUT_S if wall_timeout_s is None else wall_timeout_s
    parsed = None
    if hypothesis is not None:
        parsed = prepare_hypothesis(
            hypothesis,
            case,
            isolation=isolation,
            runner_factory=runner_factory,
            wall_timeout_s=CVE_ATTRIBUTION_WALL_TIMEOUT_S,
            factory_ref=factory_ref,
        )
    kind, payload, transcript = _judge_once(
        case,
        oracle,
        isolation=isolation,
        runner_factory=runner_factory,
        factory_ref=factory_ref,
        timeout_s=timeout_s,
        wall=wall,
        prelude=(),
        rewrite_rule=rewrite_rule,
        paired_query=paired_query,
        old_python=old_python,
        reference_factories=reference_factories,
        reference_refs=reference_refs,
    )
    if kind == "timeout":
        return _timeout_label(case, oracle, isolation)
    if kind == "crash":
        confirmed = _from_crash(
            case,
            oracle,
            isolation=isolation,
            exit_code=payload,
            runner_factory=runner_factory,
            timeout_s=timeout_s,
            wall=wall,
            rewrite_rule=rewrite_rule,
            paired_query=paired_query,
            old_python=old_python,
            reference_factories=reference_factories,
            reference_refs=reference_refs,
            factory_ref=factory_ref,
        )
    else:
        confirmed = payload
        if confirmed.y != "fail":
            return _with_cve(confirmed, _skipped_cve(0, isolation, _raw(confirmed), "not_a_candidate"))
        confirmed = _tier1(
            case,
            oracle,
            confirmed,
            transcript,
            isolation=isolation,
            runner_factory=runner_factory,
            factory_ref=factory_ref,
            timeout_s=timeout_s,
            wall=wall,
            rewrite_rule=rewrite_rule,
            paired_query=paired_query,
            old_python=old_python,
            reference_factories=reference_factories,
            reference_refs=reference_refs,
        )
    return _after_tier1(
        confirmed,
        parsed,
        diagnose=diagnose,
        case=case,
        oracle=oracle,
        isolation=isolation,
        runner_factory=runner_factory,
        factory_ref=factory_ref,
        timeout_s=timeout_s,
        rewrite_rule=rewrite_rule,
        paired_query=paired_query,
        old_python=old_python,
        reference_factories=reference_factories,
        reference_refs=reference_refs,
    )


def prepare_hypothesis(
    hypothesis: Any,
    case: SqlCase,
    *,
    isolation: str,
    runner_factory: Any,
    wall_timeout_s: float,
    factory_ref: str | None = None,
) -> ParsedHypothesis:
    """Validate ``hypothesis`` before the original judgement.

    Naming an intervention asks the engine which names exist. Under process
    isolation that question runs in a child, so the caller executes no SQL.
    """
    parsed = parse_hypothesis(hypothesis, case.engine)
    if not parsed.interventions:
        return parsed
    names = _intervention_names(
        case.engine,
        isolation=isolation,
        runner_factory=runner_factory,
        factory_ref=factory_ref,
        wall=wall_timeout_s,
    )
    ensure_known(parsed, names)
    return parsed


def _after_tier1(
    label: Label,
    parsed: ParsedHypothesis | None,
    *,
    diagnose: bool,
    case: SqlCase,
    oracle: str,
    isolation: str,
    runner_factory: Any,
    factory_ref: str | None,
    timeout_s: float,
    rewrite_rule: str | None,
    paired_query: str | None,
    old_python: str | None,
    reference_factories: dict[str, Any] | None,
    reference_refs: dict[str, str] | None,
) -> Label:
    """Attribute a confirmed fail, then minimise and profile when that is required."""
    if label.y != "fail":
        return _note_tier1_rejection(label, hypothesis=parsed is not None, diagnose=diagnose)
    if parsed is None and not diagnose:
        return label
    cve = dict(label.cve)
    if parsed is not None:
        attribution, skip = _run_attribution(
            parsed,
            label,
            case=case,
            oracle=oracle,
            isolation=isolation,
            runner_factory=runner_factory,
            factory_ref=factory_ref,
            timeout_s=timeout_s,
            rewrite_rule=rewrite_rule,
            paired_query=paired_query,
            old_python=old_python,
            reference_factories=reference_factories,
            reference_refs=reference_refs,
        )
        if attribution is None:
            cve["attribution"] = {"status": "skipped", "reason": skip}
            if not diagnose:
                return _with_cve(label, cve)
        else:
            cve["attribution"] = {"status": "ran", "reason": None, **attribution}
            if attribution["consistent"]:
                cve["tier"] = 2
                cve["minimize"] = {"status": "skipped", "reason": "attributed"}
                cve["profile"] = {"status": "skipped", "reason": "attributed"}
                return _with_cve(label, cve)
    return _run_tier3(
        label,
        cve,
        case=case,
        oracle=oracle,
        isolation=isolation,
        runner_factory=runner_factory,
        factory_ref=factory_ref,
        timeout_s=timeout_s,
        rewrite_rule=rewrite_rule,
        paired_query=paired_query,
        old_python=old_python,
        reference_factories=reference_factories,
        reference_refs=reference_refs,
    )


def _run_attribution(
    parsed: ParsedHypothesis, label: Label, **kwargs: Any
) -> tuple[dict[str, Any] | None, str | None]:
    """One membership test. A timeout or a crash is ``(None, reason)``."""
    if kwargs["isolation"] == "inline":
        factory = _resolve_factory(kwargs["case"], kwargs["runner_factory"])
        context = context_for(
            kwargs["case"],
            kwargs["oracle"],
            label,
            factory=factory,
            timeout_s=kwargs["timeout_s"],
            rewrite_rule=kwargs["rewrite_rule"],
            paired_query=kwargs["paired_query"],
            old_python=kwargs["old_python"],
            reference_factories=kwargs["reference_factories"],
        )
        result = attribute(
            parsed,
            context,
            kwargs["case"].engine,
            list(kwargs["case"].setup),
            executed_query(kwargs["case"], kwargs["oracle"]),
            kwargs["paired_query"],
            label,
        )
        return result, None
    data = _call_json(
        _worker_payload("attribute", hypothesis=parsed.to_dict(), label=label.to_dict(), **kwargs),
        CVE_ATTRIBUTION_WALL_TIMEOUT_S,
    )
    if data.get("_skip"):
        return None, str(data["_skip"])
    return _attribution_fields(data), None


def _run_tier3(label: Label, cve: dict[str, Any], **kwargs: Any) -> Label:
    if kwargs["isolation"] == "inline":
        factory = _resolve_factory(kwargs["case"], kwargs["runner_factory"])
        outcome = diagnose_case(
            kwargs["case"],
            kwargs["oracle"],
            label,
            factory=factory,
            timeout_s=kwargs["timeout_s"],
            rewrite_rule=kwargs["rewrite_rule"],
            paired_query=kwargs["paired_query"],
            old_python=kwargs["old_python"],
            reference_factories=kwargs["reference_factories"],
        )
    else:
        data = _call_json(
            _worker_payload("diagnose", label=label.to_dict(), **kwargs),
            CVE_PROFILE_WALL_TIMEOUT_S,
        )
        if data.get("_skip"):
            reason = str(data["_skip"])
            cve["minimize"] = {"status": "skipped", "reason": reason}
            cve["profile"] = {"status": "skipped", "reason": reason}
            return _with_cve(label, cve)
        outcome = data
    return _apply_tier3(label, cve, outcome)


def _apply_tier3(label: Label, cve: dict[str, Any], outcome: dict[str, Any]) -> Label:
    kind = outcome.get("kind")
    minimize = outcome.get("minimize")
    if not isinstance(minimize, dict):
        raise RuntimeError("diagnose result is missing minimize")
    cve = dict(cve)
    cve["tier"] = 3
    cve["minimize"] = {"status": "ran", "reason": None, **minimize}
    if kind == "not_reproduced":
        cve["profile"] = {"status": "skipped", "reason": "not_reproduced_minimized"}
        return Label(
            y="invalid",
            oracle=label.oracle,
            invalid_reason="not_reproduced_minimized",
            detail=label.detail,
            cve=cve,
        )
    if kind == "premise":
        premise = outcome.get("premise")
        reason = outcome.get("invalid_reason")
        if not isinstance(premise, dict) or not isinstance(reason, str) or reason == "":
            raise RuntimeError("diagnose premise result is malformed")
        cve["premise"] = premise
        cve["profile"] = {"status": "skipped", "reason": reason}
        return Label(
            y="invalid",
            oracle=label.oracle,
            invalid_reason=reason,
            detail=label.detail,
            cve=cve,
        )
    if kind != "profiled":
        raise RuntimeError(f"diagnose result kind is {kind!r}")
    profile = outcome.get("profile")
    if not isinstance(profile, dict):
        raise RuntimeError("diagnose result is missing profile")
    cve["profile"] = {"status": "ran", "reason": None, **profile}
    fix_set = profile.get("fix_set")
    if not isinstance(fix_set, list) or not all(isinstance(item, str) for item in fix_set):
        raise RuntimeError("diagnose profile.fix_set must be a list of strings")
    switches = tuple(fix_set) if fix_set else label.identity.switches
    identity = IdentityEvidence(
        switches=switches,
        error_class=label.identity.error_class,
        behavior=label.identity.behavior,
    )
    return Label(
        y="fail",
        oracle=label.oracle,
        fail_kind=label.fail_kind,
        identity=identity,
        detail=label.detail,
        cve=cve,
    )


def _note_tier1_rejection(label: Label, *, hypothesis: bool, diagnose: bool) -> Label:
    """Record which later tiers the caller asked for after a tier-1 downgrade.

    A pass, a timeout, and a harness error never reach here. A step the caller
    did not ask for keeps the reason tier 1 already wrote.
    """
    if not hypothesis and not diagnose:
        return label
    cve = dict(label.cve)
    if hypothesis:
        cve["attribution"] = {"status": "skipped", "reason": "tier1_rejected"}
    if diagnose or hypothesis:
        cve["minimize"] = {"status": "skipped", "reason": "tier1_rejected"}
        cve["profile"] = {"status": "skipped", "reason": "tier1_rejected"}
    return _with_cve(label, cve)


def _intervention_names(
    engine: str,
    *,
    isolation: str,
    runner_factory: Any,
    factory_ref: str | None,
    wall: float,
) -> list[str]:
    if isolation == "inline":
        return list_interventions(engine, _resolve_factory_engine(engine, runner_factory))
    if runner_factory is None:
        cached = _DEFAULT_INTERVENTION_NAMES.get(engine)
        if cached is not None:
            return list(cached)
    data = _call_json(
        {
            "op": "interventions",
            "sys_path": list(sys.path),
            "engine": engine,
            "runner_factory": factory_ref,
        },
        wall,
    )
    if data.get("_skip"):
        raise RuntimeError(f"hypothesis: intervention list {data['_skip']}")
    names = data.get("names")
    if not isinstance(names, list) or not all(isinstance(item, str) for item in names):
        raise RuntimeError("hypothesis: intervention list missing")
    if runner_factory is None:
        _DEFAULT_INTERVENTION_NAMES[engine] = list(names)
    return list(names)


def _worker_payload(op: str, *, label: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    case: SqlCase = kwargs["case"]
    payload: dict[str, Any] = {
        "op": op,
        "sys_path": list(sys.path),
        "case": case.to_dict(),
        "oracle": kwargs["oracle"],
        "timeout_s": kwargs["timeout_s"],
        "engine": case.engine,
        "runner_factory": kwargs["factory_ref"],
        "reference_factories": kwargs["reference_refs"],
        "rewrite_rule": kwargs["rewrite_rule"],
        "paired_query": kwargs["paired_query"],
        "old_python": kwargs["old_python"],
        "label": label,
    }
    if "hypothesis" in kwargs:
        payload["hypothesis"] = kwargs["hypothesis"]
    return payload


def _call_json(payload: dict[str, Any], wall: float) -> dict[str, Any]:
    outcome = call_worker(payload, wall)
    if outcome["kind"] == "timeout":
        return {"_skip": "timeout"}
    if outcome["kind"] == "crash":
        return {"_skip": "crash"}
    data = outcome["data"]
    if not isinstance(data, dict):
        raise RuntimeError("worker returned a non-object")
    if data.get("op") == "raise":
        _reraise(data)
    return data


def _attribution_fields(data: dict[str, Any]) -> dict[str, Any]:
    hypothesis_id = data.get("hypothesis_id")
    method = data.get("method")
    consistent = data.get("consistent")
    executions = data.get("executions")
    if (
        not isinstance(hypothesis_id, str)
        or hypothesis_id == ""
        or method not in ("fix_set", "profile")
        or not isinstance(consistent, bool)
        or isinstance(executions, bool)
        or not isinstance(executions, int)
    ):
        raise RuntimeError("attribution result is malformed")
    return {
        "hypothesis_id": hypothesis_id,
        "method": method,
        "consistent": consistent,
        "executions": executions,
    }


def _resolve_factory(case: SqlCase, runner_factory: Any) -> Any:
    return _resolve_factory_engine(case.engine, runner_factory)


def _resolve_factory_engine(engine: str, runner_factory: Any) -> Any:
    if runner_factory is not None:
        return runner_factory
    return runner_factory_for(engine)


def _tier1(case: SqlCase, oracle: str, label: Label, transcript: list[dict[str, Any]], **kwargs: Any) -> Label:
    isolation = kwargs["isolation"]
    premise = check_premises(
        case,
        oracle,
        label,
        _probe(case, kwargs["isolation"], kwargs["runner_factory"], kwargs["timeout_s"], kwargs["wall"]),
    )
    if premise["violations"]:
        cve = _base_cve(1, isolation, _raw(label))
        cve["rerun"] = {"status": "skipped", "reason": "premise_violated"}
        cve["premise"] = premise
        return Label(
            y="invalid",
            oracle=oracle,
            invalid_reason=premise["violations"][0],
            detail=label.detail,
            cve=cve,
        )
    signature = judgement_signature(label, transcript)
    stats = _rerun(signature, case, oracle, **kwargs)
    cve = _base_cve(1, isolation, _raw(label))
    cve["rerun"] = {
        "status": "ran",
        "reason": None,
        "attempts": stats["attempts"],
        "reproduced": stats["reproduced"],
        "stable": stats["stable"],
        "extended": stats["extended"],
        "distinct_outcomes": stats["distinct_outcomes"],
        "single_thread": stats["single_thread"],
    }
    cve["premise"] = premise
    if stats["stable"]:
        return _with_cve(label, cve)
    return Label(
        y="invalid",
        oracle=oracle,
        invalid_reason="unstable_rerun",
        detail=label.detail,
        cve=cve,
    )


def _rerun(signature: str, case: SqlCase, oracle: str, **kwargs: Any) -> dict[str, Any]:
    outcomes = [_judge_signature(case, oracle, prelude=(), **kwargs) for _ in range(CVE_RERUN_ATTEMPTS)]
    distinct = {signature, *(item for item in outcomes)}
    reproduced = sum(1 for item in outcomes if item == signature)
    if reproduced != CVE_RERUN_ATTEMPTS:
        return {
            "attempts": CVE_RERUN_ATTEMPTS,
            "reproduced": reproduced,
            "stable": False,
            "extended": False,
            "distinct_outcomes": len(distinct),
            "single_thread": {"ran": False, "reproduced": None},
        }
    single = _judge_signature(case, oracle, prelude=_single_thread_prelude(case.engine), **kwargs)
    if single == signature:
        return {
            "attempts": CVE_RERUN_ATTEMPTS,
            "reproduced": reproduced,
            "stable": True,
            "extended": False,
            "distinct_outcomes": len(distinct),
            "single_thread": {"ran": True, "reproduced": True},
        }
    extended = [
        _judge_signature(case, oracle, prelude=(), **kwargs) for _ in range(CVE_RERUN_EXTENDED)
    ]
    outcomes.extend(extended)
    distinct.update(extended)
    reproduced = sum(1 for item in outcomes if item == signature)
    attempts = CVE_RERUN_ATTEMPTS + CVE_RERUN_EXTENDED
    return {
        "attempts": attempts,
        "reproduced": reproduced,
        "stable": reproduced == attempts,
        "extended": True,
        "distinct_outcomes": len(distinct),
        "single_thread": {"ran": True, "reproduced": False},
    }


def _judge_signature(case: SqlCase, oracle: str, *, prelude: tuple[str, ...], **kwargs: Any) -> str:
    kind, payload, transcript = _judge_once(case, oracle, prelude=prelude, **kwargs)
    if kind == "timeout":
        return "wall-timeout"
    if kind == "crash":
        label = _crash_label(oracle, case, int(payload))
        return judgement_signature(label, [])
    return judgement_signature(payload, transcript)


def _from_crash(case: SqlCase, oracle: str, *, exit_code: int, isolation: str, **kwargs: Any) -> Label:
    label = _crash_label(oracle, case, int(exit_code))
    if oracle in _ATTRIBUTING:
        confirmed = execute_isolated(
            case,
            timeout_s=kwargs["timeout_s"],
            wall_timeout_s=kwargs["wall"],
            runner_factory=kwargs["runner_factory"],
        )
        if confirmed.status != "crash":
            cve = _skipped_cve(1, isolation, _raw(label), "unattributed_crash")
            return Label(
                y="invalid",
                oracle=oracle,
                invalid_reason="unattributed_crash",
                detail=label.detail,
                cve=cve,
            )
    return _tier1(case, oracle, label, [], isolation=isolation, **kwargs)


def _judge_once(
    case: SqlCase,
    oracle: str,
    *,
    isolation: str,
    runner_factory: Any,
    factory_ref: str | None,
    timeout_s: float,
    wall: float,
    prelude: tuple[str, ...],
    rewrite_rule: str | None,
    paired_query: str | None,
    old_python: str | None,
    reference_factories: dict[str, Any] | None,
    reference_refs: dict[str, str] | None,
) -> tuple[str, Any, list[dict[str, Any]]]:
    if isolation == "inline":
        factory = runner_factory if runner_factory is not None else runner_factory_for(case.engine)
        label, transcript = run_judge(
            case,
            oracle,
            factory=factory,
            timeout_s=timeout_s,
            prelude=prelude,
            rewrite_rule=rewrite_rule,
            paired_query=paired_query,
            old_python=old_python,
            reference_factories=reference_factories,
        )
        return "label", label, transcript
    payload = {
        "op": "judge",
        "sys_path": list(sys.path),
        "case": case.to_dict(),
        "oracle": oracle,
        "timeout_s": timeout_s,
        "rewrite_rule": rewrite_rule,
        "paired_query": paired_query,
        "old_python": old_python,
        "runner_factory": factory_ref,
        "reference_factories": reference_refs,
        "prelude": list(prelude),
    }
    outcome = call_worker(payload, wall)
    if outcome["kind"] == "timeout":
        return "timeout", None, []
    if outcome["kind"] == "crash":
        return "crash", int(outcome["exit_code"]), []
    data = outcome["data"]
    if data.get("op") == "raise":
        _reraise(data)
    label = Label.from_dict(data["label"])
    transcript = data.get("transcript")
    if not isinstance(transcript, list):
        transcript = []
    return "label", label, transcript


def _probe(case: SqlCase, isolation: str, runner_factory: Any, timeout_s: float, wall: float):
    def probe(sql: str) -> tuple[str, Any]:
        if isolation == "process":
            result = execute_isolated(
                SqlCase(engine=case.engine, setup=case.setup, query=sql),
                timeout_s=timeout_s,
                wall_timeout_s=wall,
                runner_factory=runner_factory,
            )
            value = result.rows[0][0] if result.rows and result.rows[0] else None
            return result.status, value
        factory = runner_factory if runner_factory is not None else runner_factory_for(case.engine)
        runner = factory()
        try:
            try:
                outcomes = runner.setup(list(case.setup))
            except Exception as exc:  # noqa: BLE001 - a probe failure is a violated premise
                return "error", f"{type(exc).__name__}: {exc}"
            for _statement, error in outcomes:
                if error is not None:
                    return "error", str(error)
            try:
                result = runner.run(sql, timeout_s=timeout_s)
            except Exception as exc:  # noqa: BLE001
                return "error", f"{type(exc).__name__}: {exc}"
        finally:
            try:
                runner.close()
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


def _single_thread_prelude(engine: str) -> tuple[str, ...]:
    names = _SINGLE_THREAD.get(engine)
    if not names:
        return ()
    return tuple(prelude_for_names(engine, list(names)))


def _crash_label(oracle: str, case: SqlCase, exit_code: int) -> Label:
    return Label(
        y="fail",
        oracle=oracle,
        fail_kind="crash",
        identity=IdentityEvidence(error_class="ProcessExit", behavior={"exit_code": exit_code}),
        detail={
            "full_query": full_query(case),
            "error": f"ProcessExit: exit code {exit_code}",
        },
    )


def _timeout_label(case: SqlCase, oracle: str, isolation: str) -> Label:
    raw = {
        "y": "invalid",
        "fail_kind": None,
        "invalid_reason": "timeout",
        "identity": IdentityEvidence().to_dict(),
    }
    return Label(
        y="invalid",
        oracle=oracle,
        invalid_reason="timeout",
        detail={"full_query": full_query(case)},
        cve=_skipped_cve(0, isolation, raw, "timeout"),
    )


def _raw(label: Label) -> dict[str, Any]:
    return {
        "y": label.y,
        "fail_kind": label.fail_kind,
        "invalid_reason": label.invalid_reason,
        "identity": label.identity.to_dict(),
    }


def _skipped_cve(tier: int, isolation: str, raw: dict[str, Any], reason: str) -> dict[str, Any]:
    cve = _base_cve(tier, isolation, raw)
    step = {"status": "skipped", "reason": reason}
    for name in ("rerun", "premise", "attribution", "minimize", "profile"):
        cve[name] = dict(step)
    return cve


def _base_cve(tier: int, isolation: str, raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": 1,
        "tier": tier,
        "isolation": isolation,
        "raw": raw,
        "rerun": {"status": "skipped", "reason": "not_a_candidate"},
        "premise": {"status": "skipped", "reason": "not_a_candidate"},
        "attribution": dict(_NOT_REQUESTED),
        "minimize": dict(_NOT_REQUESTED),
        "profile": dict(_NOT_REQUESTED),
    }


def _with_cve(label: Label, cve: dict[str, Any]) -> Label:
    return Label(
        y=label.y,
        oracle=label.oracle,
        fail_kind=label.fail_kind,
        invalid_reason=label.invalid_reason,
        identity=label.identity,
        detail=label.detail,
        cve=cve,
    )


def _reraise(data: dict[str, Any]) -> None:
    name = str(data.get("type") or "RuntimeError")
    message = str(data.get("message") or "")
    module = data.get("module")
    if module == "builtins":
        cls = getattr(builtins, name, None)
        if isinstance(cls, type) and issubclass(cls, Exception):
            raise cls(message)
    raise RuntimeError(f"{name}: {message}")
