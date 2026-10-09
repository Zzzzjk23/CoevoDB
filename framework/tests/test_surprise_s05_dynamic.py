"""Plan layer, data layer, extract, isolation, and the phi / corpus commands."""
from __future__ import annotations

import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from oracles.db_runner import QueryResult
from surprise.features import extract, extract_isolated
from surprise.features.data import _absorb_value, _type_feature
from surprise.harness.contracts import SqlCase

FRAMEWORK = Path(__file__).resolve().parents[1]
EXCEPT_ALL = "SELECT v FROM t EXCEPT ALL SELECT v FROM u"


def _case(engine: str, setup: tuple[str, ...], query: str, predicate: str | None = None) -> SqlCase:
    return SqlCase(engine=engine, setup=setup, query=query, predicate=predicate)


def _data(phi) -> set[str]:
    return {feature for feature in phi.features if feature.startswith("data:")}


def _plan(phi) -> set[str]:
    return {feature for feature in phi.features if feature.startswith("plan:")}


def _run(*args: str, stdin: str | None = None, timeout: float = 120.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "surprise.features", *args],
        cwd=FRAMEWORK,
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )


# ---- type names and corner values (no engine) --------------------------------


@pytest.mark.parametrize(
    ("type_name", "feature"),
    [
        ("INTEGER", "data:type:integer"),
        ("BIGINT", "data:type:integer"),
        ("Int32", "data:type:integer"),
        ("UInt64", "data:type:integer"),
        ("DOUBLE", "data:type:float"),
        ("Float64", "data:type:float"),
        ("REAL", "data:type:float"),
        ("DECIMAL(10,2)", "data:type:decimal"),
        ("Decimal128(10, 2)", "data:type:decimal"),
        ("NUMERIC(4,1)", "data:type:decimal"),
        ("VARCHAR", "data:type:string"),
        ("Utf8View", "data:type:string"),
        ("BOOLEAN", "data:type:boolean"),
        ("Boolean", "data:type:boolean"),
        ("DATE", "data:type:date"),
        ("Date32", "data:type:date"),
        ("TIMESTAMP", "data:type:timestamp"),
        ("Timestamp(Nanosecond, None)", "data:type:timestamp"),
        ("TIMESTAMP WITH TIME ZONE", "data:type:timestamp"),
        ("BLOB", "data:type:other"),
        ("INTERVAL", "data:type:other"),
        ("TIME", "data:type:other"),
    ],
)
def test_type_names_map_onto_the_vocabulary(type_name: str, feature: str) -> None:
    assert _type_feature(type_name) == feature


def test_corner_values_see_python_floats_and_ignore_booleans() -> None:
    flags: set[str] = set()
    for value in (False, True):
        _absorb_value(value, flags)
    assert flags == set()
    _absorb_value(0, flags)
    _absorb_value(-3, flags)
    _absorb_value(2147483647, flags)
    _absorb_value(-(2147483647), flags)
    assert "data:value:zero" in flags
    assert "data:value:negative" in flags
    assert "data:value:extreme_number" not in flags
    flags.clear()
    _absorb_value(-(2**31), flags)
    _absorb_value(2**31, flags)
    _absorb_value(float("nan"), flags)
    _absorb_value(float("inf"), flags)
    _absorb_value(float("-inf"), flags)
    _absorb_value(Decimal("0"), flags)
    _absorb_value(Decimal("-1.25"), flags)
    _absorb_value("", flags)
    _absorb_value("float:nan", flags)
    _absorb_value("float:+inf", flags)
    _absorb_value("float:-inf", flags)
    assert flags == {
        "data:value:extreme_number",
        "data:value:negative",
        "data:value:non_finite",
        "data:value:zero",
        "data:value:empty_string",
    }


# ---- plans -------------------------------------------------------------------


def test_duckdb_plan_names_come_from_explain_json() -> None:
    case = _case(
        "duckdb",
        ("CREATE TABLE t(v INT)", "INSERT INTO t VALUES (1),(2)", "CREATE TABLE u(v INT)", "INSERT INTO u VALUES (1)"),
        "SELECT t.v FROM t JOIN u ON t.v = u.v",
    )
    phi = extract(case)
    assert phi.layers["plan"] == "ok"
    assert "plan:HASH_JOIN" in phi.features
    assert "plan:SEQ_SCAN" in phi.features
    scan = extract(_case("duckdb", ("CREATE TABLE t(v INT)", "INSERT INTO t VALUES (1)"), "SELECT v FROM t"))
    assert "plan:SEQ_SCAN" in scan.features
    assert "plan:HASH_JOIN" not in scan.features


def test_datafusion_plan_names_come_from_physical_plan_text() -> None:
    case = _case(
        "datafusion",
        ("CREATE TABLE t(v INT)", "INSERT INTO t VALUES (1),(1),(2)", "CREATE TABLE u(v INT)", "INSERT INTO u VALUES (1)"),
        EXCEPT_ALL,
    )
    phi = extract(case)
    assert phi.layers["plan"] == "ok"
    assert {"plan:HashJoinExec", "plan:DataSourceExec"} <= _plan(phi)
    filtered = extract(
        _case("datafusion", ("CREATE TABLE t(v INT)", "INSERT INTO t VALUES (1),(4)"), "SELECT v FROM t WHERE v > 0")
    )
    assert "plan:FilterExec" in filtered.features
    assert "plan:DataSourceExec" in filtered.features


def test_plan_skips_operator_names_outside_the_token_alphabet() -> None:
    class Runner:
        def setup(self, _stmts):
            return []

        def run(self, sql, timeout_s=10.0):
            result = QueryResult()
            result.rows = [["physical_plan", "Hash-Join: mode=x\nDataSourceExec: partitions=1\n"]]
            return result

        def close(self):
            return None

    phi = extract(
        _case("datafusion", (), "SELECT v FROM t"),
        runner_factory=Runner,
    )
    assert phi.layers["plan"] == "ok"
    assert "plan:DataSourceExec" in phi.features
    assert all("Hash-Join" not in feature for feature in phi.features)


# ---- data layer --------------------------------------------------------------


def test_duckdb_data_features_positive_and_negative() -> None:
    rich = extract(
        _case(
            "duckdb",
            (
                "CREATE TABLE m(i BIGINT, x DOUBLE, s VARCHAR)",
                "INSERT INTO m VALUES (0, -1.5, ''), (9223372036854775807, 'nan', 'a')",
            ),
            "SELECT i, x, s FROM m",
        )
    )
    assert rich.layers["data"] == "ok"
    assert {
        "data:value:zero",
        "data:value:negative",
        "data:value:empty_string",
        "data:value:extreme_number",
        "data:value:non_finite",
        "data:type:integer",
        "data:type:float",
        "data:type:string",
    } <= _data(rich)
    assert "data:table:has_null" not in rich.features
    assert "data:type:decimal" not in rich.features

    plain = extract(
        _case(
            "duckdb",
            ("CREATE TABLE m(i INT, s VARCHAR)", "INSERT INTO m VALUES (1, 'a'), (2147483647, 'b')"),
            "SELECT i FROM m",
        )
    )
    assert "data:type:integer" in plain.features
    assert "data:type:string" in plain.features
    for feature in (
        "data:value:zero",
        "data:value:negative",
        "data:value:empty_string",
        "data:value:extreme_number",
        "data:value:non_finite",
    ):
        assert feature not in plain.features

    flags = extract(
        _case("duckdb", ("CREATE TABLE b(flag BOOLEAN)", "INSERT INTO b VALUES (false), (true)"), "SELECT flag FROM b")
    )
    assert "data:type:boolean" in flags.features
    assert "data:value:zero" not in flags.features
    assert "data:value:negative" not in flags.features

    kinds = extract(
        _case(
            "duckdb",
            (
                "CREATE TABLE k(d DATE, ts TIMESTAMP, n DECIMAL(10,2), b BOOLEAN, g BLOB)",
                "INSERT INTO k VALUES (DATE '2020-01-02', TIMESTAMP '2020-01-02 03:04:05', 1.25, true, 'x'::BLOB)",
            ),
            "SELECT d FROM k",
        )
    )
    assert {
        "data:type:date",
        "data:type:timestamp",
        "data:type:decimal",
        "data:type:boolean",
        "data:type:other",
    } <= _data(kinds)
    assert "data:type:integer" not in kinds.features
    assert "data:type:string" not in kinds.features

    empty = extract(_case("duckdb", ("CREATE TABLE t(v INT)",), "SELECT v FROM t"))
    assert "data:table:empty" in empty.features
    assert "data:table:single_row" not in empty.features
    assert "data:table:has_null" not in empty.features

    one = extract(_case("duckdb", ("CREATE TABLE t(v INT)", "INSERT INTO t VALUES (NULL)"), "SELECT v FROM t"))
    assert "data:table:single_row" in one.features
    assert "data:table:has_null" in one.features
    assert "data:table:empty" not in one.features
    assert "data:table:dup_rows" not in one.features

    dups = extract(
        _case("duckdb", ("CREATE TABLE t(v INT)", "INSERT INTO t VALUES (1),(1)"), "SELECT v FROM t")
    )
    assert "data:table:dup_rows" in dups.features
    assert "data:table:single_row" not in dups.features


def test_datafusion_types_and_decimal_zero() -> None:
    phi = extract(
        _case(
            "datafusion",
            (
                "CREATE TABLE k(d DATE, n DECIMAL(10,2), b BOOLEAN, s VARCHAR, x DOUBLE)",
                "INSERT INTO k VALUES (DATE '2020-01-02', 0.00, false, '', -1.5), (DATE '2020-01-03', 1.25, true, 'a', 1.5)",
            ),
            "SELECT d FROM k",
        )
    )
    assert phi.layers["data"] == "ok"
    assert {
        "data:type:date",
        "data:type:decimal",
        "data:type:boolean",
        "data:type:string",
        "data:type:float",
        "data:value:zero",
        "data:value:negative",
        "data:value:empty_string",
    } <= _data(phi)
    assert "data:type:integer" not in phi.features
    assert "data:value:extreme_number" not in phi.features
    assert "data:value:non_finite" not in phi.features


def test_only_referenced_tables_count() -> None:
    phi = extract(
        _case(
            "duckdb",
            (
                "CREATE TABLE t(v INT)",
                "INSERT INTO t VALUES (NULL),(NULL)",
                "CREATE TABLE z(a INT)",
                "INSERT INTO z VALUES (7)",
            ),
            "SELECT a FROM z",
        )
    )
    assert "data:table:single_row" in phi.features
    assert "data:type:integer" in phi.features
    assert "data:table:has_null" not in phi.features
    assert "data:table:dup_rows" not in phi.features
    assert "data:table:empty" not in phi.features


def test_setop_features_describe_the_input_not_the_table() -> None:
    filtered = extract(
        _case(
            "duckdb",
            ("CREATE TABLE t(v INT)", "INSERT INTO t VALUES (1),(2),(2)", "CREATE TABLE u(v INT)", "INSERT INTO u VALUES (5)"),
            "SELECT v FROM t WHERE v = 1 EXCEPT ALL SELECT v FROM u",
        )
    )
    assert "data:table:dup_rows" in filtered.features
    assert "data:setop:left_has_dups" not in filtered.features

    projected = extract(
        _case(
            "duckdb",
            (
                "CREATE TABLE t(a INT, b INT)",
                "INSERT INTO t VALUES (1, 10), (1, 20)",
                "CREATE TABLE u(v INT)",
                "INSERT INTO u VALUES (5)",
            ),
            "SELECT a FROM t UNION ALL SELECT v FROM u",
        )
    )
    assert "data:setop:left_has_dups" in projected.features
    assert "data:table:dup_rows" not in projected.features
    assert "data:setop:right_has_dups" not in projected.features

    distinct = extract(
        _case(
            "duckdb",
            ("CREATE TABLE t(v INT)", "INSERT INTO t VALUES (2),(2),(NULL)", "CREATE TABLE u(v INT)", "INSERT INTO u VALUES (5)"),
            "SELECT DISTINCT v FROM t INTERSECT ALL SELECT v FROM u",
        )
    )
    assert "data:table:dup_rows" in distinct.features
    assert "data:setop:left_has_null" in distinct.features
    assert "data:setop:left_has_dups" not in distinct.features

    both = extract(
        _case(
            "datafusion",
            (
                "CREATE TABLE t(v INT)",
                "INSERT INTO t VALUES (1),(1),(2),(NULL)",
                "CREATE TABLE u(v INT)",
                "INSERT INTO u VALUES (1),(2),(NULL)",
            ),
            EXCEPT_ALL,
        )
    )
    assert "data:setop:left_has_dups" in both.features
    assert "data:setop:left_has_null" in both.features
    assert "data:setop:right_has_null" in both.features
    assert "data:setop:right_has_dups" not in both.features


def test_cte_names_and_table_functions_are_not_base_tables() -> None:
    cte = extract(
        _case(
            "duckdb",
            ("CREATE TABLE t(v INT)", "INSERT INTO t VALUES (1),(1)"),
            "WITH c AS (SELECT 1 AS v) SELECT v FROM t EXCEPT ALL SELECT v FROM c",
        )
    )
    assert cte.layers["data"] == "ok"
    assert "data:setop:left_has_dups" in cte.features
    assert "data:table:dup_rows" in cte.features

    functions = extract(_case("duckdb", (), "SELECT * FROM range(3)"))
    assert functions.layers["data"] == "ok"
    assert _data(functions) == set()

    constant = extract(_case("duckdb", (), "SELECT 1"))
    assert constant.layers["data"] == "ok"
    assert _data(constant) == set()

    joined = extract(
        _case(
            "duckdb",
            ("CREATE TABLE t(v INT)", "INSERT INTO t VALUES (1),(1)"),
            "SELECT * FROM t a JOIN t b ON a.v = b.v",
        )
    )
    assert joined.layers["data"] == "ok"
    assert "data:table:dup_rows" in joined.features


def test_outer_column_in_a_setop_input_is_skipped() -> None:
    phi = extract(
        _case(
            "duckdb",
            ("CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1),(2)", "CREATE TABLE u(v INT)", "INSERT INTO u VALUES (1),(1)"),
            "SELECT * FROM t WHERE EXISTS (SELECT v FROM u EXCEPT ALL SELECT t.a)",
        )
    )
    assert phi.layers["data"] == "ok"
    assert "data:setop:left_has_dups" in phi.features
    assert "data:setop:right_has_dups" not in phi.features
    assert "data:setop:right_has_null" not in phi.features


def test_tablesample_describes_the_whole_table() -> None:
    case = _case(
        "duckdb",
        ("CREATE TABLE s AS SELECT range AS i, range % 7 AS k FROM range(2000)",),
        "SELECT i FROM s TABLESAMPLE BERNOULLI (1 PERCENT)",
    )
    first = extract(case)
    assert first.layers["data"] == "ok"
    assert "data:value:zero" in first.features
    assert "data:type:integer" in first.features
    assert extract(case) == first
    assert extract(case) == first


def test_parenthesized_join_uses_the_same_tables() -> None:
    setup = (
        "CREATE TABLE a(x INT)",
        "INSERT INTO a VALUES (1)",
        "CREATE TABLE b(x INT)",
        "INSERT INTO b VALUES (1), (1)",
    )
    parenthesized = extract(_case("duckdb", setup, "SELECT * FROM (a JOIN b ON a.x = b.x)"))
    plain = extract(_case("duckdb", setup, "SELECT * FROM a JOIN b ON a.x = b.x"))
    assert parenthesized.layers["data"] == "ok"
    assert plain.layers["data"] == "ok"
    assert _data(parenthesized) == _data(plain)
    assert {"data:table:dup_rows", "data:table:single_row", "data:type:integer"} <= _data(parenthesized)


def test_setop_input_past_the_row_cap_drops_the_data_layer() -> None:
    setup = (
        "CREATE TABLE p AS SELECT range % 3 AS i FROM range(150)",
        "CREATE TABLE q(i INT)",
        "INSERT INTO q VALUES (1)",
    )
    over = extract(_case("duckdb", setup, "SELECT x.i FROM p x, p y EXCEPT ALL SELECT i FROM q"))
    assert over.layers["data"] == "unavailable"
    assert over.layers["plan"] == "ok"
    assert _data(over) == set()
    fits = extract(_case("duckdb", setup, "SELECT x.i FROM p x EXCEPT ALL SELECT i FROM q"))
    assert fits.layers["data"] == "ok"
    assert "data:setop:left_has_dups" in fits.features


def test_full_query_predicate_is_part_of_phi() -> None:
    phi = extract(
        _case("duckdb", ("CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1)"), "SELECT a FROM t", predicate="a > 0")
    )
    assert "ast:clause:where" in phi.features


# ---- extract contract --------------------------------------------------------


def test_failing_setup_drops_plan_and_data() -> None:
    phi = extract(
        _case(
            "duckdb",
            ("CREATE TABLE t(a INTEGER)", "INSERT INTO no_such_table VALUES (1)"),
            "SELECT a FROM t WHERE a > 0",
        )
    )
    assert dict(phi.layers) == {"ast": "ok", "plan": "unavailable", "data": "unavailable"}
    assert "ast:clause:where" in phi.features
    assert all(feature.startswith("ast:") for feature in phi.features)

    class Boom:
        def setup(self, _stmts):
            raise RuntimeError("setup exploded")

        def close(self):
            return None

    blown = extract(_case("duckdb", ("CREATE TABLE t(a INT)",), "SELECT a FROM t"), runner_factory=Boom)
    assert dict(blown.layers) == {"ast": "ok", "plan": "unavailable", "data": "unavailable"}


def test_ast_only_skips_the_runner_even_without_one() -> None:
    called = {"n": 0}

    def factory():
        called["n"] += 1
        raise AssertionError("runner should not be built")

    phi = extract(
        _case("postgres", (), "SELECT a FROM t JOIN u USING (k)"),
        layers=("ast",),
        runner_factory=factory,
    )
    assert called["n"] == 0
    assert dict(phi.layers) == {"ast": "ok", "plan": "skipped", "data": "skipped"}
    assert "ast:join_cond:using" in phi.features
    assert all(feature.startswith("ast:") for feature in phi.features)
    with pytest.raises(ValueError):
        extract(_case("postgres", (), "SELECT 1"))


def test_layers_must_include_ast_and_only_the_three_names() -> None:
    case = _case("duckdb", (), "SELECT 1")
    for layers in ((), ("plan",), ("ast", "nope"), ("ast", 1)):
        with pytest.raises(ValueError):
            extract(case, layers=layers)  # type: ignore[arg-type]


def test_extract_does_not_execute_the_statement_and_is_stable() -> None:
    query = "MERGE INTO t USING s ON t.a = s.a WHEN MATCHED THEN DELETE"
    seen: list[str] = []

    class Recording:
        def setup(self, stmts):
            return [(stmt, None) for stmt in stmts]

        def run(self, sql, timeout_s=10.0):
            seen.append(sql)
            result = QueryResult()
            if sql.startswith("EXPLAIN (FORMAT JSON)"):
                result.rows = [["physical_plan", json.dumps([{"name": "MERGE_INTO", "children": [{"name": "HASH_JOIN", "children": []}]}])]]
                return result
            if sql.startswith("DESCRIBE"):
                result.rows = [["a", "INTEGER"]]
                return result
            if sql.startswith("SELECT * FROM"):
                result.rows = [[1], [2]]
                return result
            result.error = "statement was executed"
            return result

        def close(self):
            seen.append("close")

    case = _case("duckdb", ("CREATE TABLE t(a INT)", "CREATE TABLE s(a INT)"), query)
    phi = extract(case, runner_factory=Recording)
    assert query not in seen
    assert "close" in seen
    assert phi.layers["plan"] == "ok"
    assert "plan:MERGE_INTO" in phi.features
    assert "plan:HASH_JOIN" in phi.features
    again = extract(
        _case(
            "duckdb",
            ("CREATE TABLE t(v INT)", "INSERT INTO t VALUES (1),(2)", "CREATE TABLE u(v INT)", "INSERT INTO u VALUES (1)"),
            EXCEPT_ALL,
        )
    )
    assert extract(
        _case(
            "duckdb",
            ("CREATE TABLE t(v INT)", "INSERT INTO t VALUES (1),(2)", "CREATE TABLE u(v INT)", "INSERT INTO u VALUES (1)"),
            EXCEPT_ALL,
        )
    ) == again


def test_extract_isolated_matches_extract_and_degrades_when_killed() -> None:
    case = _case(
        "duckdb",
        ("CREATE TABLE t(v INT)", "INSERT INTO t VALUES (1),(1)", "CREATE TABLE u(v INT)", "INSERT INTO u VALUES (2)"),
        EXCEPT_ALL,
    )
    assert extract_isolated(case) == extract(case)
    degraded = extract_isolated(case, timeout_s=0)
    assert degraded.layers["ast"] == "ok"
    assert dict(degraded.layers)["plan"] == "unavailable"
    assert degraded.layers["data"] == "unavailable"
    assert "ast:set_op:except_all" in degraded.features
    assert all(feature.startswith("ast:") for feature in degraded.features)


def test_extract_isolated_raises_caller_errors(tmp_path: Path) -> None:
    case = _case("duckdb", (), "SELECT 1")
    with pytest.raises(FileNotFoundError):
        extract_isolated(case, registry_path="no/such/registry.json")
    bad = tmp_path / "registry.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError):
        extract_isolated(case, registry_path=str(bad))
    with pytest.raises(ValueError):
        extract_isolated(SqlCase(engine="postgres", setup=(), query="SELECT 1"))
    ast_only = extract_isolated(SqlCase(engine="postgres", setup=(), query="SELECT 1"), layers=("ast",))
    assert dict(ast_only.layers) == {"ast": "ok", "plan": "skipped", "data": "skipped"}
    timed_out = extract_isolated(case, timeout_s=0.01)
    assert timed_out.layers["ast"] == "ok"
    assert timed_out.layers["plan"] == "unavailable"
    assert timed_out.layers["data"] == "unavailable"
    assert all(feature.startswith("ast:") for feature in timed_out.features)


# ---- commands ----------------------------------------------------------------


def test_phi_command_prints_canonical_json_and_rejects_bad_input(tmp_path: Path) -> None:
    case = _case("duckdb", ("CREATE TABLE t(v INT)", "INSERT INTO t VALUES (1)"), "SELECT v FROM t")
    payload = json.dumps({"case": case.to_dict()})
    run = _run("phi", stdin=payload)
    assert run.returncode == 0, run.stderr
    line = run.stdout.strip()
    here = extract(case)
    assert line == json.dumps(here.to_dict(), sort_keys=True, separators=(",", ":"))
    assert json.loads(line) == here.to_dict()
    for bad in ("", "[]", "{}", json.dumps({"case": {"engine": "duckdb"}}), json.dumps({"extra": 1, "case": case.to_dict()})):
        failed = _run("phi", stdin=bad)
        assert failed.returncode == 2
        assert failed.stderr.strip()
    missing_runner = _run("phi", stdin=json.dumps({"case": _case("postgres", (), "SELECT 1").to_dict()}))
    assert missing_runner.returncode == 2
    ast_only = _run(
        "phi",
        stdin=json.dumps({"case": _case("postgres", (), "SELECT a FROM t").to_dict(), "layers": ["ast"]}),
    )
    assert ast_only.returncode == 0
    body = json.loads(ast_only.stdout.strip())
    assert body["layers"] == {"ast": "ok", "data": "skipped", "plan": "skipped"}


def test_corpus_command_is_stable_on_a_small_corpus(tmp_path: Path) -> None:
    seeds = [
        {
            "engine": "duckdb",
            "setup_sqls": ["CREATE TABLE t(v INT)", "INSERT INTO t VALUES (1),(1)"],
            "query": "SELECT v FROM t",
        },
        {
            "engine": "duckdb",
            "setup_sqls": ["CREATE TABLE t(v INT)", "INSERT INTO missing VALUES (1)"],
            "query": "SELECT v FROM t WHERE v > 0",
        },
        {
            "engine": "postgres",
            "setup_sqls": ["CREATE TABLE t(v INT)"],
            "query": "SELECT v FROM t",
        },
    ]
    path = tmp_path / "seeds.json"
    path.write_text(json.dumps(seeds), encoding="utf-8")
    out = tmp_path / "units.json"
    again = tmp_path / "again.json"
    first = _run("corpus", "--corpus", str(path), "--out", str(out), "--limit", "3")
    second = _run("corpus", "--corpus", str(path), "--out", str(again))
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert out.read_bytes() == again.read_bytes()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["total"] == 3
    assert report["by_engine"] == {"duckdb": 2, "postgres": 1}
    assert report["distinct_units"] == len(report["units"])
    assert sum(report["units"].values()) == 3
    assert report["layers"]["plan"]["skipped"] == 1
    assert report["layers"]["plan"]["unavailable"] == 1
    assert report["layers"]["data"]["ok"] == 1
    assert "digest" in report["vocab"]
    text = first.stdout
    assert "total 3" in text
    assert "top_units" in text
    limited = _run("corpus", "--corpus", str(path), "--limit", "1")
    assert limited.returncode == 0
    assert "total 1" in limited.stdout
    vocab = _run("vocab")
    assert vocab.returncode == 0
    assert report["vocab"]["digest"] in vocab.stdout
