"""Statement-layer features from one sqlglot walk, with a regex fallback.

``extract_ast`` does not execute SQL and does not touch an engine. The same
text and engine always produce the same set.
"""
from __future__ import annotations

import re
from typing import Iterable

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.scope import Scope, build_scope, traverse_scope

from .registry import Registry, default_registry

_DIALECTS = {
    "duckdb": "duckdb",
    "datafusion": "postgres",
    "postgres": "postgres",
    "sqlite": "sqlite",
}

_RANKING = frozenset({"row_number", "rank", "dense_rank", "ntile", "percent_rank", "cume_dist"})
_NAVIGATION = frozenset({"lag", "lead", "first_value", "last_value", "nth_value"})
# Scalar calls that already have their own leaf, plus connectives sqlglot models as functions.
_FN_DENY = _RANKING | _NAVIGATION | frozenset({
    "and", "or", "not", "xor",
    "exists", "like", "ilike", "between", "in", "is",
    "coalesce", "nullif", "concat", "cast", "try_cast", "case",
    "all", "any", "some", "filter",
    "count", "sum", "avg", "min", "max",
})
_FN_NAME = re.compile(r"[a-z0-9_]+")
_NOT_SCALAR = tuple(
    kind
    for name in (
        "AggFunc", "And", "Or", "Not", "Xor", "Like", "ILike", "Between", "In",
        "Exists", "All", "Any", "Coalesce", "Nullif", "Concat", "Cast", "TryCast",
        "Filter", "Window", "If", "Is", "Case",
    )
    if isinstance(kind := getattr(exp, name, None), type)
)

_CMP_LEAF = {
    exp.EQ: "ast:cmp:eq",
    exp.NEQ: "ast:cmp:neq",
    exp.LT: "ast:cmp:lt",
    exp.LTE: "ast:cmp:le",
    exp.GT: "ast:cmp:gt",
    exp.GTE: "ast:cmp:ge",
}
_CORR_LEAF = {
    exp.EQ: "ast:corr_cmp:eq",
    exp.NEQ: "ast:corr_cmp:neq",
    exp.LT: "ast:corr_cmp:lt",
    exp.LTE: "ast:corr_cmp:le",
    exp.GT: "ast:corr_cmp:gt",
    exp.GTE: "ast:corr_cmp:ge",
}
_NON_EQUI = (exp.LT, exp.LTE, exp.GT, exp.GTE, exp.NEQ)
_QUERY = (exp.Select, exp.Union, exp.Except, exp.Intersect)
_SET_OP = {exp.Union: "union", exp.Except: "except", exp.Intersect: "intersect"}
_ARITH = (exp.Add, exp.Sub, exp.Mul, exp.Div, exp.Mod)
# Parentheses, sqlglot's parenthesized-query node, and LATERAL do not create a query.
_QUERY_WRAPPERS = (exp.Paren, exp.Subquery, exp.Lateral)
# FILTER and null-treatment wrap the call; the function inside is the one that matters.
_CALL_WRAPPERS = tuple(
    kind
    for kind in (exp.Filter, getattr(exp, "IgnoreNulls", None), getattr(exp, "RespectNulls", None))
    if isinstance(kind, type)
)

_COMMENT = re.compile(r"/\*.*?\*/|--[^\n]*", re.DOTALL)
_STRING = re.compile(r"'(?:''|[^'])*'")
_OVER = re.compile(r"\bover\s*\(", re.IGNORECASE)
_ORDER_BY = re.compile(r"\border\s+by\b", re.IGNORECASE)
_CTE_RECURSIVE = re.compile(
    r"\bwith\s+recursive\s+[A-Za-z_][A-Za-z0-9_]*\s*(?:\([^)]*\))?\s+as\s+(?:(?:not\s+)?materialized\s+)?\(",
    re.IGNORECASE,
)
_CTE_PLAIN = re.compile(
    r"\bwith\s+[A-Za-z_][A-Za-z0-9_]*\s*(?:\([^)]*\))?\s+as\s+(?:(?:not\s+)?materialized\s+)?\(",
    re.IGNORECASE,
)
_ONE_STATEMENT = re.compile(r";\s*\S")
_STATEMENT_WORD = re.compile(r"\s*(select|insert|update|delete|merge)\b", re.IGNORECASE)


def extract_ast(
    sql: str,
    engine: str,
    registry: Registry | None = None,
) -> tuple[frozenset[str], str]:
    """Return ``(ast leaves, "ok" | "fallback")`` for one statement."""
    active = default_registry() if registry is None else registry
    tree = _parse_one(sql, _dialect(engine))
    if tree is None:
        found = _fallback(sql)
        status = "fallback"
    else:
        found = _from_tree(tree)
        status = "ok"
    found.update(_invented(sql, active))
    return frozenset(_known_ast_leaves(found, active)), status


def _dialect(engine: str) -> str | None:
    if not isinstance(engine, str):
        return None
    return _DIALECTS.get(engine.casefold())


def _parse_one(sql: str, dialect: str | None) -> exp.Expression | None:
    """One statement, or None when sqlglot cannot read the text as exactly one."""
    try:
        trees = sqlglot.parse(sql, read=dialect)
    except Exception:
        return None
    statements = [tree for tree in trees if tree is not None]
    if len(statements) != 1:
        return None
    return statements[0]


def _known_ast_leaves(found: Iterable[str], registry: Registry) -> set[str]:
    kept: set[str] = set()
    for feature_id in found:
        if not registry.known(feature_id):
            continue
        definition = registry.get(feature_id)
        if definition.kind == "leaf" and definition.layer == "ast" and definition.accepted:
            kept.add(feature_id)
    return kept


def _invented(sql: str, registry: Registry) -> set[str]:
    found: set[str] = set()
    for feature_id in registry.ids():
        definition = registry.get(feature_id)
        if definition.source == "base" or not definition.accepted:
            continue
        body = definition.definition or {}
        if body.get("kind") != "regex":
            continue
        pattern = body.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, sql, re.IGNORECASE):
            found.add(feature_id)
    return found


def _from_tree(tree: exp.Expression) -> set[str]:
    found: set[str] = set()
    _statement(tree, found)
    _set_ops(tree, found)
    _joins(tree, found)
    _subqueries(tree, found)
    _aggregates(tree, found)
    _windows(tree, found)
    _clauses(tree, found)
    _predicates(tree, found)
    _expressions(tree, found)
    _functions(tree, found)
    _merge(tree, found)
    _correlation(tree, found)
    return found


def _statement(tree: exp.Expression, found: set[str]) -> None:
    if isinstance(tree, (*_QUERY, exp.Subquery)):
        found.add("ast:stmt:select")
    elif isinstance(tree, exp.Merge):
        found.add("ast:stmt:merge")
    elif isinstance(tree, exp.Insert):
        found.add("ast:stmt:insert")
    elif isinstance(tree, exp.Update):
        found.add("ast:stmt:update")
    elif isinstance(tree, exp.Delete):
        found.add("ast:stmt:delete")


def _set_ops(tree: exp.Expression, found: set[str]) -> None:
    for node in tree.find_all(*_SET_OP):
        name = _SET_OP[type(node)]
        if node.args.get("distinct") is False:
            found.add(f"ast:set_op:{name}_all")
        else:
            found.add(f"ast:set_op:{name}")


def _token(value: object) -> str:
    if isinstance(value, str):
        return value.casefold()
    return ""


def _joins(tree: exp.Expression, found: set[str]) -> None:
    for join in tree.find_all(exp.Join):
        method = _token(join.args.get("method"))
        side = _token(join.args.get("side"))
        kind = _token(join.args.get("kind"))
        has_on = join.args.get("on") is not None
        has_using = bool(join.args.get("using"))
        if method == "asof":
            found.add("ast:join:asof")
            _join_side(side, found)
        elif method == "natural":
            found.add("ast:join_cond:natural")
            if not _join_side(side, found):
                found.add("ast:join:inner")
        elif kind == "cross" or not (method or side or kind or has_on or has_using):
            found.add("ast:join:cross")
        elif not _join_side(side, found):
            found.add("ast:join:inner")
        if has_on:
            found.add("ast:join_cond:on")
        if has_using:
            found.add("ast:join_cond:using")
        if _on_is_non_equi(join):
            found.add("ast:join_trait:non_equi")
    if any(True for _ in tree.find_all(exp.Lateral)):
        found.add("ast:join_trait:lateral")
    if _self_table(tree):
        found.add("ast:join_trait:self")


def _join_side(side: str, found: set[str]) -> bool:
    leaf = {"left": "ast:join:left", "right": "ast:join:right", "full": "ast:join:full"}.get(side)
    if leaf is None:
        return False
    found.add(leaf)
    return True


def _on_is_non_equi(join: exp.Join) -> bool:
    condition = join.args.get("on")
    if not isinstance(condition, exp.Expression):
        return False
    owner = join.find_ancestor(*_QUERY)
    for cmp in condition.find_all(*_NON_EQUI):
        home = cmp.find_ancestor(*_QUERY)
        if home is owner:
            return True
    return False


def _self_table(tree: exp.Expression) -> bool:
    cte_names = {
        alias.casefold()
        for cte in tree.find_all(exp.CTE)
        if isinstance(alias := cte.alias_or_name, str) and alias
    }
    counts: dict[str, int] = {}
    for table in tree.find_all(exp.Table):
        if isinstance(table.this, exp.Func):
            continue
        name = table.name
        if not isinstance(name, str) or not name:
            continue
        key = f"{table.db}.{name}".casefold() if table.db else name.casefold()
        if key in cte_names or name.casefold() in cte_names:
            continue
        counts[key] = counts.get(key, 0) + 1
    return any(count >= 2 for count in counts.values())


def _is_negated(node: exp.Expression) -> bool:
    parent = node.parent
    while isinstance(parent, exp.Paren):
        parent = parent.parent
    return isinstance(parent, exp.Not)


def _role_parent(node: exp.Expression) -> tuple[exp.Expression | None, str | None]:
    """Parent that decides what a query is, after wrappers that do not add a query."""
    current = node
    while isinstance(current.parent, _QUERY_WRAPPERS):
        current = current.parent
    return current.parent, current.arg_key


def _is_excluded_query(node: exp.Expression) -> bool:
    """Top-level statement, set operand, CTE body, or INSERT / CREATE TABLE AS source."""
    parent, key = _role_parent(node)
    if parent is None:
        return True
    if isinstance(parent, (exp.Union, exp.Except, exp.Intersect)) and key in ("this", "expression"):
        return True
    if isinstance(parent, exp.CTE) and key == "this":
        return True
    if isinstance(parent, exp.Insert) and key == "expression":
        return True
    if isinstance(parent, exp.Create) and key == "expression" and _token(parent.args.get("kind")) == "table":
        return True
    return False


def _subquery_form(node: exp.Expression) -> str:
    parent, key = _role_parent(node)
    if isinstance(parent, exp.Exists):
        return "not_exists" if _is_negated(parent) else "exists"
    if isinstance(parent, exp.In) and key == "query":
        return "not_in" if _is_negated(parent) else "in"
    if isinstance(parent, exp.All):
        return "all"
    if isinstance(parent, exp.Any):
        return "any"
    if isinstance(parent, exp.From) or (isinstance(parent, exp.Join) and key == "this"):
        return "derived"
    return "scalar"


def _subquery_position(node: exp.Expression) -> str | None:
    current: exp.Expression | None = node
    while current is not None:
        parent = current.parent
        key = current.arg_key
        if isinstance(current, exp.Where) and not isinstance(parent, exp.Filter):
            return "where"
        if isinstance(current, exp.Having):
            return "having"
        if isinstance(parent, exp.Select) and key == "expressions":
            return "select"
        if isinstance(parent, exp.Join) and key == "on":
            return "on"
        if isinstance(parent, exp.From) or (isinstance(parent, exp.Join) and key == "this"):
            return "from"
        current = parent
    return None


def _add_subquery(found: set[str], kind: str, node: exp.Expression) -> None:
    found.add(f"ast:subquery:{kind}")
    position = _subquery_position(node)
    if position is not None:
        found.add(f"ast:subquery_pos:{position}")


def _subqueries(tree: exp.Expression, found: set[str]) -> None:
    for node in tree.find_all(exp.In):
        if node.args.get("query") is None and node.args.get("expressions"):
            found.add("ast:pred:in_list")
    for node in tree.find_all(*_QUERY):
        if _is_excluded_query(node):
            continue
        _add_subquery(found, _subquery_form(node), node)


def _unwrap_call(node: exp.Expression | None) -> exp.Expression | None:
    while isinstance(node, _CALL_WRAPPERS):
        node = node.this
    return node


def _is_windowed(func: exp.Expression) -> bool:
    parent = func.parent
    while isinstance(parent, _CALL_WRAPPERS):
        parent = parent.parent
    return isinstance(parent, exp.Window)


def _direct_order(func: exp.Expression) -> bool:
    """ORDER BY that belongs to ``func`` itself, not to a nested query."""
    for node in func.walk():
        if not isinstance(node, exp.Order):
            continue
        current: exp.Expression | None = node
        while current is not None and current is not func:
            if isinstance(current, (*_QUERY, exp.Subquery)):
                break
            current = current.parent
        if current is func:
            return True
    return False


def _agg_distinct(func: exp.AggFunc) -> bool:
    if isinstance(func.this, exp.Distinct):
        return True
    distinct = func.args.get("distinct")
    return isinstance(distinct, exp.Expression) or distinct is True


def _aggregates(tree: exp.Expression, found: set[str]) -> None:
    for func in tree.find_all(exp.AggFunc):
        if _is_windowed(func):
            continue
        if isinstance(func, exp.Count):
            found.add("ast:agg:count")
        elif isinstance(func, exp.Sum):
            found.add("ast:agg:sum")
        elif isinstance(func, exp.Avg):
            found.add("ast:agg:avg")
        elif isinstance(func, exp.Min):
            found.add("ast:agg:min")
        elif isinstance(func, exp.Max):
            found.add("ast:agg:max")
        else:
            found.add("ast:agg:other")
        if isinstance(func, exp.Count) and isinstance(func.this, exp.Star):
            found.add("ast:agg_trait:star")
        if _agg_distinct(func):
            found.add("ast:agg_trait:distinct")
        if isinstance(func.parent, exp.Filter):
            found.add("ast:agg_trait:filter")
        if _direct_order(func):
            found.add("ast:agg_trait:ordered")


def _call_name(node: exp.Expression) -> str:
    if isinstance(node, exp.Anonymous):
        name = node.name
        return name.casefold() if isinstance(name, str) else ""
    if isinstance(node, exp.Func):
        try:
            return node.sql_name().casefold()
        except AttributeError:
            return ""
    return ""


def _expr_dup(exprs: list[exp.Expression]) -> bool:
    for index, left in enumerate(exprs):
        for right in exprs[index + 1 :]:
            if left == right:
                return True
    return False


def _is_window_call(window: exp.Window) -> bool:
    # A WINDOW clause defines a name. Only `function OVER ...` is a call.
    return window.args.get("over") == "OVER"


def _window_alias(window: exp.Window) -> str:
    alias = window.args.get("alias")
    if isinstance(alias, exp.Identifier):
        name = alias.name
        return name.casefold() if isinstance(name, str) else ""
    if isinstance(alias, str):
        return alias.casefold()
    return ""


def _window_def(window: exp.Window, name: str) -> exp.Window | None:
    current = window.parent
    while current is not None:
        for definition in current.args.get("windows") or []:
            if not isinstance(definition, exp.Window):
                continue
            ident = definition.this
            if isinstance(ident, exp.Identifier) and isinstance(ident.name, str) and ident.name.casefold() == name:
                return definition
        current = current.parent
    return None


def _add_frame(spec: exp.WindowSpec, found: set[str]) -> None:
    found.add("ast:window_spec:frame")
    frame = _token(spec.args.get("kind"))
    leaf = {
        "rows": "ast:window_frame:rows",
        "range": "ast:window_frame:range",
        "groups": "ast:window_frame:groups",
    }.get(frame)
    if leaf is not None:
        found.add(leaf)
    for side_name in ("start_side", "end_side"):
        side = _token(spec.args.get(side_name))
        if side == "preceding":
            found.add("ast:window_frame:preceding")
        elif side == "following":
            found.add("ast:window_frame:following")


def _add_window_spec(window: exp.Window, found: set[str], *, allow_empty: bool) -> None:
    parts = [part for part in (window.args.get("partition_by") or []) if isinstance(part, exp.Expression)]
    order = window.args.get("order")
    spec = window.args.get("spec")
    if parts:
        found.add("ast:window_spec:partition")
        if _expr_dup(parts):
            found.add("ast:window_trait:dup_partition_key")
    if order is not None:
        found.add("ast:window_spec:order")
    if isinstance(spec, exp.WindowSpec):
        _add_frame(spec, found)
    if allow_empty and not parts and order is None and not isinstance(spec, exp.WindowSpec):
        found.add("ast:window_spec:empty")


def _windows(tree: exp.Expression, found: set[str]) -> None:
    calls = [window for window in tree.find_all(exp.Window) if _is_window_call(window)]
    if len(calls) >= 2:
        found.add("ast:window_trait:multiple")
    for window in calls:
        call = _unwrap_call(window.this)
        name = _call_name(call) if isinstance(call, exp.Expression) else ""
        # Some navigation functions are AggFunc subclasses; the written name decides.
        if name in _RANKING:
            found.add("ast:window_fn:ranking")
        elif name in _NAVIGATION:
            found.add("ast:window_fn:navigation")
        elif isinstance(call, exp.AggFunc):
            found.add("ast:window_fn:aggregate")
        else:
            found.add("ast:window_fn:other")
        alias = _window_alias(window)
        if alias:
            definition = _window_def(window, alias)
            # A name with no definition contributes no specification features.
            if definition is not None:
                _add_window_spec(definition, found, allow_empty=False)
                _add_window_spec(window, found, allow_empty=False)
        else:
            _add_window_spec(window, found, allow_empty=True)
        if isinstance(call, exp.Expression) and _direct_order(call):
            found.add("ast:window_trait:ordered_arg")


def _clauses(tree: exp.Expression, found: set[str]) -> None:
    for where in tree.find_all(exp.Where):
        if not isinstance(where.parent, exp.Filter):
            found.add("ast:clause:where")
    for order in tree.find_all(exp.Order):
        if isinstance(order.parent, _QUERY):
            found.add("ast:clause:order_by")
    for distinct in tree.find_all(exp.Distinct):
        if isinstance(distinct.parent, exp.Select):
            found.add("ast:clause:distinct")
    if any(True for _ in tree.find_all(exp.Limit)):
        found.add("ast:clause:limit")
    if any(True for _ in tree.find_all(exp.Offset)):
        found.add("ast:clause:offset")
    if any(True for _ in tree.find_all(exp.Qualify)):
        found.add("ast:clause:qualify")
    if any(True for _ in tree.find_all(exp.Group)):
        found.add("ast:group:by")
    if any(True for _ in tree.find_all(exp.Having)):
        found.add("ast:group:having")
    if any(True for _ in tree.find_all(exp.Rollup)):
        found.add("ast:group:rollup")
    if any(True for _ in tree.find_all(exp.Cube)):
        found.add("ast:group:cube")
    if any(True for _ in tree.find_all(exp.GroupingSets)):
        found.add("ast:group:grouping_sets")
    for cte in tree.find_all(exp.With):
        if cte.args.get("recursive"):
            found.add("ast:cte:recursive")
        else:
            found.add("ast:cte:plain")


def _is_assignment(node: exp.Expression) -> bool:
    """Top-level `=` of UPDATE SET, MERGE UPDATE SET, SET, or PRAGMA. Not a comparison."""
    parent = node.parent
    if isinstance(parent, exp.Update) and node.arg_key == "expressions":
        return True
    if isinstance(parent, exp.SetItem):
        return True
    return isinstance(parent, exp.Pragma)


def _predicates(tree: exp.Expression, found: set[str]) -> None:
    for kind, leaf in _CMP_LEAF.items():
        for node in tree.find_all(kind):
            if kind is exp.EQ and _is_assignment(node):
                continue
            found.add(leaf)
            break
    for node in tree.find_all(exp.Is):
        if not isinstance(node.args.get("expression"), exp.Null):
            continue
        if _is_negated(node):
            found.add("ast:pred:is_not_null")
        else:
            found.add("ast:pred:is_null")
    if any(True for _ in tree.find_all(exp.Between)):
        found.add("ast:pred:between")
    if any(True for _ in tree.find_all(exp.Like, exp.ILike)):
        found.add("ast:pred:like")
    if any(True for _ in tree.find_all(exp.And)):
        found.add("ast:bool:and")
    if any(True for _ in tree.find_all(exp.Or)):
        found.add("ast:bool:or")


def _operand_is_interval(node: exp.Expression | None) -> bool:
    while isinstance(node, exp.Paren):
        node = node.this
    return isinstance(node, exp.Interval)


def _expressions(tree: exp.Expression, found: set[str]) -> None:
    if any(True for _ in tree.find_all(exp.Case)):
        found.add("ast:expr:case")
    if any(True for _ in tree.find_all(exp.Coalesce)):
        found.add("ast:expr:coalesce")
    if any(True for _ in tree.find_all(exp.Nullif)):
        found.add("ast:expr:nullif")
    cast_types = tuple(kind for kind in (exp.Cast, getattr(exp, "TryCast", None)) if isinstance(kind, type))
    if any(True for _ in tree.find_all(*cast_types)):
        found.add("ast:expr:cast")
    concat_types = tuple(
        kind for kind in (getattr(exp, "DPipe", None), exp.Concat, getattr(exp, "SafeConcat", None))
        if isinstance(kind, type)
    )
    if any(True for _ in tree.find_all(*concat_types)):
        found.add("ast:expr:concat")
    if any(True for _ in tree.find_all(exp.Collate)):
        found.add("ast:expr:collate")
    if any(True for _ in tree.find_all(exp.Interval)):
        found.add("ast:expr:interval")
    for node in tree.find_all(*_ARITH):
        if node.args.get("expression") is None:
            continue
        found.add("ast:expr:arith")
        if isinstance(node, (exp.Add, exp.Sub)) and (
            _operand_is_interval(node.this) or _operand_is_interval(node.args.get("expression"))
        ):
            found.add("ast:expr:date_arith")


def _functions(tree: exp.Expression, found: set[str]) -> None:
    for node in tree.find_all(exp.Func):
        if isinstance(node, _NOT_SCALAR):
            continue
        name = _call_name(node)
        if name in _FN_DENY or not _FN_NAME.fullmatch(name or ""):
            continue
        found.add(f"ast:fn:{name}")


def _merge(tree: exp.Expression, found: set[str]) -> None:
    for when in tree.find_all(exp.When):
        if when.find_ancestor(exp.Merge) is None:
            continue
        if when.args.get("source") is True:
            found.add("ast:merge:not_matched_by_source")
        elif when.args.get("matched") is True:
            found.add("ast:merge:matched")
        else:
            found.add("ast:merge:not_matched")
        action = when.args.get("then")
        if isinstance(action, exp.Update):
            found.add("ast:merge:update")
        elif isinstance(action, exp.Insert):
            found.add("ast:merge:insert")
        elif isinstance(action, exp.Delete) or _var_name(action) == "delete":
            found.add("ast:merge:delete")
        elif _var_name(action) == "update":
            found.add("ast:merge:update")
        elif _var_name(action) == "insert":
            found.add("ast:merge:insert")


def _var_name(node: object) -> str:
    if not isinstance(node, exp.Var):
        return ""
    name = node.name if isinstance(node.name, str) else node.this
    return name.casefold() if isinstance(name, str) else ""


def _source_names(scope: Scope) -> set[str]:
    return {name.casefold() for name in scope.sources if isinstance(name, str) and name}


def _outer_names(scope: Scope, extra: set[str]) -> set[str]:
    names = set(extra)
    parent = scope.parent
    while parent is not None:
        names.update(_source_names(parent))
        parent = parent.parent
    return names


def _labels_under(node: object) -> set[str]:
    """Table names and aliases of a DML relation. Do not walk into a nested query."""
    if isinstance(node, exp.Table):
        labels: set[str] = set()
        if isinstance(node.name, str) and node.name:
            labels.add(node.name.casefold())
        alias = node.alias
        if isinstance(alias, str) and alias:
            labels.add(alias.casefold())
        for join in node.args.get("joins") or []:
            labels |= _labels_under(join)
        return labels
    if isinstance(node, exp.Join):
        return _labels_under(node.this)
    if isinstance(node, exp.From):
        labels = _labels_under(node.this)
        for join in node.args.get("joins") or []:
            labels |= _labels_under(join)
        return labels
    if isinstance(node, exp.Lateral):
        return _labels_under(node.this)
    if isinstance(node, exp.Subquery):
        labels = set()
        alias = node.alias
        if isinstance(alias, str) and alias:
            labels.add(alias.casefold())
        for join in node.args.get("joins") or []:
            labels |= _labels_under(join)
        return labels
    return set()


def _dml_names(tree: exp.Expression) -> set[str]:
    """Relations of UPDATE / DELETE / MERGE. The target of INSERT or CTAS is not outer."""
    if isinstance(tree, exp.Delete):
        names = _labels_under(tree.this)
        for item in tree.args.get("using") or []:
            names |= _labels_under(item)
        return names
    if isinstance(tree, exp.Update):
        names = _labels_under(tree.this)
        source = tree.args.get("from_")
        if isinstance(source, exp.Expression):
            names |= _labels_under(source)
        return names
    if isinstance(tree, exp.Merge):
        names = _labels_under(tree.this)
        using = tree.args.get("using")
        if isinstance(using, exp.Expression):
            names |= _labels_under(using)
        elif isinstance(using, list):
            for item in using:
                names |= _labels_under(item)
        return names
    return set()


def _outermost_queries(tree: exp.Expression) -> list[exp.Expression]:
    return [node for node in tree.find_all(*_QUERY) if node.find_ancestor(*_QUERY) is None]


def _bare_column(node: exp.Expression | None) -> exp.Column | None:
    while isinstance(node, exp.Paren):
        node = node.this
    if isinstance(node, exp.Column):
        return node
    return None


def _qualifier(column: exp.Column) -> str:
    table = column.text("table")
    return table.casefold() if isinstance(table, str) else ""


def _correlation(tree: exp.Expression, found: set[str]) -> None:
    # Scope building is not part of parsing. A failure here leaves the statement
    # parsed and simply records no correlation, instead of flipping it to fallback.
    extra = _dml_names(tree)
    try:
        if build_scope(tree) is None:
            # UPDATE / DELETE / MERGE are not queries. Scope each nested query on its own.
            scopes: list[Scope] = []
            apart = True
            for query in _outermost_queries(tree):
                try:
                    if build_scope(query) is None:
                        continue
                    scopes.extend(traverse_scope(query))
                except Exception:
                    continue
        else:
            scopes = list(traverse_scope(tree))
            apart = False
    except Exception:
        return
    by_expression = {id(scope.expression): scope for scope in scopes}
    correlated = False
    for scope in scopes:
        if scope.parent is None and not apart:
            continue
        outer = set(extra) if scope.parent is None else _outer_names(scope, extra)
        if any(_qualifier(column) in outer for column in scope.external_columns):
            correlated = True
    if correlated:
        found.add("ast:subquery_trait:correlated")
    for kind, leaf in _CORR_LEAF.items():
        for cmp in tree.find_all(kind):
            scope = _scope_of(cmp, by_expression)
            if scope is None or (scope.parent is None and not apart):
                continue
            left = _bare_column(cmp.this)
            right = _bare_column(cmp.expression)
            if left is None or right is None:
                continue
            local = _source_names(scope)
            outer = set(extra) if scope.parent is None else _outer_names(scope, extra)
            left_name = _qualifier(left)
            right_name = _qualifier(right)
            # A qualifier this scope defines is local, even when an outer scope uses it too.
            left_local = bool(left_name) and left_name in local
            right_local = bool(right_name) and right_name in local
            left_outer = bool(left_name) and left_name in outer and left_name not in local
            right_outer = bool(right_name) and right_name in outer and right_name not in local
            if (left_local and right_outer) or (right_local and left_outer):
                found.add(leaf)


def _scope_of(node: exp.Expression, by_expression: dict[int, Scope]) -> Scope | None:
    current: exp.Expression | None = node
    while current is not None:
        scope = by_expression.get(id(current))
        if scope is not None:
            return scope
        current = current.parent
    return None


def _mask(sql: str) -> str:
    blank = _COMMENT.sub(" ", sql)
    return _STRING.sub("''", blank)


def _balanced(text: str, open_at: int) -> int | None:
    depth = 0
    for index in range(open_at, len(text)):
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _strip_over(text: str) -> str:
    parts: list[str] = []
    cursor = 0
    for match in _OVER.finditer(text):
        open_at = match.end() - 1
        close_at = _balanced(text, open_at)
        if close_at is None:
            continue
        parts.append(text[cursor:match.start()])
        cursor = close_at + 1
    parts.append(text[cursor:])
    return "".join(parts)


def _has_query_order_by(text: str) -> bool:
    stack: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "(":
            look = index - 1
            while look >= 0 and text[look].isspace():
                look -= 1
            stack.append("func" if look >= 0 and (text[look].isalnum() or text[look] == "_") else "other")
            index += 1
            continue
        if char == ")":
            if stack:
                stack.pop()
            index += 1
            continue
        if _ORDER_BY.match(text, index) and "func" not in stack:
            return True
        index += 1
    return False


def _window_name(prefix: str) -> str:
    match = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\s*(\((?:[^()]|\([^()]*\))*\))?\s*$", prefix)
    if match is None:
        return ""
    return match.group(1).casefold()


def _fallback(sql: str) -> set[str]:
    found = {"ast:parse:fallback"}
    masked = _mask(sql)
    _fallback_windows(masked, found)
    _fallback_joins(masked, found)
    _fallback_statement(masked, found)
    without_filter = re.sub(r"\bfilter\s*\(\s*where\b", " ", masked, flags=re.IGNORECASE)
    if re.search(r"\bwhere\b", without_filter, re.IGNORECASE):
        found.add("ast:clause:where")
    if _has_query_order_by(_strip_over(masked)):
        found.add("ast:clause:order_by")
    _fallback_keywords(masked, found)
    return found


def _fallback_windows(masked: str, found: set[str]) -> None:
    count = 0
    for match in _OVER.finditer(masked):
        open_at = match.end() - 1
        close_at = _balanced(masked, open_at)
        if close_at is None:
            continue
        count += 1
        body = masked[open_at + 1:close_at]
        if not body.strip():
            found.add("ast:window_spec:empty")
        if re.search(r"\bpartition\s+by\b", body, re.IGNORECASE):
            found.add("ast:window_spec:partition")
        if re.search(r"\border\s+by\b", body, re.IGNORECASE):
            found.add("ast:window_spec:order")
        if re.search(r"\b(rows|range|groups)\b", body, re.IGNORECASE):
            found.add("ast:window_spec:frame")
        for word, leaf in (
            ("rows", "ast:window_frame:rows"),
            ("range", "ast:window_frame:range"),
            ("groups", "ast:window_frame:groups"),
        ):
            if re.search(rf"\b{word}\b", body, re.IGNORECASE):
                found.add(leaf)
        if re.search(r"\bpreceding\b", body, re.IGNORECASE):
            found.add("ast:window_frame:preceding")
        if re.search(r"\bfollowing\b", body, re.IGNORECASE):
            found.add("ast:window_frame:following")
        name = _window_name(masked[:match.start()])
        if name in _RANKING:
            found.add("ast:window_fn:ranking")
        elif name in _NAVIGATION:
            found.add("ast:window_fn:navigation")
        elif name in {"count", "sum", "avg", "min", "max", "string_agg", "array_agg", "stddev", "variance"}:
            found.add("ast:window_fn:aggregate")
    if count >= 2:
        found.add("ast:window_trait:multiple")


def _fallback_statement(masked: str, found: set[str]) -> None:
    """One statement whose first word is a known kind. WITH, parentheses, and multi-statement text stay unguessed."""
    if _ONE_STATEMENT.search(masked):
        return
    match = _STATEMENT_WORD.match(masked)
    if match:
        found.add(f"ast:stmt:{match.group(1).casefold()}")


def _consume(pattern: str, leaf: str, text: str, found: set[str]) -> str:
    if re.search(pattern, text, re.IGNORECASE):
        found.add(leaf)
        return re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return text


def _fallback_joins(masked: str, found: set[str]) -> None:
    text = masked
    text = _consume(r"\basof\s+left\s+(?:outer\s+)?join\b", "ast:join:asof", text, found)
    if "ast:join:asof" in found and re.search(r"\basof\s+left\b", masked, re.IGNORECASE):
        found.add("ast:join:left")
    text = _consume(r"\basof\s+right\s+(?:outer\s+)?join\b", "ast:join:asof", text, found)
    if re.search(r"\basof\s+right\b", masked, re.IGNORECASE):
        found.add("ast:join:right")
    text = _consume(r"\basof\s+join\b", "ast:join:asof", text, found)
    if re.search(r"\bnatural\s+(?:inner\s+|left\s+|right\s+|full\s+)?join\b", masked, re.IGNORECASE):
        found.add("ast:join_cond:natural")
        if re.search(r"\bnatural\s+left\b", masked, re.IGNORECASE):
            found.add("ast:join:left")
        elif re.search(r"\bnatural\s+right\b", masked, re.IGNORECASE):
            found.add("ast:join:right")
        elif re.search(r"\bnatural\s+full\b", masked, re.IGNORECASE):
            found.add("ast:join:full")
        else:
            found.add("ast:join:inner")
    text = _consume(r"\bnatural\s+(?:inner\s+|left\s+|right\s+|full\s+)?join\b", "ast:join_cond:natural", text, found)
    text = _consume(r"\bleft\s+(?:outer\s+)?join\b", "ast:join:left", text, found)
    text = _consume(r"\bright\s+(?:outer\s+)?join\b", "ast:join:right", text, found)
    text = _consume(r"\bfull\s+(?:outer\s+)?join\b", "ast:join:full", text, found)
    text = _consume(r"\bcross\s+join\b", "ast:join:cross", text, found)
    text = _consume(r"\binner\s+join\b", "ast:join:inner", text, found)
    if re.search(r"\bjoin\b", text, re.IGNORECASE):
        found.add("ast:join:inner")
    if re.search(r"\bjoin\b", masked, re.IGNORECASE) and re.search(r"\busing\s*\(", masked, re.IGNORECASE):
        found.add("ast:join_cond:using")


def _fallback_keywords(masked: str, found: set[str]) -> None:
    text = masked
    for pattern, leaf in (
        (r"\bunion\s+all\b", "ast:set_op:union_all"),
        (r"\bexcept\s+all\b", "ast:set_op:except_all"),
        (r"\bintersect\s+all\b", "ast:set_op:intersect_all"),
    ):
        text = _consume(pattern, leaf, text, found)
    for pattern, leaf in (
        (r"\bunion\b", "ast:set_op:union"),
        (r"\bexcept\b", "ast:set_op:except"),
        (r"\bintersect\b", "ast:set_op:intersect"),
    ):
        text = _consume(pattern, leaf, text, found)
    if re.search(r"\bnot\s+exists\b", masked, re.IGNORECASE):
        found.add("ast:subquery:not_exists")
    exists_rest = re.sub(r"\bnot\s+exists\b", " ", masked, flags=re.IGNORECASE)
    if re.search(r"\bexists\b", exists_rest, re.IGNORECASE):
        found.add("ast:subquery:exists")
    if re.search(r"\bselect\s+distinct\b", masked, re.IGNORECASE):
        found.add("ast:clause:distinct")
    if re.search(r"\bgroup\s+by\b", masked, re.IGNORECASE):
        found.add("ast:group:by")
    if re.search(r"\bhaving\b", masked, re.IGNORECASE):
        found.add("ast:group:having")
    if re.search(r"\blimit\b", masked, re.IGNORECASE):
        found.add("ast:clause:limit")
    if re.search(r"\boffset\b", masked, re.IGNORECASE):
        found.add("ast:clause:offset")
    if re.search(r"\bqualify\b", masked, re.IGNORECASE):
        found.add("ast:clause:qualify")
    if _CTE_RECURSIVE.search(masked):
        found.add("ast:cte:recursive")
    if _CTE_PLAIN.search(_CTE_RECURSIVE.sub(" ", masked)):
        found.add("ast:cte:plain")
    if re.search(r"\bis\s+not\s+null\b", masked, re.IGNORECASE):
        found.add("ast:pred:is_not_null")
    null_rest = re.sub(r"\bis\s+not\s+null\b", " ", masked, flags=re.IGNORECASE)
    if re.search(r"\bis\s+null\b", null_rest, re.IGNORECASE):
        found.add("ast:pred:is_null")
    # A frame's BETWEEN is not the predicate. Judge it only outside OVER (...).
    if re.search(r"\bbetween\b", _strip_over(masked), re.IGNORECASE):
        found.add("ast:pred:between")
    if re.search(r"\b(like|ilike)\b", masked, re.IGNORECASE):
        found.add("ast:pred:like")
    if re.search(r"\bcase\b", masked, re.IGNORECASE):
        found.add("ast:expr:case")
    if re.search(r"\bcoalesce\s*\(", masked, re.IGNORECASE):
        found.add("ast:expr:coalesce")
    if re.search(r"\binterval\b", masked, re.IGNORECASE):
        found.add("ast:expr:interval")
