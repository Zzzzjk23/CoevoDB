# 报告 · s11-fixes

## 改了哪些文件
- `framework/surprise/theory/store.py`：`os.replace` 遇到 `PermissionError` 时按 `_REPLACE_ATTEMPTS` / `_REPLACE_DELAYS` 重试，最后一次仍失败则原样抛出。
- `framework/surprise/experiments/loop.py`：运行异常先写入 `error.txt`，再写报告；写报告失败时追加 traceback 并抛出原始异常。
- `framework/surprise/roles/constants.py`：新增 `REQUEST_DEADLINE_S = 600.0`，由现有 `as_dict()` 带出。
- `framework/surprise/roles/transport.py`：`DeepSeekTransport` 接受 `deadline_s`，流式读取并在总时限到达时抛 `TransportError("DeadlineExceeded")`。
- `framework/surprise/metrics/dups.py`：新增 `run_registry`；`new_families` / `compare` 用运行词表打开理论。
- `framework/surprise/metrics/recall.py`：`score` 与命令行 `score --run` 接受/读取运行词表。
- `framework/tests/test_surprise_s11_fixes.py`：四处修复的测试（存储重试与最终失败、两种 loop 异常、三种本地服务器、带词表的 `new_families` / `compare` / `score`）。

## 跑了哪些命令

### `cd framework; python -m pytest -q testing tests`
退出码：0

```
........................ss..................................s........... [  9%]
........................................................................ [ 18%]
........................................................................ [ 27%]
........................................................................ [ 36%]
........................................................................ [ 45%]
........................................................................ [ 55%]
........................................................................ [ 64%]
........................................................................ [ 73%]
........................................................................ [ 82%]
........................................................................ [ 91%]
.................................................................        [100%]
782 passed, 3 skipped in 182.24s (0:03:02)
```

### `cd framework; python -m surprise.gates.s11 --only store loop_error deadline`
退出码：0

```
[PASS] store: 6 replace calls for 3 transient failures (0.36s); a lasting failure raises PermissionError (2s)
[PASS] loop_error: original exception kept and written to error.txt (both, drive) (1s)
[PASS] deadline: normal answer passes; deadline 1.5s held (trickle 2.0s, silent 2.0s); errors booked, not cached (9s)
S11 GATE [only: store, loop_error, deadline]: PASS (3/3 groups passed)
```

### `cd framework; python -m surprise.gates.s11 --only vocabulary`
退出码：1

```
[FAIL] vocabulary: ModuleNotFoundError: No module named 'surprise.metrics.rundata'
S11 GATE [only: vocabulary]: FAIL (0/1 groups passed)
```

`surprise.metrics.dups` 与 `surprise.metrics.recall` 已成功导入；失败发生在随后的 `surprise.metrics.rundata` 导入（该组把 rundata 放在 dups/recall 的功能检查之前）。这是另一个包的交付物。

### `cd framework; python -m surprise.gates.s08 --only no_llm constants scoring operators candidates lanes determinism`
退出码：0

```
[PASS] no_llm: hunter, metrics, baselines, diagnoser and the loop import no model client and no old agent (0s)
[PASS] constants: 12 hunter and 2 diagnoser constants as planned; BETA = 1.0 (pre-experiment families per run: {'0.5': {'9001': 1, '9002': 3, '9003': 3}, '1.0': {'9001': 3, '9002': 3, '9003': 3}, '2.0': {'9001': 3, '9002': 3, '9003': 3}, '4.0': {'9001': 3, '9002': 5, '9003': 1}}) (0s)
[PASS] scoring: U untested 0.498 bits, adjacent 0.758; pending 0.455 after 50 probes, adjacent unexplored 1.365 at beta 2, confirmed 0 (0s)
[PASS] operators: 29 mutants of a three-statement case (4 deletions); oracle options filtered as planned (0s)
[PASS] candidates: after F1 and DF-A: {'refine': 4, 'generalize': 4, 'migrate': 2, 'explore': 81} candidates, all traceable; chose refine at 0.909 (14s)
[PASS] lanes: 32 records; executed {'bootstrap': 2, 'explore': 23, 'generalize': 3, 'refine': 4}; offered {'refine': 30, 'generalize': 31, 'migrate': 139, 'explore': 2474}; 4 families opened, 2 edits (58s)
[PASS] determinism: seed 31 twice in separate processes: 26 identical rows, labels and final theory; seed 32 differs (33s)
S08 GATE [only: no_llm, constants, scoring, operators, candidates, lanes, determinism]: PASS (7/7 groups passed)
```

### `cd framework; python -m surprise.gates.s10 --only constants frame switches`
退出码：0

```
[PASS] constants: 35 S10 constants as planned, S9 constants unchanged, library constants ['LIBRARY_ENV', 'LIBRARY_KINDS', 'LIBRARY_MIN_REFERENCES', 'LIBRARY_RULE_PREFIX', 'LIBRARY_SCHEMA'] (0s)
[PASS] frame: prior moves U 0.498 -> 1.000; extra rules offered; prepare once per round (1 rounds); vocabulary run extracts ast:set_op:except_all_two_tables (17s)
[PASS] switches: all on: calls {'implementer': 4, 'conjecturer': 1, 'prior': 3, 'translator': 1, 'vocab_inventor': 1, 'oracle_inventor': 1}; each role off: no call, no ledger line, plugin module not loaded (127s)
S10 GATE [only: constants, frame, switches]: PASS (3/3 groups passed)
```

## 与说明的偏差
`run_registry` 在 `config.json` 不存在时返回 `None`（与没有 `"vocabulary"` 键相同）。S8 现有测试的假运行目录只有 `theory/`，没有 `config.json`；真实运行总有该文件。

## 未决问题
无
