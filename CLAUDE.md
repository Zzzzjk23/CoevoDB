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

- 测试：`pytest -q testing tests`
  （不要直接 `pytest -q`：`framework/test_api.py` 在设置了密钥时会真的调用 DeepSeek API）
- 门槛：`python -m surprise.gates.all`（每个 `gates/sNN.py` 退出码 0 = 通过；由 S1 建立）
- 引擎环境：{S1 填写各 venv 的路径与版本：DuckDB 1.5.5、DuckDB 1.1.3、DataFusion 54.0.0、DataFusion 旧版、SQLite}
- PostgreSQL 相关注意事项见 `framework/AGENTS.md`。

## 收尾协议

1. 新增 `framework/surprise/gates/sNN.py`，跑测试与全部门槛，贴出结果。
2. 更新 `HANDOFF.md`，追加 `DECISIONS.md`。
3. git commit，打 tag `sNN-done`（修复会话打 `sNN-done-r2`）。
4. 最后一条消息只写：门槛结果、与计划的偏差、需要用户人工检查的 3–5 处（文件路径或命令）。
5. 上下文快用完时，先把 `HANDOFF.md` 标为"进行中"并提交 WIP；下一个会话沿用同一编号接着做。
