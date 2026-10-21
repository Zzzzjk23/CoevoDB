# s19-medium 执行报告

## 改动文件

- `framework/surprise/roles/providers.py`：glm-flash 的 reasoning.effort 从 low 改为 medium，与 S19 NEW_PROFILE 一致。
- `framework/tests/test_surprise_s19_glm.py`：同步 PROFILE 中的期望值。
- `framework/tests/test_surprise_s19_providers.py`：同步三处 reasoning 期望值。
- `framework/tests/test_surprise_s19_retry.py`：同步 expected.update 中的 reasoning 期望值。

共四个文件、六处值替换；其他字段和断言保持原样。

## 提交

分支：`grok/s19-medium`

提交：`6abadef` — `fix(s19): set glm-flash reasoning effort to medium`

## 验收命令

以下三条命令均在 `D:\CoevoDB\.worktrees\s19-medium\framework` 执行；均为离线测试。

### `python -m pytest -q testing tests`

退出码：`0`

输出末 20 行（不足 20 行则全部；按终端输出原样记录）：

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
1205 passed, 3 skipped in 475.01s (0:07:55)
```

### `python -m surprise.gates.s19`

退出码：`0`

输出末 20 行（不足 20 行则全部；按终端输出原样记录）：

```text
[PASS] grid: surprise and pure-LLM arms pass --llm-tier glm-flash; unknown tiers rejected (0s)
[PASS] prices: OpenRouter prices of 2026-10-21 price z-ai/glm-5.3-flash; DeepSeek table unchanged (0s)
[PASS] pushplus: one-to-one txt message to https://www.pushplus.plus/send with the PUSHPLUS_TOKEN token in the body; codes [900, 905, 888] stop the sender, other failures do not; no token, no request (5s)
[PASS] reason: a failed call records 'TransportError: HTTPStatusError 402' (status kept, no key); other exceptions as before; 11 reasons classified (1s)
[PASS] watch: start, 402/timeout/429 streaks (once each, re-armed by a success), failed/blocked/stalled cells, finished; one message per poll, daily cap; the grid directory untouched (0s)
2026-10-21T11:14:03.279701+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-medium\.orch\tmp\coevo-s19-gate\balance\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ�key ʣ���� $0.5
2026-10-21T11:14:03.279701+00:00 balance - low key ʣ���� $0.5
2026-10-21T11:45:03.279701+00:00 balance - empty key ʣ���� $0
2026-10-21T12:16:03.279701+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-medium\.orch\tmp\coevo-s19-gate\balance-null\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ�key û�������ޣ�ֻ�ܿ�����ʧ�ܷ���Ƿ��
2026-10-21T12:16:03.279701+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-medium\.orch\tmp\coevo-s19-gate\balance-401\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ���ȼ����֤ʧ�ܣ�HTTP 401
2026-10-21T12:16:03.279701+00:00 balance - auth ��ȼ����֤ʧ�ܣ�HTTP 401
Balance check failed; will retry at the next interval.
2026-10-21T12:16:03.279701+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-medium\.orch\tmp\coevo-s19-gate\balance-down\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ��ޣ���ȼ��ʧ�ܣ�ֻ�ܿ�����ʧ�ܷ���Ƿ��
2026-10-21T12:16:03.279701+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-medium\.orch\tmp\coevo-s19-gate\balance-nollm\grid����� 0��ʧ�� 0������ 0��δ��ʼ 2��ʧ�ܸ���
2026-10-21T12:16:03.279701+00:00 start - - ��ʼ���أ����� ZZZZJK��OUT=D:\CoevoDB\.worktrees\s19-medium\.orch\tmp\coevo-s19-gate\balance-nokey\grid����� 0��ʧ�� 0������ 0��δ��ʼ 6��ʧ�ܸ���
[PASS] balance: https://openrouter.ai/api/v1/key with the DEEPSEEK_API_KEY key every 30 minutes on glm-flash grids: low and empty once each, 401 reported, no limit or no answer is no alarm (3s)
[PASS] cli: pushplus CLI exits 2 without a token; watch exits on 'finished' and on the grid process ending (--pid) (4s)
[PASS] retry: RATE_LIMIT_WAITS_S = [10.0, 30.0, 60.0, 120.0], RETRY_STATUSES = [429, 503] added, other constants as at s15-done-r3; 429/503 retried per provider, then sail-research/fp4 -> open-inference/fp4 -> sail-research/us; 7 statuses, connection errors and null content neither retried nor switched; provider recorded and replayed (GLM only); one gateway call, cap unit and row per call (1s)
[PASS] scope: 53 paths changed (s15-done-r3..work tree), all in scope; harness untouched (0s)
S19 GATE: PASS (12/12 groups passed)
```

### `python -m surprise.gates.s15 --only config llm prices`

退出码：`0`

输出末 20 行（不足 20 行则全部；按终端输出原样记录）：

```text
[PASS] config: new keys kept and passed to the cells; 21 bad values rejected; old defaults unchanged; 14 E1/E3 arms from EXPERIMENT.md load (0s)
[PASS] llm: gateway: unlimited, env ceiling, tier override; M3 replay identical with unlimited calls; 7 strong-tier calls went to deepseek-v4-pro; pure-LLM the same (104s)
[PASS] prices: DeepSeek prices of 2026-10-19 (peak cache-miss input, peak output) price both tiers (0s)
S15 GATE [only: config, llm, prices]: PASS (3/3 groups passed)
```

### `git diff --check`

退出码：`0`

输出：无。

## 与说明的偏差

无。

## 未决问题

无。

