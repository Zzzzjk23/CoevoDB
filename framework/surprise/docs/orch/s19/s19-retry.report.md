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

