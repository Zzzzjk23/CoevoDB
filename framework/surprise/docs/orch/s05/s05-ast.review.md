# 审查包 · s05-ast

- 生成时间：2026-10-09T10:33:33+11:00
- 基线：`session/s05`（7feb44c90cf4）
- 分支：`grok/s05-ast` @ 14779bf8170b，基线之上 2 个提交
- 运行：共 2 轮（返工 1 轮），最近一轮退出码 0，用时 16m57s
- grok：grok 1.0.46 (2765805b9442)；会话 `59108666-7a52-42e8-a797-ee633d9b592d`

## 红旗汇总

- 门槛未通过（退出码 1）
- 新增宽泛的异常捕获 3 处（确认没有吞掉失败）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s05..grok/s05-ast
git diff -M --stat session/s05..grok/s05-ast
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/features/ast.py`、`framework/surprise/features/__init__.py`、`framework/surprise/features/vocabulary.py`、`framework/surprise/features/phi.py`、`framework/tests/test_surprise_s05_ast*.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/features/__init__.py` |  |
| A | `framework/surprise/features/ast.py` |  |
| M | `framework/surprise/features/phi.py` |  |
| M | `framework/surprise/features/vocabulary.py` |  |
| A | `framework/tests/test_surprise_s05_ast.py` |  |

提交：

- e1d8332 Junke: s05-ast: extract statement-layer features with sqlglot and a regex fallback
- 14779bf Junke: s05-ast: fix nested queries, named windows, DML correlation, and fallback guesses

## 2. diff 统计

```text
 framework/surprise/features/__init__.py   |    2 +
 framework/surprise/features/ast.py        | 1027 +++++++++++++++++++++++++++++
 framework/surprise/features/phi.py        |    4 +-
 framework/surprise/features/vocabulary.py |    1 +
 framework/tests/test_surprise_s05_ast.py  |  818 +++++++++++++++++++++++
 5 files changed, 1850 insertions(+), 2 deletions(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，0m35s；passed 323，skipped 3

```text
........................ss..................................s........... [ 22%]
........................................................................ [ 44%]
........................................................................ [ 66%]
........................................................................ [ 88%]
......................................                                   [100%]
323 passed, 3 skipped in 34.94s
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，3m38s

```text
[PASS] tier2: fix-set attribution: F1, F6, F6 via TLP consistent, F2 escalated; profile attribution: DF-A consistent, DF-B escalated; 5 malformed hypotheses rejected (20s)
[PASS] tier3: 9 confirmed cases profiled: fix sets as measured and as in recall_repros.json, version ladder, minimised subsequence; noise removed; lost candidate downgraded (34s)
[PASS] m1: 50 final labels in the ledger (14 fail, 20 invalid, 16 pass); known recall gaps: DF-E, DF-G, DF-H, DF-J, F10, F5 (59s)
[PASS] freeze: 51 files (31 in the harness), hash 50fa40cf2d19, 8 constants match (0s)
S04 GATE: PASS (9/9 groups passed)
=== gate s05 ===
[PASS] vocab: 166 core entries (131 leaves) with hierarchy; open families; digest 1e001c14a030 stable across processes; invented feature registered, 8 bad ones rejected, saved and loaded; phi container (0s)
[PASS] spec: 12 hand-written phi / spec pairs judged as expected; 3 malformed specs rejected (0s)
[PASS] units: 23 hand-written feature sets project onto the expected units (0s)
[PASS] ast: 60 probes, 2 fallbacks, 3 invariance pairs; 12 families show their core features and are pairwise distinct (66 pairs) (0s)
[FAIL] dynamic: AttributeError: module 'surprise.features' has no attribute 'extract'
[FAIL] stable: `features phi` failed on 'SELECT EXISTS ( SELECT 1 FROM issue23979_s2 x WHERE x.o = l.': usage: python -m surprise.features [-h] {vocab}
python -m surprise.features: error: argument command: invalid choice: 'phi' (choose from vocab)
[FAIL] distinguish: AttributeError: module 'surprise.features' has no attribute 'extract'
[FAIL] specs: AttributeError: module 'surprise.features' has no attribute 'extract'
[FAIL] corpus: `features corpus` failed: usage: python -m surprise.features [-h] {vocab}
python -m surprise.features: error: argument command: invalid choice: 'corpus' (choose from vocab)
S05 GATE: FAIL (4/9 groups passed)
=== summary ===
s01: PASS
s02: PASS
s03: PASS
s04: PASS
s05: FAIL (exit 1)
GATES: FAIL (4/5 passed)
```

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- 无

### 4.4 新增的宽泛异常捕获

- `framework/surprise/features/ast.py:118` `except Exception:`
- `framework/surprise/features/ast.py:765` `except Exception:`
- `framework/surprise/features/ast.py:770` `except Exception:`

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s05-ast.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 移动 `refs/heads/session/s05` 7feb44c90cf4 → 52e60304027d

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s05-ast.jsonl`：6440 条事件（auto_compact_completed 1，auto_compact_started 1，available_commands 105，end 2，orch.exit 2，orch.start 2，text 912，thought 4513，tool_call 152，tool_call_update 655，usage 95）；各轮合计 95 个模型回合，grok 上报花费 2.4267 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_update [completed]: {"type": "ReadFile", "FileContent": {"content": "70→[PASS] environment: 51 files hashed, 17 imported old modules all covered; old engines, PostgreSQL 16.15 and 5 packages recorded…
thought: 将追加返工章节并提交代码。 pytest 323 个用例全部通过，跳过 3 个。已捕获 s01 至 s05 的输出。准备提交并更新报告。
tool_call search_replace: {"file_path": "D:\\CoevoDB\\.worktrees\\s05-ast\\.orch\\report.md", "old_string": "## 与说明的偏差\n无。\n\n## 未决问题\n无。", "new_string": "## 与说明的偏差\n无。\n\n## 未决问题\n无。\n\n## 第 1 轮返工\n\n按 `.…
tool_call run_terminal_command: {"command": "git add -- framework/surprise/features/ast.py framework/tests/test_surprise_s05_ast.py; git commit -m \"s05-ast: fix nested queries, named windows, DML correlation, a…
tool_update [in_progress]: 
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "## 与说明的偏差\n无。\n\n## 未决问题\n无。", "new_string": "## 与说明的偏差\n无。\n\n## 未决问题\n无。\n\n## 第 1 轮返工\n\n按 `.orch/review-1.md` 改了七处判定。…
tool_update [in_progress]: warning: in the working copy of 'framework/surprise/features/ast.py', LF will be replaced by CRLF the next time Git touches it
tool_update [in_progress]: warning: in the working copy of 'framework/surprise/features/ast.py', LF will be replaced by CRLF the next time Git touches it [grok/s05-ast 14779bf] s05-ast: fix nested queries, …
tool_update [completed]: exit: 0 warning: in the working copy of 'framework/surprise/features/ast.py', LF will be replaced by CRLF the next time Git touches it [grok/s05-ast 14779bf] s05-ast: fix nested q…
text: 第 1 轮返工已提交到 `grok/s05-ast` 的 `14779bf`。工作区干净，`.orch/report.md` 保留了第一轮内容，并追加了返工一节。 七处判定都按审查意见改了： - 子查询只认嵌套的查询节点，括号、集合运算操作数、CTE 主体、INSERT 和 `CREATE TABLE AS` 的来源都不算。 - 命名窗口只数函数调用，规格…
end: stopReason=end_turn turns=29 cost_usd=0.71756932
orch.exit: {"pkg": "s05-ast", "run": 2, "at": "2026-10-09T10:33:24+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s05-ast

## 改了哪些文件
- `framework/surprise/features/ast.py`：新增。`extract_ast(sql, engine, registry=None)` 用 sqlglot 提取语句层叶子；解析异常、空结果或多语句时状态为 `fallback`，正则只认能确定的叶子。
- `framework/surprise/features/__init__.py`：修改。导出 `extract_ast`。
- `framework/surprise/features/vocabulary.py`：修改。只在末尾追加叶子 `ast:window_fn:other`（窗口函数既不是排名、导航，也不是聚合）。
- `framework/surprise/features/phi.py`：修改。`_require_layers` 在检查取值是否属于允许集合之前先判断 `isinstance(value, str)`，非字符串抛 `ValueError`。
- `framework/tests/test_surprise_s05_ast.py`：新增。19 条测试：每个语句层叶子的正例与反例、规则 5 的各点、名字无关、兜底、发明特征验收前后、十二个族两两可区分，以及层状态非字符串时的 `ValueError`。

## 跑了哪些命令

### `cd framework; python -m pytest -q testing tests`
退出码：0

```
........................ss..................................s........... [ 22%]
........................................................................ [ 45%]
........................................................................ [ 67%]
........................................................................ [ 90%]
...............................                                          [100%]
316 passed, 3 skipped in 34.89s
```

### `cd framework; python -m surprise.gates.s01`
退出码：0

```
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 316 passed (baseline 64): 316 passed, 3 skipped in 35.87s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
```

### `cd framework; python -m surprise.gates.s02`
退出码：0

```
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 51 files hashed (50fa40cf2d19); verify catches 3 kinds of change
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: PASS (5/5 groups passed)
```

### `cd framework; python -m surprise.gates.s03`
退出码：0

```
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
[PASS] local: ART exercised, injected mismatch caught; 3 proved rules x 2 engines incl NULL; untrusted pairs rejected
[PASS] cross: PG16 + DuckDB witness DF-A/DF-B; insufficient quorum, ties, multiple outliers and engine aliases rejected
[PASS] version: F2 old/new measured bags and regression direction; both old venvs work; directionless mismatch invalid
[PASS] matrix: 7 oracles x 2 engines, 14 ledger records, no hidden harness failures, manifest verified
S03 GATE: PASS (5/5 groups passed)
```

### `cd framework; python -m surprise.gates.s04`
退出码：0

```
[PASS] contracts: 17 invalid sources, 7 CVE constants in the manifest; raw entry points untouched; 5 bad requests rejected before execution (1s)
[PASS] isolation: ok / error / timeout x2 / crash x2 told apart; 7 distinct processes for one candidate; process death, hang and dying reference contained (19s)
[PASS] tier1: 6 stable families fail after 5 fresh reruns; F8 unstable; F5 reproduced 0/5; 6 scripted rerun schedules (18s)
[PASS] premise: ASOF ties, writing statements and incomparable cross-engine values are invalid; their tie-free, crashing and comparable counterparts stay fail (13s)
[PASS] environment: 51 files hashed, 17 imported old modules all covered; old engines, PostgreSQL 16.15 and 5 packages recorded (0s)
[PASS] tier2: fix-set attribution: F1, F6, F6 via TLP consistent, F2 escalated; profile attribution: DF-A consistent, DF-B escalated; 5 malformed hypotheses rejected (20s)
[PASS] tier3: 9 confirmed cases profiled: fix sets as measured and as in recall_repros.json, version ladder, minimised subsequence; noise removed; lost candidate downgraded (34s)
[PASS] m1: 50 final labels in the ledger (14 fail, 20 invalid, 16 pass); known recall gaps: DF-E, DF-G, DF-H, DF-J, F10, F5 (58s)
[PASS] freeze: 51 files (31 in the harness), hash 50fa40cf2d19, 8 constants match (0s)
S04 GATE: PASS (9/9 groups passed)
```

### `cd framework; python -m surprise.gates.s05 --only vocab spec units ast`
退出码：0

```
[PASS] vocab: 166 core entries (131 leaves) with hierarchy; open families; digest 1e001c14a030 stable across processes; invented feature registered, 8 bad ones rejected, saved and loaded; phi container (0s)
[PASS] spec: 12 hand-written phi / spec pairs judged as expected; 3 malformed specs rejected (0s)
[PASS] units: 23 hand-written feature sets project onto the expected units (0s)
[PASS] ast: 60 probes, 2 fallbacks, 3 invariance pairs; 12 families show their core features and are pairwise distinct (66 pairs) (0s)
S05 GATE [only: vocab, spec, units, ast]: PASS (4/4 groups passed)
```

## 与说明的偏差
无。

## 未决问题
无。

## 第 1 轮返工

按 `.orch/review-1.md` 改了七处判定。原有测试没有删、没有放宽。`IN ((SELECT ...))` 记为 `ast:subquery:in`（审查允许 `in` 或 `scalar` 二选一）。

### 改了哪些文件
- `framework/surprise/features/ast.py`：修改。子查询改按嵌套查询节点判定；命名窗口取定义的规格；穿过 `IgnoreNulls` / `RespectNulls`；UPDATE / DELETE / MERGE 的关系名参与相关子查询；SET 赋值不记 `ast:cmp:eq`；本层已定义的限定名不算外层列；兜底不再把帧里的 BETWEEN、`WITH TIES` 当成谓词或 CTE，并在唯一语句的首词是 SELECT / INSERT / UPDATE / DELETE / MERGE 时输出语句种类。
- `framework/tests/test_surprise_s05_ast.py`：修改。为审查里的每一条例子补了必须有和不许有的断言。

### 跑了哪些命令

#### `cd framework; python -m pytest -q testing tests`
退出码：0

```
........................ss..................................s........... [ 22%]
........................................................................ [ 44%]
........................................................................ [ 66%]
........................................................................ [ 88%]
......................................                                   [100%]
323 passed, 3 skipped in 37.89s
```

#### `cd framework; python -m surprise.gates.s01`
退出码：0

```
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 323 passed (baseline 64): 323 passed, 3 skipped in 37.27s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
```

#### `cd framework; python -m surprise.gates.s02`
退出码：0

```
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 51 files hashed (50fa40cf2d19); verify catches 3 kinds of change
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: PASS (5/5 groups passed)
```

#### `cd framework; python -m surprise.gates.s03`
退出码：0

```
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
[PASS] local: ART exercised, injected mismatch caught; 3 proved rules x 2 engines incl NULL; untrusted pairs rejected
[PASS] cross: PG16 + DuckDB witness DF-A/DF-B; insufficient quorum, ties, multiple outliers and engine aliases rejected
[PASS] version: F2 old/new measured bags and regression direction; both old venvs work; directionless mismatch invalid
[PASS] matrix: 7 oracles x 2 engines, 14 ledger records, no hidden harness failures, manifest verified
S03 GATE: PASS (5/5 groups passed)
```

#### `cd framework; python -m surprise.gates.s04`
退出码：0

```
[PASS] contracts: 17 invalid sources, 7 CVE constants in the manifest; raw entry points untouched; 5 bad requests rejected before execution (1s)
[PASS] isolation: ok / error / timeout x2 / crash x2 told apart; 7 distinct processes for one candidate; process death, hang and dying reference contained (20s)
[PASS] tier1: 6 stable families fail after 5 fresh reruns; F8 unstable; F5 reproduced 0/5; 6 scripted rerun schedules (18s)
[PASS] premise: ASOF ties, writing statements and incomparable cross-engine values are invalid; their tie-free, crashing and comparable counterparts stay fail (13s)
[PASS] environment: 51 files hashed, 17 imported old modules all covered; old engines, PostgreSQL 16.15 and 5 packages recorded (0s)
[PASS] tier2: fix-set attribution: F1, F6, F6 via TLP consistent, F2 escalated; profile attribution: DF-A consistent, DF-B escalated; 5 malformed hypotheses rejected (20s)
[PASS] tier3: 9 confirmed cases profiled: fix sets as measured and as in recall_repros.json, version ladder, minimised subsequence; noise removed; lost candidate downgraded (34s)
[PASS] m1: 50 final labels in the ledger (14 fail, 20 invalid, 16 pass); known recall gaps: DF-E, DF-G, DF-H, DF-J, F10, F5 (58s)
[PASS] freeze: 51 files (31 in the harness), hash 50fa40cf2d19, 8 constants match (0s)
S04 GATE: PASS (9/9 groups passed)
```

#### `cd framework; python -m surprise.gates.s05 --only vocab spec units ast`
退出码：0

```
[PASS] vocab: 166 core entries (131 leaves) with hierarchy; open families; digest 1e001c14a030 stable across processes; invented feature registered, 8 bad ones rejected, saved and loaded; phi container (0s)
[PASS] spec: 12 hand-written phi / spec pairs judged as expected; 3 malformed specs rejected (0s)
[PASS] units: 23 hand-written feature sets project onto the expected units (0s)
[PASS] ast: 60 probes, 2 fallbacks, 3 invariance pairs; 12 families show their core features and are pairwise distinct (66 pairs) (0s)
S05 GATE [only: vocab, spec, units, ast]: PASS (4/4 groups passed)
```

### 与说明的偏差
无。

### 未决问题
无。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：

**合并。**（2026-10-09，第 1 轮返工之后）

依据：

- 独立复跑在 14779bf 上：pytest 323 passed / 3 skipped（基线 297，第一轮 316）；S01–S04 通过；S05 的 `vocab spec units ast` 四组通过。`gates.all` 的退出码 1 只来自 S05 其余五组，属于 `s05-dynamic`，是预期的。
- worktree 里的门槛是派发时的旧表（60 条）。会话分支上的新表（`AST_PROBES` 74 条、`FALLBACK_PROBES` 2 条、`FALLBACK_LACK` 3 条，52e6030）用 `.orch/scratch/s5_gate_probe_check.py` 对着返工后的代码跑：0 条失败；第一轮代码在其中 18 条上失败。
- 两轮 diff 全读（`ast.py` 1000 余行），36 条执行命令全看过：没有越界命令，没有执行 SQL，没有按 SQL 文本硬编码。
- 红旗"宽泛异常捕获 3 处"：第 118 行是 sqlglot 解析失败转兜底（说明要求的行为）；第 765、770 行是作用域分析失败时不记相关性、语句仍算解析成功。后者是静默退化，记入 HANDOFF。
- 编排者探测：`s5_review_ast.py`（整份语料 1092 条不抛异常、只出词表叶子、两次相同、兜底 34 条；400 条随机串；改名不变）BAD COUNT 0；`s5_review_ast2.py`（返工七处的 60 余条正反例）BAD COUNT 0；`s5_review_vocab.py`、`s5_review_vocab_r1.py` BAD COUNT 0（`_require_layers` 的那一处已改成 `ValueError`）。

留下的小问题（不为它们开第 2 轮，记入 HANDOFF 未决问题）：

1. `CREATE VIEW ... AS SELECT`、`COPY (SELECT ...) TO` 的查询被记成 `ast:subquery:scalar`（只排除了 CREATE TABLE AS 与 INSERT 的来源）。这两种语句不是被测语句的种类。
2. 引用另一个命名窗口的命名窗口（`w2 AS (w1 ORDER BY a)`）：只取 `w2` 自己写的部分，`w1` 的分区没有继承过来（少报）。
3. `INSERT ... ON CONFLICT DO UPDATE SET v = 3` 的赋值仍记成 `ast:cmp:eq`。
4. 兜底认 CTE 要求 `AS` 与括号之间有空白，`WITH c AS(...)` 认不出（少报）。
5. sqlglot 把它不认识的语句（EXPLAIN、VACUUM、COPY）读成不透明的 Command：状态是 `ok`，特征为空。
