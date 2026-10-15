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
