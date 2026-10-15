"""Second rewrite layer: accepted LLM templates and the reference premise."""

from __future__ import annotations

import json

from oracles.db_runner import QueryResult
from surprise.harness.contracts import SqlCase
from surprise.harness.cve.certify import certify
from surprise.harness.oracles import judge
from surprise.harness.oracles.rewrites import (
    LIBRARY_ENV,
    LIBRARY_KINDS,
    LIBRARY_MIN_REFERENCES,
    LIBRARY_RULE_PREFIX,
    LIBRARY_SCHEMA,
    RULES,
    apply_rule,
    apply_template,
    is_library_rule,
    load_library,
    same_statement,
    template_problem,
)

_FROZEN_OUTPUTS = {
    ("SELECT a FROM t WHERE a > 1 ORDER BY a", "double_negation"):
        "SELECT a FROM t WHERE NOT (NOT (a > 1)) ORDER BY a",
    ("SELECT a FROM t WHERE a > 1 ORDER BY a", "demorgan"): None,
    ("SELECT a FROM t WHERE a > 1 ORDER BY a", "case_to_coalesce"): None,
    ("SELECT * FROM t WHERE NOT (a = 1 AND b IS NULL)", "double_negation"):
        "SELECT * FROM t WHERE NOT (NOT (NOT (a = 1 AND b IS NULL)))",
    ("SELECT * FROM t WHERE NOT (a = 1 AND b IS NULL)", "demorgan"):
        "SELECT * FROM t WHERE (NOT (a = 1)) OR (NOT (b IS NULL))",
    ("SELECT * FROM t WHERE NOT (a = 1 AND b IS NULL)", "case_to_coalesce"): None,
    ("SELECT CASE WHEN x IS NOT NULL THEN x ELSE y END FROM t", "double_negation"): None,
    ("SELECT CASE WHEN x IS NOT NULL THEN x ELSE y END FROM t", "case_to_coalesce"):
        "SELECT COALESCE(x, y) FROM t",
    ("SELECT v FROM t EXCEPT ALL SELECT v FROM u", "double_negation"): None,
    ("SELECT a FROM t WHERE a BETWEEN 1 AND 3", "double_negation"):
        "SELECT a FROM t WHERE NOT (NOT (a BETWEEN 1 AND 3))",
    ("SELECT a FROM t WHERE a BETWEEN 1 AND 3", "demorgan"): None,
    ("SELECT a FROM t WHERE NOT (a = 1 OR b = 2) GROUP BY a", "demorgan"):
        "SELECT a FROM t WHERE (NOT (a = 1)) AND (NOT (b = 2)) GROUP BY a",
}

_TEMPLATES_OK = (
    ("query_wrap", "SELECT * FROM ({q}) AS llm_sub"),
    ("query_wrap", "WITH llm_cte AS ({q}) SELECT * FROM llm_cte"),
    ("predicate_wrap", "({p}) IS TRUE"),
    ("predicate_wrap", "CASE WHEN {p} THEN TRUE ELSE FALSE END"),
    ("predicate_wrap", "({p}) AND ({p})"),
    ("predicate_wrap", "({p}) OR ({p}) OR ({p})"),
)

_TEMPLATES_BAD = (
    ("query_wrap", ""),
    ("query_wrap", "SELECT * FROM t"),
    ("query_wrap", "SELECT * FROM ({q}) AS a UNION ALL {q}"),
    ("query_wrap", "SELECT * FROM ({q}) AS a; SELECT 1"),
    ("query_wrap", "SELECT * FROM ({q}) AS a -- note"),
    ("query_wrap", "SELECT * FROM ({q}) AS a /* note */"),
    ("query_wrap", "DELETE FROM t WHERE EXISTS ({q})"),
    ("query_wrap", "INSERT INTO t SELECT * FROM ({q}) AS a"),
    ("query_wrap", "CREATE TABLE t AS SELECT * FROM ({q}) AS a"),
    ("query_wrap", "SELECT * FROM ({q}) AS a WHERE {p}"),
    ("predicate_wrap", "{q} IS TRUE"),
    ("predicate_wrap", "({p}) IS TRUE}"),
    ("predicate_wrap", "({p}) AND ({p}) AND ({p}) AND ({p})"),
    ("sql_rewrite", "SELECT * FROM ({q}) AS a"),
    ("query_wrap", None),
    ("query_wrap", 12),
    ("query_wrap", "SELECT '{q}"),
    ("query_wrap", "SELECT '{q}' AS hidden"),
    ("query_wrap", "SELECT ';' FROM ({q}) AS a"),
    ("query_wrap", "x" * 2001),
)

_APPLY_CASES = (
    ("SELECT a FROM t WHERE a > 1", "query_wrap", "SELECT * FROM ({q}) AS llm_sub",
     "SELECT * FROM (SELECT a FROM t WHERE a > 1) AS llm_sub"),
    ("SELECT a FROM t WHERE a > 1 ORDER BY a", "predicate_wrap", "({p}) IS TRUE",
     "SELECT a FROM t WHERE (((a > 1)) IS TRUE) ORDER BY a"),
    ("SELECT a FROM t", "predicate_wrap", "({p}) IS TRUE", None),
    ("DELETE FROM t WHERE a > 1", "query_wrap", "SELECT * FROM ({q}) AS llm_sub", None),
    ("SELECT a FROM t WHERE a > 1; SELECT 2", "query_wrap", "SELECT * FROM ({q}) AS llm_sub", None),
    ("  SELECT a FROM t WHERE a > 1 ;", "query_wrap", "SELECT * FROM ({q}) AS llm_sub",
     "SELECT * FROM (SELECT a FROM t WHERE a > 1) AS llm_sub"),
    ("SELECT a FROM t WHERE a > 1 ORDER BY a;", "predicate_wrap", "({p}) IS TRUE",
     "SELECT a FROM t WHERE (((a > 1)) IS TRUE) ORDER BY a"),
    ("SELECT a FROM t WHERE a > 1 UNION ALL SELECT a FROM u WHERE a < 0",
     "predicate_wrap", "({p}) IS TRUE", None),
    ("UPDATE t SET a = 1 WHERE a > 1", "predicate_wrap", "({p}) IS TRUE", None),
    ("SELECT a FROM t WHERE a > 1", "predicate_wrap", "({p}) AND ({p})",
     "SELECT a FROM t WHERE (((a > 1)) AND ((a > 1)))"),
)

_SETUP = (
    "CREATE TABLE lib_t(a INTEGER, b INTEGER)",
    "INSERT INTO lib_t VALUES (1, 10), (2, 20), (3, 30), (NULL, 40)",
)
_QUERY = "SELECT a, b FROM lib_t WHERE a > 1"
_FROZEN_DETAIL = {
    "full_query": _QUERY,
    "rule": "double_negation",
    "rewritten": "SELECT a, b FROM lib_t WHERE NOT (NOT (a > 1))",
}
_LIBRARY_RULES = {
    "llm:wrap_sub": ("query_wrap", "SELECT * FROM ({q}) AS llm_sub"),
    "llm:is_true": ("predicate_wrap", "({p}) IS TRUE"),
    "llm:first_row": ("query_wrap", "SELECT * FROM ({q}) AS llm_sub LIMIT 1"),
    "llm:octet": ("query_wrap", "SELECT * FROM ({q}) AS llm_sub WHERE octet_length('ab') = 2"),
}
_PREMISES = ("reference_disagrees", "too_few_references", "rewrite_error")


def _rule(rule_id, kind, template, **extra):
    item = {
        "rule_id": rule_id,
        "kind": kind,
        "template": template,
        "argument": "preserves the result bag",
        "acceptance": {"engines": ["gate"], "instances": 1},
    }
    item.update(extra)
    return item


def _write(path, rules, schema=LIBRARY_SCHEMA) -> None:
    payload = {"schema": schema, "rules": list(rules)}
    path.write_text(json.dumps(payload), encoding="utf-8")


def _case() -> SqlCase:
    return SqlCase(engine="duckdb", setup=_SETUP, query=_QUERY, predicate=None)


def _point(monkeypatch, path) -> None:
    monkeypatch.setenv(LIBRARY_ENV, str(path))


class _Rows:
    """Reference or target whose result depends only on the SQL text."""

    def __init__(self, rows=None, rewrite_rows=None, error=None, setup_error=None) -> None:
        self._rows = [[1], [2]] if rows is None else rows
        self._rewrite_rows = rewrite_rows
        self._error = error
        self._setup_error = setup_error
        self.runs: list[str] = []
        self.closed = 0

    def setup(self, schema_sqls):
        if self._setup_error is not None:
            return [(schema_sqls[0], self._setup_error)] if schema_sqls else [("", self._setup_error)]
        return [(statement, None) for statement in schema_sqls]

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        self.runs.append(sql)
        if self._error is not None and "llm_sub" in sql:
            return QueryResult(error=self._error)
        chosen = self._rewrite_rows if self._rewrite_rows is not None and "llm_sub" in sql else self._rows
        return QueryResult(rows=[list(row) for row in chosen])

    def close(self) -> None:
        self.closed += 1


def _factory(rows=None, rewrite_rows=None, error=None, setup_error=None, opened=None):
    def factory():
        runner = _Rows(
            rows=rows, rewrite_rows=rewrite_rows, error=error, setup_error=setup_error,
        )
        if opened is not None:
            opened.append(runner)
        return runner

    return factory


def _library_keys(detail: dict, rule_id: str, *, premise=None) -> None:
    assert detail["rule"] == rule_id
    assert detail["layer"] == "library"
    assert detail["kind"] in LIBRARY_KINDS
    assert isinstance(detail["template"], str) and detail["template"]
    assert detail["full_query"] == _QUERY
    assert isinstance(detail.get("rewritten"), str)
    refs = detail["references"]
    assert isinstance(refs, dict)
    assert set(refs.values()) <= {"agree", "disagree", "skipped"}
    if premise is None:
        assert "premise" not in detail
        assert sum(status == "agree" for status in refs.values()) >= LIBRARY_MIN_REFERENCES
        assert "disagree" not in refs.values()
    else:
        assert detail["premise"] == premise
        assert premise in _PREMISES


def test_constants_match_the_gate() -> None:
    assert LIBRARY_ENV == "SURPRISE_REWRITE_LIBRARY"
    assert LIBRARY_RULE_PREFIX == "llm:"
    assert LIBRARY_KINDS == ("query_wrap", "predicate_wrap")
    assert type(LIBRARY_KINDS) is tuple
    assert LIBRARY_MIN_REFERENCES == 2 and type(LIBRARY_MIN_REFERENCES) is int
    assert LIBRARY_SCHEMA == 1 and type(LIBRARY_SCHEMA) is int
    assert tuple(RULES) == ("double_negation", "demorgan", "case_to_coalesce")


def test_template_problem_accepts_usable_shapes() -> None:
    for kind, template in _TEMPLATES_OK:
        assert template_problem(kind, template) is None, template
    body = "SELECT * FROM ({q}) AS " + ("a" * (2000 - len("SELECT * FROM ({q}) AS ")))
    assert len(body) == 2000
    assert template_problem("query_wrap", body) is None
    assert template_problem("query_wrap", "SELECT 'DELETE' FROM ({q}) AS llm_sub") is None


def test_template_problem_rejects_each_unusable_shape() -> None:
    for kind, template in _TEMPLATES_BAD:
        reason = template_problem(kind, template)
        assert isinstance(reason, str) and reason, (kind, template)
    assert template_problem("query_wrap", "SELECT * FROM ({q}) AS " + "b" * 1981) is not None


def test_apply_template_shapes_semicolon_and_where_premises() -> None:
    for query, kind, template, want in _APPLY_CASES:
        got = apply_template(query, kind, template)
        if want is None:
            assert got is None, (query, got)
        else:
            assert isinstance(got, str) and same_statement(got, want), got
    assert apply_template("SELECT 1", "query_wrap", "{q}") is None
    assert apply_template(
        "SELECT a FROM t WHERE a > 1 AND a IN (SELECT a FROM u WHERE a > 2)",
        "predicate_wrap", "({p}) IS TRUE",
    ) is not None
    kept = apply_template(
        "SELECT a FROM t WHERE a > 1 ORDER BY a",
        "predicate_wrap", "({p}) IS TRUE",
    )
    assert kept is not None and kept.endswith(" ORDER BY a")


def test_load_library_missing_and_well_formed(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv(LIBRARY_ENV, raising=False)
    assert load_library() == {}
    assert is_library_rule("llm:wrap_sub") is False
    missing = tmp_path / "missing.json"
    assert load_library(missing) == {}
    monkeypatch.setenv(LIBRARY_ENV, str(missing))
    assert load_library() == {}

    path = tmp_path / "rewrites.json"
    rule = _rule("llm:wrap_sub", "query_wrap", "SELECT * FROM ({q}) AS llm_sub", note="kept")
    _write(path, [rule])
    loaded = load_library(path)
    assert list(loaded) == ["llm:wrap_sub"]
    assert loaded["llm:wrap_sub"]["kind"] == "query_wrap"
    assert loaded["llm:wrap_sub"]["template"] == "SELECT * FROM ({q}) AS llm_sub"
    assert loaded["llm:wrap_sub"]["argument"] == "preserves the result bag"
    assert loaded["llm:wrap_sub"]["acceptance"]["engines"] == ["gate"]
    assert loaded["llm:wrap_sub"]["note"] == "kept"
    loaded["llm:wrap_sub"]["template"] = "changed"
    assert load_library(path)["llm:wrap_sub"]["template"].startswith("SELECT")

    omitted = _rule("llm:is_true", "predicate_wrap", "({p}) IS TRUE")
    _write(path, [omitted])
    assert "proposer" not in load_library(path)["llm:is_true"]
    _point(monkeypatch, path)
    assert is_library_rule("llm:is_true") is True
    assert is_library_rule("double_negation") is False
    assert is_library_rule("llm:missing") is False

    _write(path, [_rule("llm:wrap_sub", "query_wrap", "SELECT * FROM ({q}) AS llm_sub")])
    assert is_library_rule("llm:wrap_sub") is True
    assert is_library_rule("llm:is_true") is False


def test_load_library_rejects_each_malformed_file(tmp_path) -> None:
    path = tmp_path / "bad.json"
    good = _rule("llm:wrap_sub", "query_wrap", "SELECT * FROM ({q}) AS llm_sub")
    good_text = json.dumps({"schema": 1, "rules": [good]})
    assert json.loads(good_text)["schema"] == 1
    cases = {
        "not_json": "{",
        "array": json.dumps([good]),
        "string": json.dumps("library"),
        "null": "null",
        "schema_missing": json.dumps({"rules": [good]}),
        "schema_value": json.dumps({"schema": 2, "rules": [good]}),
        "schema_type": json.dumps({"schema": "1", "rules": [good]}),
        "schema_float": '{"schema": 1.0, "rules": ' + json.dumps([good]) + "}",
        "rules_missing": json.dumps({"schema": 1}),
        "rules_object": json.dumps({"schema": 1, "rules": {"rule_id": "llm:wrap_sub"}}),
        "rule_not_object": json.dumps({"schema": 1, "rules": ["llm:wrap_sub"]}),
        "missing_argument": json.dumps({"schema": 1, "rules": [
            {key: value for key, value in good.items() if key != "argument"}]}),
        "missing_acceptance": json.dumps({"schema": 1, "rules": [
            {key: value for key, value in good.items() if key != "acceptance"}]}),
        "rule_id_type": json.dumps({"schema": 1, "rules": [dict(good, rule_id=1)]}),
        "prefix": json.dumps({"schema": 1, "rules": [dict(good, rule_id="wrap_sub")]}),
        "uppercase": json.dumps({"schema": 1, "rules": [dict(good, rule_id="llm:Wrap")]}),
        "too_long": json.dumps({"schema": 1, "rules": [dict(good, rule_id="llm:" + "a" * 41)]}),
        "frozen_name": json.dumps({"schema": 1, "rules": [dict(good, rule_id="double_negation")]}),
        "frozen_suffix": json.dumps({"schema": 1, "rules": [dict(good, rule_id="llm:double_negation")]}),
        "frozen_demorgan": json.dumps({"schema": 1, "rules": [dict(good, rule_id="llm:demorgan")]}),
        "frozen_case": json.dumps({"schema": 1, "rules": [dict(good, rule_id="llm:case_to_coalesce")]}),
        "duplicate": json.dumps({"schema": 1, "rules": [good, good]}),
        "empty_argument": json.dumps({"schema": 1, "rules": [dict(good, argument="")]}),
        "argument_type": json.dumps({"schema": 1, "rules": [dict(good, argument=1)]}),
        "empty_acceptance": json.dumps({"schema": 1, "rules": [dict(good, acceptance={})]}),
        "acceptance_list": json.dumps({"schema": 1, "rules": [dict(good, acceptance=["gate"])]}),
        "bad_template": json.dumps({"schema": 1, "rules": [dict(good, template="DELETE FROM t")]}),
        "bad_kind": json.dumps({"schema": 1, "rules": [dict(good, kind="sql_rewrite")]}),
        "kind_type": json.dumps({"schema": 1, "rules": [dict(good, kind=1)]}),
        "template_type": json.dumps({"schema": 1, "rules": [dict(good, template=1)]}),
        "proposer_null": json.dumps({"schema": 1, "rules": [dict(good, proposer=None)]}),
        "second_bad": json.dumps({"schema": 1, "rules": [good, dict(good, rule_id="llm:other", template="")]}),
    }
    for tag, text in cases.items():
        path.write_text(text, encoding="utf-8")
        assert load_library(path) == {}, tag
    path.write_bytes(b"\xff\xfe")
    assert load_library(path) == {}


def test_apply_rule_frozen_output_is_independent_of_the_library(tmp_path, monkeypatch) -> None:
    path = tmp_path / "rewrites.json"
    _write(path, [
        _rule(rule_id, kind, template) for rule_id, (kind, template) in _LIBRARY_RULES.items()
    ])
    query = "SELECT a FROM t WHERE a > 1"
    monkeypatch.delenv(LIBRARY_ENV, raising=False)
    assert apply_rule(query, "llm:wrap_sub") is None
    _point(monkeypatch, path)
    assert apply_rule(query, "llm:wrap_sub") == (
        "SELECT * FROM (SELECT a FROM t WHERE a > 1) AS llm_sub"
    )
    assert apply_rule(query, "llm:not_there") is None
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    for (text, rule_id), want in _FROZEN_OUTPUTS.items():
        monkeypatch.delenv(LIBRARY_ENV, raising=False)
        unset = apply_rule(text, rule_id)
        _point(monkeypatch, path)
        present = apply_rule(text, rule_id)
        _point(monkeypatch, broken)
        corrupt = apply_rule(text, rule_id)
        assert unset == present == corrupt == want


def test_scripted_library_premises_and_detail_keys(tmp_path, monkeypatch) -> None:
    path = tmp_path / "rewrites.json"
    _write(path, [
        _rule("llm:wrap_sub", "query_wrap", "SELECT * FROM ({q}) AS llm_sub"),
        _rule("llm:plain", "predicate_wrap", "({p}) IS TRUE"),
    ])
    _point(monkeypatch, path)
    case = _case()

    passed = judge(
        case, "equivalent_query", rewrite_rule="llm:wrap_sub",
        runner_factory=_factory(),
        reference_factories={"sqlite": _factory(), "datafusion": _factory()},
    )
    assert passed.y == "pass" and passed.invalid_reason is None
    _library_keys(passed.detail, "llm:wrap_sub")
    assert passed.detail["references"] == {"datafusion": "agree", "sqlite": "agree"}

    disagree = judge(
        case, "equivalent_query", rewrite_rule="llm:wrap_sub",
        runner_factory=_factory(),
        reference_factories={
            "sqlite": _factory(),
            "datafusion": _factory(rewrite_rows=[[9]]),
        },
    )
    assert (disagree.y, disagree.invalid_reason) == ("invalid", "untrusted_rewrite")
    _library_keys(disagree.detail, "llm:wrap_sub", premise="reference_disagrees")
    assert disagree.detail["references"]["datafusion"] == "disagree"

    opened: list[_Rows] = []
    one = judge(
        case, "equivalent_query", rewrite_rule="llm:wrap_sub",
        runner_factory=_factory(opened=opened),
        reference_factories={"sqlite": _factory()},
    )
    assert (one.y, one.invalid_reason) == ("invalid", "untrusted_rewrite")
    _library_keys(one.detail, "llm:wrap_sub", premise="too_few_references")
    assert one.detail["references"] == {"sqlite": "agree"}
    assert all(runner.runs == [] for runner in opened)

    empty = judge(
        case, "equivalent_query", rewrite_rule="llm:wrap_sub",
        runner_factory=_factory(), reference_factories={},
    )
    assert empty.detail["premise"] == "too_few_references"
    assert empty.detail["references"] == {}

    skipped = judge(
        case, "equivalent_query", rewrite_rule="llm:wrap_sub",
        runner_factory=_factory(),
        reference_factories={
            "sqlite": _factory(),
            "datafusion": _factory(setup_error="CatalogException: missing"),
            "postgres": _factory(error="BinderException: boom"),
        },
    )
    assert skipped.detail["premise"] == "too_few_references"
    assert skipped.detail["references"]["sqlite"] == "agree"
    assert skipped.detail["references"]["datafusion"] == "skipped"
    assert skipped.detail["references"]["postgres"] == "skipped"

    errored = judge(
        case, "equivalent_query", rewrite_rule="llm:wrap_sub",
        runner_factory=_factory(error="BinderException: no function"),
        reference_factories={"sqlite": _factory(), "datafusion": _factory()},
    )
    assert (errored.y, errored.invalid_reason) == ("invalid", "untrusted_rewrite")
    _library_keys(errored.detail, "llm:wrap_sub", premise="rewrite_error")

    failed = judge(
        case, "equivalent_query", rewrite_rule="llm:wrap_sub",
        runner_factory=_factory(rewrite_rows=[[1]]),
        reference_factories={"sqlite": _factory(), "datafusion": _factory()},
    )
    assert failed.y == "fail" and failed.fail_kind == "wrong_result"
    _library_keys(failed.detail, "llm:wrap_sub")
    assert failed.identity.switches == ("llm:wrap_sub",)

    absent = judge(case, "equivalent_query", rewrite_rule="llm:not_in_library",
                   runner_factory=_factory())
    assert (absent.y, absent.invalid_reason) == ("invalid", "untrusted_rewrite")
    assert "layer" not in absent.detail

    paired = judge(
        case, "equivalent_query", rewrite_rule="llm:wrap_sub",
        paired_query="SELECT 1", runner_factory=_factory(),
        reference_factories={"sqlite": _factory(), "datafusion": _factory()},
    )
    assert (paired.y, paired.invalid_reason) == ("invalid", "untrusted_rewrite")
    assert paired.detail["layer"] == "library"
    assert "references" not in paired.detail
    assert "premise" not in paired.detail
    assert isinstance(paired.detail["rewritten"], str)

    plain = SqlCase(engine="duckdb", setup=_SETUP, query="SELECT a, b FROM lib_t", predicate=None)
    declined = judge(
        plain, "equivalent_query", rewrite_rule="llm:plain", runner_factory=_factory(),
    )
    assert (declined.y, declined.invalid_reason) == ("invalid", "not_applicable")
    assert declined.detail["layer"] == "library"
    assert declined.detail["applicability"] == "rule_form"
    assert "rewritten" not in declined.detail
    assert "references" not in declined.detail


def test_real_engines_and_frozen_detail(tmp_path, monkeypatch) -> None:
    path = tmp_path / "rewrites.json"
    _write(path, [
        _rule(rule_id, kind, template) for rule_id, (kind, template) in _LIBRARY_RULES.items()
    ])
    _point(monkeypatch, path)
    case = _case()
    expected = {
        "llm:wrap_sub": ("pass", None, None),
        "llm:is_true": ("pass", None, None),
        "llm:first_row": ("invalid", "untrusted_rewrite", "reference_disagrees"),
        "llm:octet": ("invalid", "untrusted_rewrite", "rewrite_error"),
    }
    for rule_id, (y, reason, premise) in expected.items():
        judged = judge(case, "equivalent_query", rewrite_rule=rule_id)
        assert (judged.y, judged.invalid_reason) == (y, reason), (rule_id, judged.detail)
        _library_keys(judged.detail, rule_id, premise=premise)
        final = certify(case, "equivalent_query", rewrite_rule=rule_id)
        assert (final.y, final.invalid_reason) == (y, reason), (rule_id, final.detail)
        _library_keys(final.detail, rule_id, premise=premise)
        assert final.cve

    unknown = certify(case, "equivalent_query", rewrite_rule="llm:not_in_library")
    assert (unknown.y, unknown.invalid_reason) == ("invalid", "untrusted_rewrite")
    frozen = certify(case, "equivalent_query", rewrite_rule="double_negation")
    assert frozen.y == "pass" and frozen.detail == _FROZEN_DETAIL
    paired = certify(
        case, "equivalent_query", rewrite_rule="llm:wrap_sub", paired_query="SELECT 1",
    )
    assert (paired.y, paired.invalid_reason) == ("invalid", "untrusted_rewrite")

    monkeypatch.delenv(LIBRARY_ENV, raising=False)
    absent = judge(case, "equivalent_query", rewrite_rule="llm:wrap_sub")
    assert (absent.y, absent.invalid_reason) == ("invalid", "untrusted_rewrite")
    assert "layer" not in absent.detail
    still = judge(case, "equivalent_query", rewrite_rule="double_negation")
    assert still.y == "pass" and still.detail == _FROZEN_DETAIL
