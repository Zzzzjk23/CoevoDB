"""Numeric constants for the theory. The harness constants stay frozen."""

from __future__ import annotations

import json
from typing import Any

# P(fail | valid) when an example lies inside some hypothesis's S.
P_CONFIRMED = 0.95

# P(fail | valid) when an example lies between S and G.
P_PENDING = 0.5

# Numerator prior of the residual failure rate rho = (unexplained + 1.0) / (tested + 100.0).
RESIDUAL_PRIOR_FAILS = 1.0

# Denominator prior of the residual failure rate.
RESIDUAL_PRIOR_TESTS = 100.0

# Numerator prior of the invalid rate K^v = (invalid + 1.0) / (tested + 10.0).
VALIDITY_PRIOR_INVALID = 1.0

# Denominator prior of the invalid rate.
VALIDITY_PRIOR_TESTS = 10.0

# Surprise below this, in bits, is a duplicate or carries no information.
TRIAGE_LOW_BITS = 0.5

# Surprise at or above this, in bits, is a new family or an unexpected pass.
TRIAGE_HIGH_BITS = 2.0

# Maximum number of conjunctions kept in G.
VS_MAX_GENERAL = 64

# Fixed cost, in bits, of holding one more hypothesis in the theory.
MDL_HYPOTHESIS_BITS = 8.0

# Cost, in bits, of one literal of S: about log2 of the size of the vocabulary.
MDL_LITERAL_BITS = 7.4

# Largest number of held-out records one acceptance test reads.
ACCEPT_HOLDOUT_MAX = 1000

# A change in surprise smaller than this, in bits, counts as no change.
ACCEPT_TOLERANCE_BITS = 1e-9

# Weight of the residual uncertainty U against the version-space disagreement D in the Hunter's value.
# Provisional; S8 fixes it once with a pre-experiment on independent seeds (PLAN decision 8).
BETA = 1.0


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
        raise TypeError(f"theory constants are not JSON-safe: {exc}") from exc
    loaded = json.loads(blob)
    if not isinstance(loaded, dict):
        raise TypeError("theory constants did not serialise to a JSON object")
    return loaded
