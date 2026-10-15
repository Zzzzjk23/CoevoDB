角色：执行者

# 工作包 s11-purellm2：纯 LLM 对照组的提示修正（谓词的拼法）与每次 4 个用例

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s11-purellm2`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s11`（`s11-purellm` 已合并：`framework/surprise/baselines/pure_llm.py`；门槛表 `gates/s11_cases.py` 已经改成每次 4 个用例）
- 所属会话：S11；这是 `s11-purellm` 合并后的修正包

## 问题

编排者用真实调用录纯 LLM 对照组（DuckDB 1.5.5，种子 0，fast 档）时发现两件事：

1. **提示没有讲清谓词怎么拼进语句，8 条用例里 7 条无效。** harness 对带谓词的用例拼出 `query WHERE (predicate)`（plan variant、index presence、version differential、cross-DBMS 都这样；TLP / NoREC 也要求 `query` 本身是不带 WHERE 的普通查询）。模型写的是 `SELECT grp, COUNT(*) ... FROM t1 GROUP BY grp HAVING ... ORDER BY grp;` 再给一个谓词 `id > 0`，拼出来是 `...ORDER BY grp; WHERE (id > 0)`，于是 query_error 或 not_applicable。这是 S2 记下的规则（`HANDOFF.md` 的"S2 新发现"第 4 条）：只有普通的 `SELECT ... FROM ...` 才能带谓词；别的形状要把过滤条件写进 `query`、`predicate` 留空。现在的提示里只有"an optional predicate is inserted as the top-level WHERE"，模型看不出这层限制。这让对照组显得比它本来的能力差，不公平。
2. **每次 8 个用例时，4 次调用里 3 次被 16000 的上限截断**（输出 token 恰好 16000，没有 JSON，网关 `no_json` 拒收）；唯一成功的一次用了 12898 个输出 token。`deepseek-flash` 把推理 token 算进上限。

## 目标

只改 `framework/surprise/baselines/pure_llm.py`（与它的测试）：

1. `PURE_LLM_CASES_PER_CALL = 4`（门槛表已改；注释写明原因：8 个时 16000 的上限装不下推理）。别的常数不变。
2. 改提示（英文，仍然只依赖种子、批号、引擎与 oracle 列表，不带任何随运行而变的东西）：
   - 写明拼法：`predicate` 不是 null 时，harness 执行的是 `<query> WHERE (<predicate>)`（TLP / NoREC 另有它们自己的拼法，但同样要求 `query` 不带 WHERE）。所以给了 `predicate` 的用例，`query` 必须是普通的 `SELECT <列> FROM <表或连接>`：不能有 WHERE、GROUP BY、HAVING、ORDER BY、LIMIT、OFFSET、集合运算、窗口子句，也不能以分号结尾。
   - 想测 GROUP BY、HAVING、ORDER BY、集合运算、窗口等形状时，把过滤条件直接写进 `query`、`predicate` 设为 null，并选不需要谓词的 oracle（plan_variant、equivalent_query、version_differential、cross_dbms、index_presence）；TLP 与 NoREC 必须有谓词，因此只能配普通的 `SELECT ... FROM ...`。
   - `query`、`predicate` 与每条 setup 语句都不要以分号结尾。
   - 请模型把推理写短，整个回复（含推理）要在 `PURE_LLM_MAX_TOKENS` 个 token 以内。
   - 各 oracle 那一句说明里与上面冲突的措辞一并改正（例如 equivalent_query 的说明现在允许"WHERE 写在 query 里"——这仍然成立，但要与"给了 predicate 时 query 不带 WHERE"一致）。
3. **不在代码里替模型修 SQL**（不去掉分号、不改写语句、不挪谓词）：对照组测的是"LLM 本身能走多远"，harness 判 invalid 就是 invalid。只改提示与常数。
4. 测试：更新 `framework/tests/test_surprise_s11_pure_llm.py` 里依赖每次用例数的断言（如果有），并加一条测试检查提示里写明了拼法规则（例如含 `WHERE (` 与 "semicolon" 字样）与 `PURE_LLM_CASES_PER_CALL` 的值。

## 允许改动的路径

```allow-paths
framework/surprise/baselines/pure_llm.py
framework/tests/test_surprise_s11_pure_llm.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`（已冻结）。
- 不改别的模块；旧代码不碰。
- 不做任何真实 LLM 调用（测试用脚本替身）；不读取或打印 `DEEPSEEK_API_KEY`。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`；不要清理 `.orch/tmp`。

## 验收命令

在 worktree 里执行。`python` 和 `pytest` 已经指向项目解释器。shell 是 Windows PowerShell 5.1（没有 `&&`，用 `;`）。

```powershell
cd framework
python -m pytest -q testing tests                              # 0 failed，通过数不少于基线
python -m surprise.gates.s11 --only constants pure_llm_script  # 两组 PASS
python -m surprise.gates.s11 --only pure_llm                   # 预期 FAIL：缺新的录制（编排者合并后重录）
```

## 收尾

1. 把改动提交到当前分支；`git status` 应当是干净的。
2. 写 `.orch/report.md`（不入库），格式：改了哪些文件；跑了哪些命令（命令、退出码、输出末 20 行原样）；与说明的偏差；未决问题。
3. 说明有矛盾、缺前置条件或做不完：写进报告，停下。
