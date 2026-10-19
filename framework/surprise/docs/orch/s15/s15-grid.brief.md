角色：执行者

# 工作包 s15-grid：网格并行、块调度、每格 CPU 与引擎线程、墙钟强杀、新配置键

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s15-grid`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s15`
- 所属会话：S15（实验基础设施），范围见 `framework/surprise/docs/SESSIONS.md` 的 S15 一节；正式实验的调度要求见 `framework/surprise/docs/EXPERIMENT.md` §5、§9
- 依赖：无。同时在跑的包：`s15-llm`（让 `surprise.experiments.loop` 与 `surprise.baselines.pure_llm` 接受 `--llm-max-calls unlimited`、`--llm-tier {fast,strong}`，并在收到中断时写完报告、返回 130）、`s15-rundata`。之后还有 `s15-sqlancer`（新模块 `surprise.baselines.sqlancer_run`，命令行见下）。你只负责网格把这些参数传对；它们的实现不在本包。

## 目标

只改 `framework/surprise/experiments/grid.py`（外加一个价格数据文件与测试）。门槛 `framework/surprise/gates/s15.py` 的 `config`、`parallel`、`kill`、`prices` 四组是验收标准，请完整读它们（只读，不改），字段名、取值、命令行写法以门槛为准。

### 1. 配置（`load_config`）

顶层新键（加进 `_TOP_KEYS`；`load_config` 的结果里**总是**有这四个键，缺省时填默认值）：

| 键 | 取值 | 默认 |
|---|---|---|
| `concurrency` | 整数 ≥ 1（不能是 bool、浮点、字符串） | `1` |
| `cpus_per_cell` | 整数 ≥ 1 或 `null` | `null` |
| `engine_threads` | 整数 ≥ 1 或 `null` | `null` |
| `kill_grace_minutes` | 有限数 > 0（存成 float） | `10.0` |

臂的新键：

- `surprise` 与 `pure_llm`：`tier`，取 `null`/`"fast"`/`"strong"`，结果里总有这个键（缺省 `None`）。`surprise` 臂设了 `tier` 却没有 `llm` 块：`ValueError`。
- `llm.max_calls`（两种臂）：除了非负整数，还接受字符串 `"unlimited"`；其它字符串、负数、bool：`ValueError`。`pure_llm` 不离线时仍要求有 `max_calls`。
- `sqlancer`：新键 `run` 与 `budget`。
  - 没有 `run`（或为 `null`）：照旧只读汇总，**结果与现在完全相同**（键只有 `name, kind, summary, engine, network`）；此时出现 `budget` 是 `ValueError`。
  - `run` 为 `true`，或一个对象，可选键 `oracles`（非空、不重复，取自 `("NOREC", "WHERE")`）与 `threads`（整数 ≥ 1）。规整成 `{"oracles": [...], "threads": n}`，默认 `["NOREC", "WHERE"]` 与 `1`。别的值（`false`、未知键、坏值）：`ValueError`。
  - 运行模式下：不许有 `summary`、`tier`、`llm`；`engine` 默认 `"duckdb"`，只能取模块常数 `_SQLANCER_RUN_ENGINES = ("duckdb",)` 里的（S16–S18 再扩）；`budget` 取臂自己的或顶层的，必须是分钟预算。结果的键是 `name, kind, engine, run, budget, network`（`network` 为 `False`）。
- 不要改 `_ARM_KEYS`、`_LLM_ROLES`、`_HUNTER_OK`、`_FREEZE_OK`、`_FROZEN_ROLES` 这几个名字（门槛 s13 读它们）；往 `_ARM_KEYS` 里加新键即可。

### 2. 命令（`command_for`）

- `surprise` 臂：`max_calls` 为 `"unlimited"` 时传 `--llm-max-calls unlimited`；设了 `tier` 时在 LLM 参数之后加 `--llm-tier <档>`；没设就不加。
- `pure_llm` 臂：同上。
- `sqlancer` 运行臂：`[sys.executable, "-m", "surprise.baselines.sqlancer_run", "--out", <格目录>, "--seed", <种子>, "--engine", <引擎>, "--max-minutes", <分钟，用现有的 _cli_number>, "--oracle", <每个>..., "--threads", <n>]`。
- 只读汇总的 `sqlancer` 臂仍然没有格；运行模式的 `sqlancer` 臂有格（`_expected_cells` 与 `status_text` 都算它）。
- 默认的 `surprise` 臂（不带新键）argv 与现在逐字相同。

### 3. 调度（`run_grid`）

- **块**：把要跑的格按（重复序号、种子、引擎集合）分组。引擎集合：`surprise` 臂是 `tuple(engines)`，`pure_llm` 与 `sqlancer` 是 `(engine,)`，`old_coevodb` 是 `("duckdb",)`。块按第一次出现的次序排（现在的遍历次序：重复 → 种子 → 臂），块内按配置里臂的次序。
- **并发**：同时最多 `concurrency` 格。每个正在跑的格占一个槽位 0…concurrency−1（取最小的空槽）。有空槽才起下一格，起格的次序就是上面的块次序。已经 `done` 的格照旧跳过、打印 `<臂>/s<种子>-r<重复> done`。
- 用**单线程的轮询循环**管理子进程（`subprocess.Popen` + 短间隔 `poll`），不要开线程（Linux 上要用 `preexec_fn`，它和多线程一起用不安全）。子进程的输出照旧写到 `<格>.log`。
- **CPU 份额**：`cpus_per_cell` 设了、平台有 `os.sched_setaffinity`（Linux）时，运行开始取 `sorted(os.sched_getaffinity(0))` 当 CPU 池，槽位 k 分到池中第 `k*c` 到 `(k+1)*c−1` 个；`concurrency * c` 超过池的大小就在起任何格之前 `ValueError`。在子进程里用 `preexec_fn` 调 `os.sched_setaffinity(0, cpus)`。平台没有这个函数（Windows）时不绑，开始时打印一行提示，`cell.json` 的 `cpus` 记 `null`。
- **引擎线程数**：`engine_threads` 设了时，子进程环境里设 `SLURM_CPUS_ON_NODE=<n>`。写成模块常数 `_THREADS_ENV = "SLURM_CPUS_ON_NODE"`，注释写明原因：DuckDB 1.5.5 在 Linux 上把它当默认线程数（`.src/duckdb-v1.5.5/src/main/config.cpp` 的 `DBConfig::GetSystemMaxThreads`）。没设时环境不动。
- 密钥规则照旧：不需要网络的格，子进程环境里去掉 `_SECRET_ENV`。

### 4. 墙钟强杀

- 模块常数 `HARD_KILL_AFTER_S = 120.0`，**每次用时现读**（测试和门槛会临时改它）。
- 分钟预算的格（`surprise`、`pure_llm`、`old_coevodb`、`sqlancer` 运行臂）的期限 `deadline_s = 60 * (预算分钟 + kill_grace_minutes)`；次数预算的格没有期限（`None`）。
- 子进程放进自己的进程组：Windows 用 `creationflags=subprocess.CREATE_NEW_PROCESS_GROUP`，POSIX 用 `start_new_session=True`。
- 到期限子进程还活着：**中断**它——Windows `os.kill(pid, signal.CTRL_BREAK_EVENT)`，POSIX `os.kill(pid, signal.SIGINT)`（只发给格的主进程）。子进程（主循环、纯 LLM、SQLancer 驱动）会照中断的路径写完报告、返回 130。
- 中断后 `HARD_KILL_AFTER_S` 秒还活着：**杀掉整棵进程树**——Windows `taskkill /PID <pid> /T /F`，POSIX `os.killpg(<进程组>, signal.SIGKILL)`；然后等它退出。POSIX 上主进程退出后，再对它的进程组补发一次 `SIGKILL`（尽力而为，组已空就忽略），清掉残留的孙进程。
- 被中断过的格（不管有没有硬杀）：`status` 记 `"done"`（不再重跑：同样的配置会在同一处卡住），`killed: true`；`status_text` 里这一行是 `<臂>/s<种子>-r<重复> done (killed)`，打印的结果行也是这样。没被中断的格照旧：返回 0 是 `done`，否则 `failed`。
- `cell.json` 新增字段（每格都写）：`slot`（整数）、`cpus`（整数列表或 `null`）、`engine_threads`（整数或 `null`）、`deadline_s`（数或 `null`）、`killed`（bool）、`hard_killed`（bool）。原有字段不变。

### 5. 价格表 `framework/surprise/metrics/data/prices_deepseek.json`

新文件，内容是下面这个 JSON（解析后必须与门槛 `s15_cases.PRICES` 完全相等；数字来自 https://api-docs.deepseek.com/quick_start/pricing，2026-10-19 读取）：

```json
{
  "source": "https://api-docs.deepseek.com/quick_start/pricing",
  "retrieved": "2026-10-19",
  "currency": "USD",
  "unit": "per 1M tokens",
  "peak_hours_utc": "01:00-04:00 and 06:00-10:00, Monday to Friday, excluding Chinese public holidays",
  "models": {
    "deepseek-flash": {
      "version": "DeepSeek-V4.1-Flash-1017",
      "input_cache_hit": {"peak": 0.006, "off_peak": 0.003},
      "input_cache_miss": {"peak": 0.3, "off_peak": 0.15},
      "output": {"peak": 1.2, "off_peak": 0.6}
    },
    "deepseek-v4-pro": {
      "version": "DeepSeek-V4-Pro-0813",
      "input_cache_hit": {"peak": 0.044, "off_peak": 0.022},
      "input_cache_miss": {"peak": 1.32, "off_peak": 0.66},
      "output": {"peak": 3.96, "off_peak": 1.98}
    }
  },
  "grid": {
    "deepseek-flash": {"input": 0.3, "output": 1.2},
    "deepseek-v4-pro": {"input": 1.32, "output": 3.96}
  }
}
```

`grid` 一节就是网格配置的 `prices` 要填的东西（高峰时段的缓存未命中输入价与高峰输出价，所以报告里的成本是上界）。网格的 `prices` 校验不用改。

### 6. 测试 `framework/tests/test_surprise_s15_grid.py`

覆盖每个新键的默认值与坏值、旧配置的结果不变（S14 冒烟配置 `framework/surprise/docs/grids/s14_smoke.json` 规整后只多四个顶层键与 `tier`）、各种臂的 argv、块次序与槽位、并发上限、引擎线程环境变量、Linux 上的 CPU 绑定（用 `pytest.mark.skipif` 判平台**只限于**这一项，其它平台断言 `cpus` 为 `null`）、中断与硬杀（用 `python -c` 写的替身子进程，预算 0.05 分钟、宽限 0.05 分钟、临时把 `HARD_KILL_AFTER_S` 改成几秒）、硬杀后孙进程也不在了、`done (killed)` 的状态行、重跑不碰已完成与已强杀的格。替用子进程的写法可以参考门槛 `kill` 组。测试里用 monkeypatch 换掉 `command_for`，不跑真的主循环；总时长控制在 3 分钟以内。

## 背景

- 现在的 `run_grid` 逐格串行，用 `subprocess.run`；`_spawn` 写 `cell.json`。保持"已完成的格不打开写"、"没完成的旧目录改名 `<格>.stale-<k>` 再跑"这些规则。
- 门槛 `parallel` 组还会真跑一个 4 格并行的冒烟网格（四个不带 LLM 的 DuckDB 臂，各 1 分钟），要求四格起跑时间相差不超过 20 秒、确实同时在跑。
- Windows 上 `CTRL_BREAK_EVENT` 只能发给用 `CREATE_NEW_PROCESS_GROUP` 起的进程组；Python 默认收到它会直接退出（没有报告），所以 `s15-llm` 给主循环装了把它转成 `KeyboardInterrupt` 的处理。替身子进程要自己装（见门槛 `_HANDLES`）。
- S8 门槛的 `longrun` 组绑着 `experiments/` 的代码摘要，本包改了 `grid.py`，它会失败：这是预期的，编排者在全部合并后重跑长跑、重钉。不用跑它。

## 允许改动的路径

```allow-paths
framework/surprise/experiments/grid.py
framework/surprise/metrics/data/prices_deepseek.json
framework/tests/test_surprise_s15_grid.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`；不改 `framework/surprise/harness/`（已冻结）与 `HASHED_PATHS` 里的旧文件；不改主循环、纯 LLM 基线、角色代码（另一个包在改）。
- 不靠改测试让测试通过：不新增 skip / xfail（上面说的 Linux CPU 绑定那一项除外），不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。某个测试确实该改，就写进报告的"未决问题"，停下。
- 本包不需要 LLM 调用、不需要密钥；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`；不要清理 `.orch/tmp`。
- 不建指向 worktree 之外的链接或目录联接。

## 验收命令

在 worktree 里执行。`python` 和 `pytest` 已经指向项目解释器，不要换别的。shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，判断结果用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests                                         # 0 failed，通过数不少于 935
python -m surprise.gates.s15 --only config parallel kill prices           # 全部 PASS（config 组读到的 --llm-tier 只看 argv，不需要 s15-llm）
python -m surprise.gates.s11 --only grid sqlancer arms                    # 全部 PASS
python -m surprise.gates.s13                                              # PASS
python -m surprise.gates.s14 --only docs                                  # PASS
python -m surprise.gates.s08 --only no_llm constants scoring operators candidates lanes determinism   # 全部 PASS
```

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），格式见下。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s15-grid

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
