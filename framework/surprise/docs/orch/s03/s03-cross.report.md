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
