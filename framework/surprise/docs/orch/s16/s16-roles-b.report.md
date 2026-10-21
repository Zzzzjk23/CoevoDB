# 报告 · s16-roles-b

Commit: `890fe4df5db47f248a40a42542568a8ee4eede5e` on `grok/s16-roles-b`.

## 改了哪些文件

- `framework/surprise/roles/sources_map.py`：新增可选 PostgreSQL 16.15 检出常量、22 个干预的源码文件映射及 11 条特征规则。
- `framework/surprise/roles/source.py`：新增 `open_extra_sources` 和 `readers_for`，缺失或 commit 不符时输出一行 ASCII 提示；原有 `source_roots`、`open_sources` 未改。
- `framework/surprise/roles/runtime.py`：按目标引擎调用 `readers_for(engines)`。
- `framework/surprise/roles/prior.py`：PostgreSQL 证据只读取固定检出的 `doc/src/sgml/release-16.sgml`，不扫描相邻文档。
- `framework/surprise/roles/conjecturer.py`：新增 PostgreSQL fix set 与特征选片段分支，保留 DuckDB、DataFusion 分支原文。
- `framework/surprise/roles/implementer.py`：新增 PostgreSQL 16 方言和事务、search_path、角色及非超级用户限制提示。
- `framework/tests/test_surprise_s16_roles.py`：新增 31 个离线测试，覆盖真实源码检出、commit 校验、证据来源、映射与预算，并写死改动前计算的 10 组旧引擎输出 SHA-256。

## 跑了哪些命令

### `pytest -q tests/test_surprise_s16_roles.py 2>&1 | Tee-Object -FilePath ../.orch/test-s16-roles.log; exit $LASTEXITCODE`

Exit code: 2

```text

=================================== ERRORS ====================================
______________ ERROR collecting tests/test_surprise_s16_roles.py ______________
ImportError while importing test module 'D:\CoevoDB\.claude\worktrees\s16\.worktrees\s16-roles-b\framework\tests\test_surprise_s16_roles.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
D:\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\test_surprise_s16_roles.py:12: in <module>
    from diagnosis.bisect import POSTGRES_GUC_INTERVENTIONS
E   ModuleNotFoundError: No module named 'diagnosis'
=========================== short test summary info ===========================
ERROR tests/test_surprise_s16_roles.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.20s
```

### `python -m pytest -q tests/test_surprise_s16_roles.py 2>&1 | Tee-Object -FilePath ../.orch/test-s16-roles-final.log; exit $LASTEXITCODE`

Exit code: 0

```text
...............................                                          [100%]
31 passed in 1.28s
```

### `pytest -q testing tests 2>&1 | Tee-Object -FilePath ../.orch/test-all.log; exit $LASTEXITCODE`

Exit code: 0

```text
........................ss..................................s........... [  5%]
........................................................................ [ 11%]
........................................................................ [ 17%]
........................................................................ [ 23%]
........................................................................ [ 29%]
........................................................................ [ 34%]
........................................................................ [ 40%]
........................................................................ [ 46%]
........................................................................ [ 52%]
........................................................................ [ 58%]
........................................................................ [ 63%]
........................................................................ [ 69%]
........................................................................ [ 75%]
........................................................................ [ 81%]
........................................................................ [ 87%]
........................................................................ [ 92%]
........................................................................ [ 98%]
...............                                                          [100%]
1236 passed, 3 skipped in 532.07s (0:08:52)
```

### `python -m surprise.gates.s16 --only roles 2>&1 | Tee-Object -FilePath ../.orch/gate-s16-roles.log; exit $LASTEXITCODE`

Exit code: 0

```text
python : optional source checkout unavailable for postgres: missing directory or commit mismatch
所在位置 行:2 字符: 1
+ python -m surprise.gates.s16 --only roles 2>&1 | Tee-Object -FilePath ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (optional source...commit mismatch:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
[PASS] roles: optional postgres checkout 7d3e000c5961 (roles constants unchanged); 8 release-note evidence lines; memoize -> ['src/backend/executor/nodeMemoize.c']; dialect hint present (1s)
S16 GATE [only: roles]: PASS (1/1 groups passed)
```

### `python -m surprise.gates.s09 2>&1 | Tee-Object -FilePath ../.orch/gate-s09.log; exit $LASTEXITCODE`

Exit code: 0

```text
[PASS] isolation: roles load no model client until a transport is built; loop, Hunter, Diagnoser, harness never import them; transport reuses BaseAgent and the old ledger (2s)
[PASS] constants: 19 constants as planned; tiers {'fast': 'deepseek-flash', 'strong': 'deepseek-v4-pro'} (0s)
[PASS] cache: key = prompt hash + model + seed; hits make no call; replay identical; forged entry refused; ledger and per-role totals (0s)
[PASS] reject: 9 replies parsed as planned; refusals replay as refusals; the implementer refuses before phi (0s)
[PASS] cap: cap 2 blocks the third call; cache served past the cap; cap 0 calls nothing; env ceiling; errors count, not cached (0s)
[PASS] source: confined, exact, read-only; checkouts at datafusion 45d943dfb869, duckdb d8cdaa33fda8 (0s)
[PASS] implementer: accepted, retried with feedback, unmet, bad case, replayed, blocked (0s)
[PASS] conjecturer: selection picks datafusion/expr/src/logical_plan/builder.rs for DF-A and src/optimizer/filter_pushdown.cpp for ('filter_pushdown',); registered with a revise whose bets are its predictions; settled by experiments; refusals, drops, not covering, blocked (12s)
[PASS] wiring: off: 40 rows identical to S8, no role loaded; on: 7 scripted calls, 0 implementer experiments meeting their specs; cap 0 completes (68s)
[PASS] implementer_report: phi-check pass rate 0.97 at the first try, 1.00 after 2 tries (30/30); boundary 10/10, core 10/10, whole 10/10 (1s)
[PASS] dfa: mechanism: LogicalPlanBuilder::intersect_or_except implements EXCEPT ALL as a LeftAnti hash join with NullEqualsNull, so it removes every left row having any match instead; trigger ['ast:set_op:except_all', 'ast:stmt:select', 'data:setop:left_has_dups']; 4 predictions (fail on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_dups+data:table:dup_rows+data:type:integer without data:setop:left_has_null+data:setop:right_has_null+data:table:has_null; pass on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_null+data:setop:right_has_null+data:table:has_null+data:type:integer without data:setop:left_has_dups+data:table:dup_rows; fail on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_dups+data:setop:left_has_null+data:setop:right_has_null+data:table:dup_rows+data:table:has_null+data:type:integer; pass on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_dups+data:table:dup_rows+data:table:empty+data:type:integer without data:setop:left_has_null+data:setop:right_has_null+data:table:has_null); proposed as e1, accepted (0s)
[PASS] replay: 21 experiments and 25 calls replayed from the cache, identical; lanes {'bootstrap': 1, 'generalize': 5, 'bet': 5, 'implement': 7, 'refine': 3}; book {'conjectures': 3, 'rejected': 0, 'predictions': 12, 'open': 4, 'kept': 6, 'broken': 2} (64s)
S09 GATE: PASS (12/12 groups passed)
```

### `python -m surprise.gates.s10 2>&1 | Tee-Object -FilePath ../.orch/gate-s10.log; exit $LASTEXITCODE`

Exit code: 0

```text
[PASS] isolation: 4 role modules load no model client; loop, Hunter, Diagnoser and harness never import the roles (1s)
[PASS] constants: 35 S10 constants as planned, S9 constants unchanged, library constants ['LIBRARY_ENV', 'LIBRARY_KINDS', 'LIBRARY_MIN_REFERENCES', 'LIBRARY_RULE_PREFIX', 'LIBRARY_SCHEMA'] (0s)
[PASS] frozen: harness changes since s09-done-r2: ['equivalent_query.py', 'rewrites.py']; re-frozen and verified; 12 frozen-rule outputs unchanged with and without a library (0s)
[PASS] library: 4 usable and 10 refused templates; 8 malformed libraries refused; judgements {'llm:wrap_sub': 'pass', 'llm:is_true': 'pass', 'llm:first_row': 'untrusted_rewrite/reference_disagrees', 'llm:octet': 'untrusted_rewrite/rewrite_error'}; frozen rule unchanged; no library, no trust (6s)
[PASS] frame: prior moves U 0.498 -> 1.000; extra rules offered; prepare once per round (1 rounds); vocabulary run extracts ast:set_op:except_all_two_tables (26s)
[PASS] switches: all on: calls {'implementer': 4, 'conjecturer': 1, 'prior': 3, 'translator': 1, 'vocab_inventor': 1, 'oracle_inventor': 1}; each role off: no call, no ledger line, plugin module not loaded (191s)
[PASS] prior: 20 units priced in 2 calls; evidence from the checkouts (40 lines); bad prior weight -> 0.0 after 20; useful prior weight 0.490 (1s)
[PASS] translator: DF-A family -> DuckDB translated once; settled {'tr-match': ('kept', 'match'), 'tr-mismatch': ('kept', 'mismatch'), 'tr-broken': ('broken', None), 'tr-void': ('void', None)}; bad switch refused; unmet spec retried (10s)
[PASS] vocab_inventor: accepted ast:set_op:except_all_two_tables on held-out records; refused {'empty': 'pattern', 'long': 'pattern', 'catastrophic': 'scan', 'everything': 'scan', 'no_exclusion': 'train', 'train_only': 'holdout'} and a data-layer id; prompt hides the held-out records (21s)
[PASS] oracle_inventor: accepted ['llm:wrap_sub'] on 5 instances; refused disagree, template, duplicate; 3 calls in 401 experiments; judged by the harness: pass (2s)
[PASS] translator_real: F2 (duckdb) -> datafusion: status ok, expect pass, switches []; label pass; settled kept identity None (5s)
[PASS] m3: 32 experiments and 43 calls replayed from the cache, identical; calls {'conjecturer': 2, 'oracle_inventor': 1, 'implementer': 36, 'prior': 4}; DF-B (shape|datafusion|wrong_result|-|extra_only) reached at experiment 3 via bet (bet from c1 on h1); lanes {'bootstrap': 1, 'generalize': 2, 'bet': 7, 'refine': 4, 'implement': 18} (109s)
S10 GATE: PASS (12/12 groups passed)
```

### `git diff --check 2>&1 | Tee-Object -FilePath .orch/diff-check.log; exit $LASTEXITCODE`

Exit code: 0

```text

```

### `git commit -m "feat(roles): add optional pinned PostgreSQL source evidence" 2>&1 | Tee-Object -FilePath .orch/commit.log; exit $LASTEXITCODE`

Exit code: 0

```text
[grok/s16-roles-b 890fe4d] feat(roles): add optional pinned PostgreSQL source evidence
 7 files changed, 337 insertions(+), 13 deletions(-)
 create mode 100644 framework/tests/test_surprise_s16_roles.py
```

### Offline runtime manifest check

```powershell
@'
import tempfile
from pathlib import Path
from surprise.roles.constants import SOURCE_COMMITS, SOURCE_DIRS
from surprise.roles.runtime import build_roles
from surprise.roles.sources_map import EXTRA_SOURCE_COMMITS, EXTRA_SOURCE_DIRS
legacy = {engine: {'dir': directory, 'commit': SOURCE_COMMITS[engine]} for engine, directory in SOURCE_DIRS.items()}
with tempfile.TemporaryDirectory(dir='../.orch', prefix='runtime-check-') as tmp:
    for engine in ('duckdb', 'datafusion', 'postgres'):
        root = Path(tmp) / engine
        roles = build_roles({'roles': ['implementer'], 'network': False, 'cache': root / 'cache', 'max_calls': 0}, run_dir=root, extract=None, registry=None, engines=(engine,), seed=0)
        try:
            expected = dict(legacy)
            if engine == 'postgres':
                expected['postgres'] = {'dir': EXTRA_SOURCE_DIRS['postgres'], 'commit': EXTRA_SOURCE_COMMITS['postgres']}
            assert roles.manifest()['sources'] == expected
            assert roles._gateway.totals()['network'] == 0
            print(engine + ' runtime source manifest and zero network calls: PASS')
        finally:
            roles.close()
'@ | python - 2>&1 | Tee-Object -FilePath ../.orch/runtime-check.log; exit $LASTEXITCODE
```

Exit code: 0

```text
duckdb runtime source manifest and zero network calls: PASS
datafusion runtime source manifest and zero network calls: PASS
postgres runtime source manifest and zero network calls: PASS
```

### Initial runtime diagnostic script

```powershell
@'
import tempfile
from pathlib import Path
from surprise.roles.constants import SOURCE_COMMITS, SOURCE_DIRS
from surprise.roles.runtime import build_roles
from surprise.roles.sources_map import EXTRA_SOURCE_COMMITS, EXTRA_SOURCE_DIRS
legacy = {engine: {'dir': directory, 'commit': SOURCE_COMMITS[engine]} for engine, directory in SOURCE_DIRS.items()}
with tempfile.TemporaryDirectory(dir='../.orch', prefix='runtime-check-') as tmp:
    for engine in ('duckdb', 'datafusion', 'postgres'):
        root = Path(tmp) / engine
        roles = build_roles({'roles': ['implementer'], 'network': False, 'cache': root / 'cache', 'max_calls': 0}, run_dir=root, extract=None, registry=None, engines=(engine,), seed=0)
        try:
            expected = dict(legacy)
            if engine == 'postgres':
                expected['postgres'] = {'dir': EXTRA_SOURCE_DIRS['postgres'], 'commit': EXTRA_SOURCE_COMMITS['postgres']}
            assert roles.manifest()['sources'] == expected
            assert roles._gateway.totals()['calls'] == 0
            print(engine + ' runtime source manifest and zero calls: PASS')
        finally:
            roles.close()
'@ | python -
```

Exit code: 1

```text
Traceback (most recent call last):
  File "<stdin>", line 16, in <module>
KeyError: 'calls'
```

### Static invariance checks

Compared source_roots/open_sources ASTs and the original DuckDB/DataFusion selection block with HEAD before commit. Exit code: 0.

```text
source_roots/open_sources unchanged: PASS
DuckDB/DataFusion selection branches unchanged: PASS
```

### `git status --short`

Exit code: 0

```text
```

Validation notes: the initial standalone pytest invocation omitted the project import path normally added by testing/conftest.py; python -m pytest passed all 31 new tests. The initial extra smoke script used a nonexistent gateway totals field; correcting the diagnostic to network passed. Neither issue required production or baseline-test changes. S16 stderr is the expected optional-checkout warning from its empty-root check.

## 与说明的偏差

无。未修改已有测试、冻结常量、harness 或文档；未连接服务器，未调用真实 LLM，未打 tag、合并或推送。

## 未决问题

无。
