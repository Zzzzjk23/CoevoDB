角色：执行者

# 工作包 s05-vocab：φ 的词表、注册表、容器、规格核对与单元投影

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s05-vocab`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s05`（门槛提交 067a2fa 之后）
- 所属会话：S5（Phase 2：共同语言 φ），范围见 `framework/surprise/docs/SESSIONS.md` 的 S5 一节
- 依赖：`framework/surprise/harness/` 已冻结，只读不改；可以读 `surprise.harness.contracts`（`ORACLE_IDS`、`SqlCase`）与 `surprise.theory.contracts`（`Spec`）
- 后续：语句层提取由 `s05-ast` 做，计划层、数据层、组合入口与命令行的其余部分由 `s05-dynamic` 做。本包只做不碰引擎、不解析 SQL 的那一半

## 目标

依据 `framework/surprise/docs/PLAN.md` 第 4 节契约表的"规格"行、第 5 节 Phase 2、第 6 节决策 2 与决策 4。本包交付 φ 的共同语言本身：词表与类层级、注册表、φ 容器、规格核对器、单元投影。全部是纯函数，只用标准库。验收以 `framework/surprise/gates/s05.py` 的三组 `vocab spec units` 为准；门槛用到的名字和字段都在下面写明，照写。

词表契约在 `framework/surprise/gates/s05_cases.py`：先把这个文件读一遍。`CORE_VOCAB` 规定基础词表里必须有的 166 项（id、种类、父类、含义），`UNIT_PROBES`、`SPEC_PROBES` 是本包两个函数的例子。特征包不许 import `surprise.gates`：词表照抄进你的代码。

### 1. 词表与注册表（`features/vocabulary.py`、`features/registry.py`）

特征 id 的写法：`层:名[:值]`，层是 `ast`、`plan`、`data` 之一，每一段只含字母、数字、下划线。种类三种：

- `class`：层级的内部节点，不会出现在 φ 里；
- `leaf`：提取出来的特征；
- `family`：开放族。族 id 后面再加一段就是它的一个叶子（`plan:HASH_JOIN`、`plan:HashJoinExec`、`ast:fn:upper`），不用逐个登记。只多一段才算：`plan:a:b` 不是 `plan` 的成员。

`FeatureDef` 是冻结 dataclass，字段：`feature_id`、`kind`、`parent`（根为 `None`）、`layer`、`description`、`source`（基础词表为 `"base"`）、`definition`（基础词表为 `None`）、`accepted`（基础词表为 `True`）、`acceptance`（基础词表为 `None`）。带 `to_dict()` 与 `from_dict()`。

基础词表必须包含 `CORE_VOCAB` 的每一项，`kind` 与 `parent` 一致，`description` 自己写（一句话，说清什么时候成立）。可以再加别的叶子或类，但加的每一项也要守上面的写法并有描述。

`Registry` 与 `default_registry()`：

- `default_registry()` 每次返回一个新的、只含基础词表的 `Registry`；在一个注册表上登记不影响另一个。
- `known(feature_id) -> bool`：显式登记的 id，或某个族的成员。
- `get(feature_id) -> FeatureDef`：显式登记的原样返回；族成员返回一个合成的定义（`kind="leaf"`、`parent` 为族 id、`source="base"`、`accepted=True`）；其余抛 `KeyError`。
- `ids() -> tuple[str, ...]`：全部显式登记的 id，排好序。
- `layer(feature_id)`、`parent(feature_id)`、`ancestors(feature_id)`（由近到远的元组）、`children(class_id)`（直接子节点，排好序）。
- `siblings(feature_id)`：与它同一个父类的其他显式叶子，排好序，不含它自己；族成员的同类为空元组。
- `closure(features) -> frozenset[str]`：这些特征加上各自的全部祖先。
- `register(definition)`：登记一个发明的特征。下面任何一条不满足都抛 `ValueError`：id 写法合法且尚未被认识（包括不能是族成员）；`kind == "leaf"`；`source` 非空且不是 `"base"`；`layer` 与 id 的第一段一致；`parent` 是同一层里已登记的 `class`；`definition` 是 `{"kind": "regex", "pattern": <能编译的正则>}`，本会话只支持这一种、只支持 `ast` 层；`accepted` 为 `False` 且 `acceptance` 为 `None`。
- `accept(feature_id, acceptance)`：把一个发明的特征标为已验收，`acceptance` 是非空的 JSON 安全 dict（验收结果），原样保存；对基础特征或不认识的 id 抛 `KeyError` 或 `ValueError`。
- `digest() -> str`：全部显式定义的 sha256 十六进制摘要（按 id 排序、每项 `to_dict()` 用排序键的规范 JSON）。同一份词表在任何进程里摘要相同；登记或验收一个特征后摘要改变。
- `save(path)`：把发明的特征写成 UTF-8 JSON 文件；`Registry.load(path)`（类方法）返回基础词表加文件里的发明特征，`accepted` 与 `acceptance` 原样恢复。

这是给 S10 的词汇发明者预留的接口：来源写在 `source`（如 `"llm:vocabulary_inventor:<编号>"`），验收结果写在 `acceptance`。本包不调用任何 LLM。

### 2. φ 容器（`features/phi.py`）

- `Phi`：冻结 dataclass，字段 `engine`（非空字符串）、`features`（排好序、去重的叶子 id 元组）、`layers`（dict，键恰好是 `ast`、`plan`、`data`）、`vocab`（词表摘要）。`to_dict()` 的键恰好是 `schema`（值为 1）、`engine`、`features`、`layers`、`vocab`；`Phi.from_dict()` 还原出相等的对象。φ 里不放任何随运行变化的东西（没有耗时、路径、报错文本）。
- 层的状态：`ast` 只能是 `ok` 或 `fallback`；`plan`、`data` 只能是 `ok`、`unavailable`（试了但取不到）或 `skipped`（没让算）。
- `make_phi(engine, features, layers, registry=None) -> Phi`：校验后构造，`vocab` 取 `registry.digest()`（`registry` 为 `None` 时用 `default_registry()`）。抛 `ValueError` 的情况：有不认识的特征；有 class 或 family 混在特征里；有未验收的发明特征；`layers` 的键或取值不对；某个特征所在的层状态不是 `ok`（`ast` 层 `fallback` 也算可用）。

### 3. 规格核对（`features/spec.py`）

`check_spec(phi, spec, registry=None) -> SpecCheck`，`spec` 是 `surprise.theory.contracts.Spec`（按属性读 `engine`、`required`、`forbidden`、`data_properties`，不要改 `theory/contracts.py`）。`SpecCheck` 是冻结 dataclass：`ok`、`engine_ok`、`missing`、`forbidden`、`undetermined`，后三个是排好序的元组。

规则：

- `spec.required`、`spec.forbidden` 里可以是任何认识的 id（叶子、类、族、族成员）；`spec.data_properties` 里必须是 `data` 层的 id。出现不认识的 id，或 `data_properties` 里有别的层的 id：`ValueError`。
- 必须项是 `required` 加 `data_properties`。一个 id 在 `registry.closure(phi.features)` 里就算满足（所以写类名表示"其下任意一个"）。
- 一层"算出来了"指它的状态是 `ok` 或 `fallback`。某个必须项不在闭包里：它所在的层算出来了，记入 `missing`；没算出来，记入 `undetermined`。
- 某个禁止项在闭包里，记入 `forbidden`；不在闭包里但它所在的层没算出来，记入 `undetermined`。
- `engine_ok` 是 `spec.engine == phi.engine`。`ok` 当且仅当 `engine_ok` 且三个元组都为空。

### 4. 单元投影（`features/units.py`）

`unit_parts(phi, registry=None) -> tuple[str, str, str]` 返回（主构造，计划算子类，数据性质类）；`unit_of(phi, oracle, registry=None) -> str` 返回 `"引擎|oracle|主构造|计划算子类|数据性质类"`。`oracle` 不在 `surprise.harness.contracts.ORACLE_IDS` 里抛 `ValueError`。

主构造：在 φ 的闭包上按下表从上到下取第一个成立的。

| 顺序 | 取值 | 条件（闭包里有） |
|---|---|---|
| 1 | `dml` | `ast:stmt:merge`、`ast:stmt:insert`、`ast:stmt:update`、`ast:stmt:delete` 之一 |
| 2 | `set_op_all` | `ast:set_op:all` |
| 3 | `set_op` | `ast:set_op` |
| 4 | `window` | `ast:window` |
| 5 | `correlated_subquery` | `ast:subquery_trait:correlated` |
| 6 | `subquery` | `ast:subquery` |
| 7 | `asof_join` | `ast:join:asof` |
| 8 | `outer_join` | `ast:join:left`、`ast:join:right`、`ast:join:full` 之一 |
| 9 | `join` | `ast:join` |
| 10 | `aggregate` | `ast:agg` 或 `ast:group` |
| 11 | `distinct` | `ast:clause:distinct` |
| 12 | `plain` | 其余 |

计划算子类：`layers["plan"]` 不是 `ok` 时为 `none`。否则看 φ 里全部 `plan:` 特征的算子名（转成大写），按下表从上到下，只要有一个算子名满足就取该类。

| 顺序 | 取值 | 算子名里含有 |
|---|---|---|
| 1 | `asof_join` | `ASOF` |
| 2 | `delim_join` | `DELIM_JOIN` |
| 3 | `window` | `WINDOW` |
| 4 | `join` | `JOIN` 或 `CROSS_PRODUCT` |
| 5 | `union` | `UNION` 或 `RECURSIVE` |
| 6 | `aggregate` | `GROUP_BY` 或 `AGGREGATE` |
| 7 | `sort` | `ORDER_BY`、`SORT` 或 `TOP_N` |
| 8 | `scan` | 其余，包括一个算子都没有 |

数据性质类：`layers["data"]` 不是 `ok` 时为 `unknown`。否则按顺序取第一个成立的：`dups`（`data:table:dup_rows`、`data:setop:left_has_dups`、`data:setop:right_has_dups` 之一）；`nulls`（`data:table:has_null`、`data:setop:left_has_null`、`data:setop:right_has_null` 之一）；`empty`（`data:table:empty`）；`extreme`（`data:value:extreme_number` 或 `data:value:non_finite`）；`plain`。

### 5. 命令行与导出

- `python -m surprise.features vocab`（`features/__main__.py`）：打印一行，内容是基础词表的摘要和显式条目数。别的子命令后面的包再加，现在不要写。
- `surprise.features` 导出：`FeatureDef`、`Registry`、`default_registry`、`Phi`、`make_phi`、`check_spec`、`SpecCheck`、`unit_of`、`unit_parts`。

### 6. 测试

新增 `framework/tests/test_surprise_s05_vocab.py`（可以拆成多个 `test_surprise_s05_*.py`）。覆盖：词表每一项的种类与父类、族成员、祖先与同类与闭包、登记的每一条拒绝理由、验收、存取往返、摘要稳定与变化、φ 的校验与往返、规格核对的每条规则（含层没算出来的两种情况）、单元三维各自的优先级。

## 背景

- `data:setop:left_has_dups` 这类特征说的是集合运算左输入的性质，不是表的性质；它在 S6 的 DF-A 案例里要进入假设的边界。本包只管它在词表里的位置。
- DF-A（`EXCEPT ALL`）与 DF-B（`INTERSECT ALL`）的 φ 只差一个叶子，两者是 `ast:set_op:all` 下的同类；它们的单元相同。`UNIT_PROBES` 里各族的期望来自实测的默认计划，例如 F2 的默认计划里没有 WINDOW 算子（被改写成了 HASH_JOIN），所以它的计划算子类是 `join`。
- 旧的 `framework/coverage/features.py` 是用正则拼的三维"格子"，可以看它列了哪些语法点，但不要 import 它，也不要照它的 id 命名。

## 允许改动的路径

只改下面这些路径（`**` 跨目录，`*` 不跨）。审查按这个清单逐个文件核对，清单以外的任何改动都算越界。

```allow-paths
framework/surprise/features/__init__.py
framework/surprise/features/__main__.py
framework/surprise/features/vocabulary.py
framework/surprise/features/registry.py
framework/surprise/features/phi.py
framework/surprise/features/spec.py
framework/surprise/features/units.py
framework/tests/test_surprise_s05_*.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`。
- 不改 `framework/surprise/harness/`（已冻结）与 `framework/surprise/theory/`。
- 旧代码（`framework/surprise/` 以外）本包不碰。
- 本包不解析 SQL、不连接任何引擎、不 import `sqlglot`、`duckdb`、`datafusion`：那是后两个包的事。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。某个已有测试确实该改，就写进报告的"未决问题"，停下。
- 标签路径上不调用 LLM；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。本包不需要任何 LLM 调用。
- 不安装、不升级任何依赖，不动 `.venv`、`.venvs/`、`.orch/pg16/`。
- 不清理 `.orch/tmp`：临时文件留着不管，包括你自己建的（提交信息用 `git commit -m`）。不建任何指向 worktree 之外的链接或目录联接。被权限规则拒绝的操作不要换写法重试。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不做理论 T、版本空间、Hunter、LLM 角色。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests                       # 0 failed，通过数不少于 275，skip 不多于 3
python -m surprise.gates.s01                            # 退出码 0
python -m surprise.gates.s02                            # 退出码 0
python -m surprise.gates.s03                            # 退出码 0
python -m surprise.gates.s04                            # 退出码 0，约 4 分钟
python -m surprise.gates.s05 --only vocab spec units    # 退出码 0
```

`python -m surprise.gates.all` 在本包结束时仍会报 s05 FAIL：其余六组属于后面两个包，这是预期的。不要直接跑不带路径的 `pytest`。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。认为门槛或契约表的某个期望不对，写明是哪一行、为什么，停下。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s05-vocab

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
