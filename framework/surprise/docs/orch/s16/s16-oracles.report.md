# 报告 · s16-oracles

提交：`34a7cc3`（`grok/s16-oracles`）。实现已提交，但工作包尚未满足全部验收条件；遇到基线测试与门槛预期问题后，按说明停止实现修改并报告。未改基线测试、门槛、旧代码或其他工作树，未连接实验服务器。

## 改了哪些文件

- `framework/surprise/harness/oracles/index_presence.py`：新增 PostgreSQL 原生索引分支，复用旧 oracle 的最多 12 个状态变体，记录比较与跳过列表，始终执行 teardown，并映射错误、超时和结果差异；DuckDB 分支逐字保留。
- `framework/surprise/harness/oracles/version_differential.py`：新增进程内旧 PG 查询函数 `_query_old_postgres`，使用 `COEVO_OLD_PG_DSN`，返回相同的 `_OldResult`，共享给版本梯；忽略 PG 的 `old_python`，保留原方向判定。现有 `_version_of` 已读取 runner.engine_version，无需修改。
- `framework/surprise/harness/cve/certify.py`：仅为 `_SINGLE_THREAD` 加入 PostgreSQL 的 `parallel`。
- `framework/surprise/harness/cve/tier3.py`：新增 PG 版本梯分支，调用共享的旧 PG 查询函数。
- `framework/surprise/harness/manifest.py`：仅在设置相应 DSN 环境变量时记录目标和旧 PG 版本，连接失败记录 None，不保存 DSN，未改 HASHED_PATHS。
- `framework/tests/test_surprise_s16_oracles.py`：新增 19 项测试，使用真实 16.15/15.19 临时实例，覆盖原生索引、错误结果注入、错误及跳过原因、旧版本差异、CVE 版本梯与 manifest。

## 跑了哪些命令

以下测试和门槛均从 `framework/` 执行，git 命令从 worktree 根执行。日志保存在本 worktree 的 `.orch/`，每条命令下方原样摘录日志末 20 行（不足 20 行则全部列出）。

### `pytest -q tests/test_surprise_s16_oracles.py`

Exit code: 2

```text

=================================== ERRORS ====================================
_____________ ERROR collecting tests/test_surprise_s16_oracles.py _____________
ImportError while importing test module 'D:\CoevoDB\.claude\worktrees\s16\.worktrees\s16-oracles\framework\tests\test_surprise_s16_oracles.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
D:\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\test_surprise_s16_oracles.py:8: in <module>
    from oracles.db_runner import QueryResult
E   ModuleNotFoundError: No module named 'oracles'
=========================== short test summary info ===========================
ERROR tests/test_surprise_s16_oracles.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.20s
```

### `python -m pytest -q tests/test_surprise_s16_oracles.py`

Exit code: 0

```text
...................                                                      [100%]
19 passed in 79.63s (0:01:19)
```

### `python -m pytest -q testing tests`

Exit code: 1

```text
            from targets.datafusion_runner import DataFusionRunner
    
            return DataFusionRunner
        if engine == "postgres":
            import os
    
            from surprise.harness.oracles.pg_target import PostgresTargetRunner, TARGET_DSN_ENV
    
            if not os.environ.get(TARGET_DSN_ENV):
>               raise ValueError(
                    f"postgres: set {TARGET_DSN_ENV} using surprise.experiments.pg_instance "
                    "before requesting a default runner"
                )
E               ValueError: postgres: set COEVO_TARGET_PG_DSN using surprise.experiments.pg_instance before requesting a default runner

surprise\harness\oracles\registry.py:97: ValueError
=========================== short test summary info ===========================
FAILED tests/test_surprise_s03_registry.py::test_implemented_is_the_seven_plan_ids
FAILED tests/test_surprise_s03_registry.py::test_sound_oracles_pass_on_both_target_engines
2 failed, 1295 passed, 3 skipped in 716.35s (0:11:56)
```

### `python -m surprise.gates.s16 --only instances runner registry oracles cve m1 seeds`

Exit code: 1

```text
[PASS] instances: 16.15 and 15.19 from D:\CoevoDB\.orch\pg16\binaries\pgsql\bin / D:\CoevoDB\.orch\pg15\binaries\pgsql\bin; settings, locale and the non-superuser role as pinned; DSNs exported and restored; stop_all and the check CLI work (44s)
[PASS] runner: private schemas, refused statements, no superuser powers, timeout, a lost backend, setup SETs as session defaults, stable error text, schemas dropped on close; old runner on 15.19 (16s)
[PASS] registry: targets ('duckdb', 'datafusion', 'postgres'); references of postgres ['datafusion', 'duckdb', 'sqlite']; tlp and plan variant judge a PostgreSQL case (7s)
[FAIL] oracles: native index variants compared: {'full_query': 'SELECT a, b FROM t WHERE b > 3', 'index_variants_compared': ['t.btree_b', 't.covering_ios'], 'index_variants_skipped': [{'variant': 't.btree_a', 'reason': 'no_index_path'}, {'variant': 't.partial', 'reason': 'no_index_path'}, {'variant': 't.expr_abs', 'reason': 'no_index_path'}, {'variant': 't.brin', 'reason': 'no_index_path'}, {'variant': 't.hot_update', 'reason': 'no_index_path'}, {'variant': 'analyze_all', 'reason': 'no_index_path'}]}
[FAIL] cve: PG-F tier 3: switches ['enable_indexscan', 'enable_memoize', 'enable_nestloop']
[FAIL] m1: M1 PG-F: switches ['enable_indexscan', 'enable_memoize', 'enable_nestloop']
[PASS] seeds: 308 PostgreSQL seeds: 102 setups and 93 queries run on 16.15 (46s)
S16 GATE [only: instances, runner, registry, oracles, cve, m1, seeds]: FAIL (4/7 groups passed)
```

### `python -m surprise.gates.s04`

Exit code: 1

```text
[PASS] contracts: 17 invalid sources, 7 CVE constants in the manifest; raw entry points untouched; 5 bad requests rejected before execution (1s)
[PASS] isolation: ok / error / timeout x2 / crash x2 told apart; 7 distinct processes for one candidate; process death, hang and dying reference contained (28s)
[PASS] tier1: 6 stable families fail after 5 fresh reruns; F8 unstable; F5 reproduced 0/5; 6 scripted rerun schedules (34s)
[PASS] premise: ASOF ties, writing statements and incomparable cross-engine values are invalid; their tie-free, crashing and comparable counterparts stay fail (27s)
[PASS] environment: 52 files hashed, 17 imported old modules all covered; old engines, PostgreSQL 16.15 and 5 packages recorded (1s)
[PASS] tier2: fix-set attribution: F1, F6, F6 via TLP consistent, F2 escalated; profile attribution: DF-A consistent, DF-B escalated; 5 malformed hypotheses rejected (44s)
[PASS] tier3: 9 confirmed cases profiled: fix sets as measured and as in recall_repros.json, version ladder, minimised subsequence; noise removed; lost candidate downgraded (67s)
[PASS] m1: 50 final labels in the ledger (14 fail, 20 invalid, 16 pass); known recall gaps: DF-E, DF-G, DF-H, DF-J, F10, F5 (106s)
[FAIL] freeze: the harness changed after the freeze: ['changed: surprise/harness/cve/certify.py', 'changed: surprise/harness/cve/tier3.py', 'changed: surprise/harness/manifest.py', 'changed: surprise/harness/oracles/index_presence.py', 'added: surprise/harness/oracles/pg_target.py', 'changed: surprise/harness/oracles/registry.py']
S04 GATE: FAIL (8/9 groups passed)
```

### `python -m surprise.gates.s03`

Exit code: 0

```text
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
[PASS] local: ART exercised, injected mismatch caught; 3 proved rules x 2 engines incl NULL; untrusted pairs rejected
[PASS] cross: PG16 + DuckDB witness DF-A/DF-B; insufficient quorum, ties, multiple outliers and engine aliases rejected
[PASS] version: F2 old/new measured bags and regression direction; both old venvs work; directionless mismatch invalid
[PASS] matrix: 7 oracles x 2 engines, 14 ledger records, no hidden harness failures, manifest verified
S03 GATE: PASS (5/5 groups passed)
```

### `python -m surprise.gates.s07`

Exit code: 0

```text
[PASS] constants: 4 new constants beside the nine of S6, all in the manifest; a change is reported by name (0s)
[PASS] length: hypothesis = 8.0 + 7.4 x |S| bits; theory = sum (0s)
[PASS] theory_api: remove, reserve_id, passes, next_id; common_conjunction agrees with generalize on 81 pairs (0s)
[PASS] store: one file per hypothesis, save/load is the identity, 22 damaged stores refused, logs append-only (1s)
[PASS] generations: closing a generation snapshots its last state and leaves the live state alone; snapshots load, predict and are checked (0s)
[PASS] imports: 16 theory files import no model and no old code; 5 import orders load in fresh processes (4s)
[PASS] edits: 20 malformed proposals refused; claims and fingerprints ignore ids and evidence; bets match by spec; held-out sample is deterministic (0s)
[PASS] accept: hand-written h2 accepted on length alone and both bets kept; a held-out pass, the trigger record, no gain, no bets each refuse an edit; only refutations enter the negative memory; 4 unexplained failures pay for a hypothesis, 1 does not (0s)
[PASS] rollback: a lost bet rolls back the edit and replays what was observed since; the claim enters the negative memory and is refused under any kind; a settled edit survives contradictions; later edits cascade without blame; manual rollback (1s)
[PASS] journal: reopening reproduces the workbench and it continues identically; the journal alone reproduces the theory; labels are kept without detail (1s)
[PASS] mdl: merge when nothing separates two hypotheses of one identity, not when a known pass lies between them; tighten after 16 contradictions, split after 40, neither earlier; compress() reaches a fixed point and does not undo itself (3s)
[PASS] families: fix-set families span oracles; a hypothesis without a fix set is its own family; owner = opened, attributed, or first absorber (0s)
[PASS] ciao: mean surprise of the old records by generation: 0.537, 0.074, 0.074 bits (0s)
[PASS] replay: 74 experiments, 11 hypotheses; confirmed fail: 48, confirmed pass: 5, pending fail: 13, unexplored fail: 4, unexplored pass: 1; 47/54 repeats predicted before execution, 47 at tier 2; wrong edit e1 rolled back by s07-replay:49; compress applied [], declined ['merge:h6+h10:holdout', 'merge:h9+h11:holdout']; absorbed twice: [] (390s)
[PASS] ledger: 24 adjudicated failures in 10 manual families: new framework 11 families, ARI 0.974, pair F1 0.976 (P 1.00 R 0.95); sigma 19 families, ARI 0.425, pair F1 0.444 (P 1.00 R 0.29); merged against the ledger: []; split against it: ['DF-D|DF-D_where'] (94s)
S07 GATE: PASS (15/15 groups passed)
```

### `git diff --check`

Exit code: 0

```text

```

### `git commit -m "Add PostgreSQL native index and old-server oracle paths"`

Exit code: 0

```text
[grok/s16-oracles 34a7cc3] Add PostgreSQL native index and old-server oracle paths
 6 files changed, 360 insertions(+), 5 deletions(-)
 create mode 100644 framework/tests/test_surprise_s16_oracles.py
```

### `git status --short`

Exit code: 0

```text

```

## 与说明的偏差

- 直接执行 `pytest -q tests/test_surprise_s16_oracles.py` 在收集阶段报 `ModuleNotFoundError: No module named 'oracles'`。`Get-Command python, pytest` 确认两者均来自 `D:\CoevoDB\.venv\Scripts\`，`python` 的 sys.executable 也是该项目解释器。改为同一解释器的 `python -m pytest` 完成新增测试和全量测试；没有切换解释器或修改环境配置。早先进度消息提到的 Anaconda 路径来自 traceback，不能据此单独判定 pytest 使用了错误解释器。
- 新增测试全部通过，但全量测试存在两项基线失败，S16 仅 4/7 组通过，未达到说明要求的全通过状态。按执行者规则未调整断言或扩大实现范围，提交当前实现供编排者审查。
- S04 仅 freeze 失败，属于说明预先允许的情况；没有自行重新冻结。

## 未决问题

1. `framework/tests/test_surprise_s03_registry.py:68` 仍断言 `TARGET_ENGINES == ('duckdb', 'datafusion')`，与前置 s16-core 已加入 postgres 的 registry 冲突。另一个失败在同文件 `test_sound_oracles_pass_on_both_target_engines`，遍历新增 postgres 时没有启动实例，缺少 `COEVO_TARGET_PG_DSN`。本包不允许修改该文件，也未改变 registry。需要编排者处理基线测试与 S16 前置条件的衔接。
2. `framework/surprise/gates/s16.py` 的 oracles 组要求 indexable 用例至少比较 4 个原生索引变体；实际查询 `SELECT a, b FROM t WHERE b > 3` 只有 `t.btree_b`、`t.covering_ios` 经 EXPLAIN 确认使用 Index/Bitmap。其他 6 个变体均没有索引路径，按说明记录为 no_index_path。新增测试在谓词使用第一列的查询中可以比较至少 4 个变体。需要编排者核对既定用例与门槛数量预期；不能把没走索引的变体计为已比较来满足门槛。
3. S16 的 cve 与 m1 组在 PG-F tier 3 身份检查失败：最终 switches 为 `['enable_indexscan', 'enable_memoize', 'enable_nestloop']`，门槛预期为 `['no_memoize']`。现有 `certify.py` 会用非空 profile.fix_set 替换最终 identity.switches（本包未改变此逻辑）。门槛在该断言处停止，后续 profile 检查尚未验收，不能宣称 S16 的 PG-F 完整身份已通过。需要编排者核对 fix-set 实测值与原始见证开关的预期；说明只允许在 certify.py 加 single-thread 映射，不允许更改其他 CVE 逻辑。

所有已启动的检查均已结束；真实 PG 测试和门槛使用其上下文管理器清理临时实例。没有操作端口 55432 的参照实例或 `.orch/pg16/data`。
