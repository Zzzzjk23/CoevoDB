"""Hunter: four lanes of candidates, scored by expected surprise."""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from seeds.mutate import SeedMutator
from seeds.store import SeedCorpus
from surprise.features.phi import Phi
from surprise.features.registry import default_registry
from surprise.harness.contracts import ExperimentRecord, SqlCase
from . import constants
from .constants import (
    EXPLORE_SEEDS_PER_STEP,
    MIGRATE_PER_STEP,
    MUTANTS_PER_STEP,
    NOVELTY_WINDOW,
    PARENTS_PER_HYPOTHESIS,
    SEED_MUTATIONS_PER_SEED,
)
from .extractor import PhiExtractor
from .operators import case_digest, mutants, oracle_options
from .scoring import accept_probability, hypothesis_units, is_explore_slot, novelty, score
from surprise.theory import Spec, position, reduce_conjunction
from surprise.theory.constants import BETA
from surprise.theory.predict import Prediction

_FRAMEWORK = Path(__file__).resolve().parents[2]
_DEFAULT_CORPUS = _FRAMEWORK / "seeds" / "corpus.json"

LANES = ("refine", "generalize", "migrate", "explore")


def _names(value: object, name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{name}: expected a non-empty sequence of strings, got {value!r}")
    items = tuple(value)
    if not items:
        raise ValueError(f"{name}: expected a non-empty sequence of strings")
    for item in items:
        if not isinstance(item, str) or item == "":
            raise ValueError(f"{name}: expected non-empty strings, got {item!r}")
    return items


@dataclass(frozen=True)
class Candidate:
    """One proposed experiment, before scoring."""

    case: SqlCase
    oracle: str
    rule: str | None
    lane: str
    hypothesis_id: str | None
    parent: str | None
    op: str
    target: dict | None

    def key(self) -> tuple[str, str, str]:
        return (case_digest(self.case), self.oracle, self.rule or "")


@dataclass(frozen=True)
class Scored:
    """A candidate with its phi and expected-surprise score."""

    candidate: Candidate
    phi: Phi
    score: Score

    @property
    def prediction(self):
        return self.score.prediction

    @property
    def D(self) -> float:
        return self.score.D

    @property
    def U(self) -> float:
        return self.score.U

    @property
    def adjacent(self) -> bool:
        return self.score.adjacent

    @property
    def probes(self) -> int:
        return self.score.probes

    @property
    def value(self) -> float:
        return self.score.value


@dataclass(frozen=True)
class Choice:
    """One selection from a scored pool. The Hunter does not record it."""

    index: int
    slot: str
    scored: Scored
    scored_pool: tuple[Scored, ...]
    pool: dict[str, int]


class Hunter:
    """Produces and selects candidates from the live theory. Execution is the loop's job."""

    def __init__(
        self,
        *,
        engines,
        oracles,
        seed: int,
        beta: float | None = None,
        corpus_path=None,
        extractor: PhiExtractor | None = None,
    ) -> None:
        self.engines = _names(engines, "engines")
        self.oracles = _names(oracles, "oracles")
        self._seed = int(seed)
        self.beta = float(BETA if beta is None else beta)
        self.rng = random.Random(self._seed)
        self.mutator = SeedMutator(rng=random.Random(self._seed + 1))
        self.corpus = SeedCorpus.load(_DEFAULT_CORPUS if corpus_path is None else corpus_path)
        self._registry = default_registry()
        self._owns_extractor = extractor is None
        self._extractor = PhiExtractor() if extractor is None else extractor
        self._index = 0
        self._by_id: dict[str, tuple[SqlCase, str, str | None]] = {}
        self._done: set[tuple[str, str, str]] = set()
        self._done_phi: set[tuple[str, str, frozenset[str]]] = set()
        self._windows: dict[tuple[str, str], list[frozenset[str]]] = {}
        self._bad_setups: set[tuple[str, ...]] = set()
        self._probes: dict[str, int] = {}

    def phi(self, case: SqlCase) -> Phi:
        return self._extractor.extract(case)

    def record(
        self,
        record: ExperimentRecord,
        *,
        rule: str | None = None,
        prediction: Prediction | None = None,
    ) -> None:
        self._by_id[record.record_id] = (record.case, record.label.oracle, rule)
        self._done.add((case_digest(record.case), record.label.oracle, rule or ""))
        if record.phi is not None:
            example = Phi.from_dict(record.phi)
            features = frozenset(example.features)
            scope = (record.case.engine, record.label.oracle)
            window = self._windows.setdefault(scope, [])
            window.append(features)
            extra = len(window) - NOVELTY_WINDOW
            if extra > 0:
                del window[:extra]
            self._done_phi.add((record.label.oracle, rule or "", features))
        if record.label.y == "invalid" and record.label.invalid_reason == "setup_error":
            self._bad_setups.add(tuple(record.case.setup))
        if prediction is not None and prediction.hypothesis_id is not None:
            hid = prediction.hypothesis_id
            self._probes[hid] = self._probes.get(hid, 0) + 1

    def candidates(self, wb) -> list[Candidate]:
        found: list[Candidate] = []
        found.extend(self._refine_generalize(wb))
        found.extend(self._migrate(wb))
        found.extend(self._explore())
        return found

    def choose(self, wb) -> Choice | None:
        self._index += 1
        slot = "explore" if is_explore_slot(self._index) else "any"
        raw = self.candidates(wb)
        pool = {lane: 0 for lane in LANES}
        pool["rejected_known"] = 0
        pool["rejected_bad_setup"] = 0
        pool["rejected_novelty"] = 0
        pool["scored"] = 0
        for cand in raw:
            pool[cand.lane] += 1
        units = hypothesis_units(wb, self._registry)
        scored: list[Scored] = []
        seen_keys: set[tuple[str, str, str]] = set()
        for cand in raw:
            key = cand.key()
            if key in self._done or key in seen_keys:
                pool["rejected_known"] += 1
                continue
            seen_keys.add(key)
            if tuple(cand.case.setup) in self._bad_setups:
                pool["rejected_bad_setup"] += 1
                continue
            example = self.phi(cand.case)
            phi_key = (cand.oracle, cand.rule or "", frozenset(example.features))
            if phi_key in self._done_phi:
                pool["rejected_novelty"] += 1
                continue
            recent = self._windows.get((cand.case.engine, cand.oracle), ())
            nov = novelty(frozenset(example.features), recent)
            if self.rng.random() >= accept_probability(nov):
                pool["rejected_novelty"] += 1
                continue
            scored.append(
                Scored(
                    candidate=cand,
                    phi=example,
                    score=score(
                        wb,
                        example,
                        cand.oracle,
                        beta=self.beta,
                        probes=self._probes,
                        units=units,
                    ),
                )
            )
        pool["scored"] = len(scored)
        explore_scored = tuple(item for item in scored if item.candidate.lane == "explore")
        if slot == "explore" and explore_scored:
            scope: tuple[Scored, ...] = explore_scored
        else:
            scope = tuple(scored)
        if not scope:
            return None
        best = max(item.value for item in scope)
        ties = [item for item in scope if item.value >= best - 1e-12]
        chosen = ties[0] if len(ties) == 1 else self.rng.choice(ties)
        return Choice(
            index=self._index,
            slot=slot,
            scored=chosen,
            scored_pool=tuple(scored),
            pool=pool,
        )

    def close(self) -> None:
        if self._owns_extractor:
            self._extractor.close()

    def manifest(self) -> dict:
        return {
            "constants": constants.as_dict(),
            "beta": self.beta,
            "engines": list(self.engines),
            "oracles": list(self.oracles),
            "seed": self._seed,
        }

    def _parents(self, hypothesis) -> list[str]:
        known = [record_id for record_id in hypothesis.positives if record_id in self._by_id]
        return known[-PARENTS_PER_HYPOTHESIS:]

    def _refine_generalize(self, wb) -> list[Candidate]:
        eligible: list[tuple[object, list[str]]] = []
        for hypothesis in wb.theory.hypotheses:
            if hypothesis.engine not in self.engines or hypothesis.oracle is None:
                continue
            parents = self._parents(hypothesis)
            if parents:
                eligible.append((hypothesis, parents))
        if not eligible:
            return []
        quota = max(1, MUTANTS_PER_STEP // len(eligible))
        found: list[Candidate] = []
        for hypothesis, parents in eligible:
            pool: list[tuple[SqlCase, str, str]] = []
            for parent_id in parents:
                parent_case, parent_oracle, parent_rule = self._by_id[parent_id]
                for mutant, op in mutants(parent_case):
                    pool.append((mutant, op, parent_id))
            if len(pool) > quota:
                picked = sorted(self.rng.sample(range(len(pool)), quota))
                pool = [pool[index] for index in picked]
            for mutant, op, parent_id in pool:
                if mutant.engine not in self.engines:
                    continue
                example = self.phi(mutant)
                if position(hypothesis, example, hypothesis.oracle, self._registry) != "pending":
                    continue
                closure = self._registry.closure(example.features)
                missing = [lit for lit in hypothesis.specific if lit not in closure]
                swapped = [
                    (lit, sib)
                    for lit in missing
                    for sib in self._registry.siblings(lit)
                    if sib in closure and sib not in hypothesis.specific
                ]
                lane = "generalize" if swapped else "refine"
                required = reduce_conjunction(
                    [lit for lit in hypothesis.specific if lit not in missing]
                    + [sib for _lit, sib in swapped],
                    self._registry,
                )
                target = Spec(
                    engine=hypothesis.engine,
                    oracle=hypothesis.oracle,
                    required=required,
                    forbidden=tuple(sorted(missing)),
                )
                _, parent_oracle, parent_rule = self._by_id[parent_id]
                rule = parent_rule if parent_oracle == "equivalent_query" else None
                found.append(
                    Candidate(
                        case=mutant,
                        oracle=hypothesis.oracle,
                        rule=rule,
                        lane=lane,
                        hypothesis_id=hypothesis.hypothesis_id,
                        parent=parent_id,
                        op=op,
                        target=target.to_dict(),
                    )
                )
        return found

    def _migrate(self, wb) -> list[Candidate]:
        if len(self.engines) < 2:
            return []
        found: list[Candidate] = []
        for hypothesis in wb.theory.hypotheses:
            if hypothesis.oracle is None:
                continue
            for parent_id in self._parents(hypothesis):
                parent_case, _parent_oracle, parent_rule = self._by_id[parent_id]
                for engine in self.engines:
                    if engine == hypothesis.engine:
                        continue
                    try:
                        moved = replace(parent_case, engine=engine)
                    except ValueError:
                        continue
                    options = oracle_options(moved, [hypothesis.oracle])
                    if not options:
                        continue
                    if any(rule == parent_rule for _oracle, rule in options):
                        rule = parent_rule
                    else:
                        rule = options[0][1]
                    found.append(
                        Candidate(
                            case=moved,
                            oracle=hypothesis.oracle,
                            rule=rule,
                            lane="migrate",
                            hypothesis_id=hypothesis.hypothesis_id,
                            parent=parent_id,
                            op="literal",
                            target=None,
                        )
                    )
        if len(found) > MIGRATE_PER_STEP:
            picked = sorted(self.rng.sample(range(len(found)), MIGRATE_PER_STEP))
            found = [found[index] for index in picked]
        return found

    def _explore(self) -> list[Candidate]:
        found: list[Candidate] = []
        for engine in self.engines:
            seeds = list(self.corpus.for_engine(engine).seeds)
            if not seeds:
                continue
            chosen = self.rng.sample(seeds, min(EXPLORE_SEEDS_PER_STEP, len(seeds)))
            for seed in chosen:
                cases: list[tuple[SqlCase, str]] = []
                try:
                    cases.append(
                        (
                            SqlCase(
                                engine=engine,
                                setup=tuple(seed.setup_sqls),
                                query=seed.query,
                                predicate=None,
                            ),
                            "seed",
                        )
                    )
                except ValueError:
                    pass
                for mutation in self.mutator.mutations_for(seed, max_per_seed=SEED_MUTATIONS_PER_SEED):
                    try:
                        cases.append(
                            (
                                SqlCase(
                                    engine=engine,
                                    setup=tuple(mutation.setup_sqls),
                                    query=mutation.select_from,
                                    predicate=mutation.predicate,
                                ),
                                "seed_mutation",
                            )
                        )
                    except ValueError:
                        continue
                for case, op in cases:
                    for oracle, rule in oracle_options(case, self.oracles):
                        found.append(
                            Candidate(
                                case=case,
                                oracle=oracle,
                                rule=rule,
                                lane="explore",
                                hypothesis_id=None,
                                parent=None,
                                op=op,
                                target=None,
                            )
                        )
        return found
