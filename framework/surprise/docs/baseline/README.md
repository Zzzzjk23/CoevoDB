# 旧系统基线 run（S1 存档）

整理仓库之前跑的"原 CoevoDB"基线，供之后核对旧主循环是否还能照样跑。

| 项 | 值 |
|---|---|
| 命令（在 `framework/` 下） | `python main.py --engine duckdb --mode no_llm --iterations 2` |
| 时间 | 2026-10-08 20:49 |
| 代码 | 分支 `session/s01` 的起点，即 tag `s00-done-r2`（4eaa4ed）；旧代码与 `v1-baseline`（55c5512）相同，S0 只加了编排工具与文档 |
| 解释器 | 仓库根 `.venv`，Python 3.13.9，DuckDB 1.5.5 |
| 环境 | 没有设置 `DEEPSEEK_API_KEY`；没有设置 `COEVO_OLD_VENV` |
| 退出码 | 0，约 3 秒 |
| 原始输出目录 | `framework/results/duckdb_no_llm_20261008_204923/`（不入库），本目录是它的副本 |

结果摘要：2 轮，3992 次 SQL 执行，LLM 调用 0 次，候选 0 个，真 bug 0 个，家族 0 个，因结果不确定跳过 2 条。

读这份基线时要知道的两点：

- Version differential 没有参与：日志第一行是 `differential disabled (no old venv at …/bin/python)`。跑的时候旧版 DuckDB 的 venv 还没建；而且旧代码写死了 `<venv>/bin/python`，Windows 上 venv 的解释器在 `Scripts/python.exe`，所以在这台机器上即使给了 venv 也不会启用（见 `HANDOFF.md` 未决问题）。
- `no_llm` 模式只跑种子变异流，2 轮没有候选是正常结果，不代表 oracle 失效。

文件：`summary.json`、`iter_0.json`、`iter_1.json`、`metrics.jsonl`、`coverage.json`、`families.json`、`bugs.jsonl`（空）、`llm_ledger.jsonl`（空）、`run.log` 是 run 目录的原样副本；`console.txt` 是命令的完整控制台输出。

full 模式没有跑（需要 DeepSeek，用户决定本会话不跑）。
