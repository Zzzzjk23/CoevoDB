"""One in-process execution or judgement, with a bag transcript of every statement."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from surprise.harness.contracts import Label, SqlCase
from surprise.harness.oracles import judge
from surprise.harness.oracles.registry import runner_factory_for


class CallLog:
    """Delegate to ``inner`` and append a bag fingerprint for every logged ``run``."""

    def __init__(self, inner: Any, bucket: list[dict[str, Any]]) -> None:
        self._inner = inner
        self._bucket = bucket

    def run(self, sql: str, timeout_s: float = 10.0) -> Any:
        result = self._inner.run(sql, timeout_s=timeout_s)
        self._bucket.append(fingerprint(sql, result))
        return result

    def run_unlogged(self, sql: str, timeout_s: float = 10.0) -> Any:
        return self._inner.run(sql, timeout_s=timeout_s)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class PreludeRunner:
    """Replay ``prelude`` after every ``setup`` so a reconnect cannot drop it.

    Prelude statements are not part of the judgement transcript: a single-thread
    rerun would otherwise differ from the raw judgement by those statements alone.
    """

    def __init__(self, inner: Any, prelude: tuple[str, ...], timeout_s: float) -> None:
        self._inner = inner
        self._prelude = prelude
        self._timeout_s = timeout_s

    def setup(self, statements: Any) -> Any:
        outcomes = self._inner.setup(statements)
        for statement in self._prelude:
            if hasattr(self._inner, "run_unlogged"):
                self._inner.run_unlogged(statement, timeout_s=self._timeout_s)
            else:
                self._inner.run(statement, timeout_s=self._timeout_s)
        return outcomes

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def fingerprint(sql: str, result: Any) -> dict[str, Any]:
    """One statement: a normalized row bag, an error class, or a timeout."""
    if bool(getattr(result, "timed_out", False)):
        return {"sql": sql, "kind": "timeout", "bag": None, "error_class": None}
    error = getattr(result, "error", None)
    if error is not None:
        text = str(error)
        error_class = text.split(":", 1)[0] if text else ""
        return {"sql": sql, "kind": "error", "bag": None, "error_class": error_class}
    bag = _bag(result)
    return {"sql": sql, "kind": "ok", "bag": bag, "error_class": None}


def judgement_signature(label: Label, transcript: list[dict[str, Any]]) -> str:
    """Canonical text of a raw verdict plus the bags it executed."""
    payload = {
        "y": label.y,
        "fail_kind": label.fail_kind,
        "invalid_reason": label.invalid_reason,
        "identity": label.identity.to_dict(),
        "statements": transcript,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def run_judge(
    case: SqlCase,
    oracle: str,
    *,
    factory: Any,
    timeout_s: float,
    prelude: tuple[str, ...] = (),
    rewrite_rule: str | None = None,
    paired_query: str | None = None,
    old_python: str | None = None,
    reference_factories: dict[str, Any] | None = None,
) -> tuple[Label, list[dict[str, Any]]]:
    """Judge once. Every runner the factory builds appends to the same transcript."""
    bucket: list[dict[str, Any]] = []

    def wrapped() -> Any:
        inner = factory()
        logged = CallLog(inner, bucket)
        if prelude:
            return PreludeRunner(logged, prelude, timeout_s)
        return logged

    label = judge(
        case,
        oracle,
        runner_factory=wrapped,
        timeout_s=timeout_s,
        rewrite_rule=rewrite_rule,
        paired_query=paired_query,
        old_python=old_python,
        reference_factories=reference_factories,
    )
    return label, bucket


def json_rows(rows: Any) -> list[Any]:
    """A JSON-safe copy of a row list."""
    try:
        copied = json.loads(json.dumps(rows))
    except (TypeError, ValueError):
        copied = json.loads(json.dumps(rows, default=str))
    if not isinstance(copied, list):
        return []
    return copied


def _bag(result: Any) -> list[list[Any]]:
    bag_fn = getattr(result, "bag", None)
    if callable(bag_fn):
        counter = bag_fn()
    else:
        rows = getattr(result, "rows", []) or []
        counter = Counter(json.dumps(row, sort_keys=True, default=str) for row in rows)
    return [[key, int(count)] for key, count in sorted(counter.items())]


def default_factory(engine: str) -> Any:
    return runner_factory_for(engine)
