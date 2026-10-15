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
IMPLEMENTER_MAX_TOKENS = 8000

# Times the implementer may call the gateway for one spec.
IMPLEMENTER_ATTEMPTS = 2

# New targets the implementer source may implement per Hunter choice.
IMPLEMENTER_PER_CHOICE = 1

# Model tier the conjecturer uses for every call.
CONJECTURER_TIER = "fast"

# Sampling temperature of the conjecturer.
CONJECTURER_TEMPERATURE = 0.6

# Maximum tokens the conjecturer asks the model for.
CONJECTURER_MAX_TOKENS = 16000

# Predictions the conjecturer may keep from one reply.
CONJECTURER_MAX_PREDICTIONS = 5

# Source files the conjecturer may attach to one prompt.
SOURCE_MAX_FILES = 4

# Source lines the conjecturer may attach to one prompt.
SOURCE_MAX_LINES = 400

# Environment variable naming the oracle inventor's rewrite library file.
REWRITE_LIBRARY_ENV = "SURPRISE_REWRITE_LIBRARY"

# Model tier the exploration prior uses for every call.
PRIOR_TIER = "fast"

# Sampling temperature of the exploration prior.
PRIOR_TEMPERATURE = 0.2

# Maximum tokens the exploration prior asks the model for.
PRIOR_MAX_TOKENS = 8000

# Units the prior prices in one call.
PRIOR_UNITS_PER_CALL = 16

# Calls the prior may make for one Hunter choice.
PRIOR_CALLS_PER_CHOICE = 1

# Pseudo-count strength of a priced unit.
PRIOR_STRENGTH = 100.0

# Weight of the model's price before any calibration.
PRIOR_INITIAL_WEIGHT = 0.5

# Settled experiments required before the prior's weight moves.
PRIOR_MIN_SETTLED = 20

# Evidence lines the prior attaches per construct.
PRIOR_EVIDENCE_PER_CONSTRUCT = 4

# Model tier the migration translator uses for every call.
TRANSLATOR_TIER = "fast"

# Sampling temperature of the migration translator.
TRANSLATOR_TEMPERATURE = 0.2

# Maximum tokens the migration translator asks the model for.
# deepseek-flash counts reasoning tokens inside max_tokens, so 8000 truncated replies before JSON.
TRANSLATOR_MAX_TOKENS = 16000

# Times the translator may call the gateway for one family and engine.
TRANSLATOR_ATTEMPTS = 2

# Translations the translator source may offer per Hunter choice.
TRANSLATOR_PER_CHOICE = 1

# Model tier the vocabulary inventor uses for every call.
VOCAB_TIER = "fast"

# Sampling temperature of the vocabulary inventor.
VOCAB_TEMPERATURE = 0.4

# Maximum tokens the vocabulary inventor asks the model for.
# deepseek-flash counts reasoning tokens inside max_tokens, so 8000 truncated replies before JSON.
VOCAB_MAX_TOKENS = 16000

# Unexpected passes in the confirmed zone that wake the inventor.
VOCAB_TRIGGER_CONTRADICTIONS = 2

# Positive records required before the inventor proposes a feature.
VOCAB_MIN_POSITIVES = 2

# Held-out fraction: the last ceil(n / divisor) of each kind stay hidden.
VOCAB_HOLDOUT_DIVISOR = 3

# Proposals the inventor may make for one family.
VOCAB_ATTEMPTS_PER_FAMILY = 1

# Longest pattern the inventor may accept, in characters.
VOCAB_MAX_PATTERN_CHARS = 200

# Largest share of the seed corpus a pattern may match.
VOCAB_MAX_CORPUS_SHARE = 0.5

# Wall-clock budget of the corpus scan, in seconds.
VOCAB_SCAN_TIMEOUT_S = 20.0

# Model tier the oracle inventor uses for every call.
ORACLE_TIER = "fast"

# Sampling temperature of the oracle inventor.
ORACLE_TEMPERATURE = 0.6

# Maximum tokens the oracle inventor asks the model for.
# deepseek-flash counts reasoning tokens inside max_tokens, so 8000 truncated replies before JSON.
ORACLE_MAX_TOKENS = 16000

# Experiments between oracle-inventor calls.
ORACLE_EVERY = 100

# Calls the oracle inventor may make in one run.
ORACLE_CALLS_PER_RUN = 3

# Rewrite templates the oracle inventor may propose in one call.
ORACLE_RULES_PER_CALL = 3

# Engines that may accept an invented rewrite.
ORACLE_ACCEPT_ENGINES = ["duckdb", "datafusion", "sqlite", "postgres"]

# Agreeing engines required before an invented rewrite is accepted.
ORACLE_ACCEPT_MIN_ENGINES = 3

# Corpus instances an invented rewrite must pass.
ORACLE_ACCEPT_INSTANCES = 5

# Statements the oracle inventor may scan for those instances.
ORACLE_SCAN_MAX = 200

# Total time from sending the request to finishing the reply, covering keep-alive while queued.
REQUEST_DEADLINE_S = 600.0


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
