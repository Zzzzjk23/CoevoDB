"""Shared recording and label mapping for the three sound-oracle adapters.

The old ``check()`` decides whether two forms differ. This module only turns
that outcome, plus the results it recorded, into a ``Label``.
"""

from __future__ import annotations

from typing import Any

from oracles.db_runner import QueryResult
from oracles.errors import is_value_dependent_error
from oracles.models import KIND_CRASH

from surprise.harness.contracts import IdentityEvidence, Label

# One recorded execution: the SQL text passed to run(), and the result it returned.
RunCall = tuple[str, QueryResult]


class RecordingRunner:
    """Delegate ``run`` to an inner runner and keep every ``(sql, result)`` pair.

    The old oracles see this object as their runner. Setup stays on the inner
    runner so screening and the recorded execution do not share a connection.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.calls: list[RunCall] = []

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        result = self._inner.run(sql, timeout_s=timeout_s)
        self.calls.append((sql, result))
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def fail_kind_of(candidate: Any) -> str:
    """Map a ``Candidate`` onto ``crash`` / ``error_mismatch`` / ``wrong_result``."""
    if candidate.kind == KIND_CRASH:
        return "crash"
    if _summary_error(candidate.r1_summary) or _summary_error(candidate.r2_summary):
        return "error_mismatch"
    return "wrong_result"


def error_class_of(candidate: Any) -> str | None:
    """Exception class of the failing side, the text before the first colon.

    When both summaries carry an error, the second result wins.
    """
    text = _summary_error(candidate.r2_summary) or _summary_error(candidate.r1_summary)
    if not text:
        return None
    return text.split(":", 1)[0]


def _summary_error(summary: Any) -> str:
    if not isinstance(summary, dict):
        return ""
    error = summary.get("error")
    if isinstance(error, str) and error:
        return error
    return ""


def outcome_from_results(
    results: list[QueryResult],
) -> tuple[str, str | None, str | None]:
    """Split an old-oracle ``None`` into pass or invalid.

    Returns ``(y, invalid_reason, error_text)``. A timeout wins over an error.
    ``error_text`` is the first error string when the invalid reason is an error.
    """
    if any(result.timed_out for result in results):
        return "invalid", "timeout", None
    errors = [result.error or "" for result in results if not result.ok]
    if not errors:
        return "pass", None, None
    if all(is_value_dependent_error(error) for error in errors):
        return "invalid", "value_dependent_error", errors[0]
    return "invalid", "query_error", errors[0]


def _detail(full: str, extra: dict[str, Any] | None, error: str | None = None) -> dict[str, Any]:
    detail: dict[str, Any] = {"full_query": full}
    if extra:
        detail.update(extra)
    if error is not None:
        detail["error"] = error
    return detail


def pass_label(oracle: str, full: str, *, extra: dict[str, Any] | None = None) -> Label:
    return Label(y="pass", oracle=oracle, detail=_detail(full, extra))


def invalid_label(
    oracle: str,
    reason: str,
    full: str,
    *,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> Label:
    return Label(
        y="invalid",
        oracle=oracle,
        invalid_reason=reason,
        detail=_detail(full, extra, error),
    )


def label_from_results(
    oracle: str,
    full: str,
    results: list[QueryResult],
    *,
    extra: dict[str, Any] | None = None,
) -> Label:
    """Apply the shared None-splitting rule to recorded query-form results."""
    y, reason, error = outcome_from_results(results)
    if y == "pass":
        return pass_label(oracle, full, extra=extra)
    assert reason is not None
    return invalid_label(oracle, reason, full, error=error, extra=extra)


def fail_label(
    oracle: str,
    candidate: Any,
    full: str,
    *,
    behavior: dict[str, Any] | None = None,
    switches: tuple[str, ...] = (),
    extra: dict[str, Any] | None = None,
) -> Label:
    """Build a fail label from one old-oracle ``Candidate``.

    ``behavior`` is required for ``wrong_result`` and ignored otherwise.
    ``switches`` is empty except for a plan variant that names its switch.
    """
    kind = fail_kind_of(candidate)
    if kind == "wrong_result":
        if behavior is None:
            raise RuntimeError("wrong_result label is missing a behavior profile")
        identity = IdentityEvidence(switches=switches, error_class=None, behavior=behavior)
    else:
        identity = IdentityEvidence(
            switches=switches,
            error_class=error_class_of(candidate),
            behavior={},
        )
    detail = _detail(full, extra)
    detail["candidate_kind"] = candidate.kind
    detail["notes"] = candidate.notes
    detail["q1"] = candidate.q1
    detail["q2"] = candidate.q2
    return Label(y="fail", oracle=oracle, fail_kind=kind, identity=identity, detail=detail)


def multiset_difference(first: QueryResult, second: QueryResult) -> dict[str, int]:
    """Row counts in ``first`` but not ``second`` (missing) and the reverse (extra)."""
    left = first.bag()
    right = second.bag()
    return {
        "missing": int(sum((left - right).values())),
        "extra": int(sum((right - left).values())),
    }


def scalar_count(result: QueryResult) -> int:
    """The single count cell of a NoREC query. NULL and an empty result are 0."""
    if not result.rows:
        return 0
    value = result.rows[0][0]
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(float(value))
    return int(value)
