# 报告 · s08-eval

## 改了哪些文件
- `framework/surprise/metrics/curve.py`：新增。单条惊讶、整窗平均曲线、锯齿下标。
- `framework/surprise/metrics/dups.py`：新增。身份键、新家族、旧 `bugs.jsonl`、重复率，以及对照命令行。
- `framework/surprise/metrics/recall.py`：新增。在当前解释器里认证已知 bug，并按身份键对一次运行打分。
- `framework/surprise/baselines/old_no_llm.py`：新增。按墙钟预算子进程跑旧系统 `no_llm`，到点终止进程树。
- `framework/tests/test_surprise_s08_eval_curve.py`：新增。整窗切分、无效与没有 `p_t` 的记录、锯齿的各个条件。
- `framework/tests/test_surprise_s08_eval_dups.py`：新增。两种身份键、手工工作台、空基线与截断的最后一行、命令行。
- `framework/tests/test_surprise_s08_eval_recall.py`：新增。DuckDB 1.5.5 上认证 F1，手工工作台上的 `score`，两条命令行。
- `framework/tests/test_surprise_s08_eval_baseline.py`：新增。30 秒真跑被杀、立刻退出的假命令、非空目录与运行目录个数。

提交：`9cde3f5`（实现）、`b5a569b`（测试）。工作区干净。

## 跑了哪些命令

### `cd framework ; python -m pytest -q testing tests`
退出码 0。输出共 9 行：

```
........................ss..................................s........... [ 12%]
........................................................................ [ 25%]
........................................................................ [ 37%]
........................................................................ [ 50%]
........................................................................ [ 62%]
........................................................................ [ 75%]
........................................................................ [ 87%]
.......................................................................  [100%]
572 passed, 3 skipped in 80.72s (0:01:20)
```

### `cd framework ; python -c "import sys, surprise.metrics.curve, surprise.metrics.dups, surprise.metrics.recall, surprise.baselines.old_no_llm; bad=[m for m in ('openai','httpx','httpx2','agents','llm','guidelines','evolution.co_evolution') if m in sys.modules]; print('LLM-FREE' if not bad else bad)"`
退出码 0。

```
LLM-FREE
```

### `cd framework ; python -m surprise.gates.all`
退出码 1。S8 失败是说明里预期的（Hunter、主循环和 `s08_runs.json` 都不在本包）。s01–s07 全部 PASS。末 20 行：

```
[FAIL] candidates: AttributeError: module 'surprise.hunter' has no attribute 'Hunter'
[FAIL] lanes: the loop exits cleanly: 1 D:\CoevoDB\.venv\Scripts\python.exe: No module named surprise.experiments.loop

[FAIL] determinism: run a exits cleanly: D:\CoevoDB\.venv\Scripts\python.exe: No module named surprise.experiments.loop

[FAIL] longrun: s08_runs.json is not written yet: the orchestrator pins the artifacts after running them
[FAIL] sawtooth: s08_runs.json is not written yet: the orchestrator pins the artifacts after running them
[FAIL] duplicates: s08_runs.json is not written yet: the orchestrator pins the artifacts after running them
[FAIL] recall: s08_runs.json is not written yet: the orchestrator pins the artifacts after running them
S08 GATE: FAIL (0/11 groups passed)
=== summary ===
s01: PASS
s02: PASS
s03: PASS
s04: PASS
s05: PASS
s06: PASS
s07: PASS
s08: FAIL (exit 1)
GATES: FAIL (7/8 passed)
```

### `cd framework ; python -m surprise.baselines.old_no_llm --out ..\.orch\tmp\old-check --minutes 1 --seed 0`
退出码 0。目录留在 `.orch/tmp/old-check`。输出：

```
{
 "mode": "no_llm",
 "engine": "duckdb",
 "seed": 0,
 "minutes": 1.0,
 "started_at": "2026-10-14T18:38:35.996847+00:00",
 "finished_at": "2026-10-14T18:39:36.559692+00:00",
 "wall_s": 60.56988909999927,
 "ended": "killed",
 "returncode": 1,
 "run_dir": "results/duckdb_no_llm_20261015_053836_s08_old_s0",
 "reports": 2
}
```

## 与说明的偏差
- `run()` 在 `bugs.jsonl` 还没被创建时把 `reports` 记为 0。到点强杀时旧系统可能还没写出这个文件，这时不能调用 `old_reports`。验收的一分钟运行里文件已经存在，`reports` 为 2。
- `python -m surprise.metrics.dups` 写出的 JSON 使用 `indent=1`。说明只要求 `ensure_ascii=True`。解析后的对象不变。

## 未决问题
无。
