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
