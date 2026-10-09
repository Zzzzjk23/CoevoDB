角色：执行者

# 工作包 s06-vspace：理论常数、假设契约、合取语言与版本空间

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s06-vspace`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s06`（门槛提交 161f0de 之后）
- 所属会话：S6（Phase 3a：理论 T 核心），范围见 `framework/surprise/docs/SESSIONS.md` 的 S6 一节
- 依赖：`framework/surprise/harness/`（已冻结）与 `framework/surprise/features/`（S5 交付）只读不改。可以用 `surprise.features` 的 `Phi`、`Registry`、`default_registry`，`surprise.harness.contracts` 的 `Label`、`ORACLE_IDS`，`surprise.harness.cve.shape.behavior_shape`
- 后续：R、Kᵛ、P_T、惊讶、分诊、`Theory`、manifest 由下一个包 `s06-theory` 做，本包不做

## 目标

依据 `framework/surprise/docs/PLAN.md` 第 4 节契约表的"假设"行、第 5 节 Phase 3、第 6 节决策 2 与决策 3。本包交付理论层里不碰引擎的那一半：常数、假设契约的新字段、φ 字面量合取的语言、版本空间的更新规则、新家族的确定性初始化、身份判定。全部是纯函数：不连接引擎，不执行 SQL，不读写文件，结果只由参数决定。

验收以 `framework/surprise/gates/s06.py` 的五组 `constants language vspace hypothesis identity` 为准。先把 `framework/surprise/gates/s06.py` 和 `framework/surprise/gates/s06_cases.py` 读一遍：门槛用到的名字、参数、返回值都在下面写明，照写；表里的每个期望值都能由下面的规则推出来，推不出来就是你读错了规则或者表错了，后一种情况写进报告、停下。

下面所有名字都要能从 `surprise.theory` 直接导入（`from surprise import theory as T; T.reduce_conjunction(...)`）。模块怎么分由你定，建议 `theory/constants.py`、`theory/vspace.py`（第 3 节）、`theory/hypothesis.py`（第 4、6 节）、`theory/identity.py`（第 5 节）。带 `registry=None` 参数的函数，`None` 表示用 `default_registry()`。

### 1. 常数（`theory/constants.py`）

写法照 `framework/surprise/harness/constants.py`：模块级大写名字加 `as_dict()`（自动收集全部公开的大写名字，返回一个与模块脱离的 JSON 安全 dict）。九项，名字、取值、类型如下，每项上面写一行注释说明含义：

| 名字 | 取值 | 含义 |
|---|---|---|
| `P_CONFIRMED` | `0.95` | 落在某个假设的 S 里时，有效结果为失败的概率 |
| `P_PENDING` | `0.5` | 落在 S 与 G 之间时 |
| `RESIDUAL_PRIOR_FAILS` | `1.0` | 残余失败率 ρ = (未解释失败 + 1.0) / (测过 + 100.0) 的分子先验 |
| `RESIDUAL_PRIOR_TESTS` | `100.0` | 分母先验 |
| `VALIDITY_PRIOR_INVALID` | `1.0` | 无效率 Kᵛ = (无效 + 1.0) / (做过 + 10.0) 的分子先验 |
| `VALIDITY_PRIOR_TESTS` | `10.0` | 分母先验 |
| `TRIAGE_LOW_BITS` | `0.5` | 惊讶低于它：重复 / 无信息 |
| `TRIAGE_HIGH_BITS` | `2.0` | 惊讶不低于它：新家族 / 意外通过 |
| `VS_MAX_GENERAL` | `64`（int） | G 里合取个数的上限 |

本包只用到 `VS_MAX_GENERAL`，其余八项下一个包用；现在就全部写上。`from surprise.theory import constants` 要能用。不要把这些常数加进 `harness/constants.py`（已冻结）。

### 2. 假设契约的新字段（`theory/contracts.py`）

在 `Hypothesis` 现有十一个字段之后加六个带默认值的字段，别的不动（`Spec`、`TheoryEdit`、`EDIT_DECISIONS` 不改；现有字段的名字、顺序、校验不改）：

| 字段 | 默认 | 校验（不满足抛 `ValueError`） |
|---|---|---|
| `oracle` | `None` | `None` 或 `ORACLE_IDS` 里的一个 |
| `fail_kind` | `None` | `None` 或字符串 |
| `error_class` | `None` | `None` 或字符串 |
| `behavior_shape` | `None` | `None` 或字符串 |
| `contradictions` | `()` | 字符串的列表或元组，存成元组；单个字符串不行 |
| `truncated` | `False` | 必须是 `bool` |

含义：`oracle` 是假设的作用域（与 `engine` 一起）；`fail_kind`、`error_class`、`behavior_shape` 是没有开关时的身份（PLAN 决策 3）；`contradictions` 是落在 S 里却通过的实验的记录号；`truncated` 表示 G 被上限截断过。

两条兼容要求，门槛都查：S2 时期的写法（只给前十一个字段）照样能构造；S2 时期序列化出来的 dict（没有这六个键）照样能 `from_dict`。契约里 `specific`、`general` 仍然接受任意字符串：S2 的测试和门槛用的不是词表里的 id，所以**不要在契约类里按词表校验**，词表校验在第 3 节的函数里做。`surprise.theory.Hypothesis` 就是这个契约类本身（`T.Hypothesis is contracts.Hypothesis`）。

### 3. 合取语言

一个**合取**是一组特征 id，叶子、类、开放族成员都可以。φ 满足它，当且仅当每个 id 都在 `registry.closure(phi.features)` 里；所以写类名表示"其下任意一个"，空合取恒成立。没有否定：表达不了"没有某特征"。

**层根**指没有父节点的 id（现在是 `ast`、`plan`、`data`）。层根不携带条件，不进合取。

`reduce_conjunction(ids, registry=None) -> tuple[str, ...]`：约简形式。

- `ids` 是任意可迭代的 id 序列（列表、元组、集合）；传入单个字符串、或者某个元素不是字符串、或者 `registry.known()` 不认识它：`ValueError`。
- 去掉层根；去掉"是同组里另一个 id 的祖先"的 id（更具体的那个已经蕴含它）；去重；按字符串排序；返回元组。
- 幂等，结果与输入顺序无关。

`covers(conjunction, phi, registry=None) -> bool`：每个 id 都在 `registry.closure(phi.features)` 里就是 `True`。有不认识的 id：`ValueError`。只做这个集合判断，不看 φ 的层状态（层状态在第 4 节的 `position` 里处理）。

`generalize(specific, phi, registry=None) -> tuple[str, ...]`：覆盖这个正例的最小泛化，等于 `reduce_conjunction(registry.closure(specific) ∩ registry.closure(phi.features))`。效果：正例没有的特征被删掉；正例有同类的另一个值时，升到两者共同的类（`ast:set_op:except_all` 遇到带 `ast:set_op:intersect_all` 的正例，变成 `ast:set_op:all`）。

`specialize(general, specific, phi, registry=None) -> tuple[tuple[str, ...], ...]`：让 G 排除一个反例的全部最小特化。`general` 是一组合取，`specific` 是当前的 S，`phi` 是反例。

1. `S = reduce_conjunction(specific)`。如果 `covers(S, phi)`：`ValueError`（反例落在 S 里，没有哪个比 S 更一般的合取能排除它）。
2. 候选字面量集合 C：对 S 的每个字面量 s，取链 `[s] + [a for a in registry.ancestors(s) if a 不是层根]`（由近到远）。链上"不在 `registry.closure(phi.features)` 里"的元素一定是靠近 s 的一段；取这一段里最远的那个（能排除这个反例的最一般的字面量）放进 C。s 自己就在反例的闭包里时，这个 s 不出候选。
3. 对 `general` 的每个成员 g（先约简）：g 不覆盖反例，原样保留；g 覆盖反例，换成 `reduce_conjunction(g + (c,))`，C 里每个 c 一个。
4. 去重，再删掉冗余成员：成员 m 冗余，指存在另一个成员 k ≠ m，k 的每个 id 都在 `registry.closure(m)` 里（k 比 m 更一般，m 多余）。
5. 按（成员长度，成员元组）排序，返回元组的元组。

`specialize` 自己不做截断（截断在 `apply_negative` 里）。`s06_cases.py` 的 `SPECIALIZE` 表有十二个例子，其中第 5 行说明第 2 步为什么取祖先：对一条什么集合运算都没有的普通查询，候选是 `ast:set_op` 而不是 `ast:set_op:except_all`。

### 4. 假设上的操作

`Hypothesis` 是冻结的 dataclass：下面的函数都返回新对象（`dataclasses.replace`），不改传入的对象；同样的参数调两次，结果相等。假设里的 `specific` 是约简形式的合取，`general` 是按第 3 节第 5 步排好序的一组约简合取。

`position(hypothesis, phi, oracle, registry=None) -> str`，按顺序判：

1. `hypothesis.engine != phi.engine` 或 `hypothesis.oracle != oracle`：`"out_of_scope"`。
2. `hypothesis.specific` 里有某个字面量，它所在的层（id 的第一段）在 `phi.layers` 里既不是 `ok` 也不是 `fallback`：`"undetermined"`。这样的 φ 既不能证实也不能反驳这个假设。
3. `covers(hypothesis.specific, phi)`：`"confirmed"`（确认区）。
4. `hypothesis.general` 里有成员覆盖 φ：`"pending"`（待定区）。
5. 否则 `"outside"`。

`Update`：冻结 dataclass，字段 `hypothesis`、`outcome`。

`apply_positive(hypothesis, phi, record_id, registry=None) -> Update`：先算 `position(hypothesis, phi, hypothesis.oracle)`。

| 位置 | 做什么 | `outcome` |
|---|---|---|
| `confirmed` | `positives` 末尾加 `record_id` | `"duplicate"` |
| `pending` | `specific` 换成 `generalize(specific, phi)`；`general` 只留覆盖 φ 的成员；`positives` 加 `record_id` | `"generalized"` |
| 其余 | 原样返回 | 位置名本身：`"outside"`、`"undetermined"`、`"out_of_scope"` |

`apply_negative(hypothesis, phi, record_id, registry=None) -> Update`：

| 位置 | 做什么 | `outcome` |
|---|---|---|
| `confirmed` | S、G 不变；`negatives` 加 `record_id`，`contradictions` 加 `record_id` | `"contradiction"` |
| `pending` | `general` 换成 `specialize(general, specific, phi)`；成员多于 `VS_MAX_GENERAL` 时只留排序后的前 `VS_MAX_GENERAL` 个，并把 `truncated` 置为 `True`（已经是 `True` 的保持）；`negatives` 加 `record_id` | `"specialized"` |
| 其余 | 原样返回 | 位置名本身 |

往 `positives`、`negatives`、`contradictions` 里加记录号时，已经在里面的不重复加，顺序是加入的先后。落在 G 之外的例子不记进 `negatives`。

`converged(hypothesis, registry=None) -> bool`：G 约简、去冗余之后恰好只有一个成员，并且它等于 `reduce_conjunction(specific)`。

门槛的 `SEQUENCES` 表给了五条完整的序列，每一步之后的 S 和 G 都有期望值；`CAP_*` 检查上限：十四个互不相关的字面量、七个各缺一对的反例，第六个之后 G 有 64 个成员，第七个之后应有 128 个，截到按次序的前 64 个并标记。门槛还会跑 480 步随机序列，查这些不变量：S 是约简形式并覆盖每个正例；G 的每个成员是约简形式、比 S 更一般（每个 id 都在 S 的闭包里）、互不蕴含、按次序排好；没有哪个 G 成员还覆盖已经用来特化的反例；G 不会变空。

### 5. 身份判定

`identity_match(hypothesis, label) -> bool | None`："失败必须和假设的身份一致才算正例"。`label` 是 `surprise.harness.contracts.Label`；`label.y != "fail"` 抛 `ValueError`。按顺序：

1. `label.cve` 里有 `attribution`，它是 dict，`status == "ran"`，`hypothesis_id == hypothesis.hypothesis_id`，`consistent` 是 `bool`：返回 `consistent`。这是 harness 第 2 档对这个假设做过的归属测试，以它为准。
2. 否则，`hypothesis.interventions` 非空：`label.cve` 里的 `profile` 是 dict 且 `status == "ran"` 时，返回 `set(profile["fix_set"]) == set(hypothesis.interventions)`；没有这样的画像，返回 `None`（不知道）。
3. 否则（没有开关的假设）：返回 `hypothesis.fail_kind == label.fail_kind and hypothesis.error_class == label.identity.error_class and hypothesis.behavior_shape == behavior_shape(label.identity.behavior)`，`behavior_shape` 用 `surprise.harness.cve.shape` 里的那个，不要自己再写一个。

针对别的假设做的归属测试（`hypothesis_id` 不同）对这个假设什么都不说明，走第 2、3 步。`s06_cases.py` 的 `IDENTITY` 表有十七个例子。

### 6. 新家族与归属请求

`new_family(hypothesis_id, phi, label, record_id, *, negatives=(), source="deterministic", registry=None) -> Hypothesis`：从一条带第 3 档画像的失败确定性地建立假设（SESSIONS："I、ΔP、V 取自 CVE 画像；无开关引擎用错误类别 + 行为画像"）。

- `label.y != "fail"`，或者 `label.cve["profile"]` 不是 `status == "ran"` 的 dict：`ValueError`。
- 字段：`engine = phi.engine`；`oracle = label.oracle`；`interventions = tuple(profile["fix_set"])`；`plan_delta = tuple(profile["plan_diff"])`；`versions = {"ladder": profile["version_ladder"], "fix_kind": profile["fix_kind"], "witness_switches": list(profile["witness_switches"])}`；`fail_kind = label.fail_kind`；`error_class = label.identity.error_class`；`behavior_shape = behavior_shape(label.identity.behavior)`；`specific = reduce_conjunction(phi.features)`；`general = ((),)`（只有一个空合取）；`positives = (record_id,)`；`negatives = ()`；`contradictions = ()`；`truncated = False`；`source` 取参数；`status = "active"`。
- `negatives` 是 `(phi, record_id)` 对的序列：此前见过的通过。建好之后按顺序对每一对调用 `apply_negative`，取返回的假设接着用。于是 G 一出生就被已有的通过收紧，已经在 G 之外的不留痕迹。

`attribution_request(hypothesis) -> dict`：交给 harness 第 2 档的 mapping（`certify(..., hypothesis=...)`）。`interventions` 非空时恰好三个键：`hypothesis_id`、`engine`、`interventions`（list）。为空时再加三个键 `fail_kind`、`error_class`、`behavior_shape`，值取假设上的（可以是 `None`）。门槛用 `surprise.harness.cve.hypothesis.parse_hypothesis` 检查它能被冻结的 harness 接受。

### 7. 测试

新增 `framework/tests/test_surprise_s06_*.py`（可以拆成几个文件）。覆盖上面每一条规则，例子自己写，不要 import `surprise.gates`。至少包括：约简的每一步与每种拒绝；`generalize` 删特征、升类、连升两级；`specialize` 的候选取祖先、已排除的成员不动、冗余成员被删、排序、反例在 S 里时报错；S 里本身就有类一级字面量时的特化；开放族成员（`plan:某算子`）作字面量；`position` 的五种结果；`apply_positive`、`apply_negative` 每个位置的结果与记录号的去重；上限与 `truncated`；`identity_match` 的三步与各自的边界；`new_family` 的每个字段、两种拒绝、回放；契约的新字段默认值、校验、新旧 dict 的往返；两种导入顺序（见背景第 1 条）。

## 背景

1. **导入环，必须处理。** `surprise/features/spec.py` 在模块顶层 `from surprise.theory.contracts import Spec`，而理论层现在要用特征层。如果 `surprise/theory/__init__.py`（或它导入的模块）在顶层写 `from surprise.features import default_registry`，那么"先 `import surprise.features`"这个顺序会在特征包初始化到一半时回头找还没绑定的名字，直接 `ImportError`。做法：理论层的模块顶层只从特征层的**子模块**导入（`from surprise.features.registry import default_registry`、`from surprise.features.phi import Phi`），不要写 `from surprise.features import …`。门槛的 `constants` 组在四个新进程里按不同顺序导入，全部要成功。`surprise.theory.contracts` 仍然只依赖 `surprise.harness.contracts`，不要让它导入特征层。
2. 词表里的层级（`default_registry()`）：`ast:set_op:except_all` 的祖先是 `ast:set_op:all`、`ast:set_op`、`ast`；`data:setop:left_has_dups` 的祖先是 `data:setop`、`data`；`plan:HashJoinExec` 这类开放族成员的父节点就是层根 `plan`，所以它的链上只有它自己。
3. `Label.cve` 是 CVE 流水线填的 dict。归属测试跑过时 `cve["attribution"]` 形如 `{"status": "ran", "reason": None, "hypothesis_id": "h1", "method": "profile", "consistent": False, "executions": 0}`，没跑时是 `{"status": "skipped", "reason": "..."}`。第 3 档画像跑过时 `cve["profile"]` 形如 `{"status": "ran", "reason": None, "fix_kind": "non_optimizer", "fix_set": [], "plan_diff": [], "version_ladder": "longstanding", "witness_switches": [], "error_class": None, "behavior_shape": "missing_only", "executions": 13}`。读它们的时候用 `.get`，键不存在或类型不对都按"没有"处理，不要抛别的异常。
4. `s06_cases.py` 的 `PHI` 表是 DataFusion 上实测的 φ：`x1` 是 DF-A（`EXCEPT ALL`，左侧有重复行和 NULL），`x3` 去掉了左侧的重复行，`x4` 是 DF-B（`INTERSECT ALL`）。框架文档里的案例是：手写的假设 S = (`ast:set_op:except_all`, `data:setop:left_has_dups`)、G = (空合取)；`x3` 通过，`data:setop:left_has_dups` 进入 G；`x4` 失败但身份不同，对这个假设是反例，G 变成与 S 相同。这就是 `SEQUENCES["hand_written_h2"]` 的前两步。
5. 已冻结的 harness 不 import 理论层；这一点保持，本包也不改 harness。

## 允许改动的路径

只改下面这些路径（`**` 跨目录，`*` 不跨）。审查按这个清单逐个文件核对，清单以外的任何改动都算越界。

```allow-paths
framework/surprise/theory/**
framework/tests/test_surprise_s06_*.py
framework/tests/test_surprise_contracts.py
```

`framework/tests/test_surprise_contracts.py` 只在一种情况下可以动：`Hypothesis` 多了六个字段，使其中某条精确断言（比如对 `to_dict()` 键集合的断言）失败。这时只把那条断言更新成包含新字段的精确值，并在报告的"与说明的偏差"里逐条写出改前和改后。新字段都有默认值，预计这个文件不需要改；不需要改就不要碰它。

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`。
- 不改 `framework/surprise/harness/`（已冻结）与 `framework/surprise/features/`。
- 旧代码（`framework/surprise/` 以外）本包不碰，理论层也不 import 它们（`llm`、`agents`、`evolution`、`coevo` 等）。
- 本包不做 R、Kᵛ、P_T、惊讶、分诊、`Theory`、manifest，也不做持久化、回滚、Hunter、LLM 角色。
- 本包不连接任何引擎、不执行 SQL、不 import `duckdb`、`datafusion`、`sqlglot`（经由 `surprise.features` 间接加载的不算）。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。某个已有测试确实该改（上面说的那一种情况之外），写进报告的"未决问题"，停下。
- 标签路径上不调用 LLM；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。本包不需要任何 LLM 调用。
- 不安装、不升级任何依赖，不动 `.venv`、`.venvs/`、`.orch/pg16/`。
- 不清理 `.orch/tmp`：临时文件留着不管，包括你自己建的（提交信息用 `git commit -m`）。不建任何指向 worktree 之外的链接或目录联接。被权限规则拒绝的操作不要换写法重试。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests                                                # 0 failed，通过数不少于 367，skip 不多于 3
python -m surprise.gates.s01                                                     # 退出码 0
python -m surprise.gates.s02                                                     # 退出码 0
python -m surprise.gates.s03                                                     # 退出码 0
python -m surprise.gates.s04                                                     # 退出码 0，约 4 分钟
python -m surprise.gates.s05                                                     # 退出码 0，约 1 分钟
python -m surprise.gates.s06 --only constants language vspace hypothesis identity   # 退出码 0，几秒
```

`python -m surprise.gates.all` 在本包结束时仍会报 s06 FAIL：其余七组属于下一个包，这是预期的。s04 的 `freeze` 组通过说明你没有动冻结的 harness。不要直接跑不带路径的 `pytest`。开发时先反复跑最后一条和你自己的测试（都只要几秒），前面几条收尾时跑一遍即可。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。认为门槛或用例表的某个期望不对，写明是哪一行、按规则你推出的值是什么，停下。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s06-vspace

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
