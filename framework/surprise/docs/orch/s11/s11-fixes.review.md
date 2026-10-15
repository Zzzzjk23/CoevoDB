# 审查包 · s11-fixes

- 生成时间：2026-10-16T04:43:06+11:00
- 基线：`session/s11`（8d9781a47c60）
- 分支：`grok/s11-fixes` @ 511da3151d1b，基线之上 1 个提交
- 运行：共 1 轮（返工 0 轮），最近一轮退出码 0，用时 22m19s
- grok：grok 1.0.46 (2765805b9442)；会话 `dcecc9a9-1d74-4da5-b6c5-b8e29165b51a`

## 红旗汇总

- 本次审查包没有复跑测试（--skip-tests）
- 新增宽泛的异常捕获 2 处（确认没有吞掉失败）
- grok 日志里有 1 行疑似密钥（日志不入库，但要查来源）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s11..grok/s11-fixes
git diff -M --stat session/s11..grok/s11-fixes
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/theory/store.py`、`framework/surprise/experiments/loop.py`、`framework/surprise/roles/transport.py`、`framework/surprise/roles/constants.py`、`framework/surprise/metrics/dups.py`、`framework/surprise/metrics/recall.py`、`framework/tests/test_surprise_s11_fixes.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/experiments/loop.py` |  |
| M | `framework/surprise/metrics/dups.py` |  |
| M | `framework/surprise/metrics/recall.py` |  |
| M | `framework/surprise/roles/constants.py` |  |
| M | `framework/surprise/roles/transport.py` |  |
| M | `framework/surprise/theory/store.py` |  |
| A | `framework/tests/test_surprise_s11_fixes.py` |  |

提交：

- 511da31 Junke: fix(s11): store replace retry, keep loop errors, request deadline, vocab metrics

## 2. diff 统计

```text
 framework/surprise/experiments/loop.py     |  34 +++-
 framework/surprise/metrics/dups.py         |  18 +-
 framework/surprise/metrics/recall.py       |  17 +-
 framework/surprise/roles/constants.py      |   3 +
 framework/surprise/roles/transport.py      |  55 +++++-
 framework/surprise/theory/store.py         |  13 +-
 framework/tests/test_surprise_s11_fixes.py | 281 +++++++++++++++++++++++++++++
 7 files changed, 407 insertions(+), 14 deletions(-)
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

- `framework/surprise/experiments/loop.py:204` `except BaseException as report_exc:`
- `framework/surprise/roles/transport.py:114` `except BaseException as exc:`

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s11-fixes.jsonl` 中疑似密钥行数：1

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 新增 `refs/heads/grok/s11-purellm` @ 8d9781a47c60
- 新增 `refs/heads/grok/s11-runmetrics` @ 8d9781a47c60
- 移动 `refs/heads/session/s11` 8d9781a47c60 → 7d5b2aab319f

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s11-fixes.jsonl`：2102 条事件（available_commands 38，end 1，orch.exit 1，orch.start 1，plan 5，text 392，thought 880，tool_call 84，tool_call_update 672，usage 28）；各轮合计 28 个模型回合，grok 上报花费 0.6668 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_call run_terminal_command: {"command": "Remove-Item \"D:\\CoevoDB\\.worktrees\\s11-fixes\\.orch\\tmp\\msg.txt\"; git status", "description": "Remove scratch commit message; confirm clean tree"}
tool_update [in_progress]: 
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "", "new_string": "# 报告 · s11-fixes\n\n## 改了哪些文件\n- `framework/surprise/theory/store.py`：`os.replace` 遇到 `PermissionError`…
tool_update [in_progress]: On branch grok/s11-fixes nothing to commit, working tree clean
tool_update [completed]: exit: 0 On branch grok/s11-fixes nothing to commit, working tree clean
thought: 注意到 brief.md 中明确要求不要清理 .orch/tmp。
tool_call todo_write: {"todos": [{"id": "7", "status": "completed"}], "merge": true}
tool_update [completed]: {"type": "Todo", "TodosUpdated": {"summary_for_prompt": "- [completed] 1: Read gates + current source for 4 fixes\n- [completed] 2: Fix store.py PermissionError retry\n- [complete…
plan: {"entries": [{"content": "Read gates + current source for 4 fixes", "priority": "medium", "status": "completed"}, {"content": "Fix store.py PermissionError retry", "priority": "me…
text: 工作包已完成，提交在 `grok/s11-fixes`（`511da31`），报告在 `.orch/report.md`。 四处修复： - **存储**：`os.replace` 遇瞬时 `PermissionError` 最多重试 6 次 - **主循环**：原始异常写入 `error.txt`，写报告失败时仍抛原始异常 - **传输**：`REQUES…
end: stopReason=end_turn turns=28 cost_usd=0.66680188
orch.exit: {"pkg": "s11-fixes", "run": 1, "at": "2026-10-16T04:42:55+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s11-fixes

## 改了哪些文件
- `framework/surprise/theory/store.py`：`os.replace` 遇到 `PermissionError` 时按 `_REPLACE_ATTEMPTS` / `_REPLACE_DELAYS` 重试，最后一次仍失败则原样抛出。
- `framework/surprise/experiments/loop.py`：运行异常先写入 `error.txt`，再写报告；写报告失败时追加 traceback 并抛出原始异常。
- `framework/surprise/roles/constants.py`：新增 `REQUEST_DEADLINE_S = 600.0`，由现有 `as_dict()` 带出。
- `framework/surprise/roles/transport.py`：`DeepSeekTransport` 接受 `deadline_s`，流式读取并在总时限到达时抛 `TransportError("DeadlineExceeded")`。
- `framework/surprise/metrics/dups.py`：新增 `run_registry`；`new_families` / `compare` 用运行词表打开理论。
- `framework/surprise/metrics/recall.py`：`score` 与命令行 `score --run` 接受/读取运行词表。
- `framework/tests/test_surprise_s11_fixes.py`：四处修复的测试（存储重试与最终失败、两种 loop 异常、三种本地服务器、带词表的 `new_families` / `compare` / `score`）。

## 跑了哪些命令

### `cd framework; python -m pytest -q testing tests`
退出码：0

```
........................ss..................................s........... [  9%]
........................................................................ [ 18%]
........................................................................ [ 27%]
........................................................................ [ 36%]
........................................................................ [ 45%]
........................................................................ [ 55%]
........................................................................ [ 64%]
........................................................................ [ 73%]
........................................................................ [ 82%]
........................................................................ [ 91%]
.................................................................        [100%]
782 passed, 3 skipped in 182.24s (0:03:02)
```

### `cd framework; python -m surprise.gates.s11 --only store loop_error deadline`
退出码：0

```
[PASS] store: 6 replace calls for 3 transient failures (0.36s); a lasting failure raises PermissionError (2s)
[PASS] loop_error: original exception kept and written to error.txt (both, drive) (1s)
[PASS] deadline: normal answer passes; deadline 1.5s held (trickle 2.0s, silent 2.0s); errors booked, not cached (9s)
S11 GATE [only: store, loop_error, deadline]: PASS (3/3 groups passed)
```

### `cd framework; python -m surprise.gates.s11 --only vocabulary`
退出码：1

```
[FAIL] vocabulary: ModuleNotFoundError: No module named 'surprise.metrics.rundata'
S11 GATE [only: vocabulary]: FAIL (0/1 groups passed)
```

`surprise.metrics.dups` 与 `surprise.metrics.recall` 已成功导入；失败发生在随后的 `surprise.metrics.rundata` 导入（该组把 rundata 放在 dups/recall 的功能检查之前）。这是另一个包的交付物。

### `cd framework; python -m surprise.gates.s08 --only no_llm constants scoring operators candidates lanes determinism`
退出码：0

```
[PASS] no_llm: hunter, metrics, baselines, diagnoser and the loop import no model client and no old agent (0s)
[PASS] constants: 12 hunter and 2 diagnoser constants as planned; BETA = 1.0 (pre-experiment families per run: {'0.5': {'9001': 1, '9002': 3, '9003': 3}, '1.0': {'9001': 3, '9002': 3, '9003': 3}, '2.0': {'9001': 3, '9002': 3, '9003': 3}, '4.0': {'9001': 3, '9002': 5, '9003': 1}}) (0s)
[PASS] scoring: U untested 0.498 bits, adjacent 0.758; pending 0.455 after 50 probes, adjacent unexplored 1.365 at beta 2, confirmed 0 (0s)
[PASS] operators: 29 mutants of a three-statement case (4 deletions); oracle options filtered as planned (0s)
[PASS] candidates: after F1 and DF-A: {'refine': 4, 'generalize': 4, 'migrate': 2, 'explore': 81} candidates, all traceable; chose refine at 0.909 (14s)
[PASS] lanes: 32 records; executed {'bootstrap': 2, 'explore': 23, 'generalize': 3, 'refine': 4}; offered {'refine': 30, 'generalize': 31, 'migrate': 139, 'explore': 2474}; 4 families opened, 2 edits (58s)
[PASS] determinism: seed 31 twice in separate processes: 26 identical rows, labels and final theory; seed 32 differs (33s)
S08 GATE [only: no_llm, constants, scoring, operators, candidates, lanes, determinism]: PASS (7/7 groups passed)
```

### `cd framework; python -m surprise.gates.s10 --only constants frame switches`
退出码：0

```
[PASS] constants: 35 S10 constants as planned, S9 constants unchanged, library constants ['LIBRARY_ENV', 'LIBRARY_KINDS', 'LIBRARY_MIN_REFERENCES', 'LIBRARY_RULE_PREFIX', 'LIBRARY_SCHEMA'] (0s)
[PASS] frame: prior moves U 0.498 -> 1.000; extra rules offered; prepare once per round (1 rounds); vocabulary run extracts ast:set_op:except_all_two_tables (17s)
[PASS] switches: all on: calls {'implementer': 4, 'conjecturer': 1, 'prior': 3, 'translator': 1, 'vocab_inventor': 1, 'oracle_inventor': 1}; each role off: no call, no ledger line, plugin module not loaded (127s)
S10 GATE [only: constants, frame, switches]: PASS (3/3 groups passed)
```

## 与说明的偏差
`run_registry` 在 `config.json` 不存在时返回 `None`（与没有 `"vocabulary"` 键相同）。S8 现有测试的假运行目录只有 `theory/`，没有 `config.json`；真实运行总有该文件。

## 未决问题
无
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：
