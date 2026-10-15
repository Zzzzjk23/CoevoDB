"""Where the conjecturer looks in the pinned engine checkouts.

DuckDB names are the ones ``optimizer_type.cpp`` lists that have a file under
``src/optimizer/``. ``extension`` and ``materialized_cte`` have no such file.
DataFusion rows are ``(feature-id prefix, regex, subdirectory)``.
"""

from __future__ import annotations

# Enum order. A fix set is walked in this order, not in the order it was stored.
DUCKDB_OPTIMIZER_FILES: dict[str, str] = {
    "expression_rewriter": "src/optimizer/expression_rewriter.cpp",
    "filter_pullup": "src/optimizer/filter_pullup.cpp",
    "filter_pushdown": "src/optimizer/filter_pushdown.cpp",
    "empty_result_pullup": "src/optimizer/empty_result_pullup.cpp",
    "cte_filter_pusher": "src/optimizer/cte_filter_pusher.cpp",
    "regex_range": "src/optimizer/regex_range_filter.cpp",
    "in_clause": "src/optimizer/in_clause_rewriter.cpp",
    "join_order": "src/optimizer/join_order/join_order_optimizer.cpp",
    "deliminator": "src/optimizer/deliminator.cpp",
    "unnest_rewriter": "src/optimizer/unnest_rewriter.cpp",
    "unused_columns": "src/optimizer/remove_unused_columns.cpp",
    "statistics_propagation": "src/optimizer/statistics_propagator.cpp",
    "common_subexpressions": "src/optimizer/cse_optimizer.cpp",
    "common_aggregate": "src/optimizer/common_aggregate_optimizer.cpp",
    "column_lifetime": "src/optimizer/column_lifetime_analyzer.cpp",
    "limit_pushdown": "src/optimizer/limit_pushdown.cpp",
    "row_group_pruner": "src/optimizer/row_group_pruner.cpp",
    "top_n": "src/optimizer/topn_optimizer.cpp",
    "top_n_window_elimination": "src/optimizer/topn_window_elimination.cpp",
    "build_side_probe_side": "src/optimizer/build_probe_side_optimizer.cpp",
    "compressed_materialization": "src/optimizer/compressed_materialization.cpp",
    "duplicate_groups": "src/optimizer/remove_duplicate_groups.cpp",
    "reorder_filter": "src/optimizer/expression_heuristics.cpp",
    "sampling_pushdown": "src/optimizer/sampling_pushdown.cpp",
    "join_filter_pushdown": "src/optimizer/join_filter_pushdown_optimizer.cpp",
    "sum_rewriter": "src/optimizer/sum_rewriter.cpp",
    "late_materialization": "src/optimizer/late_materialization.cpp",
    "cte_inlining": "src/optimizer/cte_inlining.cpp",
    "common_subplan": "src/optimizer/common_subplan_optimizer.cpp",
    "join_elimination": "src/optimizer/join_elimination.cpp",
    "window_self_join": "src/optimizer/window_self_join.cpp",
}

# First match wins the file's place. Later rules that hit the same file merge.
DATAFUSION_SOURCE_RULES: tuple[tuple[str, str, str], ...] = (
    ("ast:set_op:", r"fn intersect_or_except", "datafusion/expr/src/logical_plan"),
    ("ast:join:", r"pub fn join\(", "datafusion/expr/src/logical_plan"),
    ("ast:join_cond:", r"pub fn join_on\(", "datafusion/expr/src/logical_plan"),
    ("ast:join_trait:", r"pub fn join\(", "datafusion/expr/src/logical_plan"),
    ("ast:subquery:", r"pub fn exists\(", "datafusion/expr/src"),
    ("ast:subquery_pos:", r"pub fn exists\(", "datafusion/expr/src"),
    ("ast:subquery_trait:", r"pub fn exists\(", "datafusion/expr/src"),
    ("ast:window", r"pub fn window\(", "datafusion/expr/src/logical_plan"),
    ("ast:agg", r"pub fn aggregate\(", "datafusion/expr/src/logical_plan"),
    ("ast:group:", r"pub fn aggregate\(", "datafusion/expr/src/logical_plan"),
    ("ast:clause:order_by", r"pub fn sort\(", "datafusion/expr/src/logical_plan"),
)
