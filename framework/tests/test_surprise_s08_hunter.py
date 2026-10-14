"""Hunter candidates, choose, exploration slots, and hash-seed determinism."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from surprise.features.registry import default_registry
from surprise.gates import s08_cases as C
from surprise.harness.contracts import ExperimentRecord, IdentityEvidence, Label, SqlCase
from surprise.harness.oracles.rewrites import RULES
from surprise.hunter import LANES, Candidate, Choice, Hunter, PhiExtractor, Score, Scored, constants
from surprise.hunter.operators import case_digest, mutants
from surprise.theory import Spec, Workbench, position

FRAMEWORK = Path(__file__).resolve().parents[1]


def _tiny_corpus(path: Path) -> Path:
    seeds = [
        {
            "setup_sqls": ["CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1), (2)"],
            "query": "SELECT a FROM t WHERE a > 0",
            "source": "test:duckdb",
            "engine": "duckdb",
            "tags": [],
        },
        {
            "setup_sqls": ["CREATE TABLE u(b INT)", "INSERT INTO u VALUES (9)"],
            "query": "SELECT b FROM u",
            "source": "test:duckdb-b",
            "engine": "duckdb",
            "tags": [],
        },
        {
            "setup_sqls": ["CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1), (2)"],
            "query": "SELECT a FROM t WHERE a > 0",
            "source": "test:datafusion",
            "engine": "datafusion",
            "tags": [],
        },
    ]
    path.write_text(json.dumps(seeds), encoding="utf-8")
    return path


def _record(case: SqlCase, oracle: str, *, record_id: str, phi=None, y: str = "pass", reason=None) -> ExperimentRecord:
    if y == "pass":
        label = Label(y="pass", oracle=oracle)
    elif y == "fail":
        label = Label(y="fail", oracle=oracle, fail_kind="wrong_result")
    else:
        label = Label(y="invalid", oracle=oracle, invalid_reason=reason or "setup_error")
    return ExperimentRecord(
        record_id=record_id,
        run_id="s08-hunter",
        seq=int(record_id.lstrip("r") or 1) if record_id[1:].isdigit() else 1,
        case=case,
        label=label,
        purpose="test",
        created_at="2020-01-01T00:00:00+00:00",
        phi=None if phi is None else phi.to_dict() if hasattr(phi, "to_dict") else phi,
    )


def test_constants_values_types_and_json_roundtrip() -> None:
    have = constants.as_dict()
    for name, value in C.HUNTER_CONSTANTS.items():
        assert have[name] == value
        assert type(have[name]) is type(value)
    detached = constants.as_dict()
    detached["EXPLORE_EVERY"] = 0
    assert constants.as_dict() == have
    from surprise.theory import constants as TC

    assert isinstance(TC.BETA, float) and TC.BETA == 1.0
    assert TC.as_dict()["BETA"] == 1.0


def test_package_exports_and_import_does_not_start_a_worker() -> None:
    import surprise.hunter as H

    assert H.LANES == LANES == ("refine", "generalize", "migrate", "explore")
    assert H.Hunter is Hunter
    assert H.PhiExtractor is PhiExtractor
    assert H.Score is Score
    assert H.Scored is Scored
    assert H.Candidate is Candidate
    assert H.Choice is Choice
    extractor = PhiExtractor()
    try:
        assert extractor._proc is None
    finally:
        extractor.close()


def test_manifest_is_json_safe(tmp_path) -> None:
    corpus = _tiny_corpus(tmp_path / "corpus.json")
    hunt = Hunter(engines=("duckdb",), oracles=("plan_variant",), seed=3, corpus_path=corpus)
    try:
        blob = hunt.manifest()
        assert json.loads(json.dumps(blob)) == blob
        assert blob["seed"] == 3
        assert blob["engines"] == ["duckdb"]
        assert blob["oracles"] == ["plan_variant"]
        assert blob["constants"] == constants.as_dict()
        assert blob["beta"] == hunt.beta
    finally:
        hunt.close()


def test_choose_explore_slot_ties_and_filter_counts(tmp_path) -> None:
    corpus = _tiny_corpus(tmp_path / "corpus.json")
    wb = Workbench.create(tmp_path / "theory")
    hunt = Hunter(
        engines=("duckdb",),
        oracles=("equivalent_query",),
        seed=11,
        corpus_path=corpus,
    )
    try:
        slots = []
        last = None
        for _ in range(5):
            last = hunt.choose(wb)
            assert last is not None
            assert last.pool["rounds"] == 1
            slots.append(last.slot)
        assert slots == ["any", "any", "any", "any", "explore"]
        assert last.index == 5 and last.slot == "explore"
        assert last.scored.candidate.lane == "explore"
        assert set(last.pool) == {
            *LANES,
            "rejected_known",
            "rejected_bad_setup",
            "rejected_novelty",
            "scored",
            "rounds",
        }
        assert last.pool["rounds"] == 1
        assert last.pool["scored"] == len(last.scored_pool)
        assert last.scored in last.scored_pool
        values = [item.value for item in last.scored_pool]
        assert last.scored.value == pytest.approx(max(values))
        ties = [item for item in last.scored_pool if item.value >= max(values) - 1e-12]
        assert last.scored in ties

        seed_item = next(item for item in last.scored_pool if item.candidate.op == "seed")
        hunt.record(
            _record(seed_item.candidate.case, seed_item.candidate.oracle, record_id="r1", phi=seed_item.phi),
            rule=seed_item.candidate.rule,
            prediction=seed_item.prediction,
        )
        after = hunt.choose(wb)
        assert after is not None
        assert after.pool["rounds"] == 1
        assert after.pool["rejected_known"] >= 1

        hunt.record(
            _record(
                SqlCase(
                    engine="duckdb",
                    setup=("CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1), (2)"),
                    query="SELECT a FROM t WHERE a > 0",
                ),
                "equivalent_query",
                record_id="r2",
                y="invalid",
                reason="setup_error",
            )
        )
        # Explore no longer draws a seed whose setup has failed. The choice-time
        # filter still counts a mutant of a parent that uses that setup.
        parent = SqlCase(
            engine="duckdb",
            setup=("CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1), (2)"),
            query="SELECT a FROM t WHERE a > 0 AND a <> 2",
        )
        example = hunt.phi(parent)
        opened = wb.observe(example, _profiled("equivalent_query"), "r3")
        assert opened.observation.opened
        hunt.record(
            _record(parent, "equivalent_query", record_id="r3", phi=example, y="fail"),
            rule=None,
            prediction=opened.observation.prediction,
        )
        blocked = hunt.choose(wb)
        assert blocked is not None
        assert blocked.pool["rounds"] == 1
        assert blocked.pool["rejected_bad_setup"] >= 1
    finally:
        hunt.close()


def test_two_hash_seeds_yield_the_same_candidate_keys(tmp_path) -> None:
    corpus = _tiny_corpus(tmp_path / "corpus.json")
    script = tmp_path / "keys.py"
    script.write_text(
        "import json, sys\n"
        "from surprise.hunter import Hunter\n"
        "from surprise.theory import Workbench\n"
        "hunt = Hunter(engines=('duckdb',), oracles=('plan_variant', 'equivalent_query'), "
        "seed=42, corpus_path=sys.argv[1])\n"
        "try:\n"
        "    wb = Workbench.create(sys.argv[2])\n"
        "    keys = [list(c.key()) for c in hunt.candidates(wb)]\n"
        "    print(json.dumps(keys))\n"
        "finally:\n"
        "    hunt.close()\n",
        encoding="utf-8",
    )
    keys = []
    for hashseed in ("0", "1"):
        theory = tmp_path / f"theory-{hashseed}"
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = hashseed
        env["PYTHONPATH"] = str(FRAMEWORK)
        env.pop("DEEPSEEK_API_KEY", None)
        proc = subprocess.run(
            [sys.executable, str(script), str(corpus), str(theory)],
            cwd=str(FRAMEWORK),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=120,
        )
        assert proc.returncode == 0, proc.stderr
        keys.append(json.loads(proc.stdout.strip().splitlines()[-1]))
    assert keys[0] == keys[1]
    assert keys[0]


def _profiled(oracle: str) -> Label:
    skipped = {"status": "skipped", "reason": "not_requested"}
    return Label(
        y="fail",
        oracle=oracle,
        fail_kind="wrong_result",
        identity=IdentityEvidence(behavior={"missing": 1, "extra": 0}),
        cve={
            "schema": 1,
            "attribution": dict(skipped),
            "profile": {
                "status": "ran",
                "reason": None,
                "fix_kind": "non_optimizer",
                "fix_set": [],
                "plan_diff": [],
                "version_ladder": "longstanding",
                "witness_switches": [],
            },
        },
    )


def test_candidates_offer_all_four_lanes_on_a_hand_bench(tmp_path) -> None:
    from dataclasses import replace as dc_replace

    from surprise import features as F

    corpus = _tiny_corpus(tmp_path / "corpus.json")
    parent = SqlCase(
        engine="duckdb",
        setup=("CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1), (1), (2)"),
        query="SELECT a FROM t WHERE a > 0 AND a <> 2",
    )
    hunt = Hunter(
        engines=("duckdb", "datafusion"),
        oracles=("plan_variant", "cross_dbms", "equivalent_query"),
        seed=11,
        corpus_path=corpus,
    )
    try:
        wb = Workbench.create(tmp_path / "theory")
        example = hunt.phi(parent)
        out = wb.observe(example, _profiled("plan_variant"), "r1")
        assert out.observation.opened
        hunt.record(
            _record(parent, "plan_variant", record_id="r1", phi=example, y="fail"),
            rule=None,
            prediction=out.observation.prediction,
        )
        pool = hunt.candidates(wb)
        lanes = {lane: [c for c in pool if c.lane == lane] for lane in LANES}
        assert set(c.lane for c in pool) <= set(LANES)
        assert all(lanes[lane] for lane in LANES), {k: len(v) for k, v in lanes.items()}
        registry = default_registry()
        executed = {(case_digest(parent), "plan_variant", "")}
        seed_setups = {
            "duckdb": {
                ("CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1), (2)"),
                ("CREATE TABLE u(b INT)", "INSERT INTO u VALUES (9)"),
            },
            "datafusion": {("CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1), (2)")},
        }
        for cand in pool:
            assert cand.oracle in ("plan_variant", "cross_dbms", "equivalent_query")
            assert (cand.rule is None) == (cand.oracle != "equivalent_query")
            assert cand.rule is None or cand.rule in RULES
            assert cand.key() not in executed
            assert cand.key() == (case_digest(cand.case), cand.oracle, cand.rule or "")
            if cand.lane in ("refine", "generalize"):
                h = wb.theory.get(cand.hypothesis_id)
                assert cand.parent in h.positives and cand.oracle == h.oracle
                assert any(
                    case_digest(m) == case_digest(cand.case) and op == cand.op for m, op in mutants(parent)
                )
                phi = hunt.phi(cand.case)
                assert position(h, phi, h.oracle, registry) == "pending"
                target = Spec.from_dict(cand.target)
                closure = registry.closure(phi.features)
                missing = [lit for lit in h.specific if lit not in closure]
                swapped = [
                    lit
                    for lit in missing
                    if any(s in closure and s not in h.specific for s in registry.siblings(lit))
                ]
                assert F.check_spec(phi, target, registry).ok
                assert sorted(target.forbidden) == sorted(missing) and missing
                assert (cand.lane == "generalize") == bool(swapped)
            elif cand.lane == "migrate":
                h = wb.theory.get(cand.hypothesis_id)
                assert cand.parent in h.positives
                assert cand.case.engine != parent.engine and cand.op == "literal"
                assert dc_replace(cand.case, engine=parent.engine) == parent
                assert cand.oracle == h.oracle
            else:
                assert cand.hypothesis_id is None and cand.parent is None
                assert cand.op in ("seed", "seed_mutation")
                assert tuple(cand.case.setup) in seed_setups[cand.case.engine]
                assert cand.oracle not in ("tlp", "norec") or cand.case.predicate
        choice = hunt.choose(wb)
        assert choice is not None and choice.index == 1 and choice.slot == "any"
        assert choice.scored in choice.scored_pool
        assert choice.pool["scored"] == len(choice.scored_pool)
        assert choice.pool["rounds"] == 1
    finally:
        hunt.close()


def test_dropping_one_of_two_comparisons_is_refine_swapping_to_a_new_one_is_generalize(tmp_path) -> None:
    """Parent has two comparisons in S. Dropping one leaves the sibling still in S (refine);
    swapping a comparison for a value S does not hold is generalize."""
    corpus = _tiny_corpus(tmp_path / "corpus.json")
    parent = SqlCase(
        engine="duckdb",
        setup=("CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1), (1), (2)"),
        query="SELECT a FROM t WHERE a > 0 AND a <> 2",
    )
    hunt = Hunter(
        engines=("duckdb",),
        oracles=("plan_variant",),
        seed=11,
        corpus_path=corpus,
    )
    try:
        wb = Workbench.create(tmp_path / "theory")
        example = hunt.phi(parent)
        out = wb.observe(example, _profiled("plan_variant"), "r1")
        assert out.observation.opened
        hunt.record(
            _record(parent, "plan_variant", record_id="r1", phi=example, y="fail"),
            rule=None,
            prediction=out.observation.prediction,
        )
        pool = hunt.candidates(wb)
        drops = [c for c in pool if c.op == "q:conj:drop"]
        new_swaps = [c for c in pool if c.op in ("q:cmp:>->=", "q:cmp:<>->=")]
        assert drops, {c.op: c.lane for c in pool if c.lane in ("refine", "generalize")}
        assert new_swaps, {c.op: c.lane for c in pool if c.lane in ("refine", "generalize")}
        assert all(c.lane == "refine" for c in drops)
        assert all(c.lane == "generalize" for c in new_swaps)
        hypothesis = wb.theory.get(drops[0].hypothesis_id)
        registry = default_registry()
        specific = set(hypothesis.specific)
        for cand in drops:
            phi = hunt.phi(cand.case)
            closure = registry.closure(phi.features)
            missing = [lit for lit in hypothesis.specific if lit not in closure]
            swapped = [
                (lit, sib)
                for lit in missing
                for sib in registry.siblings(lit)
                if sib in closure and sib not in specific
            ]
            assert not swapped
            remaining_cmp = [lit for lit in ("ast:cmp:gt", "ast:cmp:neq") if lit in specific and lit in closure]
            assert remaining_cmp
        for cand in new_swaps:
            phi = hunt.phi(cand.case)
            closure = registry.closure(phi.features)
            missing = [lit for lit in hypothesis.specific if lit not in closure]
            swapped = [
                (lit, sib)
                for lit in missing
                for sib in registry.siblings(lit)
                if sib in closure and sib not in specific
            ]
            assert swapped
            assert "ast:cmp:eq" in closure and "ast:cmp:eq" not in specific
    finally:
        hunt.close()


def _candidate(case: SqlCase, *, lane: str, oracle: str = "plan_variant") -> Candidate:
    return Candidate(
        case=case,
        oracle=oracle,
        rule=None,
        lane=lane,
        hypothesis_id=None,
        parent=None,
        op="seed",
        target=None,
    )


def test_explore_skips_seeds_that_share_a_failed_setup(tmp_path, monkeypatch) -> None:
    bad = ["CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1), (2)"]
    good = ["CREATE TABLE u(b INT)", "INSERT INTO u VALUES (9)"]
    other = ["CREATE TABLE v(c INT)", "INSERT INTO v VALUES (4)"]
    seeds = [
        {
            "setup_sqls": bad,
            "query": "SELECT a FROM t WHERE a > 0",
            "source": "test:bad-1",
            "engine": "duckdb",
            "tags": [],
        },
        {
            "setup_sqls": good,
            "query": "SELECT b FROM u",
            "source": "test:good",
            "engine": "duckdb",
            "tags": [],
        },
        {
            "setup_sqls": bad,
            "query": "SELECT a FROM t WHERE a < 3",
            "source": "test:bad-2",
            "engine": "duckdb",
            "tags": [],
        },
        {
            "setup_sqls": other,
            "query": "SELECT c FROM v",
            "source": "test:other",
            "engine": "duckdb",
            "tags": [],
        },
        {
            "setup_sqls": bad,
            "query": "SELECT COUNT(*) FROM t",
            "source": "test:bad-3",
            "engine": "duckdb",
            "tags": [],
        },
    ]
    assert sum(seed["setup_sqls"] == bad for seed in seeds) > len(seeds) / 2
    corpus = tmp_path / "corpus.json"
    corpus.write_text(json.dumps(seeds), encoding="utf-8")
    wb = Workbench.create(tmp_path / "theory")
    hunt = Hunter(engines=("duckdb",), oracles=("plan_variant",), seed=5, corpus_path=corpus)
    bad_setup = tuple(bad)
    good_setup = tuple(good)
    other_setup = tuple(other)
    try:
        before = hunt.candidates(wb)
        assert any(tuple(cand.case.setup) == bad_setup for cand in before)
        hunt.record(
            _record(
                SqlCase(engine="duckdb", setup=bad_setup, query="SELECT a FROM t WHERE a > 0"),
                "plan_variant",
                record_id="r1",
                y="invalid",
                reason="setup_error",
            )
        )
        captured: list[list[tuple[tuple[str, ...], str]]] = []
        real_sample = hunt.rng.sample

        def capture(population, k):
            captured.append([(tuple(seed.setup_sqls), seed.query) for seed in population])
            return real_sample(population, k)

        monkeypatch.setattr(hunt.rng, "sample", capture)
        after = hunt.candidates(wb)
        assert captured == [
            [(good_setup, "SELECT b FROM u"), (other_setup, "SELECT c FROM v")]
        ]
        assert all(tuple(cand.case.setup) != bad_setup for cand in after)
        assert any(tuple(cand.case.setup) == good_setup for cand in after)
        assert any(tuple(cand.case.setup) == other_setup for cand in after)
    finally:
        hunt.close()


def test_choose_uses_the_second_round_when_the_first_is_filtered_out(tmp_path, monkeypatch) -> None:
    corpus = _tiny_corpus(tmp_path / "corpus.json")
    wb = Workbench.create(tmp_path / "theory")
    hunt = Hunter(engines=("duckdb",), oracles=("plan_variant",), seed=5, corpus_path=corpus)
    case = SqlCase(
        engine="duckdb",
        setup=("CREATE TABLE u(b INT)", "INSERT INTO u VALUES (9)"),
        query="SELECT b FROM u",
    )
    offered = _candidate(case, lane="explore")
    calls = {"n": 0}

    def same(_wb):
        calls["n"] += 1
        return [offered]

    draws = iter((1.0, 0.0))
    try:
        monkeypatch.setattr(hunt, "candidates", same)
        monkeypatch.setattr(hunt.rng, "random", lambda: next(draws))
        choice = hunt.choose(wb)
        assert choice is not None
        assert calls["n"] == 2
        assert choice.index == 1 and choice.slot == "any"
        assert choice.scored.candidate is offered
        assert choice.scored_pool == (choice.scored,)
        assert choice.pool == {
            "refine": 0,
            "generalize": 0,
            "migrate": 0,
            "explore": 2,
            "rejected_known": 0,
            "rejected_bad_setup": 0,
            "rejected_novelty": 1,
            "scored": 1,
            "rounds": 2,
        }
    finally:
        hunt.close()


def test_choose_returns_none_after_every_round_is_empty(tmp_path, monkeypatch) -> None:
    bad = ["CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1), (2)"]
    seeds = [
        {
            "setup_sqls": list(bad),
            "query": query,
            "source": f"test:bad-{index}",
            "engine": "duckdb",
            "tags": [],
        }
        for index, query in enumerate(
            ("SELECT a FROM t", "SELECT a FROM t WHERE a > 0", "SELECT COUNT(*) FROM t")
        )
    ]
    corpus = tmp_path / "corpus.json"
    corpus.write_text(json.dumps(seeds), encoding="utf-8")
    wb = Workbench.create(tmp_path / "theory")
    hunt = Hunter(engines=("duckdb",), oracles=("plan_variant",), seed=5, corpus_path=corpus)
    calls = {"n": 0}
    try:
        hunt.record(
            _record(
                SqlCase(engine="duckdb", setup=tuple(bad), query="SELECT a FROM t"),
                "plan_variant",
                record_id="r1",
                y="invalid",
                reason="setup_error",
            )
        )
        assert hunt.candidates(wb) == []
        real = hunt.candidates

        def counting(workbench):
            calls["n"] += 1
            return real(workbench)

        monkeypatch.setattr(hunt, "candidates", counting)
        assert hunt.choose(wb) is None
        assert calls["n"] == constants.EMPTY_ROUNDS
        assert hunt._index == 1
    finally:
        hunt.close()
