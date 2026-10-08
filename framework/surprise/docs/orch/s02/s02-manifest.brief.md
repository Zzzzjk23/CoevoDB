角色：执行者

# 工作包 s02-manifest：run manifest、harness 哈希与校验命令

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s02-manifest`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s02`（5a2fb50）
- 所属会话：S2（Phase 1a · 契约、账本、冻结机制、三类健全 oracle），范围见 `framework/surprise/docs/SESSIONS.md` 的 S2 一节
- 依赖：工作包 s02-contracts 已合并，可以直接用 `surprise.harness.constants`（`as_dict()`）。另一个包 s02-oracles 正在别的 worktree 里并行做 `framework/surprise/harness/oracles/` 和 `evaluate.py`，和你没有共同文件，不要去建这些路径。

## 目标

一个模块加一个测试文件。它落实 PLAN.md 第 1 节总原则第 2 条："判定代码只搬不改……进 harness 并记录哈希"。门槛 `framework/surprise/gates/s02.py` 里的 `check_manifest` 是可执行的验收标准，开工前先读一遍。

### `framework/surprise/harness/manifest.py`

只用标准库。代码里的注释和文档字符串用英文。所有输出只用 ASCII。

```python
MANIFEST_SCHEMA = 1
HASHED_PATHS = (
    "surprise/harness/**/*.py",
    "oracles/tlp.py", "oracles/tlp_groupby.py", "oracles/norec.py", "oracles/plan_variant.py",
    "oracles/errors.py", "oracles/determinism.py", "oracles/normalize.py", "oracles/models.py",
    "oracles/db_runner.py", "targets/duckdb_runner.py",
)

def file_digest(path) -> str
def harness_hash(*, root=None, patterns=None) -> dict
def build_manifest(run_id: str, *, root=None) -> dict
def verify_manifest(manifest: dict, *, root=None, patterns=None) -> list[str]
def main(argv: list[str] | None = None) -> int
```

- `HASHED_PATHS` 里的路径相对 `framework/` 目录（含 `surprise/` 的那个目录，从本文件的位置推出，不依赖当前工作目录）。前一条是新 harness 的全部代码，后十条是 harness 调用、会影响标签的旧模块。`root` 和 `patterns` 两个参数默认就是这个目录和这个元组，留着是为了让测试能在临时目录里造一棵假的文件树。
- 文件清单：把各条模式展开，去掉 `__pycache__` 下的文件，相对路径用 `/` 分隔，按字典序排序去重。不含通配符的条目在磁盘上不存在时抛 `FileNotFoundError`。
- `file_digest(path)`：文件内容的 SHA-256 十六进制串，计算前把 `\r\n` 换成 `\n`。原因见"背景"第 1 条。
- `harness_hash()` 返回 `{"algorithm": "sha256", "hash": <总哈希>, "files": {相对路径: 文件摘要}}`。总哈希是对按路径排序后逐个文件的 `f"{相对路径}\0{文件摘要}\n"`（UTF-8）连起来算的 SHA-256。同一棵文件树两次调用、在两个进程里调用，结果必须相同。
- `build_manifest(run_id)` 返回一个 JSON 安全的 dict：

  ```python
  {
      "schema": MANIFEST_SCHEMA,
      "run_id": run_id,
      "created_at": <UTC 的 ISO 8601 时间>,
      "harness": harness_hash(),
      "constants": surprise.harness.constants.as_dict(),
      "environment": {
          "python": platform.python_version(),
          "platform": sys.platform,
          "engines": {"duckdb": <版本或 None>, "datafusion": <版本或 None>, "sqlite": sqlite3.sqlite_version},
      },
      "git_commit": <framework 所在仓库 HEAD 的提交号，取不到就是 None>,
  }
  ```

  引擎版本用 `importlib.metadata.version` 取，不要为了取版本去 import 引擎本身。
- `verify_manifest(manifest)` 拿 manifest 里记录的 `harness` 和当前磁盘上重新算出来的比较，返回问题列表，空列表表示没有变化。每个问题是一行 ASCII 文本，必须带上相对路径：
  - `changed: <路径>`：两边都有，摘要不同；
  - `missing: <路径>`：manifest 里有，现在磁盘上没有（或不在哈希范围里了）；
  - `added: <路径>`：现在在哈希范围里，manifest 里没有；
  - `hash mismatch: manifest <前 12 位> current <前 12 位>`：总哈希不同（放在最后）。
  
  manifest 结构不对（没有 `harness`，或 `harness` 里没有 `files`、`hash`）抛 `ValueError`。
- 命令行（`python -m surprise.harness.manifest …`，在 `framework/` 下执行）：
  - `hash`：最后一行打印当前总哈希，退出码 0。
  - `write PATH [--run-id ID]`：把 `build_manifest(ID)` 写成 UTF-8 的 JSON（`indent=2, sort_keys=True`），`ID` 默认 `manual`，退出码 0。
  - `verify PATH`：没有问题时打印 `OK <总哈希>`，退出码 0；有问题时逐行打印问题，最后一行 `MISMATCH (<n> problems)`，退出码 1；文件读不了、不是 JSON 或结构不对时打印 `ERROR: <原因>`，退出码 2。

### `framework/tests/test_surprise_manifest.py`

用 `tmp_path` 造假的文件树（借 `root` / `patterns` 参数），覆盖：摘要不受行尾影响、内容变了摘要就变；总哈希稳定；模式展开与排除 `__pycache__`；通配符之外的条目缺失时报错；`verify_manifest` 的四种问题各一例（改文件、删文件、加文件）；结构不对的 manifest；真实目录上 `build_manifest` 的各个键；命令行三个子命令的退出码与输出。测试不许改动任何受跟踪的文件。测试要自己写，不要照抄门槛。

## 背景

1. 这台机器的 git 开着 `core.autocrlf=true`：同一个提交在不同的检出里，工作区文件的行尾可能是 LF 也可能是 CRLF（新建的 worktree 里多半是 CRLF）。哈希如果直接对文件字节算，主检出区和 worktree 就对不上。所以摘要必须先把行尾归一。
2. 新 harness 的包叫 `surprise.harness.oracles`，旧代码的包是顶层的 `oracles`。`HASHED_PATHS` 里 `oracles/tlp.py` 这些指的是旧包（`framework/oracles/`）。
3. 命令都在 `framework/` 目录下执行。CLAUDE.md 里写的 `../.venv/Scripts/python.exe` 在 worktree 里不存在，直接用 `python`，它已经指向项目解释器。
4. 这个模块 S4 之后会冻结，S4 的门槛会拿它校验 harness 没被改过。校验要能准确说出哪个文件变了。

## 允许改动的路径

只改下面这些路径（`**` 跨目录，`*` 不跨）。审查按这个清单逐个文件核对，清单以外的任何改动都算越界。

```allow-paths
framework/surprise/harness/manifest.py
framework/tests/test_surprise_manifest.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`。
- 旧代码（`framework/surprise/` 以外）本包不碰。上一个包交付的 `contracts.py`、`constants.py`、`ledger.py` 也不改；觉得它们有问题，写进报告的"未决问题"，停下。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。某个测试确实该改，就写进报告的"未决问题"，停下。
- 标签路径上不调用 LLM；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。本包不需要任何 LLM 调用。manifest 里不要记录任何环境变量的值。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不装、不卸任何 Python 包，不碰 worktree 之外的任何文件。
- 不要清理 `.orch/tmp`：里面的临时文件留着，清理 worktree 时会一起删掉。删除命令被权限规则拒绝之后，不要改成逐个删除再试。

## 验收命令

在 worktree 里执行，全部通过才算完成。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests                                # 退出码 0，通过数不少于 126，再加上你新写的
python -m surprise.gates.s02 --only contracts ledger manifest    # 退出码 0，3/3
python -m surprise.gates.s01                                     # 仍是 7/7
python -m surprise.harness.manifest hash                         # 退出码 0
cd ..
git status --short                                               # 期望为空
```

`python -m surprise.gates.all` 现在会是退出码 1：`s02` 的 oracles、evaluate 两组属于并行的另一个包，这是预期的，在报告里照实写。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。发现门槛脚本和这份说明对不上，同样写进报告，停下，不要去改门槛。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s02-manifest

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改 / 移动自哪里）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
