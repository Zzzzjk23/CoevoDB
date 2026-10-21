# 审查包 · s16-core

- 生成时间：2026-10-22T00:46:49+11:00
- 基线：`session/s16`（572cad1e0d7b）
- 分支：`grok/s16-core` @ f8a24dc281a1，基线之上 2 个提交
- 运行：共 2 轮（返工 1 轮），最近一轮退出码 0，用时 15m36s
- 执行者：codex codex-cli 0.163.0；会话 `01a15e91-d919-7830-86ed-4ced9af38c37`

## 红旗汇总

- 改动了禁区路径 2 处：framework/surprise/harness/oracles/pg_target.py, framework/surprise/harness/oracles/registry.py
- 本次审查包没有复跑测试（--skip-tests）
- 新增宽泛的异常捕获 5 处（确认没有吞掉失败）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s16..grok/s16-core
git diff -M --stat session/s16..grok/s16-core
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/experiments/pg_instance.py`、`framework/surprise/harness/oracles/pg_target.py`、`framework/surprise/harness/oracles/registry.py`、`framework/tests/test_surprise_s16_instance.py`、`framework/tests/test_surprise_s16_target.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| A | `framework/surprise/experiments/pg_instance.py` |  |
| A | `framework/surprise/harness/oracles/pg_target.py` | **越界：禁区** |
| M | `framework/surprise/harness/oracles/registry.py` | **越界：禁区** |
| A | `framework/tests/test_surprise_s16_instance.py` |  |
| A | `framework/tests/test_surprise_s16_target.py` |  |

提交：

- 51aa1cd Junke: Add per-run PostgreSQL instances and S16 target runner
- f8a24dc Junke: Handle PostgreSQL target availability and recovery cleanup

## 2. diff 统计

```text
 framework/surprise/experiments/pg_instance.py   | 331 +++++++++++++++++++++
 framework/surprise/harness/oracles/pg_target.py | 278 ++++++++++++++++++
 framework/surprise/harness/oracles/registry.py  |  14 +-
 framework/tests/test_surprise_s16_instance.py   | 156 ++++++++++
 framework/tests/test_surprise_s16_target.py     | 372 ++++++++++++++++++++++++
 5 files changed, 1150 insertions(+), 1 deletion(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

按 `--skip-tests` 跳过了 pytest 与门槛。

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- 无

### 4.4 新增的宽泛异常捕获

- `framework/surprise/experiments/pg_instance.py:221` `except BaseException:`
- `framework/surprise/experiments/pg_instance.py:325` `except Exception as exc:`
- `framework/surprise/harness/oracles/pg_target.py:146` `except Exception:`
- `framework/surprise/harness/oracles/pg_target.py:183` `except Exception:`
- `framework/surprise/harness/oracles/pg_target.py:249` `except Exception as exc: # Engine/transport failures are QueryResult data.`

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s16-core.jsonl` 与 stderr 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 新增 `refs/heads/grok/s16-replay` @ 8bf6292d7b87
- 新增 `refs/heads/grok/s16-roles-b` @ 890fe4df5db4
- 移动 `refs/heads/session/s16` 572cad1e0d7b → 8ab99630f9fe

主检出区当前未提交的改动（`git status --porcelain`）：

```text
 M framework/surprise/docs/HANDOFF.md
```

## 6. 执行日志摘要

`.orch/logs/s16-core.jsonl`：130 条事件（item.completed 71，item.started 49，orch.exit 2，orch.start 2，thread.started 2，turn.completed 2，turn.started 2）；各轮合计 codex：2 轮，输入 12807268 token（其中缓存 12560768），输出 90112（其中推理 39379），codex 不报美元。

被 deny 规则（grok）或 execpolicy 规则（codex，记在 stderr）拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$s16Passfiles = @(Get-ChildItem -LiteralPath .orch/tmp -Filter pgpass -Recurse -File -ErrorAction Silent…
exec [exit 0]: local-passfiles=0 local-postmaster-pids=0 postgres-processes=16 ProcessId : 20176 CommandLine : "D:/CoevoDB/.orch/pg16/binaries/pgsql/bin/postgres.exe" -D "D:/CoevoDB/.orch/pg16/d…
text: 最终结果为 1276 通过、2 失败、3 跳过，失败正是审查要求保留的两项；定向 78 项全部通过。临时目录中 passfile 和 PID 文件均为 0，剩余 PG 实例与任务开始前一致。现在提交返工，并更新报告记录 S16 门槛冲突。
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git commit -m "Handle PostgreSQL target availability and recovery cleanup"; git status --short; git rev-…
exec [exit 0]: [grok/s16-core f8a24dc] Handle PostgreSQL target availability and recovery cleanup 3 files changed, 251 insertions(+), 21 deletions(-) f8a24dc281a191d23f48df40bf0d5e99a66b465c
file_change [completed]: delete D:\CoevoDB\.claude\worktrees\s16\.worktrees\s16-core\.orch\report.md
file_change [completed]: add D:\CoevoDB\.claude\worktrees\s16\.worktrees\s16-core\.orch\report.md
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short; git check-ignore .orch/report.md; git log -1 --oneline; Get-Item -LiteralPath .orch/…
exec [exit 0]: .orch/report.md f8a24dc Handle PostgreSQL target availability and recovery cleanup Length ------ 16047
text: 已按三项审查意见返工并提交 `f8a24dc`，工作区干净，报告已更新。 - 定向测试：78 通过。 - 全套：1276 通过、2 项已知失败、3 跳过。 - S03、S05 通过；S04 仅预期 freeze 失败。 - S16：2/3 通过。registry 门槛在启动实例前调用工厂，与新的缺 DSN 行为冲突；按 brief 保留门槛并交接。 详情见…
end: tokens in=8768528 cached=8619648 out=57124 reasoning=26920
orch.exit: {"pkg": "s16-core", "run": 2, "at": "2026-10-22T00:46:18+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s16-core（第 1 轮审查返工）

本轮提交：`f8a24dc281a191d23f48df40bf0d5e99a66b465c`，分支 `grok/s16-core`。上一轮提交为 `51aa1cd15a7b1dcab71b8747e471f3d0cbf925f5`。提交后工作区干净，本报告不入库。

三项审查修改已实现。最终完整测试 **2 failed, 1276 passed, 3 skipped**，仅剩审查明确要求保留的两项既有失败；定向 **78 passed**。S03 / S05 全部通过，S04 只有预期 freeze 失败。S16 的 instances / runner 通过，但 registry 的既有门槛在建立实例前调用工厂，与本轮缺 DSN 时抛 ValueError 的要求冲突，因此原验收命令为 **FAIL (2/3)**。按 brief 的既有门槛禁止修改与停止规则，记录后交接。

## 改了哪些文件

本轮仅修改以下 3 个允许路径；实例管理器与实例测试保持上一轮实现，仍参加全部验收。

- `framework/surprise/harness/oracles/registry.py`：未设置或设置空的 `COEVO_TARGET_PG_DSN` 时，postgres 默认工厂抛 `ValueError`，消息只说明变量和实例管理模块；有值时返回 `PostgresTargetRunner`。目标列表保持三个，参照列表不变。
- `framework/surprise/harness/oracles/pg_target.py`：连接失败最多重试约 30 秒，间隔 0.5 秒，单次 connect_timeout 按剩余预算限制（上限 10 秒）；恢复后保留 options、autocommit 与原私有 schema。close 尽力删 schema，必要时重连，无法清理时交由每格实例清理；关闭连接失败也不向 oracle finally 抛异常，最终清空本地连接 / schema 引用。
- `framework/tests/test_surprise_s16_target.py`：新增 15 项测试，覆盖工厂缺失 / 空 DSN / 配置后的返回值、恢复中多次失败后真实重连、options 与 schema 恢复、30 秒预算耗尽、单次连接占用预算、永久认证失败不重试，以及已识别 / 尚未识别的后端丢失下 close 不抛、底层 close 失败不抛。恢复故障和时间按审查允许 monkeypatch；SQL、schema 与后端终止继续使用真实 PostgreSQL。累计新增测试 73 项均通过。

认证错误的实现选择：SQLSTATE 的 28 类，以及包含 authentication failed / no password supplied / no pg_hba.conf entry / pg_hba.conf rejects connection 的 OperationalError，立即抛出、不等待重试。凭据或认证规则不变时等待不会恢复；其他 OperationalError（包括 recovery mode、starting up、Connection refused）在 30 秒预算内重试。此选择按 review-1 第 3 条授权作出，未写 docs / DECISIONS。

## 跑了哪些命令

pytest / Python 验收在 `framework/` 执行，git 与最终 PowerShell 检查在 worktree 根执行。以下保存每条验证命令的退出码和输出末 20 行。

### 新测试与指定的五项旧测试逐项验证

命令：

```powershell
python -m pytest -q tests/test_surprise_s16_instance.py tests/test_surprise_s16_target.py tests/test_surprise_s03_registry.py::test_runner_factory_for_maps_target_engines tests/test_surprise_s05_dynamic.py::test_ast_only_skips_the_runner_even_without_one tests/test_surprise_s05_dynamic.py::test_extract_isolated_raises_caller_errors tests/test_surprise_s05_dynamic.py::test_phi_command_prints_canonical_json_and_rejects_bad_input tests/test_surprise_s05_dynamic.py::test_corpus_command_is_stable_on_a_small_corpus
```

退出码：0。输出末 20 行（不足 20 行则全部列出）：

```text
........................................................................ [ 92%]
......                                                                   [100%]
78 passed in 69.14s (0:01:09)
```

定向命令显式选择了 review-1 点名的五个既有测试：factory_for、ast-only、extract_isolated caller errors、phi CLI、corpus CLI；全部通过。78 项 = 原新增 58 项 + 本轮新增 15 项 + 五项既有测试。

### 完整 pytest 套件

命令：

```powershell
pytest -q testing tests
```

退出码：1。输出末 20 行（不足 20 行则全部列出）：

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
2 failed, 1276 passed, 3 skipped in 533.94s (0:08:53)
```

### S03 门槛

命令：

```powershell
python -m surprise.gates.s03
```

退出码：0。输出末 20 行（不足 20 行则全部列出）：

```text
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
[PASS] local: ART exercised, injected mismatch caught; 3 proved rules x 2 engines incl NULL; untrusted pairs rejected
[PASS] cross: PG16 + DuckDB witness DF-A/DF-B; insufficient quorum, ties, multiple outliers and engine aliases rejected
[PASS] version: F2 old/new measured bags and regression direction; both old venvs work; directionless mismatch invalid
[PASS] matrix: 7 oracles x 2 engines, 14 ledger records, no hidden harness failures, manifest verified
S03 GATE: PASS (5/5 groups passed)
```

### S05 门槛

命令：

```powershell
python -m surprise.gates.s05
```

退出码：0。输出末 20 行（不足 20 行则全部列出）：

```text
[PASS] vocab: 166 core entries (131 leaves) with hierarchy; open families; digest 1e001c14a030 stable across processes; invented feature registered, 8 bad ones rejected, saved and loaded; phi container (1s)
[PASS] spec: 12 hand-written phi / spec pairs judged as expected; 3 malformed specs rejected (0s)
[PASS] units: 23 hand-written feature sets project onto the expected units (0s)
[PASS] ast: 74 probes, 5 fallbacks, 3 invariance pairs; 12 families show their core features and are pairwise distinct (66 pairs) (0s)
[PASS] dynamic: 13 data probes on two engines, 6 measured plans; failing setup, ast-only and isolated extraction behave (3s)
[PASS] stable: 25 cases (12 families, 13 corpus seeds): two processes and this one agree (23s)
[PASS] distinguish: 12 families: pairwise distinct by statement text alone (66 pairs) and by phi; DF-A -> DF-B is one sibling swap; 11 measured units (0s)
[PASS] specs: 17 hand-written spec / SQL pairs, all judged correctly (0s)
[PASS] corpus: 1092 seeds in 76 units over 10 constructs; ast fallback 34, plan ok 480, data ok 483; top [('postgres|plain|none|unknown', 134), ('duckdb|plain|none|unknown', 83), ('duckdb|window|none|unknown', 56)]; 16s (34s)
S05 GATE: PASS (9/9 groups passed)
```

### S16 三组门槛

命令：

```powershell
python -m surprise.gates.s16 --only instances runner registry
```

退出码：1。输出末 20 行（不足 20 行则全部列出）：

```text
[PASS] instances: 16.15 and 15.19 from D:\CoevoDB\.orch\pg16\binaries\pgsql\bin / D:\CoevoDB\.orch\pg15\binaries\pgsql\bin; settings, locale and the non-superuser role as pinned; DSNs exported and restored; stop_all and the check CLI work (42s)
[PASS] runner: private schemas, refused statements, no superuser powers, timeout, a lost backend, setup SETs as session defaults, stable error text, schemas dropped on close; old runner on 15.19 (13s)
[FAIL] registry: ValueError: postgres: set COEVO_TARGET_PG_DSN using surprise.experiments.pg_instance before requesting a default runner
S16 GATE [only: instances, runner, registry]: FAIL (2/3 groups passed)
```

### S04 门槛

命令：

```powershell
python -m surprise.gates.s04
```

退出码：1。输出末 20 行（不足 20 行则全部列出）：

```text
[PASS] contracts: 17 invalid sources, 7 CVE constants in the manifest; raw entry points untouched; 5 bad requests rejected before execution (1s)
[PASS] isolation: ok / error / timeout x2 / crash x2 told apart; 7 distinct processes for one candidate; process death, hang and dying reference contained (24s)
[PASS] tier1: 6 stable families fail after 5 fresh reruns; F8 unstable; F5 reproduced 1/5; 6 scripted rerun schedules (24s)
[PASS] premise: ASOF ties, writing statements and incomparable cross-engine values are invalid; their tie-free, crashing and comparable counterparts stay fail (18s)
[PASS] environment: 52 files hashed, 17 imported old modules all covered; old engines, PostgreSQL 16.15 and 5 packages recorded (0s)
[PASS] tier2: fix-set attribution: F1, F6, F6 via TLP consistent, F2 escalated; profile attribution: DF-A consistent, DF-B escalated; 5 malformed hypotheses rejected (28s)
[PASS] tier3: 9 confirmed cases profiled: fix sets as measured and as in recall_repros.json, version ladder, minimised subsequence; noise removed; lost candidate downgraded (47s)
[PASS] m1: 50 final labels in the ledger (14 fail, 20 invalid, 16 pass); known recall gaps: DF-E, DF-G, DF-H, DF-J, F10, F5 (82s)
[FAIL] freeze: the harness changed after the freeze: ['added: surprise/harness/oracles/pg_target.py', 'changed: surprise/harness/oracles/registry.py', 'hash mismatch: manifest 98b70d9e81fc current c05a1af28a8c']
S04 GATE: FAIL (8/9 groups passed)
```

### 双版本实例 check CLI

命令：

```powershell
python -m surprise.experiments.pg_instance check
```

退出码：0。输出末 20 行（不足 20 行则全部列出）：

```text
target 16.15 port=9179
old 15.19 port=8709
```

### 清理 S16 stop_all 门槛保留的临时数据与 passfile

命令：

```powershell
python -c "from pathlib import Path; import tempfile; from surprise.experiments import pg_instance as P; root = Path(tempfile.gettempdir()) / 'coevo-s16-gate' / 'instances-leftover' / 'target'; assert root.is_relative_to(Path(tempfile.gettempdir())); P.stop_all(root); instance = P.PgInstance(root); instance.remove(); print('gate-leftover: data=' + str(instance.data_dir.exists()) + ' passfile=' + str(instance.passfile.exists()))"
```

退出码：0。输出末 20 行（不足 20 行则全部列出）：

```text
gate-leftover: data=False passfile=False
```

门槛 stop_all 场景的临时实例已停止；上述清理只删除指定临时实例的 data / pgpass，保留 server.log / instance.json。

### 暂存与差异检查

命令：

```powershell
git add -- framework/surprise/harness/oracles/pg_target.py framework/surprise/harness/oracles/registry.py framework/tests/test_surprise_s16_target.py; git diff --cached --check; git diff --cached --stat
```

退出码：0。输出末 20 行（不足 20 行则全部列出）：

```text
warning: in the working copy of 'framework/surprise/harness/oracles/pg_target.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'framework/tests/test_surprise_s16_target.py', LF will be replaced by CRLF the next time Git touches it
 framework/surprise/harness/oracles/pg_target.py |  79 +++++++---
 framework/surprise/harness/oracles/registry.py  |  10 +-
 framework/tests/test_surprise_s16_target.py     | 183 ++++++++++++++++++++++++
 3 files changed, 251 insertions(+), 21 deletions(-)
```

### 最终临时文件、进程与工作区检查

命令：

```powershell
$s16Passfiles = @(Get-ChildItem -LiteralPath .orch/tmp -Filter pgpass -Recurse -File -ErrorAction SilentlyContinue); $s16Pidfiles = @(Get-ChildItem -LiteralPath .orch/tmp -Filter postmaster.pid -Recurse -File -ErrorAction SilentlyContinue); Write-Output ('local-passfiles=' + $s16Passfiles.Count + ' local-postmaster-pids=' + $s16Pidfiles.Count); $s16Processes = @(Get-CimInstance Win32_Process -Filter "name = 'postgres.exe'"); Write-Output ('postgres-processes=' + $s16Processes.Count); $s16Processes | Where-Object { $_.CommandLine -match '\s-D\s' } | Select-Object ProcessId,CommandLine | Format-List; git diff --cached --check; git status --short
```

退出码：0。输出末 20 行（不足 20 行则全部列出）：

```text
local-passfiles=0 local-postmaster-pids=0
postgres-processes=16


ProcessId   : 20176
CommandLine : "D:/CoevoDB/.orch/pg16/binaries/pgsql/bin/postgres.exe"  -D "D:/CoevoDB/.orch/pg16/data" -h 127.0.0.1 -p 
              55432 

ProcessId   : 135492
CommandLine : D:\CoevoDB\.orch\pg16\binaries\pgsql\bin\postgres -D C:\Users\91484\.claude\jobs\ad2552c8\tmp\pg\p16\data

ProcessId   : 139672
CommandLine : D:\CoevoDB\.orch\pg15\binaries\pgsql\bin\postgres -D C:\Users\91484\.claude\jobs\ad2552c8\tmp\pg\p15\data



M  framework/surprise/harness/oracles/pg_target.py
M  framework/surprise/harness/oracles/registry.py
M  framework/tests/test_surprise_s16_target.py
```

最终检查的完整输出开头为 `local-passfiles=0 local-postmaster-pids=0`、`postgres-processes=16`。仅有任务开始前已存在的三个 postmaster 主进程：端口 55432 参照实例 PID 20176，及其他任务目录中的 PID 135492 / 139672；连同子进程总数与任务开始前一致。本包没有留下 PG 服务器、passfile 或 postmaster.pid，未停止或修改其他任务的实例。

### 提交返工

命令：

```powershell
git commit -m "Handle PostgreSQL target availability and recovery cleanup"; git status --short; git rev-parse HEAD
```

退出码：0。输出末 20 行（不足 20 行则全部列出）：

```text
[grok/s16-core f8a24dc] Handle PostgreSQL target availability and recovery cleanup
 3 files changed, 251 insertions(+), 21 deletions(-)
f8a24dc281a191d23f48df40bf0d5e99a66b465c
```

## 与说明的偏差

- 完整测试仅剩两项 review-1 明确要求保留的失败（旧 TARGET_ENGINES 二元组断言、遍历全部目标却没有 PG 实例）；既有测试、conftest、skip / xfail 均未修改。其余 **1276 passed, 3 skipped**，本轮无额外 pytest 失败。
- 新发现的 S16 门槛冲突：`framework/surprise/gates/s16.py:379` 在没有 `COEVO_TARGET_PG_DSN` 时要求 postgres 工厂直接返回类，而实例上下文直到第 386 行才建立。review-1 第 1 条明确要求此时抛 ValueError。因此原命令 registry 组失败，instances / runner 均通过。门槛不在允许改动路径内，遵照 brief 停止规则保留现状、记录并交接；未扩大实现范围。
- S04 **8/9**，仅 freeze 组失败，属于原说明允许的差异；冻结清单由编排者更新。
- 系统中两个其他任务的 PG 实例在本轮开始前已经存在，位于本 worktree 之外，未触碰；本包运行清理已核对完成。

## 未决问题

1. **新阻塞：S16 registry 门槛的实例前置条件。** `framework/surprise/gates/s16.py:379` 的工厂映射检查早于第 386 行的 `with instances("registry", old=False)`。需编排者协调门槛与 review-1 的缺 DSN 行为（例如把该检查放进既有实例上下文）；本包不能修改 gates。按 brief「其中某个测试确实该改，就写进报告的未决问题，停下」处理，未自行修门槛。
2. **审查已确认保留：** `framework/tests/test_surprise_s03_registry.py:68` 的 `test_implemented_is_the_seven_plan_ids` 仍断言目标列表只有 duckdb / datafusion。S16 的目标列表按要求保持三个，此测试未改，交编排者处理。
3. **审查已确认保留：** `framework/tests/test_surprise_s03_registry.py:181` 的 `test_sound_oracles_pass_on_both_target_engines` 遍历全部目标但没有临时 PG 实例 / DSN；现在按审查要求由工厂抛 ValueError。此测试未改，交编排者处理。
4. S04 冻结清单重写仍由编排者处理（已知项）。

未修改 gates / docs / conftest / 旧代码；未连接实验服务器，未打 tag、合并、rebase、push 或切换分支。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：
