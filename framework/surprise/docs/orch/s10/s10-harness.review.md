# 审查包 · s10-harness

- 生成时间：2026-10-15T20:46:20+11:00
- 基线：`session/s10`（71a59c7f4247）
- 分支：`grok/s10-harness` @ dcf68f2628cd，基线之上 1 个提交
- 运行：共 1 轮（返工 0 轮），最近一轮退出码 0，用时 24m40s
- grok：grok 1.0.46 (2765805b9442)；会话 `2fefef9f-778e-448d-a02a-219d974f207b`

## 红旗汇总

- 改动了禁区路径 2 处：framework/surprise/harness/oracles/equivalent_query.py, framework/surprise/harness/oracles/rewrites.py
- 门槛未通过（退出码 1）
- 新增宽泛的异常捕获 2 处（确认没有吞掉失败）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s10..grok/s10-harness
git diff -M --stat session/s10..grok/s10-harness
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/harness/oracles/rewrites.py`、`framework/surprise/harness/oracles/equivalent_query.py`、`framework/tests/test_surprise_s10_rewrite_library.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/harness/oracles/equivalent_query.py` | **越界：禁区** |
| M | `framework/surprise/harness/oracles/rewrites.py` | **越界：禁区** |
| A | `framework/tests/test_surprise_s10_rewrite_library.py` |  |

提交：

- dcf68f2 Junke: harness(s10): accept library rewrite templates after reference agreement

## 2. diff 统计

```text
 .../surprise/harness/oracles/equivalent_query.py   | 159 ++++++-
 framework/surprise/harness/oracles/rewrites.py     | 225 +++++++++-
 .../tests/test_surprise_s10_rewrite_library.py     | 495 +++++++++++++++++++++
 3 files changed, 870 insertions(+), 9 deletions(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，2m21s；passed 701，skipped 3

```text
........................ss..................................s........... [ 10%]
........................................................................ [ 20%]
........................................................................ [ 30%]
........................................................................ [ 40%]
........................................................................ [ 51%]
........................................................................ [ 61%]
........................................................................ [ 71%]
........................................................................ [ 81%]
........................................................................ [ 92%]
........................................................                 [100%]
701 passed, 3 skipped in 140.65s (0:02:20)
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，16m26s

```text

[FAIL] constants: roles constant REWRITE_LIBRARY_ENV must be 'SURPRISE_REWRITE_LIBRARY', got None
[FAIL] frozen: the harness is re-frozen (gates/s04_frozen.json): ['changed: surprise/harness/oracles/equivalent_query.py', 'changed: surprise/harness/oracles/rewrites.py', 'hash mismatch: manifest 50fa40cf2d19 current 98b70d9e81fc']
[PASS] library: 4 usable and 10 refused templates; 8 malformed libraries refused; judgements {'llm:wrap_sub': 'pass', 'llm:is_true': 'pass', 'llm:first_row': 'untrusted_rewrite/reference_disagrees', 'llm:octet': 'untrusted_rewrite/rewrite_error'}; frozen rule unchanged; no library, no trust (4s)
[FAIL] frame: TypeError: optimistic_rate() got an unexpected keyword argument 'prior_fails'
[FAIL] switches: UsageError: llm: unknown role 'prior'
[FAIL] prior: ModuleNotFoundError: No module named 'surprise.roles.prior'
[FAIL] translator: ModuleNotFoundError: No module named 'surprise.roles.translator'
[FAIL] vocab_inventor: ModuleNotFoundError: No module named 'surprise.roles.vocab_inventor'
[FAIL] oracle_inventor: ModuleNotFoundError: No module named 'surprise.roles.oracle_inventor'
[FAIL] translator_real: ModuleNotFoundError: No module named 'surprise.roles.translator'
[FAIL] m3: gates/s10_llm/m3 is missing: the orchestrator records it with real calls after the merge
S10 GATE: FAIL (1/12 groups passed)
=== summary ===
s01: PASS
s02: PASS
s03: PASS
s04: FAIL (exit 1)
s05: PASS
s06: FAIL (exit 1)
s07: PASS
s08: FAIL (exit 1)
s09: PASS
s10: FAIL (exit 1)
GATES: FAIL (6/10 passed)
```

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- 无

### 4.4 新增的宽泛异常捕获

- `framework/surprise/harness/oracles/equivalent_query.py:207` `except Exception:`
- `framework/surprise/harness/oracles/equivalent_query.py:215` `except Exception:`

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s10-harness.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 移动 `refs/heads/grok/s10-frame` 71a59c7f4247 → f12b92a56b26
- 移动 `refs/heads/session/s10` 71a59c7f4247 → 615dd6352cdb

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s10-harness.jsonl`：3134 条事件（available_commands 60，end 1，orch.exit 1，orch.start 1，text 367，thought 2124，tool_call 98，tool_call_update 434，usage 48）；各轮合计 48 个模型回合，grok 上报花费 1.2301 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_update [in_progress]: [FAIL] frozen: the harness is re-frozen (gates/s04_frozen.json): ['changed: surprise/harness/oracles/equivalent_query.py', 'changed: surprise/harness/oracles/rewrites.py', 'hash m…
tool_update [completed]: exit: 0 [FAIL] frozen: the harness is re-frozen (gates/s04_frozen.json): ['changed: surprise/harness/oracles/equivalent_query.py', 'changed: surprise/harness/oracles/rewrites.py',…
thought: 冻结门按预期失败。仅显示重新冻结消息，列出两个变更文件及哈希不匹配。 Git diff 检查已通过。正在收集命令输出以撰写报告，单元测试结果仅 8 行，将全部纳入。 real engines 测试通过。library gate 也已通过，4 个可用模板、10 个被拒模板、8 个格式错误库被拒，冻结规则未变。正在核对 s02、s03 和完整 pytest 的…
tool_call search_replace: {"file_path": "D:\\CoevoDB\\.worktrees\\s10-harness\\.orch\\report.md", "new_string": "# 报告 · s10-harness\n\n## 改了哪些文件\n- `framework/surprise/harness/oracles/rewrites.py`：修改。增加第二层…
tool_call run_terminal_command: {"command": "Remove-Item -Force .orch\\tmp\\probe_octet.py, .orch\\tmp\\commit-msg.txt ; git status --short", "description": "Remove scratch files and confirm a clean tree"}
tool_update [in_progress]: 
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "", "new_string": "# 报告 · s10-harness\n\n## 改了哪些文件\n- `framework/surprise/harness/oracles/rewrites.py`：修改。增加第二层库的常数、模板检查与套…
tool_update [completed]: exit: 0
thought: 工作包已完成。报告已撰写，git 状态干净。
text: 工作包 `s10-harness` 已完成，提交在 `dcf68f2`（分支 `grok/s10-harness`）。改写规则库的第二层可以读 `SURPRISE_REWRITE_LIBRARY`，机械套用 `query_wrap` 和 `predicate_wrap`；库里的规则要先有至少两个参照引擎同意，才会在目标引擎上判 fail。冻结的三条规则和它…
end: stopReason=end_turn turns=48 cost_usd=1.23005404
orch.exit: {"pkg": "s10-harness", "run": 1, "at": "2026-10-15T20:46:07+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s10-harness

## 改了哪些文件
- `framework/surprise/harness/oracles/rewrites.py`：修改。增加第二层库的常数、模板检查与套用、库文件读取；`apply_rule` 在 `llm:` 前缀下查库，冻结的三条规则仍走原来的实现。
- `framework/surprise/harness/oracles/equivalent_query.py`：修改。库里的规则在目标引擎比较之前先让参照引擎对两边的结果多重集表态；参照不一致、同意数不足，或只有改写一边报错时记 `invalid / untrusted_rewrite`。冻结规则的标签不加键。
- `framework/tests/test_surprise_s10_rewrite_library.py`：新增。覆盖模板、库文件、冻结规则输出，以及第二层四种判定和 `detail` 的键。

提交：`dcf68f2`，分支 `grok/s10-harness`。

## 跑了哪些命令

按说明没有跑 `python -m surprise.gates.s04`、`python -m surprise.gates.s06` 和 `python -m surprise.gates.all`。这两道门槛里核对冻结清单的组会因哈希变化失败，冻结清单留给编排者在合并后重新生成。

### `cd framework ; python -m pytest -q tests/test_surprise_s10_rewrite_library.py -k "not real_engines"`
退出码：0

```
........                                                                 [100%]
8 passed, 1 deselected in 0.34s
```

### `cd framework ; python -m pytest -q tests/test_surprise_s10_rewrite_library.py -k real_engines`
退出码：0

```
.                                                                        [100%]
1 passed, 8 deselected in 4.60s
```

### `cd framework ; python -m surprise.gates.s10 --only library`
退出码：0

```
[PASS] library: 4 usable and 10 refused templates; 8 malformed libraries refused; judgements {'llm:wrap_sub': 'pass', 'llm:is_true': 'pass', 'llm:first_row': 'untrusted_rewrite/reference_disagrees', 'llm:octet': 'untrusted_rewrite/rewrite_error'}; frozen rule unchanged; no library, no trust (4s)
S10 GATE [only: library]: PASS (1/1 groups passed)
```

### `cd framework ; python -m surprise.gates.s02 ; python -m surprise.gates.s03 ; python -m pytest -q testing tests`
退出码：0（前一条失败则不会跑后面的）

```
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 51 files hashed (98b70d9e81fc); verify catches 3 kinds of change
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: PASS (5/5 groups passed)
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
[PASS] local: ART exercised, injected mismatch caught; 3 proved rules x 2 engines incl NULL; untrusted pairs rejected
[PASS] cross: PG16 + DuckDB witness DF-A/DF-B; insufficient quorum, ties, multiple outliers and engine aliases rejected
[PASS] version: F2 old/new measured bags and regression direction; both old venvs work; directionless mismatch invalid
[PASS] matrix: 7 oracles x 2 engines, 14 ledger records, no hidden harness failures, manifest verified
S03 GATE: PASS (5/5 groups passed)
........................ss..................................s........... [ 10%]
........................................................................ [ 20%]
........................................................................ [ 30%]
........................................................................ [ 40%]
........................................................................ [ 51%]
........................................................................ [ 61%]
........................................................................ [ 71%]
........................................................................ [ 81%]
........................................................................ [ 92%]
........................................................                 [100%]
701 passed, 3 skipped in 139.73s (0:02:19)
```

全套测试 701 通过、3 跳过（起点 692，skip 仍是 3）。上面贴的是这条命令输出的最后 20 行；第一行 `[PASS] contracts: ...` 被这 20 行截掉。

### `cd framework ; python -m surprise.gates.s10 --only frozen`
退出码：1（预期）

```
[FAIL] frozen: the harness is re-frozen (gates/s04_frozen.json): ['changed: surprise/harness/oracles/equivalent_query.py', 'changed: surprise/harness/oracles/rewrites.py', 'hash mismatch: manifest 50fa40cf2d19 current 98b70d9e81fc']
S10 GATE [only: frozen]: FAIL (0/1 groups passed)
```

失败只有这一条：相对 `s09-done-r2` 的 harness diff 只有这两个已提交文件，冻结规则的输出没有变。清单本身还是旧哈希。

## 与说明的偏差
- 占位符必须是扫描器里相邻的三个词元 `{`、名字、`}`。写在字符串里面的 `{q}` / `{p}` 整条模板不认。门槛里的可用模板都是真正的词元，这条更严的检查不影响它们。
- `_DML` 按扫描器的关键字词元判断，不按子串。字符串里的 `DELETE` 不拒绝模板；作为关键字出现的 `DELETE`、`INSERT`、`CREATE` 会拒绝。
- 参照引擎在建 runner、setup 或执行时抛出异常，记为 `skipped`，不把这次判定变成 harness 错误。setup 返回错误、或两边有一边没有成功结果，也是 `skipped`。

## 未决问题
无。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：

合并。三处红旗都是预期的：两个 harness 文件是用户批准的解冻范围（git diff 只动了这两个）；门槛失败来自冻结清单待重生成与其他包未合并；两处 `except Exception` 把跑不起来的参照引擎记为 skipped，同意数仍须达到 2。编排者另用真实引擎核对：DuckDB 目标时三个参照都计入，DataFusion 目标时 DuckDB / PostgreSQL / SQLite 都计入。
