# 审查包 · s03-version

- 生成时间：2026-10-09T04:11:39+11:00
- 基线：`session/s03`（d81010cc6e95）
- 分支：`grok/s03-version` @ 580a35013e8a，基线之上 2 个提交
- 运行：共 2 轮（返工 1 轮），最近一轮退出码 0，用时 8m56s
- grok：grok 1.0.46 (2765805b9442)；会话 `6e5c2b6d-8ea1-4f05-bf90-feebdfb71480`

## 红旗汇总

- 门槛未通过（退出码 1）
- 新增宽泛的异常捕获 7 处（确认没有吞掉失败）
- 疑似密钥 1 处、敏感文件名 0 个

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s03..grok/s03-version
git diff -M --stat session/s03..grok/s03-version
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/harness/oracles/version_differential.py`、`framework/surprise/harness/oracles/version_worker.py`、`framework/tests/test_surprise_s03_version.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`

| 状态 | 路径 | 标记 |
|---|---|---|
| A | `framework/surprise/harness/oracles/version_differential.py` |  |
| A | `framework/surprise/harness/oracles/version_worker.py` |  |
| A | `framework/tests/test_surprise_s03_version.py` |  |

提交：

- f89de7b Junke: s03-version: label a version mismatch only with independent direction evidence
- 580a350 Junke: s03-version: make version labels compatible, stable, and protocol-checked

## 2. diff 统计

```text
 .../harness/oracles/version_differential.py        | 687 ++++++++++++++++
 .../surprise/harness/oracles/version_worker.py     | 172 ++++
 framework/tests/test_surprise_s03_version.py       | 875 +++++++++++++++++++++
 3 files changed, 1734 insertions(+)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，0m12s；passed 221，skipped 3

```text
........................ss..................................s........... [ 32%]
........................................................................ [ 64%]
........................................................................ [ 96%]
........                                                                 [100%]
221 passed, 3 skipped in 11.58s
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，0m30s

```text
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 221 passed (baseline 64): 221 passed, 3 skipped in 12.28s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
=== gate s02 ===
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 36 files hashed (db4cb00fbd51); verify catches 3 kinds of change
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: PASS (5/5 groups passed)
=== gate s03 ===
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
[FAIL] local: ModuleNotFoundError: No module named 'surprise.harness.oracles.index_presence'
[PASS] cross: PG16 + DuckDB witness DF-A/DF-B; insufficient quorum, ties, multiple outliers and engine aliases rejected
[PASS] version: F2 old/new measured bags and regression direction; both old venvs work; directionless mismatch invalid
[FAIL] matrix: AssertionError: duckdb/index_presence hidden execution failure: {'y': 'invalid', 'oracle': 'index_presence', 'fail_kind': None, 'invalid_reason': 'harness_error', 'identity': {'switches': [], 'error_class': None, 'behavior': {}}, 'cve': {}, 'detail': {'exception': "ModuleNotFoundError: No module named 'surprise.harness.oracles.index_presence'"}}
S03 GATE: FAIL (3/5 groups passed)
=== summary ===
s01: PASS
s02: PASS
s03: FAIL (exit 1)
GATES: FAIL (2/3 passed)
```

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- 无

### 4.4 新增的宽泛异常捕获

- `framework/surprise/harness/oracles/version_differential.py:624` `except Exception:`
- `framework/surprise/harness/oracles/version_differential.py:637` `except Exception:`
- `framework/surprise/harness/oracles/version_worker.py:31` `except Exception as exc: # noqa: BLE001 - protocol failure, still JSON`
- `framework/surprise/harness/oracles/version_worker.py:67` `except Exception as exc: # noqa: BLE001 - reported, not judged`
- `framework/surprise/harness/oracles/version_worker.py:73` `except Exception as exc: # noqa: BLE001 - reported, not judged`
- `framework/surprise/harness/oracles/version_worker.py:88` `except Exception as exc: # noqa: BLE001 - reported, not judged`
- `framework/surprise/harness/oracles/version_worker.py:92` `except Exception as exc: # noqa: BLE001 - reported, not judged`

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- `framework/tests/test_surprise_s03_version.py:131` secret assignment: sec…(31 chars)
- 日志 `.orch/logs/s03-version.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 移动 `refs/heads/grok/s03-local` 65b0ebd9a036 → 47a36ebd9650
- 移动 `refs/heads/session/s03` d81010cc6e95 → c3ab4322a4f7

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s03-version.jsonl`：10256 条事件（auto_compact_completed 1，auto_compact_started 1，available_commands 102，end 2，orch.exit 2，orch.start 2，text 2073，thought 7094，tool_call 207，tool_call_update 674，usage 98）；各轮合计 98 个模型回合，grok 上报花费 2.8079 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 1 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- `Remove-Item -Force .orch\tmp\probe_df_bin.py, .orch\tmp\probe_new_types.py, .orch\tmp\probe_old.py, .orch\tmp\probe_pla… -> Tool `run_terminal_command` was not executed: Denied by permission policy: deny rule on bash matching "Remove-Item *-Recurse*"`

最后几条：

```text
tool_update [in_progress]: warning: in the working copy of 'framework/surprise/harness/oracles/version_differential.py', LF will be replaced by CRLF the next time Git touches it [grok/s03-version 580a350] s…
tool_update [completed]: exit: 0 warning: in the working copy of 'framework/surprise/harness/oracles/version_differential.py', LF will be replaced by CRLF the next time Git touches it [grok/s03-version 58…
thought: 当前工作区干净，无未提交更改。 正在撰写本次返工的完整报告。将更新 .orch/report.md，包含先前拒绝说明及最后 20 行命令输出。pytest 最终全部通过（33/221），s02、s03 等工具运行正常。
tool_call write: {"file_path": "D:\\CoevoDB\\.worktrees\\s03-version\\.orch\\report.md", "content": "# s03-version 报告（返工 1）\n\n## 改了哪些文件\n\n- `framework/surprise/harness/oracles/version_differenti…
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "# s03-version 报告\n\n## 改了哪些文件\n\n- `framework/surprise/harness/oracles/version_worker.py`：旧解释器用 `python -I <worker.py>` 执…
tool_call run_terminal_command: {"command": "git status --short; git log -2 --oneline", "description": "Confirm report stayed untracked and commit is current"}
tool_update [in_progress]: 
tool_update [in_progress]: 580a350 s03-version: make version labels compatible, stable, and protocol-checked
tool_update [completed]: exit: 0 580a350 s03-version: make version labels compatible, stable, and protocol-checked f89de7b s03-version: label a version mismatch only with independent direction evidence
text: 返工已提交到 `grok/s03-version` 的 `580a350`。主检出区增强后的 version 门槛和本 worktree 的原门槛都通过。报告在 `.orch/report.md`。 ## 改了哪些文件 - `framework/surprise/harness/oracles/version_differential.py`：DataFu…
end: stopReason=end_turn turns=24 cost_usd=0.8209606
orch.exit: {"pkg": "s03-version", "run": 2, "at": "2026-10-09T04:11:31+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# s03-version 报告（返工 1）

## 改了哪些文件

- `framework/surprise/harness/oracles/version_differential.py`：DataFusion 新旧结果都先走 `targets.datafusion_runner._norm` 再共享 normalize，不从字符串猜日期或 bytes。证据里的 `old_rows`/`new_rows` 按 bag 键排序，保留重复行、NULL 和值类型。双方查询失败改为 invalid/`query_error`，双方值依赖错误为 invalid/`value_dependent_error`；两边成功且 bag 相同仍 pass。子进程非 0 退出码、成功或查询错误缺少非空 `engine_version`、损坏的 typed cell、带垃圾的 stdout 都是 invalid/`harness_error`，不捞最后一段 JSON，不回退主环境版本。只在 `ModuleNotFoundError.name` 等于 `surprise.harness.oracles.index_presence` 时跳过该见证。`direction_evidence.witnesses` 保留原扁平身份并增加完整 `label`（`Label.to_dict()`）。
- `framework/tests/test_surprise_s03_version.py`：三条 DataFusion 类型查询改为端到端 label；DuckDB 类型期望未改。双方查询错误改为 invalid 断言。补了值依赖错误、行序、退出码、缺版本、坏 decimal、垃圾 stdout，以及 index 依赖缺失必须抛出的反例。
- `version_worker.py` 未改。旧进程仍只输出带类型的 JSON。

提交：`580a350`，分支 `grok/s03-version`。上一提交 `f89de7b`。

## 命令、退出码、输出末 20 行

`cd framework; python -m pytest -q tests/test_surprise_s03_version.py`，退出码 0。

```
.................................                                        [100%]
33 passed in 3.67s
```

`cd framework; python -m pytest -q testing tests`，退出码 0。

```
........................ss..................................s........... [ 32%]
........................................................................ [ 64%]
........................................................................ [ 96%]
........                                                                 [100%]
221 passed, 3 skipped in 11.68s
```

`cd framework; python -m surprise.gates.s03 --only version`，退出码 0。

```
[PASS] version: F2 old/new measured bags and regression direction; both old venvs work; directionless mismatch invalid
S03 GATE: PASS (1/1 groups passed)
```

`cd framework; python -m surprise.gates.s02`，退出码 0。

```
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 36 files hashed (db4cb00fbd51); verify catches 3 kinds of change
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: PASS (5/5 groups passed)
```

主检出区增强门槛 `D:\CoevoDB\.venv\Scripts\python.exe .orch\scratch\s3_root_gate.py s03-version --only version`，退出码 0。

```
[PASS] version: F2 old/new measured bags and regression direction; both old venvs work; directionless mismatch invalid
S03 GATE: PASS (1/1 groups passed)
```

skip 仍是 3。测试 221 = 返工前 216 + 5。worktree 内 `gates/s03.py` 未改。

## 与说明的偏差

- 审查把“双方都错仍 pass”收窄为两边成功返回同一 bag。`SELECT missing FROM t` 现为 invalid/`query_error`。同一错误结果 bag 的测试仍是 pass，且不调用参照或见证。
- 上一轮对 `.orch/tmp/empty-cwd` 的 `Remove-Item -Recurse` 被权限拒绝。当时没有改用别的方式删除。本轮没有清理 `.orch/tmp`，没有再尝试删除目录。
- 没有改旧 runner、cross、gates、docs 或公共文件，没有调用 LLM。

## 未决问题

无。DataFusion 的 `DATE`、`Binary`、`DECIMAL(10,2)` 三条查询在 50.0.0 与 54.0.0 上 `judge` 均为 pass，单元格分别是 `2020-01-02`、`0x6869`、`1.25`。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：

合并。当前HEAD 580a350，返工1轮。PI独立pytest221 passed/3 skipped，S01 7/7、S02 5/5通过；用主检出区增强门槛跑此分支的version组PASS。独立反例脚本核实DF DATE/bytes/Decimal三项pass、双方Binder错误invalid/query_error、真实runner行序互换标签完全一致且调用2次、非零退出/缺版本均invalid/harness_error。F2有参照与空参照的两支路均fail/regression。

完整初版3文件、返工diff、全部34条shell命令已读。范围仅brief的3路径，worktree干净；无新skip/xfail、测试配置或旧代码修改，无LLM标签。原新增“双方错误pass”断言和DF仅旧侧类型期望由PI反馈明确更正为执行前提与端到端类型断言；同一成功错误bag的pass测试和Duck类型断言保留，不是放宽测试。方向证据保留完整Label.to_dict和SQL，缺可选模块只按精确ModuleNotFoundError.name跳过，其它依赖异常传播。

三项自动红旗已核查：all门槛红只因派发基线缺local/index_presence，不是本包失败；7处广义捕获是引擎失败转JSON和新版版本信息回退，不写成成功；疑似密钥是测试假字符串，日志无实际密钥。初版递归删除empty-cwd被deny后目录至今仍存在，本轮8条新shell命令没有清理或重试目录删除，报告已注明。旧DF只直接导入datafusion与标准库、typed JSON回主进程归一化；旧normalizer未改。两轮花费合计2.8079美元。旧Cross DATE假候选属于继承问题，仍按HANDOFF交S4前提检查，不由本包修复。
