角色：执行者

# 工作包 s12-docs：更新 README、`framework/AGENTS.md`，新写架构文档 `framework/surprise/ARCHITECTURE.md`

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s12-docs`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s12`（含门槛 `framework/surprise/gates/s12.py` 与 `s12_cases.py`）
- 所属会话：S12（Phase 7 收尾），范围见 `framework/surprise/docs/SESSIONS.md` 的 S12 一节与 `PLAN.md` 第 5 节 Phase 7："更新 README、架构文档、AGENTS.md"
- 依赖：另一个包 `s12-move` **同时**在做代码移动，你的 worktree 里看不到它的结果。文档要按**移动之后**的布局写（见下面"移动之后的布局"）。

## 目标

只改四个文档文件，全部用英文写（与现有 README 一致）。验收是门槛 `framework/surprise/gates/s12.py` 的 `docs` 组：先读它与 `s12_cases.py` 里的 `DOCS`、`DOCS_UPDATED`、`REQUIRED_MENTIONS`、`UNTRACKED_PREFIXES`，那是逐项的规格。

**docs 组在你的 worktree 里不会全绿**：凡是指向移动之后才存在的路径（以 `surprise/baselines/coevodb_v1/`、`framework/surprise/baselines/coevodb_v1/`、`archive/`、`framework/archive/` 开头）的条目，都会报 "names `X`, which does not exist"。这是预期的，编排者合并两个包之后再核对。**除此之外的任何问题都必须为零**：报告里贴出 `python -m surprise.gates.s12 --only docs` 的输出，逐条说明每个剩下的问题都属于上面四个前缀。

### 移动之后的布局（`s12-move` 交付的，按它写；路径相对 `framework/`）

- 旧主循环（bandit + playbook 的共同进化）只把**独用**的部分移进 `surprise/baselines/coevodb_v1/`：`main.py`；`evolution/` 下 `bandit.py`、`co_evolution.py`、`coverage.py`、`playbook.py`；`agents/bug_hunter.py`；`guidelines/`；`coverage/`（AST × 计划算子 × 边界值的覆盖特征）。
- `framework/main.py` 留下一个转发入口：`runpy.run_module("surprise.baselines.coevodb_v1.main", ...)`。所以 `python main.py --engine duckdb --mode no_llm ...` 照旧可用，等价于 `python -m surprise.baselines.coevodb_v1.main ...`；九种 `--mode`：`full`、`random_category`、`no_llm`、`coverage_only`、`dce_only`、`shuffled_diag`、`coevo`、`coevo_warm`、`coevo_frozen`。作为对照组时由 `python -m surprise.baselines.old_no_llm --out DIR --minutes M --seed N [--mode no_llm]` 按墙钟跑。
- **共用原语**留在原位、只有一份（用户为 S12 选定的"方案 A"）：`evolution/dce.py`（Hunter 的变异算子）、`agents/bug_fixer.py`（第 3 档最小化用它的 `_minimize`）及其依赖 `agents/base_agent.py`、`agents/json_utils.py`、`llm/ledger.py`（`surprise/roles/transport.py` 复用 `base_agent` 的 HTTP 客户端与 `llm.ledger`），以及本来就共用的 `oracles/`、`targets/`、`diagnosis/`（`bisect.py`、`signature.py`）、`scripts/cross_engine.py`、`seeds/`、`util/`。原因：harness 冻结时对其中一批旧文件取了哈希（`surprise/harness/manifest.py` 的 `HASHED_PATHS`，校验文件 `surprise/gates/s04_frozen.json`），S8 钉住的长跑又核对 `surprise/hunter/`、`diagnoser/`、`experiments/` 的代码摘要；搬动它们就要解冻 harness、重跑长跑。
- `coevo/`（早期的 verified co-evolution 原型；它的新进程重跑与 flaky 判定已被 S4 的 harness 吸收）与 `repair_bench/`（补丁 / 定位基准，论文不再需要）归档到 `archive/coevo/`、`archive/repair_bench/`，仍可导入（`evolution/__init__.py` 导入 `archive.coevo.controller`，`tests/test_verified_loop.py` 测它）。`archive/README.md` 说明归档内容。运行产物目录 `framework/archive/repair_bench/runs/` 被 gitignore。
- `campaigns/`：S1 从 `scripts/` 移过来的 41 个 PostgreSQL 专项脚本（`campaigns/pg_*.py`）；`scripts/` 里剩下的是旧系统的实验脚本与共用的 `cross_engine.py`。

### 1. `framework/surprise/ARCHITECTURE.md`（新文件）：新框架的架构文档

写给第一次读这个仓库的研究者。内容（按这个顺序，篇幅 150–300 行）：

1. 一段话：惊讶驱动框架是什么——一个可证伪的理论 T 对每个实验预测失败概率 P_T，惊讶 = −log₂ P_T(观察到的标签)；Hunter 按信息价值选实验，Diagnoser 与 LLM 角色提理论编辑，接受规则决定收不收；标签只来自七类 oracle 加 CVE（Contract-Verified Evidence）流程，**LLM 永不打标签**。依据 `framework/surprise/docs/PLAN.md`（第 1–4 节），不要发明 PLAN 里没有的东西。
2. 一张数据流图（文本图即可）：Hunter → harness（执行、七类 oracle、CVE 三档）→ 账本 → 理论（φ、预测、惊讶、分诊）→ Diagnoser / LLM 角色 → 接受或回滚 → 理论存储，再回到 Hunter。
3. 逐个子包一节，每节写清职责、主要模块、对外接口（入口命令、主要函数）：`surprise/harness/`（冻结的评估器：契约、SQLite 账本、run manifest 与 `HASHED_PATHS`、七类 oracle——TLP、NoREC、Plan variant、Index presence、Equivalent query、Version differential、Cross-DBMS——与 CVE 三档）、`surprise/features/`（φ：AST、计划、数据三层；单元；词表注册表；规格核对器）、`surprise/theory/`（假设的版本空间、R、Kᵛ、P_T、惊讶、分诊、存储、按代快照、编辑日志、回滚与负记忆、接受规则与 MDL、`Workbench`）、`surprise/hunter/`（四类候选车道、`value = P_valid × (D + β·U)`、探索保底）、`surprise/diagnoser/`（无 LLM 的 ddmin + bisect + 版本空间规则）、`surprise/roles/`（LLM 网关：缓存键为提示哈希 + 模型 + 种子、按角色记账、调用上限、每个输出必带预测；六个角色 implementer、conjecturer、prior、translator、vocab_inventor、oracle_inventor，每个可单独开关）、`surprise/experiments/`（主循环 `loop.py`、实验网格 `grid.py`）、`surprise/metrics/`（RQ1–RQ6 指标、CIAO、统计检验、报告与图、离线去重对比、覆盖度量）、`surprise/baselines/`（`old_no_llm.py`、`pure_llm.py`、`sqlancer.py`、`coevodb_v1/`）、`surprise/gates/`（每个实施会话一个门槛 `sNN.py`，`all.py` 依次运行）。每节里出现的模块路径都要真实存在（门槛逐个核对反引号里的路径）。
4. 一节"不变式"：LLM 不打标签；harness 自 S4 起冻结（`HASHED_PATHS` 与 `surprise/gates/s04_frozen.json`），理论与特征的常数写进 run manifest、由门槛钉住；旧代码只移动不改逻辑。
5. 一节"与旧系统的关系"：上面"移动之后的布局"的要点——共用原语清单与为什么留在原位、`coevodb_v1/` 里有什么、`archive/` 里有什么。
6. 一节"文档索引"：`surprise/docs/PLAN.md`（总规划）、`SESSIONS.md`、`HANDOFF.md`（含各层"当前接口"）、`DECISIONS.md`、`ORCHESTRATION.md`。

事实来源：代码本身（`surprise/` 各子包的 `__init__.py` 与模块 docstring）、`PLAN.md`、`HANDOFF.md` 里各会话的"当前接口"一节。拿不准的不要写；不要写数字（测试数、长跑结果之类会过时）。

### 2. `framework/README.md`：改写成新框架的 README

- 开头一段：仓库现在的主体是惊讶驱动框架（`surprise/`），原 CoevoDB（LLM Hunter/Fixer 共同进化）保留为对照组；LLM 永不是 oracle 的原则照旧。链到 `surprise/ARCHITECTURE.md`。
- 一张目录表：`surprise/`、共用原语（`oracles/`、`targets/`、`diagnosis/`、`seeds/`、`util/`、`llm/`、`agents/` 里剩下的、`evolution/dce.py`）、`campaigns/`、`scripts/`、`archive/`、`tests/` 与 `testing/`。
- "Running the surprise framework"：给出可直接照抄的命令——`python -m surprise.experiments.loop --out DIR --seed 0 --engine duckdb --max-minutes 10`（参数以 `python -m surprise.experiments.loop --help` 为准，你可以自己跑 `--help` 核对）、`python -m surprise.experiments.grid run CONFIG --out DIR` / `status DIR`、`python -m surprise.metrics.report GRID_DIR`、对照组 `python -m surprise.baselines.pure_llm …` 与 `python -m surprise.baselines.old_no_llm …`。LLM 角色默认全关，用 `--llm ROLE` 打开，需要 `DEEPSEEK_API_KEY`。
- "Tests and gates"：`python -m pytest -q testing tests`（在 `framework/` 下；`framework/test_api.py` 在设置了密钥时会真的调用 API，所以不要不带路径地跑 `pytest`）、`python -m surprise.gates.all`（每个会话门槛退出码 0 = 通过）。门槛依赖仓库外的东西（引擎 venv、PostgreSQL 参照、源码检出、长跑产物），一句话说明并指向 `surprise/docs/HANDOFF.md`。
- "The old CoevoDB (baseline arm)"：位置、`python main.py` 的转发、九种模式、原 README 的 "Bug verdict taxonomy" 与 "Honesty boundaries" 两节挪到这里（内容照旧）。
- "Machine-local paths" 表保留，`repair_bench/run_localize.py` 等路径改成 `archive/repair_bench/…`。
- 删掉过时的东西：`pytest testing/ -q # 36 tests`、只描述旧系统的 Architecture 代码块（换成新的目录表）。

### 3. 仓库根 `README.md`：只改 "Framework (`framework/`)" 一节

缺陷表、"Running the reproducers"、"Documentation"、"Scope note" 一个字不改。"Framework" 一节改成：发现这些缺陷的是原 CoevoDB（LLM Hunter/Fixer 共同进化），它现在保留在 `framework/surprise/baselines/coevodb_v1/` 作为对照组；框架已迁移到惊讶驱动框架 `framework/surprise/`（一两句说明，链到 `framework/surprise/ARCHITECTURE.md`）；`repair_bench` 归档在 `framework/archive/`。代码块里的命令改成新框架的一条示例命令、旧系统的 `python main.py ...`（仍可用）与测试命令 `python -m pytest -q testing tests`。运行产物目录的说明改成 `results/`、`framework/archive/repair_bench/runs/`。

### 4. `framework/AGENTS.md`：项目说明

- "DeepSeek API" 一节的规则全部保留。补两点：本机（Windows）上密钥是用户级环境变量 `DEEPSEEK_API_KEY`；新框架的 LLM 角色经 `surprise/roles/transport.py` 读同一个变量，默认全关。示例命令 `python main.py --engine duckdb --mode full ...` 保留，注明它是旧主循环（现在在 `surprise/baselines/coevodb_v1/main.py`，`main.py` 转发）。
- 新加一节（放在 DeepSeek 之后）"Repository layout"：几行，指向 `surprise/ARCHITECTURE.md`、`surprise/docs/`（迁移规划与交接），并写明两条规则：标签只来自七类 oracle 加 CVE，LLM 不打标签；`surprise/harness/` 与 manifest 里的常数已冻结，改动要先问用户。
- PostgreSQL 两节的内容保留，只修路径：文中的 `scripts/pg_*.py` 在 S1 已移到 `campaigns/`，凡是现在实际在 `campaigns/` 下的都改成 `campaigns/pg_*.py`（逐个用文件系统核对；在 `scripts/` 下真实存在的不改）。门槛对反引号里的每个路径查存在性。

## 允许改动的路径

```allow-paths
README.md
framework/README.md
framework/AGENTS.md
framework/surprise/ARCHITECTURE.md
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`。
- 不改任何代码、测试、配置；不改 `docs/`、`framework/` 下其它 `.md`（`RESEARCH_PLAN.md` 等是历史文档，不动）；不建 `framework/archive/`（归 `s12-move`）。
- 文档里不写密钥、不写本机用户目录之外的私人路径；不贴任何命令输出里的密钥变量值。本包不需要密钥。
- 不靠改测试或门槛让检查通过。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`；不要清理 `.orch/tmp`。

## 验收命令

在 worktree 里执行。`python` 已经指向项目解释器。shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，判断结果用 ASCII 关键字。

```powershell
cd framework
python -m surprise.gates.s12 --only docs      # 只剩指向移动后路径的 "does not exist"（见上），其余为零
python -m pytest -q testing tests             # 935 passed, 3 skipped（你不改代码，应与基线相同）
```

## 收尾

1. 把改动提交到当前分支；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），格式见下；"跑了哪些命令"一节贴出 docs 组的完整输出，并逐条归类剩下的问题。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s12-docs

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
