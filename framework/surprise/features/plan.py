"""Plan-layer features: operator names as the engine prints them.

DuckDB goes through ``diagnosis.bisect.plan_op_names`` (``EXPLAIN (FORMAT JSON)``).
DataFusion, and any other engine, uses the text of ``EXPLAIN``. The statement
itself is not executed. No operator, or an unreadable plan, is ``unavailable``.
"""
from __future__ import annotations

import re

from diagnosis.bisect import plan_op_names

from .limits import PROBE_TIMEOUT_S

# An operator name may contain only these characters. Anything else is skipped.
_OP_TOKEN = re.compile(r"[A-Za-z0-9_]+")


def extract_plan(runner, query: str, engine: str) -> tuple[set[str], str]:
    """Return ``(plan leaves, "ok" | "unavailable")``."""
    try:
        names = _operator_names(runner, query, engine)
    except Exception:
        return set(), "unavailable"
    if not names:
        return set(), "unavailable"
    leaves = {f"plan:{name}" for name in names if _OP_TOKEN.fullmatch(name)}
    if not leaves:
        return set(), "unavailable"
    return leaves, "ok"


def _operator_names(runner, query: str, engine: str) -> set[str] | None:
    kind = engine.casefold() if isinstance(engine, str) else ""
    if kind == "duckdb":
        counts = plan_op_names(runner, query, "duckdb")
        if not counts:
            return None
        return {str(name) for name in counts}
    return _explain_text_names(runner, query)


def _explain_text_names(runner, query: str) -> set[str] | None:
    result = _run(runner, "EXPLAIN " + query)
    if not _succeeded(result):
        return None
    text = _physical_plan(result)
    if text is None:
        return None
    names: set[str] = set()
    for line in text.splitlines():
        token = _leading_token(line)
        if token is not None:
            names.add(token)
    if not names:
        return None
    return names


def _physical_plan(result) -> str | None:
    rows = getattr(result, "rows", None) or []
    for row in rows:
        if not row:
            continue
        label = row[0]
        if isinstance(label, str) and label.strip().casefold() == "physical_plan":
            if len(row) > 1 and isinstance(row[1], str):
                return row[1]
            return None
    return None


def _leading_token(line: str) -> str | None:
    """The operator name that opens a plan line, before a colon or a space."""
    stripped = line.strip().lstrip("|").strip()
    if not stripped:
        return None
    token = re.split(r"[\s:]", stripped, maxsplit=1)[0]
    if not token:
        return None
    return token


def _run(runner, sql: str):
    try:
        return runner.run(sql, timeout_s=PROBE_TIMEOUT_S)
    except Exception:
        return None


def _succeeded(result) -> bool:
    if result is None or getattr(result, "timed_out", False):
        return False
    if getattr(result, "error", None):
        return False
    ok = getattr(result, "ok", True)
    return bool(ok)
