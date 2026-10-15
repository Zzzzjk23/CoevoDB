# 报告 · s11-runmetrics

## 改了哪些文件
- `framework/surprise/metrics/constants.py`：新增。七个指标常数和 `as_dict()`，元组保持为元组。
- `framework/surprise/metrics/rundata.py`：新增。只读打开一个运行目录（配置、报告、progress、唯一账本、按运行词表打开的理论、`llm/` 账本）。
- `framework/surprise/metrics/rq.py`：新增。`label_key`、`ledger_families`、`theory_lengths`、`ciao`、`run_metrics`、`old_metrics`。
- `framework/surprise/metrics/boundary.py`：新增。`classify`、`load_fix_conditions`、`compare`。
- `framework/surprise/metrics/partition.py`：新增。`pair_agreement`（含调整兰德指数，分母为 0 时为 None）。
- `framework/surprise/metrics/data/fix_conditions.json`：新增。说明里的那一条 F2，未改字、未加条目。
- `framework/tests/test_surprise_s11_metrics.py`：新增。手算例子、300 条合成观察的 CIAO、一次 `max_experiments=0` 的真实 `loop.run`，以及打开前后的目录哈希。

## 跑了哪些命令

命令在 `framework/` 下执行。

### `python -m pytest -q tests/test_surprise_s11_metrics.py --tb=line`

退出码：0

```
...............                                                          [100%]
15 passed in 8.29s
```

### `python -m surprise.gates.s11 --only runmetrics llm_metrics rq6`

退出码：0

```
[PASS] runmetrics: 31 records, 1 ledger families, Brier 0.2194, 1 high-surprise records, invalid 14, theory length 193.0; all recomputed (26s)
[PASS] llm_metrics: 15 experiments replayed; 2 conjectures, survival 0.0, accuracy 0.7142857142857143 over 7 settled bets; families via {'implement': 0, 'bet': 1, 'translate': 0, 'llm_rule': 0, 'invented_feature': 0}; 23 calls (35s)
[PASS] rq6: classify, F2 fix conditions (1 entries), pair agreement as hand-computed; F2 hypothesis too_narrow (missing [], extra 9 literals); recall 0.5 (4s)
S11 GATE [only: runmetrics, llm_metrics, rq6]: PASS (3/3 groups passed)
```

### `python -m surprise.gates.s11 --only constants`

退出码：1

```
[FAIL] constants: roles constant REQUEST_DEADLINE_S must be 600.0, got None
S11 GATE [only: constants]: FAIL (0/1 groups passed)
```

metrics 常数在这条失败之前已经核对过。失败文本是 `roles constant`，没有 `metrics constant`。`surprise.baselines.pure_llm` 还没被导入：角色常数先失败，组就停了。

### `python -m pytest -q testing tests`

退出码：0

```
........................ss..................................s........... [  9%]
........................................................................ [ 18%]
........................................................................ [ 27%]
........................................................................ [ 36%]
........................................................................ [ 45%]
........................................................................ [ 54%]
........................................................................ [ 63%]
........................................................................ [ 72%]
........................................................................ [ 81%]
........................................................................ [ 90%]
........................................................................ [100%]
789 passed, 3 skipped in 190.98s (0:03:10)
```

3 个 skip 是原有测试，本包没有新增 skip / xfail。

## 与说明的偏差
- ciao 组未在 worktree 运行。测试里用 `Workbench` 观察 300 条合成记录，每 100 条 `checkpoint`，覆盖 `theory_lengths` 和 `ciao`（多代、选代、抽样、空批）。
- `p_t` 为 0 或 1 时，高惊讶不调用 `surprise_bits`（该函数要求概率严格落在 (0, 1) 内），这两条仍进入 Brier 和校准分箱。`curve.surprise_curve` 不走这个保护：窗口不大于记录数、且记录里有端点概率时，曲线仍会抛错。短跑门槛里的预测都在 (0, 1) 内。
- `prices` 里没有某次调用的模型名时，`usd` 抛 `ValueError`。说明没有规定这种缺价。
- `arm` 不是 dict 时视为未冻结。说明写的是 `arm` 为 None 或 `arm.get("freeze") != "theory"`；非 dict 的 `arm` 若直接 `.get` 会抛错。

理论家族键在已经用本运行词表打开的 `Workbench` 上按 `dups.new_families` 的规则计算，不调用还没有 `registry=` 的 `new_families()`。`recall.score` 用 `inspect.signature` 判断，有 `registry` 参数时才传入本运行的词表。这两处按说明处理，默认词表上与现有函数的结果一致。

## 未决问题
- `constants` 组停在 `surprise.roles.constants` 的 `REQUEST_DEADLINE_S`（得到 None）。这是别的包的常数，本包未改。
- `vocabulary` 门槛后半段要等 `s11-fixes` 给 `dups.new_families` 和 `recall.score` 加上 `registry=`。本包的 `run_metrics` 在扩展词表上可以算完（`test_extended_vocabulary_opens`）。
