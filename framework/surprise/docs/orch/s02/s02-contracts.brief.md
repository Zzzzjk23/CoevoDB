角色：执行者

# 工作包 s02-contracts：五个数据契约、harness 常数、SQLite 实验账本

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s02-contracts`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s02`（f19ed29）
- 所属会话：S2（Phase 1a · 契约、账本、冻结机制、三类健全 oracle），范围见 `framework/surprise/docs/SESSIONS.md` 的 S2 一节
- 依赖：无。本包是 S2 的共享接口，合并之后另外两个包（manifest、oracle 适配器）才开工，它们会直接用这里定下的名字和签名，所以**名字、字段、签名必须和下面写的一字不差**。

## 目标

四个模块加两个测试文件。契约的含义以 `framework/surprise/docs/PLAN.md` 第 4 节的"数据契约"表为准；下面给出的是这张表落到代码上的字段。门槛 `framework/surprise/gates/s02.py` 里的 `check_contracts` 和 `check_ledger` 是可执行的验收标准，开工前先读一遍。

通用要求：
- 只用标准库（`dataclasses`、`json`、`sqlite3` 等），不引入新依赖。代码里的注释和文档字符串用英文，和仓库现有代码一致。
- 契约都是 `@dataclass(frozen=True)`。声明为 `tuple[...]` 的字段，构造时传 list 也要接受，在 `__post_init__` 里转成 tuple（嵌套的也转）。
- 每个契约类都有四个方法：`to_dict()`（只含 JSON 原生类型，tuple 输出为 list，嵌套契约输出为 dict）、`from_dict(data)`（类方法）、`to_json()`（`json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False, separators=(",", ":"))`）、`from_json(text)`（类方法）。要求 `cls.from_dict(json.loads(json.dumps(obj.to_dict()))) == obj`。
- `from_dict` 遇到缺少的可选键用默认值；缺少必填键或出现未知键，抛 `ValueError`。
- 校验失败一律抛 `ValueError`，信息里写明是哪个字段、什么值。

### 1. `framework/surprise/harness/contracts.py`（harness 写出的契约）

不 import 旧代码（`oracles`、`targets` 等），也不 import `surprise` 的其他层。

```python
SCHEMA_VERSION = 1
LABELS = ("pass", "fail", "invalid")
ORACLE_IDS = ("tlp", "norec", "plan_variant", "index_presence", "equivalent_query",
              "version_differential", "cross_dbms")          # PLAN.md 第 3 节的七类
FAIL_KINDS = ("wrong_result", "error_mismatch", "crash")
INVALID_REASONS = ("setup_error", "nondeterministic", "not_applicable", "query_error",
                   "value_dependent_error", "timeout", "harness_error")
```

`FAIL_KINDS` 是 fail 的子类型（PLAN："崩溃与内部错误……是 fail 的子类型"）；`INVALID_REASONS` 是 invalid 来源的统一登记处（PLAN Phase 1："invalid 来源统一登记"），之后的会话会往里加。每个常量上面用一行注释说明各取值的含义：

- `wrong_result` 两种形式的结果不一致；`error_mismatch` 一种形式报错（且不是值依赖错误）而另一种成功；`crash` 引擎内部错误。
- `setup_error` 建表或插数语句失败；`nondeterministic` 查询结果依赖未指定的顺序或随机函数；`not_applicable` 不满足这个 oracle 的前提；`query_error` 查询或谓词本身报错（坏用例）；`value_dependent_error` 值依赖的运行时错误（溢出、类型转换失败等），是否触发取决于求值顺序；`timeout` 超时，没有结论；`harness_error` 判定过程中 harness 自己抛了异常。

四个类：

```python
class SqlCase:                     # x：一个可执行的测试用例
    engine: str                    # 非空，如 "duckdb"
    setup: tuple[str, ...]         # 建表与插数语句，按顺序；可以为空
    query: str                     # 被测查询，非空
    predicate: str | None = None   # 划分谓词，TLP / NoREC 需要；没有就是 None

class IdentityEvidence:            # 身份证据
    switches: tuple[str, ...] = () # 开关 I：见证差异的干预（如 plan variant 的标签）
    error_class: str | None = None # 错误类别
    behavior: dict = {}            # 行为画像：结果差异的形状，JSON 对象

class Label:                       # y 及其证据
    y: str                         # LABELS 之一
    oracle: str                    # ORACLE_IDS 之一
    fail_kind: str | None = None
    invalid_reason: str | None = None
    identity: IdentityEvidence = IdentityEvidence()
    cve: dict = {}                 # CVE 各步结果（rerun / premise / minimize / profile），S4 填，现在是空
    detail: dict = {}              # 原始证据，JSON 对象

class ExperimentRecord:            # 实验记录：通过与无效也全存
    record_id: str                 # 非空，全账本唯一
    run_id: str                    # 非空
    seq: int                       # run 内序号，从 1 起
    case: SqlCase
    label: Label
    purpose: str                   # 目的，非空
    created_at: str                # ISO 8601 时间
    spec: dict | None = None       # 这个用例对应的规格（序列化后的 Spec）
    phi: dict | None = None        # φ(x)，S5 填
    theory_version: str | None = None   # 理论代号
    p_t: float | None = None       # 执行前理论给出的 P_T，取值 0 到 1
    surprise: float | None = None  # 惊讶（比特）
```

（上面是字段清单，不是可以直接粘贴的代码：`dict` 类型的默认值要用 `field(default_factory=dict)`，`identity` 的默认值同理。）

`Label` 的校验：`y` 不在 `LABELS`、`oracle` 不在 `ORACLE_IDS` 都抛 `ValueError`；`y == "fail"` 时 `fail_kind` 必须在 `FAIL_KINDS` 且 `invalid_reason` 为 None；`y == "invalid"` 时 `invalid_reason` 必须在 `INVALID_REASONS` 且 `fail_kind` 为 None；`y == "pass"` 时两者都必须为 None。`ExperimentRecord` 的校验：`seq` 是不小于 1 的整数；`p_t` 不为 None 时在 0 到 1 之间；非空字段不能是空串。

### 2. `framework/surprise/theory/contracts.py`（理论侧的契约）

可以 import `surprise.harness.contracts`（用 `ORACLE_IDS`，序列化的公共代码也可以放在 harness 那边复用），反过来不行。这三个类在 S5–S7 还会细化，现在只做类型和序列化。

```python
EDIT_DECISIONS = ("pending", "accepted", "rolled_back")

class Spec:                        # 规格：对 φ 的约束
    engine: str                    # 目标引擎
    oracle: str                    # 目标 oracle，ORACLE_IDS 之一
    required: tuple[str, ...] = ()        # 必须特征
    forbidden: tuple[str, ...] = ()       # 禁止特征
    data_properties: tuple[str, ...] = () # 数据性质

class Hypothesis:                  # h = (I, ΔP, V, S, G, E⁺, E⁻) + 来源、状态
    hypothesis_id: str
    engine: str
    interventions: tuple[str, ...]        # I
    plan_delta: tuple[str, ...]           # ΔP
    versions: dict                        # V
    specific: tuple[str, ...]             # S：一个合取
    general: tuple[tuple[str, ...], ...]  # G：若干个合取
    positives: tuple[str, ...]            # E⁺：实验记录的 record_id
    negatives: tuple[str, ...]            # E⁻
    source: str                           # 来源
    status: str                           # 状态

class TheoryEdit:                  # 理论编辑
    edit_id: str
    kind: str                      # 类型
    rationale: str                 # 理由
    bets: tuple[dict, ...]         # 押注预测
    surprise_delta_in: float | None    # 留入惊讶变化
    surprise_delta_out: float | None   # 留出惊讶变化
    decision: str                  # EDIT_DECISIONS 之一
    proposer: str                  # 提出者
    theory_version: str | None = None
    payload: dict = {}             # 编辑内容
```

校验：`Spec.oracle` 不在 `ORACLE_IDS`、`TheoryEdit.decision` 不在 `EDIT_DECISIONS` 都抛 `ValueError`。

### 3. `framework/surprise/harness/constants.py`

harness 的数值常数集中放这里，之后写进 run manifest。现在只有一个：

```python
QUERY_TIMEOUT_S = 10.0     # 单条语句的墙钟超时，与旧 oracle 的默认值相同

def as_dict() -> dict:     # 本模块所有大写的公开常量，名字 -> 值，JSON 安全
```

`as_dict()` 要自动收集（之后的会话往模块里加常量时不用再改它）。

### 4. `framework/surprise/harness/ledger.py`（SQLite 实验账本）

```python
class LedgerError(Exception): ...

class Ledger:
    def __init__(self, path)                       # 打开或新建 SQLite 文件，建表
    def close(self) -> None                        # 也支持 with 语句
    def start_run(self, run_id: str, manifest: dict) -> None
    def run_manifest(self, run_id: str) -> dict
    def run_ids(self) -> list[str]                 # 按创建顺序
    def next_seq(self, run_id: str) -> int         # 空 run 返回 1
    def append(self, record: ExperimentRecord) -> None
    def records(self, *, run_id=None, theory_version=None, y=None, oracle=None) -> list[ExperimentRecord]
    def count(self, *, run_id=None, theory_version=None, y=None, oracle=None) -> int
    def label_counts(self, *, run_id=None, theory_version=None) -> dict[str, int]
```

行为：
- 只能追加：不提供任何修改或删除记录的方法（不要有 `delete`、`update`、`remove`、`clear`、`truncate` 这些名字）。
- `append` 和 `start_run` 返回之前必须已经提交到磁盘：另一个连接马上能读到，进程此后崩溃也不丢。
- `records()` 的顺序：run 按创建顺序，run 内按 `seq`。四个过滤条件是关键字参数，给了几个就按几个同时过滤，None 表示不过滤。返回的对象和写入的相等（`==`）。
- `label_counts()` 永远含 `pass`、`fail`、`invalid` 三个键，没有的记 0。
- 下列情况抛 `LedgerError`，并且不留下任何记录：`start_run` 的 `run_id` 已存在；`append` 的 `run_id` 没有 start 过；`record_id` 重复；同一个 run 里 `seq` 重复；`run_manifest` / `next_seq` 的 `run_id` 不存在。
- 记录整条存成规范 JSON（`record.to_json()`），另外把 `run_id`、`seq`、`oracle`、`y`、`theory_version`、`purpose`、`created_at` 拆成列供查询和建索引。manifest 存成 JSON 文本。
- 库里记下 `SCHEMA_VERSION`；打开一个版本号不同的账本文件时抛 `LedgerError`。
- `close()` 之后文件句柄必须真的释放：Windows 上没关干净的 SQLite 文件删不掉，门槛用临时目录，会因此失败。

### 5. 测试

- `framework/tests/test_surprise_contracts.py`：五个契约加 `SqlCase`、`IdentityEvidence` 的往返、默认值、list 转 tuple、各条校验规则、`from_dict` 对缺键和未知键的处理。
- `framework/tests/test_surprise_ledger.py`：写入与四种过滤及其组合、顺序、`next_seq`、`label_counts`、各种被拒绝的写入、关闭后重开、第二个连接可见、版本号不符。用 pytest 的 `tmp_path`。

测试要自己写，不要照抄门槛。

## 背景

1. 契约为什么分两个文件：CLAUDE.md 规定 S4 结束后 `framework/surprise/harness/` 冻结。实验记录和标签由 harness 写出，跟着 harness 一起冻结是对的；规格、假设、理论编辑要到 S5–S7 才定型，放进 harness 会被提前冻住。
2. `ExperimentRecord.spec` 存的是 dict 而不是 `Spec` 对象，就是为了让 harness 不依赖理论层。
3. `Label` 里不能放时间、耗时、随机 id 这类每次运行都变的东西：S2 的门槛要求同一输入判两次、`Label.to_dict()` 完全相同。时间只出现在 `ExperimentRecord.created_at`。
4. 命令都在 `framework/` 目录下执行。CLAUDE.md 里写的 `../.venv/Scripts/python.exe` 在 worktree 里不存在，直接用 `python`，它已经指向项目解释器。

## 允许改动的路径

只改下面这些路径（`**` 跨目录，`*` 不跨）。审查按这个清单逐个文件核对，清单以外的任何改动都算越界。

```allow-paths
framework/surprise/harness/contracts.py
framework/surprise/harness/constants.py
framework/surprise/harness/ledger.py
framework/surprise/theory/contracts.py
framework/tests/test_surprise_contracts.py
framework/tests/test_surprise_ledger.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`。
- 旧代码（`framework/surprise/` 以外）本包不碰。`framework/surprise/harness/__init__.py`、`framework/surprise/theory/__init__.py` 也不改（不要在里面加 re-export）。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。某个测试确实该改，就写进报告的"未决问题"，停下。
- 标签路径上不调用 LLM；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。本包不需要任何 LLM 调用。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不做本包以外的东西：不写 manifest、不写 oracle 适配器、不写 `evaluate`。
- 不装、不卸任何 Python 包，不碰 worktree 之外的任何文件。

## 验收命令

在 worktree 里执行，全部通过才算完成。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests                        # 退出码 0；原有的 64 个仍通过，再加上你新写的
python -m surprise.gates.s02 --only contracts ledger     # 退出码 0，最后一行是 S02 GATE [only: contracts, ledger]: PASS (2/2 groups passed)
python -m surprise.gates.s01                             # 仍是 7/7
cd ..
git status --short                                       # 期望为空
```

`python -m surprise.gates.all` 现在会是退出码 1：`s02` 的另外三组（manifest、oracles、evaluate）属于后面的包，本包做完它们仍然失败，这是预期的，在报告里照实写。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。发现门槛脚本和这份说明对不上，同样写进报告，停下，不要去改门槛。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s02-contracts

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改 / 移动自哪里）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
