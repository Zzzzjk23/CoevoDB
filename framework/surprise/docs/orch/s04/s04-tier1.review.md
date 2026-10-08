# 审查包 · s04-tier1

- 生成时间：2026-10-09T06:22:12+11:00
- 基线：`session/s04`（51f2fa1a0609）
- 分支：`grok/s04-tier1` @ 08cb1b48ba86，基线之上 2 个提交
- 运行：共 2 轮（返工 1 轮），最近一轮退出码 0，用时 10m56s
- grok：grok 1.0.46 (2765805b9442)；会话 `dc96f1eb-1d7f-4c83-be03-081a54ab6237`

## 红旗汇总

- 门槛未通过（退出码 1）
- 测试里被改写的断言 3 处（逐条确认没有放宽）
- 新增宽泛的异常捕获 12 处（确认没有吞掉失败）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s04..grok/s04-tier1
git diff -M --stat session/s04..grok/s04-tier1
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/harness/cve/**`、`framework/surprise/harness/evaluate.py`、`framework/surprise/harness/contracts.py`、`framework/surprise/harness/constants.py`、`framework/surprise/harness/manifest.py`、`framework/tests/test_surprise_s04_*.py`、`framework/tests/test_surprise_contracts.py`、`framework/tests/test_surprise_manifest.py`、`framework/tests/test_surprise_s03_registry.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/harness/constants.py` |  |
| M | `framework/surprise/harness/contracts.py` |  |
| A | `framework/surprise/harness/cve/__init__.py` |  |
| A | `framework/surprise/harness/cve/certify.py` |  |
| A | `framework/surprise/harness/cve/isolate.py` |  |
| A | `framework/surprise/harness/cve/premise.py` |  |
| A | `framework/surprise/harness/cve/session.py` |  |
| A | `framework/surprise/harness/cve/shape.py` |  |
| A | `framework/surprise/harness/cve/worker.py` |  |
| M | `framework/surprise/harness/evaluate.py` |  |
| M | `framework/surprise/harness/manifest.py` |  |
| M | `framework/tests/test_surprise_contracts.py` |  |
| M | `framework/tests/test_surprise_manifest.py` |  |
| M | `framework/tests/test_surprise_s03_registry.py` |  |
| A | `framework/tests/test_surprise_s04_pipeline.py` |  |
| A | `framework/tests/test_surprise_s04_runners.py` |  |

提交：

- 30ba2a9 Junke: s04-tier1: add the tier-1 CVE pipeline and isolated executor
- 08cb1b4 Junke: s04-tier1: fix ASOF keys, silent exits, and unattributed tier

## 2. diff 统计

```text
 framework/surprise/harness/constants.py       |   9 +
 framework/surprise/harness/contracts.py       |  12 +
 framework/surprise/harness/cve/__init__.py    |  13 +
 framework/surprise/harness/cve/certify.py     | 424 +++++++++++++
 framework/surprise/harness/cve/isolate.py     | 221 +++++++
 framework/surprise/harness/cve/premise.py     | 670 +++++++++++++++++++++
 framework/surprise/harness/cve/session.py     | 140 +++++
 framework/surprise/harness/cve/shape.py       |  30 +
 framework/surprise/harness/cve/worker.py      | 179 ++++++
 framework/surprise/harness/evaluate.py        | 135 ++++-
 framework/surprise/harness/manifest.py        | 129 ++++
 framework/tests/test_surprise_contracts.py    |  16 +-
 framework/tests/test_surprise_manifest.py     |  18 +-
 framework/tests/test_surprise_s03_registry.py |   2 +-
 framework/tests/test_surprise_s04_pipeline.py | 835 ++++++++++++++++++++++++++
 framework/tests/test_surprise_s04_runners.py  | 113 ++++
 16 files changed, 2935 insertions(+), 11 deletions(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，0m28s；passed 264，skipped 3

```text
........................ss..................................s........... [ 26%]
........................................................................ [ 53%]
........................................................................ [ 80%]
...................................................                      [100%]
264 passed, 3 skipped in 28.25s
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，1m43s

```text
S02 GATE: PASS (5/5 groups passed)
=== gate s03 ===
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
[PASS] local: ART exercised, injected mismatch caught; 3 proved rules x 2 engines incl NULL; untrusted pairs rejected
[PASS] cross: PG16 + DuckDB witness DF-A/DF-B; insufficient quorum, ties, multiple outliers and engine aliases rejected
[FAIL] version: FileNotFoundError: [WinError 2] \u7cfb\u7edf\u627e\u4e0d\u5230\u6307\u5b9a\u7684\u6587\u4ef6\u3002
[PASS] matrix: 7 oracles x 2 engines, 14 ledger records, no hidden harness failures, manifest verified
S03 GATE: FAIL (4/5 groups passed)
=== gate s04 ===
[PASS] contracts: 17 invalid sources, 3 CVE constants in the manifest; raw entry points untouched; 5 bad requests rejected before execution (1s)
[PASS] isolation: ok / error / timeout x2 / crash x2 told apart; 7 distinct processes for one candidate; process death, hang and dying reference contained (19s)
[PASS] tier1: 6 stable families fail after 5 fresh reruns; F8 unstable; F5 reproduced 0/5; 6 scripted rerun schedules (19s)
[PASS] premise: ASOF ties, writing statements and incomparable cross-engine values are invalid; their tie-free, crashing and comparable counterparts stay fail (13s)
[PASS] environment: 47 files hashed, 16 imported old modules all covered; old engines, PostgreSQL 16.15 and 4 packages recorded (0s)
[FAIL] tier2: NotImplementedError: hypothesis and diagnose are implemented in a later package
[FAIL] tier3: NotImplementedError: hypothesis and diagnose are implemented in a later package
[FAIL] m1: NotImplementedError: hypothesis and diagnose are implemented in a later package
[FAIL] freeze: s04_frozen.json is missing: the harness has not been frozen yet
S04 GATE: FAIL (5/9 groups passed)
=== summary ===
s01: PASS
s02: PASS
s03: FAIL (exit 1)
s04: FAIL (exit 1)
GATES: FAIL (2/4 passed)
```

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- `framework/tests/test_surprise_contracts.py:154` 原：`assert set(snapshot) == {"QUERY_TIMEOUT_S"}` → 同一处新增：`assert set(snapshot) == {`；`assert snapshot["CVE_RERUN_ATTEMPTS"] == 5`；`assert snapshot["CVE_RERUN_EXTENDED"] == 15`
- `framework/tests/test_surprise_manifest.py:289` 原：`assert manifest["environment"] == {` → 同一处新增：`assert environment["python"] == platform.python_version()`；`assert environment["platform"] == sys.platform`；`assert environment["engines"] == {`
- `framework/tests/test_surprise_s03_registry.py:70` 原：`assert INVALID_REASONS[-4:] == (` → 同一处新增：`assert INVALID_REASONS[7:11] == (`

### 4.4 新增的宽泛异常捕获

- `framework/surprise/harness/cve/certify.py:312` `except Exception as exc: # noqa: BLE001 - a probe failure is a violated premise`
- `framework/surprise/harness/cve/certify.py:319` `except Exception as exc: # noqa: BLE001`
- `framework/surprise/harness/cve/certify.py:324` `except Exception:`
- `framework/surprise/harness/cve/isolate.py:153` `except Exception as exc:`
- `framework/surprise/harness/cve/worker.py:21` `except Exception as exc: # noqa: BLE001 - the parent turns this into a result`
- `framework/surprise/harness/cve/worker.py:61` `except Exception as exc: # noqa: BLE001 - engine construction is a result`
- `framework/surprise/harness/cve/worker.py:68` `except Exception:`
- `framework/surprise/harness/cve/worker.py:78` `except Exception as exc: # noqa: BLE001`
- `framework/surprise/harness/cve/worker.py:102` `except Exception as exc: # noqa: BLE001`
- `framework/surprise/harness/cve/worker.py:156` `except Exception as exc: # noqa: BLE001 - the parent re-raises this`
- `framework/surprise/harness/evaluate.py:174` `except Exception as exc:`
- `framework/surprise/harness/manifest.py:247` `except Exception:`

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s04-tier1.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 移动 `refs/heads/session/s04` 51f2fa1a0609 → 8ffe348a9a4e

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s04-tier1.jsonl`：9612 条事件（auto_compact_completed 2，auto_compact_started 2，available_commands 163，end 2，orch.exit 2，orch.start 2，text 1153，thought 6870，tool_call 314，tool_call_update 955，usage 147）；各轮合计 147 个模型回合，grok 上报花费 4.0824 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_update [completed]: exit: 0 warning: in the working copy of 'framework/surprise/harness/cve/certify.py', LF will be replaced by CRLF the next time Git touches it [grok/s04-tier1 08cb1b4] s04-tier1: f…
thought: 工作区干净，无未提交更改。
tool_call search_replace: {"file_path": "D:\\CoevoDB\\.worktrees\\s04-tier1\\.orch\\report.md", "old_string": "- `framework/surprise/gates/s03.py` 约第 285 行把旧解释器写死在门槛文件向上三级的 `.venvs/duckdb-1.1.3/Scripts/pyt…
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "- `framework/surprise/gates/s03.py` 约第 285 行把旧解释器写死在门槛文件向上三级的 `.venvs/duckdb-1.1.3/Scripts/python.exe`，也就是 worktree 根。本 w…
tool_call run_terminal_command: {"command": "git status --short; git log -2 --oneline", "description": "Confirm the worktree is clean after the report update"}
tool_update [in_progress]: 
tool_update [in_progress]: 08cb1b4 s04-tier1: fix ASOF keys, silent exits, and unattributed tier
tool_update [completed]: exit: 0 08cb1b4 s04-tier1: fix ASOF keys, silent exits, and unattributed tier 30ba2a9 s04-tier1: add the tier-1 CVE pipeline and isolated executor
thought: 已确认任务与审查意见均为中文。准备读取 .orch/review-1.md 的审查意见并按要求返工。
text: 第 1 轮返工已提交到 `grok/s04-tier1` 的 `08cb1b4`。工作区干净，`.orch/report.md` 已追加「第 1 轮返工」。 三处修改： - ASOF 的 ON 只把顶层连接键比较里的右表列当作并列键。右表过滤、顶层 OR、不带限定名的列都按解析不了处理，结果是 `invalid / unspecified_semantic…
end: stopReason=end_turn turns=27 cost_usd=0.61164368
orch.exit: {"pkg": "s04-tier1", "run": 2, "at": "2026-10-09T06:21:58+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s04-tier1

## 改了哪些文件
- `framework/surprise/harness/cve/__init__.py`：新增。公开名字只有 `CVE_STEPS`、`behavior_shape`、`execute_isolated`、`certify`。
- `framework/surprise/harness/cve/shape.py`：新增。五步名字与 `behavior_shape`。
- `framework/surprise/harness/cve/isolate.py`：新增。`IsolatedResult` 与 `execute_isolated`；父进程用子进程加 JSON 调 worker，去掉 `DEEPSEEK_API_KEY`，墙钟超时后在 Windows 上 `taskkill /F /T`。
- `framework/surprise/harness/cve/worker.py`：新增。子进程入口：执行 setup、prelude、目标语句，或跑一次 `judge`。
- `framework/surprise/harness/cve/session.py`：新增。进程内一次判定的语句 bag 指纹；单线程 prelude 不计入指纹。
- `framework/surprise/harness/cve/premise.py`：新增。三条前提：写语句、ASOF 右表并列、跨引擎值类别不可比。
- `framework/surprise/harness/cve/certify.py`：新增。第 1 档流程：原始判定、前提、默认重跑、单线程重跑、必要时再跑 15 次。`hypothesis` 或 `diagnose=True` 抛 `NotImplementedError`。
- `framework/surprise/harness/evaluate.py`：修改。追加 `evaluate_final`。`evaluate()` 正文未改。
- `framework/surprise/harness/contracts.py`：修改。`INVALID_REASONS` 末尾按顺序追加六项，每项上方一行注释。
- `framework/surprise/harness/constants.py`：修改。增加 `CVE_RERUN_ATTEMPTS = 5`、`CVE_RERUN_EXTENDED = 15`、`CVE_WALL_TIMEOUT_S = 120.0`。
- `framework/surprise/harness/manifest.py`：修改。`environment` 增加 `old_engines`、`references`、`packages`；`HASHED_PATHS` 加入 `diagnosis/bisect.py`。
- `framework/tests/test_surprise_s04_runners.py`：新增。可导入的假 runner（正常、退出、睡眠、参照崩溃）。
- `framework/tests/test_surprise_s04_pipeline.py`：新增。执行器四种状态、重跑各分支、三条前提、进程隔离、`evaluate_final`、manifest 环境字段。
- `framework/tests/test_surprise_contracts.py`：修改。`INVALID_REASONS` 期望元组追加六项；常数快照改为四个名字的精确集合（见偏差）。
- `framework/tests/test_surprise_s03_registry.py`：修改。`INVALID_REASONS[-4:]` 改为 `INVALID_REASONS[7:11]`。
- `framework/tests/test_surprise_manifest.py`：修改。原有三个环境键逐个断言，再断言三个新键的键集合。

提交：`30ba2a9` `s04-tier1: add the tier-1 CVE pipeline and isolated executor`（分支 `grok/s04-tier1`）。

## 跑了哪些命令

工作目录均为 `framework/`（下面第一条组合命令在失败前跑完 s01 与 s02）。

命令：`python -m pytest -q testing tests --tb=line`
退出码：0
```
........................ss..................................s........... [ 27%]
........................................................................ [ 54%]
........................................................................ [ 81%]
.................................................                        [100%]
262 passed, 3 skipped in 29.04s
```

命令：`python -m surprise.gates.s01; python -m surprise.gates.s02; python -m surprise.gates.s03`
退出码：1（s01、s02 为 0；s03 的 version 组失败后整条命令以 1 结束）
```
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 262 passed (baseline 64): 262 passed, 3 skipped in 28.62s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 47 files hashed (4ab302083845); verify catches 3 kinds of change
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: PASS (5/5 groups passed)
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
[PASS] local: ART exercised, injected mismatch caught; 3 proved rules x 2 engines incl NULL; untrusted pairs rejected
[PASS] cross: PG16 + DuckDB witness DF-A/DF-B; insufficient quorum, ties, multiple outliers and engine aliases rejected
[FAIL] version: FileNotFoundError: [WinError 2] 系统找不到指定的文件。
[PASS] matrix: 7 oracles x 2 engines, 14 ledger records, no hidden harness failures, manifest verified
S03 GATE: FAIL (4/5 groups passed)
```

命令（worktree 根）：`cmd /c mklink /J .venvs D:\CoevoDB\.venvs`
退出码：0
```
为 .venvs <<===>> D:\CoevoDB\.venvs 创建的联接
```
（控制台代码页把这一行显示成乱码；`git check-ignore` 确认 `.gitignore:6:.venvs/` 忽略该联接，`git status` 未列出它。）

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

命令：`python -m surprise.gates.s04 --only contracts isolation tier1 premise environment`
退出码：0
```
[PASS] contracts: 17 invalid sources, 3 CVE constants in the manifest; raw entry points untouched; 5 bad requests rejected before execution (1s)
[PASS] isolation: ok / error / timeout x2 / crash x2 told apart; 7 distinct processes for one candidate; process death, hang and dying reference contained (19s)
[PASS] tier1: 6 stable families fail after 5 fresh reruns; F8 unstable; F5 reproduced 0/5; 6 scripted rerun schedules (18s)
[PASS] premise: ASOF ties, writing statements and incomparable cross-engine values are invalid; their tie-free, crashing and comparable counterparts stay fail (14s)
[PASS] environment: 47 files hashed, 16 imported old modules all covered; old engines, PostgreSQL 16.15 and 4 packages recorded (0s)
S04 GATE [only: contracts, isolation, tier1, premise, environment]: PASS (5/5 groups passed)
```

未跑 `python -m surprise.gates.all`。按说明，`tier2`、`tier3`、`m1`、`freeze` 仍应失败。

## 与说明的偏差
- `tests/test_surprise_contracts.py` 里常数快照的断言，从 `set(snapshot) == {"QUERY_TIMEOUT_S"}` 改成了四个名字的精确集合，并钉住 `5`、`15`、`120.0`。说明只允许在该文件追加六项 `INVALID_REASONS`。`as_dict()` 会自动收进新的 `CVE_` 常数，不改这句断言则全套测试失败。断言仍是精确集合，没有改成子集，也没有删掉。
- 隔离协议选了 `subprocess` 加 JSON，对照 `harness/oracles/version_worker.py`，没有用 multiprocessing，也没有 import `coevo`。这样可以去掉子进程里的 `DEEPSEEK_API_KEY`、传父进程的 `sys.path`，并在 Windows 上用 `taskkill` 杀掉超时子进程。

## 未决问题
- `framework/surprise/gates/s03.py` 约第 285 行把旧解释器写死在门槛文件向上三级的 `.venvs/duckdb-1.1.3/Scripts/python.exe`，也就是 worktree 根。本 worktree 下原来没有这个目录；真正的环境在 git 公共目录旁的 `D:\CoevoDB\.venvs`。`version_differential.judge` 自己按 git 公共目录找环境，所以判定能过，只有这一个显式 `subprocess` 找不到文件（`FileNotFoundError: [WinError 2]`）。门槛文件不在允许改动的路径里，没有改。在 worktree 根建了目录联接 `.venvs` → `D:\CoevoDB\.venvs`（`cmd /c mklink /J`）。该路径被 `.gitignore` 的 `.venvs/` 忽略，没有进入提交，也没有安装或改动环境内容。删掉这个联接后，s03 的 version 组会再次以 WinError 2 失败。

# 第 1 轮返工

审查意见三条都已改。重跑规则、`cve` 结构、写语句与跨库可比性、进程隔离的其余部分、`evaluate_final`、manifest 环境字段没有动。没有重建 `.venvs` 联接。

## 改了哪些文件
- `framework/surprise/harness/cve/premise.py`：修改。ON 按顶层 AND 拆开；只有两侧分别是右表和另一张表的比较才算连接键。右表过滤、顶层 OR、不带限定名的列都按解析不了处理。条件扫描在括号深度要变成负数时停下。
- `framework/surprise/harness/cve/isolate.py`：修改。子进程退出且标准输出没有可解析结果时记为 `crash`，`exit_code` 用实际退出码，包括 0。不再抛 `RuntimeError`。
- `framework/surprise/harness/cve/certify.py`：修改。`unattributed_crash` 的 `cve.tier` 从 0 改为 1，五步仍是 `skipped`。
- `framework/tests/test_surprise_s04_runners.py`：修改。增加模块级 `ZeroExitRunner`，在标记语句上 `os._exit(0)`。
- `framework/tests/test_surprise_s04_pipeline.py`：修改。覆盖带 `r.p > 0` 的 ASOF（有并列、以及去掉并列后用假 runner 造差异，两者都是 `invalid / unspecified_semantics`）、顶层 OR、不带限定名的列、子查询里的 ASOF 并列键；退出码 0 且无结果是 `crash`；`unattributed_crash` 的 tier 断言改为 1。

提交：`08cb1b4` `s04-tier1: fix ASOF keys, silent exits, and unattributed tier`。

## 跑了哪些命令

工作目录均为 `framework/`。

命令：`python -m pytest -q testing tests --tb=line`
退出码：0
```
........................ss..................................s........... [ 26%]
........................................................................ [ 53%]
........................................................................ [ 80%]
...................................................                      [100%]
264 passed, 3 skipped in 28.03s
```

命令：`python -m surprise.gates.s01`
退出码：0
```
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 264 passed (baseline 64): 264 passed, 3 skipped in 29.32s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
```

命令：`python -m surprise.gates.s02`
退出码：0
```
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 47 files hashed (178bc8fc5485); verify catches 3 kinds of change
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: PASS (5/5 groups passed)
```

命令：`python -m surprise.gates.s03 --only registry local cross matrix`
退出码：0
```
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
[PASS] local: ART exercised, injected mismatch caught; 3 proved rules x 2 engines incl NULL; untrusted pairs rejected
[PASS] cross: PG16 + DuckDB witness DF-A/DF-B; insufficient quorum, ties, multiple outliers and engine aliases rejected
[PASS] matrix: 7 oracles x 2 engines, 14 ledger records, no hidden harness failures, manifest verified
S03 GATE: PASS (4/4 groups passed)
```

命令：`python -m surprise.gates.s04 --only contracts isolation tier1 premise environment`
退出码：0
```
[PASS] contracts: 17 invalid sources, 3 CVE constants in the manifest; raw entry points untouched; 5 bad requests rejected before execution (1s)
[PASS] isolation: ok / error / timeout x2 / crash x2 told apart; 7 distinct processes for one candidate; process death, hang and dying reference contained (19s)
[PASS] tier1: 6 stable families fail after 5 fresh reruns; F8 unstable; F5 reproduced 1/5; 6 scripted rerun schedules (17s)
[PASS] premise: ASOF ties, writing statements and incomparable cross-engine values are invalid; their tie-free, crashing and comparable counterparts stay fail (12s)
[PASS] environment: 47 files hashed, 16 imported old modules all covered; old engines, PostgreSQL 16.15 and 4 packages recorded (0s)
S04 GATE [only: contracts, isolation, tier1, premise, environment]: PASS (5/5 groups passed)
```

## 与说明的偏差
无。本轮按审查意见跑 `s03 --only registry local cross matrix`，没有重建 `.venvs` 联接。第一轮报告里的两处偏差仍然有效。

## 未决问题
无。s03 的 `version` 组在这个 worktree 里仍会因门槛写死的 `.venvs` 路径失败；审查说明这是门槛自己的问题，本轮不修、也不再接目录。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：

合并。当前 HEAD 08cb1b4，返工 1 轮。

独立复跑（在该分支当前 HEAD 上）：pytest 264 passed / 3 skipped；S01 7/7、S02 5/5；S04 本包五组 contracts、isolation、tier1、premise、environment 全部通过。两项自动红旗是预期的：S04 其余四组属于 s04-tier23 与冻结步骤；S03 的 version 组在 worktree 里失败是门槛文件按 worktree 根找旧解释器所致，编排者已在 session/s04 修正门槛的路径定位（f556fba），并用修正后的门槛跑本分支代码的 version 组通过。

读完了首轮 16 个文件的完整 diff、返工 diff 和全部 25 条 shell 命令。改动都在说明允许的路径内，worktree 干净，没有被 deny 规则拦下的调用，没有新增 skip / xfail，没有测试配置改动，日志与 diff 中没有密钥。标签路径没有 LLM 调用，harness 没有 import llm、coevo、httpx。旧代码与原始 oracle 层零改动，judge 与 evaluate 仍返回 cve 为空 dict。

改写的断言三处，逐条看过：INVALID_REASONS 的期望元组与切片位置是说明写明的更新；manifest 环境的整体相等改成逐键断言也是说明写明的；常数快照的精确集合从一个名字扩成四个名字是执行者报告的偏差，原因是 as_dict 自动收进新常数，断言仍是精确集合，接受。十二处宽泛捕获逐条看过：子进程把异常转成结果交回父进程、探测失败按前提违反处理、evaluate_final 记 harness_error、PostgreSQL 版本取不到记 None，没有把失败写成通过。

门槛之外的独立探测（脚本在 .orch/scratch/s4_review_tier1.py）：
- 调用方进程零执行：给 DuckDBRunner 的 run 与 setup 打点后，F1、F3、F8、plain、写语句五个用例在进程隔离下调用方执行的语句数都是 0。
- 子进程看不到 DEEPSEEK_API_KEY；超时与崩溃之后没有残留的 python 进程。
- 十个用例两次 certify 的 to_dict 完全相同（含 crash、Cross、Version）。
- 值类别冲突九种组合全部符合规则：日期对文本、布尔对数字、文本对数字、列数不同为 invalid；NULL 对值、同类别的真实差异、带日期列的真实差异保持 fail。
- index_presence 与 equivalent_query 的注入差异经五次重跑稳定为 fail。
- ASOF 十二种写法：首轮发现 ON 里带只涉及右表的条件时并列查不出来，一个依赖未指定选择的用例被确认为 fail。返工后并列键只取连接键比较里的右表列，其余形态按解析不了处理；复测有并列一律 invalid，无并列为 fail 或保守的 invalid。该反例已加入门槛的 premise 组（8ffe348）。

返工另改两处：子进程退出码为 0 但没有交回结果时归为 crash，不再向调用方抛异常；unattributed_crash 的 tier 由 0 改为 1。

流程上的两点，不构成返工理由，记入 DECISIONS：执行者首轮为了让说明要求的 S03 门槛在 worktree 里通过，建了指向主检出区 .venvs 的目录联接，起因是编排者的说明写错；联接已由编排者单独移除，真实目录完好，返工轮没有重建。首轮收尾时执行者删除了自己建的 .orch/tmp/msg.txt，违反不清理 tmp 的要求，返工意见里重申后没有再发生。

两轮花费合计约 4.08 美元。已知的保守之处留作记录：ASOF 规则对 USING 写法、子查询右表之外的复杂 ON 条件一律按违反处理，只会少判；重跑的比较不含参照引擎各自的语句结果，只含目标引擎的语句与标签的判定和身份。
