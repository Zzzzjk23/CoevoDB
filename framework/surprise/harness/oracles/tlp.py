"""Three-valued adapter for WHERE, GROUP BY, and DISTINCT ternary partitioning.

Which rows differ is decided by ``TLPOracle`` or ``TLPGroupByOracle``. This
module picks the form, and turns the recorded results into a label.
"""

from __future__ import annotations

from collections import Counter

from oracles.tlp import TLPOracle, tlp_applicable
from oracles.tlp_groupby import CLEAN, CRASH, HIT, TLPGroupByOracle, rowset

from surprise.harness.contracts import Label, SqlCase

from .common import (
    RecordingRunner,
    fail_kind_of,
    fail_label,
    label_from_results,
    pass_label,
)
from .forms import split_grouped


def tlp_form(case: SqlCase) -> str | None:
    """``where``, ``groupby``, ``distinct``, or None when TLP's premise fails.

    WHERE wins when the plain oracle accepts the query. Otherwise a recognized
    grouped or distinct shape is used. An empty predicate is not applicable.
    """
    if case.predicate is None or not case.predicate.strip():
        return None
    if tlp_applicable(case.query, case.predicate):
        return "where"
    form = split_grouped(case.query)
    if form is None:
        return None
    if form.group_by is None:
        return "distinct"
    return "groupby"


def judge_tlp(
    case: SqlCase,
    recorded: RecordingRunner,
    timeout_s: float,
    full: str,
    form: str,
) -> Label:
    """Run the old TLP oracle for ``form`` and map its outcome to a label."""
    extra = {"form": form}
    if form == "where":
        return _judge_where(case, recorded, timeout_s, full, extra)
    return _judge_grouped(case, recorded, timeout_s, full, extra)


def _judge_where(
    case: SqlCase,
    recorded: RecordingRunner,
    timeout_s: float,
    full: str,
    extra: dict[str, str],
) -> Label:
    candidate = TLPOracle().check(
        recorded,
        case.query,
        case.predicate,
        list(case.setup),
        [],
        timeout_s=timeout_s,
    )
    results = [result for _, result in recorded.calls]
    if candidate is None:
        return label_from_results("tlp", full, results, extra=extra)
    behavior = _where_behavior(recorded) if fail_kind_of(candidate) == "wrong_result" else None
    return fail_label("tlp", candidate, full, behavior=behavior, extra=extra)


def _where_behavior(recorded: RecordingRunner) -> dict[str, int]:
    """Unpartitioned bag versus the multiset sum of the three partitions.

    ``TLPOracle.check`` runs the original query first and then the three
    partitions, and only reports a result mismatch after all four succeed.
    """
    calls = recorded.calls
    if len(calls) < 4:
        raise RuntimeError("tlp result mismatch did not record the original and three partitions")
    original = calls[0][1].bag()
    combined: Counter = Counter()
    for _, result in calls[1:4]:
        combined += result.bag()
    return {
        "missing": int(sum((original - combined).values())),
        "extra": int(sum((combined - original).values())),
    }


def _judge_grouped(
    case: SqlCase,
    recorded: RecordingRunner,
    timeout_s: float,
    full: str,
    extra: dict[str, str],
) -> Label:
    form = split_grouped(case.query)
    if form is None or case.predicate is None:
        raise RuntimeError("tlp grouped form disappeared between screening and execution")
    status, candidates = TLPGroupByOracle().check(
        recorded,
        select_list=form.select_list,
        from_tail=form.from_tail,
        predicate=case.predicate,
        group_by=form.group_by,
        base_where=form.base_where,
        schema_sqls=list(case.setup),
        inserts=[],
        timeout_s=timeout_s,
    )
    if status in (HIT, CRASH) and candidates:
        candidate = candidates[0]
        behavior = (
            _grouped_behavior(recorded) if fail_kind_of(candidate) == "wrong_result" else None
        )
        return fail_label("tlp", candidate, full, behavior=behavior, extra=extra)
    if status == CLEAN:
        return pass_label("tlp", full, extra=extra)
    return label_from_results(
        "tlp", full, [result for _, result in recorded.calls], extra=extra
    )


def _grouped_behavior(recorded: RecordingRunner) -> dict[str, int]:
    """Key set of the unpartitioned query versus the union of the three partitions.

    ``TLPGroupByOracle.check`` runs the original first, then the three
    partitions, and compares those sets only after every partition succeeded.
    """
    calls = recorded.calls
    if len(calls) < 4:
        raise RuntimeError("tlp grouped mismatch did not record the original and three partitions")
    original = rowset(calls[0][1].rows)
    union: set[str] = set()
    for _, result in calls[1:4]:
        union |= rowset(result.rows)
    return {"missing": len(original - union), "extra": len(union - original)}
