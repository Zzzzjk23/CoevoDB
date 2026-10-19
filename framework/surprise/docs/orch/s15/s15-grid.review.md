# 审查包 · s15-grid

- 生成时间：2026-10-19T17:14:55+11:00
- 基线：`session/s15`（c4bace369102）
- 分支：`grok/s15-grid` @ 6692708408e0，基线之上 1 个提交
- 运行：共 2 轮（返工 0 轮），最近一轮退出码 0，用时 13m57s
- 执行者：codex codex-cli 0.163.0；会话 `01a1526e-0038-7fc3-baef-17d006f905c5`；换过执行者：第 1 轮之后 grok → codex

## 红旗汇总

- 门槛未通过（退出码 1）
- 执行者日志里有 1 条 error / turn.failed 事件

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s15..grok/s15-grid
git diff -M --stat session/s15..grok/s15-grid
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/experiments/grid.py`、`framework/surprise/metrics/data/prices_deepseek.json`、`framework/tests/test_surprise_s15_grid.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/experiments/grid.py` |  |
| A | `framework/surprise/metrics/data/prices_deepseek.json` |  |
| A | `framework/tests/test_surprise_s15_grid.py` |  |

提交：

- 6692708 Junke: feat(grid): add parallel scheduling and wall-clock process limits

## 2. diff 统计

```text
 framework/surprise/experiments/grid.py             | 670 +++++++++++++++++----
 .../surprise/metrics/data/prices_deepseek.json     |  25 +
 framework/tests/test_surprise_s15_grid.py          | 593 ++++++++++++++++++
 3 files changed, 1184 insertions(+), 104 deletions(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，4m45s；passed 970，skipped 3

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
970 passed, 3 skipped in 284.29s (0:04:44)
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，37m45s

```text
b/s1-r0 done
a/s2-r0 done
b/s2-r0 done
[FAIL] archive: pack failed: 1 D:\CoevoDB\.venv\Scripts\python.exe: No module named surprise.experiments.archive

[FAIL] docs: SERVER.md: no heading '### 5.7 \u5e76\u884c\u7f51\u683c'
[PASS] scope: 8 paths changed (s14-done-r2..work tree), all in scope; harness and lower layers untouched (0s)
S15 GATE: FAIL (5/11 groups passed)
=== summary ===
s01: PASS
s02: PASS
s03: PASS
s04: PASS
s05: PASS
s06: PASS
s07: PASS
s08: FAIL (exit 1)
s09: PASS
s10: PASS
s11: FAIL (exit 1)
s12: PASS
s13: PASS
s14: PASS
s15: FAIL (exit 1)
GATES: FAIL (12/15 passed)
```

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- 无

### 4.4 新增的宽泛异常捕获

- 无

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s15-grid.jsonl` 与 stderr 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 新增 `refs/heads/grok/s15-archive` @ 5381600880f4
- 移动 `refs/heads/session/s15` c4bace369102 → 2f955f995991

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s15-grid.jsonl`：3146 条事件（available_commands 55，error 1，item.completed 52，item.started 39，orch.exit 2，orch.start 2，text 164，thought 2441，thread.started 1，tool_call 91，tool_call_update 258，turn.completed 1，turn.started 1，usage 38）；各轮合计 codex：1 轮，输入 4742856 token（其中缓存 4620160），输出 20443（其中推理 11634），codex 不报美元。

被 deny 规则（grok）或 execpolicy 规则（codex，记在 stderr）拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git commit -m "feat(grid): add parallel scheduling and wall-clock process limits" 2>&1 | Tee-Object -Fil…
exec [exit 0]: [grok/s15-grid 6692708] feat(grid): add parallel scheduling and wall-clock process limits 3 files changed, 1184 insertions(+), 104 deletions(-) create mode 100644 framework/surpri…
file_change [completed]: add D:\CoevoDB\.worktrees\s15-grid\.orch\report.md
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short 2>&1 | Tee-Object -FilePath .orch/tmp/s15-grid-status.log; $taskExit = $LASTEXITCODE;…
exec [exit 0]: 
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "@' from pathlib import Path root = Path('.orch') report = root / 'report.md' body = report.read_text(enc…
exec [exit 0]: report.md: 8 command outputs inserted; no placeholders
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Encoding UTF8 .orch/report.md | Select-Object -Last 45; git status --short; git log -1 --on…
exec [exit 0]: [PASS] no_llm: hunter, metrics, baselines, diagnoser and the loop import no model client and no old agent (0s) [PASS] constants: 12 hunter and 2 diagnoser constants as planned; BE…
text: 已完成并提交 `6692708`，工作区干净。 测试：970 passed、3 skipped；全部指定门槛通过，无范围偏差。 [报告已写入 .orch/report.md](D:/CoevoDB/.worktrees/s15-grid/.orch/report.md)。Linux 实机 CPU 绑定待复验；S8 longrun 按说明留给编排者。
end: tokens in=4742856 cached=4620160 out=20443 reasoning=11634
orch.exit: {"pkg": "s15-grid", "run": 2, "at": "2026-10-19T15:45:40+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
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
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：
