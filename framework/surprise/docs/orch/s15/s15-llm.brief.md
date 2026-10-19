角色：执行者

# 工作包 s15-llm：LLM 调用可以不设上限、整次运行换模型档、Windows 上的中断

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s15-llm`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s15`
- 所属会话：S15（实验基础设施），范围见 `framework/surprise/docs/SESSIONS.md` 的 S15 一节
- 依赖：无。同时在跑的包：`s15-grid`（改 `experiments/grid.py`，会按下面"命令行"一节的写法给子进程传参数）、`s15-rundata`。

## 目标

正式实验（`framework/surprise/docs/EXPERIMENT.md`）要求 LLM 调用不设上限、A11 臂全部角色用 strong 档；网格到 24 小时会中断还没结束的格。本包让网关、主循环与纯 LLM 基线支持这三件事。**不传新参数时，行为与现在一个字节都不差**（缓存键、`calls.jsonl`、`config.json`、run manifest 全部不变）。

### 1. 网关 `framework/surprise/roles/gateway.py`

- 模块级常数 `UNLIMITED = "unlimited"`（放在 gateway.py，**不要**放进 `roles/constants.py`：那里的全部大写常数会经 `as_dict()` 写进每次运行的 manifest）。
- `Gateway(..., max_calls=...)` 接受：
  - `None`：照旧，用 `DEFAULT_MAX_CALLS`（200）；
  - 非负整数（不能是 bool）：照旧；
  - 字符串 `"unlimited"`：网关自己不设上限；
  - 其它任何值（别的字符串，包括 `"5"`、负数、浮点数、bool）：`ValueError`。
- 环境变量上限 `CAP_ENV`（`SURPRISE_LLM_MAX_CALLS`）照旧生效：它是整数时，有效上限 = min(配置的上限, 它)；配置为 `"unlimited"` 时有效上限就是它。
- `max_calls` 属性：有上限时是整数，没有上限时是 `None`。`totals()` 与 `manifest()` 里的 `"max_calls"`：有上限写整数，没有上限写字符串 `"unlimited"`。不设上限时，`call` 里"达到上限就拒绝"的那条判断永远不触发。
- 新关键字参数 `tier: str | None = None`：
  - `None`：照旧，每次调用用调用方传的 `tier`；
  - `TIERS` 里的键（`"fast"`、`"strong"`）：这个网关的**每一次**调用都改用这一档：模型取 `TIERS[override]`，缓存键用这个模型，`Reply.tier` 与 `Reply.model` 是实际用的档与模型，`calls.jsonl` 一行里的 `tier`、`model` 也是实际用的；
  - 其它值：`ValueError`。
- `manifest()`：只在设了 `tier` 时多一个键 `"tier": <档名>`；没设时不出现这个键。

### 2. 角色运行时 `framework/surprise/roles/runtime.py`

- 主循环传来的 LLM 配置里可以有 `"tier"`（`None`/`"fast"`/`"strong"`），原样传给 `Gateway(tier=...)`；`max_calls` 可以是 `"unlimited"`，原样传给网关。
- 运行时写进 manifest 的 `"max_calls"`（第 293 行附近）与网关一致：没有上限时写 `"unlimited"`；设了 `tier` 时多一个 `"tier"` 键，没设时不出现。

### 3. 主循环 `framework/surprise/experiments/loop.py`

- `run(..., llm={...})` 的校验：`max_calls` 可以是 `None`、非负整数或 `"unlimited"`；新键 `tier` 可以缺省、`None`、`"fast"` 或 `"strong"`；其它值 `UsageError`。
- `config.json` 里的 `"llm"`：`max_calls` 照传入的写（`"unlimited"` 写字符串）；`tier` 只在不是 `None` 时写这个键（缺省时 `config.json` 与现在相同）。
- 命令行：
  - `--llm-max-calls` 接受非负整数或 `unlimited`，其它值由 argparse 报错（`main` 返回 2）；
  - 新参数 `--llm-tier {fast,strong}`，与 `--llm-cache` 等一样要求有 `--llm`，否则 `UsageError`（返回 2）。
- 中断：`main()` 开头在 Windows 上把 `signal.SIGBREAK` 的处理函数设成抛 `KeyboardInterrupt`；在 POSIX 上把 `signal.SIGTERM` 设成同样的处理（SIGINT 本来就会抛）。这样网格发 `CTRL_BREAK_EVENT`（Windows）或信号（POSIX）时，运行照现有的 `KeyboardInterrupt` 路径结束：报告状态 `"interrupted"`，写完 `report.json`，`main` 返回 130。只在 `main()` 里装，`import` 时不装。

### 4. 纯 LLM 基线 `framework/surprise/baselines/pure_llm.py`

- `run(..., max_calls=...)` 与命令行 `--llm-max-calls` 同样接受 `"unlimited"`。
- 新参数 `tier`（`run(tier=None)`、命令行 `--llm-tier {fast,strong}`）：设了就传给 `Gateway(tier=...)`；不设时照旧用 `PURE_LLM_TIER`。`config.json` 与 manifest 只在设了时记 `tier`。
- `main()` 装同样的中断处理。

### 5. 测试 `framework/tests/test_surprise_s15_llm.py`

覆盖：默认上限 200 不变；`"unlimited"` 的 `max_calls` 属性、`manifest()`、`totals()`；环境变量上限压住 `"unlimited"`；坏值 `ValueError`；`tier="strong"` 时 transport 收到 `deepseek-v4-pro`、`Reply.tier/model`、`calls.jsonl` 一行；不设 `tier` 时 manifest 没有这个键；`loop.run` 与 `pure_llm.run` 的新校验与 `config.json`；两个命令行的新参数与坏值（返回 2）；中断：用子进程跑一个很短的主循环（`--max-minutes 2`、DuckDB、两个 oracle），看到 `progress.jsonl` 有几行后，Windows 上用 `CREATE_NEW_PROCESS_GROUP` 起进程、`os.kill(pid, signal.CTRL_BREAK_EVENT)`，POSIX 上 `os.kill(pid, signal.SIGTERM)`，断言返回 130、`report.json` 的 `status` 是 `"interrupted"`。用 S9 门槛里那种假 transport（`surprise/gates/s09.py` 的 `Script`）做网关测试，不要真调用。测试总时长控制在 3 分钟以内。

## 背景

- 网关的上限只数网络调用（`self._network_calls`）；离线模式（`--llm-offline`）下缓存未命中时角色得到 `status="miss"`，主循环照常往下跑，纯 LLM 基线以 `llm_exhausted` 结束。
- 门槛 `framework/surprise/gates/s15.py` 的 `llm` 组是本包的验收标准，请读它（只读，不改）：它用 S10 录下的 M3 缓存（`gates/s10_llm/m3`）以 `--llm-max-calls unlimited` 回放，要求逐行等于录制；以 `--llm-tier strong` 回放，要求每次调用都问 `deepseek-v4-pro`、都没命中 fast 档的缓存；纯 LLM 基线（`gates/s11_llm/pure_llm`）同样两遍。
- S8 门槛的 `longrun` 组绑着 `experiments/` 的代码摘要，本包改了 `loop.py`，它会失败：这是预期的，编排者在全部合并后重跑长跑、重钉。不用跑它。

## 允许改动的路径

```allow-paths
framework/surprise/roles/gateway.py
framework/surprise/roles/runtime.py
framework/surprise/experiments/loop.py
framework/surprise/baselines/pure_llm.py
framework/tests/test_surprise_s15_llm.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`；不改 `framework/surprise/harness/`（已冻结）与 `HASHED_PATHS` 里的旧文件；不改 `roles/constants.py`。
- 不改主循环与纯 LLM 基线的其它行为：不传新参数时，回放（S9 `replay`、S10 `m3`、S11 `pure_llm`）逐行相同。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。某个测试确实该改，就写进报告的"未决问题"，停下。
- 本包不需要真实 LLM 调用、不需要密钥；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`；不要清理 `.orch/tmp`。
- 不建指向 worktree 之外的链接或目录联接。

## 验收命令

在 worktree 里执行。`python` 和 `pytest` 已经指向项目解释器，不要换别的。shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，判断结果用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests                                         # 0 failed，通过数不少于 935
python -m surprise.gates.s15 --only llm                                   # PASS
python -m surprise.gates.s09                                              # PASS
python -m surprise.gates.s10                                              # PASS
python -m surprise.gates.s11 --only constants deadline arms pure_llm_script pure_llm   # 全部 PASS
python -m surprise.gates.s08 --only no_llm constants scoring operators candidates lanes determinism   # 全部 PASS
```

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），格式见下。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s15-llm

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
