# 审查包 · s19-providers

- 生成时间：2026-10-21T19:39:18+11:00
- 基线：`session/s19`（58993e8a24c5）
- 分支：`grok/s19-providers` @ 31d2620b7128，基线之上 1 个提交
- 运行：共 1 轮（返工 0 轮），最近一轮退出码 0，用时 13m51s
- 执行者：codex codex-cli 0.163.0；会话 `01a15d90-30ce-72f1-ae85-c3c78f3c9970`

## 红旗汇总

- 门槛未通过（退出码 1）
- 测试里被改写的断言 7 处（逐条确认没有放宽）
- 执行者日志里有 2 行疑似密钥（日志不入库，但要查来源）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s19..grok/s19-providers
git diff -M --stat session/s19..grok/s19-providers
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/roles/constants.py`、`framework/surprise/roles/providers.py`、`framework/surprise/roles/transport.py`、`framework/surprise/roles/gateway.py`、`framework/surprise/metrics/data/prices_openrouter.json`、`framework/tests/test_surprise_s19_glm.py`、`framework/tests/test_surprise_s19_retry.py`、`framework/tests/test_surprise_s19_providers.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/metrics/data/prices_openrouter.json` |  |
| M | `framework/surprise/roles/constants.py` |  |
| M | `framework/surprise/roles/gateway.py` |  |
| M | `framework/surprise/roles/providers.py` |  |
| M | `framework/surprise/roles/transport.py` |  |
| M | `framework/tests/test_surprise_s19_glm.py` |  |
| A | `framework/tests/test_surprise_s19_providers.py` |  |
| M | `framework/tests/test_surprise_s19_retry.py` |  |

提交：

- 31d2620 Junke: Retry 429 and 503 across ordered LLM providers

## 2. diff 统计

```text
 .../surprise/metrics/data/prices_openrouter.json   |  13 +-
 framework/surprise/roles/constants.py              |   5 +-
 framework/surprise/roles/gateway.py                |  44 +--
 framework/surprise/roles/providers.py              |   2 +-
 framework/surprise/roles/transport.py              |  39 ++-
 framework/tests/test_surprise_s19_glm.py           |  18 +-
 framework/tests/test_surprise_s19_providers.py     | 306 +++++++++++++++++++++
 framework/tests/test_surprise_s19_retry.py         |  62 +++--
 8 files changed, 427 insertions(+), 62 deletions(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，7m08s；passed 1205，skipped 3

```text
........................ss..................................s........... [  5%]
........................................................................ [ 11%]
........................................................................ [ 17%]
........................................................................ [ 23%]
........................................................................ [ 29%]
........................................................................ [ 35%]
........................................................................ [ 41%]
........................................................................ [ 47%]
........................................................................ [ 53%]
........................................................................ [ 59%]
........................................................................ [ 65%]
........................................................................ [ 71%]
........................................................................ [ 77%]
........................................................................ [ 83%]
........................................................................ [ 89%]
........................................................................ [ 95%]
........................................................                 [100%]
1205 passed, 3 skipped in 427.53s (0:07:07)
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，30m00s

```text
[PASS] switches: all on: calls {'implementer': 4, 'conjecturer': 1, 'prior': 3, 'translator': 1, 'vocab_inventor': 1, 'oracle_inventor': 1}; each role off: no call, no ledger line, plugin module not loaded (127s)
[PASS] prior: 20 units priced in 2 calls; evidence from the checkouts (40 lines); bad prior weight -> 0.0 after 20; useful prior weight 0.490 (1s)
[PASS] translator: DF-A family -> DuckDB translated once; settled {'tr-match': ('kept', 'match'), 'tr-mismatch': ('kept', 'mismatch'), 'tr-broken': ('broken', None), 'tr-void': ('void', None)}; bad switch refused; unmet spec retried (8s)
[PASS] vocab_inventor: accepted ast:set_op:except_all_two_tables on held-out records; refused {'empty': 'pattern', 'long': 'pattern', 'catastrophic': 'scan', 'everything': 'scan', 'no_exclusion': 'train', 'train_only': 'holdout'} and a data-layer id; prompt hides the held-out records (21s)
[PASS] oracle_inventor: accepted ['llm:wrap_sub'] on 5 instances; refused disagree, template, duplicate; 3 calls in 401 experiments; judged by the harness: pass (1s)
[PASS] translator_real: F2 (duckdb) -> datafusion: status ok, expect pass, switches []; label pass; settled kept identity None (4s)
[PASS] m3: 32 experiments and 43 calls replayed from the cache, identical; calls {'conjecturer': 2, 'oracle_inventor': 1, 'implementer': 36, 'prior': 4}; DF-B (shape|datafusion|wrong_result|-|extra_only) reached at experiment 3 via bet (bet from c1 on h1); lanes {'bootstrap': 1, 'generalize': 2, 'bet': 7, 'refine': 4, 'implement': 18} (85s)
S10 GATE: PASS (12/12 groups passed)
=== gate s11 ===
[PASS] constants: 7 metric constants, request deadline 600.0 s, pure-LLM constants and 10 topics (0s)
[PASS] store: 6 replace calls for 3 transient failures (0.38s); a lasting failure raises PermissionError (2s)
[PASS] loop_error: original exception kept and written to error.txt (both, drive) (1s)
[PASS] deadline: normal answer passes; deadline 1.5s held (trickle 2.0s, silent 1.9s); errors booked, not cached (10s)
[PASS] vocabulary: run_registry, new_families, compare, recall.score, RunData and run_metrics all read the run's vocabulary (34s)
[PASS] stats: exact and asymptotic MWU (scipy agrees), A12, median, summarize as hand-computed (1s)
[PASS] runmetrics: 31 records, 1 ledger families, Brier 0.2194, 1 high-surprise records, invalid 14, theory length 193.0; all recomputed (0s)
[FAIL] ciao: artifact directory results/s08/longrun is missing on this machine
[PASS] llm_metrics: 15 experiments replayed; 2 conjectures, survival 0.0, accuracy 0.7142857142857143 over 7 settled bets; families via {'implement': 0, 'bet': 1, 'translate': 0, 'llm_rule': 0, 'invented_feature': 0}; 23 calls (33s)
[PASS] rq6: classify, F2 fix conditions (1 entries), pair agreement as hand-computed; F2 hypothesis too_narrow (missing [], extra 9 literals); recall 0.5 (4s)
[PASS] arms: random Hunter deterministic and different; frozen theory unchanged (1 failures fully profiled); frozen Diagnoser no edits; theory-from and select-from (5 choices scored differently); 5 usage errors refused (94s)
[PASS] pure_llm_script: 4 cases executed from 3 calls (1 reply rejected, 2 bad cases skipped); prompts deterministic; budget holds (4s)
[PASS] pure_llm: 16 cases from 4 cached calls replayed identically; labels {'pass': 15, 'invalid': 1}; 0 families (7s)
[PASS] dedup: 3 failures, 1 true duplicates; sigma p/r 1.0/1.0, membership p/r None/0.0 (6s)
[PASS] coverage: 4 upstream regression seeds x 2 oracles on 1.5.5 and 1.1.3; {'plan_variant': {'old': {'pass': 4}, 'new': {'pass': 4}, 'fail_old_pass_new': [], 'fail_both': [], 'fail_new_only': []}, 'equivalent_query': {'old': {'invalid': 4}, 'new': {'invalid': 4}, 'fail_old_pass_new': [], 'fail_both': [], 'fail_new_only': []}} (7s)
[PASS] sqlancer: 35 runs, 0 bugs; per engine rows match docs/FINAL_REPORT.md (0s)
```

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- `framework/tests/test_surprise_s19_glm.py:223` 原：`prices["grid"]) == pytest.approx(0.357476)` → 同一处新增：`prices["grid"]) == pytest.approx(0.39)`
- `framework/tests/test_surprise_s19_retry.py:146` 原：`assert len(wire.requests) == len(expected) + 1` → 同一处新增：`assert len(wire.requests) == attempts`；`assert wire.sleeps == expected * len(PROVIDERS)`
- `framework/tests/test_surprise_s19_retry.py:147` 原：`assert wire.sleeps == expected` → 同一处新增：`assert len(wire.requests) == attempts`；`assert wire.sleeps == expected * len(PROVIDERS)`
- `framework/tests/test_surprise_s19_retry.py:150` 原：`assert captured.err.splitlines() == _lines(expected)` → 同一处新增：`assert captured.err.splitlines() == _exhausted_lines(expected)`
- `framework/tests/test_surprise_s19_retry.py:190` 原：`with pytest.raises(TransportError, match="^HTTPStatusError 503$"):` → 同一处新增：`with pytest.raises(TransportError, match="^HTTPStatusError 402$"):`
- `framework/tests/test_surprise_s19_retry.py:230` 原：`assert len(wire.requests) == (5 if exhausted else 3)` → 同一处新增：`assert len(wire.requests) == (15 if exhausted else 3)`
- `framework/tests/test_surprise_s19_retry.py:235` 原：`assert len(wire.requests) == (5 if exhausted else 3)` → 同一处新增：`assert len(wire.requests) == (15 if exhausted else 3)`

### 4.4 新增的宽泛异常捕获

- 无

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s19-providers.jsonl` 与 stderr 中疑似密钥行数：2

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 无

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s19-providers.jsonl`：72 条事件（item.completed 39，item.started 28，orch.exit 1，orch.start 1，thread.started 1，turn.completed 1，turn.started 1）；各轮合计 codex：1 轮，输入 2718016 token（其中缓存 2628480），输出 17452（其中推理 4656），codex 不报美元。

被 deny 规则（grok）或 execpolicy 规则（codex，记在 stderr）拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
exec [exit 0]: [grok/s19-providers 31d2620] Retry 429 and 503 across ordered LLM providers 8 files changed, 427 insertions(+), 62 deletions(-) create mode 100644 framework/tests/test_surprise_s1…
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short; git log -1 --format="%H%n%s"; git show --stat --oneline HEAD'
exec [exit 0]: 31d2620b71280760398a263036fd7badbdd2625e Retry 429 and 503 across ordered LLM providers 31d2620 Retry 429 and 503 across ordered LLM providers .../surprise/metrics/data/prices_ope…
file_change [completed]: add D:\CoevoDB\.worktrees\s19-providers\.orch\report.md
text: 全部验收已通过：1205 passed、3 skipped；S19、S09、S10 均为 12/12，S15 指定组为 3/3。已提交 `31d2620`，执行报告已写入 `.orch/report.md`，正在确认提交后的工作区状态。
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Encoding UTF8 .orch/report.md | Select-Object -First 22; Get-Content -Encoding UTF8 .orch/r…
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short'
exec [exit 0]: # s19-providers 执行报告 提交：`31d2620b71280760398a263036fd7badbdd2625e` 分支：`grok/s19-providers` ## 改动文件 - `framework/surprise/roles/constants.py`：新增 `RETRY_STATUSES = [429, 503]`，等待序列和…
exec [exit 0]: 
text: 已完成并提交 `31d2620`，工作区干净。 - 测试：1205 passed，3 skipped。 - 门槛：S19、S09、S10 均 12/12；S15 指定组 3/3。 - 偏差与未决问题：无。 报告：[.orch/report.md](D:/CoevoDB/.worktrees/s19-providers/.orch/report.md)。
end: tokens in=2718016 cached=2628480 out=17452 reasoning=4656
orch.exit: {"pkg": "s19-providers", "run": 1, "at": "2026-10-21T19:38:44+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# s19-providers 执行报告

提交：`31d2620b71280760398a263036fd7badbdd2625e`
分支：`grok/s19-providers`

## 改动文件

- `framework/surprise/roles/constants.py`：新增 `RETRY_STATUSES = [429, 503]`，等待序列和其他常数保持原值。
- `framework/surprise/roles/providers.py`：GLM 端点改为 sail-research/fp4、open-inference/fp4、sail-research/us 的有序列表，body 只保留 reasoning。
- `framework/surprise/roles/transport.py`：每家独立退避，重试耗尽后立即切换；其他失败立即抛出；记录回答方和总重发次数，保持每次尝试的完整 deadline。
- `framework/surprise/roles/gateway.py`：Completion / Reply 携带 provider；有值时写入 calls.jsonl 和缓存，回放时恢复；DeepSeek 键集保持不变。
- `framework/surprise/metrics/data/prices_openrouter.json`：与 s19_cases.PRICES 一致的 2026-10-21 三家价格，grid 按第一家计算。
- `framework/tests/test_surprise_s19_glm.py`：同步 profile、请求字节与价格期望。
- `framework/tests/test_surprise_s19_retry.py`：同步 503 重试、逐家耗尽与诊断期望，覆盖两种可重试状态。
- `framework/tests/test_surprise_s19_providers.py`：新增 23 个离线用例，覆盖三家回答/耗尽、切换、非重试错误、空等待、deadline、账本次数、缓存回放、旧 Completion 与 DeepSeek 键集。

## 验证命令

以下测试和门槛均在 `framework/` 执行；git 命令在 worktree 根执行。全部验收命令通过：1205 passed、3 skipped（原基线 1180 passed、3 skipped，增加 25 个通过用例，skip 数不变）。所有传输测试使用本地模拟请求与假凭据，没有真实 LLM 调用；未连接实验服务器。

### `python -m pytest -q tests/test_surprise_s19_glm.py tests/test_surprise_s19_retry.py tests/test_surprise_s19_providers.py`

退出码：0

输出末 20 行（不足 20 行则全部列出）：

```text
................................................................         [100%]
64 passed in 25.74s
```

### `python -m pytest -q testing tests`

退出码：0

输出末 20 行（不足 20 行则全部列出）：

```text
........................ss..................................s........... [  5%]
........................................................................ [ 11%]
........................................................................ [ 17%]
........................................................................ [ 23%]
........................................................................ [ 29%]
........................................................................ [ 35%]
........................................................................ [ 41%]
........................................................................ [ 47%]
........................................................................ [ 53%]
........................................................................ [ 59%]
........................................................................ [ 65%]
........................................................................ [ 71%]
........................................................................ [ 77%]
........................................................................ [ 83%]
........................................................................ [ 89%]
........................................................................ [ 95%]
........................................................                 [100%]
1205 passed, 3 skipped in 460.76s (0:07:40)
```

### `python -m surprise.gates.s19`

退出码：0

输出末 20 行（不足 20 行则全部列出）：

```text
[PASS] grid: surprise and pure-LLM arms pass --llm-tier glm-flash; unknown tiers rejected (0s)
[PASS] prices: OpenRouter prices of 2026-10-21 price z-ai/glm-5.3-flash; DeepSeek table unchanged (0s)
[PASS] pushplus: one-to-one txt message to https://www.pushplus.plus/send with the PUSHPLUS_TOKEN token in the body; codes [900, 905, 888] stop the sender, other failures do not; no token, no request (5s)
[PASS] reason: a failed call records 'TransportError: HTTPStatusError 402' (status kept, no key); other exceptions as before; 11 reasons classified (1s)
[PASS] watch: start, 402/timeout/429 streaks (once each, re-armed by a success), failed/blocked/stalled cells, finished; one message per poll, daily cap; the grid directory untouched (0s)
2026-10-21T08:30:16.625236+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-providers\.orch\tmp\coevo-s19-gate\balance\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ�key ʣ���� $0.5
2026-10-21T08:30:16.625236+00:00 balance - low key ʣ���� $0.5
2026-10-21T09:01:16.625236+00:00 balance - empty key ʣ���� $0
2026-10-21T09:32:16.625236+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-providers\.orch\tmp\coevo-s19-gate\balance-null\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ�key û�������ޣ�ֻ�ܿ�����ʧ�ܷ���Ƿ��
2026-10-21T09:32:16.625236+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-providers\.orch\tmp\coevo-s19-gate\balance-401\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ���ȼ����֤ʧ�ܣ�HTTP 401
2026-10-21T09:32:16.625236+00:00 balance - auth ��ȼ����֤ʧ�ܣ�HTTP 401
Balance check failed; will retry at the next interval.
2026-10-21T09:32:16.625236+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-providers\.orch\tmp\coevo-s19-gate\balance-down\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ���ȼ��ʧ�ܣ�ֻ�ܿ�����ʧ�ܷ���Ƿ��
2026-10-21T09:32:16.625236+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-providers\.orch\tmp\coevo-s19-gate\balance-nollm\grid����� 0��ʧ�� 0������ 0��δ��ʼ 2��ʧ�ܸ���
2026-10-21T09:32:16.625236+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-providers\.orch\tmp\coevo-s19-gate\balance-nokey\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ���
[PASS] balance: https://openrouter.ai/api/v1/key with the DEEPSEEK_API_KEY key every 30 minutes on glm-flash grids: low and empty once each, 401 reported, no limit or no answer is no alarm (4s)
[PASS] cli: pushplus CLI exits 2 without a token; watch exits on 'finished' and on the grid process ending (--pid) (5s)
[PASS] retry: RATE_LIMIT_WAITS_S = [10.0, 30.0, 60.0, 120.0], RETRY_STATUSES = [429, 503] added, other constants as at s15-done-r3; 429/503 retried per provider, then sail-research/fp4 -> open-inference/fp4 -> sail-research/us; 7 statuses, connection errors and null content neither retried nor switched; provider recorded and replayed (GLM only); one gateway call, cap unit and row per call (1s)
[PASS] scope: 49 paths changed (s15-done-r3..work tree), all in scope; harness untouched (0s)
S19 GATE: PASS (12/12 groups passed)
```

### `python -m surprise.gates.s09`

退出码：0

输出末 20 行（不足 20 行则全部列出）：

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

### `python -m surprise.gates.s10`

退出码：0

输出末 20 行（不足 20 行则全部列出）：

```text
[PASS] isolation: 4 role modules load no model client; loop, Hunter, Diagnoser and harness never import the roles (1s)
[PASS] constants: 35 S10 constants as planned, S9 constants unchanged, library constants ['LIBRARY_ENV', 'LIBRARY_KINDS', 'LIBRARY_MIN_REFERENCES', 'LIBRARY_RULE_PREFIX', 'LIBRARY_SCHEMA'] (0s)
[PASS] frozen: harness changes since s09-done-r2: ['equivalent_query.py', 'rewrites.py']; re-frozen and verified; 12 frozen-rule outputs unchanged with and without a library (0s)
[PASS] library: 4 usable and 10 refused templates; 8 malformed libraries refused; judgements {'llm:wrap_sub': 'pass', 'llm:is_true': 'pass', 'llm:first_row': 'untrusted_rewrite/reference_disagrees', 'llm:octet': 'untrusted_rewrite/rewrite_error'}; frozen rule unchanged; no library, no trust (5s)
[PASS] frame: prior moves U 0.498 -> 1.000; extra rules offered; prepare once per round (1 rounds); vocabulary run extracts ast:set_op:except_all_two_tables (22s)
[PASS] switches: all on: calls {'implementer': 4, 'conjecturer': 1, 'prior': 3, 'translator': 1, 'vocab_inventor': 1, 'oracle_inventor': 1}; each role off: no call, no ledger line, plugin module not loaded (150s)
[PASS] prior: 20 units priced in 2 calls; evidence from the checkouts (40 lines); bad prior weight -> 0.0 after 20; useful prior weight 0.490 (1s)
[PASS] translator: DF-A family -> DuckDB translated once; settled {'tr-match': ('kept', 'match'), 'tr-mismatch': ('kept', 'mismatch'), 'tr-broken': ('broken', None), 'tr-void': ('void', None)}; bad switch refused; unmet spec retried (8s)
[PASS] vocab_inventor: accepted ast:set_op:except_all_two_tables on held-out records; refused {'empty': 'pattern', 'long': 'pattern', 'catastrophic': 'scan', 'everything': 'scan', 'no_exclusion': 'train', 'train_only': 'holdout'} and a data-layer id; prompt hides the held-out records (21s)
[PASS] oracle_inventor: accepted ['llm:wrap_sub'] on 5 instances; refused disagree, template, duplicate; 3 calls in 401 experiments; judged by the harness: pass (1s)
[PASS] translator_real: F2 (duckdb) -> datafusion: status ok, expect pass, switches []; label pass; settled kept identity None (4s)
[PASS] m3: 32 experiments and 43 calls replayed from the cache, identical; calls {'conjecturer': 2, 'oracle_inventor': 1, 'implementer': 36, 'prior': 4}; DF-B (shape|datafusion|wrong_result|-|extra_only) reached at experiment 3 via bet (bet from c1 on h1); lanes {'bootstrap': 1, 'generalize': 2, 'bet': 7, 'refine': 4, 'implement': 18} (91s)
S10 GATE: PASS (12/12 groups passed)
```

### `python -m surprise.gates.s15 --only config llm prices`

退出码：0

输出末 20 行（不足 20 行则全部列出）：

```text
[PASS] config: new keys kept and passed to the cells; 21 bad values rejected; old defaults unchanged; 14 E1/E3 arms from EXPERIMENT.md load (0s)
[PASS] llm: gateway: unlimited, env ceiling, tier override; M3 replay identical with unlimited calls; 7 strong-tier calls went to deepseek-v4-pro; pure-LLM the same (119s)
[PASS] prices: DeepSeek prices of 2026-10-19 (peak cache-miss input, peak output) price both tiers (0s)
S15 GATE [only: config, llm, prices]: PASS (3/3 groups passed)
```

### `git diff --check`

退出码：0

输出末 20 行（不足 20 行则全部列出）：

```text

```

### `git commit -m "Retry 429 and 503 across ordered LLM providers"`

退出码：0

输出末 20 行（不足 20 行则全部列出）：

```text
[grok/s19-providers 31d2620] Retry 429 and 503 across ordered LLM providers
 8 files changed, 427 insertions(+), 62 deletions(-)
 create mode 100644 framework/tests/test_surprise_s19_providers.py
```

### `git status --short`

退出码：0

输出为空，工作区干净；本报告位于被 git 忽略的 `.orch/`，不入库。

## 与说明的偏差

无。

## 未决问题

无。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：
