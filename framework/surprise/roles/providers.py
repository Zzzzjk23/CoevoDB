"""Extra endpoints, kept outside the frozen role constants."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

EXTRA_TIERS = {
    "glm-flash": {
        "model": "z-ai/glm-5.3-flash",
        "base_url": "https://openrouter.ai/api/v1",
        "body": {
            "provider": {"only": ["open-inference/fp4"], "allow_fallbacks": False},
            "reasoning": {"enabled": True},
        },
    },
}


def endpoint_for_tier(tier: str | None) -> dict[str, Any] | None:
    """Return an independent profile for a configured extra tier."""
    return deepcopy(EXTRA_TIERS.get(tier))


def endpoint_for_model(model: str) -> dict[str, Any] | None:
    """Return the extra endpoint for a model, or keep the default endpoint."""
    for profile in EXTRA_TIERS.values():
        if profile["model"] == model:
            return deepcopy(profile)
    return None
