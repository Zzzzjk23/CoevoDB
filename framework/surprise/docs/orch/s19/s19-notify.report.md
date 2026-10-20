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

