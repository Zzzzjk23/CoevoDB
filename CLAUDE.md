# CoevoDB · 迁移到惊讶驱动框架

目标：把 CoevoDB 从 bandit + playbook 的共同进化循环改造成惊讶驱动框架。
文档都在 `framework/surprise/docs/`：
- `PLAN.md`：总规划（只读，只在用户做出新决定时改）
- `SESSIONS.md`：12 个实施会话的范围、交付物与门槛
- `HANDOFF.md`：会话之间的交接
- `DECISIONS.md`：决策日志（只追加）

## 不可违反

- 密钥只走环境变量 `DEEPSEEK_API_KEY`；不打印，不写进代码、配置、日志或提交。完整规则见 `framework/AGENTS.md`。
- LLM 永不打标签：标签只来自七类 oracle 加 CVE（Contract-Verified Evidence）流程。
- S4 结束后，`framework/surprise/harness/` 和 manifest 里的常数冻结；要改先问用户。
- S12 之前，旧代码只做移动、不改逻辑（移动时只允许改导入路径）；旧测试保持通过。
- 只做 `SESSIONS.md` 中当前会话的范围；计划外的问题记进 `HANDOFF.md` 的"未决问题"，不要顺手修。
- 与 `PLAN.md` 冲突的决定先问用户；小的实现选择自己定，记进 `DECISIONS.md`。

## 命令（在 `framework/` 目录下执行）

- 测试：`../.venv/Scripts/python.exe -m pytest -q testing tests`
  （用仓库根 `.venv` 的解释器：PATH 上的 `pytest` 是 anaconda 的，没有 duckdb。不要直接 `pytest -q`：`framework/test_api.py` 在设置了密钥时会真的调用 DeepSeek API）
- 门槛：`../.venv/Scripts/python.exe -m surprise.gates.all`（每个 `gates/sNN.py` 退出码 0 = 通过；由 S1 建立）
- 编排（在仓库根执行）：`.venv/Scripts/python.exe tools/orch/grok_worker.py {spawn|status|review|resume|merge|cleanup|list}`（流程见 `framework/surprise/docs/ORCHESTRATION.md`）
- 引擎环境（路径相对仓库根，都不入库；解释器是 `<venv>/Scripts/python.exe`，Python 3.13.9）：
  - `.venv`（主环境）：DuckDB 1.5.5、DataFusion 54.0.0、SQLite 3.51.0（标准库 `sqlite3`）、psycopg2-binary 2.9.13
  - `.venvs/duckdb-1.1.3`：DuckDB 1.1.3（另装 psycopg2-binary，旧版子进程 `oracles._remote_exec` 导入时要用）
  - `.venvs/datafusion-50.0.0`：DataFusion 50.0.0（Version differential 用的旧版）
  - 仓库根有 `duckdb/`、`datafusion/` 两个放复现 SQL 的目录：在仓库根 `import` 这两个名字会假成功，核对环境要看 `__version__`
- PostgreSQL 相关注意事项见 `framework/AGENTS.md`。

## 收尾协议（编排者）

1. `framework/surprise/gates/sNN.py` 在派发前写好；收尾时跑测试与全部门槛，贴出结果。
2. 更新 `HANDOFF.md`，追加 `DECISIONS.md`。
3. git commit，打 tag `sNN-done`（修复会话打 `sNN-done-r2`）。
4. 最后一条消息只写：门槛结果、与计划的偏差、需要用户人工检查的 3–5 处（文件路径或命令）。
5. 上下文快用完时，先把 `HANDOFF.md` 标为"进行中"并提交 WIP；下一个会话沿用同一编号接着做。

## 执行者模式

任务说明（`.orch/brief.md`）第一行是"角色：执行者"时适用。此时你是某个工作包的执行者，不是编排者：下面的规则替代"收尾协议"一节，"不可违反"一节照旧有效。

- 只做 `.orch/brief.md` 里的工作包，只改其中"允许改动的路径"列出的路径。说明与本文件冲突时，以说明为准。
- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`，也不碰自己 worktree 以外的任何文件。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。认为某个测试本身有错，就写进报告，停下。
- 被权限规则拒绝的操作不要换写法重试，也不要改用 shell、脚本或别的工具达到同样效果；确实需要它才能完成任务时，写进报告，停下。
- 收尾：把改动提交到当前分支（`grok/<包号>`）；写 `.orch/report.md`（不入库），内容为改了哪些文件、跑了哪些命令及输出末 20 行、与说明的偏差、未决问题。
- 不打 tag、不合并、不 rebase、不 push、不切换或删除分支，不改 `HANDOFF.md` 与 `DECISIONS.md`。
- 说明有矛盾、缺前置条件或做不完：写进报告，停下，不自行扩大范围。
- shell 是 Windows PowerShell 5.1（没有 `&&`，用 `;`）；`python` 与 `pytest` 已指向项目解释器，不要换。
