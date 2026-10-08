# 审查包 · s03-local

- 生成时间：2026-10-09T03:17:39+11:00
- 基线：`session/s03`（eba9c849ea40）
- 分支：`grok/s03-local` @ 47a36ebd9650，基线之上 3 个提交
- 运行：共 3 轮（返工 2 轮），最近一轮退出码 0，用时 7m21s
- grok：grok 1.0.46 (2765805b9442)；会话 `4e82a95a-e8c9-4af8-979d-009df034ae30`

## 红旗汇总

- 门槛未通过（退出码 1）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s03..grok/s03-local
git diff -M --stat session/s03..grok/s03-local
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/harness/oracles/index_presence.py`、`framework/surprise/harness/oracles/equivalent_query.py`、`framework/surprise/harness/oracles/rewrites.py`、`framework/tests/test_surprise_s03_local.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`

| 状态 | 路径 | 标记 |
|---|---|---|
| A | `framework/surprise/harness/oracles/equivalent_query.py` |  |
| A | `framework/surprise/harness/oracles/index_presence.py` |  |
| A | `framework/surprise/harness/oracles/rewrites.py` |  |
| A | `framework/tests/test_surprise_s03_local.py` |  |

提交：

- 366e9b7 Junke: s03-local: add DuckDB ART index presence and proved rewrites
- 65b0ebd Junke: s03-local: decline non-connective AND and tighten pair checks
- 47a36eb Junke: s03-local: keep CASE text inside E-string literals

## 2. diff 统计

```text
 .../surprise/harness/oracles/equivalent_query.py   |  94 +++
 .../surprise/harness/oracles/index_presence.py     | 226 ++++++
 framework/surprise/harness/oracles/rewrites.py     | 708 ++++++++++++++++
 framework/tests/test_surprise_s03_local.py         | 895 +++++++++++++++++++++
 4 files changed, 1923 insertions(+)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，0m07s；passed 186，skipped 3

```text
........................ss..................................s........... [ 38%]
........................................................................ [ 76%]
.............................................                            [100%]
186 passed, 3 skipped in 7.25s
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，0m24s

```text
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 186 passed (baseline 64): 186 passed, 3 skipped in 7.18s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
=== gate s02 ===
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 35 files hashed (d986788907d9); verify catches 3 kinds of change
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: PASS (5/5 groups passed)
=== gate s03 ===
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
[PASS] local: ART exercised, injected mismatch caught; 3 proved rules x 2 engines incl NULL; untrusted pairs rejected
[FAIL] cross: ModuleNotFoundError: No module named 'surprise.harness.oracles.pg_reference'
[FAIL] version: ModuleNotFoundError: No module named 'surprise.harness.oracles.version_differential'
[FAIL] matrix: AssertionError: duckdb/version_differential hidden execution failure: {'y': 'invalid', 'oracle': 'version_differential', 'fail_kind': None, 'invalid_reason': 'harness_error', 'identity': {'switches': [], 'error_class': None, 'behavior': {}}, 'cve': {}, 'detail': {'exception': "ModuleNotFoundError: No module named 'surprise.harness.oracles.version_differential'"}}
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

- 无

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s03-local.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 新增 `refs/heads/grok/s03-cross` @ 06d571d3708c
- 新增 `refs/heads/grok/s03-version` @ d81010cc6e95
- 移动 `refs/heads/session/s03` eba9c849ea40 → b15722f4a6c4

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s03-local.jsonl`：8441 条事件（auto_compact_completed 1，auto_compact_started 1，available_commands 104，end 3，orch.exit 3，orch.start 3，text 1456，thought 6026，tool_call 163，tool_call_update 591，usage 90）；各轮合计 90 个模型回合，grok 上报花费 2.3360 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "# 报告 · s03-local\n\n## 改了哪些文件\n- `framework/surprise/harness/oracles/index_presence.py`：DuckDB ART 有/无索引的 multiset 比较。Dat…
tool_update [completed]: exit: 0
thought: 正在提交两个源文件。
tool_call run_terminal_command: {"command": "git add framework/surprise/harness/oracles/rewrites.py framework/tests/test_surprise_s03_local.py; git commit -F .orch/tmp/s03-local-msg.txt; git status --short; git …
tool_update [in_progress]: 
tool_update [in_progress]: warning: in the working copy of 'framework/surprise/harness/oracles/rewrites.py', LF will be replaced by CRLF the next time Git touches it
tool_update [in_progress]: warning: in the working copy of 'framework/surprise/harness/oracles/rewrites.py', LF will be replaced by CRLF the next time Git touches it [grok/s03-local 47a36eb] s03-local: keep…
tool_update [in_progress]: warning: in the working copy of 'framework/surprise/harness/oracles/rewrites.py', LF will be replaced by CRLF the next time Git touches it [grok/s03-local 47a36eb] s03-local: keep…
tool_update [completed]: exit: 0 warning: in the working copy of 'framework/surprise/harness/oracles/rewrites.py', LF will be replaced by CRLF the next time Git touches it [grok/s03-local 47a36eb] s03-loc…
text: 第 2 轮的转义字符串边界已经修好，并提交到 `grok/s03-local` 的 `47a36eb`。`.orch/report.md` 已更新。 紧贴引号的 `E`/`e` 现在按转义字符串扫描：反斜杠吃掉下一个字符，连续两个引号是一个嵌入引号。`SELECT E'abc\' CASE WHEN b IS NOT NULL THEN b ELSE 0 …
end: stopReason=end_turn turns=19 cost_usd=0.53113576
orch.exit: {"pkg": "s03-local", "run": 3, "at": "2026-10-09T03:17:24+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s03-local

## 改了哪些文件
- `framework/surprise/harness/oracles/index_presence.py`：DuckDB ART 有/无索引的 multiset 比较。DataFusion、非 SELECT、无可索引基表、建不出任何 ART 索引为 `invalid/not_applicable`。建索引失败不参与比较。`wrong_result` 的身份带索引名、建索引语句和 missing/extra。内部错误为 `crash`。原语句普通错误与值依赖错误为 invalid。不改会话或服务器设置。第 2 轮未改这个文件。
- `framework/surprise/harness/oracles/rewrites.py`：`RULES` 与 `apply_rule`。只实现 `double_negation`、`demorgan`、`case_to_coalesce`。De Morgan 只切一个逻辑 AND/OR；BETWEEN 自带的 AND，以及 CASE、方括号、花括号内部的 AND/OR，都不是连接词。紧贴引号的 `E`/`e` 打开转义字符串：反斜杠吃掉下一个字符，连续两个引号是一个嵌入引号，字符串里的 CASE 不会被改写。`U&` 紧贴引号的形式整句拒绝。美元引号和双写引号的标识符边界仍把内部文本留在记号里。`same_statement` 只忽略关键字大小写、记号外部空白和末尾一个分号。
- `framework/surprise/harness/oracles/equivalent_query.py`：只执行规则机械产出。未知规则、没有认证产出的外部 `paired_query`、与机械产出不一致的 `paired_query` 为 `invalid/untrusted_rewrite` 且不执行。字符串、引用标识符、美元引号、字面量内部空白和注释必须与机械产出一致。差异交给旧 `EquivalenceOracle`；其 None 按真实执行拆成 pass 或 invalid。`rewrite_rule=None` 使用 `double_negation`。第 2 轮未改这个文件。
- `framework/tests/test_surprise_s03_local.py`：保留 NULL、重复行、第 1 轮 BETWEEN/CASE 和 pair 断言。本轮用两个引擎核对 `E'...'` 的字符串内容，确认把内部 CASE 改成 COALESCE 会改变结果，`apply_rule` 为 None，judge 为 `invalid/not_applicable`。旁边的真 CASE、双写引号、美元引号、引用标识符和 `\\` 结束转义仍按边界处理。`E'Ab C'` 内部的大小写或空白变化是 `untrusted_rewrite` 且不执行。

## 跑了哪些命令

命令：`python -m pytest -q testing tests`（在 `framework/`）
退出码：0

```
........................ss..................................s........... [ 38%]
........................................................................ [ 76%]
.............................................                            [100%]
186 passed, 3 skipped in 7.68s
```

命令：`python -m surprise.gates.s03 --only local`（在 `framework/`）
退出码：0

```
[PASS] local: ART exercised, injected mismatch caught; 3 proved rules x 2 engines incl NULL; untrusted pairs rejected
S03 GATE: PASS (1/1 groups passed)
```

命令：`python -m surprise.gates.s02`（在 `framework/`）
退出码：0

```
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 35 files hashed (d986788907d9); verify catches 3 kinds of change
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: PASS (5/5 groups passed)
```

## 与说明的偏差
无。`U&` 紧贴引号时整句 `apply_rule` 返回 None，这是审查允许的保守拒绝，没有另做一套 Unicode 转义。多个顶层 WHERE 仍然不适用。实际执行的始终是规则返回的那条语句。

## 未决问题
- DuckDB 1.5.5 对门槛那张 3 行表，`CREATE INDEX` 成功后 `EXPLAIN` 仍是 `SEQ_SCAN`。比较的是索引存在与否下的 multiset，没有用 `SET`/`PRAGMA` 去逼计划走 ART。
- S3 的 cross、version、matrix 组不在本包，缺并行实现时预期红，未改门槛。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：

合并。返工2轮后独立pytest186 passed/3 skipped；S01 7/7、S02 5/5及主检出区增强local组全部通过。4个新文件和每轮完整diff已读，全部30条shell命令核对。仅允许路径变动，无新skip/xfail、删断言、配置改动、宽泛异常、LLM标签或旧实现改动。全门槛红项仅因该基线没有cross/version，按分组验收。ART实际创建/删除、注入差异、NULL/重复行，De Morgan语法内部AND、pair引用文本与E转义字符串反例均通过；额外2万行实测EXPLAIN ANALYZE确有Index Scan且oracle pass。第1轮修逻辑连接词和pair逐token比较，第2轮修E/e边界；U&保守不适用，评论及未引用标识符变化也不接受pair，只实际执行机械产物。2.3360美元。编排者自身门槛漏导入已修，执行者没有改门槛。
