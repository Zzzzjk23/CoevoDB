"""Run one oracle judgement and append it to the experiment ledger.

Pass and invalid executions are recorded too. A failure inside ``judge`` is
stored as ``invalid`` / ``harness_error`` so the attempt is not lost.
Caller errors (unknown oracle, unsupported engine, illegal options, or a
record the ledger cannot store) raise before anything executes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from surprise.harness.constants import QUERY_TIMEOUT_S
from surprise.harness.contracts import ExperimentRecord, Label, SqlCase
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
