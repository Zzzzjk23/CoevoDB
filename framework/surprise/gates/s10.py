"""S10 gate: the other four LLM roles, and M3 (DF-A to DF-B with every role on).

Usage (from ``framework/``)::

    python -m surprise.gates.s10                         # everything
    python -m surprise.gates.s10 --only prior translator

Exit code 0 = pass. Groups, following the S10 section of SESSIONS.md:

``isolation``       the new role modules load no model client; the loop, the Hunter, the
                    Diagnoser and the harness never import the roles;
``constants``       the S10 role constants and the harness library constants as planned;
``frozen``          the unfreeze the user allowed (2026-10-15): only rewrites.py and
                    equivalent_query.py changed since s09-done-r2, the harness is re-frozen,
                    the three frozen rules give the outputs they gave before;
``library``         the second rewrite layer: templates, the library file, and judgements of
                    library rules (references must agree; a rewrite error is never a bug);
``frame``           the hooks the roles use: the Hunter's prior and extra rules, the run
                    vocabulary, the library environment variable during a run;
``switches``        every role can be switched on alone and makes calls; switched off it makes
                    none and its module is not loaded;
``prior``           exploration prior: unit prices from the source checkouts' history, pseudo
                    counts, Brier calibration;
``translator``      migration translator: one translation per family and engine, phi-checked,
                    settled by the label, its predicted switches checked by bisect;
``vocab_inventor``  vocabulary inventor: triggered by unexpected passes in the confirmed zone,
                    accepted only on held-out records, safe patterns only;
``oracle_inventor`` oracle inventor: rewrite templates accepted by agreement of three or more
                    engines, written to the library the harness reads;
``translator_real`` a real translation (F2 from DuckDB to DataFusion), replayed from its cache;
``m3``              M3: a recorded run on DataFusion 54.0.0 with every role on, from DF-A,
                    replayed from its cache with no network; DF-B reproduced, judged by the
                    identity referee.

The last two read replies the orchestrator recorded once with real calls and committed
under ``gates/s10_llm/``; they fail until then. Tables live in ``s10_cases.py``. Output is
ASCII only. No group makes a network call.
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from . import s09 as G9
from . import s10_cases as C
from .s06 import GateFailure, _ascii, require

FRAMEWORK = Path(__file__).resolve().parents[2]
REPO = FRAMEWORK.parent
LLM_DIR = Path(__file__).resolve().parent / "s10_llm"
FROZEN = Path(__file__).with_name("s04_frozen.json")
LAYERS_OK = {"ast": "ok", "plan": "ok", "data": "ok"}


# ---- modules ------------------------------------------------------------------------------

def roles() -> Any:
    import surprise.roles as R

    return R


def base() -> Any:
    import surprise.roles.base as B

    return B


def runtime() -> Any:
    import surprise.roles.runtime as RT

    return RT


def plugin(name: str) -> Any:
    return importlib.import_module(C.PLUGINS[name])


def theory() -> Any:
    from surprise import theory as T

    return T


def features() -> Any:
    from surprise import features as F

    return F


def rewrites() -> Any:
    from surprise.harness.oracles import rewrites as W

    return W


def tmpdir(tag: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=f"s10-{tag}-"))


def close(a: Any, b: float, tol: float = 1e-9) -> bool:
    return isinstance(a, (int, float)) and not isinstance(a, bool) and abs(float(a) - b) <= tol


def lines_of(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class Script:
    """A transport: per role a reply, a list of replies, or a function of the prompt."""

    def __init__(self, replies: dict[str, Any]) -> None:
        self.replies = {role: (list(r) if isinstance(r, list) else r) for role, r in replies.items()}
        self.calls: list[dict[str, Any]] = []

    def complete(self, *, model: str, prompt: str, temperature: float, max_tokens: int, role: str) -> Any:
        self.calls.append({"model": model, "prompt": prompt, "temperature": temperature,
                           "max_tokens": max_tokens, "role": role})
        reply = self.replies[role]
        if isinstance(reply, list):
            reply = reply.pop(0) if len(reply) > 1 else reply[0]
        if callable(reply):
            reply = reply(prompt)
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return roles().Completion(text=text, input_tokens=len(prompt) // 4, output_tokens=len(text) // 4)

    def by_role(self, role: str) -> list[dict[str, Any]]:
        return [call for call in self.calls if call["role"] == role]


def context(root: Path, transport: Any, *, engines: tuple[str, ...], oracles: tuple[str, ...],
            max_calls: int = 50, readers: Any = None) -> Any:
    """A RoleContext over a fresh gateway and conjecture book under ``root``."""
    R, B, F = roles(), base(), features()
    llm = root / "llm"
    llm.mkdir(parents=True, exist_ok=True)
    gw = R.Gateway(cache_dir=root / "cache", ledger_path=llm / "calls.jsonl", max_calls=max_calls, transport=transport)
    return B.RoleContext(gateway=gw, book=R.ConjectureBook(llm / "conjectures.jsonl"), extract=F.extract,
                         registry=F.default_registry(), readers=R.open_sources() if readers is None else readers,
                         engines=tuple(engines), oracles=tuple(oracles), seed=0, run_dir=root, llm_dir=llm)


def observed(wb: Any, phi: Any, record: Any, outcome: Any, prediction: Any, *, lane: str = "explore",
             op: str = "seed", hypothesis: str | None = None, target: dict | None = None, index: int = 0) -> Any:
    return base().Observed(wb=wb, phi=phi, record=record, outcome=outcome, prediction=prediction, lane=lane, op=op,
                           hypothesis=hypothesis, target=target, index=index)


_SKIPPED = {"status": "skipped", "reason": "not_requested"}


def synthetic_fail(oracle: str, *, fix_set: tuple[str, ...] = (), shape: str = "missing_only") -> Any:
    """A tier-3 fail label the CVE pipeline could have produced (profile ran)."""
    from surprise.harness.contracts import IdentityEvidence, Label

    behavior = {"missing_only": {"missing": 1, "extra": 0}, "extra_only": {"missing": 0, "extra": 1},
                "both": {"missing": 1, "extra": 1}}[shape]
    cve = {"schema": 1, "tier": 3, "isolation": "inline", "attribution": dict(_SKIPPED), "minimize": dict(_SKIPPED),
           "profile": {"status": "ran", "reason": None, "fix_kind": "none" if not fix_set else "optimizer",
                       "fix_set": list(fix_set), "plan_diff": [], "version_ladder": "none", "witness_switches": [],
                       "error_class": None, "behavior_shape": shape, "executions": 3}}
    return Label(y="fail", oracle=oracle, fail_kind="wrong_result", identity=IdentityEvidence(behavior=behavior), cve=cve)


def synthetic_label(y: str, oracle: str) -> Any:
    from surprise.harness.contracts import Label

    if y == "pass":
        return Label(y="pass", oracle=oracle)
    return Label(y="invalid", oracle=oracle, invalid_reason="query_error")


def fake_record(record_id: str, seq: int, case: Any, label: Any, phi: Any) -> Any:
    return SimpleNamespace(record_id=record_id, run_id="s10-gate", seq=seq, case=case, label=label,
                           phi=phi.to_dict(), purpose="explore", spec=None)


def with_library(path: Path | None) -> Callable[[], None]:
    """Point the harness at a library file (or at none). Returns the restore function."""
    name = C.LIBRARY["LIBRARY_ENV"]
    saved = os.environ.get(name)
    if path is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = str(path)

    def restore() -> None:
        if saved is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = saved

    return restore


def write_library(path: Path, rules: dict[str, tuple[str, str]]) -> Path:
    payload = {"schema": C.LIBRARY["LIBRARY_SCHEMA"], "rules": [
        {"rule_id": rule_id, "kind": kind, "template": template, "argument": "gate fixture",
         "proposer": "gate", "acceptance": {"engines": ["gate"], "instances": 1}}
        for rule_id, (kind, template) in rules.items()]}
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return path


def library_case() -> Any:
    from surprise.harness.contracts import SqlCase

    return SqlCase(engine=C.LIBRARY_CASE["engine"], setup=tuple(C.LIBRARY_CASE["setup"]),
                   query=C.LIBRARY_CASE["query"], predicate=C.LIBRARY_CASE["predicate"])


# ---- isolation, constants -------------------------------------------------------------------

def check_isolation() -> str:
    modules = list(G9.C.LLM_MODULES)
    probe = ("import sys, json\n"
             "import surprise.roles, surprise.roles.base, surprise.roles.runtime\n"
             + "".join(f"import {mod}\n" for mod in C.PLUGINS.values())
             + f"print(json.dumps(sorted(m for m in {modules!r} if m in sys.modules)))\n")
    bad = G9.run_probe(probe, env=G9.clean_env())
    require(bad == [], f"importing the new roles must not load a model client or old agent code: {bad}")
    loop_probe = ("import sys, json\n"
                  "import surprise.hunter, surprise.diagnoser, surprise.experiments.loop, surprise.harness.evaluate\n"
                  "import surprise.harness.oracles.rewrites, surprise.harness.oracles.equivalent_query\n"
                  "print(json.dumps(sorted(m for m in sys.modules if m == 'surprise.roles' or m.startswith('surprise.roles.'))))\n")
    loaded = G9.run_probe(loop_probe, env=G9.clean_env())
    require(loaded == [], f"the loop, the Hunter, the Diagnoser and the harness must not import the roles: {loaded}")
    harness = [p.name for p in (FRAMEWORK / "surprise" / "harness").rglob("*.py")
               if "surprise.roles" in p.read_text(encoding="utf-8") or "from ..roles" in p.read_text(encoding="utf-8")
               or "from ...roles" in p.read_text(encoding="utf-8")]
    require(harness == [], f"the label path (harness) never reaches the roles: {harness}")
    for name in C.NEW_ROLES:
        require(callable(getattr(plugin(name), "build", None)), f"{C.PLUGINS[name]} exposes build(ctx)")
    return f"{len(C.PLUGINS)} role modules load no model client; loop, Hunter, Diagnoser and harness never import the roles"


def check_constants() -> str:
    have = roles().constants.as_dict()
    for name, value in C.CONSTANTS.items():
        require(name in have and have[name] == value and type(have[name]) is type(value),
                f"roles constant {name} must be {value!r}, got {have.get(name)!r}")
    for name, value in G9.C.CONSTANTS.items():
        require(have.get(name) == value, f"S9 constant {name} is unchanged: {have.get(name)!r}")
    W = rewrites()
    for name, value in C.LIBRARY.items():
        got = getattr(W, name, None)
        require(got == value and type(got) is type(value), f"harness rewrites.{name} must be {value!r}, got {got!r}")
    require(have["REWRITE_LIBRARY_ENV"] == W.LIBRARY_ENV, "the roles and the harness name the same library variable")
    require(tuple(runtime().ROLES) == C.ROLES, f"runtime.ROLES: {getattr(runtime(), 'ROLES', None)}")
    require(dict(base().PLUGINS) == C.PLUGINS, f"base.PLUGINS: {getattr(base(), 'PLUGINS', None)}")
    for name in ("PRIOR_TIER", "TRANSLATOR_TIER", "VOCAB_TIER", "ORACLE_TIER"):
        require(have[name] in have["TIERS"], f"{name} names a gateway tier")
    return f"{len(C.CONSTANTS)} S10 constants as planned, S9 constants unchanged, library constants {sorted(C.LIBRARY)}"


# ---- the unfreeze -----------------------------------------------------------------------------

def check_frozen() -> str:
    from surprise.harness import constants as HC
    from surprise.harness.manifest import verify_manifest

    proc = subprocess.run(["git", "diff", "--name-only", C.UNFREEZE_BASE, "--", "framework/surprise/harness"],
                          cwd=REPO, capture_output=True, text=True, timeout=120)
    require(proc.returncode == 0, f"git diff failed: {proc.stderr[-400:]}")
    changed = sorted(line.strip() for line in proc.stdout.splitlines() if line.strip())
    require(set(changed) <= set(C.HARNESS_CHANGED),
            f"the unfreeze allows only {list(C.HARNESS_CHANGED)}; changed since {C.UNFREEZE_BASE}: {changed}")
    untracked = subprocess.run(["git", "status", "--porcelain", "--", "framework/surprise/harness"], cwd=REPO,
                               capture_output=True, text=True, timeout=120).stdout.strip()
    require(untracked == "", f"no uncommitted change under the harness: {untracked[:300]}")
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    problems = verify_manifest(frozen)
    require(problems == [], f"the harness is re-frozen (gates/s04_frozen.json): {problems[:3]}")
    require(len(frozen["harness"]["files"]) == 51, f"the frozen list still covers 51 files: {len(frozen['harness']['files'])}")
    require(frozen.get("constants") == HC.as_dict(), "the frozen harness constants are unchanged")
    W = rewrites()
    require(tuple(W.RULES) == C.FROZEN_RULES, f"the frozen layer is the three rules: {tuple(W.RULES)}")
    tmp = tmpdir("frozen")
    lib = write_library(tmp / "rewrites.json", C.LIBRARY_RULES)
    for setting in (None, lib):
        restore = with_library(setting)
        try:
            for (query, rule), want in C.FROZEN_RULE_OUTPUTS.items():
                got = W.apply_rule(query, rule)
                require(got == want, f"frozen rule {rule} on {query!r} (library {'set' if setting else 'unset'}): {got!r}")
        finally:
            restore()
    return (f"harness changes since {C.UNFREEZE_BASE}: {[Path(p).name for p in changed]}; re-frozen and verified; "
            f"{len(C.FROZEN_RULE_OUTPUTS)} frozen-rule outputs unchanged with and without a library")


def check_library() -> str:
    from surprise.harness.cve.certify import certify

    W = rewrites()
    for kind, template in C.TEMPLATES_OK:
        require(W.template_problem(kind, template) is None, f"usable template refused: {kind} {template!r}")
    for kind, template in C.TEMPLATES_BAD:
        reason = W.template_problem(kind, template)
        require(isinstance(reason, str) and reason, f"bad template accepted: {kind} {template!r}")
    for query, kind, template, want in C.APPLY_CASES:
        got = W.apply_template(query, kind, template)
        if want is None:
            require(got is None, f"apply_template must decline {query!r} / {template!r}: {got!r}")
        else:
            require(isinstance(got, str) and W.same_statement(got, want), f"apply_template({query!r}, {template!r}) = {got!r}")
    tmp = tmpdir("library")
    lib = write_library(tmp / "rewrites.json", C.LIBRARY_RULES)
    restore = with_library(None)
    try:
        require(W.load_library() == {} and not W.is_library_rule("llm:wrap_sub"), "no variable, no library")
    finally:
        restore()
    loaded = W.load_library(lib)
    require(sorted(loaded) == sorted(C.LIBRARY_RULES)
            and all(loaded[r]["kind"] == k and loaded[r]["template"] == t for r, (k, t) in C.LIBRARY_RULES.items()),
            f"the library file loads: {sorted(loaded)}")
    good = json.loads(lib.read_text(encoding="utf-8"))
    broken = {
        "not_json": "{",
        "schema": json.dumps(dict(good, schema=2)),
        "prefix": json.dumps(dict(good, rules=[dict(good["rules"][0], rule_id="wrap_sub")])),
        "frozen_name": json.dumps(dict(good, rules=[dict(good["rules"][0], rule_id="double_negation")])),
        "duplicate": json.dumps(dict(good, rules=[good["rules"][0], good["rules"][0]])),
        "no_acceptance": json.dumps(dict(good, rules=[dict(good["rules"][0], acceptance={})])),
        "bad_template": json.dumps(dict(good, rules=[dict(good["rules"][0], template="DELETE FROM t")])),
        "bad_kind": json.dumps(dict(good, rules=[dict(good["rules"][0], kind="sql_rewrite")])),
    }
    for tag, text in broken.items():
        path = tmp / f"{tag}.json"
        path.write_text(text, encoding="utf-8")
        require(W.load_library(path) == {}, f"a malformed library ({tag}) is refused as a whole")
    case = library_case()
    seen: dict[str, str] = {}
    restore = with_library(lib)
    try:
        for rule, (y, reason, premise) in C.LIBRARY_EXPECT.items():
            label = certify(case, "equivalent_query", rewrite_rule=rule)
            require((label.y, label.invalid_reason) == (y, reason),
                    f"{rule}: expected {(y, reason)}, got {(label.y, label.invalid_reason)} {label.detail}")
            require(label.detail.get("layer") == "library" and label.detail.get("rule") == rule,
                    f"{rule}: the label says it came from the library layer: {label.detail}")
            if premise is not None:
                require(label.detail.get("premise") == premise, f"{rule}: premise {label.detail.get('premise')!r}, want {premise!r}")
            else:
                refs = label.detail.get("references") or {}
                agree = [e for e, v in refs.items() if v == "agree"]
                require(len(agree) >= C.LIBRARY["LIBRARY_MIN_REFERENCES"] and "disagree" not in refs.values(),
                        f"{rule}: at least two references agree before the target is judged: {refs}")
                require(isinstance(label.detail.get("rewritten"), str), f"{rule}: the rewritten query is recorded")
            seen[rule] = label.y if premise is None else f"{label.invalid_reason}/{premise}"
        unknown = certify(case, "equivalent_query", rewrite_rule="llm:not_in_library")
        require((unknown.y, unknown.invalid_reason) == ("invalid", "untrusted_rewrite"), "a rule not in the library is untrusted")
        frozen = certify(case, "equivalent_query", rewrite_rule="double_negation")
        require(frozen.y == "pass" and frozen.detail == C.FROZEN_DETAIL, f"a frozen rule is judged as before: {frozen.detail}")
        paired = certify(case, "equivalent_query", rewrite_rule="llm:wrap_sub", paired_query="SELECT 1")
        require((paired.y, paired.invalid_reason) == ("invalid", "untrusted_rewrite"), "a paired query that is not the product is untrusted")
    finally:
        restore()
    restore = with_library(None)
    try:
        absent = certify(case, "equivalent_query", rewrite_rule="llm:wrap_sub")
        require((absent.y, absent.invalid_reason) == ("invalid", "untrusted_rewrite"), "without the library a llm: rule is untrusted")
    finally:
        restore()
    return (f"{len(C.TEMPLATES_OK)} usable and {len(C.TEMPLATES_BAD)} refused templates; {len(broken)} malformed "
            f"libraries refused; judgements {seen}; frozen rule unchanged; no library, no trust")


# ---- the frame: hooks the roles use ------------------------------------------------------------

class FakePrior:
    def __init__(self, pseudo: tuple[float, float]) -> None:
        self.pseudo_counts = pseudo
        self.prepared: list[tuple[int, tuple[str, ...]]] = []

    def prepare(self, wb: Any, units: Any, *, index: int) -> None:
        self.prepared.append((index, tuple(units)))

    def pseudo(self, unit: str) -> tuple[float, float] | None:
        return self.pseudo_counts


def check_frame() -> str:
    from surprise.hunter import Hunter
    from surprise.hunter import scoring as S
    from surprise.hunter.operators import RULES as FROZEN, oracle_options
    from surprise.theory.constants import RESIDUAL_PRIOR_FAILS, RESIDUAL_PRIOR_TESTS

    from . import s04 as G4

    T, F = theory(), features()
    # scoring with a prior
    require(close(S.optimistic_rate(0, 0), S.optimistic_rate(0, 0, prior_fails=RESIDUAL_PRIOR_FAILS,
                                                                 prior_tests=RESIDUAL_PRIOR_TESTS)),
            "the default prior is the theory's residual prior")
    require(close(S.optimistic_rate(0, 0, prior_fails=30.0, prior_tests=100.0), 0.5), "a 0.3 prior caps at 0.5")
    require(close(S.uncertainty(0, 0, False, prior_fails=30.0, prior_tests=100.0), 1.0), "U of a capped prior is one bit")
    tmp = tmpdir("frame")
    wb = T.Workbench.create(tmp / "theory")
    example = F.make_phi("datafusion", ("ast:set_op:intersect_all", "ast:stmt:select"), LAYERS_OK)
    plain = S.score(wb, example, "cross_dbms", beta=1.0, probes={}, units=frozenset())
    primed = S.score(wb, example, "cross_dbms", beta=1.0, probes={}, units=frozenset(), prior=FakePrior((30.0, 100.0)))
    none = S.score(wb, example, "cross_dbms", beta=1.0, probes={}, units=frozenset(), prior=FakePrior(None))
    require(plain.prediction.zone == "unexplored" and close(primed.U, 1.0) and primed.U > plain.U
            and close(none.U, plain.U) and close(none.value, plain.value), f"the prior moves U only: {plain.U} {primed.U} {none.U}")
    # extra rules for the equivalent-query oracle
    case = G4.load("F1")
    base_opts = oracle_options(case, ["equivalent_query"])
    more = oracle_options(case, ["equivalent_query"], extra_rules=("llm:wrap_sub",))
    require(base_opts == [("equivalent_query", r) for r in FROZEN] and more == base_opts + [("equivalent_query", "llm:wrap_sub")],
            f"extra rules follow the frozen ones: {more}")
    # the Hunter asks the prior once per round, with the index of the choice
    fake = FakePrior((30.0, 100.0))
    hunt = Hunter(engines=("duckdb",), oracles=("tlp", "equivalent_query"), seed=0, prior=fake,
                  extra_rules=lambda: ("llm:wrap_sub",))
    try:
        cands = hunt.candidates(wb)
        require(any(c.rule == "llm:wrap_sub" for c in cands), "the Hunter offers the extra rules to explore candidates")
        choice = hunt.choose(wb)
    finally:
        hunt.close()
    require(choice is not None and fake.prepared and all(i == choice.index for i, _ in fake.prepared)
            and 1 <= len(fake.prepared) <= choice.pool["rounds"]
            and all(u and all(isinstance(x, str) and x.count("|") == 4 for x in u) for _, u in fake.prepared),
            f"prepare(wb, units, index=...) at most once per round: {[(i, len(u)) for i, u in fake.prepared]}")
    require(choice.scored.prediction.zone != "unexplored" or close(choice.scored.U, 1.0), "the chosen candidate was scored with the prior")
    # the run's vocabulary
    from surprise.features.vocabulary import FeatureDef
    from surprise.experiments import loop

    registry = F.default_registry()
    registry.register(FeatureDef(feature_id=C.VOCAB_GOOD["id"], kind="leaf", parent=C.VOCAB_PARENT, layer="ast",
                                 description="the two sides of EXCEPT ALL read different tables", source="llm:gate",
                                 definition={"kind": "regex", "pattern": C.VOCAB_GOOD["pattern"]}, accepted=False,
                                 acceptance=None))
    registry.accept(C.VOCAB_GOOD["id"], {"gate": True})
    vocab = tmp / "vocabulary.json"
    registry.save(vocab)
    out = tmp / "vocab-run"
    boot = [{"case": G4.load("DF-A").to_dict(), "oracle": "cross_dbms", "rule": None}]
    loop.run(out, seed=0, engines=("datafusion",), oracles=("cross_dbms",), max_experiments=0, bootstrap=boot,
             vocabulary=str(vocab))
    config = json.loads((out / "config.json").read_text(encoding="utf-8"))
    from surprise.harness.ledger import Ledger

    ledger = Ledger(out / "ledger.sqlite")
    try:
        records = ledger.records(run_id="loop-s0")
    finally:
        ledger.close()
    require(config.get("vocabulary") == str(vocab), f"config.json names the vocabulary: {config.get('vocabulary')}")
    require(len(records) == 1 and C.VOCAB_GOOD["id"] in records[0].phi["features"],
            "a run started with the vocabulary extracts the invented feature (DF-A reads t and u)")
    opened = T.Workbench.open(out / "theory", registry=F.Registry.load(vocab))
    require(len(opened.theory.hypotheses) == 1 and C.VOCAB_GOOD["id"] in opened.theory.hypotheses[0].specific,
            "the theory of that run speaks the extended vocabulary")
    plain_out = tmp / "plain-run"
    loop.run(plain_out, seed=0, engines=("datafusion",), oracles=("cross_dbms",), max_experiments=0, bootstrap=boot)
    require("vocabulary" not in json.loads((plain_out / "config.json").read_text(encoding="utf-8")),
            "without a vocabulary config.json is as before")
    return (f"prior moves U {plain.U:.3f} -> {primed.U:.3f}; extra rules offered; prepare once per round "
            f"({len(fake.prepared)} rounds); vocabulary run extracts {C.VOCAB_GOOD['id']}")


# ---- switches -----------------------------------------------------------------------------------

def _units_in(prompt: str) -> list[str]:
    return re.findall(r"^UNIT (\S+)$", prompt, flags=re.MULTILINE)


def price_of(unit: str) -> float:
    construct = unit.split("|")[2]
    return C.PRIOR_PRICES.get(construct, C.PRIOR_DEFAULT_PRICE)


def prior_reply(prompt: str) -> dict[str, Any]:
    return {"prediction": [{"unit": u, "p_fail": price_of(u), "why": "scripted"} for u in _units_in(prompt)]}


def translation_reply(prompt: str) -> dict[str, Any]:
    from . import s04 as G4

    dfa = G4.load("DF-A")
    return {"setup": list(dfa.setup), "query": dfa.query, "predicate": None,
            "prediction": {"expect": "pass", "switches": [], "behavior": None, "why": "scripted"}}


def vocab_reply(pattern: str, *, feature_id: str = C.VOCAB_GOOD["id"], parent: str = C.VOCAB_PARENT) -> dict[str, Any]:
    return {"feature": {"id": feature_id, "parent": parent, "description": "two different tables around EXCEPT ALL",
                        "pattern": pattern},
            "prediction": {"matches": ["P1"], "excludes": ["C1"], "why": "scripted"}}


def oracle_reply(rules: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rules = [dict(r) for r in (C.ORACLE_SCRIPT if rules is None else rules)]
    return {"rules": rules, "prediction": [{"rule": r["name"], "equivalent_on": list(C.CONSTANTS["ORACLE_ACCEPT_ENGINES"]),
                                            "why": "scripted"} for r in rules]}


def scripted_all() -> Script:
    # The trigger does not cover the DF-A failure, so the conjecture is registered (its bet feeds the
    # implementer) but proposes no revise: h1 keeps its two positives and two contradictions, which is
    # what the vocabulary inventor waits for (measured with every role off).
    conj = {"mechanism": "EXCEPT ALL is planned as an anti join", "trigger": ["ast:set_op:intersect_all"],
            "prediction": [{"required": ["ast:set_op:intersect_all", "data:setop:left_has_dups"], "forbidden": [],
                            "data_properties": [], "expect": "fail", "why": "scripted"}]}
    from . import s04 as G4

    dfa = G4.load("DF-A")
    impl = {"setup": list(dfa.setup), "query": "SELECT v FROM t INTERSECT ALL SELECT v FROM u", "predicate": None,
            "prediction": {"expect": "fail", "why": "scripted"}}
    return Script({"implementer": impl, "conjecturer": conj, "prior": prior_reply, "translator": translation_reply,
                   "vocab_inventor": vocab_reply(C.VOCAB_GOOD["pattern"]), "oracle_inventor": oracle_reply(C.ORACLE_SCRIPT[:1])})


def switch_run(tag: str, on: tuple[str, ...], *, max_experiments: int) -> tuple[dict[str, Any], Script, Path]:
    from surprise.experiments import loop

    script = scripted_all()
    base_dir = tmpdir(tag)
    boot = [{"case": {"engine": "datafusion", "setup": list(setup), "query": query, "predicate": None},
             "oracle": "cross_dbms", "rule": None} for _y, setup, query in C.VOCAB_BOOT]
    llm = {"roles": list(on), "cache": str(base_dir / "cache"), "max_calls": 60, "network": False, "transport": script}
    out = base_dir / "run"
    report = loop.run(out, seed=0, engines=("datafusion", "duckdb"), oracles=("cross_dbms", "equivalent_query"),
                      max_experiments=max_experiments, bootstrap=boot, llm=llm)
    return report, script, out


def check_switches() -> str:
    name = C.CONSTANTS["REWRITE_LIBRARY_ENV"]
    before = os.environ.get(name)
    report, script, out = switch_run("all", C.ROLES, max_experiments=3)
    require(os.environ.get(name) == before, "the library variable is restored after the run")
    by_role = report["llm"]["calls"]["by_role"]
    missing = [r for r in C.ROLES if by_role.get(r, {}).get("calls", 0) < 1]
    require(not missing, f"with every role on, every role is called: missing {missing}; {sorted(by_role)}")
    require(sorted({c["role"] for c in script.calls}) == sorted(C.ROLES), "every scripted reply was asked for")
    rows = lines_of(out / "progress.jsonl")
    require(all(set(C.NEW_ROLES) <= set(row["llm"]) for row in rows), "each progress row records every new role's step")
    for book in C.BOOKS:
        require((out / "llm" / book).is_file(), f"llm/{book} is written")
    require(report["status"] == "budget_experiments", f"the run ends at its budget: {report['status']}")
    counts = {r: by_role[r]["calls"] for r in C.ROLES}
    for role in C.ROLES:
        rest = tuple(r for r in C.ROLES if r != role)
        rep, scr, run_out = switch_run(f"off-{role}", rest, max_experiments=1)
        got = rep["llm"]["calls"]["by_role"]
        require(role not in got and not scr.by_role(role), f"{role} off: no call ({got.get(role)})")
        require(all(row.get("role") != role for row in lines_of(run_out / "llm" / "calls.jsonl")), f"{role} off: no ledger line")
    for role in C.NEW_ROLES:
        rest = [r for r in C.ROLES if r != role]
        probe = ("import sys, json, tempfile\n"
                 "from pathlib import Path\n"
                 "from surprise.roles.runtime import build_roles\n"
                 "from surprise.features import extract, default_registry\n"
                 "d = Path(tempfile.mkdtemp())\n"
                 f"rs = build_roles({{'roles': {rest!r}, 'cache': str(d / 'c'), 'max_calls': 0, 'network': False}}, "
                 "run_dir=d / 'run', extract=extract, registry=default_registry(), engines=('datafusion',), seed=0, "
                 "oracles=('cross_dbms',))\n"
                 "rs.close()\n"
                 f"print(json.dumps({C.PLUGINS[role]!r} in sys.modules))\n")
        require(G9.run_probe(probe, env=G9.clean_env()) is False, f"{role} off: {C.PLUGINS[role]} is never imported")
    return f"all on: calls {counts}; each role off: no call, no ledger line, plugin module not loaded"


# ---- exploration prior ------------------------------------------------------------------------

def prior_event(unit: str, y: str, *, zone: str = "unexplored", seq: int = 1) -> Any:
    from surprise.harness.contracts import SqlCase

    label = synthetic_fail("cross_dbms") if y == "fail" else synthetic_label(y, "cross_dbms")
    case = SqlCase(engine="datafusion", setup=(), query="SELECT 1", predicate=None)
    phi = features().make_phi("datafusion", ("ast:stmt:select",), LAYERS_OK)
    record = fake_record(f"prior-r{seq}", seq, case, label, phi)
    prediction = SimpleNamespace(zone=zone, unit=unit, hypothesis_id=None, p_fail_valid=0.01, p_invalid=0.1)
    outcome = SimpleNamespace(observation=SimpleNamespace(triage="no_information", opened=None), owner=None)
    return observed(None, phi, record, outcome, prediction, index=seq)


def check_prior() -> str:
    P = plugin("prior")
    R, T = roles(), theory()
    k = C.CONSTANTS["PRIOR_STRENGTH"]
    w0 = C.CONSTANTS["PRIOR_INITIAL_WEIGHT"]
    ref = C.PRIOR_REFERENCE_RATE
    evidence = tuple(P.prior_evidence(C.PRIOR_UNITS, R.open_sources()))
    require(evidence and all(line.startswith("EVIDENCE ") for line in evidence)
            and any(line.startswith("EVIDENCE datafusion ") for line in evidence),
            f"evidence lines come from the DataFusion checkout: {evidence[:2]}")
    require(tuple(P.prior_evidence(C.PRIOR_UNITS, R.open_sources())) == evidence, "the evidence is deterministic")
    require(not any(word in line for line in evidence for word in ("manual_findings", "FAMILY_LEDGER", "recall_repros")),
            "the project's own bug ledgers are not evidence (they are what recall is measured against)")
    root = tmpdir("prior")
    script = Script({"prior": prior_reply})
    role = P.build(context(root, script, engines=("datafusion",), oracles=("cross_dbms",)))
    require(role.name == "prior", "the role's name")
    wb = T.Workbench.create(root / "theory")
    units = list(C.PRIOR_UNITS)
    per_call = C.CONSTANTS["PRIOR_UNITS_PER_CALL"]
    role.prepare(wb, units, index=1)
    role.prepare(wb, units, index=1)
    require(len(script.calls) == 1, f"one call per choice: {len(script.calls)}")
    first = script.calls[0]
    require(_units_in(first["prompt"]) == sorted(units)[:per_call], "the first call prices the first units in sorted order")
    require(first["model"] == R.constants.TIERS[C.CONSTANTS["PRIOR_TIER"]]
            and first["temperature"] == C.CONSTANTS["PRIOR_TEMPERATURE"] and first["max_tokens"] == C.CONSTANTS["PRIOR_MAX_TOKENS"],
            "the prior's tier, temperature and token cap")
    require("EVIDENCE " in first["prompt"] and "loop-s" not in first["prompt"], "the prompt carries evidence and no run ids")
    role.prepare(wb, units, index=2)
    require(len(script.calls) == 2 and _units_in(script.calls[1]["prompt"]) == sorted(units)[per_call:],
            "the next choice prices the rest")
    role.prepare(wb, units, index=3)
    require(len(script.calls) == 2, "every unit priced: no more calls")
    for unit in units:
        p_eff = w0 * price_of(unit) + (1 - w0) * ref
        got = role.pseudo(unit)
        require(got is not None and close(got[0], p_eff * k, 1e-9) and close(got[1], k),
                f"pseudo counts of {unit}: {got}, want {(p_eff * k, k)}")
    require(role.pseudo("datafusion|tlp|plain|scan|plain") is None, "an unpriced unit has no pseudo counts")
    # replies that cannot be used leave the unit unpriced
    odd = list(C.PRIOR_UNITS[:3])
    script2 = Script({"prior": {"prediction": [{"unit": odd[0], "p_fail": 1.5, "why": "x"},
                                               {"unit": odd[1], "p_fail": "high", "why": "x"},
                                               {"unit": "datafusion|tlp|nowhere|scan|plain", "p_fail": 0.2, "why": "x"},
                                               {"unit": odd[2], "p_fail": 0.0, "why": "x"}]}})
    role2 = P.build(context(tmpdir("prior2"), script2, engines=("datafusion",), oracles=("cross_dbms",)))
    role2.prepare(wb, odd, index=1)
    require(role2.pseudo(odd[0]) is None and role2.pseudo(odd[1]) is None and role2.pseudo(odd[2]) is not None
            and role2.pseudo("datafusion|tlp|nowhere|scan|plain") is None, "out-of-range, non-numeric and unasked prices are dropped")
    # Brier calibration on a bad prior: 0.3 for a unit that never fails
    unit = next(u for u in units if u.split("|")[2] == "set_op_all")
    minimum = C.CONSTANTS["PRIOR_MIN_SETTLED"]
    role.observe(prior_event(unit, "invalid", seq=900))
    role.observe(prior_event(unit, "pass", zone="confirmed", seq=901))
    role.observe(prior_event("datafusion|tlp|plain|scan|plain", "pass", seq=902))
    require(role.brier()["settled"] == 0, "invalid, confirmed-zone and unpriced experiments settle nothing")
    for i in range(minimum - 1):
        role.observe(prior_event(unit, "pass", seq=i + 1))
    require(close(role.weight(), w0), f"below {minimum} settled the weight stays {w0}: {role.weight()}")
    role.observe(prior_event(unit, "pass", seq=minimum))
    brier = role.brier()
    p = price_of(unit)
    require(brier["settled"] == minimum and close(brier["llm"], p * p, 1e-12) and close(brier["reference"], ref * ref, 1e-12),
            f"Brier of the prior and of the reference: {brier}")
    require(close(role.weight(), 0.0) and close(role.pseudo(unit)[0], ref * k, 1e-9),
            f"a prior worse than the reference loses its weight: {role.weight()}")
    # a useful prior keeps weight
    script3 = Script({"prior": {"prediction": [{"unit": unit, "p_fail": 0.5, "why": "x"}]}})
    role3 = P.build(context(tmpdir("prior3"), script3, engines=("datafusion",), oracles=("cross_dbms",)))
    role3.prepare(wb, [unit], index=1)
    for i in range(minimum):
        role3.observe(prior_event(unit, "fail" if i % 2 == 0 else "pass", seq=i + 1))
    b3 = role3.brier()
    want_ref = (minimum // 2 * (1 - ref) ** 2 + minimum // 2 * ref ** 2) / minimum
    want_w = max(0.0, min(1.0, 1.0 - 0.25 / want_ref))
    require(close(b3["llm"], 0.25, 1e-12) and close(b3["reference"], want_ref, 1e-12) and close(role3.weight(), want_w, 1e-12),
            f"weight = clip(1 - Brier/Brier_ref, 0, 1): {b3}, {role3.weight()}")
    book = lines_of(root / "llm" / "prior.jsonl")
    require(book and {row.get("type") for row in book} >= {"price", "settle"}, f"the prior's book: {sorted({r.get('type') for r in book})}")
    step = role.step()
    require(isinstance(step, dict), "step() is a dict")
    return (f"{len(units)} units priced in 2 calls; evidence from the checkouts ({len(evidence)} lines); "
            f"bad prior weight -> 0.0 after {minimum}; useful prior weight {role3.weight():.3f}")


# ---- migration translator ---------------------------------------------------------------------

def dfa_bench(tag: str) -> tuple[Any, Any, Any]:
    """A copy of the DF-A workbench of the S9 gate, with the DF-A record and its outcome."""
    ctx = G9.dfa()
    return G9.bench_copy(tag), ctx["record"], ctx["outcome"]


def translator_with(tag: str, reply: Any, *, engines: tuple[str, ...] = ("datafusion", "duckdb")
                    ) -> tuple[Any, Script, Any, Any, Path]:
    P = plugin("translator")
    wb, record, outcome = dfa_bench(tag)
    root = tmpdir(tag)
    script = Script({"translator": reply})
    role = P.build(context(root, script, engines=engines, oracles=("cross_dbms",)))
    phi = features().Phi.from_dict(record.phi)
    prediction = SimpleNamespace(zone="unexplored", unit="", hypothesis_id=None, p_fail_valid=0.01, p_invalid=0.1)
    role.observe(observed(wb, phi, record, outcome, prediction, lane="bootstrap", op="bootstrap"))
    return role, script, wb, record, root


def translate_fail_reply(switches: list[str]) -> dict[str, Any]:
    reply = translation_reply("")
    reply["prediction"] = {"expect": "fail", "switches": switches, "behavior": "missing_only", "why": "scripted"}
    return reply


def settle_with(role: Any, wb: Any, candidate: Any, label: Any, seq: int) -> dict[str, Any]:
    phi = features().extract(candidate.case)
    record = fake_record(f"tr-r{seq}", seq, candidate.case, label, phi)
    prediction = SimpleNamespace(zone="unexplored", unit="", hypothesis_id=None, p_fail_valid=0.01, p_invalid=0.1)
    outcome = SimpleNamespace(observation=SimpleNamespace(triage="no_information", opened=None), owner=None)
    role.observe(observed(wb, phi, record, outcome, prediction, lane=C.TRANSLATE_LANE, op=C.TRANSLATOR_OP,
                          hypothesis=candidate.hypothesis_id, target=candidate.target, index=seq))
    return role.translations()[-1]


def check_translator() -> str:
    R = roles()
    role, script, wb, record, root = translator_with("tr-ok", translation_reply)
    require(role.name == "translator", "the role's name")
    sources = role.sources()
    require(len(sources) == 1, "one candidate source")
    src = sources[0]
    cands = src.candidates(wb, index=1, round=1)
    require(len(script.calls) == 1 and len(cands) == 1, f"one translation at the first choice: {len(script.calls)} calls, {len(cands)}")
    cand = cands[0]
    prompt = script.calls[0]["prompt"]
    require(cand.case.engine == "duckdb" and cand.oracle == "cross_dbms" and cand.lane == C.TRANSLATE_LANE
            and cand.op == C.TRANSLATOR_OP and cand.hypothesis_id == wb.theory.hypotheses[0].hypothesis_id
            and cand.parent == record.record_id and isinstance(cand.target, dict) and cand.target.get("engine") == "duckdb",
            f"a translate candidate on DuckDB naming its hypothesis and parent: {cand.lane} {cand.case.engine} {cand.parent}")
    require("EXCEPT ALL" in prompt.upper() and "duckdb" in prompt and "datafusion" in prompt
            and record.record_id not in prompt and wb.theory.hypotheses[0].hypothesis_id not in prompt.split(),
            "the prompt carries both engines and the case, and no ids")
    require(script.calls[0]["model"] == R.constants.TIERS[C.CONSTANTS["TRANSLATOR_TIER"]]
            and script.calls[0]["max_tokens"] == C.CONSTANTS["TRANSLATOR_MAX_TOKENS"], "the translator's tier and token cap")
    again = src.candidates(wb, index=1, round=2) + src.candidates(wb, index=2, round=1)
    require(len(script.calls) == 1 and all(c.case == cand.case for c in again), "one family and engine is translated once")
    from surprise.features.spec import check_spec

    require(check_spec(features().extract(cand.case), theory().Spec.from_dict(cand.target)).ok,
            "the translated case meets its spec")
    row = settle_with(role, wb, cand, synthetic_label("pass", "cross_dbms"), 2)
    require((row.get("state"), row.get("identity")) == ("kept", None), f"pass as predicted: kept ({row})")
    outcomes = {}
    for tag, switches, label, want in (
        ("tr-match", ["filter_pushdown"], synthetic_fail("cross_dbms", fix_set=("filter_pushdown",)), ("kept", "match")),
        ("tr-mismatch", ["filter_pushdown"], synthetic_fail("cross_dbms", fix_set=("join_order",)), ("kept", "mismatch")),
        ("tr-broken", ["filter_pushdown"], synthetic_label("pass", "cross_dbms"), ("broken", None)),
        ("tr-void", ["filter_pushdown"], synthetic_label("invalid", "cross_dbms"), ("void", None)),
    ):
        r2, s2, wb2, _rec, _root = translator_with(tag, translate_fail_reply(switches))
        made = r2.sources()[0].candidates(wb2, index=1, round=1)
        require(len(made) == 1, f"{tag}: one candidate")
        settled = settle_with(r2, wb2, made[0], label, 2)
        require((settled.get("state"), settled.get("identity")) == want, f"{tag}: {settled}")
        outcomes[tag] = want
    r3, s3, wb3, _rec, _root = translator_with("tr-badswitch", translate_fail_reply(["no_such_optimizer"]))
    made = r3.sources()[0].candidates(wb3, index=1, round=1)
    rows = [row for row in r3.translations() if row.get("type") == "translation"]
    require(made == [] and len(s3.calls) == C.CONSTANTS["TRANSLATOR_ATTEMPTS"] and rows and rows[-1].get("status") == "bad_switch",
            f"an unknown switch is refused after the retry: {rows[-1] if rows else None}")
    unmet = translation_reply("")
    unmet["query"] = "SELECT v FROM t UNION ALL SELECT v FROM u"
    r4, s4, wb4, _rec, _root = translator_with("tr-unmet", [unmet, translation_reply("")])
    made = r4.sources()[0].candidates(wb4, index=1, round=1)
    require(len(made) == 1 and len(s4.calls) == 2 and "ast:set_op:except_all" in s4.calls[1]["prompt"],
            "a translation that misses the spec is retried with the missing features")
    single, one_script, one_wb, _rec, _root = translator_with("tr-one", translation_reply, engines=("datafusion",))
    require(single.sources()[0].candidates(one_wb, index=1, round=1) == [] and len(one_script.calls) == 0,
            "with one engine there is nothing to translate")
    return f"DF-A family -> DuckDB translated once; settled {outcomes}; bad switch refused; unmet spec retried"


# ---- vocabulary inventor ------------------------------------------------------------------------

def vocab_run(tag: str, reply: Any) -> tuple[Any, Script, Path, list[Any]]:
    from surprise.harness.contracts import SqlCase

    T, F = theory(), features()
    P = plugin("vocab_inventor")
    root = tmpdir(tag)
    script = Script({"vocab_inventor": reply})
    role = P.build(context(root, script, engines=(C.VOCAB_ENGINE,), oracles=(C.VOCAB_ORACLE,)))
    wb = T.Workbench.create(root / "theory")
    phi = F.make_phi(C.VOCAB_ENGINE, C.VOCAB_PHI, LAYERS_OK)
    calls_after: list[int] = []
    for seq, (record_id, y, query) in enumerate(C.VOCAB_RECORDS, start=1):
        case = SqlCase(engine=C.VOCAB_ENGINE, setup=C.VOCAB_SETUP, query=query, predicate=None)
        label = synthetic_fail(C.VOCAB_ORACLE) if y == "fail" else synthetic_label("pass", C.VOCAB_ORACLE)
        prediction = wb.predict(phi, C.VOCAB_ORACLE)
        outcome = wb.observe(phi, label, record_id, prediction=prediction)
        record = fake_record(record_id, seq, case, label, phi)
        role.observe(observed(wb, phi, record, outcome, prediction, index=seq))
        role.after(wb, record, outcome)
        calls_after.append(len(script.calls))
    return role, script, root, calls_after


def check_vocab_inventor() -> str:
    R, F = roles(), features()
    role, script, root, calls_after = vocab_run("vocab-good", vocab_reply(C.VOCAB_GOOD["pattern"]))
    require(role.name == "vocab_inventor", "the role's name")
    require(calls_after == [0, 0, 0, 0, 1], f"called once, at the second unexpected pass with two positives: {calls_after}")
    prompt = script.calls[0]["prompt"]
    queries = {rid: q for rid, _y, q in C.VOCAB_RECORDS}
    require(all(queries[rid] in prompt for rid in C.VOCAB_TRAIN) and not any(queries[rid] in prompt for rid in C.VOCAB_HELD),
            "the prompt shows the training records and hides the held-out ones")
    require(not any(rid in prompt for rid, _y, _q in C.VOCAB_RECORDS), "the prompt carries no record ids")
    require(script.calls[0]["model"] == R.constants.TIERS[C.CONSTANTS["VOCAB_TIER"]], "the inventor's tier")
    book = [row for row in lines_of(root / "llm" / "vocabulary.jsonl") if row.get("type") == "proposal"]
    require(len(book) == 1 and book[0].get("status") == "accepted" and book[0].get("feature_id") == C.VOCAB_GOOD["id"],
            f"the good feature is accepted: {book}")
    vocab = root / "llm" / "vocabulary.json"
    loaded = F.Registry.load(vocab)
    definition = loaded.get(C.VOCAB_GOOD["id"])
    require(definition.accepted and definition.parent == C.VOCAB_PARENT and definition.layer == "ast"
            and definition.definition == {"kind": "regex", "pattern": C.VOCAB_GOOD["pattern"]}
            and {"family", "train", "holdout", "corpus_share"} <= set(definition.acceptance or {}),
            f"vocabulary.json holds the accepted feature with its acceptance: {definition}")
    require(tuple(role.accepted()) == (C.VOCAB_GOOD["id"],), "accepted() lists it")
    hit, _ = F.extract_ast(queries["vocab-r1"], C.VOCAB_ENGINE, loaded)
    miss, _ = F.extract_ast(queries["vocab-r2"], C.VOCAB_ENGINE, loaded)
    require(C.VOCAB_GOOD["id"] in hit and C.VOCAB_GOOD["id"] not in miss, "the extractor applies the accepted feature")
    reasons: dict[str, str] = {}
    for tag, (pattern, step) in C.VOCAB_BAD.items():
        started = time.monotonic()
        bad_role, bad_script, bad_root, _calls = vocab_run(f"vocab-{tag}", vocab_reply(pattern))
        rows = [row for row in lines_of(bad_root / "llm" / "vocabulary.jsonl") if row.get("type") == "proposal"]
        require(len(bad_script.calls) == 1 and rows and rows[-1].get("status") == "rejected" and rows[-1].get("reason") == step,
                f"{tag}: refused at {step}: {rows[-1] if rows else None}")
        require(tuple(bad_role.accepted()) == (), f"{tag}: accepted() stays empty")
        bad_vocab = bad_root / "llm" / "vocabulary.json"
        require(not bad_vocab.is_file() or not F.Registry.load(bad_vocab).known(C.VOCAB_GOOD["id"]),
                f"{tag}: nothing enters the vocabulary file")
        if tag == "catastrophic":
            require(time.monotonic() - started < C.CONSTANTS["VOCAB_SCAN_TIMEOUT_S"] + 60, "the scan is cut off at its timeout")
        reasons[tag] = step
    bad_def, _s, def_root, _c = vocab_run("vocab-def", vocab_reply(C.VOCAB_GOOD["pattern"], feature_id="data:setop:two_tables",
                                                                    parent="data:setop"))
    rows = [row for row in lines_of(def_root / "llm" / "vocabulary.jsonl") if row.get("type") == "proposal"]
    require(rows and rows[-1].get("reason") == "definition", f"a non-AST feature is refused at definition: {rows[-1] if rows else None}")
    return f"accepted {C.VOCAB_GOOD['id']} on held-out records; refused {reasons} and a data-layer id; prompt hides the held-out records"


# ---- oracle inventor ---------------------------------------------------------------------------

def check_oracle_inventor() -> str:
    from surprise.harness.cve.certify import certify

    R, T, W = roles(), theory(), rewrites()
    P = plugin("oracle_inventor")
    root = tmpdir("oracle")
    script = Script({"oracle_inventor": [oracle_reply(), oracle_reply(C.ORACLE_SCRIPT[:1]),
                                         {"rules": [], "prediction": []}]})
    role = P.build(context(root, script, engines=("duckdb",), oracles=("cross_dbms", "equivalent_query")))
    require(role.name == "oracle_inventor", "the role's name")
    wb = T.Workbench.create(root / "theory")
    outcome = SimpleNamespace(observation=SimpleNamespace(triage="no_information", opened=None), owner=None)

    def after(n: int) -> None:
        role.after(wb, SimpleNamespace(record_id=f"o-r{n}", seq=n), outcome)

    after(1)
    require(len(script.calls) == 1, f"called at the first experiment: {len(script.calls)}")
    prompt = script.calls[0]["prompt"]
    require(all(rule in prompt for rule in C.FROZEN_RULES) and "{q}" in prompt and "{p}" in prompt and "o-r1" not in prompt,
            "the prompt names the frozen rules and the two template kinds, and no ids")
    require(script.calls[0]["model"] == R.constants.TIERS[C.CONSTANTS["ORACLE_TIER"]], "the inventor's tier")
    require(tuple(role.rules()) == C.ORACLE_ACCEPTED, f"accepted rules: {role.rules()}")
    book = {row.get("rule_id"): row for row in lines_of(root / "llm" / "rewrites.jsonl") if row.get("type") == "proposal"}
    good = book.get("llm:wrap_sub") or {}
    instances = (good.get("acceptance") or {}).get("instances") or []
    require(good.get("status") == "accepted" and len(instances) == C.CONSTANTS["ORACLE_ACCEPT_INSTANCES"]
            and all(len(item.get("agree") or []) >= C.CONSTANTS["ORACLE_ACCEPT_MIN_ENGINES"] and not item.get("disagree")
                    for item in instances),
            f"accepted on {C.CONSTANTS['ORACLE_ACCEPT_INSTANCES']} corpus instances, each with three or more agreeing engines: {good}")
    require((book.get("llm:first_row") or {}).get("reason") == "disagree", f"a non-equivalent template is refused: {book.get('llm:first_row')}")
    require((book.get("llm:drop_t") or {}).get("reason") == "template", f"an unusable template is refused: {book.get('llm:drop_t')}")
    library = W.load_library(root / "llm" / "rewrites.json")
    require(sorted(library) == list(C.ORACLE_ACCEPTED) and library["llm:wrap_sub"]["kind"] == "query_wrap",
            f"the library file is the harness's format and holds only the accepted rule: {sorted(library)}")
    for n in range(2, C.CONSTANTS["ORACLE_EVERY"] + 1):
        after(n)
    require(len(script.calls) == 1, "no call before the next period")
    for n in range(C.CONSTANTS["ORACLE_EVERY"] + 1, 4 * C.CONSTANTS["ORACLE_EVERY"] + 2):
        after(n)
    require(len(script.calls) == C.CONSTANTS["ORACLE_CALLS_PER_RUN"], f"at most {C.CONSTANTS['ORACLE_CALLS_PER_RUN']} calls a run: {len(script.calls)}")
    dup = [row for row in lines_of(root / "llm" / "rewrites.jsonl") if row.get("type") == "proposal" and row.get("reason") == "duplicate"]
    require(dup, "a template already in the library is refused as a duplicate")
    quiet = Script({"oracle_inventor": oracle_reply()})
    q_role = P.build(context(tmpdir("oracle-off"), quiet, engines=("duckdb",), oracles=("cross_dbms",)))
    q_role.after(wb, SimpleNamespace(record_id="o-q1", seq=1), outcome)
    require(quiet.calls == [], "without the equivalent-query oracle there is nothing to invent for")
    restore = with_library(root / "llm" / "rewrites.json")
    try:
        label = certify(library_case(), "equivalent_query", rewrite_rule="llm:wrap_sub")
    finally:
        restore()
    require(label.y == "pass" and label.detail.get("layer") == "library", f"the harness judges the invented rule: {label.y} {label.detail}")
    return (f"accepted {list(C.ORACLE_ACCEPTED)} on {len(instances)} instances; refused disagree, template, duplicate; "
            f"{len(script.calls)} calls in {4 * C.CONSTANTS['ORACLE_EVERY'] + 1} experiments; judged by the harness: {label.y}")


# ---- pinned real replies ------------------------------------------------------------------------

def pinned_dir(name: str) -> Path:
    path = LLM_DIR / name
    require(path.is_dir(), f"gates/s10_llm/{name} is missing: the orchestrator records it with real calls after the merge")
    return path


def copy_cache(name: str) -> Path:
    source = pinned_dir(name) / "cache"
    require(source.is_dir() and any(source.rglob("*.json")), f"gates/s10_llm/{name}/cache holds the recorded replies")
    target = tmpdir(f"pin-{name}") / "cache"
    shutil.copytree(source, target)
    return target


def check_translator_real() -> str:
    from surprise.harness.evaluate import evaluate_final
    from surprise.harness.ledger import Ledger
    from surprise.harness.manifest import build_manifest

    from . import s04 as G4

    R, T, F = roles(), theory(), features()
    P = plugin("translator")
    spec = C.TRANSLATOR_REAL
    expected = lines_of(pinned_dir("translator") / "translations.jsonl")
    cache = copy_cache("translator")
    root = cache.parent
    wb = T.Workbench.create(root / "theory")
    ledger = Ledger(root / "ledger.sqlite")
    run_id = "s10-translator"
    refuse = G9.Refuse()
    try:
        ledger.start_run(run_id, T.extend_manifest(build_manifest(run_id)))
        case = G4.load(spec["case"])
        phi = F.extract(case)
        prediction = wb.predict(phi, spec["oracle"])
        record = evaluate_final(case, spec["oracle"], ledger=ledger, run_id=run_id, purpose="bootstrap", phi=phi.to_dict(),
                                theory_version=wb.theory.version, p_t=prediction.p_fail_valid, diagnose=True)
        outcome = wb.observe(phi, record.label, record.record_id, prediction=prediction)
        require(record.label.y == "fail" and outcome.observation.opened is not None, f"{spec['case']} opens a family on DuckDB")
        gw = R.Gateway(cache_dir=cache, ledger_path=None, max_calls=0, transport=refuse)
        ctx = base().RoleContext(gateway=gw, book=R.ConjectureBook(root / "llm" / "conjectures.jsonl"), extract=F.extract,
                                 registry=F.default_registry(), readers=R.open_sources(), engines=(spec["source"], spec["target"]),
                                 oracles=(spec["oracle"],), seed=0, run_dir=root, llm_dir=root / "llm")
        (root / "llm").mkdir(exist_ok=True)
        role = P.build(ctx)
        role.observe(observed(wb, phi, record, outcome, prediction, lane="bootstrap", op="bootstrap"))
        cands = role.sources()[0].candidates(wb, index=1, round=1)
        require(refuse.calls == 0 and gw.network_calls == 0, "the translation replays with no network call")
        require(len(cands) == 1 and cands[0].case.engine == spec["target"], f"one translation to {spec['target']}: {len(cands)}")
        cand = cands[0]
        phi2 = F.extract(cand.case)
        prediction2 = wb.predict(phi2, cand.oracle)
        rec2 = evaluate_final(cand.case, cand.oracle, ledger=ledger, run_id=run_id, purpose=cand.lane, phi=phi2.to_dict(),
                              theory_version=wb.theory.version, p_t=prediction2.p_fail_valid, diagnose=True,
                              rewrite_rule=cand.rule)
        outcome2 = wb.observe(phi2, rec2.label, rec2.record_id, prediction=prediction2)
        role.observe(observed(wb, phi2, rec2, outcome2, prediction2, lane=cand.lane, op=cand.op,
                              hypothesis=cand.hypothesis_id, target=cand.target, index=1))
    finally:
        ledger.close()
    got = lines_of(root / "llm" / "translations.jsonl")
    require(got == expected, "the replay writes the recorded translation and settlement")
    row = next(r for r in got if r.get("type") == "translation")
    settle = next((r for r in got if r.get("type") == "settle"), {})
    return (f"{spec['case']} ({spec['source']}) -> {spec['target']}: status {row.get('status')}, expect "
            f"{row.get('expect')}, switches {row.get('switches')}; label {rec2.label.y}; settled {settle.get('state')} "
            f"identity {settle.get('identity')}")


def check_m3() -> str:
    from surprise.harness.cve.certify import certify
    from surprise.harness.cve.shape import behavior_shape
    from surprise.harness.ledger import Ledger
    from surprise.metrics.dups import identity_key, new_families

    from . import s04 as G4

    T, F = theory(), features()
    pinned = pinned_dir("m3")
    expected_dir = pinned / "expected"
    cache = copy_cache("m3")
    base_dir = cache.parent
    boot = [{"case": G4.load(item["case"]).to_dict(), "oracle": item["oracle"], "rule": item["rule"]}
            for item in C.M3_RUN["bootstrap"]]
    (base_dir / "bootstrap.json").write_text(json.dumps(boot), encoding="utf-8")
    out = base_dir / "run"
    argv = [sys.executable, "-m", "surprise.experiments.loop", "--out", str(out), "--seed", str(C.M3_RUN["seed"]),
            "--max-experiments", str(C.M3_RUN["max_experiments"]), "--bootstrap", str(base_dir / "bootstrap.json"),
            "--llm-cache", str(cache), "--llm-offline"]
    for engine in C.M3_RUN["engines"]:
        argv += ["--engine", engine]
    for oracle in C.M3_RUN["oracles"]:
        argv += ["--oracle", oracle]
    for role in C.M3_RUN["roles"]:
        argv += ["--llm", role]
    proc = subprocess.run(argv, cwd=FRAMEWORK, capture_output=True, text=True, timeout=3600, env=G9.clean_env())
    require(proc.returncode == 0, f"the replay run failed: {proc.stderr[-800:]}")
    got, want = G9.rows_of(out / "progress.jsonl"), G9.rows_of(expected_dir / "progress.jsonl")
    for index, (a, b) in enumerate(zip(got, want)):
        require(a == b, f"replayed row {index} differs in {[k for k in b if a.get(k) != b.get(k)]}")
    require(len(got) == len(want), f"{len(got)} replayed rows, {len(want)} recorded")
    for book in C.BOOKS:
        if book == "calls.jsonl":
            continue
        require(lines_of(out / "llm" / book) == lines_of(expected_dir / book), f"llm/{book} replays line for line")
    for name in ("rewrites.json", "vocabulary.json"):
        if (expected_dir / name).is_file():
            require((out / "llm" / name).is_file() and json.loads((out / "llm" / name).read_text(encoding="utf-8"))
                    == json.loads((expected_dir / name).read_text(encoding="utf-8")), f"llm/{name} replays")
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    recorded = json.loads((expected_dir / "report.json").read_text(encoding="utf-8"))
    for key in C.REPORT_COMPARED:
        require(report.get(key) == recorded.get(key), f"report {key}: {report.get(key)} vs recorded {recorded.get(key)}")
    calls = lines_of(out / "llm" / "calls.jsonl")
    require(calls and all(c["source"] == "cache" and c["status"] != "miss" for c in calls),
            f"every call of the replay came from the cache: {sorted({(c['source'], c['status']) for c in calls})}")
    require([c["key"] for c in calls] == [c["key"] for c in lines_of(expected_dir / "calls.jsonl")],
            "the replay asks the same questions in the same order")
    by_role: dict[str, int] = {}
    for c in calls:
        by_role[c["role"]] = by_role.get(c["role"], 0) + 1
    # DF-B by the identity referee
    keys = {}
    for name in ("DF-A", "DF-B"):
        label = certify(G4.load(name), C.DF_B["oracle"], diagnose=True)
        require(label.y == "fail", f"{name} still fails on this machine")
        profile = label.cve.get("profile") or {}
        keys[name] = identity_key("datafusion", profile.get("fix_set") or [], label.fail_kind, label.identity.error_class,
                                  behavior_shape(label.identity.behavior))
    require(keys["DF-A"] != keys["DF-B"], f"the referee tells DF-A and DF-B apart: {keys}")
    ledger = Ledger(out / "ledger.sqlite")
    try:
        records = ledger.records(run_id=f"loop-s{C.M3_RUN['seed']}")
    finally:
        ledger.close()
    rows = {row["record_id"]: row for row in lines_of(out / "progress.jsonl")}
    wb = T.Workbench.open(out / "theory")
    registry = F.default_registry()
    first = records[0]
    # Families are read from the theory as it stands at the end: an accepted revise replaces the
    # hypothesis a record opened, so the record's current owner names its family.
    first_owner = wb.owner_of(first.record_id)
    dfa_family = None if first_owner is None else wb.family_of(first_owner)
    require(first.label.y == "fail" and rows[first.record_id]["opened"] is not None and dfa_family is not None,
            "the bootstrap DF-A fails, opens a family, and is owned at the end")
    hits = []
    for record in records[1:]:
        if record.label.y != "fail" or record.label.oracle != C.DF_B["oracle"] or record.case.engine != "datafusion":
            continue
        closed = registry.closure(record.phi["features"])
        if not all(f in closed for f in C.DF_B["features"]):
            continue
        profile = record.label.cve.get("profile") or {}
        key = identity_key("datafusion", profile.get("fix_set") or [], record.label.fail_kind,
                           record.label.identity.error_class, behavior_shape(record.label.identity.behavior))
        if key == keys["DF-B"]:
            hits.append(record)
    require(hits, f"some failure in the run has DF-B's identity ({keys['DF-B']}) and features {C.DF_B['features']}")
    hit = hits[0]
    row = rows[hit.record_id]
    require(row["lane"] in C.DF_B["role_lanes"], f"DF-B was reached through a role's lane: {row['lane']}")
    owner = wb.owner_of(hit.record_id)
    require((row["opened"] or row["owner"]) is not None and owner is not None and wb.family_of(owner) != dfa_family,
            "DF-B opened or joined a family when it ran, and that family is not DF-A's")
    families = {fam["family"]: fam for fam in new_families(out / "theory")}
    require(families.get(wb.family_of(owner), {}).get("key") == keys["DF-B"], "the referee keys that family as DF-B")
    chain = "-"
    if row["lane"] == "bet":
        conj = [c for c in lines_of(out / "llm" / "conjectures.jsonl") if c.get("type") == "conjecture"
                and any(p["spec"] == row["target"] for p in c.get("predictions") or [])]
        require(conj, "the bet that reached DF-B is a registered prediction")
        chain = f"bet from {conj[0]['conjecture_id']} on {conj[0]['hypothesis_id']}"
    return (f"{len(got)} experiments and {len(calls)} calls replayed from the cache, identical; calls {by_role}; "
            f"DF-B ({keys['DF-B']}) reached at experiment {hit.seq} via {row['lane']} ({chain}); lanes {report.get('lanes')}")


GROUPS: dict[str, Callable[[], str]] = {
    "isolation": check_isolation,
    "constants": check_constants,
    "frozen": check_frozen,
    "library": check_library,
    "frame": check_frame,
    "switches": check_switches,
    "prior": check_prior,
    "translator": check_translator,
    "vocab_inventor": check_vocab_inventor,
    "oracle_inventor": check_oracle_inventor,
    "translator_real": check_translator_real,
    "m3": check_m3,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S10 gate (the other four LLM roles, M3)")
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
    print(f"S10 GATE{scope}: {'PASS' if not failed else 'FAIL'}"
          f" ({len(selected) - failed}/{len(selected)} groups passed)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
