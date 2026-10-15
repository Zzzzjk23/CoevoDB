# 审查包 · s11-purellm3

- 生成时间：2026-10-16T06:48:32+11:00
- 基线：`session/s11`（7e202e5f2324）
- 分支：`grok/s11-purellm3` @ 88c47a1a8f62，基线之上 1 个提交
- 运行：共 1 轮（返工 0 轮），最近一轮退出码 0，用时 10m38s
- grok：grok 1.0.46 (2765805b9442)；会话 `47b97c33-005c-47c2-ba0e-65bc5af0b270`

## 红旗汇总

- 本次审查包没有复跑测试（--skip-tests）
- 测试里被改写的断言 10 处（逐条确认没有放宽）
- 派发以来有 1 处 tag 变化或 ref 被删：确认是编排者自己做的，不是执行者

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s11..grok/s11-purellm3
git diff -M --stat session/s11..grok/s11-purellm3
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/baselines/pure_llm.py`、`framework/tests/test_surprise_s11_pure_llm.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/baselines/pure_llm.py` |  |
| M | `framework/tests/test_surprise_s11_pure_llm.py` |  |

提交：

- 88c47a1 Junke: baselines(s11): answer-first pure-LLM prompt, cap 32000 tokens

## 2. diff 统计

```text
 framework/surprise/baselines/pure_llm.py      | 116 ++++++++------------------
 framework/tests/test_surprise_s11_pure_llm.py |  71 +++++++++++-----
 2 files changed, 89 insertions(+), 98 deletions(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

按 `--skip-tests` 跳过了 pytest 与门槛。

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- `framework/tests/test_surprise_s11_pure_llm.py:76` 原：`assert PURE_LLM_MAX_TOKENS == 16000 and type(PURE_LLM_MAX_TOKENS) is int` → 同一处新增：`assert PURE_LLM_MAX_TOKENS == 32000 and type(PURE_LLM_MAX_TOKENS) is int`
- `framework/tests/test_surprise_s11_pure_llm.py:107` 原：`assert "TLP and NoREC require a predicate" in prompt` → 同一处新增：`assert all(name in prompt for name in oracles)`
- `framework/tests/test_surprise_s11_pure_llm.py:108` 原：`assert PURE_LLM_CASES_PER_CALL == 4` → 同一处新增：`assert all(name in prompt for name in oracles)`
- `framework/tests/test_surprise_s11_pure_llm.py:109` 原：`assert f"exactly {PURE_LLM_CASES_PER_CALL} cases" in prompt` → 同一处新增：`assert all(name in prompt for name in oracles)`
- `framework/tests/test_surprise_s11_pure_llm.py:110` 原：`assert str(PURE_LLM_MAX_TOKENS) in prompt` → 同一处新增：`assert all(name in prompt for name in oracles)`
- `framework/tests/test_surprise_s11_pure_llm.py:140` 原：`assert script.seen[0] == (TIERS["fast"], 0.8, 16000, "pure_llm")` → 同一处新增：`assert script.seen[0] == (TIERS["fast"], 0.8, 32000, "pure_llm")`
- `framework/tests/test_surprise_s11_pure_llm.py:179` 原：`assert "Batch: 0" in script.prompts[0] and "Batch: 1" in script.prompts[1]` → 同一处新增：`assert f"Topic: {first_topic}. Batch 0. Seed 3." in script.prompts[0]`；`assert f"Topic: {second_topic}. Batch 1. Seed 3." in script.prompts[1]`；`assert "Reply with one JSON object" in script.prompts[0]`
- `framework/tests/test_surprise_s11_pure_llm.py:180` 原：`assert "Seed: 3" in script.prompts[0]` → 同一处新增：`assert f"Topic: {first_topic}. Batch 0. Seed 3." in script.prompts[0]`；`assert f"Topic: {second_topic}. Batch 1. Seed 3." in script.prompts[1]`；`assert "Reply with one JSON object" in script.prompts[0]`
- `framework/tests/test_surprise_s11_pure_llm.py:181` 原：`assert f"Topic for this batch: {first_topic}." in script.prompts[0]` → 同一处新增：`assert f"Topic: {first_topic}. Batch 0. Seed 3." in script.prompts[0]`；`assert f"Topic: {second_topic}. Batch 1. Seed 3." in script.prompts[1]`；`assert "Reply with one JSON object" in script.prompts[0]`
- `framework/tests/test_surprise_s11_pure_llm.py:182` 原：`assert f"Topic for this batch: {second_topic}." in script.prompts[1]` → 同一处新增：`assert f"Topic: {first_topic}. Batch 0. Seed 3." in script.prompts[0]`；`assert f"Topic: {second_topic}. Batch 1. Seed 3." in script.prompts[1]`；`assert "Reply with one JSON object" in script.prompts[0]`

### 4.4 新增的宽泛异常捕获

- 无

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s11-purellm3.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 删除 `refs/heads/grok/s11-report`（原 c668fbe94e56）
- 移动 `refs/heads/session/s11` 7e202e5f2324 → cc2af2b69a5c

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s11-purellm3.jsonl`：1449 条事件（available_commands 26，end 1，orch.exit 1，orch.start 1，text 509，thought 463，tool_call 34，tool_call_update 393，usage 21）；各轮合计 21 个模型回合，grok 上报花费 0.3214 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_update [completed]: {"type": "ReadFile", "FileContent": {"content": "1→# s11-purellm2 报告\n\n提交：`edd9352`（`baselines(s11): spell out predicate splicing and asks for 4 cases`），分支 `grok/s11-purellm2`。提交…
thought: 将撰写类似报告。该简报未要求运行 pure_llm 门组。 pytest 15 项测试全部通过，耗时 16.25 秒。Gate 测试已捕获，其中 pure_llm_script 耗时 5 秒。提示词与 max_tokens 已变更，旧录制缓存键不匹配，需编排者重录。`_ORACLE_TEXT` 的删除仍待确认。 报告将写入 `.orch/report.md…
tool_call write: {"file_path": "D:\\CoevoDB\\.worktrees\\s11-purellm3\\.orch\\report.md", "content": "# s11-purellm3 报告\n\n提交：`88c47a1`（`baselines(s11): answer-first pure-LLM prompt, cap 32000 tok…
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "", "new_string": "# s11-purellm3 报告\n\n提交：`88c47a1`（`baselines(s11): answer-first pure-LLM prompt, cap 32000 tokens`），分支 …
tool_call run_terminal_command: {"command": "git status --short ; git status", "description": "Confirm worktree is clean after report"}
tool_update [in_progress]: 
tool_update [in_progress]: On branch grok/s11-purellm3 nothing to commit, working tree clean
tool_update [completed]: exit: 0 On branch grok/s11-purellm3 nothing to commit, working tree clean
thought: 工作已完成。正在准备最终回复。
text: 纯 LLM 对照组已换成先给答案的短提示，输出上限改为 32000。提交 `88c47a1`，分支 `grok/s11-purellm3`，工作区干净。报告在 `.orch/report.md`。 - `framework/surprise/baselines/pure_llm.py`：`PURE_LLM_MAX_TOKENS = 32000`。`_pro…
end: stopReason=end_turn turns=21 cost_usd=0.32140744
orch.exit: {"pkg": "s11-purellm3", "run": 1, "at": "2026-10-16T06:48:16+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# s11-purellm3 报告

提交：`88c47a1`（`baselines(s11): answer-first pure-LLM prompt, cap 32000 tokens`），分支 `grok/s11-purellm3`。提交后 `git status` 干净（`.orch/` 已忽略）。

## 改了哪些文件

- `framework/surprise/baselines/pure_llm.py`
  - `PURE_LLM_MAX_TOKENS` 从 16000 改为 32000。注释写明原因：上一版提示的 6 次真实调用都在 16000 个输出 token 处截断、正文为空；同一提示把上限提到 32000，或把温度降到 0.2，推理仍跑满上限。这条先给答案的短提示在约 14981 个输出 token 后给出 4 条用例，所以 32000 留出余量。`deepseek-flash` 的推理 token 计入上限。
  - 其余常数未改：fast 档、温度 0.8、每次 4 个用例、主题表。
  - `_prompt` 改为说明里的模板，用 `str.format` 填 `{n}`、`{engine}`、`{version}`、`{topic}`、`{batch}`、`{seed}`、`{oracles}`。`{oracles}` 是本次运行的 oracle 名，按传入顺序用 `", "` 连接。JSON 花括号写成双花括号。`tlp and norec` 那一条始终保留。
  - 删掉 `_ORACLE_TEXT` 和导入时与 `ORACLE_IDS` 对齐的检查。提示不再逐个解释 oracle，这张表没有别的引用。
  - 没有在代码里改写模型写出的 SQL。
- `framework/tests/test_surprise_s11_pure_llm.py`
  - `PURE_LLM_MAX_TOKENS == 32000`；网关调用的 `max_tokens` 断言从 16000 改为 32000。
  - 提示断言改为整段与模板逐字相等，并保留 `WHERE (`、`semicolon`、`Reply with one JSON object`、`set predicate to null`，以及每个 oracle 名都出现。同一 seed 再跑一次，两次提示相同。
  - 批次行的旧措辞（`Batch:`、`Seed:`、`Topic for this batch:`）换成模板里的 `Topic: … Batch … Seed …`。

## 跑了哪些命令

没有真实 LLM 调用，没有读取或打印 `DEEPSEEK_API_KEY`。

### `cd framework; python -m pytest -q tests/test_surprise_s11_pure_llm.py --tb=short`

退出码 0。输出末 20 行：

```
...............                                                          [100%]
15 passed in 16.25s
```

### `cd framework; python -m pytest -q testing tests --tb=line`

退出码 0。输出末 20 行：

```
........................ss..................................s........... [  7%]
........................................................................ [ 15%]
........................................................................ [ 23%]
........................................................................ [ 31%]
........................................................................ [ 38%]
........................................................................ [ 46%]
........................................................................ [ 54%]
........................................................................ [ 62%]
........................................................................ [ 69%]
........................................................................ [ 77%]
........................................................................ [ 85%]
........................................................................ [ 93%]
................................................................         [100%]
925 passed, 3 skipped in 277.75s (0:04:37)
```

全套里的 3 个 skip 是原有的。本包没有新增 skip / xfail，没有删断言的条件、没有放宽剩余断言，没有改 conftest。

### `cd framework; python -m surprise.gates.s11 --only constants pure_llm_script`

退出码 0。输出末 20 行：

```
[PASS] constants: 7 metric constants, request deadline 600.0 s, pure-LLM constants and 10 topics (0s)
[PASS] pure_llm_script: 4 cases executed from 3 calls (1 reply rejected, 2 bad cases skipped); prompts deterministic; budget holds (5s)
S11 GATE [only: constants, pure_llm_script]: PASS (2/2 groups passed)
```

## 与说明的偏差

无实质偏差。两处说明允许的选择：

- 删掉 `_ORACLE_TEXT` 和它的导入时检查，而不是留着不用。
- 新模板不包含 token 上限数字，所以去掉提示里 `str(PURE_LLM_MAX_TOKENS)` 这句断言。上限改由 `PURE_LLM_MAX_TOKENS == 32000` 和网关参数 `32000` 钉住。`PURE_LLM_CASES_PER_CALL == 4` 仍在 `test_constants_match_the_planned_values`。

## 未决问题

- 本包的验收命令不含 `pure_llm` 组，没有跑。缓存键含提示的 SHA-256，提示和 `max_tokens` 都变了，旧的 `gates/s11_llm/pure_llm` 录制对不上。合并后由编排者重录。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：
