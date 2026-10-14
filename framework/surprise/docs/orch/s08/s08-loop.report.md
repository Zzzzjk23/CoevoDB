# 报告 · s08-loop

## 改了哪些文件
- `framework/surprise/diagnoser/constants.py`：新增。`COMPRESS_EVERY = 100`、`CHECKPOINT_EVERY = 100`，各一行注释，`as_dict()`。
- `framework/surprise/diagnoser/diagnoser.py`：新增。`Diagnoser.after` 在最小化复现上收紧 S 并交给工作台；`periodic` 按节拍调用 `compress` 与 `checkpoint`。
- `framework/surprise/diagnoser/__init__.py`：修改。导出 `constants` 与 `Diagnoser`。
- `framework/surprise/experiments/loop.py`：新增。主循环 `run` / `main`，以及与门槛相同的 `code_digests()`。
- `framework/tests/test_surprise_s08_loop.py`：新增。Diagnoser、参数错误、短跑、时间上限、两个进程的确定性。

`framework/surprise/experiments/__init__.py` 未改，也没有导入 `loop`。

提交：`5ee75d3` `feat(s08-loop): Diagnoser and the closed loop without an LLM`，分支 `grok/s08-loop`。

## 跑了哪些命令

### `cd framework; python -m pytest -q testing tests`
退出码：0

```
........................ss..................................s........... [ 11%]
........................................................................ [ 23%]
........................................................................ [ 35%]
........................................................................ [ 46%]
........................................................................ [ 58%]
........................................................................ [ 70%]
........................................................................ [ 82%]
........................................................................ [ 93%]
.....................................                                    [100%]
610 passed, 3 skipped in 113.87s (0:01:53)
```

### `cd framework; python -m surprise.gates.s08 --only no_llm scoring operators candidates lanes determinism`
退出码：0

```
[PASS] no_llm: hunter, metrics, baselines, diagnoser and the loop import no model client and no old agent (0s)
[PASS] scoring: U untested 0.498 bits, adjacent 0.758; pending 0.455 after 50 probes, adjacent unexplored 1.365 at beta 2, confirmed 0 (0s)
[PASS] operators: 29 mutants of a three-statement case (4 deletions); oracle options filtered as planned (0s)
[PASS] candidates: after F1 and DF-A: {'refine': 4, 'generalize': 4, 'migrate': 2, 'explore': 81} candidates, all traceable; chose refine at 0.909 (11s)
[PASS] lanes: 32 records; executed {'bootstrap': 2, 'explore': 24, 'generalize': 3, 'refine': 3}; offered {'refine': 39, 'generalize': 23, 'migrate': 156, 'explore': 2555}; 3 families opened, 2 edits (45s)
[PASS] determinism: seed 31 twice in separate processes: 26 identical rows, labels and final theory; seed 32 differs (30s)
S08 GATE [only: no_llm, scoring, operators, candidates, lanes, determinism]: PASS (6/6 groups passed)
```

### `cd framework; python -m surprise.gates.s08 --only constants`
退出码：1

```
[FAIL] constants: s08_runs.json is not written yet: the orchestrator pins the artifacts after running them
S08 GATE [only: constants]: FAIL (0/1 groups passed)
```

### `cd framework; python -m surprise.gates.all`
退出码：1（s08 的五组预期失败；s01–s07 全部 PASS）

```
[PASS] scoring: U untested 0.498 bits, adjacent 0.758; pending 0.455 after 50 probes, adjacent unexplored 1.365 at beta 2, confirmed 0 (0s)
[PASS] operators: 29 mutants of a three-statement case (4 deletions); oracle options filtered as planned (0s)
[PASS] candidates: after F1 and DF-A: {'refine': 4, 'generalize': 4, 'migrate': 2, 'explore': 81} candidates, all traceable; chose refine at 0.909 (11s)
[PASS] lanes: 32 records; executed {'bootstrap': 2, 'explore': 24, 'generalize': 3, 'refine': 3}; offered {'refine': 39, 'generalize': 23, 'migrate': 156, 'explore': 2555}; 3 families opened, 2 edits (44s)
[PASS] determinism: seed 31 twice in separate processes: 26 identical rows, labels and final theory; seed 32 differs (29s)
[FAIL] longrun: s08_runs.json is not written yet: the orchestrator pins the artifacts after running them
[FAIL] sawtooth: s08_runs.json is not written yet: the orchestrator pins the artifacts after running them
[FAIL] duplicates: s08_runs.json is not written yet: the orchestrator pins the artifacts after running them
[FAIL] recall: s08_runs.json is not written yet: the orchestrator pins the artifacts after running them
S08 GATE: FAIL (6/11 groups passed)
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

s08 在 `gates.all` 里失败的五组是 `constants`、`longrun`、`sawtooth`、`duplicates`、`recall`，原因都是 `s08_runs.json is not written yet`。`no_llm` 在这组输出的上一行，也是 PASS。

## 与说明的偏差
- `run` 比说明里的签名多一个关键字参数 `echo`（默认 `False`）。命令行传入 `True`，每条实验向 stdout 打一行 `{seq} {lane} {oracle} {y} {惊讶或 -} {triage}`，结束时再打 `{status} {experiments}`。库调用不传则不打印。失败或中断时另向 stderr 打一行 `error: ...`，stdout 仍只补打已写入的报告状态与条数。
- 报告的 `edits` 按编辑的最后状态分成三档。验收拒绝的提议在日志里的 `decision` 是 `rolled_back`，且 `payload.rollback` 为 null，报告把它计为 `rejected`。先接受、后来撤回的（`payload.rollback` 有记录）计为 `rolled_back`。`progress.jsonl` 里的 `decision` 仍是日志里的原值。
- `config.json` 的键是 `seed`、`engines`、`oracles`、`max_experiments`、`max_minutes`、`beta`（实际使用的值）、`bootstrap`（规范化后的列表）、`run_id`。

## 未决问题
无。
