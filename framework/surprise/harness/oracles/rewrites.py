"""Frozen, mechanical SQL rewrites for the equivalent-query oracle.

Each rule returns None unless its syntactic premises hold. A rewrite is never
accepted because two queries happened to agree on one database. The scanner
tracks quotes, comments, and parentheses so a keyword inside a literal,
comment, or nested query is not a clause boundary.

Equivalence arguments (SQL three-valued logic):

* ``double_negation`` wraps the whole top-level WHERE predicate ``p`` as
  ``NOT (NOT (p))``. NOT is involutive on TRUE, FALSE, and UNKNOWN, and WHERE
  keeps only TRUE, so the admitted rows are unchanged. The rule does not push
  NOT through AND, OR, or a subquery.
* ``demorgan`` rewrites a predicate that is exactly ``NOT (p AND q)`` or
  ``NOT (p OR q)`` into ``(NOT (p)) OR (NOT (q))`` or ``(NOT (p)) AND (NOT (q))``.
  Both identities hold when an operand is UNKNOWN. Mixed AND/OR, n-ary chains,
  and a NOT that does not wrap the whole predicate are declined. An AND that
  completes BETWEEN, and an AND or OR inside CASE, brackets, or braces, is
  not that connective. Those shapes, a lambda arrow, and an unclosed CASE or
  BETWEEN are declined instead of split.
* ``case_to_coalesce`` rewrites ``CASE WHEN x IS NOT NULL THEN x ELSE y END``
  to ``COALESCE(x, y)`` only when both copies of ``x`` are the same safe
  expression. NULL yields ``y`` on both sides; a non-NULL ``x`` yields ``x``.
  The original CASE evaluates ``x`` twice and COALESCE once, so the identity
  is claimed only for deterministic ``x`` (the harness already rejects
  nondeterministic queries). A different THEN expression, ``IS NULL``, extra
  WHEN arms, and simple CASE are declined.
"""

from __future__ import annotations

from dataclasses import dataclass

_DOUBLE_NEGATION_PROOF = (
    "In SQL three-valued logic NOT is involutive: NOT NOT TRUE = TRUE, "
    "NOT NOT FALSE = FALSE, and NOT NOT UNKNOWN = UNKNOWN. WHERE retains "
    "only TRUE, so wrapping the entire top-level predicate p as NOT (NOT (p)) "
    "admits the same rows. The rule does not push NOT through AND, OR, "
    "comparisons, or subqueries."
)

_DEMORGAN_PROOF = (
    "In SQL three-valued logic, NOT (p AND q) equals (NOT p) OR (NOT q) and "
    "NOT (p OR q) equals (NOT p) AND (NOT q), including when p or q is UNKNOWN. "
    "The rule fires only when the WHERE predicate is exactly that binary form. "
    "An AND that belongs to BETWEEN, and an AND or OR inside CASE, brackets, "
    "or braces, is syntax rather than this connective, so those shapes are "
    "declined. Mixed AND/OR, n-ary chains, a lambda arrow, and a NOT that "
    "covers only part of the predicate are left untouched."
)

_CASE_TO_COALESCE_PROOF = (
    "CASE WHEN x IS NOT NULL THEN x ELSE y END equals COALESCE(x, y) when both "
    "copies of x are the same expression: a NULL x yields y on both sides, and "
    "a non-NULL x yields x. The CASE evaluates x twice and COALESCE once, so "
    "this holds for deterministic x. A different THEN expression, IS NULL, "
    "extra WHEN arms, and simple CASE are not this form."
)

RULES: dict[str, dict[str, str]] = {
    "double_negation": {"proof": _DOUBLE_NEGATION_PROOF},
    "demorgan": {"proof": _DEMORGAN_PROOF},
    "case_to_coalesce": {"proof": _CASE_TO_COALESCE_PROOF},
}

_KEYWORDS = frozenset({
    "ALL", "ALTER", "AND", "AS", "BETWEEN", "BY", "CALL", "CASE", "COPY",
    "CREATE", "DELETE", "DROP", "ELSE", "END", "EXCEPT", "EXECUTE", "EXPLAIN",
    "FALSE", "FETCH", "FOR", "FROM", "GRANT", "GROUP", "HAVING", "INSERT",
    "INTERSECT", "INTO", "IS", "LIMIT", "MERGE", "NOT", "NULL", "OFFSET", "OR",
    "ORDER", "QUALIFY", "RETURNING", "REVOKE", "SELECT", "SET", "THEN", "TRUE",
    "TRUNCATE", "UNION", "UPDATE", "VALUES", "WHEN", "WHERE", "WINDOW", "WITH",
})

_DML = frozenset({
    "ALTER", "CALL", "COPY", "CREATE", "DELETE", "DROP", "EXECUTE", "GRANT",
    "INSERT", "MERGE", "REVOKE", "TRUNCATE", "UPDATE",
})

_WHERE_ENDS = frozenset({
    "EXCEPT", "FETCH", "FOR", "GROUP", "HAVING", "INTERSECT", "LIMIT",
    "OFFSET", "ORDER", "QUALIFY", "UNION", "WINDOW",
})

_TWO_CHAR = ("<>", "<=", ">=", "!=", "||", "::", "->")


class ScanError(Exception):
    """The statement is not safe to rewrite mechanically."""


@dataclass(frozen=True)
class Tok:
    """One lexical token. ``depth`` is the parenthesis depth before it."""

    kind: str
    text: str
    start: int
    end: int
    depth: int


def apply_rule(query: str, rule_id: str) -> str | None:
    """Return the rule's SQL, or None when its premises do not hold.

    Unknown rules and queries that are not a single read-only statement also
    return None. Callers must not execute a query this function did not return.
    """
    if not isinstance(query, str) or not isinstance(rule_id, str):
        return None
    impl = _IMPL.get(rule_id)
    if impl is None or rule_id not in RULES:
        return None
    return impl(query)


def is_read_only_query(query: str) -> bool:
    """True for one SELECT or WITH statement that contains no DML keyword."""
    if not isinstance(query, str):
        return False
    try:
        tokens = tokenize(query)
    except ScanError:
        return False
    return _is_read_only(tokens)


def tokenize(sql: str) -> list[Tok]:
    """Scan ``sql``. Quotes, comments, and dollar quotes hide their contents."""
    tokens: list[Tok] = []
    depth = 0
    index = 0
    length = len(sql)
    while index < length:
        char = sql[index]
        if char.isspace():
            index += 1
            continue
        if sql.startswith("--", index):
            newline = sql.find("\n", index + 2)
            index = length if newline < 0 else newline + 1
            continue
        if sql.startswith("/*", index):
            index = _skip_block_comment(sql, index)
            continue
        if char == "'":
            end = _skip_quoted(sql, index, "'")
            tokens.append(Tok("string", sql[index:end], index, end, depth))
            index = end
            continue
        if char == '"':
            end = _skip_quoted(sql, index, '"')
            tokens.append(Tok("quoted", sql[index:end], index, end, depth))
            index = end
            continue
        if char == "$":
            end = _skip_dollar(sql, index)
            tokens.append(Tok("string", sql[index:end], index, end, depth))
            index = end
            continue
        if char == "(":
            tokens.append(Tok("punct", char, index, index + 1, depth))
            depth += 1
            index += 1
            continue
        if char == ")":
            if depth == 0:
                raise ScanError("unbalanced parenthesis")
            tokens.append(Tok("punct", char, index, index + 1, depth))
            depth -= 1
            index += 1
            continue
        if char in "[]{},;":
            tokens.append(Tok("punct", char, index, index + 1, depth))
            index += 1
            continue
        if char.isalpha() or char == "_":
            end = index + 1
            while end < length and (sql[end].isalnum() or sql[end] == "_"):
                end += 1
            text = sql[index:end]
            kind = "kw" if text.upper() in _KEYWORDS else "ident"
            tokens.append(Tok(kind, text, index, end, depth))
            index = end
            continue
        if char.isdigit() or (char == "." and index + 1 < length and sql[index + 1].isdigit()):
            end = _skip_number(sql, index)
            tokens.append(Tok("number", sql[index:end], index, end, depth))
            index = end
            continue
        if sql.startswith(_TWO_CHAR, index):
            for op in _TWO_CHAR:
                if sql.startswith(op, index):
                    tokens.append(Tok("op", op, index, index + len(op), depth))
                    index += len(op)
                    break
            continue
        if char.isascii() and not char.isalnum():
            tokens.append(Tok("op", char, index, index + 1, depth))
            index += 1
            continue
        raise ScanError("unsupported character")
    if depth != 0:
        raise ScanError("unbalanced parenthesis")
    return tokens


def _skip_block_comment(sql: str, index: int) -> int:
    """Skip a possibly nested block comment. Unclosed comments are rejected."""
    index += 2
    level = 1
    length = len(sql)
    while index < length and level:
        if sql.startswith("/*", index):
            level += 1
            index += 2
        elif sql.startswith("*/", index):
            level -= 1
            index += 2
        else:
            index += 1
    if level:
        raise ScanError("unclosed comment")
    return index


def _skip_quoted(sql: str, index: int, quote: str) -> int:
    """Skip a quote-delimited literal. A doubled quote is an escape."""
    index += 1
    length = len(sql)
    while index < length:
        if sql[index] != quote:
            index += 1
            continue
        if index + 1 < length and sql[index + 1] == quote:
            index += 2
            continue
        return index + 1
    raise ScanError("unclosed quote")


def _skip_dollar(sql: str, index: int) -> int:
    """Skip a ``$tag$ ... $tag$`` string. A bare ``$`` is not a string."""
    end_tag = index + 1
    while end_tag < len(sql) and (sql[end_tag].isalnum() or sql[end_tag] == "_"):
        end_tag += 1
    if end_tag >= len(sql) or sql[end_tag] != "$":
        raise ScanError("bare dollar")
    tag = sql[index : end_tag + 1]
    close = sql.find(tag, end_tag + 1)
    if close < 0:
        raise ScanError("unclosed dollar quote")
    return close + len(tag)


def _skip_number(sql: str, index: int) -> int:
    end = index + 1
    length = len(sql)
    while end < length and (sql[end].isdigit() or sql[end] in ".eE"):
        if sql[end] in "eE" and end + 1 < length and sql[end + 1] in "+-":
            end += 2
            continue
        end += 1
    return end


def _body(tokens: list[Tok]) -> list[Tok] | None:
    """Tokens of a single statement, ignoring one trailing semicolon."""
    if any(tok.text == ";" and tok.depth == 0 for tok in tokens[:-1]):
        return None
    if tokens and tokens[-1].text == ";" and tokens[-1].depth == 0:
        tokens = tokens[:-1]
    return tokens or None


def _is_read_only(tokens: list[Tok]) -> bool:
    body = _body(tokens)
    if not body:
        return False
    first = body[0]
    if first.kind != "kw" or first.text.upper() not in {"SELECT", "WITH"}:
        return False
    return not any(tok.kind == "kw" and tok.text.upper() in _DML for tok in body)


def _where_indexes(tokens: list[Tok]) -> list[int]:
    body = _body(tokens) or []
    return [
        index for index, tok in enumerate(body)
        if tok.depth == 0 and tok.kind == "kw" and tok.text.upper() == "WHERE"
    ]


def _predicate_bounds(tokens: list[Tok], where_index: int) -> tuple[int, int] | None:
    """Token span ``(start, end)`` of the predicate after ``tokens[where_index]``."""
    start = where_index + 1
    end = start
    limit = len(tokens)
    if tokens and tokens[-1].text == ";" and tokens[-1].depth == 0:
        limit -= 1
    while end < limit:
        tok = tokens[end]
        if tok.depth == 0 and tok.kind == "kw" and tok.text.upper() in _WHERE_ENDS:
            break
        end += 1
    if start == end:
        return None
    return start, end


def _splice(sql: str, tokens: list[Tok], replacement: str) -> str:
    """Replace the source covered by ``tokens`` and keep the surrounding text."""
    return sql[: tokens[0].start] + replacement + sql[tokens[-1].end :]


def _norm(tokens: list[Tok]) -> str:
    """Whitespace-collapsed text. Unquoted identifiers are case-folded."""
    parts: list[str] = []
    for tok in tokens:
        if tok.kind == "ident":
            parts.append(tok.text.lower())
        elif tok.kind == "kw":
            parts.append(tok.text.upper())
        else:
            parts.append(tok.text)
    return " ".join(parts)


def _unwrap(tokens: list[Tok]) -> list[Tok]:
    """Drop parentheses that wrap the whole fragment and nothing else."""
    current = tokens
    while len(current) >= 2 and current[0].text == "(" and current[-1].text == ")":
        if current[-1].depth != current[0].depth + 1:
            break
        if any(tok.depth <= current[0].depth for tok in current[1:-1]):
            break
        current = current[1:-1]
    return current


def _match_paren(tokens: list[Tok], open_index: int) -> int | None:
    if open_index >= len(tokens) or tokens[open_index].text != "(":
        return None
    want = tokens[open_index].depth + 1
    for index in range(open_index + 1, len(tokens)):
        if tokens[index].text == ")" and tokens[index].depth == want:
            return index
    return None


def _kw_at(tokens: list[Tok], index: int, words: tuple[str, ...]) -> bool:
    if index + len(words) > len(tokens):
        return False
    for offset, word in enumerate(words):
        tok = tokens[index + offset]
        if tok.kind != "kw" or tok.text.upper() != word:
            return False
    return True


def _parse_safe(tokens: list[Tok], index: int) -> int | None:
    """Index after one safe expression, or None when the shape is not safe.

    A safe expression is an atom, an optional chain of ``.name``, a function
    call delimited by parentheses, a balanced parenthesized fragment, or one
    leading sign on any of those. ``+`` and ``AND`` are not absorbed, so
    ``b + 1 IS NOT NULL`` is not misread as one test expression.
    """
    if index >= len(tokens):
        return None
    tok = tokens[index]
    if tok.kind == "op" and tok.text in {"+", "-"}:
        return _parse_safe(tokens, index + 1)
    if tok.kind in {"ident", "quoted"} or (
        tok.kind == "kw" and tok.text.upper() in {"NULL", "TRUE", "FALSE"}
    ):
        cursor = index + 1
        while (
            cursor + 1 < len(tokens)
            and tokens[cursor].text == "."
            and tokens[cursor + 1].kind in {"ident", "quoted"}
        ):
            cursor += 2
        if cursor < len(tokens) and tokens[cursor].text == "(":
            close = _match_paren(tokens, cursor)
            if close is None:
                return None
            return close + 1
        return cursor
    if tok.kind in {"number", "string"}:
        return index + 1
    if tok.text == "(":
        close = _match_paren(tokens, index)
        if close is None or close == index + 1:
            return None
        return close + 1
    return None


def _slice(sql: str, tokens: list[Tok]) -> str:
    return sql[tokens[0].start : tokens[-1].end].strip()


def _apply_double_negation(query: str) -> str | None:
    try:
        tokens = tokenize(query)
    except ScanError:
        return None
    if not _is_read_only(tokens):
        return None
    found = _where_indexes(tokens)
    if len(found) != 1:
        return None
    bounds = _predicate_bounds(tokens, found[0])
    if bounds is None:
        return None
    predicate = tokens[bounds[0] : bounds[1]]
    rewritten = _splice(query, predicate, f"NOT (NOT ({_slice(query, predicate)}))")
    if rewritten == query:
        return None
    return rewritten


def _logical_connectors(tokens: list[Tok]) -> list[int] | None:
    """Indexes of logical AND/OR, or None when the fragment is unclassifiable.

    BETWEEN consumes the next AND at the same parenthesis, CASE, and bracket
    depth. AND/OR inside ``CASE`` ... ``END`` or inside ``[]`` / ``{}`` is not
    a logical connective. An unclosed CASE or BETWEEN, an unmatched bracket,
    or a ``->`` lambda declines the whole fragment.
    """
    case_depth = 0
    bracket = 0
    pending: list[tuple[int, int, int]] = []
    found: list[int] = []
    for index, tok in enumerate(tokens):
        if tok.kind == "op" and tok.text == "->":
            return None
        if tok.text in "[{":
            bracket += 1
            continue
        if tok.text in "]}":
            if any(level == bracket for _depth, _case, level in pending):
                return None
            bracket -= 1
            if bracket < 0:
                return None
            continue
        if tok.kind != "kw":
            continue
        word = tok.text.upper()
        context = (tok.depth, case_depth, bracket)
        if word == "CASE":
            case_depth += 1
            continue
        if word == "END":
            if case_depth == 0 or any(
                level == case_depth for _depth, level, _bracket in pending
            ):
                return None
            case_depth -= 1
            continue
        if word == "BETWEEN":
            if context in pending:
                return None
            pending.append(context)
            continue
        if word not in {"AND", "OR"}:
            continue
        if word == "AND" and context in pending:
            if any(
                depth > tok.depth or case > case_depth or level > bracket
                for depth, case, level in pending
            ):
                return None
            pending.remove(context)
            continue
        if context in pending or case_depth or bracket:
            # An OR cannot complete BETWEEN. Nested AND/OR is not the split.
            if context in pending:
                return None
            continue
        if any(
            depth > tok.depth or case > case_depth or level > bracket
            for depth, case, level in pending
        ):
            return None
        found.append(index)
    if case_depth or bracket or pending:
        return None
    return found


def _split_binary(sql: str, tokens: list[Tok]) -> tuple[str, str, str] | None:
    """``(left_sql, connector, right_sql)`` for one logical AND or OR."""
    current = _unwrap(tokens)
    if len(current) < 3:
        return None
    found = _logical_connectors(current)
    if not found:
        return None
    base = min(tok.depth for tok in current)
    connectors = [index for index in found if current[index].depth == base]
    if len(connectors) != 1:
        return None
    at = connectors[0]
    left, right = current[:at], current[at + 1 :]
    if not left or not right:
        return None
    return _slice(sql, left), current[at].text.upper(), _slice(sql, right)


def _apply_demorgan(query: str) -> str | None:
    try:
        tokens = tokenize(query)
    except ScanError:
        return None
    if not _is_read_only(tokens):
        return None
    found = _where_indexes(tokens)
    if len(found) != 1:
        return None
    bounds = _predicate_bounds(tokens, found[0])
    if bounds is None:
        return None
    predicate = _unwrap(tokens[bounds[0] : bounds[1]])
    if len(predicate) < 4 or predicate[0].text.upper() != "NOT" or predicate[0].kind != "kw":
        return None
    if predicate[1].text != "(":
        return None
    close = _match_paren(predicate, 1)
    if close is None or close != len(predicate) - 1:
        return None
    split = _split_binary(query, predicate[2:close])
    if split is None:
        return None
    left, connector, right = split
    junction = "OR" if connector == "AND" else "AND"
    replacement = f"(NOT ({left})) {junction} (NOT ({right}))"
    rewritten = _splice(query, tokens[bounds[0] : bounds[1]], replacement)
    if rewritten == query:
        return None
    return rewritten


def _try_case(sql: str, tokens: list[Tok], index: int) -> tuple[int, int, int, str] | None:
    """One searched CASE of the proved shape, or None to keep scanning."""
    if not _kw_at(tokens, index + 1, ("WHEN",)):
        return None
    test_end = _parse_safe(tokens, index + 2)
    if test_end is None or not _kw_at(tokens, test_end, ("IS", "NOT", "NULL")):
        return None
    then_at = test_end + 3
    if not _kw_at(tokens, then_at, ("THEN",)):
        return None
    value_end = _parse_safe(tokens, then_at + 1)
    if value_end is None or not _kw_at(tokens, value_end, ("ELSE",)):
        return None
    fallback_end = _parse_safe(tokens, value_end + 1)
    if fallback_end is None or not _kw_at(tokens, fallback_end, ("END",)):
        return None
    test = tokens[index + 2 : test_end]
    value = tokens[then_at + 1 : value_end]
    if not test or not value or _norm(test) != _norm(value):
        return None
    fallback = tokens[value_end + 1 : fallback_end]
    if not fallback:
        return None
    replacement = f"COALESCE({_slice(sql, test)}, {_slice(sql, fallback)})"
    return fallback_end + 1, tokens[index].start, tokens[fallback_end].end, replacement


def _apply_case_to_coalesce(query: str) -> str | None:
    try:
        tokens = tokenize(query)
    except ScanError:
        return None
    if not _is_read_only(tokens):
        return None
    spans: list[tuple[int, int, str]] = []
    index = 0
    while index < len(tokens):
        tok = tokens[index]
        if tok.kind == "kw" and tok.text.upper() == "CASE":
            parsed = _try_case(query, tokens, index)
            if parsed is not None:
                next_index, start, end, replacement = parsed
                spans.append((start, end, replacement))
                index = next_index
                continue
        index += 1
    if not spans:
        return None
    rewritten = query
    for start, end, replacement in reversed(spans):
        rewritten = rewritten[:start] + replacement + rewritten[end:]
    if rewritten == query:
        return None
    return rewritten


def same_statement(left: str, right: str) -> bool:
    """True when two statements are the same certified text.

    Keyword case and whitespace outside tokens may differ, and one trailing
    semicolon is ignored. Unquoted identifiers, strings, quoted identifiers,
    dollar quotes, and whitespace inside those tokens must match the source
    text. A comment difference is a difference. A scan failure is not a match.
    """
    try:
        left_tokens = tokenize(left)
        right_tokens = tokenize(right)
    except ScanError:
        return False
    left_body = _body(left_tokens)
    right_body = _body(right_tokens)
    if left_body is None or right_body is None or len(left_body) != len(right_body):
        return False
    for one, other in zip(left_body, right_body):
        if one.kind != other.kind:
            return False
        if one.kind == "kw":
            if one.text.upper() != other.text.upper():
                return False
        elif one.text != other.text:
            return False
    return _comment_gaps(left, left_tokens) == _comment_gaps(right, right_tokens)


def _comment_gaps(sql: str, tokens: list[Tok]) -> tuple[str, ...]:
    """Comment text between tokens. Whitespace-only gaps are ignored."""
    gaps: list[str] = []
    cursor = 0
    for tok in tokens:
        gap = sql[cursor:tok.start]
        if gap.strip():
            gaps.append(gap.strip())
        cursor = tok.end
    tail = sql[cursor:]
    if tail.strip():
        gaps.append(tail.strip())
    return tuple(gaps)


_IMPL = {
    "double_negation": _apply_double_negation,
    "demorgan": _apply_demorgan,
    "case_to_coalesce": _apply_case_to_coalesce,
}
