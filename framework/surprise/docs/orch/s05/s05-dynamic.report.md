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
