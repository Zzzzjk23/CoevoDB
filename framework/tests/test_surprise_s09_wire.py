"""LLM roles switch into the Hunter and the loop. With the switch off, both match S8."""

from __future__ import annotations

import ast
import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

from surprise.diagnoser import Diagnoser
from surprise.experiments import loop as loop_mod
from surprise.experiments.loop import UsageError, _PROGRESS_KEYS, main, run
from surprise.features.registry import Registry
from surprise.harness.contracts import ExperimentRecord, Label, SqlCase
from surprise.harness.ledger import Ledger
from surprise.hunter import LANES, Candidate, Hunter
from surprise.hunter import constants as hunter_constants
from surprise.theory import Workbench

FRAMEWORK = Path(__file__).resolve().parents[1]
_REPORT_ORDER = (
    "run_id",
    "seed",
    "engines",
    "oracles",
    "beta",
    "status",
    "experiments",
    "choices",
    "started_at",
    "finished_at",
    "wall_s",
    "labels",
    "lanes",
    "triage",
    "hypotheses",
    "families",
    "edits",
    "curve",
    "teeth",
    "new_families",
    "extractor",
)
_CONFIG_ORDER = (
    "seed",
    "engines",
    "oracles",
    "max_experiments",
    "max_minutes",
    "beta",
    "bootstrap",
    "run_id",
)
_POOL_BASE = (
    *LANES,
    "rejected_known",
    "rejected_bad_setup",
    "rejected_novelty",
    "scored",
    "rounds",
)


def _corpus(path: Path, seeds: list[dict] | None) -> Path:
    path.write_text(json.dumps([] if seeds is None else seeds), encoding="utf-8")
    return path


def _tiny(path: Path) -> Path:
    return _corpus(
        path,
        [
            {
                "setup_sqls": ["CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1), (2)"],
                "query": "SELECT a FROM t WHERE a > 0",
                "source": "s09-wire",
                "engine": "duckdb",
                "tags": [],
            },
            {
                "setup_sqls": ["CREATE TABLE u(b INT)", "INSERT INTO u VALUES (9)"],
                "query": "SELECT b FROM u",
                "source": "s09-wire-b",
                "engine": "duckdb",
                "tags": [],
            },
        ],
    )


def _case(query: str, setup: tuple[str, ...] | None = None) -> SqlCase:
    return SqlCase(
        engine="duckdb",
        setup=setup or ("CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1)"),
        query=query,
    )


def _candidate(case: SqlCase, lane: str) -> Candidate:
    return Candidate(
        case=case,
        oracle="plan_variant",
        rule=None,
        lane=lane,
        hypothesis_id=None,
        parent=None,
        op="implementer" if lane == "implement" else lane,
        target={"required": ["ast:stmt:select"]} if lane == "implement" else None,
    )


def _recorded(case: SqlCase, *, y: str = "pass", reason: str | None = None) -> ExperimentRecord:
    if y == "invalid":
        label = Label(y="invalid", oracle="plan_variant", invalid_reason=reason or "setup_error")
    else:
        label = Label(y="pass", oracle="plan_variant")
    return ExperimentRecord(
        record_id="r1",
        run_id="s09-wire",
        seq=1,
        case=case,
        label=label,
        purpose="test",
        created_at="2020-01-01T00:00:00+00:00",
    )


class _ListSource:
    def __init__(self, items, calls: list | None = None) -> None:
        self.items = items
        self.calls = [] if calls is None else calls

    def candidates(self, wb, *, index: int, round: int):
        self.calls.append((index, round))
        produced = self.items(index, round) if callable(self.items) else self.items
        return list(produced)


def _view(choice) -> dict:
    scored = choice.scored
    cand = scored.candidate
    return {
        "index": choice.index,
        "slot": choice.slot,
        "key": cand.key(),
        "lane": cand.lane,
        "op": cand.op,
        "value": scored.value,
        "pool": dict(choice.pool),
        "scored": [item.candidate.key() for item in choice.scored_pool],
    }


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _manifest(out: Path, run_id: str) -> dict:
    ledger = Ledger(out / "ledger.sqlite")
    try:
        return ledger.run_manifest(run_id)
    finally:
        ledger.close()


class _Roles:
    def __init__(self, source: _ListSource, *, fail_after: bool = False) -> None:
        self.sources = (source,)
        self.fail_after = fail_after
        self.events: list[tuple] = []

    def observe(self, phi, label, record_id) -> None:
        self.events.append(("observe", record_id))

    def after(self, wb, record, outcome) -> None:
        self.events.append(("after", record.record_id))
        if self.fail_after:
            raise RuntimeError("role after failed")

    def step(self) -> dict:
        self.events.append(("step",))
        return {"n": sum(1 for name, *_rest in self.events if name == "step")}

    def manifest(self) -> dict:
        return {"marker": "roles"}

    def report(self) -> dict:
        self.events.append(("report",))
        return {"marker": "report"}

    def close(self) -> None:
        self.events.append(("close",))


def _install(monkeypatch, roles: _Roles, seen: dict) -> None:
    def build(config, *, run_dir, extract, registry, engines, seed):
        seen["config"] = config
        seen["run_dir"] = run_dir
        seen["extract"] = extract
        seen["registry"] = registry
        seen["engines"] = engines
        seen["seed"] = seed
        return roles

    monkeypatch.setattr(loop_mod, "_build_roles", build)
    orig_after = Diagnoser.after
    orig_periodic = Diagnoser.periodic

    def after(self, wb, record, outcome):
        roles.events.append(("diagnoser.after", record.record_id))
        return orig_after(self, wb, record, outcome)

    def periodic(self, wb, done):
        roles.events.append(("diagnoser.periodic", done))
        return orig_periodic(self, wb, done)

    monkeypatch.setattr(Diagnoser, "after", after)
    monkeypatch.setattr(Diagnoser, "periodic", periodic)


def _short(out: Path, **kwargs):
    options = {
        "seed": 0,
        "engines": ("duckdb",),
        "oracles": ("plan_variant",),
        "max_experiments": 1,
    }
    options.update(kwargs)
    return run(out, **options)


# ---- Hunter -------------------------------------------------------------------------


def test_omitted_sources_match_an_empty_tuple(tmp_path) -> None:
    corpus = _tiny(tmp_path / "corpus.json")
    plain = Hunter(engines=("duckdb",), oracles=("plan_variant",), seed=11, corpus_path=corpus)
    empty = Hunter(
        engines=("duckdb",), oracles=("plan_variant",), seed=11, corpus_path=corpus, sources=()
    )
    wb_plain = Workbench.create(tmp_path / "plain")
    wb_empty = Workbench.create(tmp_path / "empty")
    try:
        assert plain.sources == () and empty.sources == ()
        left_keys = [item.key() for item in plain.candidates(wb_plain)]
        right_keys = [item.key() for item in empty.candidates(wb_empty)]
        assert left_keys == right_keys and left_keys
        left = []
        right = []
        for _ in range(3):
            chosen_l = plain.choose(wb_plain)
            chosen_r = empty.choose(wb_empty)
            assert chosen_l is not None and chosen_r is not None
            left.append(_view(chosen_l))
            right.append(_view(chosen_r))
        assert left == right
        assert plain.rng.getstate() == empty.rng.getstate()
        assert plain.mutator.rng.getstate() == empty.mutator.rng.getstate()
        assert plain.manifest() == empty.manifest()
        assert "sources" not in plain.manifest()
    finally:
        plain.close()
        empty.close()


def test_source_candidates_are_filtered_scored_and_selected(tmp_path) -> None:
    corpus = _corpus(tmp_path / "corpus.json", None)
    known = _case("SELECT a FROM t")
    fresh = _case("SELECT a FROM t WHERE a > 0")
    known_cand = _candidate(known, "implement")
    fresh_cand = _candidate(fresh, "implement")
    source = _ListSource([known_cand, fresh_cand])
    hunt = Hunter(
        engines=("duckdb",),
        oracles=("plan_variant",),
        seed=3,
        corpus_path=corpus,
        sources=(source,),
    )
    wb = Workbench.create(tmp_path / "theory")
    try:
        hunt.record(_recorded(known))
        choice = hunt.choose(wb)
        assert choice is not None
        assert choice.index == 1 and choice.slot == "any"
        assert choice.scored.candidate is fresh_cand
        assert choice.scored in choice.scored_pool
        assert choice.scored_pool == (choice.scored,)
        assert choice.pool["implement"] == 2
        assert choice.pool["rejected_known"] == 1
        assert choice.pool["scored"] == 1 and choice.pool["rounds"] == 1
        for key in _POOL_BASE:
            assert key in choice.pool
        assert source.calls == [(1, 1)]
        assert choice.scored.candidate.op == "implementer"
        assert choice.scored.candidate.target == {"required": ["ast:stmt:select"]}
    finally:
        hunt.close()


def test_sources_are_appended_in_order_and_round_is_forwarded(tmp_path) -> None:
    corpus = _corpus(tmp_path / "corpus.json", None)
    first = _candidate(_case("SELECT a FROM t"), "implement")
    second = _candidate(_case("SELECT b FROM u", ("CREATE TABLE u(b INT)",)), "bet")
    left = _ListSource([first])
    right = _ListSource([second])
    hunt = Hunter(
        engines=("duckdb",),
        oracles=("plan_variant",),
        seed=1,
        corpus_path=corpus,
        sources=(left, right),
    )
    wb = Workbench.create(tmp_path / "theory")
    try:
        found = hunt.candidates(wb)
        assert found == [first, second]
        assert left.calls == [(0, 1)] and right.calls == [(0, 1)]
        again = hunt.candidates(wb, round=4)
        assert again == [first, second]
        assert left.calls == [(0, 1), (0, 4)] and right.calls == [(0, 1), (0, 4)]
    finally:
        hunt.close()


def test_choose_passes_the_same_index_and_rising_rounds(tmp_path) -> None:
    corpus = _corpus(tmp_path / "corpus.json", None)
    bad = _case("SELECT a FROM t")
    source = _ListSource([_candidate(bad, "bet")])
    hunt = Hunter(
        engines=("duckdb",),
        oracles=("plan_variant",),
        seed=5,
        corpus_path=corpus,
        sources=(source,),
    )
    wb = Workbench.create(tmp_path / "theory")
    try:
        hunt.record(_recorded(bad, y="invalid", reason="setup_error"))
        assert hunt.choose(wb) is None
        assert source.calls == [(1, round_) for round_ in range(1, hunter_constants.EMPTY_ROUNDS + 1)]
        assert hunt._index == 1
    finally:
        hunt.close()


def test_explore_slot_still_picks_an_explore_candidate(tmp_path) -> None:
    corpus = _tiny(tmp_path / "corpus.json")
    offered = _candidate(_case("SELECT a FROM t WHERE a < 0"), "bet")
    source = _ListSource([offered])
    hunt = Hunter(
        engines=("duckdb",),
        oracles=("plan_variant",),
        seed=11,
        corpus_path=corpus,
        sources=(source,),
    )
    wb = Workbench.create(tmp_path / "theory")
    try:
        fifth = None
        for _ in range(5):
            fifth = hunt.choose(wb)
            assert fifth is not None
        assert fifth.index == 5 and fifth.slot == "explore"
        assert fifth.scored.candidate.lane == "explore"
        assert fifth.pool["bet"] >= 1 and fifth.pool["explore"] >= 1
        assert offered in [item.candidate for item in fifth.scored_pool]
        assert fifth.scored.candidate is not offered
    finally:
        hunt.close()


# ---- loop ---------------------------------------------------------------------------


def test_importing_the_loop_does_not_load_roles() -> None:
    hunter = (FRAMEWORK / "surprise" / "hunter" / "hunter.py").read_text(encoding="utf-8")
    assert "surprise.roles" not in hunter
    tree = ast.parse((FRAMEWORK / "surprise" / "experiments" / "loop.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or not node.module.startswith("surprise.roles")
        elif isinstance(node, ast.Import):
            assert all(not alias.name.startswith("surprise.roles") for alias in node.names)
    assert "from surprise.roles.runtime import build_roles" in inspect.getsource(loop_mod._build_roles)
    script = (
        "import json, sys\n"
        "import surprise.hunter, surprise.experiments.loop\n"
        "names = sorted(m for m in sys.modules if m == 'surprise.roles' or m.startswith('surprise.roles.'))\n"
        "print(json.dumps(names))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=FRAMEWORK,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-400:]
    assert json.loads(proc.stdout.strip().splitlines()[-1]) == []


def test_roles_off_matches_s8_files(tmp_path, monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("roles were built")

    monkeypatch.setattr(loop_mod, "_build_roles", boom)
    out = tmp_path / "off"
    report = _short(out, seed=1, run_id="off")
    assert "surprise.roles.runtime" not in sys.modules
    assert list(report) == list(_REPORT_ORDER)
    assert "llm" not in report
    config = json.loads((out / "config.json").read_text(encoding="utf-8"))
    assert list(config) == list(_CONFIG_ORDER)
    assert "llm" not in config
    rows = _rows(out / "progress.jsonl")
    assert len(rows) == 1
    assert list(rows[0]) == list(_PROGRESS_KEYS)
    manifest = _manifest(out, "off")
    assert "llm" not in manifest and "hunter" in manifest


def test_roles_on_records_calls_and_sections(tmp_path, monkeypatch) -> None:
    source = _ListSource([])
    roles = _Roles(source)
    seen: dict = {}
    token = object()
    _install(monkeypatch, roles, seen)
    cache = str(tmp_path / "cache")
    out = tmp_path / "on"
    report = _short(
        out,
        max_experiments=2,
        run_id="on",
        llm={"roles": ("implementer",), "cache": cache, "transport": token},
    )
    assert report["status"] == "budget_experiments"
    assert report["experiments"] == 2
    assert seen["run_dir"] == out
    assert seen["engines"] == ("duckdb",)
    assert seen["seed"] == 0
    assert isinstance(seen["registry"], Registry)
    assert callable(seen["extract"])
    assert seen["config"]["transport"] is token
    assert seen["config"]["roles"] == ["implementer"]
    assert seen["config"]["cache"] == cache
    assert seen["config"]["max_calls"] is None
    assert seen["config"]["network"] is True
    config = json.loads((out / "config.json").read_text(encoding="utf-8"))
    assert config["llm"] == {"roles": ["implementer"], "cache": cache, "max_calls": None, "network": True}
    assert "transport" not in config["llm"]
    assert list(report) == [*_REPORT_ORDER, "llm"]
    assert report["llm"] == {"marker": "report"}
    manifest = _manifest(out, "on")
    assert manifest["llm"] == {"marker": "roles"}
    rows = _rows(out / "progress.jsonl")
    assert len(rows) == 2
    assert [row["llm"] for row in rows] == [{"n": 1}, {"n": 2}]
    assert all(list(row) == [*_PROGRESS_KEYS, "llm"] for row in rows)
    names = [name for name, *_rest in roles.events]
    assert names[-2:] == ["report", "close"]
    cycle = ["diagnoser.after", "diagnoser.periodic", "observe", "after", "step"]
    assert names[:-2] == cycle * 2
    indexes = [index for index, _round in source.calls]
    assert indexes[0] == 1 and indexes[-1] == 2
    assert indexes == sorted(indexes)
    previous = 0
    run_rounds: list[int] = []
    for index, round_ in source.calls:
        if index != previous:
            assert round_ == 1
            run_rounds = [1]
            previous = index
        else:
            run_rounds.append(round_)
            assert run_rounds == list(range(1, len(run_rounds) + 1))


def test_a_failing_role_still_closes_and_reports(tmp_path, monkeypatch) -> None:
    source = _ListSource([])
    roles = _Roles(source, fail_after=True)
    seen: dict = {}
    _install(monkeypatch, roles, seen)
    cache = str(tmp_path / "cache")
    out = tmp_path / "err"
    llm = {
        "roles": ["conjecturer", "implementer"],
        "cache": cache,
        "max_calls": 0,
        "network": False,
        "transport": object(),
    }
    with pytest.raises(RuntimeError, match="role after failed"):
        _short(out, run_id="err", llm=llm)
    assert [name for name, *_rest in roles.events] == [
        "diagnoser.after",
        "diagnoser.periodic",
        "observe",
        "after",
        "report",
        "close",
    ]
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "error"
    assert report["error"]["type"] == "RuntimeError"
    assert "role after failed" in report["error"]["message"]
    assert report["llm"] == {"marker": "report"}
    config = json.loads((out / "config.json").read_text(encoding="utf-8"))
    assert config["llm"] == {
        "roles": ["conjecturer", "implementer"],
        "cache": cache,
        "max_calls": 0,
        "network": False,
    }
    assert _manifest(out, "err")["llm"] == {"marker": "roles"}


_BAD_LLM = [
    "implementer",
    {},
    {"roles": ["implementer"]},
    {"cache": "cache"},
    {"roles": [], "cache": "cache"},
    {"roles": (), "cache": "cache"},
    {"roles": ["nope"], "cache": "cache"},
    {"roles": ["Implementer"], "cache": "cache"},
    {"roles": ["implementer", "implementer"], "cache": "cache"},
    {"roles": ["conjecturer", "implementer", "conjecturer"], "cache": "cache"},
    {"roles": "implementer", "cache": "cache"},
    {"roles": [1], "cache": "cache"},
    {"roles": {"implementer"}, "cache": "cache"},
    {"roles": ["implementer"], "cache": ""},
    {"roles": ["implementer"], "cache": Path("cache")},
    {"roles": ["implementer"], "cache": "cache", "max_calls": -1},
    {"roles": ["implementer"], "cache": "cache", "max_calls": True},
    {"roles": ["implementer"], "cache": "cache", "max_calls": 1.5},
    {"roles": ["implementer"], "cache": "cache", "network": 1},
    {"roles": ["implementer"], "cache": "cache", "network": "yes"},
    {"roles": ["implementer"], "cache": "cache", "extra": 1},
]


@pytest.mark.parametrize("llm", _BAD_LLM)
def test_a_bad_llm_dict_is_rejected_before_the_run(tmp_path, llm) -> None:
    out = tmp_path / "out"
    with pytest.raises(UsageError):
        run(out, seed=1, max_experiments=1, llm=llm)
    assert not out.exists()


def test_cli_rejects_llm_flags_with_exit_2(tmp_path, monkeypatch) -> None:
    out = tmp_path / "out"
    cache = str(tmp_path / "cache")
    base = ["--out", str(out), "--seed", "1", "--max-experiments", "1"]

    def explode(*_args, **_kwargs):
        raise AssertionError("run should not start")

    monkeypatch.setattr(loop_mod, "run", explode)
    early = [
        base + ["--llm", "implementer"],
        base + ["--llm-cache", cache],
        base + ["--llm-max-calls", "3"],
        base + ["--llm-offline"],
        base + ["--llm-cache", cache, "--llm-max-calls", "1", "--llm-offline"],
        base + ["--llm", "wizard"],
        base + ["--llm", "implementer", "--llm-cache", cache, "--llm-max-calls", "nope"],
    ]
    for argv in early:
        assert main(argv) == 2, argv
    assert not out.exists()


def test_cli_rejects_bad_llm_values_with_exit_2(tmp_path) -> None:
    out = tmp_path / "out"
    cache = str(tmp_path / "cache")
    base = ["--out", str(out), "--seed", "1", "--max-experiments", "1", "--llm-cache", cache]
    assert main(base + ["--llm", "implementer", "--llm", "implementer"]) == 2
    assert main(base + ["--llm", "implementer", "--llm-max-calls", "-1"]) == 2
    assert main(base + ["--llm", "conjecturer", "--llm-max-calls", "0", "--llm", "conjecturer"]) == 2
    assert not out.exists()


def test_cli_assembles_the_llm_dict(tmp_path, monkeypatch, capsys) -> None:
    seen: dict = {}

    def fake_run(out, **kwargs):
        seen["kwargs"] = kwargs
        return {"status": "budget_experiments", "experiments": 2}

    monkeypatch.setattr(loop_mod, "run", fake_run)
    cache = str(tmp_path / "cache")
    out = str(tmp_path / "out")
    code = main(
        [
            "--out",
            out,
            "--seed",
            "4",
            "--max-experiments",
            "2",
            "--llm",
            "conjecturer",
            "--llm",
            "implementer",
            "--llm-cache",
            cache,
            "--llm-max-calls",
            "7",
            "--llm-offline",
        ]
    )
    assert code == 0
    assert seen["kwargs"]["echo"] is True
    assert seen["kwargs"]["llm"] == {
        "roles": ["conjecturer", "implementer"],
        "cache": cache,
        "max_calls": 7,
        "network": False,
    }
    assert "budget_experiments 2" in capsys.readouterr().out
    code = main(
        ["--out", out, "--seed", "4", "--max-experiments", "1", "--llm", "implementer", "--llm-cache", cache]
    )
    assert code == 0
    assert seen["kwargs"]["llm"] == {
        "roles": ["implementer"],
        "cache": cache,
        "max_calls": None,
        "network": True,
    }
