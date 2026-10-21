"""Mutation operators and the oracles a case is offered to."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import replace

from evolution.dce import mutate_query_text, mutate_setup
from surprise.harness.contracts import ORACLE_IDS, SqlCase
from surprise.harness.oracles.rewrites import RULES as _REWRITE_RULES

RULES: tuple[str, ...] = tuple(_REWRITE_RULES)

_INSERT_HEAD = re.compile(r"\s*INSERT\b", re.IGNORECASE)


def case_digest(case: SqlCase) -> str:
    """16-hex digest of the canonical JSON form of ``case``."""
    blob = json.dumps(case.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def mutants(case: SqlCase) -> list[tuple[SqlCase, str]]:
    """Deterministic neighbours of ``case``. The original case is not included."""
    found: list[tuple[SqlCase, str]] = []
    seen: set[str] = {case_digest(case)}

    def _keep(mutant: SqlCase, op: str) -> None:
        digest = case_digest(mutant)
        if digest in seen:
            return
        seen.add(digest)
        found.append((mutant, op))

    for text, op in mutate_query_text(case.query):
        try:
            _keep(replace(case, query=text), "q:" + op)
        except ValueError:
            continue
    if case.predicate:
        for text, op in mutate_query_text(case.predicate):
            try:
                _keep(replace(case, predicate=text), "p:" + op)
            except ValueError:
                continue
    for setup, op in mutate_setup(list(case.setup)):
        try:
            _keep(replace(case, setup=tuple(setup)), "s:" + op)
        except ValueError:
            continue
    for index, statement in enumerate(case.setup):
        split = _split_values_rows(statement)
        if split is None:
            continue
        prefix, rows, suffix = split
        for row_index in range(len(rows)):
            kept = [row for j, row in enumerate(rows) if j != row_index]
            rewritten = prefix + ", ".join(kept) + suffix
            new_setup = list(case.setup)
            new_setup[index] = rewritten
            try:
                _keep(replace(case, setup=tuple(new_setup)), f"s:drop_row[{index}][{row_index}]")
            except ValueError:
                continue
    for index, statement in enumerate(case.setup):
        if not _INSERT_HEAD.match(statement):
            continue
        new_setup = tuple(item for j, item in enumerate(case.setup) if j != index)
        try:
            _keep(replace(case, setup=new_setup), f"s:drop_insert[{index}]")
        except ValueError:
            continue
    return found


def oracle_options(
    case: SqlCase,
    oracles: Sequence[str],
    extra_rules: Sequence[str] = (),
) -> list[tuple[str, str | None]]:
    """Which (oracle, rule) pairs ``case`` may be judged under, in ``oracles`` order.

    ``equivalent_query`` offers the frozen rules, then ``extra_rules`` in the
    given order. An extra id that repeats a frozen rule is dropped.
    """
    options: list[tuple[str, str | None]] = []
    for oracle in oracles:
        if oracle not in ORACLE_IDS:
            raise ValueError(f"unknown oracle: {oracle!r}")
        if oracle in ("tlp", "norec"):
            if case.predicate:
                options.append((oracle, None))
            continue
        if oracle == "equivalent_query":
            for rule in RULES:
                options.append((oracle, rule))
            frozen = set(RULES)
            for rule in extra_rules:
                if rule in frozen:
                    continue
                options.append((oracle, rule))
            continue
        if oracle == "index_presence":
            if case.engine in ("duckdb", "postgres"):
                options.append((oracle, None))
            continue
        options.append((oracle, None))
    return options


def _split_values_rows(statement: str) -> tuple[str, list[str], str] | None:
    """Prefix, top-level VALUES rows, and suffix of a multi-row INSERT. Else None."""
    if not _INSERT_HEAD.match(statement):
        return None
    values_at = _keyword_end(statement, "VALUES")
    if values_at is None:
        return None
    index = values_at
    length = len(statement)
    rows: list[str] = []
    first_start: int | None = None
    last_end: int | None = None
    while True:
        while index < length and statement[index].isspace():
            index += 1
        if index >= length or statement[index] != "(":
            break
        end = _matching_paren(statement, index)
        if end is None:
            return None
        if first_start is None:
            first_start = index
        rows.append(statement[index : end + 1])
        last_end = end
        index = end + 1
        while index < length and statement[index].isspace():
            index += 1
        if index < length and statement[index] == ",":
            index += 1
            continue
        break
    if len(rows) < 2 or first_start is None or last_end is None:
        return None
    return statement[:first_start], rows, statement[last_end + 1 :]


def _keyword_end(text: str, word: str) -> int | None:
    """Index just after ``word`` as a keyword outside quoted strings, or None."""
    upper = text.upper()
    target = word.upper()
    index = 0
    length = len(text)
    in_string = False
    while index < length:
        char = text[index]
        if in_string:
            if char == "'":
                if index + 1 < length and text[index + 1] == "'":
                    index += 2
                    continue
                in_string = False
            index += 1
            continue
        if char == "'":
            in_string = True
            index += 1
            continue
        if upper.startswith(target, index):
            before_ok = index == 0 or not _is_ident(text[index - 1])
            after = index + len(target)
            after_ok = after == length or not _is_ident(text[after])
            if before_ok and after_ok:
                return after
        index += 1
    return None


def _matching_paren(text: str, start: int) -> int | None:
    """Index of the parenthesis that closes ``text[start]``, respecting quotes."""
    depth = 0
    index = start
    length = len(text)
    in_string = False
    while index < length:
        char = text[index]
        if in_string:
            if char == "'":
                if index + 1 < length and text[index + 1] == "'":
                    index += 2
                    continue
                in_string = False
            index += 1
            continue
        if char == "'":
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _is_ident(char: str) -> bool:
    return char.isalnum() or char == "_"
