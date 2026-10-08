"""Frozen numeric constants for the harness.

Later sessions record :func:`as_dict` in the run manifest. Add a new constant
by defining an uppercase name in this module; do not edit :func:`as_dict`.
"""

from __future__ import annotations

import json
from typing import Any

# Wall-clock timeout, in seconds, for one statement. Same default as the old oracles.
QUERY_TIMEOUT_S = 10.0

# Default-setting reruns of one fail candidate. Every one of them runs.
CVE_RERUN_ATTEMPTS = 5

# Extra default-setting reruns when the candidate disappears on one thread.
CVE_RERUN_EXTENDED = 15

# Wall-clock limit, in seconds, for one isolated judgement or one isolated execution.
CVE_WALL_TIMEOUT_S = 120.0

# Reproduction checks while dropping unused setup statements after the old minimiser.
# The old ``_minimize`` keeps its own cap; this one bounds only the extra pass.
CVE_MINIMIZE_MAX_EXECUTIONS = 30

# Execution cap passed to ``diagnosis.bisect.compute_fix_set``.
CVE_BISECT_MAX_EXECUTIONS = 120

# Wall-clock limit, in seconds, for one tier-2 attribution subprocess.
CVE_ATTRIBUTION_WALL_TIMEOUT_S = 120.0

# Wall-clock limit, in seconds, for the tier-3 minimisation and profile subprocess.
CVE_PROFILE_WALL_TIMEOUT_S = 600.0


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
        raise TypeError(f"harness constants are not JSON-safe: {exc}") from exc
    loaded = json.loads(blob)
    if not isinstance(loaded, dict):
        raise TypeError("harness constants did not serialise to a JSON object")
    return loaded
