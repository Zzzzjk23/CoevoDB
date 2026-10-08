"""Fold a case into one statement, and recognize GROUP BY / DISTINCT shapes.

``split_grouped`` accepts only the two shapes TLP can partition by set union.
Everything else returns None so the caller can fall back to WHERE injection.
"""

from __future__ import annotations

from dataclasses import dataclass

from oracles.determinism import _top_level_from_pos, _top_level_positions
from oracles.tlp import inject_predicate, tlp_applicable
from oracles.tlp_groupby import build_query

from surprise.harness.contracts import SqlCase


@dataclass(frozen=True)
class GroupedForm:
    """A SELECT that partitions by group key, or by a DISTINCT projection.

    ``group_by`` is None for the DISTINCT shape. ``from_tail`` starts with FROM.
    ``base_where`` is the existing top-level filter, or None when there is none.
    """

    select_list: str
    from_tail: str
    group_by: str | None
    base_where: str | None


def _keyword_at(sql: str, index: int, keyword: str) -> bool:
    """True when ``keyword`` sits at ``index`` as a whole word, ignoring case."""
    upper = sql.upper()
    if index < 0 or not upper.startswith(keyword, index):
        return False
    before_ok = index == 0 or not (upper[index - 1].isalnum() or upper[index - 1] == "_")
    end = index + len(keyword)
    after_ok = end >= len(upper) or not (upper[end].isalnum() or upper[end] == "_")
    return before_ok and after_ok


def _skip_ws(sql: str, index: int) -> int:
    while index < len(sql) and sql[index].isspace():
        index += 1
    return index


def _same_expr(left: str, right: str) -> bool:
    """Whitespace-compressed, case-insensitive equality of two SQL fragments."""
    return " ".join(left.split()).lower() == " ".join(right.split()).lower()


def _strip_statement(query: str) -> str:
    """Drop surrounding whitespace and one trailing semicolon."""
    text = query.strip()
    if text.endswith(";"):
        text = text[:-1].rstrip()
    return text


def _has_predicate(predicate: str | None) -> bool:
    return predicate is not None and predicate.strip() != ""


def split_grouped(query: str) -> GroupedForm | None:
    """Parse a GROUP BY or DISTINCT query, or return None when it is not one.

    The select list must not contain an aggregate or a window call, judged by
    ``tlp_applicable`` on that list alone. Any top-level clause other than the
    single WHERE these shapes allow (and the one GROUP BY) rejects the query.
    """
    text = _strip_statement(query)
    if not text or not _keyword_at(text, 0, "SELECT"):
        return None
    cursor = _skip_ws(text, len("SELECT"))
    if _keyword_at(text, cursor, "DISTINCT"):
        after_distinct = _skip_ws(text, cursor + len("DISTINCT"))
        if _keyword_at(text, after_distinct, "ON"):
            return None
        list_start = after_distinct
        distinct = True
    else:
        list_start = cursor
        distinct = False
    from_pos = _top_level_from_pos(text)
    if from_pos is None or from_pos < list_start:
        return None
    select_list = text[list_start:from_pos].strip()
    if not select_list:
        return None
    if not tlp_applicable("SELECT " + select_list, "1"):
        return None
    positions = [(pos, keyword) for pos, keyword in _top_level_positions(text) if pos >= from_pos]
    if distinct:
        return _distinct_form(text, select_list, from_pos, positions)
    return _grouped_form(text, select_list, from_pos, positions)


def _distinct_form(
    text: str,
    select_list: str,
    from_pos: int,
    positions: list[tuple[int, str]],
) -> GroupedForm | None:
    if any(keyword != "WHERE" for _, keyword in positions) or len(positions) > 1:
        return None
    if not positions:
        return GroupedForm(select_list, text[from_pos:].strip(), None, None)
    where_pos = positions[0][0]
    return GroupedForm(
        select_list,
        text[from_pos:where_pos].strip(),
        None,
        text[where_pos + len("WHERE") :].strip(),
    )


def _grouped_form(
    text: str,
    select_list: str,
    from_pos: int,
    positions: list[tuple[int, str]],
) -> GroupedForm | None:
    group_positions = [pos for pos, keyword in positions if keyword == "GROUP BY"]
    if len(group_positions) != 1:
        return None
    if any(keyword not in ("WHERE", "GROUP BY") for _, keyword in positions):
        return None
    where_positions = [pos for pos, keyword in positions if keyword == "WHERE"]
    if len(where_positions) > 1:
        return None
    group_pos = group_positions[0]
    if where_positions and where_positions[0] > group_pos:
        return None
    group_by = text[group_pos + len("GROUP BY") :].strip()
    if where_positions:
        where_pos = where_positions[0]
        from_tail = text[from_pos:where_pos].strip()
        base_where: str | None = text[where_pos + len("WHERE") : group_pos].strip()
    else:
        from_tail = text[from_pos:group_pos].strip()
        base_where = None
    if not _same_expr(select_list, group_by):
        return None
    return GroupedForm(select_list, from_tail, group_by, base_where)


def full_query(case: SqlCase) -> str:
    """The single statement determinism screening and plan variant execute.

    An empty predicate leaves ``case.query`` untouched. A grouped or distinct
    query gets the predicate in front of GROUP BY. Anything else gets the
    predicate injected at the top-level WHERE, which can be illegal SQL when
    the query already ends in another clause; execution then fails and the
    label is invalid.
    """
    if not _has_predicate(case.predicate):
        return case.query
    form = split_grouped(case.query)
    if form is not None:
        return build_query(
            form.select_list,
            form.from_tail,
            form.group_by,
            where=case.predicate,
            distinct=form.group_by is None,
            base_where=form.base_where,
        )
    return inject_predicate(case.query, case.predicate)
