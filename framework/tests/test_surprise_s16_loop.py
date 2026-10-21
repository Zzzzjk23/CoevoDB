"""PostgreSQL lifecycle, plan features, and report integration."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from types import SimpleNamespace

import pytest
from surprise.baselines import pure_llm
from surprise.experiments import grid, loop, pg_instance
from surprise.features.data import extract_data, _describe_postgres
from surprise.features.extract import extract_isolated
from surprise.features.plan import extract_plan
from surprise.gates import s16_cases
from surprise.harness.contracts import SqlCase
from surprise.harness.ledger import Ledger
from surprise.harness.oracles.pg_target import PostgresTargetRunner
from surprise.hunter.operators import oracle_options
from surprise.metrics import recall, report
from surprise.metrics.dups import old_reports
from surprise.roles.gateway import Completion

@pytest.fixture
def no_dsns(monkeypatch):
    for name in ("COEVO_TARGET_PG_DSN", "COEVO_OLD_PG_DSN"):
        monkeypatch.delenv(name, raising=False)

def assert_removed(out):
    for kind in ("target", "old"):
        assert (out / "pg" / kind / "instance.json").is_file()
        assert not (out / "pg" / kind / "data").exists()
    assert pg_instance.stop_all(out) == []

def test_pg_plan_and_native_index(tmp_path, no_dsns):
    setup, query, predicate = s16_cases.CASES["PG-F"]
    case = SqlCase(engine="postgres", setup=setup, query=query, predicate=predicate)
    with pg_instance.running(tmp_path / "instances", old=False):
        phi = extract_isolated(case)
        assert phi.layers["plan"] == "ok"
        assert set(s16_cases.PGF_PLAN_LEAVES) <= set(phi.features)
        runner = PostgresTargetRunner()
        try:
            assert extract_plan(runner, "SELECT FROM", "postgres") == (set(), "unavailable")
        finally:
            runner.close()
    assert ("index_presence", None) in oracle_options(case, ("index_presence",))

def test_loop_owns_instances_and_manifest(tmp_path, no_dsns):
    out = tmp_path / "run"
    result = loop.run(out, seed=7, engines=("postgres",), max_experiments=3)
    assert result["experiments"] == 3
    assert result["engines"] == ["postgres"]
    with Ledger(out / "ledger.sqlite") as ledger:
        manifest = ledger.run_manifest(ledger.run_ids()[0])
    assert manifest["environment"]["engines"]["postgres"] == "16.15"
    assert manifest["environment"]["old_engines"]["postgres"] == "15.19"
    assert_removed(out)

def test_loop_reuses_exported_dsns(tmp_path):
    out = tmp_path / "run"
    with pg_instance.running(tmp_path / "instances"):
        result = loop.run(out, seed=7, engines=("postgres",), max_experiments=1)
        assert result["experiments"] == 1
        assert not (out / "pg").exists()

def test_duckdb_has_no_pg_directory(tmp_path, no_dsns):
    out = tmp_path / "run"
    assert loop.run(out, seed=7, max_experiments=1)["experiments"] == 1
    assert not (out / "pg").exists()

@pytest.mark.parametrize("exception,status", [(KeyboardInterrupt, "interrupted"), (RuntimeError, "error")])
def test_loop_cleans_up_on_failure(tmp_path, no_dsns, monkeypatch, exception, status):
    def interrupt(state):
        raise exception("scripted exit")
    monkeypatch.setattr(loop, "_drive", interrupt)
    out = tmp_path / "run"
    with pytest.raises(exception):
        loop.run(out, seed=7, engines=("postgres",), max_experiments=1)
    assert json.loads((out / "report.json").read_text())["status"] == status
    assert_removed(out)

def test_pure_llm_pg_uses_scripted_transport(tmp_path, no_dsns):
    prompts = []
    class Script:
        def complete(self, **kwargs):
            prompts.append(kwargs["prompt"])
            return Completion(text=json.dumps({"prediction": "pass", "cases": [{"setup": [], "query": "SELECT 1",
                "oracle": "plan_variant", "expect": "pass"}]}), input_tokens=1, output_tokens=1)
    out = tmp_path / "pure"
    result = pure_llm.run(out, seed=7, engine="postgres", max_experiments=1, transport=Script())
    assert result["experiments"] == 1
    assert "postgres 16.15" in prompts[0]
    assert_removed(out)

def test_grid_finish_stops_residual_servers(tmp_path, monkeypatch):
    directory = tmp_path / "cell"
    directory.mkdir()
    proc = SimpleNamespace(poll=lambda: 0, returncode=0, pid=123)
    cell = grid._CellProc(proc, grid._cell_log(directory).open("wb"), 0,
        {"name": "pg", "kind": "surprise"}, 7, 0, [], datetime.now(timezone.utc),
        time.monotonic(), 60, None, None, directory)
    calls = []
    def stop_all(path):
        calls.append(path)
        return [directory / "pg" / "target" / "data"]
    monkeypatch.setattr(pg_instance, "stop_all", stop_all)
    monkeypatch.setattr(grid, "_kill_group", lambda pid: None)
    assert grid._finish(cell) == "done"
    assert calls == [directory]
    assert "Stopped 1 residual PostgreSQL servers" in grid._cell_log(directory).read_text()
    assert json.loads((directory / "cell.json").read_text())["status"] == "done"

def test_recall_known_starts_pg_and_certifies(tmp_path, no_dsns, monkeypatch):
    instances = tmp_path / "known-instances"
    original = pg_instance.ensure
    def ensure(directory, *, old):
        assert old is True
        return original(instances, old=old)
    monkeypatch.setattr(pg_instance, "ensure", ensure)
    cases = Path(__file__).parents[1] / "surprise/gates/s16_data/known_pg_cases.json"
    out = tmp_path / "known.json"
    assert recall.main(["known", "--cases", str(cases), "--out", str(out)]) == 0
    known = json.loads(out.read_text())
    assert known["engines"]["postgres"] == "16.15"
    assert known["items"][0]["y"] == "fail"
    assert known["items"][0]["key"] == s16_cases.PGF_KEY
    assert not (instances / "target" / "data").exists()
    assert not (instances / "old" / "data").exists()
    assert pg_instance.stop_all(instances) == []

def test_report_engine_and_legacy_reports(tmp_path):
    config = {"reference": "pg", "arms": [{"name": "pg", "engines": ["postgres"]}]}
    assert report._reference_engine(config, {}) == "postgres"
    cells = {"pg/s7-r0": {"arm": "pg", "metrics": {"run": {"engines": ["postgres"]}}}}
    assert report._reference_engine({"reference": "pg", "arms": [{"name": "pg"}]}, cells) == "postgres"
    bugs = tmp_path / "bugs.jsonl"
    bugs.write_text(json.dumps({"root_key": "one", "candidate": {"kind": "wrong_result"}}) + "\n")
    assert old_reports(bugs, engine="postgres")[0]["engine"] == "postgres"


_PG_TYPES = (
    ("smallint", "integer"),
    ("integer", "integer"),
    ("bigint", "integer"),
    ("real", "float"),
    ("double precision", "float"),
    ("numeric(12, 3)", "decimal"),
    ("numeric", "decimal"),
    ("boolean", "boolean"),
    ("character varying(20)", "string"),
    ("character(4)", "string"),
    ("text", "string"),
    ("name", "string"),
    ("date", "date"),
    ("timestamp without time zone", "timestamp"),
    ("timestamp(3) with time zone", "timestamp"),
    ("uuid", "other"),
    ("integer[]", "other"),
)


def test_pg_data_catalog_types_and_quoted_relation(tmp_path, no_dsns):
    with pg_instance.running(tmp_path / "instances", old=False):
        runner = PostgresTargetRunner()
        try:
            for index, (sql_type, expected) in enumerate(_PG_TYPES):
                ref = f'"type_{index}\'quoted"'
                assert runner.run(f"CREATE TABLE {ref} (a {sql_type})").ok
                features, status = extract_data(runner, f"SELECT * FROM {ref}", "postgres")
                assert status == "ok", sql_type
                assert {leaf for leaf in features if leaf.startswith("data:type:")} == {
                    "data:type:" + expected
                }, sql_type
            assert _describe_postgres(runner, '"missing\'relation"') is None
            assert _describe_postgres(runner, '"unterminated') is None
        finally:
            runner.close()
        setup = ("CREATE TABLE types (s character varying(20), f double precision, n numeric(12,3))",)
        case = SqlCase(engine="postgres", setup=setup, query="SELECT * FROM types")
        phi = extract_isolated(case)
        assert phi.layers["data"] == "ok"
        assert {"data:type:string", "data:type:float", "data:type:decimal"} <= set(phi.features)
