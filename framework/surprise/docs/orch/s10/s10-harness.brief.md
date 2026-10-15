角色：执行者

# 工作包 s10-harness：Equivalent query 改写规则库的第二层（已验收的 LLM 改写模板；用户批准的小范围解冻）

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s10-harness`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s10`（`s09-done-r2` 加上 S10 门槛的提交）
- 所属会话：S10（Phase 5b：其余四个 LLM 角色，里程碑 M3），范围见 `framework/surprise/docs/SESSIONS.md` 的 S10 一节
- 依赖：冻结的 harness（S4 起）。**用户在 2026-10-15 批准了一次小范围解冻**：只许改 `framework/surprise/harness/oracles/rewrites.py` 与 `framework/surprise/harness/oracles/equivalent_query.py` 两个文件，给改写规则库加第二层；冻结的三条规则、比较与判 fail 的代码不变；改完由编排者重新生成冻结清单。harness 里任何别的文件都不许动（审查会按文件核对，门槛 `frozen` 组用 `git diff` 查）。
- 先读：`framework/surprise/gates/s10.py` 的 `check_frozen`、`check_library` 与 `s10_cases.py` 的 `LIBRARY*`、`TEMPLATES_*`、`APPLY_CASES`、`FROZEN_*`——**门槛就是接口规格**，与本说明不一致时以门槛为准，并写进报告；`harness/oracles/rewrites.py` 与 `equivalent_query.py` 全文；`harness/oracles/cross_dbms.py`（`default_reference_factories`、参照引擎怎么建、怎么跑）；`harness/oracles/common.py`（`invalid_label`、`label_from_results`、`fail_label`、`fail_kind_of`）；旧代码 `oracles/equivalence.py`（`EquivalenceOracle.check`，只读不改）；`harness/contracts.py` 里 `untrusted_rewrite` 的定义（"不来自冻结规则库，也不是经验证的 LLM 改写"）。
- 与你并行的包 `s10-frame` 改 `surprise/roles/`、`surprise/hunter/`、`surprise/experiments/loop.py`；它在 oracle 发明者开着的运行里把环境变量 `SURPRISE_REWRITE_LIBRARY` 设成库文件的路径。你不碰那些目录；双方只靠这个变量名与下面的库文件格式对接。

## 目标

PLAN 第 3 节："`oracles/equivalence.py` → Equivalent query oracle：改写规则库分两层：冻结的确定性规则 + 经验收的 LLM 改写"；逐项表："改写来自冻结的确定性规则库，或经 oracle 发明者验收的 LLM 改写时才判 fail；其余不一致记 invalid 进 Kᵛ"；决策 9："oracle 发明者先只用多引擎一致，证明器后续再接"。SESSIONS S10："oracle 发明者：提议等价改写或蜕变关系；多引擎一致才进入 Equivalent query 的改写规则库，判定代码不变。"

本包只做 harness 这一侧：库文件怎么读、模板怎么机械套用、第二层规则在判定前多一道参照引擎前提。**发明与验收**（调用 LLM、在语料上多引擎核对、写库文件）是之后的 `s10-oracle` 包的事，不在本包。本包不做任何 LLM 调用。

### 1. 第二层的形状：两种改写模板

LLM 发明的改写不是任意代码，而是两种**模板**之一，由 harness 机械套用：

- `query_wrap`：模板里恰好一个 `{q}`，代表整条被测语句（`full_query(case)` 的结果）。例：`SELECT * FROM ({q}) AS llm_sub`。
- `predicate_wrap`：模板里有 1–3 个 `{p}`，代表语句顶层 WHERE 的谓词。例：`({p}) IS TRUE`。

### 2. `rewrites.py` 新增（冻结的部分一字不改）

模块常数（门槛 `constants` 组逐个核对值与类型）：

```python
LIBRARY_ENV = "SURPRISE_REWRITE_LIBRARY"
LIBRARY_RULE_PREFIX = "llm:"
LIBRARY_KINDS = ("query_wrap", "predicate_wrap")
LIBRARY_MIN_REFERENCES = 2
LIBRARY_SCHEMA = 1
```

函数：

- `template_problem(kind: str, template: str) -> str | None`：模板可用时返回 None，否则返回一个简短的英文原因。不可用的情形至少有（门槛 `TEMPLATES_BAD` 逐条查）：`kind` 不在 `LIBRARY_KINDS`；不是字符串或为空；长于 2000 字符；含 `;`；含注释（`--` 或 `/*`）；`query_wrap` 的 `{q}` 不是恰好一个、或含 `{p}`；`predicate_wrap` 的 `{p}` 不是 1–3 个、或含 `{q}`；去掉占位符之后还有别的 `{` 或 `}`；用本模块的扫描器（`tokenize`）扫不通（引号不配对等）；含 `_DML` 里的关键字（如 `DELETE`、`INSERT`、`CREATE`）。
- `apply_template(query: str, kind: str, template: str) -> str | None`：模板不可用（`template_problem` 非 None）或前提不成立时返回 None；否则返回改写后的语句。
  - 共同前提：`query` 是一条只读语句（`is_read_only_query`）；允许末尾一个顶层分号，套用前去掉它。
  - `query_wrap`：结果 = 模板里的 `{q}` 换成去掉首尾空白（与末尾分号）的 `query`。
  - `predicate_wrap`：与 `double_negation` 用同一套定位：恰好一个顶层 WHERE（`_where_indexes`），谓词的词元范围用 `_predicate_bounds`；谓词原文 `p = _slice(query, 谓词词元)`；替换文本 = `"(" + 模板里每个 {p} 换成 "(" + p + ")" + ")"`；用 `_splice` 拼回去，范围外的原文逐字节保留。没有顶层 WHERE、或有多个 → None。
  - 结果必须仍是只读语句（`is_read_only_query`），且与原 `query` 不同；否则 None。
  - 门槛 `APPLY_CASES` 用 `same_statement` 比对结果。
- `load_library(path=None) -> dict[str, dict]`：读库文件，返回 `{rule_id: 条目}`（条目是下面格式里的 dict 的副本）。`path` 为 None 时读环境变量 `LIBRARY_ENV`；变量没设、文件不存在 → `{}`。文件只要有任何一处不合格，**整个库都不认**（返回 `{}`，fail closed）：不是 JSON；顶层不是对象；`schema` 不等于 `LIBRARY_SCHEMA`；`rules` 不是列表；某条规则缺键或类型不对；`rule_id` 不匹配 `^llm:[a-z0-9_]{1,40}$`；`rule_id` 重复；`rule_id` 去掉前缀后与冻结的 `RULES` 重名（门槛用 `rule_id="double_negation"` 试，那是没有前缀的情形，也必须不认）；`kind` / `template` 不可用（`template_problem` 非 None）；`argument` 不是非空字符串；`acceptance` 不是非空的 dict。每次调用都重新读文件（库在运行中会增长；判定在子进程里，进程一启动就读当时的文件）。
- `is_library_rule(rule_id: str) -> bool`：`rule_id` 以 `LIBRARY_RULE_PREFIX` 开头且在 `load_library()` 里。
- `apply_rule(query, rule_id)`：冻结的三条照旧（`RULES` 与 `_IMPL` 不改）；`rule_id` 以前缀开头时查 `load_library()`，在库里就 `apply_template(query, 条目["kind"], 条目["template"])`，不在 → None；别的 → None（照旧）。
- `RULES` 仍然恰好是冻结的三条（`surprise/hunter/operators.py` 读它；门槛查它的键与三条规则在固定输入上的输出）。

库文件格式（`s10-oracle` 写，你读）：

```json
{"schema": 1, "rules": [
  {"rule_id": "llm:wrap_sub", "kind": "query_wrap", "template": "SELECT * FROM ({q}) AS llm_sub",
   "argument": "why it preserves the result bag", "proposer": "oracle_inventor",
   "acceptance": {"...": "non-empty object written by the inventor"}}
]}
```

`proposer` 可以缺省；多余的键忽略。

### 3. `equivalent_query.py`：第二层规则的判定

冻结规则的路径**逐字节不变**（门槛核对：有库、无库时 `double_negation` 的标签 `detail` 都与解冻前完全相同）。只在 `rule_id` 是库里的规则（`is_library_rule`）时走下面的分支；`llm:` 开头但不在库里的规则，照旧判 `invalid / untrusted_rewrite`（与任何未知规则相同）。

1. 信任检查：`rule_id not in RULES and not is_library_rule(rule_id)` → `untrusted_rewrite`（照旧）。`rewritten = apply_rule(full, rule_id)`；`paired_query` 的核对、`not_applicable` 的判断照旧。
2. 目标引擎 setup 照旧（setup 报错 → `setup_error`）。
3. **参照引擎前提**（只对第二层规则）：参照集合与 `cross_dbms` 相同——`options.reference_factories` 给了就用它，否则 `default_reference_factories(case.engine)`。对每个参照引擎：新建 runner、跑 setup（报错就记 `skipped`）、在同一个 runner 上跑原查询与改写后的查询（`timeout_s` 照传）；两边都成功就比较结果多重集（用与 `EquivalenceOracle` 相同的比较：`oracles.db_runner.bags_equal`），相等记 `agree`，不等记 `disagree`；有一边失败记 `skipped`；最后关掉 runner。然后：
   - 有任何 `disagree` → `invalid_label(ORACLE, "untrusted_rewrite", full, extra={...,"premise": "reference_disagrees"})`；
   - `agree` 的个数 < `LIBRARY_MIN_REFERENCES` → 同上，`"premise": "too_few_references"`；
   - 否则前提成立，接着在目标引擎上照旧用 `EquivalenceOracle().check` 比较。
4. 比较之后，**只对第二层规则**：候选的 `fail_kind_of(candidate) == "error_mismatch"`（一边报错、一边成功）→ 不判 fail，判 `invalid / untrusted_rewrite`，`"premise": "rewrite_error"`（模板在这个引擎上不适用，不是缺陷的证据）。`wrong_result` 与 `crash` 照旧判 fail；没有候选照旧走 `label_from_results`（pass 或 invalid）。
5. 第二层规则的每一个标签（pass、fail、invalid）的 `detail` 都带：`"rule": rule_id`、`"layer": "library"`、`"kind"`、`"template"`、`"references": {引擎: "agree" | "disagree" | "skipped"}`（前提没跑到时可以缺）；改写成功时还有 `"rewritten"`；前提或改写报错不成立时有 `"premise"`（取值只能是 `reference_disagrees`、`too_few_references`、`rewrite_error`）。冻结规则的 `detail` 不多任何键。

门槛的实测期望（`s10_cases.LIBRARY_EXPECT`，DuckDB 目标，参照 DataFusion / SQLite / PostgreSQL）：`llm:wrap_sub`、`llm:is_true` → pass；`llm:first_row`（`LIMIT 1`，少了一行）→ `untrusted_rewrite / reference_disagrees`；`llm:octet`（DuckDB 1.5.5 没有 `octet_length(VARCHAR)`，三个参照都有）→ `untrusted_rewrite / rewrite_error`。这些标签经 `surprise.harness.cve.certify.certify` 拿（CVE 第 1 档的新进程重跑会再判一遍，同样的结果；环境变量会传进子进程）。

### 4. 测试

新文件 `framework/tests/test_surprise_s10_rewrite_library.py`，至少覆盖：`template_problem` 的每种不可用情形；`apply_template` 的两种模板、末尾分号、没有 WHERE、多个 WHERE、非只读；`load_library` 的变量没设、文件不存在、正常、每一种不合格（整库不认）；`apply_rule` 对冻结规则在有库、无库时输出完全相同；`judge` / `certify` 对第二层规则的四种结果（pass、`reference_disagrees`、`too_few_references`、`rewrite_error`）与 `detail` 的键；不在库里的 `llm:` 规则 → `untrusted_rewrite`；冻结规则的标签 `detail` 有库时不变。测试里用 `monkeypatch.setenv` / `delenv` 设变量，库文件放 `tmp_path`。PostgreSQL 参照在本机跑在 `127.0.0.1:55432`（见 `framework/AGENTS.md`）；测试与门槛都可以用它。

## 允许改动的路径

```allow-paths
framework/surprise/harness/oracles/rewrites.py
framework/surprise/harness/oracles/equivalent_query.py
framework/tests/test_surprise_s10_rewrite_library.py
```

审查包会把这两个 harness 文件标成"越界：禁区"——这是预期的（用户批准的解冻），编排者会逐行看 diff。**除这两个文件之外 harness 的任何改动都是真越界。**

## 禁止

- 不改 `framework/surprise/gates/`（包括 `s04_frozen.json`：重新冻结由编排者做）、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`；harness 里除上面两个文件以外的任何文件；`framework/surprise/` 的其余目录。
- 冻结的三条规则（`RULES`、`_IMPL`、`_apply_*`）、扫描器、`is_read_only_query`、`same_statement`、`EquivalenceOracle` 的比较与判 fail 的代码、`common.py` 的标签构造都不改；冻结规则走的代码路径不改。
- 旧代码（`framework/surprise/` 以外，包括 `oracles/equivalence.py`、`oracles/db_runner.py`）只读不改。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest；旧测试一个都不改。某个测试确实该改，就写进报告的"未决问题"，停下。
- 不做任何 LLM 调用；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不建指向 worktree 之外的链接或目录联接；不要清理 `.orch/tmp`；测试产生的临时文件只放 pytest 的 `tmp_path`。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。worktree 里跑测试一律用 `python -m pytest`。

```powershell
cd framework
python -m pytest -q testing tests        # 通过数不少于 692（起点），skip 仍是 3
python -m surprise.gates.s02             # 通过（三类健全 oracle 的旧判定不变）
python -m surprise.gates.s03             # 通过（Equivalent query 冻结规则的反例不变）
python -m surprise.gates.s10 --only library     # 通过
python -m surprise.gates.s10 --only frozen      # 预期失败，且失败信息只能是"the harness is re-frozen (gates/s04_frozen.json)"那一条：
                                                # 冻结清单由编排者在合并后重新生成；在它之前的 git diff 检查必须已经通过（只改了两个文件、都已提交）
```

`s04` 与 `s06` 门槛里核对冻结清单的组会因为哈希变了而失败，这是预期的，不用跑；`python -m surprise.gates.all` 也不用跑。在报告里注明。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s10-harness

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
