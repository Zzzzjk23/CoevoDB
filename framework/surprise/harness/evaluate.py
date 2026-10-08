"""Run one oracle judgement and append it to the experiment ledger.

Pass and invalid executions are recorded too. A failure inside ``judge`` is
stored as ``invalid`` / ``harness_error`` so the attempt is not lost.
Caller errors (unknown oracle, unsupported engine, illegal options, or a
record the ledger cannot store) raise before anything executes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from surprise.harness.constants import CVE_ATTRIBUTION_WALL_TIMEOUT_S, QUERY_TIMEOUT_S
from surprise.harness.contracts import ExperimentRecord, IdentityEvidence, Label, SqlCase
from surprise.harness.cve import certify
from surprise.harness.cve.certify import prepare_hypothesis
from surprise.harness.cve.isolate import ensure_importable
from surprise.harness.ledger import Ledger
from surprise.harness.oracles import judge
from surprise.harness.oracles.registry import make_options, validate_request


def evaluate(case: SqlCase, oracle: str, *, ledger: Ledger, run_id: str, purpose: str,
             spec: dict | None = None, phi: dict | None = None,
             theory_version: str | None = None, p_t: float | None = None,
             runner_factory=None, timeout_s: float = QUERY_TIMEOUT_S,
             rewrite_rule: str | None = None, paired_query: str | None = None,
             old_python: str | None = None, reference_factories=None) -> ExperimentRecord:
    """Judge ``case`` and append exactly one record. Return that record.

    An unknown oracle, an unsupported engine, illegal options, a ``run_id``
    that was never started, or any argument ``ExperimentRecord`` would reject
    raises before anything executes and leaves the ledger unchanged.
    """
    options = make_options(
        rewrite_rule=rewrite_rule,
        paired_query=paired_query,
        old_python=old_python,
        reference_factories=reference_factories,
    )
    validate_request(case, oracle, options)
    seq = ledger.next_seq(run_id)
    # Reject arguments that cannot be stored before opening a runner. The
    # placeholder is discarded; ExperimentRecord remains the only validator.
    ExperimentRecord(
        record_id=f"{run_id}:{seq}",
        run_id=run_id,
        seq=seq,
        case=case,
        label=Label(y="pass", oracle=oracle),
        purpose=purpose,
        created_at=datetime.now(timezone.utc).isoformat(),
        spec=spec,
        phi=phi,
        theory_version=theory_version,
        p_t=p_t,
        surprise=None,
    )

    try:
        label = judge(
            case, oracle, runner_factory=runner_factory, timeout_s=timeout_s,
            rewrite_rule=rewrite_rule, paired_query=paired_query,
            old_python=old_python, reference_factories=reference_factories,
        )
    except Exception as exc:
        # judge failed after the run was accepted; record the attempt instead of dropping it.
        label = Label(
            y="invalid",
            oracle=oracle,
            invalid_reason="harness_error",
            detail={"exception": f"{type(exc).__name__}: {exc}"},
        )

    seq = ledger.next_seq(run_id)
    record = ExperimentRecord(
        record_id=f"{run_id}:{seq}",
        run_id=run_id,
        seq=seq,
        case=case,
        label=label,
        purpose=purpose,
        created_at=datetime.now(timezone.utc).isoformat(),
        spec=spec,
        phi=phi,
        theory_version=theory_version,
        p_t=p_t,
        surprise=None,
    )
    ledger.append(record)
    return record


def evaluate_final(
    case: SqlCase,
    oracle: str,
    *,
    ledger: Ledger,
    run_id: str,
    purpose: str,
    spec: dict | None = None,
    phi: dict | None = None,
    theory_version: str | None = None,
    p_t: float | None = None,
    runner_factory=None,
    timeout_s: float = QUERY_TIMEOUT_S,
    rewrite_rule: str | None = None,
    paired_query: str | None = None,
    old_python: str | None = None,
    reference_factories=None,
    hypothesis=None,
    diagnose: bool = False,
    isolation: str = "process",
    wall_timeout_s: float | None = None,
) -> ExperimentRecord:
    """Certify ``case`` and append exactly one record.

    Validation matches :func:`evaluate`: a record the ledger would reject, a
    ``run_id`` that was never started, or an illegal request raises before
    anything executes and leaves the ledger unchanged. Other exceptions from
    ``certify`` are stored as ``invalid`` / ``harness_error`` with a complete
    ``cve`` object. An unusable ``hypothesis`` raises ``ValueError`` before a
    record is written. ``hypothesis`` and ``diagnose`` are passed through to
    ``certify``.
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
    if isolation == "process":
        if runner_factory is not None:
            factory_ref = ensure_importable(runner_factory, "runner_factory")
        if reference_factories is not None:
            for engine, factory in reference_factories.items():
                ensure_importable(factory, f"reference_factories[{engine!r}]")

    seq = ledger.next_seq(run_id)
    ExperimentRecord(
        record_id=f"{run_id}:{seq}",
        run_id=run_id,
        seq=seq,
        case=case,
        label=Label(y="pass", oracle=oracle),
        purpose=purpose,
        created_at=datetime.now(timezone.utc).isoformat(),
        spec=spec,
        phi=phi,
        theory_version=theory_version,
        p_t=p_t,
        surprise=None,
    )
    if hypothesis is not None:
        # Before the try, so a bad hypothesis is not stored as harness_error.
        prepare_hypothesis(
            hypothesis,
            case,
            isolation=isolation,
            runner_factory=runner_factory,
            wall_timeout_s=CVE_ATTRIBUTION_WALL_TIMEOUT_S,
            factory_ref=factory_ref,
        )

    try:
        label = certify(
            case,
            oracle,
            hypothesis=hypothesis,
            diagnose=diagnose,
            isolation=isolation,
            runner_factory=runner_factory,
            timeout_s=timeout_s,
            wall_timeout_s=wall_timeout_s,
            rewrite_rule=rewrite_rule,
            paired_query=paired_query,
            old_python=old_python,
            reference_factories=reference_factories,
        )
    except Exception as exc:
        label = _harness_error_label(oracle, isolation, exc)

    seq = ledger.next_seq(run_id)
    record = ExperimentRecord(
        record_id=f"{run_id}:{seq}",
        run_id=run_id,
        seq=seq,
        case=case,
        label=label,
        purpose=purpose,
        created_at=datetime.now(timezone.utc).isoformat(),
        spec=spec,
        phi=phi,
        theory_version=theory_version,
        p_t=p_t,
        surprise=None,
    )
    ledger.append(record)
    return record


def _harness_error_label(oracle: str, isolation: str, exc: BaseException) -> Label:
    raw = {
        "y": "invalid",
        "fail_kind": None,
        "invalid_reason": "harness_error",
        "identity": IdentityEvidence().to_dict(),
    }
    step = {"status": "skipped", "reason": "harness_error"}
    cve = {
        "schema": 1,
        "tier": 0,
        "isolation": isolation,
        "raw": raw,
        "rerun": dict(step),
        "premise": dict(step),
        "attribution": dict(step),
        "minimize": dict(step),
        "profile": dict(step),
    }
    return Label(
        y="invalid",
        oracle=oracle,
        invalid_reason="harness_error",
        detail={"exception": f"{type(exc).__name__}: {exc}"},
        cve=cve,
    )
