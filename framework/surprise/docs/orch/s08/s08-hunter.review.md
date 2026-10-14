# 审查包 · s08-hunter

- 生成时间：2026-10-15T06:09:29+11:00
- 基线：`session/s08`（728ef04b6f23）
- 分支：`grok/s08-hunter` @ 45f267a0789a，基线之上 6 个提交
- 运行：共 2 轮（返工 1 轮），最近一轮退出码 0，用时 16m57s
- grok：grok 1.0.46 (2765805b9442)；会话 `3c806ea7-7307-4001-9563-bfe3dec2155f`

## 红旗汇总

- 改动了禁区路径 3 处：framework/surprise/docs/DECISIONS.md, framework/surprise/docs/HANDOFF.md, framework/surprise/gates/s08.py
- 改动超出 brief 允许的路径 1 处：framework/tests/test_surprise_s06_constants.py
- 门槛未通过（退出码 1）
- 新增宽泛的异常捕获 4 处（确认没有吞掉失败）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s08..grok/s08-hunter
git diff -M --stat session/s08..grok/s08-hunter
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/hunter/**`、`framework/surprise/theory/constants.py`、`framework/tests/test_surprise_s08_hunter*.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/docs/DECISIONS.md` | **越界：禁区** |
| M | `framework/surprise/docs/HANDOFF.md` | **越界：禁区** |
| M | `framework/surprise/gates/s08.py` | **越界：禁区** |
| M | `framework/surprise/hunter/__init__.py` |  |
| A | `framework/surprise/hunter/constants.py` |  |
| A | `framework/surprise/hunter/extractor.py` |  |
| A | `framework/surprise/hunter/hunter.py` |  |
| A | `framework/surprise/hunter/operators.py` |  |
| A | `framework/surprise/hunter/phi_worker.py` |  |
| A | `framework/surprise/hunter/scoring.py` |  |
| M | `framework/surprise/theory/constants.py` |  |
| M | `framework/tests/test_surprise_s06_constants.py` | **越界：不在允许路径内** |
| A | `framework/tests/test_surprise_s08_hunter.py` |  |
| A | `framework/tests/test_surprise_s08_hunter_extractor.py` |  |
| A | `framework/tests/test_surprise_s08_hunter_operators.py` |  |
| A | `framework/tests/test_surprise_s08_hunter_scoring.py` |  |

提交：

- a13d8d1 Junke: docs(s08): WIP - s08-hunter and s08-eval dispatched
- f8232ac Junke: docs(s08): record the user's confirmation of the opening choices
- 8c4bffd Junke: feat(s08-hunter): Hunter scoring, operators, phi worker, and four lanes
- e2d9a5b Junke: gates(s08): fix two expectations of the orchestrator's own
- b4bfb93 Junke: Merge session/s08 into grok/s08-hunter: the orchestrator's gate fix (e2d9a5b) before rework
- 45f267a Junke: fix(s08-hunter): generalize only when the sibling is not already in S

## 2. diff 统计

```text
 framework/surprise/docs/DECISIONS.md               |   1 +
 framework/surprise/docs/HANDOFF.md                 |   6 +-
 framework/surprise/gates/s08.py                    |   8 +-
 framework/surprise/hunter/__init__.py              |  20 +
 framework/surprise/hunter/constants.py             |  56 +++
 framework/surprise/hunter/extractor.py             | 202 ++++++++++
 framework/surprise/hunter/hunter.py                | 414 +++++++++++++++++++++
 framework/surprise/hunter/operators.py             | 197 ++++++++++
 framework/surprise/hunter/phi_worker.py            |  33 ++
 framework/surprise/hunter/scoring.py               | 149 ++++++++
 framework/surprise/theory/constants.py             |   4 +
 framework/tests/test_surprise_s06_constants.py     |   1 +
 framework/tests/test_surprise_s08_hunter.py        | 381 +++++++++++++++++++
 .../tests/test_surprise_s08_hunter_extractor.py    | 124 ++++++
 .../tests/test_surprise_s08_hunter_operators.py    | 110 ++++++
 .../tests/test_surprise_s08_hunter_scoring.py      | 119 ++++++
 16 files changed, 1819 insertions(+), 6 deletions(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，0m47s；passed 575，skipped 3

```text
........................ss..................................s........... [ 12%]
........................................................................ [ 24%]
........................................................................ [ 37%]
........................................................................ [ 49%]
........................................................................ [ 62%]
........................................................................ [ 74%]
........................................................................ [ 87%]
........................................................................ [ 99%]
..                                                                       [100%]
575 passed, 3 skipped in 46.37s
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，9m41s

```text
ModuleNotFoundError: No module named 'surprise.experiments.loop'

[FAIL] constants: ImportError: cannot import name 'constants' from 'surprise.diagnoser' (D:\CoevoDB\.worktrees\s08-hunter\framework\surprise\diagnoser\__init__.py)
[PASS] scoring: U untested 0.498 bits, adjacent 0.758; pending 0.455 after 50 probes, adjacent unexplored 1.365 at beta 2, confirmed 0 (0s)
[PASS] operators: 29 mutants of a three-statement case (4 deletions); oracle options filtered as planned (0s)
[PASS] candidates: after F1 and DF-A: {'refine': 4, 'generalize': 4, 'migrate': 2, 'explore': 81} candidates, all traceable; chose refine at 0.909 (11s)
[FAIL] lanes: the loop exits cleanly: 1 D:\CoevoDB\.venv\Scripts\python.exe: No module named surprise.experiments.loop

[FAIL] determinism: run a exits cleanly: D:\CoevoDB\.venv\Scripts\python.exe: No module named surprise.experiments.loop

[FAIL] longrun: s08_runs.json is not written yet: the orchestrator pins the artifacts after running them
[FAIL] sawtooth: ImportError: cannot import name 'curve' from 'surprise.metrics' (D:\CoevoDB\.worktrees\s08-hunter\framework\surprise\metrics\__init__.py)
[FAIL] duplicates: ImportError: cannot import name 'dups' from 'surprise.metrics' (D:\CoevoDB\.worktrees\s08-hunter\framework\surprise\metrics\__init__.py)
[FAIL] recall: ImportError: cannot import name 'recall' from 'surprise.metrics' (D:\CoevoDB\.worktrees\s08-hunter\framework\surprise\metrics\__init__.py)
S08 GATE: FAIL (3/11 groups passed)
=== summary ===
s01: PASS
s02: PASS
s03: PASS
s04: PASS
s05: PASS
s06: PASS
s07: PASS
s08: FAIL (exit 1)
GATES: FAIL (7/8 passed)
```

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- 无

### 4.4 新增的宽泛异常捕获

- `framework/surprise/hunter/extractor.py:126` `except Exception:`
- `framework/surprise/hunter/extractor.py:157` `except Exception:`
- `framework/surprise/hunter/extractor.py:171` `except Exception:`
- `framework/surprise/hunter/phi_worker.py:26` `except Exception as exc: # noqa: BLE001 - every failure is an error reply`

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s08-hunter.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 移动 `refs/heads/session/s08` 728ef04b6f23 → 825877b9ac17

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s08-hunter.jsonl`：4270 条事件（auto_compact_completed 1，auto_compact_started 1，available_commands 116，end 2，orch.exit 2，orch.start 2，plan 7，text 829，thought 1956，tool_call 227，tool_call_update 1029，usage 98）；各轮合计 98 个模型回合，grok 上报花费 2.8302 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_update [in_progress]: warning: in the working copy of 'framework/surprise/hunter/hunter.py', LF will be replaced by CRLF the next time Git touches it warning: in the working copy of 'framework/tests/te…
tool_update [in_progress]: warning: in the working copy of 'framework/surprise/hunter/hunter.py', LF will be replaced by CRLF the next time Git touches it warning: in the working copy of 'framework/tests/te…
tool_update [completed]: exit: 0 warning: in the working copy of 'framework/surprise/hunter/hunter.py', LF will be replaced by CRLF the next time Git touches it warning: in the working copy of 'framework/…
tool_call run_terminal_command: {"command": "Remove-Item .orch\\tmp\\msg.txt", "description": "Delete scratch commit message file"}
tool_call todo_write: {"todos": [{"id": "4", "status": "completed"}, {"id": "5", "status": "completed"}], "merge": true}
tool_update [in_progress]: 
tool_update [completed]: {"type": "Todo", "TodosUpdated": {"summary_for_prompt": "- [completed] 1: Tighten swapped condition in hunter.py _refine_generalize\n- [completed] 2: Update hunter tests + add ref…
plan: {"entries": [{"content": "Tighten swapped condition in hunter.py _refine_generalize", "priority": "medium", "status": "completed"}, {"content": "Update hunter tests + add refine-v…
tool_update [completed]: exit: 0
text: 已按 `.orch/review-1.md` 返工并提交 `45f267a`，报告写在 `.orch/report.md`。 **本轮改动** - `hunter.py`：`swapped` 收紧为 `sib in closure and sib not in hypothesis.specific` - `test_surprise_s08_hunter…
end: stopReason=end_turn turns=29 cost_usd=0.58381672
orch.exit: {"pkg": "s08-hunter", "run": 2, "at": "2026-10-15T06:09:16+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s08-hunter

## 改了哪些文件
- `framework/surprise/hunter/hunter.py`：`_refine_generalize` 的 `swapped` 收紧为 `sib in closure and sib not in hypothesis.specific`（修改）
- `framework/tests/test_surprise_s08_hunter.py`：四车道出处检查与门槛一致；新增「两个比较，删一个是 refine、换成 S 里没有的比较是 generalize」（修改）
- `framework/tests/test_surprise_s06_constants.py`：`EXPECTED` 加上 `"BETA": 1.0`（修改）

其余 Hunter 交付物仍在 `8c4bffd`，本轮未再改。门槛合入 `b4bfb93` 未回退、未 rebase。

## 跑了哪些命令

### `cd framework; python -m pytest -q testing tests`
退出码：0

```
........................ss..................................s........... [ 12%]
........................................................................ [ 24%]
........................................................................ [ 37%]
........................................................................ [ 49%]
........................................................................ [ 62%]
........................................................................ [ 74%]
........................................................................ [ 87%]
........................................................................ [ 99%]
..                                                                       [100%]
575 passed, 3 skipped in 46.56s
```

### `cd framework; python -m surprise.gates.s08 --only scoring operators candidates`
退出码：0

```
[PASS] scoring: U untested 0.498 bits, adjacent 0.758; pending 0.455 after 50 probes, adjacent unexplored 1.365 at beta 2, confirmed 0 (0s)
[PASS] operators: 29 mutants of a three-statement case (4 deletions); oracle options filtered as planned (0s)
[PASS] candidates: after F1 and DF-A: {'refine': 4, 'generalize': 4, 'migrate': 2, 'explore': 81} candidates, all traceable; chose refine at 0.909 (11s)
S08 GATE [only: scoring, operators, candidates]: PASS (3/3 groups passed)
```

### `cd framework; python -m surprise.gates.s06`
退出码：0

```
[PASS] constants: 9 constants as frozen; magnitudes 6.64, 4.32, 1.00, 0.07, 0.01 bits, split at 0.5 and 2.0; features and theory import in either order (1s)
[PASS] language: 10 reductions, 13 coverage checks, 8 generalisations, 12 specialisations; 7 malformed calls rejected (0s)
[PASS] vspace: 5 sequences (25 steps) reach the expected S and G; positions incl. undetermined and out of scope; G capped at 64; invariants hold over 480 random steps (0s)
[PASS] hypothesis: contract keeps S2-era objects and round-trips the new fields; 4 families started from profiles, one with earlier passes replayed; 2 attribution requests accepted by the harness parser (0s)
[PASS] identity: 17 hypothesis / label pairs judged: harness test first, then fix set, then the three profile fields (0s)
[PASS] residual: prior 0.01, counts and rate per unit, round trip; the rate never reaches 0 or 1 (0s)
[PASS] validity: prior 0.1; counts, reasons and rate per (class, oracle); round trip (0s)
[PASS] predict: surprise 6.64 / 4.32 / 1.00 / 0.07 / 0.01 bits; 6 zone predictions with precedence confirmed > pending > residual; per-unit rho and per-class K^v (0s)
[PASS] triage: 14 (label, bits) pairs incl. both thresholds; the six rows of the framework document; 8 bad calls rejected (0s)
[PASS] theory: 9 scripted experiments: 6.64 -> family, 1.00 x 2 -> G moves and a second family, 0.07 duplicate, 4.32 unexpected pass, 0.01 no information, invalid, unexplained failure; replay, reload and determinism; 4 drifted-residual cases; 6 bad calls rejected (0s)
[PASS] manifest: theory section: 9 constants, 16 theory files and 12 feature files hashed, vocabulary and limits; harness part and the S4 freeze verify unchanged; stored with a run; tampering reported (1s)
[PASS] walkthrough: DF-A 6.64 bits opens h2; two predictions at 1.00 bit: left_has_dups enters G, INTERSECT ALL fails with another identity and opens h3; surprises 6.64, 1.00, 1.00, 0.07, 4.32, 0.01; 6 records, surprise recomputed from the ledger (19s)
S06 GATE: PASS (12/12 groups passed)
```

### `cd framework; python -c "import sys, surprise.hunter, surprise.hunter.extractor; bad=[m for m in ('openai','httpx','httpx2','agents','llm','guidelines','evolution.co_evolution') if m in sys.modules]; print('LLM-FREE' if not bad else bad)"`
退出码：0

```
LLM-FREE
```

### `cd framework; python -m surprise.gates.all`
退出码：1（s08 其余组属于别的包与编排者，说明允许）

```
[PASS] candidates: after F1 and DF-A: {'refine': 4, 'generalize': 4, 'migrate': 2, 'explore': 81} candidates, all traceable; chose refine at 0.909 (11s)
[FAIL] lanes: the loop exits cleanly: 1 D:\CoevoDB\.venv\Scripts\python.exe: No module named surprise.experiments.loop

[FAIL] determinism: run a exits cleanly: D:\CoevoDB\.venv\Scripts\python.exe: No module named surprise.experiments.loop

[FAIL] longrun: s08_runs.json is not written yet: the orchestrator pins the artifacts after running them
[FAIL] sawtooth: ImportError: cannot import name 'curve' from 'surprise.metrics' (D:\CoevoDB\.worktrees\s08-hunter\framework\surprise\metrics\__init__.py)
[FAIL] duplicates: ImportError: cannot import name 'dups' from 'surprise.metrics' (D:\CoevoDB\.worktrees\s08-hunter\framework\surprise\metrics\__init__.py)
[FAIL] recall: ImportError: cannot import name 'recall' from 'surprise.metrics' (D:\CoevoDB\.worktrees\s08-hunter\framework\surprise\metrics\__init__.py)
S08 GATE: FAIL (3/11 groups passed)
=== summary ===
s01: PASS
s02: PASS
s03: PASS
s04: PASS
s05: PASS
s06: PASS
s07: PASS
s08: FAIL (exit 1)
GATES: FAIL (7/8 passed)
```

s01–s07 全部 PASS。s08 失败组是 `no_llm` `constants` `lanes` `determinism` `longrun` `sawtooth` `duplicates` `recall`，均属别的包与编排者。

## 与说明的偏差
无。本轮按审查意见改了 `swapped` 判定、对应测试和 s06 的 `EXPECTED["BETA"]`。

## 未决问题
无。上一轮三处未决由编排者改门槛并开放 s06 测试路径后，本轮已对齐。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：
**合并**（返工 1 轮）。理由：

- 完整 diff 已读（`hunter/` 七个文件、`theory/constants.py` 的 `BETA`、四个测试文件、S6 常数测试加一行）。打分、算子、常驻提取进程、四条车道、过滤与选择都与说明逐条一致；随机数只来自 `Random(seed)` 与 `Random(seed + 1)`，集合只做成员判断。
- 第 1 轮停下上报的三处都是编排者的错（漏放钉住常数名单的旧测试、门槛里重复行的期望、泛化判定写宽），返工意见放行了 `tests/test_surprise_s06_constants.py` 并给出新的泛化判定；门槛修正 `e2d9a5b` 由编排者合进本分支（`b4bfb93`）。本轮 diff 只有 `hunter.py` 一处条件、S6 测试一行、Hunter 测试加两例。
- 红旗：禁区三处来自编排者的合并（分支上碰过 gates/docs 的只有编排者的 e2d9a5b、f8232ac、a13d8d1，内容与 e2d9a5b 相同）；越界一处是本轮放行的 S6 测试；四处宽泛异常是提取进程的降级与清理，不吞测试失败；门槛未过的组属于 `s08-loop` 与编排者的产物。
- 独立复跑 575 passed / 3 skipped，s01–s07 PASS，s08 的 `scoring operators candidates` 3/3（细化 4、泛化 4、迁移 2、探索 81）。
- 编排者另做的探测：引导 F1、DF-A 后真实执行 25 次选择（约 45 秒）：探索保底恰在第 5、10、15、20、25 次；细化 2、泛化 6、探索 17；第 10 次的探索保底开出一个新家族（plan variant，6.64 比特）；提取进程 3424 次调用、命中缓存 2941 次、零超时。另核对过 F1、DF-A 待定区的全部变体在新判定下有细化也有泛化。
- 两轮的 shell 命令逐条看过：pytest、门槛、`python -c` 探测、git 提交、删自己的提交信息临时文件。deny 拦截 0 次，密钥 0。
- 花费：第 1 轮与第 2 轮合计见审查包第 6 节。

