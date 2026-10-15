角色：执行者

# 工作包 s11-grid：配置驱动的实验网格（臂 × 种子 × 时长 × 重复）与对照组接入

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s11-grid`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s11`（已合并 `s11-fixes`、`s11-purellm`；`s11-runmetrics`（`metrics/` 的新模块）在并行开发，网格不依赖它；`git log --oneline session/s11` 可看）。`s11-arms`（loop 的 `--freeze`、`--hunter`、`--theory-from`、`--select-from` 开关）与你并行开发：网格只把这些键原样翻成 loop 的命令行参数，你的测试不依赖它们的行为（用不带这些键的臂，或替身子进程）
- 所属会话：S11（Phase 6 评估管线），范围见 `framework/surprise/docs/SESSIONS.md` 的 S11 一节、`PLAN.md` 第 5 节 Phase 6
- 依赖：主循环 `surprise.experiments.loop`（`--llm*`、`--vocabulary`、`--bootstrap` 已有；`--freeze`、`--hunter`、`--theory-from`、`--select-from` 由并行的 `s11-arms` 加）；纯 LLM 基线 `surprise.baselines.pure_llm`；原 CoevoDB 基线 `surprise.baselines.old_no_llm`。

## 目标

SESSIONS："把 `scripts/gate2.py`、`scripts/coevo_curve.py` 泛化成配置驱动的实验网格：臂 × 种子 × 时长 × 重复"；"对照组：SQLancer（读入已有基线结果）、原 CoevoDB、纯 LLM 生成、新框架无 LLM 版"。门槛 `gates/s11.py` 的 `grid` 组（M4 冒烟：2 臂 × 2 种子的短时网格跑通、可续跑）与 `sqlancer` 组验收本包；`grid` 组后半段调用报告命令 `python -m surprise.metrics.report`（另一个包 `s11-report` 交付，可能与你并行开发），**在你的 worktree 里它会因缺报告模块失败，这是预期的；网格部分（到 `status` 检查为止）必须通过**。先把这两组的代码完整读一遍。旧脚本 `scripts/gate2.py`、`scripts/coevo_curve.py` 可以读来参考，不改、不导入。

### 1. `framework/surprise/experiments/grid.py`

**配置**（JSON 文件；`load_config(path) -> dict` 校验并补默认值，任何不合格抛 `ValueError` 写明哪一项）：

```json
{
 "schema": 1,
 "name": "s11-smoke",
 "budget": {"minutes": 1.0},
 "seeds": [0, 1],
 "repeats": 1,
 "reference": "surprise",
 "window": 10,
 "known": null,
 "prices": null,
 "arms": [
  {"name": "surprise", "kind": "surprise", "engines": ["duckdb"]},
  {"name": "old", "kind": "old_coevodb", "mode": "no_llm"}
 ]
}
```

- `budget`：`{"minutes": 数}` 或 `{"experiments": 整数}`（恰好一个键）；每个臂可以有自己的 `budget` 覆盖。`old_coevodb` 臂只认 `minutes`（旧系统没有实验数的概念），网格预算是 experiments 而它又没给自己的 minutes 时报错。
- `seeds`：非空整数列表；`repeats` ≥ 1。`reference`：一个臂名（报告以它为参照），默认第一个臂。`window`、`known`（已知 bug 文件路径，见 `metrics/recall.py`）、`prices` 原样交给报告。
- 臂名：`[a-z0-9_-]+`，不重复。`kind` 四种：
  - `"surprise"`：新框架的主循环。可选键：`engines`（默认 `["duckdb"]`）、`oracles`（默认全部七类）、`bootstrap`（列表，元素是 `{"case": SqlCase 的 dict, "oracle", "rule"}`，与 loop 的 `--bootstrap` 文件同格式）、`freeze`、`hunter`、`theory_from`、`select_from`（与 loop 的同名开关一致）、`vocabulary`（文件路径）、`beta`、`llm`（`{"roles": [...], "cache": 目录, "max_calls": 整数, "offline": bool}`；roles 非空时 `max_calls` 必须给出——HANDOFF 要求带角色的评估按预算定上限）、`python`（换解释器，例如 DuckDB 1.1.3 的 `.venvs/duckdb-1.1.3-full`）。
  - `"old_coevodb"`：原 CoevoDB。可选键 `mode`（默认 `"no_llm"`；其它模式会调用 LLM）、`python`。
  - `"pure_llm"`：纯 LLM 生成（`surprise.baselines.pure_llm`）。可选键：`engine`（默认 duckdb）、`oracles`、`llm`（`{"cache", "max_calls", "offline"}`；不离线时 `max_calls` 必须给出）。
  - `"sqlancer"`：读入已有基线结果，不跑任何东西（见第 3 节）；可选键 `summary`（文件路径，默认随包的转录文件）、`engine`（默认 duckdb）。
- 需要联网的臂（`surprise` 带角色且不离线、`pure_llm` 不离线、`old_coevodb` 的模式不是 `no_llm`）标记为 `network`；只有这样的臂的子进程环境里保留 `DEEPSEEK_API_KEY`，其余一律去掉（还有 `SURPRISE_LLM_MAX_CALLS`）。

**目录布局**（`run_grid(config, out)`，`out` 不存在则新建）：

```
out/grid.json                    # 规范化后的配置（load_config 的结果），首次运行写入；再次运行时与新配置不同就报错
out/cells/<arm>/s<seed>-r<rep>/  # 每格一个运行目录：surprise 臂是 loop 的输出目录；pure_llm 臂是 pure_llm 的输出目录；
                                 # old_coevodb 臂是 old_no_llm 的输出目录（含 old_run.json）
out/cells/<arm>/s<seed>-r<rep>/cell.json   # {"arm", "kind", "seed", "rep", "status": "done" | "failed",
                                           #  "started_at", "finished_at", "wall_s", "returncode", "command"}
out/cells/<arm>/s<seed>-r<rep>.log         # 该格子进程的标准输出与标准错误
```

（`sqlancer` 臂没有格子。）

- 每格在**子进程**里跑（`sys.executable` 或臂的 `python`，`cwd` 为 `framework/`）：`surprise` → `-m surprise.experiments.loop --out 格目录 --seed S --max-minutes M | --max-experiments N ...`（bootstrap 写成格目录旁边的文件再传；不要写进格目录本身，loop 要求输出目录为空）；`pure_llm` → `-m surprise.baselines.pure_llm ...`；`old_coevodb` → `-m surprise.baselines.old_no_llm --out 格目录 --minutes M --seed S [--mode MODE]`。子进程退出码 0 → `done`，否则 `failed`（网格继续跑别的格，最后整体退出码 1）。
- 种子：格的 seed = 配置的 seed；第 r 次重复（r 从 0 起）用同一个 seed（"重复"是同种子再跑，测墙钟与非确定性的影响）。
- 顺序：按 (rep, seed, 臂在配置里的顺序) 依次跑，让时间上的负载变化平均落到各臂上。一次只跑一格（墙钟预算要公平，不并行）。
- 续跑：`cell.json` 的 status 是 `done` 的格跳过，一个字节都不碰；目录存在但不是 `done`（中断或失败）的格，把目录改名成 `<格>.stale-<k>`（k 从 1 递增）再重跑，不删除。
- 命令行：
  - `python -m surprise.experiments.grid run CONFIG --out DIR [--only ARM]...`：退出码 0 = 所有（被选中的）格 done；
  - `python -m surprise.experiments.grid status DIR`：打印每格状态和一行汇总 `done X/Y`（Y 为应有格数），退出码 0。

### 2. `framework/surprise/baselines/old_no_llm.py`：加 `mode`

`command(out, *, seed, python, mode="no_llm")` 与 `run(out, *, minutes, seed, python=None, mode="no_llm")`，命令行加 `--mode`。`mode == "no_llm"` 时生成的命令、标签与 `old_run.json` 和现在逐字节相同（S8 门槛钉着这个基线）；别的 mode 把 `--mode` 换掉、label 用 `s11_old_<mode>_s<seed>`，`old_run.json` 的 `mode` 记实际模式；非 `no_llm` 模式子进程环境保留密钥（其余照旧去掉）。

### 3. `framework/surprise/baselines/sqlancer.py` 与 `framework/surprise/baselines/data/sqlancer_summary.json`

本机没有 SQLancer 的原始结果（`results/sqlancer_strong/` 在旧机器上，没有带过来）；仓库里只有 `docs/FINAL_REPORT.md` 的"Baseline comparison (SQLancer)"一节的汇总表。把那张表**原样转录**成 JSON：

```json
{
 "schema": 1,
 "transcribed": true,
 "source": "docs/FINAL_REPORT.md, section 'Baseline comparison (SQLancer)' (strong baseline); raw results/sqlancer_strong/ is not on this machine",
 "tool": "SQLancer 2.0.0 @9eb1db82",
 "runs": 35,
 "total_checks": 90300000,
 "total_bugs": 0,
 "approximate_checks": true,
 "engines": {
  "duckdb": {"version": "1.5.5", "oracles": 6, "checks": 7300000, "bugs": 0},
  "postgres": {"version": "16.2", "oracles": 5, "checks": 10100000, "bugs": 0},
  "sqlite3": {"version": "3.49.1", "oracles": 5, "checks": 72900000, "bugs": 0}
 },
 "note": "checks = SQLancer 'queries' (oracle checks); 7 raw flags triaged as 6 false positives and 1 unconfirmed candidate (sqlite FTS5+SUM)"
}
```

- `load(path=None) -> dict`：默认读上面的文件，校验字段。
- `metrics(summary, engine="duckdb") -> dict`：`{"kind": "sqlancer", "engine", "version", "checks", "family_count": 该引擎的 bugs, "families_per_1000": 1000*bugs/checks, "transcribed": true}`。

## 允许改动的路径

```allow-paths
framework/surprise/experiments/grid.py
framework/surprise/baselines/old_no_llm.py
framework/surprise/baselines/sqlancer.py
framework/surprise/baselines/data/sqlancer_summary.json
framework/tests/test_surprise_s11_grid.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`（已冻结）。
- 不改 `experiments/loop.py`、`baselines/pure_llm.py`、`metrics/` 等别的模块；旧代码（`main.py`、`scripts/` 等）不碰。
- 测试里**不做真实 LLM 调用**、不跑会调用 LLM 的旧系统模式；不读取或打印 `DEEPSEEK_API_KEY`（你的进程里也没有它）。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`；不要清理 `.orch/tmp`。
- 不建指向 worktree 之外的链接或目录联接。

## 验收命令

在 worktree 里执行。`python` 和 `pytest` 已经指向项目解释器，不要换别的。shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，判断结果用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests                 # 通过数不少于基线，0 failed
python -m surprise.gates.s11 --only sqlancer      # PASS
python -m surprise.gates.s11 --only grid          # 网格部分通过；若报告模块还没合并，失败点应在 "the report failed"（报告里贴出失败行）
python -m surprise.gates.s08 --only no_llm        # PASS
```

`grid` 组要真跑 4 格、每格 1 分钟，约 6 分钟。新测试覆盖配置校验（每一种错误）、布局、续跑（done 跳过、未完成改名重跑）、`status`、密钥只给联网臂、`old_no_llm` 的 `no_llm` 命令不变与新 `mode`、`sqlancer` 的 `load` / `metrics`；测试里的格子用很小的预算（几条实验）或替换子进程命令的替身，总时长控制在 4 分钟以内。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），格式见下。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s11-grid

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
