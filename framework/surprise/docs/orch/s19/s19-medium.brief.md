角色：执行者

# 工作包 s19-medium：glm-flash 档的推理强度改为 medium

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s19-medium`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s19`（门槛 `framework/surprise/gates/s19_cases.py` 的 `NEW_PROFILE` 已经改成新值）
- 所属会话：S19；用户 2026-10-21 的决定（"改成medium"），见 `framework/surprise/docs/PLAN.md` §9 最后一条与 `DECISIONS.md` 当天的条目

## 目标

服务商换成 sail-research/fp4 之后，`"reasoning": {"effort": "low"}` 下模型几乎不推理。用户定为 medium。

只改一处配置：`framework/surprise/roles/providers.py` 里 `EXTRA_TIERS["glm-flash"]["body"]["reasoning"]` 从 `{"effort": "low"}` 改成 `{"effort": "medium"}`，与 `framework/surprise/gates/s19_cases.py` 的 `NEW_PROFILE` 逐字相同。别的字段（`model`、`base_url`、`providers`）不动。

S19 的测试里写死了旧值的几处跟着改成新值，其余断言不变：
- `framework/tests/test_surprise_s19_glm.py`（`PROFILE` 里的 `reasoning`）
- `framework/tests/test_surprise_s19_providers.py`（`"reasoning": {"effort": "low"}` 的几处）
- `framework/tests/test_surprise_s19_retry.py`（`expected.update(reasoning=...)` 一处）

## 允许改动的路径

```allow-paths
framework/surprise/roles/providers.py
framework/tests/test_surprise_s19_glm.py
framework/tests/test_surprise_s19_providers.py
framework/tests/test_surprise_s19_retry.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`；不改 `roles/constants.py`、`roles/transport.py`、`roles/gateway.py`、`framework/surprise/harness/`、`experiments/`、`notify/`。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不改 conftest。上面列出的、写死旧值的那几处是本包要改的，不算放宽。
- 不登录、不连接实验服务器；不做任何真实的 LLM 调用（没有给你密钥），测试一律离线。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支；不改 `HANDOFF.md`、`DECISIONS.md`。

## 验收命令

在 worktree 里执行，全部通过才算完成。shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接。用 `python -m pytest`（沙箱里直接运行 `pytest` 启动器找不到项目包）。

```powershell
cd framework
python -m pytest -q testing tests                    # 1205 passed, 3 skipped 的基线上不减，skip 不增加
python -m surprise.gates.s19                         # S19 GATE: PASS (12/12)
python -m surprise.gates.s15 --only config llm prices   # PASS (3/3)
```

（`gates.s19` 的 `balance` 组会往终端打几行乱码的看守日志，属正常。）

## 收尾

1. 把改动提交到当前分支；`git status` 应当是干净的。
2. 写 `.orch/report.md`（不入库），格式：改了哪些文件；跑了哪些命令（命令、退出码、输出末 20 行原样）；与说明的偏差（没有写"无"）；未决问题（没有写"无"）。
3. 说明有矛盾或做不完：写进报告，停下。
