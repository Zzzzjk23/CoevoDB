# 审查包 · s19-max

- 生成时间：2026-10-22T02:05:25+11:00
- 基线：`session/s19`（d3158316f493）
- 分支：`grok/s19-max` @ 272c630074b2，基线之上 1 个提交
- 运行：共 1 轮（返工 0 轮），最近一轮退出码 0，用时 10m09s
- 执行者：codex codex-cli 0.163.0；会话 `01a15ef5-39dc-7402-98b8-4597dd0a87c7`

## 红旗汇总

- 门槛未通过（退出码 1）
- 测试里被改写的断言 2 处（逐条确认没有放宽）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s19..grok/s19-max
git diff -M --stat session/s19..grok/s19-max
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/roles/providers.py`、`framework/tests/test_surprise_s19_glm.py`、`framework/tests/test_surprise_s19_providers.py`、`framework/tests/test_surprise_s19_retry.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/roles/providers.py` |  |
| M | `framework/tests/test_surprise_s19_glm.py` |  |
| M | `framework/tests/test_surprise_s19_providers.py` |  |
| M | `framework/tests/test_surprise_s19_retry.py` |  |

提交：

- 272c630 Junke: Set glm-flash reasoning effort to max

## 2. diff 统计

```text
 framework/surprise/roles/providers.py          | 2 +-
 framework/tests/test_surprise_s19_glm.py       | 2 +-
 framework/tests/test_surprise_s19_providers.py | 6 +++---
 framework/tests/test_surprise_s19_retry.py     | 2 +-
 4 files changed, 6 insertions(+), 6 deletions(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，7m43s；passed 1205，skipped 3

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
1205 passed, 3 skipped in 461.97s (0:07:41)
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，30m00s

```text
=== gate s10 ===
[PASS] isolation: 4 role modules load no model client; loop, Hunter, Diagnoser and harness never import the roles (1s)
[PASS] constants: 35 S10 constants as planned, S9 constants unchanged, library constants ['LIBRARY_ENV', 'LIBRARY_KINDS', 'LIBRARY_MIN_REFERENCES', 'LIBRARY_RULE_PREFIX', 'LIBRARY_SCHEMA'] (0s)
[PASS] frozen: harness changes since s09-done-r2: ['equivalent_query.py', 'rewrites.py']; re-frozen and verified; 12 frozen-rule outputs unchanged with and without a library (0s)
[PASS] library: 4 usable and 10 refused templates; 8 malformed libraries refused; judgements {'llm:wrap_sub': 'pass', 'llm:is_true': 'pass', 'llm:first_row': 'untrusted_rewrite/reference_disagrees', 'llm:octet': 'untrusted_rewrite/rewrite_error'}; frozen rule unchanged; no library, no trust (4s)
[PASS] frame: prior moves U 0.498 -> 1.000; extra rules offered; prepare once per round (1 rounds); vocabulary run extracts ast:set_op:except_all_two_tables (18s)
[PASS] switches: all on: calls {'implementer': 4, 'conjecturer': 1, 'prior': 3, 'translator': 1, 'vocab_inventor': 1, 'oracle_inventor': 1}; each role off: no call, no ledger line, plugin module not loaded (135s)
[PASS] prior: 20 units priced in 2 calls; evidence from the checkouts (40 lines); bad prior weight -> 0.0 after 20; useful prior weight 0.490 (1s)
[PASS] translator: DF-A family -> DuckDB translated once; settled {'tr-match': ('kept', 'match'), 'tr-mismatch': ('kept', 'mismatch'), 'tr-broken': ('broken', None), 'tr-void': ('void', None)}; bad switch refused; unmet spec retried (8s)
[PASS] vocab_inventor: accepted ast:set_op:except_all_two_tables on held-out records; refused {'empty': 'pattern', 'long': 'pattern', 'catastrophic': 'scan', 'everything': 'scan', 'no_exclusion': 'train', 'train_only': 'holdout'} and a data-layer id; prompt hides the held-out records (21s)
[PASS] oracle_inventor: accepted ['llm:wrap_sub'] on 5 instances; refused disagree, template, duplicate; 3 calls in 401 experiments; judged by the harness: pass (1s)
[PASS] translator_real: F2 (duckdb) -> datafusion: status ok, expect pass, switches []; label pass; settled kept identity None (4s)
[PASS] m3: 32 experiments and 43 calls replayed from the cache, identical; calls {'conjecturer': 2, 'oracle_inventor': 1, 'implementer': 36, 'prior': 4}; DF-B (shape|datafusion|wrong_result|-|extra_only) reached at experiment 3 via bet (bet from c1 on h1); lanes {'bootstrap': 1, 'generalize': 2, 'bet': 7, 'refine': 4, 'implement': 18} (91s)
S10 GATE: PASS (12/12 groups passed)
=== gate s11 ===
[PASS] constants: 7 metric constants, request deadline 600.0 s, pure-LLM constants and 10 topics (0s)
[PASS] store: 6 replace calls for 3 transient failures (0.36s); a lasting failure raises PermissionError (2s)
[PASS] loop_error: original exception kept and written to error.txt (both, drive) (1s)
[PASS] deadline: normal answer passes; deadline 1.5s held (trickle 2.0s, silent 2.0s); errors booked, not cached (9s)
[PASS] vocabulary: run_registry, new_families, compare, recall.score, RunData and run_metrics all read the run's vocabulary (36s)
[PASS] stats: exact and asymptotic MWU (scipy agrees), A12, median, summarize as hand-computed (2s)
[PASS] runmetrics: 31 records, 1 ledger families, Brier 0.2194, 1 high-surprise records, invalid 14, theory length 193.0; all recomputed (0s)
[FAIL] ciao: artifact directory results/s08/longrun is missing on this machine
[PASS] llm_metrics: 15 experiments replayed; 2 conjectures, survival 0.0, accuracy 0.7142857142857143 over 7 settled bets; families via {'implement': 0, 'bet': 1, 'translate': 0, 'llm_rule': 0, 'invented_feature': 0}; 23 calls (35s)
[PASS] rq6: classify, F2 fix conditions (1 entries), pair agreement as hand-computed; F2 hypothesis too_narrow (missing [], extra 9 literals); recall 0.5 (4s)
```

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- `framework/tests/test_surprise_s19_providers.py:107` 原：`assert profile["body"] == {"reasoning": {"effort": "medium"}}` → 同一处新增：`assert profile["body"] == {"reasoning": {"effort": "max"}}`
- `framework/tests/test_surprise_s19_providers.py:111` 原：`assert get_profile(arg)["body"] == {"reasoning": {"effort": "medium"}}` → 同一处新增：`assert get_profile(arg)["body"] == {"reasoning": {"effort": "max"}}`

### 4.4 新增的宽泛异常捕获

- 无

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s19-max.jsonl` 与 stderr 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 移动 `refs/heads/session/s16` c0a6504d545f → 4774d9b1f744

主检出区当前未提交的改动（`git status --porcelain`）：

```text
?? .claude/
```

## 6. 执行日志摘要

`.orch/logs/s19-max.jsonl`：39 条事件（item.completed 23，item.started 11，orch.exit 1，orch.start 1，thread.started 1，turn.completed 1，turn.started 1）；各轮合计 codex：1 轮，输入 1349584 token（其中缓存 1278848），输出 6027（其中推理 1176），codex 不报美元。

被 deny 规则（grok）或 execpolicy 规则（codex，记在 stderr）拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
text: 测试后段暂时没有新输出，进程仍在运行，也未报告失败。我会继续等待验收结束，保留其完整结果。
text: 全量测试已继续推进到 95%，仍无失败。结束后我会立即记录结果、提交改动并检查工作区是否干净。
exec [exit 0]: ........................ss..................................s........... [ 5%] ........................................................................ [ 11%] ....................…
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git diff --check; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; git add -- framework/surprise/roles/p…
exec [exit 0]: [grok/s19-max 272c630] Set glm-flash reasoning effort to max 4 files changed, 6 insertions(+), 6 deletions(-) 272c630 Set glm-flash reasoning effort to max
text: 全部验收通过：1205 passed、3 skipped；S19 为 12/12，S15 指定组为 3/3。改动已提交为 `272c630`，工作区干净；正在写入未入库的执行报告。
file_change [completed]: add D:\CoevoDB\.worktrees\s19-max\.orch\report.md
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short; git check-ignore .orch/report.md; git show --stat --oneline HEAD'
exec [exit 0]: .orch/report.md 272c630 Set glm-flash reasoning effort to max framework/surprise/roles/providers.py | 2 +- framework/tests/test_surprise_s19_glm.py | 2 +- framework/tests/test_sur…
text: 已完成并提交 `272c630`，工作区干净。 - `glm-flash` 推理强度改为 `max`，同步测试期望。 - 全量测试：1205 passed，3 skipped。 - 门槛：S19 12/12；S15 指定组 3/3。 - 无偏差、无未决问题。 报告：[.orch/report.md](D:/CoevoDB/.worktrees/s19-ma…
end: tokens in=1349584 cached=1278848 out=6027 reasoning=1176
orch.exit: {"pkg": "s19-max", "run": 1, "at": "2026-10-22T02:05:01+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# s19-max 执行报告

角色：执行者
分支：`grok/s19-max`
提交：`272c630` — Set glm-flash reasoning effort to max

## 改动文件

- `framework/surprise/roles/providers.py`：glm-flash 的 reasoning.effort 从 medium 改为 max，其他字段不变，与门槛 NEW_PROFILE 一致。
- `framework/tests/test_surprise_s19_glm.py`：同步 PROFILE 的推理强度；两处作为非法档名的 medium 保留。
- `framework/tests/test_surprise_s19_providers.py`：同步三处推理强度期望，其他断言不变。
- `framework/tests/test_surprise_s19_retry.py`：同步 expected.update 的推理强度。

共 4 个文件、6 处值替换。

## 命令与结果

以下三项验收在 worktree 的 `framework/` 目录执行。每个测试命令的独立 PowerShell 进程先执行 `$env:DEEPSEEK_API_KEY = $null; $env:PUSHPLUS_TOKEN = $null`，不影响用户持久环境。测试使用模拟网络，未进行真实 LLM 调用，未连接实验服务器。

### `python -m pytest -q testing tests`

退出码：0。输出末 20 行（不足 20 行则完整保留，含终端原有乱码）：

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
1205 passed, 3 skipped in 507.13s (0:08:27)
```

### `python -m surprise.gates.s19`

退出码：0。输出末 20 行（不足 20 行则完整保留，含终端原有乱码）：

```text
[PASS] grid: surprise and pure-LLM arms pass --llm-tier glm-flash; unknown tiers rejected (0s)
[PASS] prices: OpenRouter prices of 2026-10-21 price z-ai/glm-5.3-flash; DeepSeek table unchanged (0s)
[PASS] pushplus: one-to-one txt message to https://www.pushplus.plus/send with the PUSHPLUS_TOKEN token in the body; codes [900, 905, 888] stop the sender, other failures do not; no token, no request (5s)
[PASS] reason: a failed call records 'TransportError: HTTPStatusError 402' (status kept, no key); other exceptions as before; 11 reasons classified (1s)
[PASS] watch: start, 402/timeout/429 streaks (once each, re-armed by a success), failed/blocked/stalled cells, finished; one message per poll, daily cap; the grid directory untouched (0s)
2026-10-21T14:56:36.654093+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-max\.orch\tmp\coevo-s19-gate\balance\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ�key ʣ���� $0.5
2026-10-21T14:56:36.654093+00:00 balance - low key ʣ���� $0.5
2026-10-21T15:27:36.654093+00:00 balance - empty key ʣ���� $0
2026-10-21T15:58:36.654093+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-max\.orch\tmp\coevo-s19-gate\balance-null\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ�key û�������ޣ�ֻ�ܿ�����ʧ�ܷ���Ƿ��
2026-10-21T15:58:36.654093+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-max\.orch\tmp\coevo-s19-gate\balance-401\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ���ȼ����֤ʧ�ܣ�HTTP 401
2026-10-21T15:58:36.654093+00:00 balance - auth ��ȼ����֤ʧ�ܣ�HTTP 401
Balance check failed; will retry at the next interval.
2026-10-21T15:58:36.654093+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-max\.orch\tmp\coevo-s19-gate\balance-down\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ���ȼ��ʧ�ܣ�ֻ�ܿ�����ʧ�ܷ���Ƿ��
2026-10-21T15:58:36.654093+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-max\.orch\tmp\coevo-s19-gate\balance-nollm\grid����� 0��ʧ�� 0������ 0��δ��ʼ 2��ʧ�ܸ���
2026-10-21T15:58:36.654093+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-max\.orch\tmp\coevo-s19-gate\balance-nokey\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ���
[PASS] balance: https://openrouter.ai/api/v1/key with the DEEPSEEK_API_KEY key every 30 minutes on glm-flash grids: low and empty once each, 401 reported, no limit or no answer is no alarm (4s)
[PASS] cli: pushplus CLI exits 2 without a token; watch exits on 'finished' and on the grid process ending (--pid) (5s)
[PASS] retry: RATE_LIMIT_WAITS_S = [10.0, 30.0, 60.0, 120.0], RETRY_STATUSES = [429, 503] added, other constants as at s15-done-r3; 429/503 retried per provider, then sail-research/fp4 -> open-inference/fp4 -> sail-research/us; 7 statuses, connection errors and null content neither retried nor switched; provider recorded and replayed (GLM only); one gateway call, cap unit and row per call (1s)
[PASS] scope: 57 paths changed (s15-done-r3..work tree), all in scope; harness untouched (0s)
S19 GATE: PASS (12/12 groups passed)
```

### `python -m surprise.gates.s15 --only config llm prices`

退出码：0。输出末 20 行（不足 20 行则完整保留，含终端原有乱码）：

```text
[PASS] config: new keys kept and passed to the cells; 21 bad values rejected; old defaults unchanged; 14 E1/E3 arms from EXPERIMENT.md load (0s)
[PASS] llm: gateway: unlimited, env ceiling, tier override; M3 replay identical with unlimited calls; 7 strong-tier calls went to deepseek-v4-pro; pure-LLM the same (128s)
[PASS] prices: DeepSeek prices of 2026-10-19 (peak cache-miss input, peak output) price both tiers (0s)
S15 GATE [only: config, llm, prices]: PASS (3/3 groups passed)
```

### 提交与工作区检查

在 worktree 根执行 `git diff --check`、`git add -- framework/surprise/roles/providers.py framework/tests/test_surprise_s19_glm.py framework/tests/test_surprise_s19_providers.py framework/tests/test_surprise_s19_retry.py`、`git commit -m "Set glm-flash reasoning effort to max"`、`git status --short`、`git log -1 --format="%h %s"`，均退出 0；diff 检查和 status 输出为空。合并输出末 20 行：

```text
[grok/s19-max 272c630] Set glm-flash reasoning effort to max
 4 files changed, 6 insertions(+), 6 deletions(-)
272c630 Set glm-flash reasoning effort to max
```

报告文件 `.orch/report.md` 被 Git 忽略，不入库。

## 与说明的偏差

无。

## 未决问题

无。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：
