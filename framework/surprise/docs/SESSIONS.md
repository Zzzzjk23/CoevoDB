# SESSIONS · 实施会话

每个会话一节：范围、复用、门槛、不做什么。开场提示词见项目文档 `claude/coevodb-session-runbook.md`（所有会话共用一段，只换编号）。门槛脚本统一放在 `framework/surprise/gates/sNN.py`，退出码 0 = 通过。

一个会话 = 一个可验收的交付物，不是固定工作量：提前做完也不顺手开下一个；做不完就拆成 S{n}a / S{n}b，共用同一个门槛。关键路径是 S1–S8，做完即得"新框架无 LLM 版"。

S0–S12 是迁移到惊讶驱动框架的改造（已完成）。S13 起是正式实验：S13 定协议（`EXPERIMENT.md`），S14–S18 准备服务器与新引擎，S19–S25 跑里程碑 E1–E7 并出报告。正式实验阶段服务器上的分工见 `EXPERIMENT.md` §7。

---

## S0 · 编排准备

不计入 12 个会话：只搭派发工具，为 S1 起的"Claude Code 编排 + grok 执行"模式做准备（见 `RUNBOOK.md` 第 2 节、`ORCHESTRATION.md`）。

范围：
- 派发脚本 `tools/orch/grok_worker.py`（只用标准库）：`spawn`、`status`、`review`、`resume`、`merge`、`cleanup`，另有 `list`。
- 任务说明模板 `framework/surprise/docs/orch/BRIEF_TEMPLATE.md`。
- 编排流程与审查清单 `framework/surprise/docs/ORCHESTRATION.md`。
- CLAUDE.md"执行者模式"一节的草稿：只给用户看，用户同意后才写入。
- `.gitignore` 加 `.worktrees/` 与 `.orch/`；本文件加这一节；`HANDOFF.md` 状态表加 S0 一行。

门槛（没有 `gates/s00.py`：`surprise.gates` 由 S1 建立，S0 用冒烟包验收）：无害的工作包 `s00-smoke`（在 worktree 里新建 `scratch/hello.txt` 并提交）走完 `spawn → status → review → cleanup --abandon`，并确认四件事：grok 无交互跑完；让它试一次 `git tag`，被 deny 规则拦下；日志可读；子进程里没有 `DEEPSEEK_API_KEY`。

不做：S1 的任何范围；任何框架代码。

---

## S1 · Phase 0 · 冻结基线与仓库整理

范围：
- 确认仓库在 git 管理下（不是就 `git init`）。补 `.gitignore`：`.venv/`、`.uv-cache/`、根目录 `results/`（现在只忽略了 `framework/results/`）。确认 `.env` 没有被跟踪。
- 在任何改动之前打 tag `v1-baseline`。
- 记录测试基线：`cd framework && pytest -q testing tests` 的通过数，写进 HANDOFF.md。
- 跑一次旧系统基线 run 并存档：`python main.py --engine duckdb --mode no_llm --iterations 2`（必做）。full 模式短跑需要 DeepSeek，可选。
- 仓库整理，只移动、不改逻辑：
  - PG 专项脚本（`framework/scripts/pg_*.py`）移到 `framework/campaigns/`，与 `scripts/` 保持同一目录深度，这样脚本里 `sys.path` 的相对定位不用改。如有 `scripts.pg_*` 形式的互相导入，只改导入路径；牵连太多就原地不动，在 DECISIONS.md 记一笔。
  - DuckDBRunner 移到 `framework/targets/duckdb_runner.py`；`oracles/db_runner.py` 保留为兼容导入（re-export），旧代码不用改。
  - `coevo/` 本会话不动：`tests/test_verified_loop.py` 依赖它。它的新进程执行在 S4 被吸收，S12 再归档。
- 建 `framework/surprise/` 骨架：`__init__.py`，子包 `harness/ features/ theory/ hunter/ diagnoser/ roles/ metrics/ experiments/ baselines/ gates/`；`gates/all.py` 依次运行 `gates/s*.py`。`docs/` 已由规划会话放好。
- 运行环境：DuckDB 1.5.5（主环境）、DuckDB 1.1.3（独立 venv）、DataFusion 54.0.0、一个更早的 DataFusion 版本（独立 venv，供 Version differential）、SQLite（标准库）；PostgreSQL 可选。把各 venv 路径与版本填进 CLAUDE.md 的"引擎环境"。

门槛 `gates/s01.py`：骨架存在；每个环境能 import 并打印版本；`python main.py --help` 正常；pytest 通过数与整理前一致。

不做：任何逻辑改动；新框架代码。

备注：本会话开始时 `surprise.gates.all` 还不存在，起点检查只跑 pytest。

---

## S2 · Phase 1a · 契约、账本、冻结机制、三类健全 oracle

范围：
- 五个数据契约（实验记录、标签、规格、假设、理论编辑）的类型定义与序列化，字段见 PLAN.md §4。
- SQLite 实验账本：写入、按 run 与理论代号查询；pass 和 invalid 也全部记录。
- run manifest 与 harness 哈希校验命令。
- TLP（同时接入现在无人调用的 `oracles/tlp_groupby.py`）、NoREC、Plan variant 的三值适配器：pass / fail / invalid + 身份证据。此时的 fail 是未经 CVE 的原始判定。

复用：`oracles/tlp.py`、`tlp_groupby.py`、`norec.py`、`plan_variant.py`、`errors.py`、`determinism.py`、`normalize.py`。

门槛 `gates/s02.py`：同一输入两次判定一致；已知复现里这三类能抓的判 fail；值依赖错误样例判 invalid；每次执行（含 pass）都进账本。

不做：CVE 流水线；φ。

---

## S3 · Phase 1b · 其余三类 oracle 与 Index presence 移植

范围：
- Index presence 移植到 DuckDB（ART 索引有 / 无）；DataFusion 没有索引，标"不适用"。
- Equivalent query 的确定性改写规则库：从旧提示词列出的改写种类里挑能机械实现的（如 in_to_exists、exists_to_in、demorgan、union_expansion、case_to_coalesce），每条规则附等价性论证与反例测试，注意 NULL 三值逻辑。
- Version differential：DuckDB 1.5.5 对 1.1.3，DataFusion 新对旧。方向判定：旧版结果得到其他引擎多数支持，或新版被前四类之一独立见证，才判 fail 并记为回归；否则 invalid。
- Cross-DBMS differential：把 `scripts/cross_engine.py` 的多数表决（`classify_divergence`）并入 oracle 层；≥3 个引擎且目标引擎是唯一异类才判 fail，否则 invalid。

复用：`oracles/index_variant.py`、`equivalence.py`、`differential.py`、`_remote_exec.py`、`cross_engine.py`。

门槛 `gates/s03.py`：七类在 DuckDB、DataFusion 上都产出三值标签或明确"不适用"；`datafusion/` 下 DF-A、DF-B 复现被 Cross-DBMS 判 fail；至少一个已知回归被 Version differential 判 fail 且方向正确；构造的不等价改写判 invalid。

不做：LLM 生成的改写。

---

## S4 · Phase 1c · CVE 分层流水线（里程碑 M1）

范围：
- 第 1 档（所有差异候选）：新进程重跑 + oracle 前提检查。吸收 `coevo/executor.py` 的子进程隔离、`oracle_repetitions`、`scripts/flaky_mine.py` 的 threads=1 复判。不过即 invalid，通过即标 fail。
- 第 2 档（预测落在已有假设里的失败）：归属测试接口。有开关的引擎用 fix set 的 prelude 复跑；无开关的引擎比对错误类别与行为画像。身份不一致则升到第 3 档。
- 第 3 档（要交给 Diagnoser 的失败）：最小化（`bug_fixer._minimize`）+ 完整画像（`diagnosis/bisect.py`、plan diff、版本梯）。最小化后不再复现或违反前提，标签降为 invalid 并记账。
- 本会话结束后 harness 冻结：manifest 记录哈希与常数。

门槛 `gates/s04.py`（M1）：
- `docs/recall_repros.json` 与 `duckdb/`、`datafusion/` 下的 `.sql` 复现中，confirmed 族全部判 fail 且身份证据正确；
- 被降级为 unspecified-semantics 的族（如 F3、F8）判 invalid；
- 一组普通查询判 pass；已知假阳类（值依赖错误、无序结果、不等价改写）判 invalid；
- manifest 校验通过。

不做：理论 T（第 2 档只实现接口，用一个手写的已知假设调通）。

---

## S5 · Phase 2 · 共同语言 φ

范围：
- φ 抽取：sqlglot AST、各引擎 EXPLAIN 计划算子、在库上用查询计算的数据性质（如"左侧有重复行"，而不是扫 INSERT 文本）。
- 特征类：支撑"换同类取值"（如 EXCEPT ALL / INTERSECT ALL / UNION ALL）和"删一个特征"。
- 单元：φ 的粗投影，作为 R 的索引。
- 词表注册表：预留 LLM 发明特征的接口，记录来源与验收结果。
- 规格语言与核对器：φ(x) ⊨ spec。

复用：`coverage/features.py` 的特征清单作起点。

门槛 `gates/s05.py`：φ 跨进程稳定；DF-A、DF-B 与 DuckDB F1–F11 的最小复现两两可区分；规格核对器在一组手写 spec / SQL 对上全对；输出单元在 `seeds/corpus.json` 上的分布报告。

不做：理论 T。

---

## S6 · Phase 3a · 理论 T 核心

范围：
- 假设 h = (I, ΔP, V, S, G, E⁺, E⁻) 与版本空间更新规则：正例泛化 S、反例特化 G、身份一致才算正例。
- 新家族的确定性初始化：I、ΔP、V 取自 CVE 画像；无开关引擎用错误类别 + 行为画像。
- R（每单元计数与未解释失败）、Kᵛ（按实验类与 oracle 的无效率）、P_T、惊讶、六类分诊。
- 常数（0.95、0.5、分诊阈值）写入 manifest。

门槛 `gates/s06.py`：用手写的 h2 代替 LLM，把框架文档 DF-A → DF-B 案例的确定性部分走一遍：第一次失败惊讶约 6.6 比特；两个预测实验各约 1.0 比特；left_has_dups 进 G；INTERSECT ALL 失败因身份不一致开新家族 h3。

不做：持久化与回滚（S7）。

---

## S7 · Phase 3b · 理论存储与接受规则

范围：每个假设一个结构化文件；按代快照（供 CIAO）；编辑日志（理由 + 押注的预测）；预测落空自动回滚并进负记忆；留出验收（触发记录上惊讶下降、留出记录上不上升）；MDL 拆分 / 合并。

门槛 `gates/s07.py`：
- 离线喂入已知复现与重新生成的 DCE 探针（`evolution/dce.py`）：惊讶落在约 6.6 / 4.3 / 1.0 / 0.07 / 0.01 比特的量级；
- 重复在执行前被识别；
- 家族划分与人工账本（`docs/manual_findings.jsonl`、`docs/FAMILY_LEDGER_155.md`）的一致度不低于 σ；
- 一条故意错误的编辑被回滚并进负记忆。

不做：Hunter。

---

## S8 · Phase 4 · Hunter 与无 LLM 闭环（里程碑 M2）

范围：
- 四类候选：细化、泛化走变异车道（复用 `evolution/dce.py` 的算子与 `seeds/mutate.py`）；迁移在无 LLM 时只做字面改写；探索采样未测单元。
- 打分 value = P_valid × (D + β·U)；探索保底名额；派生探针过多的假设降权；按 φ 新颖性拒绝采样。
- 新主循环入口：Hunter → 执行与 CVE 标注 → 惊讶 → 分诊 → Diagnoser（无 LLM：ddmin + bisect + 版本空间规则）→ 接受或回滚 → 更新 T。

门槛 `gates/s08.py`（M2）：DuckDB 上数小时 run 不崩；惊讶曲线（每 100 次执行的均值）呈锯齿；同执行预算下重复率低于原 CoevoDB 的 no_llm 基线；DuckDB 1.1.3 上的已知 bug 召回报告；同种子重跑结果一致。

不做：任何 LLM 调用。

备注：β 只在一组独立种子的预实验里调一次，然后写入 manifest。

---

## S9 · Phase 5a · LLM 网关、实现器、假设猜想者

范围：
- LLM 网关（复用 `agents/base_agent.py`、`llm/ledger.py`）：响应缓存，键为提示哈希 + 模型 + 种子；按角色记账；每个角色的输出 schema 必带"预测"字段，缺则拒收；每个会话设调用上限；至少支持两档模型。
- 实现器：spec → schema、数据、查询，用 φ 核对验收。
- 假设猜想者：读最小复现、fix set、计划差异和优化器源码，给出机制、触发条件和可证伪预测；预测登记为待检实验。需要 DuckDB / DataFusion 源码检出与只读的读源码工具。

门槛 `gates/s09.py`：缓存命中时零网络调用、重放结果一致；缺预测的输出被拒收；实现器 SQL 的 φ 核对通过率报告；猜想者在 DF-A 上给出带预测的假设并登记为待检实验。

不做：其余四个角色。

---

## S10 · Phase 5b · 其余四个 LLM 角色（里程碑 M3）

范围：
- 探索先验：读文档、发布说明、历史 bug，给未测单元先验失败率；用 Brier 分数校准。
- 迁移翻译者：把一个引擎上的假设翻成另一个引擎的开关与写法；用归属测试和 bisect 检验。
- 词汇发明者：确认区反复意外通过时提议新的可执行特征；过留出验收才入表。
- oracle 发明者：提议等价改写或蜕变关系；多引擎一致才进入 Equivalent query 的改写规则库，判定代码不变。
- 每个角色一个配置开关。

门槛 `gates/s10.py`（M3）：每个角色可单独开关、关掉时零调用；DataFusion 54.0.0 上从 DF-A 出发闭环复现 DF-B，固定缓存后可重放。

不做：评估管线。

---

## S11 · Phase 6 · 评估管线（里程碑 M4 冒烟）

范围：
- 从账本计算全部指标：惊讶曲线、CIAO 矩阵、分层冻结、跨代配对、LLM 预测准确率随时间变化、Brier 与校准曲线、猜想存活率、重复率、无效率、理论长度、留入 / 留出差距、假设边界与上游修复提交的吻合度、已知 bug 召回、每家族成本。
- CVE 的覆盖度量：已知 bug 召回基准，以及重放 `seeds/` 里解析好的上游回归测试。不参与打标签。
- 把 `scripts/gate2.py`、`scripts/coevo_curve.py` 泛化成配置驱动的实验网格：臂 × 种子 × 时长 × 重复；报告中位数、Mann-Whitney U、Vargha-Delaney Â₁₂。
- 对照组：SQLancer（读入已有基线结果）、原 CoevoDB、纯 LLM 生成、新框架无 LLM 版。
- 离线去重对比：原 CoevoDB 的 σ 去重 vs 执行前成员检验。

门槛 `gates/s11.py`（M4 冒烟）：2 臂 × 2 种子的短时网格跑通；RQ1–RQ6 指标与图一条命令生成。

不做：24 小时正式实验；SQLancer++（暂不纳入）。

---

## S12 · Phase 7 · 收尾

范围：旧主循环（`main.py`、`evolution/`、`agents/`、`guidelines/` 等）移入 `framework/surprise/baselines/coevodb_v1/` 并保持可运行；与新包共用的原语只保留一份；`coevo/` 与 `repair_bench/` 归档；README、架构文档、`framework/AGENTS.md` 更新。

门槛 `gates/s12.py`：原 CoevoDB 臂在新位置可跑；s01 到 s11 的全部门槛仍通过。

不做：新功能。

---

## S13 · 正式实验设计

范围：
- 把用户 2026-10-19 定下的正式实验设计写成 `framework/surprise/docs/EXPERIMENT.md`：引擎与版本、臂与消融、时长与种子、统计、调度与资源、里程碑与顺序、服务器分工、执行规则，末尾附门槛读取的机读清单。
- `PLAN.md` 加 §9 记新决定，并在与之冲突的旧条目旁注明；本文件写 S13–S25；`HANDOFF.md`、`DECISIONS.md` 照常更新，HANDOFF 里由这些决定了结的未决问题注明去向。

门槛 `gates/s13.py`：只核对文档。`EXPERIMENT.md` 的必备小节都在；机读清单里每个臂的每个配置键要么网格现在就认，要么写明由哪个会话补，每个引擎要么现在就是目标，要么写明由哪个会话接入，这些会话都在对应里程碑的前置里；按清单重算的格数与文中一致；正式种子与预实验种子互不重叠，也没在 `s12-done-r2` 的门槛与测试里出现过；本文件有 S13–S25 各节，每个里程碑的前置与运行会话都有对应一节；`PLAN.md` 有 §9；S13 的改动只在 `framework/surprise/docs/` 与门槛自己的两个文件里。

不做：任何代码、环境改动、真实运行；`CLAUDE.md`、`ORCHESTRATION.md`（要改先问用户）。

---

## S14 · 服务器部署与双平台门槛

范围：
- Claude 经 `ssh 3090` 搭服务器环境（用户确认服务器空闲时）：服务器上建空的 git 仓库，本机推送 tag，服务器工作目录只检出 tag；用 uv 装 Python 3.13.9 与 `.venv`、`.venvs/duckdb-1.1.3`、`.venvs/duckdb-1.1.3-full`、`.venvs/datafusion-50.0.0`；SQLite 3.51.0 单独钉住（Linux 上标准库 `sqlite3` 用系统库，版本要与 Windows 上一致）；PG 16.15 参照服务器；JDK；`.src/` 两份源码检出；`framework/results/s08/` 拷过去。
- 平台差异逐条记录；需要改的代码交给 grok 在本机 worktree 里改，两个平台都要绿。钉住的 S8 长跑产物与 Linux 对不上时，在服务器上按 S8 验收的办法重跑一份 Linux 的并另钉，Windows 的那份保留。
- 写给用户的运行手册：在 tmux 里启动网格、查看状态、生成报告、压缩并拷回结果的命令。

门槛 `gates/s14.py`：服务器上的环境版本表与约定一致；两个平台上 pytest 与 `gates.all` 都全绿；用户照运行手册在服务器上跑通一次 1 分钟的冒烟网格。

不做：新功能；改旧代码的逻辑；动 harness。

---

## S15 · 实验基础设施

范围：
- 网格并行：固定并发度、块调度（同一引擎、同一种子下的全部臂为一批）、每格固定 CPU 份额与引擎线程数。
- `surprise` 格加墙钟强杀；`RunData` 改成流式读（24h 约 7 万条记录）。
- LLM 调用可以不设上限：网关的 `DEFAULT_MAX_CALLS` 与网格的 `max_calls` 都要能设成不限，默认行为不变。
- 每个臂可选模型档（A11 用 strong 档）；`pure_llm` 跟随目标引擎。
- 真正运行 SQLancer 的臂：固定 commit，日志里报出的用例转成 `SqlCase`，经同一套 CVE 画像换成同一种身份键；核实 SQLancer 是否支持 DataFusion。
- 价格表：从 DeepSeek 官方价格页取，注明日期，接进网格的 `prices`。
- 归档命令；运行手册补上并行与归档。
- 改了 `experiments/` 等目录，按 S8 验收的办法重跑长跑、重钉，再跑 S8 的四个产物组与 S11 的 `ciao`。

门槛 `gates/s15.py`：4 格并行冒烟；强杀；流式读的内存上限；SQLancer 臂在 DuckDB 上 10 分钟冒烟并产出家族键；换档开关；不限次数的 LLM 臂在缓存重放下跑通；旧门槛全绿。

不做：新引擎；harness。

---

## S16 · PostgreSQL 目标（解冻 harness 第一批）

范围：
- 把 PostgreSQL 16.15 接成目标：`TARGET_ENGINES`、runner、plan variant（旧 PG 开关组）、Index presence（原生）、Version differential（PG 15 系列）、Cross-DBMS 参照（DuckDB、DataFusion、SQLite）、φ 计划提取、CVE 画像；种子用已有的 PG 语料。
- 建新 manifest 并重新冻结（用户已同意分批解冻）。
- 目标是在服务器跑 E1 的 3–5 天里做完；赶不上，服务器空等。服务器上的部署（装 PG 15、每格独立实例）与回放检查由 Claude 在用户确认服务器空闲时做。

门槛 `gates/s16.py`：M1 式——`postgres/` 的已知复现判 fail 且身份正确、普通查询 pass、值依赖错误 invalid；七类 oracle 各给出三值或"不适用"；φ 跨进程稳定；回放检查（`EXPERIMENT.md` §8）通过；旧门槛全绿。

不做：别的引擎。

---

## S17 · DataFusion 语料与 SQLite 目标（解冻第二批）

范围：
- 从 `.src/datafusion-54.0.0` 的 `.slt` 解析 DataFusion 种子语料。
- 把 SQLite 3.51.0 接成目标：runner、plan variant（旧代码的 `SQLITE_VARIANTS`）、Index presence、Version differential（选定旧版并装环境）、Cross-DBMS 参照、φ 计划提取（EXPLAIN QUERY PLAN）、种子语料。
- 多引擎运行（A12/A13）在 DuckDB + DataFusion + SQLite 上跑通。部署与回放检查同 S16。

门槛 `gates/s17.py`：同 S16 的 M1 式检查（`sqlite/`、`datafusion/` 的已知复现）；DataFusion 运行有探索车道、不再 `exhausted`；回放检查通过；旧门槛全绿。

不做：TiDB、MySQL。

---

## S18 · TiDB 与 MySQL 目标（解冻第三批）

范围：
- TiDB v8.5 与 MySQL 8.4 接成目标，MariaDB 11.8 接成参照：runner（TiDB 已有 `targets/tidb_runner.py`，MySQL、MariaDB 新写）、plan variant（优化器提示、`tidb_opt_*`、`optimizer_switch`）、Index presence（`USE/IGNORE INDEX`）、Version differential（TiDB v7.5、MySQL 8.0）、φ、sqlglot 方言、种子语料（TiDB 集成测试、mysql-test）。
- TiDB 没有原生 Windows 版：代码在本机写，TiDB 部分的门槛在服务器空闲时跑。部署与回放检查同 S16。

门槛 `gates/s18.py`：同 S16 的 M1 式检查（`tidb/`、`mysql/`、`mariadb/` 的已知复现）；MYSQL-A 与 MDB-A 的三票表决按预期判 `invalid`；回放检查通过；旧门槛全绿。

不做：别的引擎。

---

## S19 · E1 DuckDB 主对比

范围（S19–S24 都照这个做法）：
- Claude 在本机按 `EXPERIMENT.md` §9 写好本里程碑的网格配置与运行单，提交并部署到服务器。
- 用户照运行单在服务器上先跑预实验（2h，种子 9101、9102），把吞吐、标签稳定性与 LLM 用量发回；Claude 据此定并发度，写进协议。
- 用户跑正式格、生成报告、把结果压缩拷回本机；Claude 核对结果，写分析报告与缺陷候选清单（在最新版上复核过）。
- 本会话：DuckDB 1.5.5 上 `full`、`nollm`、`pure_llm`、`sqlancer` × 种子 1001–1005，20 格。
- 2026-10-20：预实验跑完后暂停（用户的决定，PLAN §9 补充一条）。正式格等用户说了再跑；`pure_llm` 暂不跑。
- 2026-10-20 用户加进本会话的范围：LLM 角色换成 OpenRouter 上的 GLM 5.3 Flash（PLAN §9 补充一条），工作包 `s19-glm`。门槛 `gates/s19.py` 先有六组：`transport`、`gateway`、`replay`、`grid`、`prices`、`scope`；E1 结果的几组等正式结果拷回时再加。下面"不做：改代码"一条不适用于这个包。改了 `experiments/`，合并后要按 S8 验收的办法重跑长跑、重钉。
- 2026-10-21 用户加进本会话的范围：额度不足与报错的提醒，经 pushplus 一对一消息（PLAN §9 补充一条），工作包 `s19-notify`：新包 `surprise/notify/`（发送器与看守进程），`roles/gateway.py` 失败调用的 `reason` 记下传输层的消息（HTTP 状态码）。门槛 `gates/s19.py` 加五组：`pushplus`、`reason`、`watch`、`balance`、`cli`。不改 `experiments/`，不用重钉长跑。"不做：改代码"同样不适用于这个包。
- 2026-10-21 用户定下 GLM 的推理强度为 low（PLAN §9 补充一条），工作包 `s19-effort` 只改 `roles/providers.py` 的一处配置；门槛 `s19_cases.NEW_PROFILE` 跟着改。
- 2026-10-21 用户定下 429 退避重试（PLAN §9 补充一条），工作包 `s19-retry`：`roles/transport.py` 遇 429 按 `roles/constants.py` 新加的 `RATE_LIMIT_WAITS_S` 等待后重试，别的失败不重试。门槛 `gates/s19.py` 加一组 `retry`；`roles/constants.py` 从冻结路径移出，改由 `retry` 组核对只多了这一个常数、其余与 s15-done-r3 相同。不改 `experiments/`，不用重钉长跑。"不做：改代码"不适用于这个包。
- 2026-10-21 用户定下 503 也重试、服务商换成 sail-research/fp4 并按 open-inference/fp4、sail-research/us 的次序自动切换（PLAN §9 补充一条），工作包 `s19-providers`：`roles/providers.py` 的档案改成服务商列表，`roles/transport.py` 按列表逐家重试与切换，`roles/gateway.py` 记下回答的服务商（只在 GLM 的调用记录与缓存条目里多一个字段，DeepSeek 的不变），`roles/constants.py` 加 `RETRY_STATUSES`，OpenRouter 价格表更新。门槛改 `transport`、`retry` 与 `prices` 三组的期望。不改 `experiments/`。

门槛 `gates/s19.py`：拷回的结果里所有格 `done`；配置与 `EXPERIMENT.md` 一致；harness 哈希与部署时相同；报告的每个 RQ 节都有内容。

不做：实验跑着时动服务器；改代码（发现的问题记进 HANDOFF）。

---

## S20 · E2 PostgreSQL

范围：照 S19 的做法；PostgreSQL 16.15 上 4 个臂 × 5 个种子，20 格。前置 S16。

门槛 `gates/s20.py`：同 S19。

不做：同 S19。

---

## S21 · E3 DuckDB 机制

范围：照 S19 的做法；DuckDB 1.5.5 上 A2–A11 × 5 个种子（50 格）与 A14 跨代配对（45 个 1 小时格，用 E1 的理论存储）。前置 E1。

门槛 `gates/s21.py`：同 S19。

不做：同 S19。

---

## S22 · E4 DuckDB 召回与理论质量

范围：照 S19 的做法；DuckDB 1.1.3 上 4 个臂 × 5 个种子，20 格；另做人工真值抽样，供家族划分一致性。

门槛 `gates/s22.py`：同 S19；另加每个已知缺陷的召回与首次发现时间写进报告。

不做：同 S19。

---

## S23 · E5 嵌入式引擎泛化

范围：照 S19 的做法；DataFusion、SQLite 各 4 个臂 × 5、A12/A13 × 5、SQLite 上 A3–A5 × 5，共 65 格（SQLancer 不支持 DataFusion 时少 5 格）。前置 S17。

门槛 `gates/s23.py`：同 S19。

不做：同 S19。

---

## S24 · E6 TiDB 与 MySQL

范围：照 S19 的做法；TiDB、MySQL 各 4 个臂 × 5，共 40 格。前置 S18。TiDB 吃内存，并发可能只能 4 格。

门槛 `gates/s24.py`：同 S19。

不做：同 S19。

---

## S25 · E7 总报告

范围：跨引擎总表、各里程碑结论汇总、缺陷清单（上报状态取自 `docs/UPSTREAM_ISSUES.md`）。

门槛 `gates/s25.py`：报告里每个数字都能追溯到某个网格目录。

不做：新的运行。
