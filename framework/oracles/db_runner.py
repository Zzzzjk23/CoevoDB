"""Shared QueryResult and bags_equal for every runner, plus a compatibility export of DuckDBRunner.

DuckDBRunner now lives in targets.duckdb_runner and is re-exported after QueryResult is defined.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

@dataclass
class QueryResult:
    """Normalized outcome of one SQL execution."""

    rows: list[list[Any]] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    error: str | None = None
    is_internal_error: bool = False
    elapsed: float = 0.0
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None

    def bag(self) -> Counter:
        """Row multiset; ordering is ignored on purpose."""
        return Counter(
            json.dumps(row, sort_keys=True, default=str) for row in self.rows
        )

    def summary(self, max_rows: int = 8) -> dict[str, Any]:
        """Compact, JSON-safe description used in candidate records."""
        return {
            "ok": self.ok,
            "error": self.error,
            "is_internal_error": self.is_internal_error,
            "timed_out": self.timed_out,
            "row_count": len(self.rows),
            "columns": self.columns,
            "sample_rows": self.rows[:max_rows],
            "elapsed": round(self.elapsed, 4),
        }


def bags_equal(left: QueryResult, right: QueryResult) -> bool:
    """Compare two results as row multisets, ignoring order."""
    return left.bag() == right.bag()


# QueryResult stays here so the targets/oracles import cycle can finish. Re-export
# DuckDBRunner only after QueryResult exists (targets.duckdb_runner owns the class).
from targets.duckdb_runner import DuckDBRunner  # noqa: E402,F401
