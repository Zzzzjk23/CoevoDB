# 审查包 · s11-purellm2

- 生成时间：2026-10-16T06:22:01+11:00
- 基线：`session/s11`（29260de8b2fd）
- 分支：`grok/s11-purellm2` @ edd93527cbdb，基线之上 1 个提交
- 运行：共 1 轮（返工 0 轮），最近一轮退出码 0，用时 12m16s
- grok：grok 1.0.46 (2765805b9442)；会话 `99c32dfb-1092-4ca3-9b39-673ac6c8ef91`

## 红旗汇总

- 本次审查包没有复跑测试（--skip-tests）
- 测试里被改写的断言 1 处（逐条确认没有放宽）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s11..grok/s11-purellm2
git diff -M --stat session/s11..grok/s11-purellm2
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/baselines/pure_llm.py`、`framework/tests/test_surprise_s11_pure_llm.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/baselines/pure_llm.py` |  |
| M | `framework/tests/test_surprise_s11_pure_llm.py` |  |

提交：

- edd9352 Junke: baselines(s11): spell out predicate splicing and ask for 4 cases

## 2. diff 统计

```text
 framework/surprise/baselines/pure_llm.py      | 48 +++++++++++++++++++--------
 framework/tests/test_surprise_s11_pure_llm.py | 33 +++++++++++++++++-
 2 files changed, 67 insertions(+), 14 deletions(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

按 `--skip-tests` 跳过了 pytest 与门槛。

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- `framework/tests/test_surprise_s11_pure_llm.py:77` 原：`assert PURE_LLM_CASES_PER_CALL == 8 and type(PURE_LLM_CASES_PER_CALL) is int` → 同一处新增：`assert PURE_LLM_CASES_PER_CALL == 4 and type(PURE_LLM_CASES_PER_CALL) is int`

### 4.4 新增的宽泛异常捕获

- 无

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s11-purellm2.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 移动 `refs/heads/grok/s11-report` 22b4b9af4eef → af6bfdc23f04
- 移动 `refs/heads/session/s11` 29260de8b2fd → 460e95f50860

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s11-purellm2.jsonl`：1676 条事件（available_commands 29，end 1，orch.exit 1，orch.start 1，text 384，thought 779，tool_call 39，tool_call_update 417，usage 25）；各轮合计 25 个模型回合，grok 上报花费 0.4190 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_update [completed]: exit: 0 [grok/s11-purellm2 edd9352] baselines(s11): spell out predicate splicing and ask for 4 cases 2 files changed, 67 insertions(+), 14 deletions(-) edd9352 baselines(s11): spe…
thought: Git 工作区干净，没有未提交的更改。 正在编写 .orch/report.md。该文件不会被提交，因为 .orch 目录已被 gitignore。报告将包含修改的文件、执行的命令及其退出码与输出末尾 20 行、与说明的偏差以及未决问题。Pytest 输出已截取末尾部分。 Pytest 运行结束，925 个测试通过，3 个跳过，耗时约 4 分钟。Gate …
tool_call write: {"file_path": "D:\\CoevoDB\\.worktrees\\s11-purellm2\\.orch\\report.md", "content": "# s11-purellm2 报告\n\n提交：`edd9352`（`baselines(s11): spell out predicate splicing and asks for 4…
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "", "new_string": "# s11-purellm2 报告\n\n提交：`edd9352`（`baselines(s11): spell out predicate splicing and asks for 4 cases`），…
tool_call run_terminal_command: {"command": "git status --short; git log -1 --oneline", "description": "Confirm worktree is clean after the report"}
tool_update [in_progress]: 
tool_update [in_progress]: edd9352 baselines(s11): spell out predicate splicing and ask for 4 cases
tool_update [completed]: exit: 0 edd9352 baselines(s11): spell out predicate splicing and ask for 4 cases
thought: 工作包已按 .orch/brief.md 完成，当前状态干净。
text: 纯 LLM 对照组的提示和每次用例数已改完，提交在 `edd9352`（`grok/s11-purellm2`），工作区是干净的。 `PURE_LLM_CASES_PER_CALL` 改为 4。提示写明：给了 `predicate` 时，harness 执行的是 `<query> WHERE (<predicate>)`，所以 `query` 只能是普通的…
end: stopReason=end_turn turns=25 cost_usd=0.41899356
orch.exit: {"pkg": "s11-purellm2", "run": 1, "at": "2026-10-16T06:21:28+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# s11-purellm2 报告

提交：`edd9352`（`baselines(s11): spell out predicate splicing and asks for 4 cases`），分支 `grok/s11-purellm2`。提交后 `git status` 干净（`.orch/` 已忽略）。

## 改了哪些文件

- `framework/surprise/baselines/pure_llm.py`
  - `PURE_LLM_CASES_PER_CALL` 从 8 改为 4。注释写明原因：deepseek-flash 把推理 token 算进 `max_tokens`，8 个用例装不进 16000，录到的 4 次回复里有 3 次在 16000 被截断。其余常数未改。
  - 提示（英文）写明拼法：`predicate` 不是 null 时，harness 执行 `<query> WHERE (<predicate>)`；TLP / NoREC 另有拼法，同样要求 `query` 不带 WHERE。给了谓词的 `query` 必须是普通的 `SELECT <columns> FROM <table or join>`，不能有 WHERE、GROUP BY、HAVING、ORDER BY、LIMIT、OFFSET、集合运算、窗口子句，也不能以分号结尾。
  - 要测 GROUP BY、HAVING、ORDER BY、集合运算、窗口时，过滤条件写进 `query`、`predicate` 为 null，并选不需要谓词的 oracle（plan_variant、equivalent_query、version_differential、cross_dbms、index_presence），且该 oracle 得在本批列表里。TLP 与 NoREC 必须有谓词，只配普通的 `SELECT ... FROM ...`。
  - `query`、`predicate` 和每条 setup 都不要以分号结尾。请模型把推理写短，整个回复（含推理）不超过 `PURE_LLM_MAX_TOKENS`。
  - 各 oracle 的一句说明与上面冲突的措辞已改掉（TLP 不再建议 GROUP BY / DISTINCT 配谓词；不再说 "an optional predicate is inserted as the top-level WHERE"；equivalent_query 仍允许 WHERE 写在 `query` 里，但给了 `predicate` 时 `query` 不带 WHERE）。
  - 没有在代码里改写 SQL（不去分号、不挪谓词）。
- `framework/tests/test_surprise_s11_pure_llm.py`
  - 每次用例数的断言从 8 改为 4。
  - 新增 `test_prompt_states_the_predicate_splice`：脚本替身跑一批，检查提示含 `WHERE (`、`semicolon`、`set predicate to null`、`TLP and NoREC require a predicate`、`exactly 4 cases` 和 token 上限，并确认旧的冲突句子已不在提示里。

## 跑了哪些命令

### `cd framework; python -m pytest -q tests/test_surprise_s11_pure_llm.py --tb=short`

退出码 0。输出末 20 行：

```
...............                                                          [100%]
15 passed in 17.20s
```

### `cd framework; python -m pytest -q testing tests`

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
925 passed, 3 skipped in 282.17s (0:04:42)
```

### `cd framework; python -m surprise.gates.s11 --only constants pure_llm_script`

退出码 0。输出末 20 行：

```
[PASS] constants: 7 metric constants, request deadline 600.0 s, pure-LLM constants and 10 topics (0s)
[PASS] pure_llm_script: 4 cases executed from 3 calls (1 reply rejected, 2 bad cases skipped); prompts deterministic; budget holds (4s)
S11 GATE [only: constants, pure_llm_script]: PASS (2/2 groups passed)
```

### `cd framework; python -m surprise.gates.s11 --only pure_llm`

退出码 1（说明里的预期 FAIL）。输出末 20 行：

```
[FAIL] pure_llm: gates/s11_llm/pure_llm is missing: the orchestrator records it with real calls after the merge
S11 GATE [only: pure_llm]: FAIL (0/1 groups passed)
```

没有真实 LLM 调用，没有读取或打印 `DEEPSEEK_API_KEY`。全套测试里的 3 个 skip 是原有的，本包没有新增 skip / xfail，也没有改断言以外的放宽。

## 与说明的偏差

无实质偏差。两处措辞上的实现选择：

- 提示在列出五个不需要谓词的 oracle 之后加了 "when that oracle is listed above"，避免模型去选本次运行没有打开的 oracle。字段说明里本来就要求 oracle 是上面列出的名字之一。
- 新测试除了 `WHERE (`、`semicolon` 和 `PURE_LLM_CASES_PER_CALL == 4`，还检查了形状规则的几句原文，以及旧的冲突句子已经删掉。

## 未决问题

- `pure_llm` 门槛按说明失败：缺 `gates/s11_llm/pure_llm` 的新录制。合并后由编排者重录。
- harness 仍然认识一部分 TLP 的 GROUP BY / DISTINCT 形态。提示按说明不再让模型用这些形态配谓词，代码没有去拦。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：
