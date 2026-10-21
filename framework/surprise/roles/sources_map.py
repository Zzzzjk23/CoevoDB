"""Where the conjecturer looks in the pinned engine checkouts.

DuckDB names are the ones ``optimizer_type.cpp`` lists that have a file under
``src/optimizer/``. ``extension`` and ``materialized_cte`` have no such file.
DataFusion rows are ``(feature-id prefix, regex, subdirectory)``.
"""

from __future__ import annotations

EXTRA_SOURCE_DIRS = {"postgres": "postgresql-16.15"}
EXTRA_SOURCE_COMMITS = {"postgres": "7d3e000c5961a544302072058a1184e9a588837b"}

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

# Intervention-basis order, excluding switches absent from PostgreSQL 16.15.
POSTGRES_GUC_FILES: dict[str, tuple[str, ...]] = {
    "enable_hashjoin": ("src/backend/executor/nodeHashjoin.c", "src/backend/optimizer/path/joinpath.c"),
    "enable_mergejoin": ("src/backend/executor/nodeMergejoin.c", "src/backend/optimizer/path/joinpath.c"),
    "enable_nestloop": ("src/backend/executor/nodeNestloop.c", "src/backend/optimizer/path/joinpath.c"),
    "enable_seqscan": ("src/backend/executor/nodeSeqscan.c", "src/backend/optimizer/path/costsize.c"),
    "enable_indexscan": ("src/backend/executor/nodeIndexscan.c", "src/backend/optimizer/path/costsize.c"),
    "enable_bitmapscan": ("src/backend/executor/nodeBitmapHeapscan.c", "src/backend/optimizer/path/costsize.c"),
    "enable_indexonlyscan": ("src/backend/executor/nodeIndexonlyscan.c", "src/backend/optimizer/path/costsize.c"),
    "enable_hashagg": ("src/backend/executor/nodeAgg.c", "src/backend/optimizer/plan/planner.c"),
    "enable_sort": ("src/backend/executor/nodeSort.c", "src/backend/optimizer/path/costsize.c"),
    "enable_incremental_sort": ("src/backend/executor/nodeIncrementalSort.c", "src/backend/optimizer/plan/planner.c"),
    "enable_memoize": ("src/backend/executor/nodeMemoize.c",),
    "enable_material": ("src/backend/executor/nodeMaterial.c", "src/backend/optimizer/path/joinpath.c"),
    "enable_gathermerge": ("src/backend/executor/nodeGatherMerge.c", "src/backend/optimizer/path/costsize.c"),
    "enable_partitionwise_join": ("src/backend/optimizer/path/joinrels.c",),
    "enable_partitionwise_aggregate": ("src/backend/optimizer/plan/planner.c",),
    "enable_parallel_append": ("src/backend/executor/nodeAppend.c", "src/backend/optimizer/path/allpaths.c"),
    "jit": ("src/backend/jit/jit.c", "src/backend/optimizer/plan/planner.c"),
    "geqo": ("src/backend/optimizer/geqo/geqo_main.c", "src/backend/optimizer/path/allpaths.c"),
    "parallel": ("src/backend/optimizer/path/allpaths.c", "src/backend/executor/nodeGather.c"),
    "enable_presorted_aggregate": ("src/backend/optimizer/plan/planner.c", "src/backend/executor/nodeAgg.c"),
    "enable_async_append": ("src/backend/optimizer/plan/createplan.c", "src/backend/executor/nodeAppend.c"),
    "debug_parallel_query": ("src/backend/optimizer/plan/planner.c",),
}

POSTGRES_SOURCE_RULES: tuple[tuple[str, str, str], ...] = (
    ("ast:set_op:", r"^generate_nonunion_paths\(", "src/backend/optimizer/prep"),
    ("ast:join:", r"^add_paths_to_joinrel\(", "src/backend/optimizer/path"),
    ("ast:join_cond:", r"^add_paths_to_joinrel\(", "src/backend/optimizer/path"),
    ("ast:join_trait:", r"^add_paths_to_joinrel\(", "src/backend/optimizer/path"),
    ("ast:subquery:", r"^pull_up_sublinks\(", "src/backend/optimizer/prep"),
    ("ast:subquery_pos:", r"^pull_up_sublinks\(", "src/backend/optimizer/prep"),
    ("ast:subquery_trait:", r"^pull_up_sublinks\(", "src/backend/optimizer/prep"),
    ("ast:window", r"^create_window_paths\(", "src/backend/optimizer/plan"),
    ("ast:agg", r"^create_grouping_paths\(", "src/backend/optimizer/plan"),
    ("ast:group:", r"^create_grouping_paths\(", "src/backend/optimizer/plan"),
    ("ast:clause:order_by", r"^create_ordered_paths\(", "src/backend/optimizer/plan"),
)
