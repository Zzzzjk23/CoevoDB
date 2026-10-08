"""Coarse projection of phi onto (construct, plan class, data class)."""
from __future__ import annotations

from surprise.harness.contracts import ORACLE_IDS

from .phi import Phi
from .registry import Registry, default_registry

_CONSTRUCTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("dml", ("ast:stmt:merge", "ast:stmt:insert", "ast:stmt:update", "ast:stmt:delete")),
    ("set_op_all", ("ast:set_op:all",)),
    ("set_op", ("ast:set_op",)),
    ("window", ("ast:window",)),
    ("correlated_subquery", ("ast:subquery_trait:correlated",)),
    ("subquery", ("ast:subquery",)),
    ("asof_join", ("ast:join:asof",)),
    ("outer_join", ("ast:join:left", "ast:join:right", "ast:join:full")),
    ("join", ("ast:join",)),
    ("aggregate", ("ast:agg", "ast:group")),
    ("distinct", ("ast:clause:distinct",)),
)

_PLAN_CLASSES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("asof_join", ("ASOF",)),
    ("delim_join", ("DELIM_JOIN",)),
    ("window", ("WINDOW",)),
    ("join", ("JOIN", "CROSS_PRODUCT")),
    ("union", ("UNION", "RECURSIVE")),
    ("aggregate", ("GROUP_BY", "AGGREGATE")),
    ("sort", ("ORDER_BY", "SORT", "TOP_N")),
)

_DATA_CLASSES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("dups", ("data:table:dup_rows", "data:setop:left_has_dups", "data:setop:right_has_dups")),
    ("nulls", ("data:table:has_null", "data:setop:left_has_null", "data:setop:right_has_null")),
    ("empty", ("data:table:empty",)),
    ("extreme", ("data:value:extreme_number", "data:value:non_finite")),
)


def unit_parts(phi: Phi, registry: Registry | None = None) -> tuple[str, str, str]:
    """Return (construct, plan class, data class) for ``phi``."""
    active = default_registry() if registry is None else registry
    closed = active.closure(phi.features)
    return _construct(closed), _plan_class(phi), _data_class(phi, closed)


def unit_of(phi: Phi, oracle: str, registry: Registry | None = None) -> str:
    """``engine|oracle|construct|plan class|data class``."""
    if oracle not in ORACLE_IDS:
        raise ValueError(f"unknown oracle: {oracle}")
    construct, plan_class, data_class = unit_parts(phi, registry)
    return f"{phi.engine}|{oracle}|{construct}|{plan_class}|{data_class}"


def _construct(closed: frozenset[str]) -> str:
    for name, needles in _CONSTRUCTS:
        if any(needle in closed for needle in needles):
            return name
    return "plain"


def _plan_class(phi: Phi) -> str:
    if phi.layers["plan"] != "ok":
        return "none"
    names = tuple(feature_id.split(":", 1)[1].upper() for feature_id in phi.features if feature_id.startswith("plan:"))
    for name, needles in _PLAN_CLASSES:
        if any(any(needle in operator for needle in needles) for operator in names):
            return name
    return "scan"


def _data_class(phi: Phi, closed: frozenset[str]) -> str:
    if phi.layers["data"] != "ok":
        return "unknown"
    for name, needles in _DATA_CLASSES:
        if any(needle in closed for needle in needles):
            return name
    return "plain"
