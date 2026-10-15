"""Exploration prior: unit failure prices from engine history, calibrated by Brier score.

The prompt is a pure function of the units and the evidence lines. Record ids,
hypothesis ids, run ids, clocks, seeds, and absolute paths never enter it.
Prices change only the Hunter's unexplored-zone U; they do not label.
"""

from __future__ import annotations

import json
import math
from typing import Any

from surprise.features.units import _CONSTRUCTS
from surprise.theory.constants import RESIDUAL_PRIOR_FAILS, RESIDUAL_PRIOR_TESTS

from .base import Role, RoleContext
from .constants import (
    PRIOR_CALLS_PER_CHOICE,
    PRIOR_EVIDENCE_PER_CONSTRUCT,
    PRIOR_INITIAL_WEIGHT,
    PRIOR_MAX_TOKENS,
    PRIOR_MIN_SETTLED,
    PRIOR_STRENGTH,
    PRIOR_TEMPERATURE,
    PRIOR_TIER,
    PRIOR_UNITS_PER_CALL,
)
from .source import SourceError

# Keyword regex per construct name in features.units._CONSTRUCTS, plus "plain".
# `(?i)` because SourceReader.grep compiles the pattern with no flags of its own.
_CONSTRUCT_PATTERNS: dict[str, str | None] = {
    "dml": r"(?i)\bINSERT\b|\bUPDATE\b|\bDELETE\b|\bMERGE\b",
    "set_op_all": r"(?i)EXCEPT ALL|INTERSECT ALL|UNION ALL",
    "set_op": r"(?i)\bEXCEPT\b|\bINTERSECT\b|\bUNION\b",
    "window": r"(?i)OVER \(|window function",
    "correlated_subquery": r"(?i)correlated subquery|correlated",
    "subquery": r"(?i)\bEXISTS\b|\bIN\s*\(|subquery",
    "asof_join": r"(?i)ASOF",
    "outer_join": r"(?i)LEFT JOIN|RIGHT JOIN|FULL JOIN|outer join",
    "join": r"(?i)\bJOIN\b",
    "aggregate": r"(?i)GROUP BY|aggregate",
    "distinct": r"(?i)\bDISTINCT\b",
    "plain": None,
}

_ENGINE_SEARCH: dict[str, tuple[str, tuple[str, ...]]] = {
    "datafusion": ("dev/changelog", (".md",)),
    "duckdb": ("test/issues", (".test",)),
}

_UNPRICED_MISSING = "missing"
_UNPRICED_NOT_NUMBER = "not_number"
_UNPRICED_OUT_OF_RANGE = "out_of_range"
_UNPRICED_BAD_PREDICTION = "bad_prediction"

_KNOWN_CONSTRUCTS = {name for name, _needles in _CONSTRUCTS} | {"plain"}
if set(_CONSTRUCT_PATTERNS) != _KNOWN_CONSTRUCTS:
    missing = _KNOWN_CONSTRUCTS - set(_CONSTRUCT_PATTERNS)
    extra = set(_CONSTRUCT_PATTERNS) - _KNOWN_CONSTRUCTS
    raise RuntimeError(
        f"construct patterns must cover units._CONSTRUCTS: missing {sorted(missing)} extra {sorted(extra)}"
    )


def _reference_rate() -> float:
    return float(RESIDUAL_PRIOR_FAILS / RESIDUAL_PRIOR_TESTS)


def calibrated_weight(b_llm: float, b_ref: float) -> float:
    """``clip(1 - B_llm / B_ref, 0, 1)``, with the zero-reference boundary."""
    if b_ref == 0.0:
        return 1.0 if b_llm == 0.0 else 0.0
    return max(0.0, min(1.0, 1.0 - b_llm / b_ref))


def _p_fail(value: Any) -> tuple[float | None, str | None]:
    """Return ``(p, None)`` when ``value`` is a finite number in ``[0, 1]``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None, _UNPRICED_NOT_NUMBER
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        return None, _UNPRICED_OUT_OF_RANGE
    return number, None


def _unit_parts(unit: str) -> tuple[str, str] | None:
    parts = unit.split("|")
    if len(parts) < 3:
        return None
    return parts[0], parts[2]


def prior_evidence(units, readers) -> tuple[str, ...]:
    """Evidence lines from engine checkouts, one line per grep hit.

    Only ``ctx.readers`` is read. The project's own bug ledgers are never opened.
    The same ``(units, readers)`` pair always yields the same tuple.
    """
    if not readers:
        return ()
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for unit in units:
        if not isinstance(unit, str):
            continue
        parsed = _unit_parts(unit)
        if parsed is None:
            continue
        key = parsed
        if key in seen:
            continue
        seen.add(key)
        pairs.append(key)
    pairs.sort()
    lines: list[str] = []
    for engine, construct in pairs:
        reader = readers.get(engine)
        if reader is None:
            continue
        pattern = _CONSTRUCT_PATTERNS.get(construct)
        if not pattern:
            continue
        search = _ENGINE_SEARCH.get(engine)
        if search is None:
            continue
        under, suffixes = search
        try:
            hits = reader.grep(
                pattern,
                under=under,
                suffixes=suffixes,
                max_hits=PRIOR_EVIDENCE_PER_CONSTRUCT,
            )
        except SourceError:
            continue
        for hit in tuple(hits)[:PRIOR_EVIDENCE_PER_CONSTRUCT]:
            text = str(getattr(hit, "text", "")).strip()[:200]
            path = getattr(hit, "path", "")
            line = getattr(hit, "line", "")
            lines.append(f"EVIDENCE {engine} {path}:{line} {text}")
    return tuple(lines)


def prior_prompt(units, evidence) -> str:
    """English prompt for one batch. A pure function of ``units`` and ``evidence``."""
    lines = [
        "Estimate the probability that one valid test in each unit exposes a defect.",
        "A unit is a five-part name engine|oracle|construct|plan class|data class.",
        "engine is the database engine under test.",
        "oracle is the testing oracle that judges the statement.",
        "construct is the SQL construct (the third field).",
        "plan class is the query-plan class (the fourth field).",
        "data class is the data shape (the fifth field).",
        "A typical unit fails about 1 time in 100 valid tests (the reference rate).",
        "Units to price, one per line:",
    ]
    for unit in units:
        lines.append(f"UNIT {unit}")
    lines.append("Evidence lines from engine source history (changelog or issue tests):")
    for row in evidence:
        lines.append(str(row))
    lines.extend(
        [
            "Reply with one JSON object and no other text.",
            "prediction is a list of objects, one object per unit you price.",
            "unit is the unit string copied from a UNIT line.",
            "p_fail is a number in [0.0, 1.0], not a boolean.",
            "why is a short English reason.",
            "JSON shape:",
            '{"prediction": [{"unit": "engine|oracle|construct|plan|data", "p_fail": 0.0, "why": "reason"}]}',
        ]
    )
    return "\n".join(lines)


def build(ctx: RoleContext) -> ExplorationPrior:
    """Plugin entry: one exploration prior bound to ``ctx``."""
    return ExplorationPrior(ctx)


class ExplorationPrior(Role):
    """Prices untested units and turns those prices into residual pseudo-counts."""

    name = "prior"

    def __init__(self, ctx: RoleContext) -> None:
        self.ctx = ctx
        self._ref = _reference_rate()
        self._prices: dict[str, float] = {}
        self._asked: set[str] = set()
        self._calls_by_index: dict[int, int] = {}
        self._n_calls = 0
        self._n_settled = 0
        self._brier_llm = 0.0
        self._brier_ref = 0.0
        self._step_priced: list[str] = []
        self._step_settled = 0
        path = ctx.llm_dir / "prior.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._book = path.open("a", encoding="utf-8")

    def prepare(self, wb, units, *, index: int) -> None:
        if self._calls_by_index.get(index, 0) >= PRIOR_CALLS_PER_CHOICE:
            return
        batch = self._next_batch(units)
        if not batch:
            return
        prompt = prior_prompt(batch, prior_evidence(batch, self.ctx.readers))
        reply = self.ctx.gateway.call(
            "prior",
            prompt,
            tier=PRIOR_TIER,
            seed=self.ctx.seed,
            temperature=PRIOR_TEMPERATURE,
            max_tokens=PRIOR_MAX_TOKENS,
        )
        self._calls_by_index[index] = self._calls_by_index.get(index, 0) + 1
        self._n_calls += 1
        for unit in batch:
            self._asked.add(unit)
        self._write(
            {
                "type": "call",
                "units": list(batch),
                "status": reply.status,
                "reason": reply.reason,
                "key": reply.key,
            }
        )
        self._ingest(batch, reply)

    def pseudo(self, unit: str) -> tuple[float, float] | None:
        price = self._prices.get(unit)
        if price is None:
            return None
        weight = self.weight()
        p_eff = weight * price + (1.0 - weight) * self._ref
        return (p_eff * PRIOR_STRENGTH, PRIOR_STRENGTH)

    def weight(self) -> float:
        if self._n_settled < PRIOR_MIN_SETTLED:
            return float(PRIOR_INITIAL_WEIGHT)
        b_llm = self._brier_llm / self._n_settled
        b_ref = self._brier_ref / self._n_settled
        return calibrated_weight(b_llm, b_ref)

    def brier(self) -> dict:
        if self._n_settled == 0:
            llm: float | None = None
            reference: float | None = None
        else:
            llm = self._brier_llm / self._n_settled
            reference = self._brier_ref / self._n_settled
        return {
            "settled": int(self._n_settled),
            "llm": llm,
            "reference": reference,
            "weight": self.weight(),
        }

    def priced(self) -> dict:
        return dict(self._prices)

    def observe(self, event) -> None:
        prediction = event.prediction
        if getattr(prediction, "zone", None) != "unexplored":
            return
        unit = getattr(prediction, "unit", None)
        if not isinstance(unit, str) or unit not in self._prices:
            return
        record = event.record
        y = getattr(getattr(record, "label", None), "y", None)
        if y not in ("pass", "fail"):
            return
        outcome = 1.0 if y == "fail" else 0.0
        price = self._prices[unit]
        self._brier_llm += (price - outcome) ** 2
        self._brier_ref += (self._ref - outcome) ** 2
        self._n_settled += 1
        self._step_settled += 1
        self._write(
            {
                "type": "settle",
                "unit": unit,
                "y": y,
                "record_id": getattr(record, "record_id", None),
            }
        )

    def step(self) -> dict:
        result = {
            "priced": list(self._step_priced),
            "settled": int(self._step_settled),
            "weight": self.weight(),
        }
        self._step_priced = []
        self._step_settled = 0
        return result

    def report(self) -> dict:
        return {
            "priced": len(self._prices),
            "asked": len(self._asked),
            "calls": self._n_calls,
            "brier": self.brier(),
        }

    def manifest(self) -> dict:
        return {"reference_rate": self._ref, "strength": PRIOR_STRENGTH}

    def close(self) -> None:
        handle = self._book
        if handle is not None and not handle.closed:
            handle.flush()
            handle.close()

    def _next_batch(self, units) -> list[str]:
        pending: list[str] = []
        seen: set[str] = set()
        for unit in units:
            if not isinstance(unit, str) or unit in seen:
                continue
            seen.add(unit)
            if unit in self._asked or unit in self._prices:
                continue
            pending.append(unit)
        pending.sort()
        return pending[:PRIOR_UNITS_PER_CALL]

    def _ingest(self, batch: list[str], reply: Any) -> None:
        batch_set = set(batch)
        reasons = {unit: _UNPRICED_MISSING for unit in batch}
        if reply.status != "ok" or not isinstance(getattr(reply, "data", None), dict):
            reason = reply.reason or reply.status
            for unit in batch:
                self._write({"type": "unpriced", "unit": unit, "reason": reason})
            return
        raw = reply.data.get("prediction")
        if not isinstance(raw, list):
            for unit in batch:
                self._write({"type": "unpriced", "unit": unit, "reason": _UNPRICED_BAD_PREDICTION})
            return
        seen: set[str] = set()
        for item in raw:
            if not isinstance(item, dict):
                continue
            unit = item.get("unit")
            if not isinstance(unit, str) or unit not in batch_set or unit in seen:
                continue
            seen.add(unit)
            price, reason = _p_fail(item.get("p_fail"))
            if price is None:
                reasons[unit] = reason or _UNPRICED_NOT_NUMBER
                continue
            why = item.get("why")
            self._prices[unit] = price
            self._step_priced.append(unit)
            self._write(
                {
                    "type": "price",
                    "unit": unit,
                    "p": price,
                    "why": why if isinstance(why, str) else "",
                }
            )
        for unit in batch:
            if unit not in self._prices:
                self._write({"type": "unpriced", "unit": unit, "reason": reasons[unit]})

    def _write(self, row: dict[str, Any]) -> None:
        self._book.write(json.dumps(row, ensure_ascii=True) + "\n")
        self._book.flush()
