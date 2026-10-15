"""How a hypothesis boundary lines up with the conditions of an upstream fix."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from surprise.features.registry import default_registry

_FIELDS = ("name", "engine", "key", "fix", "evidence", "conditions")
_TEXT = ("name", "engine", "key", "fix", "evidence")
_DATA = Path(__file__).resolve().parent / "data" / "fix_conditions.json"


def classify(specific: set, conditions: set) -> str:
    """``match``, ``too_wide``, ``too_narrow`` or ``mixed``.

    ``too_wide`` means ``specific`` is a proper subset of the fix conditions:
    the hypothesis demands fewer literals and covers more than the fix.
    """
    if specific == conditions:
        return "match"
    if specific < conditions:
        return "too_wide"
    if specific > conditions:
        return "too_narrow"
    return "mixed"


def load_fix_conditions(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Fix-condition rows. The default file ships with this package.

    Every condition must be a feature of the default vocabulary. A broken file
    raises ``ValueError``.
    """
    source = _DATA if path is None else Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("fix conditions: expected a JSON object")
    schema = payload.get("schema")
    if isinstance(schema, bool) or schema != 1:
        raise ValueError(f"fix conditions: schema must be 1, got {schema!r}")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("fix conditions: entries must be a list")
    registry = default_registry()
    found: list[dict[str, Any]] = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"fix conditions: entry {index} must be an object")
        missing = [field for field in _FIELDS if field not in entry]
        if missing:
            raise ValueError(f"fix conditions: entry {index} missing {missing}")
        for field in _TEXT:
            value = entry[field]
            if not isinstance(value, str) or value == "":
                raise ValueError(f"fix conditions: entry {index} {field} must be a non-empty string")
        conditions = entry["conditions"]
        if isinstance(conditions, str) or not isinstance(conditions, list) or not conditions:
            raise ValueError(f"fix conditions: entry {index} conditions must be a non-empty list")
        if not all(isinstance(item, str) and item for item in conditions):
            raise ValueError(f"fix conditions: entry {index} conditions must be non-empty strings")
        unknown = [item for item in conditions if not registry.known(item)]
        if unknown:
            raise ValueError(f"fix conditions: entry {index} unknown features {unknown}")
        found.append(
            {
                "name": entry["name"],
                "engine": entry["engine"],
                "key": entry["key"],
                "fix": entry["fix"],
                "evidence": entry["evidence"],
                "conditions": list(conditions),
            }
        )
    return found


def _specific(wb: Any, row: dict[str, Any]) -> set[str]:
    hypotheses = row.get("hypotheses")
    if wb is not None and hypotheses:
        return set(wb.theory.get(hypotheses[0]).specific)
    raw = row.get("specific")
    if raw is None:
        return set()
    return set(raw)


def compare(wb: Any, families: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per fix condition whose key equals a theory family's key.

    The family's key is the identity key used by ``dups.new_families``. The
    boundary is the ``specific`` of that family's first hypothesis. Conditions
    with no such family are left out.
    """
    by_key: dict[str, dict[str, Any]] = {}
    for row in families:
        if isinstance(row, dict) and isinstance(row.get("key"), str):
            by_key.setdefault(row["key"], row)
    found: list[dict[str, Any]] = []
    for entry in load_fix_conditions():
        row = by_key.get(entry["key"])
        if row is None:
            continue
        specific = _specific(wb, row)
        conditions = set(entry["conditions"])
        found.append(
            {
                "name": entry["name"],
                "family": row.get("family"),
                "classification": classify(specific, conditions),
                "missing": sorted(conditions - specific),
                "extra": sorted(specific - conditions),
            }
        )
    return found
