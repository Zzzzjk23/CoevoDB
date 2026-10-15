# 报告 · s10-harness

## 改了哪些文件
- `framework/surprise/harness/oracles/rewrites.py`：修改。增加第二层库的常数、模板检查与套用、库文件读取；`apply_rule` 在 `llm:` 前缀下查库，冻结的三条规则仍走原来的实现。
- `framework/surprise/harness/oracles/equivalent_query.py`：修改。库里的规则在目标引擎比较之前先让参照引擎对两边的结果多重集表态；参照不一致、同意数不足，或只有改写一边报错时记 `invalid / untrusted_rewrite`。冻结规则的标签不加键。
- `framework/tests/test_surprise_s10_rewrite_library.py`：新增。覆盖模板、库文件、冻结规则输出，以及第二层四种判定和 `detail` 的键。

提交：`dcf68f2`，分支 `grok/s10-harness`。

## 跑了哪些命令

按说明没有跑 `python -m surprise.gates.s04`、`python -m surprise.gates.s06` 和 `python -m surprise.gates.all`。这两道门槛里核对冻结清单的组会因哈希变化失败，冻结清单留给编排者在合并后重新生成。

### `cd framework ; python -m pytest -q tests/test_surprise_s10_rewrite_library.py -k "not real_engines"`
退出码：0

```
........                                                                 [100%]
8 passed, 1 deselected in 0.34s
```

### `cd framework ; python -m pytest -q tests/test_surprise_s10_rewrite_library.py -k real_engines`
退出码：0

```
.                                                                        [100%]
1 passed, 8 deselected in 4.60s
```

### `cd framework ; python -m surprise.gates.s10 --only library`
退出码：0

```
[PASS] library: 4 usable and 10 refused templates; 8 malformed libraries refused; judgements {'llm:wrap_sub': 'pass', 'llm:is_true': 'pass', 'llm:first_row': 'untrusted_rewrite/reference_disagrees', 'llm:octet': 'untrusted_rewrite/rewrite_error'}; frozen rule unchanged; no library, no trust (4s)
S10 GATE [only: library]: PASS (1/1 groups passed)
```

### `cd framework ; python -m surprise.gates.s02 ; python -m surprise.gates.s03 ; python -m pytest -q testing tests`
退出码：0（前一条失败则不会跑后面的）

```
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 51 files hashed (98b70d9e81fc); verify catches 3 kinds of change
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: PASS (5/5 groups passed)
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
[PASS] local: ART exercised, injected mismatch caught; 3 proved rules x 2 engines incl NULL; untrusted pairs rejected
[PASS] cross: PG16 + DuckDB witness DF-A/DF-B; insufficient quorum, ties, multiple outliers and engine aliases rejected
[PASS] version: F2 old/new measured bags and regression direction; both old venvs work; directionless mismatch invalid
[PASS] matrix: 7 oracles x 2 engines, 14 ledger records, no hidden harness failures, manifest verified
S03 GATE: PASS (5/5 groups passed)
........................ss..................................s........... [ 10%]
........................................................................ [ 20%]
........................................................................ [ 30%]
........................................................................ [ 40%]
........................................................................ [ 51%]
........................................................................ [ 61%]
........................................................................ [ 71%]
........................................................................ [ 81%]
........................................................................ [ 92%]
........................................................                 [100%]
701 passed, 3 skipped in 139.73s (0:02:19)
```

全套测试 701 通过、3 跳过（起点 692，skip 仍是 3）。上面贴的是这条命令输出的最后 20 行；第一行 `[PASS] contracts: ...` 被这 20 行截掉。

### `cd framework ; python -m surprise.gates.s10 --only frozen`
退出码：1（预期）

```
[FAIL] frozen: the harness is re-frozen (gates/s04_frozen.json): ['changed: surprise/harness/oracles/equivalent_query.py', 'changed: surprise/harness/oracles/rewrites.py', 'hash mismatch: manifest 50fa40cf2d19 current 98b70d9e81fc']
S10 GATE [only: frozen]: FAIL (0/1 groups passed)
```

失败只有这一条：相对 `s09-done-r2` 的 harness diff 只有这两个已提交文件，冻结规则的输出没有变。清单本身还是旧哈希。

## 与说明的偏差
- 占位符必须是扫描器里相邻的三个词元 `{`、名字、`}`。写在字符串里面的 `{q}` / `{p}` 整条模板不认。门槛里的可用模板都是真正的词元，这条更严的检查不影响它们。
- `_DML` 按扫描器的关键字词元判断，不按子串。字符串里的 `DELETE` 不拒绝模板；作为关键字出现的 `DELETE`、`INSERT`、`CREATE` 会拒绝。
- 参照引擎在建 runner、setup 或执行时抛出异常，记为 `skipped`，不把这次判定变成 harness 错误。setup 返回错误、或两边有一边没有成功结果，也是 `skipped`。

## 未决问题
无。
