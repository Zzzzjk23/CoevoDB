# 报告 · s04-tier23

## 改了哪些文件
- `framework/surprise/harness/constants.py`：修改，增加最小化、二分和两档墙钟常数
- `framework/surprise/harness/manifest.py`：修改，哈希 `agents/bug_fixer.py`，包名单加入 `sqlglot`
- `framework/surprise/harness/cve/hypothesis.py`：新增，校验手写假设
- `framework/surprise/harness/cve/criterion.py`：新增，两种形式的复现判据和一次归属测试
- `framework/surprise/harness/cve/tier3.py`：新增，最小化、删无用建表语句、画像
- `framework/surprise/harness/cve/certify.py`：修改，第 1 档确认失败后跑第 2、3 档
- `framework/surprise/harness/cve/worker.py`：修改，增加 `interventions`、`attribute`、`diagnose` 三个 op
- `framework/surprise/harness/cve/__init__.py`：修改，文档说明第 2、3 档已实现
- `framework/surprise/harness/evaluate.py`：修改，把 `hypothesis` 和 `diagnose` 传给 `certify`；非法假设在写账本前抛 `ValueError`
- `framework/tests/test_surprise_s04_tier23.py`：新增，假 runner 覆盖复现、归属、最小化、画像和跳过原因
- `framework/tests/test_surprise_s04_pipeline.py`：修改，去掉第 2、3 档的 `NotImplementedError` 桩断言

提交：`558bd7e`，分支 `grok/s04-tier23`。`git status` 干净。

## 跑了哪些命令

命令：`python -m pytest -q testing tests`（在 `framework/`）
退出码：1

```
            'CVE_RERUN_EXTENDED',
            'CVE_WALL_TIMEOUT_S',
            'QUERY_TIMEOUT_S',
        }
D:\CoevoDB\.worktrees\s04-tier23\framework\tests\test_surprise_contracts.py:160: AssertionError: assert {'CVE_ATTRIBU...XTENDED', ...} == {'CVE_RERUN_A...RY_TIMEOUT_S'}
=========================== short test summary info ===========================
FAILED tests/test_surprise_contracts.py::test_constants_collect_public_uppercase_names - AssertionError: assert {'CVE_ATTRIBU...XTENDED', ...} == {'CVE_RERUN_A...RY_TIMEOUT_S'}
  
  Extra items in the left set:
  'CVE_BISECT_MAX_EXECUTIONS'
  'CVE_PROFILE_WALL_TIMEOUT_S'
  'CVE_ATTRIBUTION_WALL_TIMEOUT_S'
  'CVE_MINIMIZE_MAX_EXECUTIONS'
  
  Full diff:
    {
  +     'CVE_ATTRIBUTION_WALL_TIMEOUT_S',
  +     'CVE_BISECT_MAX_EXECUTIONS',
  +     'CVE_MINIMIZE_MAX_EXECUTIONS',
  +     'CVE_PROFILE_WALL_TIMEOUT_S',
        'CVE_RERUN_ATTEMPTS',
        'CVE_RERUN_EXTENDED',
        'CVE_WALL_TIMEOUT_S',
        'QUERY_TIMEOUT_S',
    }
1 failed, 272 passed, 3 skipped in 33.74s
```

命令：`python -m surprise.gates.s01`
退出码：1

```
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[FAIL] pytest: pytest exit 1: Full diff: | { | +     'CVE_ATTRIBUTION_WALL_TIMEOUT_S', | +     'CVE_BISECT_MAX_EXECUTIONS', | +     'CVE_MINIMIZE_MAX_EXECUTIONS', | +     'CVE_PROFILE_WALL_TIMEOUT_S', | 'CVE_RERUN_ATTEMPTS', | 'CVE_RERUN_EXTENDED', | 'CVE_WALL_TIMEOUT_S', | 'QUERY_TIMEOUT_S', | } | 1 failed, 272 passed, 3 skipped in 33.26s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: FAIL (6/7 checks passed)
```

命令：`python -m surprise.gates.s02`
退出码：0

```
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 51 files hashed (2aae7bd29452); verify catches 3 kinds of change
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: PASS (5/5 groups passed)
```

命令：`python -m surprise.gates.s03`
退出码：0

```
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
[PASS] local: ART exercised, injected mismatch caught; 3 proved rules x 2 engines incl NULL; untrusted pairs rejected
[PASS] cross: PG16 + DuckDB witness DF-A/DF-B; insufficient quorum, ties, multiple outliers and engine aliases rejected
[PASS] version: F2 old/new measured bags and regression direction; both old venvs work; directionless mismatch invalid
[PASS] matrix: 7 oracles x 2 engines, 14 ledger records, no hidden harness failures, manifest verified
S03 GATE: PASS (5/5 groups passed)
```

命令：`python -m surprise.gates.s04 --only contracts isolation tier1 premise environment tier2 tier3 m1`
退出码：0

```
[PASS] contracts: 17 invalid sources, 7 CVE constants in the manifest; raw entry points untouched; 5 bad requests rejected before execution (1s)
[PASS] isolation: ok / error / timeout x2 / crash x2 told apart; 7 distinct processes for one candidate; process death, hang and dying reference contained (19s)
[PASS] tier1: 6 stable families fail after 5 fresh reruns; F8 unstable; F5 reproduced 0/5; 6 scripted rerun schedules (17s)
[PASS] premise: ASOF ties, writing statements and incomparable cross-engine values are invalid; their tie-free, crashing and comparable counterparts stay fail (13s)
[PASS] environment: 51 files hashed, 17 imported old modules all covered; old engines, PostgreSQL 16.15 and 5 packages recorded (0s)
[PASS] tier2: fix-set attribution: F1, F6, F6 via TLP consistent, F2 escalated; profile attribution: DF-A consistent, DF-B escalated; 5 malformed hypotheses rejected (21s)
[PASS] tier3: 9 confirmed cases profiled: fix sets as measured and as in recall_repros.json, version ladder, minimised subsequence; noise removed; lost candidate downgraded (34s)
[PASS] m1: 50 final labels in the ledger (14 fail, 20 invalid, 16 pass); known recall gaps: DF-E, DF-G, DF-H, DF-J, F10, F5 (59s)
S04 GATE [only: contracts, isolation, tier1, premise, environment, tier2, tier3, m1]: PASS (8/8 groups passed)
```

## 与说明的偏差
- `framework/tests/test_surprise_s04_pipeline.py` 里原来有三处断言：非法假设和 `diagnose=True` 会抛 `NotImplementedError`，并且不调用 runner。本包要求这两个参数生效，允许改动的路径包含 `framework/tests/test_surprise_s04_*.py`。非法假设改为在调用 runner 之前抛 `ValueError`；`diagnose=True` 对一个会 pass 的用例会执行判定，并在 `evaluate_final` 里写一条第 0 档的 pass 记录。其余断言没有放宽。
- DataFusion 的版本梯在旧解释器存在时按与 DuckDB 相同的口径计算。说明允许算，也允许记 `unavailable`。

## 未决问题
`framework/tests/test_surprise_contracts.py` 的 `test_constants_collect_public_uppercase_names`（约第 160 行）把 `as_dict()` 的键锁成四个旧名字。本包必须在 `constants.py` 增加 `CVE_` 常数，而 `as_dict()` 会自动收录大写名字。该测试不在允许改动的路径里，没有改它。因此 `pytest` 和 `python -m surprise.gates.s01` 都以这一处断言失败（272 passed，3 skipped，1 failed）。需要编排者把这四个名字补进该断言：`CVE_MINIMIZE_MAX_EXECUTIONS`、`CVE_BISECT_MAX_EXECUTIONS`、`CVE_ATTRIBUTION_WALL_TIMEOUT_S`、`CVE_PROFILE_WALL_TIMEOUT_S`。

# 第 1 轮返工

## 改了哪些文件
- `framework/tests/test_surprise_contracts.py`：修改，常数快照补上四个 `CVE_` 名字和取值断言
- `framework/surprise/harness/cve/certify.py`：修改，第 1 档降级且调用方要求了后续档时跳过原因记 `tier1_rejected`；默认工厂的干预名单按引擎缓存在调用方进程
- `framework/surprise/harness/evaluate.py`：修改，注明默认工厂的名单缓存，`certify` 的第二次校验不再另起子进程
- `framework/surprise/harness/cve/tier3.py`：修改，最小化结束后用原始判定复核，`fail` 且 `fail_kind` 相同才算复现
- `framework/tests/test_surprise_s04_tier23.py`：修改，降级跳过原因改为 `tier1_rejected`；新增数据删除后溢出不再复现、以及默认工厂干预名单只问一次

提交：`d081bc8`，分支 `grok/s04-tier23`。`git status` 干净。

## 跑了哪些命令

命令：`python -m pytest -q testing tests`（在 `framework/`）
退出码：0

```
........................ss..................................s........... [ 25%]
........................................................................ [ 51%]
........................................................................ [ 77%]
..............................................................           [100%]
275 passed, 3 skipped in 33.58s
```

命令：`python -m surprise.gates.s01`
退出码：0

```
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 275 passed (baseline 64): 275 passed, 3 skipped in 33.57s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
```

命令：`python -m surprise.gates.s02`
退出码：0

```
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 51 files hashed (50fa40cf2d19); verify catches 3 kinds of change
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: PASS (5/5 groups passed)
```

命令：`python -m surprise.gates.s03`
退出码：0

```
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
[PASS] local: ART exercised, injected mismatch caught; 3 proved rules x 2 engines incl NULL; untrusted pairs rejected
[PASS] cross: PG16 + DuckDB witness DF-A/DF-B; insufficient quorum, ties, multiple outliers and engine aliases rejected
[PASS] version: F2 old/new measured bags and regression direction; both old venvs work; directionless mismatch invalid
[PASS] matrix: 7 oracles x 2 engines, 14 ledger records, no hidden harness failures, manifest verified
S03 GATE: PASS (5/5 groups passed)
```

命令：`python -m surprise.gates.s04 --only contracts isolation tier1 premise environment tier2 tier3 m1`
退出码：0

```
[PASS] contracts: 17 invalid sources, 7 CVE constants in the manifest; raw entry points untouched; 5 bad requests rejected before execution (1s)
[PASS] isolation: ok / error / timeout x2 / crash x2 told apart; 7 distinct processes for one candidate; process death, hang and dying reference contained (19s)
[PASS] tier1: 6 stable families fail after 5 fresh reruns; F8 unstable; F5 reproduced 1/5; 6 scripted rerun schedules (17s)
[PASS] premise: ASOF ties, writing statements and incomparable cross-engine values are invalid; their tie-free, crashing and comparable counterparts stay fail (13s)
[PASS] environment: 51 files hashed, 17 imported old modules all covered; old engines, PostgreSQL 16.15 and 5 packages recorded (0s)
[PASS] tier2: fix-set attribution: F1, F6, F6 via TLP consistent, F2 escalated; profile attribution: DF-A consistent, DF-B escalated; 5 malformed hypotheses rejected (20s)
[PASS] tier3: 9 confirmed cases profiled: fix sets as measured and as in recall_repros.json, version ladder, minimised subsequence; noise removed; lost candidate downgraded (34s)
[PASS] m1: 50 final labels in the ledger (14 fail, 20 invalid, 16 pass); known recall gaps: DF-E, DF-G, DF-H, DF-J, F10, F5 (58s)
S04 GATE [only: contracts, isolation, tier1, premise, environment, tier2, tier3, m1]: PASS (8/8 groups passed)
```

## 与说明的偏差
无

## 未决问题
无

