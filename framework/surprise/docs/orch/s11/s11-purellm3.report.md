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
