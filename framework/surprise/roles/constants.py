"""Numeric and string constants for the LLM gateway and the roles that use it."""

from __future__ import annotations

import json
from typing import Any

# Mapping from a gateway tier name to the DeepSeek model that tier uses.
TIERS = {"fast": "deepseek-flash", "strong": "deepseek-v4-pro"}

# Network calls one gateway (one run) may make when no constructor cap is given.
DEFAULT_MAX_CALLS = 200

# If set to an integer, an environment ceiling that lowers every gateway's cap.
CAP_ENV = "SURPRISE_LLM_MAX_CALLS"

# Every role's reply must carry this field, and it must be non-empty.
REQUIRED_FIELD = "prediction"

# Parent directory of the pinned engine source checkouts, when not using git.
SOURCE_ROOT_ENV = "SURPRISE_SOURCE_ROOT"

# Directory name of each engine's source checkout under the source root.
SOURCE_DIRS = {"duckdb": "duckdb-v1.5.5", "datafusion": "datafusion-54.0.0"}

# Commit each engine checkout must be at when open_sources verifies.
SOURCE_COMMITS = {
    "duckdb": "d8cdaa33fda8df955cc76ef58a280f68f4cd43fa",
    "datafusion": "45d943dfb8699dc9cb9ef2320e955b73e3e6c03b",
}

# Largest regular file the source reader will open, in bytes.
SOURCE_MAX_FILE_BYTES = 2_000_000

# Model tier the implementer uses for every call.
IMPLEMENTER_TIER = "fast"

# Sampling temperature of the implementer.
IMPLEMENTER_TEMPERATURE = 0.2

# Maximum tokens the implementer asks the model for.
IMPLEMENTER_MAX_TOKENS = 2000

# Times the implementer may call the gateway for one spec.
IMPLEMENTER_ATTEMPTS = 2

# New targets the implementer source may implement per Hunter choice.
IMPLEMENTER_PER_CHOICE = 1

# Model tier the conjecturer uses for every call.
CONJECTURER_TIER = "fast"

# Sampling temperature of the conjecturer.
CONJECTURER_TEMPERATURE = 0.6

# Maximum tokens the conjecturer asks the model for.
CONJECTURER_MAX_TOKENS = 8000

# Predictions the conjecturer may keep from one reply.
CONJECTURER_MAX_PREDICTIONS = 5

# Source files the conjecturer may attach to one prompt.
SOURCE_MAX_FILES = 4

# Source lines the conjecturer may attach to one prompt.
SOURCE_MAX_LINES = 400


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
        raise TypeError(f"roles constants are not JSON-safe: {exc}") from exc
    loaded = json.loads(blob)
    if not isinstance(loaded, dict):
        raise TypeError("roles constants did not serialise to a JSON object")
    return loaded
