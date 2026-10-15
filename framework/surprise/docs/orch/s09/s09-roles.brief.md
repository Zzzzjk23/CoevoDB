角色：执行者

# 工作包 s09-roles：实现器（spec → schema、数据、查询，用 φ 核对验收）与假设猜想者（机制、触发条件、可证伪预测，登记为待检实验）

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s09-roles`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s09`（`s09-gateway` 合并之后）
- 所属会话：S9（Phase 5a：LLM 网关、实现器、假设猜想者），范围见 `framework/surprise/docs/SESSIONS.md` 的 S9 一节
- 依赖（已合并，直接用）：`surprise.roles` 的网关一层（`Gateway`、`Reply`、`Completion`、`parse_reply`、`cache_key`、`SourceReader`、`Snippet`、`open_sources`、`constants`）；`surprise.features`（`extract`、`Phi`、`make_phi`、`check_spec`、`default_registry`、`layer_of` 在 `features/vocabulary.py`）；`surprise.theory`（`Spec`、`Proposal`、`Workbench`、`reduce_conjunction`、`bet_matches`）；`surprise.hunter`（`Candidate`、`operators.oracle_options`、`operators.case_digest`）；冻结的 `surprise.harness.contracts`（`SqlCase`、`Label`、`ORACLE_IDS`）。
- 先读：`framework/surprise/gates/s09.py` 与 `s09_cases.py` 全文（门槛就是接口规格；与本说明不一致时以门槛为准，并写进报告）；`surprise/roles/` 全部代码；`surprise/diagnoser/diagnoser.py`（无 LLM 的 Diagnoser 怎样经 `wb.propose` 提议，猜想者照它的样子）；`surprise/hunter/hunter.py` 的 `Candidate` 与 `_migrate`（候选怎么写）；`surprise/theory/edits.py` 的 `Proposal`、`bet_matches`；`surprise/features/spec.py`。
- 与你并行的包 `s09-wire` 改 `surprise/hunter/hunter.py` 与 `surprise/experiments/loop.py`，把本包的 `RoleSet` 接进主循环。你不碰那两个目录；双方只靠下面第 5 节写死的接口对接。

## 目标

依据 SESSIONS 的 S9 一节："实现器：spec → schema、数据、查询，用 φ 核对验收。""假设猜想者：读最小复现、fix set、计划差异和优化器源码，给出机制、触发条件和可证伪预测；预测登记为待检实验。"门槛："缺预测的输出被拒收；实现器 SQL 的 φ 核对通过率报告；猜想者在 DF-A 上给出带预测的假设并登记为待检实验。"PLAN 第 3 节：假设猜想者替换旧的 `_analyze_root_cause` 与 root arm，"必须附可证伪预测"；第 6 节决策 7："LLM 角色先单次结构化调用"。框架原则："LLM 永不打标签"：本包的任何东西都不产生、不修改标签，只产生实验（交给冻结的 harness 判）与理论编辑的提议（交给 S7 的接受规则）。

本包本身**不做真实调用**也能全部做完、全部测完（用假传输）。派发时给了你 `DEEPSEEK_API_KEY` 与 `SURPRISE_LLM_MAX_CALLS`（见"真实调用"一节），只用来让提示在真模型上跑通。

全部放在 `framework/surprise/roles/`。

两档模型是 `fast = deepseek-flash`、`strong = deepseek-v4-pro`（编排者用 `GET /models` 核对过，已在网关包里）。

### 0. 一处常数

编排者实测 `deepseek-v4-pro` 现在只排队不生成（流式请求只收到 `: keep-alive`，900 秒没有内容），所以猜想者默认改用 fast 档。把 `surprise/roles/constants.py` 里的 `CONJECTURER_TIER = "strong"` 改成 `CONJECTURER_TIER = "fast"`（与门槛 `s09_cases.CONSTANTS` 相同）；这个文件里别的一个字都不改。**真实调用里不要用 strong 档**（会卡住）。

### 1. 提示的通则

- 一次角色调用就是一次 `gateway.call(role, prompt, tier=..., seed=..., temperature=..., max_tokens=...)`，单次结构化调用，不做多轮、不做工具调用。tier、温度、token 上限取 `roles/constants.py` 里本角色的常数。
- 提示是**纯函数**：只由传进来的内容（规格、用例、φ、身份证据、源码片段、词表）决定。不得包含记录号、假设号、编辑号、运行号、时间、随机数、绝对路径。否则缓存键随运行而变，重放不了（门槛会检查 DF-A 的提示里没有记录号与假设号）。
- 提示用英文写，要求模型"只回一个 JSON 对象"，并把 JSON 的形状逐字段写出来。每个角色的 JSON 都必须有顶层字段 `prediction`（网关的 `parse_reply` 缺它就拒收，角色不再看这条回复）。
- 要用词表时，把允许的特征 id 与一行说明列出来（`default_registry()` 能给出全部 id；描述在 `features/vocabulary.py`）。只列与本角色相关的那部分可以，但必须是确定的（同样的输入，同样的列表、同样的次序）。

### 2. 实现器（`surprise/roles/implementer.py`）

```python
@dataclass(frozen=True)
class Attempt:
    spec: dict                 # Spec.to_dict() of the target
    status: str                # "ok" | "spec_unmet" | "bad_case" | "rejected" | "blocked" | "miss" | "error"
    ok: bool
    case: SqlCase | None       # the last case that parsed (None if none did)
    phi: Phi | None            # its phi (None if not extracted)
    missing: tuple[str, ...]; forbidden: tuple[str, ...]; undetermined: tuple[str, ...]   # of the last check
    expect: str | None         # the reply's prediction.expect ("pass" | "fail") of the last usable reply
    tries: int                 # gateway calls made, of any status
    first_ok: bool             # the first try was already ok
    keys: tuple[str, ...]      # the cache keys of the calls, in order
    def to_dict(self) -> dict  # JSON-able: case as SqlCase.to_dict(), phi as Phi.to_dict(), tuples as lists

def implementer_prompt(spec, registry=None, feedback: dict | None = None) -> str
class Implementer:
    def __init__(self, *, gateway, extract, registry=None, seed: int, tier=None, attempts=None): ...
    def implement(self, spec) -> Attempt: ...     # spec: Spec or its dict
def implementer_report(specs, implementer) -> dict
```

- 回复的 JSON：`{"setup": [语句, ...], "query": "语句", "predicate": "表达式" 或 null, "prediction": {"expect": "pass" 或 "fail", "why": "..."}}`。提示里告诉模型：目标引擎（`spec.engine`）的方言；`setup` 里建表、插数据（用小表，几行到几十行）；`query` 是一条 SELECT（或该引擎能执行的一条语句）；必须让查询具有 `required` 与 `data_properties` 里的全部特征、不具有 `forbidden` 里的任何特征；并把这些特征 id 连同说明列出来。再写上本机已知的坑：窗口函数不要写显式的帧子句（一律被判不确定）；ASOF 连接的 ON 用 `左.列 比较 右.列` 的写法；TLP 认不出的形态把过滤条件写进 `query`、`predicate` 留 null。`prediction.expect` 是模型对这个用例在目标 oracle（`spec.oracle`）下会通过还是失败的押注。
- `implement(spec)`：最多 `attempts`（默认 `IMPLEMENTER_ATTEMPTS`）次。每一次：
  1. 调网关。`blocked`、`miss`、`error` → 立刻结束，`status` 就是它（不再试）。`rejected`（网关拒收）→ 这一次作废，进下一次。
  2. `ok` 时检查本角色的字段：`setup` 是字符串列表、`query` 是非空字符串、`predicate` 是字符串或 null、`prediction` 是带 `expect ∈ {"pass","fail"}` 的对象。任何一条不满足 → 这一次记为 `rejected`，进下一次。
  3. 建 `SqlCase(engine=spec.engine, setup=tuple(setup), query=query, predicate=predicate)`；抛 `ValueError` → 这一次记为 `bad_case`（反馈里带异常信息），进下一次。
  4. `phi = extract(case)`；`check = check_spec(phi, spec, registry)`。`check.ok` → 结束，`status="ok"`。否则这一次记为 `spec_unmet`，进下一次。
  最后一次之后仍没有 ok 时，`status` 取最后一次的结果。`first_ok` 是第一次就 ok。拒收的回复绝不提取 φ。
- 重试的提示 = `implementer_prompt(spec, registry, feedback)`，`feedback` 描述上一次：上一次的 `query`（若有）原文、`missing` / `forbidden` / `undetermined` 三组 id（若有）、或拒收与建用例失败的原因。门槛要求第二次的提示里出现上一次的查询原文与缺的特征 id。第一次的提示 = `implementer_prompt(spec, registry)`，与 `Implementer` 的种子无关（种子只进缓存键）。
- `implementer_report(specs, implementer)`：`specs` 是 `[{"id": "F1/whole", "spec": {...}}, ...]`（门槛的 `s09_cases.IMPLEMENTER_SPECS`）。按次序每条 `implement` 一次。返回 `{"specs": 条数, "first_ok": n, "final_ok": n, "first_rate": n/条数, "final_rate": n/条数, "by_kind": {类别: {"specs", "first_ok", "final_ok"}}, "rows": [...], "calls": 网关 totals()["by_role"] 里 "implementer" 那一项（没有就空 dict）}`；类别取 id 里 `/` 之后的部分；`rows` 每条 `{"id", "status", "tries", "first_ok", "ok", "missing", "forbidden", "undetermined", "expect"}`（tuple 写成 list）。
- 命令行：`python -m surprise.roles.implementer --specs FILE --cache DIR --out FILE [--seed N] [--max-calls N] [--offline]`。`FILE` 是上面那种列表的 JSON；不加 `--offline` 时用 `DeepSeekTransport()`（在函数里导入），加了就是离线（只用缓存）；网关账本写到 `--out` 旁边的 `<out 去掉后缀>.calls.jsonl`；报告写到 `--out`（UTF-8，`indent=1`）；`extract` 用 `surprise.features.extract`。标准输出只打一行 ASCII 摘要（通过率）。

### 3. 猜想者（`surprise/roles/conjecturer.py`）

```python
@dataclass(frozen=True)
class Conjecture:
    conjecture_id: str          # "c1", "c2", ... in the order the book receives them (every status gets one)
    record_id: str              # the failure that triggered it
    hypothesis_id: str          # the hypothesis it explains (see below)
    engine: str; oracle: str
    status: str                 # "registered" | "rejected" | "blocked" | "miss" | "error"
    reason: str | None          # why it was not registered
    mechanism: str | None
    trigger: tuple[str, ...]    # reduce_conjunction of the reply's trigger (empty when rejected)
    predictions: tuple[dict, ...]   # each {"spec": Spec.to_dict(), "expect": "pass"|"fail", "why": str}
    dropped: tuple[dict, ...]       # each {"index": i, "reason": str} for predictions left out
    edit_id: str | None; accepted: bool | None; edit_reason: str | None
    key: str | None             # cache key of the call
    sources: tuple[str, ...]    # "engine:path:start-end" of the snippets in the prompt
    def to_dict(self) -> dict

def select_sources(engine, hypothesis, phi, readers) -> tuple[Snippet, ...]
def conjecturer_prompt(*, engine, oracle, label, case, minimized, phi, hypothesis, snippets, registry=None) -> str
class Conjecturer:
    def __init__(self, *, gateway, extract, book, registry=None, sources=None, seed: int, tier=None): ...
    def after(self, wb, record, outcome) -> Conjecture | None: ...
```

- **何时调用**：`after` 只在 `outcome.observation.opened` 不为 None（这次实验开出了新家族）时做事，否则返回 None 且不调网关。要解释的假设：`wb.owner_of(record.record_id)`（同一步里 Diagnoser 可能已经改写过它）；为 None 或已不在理论里时退回 `opened`；仍不在理论里就返回 None。
- **喂给模型的材料**（提示里，全部按确定的次序）：目标引擎与 oracle；失败的类别、错误类别、行为形状（`record.label` 的 `fail_kind`、`identity`）；被执行的用例（`record.case` 的 setup 与 query）；最小复现（`record.label.cve["minimize"]["case"]`，在 `status == "ran"` 且 `reproduced is True` 时）；fix set（`hypothesis.interventions`）、计划差异（`hypothesis.plan_delta`）、版本梯（`hypothesis.versions`）；失败用例的 φ（`reduce_conjunction(Phi.from_dict(record.phi).features)`）；`select_sources` 选出的源码片段（每段以 `--- <engine>:<path> lines <start>-<end> ---` 开头）；可用的特征 id 与说明；要求的回复形状。
- **回复的 JSON**：`{"mechanism": "...", "trigger": [特征 id, ...], "prediction": [{"required": [...], "forbidden": [...], "data_properties": [...], "oracle": 可选, "expect": "pass" 或 "fail", "why": "..."}, ...]}`。提示里讲清：`trigger` 是这个缺陷被触发所需的特征合取（理论里的 S），必须是给出的 id；每条预测是一个还没做过的实验，写成规格（特征 id）与期望标签，要能被这个实验推翻；最多 `CONJECTURER_MAX_PREDICTIONS` 条；同时要有预期失败与预期通过的预测（"附近应该也坏" 与 "去掉某个条件就不坏"）。
- **检查**，依次（任何一条不过 → `status="rejected"`，`reason` 写明，什么都不登记、不提议）：网关状态不是 `ok` → 状态照搬（`blocked` / `miss` / `error`；网关拒收的是 `rejected`）；`mechanism` 不是非空字符串；`trigger` 不是非空的字符串列表，或有词表里没有的 id；`prediction` 不是列表。然后逐条检查预测，不合格的放进 `dropped`（带原因）：不是对象；`expect` 不是 pass / fail；`required`、`forbidden`、`data_properties` 不是字符串列表；有未知 id；`data_properties` 里有非 data 层的 id；`oracle` 给了却不在 `ORACLE_IDS`；`required` 与 `data_properties` 都为空；超过 `CONJECTURER_MAX_PREDICTIONS` 的部分。规格的 `engine` 一律是假设的引擎，`oracle` 默认是假设的 oracle；`required`、`forbidden`、`data_properties` 照抄回复里的列表（不排序、不约简），写成 `Spec(engine=..., oracle=..., required=tuple(...), forbidden=tuple(...), data_properties=tuple(...)).to_dict()`；`why` 照抄（没有就空串）。合格的一条也没有 → `rejected`（`reason="no_valid_prediction"`）。
- **登记**：合格的猜想 `status="registered"`，交给猜想簿（下一节），每条预测成为一条 `open` 的待检实验。
- **提议**：若 `trigger` 的每个字面量都在触发记录 φ 的闭包里（`registry.closure(Phi.from_dict(record.phi).features)`），经工作台提议：
  ```python
  template = dataclasses.replace(hypothesis, specific=trigger, source="conjecturer")
  p = Proposal(kind="revise", proposer="conjecturer", removes=(hypothesis.hypothesis_id,), adds=(template,),
               bets=tuple({"spec": pr["spec"], "expect": pr["expect"]} for pr in predictions),
               trigger=(record.record_id,), rationale=mechanism)
  edit = wb.propose(p)
  ```
  `edit_id = edit.edit_id`，`accepted = edit.decision == "accepted"`，`edit_reason` 取编辑 payload 里的拒绝原因（接受时为 None）。接受与否完全由 S7 的接受检验定。`trigger` 盖不住触发记录 → 不提议，`edit_id=None`、`accepted=None`、`edit_reason="not_covering"`，猜想照样登记。`wb.propose` 若抛 `ValueError`（例如编辑形状不合法）→ 不提议，`edit_reason` 写 `"proposal_error"`，猜想照样登记。
- **选源**（`select_sources`，确定、只读）：
  - DuckDB：fix set 里每个优化器名映射到 `src/optimizer/` 下的文件（例如 `filter_pushdown` → `src/optimizer/filter_pushdown.cpp`，`common_subexpressions` → `src/optimizer/cse_optimizer.cpp`，`statistics_propagation` → `src/optimizer/statistics_propagator.cpp`，`join_order` → `src/optimizer/join_order/` 下的主文件）。映射表写成模块里的一个字典，覆盖 `src/common/enums/optimizer_type.cpp` 里列出的、`src/optimizer/` 下有对应文件的那些名字；测试里逐条核对映射到的文件在 `.src/duckdb-v1.5.5` 里存在（读真实检出区可以，见"背景"）。
  - DataFusion（以及 fix set 为空时）：一张"特征 id 前缀 → 正则 + 子目录"的表。特征里有 `ast:set_op:*` 时必须选到 `datafusion/expr/src/logical_plan/builder.rs` 里 `fn intersect_or_except` 所在的那段（门槛检查）；其余构造（连接、子查询、窗口、聚合、排序）各给一两条合理的规则。
  - 命中的位置取前后若干行成段；同一文件相邻的段合并；文件按表里的次序、段按行号；总共不超过 `SOURCE_MAX_FILES` 个文件、`SOURCE_MAX_LINES` 行。读不到（检出区不在、路径不存在）就跳过，不抛异常。
- 猜想者自己不读密钥、不导入 `surprise.roles.transport`。

### 4. 猜想簿（`surprise/roles/conjecturer.py` 里，`ConjectureBook`）

```python
@dataclass(frozen=True)
class Pending:
    conjecture_id: str; index: int; spec: dict; expect: str
    state: str                 # "open" | "kept" | "broken"
    record_id: str | None      # the experiment that settled it

class ConjectureBook:
    def __init__(self, path=None): ...          # path: a JSONL file, created if missing, read back if present
    path: Path | None (property)
    def next_id(self) -> str: ...               # "c<n+1>"
    def add(self, conjecture) -> None: ...      # any status; only "registered" ones get pending experiments
    def conjectures(self) -> tuple[dict, ...]: ...   # to_dict() of every one received, in order
    def pending(self, state="open") -> tuple[Pending, ...]: ...   # state=None: all
    def observe(self, phi, label, record_id) -> tuple[Pending, ...]: ...   # those settled by this experiment
    def summary(self) -> dict: ...  # {"conjectures": registered, "rejected": others, "predictions", "open", "kept", "broken"}
```

- 一条待检实验在第一个"命中它"的有效实验上了结：`label.y != "invalid"`、`label.oracle == spec["oracle"]`、`check_spec(phi, Spec.from_dict(spec)).ok`（就是 `surprise.theory.bet_matches` 的判法，直接用它）。`label.y == expect` 为 `kept`，否则 `broken`，记下 `record_id`。已了结的不再变。按猜想次序、预测次序逐条看。
- 文件：每次 `add` 追加一行 `{"type": "conjecture", ...to_dict()}`，每次了结追加一行 `{"type": "settle", "conjecture_id", "index", "state", "record_id"}`（`ensure_ascii=True`）。打开已有文件时按行重放，得到同样的状态。
- 猜想号由 `next_id()` 给，`Conjecturer` 在构造 `Conjecture` 之前取号，然后 `book.add`（任何状态都 add，所以拒收的也有号、也留痕）。

### 5. 角色集合与候选来源（`surprise/roles/runtime.py`）——与 `s09-wire` 的接口，必须照写

```python
def build_roles(config: dict, *, run_dir, extract, registry, engines, seed) -> RoleSet
class RoleSet:
    sources: tuple            # candidate sources for the Hunter (one ImplementerSource when the implementer is on)
    def observe(self, phi, label, record_id) -> tuple: ...    # settle the book; returns the settled Pending
    def after(self, wb, record, outcome): ...                 # the conjecturer, when it is on; returns the Conjecture or None
    def step(self) -> dict: ...                               # the progress row's "llm" value for the step just done
    def manifest(self) -> dict: ...
    def report(self) -> dict: ...
    def close(self) -> None: ...

class ImplementerSource:
    def __init__(self, implementer, book, *, engines, per_choice=None): ...
    def candidates(self, wb, *, index: int, round: int) -> list: ...   # list of surprise.hunter.Candidate
```

- `config`：`{"roles": [...], "cache": str, "max_calls": int 或 None, "network": bool, "transport": 可选对象}`；`roles` 是 `"implementer"`、`"conjecturer"` 的非空子集。传输：给了 `transport` 就用它；否则 `network` 为真用 `DeepSeekTransport()`（在 `build_roles` 里才导入），为假用 None（离线）。一个 `RoleSet` 一个网关（`cache_dir=config["cache"]`，`ledger_path=run_dir/"llm"/"calls.jsonl"`，`max_calls=config["max_calls"]`）。猜想簿在 `run_dir/"llm"/"conjectures.jsonl"`，实现器的每次尝试追加到 `run_dir/"llm"/"implementer.jsonl"`（`Attempt.to_dict()` 加上 `"lane"`、`"index"`）。两个角色的种子都是 `seed`。源码读取器用 `open_sources()`；检出区不在时（`SourceError`）用空的读取器集合，猜想者照样工作（只是提示里没有源码）。
- 只开猜想者时 `sources` 为空元组；只开实现器时 `after` 返回 None。猜想簿两种情况下都在（只开实现器时它一直是空的）。
- `ImplementerSource.candidates`：
  - 目标队列，次序：先是猜想簿里 `open` 的待检实验（猜想次序、预测次序；规格的引擎不在 `engines` 里的跳过），车道 `"bet"`；再是理论里每个假设（`wb.theory.hypotheses` 的次序；引擎在 `engines` 里、`oracle` 不为 None）的边界目标，车道 `"implement"`：取 `S` 里 ast 层与 data 层的字面量（`layer_of`），按字典序对每个字面量 `l` 生成 `Spec(engine, oracle, required=reduce_conjunction(其余 ast/data 字面量), forbidden=(l,))`，`required` 为空的跳过。同一个规格（`to_dict()` 相等）只实现一次。
  - 每个 `index`（一次选择）最多为 `per_choice`（默认 `IMPLEMENTER_PER_CHOICE`）个新目标调用实现器，只在这个 `index` 的第一次调用时做（`round` 大于 1 时不再新调）。
  - 返回值：所有 `ok` 的尝试各一个 `Candidate(case=attempt.case, oracle=spec.oracle, rule=..., lane="bet" 或 "implement", hypothesis_id=..., parent=None, op="implementer", target=attempt.spec)`，次序固定（按尝试的先后）。`rule`：oracle 是 `equivalent_query` 时取 `oracle_options(case, [oracle])` 的第一个规则（没有就不出这个候选），否则 None。`hypothesis_id`：边界目标是那个假设的号；待检实验是猜想解释的假设号。已经做过的用例由 Hunter 自己过滤（它会把同一个用例算作"已做过"），这里不必管。
- `step()`：返回 `{"calls": {角色: {状态: 次数}}, "conjecture": [猜想号, 状态] 或 None, "settled": [[猜想号, 序号, 状态], ...], "attempts": [状态, ...]}`，只含上次 `step()` 之后这一步发生的事，然后清零。**不得含 `source`、耗时、token 数**（重放时它们会变，门槛要求逐行相同）。
- `manifest()`：`{"roles": [...], "tiers": TIERS, "max_calls": 有效上限, "network": bool, "seed": seed, "constants": constants.as_dict(), "sources": {引擎: {"dir": 目录名, "commit": 读到的提交号或 None}}}`。
- `report()`：`{"roles": [...], "calls": 网关.totals(), "book": 猜想簿.summary(), "implementer": {"attempts", "ok", "first_ok", "by_status": {...}}}`。
- `close()`：关文件。

### 6. 导出

在 `surprise/roles/__init__.py` 里追加：`Attempt`、`Implementer`、`implementer_prompt`、`implementer_report`、`Conjecture`、`Conjecturer`、`ConjectureBook`、`Pending`、`select_sources`、`conjecturer_prompt`、`RoleSet`、`ImplementerSource`、`build_roles`。导入 `surprise.roles`（以及 `implementer`、`conjecturer`、`runtime` 三个模块）不得加载 `httpx`、`agents`、`llm`、`openai` 等模块（门槛 `isolation` 组在新进程里核对）。

### 7. 测试

`framework/tests/test_surprise_roles_implementer.py`、`test_surprise_roles_conjecturer.py`、`test_surprise_roles_runtime.py`：覆盖上面每一条规则，用假传输（照 `gates/s09.py` 的 `Script`），不做真实调用。要用引擎的测试用 DuckDB（在进程里，快）；需要一个开出新家族的工作台时，可以照 `gates/s09.py` 的 `dfa()` 写，但 DataFusion 一次判定约 10 秒，测试里最多用一两次。

## 真实调用

派发时给了你 `DEEPSEEK_API_KEY`（环境变量，值不要打印、不要写进任何文件）与 `SURPRISE_LLM_MAX_CALLS`（网关会把每个实例的上限压到这个数）。只允许用它做下面两件事，总共的真实调用不超过 **60 次**：

1. 把实现器的提示在真模型上跑通：`python -m surprise.roles.implementer --specs <你从 s09_cases.IMPLEMENTER_SPECS 导出的 JSON> --cache .orch/tmp/llmcache --out .orch/tmp/impl_report.json`，看通过率，改提示。
2. 把猜想者的提示在 DF-A 上跑通：照 `gates/s09.py` 的 `dfa()` 建出 DF-A 的工作台，用 `DeepSeekTransport()` 的网关调一次 `Conjecturer.after`，看它是不是 `registered`、预测是否合格，改提示。

缓存与报告只放 `.orch/tmp/`（不入库）。报告里写清：做了几次真实调用（以网关账本为准）、最后一版提示下实现器的通过率、DF-A 上的猜想（机制、trigger、预测）。正式的录制由编排者在合并之后做，你录的缓存不会被用到。没有密钥（环境变量为空）时跳过这一节，在报告里注明。

## 背景

- `.src/duckdb-v1.5.5` 与 `.src/datafusion-54.0.0` 在主检出区（`D:\CoevoDB\.src`）；`open_sources()` 在 worktree 里也能找到它们（网关包已实现）。测试里读真实检出区可以，但只读，不写。
- 词表里与集合运算有关的 id：`ast:set_op:except_all`、`ast:set_op:intersect_all`、`ast:set_op:except`、`ast:set_op:intersect`、`data:setop:left_has_dups`、`data:setop:right_has_dups`、`data:setop:left_has_null`、`data:setop:right_has_null`。
- `wb.propose` 的规则（接受检验、押注、负记忆）见 HANDOFF 里 S7 一节的"规则"；押注的形状 `{"spec": 规格 dict, "expect": "pass" | "fail"}`。
- 门槛的 `conjecturer` 组给的假回复见 `s09_cases.GOOD_TRIGGER`、`GOOD_PREDICTIONS`、`MECHANISM`。

## 允许改动的路径

```allow-paths
framework/surprise/roles/__init__.py
framework/surprise/roles/constants.py
framework/surprise/roles/implementer.py
framework/surprise/roles/conjecturer.py
framework/surprise/roles/runtime.py
framework/surprise/roles/sources_map.py
framework/tests/test_surprise_roles_implementer.py
framework/tests/test_surprise_roles_conjecturer.py
framework/tests/test_surprise_roles_runtime.py
```

（`sources_map.py` 可选：选源的两张表想单独放一个文件就放这里。）

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`（已冻结），也不改 `roles/` 里网关包的文件（`schema.py`、`cache.py`、`gateway.py`、`transport.py`、`source.py`；`constants.py` 只按第 0 节改一行）与它的两个测试文件与 `framework/surprise/` 下除 `roles/` 以外的任何目录。觉得其中哪个非改不可，写进报告，停下。
- 旧代码（`framework/surprise/` 以外）一行都不改。
- 角色不产生、不修改任何标签；不调用 `evaluate_final` 以外的判定路径（测试与真实调用一节里为了建出 DF-A 的工作台调 `evaluate_final` 可以）。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。某个测试确实该改，就写进报告的"未决问题"，停下。
- 真实调用只按"真实调用"一节做，总数不超过 60 次。密钥只走环境变量，不打印，不写进代码、配置、日志、提交或报告。
- 不往 `.src/` 写任何东西；不往 `framework/results/` 写东西。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不建指向 worktree 之外的链接或目录联接；不要清理 `.orch/tmp`；测试产生的临时文件只放 pytest 的 `tmp_path`。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests       # 通过数不少于网关包合并后的数目（见 git log 里的合并提交，或先在起点跑一次记下），skip 仍是 3
python -m surprise.gates.s09 --only isolation constants cache reject cap source implementer conjecturer    # 8/8
python -m surprise.gates.s08 --only no_llm     # 1/1
```

`wiring` 要等 `s09-wire`，`implementer_report`、`dfa`、`replay` 要等编排者录制，都不用跑；`python -m surprise.gates.all` 也不用跑。在报告里注明。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s09-roles

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 真实调用
次数（以网关账本为准）、实现器的通过率、DF-A 上的猜想。没有密钥就写"跳过"。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
