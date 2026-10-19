# 审查包 · s15-sqlancer

- 生成时间：2026-10-19T18:27:49+11:00
- 基线：`session/s15`（33b4cd336536）
- 分支：`grok/s15-sqlancer` @ 7f7945b67688，基线之上 2 个提交
- 运行：共 2 轮（返工 1 轮），最近一轮退出码 0，用时 18m45s
- 执行者：codex codex-cli 0.163.0；会话 `01a152f6-cc0b-73d0-bdef-104dc5ee04ff`

## 红旗汇总

- 门槛未通过（退出码 1）
- 新增宽泛的异常捕获 3 处（确认没有吞掉失败）
- 派发以来有 1 处 tag 变化或 ref 被删：确认是编排者自己做的，不是执行者

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s15..grok/s15-sqlancer
git diff -M --stat session/s15..grok/s15-sqlancer
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/baselines/sqlancer_run.py`、`framework/surprise/metrics/report.py`、`framework/tests/test_surprise_s15_sqlancer.py`、`framework/tests/data/sqlancer/**`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| A | `framework/surprise/baselines/sqlancer_run.py` |  |
| M | `framework/surprise/metrics/report.py` |  |
| A | `framework/tests/data/sqlancer/norec_join.log` |  |
| A | `framework/tests/data/sqlancer/norec_mismatch.log` |  |
| A | `framework/tests/data/sqlancer/tlp_mismatch.log` |  |
| A | `framework/tests/data/sqlancer/tool_error_sqlexception.log` |  |
| A | `framework/tests/data/sqlancer/tool_error_unsupported.log` |  |
| A | `framework/tests/data/sqlancer/unexpected_error_ddl.log` |  |
| A | `framework/tests/data/sqlancer/unexpected_error_select.log` |  |
| A | `framework/tests/test_surprise_s15_sqlancer.py` |  |

提交：

- abbc3e8 Junke: Add SQLancer runner and report cells; record blocked test verification
- 7f7945b Junke: Fix SQLancer replay process guards and null command metadata

## 2. diff 统计

```text
 framework/surprise/baselines/sqlancer_run.py       | 442 +++++++++++++++++++++
 framework/surprise/metrics/report.py               |   8 +-
 framework/tests/data/sqlancer/norec_join.log       |  10 +
 framework/tests/data/sqlancer/norec_mismatch.log   |  24 ++
 framework/tests/data/sqlancer/tlp_mismatch.log     |  11 +
 .../data/sqlancer/tool_error_sqlexception.log      |  27 ++
 .../tests/data/sqlancer/tool_error_unsupported.log |  69 ++++
 .../tests/data/sqlancer/unexpected_error_ddl.log   |  45 +++
 .../data/sqlancer/unexpected_error_select.log      |  10 +
 framework/tests/test_surprise_s15_sqlancer.py      | 244 ++++++++++++
 10 files changed, 886 insertions(+), 4 deletions(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，6m24s；passed 1043，skipped 3

```text
........................ss..................................s........... [  6%]
........................................................................ [ 13%]
........................................................................ [ 20%]
........................................................................ [ 27%]
........................................................................ [ 34%]
........................................................................ [ 41%]
........................................................................ [ 48%]
........................................................................ [ 55%]
........................................................................ [ 61%]
........................................................................ [ 68%]
........................................................................ [ 75%]
........................................................................ [ 82%]
........................................................................ [ 89%]
........................................................................ [ 96%]
......................................                                   [100%]
1043 passed, 3 skipped in 383.03s (0:06:23)
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，56m50s

```text
b/s1-r0 done
a/s2-r0 done
b/s2-r0 done
[FAIL] archive: pack failed: 1 D:\CoevoDB\.venv\Scripts\python.exe: No module named surprise.experiments.archive

[FAIL] docs: SERVER.md: no heading '### 5.7 \u5e76\u884c\u7f51\u683c'
[PASS] scope: 45 paths changed (s14-done-r2..work tree), all in scope; harness and lower layers untouched (0s)
S15 GATE: FAIL (8/11 groups passed)
=== summary ===
s01: PASS
s02: PASS
s03: PASS
s04: PASS
s05: PASS
s06: PASS
s07: PASS
s08: FAIL (exit 1)
s09: PASS
s10: PASS
s11: FAIL (exit 1)
s12: PASS
s13: PASS
s14: PASS
s15: FAIL (exit 1)
GATES: FAIL (12/15 passed)
```

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- 无

### 4.4 新增的宽泛异常捕获

- `framework/surprise/baselines/sqlancer_run.py:372` `except Exception as exc:`
- `framework/surprise/baselines/sqlancer_run.py:379` `except Exception as exc:`
- `framework/surprise/baselines/sqlancer_run.py:434` `except Exception as exc:`

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s15-sqlancer.jsonl` 与 stderr 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 删除 `refs/heads/grok/s15-archive`（原 5381600880f4）
- 移动 `refs/heads/session/s15` 33b4cd336536 → 2d3bef2fc134

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s15-sqlancer.jsonl`：125 条事件（item.completed 68，item.started 47，orch.exit 2，orch.start 2，thread.started 2，turn.completed 2，turn.started 2）；各轮合计 codex：2 轮，输入 9534693 token（其中缓存 9293952），输出 45769（其中推理 8156），codex 不报美元。

被 deny 规则（grok）或 execpolicy 规则（codex，记在 stderr）拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
exec [exit 0]: warning: in the working copy of 'framework/surprise/baselines/sqlancer_run.py', LF will be replaced by CRLF the next time Git touches it warning: in the working copy of 'framework…
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "git status --short; git log -1 --oneline; rg -n 'ended before the interrupt' framework/surprise/gates/s1…
exec [exit 0]: 7f7945b Fix SQLancer replay process guards and null command metadata 499: require(proc.poll() is None, f"{what} ended before the interrupt: {proc.stderr.read()[-600:] if proc.stde…
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "python -c \"import json,tempfile; from pathlib import Path; p=Path(tempfile.gettempdir())/'coevo-s15-gat…
exec [exit 0]: {"experiments": 711, "status": "budget_minutes", "wall_s": 300.688996} sqlancer_started False
text: 返工已提交为 `7f7945b`，工作区干净。完整测试及 S11、S14 均通过；S15 的 SQLancer 组通过，中断组失败。证据显示，门槛因阻塞读等到主循环跑满 5 分钟，随后收到退出码 0，且未启动 SQLancer 中断检查。我正在将命令输出和这一基线问题写入报告。
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Encoding UTF8 -Raw .orch/report.md'
exec [exit 0]: # 报告 · s15-sqlancer 状态：未完成，按工作包的测试错误停止规则交接。提交：`abbc3e8`（当前分支 `grok/s15-sqlancer`，提交后 git status --short 无输出）。 ## 改了哪些文件 - `framework/surprise/baselines/sqlancer_run.py`：新增日志分类与原文转…
file_change [completed]: update D:\CoevoDB\.worktrees\s15-sqlancer\.orch\report.md
text: 已返工并提交 `7f7945b`，工作区干净，[报告已更新](D:/CoevoDB/.worktrees/s15-sqlancer/.orch/report.md)。 - 完整测试：1043 通过、3 跳过；S11、S14 通过。 - SQLancer 10 分钟运行：601,510 条查询、8 份报告，门槛通过。 - S15 中断组被基线门槛的阻塞读问题…
end: tokens in=8344182 cached=8192000 out=30321 reasoning=6806
orch.exit: {"pkg": "s15-sqlancer", "run": 2, "at": "2026-10-19T18:25:57+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s15-sqlancer

审查 1 的返工已完成并提交：`7f7945b`（前一实现提交 `abbc3e8`，分支 `grok/s15-sqlancer`）。提交后 `git status --short` 无输出。完整验收受基线门槛问题阻塞，不能声明本包全部验收通过。

## 改了哪些文件

- `framework/surprise/baselines/sqlancer_run.py`：新增 SQLancer 真实运行、日志分类与 SqlCase 原文转换、共同 harness/CVE 评判、回放、进程清理与报告。本轮将回放的 `sqlancer.command` 从空列表改为 `null`；回放的 `java`、`command`、`pid` 均为 `null`，不运行任何 Java，包括 `java -version`。
- `framework/surprise/metrics/report.py`：接入 SQLancer 运行臂的格及 RQ 汇总，保留只读汇总臂和 external；本轮无进一步修改。
- `framework/tests/test_surprise_s15_sqlancer.py`：新增日志分类、LF/CRLF、原文片段、unsupported_shape、不转换原因、类路径 override、环境变量找工具、回放家族键、网格报告、60 秒真实运行、20 秒后中断等测试。本轮将回放替身改为按 `Path(command[0]).name.lower()` 只拒绝 `java`/`java.exe`，同时保护 `subprocess.run` 和 `subprocess.Popen`，允许 harness 起 Python 子进程；保留其余断言并补充 null 元数据断言。
- `framework/tests/data/sqlancer/norec_mismatch.log`、`tool_error_sqlexception.log`、`tool_error_unsupported.log`、`unexpected_error_ddl.log`：四份门槛日志样例。
- `framework/tests/data/sqlancer/tlp_mismatch.log`、`norec_join.log`、`unexpected_error_select.log`：TLP 不一致、JOIN NoREC、意外 SELECT 错误样例。

本轮只修改驱动和本包新测试这两个文件；基线已有测试、门槛、冻结 harness、docs 和其它禁区均未修改。

## 跑了哪些命令

本轮结果：
- 定向测试：38 passed，耗时 87.08 秒（包含一次 60 秒真实运行和一次 20 秒后中断，小于 5 分钟）。中断测试确认退出 130、状态 interrupted、Java PID 已退出。
- 完整测试：1043 passed、3 skipped、0 failed。3 个 skip 为基线已有，未新增 skip/xfail。
- S11 grid/sqlancer/runmetrics：3/3 PASS；S14 smoke：1/1 PASS。
- S15 sqlancer：PASS；interrupt：FAIL，原因见未决问题。
- 10 分钟真实运行：600.19 秒，601,510 条查询，8 份报告；kinds 为 mismatch=0、unexpected_error=0、tool_error=8；converted=0、judged=0、unjudged=0；日志总量 3.6 MB。这 8 份工具错误未计为 harness 缺陷。
- NoREC 回放样例由 harness 判为 fail，家族键为 `fix|duckdb|deliminator,filter_pushdown`，与主循环相同。
- 真实运行产物：`D:/CoevoDB/.worktrees/s15-sqlancer/.orch/tmp/coevo-s15-gate/sqlancer/live/cells/sqlancer/s7-r0/`。未复制大日志、未清理 `.orch/tmp`、未调用 LLM。

以下为本轮验证与提交命令的退出码和原始输出末 20 行。

### python -m pytest -q tests/test_surprise_s15_sqlancer.py

命令（`python` 命令在 `framework/` 目录，其余在 worktree 根目录执行）：

```powershell
python -m pytest -q tests/test_surprise_s15_sqlancer.py
```

退出码：0。输出最后 20 行（不足 20 行则完整贴出）：

```text
......................................                                   [100%]
38 passed in 87.08s (0:01:27)
```

### python -m pytest -q testing tests

命令（`python` 命令在 `framework/` 目录，其余在 worktree 根目录执行）：

```powershell
python -m pytest -q testing tests
```

退出码：0。输出最后 20 行（不足 20 行则完整贴出）：

```text
........................ss..................................s........... [  6%]
........................................................................ [ 13%]
........................................................................ [ 20%]
........................................................................ [ 27%]
........................................................................ [ 34%]
........................................................................ [ 41%]
........................................................................ [ 48%]
........................................................................ [ 55%]
........................................................................ [ 61%]
........................................................................ [ 68%]
........................................................................ [ 75%]
........................................................................ [ 82%]
........................................................................ [ 89%]
........................................................................ [ 96%]
......................................                                   [100%]
1043 passed, 3 skipped in 414.98s (0:06:54)
```

### python -m surprise.gates.s15 --only sqlancer interrupt

命令（`python` 命令在 `framework/` 目录，其余在 worktree 根目录执行）：

```powershell
python -m surprise.gates.s15 --only sqlancer interrupt
```

退出码：1。输出最后 20 行（不足 20 行则完整贴出）：

```text
[PASS] sqlancer: 4 fixtures classified, the NoREC one judged fail with the loop's key fix|duckdb|deliminator,filter_pushdown; live run: 601510 queries, 8 reports, 0 judged, 3.6 MB of logs (607s)
[FAIL] interrupt: the loop exited 0 after the interrupt, expected 130
S15 GATE [only: sqlancer, interrupt]: FAIL (1/2 groups passed)
```

### python -m surprise.gates.s11 --only grid sqlancer runmetrics

命令（`python` 命令在 `framework/` 目录，其余在 worktree 根目录执行）：

```powershell
python -m surprise.gates.s11 --only grid sqlancer runmetrics
```

退出码：0。输出最后 20 行（不足 20 行则完整贴出）：

```text
[PASS] grid: 2 arms x 2 seeds in 4.1 min, resumed, report and 7 figures in one command; median families/hour {'surprise': 29.86419109777332, 'old': 29.929257560720792}; p 1.0, A12 0.375 (247s)
[PASS] sqlancer: 35 runs, 0 bugs; per engine rows match docs/FINAL_REPORT.md (0s)
[PASS] runmetrics: 31 records, 1 ledger families, Brier 0.2194, 1 high-surprise records, invalid 14, theory length 193.0; all recomputed (31s)
S11 GATE [only: grid, sqlancer, runmetrics]: PASS (3/3 groups passed)
```

### python -m surprise.gates.s14 --only smoke

命令（`python` 命令在 `framework/` 目录，其余在 worktree 根目录执行）：

```powershell
python -m surprise.gates.s14 --only smoke
```

退出码：0。输出最后 20 行（不足 20 行则完整贴出）：

```text
[PASS] smoke: 1 cell(s) done on Linux with the frozen harness and pinned engines, same code as s14-done apart from the gates (nothing the grid runs imports them); report has 13 sections (1s)
S14 GATE [only: smoke]: PASS (1/1 groups passed)
```

### python

命令（`python` 命令在 `framework/` 目录，其余在 worktree 根目录执行）：

```powershell
python -c "import json,tempfile; from pathlib import Path; p=Path(tempfile.gettempdir())/'coevo-s15-gate/sqlancer/live/cells/sqlancer/s7-r0'; r=json.loads((p/'report.json').read_text(encoding='utf-8')); s=r['sqlancer']; print(json.dumps({k:r[k] for k in ['status','executions','wall_s','labels']},sort_keys=True)); print(json.dumps({k:s[k] for k in ['commit','jar_sha256','jdbc','reports','kinds','converted','judged','unjudged','pid']},sort_keys=True)); print(p)"
```

退出码：0。输出最后 20 行（不足 20 行则完整贴出）：

```text
{"executions": 601510, "labels": {}, "status": "budget_minutes", "wall_s": 600.19}
{"commit": "ab328b756bf5d923b9d93959af3432546efe56fd", "converted": 0, "jar_sha256": "1a762fdb48336c7bc539c03f26b4e28209559e10729809d6d7f94d1bb4b52308", "jdbc": ["cassandra-jdbc-wrapper-4.7.0.jar", "clickhouse-jdbc-0.3.2.jar", "duckdb_jdbc-1.5.5.0.jar", "flight-sql-jdbc-driver-16.1.0.jar", "hive-jdbc-3.1.2.jar", "jdbc-yugabytedb-42.3.5-yb-1.jar", "mssql-jdbc-6.2.1.jre7.jar", "presto-jdbc-0.283.jar", "sqlite-jdbc-3.49.1.0.jar"], "judged": 0, "kinds": {"mismatch": 0, "tool_error": 8, "unexpected_error": 0}, "pid": 25160, "reports": 8, "unjudged": 0}
D:\CoevoDB\.worktrees\s15-sqlancer\.orch\tmp\coevo-s15-gate\sqlancer\live\cells\sqlancer\s7-r0
```

### git diff --check

命令（`python` 命令在 `framework/` 目录，其余在 worktree 根目录执行）：

```powershell
git diff --check
```

退出码：0。输出最后 20 行（不足 20 行则完整贴出）：

```text
warning: in the working copy of 'framework/surprise/baselines/sqlancer_run.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'framework/tests/test_surprise_s15_sqlancer.py', LF will be replaced by CRLF the next time Git touches it
```

### git add -- framework/surprise/baselines/sqlancer_run.py framework/tests/test_surprise_s15_sqlancer.py; git commit -m "Fix SQLancer replay process guards and null command metadata"

命令（`python` 命令在 `framework/` 目录，其余在 worktree 根目录执行）：

```powershell
git add -- framework/surprise/baselines/sqlancer_run.py framework/tests/test_surprise_s15_sqlancer.py; git commit -m "Fix SQLancer replay process guards and null command metadata"
```

退出码：0。输出最后 20 行（不足 20 行则完整贴出）：

```text
warning: in the working copy of 'framework/surprise/baselines/sqlancer_run.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'framework/tests/test_surprise_s15_sqlancer.py', LF will be replaced by CRLF the next time Git touches it
[grok/s15-sqlancer 7f7945b] Fix SQLancer replay process guards and null command metadata
 2 files changed, 10 insertions(+), 2 deletions(-)
```

### git status --short; git log -1 --oneline; rg -n 'ended before the interrupt' framework/surprise/gates/s15.py

命令（`python` 命令在 `framework/` 目录，其余在 worktree 根目录执行）：

```powershell
git status --short; git log -1 --oneline; rg -n 'ended before the interrupt' framework/surprise/gates/s15.py
```

退出码：0。输出最后 20 行（不足 20 行则完整贴出）：

```text
7f7945b Fix SQLancer replay process guards and null command metadata
499:        require(proc.poll() is None, f"{what} ended before the interrupt: {proc.stderr.read()[-600:] if proc.stderr else ''}")
```

### python

命令（`python` 命令在 `framework/` 目录，其余在 worktree 根目录执行）：

```powershell
python -c "import json,tempfile; from pathlib import Path; p=Path(tempfile.gettempdir())/'coevo-s15-gate/interrupt'; r=json.loads((p/'loop/report.json').read_text(encoding='utf-8')); print(json.dumps({k:r[k] for k in ['status','experiments','wall_s']},sort_keys=True)); print('sqlancer_started', (p/'sqlancer').exists())"
```

退出码：0。输出最后 20 行（不足 20 行则完整贴出）：

```text
{"experiments": 711, "status": "budget_minutes", "wall_s": 300.688996}
sqlancer_started False
```


## 与说明的偏差

- 全部指定验收命令均已执行，但 S15 interrupt 组未通过。基线 `framework/surprise/gates/s15.py:499` 的阻塞读使主循环自然跑满 5 分钟后才发中断，收到 0 而非 130，并阻止该组继续验证 SQLancer。按 brief 的“某个测试确实该改，就写进报告的未决问题，停下”规则停止；未修改基线门槛、未放宽验收、未换方式重试。审查 1 提及的测试替身及回放元数据问题均已解决，不再列为偏差。

## 未决问题

- 基线门槛 `framework/surprise/gates/s15.py:499`：

```python
require(proc.poll() is None, f"{what} ended before the interrupt: {proc.stderr.read()[-600:] if proc.stderr else ''}")
```

  Python 会先求值所有实参；即使进程仍在运行、require 条件为真，错误消息里的 `proc.stderr.read()` 仍会阻塞到 stderr EOF。该语句位于 `send_interrupt(proc)` 之前。本次主循环实际跑了 300.688996 秒、完成 711 次实验、状态为 budget_minutes；随后门槛报告 `the loop exited 0 after the interrupt, expected 130`。SQLancer 中断子检查尚未启动（`sqlancer_started False`）。应由编排者修正门槛，使 stderr 仅在失败分支读取，再重跑该组。本包允许范围不包含门槛，因此没有修改。
- 除上述基线验收阻塞外，无其它未决问题。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：
