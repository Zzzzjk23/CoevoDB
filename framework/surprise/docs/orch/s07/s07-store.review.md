# 审查包 · s07-store

- 生成时间：2026-10-09T16:44:06+11:00
- 基线：`session/s07`（4c7e402c981e）
- 分支：`grok/s07-store` @ cb5cb540a350，基线之上 1 个提交
- 运行：共 1 轮（返工 0 轮），最近一轮退出码 0，用时 28m04s
- grok：grok 1.0.46 (2765805b9442)；会话 `0610a9e0-8d26-4a3f-b216-6a9e05dfc867`

## 红旗汇总

- 门槛未通过（退出码 1）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s07..grok/s07-store
git diff -M --stat session/s07..grok/s07-store
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/theory/constants.py`、`framework/surprise/theory/theory.py`、`framework/surprise/theory/vspace.py`、`framework/surprise/theory/length.py`、`framework/surprise/theory/store.py`、`framework/surprise/theory/__init__.py`、`framework/tests/test_surprise_s07_*.py`、`framework/tests/test_surprise_s06_constants.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/theory/__init__.py` |  |
| M | `framework/surprise/theory/constants.py` |  |
| A | `framework/surprise/theory/length.py` |  |
| A | `framework/surprise/theory/store.py` |  |
| M | `framework/surprise/theory/theory.py` |  |
| M | `framework/surprise/theory/vspace.py` |  |
| M | `framework/tests/test_surprise_s06_constants.py` |  |
| A | `framework/tests/test_surprise_s07_store.py` |  |
| A | `framework/tests/test_surprise_s07_theory_api.py` |  |

提交：

- cb5cb54 Junke: theory(s07): store each hypothesis, append-only logs, and generation snapshots

## 2. diff 统计

```text
 framework/surprise/theory/__init__.py           |  11 +-
 framework/surprise/theory/constants.py          |  12 +
 framework/surprise/theory/length.py             |  29 ++
 framework/surprise/theory/store.py              | 586 ++++++++++++++++++++++++
 framework/surprise/theory/theory.py             |  41 +-
 framework/surprise/theory/vspace.py             |  15 +
 framework/tests/test_surprise_s06_constants.py  |   6 +-
 framework/tests/test_surprise_s07_store.py      | 485 ++++++++++++++++++++
 framework/tests/test_surprise_s07_theory_api.py | 174 +++++++
 9 files changed, 1352 insertions(+), 7 deletions(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，0m44s；passed 528，skipped 3

```text
........................ss..................................s........... [ 13%]
........................................................................ [ 27%]
........................................................................ [ 40%]
........................................................................ [ 54%]
........................................................................ [ 67%]
........................................................................ [ 81%]
........................................................................ [ 94%]
...........................                                              [100%]
528 passed, 3 skipped in 43.63s
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，5m15s

```text
[PASS] constants: 4 new constants beside the nine of S6, all in the manifest; a change is reported by name (0s)
[PASS] length: hypothesis = 8.0 + 7.4 x |S| bits; theory = sum (0s)
[PASS] theory_api: remove, reserve_id, passes, next_id; common_conjunction agrees with generalize on 81 pairs (0s)
[PASS] store: one file per hypothesis, save/load is the identity, 22 damaged stores refused, logs append-only (0s)
[PASS] generations: closing a generation snapshots its last state and leaves the live state alone; snapshots load, predict and are checked (0s)
[FAIL] imports: surprise/theory/edits.py must be hashed into the run manifest
[FAIL] edits: AttributeError: module 'surprise.theory' has no attribute 'Proposal'
[FAIL] accept: AttributeError: module 'surprise.theory' has no attribute 'Workbench'
[FAIL] rollback: AttributeError: module 'surprise.theory' has no attribute 'Workbench'
[FAIL] journal: AttributeError: module 'surprise.theory' has no attribute 'Workbench'
[FAIL] mdl: AttributeError: module 'surprise.theory' has no attribute 'Workbench'
[FAIL] families: AttributeError: module 'surprise.theory' has no attribute 'Workbench'
[FAIL] ciao: AttributeError: module 'surprise.theory' has no attribute 'Workbench'
[FAIL] replay: AttributeError: module 'surprise.theory' has no attribute 'Workbench'
[FAIL] ledger: AttributeError: module 'surprise.theory' has no attribute 'Workbench'
S07 GATE: FAIL (5/15 groups passed)
=== summary ===
s01: PASS
s02: PASS
s03: PASS
s04: PASS
s05: PASS
s06: PASS
s07: FAIL (exit 1)
GATES: FAIL (6/7 passed)
```

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
- 日志 `.orch/logs/s07-store.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 无

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s07-store.jsonl`：4708 条事件（auto_compact_completed 1，auto_compact_started 1，available_commands 76，end 1，orch.exit 1，orch.start 1，text 550，thought 3440，tool_call 121，tool_call_update 453，usage 63）；各轮合计 63 个模型回合，grok 上报花费 1.8436 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_update [completed]: exit: 0 N 26 '........................ss..................................s........... [ 13%]' '........................................................................ [ 27%]' '.…
thought: 已确认 brief.md 的内容格式，将按原样处理。 已确认 ANSI 颜色仅用于终端显示，实际文本内容相同。S06 日志第 11–23 行为门控输出（13 行），清单为单行。git 状态干净。准备撰写报告。
tool_call write: {"file_path": "D:\\CoevoDB\\.worktrees\\s07-store\\.orch\\report.md", "content": "# 报告 · s07-store\n\n提交 `cb5cb54`（`grok/s07-store`）。`git status` 干净。\n\n## 改了哪些文件\n- `framework/su…
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "", "new_string": "# 报告 · s07-store\n\n提交 `cb5cb54`（`grok/s07-store`）。`git status` 干净。\n\n## 改了哪些文件\n- `framework/surprise…
tool_call run_terminal_command: {"command": "git status --short; git check-ignore -v .orch/report.md", "description": "Confirm report is ignored and tree is clean"}
tool_update [in_progress]: 
tool_update [in_progress]: .gitignore:16:.orch/.orch/report.md
tool_update [completed]: exit: 0 .gitignore:16:.orch/.orch/report.md
thought: 当前工作区干净，没有未提交的更改。
text: 工作包 `s07-store` 已完成，提交在 `cb5cb54`（`grok/s07-store`），工作区干净。报告在 `.orch/report.md`（未入库）。 理论现在可以落盘：每个假设一个文件，三份只追加日志，以及按代快照。`Theory` 增加了 `next_id`、`remove`、`reserve_id`、`passes`，合取语言增加…
end: stopReason=end_turn turns=63 cost_usd=1.84355208
orch.exit: {"pkg": "s07-store", "run": 1, "at": "2026-10-09T16:43:53+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s07-store

提交 `cb5cb54`（`grok/s07-store`）。`git status` 干净。

## 改了哪些文件
- `framework/surprise/theory/constants.py`：修改。在原有九项之后追加 `MDL_HYPOTHESIS_BITS`、`MDL_LITERAL_BITS`、`ACCEPT_HOLDOUT_MAX`、`ACCEPT_TOLERANCE_BITS`。
- `framework/surprise/theory/theory.py`：修改。新增 `next_id`、`remove`、`reserve_id`、`passes`；`reserve_id` 与 `_open_family` 共用 `_peek_id`，计数器只在新家族创建成功后推进。
- `framework/surprise/theory/vspace.py`：修改。新增 `common_conjunction`。
- `framework/surprise/theory/length.py`：新增。`hypothesis_length` 与 `theory_length`。
- `framework/surprise/theory/store.py`：新增。`StoreError` 与 `TheoryStore`：每假设一个文件、三份只追加日志、按代快照、严格读回与 `verify`。
- `framework/surprise/theory/__init__.py`：修改。导出 `StoreError`、`TheoryStore`、`common_conjunction`、`hypothesis_length`、`theory_length`。
- `framework/tests/test_surprise_s06_constants.py`：修改。`EXPECTED` 补上四项新常数；子进程改为打印完整的 `sorted(constants.as_dict())`。
- `framework/tests/test_surprise_s07_theory_api.py`：新增。常数、描述长度、四个 `Theory` 补充、`common_conjunction`。
- `framework/tests/test_surprise_s07_store.py`：新增。往返、缩小理论时删文件、非法编号拒写、六类严格读回、三份日志、快照与 `verify`。

## 跑了哪些命令

### `cd framework; python -m pytest -q testing tests`
退出码：0

终端给进度点加了 ANSI 颜色。下面是去掉转义符后的全文（9 行，与原文行数一致）：

```
........................ss..................................s........... [ 13%]
........................................................................ [ 27%]
........................................................................ [ 40%]
........................................................................ [ 54%]
........................................................................ [ 67%]
........................................................................ [ 81%]
........................................................................ [ 94%]
...........................                                              [100%]
528 passed, 3 skipped in 44.57s
```

### `cd framework; python -m surprise.gates.s07 --only constants length theory_api store generations`
退出码：0

```
[PASS] constants: 4 new constants beside the nine of S6, all in the manifest; a change is reported by name (0s)
[PASS] length: hypothesis = 8.0 + 7.4 x |S| bits; theory = sum (0s)
[PASS] theory_api: remove, reserve_id, passes, next_id; common_conjunction agrees with generalize on 81 pairs (0s)
[PASS] store: one file per hypothesis, save/load is the identity, 22 damaged stores refused, logs append-only (0s)
[PASS] generations: closing a generation snapshots its last state and leaves the live state alone; snapshots load, predict and are checked (0s)
S07 GATE [only: constants, length, theory_api, store, generations]: PASS (5/5 groups passed)
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
[PASS] manifest: theory section: 9 constants, 14 theory files and 12 feature files hashed, vocabulary and limits; harness part and the S4 freeze verify unchanged; stored with a run; tampering reported (1s)
[PASS] walkthrough: DF-A 6.64 bits opens h2; two predictions at 1.00 bit: left_has_dups enters G, INTERSECT ALL fails with another identity and opens h3; surprises 6.64, 1.00, 1.00, 0.07, 4.32, 0.01; 6 records, surprise recomputed from the ledger (20s)
S06 GATE: PASS (12/12 groups passed)
```

### `cd framework; python -m surprise.harness.manifest verify surprise/gates/s04_frozen.json`
退出码：0

```
OK 50fa40cf2d1988e8718369487b42be2c1da1a76964c0c520af51ce919b8d5fd9
```

## 与说明的偏差
验收写的是 `pytest -q testing tests`。本机 `pytest` 与 `python` 都是 `D:\CoevoDB\.venv\Scripts\` 下的同一个解释器，但直接跑 `pytest` 时 pytest 9.1.1 把 `framework/tests` 插到 `sys.path` 最前，`import surprise` 失败。实际跑的是 `python -m pytest -q testing tests`（当前目录 `framework/`），由 Python 把 `framework` 放在 `sys.path` 最前。解释器没换。结果 528 passed、3 skipped，退出码 0。

## 未决问题
无。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：

**合并。**（2026-10-09，首轮，没有返工；一处性能问题不为它开返工，写进下一个包 `s07-accept` 的说明顺带修）

依据：

- 独立复跑在 cb5cb54 上：pytest 528 passed / 3 skipped（基线 514，新增 14 个测试，skip 未增加）；S01–S06 全过，S07 本包五组 `constants length theory_api store generations` 全过，其余十组属于下一个包（此时为红，预期之内）；冻结清单校验未变。
- 完整 diff 读过（实现六个文件，其中 `store.py` 586 行；测试两个新文件 659 行，一处定向更新）。改动只在允许路径内；`theory.py` 只加了 `next_id`、`remove`、`reserve_id`、`passes`，并把铸号抽成 `_peek_id` 供 `reserve_id` 与 `_open_family` 共用，原行为不变；`tests/test_surprise_s06_constants.py` 的改动恰好是说明许可的两点（精确集合加四项、新进程打印整份名单），断言没有放宽。没有新增 skip / xfail、没有宽泛的异常捕获、没有改测试配置。
- 与编排者的参考模型做差分核对（`.orch/scratch/s7/review_store.py`）：150 段随机历史、三个作用域，途中随机 `save`、追加日志、封存一代、逐个移除假设；每一步把两边存储目录的全部文件逐字节比较，另查没有 `\r`、没有残留的 `.tmp`、`load()` 读回的状态与版本号相同、重新打开后一致。8455 项零出入。
- 损坏注入：30 个随机存储各做 12 次随机单点改动（改值、删键、加键、删行、重复行、倒序、截断、删文件），`load()` 要么抛 `StoreError`、要么读回与原来逐字段相同的理论（360 次里 1 次改动恰好是空操作）；没有一次返回了不同的理论，没有一次抛出别的异常类型。
- `Theory` 的四个补充与 `common_conjunction`、长度（同一脚本）：`reserve_id` 与新家族铸号随机交替，从不重号；`remove` 后其余次序不变、版本号变化、`put` 回去能恢复；`common_conjunction` 在 3000 对随机合取上等于闭包之交的约简，对称、幂等，并等于 `generalize`；长度在 200 个随机理论上等于 `8.0 + 7.4 × |S|` 之和。合计 23995 项零出入。
- 理论层没有连接引擎、执行 SQL、调用模型的代码；存储只在给定的根目录下读写，非法编号在落盘之前被拒。

发现一处性能问题，不影响正确性：`last_seq` 每次调用都把 `journal.jsonl` 整个读一遍并逐行解析，`append_journal` 与 `close_generation` 都调用它。实测追加一条：日志 1000 条时 17 毫秒，5000 条 77 毫秒，20000 条 389 毫秒，线性增长。S8 的长 run 每条观察都要追加一次，必须改成把序号缓存在实例里。说明里写了"打开时读一遍日志以确定下一个序号"，没有明说之后不许再读，算编排者写得不够明确。已写进 `s07-accept` 的说明第 9 节，并为这一处向它开放 `store.py`。

另记两件留给 S8 的实测数字（不是本包的问题）：记住的通过到 1 万条时，`Theory.version` 一次约 47 毫秒，`store.save` 一次约 157 毫秒（两者都与状态大小成正比，因为 `Theory.to_dict()` 每次带上全部通过）。
