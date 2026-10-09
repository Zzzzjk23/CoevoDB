角色：执行者

# 工作包 s07-store：理论的落盘存储——每个假设一个文件、只追加的日志、按代快照

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s07-store`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s07`（从 `s06-done-r2` 建立，只多了 S7 的门槛文件）
- 所属会话：S7（Phase 3b：理论存储与接受规则），范围见 `framework/surprise/docs/SESSIONS.md` 的 S7 一节
- 依赖：S6 的理论核心已在 `framework/surprise/theory/`，先把这个目录读一遍（尤其 `theory.py`、`vspace.py`、`contracts.py`、`constants.py`）。`framework/surprise/harness/`（已冻结）与 `framework/surprise/features/` 只读不改
- 本包是 S7 两个串行包里的第一个。下一个包（`s07-accept`：编辑、接受规则、回滚、负记忆、MDL）建在本包的接口上，所以本包的接口照下面写的做，不要改名

## 目标

依据 `framework/surprise/docs/PLAN.md` 第 4 节契约表、第 5 节 Phase 3（"按代快照、编辑日志、自动回滚、负记忆、MDL"）、第 6 节决策 8。本包只做"存"：把 S6 的 `Theory` 落到磁盘上，一个假设一个结构化文件，另有三份只追加的日志和按代的快照；再给 `Theory` 和合取语言补几个下一个包要用的小接口。全部是纯逻辑加文件读写：不连接引擎，不执行 SQL，不调用任何模型。

验收以 `framework/surprise/gates/s07.py` 的五组 `constants length theory_api store generations` 为准（其余十组属于下一个包，现在是红的，不用管）。先把这五个 `check_*` 函数读一遍：门槛用到的名字、参数、返回值、文件名都在下面写明，照写。门槛的手工 φ 与标签借用 `gates/s06.py`、`gates/s06_cases.py`。

下面所有名字都要能从 `surprise.theory` 直接导入，并且列进 `surprise/theory/__init__.py` 的 `__all__`。

### 1. 常数（`theory/constants.py`，追加四项）

```python
# Fixed cost, in bits, of holding one more hypothesis in the theory.
MDL_HYPOTHESIS_BITS = 8.0

# Cost, in bits, of one literal of S: about log2 of the size of the vocabulary.
MDL_LITERAL_BITS = 7.4

# Largest number of held-out records one acceptance test reads.
ACCEPT_HOLDOUT_MAX = 1000

# A change in surprise smaller than this, in bits, counts as no change.
ACCEPT_TOLERANCE_BITS = 1e-9
```

类型照写（三个 `float`，`ACCEPT_HOLDOUT_MAX` 是 `int`）。原有九项的名字、取值、类型一处不许动（`gates/s06.py` 钉着）。`as_dict()` 会自动收集新常数，`theory_manifest()` 因此自动带上它们，`manifest.py` 不用改。

### 2. `Theory` 的四个补充（`theory/theory.py`，只加不改）

`Theory.predict`、`Theory.observe`、`to_dict` / `from_dict`、`version`、`put`、`get` 的行为一处不许变（S6 的门槛与测试钉着）。新增：

- 属性 `next_id -> int`：下一次铸造假设编号时起始的那个数，等于 `to_dict()["next_id"]`。
- `remove(hypothesis_id) -> Hypothesis`：把这个假设从理论里拿掉并返回它；其余假设的次序不变；编号不存在抛 `KeyError`。
- `reserve_id() -> str`：照新家族铸造编号的同一规则（从 `next_id` 起，跳过已被占用的 `h{n}`）取一个编号返回，并把计数器推进到它之后；不创建任何假设。它与 `_open_family` 必须共用同一段逻辑，保证两条路铸出的编号永不重复。
- `passes(engine, oracle) -> tuple[tuple[Phi, str], ...]`：这个作用域里记住的通过，`(phi, record_id)`，先来的在前；没有就是空元组。

### 3. 两个合取的共同部分（`theory/vspace.py`）

`common_conjunction(first, second, registry=None) -> tuple[str, ...]`：两个合取的闭包之交，再约简。即 `reduce_conjunction(registry.closure(first) & registry.closure(second))`。它是"被两者同时蕴含的最特殊的合取"：`common_conjunction(S, reduce_conjunction(phi.features)) == generalize(S, phi)`；对称、幂等；与空合取的共同部分是空合取；`(except_all,)` 与 `(intersect_all,)` 的共同部分是 `("ast:set_op:all",)`。含未知特征抛 `ValueError`（与同文件其他函数一致）。

### 4. 描述长度（新文件 `theory/length.py`）

- `hypothesis_length(hypothesis) -> float`：`MDL_HYPOTHESIS_BITS + MDL_LITERAL_BITS × len(hypothesis.specific)`。G、E⁺、E⁻、来源都不计入。
- `theory_length(theory_or_hypotheses) -> float`：对各假设求和。参数可以是 `Theory`，也可以是一串 `Hypothesis`；空理论是 `0.0`（`float`）。

### 5. 存储（新文件 `theory/store.py`）

`StoreError(ValueError)`：存储不存在、损坏、或与要存的东西对不上时抛它。**读盘途中遇到的任何问题（缺文件、不是 JSON、结构不对、`Hypothesis.from_dict` / `Theory.from_dict` / `Phi.from_dict` / `TheoryEdit.from_dict` 抛的 `ValueError`）一律包成 `StoreError`，消息里带出问题的文件名。** 绝不"悄悄修好"再返回。

`TheoryStore`：一个目录下的全部文件。只通过两个类方法得到实例：

- `TheoryStore.create(root, registry=None)`：`root` 不存在，或是空目录；否则 `StoreError`。建立下面的目录结构，其中的理论是空的 `Theory(registry)`，三份日志是空文件，代号为 0，没有任何快照文件。
- `TheoryStore.open(root, registry=None)`：`root / "head.json"` 不存在即 `StoreError`；打开时就校验 `head.json`（见下）并读一遍 `journal.jsonl` 以确定下一个序号。
- `registry=None` 时用 `surprise.features.registry.default_registry()`。

目录结构（文件名照写）：

```
<root>/
  head.json                  # {"schema": 1, "vocab": 词表摘要, "generation": 当前代号, "next_id": n,
                             #  "hypotheses": [编号，按理论里的次序], "version": Theory.version}
  hypotheses/<编号>.json     # 每个假设一个文件，内容恰好是 Hypothesis.to_dict()
  residual.json              # Residual.to_dict()
  validity.json              # Validity.to_dict()
  passes/<引擎>__<oracle>.jsonl   # 该作用域记住的通过，一行一个 {"phi": ..., "record_id": ...}，先来的在前
  journal.jsonl              # 只追加：理论经历的事件
  edits.jsonl                # 只追加：编辑日志，一行一个 TheoryEdit.to_dict()
  negative.jsonl             # 只追加：负记忆
  generations/g<六位代号>.json   # 每个已结束的代一个快照，如 g000000.json
```

写文件的规矩：UTF-8，换行一律 `\n`（打开时传 `newline="\n"`，不要让 Windows 改成 `\r\n`）；JSON 用 `sort_keys=True, ensure_ascii=False`；`.json` 文件用 `indent=1` 并以换行结尾，`.jsonl` 每行用 `separators=(",", ":")`。**覆盖已有文件一律先写同目录的临时文件（名字以 `.tmp` 结尾）再 `os.replace`**，收尾后目录里不许留下 `.tmp` 文件。内容没变的文件不要重写。

属性与方法：

- `root -> Path`；`last_seq -> int`（日志里最后一条的序号，空日志为 0）。
- `head() -> dict`：读并校验 `head.json`：键恰好是上面六个；`schema` 是 1；`vocab` 等于 registry 的摘要；`generation` 是 ≥ 0 的整数，`next_id` 是 ≥ 1 的整数（`bool` 不算整数）；`hypotheses` 是互不相同的合法编号组成的 list；`version` 是字符串。任何一条不满足：`StoreError`。
- `save(theory) -> None`：把理论的当前状态写成上面的文件。
  - 假设编号必须匹配 `^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$`，引擎名同此规则；有不合的就抛 `StoreError`，**并且在写任何文件之前抛**（被拒的 `save` 不改动磁盘上的任何东西，更不会写到 `root` 之外）。
  - 理论的词表摘要与存储不一致：`StoreError`。
  - 理论里已经没有的假设，它的文件要删掉；已经没有通过的作用域，它的 `passes` 文件要删掉。
  - `head.json` 最后写；`generation` 保持不变。
- `load() -> Theory`：读回理论，严格校验，见下一小节。
- `append_journal(entry) -> int`：`entry` 必须是带字符串 `kind`、且不带 `seq` 的 dict，否则 `ValueError`（不写）。序号从 1 起逐条加一，写进这一行的 `"seq"` 键，返回它。重新 `open` 之后接着编号。
- `journal(after=0) -> list[dict]`：序号大于 `after` 的全部条目，按序。读的时候校验第 i 行的 `seq` 恰好是 i、`kind` 是字符串，不对就 `StoreError`（所以日志被截掉一行、被改过，`open` 就会失败）。
- `append_edit(edit) -> None`：参数必须是 `TheoryEdit`（否则 `ValueError`），追加一行。同一个 `edit_id` 可以追加多次，每次是它的新状态。
- `edit_history() -> list[TheoryEdit]`：每一行，按写入次序。`edits() -> list[TheoryEdit]`：每个 `edit_id` 的最新状态，按该编号第一次出现的次序。
- `append_negative(entry) -> None`：`entry` 必须是带非空字符串 `fingerprint` 的 dict，否则 `ValueError`。`negatives() -> list[dict]`：全部条目，按序。
- `close_generation(theory, *, cause) -> int`：把 `theory` 作为**当前这一代的收尾状态**写成快照 `generations/g<代号>.json`，然后把 `head.json` 的 `generation` 加一，返回刚结束的那一代的代号（第一次调用返回 0）。`cause` 必须是非空字符串，否则 `ValueError`。快照文件的内容：`{"schema": 1, "generation": 代号, "cause": cause, "journal_seq": 当时的 last_seq, "version": theory.version, "theory": theory.to_dict()}`。同一个代号的文件已经存在：`StoreError`，不覆盖。**这个方法不改动磁盘上的"当前状态"**（假设文件、residual、validity、passes，以及 `head.json` 里除 `generation` 之外的键都不动）：调用之后 `load()` 读回的仍是上一次 `save` 的理论。
- `generations() -> list[dict]`：已结束各代的 `{"generation", "cause", "journal_seq", "version"}`，按代号。
- `load_generation(generation) -> Theory`：读回那一代的收尾状态。参数不是 ≥ 0 的整数（`bool`、字符串、浮点都不算）：`ValueError`。该代还没有快照（包括当前正在进行的那一代）：`StoreError`。读回后核对 `Theory.version` 与文件里记的 `version`，不一致：`StoreError`。
- `verify() -> list[str]`：把能查的都查一遍，返回问题清单，空表示没问题。至少包括：`load()` 能成功；`journal()`、`edit_history()`、`negatives()` 能读；快照文件的代号恰好是 `0 .. head.generation − 1`、一个不缺；每个快照都能 `load_generation`。每条问题是一行 ASCII 文本（非 ASCII 字符转义掉），遇到 `StoreError` 不向外抛、而是记成一条问题。

#### `load()` 的严格校验

S6 的 `Theory.from_dict` 对来路不明的状态过于宽容（重复编号取后一个、非规范形式悄悄规范化、不核对通过里 φ 的词表）。这些它保持原样不动，由 `load()` 在外面补严。下面每一种都必须抛 `StoreError`，不许返回一个"修好的"理论：

1. `hypotheses/` 下的 `.json` 文件集合与 `head.json` 的 `hypotheses` 不是同一个集合（多了、少了）。
2. 某个假设文件不是合法的 `Hypothesis`，或者文件里的 `hypothesis_id` 与文件名不一致。
3. 某个假设文件不是规范形式：按 `head.json` 的次序经 `Theory.from_dict` 读入之后，`theory.get(编号).to_dict()` 与文件内容不相等（例如 `specific` 没排序、带着多余的祖先）。
4. `passes/` 的某一行不是合法的 φ；φ 的 `vocab` 不是本存储的词表摘要；同一个文件里同一个 φ 出现两次。
5. `residual.json`、`validity.json` 被 `from_dict` 拒绝。
6. 读回的 `Theory.version` 与 `head.json` 的 `version` 不相等。这一条兜住一切手改：任何一个文件被改过而 `head.json` 没跟着改，版本就对不上。

正常情况下 `store.load().to_dict() == theory.to_dict()`，版本号相同，预测相同。

### 6. 测试

新测试放 `framework/tests/test_surprise_s07_*.py`（文件名自定，例如 `test_surprise_s07_store.py`、`test_surprise_s07_length.py`、`test_surprise_s07_theory_api.py`）。临时目录用 pytest 的 `tmp_path`。至少覆盖：四个常数的取值与类型；长度；`Theory` 的四个补充（含 `reserve_id` 与新家族铸号交替使用时不重号）；`common_conjunction` 的几条性质；存储的往返、缩小后删文件、非法编号在落盘之前被拒、上面"严格校验"六种情况各至少一例、三份日志的追加与读回、重新打开后序号接续、快照的写入 / 列出 / 读回 / 不覆盖 / 不动当前状态、`verify()` 在好的和坏的存储上的输出。

一处**定向更新**旧测试，只许改这两点：

- `framework/tests/test_surprise_s06_constants.py` 的 `EXPECTED`：在原有九项之后加上本包的四项（名字与取值照第 1 节）。原有九项不动；`assert constants.as_dict() == EXPECTED` 仍然是精确相等，不许改成"包含"。
- 同一个文件里新进程打印 `sorted(constants.as_dict())[0]` 的那一处：新常数按字母序排在 `P_CONFIRMED` 之前，会让它打印别的名字。把打印的内容改成整个 `sorted(constants.as_dict())`，后面 `"P_CONFIRMED" in completed.stdout` 的断言原样保留。（`gates/s06.py` 里同样的一处编排者已经改好。）

别的旧测试不许动。认为还有哪个旧测试非改不可，写进报告，停下。

## 背景

- 为什么快照存"收尾状态"：下一个包接受一条编辑之前先把当时的理论封存成一代，回滚这条编辑时从这份快照出发、把之后的观察重放一遍。所以 `close_generation` 收到的是"编辑之前"的理论，并且不能动磁盘上的当前状态。
- `Theory.to_dict()` 里 `passes` 的键是 `"引擎|oracle"`，文件名里的分隔符是两个下划线。oracle 编号（`surprise.harness.contracts.ORACLE_IDS`）本身只含小写字母与下划线。
- `Theory.version` 是 `to_dict()` 的规范 JSON 的哈希，假设的次序、`next_id` 都在里面，所以 `head.json` 记下的次序与 `next_id` 被改也会被第 6 条查出来。
- 理论层与特征层互相导入（`features/spec.py` 导入 `theory/contracts.py`）。理论层只能从特征层的**子模块**导入（`surprise.features.phi`、`surprise.features.registry` 等），不要 `from surprise.features import ...`。`gates/s06.py` 的 `constants` 组在新进程里查四种导入顺序。
- 这台机器的控制台打印中文是乱码，文件本身是 UTF-8，没有问题；判断结果看 ASCII 关键字。
- 代码风格照 `framework/surprise/theory/` 里已有的文件：英文 docstring 与注释，类型标注，不写多余的防御代码。

## 允许改动的路径

只改下面这些路径（`**` 跨目录，`*` 不跨）。审查按这个清单逐个文件核对，清单以外的任何改动都算越界。

```allow-paths
framework/surprise/theory/constants.py
framework/surprise/theory/theory.py
framework/surprise/theory/vspace.py
framework/surprise/theory/length.py
framework/surprise/theory/store.py
framework/surprise/theory/__init__.py
framework/tests/test_surprise_s07_*.py
framework/tests/test_surprise_s06_constants.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`（已冻结）、`framework/surprise/features/`。
- 旧代码（`framework/surprise/` 以外）本包不碰。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。某个测试确实该改，就写进报告的"未决问题"，停下。
- 标签路径上不调用 LLM；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。本包不需要任何 LLM 调用，也不需要网络。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不改 S6 已有函数与方法的行为（只许新增）；不做编辑、接受规则、回滚、负记忆、MDL、Workbench（下一个包）；不新建 `theory/edits.py`、`theory/workbench.py`。
- 不建指向 worktree 之外的链接或目录联接；不要清理 `.orch/tmp`；测试产生的临时文件只放 pytest 的 `tmp_path`。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
pytest -q testing tests                 # 通过数不少于 514，skip 仍是 3
python -m surprise.gates.s07 --only constants length theory_api store generations    # 最后一行 S07 GATE ... PASS (5/5 groups passed)
python -m surprise.gates.s06            # 仍然 PASS (12/12 groups passed)，约半分钟
python -m surprise.harness.manifest verify surprise/gates/s04_frozen.json            # 退出码 0：冻结区没动
```

`python -m surprise.gates.all` 约 6 分钟，其中 S07 整个门槛此时是 FAIL（另外十组属于下一个包），这是预期的，不用为它做任何事；S01–S06 必须仍是 PASS。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s07-store

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
