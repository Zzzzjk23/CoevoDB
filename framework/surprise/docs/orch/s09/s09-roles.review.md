# 审查包 · s09-roles

- 生成时间：2026-10-15T17:30:15+11:00
- 基线：`session/s09`（cbe27732142e）
- 分支：`grok/s09-roles` @ f233f343da08，基线之上 2 个提交
- 运行：共 2 轮（返工 1 轮），最近一轮退出码 0，用时 24m05s
- grok：grok 1.0.46 (2765805b9442)；会话 `d561037a-7848-45e5-bd63-193faea7ab9d`

## 红旗汇总

- 本次审查包没有复跑测试（--skip-tests）
- 测试里被改写的断言 1 处（逐条确认没有放宽）
- grok 日志里有 3 行疑似密钥（日志不入库，但要查来源）
- 派发以来有 2 处 tag 变化或 ref 被删：确认是编排者自己做的，不是执行者

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s09..grok/s09-roles
git diff -M --stat session/s09..grok/s09-roles
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/roles/__init__.py`、`framework/surprise/roles/constants.py`、`framework/surprise/roles/implementer.py`、`framework/surprise/roles/conjecturer.py`、`framework/surprise/roles/runtime.py`、`framework/surprise/roles/sources_map.py`、`framework/tests/test_surprise_roles_implementer.py`、`framework/tests/test_surprise_roles_conjecturer.py`、`framework/tests/test_surprise_roles_runtime.py`、`framework/tests/test_surprise_roles_gateway.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/roles/__init__.py` |  |
| A | `framework/surprise/roles/conjecturer.py` |  |
| M | `framework/surprise/roles/constants.py` |  |
| A | `framework/surprise/roles/implementer.py` |  |
| A | `framework/surprise/roles/runtime.py` |  |
| A | `framework/surprise/roles/sources_map.py` |  |
| A | `framework/tests/test_surprise_roles_conjecturer.py` |  |
| M | `framework/tests/test_surprise_roles_gateway.py` |  |
| A | `framework/tests/test_surprise_roles_implementer.py` |  |
| A | `framework/tests/test_surprise_roles_runtime.py` |  |

提交：

- d268bfc Junke: feat(s09-roles): implementer, conjecturer, and the role runtime
- f233f34 Junke: feat(s09-roles): raise token caps and keep ok candidates

## 2. diff 统计

```text
 framework/surprise/roles/__init__.py               |  23 +
 framework/surprise/roles/conjecturer.py            | 752 +++++++++++++++++++++
 framework/surprise/roles/constants.py              |   6 +-
 framework/surprise/roles/implementer.py            | 459 +++++++++++++
 framework/surprise/roles/runtime.py                | 382 +++++++++++
 framework/surprise/roles/sources_map.py            |  58 ++
 framework/tests/test_surprise_roles_conjecturer.py | 474 +++++++++++++
 framework/tests/test_surprise_roles_gateway.py     |   4 +-
 framework/tests/test_surprise_roles_implementer.py | 265 ++++++++
 framework/tests/test_surprise_roles_runtime.py     | 337 +++++++++
 10 files changed, 2756 insertions(+), 4 deletions(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

按 `--skip-tests` 跳过了 pytest 与门槛。

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- `framework/tests/test_surprise_roles_gateway.py:349` 原：`assert not hasattr(R, "Implementer")` → 同一处新增：`assert R.Implementer is ImplementerClass`

### 4.4 新增的宽泛异常捕获

- 无

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s09-roles.jsonl` 中疑似密钥行数：3

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 删除 `refs/heads/grok/s09-gateway`（原 3f4621a0e28d）
- 删除 `refs/heads/grok/s09-wire`（原 d3c39e51b11d）
- 移动 `refs/heads/session/s09` cbe27732142e → 04c0da98eb09

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s09-roles.jsonl`：11793 条事件（auto_compact_completed 3，auto_compact_started 3，available_commands 251，end 2，orch.exit 2，orch.start 2，plan 4，text 1761，thought 7668，tool_call 438，tool_call_update 1443，usage 216）；各轮合计 216 个模型回合，grok 上报花费 5.6453 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
text: 验收命令已重跑。全量测试只剩旧门槛那一条失败；实现器 30/30 最终通过。我把「第 1 轮返工」接到报告末尾。
tool_call search_replace: {"file_path": "D:\\CoevoDB\\.worktrees\\s09-roles\\.orch\\report.md", "old_string": "- 没有跑 `wiring`、`implementer_report`、`dfa`、`replay`，也没有跑 `python -m surprise.gates.all`。\n", "n…
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "- 没有跑 `wiring`、`implementer_report`、`dfa`、`replay`，也没有跑 `python -m surprise.gates.all`。\n", "new_string": "- 没有跑 `wiring`…
thought: 正在确认 git 状态干净，且报告部分位于文件末尾。
tool_call run_terminal_command: {"command": "Set-Location D:\\CoevoDB\\.worktrees\\s09-roles; git status --short; git log -1 --oneline; git check-ignore -v .orch/report.md", "description": "Confirm the report is…
tool_update [in_progress]: 
tool_update [in_progress]: f233f34 feat(s09-roles): raise token caps and keep ok candidates
tool_update [completed]: exit: 0 f233f34 feat(s09-roles): raise token caps and keep ok candidates .gitignore:16:.orch/.orch/report.md
thought: Git 工作区干净，没有未提交的更改。 已按审查意见完成返工，提交至 f233f34 并追加了 .orch/report.md。报告内容涵盖完成事项、变更摘要及测试结果：pytest 658 项通过、1 项失败（预期常量）、3 项跳过；s09 5/7、s08 1/1。
text: 第 1 轮返工已提交到 `grok/s09-roles` 的 `f233f34`，`.orch/report.md` 末尾已追加「第 1 轮返工」。工作区除被忽略的 `.orch/` 外是干净的。 改动是审查列出的五处：实现器上限 8000、猜想者上限 16000；猜想提示去掉 “at most two”；DuckDB 命中文件按 `SOURCE_MAX_…
end: stopReason=end_turn turns=56 cost_usd=1.45778808
orch.exit: {"pkg": "s09-roles", "run": 2, "at": "2026-10-15T17:29:54+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s09-roles

## 改了哪些文件
- `framework/surprise/roles/constants.py`：修改。`CONJECTURER_TIER` 从 `strong` 改为 `fast`，其余字符未动。
- `framework/surprise/roles/sources_map.py`：新增。DuckDB 优化器文件表与 DataFusion 选源规则。
- `framework/surprise/roles/implementer.py`：新增。实现器、提示、报告与命令行。
- `framework/surprise/roles/conjecturer.py`：新增。猜想、猜想簿、选源与猜想者。
- `framework/surprise/roles/runtime.py`：新增。`RoleSet`、`ImplementerSource`、`build_roles`。
- `framework/surprise/roles/__init__.py`：修改。在网关导出之后追加本包的名字。
- `framework/tests/test_surprise_roles_implementer.py`：新增。
- `framework/tests/test_surprise_roles_conjecturer.py`：新增。
- `framework/tests/test_surprise_roles_runtime.py`：新增。

## 跑了哪些命令
每条命令的工作目录都是 `framework/`。退出码写在命令后面。

### `python -m pytest -q tests/test_surprise_roles_implementer.py tests/test_surprise_roles_conjecturer.py tests/test_surprise_roles_runtime.py`

退出码 0。提示改短之后又跑了一次，同样是 23 passed。最后一次输出：

```
.......................                                                  [100%]
23 passed in 1.53s
```

### `python -m surprise.gates.s09 --only isolation constants cache reject cap source implementer conjecturer`

退出码 0。

```
[PASS] isolation: roles load no model client until a transport is built; loop, Hunter, Diagnoser, harness never import them; transport reuses BaseAgent and the old ledger (1s)
[PASS] constants: 19 constants as planned; tiers {'fast': 'deepseek-flash', 'strong': 'deepseek-v4-pro'} (0s)
[PASS] cache: key = prompt hash + model + seed; hits make no call; replay identical; forged entry refused; ledger and per-role totals (0s)
[PASS] reject: 9 replies parsed as planned; refusals replay as refusals; the implementer refuses before phi (0s)
[PASS] cap: cap 2 blocks the third call; cache served past the cap; cap 0 calls nothing; env ceiling; errors count, not cached (0s)
[PASS] source: confined, exact, read-only; checkouts at datafusion 45d943dfb869, duckdb d8cdaa33fda8 (0s)
[PASS] implementer: accepted, retried with feedback, unmet, bad case, replayed, blocked (0s)
[PASS] conjecturer: selection picks datafusion/expr/src/logical_plan/builder.rs for DF-A and src/optimizer/filter_pushdown.cpp for ('filter_pushdown',); registered with a revise whose bets are its predictions; settled by experiments; refusals, drops, not covering, blocked (9s)
S09 GATE [only: isolation, constants, cache, reject, cap, source, implementer, conjecturer]: PASS (8/8 groups passed)
```

提示改短之后重跑了 `python -m surprise.gates.s09 --only conjecturer`，退出码 0，1/1。

### `python -m surprise.gates.s08 --only no_llm`

退出码 0。

```
[PASS] no_llm: hunter, metrics, baselines, diagnoser and the loop import no model client and no old agent (0s)
S08 GATE [only: no_llm]: PASS (1/1 groups passed)
```

### `python -m pytest -q testing tests`

退出码 1。这一次在猜想者提示改短之前。改动只是提示里的两句英文，角色测试与 `conjecturer` 组在改后已通过。最后 20 行：

```
        assert R.constants is constants
        assert R.Gateway is GatewayClass
        assert R.ResponseCache is CacheClass
        assert R.Completion is Completion
        assert R.Reply is Reply
        assert R.TransportError is TransportError
        assert "transport" not in R.__all__
>       assert not hasattr(R, "Implementer")
E       AssertionError: assert not True
E        +  where True = hasattr(<module 'surprise.roles' from 'D:\\CoevoDB\\.worktrees\\s09-roles\\framework\\surprise\\roles\\__init__.py'>, 'Implementer')

tests\test_surprise_roles_gateway.py:349: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_surprise_roles_gateway.py::test_package_exports_and_does_not_load_transport - AssertionError: assert not True
 +  where True = hasattr(<module 'surprise.roles' from 'D:\\CoevoDB\\.worktrees\\s09-roles\\framework\\surprise\\roles\\__init__.py'>, 'Implementer')
1 failed, 657 passed, 3 skipped in 131.82s (0:02:11)
```

### 实现器命令行（正式提示，`IMPLEMENTER_MAX_TOKENS` = 2000）

先跑 10 个 core，再跑全部 30 个规格。缓存目录相同，第二次里 core 的 12 次是缓存命中。

```
python -m surprise.roles.implementer --specs D:\CoevoDB\.worktrees\s09-roles\.orch\tmp\implementer_cores.json --cache D:\CoevoDB\.worktrees\s09-roles\.orch\tmp\llmcache --out D:\CoevoDB\.worktrees\s09-roles\.orch\tmp\impl_cores_report.json --max-calls 18
```

退出码 0。

```
<frozen runpy>:128: RuntimeWarning: 'surprise.roles.implementer' found in sys.modules after import of package 'surprise.roles', but prior to execution of 'surprise.roles.implementer'; this may result in unpredictable behaviour
specs=10 first_ok=8 final_ok=10 first_rate=0.8000 final_rate=1.0000
```

```
python -m surprise.roles.implementer --specs D:\CoevoDB\.worktrees\s09-roles\.orch\tmp\implementer_specs.json --cache D:\CoevoDB\.worktrees\s09-roles\.orch\tmp\llmcache --out D:\CoevoDB\.worktrees\s09-roles\.orch\tmp\impl_report.json --max-calls 47
```

退出码 0。

```
<frozen runpy>:128: RuntimeWarning: 'surprise.roles.implementer' found in sys.modules after import of package 'surprise.roles', but prior to execution of 'surprise.roles.implementer'; this may result in unpredictable behaviour
specs=30 first_ok=22 final_ok=25 first_rate=0.7333 final_rate=0.8333
```

`wiring`、`implementer_report`、`dfa`、`replay` 和 `python -m surprise.gates.all` 没有跑。

## 真实调用
账本里 `source == "network"` 的行一共 48 次，都是 fast 档（`deepseek-flash`）。没有用 strong。

| 账本 | 网络次数 | 做什么 |
| --- | --- | --- |
| `.orch/tmp/impl_cores_report.calls.jsonl` | 12 | 10 个 core |
| `.orch/tmp/impl_report.calls.jsonl` | 26 | 全部 30 个规格；另有 12 次缓存命中 |
| `.orch/tmp/impl_long.calls.jsonl` | 7 | 诊断：只把那 5 个失败规格的 `max_tokens` 临时改成 8000，代码未改 |
| `.orch/tmp/dfa_conjecture.calls.jsonl` | 1 | DF-A，改提示之前，上限 8000 |
| `.orch/tmp/dfa_long.calls.jsonl` | 1 | 诊断：同一条旧提示，上限临时 16000 |
| `.orch/tmp/dfa_short.calls.jsonl` | 1 | DF-A，当前提示，上限 8000 |

最后一版实现器提示、上限 2000：30 个规格，`first_ok` 22，`final_ok` 25，`first_rate` 0.7333，`final_rate` 0.8333。按种类：whole 6/10 首次、7/10 最终；core 8/10 首次、10/10 最终；boundary 8/10 首次、8/10 最终。5 个未过的都是两次 `rejected` / `no_json`，回复正文为空，`output_tokens` 正好 2000。它们是 `F1/whole`、`F2/whole`、`F7/boundary`、`F11/whole`、`DF-I/boundary`。

把这 5 个的输出上限临时放到 8000（不入库）：7 次网络调用，4 个变为 `ok`，`F7/boundary` 仍是 `spec_unmet`，forbidden 含 `ast:expr:interval`。`ast:expr:date_arith` 的判定要求出现 INTERVAL，而这条 boundary 又禁止 `ast:expr:interval`，所以这条规格在检查器下做不到。

DF-A 猜想，当前提示，上限 `CONJECTURER_MAX_TOKENS`（8000）：1 次网络调用，`output_tokens` 5314，`status=registered`，`accepted=true`，`edit_reason` 为空。

机制：LogicalPlanBuilder::intersect_or_except maps EXCEPT ALL to a LeftAnti join with NullEqualsNull, which removes every left row that has any matching right row instead of subtracting multiset counts.

trigger：`ast:set_op:except_all`、`ast:stmt:select`、`data:setop:left_has_dups`、`data:table:dup_rows`。

预测两条，oracle 都是 `cross_dbms`，`data_properties` 都是 `[]`：

- expect `fail`。required：`ast:set_op:except_all`、`ast:stmt:select`、`data:setop:left_has_dups`、`data:table:dup_rows`、`data:type:integer`。forbidden：`data:setop:left_has_null`、`data:setop:right_has_null`、`data:table:has_null`。
- expect `pass`。required：`ast:set_op:except_all`、`ast:stmt:select`、`data:setop:left_has_null`、`data:setop:right_has_null`、`data:table:has_null`、`data:type:integer`。forbidden：`data:setop:left_has_dups`、`data:table:dup_rows`。

改提示之前的同一次调用在 8000 上限处返回空正文（`no_json`）。把上限临时放到 16000 时，旧提示也能 `registered` 并被接受，`output_tokens` 10860。当前提示把机制收成一句、预测收到至多两条，因此能在 8000 以内写完。

## 与说明的偏差
- 说明把空的 `query` 字符串写成字段检查失败、状态 `rejected`。门槛 `check_implementer` 的 `bad_case` 用 `query: ""`，而 `SqlCase` 对空 query 抛 `ValueError`。空字符串不是字段错误，会落到 `SqlCase`，状态是 `bad_case`。缺 `query`、query 不是字符串、expect 非法、缺 predicate 仍是 `rejected`。按门槛实现。
- 全量 `python -m pytest -q testing tests` 没有通过。失败点是网关包测试 `tests/test_surprise_roles_gateway.py:349` 的 `assert not hasattr(R, "Implementer")`。本说明第 6 节和 `gates/s09.py` 都要求从 `surprise.roles` 导出 `Implementer`。该测试文件不在允许改动的路径里，没有改它，也没有为了让它通过而撤掉导出。657 passed、3 skipped、1 failed。skip 仍是 3。通过数高于网关包合并时的基线（新增 23 个测试，旧测试里只有这一条从通过变成失败）。

## 未决问题
- 请编排者删掉或改写 `framework/tests/test_surprise_roles_gateway.py` 第 349 行 `assert not hasattr(R, "Implementer")`。这是网关包在实现器尚未导出时留下的断言。同函数后半段的隔离探测没有跑到；`gates/s09.py` 的 `isolation` 组已在新进程里通过。
- `IMPLEMENTER_MAX_TOKENS` 是 2000。`deepseek-flash` 把推理 token 算进这个上限，复杂规格会在写出 JSON 之前用完，网关只能看到空正文。常数表本包只能改 `CONJECTURER_TIER`，所以没有提高这个上限。临时 8000 能让其中 4 个规格通过。
- `F7/boundary` 要求 `ast:expr:date_arith` 并禁止 `ast:expr:interval`。当前检查器里日期运算一定带出 INTERVAL，这条 boundary 无法被 φ 接受。
- `python -m surprise.roles.implementer` 会打一条 runpy RuntimeWarning：包的 `__init__.py` 已经导入了 `implementer`。命令仍退出码 0，并打出那一行 ASCII 摘要。
- 没有跑 `wiring`、`implementer_report`、`dfa`、`replay`，也没有跑 `python -m surprise.gates.all`。

# 第 1 轮返工

提交 `f233f34`（`feat(s09-roles): raise token caps and keep ok candidates`），分支 `grok/s09-roles`。报告未入库。

## 改了哪些文件
- `framework/surprise/roles/constants.py`：修改。`IMPLEMENTER_MAX_TOKENS` 2000 → 8000，`CONJECTURER_MAX_TOKENS` 8000 → 16000。其余未动。
- `framework/surprise/roles/conjecturer.py`：修改。删掉提示里的 "Use at most two predictions"，保留 "Write the JSON object first. Do not analyse at length before the JSON."。DuckDB 命中的 k 个文件（最多 `SOURCE_MAX_FILES`）各取第 1 行到第 `SOURCE_MAX_LINES // k` 行。删掉 `_DUCKDB_HEAD`。
- `framework/surprise/roles/runtime.py`：修改。`ImplementerSource.candidates` 每次调用都返回迄今全部 `ok` 尝试，按尝试顺序；新实现仍只在尚未服务过的 index 的第 1 轮进行，最多 `per_choice` 个。
- `framework/tests/test_surprise_roles_gateway.py`：修改。只改了导出断言：`R.Implementer is ImplementerClass`。同函数后半段的新进程隔离探测未动。
- `framework/tests/test_surprise_roles_conjecturer.py`：修改。选源测试覆盖 1 个文件前 400 行、2 个文件各 200 行、4 个文件各 100 行。
- `framework/tests/test_surprise_roles_runtime.py`：修改。已实现的候选在后续选择里仍返回；补了「未选中的候选一直在，Hunter 执行过之后不再选它」。

## 跑了哪些命令
工作目录都是 `framework/`。

### `python -m pytest -q testing tests`

退出码 1。只失败 `test_constants_match_the_gate_table`（旧门槛表仍是 2000）。658 passed，3 skipped。

```
........................................................................ [ 54%]
........................................................................ [ 65%]
........................................................................ [ 76%]
........................................................................ [ 87%]
........................................................................ [ 97%]
..............                                                           [100%]
================================== FAILURES ===================================
_____________________ test_constants_match_the_gate_table _____________________

    def test_constants_match_the_gate_table() -> None:
        have = constants.as_dict()
        for name, value in C.CONSTANTS.items():
            assert name in have
>           assert have[name] == value
E           assert 8000 == 2000

tests\test_surprise_roles_gateway.py:101: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_surprise_roles_gateway.py::test_constants_match_the_gate_table - assert 8000 == 2000
1 failed, 658 passed, 3 skipped in 127.44s (0:02:07)
```

### `python -m surprise.gates.s09 --only isolation cache reject cap source implementer conjecturer`

退出码 1。5/7。`constants` 组按审查没有跑。

```
[PASS] isolation: roles load no model client until a transport is built; loop, Hunter, Diagnoser, harness never import them; transport reuses BaseAgent and the old ledger (1s)
[PASS] cache: key = prompt hash + model + seed; hits make no call; replay identical; forged entry refused; ledger and per-role totals (0s)
[PASS] reject: 9 replies parsed as planned; refusals replay as refusals; the implementer refuses before phi (0s)
[PASS] cap: cap 2 blocks the third call; cache served past the cap; cap 0 calls nothing; env ceiling; errors count, not cached (0s)
[PASS] source: confined, exact, read-only; checkouts at datafusion 45d943dfb869, duckdb d8cdaa33fda8 (0s)
[FAIL] implementer: the implementer uses its tier and settings: deepseek-flash
[FAIL] conjecturer: the conjecturer uses its tier
S09 GATE [only: isolation, cache, reject, cap, source, implementer, conjecturer]: FAIL (5/7 groups passed)
```

### `python -m surprise.gates.s08 --only no_llm`

退出码 0。

```
[PASS] no_llm: hunter, metrics, baselines, diagnoser and the loop import no model client and no old agent (0s)
S08 GATE [only: no_llm]: PASS (1/1 groups passed)
```

### 实现器真实调用

```
python -m surprise.roles.implementer --specs D:\CoevoDB\.worktrees\s09-roles\.orch\tmp\implementer_specs2.json --cache D:\CoevoDB\.worktrees\s09-roles\.orch\tmp\llmcache2 --out D:\CoevoDB\.worktrees\s09-roles\.orch\tmp\impl_report2.json --max-calls 39
```

退出码 0。规格来自门槛的 `IMPLEMENTER_SPECS`，只把 `F7/boundary` 改成 `required = ["ast:expr:interval", "data:type:date"]`、`forbidden = ["ast:expr:date_arith"]`。缓存目录是新的。

```
<frozen runpy>:128: RuntimeWarning: 'surprise.roles.implementer' found in sys.modules after import of package 'surprise.roles', but prior to execution of 'surprise.roles.implementer'; this may result in unpredictable behaviour
specs=30 first_ok=29 final_ok=30 first_rate=0.9667 final_rate=1.0000
EXIT=0
```

### 猜想者真实调用

从 `framework/` 用 `python -c` 执行 `.orch/tmp/dfa2.py`：`dfa()` 建出 DF-A 工作台，`DeepSeekTransport()`，缓存 `.orch/tmp/llmcache2-dfa`，`max_calls=1`，种子 `CONJECTURE_SEED`。

退出码 0。

```
status registered reason None
predictions 5 expects ['fail', 'pass', 'fail', 'pass', 'fail']
output_tokens 5645 network 1 accepted True reply ok None
```

`wiring`、`implementer_report`、`dfa`、`replay`、`python -m surprise.gates.all` 以及 `python -m surprise.gates.s09 --only constants` 没有跑。

## 真实调用
本轮账本里 `source == "network"` 共 32 次，都是 fast 档（`deepseek-flash`）。没有用 strong。上限按审查留在 40 以内：实现器 `--max-calls 39`，猜想者 `max_calls=1`。环境变量 `SURPRISE_LLM_MAX_CALLS` 为 60，网关取两者的较小值。

| 账本 | 网络次数 | 做什么 |
| --- | --- | --- |
| `.orch/tmp/impl_report2.calls.jsonl` | 31 | 30 个规格；其中 `F1/whole` 用了第二次尝试。缓存命中 0 |
| `.orch/tmp/dfa2.calls.jsonl` | 1 | DF-A，新提示，上限 16000 |

实现器：`first_ok` 29，`final_ok` 30，`first_rate` 0.9667，`final_rate` 1.0000。按种类：boundary 10/10 首次、10/10 最终；core 10/10、10/10；whole 9/10、10/10。30 条最终都是 `ok`，包括改过规格的 `F7/boundary`。唯一重试的是 `F1/whole`。

DF-A：`registered`，`accepted=true`，`edit_reason` 为空，`output_tokens` 5645，预测 5 条（fail、pass、fail、pass、fail），oracle 都是 `cross_dbms`，`data_properties` 都是 `[]`。

机制：DataFusion's LogicalPlanBuilder::intersect_or_except implements EXCEPT ALL as a LeftAnti HashJoinExec with NullEqualsNull instead of a multiset difference, so any left row with a matching right key is removed entirely rather than decrementing duplicate counts.

trigger：`ast:set_op:except_all`、`data:setop:left_has_dups`、`data:table:dup_rows`。

五条预测的 `required` 都含 `ast:set_op:except_all`、`ast:stmt:select`、`data:type:integer`、`plan:DataSourceExec`、`plan:HashJoinExec`。差异在集合运算的数据特征：三条 fail 带 `data:setop:left_has_dups` 与 `data:table:dup_rows`（其中一条还带 `data:setop:right_has_dups`），并禁止 null 特征；两条 pass 里，一条改为两侧 null、禁止重复行，另一条保留左侧重复行、禁止 null，期望在没有匹配右行时结果与正确语义一致。

## 与说明的偏差
- 审查的验收写的是上述 s09 七组 7/7。本 worktree 的 `framework/surprise/gates/s09_cases.py` 里 `IMPLEMENTER_MAX_TOKENS` 仍是 2000、`CONJECTURER_MAX_TOKENS` 仍是 8000。`gates/s09.py` 把真实调用的 `max_tokens` 与这张表比较，所以 implementer 组停在 "the implementer uses its tier and settings: deepseek-flash"，conjecturer 组停在 "the conjecturer uses its tier"。模型名与 fast 档一致，对不上的是 token 上限（8000 对 2000，16000 对 8000）。conjecturer 组里选源检查写在这条断言之前，组失败信息是后面的档位断言，DuckDB 改成按行数预算取文件头没有先在这里失败。`session/s09` 的 `04c0da9` 已经把门槛表改成 8000 和 16000，并改了 F7/boundary。本轮按审查没有改门槛，也没有拣那个提交。`test_constants_match_the_gate_table` 的失败是审查写明的预期。
- 真实调用的 `F7/boundary` 用的是审查给出的新规格，写在 `.orch/tmp/implementer_specs2.json`，没有改门槛文件。

## 未决问题
- 本包的 8000 / 16000 与本 worktree 的旧门槛表还不一致。编排者在 `session/s09` 的 `04c0da9` 已改表。这棵 worktree 按审查不动 `framework/surprise/gates/`。
- 上一节里「请改第 349 行」已按本轮审查改完。全量测试里 `test_package_exports_and_does_not_load_transport` 通过，同函数后半段的隔离探测因此跑完了。
- `python -m surprise.roles.implementer` 的 runpy RuntimeWarning 还在。导出保留，没有为消掉警告改 `__init__.py`。
- 没有跑 `wiring`、`implementer_report`、`dfa`、`replay`，也没有跑 `python -m surprise.gates.all`。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：
