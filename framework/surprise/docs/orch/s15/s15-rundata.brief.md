角色：执行者

# 工作包 s15-rundata：`RunData` 与 `run_metrics` 改成流式读账本

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s15-rundata`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s15`
- 所属会话：S15（实验基础设施），范围见 `framework/surprise/docs/SESSIONS.md` 的 S15 一节（"`RunData` 改成流式读（24h 约 7 万条记录）"）
- 依赖：无。同时在跑的包：`s15-grid`、`s15-llm`。之后的 `s15-sqlancer` 会写出 manifest 里 `"baseline": "sqlancer"` 的运行目录（见目标 4）。

## 问题

`RunData.open` 现在把整本账本一次读进来：冻结的 `harness/ledger.py` 的 `Ledger.records()` 先 `fetchall` 全部 `record_json`（S8 长跑 8600 条、账本 533 MB），再全部解析成 `ExperimentRecord`。编排者实测：对 S8 长跑调用 `RunData.open`，进程的内存峰值是 **3.3 GB**。正式实验每格 24 小时约 7 万条记录，会到二三十 GB，8 格并发更不可能。

## 目标

### 1. `framework/surprise/metrics/rundata.py`

- `RunData.open(path)` 不再读入全部记录。它照旧读 `config.json`、`report.json`、`progress.jsonl`、run manifest、run_id，并记下记录条数（`SELECT COUNT(*)`）。
- 新方法 `iter_records()`：按 `seq` 升序**逐条**产出 `ExperimentRecord`。自己用 `sqlite3` 以只读方式（`file:...?mode=ro` 的 URI）打开 `ledger.sqlite`，用游标一行一行取 `record_json`，`ExperimentRecord.from_json(...)` 解析后交出去，不攒成列表。查询的过滤与次序与 `Ledger.records(run_id=...)` 相同（只有一个 run，按 `seq`）。打开运行目录照旧不创建、不改写任何文件。
- `records` 保留为兼容用的属性：第一次访问时才物化成列表（给测试和别的老调用方用）。本包改过的代码路径一律不碰它。
- `kind`：manifest 的 `baseline` 是 `"pure_llm"` → `"pure_llm"`；是 `"sqlancer"` → `"sqlancer"`；否则 `"surprise"`。

### 2. `framework/surprise/metrics/rq.py` 的 `run_metrics`

- 只用 `iter_records()` 流式扫一遍（必要时扫几遍，每遍都是流式的），每条记录只留下后面的指标真正用到的少量字段（例如 `seq`、`record_id`、`label.y`、`label.oracle`、`invalid_reason`、`p_t`、`surprise`、`label_key(record)`、`spec` 里的 `expect`），不留完整记录。需要整条记录的地方（例如家族首条记录的 φ 特征）在扫到那条时当场算好。
- **输出一个字节都不能变**：同一个运行目录得到的 dict 与现在完全相同（键、次序无关的取值、浮点数都一样）。门槛 `stream` 组拿一份不会再变的长跑（主检出区的 `framework/results/s08/longrun-s10code`，9500 条）核对 `json.dumps(run_metrics(...), sort_keys=True, ensure_ascii=True, separators=(",", ":"))` 的 SHA256 必须等于改造前的值（门槛 `s15_cases.STREAM_SHA256`；改造前的完整输出在 `framework/surprise/gates/s15_data/stream_expected.json`，可以拿来对比）。
- 内存：门槛在子进程里量 `run_metrics` 的峰值，必须 ≤ 800 MB；再把那本账本复制成两倍（19000 条）重量一次，峰值增加不得超过 120 MB。
- `ledger_families`、`label_key` 等公开函数的签名与结果不变（别的模块和门槛在用）；内部可以改成接受任意可迭代对象。需要的话 `metrics/curve.py` 里的 `surprise_curve` 也可以改成流式，但结果不变。
- kind 为 `"sqlancer"` 的运行：`executions` 取 `report.json` 的 `"executions"`（SQLancer 实际执行的查询数，整数）；`report.json` 缺这个值时取 `None`，凡是除以它的指标（如 `families_per_1000`）随之为 `None`。账本里的记录只是被评判的那些用例，其余指标照常从记录算。`_engines` 对 `"sqlancer"` 与 `"pure_llm"` 一样取 `config["engine"]`。

### 3. `framework/surprise/metrics/dedup.py`

离线去重现在把全部记录读进来再挑失败的。改成流式：只留下 `label.y == "fail"` 的记录。结果不变。

### 4. 测试 `framework/tests/test_surprise_s15_rundata.py`

覆盖：`iter_records` 的次序与内容和 `Ledger.records` 相同；`RunData.open` 不读入全部记录（例如断言 `Ledger.records` 没被调用）；打开前后目录里的文件不变；`kind` 的三种取值；`run_metrics` 在一个小运行目录（用主循环在测试里跑一个很短的运行，或用现有测试的做法造一个）上与改造前的实现结果相同（可以把改造前的 `run_metrics` 抄进测试当参照，或者比对已有测试的期望值）；sqlancer 运行的 `executions`；`dedup` 的结果不变。测试总时长控制在 2 分钟以内。

## 背景

- `run_metrics` 现在多处直接用整张记录表：`ledger_families`、`_profiled_keys`、`_brier`/`_valid`/`_calibration`、`surprise_curve`、`_mean(_surprise(...))`、`_high_surprise`、`_timeline` 里的 `record_id → seq` 表、`_families_via`、`_pure_llm`、`_invalid`。逐个改成从一遍扫描得到的精简数据来算。
- `harness/` 已冻结，`Ledger` 不能改；读 SQLite 的那几行写在 `rundata.py` 里。
- 门槛 `framework/surprise/gates/s15.py` 的 `stream` 组是验收标准，请读它（只读，不改）。

## 允许改动的路径

```allow-paths
framework/surprise/metrics/rundata.py
framework/surprise/metrics/rq.py
framework/surprise/metrics/dedup.py
framework/surprise/metrics/curve.py
framework/tests/test_surprise_s15_rundata.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`；不改 `framework/surprise/harness/`（已冻结）与 `HASHED_PATHS` 里的旧文件；不改 `metrics/report.py`（另一个包要改）。
- 不改任何指标的定义或取值。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。某个测试确实该改，就写进报告的"未决问题"，停下。
- 本包不需要 LLM 调用、不需要密钥；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`；不要清理 `.orch/tmp`。
- 不复制、不链接主检出区的 `framework/results/`；门槛会自己去主检出区读那份长跑（只读）。

## 验收命令

在 worktree 里执行。`python` 和 `pytest` 已经指向项目解释器，不要换别的。shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，判断结果用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests                                         # 0 failed，通过数不少于 935
python -m surprise.gates.s15 --only stream                                # PASS（约 5 分钟）
python -m surprise.gates.s11 --only runmetrics llm_metrics rq6 dedup coverage pure_llm grid   # 全部 PASS
```

S11 的 `ciao` 组与 S8 的 `longrun`、`sawtooth`、`duplicates`、`recall` 组读主检出区的长跑产物，别的包改了 `experiments/` 之后编排者会重跑长跑、重钉，你不用跑它们。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），格式见下；写明你量到的峰值。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s15-rundata

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
