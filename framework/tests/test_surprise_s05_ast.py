"""Statement-layer extraction: leaves, the ast rules, fallback, and invented features."""
from __future__ import annotations

from surprise.features import FeatureDef, Phi, default_registry, extract_ast, make_phi
from surprise.features.vocabulary import BASE_FEATURES

PLAIN = "SELECT a FROM t"
INSERT = "INSERT INTO t VALUES (1)"

# leaf -> (sql that has it, sql that does not). SQL is local; nothing is imported from the gate.
EXAMPLES: dict[str, tuple[str, str]] = {
    "ast:stmt:select": (PLAIN, INSERT),
    "ast:stmt:merge": ("MERGE INTO t USING s ON t.a = s.a WHEN MATCHED THEN DELETE", PLAIN),
    "ast:stmt:insert": (INSERT, PLAIN),
    "ast:stmt:update": ("UPDATE t SET b = 1 WHERE a = 2", PLAIN),
    "ast:stmt:delete": ("DELETE FROM t WHERE a = 1", PLAIN),
    "ast:set_op:union_all": ("SELECT v FROM t UNION ALL SELECT v FROM u", "SELECT v FROM t UNION SELECT v FROM u"),
    "ast:set_op:except_all": ("SELECT v FROM t EXCEPT ALL SELECT v FROM u", "SELECT v FROM t EXCEPT SELECT v FROM u"),
    "ast:set_op:intersect_all": ("SELECT v FROM t INTERSECT ALL SELECT v FROM u", "SELECT v FROM t INTERSECT SELECT v FROM u"),
    "ast:set_op:union": ("SELECT v FROM t UNION SELECT v FROM u", "SELECT v FROM t UNION ALL SELECT v FROM u"),
    "ast:set_op:except": ("SELECT v FROM t EXCEPT SELECT v FROM u", "SELECT v FROM t EXCEPT ALL SELECT v FROM u"),
    "ast:set_op:intersect": ("SELECT v FROM t INTERSECT SELECT v FROM u", "SELECT v FROM t INTERSECT ALL SELECT v FROM u"),
    "ast:join:inner": ("SELECT * FROM a JOIN b ON a.x = b.x", "SELECT * FROM a CROSS JOIN b"),
    "ast:join:left": ("SELECT * FROM a LEFT JOIN b USING (x)", "SELECT * FROM a JOIN b ON a.x = b.x"),
    "ast:join:right": ("SELECT * FROM a RIGHT JOIN b ON a.x = b.x", "SELECT * FROM a LEFT JOIN b ON a.x = b.x"),
    "ast:join:full": ("SELECT * FROM a FULL JOIN b ON a.x = b.x", "SELECT * FROM a LEFT JOIN b ON a.x = b.x"),
    "ast:join:cross": ("SELECT * FROM a, b", "SELECT * FROM a JOIN b ON a.x = b.x"),
    "ast:join:asof": ("SELECT * FROM a ASOF JOIN b ON a.id = b.id AND a.ts >= b.ts", "SELECT * FROM a JOIN b ON a.id = b.id"),
    "ast:join_cond:on": ("SELECT * FROM a JOIN b ON a.x = b.x", "SELECT * FROM a JOIN b USING (x)"),
    "ast:join_cond:using": ("SELECT * FROM a JOIN b USING (x)", "SELECT * FROM a JOIN b ON a.x = b.x"),
    "ast:join_cond:natural": ("SELECT * FROM a NATURAL JOIN b", "SELECT * FROM a JOIN b ON a.x = b.x"),
    "ast:join_trait:self": ("SELECT * FROM t x JOIN t y ON x.a = y.a", "SELECT * FROM t JOIN u ON t.a = u.a"),
    "ast:join_trait:non_equi": ("SELECT * FROM a JOIN b ON a.x > b.x", "SELECT * FROM a JOIN b ON a.x = b.x"),
    "ast:join_trait:lateral": (
        "SELECT * FROM a JOIN LATERAL (SELECT * FROM b WHERE b.x = a.x) s ON true",
        "SELECT * FROM a JOIN b ON a.x = b.x",
    ),
    "ast:subquery:exists": ("SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u)", "SELECT a FROM t WHERE NOT EXISTS (SELECT 1 FROM u)"),
    "ast:subquery:not_exists": ("SELECT a FROM t WHERE NOT EXISTS (SELECT 1 FROM u)", "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u)"),
    "ast:subquery:in": ("SELECT a FROM t WHERE a IN (SELECT b FROM u)", "SELECT a FROM t WHERE a NOT IN (SELECT b FROM u)"),
    "ast:subquery:not_in": ("SELECT a FROM t WHERE a NOT IN (SELECT b FROM u)", "SELECT a FROM t WHERE a IN (SELECT b FROM u)"),
    "ast:subquery:scalar": ("SELECT (SELECT max(b) FROM u) FROM t", "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u)"),
    "ast:subquery:all": ("SELECT a FROM t WHERE b > ALL (SELECT w FROM u)", "SELECT a FROM t WHERE b = ANY (SELECT w FROM u)"),
    "ast:subquery:any": ("SELECT a FROM t WHERE b = ANY (SELECT w FROM u)", "SELECT a FROM t WHERE b > ALL (SELECT w FROM u)"),
    "ast:subquery:derived": ("SELECT * FROM (SELECT a FROM t) s", "SELECT (SELECT max(b) FROM u) FROM t"),
    "ast:subquery_pos:select": ("SELECT (SELECT max(b) FROM u) FROM t", "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u)"),
    "ast:subquery_pos:where": ("SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u)", "SELECT (SELECT max(b) FROM u) FROM t"),
    "ast:subquery_pos:from": ("SELECT * FROM (SELECT a FROM t) s", "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u)"),
    "ast:subquery_pos:having": (
        "SELECT k FROM t GROUP BY k HAVING sum(a) > (SELECT avg(a) FROM u)",
        "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u)",
    ),
    "ast:subquery_pos:on": (
        "SELECT * FROM a JOIN b ON a.x = (SELECT max(x) FROM c)",
        "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u)",
    ),
    "ast:subquery_trait:correlated": (
        "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.b = t.a)",
        "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.b > 0)",
    ),
    "ast:corr_cmp:eq": (
        "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.b = t.a)",
        "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.b > t.a)",
    ),
    "ast:corr_cmp:neq": (
        "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.b <> t.a)",
        "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.b = t.a)",
    ),
    "ast:corr_cmp:lt": (
        "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.b < t.a)",
        "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.b > t.a)",
    ),
    "ast:corr_cmp:le": (
        "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.b <= t.a)",
        "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.b < t.a)",
    ),
    "ast:corr_cmp:gt": (
        "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.b > t.a)",
        "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.b < t.a)",
    ),
    "ast:corr_cmp:ge": (
        "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.b >= t.a)",
        "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.b > t.a)",
    ),
    "ast:agg:count": ("SELECT count(a) FROM t", "SELECT sum(a) FROM t"),
    "ast:agg:sum": ("SELECT sum(a) FROM t", "SELECT count(a) FROM t"),
    "ast:agg:avg": ("SELECT avg(a) FROM t", "SELECT sum(a) FROM t"),
    "ast:agg:min": ("SELECT min(a) FROM t", "SELECT max(a) FROM t"),
    "ast:agg:max": ("SELECT max(a) FROM t", "SELECT min(a) FROM t"),
    "ast:agg:other": ("SELECT string_agg(s, ',') FROM t", "SELECT sum(a) FROM t"),
    "ast:agg_trait:star": ("SELECT count(*) FROM t", "SELECT count(a) FROM t"),
    "ast:agg_trait:distinct": ("SELECT count(DISTINCT a) FROM t", "SELECT count(a) FROM t"),
    "ast:agg_trait:filter": ("SELECT count(*) FILTER (WHERE a > 1) FROM t", "SELECT count(*) FROM t"),
    "ast:agg_trait:ordered": ("SELECT string_agg(s, ',' ORDER BY a) FROM t", "SELECT string_agg(s, ',') FROM t"),
    "ast:group:by": ("SELECT k FROM t GROUP BY k", PLAIN),
    "ast:group:having": ("SELECT k FROM t GROUP BY k HAVING sum(a) > 1", "SELECT k FROM t GROUP BY k"),
    "ast:group:rollup": ("SELECT a, b FROM t GROUP BY ROLLUP (a, b)", "SELECT a, b FROM t GROUP BY CUBE (a, b)"),
    "ast:group:cube": ("SELECT a, b FROM t GROUP BY CUBE (a, b)", "SELECT a, b FROM t GROUP BY ROLLUP (a, b)"),
    "ast:group:grouping_sets": ("SELECT a, b FROM t GROUP BY GROUPING SETS ((a), (b))", "SELECT a, b FROM t GROUP BY ROLLUP (a, b)"),
    "ast:window_fn:ranking": ("SELECT row_number() OVER (ORDER BY a) FROM t", "SELECT sum(a) OVER (ORDER BY a) FROM t"),
    "ast:window_fn:navigation": ("SELECT lag(a) OVER (ORDER BY a) FROM t", "SELECT row_number() OVER (ORDER BY a) FROM t"),
    "ast:window_fn:aggregate": ("SELECT sum(a) OVER () FROM t", "SELECT row_number() OVER () FROM t"),
    "ast:window_fn:other": ("SELECT abs(a) OVER () FROM t", "SELECT abs(a) FROM t"),
    "ast:window_spec:partition": ("SELECT sum(a) OVER (PARTITION BY k) FROM t", "SELECT sum(a) OVER () FROM t"),
    "ast:window_spec:order": ("SELECT sum(a) OVER (ORDER BY a) FROM t", "SELECT sum(a) OVER () FROM t"),
    "ast:window_spec:frame": (
        "SELECT sum(a) OVER (ORDER BY a ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING) FROM t",
        "SELECT sum(a) OVER (ORDER BY a) FROM t",
    ),
    "ast:window_spec:empty": ("SELECT count(*) OVER () FROM t", "SELECT count(*) OVER (ORDER BY a) FROM t"),
    "ast:window_frame:rows": (
        "SELECT sum(a) OVER (ORDER BY a ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING) FROM t",
        "SELECT sum(a) OVER (ORDER BY a RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) FROM t",
    ),
    "ast:window_frame:range": (
        "SELECT sum(a) OVER (ORDER BY a RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) FROM t",
        "SELECT sum(a) OVER (ORDER BY a ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING) FROM t",
    ),
    "ast:window_frame:groups": (
        "SELECT sum(a) OVER (ORDER BY a GROUPS BETWEEN 1 PRECEDING AND 1 FOLLOWING) FROM t",
        "SELECT sum(a) OVER (ORDER BY a ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING) FROM t",
    ),
    "ast:window_frame:preceding": (
        "SELECT sum(a) OVER (ORDER BY a ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) FROM t",
        "SELECT sum(a) OVER (ORDER BY a ROWS BETWEEN 1 FOLLOWING AND 2 FOLLOWING) FROM t",
    ),
    "ast:window_frame:following": (
        "SELECT sum(a) OVER (ORDER BY a ROWS BETWEEN 1 FOLLOWING AND 2 FOLLOWING) FROM t",
        "SELECT sum(a) OVER (ORDER BY a ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) FROM t",
    ),
    "ast:window_trait:dup_partition_key": (
        "SELECT sum(v) OVER (PARTITION BY a, a, b) FROM src",
        "SELECT sum(v) OVER (PARTITION BY a, b) FROM src",
    ),
    "ast:window_trait:multiple": (
        "SELECT sum(v) OVER (), sum(v) OVER () FROM src",
        "SELECT sum(v) OVER () FROM src",
    ),
    "ast:window_trait:ordered_arg": (
        "SELECT ntile(2 ORDER BY v) OVER (ORDER BY v) FROM t",
        "SELECT ntile(2) OVER (ORDER BY v) FROM t",
    ),
    "ast:clause:where": ("SELECT a FROM t WHERE a > 1", PLAIN),
    "ast:clause:distinct": ("SELECT DISTINCT a FROM t", "SELECT count(DISTINCT a) FROM t"),
    "ast:clause:order_by": ("SELECT a FROM t ORDER BY a", "SELECT sum(a) OVER (ORDER BY a) FROM t"),
    "ast:clause:limit": ("SELECT a FROM t LIMIT 3", PLAIN),
    "ast:clause:offset": ("SELECT a FROM t OFFSET 1", "SELECT a FROM t LIMIT 3"),
    "ast:clause:qualify": ("SELECT a FROM t QUALIFY row_number() OVER (ORDER BY a) = 1", "SELECT a FROM t WHERE a = 1"),
    "ast:cte:plain": ("WITH c AS (SELECT a FROM t) SELECT * FROM c", "WITH RECURSIVE r AS (SELECT 1 AS n) SELECT * FROM r"),
    "ast:cte:recursive": (
        "WITH RECURSIVE r AS (SELECT 1 AS n UNION ALL SELECT n + 1 FROM r WHERE n < 5) SELECT * FROM r",
        "WITH c AS (SELECT a FROM t) SELECT * FROM c",
    ),
    "ast:cmp:eq": ("SELECT a FROM t WHERE a = 1", "SELECT a FROM t WHERE a > 1"),
    "ast:cmp:neq": ("SELECT a FROM t WHERE a <> 1", "SELECT a FROM t WHERE a = 1"),
    "ast:cmp:lt": ("SELECT a FROM t WHERE a < 1", "SELECT a FROM t WHERE a > 1"),
    "ast:cmp:le": ("SELECT a FROM t WHERE a <= 1", "SELECT a FROM t WHERE a < 1"),
    "ast:cmp:gt": ("SELECT a FROM t WHERE a > 1", "SELECT a FROM t WHERE a < 1"),
    "ast:cmp:ge": ("SELECT a FROM t WHERE a >= 1", "SELECT a FROM t WHERE a > 1"),
    "ast:pred:is_null": ("SELECT a FROM t WHERE a IS NULL", "SELECT a FROM t WHERE a IS NOT NULL"),
    "ast:pred:is_not_null": ("SELECT a FROM t WHERE a IS NOT NULL", "SELECT a FROM t WHERE a IS NULL"),
    "ast:pred:between": ("SELECT a FROM t WHERE a BETWEEN 1 AND 3", "SELECT a FROM t WHERE a >= 1"),
    "ast:pred:like": ("SELECT a FROM t WHERE s LIKE 'x%'", "SELECT a FROM t WHERE a = 1"),
    "ast:pred:in_list": ("SELECT a FROM t WHERE a IN (1, 2, 3)", "SELECT a FROM t WHERE a IN (SELECT b FROM u)"),
    "ast:bool:and": ("SELECT a FROM t WHERE a > 1 AND b > 2", "SELECT a FROM t WHERE a > 1 OR b > 2"),
    "ast:bool:or": ("SELECT a FROM t WHERE a > 1 OR b > 2", "SELECT a FROM t WHERE a > 1 AND b > 2"),
    "ast:expr:case": ("SELECT CASE WHEN a > 0 THEN 1 ELSE 0 END FROM t", PLAIN),
    "ast:expr:coalesce": ("SELECT coalesce(a, 0) FROM t", PLAIN),
    "ast:expr:nullif": ("SELECT nullif(a, 0) FROM t", PLAIN),
    "ast:expr:cast": ("SELECT CAST(a AS VARCHAR) FROM t", PLAIN),
    "ast:expr:arith": ("SELECT a + 1 FROM t", PLAIN),
    "ast:expr:concat": ("SELECT s || 'x' FROM t", "SELECT a + 1 FROM t"),
    "ast:expr:collate": ("SELECT s COLLATE NOCASE FROM t", PLAIN),
    "ast:expr:interval": ("SELECT INTERVAL '1 day'", "SELECT a + 1 FROM t"),
    "ast:expr:date_arith": ("SELECT d + INTERVAL '1 day' FROM t", "SELECT a + 1 FROM t"),
    "ast:merge:matched": (
        "MERGE INTO t USING s ON t.a = s.a WHEN MATCHED THEN UPDATE SET b = 1",
        "MERGE INTO t USING s ON t.a = s.a WHEN NOT MATCHED THEN INSERT VALUES (1, 1)",
    ),
    "ast:merge:not_matched": (
        "MERGE INTO t USING s ON t.a = s.a WHEN NOT MATCHED THEN INSERT VALUES (1, 1)",
        "MERGE INTO t USING s ON t.a = s.a WHEN MATCHED THEN DELETE",
    ),
    "ast:merge:not_matched_by_source": (
        "MERGE INTO t USING s ON t.a = s.a WHEN NOT MATCHED BY SOURCE THEN DELETE",
        "MERGE INTO t USING s ON t.a = s.a WHEN NOT MATCHED THEN INSERT VALUES (1, 1)",
    ),
    "ast:merge:update": (
        "MERGE INTO t USING s ON t.a = s.a WHEN MATCHED THEN UPDATE SET b = 1",
        "MERGE INTO t USING s ON t.a = s.a WHEN MATCHED THEN DELETE",
    ),
    "ast:merge:delete": (
        "MERGE INTO t USING s ON t.a = s.a WHEN MATCHED THEN DELETE",
        "MERGE INTO t USING s ON t.a = s.a WHEN MATCHED THEN UPDATE SET b = 1",
    ),
    "ast:merge:insert": (
        "MERGE INTO t USING s ON t.a = s.a WHEN NOT MATCHED THEN INSERT VALUES (1, 1)",
        "MERGE INTO t USING s ON t.a = s.a WHEN MATCHED THEN DELETE",
    ),
    "ast:parse:fallback": ("SELECT {agg}(id) OVER () FROM t", PLAIN),
}

FAMILIES: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "F1": (
        "duckdb",
        "SELECT EXISTS ( SELECT 1 FROM issue23979_s2 x WHERE x.o = l.o AND r.wh <> x.wh ) AS correlated_exists, "
        "EXISTS ( SELECT 1 FROM issue23979_s2 x WHERE x.o = l.o AND (r.wh + 0) <> x.wh ) AS equivalent_rewrite "
        "FROM issue23979_l l LEFT JOIN issue23979_r r USING (o) JOIN issue23979_s2 s2 USING (o) ORDER BY l.o",
        ("ast:subquery:exists", "ast:subquery_pos:select", "ast:subquery_trait:correlated", "ast:corr_cmp:eq",
         "ast:corr_cmp:neq", "ast:join:left", "ast:join:inner", "ast:join_cond:using", "ast:clause:order_by"),
    ),
    "F2": (
        "duckdb",
        "SELECT SUM(v) OVER (PARTITION BY a, a, b) AS w_aab, SUM(v) OVER (PARTITION BY a, a, a) AS w_aaa "
        "FROM src ORDER BY b",
        ("ast:window_fn:aggregate", "ast:window_spec:partition", "ast:window_trait:dup_partition_key",
         "ast:window_trait:multiple", "ast:clause:order_by"),
    ),
    "F3": (
        "duckdb",
        "SELECT px.p FROM ev ASOF JOIN px ON ev.id = px.id AND ev.ts >= px.ts ORDER BY ev.id, ev.ts, px.p",
        ("ast:join:asof", "ast:join_trait:non_equi", "ast:clause:order_by"),
    ),
    "F5": (
        "duckdb",
        "WITH c AS ( SELECT flag FROM ordered_probe ORDER BY ord OFFSET 2 ) "
        "SELECT * FROM c INNER JOIN boolean_keys ON flag = flag_key",
        ("ast:cte:plain", "ast:clause:offset", "ast:clause:order_by", "ast:join:inner"),
    ),
    "F6": (
        "duckdb",
        "SELECT o1.amount FROM orders o1 WHERE NOT EXISTS (SELECT 1 FROM orders o2 "
        "WHERE o2.acct_id = o1.acct_id AND o2.order_id <> o1.order_id AND o2.amount > o1.amount)",
        ("ast:subquery:not_exists", "ast:subquery_pos:where", "ast:subquery_trait:correlated", "ast:corr_cmp:eq",
         "ast:corr_cmp:neq", "ast:corr_cmp:gt", "ast:join_trait:self"),
    ),
    "F7": (
        "duckdb",
        "SELECT d + INTERVAL '1 month' d1, d + INTERVAL '30 days' d2 FROM t ORDER BY d",
        ("ast:expr:interval", "ast:expr:date_arith", "ast:clause:order_by"),
    ),
    "F8": (
        "duckdb",
        "SELECT s COLLATE NOCASE AS s_nc FROM t8a UNION SELECT s COLLATE NOCASE AS s_nc FROM t8b ORDER BY s_nc",
        ("ast:set_op:union", "ast:expr:collate", "ast:clause:order_by"),
    ),
    "F9": (
        "duckdb",
        "SELECT DISTINCT CASE WHEN x IS NULL THEN 'n' WHEN x > y THEN 'gt' WHEN x = y THEN 'eq' ELSE 'lt' END AS bucket, "
        "COUNT(*) OVER () AS total FROM t ORDER BY bucket",
        ("ast:clause:distinct", "ast:expr:case", "ast:window_fn:aggregate", "ast:window_spec:empty",
         "ast:pred:is_null", "ast:clause:order_by"),
    ),
    "F10": (
        "duckdb",
        "SELECT ntile(2 ORDER BY v) OVER (ORDER BY v ROWS BETWEEN 2 FOLLOWING AND 1 FOLLOWING) FROM t1",
        ("ast:window_fn:ranking", "ast:window_trait:ordered_arg", "ast:window_spec:frame",
         "ast:window_frame:rows", "ast:window_frame:following"),
    ),
    "F11": (
        "duckdb",
        "MERGE INTO t USING s ON t.a = s.a WHEN NOT MATCHED BY SOURCE THEN DELETE",
        ("ast:stmt:merge", "ast:merge:not_matched_by_source", "ast:merge:delete"),
    ),
    "DF-A": ("datafusion", "SELECT v FROM t EXCEPT ALL SELECT v FROM u", ("ast:set_op:except_all",)),
    "DF-B": ("datafusion", "SELECT v FROM t INTERSECT ALL SELECT v FROM u", ("ast:set_op:intersect_all",)),
}


def _ok(sql: str, engine: str = "duckdb") -> frozenset[str]:
    features, status = extract_ast(sql, engine)
    assert status == "ok", sql
    assert "ast:parse:fallback" not in features
    return features


def test_non_string_layer_status_is_a_value_error() -> None:
    plan_list = {"ast": "ok", "plan": ["ok"], "data": "ok"}
    with_tuple = {"ast": ("ok",), "plan": "ok", "data": "ok"}
    for layers in (plan_list, with_tuple):
        try:
            make_phi("duckdb", ("ast:stmt:select",), layers)
        except ValueError:
            pass
        else:
            raise AssertionError(layers)
        try:
            Phi.from_dict({
                "schema": 1,
                "engine": "duckdb",
                "features": ["ast:stmt:select"],
                "layers": layers,
                "vocab": "x",
            })
        except ValueError:
            pass
        else:
            raise AssertionError(layers)


def test_every_ast_leaf_has_a_positive_and_a_negative() -> None:
    leaves = [item.feature_id for item in BASE_FEATURES if item.layer == "ast" and item.kind == "leaf"]
    assert set(EXAMPLES) == set(leaves)
    for leaf in leaves:
        positive, negative = EXAMPLES[leaf]
        got, _status = extract_ast(positive, "duckdb")
        assert leaf in got, leaf
        missing, status = extract_ast(negative, "duckdb")
        assert status == "ok", leaf
        assert leaf not in missing, leaf
        again, _status = extract_ast(positive, "duckdb")
        assert again == got


def test_outputs_are_accepted_ast_leaves() -> None:
    registry = default_registry()
    features = _ok("SELECT upper(substr(s, 1, 2)) FROM t WHERE a > 1")
    for feature_id in features:
        definition = registry.get(feature_id)
        assert definition.kind == "leaf" and definition.layer == "ast" and definition.accepted


def test_statement_kind_is_only_the_top_level_statement() -> None:
    inserted = _ok("INSERT INTO t SELECT a FROM u WHERE a > 1")
    assert "ast:stmt:insert" in inserted
    assert "ast:stmt:select" not in inserted
    assert "ast:clause:where" in inserted and "ast:cmp:gt" in inserted
    deleted = _ok("DELETE FROM t WHERE a = 1 RETURNING a")
    assert deleted >= {"ast:stmt:delete", "ast:clause:where"}
    assert "ast:stmt:select" not in deleted


def test_set_operations_keep_all_apart_from_distinct() -> None:
    both = _ok("SELECT v FROM t UNION ALL SELECT v FROM u EXCEPT SELECT v FROM w")
    assert "ast:set_op:union_all" in both and "ast:set_op:except" in both
    assert "ast:set_op:union" not in both and "ast:set_op:except_all" not in both
    nested = _ok("SELECT * FROM (SELECT v FROM t EXCEPT ALL SELECT v FROM u) s")
    assert "ast:set_op:except_all" in nested and "ast:subquery:derived" in nested


def test_join_kinds_conditions_and_traits() -> None:
    inner = _ok("SELECT * FROM a INNER JOIN b ON a.x = b.x")
    assert inner >= {"ast:join:inner", "ast:join_cond:on"}
    assert "ast:join:cross" not in inner and "ast:join_trait:non_equi" not in inner
    comma = _ok("SELECT * FROM a, b WHERE a.x > b.x")
    assert "ast:join:cross" in comma and "ast:clause:where" in comma and "ast:cmp:gt" in comma
    assert "ast:join:inner" not in comma and "ast:join_trait:non_equi" not in comma
    natural = _ok("SELECT * FROM a NATURAL JOIN b")
    assert natural >= {"ast:join:inner", "ast:join_cond:natural"}
    assert "ast:join_cond:on" not in natural and "ast:join:cross" not in natural
    asof = _ok("SELECT * FROM a ASOF LEFT JOIN b ON a.id = b.id AND a.ts >= b.ts")
    assert asof >= {"ast:join:asof", "ast:join:left", "ast:join_trait:non_equi", "ast:join_cond:on"}
    assert "ast:join:inner" not in asof
    equi = _ok("SELECT * FROM t x JOIN t y ON x.a = y.b")
    assert "ast:join_trait:self" in equi and "ast:join_trait:non_equi" not in equi
    buried = _ok("SELECT * FROM a JOIN b ON a.x = (SELECT max(x) FROM c WHERE c.y > a.y)")
    assert "ast:join_trait:non_equi" not in buried and "ast:cmp:gt" in buried
    cte_name = _ok("WITH c AS (SELECT a FROM p) SELECT * FROM c x JOIN c y ON x.a = y.a")
    assert "ast:join_trait:self" not in cte_name
    same_base = _ok("WITH c AS (SELECT a FROM t) SELECT * FROM c JOIN t ON c.a = t.a")
    assert "ast:join_trait:self" in same_base


def test_subquery_forms_are_exclusive_at_each_occurrence() -> None:
    not_exists = _ok("SELECT a FROM t WHERE NOT EXISTS (SELECT 1 FROM u WHERE u.b > 5)")
    assert "ast:subquery:not_exists" in not_exists and "ast:subquery:exists" not in not_exists
    not_in = _ok("SELECT a FROM t WHERE a NOT IN (SELECT b FROM u)")
    assert "ast:subquery:not_in" in not_in
    assert "ast:subquery:in" not in not_in and "ast:pred:in_list" not in not_in
    values = _ok("SELECT a FROM t WHERE a IN (1, 2, 3)")
    assert "ast:pred:in_list" in values and "ast:subquery:in" not in values
    exists = _ok("SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u)")
    assert "ast:subquery:exists" in exists and "ast:subquery:scalar" not in exists
    quantified = _ok("SELECT a FROM t WHERE b > ALL (SELECT w FROM u) AND b = SOME (SELECT w FROM u)")
    assert quantified >= {"ast:subquery:all", "ast:subquery:any"}
    assert "ast:subquery:scalar" not in quantified
    derived = _ok("SELECT * FROM a JOIN LATERAL (SELECT * FROM b WHERE b.x = a.x) s ON true")
    assert "ast:subquery:derived" in derived and "ast:join_trait:lateral" in derived
    assert "ast:subquery:scalar" not in derived


def test_subquery_position_is_the_enclosing_clause() -> None:
    assert "ast:subquery_pos:select" in _ok("SELECT (SELECT max(b) FROM u WHERE u.k = t.k) FROM t")
    assert "ast:subquery_pos:where" in _ok("SELECT a FROM t WHERE a IN (SELECT b FROM u)")
    assert "ast:subquery_pos:from" in _ok("SELECT * FROM (SELECT a FROM t) s")
    assert "ast:subquery_pos:having" in _ok("SELECT k FROM t GROUP BY k HAVING sum(a) > (SELECT 1)")
    assert "ast:subquery_pos:on" in _ok("SELECT * FROM a JOIN b ON a.x = (SELECT max(x) FROM c)")
    lateral = _ok("SELECT * FROM a JOIN LATERAL (SELECT * FROM b) s ON true")
    assert "ast:subquery_pos:from" in lateral and "ast:subquery_pos:on" not in lateral


def test_correlation_needs_a_qualified_outer_column() -> None:
    qualified = _ok("SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.b = t.a)")
    assert "ast:subquery_trait:correlated" in qualified and "ast:corr_cmp:eq" in qualified
    unbound = _ok("SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.b > 0)")
    assert "ast:subquery_trait:correlated" not in unbound and "ast:corr_cmp:gt" not in unbound
    unqualified = _ok("SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE b = a)")
    assert "ast:subquery_trait:correlated" not in unqualified
    half = _ok("SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE b = t.a)")
    assert "ast:subquery_trait:correlated" in half and "ast:corr_cmp:eq" not in half
    derived = _ok("SELECT * FROM a JOIN (SELECT * FROM b WHERE b.x = a.x) s ON true")
    assert "ast:subquery_trait:correlated" in derived and "ast:corr_cmp:eq" in derived


def test_corr_cmp_keeps_the_written_operator_and_needs_bare_columns() -> None:
    compared = _ok(
        "SELECT a FROM o o1 WHERE EXISTS (SELECT 1 FROM o o2 WHERE o2.v > o1.v AND o2.v < o1.w "
        "AND o2.v >= o1.x AND o2.v <= o1.y AND o2.v <> o1.z)"
    )
    assert compared >= {"ast:corr_cmp:gt", "ast:corr_cmp:lt", "ast:corr_cmp:ge", "ast:corr_cmp:le", "ast:corr_cmp:neq"}
    assert "ast:corr_cmp:eq" not in compared
    rewritten = _ok(
        "SELECT r.wh FROM l l JOIN r r ON true WHERE EXISTS ("
        "SELECT 1 FROM s x WHERE x.o = l.o AND (r.wh + 0) <> x.wh)"
    )
    assert "ast:corr_cmp:eq" in rewritten and "ast:corr_cmp:neq" not in rewritten
    assert "ast:cmp:neq" in rewritten and "ast:expr:arith" in rewritten


def test_aggregates_stop_at_over_and_filter_where_is_not_a_clause() -> None:
    plain = _ok("SELECT count(*), count(DISTINCT a), min(a) FROM t")
    assert plain >= {"ast:agg:count", "ast:agg_trait:star", "ast:agg_trait:distinct", "ast:agg:min"}
    assert "ast:clause:distinct" not in plain and "ast:window_fn:aggregate" not in plain
    filtered = _ok("SELECT count(*) FILTER (WHERE a > 1) FROM t")
    assert filtered >= {"ast:agg:count", "ast:agg_trait:star", "ast:agg_trait:filter", "ast:cmp:gt"}
    assert "ast:clause:where" not in filtered
    ordered = _ok("SELECT string_agg(s, ',' ORDER BY a) FROM t")
    assert "ast:agg:other" in ordered and "ast:agg_trait:ordered" in ordered
    assert "ast:clause:order_by" not in ordered
    window = _ok("SELECT count(*) OVER () FROM t")
    assert window >= {"ast:window_fn:aggregate", "ast:window_spec:empty"}
    assert "ast:agg:count" not in window and "ast:agg_trait:star" not in window


def test_window_shape_and_the_other_function_leaf() -> None:
    dup = _ok("SELECT sum(v) OVER (PARTITION BY a + 1, a + 1) AS x, row_number() OVER () AS y FROM src")
    assert "ast:window_trait:dup_partition_key" in dup and "ast:window_trait:multiple" in dup
    single = _ok("SELECT sum(v) OVER (PARTITION BY a, b) FROM src")
    assert "ast:window_trait:dup_partition_key" not in single and "ast:window_trait:multiple" not in single
    frame = _ok("SELECT ntile(2 ORDER BY v) OVER (ORDER BY v ROWS BETWEEN 2 FOLLOWING AND 1 FOLLOWING) FROM t")
    assert frame >= {
        "ast:window_fn:ranking", "ast:window_trait:ordered_arg", "ast:window_frame:rows", "ast:window_frame:following",
    }
    assert "ast:window_frame:preceding" not in frame and "ast:clause:order_by" not in frame
    other = _ok("SELECT abs(a) OVER () FROM t")
    assert "ast:window_fn:other" in other and "ast:fn:abs" in other
    assert "ast:window_fn:aggregate" not in other and "ast:window_fn:ranking" not in other
    groups = _ok("SELECT sum(a) OVER (ORDER BY a GROUPS BETWEEN UNBOUNDED PRECEDING AND 1 FOLLOWING) FROM t")
    assert groups >= {"ast:window_frame:groups", "ast:window_frame:preceding", "ast:window_frame:following"}


def test_clauses_ignore_over_aggregate_order_and_count_distinct() -> None:
    query = _ok("SELECT DISTINCT a FROM t ORDER BY a LIMIT 3 OFFSET 1")
    assert query >= {"ast:clause:distinct", "ast:clause:order_by", "ast:clause:limit", "ast:clause:offset"}
    window = _ok("SELECT row_number() OVER (ORDER BY a) FROM t ORDER BY a")
    assert "ast:clause:order_by" in window and "ast:window_spec:order" in window
    only_over = _ok("SELECT row_number() OVER (ORDER BY a) FROM t")
    assert "ast:clause:order_by" not in only_over
    counted = _ok("SELECT count(DISTINCT a) FROM t")
    assert "ast:agg_trait:distinct" in counted and "ast:clause:distinct" not in counted
    inside = _ok("WITH c AS (SELECT a FROM t WHERE a > 1 ORDER BY a) SELECT * FROM c")
    assert inside >= {"ast:cte:plain", "ast:clause:where", "ast:clause:order_by", "ast:cmp:gt"}
    assert "ast:cte:recursive" not in inside


def test_predicates_and_expressions() -> None:
    compared = _ok("SELECT a FROM t WHERE a != 3")
    assert "ast:cmp:neq" in compared
    bounds = _ok("SELECT a FROM t WHERE a BETWEEN 1 AND 3 AND s ILIKE 'x%'")
    assert bounds >= {"ast:pred:between", "ast:pred:like", "ast:bool:and"}
    assert "ast:cmp:ge" not in bounds and "ast:cmp:le" not in bounds
    bare_between = _ok("SELECT a FROM t WHERE a BETWEEN 1 AND 3")
    assert "ast:bool:and" not in bare_between
    nulls = _ok("SELECT a FROM t WHERE a IS NULL OR b IS NOT NULL")
    assert nulls >= {"ast:pred:is_null", "ast:pred:is_not_null", "ast:bool:or"}
    assert "ast:bool:and" not in nulls
    arith = _ok("SELECT a + 1, -a, a % 2, s || 'x' FROM t")
    assert arith >= {"ast:expr:arith", "ast:expr:concat"}
    assert "ast:expr:date_arith" not in arith and "ast:expr:interval" not in arith
    dates = _ok("SELECT d + INTERVAL '1 day', d - INTERVAL '2 day' FROM t")
    assert dates >= {"ast:expr:arith", "ast:expr:interval", "ast:expr:date_arith"}
    names = _ok("SELECT upper(s), abs(a), my_func(a), substr(s, 1, 2), date_trunc('day', d) FROM t")
    assert names >= {"ast:fn:upper", "ast:fn:abs", "ast:fn:my_func", "ast:fn:substring", "ast:fn:timestamp_trunc"}
    assert "ast:fn:substr" not in names and "ast:fn:date_trunc" not in names and "ast:fn:and" not in names
    connectives = _ok("SELECT a FROM t WHERE a > 1 AND b < 2 OR c = 3")
    assert "ast:fn:and" not in connectives and "ast:fn:or" not in connectives
    forms = _ok("SELECT CASE WHEN a > 0 THEN coalesce(b, 0) ELSE nullif(a, b) END FROM t")
    assert forms >= {"ast:expr:case", "ast:expr:coalesce", "ast:expr:nullif"}
    assert "ast:fn:coalesce" not in forms and "ast:fn:nullif" not in forms
    cast = _ok("SELECT CAST(a AS VARCHAR), b::INT, TRY_CAST(s AS DOUBLE) FROM t")
    assert "ast:expr:cast" in cast and "ast:fn:cast" not in cast


def test_merge_when_clauses_record_match_kind_and_action() -> None:
    statement = _ok(
        "MERGE INTO t USING s ON t.a = s.a "
        "WHEN MATCHED THEN UPDATE SET b = s.b "
        "WHEN NOT MATCHED BY TARGET THEN INSERT VALUES (s.a, s.b) "
        "WHEN NOT MATCHED BY SOURCE THEN DELETE"
    )
    assert statement >= {
        "ast:stmt:merge", "ast:merge:matched", "ast:merge:not_matched", "ast:merge:not_matched_by_source",
        "ast:merge:update", "ast:merge:insert", "ast:merge:delete",
    }
    assert "ast:stmt:select" not in statement


def test_names_case_layout_and_comments_are_not_features() -> None:
    pairs = (
        ("SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.b = t.a)",
         "select x\n  from orders\n where exists (select 1 from items where items.y = orders.x) -- note\n;"),
        ("SELECT v FROM t EXCEPT ALL SELECT v FROM u",
         "SELECT col FROM left_tab /* bag */ EXCEPT ALL SELECT col FROM right_tab"),
        ("SELECT sum(v) OVER (PARTITION BY a, a, b) FROM src",
         "SELECT SUM(amount) OVER (PARTITION BY k1, k1, k2) FROM facts"),
    )
    for left, right in pairs:
        assert _ok(left) == _ok(right)


def test_fallback_is_honest_and_parsed_statements_are_not_marked() -> None:
    window, status = extract_ast(
        "SELECT id, {agg}(id) OVER (PARTITION BY ch ORDER BY id ROWS BETWEEN 1 FOLLOWING AND 2 FOLLOWING) "
        "FROM t1 ORDER BY 1",
        "duckdb",
    )
    assert status == "fallback"
    assert window >= {
        "ast:parse:fallback", "ast:window_spec:partition", "ast:window_spec:order", "ast:window_spec:frame",
        "ast:window_frame:rows", "ast:window_frame:following", "ast:clause:order_by",
    }
    assert "ast:agg:count" not in window and "ast:window_fn:aggregate" not in window
    joined, status = extract_ast(
        "SELECT * FROM J1_TBL JOIN J2_TBL USING (i) AS x WHERE J1_TBL.t = 'one'",
        "postgres",
    )
    assert status == "fallback"
    assert joined >= {"ast:parse:fallback", "ast:join:inner", "ast:join_cond:using", "ast:clause:where"}
    over_only, status = extract_ast("SELECT {agg}(id) OVER (ORDER BY id) FROM t", "duckdb")
    assert status == "fallback" and "ast:window_spec:order" in over_only and "ast:clause:order_by" not in over_only
    commented, status = extract_ast(
        "SELECT * FROM t JOIN u USING (i) AS x -- WHERE a = 1 OVER (ORDER BY a)",
        "duckdb",
    )
    assert status == "fallback"
    assert "ast:join:inner" in commented
    assert "ast:clause:where" not in commented and "ast:window_spec:order" not in commented
    several, status = extract_ast("SELECT a FROM t WHERE a > 1; SELECT b FROM u", "duckdb")
    assert status == "fallback" and "ast:parse:fallback" in several and "ast:clause:where" in several
    empty, status = extract_ast("   -- nothing\n", "duckdb")
    assert status == "fallback" and empty == frozenset({"ast:parse:fallback"})
    same, status = extract_ast("SELECT a FROM t;", "DuckDB")
    assert status == "ok" and same == _ok(PLAIN)
    for engine in ("duckdb", "datafusion", "postgres", "sqlite", "mysql"):
        features, status = extract_ast(PLAIN, engine)
        assert status == "ok" and "ast:stmt:select" in features and "ast:parse:fallback" not in features


def test_invented_regex_feature_is_emitted_only_after_acceptance() -> None:
    registry = default_registry()
    registry.register(FeatureDef(
        feature_id="ast:expr:gate_marker",
        kind="leaf",
        parent="ast:expr",
        layer="ast",
        description="mentions gate_marker",
        source="llm:vocabulary_inventor:test",
        definition={"kind": "regex", "pattern": r"\bgate_marker\b"},
        accepted=False,
        acceptance=None,
    ))
    marked = "SELECT gate_marker FROM t"
    assert "ast:expr:gate_marker" not in _ok(marked)
    pending, status = extract_ast(marked, "duckdb", registry=registry)
    assert status == "ok" and "ast:expr:gate_marker" not in pending
    registry.accept("ast:expr:gate_marker", {"decided_by": "test"})
    accepted, _status = extract_ast(marked, "duckdb", registry=registry)
    assert "ast:expr:gate_marker" in accepted
    other, _status = extract_ast(PLAIN, "duckdb", registry=registry)
    assert "ast:expr:gate_marker" not in other
    untouched, _status = extract_ast(marked, "duckdb")
    assert "ast:expr:gate_marker" not in untouched
    broken, status = extract_ast(
        "SELECT * FROM t JOIN u USING (i) AS x WHERE gate_marker = 1",
        "duckdb",
        registry=registry,
    )
    assert status == "fallback" and "ast:expr:gate_marker" in broken and "ast:parse:fallback" in broken


def test_known_families_are_pairwise_distinct() -> None:
    found: dict[str, frozenset[str]] = {}
    for family, (engine, sql, required) in FAMILIES.items():
        features, status = extract_ast(sql, engine)
        assert status == "ok", family
        missing = set(required) - features
        assert not missing, (family, sorted(missing))
        found[family] = features
    names = sorted(found)
    for index, left in enumerate(names):
        for right in names[index + 1:]:
            assert found[left] != found[right], (left, right)
    assert found["DF-A"] ^ found["DF-B"] == {"ast:set_op:except_all", "ast:set_op:intersect_all"}
