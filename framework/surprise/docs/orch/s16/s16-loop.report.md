# 报告 · s16-loop · 第 1 轮返工

状态：第 1 轮审查返工完成。S16 3/3、S05 9/9、S08 6/6、S15 5/5 通过；pytest 和 S11 只保留审查明确认可的已知失败。本轮根据 `.orch/review-1.md` 明确放行 `framework/surprise/features/data.py`。前一轮提交 `ce2ffbf`，本轮提交 7ac8ac1，分支 `grok/s16-loop`。

## 改了哪些文件
- `framework/surprise/features/data.py`（修改）：只为 postgres 增加 pg_attribute / format_type / to_regclass 的列类型读取分支；按 SQL 规则转义表引用中的单引号；关系不存在或目录查询失败时返回 unavailable。PG 类型先转换到既有类型词汇，再调用原有 `_type_feature`；未知类型为 other。原有 `_type_feature`、`_type_token`、`_describe` 及其他辅助函数保持原样；非 PG 仍调用原来的 DESCRIBE 分支。
- `framework/tests/test_surprise_s16_loop.py`（修改）：增加真实 PG 测试，逐项核对 smallint / integer / bigint / real / double precision / numeric / boolean / character varying / character / text / name / date / timestamp 的类型叶子，补充 uuid 和数组归 other、带单引号的表名、缺失关系、目录读取错误，以及独立子进程提取的数据层 ok。

前一轮其他改动保持在 `ce2ffbf`，本轮没有改动其他生产代码、基线测试或门槛。

## 跑了哪些命令

所有测试与门槛在 framework 目录执行，使用 brief 指定的 python / pytest；pytest 先设置 `$env:PYTHONPATH = (Get-Location).Path`。完整日志在同一 `.orch/` 目录下的 `review1-*.log`；下列逐条列出退出码与原始输出末 20 行。没有真实 LLM 调用。

### `pytest -q tests/test_surprise_s16_loop.py -k data_catalog`

Exit code: 0

```text
.                                                                        [100%]
1 passed, 10 deselected in 5.98s
```

### `pytest -q testing tests`

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
2 failed, 1376 passed, 3 skipped in 791.61s (0:13:11)
```

### `python -m surprise.gates.s16 --only phi loop grid`

Exit code: 0

```text
[PASS] phi: phi stable across processes for ['PG-A', 'PG-F', 'indexable', 'plain_pred']; PG-F plan has ['plan:MEMOIZE', 'plan:NESTED_LOOP', 'plan:INDEX_SCAN', 'plan:AGGREGATE', 'plan:INDEX_ONLY_SCAN'] (8s)
[PASS] loop: 40 experiments on postgres (['invalid', 'pass'], oracles ['cross_dbms', 'equivalent_query', 'index_presence', 'norec', 'plan_variant', 'tlp', 'version_differential'], 0 harness errors); own instances started and removed; exported DSNs reused (140s)
[PASS] grid: two PostgreSQL cells done on their own instances (ports [12424, 12426]); report with recall against PG-F (97s)
S16 GATE [only: phi, loop, grid]: PASS (3/3 groups passed)
```

### `python -m surprise.gates.s05`

Exit code: 0

```text
[PASS] vocab: 166 core entries (131 leaves) with hierarchy; open families; digest 1e001c14a030 stable across processes; invented feature registered, 8 bad ones rejected, saved and loaded; phi container (1s)
[PASS] spec: 12 hand-written phi / spec pairs judged as expected; 3 malformed specs rejected (0s)
[PASS] units: 23 hand-written feature sets project onto the expected units (0s)
[PASS] ast: 74 probes, 5 fallbacks, 3 invariance pairs; 12 families show their core features and are pairwise distinct (66 pairs) (0s)
[PASS] dynamic: 13 data probes on two engines, 6 measured plans; failing setup, ast-only and isolated extraction behave (2s)
[PASS] stable: 25 cases (12 families, 13 corpus seeds): two processes and this one agree (21s)
[PASS] distinguish: 12 families: pairwise distinct by statement text alone (66 pairs) and by phi; DF-A -> DF-B is one sibling swap; 11 measured units (0s)
[PASS] specs: 17 hand-written spec / SQL pairs, all judged correctly (0s)
[PASS] corpus: 1092 seeds in 76 units over 10 constructs; ast fallback 34, plan ok 480, data ok 483; top [('postgres|plain|none|unknown', 134), ('duckdb|plain|none|unknown', 83), ('duckdb|window|none|unknown', 56)]; 16s (34s)
S05 GATE: PASS (9/9 groups passed)
```

### `python -m surprise.gates.s08 --only no_llm constants scoring operators candidates lanes`

Exit code: 0

```text
[PASS] no_llm: hunter, metrics, baselines, diagnoser and the loop import no model client and no old agent (0s)
[PASS] constants: 12 hunter and 2 diagnoser constants as planned; BETA = 1.0 (pre-experiment families per run: {'0.5': {'9001': 1, '9002': 3, '9003': 3}, '1.0': {'9001': 3, '9002': 3, '9003': 3}, '2.0': {'9001': 3, '9002': 3, '9003': 3}, '4.0': {'9001': 3, '9002': 5, '9003': 1}}) (0s)
[PASS] scoring: U untested 0.498 bits, adjacent 0.758; pending 0.455 after 50 probes, adjacent unexplored 1.365 at beta 2, confirmed 0 (0s)
[PASS] operators: 29 mutants of a three-statement case (4 deletions); oracle options filtered as planned (0s)
[PASS] candidates: after F1 and DF-A: {'refine': 4, 'generalize': 4, 'migrate': 2, 'explore': 81} candidates, all traceable; chose refine at 0.909 (16s)
[PASS] lanes: 32 records; executed {'bootstrap': 2, 'explore': 23, 'generalize': 3, 'refine': 4}; offered {'refine': 30, 'generalize': 31, 'migrate': 139, 'explore': 2474}; 4 families opened, 2 edits (79s)
S08 GATE [only: no_llm, constants, scoring, operators, candidates, lanes]: PASS (6/6 groups passed)
```

### `python -m surprise.gates.s11`

Exit code: 1

```text
[PASS] constants: 7 metric constants, request deadline 600.0 s, pure-LLM constants and 10 topics (0s)
[PASS] store: 6 replace calls for 3 transient failures (0.36s); a lasting failure raises PermissionError (2s)
[PASS] loop_error: original exception kept and written to error.txt (both, drive) (1s)
[PASS] deadline: normal answer passes; deadline 1.5s held (trickle 2.2s, silent 2.2s); errors booked, not cached (11s)
[PASS] vocabulary: run_registry, new_families, compare, recall.score, RunData and run_metrics all read the run's vocabulary (44s)
[PASS] stats: exact and asymptotic MWU (scipy agrees), A12, median, summarize as hand-computed (1s)
[PASS] runmetrics: 31 records, 1 ledger families, Brier 0.2194, 1 high-surprise records, invalid 14, theory length 193.0; all recomputed (0s)
[FAIL] ciao: artifact directory results/s08/longrun is missing on this machine
[PASS] llm_metrics: 15 experiments replayed; 2 conjectures, survival 0.0, accuracy 0.7142857142857143 over 7 settled bets; families via {'implement': 0, 'bet': 1, 'translate': 0, 'llm_rule': 0, 'invented_feature': 0}; 23 calls (43s)
[PASS] rq6: classify, F2 fix conditions (1 entries), pair agreement as hand-computed; F2 hypothesis too_narrow (missing [], extra 9 literals); recall 0.5 (5s)
[PASS] arms: random Hunter deterministic and different; frozen theory unchanged (1 failures fully profiled); frozen Diagnoser no edits; theory-from and select-from (5 choices scored differently); 5 usage errors refused (114s)
[PASS] pure_llm_script: 4 cases executed from 3 calls (1 reply rejected, 2 bad cases skipped); prompts deterministic; budget holds (4s)
[PASS] pure_llm: 16 cases from 4 cached calls replayed identically; labels {'pass': 15, 'invalid': 1}; 0 families (7s)
[PASS] dedup: 3 failures, 1 true duplicates; sigma p/r 1.0/1.0, membership p/r None/0.0 (6s)
[PASS] coverage: 4 upstream regression seeds x 2 oracles on 1.5.5 and 1.1.3; {'plan_variant': {'old': {'pass': 4}, 'new': {'pass': 4}, 'fail_old_pass_new': [], 'fail_both': [], 'fail_new_only': []}, 'equivalent_query': {'old': {'invalid': 4}, 'new': {'invalid': 4}, 'fail_old_pass_new': [], 'fail_both': [], 'fail_new_only': []}} (7s)
[PASS] sqlancer: 35 runs, 0 bugs; per engine rows match docs/FINAL_REPORT.md (0s)
[PASS] grid: 2 arms x 2 seeds in 4.1 min, resumed, report and 7 figures in one command; median families/hour {'surprise': 29.882032211270218, 'old': 29.77005716998551}; p 1.0, A12 0.625 (248s)
S11 GATE: FAIL (16/17 groups passed)
```

### `python -m surprise.gates.s15 --only config parallel kill interrupt llm`

Exit code: 0

```text
cpus_per_cell is set but os.sched_setaffinity is unavailable; cells will not be pinned
a/s1-r0 done
b/s1-r0 done
c/s1-r0 done
d/s1-r0 done
a/s2-r0 done
b/s2-r0 done
c/s2-r0 done
d/s2-r0 done
[PASS] parallel: 8 stand-ins, 4 at a time in block order with slots and engine threads; 4 real DuckDB cells ran together (start spread 0s) (69s)
quick/s1-r0 done
handles/s1-r0 done (killed)
ignores/s1-r0 done (killed)
handles/s1-r0 done
ignores/s1-r0 done
quick/s1-r0 done
[PASS] kill: interrupt at budget+grace (report written, exit 130), hard kill of the tree after the delay, done (killed), not rerun (10s)
[PASS] interrupt: loop interrupted after 3 experiments; SQLancer driver and its java process stopped (60s)
[PASS] llm: gateway: unlimited, env ceiling, tier override; M3 replay identical with unlimited calls; 7 strong-tier calls went to deepseek-v4-pro; pure-LLM the same (117s)
S15 GATE [only: config, parallel, kill, interrupt, llm]: PASS (5/5 groups passed)
```

### `python - (source-preservation audit against ce2ffbf, before commit)`

Exit code: 0

```text
All pre-existing helpers unchanged; extract_data adds only the postgres branch
_type_feature and _type_token unchanged
```

### `git diff --check`

Exit code: 0

```text
git : warning: in the working copy of 'framework/surprise/features/data.py', LF will be replaced by CRLF the next time 
Git touches it
所在位置 行:2 字符: 1
+ git diff --check *> .orch/review1-diff-check.log
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (warning: in the... Git touches it:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
warning: in the working copy of 'framework/tests/test_surprise_s16_loop.py', LF will be replaced by CRLF the next time 
Git touches it
```

### `python -c "from pathlib import Path; from surprise.experiments.pg_instance import stop_all; root = Path('../.orch/tmp').resolve(); assert root.is_relative_to(Path.cwd().parent.resolve()); stopped = stop_all(root); print('residual_servers_stopped=' + str(len(stopped)))"`

Exit code: 0

```text
residual_servers_stopped=0
```

### `git status --short`

Exit code: 0

```text

```

## 与说明的偏差
无。data.py 的新增允许范围来自 `.orch/review-1.md` 的“放行并要改”一节。没有修改 `_type_feature`、`_type_token` 或其他引擎行为；源码核对和 S05 的 DuckDB 语料检查均通过。

## 未决问题
- `framework/tests/test_surprise_s03_registry.py` 的两个已知失败保留，审查意见明确要求不要改：第 68 行仍要求目标只有 duckdb/datafusion；第 181 行遍历新增 PG 目标但未准备 DSN。本轮全量结果：1376 passed、3 skipped、2 failed，相比上一轮增加 1 个通过，skip 数未增加；除上述两个已知失败外全部通过。
- S11 的 ciao 需要缺失的 `results/s08/longrun`；这是 brief 和审查确认的已知例外。本轮 16/17 组通过，只有 ciao 失败。
- 上一轮报告记录的 pure_llm / sqlancer 无 Workbench 格仍输出 RQ6 recall=None。本轮审查只要求 PG 数据层返工，该项保留记录，未扩展修改。

