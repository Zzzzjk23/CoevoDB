# 审查意见 1 · s15-sqlancer

你停下来报告是对的做法；下面是编排者的决定，照着接着做完。

## 1. "不改测试"这条规则管什么

CLAUDE.md 与说明里"不靠改测试让测试通过"管的是**基线里已有的测试和门槛**（`session/s15` 33b4cd3 上已经存在的 `framework/testing/`、`framework/tests/` 文件，以及 `framework/surprise/gates/`）：不许放宽它们来求绿。

本包**新写**的 `framework/tests/test_surprise_s15_sqlancer.py` 不在此列。开发中发现它写错了，直接改，只要改完它仍然检查说明要求的那件事。

## 2. 改 `test_replay_and_grid_report` 的替身（第 153 行附近）

本意是"回放不起 Java"。改成只拒绝 Java：

- 判断条件是第一个参数的文件名，用 `Path(command[0]).name.lower()` 取，是 `java` 或 `java.exe` 就失败。harness 起 Python 子进程（`build_manifest()` 查旧版 DuckDB 的版本）照常放行。
- 驱动要是用 `subprocess.Popen` 起 java（真实运行模式），替身也要同样拦住 `Popen`，不能只拦 `run`。
- 不要因此删掉别的断言。

## 3. 回放模式的 `report.json`

照你的理解：回放模式不起任何 java（包括 `java -version`），`sqlancer.java`、`sqlancer.command`、`sqlancer.pid` 都是 `null`。`commit`、`jar_sha256`、`jdbc` 照旧从安装目录读。这符合说明第 69 行（"不起 java"）。

## 4. 接着做完

照 `.orch/brief.md` 的"验收命令"一节全部跑完，包括：

- 完整的 `python -m pytest -q testing tests`；
- 说明里列的各个门槛组；
- 60 秒的真实运行、20 秒的中断测试；
- 10 分钟的真实运行，报告里给出查询数与报告数。

做完后提交，更新 `.orch/report.md`（"与说明的偏差"一节去掉已经解决的两条）。
