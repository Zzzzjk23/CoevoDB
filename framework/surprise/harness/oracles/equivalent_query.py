"""Equivalent-query oracle over the frozen mechanical rewrite rules.

A difference is a fail only when ``apply_rule`` produced the statement that
ran. An unknown rule, a paired query with no certified product, or a paired
query that is not that product is ``untrusted_rewrite`` and is not executed.
Keyword case and whitespace outside tokens may differ; literals, quoted
identifiers, dollar quotes, and comments may not. ``EquivalenceOracle`` still
decides whether the two bags differ; a ``None`` from it is split into pass
or invalid from the recorded results.

A library rule is judged only after reference engines agree on the two bags.
One dissenting reference, fewer than ``LIBRARY_MIN_REFERENCES`` agreements,
or an error on only the rewritten side is ``untrusted_rewrite``, not a fail.
Frozen rules do not consult references, and their labels gain no keys.
"""

from __future__ import annotations

from typing import Any

from oracles.db_runner import QueryResult, bags_equal
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
from .rewrites import (
    LIBRARY_MIN_REFERENCES,
    RULES,
    apply_rule,
    is_library_rule,
    is_read_only_query,
    load_library,
    same_statement,
)

ORACLE = "equivalent_query"


def judge_case(
    case: SqlCase, *, factory, timeout_s: float, options: OracleOptions
) -> Label:
    """Run one certified rewrite beside the original statement."""
    full = full_query(case)
    rule_id = "double_negation" if options.rewrite_rule is None else options.rewrite_rule
    entry = _library_entry(rule_id)
    if rule_id not in RULES and entry is None:
        return _untrusted(full, rule_id)
    rewritten = apply_rule(full, rule_id)
    if options.paired_query is not None and (
        rewritten is None or not _same_query(options.paired_query, rewritten)
    ):
        if entry is None:
            return _untrusted(full, rule_id)
        return invalid_label(
            ORACLE, "untrusted_rewrite", full,
            extra=_library_extra(rule_id, entry, rewritten=rewritten),
        )
    if rewritten is None or not is_read_only_query(rewritten):
        if entry is None:
            extra = {"rule": rule_id, "applicability": "rule_form"}
        else:
            extra = _library_extra(rule_id, entry)
            extra["applicability"] = "rule_form"
        return invalid_label(ORACLE, "not_applicable", full, extra=extra)

    runner = factory()
    try:
        outcomes = runner.setup(list(case.setup))
        for _statement, error in outcomes:
            if error is not None:
                if entry is None:
                    extra = {"rule": rule_id}
                else:
                    extra = _library_extra(rule_id, entry, rewritten=rewritten)
                return invalid_label(
                    ORACLE, "setup_error", full, error=error, extra=extra,
                )
        references = None
        if entry is not None:
            references = _reference_status(case, full, rewritten, options, timeout_s)
            premise = _reference_premise(references)
            if premise is not None:
                return invalid_label(
                    ORACLE, "untrusted_rewrite", full,
                    extra=_library_extra(
                        rule_id, entry, rewritten=rewritten,
                        references=references, premise=premise,
                    ),
                )
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
        extra: dict[str, Any] = {"rule": rule_id, "rewritten": rewritten}
        if entry is not None:
            extra = _library_extra(
                rule_id, entry, rewritten=rewritten, references=references,
            )
            if candidate is not None and fail_kind_of(candidate) == "error_mismatch":
                extra["premise"] = "rewrite_error"
                return invalid_label(
                    ORACLE, "untrusted_rewrite", full, extra=extra,
                )
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


def _library_entry(rule_id: str) -> dict | None:
    """The library record for ``rule_id``. Absent rules are not trusted."""
    if not is_library_rule(rule_id):
        return None
    return load_library().get(rule_id)


def _library_extra(
    rule_id: str,
    entry: dict,
    *,
    rewritten: str | None = None,
    references: dict[str, str] | None = None,
    premise: str | None = None,
) -> dict[str, Any]:
    extra: dict[str, Any] = {
        "rule": rule_id,
        "layer": "library",
        "kind": entry["kind"],
        "template": entry["template"],
    }
    if references is not None:
        extra["references"] = dict(references)
    if rewritten is not None:
        extra["rewritten"] = rewritten
    if premise is not None:
        extra["premise"] = premise
    return extra


def _reference_premise(references: dict[str, str]) -> str | None:
    if any(status == "disagree" for status in references.values()):
        return "reference_disagrees"
    agree = sum(status == "agree" for status in references.values())
    if agree < LIBRARY_MIN_REFERENCES:
        return "too_few_references"
    return None


def _reference_status(
    case: SqlCase,
    original: str,
    rewritten: str,
    options: OracleOptions,
    timeout_s: float,
) -> dict[str, str]:
    """Compare the two statements on each reference engine."""
    from .cross_dbms import default_reference_factories

    supplied = options.reference_factories
    factories = default_reference_factories(case.engine) if supplied is None else supplied
    return {
        engine: _one_reference(factories[engine], case, original, rewritten, timeout_s)
        for engine in sorted(factories)
    }


def _one_reference(factory, case: SqlCase, original: str, rewritten: str, timeout_s: float) -> str:
    """``agree``, ``disagree``, or ``skipped``. A failing reference is skipped."""
    runner = None
    try:
        runner = factory()
        outcomes = runner.setup(list(case.setup))
        for _statement, error in outcomes:
            if error is not None:
                return "skipped"
        left = runner.run(original, timeout_s=timeout_s)
        right = runner.run(rewritten, timeout_s=timeout_s)
        if not _succeeded(left) or not _succeeded(right):
            return "skipped"
        return "agree" if bags_equal(left, right) else "disagree"
    except Exception:
        # One reference that cannot run does not decide the target. The count
        # of agreements still has to reach LIBRARY_MIN_REFERENCES.
        return "skipped"
    finally:
        if runner is not None:
            try:
                runner.close()
            except Exception:
                pass


def _succeeded(result: Any) -> bool:
    return (
        isinstance(result, QueryResult)
        and result.ok
        and not result.timed_out
        and not result.is_internal_error
    )


def _untrusted(full: str, rule_id: str) -> Label:
    return invalid_label(ORACLE, "untrusted_rewrite", full, extra={"rule": rule_id})


def _same_query(left: str, right: str) -> bool:
    """Certified-text equality. Never used as a query to execute."""
    return same_statement(left, right)


register(ORACLE, judge_case)
