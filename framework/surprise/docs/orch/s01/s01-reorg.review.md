# 审查包 · s01-reorg

- 生成时间：2026-10-08T21:19:12+11:00
- 基线：`session/s01`（a28532ad5cd4）
- 分支：`grok/s01-reorg` @ c649c7eb42f3，基线之上 3 个提交
- 运行：共 1 轮（返工 0 轮），最近一轮退出码 0，用时 11m22s
- grok：grok 1.0.46 (2765805b9442)；会话 `0cae9e89-8110-42d4-91d9-9ab31d9be9d5`

## 红旗汇总

- 新增宽泛的异常捕获 4 处（确认没有吞掉失败）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s01..grok/s01-reorg
git diff -M --stat session/s01..grok/s01-reorg
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/campaigns/**`、`framework/scripts/pg_*.py`、`framework/targets/duckdb_runner.py`、`framework/oracles/db_runner.py`、`framework/surprise/__init__.py`、`framework/surprise/harness/__init__.py`、`framework/surprise/features/__init__.py`、`framework/surprise/theory/__init__.py`、`framework/surprise/hunter/__init__.py`、`framework/surprise/diagnoser/__init__.py`、`framework/surprise/roles/__init__.py`、`framework/surprise/metrics/__init__.py`、`framework/surprise/experiments/__init__.py`、`framework/surprise/baselines/__init__.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`

| 状态 | 路径 | 标记 |
|---|---|---|
| R100 | `framework/scripts/pg_am_diff.py` → `framework/campaigns/pg_am_diff.py` |  |
| R100 | `framework/scripts/pg_amcheck.py` → `framework/campaigns/pg_amcheck.py` |  |
| R100 | `framework/scripts/pg_belief_audit.py` → `framework/campaigns/pg_belief_audit.py` |  |
| R100 | `framework/scripts/pg_belief_gen.py` → `framework/campaigns/pg_belief_gen.py` |  |
| R100 | `framework/scripts/pg_belief_sweep.py` → `framework/campaigns/pg_belief_sweep.py` |  |
| R100 | `framework/scripts/pg_catalog_check.py` → `framework/campaigns/pg_catalog_check.py` |  |
| R100 | `framework/scripts/pg_coldiff.py` → `framework/campaigns/pg_coldiff.py` |  |
| R100 | `framework/scripts/pg_coldstart.py` → `framework/campaigns/pg_coldstart.py` |  |
| R100 | `framework/scripts/pg_crash_recover.py` → `framework/campaigns/pg_crash_recover.py` |  |
| R100 | `framework/scripts/pg_cursor_oracle.py` → `framework/campaigns/pg_cursor_oracle.py` |  |
| R100 | `framework/scripts/pg_ddl_stress.py` → `framework/campaigns/pg_ddl_stress.py` |  |
| R100 | `framework/scripts/pg_dml_hunt.py` → `framework/campaigns/pg_dml_hunt.py` |  |
| R100 | `framework/scripts/pg_dqe.py` → `framework/campaigns/pg_dqe.py` |  |
| R100 | `framework/scripts/pg_eager_agg.py` → `framework/campaigns/pg_eager_agg.py` |  |
| R100 | `framework/scripts/pg_edge_scan.py` → `framework/campaigns/pg_edge_scan.py` |  |
| R100 | `framework/scripts/pg_error_scan.py` → `framework/campaigns/pg_error_scan.py` |  |
| R100 | `framework/scripts/pg_execdiff.py` → `framework/campaigns/pg_execdiff.py` |  |
| R100 | `framework/scripts/pg_extproto_diff.py` → `framework/campaigns/pg_extproto_diff.py` |  |
| R100 | `framework/scripts/pg_fdw_selfloop.py` → `framework/campaigns/pg_fdw_selfloop.py` |  |
| R100 | `framework/scripts/pg_fkddl.py` → `framework/campaigns/pg_fkddl.py` |  |
| R100 | `framework/scripts/pg_gsdiff.py` → `framework/campaigns/pg_gsdiff.py` |  |
| R100 | `framework/scripts/pg_index_hunt.py` → `framework/campaigns/pg_index_hunt.py` |  |
| R100 | `framework/scripts/pg_inject_sweep.py` → `framework/campaigns/pg_inject_sweep.py` |  |
| R100 | `framework/scripts/pg_leverdiff.py` → `framework/campaigns/pg_leverdiff.py` |  |
| R100 | `framework/scripts/pg_logical_loop.py` → `framework/campaigns/pg_logical_loop.py` |  |
| R100 | `framework/scripts/pg_memoize_sweep.py` → `framework/campaigns/pg_memoize_sweep.py` |  |
| R100 | `framework/scripts/pg_mutate_recall.py` → `framework/campaigns/pg_mutate_recall.py` |  |
| R100 | `framework/scripts/pg_parallel.py` → `framework/campaigns/pg_parallel.py` |  |
| R100 | `framework/scripts/pg_plan_cache.py` → `framework/campaigns/pg_plan_cache.py` |  |
| R100 | `framework/scripts/pg_plan_gucfill.py` → `framework/campaigns/pg_plan_gucfill.py` |  |
| R099 | `framework/scripts/pg_probe_run.py` → `framework/campaigns/pg_probe_run.py` |  |
| R100 | `framework/scripts/pg_recall_check.py` → `framework/campaigns/pg_recall_check.py` |  |
| R100 | `framework/scripts/pg_repack_mvcc.py` → `framework/campaigns/pg_repack_mvcc.py` |  |
| R100 | `framework/scripts/pg_repack_probe.py` → `framework/campaigns/pg_repack_probe.py` |  |
| R099 | `framework/scripts/pg_ssi_sibling.py` → `framework/campaigns/pg_ssi_sibling.py` |  |
| R100 | `framework/scripts/pg_tlp.py` → `framework/campaigns/pg_tlp.py` |  |
| R100 | `framework/scripts/pg_tlp_groupby.py` → `framework/campaigns/pg_tlp_groupby.py` |  |
| R100 | `framework/scripts/pg_transform_probes.py` → `framework/campaigns/pg_transform_probes.py` |  |
| R100 | `framework/scripts/pg_txn_fuzz.py` → `framework/campaigns/pg_txn_fuzz.py` |  |
| R100 | `framework/scripts/pg_upgrade_mxact.py` → `framework/campaigns/pg_upgrade_mxact.py` |  |
| R100 | `framework/scripts/pg_version_ladder.py` → `framework/campaigns/pg_version_ladder.py` |  |
| M | `framework/oracles/db_runner.py` |  |
| A | `framework/surprise/__init__.py` |  |
| A | `framework/surprise/baselines/__init__.py` |  |
| A | `framework/surprise/diagnoser/__init__.py` |  |
| A | `framework/surprise/experiments/__init__.py` |  |
| A | `framework/surprise/features/__init__.py` |  |
| A | `framework/surprise/harness/__init__.py` |  |
| A | `framework/surprise/hunter/__init__.py` |  |
| A | `framework/surprise/metrics/__init__.py` |  |
| A | `framework/surprise/roles/__init__.py` |  |
| A | `framework/surprise/theory/__init__.py` |  |
| A | `framework/targets/duckdb_runner.py` |  |

提交：

- 709cea4 Junke: S1: move PG campaign scripts to framework/campaigns
- 1bc3177 Junke: S1: move DuckDBRunner to targets/duckdb_runner.py
- c649c7e Junke: S1: add the surprise package skeleton

## 2. diff 统计

```text
 framework/{scripts => campaigns}/pg_am_diff.py     |   0
 framework/{scripts => campaigns}/pg_amcheck.py     |   0
 .../{scripts => campaigns}/pg_belief_audit.py      |   0
 framework/{scripts => campaigns}/pg_belief_gen.py  |   0
 .../{scripts => campaigns}/pg_belief_sweep.py      |   0
 .../{scripts => campaigns}/pg_catalog_check.py     |   0
 framework/{scripts => campaigns}/pg_coldiff.py     |   0
 framework/{scripts => campaigns}/pg_coldstart.py   |   0
 .../{scripts => campaigns}/pg_crash_recover.py     |   0
 .../{scripts => campaigns}/pg_cursor_oracle.py     |   0
 framework/{scripts => campaigns}/pg_ddl_stress.py  |   0
 framework/{scripts => campaigns}/pg_dml_hunt.py    |   0
 framework/{scripts => campaigns}/pg_dqe.py         |   0
 framework/{scripts => campaigns}/pg_eager_agg.py   |   0
 framework/{scripts => campaigns}/pg_edge_scan.py   |   0
 framework/{scripts => campaigns}/pg_error_scan.py  |   0
 framework/{scripts => campaigns}/pg_execdiff.py    |   0
 .../{scripts => campaigns}/pg_extproto_diff.py     |   0
 .../{scripts => campaigns}/pg_fdw_selfloop.py      |   0
 framework/{scripts => campaigns}/pg_fkddl.py       |   0
 framework/{scripts => campaigns}/pg_gsdiff.py      |   0
 framework/{scripts => campaigns}/pg_index_hunt.py  |   0
 .../{scripts => campaigns}/pg_inject_sweep.py      |   0
 framework/{scripts => campaigns}/pg_leverdiff.py   |   0
 .../{scripts => campaigns}/pg_logical_loop.py      |   0
 .../{scripts => campaigns}/pg_memoize_sweep.py     |   0
 .../{scripts => campaigns}/pg_mutate_recall.py     |   0
 framework/{scripts => campaigns}/pg_parallel.py    |   0
 framework/{scripts => campaigns}/pg_plan_cache.py  |   0
 .../{scripts => campaigns}/pg_plan_gucfill.py      |   0
 framework/{scripts => campaigns}/pg_probe_run.py   |   2 +-
 .../{scripts => campaigns}/pg_recall_check.py      |   0
 framework/{scripts => campaigns}/pg_repack_mvcc.py |   0
 .../{scripts => campaigns}/pg_repack_probe.py      |   0
 framework/{scripts => campaigns}/pg_ssi_sibling.py |   2 +-
 framework/{scripts => campaigns}/pg_tlp.py         |   0
 framework/{scripts => campaigns}/pg_tlp_groupby.py |   0
 .../{scripts => campaigns}/pg_transform_probes.py  |   0
 framework/{scripts => campaigns}/pg_txn_fuzz.py    |   0
 .../{scripts => campaigns}/pg_upgrade_mxact.py     |   0
 .../{scripts => campaigns}/pg_version_ladder.py    |   0
 framework/oracles/db_runner.py                     | 128 +-------------------
 framework/surprise/__init__.py                     |   1 +
 framework/surprise/baselines/__init__.py           |   1 +
 framework/surprise/diagnoser/__init__.py           |   1 +
 framework/surprise/experiments/__init__.py         |   1 +
 framework/surprise/features/__init__.py            |   1 +
 framework/surprise/harness/__init__.py             |   1 +
 framework/surprise/hunter/__init__.py              |   1 +
 framework/surprise/metrics/__init__.py             |   1 +
 framework/surprise/roles/__init__.py               |   1 +
 framework/surprise/theory/__init__.py              |   1 +
 framework/targets/duckdb_runner.py                 | 130 +++++++++++++++++++++
 53 files changed, 148 insertions(+), 124 deletions(-)
```

重命名 41 个，其中内容完全不变（R100）39 个。

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，0m01s；passed 64，skipped 3

```text
........................ss..................................s......      [100%]
64 passed, 3 skipped in 1.22s
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 0，0m10s

```text
=== gate s01 ===
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 64 passed (baseline 64): 64 passed, 3 skipped in 1.24s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
=== summary ===
s01: PASS
GATES: PASS (1/1 passed)
```

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- 无

非测试文件里另有 1 行被删的 assert，读 diff 时留意。

### 4.4 新增的宽泛异常捕获

- `framework/targets/duckdb_runner.py:51` `except Exception: # noqa: BLE001 - closing must never raise`
- `framework/targets/duckdb_runner.py:71` `except Exception as exc: # noqa: BLE001 - record and continue`
- `framework/targets/duckdb_runner.py:96` `except Exception as exc: # noqa: BLE001 - any engine error recorded`
- `framework/targets/duckdb_runner.py:110` `except Exception: # noqa: BLE001`

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s01-reorg.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 无

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s01-reorg.jsonl`：1802 条事件（available_commands 43，end 1，orch.exit 1，orch.start 1，plan 3，text 479，thought 941，tool_call 73，tool_call_update 221，usage 39）；各轮合计 39 个模型回合，grok 上报花费 0.6006 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 1 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- `Remove-Item -Recurse -Force .orch\tmp\pytest-of-91484 ; if (Test-Path .orch\tmp) { $left = Get-ChildItem .orch\tmp -For… -> Tool `run_terminal_command` was not executed: Denied by permission policy: deny rule on bash matching "Remove-Item *-Recurse*"`

最后几条：

```text
tool_call run_terminal_command: {"command": "Get-ChildItem .orch\\tmp\\pytest-of-91484 -Force -Recurse | Select-Object FullName, Length, LastWriteTime", "description": "Inspect unexpected pytest temp directory"}
tool_update [in_progress]: 
tool_update [in_progress]: 
tool_update [in_progress]: FullName Length
tool_update [completed]: exit: 0 FullName Length -------- ------ D:\CoevoDB\.worktrees\s01-reorg\.orch\tmp\pytest-of-91484\pytest-0 D:\CoevoDB\.worktrees\s01-reorg\.orch\tmp\pytest-of-91484\pytest-1 D:\Co…
thought: 正在查看 pytest 的 basetemp。该目录因 pytest 配置将 tmp_path 设为当前目录而创建。 该临时目录是 pytest 运行产生的测试残留，属于非交付物。根据 scratch 规则，应将其清理。
tool_call run_terminal_command: {"command": "Remove-Item -Recurse -Force .orch\\tmp\\pytest-of-91484 ; if (Test-Path .orch\\tmp) { $left = Get-ChildItem .orch\\tmp -Force ; if ($left) { $left | Select-Object -Ex…
tool_update [failed]: Tool `run_terminal_command` was not executed: Denied by permission policy: deny rule on bash matching "Remove-Item *-Recurse*"
thought: 权限策略阻止了 Remove-Item -Recurse 命令。 执行规则禁止绕过权限拒绝。pytest 临时目录未纳入交付物，因此不清理。
text: 工作包 s01-reorg 已完成，提交在分支 `grok/s01-reorg` 上，工作区干净。报告在 `.orch/report.md`。 三件事都按说明做完了： - 41 个 `framework/scripts/pg_*.py` 移到 `framework/campaigns/`。39 个文件内容未改（`R100`）；`pg_probe_run.p…
end: stopReason=end_turn turns=39 cost_usd=0.60060116
orch.exit: {"pkg": "s01-reorg", "run": 1, "at": "2026-10-08T21:19:01+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
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
````

## 8. 结论（编排者填）

**合并（一次通过，返工 0 轮）。** 理由，均为编排者独立核对，不采信第 7 节的自述：

- 范围：53 个改动文件全部在允许路径内，禁区零改动；worktree 干净；派发以来其他 ref 没有变化，主检出区干净。
- 复跑（第 3 节）：pytest 64 passed / 3 skipped，等于基线；`surprise.gates.all` 7/7。与执行者报告的数字一致。
- 只有移动：41 个重命名里 39 个 R100；`pg_probe_run.py`、`pg_ssi_sibling.py` 是 R099，各只有一行 `scripts.` → `campaigns.` 的导入路径变化。`DuckDBRunner` 不是整文件重命名，所以另外从 git 对象逐字节比对：`targets/duckdb_runner.py` 里的类体（107 行）与基线 `oracles/db_runner.py` 完全相同；`oracles/db_runner.py` 里的 `QueryResult`、`bags_equal` 与基线完全相同；两个文件的顶层语句除了 `.normalize` → `oracles.normalize`、新增的 `from oracles.db_runner import QueryResult` 和末尾的兼容导入之外，都是基线原有的 import 行（`from typing import Any, Iterable` 按各自用到的名字拆成两行）。
- 唯一的红旗"新增宽泛的异常捕获 4 处"是误报：这 4 行就是搬过去的类体里原有的 `except Exception`，基线里逐字相同。第 4.3 节提到的"被删的 assert"同理，是 `run()` 里随类搬走的 `assert self._conn is not None`。
- 骨架：10 个 `__init__.py` 都只有一行文档字符串，没有代码、没有 import。
- 日志：23 条 shell 命令全部在 worktree 内（git status / mv / add / commit、pytest、门槛、几条只读的 `python -c` 检查）；没有 pip，没有写 worktree 以外的路径。被拦下 1 次（递归删除自己 `.orch/tmp` 下的 pytest 临时目录），之后没有换写法绕过。执行者用一个放在 `.orch/tmp` 的 Python 脚本写文件，结果以 diff 为准，没有越界。
- 没有 LLM 调用，diff 与日志里没有密钥。

留意但不返工的两点：

1. `oracles/db_runner.py` 里 `from typing import Any` 与 `@dataclass` 之间少了一个空行（原来是两个）。纯格式，不值得用掉一轮返工。
2. `DuckDBRunner` 的 debug 日志记录器名字从 `oracles.db_runner` 变成 `targets.duckdb_runner`（`logging.getLogger(__name__)` 随类搬走的必然结果）。没有测试或配置依赖这个名字。
