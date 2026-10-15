# 审查包 · s09-gateway

- 生成时间：2026-10-15T15:25:47+11:00
- 基线：`session/s09`（ad0e90b6bad7）
- 分支：`grok/s09-gateway` @ 3f4621a0e28d，基线之上 2 个提交
- 运行：共 2 轮（返工 1 轮），最近一轮退出码 0，用时 3m56s
- grok：grok 1.0.46 (2765805b9442)；会话 `3c6ac2a0-b632-4179-9432-6947fca642c2`

## 红旗汇总

- 本次审查包没有复跑测试（--skip-tests）
- 新增宽泛的异常捕获 3 处（确认没有吞掉失败）
- 疑似密钥 1 处、敏感文件名 0 个
- grok 日志里有 3 行疑似密钥（日志不入库，但要查来源）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s09..grok/s09-gateway
git diff -M --stat session/s09..grok/s09-gateway
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/roles/__init__.py`、`framework/surprise/roles/constants.py`、`framework/surprise/roles/schema.py`、`framework/surprise/roles/cache.py`、`framework/surprise/roles/gateway.py`、`framework/surprise/roles/transport.py`、`framework/surprise/roles/source.py`、`framework/tests/test_surprise_roles_gateway.py`、`framework/tests/test_surprise_roles_source.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/roles/__init__.py` |  |
| A | `framework/surprise/roles/cache.py` |  |
| A | `framework/surprise/roles/constants.py` |  |
| A | `framework/surprise/roles/gateway.py` |  |
| A | `framework/surprise/roles/schema.py` |  |
| A | `framework/surprise/roles/source.py` |  |
| A | `framework/surprise/roles/transport.py` |  |
| A | `framework/tests/test_surprise_roles_gateway.py` |  |
| A | `framework/tests/test_surprise_roles_source.py` |  |

提交：

- a3564aa Junke: feat(s09-gateway): LLM gateway, response cache, cap, ledger, and source reader
- 3f4621a Junke: fix(s09-gateway): switch TIERS to deepseek-flash and deepseek-v4-pro

## 2. diff 统计

```text
 framework/surprise/roles/__init__.py           |  23 ++
 framework/surprise/roles/cache.py              |  67 ++++
 framework/surprise/roles/constants.py          |  83 +++++
 framework/surprise/roles/gateway.py            | 308 ++++++++++++++++++
 framework/surprise/roles/schema.py             |  37 +++
 framework/surprise/roles/source.py             | 250 +++++++++++++++
 framework/surprise/roles/transport.py          |  89 ++++++
 framework/tests/test_surprise_roles_gateway.py | 425 +++++++++++++++++++++++++
 framework/tests/test_surprise_roles_source.py  | 157 +++++++++
 9 files changed, 1439 insertions(+)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

按 `--skip-tests` 跳过了 pytest 与门槛。

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- 无

### 4.4 新增的宽泛异常捕获

- `framework/surprise/roles/cache.py:62` `except Exception:`
- `framework/surprise/roles/gateway.py:225` `except Exception as exc:`
- `framework/surprise/roles/transport.py:61` `except Exception as exc:`

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- `framework/tests/test_surprise_roles_gateway.py:30` key-like token: sk-…(37 chars)
- 日志 `.orch/logs/s09-gateway.jsonl` 中疑似密钥行数：3

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 移动 `refs/heads/session/s09` ad0e90b6bad7 → a2c5cc7518a2

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s09-gateway.jsonl`：2462 条事件（available_commands 58，end 2，orch.exit 2，orch.start 2，plan 5，text 701，thought 1142，tool_call 88，tool_call_update 419，usage 43）；各轮合计 43 个模型回合，grok 上报花费 1.0515 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_call run_terminal_command: {"command": "git add framework/surprise/roles/constants.py framework/tests/test_surprise_roles_gateway.py; git commit -F .orch/tmp/msg.txt; git status; git log -2 --oneline", "des…
tool_update [in_progress]: 
tool_update [in_progress]: warning: in the working copy of 'framework/surprise/roles/constants.py', LF will be replaced by CRLF the next time Git touches it
tool_update [in_progress]: warning: in the working copy of 'framework/surprise/roles/constants.py', LF will be replaced by CRLF the next time Git touches it [grok/s09-gateway 3f4621a] fix(s09-gateway): swit…
tool_update [in_progress]: warning: in the working copy of 'framework/surprise/roles/constants.py', LF will be replaced by CRLF the next time Git touches it [grok/s09-gateway 3f4621a] fix(s09-gateway): swit…
tool_update [completed]: exit: 0 warning: in the working copy of 'framework/surprise/roles/constants.py', LF will be replaced by CRLF the next time Git touches it [grok/s09-gateway 3f4621a] fix(s09-gatewa…
tool_call run_terminal_command: {"command": "Remove-Item .orch\\tmp\\msg.txt", "description": "Delete scratch commit message file"}
tool_update [in_progress]: 
tool_update [completed]: exit: 0
text: 第 1 轮返工已提交：`3f4621a`。报告已追加到 `.orch/report.md`。 **改动** - `TIERS` 改为 `fast=deepseek-flash`、`strong=deepseek-v4-pro` - `IMPLEMENTER_PER_CHOICE` 注释改为 Hunter 每次选择可实现的新目标数 - 测试里写死的旧模型名一…
end: stopReason=end_turn turns=16 cost_usd=0.4682242
orch.exit: {"pkg": "s09-gateway", "run": 2, "at": "2026-10-15T15:25:29+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s09-gateway

## 改了哪些文件
- `framework/surprise/roles/__init__.py`：修改，导出网关、缓存、解析与读源码工具，不导出 transport
- `framework/surprise/roles/constants.py`：新增，S9 常数与 `as_dict()`
- `framework/surprise/roles/schema.py`：新增，`parse_reply` 要求非空 `prediction`
- `framework/surprise/roles/cache.py`：新增，响应缓存（键为提示哈希 + 模型 + 种子）
- `framework/surprise/roles/gateway.py`：新增，网关（缓存、上限、按角色账本、两档模型）
- `framework/surprise/roles/transport.py`：新增，`DeepSeekTransport` 复用 `BaseAgent` 与旧 `ledger`
- `framework/surprise/roles/source.py`：新增，只读源码阅读器与 `open_sources`
- `framework/tests/test_surprise_roles_gateway.py`：新增，网关/缓存/解析/传输离线测试
- `framework/tests/test_surprise_roles_source.py`：新增，源码阅读器离线测试

## 跑了哪些命令

### `python -m pytest -q testing tests`
工作目录：`framework/`。退出码：0。

```
[ 78%]
[ 90%]
           [100%]
635 passed, 3 skipped in 118.04s (0:01:58)
```

### `python -m surprise.gates.s09 --only constants cache cap source`
工作目录：`framework/`。退出码：0。

```
[PASS] constants: 19 constants as planned; tiers {'fast': 'deepseek-chat', 'strong': 'deepseek-reasoner'} (0s)
[PASS] cache: key = prompt hash + model + seed; hits make no call; replay identical; forged entry refused; ledger and per-role totals (0s)
[PASS] cap: cap 2 blocks the third call; cache served past the cap; cap 0 calls nothing; env ceiling; errors count, not cached (0s)
[PASS] source: confined, exact, read-only; checkouts at datafusion 45d943dfb869, duckdb d8cdaa33fda8 (0s)
S09 GATE [only: constants, cache, cap, source]: PASS (4/4 groups passed)
```

### `python -m surprise.gates.s09 --only reject`
工作目录：`framework/`。退出码：1（预期失败）。

```
[FAIL] reject: AttributeError: module 'surprise.roles' has no attribute 'Implementer'
S09 GATE [only: reject]: FAIL (0/1 groups passed)
```

### `python -m surprise.gates.s08 --only no_llm`
工作目录：`framework/`。退出码：0。

```
[PASS] no_llm: hunter, metrics, baselines, diagnoser and the loop import no model client and no old agent (0s)
S08 GATE [only: no_llm]: PASS (1/1 groups passed)
```

未跑 `python -m surprise.gates.all`（说明要求本包不要跑）。

## 与说明的偏差
- `reject` 组的失败信息是门槛把未捕获异常格式化后的 `AttributeError: module 'surprise.roles' has no attribute 'Implementer'`。`parse_reply` 与网关拒收已通过，失败点是 `Implementer`（下一个包）。
- 传输测试里 `base_url=http://127.0.0.1:9` 在本机得到 `HTTPStatusError 502`（不是连接被拒）。`TransportError` 文案是 `HTTPStatusError 502`，不含假密钥。

## 未决问题
无

## 第 1 轮返工

### 改了什么
- `framework/surprise/roles/constants.py`：`TIERS` 改为 `{"fast": "deepseek-flash", "strong": "deepseek-v4-pro"}`；`IMPLEMENTER_PER_CHOICE` 注释改为 `New targets the implementer source may implement per Hunter choice.`
- `framework/tests/test_surprise_roles_gateway.py`：写死的 `deepseek-chat` 改为 `deepseek-flash`；缓存行为测试里对照模型名/缓存键/manifest 的期望从本 worktree 旧门槛的 `C.TIERS` 改到 `constants.TIERS`。不改这一处的话，`test_gateway_cache_hit_replay_offline_ledger_and_totals` 会因旧门槛模型名再失败一次，审查要求只允许 `test_constants_match_the_gate_table` 失败。
- 未改 `framework/surprise/gates/`（禁区）。

### 重跑了哪些命令

#### `python -m pytest -q tests/test_surprise_roles_gateway.py tests/test_surprise_roles_source.py`
工作目录：`framework/`。退出码：1。

```
F.....................                                                   [100%]
================================== FAILURES ===================================
_____________________ test_constants_match_the_gate_table _____________________

    def test_constants_match_the_gate_table() -> None:
        have = constants.as_dict()
        for name, value in C.CONSTANTS.items():
            assert name in have
>           assert have[name] == value
E           AssertionError: assert {'fast': 'dee...pseek-v4-pro'} == {'fast': 'dee...eek-reasoner'}
E
E             Differing items:
E             {'fast': 'deepseek-flash'} != {'fast': 'deepseek-chat'}
E             {'strong': 'deepseek-v4-pro'} != {'strong': 'deepseek-reasoner'}
1 failed, 21 passed in 3.53s
```

唯一失败是 `test_constants_match_the_gate_table`（本 worktree 门槛仍是旧模型名，审查预期如此）。

#### `python -m surprise.gates.s09 --only cache cap source`
工作目录：`framework/`。退出码：1。

```
[FAIL] cache: the tier picks the model: ['deepseek-flash', 'deepseek-flash', 'deepseek-v4-pro']
[PASS] cap: cap 2 blocks the third call; cache served past the cap; cap 0 calls nothing; env ceiling; errors count, not cached (0s)
[PASS] source: confined, exact, read-only; checkouts at datafusion 45d943dfb869, duckdb d8cdaa33fda8 (0s)
S09 GATE [only: cache, cap, source]: FAIL (2/3 groups passed)
```

`cache` 失败原因与 `constants` 相同：本 worktree 的 `gates/s09_cases.py` 仍是 `deepseek-chat` / `deepseek-reasoner`，门槛拿它和网关实际选用的新模型名比较。禁区不能改门槛。主检出区 `session/s09` 的 a2c5cc7 已把门槛改成新名字，合并后 `cache` 会过。

### 与说明的偏差
- 审查写「不要动别的行」，但缓存行为测试若不改 `C.TIERS` 期望，会多失败一个测试。为满足「只允许 `test_constants_match_the_gate_table` 失败」，把该测试的模型名期望改到 `constants.TIERS`。
- 审查写 `cache cap source` 为 3/3；本 worktree 里 `cache` 因旧门槛失败，见上。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：
