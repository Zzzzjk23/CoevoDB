# HANDOFF

## 状态总览

| 会话 | 内容 | 状态 | tag | 门槛 |
|---|---|---|---|---|
| S0 | 编排准备（派发工具） | 完成 | s00-done；s00-done-r2（CLAUDE.md 写入"执行者模式"之后） | 冒烟包 s00-smoke 四项确认全部通过（没有 gates/s00.py） |
| S1 | Phase 0 冻结基线与仓库整理 | 完成 | s01-done；s01-done-r2（验收后的修订，S2 从这里起） | `gates/s01.py` 7/7；pytest 64 passed, 3 skipped |
| S2 | Phase 1a 契约、账本、三类健全 oracle | 进行中（分支 `session/s02`） | | |
| S3 | Phase 1b 其余三类 oracle | 未开始 | | |
| S4 | Phase 1c CVE 流水线（M1） | 未开始 | | |
| S5 | Phase 2 φ | 未开始 | | |
| S6 | Phase 3a 理论 T 核心 | 未开始 | | |
| S7 | Phase 3b 理论存储与接受规则 | 未开始 | | |
| S8 | Phase 4 Hunter 与无 LLM 闭环（M2） | 未开始 | | |
| S9 | Phase 5a LLM 网关、实现器、猜想者 | 未开始 | | |
| S10 | Phase 5b 其余四个 LLM 角色（M3） | 未开始 | | |
| S11 | Phase 6 评估管线（M4 冒烟） | 未开始 | | |
| S12 | Phase 7 收尾 | 未开始 | | |

S0 的交接全文在 tag `s00-done-r2` 的本文件里；其中仍然有效的未决问题已并入下面的清单。

## 当前会话：S2 契约、账本、三类健全 oracle（进行中，2026-10-08）

分支 `session/s02`，起点 tag `s01-done-r2`（7632c03）。起点检查：pytest 64 passed, 3 skipped；门槛 `s01` 7/7。接手时先跑 `gw list` 看包的状态。

### 拆包清单

先合并共享接口一包，再并行两包（ORCHESTRATION.md 第 8 节）。门槛 `gates/s02.py` 分五组：`contracts`、`ledger`、`manifest`、`oracles`、`evaluate`，每个包对应其中几组，可以用 `python -m surprise.gates.s02 --only <组>` 单独跑。

| 包号 | 目标 | 允许路径 | 依赖 | 门槛组 | 状态 |
|---|---|---|---|---|---|
| s02-contracts | 五个数据契约（harness 侧：SQL 用例、身份证据、标签、实验记录；理论侧：规格、假设、理论编辑）与序列化；harness 常数模块；SQLite 实验账本 | `framework/surprise/harness/contracts.py`、`constants.py`、`ledger.py`，`framework/surprise/theory/contracts.py`，`framework/tests/test_surprise_contracts.py`、`test_surprise_ledger.py` | 无 | contracts、ledger | 待派发 |
| s02-manifest | run manifest、harness 哈希、校验命令 `python -m surprise.harness.manifest hash/write/verify` | `framework/surprise/harness/manifest.py`，`framework/tests/test_surprise_manifest.py` | s02-contracts | manifest | 待派发 |
| s02-oracles | TLP（WHERE、GROUP BY、DISTINCT 三种形态）、NoREC、Plan variant 的三值适配器与身份证据；`evaluate()` 把每次执行写进账本 | `framework/surprise/harness/oracles/**`、`framework/surprise/harness/evaluate.py`，`framework/tests/test_surprise_oracles.py`、`test_surprise_evaluate.py` | s02-contracts | oracles、evaluate | 待派发 |

## 最近一次会话：S1 冻结基线与仓库整理（2026-10-08）

分支 `session/s01`，起点 tag `s00-done-r2`（4eaa4ed），收尾合并回 main 并打 `s01-done`。

### 完成了什么

- 基线核对：tag `v1-baseline` 已存在，指向 55c5512，没有重打；`.env` 没有被跟踪。
- 测试基线：`.venv` 装了 psycopg2-binary 之后，`cd framework; ../.venv/Scripts/python.exe -m pytest -q testing tests` → **64 passed, 3 skipped**，退出码 0。3 个跳过都是因为没有 PostgreSQL（2 个缺 `pgserver` 包，1 个没有 PG 构建）。装之前是收集阶段失败。整理之后仍是 64 passed, 3 skipped。
- 旧系统基线 run：整理之前跑了 `python main.py --engine duckdb --mode no_llm --iterations 2`，退出码 0，存档在 `framework/surprise/docs/baseline/`（说明见该目录的 README.md）。整理之后用同一条命令重跑，`summary.json` 除计时字段外与存档完全相同（3992 次 SQL 执行、0 候选）。full 模式没跑。
- 引擎环境（都不入库）：`.venv` 加装 DataFusion 54.0.0 与 psycopg2-binary 2.9.13；新建 `.venvs/duckdb-1.1.3`（DuckDB 1.1.3 + psycopg2-binary）与 `.venvs/datafusion-50.0.0`（DataFusion 50.0.0）。路径与版本已填进 CLAUDE.md。
- 仓库整理（工作包 s01-reorg，只有移动）：
  - 41 个 `framework/scripts/pg_*.py` 移到 `framework/campaigns/`。39 个文件内容不变；`pg_probe_run.py`、`pg_ssi_sibling.py` 各改一行导入路径（`scripts.` → `campaigns.`）。`scripts/` 里还剩 29 个非 PG 脚本。
  - `class DuckDBRunner` 移到 `framework/targets/duckdb_runner.py`，类体与基线逐字节相同。`oracles/db_runner.py` 保留 `QueryResult` 与 `bags_equal`，并在文件末尾兼容导出 `DuckDBRunner`；所有调用方都没有改。
- `framework/surprise/` 骨架：`__init__.py` 与九个子包（`harness features theory hunter diagnoser roles metrics experiments baselines`），每个只有一行文档字符串；`gates/` 有 `all.py` 与 `s01.py`。
- CLAUDE.md 改了两处（用户同意）："引擎环境"填了实际路径与版本；测试命令写明用 `.venv` 的解释器。`.gitignore` 加了 `.venvs/`。

### 门槛结果

在 `session/s01` 合并之后、主检出区里跑的：

| 命令（在 `framework/` 下，解释器 `../.venv/Scripts/python.exe`） | 结果 |
|---|---|
| `-m pytest -q testing tests` | 64 passed, 3 skipped，退出码 0 |
| `-m surprise.gates.all` | `s01: PASS`（7/7），退出码 0 |

`gates/s01.py` 的七项：tag `v1-baseline` 指向 55c5512；骨架存在且能导入；三个环境各自在自己的解释器里报出期望版本（主环境 DuckDB 1.5.5、DataFusion 54.0.0、SQLite 3.51.0）；`main.py --help` 退出码 0；pytest 退出码 0 且通过数不少于 64；41 个脚本都在 `campaigns/`，其中 39 个 `--help` 正常（与整理前相同）；`DuckDBRunner` 在六种导入顺序下都是同一个类，旧版 venv 里 `oracles._remote_exec` 能导入。

### 工作包

| 包号 | 目标 | 结论 |
|---|---|---|
| s01-reorg | PG 脚本移到 `campaigns/`；`DuckDBRunner` 移到 `targets/duckdb_runner.py`；`surprise/` 骨架 | 一次通过，返工 0 轮。3 个提交，11 分 22 秒，grok 上报花费 0.60 美元。审查包唯一的红旗（"新增宽泛的异常捕获 4 处"）是误报：那是随类搬走的原有代码 |

brief、report、审查包（含编排者的结论）在 `framework/surprise/docs/orch/s01/`。

### 新增或改动的接口

- `framework/surprise/gates/all.py`：`python -m surprise.gates.all`（在 `framework/` 下）把每个 `gates/sNN.py` 当独立进程依次运行，全部通过才退出码 0。输出只用 ASCII。之后每个会话加一个 `sNN.py` 即可，不用改 `all.py`。
- `framework/surprise/gates/s01.py`：引擎 venv 不入库、放在主检出区，门槛经 git 的公共目录找到它们，所以在 worktree 里也能跑；环境变量 `COEVO_VENVS` 可以覆盖 venv 所在目录。
- `framework/targets/duckdb_runner.py`：`DuckDBRunner` 的定义处。`from oracles.db_runner import DuckDBRunner, QueryResult, bags_equal` 照旧可用；`QueryResult`、`bags_equal` 的定义仍在 `oracles/db_runner.py`。
- `framework/campaigns/pg_*.py`：PG 专项脚本的新位置，用法是在 `framework/` 下 `python campaigns/pg_xxx.py …`，模块名 `campaigns.pg_xxx`。和 `scripts/` 一样没有 `__init__.py`。
- 引擎环境：见 CLAUDE.md 的"引擎环境"。解释器是 `<venv>/Scripts/python.exe`。
- 基线存档：`framework/surprise/docs/baseline/`。

### 与 PLAN 的偏差及原因

与 PLAN.md 没有冲突。和 SESSIONS.md 的 S1 一节有这几处出入，细节在 DECISIONS.md：

- `oracles/db_runner.py` 不是纯 re-export。整体搬走会循环导入（`targets/__init__.py` → `postgres_runner` → `oracles.db_runner` → `targets.duckdb_runner`），实测报 ImportError；所以只搬 `DuckDBRunner`，共享的 `QueryResult`、`bags_equal` 留下。
- 门槛比 SESSIONS 列的四项多三项（tag 指向、campaign 脚本对照、导入顺序与旧版子进程入口）；pytest 判定是"不少于 64"而不是"等于 64"，这样之后的会话加了测试，本门槛仍然通过。
- SESSIONS 里"确认在 git 管理下、补 `.gitignore`、打 `v1-baseline`"三条在基线提交和 S0 时已经做完，本会话只核对。
- PLAN 没有指定旧版 DataFusion 的版本，选了 50.0.0。
- 旧版 DuckDB 的 venv 里多装了 psycopg2-binary（原因见未决问题第 1 条）。

### 验收后的修订（s01-done-r2，2026-10-08）

用户验收时让编排者把点名的五处人工检查项复核一遍，并按编排者的推荐处理其中没定的事。复核结果与 `s01-done` 时报告的一致，没有改任何代码和门槛；改动只有文档：

- CLAUDE.md 的门槛命令也写明了解释器：`../.venv/Scripts/python.exe -m surprise.gates.all`。
- 下面未决问题第 1、2、6、8、9 条写上了处理决定；第 1 条原先只提 psycopg2，不完整，已改正。
- 决定都记在 DECISIONS.md。

### 未决问题（S2 及之后需要知道的）

S1 新发现：
1. 要导入 `oracles.*` 或 `targets.*`，解释器里必须同时有 duckdb 和 psycopg2。duckdb 是一直都要的（`oracles/__init__.py` 导入 `db_runner`，它在模块顶层 `import duckdb`）；psycopg2 是这次移动带来的（`oracles/db_runner.py` → `targets/duckdb_runner.py` → `targets/__init__.py` → `postgres_runner`）。`.venvs/duckdb-1.1.3` 两样都有，`oracles._remote_exec` 能导入（门槛在查）。`.venvs/datafusion-50.0.0` 两样都没有，实测 `import targets.datafusion_runner` 先缺 psycopg2、再缺 duckdb。**决定**：这个 venv 保持只有 DataFusion，不为了凑导入链往里装别的引擎；S3 给旧版 DataFusion 写的子进程入口只导入 `datafusion` 和标准库，把原始行用 JSON 传回，归一化在主进程里做。S3 开工时觉得不合适可以推翻，装包只是一条命令。根治要改 `targets/__init__.py`，那是 S12 才允许的事。
2. 旧代码把旧版解释器写死成 `<venv>/bin/python`（`oracles/differential.py` 第 37 行、`main.py` 第 142 行），Windows 上 venv 的解释器是 `Scripts/python.exe`。所以旧主循环在这台机器上 Version differential 恒为 disabled，本会话的基线 run 里也没有它。**决定**：S12 之前不改旧代码，也不在 venv 里造一个 `bin/python` 的替身；S3 的 Version differential 适配器自己按平台定位解释器（`gates/s01.py` 的 `venv_python()` 是现成的写法）。旧主循环缺这一类信号的影响有限：它在旧系统里只记 `version_divergence`，单独命中不计为 bug（PLAN.md 第 3 节逐项表）。S11 跑对照组时如果需要它，再向用户提出，到 S12 允许改旧逻辑时修。
3. `campaigns/pg_upgrade_mxact.py` 第 55 行在模块顶层抛 TypeError（`str(...) / "results"`），连 `--help` 都跑不了。旧 bug，没修。
4. `campaigns/pg_repack_mvcc.py` 没有 argparse 也没有 `__main__` 守卫，导入即执行。门槛对这两个脚本只查语法。
5. 文档里还是旧路径 `scripts/pg_*.py`：`framework/AGENTS.md`、`STATUS_AND_ROADMAP.md`、`NEXT_RESEARCH_PLAN.md`、几份 `PG_*PLAN*.md`、`seeds/pg_transform_probes*.py` 的文档字符串，以及 campaign 脚本自己的用法说明。留给 S12 更新文档时一起改。
6. `gates/s01.py` 里写死了：41 个脚本、基线通过数 64、三个环境的版本号、`v1-baseline` 的提交号。**决定**：保留不改，它们记录的就是冻结下来的基线事实。S12 再移动旧代码或换引擎版本时要同步改这个门槛，改之前问用户。
7. `.venv` 是 `include-system-site-packages = true` 的 uv venv，底下是 anaconda base（pyarrow 21.0.0、pandas 等都来自 anaconda）。环境不完全可复现；S2 的 run manifest 如果记录依赖版本，要记实际解析到的版本。
8. （已关闭）CLAUDE.md 的门槛命令原先没有写明解释器，`s01-done-r2` 里已改成 `../.venv/Scripts/python.exe -m surprise.gates.all`。ORCHESTRATION.md 和任务说明模板里的 `python -m surprise.gates.all` 没有动：前者是泛指，后者是给执行者的，执行者的 `python` 本来就指向项目解释器。
9. 两处不影响行为的小出入：`oracles/db_runner.py` 里 import 与 `@dataclass` 之间少一个空行；`DuckDBRunner` 的 debug 日志记录器名字从 `oracles.db_runner` 变成了 `targets.duckdb_runner`。**决定**：都不返工。空行等 S12 整理旧代码时顺手补；记录器改名是把类搬走的必然结果，没有测试或配置依赖旧名字。
10. 执行者写文件用的是放在 `.orch/tmp` 的 Python 脚本，deny 规则管不到这种写法（与 S0 的结论一致）。本包以 diff 为准核对过，没有越界；之后的包照旧靠审查兜底。

沿用自 S0 与规划会话、仍然有效的：
- 仓库没有配置远端（`git remote -v` 为空），异地备份是用户的事。
- 新会话里 Claude Code 的安全分类器可能拒绝启动 grok（本会话没有被拒）。用户的长期批准记在 DECISIONS.md；再被拒就停下来问用户，不要绕过。
- deny 规则挡不住包一层再执行的命令（`cmd /c …`、`powershell -Command …`、`python -c …`），也挡不住用 shell 或脚本写禁区文件，见 ORCHESTRATION.md 第 10 节。
- 执行者的 shell 是 Windows PowerShell 5.1：没有 `&&`，中文输出乱码。
- `SESSIONS.md` 开头还写着开场提示词在 `claude/coevodb-session-runbook.md`，实际是同目录的 `RUNBOOK.md`。那是用户的文件，没有改。
- `%USERPROFILE%\.grok\config.toml` 里没有 `auto_update = false`；脚本每次都传 `--no-auto-update`，派发不受影响。
- `framework/test_api.py` 在设置了 `DEEPSEEK_API_KEY` 时会真的调用 API；日常测试命令只跑 `testing/` 和 `tests/`。
- `coevo/` 被 `tests/test_verified_loop.py` 依赖，S1 没有动；它的新进程执行在 S4 被吸收，S12 再归档。
- `framework/config.yml` 里 `database.version` 写的是 1.5.2，实际是 1.5.5；`database.old_venv` 是旧机器上的路径，以环境变量 `COEVO_OLD_VENV` 为准（本机没有设置）。
- PLAN.md 决策表第 2、4–10 条仍是建议，到对应会话开工时再定。S2 会碰到第 6 条（实验账本用 SQLite）。

### 下一会话的起点

- S2 从 tag `s01-done-r2` 建分支 `session/s02`（`s01-done` 不含验收后的修订，不要从它起）。
- 起点检查（在 `framework/` 下）：`../.venv/Scripts/python.exe -m pytest -q testing tests` 应为 64 passed, 3 skipped；`../.venv/Scripts/python.exe -m surprise.gates.all` 应为 `GATES: PASS (1/1 passed)`。
- S2 按 ORCHESTRATION.md 第 8 节拆：先五个数据契约一包并合并，再两包并行。审查时 `--expect-passed 64`。
- 派发脚本一律用 `.venv/Scripts/python.exe tools/orch/grok_worker.py …`；合并时设 `ORCH_COMMIT_TRAILER` 给合并提交加署名尾注。
- 收尾合并回 main 时注意：`git merge` 不能用 `-F -` 从标准输入读提交信息，要用 `-m`；合并成功并核对过之后再打 tag，两步不要用 `;` 连在一条命令里。S1 收尾时就因为这个把 `s01-done` 打在了旧的 main 上，当场删掉重打了。
