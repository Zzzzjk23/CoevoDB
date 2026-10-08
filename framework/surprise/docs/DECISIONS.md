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
| 2026-10-08 | S2 | 五个数据契约按"谁写"分两个文件：`surprise/harness/contracts.py` 放 SQL 用例、身份证据、标签、实验记录；`surprise/theory/contracts.py` 放规格、假设、理论编辑。实验记录里的规格存成 dict，harness 不 import 理论层 | 编排者定。CLAUDE.md 规定 S4 之后 `harness/` 冻结；后三个契约到 S5–S7 才定型，放进 harness 会被提前冻住。划分依据是 PLAN.md 第 4 节契约表的"谁写"一列 |
| 2026-10-08 | S2 | PLAN 决策表第 6 条（实验账本用 SQLite，不用被测的 DuckDB）在 S2 采用 | SESSIONS.md 的 S2 范围明写"SQLite 实验账本"，PLAN 的 Phase 1 也这样写；没有单独再问用户 |
| 2026-10-08 | S2 | x 的形状定为 `SqlCase(engine, setup, query, predicate)`。`full_query(case)` 规定怎样把谓词并进查询：没有谓词原样返回；分组或去重形态用旧 `tlp_groupby.build_query` 把谓词放在 GROUP BY 之前；其余用旧 `tlp.inject_predicate`，拼出不合法 SQL 时执行报错、标签为 invalid | 编排者定。TLP 与 NoREC 的旧接口要求谓词单独给；三个 oracle 共用一种 x，plan variant 与确定性筛查需要一条完整语句 |
| 2026-10-08 | S2 | 标签字段：`fail_kind` 取 wrong_result / error_mismatch / crash；`invalid_reason` 登记七种来源（setup_error、nondeterministic、not_applicable、query_error、value_dependent_error、timeout、harness_error）；`oracle` 取 PLAN 确认的七类 id；`cve` 留空 dict 给 S4 | PLAN.md 第 3 节：崩溃是 fail 的子类型；Phase 1 要求 invalid 来源统一登记。查询层面的"不适用"归 invalid（更新 Kᵛ），引擎层面的"不适用"留给 S3 |
| 2026-10-08 | S2 | 适配器只包不改：fail 当且仅当旧 oracle 的 `check()` 返回 Candidate；适配器用一个记录每次执行的 runner 代理，把旧接口的 None 拆成 pass 与 invalid。拆分规则：有超时判 timeout；有报错且全是值依赖错误判 value_dependent_error，否则 query_error；全部成功才是 pass。筛查顺序固定为 setup → 确定性 → 前提 | PLAN 总原则第 2 条"判定代码只搬不改"。确定性筛查必须在调用旧 oracle 之前：实测含 `random()` 的查询会让三个旧 oracle 都报出假差异 |
| 2026-10-08 | S2 | plan variant：切换开关的语句不参与判定；个别变体超时或报值依赖错误时跳过该变体，其余变体一致仍判 pass；一个变体都没比较成才判 invalid | 贴合旧 oracle 的语义（它对这些情况是 `continue`）。DuckDB 1.5.5 上有开关语句本身就报错，不能把它们算作查询失败 |
| 2026-10-08 | S2 | S2 的身份证据：`switches` 取 plan variant 见证差异的变体标签（TLP、NoREC 为空）；`error_class` 取报错文本第一个冒号之前的部分；`behavior` 取 `{missing, extra}` 两个计数 | PLAN 逐项表：plan variant 的开关集同时是 bisect 的干预基。最小 fix set、plan diff、版本梯要等 S4 的画像 |
| 2026-10-08 | S2 | TLP 接入 `tlp_groupby`：适配器从查询文本识别两种形态（选择列表等于分组键的 GROUP BY；SELECT DISTINCT），其余不适用。PINOLO-lite（`conjoin`）不接 | 旧 `tlp_groupby` 要求调用方拆好了传入，没有现成的驱动；x 里只有一个谓词，PINOLO 需要第二个。PINOLO 不在七类之内 |
| 2026-10-08 | S2 | harness 哈希的范围是 `surprise/harness/**/*.py` 加十个旧模块（`oracles/` 下的 tlp、tlp_groupby、norec、plan_variant、errors、determinism、normalize、models、db_runner 和 `targets/duckdb_runner.py`）；文件摘要先把 CRLF 归一成 LF | 适配器调用的是旧模块，只哈希新代码查不出旧判定逻辑被改。本机 git 开着 `core.autocrlf`，同一提交在不同检出里行尾可能不同；实测主检出区与 worktree 算出的哈希相同 |
| 2026-10-08 | S2 | 账本只能追加；每次写入在返回前提交；整条记录存规范 JSON，另拆 run、seq、oracle、y、理论代号等列供查询；库里记 schema 版本，版本不符拒绝打开 | PLAN 总原则第 5 条：每次执行都留账，指标只从账本算 |
| 2026-10-08 | S2 | `evaluate()`：判定过程中的异常记成 invalid / harness_error 并照样入账；凡是会让记录构造失败的参数在执行前拒绝 | "每次执行都进账本"是 S2 的门槛项。后半句是审查时发现的缺口，见下一条 |
| 2026-10-08 | S2 | 审查 s02-oracles 时给 `gates/s02.py` 的 evaluate 组补了一项检查（坏参数必须在执行前被拒绝，没有 runner 被打开、没有新记录），提交 522434c；并让该包返工一轮 | 任务说明和门槛都漏了：`purpose`、`p_t`、`spec` 原先在判定之后才校验，参数不合法时出现"执行了但没记账"。补的检查先实测能拦下第 1 轮的代码，再发返工意见 |
| 2026-10-08 | S2 | 拆包：s02-contracts（契约、常数、账本）先合并，然后 s02-manifest 与 s02-oracles（含 `evaluate`）并行。门槛分五组并支持 `--only`，每个包跑自己的几组 | ORCHESTRATION.md 第 8 节。账本的表结构与实验记录契约绑得紧，放进共享接口那一包；`evaluate` 依赖账本与适配器，归到后做的那个包，省掉一个串行的集成包 |
| 2026-10-08 | S2 | 门槛用例表 `gates/s02_cases.py` 的期望值是派发前用旧 oracle 在 DuckDB 1.5.5 上实测的；编排者另写了一份一次性的参考映射，把 20 个用例 × 3 个 oracle 的期望逐项核对过（含两次判定一致）。参考映射没有入库 | 门槛先于实现写，期望值写错会白白用掉返工轮次。实现代码全部来自 grok 分支 |
| 2026-10-08 | S2 | 门槛的已知复现只用 F1、F2、F7（plan variant）和账本条目 AUTO-a8be20c9、AUTO-ad38bad6 的最小化用例（TLP、NoREC）；不用 F3、F8（未指定语义）、F9（调试开关）、F10（会让进程崩溃）、F5、F6、F11 | S2 的 fail 是未经 CVE 的原始判定；前三类的最终标签要等 S4。F10 实测会直接杀掉解释器进程。F5 本机抓不到，F6 的 recall 条目没有数据，F11 是 MERGE |
| 2026-10-08 | S2 | s02-manifest 第 1 轮被编排者误操作终止（`gw status --wait --timeout 9` 的 `--timeout` 是包的运行上限），随后用 `gw resume` 在原会话续跑。这一轮不算质量返工 | 当时分支上没有提交、没有未提交文件，续跑保留了已有的分析。教训写进 HANDOFF 的操作提醒 |
| 2026-10-08 | S2 | 工作包结论：s02-contracts 一次通过；s02-manifest 质量上一次通过（另有上一条的续跑）；s02-oracles 返工 1 轮（起因在任务说明）。grok 上报花费合计约 3.16 美元 | 编排者独立复跑：合并后 pytest 149 passed、门槛 2/2。读完全部新代码；核对了三个包各自的全部 shell 命令与文件路径 |
| 2026-10-08 | S2 | 审查 s02-oracles 时在门槛之外做了一次差分核对：60 个种子经旧变异器得到 196 个用例，三个 oracle 各判两次共 588 组，与一份直接调用旧 oracle 的独立映射比较，出入为 0 | 门槛只有 20 个固定用例；种子变异能碰到真实的超时、值依赖错误和 error_mismatch。脚本在 `.orch/scratch/`，不入库 |
| 2026-10-08 | S2 | 归档的审查结论事后订正过三处，各一个提交：一个数错的测试函数个数、一句写错模块名的话、一个被展开成真实 NUL 的转义序列 | 都是编排者自己写结论时的错，订正后内容属实；NUL 字节会让 git 把文件当二进制 |
| 2026-10-08 | S2 | 编排者的审查辅助脚本改放 `.orch/scratch/` | 会话的临时目录在 S2 中途失效，放在里面的脚本不能再用 |
| 2026-10-09 | S2 修订 | 用户验收时把点名的五处人工检查项交给编排者自行决定。本次只改 HANDOFF.md 与 DECISIONS.md，不改代码和门槛；合并后打 `s02-done-r2`，S3 从它起 | 用户指示（"这些内容你都自行判断决定，不要问我"）。做法沿用 S1 的验收修订 |
| 2026-10-09 | S2 修订 | 契约维持分放 `harness/contracts.py` 与 `theory/contracts.py` | 冻结边界与"谁写"的边界是同一条线；harness 不依赖理论层 |
| 2026-10-09 | S2 修订 | "不适用"维持为 `invalid / not_applicable`，不设第四个标签值；统计无效率时把它单列 | 三值标签是 PLAN 定的，S3 门槛说的"明确不适用"用它表达。它不说明用例坏，混在无效率里会误导 |
| 2026-10-09 | S2 修订 | 划分谓词只对 TLP 认识的三种形态有定义，其余形态再给谓词判 invalid；`full_query` 不改 | 别的形态可以把过滤条件写进 `query`、`predicate` 留空，不损失可测的查询；invalid 不计惊讶，偏保守 |
| 2026-10-09 | S2 修订 | S4 门槛（M1）对已知复现的期望照 HANDOFF"S4 门槛（M1）对已知复现的期望"一节的表：F1、F2、F7、F9、F11、F6 判 fail；F3、F8、F5 判 invalid；F10 判 invalid 并记为召回缺口 | SESSIONS.md 只写了"confirmed 族全部判 fail"，没有逐族落实。表里每一格都有本机 DuckDB 1.5.5 的实测 |
| 2026-10-09 | S2 修订 | F5 归 invalid（重跑不稳定），用 `recall_repros.json` 的条目；`duckdb/F5_parallel_cte_offset.sql` 期望 pass | PLAN 标签规则：重跑不稳定的归 invalid。实测 recall 条目 200 个新连接错 20 次；`.sql` 文件的变体 80 次全对 |
| 2026-10-09 | S2 修订 | F6 用重建的复现：recall 条目的表结构与查询加三行数据；身份证据以 S4 的二分为准，不要求等于该条目的空 `fix_set` | recall 条目没有数据，`.sql` 文件的数据复现不出来，原始见证不在仓库。补上数据后 plan variant、TLP、NoREC 都判 fail |
| 2026-10-09 | S2 修订 | F10 在 M1 不要求判 fail，也不新写识别帧子句的确定性筛查；会让进程崩溃的两条语句改作新进程执行器的验证用例 | 旧筛查把帧子句当排序键，显式写帧的窗口查询一律判不确定。改它是新的判定逻辑，与 PLAN 总原则第 2 条冲突，要用户明确同意 |
| 2026-10-09 | S2 修订 | 写数据的语句（MERGE 等）在 S4 第 1 档只接受 crash，wrong_result 候选判 invalid | plan variant 在同一个连接上依次跑各变体，后面的变体看到的是被改过的数据。F11 是 crash，不受影响 |
| 2026-10-09 | S2 修订 | F9 在 M1 判 fail，"调试开关一档"只作报告时的分层 | 标签只由 oracle 与 CVE 决定；账本把 F9 算作一族，被剔除的只有 F4 那种护栏报错 |
| 2026-10-09 | S3 | Codex 接替 Claude Code 担任 PI，实现继续通过 grok_worker.py 派发给 grok；每合并一包立即提交 HANDOFF 状态 | 用户本会话指示，既有编排流程不变 |
| 2026-10-09 | S3 | PostgreSQL 16.15 免安装二进制放 `.orch/pg16/`；由 pg_ctl 启动本机 127.0.0.1:55432，不注册系统服务，使用 psycopg2，不安装 pgserver。默认 DSN 为 host=127.0.0.1 port=55432 user=coevo dbname=postgres，COEVO_REFERENCE_PG_DSN 可覆盖。用独立事务隔离各参照用例，close 回滚 | 用户明确授权本机准备 PG16。SQLite 对两个 ALL 语句报语法错；pgserver 未安装且仅二进制 pip 下载无版本。EDB 官方源 https://get.enterprisedb.com/postgresql/postgresql-16.15-1-windows-x64-binaries.zip；本地 SHA256 25e6fcdfb8caec38691bf461125e7564508760666f7b8e5dc6a5f0818f58f81e。首次 initdb 在解压未完成时失败，等待解压完成后成功，无数据被覆盖 |
| 2026-10-09 | S3 | Cross-DBMS 的 DF-A/DF-B 用 DuckDB、DataFusion、PostgreSQL 三个独立引擎；SQLite 报错不能算投票。DF-B 正确 bag 包含 NULL，门槛为 1、2、NULL，旧 SQL 注释不改 | 派发前在本机三引擎实测；保持法定数，SQL 注释订正留 S12 |
| 2026-10-09 | S3 | Version differential 回归门槛选 F2；1.1.3 为 (10,30)/(20,30)，1.5.5 为 (10,10)/(20,20)，新版 plan variant 独立见证 wrong_result。不选 F3 | 从 FAMILY_LEDGER_155 的版本梯挑选并先实测；F3 的 ASOF 并列语义未指定 |
| 2026-10-09 | S3 | 先合并 registry 包，公共文件只归它；local 与 cross 并行，cross 合并后派 version，最多两包运行。七类共用显式 options；S2 原有拒绝 DataFusion/index_presence 的过时接口断言由 registry 包定向更新为新的支持行为，保留并强化未知 ID/未知引擎拒绝测试 | 用户指出公共文件冲突与引擎覆盖缺口；这是需求变化必需的测试更新，不删有效断言、不放宽错误判定 |
| 2026-10-09 | S3 | s03-registry 合并：返工1轮，只修新增测试假定后续模块不存在的问题；使用monkeypatch模拟缺模块，保留导入失败与harness_error记账断言。独立pytest165 passed/3 skipped，S01 7/7、S02 5/5、S03 registry PASS。两轮约0.9707美元 | 编排者完整diff、返工diff、全部15条shell命令审查。没有改旧实现、门槛或conftest，没有新增skip/xfail；部分门槛因未派发包而红是预期 |
| 2026-10-09 | S3 | registry懒导入后由模块自行register，避免并行包改公共文件；old_python为字符串路径；参照None表示默认、空dict表示无参照 | 共享接口实现选择，后三包brief已同步。不改变PLAN契约 |
| 2026-10-09 | S3 | 首包合并时嵌套PowerShell提前展开ORCH_COMMIT_TRAILER，赋值失败但merge已成功；保留历史不重写。后续用.orch/scratch/s3_gw.py设置子进程环境并调用原grok_worker.py，尾注Co-authored-by: Codex <noreply@openai.com> | 编排者命令转义错误，未影响代码和审查。辅助脚本不入库，标准gw恢复命令仍可用 |
| 2026-10-09 | S3 | Cross审查补门槛：拒绝SELECT 1; SELECT 2、SELECT 1; SET ROLE，以及setup中嵌入COMMIT/END，拒绝必须在后端执行前发生。第1版独立复跑确实被此门槛拦下，要求返工 | PG runner承诺单条只读查询和未提交的独立事务，但第1版只检查首词。setup使用不连DB的记录runner作反例，不让测试本身提交schema；属于S3参照runner隔离要求 |
| 2026-10-09 | S3 | local审查补门槛：De Morgan拒绝BETWEEN和CASE内部AND；paired_query不能忽略字面量大小写。第1版两引擎实测把有效原查询改成非法SQL并假报fail/error_mismatch，要求返工1轮 | 证明只覆盖逻辑二元AND/OR，不覆盖语法内部AND；不扩大规则覆盖，保守invalid/not_applicable。字面量变化的外部pair按untrusted_rewrite拒绝 |
| 2026-10-09 | S3 | version派发前补双支路门槛：F2有参照与空参照都fail/regression；DuckDB和DataFusion的SELECT version()无参照都invalid/direction_unknown | 已实测DF54/PG16/SQLite3.51的F2都等于旧DuckDB结果，新版plan variant独立fail并有no_optimizer身份；两引擎版本字符串只是metadata变化 |
| 2026-10-09 | S3 | cross第2轮返工只补WITH起头的SELECT INTO执行前拒绝；不因第1轮多语句修正通过就接受遗漏的只读前提 | 第1轮独立pytest186 passed/3 skipped，多语句cross组通过；新断言实测WITH x AS (SELECT 1 AS a) SELECT a INTO z FROM x被错误接受。返工上限仍为2，不扩授权 |
| 2026-10-09 | S3 | local第2轮只修E转义字符串词法边界；同类字符串内SQL文本不得成为改写产物。不增加规则或依赖 | 第1轮修正后新增独立实测：转义引号包裹的CASE文本被当成代码改写，两引擎假fail/wrong_result。保守拒绝不支持的引号形式可以接受；门槛自己的SqlCase漏导入改用现有case()助手，未归咎执行者 |
| 2026-10-09 | S3 | s03-cross合并a60a287，返工2轮（多语句/事务边界、WITH SELECT INTO），共2.8134美元。PostgresReferenceRunner只作参照，不新增PG目标引擎；三引擎法定数不变 | 独立pytest188 passed/3 skipped，S01/S02与增强cross PASS；完整代码/返工diff和全部29条shell命令审查。14处捕获为参照错误/版本回退/清理，假密码扫描命中是测试数据。无新skip、越界修改、LLM标签或旧逻辑改变 |
| 2026-10-09 | S3 | s03-local合并0293ace，返工2轮（De Morgan语法/pair校验、E字符串边界），共2.3360美元。规则库只取double_negation、demorgan、case_to_coalesce；U&不适用，pair只容许关键词大小写/外部空格/单尾分号变化，引用文本/标识符/评论变化拒绝 | 独立pytest186 passed/3 skipped，S01/S02与增强local PASS；完整diff和全部30条shell命令审查。2万行另实测ART Index Scan；不强制小表计划使用索引，比较的是索引有/无的结果。无新skip、越界或旧逻辑修改 |
| 2026-10-09 | S3 | version预读补门槛：同类型值的两版DF结果应pass；unordered bag证据必须稳定；双方查询错误invalid/query_error；非零退出或缺实际版本号的响应invalid/harness_error | PI先实测两个DF版本的DATE、bytes、Decimal原始类型/值一致，再对草稿独立复跑，确认日期格式假回归、行序标签不稳定和协议失败假pass。用真实成功worker响应作故障注入基准，不凭造出来的期望行定方向 |
| 2026-10-09 | S3 | 旧Cross DATE格式假差异登记S4前提检查，不改旧normalizer、不扩S3为CVE或追加Cross包；Version新增的DF新旧传输适配缺口仍由本包修正 | 独立调用旧CrossEngineOracle与新raw Cross：同一DATE查询，DF ISO字符串对DuckDB/PG temporal前缀，旧版已产候选，新版raw fail。用户明确计划外只记未决、不顺手修；该候选不应算确认bug，S4冻结前必须处理比较前提 |
| 2026-10-09 | S3 | version第1轮返工澄清：双方成功返回同一错误bag仍pass，双方查询错误invalid；DF旧typed JSON在主进程按同一目标runner的旧归一化接口适配，不改任何旧代码 | 初版独立216 passed/3 skipped；PI原brief“都错”有歧义，新增错误pass测试须定向更正。反例/协议边界已实测，反馈包含稳定bag证据、完整见证标签、仅跳过确实缺模块。递归tmp删除被deny后空目录仍保留，取消该部分没有实现原被拒动作；返工禁止再清理tmp |
| 2026-10-09 | S3 | s03-version合并7454d8d，返工1轮；修正DF传输兼容、证据bag排序、错误标签及子进程协议。完整见证Label含SQL；只跳过精确缺失的可选index模块。两轮2.8079美元 | 独立pytest221 passed/3 skipped，S01/S02及增强version PASS；完整3文件/返工diff及全部34条shell命令审查。独立反例逐项通过，无新skip/xfail、越界修改或LLM判定；被deny的tmp目录仍在，返工无清理重试。原新增测试的语义修订由PI明确授权，不降低门槛 |
| 2026-10-09 | S3 | 最终四包集成独立242 passed/3 skipped，S01 7/7、S02 5/5、S03 5/5，GATES PASS 3/3。无推翻，registry/local/cross/version返工分别1/2/2/1轮，约8.93美元；收尾main+s03-done，清理已合并worktree | 真实七类×两引擎与14条账本记录通过，旧实现及受保护文件零改动，manifest39文件哈希59255df29e81050de12488862127e21c18762c2f1a5acc8edf2d28f377bae33e；无新增skip/xfail或LLM标签 |
| 2026-10-09 | S3 | 人工检查均由PI决定：PG只作事务隔离参照；三条证明改写保守筛查；ART比较索引有无且另查2万行Index Scan；Version按目标runner兼容归一化并保留完整见证；继承Cross DATE假候选交S4前提检查 | HANDOFF记录接口、恢复命令、边界和未决问题。旧DF仍无duckdb/psycopg2，PG遗留schema为0；最终审计通过，不扩大S3为CVE或修改旧逻辑 |
