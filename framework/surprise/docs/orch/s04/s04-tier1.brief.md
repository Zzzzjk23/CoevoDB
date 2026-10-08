角色：执行者

# 工作包 s04-tier1：新进程执行器、CVE 第 1 档、最终标签入口

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s04-tier1`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s04`（门槛提交 51f2fa1 之后）
- 所属会话：S4（Phase 1c：CVE 分层流水线，里程碑 M1），范围见 `framework/surprise/docs/SESSIONS.md` 的 S4 一节
- 依赖：S3 的七类 oracle 已合并，`surprise.harness.oracles.judge` 与 `surprise.harness.evaluate.evaluate` 可直接用
- 后续：第 2、3 档（归属测试、最小化、画像）由下一个包 `s04-tier23` 做，本包不做；本包结束后 harness 还不冻结

## 目标

依据 `framework/surprise/docs/PLAN.md` 第 3 节"标签流程：CVE"的三步表、"标签规则"三条、"成本分层"第 1 条，以及第 4 节契约表的"标签"行。本包交付第 1 档和它要用的执行器、入口、证据结构。验收以 `framework/surprise/gates/s04.py` 的五组 `contracts isolation tier1 premise environment` 为准；门槛里用到的每个字段名都在下面写明，照写。

### 1. 新包 `framework/surprise/harness/cve/`

内部怎么分文件由你定。从 `surprise.harness.cve` 能导入的公开名字固定为四个：

- `CVE_STEPS = ("rerun", "premise", "attribution", "minimize", "profile")`
- `behavior_shape(behavior: dict) -> str`：`missing > 0` 且 `extra == 0` 返回 `"missing_only"`；反过来 `"extra_only"`；都大于 0 返回 `"both"`；其余（含空 dict）返回 `"none"`。
- `execute_isolated(case, *, prelude=(), timeout_s=QUERY_TIMEOUT_S, wall_timeout_s=None, runner_factory=None) -> IsolatedResult`
- `certify(case, oracle, *, hypothesis=None, diagnose=False, isolation="process", runner_factory=None, timeout_s=QUERY_TIMEOUT_S, wall_timeout_s=None, rewrite_rule=None, paired_query=None, old_python=None, reference_factories=None) -> Label`

#### 1a. `execute_isolated`：新进程执行器

在一个新的操作系统进程里，对目标引擎依次执行 `case.setup`、`prelude` 里的语句、`full_query(case)`，把结果交回调用方。`IsolatedResult` 是冻结 dataclass，带 `to_dict()`（JSON 安全），字段：

- `status`：`"ok"`、`"error"`、`"timeout"`、`"crash"` 四选一；
- `rows`：`ok` 时是目标 runner 返回的行（已归一化的 list of list），其余为 `[]`；
- `error`：`error` 时是 runner 给的错误文本，其余为 `None`（`timeout`、`crash` 可以带说明）；
- `exit_code`：`crash` 时是子进程的退出码（非 0 整数），其余为 `None`。

分类规则：
- 子进程没有交回结果就结束（引擎把进程带崩、被信号杀掉、`os._exit`）是 `crash`；
- 超过 `wall_timeout_s`（默认取常数）还没结束，终止子进程，是 `timeout`；runner 自己报的语句超时（`QueryResult.timed_out`）也是 `timeout`；
- 语句报错是 `error`，包括 INTERNAL 错误（内部错误怎么归类是 oracle 的事，不在执行器里判）；
- setup 语句报错也算 `error`。

任何引擎侧的失败都不许让调用方进程退出或抛异常。子进程的环境变量继承父进程，但去掉 `DEEPSEEK_API_KEY`；子进程必须能导入父进程能导入的模块（同样的 `sys.path`）。Windows 上要确认超时后子进程真的被终止。

旧原型 `framework/coevo/executor.py` 的做法（spawn 上下文、队列、`join(timeout)`、`terminate`、队列空则按退出码判崩溃）可以照着写，但不要 import `coevo`：它在 S12 归档。也可以照 `harness/oracles/version_worker.py` 的做法，用 `subprocess` 加 JSON 协议。二选一，写进报告。

#### 1b. `certify`：最终标签

输入与 `judge` 相同，另加 `hypothesis`、`diagnose`、`isolation`、`wall_timeout_s`。返回的 `Label` 的 `cve` 一定非空。流程固定：

**第 0 步，原始判定。** 调用现有的 `surprise.harness.oracles.judge`（不改它），得到原始标签。`isolation="process"` 时整个判定在新进程里做，调用方进程里不执行任何目标 SQL（包括下面前提检查要跑的探测查询、单线程重跑）；`isolation="inline"` 时在调用方进程里做，但每一次判定都从 `runner_factory` 新建 runner。

- 请求不合法（未知 oracle、不支持的目标引擎、非法 options、`isolation` 不是这两个值）在任何执行之前抛 `ValueError`。
- `isolation="process"` 且传了 `runner_factory` 或 `reference_factories`：工厂必须是子进程能按 `__module__` 加 `__qualname__` 导入的模块级可调用对象。lambda、闭包、局部类在任何执行之前抛 `ValueError`，工厂不被调用。`inline` 下闭包可以用。
- 原始判定的子进程崩了：这是一个 `fail / crash` 候选，`identity.error_class = "ProcessExit"`，`identity.behavior = {"exit_code": <退出码>}`。`oracle` 是 `cross_dbms` 或 `version_differential` 时，还要用 `execute_isolated(case)` 确认目标引擎单独执行也崩；确认不了就是 `invalid / unattributed_crash`（进程里还有参照引擎，崩溃不能记到目标头上）。
- 原始判定超过墙钟上限：终止子进程，最终标签 `invalid / timeout`；`cve["tier"] = 0`，`cve["raw"]` 记 `{"y": "invalid", "invalid_reason": "timeout", ...}`，五步 `skipped`。
- `judge` 自己抛的其他异常照原样抛给调用方（`evaluate_final` 会记成 `harness_error`）。
- 上面两种降级（`unattributed_crash`、`timeout`）的标签同样带完整的 `cve` 结构，五步各自登记 `ran` 或 `skipped` 及原因。

**原始标签是 pass 或 invalid：不是候选。** 最终标签的 `y`、`fail_kind`、`invalid_reason`、`identity`、`detail` 与原始标签相同；`cve["tier"] = 0`，五步全部 `skipped`。

**原始标签是 fail：第 1 档。** 先查前提，再重跑；前提不成立就不花重跑。`cve["tier"] = 1`。

前提检查按下面的顺序做，每一条都登记进 `cve["premise"]`：

1. `side_effecting_statement`：`full_query(case)` 不是单条只读 SELECT（复用 `surprise.harness.oracles.pg_reference.is_readonly_query`），并且原始 `fail_kind` 不是 `crash`。原因见背景第 3 条。写语句的 crash 候选照常往下走。
2. `unspecified_semantics`：查询里有 ASOF JOIN，并且右表在这个连接的 ON 条件所引用的右表列上有重复行（在库上用查询算，做法可以参照 `oracles/determinism.py` 的 `_group_cardinality`）。解析不了 ON 条件时按违反处理。没有并列的 ASOF 连接不违反前提。S4 只登记这一条未指定语义的规则。
3. `incomparable_results`：只对 `cross_dbms` 的 `wrong_result` 候选。用原始标签 `detail["participants"]` 里各引擎的 bag 证据（宽松归一化后的行，JSON 文本）按列比较值的类别：`null`、`bool`、`num`（`["num", x]` 与 `float:` 前缀）、`temporal`（`["temporal", s]`）、`interval`（`interval:` 前缀）、`bytes`（`bytes:` 前缀）、`text`（其他字符串）、`list`、`map`。取目标的 bag 与任意一个和多数一致的参照的 bag：某一列里目标有一个参照没有的类别，同时参照有一个目标没有的类别，就是不可比（`null` 不算类别，不构成冲突）；两边列数不同也是不可比。不改旧 normalizer，不解析日期字符串。

违反任何一条：最终标签 `invalid`，`invalid_reason` 取按上面顺序第一条被违反的名字，重跑 `skipped`。

重跑规则（常数在 `constants.py`）：

- 在默认设置下做 `CVE_RERUN_ATTEMPTS`（定为 5）次新的原始判定，每次一个新进程（`inline` 时每次新 runner）。不提前停：五次都跑完，都计数。
- 一次重跑"复现"的定义：它的原始标签判定，加上它执行过的每条语句的结果（成功则是归一化后的行 bag，失败则是错误类别，超时则是超时），与第 0 步那一次完全相同。比的是 bag，不是行序；只看标签里的 `missing / extra` 计数不够（背景第 2 条的 F8 会漏过去）。子进程崩溃的候选，复现就是重跑也以同样方式崩。
- 另做一次单线程重跑：setup 之后、判定之前先执行 `diagnosis.bisect.prelude_for_names(engine, [...])` 给出的语句，DuckDB 用 `"threads"`，DataFusion 用 `"target_par1"`。它不计入 `attempts`。默认重跑已经不稳定时可以不做。
- 五次都复现、单线程也复现：稳定，标签 `fail`。
- 五次都复现、单线程不复现：候选依赖并行。再做 `CVE_RERUN_EXTENDED`（定为 15）次默认设置的重跑，同样不提前停；二十次全部复现才是 `fail`，否则不稳定。
- 其余情况：不稳定，最终标签 `invalid / unstable_rerun`。

最终标签为 `fail` 时，`fail_kind`、`identity`、`detail` 与原始标签相同。被 CVE 降级为 `invalid` 时，`identity` 置空（默认的 `IdentityEvidence()`），`detail` 保留原始 `detail`，原始判定留在 `cve["raw"]`。

`hypothesis` 不是 `None` 或 `diagnose=True`：本包抛 `NotImplementedError`（下一个包实现）。

#### 1c. `Label.cve` 的结构（固定）

```
{
  "schema": 1,
  "tier": 0 | 1,                       # 下一个包会用到 2、3
  "isolation": "process" | "inline",
  "raw": {"y": ..., "fail_kind": ..., "invalid_reason": ..., "identity": {...}},   # 原始判定
  "rerun":       {"status": "ran" | "skipped", "reason": None | "<非空字符串>", ...},
  "premise":     {同上},
  "attribution": {同上},
  "minimize":    {同上},
  "profile":     {同上}
}
```

- 每一步都有 `status`；`skipped` 时 `reason` 是非空字符串（如 `"not_a_candidate"`、`"premise_violated"`、`"not_requested"`），`ran` 时 `reason` 为 `None`。
- `rerun` 为 `ran` 时另有：`attempts`（默认设置的重跑次数，5 或 20）、`reproduced`（其中复现的次数）、`stable`（bool）、`extended`（bool，是否做了那 15 次）、`distinct_outcomes`（第 0 步加各次重跑里不同结果的个数）、`single_thread`：恰好是 `{"ran": bool, "reproduced": bool 或 None}`。
- `premise` 为 `ran` 时另有：`violations`（按上面顺序列出被违反的名字，没有就是 `[]`）、`checks`（每条检查一个条目，至少有 `ok`）。
- `cve` 里不放进程号、耗时、临时路径、时间戳：同一个稳定的输入 `certify` 两次，`Label.to_dict()` 必须相等。

### 2. `surprise.harness.evaluate.evaluate_final`

签名在 `evaluate` 的基础上加 `hypothesis=None, diagnose=False, isolation="process", wall_timeout_s=None`，返回 `ExperimentRecord`。每调用一次恰好写一条账本记录，标签是 `certify` 的最终标签；pass、invalid 同样入账。参数校验与 `evaluate` 一致：记录会拒绝的参数、没有 start 过的 `run_id`、不合法的请求，都在任何执行之前抛出，不留记录。`certify` 抛出的其他异常记成 `invalid / harness_error`，此时 `cve` 仍是完整结构（`tier` 为 0，`raw` 为 `{"y": "invalid", "invalid_reason": "harness_error", ...}`，五步都是 `skipped`）。

现有的 `evaluate` 与 `judge` 一个字都不改：它们是原始 oracle 层，S2、S3 的门槛和测试要求它们返回 `cve == {}`。

### 3. `harness/contracts.py`

`INVALID_REASONS` 在现有十一项之后按这个顺序追加六项，并在上方注释里各写一句含义：
`unstable_rerun`、`unspecified_semantics`、`side_effecting_statement`、`incomparable_results`、`unattributed_crash`、`not_reproduced_minimized`（最后一项下一个包用）。别的取值表不动，`SCHEMA_VERSION` 不动。

### 4. `harness/constants.py`

加 `CVE_RERUN_ATTEMPTS = 5`、`CVE_RERUN_EXTENDED = 15`、`CVE_WALL_TIMEOUT_S = 120.0`（一次隔离判定或隔离执行的墙钟上限，`wall_timeout_s=None` 时用它）。你另外需要的数值常数也放这里，名字以 `CVE_` 开头，各带一行注释。它们经 `as_dict()` 自动进 manifest。

### 5. `harness/manifest.py`

- `build_manifest` 的 `environment` 保留现有三个键，另加：
  - `old_engines`：`{"duckdb": <版本或 None>, "datafusion": <版本或 None>}`，旧版 venv 里实际装的版本。解释器的定位方式与 `harness/oracles/version_differential.py` 相同（git 公共目录旁的 `.venvs/`，`COEVO_VENVS` 可覆盖，按平台找 `Scripts/python.exe` 或 `bin/python`）；用该解释器加 `-I`、空工作目录执行，只导入对应引擎。取不到就是 `None`，不抛异常。
  - `references`：`{"postgres": <server_version 或 None>}`，经参照 DSN（`COEVO_REFERENCE_PG_DSN` 或默认值，见 `harness/oracles/pg_reference.py`）问服务器；连不上是 `None`，不抛异常，不打印 DSN。
  - `packages`：`{分发名: 版本或 None}`，至少有 `duckdb`、`datafusion`、`pyarrow`、`psycopg2-binary`，用 `importlib.metadata` 取。
- `HASHED_PATHS`：harness 里新 import 的每一个旧模块（`framework/` 下、`surprise/` 以外）都要加进去，例如 `diagnosis/bisect.py`。门槛会用 AST 扫 harness 的 import 逐个核对。

### 6. 测试

新增 `framework/tests/test_surprise_s04_*.py`。要覆盖：执行器四种状态与 prelude；`certify` 的 pass / invalid 不重跑；稳定候选；用可编排的假 runner 验证重跑规则的每一个分支（全部复现、单线程不复现后扩展、扩展中漏一次、只复现一两次、行序颠倒仍稳定）；三条前提各自的违反与不违反；进程崩溃、挂起、参照引擎崩溃；`evaluate_final` 的入账与参数校验；manifest 环境字段。测试必须确定：不要断言 F5 这类真实竞态的结果，不稳定性用假 runner 造。

三个已有测试文件里各有一处断言要随需求更新，只许做下面写明的改动，别的不动：

- `tests/test_surprise_contracts.py`：`assert INVALID_REASONS == (...)` 的期望元组末尾加上那六项。
- `tests/test_surprise_s03_registry.py`：`INVALID_REASONS[-4:] == (...)` 改成 `INVALID_REASONS[7:11] == (...)`，四个名字不变。
- `tests/test_surprise_manifest.py` 的 `test_build_manifest_on_the_real_tree`：`manifest["environment"] == {...}` 改成对原有三个键逐个断言原值，再加对三个新键的断言。

## 背景

编排者派发前在本机实测过的事实（DuckDB 1.5.5 / 1.1.3，DataFusion 54.0.0 / 50.0.0，PostgreSQL 16.15）：

1. `duckdb/F10_window_frame_underflow.sql` 的前两条 ntile 语句直接执行会让进程以 0xC0000094 退出。经 `judge` 不会崩：确定性筛查在执行前就判了 `invalid / nondeterministic`。门槛用这两条语句直接验证 `execute_isolated`。
2. `docs/recall_repros.json` 的 F8（COLLATE NOCASE 的 UNION）在同一个进程里判定稳定，但 40 个新进程里有 38 个结果互不相同；各次 plan variant 的 `missing / extra` 计数却常常碰巧一样。所以重跑必须比较每条语句的结果 bag。
3. plan variant 在同一个连接上依次跑各个变体。`DELETE … RETURNING`、`UPDATE … RETURNING` 这类写语句每跑一次都改数据，原始判定是假的 `fail / wrong_result`。F11 的 MERGE 是 crash，不受影响（默认计划成功，`SET disabled_optimizers='build_side_probe_side'` 之后报 INTERNAL）。
4. F5（recall 条目）是并行竞态：新进程里第一次执行 150 次全对；切过优化器开关后的第二次执行 80 次里错 5–9 次；threads=1 和关优化器 80 次全对。原始判定多数是 fail（每次见证的开关不同），偶尔是 pass。它的最终标签应是 `invalid / unstable_rerun`，重跑的 `reproduced / attempts` 就是观察到的比例。
5. F3（ASOF JOIN，右表 `px` 在 `(id, ts)` 上有并列）在 20 个新进程里结果完全一致，重跑筛不掉，只能靠前提规则。去掉并列行之后 plan variant 判 pass。
6. DataFusion 目标的 `SELECT DATE '2020-01-02' AS d` 原始为 Cross fail：旧 DataFusion runner 把日期转成 ISO 字符串（`targets/datafusion_runner._norm`），DuckDB 与 PostgreSQL 的 runner 给的是 temporal 值，宽松 bag 里是 `"2020-01-02"` 对 `["temporal", "2020-01-02T00:00:00"]`。DuckDB 目标、参照只有 DataFusion 与 SQLite 时，DATE 列同样原始为 fail。DF-A、DF-B、DF-D（一列全是 NULL 对数字）是可比的，必须保持 fail。
7. `.venv` 里没有 sqlglot，不要引入任何新依赖；ASOF 的识别用标准库。
8. 每个新进程（Python 启动加导入引擎）在这台机器上约 0.2–0.4 秒。

可以直接调用的现有代码：`surprise.harness.oracles.judge` 与 `forms.full_query`；`harness/oracles/common.py` 的 `RecordingRunner`（记录每条语句及结果）；`harness/oracles/registry.py` 的 `runner_factory_for`、`validate_request`、`make_options`；`diagnosis/bisect.py` 的 `prelude_for_names`。要给一次判定加 prelude，可以包一层 runner：`setup()` 之后跟着执行 prelude 语句（`DuckDBRunner.setup` 每次都会重连，所以 prelude 必须在每次 `setup()` 之后重放）。

`surprise/gates/s04_fixtures.py` 是门槛用的假 runner，读一遍能看出门槛怎样观察你的实现；不要在 harness 或测试里 import 它（`gates/` 不归你改，测试需要假 runner 就在测试文件里自己写）。

## 允许改动的路径

只改下面这些路径（`**` 跨目录，`*` 不跨）。审查按这个清单逐个文件核对，清单以外的任何改动都算越界。

```allow-paths
framework/surprise/harness/cve/**
framework/surprise/harness/evaluate.py
framework/surprise/harness/contracts.py
framework/surprise/harness/constants.py
framework/surprise/harness/manifest.py
framework/tests/test_surprise_s04_*.py
framework/tests/test_surprise_contracts.py
framework/tests/test_surprise_manifest.py
framework/tests/test_surprise_s03_registry.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`。
- 不改 `framework/surprise/harness/oracles/`、`harness/ledger.py`：原始 oracle 层与账本保持 S3 的样子。
- 旧代码（`framework/surprise/` 以外）本包不碰：只调用，不改一个字。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。上面"测试"一节写明的三处改动之外，某个测试确实该改，就写进报告的"未决问题"，停下。
- 不按族号、SQL 文本或期望行在 harness 里硬编码判定：规则只看语句形态、数据和执行结果。
- 标签路径上不调用 LLM，harness 不 import `llm`、`coevo`、`httpx`、`openai`；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。本包不需要任何 LLM 调用。
- 不安装、不升级任何依赖，不动 `.venv`、`.venvs/`、`.orch/pg16/`。
- 不清理 `.orch/tmp`：临时文件留着不管。被权限规则拒绝的操作不要换写法重试。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不做第 2、3 档，不做理论层、Hunter、LLM 角色。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器，不要换别的（CLAUDE.md 里写的 `../.venv/Scripts/python.exe` 在 worktree 里不存在）。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。PostgreSQL 参照已在 127.0.0.1:55432 运行，不要启停它。

```powershell
cd framework
python -m pytest -q testing tests                                                   # 通过数不少于 242，skip 不多于 3
python -m surprise.gates.s01                                                        # 退出码 0
python -m surprise.gates.s02                                                        # 退出码 0
python -m surprise.gates.s03                                                        # 退出码 0
python -m surprise.gates.s04 --only contracts isolation tier1 premise environment   # 退出码 0
```

`python -m surprise.gates.all` 在本包结束时仍会报 s04 FAIL：`tier2 tier3 m1 freeze` 四组属于后面的工作，这是预期的，不要为了让它们变绿去做范围外的事。不要直接跑不带路径的 `pytest`（`framework/test_api.py` 会调用外部 API）。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。认为门槛的某个期望不对，写明是哪一行、你实测到什么，停下。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s04-tier1

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
