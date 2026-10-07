# CoevoDB 改造 · 会话执行手册

2026-10-08。配套总规划：`claude/coevodb-migration-plan.md`。Claude Doc 版本（"会话执行手册"标签页）：https://claude.ai/code/artifact/ce14c65b-9c26-497c-8261-a992c0396d6a

改造分 12 个会话流水线执行（另加一个 S0 搭编排工具）：一个会话交付一个能用一条命令验收的结果，交接靠仓库里的几个文件加 git tag，每个会话用同一段开场提示词，只换编号。

执行方式（10-08 定，路线 1）：每个会话的主会话是本机 `D:\CoevoDB` 里的 Claude Code，担任编排者（PI），只拆工作包、先写门槛、派发、审查、合并、写交接；实现代码一律交给 grok build CLI，在各自的 git worktree 里以无界面模式完成。准备清单与流程见第 2 节。

## 1. 开工前准备

- 会话必须能在仓库里跑命令。2026-10-08 的规划会话无法在用户电脑上执行命令（设备工作区没能启动），只能读写文件；云端工作区的网络也连不到 xAI 的 API。因此在 `D:\CoevoDB` 里直接开 Claude Code 当主会话，由它在本机调用 grok。
- 工具、仓库整理与参数：见第 2 节"准备清单"。
- git：S0 之前先确认仓库在 git 管理下、根目录 `.env` 不会被提交（原属 S1，因 grok 一开工就要在分支上提交而提前）；之后每个会话结束打 tag。
- 交接文件（下文 5 个）已于 2026-10-08 写入仓库：根目录 CLAUDE.md 与 framework/surprise/docs/ 下四个文件。另把本手册存成 `framework/surprise/docs/RUNBOOK.md`（从项目复制本文件，或从 Claude Doc 导出 Markdown），S0 据此生成 ORCHESTRATION.md。
- LLM 预算：S9 起调用 DeepSeek，每个会话先定调用上限并打开响应缓存。grok 的花费另算，在 xAI 账户侧设上限。

## 2. 编排模式：Claude Code 主会话 + grok 执行

### 分工

| 角色 | 由谁担任 | 做什么 | 不做什么 |
|---|---|---|---|
| 编排者（PI） | Claude Code，`D:\CoevoDB` 主会话 | 读交接文件、拆工作包、写任务说明、先写 gates/sNN.py、派发与监控、独立复跑审查、合并、写 HANDOFF 与 DECISIONS、打 tag | 不写实现代码 |
| 执行者 | grok build 无界面模式，每个工作包一个 | 在自己的 worktree 与分支 `grok/<包号>` 上实现、跑测试、提交、写 `.orch/report.md` | 不改 gates/、framework/surprise/docs/、CLAUDE.md、.grok/；不打 tag、不合并、不 push |
| 用户 | — | 定参数、批准 CLAUDE.md 改动、处理升级上来的问题、会话验收 | — |

### 准备清单

装工具（Windows 本机）：
- Git for Windows：worktree 需要 git；Claude Code 在原生 Windows 上靠 Git Bash 提供 Bash 与 Monitor 工具，Monitor 用来盯 grok 的日志。
- Claude Code：PowerShell 里 `irm https://claude.ai/install.ps1 | iex`，新开终端 `claude --version`；需要 Pro、Max、Team、Enterprise 或 Console 账号。也可以用桌面 app 跑。
- Grok Build：`irm https://x.ai/cli/install.ps1 | iex`，再 `grok --version`。登录一次（浏览器登录，或设用户级环境变量 `XAI_API_KEY`），确认 `grok -p "hi"` 不弹浏览器直接出结果。
- `where.exe grok` 确认指向 xAI 的程序：npm 包 `@vibe-kit/grok-cli` 可能占用 `grok` 这个命令名。
- `%USERPROFILE%\.grok\config.toml` 的 `[cli]` 下写 `auto_update = false`。

整理仓库：
- git 基线：在 git 管理下、`.env` 在 `.gitignore` 里、工作区干净，提交一次。
- 异地备份：推到 GitHub 私有库，或拷一份到别的盘。grok 的沙箱只在 Linux 与 macOS 上生效，原生 Windows 上加 `--always-approve` 等于可以在本机任意执行命令，worktree 只隔离代码。补救靠 deny 规则（always-approve 下仍生效）加审查。
- `.gitignore` 加 `.worktrees/` 与 `.orch/`。
- 运行期间电脑不睡眠、Claude Code 不关；第一次运行派发脚本时权限提示选"本项目始终允许"。

参数（不定就用默认）：

| 参数 | 默认 |
|---|---|
| 同时运行的 grok 数 | 2 |
| 单包超时 | 60 分钟 |
| 每包返工上限 | 2 轮，超了停下来问用户 |
| grok 模型 | grok 自身默认 |
| xAI 用量上限 | 用户在账户侧自设 |
| CLAUDE.md"执行者模式"一节 | S0 出草稿，用户同意后写入 |

### 一个工作包的流程

1. 拆包：按文件归属不重叠拆分；共享接口（如 S2 的五个数据契约）先单独一包并合并，之后的包再并行。
2. 先写门槛：编排者按 SESSIONS.md 写 gates/sNN.py，提交到会话分支 `session/sNN`，以它为基线派发。出题和答题分开，执行者没法靠改门槛变绿。
3. 派发：`python tools/orch/grok_worker.py spawn <包号> --base <基线>`。提示词只指向 worktree 里的 `.orch/brief.md`，避开 Windows 命令行长度与中文转码问题；子进程去掉 `DEEPSEEK_API_KEY`（S9 前用不到，`framework/test_api.py` 有密钥会真调 API）。
4. 监控：`status <包号>` 看进程与日志末尾；超时即终止，读已有提交。
5. 审查：`review <包号>` 生成审查包，编排者再读完整 diff。结论四选一：
   - 合并：`merge`，--no-ff 并入会话分支，brief 与 report 归档到 `framework/surprise/docs/orch/sNN/`。
   - 返工：审查意见写成文件，`resume` 续上原会话（保留上下文），最多两轮。
   - 推翻：重写说明后重新派发。
   - 升级：与 PLAN 冲突、碰冻结区、超过返工上限时，停下来问用户。
6. 收尾：所有包合并后在会话分支上跑 pytest 与 gates.all，更新 HANDOFF 与 DECISIONS，合并回主分支，commit，打 sNN-done，按第 5 节格式汇报。

### 审查清单（在执行者分支上独立做，不采信其自述）

- 范围：改动只在说明允许的路径；gates/ 零改动；S4 之后 harness/ 零改动。
- 复跑：worktree 里跑 `cd framework && pytest -q testing tests` 与 `python -m surprise.gates.all`；测试数不减少，再与 report 对账。
- 防"改测试求绿"：新增 skip/xfail、被删或放宽的断言、吞异常的 try/except、conftest 与门槛的改动。deny 规则只拦编辑工具，执行者用 shell 写文件仍可能绕过，这一条不能省。
- 项目红线：标签路径上没有 LLM 调用；S1–S11 旧代码只移动（S1 用 `git diff -M` 确认只有重命名与 import 行变化）；diff 里没有密钥。
- 对照 PLAN：契约字段、逐项表里的判定条件是否照写。

### 并行建议

| 会话 | 拆法 |
|---|---|
| S1、S4、S6、S7 | 串行单包：S1 是纯移动，S4 是要冻结的 harness，S6/S7 是理论核心，审查要细 |
| S3 | 四类 oracle 可拆 3–4 包并行 |
| S2、S5 | 先契约一包，再两包并行 |
| 其余 | 按文件归属临场定 |

同时运行的包数不超过参数表上限：审查带宽有限，DuckDB 临时文件与 CPU 也会互相干扰（每个 worktree 用自己的临时目录）。

### S0 编排准备：开场提示词

在 `D:\CoevoDB` 打开终端运行 `claude`，贴入：

```text
你是 CoevoDB 改造的编排者（PI）。本会话是 S0（编排准备）：只搭派发工具，不碰 S1 的范围，不写任何框架代码。

先读 CLAUDE.md、framework/surprise/docs/RUNBOOK.md（尤其第 2 节"编排模式"）、PLAN.md、SESSIONS.md、HANDOFF.md。然后跑 grok --help 和 grok inspect，以实际参数为准；与下文不符的地方按实际改，并记进 DECISIONS.md。

交付物：
1. tools/orch/grok_worker.py（只用标准库），子命令：
   - spawn <包号> --base <tag或分支>：建 .worktrees/<包号> 和分支 grok/<包号>；把 .orch/briefs/<包号>.md 拷成 worktree 里的 .orch/brief.md；后台启动
     grok --no-auto-update --always-approve --cwd <worktree> --session-id <包号> --output-format streaming-json -p "读 .orch/brief.md，按其中说明完成工作包"
     输出写 .orch/logs/<包号>.jsonl。子进程环境去掉 DEEPSEEK_API_KEY。用 --deny 禁止：git push / tag / merge / rebase / reset --hard / worktree / branch -D、rm -rf，以及编辑 framework/surprise/gates/、framework/surprise/docs/、CLAUDE.md、.grok/。
   - status <包号>：是否在跑、已用时长、日志末尾几条事件；超过 --timeout（默认 60 分钟）就终止。
   - review <包号>：生成审查包——相对基线的改动文件（标出越界路径）、diff 统计；在 worktree 里跑 cd framework && pytest -q testing tests 与 python -m surprise.gates.all（门槛模块还不存在就跳过并注明），给出结果和测试数；扫描新增的 skip/xfail、被删或放宽的断言、conftest 改动、疑似密钥；附上 .orch/report.md。
   - resume <包号> <审查意见文件>：用同一个 --session-id 续上原会话。
   - merge <包号> --into <分支>：--no-ff 合并，把 brief 和 report 归档到 framework/surprise/docs/orch/<会话号>/。
   - cleanup <包号>：删 worktree 和分支；未合并的要求显式 --abandon。
2. framework/surprise/docs/orch/BRIEF_TEMPLATE.md：任务说明模板。开头写"角色：执行者"，包含基线、目标、允许和禁止改动的路径、验收命令、报告格式（改了哪些文件、跑了哪些命令及输出末 20 行、与说明的偏差、未决问题）。
3. framework/surprise/docs/ORCHESTRATION.md：按 RUNBOOK.md 第 2 节整理编排流程与审查清单，改成编排者直接照做的口吻。
4. CLAUDE.md"执行者模式"一节的草稿（RUNBOOK.md 第 7 节有建议稿）：只给我看，不写入。
5. .gitignore 加 .worktrees/ 和 .orch/；SESSIONS.md 开头加 S0 一节；HANDOFF.md 状态表加 S0 一行。

冒烟测试：派一个无害的工作包 s00-smoke（在 worktree 里新建 scratch/hello.txt 并提交），走完 spawn → status → review → cleanup --abandon。确认四件事：grok 无交互跑完；让它试一次 git tag，应被拒；日志可读；子进程里没有 DEEPSEEK_API_KEY。

收尾：追加 DECISIONS.md，更新 HANDOFF.md，commit，打 tag s00-done。最后一条消息只写：冒烟结果、与本说明的偏差、CLAUDE.md 草稿全文。
```

S0 通过、CLAUDE.md"执行者模式"一节经用户同意写入后，S1 起用第 5 节的编排版开场提示词。

## 3. 会话划分

一个会话 = 一个可验收的交付物，不是固定工作量。提前做完不顺手开下一个；做不完拆成 S{n}a / S{n}b，同一个门槛。关键路径 S1–S8，做完即得无 LLM 版。S0 只搭编排工具，不计入 12 个会话。

| 会话 | 阶段 | 交付物 | 门槛（通过标准） |
|---|---|---|---|
| S0 | 编排准备 | tools/orch/grok_worker.py；BRIEF_TEMPLATE.md；ORCHESTRATION.md；CLAUDE.md"执行者模式"草稿；.gitignore；SESSIONS/HANDOFF 加 S0 | 冒烟包 s00-smoke 无交互跑完；git tag 被 deny 规则拦下；日志可读；子进程里没有 DEEPSEEK_API_KEY |
| S1 | Phase 0 | git 基线 tag v1-baseline；旧系统基线 run 存档；PG 脚本移 framework/campaigns/、DuckDBRunner 移入 targets/（coevo/ 暂留，S12 归档）；framework/surprise/ 空骨架；环境：DuckDB 1.5.5 与 1.1.3、DataFusion 54.0.0 与一个旧版、SQLite（PG 可选） | pytest 全绿且测试数与整理前一致；gates/s01 检查骨架、环境版本、旧 main.py 可启动；只有移动，没有逻辑改动 |
| S2 | Phase 1a | 五个数据契约；SQLite 实验账本；run manifest 与 harness 哈希；TLP（接入 TLP-GroupBy）、NoREC、Plan variant 三值适配器 | 同输入两次判定一致；已知复现中三类能抓的判 fail；值依赖错误判 invalid；每次执行（含 pass）进账本 |
| S3 | Phase 1b | Index presence 移植到 DuckDB；Equivalent query 确定性改写规则库；Version differential（两引擎新旧版）及方向判定；Cross-DBMS 多数表决并入 oracle 层 | 七类在 DuckDB、DataFusion 上都产出三值标签或明确"不适用"；DF-A、DF-B 被 Cross-DBMS 判 fail；至少一个已知回归被 Version differential 判 fail 且方向正确；不等价改写判 invalid |
| S4 | Phase 1c | CVE 三档流水线（重跑+前提、归属测试、最小化+画像）；harness 冻结 | M1：recall_repros.json 与各引擎 .sql 复现全判 fail 且身份证据正确；普通查询 pass；已知假阳类 invalid；manifest 校验通过 |
| S5 | Phase 2 | φ 抽取（sqlglot AST、计划算子、数据性质）、特征类、单元、词表注册表、规格核对器 | φ 跨进程稳定；DF-A、DF-B 与 DuckDB F1–F11 最小复现两两可区分；规格核对器在手写 spec/SQL 对上全对；单元分布报告 |
| S6 | Phase 3a | 假设与版本空间规则、R、Kᵛ、P_T、惊讶、六类分诊（常数写入 manifest） | 用手写 h2 代替 LLM 走一遍 DF-A → DF-B 案例的确定性部分：惊讶约 6.6 / 1.0 比特，left_has_dups 进 G，INTERSECT ALL 失败因身份不一致开新家族 |
| S7 | Phase 3b | 理论存储、按代快照、编辑日志、自动回滚、负记忆、留出验收、MDL | 离线喂入已知复现与 DCE 探针：惊讶量级正确、重复执行前识别、家族划分与人工账本一致度不低于 σ；故意错误的编辑被回滚并进负记忆 |
| S8 | Phase 4 | Hunter 四类候选、期望惊讶打分、探索保底；无 LLM 主循环 | M2：DuckDB 数小时 run 不崩；惊讶曲线锯齿；同预算重复率低于原 CoevoDB 基线；1.1.3 召回报告；同种子重跑一致 |
| S9 | Phase 5a | LLM 网关（缓存、种子、模型版本、按角色记账、缺预测拒收）；实现器；假设猜想者 | 缓存命中零网络调用、重放一致；缺预测输出被拒收；实现器 φ 核对通过率报告；猜想者在 DF-A 上给出带预测的假设并登记为待检实验 |
| S10 | Phase 5b | 探索先验、迁移翻译者、词汇发明者、oracle 发明者 | M3：角色可单独开关、关掉时零调用；DataFusion 54.0.0 上从 DF-A 闭环复现 DF-B，固定缓存可重放 |
| S11 | Phase 6 | 账本指标（惊讶曲线、CIAO、Brier 等）；实验网格与统计；对照组（SQLancer、原 CoevoDB、纯 LLM、无 LLM 版） | M4 冒烟：2 臂 × 2 种子短时网格跑通；RQ1–RQ6 指标与图一条命令生成 |
| S12 | Phase 7 | 旧循环移入 baselines/coevodb_v1/；coevo/、repair_bench/ 归档；文档更新 | 原 CoevoDB 臂在新位置可跑；s01 到 M4 全部门槛仍绿 |

上下文宽裕时 S6 与 S7、S9 与 S10 可合并。S11 可在 S7 后另开分支并行，但要合并代码，建议仍按顺序。

## 4. 交接机制

| 文件 | 放什么 | 谁改 |
|---|---|---|
| CLAUDE.md（仓库根） | 常驻规则：密钥、冻结、范围纪律、命令、收尾协议、执行者模式；Claude Code 与 grok 在仓库里开会话都会自动读取 | 用户；会话只在用户同意时改 |
| framework/surprise/docs/PLAN.md | 总规划（即 coevodb-migration-plan.md） | 只在用户做出新决定时改 |
| framework/surprise/docs/RUNBOOK.md | 本手册副本 | 用户 |
| framework/surprise/docs/SESSIONS.md | S0 与 12 个会话，每个一节：范围、交付物、门槛、不做什么 | 用户 |
| framework/surprise/docs/ORCHESTRATION.md | 编排流程与审查清单（S0 据第 2 节生成） | 用户；会话只在用户同意时改 |
| framework/surprise/docs/HANDOFF.md | 状态总览 + 最近一次会话交接（含工作包清单与结论） | 每个会话收尾时改 |
| framework/surprise/docs/DECISIONS.md | 只追加的决策日志 | 每个会话追加 |
| framework/surprise/docs/orch/ | BRIEF_TEMPLATE.md；各会话归档的 brief 与 report（sNN/ 子目录） | 编排者合并时写入 |
| tools/orch/grok_worker.py | 派发脚本 | S0 写；之后的改动记 DECISIONS.md |
| .worktrees/、.orch/（不入库） | worktree、待派发的说明、grok 日志 | 派发脚本 |

- 门槛脚本：每个会话新增 framework/surprise/gates/sNN.py，退出码 0 = 通过；`python -m surprise.gates.all` 跑全部已有门槛。后面的会话必须保持前面所有门槛通过。门槛由编排者在派发前写好，执行者不能改。
- 分支：每个会话在 `session/sNN` 上合并各工作包，收尾时合并回主分支；执行者分支 `grok/<包号>` 合并后删除，--no-ff 合并提交保留来龙去脉。
- git tag：每个会话结束 commit 并打 sNN-done；修复会话打 sNN-done-r2。
- 上下文快用完：先把 HANDOFF.md 标"进行中"（写明哪些包已合并、哪些在跑）、提交 WIP；下一个会话沿用同一编号接着做。

## 5. 开场提示词

编排版通用模板（S1 起使用，只替换 {编号}、{名称}；S0 用第 2 节的专用提示词）：

```text
你在 CoevoDB 仓库上执行"迁移到惊讶驱动框架"的改造，担任编排者（PI）。本会话是 S{编号}（{名称}）。实现代码一律交给 grok 执行者；你只拆包、写门槛、派发、审查、合并、写交接。

开工前按顺序读：
1. 仓库根的 CLAUDE.md（常驻规则）
2. framework/surprise/docs/PLAN.md（总规划，只读）
3. framework/surprise/docs/ORCHESTRATION.md（编排流程与审查清单）
4. framework/surprise/docs/SESSIONS.md 中 S{编号} 一节（本会话的范围、交付物、门槛）
5. framework/surprise/docs/HANDOFF.md 与 DECISIONS.md（上一会话的交接）

然后：
- 跑一次 pytest 和 python -m surprise.gates.all，确认起点是绿的；不是绿的先停下来告诉我。
- 用 5 行以内复述：本会话交付什么、门槛命令和通过标准、HANDOFF 里哪些未决问题和本会话有关。
- 复述完直接开工，不用等我确认：从上一会话的 tag 建分支 session/s{编号}；按 ORCHESTRATION.md 拆包，把拆包清单（包号、目标、允许路径、依赖）写进 HANDOFF.md 并标"进行中"；先写 framework/surprise/gates/s{编号}.py 并提交；再按 BRIEF_TEMPLATE.md 写任务说明，用 tools/orch/grok_worker.py 派发。

范围纪律：
- 只做 S{编号} 的范围。计划外发现的问题记进 HANDOFF.md 的"未决问题"，不要顺手修，也不要派给 grok。
- 和 PLAN.md 冲突、要改冻结的 harness 部分、或某包返工超过上限时，停下来问我。小的实现选择自己定，记进 DECISIONS.md。
- 审查以你在执行者分支上的独立复跑为准，不采信执行者的报告。

收尾（全部做完才算结束）：
1. 所有包合并进 session/s{编号} 后，跑 pytest 和全部门槛，贴出结果。
2. 更新 HANDOFF.md，追加 DECISIONS.md（含每个包的结论：一次通过、返工几轮或推翻）。
3. 合并回主分支，git commit，打 tag s{编号}-done；清理已合并的 worktree。
4. 最后一条消息只写：门槛结果、与计划的偏差、需要我人工检查的 3–5 处（文件路径或命令）。
```

修复会话：

```text
本会话是 S{编号} 的修复会话，你仍是编排者。我验收时发现：
- {问题 1}
- {问题 2}

先读 CLAUDE.md、ORCHESTRATION.md、HANDOFF.md、DECISIONS.md，只修上面这些，不扩大范围。修复同样写成工作包交给 grok，基线是 s{编号}-done；问题出在门槛本身时由你改门槛，并在 DECISIONS.md 写明原因。
收尾协议同常规会话，tag 打 s{编号}-done-r2。
```

## 6. 每次会话后的验收清单

前四步每次都做；第 6 步只在关键会话做。

1. 自己跑门槛：`cd framework && pytest -q testing tests` 和 `python -m surprise.gates.all`，不只看会话自己的报告。
2. 看范围：`git diff --stat s{上一编号}-done s{编号}-done`；改动只应在本会话目录和 framework/surprise/docs/orch/；S4 之后 harness/ 不该有改动。
3. 看派发记录：framework/surprise/docs/orch/s{编号}/ 下每个包都有 brief 与 report；DECISIONS.md 有每个包的结论；`git log --merges s{上一编号}-done..s{编号}-done` 能对上每个包。实现代码应来自 grok/ 分支，编排者直接提交的只应是门槛、交接文件与合并。
4. 读 HANDOFF.md 的"偏差"和"未决问题"，挑出需要拍板的。
5. 抽查会话点名的人工检查项（如账本随机 5 条、某已知 bug 的标签与惊讶值）。
6. 关键会话多看一步：S4 标签是否可信；S7 理论修改是否可追溯；S8 无 LLM 闭环能否复现；S10 LLM 是否只提猜想、从不打标签。
7. 通过就开下一会话；不通过就开修复会话，不带着红的门槛往下走。

## 7. 文件模板

PLAN.md 用项目里的规划副本；RUNBOOK.md 用本手册；SESSIONS.md 把第 3 节表格每行展开成一节；DECISIONS.md 从空文件开始。ORCHESTRATION.md 与 BRIEF_TEMPLATE.md 由 S0 生成。

CLAUDE.md（"执行者模式"一节为建议稿，S0 出正式草稿，用户同意后写入）：

```markdown
# CoevoDB · 迁移到惊讶驱动框架

目标：把 CoevoDB 从 bandit + playbook 的共同进化循环改造成惊讶驱动框架。
总规划 framework/surprise/docs/PLAN.md；会话划分 SESSIONS.md；编排流程 ORCHESTRATION.md；交接 HANDOFF.md；决策日志 DECISIONS.md。

## 不可违反
- 密钥只走环境变量 DEEPSEEK_API_KEY；不打印，不写进代码、配置、日志或提交（沿用 framework/AGENTS.md）。
- LLM 永不打标签：标签只来自七类 oracle 加 CVE 流程。
- S4 之后 framework/surprise/harness/ 与 manifest 里的常数冻结，要改先问人。
- S12 之前，旧代码只做移动、不改逻辑；旧测试保持通过。
- 只做 SESSIONS.md 中当前会话的范围；计划外的问题记进 HANDOFF.md。

## 命令
- 测试：cd framework && pytest -q testing tests（不直接 pytest -q：framework/test_api.py 在设置了密钥时会真调 API）
- 门槛：python -m surprise.gates.all（每个 gates/sNN.py 退出码 0 = 通过）
- 编排：python tools/orch/grok_worker.py {spawn|status|review|resume|merge|cleanup}
- 引擎环境：{S1 填写各 venv 路径与版本}

## 收尾协议（编排者）
1. gates/sNN.py 在派发前写好；收尾时跑测试与全部门槛。
2. 更新 HANDOFF.md，追加 DECISIONS.md。
3. git commit，tag sNN-done。
4. 上下文快用完时，先把 HANDOFF 标为"进行中"并提交 WIP。

## 执行者模式（任务说明以"角色：执行者"开头时适用，替代上面的收尾协议）
- 只做 .orch/brief.md 里的工作包，只改其中允许的路径。
- 不改 framework/surprise/gates/、framework/surprise/docs/、CLAUDE.md、.grok/；不靠改测试或放宽断言让测试通过。
- 收尾：在当前分支 commit；写 .orch/report.md（改了哪些文件、跑了哪些命令及输出末 20 行、与说明的偏差、未决问题）。不打 tag、不合并、不 push，不改 HANDOFF.md 与 DECISIONS.md。
- 说明有矛盾或做不完：写进 report，停下，不自行扩大范围。
```

HANDOFF.md：

```markdown
# HANDOFF

## 状态总览
| 会话 | 状态 | tag | 门槛 |
|---|---|---|---|
| S0 | 未开始 | | |
| S1 | 未开始 | | |
| S2 | 未开始 | | |
（……到 S12）

## 最近一次会话：S{编号}（{日期}）
### 完成了什么
### 工作包（包号、目标、结论：一次通过 / 返工几轮 / 推翻）
### 新增或改动的接口（路径 + 一句话）
### 与 PLAN 的偏差及原因
### 未决问题（下一会话需要知道的）
### 下一会话的起点
```
