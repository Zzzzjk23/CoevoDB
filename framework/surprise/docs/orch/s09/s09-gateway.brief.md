角色：执行者

# 工作包 s09-gateway：LLM 网关（响应缓存、按角色记账、"预测"字段、调用上限、两档模型）与只读的读源码工具

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s09-gateway`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s09`（S8 验收之后，门槛 `gates/s09.py` 已写好）
- 所属会话：S9（Phase 5a：LLM 网关、实现器、假设猜想者），范围见 `framework/surprise/docs/SESSIONS.md` 的 S9 一节
- 依赖：旧代码 `framework/agents/base_agent.py`（`BaseAgent`）与 `framework/llm/ledger.py`（全局 `ledger`）；`surprise.harness`（冻结，本包不用它）。先读 `framework/surprise/gates/s09.py` 与 `s09_cases.py` 的全文：本包要让其中的 `constants`、`cache`、`cap`、`source` 四组通过，`reject` 组通过到它开始用 `Implementer` 为止（见"验收命令"）。门槛就是接口规格，下面的说明与门槛不一致时以门槛为准，并写进报告。
- 之后还有两个包并行：`s09-roles`（实现器、猜想者，只在 `surprise/roles/` 里加文件）与 `s09-wire`（Hunter 与主循环的接线）。它们都以本包合并后的 `session/s09` 为基线，所以本包的接口名字、字段、行为必须与下面写的完全一致。

## 目标

依据 SESSIONS 的 S9 一节："LLM 网关（复用 `agents/base_agent.py`、`llm/ledger.py`）：响应缓存，键为提示哈希 + 模型 + 种子；按角色记账；每个角色的输出 schema 必带'预测'字段，缺则拒收；每个会话设调用上限；至少支持两档模型。""假设猜想者……需要 DuckDB / DataFusion 源码检出与只读的读源码工具。"PLAN 第 6 节决策 7："LLM 角色先单次结构化调用"；决策 10："网关支持至少两档模型（换模型强度消融）"。PLAN 第 4 节：LLM 网关在新包的 `roles/` 一层。

全部放在 `framework/surprise/roles/`（目录已存在，只有一个 `__init__.py`）。

### 1. 常数（`surprise/roles/constants.py`）

写法照 `surprise/theory/constants.py`：每个常数一行注释、模块级 `as_dict()` 返回全部常数的 dict（字典值返回深拷贝）。取值与 `gates/s09_cases.py` 的 `CONSTANTS` **逐项相同**（包括后半段实现器、猜想者用的那些：本包先把它们定义好，下一个包直接用）：

```python
TIERS = {"fast": "deepseek-chat", "strong": "deepseek-reasoner"}   # tier -> model name
DEFAULT_MAX_CALLS = 200            # network calls one gateway (one run) may make
CAP_ENV = "SURPRISE_LLM_MAX_CALLS" # if set, an integer that lowers every gateway's cap
REQUIRED_FIELD = "prediction"      # every role's reply must carry it, non-empty
SOURCE_ROOT_ENV = "SURPRISE_SOURCE_ROOT"
SOURCE_DIRS = {"duckdb": "duckdb-v1.5.5", "datafusion": "datafusion-54.0.0"}
SOURCE_COMMITS = {"duckdb": "d8cdaa33fda8df955cc76ef58a280f68f4cd43fa",
                  "datafusion": "45d943dfb8699dc9cb9ef2320e955b73e3e6c03b"}
SOURCE_MAX_FILE_BYTES = 2_000_000
IMPLEMENTER_TIER = "fast"; IMPLEMENTER_TEMPERATURE = 0.2; IMPLEMENTER_MAX_TOKENS = 2000
IMPLEMENTER_ATTEMPTS = 2; IMPLEMENTER_PER_CHOICE = 1
CONJECTURER_TIER = "strong"; CONJECTURER_TEMPERATURE = 0.6; CONJECTURER_MAX_TOKENS = 8000
CONJECTURER_MAX_PREDICTIONS = 5; SOURCE_MAX_FILES = 4; SOURCE_MAX_LINES = 400
```

（上面为了省篇幅把几行写在一起；文件里一行一个、各带注释。）

### 2. 回复解析（`surprise/roles/schema.py`）

`parse_reply(text: str) -> tuple[dict | None, str | None]`，返回 `(data, None)` 或 `(None, reason)`：

1. 去掉首尾空白。若以 ```` ``` ```` 开头：去掉第一行（```` ``` ```` 或 ```` ```json ````），再去掉末尾的 ```` ``` ````（若有）与空白。
2. `json.loads` 整段；失败则取第一个 `{` 到最后一个 `}` 之间（含两端）再 `json.loads` 一次；仍失败（或没有这样一段）→ `(None, "no_json")`。
3. 解析出来不是 dict → `(None, "not_object")`。
4. 没有 `REQUIRED_FIELD` 键，或其值是 `None`、`""`、`[]`、`{}` → `(None, "no_prediction")`。
5. 否则 `(data, None)`。

只检查这一个字段；各角色自己的 schema（实现器、猜想者的其余字段）由下一个包检查。

### 3. 响应缓存（`surprise/roles/cache.py`）

- `cache_key(prompt: str, model: str, seed: int) -> str`：`sha256(f"{sha256(prompt)}\n{model}\n{seed}")` 的十六进制，两次 sha256 都是对 UTF-8 编码求、取 hexdigest。
- `ResponseCache(root)`：`root` 不存在就建。一条一个文件，路径 `<root>/<key[:2]>/<key>.json`，内容是 dict，键为 `key, prompt_sha256, model, seed, role, tier, prompt, text, input_tokens, output_tokens, temperature, max_tokens, created_at`（`created_at` 为 ISO 时间串）。方法：`path(key) -> Path`、`get(key) -> dict | None`、`put(entry: dict) -> None`。`put` 先写同目录的临时文件再 `os.replace`，UTF-8、`ensure_ascii=False`。
- `get` 只返回"属于这个键"的条目：文件存在、能解析、`entry["key"] == key`、`sha256(entry["prompt"]) == entry["prompt_sha256"]`、`cache_key(entry["prompt"], entry["model"], entry["seed"]) == key`；任何一条不满足就当作没有（返回 None，不抛异常）。门槛会把一条缓存的 `prompt` 改掉，要求这时网关报 `miss`。

### 4. 网关（`surprise/roles/gateway.py`）

```python
@dataclass(frozen=True)
class Completion:      # what a transport returns
    text: str
    input_tokens: int = 0
    output_tokens: int = 0

@dataclass(frozen=True)
class Reply:
    role: str; tier: str; model: str; seed: int; key: str
    status: str          # "ok" | "rejected" | "blocked" | "miss" | "error"
    source: str | None   # "network" | "cache" | None (blocked / miss)
    data: dict | None    # parsed reply when status == "ok", else None
    text: str | None     # raw text when there is one (ok / rejected), else None
    reason: str | None   # parse_reply's reason, "cap", "miss", or the exception class name
    input_tokens: int; output_tokens: int

class TransportError(RuntimeError): ...

class Gateway:
    def __init__(self, *, cache_dir, ledger_path=None, max_calls=None, transport=None): ...
    def call(self, role: str, prompt: str, *, tier: str, seed: int,
             temperature: float = 0.0, max_tokens: int = 4000) -> Reply: ...
    network_calls: int (property)   # transport attempts made by this instance
    max_calls: int (property)       # the effective cap
    def totals(self) -> dict: ...
    def manifest(self) -> dict: ...
```

- 传输对象（transport）是任何有 `complete(*, model, prompt, temperature, max_tokens, role) -> Completion` 的对象。`transport=None` 表示离线：只用缓存。
- 有效上限：`max_calls`（None 时用 `DEFAULT_MAX_CALLS`）；环境变量 `CAP_ENV` 设了一个整数时，取两者的较小者（在构造时读一次）。
- `call` 的流程，次序不能变：
  1. `tier` 不在 `TIERS` → `ValueError`。`model = TIERS[tier]`，`key = cache_key(prompt, model, seed)`。
  2. 缓存里有 → 不碰传输；`source="cache"`；对缓存里的 `text` 跑 `parse_reply`：通过为 `ok`，否则 `rejected`。token 数取条目里记的。
  3. 没有，且 `transport is None` → `status="miss"`，`source=None`，`reason="miss"`。
  4. 没有，且 `network_calls >= max_calls` → `status="blocked"`，`source=None`，`reason="cap"`，不碰传输。
  5. 否则 `network_calls += 1`，调用 `transport.complete(...)`。抛出任何异常 → `status="error"`，`source="network"`，`reason=type(exc).__name__`，**不写缓存**。返回了 `Completion` → **先写缓存**（不论之后解析通过与否），再 `parse_reply`：`ok` 或 `rejected`，`source="network"`。
  6. 每次 `call`（任何结果）都往账本追加一行，并更新按角色的计数。
- 账本（`ledger_path` 不为 None 时，JSONL，每行 `ensure_ascii=True`）每行恰好这些键：`seq`（从 1 起）、`role`、`tier`、`model`、`seed`、`key`、`prompt_sha256`、`status`、`source`、`reason`、`input_tokens`、`output_tokens`、`latency_s`（这次 `call` 的耗时，秒）。不写提示全文、不写回复全文、不写任何密钥。
- `totals()`：`{"by_role": {角色: {"calls", "network", "cache", "ok", "rejected", "blocked", "miss", "error", "input_tokens", "output_tokens"}}, "network": network_calls, "max_calls": max_calls}`。`calls` 是该角色 `call` 的总次数；`network` / `cache` 按 `source` 数；五种状态各数各的；token 只累计 `source == "network"` 的。
- `manifest()`：`{"tiers": TIERS 的拷贝, "max_calls": 有效上限, "constants": constants.as_dict()}`。
- 网关自己不读密钥、不导入 `httpx`、`agents`、`llm`。

### 5. DeepSeek 传输（`surprise/roles/transport.py`）

复用旧代码而不是复制：`from agents.base_agent import BaseAgent`、`from llm.ledger import ledger`（旧代码一行都不改）。

- `class DeepSeekTransport(BaseAgent)`：`__init__(self, *, base_url=None)` 调 `super().__init__({"api_key": "${DEEPSEEK_API_KEY}", "base_url": base_url or "https://api.deepseek.com/v1", "model": TIERS["fast"]})`，于是密钥由 `BaseAgent` 从环境变量读取。`execute` / `learn_from_feedback` 抛 `NotImplementedError`（它们不用）。
- `complete(*, model, prompt, temperature, max_tokens, role) -> Completion`：密钥为空 → 抛 `TransportError("DEEPSEEK_API_KEY is not set")`，不发请求。否则用 `self.setup_api_client()` 拿到 `BaseAgent` 的 HTTP 客户端，POST `/chat/completions`，载荷 `{"model", "messages": [{"role": "user", "content": prompt}], "temperature", "max_tokens"}`；`raise_for_status()`；取 `choices[0].message.content`（推理模型另有的 `reasoning_content` 不用）与 `usage.prompt_tokens / completion_tokens`。成功与失败都调用旧的全局 `ledger.record(agent="surprise.roles." + role, event=role, model=model, prompt=prompt, response=..., input_tokens=..., output_tokens=..., status="ok" 或 "error")`。任何失败（HTTP 错误、超时、缺字段）都转成 `TransportError`，异常信息里只写异常类别与 HTTP 状态码，**不得包含请求头、密钥或回复全文**。
- 只有这个模块导入 `agents.base_agent` 与 `llm.ledger`（因而间接导入 `httpx`）。`surprise.roles` 的 `__init__` 与其余模块都不导入它；需要真实传输的调用方自己 `from surprise.roles.transport import DeepSeekTransport`。门槛的 `isolation` 组会在新进程里核对这一点。

### 6. 读源码工具（`surprise/roles/source.py`）

只读，限定在一个根目录之内。

```python
class SourceError(ValueError): ...
@dataclass(frozen=True)
class Snippet: path: str; start: int; end: int; text: str     # path 相对根目录、用 "/"
@dataclass(frozen=True)
class Hit: path: str; line: int; text: str

class SourceReader:
    def __init__(self, root): ...       # root 必须是已存在的目录，否则 SourceError
    root: Path (property)
    commit: str | None (property)       # 见下
    def exists(self, path: str) -> bool: ...
    def read(self, path: str, start: int = 1, end: int | None = None) -> Snippet: ...
    def grep(self, pattern: str, *, under: str = "", suffixes=None, max_hits: int = 50) -> tuple[Hit, ...]: ...

def source_roots() -> dict[str, Path]: ...
def open_sources(*, verify: bool = True) -> dict[str, SourceReader]: ...
```

- 路径规则（`exists`、`read`、`grep` 的 `under` 都适用）：只接受相对路径；绝对路径、盘符、含 `..` 段、含 NUL 字符、解析（`resolve()`）之后不在根目录之内（包括经由符号链接或目录联接逃出去的）→ `SourceError`（`exists` 对这些返回 False，不抛）。`read` 的目标必须是普通文件、不超过 `SOURCE_MAX_FILE_BYTES`，否则 `SourceError`。只以只读方式打开文件，不写、不改任何东西。
- `read`：按 UTF-8 解码（`errors="replace"`），按行切分；`start < 1`、`end < start` → `SourceError`；`end` 为 None 或超过行数时截到最后一行。`text` 是第 `start` 到 `end` 行用 `"\n"` 连起来（不带末尾换行），`end` 是实际截到的行号。
- `grep`：`pattern` 是正则；在 `under`（相对根目录的子目录，空串为根）之下递归，按相对路径的字典序遍历文件，跳过 `.git` 目录与超过大小上限的文件；`suffixes` 为 None 时只看 `.cpp .hpp .h .c .rs` 五种后缀，否则只看给定后缀；逐行 `re.search`，命中记 `Hit(path, 行号, 该行去掉末尾换行)`，到 `max_hits` 条为止。
- `commit`：根目录下 `.git/HEAD` 是 40 位十六进制（浅克隆的分离头）就取它；是 `ref: <ref>` 就读 `.git/<ref>`，再不行读 `.git/packed-refs` 里对应的行；都没有返回 None。不起 `git` 子进程。
- `source_roots()`：父目录取环境变量 `SOURCE_ROOT_ENV`；没设时取"git 公共目录的父目录"下的 `.src`（`git rev-parse --path-format=absolute --git-common-dir` 的父目录；命令失败就退回 `framework/` 的上一级）。这样 worktree 里也能找到主检出区的 `.src`（主检出区是 `D:\CoevoDB`，那里有 `.src/duckdb-v1.5.5` 与 `.src/datafusion-54.0.0`，`gates/s03.py` 的 `venvs_root` 是同样的写法）。返回 `{引擎: 父目录 / SOURCE_DIRS[引擎]}`。
- `open_sources(verify=True)`：对每个引擎建 `SourceReader`；目录不存在 → `SourceError`；`verify` 时 `commit` 必须等于 `SOURCE_COMMITS[引擎]`，否则 `SourceError`。

### 7. 导出（`surprise/roles/__init__.py`）

保留现有的模块文档字符串，导出：`constants`（模块）、`Completion`、`Reply`、`Gateway`、`TransportError`、`ResponseCache`、`cache_key`、`parse_reply`、`SourceReader`、`SourceError`、`Snippet`、`Hit`、`source_roots`、`open_sources`。**不要**导出或导入 `transport`。下一个包会在这个文件里追加它的导出，所以写成每个名字单独一行的 `__all__` 与几行 `from .x import ...`，方便合并。

### 8. 测试

`framework/tests/test_surprise_roles_gateway.py`、`framework/tests/test_surprise_roles_source.py`：覆盖上面每一条规则，全部离线，用假的传输对象（不发任何网络请求，不需要密钥），临时文件只放 `tmp_path`。DeepSeek 传输只测"没有密钥时抛 `TransportError` 且不发请求"（把环境变量清掉，例如用 `monkeypatch.delenv`），以及异常信息里不含一个假密钥字符串（用 `monkeypatch.setenv` 设一个假的 `sk-...` 值，再让 HTTP 客户端失败：可以给 `base_url` 一个 `http://127.0.0.1:9`，连接被拒）。

## 背景

- 门槛的 `cache` 组在进程里临时设了一个假的 `DEEPSEEK_API_KEY`，然后扫描缓存目录与账本，要求找不到它。
- `gates/s09.py` 里的 `Script` 类就是门槛用的假传输，写测试时可以照它的样子写。
- 本机的 `.src/` 是浅克隆（`git clone --depth 1 --branch <tag>`），`.git/HEAD` 是分离头的 40 位哈希。DuckDB 的检出约 388 MB，`grep` 的测试不要扫整个检出区，扫你自己在 `tmp_path` 里建的小目录。
- `DEEPSEEK_API_KEY` 在你的环境里**没有**（派发脚本去掉了它）；本包不需要任何真实调用，也不要尝试。

## 允许改动的路径

只改下面这些路径（`**` 跨目录，`*` 不跨）。审查按这个清单逐个文件核对，清单以外的任何改动都算越界。

```allow-paths
framework/surprise/roles/__init__.py
framework/surprise/roles/constants.py
framework/surprise/roles/schema.py
framework/surprise/roles/cache.py
framework/surprise/roles/gateway.py
framework/surprise/roles/transport.py
framework/surprise/roles/source.py
framework/tests/test_surprise_roles_gateway.py
framework/tests/test_surprise_roles_source.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`（已冻结），也不改 `framework/surprise/` 下除 `roles/` 以外的任何目录。
- 旧代码（`framework/surprise/` 以外，包括 `agents/`、`llm/`）一行都不改，只导入。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。某个测试确实该改，就写进报告的"未决问题"，停下。网关把传输的异常记成 `status="error"` 是规定的行为，不算吞掉失败。
- 不做任何真实的 LLM 调用，不发任何网络请求（测试里连接 `127.0.0.1:9` 被拒除外）。密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。
- 不往 `.src/` 写任何东西，不改动它。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不建指向 worktree 之外的链接或目录联接；不要清理 `.orch/tmp`；测试产生的临时文件只放 pytest 的 `tmp_path`。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests       # 通过数不少于 613，skip 仍是 3。用 python -m pytest
python -m surprise.gates.s09 --only constants cache cap source        # 4/4
python -m surprise.gates.s09 --only reject     # 预期失败，且失败信息必须是 "module 'surprise.roles' has no attribute 'Implementer'"；更早的失败要修
python -m surprise.gates.s08 --only no_llm     # 1/1
```

`python -m surprise.gates.all` 不用跑（S9 的其余组要等后面的包）；在报告里注明没有跑。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s09-gateway

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
