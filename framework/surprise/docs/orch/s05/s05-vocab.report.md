# 报告 · s05-vocab

## 改了哪些文件
- `framework/surprise/features/vocabulary.py`：新增 FeatureDef 与基础词表 166 项（id/kind/parent 照抄契约，描述自写）
- `framework/surprise/features/registry.py`：新增 Registry 与 default_registry（族成员、登记/验收、摘要、存取）
- `framework/surprise/features/phi.py`：新增 Phi 与 make_phi
- `framework/surprise/features/spec.py`：新增 SpecCheck 与 check_spec
- `framework/surprise/features/units.py`：新增 unit_parts 与 unit_of
- `framework/surprise/features/__init__.py`：导出 FeatureDef、Registry、default_registry、Phi、make_phi、check_spec、SpecCheck、unit_of、unit_parts
- `framework/surprise/features/__main__.py`：新增 `python -m surprise.features vocab`
- `framework/tests/test_surprise_s05_vocab.py`：新增词表、注册表、φ 的单元测试
- `framework/tests/test_surprise_s05_phi.py`：新增规格核对与单元投影测试

## 跑了哪些命令

### `python -m pytest -q testing tests`
退出码：0

```
........................ss..................................s........... [ 24%]
........................................................................ [ 48%]
........................................................................ [ 72%]
........................................................................ [ 97%]
........                                                                 [100%]
293 passed, 3 skipped in 34.20s
```

### `python -m surprise.gates.s01`
退出码：0

```
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 293 passed (baseline 64): 293 passed, 3 skipped in 33.47s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
```

### `python -m surprise.gates.s02`
退出码：0

```
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 51 files hashed (50fa40cf2d19); verify catches 3 kinds of change
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: PASS (5/5 groups passed)
```

### `python -m surprise.gates.s03`
退出码：0

```
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
[PASS] local: ART exercised, injected mismatch caught; 3 proved rules x 2 engines incl NULL; untrusted pairs rejected
[PASS] cross: PG16 + DuckDB witness DF-A/DF-B; insufficient quorum, ties, multiple outliers and engine aliases rejected
[PASS] version: F2 old/new measured bags and regression direction; both old venvs work; directionless mismatch invalid
[PASS] matrix: 7 oracles x 2 engines, 14 ledger records, no hidden harness failures, manifest verified
S03 GATE: PASS (5/5 groups passed)
```

### `python -m surprise.gates.s04`
退出码：0（第一次 isolation 组因进程崩溃只复现 4/5 次记为 unstable_rerun 失败；立刻重跑通过）

```
[PASS] contracts: 17 invalid sources, 7 CVE constants in the manifest; raw entry points untouched; 5 bad requests rejected before execution (1s)
[PASS] isolation: ok / error / timeout x2 / crash x2 told apart; 7 distinct processes for one candidate; process death, hang and dying reference contained (19s)
[PASS] tier1: 6 stable families fail after 5 fresh reruns; F8 unstable; F5 reproduced 0/5; 6 scripted rerun schedules (17s)
[PASS] premise: ASOF ties, writing statements and incomparable cross-engine values are invalid; their tie-free, crashing and comparable counterparts stay fail (12s)
[PASS] environment: 51 files hashed, 17 imported old modules all covered; old engines, PostgreSQL 16.15 and 5 packages recorded (0s)
[PASS] tier2: fix-set attribution: F1, F6, F6 via TLP consistent, F2 escalated; profile attribution: DF-A consistent, DF-B escalated; 5 malformed hypotheses rejected (20s)
[PASS] tier3: 9 confirmed cases profiled: fix sets as measured and as in recall_repros.json, version ladder, minimised subsequence; noise removed; lost candidate downgraded (34s)
[PASS] m1: 50 final labels in the ledger (14 fail, 20 invalid, 16 pass); known recall gaps: DF-E, DF-G, DF-H, DF-J, F10, F5 (59s)
[PASS] freeze: 51 files (31 in the harness), hash 50fa40cf2d19, 8 constants match (0s)
S04 GATE: PASS (9/9 groups passed)
```

### `python -m surprise.gates.s05 --only vocab spec units`
退出码：0

```
[PASS] vocab: 166 core entries (131 leaves) with hierarchy; open families; digest 2544688571fc stable across processes; invented feature registered, 8 bad ones rejected, saved and loaded; phi container (0s)
[PASS] spec: 12 hand-written phi / spec pairs judged as expected; 3 malformed specs rejected (0s)
[PASS] units: 23 hand-written feature sets project onto the expected units (0s)
S05 GATE [only: vocab, spec, units]: PASS (3/3 groups passed)
```

## 与说明的偏差
无。

## 未决问题
s04 isolation 组第一次跑时，杀死子进程的候选 5 次重跑只复现 4 次，被标成 invalid/unstable_rerun；本包未改 harness。立刻重跑 s04 通过。若编排者看到偶发 isolation 失败，按环境抖动处理即可。

# 第 1 轮返工

按 `.orch/review-1.md` 改了三处：`Phi.from_dict` 做结构校验；`Registry.load` 用与 `register` 相同的规则校验发明特征（验收状态可以已经有了）；S4 测试夹具用 `die()` 立即结束进程。

## 改了哪些文件
- `framework/surprise/features/phi.py`：修改 `Phi.from_dict`，校验键、schema、engine、vocab、features 升序、layers
- `framework/surprise/features/registry.py`：修改 `load`，抽出 `_checked_invented`；验收状态允许已接受
- `framework/tests/test_surprise_s05_vocab.py`：补 `from_dict` / `load` 的拒绝与往返测试
- `framework/tests/test_surprise_s04_runners.py`：新增 `die()`，三个退出夹具改用它（本轮额外放行）

## 跑了哪些命令

### `python -m pytest -q testing tests`
退出码：0

```
........................ss..................................s........... [ 24%]
........................................................................ [ 48%]
........................................................................ [ 72%]
........................................................................ [ 96%]
............                                                             [100%]
297 passed, 3 skipped in 33.74s
```

### `python -m surprise.gates.s01`
退出码：0

```
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 297 passed (baseline 64): 297 passed, 3 skipped in 33.61s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
```

### `python -m surprise.gates.s02`
退出码：0

```
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 51 files hashed (50fa40cf2d19); verify catches 3 kinds of change
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: PASS (5/5 groups passed)
```

### `python -m surprise.gates.s03`
退出码：0

```
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
[PASS] local: ART exercised, injected mismatch caught; 3 proved rules x 2 engines incl NULL; untrusted pairs rejected
[PASS] cross: PG16 + DuckDB witness DF-A/DF-B; insufficient quorum, ties, multiple outliers and engine aliases rejected
[PASS] version: F2 old/new measured bags and regression direction; both old venvs work; directionless mismatch invalid
[PASS] matrix: 7 oracles x 2 engines, 14 ledger records, no hidden harness failures, manifest verified
S03 GATE: PASS (5/5 groups passed)
```

### `python -m surprise.gates.s04`
退出码：0

```
[PASS] contracts: 17 invalid sources, 7 CVE constants in the manifest; raw entry points untouched; 5 bad requests rejected before execution (1s)
[PASS] isolation: ok / error / timeout x2 / crash x2 told apart; 7 distinct processes for one candidate; process death, hang and dying reference contained (19s)
[PASS] tier1: 6 stable families fail after 5 fresh reruns; F8 unstable; F5 reproduced 0/5; 6 scripted rerun schedules (17s)
[PASS] premise: ASOF ties, writing statements and incomparable cross-engine values are invalid; their tie-free, crashing and comparable counterparts stay fail (13s)
[PASS] environment: 51 files hashed, 17 imported old modules all covered; old engines, PostgreSQL 16.15 and 5 packages recorded (0s)
[PASS] tier2: fix-set attribution: F1, F6, F6 via TLP consistent, F2 escalated; profile attribution: DF-A consistent, DF-B escalated; 5 malformed hypotheses rejected (20s)
[PASS] tier3: 9 confirmed cases profiled: fix sets as measured and as in recall_repros.json, version ladder, minimised subsequence; noise removed; lost candidate downgraded (34s)
[PASS] m1: 50 final labels in the ledger (14 fail, 20 invalid, 16 pass); known recall gaps: DF-E, DF-G, DF-H, DF-J, F10, F5 (58s)
[PASS] freeze: 51 files (31 in the harness), hash 50fa40cf2d19, 8 constants match (0s)
S04 GATE: PASS (9/9 groups passed)
```

### `python -m surprise.gates.s05 --only vocab spec units`
退出码：0

```
[PASS] vocab: 166 core entries (131 leaves) with hierarchy; open families; digest 2544688571fc stable across processes; invented feature registered, 8 bad ones rejected, saved and loaded; phi container (0s)
[PASS] spec: 12 hand-written phi / spec pairs judged as expected; 3 malformed specs rejected (0s)
[PASS] units: 23 hand-written feature sets project onto the expected units (0s)
S05 GATE [only: vocab, spec, units]: PASS (3/3 groups passed)
```

## 与说明的偏差
无。本轮按审查意见额外改了 `framework/tests/test_surprise_s04_runners.py`。

## 未决问题
无。第一轮记录的 s04 isolation 抖动已按审查意见改夹具；本轮 s04 一次通过。
