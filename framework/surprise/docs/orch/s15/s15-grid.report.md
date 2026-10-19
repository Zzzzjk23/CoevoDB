# 报告 · s15-grid

提交：`6692708`（`grok/s15-grid`）。沿用上一位执行者留下的可用实现，并修正配置空值校验及 POSIX 退出后的进程组清理。

## 改了哪些文件

- `framework/surprise/experiments/grid.py`：修改；增加新配置键、unlimited/tier 与 SQLancer 运行参数、按块排序的单线程并行调度、槽位 CPU 绑定与引擎线程环境、墙钟中断和进程树强杀、每格元数据及恢复状态。
- `framework/surprise/metrics/data/prices_deepseek.json`：新增；保存工作包指定的 DeepSeek 价格表，与门槛常量完全一致。
- `framework/tests/test_surprise_s15_grid.py`：新增；35 项专项用例覆盖默认值、坏值、旧配置兼容、命令、块顺序与槽位、并发、环境继承、CPU 分配、中断及孙进程清理、恢复与价格；没有新增 skip/xfail。

## 跑了哪些命令

Python 命令均在 `framework/` 下执行，使用说明指定的 `python`。验收输出通过 PowerShell `Tee-Object` 保存在 `.orch/tmp/s15-grid-*.log`，并单独保存原始 `$LASTEXITCODE`。下列列出命令、退出码和输出末 20 行；不足 20 行时完整列出。

### 1. 继承改动的专项测试

命令：`python -m pytest -q tests/test_surprise_s15_grid.py`

退出码：`0`。

```text
........................                                                 [100%]
24 passed in 13.76s
```

### 2. 修正并补充断言后的专项测试

命令：`python -m pytest -q tests/test_surprise_s15_grid.py`

退出码：`0`。

```text
...................................                                      [100%]
35 passed in 15.01s
```

### 3. 完整测试集

命令：`python -m pytest -q testing tests`

退出码：`0`。

```text
........................ss..................................s........... [  7%]
........................................................................ [ 14%]
........................................................................ [ 22%]
........................................................................ [ 29%]
........................................................................ [ 36%]
........................................................................ [ 44%]
........................................................................ [ 51%]
........................................................................ [ 59%]
........................................................................ [ 66%]
........................................................................ [ 73%]
........................................................................ [ 81%]
........................................................................ [ 88%]
........................................................................ [ 96%]
.....................................                                    [100%]
970 passed, 3 skipped in 364.99s (0:06:04)
```

### 4. S15 本包门槛

命令：`python -m surprise.gates.s15 --only config parallel kill prices`

退出码：`0`。

```text
[PASS] config: new keys kept and passed to the cells; 21 bad values rejected; old defaults unchanged; 14 E1/E3 arms from EXPERIMENT.md load (0s)
cpus_per_cell is set but os.sched_setaffinity is unavailable; cells will not be pinned
a/s1-r0 done
b/s1-r0 done
c/s1-r0 done
d/s1-r0 done
a/s2-r0 done
b/s2-r0 done
c/s2-r0 done
d/s2-r0 done
[PASS] parallel: 8 stand-ins, 4 at a time in block order with slots and engine threads; 4 real DuckDB cells ran together (start spread 0s) (71s)
quick/s1-r0 done
handles/s1-r0 done (killed)
ignores/s1-r0 done (killed)
handles/s1-r0 done
ignores/s1-r0 done
quick/s1-r0 done
[PASS] kill: interrupt at budget+grace (report written, exit 130), hard kill of the tree after the delay, done (killed), not rerun (9s)
[PASS] prices: DeepSeek prices of 2026-10-19 (peak cache-miss input, peak output) price both tiers (0s)
S15 GATE [only: config, parallel, kill, prices]: PASS (4/4 groups passed)
```

### 5. S11 回归门槛

命令：`python -m surprise.gates.s11 --only grid sqlancer arms`

退出码：`0`。

```text
[PASS] grid: 2 arms x 2 seeds in 4.1 min, resumed, report and 7 figures in one command; median families/hour {'surprise': 29.734512923486573, 'old': 29.92040429434526}; p 1.0, A12 0.375 (248s)
[PASS] sqlancer: 35 runs, 0 bugs; per engine rows match docs/FINAL_REPORT.md (0s)
[PASS] arms: random Hunter deterministic and different; frozen theory unchanged (1 failures fully profiled); frozen Diagnoser no edits; theory-from and select-from (5 choices scored differently); 5 usage errors refused (102s)
S11 GATE [only: grid, sqlancer, arms]: PASS (3/3 groups passed)
```

### 6. S13 门槛

命令：`python -m surprise.gates.s13`

退出码：`0`。

```text
[PASS] scope: 7 paths changed (s12-done-r2..s13-done), all under the docs or the S13 gate (0s)
[PASS] sections: 11 headings in order; spec parses; totals stated 2x, all match (0s)
[PASS] arms: 17 arms valid against grid.py or named sessions; ablations drop the stated roles (0s)
[PASS] engines: 7 engines; 44 milestone arm placements have their prerequisites (0s)
[PASS] cells: 7 milestones; 215 cells of 24h and 45 of 1h, as declared (0s)
[PASS] seeds: formal [1001, 1002, 1003, 1004, 1005], pilot [9101, 9102]; none among 29 numbers near 'seed' at s12-done-r2 (0s)
[PASS] sessions: SESSIONS.md has S13-S25; 7 milestones ordered; PLAN section 9 and HANDOFF row present (0s)
S13 GATE: PASS (7/7 groups passed)
```

### 7. S14 文档门槛

命令：`python -m surprise.gates.s14 --only docs`

退出码：`0`。

```text
[PASS] docs: SERVER.md: 13 headings in order, spec with 4 venvs; 6 runbook commands exist; smoke config loads offline; HANDOFF has S14 (2s)
S14 GATE [only: docs]: PASS (1/1 groups passed)
```

### 8. S8 指定回归门槛

命令：`python -m surprise.gates.s08 --only no_llm constants scoring operators candidates lanes determinism`

退出码：`0`。

```text
[PASS] no_llm: hunter, metrics, baselines, diagnoser and the loop import no model client and no old agent (0s)
[PASS] constants: 12 hunter and 2 diagnoser constants as planned; BETA = 1.0 (pre-experiment families per run: {'0.5': {'9001': 1, '9002': 3, '9003': 3}, '1.0': {'9001': 3, '9002': 3, '9003': 3}, '2.0': {'9001': 3, '9002': 3, '9003': 3}, '4.0': {'9001': 3, '9002': 5, '9003': 1}}) (0s)
[PASS] scoring: U untested 0.498 bits, adjacent 0.758; pending 0.455 after 50 probes, adjacent unexplored 1.365 at beta 2, confirmed 0 (0s)
[PASS] operators: 29 mutants of a three-statement case (4 deletions); oracle options filtered as planned (0s)
[PASS] candidates: after F1 and DF-A: {'refine': 4, 'generalize': 4, 'migrate': 2, 'explore': 81} candidates, all traceable; chose refine at 0.909 (16s)
[PASS] lanes: 32 records; executed {'bootstrap': 2, 'explore': 23, 'generalize': 3, 'refine': 4}; offered {'refine': 30, 'generalize': 31, 'migrate': 139, 'explore': 2474}; 4 families opened, 2 edits (69s)
[PASS] determinism: seed 31 twice in separate processes: 26 identical rows, labels and final theory; seed 32 differs (38s)
S08 GATE [only: no_llm, constants, scoring, operators, candidates, lanes, determinism]: PASS (7/7 groups passed)
```

### 9. 差异格式检查

命令（worktree 根目录）：`git diff --check`、`git diff --cached --check`

退出码：均为 `0`。均无输出。

### 10. 提交

命令（worktree 根目录）：`git commit -m "feat(grid): add parallel scheduling and wall-clock process limits"`

退出码：`0`。

```text
[grok/s15-grid 6692708] feat(grid): add parallel scheduling and wall-clock process limits
 3 files changed, 1184 insertions(+), 104 deletions(-)
 create mode 100644 framework/surprise/metrics/data/prices_deepseek.json
 create mode 100644 framework/tests/test_surprise_s15_grid.py
```

### 11. 收尾状态

命令（worktree 根目录）：`git status --short`

退出码：`0`。

无输出。

## 与说明的偏差

无。

## 未决问题

- 本包无阻塞问题。本机为 Windows，已实测中断、硬杀和孙进程退出；Linux 的实际 CPU 绑定需在 Linux 环境运行同一测试复验，POSIX 会话创建、子进程绑定回调与退出后的进程组清理已有模拟测试覆盖。
- 按工作包说明未运行 S8 `longrun`；编排者需在合并全部 S15 工作包后重跑长跑并重钉摘要。
