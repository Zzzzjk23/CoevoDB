# DECISIONS

只追加，不改旧条目。推翻旧决定时新加一条，写明推翻的是哪一条。

| 日期 | 会话 | 决定 | 来源 / 理由 |
|---|---|---|---|
| 2026-10-08 | 规划 | 七类 oracle = TLP、NoREC、Plan variant、Index presence、Equivalent query、Version differential、Cross-DBMS differential；崩溃与内部错误是 fail 的子类型，不单列 | 用户确认 |
| 2026-10-08 | 规划 | 标签只来自 oracle + CVE（Contract-Verified Evidence，原论文 Challenge I）；LLM 永不打标签 | 用户确认 |
| 2026-10-08 | 规划 | CVE 成本分层：所有候选新进程重跑 + 前提检查；预测落在已有假设里的失败只做一次归属测试；最小化与完整画像只给要进 Diagnoser 的失败；最小化后不复现或违反前提则降为 invalid | 用户采纳 |
| 2026-10-08 | 规划 | 首发引擎只做 DuckDB（1.5.5 + 1.1.3）与 DataFusion 54.0.0 | 用户确认 |
| 2026-10-08 | 规划 | 无开关引擎用错误类别 + 行为画像定身份（PLAN 决策 3） | 用户采纳 |
| 2026-10-08 | 规划 | Cross-DBMS：≥3 引擎且目标唯一异类才判 fail，否则 invalid（PLAN 决策 11） | 用户采纳 |
| 2026-10-08 | 规划 | Equivalent query：改写来自冻结的确定性规则库或经验收的 LLM 改写时才判 fail，其余不一致记 invalid | 用户采纳 |
| 2026-10-08 | 规划 | Version differential：方向可定（旧版得其他引擎多数支持，或新版被前四类独立见证）才判 fail 并记为回归，否则 invalid | 用户采纳 |
| 2026-10-08 | 规划 | 新包为 `framework/surprise/`，与旧代码并行，旧循环冻结为"原 CoevoDB"对照组 | 用户按推荐确认 |
| 2026-10-08 | 规划 | repair_bench 论文不再需要，S12 归档 | 用户 |
| 2026-10-08 | 规划 | SQLancer++ 暂不纳入评估；离线去重对比改为与原 CoevoDB 的 σ 比较 | 用户 |
| 2026-10-08 | 规划 | 不估工时 | 用户 |
| 2026-10-08 | 规划 | `coevo/` 推迟到 S12 归档（tests/test_verified_loop.py 依赖它） | 规划会话发现的依赖 |
