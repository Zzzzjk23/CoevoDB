"""SQLancer baseline transcribed from ``docs/FINAL_REPORT.md``.

The raw ``results/sqlancer_strong/`` tree is not on this machine. This module
only reads the summary table. It does not run SQLancer.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SUMMARY_PATH = Path(__file__).resolve().parent / "data" / "sqlancer_summary.json"

_SUMMARY_KEYS = (
    "schema",
    "transcribed",
    "source",
    "tool",
    "runs",
    "total_checks",
    "total_bugs",
    "approximate_checks",
    "engines",
    "note",
)
_ENGINE_KEYS = ("version", "oracles", "checks", "bugs")


def load(path: str | Path | None = None) -> dict[str, Any]:
    """Read a transcribed summary. The default is the summary shipped with this package."""
    file = SUMMARY_PATH if path is None else Path(path)
    if not file.is_file():
        raise ValueError(f"summary: file does not exist: {file}")
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"summary: not JSON: {file}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"summary: expected an object, got {type(data).__name__}")
    unknown = sorted(set(data) - set(_SUMMARY_KEYS))
    if unknown:
        raise ValueError(f"summary: unknown keys {unknown}")
    missing = [key for key in _SUMMARY_KEYS if key not in data]
    if missing:
        raise ValueError(f"summary: missing {', '.join(missing)}")
    if type(data["schema"]) is not int or data["schema"] != 1:
        raise ValueError(f"schema: expected 1, got {data['schema']!r}")
    if data["transcribed"] is not True:
        raise ValueError(f"transcribed: expected true, got {data['transcribed']!r}")
    _text(data["source"], "source")
    _text(data["tool"], "tool")
    _text(data["note"], "note")
    _count(data["runs"], "runs", minimum=0)
    _count(data["total_checks"], "total_checks", minimum=0)
    _count(data["total_bugs"], "total_bugs", minimum=0)
    if not isinstance(data["approximate_checks"], bool):
        raise ValueError(
            f"approximate_checks: expected a bool, got {data['approximate_checks']!r}"
        )
    engines = data["engines"]
    if not isinstance(engines, dict) or not engines:
        raise ValueError(f"engines: expected a non-empty object, got {engines!r}")
    check_sum = 0
    bug_sum = 0
    for name, row in engines.items():
        if not isinstance(name, str) or name == "":
            raise ValueError(f"engines: expected a non-empty name, got {name!r}")
        if not isinstance(row, dict):
            raise ValueError(f"engines.{name}: expected an object, got {row!r}")
        row_unknown = sorted(set(row) - set(_ENGINE_KEYS))
        row_missing = [key for key in _ENGINE_KEYS if key not in row]
        if row_unknown or row_missing:
            raise ValueError(f"engines.{name}: keys must be version, oracles, checks, bugs")
        _text(row["version"], f"engines.{name}.version")
        _count(row["oracles"], f"engines.{name}.oracles", minimum=0)
        checks = _count(row["checks"], f"engines.{name}.checks", minimum=1)
        bugs = _count(row["bugs"], f"engines.{name}.bugs", minimum=0)
        check_sum += checks
        bug_sum += bugs
    if check_sum != data["total_checks"]:
        raise ValueError(
            f"total_checks: {data['total_checks']} does not equal the sum of engine checks {check_sum}"
        )
    if bug_sum != data["total_bugs"]:
        raise ValueError(
            f"total_bugs: {data['total_bugs']} does not equal the sum of engine bugs {bug_sum}"
        )
    return data


def metrics(summary: Mapping[str, Any], engine: str = "duckdb") -> dict[str, Any]:
    """One engine's row, in the shape the report compares across arms.

    ``family_count`` is that engine's bug count. ``families_per_1000`` is
    ``1000 * bugs / checks``.
    """
    if not isinstance(summary, Mapping):
        raise ValueError(f"summary: expected an object, got {type(summary).__name__}")
    if summary.get("transcribed") is not True:
        raise ValueError(f"summary: transcribed must be true, got {summary.get('transcribed')!r}")
    engines = summary.get("engines")
    if not isinstance(engines, Mapping) or engine not in engines:
        raise ValueError(f"engine: unknown {engine!r}")
    row = engines[engine]
    if not isinstance(row, Mapping):
        raise ValueError(f"engine: {engine} is not an object")
    checks = row.get("checks")
    bugs = row.get("bugs")
    version = row.get("version")
    if type(checks) is not int or checks <= 0:
        raise ValueError(f"engine {engine}: checks must be a positive integer, got {checks!r}")
    if type(bugs) is not int or bugs < 0:
        raise ValueError(f"engine {engine}: bugs must be an integer >= 0, got {bugs!r}")
    if not isinstance(version, str) or version == "":
        raise ValueError(f"engine {engine}: version must be a non-empty string, got {version!r}")
    return {
        "kind": "sqlancer",
        "engine": engine,
        "version": version,
        "checks": checks,
        "family_count": bugs,
        "families_per_1000": 1000.0 * bugs / checks,
        "transcribed": True,
    }


def _text(value: object, where: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{where}: expected a non-empty string, got {value!r}")
    return value


def _count(value: object, where: str, *, minimum: int) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{where}: expected an integer >= {minimum}, got {value!r}")
    return value
