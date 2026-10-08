"""Final labels. Tier 1 reruns a fail candidate; tier 2 and 3 are not in this package."""

from __future__ import annotations

import builtins
import sys
from typing import Any

from diagnosis.bisect import prelude_for_names

from surprise.harness.constants import CVE_RERUN_ATTEMPTS, CVE_RERUN_EXTENDED, CVE_WALL_TIMEOUT_S, QUERY_TIMEOUT_S
from surprise.harness.contracts import IdentityEvidence, Label, SqlCase
from surprise.harness.oracles.forms import full_query
from surprise.harness.oracles.registry import make_options, runner_factory_for, validate_request

from .isolate import call_worker, ensure_importable, execute_isolated
from .premise import check_premises
from .session import judgement_signature, run_judge

_ATTRIBUTING = ("cross_dbms", "version_differential")
_SINGLE_THREAD = {"duckdb": ["threads"], "datafusion": ["target_par1"]}
_NOT_REQUESTED = {"status": "skipped", "reason": "not_requested"}


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

    Illegal requests and factories a child cannot import raise ``ValueError``
    before anything executes. ``hypothesis`` and ``diagnose`` raise
    ``NotImplementedError``. Other exceptions from ``judge`` propagate.
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
    if hypothesis is not None or diagnose:
        raise NotImplementedError("hypothesis and diagnose are implemented in a later package")

    wall = CVE_WALL_TIMEOUT_S if wall_timeout_s is None else wall_timeout_s
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
        return _from_crash(
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
    label: Label = payload
    if label.y != "fail":
        return _with_cve(label, _skipped_cve(0, isolation, _raw(label), "not_a_candidate"))
    return _tier1(
        case,
        oracle,
        label,
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
