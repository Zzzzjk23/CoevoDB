# 报告 · s15-rundata

分支：`grok/s15-rundata`；提交：`564b602`。
接续上一位执行者留下的 5 个文件，保留可用的流式聚合、延迟物化、SQLancer 和去重改动，修复指标公式并替换大 JSON 的固定头尾截取实现。

## 改了哪些文件

- `framework/surprise/metrics/rundata.py`（修改）：只读读取元数据和 COUNT，按 seq 流式读取，records 首次访问才缓存；识别三种 kind；对指标扫描中的超大 detail 使用只读 SQLite Blob 分块定位和省略，保留默认完整记录迭代。
- `framework/surprise/metrics/rq.py`（修改）：一遍扫描仅保留指标所需字段和数值；恢复 Brier 参考值 rate * (1-rate)，保持全部既有指标结果；SQLancer 执行数取 report，缺失时传播 None。
- `framework/surprise/metrics/dedup.py`（修改）：从迭代器筛选并仅保存失败记录，顺序和结果不变。
- `framework/surprise/metrics/curve.py`（修改）：按流累计完整窗口，保留丢弃尾窗和原有浮点求和顺序。
- `framework/tests/test_surprise_s15_rundata.py`（新增）：13 项测试，覆盖顺序/内容、延迟读取、文件不变、kind、旧实现完整输出、SQLancer、dedup、空账本、兼容属性不被指标路径使用，以及跨块转义/UTF-8/嵌套同名字段。

测得峰值：9500 条记录为 **358 MB**，翻倍至 19000 条后增加 **42 MB**（约 400 MB；门槛输出取整）。上限分别为 800 MB 和 120 MB。输出 SHA256 为 `2a6310744d89e0075ee14f4fac94a961093b9644e65b1ed118adbc87b56c458d`，与冻结值一致。

## 跑了哪些命令

Python 验证命令在 `framework/` 执行；git 命令在 worktree 根执行。最终测试日志由 PowerShell 的 `2>&1 | Tee-Object -FilePath ../.orch/tmp/<日志名>; exit $LASTEXITCODE` 留存，目录未清理。以下逐次给出退出码与输出末 20 行；不足 20 行时全部贴出。

### 首次检查继承改动

命令：`python -m pytest -q tests/test_surprise_s15_rundata.py`  
退出码：`1`

```text
        }
        assert got["run"]["experiments"] == len(records)
        assert got["rq1"]["executions"] == len(records)
        assert got["rq1"]["families"] == ledger_families(records, data.progress)
        assert got["rq1"]["family_count"] == 1
        assert got["rq1"]["families"][0]["elapsed_s"] == 1.5
        assert got["rq1"]["families"][0]["seq"] == 1
        assert got["rq1"]["duplicate_rate"] == duplicate_rate(_profiled_keys(records))
        assert got["rq1"]["theory_families"] is None
        assert got["rq1"]["families_per_1000"] == 1000.0 / len(records)
        brier, reference = _brier(records)
        assert got["rq2"]["valid"] == len(_valid(records))
        assert got["rq2"]["brier"] == brier
>       assert got["rq2"]["brier_reference"] == reference
E       assert 0.6 == 0.24

tests\test_surprise_s15_rundata.py:259: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_surprise_s15_rundata.py::test_run_metrics_matches_the_materialized_helpers
1 failed, 5 passed in 0.98s
```

发现继承改动的 Brier 参考值错误，已恢复原公式；原断言保留。

### 修复继承改动后

命令：`python -m pytest -q tests/test_surprise_s15_rundata.py`  
退出码：`0`

```text
......                                                                   [100%]
6 passed in 1.06s
```

### 新增完整基准对照时

命令：`python -m pytest -q tests/test_surprise_s15_rundata.py`  
退出码：`1`

```text
                "executions": 7,
                "wall_s": 3600.0,
                "llm_calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "usd": None,
                "per_family": {
                    "executions": 7.0,
                    "llm_calls": 0.0,
                    "tokens": 0.0,
                    "usd": None
                }
            }
        }
E       NameError: name 'true' is not defined

tests\test_surprise_s15_rundata.py:525: NameError
=========================== short test summary info ===========================
FAILED tests/test_surprise_s15_rundata.py::test_run_metrics_matches_complete_pre_s15_output
1 failed, 12 passed in 1.64s
```

新增基准字典有 true/false 字面量笔误，已改为 Python 的 True/False；未删除或放宽断言。

### 最终定向测试

命令：`python -m pytest -q tests/test_surprise_s15_rundata.py`  
退出码：`0`

```text
.............                                                            [100%]
13 passed in 1.57s
```

### 完整测试

命令：`python -m pytest -q testing tests`  
退出码：`0`

```text
........................ss..................................s........... [  7%]
........................................................................ [ 15%]
........................................................................ [ 22%]
........................................................................ [ 30%]
........................................................................ [ 37%]
........................................................................ [ 45%]
........................................................................ [ 52%]
........................................................................ [ 60%]
........................................................................ [ 68%]
........................................................................ [ 75%]
........................................................................ [ 83%]
........................................................................ [ 90%]
........................................................................ [ 98%]
...............                                                          [100%]
948 passed, 3 skipped in 338.35s (0:05:38)
```

3 个 skip 来自既有测试，本包未新增 skip / xfail。

### S15 流式门槛

命令：`python -m surprise.gates.s15 --only stream`  
退出码：`0`

```text
[PASS] stream: same metrics as before S15 on 9500 records; peak 358 MB (before: 3.3 GB on 8600); doubled ledger adds 42 MB (327s)
S15 GATE [only: stream]: PASS (1/1 groups passed)
```

### S11 指定门槛

命令：`python -m surprise.gates.s11 --only runmetrics llm_metrics rq6 dedup coverage pure_llm grid`  
退出码：`0`

```text
[PASS] runmetrics: 31 records, 1 ledger families, Brier 0.2194, 1 high-surprise records, invalid 14, theory length 193.0; all recomputed (36s)
[PASS] llm_metrics: 15 experiments replayed; 2 conjectures, survival 0.0, accuracy 0.7142857142857143 over 7 settled bets; families via {'implement': 0, 'bet': 1, 'translate': 0, 'llm_rule': 0, 'invented_feature': 0}; 23 calls (52s)
[PASS] rq6: classify, F2 fix conditions (1 entries), pair agreement as hand-computed; F2 hypothesis too_narrow (missing [], extra 9 literals); recall 0.5 (6s)
[PASS] dedup: 3 failures, 1 true duplicates; sigma p/r 1.0/1.0, membership p/r None/0.0 (8s)
[PASS] coverage: 4 upstream regression seeds x 2 oracles on 1.5.5 and 1.1.3; {'plan_variant': {'old': {'pass': 4}, 'new': {'pass': 4}, 'fail_old_pass_new': [], 'fail_both': [], 'fail_new_only': []}, 'equivalent_query': {'old': {'invalid': 4}, 'new': {'invalid': 4}, 'fail_old_pass_new': [], 'fail_both': [], 'fail_new_only': []}} (9s)
[PASS] pure_llm: 16 cases from 4 cached calls replayed identically; labels {'pass': 15, 'invalid': 1}; 0 families (9s)
[PASS] grid: 2 arms x 2 seeds in 4.1 min, resumed, report and 7 figures in one command; median families/hour {'surprise': 29.828751645366374, 'old': 29.92434905114654}; p 1.0, A12 0.375 (247s)
S11 GATE [only: runmetrics, llm_metrics, rq6, dedup, coverage, pure_llm, grid]: PASS (7/7 groups passed)
```

### 提交

命令：`git commit -m "metrics(s15): stream run ledgers and preserve metric outputs"`  
退出码：`0`

```text
[grok/s15-rundata 564b602] metrics(s15): stream run ledgers and preserve metric outputs
 5 files changed, 1144 insertions(+), 61 deletions(-)
 create mode 100644 framework/tests/test_surprise_s15_rundata.py
```

### 最终检查

命令：`git status --short; git diff --check; git rev-parse --short HEAD; git branch --show-current`  
退出码：`0`

```text
564b602
grok/s15-rundata
```

git status --short 与 git diff --check 均无输出；工作树干净。

## 与说明的偏差

实现扩展：`iter_records` 增加可选参数 `keep_detail=False`，仅供 `run_metrics` 使用。验收账本有一条约 483 MB 的 JSON；指标不读取 label.detail，而整条解析会产生很高的瞬时内存。因此该模式对大于 32 MiB 的记录使用只读 Blob 分块扫描，只省略 label.detail，再交给 ExperimentRecord.from_json。它不依赖键顺序或固定头尾长度。默认 `iter_records()`、兼容属性 `records` 和 dedup 仍读取完整记录；全部指标 SHA256 不变。没有会话范围或允许路径之外的代码改动。

未改 harness、门槛、文档、旧逻辑和 metrics/report.py；未新增依赖，未打 tag、合并、rebase、push 或切换分支。未自行复制/链接主检出区 framework/results；翻倍账本由指定门槛自身在临时目录构造。

## 未决问题

无。

