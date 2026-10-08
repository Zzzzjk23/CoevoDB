# HANDOFF

## 状态总览

| 会话 | 内容 | 状态 | tag | 门槛 |
|---|---|---|---|---|
| S0 | 编排准备（派发工具） | 完成 | s00-done；s00-done-r2（CLAUDE.md 写入"执行者模式"之后） | 冒烟包 s00-smoke 四项确认全部通过（没有 gates/s00.py） |
| S1 | Phase 0 冻结基线与仓库整理 | 完成 | s01-done；s01-done-r2（验收后的修订） | `gates/s01.py` 7/7；pytest 64 passed, 3 skipped |
| S2 | Phase 1a 契约、账本、三类健全 oracle | 完成 | s02-done；s02-done-r2（验收后的修订，S3 从这里起） | `gates/s02.py` 5/5；pytest 149 passed, 3 skipped |
| S3 | Phase 1b 其余三类 oracle 与 Index presence 移植 | 完成 | s03-done | S03 5/5；pytest 242 passed, 3 skipped；GATES PASS 3/3 |
| S4 | Phase 1c CVE 流水线（M1） | 完成 | s04-done | S04 9/9；pytest 275 passed, 3 skipped；GATES PASS 4/4 |
| S5 | Phase 2 φ | 进行中（见下节） | | |
| S6 | Phase 3a 理论 T 核心 | 未开始 | | |
| S7 | Phase 3b 理论存储与接受规则 | 未开始 | | |
| S8 | Phase 4 Hunter 与无 LLM 闭环（M2） | 未开始 | | |
| S9 | Phase 5a LLM 网关、实现器、猜想者 | 未开始 | | |
| S10 | Phase 5b 其余四个 LLM 角色（M3） | 未开始 | | |
| S11 | Phase 6 评估管线（M4 冒烟） | 未开始 | | |
| S12 | Phase 7 收尾 | 未开始 | | |

以前各会话的交接全文在对应 tag 的本文件里（S0：`s00-done-r2`；S1：`s01-done-r2`）；其中仍然有效的未决问题已并入下面的清单。

## 当前会话：S5（进行中，2026-10-09 起）

Claude Code 担任编排者，实现全部来自 grok 工作包。会话分支 `session/s05` 从 `s04-done`（9d88ff7）建立。用户指示 S4 完成后直接开 S5、需要确认的事项按编排者的推荐确认；已定的事项在 DECISIONS 的 S5 条目里。`.venv` 里装了 `sqlglot==30.21.0`，装完起点检查为 275 passed, 3 skipped 与 GATES PASS 4/4。

会话在 2026-10-09 因用量上限中断过一次，同日接着做。后两个包的说明在 `.orch/briefs/s05-ast.md`、`.orch/briefs/s05-dynamic.md`（`s05-dynamic` 里的 `{基线通过数}` 要在 `s05-ast` 合并后填上）；审查探测脚本 `.orch/scratch/s5_review_ast.py`、`.orch/scratch/s5_review_dynamic.py` 已备好，`s5_review_vocab.py` 与 `s5_review_vocab_r1.py` 在每个包审查时都重跑一遍（都在 `<检出区>/framework` 下运行，末行 `BAD COUNT 0` 为通过）。

断线恢复只看三样：本节、`git log session/s05`、仓库根 `.venv/Scripts/python.exe tools/orch/grok_worker.py list`。包状态与本节不一致时以 gw list 为准，先 `gw status <包号>`。

### 拆包清单（串行，同一时间只跑一包）

| 包号 | 目标 | 允许路径 | 依赖 | 门槛组 | 状态 |
|---|---|---|---|---|---|
| s05-vocab | 词表与类层级、注册表（祖先、同类、闭包、开放族、发明特征的登记与验收记录、存取）、φ 容器、规格核对、单元投影 | features/**（不含 ast.py、plan.py、data.py、extract.py、__main__.py）；tests/test_surprise_s05_*.py | s04-done | vocab spec units | **已合并**（4b55eb1，返工 1 轮）。合并后 pytest 297 passed / 3 skipped，S01–S04 通过，S05 的 `vocab spec units` 通过。返工修了 `Phi.from_dict` 与 `Registry.load` 不校验，并把 S4 测试夹具的进程退出改成立即终止。留下一处小问题交给 `s05-ast` 顺带改：`_require_layers` 对不可哈希的层状态取值抛 `TypeError` 而不是 `ValueError` |
| s05-ast | 语句层：sqlglot 提取与正则兜底，发明特征（正则类）的求值 | features/ast.py；tests/test_surprise_s05_*.py | s05-vocab 已合并 | ast | **已合并**（dd472f9，返工 1 轮）。合并后 pytest 323 passed / 3 skipped，S05 的 `vocab spec units ast` 通过（`ast` 组按新表：74 条探测、5 条兜底）。返工修了七处判错：把括号当子查询、命名窗口、IGNORE NULLS、写语句里的相关子查询、赋值记成比较、同名遮蔽、兜底的两处误报；顺带把 `_require_layers` 改成抛 `ValueError`。词表追加了一个叶子 `ast:window_fn:other`（词表摘要因此变为 1e001c14a030） |
| s05-dynamic | 计划层、数据层、组合入口 `extract`、`extract_isolated`、命令行（phi / corpus / vocab）与语料分布报告 | features/plan.py、data.py、extract.py、__main__.py 及其辅助文件；tests/test_surprise_s05_*.py | s05-ast 已合并 | dynamic stable distinguish specs corpus | 已派发（2026-10-09；验收基线 323 passed）。审查用 `.orch/scratch/s5_review_dynamic.py` |

表内路径相对 `framework/surprise/`、`framework/`。门槛 `python -m surprise.gates.s05 --only <组>`，九组全过才是 S05 通过。`harness/` 已冻结，三个包都不许碰。

### 契约（派发前定）

- 词表：`gates/s05_cases.py` 的 `CORE_VOCAB`，166 项。特征 id 是 `层:名[:值]`，层为 `ast`、`plan`、`data`；种类为 class（层级内部节点，不出现在 φ 里）、leaf、family（开放族：`plan:<算子名>`、`ast:fn:<函数名>`）。
- φ：`Phi(engine, features, layers, vocab)`，`features` 是排好序的叶子 id，`layers` 记三层各自的状态（ast：ok / fallback；plan、data：ok / unavailable / skipped），`vocab` 是词表摘要。里面没有任何随运行变化的内容。
- 规格核对：必须项与数据性质要在 φ 的闭包里，禁止项不能在；层没算出来的项记为不确定，结论为不满足。
- 单元：`引擎|oracle|主构造|计划算子类|数据性质类`，各维的优先级写在说明和 `UNIT_PROBES` 里。

### 派发前实测（脚本在 `.orch/scratch/s5_*.py`，不入库）

- sqlglot 30.21.0 解析：已知复现全部成功；种子语料 DuckDB 784 条里 767 条、PostgreSQL 308 条里 291 条成功。
- 种子语料在 DuckDB 1.5.5 上：setup 全部成功的 532 条，其余 252 条有语句被拒；`EXPLAIN (FORMAT JSON)` 能取到计划的 676 条。DataFusion 的计划来自 `EXPLAIN` 的 physical_plan 文本。
- 各族默认计划里的算子：F1、F6 有 LEFT_DELIM_JOIN；F2 是 HASH_JOIN（窗口被 window_self_join 改写掉了）；F3 是 STREAMING_WINDOW 加 NESTED_LOOP_JOIN，没有名为 ASOF 的算子；F8 有 UNION；F9、F10 有 WINDOW；DF-A、DF-B 是 HashJoinExec。门槛里各族的单元照这些写。

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

### 未决问题（S5 及之后需要知道的）

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
- `.venv` 里没有 sqlglot。S5 开工时由编排者安装（用户已预先同意按推荐确认），装完 manifest 的 `packages.sqlglot` 自动有值；不需要改 harness。
- manifest 的 `packages` 是固定名单（duckdb、datafusion、pyarrow、psycopg2-binary、sqlglot）。后续层要记别的版本，在传给 `Ledger.start_run` 的 dict 上自己加键。
- `harness/manifest.py` 里的 PostgreSQL 默认 DSN 是从 `harness/oracles/pg_reference.py` 抄了一份的字符串；两处都已冻结，改端口要一起改（解冻）。
- `datafusion/` 的 DF-B SQL 注释漏了正确 bag 中的 NULL，旧文件不改，留 S12；门槛按实测包含 NULL。

S5 发现、留后续会话：
- harness 把重跑时退出码不同算作没有复现。Windows 上以 `exit()` 正常路径结束、而 DuckDB 工作线程还在跑的进程，约 0.5% 会以 0xC0000005 而不是原来的退出码结束（实测 400 次里 2 次；立即终止进程则 600 次全部一致）。所以一个靠正常退出路径死掉的真实引擎崩溃，有小概率被判成 `invalid / unstable_rerun`。方向是少判；harness 已冻结，没有改。S8 的长 run 里如果看到成批的 `unstable_rerun` 崩溃，先想到这一条。
- `Registry.load` 接受顶层是裸列表的文件（`save` 写的是 `{"invented": [...]}`），忽略条目里多余的键，空正则 `""`（对任何语句都命中）能登记。未验收的特征不会进 φ，所以现在无害；S10 定验收规则时把空正则和恒真正则挡掉。
- 语句层（`features/ast.py`）已知的小偏差，都不在被测语句的常见形态上，S8 生成探索语句时如果用到再修：`CREATE VIEW ... AS SELECT` 与 `COPY (SELECT ...) TO` 的查询被记成 `ast:subquery:scalar`；引用另一个命名窗口的命名窗口（`w2 AS (w1 ORDER BY a)`）不继承 `w1` 的规格；`INSERT ... ON CONFLICT DO UPDATE SET v = 3` 的赋值仍记成 `ast:cmp:eq`；兜底认 CTE 要求 `AS` 与括号之间有空白。
- sqlglot 把它不认识的语句（EXPLAIN、VACUUM、COPY 等）读成不透明的 Command：语句层状态是 `ok`，特征为空，不走兜底。作用域分析失败时（`ast.py` 里两处 `except Exception`）不记相关性、状态仍是 `ok`，没有任何标记；整份种子语料上没有触发过。
- `ast:fn:<名>` 用的是 sqlglot 归一后的函数名（`substr` → `substring`，`date_trunc` → `timestamp_trunc`），不是原文里写的名字。S6 之后写规格、S7 的 LLM 提假设时要用归一后的名字；sqlglot 升级可能改这些名字，manifest 的 `packages.sqlglot` 记着版本。

已解决（留作索引）：S3 记的"manifest 环境字段"与"Cross DATE 假候选"两条在 S4 解决（环境字段补齐；`incomparable_results` 前提）；S2 第 7 条（`Label.cve` 是占位）、第 11 条（没记间接依赖）在 S4 解决；S2 第 1、2 条（F10 与逐族期望）已由 `gates/s04.py` 落实。

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
- PLAN.md 决策表第 2、4、5、7–10 条仍是建议，到对应会话开工时再定（第 6 条本会话已采用）。

### 给下一个编排者的操作提醒

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

### 下一会话的起点：S5

- 从 main 的 `s04-done` 建分支 `session/s05`。先检查主分支、tag、工作区和 PG 状态；服务器停止时按 S3 一节的恢复命令启动，不重新 initdb。
- 起点检查（在 `framework/` 下）：`../.venv/Scripts/python.exe -m pytest -q testing tests` 应为 275 passed, 3 skipped；`../.venv/Scripts/python.exe -m surprise.gates.all` 应为 `GATES: PASS (4/4 passed)`（约 6 分钟）。
- S5 做共同语言 φ（范围见 SESSIONS.md 的 S5 一节）：代码放 `framework/surprise/features/` 与 `theory/contracts.py`，不碰 `harness/`（已冻结，派发脚本会把它列入禁区）。按 ORCHESTRATION 第 8 节，先契约一包，再两包并行。
- 开工前要定的事，用户已指示按编排者的推荐确认并记入 DECISIONS：往 `.venv` 装 sqlglot（PLAN 决策 5）；PLAN 决策 2（版本空间用 φ 字面量合取加特征类层级）与决策 4（单元粒度先粗）是否在 S5 采用。
- harness 给 S5 的现成东西：`SqlCase`；`registry.runner_factory_for(engine)`；`execute_isolated` 可在隔离进程里跑 EXPLAIN 与数据性质查询；`ExperimentRecord.phi` 与 `spec` 是 dict，`evaluate_final` 原样入账；第 3 档的 `cve.minimize.case` 是最小化后的用例。S5 门槛要的"最小复现"可以直接用 `gates/s04_cases.py` 的用例表。
- 派发一律在仓库根用 `.venv/Scripts/python.exe tools/orch/grok_worker.py …`；worktree 里直接用 `python`。审查测试通过数至少 275，完整 diff、每条执行命令、分支当前 HEAD 上的独立复跑都不可省。默认两轮返工上限。
- S4 两个包都已合并并清理，`gw list` 应全部显示 cleaned。历史 brief / report / review / 返工意见在 `docs/orch/s04/`；编排者的探测与审查脚本在 `.orch/scratch/`（不入库）。恢复时看 git log、本文件和 gw list。
