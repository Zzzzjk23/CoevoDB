"""Equivalent-query oracle over the frozen mechanical rewrite rules.

A difference is a fail only when ``apply_rule`` produced the statement that
ran. An unknown rule, a paired query with no certified product, or a paired
query that is not that product is ``untrusted_rewrite`` and is not executed.
Keyword case and whitespace outside tokens may differ; literals, quoted
identifiers, dollar quotes, and comments may not. ``EquivalenceOracle`` still
decides whether the two bags differ; a ``None`` from it is split into pass
or invalid from the recorded results.
"""

from __future__ import annotations

from oracles.equivalence import EquivalenceOracle

from surprise.harness.contracts import Label, SqlCase

from .common import (
    RecordingRunner,
    fail_kind_of,
    fail_label,
    invalid_label,
    label_from_results,
    multiset_difference,
)
from .forms import full_query
from .registry import OracleOptions, register
from .rewrites import RULES, apply_rule, is_read_only_query, same_statement

ORACLE = "equivalent_query"


def judge_case(
    case: SqlCase, *, factory, timeout_s: float, options: OracleOptions
) -> Label:
    """Run one certified rewrite beside the original statement."""
    full = full_query(case)
    rule_id = "double_negation" if options.rewrite_rule is None else options.rewrite_rule
    if rule_id not in RULES:
        return _untrusted(full, rule_id)
    rewritten = apply_rule(full, rule_id)
    if options.paired_query is not None and (
        rewritten is None or not _same_query(options.paired_query, rewritten)
    ):
        return _untrusted(full, rule_id)
    if rewritten is None or not is_read_only_query(rewritten):
        return invalid_label(
            ORACLE, "not_applicable", full,
            extra={"rule": rule_id, "applicability": "rule_form"},
        )

    runner = factory()
    try:
        outcomes = runner.setup(list(case.setup))
        for _statement, error in outcomes:
            if error is not None:
                return invalid_label(ORACLE, "setup_error", full, error=error, extra={"rule": rule_id})
        recorded = RecordingRunner(runner)
        candidate = EquivalenceOracle().check(
            recorded,
            full,
            rewritten,
            list(case.setup),
            [],
            category=ORACLE,
            rewrite_kind=rule_id,
            timeout_s=timeout_s,
        )
        extra = {"rule": rule_id, "rewritten": rewritten}
        results = [result for _sql, result in recorded.calls]
        if candidate is None:
            return label_from_results(ORACLE, full, results, extra=extra)
        behavior = None
        if fail_kind_of(candidate) == "wrong_result":
            if len(results) < 2:
                raise RuntimeError("equivalent-query mismatch did not record both sides")
            behavior = multiset_difference(results[0], results[1])
        return fail_label(
            ORACLE, candidate, full, behavior=behavior, switches=(rule_id,), extra=extra,
        )
    finally:
        runner.close()


def _untrusted(full: str, rule_id: str) -> Label:
    return invalid_label(ORACLE, "untrusted_rewrite", full, extra={"rule": rule_id})


def _same_query(left: str, right: str) -> bool:
    """Certified-text equality. Never used as a query to execute."""
    return same_statement(left, right)


register(ORACLE, judge_case)
