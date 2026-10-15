# 审查包 · s11-purellm

- 生成时间：2026-10-16T04:47:45+11:00
- 基线：`session/s11`（8d9781a47c60）
- 分支：`grok/s11-purellm` @ 92bec5ba0579，基线之上 1 个提交
- 运行：共 1 轮（返工 0 轮），最近一轮退出码 0，用时 26m18s
- grok：grok 1.0.46 (2765805b9442)；会话 `b15404c7-1fdb-48b1-a8a8-6b2129b33101`

## 红旗汇总

- 本次审查包没有复跑测试（--skip-tests）
- 新增宽泛的异常捕获 4 处（确认没有吞掉失败）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s11..grok/s11-purellm
git diff -M --stat session/s11..grok/s11-purellm
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/baselines/pure_llm.py`、`framework/tests/test_surprise_s11_pure_llm.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| A | `framework/surprise/baselines/pure_llm.py` |  |
| A | `framework/tests/test_surprise_s11_pure_llm.py` |  |

提交：

- 92bec5b Junke: baselines(s11): pure-LLM control runs model SQL through the shared oracles

## 2. diff 统计

```text
 framework/surprise/baselines/pure_llm.py      | 727 ++++++++++++++++++++++++++
 framework/tests/test_surprise_s11_pure_llm.py | 451 ++++++++++++++++
 2 files changed, 1178 insertions(+)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

按 `--skip-tests` 跳过了 pytest 与门槛。

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- 无

### 4.4 新增的宽泛异常捕获

- `framework/surprise/baselines/pure_llm.py:286` `except Exception as exc:`
- `framework/surprise/baselines/pure_llm.py:293` `except Exception as exc:`
- `framework/surprise/baselines/pure_llm.py:600` `except Exception as exc:`
- `framework/surprise/baselines/pure_llm.py:719` `except Exception as exc:`

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s11-purellm.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 移动 `refs/heads/grok/s11-fixes` 8d9781a47c60 → 511da3151d1b
- 移动 `refs/heads/session/s11` 8d9781a47c60 → 7d5b2aab319f

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s11-purellm.jsonl`：3225 条事件（available_commands 68，end 1，orch.exit 1，orch.start 1，text 352，thought 2101，tool_call 118，tool_call_update 523，usage 60）；各轮合计 60 个模型回合，grok 上报花费 1.5493 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_update [in_progress]: .............. [100%] 14 passed in 13.75s
tool_update [completed]: exit: 0 .............. [100%] 14 passed in 13.75s EXIT:0
thought: 准备撰写报告，确保输出准确。 已确定报告结构为四个固定章节。将提及 git 提交 92bec5b，并完整粘贴 pytest 输出。开始撰写偏差说明。 已梳理出 5 项与说明的偏差： - `llm/pure_llm.jsonl` 不计入使运行停下的 `blocked` 或 `miss`，`pure_llm_script` 要求该文件恰好有三次有效回复；停下的…
tool_call write: {"file_path": "D:\\CoevoDB\\.worktrees\\s11-purellm\\.orch\\report.md", "content": "# 报告 · s11-purellm\n\n提交 `92bec5b`，分支 `grok/s11-purellm`。工作区干净。\n\n## 改了哪些文件\n- `framework/surp…
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "", "new_string": "# 报告 · s11-purellm\n\n提交 `92bec5b`，分支 `grok/s11-purellm`。工作区干净。\n\n## 改了哪些文件\n- `framework/surprise/bas…
tool_call run_terminal_command: {"command": "git status --short", "description": "Confirm report.md is untracked and ignored"}
tool_update [in_progress]: 
tool_update [completed]: exit: 0
thought: 工作包已完成。
text: 纯 LLM 对照组已经落在 `grok/s11-purellm` 的 `92bec5b`。模型按主题直接写 SQL，合格用例走同一套 oracle 和 CVE；模型的 `expect` 只记在记录里，标签仍只来自 harness。 - `python -m pytest -q testing tests`：788 passed，3 skipped，0 fa…
end: stopReason=end_turn turns=60 cost_usd=1.54933988
orch.exit: {"pkg": "s11-purellm", "run": 1, "at": "2026-10-16T04:47:37+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s11-purellm

提交 `92bec5b`，分支 `grok/s11-purellm`。工作区干净。

## 改了哪些文件
- `framework/surprise/baselines/pure_llm.py`：新增。纯 LLM 对照组，模型写 SQL，同一套 oracle 与 CVE 打标签。
- `framework/tests/test_surprise_s11_pure_llm.py`：新增。覆盖门槛 `pure_llm_script` 的要点，以及离线缓存缺失、`max_minutes`、用法错误。

## 跑了哪些命令

### `cd framework ; python -m pytest -q tests/test_surprise_s11_pure_llm.py --tb=line`
退出码 0。

```
..............                                                           [100%]
14 passed in 13.75s
EXIT:0
```

### `cd framework ; python -m pytest -q testing tests`
退出码 0。

```
........................ss..................................s........... [  9%]
........................................................................ [ 18%]
........................................................................ [ 27%]
........................................................................ [ 36%]
........................................................................ [ 45%]
........................................................................ [ 54%]
........................................................................ [ 63%]
........................................................................ [ 72%]
........................................................................ [ 81%]
........................................................................ [ 91%]
.......................................................................  [100%]
788 passed, 3 skipped in 192.76s (0:03:12)
```

### `cd framework ; python -m surprise.gates.s11 --only pure_llm_script`
退出码 0。

```
[PASS] pure_llm_script: 4 cases executed from 3 calls (1 reply rejected, 2 bad cases skipped); prompts deterministic; budget holds (5s)
S11 GATE [only: pure_llm_script]: PASS (1/1 groups passed)
```

### `cd framework ; python -m surprise.gates.s11 --only constants`
退出码 1。预期失败。失败行：

```
[FAIL] constants: ModuleNotFoundError: No module named 'surprise.metrics.constants'
S11 GATE [only: constants]: FAIL (0/1 groups passed)
```

### `cd framework ; python -m surprise.gates.s11 --only pure_llm`
退出码 1。预期失败。失败行：

```
[FAIL] pure_llm: gates/s11_llm/pure_llm is missing: the orchestrator records it with real calls after the merge
S11 GATE [only: pure_llm]: FAIL (0/1 groups passed)
```

## 与说明的偏差
- `llm/pure_llm.jsonl` 不记录使运行停下的那一次 `blocked` 或 `miss`。说明把这两种状态列进了该行的 `status`。门槛 `pure_llm_script` 要求这个文件的 status 恰好是 `ok`、`rejected`、`ok`。停下来的那一次在 `llm/calls.jsonl` 里，`report["status"]` 为 `llm_exhausted`，`report["calls"]` 把它算进去。影响：合并后若有人按说明去对 jsonl 的最后一行，会看不到这次拒绝；网关账本里有。
- 引擎名不是 `duckdb` 或 `datafusion` 时，`run` 在建目录之前抛 `UsageError`。harness 只有这两个目标引擎。影响：命令行传入别的名字得到退出码 2，而不是跑起来再失败。
- 命令行在运行中抛出异常时退出码 1，键盘中断时 130，与 `experiments/loop.py` 相同。说明只点名了正常 0 和用法错误 2。
- `status` 为 `error` 时，`report.json` 在说明列出的字段之外多一个 `error` 对象（`type`、`message`）。traceback 在 `error.txt`。
- `max_minutes` 用 `>=` 与已用墙钟比较，与 loop 相同。预算为 0 时在第一次模型调用之前停下。

## 未决问题
- `constants` 组在导入 `surprise.metrics.constants` 时就失败，没有执行到 `REQUEST_DEADLINE_S`。该名字目前也不在 `roles/constants.py` 里，属于并行的 `s11-fixes`。本包没有改这些文件。
- `pure_llm` 组缺少 `gates/s11_llm/pure_llm` 的真实调用录制。按说明由编排者在合并后录。本包的离线重放测试用的是测试自己写下的缓存。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：
