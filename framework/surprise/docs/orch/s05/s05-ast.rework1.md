# 审查意见 · s05-ast · 第 1 轮返工

独立复跑：pytest 316 passed / 3 skipped；S01–S04 通过；S05 的 `vocab spec units ast` 四组通过。整份语料 1092 条不抛异常、只输出词表里的叶子、两次结果相同、兜底 34 条；400 条随机串不抛异常；改名不改变特征。`phi.py` 的小修、`ast:window_fn:other` 的追加都收下。

读完 `ast.py` 后编排者补了探测，下面七处判错了，都有反例。每一处给出现状、要改成什么、必须成立的例子。例子的写法：`语句` → 必须有 / 不许有。除了指明 postgres 的，引擎都是 `duckdb`。这些例子已经加进门槛表（你的 worktree 里的门槛文件是旧的，合并后会按新表检查），所以每一条都要做到，并且每一条都要在你的测试文件里有对应的测试。

没有列在下面的行为不要动：`AST_PROBES` 原有的 60 条、`FALLBACK_PROBES`、`AST_INVARIANT`、十二个族的期望必须照旧通过。

## 1. 子查询是嵌套的查询，不是一对括号

现状：`_subqueries` 对每个 `exp.Subquery`（也就是每一对包着东西的括号）记一次。于是集合运算的带括号操作数、整条语句外面的括号、INSERT 的带括号来源都被记成 `ast:subquery:scalar`；括号里是连接而不是查询的也被记成 `derived`；而没有括号包装的嵌套查询（`ARRAY(SELECT ...)`）反而漏掉。另外 `ANY` / `ALL` 的操作数不是查询时也被记成子查询。

改成：子查询是语句里每一个**嵌套的查询节点**（SELECT 或集合运算），但下面这些不算：顶层语句本身、集合运算的操作数、CTE 的主体、INSERT 与 CREATE TABLE AS 的来源查询。外面包几层括号不改变它是谁，也不产生新的子查询。每个子查询按它所处的位置恰好归为八种形式之一：EXISTS / IN / ALL / ANY 的操作数（按是否被否定），FROM 或 JOIN 里当表用的是 `derived`，其余当值用的都是 `scalar`。`ANY`、`ALL`、`IN` 的操作数不是查询时，不记任何子查询特征。位置（`ast:subquery_pos:*`）的规则不变。

- postgres：`(SELECT a FROM t) UNION ALL (SELECT b FROM u) ORDER BY 1` → 必须有 `ast:stmt:select`、`ast:set_op:union_all`、`ast:clause:order_by`；不许有 `ast:subquery:scalar`、`ast:subquery:derived`、`ast:subquery_pos:from`
- `INSERT INTO t (SELECT a FROM u)` → 必须有 `ast:stmt:insert`；不许有 `ast:subquery:scalar`、`ast:stmt:select`
- `(SELECT 1)` → 必须有 `ast:stmt:select`；不许有 `ast:subquery:scalar`
- postgres：`SELECT * FROM (a JOIN b ON a.x = b.x)` → 必须有 `ast:join:inner`、`ast:join_cond:on`；不许有 `ast:subquery:derived`、`ast:subquery_pos:from`
- `SELECT ARRAY(SELECT a FROM t)` → 必须有 `ast:subquery:scalar`、`ast:subquery_pos:select`；不许有 `ast:subquery:derived`
- postgres：`SELECT a FROM t WHERE a = ANY (ARRAY[1, 2])` → 必须有 `ast:clause:where`、`ast:cmp:eq`；不许有 `ast:subquery:any`、`ast:subquery_pos:where`。`SELECT a FROM t WHERE a = ANY ([1, 2])`（duckdb）同样
- `SELECT a FROM t WHERE a IN ((SELECT max(b) FROM u))` → 这一个嵌套查询只记一种形式（`in` 或 `scalar` 二选一都可以，但不能两个都有）

## 2. 命名窗口

现状：`sum(a) OVER w ... WINDOW w AS (...)` 里，引用处被记成 `ast:window_spec:empty`，`WINDOW` 子句里的定义被当成又一次窗口调用（多出 `ast:window_trait:multiple` 和 `ast:window_fn:other`）。

改成：窗口调用只数"函数 + OVER"；`WINDOW` 子句里的定义不是调用。引用命名窗口的调用，它的规格取定义里写的（分区、排序、帧、重复的分区键），再并上引用处自己写的（`OVER (w ROWS ...)`）。`ast:window_spec:empty` 只用于字面的 `OVER ()`。名字找不到定义：不输出规格特征。

- `SELECT sum(a) OVER w FROM t WINDOW w AS (PARTITION BY b ORDER BY a)` → 必须有 `ast:window_fn:aggregate`、`ast:window_spec:partition`、`ast:window_spec:order`；不许有 `ast:window_spec:empty`、`ast:window_trait:multiple`、`ast:window_fn:other`、`ast:agg:sum`、`ast:clause:order_by`
- `SELECT rank() OVER w, sum(a) OVER w FROM t WINDOW w AS (ORDER BY a)` → 必须有 `ast:window_fn:ranking`、`ast:window_fn:aggregate`、`ast:window_spec:order`、`ast:window_trait:multiple`；不许有 `ast:window_spec:empty`、`ast:window_spec:partition`、`ast:window_fn:other`
- `SELECT rank() OVER (w ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) FROM t WINDOW w AS (PARTITION BY b ORDER BY a)` → 必须有 `ast:window_fn:ranking`、`ast:window_spec:partition`、`ast:window_spec:order`、`ast:window_spec:frame`、`ast:window_frame:rows`、`ast:window_frame:preceding`；不许有 `ast:window_spec:empty`、`ast:window_trait:multiple`、`ast:window_fn:other`
- `SELECT sum(a) OVER w FROM t WINDOW w AS (PARTITION BY b, b)` → 必须有 `ast:window_trait:dup_partition_key`

## 3. IGNORE NULLS / RESPECT NULLS

现状：sqlglot 在函数外面包了一层 `IgnoreNulls` / `RespectNulls`，于是被窗口化的函数认不出来（归成 `ast:window_fn:other`），里面那个函数又被当成不带 OVER 的聚合记了 `ast:agg:other`。语料里有 16 条这样的语句。

改成：判断"被窗口化的是哪个函数"和"这个聚合带不带 OVER"时穿过这两种包装，和现在穿过 `Filter` 一样。

- `SELECT first_value(a) IGNORE NULLS OVER (ORDER BY b), lag(a) RESPECT NULLS OVER (ORDER BY b) FROM t` → 必须有 `ast:window_fn:navigation`、`ast:window_spec:order`、`ast:window_trait:multiple`；不许有 `ast:agg:other`、`ast:window_fn:aggregate`、`ast:window_fn:other`
- `SELECT first(a IGNORE NULLS) OVER (ORDER BY b) FROM t` → 必须有 `ast:window_fn:aggregate`；不许有 `ast:agg:other`、`ast:window_fn:other`

## 4. UPDATE、DELETE、MERGE 里的相关子查询

现状：`build_scope` 对不是查询的根返回 `None`，`_correlation` 直接返回，所以写语句里的相关子查询既没有 `ast:subquery_trait:correlated` 也没有 `ast:corr_cmp:*`。

改成：UPDATE / DELETE / MERGE 里的子查询，外层是这条语句自己的关系：目标表，加上 UPDATE 的 FROM、DELETE 的 USING、MERGE 的 USING 源，按表名或别名认。（提示：对子查询自己调 `build_scope`，根作用域的 `external_columns` 同样可用。）INSERT ... SELECT 与 CREATE TABLE AS 的来源查询是它自己的顶层，目标表不是它的外层，这一点现状是对的，保持。

- `DELETE FROM t WHERE NOT EXISTS (SELECT 1 FROM u WHERE u.k = t.k)` → 必须有 `ast:stmt:delete`、`ast:subquery:not_exists`、`ast:subquery_pos:where`、`ast:subquery_trait:correlated`、`ast:corr_cmp:eq`；不许有 `ast:subquery:exists`、`ast:stmt:select`
- `DELETE FROM t x WHERE EXISTS (SELECT 1 FROM u WHERE u.k >= x.k)` → 必须有 `ast:subquery_trait:correlated`、`ast:corr_cmp:ge`
- `UPDATE t SET a = (SELECT max(v) FROM u WHERE u.k <> t.k) WHERE b > 2` → 必须有 `ast:stmt:update`、`ast:subquery:scalar`、`ast:subquery_trait:correlated`、`ast:corr_cmp:neq`、`ast:cmp:neq`、`ast:cmp:gt`；不许有 `ast:cmp:eq`、`ast:corr_cmp:eq`、`ast:subquery_pos:where`
- `MERGE INTO t USING u ON t.k = u.k WHEN MATCHED AND EXISTS (SELECT 1 FROM w WHERE w.k < t.k) THEN UPDATE SET v = u.v` → 必须有 `ast:stmt:merge`、`ast:merge:matched`、`ast:merge:update`、`ast:subquery:exists`、`ast:subquery_trait:correlated`、`ast:corr_cmp:lt`、`ast:cmp:eq`、`ast:cmp:lt`；不许有 `ast:corr_cmp:eq`
- `INSERT INTO t SELECT a FROM u WHERE EXISTS (SELECT 1 FROM w WHERE w.k = t.k)` → 不许有 `ast:subquery_trait:correlated`、`ast:corr_cmp:eq`（现状如此，保持）
- `DELETE FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.k > 0)` → 不许有 `ast:subquery_trait:correlated`

## 5. 赋值不是比较

现状：sqlglot 把赋值表示成 `EQ`，于是 `UPDATE t SET a = 1`、MERGE 的 `UPDATE SET v = u.v`、`SET threads = 1` 都输出 `ast:cmp:eq`。

改成：UPDATE（含 MERGE 里的 UPDATE）的 SET 列表里每一项的那个顶层 `=`、SET 与 PRAGMA 语句的 `=`，不记 `ast:cmp:eq`。赋值右边的表达式里面出现的比较照记。

- `UPDATE t SET a = 1 WHERE b > 2` → 必须有 `ast:cmp:gt`；不许有 `ast:cmp:eq`
- `UPDATE t SET a = 1 WHERE b = 2` → 必须有 `ast:cmp:eq`
- `MERGE INTO t USING u ON t.k < u.k WHEN MATCHED THEN UPDATE SET v = u.v` → 必须有 `ast:cmp:lt`；不许有 `ast:cmp:eq`
- `SET threads = 1` → 不许有 `ast:cmp:eq`

## 6. 子查询自己定义的名字是本层的

现状：`ast:corr_cmp:*` 判"一边本层、一边外层"时，一个名字在本层和外层都有的话两头都算，于是 `SELECT a FROM t WHERE EXISTS (SELECT 1 FROM t WHERE t.k = t.j)` 记了 `ast:corr_cmp:eq`（`correlated` 没记，那是对的）。

改成：一边算外层的列，要求它的限定名不是本层的源。

- `SELECT a FROM t WHERE EXISTS (SELECT 1 FROM t WHERE t.k = t.j)` → 必须有 `ast:subquery:exists`、`ast:cmp:eq`、`ast:join_trait:self`；不许有 `ast:corr_cmp:eq`、`ast:subquery_trait:correlated`

## 7. 兜底

说明里要求兜底诚实：认不准的不输出。有两处误报，另补一个能认准的。这三条的状态都必须是 `fallback`。

- 帧里的 BETWEEN 不是谓词：`SELECT {agg}(id) OVER (ORDER BY id ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) FROM t1` → 不许有 `ast:pred:between`、`ast:clause:order_by`、`ast:window_spec:empty`。判 BETWEEN 之前先去掉 OVER 的括号体。
- 不是每个 WITH 都是 CTE：postgres 的 `SELECT * FROM J1_TBL JOIN J2_TBL USING (i) AS x ORDER BY 1 FETCH FIRST 1 ROW WITH TIES` → 不许有 `ast:cte:plain`、`ast:cte:recursive`。只在出现 `WITH [RECURSIVE] 名字 [(列名表)] AS [[NOT] MATERIALIZED] (` 这个形状时才认 CTE。
- 语句种类：文本只有一条语句（去掉注释和字符串之后，分号后面没有别的内容）并且第一个词是 SELECT、INSERT、UPDATE、DELETE、MERGE 之一时，输出对应的 `ast:stmt:*`；以 WITH 或括号开头的不猜，有两条语句的不猜。
  - `SELECT id, {agg}(id) OVER (PARTITION BY ch ORDER BY id ROWS BETWEEN 1 FOLLOWING AND 2 FOLLOWING) FROM t1 ORDER BY 1` → 必须有 `ast:stmt:select`
  - postgres：`SELECT * FROM J1_TBL JOIN J2_TBL USING (i) AS x WHERE J1_TBL.t = 'one'` → 必须有 `ast:stmt:select`
  - `SELECT 1; DELETE FROM t` → 不许有 `ast:stmt:select`、`ast:stmt:delete`

## 测试

上面每一条例子在 `framework/tests/test_surprise_s05_ast*.py` 里都要有断言（必须有的和不许有的都断言）。已有的测试不许删、不许放宽；如果某条已有测试的期望与上面的规则冲突，写进报告的"未决问题"，停下。

## 验收

在 worktree 里，`python` 与 `pytest` 用现成的：

```powershell
cd framework
python -m pytest -q testing tests                          # 0 failed，不少于 316 passed，skip 不多于 3
python -m surprise.gates.s01
python -m surprise.gates.s02
python -m surprise.gates.s03
python -m surprise.gates.s04
python -m surprise.gates.s05 --only vocab spec units ast
```

都是退出码 0。范围、禁区、报告格式仍以 `.orch/brief.md` 为准：只改 `features/ast.py` 与你的测试文件（`vocabulary.py` 仍只许追加），不改门槛，不执行 SQL，不按 SQL 文本硬编码结果（特征只来自语法结构）。`.orch/tmp` 里的文件不要删。改完提交到当前分支，更新 `.orch/report.md`（保留第一轮内容，在后面加"第 1 轮返工"一节）。
