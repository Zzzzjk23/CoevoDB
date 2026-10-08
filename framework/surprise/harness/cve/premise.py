"""Tier-1 premise checks. A violated premise skips the rerun."""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from surprise.harness.contracts import SqlCase
from surprise.harness.oracles.forms import full_query
from surprise.harness.oracles.pg_reference import is_readonly_query

_ASOF_RE = re.compile(
    r"\bASOF\s+(?:(?:LEFT|RIGHT|INNER|FULL|OUTER)\s+)?JOIN\b",
    re.IGNORECASE,
)
_END_KEYWORDS = (
    "WHERE",
    "GROUP BY",
    "HAVING",
    "ORDER BY",
    "LIMIT",
    "OFFSET",
    "FETCH",
    "QUALIFY",
    "WINDOW",
    "UNION",
    "INTERSECT",
    "EXCEPT",
)
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def check_premises(
    case: SqlCase,
    oracle: str,
    label: Any,
    probe: Callable[[str], tuple[str, Any]],
) -> dict[str, Any]:
    """Run the three checks. ``probe(sql)`` returns ``(status, value)``."""
    full = full_query(case)
    side_ok = is_readonly_query(full) or label.fail_kind == "crash"
    asof_ok = _asof_holds(full, probe)
    comparable_ok = True
    if oracle == "cross_dbms" and label.fail_kind == "wrong_result":
        comparable_ok = not _incomparable(case.engine, label.detail)
    checks = [
        {"name": "side_effecting_statement", "ok": side_ok},
        {"name": "unspecified_semantics", "ok": asof_ok},
        {"name": "incomparable_results", "ok": comparable_ok},
    ]
    violations = [item["name"] for item in checks if not item["ok"]]
    return {"status": "ran", "reason": None, "violations": violations, "checks": checks}


def _asof_holds(sql: str, probe: Callable[[str], tuple[str, Any]]) -> bool:
    """True when no ASOF join has tied right-hand keys. Unparseable joins fail."""
    masked = _mask_code(sql)
    if masked is None:
        return False
    matches = list(_ASOF_RE.finditer(masked))
    if not matches:
        return True
    for match in matches:
        parsed = _parse_asof(sql, match.end())
        if parsed is None:
            return False
        statement = _probe_sql(*parsed)
        if statement is None:
            return False
        status, value = probe(statement)
        if status != "ok":
            return False
        if value is None:
            continue
        try:
            count = int(value)
        except (TypeError, ValueError):
            return False
        if count > 1:
            return False
    return True


def _probe_sql(relation: str, is_subquery: bool, columns: list[str]) -> str | None:
    quoted_columns = []
    for column in columns:
        quoted = _quote(column)
        if quoted is None:
            return None
        quoted_columns.append(quoted)
    group = ", ".join(quoted_columns)
    if is_subquery:
        source = f"{relation} AS _cve_asof"
    else:
        quoted = _quote(relation)
        if quoted is None:
            return None
        source = quoted
    return (
        "SELECT MAX(c) FROM (SELECT COUNT(*) AS c FROM "
        f"{source} GROUP BY {group}) AS _cve_asof_card"
    )


def _parse_asof(sql: str, start: int) -> tuple[str, bool, list[str]] | None:
    index = _skip_ws(sql, start)
    if index is None or index >= len(sql):
        return None
    names: list[str] = []
    if sql[index] == "(":
        end = _balanced(sql, index)
        if end is None:
            return None
        relation = sql[index:end]
        is_subquery = True
        index = end
        alias = _optional_alias(sql, index)
        if alias is None:
            return None
        names.append(alias[0])
        index = alias[1]
    else:
        name, index = _read_ident(sql, index)
        if not name:
            return None
        relation = name
        is_subquery = False
        names.append(name)
        alias = _optional_alias(sql, index)
        if alias is not None and alias[0].upper() != "ON":
            names.append(alias[0])
            index = alias[1]
    index = _skip_ws(sql, index)
    if index is None:
        return None
    on_end = _keyword_end(sql, index, "ON")
    if on_end is None:
        return None
    condition = _read_condition(sql, on_end)
    if condition is None:
        return None
    columns = _qualified_columns(condition, names)
    if not columns:
        return None
    return relation, is_subquery, columns


def _optional_alias(sql: str, index: int) -> tuple[str, int] | None:
    """An alias, consuming a leading AS. None when the next token is ON or absent."""
    peeked, _next = _read_ident(sql, index)
    if peeked is None or peeked.upper() == "ON":
        return None
    if peeked.upper() == "AS":
        alias, after = _read_ident(sql, _next)
        if alias is None or alias.upper() == "ON":
            return None
        return alias, after
    return peeked, _next


def _qualified_columns(condition: str, names: list[str]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for name in names:
        pattern = re.compile(
            rf"\b{re.escape(name)}\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)",
            re.IGNORECASE,
        )
        for match in pattern.finditer(condition):
            column = match.group(1)
            key = column.lower()
            if key not in seen:
                seen.add(key)
                found.append(column)
    return found


def _read_condition(sql: str, start: int) -> str | None:
    index = start
    depth = 0
    in_string = False
    while index < len(sql):
        char = sql[index]
        if in_string:
            if char == "'":
                if index + 1 < len(sql) and sql[index + 1] == "'":
                    index += 2
                    continue
                in_string = False
            index += 1
            continue
        if char == "'":
            in_string = True
            index += 1
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif depth == 0:
            if _keyword_end(sql, index, "JOIN") is not None:
                break
            if any(_keyword_end(sql, index, keyword) is not None for keyword in _END_KEYWORDS):
                break
        index += 1
    text = sql[start:index].strip()
    if not text:
        return None
    return text


def _incomparable(engine: str, detail: dict[str, Any]) -> bool:
    participants = detail.get("participants")
    if not isinstance(participants, dict):
        return False
    reference = _majority_reference_bag(engine, participants)
    target = participants.get(engine)
    if reference is None or not isinstance(target, dict):
        return False
    target_bag = target.get("bag")
    if not isinstance(target_bag, list):
        return False
    return categories_conflict(target_bag, reference)


def categories_conflict(target_bag: list[Any], reference_bag: list[Any]) -> bool:
    """True when some column has a category on each side that the other lacks.

    ``null`` is not a category. Empty bags do not conflict: missing rows are a
    result difference. Unequal column counts conflict.
    """
    target_rows = _rows(target_bag)
    reference_rows = _rows(reference_bag)
    if target_rows is None or reference_rows is None:
        return True
    if not target_rows or not reference_rows:
        return False
    target_widths = {len(row) for row in target_rows}
    reference_widths = {len(row) for row in reference_rows}
    if len(target_widths) != 1 or target_widths != reference_widths:
        return True
    width = next(iter(target_widths))
    for index in range(width):
        left = {_category(row[index]) for row in target_rows} - {"null"}
        right = {_category(row[index]) for row in reference_rows} - {"null"}
        if (left - right) and (right - left):
            return True
    return False


def _majority_reference_bag(engine: str, participants: dict[str, Any]) -> list[Any] | None:
    votes: list[tuple[str, tuple[tuple[str, int], ...], list[Any]]] = []
    for name, info in participants.items():
        if not isinstance(info, dict) or not info.get("ok"):
            continue
        bag = info.get("bag")
        if not isinstance(bag, list):
            continue
        try:
            signature = tuple(sorted((str(key), int(count)) for key, count in bag))
        except (TypeError, ValueError):
            continue
        votes.append((str(name), signature, bag))
    if not any(name == engine for name, _signature, _bag in votes):
        return None
    counts: dict[tuple[tuple[str, int], ...], int] = {}
    for _name, signature, _bag in votes:
        counts[signature] = counts.get(signature, 0) + 1
    top = max(counts.items(), key=lambda item: item[1])[0]
    for name, signature, bag in sorted(votes):
        if name != engine and signature == top:
            return bag
    return None


def _rows(bag: list[Any]) -> list[list[Any]] | None:
    rows: list[list[Any]] = []
    for item in bag:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            return None
        key = item[0]
        try:
            row = json.loads(key) if isinstance(key, str) else key
        except json.JSONDecodeError:
            return None
        if not isinstance(row, list):
            return None
        rows.append(row)
    return rows


def _category(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "num"
    if isinstance(value, str):
        if value.startswith("float:"):
            return "num"
        if value.startswith("interval:"):
            return "interval"
        if value.startswith("bytes:"):
            return "bytes"
        return "text"
    if isinstance(value, list):
        if len(value) == 2 and value[0] in ("num", "temporal"):
            return str(value[0])
        return "list"
    if isinstance(value, dict):
        return "map"
    return "text"


def _mask_code(sql: str) -> str | None:
    """Copy of ``sql`` with comments and string literals blanked. Length is kept."""
    out: list[str] = []
    index = 0
    length = len(sql)
    while index < length:
        char = sql[index]
        nxt = sql[index + 1] if index + 1 < length else ""
        if char == "-" and nxt == "-":
            out.append("  ")
            index += 2
            while index < length and sql[index] != "\n":
                out.append(" ")
                index += 1
            continue
        if char == "/" and nxt == "*":
            out.append("  ")
            index += 2
            while index + 1 < length and not (sql[index] == "*" and sql[index + 1] == "/"):
                out.append(" ")
                index += 1
            if index + 1 >= length:
                return None
            out.append("  ")
            index += 2
            continue
        if char == "'":
            out.append(" ")
            index += 1
            while index < length:
                out.append(" ")
                if sql[index] == "'":
                    index += 1
                    if index < length and sql[index] == "'":
                        out.append(" ")
                        index += 1
                        continue
                    break
                index += 1
            else:
                return None
            continue
        out.append(char)
        index += 1
    return "".join(out)


def _skip_ws(sql: str, index: int) -> int | None:
    length = len(sql)
    while index < length:
        char = sql[index]
        nxt = sql[index + 1] if index + 1 < length else ""
        if char.isspace():
            index += 1
            continue
        if char == "-" and nxt == "-":
            index += 2
            while index < length and sql[index] != "\n":
                index += 1
            continue
        if char == "/" and nxt == "*":
            index += 2
            while index + 1 < length and not (sql[index] == "*" and sql[index + 1] == "/"):
                index += 1
            if index + 1 >= length:
                return None
            index += 2
            continue
        break
    return index


def _read_ident(sql: str, index: int) -> tuple[str | None, int]:
    skipped = _skip_ws(sql, index)
    if skipped is None or skipped >= len(sql):
        return None, index
    if sql[skipped] == '"':
        chars: list[str] = []
        cursor = skipped + 1
        while cursor < len(sql):
            if sql[cursor] == '"':
                if cursor + 1 < len(sql) and sql[cursor + 1] == '"':
                    chars.append('"')
                    cursor += 2
                    continue
                return "".join(chars), cursor + 1
            chars.append(sql[cursor])
            cursor += 1
        return None, index
    if not (sql[skipped].isalpha() or sql[skipped] == "_"):
        return None, index
    end = skipped + 1
    while end < len(sql) and (sql[end].isalnum() or sql[end] == "_"):
        end += 1
    return sql[skipped:end], end


def _keyword_end(sql: str, index: int, keyword: str) -> int | None:
    end = index + len(keyword)
    if end > len(sql) or sql[index:end].upper() != keyword.upper():
        return None
    before = index == 0 or not (sql[index - 1].isalnum() or sql[index - 1] == "_")
    after = end >= len(sql) or not (sql[end].isalnum() or sql[end] == "_")
    if before and after:
        return end
    return None


def _balanced(sql: str, index: int) -> int | None:
    depth = 0
    in_string = False
    cursor = index
    while cursor < len(sql):
        char = sql[cursor]
        if in_string:
            if char == "'":
                if cursor + 1 < len(sql) and sql[cursor + 1] == "'":
                    cursor += 2
                    continue
                in_string = False
            cursor += 1
            continue
        if char == "'":
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return cursor + 1
        cursor += 1
    return None


def _quote(identifier: str) -> str | None:
    if _IDENT.fullmatch(identifier) is None:
        return None
    return '"' + identifier + '"'
