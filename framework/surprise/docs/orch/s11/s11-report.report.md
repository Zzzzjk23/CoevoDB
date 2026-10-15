# 报告 · s11-report

## 改了哪些文件
- `framework/surprise/experiments/grid.py`：修改。`hunter: "value"` 视为默认猎人，规范化后与省略该键相同，命令行不传 `--hunter`。
- `framework/tests/test_surprise_s11_grid.py`：修改。增加一条测试，核对 `value` 与省略 hunter 的配置和命令行一致，`random` 仍传 `--hunter random`。
- `framework/surprise/metrics/stats.py`：新增。中位数、`summarize`、Vargha–Delaney A12、双侧 Mann-Whitney U（无并列且 n≤20 用精确分布，否则用带并列与连续性修正的正态近似）。
- `framework/surprise/metrics/report.py`：新增。`python -m surprise.metrics.report` 与 `build`：只读网格，写出 `report.json`、`report.md` 和 7 张图。
- `framework/tests/test_surprise_s11_report.py`：新增。统计函数的手算值与 scipy 交叉核对，以及手工网格上的报告（含一次很短的真实 `loop.run`，和没有 `bugs.jsonl` 的被强杀旧格子）。

提交：`e823a46` `experiments(s11): accept hunter value as the omitted hunter`；`af6bfdc` `metrics(s11): report RQ1-RQ6 with Mann-Whitney and seven figures`。

## 跑了哪些命令
### `cd framework; python -m pytest -q testing tests`
退出码：0

```
........................ss..................................s........... [  7%]
........................................................................ [ 15%]
........................................................................ [ 23%]
........................................................................ [ 31%]
........................................................................ [ 39%]
........................................................................ [ 47%]
........................................................................ [ 55%]
........................................................................ [ 62%]
........................................................................ [ 70%]
........................................................................ [ 78%]
........................................................................ [ 86%]
........................................................................ [ 94%]
....................................................                     [100%]
913 passed, 3 skipped in 244.84s (0:04:04)
```

### `cd framework; python -m surprise.gates.s11 --only stats grid`
退出码：0

```
[PASS] stats: exact and asymptotic MWU (scipy agrees), A12, median, summarize as hand-computed (1s)
[PASS] grid: 2 arms x 2 seeds in 4.0 min, resumed, report and 7 figures in one command; median families/hour {'surprise': 29.887242904332677, 'old': 29.92457998383876}; p 1.0, A12 0.375 (247s)
S11 GATE [only: stats, grid]: PASS (2/2 groups passed)
```

## 与说明的偏差
无。第 1 轮返工已把“缺 `bugs.jsonl`”放进 `old_metrics`，报告不再自建临时目录。

## 未决问题
- `--dedup` / `--coverage` 与 `GRID_DIR/extras/` 下的同名文件同时存在时，命令行的文件覆盖网格里的文件。两边都没有则报告里不出现 `extras` 键。

## 第 1 轮返工
审查意见要求两处改动，都已做。提交 `c668fbe`。

- `framework/surprise/metrics/rq.py`：修改。`run_dir` 存在但没有 `bugs.jsonl` 时报告列表为空；`run_dir` 不存在仍报错。`rq2` 增加 `mean_surprise`，等于 `_surprise` 非空的记录的平均惊讶，没有这样的记录为 None。
- `framework/surprise/metrics/report.py`：修改。删掉临时目录，直接调用 `old_metrics`。`mean_surprise` 进入 RQ2 汇总与检验，配对表读这个字段，冻结对比的 `delta` 也带上它。
- `framework/tests/test_surprise_s11_metrics.py`：修改。缺 `bugs.jsonl` 时期望家族数 0、每小时 0、重复率 None；校准夹具上 `mean_surprise` 与手算的 `-log2` 平均一致。
- `framework/tests/test_surprise_s11_report.py`：修改。配对臂两格用带 `p_t` 的账本，`mean_surprise` 汇总 n 为 2，中位数等于手算值。

### `cd framework; python -m pytest -q testing tests`
退出码：0

```
........................ss..................................s........... [  7%]
........................................................................ [ 15%]
........................................................................ [ 23%]
........................................................................ [ 31%]
........................................................................ [ 39%]
........................................................................ [ 47%]
........................................................................ [ 54%]
........................................................................ [ 62%]
........................................................................ [ 70%]
........................................................................ [ 78%]
........................................................................ [ 86%]
........................................................................ [ 94%]
.....................................................                    [100%]
914 passed, 3 skipped in 226.88s (0:03:46)
```

### `cd framework; python -m surprise.gates.s11 --only stats runmetrics vocabulary grid`
退出码：0

```
[PASS] stats: exact and asymptotic MWU (scipy agrees), A12, median, summarize as hand-computed (1s)
[PASS] runmetrics: 31 records, 1 ledger families, Brier 0.2194, 1 high-surprise records, invalid 14, theory length 193.0; all recomputed (28s)
[PASS] vocabulary: run_registry, new_families, compare, recall.score, RunData and run_metrics all read the run's vocabulary (9s)
[PASS] grid: 2 arms x 2 seeds in 4.1 min, resumed, report and 7 figures in one command; median families/hour {'surprise': 29.890769662243766, 'old': 29.93901925750707}; p 1.0, A12 0.375 (246s)
S11 GATE [only: stats, runmetrics, vocabulary, grid]: PASS (4/4 groups passed)
```
