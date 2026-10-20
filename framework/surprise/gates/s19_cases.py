"""Tables for gates/s19.py (S19: switch the LLM roles to GLM 5.3 Flash on OpenRouter)."""

from __future__ import annotations

BASE_TAG = "s15-done-r3"
DONE_TAG = "s19-done"

# ---- the new tier (user's decision, 2026-10-20) ---------------------------------------------------

NEW_TIER = "glm-flash"
NEW_MODEL = "z-ai/glm-5.3-flash"
# The profile the gateway and the run manifest record when the tier is used, verbatim.
NEW_PROFILE = {
    "model": NEW_MODEL,
    "base_url": "https://openrouter.ai/api/v1",
    "body": {
        "provider": {"only": ["open-inference/fp4"], "allow_fallbacks": False},
        "reasoning": {"enabled": True},
    },
}
NEW_URL = "https://openrouter.ai/api/v1/chat/completions"
OLD_URL = "https://api.deepseek.com/v1/chat/completions"
OLD_TIERS = {"fast": "deepseek-flash", "strong": "deepseek-v4-pro"}
# Keys of Gateway.manifest() without a tier override, as at the base tag.
OLD_MANIFEST_KEYS = {"tiers", "max_calls", "constants"}
# The key stays in this variable (user's decision); a different variable must not be read.
KEY_ENV = "DEEPSEEK_API_KEY"
DECOY_ENV = "OPENROUTER_API_KEY"
CAP_ENV = "SURPRISE_LLM_MAX_CALLS"

# ---- prices: OpenRouter endpoint list for z-ai/glm-5.3-flash, read 2026-10-20 --------------------
# https://openrouter.ai/api/v1/models/z-ai/glm-5.3-flash/endpoints, provider tag open-inference/fp4:
# prompt 0.000000037476, completion 0.00000016, input_cache_read 0.000000006 USD per token.

PRICES_FILE = "framework/surprise/metrics/data/prices_openrouter.json"
PRICES = {
    "retrieved": "2026-10-20",
    "source": "https://openrouter.ai/api/v1/models/z-ai/glm-5.3-flash/endpoints",
    "unit": "USD per 1M tokens",
    "models": {
        NEW_MODEL: {"provider": "open-inference/fp4", "input": 0.037476, "output": 0.16, "input_cache_read": 0.006},
    },
    "grid": {NEW_MODEL: {"input": 0.037476, "output": 0.16}},
}
OLD_PRICES_FILE = "framework/surprise/metrics/data/prices_deepseek.json"

# ---- scope ------------------------------------------------------------------------------------------

ALLOWED_CHANGES = (
    "framework/surprise/docs/",
    "framework/surprise/gates/s19.py",
    "framework/surprise/gates/s19_cases.py",
    # S8 long run re-pinned after experiments/ changed (the S8 acceptance procedure).
    "framework/surprise/gates/s08_runs.json",
    "framework/surprise/roles/gateway.py",
    "framework/surprise/roles/transport.py",
    "framework/surprise/roles/runtime.py",
    "framework/surprise/roles/providers.py",
    "framework/surprise/experiments/grid.py",
    "framework/surprise/experiments/loop.py",
    "framework/surprise/baselines/pure_llm.py",
    PRICES_FILE,
    "framework/tests/test_surprise_s19_",
    # alerts (user's request, 2026-10-21)
    "framework/surprise/notify/",
)
FROZEN_PATHS = (
    "framework/surprise/harness",
    "framework/surprise/roles/constants.py",
    OLD_PRICES_FILE,
    "framework/agents",
    "framework/llm",
    "framework/oracles",
    "framework/targets",
)

# ---- alerts through pushplus (user's request, 2026-10-21) -------------------------------------------
# "添加额度不足、报错等的提醒：使用pushplus的一对一消息功能". The token lives in PUSH_ENV only.

PUSH_ENV = "PUSHPLUS_TOKEN"
PUSH_URL = "https://www.pushplus.plus/send"
# One-to-one message: no topic, no friend list; plain text.
PUSH_BODY_KEYS = {"token", "title", "content", "template"}
PUSH_TEMPLATE = "txt"
# pushplus codes after which the account cannot send (900 too many requests, 905 not verified,
# 888 no points): the sender stops for the rest of the process.
PUSH_STOP_CODES = (900, 905, 888)
KEY_INFO_URL = "https://openrouter.ai/api/v1/key"
# Gateway reason of a failed call -> the cause the watcher reports.
CAUSES = {
    "TransportError: HTTPStatusError 402": "credit",
    "TransportError: HTTPStatusError 401": "auth",
    "TransportError: HTTPStatusError 403": "auth",
    "TransportError: HTTPStatusError 429": "rate",
    "TransportError: DeadlineExceeded": "timeout",
    "TransportError: DEEPSEEK_API_KEY is not set": "nokey",
    "TransportError: HTTPStatusError 500": "other",
    "TransportError: ConnectError": "other",
    "TransportError": "other",
    "RuntimeError": "other",
    None: "other",
}
KINDS = ("start", "llm_errors", "llm_blocked", "cell_failed", "stall", "balance", "finished", "exited")
