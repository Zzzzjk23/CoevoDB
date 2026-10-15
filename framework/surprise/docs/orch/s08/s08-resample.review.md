# 审查包 · s08-resample

- 生成时间：2026-10-15T08:21:28+11:00
- 基线：`session/s08`（3110d6e88fef）
- 分支：`grok/s08-resample` @ 085513e51f54，基线之上 1 个提交
- 运行：共 1 轮（返工 0 轮），最近一轮退出码 0，用时 33m06s
- grok：grok 1.0.46 (2765805b9442)；会话 `8621ac0c-e563-4a3f-bbae-a593b8b3e7be`

## 红旗汇总

- 门槛未通过（退出码 1）
- 测试里被改写的断言 1 处（逐条确认没有放宽）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s08..grok/s08-resample
git diff -M --stat session/s08..grok/s08-resample
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/hunter/hunter.py`、`framework/surprise/hunter/constants.py`、`framework/tests/test_surprise_s08_hunter*.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/hunter/constants.py` |  |
| M | `framework/surprise/hunter/hunter.py` |  |
| M | `framework/tests/test_surprise_s08_hunter.py` |  |

提交：

- 085513e Junke: feat(s08-resample): redraw an empty choice and skip seeds with a failed setup

## 2. diff 统计

```text
 framework/surprise/hunter/constants.py      |   3 +
 framework/surprise/hunter/hunter.py         | 106 +++++++-------
 framework/tests/test_surprise_s08_hunter.py | 207 +++++++++++++++++++++++++++-
 3 files changed, 268 insertions(+), 48 deletions(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，1m50s；passed 613，skipped 3

```text
........................ss..................................s........... [ 11%]
........................................................................ [ 23%]
........................................................................ [ 35%]
........................................................................ [ 46%]
........................................................................ [ 58%]
........................................................................ [ 70%]
........................................................................ [ 81%]
........................................................................ [ 93%]
........................................                                 [100%]
613 passed, 3 skipped in 110.12s (0:01:50)
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，11m51s

```text
[PASS] ledger: 24 adjudicated failures in 10 manual families: new framework 11 families, ARI 0.974, pair F1 0.976 (P 1.00 R 0.95); sigma 19 families, ARI 0.425, pair F1 0.444 (P 1.00 R 0.29); merged against the ledger: []; split against it: ['DF-D|DF-D_where'] (54s)
S07 GATE: PASS (15/15 groups passed)
=== gate s08 ===
[PASS] no_llm: hunter, metrics, baselines, diagnoser and the loop import no model client and no old agent (0s)
[PASS] constants: 12 hunter and 2 diagnoser constants as planned; BETA = 1.0 (pre-experiment families per run: {'0.5': {'9001': 1, '9002': 3, '9003': 3}, '1.0': {'9001': 3, '9002': 3, '9003': 3}, '2.0': {'9001': 3, '9002': 3, '9003': 3}, '4.0': {'9001': 3, '9002': 5, '9003': 1}}) (0s)
[PASS] scoring: U untested 0.498 bits, adjacent 0.758; pending 0.455 after 50 probes, adjacent unexplored 1.365 at beta 2, confirmed 0 (0s)
[PASS] operators: 29 mutants of a three-statement case (4 deletions); oracle options filtered as planned (0s)
[PASS] candidates: after F1 and DF-A: {'refine': 4, 'generalize': 4, 'migrate': 2, 'explore': 81} candidates, all traceable; chose refine at 0.909 (11s)
[PASS] lanes: 32 records; executed {'bootstrap': 2, 'explore': 23, 'generalize': 3, 'refine': 4}; offered {'refine': 30, 'generalize': 31, 'migrate': 139, 'explore': 2474}; 4 families opened, 2 edits (48s)
[PASS] determinism: seed 31 twice in separate processes: 26 identical rows, labels and final theory; seed 32 differs (28s)
[FAIL] longrun: s08_runs.json has no 'longrun' entry yet
[FAIL] sawtooth: s08_runs.json has no 'longrun' entry yet
[FAIL] duplicates: s08_runs.json has no 'longrun' entry yet
[FAIL] recall: s08_runs.json has no 'recall' entry yet
S08 GATE: FAIL (7/11 groups passed)
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

- `framework/tests/test_surprise_s08_hunter.py:136` 原：`assert set(last.pool) == {*LANES, "rejected_known", "rejected_bad_setup", "rejected_novelty", "scored"}` → 同一处新增：`assert set(last.pool) == {`；`assert last.pool["rounds"] == 1`

### 4.4 新增的宽泛异常捕获

- 无

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s08-resample.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 移动 `refs/heads/session/s08` 3110d6e88fef → a7f56d85609e

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s08-resample.jsonl`：2860 条事件（available_commands 60，end 1，orch.exit 1，orch.start 1，text 511，thought 1682，tool_call 87，tool_call_update 465，usage 52）；各轮合计 52 个模型回合，grok 上报花费 1.0638 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_update [completed]: exit: 0 [grok/s08-resample 085513e] feat(s08-resample): redraw an empty choice and skip seeds with a failed setup 3 files changed, 268 insertions(+), 48 deletions(-) 085513e feat(…
thought: Git 工作区干净，没有未提交的更改。 提交已成功。接下来将撰写 .orch/report.md 报告并删除临时提交消息文件。报告会说明父 fixture 的差异，以及额外添加的 rounds == 1 检查（符合需求 d）。 父 fixture 的引入是唯一偏差，其余无未解决事项。报告将精确复刻 gates.all 末尾 20 行与 pytest 输出。…
tool_call write: {"file_path": "D:\\CoevoDB\\.worktrees\\s08-resample\\.orch\\report.md", "content": "# 报告 · s08-resample\n\n## 改了哪些文件\n- `framework/surprise/hunter/constants.py`：新增 `EMPTY_ROUNDS …
tool_call run_terminal_command: {"command": "Remove-Item -LiteralPath .orch\\tmp\\commit-s08-resample.txt; git status --short; git status", "description": "Remove commit-message scratch file and confirm clean tr…
tool_update [in_progress]: 
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "", "new_string": "# 报告 · s08-resample\n\n## 改了哪些文件\n- `framework/surprise/hunter/constants.py`：新增 `EMPTY_ROUNDS = 20`（int…
tool_update [in_progress]: On branch grok/s08-resample nothing to commit, working tree clean
tool_update [completed]: exit: 0 On branch grok/s08-resample nothing to commit, working tree clean
thought: 工作包已按 .orch/brief.md 的说明完成。
text: 工作包 `s08-resample` 已完成，提交 `085513e`，工作区干净。 一次选择先定下 `index` 和 `slot`，最多再抽 `EMPTY_ROUNDS`（20）轮。车道和三类拒绝计数跨轮相加，`scored` 与 `scored_pool` 只保留选出结果的那一轮，并记下 `rounds`。探索抽样会先去掉 setup 已经报错的种子…
end: stopReason=end_turn turns=52 cost_usd=1.06383144
orch.exit: {"pkg": "s08-resample", "run": 1, "at": "2026-10-15T08:21:12+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s08-resample

## 改了哪些文件
- `framework/surprise/hunter/constants.py`：新增 `EMPTY_ROUNDS = 20`（int），注释一行，格式与本文件其他常数相同。
- `framework/surprise/hunter/hunter.py`：`_explore` 先按语料次序去掉 setup 已报错的种子，再抽样；该引擎一个不剩就跳过，不调用 `sample`。`choose` 每次选择只定一次 `index` 与 `slot`，最多抽 `EMPTY_ROUNDS` 轮；某一轮的选择范围非空就在该轮里按原规则选定。`pool` 的车道与三类拒绝计数是各轮合计，`scored` 与 `scored_pool` 只取选出结果的那一轮，并多一个键 `rounds`。同一轮内的键去重不跨轮。
- `framework/tests/test_surprise_s08_hunter.py`：坏 setup 不再被抽到（过滤后的种子表保持语料次序）；第一轮被新颖性抽签滤空、第二轮同一候选通过时 `rounds == 2` 且计数是两轮合计；连续 `EMPTY_ROUNDS` 轮为空返回 `None`；正常选择 `rounds == 1`。原有的 `pool` 键集合断言加上 `rounds`。

提交：`085513e` `feat(s08-resample): redraw an empty choice and skip seeds with a failed setup`，分支 `grok/s08-resample`。

## 跑了哪些命令

### `cd framework; python -m pytest -q testing tests`
退出码：0

```
........................ss..................................s........... [ 11%]
........................................................................ [ 23%]
........................................................................ [ 35%]
........................................................................ [ 46%]
........................................................................ [ 58%]
........................................................................ [ 70%]
........................................................................ [ 81%]
........................................................................ [ 93%]
........................................                                 [100%]
613 passed, 3 skipped in 115.52s (0:01:55)
```

### `cd framework; python -m surprise.gates.s08 --only no_llm constants scoring operators candidates lanes determinism`
退出码：0

```
[PASS] no_llm: hunter, metrics, baselines, diagnoser and the loop import no model client and no old agent (0s)
[PASS] constants: 12 hunter and 2 diagnoser constants as planned; BETA = 1.0 (pre-experiment families per run: {'0.5': {'9001': 1, '9002': 3, '9003': 3}, '1.0': {'9001': 3, '9002': 3, '9003': 3}, '2.0': {'9001': 3, '9002': 3, '9003': 3}, '4.0': {'9001': 3, '9002': 5, '9003': 1}}) (0s)
[PASS] scoring: U untested 0.498 bits, adjacent 0.758; pending 0.455 after 50 probes, adjacent unexplored 1.365 at beta 2, confirmed 0 (0s)
[PASS] operators: 29 mutants of a three-statement case (4 deletions); oracle options filtered as planned (0s)
[PASS] candidates: after F1 and DF-A: {'refine': 4, 'generalize': 4, 'migrate': 2, 'explore': 81} candidates, all traceable; chose refine at 0.909 (11s)
[PASS] lanes: 32 records; executed {'bootstrap': 2, 'explore': 23, 'generalize': 3, 'refine': 4}; offered {'refine': 30, 'generalize': 31, 'migrate': 139, 'explore': 2474}; 4 families opened, 2 edits (49s)
[PASS] determinism: seed 31 twice in separate processes: 26 identical rows, labels and final theory; seed 32 differs (28s)
S08 GATE [only: no_llm, constants, scoring, operators, candidates, lanes, determinism]: PASS (7/7 groups passed)
```

### `cd framework; python -m surprise.gates.all`
退出码：1（s08 的四组按说明允许失败；s01–s07 全部 PASS）

末 20 行：

```
[PASS] scoring: U untested 0.498 bits, adjacent 0.758; pending 0.455 after 50 probes, adjacent unexplored 1.365 at beta 2, confirmed 0 (0s)
[PASS] operators: 29 mutants of a three-statement case (4 deletions); oracle options filtered as planned (0s)
[PASS] candidates: after F1 and DF-A: {'refine': 4, 'generalize': 4, 'migrate': 2, 'explore': 81} candidates, all traceable; chose refine at 0.909 (11s)
[PASS] lanes: 32 records; executed {'bootstrap': 2, 'explore': 23, 'generalize': 3, 'refine': 4}; offered {'refine': 30, 'generalize': 31, 'migrate': 139, 'explore': 2474}; 4 families opened, 2 edits (48s)
[PASS] determinism: seed 31 twice in separate processes: 26 identical rows, labels and final theory; seed 32 differs (28s)
[FAIL] longrun: s08_runs.json has no 'longrun' entry yet
[FAIL] sawtooth: s08_runs.json has no 'longrun' entry yet
[FAIL] duplicates: s08_runs.json has no 'longrun' entry yet
[FAIL] recall: s08_runs.json has no 'recall' entry yet
S08 GATE: FAIL (7/11 groups passed)
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

s08 失败的四组是 `longrun`、`sawtooth`、`duplicates`、`recall`，原因是 `s08_runs.json` 还没有对应条目。其余七组 PASS。

## 与说明的偏差
- `test_choose_explore_slot_ties_and_filter_counts` 末尾的 `assert blocked.pool["rejected_bad_setup"] >= 1` 没有改写、没有放宽。这条断言原来靠探索车道抽出坏 setup 再被 `choose` 滤掉。按本包的新规则，探索不再抽这些种子，而该测试在此之前没有假设，细化 / 泛化 / 迁移都是空的，计数会变成 0。因此在最后一次 `choose` 之前，用这段已经报错的 setup 观察并登记了一个父本，让细化 / 泛化车道的变异体仍然经过 `choose` 里保留的坏 setup 过滤。断言原文仍在。
- `EMPTY_ROUNDS` 的注释写在常数上一行，与 `constants.py` 里其余常数一致。说明里的代码块把同一句注释写在行尾。

## 未决问题
无。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：
**合并**（首轮通过，返工 0 轮）。理由：

- 完整 diff 已读：`EMPTY_ROUNDS = 20`；`_explore` 先去掉 setup 报过错的种子再抽；`choose` 的 index 与 slot 只定一次，最多抽 20 轮，计数为各轮合计并加 `rounds`，`scored` 与 `scored_pool` 取选出结果的那一轮。与说明一致。
- 红旗：改写的断言是键集合里加上 `rounds`（说明要求，更严，不是放宽）；`rejected_bad_setup >= 1` 那条原文保留，执行者在它之前补了一个用坏 setup 的父本，让 `choose` 里保留的坏 setup 过滤仍被测到，合理。门槛未过的四组是编排者的产物组。
- 独立复跑 613 passed / 3 skipped（起点 610），s01–s07 PASS，s08 的七组短跑 7/7。
- 13 条 shell 命令看过（含一条查标准库 `random.py` 位置的查询），没有越界；deny 拦截 0 次，密钥 0。约 1.06 美元。

