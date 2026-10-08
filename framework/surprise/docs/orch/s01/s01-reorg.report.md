# 报告 · s01-reorg

## 改了哪些文件
- `framework/campaigns/pg_am_diff.py`：移动自 `framework/scripts/pg_am_diff.py`（内容未改）
- `framework/campaigns/pg_amcheck.py`：移动自 `framework/scripts/pg_amcheck.py`（内容未改）
- `framework/campaigns/pg_belief_audit.py`：移动自 `framework/scripts/pg_belief_audit.py`（内容未改）
- `framework/campaigns/pg_belief_gen.py`：移动自 `framework/scripts/pg_belief_gen.py`（内容未改）
- `framework/campaigns/pg_belief_sweep.py`：移动自 `framework/scripts/pg_belief_sweep.py`（内容未改）
- `framework/campaigns/pg_catalog_check.py`：移动自 `framework/scripts/pg_catalog_check.py`（内容未改）
- `framework/campaigns/pg_coldiff.py`：移动自 `framework/scripts/pg_coldiff.py`（内容未改）
- `framework/campaigns/pg_coldstart.py`：移动自 `framework/scripts/pg_coldstart.py`（内容未改）
- `framework/campaigns/pg_crash_recover.py`：移动自 `framework/scripts/pg_crash_recover.py`（内容未改）
- `framework/campaigns/pg_cursor_oracle.py`：移动自 `framework/scripts/pg_cursor_oracle.py`（内容未改）
- `framework/campaigns/pg_ddl_stress.py`：移动自 `framework/scripts/pg_ddl_stress.py`（内容未改）
- `framework/campaigns/pg_dml_hunt.py`：移动自 `framework/scripts/pg_dml_hunt.py`（内容未改）
- `framework/campaigns/pg_dqe.py`：移动自 `framework/scripts/pg_dqe.py`（内容未改）
- `framework/campaigns/pg_eager_agg.py`：移动自 `framework/scripts/pg_eager_agg.py`（内容未改）
- `framework/campaigns/pg_edge_scan.py`：移动自 `framework/scripts/pg_edge_scan.py`（内容未改）
- `framework/campaigns/pg_error_scan.py`：移动自 `framework/scripts/pg_error_scan.py`（内容未改）
- `framework/campaigns/pg_execdiff.py`：移动自 `framework/scripts/pg_execdiff.py`（内容未改）
- `framework/campaigns/pg_extproto_diff.py`：移动自 `framework/scripts/pg_extproto_diff.py`（内容未改）
- `framework/campaigns/pg_fdw_selfloop.py`：移动自 `framework/scripts/pg_fdw_selfloop.py`（内容未改）
- `framework/campaigns/pg_fkddl.py`：移动自 `framework/scripts/pg_fkddl.py`（内容未改）
- `framework/campaigns/pg_gsdiff.py`：移动自 `framework/scripts/pg_gsdiff.py`（内容未改）
- `framework/campaigns/pg_index_hunt.py`：移动自 `framework/scripts/pg_index_hunt.py`（内容未改）
- `framework/campaigns/pg_inject_sweep.py`：移动自 `framework/scripts/pg_inject_sweep.py`（内容未改）
- `framework/campaigns/pg_leverdiff.py`：移动自 `framework/scripts/pg_leverdiff.py`（内容未改）
- `framework/campaigns/pg_logical_loop.py`：移动自 `framework/scripts/pg_logical_loop.py`（内容未改）
- `framework/campaigns/pg_memoize_sweep.py`：移动自 `framework/scripts/pg_memoize_sweep.py`（内容未改）
- `framework/campaigns/pg_mutate_recall.py`：移动自 `framework/scripts/pg_mutate_recall.py`（内容未改）
- `framework/campaigns/pg_parallel.py`：移动自 `framework/scripts/pg_parallel.py`（内容未改）
- `framework/campaigns/pg_plan_cache.py`：移动自 `framework/scripts/pg_plan_cache.py`（内容未改）
- `framework/campaigns/pg_plan_gucfill.py`：移动自 `framework/scripts/pg_plan_gucfill.py`（内容未改）
- `framework/campaigns/pg_recall_check.py`：移动自 `framework/scripts/pg_recall_check.py`（内容未改）
- `framework/campaigns/pg_repack_mvcc.py`：移动自 `framework/scripts/pg_repack_mvcc.py`（内容未改）
- `framework/campaigns/pg_repack_probe.py`：移动自 `framework/scripts/pg_repack_probe.py`（内容未改）
- `framework/campaigns/pg_tlp.py`：移动自 `framework/scripts/pg_tlp.py`（内容未改）
- `framework/campaigns/pg_tlp_groupby.py`：移动自 `framework/scripts/pg_tlp_groupby.py`（内容未改）
- `framework/campaigns/pg_transform_probes.py`：移动自 `framework/scripts/pg_transform_probes.py`（内容未改）
- `framework/campaigns/pg_txn_fuzz.py`：移动自 `framework/scripts/pg_txn_fuzz.py`（内容未改）
- `framework/campaigns/pg_upgrade_mxact.py`：移动自 `framework/scripts/pg_upgrade_mxact.py`（内容未改）
- `framework/campaigns/pg_version_ladder.py`：移动自 `framework/scripts/pg_version_ladder.py`（内容未改）
- `framework/campaigns/pg_probe_run.py`：移动自 `framework/scripts/pg_probe_run.py`，导入改为 `from campaigns.pg_recall_check import classify`
- `framework/campaigns/pg_ssi_sibling.py`：移动自 `framework/scripts/pg_ssi_sibling.py`，导入改为 `import campaigns.pg_txn_fuzz as fuzz`
- `framework/oracles/db_runner.py`：修改。留下 `QueryResult` 与 `bags_equal`，文件末尾兼容导出 `DuckDBRunner`
- `framework/targets/duckdb_runner.py`：新增。`DuckDBRunner` 类体从 `framework/oracles/db_runner.py` 原样搬来
- `framework/surprise/__init__.py`：新增。一行模块文档字符串，无导入
- `framework/surprise/harness/__init__.py`：新增。一行模块文档字符串，无导入
- `framework/surprise/features/__init__.py`：新增。一行模块文档字符串，无导入
- `framework/surprise/theory/__init__.py`：新增。一行模块文档字符串，无导入
- `framework/surprise/hunter/__init__.py`：新增。一行模块文档字符串，无导入
- `framework/surprise/diagnoser/__init__.py`：新增。一行模块文档字符串，无导入
- `framework/surprise/roles/__init__.py`：新增。一行模块文档字符串，无导入
- `framework/surprise/metrics/__init__.py`：新增。一行模块文档字符串，无导入
- `framework/surprise/experiments/__init__.py`：新增。一行模块文档字符串，无导入
- `framework/surprise/baselines/__init__.py`：新增。一行模块文档字符串，无导入

三次提交：`709cea4`（脚本移动）、`1bc3177`（DuckDBRunner）、`c649c7e`（surprise 骨架）。

## 跑了哪些命令

### `cd framework; python -m pytest -q testing tests`
退出码：0

```
........................ss..................................s......      [100%]
64 passed, 3 skipped in 1.46s
```

### `cd framework; python -m surprise.gates.all`
退出码：0

```
=== gate s01 ===
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 64 passed (baseline 64): 64 passed, 3 skipped in 1.28s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
=== summary ===
s01: PASS
GATES: PASS (1/1 passed)
```

### `cd framework; python main.py --help`
退出码：0

```
                        seeded from --playbook-seed; coevo_frozen=seeded
                        playbook, no new distillation
  --playbook-seed PLAYBOOK_SEED
                        jsonl of pre-distilled playbook rules
                        (coevo_warm/frozen)
  --iterations ITERATIONS
  --queries-per-iter QUERIES_PER_ITER
  --seed-mutations-per-iter SEED_MUTATIONS_PER_ITER
  --stagnation-limit STAGNATION_LIMIT
  --seed SEED
  --seed-corpus SEED_CORPUS
  --no-seeds
  --cross-engine        also check every query on the other engine
                        (adjudicated)
  --pg-datadir PG_DATADIR
                        pgserver datadir for the postgres target
  --results-root RESULTS_ROOT
                        directory where run artifacts are written
  --old-duckdb-venv OLD_DUCKDB_VENV
  --label LABEL         extra label appended to the run directory name
```

### `git diff -M --name-status a28532a..HEAD`
退出码：0。共 53 行。最后 20 行：

```
R100	framework/scripts/pg_repack_probe.py	framework/campaigns/pg_repack_probe.py
R099	framework/scripts/pg_ssi_sibling.py	framework/campaigns/pg_ssi_sibling.py
R100	framework/scripts/pg_tlp.py	framework/campaigns/pg_tlp.py
R100	framework/scripts/pg_tlp_groupby.py	framework/campaigns/pg_tlp_groupby.py
R100	framework/scripts/pg_transform_probes.py	framework/campaigns/pg_transform_probes.py
R100	framework/scripts/pg_txn_fuzz.py	framework/campaigns/pg_txn_fuzz.py
R100	framework/scripts/pg_upgrade_mxact.py	framework/campaigns/pg_upgrade_mxact.py
R100	framework/scripts/pg_version_ladder.py	framework/campaigns/pg_version_ladder.py
M	framework/oracles/db_runner.py
A	framework/surprise/__init__.py
A	framework/surprise/baselines/__init__.py
A	framework/surprise/diagnoser/__init__.py
A	framework/surprise/experiments/__init__.py
A	framework/surprise/features/__init__.py
A	framework/surprise/harness/__init__.py
A	framework/surprise/hunter/__init__.py
A	framework/surprise/metrics/__init__.py
A	framework/surprise/roles/__init__.py
A	framework/surprise/theory/__init__.py
A	framework/targets/duckdb_runner.py
```

### `git status --short`
退出码：0。输出为空。

## 与说明的偏差
无。

## 未决问题
无。
