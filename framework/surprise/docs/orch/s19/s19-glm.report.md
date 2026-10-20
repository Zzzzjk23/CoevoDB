# 报告 · s19-glm

状态：完成。提交：`342727f1ff53baf0e40e113cf7cadebd1a2e17e3`（`grok/s19-glm`）。工作区干净；本报告按说明不入库。

验收：1086 passed、3 skipped；S19 6/6、S09 12/12、S10 12/12、S15 指定 config/llm/prices 3/3 全部通过。

## 改了哪些文件

- `framework/surprise/roles/providers.py`：新增 glm-flash 的模型、OpenRouter 地址、指定 provider、不回退及推理配置；提供返回独立副本的查询函数。
- `framework/surprise/roles/gateway.py`：接受额外档位，按新模型生成缓存键、回复及调用记账；新档 manifest 记录 endpoint。
- `framework/surprise/roles/runtime.py`：新档运行 manifest 的 llm 节记录 endpoint。
- `framework/surprise/roles/transport.py`：新模型经现有 httpx 客户端请求 OpenRouter；沿用原鉴权、回复解析、截止时间和错误处理。
- `framework/surprise/experiments/grid.py`：网格档位接受 glm-flash 并沿用命令行参数转发。
- `framework/surprise/experiments/loop.py`：主循环配置与命令行接受 glm-flash。
- `framework/surprise/baselines/pure_llm.py`：纯 LLM 基线的配置与命令行接受 glm-flash。
- `framework/surprise/metrics/data/prices_openrouter.json`：新增与验收案例一致的 2026-10-20 OpenRouter 价格表。
- `framework/tests/test_surprise_s19_glm.py`：新增 16 个离线测试，覆盖请求字节、路由、鉴权来源、错误、缓存隔离、记账、manifest、网格、CLI 和价格。

## 跑了哪些命令

以下命令均在 worktree 的 framework 目录执行，列出退出码与原样输出末 20 行。

### `pytest -q tests/test_surprise_s19_glm.py`

退出码：1。

附加单文件探测未加载 testing/conftest.py 的项目导入路径设置；未修改 conftest 或更换解释器。

```text
=================================== ERRORS ====================================
_______________ ERROR collecting tests/test_surprise_s19_glm.py _______________
ImportError while importing test module 'D:\CoevoDB\.worktrees\s19-glm\framework\tests\test_surprise_s19_glm.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
D:\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\test_surprise_s19_glm.py:12: in <module>
    from surprise.baselines import pure_llm
E   ModuleNotFoundError: No module named 'surprise'
=========================== short test summary info ===========================
ERROR tests/test_surprise_s19_glm.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.34s
```

### `pytest -q testing tests（首次）`

退出码：1。

仅本包新增的两个网格测试缺少 max_calls；已补齐有效配置，保留全部断言。

```text
        if unknown:
            raise ValueError(f"{where}: unknown keys {unknown}")
        if _absent(value, "cache"):
            cache = None
        else:
            cache = _require_text(value["cache"], f"{where}.cache")
        offline = False if _absent(value, "offline") else _require_bool(value["offline"], f"{where}.offline")
        if _absent(value, "max_calls"):
            max_calls = None
        else:
            max_calls = _require_max_calls(value["max_calls"], f"{where}.max_calls")
        if not offline and max_calls is None:
>           raise ValueError(f"{where}.max_calls: required when not offline")
E           ValueError: arms[0].llm.max_calls: required when not offline

surprise\experiments\grid.py:507: ValueError
=========================== short test summary info ===========================
FAILED tests/test_surprise_s19_glm.py::test_grid_passes_glm_tier_and_rejects_unknown[surprise]
FAILED tests/test_surprise_s19_glm.py::test_grid_passes_glm_tier_and_rejects_unknown[pure_llm]
2 failed, 1084 passed, 3 skipped in 431.13s (0:07:11)
```

### `python -m surprise.gates.s19`

退出码：0。

```text
[PASS] transport: z-ai/glm-5.3-flash -> https://openrouter.ai/api/v1/chat/completions with provider/reasoning and the DEEPSEEK_API_KEY key; DeepSeek requests unchanged; 402/429/null content raise TransportError; 7 requests, none on the network (1s)
[PASS] gateway: tier glm-flash -> z-ai/glm-5.3-flash on every call, own cache key, recorded with its endpoint; no override: DeepSeek and the old manifest keys (0s)
[PASS] replay: M3 replay: 7 calls on z-ai/glm-5.3-flash, all cache misses, manifest records the endpoint; pure-LLM: 1 calls on z-ai/glm-5.3-flash (24s)
[PASS] grid: surprise and pure-LLM arms pass --llm-tier glm-flash; unknown tiers rejected (0s)
[PASS] prices: OpenRouter prices of 2026-10-20 price z-ai/glm-5.3-flash; DeepSeek table unchanged (0s)
[PASS] scope: 21 paths changed (s15-done-r3..work tree), all in scope; harness and roles/constants.py untouched (0s)
S19 GATE: PASS (6/6 groups passed)
```

### `python -m surprise.gates.s09`

退出码：0。

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
[PASS] replay: 21 experiments and 25 calls replayed from the cache, identical; lanes {'bootstrap': 1, 'generalize': 5, 'bet': 5, 'implement': 7, 'refine': 3}; book {'conjectures': 3, 'rejected': 0, 'predictions': 12, 'open': 4, 'kept': 6, 'broken': 2} (53s)
S09 GATE: PASS (12/12 groups passed)
```

### `python -m surprise.gates.s10`

退出码：0。

```text
[PASS] isolation: 4 role modules load no model client; loop, Hunter, Diagnoser and harness never import the roles (1s)
[PASS] constants: 35 S10 constants as planned, S9 constants unchanged, library constants ['LIBRARY_ENV', 'LIBRARY_KINDS', 'LIBRARY_MIN_REFERENCES', 'LIBRARY_RULE_PREFIX', 'LIBRARY_SCHEMA'] (0s)
[PASS] frozen: harness changes since s09-done-r2: ['equivalent_query.py', 'rewrites.py']; re-frozen and verified; 12 frozen-rule outputs unchanged with and without a library (0s)
[PASS] library: 4 usable and 10 refused templates; 8 malformed libraries refused; judgements {'llm:wrap_sub': 'pass', 'llm:is_true': 'pass', 'llm:first_row': 'untrusted_rewrite/reference_disagrees', 'llm:octet': 'untrusted_rewrite/rewrite_error'}; frozen rule unchanged; no library, no trust (5s)
[PASS] frame: prior moves U 0.498 -> 1.000; extra rules offered; prepare once per round (1 rounds); vocabulary run extracts ast:set_op:except_all_two_tables (23s)
[PASS] switches: all on: calls {'implementer': 4, 'conjecturer': 1, 'prior': 3, 'translator': 1, 'vocab_inventor': 1, 'oracle_inventor': 1}; each role off: no call, no ledger line, plugin module not loaded (154s)
[PASS] prior: 20 units priced in 2 calls; evidence from the checkouts (40 lines); bad prior weight -> 0.0 after 20; useful prior weight 0.490 (1s)
[PASS] translator: DF-A family -> DuckDB translated once; settled {'tr-match': ('kept', 'match'), 'tr-mismatch': ('kept', 'mismatch'), 'tr-broken': ('broken', None), 'tr-void': ('void', None)}; bad switch refused; unmet spec retried (9s)
[PASS] vocab_inventor: accepted ast:set_op:except_all_two_tables on held-out records; refused {'empty': 'pattern', 'long': 'pattern', 'catastrophic': 'scan', 'everything': 'scan', 'no_exclusion': 'train', 'train_only': 'holdout'} and a data-layer id; prompt hides the held-out records (21s)
[PASS] oracle_inventor: accepted ['llm:wrap_sub'] on 5 instances; refused disagree, template, duplicate; 3 calls in 401 experiments; judged by the harness: pass (2s)
[PASS] translator_real: F2 (duckdb) -> datafusion: status ok, expect pass, switches []; label pass; settled kept identity None (4s)
[PASS] m3: 32 experiments and 43 calls replayed from the cache, identical; calls {'conjecturer': 2, 'oracle_inventor': 1, 'implementer': 36, 'prior': 4}; DF-B (shape|datafusion|wrong_result|-|extra_only) reached at experiment 3 via bet (bet from c1 on h1); lanes {'bootstrap': 1, 'generalize': 2, 'bet': 7, 'refine': 4, 'implement': 18} (92s)
S10 GATE: PASS (12/12 groups passed)
```

### `python -m surprise.gates.s15 --only config llm prices`

退出码：0。

```text
[PASS] config: new keys kept and passed to the cells; 21 bad values rejected; old defaults unchanged; 14 E1/E3 arms from EXPERIMENT.md load (0s)
[PASS] llm: gateway: unlimited, env ceiling, tier override; M3 replay identical with unlimited calls; 7 strong-tier calls went to deepseek-v4-pro; pure-LLM the same (123s)
[PASS] prices: DeepSeek prices of 2026-10-19 (peak cache-miss input, peak output) price both tiers (0s)
S15 GATE [only: config, llm, prices]: PASS (3/3 groups passed)
```

### `python -m pytest -q tests/test_surprise_s19_glm.py`

退出码：0。

```text
................                                                         [100%]
16 passed in 4.73s
```

### `pytest -q testing tests（复跑）`

退出码：0。

完整复跑通过；相对 1070 passed、3 skipped 的基线新增 16 个通过测试，skip 数不变。

```text
........................ss..................................s........... [  6%]
........................................................................ [ 13%]
........................................................................ [ 19%]
........................................................................ [ 26%]
........................................................................ [ 33%]
........................................................................ [ 39%]
........................................................................ [ 46%]
........................................................................ [ 52%]
........................................................................ [ 59%]
........................................................................ [ 66%]
........................................................................ [ 72%]
........................................................................ [ 79%]
........................................................................ [ 85%]
........................................................................ [ 92%]
........................................................................ [ 99%]
.........                                                                [100%]
1086 passed, 3 skipped in 393.27s (0:06:33)
```

### `git diff --cached --check; git diff --cached --stat; git status --short`

退出码：0。

```text
 framework/surprise/baselines/pure_llm.py           |   8 +-
 framework/surprise/experiments/grid.py             |   2 +-
 framework/surprise/experiments/loop.py             |   4 +-
 .../surprise/metrics/data/prices_openrouter.json   |  16 ++
 framework/surprise/roles/gateway.py                |  16 +-
 framework/surprise/roles/providers.py              |  30 +++
 framework/surprise/roles/runtime.py                |   4 +
 framework/surprise/roles/transport.py              |  15 +-
 framework/tests/test_surprise_s19_glm.py           | 223 +++++++++++++++++++++
 9 files changed, 305 insertions(+), 13 deletions(-)
M  framework/surprise/baselines/pure_llm.py
M  framework/surprise/experiments/grid.py
M  framework/surprise/experiments/loop.py
A  framework/surprise/metrics/data/prices_openrouter.json
M  framework/surprise/roles/gateway.py
A  framework/surprise/roles/providers.py
M  framework/surprise/roles/runtime.py
M  framework/surprise/roles/transport.py
A  framework/tests/test_surprise_s19_glm.py
```

### `git commit -m "Add GLM 5.3 Flash tier through OpenRouter"`

退出码：0。

```text
[grok/s19-glm 342727f] Add GLM 5.3 Flash tier through OpenRouter
 9 files changed, 305 insertions(+), 13 deletions(-)
 create mode 100644 framework/surprise/metrics/data/prices_openrouter.json
 create mode 100644 framework/surprise/roles/providers.py
 create mode 100644 framework/tests/test_surprise_s19_glm.py
```

### `git status --short; git log -1 --format=%H; git diff HEAD --check`

退出码：0。

```text
342727f1ff53baf0e40e113cf7cadebd1a2e17e3
```


## 与说明的偏差

无。

## 未决问题

无新增。按说明，实验模块摘要变化后，编排者需在合并后重跑并重钉 S08 长跑产物及关联 S11 门槛；本包未运行 gates.all。

