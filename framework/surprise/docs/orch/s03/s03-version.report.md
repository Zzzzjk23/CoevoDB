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
