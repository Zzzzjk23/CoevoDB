"""Run one oracle judgement and append it to the experiment ledger.

Pass and invalid executions are recorded too. A failure inside ``judge`` is
stored as ``invalid`` / ``harness_error`` so the attempt is not lost.
"""

from __future__ import annotations

from datetime import datetime, timezone

from surprise.harness.constants import QUERY_TIMEOUT_S
from surprise.harness.contracts import ExperimentRecord, Label, SqlCase
from surprise.harness.ledger import Ledger
from surprise.harness.oracles import IMPLEMENTED, judge


def evaluate(case: SqlCase, oracle: str, *, ledger: Ledger, run_id: str, purpose: str,
             spec: dict | None = None, phi: dict | None = None,
             theory_version: str | None = None, p_t: float | None = None,
             runner_factory=None, timeout_s: float = QUERY_TIMEOUT_S) -> ExperimentRecord:
    """Judge ``case`` and append exactly one record. Return that record.

    An unknown oracle, an unsupported engine, a ``run_id`` that was never
    started, or any argument ``ExperimentRecord`` would reject raises before
    anything executes and leaves the ledger unchanged.
    """
    if oracle not in IMPLEMENTED:
        raise ValueError(f"oracle: must be one of {IMPLEMENTED}, got {oracle!r}")
    if case.engine != "duckdb":
        raise ValueError(f"engine: only 'duckdb' is supported, got {case.engine!r}")
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
        label = judge(case, oracle, runner_factory=runner_factory, timeout_s=timeout_s)
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
