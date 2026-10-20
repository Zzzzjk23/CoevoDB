角色：执行者

# 工作包 s19-notify：额度不足与报错的提醒（pushplus 一对一消息）

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s19-notify`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s19`（含本包的门槛 `framework/surprise/gates/s19.py` 新增的五组）
- 所属会话：S19（E1 DuckDB 主对比，暂停中）。提醒是用户 2026-10-21 加进本会话的范围，见 `framework/surprise/docs/SESSIONS.md` 的 S19 一节与 `PLAN.md` §9 最后一条
- 依赖：`s19-glm` 已合并（`glm-flash` 档，OpenRouter）

## 目标

用户的话："添加额度不足、报错等的提醒：使用pushplus的一对一消息功能"。token 只放在环境变量 `PUSHPLUS_TOKEN` 里（不给你，测试一律离线）。

做法：一个**独立的看守进程**，只读一个网格的结果目录（`grid run --out DIR` 的 `DIR`），发现问题就经 pushplus 发一条消息给用户本人。实验代码一行不改：`experiments/`、`hunter/`、`diagnoser/` 都绑着 S8 长跑的代码摘要，改了就要重跑 3 小时长跑。唯一改动的旧文件是 `roles/gateway.py` 的一行（第 3 条）。

### 1. `framework/surprise/notify/pushplus.py`（新）

- 常数 `TOKEN_ENV = "PUSHPLUS_TOKEN"`，`URL = "https://www.pushplus.plus/send"`。
- `class PushPlus`：`__init__(self, token: str | None = None, *, timeout_s: float = 10.0)`。`token` 为 None 时在构造时读 `os.environ[TOKEN_ENV]`（没有就是空）。
  - 属性 `enabled`（有 token 且没被停掉）、`sent`（成功发出的条数）。
  - `send(title: str, content: str) -> bool`：用 httpx 的默认传输层（门槛替换 `httpx.HTTPTransport.handle_request` 来拦截）POST 到 `URL`，JSON 请求体**恰好是** `{"token": ..., "title": ..., "content": ..., "template": "txt"}`。一对一消息就是不带 `topic`、不带 `to`。token 只放在请求体里，不放进 URL。
  - HTTP 200 并且回复 JSON 的 `code == 200` 才返回 True。
  - 回复 `code` 是 900（请求太多被限制）、905（未实名）、888（积分不足）时，返回 False，并把 `enabled` 置为 False；之后这个对象的 `send` 直接返回 False，不再发请求。pushplus 的文档说，被限制后继续请求会延长限制。
  - 其它失败（别的 code、HTTP 非 200、连接错误、超时、回复不是 JSON）只让这一条返回 False，`enabled` 不变，也不抛异常。
  - 没有 token：`enabled` 为 False，`send` 返回 False，不发请求。
  - token 绝不打印，也不写进任何输出与异常消息。标题截到 100 字符，正文截到 4000 字符。
- 命令行 `python -m surprise.notify.pushplus TITLE CONTENT`：发一条。发出去退出码 0，失败 1，没有 token 2（打印一行说明，不含 token）。
  用户以后在服务器上手动试推送就用它。

### 2. `framework/surprise/notify/watch.py`（新）

```python
@dataclass(frozen=True)
class Event:
    kind: str          # 见下表
    cell: str | None   # 格的标签 "arm/s<seed>-r<rep>"，全局事件为 None
    cause: str | None  # llm_errors 与 balance 的原因，其余为 None
    text: str          # 给人看的一句中文

def classify(reason: str | None) -> str: ...
class Watcher:
    def __init__(self, out, *, notifier=None, streak=5, stall_minutes=30.0, balance_usd=1.0,
                 balance_every_minutes=30.0, max_per_day=30, clock=time.time): ...
    def poll(self) -> list[Event]: ...
    def run(self, *, pid: int | None = None, interval_s: float = 60.0) -> int: ...
```

- `notifier` 是任何有 `send(title, content) -> bool` 的对象。None 时用 `PushPlus()`。`clock` 返回秒（Unix 时间），停滞与余额检查的时间都用它算，门槛用它模拟时间流逝。
- 读 `OUT/grid.json`（`grid run` 第一次写的、`load_config` 规整过的配置）。用 `surprise.experiments.grid` 里现成的函数（`_expected_cells`、`_cell_directory`、`_cell_log`）列出所有格、找到目录与日志；**不要改 `grid.py`**。
- 格的状态：有 `cell.json` 算结束（`status` 为 `done` 是完成，否则是失败）；目录在、没有 `cell.json` 算在跑；目录不在算未开始。
- **只读**：不在 `OUT` 下建、改、删任何文件或目录。门槛逐次比较每次 `poll` 前后的目录树（大小与 mtime）。状态只放内存，重启看守就从头读，可以接受。
- 每次 `poll` 依次判断下面这些事件。所有事件都打印到标准输出，一行一个，形如 `<UTC ISO 时间> <kind> <cell 或 -> <cause 或 -> <text>`。有事件时**合成一条消息**发出去：标题取第一个非 `start` 的事件（只有 `start` 时取它），前缀 `[CoevoDB]`，多于一个事件时标题末尾加"（共 N 条）"；正文逐条列出，每条都写格的标签。

| kind | 何时 | 只报一次的规则 |
|---|---|---|
| `start` | 第一次 `poll`，固定排在最前 | 一次。正文写主机名、`OUT`、各状态的格数，已经失败的格写进正文、不另发 `cell_failed`；做余额检查时写上剩余额度，或者写明 key 没设额度上限、只能靠调用失败发现欠费 |
| `llm_errors` | 某格 `llm/calls.jsonl` 里连续 `streak` 行 `status == "error"` | 每段连续失败报一次；一行 `ok` 或 `rejected` 让它重新可报。`cause = classify(最后一行的 reason)`，正文写原样的 reason（比如 `TransportError: HTTPStatusError 402`），cause 为 `credit` 时标题写"额度不足" |
| `llm_blocked` | 某格出现 `status == "blocked"` 的行（调用上限用完） | 每格一次 |
| `cell_failed` | 某格的 `cell.json` 新出现、`status` 不是 `done` | 每格一次。正文写 `returncode` 和格日志的最后 3 行（每行截到 300 字符） |
| `stall` | 在跑的格最近活动早于 `stall_minutes` 分钟。最近活动取这几样**文件**（不含目录）的 mtime 的最大值：格目录下直接的文件、`llm/` 下的文件、格日志 | 每格一次；之后有新活动（比报警时刻新）就重新可报 |
| `balance` | 见下 | `low` 一次、`empty` 一次、`auth` 一次 |
| `finished` | 每个格都有了 `cell.json` | 一次。正文写完成数、失败数和失败格的标签。之后 `poll` 永远返回 `[]`，`run` 返回 0 |
| `exited` | 给了 `pid`、那个进程已不在，但还有格没有 `cell.json` | 一次，正文同 `finished`，然后 `run` 返回 0 |

- 读 `calls.jsonl` 要增量读：记住读到的字节位置；最后一行没有换行符就先不读，等它写完整。只有在跑或刚结束的格才读。`status` 只有 `ok`、`rejected`、`error`、`miss`、`blocked` 几种，`miss` 不计数也不打断连续失败。
- `classify(reason)`：reason 里有独立的 `402` → `"credit"`；`401` 或 `403` → `"auth"`；`429` → `"rate"`；有 `DeadlineExceeded` → `"timeout"`；有 `is not set` → `"nokey"`；其余（包括 None、旧运行的 `"TransportError"`）→ `"other"`。门槛的对照表在 `framework/surprise/gates/s19_cases.py` 的 `CAUSES`。
- **余额检查**：只在 `grid.json` 里有臂的 `tier` 是 `"glm-flash"`、并且环境变量 `DEEPSEEK_API_KEY` 有值时做。第一次 `poll` 查一次，之后距上一次查满 `balance_every_minutes` 再查。请求是 `GET https://openrouter.ai/api/v1/key`，头 `Authorization: Bearer <DEEPSEEK_API_KEY>`，用 httpx 默认传输层，超时 10 秒。回复 `data.limit_remaining` 是数并且小于等于 0 → `balance`/`empty`；是数并且小于 `balance_usd` → `balance`/`low`；为 null（key 没设额度上限）不报警；HTTP 401 或 403 → `balance`/`auth`；连不上或别的错误只打印一行，不报警。密钥绝不打印。
  （OpenRouter 的账户余额要管理密钥才能查，普通 key 只能看到它自己的额度上限，所以 `limit_remaining` 是能拿到的最好信息。）
- **每日上限**：按 `clock()` 的 UTC 日期计数，一天最多发 `max_per_day` 条消息（pushplus 单日请求超过 1000 次会封号 7 天）。到了上限，事件照样返回、照样打印，只是不发；第二天重新计数。正好用掉最后一个名额的那条消息在正文末尾写一句"今天的推送已到上限，之后的事件只写日志"。
- `notifier.send` 返回 False 或抛异常都不影响看守继续运行。打印一行，不含 token。
- `run`：循环 `poll`，间隔 `interval_s`；`finished` 或 `exited` 之后返回 0。`pid` 存活检查要跨平台：POSIX 用 `os.kill(pid, 0)`；**Windows 上不能用 `os.kill(pid, 0)`**（它会调用 TerminateProcess 杀掉那个进程），要用 ctypes 的 `OpenProcess` + `GetExitCodeProcess`，以 `STILL_ACTIVE`（259）判断存活。
- 命令行 `python -m surprise.notify.watch OUT [--pid PID] [--interval 60] [--streak 5] [--stall-minutes 30] [--balance-usd 1.0] [--balance-every-minutes 30] [--max-per-day 30]`，退出码同 `run`。`OUT` 不存在或没有 `grid.json` 时退出码 2。

### 3. `framework/surprise/roles/gateway.py`：失败调用记下传输层的消息

`_invoke` 里 `except Exception as exc` 的那一处：异常是 `TransportError` 时，`reason` 记成 `f"TransportError: {exc}"`（`str(exc)` 为空时只记 `"TransportError"`）；别的异常照旧记 `type(exc).__name__`（现有测试 `tests/test_surprise_roles_gateway.py` 第 312 行要它是 `"RuntimeError"`）。比如 402 会记成 `"TransportError: HTTPStatusError 402"`。`transport.py` 构造的 `TransportError` 消息只有异常类名、状态码或固定文字，没有密钥；不要改 `transport.py`。

这一处只影响失败调用的 `reason`。失败会让角色停止重试（`implementer`、`translator` 的 `_STOP` 含 `error`），所以 reason 不会进 prompt，缓存键不变。gateway 的其它行为一律不动。

### 4. 测试 `framework/tests/test_surprise_s19_notify.py`（新）

覆盖上面几条，全部离线：拦截 httpx，不发真请求。测试不能依赖 `PUSHPLUS_TOKEN` 或 `DEEPSEEK_API_KEY` 有没有设置，要用 monkeypatch 设或删。

## 背景

- 门槛 `framework/surprise/gates/s19.py` 已经写好（编排者写的，你不能改），先读它：`pushplus`、`reason`、`watch`、`balance`、`cli` 五组写明了要求，`scope` 组核对改动范围。门槛用替换 `httpx.HTTPTransport.handle_request` 的办法拦截请求，所以发请求必须经 httpx 的默认传输层。
- 网格结果目录的样子：`OUT/grid.json`；`OUT/cells/<arm>/s<seed>-r<rep>/` 是格目录（`cell.json`、`progress.jsonl`、`llm/calls.jsonl` 等）；格日志是 `OUT/cells/<arm>/s<seed>-r<rep>.log`。`calls.jsonl` 每行有 `status`、`source`、`reason` 等字段（`roles/gateway.py` 的 `_account`）。
- 看守在服务器上与网格同在一个 tmux 会话里起，环境里有 `DEEPSEEK_API_KEY` 与 `PUSHPLUS_TOKEN`。部署与运行手册由编排者写，不在本包。

## 允许改动的路径

只改下面这些路径（`**` 跨目录，`*` 不跨）。审查按这个清单逐个文件核对，清单以外的任何改动都算越界。

```allow-paths
framework/surprise/notify/**
framework/surprise/roles/gateway.py
framework/tests/test_surprise_s19_notify.py
```

## 禁止

- 不改 `framework/surprise/experiments/`、`hunter/`、`diagnoser/`（S8 长跑的代码摘要绑着它们）、`framework/surprise/harness/`（已冻结）、`framework/surprise/roles/constants.py`、`roles/transport.py`、`framework/agents/`、`framework/llm/`。
- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。这一条管基线里已有的测试与门槛：其中某个测试确实该改，就写进报告的"未决问题"，停下。本包新写的测试照常修改，只要改完仍检查这份说明要求的东西。（看守里"推送失败不影响看守"是这份说明要求的行为，不算吞掉失败；那里只接住发送这一步。）
- 不登录、不连接实验服务器（不用 ssh、scp、rsync、sftp）。
- 不发任何真实的 pushplus 消息或 OpenRouter 请求（没有给你 token 与密钥）；测试一律离线。token 与密钥只走环境变量，不打印，不写进代码、配置、日志、提交或报告。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不顺手改别的：比如欠费时中断这一格（HANDOFF 的 S19 新发现第 1 条的后半）不在本包范围。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
pytest -q testing tests                              # 1086 passed, 3 skipped 的基线上只增不减，skip 不增加
python -m surprise.gates.s19                         # S19 GATE: PASS (11/11)
python -m surprise.gates.s09                         # PASS
python -m surprise.gates.s10                         # PASS
python -m surprise.gates.s15 --only config llm prices   # PASS (3/3)
```

不用跑 `python -m surprise.gates.all`：worktree 里没有 `framework/results/s08/` 和 `.orch/sqlancer/`，S08、S11、S15 的几组本来就过不了；合并后编排者在主检出区跑全部门槛。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s19-notify

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改 / 移动自哪里）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
