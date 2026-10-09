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
