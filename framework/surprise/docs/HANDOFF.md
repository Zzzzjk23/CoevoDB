# HANDOFF

## 状态总览

| 会话 | 内容 | 状态 | tag | 门槛 |
|---|---|---|---|---|
| S1 | Phase 0 冻结基线与仓库整理 | 未开始 | | |
| S2 | Phase 1a 契约、账本、三类健全 oracle | 未开始 | | |
| S3 | Phase 1b 其余三类 oracle | 未开始 | | |
| S4 | Phase 1c CVE 流水线（M1） | 未开始 | | |
| S5 | Phase 2 φ | 未开始 | | |
| S6 | Phase 3a 理论 T 核心 | 未开始 | | |
| S7 | Phase 3b 理论存储与接受规则 | 未开始 | | |
| S8 | Phase 4 Hunter 与无 LLM 闭环（M2） | 未开始 | | |
| S9 | Phase 5a LLM 网关、实现器、猜想者 | 未开始 | | |
| S10 | Phase 5b 其余四个 LLM 角色（M3） | 未开始 | | |
| S11 | Phase 6 评估管线（M4 冒烟） | 未开始 | | |
| S12 | Phase 7 收尾 | 未开始 | | |

## 最近一次会话：规划会话（2026-10-08）

### 完成了什么
- 定下总规划 `PLAN.md`、会话划分 `SESSIONS.md`、本文件、`DECISIONS.md`，以及仓库根的 `CLAUDE.md`。
- 没有改动任何代码。

### 新增或改动的接口
- 无。

### 与 PLAN 的偏差及原因
- 无。

### 未决问题（S1 需要知道的）
- `.gitignore` 没有忽略 `.venv/`、`.uv-cache/` 和根目录 `results/`（只忽略了 `framework/results/`）。`git add` 之前先补上。`.env` 已被忽略。
- `framework/test_api.py` 在设置了 `DEEPSEEK_API_KEY` 时会真的调用 API；日常测试命令只跑 `testing/` 和 `tests/`。
- `coevo/` 被 `tests/test_verified_loop.py` 依赖，S1 不归档。
- `framework/config.yml` 里 `database.version` 写的是 1.5.2，实际目标是 1.5.5；`database.old_venv` 是旧机器上的路径，以环境变量 `COEVO_OLD_VENV` 为准。
- PG 专项脚本靠 `sys.path` 的相对位置找框架代码，移动时保持目录深度（见 SESSIONS.md 的 S1）。
- 规划会话只读过源码，没能在本机执行命令；以上问题都没有经过实际运行验证。
- PLAN.md 决策表第 2、4–10 条仍是建议，到对应会话开工时再定。

### 下一会话的起点
- S1：先确认 git 状态，记录测试基线，打 `v1-baseline`，再做整理。
