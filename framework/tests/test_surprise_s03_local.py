"""DuckDB ART index presence and the certified equivalent-query rules."""

from __future__ import annotations

from oracles.db_runner import QueryResult
from oracles.normalize import loose_bag
from surprise.harness.contracts import SqlCase
from surprise.harness.oracles import judge
from surprise.harness.oracles.equivalent_query import judge_case as judge_equivalent
from surprise.harness.oracles.index_presence import judge_case as judge_index
from surprise.harness.oracles.registry import OracleOptions
from surprise.harness.oracles.rewrites import RULES, apply_rule
from targets.datafusion_runner import DataFusionRunner
from targets.duckdb_runner import DuckDBRunner

_SETUP = (
    "CREATE TABLE t(a INT, b INT)",
    "INSERT INTO t VALUES (1,1),(2,NULL),(3,3)",
)
_DUP_SETUP = (
    "CREATE TABLE t(a INT, b INT)",
    "INSERT INTO t VALUES (1,1),(1,1),(2,NULL),(2,NULL),(3,3),(3,3)",
)
_OPTIONS = OracleOptions()


def _case(query: str, setup: tuple[str, ...] = _SETUP, engine: str = "duckdb",
          predicate: str | None = None) -> SqlCase:
    return SqlCase(engine=engine, setup=setup, query=query, predicate=predicate)


def _assert_ternary(label, y: str, reason: str | None = None, kind: str | None = None) -> None:
    assert label.cve == {}
    assert label.y == y
    if y == "invalid":
        assert label.invalid_reason == reason
        assert label.fail_kind is None
    elif y == "fail":
        assert label.fail_kind == kind
        assert label.invalid_reason is None
    else:
        assert label.fail_kind is None
        assert label.invalid_reason is None


class _Trace(DuckDBRunner):
    """Real DuckDB runner that records every statement passed to run."""

    def __init__(self) -> None:
        super().__init__()
        self.runs: list[str] = []
        self.setups = 0
        self.closed = 0

    def setup(self, schema_sqls):
        self.setups += 1
        return super().setup(schema_sqls)

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        self.runs.append(sql)
        return super().run(sql, timeout_s=timeout_s)

    def close(self) -> None:
        self.closed += 1
        super().close()


def _traced(opened: list[_Trace]):
    def factory():
        runner = _Trace()
        opened.append(runner)
        return runner

    return factory


class _Scripted:
    """In-memory runner. Screen setup does not execute the statement under test."""

    def __init__(self, on_create, on_query) -> None:
        self.on_create = on_create
        self.on_query = on_query
        self.runs: list[str] = []
        self.setups = 0
        self.closed = 0
        self.queries = 0

    def setup(self, schema_sqls):
        self.setups += 1
        return [(statement, None) for statement in schema_sqls]

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        self.runs.append(sql)
        upper = sql.upper()
        if "CREATE" in upper and "INDEX" in upper:
            return self.on_create(sql)
        if upper.startswith("DROP INDEX"):
            return QueryResult(rows=[])
        self.queries += 1
        return self.on_query(sql, self.queries)

    def close(self) -> None:
        self.closed += 1


def _scripted(opened: list[_Scripted], on_create, on_query):
    def factory():
        runner = _Scripted(on_create, on_query)
        opened.append(runner)
        return runner

    return factory


def _rows_of(setup: tuple[str, ...], query: str) -> list[list]:
    runner = DuckDBRunner()
    try:
        assert all(error is None for _statement, error in runner.setup(setup))
        result = runner.run(query)
        assert result.ok, result.error
        return result.rows
    finally:
        runner.close()


def _bag(rows) -> object:
    return loose_bag(rows)


# ---- rewrites ---------------------------------------------------------------


def test_rules_carry_three_valued_proofs() -> None:
    assert set(RULES) >= {"double_negation", "demorgan", "case_to_coalesce"}
    for rule_id, spec in RULES.items():
        assert isinstance(spec["proof"], str) and len(spec["proof"]) >= 30, rule_id


def test_gate_rewrites_match_the_proved_shapes() -> None:
    assert apply_rule("SELECT a FROM t WHERE b > 1", "double_negation") == (
        "SELECT a FROM t WHERE NOT (NOT (b > 1))"
    )
    assert apply_rule("SELECT a FROM t WHERE NOT (b > 1 AND a < 3)", "demorgan") == (
        "SELECT a FROM t WHERE (NOT (b > 1)) OR (NOT (a < 3))"
    )
    assert apply_rule(
        "SELECT CASE WHEN b IS NOT NULL THEN b ELSE 0 END AS v FROM t",
        "case_to_coalesce",
    ) == "SELECT COALESCE(b, 0) AS v FROM t"
    assert apply_rule("SELECT 1", "demorgan") is None
    assert apply_rule("SELECT 1", "invented_rule") is None


def test_null_duplicate_and_comment_boundaries_stay_equivalent() -> None:
    wrapped = apply_rule("SELECT a FROM t WHERE b > 1", "double_negation")
    demorgan = apply_rule("SELECT a FROM t WHERE NOT (b > 1 AND a < 3)", "demorgan")
    coalesced = apply_rule(
        "SELECT CASE WHEN b IS NOT NULL THEN b ELSE 0 END AS v FROM t",
        "case_to_coalesce",
    )
    assert wrapped is not None and demorgan is not None and coalesced is not None
    # Two copies of (3, 3) stay two rows; the NULL predicate stays out of WHERE.
    assert _bag(_rows_of(_DUP_SETUP, "SELECT a FROM t WHERE b > 1")) == _bag([[3], [3]])
    assert _bag(_rows_of(_DUP_SETUP, wrapped)) == _bag([[3], [3]])
    assert _bag(_rows_of(_DUP_SETUP, "SELECT a FROM t WHERE NOT (b > 1 AND a < 3)")) == _bag(
        [[1], [1], [3], [3]]
    )
    assert _bag(_rows_of(_DUP_SETUP, demorgan)) == _bag([[1], [1], [3], [3]])
    assert _bag(_rows_of(
        _DUP_SETUP, "SELECT CASE WHEN b IS NOT NULL THEN b ELSE 0 END AS v FROM t",
    )) == _bag([[1], [1], [0], [0], [3], [3]])
    assert _bag(_rows_of(_DUP_SETUP, coalesced)) == _bag([[1], [1], [0], [0], [3], [3]])

    commented = "SELECT a FROM t WHERE NOT (b > 1 /* AND */ AND a < 3) -- tail"
    rewritten = apply_rule(commented, "demorgan")
    assert rewritten is not None
    assert rewritten.endswith("-- tail")
    assert "/* AND */" not in rewritten.split("--")[0]
    assert _bag(_rows_of(_SETUP, commented)) == _bag(_rows_of(_SETUP, rewritten))


def test_counterexamples_are_declined_when_a_naive_rewrite_would_differ() -> None:
    # Different THEN is not COALESCE(b, 0). Here a and b differ on non-NULL rows,
    # so the CASE yields a while COALESCE(b, 0) yields b.
    unequal = (
        "CREATE TABLE t(a INT, b INT)",
        "INSERT INTO t VALUES (1,10),(2,NULL),(3,3)",
    )
    different_then = "SELECT CASE WHEN b IS NOT NULL THEN a ELSE 0 END AS v FROM t"
    assert apply_rule(different_then, "case_to_coalesce") is None
    assert _bag(_rows_of(unequal, different_then)) != _bag(
        _rows_of(unequal, "SELECT COALESCE(b, 0) AS v FROM t")
    )
    # Parentheses make the test and the THEN text different expressions.
    assert apply_rule(
        "SELECT CASE WHEN (b) IS NOT NULL THEN b ELSE 0 END AS v FROM t",
        "case_to_coalesce",
    ) is None
    # Arithmetic binds tighter than IS, so this is not "x IS NOT NULL" for x = b + 0.
    assert apply_rule(
        "SELECT CASE WHEN b + 0 IS NOT NULL THEN b + 0 ELSE 0 END AS v FROM t",
        "case_to_coalesce",
    ) is None
    assert apply_rule(
        "SELECT CASE WHEN b IS NULL THEN 0 ELSE b END AS v FROM t",
        "case_to_coalesce",
    ) is None
    assert apply_rule(
        "SELECT CASE b WHEN 1 THEN 1 ELSE 0 END AS v FROM t",
        "case_to_coalesce",
    ) is None

    literal = "SELECT 'CASE WHEN b IS NOT NULL THEN b ELSE 0 END' AS v FROM t"
    assert apply_rule(literal, "case_to_coalesce") is None
    assert _bag(_rows_of(_SETUP, literal)) != _bag(
        _rows_of(_SETUP, "SELECT 'COALESCE(b, 0)' AS v FROM t")
    )
    assert apply_rule("SELECT a FROM t WHERE note <> 'NOT (a AND b)'", "demorgan") is None
    assert apply_rule(
        "SELECT 'WHERE b > 1' AS v FROM t WHERE b > 1", "double_negation",
    ) == "SELECT 'WHERE b > 1' AS v FROM t WHERE NOT (NOT (b > 1))"

    # The OR is outside the NOT, and a mixed chain is not one binary connective.
    partial = "SELECT a FROM t WHERE NOT (b > 1) AND a < 3"
    mixed = "SELECT a FROM t WHERE NOT (b > 1 AND a < 3 OR a = 1)"
    assert apply_rule(partial, "demorgan") is None
    assert apply_rule(mixed, "demorgan") is None
    wrong_split = "SELECT a FROM t WHERE (NOT (b > 1)) OR (NOT (a < 3))"
    assert _bag(_rows_of(_SETUP, mixed)) != _bag(_rows_of(_SETUP, wrong_split))
    # The NOT inside the subquery is not the top-level predicate.
    nested = "SELECT a FROM (SELECT a, b FROM t WHERE NOT (b > 1 AND a < 3)) s"
    assert apply_rule(nested, "demorgan") is None
    assert apply_rule("UPDATE t SET a = a WHERE b > 1", "double_negation") is None
    assert apply_rule(
        "WITH x AS (UPDATE t SET a = 1 RETURNING a) SELECT a FROM x WHERE a > 0",
        "double_negation",
    ) is None
    assert apply_rule(
        "SELECT a FROM t WHERE b > 1 UNION ALL SELECT a FROM t WHERE a < 3",
        "double_negation",
    ) is None


def test_same_parenthesized_case_expression_and_outer_not_still_rewrite() -> None:
    assert apply_rule(
        "SELECT CASE WHEN (b) IS NOT NULL THEN (b) ELSE 0 END AS v FROM t",
        "case_to_coalesce",
    ) == "SELECT COALESCE((b), 0) AS v FROM t"
    assert apply_rule(
        "SELECT CASE WHEN B IS NOT NULL THEN b ELSE 0 END AS v FROM t",
        "case_to_coalesce",
    ) == "SELECT COALESCE(B, 0) AS v FROM t"
    assert apply_rule(
        'SELECT CASE WHEN "b" IS NOT NULL THEN b ELSE 0 END AS v FROM t',
        "case_to_coalesce",
    ) is None
    wrapped = apply_rule("SELECT a FROM t WHERE (NOT (b > 1 AND a < 3))", "demorgan")
    assert wrapped == "SELECT a FROM t WHERE (NOT (b > 1)) OR (NOT (a < 3))"
    assert apply_rule("SELECT a FROM t WHERE NOT ((b > 1 AND a < 3))", "demorgan") == wrapped
    both = apply_rule(
        "SELECT CASE WHEN b IS NOT NULL THEN b ELSE 0 END, "
        "CASE WHEN a IS NOT NULL THEN a ELSE 1 END FROM t",
        "case_to_coalesce",
    )
    assert both == "SELECT COALESCE(b, 0), COALESCE(a, 1) FROM t"


def test_between_and_case_and_are_not_demorgan_connectives() -> None:
    # Syntax-internal AND is not p AND q. The original statements succeed and
    # return [[4]]; the split a naive scanner used to emit is a syntax error.
    review_setup = (
        "CREATE TABLE t(a INT, b INT)",
        "INSERT INTO t VALUES (1,1),(2,NULL),(3,3),(4,6)",
    )
    between = "SELECT a FROM t WHERE NOT (b BETWEEN 1 AND 3)"
    case_and = (
        "SELECT a FROM t WHERE NOT (CASE WHEN a > 0 THEN b > 0 AND b < 5 ELSE FALSE END)"
    )
    naive = {
        between: "SELECT a FROM t WHERE (NOT (b BETWEEN 1)) OR (NOT (3))",
        case_and: (
            "SELECT a FROM t WHERE (NOT (CASE WHEN a > 0 THEN b > 0)) "
            "OR (NOT (b < 5 ELSE FALSE END))"
        ),
    }
    for query, broken in naive.items():
        assert apply_rule(query, "demorgan") is None
        for engine_name, factory in (("duckdb", DuckDBRunner), ("datafusion", DataFusionRunner)):
            runner = factory()
            try:
                assert all(error is None for _statement, error in runner.setup(review_setup))
                original = runner.run(query)
                assert original.ok, original.error
                assert _bag(original.rows) == _bag([[4]])
                assert runner.run(broken).ok is False
            finally:
                runner.close()
            opened: list[_Scripted] = []
            label = judge(
                _case(query, review_setup, engine=engine_name),
                "equivalent_query",
                rewrite_rule="demorgan",
                runner_factory=_scripted(opened, lambda _sql: QueryResult(rows=[]),
                                         lambda _sql, _n: QueryResult(rows=[[4]])),
            )
            _assert_ternary(label, "invalid", "not_applicable")
            assert label.detail["rule"] == "demorgan"
            assert label.detail["applicability"] == "rule_form"
            assert all(runner.runs == [] for runner in opened)
            real = judge(
                _case(query, _SETUP, engine=engine_name),
                "equivalent_query", rewrite_rule="demorgan",
            )
            _assert_ternary(real, "invalid", "not_applicable")

    # A real connective still splits when BETWEEN or CASE is only an operand.
    operand = "SELECT a FROM t WHERE NOT (b > 1 AND a BETWEEN 1 AND 3)"
    operand_rw = "SELECT a FROM t WHERE (NOT (b > 1)) OR (NOT (a BETWEEN 1 AND 3))"
    assert apply_rule(operand, "demorgan") == operand_rw
    assert _bag(_rows_of(_SETUP, operand)) == _bag(_rows_of(_SETUP, operand_rw))
    assert _bag(_rows_of(_SETUP, operand)) == _bag([[1]])
    either = "SELECT a FROM t WHERE NOT (a = 1 OR b BETWEEN 4 AND 9)"
    either_rw = "SELECT a FROM t WHERE (NOT (a = 1)) AND (NOT (b BETWEEN 4 AND 9))"
    assert apply_rule(either, "demorgan") == either_rw
    assert _bag(_rows_of(_SETUP, either)) == _bag([[3]])
    assert _bag(_rows_of(_SETUP, either_rw)) == _bag([[3]])
    nested_case = (
        "SELECT a FROM t WHERE NOT (a = 1 OR "
        "CASE WHEN a > 0 THEN b > 0 AND b < 5 ELSE FALSE END)"
    )
    nested_rw = (
        "SELECT a FROM t WHERE (NOT (a = 1)) AND (NOT (CASE WHEN a > 0 "
        "THEN b > 0 AND b < 5 ELSE FALSE END))"
    )
    assert apply_rule(nested_case, "demorgan") == nested_rw
    assert _bag(_rows_of(review_setup, nested_case)) == _bag([[4]])
    assert _bag(_rows_of(review_setup, nested_rw)) == _bag([[4]])

    # Brackets, an unclosed form, and a lambda are not another connective.
    braced = "SELECT a FROM t WHERE NOT (b > 1 AND a < {1 AND 2})"
    assert apply_rule(braced, "demorgan") == (
        "SELECT a FROM t WHERE (NOT (b > 1)) OR (NOT (a < {1 AND 2}))"
    )
    assert apply_rule("SELECT a FROM t WHERE NOT (a[1 AND 2] > 0)", "demorgan") is None
    assert apply_rule("SELECT a FROM t WHERE NOT (a < {1 AND 2)", "demorgan") is None
    assert apply_rule("SELECT a FROM t WHERE NOT (b BETWEEN 1)", "demorgan") is None
    assert apply_rule(
        "SELECT a FROM t WHERE NOT (CASE WHEN a > 0 THEN b > 0 AND b < 5)",
        "demorgan",
    ) is None
    assert apply_rule(
        "SELECT a FROM t WHERE NOT (a > 0 AND x -> x > 1)", "demorgan",
    ) is None
    # Words inside a string or a comment are not the connective.
    hidden = "SELECT a FROM t WHERE NOT (b > 1 AND c <> 'BETWEEN 1 AND 3')"
    assert apply_rule(hidden, "demorgan") == (
        "SELECT a FROM t WHERE (NOT (b > 1)) OR (NOT (c <> 'BETWEEN 1 AND 3'))"
    )
    commented = "SELECT a FROM t WHERE NOT (b > 1 /* BETWEEN */ AND a < 3 /* CASE */)"
    assert apply_rule(commented, "demorgan") == (
        "SELECT a FROM t WHERE (NOT (b > 1)) OR (NOT (a < 3))"
    )


# ---- equivalent query -------------------------------------------------------


def test_certified_rules_pass_and_preserve_the_duplicate_null_bag() -> None:
    queries = {
        "double_negation": "SELECT a FROM t WHERE b > 1",
        "demorgan": "SELECT a FROM t WHERE NOT (b > 1 AND a < 3)",
        "case_to_coalesce": "SELECT CASE WHEN b IS NOT NULL THEN b ELSE 0 END AS v FROM t",
    }
    expected = {
        "double_negation": [[3], [3]],
        "demorgan": [[1], [1], [3], [3]],
        "case_to_coalesce": [[1], [1], [0], [0], [3], [3]],
    }
    for rule_id, query in queries.items():
        opened: list[_Trace] = []
        label = judge(_case(query, _DUP_SETUP), "equivalent_query",
                      rewrite_rule=rule_id, runner_factory=_traced(opened))
        _assert_ternary(label, "pass")
        assert label.detail["rule"] == rule_id
        assert label.detail["rewritten"] == apply_rule(query, rule_id)
        handler = next(runner for runner in opened if runner.runs)
        assert handler.setups == 1
        assert handler.runs == [query, label.detail["rewritten"]]
        assert handler.closed == 2  # setup reconnects once; the handler closes again
        assert _bag(_rows_of(_DUP_SETUP, query)) == _bag(expected[rule_id])
        assert all(runner.closed >= 1 for runner in opened)
        again = judge(_case(query, _DUP_SETUP), "equivalent_query", rewrite_rule=rule_id)
        assert label.to_dict() == again.to_dict()


def test_default_rule_is_double_negation_and_unsupported_form_is_not_applicable() -> None:
    opened: list[_Trace] = []
    label = judge(
        _case("SELECT a FROM t WHERE b > 1"), "equivalent_query", runner_factory=_traced(opened),
    )
    _assert_ternary(label, "pass")
    assert label.detail["rule"] == "double_negation"
    assert label.detail["rewritten"] == "SELECT a FROM t WHERE NOT (NOT (b > 1))"

    plain = judge(_case("SELECT a, b FROM t"), "equivalent_query")
    _assert_ternary(plain, "invalid", "not_applicable")
    assert plain.detail["rule"] == "double_negation"
    declined = judge(_case("SELECT 1"), "equivalent_query", rewrite_rule="demorgan")
    _assert_ternary(declined, "invalid", "not_applicable")


def test_untrusted_pairs_are_not_executed() -> None:
    query = "SELECT a FROM t WHERE b > 1"
    opened: list[_Scripted] = []

    def factory():
        runner = _Scripted(lambda _sql: QueryResult(rows=[]), lambda _sql, _n: QueryResult(rows=[[9]]))
        opened.append(runner)
        return runner

    unknown = judge(_case(query), "equivalent_query", rewrite_rule="invented_rule", runner_factory=factory)
    mismatched = judge(
        _case(query), "equivalent_query", rewrite_rule="double_negation",
        paired_query="SELECT a FROM t", runner_factory=factory,
    )
    external = judge(
        _case(query), "equivalent_query", paired_query="SELECT a FROM t", runner_factory=factory,
    )
    for label in (unknown, mismatched, external):
        _assert_ternary(label, "invalid", "untrusted_rewrite")
    assert all(runner.runs == [] for runner in opened)
    # Keyword case and whitespace outside tokens may differ. The handler runs
    # the mechanical statement, not the paired text.
    opened.clear()
    trusted = judge(
        _case(query), "equivalent_query", rewrite_rule="double_negation",
        paired_query="select  a  from t where not (not (b > 1))",
        runner_factory=_traced(opened),
    )
    _assert_ternary(trusted, "pass")
    handler = next(runner for runner in opened if runner.runs)
    assert handler.runs[1] == apply_rule(query, "double_negation")
    assert "select  a  from t where not (not (b > 1))" not in handler.runs


def test_paired_literals_quotes_and_comments_are_not_rewritten_text() -> None:
    literal = "SELECT CASE WHEN s IS NOT NULL THEN s ELSE 'ABC' END FROM t"
    setup = ("CREATE TABLE t(s VARCHAR)", "INSERT INTO t VALUES (NULL), ('ZZ')")
    certified = apply_rule(literal, "case_to_coalesce")
    assert certified == "SELECT COALESCE(s, 'ABC') FROM t"
    quoted = 'SELECT CASE WHEN "S" IS NOT NULL THEN "S" ELSE 0 END FROM t'
    quoted_sql = apply_rule(quoted, "case_to_coalesce")
    assert quoted_sql == 'SELECT COALESCE("S", 0) FROM t'
    dollar = "SELECT CASE WHEN s IS NOT NULL THEN s ELSE $tag$ABC$tag$ END FROM t"
    dollar_sql = apply_rule(dollar, "case_to_coalesce")
    assert dollar_sql == "SELECT COALESCE(s, $tag$ABC$tag$) FROM t"
    spaced = "SELECT CASE WHEN s IS NOT NULL THEN s ELSE 'A B' END FROM t"
    spaced_sql = apply_rule(spaced, "case_to_coalesce")
    assert spaced_sql == "SELECT COALESCE(s, 'A B') FROM t"

    opened: list[_Scripted] = []

    def factory():
        runner = _Scripted(lambda _sql: QueryResult(rows=[]), lambda _sql, _n: QueryResult(rows=[[9]]))
        opened.append(runner)
        return runner

    # A comment is not external whitespace, and an identifier is not a keyword.
    rejected = (
        (literal, "case_to_coalesce", certified.replace("'ABC'", "'abc'")),
        (quoted, "case_to_coalesce", quoted_sql.replace('"S"', '"s"')),
        (dollar, "case_to_coalesce", dollar_sql.replace("$tag$ABC$tag$", "$tag$abc$tag$")),
        (spaced, "case_to_coalesce", spaced_sql.replace("'A B'", "'A  B'")),
        ("SELECT a FROM t WHERE b > 1", "double_negation",
         "SELECT A FROM t WHERE NOT (NOT (b > 1))"),
        (literal, "case_to_coalesce", certified + " /* note */"),
    )
    for query, rule_id, paired in rejected:
        opened.clear()
        label = judge(
            _case(query, setup), "equivalent_query", rewrite_rule=rule_id,
            paired_query=paired, runner_factory=factory,
        )
        _assert_ternary(label, "invalid", "untrusted_rewrite")
        assert all(runner.runs == [] for runner in opened)
    real_untrusted = judge(
        _case(literal, setup), "equivalent_query", rewrite_rule="case_to_coalesce",
        paired_query=certified.replace("'ABC'", "'abc'"),
    )
    _assert_ternary(real_untrusted, "invalid", "untrusted_rewrite")

    # The same literal matches once keyword case, external space, and one
    # trailing semicolon are the only differences. The run is the mechanical text.
    opened_real: list[_Trace] = []
    trusted = judge(
        _case(literal, setup), "equivalent_query", rewrite_rule="case_to_coalesce",
        paired_query="select  COALESCE(s, 'ABC')  from t ;",
        runner_factory=_traced(opened_real),
    )
    _assert_ternary(trusted, "pass")
    handler = next(runner for runner in opened_real if runner.runs)
    assert handler.runs[1] == certified
    assert "select  COALESCE(s, 'ABC')  from t ;" not in handler.runs


def test_equivalence_none_is_split_from_the_real_execution() -> None:
    query = "SELECT a FROM t WHERE b > 1"
    opened: list[_Scripted] = []

    def both_error(_sql, _n):
        return QueryResult(error="BinderException: missing")

    label = judge(_case(query), "equivalent_query", rewrite_rule="double_negation",
                  runner_factory=_scripted(opened, lambda _sql: QueryResult(rows=[]), both_error))
    _assert_ternary(label, "invalid", "query_error")
    assert "BinderException" in label.detail["error"]
    handler = next(runner for runner in opened if runner.runs)
    assert len(handler.runs) == 2

    def value_dependent(_sql, n):
        if n == 1:
            return QueryResult(rows=[[3]])
        return QueryResult(error="ConversionException: division by zero")

    split = judge(_case(query), "equivalent_query", rewrite_rule="double_negation",
                  runner_factory=_scripted([], lambda _sql: QueryResult(rows=[]), value_dependent))
    _assert_ternary(split, "invalid", "value_dependent_error")

    def timeout(_sql, n):
        if n == 1:
            return QueryResult(rows=[[3]])
        return QueryResult(error="TimeoutError: injected", timed_out=True)

    timed = judge(_case(query), "equivalent_query", rewrite_rule="double_negation",
                  runner_factory=_scripted([], lambda _sql: QueryResult(rows=[]), timeout))
    _assert_ternary(timed, "invalid", "timeout")

    def crash(_sql, _n):
        return QueryResult(error="InternalException: INTERNAL Error: boom", is_internal_error=True)

    crashed = judge(_case(query), "equivalent_query", rewrite_rule="double_negation",
                    runner_factory=_scripted([], lambda _sql: QueryResult(rows=[]), crash))
    _assert_ternary(crashed, "fail", kind="crash")
    assert crashed.identity.error_class == "InternalException"
    assert crashed.identity.switches == ("double_negation",)


def test_certified_mismatch_is_wrong_result_with_behavior() -> None:
    query = "SELECT a FROM t WHERE b > 1"

    def on_query(sql, _n):
        if "NOT (NOT" in sql:
            return QueryResult(rows=[[3]])
        return QueryResult(rows=[[3], [3]])

    label = judge(_case(query), "equivalent_query", rewrite_rule="double_negation",
                  runner_factory=_scripted([], lambda _sql: QueryResult(rows=[]), on_query))
    _assert_ternary(label, "fail", kind="wrong_result")
    assert label.identity.switches == ("double_negation",)
    assert label.identity.behavior["missing"] == 1
    assert label.identity.behavior["extra"] == 0
    assert label.detail["rewritten"] == apply_rule(query, "double_negation")
    assert label.to_dict() == judge(
        _case(query), "equivalent_query", rewrite_rule="double_negation",
        runner_factory=_scripted([], lambda _sql: QueryResult(rows=[]), on_query),
    ).to_dict()


def test_equivalent_handler_checks_setup_and_closes() -> None:
    class _Bad:
        def __init__(self) -> None:
            self.closed = 0
            self.runs: list[str] = []

        def setup(self, schema_sqls):
            return [(schema_sqls[0], "CatalogException: missing")]

        def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
            self.runs.append(sql)
            return QueryResult(rows=[])

        def close(self) -> None:
            self.closed += 1

    runner = _Bad()
    label = judge_equivalent(
        _case("SELECT a FROM t WHERE b > 1"),
        factory=lambda: runner, timeout_s=10.0, options=_OPTIONS,
    )
    _assert_ternary(label, "invalid", "setup_error")
    assert runner.closed == 1
    assert runner.runs == []


# ---- index presence ---------------------------------------------------------


def test_art_indexes_are_created_without_session_settings_and_keep_duplicates() -> None:
    query = "SELECT a, b FROM t WHERE a = 1"
    opened: list[_Trace] = []
    label = judge(_case(query, _DUP_SETUP), "index_presence", runner_factory=_traced(opened))
    _assert_ternary(label, "pass")
    created = label.detail["indexes_created"]
    assert [item["name"] for item in created] == ["art0_t_a", "art1_t_b"]
    assert created[0]["statement"] == 'CREATE INDEX "art0_t_a" ON "t"("a")'
    assert created[1]["statement"] == 'CREATE INDEX "art1_t_b" ON "t"("b")'
    handler = next(runner for runner in opened if runner.runs)
    assert handler.setups == 1
    assert handler.closed == 2  # setup reconnects once; the handler closes again
    assert handler.runs == [
        query,
        created[0]["statement"], query, 'DROP INDEX IF EXISTS "art0_t_a"',
        created[1]["statement"], query, 'DROP INDEX IF EXISTS "art1_t_b"',
    ]
    assert not any(
        "ENABLE_SEQSCAN" in sql.upper() or sql.upper().startswith("SET ") or "PRAGMA" in sql.upper()
        for sql in handler.runs
    )
    assert _bag(_rows_of(_DUP_SETUP, query)) == _bag([[1, 1], [1, 1]])
    assert all(runner.closed >= 1 for runner in opened)
    assert label.to_dict() == judge(_case(query, _DUP_SETUP), "index_presence").to_dict()


def test_index_presence_rejects_engines_shapes_and_unindexable_tables() -> None:
    datafusion = judge(_case("SELECT a, b FROM t", engine="datafusion"), "index_presence")
    _assert_ternary(datafusion, "invalid", "not_applicable")
    assert datafusion.detail["applicability"] == "no_secondary_index"

    opened: list[_Trace] = []
    update = judge(
        _case("UPDATE t SET a = a"), "index_presence", runner_factory=_traced(opened),
    )
    _assert_ternary(update, "invalid", "not_applicable")
    assert update.detail["applicability"] == "not_select"
    assert all(runner.runs == [] for runner in opened)

    bare = judge(_case("SELECT 1", setup=()), "index_presence")
    _assert_ternary(bare, "invalid", "not_applicable")
    assert bare.detail["applicability"] == "no_base_table"

    arrays = judge(
        _case("SELECT w FROM arr", setup=("CREATE TABLE arr(w INT[])", "INSERT INTO arr VALUES (NULL)")),
        "index_presence",
    )
    _assert_ternary(arrays, "invalid", "not_applicable")
    assert arrays.detail["applicability"] == "no_art_index"
    assert "indexes_created" not in arrays.detail


def test_failed_index_setup_is_not_a_comparison() -> None:
    query = "SELECT a FROM t WHERE a = 1"
    opened: list[_Scripted] = []

    def on_create(_sql):
        return QueryResult(error="InvalidTypeException: Invalid type for index key")

    def on_query(_sql, n):
        if n == 1:
            return QueryResult(rows=[[1], [1]])
        return QueryResult(rows=[])

    label = judge(_case(query), "index_presence",
                  runner_factory=_scripted(opened, on_create, on_query))
    _assert_ternary(label, "invalid", "not_applicable")
    handler = next(runner for runner in opened if runner.runs)
    assert handler.queries == 1
    assert any("CREATE INDEX" in sql.upper() for sql in handler.runs)


def test_injected_index_mismatch_is_wrong_result() -> None:
    query = "SELECT a, b FROM t WHERE a = 3"

    class IndexMismatch(DuckDBRunner):
        def __init__(self) -> None:
            super().__init__()
            self.indexed = False

        def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
            result = super().run(sql, timeout_s=timeout_s)
            if "CREATE" in sql.upper() and "INDEX" in sql.upper() and result.ok:
                self.indexed = True
            if self.indexed and sql.strip().rstrip(";") == query:
                return QueryResult(rows=[])
            return result

    label = judge(_case(query), "index_presence", runner_factory=IndexMismatch)
    _assert_ternary(label, "fail", kind="wrong_result")
    assert label.identity.switches == ("art0_t_a",)
    assert label.identity.behavior["index"] == "art0_t_a"
    assert label.identity.behavior["statement"] == 'CREATE INDEX "art0_t_a" ON "t"("a")'
    assert label.identity.behavior["missing"] == 1
    assert label.identity.behavior["extra"] == 0
    assert label.identity.error_class is None


def test_index_errors_map_to_crash_or_invalid_and_do_not_compare() -> None:
    query = "SELECT a FROM t"

    def create_ok(_sql):
        return QueryResult(rows=[])

    def baseline(kind: str):
        def on_query(_sql, n):
            if n > 1:
                return QueryResult(rows=[[9]])
            if kind == "binder":
                return QueryResult(error="BinderException: missing")
            if kind == "value":
                return QueryResult(error="ConversionException: division by zero")
            if kind == "timeout":
                return QueryResult(error="TimeoutError: injected", timed_out=True)
            return QueryResult(error="InternalException: INTERNAL Error: boom", is_internal_error=True)

        return on_query

    binder = judge(_case(query), "index_presence",
                   runner_factory=_scripted([], create_ok, baseline("binder")))
    _assert_ternary(binder, "invalid", "query_error")
    value = judge(_case(query), "index_presence",
                  runner_factory=_scripted([], create_ok, baseline("value")))
    _assert_ternary(value, "invalid", "value_dependent_error")
    timed = judge(_case(query), "index_presence",
                  runner_factory=_scripted([], create_ok, baseline("timeout")))
    _assert_ternary(timed, "invalid", "timeout")
    crashed = judge(_case(query), "index_presence",
                    runner_factory=_scripted([], create_ok, baseline("crash")))
    _assert_ternary(crashed, "fail", kind="crash")

    opened: list[_Scripted] = []
    judge(_case(query), "index_presence", runner_factory=_scripted(opened, create_ok, baseline("binder")))
    handler = next(runner for runner in opened if runner.runs)
    assert not any("CREATE INDEX" in sql.upper() for sql in handler.runs)

    def indexed_crash(_sql, n):
        if n == 1:
            return QueryResult(rows=[[1]])
        return QueryResult(error="InternalException: INTERNAL Error: boom", is_internal_error=True)

    under = judge(_case(query), "index_presence",
                  runner_factory=_scripted([], create_ok, indexed_crash))
    _assert_ternary(under, "fail", kind="crash")
    assert under.identity.switches == ("art0_t_a",)

    def create_crash(_sql):
        return QueryResult(error="InternalException: INTERNAL Error: art", is_internal_error=True)

    while_creating = judge(_case(query), "index_presence",
                           runner_factory=_scripted([], create_crash, lambda _sql, n: QueryResult(rows=[[1]])))
    _assert_ternary(while_creating, "fail", kind="crash")


def test_index_handler_checks_setup_and_closes() -> None:
    class _Bad:
        def __init__(self) -> None:
            self.closed = 0

        def setup(self, schema_sqls):
            return [(schema_sqls[0], "CatalogException: missing")]

        def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
            raise AssertionError(sql)

        def close(self) -> None:
            self.closed += 1

    runner = _Bad()
    label = judge_index(_case("SELECT a FROM t"), factory=lambda: runner, timeout_s=10.0, options=_OPTIONS)
    _assert_ternary(label, "invalid", "setup_error")
    assert runner.closed == 1


def test_real_value_dependent_baseline_does_not_build_an_index() -> None:
    opened: list[_Trace] = []
    query = "SELECT CAST('x' AS INT) FROM t"
    label = judge(_case(query), "index_presence", runner_factory=_traced(opened))
    _assert_ternary(label, "invalid", "value_dependent_error")
    handler = next(runner for runner in opened if runner.runs)
    assert handler.runs == [query]
