"""Mutation operators, row deletion, and oracle options."""

from __future__ import annotations

from dataclasses import replace

import pytest

from evolution.dce import mutate_query_text, mutate_setup
from surprise.gates import s08_cases as C
from surprise.harness.contracts import SqlCase
from surprise.harness.oracles.rewrites import RULES
from surprise.hunter import operators as O


def _case() -> SqlCase:
    return SqlCase(
        engine="duckdb",
        setup=(
            "CREATE TABLE t(a INT, b INT)",
            "INSERT INTO t VALUES (1, 2), (3, NULL), (3, NULL)",
            "INSERT INTO t VALUES (5, 6)",
        ),
        query="SELECT a FROM t WHERE a > 1 AND b <> 2",
        predicate="b IS NOT NULL",
    )


def test_mutants_reuse_dce_and_delete_rows_and_inserts() -> None:
    case = _case()
    found = O.mutants(case)
    ops = [op for _m, op in found]
    digests = [O.case_digest(m) for m, _op in found]
    assert len(set(digests)) == len(digests)
    assert O.case_digest(case) not in digests
    expected_q = {"q:" + op for _t, op in mutate_query_text(case.query)}
    expected_p = {"p:" + op for _t, op in mutate_query_text(case.predicate)}
    expected_s = {"s:" + op for _s, op in mutate_setup(list(case.setup))}
    assert expected_q <= set(ops)
    assert expected_p <= set(ops)
    assert expected_s <= set(ops)
    drops = {op: m for m, op in found if op.startswith("s:drop_")}
    assert "s:drop_row[1][0]" in drops and "s:drop_row[1][1]" in drops
    assert "s:drop_insert[1]" in drops and "s:drop_insert[2]" in drops
    # Rows 1 and 2 of the multi-row INSERT are the same tuple, so dropping either
    # yields the same case; case_digest keeps only the first (drop_row[1][1]).
    assert "s:drop_row[1][2]" not in drops
    assert drops["s:drop_row[1][1]"].setup[1] == "INSERT INTO t VALUES (1, 2), (3, NULL)"
    assert drops["s:drop_row[1][0]"].setup[1] == "INSERT INTO t VALUES (3, NULL), (3, NULL)"
    assert drops["s:drop_insert[2]"].setup == case.setup[:2]
    assert O.mutants(case) == found


def test_drop_row_respects_quotes_commas_parens_and_suffix() -> None:
    case = SqlCase(
        engine="duckdb",
        setup=(
            "INSERT INTO t VALUES ('a, (b)', 1), (2, 'it''s'), (3, (4, 5)) ON CONFLICT DO NOTHING",
        ),
        query="SELECT 1",
    )
    found = {op: m for m, op in O.mutants(case) if op.startswith("s:drop_row")}
    assert set(found) == {"s:drop_row[0][0]", "s:drop_row[0][1]", "s:drop_row[0][2]"}
    assert found["s:drop_row[0][0]"].setup[0] == "INSERT INTO t VALUES (2, 'it''s'), (3, (4, 5)) ON CONFLICT DO NOTHING"
    assert found["s:drop_row[0][1]"].setup[0] == "INSERT INTO t VALUES ('a, (b)', 1), (3, (4, 5)) ON CONFLICT DO NOTHING"
    assert found["s:drop_row[0][2]"].setup[0] == "INSERT INTO t VALUES ('a, (b)', 1), (2, 'it''s') ON CONFLICT DO NOTHING"


def test_single_row_insert_has_no_drop_row() -> None:
    case = SqlCase(
        engine="duckdb",
        setup=("CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1)"),
        query="SELECT a FROM t",
    )
    ops = [op for _m, op in O.mutants(case)]
    assert not any(op.startswith("s:drop_row") for op in ops)
    assert "s:drop_insert[1]" in ops
    assert "s:drop_insert[0]" not in ops


def test_case_digest_is_stable_and_sixteen_hex() -> None:
    case = _case()
    digest = O.case_digest(case)
    assert len(digest) == 16
    assert digest == O.case_digest(case)
    assert O.case_digest(replace(case, query=case.query + " ")) != digest


def test_oracle_options_filter_predicate_and_engine() -> None:
    case = _case()
    rules = tuple(RULES)
    assert O.RULES == rules
    assert O.oracle_options(case, C.ORACLES) == [
        ("tlp", None),
        ("norec", None),
        ("plan_variant", None),
        ("index_presence", None),
        *[("equivalent_query", r) for r in rules],
        ("version_differential", None),
        ("cross_dbms", None),
    ]
    bare = replace(case, predicate=None, engine="datafusion")
    assert O.oracle_options(bare, C.ORACLES) == [
        ("plan_variant", None),
        *[("equivalent_query", r) for r in rules],
        ("version_differential", None),
        ("cross_dbms", None),
    ]
    with pytest.raises(ValueError):
        O.oracle_options(case, ("no_such_oracle",))
