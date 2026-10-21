角色：执行者

# 工作包 s19-retry：传输层遇 HTTP 429 退避重试

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s19-retry`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s19`（门槛 `framework/surprise/gates/s19.py` 的 `retry` 组与 `s19_cases.py` 的 `RETRY_*` 常数已经写好，现在不通过）
- 所属会话：S19；用户 2026-10-21 的决定（"同意，改成429退避重试"），见 `framework/surprise/docs/PLAN.md` §9 最后一条与 `SESSIONS.md` 的 S19 一节

## 目标

`glm-flash` 档只用 OpenRouter 上的一个提供商、不回退，并发跑时会被限流（HTTP 429）。现在网关把 429 当成一次失败的调用，角色随即放弃，LLM 臂就悄悄少用了 LLM。改成：传输层遇到 429 等一会儿再试，别的失败照旧只试一次。

1. `framework/surprise/roles/constants.py`：在文件末尾（`REQUEST_DEADLINE_S` 之后、`as_dict` 之前）加一个常数，带一行与别的常数同样写法的注释：
   ```python
   # Seconds to wait before each retry of an HTTP 429 (rate limited) answer; one retry per entry.
   RATE_LIMIT_WAITS_S = [10.0, 30.0, 60.0, 120.0]
   ```
   是 list（`as_dict()` 经 JSON 往返，tuple 会变成 list，门槛按 list 核对）。文件里别的常数一个字不改。

2. `framework/surprise/roles/transport.py`，`DeepSeekTransport`：
   - 构造函数加两个仅限关键字参数：`rate_limit_waits_s`（默认 `None` = 用 `RATE_LIMIT_WAITS_S`）与 `sleep`（默认 `None` = `time.sleep`）。把等待序列存成属性 `self.rate_limit_waits_s`，类型是 float 的 tuple（`()` 表示不重试）。原有的 `base_url`、`deadline_s` 不变。
   - `complete()`：一次请求的 HTTP 状态是 429（`httpx.HTTPStatusError`，`exc.response.status_code == 429`）而且还有剩余的等待时，先往 `sys.stderr` 写一行（调用时取 `sys.stderr`，门槛用 `contextlib.redirect_stderr` 截获），再调 `sleep(wait)`，然后用同一个 payload、同一个 url 重发。这一行的格式逐字是 `s19_cases.RETRY_LINE`：
     ```
     surprise.roles.transport: HTTP 429 for role {role}, model {model}; retry {attempt}/{retries} in {wait:g} s
     ```
     `attempt` 从 1 起，`retries` 是 `len(self.rate_limit_waits_s)`；只这一行，不带密钥、不带回复正文。
   - 等待用完后还是 429：照现在的样子抛 `TransportError("HTTPStatusError 429")`。
   - 别的都不重试：其他 HTTP 状态（400、401、402、403、404、500、502、503……）、连接错误、`DeadlineExceeded`、正文为 null 或缺字段，都和现在一样只试一次、抛同样的 `TransportError`，不写 stderr、不调 `sleep`。
   - 每次重发各自有完整的 `deadline_s`（等待不算进请求的时限）。
   - 旧全局账本（`llm.ledger.ledger.record`）每次 `complete()` 仍只记一条（成功记 `status="ok"`，失败记 `status="error"`），多传 `retries=<这次实际重试的次数>`。
   - 重试全在 `complete()` 里：`roles/gateway.py` 不改，网关看到的仍是一次调用（调用上限、`calls.jsonl`、`totals()` 都按一次算）。
   - DeepSeek 的两个模型同样适用，请求体不变。

3. `framework/tests/test_surprise_s19_glm.py`：`test_transport_keeps_http_status_and_hides_response` 参数化里有 429，改完后默认会真的等 220 秒。把这个测试里的 `DeepSeekTransport()` 改成 `DeepSeekTransport(rate_limit_waits_s=())`，断言一个字不改。

4. 新测试 `framework/tests/test_surprise_s19_retry.py`（离线，不联网，不真的 sleep）：至少覆盖 429 两次后成功、429 一直到用完、非 429 不重试、`rate_limit_waits_s=()` 不重试、经网关只算一次调用与一个上限名额、stderr 行的格式、旧账本的 `retries`。可以照 `test_surprise_s19_glm.py` 的 `wire` 夹具拦住 httpx。

## 允许改动的路径

```allow-paths
framework/surprise/roles/constants.py
framework/surprise/roles/transport.py
framework/tests/test_surprise_s19_glm.py
framework/tests/test_surprise_s19_retry.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`；不改 `roles/gateway.py`、`roles/providers.py`、`framework/surprise/harness/`、`experiments/`、`framework/agents/`、`framework/llm/`。
- `roles/constants.py` 里已有的常数一个都不改（门槛拿 s15-done-r3 的版本逐个对照）。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不改 conftest。上面第 3 条那一处构造参数是本包要改的，不算放宽。
- 不登录、不连接实验服务器；不做任何真实的 LLM 调用（没有给你密钥），测试一律离线。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支；不改 `HANDOFF.md`、`DECISIONS.md`。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器。shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接。

```powershell
cd framework
pytest -q testing tests                              # 1157 passed, 3 skipped 的基线上只增不减，skip 不增加
python -m surprise.gates.s19                         # S19 GATE: PASS (12/12)
python -m surprise.gates.s09 --only constants        # PASS
python -m surprise.gates.s11 --only constants        # PASS
python -m surprise.gates.s15 --only config llm prices   # PASS (3/3)
```

（`gates.s19` 的 `balance` 组会往终端打几行乱码的看守日志，属正常。）

## 收尾

1. 把改动提交到当前分支；`git status` 应当是干净的。
2. 写 `.orch/report.md`（不入库），格式：改了哪些文件；跑了哪些命令（命令、退出码、输出末 20 行原样）；与说明的偏差（没有写"无"）；未决问题（没有写"无"）。
3. 说明有矛盾或做不完：写进报告，停下。
