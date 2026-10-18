"""Tables for ``gates/s14.py`` (server deployment and the two-platform gate).

The expected environment itself is not here: it is the JSON block at the end of
``SERVER.md``, so the document and the gate cannot drift apart.
"""
from __future__ import annotations

SERVER = "framework/surprise/docs/SERVER.md"
HANDOFF = "framework/surprise/docs/HANDOFF.md"
SMOKE_CONFIG = "framework/surprise/docs/grids/s14_smoke.json"
EVIDENCE = "framework/surprise/gates/s14_evidence"
FROZEN_MANIFEST = "framework/surprise/gates/s04_frozen.json"

SPEC_HEADING = "## 7. 机读清单"
SECTIONS = (
    "## 1. 主机与布局",
    "## 2. 环境版本",
    "## 3. 部署新代码（编排者）",
    "## 4. 重建步骤",
    "## 5. 运行手册（用户）",
    "### 5.1 开跑前检查",
    "### 5.2 在 tmux 里启动网格",
    "### 5.3 查看状态",
    "### 5.4 生成报告",
    "### 5.5 压缩并拷回",
    "### 5.6 S14 冒烟",
    "## 6. 平台差异",
    "## 7. 机读清单",
)
# Every ``$PY -m <module> <subcommand>`` the runbook uses must exist with that subcommand.
RUNBOOK_COMMANDS = {
    "surprise.experiments.grid": ("run", "status"),
    "surprise.metrics.report": (),
}

BASE_TAG = "s13-done-r2"
DONE_TAG = "s14-done"
# Paths S14 may change. Code fixes for Linux come from grok packages and are listed by file.
ALLOWED_CHANGES = (
    "framework/surprise/docs/",
    "framework/surprise/gates/s14.py",
    "framework/surprise/gates/s14_cases.py",
    "framework/surprise/gates/s14_evidence/",
    "framework/surprise/gates/s03.py",
    # s14-posix-die: die() exits with the given code on POSIX too.
    "framework/tests/test_surprise_s04_runners.py",
)
# S14 does not touch the frozen harness (SESSIONS: no harness changes).
FROZEN_PATHS = ("framework/surprise/harness/", FROZEN_MANIFEST)
# Changes to these never make a Linux record stale: they are not code.
NOT_CODE = ("framework/surprise/docs/", EVIDENCE + "/", "CLAUDE.md")

# Windows at s13-done-r2: 935 passed, 3 skipped. Linux may not skip more.
SKIP_MAX = 3
PYTEST_ARGS = ("-m", "pytest", "-q", "testing", "tests")
PG_DSN = "host=127.0.0.1 port=55432 user=coevo dbname=postgres connect_timeout=5"
PG_SETTINGS = ("server_version_num", "server_encoding", "TimeZone", "DateStyle",
               "default_text_search_config", "lc_messages", "lc_monetary", "lc_numeric", "lc_time")
OLD_CODE_DEFAULT_ROOT = "/home/user/"

# The smoke grid (SERVER.md 5.6).
SMOKE_CELLS = ("nollm/s7-r0",)
SMOKE_MIN_WALL_S = 55.0
SMOKE_MAX_WALL_S = 900.0
