# 审查包 · s11-grid

- 生成时间：2026-10-16T05:29:39+11:00
- 基线：`session/s11`（10adc21b1420）
- 分支：`grok/s11-grid` @ d517c3496290，基线之上 2 个提交
- 运行：共 1 轮（返工 0 轮），最近一轮退出码 0，用时 39m24s
- grok：grok 1.0.46 (2765805b9442)；会话 `9f74b533-94a5-4957-9982-b6ab32893267`

## 红旗汇总

- 本次审查包没有复跑测试（--skip-tests）
- 派发以来有 1 处 tag 变化或 ref 被删：确认是编排者自己做的，不是执行者

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s11..grok/s11-grid
git diff -M --stat session/s11..grok/s11-grid
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/experiments/grid.py`、`framework/surprise/baselines/old_no_llm.py`、`framework/surprise/baselines/sqlancer.py`、`framework/surprise/baselines/data/sqlancer_summary.json`、`framework/tests/test_surprise_s11_grid.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| A | `framework/surprise/baselines/data/sqlancer_summary.json` |  |
| M | `framework/surprise/baselines/old_no_llm.py` |  |
| A | `framework/surprise/baselines/sqlancer.py` |  |
| A | `framework/surprise/experiments/grid.py` |  |
| A | `framework/tests/test_surprise_s11_grid.py` |  |

提交：

- 2e40ccf Junke: baselines(s11): transcribe SQLancer and accept old CoevoDB modes
- d517c34 Junke: experiments(s11): run an arm by seed by duration grid

## 2. diff 统计

```text
 .../surprise/baselines/data/sqlancer_summary.json  |  16 +
 framework/surprise/baselines/old_no_llm.py         |  72 +-
 framework/surprise/baselines/sqlancer.py           | 138 ++++
 framework/surprise/experiments/grid.py             | 861 +++++++++++++++++++++
 framework/tests/test_surprise_s11_grid.py          | 796 +++++++++++++++++++
 5 files changed, 1870 insertions(+), 13 deletions(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

按 `--skip-tests` 跳过了 pytest 与门槛。

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
- 日志 `.orch/logs/s11-grid.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 新增 `refs/heads/grok/s11-dedup` @ ba4019a937d1
- 删除 `refs/heads/grok/s11-runmetrics`（原 8d9781a47c60）
- 移动 `refs/heads/session/s11` 10adc21b1420 → ca0dfea0771b

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s11-grid.jsonl`：4771 条事件（auto_compact_completed 1，auto_compact_started 1，available_commands 68，end 1，orch.exit 1，orch.start 1，plan 3，text 525，thought 3644，tool_call 135，tool_call_update 333，usage 58）；各轮合计 58 个模型回合，grok 上报花费 1.2604 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_call write: {"file_path": "D:\\CoevoDB\\.worktrees\\s11-grid\\.orch\\report.md", "content": "# 报告 · s11-grid\n\n## 改了哪些文件\n- `framework/surprise/baselines/old_no_llm.py`：修改。`command` / `run` …
tool_call todo_write: {"todos": [{"id": "4", "content": "Run tests and gates, commit, write report", "status": "completed"}], "merge": true}
tool_update [completed]: {"type": "Todo", "TodosUpdated": {"summary_for_prompt": "- [completed] 1: Add sqlancer transcript loader and old_no_llm mode\n- [completed] 2: Implement experiments/grid.py\n- [co…
plan: {"entries": [{"content": "Add sqlancer transcript loader and old_no_llm mode", "priority": "medium", "status": "completed"}, {"content": "Implement experiments/grid.py", "priority…
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "", "new_string": "# 报告 · s11-grid\n\n## 改了哪些文件\n- `framework/surprise/baselines/old_no_llm.py`：修改。`command` / `run` / 命令行…
tool_call run_terminal_command: {"command": "git status --short", "description": "Confirm report is untracked and tree clean"}
tool_update [in_progress]: 
tool_update [completed]: exit: 0
thought: 已阅读 .orch/brief.md，准备按说明完成工作包。
text: 工作包 `s11-grid` 已完成，提交在 `grok/s11-grid`：`2e40ccf`（SQLancer 转录与旧系统 mode）和 `d517c34`（实验网格与测试）。工作区是干净的，报告在 `.orch/report.md`。 网格按配置逐格跑（臂 × 种子 × 时长 × 重复），`done` 的格子原样跳过，未完成的目录改名为 `.sta…
end: stopReason=end_turn turns=58 cost_usd=1.26044732
orch.exit: {"pkg": "s11-grid", "run": 1, "at": "2026-10-16T05:29:30+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s11-grid

## 改了哪些文件
- `framework/surprise/baselines/old_no_llm.py`：修改。`command` / `run` / 命令行增加 `mode`。`no_llm` 的子进程 argv、标签 `s08_old_s<seed>`、`old_run.json` 与原来一致，并继续去掉 `DEEPSEEK_API_KEY`；其它模式保留该变量，标签为 `s11_old_<mode>_s<seed>`。
- `framework/surprise/baselines/sqlancer.py`：新增。`load` 校验转录摘要，`metrics` 给出该引擎的 checks 与 family 计数。
- `framework/surprise/baselines/data/sqlancer_summary.json`：新增。`docs/FINAL_REPORT.md` 里 SQLancer 表的转录（schema 1，35 次，90300000 checks，0 bugs）。
- `framework/surprise/experiments/grid.py`：新增。配置校验、按 (rep, seed, 臂顺序) 逐格跑、续跑、`status`。
- `framework/tests/test_surprise_s11_grid.py`：新增。配置错误、布局、续跑、status、密钥、old mode、SQLancer。

提交：`2e40ccf` baselines(s11)，`d517c34` experiments(s11)。分支 `grok/s11-grid`，工作区干净。

## 跑了哪些命令

工作目录均为 `framework/`。

命令：`python -m pytest -q tests/test_surprise_s11_grid.py`

退出码：0

```
........................................................................ [ 77%]
.....................                                                    [100%]
93 passed in 3.14s
```

命令：`python -m pytest -q testing tests`

退出码：0

```
........................ss..................................s........... [  8%]
........................................................................ [ 16%]
........................................................................ [ 24%]
........................................................................ [ 32%]
........................................................................ [ 40%]
........................................................................ [ 48%]
........................................................................ [ 56%]
........................................................................ [ 64%]
........................................................................ [ 72%]
........................................................................ [ 80%]
........................................................................ [ 88%]
........................................................................ [ 96%]
............................                                             [100%]
889 passed, 3 skipped in 214.70s (0:03:34)
```

命令：`python -m surprise.gates.s11 --only sqlancer`

退出码：0

```
[PASS] sqlancer: 35 runs, 0 bugs; per engine rows match docs/FINAL_REPORT.md (0s)
S11 GATE [only: sqlancer]: PASS (1/1 groups passed)
```

命令：`python -m surprise.gates.s11 --only grid`

退出码：1

```
[FAIL] grid: the report failed: D:\CoevoDB\.venv\Scripts\python.exe: No module named surprise.metrics.report

S11 GATE [only: grid]: FAIL (0/1 groups passed)
```

失败点在报告命令。网格部分（4 格跑完、续跑不改 `cell.json`、`status` 含 `4/4`）已通过，否则失败行会是 `the grid failed`、`a rerun resumes` 或 `status reports 4/4`。

命令：`python -m surprise.gates.s08 --only no_llm`

退出码：0

```
[PASS] no_llm: hunter, metrics, baselines, diagnoser and the loop import no model client and no old agent (0s)
S08 GATE [only: no_llm]: PASS (1/1 groups passed)
```

## 与说明的偏差
- `surprise` 臂的 `freeze` 只接受 `theory` 和 `diagnoser`，`hunter` 只接受 `random`，`theory_from` / `select_from` 必须是非空的 `RUN@GEN`。`freeze` 与 `llm` 同用时，roles 只允许 `implementer` 和 `prior`。这些取值来自 `gates/s11.py` 的 arms 组与 S11 决策；本 worktree 的 loop 还没有这些开关。不在此列的配置在 `load_config` 报错，不会原样传给 loop。
- 配置或 `status` 目录不合法时进程退出码是 2，stderr 为一行 `error: ...`。格子失败时 `run` 退出码是 1，并继续跑其余格子。说明只规定了格子失败为 1、`status` 为 0。

## 未决问题
无。`python -m surprise.metrics.report` 缺失是说明里写明的预期（`s11-report` 尚未合并）。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：
