# 审查包 · s16-replay

- 生成时间：2026-10-22T00:25:26+11:00
- 基线：`session/s16`（572cad1e0d7b）
- 分支：`grok/s16-replay` @ 8bf6292d7b87，基线之上 1 个提交
- 运行：共 1 轮（返工 0 轮），最近一轮退出码 0，用时 15m31s
- 执行者：codex codex-cli 0.163.0；会话 `01a15e94-7b2b-7482-a346-b863e476f65a`

## 红旗汇总

- 门槛未通过（退出码 1）
- 新增宽泛的异常捕获 1 处（确认没有吞掉失败）
- 派发以来有 2 处 tag 变化或 ref 被删：确认是编排者自己做的，不是执行者

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s16..grok/s16-replay
git diff -M --stat session/s16..grok/s16-replay
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/metrics/replay.py`、`framework/tests/test_surprise_s16_replay.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| A | `framework/surprise/metrics/replay.py` |  |
| A | `framework/tests/test_surprise_s16_replay.py` |  |

提交：

- 8bf6292 Junke: feat(metrics): add stratified harness replay and evidence checks

## 2. diff 统计

```text
 framework/surprise/metrics/replay.py        | 210 +++++++++++++++++++++
 framework/tests/test_surprise_s16_replay.py | 278 ++++++++++++++++++++++++++++
 2 files changed, 488 insertions(+)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，7m52s；passed 1230，skipped 3

```text
........................ss..................................s........... [  5%]
........................................................................ [ 11%]
........................................................................ [ 17%]
........................................................................ [ 23%]
........................................................................ [ 29%]
........................................................................ [ 35%]
........................................................................ [ 40%]
........................................................................ [ 46%]
........................................................................ [ 52%]
........................................................................ [ 58%]
........................................................................ [ 64%]
........................................................................ [ 70%]
........................................................................ [ 75%]
........................................................................ [ 81%]
........................................................................ [ 87%]
........................................................................ [ 93%]
........................................................................ [ 99%]
.........                                                                [100%]
1230 passed, 3 skipped in 471.01s (0:07:51)
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，30m00s

```text
[PASS] isolation: roles load no model client until a transport is built; loop, Hunter, Diagnoser, harness never import them; transport reuses BaseAgent and the old ledger (2s)
[PASS] constants: 19 constants as planned; tiers {'fast': 'deepseek-flash', 'strong': 'deepseek-v4-pro'} (0s)
[PASS] cache: key = prompt hash + model + seed; hits make no call; replay identical; forged entry refused; ledger and per-role totals (0s)
[PASS] reject: 9 replies parsed as planned; refusals replay as refusals; the implementer refuses before phi (0s)
[PASS] cap: cap 2 blocks the third call; cache served past the cap; cap 0 calls nothing; env ceiling; errors count, not cached (0s)
[PASS] source: confined, exact, read-only; checkouts at datafusion 45d943dfb869, duckdb d8cdaa33fda8 (0s)
[PASS] implementer: accepted, retried with feedback, unmet, bad case, replayed, blocked (0s)
[PASS] conjecturer: selection picks datafusion/expr/src/logical_plan/builder.rs for DF-A and src/optimizer/filter_pushdown.cpp for ('filter_pushdown',); registered with a revise whose bets are its predictions; settled by experiments; refusals, drops, not covering, blocked (13s)
[PASS] wiring: off: 40 rows identical to S8, no role loaded; on: 7 scripted calls, 0 implementer experiments meeting their specs; cap 0 completes (81s)
[PASS] implementer_report: phi-check pass rate 0.97 at the first try, 1.00 after 2 tries (30/30); boundary 10/10, core 10/10, whole 10/10 (1s)
[PASS] dfa: mechanism: LogicalPlanBuilder::intersect_or_except implements EXCEPT ALL as a LeftAnti hash join with NullEqualsNull, so it removes every left row having any match instead; trigger ['ast:set_op:except_all', 'ast:stmt:select', 'data:setop:left_has_dups']; 4 predictions (fail on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_dups+data:table:dup_rows+data:type:integer without data:setop:left_has_null+data:setop:right_has_null+data:table:has_null; pass on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_null+data:setop:right_has_null+data:table:has_null+data:type:integer without data:setop:left_has_dups+data:table:dup_rows; fail on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_dups+data:setop:left_has_null+data:setop:right_has_null+data:table:dup_rows+data:table:has_null+data:type:integer; pass on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_dups+data:table:dup_rows+data:table:empty+data:type:integer without data:setop:left_has_null+data:setop:right_has_null+data:table:has_null); proposed as e1, accepted (0s)
[PASS] replay: 21 experiments and 25 calls replayed from the cache, identical; lanes {'bootstrap': 1, 'generalize': 5, 'bet': 5, 'implement': 7, 'refine': 3}; book {'conjectures': 3, 'rejected': 0, 'predictions': 12, 'open': 4, 'kept': 6, 'broken': 2} (66s)
S09 GATE: PASS (12/12 groups passed)
=== gate s10 ===
[PASS] isolation: 4 role modules load no model client; loop, Hunter, Diagnoser and harness never import the roles (1s)
[PASS] constants: 35 S10 constants as planned, S9 constants unchanged, library constants ['LIBRARY_ENV', 'LIBRARY_KINDS', 'LIBRARY_MIN_REFERENCES', 'LIBRARY_RULE_PREFIX', 'LIBRARY_SCHEMA'] (0s)
[PASS] frozen: harness changes since s09-done-r2: ['equivalent_query.py', 'rewrites.py']; re-frozen and verified; 12 frozen-rule outputs unchanged with and without a library (0s)
[PASS] library: 4 usable and 10 refused templates; 8 malformed libraries refused; judgements {'llm:wrap_sub': 'pass', 'llm:is_true': 'pass', 'llm:first_row': 'untrusted_rewrite/reference_disagrees', 'llm:octet': 'untrusted_rewrite/rewrite_error'}; frozen rule unchanged; no library, no trust (6s)
[PASS] frame: prior moves U 0.498 -> 1.000; extra rules offered; prepare once per round (1 rounds); vocabulary run extracts ast:set_op:except_all_two_tables (25s)
[PASS] switches: all on: calls {'implementer': 4, 'conjecturer': 1, 'prior': 3, 'translator': 1, 'vocab_inventor': 1, 'oracle_inventor': 1}; each role off: no call, no ledger line, plugin module not loaded (181s)
[PASS] prior: 20 units priced in 2 calls; evidence from the checkouts (40 lines); bad prior weight -> 0.0 after 20; useful prior weight 0.490 (1s)
[PASS] translator: DF-A family -> DuckDB translated once; settled {'tr-match': ('kept', 'match'), 'tr-mismatch': ('kept', 'mismatch'), 'tr-broken': ('broken', None), 'tr-void': ('void', None)}; bad switch refused; unmet spec retried (11s)
[PASS] vocab_inventor: accepted ast:set_op:except_all_two_tables on held-out records; refused {'empty': 'pattern', 'long': 'pattern', 'catastrophic': 'scan', 'everything': 'scan', 'no_exclusion': 'train', 'train_only': 'holdout'} and a data-layer id; prompt hides the held-out records (21s)
[PASS] oracle_inventor: accepted ['llm:wrap_sub'] on 5 instances; refused disagree, template, duplicate; 3 calls in 401 experiments; judged by the harness: pass (2s)
[PASS] translator_real: F2 (duckdb) -> datafusion: status ok, expect pass, switches []; label pass; settled kept identity None (6s)
```

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- 无

### 4.4 新增的宽泛异常捕获

- `framework/surprise/metrics/replay.py:123` `except Exception as exc:`

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s16-replay.jsonl` 与 stderr 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 删除 `refs/heads/grok/s16-core`（原 572cad1e0d7b）
- 新增 `refs/heads/grok/s16-oracles` @ 34a7cc32a5c0
- 删除 `refs/heads/grok/s16-roles`（原 572cad1e0d7b）
- 新增 `refs/heads/grok/s16-roles-b` @ 890fe4df5db4
- 新增 `refs/heads/grok/s16-sqlancer` @ 47029d9fe595
- 移动 `refs/heads/session/s16` 572cad1e0d7b → 6191a06f349a

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s16-replay.jsonl`：58 条事件（item.completed 32，item.started 21，orch.exit 1，orch.start 1，thread.started 1，turn.completed 1，turn.started 1）；各轮合计 codex：1 轮，输入 3696413 token（其中缓存 3605760），输出 22579（其中推理 10723），codex 不报美元。

被 deny 规则（grok）或 execpolicy 规则（codex，记在 stderr）拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
exec [exit 0]: ........................ss..................................s........... [ 5%] ........................................................................ [ 11%] ....................…
text: 完整测试集通过：`1230 passed, 3 skipped`；新增测试为 `25 passed`，CLI 帮助检查通过。现在提交改动并写入 `.orch/report.md`，记录验收输出和环境处理方式。
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git diff --cached --check'
exec [exit 0]: 
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git commit -m "feat(metrics): add stratified harness replay and evidence checks"'
exec [exit 0]: [grok/s16-replay 8bf6292] feat(metrics): add stratified harness replay and evidence checks 2 files changed, 488 insertions(+) create mode 100644 framework/surprise/metrics/replay.…
file_change [completed]: add D:\CoevoDB\.claude\worktrees\s16\.worktrees\s16-replay\.orch\report.md
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short; git check-ignore .orch/report.md; git log -1 --oneline'
exec [exit 0]: .orch/report.md 8bf6292 feat(metrics): add stratified harness replay and evidence checks
text: 已完成并提交 `8bf6292`，工作区干净。 - 完整测试：1230 passed，3 skipped - 新增测试：25 passed - CLI 帮助检查通过 - 按说明未跑全部门槛 详见[工作报告](D:/CoevoDB/.claude/worktrees/s16/.worktrees/s16-replay/.orch/report.md)。
end: tokens in=3696413 cached=3605760 out=22579 reasoning=10723
orch.exit: {"pkg": "s16-replay", "run": 1, "at": "2026-10-22T00:24:43+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s16-replay

## 改了哪些文件

- `framework/surprise/metrics/replay.py`：新增两遍流式分层抽样、最大余数分配与每层至少一条约束、spawn 子进程回放、CVE/身份比较、ASCII JSON 报告及 CLI 退出码。
- `framework/tests/test_surprise_s16_replay.py`：新增 25 项测试，用关闭 LLM 的 DuckDB 主循环运行作素材，覆盖抽样、worker 一致性、复制账本后篡改检测、放宽规则、归属计数、CVE/身份字段、异常与路径格式。

提交：`8bf6292`，当前分支 `grok/s16-replay`。只提交上述两个允许的路径；本报告不入库。

## 跑了哪些命令

测试与 CLI 命令的工作目录为 `framework/`；git 命令在 worktree 根执行。以下保留验收及提交命令的原始输出；读取文件和定位实现的只读查询不列入验收记录。

### `pytest -q tests/test_surprise_s16_replay.py`

退出码：1。输出最后 20 行：

```text

=================================== ERRORS ====================================
_____________ ERROR collecting tests/test_surprise_s16_replay.py ______________
ImportError while importing test module 'D:\CoevoDB\.claude\worktrees\s16\.worktrees\s16-replay\framework\tests\test_surprise_s16_replay.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
D:\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\test_surprise_s16_replay.py:17: in <module>
    from surprise.experiments.loop import run
E   ModuleNotFoundError: No module named 'surprise'
=========================== short test summary info ============================
ERROR tests/test_surprise_s16_replay.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.18s
```

### `$env:PYTHONPATH = (Get-Location).Path; pytest -q tests/test_surprise_s16_replay.py`

退出码：0。输出最后 20 行：

```text
.........................                                                [100%]
25 passed in 15.96s
```

### `$env:PYTHONPATH = (Get-Location).Path; pytest -q testing tests`

退出码：0。输出最后 20 行：

```text
........................ss..................................s........... [  5%]
........................................................................ [ 11%]
........................................................................ [ 17%]
........................................................................ [ 23%]
........................................................................ [ 29%]
........................................................................ [ 35%]
........................................................................ [ 40%]
........................................................................ [ 46%]
........................................................................ [ 52%]
........................................................................ [ 58%]
........................................................................ [ 64%]
........................................................................ [ 70%]
........................................................................ [ 75%]
........................................................................ [ 81%]
........................................................................ [ 87%]
........................................................................ [ 93%]
........................................................................ [ 99%]
.........                                                                [100%]
1230 passed, 3 skipped in 555.80s (0:09:15)
```

### `python -m surprise.metrics.replay --help`

退出码：0。输出最后 20 行：

```text
usage: replay.py [-h] --sample SAMPLE --seed SEED --out OUT
                 [--workers WORKERS]
                 run_dir

Stratified replay of an old ledger against the current frozen harness.

positional arguments:
  run_dir

options:
  -h, --help         show this help message and exit
  --sample SAMPLE
  --seed SEED
  --out OUT
  --workers WORKERS
```

### `git diff --cached --check`

退出码：0。无输出。

### `git commit -m "feat(metrics): add stratified harness replay and evidence checks"`

退出码：0。输出最后 20 行：

```text
[grok/s16-replay 8bf6292] feat(metrics): add stratified harness replay and evidence checks
 2 files changed, 488 insertions(+)
 create mode 100644 framework/surprise/metrics/replay.py
 create mode 100644 framework/tests/test_surprise_s16_replay.py
```

### `git status --short`

退出码：0。无输出，工作区干净。

## 与说明的偏差

功能与修改范围无偏差。首次直接运行 `pytest` 时，入口未将当前 `framework/` 加入模块搜索路径，收集阶段报 `ModuleNotFoundError: No module named 'surprise'`。后续只为测试进程设置 `PYTHONPATH` 为当前 `framework/`，继续使用说明指定的 `pytest` 和项目解释器；未修改 conftest、基线测试或环境安装。

边界输入约定：当 `--sample` 小于非空层数时，无法同时满足每层至少一条与固定总数，作为用法错误返回 2。最大余数并列按层键排序，保证可重复。

按说明未运行 `python -m surprise.gates.all`，也未连接实验服务器、修改冻结 harness 或结果产物、打 tag、合并、rebase、push 或切换分支。新增测试全部通过且无 skip/xfail；完整测试集为 1230 passed、3 skipped。

## 未决问题

无。本 worktree 缺少说明中列出的 S8 旧账本与门槛产物；现场旧账本回放及全部门槛由编排者合并后在主检出区运行。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：
