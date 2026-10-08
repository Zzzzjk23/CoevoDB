"""Shared oracle registry, option validation, and DataFusion sound adapters."""

from __future__ import annotations

import pytest

from surprise.harness.contracts import INVALID_REASONS, Label, ORACLE_IDS, SqlCase
from surprise.harness.evaluate import evaluate
from surprise.harness.ledger import Ledger
from surprise.harness.oracles import IMPLEMENTED, judge
from surprise.harness.oracles import registry
from surprise.harness.oracles.registry import (
    REFERENCE_ENGINES,
    SOUND_ORACLE_IDS,
    TARGET_ENGINES,
    OracleOptions,
    get_handler,
    make_options,
    register,
    runner_factory_for,
    validate_request,
)
from targets.datafusion_runner import DataFusionRunner
from targets.duckdb_runner import DuckDBRunner

_SETUP = (
    "CREATE TABLE t(a INTEGER, b INTEGER)",
    "INSERT INTO t VALUES (1, 10), (2, 0), (NULL, 3)",
)


_LATER_IDS = (
    "index_presence",
    "equivalent_query",
    "version_differential",
    "cross_dbms",
)


def _case(query: str = "SELECT a, b FROM t", predicate: str | None = "a > 0",
          engine: str = "duckdb", setup: tuple[str, ...] = _SETUP) -> SqlCase:
    return SqlCase(engine=engine, setup=setup, query=query, predicate=predicate)


def _fake_pass_handler(oracle_id: str):
    def judge_case(case, *, factory, timeout_s, options):
        return Label(y="pass", oracle=oracle_id)

    return judge_case


def _absent_module(oracle_id: str) -> str:
    return f"surprise.harness.oracles._s03_registry_absent_{oracle_id}"


def test_implemented_is_the_seven_plan_ids() -> None:
    assert IMPLEMENTED == ORACLE_IDS
    assert IMPLEMENTED == (
        "tlp",
        "norec",
        "plan_variant",
        "index_presence",
        "equivalent_query",
        "version_differential",
        "cross_dbms",
    )
    assert SOUND_ORACLE_IDS == ("tlp", "norec", "plan_variant")
    assert TARGET_ENGINES == ("duckdb", "datafusion")
    assert REFERENCE_ENGINES == ("duckdb", "datafusion", "sqlite", "postgres")
    assert INVALID_REASONS[-4:] == (
        "untrusted_rewrite",
        "direction_unknown",
        "insufficient_engines",
        "non_unique_outlier",
    )


def test_register_and_get_handler_for_sound_oracles() -> None:
    for oracle in SOUND_ORACLE_IDS:
        handler = get_handler(oracle)
        assert callable(handler)
        assert registry.get_handler(oracle) is handler
    with pytest.raises(ValueError, match="already registered"):
        register("tlp", get_handler("tlp"))
    with pytest.raises(ValueError):
        register("no_such_oracle", get_handler("tlp"))
    with pytest.raises(ValueError):
        get_handler("no_such_oracle")
    with pytest.raises(ValueError):
        get_handler("TLP")


def test_missing_later_module_is_not_a_pass(monkeypatch) -> None:
    planted = dict(registry._HANDLERS)
    fakes = {oracle_id: _fake_pass_handler(oracle_id) for oracle_id in _LATER_IDS}
    planted.update(fakes)
    monkeypatch.setattr(registry, "_HANDLERS", planted)
    assert get_handler("index_presence") is fakes["index_presence"]

    handlers = dict(registry._HANDLERS)
    modules = dict(registry._LAZY_MODULES)
    for oracle_id in _LATER_IDS:
        handlers.pop(oracle_id, None)
        modules[oracle_id] = _absent_module(oracle_id)
    monkeypatch.setattr(registry, "_HANDLERS", handlers)
    monkeypatch.setattr(registry, "_LAZY_MODULES", modules)

    with pytest.raises(ImportError):
        get_handler("index_presence")
    with pytest.raises(ImportError):
        get_handler("equivalent_query")
    with pytest.raises(ImportError):
        judge(_case(), "cross_dbms")
    limited = _case("SELECT a FROM t LIMIT 2", predicate=None)
    for oracle in ("index_presence", "equivalent_query", "version_differential", "cross_dbms"):
        label = judge(limited, oracle)
        assert (label.y, label.invalid_reason) == ("invalid", "nondeterministic"), oracle
        assert "form" not in label.detail


def test_runner_factory_for_maps_target_engines() -> None:
    assert runner_factory_for("duckdb") is DuckDBRunner
    assert runner_factory_for("datafusion") is DataFusionRunner
    with pytest.raises(ValueError):
        runner_factory_for("sqlite")
    with pytest.raises(ValueError):
        runner_factory_for("postgres")


def test_options_validation_rejects_aliases_and_the_target() -> None:
    case = _case(engine="datafusion")
    options = make_options(reference_factories={"duckdb_old": DuckDBRunner})
    with pytest.raises(ValueError, match="duckdb_old"):
        validate_request(case, "cross_dbms", options)
    with pytest.raises(ValueError, match="target engine"):
        validate_request(
            case, "cross_dbms",
            make_options(reference_factories={"datafusion": DuckDBRunner}),
        )
    with pytest.raises(ValueError):
        make_options(reference_factories=["duckdb"])
    with pytest.raises(ValueError):
        validate_request(
            case, "tlp",
            make_options(reference_factories={"duckdb": "not-callable"}),
        )
    allowed = make_options(reference_factories={
        "duckdb": DuckDBRunner, "sqlite": DuckDBRunner, "postgres": DuckDBRunner,
    })
    validate_request(case, "cross_dbms", allowed)
    validate_request(case, "tlp", make_options(reference_factories=None))
    validate_request(case, "tlp", make_options(reference_factories={}))


def test_validation_happens_before_any_runner_opens() -> None:
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return DuckDBRunner()

    case = _case()
    with pytest.raises(ValueError):
        judge(case, "no_such_oracle", runner_factory=factory)
    with pytest.raises(ValueError):
        judge(_case(engine="sqlite"), "tlp", runner_factory=factory)
    with pytest.raises(ValueError):
        judge(
            case, "tlp", runner_factory=factory,
            reference_factories={"duckdb": DuckDBRunner},
        )
    with pytest.raises(ValueError):
        judge(case, "tlp", runner_factory=factory, old_python=1)
    assert calls["n"] == 0


def test_sound_oracles_pass_on_both_target_engines() -> None:
    for engine in TARGET_ENGINES:
        case = _case(engine=engine)
        for oracle in SOUND_ORACLE_IDS:
            first = judge(case, oracle)
            assert first.y == "pass", (engine, oracle, first.to_dict())
            assert first.to_dict() == judge(case, oracle).to_dict()
            assert first.cve == {}
            handler = get_handler(oracle)
            via_handler = handler(
                case, factory=runner_factory_for(engine), timeout_s=10.0,
                options=OracleOptions(),
            )
            assert via_handler.to_dict() == first.to_dict()


def test_datafusion_setup_error_and_not_applicable() -> None:
    broken = _case(
        engine="datafusion",
        setup=("INSERT INTO no_such_table VALUES (1)",),
    )
    label = judge(broken, "plan_variant")
    assert (label.y, label.invalid_reason) == ("invalid", "setup_error")
    assert label.detail["error"]

    skipped = judge(_case(predicate=None, engine="datafusion"), "norec")
    assert (skipped.y, skipped.invalid_reason) == ("invalid", "not_applicable")

    limited = judge(_case("SELECT a FROM t LIMIT 2", None, engine="datafusion"), "tlp")
    assert (limited.y, limited.invalid_reason) == ("invalid", "nondeterministic")


def test_evaluate_accounts_datafusion_and_missing_handler(tmp_path, monkeypatch) -> None:
    ledger = Ledger(tmp_path / "ledger.sqlite")
    try:
        ledger.start_run("run-1", {})
        case = _case(engine="datafusion")
        record = evaluate(case, "tlp", ledger=ledger, run_id="run-1", purpose="s03")
        assert ledger.count(run_id="run-1") == 1
        assert record.label.to_dict() == judge(case, "tlp").to_dict()
        assert record.label.y == "pass"

        planted = dict(registry._HANDLERS)
        fake = _fake_pass_handler("index_presence")
        planted["index_presence"] = fake
        monkeypatch.setattr(registry, "_HANDLERS", planted)
        assert get_handler("index_presence") is fake

        handlers = dict(registry._HANDLERS)
        handlers.pop("index_presence", None)
        modules = dict(registry._LAZY_MODULES)
        modules["index_presence"] = _absent_module("index_presence")
        monkeypatch.setattr(registry, "_HANDLERS", handlers)
        monkeypatch.setattr(registry, "_LAZY_MODULES", modules)

        missing = evaluate(_case(), "index_presence", ledger=ledger, run_id="run-1", purpose="s03")
        assert (missing.label.y, missing.label.invalid_reason) == ("invalid", "harness_error")
        assert "ImportError" in missing.label.detail["exception"] or (
            "ModuleNotFoundError" in missing.label.detail["exception"]
        )
        assert ledger.count(run_id="run-1") == 2
    finally:
        ledger.close()


def test_empty_reference_map_is_accepted_on_sound_oracles() -> None:
    case = _case()
    passed = judge(case, "tlp", reference_factories={})
    assert passed.y == "pass"
    again = judge(case, "tlp", reference_factories=None)
    assert passed.to_dict() == again.to_dict()
