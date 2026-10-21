"""Tables for gates/s19.py (S19: switch the LLM roles to GLM 5.3 Flash on OpenRouter)."""

from __future__ import annotations

BASE_TAG = "s15-done-r3"
DONE_TAG = "s19-done"

# ---- the new tier (user's decision, 2026-10-20) ---------------------------------------------------

NEW_TIER = "glm-flash"
NEW_MODEL = "z-ai/glm-5.3-flash"
# The profile the gateway and the run manifest record when the tier is used, verbatim.
# 2026-10-21 (user): providers tried in this order, one per request ("provider": {"only": [p],
# "allow_fallbacks": false}); the next one only after the retries on the current one are used up.
# All three serve fp4. Replaces open-inference/fp4 alone, which answered HTTP 503 in bursts.
NEW_PROVIDERS = ["sail-research/fp4", "open-inference/fp4", "sail-research/us"]
NEW_PROFILE = {
    "model": NEW_MODEL,
    "base_url": "https://openrouter.ai/api/v1",
    "providers": NEW_PROVIDERS,
    "body": {
        # 2026-10-21 (user): reasoning effort low, aligned with deepseek-flash, which reasons by default.
        # The endpoint refuses to disable reasoning (enabled false / effort none: HTTP 400); with the
        # default effort the implementer and conjecturer spent all of max_tokens on reasoning (that was
        # open-inference/fp4). Later the same day, after sail-research/fp4 reasoned 1-269 tokens at low,
        # the user chose medium ("改成medium"). The model supports only low, high and max (OpenRouter
        # /api/v1/models; default max, mandatory), so medium acted as low. 2026-10-22: max, the only
        # level whose reasoning on sail-research/fp4 came near deepseek-flash's ("用max挡").
        "reasoning": {"effort": "max"},
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

# ---- prices: OpenRouter endpoint list for z-ai/glm-5.3-flash, read 2026-10-21 --------------------
# https://openrouter.ai/api/v1/models/z-ai/glm-5.3-flash/endpoints, USD per token:
#   sail-research/fp4  prompt 0.00000009     completion 0.00000015  input_cache_read 0.0000000261
#   open-inference/fp4 prompt 0.000000041191 completion 0.00000012  input_cache_read 0.00000000375
#   sail-research/us   prompt 0.00000009     completion 0.00000015  input_cache_read 0.0000000261
# The grid prices every call at the first provider's rate; the others cost the same or less.

PRICES_FILE = "framework/surprise/metrics/data/prices_openrouter.json"
PRICES = {
    "retrieved": "2026-10-21",
    "source": "https://openrouter.ai/api/v1/models/z-ai/glm-5.3-flash/endpoints",
    "unit": "USD per 1M tokens",
    "models": {
        NEW_MODEL: {
            "providers": {
                "sail-research/fp4": {"input": 0.09, "output": 0.15, "input_cache_read": 0.0261},
                "open-inference/fp4": {"input": 0.041191, "output": 0.12, "input_cache_read": 0.00375},
                "sail-research/us": {"input": 0.09, "output": 0.15, "input_cache_read": 0.0261},
            },
        },
    },
    "grid": {NEW_MODEL: {"input": 0.09, "output": 0.15}},
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
    # keys stored on the server (user's instruction, 2026-10-21): the rule in both files changed
    "CLAUDE.md",
    "framework/AGENTS.md",
    # 429 retry (user's decision, 2026-10-21): one constant added; group `retry` checks that every
    # constant of the base tag keeps its value
    "framework/surprise/roles/constants.py",
    # READMEs rewritten for the teammate handoff (user's decision, 2026-10-22): the two docs only
    "README.md",
    "framework/README.md",
)
# Sessions built on session/s19 before S19 ends (S16, PostgreSQL target, user's decision 2026-10-22): the
# paths their case tables list (ALLOWED_CHANGES, and HARNESS_CHANGED for the unfreeze) are checked by
# their own gates' scope groups and are left out of this one.
LATER_CASES = ("s16_cases",)
FROZEN_PATHS = (
    "framework/surprise/harness",
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

# ---- 429 and 503 retried with backoff, then the next provider (user's decisions, 2026-10-21:
# "同意，改成429退避重试"; "1. 添加退避重试 2. 服务商由open-inference/fp4更换为为sail-research/fp4
# 3. 若退避重试仍然不行可以更换别的服务商，优先尝试open-inference/fp4和sail-research/us", then
# "每次调用自动切换") ----------------------------------------------------------------------------------
# The transport waits and retries when the answer is HTTP 429 or 503, and only then; every other
# failure is still one attempt and never switches provider. When a provider's waits are used up, the
# next provider of the profile is tried at once with the same waits; every call starts with the first.
# It all happens inside one gateway call: the cap, calls.jsonl and the gateway's totals see one call.
# Each attempt keeps its own request deadline.

CONSTANTS_FILE = "framework/surprise/roles/constants.py"
RETRY_CONSTANT = "RATE_LIMIT_WAITS_S"
# Seconds to wait before retry 1, 2, ... on one provider; four retries, five attempts, 220 s at most.
RETRY_WAITS_S = [10.0, 30.0, 60.0, 120.0]
RETRY_STATUSES_CONSTANT = "RETRY_STATUSES"
RETRY_STATUSES = [429, 503]
# Written to stderr (the cell log); ASCII, never the key or the response body. RETRY_LINE before each
# wait on an endpoint without providers (DeepSeek), RETRY_LINE_VIA on a provider, SWITCH_LINE when a
# provider's waits are used up and the next one is tried.
RETRY_LINE = "surprise.roles.transport: HTTP {status} for role {role}, model {model}; retry {attempt}/{retries} in {wait:g} s"
RETRY_LINE_VIA = ("surprise.roles.transport: HTTP {status} for role {role}, model {model} via {provider}; "
                  "retry {attempt}/{retries} in {wait:g} s")
SWITCH_LINE = ("surprise.roles.transport: HTTP {status} for role {role}, model {model} via {provider}; "
               "retries used up, switching to {next}")
# Answers that are neither retried nor switched.
NO_RETRY_STATUSES = (400, 401, 402, 403, 404, 500, 502)
