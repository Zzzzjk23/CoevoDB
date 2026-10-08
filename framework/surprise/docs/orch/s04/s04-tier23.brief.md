角色：执行者

# 工作包 s04-tier23：CVE 第 2 档归属测试接口与第 3 档最小化、完整画像

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s04-tier23`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s04`（`s04-tier1` 已合并）
- 所属会话：S4（Phase 1c：CVE 分层流水线，里程碑 M1），范围见 `framework/surprise/docs/SESSIONS.md` 的 S4 一节
- 依赖：`surprise.harness.cve` 的 `execute_isolated`、`certify`（第 0 步与第 1 档）、`behavior_shape`、`CVE_STEPS`；`surprise.harness.evaluate.evaluate_final`。先把 `framework/surprise/harness/cve/` 读一遍，沿用它的隔离方式、证据结构和写法：`isolate.py` 是父进程侧（`subprocess` 加 JSON，`call_worker`），`worker.py` 是子进程入口（现有 `execute`、`judge` 两个 op，你可以加新的 op），`session.py` 的 `run_judge` 做一次带 prelude 的判定并返回每条语句的结果指纹，`premise.py` 是三条前提，`certify.py` 是第 0 步与第 1 档
- 本包合并后，编排者冻结 harness：这是 S12 之前最后一次可以改 `framework/surprise/harness/` 的机会

## 目标

依据 `framework/surprise/docs/PLAN.md` 第 3 节"标签流程：CVE"的"画像"一行、"成本分层"第 2、3 条，第 4 节契约表的"标签"行（身份证据：开关 I、错误类别、行为画像），第 6 节决策 3。让 `certify` 的 `hypothesis` 与 `diagnose` 两个参数生效（现在是 `NotImplementedError`）。验收以 `framework/surprise/gates/s04.py` 的 `tier2 tier3 m1` 三组为准，前五组 `contracts isolation tier1 premise environment` 必须保持通过；门槛里用到的每个字段名都在下面写明，照写。

第 1 档的行为不变：下面三步只在候选通过第 1 档（标签仍是 `fail`）之后才发生。第 1 档降级的、原始就不是候选的，第 2、3 档一律 `skipped` 并写原因。

### 1. 复现判据（第 2、3 档共用）

"候选在某个 prelude 下是否仍然复现"统一定义为：**被见证的两种形式仍然不一致**。

- `plan_variant`：只看见证差异的那个变体（原始标签 `identity.switches` 里的那个）。在 prelude 之后执行查询（形式一），再打开见证开关执行一次（形式二）。两边都成功且 bag 相同、或两边以相同的错误类别失败，算一致（不复现）；其余算不一致（复现）。
- 其他六类：在 prelude 之下重做原始判定，标签仍是 `fail` 算复现。

这个定义是 F11 能定位的原因：MERGE 在默认计划下成功、关掉全部优化器后报 INTERNAL；只关 `build_side_probe_side` 时形式一也报同样的 INTERNAL，两边一致，差异"被消除"，所以它是 fix set。旧 `oracles/reproduce.py` 的 `CaseChecker.reproduces` 对 crash 候选只执行形式一，做不到这一点，不要直接用它做判据；按 `SignatureEngine`、`BugFixer._minimize` 需要的 `reproduces(candidate, schema_sqls, inserts, q1, q2, prelude_sqls=...)` 形状自己写一个 checker 交给旧工具。

每次判据执行都用新建的 runner 重新 setup（MERGE 这类语句会改数据）。`isolation="process"` 时第 2、3 档的全部目标 SQL 同样不在调用方进程里执行：把整段归属测试、整段最小化加画像各放进一个子进程，墙钟上限取常数。

### 2. 第 2 档：归属测试接口（`hypothesis` 不为 `None`）

`hypothesis` 是一个 mapping（harness 不 import 理论层；S6 会把 `theory.contracts.Hypothesis.to_dict()` 传进来）。用到的键：

- `hypothesis_id`：非空字符串，必填；
- `engine`：必填，必须等于 `case.engine`；
- `interventions`：字符串列表，必填，可以为空；每个名字必须是该引擎干预基里的名字（`diagnosis.bisect.interventions_for(engine, runner)` 给出的那些）；
- `fail_kind`、`error_class`、`behavior_shape`：可选，只在 `interventions` 为空时使用。

其余的键忽略。不是 mapping、缺必填键、类型不对、引擎不符、有未知的干预名：抛 `ValueError`。校验在原始判定之前完成，与候选是否成立无关（一个最终会 pass 的用例配上非法假设同样抛错）。需要向引擎要干预名单时在子进程里问，调用方进程不执行目标 SQL。

候选通过第 1 档之后做**一次**归属测试：

- `interventions` 非空（`method = "fix_set"`）：用 `diagnosis.bisect.prelude_for_names(engine, interventions)` 作 prelude 做一次复现判据。不再复现，身份一致。这是 `evolution/co_evolution.py` 的 `_expand_family` 里"Fast membership test"那一段（第 484–504 行）的做法。
- `interventions` 为空（`method = "profile"`）：比较假设给出的 `fail_kind`、`error_class`、`behavior_shape` 与候选的对应值（`behavior_shape` 用 `cve.behavior_shape(identity.behavior)`）；假设里出现的键全部相等才一致。三个键一个都没给：`ValueError`。

`cve["attribution"]` 为 `ran` 时另有：`hypothesis_id`、`method`、`consistent`（bool）、`executions`（判据执行次数，profile 方式为 0）。

- 一致：最终标签 `fail`，`cve["tier"] = 2`，`minimize`、`profile` 为 `skipped`（原因如 `"attributed"`），`identity` 与第 1 档相同。
- 不一致：升到第 3 档（即使 `diagnose=False`）。

没有给 `hypothesis` 时 `attribution` 为 `skipped`。

### 3. 第 3 档：最小化与完整画像（`diagnose=True`，或归属不一致）

**最小化。** 复用旧代码，不改它：

- `agents.bug_fixer.BugFixer._minimize` 当作普通函数调用，第一个参数给一个只带 `checker` 属性的对象，不要实例化 `BugFixer` 或 `BaseAgent`，不构造任何 LLM 客户端。它按语句删 INSERT，再删 SELECT 列表项。它需要旧的 `oracles.models.Candidate`：`schema_sqls` 放 setup 里非 INSERT 的语句，`inserts` 放 INSERT 语句，`q1` 放被判据执行的查询。
- 旧函数不删建表语句。在它之后加一遍：对剩下的每条 setup 语句试着去掉，仍复现就去掉（用同一个判据），这样没用到的表会被删掉。
- 两段各有执行次数上限（常数）。
- 最小化结束后，无论有没有删掉东西，都对最小化后的用例再做一次复现判据（不带 prelude），并重查第 1 档的前提。
  - 不再复现：最终标签 `invalid / not_reproduced_minimized`，`identity` 置空，`profile` 为 `skipped`；
  - 违反前提：最终标签 `invalid`，原因取被违反的前提名，`profile` 为 `skipped`。

`cve["minimize"]` 为 `ran` 时另有：`reproduced`（bool）、`setup_before`、`setup_after`（语句条数）、`case`（最小化后的 `SqlCase.to_dict()`；`setup` 必须是原 setup 的子序列）、`executions`。

**画像。** 在最小化后的用例上做，复用旧工具：

- fix set：`diagnosis.bisect.compute_fix_set(fails, engine, runner, max_executions=...)`，`fails(prelude)` 就是上面的复现判据。可以经 `diagnosis.signature.SignatureEngine.compute` 一起拿到三项，也可以直接调用下面两个函数。
- plan diff：`diagnosis.bisect.plan_diff_ops`（默认计划与全部干预关闭时的算子差）。
- 版本梯：旧 `SignatureEngine._version_ladder` 的口径，取值 `longstanding`（旧版对最小化查询返回与新版默认相同的行）、`recent`（不同，或旧版报运行期错误）、`unknown`（旧版报 Parser / Binder / Catalog 错误，或判断不了）、`unavailable`（没有旧版环境）。旧版执行走 S3 的 `harness/oracles/version_worker.py` 那条路（按平台定位解释器，不用旧代码写死的 `bin/python`）。DataFusion 可以算，也可以记 `unavailable`。
- 错误类别与行为画像：取自候选的身份证据。

`cve["profile"]` 为 `ran` 时另有：`fix_kind`（旧工具的原值，如 `single`、`minimal_set`、`unstable`、`non_optimizer`）、`fix_set`（排序后的列表，可以为空）、`plan_diff`（算子名列表）、`version_ladder`、`error_class`、`behavior_shape`（`wrong_result` 候选才有意义，其余为 `None`）、`witness_switches`（原始标签的 `identity.switches`，列表）、`executions`。

最终标签 `fail`，`cve["tier"] = 3`。`identity.switches`：`fix_set` 非空时取 `fix_set`，为空时保留原始见证开关；`error_class`、`behavior` 不变。

第 3 档的子进程崩溃或超时：标签保持 `fail`（第 1 档已经确认），`minimize`、`profile` 记 `skipped` 并写原因，`tier` 不升。

同一个稳定的输入 `certify(..., diagnose=True)` 两次，`Label.to_dict()` 必须相等。

### 4. 其余

- `harness/constants.py`：加 `CVE_MINIMIZE_MAX_EXECUTIONS`、`CVE_BISECT_MAX_EXECUTIONS = 120`、`CVE_PROFILE_WALL_TIMEOUT_S`，以及你另外需要的数值常数，名字以 `CVE_` 开头，各带一行注释。旧 `_minimize` 内部用的是它自己的 `MAX_MINIMIZE_EXECUTIONS = 30`，新常数管你加的那一遍。
- `harness/manifest.py`：`HASHED_PATHS` 加上 harness 新 import 的每个旧模块（`agents/bug_fixer.py`、`diagnosis/signature.py` 等）。门槛用 AST 核对。`environment.packages` 的固定名单里再加 `sqlglot`（S5 的 φ 要用；现在没装，记 `None`，不要安装它）。
- `evaluate_final` 把 `hypothesis`、`diagnose` 原样传给 `certify`，现在应当能用。
- 测试：新增 `framework/tests/test_surprise_s04_*.py`（可以新建文件，也可以在本包上一个包建的文件里加）。覆盖复现判据（含 crash 候选两边都崩算一致）、归属测试两种方式的一致与不一致、假设校验、最小化（删行、删表、子序列、最小化后不复现）、画像各字段、降级与跳过原因、两次判定相等。不稳定和"最小化途中丢失"用假 runner 造，不依赖真实竞态。

## 背景

编排者派发前用旧工具实测的结果（DuckDB 1.5.5，旧版 1.1.3）。门槛的期望照这些写；你的实现走的是同一批旧工具，应当得到同样的数：

| 用例 | 见证 | fix_kind / fix_set | 版本梯 | 最小化 |
|---|---|---|---|---|
| F1（recall） | plan variant `no_optimizer` | single / `deliminator, filter_pushdown` | longstanding | 6 条 setup 剩 5 条 |
| F2（recall）与 `.sql` 里的写法 | `no_optimizer` | single / `window_self_join` | recent | 不变 |
| F7（recall）与 `.sql` 里的写法 | `no_optimizer` | single / `common_subexpressions, expression_rewriter`；plan diff 为空 | longstanding | 不变 |
| F9（recall） | `window_combine` | unstable / 空集（用满 120 次） | longstanding | 不变 |
| F11 MERGE | `no_optimizer`，crash，`InternalException` | 只有 `build_side_probe_side` 单独关闭时两边一致 | unknown（1.1.3 报 Parser Error） | — |
| F6：recall 的表结构与查询加三行数据 | `no_optimizer` | single / `deliminator, filter_pushdown`（与 F1 相同） | longstanding | 没用到的 `accounts` 表应被删掉 |
| F6 带谓词 `o1.placed IS NOT NULL` | TLP（plan variant 判 pass） | 同上 | longstanding | — |
| DF-B（DataFusion，Cross） | 无开关 | 七个 DataFusion 干预都消不掉，fix_set 为空 | — | — |

- F1 的 setup 后面再加一张无关的表和它的 INSERT，旧 `_minimize` 只删掉那条 INSERT，建表语句还在；门槛要求两条都不在最小化结果里。
- `import agents.bug_fixer` 会连带导入 `agents.base_agent`（`httpx`）和 `llm.ledger`，导入本身没有副作用。在用到第 3 档时再导入（函数内 import），harness 自己的文件不直接 import `llm`、`httpx`。
- `SignatureEngine._version_ladder` 只对 `engine == "duckdb"` 且 `differential.available` 为真时工作，它调用 `differential.run_remote(setup, [q1])`，期望返回 `{"results": [{"rows": ..., "error": ...}]}`，`rows` 是归一化后的行。旧 `DifferentialOracle` 在 Windows 上恒为不可用（写死了 `bin/python`），所以要给它一个走 `version_worker` 的替身，或者不经过它、自己按同样口径算。
- 宽 fix set（超过干预基四分之一）在旧 `SignatureEngine.compute` 里会被改判为 `pervasive` 并清空；沿用旧工具的结果，不另立规则。

## 允许改动的路径

只改下面这些路径（`**` 跨目录，`*` 不跨）。审查按这个清单逐个文件核对，清单以外的任何改动都算越界。

```allow-paths
framework/surprise/harness/cve/**
framework/surprise/harness/evaluate.py
framework/surprise/harness/constants.py
framework/surprise/harness/manifest.py
framework/tests/test_surprise_s04_*.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`。
- 不改 `framework/surprise/harness/oracles/`、`harness/ledger.py`、`harness/contracts.py`：原始 oracle 层、账本、取值表保持现状。
- 旧代码（`framework/surprise/` 以外）本包不碰：只调用，不改一个字。
- 不改第 1 档已经通过门槛的行为；发现它有错，写进报告的"未决问题"，停下。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。某个已有测试确实该改，就写进报告的"未决问题"，停下。
- 不按族号、SQL 文本或期望行在 harness 里硬编码判定或画像结果。
- 标签路径上不调用 LLM，不实例化任何 agent；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。本包不需要任何 LLM 调用。
- 不安装、不升级任何依赖，不动 `.venv`、`.venvs/`、`.orch/pg16/`。
- 不清理 `.orch/tmp`：临时文件留着不管，包括你自己建的（提交信息用 `git commit -m`）。被权限规则拒绝的操作不要换写法重试。
- 不建任何指向 worktree 之外的链接或目录联接（`mklink`、符号链接等）。旧版解释器由代码经 git 公共目录自己找到，worktree 里不需要 `.venvs`。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不做理论 T、版本空间、Hunter、LLM 角色。第 2 档只是接口，用手写的假设调通。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。PostgreSQL 参照已在 127.0.0.1:55432 运行，不要启停它。

```powershell
cd framework
python -m pytest -q testing tests                                                   # 通过数不少于 264，skip 不多于 3
python -m surprise.gates.s01                                                        # 退出码 0
python -m surprise.gates.s02                                                        # 退出码 0
python -m surprise.gates.s03                                                        # 退出码 0
python -m surprise.gates.s04 --only contracts isolation tier1 premise environment tier2 tier3 m1   # 退出码 0
```

`python -m surprise.gates.all` 在本包结束时仍会报 s04 FAIL：只剩 `freeze` 一组，由编排者在合并后做，这是预期的。整套 s04 八组在这台机器上要跑几分钟（每个候选 6 个以上新进程，第 3 档每个用例几十到一百多次执行），属于正常。不要直接跑不带路径的 `pytest`。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。认为门槛的某个期望不对，写明是哪一行、你实测到什么，停下。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s04-tier23

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
