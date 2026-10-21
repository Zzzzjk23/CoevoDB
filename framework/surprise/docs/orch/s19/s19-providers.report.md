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

