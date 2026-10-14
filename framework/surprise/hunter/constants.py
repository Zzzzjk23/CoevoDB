"""Numeric constants for the Hunter. The theory constants stay in theory.constants."""

from __future__ import annotations

import json
from typing import Any

# seeds sampled per engine per step for the explore lane
EXPLORE_SEEDS_PER_STEP = 6

# SeedMutator mutations per sampled seed
SEED_MUTATIONS_PER_SEED = 1

# most recent positives of a hypothesis used as parents
PARENTS_PER_HYPOTHESIS = 3

# mutants examined per step, shared out over hypotheses
MUTANTS_PER_STEP = 48

# migrate candidates kept per step
MIGRATE_PER_STEP = 8

# every fifth choice is an exploration slot
EXPLORE_EVERY = 5

# downweight 1 / (1 + probes / PROBE_HALF)
PROBE_HALF = 50.0

# recent experiments of the same scope a candidate is compared with
NOVELTY_WINDOW = 200

# acceptance probability of a candidate with zero novelty
NOVELTY_FLOOR = 0.2

# optimistic rate multiplier for a unit next to a known hypothesis
ADJACENT_FACTOR = 2.0

# wall-clock limit of one phi extraction in the worker process
PHI_TIMEOUT_S = 30.0


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
        raise TypeError(f"hunter constants are not JSON-safe: {exc}") from exc
    loaded = json.loads(blob)
    if not isinstance(loaded, dict):
        raise TypeError("hunter constants did not serialise to a JSON object")
    return loaded
