# HANDOFF

## 状态总览

| 会话 | 内容 | 状态 | tag | 门槛 |
|---|---|---|---|---|
| S0 | 编排准备（派发工具） | 完成 | s00-done；s00-done-r2（CLAUDE.md 写入"执行者模式"之后） | 冒烟包 s00-smoke 四项确认全部通过（没有 gates/s00.py） |
| S1 | Phase 0 冻结基线与仓库整理 | 完成 | s01-done；s01-done-r2（验收后的修订） | `gates/s01.py` 7/7；pytest 64 passed, 3 skipped |
| S2 | Phase 1a 契约、账本、三类健全 oracle | 完成 | s02-done；s02-done-r2（验收后的修订，S3 从这里起） | `gates/s02.py` 5/5；pytest 149 passed, 3 skipped |
| S3 | Phase 1b 其余三类 oracle 与 Index presence 移植 | 完成 | s03-done | S03 5/5；pytest 242 passed, 3 skipped；GATES PASS 3/3 |
| S4 | Phase 1c CVE 流水线（M1） | 完成 | s04-done | S04 9/9；pytest 275 passed, 3 skipped；GATES PASS 4/4 |
| S5 | Phase 2 共同语言 φ | 完成 | s05-done | S05 9/9；pytest 367 passed, 3 skipped；GATES PASS 5/5 |
| S6 | Phase 3a 理论 T 核心 | 完成 | s06-done；s06-done-r2（用户验收之后，S7 从这里起） | S06 12/12；pytest 514 passed, 3 skipped；GATES PASS 6/6 |
| S7 | Phase 3b 理论存储与接受规则 | 完成 | s07-done；s07-done-r2（用户验收之后，S8 从这里起） | S07 15/15；pytest 550 passed, 3 skipped；GATES PASS 7/7 |
| S8 | Phase 4 Hunter 与无 LLM 闭环（M2） | 完成 | s08-done；s08-done-r2（用户验收之后，S9 从这里起） | S08 11/11；pytest 613 passed, 3 skipped；GATES PASS 8/8 |
| S9 | Phase 5a LLM 网关、实现器、猜想者 | 完成 | s09-done；s09-done-r2（用户验收之后，S10 从这里起） | S09 12/12；pytest 692 passed, 3 skipped；GATES PASS 9/9 |
| S10 | Phase 5b 其余四个 LLM 角色（M3） | 完成 | s10-done；s10-done-r2（用户验收之后，S11 从这里起） | S10 12/12；pytest 774 passed, 3 skipped；GATES PASS 10/10 |
| S11 | Phase 6 评估管线（M4 冒烟） | 完成 | s11-done；s11-done-r2（用户验收之后，S12 从这里起） | S11 17/17；pytest 935 passed, 3 skipped；GATES PASS 11/11 |
| S12 | Phase 7 收尾 | 完成 | s12-done；s12-done-r2（用户验收之后，之后的工作从这里起） | S12 6/6；pytest 935 passed, 3 skipped；GATES PASS 12/12 |
| S13 | 正式实验设计 | 完成 | s13-done；s13-done-r2（用户验收之后，之后的工作从这里起） | S13 7/7；pytest 935 passed, 3 skipped；GATES PASS 13/13 |
| S14 | 服务器部署与双平台门槛 | 完成 | s14-done；s14-done-r2（编排者按用户指示自行验收，之后的工作从这里起） | S14 5/5；pytest 935 passed, 3 skipped（两个平台）；GATES PASS 14/14（两个平台） |
| S15 | 实验基础设施 | 完成 | s15-done；s15-done-r2（编排者照惯例自行验收）；s15-done-r3（用户同意 CLAUDE.md 的改动，之后的工作从这里起） | S15 11/11；pytest 1070 passed, 3 skipped（两个平台）；GATES PASS 15/15（本机） |
| S19 | E1 DuckDB 主对比 | **暂停**（预实验已跑完；用户 2026-10-20 指示服务器什么都不跑，等用户说；换模型已合并） | s19-deploy-1（预实验部署） | S19 6/6（换模型的门槛）；pytest 1086 passed, 3 skipped；GATES PASS 16/16（本机） |

以前各会话的交接全文在对应 tag 的本文件里（S0：`s00-done-r2`；S1：`s01-done-r2`）；其中仍然有效的未决问题已并入下面的清单。

## 暂停中：S19（E1 DuckDB 主对比，2026-10-20 开始）

用户的指示："开始S19，注意你只需要把实验跑起来，并告诉我结果会储存到哪里，以及进入实验terminal的tmux指令，不需要监控它是否跑完"。会话分支 `session/s19` 从 `s15-done-r3` 建立；预实验部署（`s19-deploy-1`）的代码与 `s15-done-r3` 相同，之后只有换模型（见下）改了代码。

- 交付：预实验配置 `docs/grids/e1_pilot_c{8,4,1}.json`、脚本 `docs/runs/e1_pilot.sh`、运行单 `docs/runs/E1.md`（正式配置等预实验之后写）。
- 部署 `s19-deploy-1` 到服务器，tmux 会话 `e1-pilot` 里依次跑 c8 → c4 → c1，约 15 小时；结果在服务器 `~/CoevoDB/framework/results/e1-pilot-c{8,4,1}/` 与同名 `.log`。密钥经 ssh 标准输入（`tmux load-buffer -`）粘进会话里的 `read -rs`，没有进命令行、文件与日志。
- 按用户的话，起跑后不监控。

预实验三次都跑完了（c8 10-19 13:22–15:22 UTC，c4 15:24–19:24，c1 19:26 至 10-20 03:26），全部格 `done`。

### 用户的决定（2026-10-20，PLAN §9 补充一条）

用户先说"当前实验太繁杂了，我的tokens不够用。现在先去掉各种消融实验的实验，并且优先跑postgre sql的实验"，讨论之后定下：
1. `pure_llm` 先不跑；方法照原样保留（代码、`EXPERIMENT.md` §3.1 与 §9 的臂都不动），以后需要时用户再决定跑不跑。
2. E3、E4、E5、E6 保留，只是现在不跑（第一句"去掉消融"由这一条取代：E3 与 E5 里的消融都保留、暂缓）。
3. 服务器现在什么都不跑，要跑时用户会说。这一条暂时收回"Claude 照运行单直接起实验"的授权；部署同样等用户说。
4. 核实预实验有没有因为 API 欠费调用失败，说清哪些结果可用（见下）。
5. 暂不开始 PostgreSQL 的部署（S16）。以后恢复时 PG 优先（用户的第一句话）。

### 预实验的 LLM 调用核实（编排者在服务器上只读 `llm/calls.jsonl` 与 `progress.jsonl`）

| 预实验 | 格 | LLM 调用 | 结论 |
|---|---|---|---|
| c8 | `full` s9101、s9102 | 272、242 次，0 次失败 | 可用 |
| c8 | `pure-llm` s9101、s9102 | 323、328 次，0 次失败 | 可用 |
| c4 | `full` s9101、s9102 | 294、346 次，0 次失败 | 可用 |
| c4 | `pure-llm` s9101、s9102 | 322、326 次，0 次失败 | 可用 |
| c1 | `full` s9101 | 343 次，第 294–343 次（50 次）全部失败 | 只有前 113.3 分钟可用 |
| c1 | `pure-llm` s9101 | 11,922 次全部失败，0 条记录 | 不可用 |
| 三次 | `nollm` 5 格、`sqlancer` 5 格 | 不调用 API | 可用 |

- `rejected`（`full` 每格 31–53 次）是回复解析不过，与欠费无关。
- 欠费从 c1 `full` 的第 113.3 分钟开始，约 2026-10-19 21:19 UTC。从这里起每次调用都在 1 秒内失败，一直持续到 c1 `pure-llm` 结束（10-20 01:26 UTC）。c1 `full` 在欠费后又跑了 463 条记录（共 1355 条），这些记录里没有 LLM 参与；它的 5 个家族都在第 87 分钟之前找到。所以家族数与首次发现时间不受影响；执行数、每千次家族数、每家族调用与 token、理论终态、编辑数都混进了无 LLM 的尾段，不能用。
- 日志只记异常类名 `TransportError`，没有 HTTP 状态码，从日志本身分不出是欠费（402）还是网络中断。用户说是欠费。
- 报告：c8、c4 的 `report/` 全部可用；c1 的 `report/` 只有 `nollm`、`sqlancer` 两个臂的数可用。
- 失败之前整个预实验花了约 $15.2（每格 2 小时：`full` $1.31–1.83，`pure-llm` $1.87–1.90；按 `grid` 一节的高峰价，是上界）。
- 另一个现象，不是欠费：c4 `full` s9102 只有 263 条记录（同一臂 s9101 有 1243 条）。它 120 分钟里有 115 分钟在等 LLM 回复；`full` 每格等 LLM 的时间在 85–115 分钟之间，主循环的吞吐受 LLM 延迟限制。

### 换模型：GLM 5.3 Flash（OpenRouter），工作包 `s19-glm`（已合并）

用户 2026-10-20 决定 LLM 角色改用 OpenRouter 的 `z-ai/glm-5.3-flash`，只用提供商 `open-inference/fp4`，不回退，开推理；密钥仍放在 `DEEPSEEK_API_KEY`（用户已把 OpenRouter 的密钥给编排者，写进了本机用户级环境变量）。做法见 DECISIONS 当天三条：加一档 `glm-flash`，默认两档不变，配置放新模块 `roles/providers.py`，照旧用 httpx。门槛 `gates/s19.py` 有六组，派发前写好（12f4f1b）；说明在 `.orch/briefs/s19-glm.md`；从 `session/s19` 派给 codex。
- codex 一次交付（342727f），改 9 个文件，与说明逐条对上；`roles/constants.py`、harness、DeepSeek 价格表没碰。合并 5828c1d，归档 cc26838（`docs/orch/s19/`），worktree 已清理。
- 用法：主循环与 `pure_llm` 传 `--llm-tier glm-flash`，网格的臂写 `"tier": "glm-flash"`。不传时缓存键、`calls.jsonl`、`config.json`、manifest 与以前逐字节相同；用了新档，运行 manifest 的 `llm` 一节多一个 `endpoint`（模型、`base_url`、请求体附加字段）。价格表 `metrics/data/prices_openrouter.json`。
- 长跑重跑（LLM 全关，DuckDB 1.5.5，种子 0，七类 oracle，180 分钟）：以 `budget_minutes` 结束，9400 条，0 条 harness_error，11 个家族。去掉 `elapsed_s` 后前 7143 行与 S15 代码的长跑逐行相同；第 7144 行是 plan variant 用例的第 1 档重跑不稳定（这次判 `invalid / unstable_rerun`，S15 那次判 `pass`），之后路径不同，与 S8 以来同一类不稳定。S15 代码的长跑挪到 `results/s08/longrun-s15code`（不入库）。重钉 4d0c74b；S8 的四个产物组与 S11 `ciao` 通过。
- 最终复跑（在 `session/s19` 主检出区，在 `framework/` 下，去掉密钥）：pytest 1086 passed, 3 skipped（比 S15 多 16 个，都是本包的离线测试）；GATES PASS 16/16。
- 还没做：用新密钥经网关做一次真实调用冒烟（本机、1–2 次调用、不到 1 美分），等用户同意。要看的是回复能不能解析、推理会不会把 `max_tokens` 用完、实际 token 量与延迟。编排者进程里的 `DEEPSEEK_API_KEY` 还是旧值，冒烟要从用户级环境变量取。
- 按 OpenRouter 的价格，Open Inference 的输出是 $0.16 每百万 token（deepseek-flash 是 $1.2）。拿预实验的 token 量估算，`full` 每格 24 小时约 $2–3。实际 token 量要等新模型的冒烟才知道。

### 额度不足与报错的提醒（pushplus），工作包 `s19-notify`（进行中）

用户 2026-10-21："添加额度不足、报错等的提醒：使用pushplus的一对一消息功能"。token 已写进本机用户级环境变量 `PUSHPLUS_TOKEN`（编排者进程里还没有，要从用户级环境变量取）。做法见 DECISIONS 当天两条：独立的看守进程 `surprise.notify.watch` 只读网格结果目录，按事件推送；`roles/gateway.py` 失败调用的 `reason` 记下 HTTP 状态码。不改 `experiments/`，不用重钉长跑。门槛 `gates/s19.py` 加五组（`pushplus`、`reason`、`watch`、`balance`、`cli`），派发前写好；说明在 `.orch/briefs/s19-notify.md`；从 `session/s19` 派给 codex。
- 合并后：在主检出区跑测试与全部门槛；运行手册（SERVER.md 的密钥一节、E1 的运行脚本）加上 `PUSHPLUS_TOKEN` 进 tmux 会话、与网格一起起看守；经用户同意后发一条真实的测试推送。
- 想让余额提前预警，要在 OpenRouter 给这把 key 设额度上限（普通 key 查不到账户余额）；不设上限时，欠费只能靠调用失败（402）发现。

下一步（等用户说）：
- 恢复之前先换好 OpenRouter 的密钥并确认余额（LLM 臂改用 `glm-flash` 档）。恢复时按用户的第一句话 PG 优先：S16 → E2。回放检查要用 E1 的账本，E1 正式还没跑，到时候改用预实验 c8、c4 的账本，要先问用户。
- E1 正式运行：配置 `docs/grids/e1.json` 还没写，四个臂里 `pure_llm` 暂不跑，LLM 臂用 `glm-flash` 档。并发度还没定。吞吐与标签稳定性已经比过（见未决问题的"S19 新发现"第 3、4 条）：c8 的吞吐够用，标签分叉与并发高低不单调；c1 的 LLM 臂虽然只能用前 113 分钟，也不必为此重跑 c1。想分清标签分叉是不是负载造成的，可以在同一并发下把 `nollm` 同种子重复跑一次（可选，要用户定）。换了模型之后，LLM 臂的延迟会变，`full` 的吞吐要重新看。
- 预实验结果都在服务器上，没有拷回；本次核实只读，没有改动结果目录。

## 最近完成会话：S15（2026-10-19）

用户的指示："S14验收后执行/clear，然后开始做S15，S15做完后继续做S19 E1"。会话分支 `session/s15` 从 `s14-done-r2` 建立；起点复跑 935 passed, 3 skipped，GATES PASS 14/14。门槛 `gates/s15.py`（表在 `s15_cases.py`，数据在 `s15_data/`）十一组，派发前写好。中途 grok 余额用完，用户把执行者换成 codex（见下）。五个包全部合并；长跑重跑、重钉，服务器部署与 Linux 上的复核由编排者做。收尾合并回 main，tag `s15-done`。

编排者已做的环境准备（不入库，在仓库根 `.orch/` 下）：Temurin JDK 21.0.12.1+1（与服务器同版本，SHA256 已核对）、Maven 3.9.16（SHA512 已核对）、SQLancer `ab328b75`（2026-10-14 的 main）构建成 `.orch/sqlancer/`，打了一个补丁（`docs/sqlancer/log-each-select.patch`：原代码只要关掉 `--log-each-select` 就断言失败，不关的话 `-cur.log` 每格 24 小时会有几十 GB），自带的 DuckDB JDBC 1.3.0.0 换成 `override/duckdb_jdbc-1.5.5.0.jar`（SHA1 已核对；日志头确认 `Database version: v1.5.5`）。SQLancer 支持 DataFusion，但走它自己的 Flight SQL 服务端，钉在 DataFusion 40.0.0，要测 54.0.0 得先移植那个 Rust 服务端（留给 S17 决定）。

拆包（文件归属不重叠）：

| 包 | 内容 | 允许路径 | 批次 |
|---|---|---|---|
| `s15-llm` | LLM 调用不设上限（`"unlimited"`）、整次运行换档（`--llm-tier`）、Windows 上 CTRL_BREAK 转成中断 | `roles/gateway.py`、`roles/constants.py`、`roles/runtime.py`、`experiments/loop.py`、`baselines/pure_llm.py`、测试 | 1 |
| `s15-grid` | 并发、块调度、每格 CPU 与引擎线程、墙钟强杀、新配置键、SQLancer 运行臂的命令、价格表数据文件 | `experiments/grid.py`、`metrics/data/prices_deepseek.json`、测试 | 1 |
| `s15-rundata` | `RunData` 与 `run_metrics`、离线去重改成流式读 | `metrics/rundata.py`、`metrics/rq.py`、`metrics/dedup.py`、测试 | 1 |
| `s15-sqlancer` | 真正运行 SQLancer 的驱动：日志转 `SqlCase`、同一套 oracle 与 CVE 评判、报告接入 | `baselines/sqlancer_run.py`（新）、`metrics/report.py`、测试与测试数据 | 2（在 grid 合并后） |
| `s15-archive` | 归档命令：打包、校验、精简 | `experiments/archive.py`（新）、测试 | 2 |

全部合并后：按 S8 验收的办法重跑 3 小时长跑、重钉；补 SERVER.md 的并行、归档与 SQLancer 三节；服务器部署（SQLancer 拷过去）。

**阻塞（2026-10-19 08:33）：grok 账户余额用完。** 第一批三个包派发约 25 分钟后，`s15-rundata` 收到 `API error (status 402 Payment Required): Grok Build usage balance exhausted` 退出（未提交，worktree 里留着 5 个文件的改动）；另外两个包在下一次调用模型时也同样退出。已做完、不依赖 grok 的：门槛 s15、SQLancer 的构建与补丁、SQLancer 已拷到服务器并冒烟通过（`.orch/sqlancer`，DuckDB 1.5.5，约 700 条查询每秒）、SERVER.md 三节的草稿（现在在 `.orch/s15/SERVER.md.draft`，不入库；归档模块合并后才能提交，因为 s14 的 `docs` 组会对手册里的每条命令跑 `--help`）。

**换成 codex（2026-10-19 15:30，用户决定）：** 用户指示"暂时把grok的角色换为codex"，启动命令 `codex -m gpt-6.1-sol -c 'model_reasoning_effort="high"' --yolo`。`tools/orch/grok_worker.py` 加了 codex 后端（默认执行者现在是 codex）和 `handover` 命令；拦截改用 worktree 里的 execpolicy 规则；做法与实测见 ORCHESTRATION §11 与 DECISIONS 当天各条。冒烟包 `s15-codex-smoke` 跑通后已清理。第一批三个包用 `gw handover <包号>` 交给 codex，在原 worktree 上接着做（grok 留下的未提交改动保留）；之后的包（`s15-sqlancer`、`s15-archive`）用 codex 派发。

### 交付与门槛

- **LLM 不设上限与换档**（`s15-llm`）：网关 `max_calls` 接受 `"unlimited"`（模块常数 `roles.gateway.UNLIMITED`，不进 `roles/constants.py`），环境变量 `SURPRISE_LLM_MAX_CALLS` 照旧压得住它；`Gateway(tier=...)` 让整次运行的每一次调用都改用一档（缓存键、`Reply`、`calls.jsonl` 都记实际的档与模型）。主循环与纯 LLM 基线加 `--llm-max-calls unlimited`、`--llm-tier {fast,strong}`；`main()` 里把 Windows 的 `SIGBREAK`、POSIX 的 `SIGTERM` 转成 `KeyboardInterrupt`（报告 `interrupted`，返回 130）。不传新参数时缓存键、`calls.jsonl`、`config.json`、manifest 都不变。
- **网格**（`s15-grid`）：顶层新键 `concurrency`、`cpus_per_cell`、`engine_threads`、`kill_grace_minutes`；块调度（重复 → 种子 → 引擎集合为一块）、单线程轮询、槽位；Linux 上按槽位绑 CPU（`sched_setaffinity`），引擎线程数经 `SLURM_CPUS_ON_NODE` 交给 DuckDB；分钟预算的格到"预算 + 宽限"先中断、120 秒后杀整棵进程树，记 `done`、`killed: true`、不重跑；臂的 `tier`、`max_calls: "unlimited"`；`sqlancer` 臂的运行模式（`"run": true`）。价格表 `metrics/data/prices_deepseek.json`（官方价格页 2026-10-19）。
- **流式读**（`s15-rundata`）：`RunData.open` 只数记录，`iter_records()` 用只读游标逐条读；`run_metrics` 一遍扫描、只留指标要用的字段；大于 32 MiB 的记录在指标扫描里把 `label.detail` 换成 `{}`（S10 代码的长跑里有一条 483 MB 的 detail；指标与 φ 都不读它）。9500 条的长跑输出与改造前逐字节相同，峰值 357 MB（改造前 8600 条 3.3 GB），账本加倍只多 42 MB。`dedup` 也改成流式。
- **SQLancer 驱动**（`s15-sqlancer`，`baselines/sqlancer_run.py`）：在格目录里起 SQLancer（`ab328b75` 加补丁，DuckDB JDBC 1.5.5.0），每两秒收一次缺陷日志，分类（`mismatch` / `unexpected_error` / `tool_error`），能拆成"`SELECT <列> FROM <表或连接>` + 谓词"的转成 `SqlCase` 交给同一套 oracle 与 CVE 评判；SQLancer 说它是缺陷不算数。`--replay-logs` 不起 java。报告管线把运行模式的 `sqlancer` 臂当普通有格的臂。
- **归档**（`s15-archive`，`experiments/archive.py`）：`pack`（tar.gz 加每个文件的 SHA256 清单）、`verify [--against]`、`prune`（先完整核对，对不上就什么都不删；只留 `grid.json`、`report/` 与每格的 `cell.json`、`config.json`、`report.json`、`error.txt`）。
- **SERVER.md**：§5.7 并行网格、§5.8 归档（E1 的原始目录先不精简）、§8 SQLancer（版本、补丁、构建、部署、驱动、DataFusion）。
- **派发工具**：codex 后端与 `handover`（见上，ORCHESTRATION §11）。
- **门槛 s15** 十一组：`config`、`parallel`、`kill`、`interrupt`、`stream`、`llm`、`sqlancer`、`prices`、`archive`、`docs`、`scope`。派发后编排者改过三处：`scope` 允许 `tools/orch/`（换执行者）；补交被 `*.log` 挡住的四份 SQLancer 样例（`.gitignore` 加例外）；`interrupt` 组的错误消息在条件成立时也会阻塞读 stderr，改成写文件（s15-sqlancer 的执行者发现）。

### 拆包清单与结论（全部已合并）

| 包 | 轮数 | 合并 | 审查 |
|---|---|---|---|
| s15-llm | grok 做到一半余额用完；codex 交接后一次完成 | 81b80d6 | 五个文件与说明逐条对上；codex 输入 209 万 token（96% 缓存）、输出 1.2 万 |
| s15-rundata | 同上 | 7e54b0a | 手写的 detail 定位器逐行核过；`stream` 组在 worktree 里独立复跑通过；codex 输入 329 万、输出 2.5 万 |
| s15-grid | 同上 | f8eafb3 | 调度与强杀逐条对上；另加的"监督期间忽略 `SIGBREAK`"（防止发给已退出的子进程时被广播回网格）接受；codex 输入 474 万、输出 2.0 万 |
| s15-archive | 首轮通过 | 9db8fab | `prune` 的保留规则与删除次序逐条核过；codex 输入 153 万、输出 1.9 万 |
| s15-sqlancer | 第一次派发因样例缺失停下（编排者的错，作废重派）；返工 1 轮：执行者把"不改测试"套到自己新写的测试上停下，意见澄清后完成 | 21dcb2c | 三处宽泛 `except` 都是记下后再抛或按约定返回 1；codex 两轮输入 953 万、输出 4.6 万 |

- 说明、报告、审查包与返工意见归档在 `docs/orch/s15/`。codex 合计输入约 2158 万 token（97% 命中缓存）、输出约 12.6 万；codex 不报美元。grok 第一批三个包在余额用完之前的花费见各自日志。
- 五个审查包的门槛复跑都有 S08、S11 失败：worktree 里没有 `framework/results/s08/`（S12 起已知），S8 的 `longrun` 另绑着 `experiments/` 的代码摘要；合并后在主检出区重钉、通过。

### 实机运行的数字

**长跑**（`results/s08/longrun`，角色全关、DuckDB 1.5.5、种子 0、七类 oracle、180 分钟，五个包合并之后、s15-sqlancer 合并之前起跑：S8 的代码摘要只看 `hunter/`、`diagnoser/`、`experiments/`，s15-sqlancer 不碰）

| | S11 代码 | S15 代码 |
|---|---|---|
| 实验 | 8600 | 9236 |
| fail / pass / invalid | 90 / 4117 / 4393 | 93 / 4318 / 4825 |
| 车道（探索 / 泛化 / 细化） | 8511 / 55 / 34 | 9145 / 53 / 38 |
| 假设 / 家族 | 27 / 13 | 26 / 11 |
| 重复率（旧系统 0.818） | 0.462 | 0.545 |
| 窗口与齿 | 86 个窗口 | 92 个窗口，齿在 3、9、17、40、87 |
| CIAO（代数；对角线 / 新理论看旧批 / 旧理论看新批，比特） | 88 代；0.056 / 0.029 / 0.211 | 93 代；0.014 / 0.013 / 0.094 |

- 以 `budget_minutes` 结束，0 条 harness_error。去掉 `elapsed_s` 后前 2936 行与 S11 代码的长跑逐行相同；第 2937 行仍是 S8 以来那条第 1 档重跑不稳定的 plan variant 用例（这次判 `invalid / unstable_rerun`，S11 那次判 `pass`），之后路径不同。S11 代码的长跑挪到 `results/s08/longrun-s11code`（不入库）。重钉 ab37bc6。

**SQLancer 在 DuckDB 1.5.5 上 10 分钟**（门槛 `sqlancer` 组）：本机 601,510 条查询、8 份日志；服务器 501,698 条、7 份。全是 SQLancer 自己的问题或预期外报错，没有一份能转换成用例，0 个家族。门槛的"产出家族键"靠编排者写的 NoREC 样例（判 `fail`，家族键 `fix|duckdb|deliminator,filter_pushdown`，与主循环相同）。

**服务器**（`s15-deploy-1` = 6c44b3e，五个包与门槛修复都在内，tmux 会话 `s15-check`，结果在 `~/s15-check/`）：pytest 1070 passed, 3 skipped；S15 九组通过，其中 `parallel`（含 Linux 上的 CPU 绑定与引擎线程数）、`kill`（POSIX 的中断与 `killpg`）、`interrupt` 是本机测不到的；`stream` 失败（`results/s08/longrun-s10code` 只在 Windows 上）、`docs` 失败（那时 HANDOFF 还没有 S15 一行）。只做了检查，没有入库证据：S15 的门槛不读服务器记录。

### 与计划的偏差

- 执行者从 grok 换成 codex（用户的决定，PLAN 没有写执行者是谁；ORCHESTRATION §11）。第一批三个包是交接的，不是重做。
- 门槛 s15 在派发后改了三处（见"交付与门槛"最后一条），都不是放宽：一处是扩范围（`tools/orch/`），两处是门槛自己的错（数据没进库、读 stderr 阻塞）。
- 长跑在 s15-sqlancer 合并之前起跑（理由见上表头）。
- 服务器上只跑了 pytest 与 S15 门槛，没有像 S14 那样入库一份全量记录。
- SESSIONS 写"核实 SQLancer 是否支持 DataFusion"：支持，但钉在 DataFusion 40.0.0（SERVER.md §8），留给 S17 决定。

### 最终复跑

全部合并、长跑重钉之后，在 `session/s15` 主检出区，在 `framework/` 下，去掉密钥：

| 平台 | 命令 | 结果 |
|---|---|---|
| 本机 | `../.venv/Scripts/python.exe -m pytest -q testing tests` | 1070 passed, 3 skipped，退出码 0（起点 935，新增 135，skip 未增加） |
| 本机 | `../.venv/Scripts/python.exe -m surprise.gates.all` | S01 7/7、S02 5/5、S03 5/5、S04 9/9、S05 9/9、S06 12/12、S07 15/15、S08 11/11、S09 12/12、S10 12/12、S11 17/17、S12 6/6、S13 7/7、S14 5/5、S15 11/11；GATES: PASS (15/15 passed)，退出码 0。S15 `sqlancer` 组这次 711,107 条查询、9 份日志、0 条转成用例；`stream` 峰值 357 MB，加倍多 44 MB |
| 服务器（`s15-deploy-1`） | `../.venv/bin/python -m pytest -q testing tests`；`-m surprise.gates.s15` | 1070 passed, 3 skipped；S15 9/11（`stream`、`docs` 的原因见上） |

### 验收（2026-10-19，编排者照惯例自行定下，用户可以推翻）

1. 派发工具的 codex 后端与 `handover`、ORCHESTRATION §11 照现在的样子接受（用户的决定；冒烟包与五个包都跑通）。
2. 接受 `s15-rundata` 在指标扫描里跳过大于 32 MiB 记录的 `label.detail`（指标与 φ 都不读它，输出逐字节不变）。
3. 接受 SQLancer 臂在 DuckDB 1.5.5 上 10 分钟 0 个家族的现状：驱动的评判路径由 NoREC 样例证明，E1 报告里照实写。
4. 接受长跑重钉（9236 条，第 2937 行起的分叉是已知的不稳定用例）。
5. `CLAUDE.md` 的两处改动：**用户同意**（2026-10-19，"第五项同意改动"），已写入，tag `s15-done-r3`。
   - S14 的改动稿（`docs/orch/s14/claude_md_proposal.md`）照稿写入，按现状调了三处：执行者写成"grok 或 codex"；ORCHESTRATION 的服务器一节编为 §12（§11 已是 codex）；ssh、scp、rsync、sftp 同时进 grok 的 `DENY_BASH` 与 codex 的 `CODEX_FORBIDDEN`（`codex execpolicy check` 核过：这四个被拒，`git status`、pytest 照常）。
   - 执行者模式"不改测试"那条补上："这一条管基线里已有的测试与门槛……本包新写的测试照常修改，只要改完仍检查说明要求的东西"。说明模板 `docs/orch/BRIEF_TEMPLATE.md` 里同一句同样补上（执行者那次引用的就是说明里的原话），也加了"不登录服务器"。
   - 顺带：CLAUDE.md 的编排命令列表补上 `handover`。

S15 到此结束：`s15-done-r2` 只比 `s15-done` 多这段验收记录，`s15-done-r3` 再多上面第 5 项的改动。S19 从 `s15-done-r3` 起。

### 下一会话的起点：S19（E1 DuckDB 主对比）

- 起点 `s15-done-r3`。用户的指示是 S15 之后做 S19 E1；按 SESSIONS，S16（PG 目标）在 E1 于服务器上跑的那几天里在本机做。
- 范围见 SESSIONS 的 S19 一节与 `EXPERIMENT.md` §9：先在本机写 E1 的网格配置与运行单，部署 tag 到服务器；先跑预实验（2 小时，种子 9101、9102，并发 1、4、8 比吞吐与标签稳定性），据此定并发度写进协议，再起正式的 20 格。
- 服务器专用，部署与起实验不必先问（用户的决定）；密钥只经 ssh 标准输入进 tmux 会话的环境。
- 服务器上现在检出的是 `s15-deploy-1`（与 `s15-done` 只差收尾的门槛表、HANDOFF 与 DECISIONS）；SQLancer 与 JDK 已在 `~/CoevoDB/.orch/`。tmux 里有用户的 `s14-smoke` 与编排者的 `s15-check` 两个会话，都已空闲。
- 执行者现在是 codex（ORCHESTRATION §11）；用户要换回 grok 时 `--executor grok`。

## 最近完成会话：S14（2026-10-19）

Claude Code 担任编排者。用户的指示是"当前服务器3090空闲，开始搭建环境"（即开 S14，并确认了服务器空闲）；重新记录之前又问过一次，用户答"空闲，开始吧"。会话分支 `session/s14` 从 `s13-done-r2` 建立，收尾合并回 main，tag `s14-done`。派发了一个 grok 包（`s14-posix-die`）。服务器上只做了搭环境与部署；冒烟网格由用户自己跑。

### 交付与门槛

- **服务器环境**（全在 `~/CoevoDB` 下，没有 sudo，机器是多人共用的）：
  - 代码：裸仓库 `~/coevodb.git`，工作目录 `~/CoevoDB` 只检出 tag。
  - Python：micromamba + conda-forge 的 Python 3.13.9 作底座，uv 建四个 venv，包版本逐个钉成 Windows 上对应 venv 实际看到的版本（含间接依赖）。
  - SQLite：按 Windows 那份库的编译选项自编 3.51.0，source id 与 Windows 逐字相同。
  - PG 16.15：自编，ICU 67.1，设置与 Windows 逐项相同；认证用 scram + `~/.pgpass`；crontab `@reboot` 自启。
  - 另有 JDK 21、`.src/` 两份检出、`framework/results/s08/` 四个钉住的目录。
  - 细节与理由见新文件 `framework/surprise/docs/SERVER.md` §1–§4；§5 是用户运行手册，§7 是门槛读取的版本清单。
- **`framework/surprise/docs/grids/s14_smoke.json`**（新）：一个不带 LLM 的 `surprise` 臂加一个读汇总的 `sqlancer` 臂，种子 7，1 分钟。
- **包 `s14-posix-die`**（grok，首轮通过）：S4 测试夹具 `die()` 在 POSIX 上改用 `os._exit(code)`。
- **编排者改门槛 s03**：venv 解释器与污染检查不再写死 Windows 布局。
- **门槛 `gates/s14.py`**（表在 `s14_cases.py`）五组：
  - `env`：现场探针对照 SERVER.md §7（Python、SQLite 版本、source id 与编译选项、四个 venv 的全部包、PG 设置与 ICU 排序版本、两份源码的 commit）。在服务器上另查 JDK、PG 没有 trust 规则、旧代码路径的覆盖、工作目录是干净的 tag 检出。在本机另查入库的服务器探针，并对照两边的 SQLite 编译选项（只差平台前缀）与 PG 设置。
  - `linux`：入库的服务器记录（`--record` 写出）对应的提交与本机工作树代码相同；pytest 退出码 0、没有失败、skip ≤ 3；全部门槛 PASS。
  - `smoke`：用户的冒烟网格（`--ingest-smoke` 导入）配置与 §5.6 相同，`done 1/1`，墙钟在 55–900 秒；manifest 是 Linux、钉住的引擎与旧引擎、PG 16.15、冻结的 harness 哈希、同一份代码（门槛自身除外，门槛核实网格不导入它）；报告各节齐全。
  - `docs`：SERVER.md 各节次序；运行手册里的每条 `$PY -m` 命令存在且 `--help` 退出码 0；冒烟配置离线、1 分钟、一个种子。
  - `scope`：自 `s13-done-r2` 起只改了 docs、门槛 s03 与 s14、证据目录和那个测试夹具；harness 与冻结清单没动。
  - `linux`、`smoke` 两组在服务器上显示 N/A、不计数。
  - 打出 `s14-done` 之后，`linux`、`smoke` 改为对照 tag：比较记录的提交与 tag 的代码，门槛清单与版本表取 tag 里的，证据自 tag 起不许改；`env` 组里入库的服务器探针也对照 tag 里的版本表。所以后面的会话改代码、加门槛，S14 照样是绿的。`env` 组的现场探针（本机，或在服务器上跑时的服务器）仍对照当前的 SERVER.md §7。
- **证据** `gates/s14_evidence/`：服务器记录（`linux_env.json`、`linux_runs.json`、pytest 与门槛的日志）与 `smoke/`。

最终复跑：

| 平台 | 命令 | 结果 |
|---|---|---|
| 服务器（`s14-deploy-3`，7f35b42） | `python -m surprise.gates.s14 --record` | env 通过；pytest 935 passed, 3 skipped，退出码 0；S01 7/7、S02 5/5、S03 5/5、S04 9/9、S05 9/9、S06 12/12、S07 15/15、S08 11/11、S09 12/12、S10 12/12、S11 17/17、S12 6/6、S13 7/7、S14 3/3（另两组在服务器上 N/A）；GATES: PASS (14/14 passed) |
| 本机（`session/s14`，代码同 7f35b42） | `../.venv/Scripts/python.exe -m pytest -q testing tests` | 935 passed, 3 skipped，退出码 0（与起点相同，skip 未增加） |
| 本机 | `../.venv/Scripts/python.exe -m surprise.gates.all` | S01–S13 全过（组数与服务器相同），S14 5/5；GATES: PASS (14/14 passed)，退出码 0 |
| 服务器（用户，`s14-deploy-1`） | SERVER.md §5.6 冒烟网格 | `nollm/s7-r0` done，60.7 秒，78 条实验（37 pass、40 invalid、1 fail），1 个新族（Version differential）；第一次在 3 秒时被 Ctrl-C 打断，续跑时网格把那一格改名 `s7-r0.stale-1` 保留后重跑 |

S8 钉住的 Windows 长跑产物在服务器上直接核对通过（S08 11/11），不需要另钉一份 Linux 的。

### 平台差异

SERVER.md §6 共四条，都已处理，没有放宽断言：
1. 旧代码的默认路径指向这台机器上另一账号 `user` 的 `/home/user/...`：目录存在但不可读，`exists()` 抛 `PermissionError`。用环境变量把五个路径指到不存在的位置（`.orch/server.env`，`~/.bashrc` 第一行读入），旧代码不动。
2. S4 测试夹具 `die()` 在 POSIX 上给自己发 SIGKILL，退出码恒为 -9。由包 `s14-posix-die` 修。
3. 门槛 s03 写死了 Windows 的 venv 布局。
4. 门槛 s14 自己：冒烟 `grid.json` 里 sqlancer 汇总存成绝对路径。

### 与计划的偏差

- SESSIONS 写"用 uv 装 Python 3.13.9"。实际用 conda-forge 的 Python 3.13.9 作底座：uv 的 Python 静态链接 SQLite 3.50.4，换不了；venv 仍由 uv 建，与 Windows 的结构（anaconda 底座 + uv venv）一致。
- SQLite 3.51.0 是自编的：conda-forge 的 3.51.0 打过补丁，编译选项也不同，会改变 SQLite 参照的结果（例如 `sqrt(4)`）。
- 服务器上 PG 用 scram + `~/.pgpass`，不用 trust：机器多人共用。DSN 不变，harness 与门槛都不用改。
- 旧代码路径在服务器上靠环境变量覆盖（见平台差异第 1 条）。
- Maven、SQLancer 本身与 Windows 本机的 JDK 留给 S15。
- 门槛 s14 在导入冒烟后又改了两次（跨平台路径；打 tag 后对照 tag），每次都重新部署、重新记录（`s14-deploy-2`、`s14-deploy-3`），之前都问过用户服务器是否空闲。冒烟网格是在 `s14-deploy-1` 上跑的，与最终代码只差门槛与文档。
- 没有写 `CLAUDE.md`、`ORCHESTRATION.md` 与 `tools/orch/grok_worker.py`：改动稿在收尾消息里给用户看，同意后在 `s14-done-r2` 写入。

### 验收（2026-10-19，编排者按用户指示自行定下）

用户的指示是"S14验收后执行/clear，然后开始做S15，S15做完后继续做S19 E1"，人当时去睡了。照以往惯例，收尾的人工检查项由编排者定下，用户可以推翻：
1. `SERVER.md` §5 运行手册照现在的样子接受：用户已照 §5.6 跑通冒烟；续跑会覆盖日志的问题已改成 `tee -a`。
2. 接受 conda-forge 的 Python 底座与自编的 SQLite 3.51.0（偏离 SESSIONS 写的"用 uv 装 Python"）：理由见 SERVER.md §2，是让 SQLite 参照与 Windows 逐字相同的唯一办法。
3. 接受服务器上 PG 用 scram + `~/.pgpass`：机器多人共用，DSN 不变。
4. 接受门槛 s14 在打 tag 后对照 `s14-done`（本节"交付与门槛"最后一条）。
5. **没有定**：`CLAUDE.md`、`ORCHESTRATION.md` 与 `tools/orch/grok_worker.py` 的改动（稿子在 `orch/s14/claude_md_proposal.md`）。按规定要用户同意，建议照稿写入。

`CLAUDE.md` 的改动稿以外，S14 到此结束，tag `s14-done-r2`（只比 `s14-done` 多这段验收记录）。S15 从 `s14-done-r2` 起。

### 下一会话的起点：S15

- 起点 `s14-done-r2`。范围见 SESSIONS 的 S15 一节。
- S15 改了 `experiments/` 等目录之后，要按 S8 验收的办法重跑长跑、重钉。要在服务器上验证新代码时：先问用户是否空闲，部署新 tag，跑 `python -m surprise.gates.s14 --record <目录>`（或 S15 自己的记录命令），拷回后在 S15 的门槛里核对；S14 的证据不要动（打 tag 后它只对照 `s14-done`）。
- 改了环境（例如给 venv 加包）就要同时改 SERVER.md §7，两个平台都装上，否则在那个平台上跑 S14 的 `env` 组会失败。
- 服务器上的 SQLancer 需要 Maven；SQLancer 的 commit 与 JDK 版本在 S15 定。
- 开工检查：本机 `pg_ctl status`。
- **用户的新决定（S14 期间，写进 PLAN §9 补充一条与 EXPERIMENT §7）**：服务器专用，部署不必先问是否空闲；实验也由 Claude 在服务器上起，次序仍按 SESSIONS（E1 在 S15 之后的 S19，预实验在前）；密钥沿用现有的，只走环境变量（本机用户环境里有 `DEEPSEEK_API_KEY`；传到服务器时经 ssh 标准输入进 tmux 会话的环境，不进命令行、文件与日志）。
- **用户的指示**："S14验收后执行/clear，然后开始做S15，S15做完后继续做S19 E1"。S14、S15 的验收项照惯例由编排者自己定、打 `-r2`；`CLAUDE.md` 与 `ORCHESTRATION.md` 的改动仍等用户看过再写（见下面未决问题）。

## 最近完成会话：S13（2026-10-19）

Claude Code 担任编排者。S13 只写文档与门槛：没有派发 grok 包，没有真实调用，也没有运行实验。用户的指示是"开始做 S13"。设计在此前与用户的讨论里逐项定下，讨论稿在 Claude Doc（https://claude.ai/code/artifact/b1b40efa-a437-4839-aa25-a4e3a6845e63）。全部用户决定记在 `PLAN.md` §9 与 DECISIONS 的 S13 各条。会话分支 `session/s13` 从 `s12-done-r2` 建立。收尾合并回 main，tag `s13-done`。用户验收后另打 `s13-done-r2`（只多了验收记录，代码与门槛相同），之后的工作从 `s13-done-r2` 起。

**用户验收（2026-10-19）：** 用户的答复是"没有问题"。收尾消息里的五项人工检查都按编排者的说法定下，逐项见 DECISIONS 的 S13 验收一条：`EXPERIMENT.md` 的消融表与里程碑表、`PLAN.md` §9、`SESSIONS.md` 的 S14–S18 照现在的样子接受；`CLAUDE.md` 与 `ORCHESTRATION.md` 按建议在 S14 搭完服务器时一起改（届时把具体改动给用户看过再写入）。

起点：第一次复跑 13 条测试失败。原因是 PG 参照服务器没在运行（`pg_ctl status` 退出码 3，测试报连接被拒），按 S3 一节的命令启动后（没有重新 initdb）重跑：pytest 935 passed, 3 skipped；GATES PASS 12/12（与 S12 收尾相同）。

### 交付与门槛

- `framework/surprise/docs/EXPERIMENT.md`（新）：正式实验协议。内容是引擎与版本、臂与消融（A1–A14）、时长与种子、统计、调度与资源、里程碑 E1–E7 与顺序、服务器分工、执行规则（协议冻结、回放检查、缺陷上报），末尾是门槛读取的机读清单（JSON）。
- `PLAN.md`：加 §9"正式实验的决定"；与之冲突的六处旧条目旁注明"见 §9"，原文不删。
- `SESSIONS.md`：标题改为"实施会话"，开头加一段说明 S13 起的阶段；新增 S13–S25 十三节。
- 门槛 `gates/s13.py`（表在 `s13_cases.py`）七组，只核对文档、不跑引擎：
  - `scope`：S13 只改了 docs 与门槛自己的两个文件；打了 `s13-done` 之后改为比较两个 tag，后面的会话改代码不影响这一组。
  - `sections`：EXPERIMENT.md 的小节齐全、次序正确，并写明格数合计。
  - `arms`：每个臂的每个配置键要么网格现在就认，要么写明哪个会话补；角色、`hunter`、`freeze` 取值合法；冻结臂只开允许的角色；A6–A10、A13 恰好去掉所说的角色。
  - `engines`：每个引擎要么现在就是目标或参照，要么写明哪个会话接入；每个里程碑的前置包含它的引擎与臂需要的会话；纯 LLM 与 SQLancer 每格只用一个引擎。
  - `cells`：按清单重算的格数与声明一致：215 个 24 小时格加 45 个 1 小时格。
  - `seeds`：正式种子 1001–1005 与预实验种子 9101、9102 互不重叠，也没在 `s12-done-r2` 的门槛与测试里出现过。
  - `sessions`：SESSIONS 有 S13–S25，里程碑的前置与运行会话都有对应一节且次序正确；PLAN 有 §9；本文件状态表有 S13 一行。

最终复跑（在 `session/s13` 主检出区，在 `framework/` 下，去掉密钥）：

| 命令 | 结果 |
|---|---|
| `../.venv/Scripts/python.exe -m pytest -q testing tests` | 935 passed, 3 skipped，退出码 0（与起点相同，skip 未增加） |
| `../.venv/Scripts/python.exe -m surprise.gates.all` | S01 7/7、S02 5/5、S03 5/5、S04 9/9、S05 9/9、S06 12/12、S07 15/15、S08 11/11、S09 12/12、S10 12/12、S11 17/17、S12 6/6、S13 7/7；GATES: PASS (13/13 passed)，退出码 0 |

### 读代码核实的现状（S14 起要用）

| 事实 | 出处 | 影响 |
|---|---|---|
| harness 只认 `duckdb`、`datafusion` 为目标；`sqlite`、`postgres` 只是 Cross-DBMS 参照 | `surprise/harness/oracles/registry.py` 的 `TARGET_ENGINES`、`REFERENCE_ENGINES` | 加新目标都要解冻 harness（在 `HASHED_PATHS` 里），S16–S18 分三批 |
| 种子语料只有 DuckDB 784 条、PG 308 条 | `seeds/corpus.json` | DataFusion 没有探索车道（M3 跑到第 32 条就 `exhausted`）；SQLite、TiDB、MySQL 也没有种子 |
| `.src/datafusion-54.0.0` 里有 474 个 `.slt` | — | 格式与 DuckDB 的 `.test` 基本相同，S17 可复用 `seeds/parse.py` 的思路 |
| 旧系统留下各引擎的已知复现：仓库根 `sqlite/` 3 条、`tidb/` 2 条、`mysql/` 1 条、`mariadb/` 2 条、`postgres/` 7 条 | — | S16–S18 拿来做 M1 式验证，也当召回真值 |
| 旧系统测过的版本：SQLite 3.51.2、PG 16.2、TiDB v8.5.8、MySQL 8.4.2、MariaDB 11.8.9 | `docs/FINAL_REPORT.md`、各复现文件头 | 用户据此定了沿用旧版本线 |
| 网格逐格串行；`surprise` 格没有墙钟强杀；`RunData` 一次读入 | `experiments/grid.py`、`metrics/rundata.py` | S15 补 |
| LLM 调用有硬上限：网关默认每次运行 200 次（`DEFAULT_MAX_CALLS`），网格要求填 `max_calls` | `roles/constants.py`、`grid.py` | 用户定不设上限，S15 让两处都能设成不限 |
| 每个角色用哪一档模型是常数（`*_TIER`），网格没有换档开关 | `roles/constants.py` | S15 补（A11 要用） |
| `sqlancer` 臂只读汇总 JSON；Windows 本机没有 Java | `baselines/sqlancer.py` | S15 新写真正运行 SQLancer 的臂；本机与服务器都要装 JDK |
| 代码按平台区分 `Scripts/python.exe` 与 `bin/python`，但从没在 Linux 上跑过 | `harness/manifest.py`、`harness/oracles/version_differential.py`、`gates/s01.py` 等 | S14 在服务器上跑全部门槛，平台差异逐条记录 |
| 吞吐：DuckDB 3 小时 8600 条；理论存储 152 MB、账本 79 MB | S11 长跑 | 每格 24h 约 2 GB，全部约 0.45 TB，服务器只有 309 GB 可用：每个里程碑后归档 |
| 服务器（`ssh 3090`，经 UNSW 跳板、免密钥，用户 `junkezhang`）：Ubuntu 24.04.4，8 核 16 线程，62 GB，可用 309 GB；有 git、tmux、rsync、Python 3.12.3；没有 uv、Java | 2026-10-19 只读核查 | S14 装 Python 3.13.9（uv）、JDK、全部 venv 与 PG |

### 与计划的偏差

- 原 CoevoDB 不再评估（PLAN 原定作对照组）；SQLancer 改为在服务器上重跑（S11 验收原定拷回原始结果）；被测引擎扩到六个。这些都是用户的新决定，已记进 PLAN §9。
- S13 本身是在原定的十二个会话之后新开的。
- 没有改 `CLAUDE.md` 与 `ORCHESTRATION.md`：按规定要用户同意。见未决问题"S13 新发现"第 1 条。
- 讨论稿的本地副本 `S13_DRAFT.md` 不入库，已删除，内容全部并入 EXPERIMENT.md。

### 下一会话的起点：S14

- 起点 `s13-done-r2`。范围见 SESSIONS 的 S14 一节；收尾时连同 `CLAUDE.md`（"12 个实施会话"、服务器的引擎环境）与 `ORCHESTRATION.md`（grok 不登录服务器）的改动一起给用户看。
- 开工前先问用户服务器是否空闲。Claude 只用 ssh 搭环境；grok 不登录服务器，需要改的代码照旧在本机 worktree 里由 grok 改。
- PG 参照在本机重启后不会自己起来：开工检查先跑 `pg_ctl status`。

## 最近完成会话：S12（2026-10-16）

Claude Code 担任编排者，全部实现来自 grok 工作包。用户的指示是"现在开始完成S12"。会话分支 `session/s12` 从 main 的 0dae74d 建立（`s11-done-r2` 之后只多一个记下方案 A 的文档提交）；起点独立复跑 935 passed / 3 skipped，GATES PASS 11/11。两个包都合并；不需要真实调用，没有重跑长跑。收尾合并回 main，tag `s12-done`。这是 SESSIONS 里的最后一个会话。用户验收后另打 `s12-done-r2`（只多了验收记录，代码与门槛相同）；之后的工作从 `s12-done-r2` 起。

**用户验收（2026-10-16）：** 用户的答复是"全部确认"。收尾消息里的五项人工检查都按编排者的建议定下，逐项见 DECISIONS 的 S12 验收一条：
- `framework/main.py` 的转发入口保留；
- 三处位置锚点（`PROJECT_DIR` 与两处 `sys.path`）算作移动允许的改动；
- `evolution/__init__.py` 从 `archive.coevo.controller` 的再导出现在不动（删它算改逻辑，要断开这条链时另开小修）；
- `framework/surprise/ARCHITECTURE.md` 照现在的样子接受，包括"Relation to the old system"一节的口径；
- 下一步是规划正式实验，要定的事见文末"S12 之后"。

下面"PI 已自行核查并定下的选择"五条也随之由用户确认。

### 交付与门槛

按用户选定的方案 A（DECISIONS"S12 准备"一条）：

- **旧主循环**的独用部分移入 `framework/surprise/baselines/coevodb_v1/`，子目录结构与原路径一一对应：`main.py`；`evolution/` 的 `bandit.py`、`co_evolution.py`、`coverage.py`、`playbook.py`；`agents/bug_hunter.py`；`guidelines/`；`coverage/`。新加三个只含 docstring 的 `__init__.py`（包本身、`evolution/`、`agents/`）。
- **`framework/main.py`** 现在只是转发入口（`runpy.run_module("surprise.baselines.coevodb_v1.main", run_name="__main__", alter_sys=True)`），`python main.py …` 照旧可用，`--help` 与 `s11-done-r2` 逐字相同；`python -m surprise.baselines.coevodb_v1.main …` 等价。`surprise/baselines/old_no_llm.py` 一行没改，经转发跑新位置的代码。
- **共用原语**留在原位、只有一份：`evolution/__init__.py`、`evolution/dce.py`、`agents/__init__.py`、`agents/base_agent.py`、`agents/bug_fixer.py`、`agents/json_utils.py`、`llm/`、`oracles/`、`targets/`、`diagnosis/`、`seeds/`、`util/`、`scripts/cross_engine.py`。harness 指纹（`HASHED_PATHS`）与 S8 长跑钉住的代码摘要都没动，长跑与召回跑不用重跑。
- **归档**：`coevo/` → `framework/archive/coevo/`，`repair_bench/` → `framework/archive/repair_bench/`；`archive/` 带只含 docstring 的 `__init__.py` 与 `README.md`，仍可导入。`evolution/__init__.py` 那一行改成 `from archive.coevo.controller import CoEvolutionController`，所以 Hunter 导入 `evolution.dce` 时仍会连带导入归档的原型（与移动前相同）。
- **只改导入路径的旧文件**（11 个）：`evolution/__init__.py`、`campaigns/pg_coldstart.py`、`scripts/` 下 `corpus_hunt`、`flaky_mine`、`llm_rule_gen`、`make_playbook_seed`、`make_playbook_seed_v2`、`testing/test_new_components.py`、`tests/test_diagnosis_dce.py`、`tests/test_verified_loop.py`、`framework/test_simple.py`。另有三处位置锚点改成指向原目录（`coevodb_v1/main.py` 的 `PROJECT_DIR`，`archive/repair_bench/` 两个脚本的 `sys.path`），`tests/test_surprise_s11_grid.py` 一处读 `main.py` 取值表的路径，仓库根 `.gitignore` 一行。
- **文档**：根 `README.md` 只改 Framework 一节；`framework/README.md` 改写成新框架的 README（目录表、命令、测试与门槛、原 CoevoDB 对照组、本机路径）；`framework/AGENTS.md` 保留全部规则，补 Windows 上的密钥与 LLM 角色默认全关，加 "Repository layout" 一节，PostgreSQL 脚本路径改到 `campaigns/`，示例命令改成 `main.py` 真有的参数；新写 `framework/surprise/ARCHITECTURE.md`（数据流、十个子包、不变式、与旧系统的关系、文档索引）。

门槛 `gates/s12.py` 共六组：

- `layout`：两棵新树的文件集合精确比对、旧路径清空、转发器的形状、共用原语在原位且没有第二份、`.gitignore`。
- `moves`：`s11-done-r2` 的每个旧代码 `.py`（`surprise/` 以外，不含 `test_surprise_*`）与现在对应位置的文件比较：导入一律换成绝对的、移动前的模块名，再套用 `ANCHORS` 表，AST 必须相同；留在原位又不在 `IMPORT_EDITED` 表里的逐字节相同；移动的非 Python 文件逐字节相同。
- `imports`：全仓库没有导入旧位置的语句，第一方导入都能解析，移动的模块能导入，三个脚本答 `--help`，coevo 冒烟从归档跑通。
- `isolation`：S8 / S9 门槛的无 LLM 检查按旧模块名列（`agents.bug_hunter`、`evolution.co_evolution`、`guidelines`），移动之后这几个名字不会再出现；这一组按新名字补上，并查 harness 不导入 `archive` 与 `coevodb_v1`。
- `old_arm`（SESSIONS 的"原 CoevoDB 臂在新位置可跑"）：`--help` 三处逐字相同；从 `s11-done-r2` 导出旧代码，2 轮 `no_llm` 运行的 9 个产物去掉时间与路径字段后与新位置相同（含 3992 次 SQL 执行数与覆盖单元集合）；`old_no_llm` 跑 1 分钟、指标能读。
- `docs`：四个文档里反引号与链接中的仓库路径全部存在，各自要提到的内容都在。

"S01–S11 的全部门槛仍通过"由 `gates.all` 保证。门槛派发前在一个不入库的参考移动上验证过（`.orch/scratch/s12/ref_move.py`），并对六种故意的违规都报失败。

最终复跑（全部合并之后，在 `session/s12` 主检出区独立运行，在 `framework/` 下，去掉密钥）：

| 命令 | 结果 |
|---|---|
| `../.venv/Scripts/python.exe -m pytest -q testing tests` | 935 passed, 3 skipped，退出码 0（与起点相同，skip 未增加） |
| `../.venv/Scripts/python.exe -m surprise.gates.all` | S01 7/7、S02 5/5、S03 5/5、S04 9/9、S05 9/9、S06 12/12、S07 15/15、S08 11/11、S09 12/12、S10 12/12、S11 17/17、S12 6/6；GATES: PASS (12/12 passed)，退出码 0 |

### 拆包清单与结论（全部已合并）

| 包 | 内容 | 轮数 | 合并 | 审查 |
|---|---|---|---|---|
| s12-move | 移动、归档、转发入口、导入路径 | 首轮通过 | d9826e6 | 与参考移动逐文件比对树：代码、测试、脚本逐字相同，只有 6 个新文件的措辞不同；约 0.97 美元 |
| s12-docs | 两份 README、AGENTS.md、架构文档 | 返工 1 轮：示例命令的参数不存在、`partition.py` 说错、接受规则漏两步、`pure_llm` 没注明会调用 LLM | 42a831e | 点名的 36 个接口逐个核对；约 0.94 美元（两轮） |

- 说明、报告、审查包归档在 `docs/orch/s12/`；grok 成本合计约 1.91 美元；编排者没有做真实调用。

### 当前接口（S12 之后的布局）

- 原 CoevoDB：`python main.py …`（转发）或 `python -m surprise.baselines.coevodb_v1.main …`；作为对照组照旧是 `python -m surprise.baselines.old_no_llm --out DIR --minutes M --seed N [--mode no_llm]`。
- 旧模块的新名字：`surprise.baselines.coevodb_v1.{main, evolution.bandit, evolution.co_evolution, evolution.coverage, evolution.playbook, agents.bug_hunter, guidelines, coverage}`；`archive.coevo`、`archive.repair_bench`。旧名字（`coevo`、`guidelines`、`coverage`、`repair_bench`、`evolution.bandit` 等）都已导入不到。
- 新框架的命令与 Python 接口没有变化，见 S11 一节"当前接口"；总览在 `framework/surprise/ARCHITECTURE.md`。

### PI 已自行核查并定下的选择（用户已验收）

**用户验收（2026-10-16）：下面五条，用户答复"全部确认"。** 它们从此是用户确认过的决定。

用户的指示是"现在开始完成S12"，下面几条没有另行提问，按 CLAUDE.md"小的实现选择自己定"处理，每条在 DECISIONS 里有理由：

1. **`framework/main.py` 留转发入口**：S01 门槛、`old_no_llm` 的 `no_llm` 命令（S11 测试钉着"不变"）、两个旧脚本与 README 都用 `python main.py`；改 S01 门槛要先问用户。
2. **三处位置锚点**算作移动允许的改动（`PROJECT_DIR`、两个 `sys.path.insert`），行为不变；不改的话移动后的入口找不到 `config.yml` 与种子。
3. **归档到 `framework/archive/`、保持可导入**；`evolution/__init__.py` 只改那一行的路径，不删（删它算改逻辑）。
4. **`coverage/` 与 `evolution/coverage.py` 算旧主循环独用**，一起移入；`scripts/`、`campaigns/` 不搬，只改导入；`test_simple.py` 留在原位。
5. **不做之前标着"留给 S12"的小修**（见未决问题"S12 发现"）：不在 SESSIONS 的 S12 范围里，其中三处在 `HASHED_PATHS` 里。

### 与计划的偏差

- `evolution/`、`agents/` 被拆开，与 SESSIONS 字面的"整个目录移入"不同：用户开工前选定的方案 A。
- SESSIONS 说 `main.py` 移入新位置；原路径上另留了一个转发文件（上面第 1 条）。
- 架构文档是新写的 `framework/surprise/ARCHITECTURE.md`（原来没有单独的架构文档，`framework/README.md` 里只有一段旧系统的目录图）。
- `s12-docs` 返工一轮。
- `s12-move` 的说明没写明 S08 的四个产物组只能在主检出区跑（`framework/results/s08/` 不在 worktree 里），执行者如实报了失败；合并后在会话分支上通过。
- 门槛在派发 `s12-docs` 之后改了一处（938aee0，`old_arm` 的时间字段匹配，比较更多、不是放宽），`s12-move` 派发时已包含。
- 没有改 harness、`HASHED_PATHS` 列出的文件、`surprise/hunter/`、`diagnoser/`、`experiments/`；没有重跑长跑；旧代码只改了导入路径与三处锚点；LLM 没有打任何标签。

## 最近完成会话：S11（2026-10-16）

Claude Code 担任编排者，全部实现来自 grok 工作包。用户的指示是"继续完成S11"。会话分支 `session/s11` 从 `s10-done-r2`（c0a9737）建立；起点独立复跑 774 passed / 3 skipped，GATES PASS 10/10。九个包（含两个计划外的纯 LLM 修正包）全部合并；纯 LLM 对照组的真实调用录制、3 小时长跑的重跑与重钉由编排者自己做。收尾合并回 main，tag `s11-done`。用户验收后另打 `s11-done-r2`（只多了验收记录，代码与门槛相同）；S12 从 `s11-done-r2` 起。

**用户验收（2026-10-16）：** 用户的答复是"全部确认"。收尾消息里的五项人工检查都按编排者的建议定下，逐项见 DECISIONS 的 S11 验收一条：
- 纯 LLM 对照组的短提示与 32000 的上限照现在的样子保留；
- "第 j 代的 Hunter"定义为"用第 j 代理论选题的 Hunter"（`--select-from` / `--theory-from`）；
- SQLancer 对照组暂时用转录的汇总，正式实验之前把原始结果 `results/sqlancer_strong/` 拷回来；
- 长跑第 8392 条暴露的"harness 没有结果行数上限"：S12 不动冻结的 harness，规划正式实验时再定要不要加上限；
- RQ6 的修复条件表只有 F2，三个条件照现在写的接受。

下面"PI 已自行核查并定下的选择"十一条也随之由用户确认。

RQ1–RQ6 的定义取自用户 Claude Doc 里的框架文档《惊讶驱动的 CoevoDB：新框架与故事》"评估设计"一节（仓库里没有这份定义）：RQ1 发现、RQ2 校准、RQ3 LLM 猜想、RQ4 Harness、RQ5 协同进化、RQ6 理论质量。

### 交付与门槛

- **S9 / S10 验收定下的四处修复**（`s11-fixes`）：
  - 理论存储写盘重试：`os.replace` 遇 `PermissionError` 最多 6 次、间隔 0.05–0.8 秒（`theory/store.py` 的私有常数，不进理论常数）。
  - 主循环保留原始异常：出错时先把完整 traceback 写进 run 目录的 `error.txt`，再写报告；写报告也失败时抛出的仍是原始异常。
  - 每个请求的总时限：`roles/constants.py` 的 `REQUEST_DEADLINE_S = 600.0`；`DeepSeekTransport` 用工作线程加流式读取，超时抛 `TransportError("DeadlineExceeded")`，网关记账、不缓存。
  - `metrics/` 认扩展词表：`dups.run_registry(run_dir)`，`dups.new_families(..., registry=)`、`recall.score(..., registry=)`。
- **单次运行的全部指标**（`metrics/rundata.py`、`rq.py`、`boundary.py`、`partition.py`、`constants.py`、`data/fix_conditions.json`）：`run_metrics(run_dir, known=, prices=, window=)` 只读一个 run 目录，返回 `rq1`–`rq6` 与 `cost`：
  - RQ1：跨臂统一的"账本家族"（有完整画像的失败的身份键，按 seq 第一次出现）、每千次执行与每小时的家族数、第一个家族出现的时刻、理论家族、重复率；
  - RQ2：有效记录数、Brier 与参照、平均惊讶、校准分箱、高惊讶记录（≥ 4 比特）、惊讶曲线与齿；
  - RQ3：猜想存活率、押注预测准确率随时间、翻译结算、经各 LLM 通道开出的家族（implement / bet / translate / llm_rule / invented_feature）、调用与 token、每家族的调用与 token、纯 LLM 臂自己的 `expect` 准确率；
  - RQ4：无效率（按原因与 oracle）、重复率、理论长度随代、编辑的接受 / 拒绝 / 回滚、留入 / 留出差距；
  - RQ5：惊讶版 CIAO 矩阵（最多 12 代 × 12 批、每批最多均匀抽 200 条）与本臂的冻结 / 配对设置；
  - RQ6：已知缺陷召回、假设边界与上游修复范围的吻合度（吻合 / 过宽 / 过窄 / 交错）；家族划分与人工判定的成对一致性（`partition.pair_agreement`）；
  - 成本：执行数、墙钟、调用、token、美元（给了价格表才算）、每家族成本。
- **分层冻结与跨代配对**（`s11-arms`；`experiments/loop.py`、`hunter/hunter.py`、`diagnoser/diagnoser.py`、`theory/workbench.py`）：`--freeze theory`（不 observe、不诊断）、`--freeze diagnoser`（照常 observe 与按代关闭，不提编辑）、`--hunter random`、`--theory-from RUN@GEN`（理论从那一代起）、`--select-from RUN@GEN`（Hunter 用那一代的理论选题与打分，进度行多一个 `select_p`）。不是默认值时 `arm` 才写进 config / report / manifest，全关的运行与 S8–S10 逐行相同。开了冻结时只允许实现器、探索先验两个不改理论的角色。
- **对照组**：
  - 纯 LLM 生成（`baselines/pure_llm.py`）：fast 档、温度 0.8、每次 4 个用例、`max_tokens` 32000、按种子轮换的主题表；用例走同一套 oracle 与 CVE（每个失败走第 3 档），模型的 `expect` 只记进 spec。提示是一段短而"先给答案"的固定文本（`s11-purellm3`）。
  - 原 CoevoDB（`baselines/old_no_llm.py`，`--mode`，默认 `no_llm`；旧代码不改）。
  - SQLancer（`baselines/sqlancer.py` 读 `baselines/data/sqlancer_summary.json`）：只是 `docs/FINAL_REPORT.md` 汇总表的转录（35 次运行、约 9030 万次检查、0 个缺陷），原始结果不在这台机器上。
  - 新框架无 LLM 版：网格里不开角色的 `surprise` 臂。
- **实验网格**（`experiments/grid.py`）：JSON 配置，臂 × 种子 × 重复，每格一个子进程、逐格串行（墙钟预算公平）；臂的种类 `surprise`、`old_coevodb`、`pure_llm`、`sqlancer`；完成的格（`cell.json` 为 `done`）续跑时不碰，其它残留改名 `<格>.stale-<k>` 保留；不需要联网的子进程去掉密钥变量；配置可带 `prices`。
- **统计、报告与图**（`metrics/stats.py`、`metrics/report.py`）：中位数、Mann–Whitney U（无并列且合计 ≤ 20 时精确分布，否则正态近似加并列与连续性修正，与 scipy 一致）、Vargha–Delaney Â₁₂，只用标准库；`python -m surprise.metrics.report GRID_DIR` 一条命令写 `report.json` 与 7 张图（RQ1 家族、RQ2 惊讶曲线与校准、RQ3 LLM、RQ4 质量、RQ5 CIAO、RQ6 召回），同一个网格得到同一份 `report.json`。
- **离线去重对比与覆盖度量**（`metrics/dedup.py`、`metrics/coverage.py`）：
  - σ 对执行前成员检验：在一次运行的全部失败上，真值是完整画像的身份键（只做了第 2 档的失败离线重做画像，版本要与运行时一致），σ 键用旧代码 `SignatureEngine._signature` 从同一份画像算；各报精度、召回与所花执行数。
  - 上游回归测试重放：`seeds/corpus.json` 里解析好的 DuckDB 上游测试按 oracle 重放到 1.1.3 与 1.5.5，报两版的标签分布与"旧版 fail 新版 pass""两版都 fail""只新版 fail"三张清单。只做度量，不写账本、不打标签。

门槛 `gates/s11.py` 共十七组：

- 修复：`constants`、`store`、`loop_error`、`deadline`、`vocabulary`。
- 指标：`stats`、`runmetrics`（种子 51 的 30 条短跑，全部指标由门槛独立重算）、`ciao`（S8 长跑产物）、`llm_metrics`（S10 的 M3 缓存重放）、`rq6`。
- 消融：`arms`（冻结、随机 Hunter、`--theory-from`、`--select-from`；每行 `select_p` 等于源理论对该记录的预测）。
- 对照组：`pure_llm_script`（脚本回复）、`pure_llm`（重放编排者录下的真实回复，`gates/s11_llm/pure_llm`，9 个文件、约 19.6 KB，只有提示与回复，按值查过没有密钥）、`sqlancer`。
- 去重与覆盖：`dedup`、`coverage`（要 `.venvs/duckdb-1.1.3-full`）。
- M4 冒烟：`grid`（下面一节）。

与 SESSIONS 的对应：

| SESSIONS 的要求 | 门槛组 |
|---|---|
| 从账本算全部指标 | `runmetrics`、`ciao`、`llm_metrics`、`rq6`、`vocabulary` |
| 分层冻结、跨代配对 | `arms` |
| CVE 覆盖度量（召回基准、上游回归测试重放），不参与打标签 | `rq6`（召回）、`coverage` |
| 配置驱动的网格，中位数、MWU、Â₁₂ | `grid`、`stats` |
| 对照组：SQLancer、原 CoevoDB、纯 LLM、新框架无 LLM | `sqlancer`、`grid`（原 CoevoDB 与无 LLM 臂）、`pure_llm_script`、`pure_llm` |
| 离线去重对比 | `dedup` |
| M4 冒烟：2 臂 × 2 种子短时网格跑通，RQ1–RQ6 指标与图一条命令生成 | `grid` |

最终复跑（全部合并、录制与长跑重钉之后，在 `session/s11` 主检出区独立运行，在 `framework/` 下，去掉密钥）：

| 命令 | 结果 |
|---|---|
| `../.venv/Scripts/python.exe -m pytest -q testing tests` | 935 passed, 3 skipped，退出码 0（起点 774，新增 161，skip 未增加） |
| `../.venv/Scripts/python.exe -m surprise.gates.all` | S01 7/7、S02 5/5、S03 5/5、S04 9/9、S05 9/9、S06 12/12、S07 15/15、S08 11/11、S09 12/12、S10 12/12、S11 17/17；GATES: PASS (11/11 passed)，退出码 0 |

### 实机运行的数字

**M4 冒烟网格**（门槛 `grid` 组；配置在 `gates/s11_cases.GRID_CONFIG`）：新框架无 LLM 臂对原 CoevoDB（`no_llm`），DuckDB 1.5.5，种子 0、1，每格 1 分钟。4 格加报告约 4 分钟（门槛 246 秒），续跑不碰已完成的格，`report.json` 与 7 张图一条命令生成；每小时家族数的中位数：新框架 29.79、原 CoevoDB 29.78，MWU p = 1.0，Â₁₂ = 0.625。 每格 1 分钟、每臂 2 个样本，这组数字只说明管线走通，不能拿来比较两个系统。

**长跑**（`results/s08/longrun`，角色全关、DuckDB 1.5.5、种子 0、七类 oracle、180 分钟）

| | S10 代码 | S11 代码 |
|---|---|---|
| 实验 | 9500 | 8600 |
| fail / pass / invalid | 95 / 4449 / 4956 | 90 / 4117 / 4393 |
| 车道（探索 / 泛化 / 细化） | 9409 / 53 / 38 | 8511 / 55 / 34 |
| 假设 / 家族 / 不同身份 | 26 / 11 / 5 | 27 / 13 / 7 |
| 编辑（接受 / 拒绝） | 0 / 2 | 1 / 2 |
| 重复率（旧系统 0.818） | 0.545 | 0.462 |
| 窗口与齿 | 95 个窗口，齿在 3、9、17、40、87 | 86 个窗口，齿在 3、9、17、35、63、78 |
| CIAO（代数；对角线 / 新理论看旧批 / 旧理论看新批，比特） | 96 代；0.026 / 0.019 / 0.063 | 88 代；0.056 / 0.029 / 0.211 |

- 以 `budget_minutes` 结束，0 条 harness_error；S8 门槛的 `longrun`、`sawtooth`、`duplicates`、`recall` 四组与 S11 的 `ciao` 组对新产物通过（b2e55ce 重钉）。
- 去掉 `elapsed_s` 后前 2936 行与 S10 代码的长跑逐行相同，第 2937 行分叉：仍是 S8 以来那条 plan variant 用例（harness 第 1 档重跑不稳定，这次判 `invalid / unstable_rerun`）。分叉之后走的路不同，3 小时里少跑了 900 条：前 8000 条的耗时与 S10 相当（9079 秒对 9016 秒），差主要在第 8392 条一条用了 941 秒（细化车道的 cross_dbms 用例，2000 行的自连接、约 200 万行结果，第 1 档重跑 5 次加单线程一次；见未决问题）。
- 这次长跑在全部改 `experiments/`、`hunter/`、`diagnoser/`、`theory/` 的包合并之后单独起跑（cc2af2b）；之后合并的 `s11-purellm3` 只动 `baselines/`。S10 代码的长跑挪到 `results/s08/longrun-s10code`。

**纯 LLM 对照组**（`gates/s11_llm/pure_llm`；DuckDB 1.5.5、种子 0、fast 档）：第三次录制成功，4 次调用、每次 4–7 千个输出 token、23–40 秒；16 条用例里 15 条 pass、1 条 invalid（equivalent_query 套不上），没有失败、没有家族；模型预测 fail 的 4 条实际都 pass。前两次录制作废、不入库：第一次 4 次调用里 3 次推理吃满 16000 上限、唯一成功的一批 7/8 无效（提示没讲清谓词的拼法）；第二次（修好提示后）6 次全部在 16000 处截断。三次单发探测定下短提示与 32000 上限。纯 LLM 对照组的调试与录制合计真实调用 17 次，全部由编排者做。

**门槛短跑上的数字**（只说明管线走通）：
- `runmetrics`（种子 51、30 条）：31 条记录、1 个账本家族、Brier 0.2194、1 条高惊讶记录、14 条 invalid、理论长度 193.0 比特。
- `llm_metrics`（M3 缓存重放）：2 条猜想、存活率 0、7 次结算的押注准确率 0.714；经 bet 开出 1 个家族。
- `rq6`：F2 家族的假设"过窄"（修复条件全在、多 9 个字面量：出生时的 S 是整条 φ）；1.1.3 召回 run 的召回 0.5。
- `dedup`（种子 51 短跑）：3 条失败、1 条真重复；σ 精度 / 召回 1.0 / 1.0，成员检验一次也没判重复。
- `coverage`：4 条上游回归测试 × 2 个 oracle：plan variant 两版都 4 条 pass，equivalent_query 两版都 4 条 invalid。
- `sqlancer`：35 次运行、0 个缺陷，每行与 `docs/FINAL_REPORT.md` 一致。

### 拆包清单与结论（全部已合并）

| 包 | 内容 | 轮数 | 合并 | 审查 |
|---|---|---|---|---|
| s11-fixes | 存储写盘重试、保留原始异常、请求总时限、metrics 认扩展词表 | 首轮通过 | c8aeff5 | 独立复跑 782 passed；S9 `replay`、S10 `m3` 逐行重放；约 0.67 美元 |
| s11-runmetrics | 单次运行的 RQ1–RQ6 指标、CIAO、边界吻合、划分一致性 | 首轮通过 | 8f88016 | 789 passed；`ciao` 在主检出区对长跑跑过；约 2.43 美元 |
| s11-purellm | 纯 LLM 对照组 | 首轮通过 | bf270d2 | 约 1.55 美元 |
| s11-grid | 实验网格、原 CoevoDB 的 mode、SQLancer 转录 | 首轮通过 | de756ff | 889 passed；网格部分通过，报告命令留给 `s11-report`；约 1.26 美元 |
| s11-arms | 冻结、随机 Hunter、`--theory-from`、`--select-from` | 首轮通过（门槛一条断言改准，a742cca） | b294745 | 807 passed；S8 `lanes` / `determinism`、S10 `m3` 逐行相同；约 2.29 美元 |
| s11-dedup | 离线去重对比、上游回归测试重放 | 首轮通过 | 69d6811 | 820 passed；约 1.47 美元 |
| s11-purellm2 | 纯 LLM 提示讲清谓词拼法、每次 4 个用例（计划外） | 首轮通过 | 73f61a0 | 约 0.42 美元 |
| s11-report | 统计检验、报告命令与 7 张图（带 `grid.py` 的一行修正） | 返工 1 轮：缺 `bugs.jsonl` 时造临时目录绕过；`mean_surprise` 恒为空 | baede2f | 914 passed；`stats`、`runmetrics`、`grid` 通过；约 3.03 美元（两轮） |
| s11-purellm3 | 纯 LLM 换短提示、上限 32000（计划外） | 首轮通过 | 08b0334 | 约 0.32 美元 |

- 说明、报告、审查包归档在 `docs/orch/s11/`；grok 成本合计约 13.44 美元。
- 计划外的两个包都因为纯 LLM 对照组的提示：第一次录制暴露了提示没讲清谓词拼法，第二次暴露了推理模型在密集提示上推理不止。

### 当前接口

命令（在 `framework/` 下）：

- `python -m surprise.experiments.loop … [--freeze theory|diagnoser] [--hunter value|random] [--theory-from RUN_DIR@GEN] [--select-from RUN_DIR@GEN]`；出错时 run 目录里有 `error.txt`。
- `python -m surprise.experiments.grid run CONFIG --out DIR [--only ARM]...`；`python -m surprise.experiments.grid status DIR`。`run` 退出码 0 = 选中的格全部完成，1 = 有格失败，2 = 配置不合法。
- `python -m surprise.metrics.report GRID_DIR [--out DIR] [--dedup FILE] [--coverage FILE]`：默认写到 `GRID_DIR/report/`。
- `python -m surprise.baselines.pure_llm --out DIR --seed N [--engine duckdb] [--oracle …] [--max-experiments N] [--max-minutes M] [--llm-cache DIR] [--llm-max-calls N] [--llm-offline]`。
- `python -m surprise.baselines.old_no_llm --out DIR --minutes M --seed N [--mode no_llm] [--python 解释器]`。
- `python -m surprise.metrics.dedup RUN_DIR --out FILE [--limit N] [--no-reprofile]`。
- `<venv 的 python> -m surprise.metrics.coverage run --out FILE [--prefix duckdb:test/] [--limit N] [--oracle …]`（1.1.3 用 `.venvs/duckdb-1.1.3-full`）；`… coverage compare OLD NEW --out FILE`。

Python 接口：
- `surprise.metrics.rq`：`run_metrics(run_dir, *, known=None, prices=None, window=None)`、`old_metrics(old_dir)`、`ledger_families`、`ciao(wb)`、`theory_lengths(wb)`；`surprise.metrics.rundata.RunData.open(run_dir)`（`records`、`progress`、`config`、`report`、`manifest`、`registry`、`workbench()`、`book(name)`）。
- `surprise.metrics.stats`：`median`、`summarize`、`a12`、`mann_whitney_u`；`surprise.metrics.boundary`：`classify`、`load_fix_conditions`、`compare`；`surprise.metrics.partition.pair_agreement(pred, truth)`。
- `surprise.metrics.dedup.compare_dedup(run_dir, *, limit=None, reprofile=True)`；`surprise.metrics.coverage`：`select`、`replay`、`compare`。
- `surprise.baselines.sqlancer`：`load(path=None)`、`metrics(summary, engine="duckdb")`。
- `surprise.experiments.grid`：`load_config(path)`、`run_grid(config, out, *, only=None)`、`status_text(out)`。
- `Workbench.create(root, ..., theory=None)`；`Hunter(..., select="value")` 与 `remember_case`。

### PI 已自行核查并定下的选择（用户已验收）

**用户验收（2026-10-16）：下面十一条，用户答复"全部确认"。** 它们从此是用户确认过的决定；逐条见 DECISIONS 的 S11 各条。

1. **跨臂统一的家族口径**：账本里有完整画像的失败的身份键（S8 重复率裁判的键），按 seq 第一次出现算一个新家族；不依赖理论，所以纯 LLM、冻结理论的臂也能算。新框架臂另外照旧报理论家族；原 CoevoDB 用 `bugs.jsonl` 的报告键；SQLancer 用转录的汇总。所有臂都报"每小时"，有账本的臂另报"每千次执行"。
2. **指标常数**（`metrics/constants.py`）：高惊讶 4.0 比特、校准分箱 (0, 0.05, 0.2, 0.4, 0.6, 0.8, 0.95, 1.0)、CIAO 最多 12 代、每批抽 200 条、曲线窗口 100、齿 0.25 / 5。
3. **CIAO 的"第 j 批"** = 第 j 代理论打开期间被观察的有效记录（代按每 100 条的 checkpoint 切）。
4. **"第 j 代的 Hunter"= 用第 j 代理论选题的 Hunter**（本框架的 Hunter 自己不学东西），跨代配对 = `--select-from` 与 `--theory-from` 的组合；选题时 Hunter 从源运行的账本借正例的 SQL 来细化，不标为已做、不消耗随机数。
5. **纯 LLM 对照组**：fast 档、温度 0.8、每次 4 个用例、上限 32000、短提示（逐字在 `baselines/pure_llm.py`）；不在代码里替模型修 SQL；失败一律走第 3 档。
6. **离线去重对比**的真值是完整画像的身份键，σ 用旧代码的 `SignatureEngine._signature`，成员检验 = 执行前预测区为 confirmed。
7. **SQLancer 只转录汇总表**（原始结果不在这台机器上），标明是转录、检查数是近似值。
8. **RQ6 的边界真值只有 F2**（唯一合并了上游修复的已知缺陷，duckdb/duckdb#24685）；修复条件按 PR 说明定为 {有 PARTITION BY、分区键重复、两个以上窗口表达式}。家族划分的成对一致性只给函数，网格里没有人工真值，报告留空。
9. **统计只用标准库**；没有价格表就只报 token、不报美元。
10. **请求总时限 600 秒**、存储写盘重试 6 次。
11. **M4 冒烟网格**：新框架无 LLM 臂对原 CoevoDB（`no_llm`），种子 0、1，每格 1 分钟，逐格串行；中断的格改名保留。

### 与计划的偏差

- 拆了九个包，比开工时定的七个多两个计划外的修正包（`s11-purellm2`、`s11-purellm3`）与一轮返工（`s11-report`）。
- 纯 LLM 对照组录了三次，前两次作废、不入库；合计真实调用 17 次。
- 门槛 `gates/s11.py` / `s11_cases.py` 在派发后改了三次，期望都没有放宽：a742cca（`arms` 组"要出现细化 / 泛化车道"改成每行 `select_p` 等于源理论的预测，更强也更准）；29260de（`PURE_LLM_CASES_PER_CALL` 8 → 4）；7e202e5（`PURE_LLM_MAX_TOKENS` 16000 → 32000）。录制的回复（a517b4b）是门槛事先说好要补的数据。
- 编排者先合并了 `s11-purellm2`、`s11-purellm3`，之后才读审查包标出的"改写了断言"：核对过没有放宽（一处是说明要求的常数 8 → 4，一处换成对整段提示的逐字比对）。顺序错了，结论不变。
- 长跑在最后一个包（`s11-purellm3`，只动 `baselines/`）合并之前起跑。
- DECISIONS 里 `s11-runmetrics` 的花费先写错（约 1.9 美元），后面追加了一条更正（约 2.43 美元）。
- SQLancer 对照组只有转录的汇总，不是逐次运行的结果。
- 没有改 harness，没有改 S6 / S7 的规则与 S8–S10 门槛的检查逻辑；旧代码没有改；LLM 没有打任何标签。

S11 留下的未决问题在文末"未决问题"一节的"S11 发现"一组里。

## 最近完成会话：S10（2026-10-16）

Claude Code 担任编排者，全部实现来自 grok 工作包。用户的指示是"读取当前项目进度，然后开始完成S10"。会话分支 `session/s10` 从 `s09-done-r2`（1637287）建立；起点独立复跑 692 passed / 3 skipped，GATES PASS 9/9。九个包（含两个计划外的小包）全部合并；真实调用的录制、长跑由编排者自己做。收尾合并回 main，tag `s10-done`。用户验收后另打 `s10-done-r2`（只多了验收记录，代码与门槛相同）；S11 从 `s10-done-r2` 起。

**用户验收（2026-10-16）：** 用户的答复是"全部确认"。收尾消息里的五项人工检查都按编排者的建议定下，逐项见 DECISIONS 的 S10 验收一条：
- harness 第二层照现在的样子保留：参照引擎不一致、或改写只在目标引擎上报错，都判 invalid，不判 fail；
- 词表按版本分段保留：发明的特征只写进 `llm/vocabulary.json`，下一次用 `--vocabulary` 起的运行才生效；
- 翻译者、词汇发明者、oracle 发明者的 token 上限保留 16000；
- 理论存储写盘的重试与主循环保留原始异常，在 S11 开头与 S11 自己对 `theory/`、`experiments/` 的改动一起修，只重跑一次长跑；
- oracle 发明者的"所有引擎一致"验收规则按 PLAN 决策 9 暂不改，接上证明器时再定。

下面"PI 已自行核查并定下的选择"六条也随之由用户确认。

**用户在开工时的决定（2026-10-15）：** 同意小范围解冻 harness。oracle 发明者要把多引擎验收过的改写放进 Equivalent query 的规则库，而这个库在冻结区里。只改 `harness/oracles/rewrites.py` 与 `equivalent_query.py`：规则库加第二层"已验收的改写模板"，判 fail 的代码与冻结的三条规则不变；改完重新冻结（477d6eb，新哈希 `98b70d9e81fc`）。

### 交付与门槛

四个新角色全部在 `surprise/roles/` 里，按开关懒加载；全关时与 S8、S9 逐行相同。

- **harness 的第二层**（`harness/oracles/rewrites.py`、`equivalent_query.py`）：
  - 两种模板：`query_wrap`（恰好一个 `{q}`，整条语句）与 `predicate_wrap`（1–3 个 `{p}`，顶层 WHERE 谓词）。由 `apply_template` 机械套用；`template_problem` 挡掉分号、注释、写操作关键字、多余的花括号。
  - 库文件路径走环境变量 `SURPRISE_REWRITE_LIBRARY`；格式 `{"schema": 1, "rules": [...]}`；任何一处不合格整库不认。
  - 第二层规则判定前，参照引擎（与 Cross-DBMS 同一组）要至少 2 个在本例上原查询与改写结果一致、且没有一个不一致，否则 `invalid / untrusted_rewrite`；目标引擎上一边报错一边成功也判 `untrusted_rewrite`（`premise = rewrite_error`），不判 fail。`wrong_result` 与 `crash` 照旧判 fail。
  - 冻结规则的路径与标签 `detail` 与解冻前逐字节相同（门槛核对）。
- **框架**（`roles/base.py`、`roles/runtime.py`、`hunter/`、`experiments/loop.py`）：
  - `RoleContext`、`Observed`、`Role`、`PLUGINS`；`runtime.ROLES` 六个名字；没开的角色模块不导入。
  - Hunter 多了 `prior`（未探索区的 U 改用角色给的伪计数）、`extra_rules`（Equivalent query 的候选规则接上已验收的 `llm:*` 规则）、`registry`。
  - 主循环：`--llm` 认六个名字；oracle 发明者开着时设库变量、结束恢复；`--vocabulary FILE` 让一次运行从头使用扩展词表。
- **探索先验**（`roles/prior.py`）：每次选择最多一次调用、每次最多 16 个单元（排序后取未问过的）；证据只来自两份引擎检出（DataFusion 的 `dev/changelog`、DuckDB 的 `test/issues`），不读项目自己的 bug 账本。伪计数 `(p_eff·100, 100)`，`p_eff = w·p + (1−w)·0.01`；结算满 20 条后 `w = clip(1 − Brier/Brier_ref, 0, 1)`，之前 0.5。只改 Hunter 的 U，不改理论的 P_T 与惊讶。
- **迁移翻译者**（`roles/translator.py`）：每个（家族，另一个引擎）翻一次，新车道 `translate`；翻译要过 φ 核对（假设 S 的 ast 与 data 字面量）；预测的开关用第 3 档画像的 fix set（bisect）或归属测试核对，没有开关的引擎核对行为形状。
- **词汇发明者**（`roles/vocab_inventor.py`、`features/registry.py`）：某个家族确认区里的意外通过满 2 条、正例满 2 条时调用一次；最近的 ⌈n/3⌉ 条留出、不进提示；验收依次是定义、正则（不匹配空串、≤200 字符）、语料扫描（子进程，20 秒时限，命中 ≤ 一半）、训练、留出。收下的特征写进 `llm/vocabulary.json`，**本次运行的理论不改**，之后用 `--vocabulary` 起的运行才用它（按词表版本分段）。注册表另外挡掉能匹配空串的正则（S5 留的事）。
- **oracle 发明者**（`roles/oracle_inventor.py`）：第 1 条实验之后与每 100 条调用一次，每次运行最多 3 次、每次最多 3 条模板；验收：按种子语料次序找 5 个实例，每个实例上至少 3 个引擎（DuckDB、DataFusion、SQLite、PostgreSQL 中）原查询跑通、结果至少 2 行、改写结果一致；任何一个引擎不一致就不收。收下的写进 `llm/rewrites.json`，就是 harness 读的库。
- **上限**：翻译者、词汇发明者、oracle 发明者的 `max_tokens` 由 8000 提到 16000（`s10-caps`）。

门槛 `gates/s10.py` 共十二组：

- 十组用脚本回复或不调用：`isolation`、`constants`、`frozen`、`library`、`frame`、`switches`、`prior`、`translator`、`vocab_inventor`、`oracle_inventor`。
- 两组重放编排者录下的真实回复：`translator_real`、`m3`。回复缓存提交在 `gates/s10_llm/`（55 个文件、364 KB，只有提示与回复，按值查过没有密钥）。整个门槛不联网。

与 SESSIONS 的对应：

| SESSIONS 的要求 | 门槛组 |
|---|---|
| 每个角色可单独开关、关掉时零调用 | `switches`（六个全开时每个都被调用；逐个关掉时它零调用、账本没有它的行、插件模块不被导入）；全关时与 S8 相同仍由 S9 的 `wiring` 查 |
| DataFusion 54.0.0 上从 DF-A 出发闭环复现 DF-B，固定缓存后可重放 | `m3` |
| 探索先验：给未测单元先验失败率，用 Brier 分数校准 | `prior`、`frame` |
| 迁移翻译者：翻成另一个引擎的开关与写法，用归属测试和 bisect 检验 | `translator`、`translator_real` |
| 词汇发明者：确认区反复意外通过时提议新特征，过留出验收才入表 | `vocab_inventor`、`frame`（`--vocabulary`） |
| oracle 发明者：多引擎一致才进入 Equivalent query 的改写规则库，判定代码不变 | `oracle_inventor`、`library`、`frozen` |

最终复跑（全部合并、录制与长跑重钉之后，在 `session/s10` 主检出区独立运行，在 `framework/` 下，去掉密钥）：

| 命令 | 结果 |
|---|---|
| `../.venv/Scripts/python.exe -m pytest -q testing tests` | 774 passed, 3 skipped，退出码 0（起点 692，新增 82，skip 未增加） |
| `../.venv/Scripts/python.exe -m surprise.gates.all` | S01 7/7、S02 5/5、S03 5/5、S04 9/9、S05 9/9、S06 12/12、S07 15/15、S08 11/11、S09 12/12、S10 12/12；GATES: PASS (10/10 passed)，退出码 0 |

### 实机运行的数字

**M3**（`gates/s10_llm/m3`；产物在 `results/s10/m3_llm`，不入库）
- 设置：DataFusion 54.0.0、种子 0、cross_dbms / tlp / norec / equivalent_query、最多 40 次选择、六个角色全开、只引导 DF-A。
- 规模：32 条实验后以 `exhausted` 结束（DataFusion 没有种子，没有探索车道，候选用完）。43 次调用：实现器 36、先验 4、猜想者 2、oracle 发明者 1。
- 车道：引导 1、implement 18、bet 7、refine 4、generalize 2。标签：fail 8、pass 24。家族 2 个。
- **复现 DF-B**：第 3 条就是猜想 c1（对 DF-A 的 h1）的预测"左侧有重复的 INTERSECT ALL 会失败"的 bet 实验，判 fail（只多行），开出新家族。身份裁判的键 `shape|datafusion|wrong_result|-|extra_only` 等于现场 certify `DF-B` 复现得到的键，与 DF-A 的 `missing_only` 不同；对它的猜想 c2 的 `revise` 被接受，之后 implement 车道又有 5 条失败归进同一家族。
- 先验：5 个单元定上价；结算 9 条（未满 20 条，权重仍是 0.5）；Brier 0.0068，参照 0.0001。
- oracle 发明者：提了 3 条，收下 `SELECT * FROM ({q}) AS llm_sub` 与 `WITH llm_cte AS ({q}) SELECT * FROM llm_cte`（都是提示里的例子），`({p}) IS TRUE` 因不一致不收。这次运行里没有用到收下的规则：DataFusion 没有探索与迁移车道，Equivalent query 的候选只从那两条车道来。
- 词汇发明者没有触发（没有家族攒到 2 条矛盾通过）；翻译者只有一个引擎，不工作。两者各由脚本组与 `translator_real` 查。
- 与 S9 的同种子短跑相比，DF-B 从第 13 条提前到第 3 条。

**翻译者**（`gates/s10_llm/translator`）：F2 在 DuckDB 上开出家族（fix set `window_self_join`），翻到 DataFusion 的 plan variant；1 次调用（12490 个输出 token），预测 pass，实际 pass，结算 kept。

**被 oracle 发明者拒掉的那个实例是 DuckDB 的已知缺陷**：种子语料第 183 条（带相关 EXISTS 的计数）在 DuckDB 1.5.5 上默认返回 0，关掉 `filter_pushdown` 或 `deliminator` 返回 4，SQLite 也是 4；fix set 与 F1 家族相同。验收规则"每个引擎都一致"因此把一条正确的模板拒了（见未决问题）。

**真实调用合计**：编排者 47 次（M3 第一次录 43 次、重录 1 次；翻译 8000 上限下 2 次、16000 下 1 次），执行者 3 次（先验、翻译者、词汇发明者各 1 次）；全部 fast 档。

**长跑**（`results/s08/longrun`，角色全关、DuckDB 1.5.5、种子 0、七类 oracle、180 分钟）

| | S9 代码（角色全关） | S10 代码（角色全关） |
|---|---|---|
| 实验 | 9388 | 9500 |
| fail / pass / invalid | 106 / 4438 / 4844 | 95 / 4449 / 4956 |
| 车道（探索 / 泛化 / 细化） | 9279 / 68 / 41 | 9409 / 53 / 38 |
| 假设 / 家族 / 不同身份 | 30 / 15 / 7 | 26 / 11 / 5 |
| 重复率（旧系统 0.818） | 0.533 | 0.545 |
| 窗口与齿 | 93 个窗口，齿在 3、9、17、43 | 95 个窗口，齿在 3、9、17、40、87 |

- 以 `budget_minutes` 结束，0 条 harness_error；S8 门槛的 `longrun`、`sawtooth`、`duplicates`、`recall` 四组对新产物通过（9cf3009 重钉）。
- 去掉 `elapsed_s` 后前 2936 行与 S9 代码的长跑逐行相同，第 2937 行分叉：与 S9 那次和 S8 分叉的是同一条 plan variant 用例（harness 第 1 档重跑不稳定）。
- 第一次重跑（21:13 起，与审查和别的包同时跑）在第 3886 条因负载判出不同的标签而分叉，第 6526 条之后理论存储写盘失败、整次作废，产物在 `results/s08/longrun-s10-crashed`（不入库）。第二次在全部包合并后单独跑，经报错记录脚本启动，没有出错。S9 代码的长跑挪到 `results/s08/longrun-s9code`。

### 拆包清单与结论（全部已合并）

| 包 | 内容 | 轮数 | 合并 | 审查 |
|---|---|---|---|---|
| s10-harness | 第二层改写规则库 | 首轮通过 | 3502033 | 独立复跑 701 passed；参照引擎计数用真实引擎核对；约 1.23 美元 |
| s10-frame | 插件框架、Hunter 钩子、`--vocabulary` | 首轮通过 | 243af6e | 独立复跑 705 passed，S8 六组短跑、S9 十二组通过；约 2.01 美元 |
| s10-testfix | frame 的一条测试不再依赖模块是否存在、执行次序（计划外） | 首轮通过 | fe31e6a | 714 passed；约 0.18 美元 |
| s10-oracle | oracle 发明者 | 首轮通过 | d9f77cf | 约 1.54 美元 |
| s10-prior | 探索先验 | 返工 1 轮：回复里非字符串的 `unit` 会让整次运行出错 | 78c7ffe | 约 1.41 美元（两轮） |
| s10-vocab | 词汇发明者、注册表挡空正则 | 首轮通过 | 5fa6cf5 | 747 passed，S05 9/9；约 1.48 美元 |
| s10-translator | 迁移翻译者 | 首轮通过 | ccca405 | 764 passed；约 2.95 美元 |
| s10-caps | 三个角色的 token 上限提到 16000（计划外） | 首轮通过 | 9e724ee | 编排者独立复跑 774 passed；约 0.09 美元 |

- 说明、报告、审查包归档在 `docs/orch/s10/`；grok 成本合计约 10.89 美元。
- 计划外的两个包：`s10-testfix`（与 S9 的 `s09-testfix` 同一类：并行开发的包各自都绿，合并后才暴露对环境的依赖）；`s10-caps`（录制才看出 8000 的上限截断回复）。

### 当前接口

命令（在 `framework/` 下）：

- `python -m surprise.experiments.loop … [--llm ROLE]... [--llm-cache 目录] [--llm-max-calls N] [--llm-offline] [--vocabulary 文件]`
  - `ROLE` 是 `implementer`、`conjecturer`、`prior`、`translator`、`vocab_inventor`、`oracle_inventor` 之一，可重复。
  - `--vocabulary` 读 `Registry.save` 格式的文件（如上一次运行的 `llm/vocabulary.json`），整次运行（φ 提取子进程、Hunter、Diagnoser、理论、角色）都用它；`config.json` 与 manifest 多一个 `vocabulary`。
  - 开着 `oracle_inventor` 时，运行期间 `SURPRISE_REWRITE_LIBRARY` 指向 `llm/rewrites.json`。

run 目录的 `llm/` 在 S9 之外多了：`prior.jsonl`、`translations.jsonl`、`vocabulary.jsonl` 与 `vocabulary.json`、`rewrites.jsonl` 与 `rewrites.json`。进度行的 `llm` 里每个开着的新角色一个键（各自 `step()`），`report.json` 的 `llm` 里各自 `report()`，manifest 的 `llm.plugins` 里各自 `manifest()`。

Python 接口：
- `surprise.roles.base`：`RoleContext`、`Observed`、`Role`、`PLUGINS`；`surprise.roles.runtime.ROLES`、`build_roles(..., oracles=())`，`RoleSet.plugins`、`.prior`、`.rewrite_rules()`、`.rewrite_library`。
- 每个新角色模块有 `build(ctx) -> Role`：`ExplorationPrior`（`prepare(wb, units, *, index)`、`pseudo(unit)`、`weight()`、`brier()`）、`Translator`（`sources()`、`translations()`、`allowed_switches(engine)`）、`VocabInventor`（`accepted()`、`split_holdout(items)`）、`OracleInventor`（`rules()`、`accept_template(kind, template)`）。
- harness：`rewrites.template_problem`、`apply_template`、`load_library(path=None)`、`is_library_rule`、`LIBRARY_*` 常数。
- Hunter：`Hunter(..., prior=None, extra_rules=None, registry=None)`；`scoring.score(..., prior=None)`；`operators.oracle_options(case, oracles, extra_rules=())`；`PhiExtractor(..., registry_path=None)`。

### PI 已自行核查并定下的选择（用户已验收）

**用户验收（2026-10-16）：下面六条，用户答复"全部确认"。** 它们从此是用户确认过的决定。

1. **词表按版本分段**（S6 留给 S10 定）：发明的特征写进 `llm/vocabulary.json`，本次运行不改理论，之后用 `--vocabulary` 的运行从头用它。中途改词表就要重放整个理论、重新判接受过的编辑，没有做。
2. **探索先验只改 Hunter 的 U**，不改理论的 P_T 与惊讶；Brier 校准的规则见上面；证据不读项目自己的 bug 账本（那是召回的真值）。
3. **第二层规则在目标引擎上的"一边报错"判 invalid、不判 fail**：模板在某个引擎上不适用不是缺陷的证据（实测 DuckDB 1.5.5 没有 `octet_length(VARCHAR)`）。
4. **三个角色的 token 上限提到 16000**（先验仍 8000，实现器是 S9 的常数仍 8000）。
5. **M3 只在 DataFusion 上跑**：翻译者在一个引擎上不工作，另录 `translator_real`；oracle 发明者收下的规则在这次运行里用不上（DataFusion 没有探索车道）。M3 以 `exhausted` 在 32 条结束，不是 40。
6. **长跑第一次重跑中断后**，在词汇包合并之后经报错记录脚本重跑（见实机数字与未决问题）。

### 与计划的偏差

- 改了冻结的 harness：用户在开工时批准，只动了两个文件，已重新冻结。
- 拆了九个包，比开工时定的六个多两个计划外的小包（`s10-testfix`、`s10-caps`）与一个第二轮的返工（`s10-prior`）。
- 门槛 `gates/s10.py` / `s10_cases.py` 在派发后改了两次，期望都没有放宽：615dd63（`switches` 组的脚本猜想不提 revise，让 h1 保住词汇发明者等的触发条件）；c3507db（三个 token 上限；`m3` 组按记录结束时的归属取家族）。录制的回复（931f0e1、f38744e）是门槛事先说好要补的数据。
- 长跑的第一次重跑中断，多花了一次 3 小时重跑。
- 没有改 S6 / S7 的规则与 S8、S9 门槛的检查逻辑；LLM 没有打任何标签。

S10 留下的未决问题在文末"未决问题"一节的"S10 发现"一组里。

## 最近完成会话：S9（2026-10-15）

Claude Code 担任编排者，全部实现来自 grok 工作包。用户的指示是"现在是不是可以进入S9了"。开工前问了 LLM 密钥怎么给工作包，用户选了"给需要的包，加调用上限"，之后告知"密钥已经设好了"。会话分支 `session/s09` 从 `s08-done-r2`（804ec1c）建立；起点独立复跑 613 passed / 3 skipped，GATES PASS 8/8。

四个包全部合并。真实调用的录制、LLM 全关的 3 小时长跑由编排者自己做。收尾合并回 main，tag `s09-done`。用户验收后另打 `s09-done-r2`（只多了验收记录，代码与门槛相同）；S10 从 `s09-done-r2` 起。

**用户验收（2026-10-15）：** 用户的答复是"全部没有问题，一切都按照你的建议"。收尾消息里的五项人工检查都按编排者的建议定下，逐项见 DECISIONS 的 S9 验收一条：
- 两个角色都用 fast 档；S11 做模型强度比较之前，先在 `roles/transport.py` 加每个请求的总时限；
- 真实回复的缓存留在 `gates/s09_llm/` 入库；
- S8 长跑按重跑的产物重钉；旧长跑 `results/s08/longrun-s8code` 不入库，备份由用户自己做；
- S10 把短跑里"从 DF-A 走到 INTERSECT ALL"当 M3 的起点参考，"复现 DF-B"要经身份裁判核对；
- S10 照用 `spawn --llm-key N`，只给要录真实调用的包。

下面"PI 已自行核查并定下的选择"八条也随之由用户确认。

### 交付与门槛

LLM 角色全部在新目录 `surprise/roles/` 里。`hunter/hunter.py` 与 `experiments/loop.py` 只加了接线，角色由开关接入，全关时与 S8 逐行相同。`diagnoser/`、`harness/`、`features/`、`theory/` 与冻结清单都没有动。

- **网关**（`roles/gateway.py`、`cache.py`、`schema.py`、`transport.py`、`constants.py`）：
  - 响应缓存：键是 `sha256(提示的 sha256 + 模型 + 种子)`。命中时不联网；条目里存着提示哈希，对不上的条目拒收。
  - 回复必须是带 `prediction` 字段的 JSON 对象，否则拒收。拒收也进缓存，重放时仍是拒收。
  - 按角色记账：调用、联网、缓存、通过、拒收、被上限挡下、缓存缺失、出错，以及输入输出 token。每次调用在 run 目录的 `llm/calls.jsonl` 写一行。
  - 上限：每个网关实例默认最多 200 次联网调用。环境变量 `SURPRISE_LLM_MAX_CALLS` 只能把它调低。出错的调用也计数，不进缓存。
  - 两档模型：`fast = deepseek-flash`，`strong = deepseek-v4-pro`。
  - `DeepSeekTransport` 继承旧的 `agents/base_agent.BaseAgent`，每次调用也记进旧的 `llm/ledger`。只有真要联网时才构造它。
- **读源码工具**（`roles/source.py`）：只读，限定在根目录之内。`open_sources()` 核对仓库根 `.src/` 下两份检出的提交号：DuckDB v1.5.5 是 d8cdaa33，DataFusion 54.0.0 是 45d943df。
- **实现器**（`roles/implementer.py`）：
  - 把规格写成 setup、query、predicate 三项的 JSON。
  - 提取 φ，用 `check_spec` 核对。不满足时，带上缺了哪些特征、多了哪些特征重试一次。
  - 命令行 `--specs` 给出 φ 核对报告。
- **猜想者**（`roles/conjecturer.py`）：
  - 新家族开出时调用一次。
  - 提示里有：用例、最小化用例、fix set、计划差异、φ、源码片段、只许用的词表。源码片段按 `roles/sources_map.py` 选，最多 4 个文件、400 行。
  - 回复要给出机制、触发条件（用词表里的特征）和 1–5 条预测，其中至少一条 fail、一条 pass。
  - 登记进猜想簿 `llm/conjectures.jsonl`。状态为 open 的预测就是待检实验。
  - 同时经 `wb.propose` 提一条 `revise`，押注就是这些预测。
  - 之后的实验落进某条预测的规格时兑现，记为 kept 或 broken。
- **接线**：
  - `roles/runtime.py` 提供 `RoleSet`、`ImplementerSource` 与 `build_roles`。
  - Hunter 加了 `sources` 钩子。实现器经它给 Hunter 两条新车道的候选：`bet` 来自猜想的待检预测，`implement` 来自假设边界上的规格。
  - 主循环加了 `llm` 参数与 `--llm*` 开关。
  - progress 每行多一个 `llm` 摘要。摘要里不放耗时与 token，这样重放才能逐行相同。

门槛 `gates/s09.py` 共十二组：

- 九组用脚本回复或不调用：`isolation`、`constants`、`cache`、`reject`、`cap`、`source`、`implementer`、`conjecturer`、`wiring`。
- 三组重放编排者录下的真实回复：`implementer_report`、`dfa`、`replay`。
  - 回复缓存提交在 `gates/s09_llm/`，里面只有提示与回复，没有密钥。
  - 整个门槛不联网。

与 SESSIONS 的对应：

| SESSIONS 的要求 | 门槛组 |
|---|---|
| 缓存命中时零网络调用、重放结果一致 | `cache`、`replay`（开着角色的 21 条短跑逐行重放） |
| 缺预测的输出被拒收 | `reject` |
| 实现器 SQL 的 φ 核对通过率报告 | `implementer`（脚本回复）、`implementer_report`（真实回复，只报告、不设线） |
| 猜想者在 DF-A 上给出带预测的假设并登记为待检实验 | `conjecturer`（脚本回复）、`dfa`（真实回复） |
| 按角色记账、调用上限、两档模型 | `cache`、`cap`、`constants` |
| 读源码工具与源码检出 | `source` |
| （S8 验收定下）LLM 全关时与 S8 相同 | `wiring`、`isolation`，以及 S8 门槛重钉的 `longrun` |

最终复跑（四包合并、录制与长跑重钉之后，在 `session/s09` 主检出区独立运行，在 `framework/` 下，去掉密钥）：

| 命令 | 结果 |
|---|---|
| `../.venv/Scripts/python.exe -m pytest -q testing tests` | 692 passed, 3 skipped，退出码 0（起点 613，新增 79，skip 未增加） |
| `../.venv/Scripts/python.exe -m surprise.gates.all` | S05 9/9、S06 12/12、S07 15/15、S08 11/11、S09 12/12；S01–S04 PASS（输出只留了末 80 行，前四个门槛的组数没有留下）；GATES: PASS (9/9 passed)，退出码 0 |

### 实机运行的数字

**真实调用**：全部在 fast 档（`deepseek-flash`）。

| 谁 | 次数 | 用途 |
|---|---|---|
| 执行者 | 80 | `s09-roles` 首轮 48 次、返工 32 次，确认提示与上限在真模型上有效 |
| 编排者 | 57 | 录制：实现器报告 31 次，DF-A 猜想 1 次，短跑 25 次 |
| 编排者 | 几次 | 冒烟测试；strong 档的排队探测 |

**实现器的 φ 核对**（`gates/s09_llm/implementer/report.json`；30 条规格，十个家族各三条）
- 首次通过 29/30（0.97），重试之后 30/30。
- 按类别（首次 → 最终）：整个 S 9 → 10；特征核心 10 → 10；边界（核心去掉一个字面量当禁止项）10 → 10。
- 31 次调用，其中 1 次回复被拒收。输入 19,599 token，输出 52,933 token。

**DF-A 的猜想**（`gates/s09_llm/dfa/conjecture.json`）
- 结果：登记成功。选的源码是 `datafusion/expr/src/logical_plan/builder.rs` 第 1332–1422 行。
- 机制：`LogicalPlanBuilder::intersect_or_except` 把 EXCEPT ALL 实现成带 NullEqualsNull 的 LeftAnti 连接，于是只要右侧有匹配，左侧的行就全部删掉，而不是按重复次数逐个抵消。
- 触发条件：`ast:set_op:except_all`、`ast:stmt:select`、`data:setop:left_has_dups`。
- 4 条预测（fail、pass、fail、pass）。随之提的 `revise`（e1）被接受。

**开着角色的 DataFusion 短跑**（`gates/s09_llm/loop/`；产物在 `results/s09/loop_llm`，不入库）
- 设置：种子 0；cross_dbms、tlp、norec 三类 oracle；从 DF-A 引导。
- 规模：20 次选择、21 条实验，446 秒。联网 25 次：猜想者 3 次，实现器 22 次。
- 车道：引导 1、implement 7、bet 5、generalize 5、refine 3。标签：fail 4、pass 17。
- 实现器：20 次尝试，18 次首次就满足规格，2 次 `spec_unmet`。
- 猜想：3 条，共 12 条预测。kept 6、broken 2，4 条仍是 open。
- 编辑：报告里接受 1、拒绝 1、回滚 1。最后留在理论里的猜想者提议只有 h5（下面第一点）。
- **从 DF-A 走到了 INTERSECT ALL**：
  - 第 10 条开出新家族。对它的猜想 c2 有一条预测："左侧有重复的 INTERSECT ALL 会失败"。
  - 第 13 条就是这条预测的 bet 车道实验。它判 fail（只多行），开了新假设。
  - 对它的猜想 c3 说：INTERSECT ALL 被降成 LeftSemi 哈希连接，保留了左侧全部的重复行。这与 `datafusion/DF-B_intersect_all.sql` 的描述一致。
  - c3 的 `revise`（e3）被接受，S 缩到 3 个字面量（h5）。
  - 它是不是 DF-B 没有经身份裁判核对，只是编排者的判读。S10 的 M3 门槛是"从 DF-A 出发闭环复现 DF-B"，这次短跑可以当参考。
- **被证伪的预测**：c1 预测"左侧有重复、两侧都没有 NULL 的 EXCEPT ALL 会失败"，第 4 条实验却通过了（`unexpected_pass`）。之后 DF-A 的两个假设（h1、h3）的 S 都带着 NULL 的特征。
- DF-A 开了两个家族：h1 来自引导，h3 来自第 10 条。第 10 条的失败没有右侧 NULL，落在 h1 的 G 之外，按 S6 的规则另开了一个身份相同的家族（见 S6 发现"身份一致但落在 G 之外"）。

**LLM 全关的 3 小时长跑（重跑）**（`results/s08/longrun`；S8 代码跑出的那份挪到 `results/s08/longrun-s8code`，两份都不入库）

| | S8 代码 | S9 代码（角色全关） |
|---|---|---|
| 实验 | 8900 | 9388 |
| fail / pass / invalid | 89 / 4197 / 4614 | 106 / 4438 / 4844 |
| 车道（探索 / 泛化 / 细化） | 8804 / 60 / 36 | 9279 / 68 / 41 |
| 假设 / 家族 / 不同身份 | 26 / 12 / 6 | 30 / 15 / 7 |
| 重复率（旧系统 0.818） | 0.500 | 0.533 |
| 窗口与齿 | 89 个窗口，齿在 3、9、17、40 | 93 个窗口，齿在 3、9、17、43 |

- 两份都是 0 条 harness_error。
- 去掉 `elapsed_s` 后，前 2936 行逐行相同。
- 第 2937 行是同一条 plan variant 用例：S8 那次判 `invalid / unstable_rerun`，这次判 pass。这是 harness 第 1 档的重跑不稳定，不是代码差异。之后的选择链就分开了。
- 这次是单独跑的；S8 时与旧系统基线、召回 run 三个并行。所以这次吞吐更高、条数更多。

### 拆包清单与结论（全部已合并）

| 包 | 内容 | 轮数 | 合并 | 审查 |
|---|---|---|---|---|
| s09-gateway | 网关、缓存、账本、上限、两档模型、DeepSeek 传输、读源码工具 | 返工 1 轮：模型改名（编排者没在派发前核对） | fad16c2 | 独立复跑 635 passed / 3 skipped；约 1.05 美元 |
| s09-wire | Hunter 的 `sources` 钩子；主循环的 `llm` 参数与 `--llm*` 开关 | 首轮通过 | 8b7541e | 独立复跑 668 passed / 3 skipped，全关 40 行与 S8 相同；约 1.28 美元 |
| s09-roles | 实现器、猜想者、猜想簿、选源、`RoleSet`、`ImplementerSource` | 返工 1 轮：五处，见 DECISIONS | 4c5f31b | 真实调用 80 次（`--llm-key 60`，返工 40）；约 5.65 美元 |
| s09-testfix | 一条测试不再依赖执行次序 | 首轮通过 | 9069083 | 合并后 692 passed / 3 skipped；约 0.13 美元 |

- 说明、报告、审查包归档在 `docs/orch/s09/`。
- grok 成本合计约 8.11 美元。
- 第四个包是计划外的：两个包并行开发时各自都绿，合并之后一条测试才因为执行次序失败。

### 当前接口

命令（在 `framework/` 下）：

- `python -m surprise.experiments.loop … [--llm implementer] [--llm conjecturer] [--llm-cache 目录] [--llm-max-calls N] [--llm-offline]`
  - 不带 `--llm` 时与 S8 相同，不导入任何角色模块。
  - 带 `--llm` 必须给 `--llm-cache`。
  - 联网要 `DEEPSEEK_API_KEY`。`--llm-offline` 只从缓存回答，缓存缺失记为 `miss`。
  - 其余参数同 S8。
- `python -m surprise.roles.implementer --specs <JSON：[{id, spec}]> --cache <目录> --out <报告> [--seed N] [--max-calls N] [--offline]`
  - 会打出一条 runpy 的 RuntimeWarning，无害。

run 目录在 S8 之外多了 `llm/`：
- `calls.jsonl`：每次调用一行，有角色、档、模型、键、提示哈希、状态、来源、token、耗时。
- `conjectures.jsonl`：猜想簿，包括 conjecture 行与 settle 行。
- `implementer.jsonl`：实现器的每次尝试。
- 此外，`config.json` 与 manifest 多了 `llm` 一节，`report.json` 多了 `llm` 摘要。

Python 接口（`surprise.roles`）：
- `Gateway(*, cache_dir, ledger_path=None, max_calls=None, transport=None)`：
  - `.call(role, prompt, *, tier, seed, temperature=0.0, max_tokens=4000) -> Reply`
  - `.totals()`、`.manifest()`、`.network_calls`
- `Implementer(*, gateway, extract, registry=None, seed, tier=None, attempts=None)`：`.implement(spec) -> Attempt`。另有 `implementer_report(specs, implementer)`。
- `Conjecturer(*, gateway, extract, book, registry=None, sources=None, seed, tier=None)`：`.after(wb, record, outcome) -> Conjecture | None`。
- `ConjectureBook(path)`：`.pending()`、`.observe(phi, label, record_id)`、`.summary()`。
- `select_sources(engine, hypothesis, phi, readers)`；`open_sources()`；`SourceReader`。
- `build_roles(config, *, run_dir, extract, registry, engines, seed) -> RoleSet`：
  - `config` 是 `{"roles", "cache", "max_calls", "network"}`；测试可以多传一个 `transport`。
- `Hunter(…, sources=())`：每个来源要有 `.candidates(wb, *, index, round)`，返回 `Candidate` 列表。

S10 的四个角色接进来的位置：
- 每个角色照 `roles/` 的写法，经同一个网关。
- 由 `build_roles` 的 `roles` 列表加开关。
- 需要给 Hunter 候选的，走 `sources` 钩子；需要提编辑的，走 `wb.propose`。

### PI 已自行核查并定下的选择（用户已验收）

**用户验收（2026-10-15）：下面八条，用户答复"全部没有问题，一切都按照你的建议"。** 它们从此是用户确认过的决定。

1. **模型名**：两档改为 `deepseek-flash` / `deepseek-v4-pro`。开工时定的 `deepseek-chat` / `deepseek-reasoner` 不在 DeepSeek 的 `/models` 列表里。
2. **猜想者默认用 fast 档**：
   - strong 档第一次冒烟时排队了 900 秒；录制前再试，1.8 秒就开始输出。
   - 但传输没有每个请求的总时限，长跑里一次卡住就会拖住整个循环。提示也是在 flash 上调出来的。
   - strong 档保留，供 S11 做模型强度消融。
3. **token 上限**：实现器 8000、猜想者 16000。`deepseek-flash` 把推理 token 算进 `max_tokens`，2000 时有 5/30 条规格在写出 JSON 之前就用完了。
4. **门槛 `F7/boundary` 的规格改了**：原题"有 date_arith、无 interval"按词表定义做不到，是编排者出题的错。没有放宽任何检查。
5. **"全关时与 S8 相同"的落地办法**：
   - 门槛：同种子 40 条短跑，去掉耗时字段之后的哈希等于 S8 长跑的前 40 行，且进程里没有加载任何 `surprise.roles` 模块。
   - 长跑：重跑一次再重钉哈希（S8 验收定下的办法），单独跑。
6. **实现器的规格不放 plan 层字面量**：实现器写的是 SQL，挑不了计划。φ 核对报告只报告，不设线。
7. **"登记为待检实验"落成两件事**：猜想簿里状态为 open 的预测，加上 `revise` 编辑的押注。编辑被不被接受由 S7 的规则定，门槛不要求接受。
8. **真实回复录一次、提交入库**（`gates/s09_llm/`，57 个缓存文件，共 344 KB）。门槛从缓存重放，不联网。缓存里只有提示与回复；提交前查过，没有密钥。

### 与计划的偏差

- 拆了四个包，比开工时定的三个多一个修复包 `s09-testfix`。
- 门槛 `gates/s09_cases.py` 在派发后改了三次，期望都没有放宽：
  - a2c5cc7：模型名；
  - cbe2773：猜想者改用 fast 档；
  - 04c0da9：token 上限与 F7 边界规格。
  - 录制的回复（4e696af、0fb197c）是门槛事先说好要补的数据，不算改门槛。
- PLAN 决策 10 写的是"至少两档"，网关照做了。但两个角色实际都用 fast 档，strong 档在本会话只在冒烟与探测里用过。
- 执行者拿到了真实密钥（用户的决定）。各轮都没有超过上限；日志与 worktree 里都扫过，没有密钥。
- 重跑的长跑数字与 S8 不同（见上），原因是 harness 的不稳定与单独运行，不是接线。S8 门槛的 `longrun`、`sawtooth`、`duplicates`、`recall` 四组对新产物通过。
- 没有改冻结区、S6 / S7 的规则与 S8 门槛的检查逻辑；LLM 没有打任何标签。

S9 留下的未决问题在文末"未决问题"一节的"S9 发现"一组里。

## 最近完成会话：S8（2026-10-15）

Claude Code 担任编排者，全部实现来自 grok 工作包。用户的指示是"确认S7中的新常数和编排规则，然后开始S8"。会话分支 `session/s08` 从 `s07-done-r2`（f762a66）建立；PG 服务器原先停着，按 S3 一节的命令启动（没有重新 initdb）。起点独立复跑：550 passed, 3 skipped；GATES PASS 7/7。四个包全部合并，长跑等产物由编排者自己跑；收尾合并回 main，tag `s08-done`。用户验收后另打 `s08-done-r2`（只多了验收记录，代码与门槛相同）；S9 从 `s08-done-r2` 起。

**用户验收（2026-10-15）：** 用户的答复是"全部按照你建议的确认"。收尾消息里的五项人工检查都按编排者的建议定下，逐项见 DECISIONS 的 S8 验收一条：门槛的修正（798c7c4）保留；`window_self_join` 维持现状（不对外报告、不加进已知集）；β = 1.0；S9 改到 S8 长跑绑定的代码时的处理办法（S9 已按它重跑长跑，见 S9 一节）；产物不入库、由用户自行备份。

**用户在开工后确认的三件事（2026-10-15）：** 用户答复"由你定、可以推翻的几件事都确认"。三件事是：重复率用同一个身份裁判、按同样的墙钟预算比；β 预实验的方案；误吸收的规则不改。

### 交付与门槛

无 LLM 的闭环，全部在 `framework/surprise/` 的新目录里；`harness/`、`features/`、冻结清单没有动，S6 / S7 的规则没有动。

- **Hunter**（`hunter/`）：
  - 四条车道的候选：细化、泛化、迁移、探索。
  - 打分 `value = P_valid × (D + β·U)`。
  - 每第 5 次选择是探索保底位。
  - 按"负责预测的假设"做过的探针数降权。
  - 按 φ 做新颖性拒绝。
  - 一次选择最多重抽 20 轮。
  - 候选的 φ 由常驻子进程提取，限时 30 秒。
  - 常数 12 项，见 `hunter/constants.py`。
- **β**：`theory/constants.py` 加了 `BETA = 1.0`，进 `theory_manifest()`。
- **Diagnoser**（`diagnoser/`，无 LLM）：
  - 新家族开出、且第 3 档给出仍能复现的最小化用例时，提议一条 `revise`，把 S 换成原 S 与最小化用例 φ 的共同部分。
  - 每 100 条实验跑一次 `compress()`，并切一代。
- **主循环**（`experiments/loop.py`）：Hunter → `evaluate_final` → `Workbench.observe` → Diagnoser。产物见下面"当前接口"。
- **指标**（`metrics/`）：
  - 惊讶曲线与齿；
  - 家族身份与重复率；
  - 已知 bug 召回。
- **旧系统基线**（`baselines/old_no_llm.py`）：按墙钟跑旧 `main.py --mode no_llm`，到点强杀。

门槛 `gates/s08.py` 共十一组：

- 七组短跑与规则检查：`no_llm`、`constants`、`scoring`、`operators`、`candidates`、`lanes`、`determinism`。这些在门槛里现跑。
- 四组核对编排者跑出来的产物：`longrun`、`sawtooth`、`duplicates`、`recall`。
  - 产物不入库，哈希钉在 `gates/s08_runs.json`。
  - `longrun` 还核对 manifest 里的代码摘要等于当前代码；改了 `hunter/`、`diagnoser/`、`experiments/` 的任何一行，这组就要重跑长跑。

与 SESSIONS 的对应：

| SESSIONS 的要求 | 门槛组 |
|---|---|
| 数小时 run 不崩 | `longrun`，并逐行核对来源 |
| 惊讶曲线呈锯齿 | `sawtooth` |
| 同执行预算下重复率低于旧 no_llm | `duplicates` |
| DuckDB 1.1.3 上的召回报告 | `recall`（只报告，不设线） |
| 同种子重跑一致 | `determinism` |

最终复跑（四包合并、门槛修正之后，在 `session/s08` 主检出区独立运行，在 `framework/` 下）：

| 命令 | 结果 |
|---|---|
| `../.venv/Scripts/python.exe -m pytest -q testing tests` | 613 passed, 3 skipped，退出码 0（起点 550，新增 63，skip 未增加） |
| `../.venv/Scripts/python.exe -m surprise.gates.all` | S01 7/7、S02 5/5、S03 5/5、S04 9/9、S05 9/9、S06 12/12、S07 15/15、S08 11/11；GATES: PASS (8/8 passed)，退出码 0 |

### 实机运行的数字

产物在 `framework/results/s08/`（不入库）；第一次的三个运行作废，移到 `aborted-1/`，原因见下面"PI 已自行核查并定下的选择"第 3 条。

**β 预实验**
- 设置：DuckDB 1.5.5、七类 oracle、每次 300 条、种子 9001–9003。
- 不同身份的家族数：

  | β | 三个种子上的家族数 |
  |---|---|
  | 0.5 | 1, 3, 3 |
  | 1 | 3, 3, 3 |
  | 2 | 3, 3, 3 |
  | 4 | 3, 5, 1 |

- 四个 β 的中位数都是 3；1、2、4 的合计都是 9。按事先定的规则取较小的，β = 1.0。

**长跑**（`results/s08/longrun`，DuckDB 1.5.5、七类 oracle、种子 0、180 分钟，与基线和召回 run 同时跑）
- 以 `budget_minutes` 结束：8900 条实验，0 条 harness_error。
- 标签：fail 89、pass 4197、invalid 4614（52%）。
- 车道：探索 8804、泛化 60、细化 36、迁移 0。迁移只在两个引擎以上才有候选；短跑的 `lanes` 组在两个引擎上覆盖了它。
- 分诊：新家族 26、边界移动 162、重复 23、意外通过 2、无信息 4073。
- 理论：26 个假设，12 个家族，6 个不同身份。
- 编辑：Diagnoser 提了 2 条 `revise`，都因 `no_gain` 被拒，接受 0 条；MDL 的 `compress()` 没有接受任何编辑。
- φ 提取：调用 88 万次、缓存命中 98.5%，超时、重启、出错都是 0。
- 吞吐：每千条平均 0.73–1.66 秒一条，没有随长度变慢的趋势。
- 慢在第 3 档：最慢的五次崩溃 / 超时复核各用了 2–7 分钟，合计约 19 分钟。
- 存储体积：理论存储 152 MB（`journal.jsonl` 9.9 MB），账本 79 MB。

**锯齿**
- 89 个窗口，齿在第 3、9、17、40 窗口。
- 曲线前半段起伏，后 40 个窗口多在 0.01–0.05 比特。理论把常见的失败都预测到了；新的起伏来自偶尔开出的家族。

**重复率**（同一个身份裁判，各 180 分钟）

| 系统 | 报告 | 不同身份 | 重复率 |
|---|---|---|---|
| 新框架 | 12 个家族 | 6 | 0.500 |
| 旧系统 no_llm | 11 条 | 2 | 0.818 |

- 旧系统：872 轮；报告是 `deliminator,filter_pushdown` 6 条、`join_order` 5 条。
- 新框架的 6 条重复全来自没有 fix set 的家族：有 6 个家族的形状键都是 `wrong_result|-|both`，2 个是 `error_mismatch|InvalidInputException`。形状键很粗，这些家族之间是不是同一个缺陷，裁判分不出来，一律算重复，对新框架不利。
- 有 fix set 的家族没有重复，13 个跨 oracle 的 `deliminator,filter_pushdown` 假设被 S7 的规则归成了一个家族。

**召回**（`results/s08/recall113`，`.venvs/duckdb-1.1.3-full`，六类 oracle、不用 Version、种子 0、60 分钟）
- 已知集：M1 表里 DuckDB 的 9 条已知复现，在 1.1.3 上经 certify 判 fail 的有 6 条（F1、F7、F7_file、F9、F6、F6_predicate），属于 3 个身份。F2、F2_file 判 pass，F11 判 invalid。
- run：3395 条，以 `budget_minutes` 结束。
- 结果：召回 F1、F6、F6_predicate，第 35 条实验就开出了它们共同的家族；漏了 F7、F7_file（`common_subexpressions,expression_rewriter`）与 F9（`wrong_result|-|both`）。
- 按条算召回 0.5，按身份是 3 个里 1 个。
- 另开了已知表里没有的身份：`deliminator`、`filter_pushdown`、`join_order`、`statistics_propagation`、`unnest_rewriter` 各一，`InternalException` 崩溃两个。

**新发现的缺陷候选：DuckDB 1.5.5 的 `window_self_join`**
- 长跑第 874 条开出，fix set 是 `window_self_join`；plan variant、Version、Cross 三个 oracle 都见证，归成一个家族。
- 复现：

  ```sql
  CREATE TABLE src(a INTEGER, b INTEGER, v INTEGER);
  INSERT INTO src VALUES (1, 1, 10), (1, 2, 20);
  SELECT SUM(v) OVER (PARTITION BY a, b) AS w_ab, SUM(v) OVER (PARTITION BY a, a) AS w_aa FROM src ORDER BY b;
  ```

- 默认设置返回 (10, 10)、(20, 20)；`SET disabled_optimizers='window_self_join'` 之后是正确的 (10, 30)、(20, 30)。编排者在主环境里直接复现过。
- 没有对外报告。用户验收时确认维持现状：不对外报告，也不加进已知集。

**误吸收**（规则没有改）
- 长跑里 85 条进了假设正例的失败中，3 条同时是两个假设的正例：h23 与 h25，都是 cross_dbms、都没有 fix set、形状相同。
- 有 fix set 的失败被无开关假设顺带吸收：0 条。

### 拆包清单与结论（全部已合并）

| 包 | 内容 | 轮数 | 合并 | 审查 |
|---|---|---|---|---|
| s08-hunter | Hunter 的打分、车道、候选、选择、常驻 φ 提取；`BETA` | 返工 1 轮，三处都是编排者的错（见 DECISIONS） | 6bd08d9 | 独立复跑 575 passed / 3 skipped；引导 F1、DF-A 后真实执行 25 次选择核对车道与保底；约 2.83 美元（两轮） |
| s08-eval | 曲线与齿、身份与重复率、召回、旧系统基线 | 首轮通过 | 8a60a37 | 独立复跑 572 passed / 3 skipped；用派发前的旧系统探测与原型 run 核对；约 1.40 美元 |
| s08-loop | 无 LLM 的 Diagnoser 与主循环命令行 | 首轮通过 | fc17952 | 独立复跑 610 passed / 3 skipped，短跑六组 6/6，同种子两个进程 26 行逐行相同；约 1.68 美元 |
| s08-resample | 一次选择最多重抽 20 轮；探索不再抽 setup 坏过的种子 | 首轮通过 | 287683a | 独立复跑 613 passed / 3 skipped，短跑七组 7/7；约 1.06 美元 |

说明、报告、审查包归档在 `docs/orch/s08/`。grok 成本合计约 6.97 美元。第四个包是计划外的：第一次召回 run 暴露了"一轮抽空就停"的语义错误。

### 当前接口

命令（在 `framework/` 下；跑长任务时去掉密钥：`env -u DEEPSEEK_API_KEY`）：

- `python -m surprise.experiments.loop --out <空目录> --seed N [--engine E]... [--oracle O]... [--max-experiments N] [--max-minutes M] [--beta B] [--bootstrap 文件] [--run-id ID]`
  - 不支持续跑，输出目录必须为空。
  - 默认引擎是 duckdb，默认七类 oracle。
  - 在 DuckDB 1.1.3 上跑，换成 `.venvs/duckdb-1.1.3-full` 的解释器，并且不传 `version_differential`。
- `python -m surprise.baselines.old_no_llm --out <目录> --minutes M --seed N`：写 `old_run.json`，旧系统的 run 目录在它的 `run_dir` 里。
- `python -m surprise.metrics.dups --new <run 目录> --old <基线目录>`
- `python -m surprise.metrics.recall known --cases <cases.json> --out <known.json>`：要用目标引擎版本的解释器跑。
- `python -m surprise.metrics.recall score --known <known.json> --run <run 目录> --out <recall.json>`

run 目录：
- `config.json`；
- `ledger.sqlite`：一个 run，manifest 带 `hunter` 一节，有常数、β、引擎、oracle、种子、代码摘要；
- `theory/`：S7 的存储；
- `progress.jsonl`：每次实验一行，键见 `experiments/loop.py`，包括车道、父本、目标规格、预测区、D / U / value、选择计数 `pool`（含 `rounds`）、分诊、编辑；
- `report.json`：
  - 状态：`budget_experiments` / `budget_minutes` / `exhausted` / `interrupted` / `error`；
  - 标签、车道、分诊；
  - 曲线与齿；
  - 家族数、φ 提取统计。

Python 接口：
- `surprise.hunter`：`Hunter(*, engines, oracles, seed, beta=None, corpus_path=None, extractor=None)`，方法有 `.candidates(wb)`、`.choose(wb) -> Choice | None`、`.record(record, *, rule=None, prediction=None)`、`.phi(case)`、`.manifest()`、`.close()`；另有 `Candidate`、`Scored`、`Choice`、`LANES`、`PhiExtractor`、`scoring`、`operators`、`constants`。
- `surprise.diagnoser.Diagnoser(*, phi, registry)`：`.after(wb, record, outcome)` 与 `.periodic(wb, done)`，两者都返回工作台记下的编辑（含被拒的）。
- `surprise.metrics.curve`：`surprise_curve`、`teeth`。
- `surprise.metrics.dups`：`identity_key`、`new_families`、`old_reports`、`duplicate_rate`。
- `surprise.metrics.recall`：`score`。

S9 的 LLM 角色接进来的位置：
- 猜想者与 Diagnoser 并列，在 `loop._drive` 里新家族开出之后调用，提议照样走 `wb.propose`。
- 实现器给 Hunter 加候选来源，产出照样是 `Candidate`，带目标规格，用 `check_spec` 核对。

### PI 已自行核查并定下的选择（用户已验收）

**用户验收（2026-10-15）：下面五条，用户答复"全部按照你建议的确认"。** 它们从此是用户确认过的决定，不再是"编排者定、可推翻"。开工时的三件事也已由用户确认（见本节开头）。下面五条是编排者当时没有先问就定下的。

1. **长跑跑完之后改了门槛的两处逐行检查**（798c7c4）。两处都是门槛比说明里定的规则严，长跑 8900 行里各碰到 1 行：
   - 细化 / 泛化：说明定的是"变异体落在**生成它的假设**的待定区"（`candidates` 组也是这么查的），逐行检查却查了整个理论预测的区。两个假设重叠时，理论会把变异体归给另一个假设的确认区。改为只多放行这一种情形：预测的假设不是生成它的假设，且目标规格的 forbidden 非空，也就是不在生成它的假设的确认区里。第 6927、7455 行属于这种情形。
   - 保底位：说明定的是"保底位上没有探索候选留下时在全部候选里选"，逐行检查却要求保底位一定是探索车道。改为要求最终的打分数不多于非探索候选的个数。这是选择计数能给出的必要条件。第 7455 行是这种情形：58 个探索候选全被拒，只剩一个泛化候选。
   - 其余条件都没有动，SESSIONS 的五项要求本身没有放宽。
2. **β = 1.0**：按预实验事先定的规则（中位数、合计、取小）选出，与暂定值相同。三组种子上差别很小，β 在 0.5–4 之间不敏感。
3. **第一次的三个运行作废、加派 `s08-resample`**：召回 run 7.7 分钟就以 `exhausted` 停了，"一轮抽空就当无可再测"是编排者说明里定错的语义。β 没有重做预实验，因为预实验的 12 次运行都以预算结束、没有遇到抽空，而且 PLAN 决策 8 说 β 只调一次。
4. **三个运行同时跑**，共用这台 16 核机器。新旧两边承受同样的负载、同样的 180 分钟墙钟，预算仍然可比；代价是绝对吞吐比单独跑低。
5. **召回的已知集**：取 M1 表里 DuckDB 的 9 条复现中在 1.1.3 上判 fail 的 6 条，按条计召回（0.5）。按身份计是 3 个里 1 个，两种数字都写进了报告。

### 与计划的偏差

- 拆了四个包，比开工时定的三个多一个修复包 `s08-resample`。
- 门槛 `gates/s08.py` 在派发后改了三次，都是编排者写门槛时的疏漏，期望没有放宽：
  - e2d9a5b：两行相同的用例；泛化判定写宽了；
  - 3110d6e：为修复包加常数与 `rounds` 键；
  - 798c7c4：上面第 1 条。
- "同执行预算"按墙钟时间落地：新框架每次判定起隔离进程，SQL 条数不可比。
- 召回 run 不用 Version differential，因为旧版就是被测引擎本身。
- 长跑只在 DuckDB 上跑，迁移车道在长跑里没有候选，由短跑在两个引擎上覆盖。
- 长跑里 Diagnoser 与 MDL 的编辑都没有被接受（召回 run 里接受 1 条）：闭环在规则层面是通的，"提议 → 接受"这一环在实机上几乎没有发生。
- 没有与 PLAN 冲突的实现选择；没有调用任何 LLM；没有改冻结区与 S6 / S7 的规则。

S8 留下的未决问题在文末"未决问题"一节的"S8 发现"一组里。

## 最近完成会话：S7（2026-10-09）

Claude Code 担任编排者，全部实现来自 grok 工作包。用户指示"继续完成 S7"。会话分支 `session/s07` 从 `s06-done-r2`（0361b75）建立；起点独立复跑 514 passed, 3 skipped 与 GATES PASS 6/6。两包全部合并，收尾合并回 main，tag `s07-done`。用户验收后另打 `s07-done-r2`（只多了验收记录，代码与门槛相同）；S8 从 `s07-done-r2` 起。

**用户验收（2026-10-15）：** 用户的答复是"确认S7中的新常数和编排规则，然后开始S8"。

### 交付与门槛

理论的存储与接受规则，全部在 `framework/surprise/theory/`，不连接引擎、不执行 SQL、不调用模型；`harness/`、`features/`、冻结清单没有动；S6 的规则与 `Theory` 的既有行为没有动。

- 常数四项（`theory/constants.py`，进 run manifest 的 `theory` 一节）：`MDL_HYPOTHESIS_BITS = 8.0`、`MDL_LITERAL_BITS = 7.4`、`ACCEPT_HOLDOUT_MAX = 1000`、`ACCEPT_TOLERANCE_BITS = 1e-9`。`gates/s07.py` 的 `constants` 组钉住取值：**此后改它们先问用户**。
- 存储（`theory/store.py`，`TheoryStore`）：一个目录，`hypotheses/<编号>.json` 每个假设一个文件，另有 `head.json`、`residual.json`、`validity.json`、`passes/<引擎>__<oracle>.jsonl`，三份只追加的日志 `journal.jsonl`（观察与事件）、`edits.jsonl`（编辑日志）、`negative.jsonl`（负记忆），`generations/g<六位代号>.json` 每个已结束的代一个快照。读盘严格：任何手改都会让版本号对不上，抛 `StoreError`，不"修好了再返回"。
- 编辑（`theory/edits.py`）：五类 `add / revise / split / merge / retire`；每条带理由与押注；提出者只定身份与 S，其余由证据重算；编辑加进来的假设一律铸新编号。
- 接受检验：触发记录上惊讶不升、留出记录上惊讶不升、（惊讶变化 + 长度变化）严格为负，三条同时成立才接受。
- 工作台（`theory/workbench.py`，`Workbench`）：在用的理论加存储。`observe` 记日志、兑付押注、必要时回滚、落盘；`propose` / `assess`；`rollback`（快照加重放，级联）；负记忆按断言的指纹拒收；`checkpoint` 切代；MDL 的 `merge_candidates` / `repair_candidates` / `compress`；`owner_of` / `family_of` / `families` / `partition`；`surprise_under(代号, 记录)`。
- `Theory` 加了 `next_id`、`remove`、`reserve_id`、`passes`；合取语言加了 `common_conjunction`；`theory/length.py` 给出描述长度。

门槛十五组与 SESSIONS 的对应：`replay` 把已知复现与重新生成的 DCE 探针在真实引擎上离线喂一遍，查五个量级、执行前识别重复、一条故意错误的编辑被回滚并进负记忆；`ledger` 拿同一次回放的家族划分与人工账本比，要求不低于 σ；其余十三组是不碰引擎的逐条规则检查（常数、长度、`Theory` 的补充、存储、快照、导入、编辑、接受、回滚、重开、MDL、家族、按代惊讶）。

最终复跑（两包合并后在 `session/s07` 主检出区独立运行，在 `framework/` 下）：

| 命令 | 结果 |
|---|---|
| `../.venv/Scripts/python.exe -m pytest -q testing tests` | 550 passed, 3 skipped，退出码 0（起点 514，新增 36，skip 未增加） |
| `../.venv/Scripts/python.exe -m surprise.gates.all` | S01 7/7、S02 5/5、S03 5/5、S04 9/9、S05 9/9、S06 12/12、S07 15/15；GATES: PASS (7/7 passed)，退出码 0 |

`gates/s07.py` 单独跑约 5 分钟（`replay` 约 4 分钟，`ledger` 约 1 分钟，其余十三组合计几秒）；`surprise.gates.all` 约 11 分钟。

### 实机回放的数字

回放的内容：人工账本明文裁定到某一族的 24 条语句（十族：F1、F2、F7、F9、F11、DF-A、DF-B、DF-D、DF-F、DF-I；清单与出处在 `gates/s07_cases.py`），每族第一条语句的 DCE 探针若干（共 38 条，`evolution/dce.py` 的算子重新生成、等距取样），每族第一条语句再喂一遍，外加一条故意错误的编辑及其押注实验。共 74 次实验，全部经 `evaluate_final` 入账。

| 位置与结果 | 条数 | 惊讶（比特） | 分诊 |
|---|---|---|---|
| 未探索区失败 | 4 | 6.64 | new_family |
| 确认区通过 | 5 | 4.32 | unexpected_pass |
| 待定区失败 | 13 | 1.00 | boundary_move |
| 确认区失败 | 48 | 0.07 | duplicate |
| 未探索区通过 | 1 | 0.01 | no_information |
| 无效 | 3 | 不计 | invalid |

- 每条记录的惊讶都能由账本里的 `p_t` 与标签重算出来（门槛逐条核对）。
- 执行前识别重复：十族的第一条语句再喂一遍，十次都在执行前落在确认区，执行后都只做了一次归属测试（第 2 档，没有最小化与画像）。全部 65 条失败里，11 条开出家族（各做一次第 3 档画像），54 条归入已有家族；这 54 条里 47 条执行前就被预测为重复，其余 7 条落在待定区（1 比特的边界移动）。
- 故意错误的编辑（在 DF-A 之后）：把 DF-A 的假设改写成"左输入有重复行就丢行"，S 从十个字面量变成一个。接受检验通过（惊讶不变，长度少 66.6 比特）。它押注"UNION ALL 且左侧有重复会失败"；真实执行 UNION ALL 通过（落在这条编辑的确认区，4.32 比特），押注落空，编辑回滚，理论回到编辑之前并学到这条通过；负记忆里多一条；原样再提被 `negative_memory` 拒收；同一条 UNION ALL 再喂一遍落在未探索区，0.01 比特。
- 回放结束时 11 个假设。`compress()` 没有应用任何编辑：两对合并候选（DF-A 与 `DF-D_where` 的假设、DF-D 与 DF-F 的假设）都因为并起来的 S 会盖住一条已知的通过而被留出记录拒掉；没有修复候选。

与人工账本比家族划分（24 条裁定语句，配对计数）：

| 划分 | 家族数 | 精确率 | 召回率 | 配对 F1 | ARI |
|---|---|---|---|---|---|
| 人工账本 | 10 | | | | |
| 新框架（执行前成员检验 + 版本空间） | 11 | 1.00 | 0.95 | 0.976 | 0.974 |
| σ（旧系统的家族键，由 CVE 画像按旧规则重算） | 19 | 1.00 | 0.29 | 0.444 | 0.425 |

新框架与账本唯一的出入：`DF-D_where`（`SELECT a FROM t WHERE b > 0`，只少行）被分到 DF-D（少行多行都有）之外，因为没有开关的身份按行为形状分。σ 没有把不同族并在一起，但把一族拆碎：F9 两个键（就是人工账本里的 AUTO-f50fc0f3 与 AUTO-13f4608a，重算出来逐位相同），DataFusion 上因为没有 fix set、没有计划差异、没有版本梯，键退化成"最小化用例的文本摘要"，每条语句一个键。代价的对比：σ 要给每一条失败做完整画像；新框架里 54 条重复有 47 条只做了一次归属测试。

合取可表达的比例（PLAN 第 7 节；本机能回放的只有这十族，不是三十一族）：十族里九族的假设没有落在 S 内的通过；F2 有四条（改一个数据值就不再出错的探针，φ 与正例相同），现有词表分不开，属于要靠 S10 发明新特征的情形。

误吸收（S6 留的未决问题，要求量一下）：门槛这次回放的 65 条失败里没有一条被两个假设同时吸收。派发前另一次范围更大的探测（含重建的 F6、每族 12 条探针，约 170 次实验）里出现过两类：F7 的两条探针失败在被归属测试判给 F7 的同时，也被没有 fix set 的 F9 假设按三项画像当成正例；DF-F 的首条失败落在 DF-D 假设的待定区、形状相同，被吸收进去，两族并成一个假设。后者只在该作用域还没有几条通过、G 还很松的时候发生；这次回放的喂入次序下 DF-D 的 G 已经被收紧，DF-F 开出了自己的家族。规则没有改，见未决问题。

### 拆包清单与结论（全部已合并）

| 包 | 内容 | 轮数 | 合并 | 审查 |
|---|---|---|---|---|
| s07-store | 四个常数、`Theory` 的四个接口、`common_conjunction`、长度、`TheoryStore` | 首轮通过，返工 0 轮 | 60563a1 | 独立复跑 528 passed / 3 skipped；与参考模型逐字节差分 23995 项零出入（含 360 次损坏注入）；19 条命令已看；约 1.84 美元。发现日志追加随长度线性变慢，写进下一个包顺带修 |
| s07-accept | 编辑、接受检验、工作台、回滚、负记忆、MDL、家族；日志序号缓存 | 首轮通过，返工 0 轮 | 8061cef | 独立复跑 550 passed / 3 skipped，GATES PASS 7/7；与参考模型在 300 段随机历史上逐步差分 29709 项零出入；真实引擎两组的数字与派发前逐项相同；15 条命令已看；约 1.93 美元 |

说明、报告、审查包归档在 `docs/orch/s07/`。没有返工，没有推翻包。grok 成本合计约 3.77 美元。两个包首轮都过，做法同 S6：派发前规则已经用参考模型在真实引擎上把门槛跑通，说明里把每一步都写了出来；审查的力气花在随机差分上。

### 当前接口

`surprise.theory` 新增导出（S8 直接用）：

- `TheoryStore.create(root)` / `.open(root)`：`root`、`last_seq`、`head()`、`save(theory)`、`load()`、`append_journal(entry)`、`journal(after=0)`、`append_edit(edit)`、`edit_history()`、`edits()`、`append_negative(entry)`、`negatives()`、`close_generation(theory, cause=...)`、`generations()`、`load_generation(n)`、`verify()`；`StoreError`。一个存储目录同一时间只由一个实例写。
- `Workbench.create(root)` / `.open(root)`：`store`、`theory`（当只读用）、`generation`、`predict(phi, oracle)`、`observe(phi, label, record_id, *, prediction=None) -> Outcome`、`assess(proposal) -> Assessment`、`propose(proposal) -> TheoryEdit`、`rollback(edit_id, *, reason="manual", record_id=None)`、`checkpoint(note)`、`records()`、`seen(record_id)`、`edits()`、`edit(edit_id)`、`negatives()`、`open_bets()`、`merge_candidates()`、`repair_candidates()`、`compress()`、`owner_of(record_id)`、`family_of(hypothesis_id)`、`families()`、`partition()`、`surprise_under(generation, record_ids)`。
- `Outcome`：`observation`（S6 的 `Observation`）、`seq`、`owner`、`bets`、`rolled_back`。
- `Proposal(kind, rationale, proposer, removes=(), adds=(), bets=(), trigger=())`；`Seen(record_id, phi, label)`；`Assessment`；`EDIT_KINDS`、`REJECT_REASONS`、`ROLLBACK_REASONS`、`BET_STATES`；`claim`、`fingerprint`、`default_bets`、`bet_matches`、`holdout_sample`。
- `Theory.next_id`、`.remove(id)`、`.reserve_id()`、`.passes(engine, oracle)`；`common_conjunction(a, b)`；`hypothesis_length(h)`、`theory_length(theory 或一串假设)`。

一次实验在 S8 主循环里的顺序（门槛的 `replay` 组就是这么写的，比 S6 只多了把 `Theory` 换成 `Workbench`）：`phi = extract(case)` → `prediction = wb.predict(phi, oracle)` → `evaluate_final(case, oracle, ..., phi=phi.to_dict(), theory_version=wb.theory.version, p_t=prediction.p_fail_valid, hypothesis=attribution_request(wb.theory.get(prediction.hypothesis_id)))`（未探索区没有假设时改传 `diagnose=True`）→ `outcome = wb.observe(phi, record.label, record.record_id, prediction=prediction)`。`outcome.rolled_back` 非空说明这条记录让某条编辑的押注落空了，理论已经回到那条编辑之前并重放过。

编辑日志里一条记录（`TheoryEdit`）的 `payload`：`reason`、`fingerprint`、`trigger`、`holdout`、`length_delta`、`removes`、`removed`、`adds`、`added`、`generation`、`journal_seq`、`bets_state`、`rollback`。日志条目：`observe`（`record_id`、`phi`、去掉 `detail` 的 `label`）、`edit`、`rollback`（`reason`、`cascade`）、`checkpoint`。

### 规则（实现与门槛都按它；逐条细则在 `docs/orch/s07/` 归档的两份任务说明里）

框架文档的相关原文："理论的每次修改都写明理由和预测；预测落空的编辑自动回滚，并作为负面记忆留下，防止同一个错误猜想反复出现"；"新特征、拆分与合并必须在触发记录上降低惊讶，在留出记录上不增加惊讶"；"理论修改的目标：最小化'累计惊讶 + 理论长度'（MDL），作为假设拆分和合并的判据"；"通过的结果、退役的假设、被拒绝的提议都保留为负记忆"。

- **两种变化**：规则更新（`Theory.observe` 按 S6 的规则动 S、G、开新家族、记 R 与 Kᵛ）不是编辑，不走接受检验，留痕在观察日志；编辑是别人提出的改动，写进编辑日志。
- **编辑加进来的假设**：身份与 S 取提出者给的模板，编号新铸，G 从空合取起把该作用域记住的通过逐条回放（落在 S 里的成为矛盾），E⁺ 取被替换的假设的正例里仍落在新 S 内的（`add` 取同作用域里身份一致且落在 S 内的失败）。
- **接受检验**，依次：指纹在负记忆里，拒（`negative_memory`）；没有押注，拒（`no_bets`）；触发记录上惊讶之和升了，拒（`trigger`，进负记忆）；留出记录上升了，拒（`holdout`，进负记忆）；三项之和不是严格为负，拒（`no_gain`）；否则接受。惊讶是用现在的理论看旧记录；留出记录是编辑涉及的作用域里、触发记录之外的全部有效记录，超过 1000 条按记录编号的哈希取 1000 条。
- **长度**：每个假设 `8.0 + 7.4 × |S|` 比特；G 与证据不计。
- **押注**：`{"spec": 规格, "expect": "pass" | "fail"}`。第一条命中规格、标签有效的实验兑付它：标签等于期望为兑现，否则落空。只看标签，不看身份。
- **回滚**：先把当前理论封存成一代；取这条编辑之前封存的快照，编号计数器沿用现在的；把这条编辑之后的全部观察按原次序重放（重新预测）；之后接受的编辑一并撤销（`cascade`，不进负记忆）；这条编辑进负记忆（`bet_broken` 或 `manual`）。
- **负记忆的指纹**：只看加进来的各假设的（引擎、oracle、fix set、失败类别、错误类别、行为形状、约简后的 S）；退役按被撤回的断言算。编辑类型、提出者、编号、G、证据都不进指纹。
- **代**：接受编辑、回滚、检查点各结束一代；快照存一代结束时的理论。
- **MDL 候选**（接受与否都走同一个检验，押注用默认的"落在新 S 里的实验会失败"）：合并——同作用域、身份相同（都有 fix set 时只比 fix set；都没有时比三项画像）的一对，S 取两者的共同部分，为空不提；修复——假设的 `contradictions` 里有通过时，把正例按次序贪心分簇，使每簇的 S 不新盖住任何一条矛盾通过，一簇为收紧、多簇为拆分。`compress()` 反复应用第一条可接受的候选直到没有。
- **归属与家族**：一条失败属于把它列在 E⁺ 里的假设（多个时取归属测试点名的，否则最早的）；有 fix set 的假设按（引擎，fix set）跨 oracle 成一个家族，没有的一个假设一个家族。

### PI 已自行核查并定下的选择（用户已验收）

**用户验收（2026-10-15）：下面六条，用户答复"确认S7中的新常数和编排规则"。** 它们从此是用户确认过的决定，不再是"编排者定、可推翻"；四个新常数的取值照旧由门槛钉住，要改先问用户。

用户的指示是"继续完成 S7"；S6 交接里写着"S7 开工前要定的几件事"与新常数的取值，编排者没有另行提问，按推荐定下，依据是此前把确认事项交回编排者自行决定的约定。每一条都在 DECISIONS 里有理由。

1. **四个新常数的取值**。文档只说"最小化累计惊讶加理论长度"，没有给长度的单位与数值；8.0 与 7.4 比特是编排者定的（字面量按 167 项词表编码）。后果：一条矛盾通过（4.32 比特）付不起一个假设（15.4 比特）；收紧一个多写 8 个字面量的 S 要十四条以上的矛盾，拆出第二个十字面量的假设要三十五条以上；一条没有画像的失败付不起一个新假设，四条可以。嫌拆分太迟钝，调小 `MDL_LITERAL_BITS` 即可，门槛里相应的条数要跟着改。
2. **接受检验把文档的"在触发记录上降低惊讶"放宽成"不升"，再要求惊讶加长度严格变小**。否则合并（不降低任何已有记录的惊讶）与手写的 h2（DF-A 已经被规则解释成 0.07 比特）都过不了。
3. **押注只看标签、一次兑付**；全部兑现之后的编辑不再因为新的矛盾而回滚。
4. **回滚用"快照加重放"，并级联撤销之后接受的编辑**（后者不进负记忆）。
5. **家族的定义**：有 fix set 的按 fix set 跨 oracle 归并，没有的一个假设一个家族；与人工账本比划分时用 ARI 与配对 F1，真值只取账本明文裁定的 24 条语句，探针不计分，F6 不进真值表。
6. **`gates/s06.py` 改了一行**（新进程里打印整份常数名单而不是第一个），期望不变。

### 与计划的偏差

- ORCHESTRATION 第 8 节建议 S7 串行单包，实际拆成两个串行包（存储一包、接受规则一包）。
- SESSIONS 写"离线喂入已知复现与重新生成的 DCE 探针"：DCE 只用了它的两个探针生成函数（`mutate_query_text`、`mutate_setup`），由门槛调用；旧的 `FamilyExpander` 没有用（它自带判定与去重）。探针每族只取 2–6 条（等距取样），为的是把门槛控制在 5 分钟。
- PLAN 第 7 节"先测 31 个已确认家族中可用合取表达的比例"：只在本机能回放的十族上量了（九族可以，F2 不行）。其余家族不在首发引擎上，或在冻结的 harness 下不判 fail（见 S4 的召回缺口）。
- PLAN 总原则第 2 条写"惊讶公式、接受规则进 harness 并记录哈希"。harness 在 S4 已冻结，接受规则放在理论层（`theory/edits.py`、`theory/workbench.py`），它们的代码哈希由 `theory_manifest()` 记进 run manifest 的 `theory` 一节，做法与 S6 相同。
- 改了上一会话的门槛 `gates/s06.py` 一行（见上面第 6 条）。
- 没有与 PLAN 冲突的实现选择；没有做 Hunter、主循环、LLM 角色；没有改 S6 的规则。

S7 留下的未决问题在文末"未决问题"一节的"S7 发现"一组里。

## 最近完成会话：S6（2026-10-09）

Claude Code 担任编排者，全部实现来自 grok 工作包。用户指示"继续完成 S6"。会话分支 `session/s06` 从 `s05-done`（8c37d25）建立；起点独立复跑 367 passed, 3 skipped 与 GATES PASS 5/5。两包全部合并，收尾合并回 main，tag `s06-done`。用户验收后另打 `s06-done-r2`（只多了验收记录，代码与门槛相同）；S7 从 `s06-done-r2` 起。

### 交付与门槛

理论 T = (H, R, Kᵛ) 的核心，全部在 `framework/surprise/theory/`，不连接引擎、不执行 SQL；`harness/` 与冻结清单没有动。

- 常数九项（`theory/constants.py`）：`P_CONFIRMED = 0.95`、`P_PENDING = 0.5`、`RESIDUAL_PRIOR_FAILS = 1.0`、`RESIDUAL_PRIOR_TESTS = 100.0`、`VALIDITY_PRIOR_INVALID = 1.0`、`VALIDITY_PRIOR_TESTS = 10.0`、`TRIAGE_LOW_BITS = 0.5`、`TRIAGE_HIGH_BITS = 2.0`、`VS_MAX_GENERAL = 64`。`gates/s06.py` 的 `constants` 组钉住取值：**此后改它们先问用户**。
- 假设 h = (I, ΔP, V, S, G, E⁺, E⁻)：`Hypothesis` 契约加了六个带默认值的字段（`oracle`、`fail_kind`、`error_class`、`behavior_shape`、`contradictions`、`truncated`），S2 时期的对象与 dict 照样可用。
- 版本空间：S 是一个合取，G 是一组合取，字面量是词表里的叶子或类。正例泛化 S（删特征、同类不同值升到类），反例特化 G（取能排除反例的最一般的字面量，保留全部最小特化，去冗余，上限 64）。位置四种加"不在作用域"。
- 身份一致才算正例：harness 的归属测试结果优先，其次比 fix set，没有开关的比失败类别、错误类别、行为形状。
- 新家族的确定性初始化：I、ΔP、V 取自第 3 档画像；G 用此前同范围的通过回放收紧。
- R（每单元计数与未解释失败）、Kᵛ（按实验类与 oracle 的无效率）、P_T 与惊讶、六类分诊、`Theory.predict` / `Theory.observe`、状态往返与版本号。
- 常数进 run manifest：`extend_manifest()` 在 manifest 上加 `theory` 一节，`verify_theory_manifest()` 核对。

门槛十二组与 SESSIONS 的对应：`walkthrough` 在真实引擎上把框架文档的 DF-A → DF-B 案例走了一遍，用手写的 h2 代替 LLM——第一次失败 6.64 比特（"约 6.6"）；两个预测实验各 1.00 比特；`data:setop:left_has_dups` 进 G；INTERSECT ALL 的失败经归属测试判为身份不一致，对 h2 是反例，并开出新家族 h3。同一组里另有三步把分诊表其余几行也走到：DF-A 再来一次 0.07 比特（重复），左右重复数相同的 EXCEPT ALL 4.32 比特（意外通过），UNION ALL 0.01 比特（无信息）。其余十一组是不碰引擎的逐条规则检查。

最终复跑（两包合并后在 `session/s06` 主检出区独立运行，在 `framework/` 下）：

| 命令 | 结果 |
|---|---|
| `../.venv/Scripts/python.exe -m pytest -q testing tests` | 514 passed, 3 skipped，退出码 0（起点 367，新增 147，skip 未增加） |
| `../.venv/Scripts/python.exe -m surprise.gates.all` | S01 7/7、S02 5/5、S03 5/5、S04 9/9、S05 9/9、S06 12/12；GATES: PASS (6/6 passed)，退出码 0 |

`gates/s06.py` 单独跑约半分钟（`walkthrough` 约 20 秒，其余十一组不到 2 秒）；`surprise.gates.all` 约 6 分钟。

实机走查的数字（DataFusion 54.0.0，参照 DuckDB、PostgreSQL、SQLite）：

| 步 | 语句 | 预测时的位置 | 标签 | 惊讶（比特） | 分诊 | 理论的变化 |
|---|---|---|---|---|---|---|
| 1 | DF-A：`EXCEPT ALL`，左侧有重复行与 NULL | 未探索区（ρ = 0.01） | fail，第 3 档 | 6.64 | new_family | 开出 h1：S = φ 的十个叶子，G = 空合取，身份为"只少行" |
| 2 | （手写 h2 顶替 LLM：把 h1 的 S 换成 `ast:set_op:except_all` 与 `data:setop:left_has_dups`） | | | | | |
| 3 | 去掉左侧的重复行 | h1 的待定区 | pass | 1.00 | boundary_move | `data:setop:left_has_dups` 进 G |
| 4 | DF-B：换成 `INTERSECT ALL` | h1 的待定区 | fail；归属测试不一致，升第 3 档，"只多行" | 1.00 | boundary_move | 对 h1 是反例，G 收到与 S 相同；开出 h2，它的 G 被第 3 步的通过回放成三个候选 |
| 5 | DF-A 再来一次 | h1 的确认区 | fail，第 2 档归属一致 | 0.07 | duplicate | 记为 h1 的正例；对 h2 是反例，G 收到只剩 `ast:set_op:intersect_all` |
| 6 | 左右各两个 1 的 `EXCEPT ALL` | h1 的确认区 | pass | 4.32 | unexpected_pass | 记进 h1 的 `contradictions` |
| 7 | `UNION ALL` | 未探索区 | pass | 0.01 | no_information | 只有 R 的该单元加一 |

（表里的 h1、h2 是程序自动起的编号，对应框架文档里的 h2、h3。）不用手写的 S、只靠确定性规则时，第 3 步之后 G 是 `data:setop:left_has_dups` 与 `data:table:dup_rows` 两个候选（去掉左侧重复行同时也去掉了"表里有重复行"，规则分不出是哪一个），第 4 步之后两个候选各加上 `ast:set_op:except_all`；门槛两种走法都查。

### 拆包清单与结论（全部已合并）

| 包 | 内容 | 轮数 | 合并 | 审查 |
|---|---|---|---|---|
| s06-vspace | 常数、契约字段、合取语言、版本空间、建族、身份、归属请求 | 首轮通过，返工 0 轮 | cebb344 | 独立复跑 398 passed / 3 skipped；与参考模型差分 115002 项零出入；穷举核对 1655 个边界零出入；14 条命令已看；约 1.35 美元 |
| s06-theory | R、Kᵛ、预测与惊讶、分诊、`Theory`、manifest 一节、命令行 | 首轮通过，返工 0 轮 | 19686eb | 独立复跑 514 passed / 3 skipped，GATES PASS 6/6；与参考模型差分 63763 项零出入；不变量 14347 对零违反；13 条命令已看；约 1.81 美元 |

没有返工，没有推翻包。grok 成本合计约 3.16 美元。说明、报告、审查包归档在 `docs/orch/s06/`。两个包首轮都过，原因是派发前规则已经用参考模型跑通过门槛，说明里把每个函数的每一步都写了出来；审查的力气花在差分与不变量上，而不是等执行者猜规则。

### 当前接口

`surprise.theory` 导出（S7、S8 直接用）：

- `constants`（子模块，`as_dict()`）。
- 合取：`reduce_conjunction(ids, registry=None)`、`covers(conjunction, phi, registry=None) -> bool`、`generalize(specific, phi, registry=None)`、`specialize(general, specific, phi, registry=None)`。
- 假设：`Hypothesis`、`position(h, phi, oracle, registry=None)`（`confirmed` / `pending` / `outside` / `undetermined` / `out_of_scope`）、`apply_positive` 与 `apply_negative`（返回 `Update(hypothesis, outcome)`，outcome 为 `duplicate` / `generalized` / `specialized` / `contradiction` 或位置名）、`converged(h)`、`identity_match(h, label) -> True | False | None`、`new_family(hypothesis_id, phi, label, record_id, *, negatives=(), source="deterministic")`、`attribution_request(h) -> dict`（直接传给 `certify(..., hypothesis=...)`）。
- `Residual`（`observe(unit, y)`、`counts`、`rate`、`to_dict` / `from_dict`）；`Validity`（`observe(experiment_class, oracle, y, invalid_reason=None)`、`counts`、`reasons`、`rate`、`to_dict` / `from_dict`）；`experiment_class(phi)`。
- `Prediction`（`zone`、`hypothesis_id`、`confirmed`、`pending`、`unit`、`experiment_class`、`p_fail_valid`、`p_invalid`、`p_fail`、`p_pass`、`surprise(y)`、`to_dict()`）；`surprise_bits(p_fail_valid, y)`；`triage(y, bits)`；`ZONES`、`TRIAGE_KINDS`。
- `Theory(registry=None)`：`hypotheses`、`get`、`put`、`residual`、`validity`、`predict(phi, oracle)`、`observe(phi, label, record_id, *, prediction=None) -> Observation`、`to_dict()` / `Theory.from_dict()`、`version`。`Observation`：`prediction`、`y`、`surprise`、`triage`、`effects`、`opened`、`unexplained`。
- `theory_manifest()`、`extend_manifest(manifest)`、`verify_theory_manifest(manifest)`；命令行 `python -m surprise.theory {constants|manifest}`。

一次实验在 S8 主循环里的顺序（门槛的 `walkthrough` 组就是这么写的）：`phi = extract(case)` → `prediction = theory.predict(phi, oracle)` → `evaluate_final(case, oracle, ..., phi=phi.to_dict(), theory_version=theory.version, p_t=prediction.p_fail_valid, hypothesis=attribution_request(theory.get(prediction.hypothesis_id)))`（未探索区没有假设时改传 `diagnose=True`）→ `theory.observe(phi, record.label, record.record_id, prediction=prediction)`。

### 规则（实现与门槛都按它；逐条细则在 `docs/orch/s06/` 归档的两份任务说明里）

框架文档是《惊讶驱动的 CoevoDB：新框架与故事》（2026-10-07），仓库里没有，本机在 `C:\Users\91484\Desktop\` 下的同名 PDF。相关原文：`P_T(fail | x) = (1 − Kᵛ(x)) × [确认区约 0.95；待定区约 0.5；否则取 ρ_c]`；六类分诊表（未探索区失败约 6.6 比特、确认区通过约 4.3、待定区约 1.0、确认区失败约 0.07、未探索区通过约 0.01、无效不计）；"失败必须和假设的身份一致才算正例"。

- **语言**：合取是一组特征 id（叶子或类）；φ 满足它，当且仅当每个 id 都在 `registry.closure(φ.features)` 里。没有否定。约简形式：排序、去重、去掉层根（`ast`、`plan`、`data`）、去掉被同组里更具体的 id 蕴含的祖先。
- **S** 是一个合取，初值为第一条失败的 φ 的全部叶子；**G** 是一组合取，初值只有空合取（作用域内处处可能）。
- **正例**（落在待定区）：S 换成"S 的闭包与正例闭包的交"的约简（缺的特征删掉，同类不同值升到类）；G 里不覆盖该正例的成员删掉。落在确认区的只记进 E⁺。
- **反例**（落在待定区）：G 里覆盖它的每个成员，换成"加上一个 S 里它没有的字面量"的各种最小特化，字面量取该 S 字面量的祖先链上仍不在反例闭包里的最一般的那个；然后去掉被别的成员蕴含的成员，按（长度，字典序）排序，超过 `VS_MAX_GENERAL` 截断并置 `truncated`。落在确认区的通过无法排除，记进 E⁻ 与 `contradictions`，S、G 不变。
- **位置**：假设的作用域是（引擎，oracle）。φ 缺 S 提到的某一层时为 `undetermined`（既不算正例也不算反例）；满足 S 为 `confirmed`；否则满足某个 G 成员为 `pending`；否则 `outside`。
- **身份**：依次看 harness 第 2 档对这个假设的归属测试结果；有 fix set 的假设与第 3 档画像的 fix set 比较（没有画像则未知）；没有 fix set 的假设比较失败类别、错误类别、行为画像形状。身份不一致的失败对该假设是反例；未知则不更新。
- **新家族**：没有被任何假设吸收为正例的失败，带第 3 档画像时建立新假设：I 取 fix set，ΔP 取 plan diff，V 取版本梯，另记失败类别、错误类别、行为形状；G 用此前同作用域里见过的通过回放一遍。没有画像的记为未解释失败进 R。
- **R**：`ρ_c = (未解释失败 + 1) / (测过 + 100)`，按单元；只记预测时落在未探索区的通过，与任何没有得到解释的失败。**Kᵛ**：`(无效 + 1) / (做过 + 10)`，按（`引擎|主构造`，oracle）；每条实验都计，无效来源分开记数。
- **惊讶**：对有效结果按 `−log₂ P(y | 有效)` 算，无效不计。`ExperimentRecord.p_t` 记 `P(fail | 有效)`，所以账本里的 `p_t` 加标签就能重算惊讶。
- **分诊**按惊讶大小：不低于 2.0 比特，失败为新家族、通过为意外通过；0.5 到 2.0 为边界移动；低于 0.5，失败为重复、通过为无信息；无效单列。

### PI 已自行核查并定下的选择（用户已验收）

**用户验收（2026-10-09）：下面五条，连同"与计划的偏差"一节的六处，用户看过收尾消息后答复"都没有问题"。** 它们从此是用户确认过的决定，不再是"编排者定、可推翻"；九个常数的取值照旧由门槛钉住，要改先问用户。

用户的指示是"继续完成 S6"；S5 交接里写着要先问用户的两件事（第 1、2 条），编排者没有另行提问，按推荐定下，依据是此前两次"自行判断决定"的约定。每一条都在 DECISIONS 里有理由。

1. **理论常数九项的取值，以及它们进 manifest 的办法。** 0.95、0.5 是文档原值；ρ 的先验 1/100 由"未探索区失败约 6.6 比特"反推；先验的强度（100 次、10 次）、两个分诊阈值（0.5、2.0 比特）、G 的上限（64）文档没有给，是编排者定的。它们放在 `theory/constants.py`，由 `extend_manifest()` 写进 run manifest 的 `theory` 一节；`harness/constants.py`、`harness/manifest.py`、`gates/s04_frozen.json` 没有动。门槛钉住了这九个值。
2. **PLAN 决策 2 的版本空间一侧**：采用。单调合取加类层级，S 一个、G 一组，析取靠拆假设。
3. **惊讶以"有效"为条件算，Kᵛ 不乘进去**；`p_t` 记 `P(fail | 有效)`。文档的公式写的是联合概率，分诊表的五个量级却只与条件概率吻合，两者取了后者。
4. **分诊按惊讶大小分带，不按位置。** 两者在确认区、待定区恒一致；未探索区的 ρ 漂高后，按大小分的含义是"R 已经知道这个单元常失败，不再当新家族反复诊断"。这时 `Observation.triage` 可能是 `boundary_move` 或 `duplicate` 而 `prediction.hypothesis_id` 是 `None`。
5. **假设的作用域是（引擎，oracle）；G 的初值是空合取，建族时回放见过的通过。** 同一机制被两个 oracle 各自发现时是两个假设。

### 与计划的偏差

- ORCHESTRATION 第 8 节建议 S6 串行单包，实际拆成两个串行包（版本空间一包、理论组合一包）。
- 门槛的实机走查比 SESSIONS 的字面要求多三步（重复、意外通过、无信息），五个量级一次走全。
- PLAN 总原则第 2 条写"惊讶公式、接受规则进 harness 并记录哈希"。harness 在 S4 已冻结，惊讶公式放在理论层；它的代码哈希由 `theory_manifest()` 记进 run manifest 的 `theory` 一节，`verify_theory_manifest()` 能查出改动。没有改 harness。
- PLAN 第 7 节"先测 31 个已确认家族中可用合取表达的比例"没有做：SESSIONS 的 S6 门槛不含这一项，它需要逐族的最小复现与正反例，留给 S7 的离线回放（见未决问题）。
- 没有与 PLAN 冲突的实现选择；没有做持久化、回滚、MDL、Hunter、LLM 角色。

S6 留下的未决问题在文末"未决问题"一节的"S6 发现"一组里。

## 最近完成会话：S5（2026-10-09）

Claude Code 担任编排者，全部实现来自 grok 工作包。会话分支 `session/s05` 从 `s04-done`（9d88ff7）建立；用户此前指示 S4 完成后直接开 S5、需要确认的事项按编排者的推荐确认（逐项在 DECISIONS 的 S5 条目里）。开工时往 `.venv` 装了 `sqlglot==30.21.0`，装完起点检查为 275 passed, 3 skipped 与 GATES PASS 4/4。会话中途因用量上限中断过一次，靠 WIP 提交与本文件接上。三包全部合并，收尾合并回 main，tag `s05-done`；S6 从此 tag 起。

**用户的自主指示只到 S5 为止。** S6 要不要开、S6 里需要确认的事项怎么定，等用户发话。

### 交付与门槛

- 词表与类层级（`features/vocabulary.py`、`registry.py`）：167 项（门槛契约 `CORE_VOCAB` 的 166 项，加执行者追加的叶子 `ast:window_fn:other`），三层 `ast`、`plan`、`data`；种类为 class、leaf、family（开放族 `plan:<算子名>`、`ast:fn:<函数名>`）。注册表给出祖先、同类（"换同类取值"）、闭包，发明特征（正则类）的登记、验收记录、存取。词表摘要 `1e001c14a030…`，词表一变摘要就变，φ 里带着它。
- φ 容器（`phi.py`）：`Phi(engine, features, layers, vocab)`；`features` 是排好序的叶子 id，`layers` 记三层状态（ast：ok / fallback；plan、data：ok / unavailable / skipped）。没有任何随运行变化的内容；`to_dict` / `from_dict` 做结构校验，可以原样进账本的 `ExperimentRecord.phi`。
- 规格核对（`spec.py`）：`check_spec(phi, spec)` 判 φ ⊨ spec，必须项与数据性质要在 φ 的闭包里（所以规格可以写类一级的 id），禁止项不能在；某一层没算出来时相关项记为不确定，结论为不满足。
- 单元投影（`units.py`）：`引擎|oracle|主构造|计划算子类|数据性质类`，主构造十二种、计划算子类八种加 `none`、数据性质类五种加 `unknown`，各维按固定优先级取一个。
- 语句层（`ast.py`）：sqlglot 解析，特征只来自语法结构；解析不了（或一段文本不止一条语句）走正则兜底并带 `ast:parse:fallback`。已验收的发明特征按正则命中输出。
- 计划层（`plan.py`）：DuckDB 复用旧工具 `diagnosis.bisect.plan_op_names`（`EXPLAIN (FORMAT JSON)`），DataFusion 取 `EXPLAIN` 的 physical_plan 文本；算子名原样作特征。
- 数据层（`data.py`）：一律在库上算，而且不发聚合 SQL：把被引用的基表取回来在 Python 里数（空表、单行、重复行、NULL、零、负数、极端数、空串、非有限值、列类型）；集合运算的两个输入各自作为查询执行，判重复行与 NULL。被测语句本身从不执行。
- 组合入口（`extract.py`）：`extract`（调用方进程内）与 `extract_isolated`（子进程；崩溃、超时时语句层照算，`plan`、`data` 记 `unavailable`）。命令行 `python -m surprise.features {vocab|phi|corpus}`。
- 门槛九组：`vocab spec units`（s05-vocab）、`ast`（s05-ast）、`dynamic stable distinguish specs corpus`（s05-dynamic）。φ 跨进程稳定（25 个用例，两个子进程与本进程三方一致）；DF-A、DF-B 与 DuckDB F1–F11 的最小复现两两可区分（66 对），DF-A → DF-B 恰好是一次同类替换；17 组手写 spec / SQL 对全对；语料分布报告两次运行相同。
- 语料分布（`seeds/corpus.json`，门槛实测）：1092 条种子落在 76 个单元、10 种主构造；语句层兜底 34 条，计划层可用 480 条，数据层可用 483 条；最大的三个单元是 `postgres|plain|none|unknown`（134）、`duckdb|plain|none|unknown`（83）、`duckdb|window|none|unknown`（56）。

最终复跑（三包合并后在 `session/s05` 主检出区独立运行）：pytest 367 passed, 3 skipped（起点 275，skip 未增加）；S01 7/7、S02 5/5、S03 5/5、S04 9/9、S05 9/9，`GATES: PASS (5/5 passed)`。冻结清单未动（S04 的 freeze 组照常通过）。

### 拆包清单与结论（全部已合并）

| 包 | 内容 | 轮数 | 合并 | 审查发现 |
|---|---|---|---|---|
| s05-vocab | 词表、注册表、φ 容器、规格核对、单元投影 | 首轮 + 返工 1 轮 | 4b55eb1 | `Phi.from_dict` 与 `Registry.load` 不做校验；顺带改了 S4 测试夹具的进程退出方式 |
| s05-ast | 语句层与正则兜底 | 首轮 + 返工 1 轮 | dd472f9 | 七处判错：把括号当子查询、命名窗口、IGNORE NULLS、写语句里的相关子查询、赋值记成比较、同名遮蔽、兜底的两处误报 |
| s05-dynamic | 计划层、数据层、组合入口、命令行、语料报告 | 首轮 + 返工 1 轮 | 42e1856 | `extract_isolated` 吞掉调用方错误；基表引用带上了采样或连接子句；超上限的集合运算输入被当成没有特征 |

三个包首轮都通过了自己的全部门槛，问题都是编排者读代码加探测找出来的。没有推翻包，没有第 2 轮返工。grok 成本合计约 5.9 美元（vocab 1.16、ast 2.43、dynamic 2.34）。说明、报告、审查包、返工意见归档在 `docs/orch/s05/`。

### 当前接口

`surprise.features` 导出（S6 起直接用）：

- `default_registry()`、`Registry`（`known`、`get`、`ids`、`layer`、`parent`、`ancestors`、`children`、`siblings`、`closure`、`register`、`accept`、`digest`、`save`、`Registry.load`）、`FeatureDef`。
- `Phi`、`make_phi(engine, features, layers, registry=None)`。
- `check_spec(phi, spec, registry=None) -> SpecCheck(ok, engine_ok, missing, forbidden, undetermined)`；`spec` 是 `surprise.theory.contracts.Spec`。
- `unit_parts(phi) -> (主构造, 计划算子类, 数据性质类)`、`unit_of(phi, oracle)`。
- `extract_ast(sql, engine, registry=None) -> (frozenset, "ok" | "fallback")`。
- `extract(case, *, layers=("ast", "plan", "data"), runner_factory=None, registry=None) -> Phi`：φ 描述的语句是 `full_query(case)`。
- `extract_isolated(case, *, layers=..., timeout_s=None, registry_path=None) -> Phi`：调用方的错误（读不了的词表文件、没有 runner 的引擎要算 `plan` 或 `data`）照样抛出。
- 常数在 `features/limits.py`：`MAX_TABLE_ROWS = 10000`、`PROBE_TIMEOUT_S = 10.0`、`ISOLATION_TIMEOUT_S = 60.0`。它们不在 manifest 的冻结常数里；S6 把理论常数写进 manifest 时决定要不要一并记。

成本（主检出区实测）：进程内 `extract` 三层约 15 毫秒一次；`extract_isolated` 约 0.3 秒一次；整份语料 1092 条的报告约 11 秒。

### PI 已自行核查并定下的选择（用户可以推翻）

1. **数据性质不用聚合 SQL 算，取回行在 Python 里数**，每张表上限 10000 行，超过就整层 `unavailable`。理由：被测引擎的缺陷可能把用来验证的聚合也算错。代价：大表上的语句没有数据层。
2. **看不全就不描述**：集合运算的某个输入超过上限、某张表的引用生成不了，数据层整层 `unavailable`，而不是少报几个特征。唯一的例外是输入单独跑不起来（引用了外层的列）：不输出它的特征，层仍是 `ok`。这时 φ 里没有 `data:setop:*` 不等于"没有重复行"。
3. **φ 默认在调用方进程里提取**（只跑 EXPLAIN、取表、集合运算的输入，不执行被测语句），`extract_isolated` 留给不放心的场合。已知会杀进程的 F10 语句取计划是安全的。
4. **语句层的反例进门槛**：`gates/s05_cases.py` 在派发后追加了 14 条 `AST_PROBES`、3 条 `FALLBACK_LACK`（52e6030）。这是在本会话自己的门槛上加严，不是改旧门槛。
5. **单元的三维取值表与优先级**（主构造 dml > set_op_all > set_op > window > …；计划算子类按算子名子串；数据性质类 dups > nulls > empty > extreme > plain）是编排者定的粗粒度，对应 PLAN 决策 4"先粗"。语料上 1092 条落在 76 个单元。S8 发现太粗或太细时改 `units.py` 一个文件。

### 与计划的偏差

- SESSIONS 写的是"先契约一包，再两包并行"，实际三包串行：`s05-ast` 与 `s05-dynamic` 都要改 `features/__init__.py`，后者还依赖前者的 `extract_ast`。
- 没有改 `theory/contracts.py`：S2 定的 `Spec` 已经够用，规格核对器直接用它。
- `coverage/features.py` 只作参考，没有 import（旧代码不动）。

## 最近完成会话：S4（2026-10-09）

Claude Code 担任编排者，全部实现来自 grok 工作包。会话分支 `session/s04` 从 `s03-done`（499291b）建立；起点独立复跑 242 passed, 3 skipped 与 GATES PASS 3/3。两包全部合并，harness 已冻结，收尾合并回 main，tag `s04-done`；S5 从此 tag 起。

用户在会话中追加的指示（2026-10-09）：S4 完成后编排者自行开始 S5；需要确认的事项一律按编排者的推荐确认，逐项记入 DECISIONS。接手的会话沿用这条指示，不等答复，直接按 SESSIONS 的 S5 一节开工。

### 交付与门槛

- 第 1 档：新进程执行器 `execute_isolated`（ok / error / timeout / crash 四种状态，子进程崩溃或挂起不影响调用方）；每个差异候选先查三条前提、再做 5 次新进程重跑加 1 次单线程重跑，不稳定、依赖未指定语义、结果不可比、写语句的非崩溃候选都降为 invalid。
- 第 2 档：归属测试接口，用手写假设调通。有干预名的假设做一次"关掉 fix set 后差异是否消失"的测试；没有干预名的比较失败类别、错误类别与行为画像的形状。身份不一致升第 3 档。理论 T 没有做。
- 第 3 档：最小化（旧 `BugFixer._minimize` 加一遍删无用 setup 语句）与完整画像（旧 `compute_fix_set`、`plan_diff_ops`，版本梯走 S3 的旧版子进程）。最小化后不复现或违反前提降为 invalid。
- `Label.cve` 记五步的执行或跳过原因及证据；最终标签经 `evaluate_final` 入账，pass、invalid 同样记录。
- harness 与常数冻结，清单与哈希校验见"冻结"一节；manifest 环境补了旧版引擎、PostgreSQL 参照、间接依赖。

最终在 `framework/` 下、两包合并并冻结之后的主检出区独立运行：

| 命令 | 结果 |
|---|---|
| `../.venv/Scripts/python.exe -m pytest -q testing tests` | 275 passed, 3 skipped，退出码 0（起点 242，新增 33，skip 未增加） |
| `../.venv/Scripts/python.exe -m surprise.gates.all` | S01 7/7、S02 5/5、S03 5/5、S04 9/9；GATES: PASS (4/4 passed)，退出码 0 |

`gates/s04.py` 九组与 SESSIONS.md S4 门槛的对应：

- `m1`：经 `evaluate_final` 写入 50 条最终标签（14 fail、20 invalid、16 pass）。confirmed 族 fail 且身份证据正确：F1、重建的 F6（含经 TLP 的带谓词形态）落在 `deliminator, filter_pushdown`；F2 及其 `.sql` 写法 `window_self_join`；F7 及其 `.sql` 写法 `common_subexpressions, expression_rewriter`；F9 fix set 为空、身份是见证开关 `window_combine`；F11 是 crash，`InternalException`，fix set `build_side_probe_side`；DF-A、DF-B、DF-D、DF-F 为 Cross fail（三个以上独立引擎、目标唯一异类），DF-I 为 crash。四个有 fix set 的 recall 条目（F1、F2、F7、F9）与 `docs/recall_repros.json` 一致。未指定语义的 F3（前提）、F8（重跑）判 invalid；F5 只允许 pass 或 `unstable_rerun`；普通查询与两份不复现的 `.sql` 变体判 pass；值依赖错误、无序结果、不等价改写、DATE 假候选、写语句判 invalid。
- `tier1`：六个稳定族经 5 次新进程重跑仍为 fail；F8 `unstable_rerun`；F5 最多试 10 次，出现 `unstable_rerun` 即止，任何一次 fail 都算不过；六种可编排的重跑日程（全复现、单线程不复现后追加 15 次、追加中漏一次、只复现一两次、行序颠倒仍稳定）。
- `premise`：ASOF 并列（含审查中发现的"ON 里带只涉及右表的条件"）、写语句、跨库值类别不可比为 invalid；无并列、写语句的 crash、可比的跨库差异保持 fail。
- `isolation`：四种状态分得清；`duckdb/F10_window_frame_underflow.sql` 的两条致命语句在子进程里以退出码 0xC0000094 结束、调用方无恙；一个候选至少七个不同进程；会杀进程、会挂起的假 runner 与会崩的参照引擎都被收住。
- `tier2`、`tier3`：归属一致与不一致各两种方式；九个确认用例的 fix set、版本梯、最小化结果是原 setup 的子序列；无关的表被删掉；最小化途中丢失的候选降级；第 1 档被拒后的跳过原因如实记录。
- `contracts`、`environment`、`freeze`：取值表与常数、原始入口仍返回 `cve == {}`、非法请求在执行前被拒；manifest 环境字段与"harness import 的旧模块都在哈希范围内"；冻结清单与工作树一致。

门槛期望全部在派发前实测；审查中发现的两类问题先实测再加进门槛（ASOF 反例、跳过原因）。没有按族号或 SQL 文本硬编码的判定。

### 已知的召回缺口（门槛如实记录，不要求 fail）

| 族 | 最终标签 | 原因 |
|---|---|---|
| F10（四条语句） | invalid / nondeterministic | 旧确定性筛查把显式帧子句当排序键，执行之前就筛掉；两条致命语句只用来直接验证执行器 |
| F5 | invalid / unstable_rerun（偶尔原始判定就是 pass） | 并行竞态；新进程里复现率约 6–11% |
| DF-E、DF-J | invalid / query_error | 引擎拒绝合法 SQL，按标签规则"查询报错"归 invalid |
| DF-H | invalid / query_error | panic 文本不在旧 `is_internal_error` 的标记里 |
| DF-G | pass | 旧宽松归一化把 DECIMAL 舍入成浮点，看不出精度丢失 |

让它们判 fail 都要改旧判定代码，与"判定代码只搬不改"冲突。

### 拆包清单与结论（全部已合并）

| 包号 | 目标 | 允许路径 | 依赖 | 门槛组 | 结论 |
|---|---|---|---|---|---|
| s04-tier1 | 新进程执行器、第 1 档、`certify` 与 `evaluate_final`、`Label.cve` 结构、新 invalid 来源与常数、manifest 环境字段 | harness/cve/**、harness/evaluate.py、contracts.py、constants.py、manifest.py；tests/test_surprise_s04_*.py 与三个定向更新的旧测试 | s03-done | contracts isolation tier1 premise environment | 合并 7b12a85；返工 1 轮（ASOF 并列键漏判、退出码 0 无结果应为 crash、`unattributed_crash` 的 tier）。独立 264 passed / 3 skipped；25 条 shell 命令已审查；约 4.08 美元 |
| s04-tier23 | 第 2 档接口、第 3 档最小化与画像、降级规则 | harness/cve/**、harness/evaluate.py、constants.py、manifest.py；tests/test_surprise_s04_*.py | s04-tier1 | tier2 tier3 m1（连同前五组） | 合并 1ae6e61；返工 1 轮（放行漏放的常数快照断言、第 1 档被拒后的跳过原因、干预名单缓存、最小化后用原始判定再验证）。独立 275 passed / 3 skipped；23 条 shell 命令已审查；约 4.19 美元 |
| （编排者） | 冻结清单 | gates/ | 两包都已合并 | freeze | 已做 |

表内 harness、tests 路径相对 `framework/surprise/`、`framework/`。两包的 brief、报告、审查结论、返工意见归档在 `framework/surprise/docs/orch/s04/`。没有推翻包，没有第 3 轮返工。

### 当前接口（已冻结）

入口边界：`judge`、`evaluate` 是原始 oracle 层，返回未经 CVE 的标签，`cve == {}`，S2/S3 的门槛与测试照旧验证它们。最终标签走 `surprise.harness.cve.certify`，入账走 `surprise.harness.evaluate.evaluate_final`。S8 的主循环用后者。

- `certify(case, oracle, *, hypothesis=None, diagnose=False, isolation="process", runner_factory=None, timeout_s=10.0, wall_timeout_s=None, rewrite_rule=None, paired_query=None, old_python=None, reference_factories=None) -> Label`。`evaluate_final` 在 `evaluate` 的参数之外多 `hypothesis`、`diagnose`、`isolation`、`wall_timeout_s`，每调用一次恰好写一条记录；流水线自身抛异常记 `invalid / harness_error`。
- `isolation="process"`（默认）：调用方进程不执行任何目标 SQL；传入的工厂必须是子进程能按模块名导入的模块级可调用对象，否则在执行前抛 `ValueError`。`"inline"`：全部在调用方进程里做、每次判定新建 runner，给测试用的闭包工厂用。
- `execute_isolated(case, *, prelude=(), timeout_s, wall_timeout_s, runner_factory) -> IsolatedResult(status, rows, error, exit_code)`。S5 可以用它在隔离进程里跑 EXPLAIN 与数据性质查询（把语句放进 `SqlCase.query`）。
- `Label.cve`：`schema`（1）、`tier`（0 不是候选；1 做了第 1 档；2 归属一致；3 做了最小化）、`isolation`、`raw`（原始判定及其身份）、五步 `rerun / premise / attribution / minimize / profile`。每步有 `status`；跳过时 `reason` 取 `not_a_candidate`、`not_requested`、`premise_violated`、`tier1_rejected`、`attributed`、`unattributed_crash`、`not_reproduced_minimized`、`timeout`、`crash`、`harness_error` 或被违反的前提名。
  - `rerun`：`attempts`（5 或 20）、`reproduced`、`stable`、`extended`、`distinct_outcomes`、`single_thread: {ran, reproduced}`。
  - `premise`：`violations`、`checks`。
  - `attribution`：`hypothesis_id`、`method`（`fix_set` / `profile`）、`consistent`、`executions`。
  - `minimize`：`reproduced`、`setup_before`、`setup_after`、`case`、`executions`。
  - `profile`：`fix_kind`、`fix_set`、`plan_diff`、`version_ladder`（`longstanding` / `recent` / `unknown` / `unavailable`）、`error_class`、`behavior_shape`、`witness_switches`、`executions`。
- 身份证据：第 3 档之后 `identity.switches` 取 fix set，fix set 为空时保留原始见证开关；`error_class`、`behavior` 不变。被 CVE 降级为 invalid 的标签身份为空，原始判定留在 `cve.raw`。同一稳定输入两次判定的 `to_dict()` 相等（`cve` 里没有进程号、耗时、路径）。
- 假设（第 2 档）是 mapping：`hypothesis_id`、`engine`、`interventions`（干预名列表，可空），无开关时另给 `fail_kind`、`error_class`、`behavior_shape` 中的若干个；其余键忽略，所以 `theory.contracts.Hypothesis.to_dict()` 补上这几个键就能直接传。校验在原始判定之前，非法即 `ValueError`。`behavior_shape(behavior)` 返回 `missing_only` / `extra_only` / `both` / `none`。
- `INVALID_REASONS` 十七项，S4 新增 `unstable_rerun`、`unspecified_semantics`、`side_effecting_statement`、`incomparable_results`、`unattributed_crash`、`not_reproduced_minimized`。
- 复现判据（第 2、3 档共用）：plan variant 比较"prelude 之后"与"再打开见证开关"两种形式，两边成功且 bag 相同、或以相同错误类别失败算一致；其他 oracle 在 prelude 之下重做原始判定，仍 fail 算复现。最小化结束后另做一次不带 prelude 的原始判定，fail 且失败类别不变才算复现。

### 冻结

- 清单：`framework/surprise/gates/s04_frozen.json`，由 `python -m surprise.harness.manifest write` 在两包合并后生成。51 个文件（harness 31 个、旧依赖 20 个），哈希 `50fa40cf2d1988e8718369487b42be2c1da1a76964c0c520af51ce919b8d5fd9`。
- 常数八项：`QUERY_TIMEOUT_S = 10.0`、`CVE_RERUN_ATTEMPTS = 5`、`CVE_RERUN_EXTENDED = 15`、`CVE_WALL_TIMEOUT_S = 120.0`、`CVE_ATTRIBUTION_WALL_TIMEOUT_S = 120.0`、`CVE_PROFILE_WALL_TIMEOUT_S = 600.0`、`CVE_MINIMIZE_MAX_EXECUTIONS = 30`、`CVE_BISECT_MAX_EXECUTIONS = 120`。
- 环境（清单里的快照）：Python 3.13.9；DuckDB 1.5.5 / 旧 1.1.3；DataFusion 54.0.0 / 旧 50.0.0；SQLite 3.51.0；PostgreSQL 参照 16.15；pyarrow 21.0.0、psycopg2-binary 2.9.13；sqlglot 未安装（记 None，名单里留了位置）。
- 校验：在 `framework/` 下 `../.venv/Scripts/python.exe -m surprise.harness.manifest verify surprise/gates/s04_frozen.json`，退出码 0 表示未变；`gates/s04.py` 的 `freeze` 组每次都查清单、哈希与常数。
- 冻结之后 `framework/surprise/harness/` 与被哈希的二十个旧模块有任何改动，S04 门槛变红。要改先问用户；改完重新生成清单并在 DECISIONS 记一笔。派发脚本见到 `s04-done` 会自动把 `harness/` 列入执行者禁区。
- 后续层要往 run manifest 里加自己的内容（如 φ 词表版本、LLM 模型号），在传给 `Ledger.start_run` 的 dict 上加键即可，不需要改 `manifest.py`。

### 成本（主检出区实测，每次调用）

| 情形 | 耗时 |
|---|---|
| 通过的用例经 `certify`（DuckDB，TLP / plan variant） | 约 0.2 秒 |
| 通过的用例经 `certify`（DataFusion，Cross，含 PostgreSQL） | 约 0.6 秒 |
| 候选做完第 1 档（原始判定加 6 个新进程） | 约 1.5 秒 |
| 第 1 档加第 2 档归属一致 | 约 1.7 秒 |
| 第 1 档加第 3 档（F1） | 约 2.7 秒；F9 的二分用满 120 次约 3.8 秒；跨库约 6 秒 |

整套 `gates/s04.py` 约 3 分半，`surprise.gates.all` 约 6 分钟。

### PI 已自行核查并定下的选择（用户可以推翻）

1. `gates/s03.py` 的旧解释器路径改为经 git 公共目录定位（f556fba）。期望值没动，主检出区仍是 5/5；起因是它在 worktree 里恒失败，执行者为此建过目录联接。
2. `datafusion/` 下 M1 表没覆盖的复现按实测定期望：DF-D、DF-F、DF-I 判 fail，DF-E、DF-H、DF-J、DF-G 记为召回缺口。
3. 重跑次数定为 5 加单线程 1 次，单线程不复现再加 15 次；复现按每条语句的结果 bag 比较。
4. 跨库可比性按"同一列上值类别互斥"判，不改旧 normalizer；对 DuckDB 目标同样生效。
5. 冻结前没有处理每次原始判定起一个进程的开销，也没有并行重跑；留到 S8 实测吞吐后再定，动它要解冻。

### 与计划的偏差

没有与 PLAN 冲突，没有做理论 T、Hunter、LLM 角色。相对 SESSIONS 的字面要求有三处出入，都已记入 DECISIONS：F10、F5 不判 fail（S2 验收时已定）；`datafusion/` 下四个复现记为召回缺口；拆成两个串行包而不是一个包。操作上的偏差：执行者首轮建过一个指向主检出区 `.venvs` 的目录联接并删过一个自己的临时文件，联接由编排者在清理前单独移除；编排者两次在说明里漏放常数快照断言所在的测试文件。

## 最近完成会话：S3（2026-10-09）

Codex 担任编排者，全部实现来自 grok 工作包。会话分支 `session/s03` 从 `s02-done-r2`（caec153）建立；起点独立复跑 149 passed, 3 skipped 与 GATES PASS 2/2。四包全部合并，最终独立集成通过。收尾合并回 main，tag `s03-done`；S4 从此 tag 起。下方保留 S2 的历史接口与 M1 逐族期望，当前接口以本节为准。

### 交付与门槛

- 七类 `tlp/norec/plan_variant/index_presence/equivalent_query/version_differential/cross_dbms` 统一注册分发；DuckDB 与 DataFusion 都可调用 `judge`、`evaluate`。DataFusion 的 Index presence 是 `invalid / not_applicable`。标签仍只有 pass/fail/invalid，全部 `cve={}`，S4 才接 CVE。
- Index presence 比较 DuckDB ART 索引有/无的结果；Equivalent query 只使用三条附等价性论证的机械规则 `double_negation`、`demorgan`、`case_to_coalesce`。NULL、重复行、BETWEEN/CASE 内部 AND、引用字符串与不可信 pair 均有反例。
- Cross 复用旧 `classify_divergence`，至少三个独立成功引擎、目标唯一异类才 fail。DF-A/DF-B 以 DuckDB 与 PostgreSQL 作参照；SQLite 3.51.0 不支持两个 ALL 语句，报错不能投票。DF-B 正确 bag 包含 NULL，旧 SQL 注释不改。
- Version 比较 DuckDB 1.1.3/1.5.5、DataFusion 50.0.0/54.0.0；仅独立多数支持旧结果或前四类在新版上独立见证 fail，才判回归。F2 两条方向证据支路均已实测；无参照的 SELECT version() 只判 `invalid / direction_unknown`。

最终在 `framework/` 下、四包合并后的主检出区（94b602c）独立运行：

| 命令 | 结果 |
|---|---|
| `../.venv/Scripts/python.exe -m pytest -q testing tests` | 242 passed, 3 skipped，退出码 0 |
| `../.venv/Scripts/python.exe -m surprise.gates.all` | S01 7/7、S02 5/5、S03 5/5；GATES: PASS (3/3 passed)，退出码 0 |

S3 五组 `registry/local/cross/version/matrix` 全通过。matrix 实际写入七类 × 两引擎共 14 条账本记录，并检查无隐藏 harness_error、DataFusion 索引不适用、标签稳定、manifest 校验。派发前期望来自本机实测；审查反例也先实测再加门槛，没有降低法定数或把版本当独立引擎。

### 拆包清单与结论（全部已合并）

| 包号 | 目标 | 允许路径 | 依赖 | 门槛组 | 结论 |
|---|---|---|---|---|---|
| s03-registry | 注册分发、两引擎映射、S2 三类接 DataFusion、options、invalid 来源与 manifest 范围 | harness/oracles/__init__.py、registry.py、sound.py；harness/evaluate.py、contracts.py、manifest.py；tests/test_surprise_oracles.py、test_surprise_evaluate.py、test_surprise_contracts.py、test_surprise_s03_registry.py | s02-done-r2 | registry | 合并1cae8cd；返工1轮，仅修新增测试的长期有效性。独立165 passed/3 skipped；15条shell命令已审查 |
| s03-local | ART Index presence、确定性改写规则 | harness/oracles/index_presence.py、equivalent_query.py、rewrites.py；tests/test_surprise_s03_local.py | registry | local | 合并0293ace；返工2轮（De Morgan/pair前提、E字符串边界）。独立186 passed/3 skipped；30条shell命令已审查 |
| s03-cross | PG16参照 runner、法定数及唯一异类 | harness/oracles/cross_dbms.py、pg_reference.py；tests/test_surprise_s03_cross.py | registry、PG就绪 | cross | 合并a60a287；返工2轮（多语句/事务边界、WITH SELECT INTO）。独立188 passed/3 skipped；29条shell命令已审查 |
| s03-version | 两引擎新旧子进程、回归方向证据 | harness/oracles/version_differential.py、version_worker.py；tests/test_surprise_s03_version.py | registry、cross | version | 合并7454d8d；返工1轮（类型兼容、证据稳定、协议/错误标签）。独立221 passed/3 skipped；34条shell命令已审查 |

表内 harness、tests 路径相对 `framework/surprise/`、`framework/`。公共文件仅 registry 改；local/cross 并行，cross 合并后派 version，同时最多两包。每包合并即提交 HANDOFF 状态。四包 brief、报告、最新独立审查结论、各轮返工意见已归档 `framework/surprise/docs/orch/s03/`，总花费约 8.93 美元。没有推翻包，没有超过两轮返工。

### 当前接口与证据

- `judge(case, oracle, *, runner_factory, timeout_s, rewrite_rule, paired_query, old_python, reference_factories)`；`evaluate` 同样支持这四个新增 options，仍每次写一条账本记录。
- `register(id, handler)`、`get_handler(id)`、`runner_factory_for(engine)` 在 `harness/oracles/registry.py`。模块末尾自行注册，公共入口懒导入。handler 签名 `judge_case(case, *, factory, timeout_s, options)`。
- `OracleOptions` 为冻结 dataclass：`rewrite_rule/paired_query/old_python/reference_factories`。old_python 是字符串路径；参照 None 使用默认集合，空 dict 明确无参照。只接受独立 ID duckdb/datafusion/sqlite/postgres，拒绝目标和版本别名；PG/SQLite 只作参照。
- `INVALID_REASONS` 共十一项；本次追加 `untrusted_rewrite/direction_unknown/insufficient_engines/non_unique_outlier`，没有第四个标签。S4 冻结前可继续登记 CVE 的 invalid 来源。
- Version detail 保存 `old_version/new_version/old_rows/new_rows/direction/direction_evidence`；行证据按 bag 规范排序，保留重复、NULL、类型。独立 sound 见证保存完整 `Label.to_dict()`，包含 SQL、身份与 detail。
- manifest 覆盖 39 个文件（新 harness 21 个、旧依赖18个），哈希 `59255df29e81050de12488862127e21c18762c2f1a5acc8edf2d28f377bae33e`。旧实现与 PLAN/SESSIONS/ORCHESTRATION/CLAUDE/AGENTS/tools/orch/.grok 零改动。当前未统一记录的环境版本见下面未决问题。

### PostgreSQL 与旧版环境的恢复

本机参照为 EDB PostgreSQL 16.15 Windows x64，免安装二进制与数据在不入库的 `.orch/pg16/`，无系统服务、无全局 PATH 修改；下载源及 SHA256 记在 DECISIONS。仅监听 127.0.0.1:55432，用户 coevo、数据库 postgres、本机 trust。

先查状态（仓库根）：

`.orch/pg16/binaries/pgsql/bin/pg_ctl.exe -D D:/CoevoDB/.orch/pg16/data status`

仅服务器未运行时启动，已有数据不得重新 initdb：

`.orch/pg16/binaries/pgsql/bin/pg_ctl.exe -D D:/CoevoDB/.orch/pg16/data -l D:/CoevoDB/.orch/pg16/server.log -o "-h 127.0.0.1 -p 55432" -w start`

参照默认 DSN 为 `host=127.0.0.1 port=55432 user=coevo dbname=postgres connect_timeout=5`，`COEVO_REFERENCE_PG_DSN` 可覆盖。每 runner 用独立未提交 schema/事务，close 回滚；最终人工核查遗留 schema 数为 0。

旧解释器默认从 git 公共目录定位 `.venvs/duckdb-1.1.3`、`.venvs/datafusion-50.0.0`，按平台找 Scripts/python.exe 或 bin/python，`COEVO_VENVS` 可覆盖。version_worker 经文件路径和 `-I` 启动，空临时工作目录；旧 DF 只直接导入 datafusion 与标准库，原始 typed JSON 回主进程再归一化。独立核查旧 DF 环境仍无 duckdb/psycopg2，没有安装依赖或使用旧代码写死的 bin/python。

### PI 已自行核查并定下的选择

1. PG 只作参照，直接 psycopg2 包装事务隔离；查询限单条只读，setup 事务控制在执行前拒绝，不让参照 schema 被误提交。
2. 改写仅上述三条证明规则；外部 pair 只容许关键词大小写、外部空格、单尾分号等一致写法，字面量/引用标识符/评论文本变化拒绝。U& 形态保守不适用，不扩大规则覆盖。
3. Index 门槛不强迫小表计划选索引。另用2万行人工核查确实出现 ART Index Scan，结果仍 pass；测试的是索引存在/不存在的结果等价。
4. Version 旧 DF 原始类型在主进程调用既有 `targets.datafusion_runner._norm` 后共享 normalize，与同一目标 runner 兼容；不从字符串猜日期。DATE/bytes/Decimal 的真实端到端标签都 pass。双方成功同一错误 bag 仍 pass，双方 SQL 错误 invalid；非零退出、缺实际版本号、垃圾 JSON/损坏 typed cell invalid/harness_error。只精确跳过不存在的可选 index 模块，其它依赖异常传播。
5. 继承自旧 Cross 的 DATE 格式假候选按范围纪律留 S4 前提检查，详细反例在下面未决问题；S3 raw fail 不等于确认 bug。

### 与计划的偏差

没有与 PLAN 冲突，没有接 CVE、LLM 改写或理论层。为满足用户点出的前提，拆出 registry 公共包并把 S2 三类接到 DataFusion；增加 PG16 参照 runner 和新的旧版 JSON 子进程入口。规则选三条可证明的机械规则，未实现 SESSIONS 举例的全部种类。门槛在独立审查中补了实际反例，既有旧逻辑未改。

操作偏差也已记录 DECISIONS：registry 首次合并的署名环境变量被嵌套 PowerShell 展开，保留历史不重写；后续使用 PI 的 `.orch/scratch/s3_gw.py` 设置尾注。version 首轮 tmp 递归删除被 deny，核查目录一直保留，后续没有重试删除；最终仅按用户授权由 gw 清理已合并的整个 worktree。PI local 门槛一处漏导入已自行修正，未算执行者返工。

## 最近一次已完成会话：S2 契约、账本、三类健全 oracle（2026-10-08）

分支 `session/s02`，起点 tag `s01-done-r2`（7632c03），收尾合并回 main 并打 `s02-done`。

### 验收后的修订（s02-done-r2，2026-10-09）

用户验收时把点名的五处人工检查项交给编排者自行判断决定。复核没有改任何代码和门槛，改动只有本文件和 DECISIONS.md。五处的结论：

1. **契约分放 `harness/contracts.py` 与 `theory/contracts.py`**：维持。冻结边界和"谁写"的边界是同一条线；实验记录里的规格存成 dict，harness 不依赖理论层。harness 一侧的字段名和四张取值表到 S4 冻结，在那之前 `FAIL_KINDS`、`INVALID_REASONS` 还可以加项。
2. **`gates/s02_cases.py` 的 20 个用例期望**：全部维持，逐条看过。两点定下来：
   - "不适用"就是 `invalid / not_applicable`，不另设第四个标签值。S3 门槛里说的"明确'不适用'"指的就是它。以后统计无效率时把这一项单列，它不代表用例坏。
   - 划分谓词只对 TLP 认识的三种形态有定义（普通 `SELECT … FROM … [WHERE …]`、选择列表等于分组键的 GROUP BY、SELECT DISTINCT）。别的形态再给谓词就是坏用例，判 invalid（`grouped_with_aggregate` 在 plan variant 下是 `query_error`）；`full_query` 不改。生成用例的一方遇到别的形态，把过滤条件直接写进 `query`、`predicate` 留空，这样不损失任何可测的查询。
3. **F5、F6、F10 等已知复现在 S4 门槛里怎么算**：见下面"S4 门槛（M1）对已知复现的期望"一节。为此补查了事实；未决问题"S2 新发现"第 1、2 条已按实测改写，原先有三处写得不对（F5 不是抓不到；F6 补上数据就能复现；F10 经适配器根本不会被执行，所以也不会崩）。
4. **实际标签**（`metrics_small` × TLP）：看过，`y`、`fail_kind`、身份证据（`missing: 1, extra: 0`）与判定依据（`detail` 里的两条语句）齐全，没有要改的。
5. **`orch/s02/s02-oracles.review.md` 第 8 节**：复核无异议。返工的起因在任务说明，补的门槛检查现在是 `evaluate` 组的一部分，本次重跑通过。

复核时在主检出区重跑：pytest 149 passed, 3 skipped；门槛 `s01`、`s02` 都通过。

### 完成了什么

- 五个数据契约与序列化，按"谁写"分成两个文件：
  - `framework/surprise/harness/contracts.py`：`SqlCase`（x）、`IdentityEvidence`（身份证据）、`Label`（y 及证据）、`ExperimentRecord`（实验记录），以及四张取值表 `LABELS`、`ORACLE_IDS`（七类）、`FAIL_KINDS`、`INVALID_REASONS`。
  - `framework/surprise/theory/contracts.py`：`Spec`（规格）、`Hypothesis`（假设）、`TheoryEdit`（理论编辑）。只有类型和序列化，S5–S7 再细化。
- `framework/surprise/harness/constants.py`：harness 的数值常数，现在只有 `QUERY_TIMEOUT_S = 10.0`；`as_dict()` 自动收集，写进 manifest。
- `framework/surprise/harness/ledger.py`：SQLite 实验账本，只能追加；按 run、理论代号、标签、oracle 查询；pass 和 invalid 一样入账。
- `framework/surprise/harness/manifest.py`：run manifest、harness 哈希、校验命令。哈希覆盖新 harness 的全部 `.py`（现在 12 个）加十个会影响标签的旧模块，共 22 个文件；摘要与行尾无关，主检出区和 worktree 算出来相同。
- `framework/surprise/harness/oracles/`：TLP（WHERE、GROUP BY、DISTINCT 三种形态，后两种接入了原先无人调用的 `oracles/tlp_groupby.py`）、NoREC、Plan variant 的三值适配器。什么算差异仍由旧 oracle 的 `check()` 决定，适配器只做执行前筛查、把旧接口的 None 拆成 pass 与 invalid、整理身份证据。旧代码一个字没改。
- `framework/surprise/harness/evaluate.py`：`evaluate()` 判定一个用例并写一条实验记录；判定过程抛异常也记成 `invalid / harness_error`。
- 测试 85 个（`framework/tests/test_surprise_*.py` 五个文件）。

### 门槛结果

在 `session/s02` 三个包都合并之后、主检出区里跑的：

| 命令（在 `framework/` 下，解释器 `../.venv/Scripts/python.exe`） | 结果 |
|---|---|
| `-m pytest -q testing tests` | 149 passed, 3 skipped，退出码 0（S1 的 64 个都在，新增 85 个） |
| `-m surprise.gates.all` | `s01: PASS`（7/7）、`s02: PASS`（5/5），退出码 0 |

`gates/s02.py` 的五组与 SESSIONS.md 的对应：

- `oracles`：20 个固定用例 × 3 个 oracle 共 60 组，每组判两次结果相同（"同一输入两次判定一致"）；已知复现判 fail：TLP 与 NoREC 各抓到账本条目 AUTO-a8be20c9 / AUTO-ad38bad6 的最小化用例，plan variant 抓到 `recall_repros.json` 的 F1、F2、F7 和旧测试里的 deliminator 用例，身份证据里的开关都是 `no_optimizer`（"已知复现里这三类能抓的判 fail"）；四个值依赖错误用例判 `invalid / value_dependent_error`（"值依赖错误样例判 invalid"）；另有崩溃、一侧报错、超时三条注入路径。
- `evaluate`：11 次执行对应 11 条记录，pass、fail、invalid 都有（"每次执行（含 pass）都进账本"）；参数不合法时在执行前拒绝，不留记录。
- `contracts`、`ledger`、`manifest`：往返与校验；写入、过滤、重开；哈希稳定、校验命令能指出被改的文件。

用例表 `gates/s02_cases.py` 里的期望值是派发前用旧 oracle 实测的。

### 工作包

| 包号 | 目标 | 结论 |
|---|---|---|
| s02-contracts | 契约、常数、账本 | 一次通过，返工 0 轮。16 分 35 秒，0.91 美元 |
| s02-manifest | manifest、harness 哈希、校验命令 | 质量上一次通过。记录里有第 2 轮，是编排者误操作把第 1 轮提前终止后的续跑，不是返工。0.48 美元（被终止的那一轮没有上报花费） |
| s02-oracles | 三个适配器与 `evaluate()` | 返工 1 轮。起因是任务说明和门槛都漏了一点（`evaluate` 的部分参数在判定之后才校验），不是执行者理解错了；编排者补了门槛检查后返工，第 2 轮改对。两轮共 1.77 美元 |

brief、report、审查包（含编排者的结论）和返工意见在 `framework/surprise/docs/orch/s02/`。

审查时在门槛之外另做了一次差分核对：从种子语料取 60 个种子、经旧的变异器得到 196 个用例，每个用例对三个 oracle 各判两次，共 588 组；新标签与一份直接调用旧 oracle 的独立映射逐组比较，出入为 0。

### 新增或改动的接口

- `SqlCase(engine, setup, query, predicate=None)`：`query` 是被测查询（给 TLP / NoREC 时是不含划分谓词的那部分，可以自带 WHERE），`predicate` 是划分谓词。
- `Label(y, oracle, fail_kind, invalid_reason, identity, cve, detail)`：`y` 为 fail 时必须有 `fail_kind`，为 invalid 时必须有 `invalid_reason`，为 pass 时两者都是 None。`cve` 现在是空 dict，S4 填。
- `surprise.harness.oracles.judge(case, oracle, *, runner_factory=None, timeout_s=10.0) -> Label`：只判定，不记账。`IMPLEMENTED = ("tlp", "norec", "plan_variant")`，只支持 `engine == "duckdb"`，其余抛 `ValueError`。
- `surprise.harness.oracles.forms.full_query(case)`：把划分谓词并进查询后的那一条语句，确定性筛查与 plan variant 用它。`split_grouped(query)` 识别 `SELECT 键 FROM … [WHERE …] GROUP BY 键` 与 `SELECT DISTINCT 列 FROM … [WHERE …]` 两种形态。
- `surprise.harness.evaluate.evaluate(case, oracle, *, ledger, run_id, purpose, spec, phi, theory_version, p_t, runner_factory, timeout_s) -> ExperimentRecord`：每调用一次恰好写一条记录。
- `Ledger(path)`：`start_run`、`run_manifest`、`run_ids`、`next_seq`、`append`、`records`、`count`、`label_counts`；出错抛 `LedgerError`。
- `python -m surprise.harness.manifest hash | write PATH [--run-id ID] | verify PATH`（在 `framework/` 下执行）：`verify` 退出码 0 表示 harness 未变，1 表示有文件变了并逐个列出，2 表示 manifest 读不了。
- `python -m surprise.gates.s02 --only <组> …`：只跑指定的组，给工作包做部分验收用。

`judge` 的流程是固定顺序：`setup` 有语句报错 → `setup_error`；`is_usable_for_oracles` 不通过 → `nondeterministic`；不满足该 oracle 的前提 → `not_applicable`；然后才调用旧 oracle。旧 oracle 返回 None 时，记录下来的查询形式里有超时 → `timeout`，有报错且全是值依赖错误 → `value_dependent_error`，有别的报错 → `query_error`，全部成功才是 pass。

### 与 PLAN 的偏差及原因

与 PLAN.md 没有冲突。下面几处是 PLAN 和 SESSIONS 没有写到、由编排者定下的，细节在 DECISIONS.md：

- 五个契约分放 `harness/` 与 `theory/` 两个文件，而不是集中一处。原因是 CLAUDE.md 规定 S4 之后 `harness/` 冻结，规格、假设、理论编辑到 S5–S7 才定型，放进去会被提前冻住。实验记录里的规格因此存成 dict，harness 不依赖理论层。
- PLAN 决策表第 6 条（实验账本用 SQLite）仍标着"建议"，本会话按 SESSIONS.md 的 S2 范围直接采用，没有单独再问。
- TLP 的 GROUP BY / DISTINCT 形态需要从查询文本里识别形态，这段识别是新写的（旧 `tlp_groupby` 要求调用方拆好了传进来）；PINOLO-lite（`conjoin` 参数）没有接。
- harness 哈希的范围除了 `surprise/harness/`，还列入了十个旧模块：适配器调用的是它们，只哈希新代码查不出旧判定逻辑被改。
- 门槛比 SESSIONS 列的四项多了契约、账本、manifest 三组，以及 `evaluate` 的参数校验一项（后者是审查中发现缺口后补的）。

### S4 门槛（M1）对已知复现的期望（验收时定，2026-10-09）

SESSIONS.md 对 `gates/s04.py` 的要求是"confirmed 族全部判 fail 且身份证据正确"。下表把每个族落到具体的复现和期望上，S4 写门槛时照这张表。"本机实测"都是 DuckDB 1.5.5、S2 的适配器、未经 CVE 的原始判定；探测脚本是 `.orch/scratch/` 下的 `m1_probe.py`、`m1_probe2.py`、`m1_probe3.py`（不入库）。

| 族 | 用哪份复现 | 本机实测 | M1 期望 | S4 要做的 |
|---|---|---|---|---|
| F1、F2、F7 | `recall_repros.json` | plan variant 判 fail / wrong_result，开关 `no_optimizer`，稳定 | fail | 第 3 档二分把开关细化成 fix set，与该条目的 `fix_set` 对照 |
| F9 | `recall_repros.json` | plan variant 判 fail，开关 `window_combine`，稳定 | fail | "调试开关一档"只是报告时的分层，不影响标签 |
| F11 | `duckdb/F11_merge_nmbs_rowid.sql` 里的 MERGE | plan variant 判 fail / crash，`error_class` 为 `InternalException`，开关 `no_optimizer`，稳定 | fail（crash） | 二分应落到 `build_side_probe_side`。写数据的语句只认 crash，见表后第 2 点 |
| F6 | `recall_repros.json` 的表结构和查询，补三行数据（表后第 1 点） | 不带谓词：plan variant 判 fail，开关 `no_optimizer`，`missing: 1`。带谓词 `o1.placed IS NOT NULL`：TLP、NoREC 判 fail，plan variant 判 pass | fail | 身份证据以二分结果为准，不要求等于该条目的空 `fix_set` |
| F3 | `recall_repros.json` | plan variant 判 fail，开关 `no_optimizer`，稳定 | invalid | 结果稳定，重跑筛不掉；要一条前提规则（ASOF 连接右侧有并列时取哪一行未指定） |
| F8 | `recall_repros.json` | 同一进程里三次判定相同（fail）；60 个新连接出现 8 种不同结果 | invalid | 新进程重跑不一致即可筛掉 |
| F5 | `recall_repros.json` | 200 个新连接里 20 次结果不对（10%）；plan variant 三次判定不一致，第一次是 fail，开关 `no_statistics` | invalid（重跑不稳定） | 第 1 档重跑加 threads=1 复判；把观察到的比例记进 `Label.cve` |
| F10 | `duckdb/F10_window_frame_underflow.sql` | 经适配器：试过的六种写法全部 invalid / nondeterministic，查询没有被执行。直接执行：前两条 ntile 语句都让进程以 0xC0000094 退出 | invalid；记为已知的召回缺口，不要求 fail | 新进程执行器要把"子进程异常退出"报成 crash，用这两条语句直接验证执行器（表后第 3 点） |

另有两份 `.sql` 文件按文件里的数据复现不出来，M1 期望 pass：
- `duckdb/F5_parallel_cte_offset.sql`：默认设置、threads=1、关优化器各 80 个新连接，全部返回 12 行。文件注释写的"Expected: 8 rows"是错的，正确行数就是 12。
- `duckdb/F6_null_exists_notin.sql`：默认与关优化器都返回 `[(1, 1)]`，三个 oracle 都判 pass。文件声称的"12 行对 8 行"出自原始见证，那份数据不在仓库里（全仓库只有文档提到 σ 键 `ab630f7b`）。

几点说明：

1. F6 的补充数据：`INSERT INTO orders VALUES (2, 1, -1e308, 'a', DATE '2021-06-15'), (3, NULL, NULL, NULL, NULL), (9, 1, 0.0, 'a', DATE '2015-05-05')`，照门槛用例 `metrics_small` 的三行改的。带谓词的形态把选择列表换成了 `o1.order_id, o1.amount`。这是重建的复现，不是原始见证；它很可能就是 F1 的机制落在 F6 的查询形态上（账本自己也这么猜）。二分落到 F1 的 fix set（`deliminator`、`filter_pushdown`）就把 F6 记成与 F1 同一机制。
2. plan variant 在同一个连接上依次跑各个变体。MERGE 这类写数据的语句每跑一次都改数据，后面的变体看到的是改过的表，结果比较不可信。S4 第 1 档的前提检查里，非 SELECT 语句只接受 crash，wrong_result 候选一律判 invalid。
3. F10 不要求判 fail 的原因：旧的确定性筛查（`oracles/determinism.py` 的 `has_nondeterministic_tiebreak`）把窗口里 ORDER BY 之后的帧子句也当成排序键，探测语句执行失败，于是判"不确定"。凡是显式写了帧的窗口查询都是这个结果，哪怕排序键唯一、写的就是默认帧。要让 F10 判 fail 得新写一段识别帧子句的筛查，这是新的判定逻辑，与 PLAN.md 总原则第 2 条"判定代码只搬不改"冲突，用户没有明确同意就不做。现状偏保守：只会少判，不会错判。
4. F5 判 invalid 是 PLAN.md 标签规则的直接结果（"重跑不稳定或结果不确定的也归此类"）。后果是 F5 这类时有时无的真缺陷在新框架里不计惊讶，理论学不到它；评估时把它和 F8 一起算作"不稳定"一类单独报告。

这张表与 SESSIONS.md 的字面要求有两处出入，都是事实逼出来的：F10 不判 fail（上面第 3 点）；F5 归到 invalid 一侧而不是 confirmed 一侧（上面第 4 点）。

### 未决问题（之后的工作需要知道的）

S13 处理与新发现（2026-10-19）：
- **由 S13 的决定了结或改派的旧条目**（原条目不删，以这里为准）：
  - "harness 要不要加结果行数上限"（S11 发现"单条实验可以很慢"）：用户定不加。
  - "SQLancer 对照组只有转录的汇总"：改为在服务器上重跑，S15 建臂；原始结果不再拷回。
  - "没有价格表"：S15 从官方价格页补；LLM 调用不设上限，成本照实报告。
  - "`RunData` 一次读入整个账本"、"网格的 `surprise` 格没有墙钟强杀"：S15 处理。
  - "M4 冒烟的数字不能拿来比较"、"纯 LLM 对照组在 DuckDB 1.5.5 上 16 条用例没有一个失败"、"离线去重与覆盖度量的门槛样本很小"：正式实验的规模与预算已定，见 `EXPERIMENT.md`。
  - "原 CoevoDB 对照组在 Windows 上 Version differential 恒为 disabled"：原 CoevoDB 不再评估，不再影响结果。
- **S13 新发现**：
  1. `CLAUDE.md` 有两处过时：开头写"`SESSIONS.md`：12 个实施会话的范围"，"引擎环境"只有 Windows 路径、没有服务器。"grok 不登录服务器"目前只写在 `EXPERIMENT.md` §7 与 `PLAN.md` §9，没写进 `ORCHESTRATION.md` 与 `CLAUDE.md`。这两个文件要用户同意才能改；建议 S14 搭完服务器时一起改。
  2. SQLancer 是否支持 DataFusion 没有核实（S15）；不支持的话 E5 少 5 格。
  3. SQLite 的 Version differential 旧版没定（S17 选）。
  4. 消融（E3）与 E1 的 `full`、`nollm` 不在同一批里跑，靠固定的每格 CPU 份额与线程数保证条件一致；报告里要写明。
  5. 本机重启后 PG 参照不会自己起来，S13 开工时碰上了（13 条测试失败）。开工检查先跑 `pg_ctl status`。
  6. 服务器上标准库 `sqlite3` 用系统库；版本与 Windows 上的 3.51.0 不同时，Cross-DBMS 的参照结果可能变，回放检查会过不了。S14 要单独钉住。
- **S14 处理与新发现（2026-10-19）**：
  - 上面第 6 条已解决：服务器上的 SQLite 3.51.0 按 Windows 的编译选项自编，source id 相同（SERVER.md §2）。
  - 上面第 1 条（已解决，`s15-done-r3`：用户同意，照稿写入；原文：）`CLAUDE.md`、`ORCHESTRATION.md` 与 `tools/orch/grok_worker.py`（DENY_BASH 加 ssh、scp、rsync、sftp）的改动稿在 `framework/surprise/docs/orch/s14/claude_md_proposal.md`（S14 收尾消息里也贴了）。用户后来改了服务器分工（PLAN §9 补充一条），改动稿已按新分工写。
  - 新：`.gitignore` 的 `*.log` 会挡住证据目录里的日志；S14 的四个日志是 `git add -f` 加进去的。以后的证据日志同样要强制加入，或者在 S15 给 `.gitignore` 加一条例外（不在 S14 范围）。
  - 新：本机 `.venv` 继承 anaconda 底座（`include-system-site-packages = true`），服务器的 venv 不继承、包逐个钉住。以后往 Windows 的 anaconda 里装或升级包，会让两边对不上，S14 的 `env` 组会在本机失败。
- **S15 处理与新发现（2026-10-19）**：
  - 已解决：S11 发现的"`RunData` 一次读入""网格的 `surprise` 格没有墙钟强杀""没有价格表""SQLancer 对照组只有转录的汇总"（现在真跑）；S13 第 2 条（SQLancer 支持 DataFusion，但钉在 40.0.0，S17 定）；S14 的"`*.log` 挡住日志"对 SQLancer 样例与驱动测试数据加了例外（证据目录的日志仍要 `git add -f`）。
  - 新 1（已解决，`s15-done-r3`：用户同意，CLAUDE.md 与说明模板都补上了）：**`CLAUDE.md` 执行者模式"不靠改测试让测试通过……认为某个测试本身有错，就写进报告，停下"对 codex 不够清楚**：s15-sqlancer 的执行者把它套到自己本包新写的测试上，停下等编排者。建议补半句："指基线里已有的测试与门槛；本包新写的测试照常修改，只要仍检查说明要求的东西"。要用户同意才能改。
  - 新 2：codex 的 execpolicy 规则管不了它自己的编辑工具，禁区全靠审查按 diff 核对（ORCHESTRATION §11）。五个包都没有碰禁区。
  - 新 3：**SQLancer 在 DuckDB 1.5.5 上 10 分钟报出的 7–8 份日志全是工具问题或预期外报错**，没有一份转成用例。E1 的 `sqlancer` 臂很可能 24 小时也是 0 个家族；这不是驱动的问题，报告里照实写。
  - 新 4：S15 的 `stream` 组读 `results/s08/longrun-s10code`（只在 Windows 上），在服务器上必然失败；要在 Linux 上量内存就把它拷过去。
  - 新 5：直接 Ctrl-C 网格本身（不是格到期）会杀掉在跑的格、不写它们的报告；续跑时这些格按原规则改名 `.stale-<k>` 重跑。要停正式实验，等格到期，或者只停个别格。
  - 新 6：codex 在 Windows 上用 PowerShell 5.1；它写的提交带 LF→CRLF 提示，不影响内容。
- **S19 新发现（2026-10-20）**：
  1. **欠费时网格不报警（提醒由 `s19-notify` 解决；中断这一格仍未做），LLM 臂照样跑满预算**：网关把每次调用失败记成 `error`，然后接着跑；`pure_llm` 在 2 小时里空转了 11,922 次调用、0 条记录，格仍记 `done`。`full` 在欠费后退化成没有 LLM 的运行，从 `cell.json` 看不出来。可能的修法：LLM 臂起跑前先试一次调用；连续失败到一定次数就中断这一格、写 `error.txt`。这要改 `roles/` 与 `experiments/`，不在 S19 范围里。
  2. **`calls.jsonl` 只记异常类名**（`TransportError`；`s19-notify` 改为记下传输层的消息）：`transport.py` 把 HTTP 状态写进了异常消息，网关记 `reason` 时只取了 `type(exc).__name__`，所以欠费、限流、网络中断分不出来。
  3. **同种子的 `nollm` 在不同并发下标签会分叉**（预实验 progress 逐条比 `case_digest`、oracle、`y`、`kind`）：s9101 的 c1 对 c4 在第 302 条分叉（cross_dbms：`fail/crash` 对 `invalid/unattributed_crash`），c1 对 c8 在第 1316 条（version_differential：`pass` 对 `invalid/direction_unknown`）；s9102 的 c4 对 c8 在第 957 条（plan_variant：`pass` 对 `invalid/unstable_rerun`）。分叉之后路径完全不同。分叉早晚与并发高低不单调（c1 与 c8 一致得比 c1 与 c4 久），像是个别用例本身不稳定，不像负载造成；要分清，得在同一并发下重复跑同一种子。影响：`EXPERIMENT.md` §4 的"同种子重跑结果一致"在实机条件下不成立（统计靠 5 个种子，不受影响，报告要改写这句）；§8 回放检查要求逐条相同，这几类标签可能过不了。超时（4–7 条）与重跑不稳定（1–2 条）的数量在三种并发下差不多。
  4. **`full` 的吞吐受 LLM 延迟限制**：每格 2 小时里有 85–115 分钟在等 LLM，执行数只有同种子 `nollm` 的 4%–26%。24 小时的正式格里，"每小时家族数"会把这个差别算进去，报告里要同时给"每千次执行"。

S12 发现、留之后的工作：
- **之前标着"留给 S12"的几件小修没有做**（不在 SESSIONS 的 S12 范围里）：`oracles/db_runner.py` 少一个空行、`targets/datafusion_runner.py` 的 `_norm` 遇 NaN / Inf 抛错、`oracles/differential.py` 写死 `<venv>/bin/python`——三处都在 `HASHED_PATHS` 里，改了就是解冻 harness，先问用户；`surprise/baselines/coevodb_v1/main.py`（原 `main.py` 第 142 行）同样写死 `bin/python`、`framework/config.yml` 的 `database.version` 写着 1.5.2——改的是原 CoevoDB 对照组的行为；`duckdb/F5_parallel_cte_offset.sql` 的"Expected: 8 rows"（应为 12）、`duckdb/F6_null_exists_notin.sql` 复现不出、`datafusion/DF-B` 注释漏了 NULL——复现文件被门槛读取，改前先核对 S02–S05 的门槛；`campaigns/pg_upgrade_mxact.py` 模块顶层 TypeError、`campaigns/pg_repack_mvcc.py` 导入即执行。
- **`evolution/__init__.py` 仍从 `archive.coevo.controller` 再导出 `CoEvolutionController`**：Hunter 导入 `evolution.dce` 时会连带导入整个归档的原型（移动前就如此）。仓库里没有任何地方用 `from evolution import CoEvolutionController`；删掉这一行能断开这条链，但算改旧代码的逻辑，要先问用户。用户验收 S12 时定下：现在不动，要断开时另开小修。
- **旧门槛与旧测试里按旧模块名列的检查已失去作用**：S08 / S09 门槛的 `LLM_MODULES` 里的 `agents.bug_hunter`、`evolution.co_evolution`、`guidelines`，S04 / S06 门槛 `FORBIDDEN_IMPORTS` 里的 `coevo`，`tests/test_surprise_s08_eval_baseline.py`、`test_surprise_s08_loop.py` 里的同类名单，移动之后这些名字不可能再出现在 `sys.modules` 里。S12 门槛的 `isolation` 组按新名字补上了同样的检查；旧门槛与旧测试没有改。
- **`framework/` 下的历史文档仍是旧路径**：`RESEARCH_PLAN.md`、`BRIEF_coevo_framework.md`、`STATUS_AND_ROADMAP.md`、各份 PG 计划等描述的是迁移之前的系统，S12 只更新了两份 README、`AGENTS.md` 与新写的架构文档。
- **`framework/AGENTS.md` 里 zsh 与 `~/.config/coevo/secrets.env` 的说明是原 Linux 开发机的**，保留未删；本机（Windows）的说法另加了一行。
- **原 CoevoDB 对照组在 Windows 上 Version differential 恒为 disabled**（旧代码写死 `bin/python`，见第一条）：作为对照组的 `no_llm` 臂一直如此，S8 以来的基线都是在这个条件下跑的。

已解决（留作索引）：S11 发现的"S12 移动旧代码时要一起改的"——方案 A 下 `diagnosis/` 不搬，`metrics/dedup.py` 不用改；`old_no_llm.py` 经 `framework/main.py` 转发，也不用改；S11 的 `grid`、`dedup` 两组在会话分支上通过。S4 发现的"S12 移动旧代码时 harness 的 import 与 `HASHED_PATHS` 都要改"——方案 A 下 `agents/bug_fixer.py` 留在原位，没有解冻。S1 沿用第 5 条（文档里的 `scripts/pg_*.py` 旧路径）在 `framework/AGENTS.md` 里改到了 `campaigns/`。沿用自 S0 与规划会话的"`coevo/` 被 `tests/test_verified_loop.py` 依赖，S12 再归档"——已归档到 `framework/archive/coevo/`，测试改了导入、照旧通过。

S11 发现、留后续会话：
- **M4 冒烟的数字不能拿来比较**：每格 1 分钟、每臂 2 个样本，新框架与原 CoevoDB 每小时都是约 30 个家族（MWU p = 1.0）。正式比较要长得多的格子与更多种子；SESSIONS 把 24 小时正式实验排除在 S11 之外，S12 的范围里也没有它，什么时候跑、跑多大，要用户定。
- **`RunData` 一次读入整个账本与进度**：3 小时长跑（8600 条）的 `ciao` 组 26 秒，可以；24 小时的运行（约 7 万条）要改成流式读，否则内存与时间都会成问题。
- **RQ6 的边界真值只有 F2 一条**：其它已知缺陷没有合并了的上游修复。F2 的假设判为"过窄"，是因为出生时的 S 是整条 φ，要等理论泛化之后再量才有意义；长一点的运行里再看。想让这个指标有统计意义，要找更多"有上游修复、能写出修复条件"的缺陷。
- **家族划分一致性在网格里没有人工真值**，报告留空。S8 的 `ledger` 组有 24 条人工裁定的失败、10 个人工家族，可以当一份真值接进报告，没有做。
- **SQLancer 对照组只有转录的汇总**（35 次运行、0 个缺陷），没有逐次运行的家族数与时间。要做"每小时家族数"的检验，得把原始结果（`results/sqlancer_strong/`）拷回来，或在本机重跑 SQLancer。用户验收定下：正式实验之前把原始结果拷回来。
- **没有价格表**：`deepseek-flash` / `deepseek-v4-pro` 的单价不知道，报告里美元一栏是空的，只有 token。网格配置的 `prices` 键已经能用。
- **网格的 `surprise` 格没有墙钟强杀**：时长靠主循环自己的 `--max-minutes`；原 CoevoDB 的格到点强杀。主循环卡在某一条实验上（见下一条）时整个网格会等着它。
- **单条实验可以很慢**：长跑第 8392 条（细化车道的 cross_dbms 用例：2000 行表的 `t1.id <= t2.id` 自连接，约 200 万行结果）用了 941 秒，第 1 档重跑 5 次加单线程一次，每次都在几个引擎上跑完整结果再比较；比较结果是两边各有约 150 万行对不上，`VARCHAR[]` 的跨引擎表示是不是原因没有核实。harness 没有结果行数上限，它是冻结的。用户验收定下：S12 不动，规划正式实验时再定要不要加上限。
- **推理模型在密集的开放式生成提示上会推理不止**：纯 LLM 对照组的头两版提示让 `deepseek-flash` 把 16000 / 32000 的上限都推理完、正文为空，降温也不管用；改成短而"先给答案"的提示才好。实现器（S9 常数 8000）在 M3 里截断过 3/36，可能是同一个原因；改别的角色的提示要重录对应的缓存。
- **纯 LLM 对照组在 DuckDB 1.5.5 上 16 条用例没有一个失败**：只录了种子 0 的 4 次调用，样本太小，什么也说明不了；正式实验里它的预算要与其他臂一样按墙钟给，调用上限按预算定。
- **离线去重与覆盖度量的门槛样本很小**：去重只有 3 条失败（σ 与成员检验的差别看不出来）；覆盖度量只重放 4 条上游测试，equivalent_query 在两个版本上都是 4 条 invalid。正式跑要用长跑的账本与整个 `duckdb:test/` 前缀。
- **σ 的引擎名固定为 `duckdb`**：`metrics/dedup.py` 用 `SignatureEngine` 的默认引擎名。只在同一次运行内比较键，结论不受影响，但 DataFusion 运行的键里引擎名不对。
- **`metrics/rq.py` 有两处可以简化的重复**：理论家族键自己按 `dups.new_families` 的规则重算；`recall.score` 用 `inspect.signature` 判断要不要传词表。`s11-fixes` 合并后两处都能直接调用。
- **`loop.py` 的 `raise pending from None` 丢掉原始异常自带的 `__cause__` 链**；`error.txt` 在写报告之前已存下完整 traceback，排查不受影响。
- **`llm/pure_llm.jsonl` 不记使运行停下的那次 `blocked` / `miss`**；那次调用在网关的 `calls.jsonl` 里。
- **S12 移动旧代码时要一起改的**：`baselines/old_no_llm.py` 起旧主循环、`metrics/dedup.py` 导入旧 `diagnosis/signature.py`，S12 把旧代码移到 `baselines/coevodb_v1/` 后这两处的路径要跟着改，S11 的 `grid`、`dedup` 两组要仍然通过。
- **S8 门槛的 `longrun` 与 S11 的 `ciao` 都绑着 S8 长跑的产物**：之后改 `hunter/`、`diagnoser/`、`experiments/`、`harness/`、`theory/`、`features/` 的任何一行，都要再按 S8 验收的办法重跑长跑、重钉，再跑这五组。

已解决（留作索引）：S9 验收的"请求总时限"、S10 发现的"存储 `save` 不耐瞬时文件错误、主循环盖掉原始异常"与"`metrics.dups.new_families` 不认扩展词表"三条在 `s11-fixes` 解决（见 S11 一节）；S10 发现的"S8 门槛的 `longrun` 与代码摘要绑定"按 S8 验收的办法重跑重钉了一次（b2e55ce）。

S10 发现、留后续会话：
- **理论存储的 `save` 不耐瞬时文件错误，主循环会把原始异常盖掉**：长跑第一次重跑在第 6526 条之后中断。`save` 已经写了 `passes/` 的两个文件、还没写 `head.json` 时失败；主循环接着写报告，`metrics.dups.new_families` 用 `Workbench.open` 读存储，报版本不一致，这个异常把原始异常盖掉了（`run` 里 `_write_report` 抛出时 `state.exc` 丢失）。原因没能确定，判断是负载下的一次文件错误（Windows 上 `os.replace` 遇到被别的进程打开的文件会失败）。可选的修法：`theory/store.py` 的 `_write_text` 在 `PermissionError` 时短暂重试；`experiments/loop.py` 在写报告失败时先把原始异常写出来。后者改的是 `experiments/`，又要重跑长跑重钉，宜与 S11 自己对这几个目录的改动一起做。产物在 `results/s08/longrun-s10-crashed`（不入库）。用户验收时定下：两处都在 S11 开头修，与 S11 对这几个目录的其它改动合在一起，只重跑一次长跑。
- **oracle 发明者的验收会把引擎缺陷当成"改写不等价"**：`({p}) IS TRUE` 在种子语料第 183 条上被 DuckDB 1.5.5 的已知错误（F1 家族，`filter_pushdown` / `deliminator`）挡下，一条正确的模板没收下。PLAN 决策 9 定的是"多引擎一致"，规则没有改；接上证明器、或改成"多数一致且异类是单个引擎"，都要先问用户。反过来看，这也是一次 oracle 发明者顺带撞上真实缺陷的例子。用户验收时确认：按 PLAN 决策 9 暂不改规则，接上证明器时再定。
- **oracle 发明者收的两条规则都是提示里的例子**（`SELECT * FROM ({q}) AS llm_sub`、CTE 包裹）。提示给了例子，模型就照抄。要它发明新东西，S11 做评估时可以去掉例子或只给一种形状，再比较收下的条数。
- **收下的规则在 DataFusion 上用不上**：Equivalent query 的候选只从探索与迁移车道来，DataFusion 没有种子（探索车道空）、单引擎时没有迁移。要让 DataFusion 用上发明的规则，得让细化 / 泛化或实现器的候选也挂 `llm:*` 规则，属于改车道规则。
- **`metrics.dups.new_families` 不认扩展词表**：带 `--vocabulary` 的运行里，它用默认词表打开理论会报摘要不符；主循环已在这种运行里改用同一个 `Registry` 计数，但 `metrics/` 本身没改。S11 做指标时让 `metrics/` 接受词表（或从 run 的 manifest 读词表文件）。
- **词汇发明者在实机上没触发过**：M3 里没有家族攒到 2 条矛盾通过；只在门槛的脚本组与执行者的 1 次真实调用里走通过。它只做 AST 层的正则特征；"左侧重复数多于右侧"这类数据性质特征（S6 的实机例子）表达不了，要支持就得给注册表加一种能在库上计算的定义。
- **词汇发明者把整次运行的语句都记在内存里**，查重是线性扫描；几万条的长 run 里会慢。S11 的长时间带角色运行之前量一下。
- **探索先验在 M3 里只结算了 9 条**，没到校准门槛（20 条），权重一直是初值 0.5；Brier 0.0068 对参照 0.0001（参照几乎总对，因为大多数实验都通过）。按现在的规则，满 20 条之后这样的先验权重会降到 0。S11 的 Brier 与校准曲线要在更长的运行上看。
- **实现器的 8000 上限**（S9 常数）在 M3 里截断了 36 次里 3 次（`no_json`）。没有改（改 S9 常数要动 S9 门槛的常数表）；S11 若要提，同时改 `gates/s09_cases.py` 的表并记一笔。
- **M3 的回复缓存与 S9 的提示共享缓存键规则**：提示的任何改动（包括角色常数里不进缓存键的 `max_tokens`、温度）都会让门槛的 `m3` 重放失效或拿到旧回复；要改这些角色的提示或上限，就得重录 `gates/s10_llm/m3`。
- **S8 门槛的 `longrun` 仍与代码摘要和 harness 哈希绑定**：S11 改了 `hunter/`、`diagnoser/`、`experiments/`、`harness/`、`theory/`、`features/` 的任何一行，都要再按 S8 验收的办法重跑长跑重钉。

S9 发现、留后续会话：
- **传输没有每个请求的总时限**：
  - `DeepSeekTransport` 用的是旧 `BaseAgent` 的 httpx 客户端，`timeout=300` 管的是两次读之间的间隔。
  - DeepSeek 排队时会一直发 keep-alive，所以这个超时不会触发。冒烟时一次 strong 档调用 900 秒没有任何内容。
  - 要在长 run 里用 strong 档，先在 `roles/transport.py` 里加每个请求的总时限（旧的 `agents/base_agent.py` 不改）。用户验收时定下：最晚在 S11 做模型强度比较之前加上。
- **`deepseek-v4-pro` 时好时坏**：一次排队 15 分钟，一小时后 1.8 秒就开始输出。两个角色现在都用 fast 档，见 S9 一节"PI 已自行核查"第 2 条。
- **缓存键不含温度与 token 上限**（PLAN 定的是"提示哈希 + 模型 + 种子"）：
  - 只改温度或 `*_MAX_TOKENS` 时，旧缓存照样命中，拿到的是旧设置下的回答。
  - 要重新录，就换缓存目录。门槛的 `gates/s09_llm/` 是按现在的常数录的。
- **提示里不能有随运行而变的东西**：记录号、假设号、时间戳都会让缓存键变，重放就失效。S9 的猜想者提示因此不带这些编号（门槛 `conjecturer` 组查过）。S10 的四个角色照此办理。
- **开着角色的长 run 很快会撞上上限**：短跑 20 次选择就用了 25 次调用，默认上限是 200。到了上限之后角色全部被挡下，循环照常跑（门槛 `wiring` 组查过上限为 0 的情形），只是之后就没有 LLM 了。S11 跑带角色的评估时，要按预算定 `--llm-max-calls`。
- **猜想的预测里可以出现 plan 层字面量**（词表允许）。实现器只写 SQL、挑不了计划，这类预测作 bet 时可能总是 `spec_unmet`，只能等探索碰上，可能一直是 open。
- **DuckDB 的选源取的是文件开头**：按 fix set 里的优化器名查 `roles/sources_map.py` 找文件，每个文件取开头的 400 / k 行。DataFusion 一侧按特征定位到函数（如 `fn intersect_or_except`）。DuckDB 也要定位到函数的话，得给每个优化器补一个函数名标记，没有做。
- **DF-A 在开着角色的短跑里开了两个家族**（h1、h3）：第 10 条的失败没有右侧 NULL，落在 h1 的 G 之外，于是另开了一个身份相同的家族。这是 S6 发现里"身份一致但落在 G 之外"的实机例子，合并要靠 MDL。
- **`python -m surprise.roles.implementer` 会打一条 runpy 的 RuntimeWarning**：`roles/__init__.py` 已经导入了这个模块。无害，没有改。
- **长跑门槛仍与代码摘要绑定**：S10 改了 `hunter/`、`diagnoser/`、`experiments/` 的任何一行，S8 门槛的 `longrun` 组又会失败，要按 S8 验收的办法在 LLM 全关时重跑 3 小时长跑、重钉哈希。
- **门槛 `replay` 组现跑一次 21 条的循环**（DataFusion，回复全从缓存来），`replay` 约 42 秒、`wiring` 约 44 秒，`surprise.gates.all` 因此多了一分半钟左右。
- **重跑的长跑在第 2937 行与 S8 分叉**：同一条 plan variant 用例，一次判 `invalid / unstable_rerun`，一次判 pass。harness 的第 1 档重跑不稳定会让同种子的长跑不可逐行复现；S8 的 `determinism` 组只在短跑上查同种子一致。

S8 发现、留后续会话：
- **DuckDB 1.5.5 的 `window_self_join` 错误结果**（复现与数字见 S8 一节）：没有对外报告，也没有写进 `duckdb/` 复现目录或 M1 表；要不要报告、要不要把它加进已知集，由用户定。用户验收时确认维持现状：不报告、不加。
- **无效率高**：长跑 52%，召回 run 47%。
  - 按原因：`query_error` 1892、`not_applicable` 1765、`nondeterministic` 413、`insufficient_engines` 382，其余合计 162。
  - 按 oracle：Equivalent query 1779/2053（87%）最差，其中 1537 条是 `not_applicable`（选中的改写规则套不上这条语句）；Cross 735/1077，主要是 `insufficient_engines` 382（参照引擎跑不了 DuckDB 方言）与 `query_error` 228。
  - Hunter 的 `P_valid` 来自理论的 `p_invalid`（S6 的 Kᵛ）。学得太慢的话，要给 oracle 与用例形态加一个更直接的有效性先验，可以由 S10 的"探索先验"接管。
- **探索车道占了 99%**（8804/8900），边界探针只有 96 条。原因有三：
  - 变异算子对已知家族的父本能改出的变体很少，一个父本 19 个上下，很快就做过了；第 6927 次那一轮有 36 个候选因为"已做过"被拒。
  - 新颖性抽签又拒掉一批。
  - 待定区之外的变体直接丢弃。
  - 后果：长跑后半段的曲线贴着 0.01 比特，新家族全靠探索撞上。S9 的实现器（spec → SQL）就是来补这一块的。
- **细化 / 泛化候选可能落在别的假设的确认区**：车道按生成它的假设定，打分按整个理论，这时 D = 0、value = 0。只有它一个候选时仍会被选上（长跑 2 次）。Hunter 可以在生成时就按理论的预测区过滤，这属于改车道规则，没有做。
- **没有 fix set 的家族太多、身份太粗**：长跑 12 个家族里 9 个没有 fix set，其中 6 个的形状键都是 `wrong_result|-|both`、2 个都是 `error_mismatch|InvalidInputException`。重复率裁判把它们算作重复，对新框架不利；它们是不是同一个缺陷没人知道。S7 记的"无开关的身份太粗"仍是根子。
- **误吸收**：长跑 3 条失败同时挂在两个无 fix set、形状相同的 cross_dbms 假设下（h23、h25）。规则没有改，见 S7 发现的第一条。
- **Diagnoser 的 revise 在实机上几乎不被接受**：长跑提了 2 条、拒 2 条，召回 run 提了 4 条、接受 1 条。被拒的 5 条都是 `no_gain`、长度变化 0：最小化用例的 φ 仍盖住原 S 的全部字面量，共同部分就是原 S，提议等于没改；接受的那条把 S 缩了一个字面量（长度 −7.4 比特）。无 LLM 的 Diagnoser 只有这一招，S9 的猜想者要接上的就是这一环。
- **召回漏了 F7 / F7_file**（`common_subexpressions,expression_rewriter`）**与 F9**：60 分钟的 run 里没有生成触发它们的构造。F9 的触发面很宽（S2 第 12 条：排序键唯一的普通窗口计数），漏掉说明种子语料与变异算子很少产出带 `OVER (ORDER BY ...)` 的窗口查询。
- **旧系统基线是到点强杀的**（`ended: killed`，`returncode 1`）：`bugs.jsonl` 的最后一行可能是半截。`old_reports` 会忽略截断的最后一行，这次 11 条都完整。
- **第 3 档里崩溃与超时的复核很慢**：长跑最慢的五次各用 2–7 分钟，都是 crash / timeout 的重跑与最小化，五次合计约 19 分钟，占墙钟的 11%。S4 记的"每次原始判定起一个进程"在长跑里实测平均每条 1.2 秒，没有成为瓶颈。
- **`loop` 不支持续跑**，输出目录必须为空，中断了只能整个重跑。理论存储每 100 条切一代，可以从最近一代恢复，没有做。
- **长跑门槛与代码摘要绑定**：`longrun` 组要求 manifest 里的代码摘要等于当前 `hunter/`、`diagnoser/`、`experiments/` 的代码。之后的会话只要改了这三个目录，S8 门槛的 `longrun` 组就会失败，得重跑 3 小时长跑再钉哈希；不想重跑，就要先问用户怎么处理旧门槛。`sawtooth`、`duplicates` 用同一份产物，不查代码摘要。用户验收时按编排者的建议定下办法（DECISIONS 的 S8 验收一条第 (4) 项）；S9 已按它重跑并重钉一次。
- **产物不入库**：`framework/results/s08/` 被 gitignore，门槛只钉哈希。换机器或清了目录，四个产物组就会失败；要保留就另行备份这个目录（386 MB）。用户验收时确认：产物不入库，备份由用户自己做。

S7 发现、留后续会话：
- 误吸收仍在（规则没有改）：没有 fix set 的假设按失败类别、错误类别、行为形状认正例，所以 (a) 一条已经被归属测试判给有 fix set 的假设的失败，只要落在某个无开关假设的确认区或待定区且三项相同，也会被它当成正例，把它的 S 泛化掉；(b) 作用域里通过还少、G 还松的时候，形状相同的另一种缺陷会被吸收进来而不是开新家族（实机例子：DF-F 进了 DF-D 的假设）。数字见 S7 一节"实机回放的数字"。可选的修法是在 `Theory._update_hypotheses` 里加一条"归属测试已经判给别的假设的失败，不再算其他假设的正例"，它改的是 S6 的规则，先问用户。MDL 的拆分只在"簇与簇之间"落了足够多的通过时才会把并错的假设拆开（三十五条以上）。
- 没有开关的身份太粗的另一面：`DF-D_where`（只少行）与 DF-D（少行多行都有）是同一个缺陷，却因为形状不同分成两个家族。这是与人工账本唯一的出入。要更细或更稳的行为画像得在理论层另算，或解冻 harness。
- 回滚会给"被回滚的编辑之后才开出的家族"换编号（计数器不回退、重放时重新铸号）。账本里指向旧编号的第 2 档归属结果，对有 fix set 的假设就读不出来了（记为身份未知，不学）；没有 fix set 的假设靠标签自己的三项，不受影响。要保住就得让重放时"同一条记录开出的家族沿用原编号"，需要给 `Theory.observe` 加一个指定编号的入口。
- 工作台把观察日志全部留在内存里（每条的 φ 与去掉 detail 的标签），`journal.jsonl` 只增不减，一条观察约 1–1.5 KB。S8 的长 run 之前先量；接受检验每次要扫编辑所在作用域的全部记录（上限 1000 条留出记录是对预测次数的上限，不是对扫描的上限）。
- `Theory.to_dict()` 每次都带上全部记住的通过，所以 `Theory.version`、`store.save`、每次接受检验前后的状态比较都与通过的条数成正比：实测 1 万条通过时 `version` 一次约 47 毫秒，`save` 一次约 157 毫秒。S8 每条实验都要算一次版本号、存一次盘。需要的话把通过改成追加写、版本号改成增量哈希，属于理论层，不涉及冻结区。
- 存储没有崩溃恢复：`save` 先写各文件、最后写 `head.json`，中途被杀的话下次 `load()` 会因为版本号对不上而拒绝（不会读到半截状态），但要人工处理。可以从最近一代的快照加日志重放恢复，没有做。
- 押注"落在新 S 里的实验会失败"只兑付一次：兑现之后，这条编辑的 S 里再出现多少条通过都只是矛盾（4.32 比特一条），要等 MDL 的修复候选攒够了才动。确认区的 0.95 对这类假设是偏高的（实机例子：F2 的假设，落在 S 里的 9 次实验有 4 次通过）。校准留给 S11 的 Brier 分数；要不要让确认区的概率随矛盾数下调，属于改 S6 的常数与规则，先问用户。
- `contradictions` 里既有落在 S 内的通过，也有落在 S 内、身份不一致的失败（S6 的规则如此）。MDL 的修复只看前者。读这个字段做统计时要自己按标签分开。
- 同作用域、同身份、由规则各自开出的两个家族，几乎不可能被 MDL 合并：第二个是因为落在第一个的 G 之外才开出来的，而"在 G 之外"就意味着把两者的 S 并起来会盖住某条已知的通过。合并实际能发生的场合是：缺某一层 φ 而没被吸收的失败、编辑造出来的假设、G 被截断之后。实机回放里两对候选（DF-A 与 DF-D_where 的假设，DF-D 与 DF-F 的假设）都被留出记录拒掉。
- `add`（凭空加一个假设）的候选正例取"同作用域里身份一致且落在 S 内的全部失败"，包括已经属于别的假设的；这些记录之后归谁，按"归属测试点名的优先，否则最早的假设"定。S9 的猜想者如果常用 `add` 而不是改写规则开出的家族，会出现同一批失败挂在两个假设下。
- 预测时"负责的假设"取待定区里最早的那个（S6）。实机回放里有两次因此先对一个不相干的假设做了归属测试、不一致、白做了一次第 3 档画像（约 2.5 秒），之后才被真正的家族吸收。S8 的主循环可以在待定区有多个假设时挑身份更可能一致的那个去问。
- 门槛的 `replay` 与 `ledger` 两组约 5 分钟，`surprise.gates.all` 现在约 11 分钟。期望值是在 DuckDB 1.5.5 / 1.1.3、DataFusion 54.0.0 / 50.0.0、PostgreSQL 16.15 上测的；`gates/s07_cases.py` 的裁定语句表每条都要求在本机判 fail，换引擎版本要同步改，改之前问用户。
- `verify_theory_manifest` 对常数的 `added` / `missing` 措辞方向（S6 留的）没有动：本会话没有改 `manifest.py`。
- PLAN 第 7 节的"31 个家族里能用合取表达的比例"只量了本机能回放的十族。

S6 发现、留后续会话：
- `evaluate_final`（已冻结）写账本时 `surprise` 字段恒为 `None`，也没有参数可传。现在的约定是 `p_t` 传 `prediction.p_fail_valid`，惊讶由 `surprise_bits(record.p_t, record.label.y)` 从账本重算（门槛的 `walkthrough` 组核对过）。S8 的主循环和 S11 的指标都按这个算；要把惊讶直接存进记录就得解冻 harness，先问用户。
- 作用域按 oracle 分的后果：同一个缺陷经两个 oracle 暴露会开两个假设，各自的 S、G 分别学。S7 做 MDL 合并与家族计数时，按身份（I，或三项画像）跨 oracle 归并；与人工账本比家族划分时也要先归并。
- 没有开关的假设身份很粗（失败类别、错误类别、少行 / 多行 / 都有）：DataFusion 上两个机制不同而形状相同的缺陷，只要 φ 落在对方的 G 里就会被当成正例吸收，把对方的 S 泛化掉。见证开关没有放进身份（它随哪个变体先见证而变，没有实测）。S7 回放人工账本时量一下这种误吸收有多少。
- `Theory` 把每个作用域里见过的通过（去重后的 φ）全留在内存里，建新家族时逐条回放，没有上限。S7 做存储时接管；S8 的长 run 之前先量内存与建族耗时。
- G 的初值是空合取：一个作用域里刚开出第一个家族、而此前见过的通过还少时，这个作用域里几乎处处是待定区（每次 1 比特），要靠后续的通过把 G 收紧。S8 的 Hunter 会看到 D 项在整个作用域里都接近 1 比特，这是预期的；惊讶曲线在新家族之后会有一段抬高。
- 建族时只回放通过，不回放别的家族此前的失败；那些失败再次出现时才作为反例作用到新假设上。
- 新家族的 S 取被执行语句的 φ，不取最小化之后的用例。`label.cve["minimize"]["case"]` 里有最小化的用例，S7 / S8 可以对它另行 `extract` 再建族（`new_family` 的 `phi` 参数就是为此留的；注意 S 必须覆盖触发它的那条失败，否则这条失败自己落在确认区之外）。
- `contradictions`（确认区里的通过）现在只记录，不收紧、不拆分。它是文档里"复核后收紧或拆分；解释不了就由 LLM 发明新特征"的入口，属 S7（MDL）与 S10（词汇发明者）。实机例子：手写的"EXCEPT ALL 且左侧有重复"遇到左右重复数相同的输入就通过，现有词表表达不了"左侧重复数多于右侧"。
- G 超过 64 个成员时被截断（`truncated`），待定区因此被低估。随机测试里 G 最大到 48；S8 的长 run 里统计一下有多少假设被截断。
- 身份一致但落在 G 之外的失败不被吸收（`effects` 里记 `outside`），有画像就另开一个身份相同的家族。合并这类家族是 S7 的事。
- 身份未知（假设有 fix set，而标签既没有对它的归属测试也没有画像）时什么都不学。S8 的主循环按 `walkthrough` 的写法给预测到的假设传 `attribution_request`，就不会落到这里。
- 分诊按大小：未探索区里 ρ 漂高的单元会出现 `boundary_move`、`duplicate`、`unexpected_pass` 而 `hypothesis_id` 为 `None`。S8 处理分诊结果时，`hypothesis_id is None` 的一律只当 R 的更新，不要去找假设。
- Kᵛ 的实验类只到"引擎加主构造"，`not_applicable` 也计入无效率（来源分开记了数）。S8 用 `1 − Kᵛ` 当 `P_valid` 时如果太粗，再细分是理论层的事，不涉及冻结区。
- `Theory` 要求 φ 的词表摘要与自己的词表一致。S10 验收新特征后词表摘要会变，旧的 φ（包括 `Theory` 记住的通过、账本里的 φ）就对不上了：S10 要定迁移办法（重新提取，或按词表版本分段）。
- PLAN 第 7 节的"31 个已确认家族里能用合取表达的比例"还没有量；S7 离线喂入已知复现时一并报告，压不了的记为样例家族。
- `registry=None` 时理论层的函数每次调用都新建默认词表；`Theory` 已经把自己的词表传下去。直接调用这些函数的代码（S8 的 Hunter）在循环里要自己传 `registry`。
- 理论状态只在内存里（`Theory.to_dict()` / `from_dict()` 是给 S7 的存储用的往返格式），按代快照、编辑日志、回滚、负记忆都还没有。
- `Theory.from_dict` 的校验只到键、版本号、词表摘要、计数与 `passes` 的写法：遇到重复的假设编号取后一个，遇到不是规范形式的假设静默规范化，不核对记住的通过里 φ 的词表摘要。`to_dict()` 自己的产物没有这些情况；S7 做存储时补上（审查时发现，没有为它返工）。
- `verify_theory_manifest` 对常数的措辞与对文件的方向相反：manifest 里有而现在没有的常数报成 `constant added`，现在有而 manifest 里没有的报成 `constant missing`；文件一侧（与冻结的 `verify_manifest` 一致）是"现在有而记录里没有"为 `added`。两种情况都报、都带名字，只是读起来别扭；S7 动这个文件时顺手对齐（审查时发现，没有为它返工）。
- `gates/s06.py` 的 `theory` 组把 R、Kᵛ、分诊在一串实验之后的状态逐项钉住了。S7 的回滚、合并如果要改"什么进 R""什么算反例"这类规则，就是改 S6 的门槛，先问用户。

S4 发现、留后续会话：
- 召回缺口：F10、F5、DF-E、DF-H、DF-J、DF-G 在新框架里不是 fail，原因见上面"已知的召回缺口"一节。评估（S11）报告召回时要把它们单列；要补上任何一个都得改旧判定代码或解冻 harness，先问用户。
- 每次 `evaluate_final` 的原始判定都起一个新进程，候选的重跑是串行的（数字见"成本"一节）。S8 跑长 run 之前先实测吞吐；需要常驻工作进程或并行重跑时要解冻 harness，先问用户。常驻进程会让 F5 这类"进程里第一次执行恒正确"的现象重新混进原始判定，并行会改变竞态缺陷的复现率，两样都要重新实测。
- ASOF 前提是保守的：USING 写法、连接键比较以外的任何 ON 条件、解析不了的右表，一律按违反处理。只会少判，不会把依赖未指定选择的用例确认成 fail。S8 生成 ASOF 用例时用 `左.列 比较 右.列` 的 ON 写法，否则全是 invalid。
- 第 1 档的重跑只比较目标引擎执行的语句结果，加上标签的判定与身份；参照引擎、旧版引擎各自的语句结果不在比较范围内。参照引擎自身不确定而判定和计数碰巧不变的情况理论上查不出来，实际需要两个独立引擎以相同方式一起变，没有见到过。
- 第 2 档的 `profile` 方式只比较失败类别、错误类别和 missing / extra 的符号组合，很粗。无开关引擎上两个机制不同但形状相同的缺陷会被判成同一身份；S6 的假设如果需要更细的行为画像，要在理论层另算（harness 已冻结），或者提出解冻。
- 复现判据对 plan variant 把"一侧成功、一侧报值依赖错误或超时"算作不一致。二分时这偏保守（不会把无关规则算成 fix）；最小化时可能把用例缩向另一种现象，由最小化后的原始判定再验证兜住（失败类别变了即 `not_reproduced_minimized`）。
- F9 的画像每次用满 120 次二分（约 3.8 秒）才得出"没有稳定 fix set"。S8 的探索会反复撞上这一族（见下面 S2 第 12 条），确认它是 F9 的便宜办法是第 2 档：给一个 `interventions` 为空、`behavior_shape` 为 `both` 的假设不够区分，建议 S6 用见证开关 `window_combine` 加错误类别建立假设，避免每次进第 3 档。
- 被哈希的旧模块有二十个，含 `agents/bug_fixer.py`（第 3 档以普通函数方式调用它的 `_minimize`，不构造 agent；`import agents.bug_fixer` 会连带导入 `httpx` 与 `llm.ledger`，只在第 3 档的子进程里发生）。S12 移动旧代码时这些路径会变：harness 的 import 与 `HASHED_PATHS` 都要改，属于解冻，先问用户，改完重新生成 `gates/s04_frozen.json`。
- `gates/s04_cases.py` 的期望值是在 DuckDB 1.5.5 / 1.1.3、DataFusion 54.0.0 / 50.0.0、PostgreSQL 16.15 上测的；`gates/s04.py` 的 isolation 组断言 F10 两条语句让子进程崩溃（Windows 上退出码 0xC0000094）。换引擎版本或换平台要同步改门槛，改之前问用户。
- 已解决：`.venv` 里装了 `sqlglot==30.21.0`（S5 开工时），manifest 的 `packages.sqlglot` 有值。换机器重建环境时要装同一版本：`ast:fn:<名>` 用的是 sqlglot 归一后的函数名，版本一变名字可能变。
- manifest 的 `packages` 是固定名单（duckdb、datafusion、pyarrow、psycopg2-binary、sqlglot）。后续层要记别的版本，在传给 `Ledger.start_run` 的 dict 上自己加键。
- `harness/manifest.py` 里的 PostgreSQL 默认 DSN 是从 `harness/oracles/pg_reference.py` 抄了一份的字符串；两处都已冻结，改端口要一起改（解冻）。
- `datafusion/` 的 DF-B SQL 注释漏了正确 bag 中的 NULL，旧文件不改，留 S12；门槛按实测包含 NULL。

S5 发现、留后续会话：
- harness 把重跑时退出码不同算作没有复现。Windows 上以 `exit()` 正常路径结束、而 DuckDB 工作线程还在跑的进程，约 0.5% 会以 0xC0000005 而不是原来的退出码结束（实测 400 次里 2 次；立即终止进程则 600 次全部一致）。所以一个靠正常退出路径死掉的真实引擎崩溃，有小概率被判成 `invalid / unstable_rerun`。方向是少判；harness 已冻结，没有改。S8 的长 run 里如果看到成批的 `unstable_rerun` 崩溃，先想到这一条。
- `Registry.load` 接受顶层是裸列表的文件（`save` 写的是 `{"invented": [...]}`），忽略条目里多余的键，空正则 `""`（对任何语句都命中）能登记。未验收的特征不会进 φ，所以现在无害；S10 定验收规则时把空正则和恒真正则挡掉。
- `framework/targets/datafusion_runner.py` 的 `_norm` 遇到浮点 NaN 或 Inf 会抛 `ValueError`，整次查询被记成出错。所以 DataFusion 上含这些值的表数据层是 `unavailable`，`data:value:non_finite` 在 DataFusion 上实际观察不到；同一个问题也会让 oracle 在这类数据上拿到执行错误。旧代码，S12 之前不改。
- 语料分布里最大的几个单元是 `…|none|unknown`：PostgreSQL 的 308 条种子这里没有 runner（只有语句层），DuckDB 的 784 条里有 252 条 setup 被 1.5.5 拒绝。S8 用种子做探索起点时，这些种子的 φ 只有语句层，单元的后两维是占位值。
- 单元的"计划算子类"按算子名子串归类，是照 DuckDB 的算子名写的；DataFusion 的 `HashJoinExec` 归到 `join`、`AggregateExec` 归到 `aggregate` 是碰巧子串对得上，`SortExec`、`WindowAggExec` 等要到 S8 接 DataFusion 探索时核对一遍。
- 发明特征的正则在每次提取时对整条语句 `re.search`，没有超时。S10 接 LLM 词汇发明者时要防灾难性回溯的正则（验收前先在语料上跑一遍并计时）。
- 语句层（`features/ast.py`）已知的小偏差，都不在被测语句的常见形态上，S8 生成探索语句时如果用到再修：`CREATE VIEW ... AS SELECT` 与 `COPY (SELECT ...) TO` 的查询被记成 `ast:subquery:scalar`；引用另一个命名窗口的命名窗口（`w2 AS (w1 ORDER BY a)`）不继承 `w1` 的规格；`INSERT ... ON CONFLICT DO UPDATE SET v = 3` 的赋值仍记成 `ast:cmp:eq`；兜底认 CTE 要求 `AS` 与括号之间有空白。
- sqlglot 把它不认识的语句（EXPLAIN、VACUUM、COPY 等）读成不透明的 Command：语句层状态是 `ok`，特征为空，不走兜底。作用域分析失败时（`ast.py` 里两处 `except Exception`）不记相关性、状态仍是 `ok`，没有任何标记；整份种子语料上没有触发过。
- `ast:fn:<名>` 用的是 sqlglot 归一后的函数名（`substr` → `substring`，`date_trunc` → `timestamp_trunc`），不是原文里写的名字。S6 之后写规格、S7 的 LLM 提假设时要用归一后的名字；sqlglot 升级可能改这些名字，manifest 的 `packages.sqlglot` 记着版本。

已解决（留作索引）：S6 留给 S7 的几件在 S7 定下并交付——理论状态的落盘、按代快照、编辑日志、回滚与负记忆；跨 oracle 的假设按 fix set 归并成家族；`contradictions` 由 MDL 的修复候选处理（收紧或拆分）；记住的通过随存储落盘（仍在内存里）；来路不明的状态由 `TheoryStore.load()` 严格拒收（`Theory.from_dict` 本身没有改）；误吸收与合取可表达的比例量过了，数字在 S7 一节。S3 记的"manifest 环境字段"与"Cross DATE 假候选"两条在 S4 解决（环境字段补齐；`incomparable_results` 前提）；S2 第 7 条（`Label.cve` 是占位）、第 11 条（没记间接依赖）在 S4 解决；S2 第 1、2 条（F10 与逐族期望）已由 `gates/s04.py` 落实。S2 第 6 条（惊讶取到无穷大要先截断）在 S6 不再需要：ρ、Kᵛ 与 0.95 / 0.5 都严格在 0 与 1 之间，惊讶恒为有限值；S5 留的"`features/limits.py` 的三个上限要不要进 manifest"在 S6 定为进（run manifest 的 `theory` 一节里的 `features.limits`）；S4 记的"F9 每次都进第 3 档"：从没有 fix set 的画像建出的假设，确认区里的重复走第 2 档的画像比较（零执行）就能确认，DF-A 上实测如此，F9 本身留给 S8 的实机 run 核对（S8 的 1.1.3 召回 run 没有撞上 F9，见"S8 发现"）。S7 留的"长 run 的吞吐先实测再定"在 S8 量过：长跑每条约 1.2 秒，没有随长度变慢；`Theory.version` / `store.save` 的线性开销与留在内存里的日志，在 8900 条的规模上都没有成为瓶颈，没有动。

S2 新发现：
1. `duckdb/F10_window_frame_underflow.sql`（2026-10-09 按实测改写）：直接用 duckdb 执行，前两条 ntile 语句都让解释器进程以 0xC0000094 退出，文件注释只把第二条描述成 INTERNAL 错误。经 `judge` 则不会崩：确定性筛查在执行之前就把它们判成 `invalid / nondeterministic`。所以这一族现在既拖不垮 harness，也抓不到，处理办法见上面一节的第 3 点。别的查询仍然可能让引擎进程崩溃，`evaluate()` 在进程内拦不住；S4 的新进程执行器和 S8 的运行循环要考虑这一点。
2. 已知复现在本机 DuckDB 1.5.5 上被这三类 oracle 抓到的情况，以及 S4 门槛对每一族的期望：见上面"S4 门槛（M1）对已知复现的期望"一节（2026-10-09 按实测重写；原先写的"F5 抓不到""F6 什么都复现不了""F11 没有试"都已更正）。
3. TLP 的 GROUP BY / DISTINCT 形态没有已知的失败复现，门槛只覆盖了它的 pass 与 invalid。
4. `(query, predicate)` 只在 TLP 认识的形态下能合成一条合法语句。例如带聚合的分组查询再给一个谓词，`full_query` 会拼出 `… GROUP BY b WHERE (…)`，执行报错，三个 oracle 都判 invalid。这是有意的（坏用例就是 invalid），但 S8 的 Hunter 生成用例时要知道。验收时定为维持不改：遇到 TLP 不认识的形态，把过滤条件写进 `query`、`predicate` 留空。
5. plan variant 的 28 个变体里，`ordered_agg_off` 的开关语句 `SET ordered_aggregate_threshold=0` 在 DuckDB 1.5.5 上报 Parser Error，这个变体实际是空操作：查询照默认设置跑一遍，被算进 `variants_compared`。这是旧代码变体表的问题，没有动。
6. 契约拒绝非有限的浮点数（JSON 表示不了 NaN 和无穷大）。S6 算惊讶时如果 P_T 取到 0 或 1，要先截断再写进 `ExperimentRecord.surprise`。
7. `Label.cve` 仍是空 dict 占位，四步（rerun、premise、minimize、profile）各自记什么由 S4 定。S3已给`INVALID_REASONS`追加untrusted_rewrite、direction_unknown、insufficient_engines、non_unique_outlier，共十一项；S4的重跑不稳定等来源继续往表里加，冻结之前可以改。
8. 已解决：S3 registry包已让`judge`和`evaluate`支持DuckDB/DataFusion，两引擎映射统一；SQLite/PG仅作参照，不作首发目标。
9. `oracles/forms.py` 依赖旧模块 `oracles.determinism` 里带下划线的两个函数（`_top_level_positions`、`_top_level_from_pos`）；`theory/contracts.py` 复用了 `harness/contracts.py` 里带下划线的序列化辅助函数。S12 整理旧代码、或 S4 之后想动这些辅助函数时要同步。
10. 种子语料在 DuckDB 1.5.5 上的无效率不低：差分核对的 196 个种子变异里有 72 个在 setup 阶段就报错。S8 用种子做探索起点时会看到很多 `setup_error`。
11. manifest 的环境一节只记了 Python、平台和三个引擎的版本，没有记 pyarrow 等间接依赖（`.venv` 继承 anaconda base，环境不完全可复现，见下面沿用的第 7 条）。
12. （验收时发现）F9 的触发面很宽：`SELECT id, count(*) OVER (ORDER BY v) FROM t1` 这样排序键唯一的普通窗口计数，plan variant 就在 `window_combine` 下判 fail（8 行全不同）。S8 的探索一碰窗口聚合就会反复撞上这一族，理论要能尽快把它归到一个假设里，否则预算会耗在重复上。
13. （验收时发现）显式写了帧子句的窗口查询一律被确定性筛查判成 `invalid / nondeterministic`，原因见"S4 门槛（M1）对已知复现的期望"一节的第 3 点。S8 生成用例时要么不写帧子句，要么接受这部分全是 invalid。
14. （验收时发现）`duckdb/F5_parallel_cte_offset.sql` 的注释"Expected: 8 rows"是错的（正确是 12 行），`duckdb/F6_null_exists_notin.sql` 的数据复现不出它声称的现象。两个文件都没有改，留给 S12 整理复现文件时处理。

沿用自 S1、仍然有效的（编号沿用 S1 交接里的）：
1. 要导入 `oracles.*` 或 `targets.*`，解释器里必须同时有duckdb和psycopg2。`.venvs/duckdb-1.1.3`两样都有；`.venvs/datafusion-50.0.0`两样都没有。S3保持此隔离，旧版DF子进程只直接导入datafusion与标准库，原始行JSON传回，主进程归一化；新入口version_worker.py已完成并独立验证。
2. 旧代码把旧版解释器写死成 `<venv>/bin/python`（`oracles/differential.py` 第 37 行、`main.py` 第 142 行），Windows 上是 `Scripts/python.exe`，所以旧主循环在本机 Version differential 恒为 disabled。决定：S12 之前不改旧代码；S3 的适配器自己按平台定位解释器（`gates/s01.py` 的 `venv_python()` 是现成写法）。
3. `campaigns/pg_upgrade_mxact.py` 第 55 行在模块顶层抛 TypeError；`campaigns/pg_repack_mvcc.py` 导入即执行。旧问题，没修。
5. 文档里还是旧路径 `scripts/pg_*.py`，留给 S12。
6. `gates/s01.py` 里写死了 41 个脚本、基线通过数 64、三个环境的版本号、`v1-baseline` 的提交号；`gates/s02_cases.py` 里的期望值是在 DuckDB 1.5.5 上测的。换引擎版本或再移动旧代码时要同步改门槛，改之前问用户。
7. `.venv` 是继承 anaconda base 的 uv venv，环境不完全可复现。
9. `oracles/db_runner.py` 少一个空行，S12 顺手补。
10. 执行者可以用脚本写文件，deny 规则管不到，靠审查兜底。

沿用自 S0 与规划会话、仍然有效的：
- 仓库没有配置远端，异地备份是用户的事。
- 新会话里 Claude Code 的安全分类器可能拒绝启动 grok（S1、S2 都没有被拒）。用户的长期批准记在 DECISIONS.md；再被拒就停下来问用户，不要绕过。
- 执行者的 shell 是 Windows PowerShell 5.1：没有 `&&`，中文输出乱码。
- `SESSIONS.md` 开头写的开场提示词路径不对，实际是同目录的 `RUNBOOK.md`。那是用户的文件，没有改。
- `framework/test_api.py` 在设置了 `DEEPSEEK_API_KEY` 时会真的调用 API；日常测试命令只跑 `testing/` 和 `tests/`。
- `coevo/` 被 `tests/test_verified_loop.py` 依赖；它的新进程执行在 S4 被吸收，S12 再归档。
- `framework/config.yml` 里 `database.version` 写的是 1.5.2，实际是 1.5.5；`database.old_venv` 是旧机器上的路径。
- PLAN.md 决策表：第 5 条（φ 用 sqlglot、正则兜底）、第 4 条（单元先粗）、第 2 条（φ 一侧在 S5，版本空间一侧在 S6）已采用；第 8 条里 0.95 / 0.5 与分诊阈值在 S6 定值并由门槛钉住，β 留给 S8；第 7、9、10 条仍是建议，到对应会话开工时再定（第 6 条 S4 已采用）。

### 给下一个编排者的操作提醒

S15 踩到的：

- **门槛数据提交后用 `git ls-files` 核对一遍**：`.gitignore` 的 `*.log` 把四份 SQLancer 样例挡在库外，主检出区有、worktree 里没有，执行者因此第一次派发就停下。
- **不要在 shell 的当前目录停在某个 worktree 时起后台任务**：后台任务继承当前目录，那个 worktree 在任务结束之前删不掉（`cleanup` 报 WinError 32）。进 worktree 跑命令用子 shell：`(cd .worktrees/<包>/framework && ...)`。
- **门槛的 `require(cond, f"...")` 会先求值消息**：消息里不能有读管道、跑命令这类有副作用或会阻塞的东西。
- **执行者中途退出（余额、网络）时用 `gw handover`**：原 worktree 与未提交改动保留，新会话先读懂再接着做；三个包都是这样完成的，比推翻重做省事。
- **codex 的审查包没有美元数**，只有 token；成本按 token 记。
- **改了 `experiments/` 的会话，长跑可以在最后一个碰 `hunter/`、`diagnoser/`、`experiments/` 的包合并后就起跑**，不必等全部合并；中途拿半截 `progress.jsonl` 与上一次长跑逐行比（去掉 `elapsed_s`），能提早看出全关时有没有变。

S12 踩到的：

- **纯移动的会话，先做一份不入库的参考移动**（`.orch/scratch/s12/ref_move.py`，在一个临时 worktree 里跑）：门槛在它上面先跑通、再拿几种故意的违规测一遍；审查时用 `git diff <参考提交> grok/<包号>` 对整棵树，几分钟就能确认执行者的改动与参考逐字相同，只剩措辞要读。
- **验收命令里，依赖主检出区产物的门槛组要单独标出来**：S8 的 `longrun`、`sawtooth`、`duplicates`、`recall` 读 `framework/results/s08/`，在 worktree 里必然失败。这次说明里让执行者跑整个 `gates.s08`，执行者如实报了 4 组失败；应当写 `--only no_llm constants scoring operators candidates lanes determinism`，产物组留给编排者合并后跑。
- **门槛里按键名清掉时间字段，用下划线分段匹配，不用子串**：`total_candidates` 含 "dates"，子串匹配把它当成了时间字段。
- **`git mv` 之后，主检出区的旧目录里会留下只含 `__pycache__` 的空壳**（worktree 里则是空目录，执行者删不掉——递归删除被 deny 规则拦下）。合并后在主检出区核对只剩缓存，再删；不删的话 `import coevo` 之类会以命名空间包的形式"导入成功"。
- **文档包可以与代码移动并行**：说明里写清"按移动之后的布局写"，并列出哪些路径在文档包的 worktree 里必然报"不存在"；合并两个包之后在会话分支上复核 `docs` 组。

S11 踩到的：

- **对照组或新角色的提示，派发前先用一两次真实调用试**：推理模型（`deepseek-flash`）对"规则很密、开放式生成"的提示会一直推理到上限，正文为空；提高上限、降温都不管用。纯 LLM 对照组因此作废两次录制、多开两个修正包。试出来能用的提示原文写进说明，由执行者逐字照用（`s11-purellm3` 一次就过）。探测脚本 `.orch/scratch/s11/probe_pure_prompt.py`、录制脚本 `record_pure.py`（不入库，密钥从注册表读、不打印）。
- **审查包标出"改写了断言"时，先读那几处再合并**，包再小也一样。这次两个纯 LLM 修正包是先合并后核对的（结论没变，顺序错了）。
- **写进 DECISIONS 的数字先核对日志**：`s11-runmetrics` 的花费凭印象写错，只能追加更正。
- **`gw cleanup` 报 `PermissionError`，多半是编排者的 shell 停在那个 worktree 里**：先 `cd /d/CoevoDB` 再清理。
- **门槛断言写得比实现能保证的更强时，换成更准的断言，不放宽**：`arms` 组原来要求 `--select-from` 的运行出现细化 / 泛化车道，源运行跑满之后候选可能为空；改成"每行 `select_p` 等于源理论的预测"，更强也不依赖运气。
- **长跑可以在只剩不碰钉住代码的包时起跑**：这次最后一个包只动 `baselines/`，长跑与它、与十几条用例的录制同时跑，没有出问题；但审查复跑与全量门槛仍然等长跑结束再跑。
- **CIAO 用主检出区的长跑核对 worktree 里的代码**：`.orch/scratch/s11/ciao_check.py`。

S10 踩到的：

- **长跑不要与审查、grok 包同时跑。** 第一次重跑与三个审查、两个包并行，第 3886 条在负载下判成 `timeout`、选择链与 S9 分开，第 6526 条之后理论存储写盘失败、整次作废。单独重跑就顺利。另外，改了 `features/` 或 `theory/` 的包没合并之前不要起长跑：长跑的 manifest 会核对这两层的代码哈希，钉不上。
- **长跑经报错记录脚本起**（`.orch/scratch/s10/longrun_wrapper.py`）：主循环写报告失败时会盖掉原始异常，脚本只包住这条路径、把原始异常写进文件，不改代码文件，manifest 的代码摘要不受影响。
- **录真实回复之前，先按 S9 的教训确认上限**：这次三个角色用 8000，录 M3 时 oracle 发明者唯一的一次调用、翻译者的第一次尝试都被截断。缓存键不含 `max_tokens`，改了上限要把被截断的条目删掉再录（`record.py m3 --keep-cache --drop-role 角色` 只删那个角色的条目，其余照旧命中，运行逐行相同）。
- **派发前想清楚包合并后测试会不会互相影响**：`s10-frame` 的测试假定"四个角色模块都不存在"，第一个角色包一到就失败（S9 是 `sys.modules` 的执行次序）。框架包的说明里要写明：测试不得依赖之后才会出现或消失的模块。
- **审查包对"用户批准的解冻"一样标"越界：禁区"**：`gw review` 见到 `s04-done` 就把 `harness/` 当禁区。以 `git diff s09-done-r2 -- framework/surprise/harness` 为准逐个文件核对。解冻之后要用 `python -m surprise.harness.manifest write gates/s04_frozen.json --run-id <名字>` 重新冻结，再跑 S04、S06 与 S10 `frozen`。
- **门槛按"运行结束时的归属"找家族**：S7 的编辑一律铸新编号，记录开出的假设号在被接受的 `revise` 之后就不在理论里了，用 `wb.owner_of(record_id)`。
- **小包可以用轻量审查**：`s10-caps` 只改三个常数，长跑在跑，用 `gw review --skip-tests` 生成审查包、编排者自己在 worktree 里跑 pytest 与相关门槛组，结果写进结论。

S9 踩到的：

- **派发前先用 `GET /models` 核对模型名**（不耗 token）。这次开工时定的两个名字都不存在，网关包因此返工了一轮。
- **推理模型会把推理 token 算进 `max_tokens`**。上限要先用几条真实调用试出来；只看回复长度会定得太低。
- **并行开发的两个包，各自都绿，合并后可能互相影响进程状态**：这次是 `sys.modules`，所以多了一个修复包。合并第二个包之后马上全量跑一次测试。
- **派发后改了门槛，worktree 里的门槛还是旧的**：返工意见里要逐条写明哪些组"预期失败"、为什么，免得执行者去动门槛或放宽测试。
- **在主检出区跑门槛与测试一律用 `../.venv/Scripts/python.exe`**。PATH 上的 `python` 是 anaconda 的，没有 sqlglot，这次跑错过一次。
- **真实回复录一次就提交缓存**，门槛从缓存重放：
  - 录制脚本在 `.orch/scratch/s9/record.py`（不入库）。
  - 录完先在没有密钥的环境里跑 `--only implementer_report dfa replay`，再提交。
- **给包密钥用 `spawn … --llm-key N`**：
  - 只给真要调用的包；N 是该包每个网关实例的上限。
  - 审查复跑、长跑、门槛照旧加 `env -u DEEPSEEK_API_KEY`。
  - 审查包的密钥扫描会按值比对密钥本身。
- **3 小时长跑放后台单独跑**。中途拿半截的 `progress.jsonl` 对 S8 的旧长跑做一次逐行对比（去掉 `elapsed_s`），能尽早发现全关时是否真的与 S8 相同。

S8 踩到的：

- **核对产物的门槛，在长跑中途就拿半截产物跑一遍。** 这次长跑跑完 3 小时才发现门槛的两处逐行检查比说明严。短跑里假设不重叠、保底位总有探索候选，查不出来。中途把门槛模块的 `require` 换成只记录不抛异常，对半截目录调用 `check_rows`，就能一次列出全部不一致。中途算了曲线与重复率，却没有跑逐行检查，这是漏掉的一步。
- **"返回 None 就停"这类语义，在说明里要写清是"真的无可再做"还是"这一轮没抽到"。** 第一次的召回 run 因此 7.7 分钟就停了，多花了一个修复包、一个小时。
- **长任务一律用后台任务**：3 小时的 `loop` 与旧系统基线都活到了结束并发来通知。三个运行同时跑互不干扰。命令前加 `env -u DEEPSEEK_API_KEY`。
- **产物的哈希用脚本钉**（`.orch/scratch/s8/pin.py longrun old recall`），钉完先跑 `--only longrun sawtooth duplicates recall` 再提交。`s08_runs.json` 提交时 git 会提示 LF→CRLF，不影响：门槛读的是 JSON 内容，哈希算的是产物文件。
- **跑旧系统要设墙钟上限、到点强杀**：旧系统的 `DuckDBRunner.setup` 没有超时，某些种子会长时间占满 CPU（10 分钟的探测里卡过两段，各约 3.5 分钟）。
- **`.venvs/duckdb-1.1.3-full`** 是在 DuckDB 1.1.3 上跑整个新框架用的；原有的 `.venvs/duckdb-1.1.3` 只装了 duckdb 与 psycopg2，跑不了新框架。

S7 踩到的：

- **参考模型用 shim 装进进程里的 `surprise.theory`（`.orch/scratch/s7/ref_shim.py`），新进程看不到它。** 跑门槛时把门槛里那几处起新进程的检查替换掉（`run_gate_ref.py`）；真实引擎的子进程只导入冻结的 harness，不受影响。
- **审查用的随机差分脚本先让参考模型自己跑一遍（`--self`）。** 这一步在派发第二个包之前查出了规格漏洞（分簇得到空的 S 会让 `compress()` 抛异常），来得及写进说明。
- **差分要放过说明没有规定的东西**（自拟的文本、浮点求和的末位），否则一轮在第一处假出入就中断，后面的路径都没比到；放过之后再看剩下的才是真出入。
- **性能问题门槛查不出来。** 审查时按下一个会话的规模（几万条）量一下每次调用的耗时：这次量出日志追加随长度线性变慢。
- **给理论层加常数之前，grep 一遍旧门槛与旧测试里对常数名单做了什么假设**（这次是"按字母序第一个是 `P_CONFIRMED`"）。
- 超长的 shell heredoc 又解析失败了两次：补丁脚本一律用 Write 工具写成文件再执行。
- 在 worktree 里跑探测之后，Bash 的工作目录会留在 worktree，环境提示也会改口说"不要 cd 回主检出区"。编排者的家是主检出区：每条命令照旧以 `cd /d/CoevoDB` 开头。
- worktree 里直接敲 `pytest` 会因为导入路径失败（pytest 把 `tests/` 放到 `sys.path` 最前），说明里写 `python -m pytest`。

S6 踩到的：

- **先写一份不入库的参考模型，再写门槛。** 规则密集的会话里，门槛的几十个期望值靠手推容易错；参考模型把门槛跑通（12/12）之后再派发，审查时拿它与执行者的实现做随机差分（十几万项比较），第一个包首轮就过了。再用穷举法核对规则本身（增量算出的 G 是否就是真正的一般边界），这一步查的是规则，不是实现。脚本在 `.orch/scratch/s6_ref/`、`s6_review_vspace.py`、`s6_review_theory.py`、`s6_bruteforce_g.py`。
- **同一条消息里并行发出的几条 Bash 命令共用一个工作目录**：其中一条 `cd` 进了 worktree，另外两条的相对路径就全错了。带 `cd` 的命令串行发，每条以 `cd /d/CoevoDB` 开头。
- PowerShell 里 `git rev-parse tag^{commit}` 的花括号会被当成脚本块；查提交用 Bash。
- 前台命令里不能 `sleep` 等后台任务；后台任务结束会有通知，等通知的时候做别的事（读 diff、跑探测、起草交接）。
- 理论层与特征层互相导入（`features/spec.py` 导入 `theory/contracts.py`）：理论层只能从特征层的子模块导入。门槛的 `constants` 组在新进程里查四种导入顺序；以后往 `theory/__init__.py` 加导出时留意。
- Python 在这台机器的控制台上打印中文是乱码，文件本身是 UTF-8，没有问题；判断结果看 ASCII 关键字或直接读文件。

S5 踩到的：

- **派发之后往门槛表里加的反例，执行者的 worktree 里没有。** 返工那一轮它跑的是旧表。审查时用一个从主检出区按路径加载门槛表、对着 worktree 的代码跑的脚本核对（`.orch/scratch/s5_gate_probe_check.py`），并在返工意见里把每条反例连同"必须有 / 不许有"原样列出来，要求逐条有测试。
- **三个包首轮都过了全部门槛，每个包的问题都是读完整实现再写探测找到的。** 探测要对着"定义"写而不是对着门槛里已有的例子写：换一种写法（带括号、命名窗口、写语句、被包装的函数）往往就错了。
- **探测脚本会过期。** 给上一个包写的静态检查（"特征包不许 import sqlglot"）到下一个包就是误报；每个包审查前先把旧脚本过一遍。
- **编排者的 Bash 工作目录会随 `cd` 漂进 worktree**，之后环境提示会把 worktree 当成主目录。每条命令都从 `cd /d/CoevoDB` 或 `Set-Location D:\CoevoDB` 开始。
- **用量上限会在会话中途打断。** 每次合并、每次派发之后都更新本文件并提交，中断时只多做一次 WIP 提交就能接上；恢复后先 `gw list` 与 `gw status <包号>`，不要重跑已完成的步骤。
- 后台的 `gw review` 约 5 分钟（S5 最后一包含语料报告，约 6 分钟）；等它的时候读 diff、跑探测，结论等复跑结果出来再下。
- `gw review` 的退出码 3 表示有红旗，不是失败；"门槛未通过"在一个会话的前几个包里是预期的（后面的组还没有实现）。

S4 踩到的：

- **说明里的验收命令必须在 worktree 里跑得通。** S4 第一包的说明要求 S03 门槛退出码 0，而当时那个门槛按 worktree 根找 `.venvs`，不可能通过；执行者于是建了一个指向主检出区的目录联接。门槛已修，但这类"环境只在主检出区有"的假设以后还会出现：派发前在一个没有 `.venvs`、没有 `.orch/pg16` 的目录里想一遍。
- **说明里写明"不建指向 worktree 之外的链接或目录联接"。** 联接留在 worktree 里，`gw cleanup` 的递归删除有连带删掉真实目录的风险。发现了先用 `cmd /c rmdir <联接>`（不带 `/s`）单独移除，核对真实目录还在，再清理。
- **改常数、改取值表的包，允许路径里要放进钉住它们的旧测试。** S4 两个包都因为 `tests/test_surprise_contracts.py` 的常数快照断言卡了一下（第一包执行者自行改了并报告，第二包停下上报）。harness 现在冻结了，这条主要对 S5 的词表、S6 的阈值适用：先 grep 一遍哪些测试对它们做了精确断言。
- **承载 `gw spawn` 的后台任务不受 10 分钟上限影响。** S4 两个包分别跑了 51 分钟和 46 分钟，后台任务都活到 grok 退出并发来通知。
- **审查时用门槛之外的独立探测。** S4 两个包首轮都通过了自己的全部门槛，问题是探测脚本找出来的（`.orch/scratch/s4_review_tier1.py`、`s4_review_tier23.py`）。探测里发现的反例先实测，再加进门槛。
- 包里有 `from .x import x` 这种把子模块名和函数名重合的写法时，`import pkg.x as m` 拿到的是函数不是模块；测试和探测里用 `sys.modules["pkg.x"]`。
- 往归档的审查结论里写内容，用脚本从文件读入再写，不要走很长的 shell heredoc：超长的 heredoc 在这里出过解析错误。

S2、S3 踩到的，仍然有效：

这几条都是本会话或上一会话实际踩到的：

- **`gw status --wait` 不要加 `--timeout`**。那个参数是"包运行超过这么多分钟就终止"，不是"最多等这么久"。本会话因此误杀了一个跑了 11 分半的包。想限制等待时间，用后台任务或命令自身的超时。
- 任务说明里写明"不要清理 `.orch/tmp`"。执行者收尾时喜欢清理临时文件，递归删除会被 deny 规则拦下，然后它会改成逐个删除，擦着"被拒绝的操作不要换写法重试"的边。
- CLAUDE.md 里的测试与门槛命令写的是 `../.venv/Scripts/python.exe`，这个路径在 worktree 里不存在。任务说明里要写明直接用 `python`。
- 往审查包里写结论时，文本里不要出现反斜杠转义（如反斜杠加 0、反斜杠加 n）：它们会被展开成真的 NUL 和换行，git 会把文件当成二进制。本会话为此补过一次提交。
- `git merge` 不能用 `-F -` 从标准输入读提交信息，要用 `-m`；合并成功并核对过之后再打 tag，两步不要连在一条命令里。
- 并行的包合并之前，各自 worktree 里的门槛都会因为缺另一个包而报"门槛未通过"，这是预期的红旗；用 `--only` 跑它自己的那几组。编排者补了门槛之后，可以用主检出区的门槛文件去跑分支上的代码来复核（本会话的做法记在 `orch/s02/s02-oracles.review.md` 的结论里）。
- 编排者自己的审查辅助脚本放在 `.orch/scratch/`（不入库）：列出执行者跑过的全部命令、种子语料差分核对、用主检出区的门槛跑别的检出。会话的临时目录中途可能失效，不要把还要用的脚本放在那里。

### S12 之后

SESSIONS 的十二个会话到此全部完成。没有排定的 S13；接下来做什么由用户定。

（2026-10-19）S13 已据此定下正式实验，见 `EXPERIMENT.md`；接着是 S14，起点见文首 S13 一节。下面各条里与正式实验有关的事项，去向见未决问题的"S13 处理与新发现"一组。

- **起点**：`s12-done-r2`（用户验收之后的 main；与 `s12-done` 相比只多了验收记录）。用户验收时确认的下一步是规划正式实验。开工检查照旧：主分支、tag、工作区；PG 参照（服务器停着时按 S3 一节的恢复命令启动，不重新 initdb）；`DEEPSEEK_API_KEY` 在 Windows 用户环境变量里。
- **复跑**（在 `framework/` 下，去掉密钥）：`../.venv/Scripts/python.exe -m pytest -q testing tests` 应为 935 passed, 3 skipped；`../.venv/Scripts/python.exe -m surprise.gates.all` 应为 `GATES: PASS (12/12 passed)`。
- **门槛依赖仓库外的东西**（与 S11 相同）：`framework/results/s08/`（S8 的四个产物组与 S11 的 `ciao`）、`.src/` 两份源码检出（S9、S10 的若干组）、PostgreSQL 参照（S10 的若干组）、`.venvs/duckdb-1.1.3-full`（S11 `coverage`）。S12 自己的 `old_arm` 组从 git 导出 `s11-done-r2` 的旧代码来对照，不依赖仓库外的产物。
- **正式实验之前要定的**（都在上面的未决问题里，摘要）：网格的规模与时长（24 小时正式实验不在任何会话的范围里）；SQLancer 的原始结果拷回 `results/sqlancer_strong/`（用户验收 S11 时定下）；价格表；harness 要不要加结果行数上限（冻结区，用户验收 S11 时定下"规划正式实验时再定"）；`RunData` 改流式读；网格的 `surprise` 格加墙钟强杀。
- **冻结与改动规则照旧**：harness 与 manifest 里的常数冻结；改 `surprise/hunter/`、`diagnoser/`、`experiments/`、`harness/`、`theory/`、`features/` 的任何一行，都要按 S8 验收的办法重跑长跑、重钉，再跑 S8 的四个产物组与 S11 的 `ciao`；旧代码（`surprise/` 以外与 `coevodb_v1/`、`archive/`）由 S12 的 `moves` 组钉着与 `s11-done-r2` 只差导入路径，要改它们就得同时改这一组的表，先问用户。
