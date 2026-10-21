# 审查包 · s19-retry

- 生成时间：2026-10-21T15:07:57+11:00
- 基线：`session/s19`（d00f432657d4）
- 分支：`grok/s19-retry` @ f38ee0a507af，基线之上 1 个提交
- 运行：共 1 轮（返工 0 轮），最近一轮退出码 0，用时 11m06s
- 执行者：codex codex-cli 0.163.0；会话 `01a15c9a-3194-7b63-a081-5f358634fa79`

## 红旗汇总

- 门槛未通过（退出码 1）
- 疑似密钥 1 处、敏感文件名 0 个

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s19..grok/s19-retry
git diff -M --stat session/s19..grok/s19-retry
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/roles/constants.py`、`framework/surprise/roles/transport.py`、`framework/tests/test_surprise_s19_glm.py`、`framework/tests/test_surprise_s19_retry.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/roles/constants.py` |  |
| M | `framework/surprise/roles/transport.py` |  |
| M | `framework/tests/test_surprise_s19_glm.py` |  |
| A | `framework/tests/test_surprise_s19_retry.py` |  |

提交：

- f38ee0a Junke: Retry rate-limited role requests with bounded backoff

## 2. diff 统计

```text
 framework/surprise/roles/constants.py      |   3 +
 framework/surprise/roles/transport.py      |  39 ++++-
 framework/tests/test_surprise_s19_glm.py   |   2 +-
 framework/tests/test_surprise_s19_retry.py | 236 +++++++++++++++++++++++++++++
 4 files changed, 276 insertions(+), 4 deletions(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，6m55s；passed 1180，skipped 3

```text
........................ss..................................s........... [  6%]
........................................................................ [ 12%]
........................................................................ [ 18%]
........................................................................ [ 24%]
........................................................................ [ 30%]
........................................................................ [ 36%]
........................................................................ [ 42%]
........................................................................ [ 48%]
........................................................................ [ 54%]
........................................................................ [ 60%]
........................................................................ [ 66%]
........................................................................ [ 73%]
........................................................................ [ 79%]
........................................................................ [ 85%]
........................................................................ [ 91%]
........................................................................ [ 97%]
...............................                                          [100%]
1180 passed, 3 skipped in 414.26s (0:06:54)
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，30m00s

```text
[PASS] switches: all on: calls {'implementer': 4, 'conjecturer': 1, 'prior': 3, 'translator': 1, 'vocab_inventor': 1, 'oracle_inventor': 1}; each role off: no call, no ledger line, plugin module not loaded (129s)
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
[PASS] llm_metrics: 15 experiments replayed; 2 conjectures, survival 0.0, accuracy 0.7142857142857143 over 7 settled bets; families via {'implement': 0, 'bet': 1, 'translate': 0, 'llm_rule': 0, 'invented_feature': 0}; 23 calls (33s)
[PASS] rq6: classify, F2 fix conditions (1 entries), pair agreement as hand-computed; F2 hypothesis too_narrow (missing [], extra 9 literals); recall 0.5 (4s)
[PASS] arms: random Hunter deterministic and different; frozen theory unchanged (1 failures fully profiled); frozen Diagnoser no edits; theory-from and select-from (5 choices scored differently); 5 usage errors refused (95s)
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

- 无

### 4.4 新增的宽泛异常捕获

- 无

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- `framework/tests/test_surprise_s19_retry.py:134` bearer token: Bea…(29 chars)
- 日志 `.orch/logs/s19-retry.jsonl` 与 stderr 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 无

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s19-retry.jsonl`：73 条事件（item.completed 39，item.started 29，orch.exit 1，orch.start 1，thread.started 1，turn.completed 1，turn.started 1）；各轮合计 codex：1 轮，输入 1983135 token（其中缓存 1883776），输出 13498（其中推理 4583），codex 不报美元。

被 deny 规则（grok）或 execpolicy 规则（codex，记在 stderr）拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

````text
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git commit -m "Retry rate-limited role requests with bounded backoff"'
exec [exit 0]: [grok/s19-retry f38ee0a] Retry rate-limited role requests with bounded backoff 4 files changed, 276 insertions(+), 4 deletions(-) create mode 100644 framework/tests/test_surprise_…
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short'
exec [exit 0]: 
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git rev-parse HEAD'
exec [exit 0]: f38ee0a507afc91eb951db4639280905de82bf86
file_change [completed]: add D:\CoevoDB\.worktrees\s19-retry\.orch\report.md
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short; git check-ignore .orch/report.md; Get-Content -Encoding UTF8 .orch/report.md | Selec…
exec [exit 0]: .orch/report.md ``` ## 与说明的偏差 验收中将 `pytest -q testing tests` 改为 `python -m pytest -q testing tests`。首次直接执行 pytest 的定向测试在收集阶段失败，错误栈来自 D:\anaconda3，无法导入 llm/surprise。只读检查显示 python 和…
text: 已完成并提交 `f38ee0a`，工作区干净。 - 全量测试：1180 passed，3 skipped。 - S19：12/12；S09、S11、S15 指定门槛全部通过。 - 偏差：因 `pytest.exe` 启动器异常，使用同一项目解释器的 `python -m pytest`。 详情见 [.orch/report.md](D:/CoevoDB/.…
end: tokens in=1983135 cached=1883776 out=13498 reasoning=4583
orch.exit: {"pkg": "s19-retry", "run": 1, "at": "2026-10-21T15:07:17+11:00", "exitCode": 0, "timedOut": false, "error": null}
````

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# s19-retry 执行报告

分支：grok/s19-retry。提交：`f38ee0a507afc91eb951db4639280905de82bf86`。状态：工作包完成，git status --short 输出为空。

## 改动文件

- `framework/surprise/roles/constants.py`：仅新增注释和 `RATE_LIMIT_WAITS_S = [10.0, 30.0, 60.0, 120.0]`，既有常数不变。
- `framework/surprise/roles/transport.py`：增加关键字参数 `rate_limit_waits_s`、`sleep`；等待配置复制为 float tuple。仅 HTTPStatusError 429 在 complete() 内按序重试，重用同一 payload 和 URL，每次请求独立使用完整 deadline_s。等待前写指定 stderr 行，最终成功或失败均只记一条旧账本记录，并记录实际 retries；网关未改。
- `framework/tests/test_surprise_s19_glm.py`：仅为指定 HTTP 状态测试增加 `rate_limit_waits_s=()`，断言不变。
- `framework/tests/test_surprise_s19_retry.py`：新增 23 项离线测试，覆盖三模型的 429 两次后成功、重试耗尽、禁用/自定义重试、其他 HTTP 状态、连接错误、DeadlineExceeded、null/缺字段、重试后的非 429 失败、stderr 格式与等待前输出、独立请求时限、单条旧账本和 retries，以及成功/失败经网关只占一次调用、一个上限名额和一行 calls.jsonl。

## 命令与结果

测试和门槛的工作目录为 worktree 的 `framework/`；Git 命令的工作目录为 worktree 根。每项以下保留输出末 20 行，不满 20 行则全部保留；空输出用空代码块表示。

### `pytest -q tests/test_surprise_s19_retry.py tests/test_surprise_s19_glm.py`

退出码：1。

```text
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\test_surprise_s19_retry.py:13: in <module>
    from llm.ledger import LLMLedger
E   ModuleNotFoundError: No module named 'llm'
_______________ ERROR collecting tests/test_surprise_s19_glm.py _______________
ImportError while importing test module 'D:\CoevoDB\.worktrees\s19-retry\framework\tests\test_surprise_s19_glm.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
D:\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\test_surprise_s19_glm.py:12: in <module>
    from surprise.baselines import pure_llm
E   ModuleNotFoundError: No module named 'surprise'
=========================== short test summary info ===========================
ERROR tests/test_surprise_s19_retry.py
ERROR tests/test_surprise_s19_glm.py
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!
2 errors in 0.37s
```

### `python -m pytest -q tests/test_surprise_s19_retry.py tests/test_surprise_s19_glm.py`

退出码：0。

```text
.......................................                                  [100%]
39 passed in 15.30s
```

### `python -m pytest -q tests/test_surprise_s19_retry.py`

退出码：0。

```text
.......................                                                  [100%]
23 passed in 13.90s
```

### `python -m pytest -q testing tests`

退出码：0。

```text
........................ss..................................s........... [  6%]
........................................................................ [ 12%]
........................................................................ [ 18%]
........................................................................ [ 24%]
........................................................................ [ 30%]
........................................................................ [ 36%]
........................................................................ [ 42%]
........................................................................ [ 48%]
........................................................................ [ 54%]
........................................................................ [ 60%]
........................................................................ [ 66%]
........................................................................ [ 73%]
........................................................................ [ 79%]
........................................................................ [ 85%]
........................................................................ [ 91%]
........................................................................ [ 97%]
...............................                                          [100%]
1180 passed, 3 skipped in 431.16s (0:07:11)
```

### `python -m surprise.gates.s19`

退出码：0。

```text
[PASS] grid: surprise and pure-LLM arms pass --llm-tier glm-flash; unknown tiers rejected (0s)
[PASS] prices: OpenRouter prices of 2026-10-20 price z-ai/glm-5.3-flash; DeepSeek table unchanged (0s)
[PASS] pushplus: one-to-one txt message to https://www.pushplus.plus/send with the PUSHPLUS_TOKEN token in the body; codes [900, 905, 888] stop the sender, other failures do not; no token, no request (5s)
[PASS] reason: a failed call records 'TransportError: HTTPStatusError 402' (status kept, no key); other exceptions as before; 11 reasons classified (1s)
[PASS] watch: start, 402/timeout/429 streaks (once each, re-armed by a success), failed/blocked/stalled cells, finished; one message per poll, daily cap; the grid directory untouched (0s)
2026-10-21T03:59:31.866959+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-retry\.orch\tmp\coevo-s19-gate\balance\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ�key ʣ���� $0.5
2026-10-21T03:59:31.866959+00:00 balance - low key ʣ���� $0.5
2026-10-21T04:30:31.866959+00:00 balance - empty key ʣ���� $0
2026-10-21T05:01:31.866959+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-retry\.orch\tmp\coevo-s19-gate\balance-null\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ�key û�������ޣ�ֻ�ܿ�����ʧ�ܷ���Ƿ��
2026-10-21T05:01:31.866959+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-retry\.orch\tmp\coevo-s19-gate\balance-401\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ���ȼ����֤ʧ�ܣ�HTTP 401
2026-10-21T05:01:31.866959+00:00 balance - auth ��ȼ����֤ʧ�ܣ�HTTP 401
Balance check failed; will retry at the next interval.
2026-10-21T05:01:31.866959+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-retry\.orch\tmp\coevo-s19-gate\balance-down\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ���ȼ��ʧ�ܣ�ֻ�ܿ�����ʧ�ܷ���Ƿ��
2026-10-21T05:01:31.866959+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-retry\.orch\tmp\coevo-s19-gate\balance-nollm\grid����� 0��ʧ�� 0������ 0��δ��ʼ 2��ʧ�ܸ���
2026-10-21T05:01:31.866959+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-retry\.orch\tmp\coevo-s19-gate\balance-nokey\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ���
[PASS] balance: https://openrouter.ai/api/v1/key with the DEEPSEEK_API_KEY key every 30 minutes on glm-flash grids: low and empty once each, 401 reported, no limit or no answer is no alarm (3s)
[PASS] cli: pushplus CLI exits 2 without a token; watch exits on 'finished' and on the grid process ending (--pid) (4s)
[PASS] retry: RATE_LIMIT_WAITS_S = [10.0, 30.0, 60.0, 120.0] added, other constants as at s15-done-r3; 429 retried with those waits and one stderr line each, then TransportError 429; 8 statuses, connection errors and null content not retried; one gateway call, cap unit and row per call (2s)
[PASS] scope: 41 paths changed (s15-done-r3..work tree), all in scope; harness untouched (0s)
S19 GATE: PASS (12/12 groups passed)
```

### `python -m surprise.gates.s09 --only constants`

退出码：0。

```text
[PASS] constants: 19 constants as planned; tiers {'fast': 'deepseek-flash', 'strong': 'deepseek-v4-pro'} (0s)
S09 GATE [only: constants]: PASS (1/1 groups passed)
```

### `python -m surprise.gates.s11 --only constants`

退出码：0。

```text
[PASS] constants: 7 metric constants, request deadline 600.0 s, pure-LLM constants and 10 topics (0s)
S11 GATE [only: constants]: PASS (1/1 groups passed)
```

### `python -m surprise.gates.s15 --only config llm prices`

退出码：0。

```text
[PASS] config: new keys kept and passed to the cells; 21 bad values rejected; old defaults unchanged; 14 E1/E3 arms from EXPERIMENT.md load (0s)
[PASS] llm: gateway: unlimited, env ceiling, tier override; M3 replay identical with unlimited calls; 7 strong-tier calls went to deepseek-v4-pro; pure-LLM the same (107s)
[PASS] prices: DeepSeek prices of 2026-10-19 (peak cache-miss input, peak output) price both tiers (0s)
S15 GATE [only: config, llm, prices]: PASS (3/3 groups passed)
```

### `git diff --check`

退出码：0。

```text

```

### `git commit -m "Retry rate-limited role requests with bounded backoff"`

退出码：0。

```text
[grok/s19-retry f38ee0a] Retry rate-limited role requests with bounded backoff
 4 files changed, 276 insertions(+), 4 deletions(-)
 create mode 100644 framework/tests/test_surprise_s19_retry.py
```

### `git status --short`

退出码：0。

```text

```

## 与说明的偏差

验收中将 `pytest -q testing tests` 改为 `python -m pytest -q testing tests`。首次直接执行 pytest 的定向测试在收集阶段失败，错误栈来自 D:\anaconda3，无法导入 llm/surprise。只读检查显示 python 和 pytest 的命令路径均在 D:\CoevoDB\.venv\Scripts 下，且 python 的 sys.executable 为 D:\CoevoDB\.venv\Scripts\python.exe；因此使用说明中同一个 python 的 -m pytest，未更换解释器、修改环境或修复外部启动器。全量结果为 1180 passed、3 skipped（基线 1157 passed、3 skipped，新增 23 项），所有指定门槛通过。

除测试启动形式外，无范围或实现偏差。未登录实验服务器、未进行真实 LLM 调用、未真正等待重试间隔；未改门槛、文档、网关或其他禁止路径；未打 tag、合并、rebase、push 或切换分支。本报告位于忽略的 .orch 目录，未入库。

## 未决问题

直接执行 pytest.exe 的启动器绑定异常未修复，属于允许改动路径之外；本包全部测试已通过同一项目解释器的 python -m pytest 完成。功能与验收无未决问题。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：
