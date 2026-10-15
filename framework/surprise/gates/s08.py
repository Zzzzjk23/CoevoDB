"""S8 gate: the Hunter and the closed loop without any LLM (milestone M2).

Usage (from ``framework/``)::

    python -m surprise.gates.s08                          # everything
    python -m surprise.gates.s08 --only scoring operators no_llm

Exit code 0 = pass. Groups, following the S8 section of SESSIONS.md:

``no_llm``       the new packages import no model client and no old agent code;
``constants``    the Hunter and Diagnoser constants have the planned values; BETA
                 is a theory constant fixed by the recorded pre-experiment;
``scoring``      value = P_valid x (D + beta U), the optimistic residual estimate,
                 the adjacency prior, the downweight of over-probed hypotheses,
                 novelty, the exploration slot;
``operators``    the mutation operators and which oracles a case is offered to;
``candidates``   after two known reproductions on the real engines, the Hunter
                 offers all four lanes, each with a provenance that checks out;
``lanes``        a short run of the loop: one ledger record per experiment, every
                 experiment traceable to its lane, the exploration slot kept;
``determinism``  two runs with the same seed give the same experiments and labels;
``longrun``      the recorded run of several hours on DuckDB finished cleanly;
``sawtooth``     its surprise curve (mean of each 100 executions) rises and falls;
``duplicates``   its duplicate-family rate is below the old system's no_llm run on
                 the same wall-clock budget;
``recall``       the recall report for the known bugs on DuckDB 1.1.3.

The last four read artifacts the orchestrator produces with the merged code and
pins in ``s08_runs.json`` (paths relative to ``framework/``, sha256 of each file);
they fail until then. Tables live in ``s08_cases.py``. PostgreSQL reference:
COEVO_REFERENCE_PG_DSN or local port 55432 (see HANDOFF). Output is ASCII only.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from . import s04_cases as C4
from . import s06_cases as C6
from . import s08_cases as C
from .s06 import GateFailure, _ascii, close, require

FRAMEWORK = Path(__file__).resolve().parents[2]
RUNS_FILE = Path(__file__).resolve().parent / "s08_runs.json"
CODE_DIRS = ("surprise/hunter", "surprise/diagnoser", "surprise/experiments")
LLM_MODULES = ("openai", "httpx", "httpx2", "anthropic", "agents", "agents.base_agent", "agents.bug_hunter",
               "agents.bug_fixer", "llm", "llm.ledger", "evolution.co_evolution", "guidelines")


def theory() -> Any:
    from surprise import theory as T

    return T


def hunter() -> Any:
    import surprise.hunter as H

    return H


def load_case(name: str) -> Any:
    from . import s04 as G4

    return G4.load(name)


def code_digests() -> dict[str, str]:
    """sha256 of every .py file the loop runs, with CRLF read as LF, keyed by path relative to framework/."""
    digests: dict[str, str] = {}
    for folder in CODE_DIRS:
        for path in sorted((FRAMEWORK / folder).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            blob = path.read_bytes().replace(b"\r\n", b"\n")
            digests[path.relative_to(FRAMEWORK).as_posix()] = hashlib.sha256(blob).hexdigest()
    return digests


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def bootstrap_file(directory: Path, names: tuple[tuple[str, str], ...]) -> Path:
    items = [{"case": load_case(name).to_dict(), "oracle": oracle, "rule": None} for name, oracle in names]
    path = directory / "bootstrap.json"
    path.write_text(json.dumps(items, indent=1), encoding="utf-8")
    return path


def run_loop(out: Path, *, seed: int, engines: tuple[str, ...], experiments: int, bootstrap: Path | None) -> subprocess.CompletedProcess:
    command = [sys.executable, "-m", "surprise.experiments.loop", "--out", str(out), "--seed", str(seed),
               "--max-experiments", str(experiments)]
    for engine in engines:
        command += ["--engine", engine]
    if bootstrap is not None:
        command += ["--bootstrap", str(bootstrap)]
    return subprocess.run(command, cwd=FRAMEWORK, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=3600)


def open_run(out: Path) -> dict[str, Any]:
    """Everything a run directory holds, read back."""
    from surprise.harness.ledger import Ledger

    T = theory()
    require((out / "ledger.sqlite").is_file() and (out / "theory").is_dir() and (out / "progress.jsonl").is_file()
            and (out / "report.json").is_file(), f"{out}: a run directory holds ledger.sqlite, theory/, progress.jsonl, report.json")
    ledger = Ledger(out / "ledger.sqlite")
    try:
        run_ids = ledger.run_ids()
        require(len(run_ids) == 1, f"{out}: one run per ledger, found {run_ids}")
        records = ledger.records(run_id=run_ids[0])
        manifest = ledger.run_manifest(run_ids[0])
    finally:
        ledger.close()
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    progress = read_jsonl(out / "progress.jsonl")
    wb = T.Workbench.open(out / "theory")
    return {"run_id": run_ids[0], "records": records, "manifest": manifest, "report": report, "progress": progress, "wb": wb}


def pinned(name: str) -> dict[str, Any]:
    require(RUNS_FILE.is_file(), f"{RUNS_FILE.name} is not written yet: the orchestrator pins the artifacts after running them")
    runs = json.loads(RUNS_FILE.read_text(encoding="utf-8"))
    require(name in runs, f"{RUNS_FILE.name} has no '{name}' entry yet")
    return runs[name]


def pinned_dir(entry: dict[str, Any]) -> Path:
    out = FRAMEWORK / entry["dir"]
    require(out.is_dir(), f"artifact directory {entry['dir']} is missing on this machine")
    for rel, digest in entry.get("sha256", {}).items():
        path = out / rel
        require(path.is_file() and file_digest(path) == digest, f"{entry['dir']}/{rel} is missing or is not the pinned artifact")
    return out


def minutes_between(first: str, last: str) -> float:
    return (datetime.fromisoformat(last) - datetime.fromisoformat(first)).total_seconds() / 60.0


# ---- no_llm, constants ------------------------------------------------------------------

def check_no_llm() -> str:
    probe = ("import sys, json\n"
             "import surprise.hunter, surprise.metrics, surprise.baselines, surprise.diagnoser, surprise.experiments.loop\n"
             "import surprise.metrics.curve, surprise.metrics.dups, surprise.metrics.recall, surprise.baselines.old_no_llm\n"
             f"bad = sorted(m for m in {list(LLM_MODULES)!r} if m in sys.modules)\n"
             "print(json.dumps(bad))\n")
    proc = subprocess.run([sys.executable, "-c", probe], cwd=FRAMEWORK, capture_output=True, text=True, timeout=300)
    require(proc.returncode == 0, f"the S8 modules must import cleanly: {proc.stderr[-600:]}")
    bad = json.loads(proc.stdout.strip().splitlines()[-1])
    require(bad == [], f"S8 runs without any LLM: these model or agent modules were imported: {bad}")
    return "hunter, metrics, baselines, diagnoser and the loop import no model client and no old agent"


def check_constants() -> str:
    from surprise.diagnoser import constants as DC
    from surprise.hunter import constants as HC

    T = theory()
    have = HC.as_dict()
    for name, value in C.HUNTER_CONSTANTS.items():
        require(name in have and have[name] == value and type(have[name]) is type(value),
                f"hunter constant {name} must be {value!r}, got {have.get(name)!r}")
    have_d = DC.as_dict()
    for name, value in C.DIAGNOSER_CONSTANTS.items():
        require(name in have_d and have_d[name] == value and type(have_d[name]) is type(value),
                f"diagnoser constant {name} must be {value!r}, got {have_d.get(name)!r}")
    beta = T.constants.as_dict().get("BETA")
    require(isinstance(beta, float) and beta > 0, f"BETA must be a positive float theory constant, got {beta!r}")
    require(T.theory_manifest()["constants"].get("BETA") == beta, "BETA reaches the theory section of the run manifest")
    entry = pinned("beta")
    require(entry.get("value") == beta, f"BETA {beta} must be the value the pre-experiment chose, {entry.get('value')}")
    table = entry.get("results", {})
    require(sorted(float(b) for b in table) == sorted(C.BETA_CANDIDATES)
            and all(sorted(int(s) for s in table[b]) == sorted(C.PRE_SEEDS) for b in table)
            and entry.get("experiments") == C.PRE_EXPERIMENTS,
            f"the pre-experiment covers beta {C.BETA_CANDIDATES} x seeds {C.PRE_SEEDS} at {C.PRE_EXPERIMENTS} experiments")
    best = max(C.BETA_CANDIDATES, key=lambda b: (_median([table[str(b)][str(s)] for s in C.PRE_SEEDS]),
                                                  sum(table[str(b)][str(s)] for s in C.PRE_SEEDS), -b))
    require(best == beta, f"the rule (highest median of distinct families, then highest total, then smaller beta) picks {best}")
    return (f"{len(have)} hunter and {len(have_d)} diagnoser constants as planned; BETA = {beta} "
            f"(pre-experiment families per run: {table})")


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


# ---- scoring ----------------------------------------------------------------------------

def check_scoring() -> str:
    from surprise.hunter import constants as HC
    from surprise.hunter import scoring as S

    from . import s07 as G7

    T = theory()
    require(close(S.binary_entropy(0.5), 1.0) and S.binary_entropy(0.0) == 0.0 and S.binary_entropy(1.0) == 0.0
            and close(S.binary_entropy(0.11), -(0.11 * math.log2(0.11) + 0.89 * math.log2(0.89))), "binary entropy in bits")
    for (tested, unexplained), expected in C.OPTIMISTIC.items():
        got = S.optimistic_rate(tested, unexplained)
        require(close(got, expected), f"optimistic_rate({tested}, {unexplained}) = {got}, expected {expected}")
    plain, adj = S.uncertainty(0, 0, False), S.uncertainty(0, 0, True)
    require(close(plain, S.binary_entropy(C.OPTIMISTIC[(0, 0)])) and close(adj, S.binary_entropy(min(0.5, 2.0 * C.OPTIMISTIC[(0, 0)])))
            and adj > plain > S.uncertainty(99, 0, False), f"U: untested {plain}, untested and adjacent {adj}")
    require(close(S.uncertainty(100, 100, False), 1.0) and close(S.uncertainty(100, 100, True), 1.0), "U is capped at 1 bit")
    require([S.disagreement(z) for z in T.ZONES] == [0.0, 1.0, 0.0], "D is one bit in the pending zone only")
    require(close(S.downweight(0), 1.0) and close(S.downweight(50), 0.5) and close(S.downweight(150), 0.25), "downweight 1 / (1 + n / 50)")
    require(close(S.value(0.1, 1.0, 0.0, 2.0, 0), 0.9) and close(S.value(0.2, 0.0, 0.5, 2.0, 50), 0.8 * 1.0 * 0.5)
            and S.value(0.3, 0.0, 0.0, 4.0, 0) == 0.0, "value = (1 - p_invalid) (D + beta U) / (1 + probes / 50)")
    a, b = frozenset({"x", "y", "z"}), frozenset({"y", "z", "w"})
    require(close(S.jaccard(a, b), 0.5) and S.jaccard(frozenset(), frozenset()) == 1.0, "Jaccard similarity")
    require(close(S.novelty(a, [b, frozenset({"q"})]), 0.5) and S.novelty(a, []) == 1.0 and S.novelty(a, [a]) == 0.0, "novelty")
    require(close(S.accept_probability(0.0), HC.NOVELTY_FLOOR) and close(S.accept_probability(1.0), 1.0)
            and close(S.accept_probability(0.5), 0.2 + 0.8 * 0.5), "accept probability floor + (1 - floor) novelty")
    require([i for i in range(0, 21) if S.is_explore_slot(i)] == [5, 10, 15, 20], "every fifth choice is an exploration slot")
    u = "duckdb|tlp|window|window|dups"
    require(S.adjacent("duckdb|norec|window|scan|plain", [u]) and S.adjacent("duckdb|tlp|window|none|unknown", [u])
            and not S.adjacent(u, [u]) and not S.adjacent("duckdb|tlp|join|window|dups", [u])
            and not S.adjacent("datafusion|tlp|window|window|dups", [u]) and not S.adjacent(u, []),
            "adjacent = same engine and construct as a unit some hypothesis was seen in, but not that unit")
    # the same rules through the theory: confirmed, pending, unexplored and adjacent
    tmp = tempfile.mkdtemp(prefix="s08-gate-")
    try:
        wb, first = G7.opened_bench(tmp)
        units = S.hypothesis_units(wb)
        require(len(units) == 1 and next(iter(units)).startswith("datafusion|cross_dbms|"), f"units of the positives: {units}")
        beta = 2.0
        conf = S.score(wb, G7.phi("x1"), "cross_dbms", beta=beta, probes={}, units=units)
        pend = S.score(wb, G7.phi("x3"), "cross_dbms", beta=beta, probes={first: 50}, units=units)
        other = S.score(wb, G7.phi("x1"), "tlp", beta=beta, probes={}, units=units)
        require(conf.prediction.zone == "confirmed" and conf.D == 0.0 and conf.U == 0.0 and conf.value == 0.0,
                f"a predicted duplicate is worth nothing: {conf}")
        require(pend.prediction.zone == "pending" and pend.D == 1.0 and pend.U == 0.0 and pend.probes == 50
                and close(pend.value, (1 - pend.prediction.p_invalid) * 1.0 * 0.5), f"a boundary sample, probed 50 times: {pend}")
        require(other.prediction.zone == "unexplored" and other.adjacent and other.D == 0.0
                and close(other.U, S.uncertainty(0, 0, True)) and close(other.value, (1 - other.prediction.p_invalid) * beta * other.U),
                f"an untested unit next to a known hypothesis: {other}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return (f"U untested {plain:.3f} bits, adjacent {adj:.3f}; pending {pend.value:.3f} after 50 probes, "
            f"adjacent unexplored {other.value:.3f} at beta 2, confirmed 0")


# ---- operators --------------------------------------------------------------------------

def check_operators() -> str:
    from evolution.dce import mutate_query_text, mutate_setup
    from surprise.harness.contracts import SqlCase
    from surprise.harness.oracles.rewrites import RULES

    H = hunter()
    O = H.operators
    case = SqlCase(engine="duckdb", setup=("CREATE TABLE t(a INT, b INT)", "INSERT INTO t VALUES (1, 2), (3, NULL), (3, NULL)",
                                           "INSERT INTO t VALUES (5, 6)"),
                   query="SELECT a FROM t WHERE a > 1 AND b <> 2", predicate="b IS NOT NULL")
    found = O.mutants(case)
    ops = [op for _m, op in found]
    digests = [O.case_digest(m) for m, _op in found]
    require(len(set(digests)) == len(digests) and O.case_digest(case) not in digests, "mutants are distinct and differ from the case")
    expected_q = {"q:" + op for _t, op in mutate_query_text(case.query)}
    expected_p = {"p:" + op for _t, op in mutate_query_text(case.predicate)}
    expected_s = {"s:" + op for _s, op in mutate_setup(list(case.setup))}
    require(expected_q <= set(ops) and expected_p <= set(ops) and expected_s <= set(ops), "the old DCE operators are all reused")
    drops = {op: m for m, op in found if op.startswith("s:drop_")}
    # rows 1 and 2 are the same (3, NULL): deleting either gives one case, kept once under the first label
    require(set(drops) == {"s:drop_row[1][0]", "s:drop_row[1][1]", "s:drop_insert[1]", "s:drop_insert[2]"},
            f"one deletion per VALUES row of a multi-row INSERT, and one per INSERT statement, duplicates once: {sorted(drops)}")
    require(drops["s:drop_row[1][1]"].setup[1] == "INSERT INTO t VALUES (1, 2), (3, NULL)"
            and drops["s:drop_row[1][0]"].setup[1] == "INSERT INTO t VALUES (3, NULL), (3, NULL)"
            and drops["s:drop_insert[2]"].setup == case.setup[:2], "deleting a row keeps the statement well formed")
    require(O.mutants(case) == found, "the operators are deterministic")
    rules = tuple(RULES)
    require(O.oracle_options(case, C.ORACLES) == [("tlp", None), ("norec", None), ("plan_variant", None), ("index_presence", None),
                                                 *[("equivalent_query", r) for r in rules], ("version_differential", None),
                                                 ("cross_dbms", None)], "every oracle, one entry per rewrite rule")
    bare = dataclasses.replace(case, predicate=None, engine="datafusion")
    require(O.oracle_options(bare, C.ORACLES) == [("plan_variant", None), *[("equivalent_query", r) for r in rules],
                                                 ("version_differential", None), ("cross_dbms", None)],
            "TLP and NoREC need a predicate; index presence is DuckDB only")
    return f"{len(found)} mutants of a three-statement case ({len(drops)} deletions); oracle options filtered as planned"


# ---- candidates on the real engines ------------------------------------------------------

def _feed(wb: Any, ledger: Any, run_id: str, h: Any, case: Any, oracle: str) -> Any:
    from surprise import features as F
    from surprise.harness.evaluate import evaluate_final

    T = theory()
    example = F.extract(case)
    prediction = wb.predict(example, oracle)
    owner = prediction.hypothesis_id
    options: dict[str, Any] = {"diagnose": True} if owner is None else {"hypothesis": T.attribution_request(wb.theory.get(owner))}
    record = evaluate_final(case, oracle, ledger=ledger, run_id=run_id, purpose="bootstrap", phi=example.to_dict(),
                            theory_version=wb.theory.version, p_t=prediction.p_fail_valid, **options)
    outcome = wb.observe(example, record.label, record.record_id, prediction=prediction)
    h.record(record, rule=None, prediction=prediction)
    return outcome


def check_candidates() -> str:
    from seeds.store import SeedCorpus
    from surprise import features as F
    from surprise.harness.ledger import Ledger
    from surprise.harness.manifest import build_manifest
    from surprise.harness.oracles.rewrites import RULES
    from surprise.theory.contracts import Spec

    T = theory()
    H = hunter()
    registry = F.default_registry()
    tmp = tempfile.mkdtemp(prefix="s08-gate-")
    hunt = H.Hunter(engines=("duckdb", "datafusion"), oracles=C.ORACLES, seed=C.CANDIDATES_SEED)
    try:
        wb = T.Workbench.create(Path(tmp) / "theory")
        ledger = Ledger(Path(tmp) / "ledger.sqlite")
        run_id = "s08-candidates"
        ledger.start_run(run_id, T.extend_manifest(build_manifest(run_id)))
        cases = {}
        for name, oracle in C.BOOTSTRAP:
            case = load_case(name)
            out = _feed(wb, ledger, run_id, hunt, case, oracle)
            require(out.observation.opened, f"{name} opens a family: {out}")
            cases[out.observation.opened] = (case, oracle)
        by_record = {r.record_id: r for r in ledger.records(run_id=run_id)}
        ledger.close()
        pool = hunt.candidates(wb)
        lanes = {lane: [c for c in pool if c.lane == lane] for lane in C.LANES}
        require(set(c.lane for c in pool) <= set(C.LANES) and all(lanes[lane] for lane in C.LANES),
                f"all four lanes offer candidates: { {k: len(v) for k, v in lanes.items()} }")
        corpus = SeedCorpus.load(FRAMEWORK / "seeds" / "corpus.json")
        seed_setups = {e: {tuple(s.setup_sqls) for s in corpus.for_engine(e).seeds} for e in ("duckdb", "datafusion")}
        executed = {(H.operators.case_digest(r.case), r.label.oracle, "") for r in by_record.values()}
        for cand in pool:
            require(cand.oracle in C.ORACLES and (cand.rule is None) == (cand.oracle != "equivalent_query")
                    and (cand.rule is None or cand.rule in RULES), f"oracle and rule: {cand}")
            require(cand.key() not in executed and cand.key() == (H.operators.case_digest(cand.case), cand.oracle, cand.rule or ""),
                    f"never offer an experiment already run: {cand}")
            if cand.lane in ("refine", "generalize"):
                h = wb.theory.get(cand.hypothesis_id)
                parent = by_record[cand.parent].case
                require(cand.parent in h.positives and cand.oracle == h.oracle, f"derived from a positive of {h.hypothesis_id}: {cand}")
                require(any(H.operators.case_digest(m) == H.operators.case_digest(cand.case) and op == cand.op
                            for m, op in H.operators.mutants(parent)), f"one mutation of its parent: {cand.op}")
                example = hunt.phi(cand.case)
                require(T.position(h, example, h.oracle, registry) == "pending", f"lands between S and G of {h.hypothesis_id}")
                target = Spec.from_dict(cand.target)
                closure = registry.closure(example.features)
                missing = sorted(lit for lit in h.specific if lit not in closure)
                # a swap brings in another value of the same class that S does not already hold
                swapped = [lit for lit in missing if any(s in closure and s not in h.specific for s in registry.siblings(lit))]
                require(F.check_spec(example, target, registry).ok and sorted(target.forbidden) == missing and missing
                        and (cand.lane == "generalize") == bool(swapped),
                        f"{cand.lane}: target {cand.target} vs missing {missing}, swapped {swapped}")
            elif cand.lane == "migrate":
                h = wb.theory.get(cand.hypothesis_id)
                parent = by_record[cand.parent].case
                require(cand.parent in h.positives and cand.case.engine != parent.engine and cand.op == "literal"
                        and dataclasses.replace(cand.case, engine=parent.engine) == parent and cand.oracle == h.oracle,
                        f"a literal copy of a positive on the other engine: {cand}")
            else:
                require(cand.hypothesis_id is None and cand.parent is None and cand.op in ("seed", "seed_mutation")
                        and tuple(cand.case.setup) in seed_setups[cand.case.engine], f"explore from the seed corpus: {cand}")
                require(cand.oracle not in ("tlp", "norec") or cand.case.predicate, "TLP and NoREC only with a predicate")
        choice = hunt.choose(wb)
        require(choice is not None and choice.index == 1 and choice.slot == "any", f"the first choice: {choice}")
        values = [s.value for s in choice.scored_pool]
        require(choice.scored in choice.scored_pool and close(choice.scored.value, max(values)),
                "the chosen candidate has the highest value among those that passed the novelty draw")
        require(set(choice.pool) == {*C.LANES, "rejected_known", "rejected_bad_setup", "rejected_novelty", "scored", "rounds"}
                and choice.pool["scored"] == len(choice.scored_pool) and choice.pool["rounds"] == 1, f"pool counts: {choice.pool}")
    finally:
        hunt.close()
        shutil.rmtree(tmp, ignore_errors=True)
    shown = {k: len(v) for k, v in lanes.items()}
    return f"after F1 and DF-A: {shown} candidates, all traceable; chose {choice.scored.candidate.lane} at {choice.scored.value:.3f}"


# ---- short runs of the loop --------------------------------------------------------------

def check_rows(run: dict[str, Any], out: Path) -> dict[str, int]:
    """Provenance of every experiment in a run directory. Returns the lane counts."""
    from seeds.store import SeedCorpus
    from surprise import features as F
    from surprise.features.phi import Phi
    from surprise.harness.manifest import verify_manifest
    from surprise.theory.contracts import Spec

    T = theory()
    H = hunter()
    registry = F.default_registry()
    records, progress, manifest = run["records"], run["progress"], run["manifest"]
    require(len(records) == len(progress) and [r.record_id for r in records] == [row["record_id"] for row in progress],
            "one progress row per ledger record, in the same order")
    require(verify_manifest(manifest) == [] and T.verify_theory_manifest(manifest) == [], "the run manifest verifies")
    section = manifest.get("hunter", {})
    require(section.get("constants") == H.constants.as_dict() and section.get("code") == code_digests()
            and section.get("seed") == run["report"].get("seed"), "the manifest names the Hunter constants, seed and code that ran")
    require(run["wb"].store.verify() == [], "the theory store verifies")
    by_id = {r.record_id: r for r in records}
    corpus = SeedCorpus.load(FRAMEWORK / "seeds" / "corpus.json")
    seed_setups = {e: {tuple(s.setup_sqls) for s in corpus.for_engine(e).seeds} for e in ("duckdb", "datafusion")}
    seen: set[tuple[str, str, str]] = set()
    lanes: dict[str, int] = {}
    for record, row in zip(records, progress):
        label, spec = record.label, record.spec or {}
        lane = row["lane"]
        lanes[lane] = lanes.get(lane, 0) + 1
        key = (H.operators.case_digest(record.case), label.oracle, spec.get("rule") or "")
        require(key not in seen, f"{record.record_id}: the same experiment ran twice")
        seen.add(key)
        require(record.phi is not None and record.p_t is not None and record.theory_version is not None
                and spec.get("lane") == lane == record.purpose, f"{record.record_id}: the ledger keeps phi, P_T, the theory and the lane")
        bits = None if label.y == "invalid" else T.surprise_bits(record.p_t, label.y)
        require((bits is None and row["surprise"] is None) or close(bits, row["surprise"]), f"{record.record_id}: surprise from the ledger")
        example = Phi.from_dict(record.phi)
        if lane in ("refine", "generalize"):
            parent = by_id[spec["parent"]]
            target = Spec.from_dict(spec["target"])
            # The lane rule is the generating hypothesis's own position (see check_candidates). The theory's
            # prediction may instead name another hypothesis whose confirmed zone covers the mutant; the
            # target's forbidden literals still keep it out of the generating hypothesis's confirmed zone.
            zone_ok = row["zone"] == "pending" or (
                row["zone"] == "confirmed" and row["predicted"] not in (None, spec["hypothesis"]) and bool(target.forbidden))
            require(zone_ok and F.check_spec(example, target, registry).ok
                    and any(H.operators.case_digest(m) == key[0] and op == spec["op"] for m, op in H.operators.mutants(parent.case)),
                    f"{record.record_id}: {lane} is a mutation of {spec['parent']} that meets its target in the pending zone")
        elif lane == "migrate":
            parent = by_id[spec["parent"]]
            require(dataclasses.replace(record.case, engine=parent.case.engine) == parent.case and record.case.engine != parent.case.engine,
                    f"{record.record_id}: migrate is a literal copy of {spec['parent']}")
        elif lane == "explore":
            require(tuple(record.case.setup) in seed_setups[record.case.engine] and spec.get("op") in ("seed", "seed_mutation"),
                    f"{record.record_id}: explore starts from a seed")
        else:
            require(lane == "bootstrap" and row["index"] == 0, f"{record.record_id}: unknown lane {lane}")
        if row["index"] and row["index"] % C.HUNTER_CONSTANTS["EXPLORE_EVERY"] == 0:
            # Another lane only when no exploration candidate survived the filters (the s08-hunter rule); the
            # pool counts cannot show which lanes were filtered, so this is the necessary condition they allow.
            others = sum(row["pool"][name] for name in ("refine", "generalize", "migrate"))
            require(row["slot"] == "explore" and (lane == "explore" or row["pool"]["scored"] <= others),
                    f"{record.record_id}: choice {row['index']} is an exploration slot")
    return lanes


def check_lanes() -> str:
    tmp = Path(tempfile.mkdtemp(prefix="s08-gate-"))
    try:
        boot = bootstrap_file(tmp, C.BOOTSTRAP)
        spec = C.LANES_RUN
        proc = run_loop(tmp / "run", seed=spec["seed"], engines=spec["engines"], experiments=spec["experiments"], bootstrap=boot)
        require(proc.returncode == 0, f"the loop exits cleanly: {proc.returncode} {proc.stderr[-800:]}")
        run = open_run(tmp / "run")
        report = run["report"]
        require(report.get("status") == "budget_experiments" and report.get("experiments") == len(run["records"])
                == spec["experiments"] + len(C.BOOTSTRAP), f"the run stops at its budget: {report.get('status')} {report.get('experiments')}")
        lanes = check_rows(run, tmp / "run")
        require(lanes.get("explore", 0) >= 1 and lanes.get("refine", 0) + lanes.get("generalize", 0) >= 1,
                f"exploration and boundary probes both ran: {lanes}")
        pools = [row["pool"] for row in run["progress"] if row["index"]]
        offered = {lane: sum(p.get(lane, 0) for p in pools) for lane in C.LANES}
        require(all(offered.values()), f"every lane offered candidates during the run: {offered}")
        edits = [e for row in run["progress"] for e in row.get("edits", [])]
        opened = [row for row in run["progress"] if row["opened"]]
        require(all(e.get("proposer") in ("diagnoser", "mdl") for e in edits), f"edits come from the Diagnoser or MDL: {edits}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return f"{len(run['records'])} records; executed {lanes}; offered {offered}; {len(opened)} families opened, {len(edits)} edits"


def _normal(run: dict[str, Any]) -> list[Any]:
    rows = [{k: v for k, v in row.items() if k not in ("elapsed_s",)} for row in run["progress"]]
    labels = [r.label.to_dict() for r in run["records"]]
    return [rows, labels, run["wb"].theory.version]


def check_determinism() -> str:
    tmp = Path(tempfile.mkdtemp(prefix="s08-gate-"))
    try:
        boot = bootstrap_file(tmp, C.BOOTSTRAP[:1])
        spec = C.DETERMINISM_RUN
        jobs = {"a": spec["seed"], "b": spec["seed"], "c": spec["other_seed"]}
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = {name: pool.submit(run_loop, tmp / name, seed=seed, engines=spec["engines"], experiments=spec["experiments"],
                                         bootstrap=boot) for name, seed in jobs.items()}
            procs = {name: f.result() for name, f in futures.items()}
        for name, proc in procs.items():
            require(proc.returncode == 0, f"run {name} exits cleanly: {proc.stderr[-600:]}")
        runs = {name: open_run(tmp / name) for name in jobs}
        a, b, c = (_normal(runs[n]) for n in ("a", "b", "c"))
        if a != b:
            for index, (x, y) in enumerate(zip(a[0], b[0])):
                require(x == y, f"same seed, different experiment at row {index}: {json.dumps(x)[:400]} vs {json.dumps(y)[:400]}")
            require(a[1] == b[1], "same seed, same labels")
            require(a[2] == b[2], "same seed, same final theory")
        require([r["case_digest"] for r in a[0]] != [r["case_digest"] for r in c[0]], "another seed explores differently")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return (f"seed {spec['seed']} twice in separate processes: {len(a[0])} identical rows, labels and final theory; "
            f"seed {spec['other_seed']} differs")


# ---- artifacts --------------------------------------------------------------------------

_LONG: dict[str, Any] = {}


def longrun() -> dict[str, Any]:
    if not _LONG:
        entry = pinned("longrun")
        out = pinned_dir(entry)
        _LONG.update(open_run(out), entry=entry, out=out)
    return _LONG


def check_longrun() -> str:
    T = theory()
    run = longrun()
    records, report, manifest = run["records"], run["report"], run["manifest"]
    spec = C.LONGRUN
    lanes = check_rows(run, run["out"])
    minutes = minutes_between(records[0].created_at, records[-1].created_at)
    require(report.get("status") in ("budget_minutes", "budget_experiments") and report.get("experiments") == len(records)
            and len(records) >= spec["min_records"] and minutes >= spec["min_minutes"],
            f"a run of at least {spec['min_minutes']} minutes and {spec['min_records']} experiments that ended at its budget: "
            f"{report.get('status')}, {len(records)} records over {minutes:.0f} minutes")
    require(tuple(report.get("engines", ())) == spec["engines"] and tuple(manifest["hunter"].get("engines", ())) == spec["engines"],
            f"the long run is on DuckDB: {report.get('engines')}")
    require(manifest["hunter"].get("beta") == T.constants.BETA == report.get("beta"), "the long run used the frozen BETA")
    harness_errors = sum(1 for r in records if r.label.invalid_reason == "harness_error")
    require(harness_errors <= spec["max_harness_error"] * len(records), f"{harness_errors} harness errors in {len(records)} records")
    labels: dict[str, int] = {}
    for r in records:
        labels[r.label.y] = labels.get(r.label.y, 0) + 1
    return (f"{len(records)} experiments over {minutes:.0f} minutes, labels {labels}, lanes {lanes}, "
            f"{len(run['wb'].theory.hypotheses)} hypotheses, {len(run['wb'].families())} families, {harness_errors} harness errors")


def check_sawtooth() -> str:
    from surprise.metrics import curve as M

    run = longrun()
    spec = C.SAWTOOTH
    series = M.surprise_curve(run["records"], window=spec["window"])
    require(len(series) == len(run["records"]) // spec["window"] and all(v is not None for v in series),
            f"every window of {spec['window']} executions has a valid experiment")
    teeth = M.teeth(series, amplitude=spec["amplitude"], width=spec["width"])
    require(len(teeth) >= spec["min_teeth"], f"the curve must rise and fall at least {spec['min_teeth']} times "
            f"by {spec['amplitude']} bits within {spec['width']} windows; teeth at {teeth}; curve {[round(v, 2) for v in series]}")
    require(run["report"].get("teeth") == teeth, "the report shows the same teeth")
    return f"{len(series)} windows, teeth at {teeth}; curve {[round(v, 2) for v in series]}"


def check_duplicates() -> str:
    from surprise.metrics import dups as M

    run = longrun()
    entry = pinned("old")
    out = pinned_dir(entry)
    old_run = json.loads((out / "old_run.json").read_text(encoding="utf-8"))
    new_minutes = minutes_between(run["records"][0].created_at, run["records"][-1].created_at)
    spec = C.DUPLICATES
    require(abs(old_run["wall_s"] / 60.0 - new_minutes) <= spec["budget_tolerance"] * new_minutes,
            f"the same wall-clock budget: old {old_run['wall_s'] / 60.0:.0f} minutes, new {new_minutes:.0f}")
    require(old_run.get("mode") == "no_llm" and old_run.get("engine") == "duckdb", f"the baseline is the old no_llm mode: {old_run}")
    new = M.new_families(run["out"] / "theory")
    old = M.old_reports(out / old_run["run_dir"] / "bugs.jsonl")
    require(len(old) >= spec["min_old_reports"], f"the old run must report at least {spec['min_old_reports']} bugs to compare: {len(old)}")
    rate_new, rate_old = M.duplicate_rate([f["key"] for f in new]), M.duplicate_rate([r["key"] for r in old])
    require(rate_new is not None and rate_old is not None and rate_new < rate_old,
            f"duplicate rate: new {rate_new} over {len(new)} families, old {rate_old} over {len(old)} reports")
    return (f"duplicate rate new {rate_new:.3f} ({len(new)} families, {len({f['key'] for f in new})} distinct identities) "
            f"< old no_llm {rate_old:.3f} ({len(old)} reports, {len({r['key'] for r in old})} distinct) "
            f"on {new_minutes:.0f} minutes each")


def check_recall() -> str:
    from surprise.metrics import recall as M

    entry = pinned("recall")
    out = pinned_dir(entry)
    known = json.loads((out / "known.json").read_text(encoding="utf-8"))
    require(known.get("engines", {}).get("duckdb") == "1.1.3", f"the known list was certified on DuckDB 1.1.3: {known.get('engines')}")
    require(sorted(item["name"] for item in known["items"]) == sorted(C.RECALL_CASES), "every DuckDB family of the M1 table was certified")
    run = open_run(out / "run")
    require(run["manifest"]["environment"]["engines"]["duckdb"] == "1.1.3" and run["report"].get("engines") == ["duckdb"],
            "the recall run targets DuckDB 1.1.3")
    score = M.score(known, out / "run" / "theory")
    stored = json.loads((out / "recall.json").read_text(encoding="utf-8"))
    require(score == stored, "the stored recall report is what score() computes from the run")
    present = [i["name"] for i in known["items"] if i["y"] == "fail"]
    minutes = minutes_between(run["records"][0].created_at, run["records"][-1].created_at)
    return (f"DuckDB 1.1.3: {len(present)} of {len(known['items'])} known reproductions fail there ({present}); "
            f"{len(run['records'])} experiments over {minutes:.0f} minutes recalled {score['recalled']} "
            f"(recall {score['recall']}), missed {score['missed']}")


GROUPS: dict[str, Callable[[], str]] = {
    "no_llm": check_no_llm,
    "constants": check_constants,
    "scoring": check_scoring,
    "operators": check_operators,
    "candidates": check_candidates,
    "lanes": check_lanes,
    "determinism": check_determinism,
    "longrun": check_longrun,
    "sawtooth": check_sawtooth,
    "duplicates": check_duplicates,
    "recall": check_recall,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S8 gate (Hunter and the loop without LLM, M2)")
    parser.add_argument("--only", nargs="+", choices=list(GROUPS), metavar="GROUP",
                        help="run only these groups (the gate proper is all of them)")
    args = parser.parse_args(argv)
    selected = args.only or list(GROUPS)
    failed = 0
    for name in selected:
        started = time.monotonic()
        try:
            detail = GROUPS[name]()
            print(f"[PASS] {name}: {_ascii(detail)} ({time.monotonic() - started:.0f}s)", flush=True)
        except GateFailure as exc:
            failed += 1
            print(f"[FAIL] {name}: {_ascii(exc)}", flush=True)
        except Exception as exc:  # noqa: BLE001 - a crashing check is a failed check
            failed += 1
            print(f"[FAIL] {name}: {type(exc).__name__}: {_ascii(exc)}", flush=True)
    scope = "" if not args.only else f" [only: {', '.join(selected)}]"
    print(f"S08 GATE{scope}: {'PASS' if not failed else 'FAIL'}"
          f" ({len(selected) - failed}/{len(selected)} groups passed)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
