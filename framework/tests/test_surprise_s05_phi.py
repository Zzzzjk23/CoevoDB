"""Spec checking and the three-dimensional unit projection."""
from __future__ import annotations

import pytest

from surprise.features import check_spec, make_phi, unit_of, unit_parts
from surprise.gates.s05_cases import SPEC_PROBES, UNIT_PROBES
from surprise.harness.contracts import ORACLE_IDS
from surprise.theory.contracts import Spec

ALL_OK = {"ast": "ok", "plan": "ok", "data": "ok"}


def _phi(engine: str, features: tuple[str, ...], layers: dict[str, str]):
    return make_phi(engine, features, dict(layers))


def test_spec_probes_match_the_gate_table() -> None:
    for index, (engine, features, layers, fields, expected) in enumerate(SPEC_PROBES):
        result = check_spec(_phi(engine, features, layers), Spec(**fields))
        got = (result.ok, tuple(result.missing), tuple(result.forbidden), tuple(result.undetermined))
        assert got == expected, index
        assert result.engine_ok is (fields["engine"] == engine)


def test_spec_rejects_unknown_and_non_data_properties() -> None:
    phi = _phi("duckdb", ("ast:stmt:select",), ALL_OK)
    for bad in (
        dict(required=("ast:no_such_feature",)),
        dict(forbidden=("nope",)),
        dict(data_properties=("ast:clause:where",)),
        dict(data_properties=("plan:HASH_JOIN",)),
    ):
        with pytest.raises(ValueError):
            check_spec(phi, Spec(engine="duckdb", oracle="tlp", **bad))


def test_spec_undetermined_when_a_layer_was_not_computed() -> None:
    ast_only = {"ast": "ok", "plan": "skipped", "data": "skipped"}
    features = ("ast:stmt:select", "ast:set_op:except_all")
    present = check_spec(
        _phi("postgres", features, ast_only),
        Spec(engine="postgres", oracle="tlp", required=("ast:set_op:all",)),
    )
    assert present.ok is True
    assert present.missing == present.forbidden == present.undetermined == ()

    data_missing = check_spec(
        _phi("postgres", features, ast_only),
        Spec(
            engine="postgres",
            oracle="tlp",
            required=("ast:set_op:all",),
            data_properties=("data:setop:left_has_dups",),
        ),
    )
    assert data_missing.ok is False
    assert data_missing.missing == ()
    assert data_missing.forbidden == ()
    assert data_missing.undetermined == ("data:setop:left_has_dups",)

    plan_forbidden = check_spec(
        _phi("postgres", features, ast_only),
        Spec(engine="postgres", oracle="tlp", forbidden=("plan:HASH_JOIN", "ast:window")),
    )
    assert plan_forbidden.ok is False
    assert plan_forbidden.forbidden == ()
    assert plan_forbidden.undetermined == ("plan:HASH_JOIN",)

    unavailable = {"ast": "ok", "plan": "unavailable", "data": "unavailable"}
    both = check_spec(
        _phi("duckdb", ("ast:stmt:select",), unavailable),
        Spec(
            engine="duckdb",
            oracle="tlp",
            required=("plan:HASH_JOIN",),
            forbidden=("data:table:empty",),
        ),
    )
    assert both.ok is False
    assert both.missing == ()
    assert both.forbidden == ()
    assert both.undetermined == ("data:table:empty", "plan:HASH_JOIN")


def test_spec_class_and_family_in_required_use_the_closure() -> None:
    dfa = (
        "ast:stmt:select",
        "ast:set_op:except_all",
        "data:setop:left_has_dups",
        "data:table:dup_rows",
        "plan:HashJoinExec",
    )
    result = check_spec(
        _phi("datafusion", dfa, ALL_OK),
        Spec(engine="datafusion", oracle="cross_dbms", required=("ast:set_op", "plan", "data:setop")),
    )
    assert result.ok is True


def test_unit_probes_match_the_gate_table() -> None:
    for engine, oracle, features, layers, expected in UNIT_PROBES:
        got = unit_of(_phi(engine, features, layers), oracle)
        assert got == expected, (engine, oracle, features)


def test_unit_of_rejects_unknown_oracle() -> None:
    phi = _phi("duckdb", ("ast:stmt:select",), ALL_OK)
    with pytest.raises(ValueError):
        unit_of(phi, "no_such_oracle")
    for oracle in ORACLE_IDS:
        assert unit_of(phi, oracle).startswith(f"duckdb|{oracle}|")


def test_construct_priority() -> None:
    order = [
        (("ast:stmt:merge", "ast:set_op:union_all", "ast:window_fn:ranking"), "dml"),
        (("ast:set_op:except_all", "ast:window_fn:ranking"), "set_op_all"),
        (("ast:set_op:union", "ast:window_fn:ranking"), "set_op"),
        (("ast:window_fn:ranking", "ast:subquery_trait:correlated"), "window"),
        (("ast:subquery_trait:correlated", "ast:subquery:exists", "ast:join:asof"), "correlated_subquery"),
        (("ast:subquery:in", "ast:join:left"), "subquery"),
        (("ast:join:asof", "ast:join:left"), "asof_join"),
        (("ast:join:left", "ast:join:inner", "ast:agg:sum"), "outer_join"),
        (("ast:join:inner", "ast:agg:sum"), "join"),
        (("ast:agg:count", "ast:clause:distinct"), "aggregate"),
        (("ast:group:by",), "aggregate"),
        (("ast:clause:distinct",), "distinct"),
        (("ast:stmt:select", "ast:clause:where"), "plain"),
    ]
    for features, expected in order:
        construct, _, _ = unit_parts(_phi("duckdb", features, ALL_OK))
        assert construct == expected, features


def test_plan_class_priority() -> None:
    order = [
        (("plan:ASOF_JOIN", "plan:WINDOW", "plan:HASH_JOIN"), "asof_join"),
        (("plan:RIGHT_DELIM_JOIN", "plan:WINDOW"), "delim_join"),
        (("plan:STREAMING_WINDOW", "plan:HASH_JOIN"), "window"),
        (("plan:HASH_JOIN", "plan:HASH_GROUP_BY"), "join"),
        (("plan:CROSS_PRODUCT",), "join"),
        (("plan:UNION", "plan:TOP_N"), "union"),
        (("plan:RecursiveQueryExec",), "union"),
        (("plan:HASH_GROUP_BY", "plan:ORDER_BY"), "aggregate"),
        (("plan:AggregateExec", "plan:SortExec"), "aggregate"),
        (("plan:ORDER_BY",), "sort"),
        (("plan:TOP_N",), "sort"),
        (("plan:SEQ_SCAN", "plan:FILTER"), "scan"),
        (("plan:MERGE_INTO",), "scan"),
        ((), "scan"),
    ]
    for operators, expected in order:
        features = ("ast:stmt:select",) + operators
        _, plan_class, _ = unit_parts(_phi("duckdb", features, ALL_OK))
        assert plan_class == expected, operators
    skipped = {"ast": "ok", "plan": "skipped", "data": "ok"}
    _, plan_class, _ = unit_parts(_phi("duckdb", ("ast:stmt:select",), skipped))
    assert plan_class == "none"
    unavailable = {"ast": "ok", "plan": "unavailable", "data": "ok"}
    _, plan_class, _ = unit_parts(_phi("duckdb", ("ast:stmt:select",), unavailable))
    assert plan_class == "none"


def test_data_class_priority() -> None:
    order = [
        (("data:table:dup_rows", "data:table:has_null", "data:table:empty"), "dups"),
        (("data:setop:right_has_dups", "data:value:non_finite"), "dups"),
        (("data:setop:left_has_null", "data:table:empty"), "nulls"),
        (("data:table:empty", "data:value:extreme_number"), "empty"),
        (("data:value:non_finite", "data:value:zero"), "extreme"),
        (("data:value:extreme_number",), "extreme"),
        (("data:value:zero", "data:type:integer", "data:table:single_row"), "plain"),
    ]
    for extras, expected in order:
        features = ("ast:stmt:select",) + extras
        _, _, data_class = unit_parts(_phi("duckdb", features, ALL_OK))
        assert data_class == expected, extras
    skipped = {"ast": "ok", "plan": "ok", "data": "skipped"}
    _, _, data_class = unit_parts(_phi("duckdb", ("ast:stmt:select",), skipped))
    assert data_class == "unknown"
    unavailable = {"ast": "ok", "plan": "ok", "data": "unavailable"}
    _, _, data_class = unit_parts(_phi("duckdb", ("ast:stmt:select",), unavailable))
    assert data_class == "unknown"
