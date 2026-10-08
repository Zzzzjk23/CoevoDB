角色：执行者

# 工作包 s02-oracles：TLP、NoREC、Plan variant 的三值适配器，以及把每次执行写进账本的 evaluate

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s02-oracles`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s02`（5a2fb50）
- 所属会话：S2（Phase 1a · 契约、账本、冻结机制、三类健全 oracle），范围见 `framework/surprise/docs/SESSIONS.md` 的 S2 一节
- 依赖：工作包 s02-contracts 已合并，直接用 `surprise.harness.contracts`（`SqlCase`、`IdentityEvidence`、`Label`、`ExperimentRecord` 及各取值表）、`surprise.harness.constants.QUERY_TIMEOUT_S`、`surprise.harness.ledger`（`Ledger`、`LedgerError`）。另一个包 s02-manifest 正在别的 worktree 里并行做 `framework/surprise/harness/manifest.py`，和你没有共同文件。

## 目标

旧 oracle 的 `check()` 返回 `Candidate | None`，None 里混着"通过""不适用""查询报错""超时"。本包给三类健全 oracle 各包一层适配器，显式给出 pass / fail / invalid 和身份证据（PLAN.md 第 3 节逐项表前三行、"标签规则"一段）。此时的 fail 是未经 CVE 的原始判定。

**判定逻辑只搬不改**：什么算差异，由旧 oracle 的 `check()` 说了算，适配器不重新实现比较；适配器只做三件事：执行前的筛查、把 None 拆成 pass 与 invalid、从执行记录里整理身份证据。旧文件一个字都不改。

门槛 `framework/surprise/gates/s02.py` 的 `check_oracles`、`check_evaluate` 和用例表 `framework/surprise/gates/s02_cases.py` 是可执行的验收标准，开工前先读一遍。用例表里的期望值是编排者用旧 oracle 在 DuckDB 1.5.5 上实测得到的，并且已经用一份按下文规则写的参考映射核对过全部 60 项（20 个用例 × 3 个 oracle），所以下文的规则是能满足门槛的。

代码里的注释和文档字符串用英文。只用标准库加仓库已有的代码。

### 1. 对外接口（名字和签名必须一字不差）

```python
# framework/surprise/harness/oracles/__init__.py
IMPLEMENTED = ("tlp", "norec", "plan_variant")
def judge(case: SqlCase, oracle: str, *, runner_factory=None,
          timeout_s: float = QUERY_TIMEOUT_S) -> Label

# framework/surprise/harness/oracles/forms.py
@dataclass(frozen=True)
class GroupedForm:
    select_list: str
    from_tail: str            # 以 FROM 开头
    group_by: str | None      # None 表示 SELECT DISTINCT 形态
    base_where: str | None
def split_grouped(query: str) -> GroupedForm | None
def full_query(case: SqlCase) -> str

# framework/surprise/harness/evaluate.py
def evaluate(case: SqlCase, oracle: str, *, ledger: Ledger, run_id: str, purpose: str,
             spec: dict | None = None, phi: dict | None = None,
             theory_version: str | None = None, p_t: float | None = None,
             runner_factory=None, timeout_s: float = QUERY_TIMEOUT_S) -> ExperimentRecord
```

`framework/surprise/harness/oracles/` 下其余文件怎么分由你定（建议 `tlp.py`、`norec.py`、`plan_variant.py` 各一个，公共部分一个）。

- `oracle` 不在 `IMPLEMENTED` 里：抛 `ValueError`。`case.engine` 不是 `"duckdb"`：抛 `ValueError`（DataFusion 是 S3 的事）。
- `runner_factory` 是一个无参可调用对象，每次调用返回一个新的 runner，接口同 `targets.duckdb_runner.DuckDBRunner`：`setup(sqls) -> [(语句, 错误或 None)]`、`run(sql, timeout_s=...) -> QueryResult`、`close()`。默认用 `DuckDBRunner`。门槛会传一个包着真 runner、对指定语句返回假结果的工厂进来，所以适配器不要绕过 `runner.run` 去直接碰连接。
- `judge` 自己不吞异常：runner 或旧 oracle 抛出来的异常原样往外抛。
- 同一个输入调两次 `judge`，返回的 `Label.to_dict()` 必须完全相同：`Label` 里不放耗时、时间、随机 id（旧 `QueryResult.summary()` 里的 `elapsed` 不要带进来）。`Label.cve` 留空 dict。

### 2. `full_query` 与 `split_grouped`

`full_query(case)` 是"把划分谓词并进查询之后的那一条语句"，确定性筛查和 plan variant 都用它：

1. `case.predicate` 是 None 或全空白：原样返回 `case.query`。
2. 否则若 `split_grouped(case.query)` 不是 None：返回 `oracles.tlp_groupby.build_query(form.select_list, form.from_tail, form.group_by, where=case.predicate, distinct=form.group_by is None, base_where=form.base_where)`（谓词在分组之前过滤行）。
3. 否则返回 `oracles.tlp.inject_predicate(case.query, case.predicate)`。

第 3 条对带尾部子句的查询可能拼出不合法的 SQL（如 `… GROUP BY b WHERE (…)`），不用管：执行时报错，标签自然是 invalid。期望的字符串见用例表的 `FULL_QUERIES`。

`split_grouped(query)` 只认两种形态，其余一律返回 None：

- 分组形态：`SELECT <列表> FROM <尾部> [WHERE <条件>] GROUP BY <键>`，要求 `<键>` 和 `<列表>` 在压缩空白、转小写之后相同。
- 去重形态：`SELECT DISTINCT <列表> FROM <尾部> [WHERE <条件>]`；`DISTINCT ON` 不认。

规则：
- 先去掉首尾空白和末尾的一个分号。关键字不分大小写。"顶层"指括号深度为 0 且不在单引号字符串里。
- 取第一个顶层 `FROM`；`<列表>` 是 `SELECT [DISTINCT]` 与它之间的文本（去首尾空白），为空则返回 None。
- `<列表>` 里不能有聚合或窗口函数：用旧 oracle 自己的标准判断，`oracles.tlp.tlp_applicable("SELECT " + 列表, "1")` 必须为 True。
- `FROM` 之后的顶层子句关键字，认 `oracles.determinism._top_level_positions` 那一组（WHERE、GROUP BY、HAVING、ORDER BY、LIMIT、OFFSET、FETCH、UNION、INTERSECT、EXCEPT、WINDOW、QUALIFY）。去重形态只允许至多一个 WHERE；分组形态要求恰好一个 GROUP BY、其前至多一个 WHERE；出现别的关键字就返回 None。可以直接调用这个旧函数（它带下划线，但旧代码在 S12 之前不会变），也可以自己写同样语义的扫描。
- `from_tail` 是从 `FROM` 到 WHERE（没有 WHERE 就到 GROUP BY 或结尾）的文本；`base_where` 是 WHERE 与 GROUP BY（或结尾）之间的文本，没有 WHERE 就是 None；`group_by` 是 GROUP BY 之后的文本。都去首尾空白。

### 3. `judge` 的流程（顺序是规定的）

1. `full = full_query(case)`。
2. 取一个 runner，执行 `setup(list(case.setup))`。有任何一条报错：`invalid / setup_error`。
3. `oracles.determinism.is_usable_for_oracles(full, runner, list(case.setup))` 为 False：`invalid / nondeterministic`。这一步不能省，也不能挪到后面：结果不确定的查询会让三个旧 oracle 都报出假的差异。
4. 这个 oracle 的前提不满足（见第 4 节）：`invalid / not_applicable`。到这里为止不调用旧 oracle。
5. 再取一个新的 runner 并 `setup`，包一层记录每次 `run` 的 `(sql, QueryResult)` 的代理，把代理交给旧 oracle 的 `check()`，`timeout_s` 透传。按第 4 节把结果映射成 `Label`。
6. 用过的 runner 都要 `close()`（放在 `finally` 里）。

### 4. 各 oracle 的映射

公共规则：

- **fail 的子类型**（`Candidate` → `fail_kind`）：`candidate.kind == KIND_CRASH` 是 `crash`；否则 `r1_summary` 或 `r2_summary` 里有非空的 `error` 是 `error_mismatch`；否则是 `wrong_result`。
- **`identity.error_class`**：`crash` 和 `error_mismatch` 时取报错那一侧的错误文本里第一个冒号之前的部分（两侧都有就取 `r2_summary` 的），如 `InternalException`、`BinderException`；`wrong_result` 时为 None。
- **`identity.behavior`**：`wrong_result` 时是 `{"missing": 整数, "extra": 整数}`，从记录下来的结果里按下面各 oracle 的"第一种形式 / 第二种形式"算：`missing` 是第一种形式有而第二种没有的行数，`extra` 反之，按多重集算（计重数）。其他情况是空 dict。
- **None 拆成 pass 还是 invalid**，看记录下来的"查询形式"的结果：有任何一条超时是 `invalid / timeout`；否则有任何一条报错，若所有报错都满足 `oracles.errors.is_value_dependent_error` 是 `invalid / value_dependent_error`，不然是 `invalid / query_error`；全部成功才是 `pass`。
- **`Label.detail`**：始终有 `"full_query"`；fail 时加 `"candidate_kind"`、`"notes"`、`"q1"`、`"q2"`（取自 Candidate）；因报错而 invalid 时加 `"error"`（第一条报错文本）；各 oracle 另有下面写明的键。只放 JSON 原生类型。

**tlp**
- 前提：`case.predicate` 非空。满足 `oracles.tlp.tlp_applicable(case.query, case.predicate)` 走 WHERE 形态；否则 `split_grouped(case.query)` 不是 None 走分组或去重形态；都不是就 `not_applicable`。
- WHERE 形态：`oracles.tlp.TLPOracle().check(代理, case.query, case.predicate, list(case.setup), [], timeout_s=…)`。返回 Candidate 是 fail，返回 None 按公共规则拆。行为画像：第一种形式是未划分查询的结果，第二种是三个划分结果之和。
- 分组 / 去重形态：`oracles.tlp_groupby.TLPGroupByOracle().check(代理, select_list=…, from_tail=…, predicate=case.predicate, group_by=…, base_where=…, schema_sqls=list(case.setup), inserts=[], timeout_s=…)`，不传 `conjoin`（PINOLO-lite 本会话不接）。它返回 `(status, candidates)`：`HIT`、`CRASH` 是 fail（取第一个 Candidate）；`CLEAN` 是 pass；其余三种状态是 invalid，原因按公共规则从记录里判。行为画像用 `oracles.tlp_groupby.rowset` 得到的集合算：第一种形式是未划分查询的键集合，第二种是三个划分的并集。
- 只要调用过旧 oracle，`detail["form"]` 就是 `"where"`、`"groupby"` 或 `"distinct"`。
- `identity.switches` 为空。

**norec**
- 前提：`case.predicate` 非空且 `oracles.norec.norec_applicable(case.query, case.predicate)`。
- `oracles.norec.NoRECOracle().check(代理, case.query, case.predicate, list(case.setup), [], timeout_s=…)`。返回 Candidate 是 fail，None 按公共规则拆。
- 行为画像：第一种形式是逐行求值的参考计数（`SUM(CASE …)`，NULL 当 0），第二种是 `COUNT(*) … WHERE` 的计数；`missing = max(参考 − 优化, 0)`，`extra = max(优化 − 参考, 0)`。
- `identity.switches` 为空。

**plan_variant**
- 前提：无（任何能跑的查询都适用）。
- `oracles.plan_variant.PlanVariantOracle(engine=case.engine).check(代理, full, list(case.setup), [], timeout_s=…)`，传进去的查询必须就是 `full_query(case)` 返回的那个字符串。
- "查询形式"只指记录里 `sql == full` 的那些执行：第一次是基线，之后第 i 次对应 `PlanVariantOracle(...).variants` 的第 i 项。其余语句（`SET`、`RESET`、`PRAGMA`、`FORCE CHECKPOINT`）是切换开关用的，判定时一律忽略：其中有的在当前 DuckDB 上本来就会报错（如 `SET ordered_aggregate_threshold=0`）。
- 返回 Candidate 是 fail：`identity.switches = (candidate.r2_summary["variant"],)`（基线自己崩溃时没有 variant，就是空）。行为画像：第一种形式是基线结果，第二种是出现差异的那个变体的结果。
- 返回 None：基线没成功，按公共规则对基线那一条判 invalid。基线成功时，把变体执行分成"比较过的"（成功且没超时）和"跳过的"（旧 oracle 对超时、值依赖错误、guard-rail 拒绝都是跳过该变体）：比较过的不少于 1 个是 `pass`；一个都没有是 invalid，原因在有变体超时时取 `timeout`，否则取 `value_dependent_error`。
- `detail["variants_compared"]` 是比较过的个数，`detail["variants_skipped"]` 是被跳过的变体标签列表。

### 5. `evaluate`

每调用一次，账本里恰好多一条记录，pass 和 invalid 也一样。

1. 执行任何东西之前先检查参数：`oracle` 不在 `IMPLEMENTED`、引擎不支持，抛 `ValueError`；`run_id` 没有 `start_run` 过，抛 `LedgerError`（`ledger.next_seq(run_id)` 会抛）。这三种情况不留记录。
2. 调 `judge`。判定过程中抛出的任何异常都转成 `Label(y="invalid", oracle=oracle, invalid_reason="harness_error", detail={"exception": "<异常类名>: <消息>"})`，照样记账。这里需要一个宽泛的 `except Exception`，是这份说明要求的，在旁边写一行注释说明原因。
3. 组装 `ExperimentRecord`：`seq = ledger.next_seq(run_id)`，`record_id = f"{run_id}:{seq}"`，`created_at` 用 UTC 的 ISO 8601 时间，`surprise` 留 None（S6 才有惊讶公式），其余字段取自参数。
4. `ledger.append(record)`，返回这条记录。

### 6. 测试

- `framework/tests/test_surprise_oracles.py`：`split_grouped` 的接受与拒绝各若干例；`full_query` 三条分支；三个适配器各自的 pass、fail、各种 invalid；用假 runner（包一个真 `DuckDBRunner`，对选中的语句返回构造的 `QueryResult`）覆盖崩溃、一侧报错、超时、变体被跳过这些真引擎上不好触发的分支；同一输入两次判定相同；参数错误。
- `framework/tests/test_surprise_evaluate.py`：每次调用恰好一条记录、记录内容与 `judge` 一致、判定抛异常时记成 `harness_error`、参数错误不留记录、重开账本后记录还在。用 `tmp_path`。

测试要自己写，不要照抄门槛。已知会失败的用例（`metrics_small`、`inv_delim`）是从真实 bug 来的，它们的 SQL 可以从 `surprise.gates.s02_cases` 导入使用。

## 背景

1. 包名容易混：新包是 `surprise.harness.oracles`，旧包是顶层的 `oracles`。在新包里写 `from oracles.tlp import TLPOracle` 拿到的是旧包，这是对的；不要写成相对导入。
2. `is_usable_for_oracles` 会在传进去的 runner 上重新执行一遍 `setup` 并跑探测查询，所以筛查和正式判定用两个 runner，互不干扰。
3. 用例表里 `vd_partial` 这一例说明了为什么要有 `value_dependent_error`：谓词 `c <> 'x' AND CAST(c AS INTEGER) > 0` 在 TLP 的三个划分里有两个报类型转换错误、一个不报，是否报错取决于求值顺序。旧 oracle 对这种情况返回 None，新标签必须是 invalid 而不是 pass。同一个用例在 NoREC 和 plan variant 下是 pass。
4. **不要执行 `duckdb/F10_window_frame_underflow.sql` 里的语句**：其中两条会让解释器进程直接崩溃（实测，退出码 0xC0000094）。这类 bug 要等 S4 的新进程隔离才能安全地判。也不要去跑 `duckdb/`、`datafusion/` 下其他复现文件；门槛要用的已知复现都在用例表里。
5. 命令都在 `framework/` 目录下执行。CLAUDE.md 里写的 `../.venv/Scripts/python.exe` 在 worktree 里不存在，直接用 `python`，它已经指向项目解释器。
6. 这些文件在 `framework/surprise/harness/` 下，S4 之后冻结。

## 允许改动的路径

只改下面这些路径（`**` 跨目录，`*` 不跨）。审查按这个清单逐个文件核对，清单以外的任何改动都算越界。

```allow-paths
framework/surprise/harness/oracles/**
framework/surprise/harness/evaluate.py
framework/tests/test_surprise_oracles.py
framework/tests/test_surprise_evaluate.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`。
- 旧代码（`framework/surprise/` 以外）一个字都不改，包括 `framework/oracles/` 下所有文件。上一个包交付的 `contracts.py`、`constants.py`、`ledger.py` 也不改；觉得它们有问题，或者旧 oracle 的行为和这份说明写的对不上，写进报告的"未决问题"，停下。
- 不重新实现旧 oracle 的比较逻辑，不绕开旧 `check()` 自己判 fail。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败（`evaluate` 里那一处是说明要求的，除此之外不要有），不改 conftest。某个测试确实该改，就写进报告的"未决问题"，停下。
- 标签路径上不调用 LLM；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。本包不需要任何 LLM 调用。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不做本包以外的东西：不做 CVE 流水线（新进程重跑、最小化、画像），不做 φ，不接 DataFusion，不写 manifest。
- 不装、不卸任何 Python 包，不碰 worktree 之外的任何文件。
- 不要清理 `.orch/tmp`：里面的临时文件留着，清理 worktree 时会一起删掉。删除命令被权限规则拒绝之后，不要改成逐个删除再试。

## 验收命令

在 worktree 里执行，全部通过才算完成。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests                                        # 退出码 0，通过数不少于 126，再加上你新写的
python -m surprise.gates.s02 --only contracts ledger oracles evaluate    # 退出码 0，4/4
python -m surprise.gates.s01                                             # 仍是 7/7
cd ..
git status --short                                                       # 期望为空
```

`python -m surprise.gates.all` 现在会是退出码 1：`s02` 的 manifest 组属于并行的另一个包，这是预期的，在报告里照实写。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。发现门槛脚本和这份说明对不上，同样写进报告，停下，不要去改门槛。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s02-oracles

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改 / 移动自哪里）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
