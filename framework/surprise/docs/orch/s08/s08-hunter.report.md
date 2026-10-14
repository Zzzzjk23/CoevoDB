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
