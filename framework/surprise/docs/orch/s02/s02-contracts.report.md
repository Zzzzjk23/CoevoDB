# 报告 · s02-contracts

## 改了哪些文件
- `framework/surprise/harness/contracts.py`：新增。`SqlCase`、`IdentityEvidence`、`Label`、`ExperimentRecord` 四个冻结契约，以及 `SCHEMA_VERSION`、`LABELS`、`ORACLE_IDS`、`FAIL_KINDS`、`INVALID_REASONS`。
- `framework/surprise/harness/constants.py`：新增。`QUERY_TIMEOUT_S = 10.0`，`as_dict()` 自动收集本模块大写公开常量。
- `framework/surprise/harness/ledger.py`：新增。追加式 SQLite 账本 `Ledger` / `LedgerError`。
- `framework/surprise/theory/contracts.py`：新增。`Spec`、`Hypothesis`、`TheoryEdit` 与 `EDIT_DECISIONS`。
- `framework/tests/test_surprise_contracts.py`：新增。五个契约加 `SqlCase`、`IdentityEvidence` 的往返、默认值、list 转 tuple、校验与缺键/未知键。
- `framework/tests/test_surprise_ledger.py`：新增。过滤、顺序、拒绝写入、重开、第二连接、版本号不符。

提交：`6d368c21f20e61f040ffe9721bc6a5bb22b67f37`，分支 `grok/s02-contracts`。

## 跑了哪些命令

### `python -m pytest -q testing tests`（在 `framework/`）
退出码 0

```
........................ss..................................s........... [ 55%]
.........................................................                [100%]
126 passed, 3 skipped in 1.64s
```

### `python -m surprise.gates.s02 --only contracts ledger`（在 `framework/`）
退出码 0

```
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
S02 GATE [only: contracts, ledger]: PASS (2/2 groups passed)
```

### `python -m surprise.gates.s01`（在 `framework/`）
退出码 0

```
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 126 passed (baseline 64): 126 passed, 3 skipped in 1.63s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
```

### `python -m surprise.gates.all`（在 `framework/`）
退出码 1。`contracts` 与 `ledger` 通过；`manifest`、`oracles`、`evaluate` 仍失败，因为这三组不属于本包。

```
=== gate s01 ===
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 126 passed (baseline 64): 126 passed, 3 skipped in 1.62s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
=== gate s02 ===
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[FAIL] manifest: ImportError: cannot import name 'manifest' from 'surprise.harness' (D:\CoevoDB\.worktrees\s02-contracts\framework\surprise\harness\__init__.py)
[FAIL] oracles: ModuleNotFoundError: No module named 'surprise.harness.oracles'
[FAIL] evaluate: ModuleNotFoundError: No module named 'surprise.harness.evaluate'
S02 GATE: FAIL (2/5 groups passed)
=== summary ===
s01: PASS
s02: FAIL (exit 1)
GATES: FAIL (1/2 passed)
```

### `git status --short`（提交之后，在 worktree 根）
退出码 0。无输出。

## 与说明的偏差
无。

## 未决问题
无。
