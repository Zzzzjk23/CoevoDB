角色：执行者

# 工作包 s11-fixes：S11 开头的四处修复（存储写盘重试、主循环保留原始异常、请求总时限、指标认扩展词表）

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s11-fixes`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s11`（门槛 `framework/surprise/gates/s11.py` 与 `s11_cases.py` 已经写好）
- 所属会话：S11（Phase 6 评估管线），范围见 `framework/surprise/docs/SESSIONS.md` 的 S11 一节
- 依赖：无。与你并行的还有 `s11-runmetrics`（`surprise/metrics/` 的新模块）和 `s11-purellm`（`surprise/baselines/pure_llm.py`）；你们改的文件不重叠。

## 目标

S9、S10 验收时定下、要在 S11 开头修的四件事。门槛 `gates/s11.py` 的 `store`、`loop_error`、`deadline`、`vocabulary` 四组检查它们（`vocabulary` 组还要用 `s11-runmetrics` 的 `RunData` 与 `run_metrics`，在你的 worktree 里这一组会因为缺那两个模块而失败，这是预期的；它前半段关于 `dups` / `recall` 的检查应当通过，见"验收命令"）。先读一遍这四组的代码，它们就是验收标准。

### 1. 理论存储写盘遇到瞬时 PermissionError 时重试（`framework/surprise/theory/store.py`）

背景：S10 的长跑在负载下中断过一次，判断是 Windows 上 `os.replace` 遇到被别的进程打开的文件失败（PermissionError）。

- `_write_text(path, text)` 里的 `os.replace(temporary, path)` 遇到 `PermissionError` 时短暂等待后重试；总共最多 6 次尝试，两次之间依次等 0.05、0.1、0.2、0.4、0.8 秒。最后一次仍失败，就把**那个 PermissionError 原样抛出**（不要包成别的异常类型）。
- 重试参数写成模块私有常数（如 `_REPLACE_ATTEMPTS`、`_REPLACE_DELAYS`），**不要**放进 `theory/constants.py`（理论常数由 S6/S7 门槛钉住）。
- 其它异常不重试。成功或最终失败后都不能留下 `.tmp` 文件（现有的 `finally` 已经负责删除，保持）。
- 必须通过模块里的 `os.replace` 调用（门槛用替换全局 `os.replace` 的办法模拟失败）。

### 2. 主循环保留原始异常（`framework/surprise/experiments/loop.py`）

背景：同一次中断里，主循环接着写报告，写报告又抛了异常，把原始异常盖掉了（`run()` 里 `_write_report` 抛出时 `pending` 丢失）。

改 `run()`（只改异常处理这一段，别的逻辑不动）：

- 运行因异常结束时（`_prepare` / `_drive` 抛出，包括 KeyboardInterrupt），**在尝试写报告之前**，把这个异常的完整 traceback 写进 `<out>/error.txt`（UTF-8）。
- 之后照旧写报告。写报告本身又抛异常时：把这个异常的 traceback 追加到 `error.txt`（前面加一行说明，例如 `--- while writing the report ---`），然后向调用者抛出**原始异常**（不是写报告的异常）。
- 没有原始异常而写报告失败时，照旧抛写报告的异常（这时也把它写进 `error.txt`）。
- 运行正常结束时不写 `error.txt`。
- `_close` 与 `_restore_library` 的 `finally` 顺序保持不变。
- 门槛 `loop_error` 组用替换 `loop._drive` 与 `loop._write_report` 的办法检查这两种情况：调用者拿到原始的 `ValueError`；`error.txt` 含原始异常（和报告异常）的文字；只有 `_drive` 失败时 `report.json` 的 `status` 是 `"error"`。

默认运行的 `config.json`、`report.json`、`progress.jsonl` 一个字节都不能变（S8/S9/S10 的门槛对它们逐行比对）。

### 3. 每个请求的总时限（`framework/surprise/roles/transport.py`、`framework/surprise/roles/constants.py`）

背景：`DeepSeekTransport` 用旧 `BaseAgent` 的 httpx 客户端，`timeout=300` 管的是两次读之间的间隔；DeepSeek 排队时一直发 keep-alive（空白行），这个超时永远不触发，S9 冒烟时一次 strong 档调用 900 秒没有内容。S9 验收定下：S11 做模型强度比较之前加上每个请求的总时限。

- `roles/constants.py` 新增 `REQUEST_DEADLINE_S = 600.0`（float，英文注释一行：从发出请求到读完回复的总时限，覆盖排队时的 keep-alive），并把它加进 `as_dict()`（照现有常数的写法）。不改任何现有常数。
- `DeepSeekTransport.__init__(self, *, base_url=None, deadline_s=None)`：`deadline_s` 为 None 时取 `REQUEST_DEADLINE_S`；存为实例属性 `self.deadline_s`。
- `complete(...)` 从发出请求到拿到完整回复的总时间超过 `deadline_s` 就放弃，抛 `TransportError`（消息只写类名或状态，例如 `TransportError("DeadlineExceeded")`，不能带密钥、提示或回复内容）。两种情形都要在时限内结束：服务器一直发空白行（keep-alive）；服务器完全不发数据。做法自定（例如用 `client.stream(...)` 逐块读、每块检查已用时间，同时把 httpx 的读超时设成不超过剩余时间；或别的可靠办法），但：
  - 正常回复的处理不变（JSON 解析、`usage` 计数、旧 `llm.ledger` 记账照旧）；
  - 不改 `agents/base_agent.py` 与 `llm/` 下的旧代码；
  - 网关（`roles/gateway.py`）不用改：它已经把 `TransportError` 记为 error、不进缓存。门槛 `deadline` 组会起一个本地 HTTP 服务器分别模拟"正常回复""持续发空白行""一直不发数据"三种情况，时限 1.5 秒，要求 1.5 + 3 秒内抛出 `TransportError`，网关记为 1 次 network、1 次 error，缓存目录里没有文件。
- 测试里起本地服务器时只用 `127.0.0.1`，密钥用假值（例如 `sk-test-dummy`），用完恢复环境变量。

### 4. 指标认扩展词表（`framework/surprise/metrics/dups.py`、`framework/surprise/metrics/recall.py`）

背景：带 `--vocabulary` 的运行，其理论存储要用同一份词表打开（摘要不同会被拒）；`metrics/` 现在一律用默认词表，打不开这种运行。

- `dups.py` 新增 `run_registry(run_dir) -> Registry | None`：读 `run_dir/config.json`，有 `"vocabulary"` 键就 `Registry.load(那个路径)` 返回，没有就返回 None。
- `dups.new_families(store_dir, registry=None)`：registry 传给 `Workbench.open(store_dir, registry=registry)`（None 时与现在相同）。
- `dups.compare(run_dir, old_dir)`：用 `run_registry(run_dir)` 打开新运行的理论。
- `recall.score(known, store_dir, registry=None)`：传给 `new_families`；命令行 `score --run DIR` 用 `run_registry(DIR)`。
- 返回值的格式、键顺序、默认行为一律不变（S8 门槛的 `duplicates`、`recall` 组拿它们对比钉住的产物）。

## 允许改动的路径

```allow-paths
framework/surprise/theory/store.py
framework/surprise/experiments/loop.py
framework/surprise/roles/transport.py
framework/surprise/roles/constants.py
framework/surprise/metrics/dups.py
framework/surprise/metrics/recall.py
framework/tests/test_surprise_s11_fixes.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`（已冻结）。
- 旧代码（`framework/surprise/` 以外，如 `agents/`、`llm/`）不碰。
- 不改 `theory/constants.py`、不改任何现有常数的值。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。某个现有测试确实该改，就写进报告的"未决问题"，停下。
- 本包不需要任何真实 LLM 调用；测试一律用本地假服务器或替身。密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`；不要清理 `.orch/tmp`。
- 不建指向 worktree 之外的链接或目录联接。

## 验收命令

在 worktree 里执行。`python` 和 `pytest` 已经指向项目解释器，不要换别的。shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，判断结果用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests                      # 通过数不少于 774，0 failed
python -m surprise.gates.s11 --only store loop_error deadline   # 三组 PASS
python -m surprise.gates.s11 --only vocabulary         # 预期 FAIL：缺 surprise.metrics.rundata（另一个包交付）；报告里贴出失败行，确认失败点在 rundata 之后
python -m surprise.gates.s08 --only no_llm constants scoring operators candidates lanes determinism   # 全部 PASS
python -m surprise.gates.s10 --only constants frame switches   # 全部 PASS
```

全量 `python -m surprise.gates.all` 很慢（半小时以上），而且 S11 门槛在别的包合并前不会全绿、S8 的长跑组在本包改了 `experiments/` 与 `theory/` 之后会失败（编排者在全部合并后重跑长跑重钉），所以**不要求**你跑全量门槛。

新测试放在 `framework/tests/test_surprise_s11_fixes.py`：每一处修复至少一个测试（存储重试成功、存储最终失败抛 PermissionError、两种 loop 异常情形、三种服务器情形、带词表运行的 `new_families` / `compare` / `score`）。测试总时长控制在 2 分钟以内。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），格式见下。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s11-fixes

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
