"""Parse a role's reply into JSON and require the prediction field."""

from __future__ import annotations

import json

from .constants import REQUIRED_FIELD


def parse_reply(text: str) -> tuple[dict | None, str | None]:
    """Return ``(data, None)`` or ``(None, reason)`` for a model's reply text."""
    raw = text.strip()
    if raw.startswith("```"):
        newline = raw.find("\n")
        raw = "" if newline == -1 else raw[newline + 1 :]
        raw = raw.rstrip()
        if raw.endswith("```"):
            raw = raw[: -3].rstrip()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end < start:
            return None, "no_json"
        try:
            data = json.loads(raw[start : end + 1])
        except (json.JSONDecodeError, TypeError, ValueError):
            return None, "no_json"
    if not isinstance(data, dict):
        return None, "not_object"
    if REQUIRED_FIELD not in data:
        return None, "no_prediction"
    value = data[REQUIRED_FIELD]
    if value is None or value == "" or value == [] or value == {}:
        return None, "no_prediction"
    return data, None
