# 审查包 · s05-dynamic

- 生成时间：2026-10-09T11:52:30+11:00
- 基线：`session/s05`（21ace71aead8）
- 分支：`grok/s05-dynamic` @ 204cdfb34d5d，基线之上 2 个提交
- 运行：共 2 轮（返工 1 轮），最近一轮退出码 0，用时 17m25s
- grok：grok 1.0.46 (2765805b9442)；会话 `01318c98-d1f5-4213-abf1-aeebff712a04`

## 红旗汇总

- 新增宽泛的异常捕获 9 处（确认没有吞掉失败）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s05..grok/s05-dynamic
git diff -M --stat session/s05..grok/s05-dynamic
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/features/extract.py`、`framework/surprise/features/plan.py`、`framework/surprise/features/data.py`、`framework/surprise/features/limits.py`、`framework/surprise/features/__main__.py`、`framework/surprise/features/__init__.py`、`framework/tests/test_surprise_s05_dynamic*.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/features/__init__.py` |  |
| M | `framework/surprise/features/__main__.py` |  |
| A | `framework/surprise/features/data.py` |  |
| A | `framework/surprise/features/extract.py` |  |
| A | `framework/surprise/features/limits.py` |  |
| A | `framework/surprise/features/plan.py` |  |
| A | `framework/tests/test_surprise_s05_dynamic.py` |  |

提交：

- f1284a6 Junke: s05-dynamic: add plan and data layers, extract, and the corpus report
- 204cdfb Junke: s05-dynamic: raise caller errors and stop truncated data looks

## 2. diff 统计

```text
 framework/surprise/features/__init__.py      |   3 +
 framework/surprise/features/__main__.py      | 170 ++++++-
 framework/surprise/features/data.py          | 362 +++++++++++++++
 framework/surprise/features/extract.py       | 242 ++++++++++
 framework/surprise/features/limits.py        |  17 +
 framework/surprise/features/plan.py          |  97 ++++
 framework/tests/test_surprise_s05_dynamic.py | 666 +++++++++++++++++++++++++++
 7 files changed, 1555 insertions(+), 2 deletions(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，0m39s；passed 367，skipped 3

```text
........................ss..................................s........... [ 19%]
........................................................................ [ 38%]
........................................................................ [ 58%]
........................................................................ [ 77%]
........................................................................ [ 97%]
..........                                                               [100%]
367 passed, 3 skipped in 39.03s
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 0，4m23s

```text
[PASS] premise: ASOF ties, writing statements and incomparable cross-engine values are invalid; their tie-free, crashing and comparable counterparts stay fail (13s)
[PASS] environment: 51 files hashed, 17 imported old modules all covered; old engines, PostgreSQL 16.15 and 5 packages recorded (0s)
[PASS] tier2: fix-set attribution: F1, F6, F6 via TLP consistent, F2 escalated; profile attribution: DF-A consistent, DF-B escalated; 5 malformed hypotheses rejected (20s)
[PASS] tier3: 9 confirmed cases profiled: fix sets as measured and as in recall_repros.json, version ladder, minimised subsequence; noise removed; lost candidate downgraded (34s)
[PASS] m1: 50 final labels in the ledger (14 fail, 20 invalid, 16 pass); known recall gaps: DF-E, DF-G, DF-H, DF-J, F10, F5 (59s)
[PASS] freeze: 51 files (31 in the harness), hash 50fa40cf2d19, 8 constants match (0s)
S04 GATE: PASS (9/9 groups passed)
=== gate s05 ===
[PASS] vocab: 166 core entries (131 leaves) with hierarchy; open families; digest 1e001c14a030 stable across processes; invented feature registered, 8 bad ones rejected, saved and loaded; phi container (0s)
[PASS] spec: 12 hand-written phi / spec pairs judged as expected; 3 malformed specs rejected (0s)
[PASS] units: 23 hand-written feature sets project onto the expected units (0s)
[PASS] ast: 74 probes, 5 fallbacks, 3 invariance pairs; 12 families show their core features and are pairwise distinct (66 pairs) (0s)
[PASS] dynamic: 13 data probes on two engines, 6 measured plans; failing setup, ast-only and isolated extraction behave (2s)
[PASS] stable: 25 cases (12 families, 13 corpus seeds): two processes and this one agree (14s)
[PASS] distinguish: 12 families: pairwise distinct by statement text alone (66 pairs) and by phi; DF-A -> DF-B is one sibling swap; 11 measured units (0s)
[PASS] specs: 17 hand-written spec / SQL pairs, all judged correctly (0s)
[PASS] corpus: 1092 seeds in 76 units over 10 constructs; ast fallback 34, plan ok 480, data ok 483; top [('postgres|plain|none|unknown', 134), ('duckdb|plain|none|unknown', 83), ('duckdb|window|none|unknown', 56)]; 12s (23s)
S05 GATE: PASS (9/9 groups passed)
=== summary ===
s01: PASS
s02: PASS
s03: PASS
s04: PASS
s05: PASS
GATES: PASS (5/5 passed)
```

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- 无

### 4.4 新增的宽泛异常捕获

- `framework/surprise/features/data.py:148` `except Exception as exc:`
- `framework/surprise/features/data.py:184` `except Exception:`
- `framework/surprise/features/data.py:214` `except Exception:`
- `framework/surprise/features/data.py:352` `except Exception:`
- `framework/surprise/features/extract.py:112` `except Exception:`
- `framework/surprise/features/extract.py:141` `except Exception:`
- `framework/surprise/features/extract.py:217` `except Exception:`
- `framework/surprise/features/plan.py:23` `except Exception:`
- `framework/surprise/features/plan.py:87` `except Exception:`

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s05-dynamic.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 移动 `refs/heads/session/s05` 21ace71aead8 → ecfdfaf502b1

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s05-dynamic.jsonl`：5250 条事件（auto_compact_completed 1，auto_compact_started 1，available_commands 102，end 2，orch.exit 2，orch.start 2，text 1024，thought 3444，tool_call 160，tool_call_update 424，usage 88）；各轮合计 88 个模型回合，grok 上报花费 2.3402 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "## 未决问题\n`framework/targets/datafusion_runner.py` 的 `_norm` 遇到浮点 NaN 或 Inf 会在 `int(...)` 处抛出 `ValueError`，`run` 把整次取行记成错误…
thought: 审查意见中偏差部分先写“无”，随后描述了修正内容。 修正内容属于合规而非偏差，保留说明段落以体现旧选择被撤销。准备执行 git add、commit 并检查状态，不修改 git 配置。
tool_call run_terminal_command: {"command": "git add framework/surprise/features/data.py framework/surprise/features/extract.py framework/surprise/features/limits.py framework/tests/test_surprise_s05_dynamic.py;…
tool_update [in_progress]: 
tool_update [in_progress]: warning: in the working copy of 'framework/surprise/features/data.py', LF will be replaced by CRLF the next time Git touches it
tool_update [in_progress]: warning: in the working copy of 'framework/surprise/features/data.py', LF will be replaced by CRLF the next time Git touches it [grok/s05-dynamic 204cdfb] s05-dynamic: raise calle…
tool_update [in_progress]: warning: in the working copy of 'framework/surprise/features/data.py', LF will be replaced by CRLF the next time Git touches it [grok/s05-dynamic 204cdfb] s05-dynamic: raise calle…
tool_update [completed]: exit: 0 warning: in the working copy of 'framework/surprise/features/data.py', LF will be replaced by CRLF the next time Git touches it [grok/s05-dynamic 204cdfb] s05-dynamic: rai…
thought: Git 工作区干净，无未提交的更改。
text: 第 1 轮返工已经提交到 `grok/s05-dynamic`（`204cdfb`），`.orch/report.md` 保留了第一轮内容，并追加了「第 1 轮返工」。 三处行为已按审查意见改完： - `extract_isolated` 在起子进程之前抛出调用方错误：词表读不了抛 `OSError`，内容不合格抛 `ValueError`，没有 runn…
end: stopReason=end_turn turns=30 cost_usd=0.68196112
orch.exit: {"pkg": "s05-dynamic", "run": 2, "at": "2026-10-09T11:52:20+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s05-dynamic

## 改了哪些文件
- `framework/surprise/features/limits.py`：新增。表行数上限 10000、单条探测超时 10 秒、隔离超时 60 秒。
- `framework/surprise/features/plan.py`：新增。DuckDB 走 `diagnosis.bisect.plan_op_names`，DataFusion 解析 `EXPLAIN` 的 `physical_plan` 文本；算子名只保留字母、数字和下划线。
- `framework/surprise/features/data.py`：新增。在库上取被引用的基表和集合运算输入，在 Python 里数形状、边角值、列类型和输入性质。
- `framework/surprise/features/extract.py`：新增。`extract` 组合三层；`extract_isolated` 起子进程跑 `phi`，超时后在 Windows 上杀掉进程树，失败时只保留语句层。
- `framework/surprise/features/__init__.py`：修改。导出 `extract` 和 `extract_isolated`。
- `framework/surprise/features/__main__.py`：修改。增加 `phi` 与 `corpus` 子命令；`vocab` 输出不变。
- `framework/tests/test_surprise_s05_dynamic.py`：新增。计划、数据、组合、隔离、命令行和语料报告。

## 跑了哪些命令

### `python -m pytest -q testing tests`
退出码：0

```
........................ss..................................s........... [ 19%]
........................................................................ [ 39%]
........................................................................ [ 59%]
........................................................................ [ 78%]
........................................................................ [ 98%]
......                                                                   [100%]
363 passed, 3 skipped in 39.59s
```

### `python -m surprise.gates.s01`
退出码：0

```
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 363 passed (baseline 64): 363 passed, 3 skipped in 68.35s (0:01:08)
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
```

### `python -m surprise.gates.s02`
退出码：0

```
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 51 files hashed (50fa40cf2d19); verify catches 3 kinds of change
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: PASS (5/5 groups passed)
```

### `python -m surprise.gates.s03`
退出码：0

```
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
[PASS] local: ART exercised, injected mismatch caught; 3 proved rules x 2 engines incl NULL; untrusted pairs rejected
[PASS] cross: PG16 + DuckDB witness DF-A/DF-B; insufficient quorum, ties, multiple outliers and engine aliases rejected
[PASS] version: F2 old/new measured bags and regression direction; both old venvs work; directionless mismatch invalid
[PASS] matrix: 7 oracles x 2 engines, 14 ledger records, no hidden harness failures, manifest verified
S03 GATE: PASS (5/5 groups passed)
```

### `python -m surprise.gates.s04`
退出码：0

```
[PASS] contracts: 17 invalid sources, 7 CVE constants in the manifest; raw entry points untouched; 5 bad requests rejected before execution (1s)
[PASS] isolation: ok / error / timeout x2 / crash x2 told apart; 7 distinct processes for one candidate; process death, hang and dying reference contained (19s)
[PASS] tier1: 6 stable families fail after 5 fresh reruns; F8 unstable; F5 reproduced 1/5; 6 scripted rerun schedules (17s)
[PASS] premise: ASOF ties, writing statements and incomparable cross-engine values are invalid; their tie-free, crashing and comparable counterparts stay fail (13s)
[PASS] environment: 51 files hashed, 17 imported old modules all covered; old engines, PostgreSQL 16.15 and 5 packages recorded (0s)
[PASS] tier2: fix-set attribution: F1, F6, F6 via TLP consistent, F2 escalated; profile attribution: DF-A consistent, DF-B escalated; 5 malformed hypotheses rejected (20s)
[PASS] tier3: 9 confirmed cases profiled: fix sets as measured and as in recall_repros.json, version ladder, minimised subsequence; noise removed; lost candidate downgraded (34s)
[PASS] m1: 50 final labels in the ledger (14 fail, 20 invalid, 16 pass); known recall gaps: DF-E, DF-G, DF-H, DF-J, F10, F5 (59s)
[PASS] freeze: 51 files (31 in the harness), hash 50fa40cf2d19, 8 constants match (0s)
S04 GATE: PASS (9/9 groups passed)
```

### `python -m surprise.gates.s05`
退出码：0

```
[PASS] vocab: 166 core entries (131 leaves) with hierarchy; open families; digest 1e001c14a030 stable across processes; invented feature registered, 8 bad ones rejected, saved and loaded; phi container (0s)
[PASS] spec: 12 hand-written phi / spec pairs judged as expected; 3 malformed specs rejected (0s)
[PASS] units: 23 hand-written feature sets project onto the expected units (0s)
[PASS] ast: 74 probes, 5 fallbacks, 3 invariance pairs; 12 families show their core features and are pairwise distinct (66 pairs) (0s)
[PASS] dynamic: 13 data probes on two engines, 6 measured plans; failing setup, ast-only and isolated extraction behave (2s)
[PASS] stable: 25 cases (12 families, 13 corpus seeds): two processes and this one agree (14s)
[PASS] distinguish: 12 families: pairwise distinct by statement text alone (66 pairs) and by phi; DF-A -> DF-B is one sibling swap; 11 measured units (0s)
[PASS] specs: 17 hand-written spec / SQL pairs, all judged correctly (0s)
[PASS] corpus: 1092 seeds in 76 units over 10 constructs; ast fallback 34, plan ok 480, data ok 483; top [('postgres|plain|none|unknown', 134), ('duckdb|plain|none|unknown', 83), ('duckdb|window|none|unknown', 56)]; 11s (23s)
S05 GATE: PASS (9/9 groups passed)
```

以上命令都在 `framework/` 下执行。

## 与说明的偏差
无。

集合运算的输入复用了同一行数上限。某一侧超过上限时，该侧不产出特征，数据层仍是 ok；基表超过上限时，整层为 unavailable。说明只把上限写在取表上，这是未写死的实现选择。门槛语料没有因此掉出允许范围。

## 未决问题
`framework/targets/datafusion_runner.py` 的 `_norm` 遇到浮点 NaN 或 Inf 会在 `int(...)` 处抛出 `ValueError`，`run` 把整次取行记成错误。含这些值的 DataFusion 表因此使数据层变为 unavailable，而不是发出 `data:value:non_finite`。特征代码本身认 Python 浮点 NaN/Inf，也认 DuckDB 归一化后的 `float:nan`、`float:+inf`、`float:-inf`。本包不能改 runner。S5 门槛里的 DataFusion 探针没有这类值。

# 第 1 轮返工

## 改了哪些文件
- `framework/surprise/features/extract.py`：`extract_isolated` 在起子进程之前加载词表并检查引擎有没有 runner。读不了或内容不合格的 `registry_path` 抛 `Registry.load` 的异常；要算 `plan` 或 `data` 而没有 runner 时抛 `ValueError`；子进程退出码 2 抛 `ValueError`，消息是它的标准错误。崩溃、超时、输出解析不了仍退化。
- `framework/surprise/features/data.py`：基表引用只保留 catalog、schema、表名（引号保留）。引用生成失败，或集合运算的某一侧跑起来但超过行数上限，整个数据层为 `unavailable`，不输出 `data:` 特征。单独跑不起来的输入仍不产出特征，层保持 `ok`。
- `framework/surprise/features/limits.py`：`MAX_TABLE_ROWS` 的注释改为超上限的集合输入也使数据层不可用。常数值未改。
- `framework/tests/test_surprise_s05_dynamic.py`：新增四条测试，覆盖采样子句、括号连接、超上限集合输入，以及隔离提取的调用方错误和 `timeout_s=0.01` 退化。已有断言没有删、没有放宽，也没有改期望。

## 跑了哪些命令

### `python -m pytest -q testing tests`
退出码：0

```
........................ss..................................s........... [ 19%]
........................................................................ [ 38%]
........................................................................ [ 58%]
........................................................................ [ 77%]
........................................................................ [ 97%]
..........                                                               [100%]
367 passed, 3 skipped in 38.20s
```

### `python -m surprise.gates.s01`
退出码：0

```
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 367 passed (baseline 64): 367 passed, 3 skipped in 38.36s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
```

### `python -m surprise.gates.s02`
退出码：0

```
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 51 files hashed (50fa40cf2d19); verify catches 3 kinds of change
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: PASS (5/5 groups passed)
```

### `python -m surprise.gates.s03`
退出码：0

```
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
[PASS] local: ART exercised, injected mismatch caught; 3 proved rules x 2 engines incl NULL; untrusted pairs rejected
[PASS] cross: PG16 + DuckDB witness DF-A/DF-B; insufficient quorum, ties, multiple outliers and engine aliases rejected
[PASS] version: F2 old/new measured bags and regression direction; both old venvs work; directionless mismatch invalid
[PASS] matrix: 7 oracles x 2 engines, 14 ledger records, no hidden harness failures, manifest verified
S03 GATE: PASS (5/5 groups passed)
```

### `python -m surprise.gates.s04`
退出码：0

```
[PASS] contracts: 17 invalid sources, 7 CVE constants in the manifest; raw entry points untouched; 5 bad requests rejected before execution (1s)
[PASS] isolation: ok / error / timeout x2 / crash x2 told apart; 7 distinct processes for one candidate; process death, hang and dying reference contained (19s)
[PASS] tier1: 6 stable families fail after 5 fresh reruns; F8 unstable; F5 reproduced 0/5; 6 scripted rerun schedules (17s)
[PASS] premise: ASOF ties, writing statements and incomparable cross-engine values are invalid; their tie-free, crashing and comparable counterparts stay fail (13s)
[PASS] environment: 51 files hashed, 17 imported old modules all covered; old engines, PostgreSQL 16.15 and 5 packages recorded (0s)
[PASS] tier2: fix-set attribution: F1, F6, F6 via TLP consistent, F2 escalated; profile attribution: DF-A consistent, DF-B escalated; 5 malformed hypotheses rejected (20s)
[PASS] tier3: 9 confirmed cases profiled: fix sets as measured and as in recall_repros.json, version ladder, minimised subsequence; noise removed; lost candidate downgraded (34s)
[PASS] m1: 50 final labels in the ledger (14 fail, 20 invalid, 16 pass); known recall gaps: DF-E, DF-G, DF-H, DF-J, F10, F5 (59s)
[PASS] freeze: 51 files (31 in the harness), hash 50fa40cf2d19, 8 constants match (0s)
S04 GATE: PASS (9/9 groups passed)
```

### `python -m surprise.gates.s05`
退出码：0

```
[PASS] vocab: 166 core entries (131 leaves) with hierarchy; open families; digest 1e001c14a030 stable across processes; invented feature registered, 8 bad ones rejected, saved and loaded; phi container (0s)
[PASS] spec: 12 hand-written phi / spec pairs judged as expected; 3 malformed specs rejected (0s)
[PASS] units: 23 hand-written feature sets project onto the expected units (0s)
[PASS] ast: 74 probes, 5 fallbacks, 3 invariance pairs; 12 families show their core features and are pairwise distinct (66 pairs) (0s)
[PASS] dynamic: 13 data probes on two engines, 6 measured plans; failing setup, ast-only and isolated extraction behave (2s)
[PASS] stable: 25 cases (12 families, 13 corpus seeds): two processes and this one agree (14s)
[PASS] distinguish: 12 families: pairwise distinct by statement text alone (66 pairs) and by phi; DF-A -> DF-B is one sibling swap; 11 measured units (0s)
[PASS] specs: 17 hand-written spec / SQL pairs, all judged correctly (0s)
[PASS] corpus: 1092 seeds in 76 units over 10 constructs; ast fallback 34, plan ok 480, data ok 483; top [('postgres|plain|none|unknown', 134), ('duckdb|plain|none|unknown', 83), ('duckdb|window|none|unknown', 56)]; 11s (23s)
S05 GATE: PASS (9/9 groups passed)
```

以上命令都在 `framework/` 下执行。

## 与说明的偏差
无。

第一轮把超上限的集合输入做成“该侧不产出特征、数据层仍是 ok”。审查否定了这个选择，本轮已改成整层 `unavailable`、不输出数据特征。语料计数没有变化（data ok 仍是 483）。

## 未决问题
无。第一轮记下的 DataFusion runner 对 NaN / Inf 报错仍在，本轮没有改 `framework/targets/datafusion_runner.py`。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：

**合并。**（2026-10-09，第 1 轮返工之后）

依据：

- 独立复跑在 204cdfb 上：pytest 367 passed / 3 skipped（基线 323，第一轮 363）；`gates.all` 退出码 0，S01–S05 全过，S05 九组全过。语料 1092 条落在 76 个单元、10 种主构造，语句层兜底 34 条，计划层 480 条、数据层 483 条可用，返工前后不变。
- 两轮 diff 全读（`extract.py`、`plan.py`、`data.py`、`limits.py`、`__main__.py`），23 条执行命令全看过：没有越界命令，没有改前两个包的文件，没有执行被测语句。
- 红旗"宽泛异常捕获 9 处"逐处看过：`plan.py` 两处与 `data.py` 第 352 行把探测失败变成该层 `unavailable`；`data.py` 第 148 行把引用生成失败变成 `_RefError`（整层 `unavailable`）；第 184、214 行是集合运算的某个输入或它的 WITH 生成不了 SQL，按"单独跑不起来"处理（不出特征，层仍 `ok`）；`extract.py` 三处是 setup 抛异常记为失败、超时后收尸、关闭 runner。没有把失败变成一个看起来完整的结果的。
- 编排者探测：`s5_review_dynamic.py`（六种语句都不执行被测语句、不发聚合探测、runner 只 setup 一次并关闭；层参数；超上限的表；CTE 遮蔽；边角值；两种引擎的计划；隔离提取；`phi` 与 `corpus` 命令）BAD COUNT 0；`s5_review_dynamic2.py`（返工三处的正反例）BAD COUNT 0；前两个包的探测脚本与新门槛表核对脚本重跑，全部 BAD COUNT 0 / 0 条失败。

留下的事（记入 HANDOFF 未决问题）：

1. 旧 DataFusion runner 遇到 NaN / Inf 报错，DataFusion 上含非有限值的表数据层为 `unavailable`。旧代码，不改。
2. 集合运算的输入单独跑不起来时不出特征、层仍 `ok`：这时 φ 里没有 `data:setop:*` 不等于没有重复行。这是说明里定的行为。
3. 语料报告的 `vocab` 是 `{digest, entries, leaves}` 而不是单个字符串：收下。
