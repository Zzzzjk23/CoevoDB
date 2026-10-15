# 审查意见 · s11-report · 第 1 轮

结论：返工一轮，两处小改。你交付的统计、报告、图与 `hunter: "value"` 修正都保留不动；门槛 `stats`、`grid` 两组在编排者这边也复核过。

## 1. 旧系统格子缺 `bugs.jsonl`：在 `old_metrics` 里处理，删掉报告里的临时目录

你在报告里用临时目录补一份空 `bugs.jsonl` 再调 `old_metrics`，绕开了 `FileNotFoundError`。这件事属于 `old_metrics` 本身：`old_no_llm` 已经约定"被强杀时 `bugs.jsonl` 可能还没创建，记 0 条报告"。

- 改 `framework/surprise/metrics/rq.py` 的 `old_metrics`：`old_run.json` 指向的 `run_dir` 下没有 `bugs.jsonl` 时，报告列表为空（与 `old_no_llm.run` 记 `reports: 0` 的口径一致）；`run_dir` 本身不存在仍然报错。其余逻辑一个字都不改。
- 删掉 `framework/surprise/metrics/report.py` 里 `_old_cell_metrics` 的临时目录分支（以及不再需要的 `tempfile` 导入），直接调用 `old_metrics`。
- 在 `framework/tests/test_surprise_s11_metrics.py` 加一条测试：没有 `bugs.jsonl` 的旧运行目录，`family_count == 0`、`families_per_hour == 0.0`、`duplicate_rate is None`。

## 2. `run_metrics` 加 `rq2.mean_surprise`，报告的配对表用它

`_mean_surprise` 现在恒为 None，配对表的 `mean_surprise` 一栏没有内容。

- `framework/surprise/metrics/rq.py` 的 `run_metrics`：`rq2` 加一个键 `"mean_surprise"`，= 有效记录（`y` 是 pass / fail、`p_t` 在 (0, 1) 内，即现有 `_surprise` 返回非 None 的记录）惊讶的平均值；没有这样的记录为 None。`rq2` 其余键不变。
- `report.py`：`_mean_surprise` 读这个字段；把 `mean_surprise` 加进 rq2 的标量指标表（`RQ_METRICS["rq2"]`），这样它也进汇总与检验；`freezing` 的 `delta` 也加上 `mean_surprise`。
- 测试：`run_metrics` 的 `mean_surprise` 与手算一致（可以用已有的短跑夹具）；报告里配对臂的 `mean_surprise` 汇总不再是 n = 0。

## 允许改动的路径（本轮）

```allow-paths
framework/surprise/metrics/report.py
framework/surprise/metrics/rq.py
framework/tests/test_surprise_s11_report.py
framework/tests/test_surprise_s11_metrics.py
```

其余照原说明：不改 `gates/`、`docs/`、harness，不新增 skip / xfail，不放宽断言。

## 验收

```powershell
cd framework
python -m pytest -q testing tests                                   # 0 failed
python -m surprise.gates.s11 --only stats runmetrics vocabulary grid   # 四组 PASS
```

更新 `.orch/report.md`（追加"第 1 轮返工"一节：改了什么、命令与输出末 20 行），提交到当前分支。
