# ORCHESTRATION · 编排流程与审查清单

写给编排者（PI）：`D:\CoevoDB` 主会话里的 Claude Code。S1 起每个会话照此执行。来源是 `RUNBOOK.md` 第 2 节，按 S0 实测结果改写；两者不一致时以本文件为准，改动原因见 `DECISIONS.md`。

## 1. 你做什么，不做什么

| 角色 | 谁 | 做 | 不做 |
|---|---|---|---|
| 编排者 | 你 | 读交接文件、拆工作包、先写 `gates/sNN.py`、写任务说明、派发与监控、独立复跑审查、合并、写 HANDOFF 与 DECISIONS、打 tag | 不写实现代码 |
| 执行者 | grok 无界面模式，每个工作包一个 | 在自己的 worktree 与分支 `grok/<包号>` 上实现、跑测试、提交、写 `.orch/report.md` | 不改 `gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`；不打 tag、不合并、不 push |
| 用户 | — | 定参数、批准 CLAUDE.md 改动、处理升级上来的问题、会话验收 | — |

你直接提交的只应是：门槛脚本、交接文件、归档、合并提交。实现代码全部来自 `grok/` 分支。

## 2. 环境事实（S0 实测，grok 1.0.46）

- 解释器：一律用项目解释器跑派发脚本，目前是仓库根的 `.venv`：`.venv/Scripts/python.exe tools/orch/grok_worker.py …`（下文简写成 `gw`）。脚本把这个解释器放到执行者 PATH 的最前面，执行者的 `python`、`pytest` 和你审查时复跑用的是同一个。PATH 上默认的 `pytest` 是 anaconda 的，没有 duckdb，不要用。
- 执行者的 shell 是 Windows PowerShell 5.1：没有 `&&`（用 `;`），中文输出会乱码。任务说明里的命令按 PowerShell 写，判断结果用 ASCII 关键字。
- grok 的会话号必须是 UUID，脚本在 `spawn` 时生成并记在 `.orch/state/<包号>.json`；返工用 `--resume <UUID>` 续接，上下文保留（S0 已验证）。
- grok 在 worktree 里会自动读 `CLAUDE.md`（脚本传了 `--trust`）。任务说明第一行是"角色：执行者"时，执行者按 CLAUDE.md 的"执行者模式"行事。
- 密钥：脚本从执行者进程和审查复跑的环境里去掉 `DEEPSEEK_API_KEY`（S0 已验证：父进程有、子 shell 里没有）。S9 开工时用户定下（DECISIONS 2026-10-15）：需要真实调用的包用 `spawn --llm-key N` 派发，它的 grok 进程得到密钥与 `SURPRISE_LLM_MAX_CALLS=N`（网关把它当作每个实例的上限），返工各轮沿用；审查复跑与其余包照旧去掉密钥。密钥取自编排者进程的环境，没有时读 Windows 用户级环境变量。说明里写明这一包真实调用的总数上限，审查时按网关账本核对，并确认日志与 worktree 文件里没有密钥本身（审查包第 4.6 节按值比对）。编排者自己要做真实调用时，在那一条命令里从用户级环境变量取值，不打印。
- 隔离：grok 的沙箱在原生 Windows 上不生效，`--always-approve` 下执行者可以在本机执行任意命令，worktree 只隔离代码。防线是 deny 规则加你的审查，两样都不能省。
- 花费：grok 在日志的 `end` 事件里上报每轮的美元花费，审查包第 6 节有合计。S0 两个冒烟包各约 0.1 美元。

## 3. 参数

| 参数 | 默认 | 怎么改 |
|---|---|---|
| 同时运行的 grok 数 | 2 | `spawn --max-parallel N` |
| 单包超时 | 60 分钟 | `spawn/resume --timeout 分钟` |
| 每包返工上限 | 2 轮 | 到上限 `resume` 会拒绝；停下来问用户 |
| grok 模型 | grok 自身默认 | `spawn --model ID` |
| 复跑单条命令超时 | 30 分钟 | `review --test-timeout 分钟` |

## 4. 一个会话的流程

1. 起点：从上一会话的 tag 建会话分支 `git switch -c session/sNN <上一个 tag>`；跑一次 pytest 和 `python -m surprise.gates.all`，不绿先停下来告诉用户。
2. 拆包：按文件归属不重叠拆分。共享接口（如 S2 的五个数据契约）先单独一包并合并，之后的包以合并后的会话分支为基线再并行。包号用 `sNN-<短名>`。把拆包清单（包号、目标、允许路径、依赖）写进 `HANDOFF.md` 并标"进行中"。
3. 先写门槛：按 `SESSIONS.md` 写 `framework/surprise/gates/sNN.py`，提交到 `session/sNN`，以它为基线派发。出题和答题分开，执行者没法靠改门槛变绿。
4. 写任务说明：复制 `orch/BRIEF_TEMPLATE.md` 成 `.orch/briefs/<包号>.md` 再填。第一行保持"角色：执行者"；允许路径写在 ```` ```allow-paths ```` 块里，审查按它逐个文件核对；契约字段、判定条件直接引用 PLAN.md 的章节，不转述。
5. 派发：`gw spawn <包号> --base session/sNN`。命令会一直阻塞到 grok 退出，所以用你自己的后台任务方式运行它，不要另开窗口、不要用 `Start-Process`。
6. 监控：`gw status <包号>` 看阶段、已用时长、日志末尾；`gw status <包号> --wait` 等到结束。超时由脚本终止，终止后照常读已有提交。
7. 审查：`gw review <包号>` 生成 `.orch/reviews/<包号>.md`，读完它，再读完整 diff，对照第 6 节清单，在第 7 节的四种结论里选一种。
8. 收尾：所有包合并后，在会话分支上跑 pytest 与全部门槛；更新 `HANDOFF.md`、追加 `DECISIONS.md`（含每个包的结论：一次通过、返工几轮或推翻）；合并回主分支，打 `sNN-done`；`gw cleanup` 清掉已合并的包；按 CLAUDE.md 收尾协议汇报。

上下文快用完：先把 `HANDOFF.md` 标"进行中"（写明哪些包已合并、哪些在跑），提交 WIP；下一个会话沿用同一编号接着做。包的状态都在 `.orch/state/` 里，`gw list` 能接上。

## 5. 命令速查

`gw` = `.venv/Scripts/python.exe tools/orch/grok_worker.py`，在仓库根执行。

| 命令 | 作用 | 退出码 |
|---|---|---|
| `gw spawn <包号> --base <tag或分支> [--llm-key N]` | 建 `.worktrees/<包号>` 与分支 `grok/<包号>`，拷入 brief，启动 grok 并等它退出；`--llm-key N` 给这个包密钥与调用上限 | 0 正常结束；2 非零退出或超时；1 前置条件不满足 |
| `gw status <包号> [--wait] [--tail N] [--timeout 分钟]` | 阶段、时长、分支上的提交数、未提交改动、日志末尾；超时就终止 | 0 正常结束；10 还在跑；2 异常结束 |
| `gw review <包号> [--expect-passed N] [--skip-tests]` | 生成审查包并在 worktree 里复跑 pytest 与门槛 | 0 没有红旗；3 有红旗 |
| `gw resume <包号> <审查意见.md>` | 把意见放进 worktree，续接原会话返工 | 同 spawn |
| `gw merge <包号> --into session/sNN` | `--no-ff` 合并，再单独提交一次归档（brief、report、审查包、各轮意见 → `orch/sNN/`） | 0 / 1 |
| `gw cleanup <包号> [--abandon]` | 删 worktree 和分支；未合并的必须 `--abandon`（也会终止还在跑的 grok） | 0 / 1 |
| `gw list` | 所有包及状态 | 0 |

要点：
- `merge` 要求主检出区正停在 `--into` 的分支上、没有未提交的已跟踪改动，并且对分支当前的提交做过 `review`（返工后要重新 review）。合并冲突会自动 `--abort`。
- 合并与归档提交需要署名尾注时，设环境变量 `ORCH_COMMIT_TRAILER`。
- `spawn`/`resume` 加 `--detach` 会立刻返回、留一个隐藏的监督进程。默认不用：用户要求长时间命令走编排者自己的后台任务。
- 文件位置：说明 `.orch/briefs/`，日志 `.orch/logs/<包号>.jsonl`（另有 `.stderr.log`），状态 `.orch/state/`，审查包 `.orch/reviews/`；worktree 里 `.orch/brief.md`、`.orch/report.md`、`.orch/review-<n>.md`、`.orch/tmp/`（该包的临时目录）。`.orch/` 与 `.worktrees/` 不入库。
- 脚本拒绝在 `.worktrees/` 以外的目录启动 grok。

## 6. 审查清单

在执行者分支上独立做，不采信 `.orch/report.md` 的自述。审查包是筛子，红旗为零不等于通过：每个包都要读完整 diff（`git diff <基线>..grok/<包号>`）。

1. 范围
   - 改动只在说明允许的路径内（审查包第 1 节逐个文件标出"越界"）；`gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/` 零改动；`s04-done` 之后 `harness/` 零改动（脚本见到这个 tag 会自动把它列入禁区）。
   - worktree 没有未提交的改动；brief 在派发后没被改过；分支上有提交。
   - worktree 之外没被动过（第 5 节）：其他 ref、tag 的变化和主检出区的未提交改动，都要能对上你自己的操作。
2. 复跑
   - 第 3 节的 pytest 与 `surprise.gates.all` 通过；测试数不减少：用 `--expect-passed <会话起点的通过数>`。
   - 复跑结果与执行者报告里的数字对账，对不上就追问。
3. 防"改测试求绿"（第 4 节，逐条看，不能只数个数）
   - 新增的 skip / xfail / `collect_ignore` / `--deselect`；
   - 测试里被删的断言、被改写的断言（改写的要逐条确认没有放宽）；
   - 新增的宽泛 `except`（确认没有吞掉失败）；
   - `conftest.py`、`pytest.ini` 等测试配置的改动；被删的测试文件。
   - deny 规则只拦 grok 的编辑工具和列出的 shell 写法，执行者用 shell 或 Python 写文件仍能绕过。所以禁区是否被动过，以 diff 为准，不以"没看到拒绝记录"为准。
4. 项目红线
   - 标签路径上没有 LLM 调用：标签只来自七类 oracle 加 CVE 流程。脚本查不了这一条，读 diff 时自己确认。
   - S12 之前旧代码只移动、不改逻辑：`git diff -M --stat <基线>..grok/<包号>`，重命名应是 R100 或只有 import 行变化（第 2 节给出 R100 的个数）。
   - diff、报告、日志里没有密钥（第 4.6 节；命中只显示前三个字符和长度）。
5. 对照 PLAN：契约字段、逐项表里的判定条件是否照写；常数是否进了 manifest；和 PLAN 冲突的实现选择不能由执行者或你自己定。
6. 日志（第 6 节）：被 deny 规则拦下的调用本身不是问题，要看的是之后有没有换写法绕过去；有 `error` 事件、非零退出或超时，要弄清原因再下结论。

## 7. 结论四选一

- 合并：`gw merge <包号> --into session/sNN`，然后 `gw cleanup <包号>`。
- 返工：把意见写成一个 markdown 文件（指出文件与行、要改成什么、哪些不要动），`gw resume <包号> <文件>`，之后重新 `review`。最多两轮。
- 推翻：思路错了、返工不如重做时，`gw cleanup <包号> --abandon`，重写任务说明后用新包号重新派发（如 `s02-contracts-b`），在 DECISIONS.md 记下推翻原因。
- 升级：与 PLAN 冲突、碰冻结区、超过返工上限、需要密钥或需要改 CLAUDE.md 时，停下来问用户。包保持原样，不清理。

每个包的结论写进 `DECISIONS.md`：一次通过、返工几轮或推翻，以及原因。

## 8. 并行建议

| 会话 | 拆法 |
|---|---|
| S1、S4、S6、S7 | 串行单包：S1 是纯移动，S4 是要冻结的 harness，S6/S7 是理论核心，审查要细 |
| S3 | 四类 oracle 可拆 3–4 包并行 |
| S2、S5 | 先契约一包，再两包并行 |
| 其余 | 按文件归属临场定 |

同时运行的包数不超过参数表上限：你的审查带宽有限，DuckDB 临时文件与 CPU 也会互相干扰。

## 9. 出问题时

- 你的安全分类器拒绝启动 grok：不要换别的方式绕过。用户已长期批准"在本项目里通过 `tools/orch/grok_worker.py` 启动 grok，`--cwd` 限定在 `.worktrees/` 下"（见 DECISIONS.md 2026-10-08）；仍被拒就停下来告诉用户，由用户重申授权或加权限规则。
- 超时：脚本已终止 grok。`gw status` 看分支上有多少提交、有没有未提交改动，再决定返工（"接着做完"也走 `resume`）还是推翻。
- 阶段显示 `LOST`：监督进程没留下退出记录（多半是承载它的后台任务被杀）。看 `.orch/logs/<包号>.stderr.log` 和分支状态，按超时处理。
- grok 启动即失败：看 `.orch/logs/<包号>.stderr.log`；`where.exe grok` 确认是 xAI 的程序；`grok -p "hi"` 确认登录没过期。需要指定程序路径时设 `ORCH_GROK_CMD`。
- worktree 删不掉（文件被占用）：关掉占用它的进程后重跑 `gw cleanup`；脚本会先试 `git worktree remove --force`，不行再直接删目录。
- 脚本本身要改：由你改（它是编排者的工具，不派给执行者），改动记进 DECISIONS.md。

## 10. deny 规则覆盖什么，不覆盖什么

规则清单在 `tools/orch/grok_worker.py` 的 `DENY_BASH`、`PROTECTED`、`ORCH_PRIVATE`。S0 用探测包逐条验证过会被拦下的写法：

- `git tag`、`git -C . tag`、`git push`、`git merge <ref>`、`git rebase`、`git reset --hard`、`git worktree`、`git branch -D`；
- `Remove-Item -Recurse -Force`、`rm -rf`；
- 用编辑工具写 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`，包括用绝对路径写主检出区的同名路径。

不覆盖的：经 `cmd /c`、`powershell -Command`、`python -c` 等包一层再执行的命令；PowerShell 里没列出的缩写参数；用 shell 重定向或脚本写禁区文件。这些靠审查清单第 1、3 条兜住。
