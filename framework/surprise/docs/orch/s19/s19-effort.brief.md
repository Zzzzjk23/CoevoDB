角色：执行者

# 工作包 s19-effort：glm-flash 档的推理强度改为 low

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s19-effort`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s19`（门槛 `framework/surprise/gates/s19_cases.py` 的 `NEW_PROFILE` 已经改成新值）
- 所属会话：S19；用户 2026-10-21 的决定，见 `framework/surprise/docs/PLAN.md` §9 最后一条与 `DECISIONS.md` 当天的条目

## 目标

编排者用真实调用测过：`glm-flash` 档开着默认推理（`"reasoning": {"enabled": true}`）时，implementer 与 conjecturer 两个角色把整个 `max_tokens` 都花在推理上，没有答案（`finish_reason: length`）；这个提供商不允许关推理（`enabled: false` 与 `effort: "none"` 都回 HTTP 400 "Reasoning is mandatory for this endpoint and cannot be disabled."）；`"reasoning": {"effort": "low"}` 时两个角色都在上限内给出了合法 JSON，推理量与以前的 deepseek-flash 相当。用户定下：与以前 DeepSeek 的做法对齐（开推理、各角色 `max_tokens` 不变），推理强度设为 low。

只改一处配置：`framework/surprise/roles/providers.py` 里 `EXTRA_TIERS["glm-flash"]["body"]["reasoning"]` 从 `{"enabled": True}` 改成 `{"effort": "low"}`，与 `framework/surprise/gates/s19_cases.py` 的 `NEW_PROFILE` 逐字相同。别的字段（`model`、`base_url`、`provider`）不动。

`framework/tests/test_surprise_s19_glm.py` 里写死的旧配置（第 28 行附近）跟着改成新值；其余断言不变。

## 允许改动的路径

```allow-paths
framework/surprise/roles/providers.py
framework/tests/test_surprise_s19_glm.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`；不改 `roles/constants.py`（各角色的 `max_tokens` 不变）、`roles/transport.py`、`roles/gateway.py`、`framework/surprise/harness/`、`experiments/`。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不改 conftest。上面那一处写死的旧配置是本包要改的，不算放宽。
- 不登录、不连接实验服务器；不做任何真实的 LLM 调用（没有给你密钥），测试一律离线。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支；不改 `HANDOFF.md`、`DECISIONS.md`。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器。shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接。

```powershell
cd framework
pytest -q testing tests                              # 1157 passed, 3 skipped 的基线上不减，skip 不增加
python -m surprise.gates.s19                         # S19 GATE: PASS (11/11)
python -m surprise.gates.s15 --only config llm prices   # PASS (3/3)
```

## 收尾

1. 把改动提交到当前分支；`git status` 应当是干净的。
2. 写 `.orch/report.md`（不入库），格式：改了哪些文件；跑了哪些命令（命令、退出码、输出末 20 行原样）；与说明的偏差（没有写"无"）；未决问题（没有写"无"）。
3. 说明有矛盾或做不完：写进报告，停下。
