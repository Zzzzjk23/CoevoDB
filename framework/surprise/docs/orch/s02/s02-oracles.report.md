# 报告 · s02-oracles

## 改了哪些文件
- `framework/surprise/harness/oracles/__init__.py`：新增 `IMPLEMENTED` 与 `judge`（筛查后调用旧 oracle，不吞异常）
- `framework/surprise/harness/oracles/forms.py`：新增 `GroupedForm`、`split_grouped`、`full_query`
- `framework/surprise/harness/oracles/common.py`：新增记录每次 `run` 的代理，以及 Candidate / None 到 `Label` 的映射
- `framework/surprise/harness/oracles/tlp.py`：新增 TLP 的 WHERE、GROUP BY、DISTINCT 适配器
- `framework/surprise/harness/oracles/norec.py`：新增 NoREC 适配器
- `framework/surprise/harness/oracles/plan_variant.py`：新增 plan variant 适配器（只把折叠后的查询当查询形式）
- `framework/surprise/harness/evaluate.py`：新增 `evaluate`，每次调用记一条账，判定异常记成 `harness_error`
- `framework/tests/test_surprise_oracles.py`：新增形式解析、三值标签、假 runner 与参数错误测试
- `framework/tests/test_surprise_evaluate.py`：新增记账、异常记账、拒绝不留记录、重开账本测试

提交：`7d9b9e2`（`grok/s02-oracles`）

## 跑了哪些命令

命令：`python -m pytest -q testing tests`（在 `framework/`）
退出码：0

```
........................ss..................................s........... [ 50%]
.......................................................................  [100%]
140 passed, 3 skipped in 4.42s
```

命令：`python -m surprise.gates.s02 --only contracts ledger oracles evaluate`（在 `framework/`）
退出码：0

```
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE [only: contracts, ledger, oracles, evaluate]: PASS (4/4 groups passed)
```

命令：`python -m surprise.gates.s01`（在 `framework/`）
退出码：0

```
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 140 passed (baseline 64): 140 passed, 3 skipped in 3.84s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
```

命令：`python -m surprise.gates.all`（在 `framework/`）
退出码：1（说明里写明的预期：`manifest` 属于并行的另一个包）

```
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 140 passed (baseline 64): 140 passed, 3 skipped in 3.73s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
=== gate s02 ===
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[FAIL] manifest: ImportError: cannot import name 'manifest' from 'surprise.harness' (D:\CoevoDB\.worktrees\s02-oracles\framework\surprise\harness\__init__.py)
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: FAIL (4/5 groups passed)
=== summary ===
s01: PASS
s02: FAIL (exit 1)
GATES: FAIL (1/2 passed)
```

命令：`git status --short`（在 worktree 根，提交之后）
退出码：0
输出为空。

## 与说明的偏差
无。

## 未决问题
无。

## 第 1 轮返工

`evaluate` 在调用 `judge` 之前，用一条丢弃的占位 `ExperimentRecord` 按契约校验 `purpose`、`p_t`、`spec`、`phi`、`theory_version`。不合法则抛 `ValueError`，不调用 `runner_factory`，也不写账本。`oracle`、引擎、`run_id` 三项检查仍在最前面。

改动：
- `framework/surprise/harness/evaluate.py`：修改，执行前增加占位记录校验
- `framework/tests/test_surprise_evaluate.py`：修改，补 `purpose=""`、`p_t=1.5`、`spec` 含集合这三例

提交：`60fa36a`（`grok/s02-oracles`）

与说明的偏差：无。未决问题：无。

命令：`python -m pytest -q testing tests`（在 `framework/`）
退出码：0

```
........................ss..................................s........... [ 50%]
........................................................................ [100%]
141 passed, 3 skipped in 3.37s
```

命令：`python -m surprise.gates.s02 --only contracts ledger oracles evaluate`（在 `framework/`）
退出码：0

```
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE [only: contracts, ledger, oracles, evaluate]: PASS (4/4 groups passed)
```

命令：`python -m surprise.gates.s01`（在 `framework/`）
退出码：0

```
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 141 passed (baseline 64): 141 passed, 3 skipped in 3.32s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
```

命令：`python -m surprise.gates.all`（在 `framework/`）
退出码：1（预期：`manifest` 属于并行的另一个包；本 worktree 的门槛还没有编排者后补的 evaluate 参数检查）

```
=== gate s01 ===
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 141 passed (baseline 64): 141 passed, 3 skipped in 3.30s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
=== gate s02 ===
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[FAIL] manifest: ImportError: cannot import name 'manifest' from 'surprise.harness' (D:\CoevoDB\.worktrees\s02-oracles\framework\surprise\harness\__init__.py)
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: FAIL (4/5 groups passed)
=== summary ===
s01: PASS
s02: FAIL (exit 1)
GATES: FAIL (1/2 passed)
```

命令：`git status --short`（在 worktree 根，提交之后）
退出码：0
输出为空。
