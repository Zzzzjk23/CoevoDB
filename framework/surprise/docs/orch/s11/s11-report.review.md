# 审查包 · s11-report

- 生成时间：2026-10-16T06:31:17+11:00
- 基线：`session/s11`（22b4b9af4eef）
- 分支：`grok/s11-report` @ c668fbe94e56，基线之上 3 个提交
- 运行：共 2 轮（返工 1 轮），最近一轮退出码 0，用时 9m57s
- grok：grok 1.0.46 (2765805b9442)；会话 `c45296fe-2a66-451a-9088-0fe6d661906e`

## 红旗汇总

- 改动超出 brief 允许的路径 2 处：framework/surprise/metrics/rq.py, framework/tests/test_surprise_s11_metrics.py
- 本次审查包没有复跑测试（--skip-tests）
- 派发以来有 2 处 tag 变化或 ref 被删：确认是编排者自己做的，不是执行者

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s11..grok/s11-report
git diff -M --stat session/s11..grok/s11-report
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/metrics/stats.py`、`framework/surprise/metrics/report.py`、`framework/tests/test_surprise_s11_report.py`、`framework/surprise/experiments/grid.py`、`framework/tests/test_surprise_s11_grid.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/experiments/grid.py` |  |
| A | `framework/surprise/metrics/report.py` |  |
| M | `framework/surprise/metrics/rq.py` | **越界：不在允许路径内** |
| A | `framework/surprise/metrics/stats.py` |  |
| M | `framework/tests/test_surprise_s11_grid.py` |  |
| M | `framework/tests/test_surprise_s11_metrics.py` | **越界：不在允许路径内** |
| A | `framework/tests/test_surprise_s11_report.py` |  |

提交：

- e823a46 Junke: experiments(s11): accept hunter value as the omitted hunter
- af6bfdc Junke: metrics(s11): report RQ1-RQ6 with Mann-Whitney and seven figures
- c668fbe Junke: metrics(s11): score a missing bugs file as zero and report mean surprise

## 2. diff 统计

```text
 framework/surprise/experiments/grid.py       |   5 +-
 framework/surprise/metrics/report.py         | 991 +++++++++++++++++++++++++++
 framework/surprise/metrics/rq.py             |  13 +-
 framework/surprise/metrics/stats.py          | 131 ++++
 framework/tests/test_surprise_s11_grid.py    |  25 +
 framework/tests/test_surprise_s11_metrics.py |  26 +
 framework/tests/test_surprise_s11_report.py  | 445 ++++++++++++
 7 files changed, 1633 insertions(+), 3 deletions(-)
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
- 日志 `.orch/logs/s11-report.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 删除 `refs/heads/grok/s11-arms`（原 134967c2d427）
- 删除 `refs/heads/grok/s11-dedup`（原 ba4019a937d1）
- 移动 `refs/heads/session/s11` 22b4b9af4eef → bb79e9dfa916

主检出区当前未提交的改动（`git status --porcelain`）：

```text
?? framework/surprise/gates/s11_llm/
```

## 6. 执行日志摘要

`.orch/logs/s11-report.jsonl`：5546 条事件（auto_compact_completed 1，auto_compact_started 1，available_commands 143，end 2，orch.exit 2，orch.start 2，plan 3，text 948，thought 3502，tool_call 247，tool_call_update 576，usage 119）；各轮合计 119 个模型回合，grok 上报花费 3.0253 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "## 与说明的偏差\n被强杀且 `old_run.json` 里 `reports` 为 0、磁盘上没有 `bugs.jsonl` 的旧格子：`old_metrics` 会因文件不存在抛出 `FileNotFoundError`（`old_n…
tool_call run_terminal_command: {"command": "git status --short; git log -3 --format=\"%h %s\"; git check-ignore -v .orch/report.md", "description": "Confirm clean branch after the rework commit"}
tool_call read_file: {"target_file": "D:\\CoevoDB\\.worktrees\\s11-report\\.orch\\report.md", "offset": 42, "limit": 20}
tool_update [in_progress]: 
tool_update [completed]: {"type": "ReadFile", "FileContent": {"content": "42→## 与说明的偏差\n无。第 1 轮返工已把“缺 `bugs.jsonl`”放进 `old_metrics`，报告不再自建临时目录。\n\n## 未决问题\n- `--dedup` / `--coverage` 与 `GRID_DIR/extras/` …
tool_update [in_progress]: c668fbe metrics(s11): score a missing bugs file as zero and report mean surprise
tool_update [in_progress]: c668fbe metrics(s11): score a missing bugs file as zero and report mean surprise af6bfdc metrics(s11): report RQ1-RQ6 with Mann-Whitney and seven figures e823a46 experiments(s11):…
tool_update [completed]: exit: 0 c668fbe metrics(s11): score a missing bugs file as zero and report mean surprise af6bfdc metrics(s11): report RQ1-RQ6 with Mann-Whitney and seven figures e823a46 experimen…
thought: Git 工作区干净，无未提交更改。
text: 第 1 轮审查的两处返工已经做完，提交为 `c668fbe`，工作区干净。`.orch/report.md` 已追加「第 1 轮返工」。 - `old_metrics` 在 `run_dir` 存在但没有 `bugs.jsonl` 时按 0 条报告计算；目录本身不存在仍报错。报告不再自建临时目录。 - `run_metrics` 的 `rq2.mean_s…
end: stopReason=end_turn turns=24 cost_usd=0.80595572
orch.exit: {"pkg": "s11-report", "run": 2, "at": "2026-10-16T06:30:45+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s11-report

## 改了哪些文件
- `framework/surprise/experiments/grid.py`：修改。`hunter: "value"` 视为默认猎人，规范化后与省略该键相同，命令行不传 `--hunter`。
- `framework/tests/test_surprise_s11_grid.py`：修改。增加一条测试，核对 `value` 与省略 hunter 的配置和命令行一致，`random` 仍传 `--hunter random`。
- `framework/surprise/metrics/stats.py`：新增。中位数、`summarize`、Vargha–Delaney A12、双侧 Mann-Whitney U（无并列且 n≤20 用精确分布，否则用带并列与连续性修正的正态近似）。
- `framework/surprise/metrics/report.py`：新增。`python -m surprise.metrics.report` 与 `build`：只读网格，写出 `report.json`、`report.md` 和 7 张图。
- `framework/tests/test_surprise_s11_report.py`：新增。统计函数的手算值与 scipy 交叉核对，以及手工网格上的报告（含一次很短的真实 `loop.run`，和没有 `bugs.jsonl` 的被强杀旧格子）。

提交：`e823a46` `experiments(s11): accept hunter value as the omitted hunter`；`af6bfdc` `metrics(s11): report RQ1-RQ6 with Mann-Whitney and seven figures`。

## 跑了哪些命令
### `cd framework; python -m pytest -q testing tests`
退出码：0

```
........................ss..................................s........... [  7%]
........................................................................ [ 15%]
........................................................................ [ 23%]
........................................................................ [ 31%]
........................................................................ [ 39%]
........................................................................ [ 47%]
........................................................................ [ 55%]
........................................................................ [ 62%]
........................................................................ [ 70%]
........................................................................ [ 78%]
........................................................................ [ 86%]
........................................................................ [ 94%]
....................................................                     [100%]
913 passed, 3 skipped in 244.84s (0:04:04)
```

### `cd framework; python -m surprise.gates.s11 --only stats grid`
退出码：0

```
[PASS] stats: exact and asymptotic MWU (scipy agrees), A12, median, summarize as hand-computed (1s)
[PASS] grid: 2 arms x 2 seeds in 4.0 min, resumed, report and 7 figures in one command; median families/hour {'surprise': 29.887242904332677, 'old': 29.92457998383876}; p 1.0, A12 0.375 (247s)
S11 GATE [only: stats, grid]: PASS (2/2 groups passed)
```

## 与说明的偏差
无。第 1 轮返工已把“缺 `bugs.jsonl`”放进 `old_metrics`，报告不再自建临时目录。

## 未决问题
- `--dedup` / `--coverage` 与 `GRID_DIR/extras/` 下的同名文件同时存在时，命令行的文件覆盖网格里的文件。两边都没有则报告里不出现 `extras` 键。

## 第 1 轮返工
审查意见要求两处改动，都已做。提交 `c668fbe`。

- `framework/surprise/metrics/rq.py`：修改。`run_dir` 存在但没有 `bugs.jsonl` 时报告列表为空；`run_dir` 不存在仍报错。`rq2` 增加 `mean_surprise`，等于 `_surprise` 非空的记录的平均惊讶，没有这样的记录为 None。
- `framework/surprise/metrics/report.py`：修改。删掉临时目录，直接调用 `old_metrics`。`mean_surprise` 进入 RQ2 汇总与检验，配对表读这个字段，冻结对比的 `delta` 也带上它。
- `framework/tests/test_surprise_s11_metrics.py`：修改。缺 `bugs.jsonl` 时期望家族数 0、每小时 0、重复率 None；校准夹具上 `mean_surprise` 与手算的 `-log2` 平均一致。
- `framework/tests/test_surprise_s11_report.py`：修改。配对臂两格用带 `p_t` 的账本，`mean_surprise` 汇总 n 为 2，中位数等于手算值。

### `cd framework; python -m pytest -q testing tests`
退出码：0

```
........................ss..................................s........... [  7%]
........................................................................ [ 15%]
........................................................................ [ 23%]
........................................................................ [ 31%]
........................................................................ [ 39%]
........................................................................ [ 47%]
........................................................................ [ 54%]
........................................................................ [ 62%]
........................................................................ [ 70%]
........................................................................ [ 78%]
........................................................................ [ 86%]
........................................................................ [ 94%]
.....................................................                    [100%]
914 passed, 3 skipped in 226.88s (0:03:46)
```

### `cd framework; python -m surprise.gates.s11 --only stats runmetrics vocabulary grid`
退出码：0

```
[PASS] stats: exact and asymptotic MWU (scipy agrees), A12, median, summarize as hand-computed (1s)
[PASS] runmetrics: 31 records, 1 ledger families, Brier 0.2194, 1 high-surprise records, invalid 14, theory length 193.0; all recomputed (28s)
[PASS] vocabulary: run_registry, new_families, compare, recall.score, RunData and run_metrics all read the run's vocabulary (9s)
[PASS] grid: 2 arms x 2 seeds in 4.1 min, resumed, report and 7 figures in one command; median families/hour {'surprise': 29.890769662243766, 'old': 29.93901925750707}; p 1.0, A12 0.375 (246s)
S11 GATE [only: stats, runmetrics, vocabulary, grid]: PASS (4/4 groups passed)
```
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：
