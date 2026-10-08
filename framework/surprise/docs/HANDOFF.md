# HANDOFF

## 状态总览

| 会话 | 内容 | 状态 | tag | 门槛 |
|---|---|---|---|---|
| S0 | 编排准备（派发工具） | 完成 | s00-done；s00-done-r2（CLAUDE.md 写入"执行者模式"之后，S1 从这里起） | 冒烟包 s00-smoke 四项确认全部通过（没有 gates/s00.py，见下） |
| S1 | Phase 0 冻结基线与仓库整理 | 进行中（分支 `session/s01`） | | |
| S2 | Phase 1a 契约、账本、三类健全 oracle | 未开始 | | |
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

## 当前会话：S1 冻结基线与仓库整理（进行中，2026-10-08）

分支 `session/s01`，起点 tag `s00-done-r2`（4eaa4ed）。接手时先跑 `gw list` 看包的状态。

### 已完成（编排者直接做的）

- tag `v1-baseline` 核对：存在，指向 55c5512，没有重打。
- 测试基线：`.venv` 装了 psycopg2-binary 之后，`cd framework; ../.venv/Scripts/python.exe -m pytest -q testing tests` → **64 passed, 3 skipped**，退出码 0。3 个跳过都是因为没有 PostgreSQL（2 个缺 `pgserver` 包，1 个没有 PG 构建）。装之前是收集阶段失败（S0 未决问题第 1 条，用户决定装）。
- 旧系统基线 run：`python main.py --engine duckdb --mode no_llm --iterations 2`，退出码 0，存档在 `framework/surprise/docs/baseline/`（说明见该目录的 README.md）。full 模式没跑。
- 引擎环境（都不入库，`.gitignore` 加了 `.venvs/`）：`.venv` 加装 DataFusion 54.0.0 与 psycopg2-binary 2.9.13；新建 `.venvs/duckdb-1.1.3`（DuckDB 1.1.3 + psycopg2-binary）与 `.venvs/datafusion-50.0.0`（DataFusion 50.0.0）。已填进 CLAUDE.md 的"引擎环境"，测试命令也写明了解释器（两处改动用户已同意）。
- 整理前记录：41 个 `scripts/pg_*.py` 里，39 个 `--help` 正常；`pg_repack_mvcc.py` 没有 argparse、导入即执行；`pg_upgrade_mxact.py` 在模块顶层就抛 TypeError（旧 bug，不修）。

### 拆包清单

S1 是纯移动，按 ORCHESTRATION.md 第 8 节串行单包。

| 包号 | 目标 | 允许路径 | 依赖 | 状态 |
|---|---|---|---|---|
| s01-reorg | ① 41 个 `framework/scripts/pg_*.py` 移到 `framework/campaigns/`，只改两处 `scripts.pg_*` 导入路径；② `DuckDBRunner` 移到 `framework/targets/duckdb_runner.py`，`oracles/db_runner.py` 保留 `QueryResult`、`bags_equal` 并 re-export `DuckDBRunner`；③ `framework/surprise/` 骨架：`__init__.py` 与九个子包的 `__init__.py` | `framework/campaigns/**`、`framework/scripts/pg_*.py`、`framework/targets/duckdb_runner.py`、`framework/oracles/db_runner.py`、`framework/surprise/__init__.py`、`framework/surprise/{harness,features,theory,hunter,diagnoser,roles,metrics,experiments,baselines}/__init__.py` | 无（`gates/` 由编排者先写好并提交） | 待派发 |

门槛 `framework/surprise/gates/s01.py`（编排者写）：tag、骨架、三个环境的版本、`main.py --help`、pytest 通过数不少于 64、移动后的布局与导入顺序。

## 上一次会话：S0 编排准备（2026-10-08）

### 完成了什么

- 派发脚本 `tools/orch/grok_worker.py`（只用标准库）：`spawn`、`status`、`review`、`resume`、`merge`、`cleanup`、`list`。
- 任务说明模板 `framework/surprise/docs/orch/BRIEF_TEMPLATE.md`；编排流程与审查清单 `framework/surprise/docs/ORCHESTRATION.md`。
- `SESSIONS.md` 加了 S0 一节；本文件状态表加了 S0 一行。`.gitignore` 在基线提交里已经有 `.worktrees/` 与 `.orch/`，没有再改。
- CLAUDE.md 加了"执行者模式"一节，"收尾协议"改名为"收尾协议（编排者）"并写明门槛在派发前写好，"命令"一节加了编排命令一行。草稿经用户 2026-10-08 同意后写入，tag `s00-done-r2`。写入之后没有再派发过工作包，新的一节还没有被执行者实际读过。
- 没有碰 S1 的范围，没有写任何框架代码。

### 门槛结果

S0 没有 `gates/s00.py`（`surprise.gates` 由 S1 建立），用冒烟包验收。四项都由编排者从日志和仓库状态独立核实，不是采信执行者的报告：

| 确认项 | 结果 | 证据 |
|---|---|---|
| grok 无交互跑完 | 通过 | s00-smoke：退出码 0，3 分 17 秒，12 个模型回合，全程没有提示 |
| `git tag` 被拒 | 通过 | 日志：`Denied by permission policy: deny rule on bash matching "git tag*"`；之后仓库里仍只有 `v1-baseline` |
| 日志可读 | 通过 | `.orch/logs/s00-smoke.jsonl` 668 行全部能按 JSON 解析，`status` 与审查包都能给出摘要 |
| 子进程里没有 `DEEPSEEK_API_KEY` | 通过 | 派发时父进程环境里放了一个假的哨兵值；脚本记录子进程环境里没有它，grok 在自己的 shell 里查到 `KEY_STATUS=absent` |

流程 `spawn → status → review → cleanup --abandon` 走完，仓库回到只有主检出区一个 worktree、没有 `grok/` 分支、没有多余 tag。

另外验证了三件开场提示词没有要求的事：
- 13 条 deny 探测（s00-deny）全部被拦下：`Remove-Item -Recurse -Force`、`rm -rf`、`git -C . tag`、`git push`、`git merge`、`git rebase`、`git reset --hard`、`git worktree`、`git branch -D`，以及用编辑工具写 `gates/`、`docs/`、`.grok/` 和用绝对路径写主检出区的 `gates/`。
- `resume` 用 `--resume <UUID>` 续接原会话可用，上下文保留（s00-deny 第 2 轮）。
- `merge`、超时终止、并行上限、违规扫描这几条路径没有用真 grok 跑，是用一个替身程序在仓库的临时克隆里验证的：合并加归档提交、超时被杀并记为 TIMED OUT、故意违规的替身被审查扫出 11 条红旗。

### 工作包

| 包号 | 目标 | 结论 |
|---|---|---|
| s00-smoke | 新建 `scratch/hello.txt` 并提交；试一次 `git tag`、一次编辑 CLAUDE.md；报告 shell 与密钥变量是否存在 | 一次通过；按计划 `--abandon`，不合并 |
| s00-deny | 13 条 deny 探测；再用一轮返工验证 `resume` | 一次通过，另有 1 轮返工（为测试 `resume` 特意安排）；`--abandon`，不合并 |

两个包的 brief、report、审查包（s00-deny 还有返工意见）留在 `framework/surprise/docs/orch/s00/`。两个包的审查包里都有一条红旗"pytest 未通过"，那是基线本身的问题，见下面未决问题第 1 条。`s00-deny.review.md` 第 6 节写的是"拦下 14 次"，真实数字是 13：第 14 条是一次读报告的调用被误计，计数的 bug 已修，归档文件保持生成时的原样。

### 新增或改动的接口

- `tools/orch/grok_worker.py`：见 `ORCHESTRATION.md` 第 5 节的命令表。状态在 `.orch/state/<包号>.json`，日志在 `.orch/logs/<包号>.jsonl`，审查包在 `.orch/reviews/<包号>.md`。
- 任务说明的约定：第一行"角色：执行者"（否则 `spawn` 拒绝）；允许路径写在 ```` ```allow-paths ```` 块里，`review` 按它判越界。
- 环境变量：`ORCH_GROK_CMD`（指定 grok 程序）、`ORCH_COMMIT_TRAILER`（合并与归档提交的尾注）、`ORCH_ROOT`。

### 与 PLAN 的偏差及原因

- 与 PLAN.md 没有偏差（S0 不涉及框架）。
- 与 S0 开场提示词的偏差都记在 `DECISIONS.md` 的 S0 条目里，主要是：会话号改用 UUID、续接改用 `--resume`；派发默认前台阻塞、由后台任务承载；deny 规则比提示词列的多；多跑了一个探测包。

### 未决问题（S1 需要知道的）

S0 新发现：
1. 测试基线不是绿的。用 `.venv` 跑 `pytest -q testing tests`，收集阶段就失败（`tests/test_pg_local_server.py` 导入 `psycopg2`，`.venv` 里没有），退出码 2；加 `--continue-on-collection-errors` 是 61 passed、2 skipped、1 error。S1 的"起点不绿先停下来"会在这里触发，需要用户决定是装 psycopg2 还是别的处理。
2. PATH 上的 `pytest` 和 `python` 是 anaconda 的，没有 duckdb（那样跑是 7 个收集错误）。项目解释器是仓库根的 `.venv`（Python 3.13.9，duckdb 1.5.5，pytest 9.1.1）。CLAUDE.md 的测试命令没有写明解释器，S1 填"引擎环境"时一并写清。
3. `.venv` 里没有 datafusion 和 sqlglot（S1 要装 DataFusion 54.0.0；sqlglot 到 S5 才用）。
4. 仓库根有 `duckdb/`、`datafusion/` 两个目录（放复现 SQL）。在仓库根执行 `import duckdb` 时，真包没装也会导入成功（当成命名空间包）。`gates/s01.py` 检查环境时要看 `__version__`，或者换个工作目录。
5. tag `v1-baseline` 已经存在，指向基线提交 55c5512。S1 不用再打，核对即可。
6. 仓库没有配置远端（`git remote -v` 为空）。RUNBOOK 准备清单建议有异地备份，这是用户的事。
7. （已关闭）CLAUDE.md 的"执行者模式"已写入，见 tag `s00-done-r2`。S0 的两个冒烟包是在写入之前跑的，当时只靠任务说明约束。
8. 新会话里 Claude Code 的安全分类器可能再次拒绝启动 grok（本会话里拒了三次，用户明确批准后才放行）。用户的长期批准记在 `DECISIONS.md`；再被拒就停下来问用户，不要绕过。
9. deny 规则挡不住包一层再执行的命令（`cmd /c …`、`powershell -Command …`、`python -c …`），也挡不住用 shell 写禁区文件。靠审查兜底，见 `ORCHESTRATION.md` 第 10 节。
10. 执行者的 shell 是 Windows PowerShell 5.1：没有 `&&`，中文输出乱码。模板已注明。
11. `SESSIONS.md` 开头还写着开场提示词在 `claude/coevodb-session-runbook.md`，实际是同目录的 `RUNBOOK.md`。那是用户的文件，没有改。
12. `%USERPROFILE%\.grok\config.toml` 的 `[cli]` 下没有 `auto_update = false`（RUNBOOK 准备清单里有这一条）。脚本每次都传 `--no-auto-update` 并设 `GROK_DISABLE_AUTOUPDATER=1`，派发不受影响。
13. 不确定 grok 在 worktree 里读到 CLAUDE.md 是靠脚本传的 `--trust`，还是靠用户对 `D:\CoevoDB` 的信任。实测读到了；`trusted_folders.toml` 里只有 `D:\CoevoDB` 一条。

规划会话留下、仍然有效的：
- `framework/test_api.py` 在设置了 `DEEPSEEK_API_KEY` 时会真的调用 API；日常测试命令只跑 `testing/` 和 `tests/`。
- `coevo/` 被 `tests/test_verified_loop.py` 依赖，S1 不归档。
- `framework/config.yml` 里 `database.version` 写的是 1.5.2，实际目标是 1.5.5；`database.old_venv` 是旧机器上的路径，以环境变量 `COEVO_OLD_VENV` 为准。
- PG 专项脚本靠 `sys.path` 的相对位置找框架代码，移动时保持目录深度（见 SESSIONS.md 的 S1）。
- PLAN.md 决策表第 2、4–10 条仍是建议，到对应会话开工时再定。
- 规划会话提到的 `.gitignore` 缺 `.venv/`、`.uv-cache/`、根目录 `results/`：基线提交里已经补上，这条关闭。

### 下一会话的起点

- 先处理未决问题第 1 条（测试基线不绿），需要用户拍板。
- S1 用 `RUNBOOK.md` 第 5 节的编排版开场提示词，从 tag `s00-done-r2` 建分支 `session/s01`（`s00-done` 不含 CLAUDE.md 的"执行者模式"，不要从它起）。S1 是纯移动，按 `ORCHESTRATION.md` 第 8 节串行单包。
- 派发脚本一律用 `.venv/Scripts/python.exe tools/orch/grok_worker.py …`。
