# 审查包 · s03-cross

- 生成时间：2026-10-09T03:10:54+11:00
- 基线：`session/s03`（eba9c849ea40）
- 分支：`grok/s03-cross` @ 06d571d3708c，基线之上 3 个提交
- 运行：共 3 轮（返工 2 轮），最近一轮退出码 0，用时 4m52s
- grok：grok 1.0.46 (2765805b9442)；会话 `7c2b4869-7c46-4c67-8561-85e81b47d12e`

## 红旗汇总

- 门槛未通过（退出码 1）
- 新增宽泛的异常捕获 14 处（确认没有吞掉失败）
- 疑似密钥 1 处、敏感文件名 0 个

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s03..grok/s03-cross
git diff -M --stat session/s03..grok/s03-cross
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/harness/oracles/cross_dbms.py`、`framework/surprise/harness/oracles/pg_reference.py`、`framework/tests/test_surprise_s03_cross.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`

| 状态 | 路径 | 标记 |
|---|---|---|
| A | `framework/surprise/harness/oracles/cross_dbms.py` |  |
| A | `framework/surprise/harness/oracles/pg_reference.py` |  |
| A | `framework/tests/test_surprise_s03_cross.py` |  |

提交：

- f7631e3 Junke: s03-cross: PostgreSQL reference runner and cross-DBMS unique-outlier quorum
- dc20f00 Junke: s03-cross: reject a second SQL statement before execution
- 06d571d Junke: s03-cross: reject SELECT INTO after a WITH head

## 2. diff 统计

```text
 framework/surprise/harness/oracles/cross_dbms.py   | 448 +++++++++++++
 framework/surprise/harness/oracles/pg_reference.py | 496 +++++++++++++++
 framework/tests/test_surprise_s03_cross.py         | 706 +++++++++++++++++++++
 3 files changed, 1650 insertions(+)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，0m09s；passed 188，skipped 3

```text
........................ss..................................s........... [ 37%]
........................................................................ [ 75%]
...............................................                          [100%]
188 passed, 3 skipped in 8.43s
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，0m25s

```text
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 188 passed (baseline 64): 188 passed, 3 skipped in 8.37s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
=== gate s02 ===
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 34 files hashed (12e6c632f56f); verify catches 3 kinds of change
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: PASS (5/5 groups passed)
=== gate s03 ===
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
[FAIL] local: ModuleNotFoundError: No module named 'surprise.harness.oracles.index_presence'
[PASS] cross: PG16 + DuckDB witness DF-A/DF-B; insufficient quorum, ties, multiple outliers and engine aliases rejected
[FAIL] version: ModuleNotFoundError: No module named 'surprise.harness.oracles.version_differential'
[FAIL] matrix: AssertionError: duckdb/index_presence hidden execution failure: {'y': 'invalid', 'oracle': 'index_presence', 'fail_kind': None, 'invalid_reason': 'harness_error', 'identity': {'switches': [], 'error_class': None, 'behavior': {}}, 'cve': {}, 'detail': {'exception': "ModuleNotFoundError: No module named 'surprise.harness.oracles.index_presence'"}}
S03 GATE: FAIL (2/5 groups passed)
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

- `framework/surprise/harness/oracles/cross_dbms.py:232` `except Exception as exc:`
- `framework/surprise/harness/oracles/cross_dbms.py:241` `except Exception:`
- `framework/surprise/harness/oracles/cross_dbms.py:306` `except Exception:`
- `framework/surprise/harness/oracles/cross_dbms.py:312` `except Exception:`
- `framework/surprise/harness/oracles/pg_reference.py:363` `except Exception:`
- `framework/surprise/harness/oracles/pg_reference.py:366` `except Exception:`
- `framework/surprise/harness/oracles/pg_reference.py:372` `except Exception:`
- `framework/surprise/harness/oracles/pg_reference.py:380` `except Exception as exc:`
- `framework/surprise/harness/oracles/pg_reference.py:390` `except Exception:`
- `framework/surprise/harness/oracles/pg_reference.py:393` `except Exception:`
- `framework/surprise/harness/oracles/pg_reference.py:414` `except Exception:`
- `framework/surprise/harness/oracles/pg_reference.py:443` `except Exception as exc:`
- `framework/surprise/harness/oracles/pg_reference.py:465` `except Exception:`
- `framework/surprise/harness/oracles/pg_reference.py:468` `except Exception:`

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- `framework/tests/test_surprise_s03_cross.py:458` secret assignment: sec…(32 chars)
- 日志 `.orch/logs/s03-cross.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 移动 `refs/heads/grok/s03-local` eba9c849ea40 → 65b0ebd9a036
- 移动 `refs/heads/session/s03` eba9c849ea40 → 1bdf089ca5ed

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s03-cross.jsonl`：6384 条事件（auto_compact_completed 1，auto_compact_started 1，available_commands 77，end 3，orch.exit 3，orch.start 3，text 937，thought 4659，tool_call 131，tool_call_update 502，usage 67）；各轮合计 67 个模型回合，grok 上报花费 2.8134 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_update [in_progress]: warning: in the working copy of 'framework/surprise/harness/oracles/pg_reference.py', LF will be replaced by CRLF the next time Git touches it warning: in the working copy of 'fra…
tool_update [completed]: exit: 0 warning: in the working copy of 'framework/surprise/harness/oracles/pg_reference.py', LF will be replaced by CRLF the next time Git touches it warning: in the working copy…
thought: 按 scratch_files 指令删除临时提交消息文件。
tool_call search_replace: {"file_path": "D:\\CoevoDB\\.worktrees\\s03-cross\\.orch\\report.md", "old_string": "提交：见本轮 git commit，分支 `grok/s03-cross`。", "new_string": "提交：`06d571d`，分支 `grok/s03-cross`。"}
tool_call run_terminal_command: {"command": "Remove-Item D:\\CoevoDB\\.worktrees\\s03-cross\\.orch\\tmp\\s03-cross-r2-msg.txt", "description": "Delete temporary commit message file"}
tool_update [in_progress]: 
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "提交：见本轮 git commit，分支 `grok/s03-cross`。", "new_string": "提交：`06d571d`，分支 `grok/s03-cross`。", "tool_output_for_prompt": "Th…
tool_update [completed]: exit: 0
thought: 审查意见返工已完成。已按 .orch/brief.md 的范围、禁区与格式要求提交更新，并同步更新了 .orch/report.md。
text: 已按第 2 轮审查返工并提交。 `is_readonly_query` 现在对所有允许的 head（SELECT / WITH / VALUES / TABLE）检查代码中的 `INTO`。`WITH x AS (SELECT 1 AS a) SELECT a INTO z FROM x` 会在执行前拒绝。字符串、标识符、注释、美元引号里的 `INTO` …
end: stopReason=end_turn turns=12 cost_usd=0.13643112
orch.exit: {"pkg": "s03-cross", "run": 3, "at": "2026-10-09T03:08:38+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# s03-cross 报告（返工 2）

## 改了哪些文件

- `framework/surprise/harness/oracles/pg_reference.py`：`is_readonly_query` 对所有允许的 head（SELECT/WITH/VALUES/TABLE）检查代码中的 `INTO`。字符串、带引号标识符、注释、美元引号里的 INTO 仍由 `_code_mask` 遮掉。
- `framework/tests/test_surprise_s03_cross.py`：无 DB 记录 runner 确认 `WITH … SELECT a INTO z` 不调用 `_execute`；`judge_case` 在开 runner 之前判 `not_applicable`。真实 PG 上正常 WITH、字符串/标识符/注释/美元引号中的 INTO 文本仍可执行。未向真实库发送 SELECT INTO 反例。原有法定数与 DF-A/B 断言保留。
- `framework/surprise/harness/oracles/cross_dbms.py` 未改。`judge_case` 已用 `is_readonly_query`。

提交：`06d571d`，分支 `grok/s03-cross`。

## 命令、退出码、输出末 20 行

`cd framework; python -m pytest -q testing tests`，退出码 0。

```
........................ss..................................s........... [ 37%]
........................................................................ [ 75%]
...............................................                          [100%]
188 passed, 3 skipped in 9.26s
```

`cd framework; python -m surprise.gates.s03 --only cross`，退出码 0。

```
[PASS] cross: PG16 + DuckDB witness DF-A/DF-B; insufficient quorum, ties, multiple outliers and engine aliases rejected
S03 GATE: PASS (1/1 groups passed)
```

`cd framework; python -m surprise.gates.s02`，退出码 0。

```
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 34 files hashed (12e6c632f56f); verify catches 3 kinds of change
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: PASS (5/5 groups passed)
```

skip 仍是 3。测试 188 = 返工 1 的 186 + 2。未改 worktree 内门槛。

## 与说明的偏差

- 没有改门槛、公共文件、旧代码或文档。没有对真实库执行 SELECT INTO 反例。
- `cross_dbms.py` 仍只调用 `is_readonly_query`，没有重复实现一份扫描器。

## 未决问题

无。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：

合并。返工2轮后独立pytest188 passed/3 skipped；S01 7/7、S02 5/5与主检出区最新cross组全部通过。已完整阅读3个新增文件及两轮完整diff，核对累计29条shell命令。仅允许路径改变，无skip/xfail、删断言、配置或旧代码变化，无LLM判定。14处宽泛异常捕获只负责参照失败保留错误/排除投票、版本信息回退与清理；固定假密码是测试数据，日志未命中密钥。其他ref变化与编排者/并行local包的操作一致。全门槛红项只因local/version尚未合并，按分组验收。PG隔离、超时后复用、所有新增执行前拒绝与合法引用/注释路径已独立复跑；DF-A/DF-B以三独立引擎法定数判目标唯一异类，SQLite语法错误未投票；版本别名拒绝。2.8134美元。第一轮修多语句/事务边界，第二轮修WITH SELECT INTO；范围与PLAN一致。
