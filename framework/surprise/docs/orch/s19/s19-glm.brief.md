角色：执行者

# 工作包 s19-glm：LLM 角色加一档 GLM 5.3 Flash（OpenRouter）

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s19-glm`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s19`（12f4f1b）
- 所属会话：S19（E1 DuckDB 主对比）。换模型是用户 2026-10-20 加进本会话的范围，见 `framework/surprise/docs/SESSIONS.md` 的 S19 一节与 `PLAN.md` §9 最后一条
- 依赖：S15 的换档机制（网关 `Gateway(tier=...)`、主循环与纯 LLM 的 `--llm-tier`、网格臂的 `tier` 键），已在基线里

## 目标

用户决定 LLM 角色改用 OpenRouter 上的 `z-ai/glm-5.3-flash`：只用提供商 `open-inference/fp4`，不回退，开推理；接口与 OpenAI 兼容；密钥仍然从环境变量 `DEEPSEEK_API_KEY` 读。用户给的示例（OpenAI SDK）等价于下面这个请求：

```
POST https://openrouter.ai/api/v1/chat/completions
Authorization: Bearer <DEEPSEEK_API_KEY 的值>
{"model": "z-ai/glm-5.3-flash", "messages": [{"role": "user", "content": "<prompt>"}],
 "temperature": <t>, "max_tokens": <n>,
 "provider": {"only": ["open-inference/fp4"], "allow_fallbacks": false},
 "reasoning": {"enabled": true}}
```

做成一个新档 `glm-flash`，走 S15 已有的整次运行换档（`--llm-tier glm-flash`、网格臂 `"tier": "glm-flash"`）。原来的 fast / strong 两档、默认行为一点不变。

- `framework/surprise/roles/providers.py`（新）：`EXTRA_TIERS = {"glm-flash": {...}}`，值与 `framework/surprise/gates/s19_cases.py` 的 `NEW_PROFILE` 逐字相同（`model`、`base_url`、`body`）。可以再提供小函数（比如按档名或模型名取配置），名字自定。
- `roles/gateway.py`：强制档（`tier=`）接受 `TIERS` 与 `EXTRA_TIERS` 的键，其余照旧报 `ValueError`；`call` 用新档时模型取配置里的 `model`（缓存键、`Reply`、`calls.jsonl` 都记这个模型和档名 `glm-flash`）；`manifest()` 在强制档是新档时多记 `"endpoint": <那份配置>`，其余键不变。
- `roles/runtime.py`：运行 manifest 的 `llm` 一节（`manifest()`，约第 280 行）同样在新档时多记 `"endpoint"`。
- `roles/transport.py`：`DeepSeekTransport.complete(model=...)` 遇到新档的模型时，POST 到 `<base_url>/chat/completions`，请求体是原来的四个字段加上配置里 `body` 的字段，鉴权头照旧是 `DEEPSEEK_API_KEY`；其它模型的请求与现在逐字节相同。回复照旧读 `choices[0].message.content` 和 `usage.prompt_tokens` / `completion_tokens`；回复里多出的 `reasoning`、`reasoning_details` 不用管。HTTP 错误、`content` 为 null 时照旧抛 `TransportError`（402 这类状态码留在异常消息里，现在已经是这样）。类名 `DeepSeekTransport` 不改（有三处调用）。
- `experiments/grid.py` 的 `_TIERS`、`experiments/loop.py` 的 `_LLM_TIERS`、`baselines/pure_llm.py` 的 `--llm-tier` 可选值：加上 `glm-flash`。网格对 `"tier": "glm-flash"` 的臂照旧生成 `--llm-tier glm-flash`。
- `framework/surprise/metrics/data/prices_openrouter.json`（新）：内容与 `s19_cases.py` 的 `PRICES` 相同（JSON 相等即可）。
- 测试 `framework/tests/test_surprise_s19_glm.py`（新）：覆盖上面几条，全部离线（拦截 httpx，不发真请求）。

## 背景

- 调用路径：`Gateway.call` → `TIERS[tier]` 得到模型名 → `cache_key(prompt, model, seed)` → `transport.complete(model=...)` → `_read_with_deadline` 用 `BaseAgent` 建的 `httpx.Client`（`base_url` 是 DeepSeek）POST 相对路径 `/chat/completions`。httpx 接受绝对 URL，可以对新模型直接传完整地址；也可以为它另建一个 client，自己选，两种都要让 DeepSeek 的请求不变。
- 新档的配置**不要放进 `roles/constants.py`**：`constants.as_dict()` 收集模块里所有公开的大写常数，写进每一次运行的 manifest；放进去会改掉所有旧运行的 manifest，S9–S11、S15 的门槛回放会对不上。`roles/constants.py` 本包不许改。
- 不改 fast / strong 的映射：缓存键含模型名，门槛回放的录制缓存都是 DeepSeek 模型录的。不传 `--llm-tier glm-flash` 时，缓存键、`calls.jsonl`、`config.json`、manifest 都要与现在相同。
- 不引入 OpenAI SDK，照旧用 httpx：用户示例里的 `extra_body` 就是并进请求体顶层的字段；服务器的 venv 是逐个钉住版本的；S8 门槛把 `openai` 当成 LLM 模块。
- 示例后半段把 `reasoning_details` 回传给第二轮对话，本项目用不上：每个角色都是单轮调用，不要实现多轮。
- 门槛 `framework/surprise/gates/s19.py` 已经写好（编排者写的，你不能改），先读它：`transport` 组用替换 `httpx.HTTPTransport.handle_request` 的办法拦截请求，所以必须经 httpx 的默认传输层发请求；`gateway`、`replay`、`grid`、`prices`、`scope` 各组写明了要求。
- 改了 `experiments/` 之后，S08 门槛的 `longrun` 组会因代码摘要不同而失败，S11 的 `ciao` 也绑着那份产物。这是预期的，合并后由编排者重跑长跑、重钉，你不要动 `gates/s08_runs.json`。

## 允许改动的路径

只改下面这些路径（`**` 跨目录，`*` 不跨）。审查按这个清单逐个文件核对，清单以外的任何改动都算越界。

```allow-paths
framework/surprise/roles/gateway.py
framework/surprise/roles/transport.py
framework/surprise/roles/runtime.py
framework/surprise/roles/providers.py
framework/surprise/experiments/grid.py
framework/surprise/experiments/loop.py
framework/surprise/baselines/pure_llm.py
framework/surprise/metrics/data/prices_openrouter.json
framework/tests/test_surprise_s19_*.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`；不改 `framework/surprise/harness/`（已冻结）、`framework/surprise/roles/constants.py`、`framework/surprise/metrics/data/prices_deepseek.json`、`framework/agents/`、`framework/llm/`。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。这一条管基线里已有的测试与门槛：其中某个测试确实该改，就写进报告的"未决问题"，停下。本包新写的测试照常修改，只要改完仍检查这份说明要求的东西。
- 不登录、不连接实验服务器（不用 ssh、scp、rsync、sftp）。
- 本包不做任何真实的 LLM 调用（没有给你密钥）；测试一律离线。密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不顺手改别的：比如网关记 `reason` 只取异常类名、欠费时不报警（HANDOFF 的 S19 新发现）都不在本包范围。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
pytest -q testing tests                              # 1070 passed, 3 skipped 的基线上只增不减，skip 不增加
python -m surprise.gates.s19                         # S19 GATE: PASS (6/6)
python -m surprise.gates.s09                         # PASS
python -m surprise.gates.s10                         # PASS
python -m surprise.gates.s15 --only config llm prices   # PASS (3/3)
```

不用跑 `python -m surprise.gates.all`：worktree 里没有 `framework/results/s08/` 和 `.orch/sqlancer/`，S08、S11、S15 的几组本来就过不了；合并后编排者在主检出区跑全部门槛。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s19-glm

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改 / 移动自哪里）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
