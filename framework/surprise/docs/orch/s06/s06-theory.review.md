# 审查包 · s06-theory

- 生成时间：2026-10-09T15:09:08+11:00
- 基线：`session/s06`（c4995fdaa326）
- 分支：`grok/s06-theory` @ 9e4366f75073，基线之上 1 个提交
- 运行：共 1 轮（返工 0 轮），最近一轮退出码 0，用时 42m51s
- grok：grok 1.0.46 (2765805b9442)；会话 `133eccfc-c42a-4083-a7cf-c61a46437939`

## 红旗汇总

- 自动检查没有发现红旗。

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s06..grok/s06-theory
git diff -M --stat session/s06..grok/s06-theory
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/theory/**`、`framework/tests/test_surprise_s06_*.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/theory/__init__.py` |  |
| A | `framework/surprise/theory/__main__.py` |  |
| A | `framework/surprise/theory/manifest.py` |  |
| A | `framework/surprise/theory/predict.py` |  |
| A | `framework/surprise/theory/residual.py` |  |
| A | `framework/surprise/theory/theory.py` |  |
| A | `framework/surprise/theory/validity.py` |  |
| A | `framework/tests/test_surprise_s06_manifest.py` |  |
| A | `framework/tests/test_surprise_s06_predict.py` |  |
| A | `framework/tests/test_surprise_s06_residual.py` |  |
| A | `framework/tests/test_surprise_s06_theory.py` |  |

提交：

- 9e4366f Junke: s06-theory: add residual, validity, prediction, triage, Theory, and the manifest section

## 2. diff 统计

```text
 framework/surprise/theory/__init__.py         |  20 +-
 framework/surprise/theory/__main__.py         |  28 ++
 framework/surprise/theory/manifest.py         | 130 ++++++++
 framework/surprise/theory/predict.py          | 143 ++++++++
 framework/surprise/theory/residual.py         |  72 ++++
 framework/surprise/theory/theory.py           | 386 ++++++++++++++++++++++
 framework/surprise/theory/validity.py         | 127 ++++++++
 framework/tests/test_surprise_s06_manifest.py | 108 ++++++
 framework/tests/test_surprise_s06_predict.py  | 279 ++++++++++++++++
 framework/tests/test_surprise_s06_residual.py | 173 ++++++++++
 framework/tests/test_surprise_s06_theory.py   | 451 ++++++++++++++++++++++++++
 11 files changed, 1916 insertions(+), 1 deletion(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，0m38s；passed 514，skipped 3

```text
........................ss..................................s........... [ 13%]
........................................................................ [ 27%]
........................................................................ [ 41%]
........................................................................ [ 55%]
........................................................................ [ 69%]
........................................................................ [ 83%]
........................................................................ [ 97%]
.............                                                            [100%]
514 passed, 3 skipped in 37.68s
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 0，4m59s

```text
[PASS] specs: 17 hand-written spec / SQL pairs, all judged correctly (0s)
[PASS] corpus: 1092 seeds in 76 units over 10 constructs; ast fallback 34, plan ok 480, data ok 483; top [('postgres|plain|none|unknown', 134), ('duckdb|plain|none|unknown', 83), ('duckdb|window|none|unknown', 56)]; 12s (24s)
S05 GATE: PASS (9/9 groups passed)
=== gate s06 ===
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
[PASS] manifest: theory section: 9 constants, 12 theory files and 12 feature files hashed, vocabulary and limits; harness part and the S4 freeze verify unchanged; stored with a run; tampering reported (1s)
[PASS] walkthrough: DF-A 6.64 bits opens h2; two predictions at 1.00 bit: left_has_dups enters G, INTERSECT ALL fails with another identity and opens h3; surprises 6.64, 1.00, 1.00, 0.07, 4.32, 0.01; 6 records, surprise recomputed from the ledger (19s)
S06 GATE: PASS (12/12 groups passed)
=== summary ===
s01: PASS
s02: PASS
s03: PASS
s04: PASS
s05: PASS
s06: PASS
GATES: PASS (6/6 passed)
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
- 日志 `.orch/logs/s06-theory.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 无

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s06-theory.jsonl`：4740 条事件（auto_compact_completed 1，auto_compact_failed 1，auto_compact_started 2，available_commands 54，end 1，orch.exit 1，orch.start 1，text 388，thought 3728，tool_call 94，tool_call_update 419，usage 50）；各轮合计 50 个模型回合，grok 上报花费 1.8090 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
thought: 用户要求继续此前的对话。
text: 工作包在上一轮已经落地。我先核对提交、工作区和报告是否还在，再给你结果。
tool_call run_terminal_command: {"command": "git status -sb; git log -1 --format=\"%H%n%s\"", "description": "Verify branch status and latest commit"}
tool_call read_file: {"target_file": "D:\\CoevoDB\\.worktrees\\s06-theory\\.orch\\report.md"}
tool_update [in_progress]: 
tool_update [completed]: {"type": "ReadFile", "FileContent": {"content": "1→# 报告 · s06-theory\n\n## 改了哪些文件\n- `framework/surprise/theory/residual.py`：新增。按单元计未解释失败，给出残余失败率 ρ_c。\n- `framework/surprise/theor…
tool_update [in_progress]: ## grok/s06-theory
tool_update [completed]: exit: 0 ## grok/s06-theory 9e4366f75073aad6fed0ed5ced99bd1a9f780d08 s06-theory: add residual, validity, prediction, triage, Theory, and the manifest section
thought: 工作包已完成。我将提供清晰的完成总结。
text: 工作包 s06-theory 已完成，提交在 `grok/s06-theory` 的 `9e4366f`，工作区干净。报告在 `.orch/report.md`。 理论核心 T = (H, R, Kᵛ) 已从 `surprise.theory` 导出：残余失败率、无效率、预测与惊讶、六类分诊、`Theory.observe`，以及 run manifest…
end: stopReason=end_turn turns=50 cost_usd=1.80900264
orch.exit: {"pkg": "s06-theory", "run": 1, "at": "2026-10-09T15:08:47+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s06-theory

## 改了哪些文件
- `framework/surprise/theory/residual.py`：新增。按单元计未解释失败，给出残余失败率 ρ_c。
- `framework/surprise/theory/validity.py`：新增。实验类，以及按实验类和 oracle 计无效率 Kᵛ。
- `framework/surprise/theory/predict.py`：新增。预测、以有效为条件的惊讶、六类分诊。
- `framework/surprise/theory/theory.py`：新增。`Theory` 与 `Observation`：预测、学习、状态往返、版本。
- `framework/surprise/theory/manifest.py`：新增。把理论常数和代码哈希写进 run manifest，并核对。
- `framework/surprise/theory/__main__.py`：新增。`python -m surprise.theory {constants|manifest}`。
- `framework/surprise/theory/__init__.py`：修改。导出本包的名字。
- `framework/tests/test_surprise_s06_residual.py`：新增。R、Kᵛ 与实验类。
- `framework/tests/test_surprise_s06_predict.py`：新增。三个区、惊讶的五个量级、分诊。
- `framework/tests/test_surprise_s06_theory.py`：新增。`observe` 的分支、新家族、编号、`put`、往返、版本。
- `framework/tests/test_surprise_s06_manifest.py`：新增。manifest 的三个函数和命令行。

## 跑了哪些命令

### `cd framework; python -m pytest -q tests/test_surprise_s06_residual.py tests/test_surprise_s06_predict.py tests/test_surprise_s06_theory.py tests/test_surprise_s06_manifest.py`
退出码：0

```
........................................................................ [ 62%]
............................................                             [100%]
116 passed in 0.88s
```

### `cd framework; python -m pytest -q testing tests`
退出码：0

```
........................ss..................................s........... [ 13%]
........................................................................ [ 27%]
........................................................................ [ 41%]
........................................................................ [ 55%]
........................................................................ [ 69%]
........................................................................ [ 83%]
........................................................................ [ 97%]
.............                                                            [100%]
514 passed, 3 skipped in 40.87s
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
[PASS] manifest: theory section: 9 constants, 12 theory files and 12 feature files hashed, vocabulary and limits; harness part and the S4 freeze verify unchanged; stored with a run; tampering reported (1s)
[PASS] walkthrough: DF-A 6.64 bits opens h2; two predictions at 1.00 bit: left_has_dups enters G, INTERSECT ALL fails with another identity and opens h3; surprises 6.64, 1.00, 1.00, 0.07, 4.32, 0.01; 6 records, surprise recomputed from the ledger (19s)
S06 GATE: PASS (12/12 groups passed)
```

### `cd framework; python -m surprise.gates.all`
退出码：0

```
[PASS] vspace: 5 sequences (25 steps) reach the expected S and G; positions incl. undetermined and out of scope; G capped at 64; invariants hold over 480 random steps (0s)
[PASS] hypothesis: contract keeps S2-era objects and round-trips the new fields; 4 families started from profiles, one with earlier passes replayed; 2 attribution requests accepted by the harness parser (0s)
[PASS] identity: 17 hypothesis / label pairs judged: harness test first, then fix set, then the three profile fields (0s)
[PASS] residual: prior 0.01, counts and rate per unit, round trip; the rate never reaches 0 or 1 (0s)
[PASS] validity: prior 0.1; counts, reasons and rate per (class, oracle); round trip (0s)
[PASS] predict: surprise 6.64 / 4.32 / 1.00 / 0.07 / 0.01 bits; 6 zone predictions with precedence confirmed > pending > residual; per-unit rho and per-class K^v (0s)
[PASS] triage: 14 (label, bits) pairs incl. both thresholds; the six rows of the framework document; 8 bad calls rejected (0s)
[PASS] theory: 9 scripted experiments: 6.64 -> family, 1.00 x 2 -> G moves and a second family, 0.07 duplicate, 4.32 unexpected pass, 0.01 no information, invalid, unexplained failure; replay, reload and determinism; 4 drifted-residual cases; 6 bad calls rejected (0s)
[PASS] manifest: theory section: 9 constants, 12 theory files and 12 feature files hashed, vocabulary and limits; harness part and the S4 freeze verify unchanged; stored with a run; tampering reported (1s)
[PASS] walkthrough: DF-A 6.64 bits opens h2; two predictions at 1.00 bit: left_has_dups enters G, INTERSECT ALL fails with another identity and opens h3; surprises 6.64, 1.00, 1.00, 0.07, 4.32, 0.01; 6 records, surprise recomputed from the ledger (18s)
S06 GATE: PASS (12/12 groups passed)
=== summary ===
s01: PASS
s02: PASS
s03: PASS
s04: PASS
s05: PASS
s06: PASS
GATES: PASS (6/6 passed)
```

## 与说明的偏差
无。

## 未决问题
无。
````

## 8. 结论（编排者填）

**合并。**（2026-10-09，首轮，没有返工）

依据：

- 独立复跑在 9e4366f 上：pytest 514 passed / 3 skipped（基线 398，新增 116 个测试，skip 未增加）；`gates.all` 退出码 0，S01–S06 全过，S06 十二组全过，红旗为零。`walkthrough` 组在真实引擎上给出 6.64、1.00、1.00、0.07、4.32、0.01 比特，六条账本记录的惊讶都能由 `p_t` 与标签重算出来；S04 的 freeze 组与 `manifest` 组里对 `s04_frozen.json` 的校验都通过，冻结的 harness 没有动。
- 完整 diff 读过（实现七个文件 906 行、测试四个文件 1011 行）。改动只在允许路径内；上一个包交付的文件只有 `theory/__init__.py` 加了导出；没有新增 skip / xfail、没有宽泛的异常捕获、没有改测试配置。执行者的 13 条 shell 命令全部看过：读 git 状态、跑测试与门槛、提交；文件工具访问的 56 个路径没有一个在 worktree 之外。
- 与编排者的参考模型做差分核对（`.orch/scratch/s6_review_theory.py`）：600 次随机运行，三个作用域，标签随机带归属测试与画像，中途随机放入放宽过的假设、随机重载状态；每一步比较预测、观察结果、完整状态与版本号。六种分诊结果与六种假设效果都大量出现，共开出 3114 个家族，同时最多 14 个。R、Kᵛ、`surprise_bits`、`triage`（含两个阈值两侧的取值）另行比较。共 63763 项，出入为 0。
- 对着定义写的不变量（实现一侧，250 次随机运行、14347 对"记住的通过 × 假设"）：没有一条记住的通过还落在某个假设的待定区；落在确认区的，该假设都留有矛盾记录；一条通过观察完之后立刻再预测，不会仍是待定区；开出新家族的那条失败立刻落在它自己的确认区。违反数为 0。
- 边角探测：`predict` 不改状态；11 种被拒绝的调用（参数类型不对、给了别的 oracle 或别的引擎的预测、`put` 的非法假设）之后状态逐字节不变；手工放了一个 `h1` 之后自动编号跳过它、不回收；`from_dict` 拒绝 `next_id` 非正整数、`hypotheses` 不是列表、缺键；`theory_manifest()` 与参考模型相等；`verify_theory_manifest` 对六处篡改各报一行；命令行两个子命令退出码 0、未知子命令退出码 2。1500 条随机观察（开出 151 个假设）17.7 秒。
- 理论层没有连接引擎、执行 SQL、读写文件（`manifest.py` 经 `harness_hash` 读源码算哈希除外）、读时钟或环境变量的代码；常数只在 `constants.py` 里写了一次，别处的 0.95、0.5 只出现在文档字符串里。

实现上由执行者定、编排者收下的选择：

1. `Prediction` 在构造时校验自己的字段（区名、非空字符串、两个概率严格在 0 与 1 之间）。Kᵛ 与 ρ 的公式保证它们落在这个区间里，所以不会在 `predict` 里触发。
2. `Theory.from_dict` 还检查了 `passes` 的范围键写法与其中 φ 的引擎。

没有为之返工、记入 HANDOFF 未决问题的两处：

1. `verify_theory_manifest` 对常数的措辞与对文件的相反：manifest 里有、现在没有的常数报成 `constant added`，现在有、manifest 里没有的报成 `constant missing`；文件一侧（与冻结的 `verify_manifest` 一致）是"现在有而记录里没有"为 `added`。两种情况都报出来了、都带着名字，只是方向读起来别扭。
2. `Theory.from_dict` 遇到重复的假设编号时取后一个，遇到不是规范形式的假设时静默规范化，也不核对记住的通过里 φ 的词表摘要。`to_dict()` 自己产出的状态不会有这些情况；S7 做存储时把这几项校验补上。
