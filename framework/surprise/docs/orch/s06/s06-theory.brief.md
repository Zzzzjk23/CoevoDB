角色：执行者

# 工作包 s06-theory：R、Kᵛ、预测与惊讶、六类分诊、Theory 与 manifest

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s06-theory`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s06`（`s06-vspace` 合并之后，c4995fd）
- 所属会话：S6（Phase 3a：理论 T 核心），范围见 `framework/surprise/docs/SESSIONS.md` 的 S6 一节
- 依赖：上一个包 `s06-vspace` 已经合并，直接用它在 `surprise.theory` 里的东西：`constants`、`Hypothesis`、`reduce_conjunction`、`covers`、`position`、`apply_positive`、`apply_negative`、`identity_match`、`new_family`、`attribution_request`。先读 `framework/surprise/theory/` 下已有的代码。`framework/surprise/harness/`（已冻结）与 `framework/surprise/features/` 只读不改
- 本包做完，S6 的门槛十二组应当全部通过

## 目标

依据 `framework/surprise/docs/PLAN.md` 第 4 节契约表、第 5 节 Phase 3、第 6 节决策 8。理论 T = (H, R, Kᵛ)：H 是假设集合（上一个包），本包交付残余模型 R、有效性模型 Kᵛ、预测 P_T 与惊讶、六类分诊、把它们合在一起的 `Theory`，以及把理论常数写进 run manifest 的办法。除第 6 节的 manifest 要读源文件算哈希之外，全部是纯逻辑：不连接引擎，不执行 SQL，同样的输入序列得到同样的状态。

验收以 `framework/surprise/gates/s06.py` 的七组 `residual validity predict triage theory manifest walkthrough` 为准（另外五组上一个包已经通过，必须保持通过）。先把 `gates/s06.py` 的这七个 `check_*` 函数和 `gates/s06_cases.py` 读一遍：门槛用到的名字、参数、返回值都在下面写明，照写。

下面所有名字都要能从 `surprise.theory` 直接导入。模块怎么分由你定，建议 `theory/residual.py`、`theory/validity.py`、`theory/predict.py`（预测、惊讶、分诊）、`theory/theory.py`、`theory/manifest.py`、`theory/__main__.py`。常数一律从 `surprise.theory.constants` 读，不要在别处再写一遍数字。

框架文档里的原话，本包照它实现：

- 预测：`P_T(fail | x) = (1 − Kᵛ(x)) × [在某个 h 的确认区内约 0.95；在待定区约 0.5；否则取 ρ_c]`。
- R 是残余模型，记录没被任何假设覆盖的单元测了多少次、出过几次未解释的失败，给出残余失败率 ρ_c。Kᵛ 是有效性模型，估计某类实验在某个 oracle 下无效的概率。
- 分诊表：未探索区失败约 6.6 比特，新家族；确认区通过约 4.3，意外通过；待定区任一结果约 1.0，边界移动；确认区失败约 0.07，重复；未探索区通过约 0.01，无信息，只更新 R；无效不计惊讶，只进 Kᵛ，不碰 H 和 R。

### 1. 残余模型 R（`Residual`）

按单元（`surprise.features.units.unit_of(phi, oracle)` 给出的字符串）计数。

- `Residual()`：空的。
- `observe(unit, y)`：`y` 只能是 `"pass"` 或 `"fail"`，`unit` 是非空字符串，否则 `ValueError` 且不计数。该单元"测过"加一；`fail` 时"未解释失败"再加一。
- `counts(unit) -> (tested, unexplained)`：没见过的单元是 `(0, 0)`。
- `rate(unit) -> float`：`(unexplained + RESIDUAL_PRIOR_FAILS) / (tested + RESIDUAL_PRIOR_TESTS)`。没测过的单元是 0.01；永远严格在 0 与 1 之间。
- `to_dict()`：`{单元: {"tested": n, "unexplained": k}}`，只含见过的单元，按单元名排序。`Residual.from_dict(data)`（类方法）还原出独立的对象；`data` 不是 dict、某一行的键不是恰好这两个、计数不是非负整数、或者 `unexplained > tested`：`ValueError`。

### 2. 有效性模型 Kᵛ（`Validity`）与实验类

`experiment_class(phi, registry=None) -> str`：`f"{phi.engine}|{主构造}"`，主构造是 `surprise.features.units.unit_parts(phi, registry)[0]`。它只依赖语句层，所以没跑起来的实验（只有 ast 层的 φ）也有实验类。

- `Validity()`：空的。
- `observe(experiment_class, oracle, y, invalid_reason=None)`：`oracle` 必须在 `ORACLE_IDS` 里，`y` 必须在 `LABELS` 里，`experiment_class` 是非空字符串；`y == "invalid"` 时必须给 `invalid_reason`，别的标签不许给。任何一条不满足：`ValueError` 且不计数。该（实验类，oracle）"做过"加一；无效时"无效"加一，并按 `invalid_reason` 分开记数。
- `counts(experiment_class, oracle) -> (tested, invalid)`；`reasons(experiment_class, oracle) -> dict`（来源 → 次数，按来源名排序；`not_applicable` 就这样与别的来源分开）。
- `rate(experiment_class, oracle) -> float`：`(invalid + VALIDITY_PRIOR_INVALID) / (tested + VALIDITY_PRIOR_TESTS)`。没做过的是 0.1。
- `to_dict()`：`{实验类: {oracle: {"tested": n, "invalid": k, "reasons": {来源: 次数}}}}`，各级按键排序。`Validity.from_dict(data)` 还原；结构不对或 `reasons` 的合计不等于 `invalid`：`ValueError`。

### 3. 预测与惊讶

`ZONES = ("confirmed", "pending", "unexplored")`。

`Prediction`：冻结 dataclass，字段依次为 `engine`、`oracle`、`unit`、`experiment_class`、`zone`、`hypothesis_id`（决定这个区的假设；未探索区为 `None`）、`confirmed`（φ 落在其确认区的全部假设编号，元组）、`pending`（落在其待定区的，元组）、`p_fail_valid`（结果有效时为失败的概率）、`p_invalid`（Kᵛ）。另有：

- 属性 `p_fail = (1 − p_invalid) × p_fail_valid`（文档里的 `P_T(fail | x)`）与 `p_pass = (1 − p_invalid) × (1 − p_fail_valid)`；三者相加为 1。
- 方法 `surprise(y)`，等于 `surprise_bits(self.p_fail_valid, y)`。
- `to_dict()`：上面十个字段加 `p_fail`、`p_pass`，元组写成 list，JSON 安全。

`surprise_bits(p_fail_valid, y) -> float | None`：`y == "invalid"` 返回 `None`（无效不计惊讶）；`fail` 返回 `−log₂(p_fail_valid)`；`pass` 返回 `−log₂(1 − p_fail_valid)`。`y` 不在 `LABELS` 里，或者 `p_fail_valid` 不是严格在 0 与 1 之间的数（`bool` 不算数）：`ValueError`。惊讶是对有效结果、以"有效"为条件算的，Kᵛ 不乘进去：这样文档的五个量级正好是 `−log₂ 0.01 ≈ 6.64`、`−log₂ 0.05 ≈ 4.32`、`−log₂ 0.5 = 1`、`−log₂ 0.95 ≈ 0.074`、`−log₂ 0.99 ≈ 0.0145`。

### 4. 六类分诊

`TRIAGE_KINDS = ("new_family", "unexpected_pass", "boundary_move", "duplicate", "no_information", "invalid")`。

`triage(y, bits) -> str`，按惊讶的大小分：

| 条件 | 结果 |
|---|---|
| `y == "invalid"`（此时 `bits` 必须是 `None`） | `"invalid"` |
| `bits >= TRIAGE_HIGH_BITS` | 失败 `"new_family"`，通过 `"unexpected_pass"` |
| `TRIAGE_LOW_BITS <= bits < TRIAGE_HIGH_BITS` | `"boundary_move"` |
| `bits < TRIAGE_LOW_BITS` | 失败 `"duplicate"`，通过 `"no_information"` |

`ValueError`：`y` 不在 `LABELS` 里；无效却给了 `bits`；有效而 `bits` 是 `None`、不是数（`bool` 与字符串不算数）、为负、NaN 或无穷大。两个阈值都归上面那一档（`bits == 2.0` 是新家族，`bits == 0.5` 是边界移动）。0.95 与 0.5 固定时，这张表在确认区、待定区与文档的"位置与结果"表完全一致；未探索区的 ρ_c 漂高之后，分诊跟着惊讶走，不跟着位置走（门槛的 `theory` 组有四个这样的例子）。

### 5. `Theory`

`Theory(registry=None)`：空的理论。属性与方法：

- `residual`（一个 `Residual`）、`validity`（一个 `Validity`）：公开属性，调用方可以直接 `theory.residual.observe(...)`。
- `hypotheses`：全部假设的元组，按建立的先后；`get(hypothesis_id)`：没有抛 `KeyError`。
- `put(hypothesis)`：放进一个假设（手写的、或者把已有的换掉）。校验，不过抛 `ValueError`：参数是 `Hypothesis`；`hypothesis_id` 与 `engine` 非空；`oracle` 在 `ORACLE_IDS` 里（不能是 `None`）；`specific` 与 `general` 里的 id 词表都认识；`general` 的每个成员约简之后比 S 更一般（每个 id 都在 `registry.closure(specific)` 里）。存进去的是规范形式：`specific` 约简，`general` 的成员各自约简、去重、去掉被别的成员蕴含的、按（长度，元组）排序。编号已存在时替换，位置不变；否则排在最后。
- `predict(phi, oracle) -> Prediction`：`phi` 必须是 `Phi` 且 `phi.vocab == registry.digest()`，`oracle` 在 `ORACLE_IDS` 里，否则 `ValueError`。对每个假设算 `position(h, phi, oracle)`：`confirmed` 的进 `confirmed` 列表，`pending` 的进 `pending` 列表（都按建立的先后），别的位置（`outside`、`undetermined`、`out_of_scope`）不算。有确认的：`zone = "confirmed"`，`hypothesis_id` 取第一个，`p_fail_valid = P_CONFIRMED`；否则有待定的：`zone = "pending"`，取第一个，`P_PENDING`；否则 `zone = "unexplored"`，`hypothesis_id = None`，`p_fail_valid = residual.rate(unit)`。`p_invalid = validity.rate(experiment_class, oracle)`。`predict` 不改任何状态。
- `observe(phi, label, record_id, *, prediction=None) -> Observation`：学习一条实验结果，见下。
- `to_dict()`、`Theory.from_dict(data, registry=None)`、`version`：见下。

`Observation`：冻结 dataclass，字段 `prediction`、`y`、`surprise`（无效为 `None`）、`triage`、`effects`（`(hypothesis_id, outcome)` 对的元组，按假设建立的先后）、`opened`（这一步建立的新假设编号，没有为 `None`）、`unexplained`（`bool`）。`to_dict()` JSON 安全，`prediction` 用它自己的 `to_dict()`，`effects` 写成 list 的 list。

**`observe` 的步骤**（oracle 取 `label.oracle`）：

1. 校验：`phi` 是 `Phi` 且词表摘要一致；`label` 是 `Label`；`record_id` 是非空字符串；给了 `prediction` 的话它必须是 `Prediction` 且 `(prediction.engine, prediction.oracle) == (phi.engine, label.oracle)`。不过抛 `ValueError`，并且不改任何状态。没给 `prediction` 就在这里、任何更新之前调用 `self.predict(phi, label.oracle)`。
2. `validity.observe(prediction.experiment_class, oracle, label.y, label.invalid_reason)`：每一条实验都进 Kᵛ。
3. 标签无效：到此为止，返回 `surprise=None`、`triage="invalid"`、`effects=()`、`opened=None`、`unexplained=False`。H、R 与记住的通过都不动。
4. `surprise = surprise_bits(prediction.p_fail_valid, y)`；`triage = triage(y, surprise)`。
5. 按建立的先后，对这一步开始时已有的每个假设 h 算 `position(h, phi, oracle)`。`out_of_scope` 与 `undetermined` 跳过。其余：
   - `y == "pass"`：`outside` 跳过；`confirmed` 或 `pending` 调 `apply_negative`，换成返回的假设，记 `(h.hypothesis_id, outcome)`。
   - `y == "fail"`：先算 `identity_match(h, label)`。
     - `None`：位置不是 `outside` 时记 `(编号, "unknown_identity")`，假设不变；`outside` 时跳过。
     - `True`：`outside` 时记 `(编号, "outside")`，假设不变（身份对得上但落在边界之外，不吸收）；`confirmed` 或 `pending` 调 `apply_positive`，换成返回的假设，记下 outcome，并把这条失败标为"已被吸收"。
     - `False`：`outside` 跳过；`confirmed` 或 `pending` 调 `apply_negative`（身份不一致的失败对这个假设是反例），换成返回的假设，记下 outcome。
6. `y == "fail"` 而没有被任何假设吸收：
   - `label.cve["profile"]` 是 `status == "ran"` 的 dict：建立新家族。编号取 `f"h{n}"`，n 从 1 起的计数器，跳过已被占用的编号，用过之后加一，不回收。`new_family(编号, phi, label, record_id, negatives=此前在同一（引擎，oracle）下记住的通过)`，排在最后，`opened` 取这个编号。
   - 否则：`unexplained = True`，`residual.observe(prediction.unit, "fail")`。
7. `y == "pass"`：`prediction.zone == "unexplored"` 时 `residual.observe(prediction.unit, "pass")`（确认区、待定区的通过不进 R）。然后把 `(phi, record_id)` 记进这个（引擎，oracle）的"见过的通过"里，φ 相同的只记第一次。
8. 返回 `Observation`。

注意第 6 步与第 7 步用的是第 1 步的 `prediction`（执行之前的预测），不是更新之后重新算的。

**状态**：`to_dict()` 的键恰好是这七个：`schema`（值为 1）、`vocab`（词表摘要）、`hypotheses`（各假设的 `to_dict()`，按建立的先后）、`residual`、`validity`（各自的 `to_dict()`）、`passes`（`{"引擎|oracle": [{"phi": phi.to_dict(), "record_id": 记录号}, …]}`，范围按键排序，范围内按第一次见到的先后）、`next_id`（编号计数器的下一个 n）。JSON 安全。同样的历史得到相等的 dict。

`Theory.from_dict(data, registry=None)`：还原出一个接着用与原来毫无区别的理论（门槛会在还原前后的两个对象上接着喂同样的实验，要求观察结果与最终状态都相等）。`data` 不是 dict、键不是恰好这七个、`schema` 不是 1、`vocab` 与词表摘要不一致：`ValueError`。

`version`：属性，`"T-"` 加上 `to_dict()` 的规范 JSON（`sort_keys=True, separators=(",", ":"), ensure_ascii=False`，UTF-8）的 sha256 十六进制前 12 位。它用作 `ExperimentRecord.theory_version`：状态一变它就变，同样的状态同样的值。

### 6. manifest

SESSIONS："常数（0.95、0.5、分诊阈值）写入 manifest"。`harness/manifest.py` 与 `harness/constants.py` 已冻结，不改；理论层自己出一节，加到 run manifest 的 dict 上。

- `theory_manifest() -> dict`：`{"schema": 1, "constants": constants.as_dict(), "code": harness_hash(patterns=("surprise/theory/**/*.py",)), "features": {"vocab": default_registry().digest(), "limits": {"MAX_TABLE_ROWS": …, "PROBE_TIMEOUT_S": …, "ISOLATION_TIMEOUT_S": …}, "code": harness_hash(patterns=("surprise/features/**/*.py",))}}`。`harness_hash` 是 `surprise.harness.manifest` 里现成的函数（返回 `algorithm`、`hash`、`files`），直接调用；三个上限从 `surprise.features.limits` 读。
- `extend_manifest(manifest) -> dict`：返回 `manifest` 的深拷贝加一个键 `"theory"`，值为 `theory_manifest()`；不改传入的 dict，不动别的键。`manifest` 不是含有 `harness` 与 `constants` 两个键的 dict，或者已经有 `theory` 键：`ValueError`。
- `verify_theory_manifest(manifest) -> list[str]`：把 manifest 里记的 `theory` 一节与当前的代码和常数比较，返回问题清单，空表示没变。每条一行、纯 ASCII；常数变了的那一行里有常数名，文件变了（改了、多了、少了）的那一行里有文件的相对路径；词表摘要或上限变了也各报一行。`manifest` 没有 `theory` 一节：`ValueError`。
- 命令行 `python -m surprise.theory {constants|manifest}`（`theory/__main__.py`，在 `framework/` 下执行）：分别把 `constants.as_dict()` 和 `theory_manifest()` 打印成 JSON（`sort_keys=True`、`ensure_ascii=True`），退出码 0。

### 7. 测试

新增 `framework/tests/test_surprise_s06_*.py`（文件名不要与上一个包的重复，可以拆成几个）。例子自己写，不要 import `surprise.gates`。至少覆盖：R 与 Kᵛ 的计数、公式、每种拒绝、往返；实验类；`predict` 的三个区、优先级、多个假设同时确认或待定时列表的次序、别的引擎与 oracle 不相干、`undetermined` 不算区；`surprise_bits` 的五个量级与拒绝；`triage` 的每一档、两个阈值、每种拒绝；`observe` 第 5 步的每一个分支（通过与失败 × 三种位置 × 身份三种结果）、新家族的建立与回放、没有画像的失败进 R、无效只动 Kᵛ、校验失败不改状态、显式传入的 `prediction`；编号计数器；`put` 的规范化、替换与每种拒绝；状态往返与"还原后接着用"；`version`；manifest 的三个函数与命令行。

## 背景

1. **导入环。** `surprise/features/spec.py` 在顶层导入 `surprise.theory.contracts`，所以理论层的模块顶层只从特征层的**子模块**导入（`from surprise.features.units import unit_of, unit_parts`、`from surprise.features.phi import Phi`、`from surprise.features.registry import default_registry`），不要写 `from surprise.features import …`。门槛的 `constants` 组在四个新进程里按不同顺序导入，本包加了模块之后仍要全部成功。
2. `evaluate_final`（已冻结）写账本时 `surprise` 字段恒为 `None`，它只收一个 `p_t`。约定 `p_t` 传 `prediction.p_fail_valid`：这样账本里的 `p_t` 加上标签就能用 `surprise_bits` 重算惊讶。门槛的 `walkthrough` 组就是这么做的，本包不需要为它写代码。
3. `walkthrough` 组在真实引擎上跑（DataFusion，参照 DuckDB、PostgreSQL、SQLite），约 20 秒，需要本机的 PostgreSQL 参照服务器（127.0.0.1:55432）在运行。它连不上时这一组会失败：不要自己去启动或安装任何东西，把现象写进报告、停下。
4. 手写标签的形状见 `gates/s06.py` 的 `fail_label`。`label.cve` 的读取一律用 `.get`，键不存在或类型不对按"没有"处理。
5. 一个 φ 相同、标签不同的实验再来一次是正常的（同一条语句被重复执行）；记录号不同。`Phi` 不能直接当 dict 的键（它的 `layers` 是只读映射，不可哈希），记"见过的通过"时用它的规范 JSON 或特征元组加层状态当键。
6. `Theory` 把自己的词表（构造时的 `registry`，`None` 则建一份默认词表存起来）传给每一次 `position`、`apply_positive`、`apply_negative`、`new_family`、`reduce_conjunction`、`unit_of`、`unit_parts` 调用，不要让它们各自再建默认词表。`put` 的规范化可以直接用 `theory/vspace.py` 里现成的 `_drop_redundant` 与 `_canonical`（同一个包内使用私有函数没有问题）。

## 允许改动的路径

只改下面这些路径（`**` 跨目录，`*` 不跨）。审查按这个清单逐个文件核对，清单以外的任何改动都算越界。

```allow-paths
framework/surprise/theory/**
framework/tests/test_surprise_s06_*.py
```

上一个包交付的 `theory/` 下的文件，除了往 `theory/__init__.py` 里加导出之外原则上不改。发现其中有错：写进报告的"未决问题"，说明是哪一行、反例是什么；不要顺手改它的行为，也不要改它的测试。

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`。
- 不改 `framework/surprise/harness/`（已冻结）与 `framework/surprise/features/`。
- 旧代码（`framework/surprise/` 以外）本包不碰，理论层也不 import 它们（`llm`、`agents`、`evolution`、`coevo` 等），也不 import `surprise.gates`、`surprise.roles`、`surprise.hunter`、`surprise.diagnoser`。
- 本包不做持久化到文件、按代快照、编辑日志、回滚、负记忆、MDL（S7），不做 Hunter 与主循环（S8），不做任何 LLM 角色。
- 理论层的代码不连接引擎、不执行 SQL。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。某个已有测试确实该改，写进报告的"未决问题"，停下。
- 标签路径上不调用 LLM；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。本包不需要任何 LLM 调用。
- 不安装、不升级任何依赖，不动 `.venv`、`.venvs/`、`.orch/pg16/`。
- 不清理 `.orch/tmp`：临时文件留着不管，包括你自己建的（提交信息用 `git commit -m`）。不建任何指向 worktree 之外的链接或目录联接。被权限规则拒绝的操作不要换写法重试。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests        # 0 failed，通过数不少于上一个包合并后的数目（见 .orch/brief.md 末尾"基线通过数"），skip 不多于 3
python -m surprise.gates.s06             # 退出码 0，十二组全过，约半分钟
python -m surprise.gates.all             # 退出码 0，GATES: PASS (6/6 passed)，约 7 分钟
```

不要直接跑不带路径的 `pytest`。开发时反复跑 `python -m surprise.gates.s06 --only residual validity predict triage theory manifest` 和你自己的测试（都只要几秒），`walkthrough` 与 `gates.all` 收尾时跑。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。认为门槛或用例表的某个期望不对，写明是哪一行、按规则你推出的值是什么，停下。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s06-theory

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```

基线通过数：398 passed，3 skipped（`s06-vspace` 合并后在主检出区实测）。
