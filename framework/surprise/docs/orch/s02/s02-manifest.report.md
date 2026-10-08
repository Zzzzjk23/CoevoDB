# 报告 · s02-manifest

## 改了哪些文件
- `framework/surprise/harness/manifest.py`：新增。run manifest、harness 哈希与 `hash` / `write` / `verify` 命令。
- `framework/tests/test_surprise_manifest.py`：新增。临时文件树上的哈希、校验与命令行测试。

提交：`3bf4dd4`，分支 `grok/s02-manifest`。

## 跑了哪些命令

命令：`cd framework; python -m pytest -q testing tests`

退出码：0

```
........................ss..................................s........... [ 52%]
.................................................................        [100%]
134 passed, 3 skipped in 3.23s
```

命令：`cd framework; python -m surprise.gates.s02 --only contracts ledger manifest`

退出码：0

```
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 15 files hashed (b03292396561); verify catches 3 kinds of change
S02 GATE [only: contracts, ledger, manifest]: PASS (3/3 groups passed)
```

命令：`cd framework; python -m surprise.gates.s01`

退出码：0

```
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 134 passed (baseline 64): 134 passed, 3 skipped in 3.28s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
```

命令：`cd framework; python -m surprise.harness.manifest hash`

退出码：0

```
b03292396561aacc6e901afefb6f677c0f7e8e43e398d79d6568f11856752dfb
```

命令：`git status --short`（worktree 根）

退出码：0

```
```

输出为空。

命令：`cd framework; python -m surprise.gates.all`

退出码：1。说明里写明这是预期结果：`oracles` 和 `evaluate` 属于并行的另一个包。

```
=== gate s01 ===
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 134 passed (baseline 64): 134 passed, 3 skipped in 3.42s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
=== gate s02 ===
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 15 files hashed (b03292396561); verify catches 3 kinds of change
[FAIL] oracles: ModuleNotFoundError: No module named 'surprise.harness.oracles'
[FAIL] evaluate: ModuleNotFoundError: No module named 'surprise.harness.evaluate'
S02 GATE: FAIL (3/5 groups passed)
=== summary ===
s01: PASS
s02: FAIL (exit 1)
GATES: FAIL (1/2 passed)
```

## 与说明的偏差
无。

## 未决问题
无。
