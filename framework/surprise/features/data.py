"""Data-layer features, counted in Python from rows the engine returned.

No aggregate SQL. The statement under test is not executed. Referenced base
tables are read with ``SELECT *`` and ``DESCRIBE``; each input of a set
operation is run on its own. A reference is only the catalog, schema, and
table name. A table that cannot be read, a reference that cannot be rendered,
a table past the row cap, or a set-operation input that runs and passes the
row cap makes the layer unavailable and contributes no data features. A
set-operation input that cannot be run on its own contributes nothing and
leaves the layer ``ok``.
"""
from __future__ import annotations

import math
import re
from decimal import Decimal

from sqlglot import exp

from .ast import _dialect, _parse_one
from .limits import MAX_TABLE_ROWS, PROBE_TIMEOUT_S

_EXTREME = 2**31
_NON_FINITE_TEXT = frozenset({"float:nan", "float:+inf", "float:-inf"})
_SET_OPS = (exp.Union, exp.Except, exp.Intersect)


class _RefError(Exception):
    """A base-table reference could not be rendered from its name alone."""


_INTEGER_TOKENS = frozenset({
    "TINYINT", "SMALLINT", "INTEGER", "INT", "BIGINT", "HUGEINT",
    "UTINYINT", "USMALLINT", "UINTEGER", "UINT", "UBIGINT", "UHUGEINT",
    "INT2", "INT4", "INT8", "INT16", "INT32", "INT64", "INT128",
    "UINT8", "UINT16", "UINT32", "UINT64", "UINT128",
    "SIGNED",
})
_INTEGER_RE = re.compile(r"U?INT\d*")
_FLOAT_TOKENS = frozenset({"FLOAT", "REAL", "DOUBLE", "DOUBLEPRECISION"})
_STRING_TOKENS = frozenset({
    "VARCHAR", "CHAR", "CHARACTER", "TEXT", "STRING", "BPCHAR",
    "NVARCHAR", "CLOB", "UTF8", "UTF8VIEW", "LARGEUTF8", "LARGESTRING",
})


def extract_data(runner, query: str, engine: str) -> tuple[set[str], str]:
    """Return ``(data leaves, "ok" | "unavailable")``."""
    tree = _parse_one(query, _dialect(engine))
    if tree is None:
        return set(), "unavailable"
    dialect = _dialect(engine)
    features: set[str] = set()
    try:
        refs = _base_tables(tree, dialect)
    except _RefError:
        return set(), "unavailable"
    for ref in refs:
        rows = _fetch_table(runner, ref)
        if rows is None:
            return set(), "unavailable"
        _table_flags(rows, features)
        described = _describe(runner, ref)
        if described is None:
            return set(), "unavailable"
        features.update(described)
    for node in tree.find_all(*_SET_OPS):
        for which, side in (("left", node.args.get("this")), ("right", node.args.get("expression"))):
            if _setop_input(runner, node, side, which, dialect, features):
                return set(), "unavailable"
    return features, "ok"


def _type_feature(type_name: str) -> str:
    """Map an engine type name onto one ``data:type:*`` leaf."""
    token = _type_token(type_name)
    if not token:
        return "data:type:other"
    if token.startswith("TIMESTAMP") or token in {"DATETIME", "TIMESTAMPTZ"}:
        return "data:type:timestamp"
    if token == "DATE" or token.startswith("DATE"):
        return "data:type:date"
    if token.startswith("DECIMAL") or token.startswith("NUMERIC"):
        return "data:type:decimal"
    if token in {"BOOLEAN", "BOOL"}:
        return "data:type:boolean"
    if token in _FLOAT_TOKENS or token.startswith("FLOAT"):
        return "data:type:float"
    if token in _INTEGER_TOKENS or _INTEGER_RE.fullmatch(token):
        return "data:type:integer"
    if (
        token in _STRING_TOKENS
        or "UTF8" in token
        or token.endswith("CHAR")
        or token.endswith("STRING")
        or token.endswith("TEXT")
    ):
        return "data:type:string"
    return "data:type:other"


def _type_token(type_name: str) -> str:
    head = re.split(r"[\s(]", type_name.strip(), maxsplit=1)[0]
    return re.sub(r"[^A-Za-z0-9]", "", head).upper()


def _base_tables(tree: exp.Expression, dialect: str | None) -> list[str]:
    """SQL references of base tables, CTE names and table functions removed.

    Each reference is catalog, schema, and table name. A name that cannot be
    rendered raises ``_RefError`` so the layer is not reported as complete.
    """
    cte_names: set[str] = set()
    for cte in tree.find_all(exp.CTE):
        key = _cte_key(cte)
        if key is not None:
            cte_names.add(key)
    seen: set[tuple] = set()
    refs: list[str] = []
    for table in tree.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier):
            continue
        if _is_cte_ref(table, cte_names):
            continue
        key = _table_key(table)
        if key in seen:
            continue
        seen.add(key)
        refs.append(_table_sql(table, dialect))
    return refs


def _table_sql(table: exp.Table, dialect: str | None) -> str:
    """Render catalog, schema, and name, keeping the quotes those parts had."""
    this = table.this
    if not isinstance(this, exp.Identifier):
        raise _RefError("table name is not an identifier")
    ref = exp.Table(this=this.copy())
    for arg in ("db", "catalog"):
        part = table.args.get(arg)
        if part is None:
            continue
        if not isinstance(part, exp.Identifier):
            raise _RefError(f"{arg} is not an identifier")
        ref.set(arg, part.copy())
    try:
        rendered = ref.sql(dialect=dialect)
    except Exception as exc:
        raise _RefError("table reference did not render") from exc
    if not isinstance(rendered, str) or not rendered.strip():
        raise _RefError("table reference did not render")
    return rendered


def _fetch_table(runner, ref: str) -> list | None:
    limit = MAX_TABLE_ROWS + 1
    result = _run(runner, f"SELECT * FROM {ref} LIMIT {limit}")
    if not _succeeded(result):
        return None
    rows = list(result.rows or [])
    if len(rows) > MAX_TABLE_ROWS:
        return None
    return rows


def _describe(runner, ref: str) -> set[str] | None:
    result = _run(runner, f"DESCRIBE {ref}")
    if not _succeeded(result):
        return None
    found: set[str] = set()
    for row in result.rows or []:
        if not row or len(row) < 2 or row[1] is None:
            continue
        found.add(_type_feature(str(row[1])))
    return found


def _setop_input(runner, node, side, which: str, dialect: str | None, features: set[str]) -> bool:
    """Record one input. Return True when it ran and exceeded the row cap."""
    if side is None:
        return False
    try:
        body = side.sql(dialect=dialect)
    except Exception:
        return False
    if not isinstance(body, str) or not body.strip():
        return False
    limit = MAX_TABLE_ROWS + 1
    wrapped = f"SELECT * FROM ({body}) AS _coevo_setop_input LIMIT {limit}"
    prefix = _with_sql(node, dialect)
    sql = f"{prefix} {wrapped}" if prefix else wrapped
    result = _run(runner, sql)
    if not _succeeded(result):
        return False
    rows = list(result.rows or [])
    if len(rows) > MAX_TABLE_ROWS:
        return True
    if _has_duplicate(rows):
        features.add(f"data:setop:{which}_has_dups")
    if _has_null(rows):
        features.add(f"data:setop:{which}_has_null")
    return False


def _with_sql(node: exp.Expression, dialect: str | None) -> str | None:
    current: exp.Expression | None = node
    while current is not None:
        found = current.args.get("with_")
        if found is None:
            found = current.args.get("with")
        if isinstance(found, exp.With):
            try:
                return found.sql(dialect=dialect)
            except Exception:
                return None
        current = current.parent
    return None


def _table_flags(rows: list, features: set[str]) -> None:
    if len(rows) == 0:
        features.add("data:table:empty")
    elif len(rows) == 1:
        features.add("data:table:single_row")
    if _has_duplicate(rows):
        features.add("data:table:dup_rows")
    if _has_null(rows):
        features.add("data:table:has_null")
    for row in rows:
        for cell in row:
            _absorb_value(cell, features)


def _absorb_value(value, features: set[str]) -> None:
    """Record corner-case leaves present in one cell. Booleans are not numbers."""
    if isinstance(value, list):
        for item in value:
            _absorb_value(item, features)
        return
    if isinstance(value, dict):
        for item in value.values():
            _absorb_value(item, features)
        return
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, str):
        if value == "":
            features.add("data:value:empty_string")
        elif value in _NON_FINITE_TEXT:
            features.add("data:value:non_finite")
        return
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        features.add("data:value:non_finite")
        return
    if isinstance(value, Decimal) and (value.is_nan() or value.is_infinite()):
        features.add("data:value:non_finite")
        return
    if isinstance(value, (int, float, Decimal)):
        if value == 0:
            features.add("data:value:zero")
        if value < 0:
            features.add("data:value:negative")
        if abs(value) >= _EXTREME:
            features.add("data:value:extreme_number")


def _has_duplicate(rows: list) -> bool:
    seen: set = set()
    for row in rows:
        key = tuple(_freeze(cell) for cell in row)
        if key in seen:
            return True
        seen.add(key)
    return False


def _has_null(rows: list) -> bool:
    return any(_contains_none(cell) for row in rows for cell in row)


def _contains_none(value) -> bool:
    if value is None:
        return True
    if isinstance(value, list):
        return any(_contains_none(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_none(item) for item in value.values())
    return False


def _freeze(value):
    if isinstance(value, float):
        if math.isnan(value):
            return ("nan",)
        if math.isinf(value):
            return ("+inf",) if value > 0 else ("-inf",)
    if isinstance(value, Decimal):
        if value.is_nan():
            return ("nan",)
        if value.is_infinite():
            return ("+inf",) if value > 0 else ("-inf",)
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((str(key), _freeze(item)) for key, item in value.items()))
    return value


def _table_key(table: exp.Table) -> tuple:
    return (
        _ident_key(table.args.get("catalog")),
        _ident_key(table.args.get("db")),
        _ident_key(table.this),
    )


def _is_cte_ref(table: exp.Table, cte_names: set[str]) -> bool:
    if table.args.get("db") is not None or table.args.get("catalog") is not None:
        return False
    key = _ident_key(table.this)
    return key is not None and key in cte_names


def _cte_key(cte: exp.CTE) -> str | None:
    alias = cte.args.get("alias")
    ident = None
    if isinstance(alias, exp.TableAlias):
        if isinstance(alias.this, exp.Identifier):
            ident = alias.this
    elif isinstance(alias, exp.Identifier):
        ident = alias
    if ident is not None:
        return _ident_key(ident)
    text = cte.alias
    if isinstance(text, str) and text:
        return text.casefold()
    return None


def _ident_key(node) -> str | None:
    if not isinstance(node, exp.Identifier):
        return None
    name = node.name
    if node.args.get("quoted"):
        return name
    return name.casefold()


def _run(runner, sql: str):
    try:
        return runner.run(sql, timeout_s=PROBE_TIMEOUT_S)
    except Exception:
        return None


def _succeeded(result) -> bool:
    if result is None or getattr(result, "timed_out", False):
        return False
    if getattr(result, "error", None):
        return False
    ok = getattr(result, "ok", True)
    return bool(ok)
