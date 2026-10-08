"""Contract data for the S5 gate (data only; ``gates/all.py`` does not run this file).

``CORE_VOCAB`` is the base vocabulary of phi that the gate depends on: ids,
kinds and parents are fixed here, the feature package reproduces them and may
add more. The probe tables say what each feature means by example. Plan
operators and corpus figures were measured on DuckDB 1.5.5, DataFusion 54.0.0
and sqlglot 30.21.0 before any feature code existed.

Feature ids are ``<layer>:<name>[:<value>]`` with layer ``ast``, ``plan`` or
``data``. Kinds: ``class`` (an inner node of the hierarchy, never emitted by
extraction), ``leaf`` (emitted), ``family`` (a class whose leaves are open:
any ``<family id>:<token>`` is a leaf of it).
"""
from __future__ import annotations

# id -> (kind, parent, meaning)
CORE_VOCAB: dict[str, tuple[str, str | None, str]] = {
    "ast": ("class", None, "what the statement text says"),
    "plan": ("family", None, "physical operators of the target engine's plan, named as the engine prints them"),
    "data": ("class", None, "properties of the data the statement runs on, computed on the database"),

    # ---- statement
    "ast:stmt": ("class", "ast", "kind of the top-level statement"),
    "ast:stmt:select": ("leaf", "ast:stmt", "a query, including a set operation of queries"),
    "ast:stmt:merge": ("leaf", "ast:stmt", "MERGE"),
    "ast:stmt:insert": ("leaf", "ast:stmt", "INSERT"),
    "ast:stmt:update": ("leaf", "ast:stmt", "UPDATE"),
    "ast:stmt:delete": ("leaf", "ast:stmt", "DELETE"),

    # ---- set operations, anywhere in the statement
    "ast:set_op": ("class", "ast", "a set operation"),
    "ast:set_op:all": ("class", "ast:set_op", "bag semantics: the ALL variants"),
    "ast:set_op:union_all": ("leaf", "ast:set_op:all", "UNION ALL"),
    "ast:set_op:except_all": ("leaf", "ast:set_op:all", "EXCEPT ALL"),
    "ast:set_op:intersect_all": ("leaf", "ast:set_op:all", "INTERSECT ALL"),
    "ast:set_op:distinct": ("class", "ast:set_op", "set semantics"),
    "ast:set_op:union": ("leaf", "ast:set_op:distinct", "UNION without ALL"),
    "ast:set_op:except": ("leaf", "ast:set_op:distinct", "EXCEPT without ALL"),
    "ast:set_op:intersect": ("leaf", "ast:set_op:distinct", "INTERSECT without ALL"),

    # ---- joins
    "ast:join": ("class", "ast", "a join between two relations"),
    "ast:join:inner": ("leaf", "ast:join", "JOIN / INNER JOIN with a condition, and NATURAL JOIN"),
    "ast:join:left": ("leaf", "ast:join", "LEFT [OUTER] JOIN"),
    "ast:join:right": ("leaf", "ast:join", "RIGHT [OUTER] JOIN"),
    "ast:join:full": ("leaf", "ast:join", "FULL [OUTER] JOIN"),
    "ast:join:cross": ("leaf", "ast:join", "CROSS JOIN, or two relations separated by a comma"),
    "ast:join:asof": ("leaf", "ast:join", "ASOF JOIN (with its side as well, when one is written)"),
    "ast:join_cond": ("class", "ast", "how a join states its condition"),
    "ast:join_cond:on": ("leaf", "ast:join_cond", "ON"),
    "ast:join_cond:using": ("leaf", "ast:join_cond", "USING"),
    "ast:join_cond:natural": ("leaf", "ast:join_cond", "NATURAL"),
    "ast:join_trait": ("class", "ast", "properties of the joined relations"),
    "ast:join_trait:self": ("leaf", "ast:join_trait", "the same base table is referenced two or more times in the statement"),
    "ast:join_trait:non_equi": ("leaf", "ast:join_trait", "a join ON condition compares with <, <=, >, >= or <>"),
    "ast:join_trait:lateral": ("leaf", "ast:join_trait", "the LATERAL keyword"),

    # ---- subqueries
    "ast:subquery": ("class", "ast", "a nested query"),
    "ast:subquery:exists": ("leaf", "ast:subquery", "EXISTS (...) that is not negated"),
    "ast:subquery:not_exists": ("leaf", "ast:subquery", "NOT EXISTS (...)"),
    "ast:subquery:in": ("leaf", "ast:subquery", "expr IN (SELECT ...) that is not negated"),
    "ast:subquery:not_in": ("leaf", "ast:subquery", "expr NOT IN (SELECT ...)"),
    "ast:subquery:scalar": ("leaf", "ast:subquery", "a parenthesised query used as a value"),
    "ast:subquery:all": ("leaf", "ast:subquery", "comparison with ALL (SELECT ...)"),
    "ast:subquery:any": ("leaf", "ast:subquery", "comparison with ANY or SOME (SELECT ...)"),
    "ast:subquery:derived": ("leaf", "ast:subquery", "a query in FROM or JOIN used as a table"),
    "ast:subquery_pos": ("class", "ast", "the clause of the enclosing query that holds a subquery"),
    "ast:subquery_pos:select": ("leaf", "ast:subquery_pos", "the select list"),
    "ast:subquery_pos:where": ("leaf", "ast:subquery_pos", "WHERE"),
    "ast:subquery_pos:from": ("leaf", "ast:subquery_pos", "FROM or a joined relation"),
    "ast:subquery_pos:having": ("leaf", "ast:subquery_pos", "HAVING"),
    "ast:subquery_pos:on": ("leaf", "ast:subquery_pos", "a join ON condition"),
    "ast:subquery_trait": ("class", "ast", "properties of a subquery"),
    "ast:subquery_trait:correlated": ("leaf", "ast:subquery_trait", "it references a qualified column of an enclosing query"),
    "ast:corr_cmp": ("class", "ast", "comparison, inside a correlated subquery, between an inner column and an outer column"),
    "ast:corr_cmp:eq": ("leaf", "ast:corr_cmp", "="),
    "ast:corr_cmp:neq": ("leaf", "ast:corr_cmp", "<> or !="),
    "ast:corr_cmp:lt": ("leaf", "ast:corr_cmp", "< as written"),
    "ast:corr_cmp:le": ("leaf", "ast:corr_cmp", "<= as written"),
    "ast:corr_cmp:gt": ("leaf", "ast:corr_cmp", "> as written"),
    "ast:corr_cmp:ge": ("leaf", "ast:corr_cmp", ">= as written"),

    # ---- aggregation (aggregate calls that are not window functions)
    "ast:agg": ("class", "ast", "an aggregate function call without OVER"),
    "ast:agg:count": ("leaf", "ast:agg", "COUNT"),
    "ast:agg:sum": ("leaf", "ast:agg", "SUM"),
    "ast:agg:avg": ("leaf", "ast:agg", "AVG"),
    "ast:agg:min": ("leaf", "ast:agg", "MIN"),
    "ast:agg:max": ("leaf", "ast:agg", "MAX"),
    "ast:agg:other": ("leaf", "ast:agg", "any other aggregate"),
    "ast:agg_trait": ("class", "ast", "how an aggregate is called"),
    "ast:agg_trait:star": ("leaf", "ast:agg_trait", "COUNT(*)"),
    "ast:agg_trait:distinct": ("leaf", "ast:agg_trait", "DISTINCT inside the call"),
    "ast:agg_trait:filter": ("leaf", "ast:agg_trait", "FILTER (WHERE ...)"),
    "ast:agg_trait:ordered": ("leaf", "ast:agg_trait", "ORDER BY inside the call"),
    "ast:group": ("class", "ast", "grouping clauses"),
    "ast:group:by": ("leaf", "ast:group", "GROUP BY"),
    "ast:group:having": ("leaf", "ast:group", "HAVING"),
    "ast:group:rollup": ("leaf", "ast:group", "ROLLUP"),
    "ast:group:cube": ("leaf", "ast:group", "CUBE"),
    "ast:group:grouping_sets": ("leaf", "ast:group", "GROUPING SETS"),

    # ---- window functions
    "ast:window": ("class", "ast", "a function call with OVER"),
    "ast:window_fn": ("class", "ast:window", "which kind of function is windowed"),
    "ast:window_fn:ranking": ("leaf", "ast:window_fn", "row_number, rank, dense_rank, ntile, percent_rank, cume_dist"),
    "ast:window_fn:navigation": ("leaf", "ast:window_fn", "lag, lead, first_value, last_value, nth_value"),
    "ast:window_fn:aggregate": ("leaf", "ast:window_fn", "an aggregate function with OVER"),
    "ast:window_spec": ("class", "ast:window", "what the OVER clause contains"),
    "ast:window_spec:partition": ("leaf", "ast:window_spec", "PARTITION BY"),
    "ast:window_spec:order": ("leaf", "ast:window_spec", "ORDER BY inside OVER"),
    "ast:window_spec:frame": ("leaf", "ast:window_spec", "an explicit frame"),
    "ast:window_spec:empty": ("leaf", "ast:window_spec", "OVER ()"),
    "ast:window_frame": ("class", "ast:window", "shape of an explicit frame"),
    "ast:window_frame:rows": ("leaf", "ast:window_frame", "ROWS"),
    "ast:window_frame:range": ("leaf", "ast:window_frame", "RANGE"),
    "ast:window_frame:groups": ("leaf", "ast:window_frame", "GROUPS"),
    "ast:window_frame:preceding": ("leaf", "ast:window_frame", "a PRECEDING bound, UNBOUNDED included"),
    "ast:window_frame:following": ("leaf", "ast:window_frame", "a FOLLOWING bound, UNBOUNDED included"),
    "ast:window_trait": ("class", "ast:window", "other properties of window calls"),
    "ast:window_trait:dup_partition_key": ("leaf", "ast:window_trait", "one PARTITION BY list names the same expression twice"),
    "ast:window_trait:multiple": ("leaf", "ast:window_trait", "two or more window calls in the statement"),
    "ast:window_trait:ordered_arg": ("leaf", "ast:window_trait", "ORDER BY inside the argument list of the windowed function"),

    # ---- clauses of a query (anywhere in the statement, subqueries and CTEs included)
    "ast:clause": ("class", "ast", "clauses of a query"),
    "ast:clause:where": ("leaf", "ast:clause", "WHERE"),
    "ast:clause:distinct": ("leaf", "ast:clause", "SELECT DISTINCT"),
    "ast:clause:order_by": ("leaf", "ast:clause", "ORDER BY of a query (not of OVER, not of an aggregate call)"),
    "ast:clause:limit": ("leaf", "ast:clause", "LIMIT"),
    "ast:clause:offset": ("leaf", "ast:clause", "OFFSET"),
    "ast:clause:qualify": ("leaf", "ast:clause", "QUALIFY"),
    "ast:cte": ("class", "ast", "WITH"),
    "ast:cte:plain": ("leaf", "ast:cte", "WITH without RECURSIVE"),
    "ast:cte:recursive": ("leaf", "ast:cte", "WITH RECURSIVE"),

    # ---- predicates and expressions, anywhere in the statement
    "ast:cmp": ("class", "ast", "comparison operators"),
    "ast:cmp:eq": ("leaf", "ast:cmp", "="),
    "ast:cmp:neq": ("leaf", "ast:cmp", "<> or !="),
    "ast:cmp:lt": ("leaf", "ast:cmp", "<"),
    "ast:cmp:le": ("leaf", "ast:cmp", "<="),
    "ast:cmp:gt": ("leaf", "ast:cmp", ">"),
    "ast:cmp:ge": ("leaf", "ast:cmp", ">="),
    "ast:pred": ("class", "ast", "other predicates"),
    "ast:pred:is_null": ("leaf", "ast:pred", "IS NULL"),
    "ast:pred:is_not_null": ("leaf", "ast:pred", "IS NOT NULL"),
    "ast:pred:between": ("leaf", "ast:pred", "BETWEEN"),
    "ast:pred:like": ("leaf", "ast:pred", "LIKE or ILIKE"),
    "ast:pred:in_list": ("leaf", "ast:pred", "IN with a list of values"),
    "ast:bool": ("class", "ast", "boolean connectives"),
    "ast:bool:and": ("leaf", "ast:bool", "AND"),
    "ast:bool:or": ("leaf", "ast:bool", "OR"),
    "ast:expr": ("class", "ast", "expression forms"),
    "ast:expr:case": ("leaf", "ast:expr", "CASE"),
    "ast:expr:coalesce": ("leaf", "ast:expr", "COALESCE"),
    "ast:expr:nullif": ("leaf", "ast:expr", "NULLIF"),
    "ast:expr:cast": ("leaf", "ast:expr", "CAST, TRY_CAST or ::"),
    "ast:expr:arith": ("leaf", "ast:expr", "binary +, -, *, / or %"),
    "ast:expr:concat": ("leaf", "ast:expr", "|| or CONCAT"),
    "ast:expr:collate": ("leaf", "ast:expr", "COLLATE"),
    "ast:expr:interval": ("leaf", "ast:expr", "an INTERVAL literal"),
    "ast:expr:date_arith": ("leaf", "ast:expr", "+ or - with an INTERVAL literal as one operand"),
    "ast:fn": ("family", "ast", "scalar function calls: ast:fn:<name>, the lower-cased sqlglot name of the function"),
    "ast:merge": ("class", "ast", "clauses of MERGE"),
    "ast:merge:matched": ("leaf", "ast:merge", "WHEN MATCHED"),
    "ast:merge:not_matched": ("leaf", "ast:merge", "WHEN NOT MATCHED [BY TARGET]"),
    "ast:merge:not_matched_by_source": ("leaf", "ast:merge", "WHEN NOT MATCHED BY SOURCE"),
    "ast:merge:update": ("leaf", "ast:merge", "THEN UPDATE"),
    "ast:merge:delete": ("leaf", "ast:merge", "THEN DELETE"),
    "ast:merge:insert": ("leaf", "ast:merge", "THEN INSERT"),
    "ast:parse": ("class", "ast", "how the text was read"),
    "ast:parse:fallback": ("leaf", "ast:parse", "sqlglot could not parse it; the ast features come from regular expressions"),

    # ---- data: every base table the statement references
    "data:table": ("class", "data", "shape of the referenced base tables"),
    "data:table:empty": ("leaf", "data:table", "some referenced table has no rows"),
    "data:table:single_row": ("leaf", "data:table", "some referenced table has exactly one row"),
    "data:table:dup_rows": ("leaf", "data:table", "some referenced table holds two identical rows"),
    "data:table:has_null": ("leaf", "data:table", "some referenced table holds a NULL"),
    "data:value": ("class", "data", "corner-case values in the referenced tables"),
    "data:value:zero": ("leaf", "data:value", "a numeric zero"),
    "data:value:negative": ("leaf", "data:value", "a negative number"),
    "data:value:extreme_number": ("leaf", "data:value", "a number whose absolute value is at least 2**31"),
    "data:value:empty_string": ("leaf", "data:value", "an empty string"),
    "data:value:non_finite": ("leaf", "data:value", "NaN or an infinity"),
    "data:type": ("class", "data", "column types of the referenced tables"),
    "data:type:integer": ("leaf", "data:type", "an integer type"),
    "data:type:float": ("leaf", "data:type", "REAL, FLOAT or DOUBLE"),
    "data:type:decimal": ("leaf", "data:type", "DECIMAL or NUMERIC"),
    "data:type:string": ("leaf", "data:type", "a character type"),
    "data:type:boolean": ("leaf", "data:type", "BOOLEAN"),
    "data:type:date": ("leaf", "data:type", "DATE"),
    "data:type:timestamp": ("leaf", "data:type", "TIMESTAMP, with or without time zone"),
    "data:type:other": ("leaf", "data:type", "anything else"),
    # ---- data: the operands of a set operation, evaluated as queries
    "data:setop": ("class", "data", "the two inputs of a set operation, computed by running each input"),
    "data:setop:left_has_dups": ("leaf", "data:setop", "the left input returns two identical rows"),
    "data:setop:right_has_dups": ("leaf", "data:setop", "the right input returns two identical rows"),
    "data:setop:left_has_null": ("leaf", "data:setop", "the left input returns a NULL"),
    "data:setop:right_has_null": ("leaf", "data:setop", "the right input returns a NULL"),
}

# sibling sets the generalisation lane relies on ("swap for a value of the same class")
SIBLINGS = {
    "ast:set_op:except_all": ("ast:set_op:intersect_all", "ast:set_op:union_all"),
    "ast:set_op:union": ("ast:set_op:except", "ast:set_op:intersect"),
    "ast:subquery:not_exists": ("ast:subquery:all", "ast:subquery:any", "ast:subquery:derived", "ast:subquery:exists",
                                "ast:subquery:in", "ast:subquery:not_in", "ast:subquery:scalar"),
    "data:setop:left_has_dups": ("data:setop:left_has_null", "data:setop:right_has_dups", "data:setop:right_has_null"),
}
ANCESTORS = {
    "ast:set_op:except_all": ("ast:set_op:all", "ast:set_op", "ast"),
    "ast:window_trait:dup_partition_key": ("ast:window_trait", "ast:window", "ast"),
    "data:setop:left_has_dups": ("data:setop", "data"),
    "plan:HASH_JOIN": ("plan",),
    "ast:fn:upper": ("ast:fn", "ast"),
}

# ---- AST probes: (engine, sql, features it must have, features it must not have) -------------

T = "t"
AST_PROBES: list[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = [
    ("duckdb", "SELECT a FROM t",
     ("ast:stmt:select",),
     ("ast:clause:where", "ast:join:inner", "ast:join:cross", "ast:parse:fallback", "ast:cmp:eq", "ast:agg:count")),
    ("duckdb", "SELECT a, b FROM t WHERE a > 1 AND b <= 2 OR a <> 3",
     ("ast:clause:where", "ast:cmp:gt", "ast:cmp:le", "ast:cmp:neq", "ast:bool:and", "ast:bool:or"),
     ("ast:cmp:eq", "ast:cmp:lt", "ast:cmp:ge")),
    ("duckdb", "SELECT a FROM t WHERE a != 3 AND a >= 1 AND a < 9 AND a = b",
     ("ast:cmp:neq", "ast:cmp:ge", "ast:cmp:lt", "ast:cmp:eq"), ("ast:cmp:gt", "ast:cmp:le", "ast:bool:or")),
    # set operations
    ("duckdb", "SELECT v FROM t EXCEPT ALL SELECT v FROM u",
     ("ast:set_op:except_all", "ast:stmt:select"), ("ast:set_op:except", "ast:set_op:intersect_all", "ast:set_op:union_all")),
    ("datafusion", "SELECT v FROM t INTERSECT ALL SELECT v FROM u",
     ("ast:set_op:intersect_all",), ("ast:set_op:intersect", "ast:set_op:except_all")),
    ("duckdb", "SELECT v FROM t UNION SELECT v FROM u",
     ("ast:set_op:union",), ("ast:set_op:union_all",)),
    ("duckdb", "SELECT v FROM t UNION ALL SELECT v FROM u EXCEPT SELECT v FROM w",
     ("ast:set_op:union_all", "ast:set_op:except"), ("ast:set_op:union", "ast:set_op:except_all")),
    ("duckdb", "SELECT v FROM t INTERSECT SELECT v FROM u",
     ("ast:set_op:intersect",), ("ast:set_op:intersect_all",)),
    ("duckdb", "SELECT * FROM (SELECT v FROM t EXCEPT ALL SELECT v FROM u) s WHERE v > 0",
     ("ast:set_op:except_all", "ast:subquery:derived", "ast:subquery_pos:from"), ("ast:subquery:scalar",)),
    # joins
    ("duckdb", "SELECT * FROM a JOIN b ON a.x = b.x",
     ("ast:join:inner", "ast:join_cond:on"), ("ast:join:left", "ast:join:cross", "ast:join_cond:using", "ast:join_trait:non_equi",
                                              "ast:join_trait:self")),
    ("duckdb", "SELECT * FROM a LEFT JOIN b USING (x)",
     ("ast:join:left", "ast:join_cond:using"), ("ast:join:inner", "ast:join_cond:on")),
    ("duckdb", "SELECT * FROM a RIGHT OUTER JOIN b ON a.x = b.x FULL JOIN c ON b.x = c.x",
     ("ast:join:right", "ast:join:full"), ("ast:join:left", "ast:join:inner")),
    ("duckdb", "SELECT * FROM a CROSS JOIN b", ("ast:join:cross",), ("ast:join:inner", "ast:join_cond:on")),
    ("duckdb", "SELECT * FROM a, b WHERE a.x = b.x", ("ast:join:cross", "ast:clause:where"), ("ast:join:inner",)),
    ("duckdb", "SELECT * FROM a NATURAL JOIN b", ("ast:join:inner", "ast:join_cond:natural"), ("ast:join_cond:on", "ast:join:cross")),
    ("duckdb", "SELECT px.p FROM ev ASOF JOIN px ON ev.id = px.id AND ev.ts >= px.ts",
     ("ast:join:asof", "ast:join_cond:on", "ast:join_trait:non_equi"), ("ast:join:left", "ast:join:cross")),
    ("duckdb", "SELECT * FROM a ASOF LEFT JOIN b ON a.x = b.x AND a.t >= b.t",
     ("ast:join:asof", "ast:join:left", "ast:join_trait:non_equi"), ("ast:join:inner",)),
    ("duckdb", "SELECT * FROM t x JOIN t y ON x.a = y.b",
     ("ast:join_trait:self", "ast:join:inner"), ("ast:join_trait:non_equi",)),
    ("duckdb", "SELECT * FROM a JOIN LATERAL (SELECT * FROM b WHERE b.x = a.x) s ON true",
     ("ast:join_trait:lateral", "ast:subquery:derived"), ()),
    # subqueries
    ("duckdb", "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.b = t.a)",
     ("ast:subquery:exists", "ast:subquery_pos:where", "ast:subquery_trait:correlated", "ast:corr_cmp:eq"),
     ("ast:subquery:not_exists", "ast:subquery_pos:select", "ast:corr_cmp:neq")),
    ("duckdb", "SELECT a FROM t WHERE NOT EXISTS (SELECT 1 FROM u WHERE u.b <> t.a AND u.c > 5)",
     ("ast:subquery:not_exists", "ast:subquery_trait:correlated", "ast:corr_cmp:neq", "ast:cmp:gt"),
     ("ast:subquery:exists", "ast:corr_cmp:eq", "ast:corr_cmp:gt")),
    ("duckdb", "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.b > 0)",
     ("ast:subquery:exists",), ("ast:subquery_trait:correlated", "ast:corr_cmp:gt")),
    ("duckdb", "SELECT a FROM t WHERE a IN (SELECT b FROM u)",
     ("ast:subquery:in", "ast:subquery_pos:where"), ("ast:subquery:not_in", "ast:pred:in_list", "ast:subquery_trait:correlated")),
    ("duckdb", "SELECT a FROM t WHERE a NOT IN (SELECT b FROM u)",
     ("ast:subquery:not_in",), ("ast:subquery:in", "ast:pred:in_list")),
    ("duckdb", "SELECT a FROM t WHERE a IN (1, 2, 3)", ("ast:pred:in_list",), ("ast:subquery:in",)),
    ("duckdb", "SELECT a, (SELECT max(b) FROM u WHERE u.k = t.k) FROM t",
     ("ast:subquery:scalar", "ast:subquery_pos:select", "ast:subquery_trait:correlated", "ast:corr_cmp:eq", "ast:agg:max"),
     ("ast:subquery_pos:where", "ast:subquery:exists")),
    ("datafusion", "SELECT a FROM t WHERE b > ALL (SELECT w FROM u)",
     ("ast:subquery:all", "ast:subquery_pos:where"), ("ast:subquery:any", "ast:subquery:scalar")),
    ("duckdb", "SELECT a FROM t WHERE b = ANY (SELECT w FROM u)", ("ast:subquery:any",), ("ast:subquery:all",)),
    ("duckdb", "SELECT k FROM t GROUP BY k HAVING sum(a) > (SELECT avg(a) FROM t)",
     ("ast:subquery:scalar", "ast:subquery_pos:having", "ast:group:by", "ast:group:having", "ast:agg:sum", "ast:agg:avg",
      "ast:join_trait:self"), ("ast:subquery_pos:where",)),
    ("duckdb", "SELECT * FROM a JOIN b ON a.x = (SELECT max(x) FROM c)",
     ("ast:subquery:scalar", "ast:subquery_pos:on"), ("ast:subquery_pos:where",)),
    ("duckdb", "SELECT o1.x FROM o o1 WHERE NOT EXISTS (SELECT 1 FROM o o2 WHERE o2.k = o1.k AND o2.id <> o1.id AND o2.v > o1.v)",
     ("ast:subquery:not_exists", "ast:corr_cmp:eq", "ast:corr_cmp:neq", "ast:corr_cmp:gt", "ast:join_trait:self"),
     ("ast:corr_cmp:lt", "ast:join:inner")),
    # aggregation
    ("duckdb", "SELECT count(*), count(DISTINCT a), min(a) FROM t",
     ("ast:agg:count", "ast:agg_trait:star", "ast:agg_trait:distinct", "ast:agg:min"),
     ("ast:group:by", "ast:clause:distinct", "ast:window_fn:aggregate", "ast:agg:sum")),
    ("duckdb", "SELECT k, string_agg(s, ',' ORDER BY a), count(*) FILTER (WHERE a > 1) FROM t GROUP BY k",
     ("ast:agg:other", "ast:agg_trait:ordered", "ast:agg_trait:filter", "ast:group:by", "ast:agg:count"),
     ("ast:clause:order_by", "ast:clause:where")),
    ("duckdb", "SELECT a, b FROM t GROUP BY ROLLUP (a, b)", ("ast:group:rollup",), ("ast:group:cube",)),
    ("duckdb", "SELECT a, b FROM t GROUP BY CUBE (a, b)", ("ast:group:cube",), ("ast:group:rollup",)),
    ("duckdb", "SELECT a, b FROM t GROUP BY GROUPING SETS ((a), (b))", ("ast:group:grouping_sets",), ("ast:group:rollup",)),
    # window functions
    ("duckdb", "SELECT sum(v) OVER (PARTITION BY a, a, b) AS x, sum(v) OVER (PARTITION BY a, a, a) AS y FROM src ORDER BY b",
     ("ast:window_fn:aggregate", "ast:window_spec:partition", "ast:window_trait:dup_partition_key", "ast:window_trait:multiple",
      "ast:clause:order_by"),
     ("ast:agg:sum", "ast:window_spec:order", "ast:window_spec:frame", "ast:window_spec:empty", "ast:group:by")),
    ("duckdb", "SELECT sum(v) OVER (PARTITION BY a, b) FROM src",
     ("ast:window_fn:aggregate", "ast:window_spec:partition"),
     ("ast:window_trait:dup_partition_key", "ast:window_trait:multiple", "ast:clause:order_by")),
    ("duckdb", "SELECT row_number() OVER (ORDER BY a), lag(a) OVER (ORDER BY a) FROM t",
     ("ast:window_fn:ranking", "ast:window_fn:navigation", "ast:window_spec:order", "ast:window_trait:multiple"),
     ("ast:window_fn:aggregate", "ast:clause:order_by", "ast:window_spec:partition")),
    ("duckdb", "SELECT count(*) OVER () FROM t",
     ("ast:window_fn:aggregate", "ast:window_spec:empty"), ("ast:window_spec:order", "ast:agg:count", "ast:agg_trait:star")),
    ("duckdb", "SELECT count(*) OVER (ORDER BY v ROWS BETWEEN 1 PRECEDING AND 5 PRECEDING) FROM t1",
     ("ast:window_spec:frame", "ast:window_frame:rows", "ast:window_frame:preceding", "ast:window_spec:order"),
     ("ast:window_frame:following", "ast:window_frame:range", "ast:window_trait:ordered_arg")),
    ("duckdb", "SELECT ntile(2 ORDER BY v) OVER (ORDER BY v ROWS BETWEEN 2 FOLLOWING AND 1 FOLLOWING) FROM t1",
     ("ast:window_fn:ranking", "ast:window_trait:ordered_arg", "ast:window_frame:rows", "ast:window_frame:following"),
     ("ast:window_frame:preceding", "ast:clause:order_by")),
    ("duckdb", "SELECT sum(a) OVER (ORDER BY a RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) FROM t",
     ("ast:window_frame:range", "ast:window_frame:preceding"), ("ast:window_frame:rows", "ast:window_frame:following")),
    ("duckdb", "SELECT a FROM t QUALIFY row_number() OVER (PARTITION BY b ORDER BY a) = 1",
     ("ast:clause:qualify", "ast:window_fn:ranking", "ast:cmp:eq"), ("ast:clause:where",)),
    # clauses and CTEs
    ("duckdb", "SELECT DISTINCT a FROM t ORDER BY a LIMIT 3 OFFSET 1",
     ("ast:clause:distinct", "ast:clause:order_by", "ast:clause:limit", "ast:clause:offset"), ("ast:agg_trait:distinct",)),
    ("duckdb", "WITH c AS (SELECT flag FROM p ORDER BY ord OFFSET 2) SELECT * FROM c INNER JOIN k ON flag = flag_key",
     ("ast:cte:plain", "ast:clause:offset", "ast:clause:order_by", "ast:join:inner", "ast:join_cond:on"),
     ("ast:cte:recursive", "ast:clause:limit", "ast:join_trait:non_equi")),
    ("datafusion", "WITH RECURSIVE r AS (SELECT 1 AS n UNION ALL SELECT n + 1 FROM r WHERE n < 5) SELECT count(*) FROM r",
     ("ast:cte:recursive", "ast:set_op:union_all", "ast:expr:arith", "ast:agg:count", "ast:agg_trait:star"),
     ("ast:cte:plain", "ast:set_op:union")),
    # predicates and expressions
    ("duckdb", "SELECT a FROM t WHERE a IS NULL OR b IS NOT NULL",
     ("ast:pred:is_null", "ast:pred:is_not_null", "ast:bool:or"), ("ast:bool:and",)),
    ("duckdb", "SELECT a FROM t WHERE a BETWEEN 1 AND 3 AND s LIKE 'x%'",
     ("ast:pred:between", "ast:pred:like", "ast:bool:and"), ("ast:cmp:ge", "ast:cmp:le")),
    ("duckdb", "SELECT CASE WHEN a > 0 THEN 'p' ELSE 'n' END, coalesce(b, 0), nullif(a, b) FROM t",
     ("ast:expr:case", "ast:expr:coalesce", "ast:expr:nullif", "ast:cmp:gt"), ("ast:expr:cast",)),
    ("duckdb", "SELECT CAST(a AS VARCHAR), b::INT, TRY_CAST(s AS DOUBLE) FROM t", ("ast:expr:cast",), ("ast:expr:case",)),
    ("duckdb", "SELECT a + 1, a * b, s || 'x' FROM t", ("ast:expr:arith", "ast:expr:concat"), ("ast:expr:date_arith",)),
    ("duckdb", "SELECT d + INTERVAL '1 month' AS a, d + INTERVAL '30 days' AS b FROM t ORDER BY d",
     ("ast:expr:interval", "ast:expr:date_arith", "ast:expr:arith", "ast:clause:order_by"), ("ast:expr:cast",)),
    ("duckdb", "SELECT s COLLATE NOCASE AS s_nc FROM a UNION SELECT s COLLATE NOCASE FROM b ORDER BY s_nc",
     ("ast:expr:collate", "ast:set_op:union", "ast:clause:order_by"), ("ast:set_op:union_all",)),
    ("duckdb", "SELECT upper(s), abs(a), my_func(a) FROM t", ("ast:fn:upper", "ast:fn:abs", "ast:fn:my_func"), ("ast:agg:other",)),
    # other statements
    ("duckdb", "MERGE INTO t USING s ON t.a = s.a WHEN NOT MATCHED BY SOURCE THEN DELETE",
     ("ast:stmt:merge", "ast:merge:not_matched_by_source", "ast:merge:delete"),
     ("ast:stmt:select", "ast:merge:matched", "ast:merge:not_matched", "ast:merge:insert", "ast:merge:update")),
    ("duckdb", "MERGE INTO t USING s ON t.a = s.a WHEN MATCHED THEN UPDATE SET b = s.b "
               "WHEN NOT MATCHED THEN INSERT VALUES (s.a, s.b)",
     ("ast:stmt:merge", "ast:merge:matched", "ast:merge:not_matched", "ast:merge:update", "ast:merge:insert"),
     ("ast:merge:not_matched_by_source", "ast:merge:delete")),
    ("duckdb", "DELETE FROM t WHERE a = 1 RETURNING a", ("ast:stmt:delete", "ast:clause:where"), ("ast:stmt:select",)),
    ("duckdb", "UPDATE t SET b = b + 1 WHERE a = 2", ("ast:stmt:update", "ast:expr:arith"), ("ast:stmt:select",)),
    ("duckdb", "INSERT INTO t VALUES (9, 90)", ("ast:stmt:insert",), ("ast:stmt:select",)),
    # counterexamples found in the review of s05-ast (first round)
    # a named window: the reference is not OVER (), the definition is not a second window call
    ("duckdb", "SELECT sum(a) OVER w FROM t WINDOW w AS (PARTITION BY b ORDER BY a)",
     ("ast:window_fn:aggregate", "ast:window_spec:partition", "ast:window_spec:order"),
     ("ast:window_spec:empty", "ast:window_trait:multiple", "ast:window_fn:other", "ast:agg:sum", "ast:clause:order_by")),
    ("duckdb", "SELECT rank() OVER w, sum(a) OVER w FROM t WINDOW w AS (ORDER BY a)",
     ("ast:window_fn:ranking", "ast:window_fn:aggregate", "ast:window_spec:order", "ast:window_trait:multiple"),
     ("ast:window_spec:empty", "ast:window_spec:partition", "ast:window_fn:other")),
    # IGNORE NULLS / RESPECT NULLS do not change which function is windowed
    ("duckdb", "SELECT first_value(a) IGNORE NULLS OVER (ORDER BY b), lag(a) RESPECT NULLS OVER (ORDER BY b) FROM t",
     ("ast:window_fn:navigation", "ast:window_spec:order", "ast:window_trait:multiple"),
     ("ast:agg:other", "ast:window_fn:aggregate", "ast:window_fn:other")),
    ("duckdb", "SELECT first(a IGNORE NULLS) OVER (ORDER BY b) FROM t", ("ast:window_fn:aggregate",),
     ("ast:agg:other", "ast:window_fn:other")),
    # a subquery is a nested query, not a pair of parentheses
    ("postgres", "(SELECT a FROM t) UNION ALL (SELECT b FROM u) ORDER BY 1",
     ("ast:stmt:select", "ast:set_op:union_all", "ast:clause:order_by"),
     ("ast:subquery:scalar", "ast:subquery:derived", "ast:subquery_pos:from")),
    ("duckdb", "INSERT INTO t (SELECT a FROM u)", ("ast:stmt:insert",), ("ast:subquery:scalar", "ast:stmt:select")),
    ("postgres", "SELECT * FROM (a JOIN b ON a.x = b.x)", ("ast:join:inner", "ast:join_cond:on"),
     ("ast:subquery:derived", "ast:subquery_pos:from")),
    ("duckdb", "SELECT ARRAY(SELECT a FROM t)", ("ast:subquery:scalar", "ast:subquery_pos:select"), ("ast:subquery:derived",)),
    ("postgres", "SELECT a FROM t WHERE a = ANY (ARRAY[1, 2])", ("ast:clause:where", "ast:cmp:eq"),
     ("ast:subquery:any", "ast:subquery_pos:where")),
    # correlation inside UPDATE, DELETE and MERGE: the statement's own relations are the outer query
    ("duckdb", "DELETE FROM t WHERE NOT EXISTS (SELECT 1 FROM u WHERE u.k = t.k)",
     ("ast:stmt:delete", "ast:subquery:not_exists", "ast:subquery_pos:where", "ast:subquery_trait:correlated", "ast:corr_cmp:eq"),
     ("ast:subquery:exists", "ast:stmt:select")),
    # ... and an assignment is not a comparison
    ("duckdb", "UPDATE t SET a = (SELECT max(v) FROM u WHERE u.k <> t.k) WHERE b > 2",
     ("ast:stmt:update", "ast:subquery:scalar", "ast:subquery_trait:correlated", "ast:corr_cmp:neq", "ast:cmp:neq", "ast:cmp:gt"),
     ("ast:cmp:eq", "ast:corr_cmp:eq", "ast:subquery_pos:where")),
    ("duckdb", "MERGE INTO t USING u ON t.k = u.k WHEN MATCHED AND EXISTS (SELECT 1 FROM w WHERE w.k < t.k) "
               "THEN UPDATE SET v = u.v",
     ("ast:stmt:merge", "ast:merge:matched", "ast:merge:update", "ast:subquery:exists", "ast:subquery_trait:correlated",
      "ast:corr_cmp:lt", "ast:cmp:eq", "ast:cmp:lt"), ("ast:corr_cmp:eq",)),
    ("duckdb", "SET threads = 1", (), ("ast:cmp:eq",)),
    # an alias the subquery defines itself is local, even when the outer query has the same one
    ("duckdb", "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM t WHERE t.k = t.j)",
     ("ast:subquery:exists", "ast:cmp:eq", "ast:join_trait:self"), ("ast:corr_cmp:eq", "ast:subquery_trait:correlated")),
]

# statements sqlglot 30.21.0 cannot parse (both are in seeds/corpus.json): regex fallback
FALLBACK_PROBES: list[tuple[str, str, tuple[str, ...]]] = [
    # (engine, sql, ids that must be in the closure of the features)
    ("duckdb", "SELECT id, {agg}(id) OVER (PARTITION BY ch ORDER BY id ROWS BETWEEN 1 FOLLOWING AND 2 FOLLOWING) FROM t1 ORDER BY 1",
     ("ast:parse:fallback", "ast:window", "ast:clause:order_by", "ast:stmt:select")),
    ("postgres", "SELECT * FROM J1_TBL JOIN J2_TBL USING (i) AS x WHERE J1_TBL.t = 'one'",
     ("ast:parse:fallback", "ast:join", "ast:clause:where", "ast:stmt:select")),
]
# the fallback is honest: (engine, sql, leaves it must not claim). Found in the review of s05-ast.
FALLBACK_LACK: list[tuple[str, str, tuple[str, ...]]] = [
    # BETWEEN and ORDER BY of a window frame are not a predicate and not the query's ORDER BY
    ("duckdb", "SELECT {agg}(id) OVER (ORDER BY id ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) FROM t1",
     ("ast:pred:between", "ast:clause:order_by", "ast:window_spec:empty")),
    # WITH that does not open a common table expression
    ("postgres", "SELECT * FROM J1_TBL JOIN J2_TBL USING (i) AS x ORDER BY 1 FETCH FIRST 1 ROW WITH TIES",
     ("ast:cte:plain", "ast:cte:recursive")),
    # two statements: the kind of "the" statement is not known
    ("duckdb", "SELECT 1; DELETE FROM t", ("ast:stmt:select", "ast:stmt:delete")),
]

# pairs that must give exactly the same ast features: names, case, layout and comments are not features
AST_INVARIANT: list[tuple[str, str]] = [
    ("SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.b = t.a)",
     "select x\n  from orders\n where exists (select 1 from items where items.y = orders.x) -- note\n;"),
    ("SELECT v FROM t EXCEPT ALL SELECT v FROM u", "SELECT col FROM left_tab /* bag */ EXCEPT ALL SELECT col FROM right_tab"),
    ("SELECT sum(v) OVER (PARTITION BY a, a, b) FROM src", "SELECT SUM(amount) OVER (PARTITION BY k1, k1, k2) FROM facts"),
]

# ---- the known families: gate cases of S4 (name in gates/s04_cases.py) and the ast features they must show ----

FAMILIES: dict[str, tuple[str, tuple[str, ...]]] = {
    # family -> (s04 case, core ast features of its minimal repro)
    "F1": ("F1", ("ast:subquery:exists", "ast:subquery_pos:select", "ast:subquery_trait:correlated", "ast:corr_cmp:eq",
                  "ast:corr_cmp:neq", "ast:join:left", "ast:join:inner", "ast:join_cond:using", "ast:clause:order_by")),
    "F2": ("F2", ("ast:window_fn:aggregate", "ast:window_spec:partition", "ast:window_trait:dup_partition_key",
                  "ast:window_trait:multiple", "ast:clause:order_by")),
    "F3": ("F3", ("ast:join:asof", "ast:join_trait:non_equi", "ast:clause:order_by")),
    "F5": ("F5", ("ast:cte:plain", "ast:clause:offset", "ast:clause:order_by", "ast:join:inner")),
    "F6": ("F6", ("ast:subquery:not_exists", "ast:subquery_pos:where", "ast:subquery_trait:correlated", "ast:corr_cmp:eq",
                  "ast:corr_cmp:neq", "ast:corr_cmp:gt", "ast:join_trait:self")),
    "F7": ("F7", ("ast:expr:interval", "ast:expr:date_arith", "ast:clause:order_by")),
    "F8": ("F8", ("ast:set_op:union", "ast:expr:collate", "ast:clause:order_by")),
    "F9": ("F9", ("ast:clause:distinct", "ast:expr:case", "ast:window_fn:aggregate", "ast:window_spec:empty",
                  "ast:pred:is_null", "ast:clause:order_by")),
    "F10": ("F10_q1", ("ast:window_fn:ranking", "ast:window_trait:ordered_arg", "ast:window_spec:frame",
                       "ast:window_frame:rows", "ast:window_frame:following")),
    "F11": ("F11", ("ast:stmt:merge", "ast:merge:not_matched_by_source", "ast:merge:delete")),
    "DF-A": ("DF-A", ("ast:set_op:except_all",)),
    "DF-B": ("DF-B", ("ast:set_op:intersect_all",)),
}

# family -> (oracle, unit). Plan classes come from the default plans measured before dispatch:
# F1/F6 LEFT_DELIM_JOIN, F2 HASH_JOIN (window_self_join rewrote the window away), F3 STREAMING_WINDOW +
# NESTED_LOOP_JOIN, F5/F11 HASH_JOIN, F7 ORDER_BY, F8 UNION, F9/F10 WINDOW, DF-A/DF-B HashJoinExec.
UNITS: dict[str, tuple[str, str]] = {
    "F1": ("plan_variant", "duckdb|plan_variant|correlated_subquery|delim_join|plain"),
    "F2": ("plan_variant", "duckdb|plan_variant|window|join|plain"),
    "F3": ("plan_variant", "duckdb|plan_variant|asof_join|window|plain"),
    "F5": ("plan_variant", "duckdb|plan_variant|join|join|plain"),
    "F6": ("plan_variant", "duckdb|plan_variant|correlated_subquery|delim_join|nulls"),
    "F7": ("plan_variant", "duckdb|plan_variant|plain|sort|plain"),
    "F8": ("plan_variant", "duckdb|plan_variant|set_op|union|plain"),
    "F9": ("plan_variant", "duckdb|plan_variant|window|window|nulls"),
    "F11": ("plan_variant", "duckdb|plan_variant|dml|join|plain"),
    "DF-A": ("cross_dbms", "datafusion|cross_dbms|set_op_all|join|dups"),
    "DF-B": ("cross_dbms", "datafusion|cross_dbms|set_op_all|join|dups"),
}
# plan operators the default plan must show (measured)
PLAN_FEATURES: dict[str, tuple[str, ...]] = {
    "F1": ("plan:LEFT_DELIM_JOIN", "plan:HASH_JOIN", "plan:SEQ_SCAN"),
    "F3": ("plan:STREAMING_WINDOW", "plan:NESTED_LOOP_JOIN"),
    "F8": ("plan:UNION",),
    "F9": ("plan:WINDOW",),
    "DF-A": ("plan:HashJoinExec", "plan:DataSourceExec"),
    "plain_df": ("plan:FilterExec", "plan:DataSourceExec"),
}

# ---- unit projection on hand-written feature sets --------------------------------------------
# (engine, oracle, features, layers, expected unit)
ALL_OK = {"ast": "ok", "plan": "ok", "data": "ok"}
UNIT_PROBES: list[tuple[str, str, tuple[str, ...], dict[str, str], str]] = [
    ("duckdb", "tlp", ("ast:stmt:select",), ALL_OK, "duckdb|tlp|plain|scan|plain"),
    ("duckdb", "tlp", ("ast:stmt:select", "plan:SEQ_SCAN", "plan:FILTER"), ALL_OK, "duckdb|tlp|plain|scan|plain"),
    ("duckdb", "norec", ("ast:stmt:select", "ast:clause:distinct", "plan:HASH_GROUP_BY"), ALL_OK,
     "duckdb|norec|distinct|aggregate|plain"),
    ("duckdb", "tlp", ("ast:stmt:select", "ast:agg:count", "ast:clause:distinct", "plan:UNGROUPED_AGGREGATE", "plan:ORDER_BY"),
     ALL_OK, "duckdb|tlp|aggregate|aggregate|plain"),
    ("duckdb", "tlp", ("ast:stmt:select", "ast:join:inner", "ast:agg:sum", "plan:HASH_JOIN", "plan:HASH_GROUP_BY"), ALL_OK,
     "duckdb|tlp|join|join|plain"),
    ("duckdb", "tlp", ("ast:stmt:select", "ast:join:left", "ast:join:inner", "plan:NESTED_LOOP_JOIN"), ALL_OK,
     "duckdb|tlp|outer_join|join|plain"),
    ("duckdb", "tlp", ("ast:stmt:select", "ast:join:asof", "ast:join:left", "plan:ASOF_JOIN", "plan:WINDOW"), ALL_OK,
     "duckdb|tlp|asof_join|asof_join|plain"),
    ("duckdb", "tlp", ("ast:stmt:select", "ast:subquery:in", "ast:join:left", "plan:CROSS_PRODUCT"), ALL_OK,
     "duckdb|tlp|subquery|join|plain"),
    ("duckdb", "tlp", ("ast:stmt:select", "ast:subquery:exists", "ast:subquery_trait:correlated", "ast:window_fn:ranking",
                       "plan:RIGHT_DELIM_JOIN", "plan:WINDOW"), ALL_OK, "duckdb|tlp|window|delim_join|plain"),
    ("duckdb", "tlp", ("ast:stmt:select", "ast:set_op:union", "ast:window_fn:ranking", "plan:UNION", "plan:TOP_N"), ALL_OK,
     "duckdb|tlp|set_op|union|plain"),
    ("duckdb", "tlp", ("ast:stmt:select", "ast:set_op:union", "ast:set_op:except_all", "plan:ORDER_BY"), ALL_OK,
     "duckdb|tlp|set_op_all|sort|plain"),
    ("duckdb", "plan_variant", ("ast:stmt:merge", "ast:set_op:union_all", "plan:MERGE_INTO"), ALL_OK,
     "duckdb|plan_variant|dml|scan|plain"),
    ("datafusion", "cross_dbms", ("ast:stmt:select", "plan:SortExec", "plan:AggregateExec"), ALL_OK,
     "datafusion|cross_dbms|plain|aggregate|plain"),
    ("datafusion", "cross_dbms", ("ast:stmt:select", "plan:WindowAggExec", "plan:SortExec"), ALL_OK,
     "datafusion|cross_dbms|plain|window|plain"),
    ("datafusion", "cross_dbms", ("ast:stmt:select", "plan:RecursiveQueryExec"), ALL_OK,
     "datafusion|cross_dbms|plain|union|plain"),
    # data: dups > nulls > empty > extreme > plain
    ("duckdb", "tlp", ("ast:stmt:select", "data:table:dup_rows", "data:table:has_null", "data:table:empty"), ALL_OK,
     "duckdb|tlp|plain|scan|dups"),
    ("duckdb", "tlp", ("ast:stmt:select", "data:setop:right_has_dups", "data:value:non_finite"), ALL_OK,
     "duckdb|tlp|plain|scan|dups"),
    ("duckdb", "tlp", ("ast:stmt:select", "data:setop:left_has_null", "data:table:empty"), ALL_OK, "duckdb|tlp|plain|scan|nulls"),
    ("duckdb", "tlp", ("ast:stmt:select", "data:table:empty", "data:value:extreme_number"), ALL_OK, "duckdb|tlp|plain|scan|empty"),
    ("duckdb", "tlp", ("ast:stmt:select", "data:value:non_finite", "data:value:zero"), ALL_OK, "duckdb|tlp|plain|scan|extreme"),
    ("duckdb", "tlp", ("ast:stmt:select", "data:value:zero", "data:type:integer", "data:table:single_row"), ALL_OK,
     "duckdb|tlp|plain|scan|plain"),
    # layers that were not computed
    ("postgres", "tlp", ("ast:stmt:select", "ast:join:inner"), {"ast": "ok", "plan": "skipped", "data": "skipped"},
     "postgres|tlp|join|none|unknown"),
    ("duckdb", "tlp", ("ast:parse:fallback", "ast:clause:where"), {"ast": "fallback", "plan": "unavailable", "data": "unavailable"},
     "duckdb|tlp|plain|none|unknown"),
]

# ---- spec checking on hand-written feature sets -----------------------------------------------
# (phi engine, features, layers, spec fields, expected (ok, missing, forbidden, undetermined))
DFA = ("ast:stmt:select", "ast:set_op:except_all", "data:setop:left_has_dups", "data:table:dup_rows", "plan:HashJoinExec")
AST_ONLY = {"ast": "ok", "plan": "skipped", "data": "skipped"}
SPEC_PROBES: list[tuple[str, tuple[str, ...], dict[str, str], dict, tuple[bool, tuple, tuple, tuple]]] = [
    ("datafusion", DFA, ALL_OK, dict(engine="datafusion", oracle="cross_dbms", required=("ast:set_op:except_all",)),
     (True, (), (), ())),
    ("datafusion", DFA, ALL_OK, dict(engine="datafusion", oracle="cross_dbms", required=("ast:set_op:all",),
                                     data_properties=("data:setop:left_has_dups",)), (True, (), (), ())),
    ("datafusion", DFA, ALL_OK, dict(engine="datafusion", oracle="cross_dbms", required=("ast:set_op", "plan", "data:setop")),
     (True, (), (), ())),
    ("datafusion", DFA, ALL_OK, dict(engine="datafusion", oracle="cross_dbms", required=("ast:set_op:intersect_all",)),
     (False, ("ast:set_op:intersect_all",), (), ())),
    ("datafusion", DFA, ALL_OK, dict(engine="datafusion", oracle="cross_dbms", required=("ast:set_op:all", "ast:window"),
                                     data_properties=("data:setop:right_has_dups",)),
     (False, ("ast:window", "data:setop:right_has_dups"), (), ())),
    ("datafusion", DFA, ALL_OK, dict(engine="datafusion", oracle="cross_dbms", forbidden=("ast:set_op:all",)),
     (False, (), ("ast:set_op:all",), ())),
    ("datafusion", DFA, ALL_OK, dict(engine="datafusion", oracle="cross_dbms", forbidden=("ast:clause:order_by", "ast:window")),
     (True, (), (), ())),
    ("datafusion", DFA, ALL_OK, dict(engine="datafusion", oracle="cross_dbms", required=("ast:set_op:except_all",),
                                     forbidden=("data:table:dup_rows", "plan:HashJoinExec")),
     (False, (), ("data:table:dup_rows", "plan:HashJoinExec"), ())),
    ("datafusion", DFA, ALL_OK, dict(engine="duckdb", oracle="cross_dbms", required=("ast:set_op:except_all",)),
     (False, (), (), ())),  # engine mismatch
    # a layer that was not computed cannot satisfy or refute anything about itself
    ("postgres", ("ast:stmt:select", "ast:set_op:except_all"), AST_ONLY,
     dict(engine="postgres", oracle="tlp", required=("ast:set_op:all",)), (True, (), (), ())),
    ("postgres", ("ast:stmt:select", "ast:set_op:except_all"), AST_ONLY,
     dict(engine="postgres", oracle="tlp", required=("ast:set_op:all",), data_properties=("data:setop:left_has_dups",)),
     (False, (), (), ("data:setop:left_has_dups",))),
    ("postgres", ("ast:stmt:select", "ast:set_op:except_all"), AST_ONLY,
     dict(engine="postgres", oracle="tlp", forbidden=("plan:HASH_JOIN", "ast:window")),
     (False, (), (), ("plan:HASH_JOIN",))),
]

# ---- dynamic layers: data and plan on real engines ---------------------------------------------
S_T = "CREATE TABLE t(v INT)"
S_U = "CREATE TABLE u(v INT)"
EXCEPT_ALL = "SELECT v FROM t EXCEPT ALL SELECT v FROM u"
# name -> (engine, setup, query, data features it must have, data features it must not have)
DATA_PROBES: dict[str, tuple[str, tuple[str, ...], str, tuple[str, ...], tuple[str, ...]]] = {
    "dfa": ("datafusion", (S_T, "INSERT INTO t VALUES (1),(1),(2),(2),(2),(NULL)", S_U, "INSERT INTO u VALUES (1),(2),(NULL)"),
            EXCEPT_ALL,
            ("data:setop:left_has_dups", "data:setop:left_has_null", "data:setop:right_has_null", "data:table:dup_rows",
             "data:table:has_null", "data:type:integer"),
            ("data:setop:right_has_dups", "data:table:empty", "data:table:single_row", "data:type:string", "data:value:zero")),
    "dfa_duckdb": ("duckdb", (S_T, "INSERT INTO t VALUES (1),(1),(2),(2),(2),(NULL)", S_U, "INSERT INTO u VALUES (1),(2),(NULL)"),
                   EXCEPT_ALL,
                   ("data:setop:left_has_dups", "data:setop:left_has_null", "data:setop:right_has_null", "data:table:dup_rows"),
                   ("data:setop:right_has_dups",)),
    "no_dups": ("datafusion", (S_T, "INSERT INTO t VALUES (1),(2),(3)", S_U, "INSERT INTO u VALUES (1),(1)"), EXCEPT_ALL,
                ("data:setop:right_has_dups", "data:table:dup_rows"),
                ("data:setop:left_has_dups", "data:setop:left_has_null", "data:setop:right_has_null", "data:table:has_null")),
    # the property is of the input of the set operation, not of the table behind it
    "operand_filter": ("duckdb", (S_T, "INSERT INTO t VALUES (1),(2),(2)", S_U, "INSERT INTO u VALUES (5)"),
                       "SELECT v FROM t WHERE v = 1 EXCEPT ALL SELECT v FROM u",
                       ("data:table:dup_rows", "data:table:single_row"), ("data:setop:left_has_dups",)),
    "operand_distinct": ("duckdb", (S_T, "INSERT INTO t VALUES (2),(2),(NULL)", S_U, "INSERT INTO u VALUES (5)"),
                         "SELECT DISTINCT v FROM t INTERSECT ALL SELECT v FROM u",
                         ("data:table:dup_rows", "data:setop:left_has_null"), ("data:setop:left_has_dups",)),
    "operand_projection": ("duckdb", ("CREATE TABLE t(a INT, b INT)", "INSERT INTO t VALUES (1, 10), (1, 20)", S_U,
                                      "INSERT INTO u VALUES (5)"),
                           "SELECT a FROM t UNION ALL SELECT v FROM u",
                           ("data:setop:left_has_dups",), ("data:table:dup_rows", "data:setop:right_has_dups")),
    # only tables the statement references count
    "referenced_only": ("duckdb", (S_T, "INSERT INTO t VALUES (NULL),(NULL)", "CREATE TABLE z(a INT)", "INSERT INTO z VALUES (7)"),
                        "SELECT a FROM z", ("data:table:single_row", "data:type:integer"),
                        ("data:table:has_null", "data:table:dup_rows", "data:table:empty")),
    "empty": ("duckdb", (S_T,), "SELECT v FROM t", ("data:table:empty",), ("data:table:single_row", "data:table:has_null")),
    "values": ("duckdb", ("CREATE TABLE m(i BIGINT, x DOUBLE, s VARCHAR)",
                          "INSERT INTO m VALUES (0, -1.5, ''), (9223372036854775807, 'nan', 'a')"),
               "SELECT i, x, s FROM m",
               ("data:value:zero", "data:value:negative", "data:value:empty_string", "data:value:extreme_number",
                "data:value:non_finite", "data:type:integer", "data:type:float", "data:type:string"),
               ("data:table:has_null", "data:type:date", "data:type:decimal")),
    "plain_values": ("duckdb", ("CREATE TABLE m(i INT, s VARCHAR)", "INSERT INTO m VALUES (1, 'a'), (2147483647, 'b')"),
                     "SELECT i FROM m", ("data:type:integer", "data:type:string"),
                     ("data:value:zero", "data:value:negative", "data:value:empty_string", "data:value:extreme_number",
                      "data:value:non_finite")),
    "types": ("duckdb", ("CREATE TABLE k(d DATE, ts TIMESTAMP, n DECIMAL(10,2), b BOOLEAN)",
                         "INSERT INTO k VALUES (DATE '2020-01-02', TIMESTAMP '2020-01-02 03:04:05', 1.25, true)"),
              "SELECT d FROM k", ("data:type:date", "data:type:timestamp", "data:type:decimal", "data:type:boolean"),
              ("data:type:integer", "data:type:string", "data:type:float")),
    "types_df": ("datafusion", ("CREATE TABLE k(d DATE, n DECIMAL(10,2), b BOOLEAN, s VARCHAR, x DOUBLE)",
                                "INSERT INTO k VALUES (DATE '2020-01-02', 1.25, true, 'a', 1.5)"),
                 "SELECT d FROM k", ("data:type:date", "data:type:decimal", "data:type:boolean", "data:type:string",
                                     "data:type:float"), ("data:type:integer",)),
    "join_tables": ("duckdb", ("CREATE TABLE a(x INT)", "INSERT INTO a VALUES (1),(1)", "CREATE TABLE b(x INT)",
                               "INSERT INTO b VALUES (NULL)"),
                    "SELECT * FROM a JOIN b ON a.x = b.x WHERE EXISTS (SELECT 1 FROM a a2 WHERE a2.x = b.x)",
                    ("data:table:dup_rows", "data:table:has_null", "data:table:single_row"), ("data:table:empty",)),
}
# a setup that fails: the dynamic layers are unavailable, the ast layer is still there
BROKEN_SETUP = ("duckdb", ("CREATE TABLE t(a INTEGER)", "INSERT INTO no_such_table VALUES (1)"), "SELECT a FROM t WHERE a > 0")

# ---- specs against real statements: (s04 case or DATA_PROBES name, spec fields, expected ok) ----
SPEC_PAIRS: list[tuple[str, dict, bool]] = [
    ("DF-A", dict(engine="datafusion", oracle="cross_dbms", required=("ast:set_op:except_all",),
                  data_properties=("data:setop:left_has_dups",)), True),
    ("DF-A", dict(engine="datafusion", oracle="cross_dbms", required=("ast:set_op:all",), forbidden=("ast:clause:order_by",)), True),
    ("DF-B", dict(engine="datafusion", oracle="cross_dbms", required=("ast:set_op:except_all",)), False),
    ("DF-B", dict(engine="datafusion", oracle="cross_dbms", required=("ast:set_op:all",),
                  data_properties=("data:setop:left_has_dups", "data:setop:right_has_null")), True),
    ("no_dups", dict(engine="datafusion", oracle="cross_dbms", required=("ast:set_op:except_all",),
                     data_properties=("data:setop:left_has_dups",)), False),
    ("no_dups", dict(engine="datafusion", oracle="cross_dbms", required=("ast:set_op:except_all",),
                     forbidden=("data:setop:left_has_dups",)), True),
    ("F2", dict(engine="duckdb", oracle="plan_variant", required=("ast:window", "ast:window_trait:dup_partition_key")), True),
    ("F2", dict(engine="duckdb", oracle="plan_variant", required=("ast:window",), forbidden=("ast:window_spec:partition",)), False),
    ("F9", dict(engine="duckdb", oracle="plan_variant", required=("ast:window_spec:empty", "ast:clause:distinct"),
                data_properties=("data:table:has_null",)), True),
    ("F9", dict(engine="duckdb", oracle="plan_variant", required=("ast:window_trait:dup_partition_key",)), False),
    ("F1", dict(engine="duckdb", oracle="plan_variant", required=("ast:subquery_trait:correlated", "ast:corr_cmp:neq",
                                                                  "plan:LEFT_DELIM_JOIN")), True),
    ("F1", dict(engine="duckdb", oracle="plan_variant", required=("ast:subquery:not_exists",)), False),
    ("F6", dict(engine="duckdb", oracle="plan_variant", required=("ast:subquery:not_exists", "ast:corr_cmp:gt"),
                data_properties=("data:table:has_null", "data:value:extreme_number")), True),
    ("F8", dict(engine="duckdb", oracle="plan_variant", required=("ast:set_op:distinct", "ast:expr:collate"),
                forbidden=("ast:set_op:all",)), True),
    ("F11", dict(engine="duckdb", oracle="plan_variant", required=("ast:stmt:merge",), forbidden=("ast:merge:insert",)), True),
    ("F3", dict(engine="duckdb", oracle="plan_variant", required=("ast:join:asof",), forbidden=("ast:join_trait:non_equi",)), False),
    ("F7", dict(engine="datafusion", oracle="plan_variant", required=("ast:expr:date_arith",)), False),  # engine mismatch
]

# ---- corpus report: seeds/corpus.json, measured before dispatch ---------------------------------
CORPUS = {
    "total": 1092, "duckdb": 784, "postgres": 308,
    "sqlglot_failures": 34,          # 17 + 17: unfilled {placeholders} and "USING (...) AS alias"
    "duckdb_setup_ok": 532,          # the other 252 seeds have a setup statement DuckDB 1.5.5 rejects
}
