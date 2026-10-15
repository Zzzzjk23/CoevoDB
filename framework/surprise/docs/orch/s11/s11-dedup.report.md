# 报告 · s11-dedup

## 改了哪些文件
- `framework/surprise/metrics/dedup.py`：新增。`compare_dedup` 与命令行。只读运行目录，比较 σ 与执行前成员检验。
- `framework/surprise/metrics/coverage.py`：新增。`select` / `replay` / `compare` 与两条命令。重放上游回归种子，不写账本。
- `framework/tests/test_surprise_s11_dedup.py`：新增。一次 F1 引导、再选 2 条的真实 `loop.run`，核对每个字段与汇总、只读、`reprofile=False`、版本不符。
- `framework/tests/test_surprise_s11_coverage.py`：新增。`select` 的次序与 limit，3 条种子、1 个 oracle 的 `replay`（两次相同，并与直接 `certify` 对过），`compare` 的三张清单。

提交：`0f4558e`，分支 `grok/s11-dedup`。`git status` 干净。

## 跑了哪些命令

命令在 `framework/` 下执行。

### `python -m pytest -q tests/test_surprise_s11_coverage.py --tb=short`

退出码：0

```
....                                                                     [100%]
4 passed in 4.37s
```

### `python -m pytest -q tests/test_surprise_s11_dedup.py --tb=line`

退出码：0

```
.....                                                                    [100%]
5 passed in 6.76s
```

### `python -m surprise.gates.s11 --only dedup`

退出码：0

```
[PASS] dedup: 3 failures, 1 true duplicates; sigma p/r 1.0/1.0, membership p/r None/0.0 (33s)
S11 GATE [only: dedup]: PASS (1/1 groups passed)
```

### `python -m surprise.gates.s11 --only coverage`

退出码：0

```
[PASS] coverage: 4 upstream regression seeds x 2 oracles on 1.5.5 and 1.1.3; {'plan_variant': {'old': {'pass': 4}, 'new': {'pass': 4}, 'fail_old_pass_new': [], 'fail_both': [], 'fail_new_only': []}, 'equivalent_query': {'old': {'invalid': 4}, 'new': {'invalid': 4}, 'fail_old_pass_new': [], 'fail_both': [], 'fail_new_only': []}} (7s)
S11 GATE [only: coverage]: PASS (1/1 groups passed)
```

### `python -m pytest -q testing tests --tb=line`

退出码：0

进度行是 pytest 的点（带颜色码），这里只留百分比和结尾：

```
[  8%]
[ 17%]
[ 26%]
[ 34%]
[ 43%]
[ 52%]
[ 61%]
[ 69%]
[ 78%]
[ 87%]
[ 96%]
[100%]
820 passed, 3 skipped in 230.15s (0:03:50)
```

3 个 skip 是原有测试。本包没有新增 skip / xfail，没有删断言。新测试 9 条（dedup 5，coverage 4）。

## 与说明的偏差
- 每一行的 `error_class` 都取账本里那条失败自己的 `identity.error_class`，包括离线重画像的行。门槛 `check_dedup` 对每一行都拿这个字段和账本标签比。重画像时 `truth_key` 仍用新标签算（`label_key` 的口径）。σ 的候选 `notes` 用行里的这个字段，与门槛自己调用 `SignatureEngine._signature` 的算法一致。若新标签的错误类别与账本不同，身份键用新的，行上显示的类别和 σ 的 notes 用账本的。这次 dedup 门槛通过了。
- `attribution_executions` 放在返回值顶层，不放进 `membership`。`membership.executions` 是 0。这个和是各行账本标签 `cve["attribution"]["executions"]` 之和；缺这个字段、或不是整数，记 0。不取离线重画像的新标签：重画像是 `certify(..., diagnose=True)`，不传 hypothesis，新标签的归属测试是 `not_requested`。成员检验的执行成本是运行当时记在账本上的那一次。
- `replay(seeds, oracles, *, prefix=None, limit=None)` 比说明多了两个关键字参数，用来把本次选择写进结果；不传就是 null。命令行总会把 `--prefix` / `--limit` 传进去。`compare` 在 `engine`、`prefix`、`limit`、`oracles` 不一致，或两边种子下标对不上时抛 `ValueError`。门槛给出的两份结果是同一选择，不受影响。

σ 用 `SignatureEngine(runner_factory=lambda: None, checker=None)`，引擎名保持默认的 `duckdb`，与说明里的调用和门槛一致。

## 未决问题
无。
