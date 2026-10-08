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
