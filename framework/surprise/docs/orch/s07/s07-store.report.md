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
