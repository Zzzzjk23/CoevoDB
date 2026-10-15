# 审查包 · s11-dedup

- 生成时间：2026-10-16T05:57:28+11:00
- 基线：`session/s11`（ba4019a937d1）
- 分支：`grok/s11-dedup` @ 0f4558e28aa8，基线之上 1 个提交
- 运行：共 1 轮（返工 0 轮），最近一轮退出码 0，用时 42m04s
- grok：grok 1.0.46 (2765805b9442)；会话 `ebdf3610-585d-4bf1-81d1-46d5de867c3b`

## 红旗汇总

- 本次审查包没有复跑测试（--skip-tests）
- 派发以来有 2 处 tag 变化或 ref 被删：确认是编排者自己做的，不是执行者

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s11..grok/s11-dedup
git diff -M --stat session/s11..grok/s11-dedup
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/metrics/dedup.py`、`framework/surprise/metrics/coverage.py`、`framework/tests/test_surprise_s11_dedup.py`、`framework/tests/test_surprise_s11_coverage.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| A | `framework/surprise/metrics/coverage.py` |  |
| A | `framework/surprise/metrics/dedup.py` |  |
| A | `framework/tests/test_surprise_s11_coverage.py` |  |
| A | `framework/tests/test_surprise_s11_dedup.py` |  |

提交：

- 0f4558e Junke: metrics(s11): offline sigma-vs-membership dedup and upstream regression replay

## 2. diff 统计

```text
 framework/surprise/metrics/coverage.py        | 208 +++++++++++++++++++
 framework/surprise/metrics/dedup.py           | 279 +++++++++++++++++++++++++
 framework/tests/test_surprise_s11_coverage.py | 123 +++++++++++
 framework/tests/test_surprise_s11_dedup.py    | 282 ++++++++++++++++++++++++++
 4 files changed, 892 insertions(+)
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

- 无

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s11-dedup.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 删除 `refs/heads/grok/s11-arms`（原 134967c2d427）
- 删除 `refs/heads/grok/s11-grid`（原 10adc21b1420）
- 新增 `refs/heads/grok/s11-report` @ 22b4b9af4eef
- 移动 `refs/heads/session/s11` ba4019a937d1 → 520c70478410

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s11-dedup.jsonl`：3433 条事件（available_commands 74，end 1，orch.exit 1，orch.start 1，text 456，thought 2219，tool_call 111，tool_call_update 515，usage 55）；各轮合计 55 个模型回合，grok 上报花费 1.4725 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
thought: 正在查看 .orch/brief.md 文件，准备按说明完成工作包。 正在确定报告格式。按 brief 要求原样贴出摘要行，进度条将用点号表示。 已确认 pytest 输出包含 12 个进度行及摘要。将保留百分比标记，仅去除 ANSI 颜色代码以确保可读性。 决定采用纯文本点号进度条，直接粘贴日志中去除 ANSI 颜色后的精确摘要行。 将用中文撰写报告。已…
tool_call write: {"file_path": "D:\\CoevoDB\\.worktrees\\s11-dedup\\.orch\\report.md", "content": "# 报告 · s11-dedup\n\n## 改了哪些文件\n- `framework/surprise/metrics/dedup.py`：新增。`compare_dedup` 与命令行。只读…
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "", "new_string": "# 报告 · s11-dedup\n\n## 改了哪些文件\n- `framework/surprise/metrics/dedup.py`：新增。`compare_dedup` 与命令行。只读运行目录，比…
thought: 正在确认 git 状态是否干净，报告文件已被忽略，且提交已存在。
tool_call run_terminal_command: {"command": "git status --short; git log -1 --oneline", "description": "Confirm the worktree is clean after the report"}
tool_update [in_progress]: 
tool_update [in_progress]: 0f4558e metrics(s11): offline sigma-vs-membership dedup and upstream regression replay
tool_update [completed]: exit: 0 0f4558e metrics(s11): offline sigma-vs-membership dedup and upstream regression replay
thought: Git 工作区干净，没有未提交的更改。
text: 离线去重对比和上游回归重放已经做完，提交在 `grok/s11-dedup` 的 `0f4558e`。两个模块只测量，不写账本、不改运行目录。 - `framework/surprise/metrics/dedup.py`：在同一次运行的失败上比较旧 σ 键和执行前成员检验（`zone == "confirmed"`），真值是完整 CVE 画像的身份键。 …
end: stopReason=end_turn turns=55 cost_usd=1.47248356
orch.exit: {"pkg": "s11-dedup", "run": 1, "at": "2026-10-16T05:57:17+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s11-dedup

## 改了哪些文件
- `framework/surprise/metrics/dedup.py`：新增。`compare_dedup` 与命令行。只读运行目录，比较 σ 与执行前成员检验。
- `framework/surprise/metrics/coverage.py`：新增。`select` / `replay` / `compare` 与两条命令。重放上游回归种子，不写账本。
- `framework/tests/test_surprise_s11_dedup.py`：新增。一次 F1 引导、再选 2 条的真实 `loop.run`，核对每个字段与汇总、只读、`reprofile=False`、版本不符。
- `framework/tests/test_surprise_s11_coverage.py`：新增。`select` 的次序与 limit，3 条种子、1 个 oracle 的 `replay`（两次相同，并与直接 `certify` 对过），`compare` 的三张清单。

提交：`0f4558e`，分支 `grok/s11-dedup`。`git status` 干净。

## 跑了哪些命令

命令在 `framework/` 下执行。

### `python -m pytest -q tests/test_surprise_s11_coverage.py --tb=short`

退出码：0

```
....                                                                     [100%]
4 passed in 4.37s
```

### `python -m pytest -q tests/test_surprise_s11_dedup.py --tb=line`

退出码：0

```
.....                                                                    [100%]
5 passed in 6.76s
```

### `python -m surprise.gates.s11 --only dedup`

退出码：0

```
[PASS] dedup: 3 failures, 1 true duplicates; sigma p/r 1.0/1.0, membership p/r None/0.0 (33s)
S11 GATE [only: dedup]: PASS (1/1 groups passed)
```

### `python -m surprise.gates.s11 --only coverage`

退出码：0

```
[PASS] coverage: 4 upstream regression seeds x 2 oracles on 1.5.5 and 1.1.3; {'plan_variant': {'old': {'pass': 4}, 'new': {'pass': 4}, 'fail_old_pass_new': [], 'fail_both': [], 'fail_new_only': []}, 'equivalent_query': {'old': {'invalid': 4}, 'new': {'invalid': 4}, 'fail_old_pass_new': [], 'fail_both': [], 'fail_new_only': []}} (7s)
S11 GATE [only: coverage]: PASS (1/1 groups passed)
```

### `python -m pytest -q testing tests --tb=line`

退出码：0

进度行是 pytest 的点（带颜色码），这里只留百分比和结尾：

```
[  8%]
[ 17%]
[ 26%]
[ 34%]
[ 43%]
[ 52%]
[ 61%]
[ 69%]
[ 78%]
[ 87%]
[ 96%]
[100%]
820 passed, 3 skipped in 230.15s (0:03:50)
```

3 个 skip 是原有测试。本包没有新增 skip / xfail，没有删断言。新测试 9 条（dedup 5，coverage 4）。

## 与说明的偏差
- 每一行的 `error_class` 都取账本里那条失败自己的 `identity.error_class`，包括离线重画像的行。门槛 `check_dedup` 对每一行都拿这个字段和账本标签比。重画像时 `truth_key` 仍用新标签算（`label_key` 的口径）。σ 的候选 `notes` 用行里的这个字段，与门槛自己调用 `SignatureEngine._signature` 的算法一致。若新标签的错误类别与账本不同，身份键用新的，行上显示的类别和 σ 的 notes 用账本的。这次 dedup 门槛通过了。
- `attribution_executions` 放在返回值顶层，不放进 `membership`。`membership.executions` 是 0。这个和是各行账本标签 `cve["attribution"]["executions"]` 之和；缺这个字段、或不是整数，记 0。不取离线重画像的新标签：重画像是 `certify(..., diagnose=True)`，不传 hypothesis，新标签的归属测试是 `not_requested`。成员检验的执行成本是运行当时记在账本上的那一次。
- `replay(seeds, oracles, *, prefix=None, limit=None)` 比说明多了两个关键字参数，用来把本次选择写进结果；不传就是 null。命令行总会把 `--prefix` / `--limit` 传进去。`compare` 在 `engine`、`prefix`、`limit`、`oracles` 不一致，或两边种子下标对不上时抛 `ValueError`。门槛给出的两份结果是同一选择，不受影响。

σ 用 `SignatureEngine(runner_factory=lambda: None, checker=None)`，引擎名保持默认的 `duckdb`，与说明里的调用和门槛一致。

## 未决问题
无。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：
