# CoevoDB 改造规划：迁移到惊讶驱动框架

2026-10-08 · 对应框架文档《惊讶驱动的 CoevoDB：新框架与故事》（2026-10-07）。本规划只定大方向，不含具体实现细节。
Claude Doc 版本（含架构图与路线图）：https://claude.ai/code/artifact/ce14c65b-9c26-497c-8261-a992c0396d6a

## 1. 目标与总原则

一句话策略：把旧系统里确定性的部分（执行器、oracle、最小化、干预二分、版本梯）冻结成环外评估器，在其上先建成"无 LLM 版"的惊讶闭环，再逐个接入六个 LLM 角色；旧主循环整体保留为"原 CoevoDB"对照组。（2026-10-19 起不再评估原 CoevoDB，见 §9。）

1. 并行新建，不原地改写。旧的 bandit + playbook + DCE 循环冻结成对照组。（正式实验不再用它作对照，见 §9。）
2. 判定代码只搬不改。oracle、φ 基础词表、惊讶公式、接受规则进 harness 并记录哈希；LLM 只能调用不能修改。
3. 无 LLM 版是第一个可运行里程碑（消融下界 + 可复现基线 + 最便宜的调试环境）。
4. LLM 角色一次接一个，每个都能开关，对上消融表。
5. 每次执行都留账（含通过、无效、被拒绝的提议）；所有指标只从账本计算。
6. 先窄后宽：首发只打 DuckDB 与 DataFusion。（正式实验扩到六个引擎，见 §9。）

## 2. 原代码现状（2026-10 快照）

主线 `main.py` → `evolution/co_evolution.py`：guideline(LLM) + UCB1 bandit 选类别 → BugHunter（种子变异流 + 每轮 3 次 LLM：建库/查询/改写）→ 多 oracle 筛查，只返回不一致 → BugFixer（ddmin + 判定 + LLM 根因 + root arm）→ σ（fix set + plan diff + 版本梯）作家族 key → playbook 蒸馏 + DCE 扩展。
另有 `coevo/` 早期原型、`repair_bench/`、`scripts/` 70 个脚本（41 个 PG 专项）、`seeds/`、`targets/`（5 引擎）、`docs/` 人工账本与 `recall_repros.json`。

与新框架的冲突：
- 驱动信号不做预测，产生不了惊讶。
- oracle 返回 `Candidate | None`，pass / 不适用 / invalid 混在一起，R 与 Kᵛ 学不到。
- 去重在执行之后（σ 需最多 120 次二分），新框架要求执行前用成员检验预测重复。
- 经验是自由文本（root arm hint、playbook），不可证伪。
- LLM 在热路径上，根因分析不附预测。

## 3. 新旧模块映射

| 原模块 | 新角色 | 处理 | 要点 |
|---|---|---|---|
| targets/*、oracles/db_runner.py | harness 执行层 | 保留 | DuckDBRunner 并入 targets/ |
| oracles/ TLP（含未接入的 TLP-GroupBy）、NoREC、plan-variant、index-variant、跨引擎（并入 scripts/cross_engine.py 法定数规则） | 七类 oracle 中的五类 | 改造 | 显式返回 pass/fail/invalid + 身份证据，冻结 |
| oracles/errors、determinism、normalize、reproduce | CVE 验证步骤：前提检查与重放 | 保留 | 原样进 harness |
| bug_fixer.triage 确定性部分 | 标签器 | 改造 | 确定性闸门、sound promotion、原查询报错判 invalid，并入 CVE 验证步骤 |
| bug_fixer._minimize | CVE 第 3 档：最小化（只给进 Diagnoser 的失败） | 改造 | 抽成工具 |
| diagnosis/bisect.py | Diagnoser 工具：bisect、计划比较 | 保留 | 填 h 的 I、ΔP |
| co_evolution._expand_family 快速成员检验 | 归属测试 | 改造 | 执行前预测重复、执行后核对身份 |
| oracles/differential.py、pg_version_ladder.py | Version differential oracle，兼作版本梯工具 | 改造 | 既产出标签，也填 h 的 V |
| diagnosis/signature.py (σ) | CVE 画像步骤；假设初始化证据；去重对照 | 改造 | 不再当家族身份 |
| evolution/dce.py 算子、seeds/mutate.py | Hunter 细化/泛化车道 | 改造 | 由规格差驱动 |
| coverage/features.py | φ 基础词表 | 改造 | 结构化特征 + 特征类 |
| seeds/ | 探索起点、先验语料 | 保留 | 按引擎与 φ 索引 |
| llm/ledger.py、base_agent.py | LLM 网关 | 改造 | 缓存、种子、模型版本、按角色记账 |
| oracles/equivalence.py | Equivalent query oracle | 改造 | 改写规则库分两层：冻结的确定性规则 + 经验收的 LLM 改写 |
| _analyze_root_cause、root arm | 假设猜想者 | 替换 | 必须附可证伪预测 |
| evolution/bandit.py | 惊讶打分 | 替换 | 原代码进对照组 |
| evolution/playbook.py、guidelines/ | 结构化理论 T | 替换 | 原代码进对照组 |
| agents/bug_hunter.py、co_evolution.py | 新 Hunter 与惊讶闭环 | 替换 | 冻结为"原 CoevoDB" |
| coevo/ 原型 | — | 移出 | 新进程重跑（供 CVE 用）、重复判 flaky 吸收进 harness 后归档 |
| repair_bench/、coevo/repair.py | 论文不再需要 | 移出 | 整体归档 |
| scripts/ 41 个 PG 脚本 | 暂不进入 | 移出 | campaigns/，PG 进评估时再包成 oracle |
| gate2.py、coevo_curve.py、final_report.py | 评估管线 | 改造 | 配置驱动的实验网格 |
| docs/ 账本、recall_repros.json、.sql 复现 | RQ6 真值、召回集 | 保留 | 整理成机器可读格式 |

### 七类 oracle 逐项（2026-10-08 确认清单）

七类在原代码里都已实现，但分两档：前四类是"健全"信号，命中即判 true_bug；后三类是"不健全"信号，单独命中永远不计 bug，只有被 plan-variant 重新见证（sound promotion）才算。新框架要求七类都直接产出 y，所以后三类必须补齐"何时判 fail"的规则；另有两类的引擎覆盖与首发引擎对不上。

| Oracle | 原代码 | 主循环接入 | 引擎覆盖 | 旧判定 | 新框架判 fail 的条件（已采纳） |
|---|---|---|---|---|---|
| TLP | oracles/tlp.py；tlp_groupby.py 已写好但无人调用 | Hunter、DCE、种子流 | 通用 | 命中即 true_bug | 不变；Phase 1 接入 GroupBy / Distinct 变体 |
| NoREC | oracles/norec.py | Hunter、DCE、种子流 | 通用 | 命中即 true_bug | 不变 |
| Plan variant | oracles/plan_variant.py | Hunter、DCE、Fixer sound promotion | DuckDB、PG、SQLite、DataFusion 四套开关 | 命中即 true_bug | 不变；开关集同时是 bisect 干预基 |
| Index presence | oracles/index_variant.py | 仅 engine == postgres 时启用 | 仅 PostgreSQL | 命中即 true_bug | 不变；首发引擎覆盖弱：DuckDB 需移植（ART 索引），DataFusion 无索引标为不适用 |
| Equivalent query | oracles/equivalence.py，改写由 LLM 每轮生成 | Hunter 每轮 1 次 LLM 改写 | 通用 | LLM 判等价后最多 unverified_bug | 改写来自冻结的确定性规则库，或经 oracle 发明者验收的 LLM 改写时才判 fail；其余不一致记 invalid 进 Kᵛ |
| Version differential | oracles/differential.py（旧版 venv 子进程）；PG 仅 scripts/pg_version_ladder.py | 仅 DuckDB | DuckDB；PG 仅脚本 | 只记 version_divergence | 新旧不一致且方向可定（旧版结果得其他引擎多数支持，或新版被前四类独立见证）时判 fail 记回归，否则 invalid；同时提供 V；DataFusion 需按 pip 版本建多环境 |
| Cross-DBMS differential | oracles/cross_engine.py（两两）；多数表决在 scripts/cross_engine.py | PG / SQLite / DataFusion 以 DuckDB 为参照 | 两两在主循环，多数表决仅脚本 | 只记 cross_engine_divergence | 决策 11：≥3 引擎且目标是唯一异类才判 fail；TiDB 对 MySQL 这类承诺兼容的参照也归此类 |

崩溃与内部错误不是第八类：每一类都可能产出 KIND_CRASH，新框架里是 fail 的子类型，身份证据取错误类别。

### 标签流程：CVE（Contract-Verified Evidence，契约验证证据；2026-10-08 确认）

CVE 是原论文 Challenge I 提出的流程，不是安全领域的漏洞编号。标签由 oracle + CVE 产出，LLM 永不参与。三步在旧代码里都有对应实现，但散在 Fixer、σ 和 coevo/ 原型里；新框架收拢成 harness 里一条冻结的流水线。

| 步骤 | 做什么 | 旧代码对应 | 新位置 |
|---|---|---|---|
| 执行契约 | 七类 oracle 按声明的语义契约执行，不一致即差异候选 | 七类 oracle 的 check() | harness oracle 层 |
| 验证 | 新进程重跑；最小化 schema、数据、查询；检查 oracle 前提；剔除不确定、依赖未定义语义、改写不等价的用例 | determinism.py、errors.py、bug_fixer._minimize、reproduce.py、oracle_repetitions、flaky_mine；主循环的重跑只是同进程新建连接，真正的新进程隔离只在 coevo/executor.py 和版本差分子进程里有 | harness CVE 模块，冻结 |
| 画像 | 记录诊断画像：fix set、plan diff、版本梯、错误类别、行为画像 | diagnosis/signature.py（σ）、bisect.py | 写进标签的身份证据；Diagnoser 复用同一批工具 |

标签规则：
- pass：oracle 没报差异。
- fail：oracle 报了差异，且通过 CVE 的新进程重跑与前提检查（后续步骤按下方成本分层执行）。
- invalid：查询报错、违反 oracle 前提、依赖未定义语义、改写不等价；重跑不稳定或结果不确定的也归此类。只更新 Kᵛ，不计惊讶。

CVE 的另一半（测量 oracle 覆盖哪些缺陷：召回基准、上游回归测试重放）归 Phase 6 评估，不参与打标签。

成本分层（2026-10-08 定）：CVE 按失败的去向分三档执行，避免预期中的重复花掉完整诊断的预算（旧代码最小化每个候选最多 30 次执行，σ 画像最多 120 次二分）。

1. 所有差异候选：新进程重跑 + 前提检查。不过即 invalid，通过即标 fail。
2. 预测落在已有假设里的失败（确认区的重复、待定区的边界样本）：只做一次归属测试。身份一致，记为该假设的实例或正例；身份不一致，说明预测错了，升级到第 3 档。
3. 要交给 Diagnoser 的失败（未探索区的新家族候选、归属测试不一致的失败）：最小化 + 完整画像（bisect、plan diff、版本梯）。若最小化后不再复现或违反前提，标签降为 invalid 并记账。

## 4. 目标架构与数据契约

新包 `framework/surprise/`（10-08 按推荐确认），四层：冻结评估器（harness/）、理论（theory/ + features/）、智能体（hunter/、diagnoser/）、LLM 网关（roles/）；另有 metrics/、experiments/、baselines/。新包调用旧代码保留部分，旧代码不反向依赖。数据流：Hunter 交 SQL x 给 harness；harness 标注、算惊讶、把高惊讶样本交 Diagnoser；Diagnoser 交待检编辑；harness 只把通过反驳的编辑写入 T；T 提供 P_T 指导选点；全部账本供 metrics。

| 契约 | 内容 | 谁写 | 谁读 |
|---|---|---|---|
| 实验记录 | (spec, x, φ(x), y, 目的) + 理论代号、当时 P_T 与惊讶；通过与无效也全存 | harness | 全部 |
| 标签 | y ∈ {pass, fail, invalid}、oracle 编号、身份证据（开关 I、错误类别、行为画像）、CVE 各步结果（重跑、前提检查、最小化、画像） | harness 标签器（CVE） | 分诊、归属测试、Kᵛ |
| 规格 | 对 φ 的约束：必须/禁止特征、数据性质、目标引擎与 oracle | Hunter、LLM 角色 | 实现器、变异算子、φ 核对 |
| 假设 | h = (I, ΔP, V, S, G, E⁺, E⁻) + 来源、状态 | Diagnoser（经接受规则） | 预测、Hunter、归属测试 |
| 理论编辑 | 类型、理由、押注预测、留入/留出惊讶变化、接受或回滚、提出者；回滚进负记忆 | Diagnoser | 接受规则、RQ3/RQ4 归因 |

行为画像：DataFusion 类 bug（DF-A/DF-B）没有开关，身份只能靠结果差异形状区分。

## 5. 分阶段路线（关键路径 Phase 1→2→3→4；Phase 6 在 Phase 3 后并行）

- Phase 0 冻结对照组、整理仓库：打 tag；确认旧 main.py 各模式可复现并存基线 run；PG 脚本移 framework/campaigns/，DuckDBRunner 移入 targets/（coevo/ 被 tests/test_verified_loop.py 依赖，S12 再归档）；首发引擎（10-08 确认）DuckDB 1.5.5 + 1.1.3、DataFusion 54.0.0（PG/SQLite 作参照）。出口：现有测试全过。
- Phase 1 环外评估器：五个契约；七类 oracle 统一接口与三值标签，后三类按逐项表补齐判 fail 条件，接入闲置的 TLP-GroupBy，给 Equivalent query 建不依赖 LLM 的确定性改写规则库（无 LLM 版靠它）；invalid 来源统一登记；把 CVE 收拢成分层流水线（所有候选新进程重跑 + 前提检查，不确定一律 invalid；预测落在已有假设里的失败只做一次归属测试；最小化与完整画像只给进 Diagnoser 的失败）；实验账本用 SQLite；harness 哈希写入 run manifest。出口 M1：recall_repros 与各 .sql 复现重放为 fail 且身份正确，普通查询 pass，值依赖错误 invalid。
- Phase 2 共同语言 φ：sqlglot AST + 各引擎计划算子 + 在库上算的数据性质；特征类（支撑换同类取值/删特征）；单元定义；词表注册表；规格核对 φ(x) ⊨ spec。出口：φ 稳定，能区分 DF-A/DF-B 与 DuckDB F1–F11。
- Phase 3 理论 T 与惊讶（无 LLM）：版本空间（正例泛化 S，反例特化 G，身份一致才算正例）；新家族由 fix set / plan diff / 版本梯确定性初始化；R、Kᵛ、P_T、六类分诊（阈值冻结）；按代快照、编辑日志、自动回滚、负记忆、MDL。出口：离线喂入已知复现与 DCE 探针，惊讶量级约 6.6/4.3/1.0/0.07/0.01 比特；执行前识别重复；家族划分与人工账本一致度不低于 σ。
- Phase 4 Hunter 与无 LLM 闭环：四类候选、value = P_valid × (D + β·U)、探索保底、降权与新颖性拒绝采样；新主循环。出口 M2：DuckDB 长 run 跑通，惊讶曲线锯齿，重复率低于原 CoevoDB，DuckDB 1.1.3 召回。
- Phase 5 六个 LLM 角色：先建网关（缓存、种子、模型版本、按角色记账；输出缺预测即拒收）。顺序：实现器 → 假设猜想者（需 DuckDB/DataFusion 源码与读源码工具）→ 探索先验（Brier 校准）→ 迁移翻译者 → 词汇发明者（留出验收）→ oracle 发明者（经证明器或多引擎一致才进入 Equivalent query 的改写规则库；oracle 判定代码不变）。先单次结构化调用，Diagnoser 按需升级为工具智能体。出口 M3：角色可单独开关，闭环复现 DF-A → DF-B。
- Phase 6 评估管线：全部指标从账本算（惊讶曲线、CIAO、分层冻结、跨代配对、LLM 预测准确率、Brier、猜想存活率、重复率、无效率、理论长度、留入/留出差距、边界吻合度、召回、成本）；CVE 的覆盖度量部分（已知 bug 召回基准、重放 seeds/ 里的上游回归测试）放在这里，不参与打标签；实验网格 臂×种子×24h×5 次，中位数 + Mann-Whitney U + Â₁₂；对照组 SQLancer、原 CoevoDB、纯 LLM 生成、无 LLM 版；离线去重对比改为原 CoevoDB 的 σ 去重 vs 执行前成员检验（SQLancer++ 暂不纳入）。出口 M4：RQ1–RQ6 指标一键生成。（正式实验的设计见 §9 与 `EXPERIMENT.md`：不再评估原 CoevoDB，SQLancer 在服务器上重跑。）
- Phase 7 收尾：旧循环移入 baselines/coevodb_v1/，共用原语只留一份；更新 README、架构文档、AGENTS.md。

## 6. 关键设计决策（建议）

1. 新包并行，不原地改写。
2. 版本空间：φ 字面量合取 + 特征类层级；析取靠拆假设，MDL 决定。
3. 无开关引擎的身份：错误类别 + 行为画像（DataFusion plan-variant 旧系统 494 次执行 0 命中）。
4. 单元粒度先粗：oracle × 主构造 × 关键计划算子 × 数据性质。
5. φ 用 sqlglot，正则兜底。
6. 实验账本用 SQLite，不用被测 DuckDB 做存储。
7. LLM 角色先单次结构化调用。
8. 0.95/0.5、分诊阈值、β 全部冻结写入 manifest；β 只在预实验调一次。
9. oracle 发明者先只用多引擎一致，证明器后续再接（原代码 argus_lite.py 记录过 SQLSolver 遇到 DECIMAL / TIMESTAMP 返回 UNKNOWN）。
10. 网关支持至少两档模型（换模型强度消融）。
11. 跨引擎差分：≥3 引擎且目标是唯一异类记 fail，否则 invalid（改变旧系统"永不升级"口径）。

## 7. 工程风险

- 版本空间表达不了析取/数值阈值：Phase 3 先测 31 个已确认家族中可用合取表达的比例；压不了的存样例家族。
- 执行前成员检验误判：确认区仍小比例抽样执行，监测意外通过率。
- 数据性质特征成本：按表缓存，只在规格涉及时计算。
- CIAO 计算量：只在接受编辑时快照，重算按批抽样。
- 旧代码隐性状态（PG autocommit、GUC 泄漏等，见 AGENTS.md）：保留 teardown/RESET 并写回归测试。
- 范围蔓延：首发只做 DuckDB + DataFusion。（正式实验扩到六个引擎，见 §9。）
- 调参自由度：预实验用独立种子，正式实验前冻结。

## 8. 已确认事项（2026-10-08）

- 七类 oracle = TLP、NoREC、Plan variant、Index presence、Equivalent query、Version differential、Cross-DBMS differential，原代码都有实现，见 §3 逐项表。
- "CVE 验证" = 原论文的 Contract-Verified Evidence，见 §3 标签流程；成本分层已定。
- 首发引擎只做 DuckDB（1.5.5 + 1.1.3）与 DataFusion 54.0.0。（正式实验另加 SQLite、PostgreSQL、TiDB、MySQL，见 §9。）
- 决策 3（行为画像定身份）、决策 11（跨引擎法定数即记 fail），以及 Equivalent query、Version differential 判 fail 的条件：采纳。
- 新包名字与位置按推荐：`framework/surprise/`。
- repair_bench 论文不再需要，整体归档。
- SQLancer++ 对照暂不放入评估。
- 不估工时。

## 9. 正式实验的决定（2026-10-19，用户）

设计全文在 `EXPERIMENT.md`，实施会话在 `SESSIONS.md` 的 S13–S25。与上文冲突处以本节为准。

- 只评估新框架及其消融；原 CoevoDB 是早期草稿，淘汰，不再作对照组（改 §1 首句、第 1 条与 Phase 6 的对照组名单）。对照组：无 LLM 版、纯 LLM 生成、SQLancer。
- 被测引擎扩到六个：DuckDB 1.5.5、DataFusion 54.0.0、SQLite 3.51.0、PostgreSQL 16.15、TiDB v8.5、MySQL 8.4 LTS；MariaDB 11.8 只作 MySQL 族的 Cross-DBMS 参照（改 §1 第 6 条、§7、§8 的"首发只做 DuckDB 与 DataFusion"）。新引擎沿用旧系统测过的版本线；DuckDB 与 DataFusion 不升版本。
- 实验在 Linux 服务器上跑，实验期间专用；开发留在 Windows 本机。实验由用户自己在服务器上跑；Claude 只在搭环境与部署新引擎时、且服务器空闲时动服务器；grok 不登录服务器。（分工部分被下面 2026-10-19 补充的一条取代。）
- （2026-10-19 补充，用户，S14 期间）服务器现在是专用的：Claude 部署不必先问是否空闲，可以直接部署；实验也由 Claude 在服务器上起（用户的原话是"帮我新建一个tmux窗口然后跑起来正式实验"），但仍按 SESSIONS 的次序：E1 在 S15 之后的 S19 跑，预实验在前。密钥沿用现有的那个（"你可以直接使用"），只走环境变量 `DEEPSEEK_API_KEY`：经 ssh 的标准输入传进 tmux 会话的环境，不进命令行、文件与日志。grok 仍不登录服务器。
- 规模：每格 24h × 5 个种子，按里程碑 E1–E7 分批，每个里程碑出一份报告；顺序为 DuckDB 主对比 → PostgreSQL → 其余；PostgreSQL 接入没赶上时服务器空等。
- harness 分批解冻（PostgreSQL → DataFusion 与 SQLite → TiDB 与 MySQL），每次解冻后用新 harness 回放 E1 的一批记录，标签与身份逐条相同才算可比。不加结果行数上限。
- SQLancer 在服务器上重跑（取代 S11 验收时"拷回原始结果"的决定）。LLM 调用不设上限，成本照实报告。
- 新发现的缺陷在每个里程碑之后、到最新版复核过，交给用户提交上游。
- （2026-10-20 补充，用户，S19 期间；DeepSeek 余额在预实验后半段用完）用户先说"当前实验太繁杂了，我的tokens不够用。现在先去掉各种消融实验的实验，并且优先跑postgre sql的实验"，讨论后定下：`pure_llm` 先不跑，方法照原样保留，以后需要时再定；E3–E6 保留，只是现在不跑（取代"去掉消融"）；服务器现在什么都不跑，等用户说（暂时收回上面"Claude 在服务器上起实验"的授权）；暂不开始 PostgreSQL 的部署（S16）；恢复时 PG 优先。
- （2026-10-20 补充，用户，S19 期间）LLM 角色换模型：OpenRouter 上的 Z.ai GLM 5.3 Flash（`z-ai/glm-5.3-flash`），只用提供商 Open Inference（`open-inference/fp4`），不回退到别的提供商，开推理；接口与 OpenAI 兼容；密钥仍放在 `DEEPSEEK_API_KEY` 里（用户稍后换成 OpenRouter 的密钥）。实现为网关的新档 `glm-flash`，原来的 fast / strong 两档与默认行为不变（决策 10 仍成立）。
- （2026-10-21 补充，用户，S19 期间）加提醒：额度不足、报错等经 pushplus 的一对一消息推给用户本人（用户的话："添加额度不足、报错等的提醒：使用pushplus的一对一消息功能"）。token 只放在环境变量 `PUSHPLUS_TOKEN`，同 `DEEPSEEK_API_KEY` 的规矩。实现为独立的看守进程 `surprise.notify.watch`，只读网格结果目录，实验代码不变。
- （2026-10-21 补充，用户，S19 期间）GLM 的推理强度：这个端点不允许关推理，默认强度下复杂角色把 max_tokens 都花在推理上；用户定为与以前的 deepseek-flash 对齐（它默认就推理）：开推理、各角色 max_tokens 不变，`reasoning` 设为 `{"effort": "low"}`，取代上面换模型一条里的"开推理"（`enabled: true`）。
- （2026-10-21 补充，用户，S19 期间）OpenRouter 回 HTTP 429（限流）时退避重试，不再算作一次失败的调用（用户的话："同意，改成429退避重试"）。只重试 429，别的错误照旧只试一次；重试在一次网关调用之内，调用上限与 `calls.jsonl` 仍按一次算。
- （2026-10-21 补充，用户，S19 期间；GLM 预实验里 Open Inference 成串回 HTTP 503）用户的话："1. 添加退避重试 2. 服务商由open-inference/fp4更换为为sail-research/fp4 3. 若退避重试仍然不行可以更换别的服务商，优先尝试open-inference/fp4和sail-research/us"，并选定"每次调用自动切换"：503 也退避重试；每次调用先找 `sail-research/fp4`，它的重试用完仍 429/503 就换 `open-inference/fp4`，再换 `sail-research/us`，三家都不行才算失败（三家都是 fp4）。每次调用记下实际回答的服务商。取代上面换模型一条里的"只用 Open Inference"。
