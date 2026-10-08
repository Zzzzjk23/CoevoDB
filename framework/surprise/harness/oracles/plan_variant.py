"""Three-valued adapter for the plan-variant oracle.

Switch statements (``SET``, ``RESET``, ``PRAGMA``, ``FORCE CHECKPOINT``) are
ignored when a ``None`` from the old oracle is split into pass or invalid.
Only executions of the folded query count as query forms.
"""

from __future__ import annotations

from oracles.errors import is_guard_rail_error, is_value_dependent_error
from oracles.plan_variant import PlanVariantOracle

from surprise.harness.contracts import Label, SqlCase

from .common import (
    RecordingRunner,
    fail_kind_of,
    fail_label,
    invalid_label,
    label_from_results,
    multiset_difference,
    pass_label,
)


def judge_plan_variant(
    case: SqlCase,
    recorded: RecordingRunner,
    timeout_s: float,
    full: str,
) -> Label:
    """Run ``PlanVariantOracle`` on ``full`` and map its outcome to a label."""
    oracle = PlanVariantOracle(engine=case.engine)
    candidate = oracle.check(
        recorded,
        full,
        list(case.setup),
        [],
        timeout_s=timeout_s,
    )
    full_runs = [result for sql, result in recorded.calls if sql == full]
    if not full_runs:
        raise RuntimeError("plan variant finished without running the query")
    compared, skipped, saw_timeout = _classify_variants(full_runs, oracle.variants)
    extra = {"variants_compared": compared, "variants_skipped": skipped}
    if candidate is not None:
        behavior = None
        if fail_kind_of(candidate) == "wrong_result":
            behavior = _variant_behavior(candidate, full_runs, oracle.variants)
        return fail_label(
            "plan_variant",
            candidate,
            full,
            behavior=behavior,
            switches=_switches(candidate),
            extra=extra,
        )
    baseline = full_runs[0]
    if not baseline.ok or baseline.timed_out:
        return label_from_results("plan_variant", full, [baseline], extra=extra)
    if compared >= 1:
        return pass_label("plan_variant", full, extra=extra)
    reason = "timeout" if saw_timeout else "value_dependent_error"
    error = None if saw_timeout else _first_error(full_runs[1:])
    return invalid_label("plan_variant", reason, full, error=error, extra=extra)


def _switches(candidate: object) -> tuple[str, ...]:
    summary = getattr(candidate, "r2_summary", None)
    if not isinstance(summary, dict):
        return ()
    variant = summary.get("variant")
    if isinstance(variant, str) and variant:
        return (variant,)
    return ()


def _classify_variants(
    full_runs: list,
    variants: list,
) -> tuple[int, list[str], bool]:
    """Split variant executions into compared and skipped.

    The first ``full`` execution is the baseline. Execution ``i`` after that
    is ``variants[i]``. A variant counts as compared when it succeeded and did
    not time out. Timeouts, value-dependent errors, and guard-rail refusals
    are skips. A variant that produced the candidate is neither.
    """
    compared = 0
    skipped: list[str] = []
    saw_timeout = False
    for index, variant in enumerate(variants):
        if index + 1 >= len(full_runs):
            break
        label = variant[0]
        result = full_runs[index + 1]
        if result.timed_out:
            skipped.append(label)
            saw_timeout = True
            continue
        if result.ok:
            compared += 1
            continue
        if is_value_dependent_error(result.error) or is_guard_rail_error(result.error, label):
            skipped.append(label)
    return compared, skipped, saw_timeout


def _variant_behavior(candidate: object, full_runs: list, variants: list) -> dict[str, int]:
    """Baseline bag versus the bag of the variant named on the candidate."""
    summary = getattr(candidate, "r2_summary", None)
    label = summary.get("variant") if isinstance(summary, dict) else None
    index = next((i for i, variant in enumerate(variants) if variant[0] == label), None)
    if index is None or index + 1 >= len(full_runs):
        raise RuntimeError(f"plan variant {label!r} was not recorded")
    return multiset_difference(full_runs[0], full_runs[index + 1])


def _first_error(results: list) -> str | None:
    for result in results:
        if result.error:
            return result.error
    return None
