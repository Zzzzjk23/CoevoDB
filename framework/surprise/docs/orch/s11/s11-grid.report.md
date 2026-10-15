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
