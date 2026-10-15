角色：执行者

# 工作包 s11-purellm3：纯 LLM 对照组换成短而先给答案的提示，上限 32000

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s11-purellm3`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s11`（`s11-purellm`、`s11-purellm2` 已合并；门槛表 `gates/s11_cases.py` 已改成 `PURE_LLM_MAX_TOKENS = 32000`）
- 所属会话：S11；纯 LLM 对照组的第二个修正包

## 问题

编排者按 `s11-purellm2` 的提示真实调用了 6 次，6 次都在 16000 个输出 token 处截断、回复正文为空（`deepseek-flash` 是推理模型，推理 token 计入上限，推理一直没结束）。另外的探测：同一个提示把上限提到 32000、或把温度降到 0.2，推理照样跑满上限。换成下面这个短而"先给答案"的提示（同样的拼法规则，压缩写法；告诉模型不要分析引擎内部、不要推断用例会不会失败），一次调用 14981 个输出 token 后给出 4 条用例。所以：换提示，并把上限提到 32000 留出余量。

## 目标

只改 `framework/surprise/baselines/pure_llm.py` 与它的测试：

1. `PURE_LLM_MAX_TOKENS = 32000`（注释写明原因）。其余常数不变（每次 4 个用例、温度 0.8、fast 档、主题表）。
2. `_prompt` 改成下面这个模板（**逐字使用**，只把花括号里的占位换成值；`{oracles}` 是本次运行的 oracle 名用 `", "` 连起来，`{n}` 是 `PURE_LLM_CASES_PER_CALL`，`{engine}` / `{version}` 照现有写法取，`{topic}` / `{batch}` / `{seed}` 照旧）。原来逐个 oracle 的说明段（`_ORACLE_TEXT`）不再放进提示；可以删掉这个表与它的导入时检查，或保留但不用——你定，在报告里写明。

```text
Write {n} SQL test cases that might expose logic bugs in {engine} {version}.
Topic: {topic}. Batch {batch}. Seed {seed}.

Reply with one JSON object and nothing else. Work quickly: do not analyse the engine's source or
internals, and do not try to work out whether a case fails. A harness runs every case and decides.

Format:
{"prediction": "<one sentence: what you expect to find>",
 "cases": [{"setup": ["CREATE TABLE ...", "INSERT INTO ..."], "query": "SELECT ...", "predicate": null,
            "oracle": "<one of the oracles below>", "expect": "pass"}]}

Rules:
- setup is a list of CREATE TABLE / INSERT statements; query is one SELECT. No statement ends with a semicolon.
- oracle is one of: {oracles}.
- tlp and norec need a predicate: a boolean expression without the WHERE keyword, and query must be exactly
  SELECT <columns> FROM <table or join>, with no WHERE, GROUP BY, HAVING, ORDER BY, LIMIT or set operation.
- For any other oracle, either put every filter inside query and set predicate to null (any SELECT shape),
  or give a predicate with a plain SELECT <columns> FROM <table or join>; the harness then runs
  <query> WHERE (<predicate>).
- expect is your guess, "pass" or "fail".
```

   注意模板里的 JSON 花括号是字面量（用 `str.format` 时要写成双花括号）；`tlp and norec ...` 那一条只在本次运行打开了 tlp 或 norec 时才有意义，但为了简单**始终保留**。
3. 不在代码里替模型修 SQL（照 `s11-purellm2` 的原则）。
4. 测试：更新提示相关的断言（含 `WHERE (`、`semicolon`、`Reply with one JSON object`、`PURE_LLM_MAX_TOKENS == 32000`、每个 oracle 名都出现在提示里、同一 seed 两次提示相同）。

## 允许改动的路径

```allow-paths
framework/surprise/baselines/pure_llm.py
framework/tests/test_surprise_s11_pure_llm.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`。
- 不改别的模块；旧代码不碰。
- 不做任何真实 LLM 调用（测试用脚本替身）；不读取或打印 `DEEPSEEK_API_KEY`。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言（提示文字变了，旧的措辞断言换成新的同等强度的断言），不用宽泛的 try/except，不改 conftest。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`；不要清理 `.orch/tmp`。

## 验收命令

```powershell
cd framework
python -m pytest -q testing tests                              # 0 failed
python -m surprise.gates.s11 --only constants pure_llm_script  # 两组 PASS
```

## 收尾

1. 提交到当前分支；`git status` 干净。
2. 写 `.orch/report.md`（不入库）：改了哪些文件；命令、退出码、输出末 20 行原样；与说明的偏差；未决问题。
3. 有矛盾或做不完：写进报告，停下。
