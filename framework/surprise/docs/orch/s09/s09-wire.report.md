# 报告 · s09-wire

## 改了哪些文件
- `framework/surprise/hunter/hunter.py`：修改。`Hunter` 增加 `sources`，在四条车道之后按序追加来源候选；`choose` 把 `round` 传给接受该参数的 `candidates`，车道计数允许新车道名。
- `framework/surprise/experiments/loop.py`：修改。`run(..., llm=None)` 与 `--llm` / `--llm-cache` / `--llm-max-calls` / `--llm-offline`。`llm` 非空时惰性调用 `_build_roles`，把角色接到 Hunter、进度行、`config.json`、run manifest 和 `report.json`，并在 `_close` 里 `close()`。
- `framework/tests/test_surprise_s09_wire.py`：新增。Hunter 来源、主循环开关、命令行组合。

提交：`53d6220` `feat(s09-wire): switch LLM roles into the Hunter and the loop`，分支 `grok/s09-wire`。

## 跑了哪些命令

起点（改代码之前）：

```text
cd framework ; python -m pytest -q testing tests
```

退出码 0。输出末尾：

```text
........................ss..................................s........... [ 11%]
........................................................................ [ 22%]
........................................................................ [ 33%]
........................................................................ [ 45%]
........................................................................ [ 56%]
........................................................................ [ 67%]
........................................................................ [ 78%]
........................................................................ [ 90%]
..............................................................           [100%]
635 passed, 3 skipped in 127.38s (0:02:07)
```

实现后的全量测试：

```text
cd framework ; python -m pytest -q testing tests
```

退出码 0。输出末尾：

```text
........................ss..................................s........... [ 10%]
........................................................................ [ 21%]
........................................................................ [ 32%]
........................................................................ [ 42%]
........................................................................ [ 53%]
........................................................................ [ 64%]
........................................................................ [ 75%]
........................................................................ [ 85%]
........................................................................ [ 96%]
.......................                                                  [100%]
668 passed, 3 skipped in 135.36s (0:02:15)
```

668 = 起点 635 + 本包 33。skip 仍是 3。

```text
cd framework ; python -m surprise.gates.s08 --only no_llm scoring operators candidates lanes determinism
```

退出码 0。输出：

```text
[PASS] no_llm: hunter, metrics, baselines, diagnoser and the loop import no model client and no old agent (0s)
[PASS] scoring: U untested 0.498 bits, adjacent 0.758; pending 0.455 after 50 probes, adjacent unexplored 1.365 at beta 2, confirmed 0 (0s)
[PASS] operators: 29 mutants of a three-statement case (4 deletions); oracle options filtered as planned (0s)
[PASS] candidates: after F1 and DF-A: {'refine': 4, 'generalize': 4, 'migrate': 2, 'explore': 81} candidates, all traceable; chose refine at 0.909 (13s)
[PASS] lanes: 32 records; executed {'bootstrap': 2, 'explore': 23, 'generalize': 3, 'refine': 4}; offered {'refine': 30, 'generalize': 31, 'migrate': 139, 'explore': 2474}; 4 families opened, 2 edits (58s)
[PASS] determinism: seed 31 twice in separate processes: 26 identical rows, labels and final theory; seed 32 differs (32s)
S08 GATE [only: no_llm, scoring, operators, candidates, lanes, determinism]: PASS (6/6 groups passed)
```

```text
cd framework ; python -m surprise.gates.s09 --only wiring
```

退出码 1。输出：

```text
[FAIL] wiring: ModuleNotFoundError: No module named 'surprise.roles.runtime'
S09 GATE [only: wiring]: FAIL (0/1 groups passed)
```

失败类型是 `ModuleNotFoundError`。门槛里更早的 `require` 失败会以 `GateFailure` 抛出，且打印时不带异常类名。因此全关的 40 条（与 S8 逐行相同、行键、`config.json` / `report.json` / manifest 都没有 `llm`、未加载 `surprise.roles`）已经通过。角色打开后才导入 `surprise.roles.runtime`，该模块要等 `s09-roles` 合并。这是说明里写明的预期失败。

未跑 `python -m surprise.gates.s08` 的 `longrun` 组，也未跑 `python -m surprise.gates.all`。`longrun` 会因为 `code_digests()` 纳入本次改过的文件而失败；`code_digests()` 本身没有改。按说明留给编排者重跑长跑并重钉哈希。

## 与说明的偏差

`choose` 在 `candidates` 接受 `round`（或带 `**kwargs`）时调用 `candidates(wb, round=rounds)`。S8 有两个单测把 `candidates` 换成只接收 `wb` 的函数，无条件传入 `round` 会 `TypeError`，而本包不能改那些测试。真实的 `Hunter.candidates` 始终收到 `round`，并连同当前 `_index` 传给每个来源。`sources` 为空时不消耗额外随机数。S8 的 `lanes`、`determinism` 和 wiring 的全关 40 行哈希已通过。

## 未决问题

无。
