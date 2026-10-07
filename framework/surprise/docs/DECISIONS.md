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
| 2026-10-08 | S0 | 长期批准：在本项目里通过 `python tools/orch/grok_worker.py` 启动 grok 子进程（带 `--always-approve`，`--cwd` 限定在 `.worktrees/` 下）。不另开 PowerShell 窗口、不用 `Start-Process`；长时间运行的命令用编排者自己的后台任务方式运行 | 用户（Claude Code 的安全分类器三次拒绝启动 grok 之后给出） |
| 2026-10-08 | S0 | 派发默认前台阻塞到 grok 退出，由编排者的后台任务承载；`--detach`（隐藏的监督进程）保留但默认不用。脚本拒绝在 `.worktrees/` 以外启动 grok | 落实上一条用户指示；开场提示词写的是"后台启动" |
| 2026-10-08 | S0 | 会话号由 `spawn` 生成 UUID 记入 `.orch/state/`，返工用 `--resume <UUID>` 续接 | grok 1.0.46 实测：`--session-id` 只接受新的 UUID，不能续接；开场提示词写的是 `--session-id <包号>` |
| 2026-10-08 | S0 | 派发时给 grok 传 `--trust`；提示词保持 `-p` 指向 `.orch/brief.md` | worktree 对 grok 是独立工作区，不信任就不加载 CLAUDE.md；实测中文参数、读取被忽略目录里的 brief 都正常 |
| 2026-10-08 | S0 | deny 规则比开场提示词列的多：加了 PowerShell 与 cmd 的递归删除写法、`git -C`/`git -c` 变体、`tools/orch/`、`.orch/` 下编排者的文件；路径规则同时给 Edit、Write 两种前缀和相对、`**/` 两种形式 | 实测执行者的 shell 是 Windows PowerShell 5.1，`rm -rf` 一条不够；`**/` 形式用来挡住用绝对路径写主检出区；13 条探测全部被拦下 |
| 2026-10-08 | S0 | 执行者与审查复跑共用运行派发脚本的那个解释器（放到执行者 PATH 最前）；每个 worktree 的 TMP/TEMP 指向自己的 `.orch/tmp`；审查复跑同样去掉 `DEEPSEEK_API_KEY` | PATH 上默认的 pytest 是 anaconda 的，没有 duckdb；RUNBOOK 要求每个 worktree 用自己的临时目录 |
| 2026-10-08 | S0 | `review` 的允许路径取自 brief 里的 ```` ```allow-paths ```` 块（派发时连同 brief 的哈希记入状态）；有红旗时退出码 3 | 审查与执行者读同一份说明，执行者事后改 brief 会被发现 |
| 2026-10-08 | S0 | `merge` 要求对分支当前提交做过 `review`；合并提交保持纯合并，brief、report、审查包与各轮返工意见另起一个归档提交 | `git log --merges` 能直接对上每个包；审查包留作验收证据 |
| 2026-10-08 | S0 | S0 不写 `gates/s00.py`，以冒烟包验收，证据归档在 `framework/surprise/docs/orch/s00/` | `surprise.gates` 包由 S1 建立；S0 不写框架代码 |
| 2026-10-08 | S0 | 多派了一个探测包 s00-deny（13 条 deny 探测加一轮 `resume`），超出开场提示词的最小冒烟 | deny 规则是在不知道 shell 类型时写的，原生 Windows 又没有沙箱，要实测；`resume` 的做法与提示词不同，也要实测 |
| 2026-10-08 | S0 | 工作包结论：s00-smoke 一次通过；s00-deny 一次通过，另有 1 轮为测试 `resume` 安排的返工。两个包都按计划 `--abandon`，不合并 | 冒烟包不产出要保留的代码 |
| 2026-10-08 | S0 | S0 在分支 `session/s00` 上做，收尾合并回 main 再打 `s00-done` | 与 S1 起的会话分支约定一致 |
| 2026-10-08 | S0 | CLAUDE.md 写入"执行者模式"一节；"收尾协议"改名为"收尾协议（编排者）"，第 1 条写明门槛在派发前写好；"命令"一节加编排命令一行（注明在仓库根执行） | 用户同意 S0 收尾消息里的草稿与两处配套小改 |
| 2026-10-08 | S0 | 写入 CLAUDE.md 之后另打 tag `s00-done-r2`，不移动 `s00-done`；S1 从 `s00-done-r2` 起 | 会话分支从上一会话的 tag 建，tag 里要含"执行者模式"；沿用修复会话的 `-r2` 命名，不改写已有 tag |
