角色：执行者

# 工作包 s07-accept：理论编辑、接受规则、押注与自动回滚、负记忆、MDL 合并与拆分

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s07-accept`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s07`（上一个包 `s07-store` 合并之后）
- 所属会话：S7（Phase 3b：理论存储与接受规则），范围见 `framework/surprise/docs/SESSIONS.md` 的 S7 一节
- 依赖：`s07-store` 已经合并，直接用它在 `surprise.theory` 里的东西：`TheoryStore`、`StoreError`、`Theory.next_id` / `remove` / `reserve_id` / `passes`、`common_conjunction`、`hypothesis_length`、`theory_length`、四个新常数。先读 `framework/surprise/theory/` 下已有的代码（尤其 `store.py`、`theory.py`、`hypothesis.py`、`identity.py`、`contracts.py` 里的 `TheoryEdit`）。`framework/surprise/harness/`（已冻结）与 `framework/surprise/features/` 只读不改
- 本包做完，S7 的门槛十五组应当全部通过

## 目标

依据 `framework/surprise/docs/PLAN.md` 第 4 节契约表（"理论编辑：类型、理由、押注预测、留入/留出惊讶变化、接受或回滚、提出者；回滚进负记忆"）、第 5 节 Phase 3、第 6 节决策 2（"析取靠拆假设，MDL 决定"）。框架文档的原话，本包照它实现：

- "理论的每次修改都写明理由和预测；预测落空的编辑自动回滚，并作为负面记忆留下，防止同一个错误猜想反复出现。"
- "新特征、拆分与合并必须在触发记录上降低惊讶，在留出记录上不增加惊讶。"
- "理论修改的目标：最小化'累计惊讶 + 理论长度'（MDL），作为假设拆分和合并的判据。"
- "通过的结果、退役的假设、被拒绝的提议都保留为负记忆。"

本包交付两个新文件：`theory/edits.py`（编辑的数据与接受规则，纯函数，不做文件读写）与 `theory/workbench.py`（`Workbench`：带着存储、日志、编辑日志、押注、回滚与 MDL 的"在用的理论"）。全部是纯逻辑加文件读写：不连接引擎，不执行 SQL，不调用任何模型，同样的输入序列得到同样的状态与同样的文件。

验收以 `framework/surprise/gates/s07.py` 的十组 `imports edits accept rollback journal mdl families ciao replay ledger` 为准（另外五组上一个包已经通过，必须保持通过）。先把这十个 `check_*` 函数和 `gates/s07_cases.py` 读一遍：门槛用到的名字、参数、返回值、日志的键都在下面写明，照写。前八组不碰引擎；`replay` 与 `ledger` 在真实引擎上回放已知复现与 DCE 探针，两组共用一次回放，合计约 5 分钟。

下面的名字都要能从 `surprise.theory` 直接导入并列进 `__all__`：`Assessment`、`BET_STATES`、`EDIT_KINDS`、`Outcome`、`Proposal`、`REJECT_REASONS`、`ROLLBACK_REASONS`、`Seen`、`Workbench`、`bet_matches`、`claim`、`default_bets`、`fingerprint`、`holdout_sample`。常数一律从 `surprise.theory.constants` 读。

### 1. 取值表与数据类型（`theory/edits.py`）

```python
EDIT_KINDS = ("add", "revise", "split", "merge", "retire")
REJECT_REASONS = ("negative_memory", "no_bets", "trigger", "holdout", "no_gain")
ROLLBACK_REASONS = ("bet_broken", "manual", "cascade")
BET_STATES = ("open", "kept", "broken", "void")
```

**押注（bet）**是一个 dict，键恰好是 `"spec"` 与 `"expect"`：`spec` 是 `surprise.theory.contracts.Spec` 的 dict 形式（引擎、oracle、必须有的特征、不许有的特征、数据性质），`expect` 是 `"pass"` 或 `"fail"`。它的意思是："一条满足这个规格的有效实验，标签会是 expect。"

`Proposal`：冻结 dataclass，提出者交进来的一条编辑。字段依次为 `kind`、`rationale`、`proposer`、`removes=()`（要拿掉的假设编号）、`adds=()`（要加进来的假设，`Hypothesis` 对象；其 `hypothesis_id` 只是占位，见第 3 节）、`bets=()`、`trigger=()`（触发这条编辑的实验记录编号）。构造时校验，不合即 `ValueError`：

- `kind` 在 `EDIT_KINDS` 里；`rationale`、`proposer` 是非空字符串。
- 各类编辑的形状：`add` 拿掉 0 个加 1 个；`revise` 拿掉 1 个加 1 个；`split` 拿掉 1 个加 ≥ 2 个；`merge` 拿掉 ≥ 2 个加 1 个；`retire` 拿掉 1 个加 0 个。
- `removes`、`trigger` 是互不重复的非空字符串序列（单个字符串不算序列）；`adds` 是 `Hypothesis` 的序列（dict 不行）。
- `bets` 是押注的序列（单个 dict 不算序列）；每个押注的键恰好是那两个，`expect` 合法，`spec` 能被 `Spec.from_dict` 接受。存下来的是规范化后的形式 `{"spec": Spec.to_dict(), "expect": ...}`。
- `bets` 可以为空：没有押注的提案写得出来，由工作台拒收并记录（见第 4 节）。
- 存下来的 `removes`、`adds`、`bets`、`trigger` 都是元组。

`Seen`：冻结 dataclass，日志里的一条观察：`record_id`、`phi`（`Phi`）、`label`（`Label`）。

`Assessment`：冻结 dataclass，一次接受检验的结论：`accepted`（bool）、`reason`（接受时为 `None`，否则是 `REJECT_REASONS` 之一）、`fingerprint`、`delta_in`、`delta_out`、`delta_length`（没算到这一步时为 `None`）、`holdout`（用到的留出记录编号，元组）。

### 2. 声明、指纹、押注、留出样本（`theory/edits.py`，纯函数）

- `claim(hypothesis, registry) -> list`：一个假设"断言了什么"：`[engine, oracle, sorted(interventions), fail_kind, error_class, behavior_shape, list(reduce_conjunction(specific, registry))]`。编号、G、E⁺、E⁻、来源、ΔP、V，以及 S 的写法（次序、多余的祖先、层根）都不影响它。
- `fingerprint(removed, added, registry) -> str`：16 位小写十六进制。取 `{"adds": 各 added 的 claim（排序）, "retire": added 为空时各 removed 的 claim（排序），否则空表}` 的规范 JSON（`sort_keys=True, separators=(",", ":"), ensure_ascii=False`）的 SHA-256 的前 16 位。排序按每个 claim 自己的规范 JSON 字符串。所以：指纹只看"加进来的断言"；编辑的类型、提出者、被替换掉的是谁都不进指纹；只有退役（什么都不加）才按"撤回的断言"算。
- `default_bets(removed, added, registry) -> tuple[dict, ...]`：`added` 非空时，每个加进来的假设一条：`Spec(engine, oracle, required=reduce_conjunction(specific))` 期望 `"fail"`（"落在它的 S 里的实验会失败"）；`added` 为空时，每个被拿掉的假设一条：同样的规格期望 `"pass"`。
- `bet_matches(bet, phi, label, registry) -> bool`：这条有效实验是不是这个押注说的那种：`label.y != "invalid"`、`spec.oracle == label.oracle`、并且 `surprise.features.spec.check_spec(phi, Spec.from_dict(bet["spec"]), registry).ok`。`check_spec` 在函数内部导入（见"背景"里的导入顺序）。φ 缺了规格要用的那一层时 `ok` 为假，押注不算命中。
- `holdout_sample(records, scopes, exclude, limit=ACCEPT_HOLDOUT_MAX) -> tuple[Seen, ...]`：留出记录。从 `records`（一串 `Seen`）里取：标签有效、`(phi.engine, label.oracle)` 在 `scopes`（一组（引擎，oracle））里、编号不在 `exclude` 里的；保持原来的次序。超过 `limit` 时只留 `sha256(record_id.encode("utf-8")).hexdigest()` 最小的 `limit` 条（仍按原次序返回）。

### 3. 一条编辑加进来的假设是怎么造出来的

提出者只决定一个假设的**身份**（引擎、oracle、interventions、fail_kind、error_class、behavior_shape）与 **S**；其余全部由证据重算，提出者塞不进任何别的东西。给定模板 `template`（`Proposal.adds` 里的一项）与一个编号：

1. `S = reduce_conjunction(template.specific)`；约简后为空，或 `template.oracle` 是 `None`：`ValueError`。
2. 新假设：编号取给定的；`engine`、`oracle`、`interventions`、`plan_delta`、`versions`、`fail_kind`、`error_class`、`behavior_shape`、`source` 取模板的；`specific = S`；`general = ((),)`；`positives`、`negatives`、`contradictions` 为空；`status = "active"`；`truncated = False`。
3. 正例：候选记录按次序过一遍，凡 `position(新假设, 该记录的 phi, oracle) == "confirmed"` 的，把记录编号记进 `positives`（不重复）。候选是：
   - 编辑有 `removes` 时：被拿掉的各假设的 `positives`，按 `removes` 的次序接起来、去重，只取日志里有的记录；
   - `add`（没有 `removes`）时：日志里同作用域的全部失败记录中，`identity_match(第 2 步的新假设, 记录的标签) is True` 的那些，按日志次序。
4. G：把该作用域记住的通过（`theory.passes(engine, oracle)`）按次序逐条 `apply_negative`。落在 S 里的通过因此进 `contradictions`，落在待定区的把 G 收紧。

编号：评估时用占位编号（例如 `"e3.1"`、`"e3.2"`，只要互不相同且不与现有编号重复）；**只有被接受时**才用 `theory.reserve_id()` 依次取真编号，并按真编号重造一遍。被拒绝的提案不消耗编号。编辑**永远不复用**被它拿掉的假设的编号。

### 4. 接受检验（`assess`）

输入：当前理论、被拿掉的假设 `removed`、按第 3 节造出来的 `added`、押注、触发记录（`Seen`）、日志里的全部记录、负记忆里的指纹。按下面的次序判，先命中的为准：

1. 指纹在负记忆里：拒绝，`reason = "negative_memory"`，三个差值为 `None`，`holdout = ()`。
2. 没有押注：拒绝，`reason = "no_bets"`，同上。
3. 触发记录里有标签无效的：`ValueError`（这是调用方的错，不是一次被拒）。
4. 算三个差值：
   - "之后"的理论：当前理论去掉 `removed`、在末尾按次序加上 `added`；R 与 Kᵛ 与当前理论相同。它只用来做预测，不许被训练。（做法建议：新建一个 `Theory(registry)`，把 `residual`、`validity` 两个属性指向当前理论的同名对象，再把假设逐个 `put` 进去；不要拷贝记住的通过。）
   - 一条记录在某个理论下的惊讶 = `surprise_bits(theory.predict(phi, label.oracle).p_fail_valid, label.y)`，就是用**现在的**理论去看这条旧记录。
   - 留出记录 = `holdout_sample(全部记录, removed 与 added 涉及的作用域, 触发记录的编号)`。
   - `delta_in` = 触发记录上（之后 − 之前）的惊讶之和；`delta_out` = 留出记录上的同一个和；`delta_length = theory_length(之后) − theory_length(之前)`。前两个是 `float`（空和是 `0.0`）。
5. `delta_in > ACCEPT_TOLERANCE_BITS`：拒绝，`"trigger"`。
6. `delta_out > ACCEPT_TOLERANCE_BITS`：拒绝，`"holdout"`。
7. `delta_in + delta_out + delta_length >= −ACCEPT_TOLERANCE_BITS`：拒绝，`"no_gain"`。
8. 否则接受。

也就是：在触发记录上不变差、在留出记录上不变差、并且"惊讶加长度"严格变小，三条同时成立才接受。第 5、6 步的拒绝是"被已有的记录反驳"，进负记忆；`no_gain` 与 `no_bets` 不是反驳，不进。

### 5. 工作台（`theory/workbench.py`）

`Outcome`：冻结 dataclass，一次观察的后果：`observation`（S6 的 `Observation`）、`seq`（这条观察在日志里的序号）、`owner`（见第 8 节）、`bets`（本次兑付的押注，`(edit_id, 押注下标, "kept" | "broken")` 的元组）、`rolled_back`（因本次观察被回滚的编辑编号，元组）。两个 `Outcome` 能用 `==` 比较。

`Workbench`：只通过两个类方法得到实例：

- `Workbench.create(root, registry=None)`：`TheoryStore.create` 一个新存储，理论为空。
- `Workbench.open(root, registry=None)`：`TheoryStore.open`，`store.load()` 读回理论，从 `journal.jsonl` 的 `observe` 条目重建全部 `Seen`，从 `store.edits()` 读回编辑。重新打开的工作台与原来的那个在一切可观察的方面相同，接着用的结果也相同。

读：

- 属性 `store`、`theory`（在用的 `Theory`；调用方当作只读）、`generation`（当前代号，即 `store.head()["generation"]`）。
- `predict(phi, oracle)`：同 `theory.predict`。
- `records() -> tuple[Seen, ...]`（按观察次序）；`seen(record_id) -> Seen`（没观察过抛 `KeyError`）。
- `edits() -> tuple[TheoryEdit, ...]`（每条编辑的最新状态，按编号次序）；`edit(edit_id)`；`negatives() -> tuple[dict, ...]`。
- `open_bets() -> tuple[(edit_id, 下标, 押注 dict), ...]`：已接受的编辑里状态还是 `"open"` 的押注，按编辑次序、下标次序。
- `surprise_under(generation, record_ids) -> float`：这些记录在那一代理论下的平均惊讶。`generation` 等于当前代号时用在用的理论，否则用 `store.load_generation(generation)`（不存在的代因此抛 `StoreError`）。`record_ids` 为空抛 `ValueError`；含无效记录抛 `ValueError`；含没观察过的记录抛 `KeyError` 或 `ValueError`。

#### 5.1 观察

`observe(phi, label, record_id, *, prediction=None) -> Outcome`，依次：

1. `record_id` 已经观察过：`ValueError`，什么都不做。
2. `observation = theory.observe(phi, label, record_id, prediction=prediction)`。
3. 往日志追加一条：`{"kind": "observe", "record_id": ..., "phi": phi.to_dict(), "label": 去掉 detail 的标签的 to_dict()}`（加上存储写的 `seq`，键恰好这五个）。"去掉 detail"指 `Label.from_dict({**label.to_dict(), "detail": {}})`；`cve` 原样保留。工作台自己记住的 `Seen` 也用这个去掉 detail 的标签。
4. 兑付押注：按编辑编号次序看每条已接受的编辑，按下标次序看它还 `"open"` 的押注；`bet_matches(押注, phi, 标签, registry)` 为真的，状态改成 `"kept"`（`label.y == expect`）或 `"broken"`，并记下 `record_id`。一条编辑有押注落空：立刻 `rollback(该编辑, reason="bet_broken", record_id=record_id)`，然后**不再看后面的编辑**（它们已经被级联撤掉）。一条编辑只有兑现的押注：把它的新状态 `append_edit` 一次。
5. 没有发生回滚时 `store.save(theory)`（回滚自己会存）。
6. 返回 `Outcome`。其中 `observation` 是第 2 步的结果，即"当时的理论"经历的惊讶与分诊，不因随后的回滚而改写。

每一次 `observe` 返回之后，磁盘上的状态都等于在用的理论（`store.load().to_dict() == theory.to_dict()`）。一条押注只兑付一次：全部押注都兑现之后，这条编辑就定下来了，以后落在它的 S 里的通过只是 S6 意义上的矛盾（`contradiction`），不会回滚它。

#### 5.2 提议

`propose(proposal) -> TheoryEdit`。参数不是 `Proposal`：`ValueError`。先核对用法，不合就抛异常、**不留任何记录**：`removes` 里有理论中不存在的编号（`KeyError` 或 `ValueError`）；被拿掉的与加进来的假设不在同一个（引擎，oracle）作用域（`ValueError`）；`trigger` 里有没观察过的记录或无效记录（`ValueError`）；模板的 S 约简后为空（`ValueError`）。

编辑编号是 `"e{n}"`，`n` = 已有编辑的条数 + 1；被拒绝的提案同样占一个编号、同样写进编辑日志。然后按第 3、4 节造假设、做接受检验，写一条 `TheoryEdit`：

- `edit_id`、`kind`、`rationale`、`bets`（押注的定义）、`proposer` 取自提案；`theory_version` 是提议之前的 `theory.version`；`surprise_delta_in` / `surprise_delta_out` 是检验算出的 `delta_in` / `delta_out`（没算到就是 `None`）；`decision` 是 `"accepted"` 或 `"rolled_back"`。
- `payload` 的键恰好是下面这些：
  - `reason`：被拒的原因，接受时为 `None`；
  - `fingerprint`；`trigger`（提案里的编号，list）；`holdout`（用到的留出记录条数）；`length_delta`（`delta_length`，没算到为 `None`）；
  - `removes`（编号 list）；`removed`（被拿掉的假设在提议时的 `to_dict()`，list）；
  - `adds`（真编号 list；被拒时为 `[]`）；`added`（造出来的假设的 `to_dict()`；接受时带真编号，且等于写进理论的那个假设）；
  - `generation`（接受这条编辑时封存的那一代的代号；被拒时 `None`）；`journal_seq`（日志里那条 `edit` 条目的序号；被拒时 `None`）；
  - `bets_state`：与 `bets` 等长的 list，每项 `{"status": ..., "record_id": ...}`；接受时全是 `{"status": "open", "record_id": None}`，被拒时全是 `"void"`；
  - `rollback`：`None`，回滚之后是 `{"reason", "record_id", "generation"}`（见 5.3）。

被拒绝时：理论、代号、编号计数器、磁盘上的状态都不变；`reason` 是 `"trigger"` 或 `"holdout"` 时往负记忆追加一条 `{"fingerprint", "edit_id", "kind", "reason", "record_id": None, "claims"}`，其中 `claims` 是加进来的各假设的 `claim`（退役时是被拿掉的各假设的）。

被接受时，依次：`generation = store.close_generation(theory, cause=f"edit:{edit_id}")`（封存的是**应用编辑之前**的理论）→ 取真编号、按真编号重造 → 从理论里 `remove` 被拿掉的、把加进来的依次 `put` → 往日志追加 `{"kind": "edit", "edit_id": ..., "generation": generation}` → `store.save(theory)` → `append_edit`。

`assess(proposal) -> Assessment`：同样的用法核对与接受检验，但不应用、不记录、不消耗编号：调用前后理论、编辑日志、负记忆、磁盘都不变。

#### 5.3 回滚

`rollback(edit_id, *, reason="manual", record_id=None) -> tuple[TheoryEdit, ...]`。`reason` 只能是 `"bet_broken"` 或 `"manual"`（`"cascade"` 不能由调用方给）；`edit_id` 不是一条当前状态为 `"accepted"` 的编辑：`ValueError`。依次：

1. `closed = store.close_generation(theory, cause=f"rollback:{edit_id}")`：把回滚之前的理论封存成一代（被反驳的状态留档）。
2. 取这条编辑的 `payload["generation"]` 那一代的快照 `store.load_generation(...)`，这是应用它之前的理论。把它的状态取出来，把 `next_id` 改成在用的理论的 `next_id`（**编号计数器不回退**，用过的编号永不再发），再 `Theory.from_dict` 成一个新理论。
3. 把日志里序号大于这条编辑的 `payload["journal_seq"]` 的全部 `observe` 条目，按次序在新理论上重放：`theory.observe(seen.phi, seen.label, seen.record_id)`，**不传 `prediction`**（由恢复后的理论重新预测）。`edit`、`rollback`、`checkpoint` 条目跳过。
4. 级联：编辑日志里所有仍为 `"accepted"`、且 `payload["journal_seq"]` 大于这条编辑的，一并撤销（它们是在包含这条编辑的理论上被接受的）。
5. 新理论成为在用的理论。往日志追加 `{"kind": "rollback", "edit_id": ..., "reason": ..., "generation": closed, "cascade": [被级联的编辑编号，按编号次序]}`（加 `seq`，键恰好这六个），`store.save(新理论)`。
6. 这条编辑与被级联的各条，各 `append_edit` 一个新状态：`decision = "rolled_back"`；`bets_state` 里还 `"open"` 的改成 `"void"`，已经 `"kept"` / `"broken"` 的不动；`payload["rollback"] = {"reason": 这条编辑用传入的 reason、被级联的用 "cascade", "record_id": 这条编辑用传入的 record_id、被级联的为 None, "generation": closed}`。
7. 往负记忆追加这条编辑：`{"fingerprint": payload["fingerprint"], "edit_id", "kind", "reason", "record_id", "claims"}`。**被级联的编辑不进负记忆**（它们没有被反驳，可以再提）。
8. 返回 `(这条编辑的新状态, 被级联的各条的新状态…)`。

回滚之后的理论 = "应用这条编辑之前的理论，学过此后的全部观察"。门槛用 S6 的 `Theory` 独立算一遍来核对，必须逐字段相等。

#### 5.4 检查点

`checkpoint(note) -> int`：`note` 不是非空字符串抛 `ValueError`。`closed = store.close_generation(theory, cause=f"checkpoint:{note}")`，往日志追加 `{"kind": "checkpoint", "note": note, "generation": closed}`，返回 `closed`。S8 用它按批切代。

### 6. MDL：合并、收紧、拆分

三种候选都只是生成 `Proposal`，接受与否一律由第 4 节的同一个检验决定；`proposer` 都是 `"mdl"`，押注都是 `default_bets`，加进来的模板的 `source` 都是 `"mdl"`。

`merge_candidates() -> tuple[Proposal, ...]`：对理论里每一对假设（按理论次序，`first` 在 `second` 之前），同一个（引擎，oracle）且**身份相同**时生成一条。身份相同：两者都有 `interventions` 时，只看 fix set 相同（集合相等，失败类别与形状不论）；两者都没有时，看 `fail_kind`、`error_class`、`behavior_shape` 三项都相同；一个有一个没有，不算相同。`S = common_conjunction(first.specific, second.specific)`，为空则跳过。提案：`kind="merge"`，`removes=(first, second)`，`adds=(dataclasses.replace(first, specific=S, source="mdl"),)`（身份、ΔP、V 取较早的那个），`trigger=()`，`rationale` 自拟（非空，带上两个编号）。

`repair_candidates() -> tuple[Proposal, ...]`：对每个假设，取它的 `contradictions` 里**标签是 pass** 的记录（身份不一致的失败也会进 `contradictions`，这里不算）与它的 `positives`（都只取日志里有的）。两者有一个为空就跳过。然后把正例按次序贪心分簇：

```
簇 = []                       # 每个簇是一个约简过的、非空的合取
对每个正例 p（按 positives 的次序）:
    own = reduce_conjunction(p.phi.features)
    own 为空：跳过这个正例（它什么也说明不了）
    对每个已有的簇 S（按建立次序）:
        S2 = generalize(S, p.phi)
        S2 为空，或者存在某条矛盾通过 c 使得 covers(S2, c.phi) 且 not covers(S, c.phi)：这个簇不行，看下一个
        否则：这个簇换成 S2，p 归它，处理下一个正例
    没有簇收下 p：新开一个簇 own
```

一个簇都没有，或者只有一个簇且它等于这个假设现在的 S：没有可修的，跳过。候选里的 S 因此永远非空，`compress()` 不会因为空的 S 抛异常。否则生成一条提案：一个簇是 `kind="revise"`（收紧），多个簇是 `kind="split"`（拆分）；`removes=(这个假设,)`；`adds` 是每个簇一个模板 `dataclasses.replace(假设, specific=簇, source="mdl")`，按簇的建立次序；`trigger` 是那些矛盾通过的记录编号，按 `contradictions` 的次序。

`compress() -> tuple[TheoryEdit, ...]`：反复做：依次看 `repair_candidates()` 再看 `merge_candidates()`，对每条候选先 `assess`，遇到第一条会被接受的就 `propose` 它并从头再来；一整轮没有可接受的就停。最多 100 轮。返回这次应用的编辑。被 `assess` 判为不接受的候选**不** `propose`，所以不写编辑日志、不进负记忆（它们每次都会被同样的证据再拒一遍）。

### 7. 惊讶随代的变化

见 5 里的 `surprise_under`。它是惊讶版 CIAO 矩阵的一格：用第 i 代理论看一批旧记录。

### 8. 归属与家族

- 一条失败记录的 owner：理论里把这条记录列在 `positives` 里的假设。没有：`None`。有多个：标签的 `cve["attribution"]` 是一次 `status == "ran"`、`consistent is True` 的归属测试，且它的 `hypothesis_id` 在其中时，取它；否则取理论次序里最前的那个。通过、无效的记录没有 owner。
  - `Outcome.owner` 是观察刚结束时按这条规则算的；`owner_of(record_id)` 是按**现在的**理论算的（没观察过的记录抛 `KeyError`）。合并、拆分、收紧、回滚之后不需要另外记账：`positives` 跟着第 3 节的重造与回滚的重放走。
- `family_of(hypothesis_id) -> str`（编号不存在抛 `KeyError`）：有 `interventions` 时是 `f"{engine}|fix:{'+'.join(sorted(interventions))}"`（同一个 fix set 跨 oracle、跨假设是一个家族）；没有时是 `f"{engine}|{hypothesis_id}"`（这个假设自己是一个家族）。
- `families() -> dict[str, tuple[str, ...]]`：家族名 → 属于它的假设编号（理论次序）；家族按第一次出现的次序。
- `partition() -> dict[str, str | None]`：日志里每条失败记录（按观察次序）→ 它的 owner 的家族名，没有 owner 为 `None`。

### 9. 顺带修上一个包的一处（`theory/store.py`，只许改这一处）

`TheoryStore.last_seq` 现在每次都把 `journal.jsonl` 整个读一遍、逐行解析，`append_journal` 与 `close_generation` 又都调用它。编排者实测：日志 1000 条时追加一条 17 毫秒，5000 条 77 毫秒，20000 条 389 毫秒，随长度线性增长；S8 的长 run 每条观察都要追加一次。改成：

- 序号存在实例里：`create` 时为 0，`open` 时读一遍日志（照旧校验）得到；`append_journal` 写完一行后加一；`last_seq` 返回这个数。`append_journal`、`last_seq`、`close_generation` **都不再读日志文件**。
- `journal()` 照旧每次读文件并校验。`open` 之后日志被别人改动不在考虑之内：一个存储目录同一时间只由一个 `TheoryStore` 实例写，在类的 docstring 里写明这一点。
- 加一条测试：`open` 一个已有若干条日志的存储之后，连续追加几条，期间读日志文件的那个函数一次都没有被调用（用 `monkeypatch` 给 `surprise.theory.store` 里读 jsonl 的函数计数即可），序号仍然连续，重新 `open` 后接得上。

`store.py` 的其余部分、文件格式、别的方法的行为一处不许动；上一个包的测试必须照旧通过。

### 10. 测试

新测试放 `framework/tests/test_surprise_s07_*.py`（例如 `test_surprise_s07_edits.py`、`test_surprise_s07_workbench.py`、`test_surprise_s07_mdl.py`；不要改上一个包留下的测试文件里已有的断言）。手工 φ 与标签可以照 `gates/s06.py` 的做法自己造（`surprise.features.make_phi`、`Label`、`IdentityEvidence`），但测试不要 import `surprise.gates`。至少覆盖：`Proposal` 的每一条校验；`claim` / `fingerprint` 的不变性；`default_bets`；`bet_matches` 的各种不命中；`holdout_sample` 的截断；接受检验的每一种结论各至少一例，并对差值做数值断言；被拒的提案不改状态、不耗编号；押注兑现与落空；回滚后的理论与"快照加重放"逐字段相等；级联与"级联的不进负记忆、可以再提"；负记忆按指纹拒绝（换一种 `kind`、换一个提出者照样拒）；手动回滚；`Workbench.open` 之后状态相同、接着用结果相同；日志条目的键；三种 MDL 候选的生成与 `compress()` 的不动点；`owner_of` / `family_of` / `families` / `partition`；`surprise_under`。

## 背景

- **编辑与规则更新是两回事。** `Theory.observe` 按 S6 的版本空间规则更新 S、G、开新家族，这些不是编辑，不走接受检验，也不进编辑日志（日志里有那条观察）。编辑是"别人提出来的改动"：猜想者改写 S、MDL 合并拆分、退役。S6 的规则与 `Theory` 的既有行为一处不许动。
- **为什么编辑不复用编号。** 账本里的标签带着归属测试的结果（`cve["attribution"]["hypothesis_id"]`）。编号一旦换了含义，旧标签就会被误读成对另一个假设的证据。所以：一个编号的身份永远不变，它的 S、G 只按版本空间规则变；其余任何改动都换新编号；回滚时计数器不回退。
- **导入顺序。** `features/spec.py` 导入 `theory/contracts.py`，而理论层又要用 `check_spec`。理论层只能从特征层的**子模块**导入（`surprise.features.phi`、`surprise.features.registry`），并且 `surprise.features.spec` 要在函数内部导入，不要放在 `edits.py` 的顶部。门槛的 `imports` 组在新进程里查五种导入顺序。
- 理论层不许导入 `llm`、`coevo`、`agents`、`evolution`、`openai`、`anthropic`、`httpx`、`requests`、`surprise.gates`、`surprise.roles`、`surprise.hunter`、`surprise.diagnoser`（门槛逐个文件查）。
- `Theory.put` 会把假设规范化；`Hypothesis` 是冻结 dataclass，改字段用 `dataclasses.replace`；`TheoryEdit` 同样。`TheoryEdit.payload` 必须是 JSON 安全的 dict。
- 门槛里几个数字的来历（帮助你自查，不要写死在代码里）：一个假设的长度是 `8.0 + 7.4 × |S|` 比特；确认区里的一条通过是 4.32 比特，挪到未探索区是 0.0145 比特；所以收紧一个多写 8 个字面量的 S 需要十四条以上的矛盾通过才划算，拆出第二个十字面量的假设需要三十五条以上。
- 这台机器的控制台打印中文是乱码，文件本身是 UTF-8，没有问题；判断结果看 ASCII 关键字。
- 代码风格照 `framework/surprise/theory/` 里已有的文件：英文 docstring 与注释，类型标注，不写多余的防御代码。

## 允许改动的路径

只改下面这些路径（`**` 跨目录，`*` 不跨）。审查按这个清单逐个文件核对，清单以外的任何改动都算越界。

```allow-paths
framework/surprise/theory/edits.py
framework/surprise/theory/workbench.py
framework/surprise/theory/__init__.py
framework/surprise/theory/store.py
framework/tests/test_surprise_s07_*.py
```

`store.py` 只为第 9 节那一处开放。

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`（已冻结）、`framework/surprise/features/`。
- 不改 `framework/surprise/theory/` 里上面没列出的文件（`theory.py`、`vspace.py`、`hypothesis.py`、`identity.py`、`constants.py`、`length.py` 等）；`store.py` 除第 9 节那一处之外不改。觉得其中哪个非改不可，写进报告，停下。
- 旧代码（`framework/surprise/` 以外）本包不碰。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。某个测试确实该改，就写进报告的"未决问题"，停下。
- 标签路径上不调用 LLM；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。本包不需要任何 LLM 调用。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不做 Hunter、主循环、任何 LLM 角色；不改"什么算正例、什么进 R"这类 S6 的规则。
- 不建指向 worktree 之外的链接或目录联接；不要清理 `.orch/tmp`；测试产生的临时文件只放 pytest 的 `tmp_path`。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests       # 通过数不少于 528（上一个包合并后的数目），skip 仍是 3。用 `python -m pytest`：直接敲 `pytest` 会把 tests 目录放到 sys.path 最前，`import surprise` 失败
python -m surprise.gates.s07 --only constants length theory_api store generations imports edits accept rollback journal mdl families ciao    # 13/13，几秒钟
python -m surprise.gates.s07            # 15/15，约 5 分钟（真实引擎）
python -m surprise.gates.all            # 最后一行 GATES: PASS (7/7 passed)，约 11 分钟
```

真实引擎的两组需要本机的 PostgreSQL 参照（127.0.0.1:55432，已在运行）和主检出区的旧版引擎环境；门槛自己会找到它们，你不需要启动或配置任何东西。如果 `replay` 或 `ledger` 因为连不上 PostgreSQL 或找不到旧版解释器而失败，不要去修环境：把报错原样写进报告，停下。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s07-accept

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
