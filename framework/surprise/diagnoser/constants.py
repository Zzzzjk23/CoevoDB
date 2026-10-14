"""Numeric constants for the Diagnoser. The theory constants stay in theory.constants."""

from __future__ import annotations

import json
from typing import Any

COMPRESS_EVERY = 100     # run the MDL compress() after every this many experiments
CHECKPOINT_EVERY = 100   # close a generation after every this many experiments


def as_dict() -> dict[str, Any]:
    """Every public uppercase constant in this module, as a detached JSON object."""
    raw = {
        name: value
        for name, value in globals().items()
        if name.isupper() and not name.startswith("_")
    }
    try:
        blob = json.dumps(raw, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"diagnoser constants are not JSON-safe: {exc}") from exc
    loaded = json.loads(blob)
    if not isinstance(loaded, dict):
        raise TypeError("diagnoser constants did not serialise to a JSON object")
    return loaded
