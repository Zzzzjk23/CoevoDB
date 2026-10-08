"""Version differential: real old interpreters, and direction only with evidence.

Fixed runners stand in for the new engine only where the verdict depends on a
constructed timeout, a bad worker payload, or a tie that real engines do not
produce. DuckDB 1.1.3 and DataFusion 50.0.0 still execute the measured cases.
"""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

import pytest

from oracles.db_runner import QueryResult
from oracles.normalize import loose_bag
from surprise.harness.contracts import IdentityEvidence, Label, SqlCase
from surprise.harness.oracles import judge
from surprise.harness.oracles import version_differential as vd
from surprise.harness.oracles.registry import get_handler, make_options
from surprise.harness.oracles.version_differential import judge_case

_ROOT = Path(__file__).resolve().parents[2]
_SETUP = (
    "CREATE TABLE t(a INT, b INT)",
    "INSERT INTO t VALUES (1, 1), (2, NULL), (3, 3)",
)
_F2_OLD = [[10, 30], [20, 30]]
_F2_NEW = [[10, 10], [20, 20]]
_TYPED = [
    1.5,
    "temporal:2020-01-02",
    "temporal:2020-01-02T03:04:05",
    "bytes:6869",
]
_DUCK_TYPES = (
    "SELECT CAST(1.50 AS DECIMAL(10,2)), DATE '2020-01-02', "
    "TIMESTAMP '2020-01-02 03:04:05', 'hi'::BLOB"
)
_DF_TYPES = (
    "SELECT arrow_cast(1.50, 'Decimal128(10, 2)'), "
    "arrow_cast('2020-01-02', 'Date32'), "
    "arrow_cast('2020-01-02T03:04:05', 'Timestamp(Microsecond, None)'), "
    "arrow_cast('hi', 'Binary')"
)


def _case(
    engine: str = "duckdb",
    query: str = "SELECT a, b FROM t",
    predicate: str | None = "b > 1",
    setup: tuple[str, ...] = _SETUP,
) -> SqlCase:
    return SqlCase(engine=engine, setup=setup, query=query, predicate=predicate)


def _f2() -> SqlCase:
    recall = json.loads((_ROOT / "docs" / "recall_repros.json").read_text(encoding="utf-8"))
    block = recall["F2"]
    return SqlCase("duckdb", tuple(block["setup"]), block["q"], None)


def _fixed(
    rows: tuple | list = (),
    *,
    error: str | None = None,
    internal: bool = False,
    timed_out: bool = False,
    setup_error: str | None = None,
    version: str = "fixture",
):
    class Runner:
        engine_version = version

        def setup(self, statements):
            if setup_error is not None:
                text = statements[0] if statements else ""
                return [(text, setup_error)]
            return [(statement, None) for statement in statements]

        def run(self, sql, timeout_s=10.0):
            return QueryResult(
                rows=[list(row) for row in rows],
                error=error,
                is_internal_error=internal,
                timed_out=timed_out,
            )

        def close(self):
            pass

    return Runner


def _old_rows(rows: list, *, error: str | None = None, version: str = "1.1.3") -> vd._OldResult:
    return vd._OldResult(version, rows, error, None, None)


def _pass(oracle_id: str) -> Label:
    return Label(y="pass", oracle=oracle_id)


def _index_fail() -> Label:
    return Label(
        y="fail",
        oracle="index_presence",
        fail_kind="wrong_result",
        identity=IdentityEvidence(switches=("art",), behavior={"missing": 1, "extra": 1}),
    )


def _detail_keys(label: Label) -> None:
    for key in (
        "old_version",
        "new_version",
        "old_rows",
        "new_rows",
        "direction",
        "direction_evidence",
    ):
        assert key in label.detail


def test_handler_is_registered() -> None:
    assert get_handler("version_differential") is judge_case


def test_clean_select_passes_on_both_real_engines(monkeypatch) -> None:
    secret = "dummy-not-a-real-key"
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)
    seen: list[tuple] = []
    real_run = vd.subprocess.run

    def wrapped(*args, **kwargs):
        seen.append((args, kwargs))
        return real_run(*args, **kwargs)

    monkeypatch.setattr(vd.subprocess, "run", wrapped)
    expected = {"duckdb": ("1.1.3", "1.5.5"), "datafusion": ("50.0.0", "54.0.0")}
    dumped = []
    for engine, (old_version, new_version) in expected.items():
        case = _case(engine)
        first = judge(case, "version_differential")
        assert first.y == "pass", first.to_dict()
        assert first.cve == {}
        assert first.detail["direction"] == "agree"
        assert first.detail["direction_evidence"] == {}
        assert first.detail["old_version"] == old_version
        assert first.detail["new_version"] == new_version
        assert first.detail["old_rows"] == [[3, 3]]
        assert first.detail["new_rows"] == [[3, 3]]
        assert "WHERE" in first.detail["full_query"]
        second = judge(case, "version_differential")
        assert first.to_dict() == second.to_dict()
        dumped.append(json.dumps(first.to_dict()))

    worker_calls = []
    for args, kwargs in seen:
        command = args[0] if args else kwargs.get("args")
        if command and any("version_worker.py" in str(part) for part in command):
            worker_calls.append((list(command), kwargs))
    assert len(worker_calls) == 4
    for command, kwargs in worker_calls:
        assert "-I" in command
        assert "-m" not in command
        assert "coevo-version-" in str(kwargs["cwd"])
        env = kwargs["env"]
        assert "DEEPSEEK_API_KEY" not in {key.upper() for key in env}
        assert secret not in env.values()
    assert dumped
    for text in dumped:
        assert secret not in text
        assert "coevo-version-" not in text


def test_explicit_old_python_is_the_interpreter_that_runs() -> None:
    python = vd._resolve_old_python("datafusion", None)
    assert python is not None and python.is_file()
    case = _case("datafusion", query="SELECT 1", predicate=None, setup=())
    label = judge(case, "version_differential", old_python=str(python))
    assert label.y == "pass"
    assert label.detail["old_version"] == "50.0.0"
    assert label.detail["new_version"] == "54.0.0"
    assert label.detail["old_rows"] == [[1]]


def test_version_string_mismatch_has_no_direction() -> None:
    for engine in ("duckdb", "datafusion"):
        case = _case(engine, query="SELECT version()", predicate=None, setup=())
        label = judge(case, "version_differential", reference_factories={})
        assert (label.y, label.invalid_reason) == ("invalid", "direction_unknown"), label.to_dict()
        assert label.detail["direction"] == "unknown"
        assert label.detail["direction_evidence"] == {}
        assert label.cve == {}
        assert label.detail["old_rows"] != label.detail["new_rows"]


def test_f2_regression_matches_the_measured_bags() -> None:
    case = _f2()
    first = judge(case, "version_differential")
    second = judge(case, "version_differential")
    assert first.to_dict() == second.to_dict()
    assert first.y == "fail"
    assert first.fail_kind == "wrong_result"
    assert first.cve == {}
    assert first.detail["direction"] == "regression"
    assert first.detail["old_version"] == "1.1.3"
    assert first.detail["new_version"] == "1.5.5"
    assert loose_bag(first.detail["old_rows"]) == loose_bag(_F2_OLD)
    assert loose_bag(first.detail["new_rows"]) == loose_bag(_F2_NEW)
    assert first.identity.behavior == {"missing": 2, "extra": 2}
    assert "no_optimizer" in first.identity.switches
    evidence = first.detail["direction_evidence"]
    assert set(evidence["majority"]) >= {"datafusion", "sqlite"}
    assert set(evidence["majority"]) <= {"datafusion", "sqlite", "postgres"}
    assert any(
        item["oracle"] == "plan_variant" and item["switches"] == ["no_optimizer"]
        for item in evidence["witnesses"]
    )

    witnessed = judge(case, "version_differential", reference_factories={})
    assert witnessed.y == "fail"
    assert witnessed.fail_kind == "wrong_result"
    assert witnessed.detail["direction"] == "regression"
    assert "no_optimizer" in witnessed.identity.switches
    assert "majority" not in witnessed.detail["direction_evidence"]
    assert witnessed.detail["direction_evidence"]["witnesses"]


def test_both_engines_erroring_is_a_pass(monkeypatch) -> None:
    consulted = {"n": 0}

    def boom():
        consulted["n"] += 1
        raise AssertionError("references consulted")

    def witnesses(*args, **kwargs):
        raise AssertionError("witnesses consulted")

    monkeypatch.setattr(vd, "_collect_witnesses", witnesses)
    case = _case(query="SELECT * FROM no_such", predicate=None, setup=())
    label = judge(
        case,
        "version_differential",
        reference_factories={"datafusion": boom, "sqlite": boom},
    )
    assert label.y == "pass", label.to_dict()
    assert label.detail["direction"] == "agree"
    assert label.detail["old_rows"] == []
    assert label.detail["new_rows"] == []
    assert consulted["n"] == 0
    assert label.cve == {}


def test_same_wrong_rows_do_not_consult_references_or_witnesses(monkeypatch) -> None:
    def boom():
        raise AssertionError("references consulted")

    def witnesses(*args, **kwargs):
        raise AssertionError("witnesses consulted")

    monkeypatch.setattr(vd, "_query_old", lambda *args, **kwargs: _old_rows([[9], [9]]))
    monkeypatch.setattr(vd, "_collect_witnesses", witnesses)
    label = judge_case(
        _case(query="SELECT a FROM t", predicate=None),
        factory=_fixed([[9], [9]]),
        timeout_s=5,
        options=make_options(reference_factories={"datafusion": boom, "sqlite": boom}),
    )
    assert label.y == "pass"
    assert label.detail["direction"] == "agree"
    assert label.detail["old_rows"] == [[9], [9]]


def test_old_internal_error_is_not_a_new_regression(monkeypatch) -> None:
    monkeypatch.setattr(
        vd,
        "_query_old",
        lambda *args, **kwargs: _old_rows(
            [],
            error="InternalException: INTERNAL Error: injected",
        ),
    )
    monkeypatch.setattr(vd, "_index_presence_available", lambda: False)
    case = _case(query="SELECT 1", predicate=None, setup=())
    label = judge(case, "version_differential", reference_factories={})
    assert (label.y, label.invalid_reason) == ("invalid", "direction_unknown"), label.to_dict()
    assert label.fail_kind is None
    assert label.detail["direction"] == "unknown"
    assert label.detail["new_rows"] == [[1]]


def test_a_new_version_witness_can_direct_an_old_error(monkeypatch) -> None:
    monkeypatch.setattr(
        vd,
        "_query_old",
        lambda *args, **kwargs: _old_rows([], error="InternalException: INTERNAL Error: injected"),
    )
    monkeypatch.setattr(vd, "_index_presence_available", lambda: True)

    def call(case, oracle_id, factory, timeout_s):
        if oracle_id == "index_presence":
            return _index_fail()
        return _pass(oracle_id)

    monkeypatch.setattr(vd, "_call_public_judge", call)
    label = judge_case(
        _case(query="SELECT 1", predicate=None, setup=()),
        factory=_fixed([[1]]),
        timeout_s=5,
        options=make_options(reference_factories={}),
    )
    assert label.y == "fail"
    assert label.fail_kind == "wrong_result"
    assert label.detail["direction"] == "regression"
    assert label.identity.switches == ("art",)
    assert label.identity.error_class is None
    assert label.detail["direction_evidence"]["witnesses"][0]["oracle"] == "index_presence"


def test_old_subprocess_timeout_is_invalid(monkeypatch) -> None:
    def timed_out(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="python", timeout=1)

    monkeypatch.setattr(vd, "_run_worker", timed_out)
    label = judge_case(
        _case(query="SELECT 1", predicate=None, setup=()),
        factory=_fixed([[1]]),
        timeout_s=5,
        options=make_options(),
    )
    assert (label.y, label.invalid_reason) == ("invalid", "timeout")
    assert label.detail["error"] == "old execution timed out"
    assert label.detail["direction"] == "unknown"
    _detail_keys(label)


def test_new_timeout_does_not_run_the_old_engine(monkeypatch) -> None:
    def explode(*args, **kwargs):
        raise AssertionError("old engine ran")

    monkeypatch.setattr(vd, "_query_old", explode)
    label = judge_case(
        _case(query="SELECT 1", predicate=None, setup=()),
        factory=_fixed([[1]], timed_out=True, error="timed out"),
        timeout_s=5,
        options=make_options(),
    )
    assert (label.y, label.invalid_reason) == ("invalid", "timeout")
    assert label.detail["direction"] == "unknown"


def test_bad_worker_output_is_harness_error(monkeypatch) -> None:
    def bad_json(*args, **kwargs):
        return subprocess.CompletedProcess(
            ["python"],
            0,
            "NOT JSON\ncoevo-version-secret",
            "stderr-secret",
        )

    monkeypatch.setattr(vd, "_run_worker", bad_json)
    label = judge_case(
        _case(query="SELECT 1", predicate=None, setup=()),
        factory=_fixed([[1]]),
        timeout_s=5,
        options=make_options(),
    )
    assert (label.y, label.invalid_reason) == ("invalid", "harness_error")
    assert label.detail["error"] == "worker output is not valid JSON"
    dumped = json.dumps(label.to_dict())
    assert "coevo-version-" not in dumped
    assert "stderr-secret" not in dumped
    assert "NOT JSON" not in dumped

    def protocol(*args, **kwargs):
        return subprocess.CompletedProcess(
            ["python"],
            0,
            json.dumps({"protocol_error": "TypeError: nope", "engine_version": "1.1.3"}),
            "",
        )

    monkeypatch.setattr(vd, "_run_worker", protocol)
    again = judge_case(
        _case(query="SELECT 1", predicate=None, setup=()),
        factory=_fixed([[1]]),
        timeout_s=5,
        options=make_options(),
    )
    assert again.detail["error"] == "worker output is not valid JSON"
    assert again.detail["old_version"] is None


def test_setup_errors_stay_invalid(monkeypatch) -> None:
    def explode(*args, **kwargs):
        raise AssertionError("old engine ran")

    monkeypatch.setattr(vd, "_query_old", explode)
    new_side = judge_case(
        _case(setup=("INSERT INTO missing VALUES (1)",), query="SELECT 1", predicate=None),
        factory=_fixed(setup_error="Catalog Error: missing"),
        timeout_s=5,
        options=make_options(),
    )
    assert (new_side.y, new_side.invalid_reason) == ("invalid", "setup_error")
    assert new_side.detail["error"] == "Catalog Error: missing"
    assert new_side.detail["direction"] == "unknown"
    _detail_keys(new_side)


def test_old_setup_error_is_invalid() -> None:
    old_side = judge_case(
        _case(setup=("INSERT INTO missing VALUES (1)",), query="SELECT 1", predicate=None),
        factory=_fixed([[1]]),
        timeout_s=20,
        options=make_options(),
    )
    assert (old_side.y, old_side.invalid_reason) == ("invalid", "setup_error"), old_side.to_dict()
    assert old_side.detail["old_version"] == "1.1.3"
    assert old_side.detail["error"]
    assert old_side.y != "pass"


def test_missing_interpreter_is_harness_error(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("COEVO_VENVS", str(tmp_path))
    label = judge_case(
        _case(query="SELECT 1", predicate=None, setup=()),
        factory=_fixed([[1]]),
        timeout_s=5,
        options=make_options(),
    )
    assert (label.y, label.invalid_reason) == ("invalid", "harness_error")
    assert label.detail["error"] == "old interpreter is missing"
    assert label.detail["old_version"] is None


def test_explicit_missing_interpreter_does_not_fall_back() -> None:
    missing = _ROOT / ".orch" / "tmp" / "no-such-python.exe"
    label = judge_case(
        _case(query="SELECT 1", predicate=None, setup=()),
        factory=_fixed([[1]]),
        timeout_s=5,
        options=make_options(old_python=str(missing)),
    )
    assert (label.y, label.invalid_reason) == ("invalid", "harness_error")
    assert label.detail["error"] == "old interpreter is missing"
    assert label.detail["old_rows"] == []


def test_duckdb_type_transport_preserves_normalized_cells() -> None:
    case = _case("duckdb", query=_DUCK_TYPES, predicate=None, setup=())
    label = judge(case, "version_differential")
    assert label.y == "pass", label.to_dict()
    assert label.detail["old_rows"] == [_TYPED]
    assert label.detail["new_rows"] == [_TYPED]
    assert label.detail["new_rows"][0][0] == 1.5
    assert isinstance(label.detail["new_rows"][0][0], float)


def test_datafusion_type_transport_preserves_normalized_cells() -> None:
    python = vd._resolve_old_python("datafusion", None)
    assert python is not None
    old = vd._query_old(python, "datafusion", [], _DF_TYPES, 20)
    assert old.protocol_error is None
    assert old.error is None
    assert old.setup_error is None
    assert old.version == "50.0.0"
    assert old.rows == [_TYPED]
    assert isinstance(old.rows[0][0], float)

    decimal = judge(
        _case(
            "datafusion",
            query="SELECT arrow_cast(1.50, 'Decimal128(10, 2)')",
            predicate=None,
            setup=(),
        ),
        "version_differential",
    )
    assert decimal.y == "pass", decimal.to_dict()
    assert decimal.detail["old_rows"] == [[1.5]]
    assert decimal.detail["new_rows"] == [[1.5]]
    assert decimal.detail["old_version"] == "50.0.0"
    assert decimal.detail["new_version"] == "54.0.0"


def test_two_supporters_direct_a_regression_without_witnesses(monkeypatch) -> None:
    monkeypatch.setattr(vd, "_query_old", lambda *args, **kwargs: _old_rows([[1]]))
    monkeypatch.setattr(vd, "_collect_witnesses", lambda *args, **kwargs: [])
    label = judge_case(
        _case(query="SELECT a FROM t", predicate=None),
        factory=_fixed([[2]]),
        timeout_s=5,
        options=make_options(reference_factories={
            "datafusion": _fixed([[1]]),
            "sqlite": _fixed([[1]]),
        }),
    )
    assert label.y == "fail"
    assert label.fail_kind == "wrong_result"
    assert label.detail["direction"] == "regression"
    assert label.identity.switches == ()
    assert label.identity.behavior == {"missing": 1, "extra": 1}
    assert label.detail["direction_evidence"] == {"majority": ["datafusion", "sqlite"]}


def test_fewer_than_two_supporters_or_a_dissenter_has_no_direction(monkeypatch) -> None:
    monkeypatch.setattr(vd, "_query_old", lambda *args, **kwargs: _old_rows([[1]]))
    monkeypatch.setattr(vd, "_collect_witnesses", lambda *args, **kwargs: [])
    case = _case(query="SELECT a FROM t", predicate=None)
    one = judge_case(
        case,
        factory=_fixed([[2]]),
        timeout_s=5,
        options=make_options(reference_factories={"datafusion": _fixed([[1]])}),
    )
    assert (one.y, one.invalid_reason) == ("invalid", "direction_unknown")
    assert one.detail["old_rows"] == [[1]]
    assert one.detail["new_rows"] == [[2]]

    split = judge_case(
        case,
        factory=_fixed([[2]]),
        timeout_s=5,
        options=make_options(reference_factories={
            "datafusion": _fixed([[1]]),
            "sqlite": _fixed([[1]]),
            "postgres": _fixed([[9]]),
        }),
    )
    assert (split.y, split.invalid_reason) == ("invalid", "direction_unknown")

    errored = judge_case(
        case,
        factory=_fixed([[2]]),
        timeout_s=5,
        options=make_options(reference_factories={
            "datafusion": _fixed([[1]]),
            "sqlite": _fixed([[1]]),
            "postgres": _fixed(error="connection refused"),
        }),
    )
    assert errored.y == "fail"
    assert errored.detail["direction_evidence"]["majority"] == ["datafusion", "sqlite"]


def test_no_references_and_no_witness_is_direction_unknown(monkeypatch) -> None:
    monkeypatch.setattr(vd, "_query_old", lambda *args, **kwargs: _old_rows([[1]]))
    monkeypatch.setattr(vd, "_collect_witnesses", lambda *args, **kwargs: [])
    label = judge_case(
        _case(query="SELECT a FROM t", predicate=None),
        factory=_fixed([[2]]),
        timeout_s=5,
        options=make_options(reference_factories={}),
    )
    assert (label.y, label.invalid_reason) == ("invalid", "direction_unknown")
    assert label.detail["direction_evidence"] == {}


def test_witness_runtime_error_propagates(monkeypatch) -> None:
    monkeypatch.setattr(vd, "_query_old", lambda *args, **kwargs: _old_rows([[1]]))

    def call(case, oracle_id, factory, timeout_s):
        if oracle_id == "plan_variant":
            raise RuntimeError("plan variant exploded")
        return _pass(oracle_id)

    monkeypatch.setattr(vd, "_call_public_judge", call)
    with pytest.raises(RuntimeError, match="plan variant exploded"):
        judge_case(
            _case(query="SELECT a FROM t", predicate=None),
            factory=_fixed([[2]]),
            timeout_s=5,
            options=make_options(reference_factories={}),
        )


def test_unavailable_index_presence_is_not_called(monkeypatch) -> None:
    called: list[str] = []
    monkeypatch.setattr(vd, "_query_old", lambda *args, **kwargs: _old_rows([[1]]))
    monkeypatch.setattr(vd, "_index_presence_available", lambda: False)

    def call(case, oracle_id, factory, timeout_s):
        called.append(oracle_id)
        return _pass(oracle_id)

    monkeypatch.setattr(vd, "_call_public_judge", call)
    label = judge_case(
        _case(query="SELECT a FROM t", predicate=None),
        factory=_fixed([[2]]),
        timeout_s=5,
        options=make_options(reference_factories={}),
    )
    assert called == ["plan_variant"]
    assert (label.y, label.invalid_reason) == ("invalid", "direction_unknown")


def test_index_presence_import_error_is_not_harness_error(monkeypatch) -> None:
    monkeypatch.setattr(vd, "_query_old", lambda *args, **kwargs: _old_rows([[1]]))
    monkeypatch.setattr(vd, "_index_presence_available", lambda: True)

    def call(case, oracle_id, factory, timeout_s):
        if oracle_id == "index_presence":
            raise ModuleNotFoundError("surprise.harness.oracles.index_presence")
        return _pass(oracle_id)

    monkeypatch.setattr(vd, "_call_public_judge", call)
    label = judge_case(
        _case(query="SELECT a FROM t", predicate=None),
        factory=_fixed([[2]]),
        timeout_s=5,
        options=make_options(reference_factories={}),
    )
    assert (label.y, label.invalid_reason) == ("invalid", "direction_unknown")
    assert label.invalid_reason != "harness_error"


def test_index_presence_failure_is_carried_on_the_version_label(monkeypatch) -> None:
    monkeypatch.setattr(vd, "_query_old", lambda *args, **kwargs: _old_rows([[1]]))
    monkeypatch.setattr(vd, "_index_presence_available", lambda: True)

    def call(case, oracle_id, factory, timeout_s):
        if oracle_id == "index_presence":
            return _index_fail()
        return _pass(oracle_id)

    monkeypatch.setattr(vd, "_call_public_judge", call)
    label = judge_case(
        _case(query="SELECT a FROM t", predicate=None),
        factory=_fixed([[2]]),
        timeout_s=5,
        options=make_options(reference_factories={}),
    )
    assert label.y == "fail"
    assert label.detail["direction"] == "regression"
    assert label.identity.switches == ("art",)
    recorded = label.detail["direction_evidence"]["witnesses"]
    assert recorded == [{
        "oracle": "index_presence",
        "y": "fail",
        "fail_kind": "wrong_result",
        "switches": ["art"],
        "error_class": None,
        "behavior": {"missing": 1, "extra": 1},
    }]


def test_version_alias_is_rejected() -> None:
    case = _case(query="SELECT 1", predicate=None, setup=())
    with pytest.raises(ValueError):
        judge(case, "version_differential", reference_factories={"duckdb_old": _fixed([[1]])})


def test_version_alias_reaches_reference_collection_on_a_mismatch(monkeypatch) -> None:
    monkeypatch.setattr(vd, "_query_old", lambda *args, **kwargs: _old_rows([[1]]))
    with pytest.raises(ValueError, match="version alias"):
        judge_case(
            _case(query="SELECT a FROM t", predicate=None),
            factory=_fixed([[2]]),
            timeout_s=5,
            options=make_options(reference_factories={"duckdb_old": _fixed([[1]])}),
        )


def test_worker_imports_stay_inside_the_engine_functions() -> None:
    tree = ast.parse(vd._WORKER.read_text(encoding="utf-8"))
    top: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            top.add((node.module or "").split(".")[0])
    assert top <= {"json", "math", "sys", "datetime", "decimal", "__future__"}

    def imported(function_name: str) -> set[str]:
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == function_name
        )
        names: set[str] = set()
        for child in ast.walk(function):
            if isinstance(child, ast.Import):
                names.update(alias.name.split(".")[0] for alias in child.names)
            elif isinstance(child, ast.ImportFrom):
                names.add((child.module or "").split(".")[0])
        return names

    duck = imported("_run_duckdb")
    fusion = imported("_run_datafusion")
    assert duck == {"duckdb"}
    assert fusion == {"datafusion"}
    text = vd._WORKER.read_text(encoding="utf-8")
    assert "DEEPSEEK" not in text
    assert "os.environ" not in text
    assert "surprise" not in text
