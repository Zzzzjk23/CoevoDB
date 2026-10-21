角色：执行者

# 工作包 s19-providers：503 也重试，服务商列表按次序自动切换

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s19-providers`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s19`。门槛 `framework/surprise/gates/s19.py` 的 `transport`、`gateway`、`retry`、`prices` 组与 `s19_cases.py`（`NEW_PROVIDERS`、`NEW_PROFILE`、`RETRY_*`、`SWITCH_LINE`、`NO_RETRY_STATUSES`、`PRICES`）已经改好，现在不通过。
- 所属会话：S19；用户 2026-10-21 的决定，见 `framework/surprise/docs/PLAN.md` §9 最后一条、`SESSIONS.md` 的 S19 一节与 `DECISIONS.md` 当天的条目。

## 背景

GLM 预实验里 OpenRouter 成串回 HTTP 503（"no available model provider that meets your routing requirements"）：我们只许 `open-inference/fp4` 一家、不许回退，这家一时不可用就是 503。用户定下：503 也退避重试；服务商换成 `sail-research/fp4`；一家的重试用完仍不行，就依次换 `open-inference/fp4`、`sail-research/us`（三家都是 fp4），每次调用自动做。

## 要做的

1. `framework/surprise/roles/constants.py`：在 `RATE_LIMIT_WAITS_S` 之后加
   ```python
   # HTTP statuses retried after RATE_LIMIT_WAITS_S on one provider, then sent to the endpoint's next provider.
   RETRY_STATUSES = [429, 503]
   ```
   `RATE_LIMIT_WAITS_S` 的值不变，它上面那行注释可以改成同时说 429 与 503、按每家计。别的常数一个字不改（门槛拿 s15-done-r3 逐个对照，只许多这两个）。

2. `framework/surprise/roles/providers.py`：`EXTRA_TIERS["glm-flash"]` 改成与 `s19_cases.NEW_PROFILE` 逐项相等：
   ```python
   {
       "model": "z-ai/glm-5.3-flash",
       "base_url": "https://openrouter.ai/api/v1",
       "providers": ["sail-research/fp4", "open-inference/fp4", "sail-research/us"],
       "body": {"reasoning": {"effort": "low"}},
   }
   ```
   `body` 里不再有 `provider`；它由传输层按当前这一家生成。`endpoint_for_tier` / `endpoint_for_model` 照旧返回深拷贝。

3. `framework/surprise/roles/transport.py`，`DeepSeekTransport.complete()`：
   - 有 `providers` 的端点：按列表次序，每一家发的请求体是 `{原有字段, **body, "provider": {"only": [这一家], "allow_fallbacks": False}}`（键的次序：`model`、`messages`、`temperature`、`max_tokens`、`reasoning`、`provider`）。没有 `providers` 的端点（DeepSeek）请求体与现在逐字节相同，当作只有一家、名字是 `None`。
   - 一次请求回的 HTTP 状态在 `RETRY_STATUSES` 里：这一家还有等待就往 `sys.stderr` 写一行、`sleep(wait)`、同一请求重发（等待按 `self.rate_limit_waits_s` 的次序，每换一家从头算）；这一家的等待用完、后面还有别家，就写一行切换说明、立刻换下一家（不等待）；最后一家也用完，照现在的样子抛 `TransportError("HTTPStatusError <状态>")`。
   - stderr 行的格式逐字照 `s19_cases`：没有服务商时 `RETRY_LINE`，有服务商时 `RETRY_LINE_VIA`，切换时 `SWITCH_LINE`；`attempt` 从 1 起、每家重新计，`retries` 是 `len(self.rate_limit_waits_s)`。不带密钥、不带回复正文。
   - 别的失败（其他状态码、连接错误、`DeadlineExceeded`、正文为 null 或缺字段，以及重试中途出现的非重试状态）都立刻抛，既不重试也不切换，和现在一样。
   - 每次请求各自有完整的 `deadline_s`。
   - 旧全局账本仍是每次 `complete()` 一条，`retries` 是这次实际重发的次数（尝试次数减一，切换也算一次重发）。
   - `Completion` 带上回答的那一家：`provider=<这一家的名字>`；没有服务商的端点是 `None`。
   - `rate_limit_waits_s`、`sleep` 两个参数照旧；`()` 时不等待，429/503 在有别家时直接切换，没有别家时直接抛。

4. `framework/surprise/roles/gateway.py`：
   - `Completion` 与 `Reply` 各在最后加一个字段 `provider: str | None = None`。
   - 网络调用成功：`Reply.provider` 取 `Completion.provider`（取不到时为 `None`）；缓存条目只在它不是 `None` 时多写一个键 `"provider"`。
   - 命中缓存：`Reply.provider` 取条目里的 `"provider"`（没有或不是字符串时为 `None`）。
   - `calls.jsonl` 的一行只在 `reply.provider` 不是 `None` 时多一个键 `"provider"`。`error`、`miss`、`blocked` 的回复都是 `None`。
   - 这样 DeepSeek 的行与缓存条目的键集与现在完全相同（S9 门槛按键集核对）。网关别的行为不变：重试与切换都在一次调用之内，调用上限、`totals()`、manifest 都按一次算。

5. `framework/surprise/metrics/data/prices_openrouter.json`：内容与 `s19_cases.PRICES` 相等（2026-10-21 读的三家价格；`grid` 按第一家 `sail-research/fp4` 计）。

6. 测试：
   - `framework/tests/test_surprise_s19_glm.py`、`framework/tests/test_surprise_s19_retry.py`：本包改掉的行为（`PROFILE`、请求体字节、价格表、503 不重试、stderr 行格式）跟着改；其余断言不动。
   - 新测试 `framework/tests/test_surprise_s19_providers.py`（离线，不真的 sleep）：至少覆盖第一家 503 后成功、第一家一直 503 后第二家回答、三家都不行、503 后 402 不再切换、`rate_limit_waits_s=()` 时直接切换、回答的服务商出现在 Completion / Reply / `calls.jsonl` / 缓存条目且命中缓存时还在、DeepSeek 的行与条目键集不变。

## 允许改动的路径

```allow-paths
framework/surprise/roles/constants.py
framework/surprise/roles/providers.py
framework/surprise/roles/transport.py
framework/surprise/roles/gateway.py
framework/surprise/metrics/data/prices_openrouter.json
framework/tests/test_surprise_s19_glm.py
framework/tests/test_surprise_s19_retry.py
framework/tests/test_surprise_s19_providers.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`；不改 `framework/surprise/harness/`、`experiments/`、`notify/`、`baselines/`、`framework/agents/`、`framework/llm/`。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不改 conftest。上面第 6 条列出的、因本包行为改变而要改的期望不算放宽；S19 以外的测试一个都不改。
- 不登录、不连接实验服务器；不做任何真实的 LLM 调用（没有给你密钥），测试一律离线。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支；不改 `HANDOFF.md`、`DECISIONS.md`。

## 验收命令

在 worktree 里执行，全部通过才算完成。shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接。上次直接运行 `pytest` 启动器在沙箱里找不到项目包，用 `python -m pytest`。

```powershell
cd framework
python -m pytest -q testing tests                    # 1180 passed, 3 skipped 的基线上只增不减，skip 不增加
python -m surprise.gates.s19                         # S19 GATE: PASS (12/12)
python -m surprise.gates.s09                         # PASS (12/12)
python -m surprise.gates.s10                         # PASS (12/12)
python -m surprise.gates.s15 --only config llm prices   # PASS (3/3)
```

（`gates.s19` 的 `balance` 组会往终端打几行乱码的看守日志，属正常。）

## 收尾

1. 把改动提交到当前分支；`git status` 应当是干净的。
2. 写 `.orch/report.md`（不入库），格式：改了哪些文件；跑了哪些命令（命令、退出码、输出末 20 行原样）；与说明的偏差（没有写"无"）；未决问题（没有写"无"）。
3. 说明有矛盾或做不完：写进报告，停下。
