"""S10 role frame: plugin protocol, Hunter hooks, and the run vocabulary.

Scripted plugins and local engines only. No network and no API key.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from surprise.experiments.loop import UsageError, _LLM_ROLES, _REWRITE_LIBRARY_ENV
from surprise.experiments import loop as loop_mod
from surprise.features.phi import make_phi
from surprise.features.registry import Registry, default_registry
from surprise.features.vocabulary import FeatureDef
from surprise.gates.s04 import load as load_case
from surprise.gates.s10_cases import CONSTANTS, PLUGINS, ROLES, VOCAB_GOOD, VOCAB_PARENT
from surprise.harness.contracts import IdentityEvidence, Label, SqlCase
from surprise.harness.ledger import Ledger
from surprise.hunter import Hunter, PhiExtractor
from surprise.hunter import scoring as scoring
from surprise.hunter.operators import RULES, oracle_options
from surprise.roles import base
from surprise.roles.constants import REWRITE_LIBRARY_ENV, as_dict
from surprise.roles.runtime import ROLES as RUNTIME_ROLES
from surprise.roles.runtime import build_roles
from surprise.theory.constants import RESIDUAL_PRIOR_FAILS, RESIDUAL_PRIOR_TESTS
from surprise.theory.workbench import Workbench

LAYERS = {"ast": "ok", "plan": "ok", "data": "ok"}
LIBRARY_ENV = "SURPRISE_REWRITE_LIBRARY"


class Prior:
    def __init__(self, pseudo: tuple[float, float] | None) -> None:
        self.pseudo_counts = pseudo
        self.prepared: list[tuple[int, tuple[str, ...]]] = []

    def prepare(self, wb: Any, units: Any, *, index: int) -> None:
        self.prepared.append((index, tuple(units)))

    def pseudo(self, unit: str) -> tuple[float, float] | None:
        return self.pseudo_counts


class _Source:
    def __init__(self, name: str) -> None:
        self.name = name

    def candidates(self, wb: Any, *, index: int, round: int) -> list:
        return []


class Plugin(base.Role):
    def __init__(self, name: str, ctx: base.RoleContext, log: list[str], *, boom: bool = False) -> None:
        self.name = name
        self.ctx = ctx
        self.log = log
        self.boom = boom
        self.events: list[Any] = []
        self._source = _Source(name)

    def sources(self) -> tuple:
        return (self._source,)

    def observe(self, event: base.Observed) -> None:
        self.log.append(f"observe:{self.name}")
        self.events.append(event)

    def after(self, wb: Any, record: Any, outcome: Any) -> None:
        self.log.append(f"after:{self.name}")

    def step(self) -> dict:
        return {"name": self.name}

    def report(self) -> dict:
        return {"name": self.name}

    def manifest(self) -> dict:
        return {"name": self.name}

    def close(self) -> None:
        self.log.append(f"close:{self.name}")
        if self.boom:
            raise RuntimeError(f"{self.name} close failed")

    def rules(self) -> tuple[str, ...]:
        return ("llm:wrap_sub", "double_negation", "llm:other")


def _install(monkeypatch: pytest.MonkeyPatch, name: str, log: list[str], *, boom: bool = False) -> dict[str, Plugin]:
    module_name = f"surprise.roles._s10_fake_{name}"
    module = types.ModuleType(module_name)
    holder: dict[str, Plugin] = {}

    def build(ctx: base.RoleContext) -> Plugin:
        role = Plugin(name, ctx, log, boom=boom)
        holder["role"] = role
        return role

    module.build = build
    monkeypatch.setitem(sys.modules, module_name, module)
    monkeypatch.setitem(base.PLUGINS, name, module_name)
    return holder


def _config(tmp: Path, which: tuple[str, ...], script: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "roles": list(which),
        "cache": str(tmp / "cache"),
        "max_calls": 4,
        "network": False,
    }
    if script is not None:
        payload["transport"] = script
    return payload


def _roles(tmp: Path, which: tuple[str, ...], *, oracles: tuple[str, ...] = ()) -> Any:
    return build_roles(
        _config(tmp, which),
        run_dir=tmp / "run",
        extract=lambda case: None,
        registry=None,
        engines=("duckdb",),
        seed=4,
        oracles=oracles,
    )


def _corpus(path: Path) -> Path:
    path.write_text(
        json.dumps(
            [
                {
                    "setup_sqls": ["CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1), (2)"],
                    "query": "SELECT a FROM t WHERE a > 0",
                    "source": "s10-frame",
                    "engine": "duckdb",
                    "tags": [],
                }
            ]
        ),
        encoding="utf-8",
    )
    return path


class _FixedPhi:
    def extract(self, case: SqlCase):
        return make_phi(case.engine, ("ast:stmt:select",), LAYERS)

    def close(self) -> None:
        return None


def _view(choice) -> dict[str, Any]:
    scored = choice.scored
    return {
        "index": choice.index,
        "slot": choice.slot,
        "key": scored.candidate.key(),
        "lane": scored.candidate.lane,
        "value": scored.value,
        "u": scored.U,
        "pool": dict(choice.pool),
        "scored": [item.candidate.key() for item in choice.scored_pool],
    }


def _fail_label(oracle: str = "plan_variant") -> Label:
    return Label(
        y="fail",
        oracle=oracle,
        fail_kind="wrong_result",
        identity=IdentityEvidence(error_class=None, behavior={"missing": 1}),
        cve={"profile": {"status": "ran", "fix_kind": "none", "fix_set": [], "plan_diff": [],
                         "version_ladder": "none", "witness_switches": []}},
    )


def _vocabulary(path: Path) -> Registry:
    registry = default_registry()
    registry.register(
        FeatureDef(
            feature_id=VOCAB_GOOD["id"],
            kind="leaf",
            parent=VOCAB_PARENT,
            layer="ast",
            description="the two sides of EXCEPT ALL read different tables",
            source="llm:gate",
            definition={"kind": "regex", "pattern": VOCAB_GOOD["pattern"]},
            accepted=False,
            acceptance=None,
        )
    )
    registry.accept(VOCAB_GOOD["id"], {"gate": True})
    registry.save(path)
    return registry


# ---- protocol and constants -----------------------------------------------------------------


def test_protocol_defaults_and_plugin_table() -> None:
    assert base.PLUGINS == PLUGINS
    assert RUNTIME_ROLES == ROLES == _LLM_ROLES
    assert REWRITE_LIBRARY_ENV == LIBRARY_ENV == _REWRITE_LIBRARY_ENV
    have = as_dict()
    for name, value in CONSTANTS.items():
        assert name in have and have[name] == value and type(have[name]) is type(value)
    role = base.Role()
    assert role.name == ""
    assert role.sources() == ()
    assert role.step() == {} and role.report() == {} and role.manifest() == {}
    assert role.observe(None) is None  # type: ignore[arg-type]
    assert role.after(None, None, None) is None
    assert role.close() is None
    fields = {item.name for item in base.RoleContext.__dataclass_fields__.values()}
    assert fields == {
        "gateway", "book", "extract", "registry", "readers", "engines", "oracles", "seed", "run_dir", "llm_dir"
    }
    observed = {item.name for item in base.Observed.__dataclass_fields__.values()}
    assert observed == {
        "wb", "phi", "record", "outcome", "prediction", "lane", "op", "hypothesis", "target", "index"
    }
    frozen = base.RoleContext(  # type: ignore[call-arg]
        gateway=object(), book=object(), extract=lambda case: None, registry=object(),
        readers={}, engines=(), oracles=(), seed=0, run_dir=Path("."), llm_dir=Path("."),
    )
    with pytest.raises(AttributeError):
        frozen.seed = 1  # type: ignore[misc]


def test_build_roles_knows_six_names_and_loads_only_the_ones_on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib.util

    with pytest.raises(ValueError, match="unknown role"):
        _roles(tmp_path / "bad", ("diagnoser",))
    with pytest.raises(ValueError, match="non-empty"):
        _roles(tmp_path / "empty", ())
    for name in ("prior", "translator", "vocab_inventor", "oracle_inventor"):
        missing = f"surprise.roles._s10_missing_{name}"
        assert missing not in sys.modules
        assert importlib.util.find_spec(missing) is None
        with monkeypatch.context() as patch:
            patch.setitem(base.PLUGINS, name, missing)
            with pytest.raises(ValueError, match="not available") as caught:
                _roles(tmp_path / name, (name,))
            assert "unknown role" not in str(caught.value)
            assert missing not in sys.modules

    log: list[str] = []
    prior = _install(monkeypatch, "prior", log)
    translator = _install(monkeypatch, "translator", log)
    for module_name in (
        "surprise.roles.vocab_inventor",
        "surprise.roles.oracle_inventor",
        "surprise.roles._s10_fake_vocab_inventor",
        "surprise.roles._s10_missing_prior",
        "surprise.roles._s10_missing_translator",
        "surprise.roles._s10_missing_vocab_inventor",
        "surprise.roles._s10_missing_oracle_inventor",
    ):
        monkeypatch.delitem(sys.modules, module_name, raising=False)
    made = _roles(tmp_path / "on", ("translator", "prior", "prior"), oracles=("plan_variant", "tlp"))
    try:
        assert list(made.plugins) == ["prior", "translator"]
        assert made.prior is prior["role"]
        assert made.rewrite_rules() == ()
        assert made.rewrite_library is None
        assert [item.name for item in made.sources] == ["prior", "translator"]
        assert prior["role"].ctx is not None
        assert prior["role"].ctx.gateway is translator["role"].ctx.gateway
        assert prior["role"].ctx.book is translator["role"].ctx.book
        assert prior["role"].ctx.oracles == ("plan_variant", "tlp")
        assert isinstance(prior["role"].ctx.registry, Registry)
        assert prior["role"].ctx.llm_dir == tmp_path / "on" / "run" / "llm"
        assert prior["role"].ctx.engines == ("duckdb",)
        assert "surprise.roles.vocab_inventor" not in sys.modules
        assert "surprise.roles.oracle_inventor" not in sys.modules
        assert f"surprise.roles._s10_fake_vocab_inventor" not in sys.modules
    finally:
        made.close()


def test_s9_roles_keep_the_old_step_report_and_manifest(tmp_path: Path) -> None:
    made = _roles(tmp_path, ("implementer", "conjecturer"))
    try:
        assert made.plugins == {}
        assert made.prior is None
        assert made.rewrite_rules() == ()
        assert made.rewrite_library is None
        assert len(made.sources) == 1
        assert list(made.step()) == ["calls", "conjecture", "settled", "attempts"]
        assert made.step() == {"calls": {}, "conjecture": None, "settled": [], "attempts": []}
        report = made.report()
        assert list(report) == ["roles", "calls", "book", "implementer"]
        manifest = made.manifest()
        assert "plugins" not in manifest
        assert manifest["roles"] == ["implementer", "conjecturer"]
        assert manifest["constants"]["PRIOR_TIER"] == "fast"
    finally:
        made.close()


def test_plugins_join_in_role_order_and_add_their_sections(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log: list[str] = []
    prior = _install(monkeypatch, "prior", log)
    oracle = _install(monkeypatch, "oracle_inventor", log, boom=True)
    _install(monkeypatch, "translator", log)
    made = _roles(tmp_path, ("implementer", "oracle_inventor", "prior"), oracles=("cross_dbms",))
    try:
        assert list(made.plugins) == ["prior", "oracle_inventor"]
        assert made.prior is prior["role"]
        assert made.rewrite_rules() == ("llm:wrap_sub", "double_negation", "llm:other")
        assert made.rewrite_library == tmp_path / "run" / "llm" / "rewrites.json"
        assert [getattr(item, "name", "implementer") for item in made.sources] == [
            "implementer", "prior", "oracle_inventor"
        ]
        phi = make_phi("duckdb", ("ast:stmt:select",), LAYERS)
        label = Label(y="pass", oracle="plan_variant")
        event = base.Observed(
            wb=None, phi=phi, record="rec", outcome=None, prediction=None, lane="explore", op="seed",
            hypothesis=None, target=None, index=3,
        )
        assert made.observe(phi, label, "rec-1", event=event) == ()
        assert made.observe(phi, label, "rec-2") == ()
        assert log == ["observe:prior", "observe:oracle_inventor"]
        assert prior["role"].events == [event]
        assert oracle["role"].events == [event]
        assert made.after(None, None, None) is None
        assert log[-2:] == ["after:prior", "after:oracle_inventor"]
        step = made.step()
        assert list(step) == ["calls", "conjecture", "settled", "attempts", "prior", "oracle_inventor"]
        assert step["prior"] == {"name": "prior"}
        assert json.dumps(step)
        report = made.report()
        assert report["prior"]["name"] == "prior" and report["oracle_inventor"]["name"] == "oracle_inventor"
        manifest = made.manifest()
        assert list(manifest["plugins"]) == ["prior", "oracle_inventor"]
        assert manifest["plugins"]["prior"] == {"name": "prior"}
    finally:
        with pytest.raises(RuntimeError, match="prior close failed"):
            # oracle is asked to close too; its failure is second, so prior's is raised
            prior["role"].boom = True
            made.close()
        assert "close:prior" in log and "close:oracle_inventor" in log


def test_close_runs_every_plugin_and_raises_the_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log: list[str] = []
    _install(monkeypatch, "prior", log, boom=True)
    _install(monkeypatch, "translator", log)
    made = _roles(tmp_path, ("prior", "translator"))
    with pytest.raises(RuntimeError, match="prior close failed"):
        made.close()
    assert log == ["close:prior", "close:translator"]


# ---- scoring and the Hunter --------------------------------------------------------------------


def test_scoring_keeps_the_default_prior_and_accepts_another() -> None:
    assert scoring.optimistic_rate(0, 0) == scoring.optimistic_rate(
        0, 0, prior_fails=RESIDUAL_PRIOR_FAILS, prior_tests=RESIDUAL_PRIOR_TESTS
    )
    assert scoring.optimistic_rate(4, 1) == scoring.optimistic_rate(4, 1, RESIDUAL_PRIOR_FAILS, RESIDUAL_PRIOR_TESTS)
    assert scoring.uncertainty(2, 1, True) == scoring.uncertainty(
        2, 1, True, prior_fails=RESIDUAL_PRIOR_FAILS, prior_tests=RESIDUAL_PRIOR_TESTS
    )
    rho = (0 + 30.0) / (0 + 100.0)
    capped = min(0.5, rho + math.sqrt(rho * (1.0 - rho) / 1))
    assert scoring.optimistic_rate(0, 0, prior_fails=30.0, prior_tests=100.0) == pytest.approx(capped)
    assert scoring.uncertainty(0, 0, False, prior_fails=30.0, prior_tests=100.0) == pytest.approx(1.0)


def test_prior_moves_only_unexplored_uncertainty(tmp_path: Path) -> None:
    phi = make_phi("duckdb", ("ast:stmt:select", "ast:clause:where"), LAYERS)
    fresh = Workbench.create(tmp_path / "fresh")
    plain = scoring.score(fresh, phi, "plan_variant", beta=1.0, probes={}, units=frozenset())
    primed = scoring.score(
        fresh, phi, "plan_variant", beta=1.0, probes={}, units=frozenset(), prior=Prior((30.0, 100.0))
    )
    none = scoring.score(fresh, phi, "plan_variant", beta=1.0, probes={}, units=frozenset(), prior=Prior(None))
    assert plain.prediction.zone == "unexplored"
    assert primed.U == pytest.approx(1.0) and primed.U > plain.U
    assert none.U == pytest.approx(plain.U) and none.value == pytest.approx(plain.value)
    assert primed.D == plain.D
    opened = Workbench.create(tmp_path / "opened")
    opened.observe(phi, _fail_label(), "rec-1")
    inside = scoring.score(opened, phi, "plan_variant", beta=1.0, probes={}, units=frozenset())
    inside_prior = scoring.score(
        opened, phi, "plan_variant", beta=1.0, probes={}, units=frozenset(), prior=Prior((30.0, 100.0))
    )
    assert inside.prediction.zone != "unexplored"
    assert inside.U == 0.0 and inside_prior.U == 0.0
    assert inside.value == pytest.approx(inside_prior.value)


def test_no_prior_matches_an_omitted_prior_and_a_prior_is_asked_once_per_round(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path / "corpus.json")
    plain = Hunter(
        engines=("duckdb",), oracles=("plan_variant",), seed=3, corpus_path=corpus, extractor=_FixedPhi()
    )
    same = Hunter(
        engines=("duckdb",), oracles=("plan_variant",), seed=3, corpus_path=corpus, extractor=_FixedPhi(),
        prior=None, extra_rules=None, registry=None,
    )
    asked = Prior((30.0, 100.0))
    primed = Hunter(
        engines=("duckdb",), oracles=("plan_variant",), seed=3, corpus_path=corpus, extractor=_FixedPhi(),
        prior=asked,
    )
    left = Workbench.create(tmp_path / "left")
    right = Workbench.create(tmp_path / "right")
    primed_wb = Workbench.create(tmp_path / "primed")
    try:
        assert [_view(plain.choose(left)) for _ in range(3)] == [_view(same.choose(right)) for _ in range(3)]
        assert plain.rng.getstate() == same.rng.getstate()
        choice = primed.choose(primed_wb)
        assert choice is not None
        assert asked.prepared
        assert all(index == choice.index for index, _units in asked.prepared)
        assert 1 <= len(asked.prepared) <= choice.pool["rounds"]
        assert all(units and all(isinstance(unit, str) and unit.count("|") == 4 for unit in units)
                   for _index, units in asked.prepared)
        assert choice.scored.prediction.zone != "unexplored" or choice.scored.U == pytest.approx(1.0)
    finally:
        plain.close()
        same.close()
        primed.close()


def test_extra_rules_follow_the_frozen_rules_on_explore_candidates(tmp_path: Path) -> None:
    case = SqlCase(engine="duckdb", setup=(), query="SELECT 1", predicate=None)
    base_opts = oracle_options(case, ["equivalent_query", "cross_dbms"])
    more = oracle_options(
        case, ["equivalent_query", "cross_dbms"], extra_rules=("llm:wrap_sub", "double_negation", "llm:other")
    )
    assert base_opts == [("equivalent_query", rule) for rule in RULES] + [("cross_dbms", None)]
    assert more == [("equivalent_query", rule) for rule in RULES] + [
        ("equivalent_query", "llm:wrap_sub"),
        ("equivalent_query", "llm:other"),
        ("cross_dbms", None),
    ]
    corpus = _corpus(tmp_path / "corpus.json")
    hunt = Hunter(
        engines=("duckdb",),
        oracles=("equivalent_query",),
        seed=1,
        corpus_path=corpus,
        extractor=_FixedPhi(),
        extra_rules=lambda: ("llm:wrap_sub",),
    )
    wb = Workbench.create(tmp_path / "theory")
    try:
        found = [item.rule for item in hunt.candidates(wb) if item.op == "seed" and item.oracle == "equivalent_query"]
    finally:
        hunt.close()
    assert found[: len(RULES)] == list(RULES)
    assert found[len(RULES) :] == ["llm:wrap_sub"]


def test_registry_reaches_the_worker_and_the_candidate_phi(tmp_path: Path) -> None:
    plain = PhiExtractor()
    try:
        assert plain._command == [sys.executable, "-m", "surprise.hunter.phi_worker"]
    finally:
        plain.close()
    vocab = tmp_path / "vocabulary.json"
    registry = _vocabulary(vocab)
    case = SqlCase(
        engine="duckdb",
        setup=("CREATE TABLE t(v INT)", "INSERT INTO t VALUES (1), (1)", "CREATE TABLE u(v INT)", "INSERT INTO u VALUES (1)"),
        query="SELECT v FROM t EXCEPT ALL SELECT v FROM u",
        predicate=None,
    )
    corpus = tmp_path / "corpus.json"
    corpus.write_text(
        json.dumps(
            [{
                "setup_sqls": list(case.setup),
                "query": case.query,
                "source": "s10-frame-vocab",
                "engine": "duckdb",
                "tags": [],
            }]
        ),
        encoding="utf-8",
    )
    extractor = PhiExtractor(registry_path=str(vocab))
    assert extractor._command[-2:] == ["--registry", str(vocab)]
    hunt = Hunter(
        engines=("duckdb",), oracles=("cross_dbms",), seed=0, corpus_path=corpus, extractor=extractor, registry=registry
    )
    wb = Workbench.create(tmp_path / "theory")
    bare = PhiExtractor()
    try:
        seeds = [item for item in hunt.candidates(wb) if item.op == "seed"]
        assert seeds
        found = hunt.phi(seeds[0].case)
        assert VOCAB_GOOD["id"] in found.features
        assert VOCAB_GOOD["id"] not in bare.extract(seeds[0].case).features
        assert hunt._registry is registry
    finally:
        hunt.close()
        extractor.close()
        bare.close()


# ---- the loop ----------------------------------------------------------------------------------


def _duck_boot() -> list[dict[str, Any]]:
    return [{
        "case": {
            "engine": "duckdb",
            "setup": ["CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1)"],
            "query": "SELECT a FROM t",
            "predicate": None,
        },
        "oracle": "plan_variant",
        "rule": None,
    }]


class _LoopRoles:
    def __init__(self, library: Path | None, *, fail: bool = False) -> None:
        self.rewrite_library = library
        self.sources: tuple = ()
        self.events: list[Any] = []
        self.during: list[str | None] = []
        self.fail = fail
        self.closed = False

    def observe(self, phi: Any, label: Any, record_id: str, *, event: Any = None) -> None:
        self.events.append(event)
        self.during.append(os.environ.get(LIBRARY_ENV))

    def after(self, wb: Any, record: Any, outcome: Any) -> None:
        if self.fail:
            raise RuntimeError("role after failed")

    def step(self) -> dict:
        return {"n": len(self.events)}

    def report(self) -> dict:
        return {"marker": True}

    def manifest(self) -> dict:
        return {"marker": True}

    def close(self) -> None:
        self.closed = True


def test_vocabulary_run_records_the_invented_feature_and_a_plain_run_does_not(tmp_path: Path) -> None:
    vocab = tmp_path / "vocabulary.json"
    _vocabulary(vocab)
    case = load_case("DF-A")
    boot = [{"case": case.to_dict(), "oracle": "cross_dbms", "rule": None}]
    out = tmp_path / "vocab-run"
    loop_mod.run(
        out, seed=0, engines=("datafusion",), oracles=("cross_dbms",), max_experiments=0, bootstrap=boot,
        vocabulary=str(vocab),
    )
    config = json.loads((out / "config.json").read_text(encoding="utf-8"))
    assert config["vocabulary"] == str(vocab)
    ledger = Ledger(out / "ledger.sqlite")
    try:
        records = ledger.records(run_id="loop-s0")
        manifest = ledger.run_manifest("loop-s0")
    finally:
        ledger.close()
    assert len(records) == 1 and VOCAB_GOOD["id"] in records[0].phi["features"]
    assert manifest["vocabulary"] == {
        "path": str(vocab),
        "sha256": hashlib.sha256(vocab.read_bytes()).hexdigest(),
        "digest": Registry.load(vocab).digest(),
    }
    opened = Workbench.open(out / "theory", registry=Registry.load(vocab))
    assert len(opened.theory.hypotheses) == 1
    assert VOCAB_GOOD["id"] in opened.theory.hypotheses[0].specific

    plain = tmp_path / "plain-run"
    loop_mod.run(
        plain, seed=1, engines=("duckdb",), oracles=("plan_variant",), max_experiments=0, bootstrap=_duck_boot()
    )
    plain_config = json.loads((plain / "config.json").read_text(encoding="utf-8"))
    assert "vocabulary" not in plain_config
    plain_ledger = Ledger(plain / "ledger.sqlite")
    try:
        plain_manifest = plain_ledger.run_manifest("loop-s1")
    finally:
        plain_ledger.close()
    assert "vocabulary" not in plain_manifest


def test_rewrite_library_is_set_for_the_run_and_restored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    library = tmp_path / "rewrites.json"
    roles = _LoopRoles(library)
    seen: dict[str, Any] = {}

    def build(config, *, run_dir, extract, registry, engines, seed):
        seen["oracles"] = config["oracles"]
        return roles

    monkeypatch.setattr(loop_mod, "_build_roles", build)
    os.environ.pop(LIBRARY_ENV, None)
    out = tmp_path / "on"
    report = loop_mod.run(
        out, seed=0, engines=("duckdb",), oracles=("plan_variant",), max_experiments=0, bootstrap=_duck_boot(),
        llm={"roles": ["implementer"], "cache": str(tmp_path / "cache"), "network": False, "max_calls": 0},
    )
    assert report["status"] == "budget_experiments"
    assert seen["oracles"] == ("plan_variant",)
    assert roles.during == [str(library)]
    assert os.environ.get(LIBRARY_ENV) is None
    assert roles.closed
    event = roles.events[0]
    assert isinstance(event, base.Observed)
    assert event.lane == "bootstrap" and event.op == "bootstrap" and event.index == 0
    assert event.phi is not None and event.record is not None and event.outcome is not None
    assert event.prediction is not None and event.wb is not None

    previous = "already-set"
    os.environ[LIBRARY_ENV] = previous
    broken = _LoopRoles(library, fail=True)

    def build_broken(config, *, run_dir, extract, registry, engines, seed):
        return broken

    monkeypatch.setattr(loop_mod, "_build_roles", build_broken)
    try:
        with pytest.raises(RuntimeError, match="role after failed"):
            loop_mod.run(
                tmp_path / "err", seed=0, engines=("duckdb",), oracles=("plan_variant",), max_experiments=0,
                bootstrap=_duck_boot(),
                llm={"roles": ["conjecturer"], "cache": str(tmp_path / "cache2"), "network": False, "max_calls": 0},
            )
        assert broken.during == [str(library)]
        assert os.environ.get(LIBRARY_ENV) == previous
        assert broken.closed
    finally:
        os.environ.pop(LIBRARY_ENV, None)


def test_vocabulary_must_be_a_file_and_the_cli_forwards_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "missing"
    with pytest.raises(UsageError, match="vocabulary"):
        loop_mod.run(out, seed=1, max_experiments=0, vocabulary=str(tmp_path / "nope.json"))
    assert not out.exists()
    seen: dict[str, Any] = {}

    def fake_run(out_dir, **kwargs):
        seen.update(kwargs)
        return {"status": "budget_experiments", "experiments": 0}

    monkeypatch.setattr(loop_mod, "run", fake_run)
    vocab = tmp_path / "vocabulary.json"
    vocab.write_text("{}\n", encoding="utf-8")
    code = loop_mod.main(
        ["--out", str(out), "--seed", "1", "--max-experiments", "0", "--vocabulary", str(vocab)]
    )
    assert code == 0
    assert seen["vocabulary"] == str(vocab)
    assert seen["llm"] is None
