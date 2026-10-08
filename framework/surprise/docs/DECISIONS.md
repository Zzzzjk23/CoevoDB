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
| 2026-10-08 | S1 | 测试基线不绿的处理：往 `.venv` 装 psycopg2-binary（装到 2.9.13）。装完 `pytest -q testing tests` 为 64 passed、3 skipped，作为 S1 基线 | 用户。开场提示词里这一条带着"贴之前请确认"的备注，编排者问过一次后才装 |
| 2026-10-08 | S1 | 引擎环境由编排者直接装，不派给执行者：`.venv` 加 `datafusion==54.0.0`；用 `D:\anaconda3\python.exe -m venv` 加 pip 新建 `.venvs/duckdb-1.1.3`（duckdb 1.1.3）与 `.venvs/datafusion-50.0.0`（datafusion 50.0.0，依赖带进 pyarrow 25.0.1）；两个新 venv 都不继承系统包；`.gitignore` 加 `.venvs/`。PostgreSQL 本体没装 | 用户同意由编排者直接装；位置、建法由编排者定。执行者不许碰 worktree 之外的东西 |
| 2026-10-08 | S1 | 旧版 DataFusion 选 50.0.0 | 编排者定（确认环境准备时列给用户看过，用户没有改）。PLAN 只说"一个更早的版本"；与 54 隔 4 个大版本，和 DuckDB 1.5.5 对 1.1.3 的间隔相当，Python 接口是同一代。S3 做 Version differential 时可以换 |
| 2026-10-08 | S1 | `.venvs/duckdb-1.1.3` 里另装 psycopg2-binary 2.9.13 | `DuckDBRunner` 移进 `targets/` 之后，`import oracles`（含旧版子进程入口 `oracles._remote_exec`）会经过 `targets/__init__.py` 导入 psycopg2；整理前这个入口只需要 duckdb。S12 之前不改 `targets/__init__.py`，所以在环境侧补上 |
| 2026-10-08 | S1 | CLAUDE.md 改两处：填"引擎环境"；测试命令写明用 `.venv` 的解释器。其他地方没动 | 用户同意。前一处是 SESSIONS.md 的 S1 要求，后一处对应 S0 未决问题第 2 条 |
| 2026-10-08 | S1 | 旧系统基线 run 的存档入库，放在 `framework/surprise/docs/baseline/`（约 15 KB），其中 `run.log` 用 `git add -f` 加入 | `results/` 不入库，放在那里会丢；`*.log` 在 `.gitignore` 里。full 模式按用户指示不跑 |
| 2026-10-08 | S1 | `DuckDBRunner` 的移法：只把 `class DuckDBRunner` 搬到 `targets/duckdb_runner.py`；`QueryResult`、`bags_equal` 留在 `oracles/db_runner.py`，文件末尾兼容导入 `DuckDBRunner`。其他文件一律不改 | 整体搬走加纯 re-export 会循环导入（`targets/__init__.py` → `postgres_runner` → `from oracles.db_runner import QueryResult`），派发前实测报 ImportError。SESSIONS 写的是"`oracles/db_runner.py` 保留为兼容导入"，这里多留了两个共享定义 |
| 2026-10-08 | S1 | PG 脚本 41 个全部移到 `framework/campaigns/`，只改两处 `scripts.pg_*` 导入；`campaigns/` 不建 `__init__.py`；文档与文档字符串里的旧路径不改 | 牵连很少（没有别的代码按模块名或路径依赖这些脚本），不需要用 SESSIONS 给的"原地不动"退路；`scripts/` 本来就是命名空间包；文档更新是 S12 的范围 |
| 2026-10-08 | S1 | `gates/s01.py` 在 SESSIONS 列的四项之外加三项：tag `v1-baseline` 指向 55c5512；campaign 脚本对照整理前的 `--help` 结果（39 个正常，另 2 个只查语法）；`DuckDBRunner` 六种导入顺序加旧版 venv 里 `oracles._remote_exec` 可导入 | 四项查不出"移动弄坏了导入"；这三项都是 S1 交付物的直接后果。S12 再移动旧代码时要同步改门槛 |
| 2026-10-08 | S1 | `gates/s01.py` 的 pytest 判定是"退出码 0 且通过数不少于 64"，不是"等于 64" | 之后的会话会加测试，前面的门槛必须一直通过。S1 自身核对的是恰好 64 passed、3 skipped |
| 2026-10-08 | S1 | 门槛经 git 公共目录定位主检出区的 `.venvs/`，环境变量 `COEVO_VENVS` 可覆盖；版本检查用各环境自己的解释器、`-I` 加空目录执行，比对 `__version__` | 审查在 worktree 里复跑门槛，而 venv 只在主检出区；仓库根的 `duckdb/`、`datafusion/` 目录会让 import 假成功（S0 未决问题第 4 条） |
| 2026-10-08 | S1 | `gates/all.py` 把每个 `sNN.py` 当独立进程运行，前面的失败不中断后面的；门槛输出只用 ASCII | 进程隔离避免门槛之间互相带入已导入的模块；执行者的 PowerShell 5.1 会把中文输出弄乱 |
| 2026-10-08 | S1 | 派发前，编排者在会话临时目录的仓库克隆里一次性试做了整理，用来确认门槛能被满足、朴素做法会被门槛拦下；克隆已删除，没有任何内容进入仓库 | 门槛写错会白白用掉返工轮次。仓库里的实现代码全部来自 `grok/s01-reorg` |
| 2026-10-08 | S1 | 工作包结论：s01-reorg 一次通过，返工 0 轮。审查包的一条红旗（新增宽泛异常捕获 4 处）核对后是误报；少一个空行与日志记录器改名两处小出入不返工 | 编排者独立复跑：pytest 64 passed、门槛 7/7；从 git 对象逐字节比对类体与两个共享定义；核对了执行者的全部 23 条 shell 命令 |
| 2026-10-08 | S1 | 整理之后用基线 run 的同一条命令重跑旧主循环，`summary.json` 除计时字段外与存档相同 | SESSIONS 没有要求；PLAN 的 Phase 0 要"确认旧 main.py 可复现"，顺手做的核对，结果不入库 |
| 2026-10-08 | S1 修订 | 验收：用户让编排者复核收尾消息里点名的五处，并按编排者的推荐处理其中没定的事。下面几条"S1 修订"都出自这次授权。复核结果与 `s01-done` 时的报告一致，代码和门槛都没有改 | 用户（"一切按照你的推荐方法修改"） |
| 2026-10-08 | S1 修订 | CLAUDE.md 的门槛命令写明解释器：`../.venv/Scripts/python.exe -m surprise.gates.all`。ORCHESTRATION.md 与任务说明模板里的同名命令不动 | 与测试命令一致，避免用到 PATH 上 anaconda 的 python。模板是给执行者的，执行者的 `python` 已由派发脚本指向项目解释器 |
| 2026-10-08 | S1 修订 | `gates/s01.py` 多出的三项检查和写死的常数（41 个脚本、基线 64、三个版本号、`v1-baseline` 的提交号）保留不改 | 它们记录的就是冻结下来的基线事实；放宽之后门槛查不出环境或布局漂移 |
| 2026-10-08 | S1 修订 | 旧代码写死 `<venv>/bin/python` 的问题：S12 之前不改旧代码，也不在 venv 里造 `bin/python` 的替身。S3 的 Version differential 适配器自己按平台定位解释器。旧主循环在本机的 Version differential 保持 disabled；S11 的对照组如果需要它，再向用户提出 | "S12 之前旧代码不改逻辑"是不可违反的规则；替身要靠 Windows 给无扩展名的程序名自动补 `.exe`，太隐蔽。这类信号在旧系统里单独命中不计为 bug，缺它对计数类对比影响有限 |
| 2026-10-08 | S1 修订 | `.venvs/datafusion-50.0.0` 保持只有 DataFusion，不装 duckdb 和 psycopg2。S3 给旧版 DataFusion 写的子进程入口只导入 `datafusion` 与标准库，原始行用 JSON 传回，归一化在主进程做。S3 开工时可以推翻 | 实测在这个 venv 里导入 `targets.datafusion_runner` 先缺 psycopg2、再缺 duckdb：为了凑导入链要把另一个引擎装进"旧版 DataFusion"的隔离环境，得不偿失。同时订正：HANDOFF 原先只写了 psycopg2 一项 |
| 2026-10-08 | S1 修订 | 旧版 DataFusion 维持 50.0.0 | 没有新的信息要求换；S3 实际做 Version differential 时若 50.0.0 与复现用到的 SQL 特性不合，再换 |
| 2026-10-08 | S1 修订 | 审查时留下的两处小出入（`oracles/db_runner.py` 少一个空行、`DuckDBRunner` 的日志记录器改名）不返工 | 都不影响行为。补一个空行要另派一个工作包，不值；S12 整理旧代码时顺手补 |
| 2026-10-08 | S1 修订 | 修订在 `session/s01` 上提交，合并回 main 后另打 tag `s01-done-r2`，不移动 `s01-done`；S2 从 `s01-done-r2` 起 | 沿用 S0 的做法：tag 里要含最新的 CLAUDE.md 与交接文件，已有 tag 不改写 |
