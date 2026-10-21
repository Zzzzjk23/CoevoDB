# s16-testfix 执行报告

## 改动文件

- `framework/tests/test_surprise_s03_registry.py`
  - `test_implemented_is_the_seven_plan_ids` 的目标引擎元组加入 `postgres`。
  - `test_sound_oracles_pass_on_both_target_engines` 显式遍历 `("duckdb", "datafusion")`，添加一行注释说明 PostgreSQL 检查位于 S16 测试和门槛，每次运行需要自己的实例。
  - 其余测试和断言保持原样。
- 已提交到当前分支 `grok/s16-testfix`，提交 `4ffacb9`。
- 本报告不入库；未改动其他受版本控制的文件。

## 验收命令

以下三条命令均在 `framework/` 下运行，输出不足 20 行时完整保留。

### python -m pytest -q tests/test_surprise_s03_registry.py

退出码：0

```text
..........                                                               [100%]
10 passed in 1.52s
```

### python -m pytest -q testing tests

退出码：0

输出最后 20 行原样：

```text
........................................................................ [ 10%]
........................................................................ [ 15%]
........................................................................ [ 20%]
........................................................................ [ 26%]
........................................................................ [ 31%]
........................................................................ [ 36%]
........................................................................ [ 41%]
........................................................................ [ 46%]
........................................................................ [ 52%]
........................................................................ [ 57%]
........................................................................ [ 62%]
........................................................................ [ 67%]
........................................................................ [ 72%]
........................................................................ [ 78%]
........................................................................ [ 83%]
........................................................................ [ 88%]
........................................................................ [ 93%]
........................................................................ [ 99%]
.............                                                            [100%]
1378 passed, 3 skipped in 830.86s (0:13:50)
```

### python -m surprise.gates.s03

退出码：0

```text
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
[PASS] local: ART exercised, injected mismatch caught; 3 proved rules x 2 engines incl NULL; untrusted pairs rejected
[PASS] cross: PG16 + DuckDB witness DF-A/DF-B; insufficient quorum, ties, multiple outliers and engine aliases rejected
[PASS] version: F2 old/new measured bags and regression direction; both old venvs work; directionless mismatch invalid
[PASS] matrix: 7 oracles x 2 engines, 14 ledger records, no hidden harness failures, manifest verified
S03 GATE: PASS (5/5 groups passed)
```

## 提交与检查

以下命令在 worktree 根目录运行。

### git diff --check

退出码：0；无输出（提交前及提交后均检查）。

### git add -- framework/tests/test_surprise_s03_registry.py

退出码：0；无输出。

### git commit -m "test: align S03 registry checks with PostgreSQL target"

退出码：0

```text
[grok/s16-testfix 4ffacb9] test: align S03 registry checks with PostgreSQL target
 1 file changed, 3 insertions(+), 2 deletions(-)
```

### git status --short

退出码：0；无输出，工作区干净。

### git check-ignore .orch/report.md

退出码：0

```text
.orch/report.md
```

## 与说明的偏差

无。只修改授权的两个测试位置，未新增 skip / xfail，未改循环体断言。

## 未决问题

无。

