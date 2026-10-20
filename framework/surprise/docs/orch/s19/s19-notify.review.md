# 审查包 · s19-notify

- 生成时间：2026-10-21T04:22:21+11:00
- 基线：`session/s19`（aa6410222a45）
- 分支：`grok/s19-notify` @ d84588bae100，基线之上 2 个提交
- 运行：共 2 轮（返工 1 轮），最近一轮退出码 0，用时 13m47s
- 执行者：codex codex-cli 0.163.0；会话 `01a15a13-e8a0-7952-af25-dfcd5740149f`

## 红旗汇总

- 门槛未通过（退出码 1）
- 新增宽泛的异常捕获 2 处（确认没有吞掉失败）
- 疑似密钥 1 处、敏感文件名 0 个

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s19..grok/s19-notify
git diff -M --stat session/s19..grok/s19-notify
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/notify/**`、`framework/surprise/roles/gateway.py`、`framework/tests/test_surprise_s19_notify.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| A | `framework/surprise/notify/__init__.py` |  |
| A | `framework/surprise/notify/pushplus.py` |  |
| A | `framework/surprise/notify/watch.py` |  |
| M | `framework/surprise/roles/gateway.py` |  |
| A | `framework/tests/test_surprise_s19_notify.py` |  |

提交：

- 232febd Junke: Add pushplus alerts and read-only grid watcher
- d84588b Junke: Fix recursive activity checks and watcher failure recovery

## 2. diff 统计

```text
 framework/surprise/notify/__init__.py       |   1 +
 framework/surprise/notify/pushplus.py       |  72 ++++
 framework/surprise/notify/watch.py          | 382 +++++++++++++++++
 framework/surprise/roles/gateway.py         |   2 +-
 framework/tests/test_surprise_s19_notify.py | 636 ++++++++++++++++++++++++++++
 5 files changed, 1092 insertions(+), 1 deletion(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，6m53s；passed 1157，skipped 3

```text
........................ss..................................s........... [  6%]
........................................................................ [ 12%]
........................................................................ [ 18%]
........................................................................ [ 24%]
........................................................................ [ 31%]
........................................................................ [ 37%]
........................................................................ [ 43%]
........................................................................ [ 49%]
........................................................................ [ 55%]
........................................................................ [ 62%]
........................................................................ [ 68%]
........................................................................ [ 74%]
........................................................................ [ 80%]
........................................................................ [ 86%]
........................................................................ [ 93%]
........................................................................ [ 99%]
........                                                                 [100%]
1157 passed, 3 skipped in 412.81s (0:06:52)
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，30m00s

```text
[PASS] switches: all on: calls {'implementer': 4, 'conjecturer': 1, 'prior': 3, 'translator': 1, 'vocab_inventor': 1, 'oracle_inventor': 1}; each role off: no call, no ledger line, plugin module not loaded (128s)
[PASS] prior: 20 units priced in 2 calls; evidence from the checkouts (40 lines); bad prior weight -> 0.0 after 20; useful prior weight 0.490 (1s)
[PASS] translator: DF-A family -> DuckDB translated once; settled {'tr-match': ('kept', 'match'), 'tr-mismatch': ('kept', 'mismatch'), 'tr-broken': ('broken', None), 'tr-void': ('void', None)}; bad switch refused; unmet spec retried (8s)
[PASS] vocab_inventor: accepted ast:set_op:except_all_two_tables on held-out records; refused {'empty': 'pattern', 'long': 'pattern', 'catastrophic': 'scan', 'everything': 'scan', 'no_exclusion': 'train', 'train_only': 'holdout'} and a data-layer id; prompt hides the held-out records (21s)
[PASS] oracle_inventor: accepted ['llm:wrap_sub'] on 5 instances; refused disagree, template, duplicate; 3 calls in 401 experiments; judged by the harness: pass (1s)
[PASS] translator_real: F2 (duckdb) -> datafusion: status ok, expect pass, switches []; label pass; settled kept identity None (4s)
[PASS] m3: 32 experiments and 43 calls replayed from the cache, identical; calls {'conjecturer': 2, 'oracle_inventor': 1, 'implementer': 36, 'prior': 4}; DF-B (shape|datafusion|wrong_result|-|extra_only) reached at experiment 3 via bet (bet from c1 on h1); lanes {'bootstrap': 1, 'generalize': 2, 'bet': 7, 'refine': 4, 'implement': 18} (85s)
S10 GATE: PASS (12/12 groups passed)
=== gate s11 ===
[PASS] constants: 7 metric constants, request deadline 600.0 s, pure-LLM constants and 10 topics (0s)
[PASS] store: 6 replace calls for 3 transient failures (0.36s); a lasting failure raises PermissionError (2s)
[PASS] loop_error: original exception kept and written to error.txt (both, drive) (1s)
[PASS] deadline: normal answer passes; deadline 1.5s held (trickle 1.9s, silent 1.9s); errors booked, not cached (9s)
[PASS] vocabulary: run_registry, new_families, compare, recall.score, RunData and run_metrics all read the run's vocabulary (34s)
[PASS] stats: exact and asymptotic MWU (scipy agrees), A12, median, summarize as hand-computed (1s)
[PASS] runmetrics: 31 records, 1 ledger families, Brier 0.2194, 1 high-surprise records, invalid 14, theory length 193.0; all recomputed (0s)
[FAIL] ciao: artifact directory results/s08/longrun is missing on this machine
[PASS] llm_metrics: 15 experiments replayed; 2 conjectures, survival 0.0, accuracy 0.7142857142857143 over 7 settled bets; families via {'implement': 0, 'bet': 1, 'translate': 0, 'llm_rule': 0, 'invented_feature': 0}; 23 calls (34s)
[PASS] rq6: classify, F2 fix conditions (1 entries), pair agreement as hand-computed; F2 hypothesis too_narrow (missing [], extra 9 literals); recall 0.5 (4s)
[PASS] arms: random Hunter deterministic and different; frozen theory unchanged (1 failures fully profiled); frozen Diagnoser no edits; theory-from and select-from (5 choices scored differently); 5 usage errors refused (94s)
[PASS] pure_llm_script: 4 cases executed from 3 calls (1 reply rejected, 2 bad cases skipped); prompts deterministic; budget holds (4s)
[PASS] pure_llm: 16 cases from 4 cached calls replayed identically; labels {'pass': 15, 'invalid': 1}; 0 families (7s)
[PASS] dedup: 3 failures, 1 true duplicates; sigma p/r 1.0/1.0, membership p/r None/0.0 (7s)
[PASS] coverage: 4 upstream regression seeds x 2 oracles on 1.5.5 and 1.1.3; {'plan_variant': {'old': {'pass': 4}, 'new': {'pass': 4}, 'fail_old_pass_new': [], 'fail_both': [], 'fail_new_only': []}, 'equivalent_query': {'old': {'invalid': 4}, 'new': {'invalid': 4}, 'fail_old_pass_new': [], 'fail_both': [], 'fail_new_only': []}} (7s)
[PASS] sqlancer: 35 runs, 0 bugs; per engine rows match docs/FINAL_REPORT.md (0s)
```

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- 无

### 4.4 新增的宽泛异常捕获

- `framework/surprise/notify/watch.py:267` `except Exception:`
- `framework/surprise/notify/watch.py:313` `except Exception as exc:`

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- `framework/tests/test_surprise_s19_notify.py:129` secret assignment: tok…(35 chars)
- 日志 `.orch/logs/s19-notify.jsonl` 与 stderr 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 移动 `refs/heads/session/s19` aa6410222a45 → cf5816b340f9

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s19-notify.jsonl`：131 条事件（item.completed 71，item.started 50，orch.exit 2，orch.start 2，thread.started 2，turn.completed 2，turn.started 2）；各轮合计 codex：2 轮，输入 11044179 token（其中缓存 10779648），输出 103446（其中推理 56557），codex 不报美元。

被 deny 规则（grok）或 execpolicy 规则（codex，记在 stderr）拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "python -c \"from pathlib import Path; import json; text=Path('.orch/report.md').read_text(encoding='utf-…
exec [exit 0]: {"tail": "\u3002\u53ea\u6539\u5141\u8bb8\u7684\u4e94\u4e2a\u6587\u4ef6\uff1b\u6bcf\u65e5\u4e0a\u9650\u6309\u53d1\u9001\u5c1d\u8bd5\u8ba1\u6570\uff08\u5931\u8d25\u4e5f\u5360\u7528\…
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "python -c \"from pathlib import Path; import json; names=('r2-pytest','r2-notify-tests','r2-s09','r2-s10…
exec [exit 0]: {"r2-pytest": "........................ss..................................s........... [ 6%]\n........................................................................ [ 12%]\n...…
file_change [completed]: update D:\CoevoDB\.worktrees\s19-notify\.orch\report.md
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "python -c \"from pathlib import Path; import hashlib,json; report=Path('.orch/report.md').read_text(enco…
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --porcelain; git log -1 --oneline; git check-ignore .orch/report.md'
exec [exit 0]: d84588b Fix recursive activity checks and watcher failure recovery .orch/report.md
exec [exit 0]: {"prefix_sha": "925f29dd54bd30513de01d4df0d7789b3194e1329d2eafe04f0ae37f0d491d92", "rounds": 1, "round_line": 258, "has_commit": true}
text: 三项审查意见已修复并提交 `d84588b`，工作区干净，无范围偏差。 - 测试：1157 passed，3 skipped。 - 门槛：S19 11/11，S09、S10 各 12/12，S15 指定组 3/3。 - 已追加[第 2 轮报告](D:/CoevoDB/.worktrees/s19-notify/.orch/report.md:258)，保留…
end: tokens in=7180605 cached=7020544 out=64843 reasoning=36894
orch.exit: {"pkg": "s19-notify", "run": 2, "at": "2026-10-21T04:22:03+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s19-notify

提交：`232febd`，当前分支 `grok/s19-notify`。

## 改了哪些文件

- `framework/surprise/notify/__init__.py`：新增提醒包。
- `framework/surprise/notify/pushplus.py`：新增一对一 txt 发送器与 CLI；失败安全返回、限制码停发、长度截断，凭据仅进入请求体。
- `framework/surprise/notify/watch.py`：新增只读网格看守；增量读取调用、失败分类与去重、停滞与余额检查、每日发送上限、批次合并、跨平台 PID 检查及 CLI。退出事件也与同轮事件合并。
- `framework/surprise/roles/gateway.py`：只修改失败 Reply 的 reason 一行，保留 TransportError 消息，其它异常仍只记类名。
- `framework/tests/test_surprise_s19_notify.py`：新增 56 项离线用例，拦截 httpx，显式管理凭据环境变量，覆盖只读目录、半行 UTF-8、去重与重置、日志尾部、UTC 跨日、发送失败隔离、余额、CLI 和 PID 检查。

## 跑了哪些命令

除注明仓库根的 git 命令外，工作目录均为 `framework/`。以下输出保留原样，最多取末 20 行；原生 PowerShell 管道中的部分中文输出乱码也原样保留。

最终结果：1142 passed、3 skipped，较说明基线增加 56 项通过，skip 不增加。S19 11/11、S09 12/12、S10 12/12、S15 指定组 3/3。测试与门槛全部离线；没有发送真实 pushplus 或 OpenRouter 请求。

首次直接用 pytest 入口只收集 tests 中这个文件时，没有加载 testing/conftest.py 的路径设置，出现 surprise 导入失败。未修改 conftest 或已有测试；改用 python -m pytest 定向执行通过，说明指定的完整 pytest 命令两次均通过。

### 最终完整测试

命令：`Move-Item -LiteralPath ../.orch/pytest.log -Destination ../.orch/pytest-initial.log; pytest -q testing tests 2>&1 | Tee-Object -FilePath ../.orch/pytest.log; exit $LASTEXITCODE`

退出码：0

```text
........................ss..................................s........... [  6%]
........................................................................ [ 12%]
........................................................................ [ 18%]
........................................................................ [ 25%]
........................................................................ [ 31%]
........................................................................ [ 37%]
........................................................................ [ 44%]
........................................................................ [ 50%]
........................................................................ [ 56%]
........................................................................ [ 62%]
........................................................................ [ 69%]
........................................................................ [ 75%]
........................................................................ [ 81%]
........................................................................ [ 88%]
........................................................................ [ 94%]
.................................................................        [100%]
1142 passed, 3 skipped in 400.28s (0:06:40)
```

### S19 全部门槛

命令：`python -m surprise.gates.s19 2>&1 | Tee-Object -FilePath ../.orch/s19.log; exit $LASTEXITCODE`

退出码：0

```text
[PASS] replay: M3 replay: 7 calls on z-ai/glm-5.3-flash, all cache misses, manifest records the endpoint; pure-LLM: 1 calls on z-ai/glm-5.3-flash (22s)
[PASS] grid: surprise and pure-LLM arms pass --llm-tier glm-flash; unknown tiers rejected (0s)
[PASS] prices: OpenRouter prices of 2026-10-20 price z-ai/glm-5.3-flash; DeepSeek table unchanged (0s)
[PASS] pushplus: one-to-one txt message to https://www.pushplus.plus/send with the PUSHPLUS_TOKEN token in the body; codes [900, 905, 888] stop the sender, other failures do not; no token, no request (6s)
[PASS] reason: a failed call records 'TransportError: HTTPStatusError 402' (status kept, no key); other exceptions as before; 11 reasons classified (1s)
[PASS] watch: start, 402/timeout/429 streaks (once each, re-armed by a success), failed/blocked/stalled cells, finished; one message per poll, daily cap; the grid directory untouched (0s)
2026-10-20T16:18:22.447471+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-notify\.orch\tmp\coevo-s19-gate\balance\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ�key ʣ���� $0.5
2026-10-20T16:18:22.447471+00:00 balance - low key ʣ���� $0.5
2026-10-20T16:49:22.447471+00:00 balance - empty key ʣ���� $0
2026-10-20T17:20:22.447471+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-notify\.orch\tmp\coevo-s19-gate\balance-null\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ�key û�������ޣ�ֻ�ܿ�����ʧ�ܷ���Ƿ��
2026-10-20T17:20:22.447471+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-notify\.orch\tmp\coevo-s19-gate\balance-401\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ���ȼ����֤ʧ�ܣ�HTTP 401
2026-10-20T17:20:22.447471+00:00 balance - auth ��ȼ����֤ʧ�ܣ�HTTP 401
Balance check failed; will retry at the next interval.
2026-10-20T17:20:22.447471+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-notify\.orch\tmp\coevo-s19-gate\balance-down\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ���ȼ��ʧ�ܣ�ֻ�ܿ�����ʧ�ܷ���Ƿ��
2026-10-20T17:20:22.447471+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-notify\.orch\tmp\coevo-s19-gate\balance-nollm\grid����� 0��ʧ�� 0������ 0��δ��ʼ 2��ʧ�ܸ���
2026-10-20T17:20:22.447471+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-notify\.orch\tmp\coevo-s19-gate\balance-nokey\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ���
[PASS] balance: https://openrouter.ai/api/v1/key with the DEEPSEEK_API_KEY key every 30 minutes on glm-flash grids: low and empty once each, 401 reported, no limit or no answer is no alarm (4s)
[PASS] cli: pushplus CLI exits 2 without a token; watch exits on 'finished' and on the grid process ending (--pid) (5s)
[PASS] scope: 29 paths changed (s15-done-r3..work tree), all in scope; harness and roles/constants.py untouched (0s)
S19 GATE: PASS (11/11 groups passed)
```

### S09

命令：`python -m surprise.gates.s09 2>&1 | Tee-Object -FilePath ../.orch/s09.log; exit $LASTEXITCODE`

退出码：0

```text
[PASS] isolation: roles load no model client until a transport is built; loop, Hunter, Diagnoser, harness never import them; transport reuses BaseAgent and the old ledger (1s)
[PASS] constants: 19 constants as planned; tiers {'fast': 'deepseek-flash', 'strong': 'deepseek-v4-pro'} (0s)
[PASS] cache: key = prompt hash + model + seed; hits make no call; replay identical; forged entry refused; ledger and per-role totals (0s)
[PASS] reject: 9 replies parsed as planned; refusals replay as refusals; the implementer refuses before phi (0s)
[PASS] cap: cap 2 blocks the third call; cache served past the cap; cap 0 calls nothing; env ceiling; errors count, not cached (0s)
[PASS] source: confined, exact, read-only; checkouts at datafusion 45d943dfb869, duckdb d8cdaa33fda8 (0s)
[PASS] implementer: accepted, retried with feedback, unmet, bad case, replayed, blocked (0s)
[PASS] conjecturer: selection picks datafusion/expr/src/logical_plan/builder.rs for DF-A and src/optimizer/filter_pushdown.cpp for ('filter_pushdown',); registered with a revise whose bets are its predictions; settled by experiments; refusals, drops, not covering, blocked (11s)
[PASS] wiring: off: 40 rows identical to S8, no role loaded; on: 7 scripted calls, 0 implementer experiments meeting their specs; cap 0 completes (58s)
[PASS] implementer_report: phi-check pass rate 0.97 at the first try, 1.00 after 2 tries (30/30); boundary 10/10, core 10/10, whole 10/10 (1s)
[PASS] dfa: mechanism: LogicalPlanBuilder::intersect_or_except implements EXCEPT ALL as a LeftAnti hash join with NullEqualsNull, so it removes every left row having any match instead; trigger ['ast:set_op:except_all', 'ast:stmt:select', 'data:setop:left_has_dups']; 4 predictions (fail on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_dups+data:table:dup_rows+data:type:integer without data:setop:left_has_null+data:setop:right_has_null+data:table:has_null; pass on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_null+data:setop:right_has_null+data:table:has_null+data:type:integer without data:setop:left_has_dups+data:table:dup_rows; fail on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_dups+data:setop:left_has_null+data:setop:right_has_null+data:table:dup_rows+data:table:has_null+data:type:integer; pass on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_dups+data:table:dup_rows+data:table:empty+data:type:integer without data:setop:left_has_null+data:setop:right_has_null+data:table:has_null); proposed as e1, accepted (0s)
[PASS] replay: 21 experiments and 25 calls replayed from the cache, identical; lanes {'bootstrap': 1, 'generalize': 5, 'bet': 5, 'implement': 7, 'refine': 3}; book {'conjectures': 3, 'rejected': 0, 'predictions': 12, 'open': 4, 'kept': 6, 'broken': 2} (54s)
S09 GATE: PASS (12/12 groups passed)
```

### S10

命令：`python -m surprise.gates.s10 2>&1 | Tee-Object -FilePath ../.orch/s10.log; exit $LASTEXITCODE`

退出码：0

```text
[PASS] isolation: 4 role modules load no model client; loop, Hunter, Diagnoser and harness never import the roles (1s)
[PASS] constants: 35 S10 constants as planned, S9 constants unchanged, library constants ['LIBRARY_ENV', 'LIBRARY_KINDS', 'LIBRARY_MIN_REFERENCES', 'LIBRARY_RULE_PREFIX', 'LIBRARY_SCHEMA'] (0s)
[PASS] frozen: harness changes since s09-done-r2: ['equivalent_query.py', 'rewrites.py']; re-frozen and verified; 12 frozen-rule outputs unchanged with and without a library (0s)
[PASS] library: 4 usable and 10 refused templates; 8 malformed libraries refused; judgements {'llm:wrap_sub': 'pass', 'llm:is_true': 'pass', 'llm:first_row': 'untrusted_rewrite/reference_disagrees', 'llm:octet': 'untrusted_rewrite/rewrite_error'}; frozen rule unchanged; no library, no trust (5s)
[PASS] frame: prior moves U 0.498 -> 1.000; extra rules offered; prepare once per round (1 rounds); vocabulary run extracts ast:set_op:except_all_two_tables (22s)
[PASS] switches: all on: calls {'implementer': 4, 'conjecturer': 1, 'prior': 3, 'translator': 1, 'vocab_inventor': 1, 'oracle_inventor': 1}; each role off: no call, no ledger line, plugin module not loaded (158s)
[PASS] prior: 20 units priced in 2 calls; evidence from the checkouts (40 lines); bad prior weight -> 0.0 after 20; useful prior weight 0.490 (1s)
[PASS] translator: DF-A family -> DuckDB translated once; settled {'tr-match': ('kept', 'match'), 'tr-mismatch': ('kept', 'mismatch'), 'tr-broken': ('broken', None), 'tr-void': ('void', None)}; bad switch refused; unmet spec retried (9s)
[PASS] vocab_inventor: accepted ast:set_op:except_all_two_tables on held-out records; refused {'empty': 'pattern', 'long': 'pattern', 'catastrophic': 'scan', 'everything': 'scan', 'no_exclusion': 'train', 'train_only': 'holdout'} and a data-layer id; prompt hides the held-out records (21s)
[PASS] oracle_inventor: accepted ['llm:wrap_sub'] on 5 instances; refused disagree, template, duplicate; 3 calls in 401 experiments; judged by the harness: pass (1s)
[PASS] translator_real: F2 (duckdb) -> datafusion: status ok, expect pass, switches []; label pass; settled kept identity None (4s)
[PASS] m3: 32 experiments and 43 calls replayed from the cache, identical; calls {'conjecturer': 2, 'oracle_inventor': 1, 'implementer': 36, 'prior': 4}; DF-B (shape|datafusion|wrong_result|-|extra_only) reached at experiment 3 via bet (bet from c1 on h1); lanes {'bootstrap': 1, 'generalize': 2, 'bet': 7, 'refine': 4, 'implement': 18} (94s)
S10 GATE: PASS (12/12 groups passed)
```

### S15 指定组

命令：`python -m surprise.gates.s15 --only config llm prices 2>&1 | Tee-Object -FilePath ../.orch/s15.log; exit $LASTEXITCODE`

退出码：0

```text
[PASS] config: new keys kept and passed to the cells; 21 bad values rejected; old defaults unchanged; 14 E1/E3 arms from EXPERIMENT.md load (0s)
[PASS] llm: gateway: unlimited, env ceiling, tier override; M3 replay identical with unlimited calls; 7 strong-tier calls went to deepseek-v4-pro; pure-LLM the same (122s)
[PASS] prices: DeepSeek prices of 2026-10-19 (peak cache-miss input, peak output) price both tiers (0s)
S15 GATE [only: config, llm, prices]: PASS (3/3 groups passed)
```

### 最终版本定向测试

命令：`python -m pytest -q tests/test_surprise_s19_notify.py 2>&1 | Tee-Object -FilePath ../.orch/notify-tests.log; exit $LASTEXITCODE`

退出码：0

```text
........................................................                 [100%]
56 passed in 25.21s
```

### 首轮完整测试（之后增加 3 个 POSIX PID 用例，并合并退出事件到轮询批次）

命令：`pytest -q testing tests 2>&1 | Tee-Object -FilePath ../.orch/pytest.log; exit $LASTEXITCODE`

退出码：0

```text
........................ss..................................s........... [  6%]
........................................................................ [ 12%]
........................................................................ [ 18%]
........................................................................ [ 25%]
........................................................................ [ 31%]
........................................................................ [ 37%]
........................................................................ [ 44%]
........................................................................ [ 50%]
........................................................................ [ 56%]
........................................................................ [ 63%]
........................................................................ [ 69%]
........................................................................ [ 75%]
........................................................................ [ 81%]
........................................................................ [ 88%]
........................................................................ [ 94%]
..............................................................           [100%]
1139 passed, 3 skipped in 444.05s (0:07:24)
```

### 首次定向收集

命令：`pytest -q tests/test_surprise_s19_notify.py`

退出码：1

```text

=================================== ERRORS ====================================
_____________ ERROR collecting tests/test_surprise_s19_notify.py ______________
ImportError while importing test module 'D:\CoevoDB\.worktrees\s19-notify\framework\tests\test_surprise_s19_notify.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
D:\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\test_surprise_s19_notify.py:16: in <module>
    from surprise.experiments import grid
E   ModuleNotFoundError: No module named 'surprise'
=========================== short test summary info ===========================
ERROR tests/test_surprise_s19_notify.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.31s
```

### 初次离线预验收

命令：`python -m surprise.gates.s19 --only pushplus reason watch balance cli`

退出码：0

```text
[PASS] pushplus: one-to-one txt message to https://www.pushplus.plus/send with the PUSHPLUS_TOKEN token in the body; codes [900, 905, 888] stop the sender, other failures do not; no token, no request (4s)
[PASS] reason: a failed call records 'TransportError: HTTPStatusError 402' (status kept, no key); other exceptions as before; 11 reasons classified (1s)
[PASS] watch: start, 402/timeout/429 streaks (once each, re-armed by a success), failed/blocked/stalled cells, finished; one message per poll, daily cap; the grid directory untouched (0s)
2026-10-20T16:12:42.536583+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-notify\.orch\tmp\coevo-s19-gate\balance\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ�key ʣ���� $0.5
2026-10-20T16:12:42.536583+00:00 balance - low key ʣ���� $0.5
2026-10-20T16:43:42.536583+00:00 balance - empty key ʣ���� $0
2026-10-20T17:14:42.536583+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-notify\.orch\tmp\coevo-s19-gate\balance-null\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ�key û�������ޣ�ֻ�ܿ�����ʧ�ܷ���Ƿ��
2026-10-20T17:14:42.536583+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-notify\.orch\tmp\coevo-s19-gate\balance-401\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ���ȼ����֤ʧ�ܣ�HTTP 401
2026-10-20T17:14:42.536583+00:00 balance - auth ��ȼ����֤ʧ�ܣ�HTTP 401
Balance check failed; will retry at the next interval.
2026-10-20T17:14:42.536583+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-notify\.orch\tmp\coevo-s19-gate\balance-down\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ���ȼ��ʧ�ܣ�ֻ�ܿ�����ʧ�ܷ���Ƿ��
2026-10-20T17:14:42.536583+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-notify\.orch\tmp\coevo-s19-gate\balance-nollm\grid����� 0��ʧ�� 0������ 0��δ��ʼ 2��ʧ�ܸ��ޣ�
2026-10-20T17:14:42.536583+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-notify\.orch\tmp\coevo-s19-gate\balance-nokey\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ�
[PASS] balance: https://openrouter.ai/api/v1/key with the DEEPSEEK_API_KEY key every 30 minutes on glm-flash grids: low and empty once each, 401 reported, no limit or no answer is no alarm (3s)
[PASS] cli: pushplus CLI exits 2 without a token; watch exits on 'finished' and on the grid process ending (--pid) (4s)
S19 GATE [only: pushplus, reason, watch, balance, cli]: PASS (5/5 groups passed)
```

### 提交前范围与空白检查（仓库根）

命令：`git diff --cached --check; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; git diff --cached --name-only; git diff --name-only; git branch --show-current`

退出码：0

```text
framework/surprise/notify/__init__.py
framework/surprise/notify/pushplus.py
framework/surprise/notify/watch.py
framework/surprise/roles/gateway.py
framework/tests/test_surprise_s19_notify.py
grok/s19-notify
```

### 提交（仓库根）

命令：`git commit -m "Add pushplus alerts and read-only grid watcher"`

退出码：0

```text
[grok/s19-notify 232febd] Add pushplus alerts and read-only grid watcher
 5 files changed, 861 insertions(+), 1 deletion(-)
 create mode 100644 framework/surprise/notify/__init__.py
 create mode 100644 framework/surprise/notify/pushplus.py
 create mode 100644 framework/surprise/notify/watch.py
 create mode 100644 framework/tests/test_surprise_s19_notify.py
```

## 与说明的偏差

无。只改允许的五个文件；每日上限按发送尝试计数（失败也占用额度），以限制故障时的请求数。未改实验、harness、transport、门槛与文档，未连接实验服务器，未打 tag、合并、rebase 或 push。

## 未决问题

无。

## 第 2 轮

审查依据：`.orch/review-1.md`。提交：`d84588b`，分支 `grok/s19-notify`。

### 改了哪些文件

- `framework/surprise/notify/watch.py`：修改停滞检查，递归读取格目录整棵树的普通文件并计入格日志；跳过遍历或 stat 时消失的文件、子目录和格目录，保留其它错误的抛出。
- `framework/surprise/notify/watch.py`：只在 run 层捕获轮询异常，逐次打印脱敏后的异常类名和消息，按原间隔继续；连续第三次失败发送一次 `[CoevoDB] 看守出错`，正文包含 OUT 与脱敏异常，一次成功轮询后重新可报。失败的轮询即使已设置 finished 也继续重试。
- `framework/surprise/notify/watch.py`：提取共用发送方法，普通事件与看守出错提醒共用 UTC 每日上限、最后名额说明和发送失败隔离逻辑；poll 内未添加宽泛异常捕获。
- `framework/tests/test_surprise_s19_notify.py`：新增 15 项离线回归用例，覆盖 SQLancer 与更深目录的活动、全树变旧、文件和目录消失、非消失错误仍从 poll 抛出、连续轮询失败去重与恢复、两种密钥脱敏、发送失败、共享每日上限及失败轮询的 finished 状态。

### 跑了哪些命令

测试与门槛工作目录为 `framework/`，git 命令在仓库根执行。以下输出原样取末 20 行；沿用 PowerShell 原生输出中的中文乱码。

完整测试：1157 passed、3 skipped，较上一轮增加 15 项通过，skip 未增加。定向测试 71 passed。S19 11/11、S09 12/12、S10 12/12、S15 指定组 3/3。全部离线。

#### 完整测试

命令：`pytest -q testing tests 2>&1 | Tee-Object -FilePath ../.orch/r2-pytest.log; exit $LASTEXITCODE`

退出码：0

```text
........................ss..................................s........... [  6%]
........................................................................ [ 12%]
........................................................................ [ 18%]
........................................................................ [ 24%]
........................................................................ [ 31%]
........................................................................ [ 37%]
........................................................................ [ 43%]
........................................................................ [ 49%]
........................................................................ [ 55%]
........................................................................ [ 62%]
........................................................................ [ 68%]
........................................................................ [ 74%]
........................................................................ [ 80%]
........................................................................ [ 86%]
........................................................................ [ 93%]
........................................................................ [ 99%]
........                                                                 [100%]
1157 passed, 3 skipped in 436.30s (0:07:16)
```

#### S19 全部门槛

命令：`python -m surprise.gates.s19 2>&1 | Tee-Object -FilePath ../.orch/r2-s19.log; exit $LASTEXITCODE`

退出码：0

```text
[PASS] replay: M3 replay: 7 calls on z-ai/glm-5.3-flash, all cache misses, manifest records the endpoint; pure-LLM: 1 calls on z-ai/glm-5.3-flash (23s)
[PASS] grid: surprise and pure-LLM arms pass --llm-tier glm-flash; unknown tiers rejected (0s)
[PASS] prices: OpenRouter prices of 2026-10-20 price z-ai/glm-5.3-flash; DeepSeek table unchanged (0s)
[PASS] pushplus: one-to-one txt message to https://www.pushplus.plus/send with the PUSHPLUS_TOKEN token in the body; codes [900, 905, 888] stop the sender, other failures do not; no token, no request (5s)
[PASS] reason: a failed call records 'TransportError: HTTPStatusError 402' (status kept, no key); other exceptions as before; 11 reasons classified (1s)
[PASS] watch: start, 402/timeout/429 streaks (once each, re-armed by a success), failed/blocked/stalled cells, finished; one message per poll, daily cap; the grid directory untouched (0s)
2026-10-20T17:12:55.446450+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-notify\.orch\tmp\coevo-s19-gate\balance\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ�key ʣ���� $0.5
2026-10-20T17:12:55.446450+00:00 balance - low key ʣ���� $0.5
2026-10-20T17:43:55.446450+00:00 balance - empty key ʣ���� $0
2026-10-20T18:14:55.446450+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-notify\.orch\tmp\coevo-s19-gate\balance-null\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ�key û�������ޣ�ֻ�ܿ�����ʧ�ܷ���Ƿ��
2026-10-20T18:14:55.446450+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-notify\.orch\tmp\coevo-s19-gate\balance-401\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ���ȼ����֤ʧ�ܣ�HTTP 401
2026-10-20T18:14:55.446450+00:00 balance - auth ��ȼ����֤ʧ�ܣ�HTTP 401
Balance check failed; will retry at the next interval.
2026-10-20T18:14:55.446450+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-notify\.orch\tmp\coevo-s19-gate\balance-down\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ���ȼ��ʧ�ܣ�ֻ�ܿ�����ʧ�ܷ���Ƿ��
2026-10-20T18:14:55.446450+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-notify\.orch\tmp\coevo-s19-gate\balance-nollm\grid����� 0��ʧ�� 0������ 0��δ��ʼ 2��ʧ�ܸ���
2026-10-20T18:14:55.446450+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-notify\.orch\tmp\coevo-s19-gate\balance-nokey\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ���
[PASS] balance: https://openrouter.ai/api/v1/key with the DEEPSEEK_API_KEY key every 30 minutes on glm-flash grids: low and empty once each, 401 reported, no limit or no answer is no alarm (4s)
[PASS] cli: pushplus CLI exits 2 without a token; watch exits on 'finished' and on the grid process ending (--pid) (5s)
[PASS] scope: 29 paths changed (s15-done-r3..work tree), all in scope; harness and roles/constants.py untouched (0s)
S19 GATE: PASS (11/11 groups passed)
```

#### S09

命令：`python -m surprise.gates.s09 2>&1 | Tee-Object -FilePath ../.orch/r2-s09.log; exit $LASTEXITCODE`

退出码：0

```text
[PASS] isolation: roles load no model client until a transport is built; loop, Hunter, Diagnoser, harness never import them; transport reuses BaseAgent and the old ledger (1s)
[PASS] constants: 19 constants as planned; tiers {'fast': 'deepseek-flash', 'strong': 'deepseek-v4-pro'} (0s)
[PASS] cache: key = prompt hash + model + seed; hits make no call; replay identical; forged entry refused; ledger and per-role totals (0s)
[PASS] reject: 9 replies parsed as planned; refusals replay as refusals; the implementer refuses before phi (0s)
[PASS] cap: cap 2 blocks the third call; cache served past the cap; cap 0 calls nothing; env ceiling; errors count, not cached (0s)
[PASS] source: confined, exact, read-only; checkouts at datafusion 45d943dfb869, duckdb d8cdaa33fda8 (0s)
[PASS] implementer: accepted, retried with feedback, unmet, bad case, replayed, blocked (0s)
[PASS] conjecturer: selection picks datafusion/expr/src/logical_plan/builder.rs for DF-A and src/optimizer/filter_pushdown.cpp for ('filter_pushdown',); registered with a revise whose bets are its predictions; settled by experiments; refusals, drops, not covering, blocked (11s)
[PASS] wiring: off: 40 rows identical to S8, no role loaded; on: 7 scripted calls, 0 implementer experiments meeting their specs; cap 0 completes (56s)
[PASS] implementer_report: phi-check pass rate 0.97 at the first try, 1.00 after 2 tries (30/30); boundary 10/10, core 10/10, whole 10/10 (1s)
[PASS] dfa: mechanism: LogicalPlanBuilder::intersect_or_except implements EXCEPT ALL as a LeftAnti hash join with NullEqualsNull, so it removes every left row having any match instead; trigger ['ast:set_op:except_all', 'ast:stmt:select', 'data:setop:left_has_dups']; 4 predictions (fail on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_dups+data:table:dup_rows+data:type:integer without data:setop:left_has_null+data:setop:right_has_null+data:table:has_null; pass on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_null+data:setop:right_has_null+data:table:has_null+data:type:integer without data:setop:left_has_dups+data:table:dup_rows; fail on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_dups+data:setop:left_has_null+data:setop:right_has_null+data:table:dup_rows+data:table:has_null+data:type:integer; pass on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_dups+data:table:dup_rows+data:table:empty+data:type:integer without data:setop:left_has_null+data:setop:right_has_null+data:table:has_null); proposed as e1, accepted (0s)
[PASS] replay: 21 experiments and 25 calls replayed from the cache, identical; lanes {'bootstrap': 1, 'generalize': 5, 'bet': 5, 'implement': 7, 'refine': 3}; book {'conjectures': 3, 'rejected': 0, 'predictions': 12, 'open': 4, 'kept': 6, 'broken': 2} (52s)
S09 GATE: PASS (12/12 groups passed)
```

#### S10

命令：`python -m surprise.gates.s10 2>&1 | Tee-Object -FilePath ../.orch/r2-s10.log; exit $LASTEXITCODE`

退出码：0

```text
[PASS] isolation: 4 role modules load no model client; loop, Hunter, Diagnoser and harness never import the roles (1s)
[PASS] constants: 35 S10 constants as planned, S9 constants unchanged, library constants ['LIBRARY_ENV', 'LIBRARY_KINDS', 'LIBRARY_MIN_REFERENCES', 'LIBRARY_RULE_PREFIX', 'LIBRARY_SCHEMA'] (0s)
[PASS] frozen: harness changes since s09-done-r2: ['equivalent_query.py', 'rewrites.py']; re-frozen and verified; 12 frozen-rule outputs unchanged with and without a library (0s)
[PASS] library: 4 usable and 10 refused templates; 8 malformed libraries refused; judgements {'llm:wrap_sub': 'pass', 'llm:is_true': 'pass', 'llm:first_row': 'untrusted_rewrite/reference_disagrees', 'llm:octet': 'untrusted_rewrite/rewrite_error'}; frozen rule unchanged; no library, no trust (5s)
[PASS] frame: prior moves U 0.498 -> 1.000; extra rules offered; prepare once per round (1 rounds); vocabulary run extracts ast:set_op:except_all_two_tables (22s)
[PASS] switches: all on: calls {'implementer': 4, 'conjecturer': 1, 'prior': 3, 'translator': 1, 'vocab_inventor': 1, 'oracle_inventor': 1}; each role off: no call, no ledger line, plugin module not loaded (151s)
[PASS] prior: 20 units priced in 2 calls; evidence from the checkouts (40 lines); bad prior weight -> 0.0 after 20; useful prior weight 0.490 (1s)
[PASS] translator: DF-A family -> DuckDB translated once; settled {'tr-match': ('kept', 'match'), 'tr-mismatch': ('kept', 'mismatch'), 'tr-broken': ('broken', None), 'tr-void': ('void', None)}; bad switch refused; unmet spec retried (9s)
[PASS] vocab_inventor: accepted ast:set_op:except_all_two_tables on held-out records; refused {'empty': 'pattern', 'long': 'pattern', 'catastrophic': 'scan', 'everything': 'scan', 'no_exclusion': 'train', 'train_only': 'holdout'} and a data-layer id; prompt hides the held-out records (21s)
[PASS] oracle_inventor: accepted ['llm:wrap_sub'] on 5 instances; refused disagree, template, duplicate; 3 calls in 401 experiments; judged by the harness: pass (1s)
[PASS] translator_real: F2 (duckdb) -> datafusion: status ok, expect pass, switches []; label pass; settled kept identity None (4s)
[PASS] m3: 32 experiments and 43 calls replayed from the cache, identical; calls {'conjecturer': 2, 'oracle_inventor': 1, 'implementer': 36, 'prior': 4}; DF-B (shape|datafusion|wrong_result|-|extra_only) reached at experiment 3 via bet (bet from c1 on h1); lanes {'bootstrap': 1, 'generalize': 2, 'bet': 7, 'refine': 4, 'implement': 18} (92s)
S10 GATE: PASS (12/12 groups passed)
```

#### S15 指定组

命令：`python -m surprise.gates.s15 --only config llm prices 2>&1 | Tee-Object -FilePath ../.orch/r2-s15.log; exit $LASTEXITCODE`

退出码：0

```text
[PASS] config: new keys kept and passed to the cells; 21 bad values rejected; old defaults unchanged; 14 E1/E3 arms from EXPERIMENT.md load (0s)
[PASS] llm: gateway: unlimited, env ceiling, tier override; M3 replay identical with unlimited calls; 7 strong-tier calls went to deepseek-v4-pro; pure-LLM the same (120s)
[PASS] prices: DeepSeek prices of 2026-10-19 (peak cache-miss input, peak output) price both tiers (0s)
S15 GATE [only: config, llm, prices]: PASS (3/3 groups passed)
```

#### 通知定向测试

命令：`python -m pytest -q tests/test_surprise_s19_notify.py 2>&1 | Tee-Object -FilePath ../.orch/r2-notify-tests.log; exit $LASTEXITCODE`

退出码：0

```text
.......................................................................  [100%]
71 passed in 21.42s
```

#### 暂存与范围检查

命令：`git add -- framework/surprise/notify/watch.py framework/tests/test_surprise_s19_notify.py; git diff --cached --check; git diff --cached --stat; git diff --cached --name-only`

退出码：0

```text
warning: in the working copy of 'framework/surprise/notify/watch.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'framework/tests/test_surprise_s19_notify.py', LF will be replaced by CRLF the next time Git touches it
 framework/surprise/notify/watch.py          |  59 +++++++--
 framework/tests/test_surprise_s19_notify.py | 198 ++++++++++++++++++++++++++++
 2 files changed, 244 insertions(+), 13 deletions(-)
framework/surprise/notify/watch.py
framework/tests/test_surprise_s19_notify.py
```

#### 提交前检查

命令：`git diff --cached --check; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; git diff --exit-code; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; git diff --cached --name-only; git branch --show-current`

退出码：0

```text
framework/surprise/notify/watch.py
framework/tests/test_surprise_s19_notify.py
grok/s19-notify
```

#### 提交

命令：`git commit -m "Fix recursive activity checks and watcher failure recovery"`

退出码：0

```text
[grok/s19-notify d84588b] Fix recursive activity checks and watcher failure recovery
 2 files changed, 244 insertions(+), 13 deletions(-)
```

### 与说明的偏差

无。活动范围和 run 异常恢复行为按本轮审查明确修订；允许路径、禁区和其余约束保持原样。仅提交上述两个允许的文件，未连接服务器，未发送真实通知或 OpenRouter 请求，未打 tag、合并、rebase 或 push。

### 未决问题

无。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：
