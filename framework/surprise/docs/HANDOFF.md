# HANDOFF

## 状态总览

| 会话 | 内容 | 状态 | tag | 门槛 |
|---|---|---|---|---|
| S0 | 编排准备（派发工具） | 完成 | s00-done；s00-done-r2（CLAUDE.md 写入"执行者模式"之后） | 冒烟包 s00-smoke 四项确认全部通过（没有 gates/s00.py） |
| S1 | Phase 0 冻结基线与仓库整理 | 完成 | s01-done；s01-done-r2（验收后的修订） | `gates/s01.py` 7/7；pytest 64 passed, 3 skipped |
| S2 | Phase 1a 契约、账本、三类健全 oracle | 完成 | s02-done；s02-done-r2（验收后的修订，S3 从这里起） | `gates/s02.py` 5/5；pytest 149 passed, 3 skipped |
| S3 | Phase 1b 其余三类 oracle 与 Index presence 移植 | 进行中（registry/cross/local已合并，version运行中） | 起点 s02-done-r2 | local独立186 passed/3 skipped，cross188 passed/3 skipped；三个已合并组PASS |
| S4 | Phase 1c CVE 流水线（M1） | 未开始 | | |
| S5 | Phase 2 φ | 未开始 | | |
| S6 | Phase 3a 理论 T 核心 | 未开始 | | |
| S7 | Phase 3b 理论存储与接受规则 | 未开始 | | |
| S8 | Phase 4 Hunter 与无 LLM 闭环（M2） | 未开始 | | |
| S9 | Phase 5a LLM 网关、实现器、猜想者 | 未开始 | | |
| S10 | Phase 5b 其余四个 LLM 角色（M3） | 未开始 | | |
| S11 | Phase 6 评估管线（M4 冒烟） | 未开始 | | |
| S12 | Phase 7 收尾 | 未开始 | | |

以前各会话的交接全文在对应 tag 的本文件里（S0：`s00-done-r2`；S1：`s01-done-r2`）；其中仍然有效的未决问题已并入下面的清单。

## 当前会话：S3（2026-10-09，进行中）

编排者为 Codex；实现仍只交给 grok。主检出区分支 `session/s03`，起点 `s02-done-r2`（caec153）。起点独立复跑为 149 passed, 3 skipped 与 GATES PASS 2/2。S2 交接全文在下方保留。

### 当前进度与恢复入口

- 前置实测脚本在 `.orch/scratch/s3_probe.py`、`s3_probe2.py`、`s3_versions.py`，不入库。
- SQLite 3.51.0 对 EXCEPT ALL / INTERSECT ALL 都报语法错误；DuckDB 1.5.5 与 DataFusion 54.0.0 都能执行并且不同。DF-B 的正确 bag 包含 NULL：`1, 2, NULL`（原 SQL 文件注释漏了 NULL，旧文件不改）。
- 本机 PATH 没有 PostgreSQL 命令，pgserver 未安装，pip 仅二进制下载也返回 no matching distribution。EDB PostgreSQL 16.15 Windows x64 已放在 `.orch/pg16/`（已有忽略规则覆盖），服务器监听 127.0.0.1:55432，用户 coevo、数据库 postgres、仅本机 trust，无系统服务。两种 ALL 运算经 psycopg2 实测与 DuckDB 一致。
- F2 已实测：1.1.3 返回 `[(10,30),(20,30)]`，1.5.5 返回 `[(10,10),(20,20)]`；新版 plan variant 独立判 fail / wrong_result。S3 回归门槛选 F2，不用语义未指定的 F3。
- F2另实测DF54/PG16/SQLite3.51全支持旧结果，版本门槛另覆盖无参照时的sound独立见证。DuckDB和DataFusion各自新旧SELECT version()的字符串不同、无参照时方向不可定；两项都进入派发前门槛。
- 已提交 `gates/s03.py` 五组门槛（registry/local/cross/version/matrix）；registry 已审查合并并归档。local/cross从eba9c84并行派发后均已提交，正在独立审查，version brief待cross合并后派发。关键期望在派发前实测，包含三个改写的 NULL 样例和 SELECT version() 的方向不可定样例。
- Cross预读发现PG只读查询检查允许多语句、setup只检查首词事务控制。编排者已补门槛并实测第一版被拦下；setup用不连数据库的记录runner验证拒绝发生在执行前，避免测试自身提交参照schema。将作为cross第1轮返工项。
- Cross第1轮返工dc20f00独立pytest186 passed/3 skipped，多语句门槛通过；完整复查新增发现WITH起头的SELECT INTO遗漏，门槛已拦下。第2轮（最后一轮）只修该只读前提，达到返工上限后若仍有必修问题必须问用户。
- local独立审查实测De Morgan把BETWEEN和CASE内部AND误拆，导致两引擎假fail/error_mismatch；paired_query比较还会忽略字符串大小写。已补对应门槛，将作为local第1轮返工项。基础三条NULL/重复行用例保留。
- local第1轮两项已修正；新增反例实测E转义字符串内的CASE文本被改写，两引擎假fail/wrong_result，第2轮只修词法引用边界。编排者新门槛的SqlCase漏导入已自行改为共用case()助手，执行者未动门槛。
- 注册API：register(id, handler)、get_handler(id)、runner_factory_for(engine)。后续模块在末尾自行register；统一handler签名 judge_case(case, *, factory, timeout_s, options)。OracleOptions四字段rewrite_rule/paired_query/old_python/reference_factories；old_python使用字符串路径，None默认、空参照字典表示无参照。
- registry审查与返工证据已归档到 docs/orch/s03/；新增缺模块测试现在在测试内模拟缺失，不依赖后续文件未实现。审查唯一红旗是S3其余模块尚缺，按部分门槛验收。
- PostgreSQL 恢复命令（根目录）：`.orch/pg16/binaries/pgsql/bin/pg_ctl.exe -D D:/CoevoDB/.orch/pg16/data -l D:/CoevoDB/.orch/pg16/server.log -o "-h 127.0.0.1 -p 55432" -w start`。已有服务器时只查 status。参照 runner 默认此连接，`COEVO_REFERENCE_PG_DSN` 可覆盖；参照用例由独立事务隔离，close 回滚，禁止注册服务、改全局 PATH。
- 恢复命令：`git status --short --branch`、`git log -8 --oneline`、`.venv/Scripts/python.exe tools/orch/grok_worker.py list`。
- 三包合并后的主检出区集成复跑：209 passed, 3 skipped；`-m surprise.gates.s03 --only registry local cross` PASS 3/3（最终all尚待version）。最近集成基线c391423。
- version草稿预读后的独立反例在`.orch/scratch/s3_version_review_probe.py`：DF50/54原始DATE/bytes/Decimal一致，但草稿DATE假fail、bytes假invalid；行序变化使pass标签不同；双方Binder错误、非零退出带合法JSON、缺engine_version都被错误判pass。已补主门槛，待提交后review再派第1轮反馈，不能提前合并。

### 预定拆包（门槛提交后才派发）

| 包号 | 目标 | 允许路径 | 依赖 | 门槛组 | 状态 |
|---|---|---|---|---|---|
| s03-registry | 注册分发、DuckDB/DataFusion 映射、S2 三类接 DataFusion、统一 options、invalid 来源、manifest 依赖范围 | harness/oracles/__init__.py、registry.py、sound.py；harness/evaluate.py、contracts.py、manifest.py；tests/test_surprise_oracles.py、test_surprise_evaluate.py、test_surprise_contracts.py、test_surprise_s03_registry.py | s02-done-r2 | registry | 已合并（1cae8cd）；返工1轮，只修新增测试的长期有效性。独立pytest165 passed/3 skipped，registry PASS，S01/S02 PASS |
| s03-local | DuckDB ART Index presence、确定性 Equivalent query 规则库 | harness/oracles/index_presence.py、equivalent_query.py、rewrites.py；tests/test_surprise_s03_local.py | registry 已合并 | local | 已合并0293ace，返工2轮；独立pytest186 passed/3 skipped，S01/S02与增强local PASS，归档完成 |
| s03-cross | psycopg2 PostgreSQL 参照 runner、Cross-DBMS 法定数及唯一异类判定 | harness/oracles/cross_dbms.py、pg_reference.py；tests/test_surprise_s03_cross.py | registry 已合并，PostgreSQL 就绪 | cross | 已合并a60a287，返工2轮；独立pytest188 passed/3 skipped，S01/S02与增强cross PASS，归档完成 |
| s03-version | 两引擎新旧版子进程及回归方向证据 | harness/oracles/version_differential.py、version_worker.py；tests/test_surprise_s03_version.py | registry、cross 已合并 | version | run1运行中，session 6e5c2b6d-8ea1-4f05-bf90-feebdfb71480，基线d81010c；local尚未合并 |

表内 harness、tests 路径分别相对 `framework/surprise/`、`framework/`。公共文件只归 registry 包；local 与 cross 并行，cross 合并后可派 version，同时最多两包运行。每包合并后立即更新本表并提交。最后集成门槛组为 matrix（七类 × 两引擎与账本）。

## 最近一次已完成会话：S2 契约、账本、三类健全 oracle（2026-10-08）

分支 `session/s02`，起点 tag `s01-done-r2`（7632c03），收尾合并回 main 并打 `s02-done`。

### 验收后的修订（s02-done-r2，2026-10-09）

用户验收时把点名的五处人工检查项交给编排者自行判断决定。复核没有改任何代码和门槛，改动只有本文件和 DECISIONS.md。五处的结论：

1. **契约分放 `harness/contracts.py` 与 `theory/contracts.py`**：维持。冻结边界和"谁写"的边界是同一条线；实验记录里的规格存成 dict，harness 不依赖理论层。harness 一侧的字段名和四张取值表到 S4 冻结，在那之前 `FAIL_KINDS`、`INVALID_REASONS` 还可以加项。
2. **`gates/s02_cases.py` 的 20 个用例期望**：全部维持，逐条看过。两点定下来：
   - "不适用"就是 `invalid / not_applicable`，不另设第四个标签值。S3 门槛里说的"明确'不适用'"指的就是它。以后统计无效率时把这一项单列，它不代表用例坏。
   - 划分谓词只对 TLP 认识的三种形态有定义（普通 `SELECT … FROM … [WHERE …]`、选择列表等于分组键的 GROUP BY、SELECT DISTINCT）。别的形态再给谓词就是坏用例，判 invalid（`grouped_with_aggregate` 在 plan variant 下是 `query_error`）；`full_query` 不改。生成用例的一方遇到别的形态，把过滤条件直接写进 `query`、`predicate` 留空，这样不损失任何可测的查询。
3. **F5、F6、F10 等已知复现在 S4 门槛里怎么算**：见下面"S4 门槛（M1）对已知复现的期望"一节。为此补查了事实；未决问题"S2 新发现"第 1、2 条已按实测改写，原先有三处写得不对（F5 不是抓不到；F6 补上数据就能复现；F10 经适配器根本不会被执行，所以也不会崩）。
4. **实际标签**（`metrics_small` × TLP）：看过，`y`、`fail_kind`、身份证据（`missing: 1, extra: 0`）与判定依据（`detail` 里的两条语句）齐全，没有要改的。
5. **`orch/s02/s02-oracles.review.md` 第 8 节**：复核无异议。返工的起因在任务说明，补的门槛检查现在是 `evaluate` 组的一部分，本次重跑通过。

复核时在主检出区重跑：pytest 149 passed, 3 skipped；门槛 `s01`、`s02` 都通过。

### 完成了什么

- 五个数据契约与序列化，按"谁写"分成两个文件：
  - `framework/surprise/harness/contracts.py`：`SqlCase`（x）、`IdentityEvidence`（身份证据）、`Label`（y 及证据）、`ExperimentRecord`（实验记录），以及四张取值表 `LABELS`、`ORACLE_IDS`（七类）、`FAIL_KINDS`、`INVALID_REASONS`。
  - `framework/surprise/theory/contracts.py`：`Spec`（规格）、`Hypothesis`（假设）、`TheoryEdit`（理论编辑）。只有类型和序列化，S5–S7 再细化。
- `framework/surprise/harness/constants.py`：harness 的数值常数，现在只有 `QUERY_TIMEOUT_S = 10.0`；`as_dict()` 自动收集，写进 manifest。
- `framework/surprise/harness/ledger.py`：SQLite 实验账本，只能追加；按 run、理论代号、标签、oracle 查询；pass 和 invalid 一样入账。
- `framework/surprise/harness/manifest.py`：run manifest、harness 哈希、校验命令。哈希覆盖新 harness 的全部 `.py`（现在 12 个）加十个会影响标签的旧模块，共 22 个文件；摘要与行尾无关，主检出区和 worktree 算出来相同。
- `framework/surprise/harness/oracles/`：TLP（WHERE、GROUP BY、DISTINCT 三种形态，后两种接入了原先无人调用的 `oracles/tlp_groupby.py`）、NoREC、Plan variant 的三值适配器。什么算差异仍由旧 oracle 的 `check()` 决定，适配器只做执行前筛查、把旧接口的 None 拆成 pass 与 invalid、整理身份证据。旧代码一个字没改。
- `framework/surprise/harness/evaluate.py`：`evaluate()` 判定一个用例并写一条实验记录；判定过程抛异常也记成 `invalid / harness_error`。
- 测试 85 个（`framework/tests/test_surprise_*.py` 五个文件）。

### 门槛结果

在 `session/s02` 三个包都合并之后、主检出区里跑的：

| 命令（在 `framework/` 下，解释器 `../.venv/Scripts/python.exe`） | 结果 |
|---|---|
| `-m pytest -q testing tests` | 149 passed, 3 skipped，退出码 0（S1 的 64 个都在，新增 85 个） |
| `-m surprise.gates.all` | `s01: PASS`（7/7）、`s02: PASS`（5/5），退出码 0 |

`gates/s02.py` 的五组与 SESSIONS.md 的对应：

- `oracles`：20 个固定用例 × 3 个 oracle 共 60 组，每组判两次结果相同（"同一输入两次判定一致"）；已知复现判 fail：TLP 与 NoREC 各抓到账本条目 AUTO-a8be20c9 / AUTO-ad38bad6 的最小化用例，plan variant 抓到 `recall_repros.json` 的 F1、F2、F7 和旧测试里的 deliminator 用例，身份证据里的开关都是 `no_optimizer`（"已知复现里这三类能抓的判 fail"）；四个值依赖错误用例判 `invalid / value_dependent_error`（"值依赖错误样例判 invalid"）；另有崩溃、一侧报错、超时三条注入路径。
- `evaluate`：11 次执行对应 11 条记录，pass、fail、invalid 都有（"每次执行（含 pass）都进账本"）；参数不合法时在执行前拒绝，不留记录。
- `contracts`、`ledger`、`manifest`：往返与校验；写入、过滤、重开；哈希稳定、校验命令能指出被改的文件。

用例表 `gates/s02_cases.py` 里的期望值是派发前用旧 oracle 实测的。

### 工作包

| 包号 | 目标 | 结论 |
|---|---|---|
| s02-contracts | 契约、常数、账本 | 一次通过，返工 0 轮。16 分 35 秒，0.91 美元 |
| s02-manifest | manifest、harness 哈希、校验命令 | 质量上一次通过。记录里有第 2 轮，是编排者误操作把第 1 轮提前终止后的续跑，不是返工。0.48 美元（被终止的那一轮没有上报花费） |
| s02-oracles | 三个适配器与 `evaluate()` | 返工 1 轮。起因是任务说明和门槛都漏了一点（`evaluate` 的部分参数在判定之后才校验），不是执行者理解错了；编排者补了门槛检查后返工，第 2 轮改对。两轮共 1.77 美元 |

brief、report、审查包（含编排者的结论）和返工意见在 `framework/surprise/docs/orch/s02/`。

审查时在门槛之外另做了一次差分核对：从种子语料取 60 个种子、经旧的变异器得到 196 个用例，每个用例对三个 oracle 各判两次，共 588 组；新标签与一份直接调用旧 oracle 的独立映射逐组比较，出入为 0。

### 新增或改动的接口

- `SqlCase(engine, setup, query, predicate=None)`：`query` 是被测查询（给 TLP / NoREC 时是不含划分谓词的那部分，可以自带 WHERE），`predicate` 是划分谓词。
- `Label(y, oracle, fail_kind, invalid_reason, identity, cve, detail)`：`y` 为 fail 时必须有 `fail_kind`，为 invalid 时必须有 `invalid_reason`，为 pass 时两者都是 None。`cve` 现在是空 dict，S4 填。
- `surprise.harness.oracles.judge(case, oracle, *, runner_factory=None, timeout_s=10.0) -> Label`：只判定，不记账。`IMPLEMENTED = ("tlp", "norec", "plan_variant")`，只支持 `engine == "duckdb"`，其余抛 `ValueError`。
- `surprise.harness.oracles.forms.full_query(case)`：把划分谓词并进查询后的那一条语句，确定性筛查与 plan variant 用它。`split_grouped(query)` 识别 `SELECT 键 FROM … [WHERE …] GROUP BY 键` 与 `SELECT DISTINCT 列 FROM … [WHERE …]` 两种形态。
- `surprise.harness.evaluate.evaluate(case, oracle, *, ledger, run_id, purpose, spec, phi, theory_version, p_t, runner_factory, timeout_s) -> ExperimentRecord`：每调用一次恰好写一条记录。
- `Ledger(path)`：`start_run`、`run_manifest`、`run_ids`、`next_seq`、`append`、`records`、`count`、`label_counts`；出错抛 `LedgerError`。
- `python -m surprise.harness.manifest hash | write PATH [--run-id ID] | verify PATH`（在 `framework/` 下执行）：`verify` 退出码 0 表示 harness 未变，1 表示有文件变了并逐个列出，2 表示 manifest 读不了。
- `python -m surprise.gates.s02 --only <组> …`：只跑指定的组，给工作包做部分验收用。

`judge` 的流程是固定顺序：`setup` 有语句报错 → `setup_error`；`is_usable_for_oracles` 不通过 → `nondeterministic`；不满足该 oracle 的前提 → `not_applicable`；然后才调用旧 oracle。旧 oracle 返回 None 时，记录下来的查询形式里有超时 → `timeout`，有报错且全是值依赖错误 → `value_dependent_error`，有别的报错 → `query_error`，全部成功才是 pass。

### 与 PLAN 的偏差及原因

与 PLAN.md 没有冲突。下面几处是 PLAN 和 SESSIONS 没有写到、由编排者定下的，细节在 DECISIONS.md：

- 五个契约分放 `harness/` 与 `theory/` 两个文件，而不是集中一处。原因是 CLAUDE.md 规定 S4 之后 `harness/` 冻结，规格、假设、理论编辑到 S5–S7 才定型，放进去会被提前冻住。实验记录里的规格因此存成 dict，harness 不依赖理论层。
- PLAN 决策表第 6 条（实验账本用 SQLite）仍标着"建议"，本会话按 SESSIONS.md 的 S2 范围直接采用，没有单独再问。
- TLP 的 GROUP BY / DISTINCT 形态需要从查询文本里识别形态，这段识别是新写的（旧 `tlp_groupby` 要求调用方拆好了传进来）；PINOLO-lite（`conjoin` 参数）没有接。
- harness 哈希的范围除了 `surprise/harness/`，还列入了十个旧模块：适配器调用的是它们，只哈希新代码查不出旧判定逻辑被改。
- 门槛比 SESSIONS 列的四项多了契约、账本、manifest 三组，以及 `evaluate` 的参数校验一项（后者是审查中发现缺口后补的）。

### S4 门槛（M1）对已知复现的期望（验收时定，2026-10-09）

SESSIONS.md 对 `gates/s04.py` 的要求是"confirmed 族全部判 fail 且身份证据正确"。下表把每个族落到具体的复现和期望上，S4 写门槛时照这张表。"本机实测"都是 DuckDB 1.5.5、S2 的适配器、未经 CVE 的原始判定；探测脚本是 `.orch/scratch/` 下的 `m1_probe.py`、`m1_probe2.py`、`m1_probe3.py`（不入库）。

| 族 | 用哪份复现 | 本机实测 | M1 期望 | S4 要做的 |
|---|---|---|---|---|
| F1、F2、F7 | `recall_repros.json` | plan variant 判 fail / wrong_result，开关 `no_optimizer`，稳定 | fail | 第 3 档二分把开关细化成 fix set，与该条目的 `fix_set` 对照 |
| F9 | `recall_repros.json` | plan variant 判 fail，开关 `window_combine`，稳定 | fail | "调试开关一档"只是报告时的分层，不影响标签 |
| F11 | `duckdb/F11_merge_nmbs_rowid.sql` 里的 MERGE | plan variant 判 fail / crash，`error_class` 为 `InternalException`，开关 `no_optimizer`，稳定 | fail（crash） | 二分应落到 `build_side_probe_side`。写数据的语句只认 crash，见表后第 2 点 |
| F6 | `recall_repros.json` 的表结构和查询，补三行数据（表后第 1 点） | 不带谓词：plan variant 判 fail，开关 `no_optimizer`，`missing: 1`。带谓词 `o1.placed IS NOT NULL`：TLP、NoREC 判 fail，plan variant 判 pass | fail | 身份证据以二分结果为准，不要求等于该条目的空 `fix_set` |
| F3 | `recall_repros.json` | plan variant 判 fail，开关 `no_optimizer`，稳定 | invalid | 结果稳定，重跑筛不掉；要一条前提规则（ASOF 连接右侧有并列时取哪一行未指定） |
| F8 | `recall_repros.json` | 同一进程里三次判定相同（fail）；60 个新连接出现 8 种不同结果 | invalid | 新进程重跑不一致即可筛掉 |
| F5 | `recall_repros.json` | 200 个新连接里 20 次结果不对（10%）；plan variant 三次判定不一致，第一次是 fail，开关 `no_statistics` | invalid（重跑不稳定） | 第 1 档重跑加 threads=1 复判；把观察到的比例记进 `Label.cve` |
| F10 | `duckdb/F10_window_frame_underflow.sql` | 经适配器：试过的六种写法全部 invalid / nondeterministic，查询没有被执行。直接执行：前两条 ntile 语句都让进程以 0xC0000094 退出 | invalid；记为已知的召回缺口，不要求 fail | 新进程执行器要把"子进程异常退出"报成 crash，用这两条语句直接验证执行器（表后第 3 点） |

另有两份 `.sql` 文件按文件里的数据复现不出来，M1 期望 pass：
- `duckdb/F5_parallel_cte_offset.sql`：默认设置、threads=1、关优化器各 80 个新连接，全部返回 12 行。文件注释写的"Expected: 8 rows"是错的，正确行数就是 12。
- `duckdb/F6_null_exists_notin.sql`：默认与关优化器都返回 `[(1, 1)]`，三个 oracle 都判 pass。文件声称的"12 行对 8 行"出自原始见证，那份数据不在仓库里（全仓库只有文档提到 σ 键 `ab630f7b`）。

几点说明：

1. F6 的补充数据：`INSERT INTO orders VALUES (2, 1, -1e308, 'a', DATE '2021-06-15'), (3, NULL, NULL, NULL, NULL), (9, 1, 0.0, 'a', DATE '2015-05-05')`，照门槛用例 `metrics_small` 的三行改的。带谓词的形态把选择列表换成了 `o1.order_id, o1.amount`。这是重建的复现，不是原始见证；它很可能就是 F1 的机制落在 F6 的查询形态上（账本自己也这么猜）。二分落到 F1 的 fix set（`deliminator`、`filter_pushdown`）就把 F6 记成与 F1 同一机制。
2. plan variant 在同一个连接上依次跑各个变体。MERGE 这类写数据的语句每跑一次都改数据，后面的变体看到的是改过的表，结果比较不可信。S4 第 1 档的前提检查里，非 SELECT 语句只接受 crash，wrong_result 候选一律判 invalid。
3. F10 不要求判 fail 的原因：旧的确定性筛查（`oracles/determinism.py` 的 `has_nondeterministic_tiebreak`）把窗口里 ORDER BY 之后的帧子句也当成排序键，探测语句执行失败，于是判"不确定"。凡是显式写了帧的窗口查询都是这个结果，哪怕排序键唯一、写的就是默认帧。要让 F10 判 fail 得新写一段识别帧子句的筛查，这是新的判定逻辑，与 PLAN.md 总原则第 2 条"判定代码只搬不改"冲突，用户没有明确同意就不做。现状偏保守：只会少判，不会错判。
4. F5 判 invalid 是 PLAN.md 标签规则的直接结果（"重跑不稳定或结果不确定的也归此类"）。后果是 F5 这类时有时无的真缺陷在新框架里不计惊讶，理论学不到它；评估时把它和 F8 一起算作"不稳定"一类单独报告。

这张表与 SESSIONS.md 的字面要求有两处出入，都是事实逼出来的：F10 不判 fail（上面第 3 点）；F5 归到 invalid 一侧而不是 confirmed 一侧（上面第 4 点）。

### 未决问题（S3 及之后需要知道的）

S3发现、留后续会话：
- `datafusion/`的DF-B SQL注释漏了正确bag中的NULL，旧文件不改，留S12；S3门槛按实测包含NULL。
- manifest的environment还只记主Python、平台和DuckDB/DataFusion/SQLite；PG及旧版版本记录在oracle detail，PG二进制SHA256记在DECISIONS。S4冻结前评估是否补齐环境字段，S3不扩大环境重构范围。
- 实测旧CrossEngineOracle已把`SELECT DATE '2020-01-02' AS d`当跨库差异候选：DF旧runner返回ISO字符串，DuckDB/PG返回temporal前缀；S3 raw Cross标签也为fail/wrong_result（无CVE）。这是旧归一化的假差异，不应算确认bug。按范围纪律不改旧normalizer、不追加Cross返工；S4必须在跨库前提检查里保守invalid或建立兼容的比较前提。版本包自己的DF新旧传输差异在S3修正，两版本原始类型/值确实相同。

S2 新发现：
1. `duckdb/F10_window_frame_underflow.sql`（2026-10-09 按实测改写）：直接用 duckdb 执行，前两条 ntile 语句都让解释器进程以 0xC0000094 退出，文件注释只把第二条描述成 INTERNAL 错误。经 `judge` 则不会崩：确定性筛查在执行之前就把它们判成 `invalid / nondeterministic`。所以这一族现在既拖不垮 harness，也抓不到，处理办法见上面一节的第 3 点。别的查询仍然可能让引擎进程崩溃，`evaluate()` 在进程内拦不住；S4 的新进程执行器和 S8 的运行循环要考虑这一点。
2. 已知复现在本机 DuckDB 1.5.5 上被这三类 oracle 抓到的情况，以及 S4 门槛对每一族的期望：见上面"S4 门槛（M1）对已知复现的期望"一节（2026-10-09 按实测重写；原先写的"F5 抓不到""F6 什么都复现不了""F11 没有试"都已更正）。
3. TLP 的 GROUP BY / DISTINCT 形态没有已知的失败复现，门槛只覆盖了它的 pass 与 invalid。
4. `(query, predicate)` 只在 TLP 认识的形态下能合成一条合法语句。例如带聚合的分组查询再给一个谓词，`full_query` 会拼出 `… GROUP BY b WHERE (…)`，执行报错，三个 oracle 都判 invalid。这是有意的（坏用例就是 invalid），但 S8 的 Hunter 生成用例时要知道。验收时定为维持不改：遇到 TLP 不认识的形态，把过滤条件写进 `query`、`predicate` 留空。
5. plan variant 的 28 个变体里，`ordered_agg_off` 的开关语句 `SET ordered_aggregate_threshold=0` 在 DuckDB 1.5.5 上报 Parser Error，这个变体实际是空操作：查询照默认设置跑一遍，被算进 `variants_compared`。这是旧代码变体表的问题，没有动。
6. 契约拒绝非有限的浮点数（JSON 表示不了 NaN 和无穷大）。S6 算惊讶时如果 P_T 取到 0 或 1，要先截断再写进 `ExperimentRecord.surprise`。
7. `Label.cve` 仍是空 dict 占位，四步（rerun、premise、minimize、profile）各自记什么由 S4 定。S3已给`INVALID_REASONS`追加untrusted_rewrite、direction_unknown、insufficient_engines、non_unique_outlier，共十一项；S4的重跑不稳定等来源继续往表里加，冻结之前可以改。
8. 已解决：S3 registry包已让`judge`和`evaluate`支持DuckDB/DataFusion，两引擎映射统一；SQLite/PG仅作参照，不作首发目标。
9. `oracles/forms.py` 依赖旧模块 `oracles.determinism` 里带下划线的两个函数（`_top_level_positions`、`_top_level_from_pos`）；`theory/contracts.py` 复用了 `harness/contracts.py` 里带下划线的序列化辅助函数。S12 整理旧代码、或 S4 之后想动这些辅助函数时要同步。
10. 种子语料在 DuckDB 1.5.5 上的无效率不低：差分核对的 196 个种子变异里有 72 个在 setup 阶段就报错。S8 用种子做探索起点时会看到很多 `setup_error`。
11. manifest 的环境一节只记了 Python、平台和三个引擎的版本，没有记 pyarrow 等间接依赖（`.venv` 继承 anaconda base，环境不完全可复现，见下面沿用的第 7 条）。
12. （验收时发现）F9 的触发面很宽：`SELECT id, count(*) OVER (ORDER BY v) FROM t1` 这样排序键唯一的普通窗口计数，plan variant 就在 `window_combine` 下判 fail（8 行全不同）。S8 的探索一碰窗口聚合就会反复撞上这一族，理论要能尽快把它归到一个假设里，否则预算会耗在重复上。
13. （验收时发现）显式写了帧子句的窗口查询一律被确定性筛查判成 `invalid / nondeterministic`，原因见"S4 门槛（M1）对已知复现的期望"一节的第 3 点。S8 生成用例时要么不写帧子句，要么接受这部分全是 invalid。
14. （验收时发现）`duckdb/F5_parallel_cte_offset.sql` 的注释"Expected: 8 rows"是错的（正确是 12 行），`duckdb/F6_null_exists_notin.sql` 的数据复现不出它声称的现象。两个文件都没有改，留给 S12 整理复现文件时处理。

沿用自 S1、仍然有效的（编号沿用 S1 交接里的）：
1. 要导入 `oracles.*` 或 `targets.*`，解释器里必须同时有duckdb和psycopg2。`.venvs/duckdb-1.1.3`两样都有；`.venvs/datafusion-50.0.0`两样都没有。S3保持此隔离，旧版DF子进程只直接导入datafusion与标准库，原始行JSON传回，主进程归一化；新入口当前由version包实现中。
2. 旧代码把旧版解释器写死成 `<venv>/bin/python`（`oracles/differential.py` 第 37 行、`main.py` 第 142 行），Windows 上是 `Scripts/python.exe`，所以旧主循环在本机 Version differential 恒为 disabled。决定：S12 之前不改旧代码；S3 的适配器自己按平台定位解释器（`gates/s01.py` 的 `venv_python()` 是现成写法）。
3. `campaigns/pg_upgrade_mxact.py` 第 55 行在模块顶层抛 TypeError；`campaigns/pg_repack_mvcc.py` 导入即执行。旧问题，没修。
5. 文档里还是旧路径 `scripts/pg_*.py`，留给 S12。
6. `gates/s01.py` 里写死了 41 个脚本、基线通过数 64、三个环境的版本号、`v1-baseline` 的提交号；`gates/s02_cases.py` 里的期望值是在 DuckDB 1.5.5 上测的。换引擎版本或再移动旧代码时要同步改门槛，改之前问用户。
7. `.venv` 是继承 anaconda base 的 uv venv，环境不完全可复现。
9. `oracles/db_runner.py` 少一个空行，S12 顺手补。
10. 执行者可以用脚本写文件，deny 规则管不到，靠审查兜底。

沿用自 S0 与规划会话、仍然有效的：
- 仓库没有配置远端，异地备份是用户的事。
- 新会话里 Claude Code 的安全分类器可能拒绝启动 grok（S1、S2 都没有被拒）。用户的长期批准记在 DECISIONS.md；再被拒就停下来问用户，不要绕过。
- 执行者的 shell 是 Windows PowerShell 5.1：没有 `&&`，中文输出乱码。
- `SESSIONS.md` 开头写的开场提示词路径不对，实际是同目录的 `RUNBOOK.md`。那是用户的文件，没有改。
- `framework/test_api.py` 在设置了 `DEEPSEEK_API_KEY` 时会真的调用 API；日常测试命令只跑 `testing/` 和 `tests/`。
- `coevo/` 被 `tests/test_verified_loop.py` 依赖；它的新进程执行在 S4 被吸收，S12 再归档。
- `framework/config.yml` 里 `database.version` 写的是 1.5.2，实际是 1.5.5；`database.old_venv` 是旧机器上的路径。
- PLAN.md 决策表第 2、4、5、7–10 条仍是建议，到对应会话开工时再定（第 6 条本会话已采用）。

### 给下一个编排者的操作提醒

这几条都是本会话或上一会话实际踩到的：

- **`gw status --wait` 不要加 `--timeout`**。那个参数是"包运行超过这么多分钟就终止"，不是"最多等这么久"。本会话因此误杀了一个跑了 11 分半的包。想限制等待时间，用后台任务或命令自身的超时。
- 任务说明里写明"不要清理 `.orch/tmp`"。执行者收尾时喜欢清理临时文件，递归删除会被 deny 规则拦下，然后它会改成逐个删除，擦着"被拒绝的操作不要换写法重试"的边。
- CLAUDE.md 里的测试与门槛命令写的是 `../.venv/Scripts/python.exe`，这个路径在 worktree 里不存在。任务说明里要写明直接用 `python`。
- 往审查包里写结论时，文本里不要出现反斜杠转义（如反斜杠加 0、反斜杠加 n）：它们会被展开成真的 NUL 和换行，git 会把文件当成二进制。本会话为此补过一次提交。
- `git merge` 不能用 `-F -` 从标准输入读提交信息，要用 `-m`；合并成功并核对过之后再打 tag，两步不要连在一条命令里。
- 并行的包合并之前，各自 worktree 里的门槛都会因为缺另一个包而报"门槛未通过"，这是预期的红旗；用 `--only` 跑它自己的那几组。编排者补了门槛之后，可以用主检出区的门槛文件去跑分支上的代码来复核（本会话的做法记在 `orch/s02/s02-oracles.review.md` 的结论里）。
- 编排者自己的审查辅助脚本放在 `.orch/scratch/`（不入库）：列出执行者跑过的全部命令、种子语料差分核对、用主检出区的门槛跑别的检出。会话的临时目录中途可能失效，不要把还要用的脚本放在那里。

### 下一会话的起点

- S3 从 tag `s02-done-r2` 建分支 `session/s03`（`s02-done` 不含验收后的修订，不要从它起）。
- 起点检查（在 `framework/` 下）：`../.venv/Scripts/python.exe -m pytest -q testing tests` 应为 149 passed, 3 skipped；`../.venv/Scripts/python.exe -m surprise.gates.all` 应为 `GATES: PASS (2/2 passed)`。
- S3 按 ORCHESTRATION.md 第 8 节可拆 3–4 包并行。四类新 oracle 都落在 `framework/surprise/harness/oracles/` 下，按文件归属拆包时注意 `oracles/__init__.py`（`IMPLEMENTED` 与 `judge` 的分发）是公共文件，要么先单独一包把分发改成注册式，要么指定只由一个包来改。审查时 `--expect-passed 149`。
- 派发脚本一律用 `.venv/Scripts/python.exe tools/orch/grok_worker.py …`；合并时设 `ORCH_COMMIT_TRAILER` 给合并提交加署名尾注。
