"""Tables for the S13 gate (the formal experiment protocol).

S13 writes documents only: ``framework/surprise/docs/EXPERIMENT.md`` (the protocol, with a
machine-readable spec at its end), ``PLAN.md`` section 9, the S13-S25 sections of
``SESSIONS.md``, ``HANDOFF.md`` and ``DECISIONS.md`` (user decisions of 2026-10-19).
"""
from __future__ import annotations

BASE_TAG = "s12-done-r2"
# Once S13 is tagged, the scope check compares the base with this tag instead of the work tree.
DONE_TAG = "s13-done"

DOCS = "framework/surprise/docs"
EXPERIMENT = f"{DOCS}/EXPERIMENT.md"
SESSIONS = f"{DOCS}/SESSIONS.md"
PLAN = f"{DOCS}/PLAN.md"
HANDOFF = f"{DOCS}/HANDOFF.md"

# S13 may change only these (prefixes end with "/").
ALLOWED_CHANGES = (
    f"{DOCS}/",
    "framework/surprise/gates/s13.py",
    "framework/surprise/gates/s13_cases.py",
)

# Headings of EXPERIMENT.md, in this order.
SECTIONS = (
    "## 1. 范围",
    "## 2. 被测引擎与版本",
    "## 3. 臂",
    "### 3.1 主臂与对照组",
    "### 3.2 消融",
    "## 4. 时长、种子与统计",
    "## 5. 调度与资源",
    "## 6. 里程碑与顺序",
    "## 7. 服务器分工",
    "## 8. 执行规则",
    "## 9. 机读清单",
)
SPEC_HEADING = "## 9. 机读清单"

# Keys of a spec arm that are not grid config keys.
META_KEYS = frozenset({"kind", "needs", "pairs", "hours"})
# Allowed keys inside an arm's "llm" object, per kind (as grid.py validates them).
LLM_KEYS = {
    "surprise": frozenset({"roles", "cache", "max_calls", "offline"}),
    "pure_llm": frozenset({"cache", "max_calls", "offline"}),
}
UNLIMITED = "unlimited"
# Kinds that run on exactly one engine per cell.
SINGLE_ENGINE_KINDS = frozenset({"pure_llm", "sqlancer"})

# The ablation table: A6-A10 each drop exactly one of these roles from `full`; A13 drops translator.
LEAVE_ONE_OUT = {"A6": "implementer", "A7": "conjecturer", "A8": "prior",
                 "A9": "vocab_inventor", "A10": "oracle_inventor"}
NO_TRANSLATOR = "A13"
MULTI_ENGINE_FULL = "A12"

FIRST_SESSION, LAST_SESSION = 13, 25
PLAN_SECTION = "## 9. 正式实验的决定"
HANDOFF_ROW = "| S13 |"

# Where seeds used before S13 are looked up (at BASE_TAG).
SEED_SCAN_PATHS = ("framework/surprise/gates", "framework/tests", "framework/testing")
SEED_WINDOW = 40  # characters after the word "seed" whose integers count as used seeds
