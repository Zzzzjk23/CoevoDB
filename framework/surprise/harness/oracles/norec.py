"""Three-valued adapter for the NoREC count oracle.

``NoRECOracle.check`` decides whether the optimized count and the per-row
reference count disagree. This module only maps that outcome to a label.
"""

from __future__ import annotations

from oracles.norec import NoRECOracle, norec_applicable

from surprise.harness.contracts import Label, SqlCase

from .common import (
    RecordingRunner,
    fail_kind_of,
    fail_label,
    label_from_results,
    scalar_count,
)


def norec_applies(case: SqlCase) -> bool:
    """True when the old NoREC premise holds for this case."""
    return norec_applicable(case.query, case.predicate)


def judge_norec(
    case: SqlCase,
    recorded: RecordingRunner,
    timeout_s: float,
    full: str,
) -> Label:
    """Run ``NoRECOracle`` and map its candidate or ``None`` to a label."""
    candidate = NoRECOracle().check(
        recorded,
        case.query,
        case.predicate,
        list(case.setup),
        [],
        timeout_s=timeout_s,
    )
    if candidate is None:
        return label_from_results("norec", full, [result for _, result in recorded.calls])
    behavior = _norec_behavior(recorded) if fail_kind_of(candidate) == "wrong_result" else None
    return fail_label("norec", candidate, full, behavior=behavior)


def _norec_behavior(recorded: RecordingRunner) -> dict[str, int]:
    """``missing`` is how far the reference exceeds the optimized count, else ``extra``.

    ``NoRECOracle.check`` runs a probe, then the optimized ``COUNT(*) ... WHERE``,
    then the ``SUM(CASE ...)`` reference, and only then reports a count mismatch.
    NULL counts as 0, matching the old oracle.
    """
    calls = recorded.calls
    if len(calls) < 3:
        raise RuntimeError("norec count mismatch did not record the optimized and reference counts")
    optimized = scalar_count(calls[-2][1])
    reference = scalar_count(calls[-1][1])
    return {
        "missing": max(reference - optimized, 0),
        "extra": max(optimized - reference, 0),
    }
