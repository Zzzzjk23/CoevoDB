角色：执行者

# 工作包 s05-ast：φ 的语句层（sqlglot 提取与正则兜底）

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s05-ast`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s05`（`s05-vocab` 已合并）
- 所属会话：S5（Phase 2：共同语言 φ），范围见 `framework/surprise/docs/SESSIONS.md` 的 S5 一节
- 依赖：`surprise.features` 里已有词表、注册表（`default_registry`、`Registry`、`FeatureDef`）、φ 容器、规格核对、单元投影。先把 `framework/surprise/features/` 读一遍，沿用它的写法。`.venv` 里有 `sqlglot==30.21.0`
- 后续：计划层、数据层、组合入口由 `s05-dynamic` 做，本包不碰引擎

## 目标

依据 `framework/surprise/docs/PLAN.md` 第 5 节 Phase 2 与第 6 节决策 5（φ 用 sqlglot，正则兜底）。交付一个纯函数：

```python
extract_ast(sql: str, engine: str, registry=None) -> tuple[frozenset[str], str]
```

返回语句层的特征集合与状态。状态是 `"ok"`（sqlglot 解析成功）或 `"fallback"`（解析失败，特征来自正则）。放在 `framework/surprise/features/ast.py`，从 `surprise.features` 导出。不执行 SQL，不连引擎，同一输入永远返回同一结果。

验收以 `framework/surprise/gates/s05.py` 的 `ast` 组为准，前三组 `vocab spec units` 必须保持通过。每个特征的含义以 `framework/surprise/gates/s05_cases.py` 为准：`CORE_VOCAB` 的第三列是定义，`AST_PROBES` 是例子（每条给出必须有与不许有的特征），`FAMILIES` 是十二个已知族的最小复现必须出现的特征。先把这个文件读完。特征包不许 import `surprise.gates`。

### 规则

1. **方言**：`duckdb` 用 sqlglot 的 `duckdb`，`datafusion` 与 `postgres` 用 `postgres`，`sqlite` 用 `sqlite`，其他引擎名用 sqlglot 的默认方言。
2. **只输出词表里的叶子**：每个输出的 id 都满足 `registry.known(id)` 且种类是 leaf，层是 `ast`。`ast:fn:<名>` 是开放族，名字取函数在 sqlglot 里的 `sql_name()` 的小写（匿名函数取它写出来的名字的小写）；名字里有字母、数字、下划线以外的字符就不输出。
3. **范围**：除了 `ast:stmt:*` 只看顶层语句，其余特征在整条语句的任何位置出现都算，包括子查询与 CTE 内部。
4. **名字不是特征**：表名、列名、别名、大小写、空白、注释、末尾分号都不影响结果（`AST_INVARIANT` 的每一对必须得到相同的集合）。
5. **需要想清楚的定义**（`AST_PROBES` 里各有例子）：
   - 集合运算按有没有 ALL 区分成六个叶子。
   - 连接：`JOIN` / `INNER JOIN` 带条件与 `NATURAL JOIN` 是 `ast:join:inner`；逗号分隔的两个关系和 `CROSS JOIN` 是 `ast:join:cross`；`ASOF JOIN` 是 `ast:join:asof`，写了方向的再加上方向。`ast:join_trait:self` 指同一个基表名在整条语句里被引用两次以上（CTE 的名字不算基表）。`ast:join_trait:non_equi` 指某个连接的 ON 条件里有 `<`、`<=`、`>`、`>=` 或 `<>` 比较。
   - 子查询的八种形式互斥地按出现处判定：`NOT EXISTS (...)` 只记 `not_exists` 不记 `exists`，`NOT IN (SELECT ...)` 只记 `not_in`；`IN (值列表)` 是 `ast:pred:in_list`，不是子查询；作为 EXISTS、IN、ALL、ANY 操作数的查询不算 `scalar`；FROM 或 JOIN 里当表用的查询（含 LATERAL 后面的）是 `derived`。
   - `ast:subquery_pos:*` 是包含该子查询的那一层查询的子句：选择列表、WHERE、FROM（含被连接的关系）、HAVING、连接的 ON。
   - `ast:subquery_trait:correlated`：子查询引用了外层查询的带限定名的列。用 `sqlglot.optimizer.scope`（`build_scope`、`external_columns`）判断，不要自己猜。不带限定名的列无法归属，不算。
   - `ast:corr_cmp:*`：相关子查询里，一边是本层的列、另一边是外层的列的比较，运算符照写出来的记（不调换方向）。两边都必须是裸的列引用：`(r.wh + 0) <> x.wh` 不算。
   - 聚合类（`ast:agg:*`、`ast:agg_trait:*`）只管不带 OVER 的聚合调用；带 OVER 的归 `ast:window_fn:aggregate`。`COUNT(*) OVER ()` 没有 `ast:agg:count`，也没有 `ast:agg_trait:star`。
   - 窗口：`ast:window_spec:empty` 是 `OVER ()`；`ast:window_frame:preceding` / `following` 把 UNBOUNDED 的也算上；`ast:window_trait:dup_partition_key` 是同一个 PARTITION BY 列表里同一个表达式出现两次；`ast:window_trait:ordered_arg` 是被窗口化的函数的参数表里有 ORDER BY（`ntile(2 ORDER BY v) OVER (...)`）。
   - `ast:clause:where` 是查询、UPDATE、DELETE 的 WHERE，不包括聚合的 `FILTER (WHERE ...)`。`ast:clause:order_by` 是查询或集合运算的 ORDER BY，不包括 OVER 里的和聚合参数里的。`ast:clause:distinct` 是 `SELECT DISTINCT`，不包括 `count(DISTINCT x)`。
   - `ast:cmp:*` 记整条语句里出现的比较运算符，相关子查询里的、连接条件里的也算；BETWEEN 不拆成两个比较，它里面的 AND 也不算 `ast:bool:and`。
   - `ast:pred:is_null` 与 `ast:pred:is_not_null` 互斥地按出现处判定。
   - `ast:expr:arith` 是二元的 `+ - * / %`；一个操作数是 INTERVAL 字面量的加减同时记 `ast:expr:date_arith`。
   - `ast:fn:*` 不包括已经有自己特征的东西：聚合、窗口的排名与导航函数、COALESCE、NULLIF、CAST、CASE、CONCAT，也不包括 sqlglot 当成函数类实现的 AND、OR 这类连接词。
   - MERGE：每个 WHEN 子句按 MATCHED / NOT MATCHED / NOT MATCHED BY SOURCE 与 UPDATE / DELETE / INSERT 各记一个叶子。
6. **正则兜底**：sqlglot 抛异常、返回空、或者一段文本里有不止一条语句时，状态为 `fallback`，输出 `ast:parse:fallback` 加上用正则能认出来的叶子。兜底的叶子不要求精细，但要诚实：认不准的就不输出。至少做到 `FALLBACK_PROBES` 的要求（窗口、连接、WHERE、查询级的 ORDER BY 能认出来）。解析成功的语句不许带 `ast:parse:fallback`。
7. **发明的特征**：注册表里已验收（`accepted` 为真）、`definition["kind"] == "regex"` 的特征，按 `re.search(pattern, sql, re.IGNORECASE)` 是否命中决定输出，两种状态下都生效；未验收的不输出。用调用方传进来的 `registry`，没传就用 `default_registry()`。
8. 词表不够用时可以往 `features/vocabulary.py` 里追加叶子或类（比如给窗口里既不是排名、导航也不是聚合的函数留一个叶子），只许追加，不许改已有条目；`CORE_VOCAB` 的条目必须原样保留。追加的每一项要有测试。

### 顺带的一处小修（上一个包审查留下的）

`framework/surprise/features/phi.py` 的 `_require_layers`：层状态的取值不是字符串时（比如 `{"ast": "ok", "plan": ["ok"], "data": "ok"}`），现在抛 `TypeError: unhashable type`，应当抛 `ValueError`。`Phi.from_dict` 与 `make_phi` 都走这个函数，从账本读回一条坏记录时调用方只接 `ValueError`。改法：取值先判 `isinstance(value, str)`，不是就抛 `ValueError`。这个文件只许改这一处，补一条测试（放在你的测试文件里）。

### 测试

新增 `framework/tests/test_surprise_s05_ast*.py`。每个核心叶子至少一条正例一条反例；上面第 5 条的每一点各有测试；名字无关性；兜底；发明特征验收前后；十二个族的两两可区分。测试里的 SQL 自己写，不要 import `surprise.gates`。

## 背景

编排者派发前用 sqlglot 30.21.0 实测：

- 十二个已知族的最小复现全部能解析，包括 F10 的 `ntile(2 ORDER BY v) OVER (ORDER BY v ROWS BETWEEN 2 FOLLOWING AND 1 FOLLOWING)`（参数里的 ORDER BY 是 `Ntile.this` 下的 `Order`，帧在 `Window.args["spec"]` 里）、F11 的 `WHEN NOT MATCHED BY SOURCE THEN DELETE`（`When(matched=False, source=True, then=Var(DELETE))`）、F3 的 ASOF JOIN（`Join.args["method"] == "ASOF"`）。
- `NATURAL JOIN` 是 `Join(method="NATURAL")`；逗号连接是既没有 on、using 也没有 side、kind、method 的 `Join`；`EXCEPT ALL` 是 `Except(distinct=False)`。
- 种子语料 `framework/seeds/corpus.json` 的 1092 条里有 34 条解析不了：没填的模板占位符（`{agg}(id) OVER (...)`、`r::{type}`）和 PostgreSQL 的 `JOIN ... USING (i) AS x`。它们走兜底。
- sqlglot 把 `substr` 归一成 `SUBSTRING`、`date_trunc` 归一成 `TIMESTAMP_TRUNC`，所以 `ast:fn:` 后面的名字是 sqlglot 的名字，不一定是原文里写的。
- 旧的 `framework/coverage/features.py` 里有一份正则清单，可以参考它认哪些语法点来写兜底，但不要 import 它。

## 允许改动的路径

只改下面这些路径（`**` 跨目录，`*` 不跨）。审查按这个清单逐个文件核对，清单以外的任何改动都算越界。

```allow-paths
framework/surprise/features/ast.py
framework/surprise/features/__init__.py
framework/surprise/features/vocabulary.py
framework/surprise/features/phi.py
framework/tests/test_surprise_s05_ast*.py
```

`phi.py` 只限"顺带的一处小修"那一处。

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`。
- 不改 `framework/surprise/harness/`（已冻结）与 `framework/surprise/theory/`。
- `features/` 里上一个包的文件，除了 `__init__.py` 加导出、`vocabulary.py` 追加条目、`phi.py` 那一处小修之外不动；发现它们有错，写进报告的"未决问题"，停下。
- 旧代码（`framework/surprise/` 以外）本包不碰。
- 本包不执行 SQL、不连接任何引擎。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。某个已有测试确实该改（比如你追加了词表条目而某个测试钉死了条目数），写进报告的"未决问题"，停下。
- 不按 SQL 文本、表名或族号硬编码结果：特征只来自语法结构。
- 标签路径上不调用 LLM；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。本包不需要任何 LLM 调用。
- 不安装、不升级任何依赖，不动 `.venv`、`.venvs/`、`.orch/pg16/`。
- 不清理 `.orch/tmp`：临时文件留着不管，包括你自己建的（提交信息用 `git commit -m`）。不建任何指向 worktree 之外的链接或目录联接。被权限规则拒绝的操作不要换写法重试。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests                          # 0 failed，通过数不少于 297，skip 不多于 3
python -m surprise.gates.s01                               # 退出码 0
python -m surprise.gates.s02                               # 退出码 0
python -m surprise.gates.s03                               # 退出码 0
python -m surprise.gates.s04                               # 退出码 0，约 4 分钟
python -m surprise.gates.s05 --only vocab spec units ast   # 退出码 0
```

`python -m surprise.gates.all` 在本包结束时仍会报 s05 FAIL：其余五组属于下一个包，这是预期的。不要直接跑不带路径的 `pytest`。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。认为门槛或契约表的某个期望不对，写明是哪一行、sqlglot 实际给出什么，停下。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s05-ast

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
