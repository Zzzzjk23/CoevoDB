# 审查包 · s04-tier23

- 生成时间：2026-10-09T08:16:43+11:00
- 基线：`session/s04`（f87373f56238）
- 分支：`grok/s04-tier23` @ d081bc850473，基线之上 2 个提交
- 运行：共 2 轮（返工 1 轮），最近一轮退出码 0，用时 16m13s
- grok：grok 1.0.46 (2765805b9442)；会话 `90509aee-9cbe-4f39-b56f-0631e57a1037`

## 红旗汇总

- 改动超出 brief 允许的路径 1 处：framework/tests/test_surprise_contracts.py
- 门槛未通过（退出码 1）
- 测试里被改写的断言 3 处（逐条确认没有放宽）
- 新增宽泛的异常捕获 7 处（确认没有吞掉失败）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s04..grok/s04-tier23
git diff -M --stat session/s04..grok/s04-tier23
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/harness/cve/**`、`framework/surprise/harness/evaluate.py`、`framework/surprise/harness/constants.py`、`framework/surprise/harness/manifest.py`、`framework/tests/test_surprise_s04_*.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/harness/constants.py` |  |
| M | `framework/surprise/harness/cve/__init__.py` |  |
| M | `framework/surprise/harness/cve/certify.py` |  |
| A | `framework/surprise/harness/cve/criterion.py` |  |
| A | `framework/surprise/harness/cve/hypothesis.py` |  |
| A | `framework/surprise/harness/cve/tier3.py` |  |
| M | `framework/surprise/harness/cve/worker.py` |  |
| M | `framework/surprise/harness/evaluate.py` |  |
| M | `framework/surprise/harness/manifest.py` |  |
| M | `framework/tests/test_surprise_contracts.py` | **越界：不在允许路径内** |
| M | `framework/tests/test_surprise_s04_pipeline.py` |  |
| A | `framework/tests/test_surprise_s04_tier23.py` |  |

提交：

- 558bd7e Junke: s04-tier23: attribute hypotheses and profile minimised fails
- d081bc8 Junke: s04-tier23: record tier-1 rejections and recheck minimised fails

## 2. diff 统计

```text
 framework/surprise/harness/constants.py       |  13 +
 framework/surprise/harness/cve/__init__.py    |   3 +-
 framework/surprise/harness/cve/certify.py     | 401 +++++++++++++++++++++++-
 framework/surprise/harness/cve/criterion.py   | 386 +++++++++++++++++++++++
 framework/surprise/harness/cve/hypothesis.py  | 109 +++++++
 framework/surprise/harness/cve/tier3.py       | 361 +++++++++++++++++++++
 framework/surprise/harness/cve/worker.py      |  12 +
 framework/surprise/harness/evaluate.py        |  26 +-
 framework/surprise/harness/manifest.py        |   3 +-
 framework/tests/test_surprise_contracts.py    |   8 +
 framework/tests/test_surprise_s04_pipeline.py |  20 +-
 framework/tests/test_surprise_s04_tier23.py   | 435 ++++++++++++++++++++++++++
 12 files changed, 1746 insertions(+), 31 deletions(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，0m35s；passed 275，skipped 3

```text
........................ss..................................s........... [ 25%]
........................................................................ [ 51%]
........................................................................ [ 77%]
..............................................................           [100%]
275 passed, 3 skipped in 34.74s
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，3m43s

```text
S02 GATE: PASS (5/5 groups passed)
=== gate s03 ===
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
[PASS] local: ART exercised, injected mismatch caught; 3 proved rules x 2 engines incl NULL; untrusted pairs rejected
[PASS] cross: PG16 + DuckDB witness DF-A/DF-B; insufficient quorum, ties, multiple outliers and engine aliases rejected
[PASS] version: F2 old/new measured bags and regression direction; both old venvs work; directionless mismatch invalid
[PASS] matrix: 7 oracles x 2 engines, 14 ledger records, no hidden harness failures, manifest verified
S03 GATE: PASS (5/5 groups passed)
=== gate s04 ===
[PASS] contracts: 17 invalid sources, 7 CVE constants in the manifest; raw entry points untouched; 5 bad requests rejected before execution (1s)
[PASS] isolation: ok / error / timeout x2 / crash x2 told apart; 7 distinct processes for one candidate; process death, hang and dying reference contained (19s)
[PASS] tier1: 6 stable families fail after 5 fresh reruns; F8 unstable; F5 reproduced 0/5; 6 scripted rerun schedules (18s)
[PASS] premise: ASOF ties, writing statements and incomparable cross-engine values are invalid; their tie-free, crashing and comparable counterparts stay fail (13s)
[PASS] environment: 51 files hashed, 17 imported old modules all covered; old engines, PostgreSQL 16.15 and 5 packages recorded (0s)
[PASS] tier2: fix-set attribution: F1, F6, F6 via TLP consistent, F2 escalated; profile attribution: DF-A consistent, DF-B escalated; 5 malformed hypotheses rejected (21s)
[PASS] tier3: 9 confirmed cases profiled: fix sets as measured and as in recall_repros.json, version ladder, minimised subsequence; noise removed; lost candidate downgraded (36s)
[PASS] m1: 50 final labels in the ledger (14 fail, 20 invalid, 16 pass); known recall gaps: DF-E, DF-G, DF-H, DF-J, F10, F5 (58s)
[FAIL] freeze: s04_frozen.json is missing: the harness has not been frozen yet
S04 GATE: FAIL (8/9 groups passed)
=== summary ===
s01: PASS
s02: PASS
s03: PASS
s04: FAIL (exit 1)
GATES: FAIL (3/4 passed)
```

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- `framework/tests/test_surprise_s04_pipeline.py:764` 原：`with pytest.raises(NotImplementedError):` → 同一处新增：`with pytest.raises(ValueError):`
- `framework/tests/test_surprise_s04_pipeline.py:766` 原：`with pytest.raises(NotImplementedError):` → 同一处新增：`with pytest.raises(ValueError):`
- `framework/tests/test_surprise_s04_pipeline.py:811` 原：`with pytest.raises(NotImplementedError):` → 同一处新增：`with pytest.raises(ValueError):`

### 4.4 新增的宽泛异常捕获

- `framework/surprise/harness/cve/criterion.py:92` `except Exception:`
- `framework/surprise/harness/cve/criterion.py:257` `except Exception:`
- `framework/surprise/harness/cve/tier3.py:215` `except Exception:`
- `framework/surprise/harness/cve/tier3.py:271` `except Exception:`
- `framework/surprise/harness/cve/tier3.py:329` `except Exception as exc:`
- `framework/surprise/harness/cve/tier3.py:337` `except Exception as exc:`
- `framework/surprise/harness/cve/tier3.py:344` `except Exception:`

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s04-tier23.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 移动 `refs/heads/session/s04` f87373f56238 → d0cf13e229cc

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s04-tier23.jsonl`：10043 条事件（auto_compact_completed 2，auto_compact_failed 4，auto_compact_started 6，available_commands 173，end 2，orch.exit 2，orch.start 2，plan 4，text 1014，thought 7382，tool_call 321，tool_call_update 983，usage 148）；各轮合计 148 个模型回合，grok 上报花费 4.1868 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_update [completed]: exit: 0 warning: in the working copy of 'framework/surprise/harness/cve/tier3.py', LF will be replaced by CRLF the next time Git touches it [grok/s04-tier23 d081bc8] s04-tier23: r…
thought: 提交成功，工作区已清空。
tool_call search_replace: {"file_path": "D:\\CoevoDB\\.worktrees\\s04-tier23\\.orch\\report.md", "old_string": "`framework/tests/test_surprise_contracts.py` 的 `test_constants_collect_public_uppercase_names…
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "`framework/tests/test_surprise_contracts.py` 的 `test_constants_collect_public_uppercase_names`（约第 160 行）把 `as_dict()` 的键锁…
tool_call run_terminal_command: {"command": "Set-Location D:\\CoevoDB\\.worktrees\\s04-tier23; git status --short; git log -1 --oneline", "description": "Confirm the worktree is clean after the report update"}
tool_update [in_progress]: 
tool_update [in_progress]: d081bc8 s04-tier23: record tier-1 rejections and recheck minimised fails
tool_update [completed]: exit: 0 d081bc8 s04-tier23: record tier-1 rejections and recheck minimised fails
thought: Git 工作区干净，无未提交更改。 报告已提交并更新。审查意见返工完成，工作区干净。
text: 第 1 轮返工已提交到 `grok/s04-tier23`（`d081bc8`），工作区干净。`.orch/report.md` 保留了第一轮内容，并追加了「第 1 轮返工」。 四处改动： - 常数快照补上 `CVE_MINIMIZE_MAX_EXECUTIONS`、`CVE_BISECT_MAX_EXECUTIONS`、`CVE_ATTRIBUTION_…
end: stopReason=end_turn turns=32 cost_usd=0.64140524
orch.exit: {"pkg": "s04-tier23", "run": 2, "at": "2026-10-09T08:16:30+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
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
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：

合并。当前 HEAD d081bc8，返工 1 轮。

独立复跑（在该分支当前 HEAD 上）：pytest 275 passed / 3 skipped，退出码 0；S01 7/7、S02 5/5、S03 5/5；S04 八组 contracts、isolation、tier1、premise、environment、tier2、tier3、m1 全部通过，剩下的 freeze 一组由编排者在合并后做。

读完了首轮 11 个文件的完整 diff、返工 diff 和全部 23 条 shell 命令。worktree 干净，没有被 deny 规则拦下的调用，没有新增 skip / xfail，没有测试配置改动，没有链接或目录联接，.orch/tmp 没有被清理，日志与 diff 中没有密钥。旧代码与原始 oracle 层零改动。标签路径没有 LLM 调用：BugFixer._minimize 以普通函数方式调用，传入的对象只有 checker 属性；编排者把 BaseAgent 的构造函数和 httpx.Client 都换成会抛异常的桩之后，内联方式的第 3 档照常完成。

四项自动红旗的核对：
- 越界一处是 tests/test_surprise_contracts.py。首轮执行者没有改它，按规矩在报告的未决问题里停下；它失败是因为 as_dict 自动收进新常数，而编排者的说明漏放了这条断言。返工意见第 1 条明确放行，改动只有期望集合加四个名字和四句取值断言，仍是精确集合。
- 门槛未通过只因 freeze 组。
- 改写的断言三处都在本包上一个包建的测试里：原先断言第 2、3 档抛 NotImplementedError，本包让这两个参数生效，改为断言非法假设抛 ValueError，并新增 diagnose 对 pass 用例写一条第 0 档记录的断言。
- 七处宽泛捕获逐条看过：关闭 runner、版本梯取不到记 unknown、探测失败按前提违反处理，没有把失败写成通过。

门槛之外的独立探测（脚本在 .orch/scratch/s4_review_tier23.py，返工后重跑，57 项全部通过）：
- 归属测试十二组：F2 配自己的 fix set 一致；F1 配 F2 的 fix set、配 threads 不一致并升档；F1 只配 deliminator 一致；F11 配 build_side_probe_side 一致、配 F1 的 fix set 不一致；F9 配 F1 的 fix set 不一致；无开关的 DF-B、DF-I 按行为画像与错误类别判断，错误类别或失败类别不符即不一致。
- 九个确认用例最小化后的用例拿去做原始判定，仍是同一类 fail；F2 加两张无关表后只剩建表与一条 INSERT。
- 进程隔离下第 2、3 档调用方进程执行的语句数为 0。
- 八组两次 certify 的 to_dict 完全相同。
- 会杀死进程的候选要求第 3 档时两秒内返回，标签保持 fail，minimize 与 profile 记 skipped 及原因。

首轮发现并在返工中改掉的三处：第 1 档被拒后，被请求的后续步骤的跳过原因记成了 not_requested，现改为 tier1_rejected；带假设调用时干预名单重复查询，现按引擎缓存，三次调用只问子进程一次；最小化后的再验证改用原始判定并要求失败类别不变，编排者用一个删行后变成一侧溢出报错的假 runner 复测，结果是 invalid 加 not_reproduced_minimized。前两项已加入门槛。

实现选择，接受：画像直接调用 compute_fix_set 与 plan_diff_ops，没有经过 SignatureEngine.compute，其中宽 fix set 改判 pervasive 的三行规则照旧代码写了一遍；版本梯走 S3 的 version_worker，DataFusion 也按同一口径计算；归属与第 3 档各放进一个子进程，墙钟上限取常数。

两轮花费合计约 4.19 美元。
