角色：执行者

# 工作包 s15-archive：网格目录的归档命令（打包、校验、精简）

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s15-archive`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s15`
- 所属会话：S15（实验基础设施），范围见 `framework/surprise/docs/SESSIONS.md` 的 S15 一节（"归档命令"）；用途见 `framework/surprise/docs/EXPERIMENT.md` §5：每个里程碑出完报告后，原始格子目录压缩、拷回 Windows 本机，服务器上只留报告与摘要。
- 依赖：无。

## 目标

新模块 `framework/surprise/experiments/archive.py`，命令行 `python -m surprise.experiments.archive {pack|verify|prune} ...`。返回码：0 成功；1 校验不过或拒绝执行；2 参数错。只用标准库（`tarfile`、`hashlib`、`json`、`pathlib`、`shutil`）。

### `pack OUT --dest FILE`

- 把网格目录 `OUT` 整个打成 gzip 压缩的 tar：成员路径是 `<OUT 的目录名>/<相对路径>`（POSIX 分隔符），按相对路径排序加入；只收普通文件与目录，遇到符号链接报错（返回 1）。
- `FILE` 已存在就拒绝（返回 1）；`FILE` 落在 `OUT` 里面也拒绝。
- 同时写清单 `FILE + ".json"`：`{"schema": 1, "root": <OUT 的目录名>, "files": {<相对路径>: <sha256>, ...}, "tar_sha256": <FILE 的 sha256>}`，`files` 列出 `OUT` 里的每一个普通文件。
- 大文件按块读算哈希，不要一次读进内存（单个账本可能几个 GB）。

### `verify FILE [--against OUT]`

- 读 `FILE + ".json"`；`FILE` 的 sha256 必须等于 `tar_sha256`；逐个成员流式算 sha256，成员集合与 `files` 完全相同、每个哈希都对上。任何一项不对：打印原因，返回 1。
- `--against OUT`：再核对 `OUT` 里现存的每个普通文件都在清单里且哈希相同。

### `prune OUT --archive FILE`

- 先做 `verify FILE --against OUT` 的全部检查；任何一项不过就**什么都不删**，返回 1。
- 通过后删掉原始数据，只留报告与摘要：
  - `OUT` 顶层：留 `grid.json` 与整个 `report/` 目录（里面的东西全留）；
  - `OUT/cells/<臂>/<格>/` 里：只留 `cell.json`、`config.json`、`report.json`、`error.txt`（有就留）；其余文件与子目录（`ledger.sqlite`、`theory/`、`progress.jsonl`、`llm/`、`sqlancer/` 等）全删；
  - `OUT/cells/<臂>/` 下的 `<格>.log`、`<格>.bootstrap.json` 与整个 `<格>.stale-<k>/` 目录也删（都在归档里）；
  - `OUT` 顶层别的东西：删（都在归档里）。
- 打印删了多少文件、腾出多少字节。

### 测试 `framework/tests/test_surprise_s15_archive.py`

造一个小网格目录（几格，每格有假的 `ledger.sqlite`、`theory/`、`progress.jsonl`、`report.json`、`config.json`、`cell.json`，再加 `report/`、`.log`、`.stale-1/`），覆盖：打包与清单、校验通过、篡改一个字节后校验失败、目录与归档不符时 `prune` 拒绝且一个文件都没删、`prune` 之后剩下的恰好是该留的、解包后与原目录逐文件相同、`FILE` 已存在或在 `OUT` 里时拒绝、符号链接时拒绝（Windows 上没有权限建符号链接：用 `if` 判断 `os.symlink` 是否成功，成功才断言 `pack` 拒绝；不要用 skip）。测试总时长控制在 1 分钟以内。

## 背景

- 门槛 `framework/surprise/gates/s15.py` 的 `archive` 组是验收标准，请读它（只读，不改）。
- 运行手册（`SERVER.md`，编排者写）会让用户在服务器上：`pack` → `scp` 拷回 → 在 Windows 上 `verify` → 回服务器 `prune`。

## 允许改动的路径

```allow-paths
framework/surprise/experiments/archive.py
framework/tests/test_surprise_s15_archive.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`；不改 `framework/surprise/harness/`（已冻结）；不改 `experiments/` 里别的文件。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。某个测试确实该改，就写进报告的"未决问题"，停下。
- 本包不需要 LLM 调用、不需要密钥。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`；不要清理 `.orch/tmp`。

## 验收命令

在 worktree 里执行。`python` 和 `pytest` 已经指向项目解释器，不要换别的。shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，判断结果用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests                                         # 0 failed，通过数不少于基线
python -m surprise.gates.s15 --only archive                               # PASS
python -m surprise.experiments.archive --help                             # 退出码 0
```

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），格式见下。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s15-archive

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
