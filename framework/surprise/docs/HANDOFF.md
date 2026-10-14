# HANDOFF

## 状态总览

| 会话 | 内容 | 状态 | tag | 门槛 |
|---|---|---|---|---|
| S0 | 编排准备（派发工具） | 完成 | s00-done；s00-done-r2（CLAUDE.md 写入"执行者模式"之后） | 冒烟包 s00-smoke 四项确认全部通过（没有 gates/s00.py） |
| S1 | Phase 0 冻结基线与仓库整理 | 完成 | s01-done；s01-done-r2（验收后的修订） | `gates/s01.py` 7/7；pytest 64 passed, 3 skipped |
| S2 | Phase 1a 契约、账本、三类健全 oracle | 完成 | s02-done；s02-done-r2（验收后的修订，S3 从这里起） | `gates/s02.py` 5/5；pytest 149 passed, 3 skipped |
| S3 | Phase 1b 其余三类 oracle 与 Index presence 移植 | 完成 | s03-done | S03 5/5；pytest 242 passed, 3 skipped；GATES PASS 3/3 |
| S4 | Phase 1c CVE 流水线（M1） | 完成 | s04-done | S04 9/9；pytest 275 passed, 3 skipped；GATES PASS 4/4 |
| S5 | Phase 2 共同语言 φ | 完成 | s05-done | S05 9/9；pytest 367 passed, 3 skipped；GATES PASS 5/5 |
| S6 | Phase 3a 理论 T 核心 | 完成 | s06-done；s06-done-r2（用户验收之后，S7 从这里起） | S06 12/12；pytest 514 passed, 3 skipped；GATES PASS 6/6 |
| S7 | Phase 3b 理论存储与接受规则 | 完成 | s07-done；s07-done-r2（用户验收之后，S8 从这里起） | S07 15/15；pytest 550 passed, 3 skipped；GATES PASS 7/7 |
| S8 | Phase 4 Hunter 与无 LLM 闭环（M2） | 进行中 | | |
| S9 | Phase 5a LLM 网关、实现器、猜想者 | 未开始 | | |
| S10 | Phase 5b 其余四个 LLM 角色（M3） | 未开始 | | |
| S11 | Phase 6 评估管线（M4 冒烟） | 未开始 | | |
| S12 | Phase 7 收尾 | 未开始 | | |

以前各会话的交接全文在对应 tag 的本文件里（S0：`s00-done-r2`；S1：`s01-done-r2`）；其中仍然有效的未决问题已并入下面的清单。

## 进行中会话：S8（2026-10-15 开工）

用户验收 S7 时指示"然后开始S8"。会话分支 `session/s08` 从 `s07-done-r2`（f762a66）建立；PG 服务器原先停着，按 S3 一节的命令启动（没有重新 initdb）。起点独立复跑：pytest 550 passed, 3 skipped；GATES PASS 7/7。

派发前的探测（不入库，`.orch/scratch/s8/`）：
- 旧系统 no_llm 跑 10 分钟（`main.py --mode no_llm --seed 0`，到点强杀）：39 轮，其中两段各卡了约 3.5 分钟；报了 5 条 bug，按 fix set 只有两个机制（F1 的 `deliminator, filter_pushdown` 三条、`join_order` 两条），另有 122 条被 DCE 判为已有家族的成员。σ 把 plan diff 算进键里，同一个 fix set 被报成几条。
- 原型主循环（`proto.py`，只作可行性探测，不是规格）80 步约 3.3 分钟：每步约 2.5 秒（取 φ 约 0.7 秒、`evaluate_final` 约 1.7 秒）；第 11 步开出一个家族（plan variant，fix set `join_order`，`error_mismatch`），之后 6 条失败都落在它的待定区并被归属测试吸收；冷启动的无效率高（TLP / NoREC 拿到没有谓词的种子判 `not_applicable`，种子 setup 在 1.5.5 上报错）；DCE 的算子几乎改不动只剩三个字面量的 S，细化 / 泛化车道没有产出候选。
- 旧系统会在某些种子上长时间占满 CPU（`DuckDBRunner.setup` 没有超时）；新框架的 φ 提取同样会执行 setup，所以候选的 φ 由常驻子进程提取并加超时。
- 建了 `.venvs/duckdb-1.1.3-full`（uv，继承 anaconda base；duckdb 1.1.3、datafusion 54.0.0、psycopg2-binary 2.9.13、sqlglot 30.21.0、pyarrow 21.0.0、pyyaml、pytest），在 DuckDB 1.1.3 上跑整个新框架用；harness 在它下面导入正常，manifest 里引擎版本记为 1.1.3。

拆包（进行中，合并一个更新一次）：

| 包 | 内容 | 允许路径（相对 `framework/`） | 依赖 | 状态 |
|---|---|---|---|---|
| s08-hunter | Hunter：四条车道的候选、打分 `value = P_valid × (D + β·U)`、探索保底、降权、新颖性拒绝、常驻 φ 提取子进程；`theory/constants.py` 加 `BETA`（暂定 1.0） | `surprise/hunter/**`、`surprise/theory/constants.py`、`tests/test_surprise_s08_hunter*.py` | s07-done-r2 | 已合并（6bd08d9，返工 1 轮，三处都是编排者的错；575 passed / 3 skipped） |
| s08-eval | 指标与基线：惊讶曲线与锯齿、家族重复率（统一的身份键）、已知 bug 召回、旧系统 no_llm 按墙钟预算跑 | `surprise/metrics/**`、`surprise/baselines/**`、`tests/test_surprise_s08_eval*.py` | s07-done-r2 | 已合并（8a60a37，首轮通过，返工 0 轮；572 passed / 3 skipped） |
| s08-loop | 无 LLM 的 Diagnoser 与主循环命令行（账本、存储、进度、报告） | `surprise/diagnoser/**`、`surprise/experiments/**`、`tests/test_surprise_s08_loop*.py` | 前两包 | 已合并（fc17952，首轮通过，返工 0 轮；610 passed / 3 skipped） |
| s08-resample | Hunter 一轮抽空时重抽（`EMPTY_ROUNDS = 20`），探索只抽 setup 没坏过的种子 | `surprise/hunter/hunter.py`、`hunter/constants.py`、`tests/test_surprise_s08_hunter*.py` | 三包 | 已派发 |

三包都已合并（2026-10-15）。编排者自己跑（进行中，产物在 `framework/results/s08/`，不入库）：

- β 预实验已做完：每组 300 条、约 3–7 分钟；不同身份的家族数 β=0.5 → 1,3,3；1 → 3,3,3；2 → 3,3,3；4 → 3,5,1，按规则取 1.0（就是暂定值，不用另派包），已钉进 `gates/s08_runs.json`（121adc9）。
- 2026-10-15 07:37 同时启动三个运行（编排者的后台任务）：`results/s08/longrun`（DuckDB 1.5.5，种子 0，180 分钟）、`results/s08/old_no_llm`（旧系统 no_llm，种子 0，180 分钟到点强杀）、`results/s08/recall113/run`（`.venvs/duckdb-1.1.3-full`，种子 0，60 分钟，不用 Version differential）。`results/s08/recall113/known.json` 已在 1.1.3 上算好（F1、F7、F7_file、F9、F6、F6_predicate 判 fail，三个身份；F2 pass、F11 invalid）。
- 第一次的三个运行作废（产物移到 `results/s08/aborted-1/`）：1.1.3 的召回 run 7.7 分钟、326 条就以 `exhausted` 停了，原因是某一轮抽到的候选全被过滤掉、Hunter 返回空、主循环当作"无可再测"；长跑 8.5 分钟 448 条时同样的问题已有苗头（一轮 78 个探索候选里 71 个因坏 setup 被丢）。长跑与基线随即停掉。派了修复包 `s08-resample`（一次选择最多重抽 20 轮；探索只从 setup 没坏过的种子里抽），合并后三个运行重跑。
- 中断了的话：三个目录要整个删掉重跑（`loop` 不支持续跑，要求输出目录为空）；跑完之后用 `.orch/scratch/s8/pin.py longrun old recall` 写哈希，`recall score` 先写出 `recall.json`。β 预实验（独立种子）→ 定 `BETA`（与暂定值不同时另派一个只改常数的小包）→ DuckDB 1.5.5 上 3 小时长跑与同墙钟的旧系统基线（并行）→ DuckDB 1.1.3 上的召回 run → 把产物的哈希钉进 `gates/s08_runs.json` → 收尾。门槛 `gates/s08.py` 的定义与理由见 DECISIONS 的 S8 条目。

## 最近完成会话：S7（2026-10-09）

Claude Code 担任编排者，全部实现来自 grok 工作包。用户指示"继续完成 S7"。会话分支 `session/s07` 从 `s06-done-r2`（0361b75）建立；起点独立复跑 514 passed, 3 skipped 与 GATES PASS 6/6。两包全部合并，收尾合并回 main，tag `s07-done`。用户验收后另打 `s07-done-r2`（只多了验收记录，代码与门槛相同）；S8 从 `s07-done-r2` 起。

**用户验收（2026-10-15）：** 用户的答复是"确认S7中的新常数和编排规则，然后开始S8"。

### 交付与门槛

理论的存储与接受规则，全部在 `framework/surprise/theory/`，不连接引擎、不执行 SQL、不调用模型；`harness/`、`features/`、冻结清单没有动；S6 的规则与 `Theory` 的既有行为没有动。

- 常数四项（`theory/constants.py`，进 run manifest 的 `theory` 一节）：`MDL_HYPOTHESIS_BITS = 8.0`、`MDL_LITERAL_BITS = 7.4`、`ACCEPT_HOLDOUT_MAX = 1000`、`ACCEPT_TOLERANCE_BITS = 1e-9`。`gates/s07.py` 的 `constants` 组钉住取值：**此后改它们先问用户**。
- 存储（`theory/store.py`，`TheoryStore`）：一个目录，`hypotheses/<编号>.json` 每个假设一个文件，另有 `head.json`、`residual.json`、`validity.json`、`passes/<引擎>__<oracle>.jsonl`，三份只追加的日志 `journal.jsonl`（观察与事件）、`edits.jsonl`（编辑日志）、`negative.jsonl`（负记忆），`generations/g<六位代号>.json` 每个已结束的代一个快照。读盘严格：任何手改都会让版本号对不上，抛 `StoreError`，不"修好了再返回"。
- 编辑（`theory/edits.py`）：五类 `add / revise / split / merge / retire`；每条带理由与押注；提出者只定身份与 S，其余由证据重算；编辑加进来的假设一律铸新编号。
- 接受检验：触发记录上惊讶不升、留出记录上惊讶不升、（惊讶变化 + 长度变化）严格为负，三条同时成立才接受。
- 工作台（`theory/workbench.py`，`Workbench`）：在用的理论加存储。`observe` 记日志、兑付押注、必要时回滚、落盘；`propose` / `assess`；`rollback`（快照加重放，级联）；负记忆按断言的指纹拒收；`checkpoint` 切代；MDL 的 `merge_candidates` / `repair_candidates` / `compress`；`owner_of` / `family_of` / `families` / `partition`；`surprise_under(代号, 记录)`。
- `Theory` 加了 `next_id`、`remove`、`reserve_id`、`passes`；合取语言加了 `common_conjunction`；`theory/length.py` 给出描述长度。

门槛十五组与 SESSIONS 的对应：`replay` 把已知复现与重新生成的 DCE 探针在真实引擎上离线喂一遍，查五个量级、执行前识别重复、一条故意错误的编辑被回滚并进负记忆；`ledger` 拿同一次回放的家族划分与人工账本比，要求不低于 σ；其余十三组是不碰引擎的逐条规则检查（常数、长度、`Theory` 的补充、存储、快照、导入、编辑、接受、回滚、重开、MDL、家族、按代惊讶）。

最终复跑（两包合并后在 `session/s07` 主检出区独立运行，在 `framework/` 下）：

| 命令 | 结果 |
|---|---|
| `../.venv/Scripts/python.exe -m pytest -q testing tests` | 550 passed, 3 skipped，退出码 0（起点 514，新增 36，skip 未增加） |
| `../.venv/Scripts/python.exe -m surprise.gates.all` | S01 7/7、S02 5/5、S03 5/5、S04 9/9、S05 9/9、S06 12/12、S07 15/15；GATES: PASS (7/7 passed)，退出码 0 |

`gates/s07.py` 单独跑约 5 分钟（`replay` 约 4 分钟，`ledger` 约 1 分钟，其余十三组合计几秒）；`surprise.gates.all` 约 11 分钟。

### 实机回放的数字

回放的内容：人工账本明文裁定到某一族的 24 条语句（十族：F1、F2、F7、F9、F11、DF-A、DF-B、DF-D、DF-F、DF-I；清单与出处在 `gates/s07_cases.py`），每族第一条语句的 DCE 探针若干（共 38 条，`evolution/dce.py` 的算子重新生成、等距取样），每族第一条语句再喂一遍，外加一条故意错误的编辑及其押注实验。共 74 次实验，全部经 `evaluate_final` 入账。

| 位置与结果 | 条数 | 惊讶（比特） | 分诊 |
|---|---|---|---|
| 未探索区失败 | 4 | 6.64 | new_family |
| 确认区通过 | 5 | 4.32 | unexpected_pass |
| 待定区失败 | 13 | 1.00 | boundary_move |
| 确认区失败 | 48 | 0.07 | duplicate |
| 未探索区通过 | 1 | 0.01 | no_information |
| 无效 | 3 | 不计 | invalid |

- 每条记录的惊讶都能由账本里的 `p_t` 与标签重算出来（门槛逐条核对）。
- 执行前识别重复：十族的第一条语句再喂一遍，十次都在执行前落在确认区，执行后都只做了一次归属测试（第 2 档，没有最小化与画像）。全部 65 条失败里，11 条开出家族（各做一次第 3 档画像），54 条归入已有家族；这 54 条里 47 条执行前就被预测为重复，其余 7 条落在待定区（1 比特的边界移动）。
- 故意错误的编辑（在 DF-A 之后）：把 DF-A 的假设改写成"左输入有重复行就丢行"，S 从十个字面量变成一个。接受检验通过（惊讶不变，长度少 66.6 比特）。它押注"UNION ALL 且左侧有重复会失败"；真实执行 UNION ALL 通过（落在这条编辑的确认区，4.32 比特），押注落空，编辑回滚，理论回到编辑之前并学到这条通过；负记忆里多一条；原样再提被 `negative_memory` 拒收；同一条 UNION ALL 再喂一遍落在未探索区，0.01 比特。
- 回放结束时 11 个假设。`compress()` 没有应用任何编辑：两对合并候选（DF-A 与 `DF-D_where` 的假设、DF-D 与 DF-F 的假设）都因为并起来的 S 会盖住一条已知的通过而被留出记录拒掉；没有修复候选。

与人工账本比家族划分（24 条裁定语句，配对计数）：

| 划分 | 家族数 | 精确率 | 召回率 | 配对 F1 | ARI |
|---|---|---|---|---|---|
| 人工账本 | 10 | | | | |
| 新框架（执行前成员检验 + 版本空间） | 11 | 1.00 | 0.95 | 0.976 | 0.974 |
| σ（旧系统的家族键，由 CVE 画像按旧规则重算） | 19 | 1.00 | 0.29 | 0.444 | 0.425 |

新框架与账本唯一的出入：`DF-D_where`（`SELECT a FROM t WHERE b > 0`，只少行）被分到 DF-D（少行多行都有）之外，因为没有开关的身份按行为形状分。σ 没有把不同族并在一起，但把一族拆碎：F9 两个键（就是人工账本里的 AUTO-f50fc0f3 与 AUTO-13f4608a，重算出来逐位相同），DataFusion 上因为没有 fix set、没有计划差异、没有版本梯，键退化成"最小化用例的文本摘要"，每条语句一个键。代价的对比：σ 要给每一条失败做完整画像；新框架里 54 条重复有 47 条只做了一次归属测试。

合取可表达的比例（PLAN 第 7 节；本机能回放的只有这十族，不是三十一族）：十族里九族的假设没有落在 S 内的通过；F2 有四条（改一个数据值就不再出错的探针，φ 与正例相同），现有词表分不开，属于要靠 S10 发明新特征的情形。

误吸收（S6 留的未决问题，要求量一下）：门槛这次回放的 65 条失败里没有一条被两个假设同时吸收。派发前另一次范围更大的探测（含重建的 F6、每族 12 条探针，约 170 次实验）里出现过两类：F7 的两条探针失败在被归属测试判给 F7 的同时，也被没有 fix set 的 F9 假设按三项画像当成正例；DF-F 的首条失败落在 DF-D 假设的待定区、形状相同，被吸收进去，两族并成一个假设。后者只在该作用域还没有几条通过、G 还很松的时候发生；这次回放的喂入次序下 DF-D 的 G 已经被收紧，DF-F 开出了自己的家族。规则没有改，见未决问题。

### 拆包清单与结论（全部已合并）

| 包 | 内容 | 轮数 | 合并 | 审查 |
|---|---|---|---|---|
| s07-store | 四个常数、`Theory` 的四个接口、`common_conjunction`、长度、`TheoryStore` | 首轮通过，返工 0 轮 | 60563a1 | 独立复跑 528 passed / 3 skipped；与参考模型逐字节差分 23995 项零出入（含 360 次损坏注入）；19 条命令已看；约 1.84 美元。发现日志追加随长度线性变慢，写进下一个包顺带修 |
| s07-accept | 编辑、接受检验、工作台、回滚、负记忆、MDL、家族；日志序号缓存 | 首轮通过，返工 0 轮 | 8061cef | 独立复跑 550 passed / 3 skipped，GATES PASS 7/7；与参考模型在 300 段随机历史上逐步差分 29709 项零出入；真实引擎两组的数字与派发前逐项相同；15 条命令已看；约 1.93 美元 |

说明、报告、审查包归档在 `docs/orch/s07/`。没有返工，没有推翻包。grok 成本合计约 3.77 美元。两个包首轮都过，做法同 S6：派发前规则已经用参考模型在真实引擎上把门槛跑通，说明里把每一步都写了出来；审查的力气花在随机差分上。

### 当前接口

`surprise.theory` 新增导出（S8 直接用）：

- `TheoryStore.create(root)` / `.open(root)`：`root`、`last_seq`、`head()`、`save(theory)`、`load()`、`append_journal(entry)`、`journal(after=0)`、`append_edit(edit)`、`edit_history()`、`edits()`、`append_negative(entry)`、`negatives()`、`close_generation(theory, cause=...)`、`generations()`、`load_generation(n)`、`verify()`；`StoreError`。一个存储目录同一时间只由一个实例写。
- `Workbench.create(root)` / `.open(root)`：`store`、`theory`（当只读用）、`generation`、`predict(phi, oracle)`、`observe(phi, label, record_id, *, prediction=None) -> Outcome`、`assess(proposal) -> Assessment`、`propose(proposal) -> TheoryEdit`、`rollback(edit_id, *, reason="manual", record_id=None)`、`checkpoint(note)`、`records()`、`seen(record_id)`、`edits()`、`edit(edit_id)`、`negatives()`、`open_bets()`、`merge_candidates()`、`repair_candidates()`、`compress()`、`owner_of(record_id)`、`family_of(hypothesis_id)`、`families()`、`partition()`、`surprise_under(generation, record_ids)`。
- `Outcome`：`observation`（S6 的 `Observation`）、`seq`、`owner`、`bets`、`rolled_back`。
- `Proposal(kind, rationale, proposer, removes=(), adds=(), bets=(), trigger=())`；`Seen(record_id, phi, label)`；`Assessment`；`EDIT_KINDS`、`REJECT_REASONS`、`ROLLBACK_REASONS`、`BET_STATES`；`claim`、`fingerprint`、`default_bets`、`bet_matches`、`holdout_sample`。
- `Theory.next_id`、`.remove(id)`、`.reserve_id()`、`.passes(engine, oracle)`；`common_conjunction(a, b)`；`hypothesis_length(h)`、`theory_length(theory 或一串假设)`。

一次实验在 S8 主循环里的顺序（门槛的 `replay` 组就是这么写的，比 S6 只多了把 `Theory` 换成 `Workbench`）：`phi = extract(case)` → `prediction = wb.predict(phi, oracle)` → `evaluate_final(case, oracle, ..., phi=phi.to_dict(), theory_version=wb.theory.version, p_t=prediction.p_fail_valid, hypothesis=attribution_request(wb.theory.get(prediction.hypothesis_id)))`（未探索区没有假设时改传 `diagnose=True`）→ `outcome = wb.observe(phi, record.label, record.record_id, prediction=prediction)`。`outcome.rolled_back` 非空说明这条记录让某条编辑的押注落空了，理论已经回到那条编辑之前并重放过。

编辑日志里一条记录（`TheoryEdit`）的 `payload`：`reason`、`fingerprint`、`trigger`、`holdout`、`length_delta`、`removes`、`removed`、`adds`、`added`、`generation`、`journal_seq`、`bets_state`、`rollback`。日志条目：`observe`（`record_id`、`phi`、去掉 `detail` 的 `label`）、`edit`、`rollback`（`reason`、`cascade`）、`checkpoint`。

### 规则（实现与门槛都按它；逐条细则在 `docs/orch/s07/` 归档的两份任务说明里）

框架文档的相关原文："理论的每次修改都写明理由和预测；预测落空的编辑自动回滚，并作为负面记忆留下，防止同一个错误猜想反复出现"；"新特征、拆分与合并必须在触发记录上降低惊讶，在留出记录上不增加惊讶"；"理论修改的目标：最小化'累计惊讶 + 理论长度'（MDL），作为假设拆分和合并的判据"；"通过的结果、退役的假设、被拒绝的提议都保留为负记忆"。

- **两种变化**：规则更新（`Theory.observe` 按 S6 的规则动 S、G、开新家族、记 R 与 Kᵛ）不是编辑，不走接受检验，留痕在观察日志；编辑是别人提出的改动，写进编辑日志。
- **编辑加进来的假设**：身份与 S 取提出者给的模板，编号新铸，G 从空合取起把该作用域记住的通过逐条回放（落在 S 里的成为矛盾），E⁺ 取被替换的假设的正例里仍落在新 S 内的（`add` 取同作用域里身份一致且落在 S 内的失败）。
- **接受检验**，依次：指纹在负记忆里，拒（`negative_memory`）；没有押注，拒（`no_bets`）；触发记录上惊讶之和升了，拒（`trigger`，进负记忆）；留出记录上升了，拒（`holdout`，进负记忆）；三项之和不是严格为负，拒（`no_gain`）；否则接受。惊讶是用现在的理论看旧记录；留出记录是编辑涉及的作用域里、触发记录之外的全部有效记录，超过 1000 条按记录编号的哈希取 1000 条。
- **长度**：每个假设 `8.0 + 7.4 × |S|` 比特；G 与证据不计。
- **押注**：`{"spec": 规格, "expect": "pass" | "fail"}`。第一条命中规格、标签有效的实验兑付它：标签等于期望为兑现，否则落空。只看标签，不看身份。
- **回滚**：先把当前理论封存成一代；取这条编辑之前封存的快照，编号计数器沿用现在的；把这条编辑之后的全部观察按原次序重放（重新预测）；之后接受的编辑一并撤销（`cascade`，不进负记忆）；这条编辑进负记忆（`bet_broken` 或 `manual`）。
- **负记忆的指纹**：只看加进来的各假设的（引擎、oracle、fix set、失败类别、错误类别、行为形状、约简后的 S）；退役按被撤回的断言算。编辑类型、提出者、编号、G、证据都不进指纹。
- **代**：接受编辑、回滚、检查点各结束一代；快照存一代结束时的理论。
- **MDL 候选**（接受与否都走同一个检验，押注用默认的"落在新 S 里的实验会失败"）：合并——同作用域、身份相同（都有 fix set 时只比 fix set；都没有时比三项画像）的一对，S 取两者的共同部分，为空不提；修复——假设的 `contradictions` 里有通过时，把正例按次序贪心分簇，使每簇的 S 不新盖住任何一条矛盾通过，一簇为收紧、多簇为拆分。`compress()` 反复应用第一条可接受的候选直到没有。
- **归属与家族**：一条失败属于把它列在 E⁺ 里的假设（多个时取归属测试点名的，否则最早的）；有 fix set 的假设按（引擎，fix set）跨 oracle 成一个家族，没有的一个假设一个家族。

### PI 已自行核查并定下的选择（用户已验收）

**用户验收（2026-10-15）：下面六条，用户答复"确认S7中的新常数和编排规则"。** 它们从此是用户确认过的决定，不再是"编排者定、可推翻"；四个新常数的取值照旧由门槛钉住，要改先问用户。

用户的指示是"继续完成 S7"；S6 交接里写着"S7 开工前要定的几件事"与新常数的取值，编排者没有另行提问，按推荐定下，依据是此前把确认事项交回编排者自行决定的约定。每一条都在 DECISIONS 里有理由。

1. **四个新常数的取值**。文档只说"最小化累计惊讶加理论长度"，没有给长度的单位与数值；8.0 与 7.4 比特是编排者定的（字面量按 167 项词表编码）。后果：一条矛盾通过（4.32 比特）付不起一个假设（15.4 比特）；收紧一个多写 8 个字面量的 S 要十四条以上的矛盾，拆出第二个十字面量的假设要三十五条以上；一条没有画像的失败付不起一个新假设，四条可以。嫌拆分太迟钝，调小 `MDL_LITERAL_BITS` 即可，门槛里相应的条数要跟着改。
2. **接受检验把文档的"在触发记录上降低惊讶"放宽成"不升"，再要求惊讶加长度严格变小**。否则合并（不降低任何已有记录的惊讶）与手写的 h2（DF-A 已经被规则解释成 0.07 比特）都过不了。
3. **押注只看标签、一次兑付**；全部兑现之后的编辑不再因为新的矛盾而回滚。
4. **回滚用"快照加重放"，并级联撤销之后接受的编辑**（后者不进负记忆）。
5. **家族的定义**：有 fix set 的按 fix set 跨 oracle 归并，没有的一个假设一个家族；与人工账本比划分时用 ARI 与配对 F1，真值只取账本明文裁定的 24 条语句，探针不计分，F6 不进真值表。
6. **`gates/s06.py` 改了一行**（新进程里打印整份常数名单而不是第一个），期望不变。

### 与计划的偏差

- ORCHESTRATION 第 8 节建议 S7 串行单包，实际拆成两个串行包（存储一包、接受规则一包）。
- SESSIONS 写"离线喂入已知复现与重新生成的 DCE 探针"：DCE 只用了它的两个探针生成函数（`mutate_query_text`、`mutate_setup`），由门槛调用；旧的 `FamilyExpander` 没有用（它自带判定与去重）。探针每族只取 2–6 条（等距取样），为的是把门槛控制在 5 分钟。
- PLAN 第 7 节"先测 31 个已确认家族中可用合取表达的比例"：只在本机能回放的十族上量了（九族可以，F2 不行）。其余家族不在首发引擎上，或在冻结的 harness 下不判 fail（见 S4 的召回缺口）。
- PLAN 总原则第 2 条写"惊讶公式、接受规则进 harness 并记录哈希"。harness 在 S4 已冻结，接受规则放在理论层（`theory/edits.py`、`theory/workbench.py`），它们的代码哈希由 `theory_manifest()` 记进 run manifest 的 `theory` 一节，做法与 S6 相同。
- 改了上一会话的门槛 `gates/s06.py` 一行（见上面第 6 条）。
- 没有与 PLAN 冲突的实现选择；没有做 Hunter、主循环、LLM 角色；没有改 S6 的规则。

S7 留下的未决问题在文末"未决问题"一节的"S7 发现"一组里。

## 最近完成会话：S6（2026-10-09）

Claude Code 担任编排者，全部实现来自 grok 工作包。用户指示"继续完成 S6"。会话分支 `session/s06` 从 `s05-done`（8c37d25）建立；起点独立复跑 367 passed, 3 skipped 与 GATES PASS 5/5。两包全部合并，收尾合并回 main，tag `s06-done`。用户验收后另打 `s06-done-r2`（只多了验收记录，代码与门槛相同）；S7 从 `s06-done-r2` 起。

### 交付与门槛

理论 T = (H, R, Kᵛ) 的核心，全部在 `framework/surprise/theory/`，不连接引擎、不执行 SQL；`harness/` 与冻结清单没有动。

- 常数九项（`theory/constants.py`）：`P_CONFIRMED = 0.95`、`P_PENDING = 0.5`、`RESIDUAL_PRIOR_FAILS = 1.0`、`RESIDUAL_PRIOR_TESTS = 100.0`、`VALIDITY_PRIOR_INVALID = 1.0`、`VALIDITY_PRIOR_TESTS = 10.0`、`TRIAGE_LOW_BITS = 0.5`、`TRIAGE_HIGH_BITS = 2.0`、`VS_MAX_GENERAL = 64`。`gates/s06.py` 的 `constants` 组钉住取值：**此后改它们先问用户**。
- 假设 h = (I, ΔP, V, S, G, E⁺, E⁻)：`Hypothesis` 契约加了六个带默认值的字段（`oracle`、`fail_kind`、`error_class`、`behavior_shape`、`contradictions`、`truncated`），S2 时期的对象与 dict 照样可用。
- 版本空间：S 是一个合取，G 是一组合取，字面量是词表里的叶子或类。正例泛化 S（删特征、同类不同值升到类），反例特化 G（取能排除反例的最一般的字面量，保留全部最小特化，去冗余，上限 64）。位置四种加"不在作用域"。
- 身份一致才算正例：harness 的归属测试结果优先，其次比 fix set，没有开关的比失败类别、错误类别、行为形状。
- 新家族的确定性初始化：I、ΔP、V 取自第 3 档画像；G 用此前同范围的通过回放收紧。
- R（每单元计数与未解释失败）、Kᵛ（按实验类与 oracle 的无效率）、P_T 与惊讶、六类分诊、`Theory.predict` / `Theory.observe`、状态往返与版本号。
- 常数进 run manifest：`extend_manifest()` 在 manifest 上加 `theory` 一节，`verify_theory_manifest()` 核对。

门槛十二组与 SESSIONS 的对应：`walkthrough` 在真实引擎上把框架文档的 DF-A → DF-B 案例走了一遍，用手写的 h2 代替 LLM——第一次失败 6.64 比特（"约 6.6"）；两个预测实验各 1.00 比特；`data:setop:left_has_dups` 进 G；INTERSECT ALL 的失败经归属测试判为身份不一致，对 h2 是反例，并开出新家族 h3。同一组里另有三步把分诊表其余几行也走到：DF-A 再来一次 0.07 比特（重复），左右重复数相同的 EXCEPT ALL 4.32 比特（意外通过），UNION ALL 0.01 比特（无信息）。其余十一组是不碰引擎的逐条规则检查。

最终复跑（两包合并后在 `session/s06` 主检出区独立运行，在 `framework/` 下）：

| 命令 | 结果 |
|---|---|
| `../.venv/Scripts/python.exe -m pytest -q testing tests` | 514 passed, 3 skipped，退出码 0（起点 367，新增 147，skip 未增加） |
| `../.venv/Scripts/python.exe -m surprise.gates.all` | S01 7/7、S02 5/5、S03 5/5、S04 9/9、S05 9/9、S06 12/12；GATES: PASS (6/6 passed)，退出码 0 |

`gates/s06.py` 单独跑约半分钟（`walkthrough` 约 20 秒，其余十一组不到 2 秒）；`surprise.gates.all` 约 6 分钟。

实机走查的数字（DataFusion 54.0.0，参照 DuckDB、PostgreSQL、SQLite）：

| 步 | 语句 | 预测时的位置 | 标签 | 惊讶（比特） | 分诊 | 理论的变化 |
|---|---|---|---|---|---|---|
| 1 | DF-A：`EXCEPT ALL`，左侧有重复行与 NULL | 未探索区（ρ = 0.01） | fail，第 3 档 | 6.64 | new_family | 开出 h1：S = φ 的十个叶子，G = 空合取，身份为"只少行" |
| 2 | （手写 h2 顶替 LLM：把 h1 的 S 换成 `ast:set_op:except_all` 与 `data:setop:left_has_dups`） | | | | | |
| 3 | 去掉左侧的重复行 | h1 的待定区 | pass | 1.00 | boundary_move | `data:setop:left_has_dups` 进 G |
| 4 | DF-B：换成 `INTERSECT ALL` | h1 的待定区 | fail；归属测试不一致，升第 3 档，"只多行" | 1.00 | boundary_move | 对 h1 是反例，G 收到与 S 相同；开出 h2，它的 G 被第 3 步的通过回放成三个候选 |
| 5 | DF-A 再来一次 | h1 的确认区 | fail，第 2 档归属一致 | 0.07 | duplicate | 记为 h1 的正例；对 h2 是反例，G 收到只剩 `ast:set_op:intersect_all` |
| 6 | 左右各两个 1 的 `EXCEPT ALL` | h1 的确认区 | pass | 4.32 | unexpected_pass | 记进 h1 的 `contradictions` |
| 7 | `UNION ALL` | 未探索区 | pass | 0.01 | no_information | 只有 R 的该单元加一 |

（表里的 h1、h2 是程序自动起的编号，对应框架文档里的 h2、h3。）不用手写的 S、只靠确定性规则时，第 3 步之后 G 是 `data:setop:left_has_dups` 与 `data:table:dup_rows` 两个候选（去掉左侧重复行同时也去掉了"表里有重复行"，规则分不出是哪一个），第 4 步之后两个候选各加上 `ast:set_op:except_all`；门槛两种走法都查。

### 拆包清单与结论（全部已合并）

| 包 | 内容 | 轮数 | 合并 | 审查 |
|---|---|---|---|---|
| s06-vspace | 常数、契约字段、合取语言、版本空间、建族、身份、归属请求 | 首轮通过，返工 0 轮 | cebb344 | 独立复跑 398 passed / 3 skipped；与参考模型差分 115002 项零出入；穷举核对 1655 个边界零出入；14 条命令已看；约 1.35 美元 |
| s06-theory | R、Kᵛ、预测与惊讶、分诊、`Theory`、manifest 一节、命令行 | 首轮通过，返工 0 轮 | 19686eb | 独立复跑 514 passed / 3 skipped，GATES PASS 6/6；与参考模型差分 63763 项零出入；不变量 14347 对零违反；13 条命令已看；约 1.81 美元 |

没有返工，没有推翻包。grok 成本合计约 3.16 美元。说明、报告、审查包归档在 `docs/orch/s06/`。两个包首轮都过，原因是派发前规则已经用参考模型跑通过门槛，说明里把每个函数的每一步都写了出来；审查的力气花在差分与不变量上，而不是等执行者猜规则。

### 当前接口

`surprise.theory` 导出（S7、S8 直接用）：

- `constants`（子模块，`as_dict()`）。
- 合取：`reduce_conjunction(ids, registry=None)`、`covers(conjunction, phi, registry=None) -> bool`、`generalize(specific, phi, registry=None)`、`specialize(general, specific, phi, registry=None)`。
- 假设：`Hypothesis`、`position(h, phi, oracle, registry=None)`（`confirmed` / `pending` / `outside` / `undetermined` / `out_of_scope`）、`apply_positive` 与 `apply_negative`（返回 `Update(hypothesis, outcome)`，outcome 为 `duplicate` / `generalized` / `specialized` / `contradiction` 或位置名）、`converged(h)`、`identity_match(h, label) -> True | False | None`、`new_family(hypothesis_id, phi, label, record_id, *, negatives=(), source="deterministic")`、`attribution_request(h) -> dict`（直接传给 `certify(..., hypothesis=...)`）。
- `Residual`（`observe(unit, y)`、`counts`、`rate`、`to_dict` / `from_dict`）；`Validity`（`observe(experiment_class, oracle, y, invalid_reason=None)`、`counts`、`reasons`、`rate`、`to_dict` / `from_dict`）；`experiment_class(phi)`。
- `Prediction`（`zone`、`hypothesis_id`、`confirmed`、`pending`、`unit`、`experiment_class`、`p_fail_valid`、`p_invalid`、`p_fail`、`p_pass`、`surprise(y)`、`to_dict()`）；`surprise_bits(p_fail_valid, y)`；`triage(y, bits)`；`ZONES`、`TRIAGE_KINDS`。
- `Theory(registry=None)`：`hypotheses`、`get`、`put`、`residual`、`validity`、`predict(phi, oracle)`、`observe(phi, label, record_id, *, prediction=None) -> Observation`、`to_dict()` / `Theory.from_dict()`、`version`。`Observation`：`prediction`、`y`、`surprise`、`triage`、`effects`、`opened`、`unexplained`。
- `theory_manifest()`、`extend_manifest(manifest)`、`verify_theory_manifest(manifest)`；命令行 `python -m surprise.theory {constants|manifest}`。

一次实验在 S8 主循环里的顺序（门槛的 `walkthrough` 组就是这么写的）：`phi = extract(case)` → `prediction = theory.predict(phi, oracle)` → `evaluate_final(case, oracle, ..., phi=phi.to_dict(), theory_version=theory.version, p_t=prediction.p_fail_valid, hypothesis=attribution_request(theory.get(prediction.hypothesis_id)))`（未探索区没有假设时改传 `diagnose=True`）→ `theory.observe(phi, record.label, record.record_id, prediction=prediction)`。

### 规则（实现与门槛都按它；逐条细则在 `docs/orch/s06/` 归档的两份任务说明里）

框架文档是《惊讶驱动的 CoevoDB：新框架与故事》（2026-10-07），仓库里没有，本机在 `C:\Users\91484\Desktop\` 下的同名 PDF。相关原文：`P_T(fail | x) = (1 − Kᵛ(x)) × [确认区约 0.95；待定区约 0.5；否则取 ρ_c]`；六类分诊表（未探索区失败约 6.6 比特、确认区通过约 4.3、待定区约 1.0、确认区失败约 0.07、未探索区通过约 0.01、无效不计）；"失败必须和假设的身份一致才算正例"。

- **语言**：合取是一组特征 id（叶子或类）；φ 满足它，当且仅当每个 id 都在 `registry.closure(φ.features)` 里。没有否定。约简形式：排序、去重、去掉层根（`ast`、`plan`、`data`）、去掉被同组里更具体的 id 蕴含的祖先。
- **S** 是一个合取，初值为第一条失败的 φ 的全部叶子；**G** 是一组合取，初值只有空合取（作用域内处处可能）。
- **正例**（落在待定区）：S 换成"S 的闭包与正例闭包的交"的约简（缺的特征删掉，同类不同值升到类）；G 里不覆盖该正例的成员删掉。落在确认区的只记进 E⁺。
- **反例**（落在待定区）：G 里覆盖它的每个成员，换成"加上一个 S 里它没有的字面量"的各种最小特化，字面量取该 S 字面量的祖先链上仍不在反例闭包里的最一般的那个；然后去掉被别的成员蕴含的成员，按（长度，字典序）排序，超过 `VS_MAX_GENERAL` 截断并置 `truncated`。落在确认区的通过无法排除，记进 E⁻ 与 `contradictions`，S、G 不变。
- **位置**：假设的作用域是（引擎，oracle）。φ 缺 S 提到的某一层时为 `undetermined`（既不算正例也不算反例）；满足 S 为 `confirmed`；否则满足某个 G 成员为 `pending`；否则 `outside`。
- **身份**：依次看 harness 第 2 档对这个假设的归属测试结果；有 fix set 的假设与第 3 档画像的 fix set 比较（没有画像则未知）；没有 fix set 的假设比较失败类别、错误类别、行为画像形状。身份不一致的失败对该假设是反例；未知则不更新。
- **新家族**：没有被任何假设吸收为正例的失败，带第 3 档画像时建立新假设：I 取 fix set，ΔP 取 plan diff，V 取版本梯，另记失败类别、错误类别、行为形状；G 用此前同作用域里见过的通过回放一遍。没有画像的记为未解释失败进 R。
- **R**：`ρ_c = (未解释失败 + 1) / (测过 + 100)`，按单元；只记预测时落在未探索区的通过，与任何没有得到解释的失败。**Kᵛ**：`(无效 + 1) / (做过 + 10)`，按（`引擎|主构造`，oracle）；每条实验都计，无效来源分开记数。
- **惊讶**：对有效结果按 `−log₂ P(y | 有效)` 算，无效不计。`ExperimentRecord.p_t` 记 `P(fail | 有效)`，所以账本里的 `p_t` 加标签就能重算惊讶。
- **分诊**按惊讶大小：不低于 2.0 比特，失败为新家族、通过为意外通过；0.5 到 2.0 为边界移动；低于 0.5，失败为重复、通过为无信息；无效单列。

### PI 已自行核查并定下的选择（用户已验收）

**用户验收（2026-10-09）：下面五条，连同"与计划的偏差"一节的六处，用户看过收尾消息后答复"都没有问题"。** 它们从此是用户确认过的决定，不再是"编排者定、可推翻"；九个常数的取值照旧由门槛钉住，要改先问用户。

用户的指示是"继续完成 S6"；S5 交接里写着要先问用户的两件事（第 1、2 条），编排者没有另行提问，按推荐定下，依据是此前两次"自行判断决定"的约定。每一条都在 DECISIONS 里有理由。

1. **理论常数九项的取值，以及它们进 manifest 的办法。** 0.95、0.5 是文档原值；ρ 的先验 1/100 由"未探索区失败约 6.6 比特"反推；先验的强度（100 次、10 次）、两个分诊阈值（0.5、2.0 比特）、G 的上限（64）文档没有给，是编排者定的。它们放在 `theory/constants.py`，由 `extend_manifest()` 写进 run manifest 的 `theory` 一节；`harness/constants.py`、`harness/manifest.py`、`gates/s04_frozen.json` 没有动。门槛钉住了这九个值。
2. **PLAN 决策 2 的版本空间一侧**：采用。单调合取加类层级，S 一个、G 一组，析取靠拆假设。
3. **惊讶以"有效"为条件算，Kᵛ 不乘进去**；`p_t` 记 `P(fail | 有效)`。文档的公式写的是联合概率，分诊表的五个量级却只与条件概率吻合，两者取了后者。
4. **分诊按惊讶大小分带，不按位置。** 两者在确认区、待定区恒一致；未探索区的 ρ 漂高后，按大小分的含义是"R 已经知道这个单元常失败，不再当新家族反复诊断"。这时 `Observation.triage` 可能是 `boundary_move` 或 `duplicate` 而 `prediction.hypothesis_id` 是 `None`。
5. **假设的作用域是（引擎，oracle）；G 的初值是空合取，建族时回放见过的通过。** 同一机制被两个 oracle 各自发现时是两个假设。

### 与计划的偏差

- ORCHESTRATION 第 8 节建议 S6 串行单包，实际拆成两个串行包（版本空间一包、理论组合一包）。
- 门槛的实机走查比 SESSIONS 的字面要求多三步（重复、意外通过、无信息），五个量级一次走全。
- PLAN 总原则第 2 条写"惊讶公式、接受规则进 harness 并记录哈希"。harness 在 S4 已冻结，惊讶公式放在理论层；它的代码哈希由 `theory_manifest()` 记进 run manifest 的 `theory` 一节，`verify_theory_manifest()` 能查出改动。没有改 harness。
- PLAN 第 7 节"先测 31 个已确认家族中可用合取表达的比例"没有做：SESSIONS 的 S6 门槛不含这一项，它需要逐族的最小复现与正反例，留给 S7 的离线回放（见未决问题）。
- 没有与 PLAN 冲突的实现选择；没有做持久化、回滚、MDL、Hunter、LLM 角色。

S6 留下的未决问题在文末"未决问题"一节的"S6 发现"一组里。

## 最近完成会话：S5（2026-10-09）

Claude Code 担任编排者，全部实现来自 grok 工作包。会话分支 `session/s05` 从 `s04-done`（9d88ff7）建立；用户此前指示 S4 完成后直接开 S5、需要确认的事项按编排者的推荐确认（逐项在 DECISIONS 的 S5 条目里）。开工时往 `.venv` 装了 `sqlglot==30.21.0`，装完起点检查为 275 passed, 3 skipped 与 GATES PASS 4/4。会话中途因用量上限中断过一次，靠 WIP 提交与本文件接上。三包全部合并，收尾合并回 main，tag `s05-done`；S6 从此 tag 起。

**用户的自主指示只到 S5 为止。** S6 要不要开、S6 里需要确认的事项怎么定，等用户发话。

### 交付与门槛

- 词表与类层级（`features/vocabulary.py`、`registry.py`）：167 项（门槛契约 `CORE_VOCAB` 的 166 项，加执行者追加的叶子 `ast:window_fn:other`），三层 `ast`、`plan`、`data`；种类为 class、leaf、family（开放族 `plan:<算子名>`、`ast:fn:<函数名>`）。注册表给出祖先、同类（"换同类取值"）、闭包，发明特征（正则类）的登记、验收记录、存取。词表摘要 `1e001c14a030…`，词表一变摘要就变，φ 里带着它。
- φ 容器（`phi.py`）：`Phi(engine, features, layers, vocab)`；`features` 是排好序的叶子 id，`layers` 记三层状态（ast：ok / fallback；plan、data：ok / unavailable / skipped）。没有任何随运行变化的内容；`to_dict` / `from_dict` 做结构校验，可以原样进账本的 `ExperimentRecord.phi`。
- 规格核对（`spec.py`）：`check_spec(phi, spec)` 判 φ ⊨ spec，必须项与数据性质要在 φ 的闭包里（所以规格可以写类一级的 id），禁止项不能在；某一层没算出来时相关项记为不确定，结论为不满足。
- 单元投影（`units.py`）：`引擎|oracle|主构造|计划算子类|数据性质类`，主构造十二种、计划算子类八种加 `none`、数据性质类五种加 `unknown`，各维按固定优先级取一个。
- 语句层（`ast.py`）：sqlglot 解析，特征只来自语法结构；解析不了（或一段文本不止一条语句）走正则兜底并带 `ast:parse:fallback`。已验收的发明特征按正则命中输出。
- 计划层（`plan.py`）：DuckDB 复用旧工具 `diagnosis.bisect.plan_op_names`（`EXPLAIN (FORMAT JSON)`），DataFusion 取 `EXPLAIN` 的 physical_plan 文本；算子名原样作特征。
- 数据层（`data.py`）：一律在库上算，而且不发聚合 SQL：把被引用的基表取回来在 Python 里数（空表、单行、重复行、NULL、零、负数、极端数、空串、非有限值、列类型）；集合运算的两个输入各自作为查询执行，判重复行与 NULL。被测语句本身从不执行。
- 组合入口（`extract.py`）：`extract`（调用方进程内）与 `extract_isolated`（子进程；崩溃、超时时语句层照算，`plan`、`data` 记 `unavailable`）。命令行 `python -m surprise.features {vocab|phi|corpus}`。
- 门槛九组：`vocab spec units`（s05-vocab）、`ast`（s05-ast）、`dynamic stable distinguish specs corpus`（s05-dynamic）。φ 跨进程稳定（25 个用例，两个子进程与本进程三方一致）；DF-A、DF-B 与 DuckDB F1–F11 的最小复现两两可区分（66 对），DF-A → DF-B 恰好是一次同类替换；17 组手写 spec / SQL 对全对；语料分布报告两次运行相同。
- 语料分布（`seeds/corpus.json`，门槛实测）：1092 条种子落在 76 个单元、10 种主构造；语句层兜底 34 条，计划层可用 480 条，数据层可用 483 条；最大的三个单元是 `postgres|plain|none|unknown`（134）、`duckdb|plain|none|unknown`（83）、`duckdb|window|none|unknown`（56）。

最终复跑（三包合并后在 `session/s05` 主检出区独立运行）：pytest 367 passed, 3 skipped（起点 275，skip 未增加）；S01 7/7、S02 5/5、S03 5/5、S04 9/9、S05 9/9，`GATES: PASS (5/5 passed)`。冻结清单未动（S04 的 freeze 组照常通过）。

### 拆包清单与结论（全部已合并）

| 包 | 内容 | 轮数 | 合并 | 审查发现 |
|---|---|---|---|---|
| s05-vocab | 词表、注册表、φ 容器、规格核对、单元投影 | 首轮 + 返工 1 轮 | 4b55eb1 | `Phi.from_dict` 与 `Registry.load` 不做校验；顺带改了 S4 测试夹具的进程退出方式 |
| s05-ast | 语句层与正则兜底 | 首轮 + 返工 1 轮 | dd472f9 | 七处判错：把括号当子查询、命名窗口、IGNORE NULLS、写语句里的相关子查询、赋值记成比较、同名遮蔽、兜底的两处误报 |
| s05-dynamic | 计划层、数据层、组合入口、命令行、语料报告 | 首轮 + 返工 1 轮 | 42e1856 | `extract_isolated` 吞掉调用方错误；基表引用带上了采样或连接子句；超上限的集合运算输入被当成没有特征 |

三个包首轮都通过了自己的全部门槛，问题都是编排者读代码加探测找出来的。没有推翻包，没有第 2 轮返工。grok 成本合计约 5.9 美元（vocab 1.16、ast 2.43、dynamic 2.34）。说明、报告、审查包、返工意见归档在 `docs/orch/s05/`。

### 当前接口

`surprise.features` 导出（S6 起直接用）：

- `default_registry()`、`Registry`（`known`、`get`、`ids`、`layer`、`parent`、`ancestors`、`children`、`siblings`、`closure`、`register`、`accept`、`digest`、`save`、`Registry.load`）、`FeatureDef`。
- `Phi`、`make_phi(engine, features, layers, registry=None)`。
- `check_spec(phi, spec, registry=None) -> SpecCheck(ok, engine_ok, missing, forbidden, undetermined)`；`spec` 是 `surprise.theory.contracts.Spec`。
- `unit_parts(phi) -> (主构造, 计划算子类, 数据性质类)`、`unit_of(phi, oracle)`。
- `extract_ast(sql, engine, registry=None) -> (frozenset, "ok" | "fallback")`。
- `extract(case, *, layers=("ast", "plan", "data"), runner_factory=None, registry=None) -> Phi`：φ 描述的语句是 `full_query(case)`。
- `extract_isolated(case, *, layers=..., timeout_s=None, registry_path=None) -> Phi`：调用方的错误（读不了的词表文件、没有 runner 的引擎要算 `plan` 或 `data`）照样抛出。
- 常数在 `features/limits.py`：`MAX_TABLE_ROWS = 10000`、`PROBE_TIMEOUT_S = 10.0`、`ISOLATION_TIMEOUT_S = 60.0`。它们不在 manifest 的冻结常数里；S6 把理论常数写进 manifest 时决定要不要一并记。

成本（主检出区实测）：进程内 `extract` 三层约 15 毫秒一次；`extract_isolated` 约 0.3 秒一次；整份语料 1092 条的报告约 11 秒。

### PI 已自行核查并定下的选择（用户可以推翻）

1. **数据性质不用聚合 SQL 算，取回行在 Python 里数**，每张表上限 10000 行，超过就整层 `unavailable`。理由：被测引擎的缺陷可能把用来验证的聚合也算错。代价：大表上的语句没有数据层。
2. **看不全就不描述**：集合运算的某个输入超过上限、某张表的引用生成不了，数据层整层 `unavailable`，而不是少报几个特征。唯一的例外是输入单独跑不起来（引用了外层的列）：不输出它的特征，层仍是 `ok`。这时 φ 里没有 `data:setop:*` 不等于"没有重复行"。
3. **φ 默认在调用方进程里提取**（只跑 EXPLAIN、取表、集合运算的输入，不执行被测语句），`extract_isolated` 留给不放心的场合。已知会杀进程的 F10 语句取计划是安全的。
4. **语句层的反例进门槛**：`gates/s05_cases.py` 在派发后追加了 14 条 `AST_PROBES`、3 条 `FALLBACK_LACK`（52e6030）。这是在本会话自己的门槛上加严，不是改旧门槛。
5. **单元的三维取值表与优先级**（主构造 dml > set_op_all > set_op > window > …；计划算子类按算子名子串；数据性质类 dups > nulls > empty > extreme > plain）是编排者定的粗粒度，对应 PLAN 决策 4"先粗"。语料上 1092 条落在 76 个单元。S8 发现太粗或太细时改 `units.py` 一个文件。

### 与计划的偏差

- SESSIONS 写的是"先契约一包，再两包并行"，实际三包串行：`s05-ast` 与 `s05-dynamic` 都要改 `features/__init__.py`，后者还依赖前者的 `extract_ast`。
- 没有改 `theory/contracts.py`：S2 定的 `Spec` 已经够用，规格核对器直接用它。
- `coverage/features.py` 只作参考，没有 import（旧代码不动）。

## 最近完成会话：S4（2026-10-09）

Claude Code 担任编排者，全部实现来自 grok 工作包。会话分支 `session/s04` 从 `s03-done`（499291b）建立；起点独立复跑 242 passed, 3 skipped 与 GATES PASS 3/3。两包全部合并，harness 已冻结，收尾合并回 main，tag `s04-done`；S5 从此 tag 起。

用户在会话中追加的指示（2026-10-09）：S4 完成后编排者自行开始 S5；需要确认的事项一律按编排者的推荐确认，逐项记入 DECISIONS。接手的会话沿用这条指示，不等答复，直接按 SESSIONS 的 S5 一节开工。

### 交付与门槛

- 第 1 档：新进程执行器 `execute_isolated`（ok / error / timeout / crash 四种状态，子进程崩溃或挂起不影响调用方）；每个差异候选先查三条前提、再做 5 次新进程重跑加 1 次单线程重跑，不稳定、依赖未指定语义、结果不可比、写语句的非崩溃候选都降为 invalid。
- 第 2 档：归属测试接口，用手写假设调通。有干预名的假设做一次"关掉 fix set 后差异是否消失"的测试；没有干预名的比较失败类别、错误类别与行为画像的形状。身份不一致升第 3 档。理论 T 没有做。
- 第 3 档：最小化（旧 `BugFixer._minimize` 加一遍删无用 setup 语句）与完整画像（旧 `compute_fix_set`、`plan_diff_ops`，版本梯走 S3 的旧版子进程）。最小化后不复现或违反前提降为 invalid。
- `Label.cve` 记五步的执行或跳过原因及证据；最终标签经 `evaluate_final` 入账，pass、invalid 同样记录。
- harness 与常数冻结，清单与哈希校验见"冻结"一节；manifest 环境补了旧版引擎、PostgreSQL 参照、间接依赖。

最终在 `framework/` 下、两包合并并冻结之后的主检出区独立运行：

| 命令 | 结果 |
|---|---|
| `../.venv/Scripts/python.exe -m pytest -q testing tests` | 275 passed, 3 skipped，退出码 0（起点 242，新增 33，skip 未增加） |
| `../.venv/Scripts/python.exe -m surprise.gates.all` | S01 7/7、S02 5/5、S03 5/5、S04 9/9；GATES: PASS (4/4 passed)，退出码 0 |

`gates/s04.py` 九组与 SESSIONS.md S4 门槛的对应：

- `m1`：经 `evaluate_final` 写入 50 条最终标签（14 fail、20 invalid、16 pass）。confirmed 族 fail 且身份证据正确：F1、重建的 F6（含经 TLP 的带谓词形态）落在 `deliminator, filter_pushdown`；F2 及其 `.sql` 写法 `window_self_join`；F7 及其 `.sql` 写法 `common_subexpressions, expression_rewriter`；F9 fix set 为空、身份是见证开关 `window_combine`；F11 是 crash，`InternalException`，fix set `build_side_probe_side`；DF-A、DF-B、DF-D、DF-F 为 Cross fail（三个以上独立引擎、目标唯一异类），DF-I 为 crash。四个有 fix set 的 recall 条目（F1、F2、F7、F9）与 `docs/recall_repros.json` 一致。未指定语义的 F3（前提）、F8（重跑）判 invalid；F5 只允许 pass 或 `unstable_rerun`；普通查询与两份不复现的 `.sql` 变体判 pass；值依赖错误、无序结果、不等价改写、DATE 假候选、写语句判 invalid。
- `tier1`：六个稳定族经 5 次新进程重跑仍为 fail；F8 `unstable_rerun`；F5 最多试 10 次，出现 `unstable_rerun` 即止，任何一次 fail 都算不过；六种可编排的重跑日程（全复现、单线程不复现后追加 15 次、追加中漏一次、只复现一两次、行序颠倒仍稳定）。
- `premise`：ASOF 并列（含审查中发现的"ON 里带只涉及右表的条件"）、写语句、跨库值类别不可比为 invalid；无并列、写语句的 crash、可比的跨库差异保持 fail。
- `isolation`：四种状态分得清；`duckdb/F10_window_frame_underflow.sql` 的两条致命语句在子进程里以退出码 0xC0000094 结束、调用方无恙；一个候选至少七个不同进程；会杀进程、会挂起的假 runner 与会崩的参照引擎都被收住。
- `tier2`、`tier3`：归属一致与不一致各两种方式；九个确认用例的 fix set、版本梯、最小化结果是原 setup 的子序列；无关的表被删掉；最小化途中丢失的候选降级；第 1 档被拒后的跳过原因如实记录。
- `contracts`、`environment`、`freeze`：取值表与常数、原始入口仍返回 `cve == {}`、非法请求在执行前被拒；manifest 环境字段与"harness import 的旧模块都在哈希范围内"；冻结清单与工作树一致。

门槛期望全部在派发前实测；审查中发现的两类问题先实测再加进门槛（ASOF 反例、跳过原因）。没有按族号或 SQL 文本硬编码的判定。

### 已知的召回缺口（门槛如实记录，不要求 fail）

| 族 | 最终标签 | 原因 |
|---|---|---|
| F10（四条语句） | invalid / nondeterministic | 旧确定性筛查把显式帧子句当排序键，执行之前就筛掉；两条致命语句只用来直接验证执行器 |
| F5 | invalid / unstable_rerun（偶尔原始判定就是 pass） | 并行竞态；新进程里复现率约 6–11% |
| DF-E、DF-J | invalid / query_error | 引擎拒绝合法 SQL，按标签规则"查询报错"归 invalid |
| DF-H | invalid / query_error | panic 文本不在旧 `is_internal_error` 的标记里 |
| DF-G | pass | 旧宽松归一化把 DECIMAL 舍入成浮点，看不出精度丢失 |

让它们判 fail 都要改旧判定代码，与"判定代码只搬不改"冲突。

### 拆包清单与结论（全部已合并）

| 包号 | 目标 | 允许路径 | 依赖 | 门槛组 | 结论 |
|---|---|---|---|---|---|
| s04-tier1 | 新进程执行器、第 1 档、`certify` 与 `evaluate_final`、`Label.cve` 结构、新 invalid 来源与常数、manifest 环境字段 | harness/cve/**、harness/evaluate.py、contracts.py、constants.py、manifest.py；tests/test_surprise_s04_*.py 与三个定向更新的旧测试 | s03-done | contracts isolation tier1 premise environment | 合并 7b12a85；返工 1 轮（ASOF 并列键漏判、退出码 0 无结果应为 crash、`unattributed_crash` 的 tier）。独立 264 passed / 3 skipped；25 条 shell 命令已审查；约 4.08 美元 |
| s04-tier23 | 第 2 档接口、第 3 档最小化与画像、降级规则 | harness/cve/**、harness/evaluate.py、constants.py、manifest.py；tests/test_surprise_s04_*.py | s04-tier1 | tier2 tier3 m1（连同前五组） | 合并 1ae6e61；返工 1 轮（放行漏放的常数快照断言、第 1 档被拒后的跳过原因、干预名单缓存、最小化后用原始判定再验证）。独立 275 passed / 3 skipped；23 条 shell 命令已审查；约 4.19 美元 |
| （编排者） | 冻结清单 | gates/ | 两包都已合并 | freeze | 已做 |

表内 harness、tests 路径相对 `framework/surprise/`、`framework/`。两包的 brief、报告、审查结论、返工意见归档在 `framework/surprise/docs/orch/s04/`。没有推翻包，没有第 3 轮返工。

### 当前接口（已冻结）

入口边界：`judge`、`evaluate` 是原始 oracle 层，返回未经 CVE 的标签，`cve == {}`，S2/S3 的门槛与测试照旧验证它们。最终标签走 `surprise.harness.cve.certify`，入账走 `surprise.harness.evaluate.evaluate_final`。S8 的主循环用后者。

- `certify(case, oracle, *, hypothesis=None, diagnose=False, isolation="process", runner_factory=None, timeout_s=10.0, wall_timeout_s=None, rewrite_rule=None, paired_query=None, old_python=None, reference_factories=None) -> Label`。`evaluate_final` 在 `evaluate` 的参数之外多 `hypothesis`、`diagnose`、`isolation`、`wall_timeout_s`，每调用一次恰好写一条记录；流水线自身抛异常记 `invalid / harness_error`。
- `isolation="process"`（默认）：调用方进程不执行任何目标 SQL；传入的工厂必须是子进程能按模块名导入的模块级可调用对象，否则在执行前抛 `ValueError`。`"inline"`：全部在调用方进程里做、每次判定新建 runner，给测试用的闭包工厂用。
- `execute_isolated(case, *, prelude=(), timeout_s, wall_timeout_s, runner_factory) -> IsolatedResult(status, rows, error, exit_code)`。S5 可以用它在隔离进程里跑 EXPLAIN 与数据性质查询（把语句放进 `SqlCase.query`）。
- `Label.cve`：`schema`（1）、`tier`（0 不是候选；1 做了第 1 档；2 归属一致；3 做了最小化）、`isolation`、`raw`（原始判定及其身份）、五步 `rerun / premise / attribution / minimize / profile`。每步有 `status`；跳过时 `reason` 取 `not_a_candidate`、`not_requested`、`premise_violated`、`tier1_rejected`、`attributed`、`unattributed_crash`、`not_reproduced_minimized`、`timeout`、`crash`、`harness_error` 或被违反的前提名。
  - `rerun`：`attempts`（5 或 20）、`reproduced`、`stable`、`extended`、`distinct_outcomes`、`single_thread: {ran, reproduced}`。
  - `premise`：`violations`、`checks`。
  - `attribution`：`hypothesis_id`、`method`（`fix_set` / `profile`）、`consistent`、`executions`。
  - `minimize`：`reproduced`、`setup_before`、`setup_after`、`case`、`executions`。
  - `profile`：`fix_kind`、`fix_set`、`plan_diff`、`version_ladder`（`longstanding` / `recent` / `unknown` / `unavailable`）、`error_class`、`behavior_shape`、`witness_switches`、`executions`。
- 身份证据：第 3 档之后 `identity.switches` 取 fix set，fix set 为空时保留原始见证开关；`error_class`、`behavior` 不变。被 CVE 降级为 invalid 的标签身份为空，原始判定留在 `cve.raw`。同一稳定输入两次判定的 `to_dict()` 相等（`cve` 里没有进程号、耗时、路径）。
- 假设（第 2 档）是 mapping：`hypothesis_id`、`engine`、`interventions`（干预名列表，可空），无开关时另给 `fail_kind`、`error_class`、`behavior_shape` 中的若干个；其余键忽略，所以 `theory.contracts.Hypothesis.to_dict()` 补上这几个键就能直接传。校验在原始判定之前，非法即 `ValueError`。`behavior_shape(behavior)` 返回 `missing_only` / `extra_only` / `both` / `none`。
- `INVALID_REASONS` 十七项，S4 新增 `unstable_rerun`、`unspecified_semantics`、`side_effecting_statement`、`incomparable_results`、`unattributed_crash`、`not_reproduced_minimized`。
- 复现判据（第 2、3 档共用）：plan variant 比较"prelude 之后"与"再打开见证开关"两种形式，两边成功且 bag 相同、或以相同错误类别失败算一致；其他 oracle 在 prelude 之下重做原始判定，仍 fail 算复现。最小化结束后另做一次不带 prelude 的原始判定，fail 且失败类别不变才算复现。

### 冻结

- 清单：`framework/surprise/gates/s04_frozen.json`，由 `python -m surprise.harness.manifest write` 在两包合并后生成。51 个文件（harness 31 个、旧依赖 20 个），哈希 `50fa40cf2d1988e8718369487b42be2c1da1a76964c0c520af51ce919b8d5fd9`。
- 常数八项：`QUERY_TIMEOUT_S = 10.0`、`CVE_RERUN_ATTEMPTS = 5`、`CVE_RERUN_EXTENDED = 15`、`CVE_WALL_TIMEOUT_S = 120.0`、`CVE_ATTRIBUTION_WALL_TIMEOUT_S = 120.0`、`CVE_PROFILE_WALL_TIMEOUT_S = 600.0`、`CVE_MINIMIZE_MAX_EXECUTIONS = 30`、`CVE_BISECT_MAX_EXECUTIONS = 120`。
- 环境（清单里的快照）：Python 3.13.9；DuckDB 1.5.5 / 旧 1.1.3；DataFusion 54.0.0 / 旧 50.0.0；SQLite 3.51.0；PostgreSQL 参照 16.15；pyarrow 21.0.0、psycopg2-binary 2.9.13；sqlglot 未安装（记 None，名单里留了位置）。
- 校验：在 `framework/` 下 `../.venv/Scripts/python.exe -m surprise.harness.manifest verify surprise/gates/s04_frozen.json`，退出码 0 表示未变；`gates/s04.py` 的 `freeze` 组每次都查清单、哈希与常数。
- 冻结之后 `framework/surprise/harness/` 与被哈希的二十个旧模块有任何改动，S04 门槛变红。要改先问用户；改完重新生成清单并在 DECISIONS 记一笔。派发脚本见到 `s04-done` 会自动把 `harness/` 列入执行者禁区。
- 后续层要往 run manifest 里加自己的内容（如 φ 词表版本、LLM 模型号），在传给 `Ledger.start_run` 的 dict 上加键即可，不需要改 `manifest.py`。

### 成本（主检出区实测，每次调用）

| 情形 | 耗时 |
|---|---|
| 通过的用例经 `certify`（DuckDB，TLP / plan variant） | 约 0.2 秒 |
| 通过的用例经 `certify`（DataFusion，Cross，含 PostgreSQL） | 约 0.6 秒 |
| 候选做完第 1 档（原始判定加 6 个新进程） | 约 1.5 秒 |
| 第 1 档加第 2 档归属一致 | 约 1.7 秒 |
| 第 1 档加第 3 档（F1） | 约 2.7 秒；F9 的二分用满 120 次约 3.8 秒；跨库约 6 秒 |

整套 `gates/s04.py` 约 3 分半，`surprise.gates.all` 约 6 分钟。

### PI 已自行核查并定下的选择（用户可以推翻）

1. `gates/s03.py` 的旧解释器路径改为经 git 公共目录定位（f556fba）。期望值没动，主检出区仍是 5/5；起因是它在 worktree 里恒失败，执行者为此建过目录联接。
2. `datafusion/` 下 M1 表没覆盖的复现按实测定期望：DF-D、DF-F、DF-I 判 fail，DF-E、DF-H、DF-J、DF-G 记为召回缺口。
3. 重跑次数定为 5 加单线程 1 次，单线程不复现再加 15 次；复现按每条语句的结果 bag 比较。
4. 跨库可比性按"同一列上值类别互斥"判，不改旧 normalizer；对 DuckDB 目标同样生效。
5. 冻结前没有处理每次原始判定起一个进程的开销，也没有并行重跑；留到 S8 实测吞吐后再定，动它要解冻。

### 与计划的偏差

没有与 PLAN 冲突，没有做理论 T、Hunter、LLM 角色。相对 SESSIONS 的字面要求有三处出入，都已记入 DECISIONS：F10、F5 不判 fail（S2 验收时已定）；`datafusion/` 下四个复现记为召回缺口；拆成两个串行包而不是一个包。操作上的偏差：执行者首轮建过一个指向主检出区 `.venvs` 的目录联接并删过一个自己的临时文件，联接由编排者在清理前单独移除；编排者两次在说明里漏放常数快照断言所在的测试文件。

## 最近完成会话：S3（2026-10-09）

Codex 担任编排者，全部实现来自 grok 工作包。会话分支 `session/s03` 从 `s02-done-r2`（caec153）建立；起点独立复跑 149 passed, 3 skipped 与 GATES PASS 2/2。四包全部合并，最终独立集成通过。收尾合并回 main，tag `s03-done`；S4 从此 tag 起。下方保留 S2 的历史接口与 M1 逐族期望，当前接口以本节为准。

### 交付与门槛

- 七类 `tlp/norec/plan_variant/index_presence/equivalent_query/version_differential/cross_dbms` 统一注册分发；DuckDB 与 DataFusion 都可调用 `judge`、`evaluate`。DataFusion 的 Index presence 是 `invalid / not_applicable`。标签仍只有 pass/fail/invalid，全部 `cve={}`，S4 才接 CVE。
- Index presence 比较 DuckDB ART 索引有/无的结果；Equivalent query 只使用三条附等价性论证的机械规则 `double_negation`、`demorgan`、`case_to_coalesce`。NULL、重复行、BETWEEN/CASE 内部 AND、引用字符串与不可信 pair 均有反例。
- Cross 复用旧 `classify_divergence`，至少三个独立成功引擎、目标唯一异类才 fail。DF-A/DF-B 以 DuckDB 与 PostgreSQL 作参照；SQLite 3.51.0 不支持两个 ALL 语句，报错不能投票。DF-B 正确 bag 包含 NULL，旧 SQL 注释不改。
- Version 比较 DuckDB 1.1.3/1.5.5、DataFusion 50.0.0/54.0.0；仅独立多数支持旧结果或前四类在新版上独立见证 fail，才判回归。F2 两条方向证据支路均已实测；无参照的 SELECT version() 只判 `invalid / direction_unknown`。

最终在 `framework/` 下、四包合并后的主检出区（94b602c）独立运行：

| 命令 | 结果 |
|---|---|
| `../.venv/Scripts/python.exe -m pytest -q testing tests` | 242 passed, 3 skipped，退出码 0 |
| `../.venv/Scripts/python.exe -m surprise.gates.all` | S01 7/7、S02 5/5、S03 5/5；GATES: PASS (3/3 passed)，退出码 0 |

S3 五组 `registry/local/cross/version/matrix` 全通过。matrix 实际写入七类 × 两引擎共 14 条账本记录，并检查无隐藏 harness_error、DataFusion 索引不适用、标签稳定、manifest 校验。派发前期望来自本机实测；审查反例也先实测再加门槛，没有降低法定数或把版本当独立引擎。

### 拆包清单与结论（全部已合并）

| 包号 | 目标 | 允许路径 | 依赖 | 门槛组 | 结论 |
|---|---|---|---|---|---|
| s03-registry | 注册分发、两引擎映射、S2 三类接 DataFusion、options、invalid 来源与 manifest 范围 | harness/oracles/__init__.py、registry.py、sound.py；harness/evaluate.py、contracts.py、manifest.py；tests/test_surprise_oracles.py、test_surprise_evaluate.py、test_surprise_contracts.py、test_surprise_s03_registry.py | s02-done-r2 | registry | 合并1cae8cd；返工1轮，仅修新增测试的长期有效性。独立165 passed/3 skipped；15条shell命令已审查 |
| s03-local | ART Index presence、确定性改写规则 | harness/oracles/index_presence.py、equivalent_query.py、rewrites.py；tests/test_surprise_s03_local.py | registry | local | 合并0293ace；返工2轮（De Morgan/pair前提、E字符串边界）。独立186 passed/3 skipped；30条shell命令已审查 |
| s03-cross | PG16参照 runner、法定数及唯一异类 | harness/oracles/cross_dbms.py、pg_reference.py；tests/test_surprise_s03_cross.py | registry、PG就绪 | cross | 合并a60a287；返工2轮（多语句/事务边界、WITH SELECT INTO）。独立188 passed/3 skipped；29条shell命令已审查 |
| s03-version | 两引擎新旧子进程、回归方向证据 | harness/oracles/version_differential.py、version_worker.py；tests/test_surprise_s03_version.py | registry、cross | version | 合并7454d8d；返工1轮（类型兼容、证据稳定、协议/错误标签）。独立221 passed/3 skipped；34条shell命令已审查 |

表内 harness、tests 路径相对 `framework/surprise/`、`framework/`。公共文件仅 registry 改；local/cross 并行，cross 合并后派 version，同时最多两包。每包合并即提交 HANDOFF 状态。四包 brief、报告、最新独立审查结论、各轮返工意见已归档 `framework/surprise/docs/orch/s03/`，总花费约 8.93 美元。没有推翻包，没有超过两轮返工。

### 当前接口与证据

- `judge(case, oracle, *, runner_factory, timeout_s, rewrite_rule, paired_query, old_python, reference_factories)`；`evaluate` 同样支持这四个新增 options，仍每次写一条账本记录。
- `register(id, handler)`、`get_handler(id)`、`runner_factory_for(engine)` 在 `harness/oracles/registry.py`。模块末尾自行注册，公共入口懒导入。handler 签名 `judge_case(case, *, factory, timeout_s, options)`。
- `OracleOptions` 为冻结 dataclass：`rewrite_rule/paired_query/old_python/reference_factories`。old_python 是字符串路径；参照 None 使用默认集合，空 dict 明确无参照。只接受独立 ID duckdb/datafusion/sqlite/postgres，拒绝目标和版本别名；PG/SQLite 只作参照。
- `INVALID_REASONS` 共十一项；本次追加 `untrusted_rewrite/direction_unknown/insufficient_engines/non_unique_outlier`，没有第四个标签。S4 冻结前可继续登记 CVE 的 invalid 来源。
- Version detail 保存 `old_version/new_version/old_rows/new_rows/direction/direction_evidence`；行证据按 bag 规范排序，保留重复、NULL、类型。独立 sound 见证保存完整 `Label.to_dict()`，包含 SQL、身份与 detail。
- manifest 覆盖 39 个文件（新 harness 21 个、旧依赖18个），哈希 `59255df29e81050de12488862127e21c18762c2f1a5acc8edf2d28f377bae33e`。旧实现与 PLAN/SESSIONS/ORCHESTRATION/CLAUDE/AGENTS/tools/orch/.grok 零改动。当前未统一记录的环境版本见下面未决问题。

### PostgreSQL 与旧版环境的恢复

本机参照为 EDB PostgreSQL 16.15 Windows x64，免安装二进制与数据在不入库的 `.orch/pg16/`，无系统服务、无全局 PATH 修改；下载源及 SHA256 记在 DECISIONS。仅监听 127.0.0.1:55432，用户 coevo、数据库 postgres、本机 trust。

先查状态（仓库根）：

`.orch/pg16/binaries/pgsql/bin/pg_ctl.exe -D D:/CoevoDB/.orch/pg16/data status`

仅服务器未运行时启动，已有数据不得重新 initdb：

`.orch/pg16/binaries/pgsql/bin/pg_ctl.exe -D D:/CoevoDB/.orch/pg16/data -l D:/CoevoDB/.orch/pg16/server.log -o "-h 127.0.0.1 -p 55432" -w start`

参照默认 DSN 为 `host=127.0.0.1 port=55432 user=coevo dbname=postgres connect_timeout=5`，`COEVO_REFERENCE_PG_DSN` 可覆盖。每 runner 用独立未提交 schema/事务，close 回滚；最终人工核查遗留 schema 数为 0。

旧解释器默认从 git 公共目录定位 `.venvs/duckdb-1.1.3`、`.venvs/datafusion-50.0.0`，按平台找 Scripts/python.exe 或 bin/python，`COEVO_VENVS` 可覆盖。version_worker 经文件路径和 `-I` 启动，空临时工作目录；旧 DF 只直接导入 datafusion 与标准库，原始 typed JSON 回主进程再归一化。独立核查旧 DF 环境仍无 duckdb/psycopg2，没有安装依赖或使用旧代码写死的 bin/python。

### PI 已自行核查并定下的选择

1. PG 只作参照，直接 psycopg2 包装事务隔离；查询限单条只读，setup 事务控制在执行前拒绝，不让参照 schema 被误提交。
2. 改写仅上述三条证明规则；外部 pair 只容许关键词大小写、外部空格、单尾分号等一致写法，字面量/引用标识符/评论文本变化拒绝。U& 形态保守不适用，不扩大规则覆盖。
3. Index 门槛不强迫小表计划选索引。另用2万行人工核查确实出现 ART Index Scan，结果仍 pass；测试的是索引存在/不存在的结果等价。
4. Version 旧 DF 原始类型在主进程调用既有 `targets.datafusion_runner._norm` 后共享 normalize，与同一目标 runner 兼容；不从字符串猜日期。DATE/bytes/Decimal 的真实端到端标签都 pass。双方成功同一错误 bag 仍 pass，双方 SQL 错误 invalid；非零退出、缺实际版本号、垃圾 JSON/损坏 typed cell invalid/harness_error。只精确跳过不存在的可选 index 模块，其它依赖异常传播。
5. 继承自旧 Cross 的 DATE 格式假候选按范围纪律留 S4 前提检查，详细反例在下面未决问题；S3 raw fail 不等于确认 bug。

### 与计划的偏差

没有与 PLAN 冲突，没有接 CVE、LLM 改写或理论层。为满足用户点出的前提，拆出 registry 公共包并把 S2 三类接到 DataFusion；增加 PG16 参照 runner 和新的旧版 JSON 子进程入口。规则选三条可证明的机械规则，未实现 SESSIONS 举例的全部种类。门槛在独立审查中补了实际反例，既有旧逻辑未改。

操作偏差也已记录 DECISIONS：registry 首次合并的署名环境变量被嵌套 PowerShell 展开，保留历史不重写；后续使用 PI 的 `.orch/scratch/s3_gw.py` 设置尾注。version 首轮 tmp 递归删除被 deny，核查目录一直保留，后续没有重试删除；最终仅按用户授权由 gw 清理已合并的整个 worktree。PI local 门槛一处漏导入已自行修正，未算执行者返工。

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

### 未决问题（S8 及之后需要知道的）

S7 发现、留后续会话：
- 误吸收仍在（规则没有改）：没有 fix set 的假设按失败类别、错误类别、行为形状认正例，所以 (a) 一条已经被归属测试判给有 fix set 的假设的失败，只要落在某个无开关假设的确认区或待定区且三项相同，也会被它当成正例，把它的 S 泛化掉；(b) 作用域里通过还少、G 还松的时候，形状相同的另一种缺陷会被吸收进来而不是开新家族（实机例子：DF-F 进了 DF-D 的假设）。数字见 S7 一节"实机回放的数字"。可选的修法是在 `Theory._update_hypotheses` 里加一条"归属测试已经判给别的假设的失败，不再算其他假设的正例"，它改的是 S6 的规则，先问用户。MDL 的拆分只在"簇与簇之间"落了足够多的通过时才会把并错的假设拆开（三十五条以上）。
- 没有开关的身份太粗的另一面：`DF-D_where`（只少行）与 DF-D（少行多行都有）是同一个缺陷，却因为形状不同分成两个家族。这是与人工账本唯一的出入。要更细或更稳的行为画像得在理论层另算，或解冻 harness。
- 回滚会给"被回滚的编辑之后才开出的家族"换编号（计数器不回退、重放时重新铸号）。账本里指向旧编号的第 2 档归属结果，对有 fix set 的假设就读不出来了（记为身份未知，不学）；没有 fix set 的假设靠标签自己的三项，不受影响。要保住就得让重放时"同一条记录开出的家族沿用原编号"，需要给 `Theory.observe` 加一个指定编号的入口。
- 工作台把观察日志全部留在内存里（每条的 φ 与去掉 detail 的标签），`journal.jsonl` 只增不减，一条观察约 1–1.5 KB。S8 的长 run 之前先量；接受检验每次要扫编辑所在作用域的全部记录（上限 1000 条留出记录是对预测次数的上限，不是对扫描的上限）。
- `Theory.to_dict()` 每次都带上全部记住的通过，所以 `Theory.version`、`store.save`、每次接受检验前后的状态比较都与通过的条数成正比：实测 1 万条通过时 `version` 一次约 47 毫秒，`save` 一次约 157 毫秒。S8 每条实验都要算一次版本号、存一次盘。需要的话把通过改成追加写、版本号改成增量哈希，属于理论层，不涉及冻结区。
- 存储没有崩溃恢复：`save` 先写各文件、最后写 `head.json`，中途被杀的话下次 `load()` 会因为版本号对不上而拒绝（不会读到半截状态），但要人工处理。可以从最近一代的快照加日志重放恢复，没有做。
- 押注"落在新 S 里的实验会失败"只兑付一次：兑现之后，这条编辑的 S 里再出现多少条通过都只是矛盾（4.32 比特一条），要等 MDL 的修复候选攒够了才动。确认区的 0.95 对这类假设是偏高的（实机例子：F2 的假设，落在 S 里的 9 次实验有 4 次通过）。校准留给 S11 的 Brier 分数；要不要让确认区的概率随矛盾数下调，属于改 S6 的常数与规则，先问用户。
- `contradictions` 里既有落在 S 内的通过，也有落在 S 内、身份不一致的失败（S6 的规则如此）。MDL 的修复只看前者。读这个字段做统计时要自己按标签分开。
- 同作用域、同身份、由规则各自开出的两个家族，几乎不可能被 MDL 合并：第二个是因为落在第一个的 G 之外才开出来的，而"在 G 之外"就意味着把两者的 S 并起来会盖住某条已知的通过。合并实际能发生的场合是：缺某一层 φ 而没被吸收的失败、编辑造出来的假设、G 被截断之后。实机回放里两对候选（DF-A 与 DF-D_where 的假设，DF-D 与 DF-F 的假设）都被留出记录拒掉。
- `add`（凭空加一个假设）的候选正例取"同作用域里身份一致且落在 S 内的全部失败"，包括已经属于别的假设的；这些记录之后归谁，按"归属测试点名的优先，否则最早的假设"定。S9 的猜想者如果常用 `add` 而不是改写规则开出的家族，会出现同一批失败挂在两个假设下。
- 预测时"负责的假设"取待定区里最早的那个（S6）。实机回放里有两次因此先对一个不相干的假设做了归属测试、不一致、白做了一次第 3 档画像（约 2.5 秒），之后才被真正的家族吸收。S8 的主循环可以在待定区有多个假设时挑身份更可能一致的那个去问。
- 门槛的 `replay` 与 `ledger` 两组约 5 分钟，`surprise.gates.all` 现在约 11 分钟。期望值是在 DuckDB 1.5.5 / 1.1.3、DataFusion 54.0.0 / 50.0.0、PostgreSQL 16.15 上测的；`gates/s07_cases.py` 的裁定语句表每条都要求在本机判 fail，换引擎版本要同步改，改之前问用户。
- `verify_theory_manifest` 对常数的 `added` / `missing` 措辞方向（S6 留的）没有动：本会话没有改 `manifest.py`。
- PLAN 第 7 节的"31 个家族里能用合取表达的比例"只量了本机能回放的十族。

S6 发现、留后续会话：
- `evaluate_final`（已冻结）写账本时 `surprise` 字段恒为 `None`，也没有参数可传。现在的约定是 `p_t` 传 `prediction.p_fail_valid`，惊讶由 `surprise_bits(record.p_t, record.label.y)` 从账本重算（门槛的 `walkthrough` 组核对过）。S8 的主循环和 S11 的指标都按这个算；要把惊讶直接存进记录就得解冻 harness，先问用户。
- 作用域按 oracle 分的后果：同一个缺陷经两个 oracle 暴露会开两个假设，各自的 S、G 分别学。S7 做 MDL 合并与家族计数时，按身份（I，或三项画像）跨 oracle 归并；与人工账本比家族划分时也要先归并。
- 没有开关的假设身份很粗（失败类别、错误类别、少行 / 多行 / 都有）：DataFusion 上两个机制不同而形状相同的缺陷，只要 φ 落在对方的 G 里就会被当成正例吸收，把对方的 S 泛化掉。见证开关没有放进身份（它随哪个变体先见证而变，没有实测）。S7 回放人工账本时量一下这种误吸收有多少。
- `Theory` 把每个作用域里见过的通过（去重后的 φ）全留在内存里，建新家族时逐条回放，没有上限。S7 做存储时接管；S8 的长 run 之前先量内存与建族耗时。
- G 的初值是空合取：一个作用域里刚开出第一个家族、而此前见过的通过还少时，这个作用域里几乎处处是待定区（每次 1 比特），要靠后续的通过把 G 收紧。S8 的 Hunter 会看到 D 项在整个作用域里都接近 1 比特，这是预期的；惊讶曲线在新家族之后会有一段抬高。
- 建族时只回放通过，不回放别的家族此前的失败；那些失败再次出现时才作为反例作用到新假设上。
- 新家族的 S 取被执行语句的 φ，不取最小化之后的用例。`label.cve["minimize"]["case"]` 里有最小化的用例，S7 / S8 可以对它另行 `extract` 再建族（`new_family` 的 `phi` 参数就是为此留的；注意 S 必须覆盖触发它的那条失败，否则这条失败自己落在确认区之外）。
- `contradictions`（确认区里的通过）现在只记录，不收紧、不拆分。它是文档里"复核后收紧或拆分；解释不了就由 LLM 发明新特征"的入口，属 S7（MDL）与 S10（词汇发明者）。实机例子：手写的"EXCEPT ALL 且左侧有重复"遇到左右重复数相同的输入就通过，现有词表表达不了"左侧重复数多于右侧"。
- G 超过 64 个成员时被截断（`truncated`），待定区因此被低估。随机测试里 G 最大到 48；S8 的长 run 里统计一下有多少假设被截断。
- 身份一致但落在 G 之外的失败不被吸收（`effects` 里记 `outside`），有画像就另开一个身份相同的家族。合并这类家族是 S7 的事。
- 身份未知（假设有 fix set，而标签既没有对它的归属测试也没有画像）时什么都不学。S8 的主循环按 `walkthrough` 的写法给预测到的假设传 `attribution_request`，就不会落到这里。
- 分诊按大小：未探索区里 ρ 漂高的单元会出现 `boundary_move`、`duplicate`、`unexpected_pass` 而 `hypothesis_id` 为 `None`。S8 处理分诊结果时，`hypothesis_id is None` 的一律只当 R 的更新，不要去找假设。
- Kᵛ 的实验类只到"引擎加主构造"，`not_applicable` 也计入无效率（来源分开记了数）。S8 用 `1 − Kᵛ` 当 `P_valid` 时如果太粗，再细分是理论层的事，不涉及冻结区。
- `Theory` 要求 φ 的词表摘要与自己的词表一致。S10 验收新特征后词表摘要会变，旧的 φ（包括 `Theory` 记住的通过、账本里的 φ）就对不上了：S10 要定迁移办法（重新提取，或按词表版本分段）。
- PLAN 第 7 节的"31 个已确认家族里能用合取表达的比例"还没有量；S7 离线喂入已知复现时一并报告，压不了的记为样例家族。
- `registry=None` 时理论层的函数每次调用都新建默认词表；`Theory` 已经把自己的词表传下去。直接调用这些函数的代码（S8 的 Hunter）在循环里要自己传 `registry`。
- 理论状态只在内存里（`Theory.to_dict()` / `from_dict()` 是给 S7 的存储用的往返格式），按代快照、编辑日志、回滚、负记忆都还没有。
- `Theory.from_dict` 的校验只到键、版本号、词表摘要、计数与 `passes` 的写法：遇到重复的假设编号取后一个，遇到不是规范形式的假设静默规范化，不核对记住的通过里 φ 的词表摘要。`to_dict()` 自己的产物没有这些情况；S7 做存储时补上（审查时发现，没有为它返工）。
- `verify_theory_manifest` 对常数的措辞与对文件的方向相反：manifest 里有而现在没有的常数报成 `constant added`，现在有而 manifest 里没有的报成 `constant missing`；文件一侧（与冻结的 `verify_manifest` 一致）是"现在有而记录里没有"为 `added`。两种情况都报、都带名字，只是读起来别扭；S7 动这个文件时顺手对齐（审查时发现，没有为它返工）。
- `gates/s06.py` 的 `theory` 组把 R、Kᵛ、分诊在一串实验之后的状态逐项钉住了。S7 的回滚、合并如果要改"什么进 R""什么算反例"这类规则，就是改 S6 的门槛，先问用户。

S4 发现、留后续会话：
- 召回缺口：F10、F5、DF-E、DF-H、DF-J、DF-G 在新框架里不是 fail，原因见上面"已知的召回缺口"一节。评估（S11）报告召回时要把它们单列；要补上任何一个都得改旧判定代码或解冻 harness，先问用户。
- 每次 `evaluate_final` 的原始判定都起一个新进程，候选的重跑是串行的（数字见"成本"一节）。S8 跑长 run 之前先实测吞吐；需要常驻工作进程或并行重跑时要解冻 harness，先问用户。常驻进程会让 F5 这类"进程里第一次执行恒正确"的现象重新混进原始判定，并行会改变竞态缺陷的复现率，两样都要重新实测。
- ASOF 前提是保守的：USING 写法、连接键比较以外的任何 ON 条件、解析不了的右表，一律按违反处理。只会少判，不会把依赖未指定选择的用例确认成 fail。S8 生成 ASOF 用例时用 `左.列 比较 右.列` 的 ON 写法，否则全是 invalid。
- 第 1 档的重跑只比较目标引擎执行的语句结果，加上标签的判定与身份；参照引擎、旧版引擎各自的语句结果不在比较范围内。参照引擎自身不确定而判定和计数碰巧不变的情况理论上查不出来，实际需要两个独立引擎以相同方式一起变，没有见到过。
- 第 2 档的 `profile` 方式只比较失败类别、错误类别和 missing / extra 的符号组合，很粗。无开关引擎上两个机制不同但形状相同的缺陷会被判成同一身份；S6 的假设如果需要更细的行为画像，要在理论层另算（harness 已冻结），或者提出解冻。
- 复现判据对 plan variant 把"一侧成功、一侧报值依赖错误或超时"算作不一致。二分时这偏保守（不会把无关规则算成 fix）；最小化时可能把用例缩向另一种现象，由最小化后的原始判定再验证兜住（失败类别变了即 `not_reproduced_minimized`）。
- F9 的画像每次用满 120 次二分（约 3.8 秒）才得出"没有稳定 fix set"。S8 的探索会反复撞上这一族（见下面 S2 第 12 条），确认它是 F9 的便宜办法是第 2 档：给一个 `interventions` 为空、`behavior_shape` 为 `both` 的假设不够区分，建议 S6 用见证开关 `window_combine` 加错误类别建立假设，避免每次进第 3 档。
- 被哈希的旧模块有二十个，含 `agents/bug_fixer.py`（第 3 档以普通函数方式调用它的 `_minimize`，不构造 agent；`import agents.bug_fixer` 会连带导入 `httpx` 与 `llm.ledger`，只在第 3 档的子进程里发生）。S12 移动旧代码时这些路径会变：harness 的 import 与 `HASHED_PATHS` 都要改，属于解冻，先问用户，改完重新生成 `gates/s04_frozen.json`。
- `gates/s04_cases.py` 的期望值是在 DuckDB 1.5.5 / 1.1.3、DataFusion 54.0.0 / 50.0.0、PostgreSQL 16.15 上测的；`gates/s04.py` 的 isolation 组断言 F10 两条语句让子进程崩溃（Windows 上退出码 0xC0000094）。换引擎版本或换平台要同步改门槛，改之前问用户。
- 已解决：`.venv` 里装了 `sqlglot==30.21.0`（S5 开工时），manifest 的 `packages.sqlglot` 有值。换机器重建环境时要装同一版本：`ast:fn:<名>` 用的是 sqlglot 归一后的函数名，版本一变名字可能变。
- manifest 的 `packages` 是固定名单（duckdb、datafusion、pyarrow、psycopg2-binary、sqlglot）。后续层要记别的版本，在传给 `Ledger.start_run` 的 dict 上自己加键。
- `harness/manifest.py` 里的 PostgreSQL 默认 DSN 是从 `harness/oracles/pg_reference.py` 抄了一份的字符串；两处都已冻结，改端口要一起改（解冻）。
- `datafusion/` 的 DF-B SQL 注释漏了正确 bag 中的 NULL，旧文件不改，留 S12；门槛按实测包含 NULL。

S5 发现、留后续会话：
- harness 把重跑时退出码不同算作没有复现。Windows 上以 `exit()` 正常路径结束、而 DuckDB 工作线程还在跑的进程，约 0.5% 会以 0xC0000005 而不是原来的退出码结束（实测 400 次里 2 次；立即终止进程则 600 次全部一致）。所以一个靠正常退出路径死掉的真实引擎崩溃，有小概率被判成 `invalid / unstable_rerun`。方向是少判；harness 已冻结，没有改。S8 的长 run 里如果看到成批的 `unstable_rerun` 崩溃，先想到这一条。
- `Registry.load` 接受顶层是裸列表的文件（`save` 写的是 `{"invented": [...]}`），忽略条目里多余的键，空正则 `""`（对任何语句都命中）能登记。未验收的特征不会进 φ，所以现在无害；S10 定验收规则时把空正则和恒真正则挡掉。
- `framework/targets/datafusion_runner.py` 的 `_norm` 遇到浮点 NaN 或 Inf 会抛 `ValueError`，整次查询被记成出错。所以 DataFusion 上含这些值的表数据层是 `unavailable`，`data:value:non_finite` 在 DataFusion 上实际观察不到；同一个问题也会让 oracle 在这类数据上拿到执行错误。旧代码，S12 之前不改。
- 语料分布里最大的几个单元是 `…|none|unknown`：PostgreSQL 的 308 条种子这里没有 runner（只有语句层），DuckDB 的 784 条里有 252 条 setup 被 1.5.5 拒绝。S8 用种子做探索起点时，这些种子的 φ 只有语句层，单元的后两维是占位值。
- 单元的"计划算子类"按算子名子串归类，是照 DuckDB 的算子名写的；DataFusion 的 `HashJoinExec` 归到 `join`、`AggregateExec` 归到 `aggregate` 是碰巧子串对得上，`SortExec`、`WindowAggExec` 等要到 S8 接 DataFusion 探索时核对一遍。
- 发明特征的正则在每次提取时对整条语句 `re.search`，没有超时。S10 接 LLM 词汇发明者时要防灾难性回溯的正则（验收前先在语料上跑一遍并计时）。
- 语句层（`features/ast.py`）已知的小偏差，都不在被测语句的常见形态上，S8 生成探索语句时如果用到再修：`CREATE VIEW ... AS SELECT` 与 `COPY (SELECT ...) TO` 的查询被记成 `ast:subquery:scalar`；引用另一个命名窗口的命名窗口（`w2 AS (w1 ORDER BY a)`）不继承 `w1` 的规格；`INSERT ... ON CONFLICT DO UPDATE SET v = 3` 的赋值仍记成 `ast:cmp:eq`；兜底认 CTE 要求 `AS` 与括号之间有空白。
- sqlglot 把它不认识的语句（EXPLAIN、VACUUM、COPY 等）读成不透明的 Command：语句层状态是 `ok`，特征为空，不走兜底。作用域分析失败时（`ast.py` 里两处 `except Exception`）不记相关性、状态仍是 `ok`，没有任何标记；整份种子语料上没有触发过。
- `ast:fn:<名>` 用的是 sqlglot 归一后的函数名（`substr` → `substring`，`date_trunc` → `timestamp_trunc`），不是原文里写的名字。S6 之后写规格、S7 的 LLM 提假设时要用归一后的名字；sqlglot 升级可能改这些名字，manifest 的 `packages.sqlglot` 记着版本。

已解决（留作索引）：S6 留给 S7 的几件在 S7 定下并交付——理论状态的落盘、按代快照、编辑日志、回滚与负记忆；跨 oracle 的假设按 fix set 归并成家族；`contradictions` 由 MDL 的修复候选处理（收紧或拆分）；记住的通过随存储落盘（仍在内存里）；来路不明的状态由 `TheoryStore.load()` 严格拒收（`Theory.from_dict` 本身没有改）；误吸收与合取可表达的比例量过了，数字在 S7 一节。S3 记的"manifest 环境字段"与"Cross DATE 假候选"两条在 S4 解决（环境字段补齐；`incomparable_results` 前提）；S2 第 7 条（`Label.cve` 是占位）、第 11 条（没记间接依赖）在 S4 解决；S2 第 1、2 条（F10 与逐族期望）已由 `gates/s04.py` 落实。S2 第 6 条（惊讶取到无穷大要先截断）在 S6 不再需要：ρ、Kᵛ 与 0.95 / 0.5 都严格在 0 与 1 之间，惊讶恒为有限值；S5 留的"`features/limits.py` 的三个上限要不要进 manifest"在 S6 定为进（run manifest 的 `theory` 一节里的 `features.limits`）；S4 记的"F9 每次都进第 3 档"：从没有 fix set 的画像建出的假设，确认区里的重复走第 2 档的画像比较（零执行）就能确认，DF-A 上实测如此，F9 本身留给 S8 的实机 run 核对。

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
1. 要导入 `oracles.*` 或 `targets.*`，解释器里必须同时有duckdb和psycopg2。`.venvs/duckdb-1.1.3`两样都有；`.venvs/datafusion-50.0.0`两样都没有。S3保持此隔离，旧版DF子进程只直接导入datafusion与标准库，原始行JSON传回，主进程归一化；新入口version_worker.py已完成并独立验证。
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
- PLAN.md 决策表：第 5 条（φ 用 sqlglot、正则兜底）、第 4 条（单元先粗）、第 2 条（φ 一侧在 S5，版本空间一侧在 S6）已采用；第 8 条里 0.95 / 0.5 与分诊阈值在 S6 定值并由门槛钉住，β 留给 S8；第 7、9、10 条仍是建议，到对应会话开工时再定（第 6 条 S4 已采用）。

### 给下一个编排者的操作提醒

S7 踩到的：

- **参考模型用 shim 装进进程里的 `surprise.theory`（`.orch/scratch/s7/ref_shim.py`），新进程看不到它。** 跑门槛时把门槛里那几处起新进程的检查替换掉（`run_gate_ref.py`）；真实引擎的子进程只导入冻结的 harness，不受影响。
- **审查用的随机差分脚本先让参考模型自己跑一遍（`--self`）。** 这一步在派发第二个包之前查出了规格漏洞（分簇得到空的 S 会让 `compress()` 抛异常），来得及写进说明。
- **差分要放过说明没有规定的东西**（自拟的文本、浮点求和的末位），否则一轮在第一处假出入就中断，后面的路径都没比到；放过之后再看剩下的才是真出入。
- **性能问题门槛查不出来。** 审查时按下一个会话的规模（几万条）量一下每次调用的耗时：这次量出日志追加随长度线性变慢。
- **给理论层加常数之前，grep 一遍旧门槛与旧测试里对常数名单做了什么假设**（这次是"按字母序第一个是 `P_CONFIRMED`"）。
- 超长的 shell heredoc 又解析失败了两次：补丁脚本一律用 Write 工具写成文件再执行。
- 在 worktree 里跑探测之后，Bash 的工作目录会留在 worktree，环境提示也会改口说"不要 cd 回主检出区"。编排者的家是主检出区：每条命令照旧以 `cd /d/CoevoDB` 开头。
- worktree 里直接敲 `pytest` 会因为导入路径失败（pytest 把 `tests/` 放到 `sys.path` 最前），说明里写 `python -m pytest`。

S6 踩到的：

- **先写一份不入库的参考模型，再写门槛。** 规则密集的会话里，门槛的几十个期望值靠手推容易错；参考模型把门槛跑通（12/12）之后再派发，审查时拿它与执行者的实现做随机差分（十几万项比较），第一个包首轮就过了。再用穷举法核对规则本身（增量算出的 G 是否就是真正的一般边界），这一步查的是规则，不是实现。脚本在 `.orch/scratch/s6_ref/`、`s6_review_vspace.py`、`s6_review_theory.py`、`s6_bruteforce_g.py`。
- **同一条消息里并行发出的几条 Bash 命令共用一个工作目录**：其中一条 `cd` 进了 worktree，另外两条的相对路径就全错了。带 `cd` 的命令串行发，每条以 `cd /d/CoevoDB` 开头。
- PowerShell 里 `git rev-parse tag^{commit}` 的花括号会被当成脚本块；查提交用 Bash。
- 前台命令里不能 `sleep` 等后台任务；后台任务结束会有通知，等通知的时候做别的事（读 diff、跑探测、起草交接）。
- 理论层与特征层互相导入（`features/spec.py` 导入 `theory/contracts.py`）：理论层只能从特征层的子模块导入。门槛的 `constants` 组在新进程里查四种导入顺序；以后往 `theory/__init__.py` 加导出时留意。
- Python 在这台机器的控制台上打印中文是乱码，文件本身是 UTF-8，没有问题；判断结果看 ASCII 关键字或直接读文件。

S5 踩到的：

- **派发之后往门槛表里加的反例，执行者的 worktree 里没有。** 返工那一轮它跑的是旧表。审查时用一个从主检出区按路径加载门槛表、对着 worktree 的代码跑的脚本核对（`.orch/scratch/s5_gate_probe_check.py`），并在返工意见里把每条反例连同"必须有 / 不许有"原样列出来，要求逐条有测试。
- **三个包首轮都过了全部门槛，每个包的问题都是读完整实现再写探测找到的。** 探测要对着"定义"写而不是对着门槛里已有的例子写：换一种写法（带括号、命名窗口、写语句、被包装的函数）往往就错了。
- **探测脚本会过期。** 给上一个包写的静态检查（"特征包不许 import sqlglot"）到下一个包就是误报；每个包审查前先把旧脚本过一遍。
- **编排者的 Bash 工作目录会随 `cd` 漂进 worktree**，之后环境提示会把 worktree 当成主目录。每条命令都从 `cd /d/CoevoDB` 或 `Set-Location D:\CoevoDB` 开始。
- **用量上限会在会话中途打断。** 每次合并、每次派发之后都更新本文件并提交，中断时只多做一次 WIP 提交就能接上；恢复后先 `gw list` 与 `gw status <包号>`，不要重跑已完成的步骤。
- 后台的 `gw review` 约 5 分钟（S5 最后一包含语料报告，约 6 分钟）；等它的时候读 diff、跑探测，结论等复跑结果出来再下。
- `gw review` 的退出码 3 表示有红旗，不是失败；"门槛未通过"在一个会话的前几个包里是预期的（后面的组还没有实现）。

S4 踩到的：

- **说明里的验收命令必须在 worktree 里跑得通。** S4 第一包的说明要求 S03 门槛退出码 0，而当时那个门槛按 worktree 根找 `.venvs`，不可能通过；执行者于是建了一个指向主检出区的目录联接。门槛已修，但这类"环境只在主检出区有"的假设以后还会出现：派发前在一个没有 `.venvs`、没有 `.orch/pg16` 的目录里想一遍。
- **说明里写明"不建指向 worktree 之外的链接或目录联接"。** 联接留在 worktree 里，`gw cleanup` 的递归删除有连带删掉真实目录的风险。发现了先用 `cmd /c rmdir <联接>`（不带 `/s`）单独移除，核对真实目录还在，再清理。
- **改常数、改取值表的包，允许路径里要放进钉住它们的旧测试。** S4 两个包都因为 `tests/test_surprise_contracts.py` 的常数快照断言卡了一下（第一包执行者自行改了并报告，第二包停下上报）。harness 现在冻结了，这条主要对 S5 的词表、S6 的阈值适用：先 grep 一遍哪些测试对它们做了精确断言。
- **承载 `gw spawn` 的后台任务不受 10 分钟上限影响。** S4 两个包分别跑了 51 分钟和 46 分钟，后台任务都活到 grok 退出并发来通知。
- **审查时用门槛之外的独立探测。** S4 两个包首轮都通过了自己的全部门槛，问题是探测脚本找出来的（`.orch/scratch/s4_review_tier1.py`、`s4_review_tier23.py`）。探测里发现的反例先实测，再加进门槛。
- 包里有 `from .x import x` 这种把子模块名和函数名重合的写法时，`import pkg.x as m` 拿到的是函数不是模块；测试和探测里用 `sys.modules["pkg.x"]`。
- 往归档的审查结论里写内容，用脚本从文件读入再写，不要走很长的 shell heredoc：超长的 heredoc 在这里出过解析错误。

S2、S3 踩到的，仍然有效：

这几条都是本会话或上一会话实际踩到的：

- **`gw status --wait` 不要加 `--timeout`**。那个参数是"包运行超过这么多分钟就终止"，不是"最多等这么久"。本会话因此误杀了一个跑了 11 分半的包。想限制等待时间，用后台任务或命令自身的超时。
- 任务说明里写明"不要清理 `.orch/tmp`"。执行者收尾时喜欢清理临时文件，递归删除会被 deny 规则拦下，然后它会改成逐个删除，擦着"被拒绝的操作不要换写法重试"的边。
- CLAUDE.md 里的测试与门槛命令写的是 `../.venv/Scripts/python.exe`，这个路径在 worktree 里不存在。任务说明里要写明直接用 `python`。
- 往审查包里写结论时，文本里不要出现反斜杠转义（如反斜杠加 0、反斜杠加 n）：它们会被展开成真的 NUL 和换行，git 会把文件当成二进制。本会话为此补过一次提交。
- `git merge` 不能用 `-F -` 从标准输入读提交信息，要用 `-m`；合并成功并核对过之后再打 tag，两步不要连在一条命令里。
- 并行的包合并之前，各自 worktree 里的门槛都会因为缺另一个包而报"门槛未通过"，这是预期的红旗；用 `--only` 跑它自己的那几组。编排者补了门槛之后，可以用主检出区的门槛文件去跑分支上的代码来复核（本会话的做法记在 `orch/s02/s02-oracles.review.md` 的结论里）。
- 编排者自己的审查辅助脚本放在 `.orch/scratch/`（不入库）：列出执行者跑过的全部命令、种子语料差分核对、用主检出区的门槛跑别的检出。会话的临时目录中途可能失效，不要把还要用的脚本放在那里。

### 下一会话的起点：S8

**用户验收 S7 时指示开始 S8（2026-10-15）。** β 的预实验与下面列的几件要定的事由编排者按推荐定下、记进 DECISIONS；改 S6 的规则、改冻结区仍要先问用户。

- 从 main 的 `s07-done-r2` 建分支 `session/s08`。先检查主分支、tag、工作区和 PG 状态；服务器停止时按 S3 一节的恢复命令启动，不重新 initdb。
- 起点检查（在 `framework/` 下）：`../.venv/Scripts/python.exe -m pytest -q testing tests` 应为 550 passed, 3 skipped；`../.venv/Scripts/python.exe -m surprise.gates.all` 应为 `GATES: PASS (7/7 passed)`（约 11 分钟）。
- S8 做 Hunter 与无 LLM 闭环（范围见 SESSIONS.md 的 S8 一节，里程碑 M2）：四类候选、`value = P_valid × (D + β·U)`、探索保底、降权与新颖性拒绝采样；新主循环 Hunter → 执行与 CVE 标注 → 惊讶 → 分诊 → Diagnoser（无 LLM）→ 接受或回滚 → 更新 T。代码放 `framework/surprise/hunter/`、`diagnoser/` 等新目录，不碰 `harness/`。
- S7 给 S8 的现成东西：主循环里用 `Workbench` 代替裸的 `Theory`，一次实验的调用顺序见 S7 一节"当前接口"；`wb.compress()` 是无 LLM 版 Diagnoser 的 MDL 一步，隔一段调用一次即可；`wb.checkpoint(note)` 按批切代，`wb.surprise_under(代号, 记录)` 给出 CIAO 的一格；`wb.partition()` 给出每条失败的家族，重复率、家族数都从它算；`P_valid = 1 − prediction.p_invalid`，`D` 取"落在某个假设待定区时为 1 比特"（`prediction.zone == "pending"`），`U` 取 `prediction.p_fail_valid` 在未探索区的值或它的熵。细化与泛化候选从假设的 S 与 G 之差生成：删一个 S 的字面量、换成同类取值（`registry.siblings`），规格用 `Spec`，核对用 `check_spec`；变异算子复用 `evolution/dce.py` 的 `mutate_query_text`、`mutate_setup`（门槛 `gates/s07.py` 的 `dce_probes` 是现成的调用样例）与 `seeds/mutate.py`。
- S8 开工前要定的几件事（都在"未决问题"里）：β 的预实验怎么做、取值写进 `theory/constants.py`（PLAN 决策 8）；误吸收的规则要不要改（S7 发现第一条，改的是 S6 的规则，先问用户）；长 run 的吞吐——每次原始判定起一个进程（S4）、`Theory.version` 与 `store.save` 随记住的通过线性变慢（S7）、工作台把日志留在内存里（S7）——先实测再定要不要动；同种子重跑结果一致的要求意味着主循环里不能有墙钟、不能有无序集合的遍历次序泄漏。
- **理论常数十三项已由 `gates/s06.py`、`gates/s07.py` 钉住取值**，改它们先问用户。S8 的 β 照样放进 `theory/constants.py`，会自动进 `theory_manifest()`；两个门槛都只要求自己那几项在且取值不变，不拦新增的。
- 派发一律在仓库根用 `.venv/Scripts/python.exe tools/orch/grok_worker.py …`；worktree 里直接用 `python`，跑测试用 `python -m pytest`（直接敲 `pytest` 在 worktree 里会因为导入路径失败）。审查测试通过数至少 550，完整 diff、每条执行命令、分支当前 HEAD 上的独立复跑都不可省。默认两轮返工上限。
- S7 两个包都已合并并清理，`gw list` 应全部显示 cleaned。历史 brief / report / review 在 `docs/orch/s07/`；编排者的参考模型与探测脚本在 `.orch/scratch/s7/`（不入库：`ref/` 四个文件、`ref_shim.py`、`run_gate_ref.py`、`review_store.py`、`review_accept.py`、`replay_ref.py`、`explore1.py` / `explore2.py`）。恢复时看 git log、本文件和 gw list。
