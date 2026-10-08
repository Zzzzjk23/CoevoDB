"""Feature identifiers, kinds, and the frozen FeatureDef record."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

LAYERS = ("ast", "plan", "data")
KINDS = ("class", "leaf", "family")
FEATURE_ID_RE = re.compile(r"(?:ast|plan|data)(?::[A-Za-z0-9_]+)*")


def is_feature_id(feature_id: str) -> bool:
    return isinstance(feature_id, str) and bool(FEATURE_ID_RE.fullmatch(feature_id))


def layer_of(feature_id: str) -> str:
    return feature_id.split(":", 1)[0]


@dataclass(frozen=True)
class FeatureDef:
    """One vocabulary entry: a class, a leaf, or an open family."""

    feature_id: str
    kind: str
    parent: str | None
    layer: str
    description: str
    source: str
    definition: dict[str, Any] | None
    accepted: bool
    acceptance: dict[str, Any] | None

    def __post_init__(self) -> None:
        if isinstance(self.definition, dict):
            object.__setattr__(self, "definition", dict(self.definition))
        if isinstance(self.acceptance, dict):
            object.__setattr__(self, "acceptance", dict(self.acceptance))

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "kind": self.kind,
            "parent": self.parent,
            "layer": self.layer,
            "description": self.description,
            "source": self.source,
            "definition": None if self.definition is None else dict(self.definition),
            "accepted": self.accepted,
            "acceptance": None if self.acceptance is None else dict(self.acceptance),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeatureDef:
        definition = data.get("definition")
        acceptance = data.get("acceptance")
        return cls(
            feature_id=data["feature_id"],
            kind=data["kind"],
            parent=data["parent"],
            layer=data["layer"],
            description=data["description"],
            source=data["source"],
            definition=None if definition is None else dict(definition),
            accepted=data["accepted"],
            acceptance=None if acceptance is None else dict(acceptance),
        )


def _base(feature_id: str, kind: str, parent: str | None, description: str) -> FeatureDef:
    return FeatureDef(
        feature_id=feature_id,
        kind=kind,
        parent=parent,
        layer=layer_of(feature_id),
        description=description,
        source="base",
        definition=None,
        accepted=True,
        acceptance=None,
    )


# Copied from the S5 contract (ids, kinds, parents). Descriptions are local.
_BASE_ROWS: tuple[tuple[str, str, str | None, str], ...] = (
    ('ast', 'class', None, 'What the statement text says.'),
    ('plan', 'family', None, "Physical operators of the target engine's plan, named as the engine prints them."),
    ('data', 'class', None, 'Properties of the data the statement runs on, computed on the database.'),
    ('ast:stmt', 'class', 'ast', 'Kind of the top-level statement.'),
    ('ast:stmt:select', 'leaf', 'ast:stmt', 'A query, including a set operation of queries.'),
    ('ast:stmt:merge', 'leaf', 'ast:stmt', 'MERGE.'),
    ('ast:stmt:insert', 'leaf', 'ast:stmt', 'INSERT.'),
    ('ast:stmt:update', 'leaf', 'ast:stmt', 'UPDATE.'),
    ('ast:stmt:delete', 'leaf', 'ast:stmt', 'DELETE.'),
    ('ast:set_op', 'class', 'ast', 'A set operation.'),
    ('ast:set_op:all', 'class', 'ast:set_op', 'Bag semantics: the ALL variants.'),
    ('ast:set_op:union_all', 'leaf', 'ast:set_op:all', 'UNION ALL.'),
    ('ast:set_op:except_all', 'leaf', 'ast:set_op:all', 'EXCEPT ALL.'),
    ('ast:set_op:intersect_all', 'leaf', 'ast:set_op:all', 'INTERSECT ALL.'),
    ('ast:set_op:distinct', 'class', 'ast:set_op', 'Set semantics.'),
    ('ast:set_op:union', 'leaf', 'ast:set_op:distinct', 'UNION without ALL.'),
    ('ast:set_op:except', 'leaf', 'ast:set_op:distinct', 'EXCEPT without ALL.'),
    ('ast:set_op:intersect', 'leaf', 'ast:set_op:distinct', 'INTERSECT without ALL.'),
    ('ast:join', 'class', 'ast', 'A join between two relations.'),
    ('ast:join:inner', 'leaf', 'ast:join', 'JOIN / INNER JOIN with a condition, and NATURAL JOIN.'),
    ('ast:join:left', 'leaf', 'ast:join', 'LEFT [OUTER] JOIN.'),
    ('ast:join:right', 'leaf', 'ast:join', 'RIGHT [OUTER] JOIN.'),
    ('ast:join:full', 'leaf', 'ast:join', 'FULL [OUTER] JOIN.'),
    ('ast:join:cross', 'leaf', 'ast:join', 'CROSS JOIN, or two relations separated by a comma.'),
    ('ast:join:asof', 'leaf', 'ast:join', 'ASOF JOIN (with its side as well, when one is written).'),
    ('ast:join_cond', 'class', 'ast', 'How a join states its condition.'),
    ('ast:join_cond:on', 'leaf', 'ast:join_cond', 'ON.'),
    ('ast:join_cond:using', 'leaf', 'ast:join_cond', 'USING.'),
    ('ast:join_cond:natural', 'leaf', 'ast:join_cond', 'NATURAL.'),
    ('ast:join_trait', 'class', 'ast', 'Properties of the joined relations.'),
    ('ast:join_trait:self', 'leaf', 'ast:join_trait', 'The same base table is referenced two or more times in the statement.'),
    ('ast:join_trait:non_equi', 'leaf', 'ast:join_trait', 'A join ON condition compares with <, <=, >, >= or <>.'),
    ('ast:join_trait:lateral', 'leaf', 'ast:join_trait', 'The LATERAL keyword.'),
    ('ast:subquery', 'class', 'ast', 'A nested query.'),
    ('ast:subquery:exists', 'leaf', 'ast:subquery', 'EXISTS (...) that is not negated.'),
    ('ast:subquery:not_exists', 'leaf', 'ast:subquery', 'NOT EXISTS (...).'),
    ('ast:subquery:in', 'leaf', 'ast:subquery', 'Expr IN (SELECT ...) that is not negated.'),
    ('ast:subquery:not_in', 'leaf', 'ast:subquery', 'Expr NOT IN (SELECT ...).'),
    ('ast:subquery:scalar', 'leaf', 'ast:subquery', 'A parenthesised query used as a value.'),
    ('ast:subquery:all', 'leaf', 'ast:subquery', 'Comparison with ALL (SELECT ...).'),
    ('ast:subquery:any', 'leaf', 'ast:subquery', 'Comparison with ANY or SOME (SELECT ...).'),
    ('ast:subquery:derived', 'leaf', 'ast:subquery', 'A query in FROM or JOIN used as a table.'),
    ('ast:subquery_pos', 'class', 'ast', 'The clause of the enclosing query that holds a subquery.'),
    ('ast:subquery_pos:select', 'leaf', 'ast:subquery_pos', 'The select list.'),
    ('ast:subquery_pos:where', 'leaf', 'ast:subquery_pos', 'WHERE.'),
    ('ast:subquery_pos:from', 'leaf', 'ast:subquery_pos', 'FROM or a joined relation.'),
    ('ast:subquery_pos:having', 'leaf', 'ast:subquery_pos', 'HAVING.'),
    ('ast:subquery_pos:on', 'leaf', 'ast:subquery_pos', 'A join ON condition.'),
    ('ast:subquery_trait', 'class', 'ast', 'Properties of a subquery.'),
    ('ast:subquery_trait:correlated', 'leaf', 'ast:subquery_trait', 'It references a qualified column of an enclosing query.'),
    ('ast:corr_cmp', 'class', 'ast', 'Comparison, inside a correlated subquery, between an inner column and an outer column.'),
    ('ast:corr_cmp:eq', 'leaf', 'ast:corr_cmp', '=.'),
    ('ast:corr_cmp:neq', 'leaf', 'ast:corr_cmp', '<> or !=.'),
    ('ast:corr_cmp:lt', 'leaf', 'ast:corr_cmp', '< as written.'),
    ('ast:corr_cmp:le', 'leaf', 'ast:corr_cmp', '<= as written.'),
    ('ast:corr_cmp:gt', 'leaf', 'ast:corr_cmp', '> as written.'),
    ('ast:corr_cmp:ge', 'leaf', 'ast:corr_cmp', '>= as written.'),
    ('ast:agg', 'class', 'ast', 'An aggregate function call without OVER.'),
    ('ast:agg:count', 'leaf', 'ast:agg', 'COUNT.'),
    ('ast:agg:sum', 'leaf', 'ast:agg', 'SUM.'),
    ('ast:agg:avg', 'leaf', 'ast:agg', 'AVG.'),
    ('ast:agg:min', 'leaf', 'ast:agg', 'MIN.'),
    ('ast:agg:max', 'leaf', 'ast:agg', 'MAX.'),
    ('ast:agg:other', 'leaf', 'ast:agg', 'Any other aggregate.'),
    ('ast:agg_trait', 'class', 'ast', 'How an aggregate is called.'),
    ('ast:agg_trait:star', 'leaf', 'ast:agg_trait', 'COUNT(*).'),
    ('ast:agg_trait:distinct', 'leaf', 'ast:agg_trait', 'DISTINCT inside the call.'),
    ('ast:agg_trait:filter', 'leaf', 'ast:agg_trait', 'FILTER (WHERE ...).'),
    ('ast:agg_trait:ordered', 'leaf', 'ast:agg_trait', 'ORDER BY inside the call.'),
    ('ast:group', 'class', 'ast', 'Grouping clauses.'),
    ('ast:group:by', 'leaf', 'ast:group', 'GROUP BY.'),
    ('ast:group:having', 'leaf', 'ast:group', 'HAVING.'),
    ('ast:group:rollup', 'leaf', 'ast:group', 'ROLLUP.'),
    ('ast:group:cube', 'leaf', 'ast:group', 'CUBE.'),
    ('ast:group:grouping_sets', 'leaf', 'ast:group', 'GROUPING SETS.'),
    ('ast:window', 'class', 'ast', 'A function call with OVER.'),
    ('ast:window_fn', 'class', 'ast:window', 'Which kind of function is windowed.'),
    ('ast:window_fn:ranking', 'leaf', 'ast:window_fn', 'Row_number, rank, dense_rank, ntile, percent_rank, cume_dist.'),
    ('ast:window_fn:navigation', 'leaf', 'ast:window_fn', 'Lag, lead, first_value, last_value, nth_value.'),
    ('ast:window_fn:aggregate', 'leaf', 'ast:window_fn', 'An aggregate function with OVER.'),
    ('ast:window_spec', 'class', 'ast:window', 'What the OVER clause contains.'),
    ('ast:window_spec:partition', 'leaf', 'ast:window_spec', 'PARTITION BY.'),
    ('ast:window_spec:order', 'leaf', 'ast:window_spec', 'ORDER BY inside OVER.'),
    ('ast:window_spec:frame', 'leaf', 'ast:window_spec', 'An explicit frame.'),
    ('ast:window_spec:empty', 'leaf', 'ast:window_spec', 'OVER ().'),
    ('ast:window_frame', 'class', 'ast:window', 'Shape of an explicit frame.'),
    ('ast:window_frame:rows', 'leaf', 'ast:window_frame', 'ROWS.'),
    ('ast:window_frame:range', 'leaf', 'ast:window_frame', 'RANGE.'),
    ('ast:window_frame:groups', 'leaf', 'ast:window_frame', 'GROUPS.'),
    ('ast:window_frame:preceding', 'leaf', 'ast:window_frame', 'A PRECEDING bound, UNBOUNDED included.'),
    ('ast:window_frame:following', 'leaf', 'ast:window_frame', 'A FOLLOWING bound, UNBOUNDED included.'),
    ('ast:window_trait', 'class', 'ast:window', 'Other properties of window calls.'),
    ('ast:window_trait:dup_partition_key', 'leaf', 'ast:window_trait', 'One PARTITION BY list names the same expression twice.'),
    ('ast:window_trait:multiple', 'leaf', 'ast:window_trait', 'Two or more window calls in the statement.'),
    ('ast:window_trait:ordered_arg', 'leaf', 'ast:window_trait', 'ORDER BY inside the argument list of the windowed function.'),
    ('ast:clause', 'class', 'ast', 'Clauses of a query.'),
    ('ast:clause:where', 'leaf', 'ast:clause', 'WHERE.'),
    ('ast:clause:distinct', 'leaf', 'ast:clause', 'SELECT DISTINCT.'),
    ('ast:clause:order_by', 'leaf', 'ast:clause', 'ORDER BY of a query (not of OVER, not of an aggregate call).'),
    ('ast:clause:limit', 'leaf', 'ast:clause', 'LIMIT.'),
    ('ast:clause:offset', 'leaf', 'ast:clause', 'OFFSET.'),
    ('ast:clause:qualify', 'leaf', 'ast:clause', 'QUALIFY.'),
    ('ast:cte', 'class', 'ast', 'WITH.'),
    ('ast:cte:plain', 'leaf', 'ast:cte', 'WITH without RECURSIVE.'),
    ('ast:cte:recursive', 'leaf', 'ast:cte', 'WITH RECURSIVE.'),
    ('ast:cmp', 'class', 'ast', 'Comparison operators.'),
    ('ast:cmp:eq', 'leaf', 'ast:cmp', '=.'),
    ('ast:cmp:neq', 'leaf', 'ast:cmp', '<> or !=.'),
    ('ast:cmp:lt', 'leaf', 'ast:cmp', '<.'),
    ('ast:cmp:le', 'leaf', 'ast:cmp', '<=.'),
    ('ast:cmp:gt', 'leaf', 'ast:cmp', '>.'),
    ('ast:cmp:ge', 'leaf', 'ast:cmp', '>=.'),
    ('ast:pred', 'class', 'ast', 'Other predicates.'),
    ('ast:pred:is_null', 'leaf', 'ast:pred', 'IS NULL.'),
    ('ast:pred:is_not_null', 'leaf', 'ast:pred', 'IS NOT NULL.'),
    ('ast:pred:between', 'leaf', 'ast:pred', 'BETWEEN.'),
    ('ast:pred:like', 'leaf', 'ast:pred', 'LIKE or ILIKE.'),
    ('ast:pred:in_list', 'leaf', 'ast:pred', 'IN with a list of values.'),
    ('ast:bool', 'class', 'ast', 'Boolean connectives.'),
    ('ast:bool:and', 'leaf', 'ast:bool', 'AND.'),
    ('ast:bool:or', 'leaf', 'ast:bool', 'OR.'),
    ('ast:expr', 'class', 'ast', 'Expression forms.'),
    ('ast:expr:case', 'leaf', 'ast:expr', 'CASE.'),
    ('ast:expr:coalesce', 'leaf', 'ast:expr', 'COALESCE.'),
    ('ast:expr:nullif', 'leaf', 'ast:expr', 'NULLIF.'),
    ('ast:expr:cast', 'leaf', 'ast:expr', 'CAST, TRY_CAST or ::.'),
    ('ast:expr:arith', 'leaf', 'ast:expr', 'Binary +, -, *, / or %.'),
    ('ast:expr:concat', 'leaf', 'ast:expr', '|| or CONCAT.'),
    ('ast:expr:collate', 'leaf', 'ast:expr', 'COLLATE.'),
    ('ast:expr:interval', 'leaf', 'ast:expr', 'An INTERVAL literal.'),
    ('ast:expr:date_arith', 'leaf', 'ast:expr', '+ or - with an INTERVAL literal as one operand.'),
    ('ast:fn', 'family', 'ast', 'Scalar function calls: ast:fn:<name>, the lower-cased sqlglot name of the function.'),
    ('ast:merge', 'class', 'ast', 'Clauses of MERGE.'),
    ('ast:merge:matched', 'leaf', 'ast:merge', 'WHEN MATCHED.'),
    ('ast:merge:not_matched', 'leaf', 'ast:merge', 'WHEN NOT MATCHED [BY TARGET].'),
    ('ast:merge:not_matched_by_source', 'leaf', 'ast:merge', 'WHEN NOT MATCHED BY SOURCE.'),
    ('ast:merge:update', 'leaf', 'ast:merge', 'THEN UPDATE.'),
    ('ast:merge:delete', 'leaf', 'ast:merge', 'THEN DELETE.'),
    ('ast:merge:insert', 'leaf', 'ast:merge', 'THEN INSERT.'),
    ('ast:parse', 'class', 'ast', 'How the text was read.'),
    ('ast:parse:fallback', 'leaf', 'ast:parse', 'Sqlglot could not parse it; the ast features come from regular expressions.'),
    ('data:table', 'class', 'data', 'Shape of the referenced base tables.'),
    ('data:table:empty', 'leaf', 'data:table', 'Some referenced table has no rows.'),
    ('data:table:single_row', 'leaf', 'data:table', 'Some referenced table has exactly one row.'),
    ('data:table:dup_rows', 'leaf', 'data:table', 'Some referenced table holds two identical rows.'),
    ('data:table:has_null', 'leaf', 'data:table', 'Some referenced table holds a NULL.'),
    ('data:value', 'class', 'data', 'Corner-case values in the referenced tables.'),
    ('data:value:zero', 'leaf', 'data:value', 'A numeric zero.'),
    ('data:value:negative', 'leaf', 'data:value', 'A negative number.'),
    ('data:value:extreme_number', 'leaf', 'data:value', 'A number whose absolute value is at least 2**31.'),
    ('data:value:empty_string', 'leaf', 'data:value', 'An empty string.'),
    ('data:value:non_finite', 'leaf', 'data:value', 'NaN or an infinity.'),
    ('data:type', 'class', 'data', 'Column types of the referenced tables.'),
    ('data:type:integer', 'leaf', 'data:type', 'An integer type.'),
    ('data:type:float', 'leaf', 'data:type', 'REAL, FLOAT or DOUBLE.'),
    ('data:type:decimal', 'leaf', 'data:type', 'DECIMAL or NUMERIC.'),
    ('data:type:string', 'leaf', 'data:type', 'A character type.'),
    ('data:type:boolean', 'leaf', 'data:type', 'BOOLEAN.'),
    ('data:type:date', 'leaf', 'data:type', 'DATE.'),
    ('data:type:timestamp', 'leaf', 'data:type', 'TIMESTAMP, with or without time zone.'),
    ('data:type:other', 'leaf', 'data:type', 'Anything else.'),
    ('data:setop', 'class', 'data', 'The two inputs of a set operation, computed by running each input.'),
    ('data:setop:left_has_dups', 'leaf', 'data:setop', 'The left input returns two identical rows.'),
    ('data:setop:right_has_dups', 'leaf', 'data:setop', 'The right input returns two identical rows.'),
    ('data:setop:left_has_null', 'leaf', 'data:setop', 'The left input returns a NULL.'),
    ('data:setop:right_has_null', 'leaf', 'data:setop', 'The right input returns a NULL.'),
)


BASE_FEATURES: tuple[FeatureDef, ...] = tuple(_base(*row) for row in _BASE_ROWS)
