"""S6 gate: the core of the theory T = (H, R, K^v).

Usage (from ``framework/``)::

    python -m surprise.gates.s06                        # everything
    python -m surprise.gates.s06 --only constants language vspace

Exit code 0 = pass. Groups, following the S6 section of SESSIONS.md:

``constants``    0.95, 0.5, the residual and validity priors, the triage
                 thresholds and the cap on G have the frozen values;
``language``     conjunctions of phi literals with the class hierarchy:
                 reduction, coverage, the least general generalisation and the
                 minimal specialisations;
``vspace``       positive examples generalise S, negative examples specialise
                 G, on whole sequences; the invariants of a version space hold;
``hypothesis``   the hypothesis contract, the deterministic start of a new
                 family from a CVE profile, the tier-2 attribution request;
``identity``     a failure is a positive example only when its identity agrees;
``residual``     R: per-unit counts and the residual failure rate;
``validity``     K^v: the invalid rate by experiment class and oracle;
``predict``      zones, P_T and surprise;
``triage``       the six-way triage by the size of the surprise;
``theory``       ``Theory.observe`` on scripted experiments with hand-made
                 labels: every rule above applied together, deterministically;
``manifest``     the constants reach the run manifest without touching the
                 frozen harness;
``walkthrough``  the deterministic part of the DF-A -> DF-B case of the
                 framework document, on the real engines, with a hand-written
                 h2 in place of the LLM.

Tables live in ``s06_cases.py``. ``--only`` exists so a work package can run
the groups it delivers; the gate proper is all groups. PostgreSQL reference:
COEVO_REFERENCE_PG_DSN or local port 55432 (see HANDOFF). Output is ASCII only.
"""
from __future__ import annotations

import argparse
import ast
import dataclasses
import json
import math
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from . import s06_cases as C

FRAMEWORK = Path(__file__).resolve().parents[2]
FROZEN_S04 = Path(__file__).with_name("s04_frozen.json")
ORACLE = "cross_dbms"
ENGINE = "datafusion"
# The theory decides nothing by asking a model, and it does not reach into the old code base.
FORBIDDEN_IMPORTS = ("llm", "coevo", "agents", "evolution", "openai", "anthropic", "httpx", "requests", "surprise.gates",
                     "surprise.roles", "surprise.hunter", "surprise.diagnoser")


class GateFailure(Exception):
    """A check did not hold; the message says what and why."""


def require(condition: Any, message: str) -> None:
    if not condition:
        raise GateFailure(message)


def expect_raises(kind: type[BaseException] | tuple, call: Callable[[], Any], what: str) -> None:
    try:
        call()
    except kind:
        return
    except Exception as exc:  # noqa: BLE001 - the wrong exception is the finding
        raise GateFailure(f"{what}: raised {type(exc).__name__}: {exc}") from exc
    raise GateFailure(f"{what}: no error raised")


def _ascii(text: Any) -> str:
    return str(text).encode("ascii", "backslashreplace").decode("ascii")


def close(got: Any, expected: float, tolerance: float = 1e-9) -> bool:
    return isinstance(got, float) and abs(got - expected) <= tolerance


def bits(probability: float) -> float:
    return -math.log2(probability)


def theory_api() -> Any:
    from surprise import theory

    return theory


def features_api() -> Any:
    from surprise import features

    return features


# ---- fixtures: hand-made phi, labels and hypotheses ---------------------------

def phi(name_or_features: Any, *, engine: str = ENGINE, layers: dict[str, str] | None = None) -> Any:
    features = C.PHI[name_or_features] if isinstance(name_or_features, str) else name_or_features
    return features_api().make_phi(engine, features, dict(C.ALL_OK if layers is None else layers))


def profile_of(name: str, label_fields: tuple) -> dict[str, Any]:
    from surprise.harness.cve.shape import behavior_shape

    evidence = C.PROFILES[name]
    return {"status": "ran", "reason": None, "fix_kind": evidence["fix_kind"], "fix_set": list(evidence["fix_set"]),
            "plan_diff": list(evidence["plan_diff"]), "version_ladder": evidence["ladder"],
            "witness_switches": list(evidence["witness"]), "error_class": label_fields[2],
            "behavior_shape": behavior_shape(label_fields[3]), "executions": 13}


def fail_label(name: str, *, attribution: tuple[str, bool] | None = None, oracle: str | None = None) -> Any:
    """A fail label the CVE pipeline could have produced: tier 3 when it has a profile, tier 2 when attributed."""
    from surprise.harness.contracts import IdentityEvidence, Label

    fields = C.FAILS[name]
    label_oracle, fail_kind, error_class, behavior, switches, profile_name = fields
    skipped = {"status": "skipped", "reason": "not_requested"}
    cve: dict[str, Any] = {"schema": 1, "tier": 1, "isolation": "inline", "attribution": dict(skipped),
                           "minimize": dict(skipped), "profile": dict(skipped)}
    if attribution is not None:
        cve["attribution"] = {"status": "ran", "reason": None, "hypothesis_id": attribution[0],
                              "method": "profile", "consistent": attribution[1], "executions": 0}
        cve["tier"] = 2
    if profile_name is not None:
        cve["profile"] = profile_of(profile_name, fields)
        cve["tier"] = 3
    return Label(y="fail", oracle=oracle or label_oracle, fail_kind=fail_kind,
                 identity=IdentityEvidence(switches=switches, error_class=error_class, behavior=dict(behavior)), cve=cve)


def pass_label(oracle: str = ORACLE) -> Any:
    from surprise.harness.contracts import Label

    return Label(y="pass", oracle=oracle)


def invalid_label(reason: str = "query_error", oracle: str = ORACLE) -> Any:
    from surprise.harness.contracts import Label

    return Label(y="invalid", oracle=oracle, invalid_reason=reason)


def hand_hypothesis(specific: tuple[str, ...], general: tuple[tuple[str, ...], ...], *, hypothesis_id: str = "h-test",
                    identity: str = "h_missing", engine: str = ENGINE, oracle: str = ORACLE) -> Any:
    interventions, fail_kind, error_class, shape = C.IDENTITIES[identity]
    return theory_api().Hypothesis(
        hypothesis_id=hypothesis_id, engine=engine, interventions=interventions, plan_delta=(), versions={},
        specific=specific, general=general, positives=(), negatives=(), source="hand-written", status="active",
        oracle=oracle, fail_kind=fail_kind, error_class=error_class, behavior_shape=shape)


def tuples(general: Any) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(member) for member in general)


# ---- constants -----------------------------------------------------------------

def check_constants() -> str:
    from surprise.harness import constants as harness_constants
    from surprise.theory import constants

    got = constants.as_dict()
    require(got == C.CONSTANTS, f"theory constants are {got}, expected {C.CONSTANTS}")
    for name, value in C.CONSTANTS.items():
        require(getattr(constants, name) == value and type(getattr(constants, name)) is type(value),
                f"constants.{name} is {getattr(constants, name)!r}, expected {value!r}")
    got["P_CONFIRMED"] = 0.0
    require(constants.as_dict() == C.CONSTANTS, "as_dict() must return a detached copy")
    require(not set(C.CONSTANTS) & set(harness_constants.as_dict()),
            "theory constants do not live among the frozen harness constants")
    prior = C.CONSTANTS["RESIDUAL_PRIOR_FAILS"] / C.CONSTANTS["RESIDUAL_PRIOR_TESTS"]
    low, high = C.CONSTANTS["TRIAGE_LOW_BITS"], C.CONSTANTS["TRIAGE_HIGH_BITS"]
    magnitudes = {
        "unexplored fail": bits(prior), "confirmed pass": bits(1 - C.CONSTANTS["P_CONFIRMED"]),
        "pending": bits(C.CONSTANTS["P_PENDING"]), "confirmed fail": bits(C.CONSTANTS["P_CONFIRMED"]),
        "unexplored pass": bits(1 - prior),
    }
    expected = {"unexplored fail": 6.6, "confirmed pass": 4.3, "pending": 1.0, "confirmed fail": 0.07, "unexplored pass": 0.01}
    for what, value in expected.items():
        require(abs(magnitudes[what] - value) < 0.05, f"{what}: {magnitudes[what]:.4f} bits, the framework document says about {value}")
    require(magnitudes["confirmed fail"] < low <= magnitudes["pending"] < high <= magnitudes["confirmed pass"]
            and magnitudes["unexplored pass"] < low and magnitudes["unexplored fail"] >= high,
            f"the thresholds {low} / {high} must separate the five magnitudes {magnitudes}")
    # features.spec imports theory.contracts and the theory imports the features: either order must load
    for order in ("import surprise.features, surprise.theory", "import surprise.theory, surprise.features",
                  "import surprise.theory.contracts, surprise.features.spec, surprise.theory",
                  "import surprise.harness.evaluate, surprise.theory"):
        run = subprocess.run([sys.executable, "-c",
                              order + "; from surprise.theory import constants; print(sorted(constants.as_dict())[0])"],
                             cwd=FRAMEWORK, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120.0,
                             encoding="utf-8", errors="replace")
        require(run.returncode == 0 and "P_CONFIRMED" in run.stdout,
                f"`{order}` in a fresh process: {_ascii(run.stderr.strip()[-300:])}")
    shown = ", ".join(f"{magnitudes[k]:.2f}" for k in expected)
    return (f"{len(C.CONSTANTS)} constants as frozen; magnitudes {shown} bits, split at {low} and {high}; "
            "features and theory import in either order")


# ---- language ------------------------------------------------------------------

def check_language() -> str:
    T = theory_api()
    registry = features_api().default_registry()
    for ids, expected in C.REDUCE:
        got = T.reduce_conjunction(ids)
        require(got == expected and isinstance(got, tuple), f"reduce_conjunction({ids}) is {got!r}, expected {expected!r}")
        require(T.reduce_conjunction(got) == got and T.reduce_conjunction(tuple(reversed(ids))) == got,
                f"reduce_conjunction({ids}) must be idempotent and ignore the order")
        require(T.reduce_conjunction(list(ids), registry) == got, "reduce_conjunction takes any sequence and a registry")
    for bad in C.REDUCE_BAD:
        expect_raises(ValueError, lambda b=bad: T.reduce_conjunction(b), f"reduce_conjunction({bad!r})")
    for conjunction, name, expected in C.COVERS:
        got = T.covers(conjunction, phi(name))
        require(got is expected, f"covers({conjunction}, {name}) is {got!r}, expected {expected!r}")
    expect_raises(ValueError, lambda: T.covers(("ast:no_such_feature",), phi("x1")), "covers with an unknown id")
    for specific, name, expected in C.GENERALIZE:
        got = T.generalize(specific, phi(name))
        require(got == expected, f"generalize({specific}, {name}) is {got!r}, expected {expected!r}")
        require(T.covers(got, phi(name)), f"generalize({specific}, {name}) must cover the positive example")
        closure = registry.closure(specific)
        require(all(literal in closure for literal in got),
                f"generalize({specific}, {name}) must be more general than what it started from")
        require(T.generalize(got, phi(name)) == got, f"generalize({specific}, {name}) must be a fixed point")
    for general, specific, name, expected in C.SPECIALIZE:
        got = tuples(T.specialize(general, specific, phi(name)))
        require(got == expected, f"specialize({general}, {name}) is {got!r}, expected {expected!r}")
        require(not any(T.covers(member, phi(name)) for member in got),
                f"specialize({general}, {name}): no member may still cover the negative example")
    expect_raises(ValueError, lambda: T.specialize(C.TOP, C.S_HAND, phi("x8")),
                  "specialize with a negative example inside the specific boundary")
    return (f"{len(C.REDUCE)} reductions, {len(C.COVERS)} coverage checks, {len(C.GENERALIZE)} generalisations, "
            f"{len(C.SPECIALIZE)} specialisations; {len(C.REDUCE_BAD) + 2} malformed calls rejected")


# ---- vspace --------------------------------------------------------------------

def check_invariants(T: Any, hypothesis: Any, positives: list[Any], negatives: list[Any], where: str) -> None:
    registry = features_api().default_registry()
    specific = tuple(hypothesis.specific)
    general = tuples(hypothesis.general)
    require(T.reduce_conjunction(specific) == specific, f"{where}: S is not in reduced form: {specific}")
    require(list(general) == sorted(set(general), key=lambda member: (len(member), member)),
            f"{where}: G must be ordered by size, then by text, without repeats: {general}")
    closure = registry.closure(specific)
    for member in general:
        require(T.reduce_conjunction(member) == member, f"{where}: G member is not in reduced form: {member}")
        require(all(literal in closure for literal in member), f"{where}: G member {member} is not more general than S {specific}")
    for a in general:
        for b in general:
            if a != b:
                require(not all(literal in registry.closure(b) for literal in a),
                        f"{where}: G member {b} is covered by the more general member {a}")
    for example in positives:
        require(T.covers(specific, example), f"{where}: S {specific} no longer covers a positive example")
    for example in negatives:
        require(not any(T.covers(member, example) for member in general),
                f"{where}: a G member still covers a negative example")


def run_sequence(T: Any, name: str) -> int:
    specific, general, steps = C.SEQUENCES[name]
    hypothesis = hand_hypothesis(specific, general)
    positives: list[Any] = []
    negatives: list[Any] = []
    for index, (kind, phi_name, outcome, specific_after, general_after) in enumerate(steps, start=1):
        where = f"sequence {name} step {index} ({kind}{phi_name})"
        example = phi(phi_name)
        before = hypothesis
        apply = T.apply_positive if kind == "+" else T.apply_negative
        update = apply(hypothesis, example, f"r{index}")
        hypothesis = update.hypothesis
        require(update.outcome == outcome, f"{where}: outcome is {update.outcome!r}, expected {outcome!r}")
        require(tuple(hypothesis.specific) == specific_after, f"{where}: S is {tuple(hypothesis.specific)}, expected {specific_after}")
        require(tuples(hypothesis.general) == general_after, f"{where}: G is {tuples(hypothesis.general)}, expected {general_after}")
        require(before.specific == specific if index == 1 else True, f"{where}: the input hypothesis must not be mutated")
        recorded = f"r{index}"
        if outcome in ("duplicate", "generalized"):
            positives.append(example)
            require(recorded in hypothesis.positives and recorded not in hypothesis.negatives, f"{where}: E+ must gain {recorded}")
        elif outcome == "specialized":
            negatives.append(example)
            require(recorded in hypothesis.negatives and recorded not in hypothesis.contradictions,
                    f"{where}: E- must gain {recorded}")
        elif outcome == "contradiction":
            require(recorded in hypothesis.negatives and recorded in hypothesis.contradictions,
                    f"{where}: a pass inside S is kept in E- and listed as a contradiction")
        else:
            require(hypothesis == before, f"{where}: an example outside G leaves the hypothesis as it was")
        check_invariants(T, hypothesis, positives, negatives, where)
        again = apply(before, example, f"r{index}")
        require(again.hypothesis == hypothesis and again.outcome == outcome, f"{where}: the same update twice must agree")
    return len(steps)


def check_vspace() -> str:
    T = theory_api()
    steps = sum(run_sequence(T, name) for name in C.SEQUENCES)

    hypothesis = hand_hypothesis(C.S_HAND, C.TOP)
    for name, expected in (("x1", "confirmed"), ("x8", "confirmed"), ("x3", "pending"), ("plain", "pending")):
        require(T.position(hypothesis, phi(name), ORACLE) == expected, f"position of {name} under the fresh h2 must be {expected}")
    narrowed = hand_hypothesis(C.S_HAND, ((C.L_DUPS,),))
    for name, expected in (("x1", "confirmed"), ("x4", "pending"), ("x3", "outside"), ("plain", "outside")):
        require(T.position(narrowed, phi(name), ORACLE) == expected, f"position of {name} with G = left_has_dups must be {expected}")
    require(T.position(narrowed, phi("x1"), "tlp") == "out_of_scope"
            and T.position(narrowed, phi("x1", engine="duckdb"), ORACLE) == "out_of_scope",
            "a hypothesis says nothing about another oracle or another engine")
    # a phi that lacks a layer S talks about can neither confirm nor refute
    partial = phi((C.EXC_ALL, C.SELECT, C.SRC, C.HJ), layers=C.NO_DATA)
    ast_only = phi((C.EXC_ALL, C.SELECT), layers=C.AST_ONLY)
    for example in (partial, ast_only):
        require(T.position(narrowed, example, ORACLE) == "undetermined", "S mentions the data layer; without it the position is undetermined")
        for apply in (T.apply_positive, T.apply_negative):
            update = apply(narrowed, example, "r9")
            require(update.outcome == "undetermined" and update.hypothesis == narrowed,
                    "an undetermined example must not change the hypothesis")
    ast_hypothesis = hand_hypothesis((C.EXC_ALL,), C.TOP)
    require(T.position(ast_hypothesis, ast_only, ORACLE) == "confirmed",
            "a hypothesis that only mentions the ast layer can be judged on an ast-only phi")
    require(T.converged(hand_hypothesis(C.S_HAND, (C.S_HAND,))) and not T.converged(hypothesis) and not T.converged(narrowed),
            "converged() means G has shrunk onto S")

    # the cap on G
    cap = C.CONSTANTS["VS_MAX_GENERAL"]
    hypothesis = hand_hypothesis(tuple(sorted(C.CAP_LEAVES)), C.TOP, engine="duckdb")
    for count, features in enumerate(C.CAP_NEGATIVES, start=1):
        update = T.apply_negative(hypothesis, phi(features, engine="duckdb"), f"n{count}")
        hypothesis = update.hypothesis
        require(update.outcome == "specialized", f"cap negative {count}: outcome {update.outcome!r}")
        if 2 ** count <= cap:
            require(tuples(hypothesis.general) == C.cap_general(count) and hypothesis.truncated is False,
                    f"cap negative {count}: G must hold all {2 ** count} minimal specialisations")
        else:
            require(tuples(hypothesis.general) == C.cap_general(count, keep=cap) and hypothesis.truncated is True,
                    f"cap negative {count}: G holds the first {cap} members in canonical order and is marked truncated, "
                    f"got {len(hypothesis.general)} members, truncated={hypothesis.truncated}")

    # random sequences: the invariants hold whatever comes, and the result does not depend on the run
    rng = random.Random(6)
    names = sorted(C.PHI)
    checked = 0
    for round_index in range(40):
        seed_name = rng.choice(names)
        hypothesis = hand_hypothesis(tuple(sorted(C.PHI[seed_name])), C.TOP)
        positives, negatives = [phi(seed_name)], []
        script = [(rng.choice("+-"), rng.choice(names)) for _ in range(12)]
        for step, (kind, phi_name) in enumerate(script):
            example = phi(phi_name)
            update = (T.apply_positive if kind == "+" else T.apply_negative)(hypothesis, example, f"q{step}")
            if update.outcome in ("duplicate", "generalized"):
                positives.append(example)
            elif update.outcome == "specialized":
                negatives.append(example)
            hypothesis = update.hypothesis
            # a later generalisation may swallow an earlier negative only by first dropping every G member: it cannot
            check_invariants(T, hypothesis, positives, negatives, f"random round {round_index} step {step} ({kind}{phi_name})")
            require(len(hypothesis.general) >= 1, f"random round {round_index}: G must never become empty")
            checked += 1
    return (f"{len(C.SEQUENCES)} sequences ({steps} steps) reach the expected S and G; positions incl. undetermined and "
            f"out of scope; G capped at {cap}; invariants hold over {checked} random steps")


# ---- hypothesis ----------------------------------------------------------------

def check_hypothesis() -> str:
    from surprise.harness.cve.hypothesis import parse_hypothesis
    from surprise.theory import contracts

    T = theory_api()
    require(T.Hypothesis is contracts.Hypothesis, "surprise.theory.Hypothesis is the contract class")
    old = contracts.Hypothesis(
        hypothesis_id="h1", engine="duckdb", interventions=["deliminator", "filter_pushdown"], plan_delta=["HASH_JOIN"],
        versions={"1.1.3": "fail"}, specific=["correlated_exists", "neq"], general=[["correlated_exists"], ["neq"]],
        positives=["run-1:1"], negatives=[], source="deterministic", status="proposed")
    require((old.oracle, old.fail_kind, old.error_class, old.behavior_shape, old.contradictions, old.truncated)
            == (None, None, None, None, (), False), "the fields S6 adds must default to empty, so S2-era objects still build")
    s2_era = {key: value for key, value in old.to_dict().items()
              if key not in ("oracle", "fail_kind", "error_class", "behavior_shape", "contradictions", "truncated")}
    require(contracts.Hypothesis.from_dict(s2_era) == old, "a hypothesis serialised before S6 must still load")
    full = hand_hypothesis(C.S_HAND, ((C.L_DUPS,),))
    full = dataclasses.replace(full, positives=("r1",), negatives=("r2", "r3"), contradictions=("r3",), truncated=True,
                               versions={"ladder": "longstanding"})
    as_dict = full.to_dict()
    require(json.loads(json.dumps(as_dict, sort_keys=True)) == as_dict and contracts.Hypothesis.from_dict(as_dict) == full
            and contracts.Hypothesis.from_json(full.to_json()) == full, "a full hypothesis must round-trip through JSON")
    require({"oracle", "fail_kind", "error_class", "behavior_shape", "contradictions", "truncated"} <= set(as_dict),
            f"to_dict() must carry the new fields, got {sorted(as_dict)}")
    for what, change in (("an unknown oracle", dict(oracle="no_such_oracle")), ("a non-string fail_kind", dict(fail_kind=3)),
                         ("contradictions as one string", dict(contradictions="r1")), ("a non-bool truncated", dict(truncated="yes"))):
        expect_raises(ValueError, lambda c=change: dataclasses.replace(full, **c), f"Hypothesis with {what}")

    # the deterministic start of a family: I, delta-P and V come from the CVE profile
    started = 0
    for fail_name, phi_name, engine in (("df_missing", "x1", ENGINE), ("df_extra", "x4", ENGINE), ("f1", "joinq", "duckdb"),
                                        ("f9", "plain", "duckdb")):
        label = fail_label(fail_name)
        example = phi(phi_name, engine=engine)
        family = T.new_family("h-new", example, label, "run:7")
        evidence = C.PROFILES[C.FAILS[fail_name][5]]
        where = f"new_family from {fail_name}"
        require((family.hypothesis_id, family.engine, family.oracle) == ("h-new", engine, label.oracle), f"{where}: header wrong")
        require(tuple(family.interventions) == tuple(evidence["fix_set"]), f"{where}: I must be the fix set, got {family.interventions}")
        require(tuple(family.plan_delta) == tuple(evidence["plan_diff"]), f"{where}: delta-P must be the plan diff")
        require(family.versions.get("ladder") == evidence["ladder"], f"{where}: V must record the version ladder, got {family.versions}")
        require(family.versions.get("witness_switches") == list(evidence["witness"])
                and family.versions.get("fix_kind") == evidence["fix_kind"], f"{where}: V keeps the profile's other evidence")
        from surprise.harness.cve.shape import behavior_shape

        require((family.fail_kind, family.error_class, family.behavior_shape)
                == (label.fail_kind, label.identity.error_class, behavior_shape(label.identity.behavior)),
                f"{where}: the failure class, error class and behavior shape come from the label")
        require(tuple(family.specific) == tuple(sorted(C.PHI[phi_name])) and tuples(family.general) == C.TOP,
                f"{where}: S starts as phi and G as the empty conjunction, got {family.specific} / {family.general}")
        require(family.positives == ("run:7",) and family.negatives == () and family.contradictions == ()
                and family.truncated is False and family.source == "deterministic" and family.status == "active",
                f"{where}: bookkeeping wrong: {family.to_dict()}")
        require(T.position(family, example, label.oracle) == "confirmed", f"{where}: the first failure lies in its own S")
        started += 1
    replayed = T.new_family("h-new", phi("x4"), fail_label("df_extra"), "run:9",
                            negatives=[(phi("plain"), "run:2"), (phi("x3"), "run:3"), (phi("joinq"), "run:4")], source="hand")
    require(tuples(replayed.general) == ((C.INT_ALL,), (C.L_DUPS,), (C.T_DUPS,)) and replayed.negatives == ("run:2", "run:3")
            and replayed.source == "hand",
            f"earlier passes carve G at birth, and one that G already excludes is not an example: "
            f"G is {tuples(replayed.general)}, E- is {replayed.negatives}")
    expect_raises(ValueError, lambda: T.new_family("h", phi("x1"), pass_label(), "r"), "a family from a pass label")
    expect_raises(ValueError, lambda: T.new_family("h", phi("x1"), fail_label("df_missing_raw"), "r"),
                  "a family from a failure that was not profiled")

    # what tier 2 of the harness is given
    request = T.attribution_request(hand_hypothesis(C.S_HAND, C.TOP, hypothesis_id="h2"))
    require(request == {"hypothesis_id": "h2", "engine": ENGINE, "interventions": [], "fail_kind": "wrong_result",
                        "error_class": None, "behavior_shape": "missing_only"}, f"attribution request without switches: {request}")
    switched = T.attribution_request(hand_hypothesis((C.SELECT,), C.TOP, hypothesis_id="h7", identity="h_f1", engine="duckdb",
                                                     oracle="plan_variant"))
    require(switched == {"hypothesis_id": "h7", "engine": "duckdb", "interventions": ["filter_pushdown", "deliminator"]},
            f"with a fix set the request names the interventions and nothing else: {switched}")
    for mapping, engine in ((request, ENGINE), (switched, "duckdb")):
        json.dumps(mapping)
        parsed = parse_hypothesis(mapping, engine)
        require(parsed.hypothesis_id == mapping["hypothesis_id"], "the frozen harness must accept the request")
    return (f"contract keeps S2-era objects and round-trips the new fields; {started} families started from profiles, "
            "one with earlier passes replayed; 2 attribution requests accepted by the harness parser")


# ---- identity ------------------------------------------------------------------

def check_identity() -> str:
    T = theory_api()
    for identity, fail_name, attribution, expected in C.IDENTITY:
        hypothesis = hand_hypothesis((C.SELECT,), C.TOP, identity=identity)
        got = T.identity_match(hypothesis, fail_label(fail_name, attribution=attribution))
        require(got is expected, f"identity_match({identity}, {fail_name}, attribution={attribution}) is {got!r}, expected {expected!r}")
    hypothesis = hand_hypothesis((C.SELECT,), C.TOP)
    expect_raises(ValueError, lambda: T.identity_match(hypothesis, pass_label()), "identity_match on a pass label")
    expect_raises(ValueError, lambda: T.identity_match(hypothesis, invalid_label()), "identity_match on an invalid label")
    return f"{len(C.IDENTITY)} hypothesis / label pairs judged: harness test first, then fix set, then the three profile fields"


# ---- residual ------------------------------------------------------------------

def check_residual() -> str:
    T = theory_api()
    prior_fails, prior_tests = C.CONSTANTS["RESIDUAL_PRIOR_FAILS"], C.CONSTANTS["RESIDUAL_PRIOR_TESTS"]
    residual = T.Residual()
    unit, other = C.UNITS["x1"], C.UNITS["plain"]
    require(residual.counts(unit) == (0, 0) and close(residual.rate(unit), prior_fails / prior_tests),
            f"an untested unit has the prior rate, got {residual.rate(unit)!r}")
    script = ["pass"] * 7 + ["fail"] * 2 + ["pass"]
    for outcome in script:
        residual.observe(unit, outcome)
    require(residual.counts(unit) == (10, 2) and close(residual.rate(unit), (2 + prior_fails) / (10 + prior_tests)),
            f"after 8 passes and 2 unexplained failures: {residual.counts(unit)} {residual.rate(unit)!r}")
    require(residual.counts(other) == (0, 0) and close(residual.rate(other), prior_fails / prior_tests), "units are independent")
    for bad_unit, bad_outcome in ((unit, "invalid"), (unit, "maybe"), ("", "pass")):
        expect_raises(ValueError, lambda u=bad_unit, o=bad_outcome: residual.observe(u, o), f"Residual.observe({bad_unit!r}, {bad_outcome!r})")
    require(residual.counts(unit) == (10, 2), "a rejected observation must not count")
    as_dict = residual.to_dict()
    require(as_dict == {unit: {"tested": 10, "unexplained": 2}} and json.loads(json.dumps(as_dict)) == as_dict,
            f"Residual.to_dict() is {as_dict}")
    loaded = T.Residual.from_dict(as_dict)
    require(loaded.to_dict() == as_dict and loaded.counts(unit) == (10, 2), "Residual must round-trip")
    loaded.observe(unit, "pass")
    require(residual.counts(unit) == (10, 2), "a loaded residual is a separate object")
    for bad in ({unit: {"tested": 1, "unexplained": 2}}, {unit: {"tested": -1, "unexplained": 0}}, {unit: {"tested": 1}}, [unit]):
        expect_raises((ValueError, KeyError, TypeError), lambda b=bad: T.Residual.from_dict(b), f"Residual.from_dict({bad!r})")
    rates = [T.Residual().rate(unit)]
    grow = T.Residual()
    for _ in range(300):
        grow.observe(unit, "fail")
        rates.append(grow.rate(unit))
    require(all(0.0 < rate < 1.0 for rate in rates) and rates == sorted(rates), "the rate stays strictly inside (0, 1) and rises with failures")
    return f"prior {prior_fails / prior_tests}, counts and rate per unit, round trip; the rate never reaches 0 or 1"


# ---- validity ------------------------------------------------------------------

def check_validity() -> str:
    T = theory_api()
    prior_invalid, prior_tests = C.CONSTANTS["VALIDITY_PRIOR_INVALID"], C.CONSTANTS["VALIDITY_PRIOR_TESTS"]
    for name, expected in C.CLASSES.items():
        require(T.experiment_class(phi(name)) == expected, f"experiment_class({name}) is {T.experiment_class(phi(name))!r}")
    require(T.experiment_class(phi((C.EXC_ALL, C.SELECT), engine="postgres", layers=C.AST_ONLY)) == "postgres|set_op_all",
            "the experiment class needs only the ast layer: an experiment that never ran still has one")
    validity = T.Validity()
    klass = C.CLASSES["x1"]
    require(validity.counts(klass, "tlp") == (0, 0) and close(validity.rate(klass, "tlp"), prior_invalid / prior_tests),
            f"an untried class has the prior rate, got {validity.rate(klass, 'tlp')!r}")
    for outcome, reason in (("pass", None), ("invalid", "not_applicable"), ("fail", None), ("invalid", "not_applicable"),
                            ("invalid", "query_error")):
        validity.observe(klass, "tlp", outcome, reason)
    require(validity.counts(klass, "tlp") == (5, 3) and close(validity.rate(klass, "tlp"), (3 + prior_invalid) / (5 + prior_tests)),
            f"after 5 experiments, 3 invalid: {validity.counts(klass, 'tlp')} {validity.rate(klass, 'tlp')!r}")
    require(validity.reasons(klass, "tlp") == {"not_applicable": 2, "query_error": 1},
            f"invalid reasons are tallied, not_applicable apart: {validity.reasons(klass, 'tlp')}")
    require(validity.counts(klass, ORACLE) == (0, 0) and validity.counts(C.CLASSES["plain"], "tlp") == (0, 0),
            "the rate is per experiment class and per oracle")
    for what, args in (("an unknown oracle", (klass, "nope", "pass", None)), ("an unknown label", (klass, "tlp", "maybe", None)),
                       ("invalid without a reason", (klass, "tlp", "invalid", None)),
                       ("a reason on a pass", (klass, "tlp", "pass", "timeout")), ("an empty class", ("", "tlp", "pass", None))):
        expect_raises(ValueError, lambda a=args: validity.observe(*a), f"Validity.observe with {what}")
    require(validity.counts(klass, "tlp") == (5, 3), "a rejected observation must not count")
    as_dict = validity.to_dict()
    require(json.loads(json.dumps(as_dict)) == as_dict and T.Validity.from_dict(as_dict).to_dict() == as_dict
            and T.Validity.from_dict(as_dict).rate(klass, "tlp") == validity.rate(klass, "tlp"), "Validity must round-trip")
    return f"prior {prior_invalid / prior_tests}; counts, reasons and rate per (class, oracle); round trip"


# ---- predict -------------------------------------------------------------------

def check_predict() -> str:
    T = theory_api()
    prior = C.CONSTANTS["RESIDUAL_PRIOR_FAILS"] / C.CONSTANTS["RESIDUAL_PRIOR_TESTS"]
    k_prior = C.CONSTANTS["VALIDITY_PRIOR_INVALID"] / C.CONSTANTS["VALIDITY_PRIOR_TESTS"]
    require(tuple(T.ZONES) == C.ZONES and tuple(T.TRIAGE_KINDS) == C.TRIAGE_KINDS, f"ZONES / TRIAGE_KINDS: {T.ZONES} {T.TRIAGE_KINDS}")
    for probability, outcome, expected in ((prior, "fail", 6.643856189774724), (0.95, "pass", 4.321928094887363),
                                           (0.5, "fail", 1.0), (0.5, "pass", 1.0), (0.95, "fail", 0.07400058144377693),
                                           (prior, "pass", 0.014499569695115089)):
        got = T.surprise_bits(probability, outcome)
        require(close(got, expected), f"surprise_bits({probability}, {outcome}) is {got!r}, expected {expected!r}")
    require(T.surprise_bits(0.5, "invalid") is None, "an invalid experiment has no surprise")
    for bad in ((0.0, "fail"), (1.0, "pass"), (-0.1, "fail"), (1.5, "fail"), (0.5, "maybe"), ("0.5", "fail"), (True, "fail")):
        expect_raises(ValueError, lambda b=bad: T.surprise_bits(*b), f"surprise_bits{bad}")

    theory = T.Theory()
    empty = theory.predict(phi("x1"), ORACLE)
    require((empty.zone, empty.hypothesis_id, tuple(empty.confirmed), tuple(empty.pending)) == ("unexplored", None, (), ()),
            f"an empty theory explores: {empty.to_dict()}")
    require((empty.engine, empty.oracle, empty.unit, empty.experiment_class) == (ENGINE, ORACLE, C.UNITS["x1"], C.CLASSES["x1"]),
            f"prediction header: {empty.to_dict()}")
    require(close(empty.p_fail_valid, prior) and close(empty.p_invalid, k_prior)
            and close(empty.p_fail, (1 - k_prior) * prior) and close(empty.p_pass, (1 - k_prior) * (1 - prior)),
            f"P_T(fail | x) = (1 - K^v) * rho_c: {empty.to_dict()}")
    require(close(empty.p_fail + empty.p_pass + empty.p_invalid, 1.0), "the three outcomes sum to one")
    require(close(empty.surprise("fail"), bits(prior)) and close(empty.surprise("pass"), bits(1 - prior))
            and empty.surprise("invalid") is None, "Prediction.surprise() is the surprise of a valid outcome")
    as_dict = empty.to_dict()
    require(json.loads(json.dumps(as_dict)) == as_dict and {"engine", "oracle", "unit", "experiment_class", "zone", "hypothesis_id",
                                                             "confirmed", "pending", "p_fail_valid", "p_invalid", "p_fail",
                                                             "p_pass"} <= set(as_dict), f"Prediction.to_dict(): {sorted(as_dict)}")

    theory.put(hand_hypothesis(C.S_HAND, ((C.L_DUPS,),), hypothesis_id="h-a"))
    theory.put(hand_hypothesis(C.S_X4, ((C.INT_ALL,), (C.T_DUPS,)), hypothesis_id="h-b", identity="h_extra"))
    theory.put(hand_hypothesis((C.SELECT,), C.TOP, hypothesis_id="h-duck", engine="duckdb", oracle="plan_variant"))
    expectations = [
        # phi, zone, owner, confirmed, pending, P(fail | valid)
        ("x1", "confirmed", "h-a", ("h-a",), ("h-b",), 0.95),
        ("x8", "confirmed", "h-a", ("h-a",), ("h-b",), 0.95),
        ("x4", "confirmed", "h-b", ("h-b",), ("h-a",), 0.95),
        ("x5", "pending", "h-a", (), ("h-a", "h-b"), 0.5),
        ("x3", "unexplored", None, (), (), prior),
        ("plain", "unexplored", None, (), (), prior),
    ]
    for name, zone, owner, confirmed, pending, probability in expectations:
        got = theory.predict(phi(name), ORACLE)
        require((got.zone, got.hypothesis_id, tuple(got.confirmed), tuple(got.pending)) == (zone, owner, confirmed, pending)
                and close(got.p_fail_valid, float(probability)),
                f"predict({name}): {got.to_dict()}, expected {(zone, owner, confirmed, pending, probability)}")
    foreign = theory.predict(phi("x1"), "tlp")
    require(foreign.zone == "unexplored" and foreign.unit == C.UNITS["x1"].replace("cross_dbms", "tlp"),
            "hypotheses of another oracle do not colour the prediction")
    require(theory.predict(phi("plain", engine="duckdb"), "plan_variant").zone == "confirmed",
            "each engine and oracle has its own hypotheses")
    partial = theory.predict(phi((C.EXC_ALL, C.SELECT), layers=C.AST_ONLY), ORACLE)
    require(partial.zone == "unexplored" and partial.unit == "datafusion|cross_dbms|set_op_all|none|unknown",
            f"an undetermined position is not a zone: {partial.to_dict()}")
    # the residual drives the unexplored zone, per unit
    for _ in range(9):
        theory.residual.observe(C.UNITS["plain"], "pass")
    theory.residual.observe(C.UNITS["plain"], "fail")
    drifted = theory.predict(phi("plain"), ORACLE)
    require(close(drifted.p_fail_valid, 2 / 110) and close(theory.predict(phi("x3"), ORACLE).p_fail_valid, prior),
            f"rho_c of the unit: {drifted.p_fail_valid!r}")
    theory.validity.observe(C.CLASSES["plain"], ORACLE, "invalid", "query_error")
    require(close(theory.predict(phi("plain"), ORACLE).p_invalid, 2 / 11) and close(theory.predict(phi("x3"), ORACLE).p_invalid, k_prior),
            "K^v of the experiment class and oracle")
    expect_raises(ValueError, lambda: theory.predict(phi("x1"), "no_such_oracle"), "predict with an unknown oracle")
    other_vocab = dataclasses.replace(phi("x1"), vocab="0" * 64)
    expect_raises(ValueError, lambda: theory.predict(other_vocab, ORACLE), "predict with a phi of another vocabulary")
    expect_raises(ValueError, lambda: theory.predict(phi("x1").to_dict(), ORACLE), "predict with a dict instead of a Phi")
    return (f"surprise 6.64 / 4.32 / 1.00 / 0.07 / 0.01 bits; {len(expectations)} zone predictions with precedence "
            "confirmed > pending > residual; per-unit rho and per-class K^v")


# ---- triage --------------------------------------------------------------------

def check_triage() -> str:
    T = theory_api()
    for outcome, surprise, kind in C.TRIAGE:
        got = T.triage(outcome, surprise)
        require(got == kind, f"triage({outcome}, {surprise}) is {got!r}, expected {kind!r}")
    for outcome, surprise in C.TRIAGE_BAD:
        expect_raises(ValueError, lambda o=outcome, s=surprise: T.triage(o, s), f"triage({outcome!r}, {surprise!r})")
    theory = T.Theory()
    theory.put(hand_hypothesis(C.S_HAND, ((C.L_DUPS,),), hypothesis_id="h-a"))
    where = {"confirmed": "x1", "pending": "x4", "unexplored": "plain"}
    for (zone, outcome), (kind, about) in C.DOCUMENT_TABLE.items():
        prediction = theory.predict(phi(where[zone]), ORACLE)
        surprise = prediction.surprise(outcome)
        require(prediction.zone == zone and abs(surprise - about) < 1e-3 and T.triage(outcome, surprise) == kind,
                f"{zone} + {outcome}: {surprise:.4f} bits -> {T.triage(outcome, surprise)!r}, the document says {about} -> {kind!r}")
    return f"{len(C.TRIAGE)} (label, bits) pairs incl. both thresholds; the six rows of the framework document; {len(C.TRIAGE_BAD)} bad calls rejected"


# ---- theory --------------------------------------------------------------------

def state_without(theory: Any, *keys: str) -> dict:
    return {key: value for key, value in theory.to_dict().items() if key not in keys}


def scripted_walk(T: Any) -> tuple[Any, list[Any]]:
    """The DF-A -> DF-B case with hand-made labels. Returns the theory and the observations."""
    theory = T.Theory()
    seen: list[Any] = []
    obs = theory.observe(phi("x1"), fail_label("df_missing"), "r1")
    seen.append(obs)
    first = obs.opened
    require(isinstance(first, str) and first, f"the first unexplained, profiled failure opens a family: {obs.to_dict()}")
    theory.put(dataclasses.replace(theory.get(first), specific=C.S_HAND, source="hand-written"))
    seen.append(theory.observe(phi("x3"), pass_label(), "r2"))
    seen.append(theory.observe(phi("x4"), fail_label("df_extra", attribution=(first, False)), "r3"))
    seen.append(theory.observe(phi("x1"), fail_label("df_missing_raw", attribution=(first, True)), "r4"))
    seen.append(theory.observe(phi("x8"), pass_label(), "r5"))
    seen.append(theory.observe(phi("x5"), pass_label(), "r6"))
    seen.append(theory.observe(phi("x5"), pass_label(), "r7"))
    seen.append(theory.observe(phi("plain"), invalid_label("query_error"), "r8"))
    seen.append(theory.observe(phi("x6"), fail_label("df_missing_raw"), "r9"))
    return theory, seen


def check_theory() -> str:
    T = theory_api()
    prior = C.CONSTANTS["RESIDUAL_PRIOR_FAILS"] / C.CONSTANTS["RESIDUAL_PRIOR_TESTS"]
    theory, seen = scripted_walk(T)
    h2 = seen[0].opened
    h3 = seen[2].opened
    require(isinstance(h3, str) and h3 and h3 != h2, f"the INTERSECT ALL failure opens a second family: {seen[2].to_dict()}")
    expected = [
        # zone, owner, bits, triage, effects, opened, unexplained
        ("unexplored", None, bits(prior), "new_family", (), h2, False),
        ("pending", h2, 1.0, "boundary_move", ((h2, "specialized"),), None, False),
        ("pending", h2, 1.0, "boundary_move", ((h2, "specialized"),), h3, False),
        ("confirmed", h2, bits(0.95), "duplicate", ((h2, "duplicate"), (h3, "specialized")), None, False),
        ("confirmed", h2, bits(0.05), "unexpected_pass", ((h2, "contradiction"),), None, False),
        ("unexplored", None, bits(1 - prior), "no_information", (), None, False),
        ("unexplored", None, bits(1 - 1 / 101), "no_information", (), None, False),
        ("unexplored", None, None, "invalid", (), None, False),
        ("unexplored", None, bits(prior), "new_family", ((h2, "outside"),), None, True),
    ]
    for index, (obs, (zone, owner, surprise, kind, effects, opened, unexplained)) in enumerate(zip(seen, expected), start=1):
        where = f"scripted step {index}"
        got_effects = tuple(tuple(effect) for effect in obs.effects)
        require((obs.prediction.zone, obs.prediction.hypothesis_id) == (zone, owner), f"{where}: predicted {obs.prediction.to_dict()}")
        require((obs.surprise is None) if surprise is None else close(obs.surprise, surprise, 1e-9),
                f"{where}: surprise is {obs.surprise!r}, expected {surprise!r}")
        require((obs.triage, got_effects, obs.opened, obs.unexplained) == (kind, effects, opened, unexplained),
                f"{where}: {(obs.triage, got_effects, obs.opened, obs.unexplained)}, expected {(kind, effects, opened, unexplained)}")
        require(json.loads(json.dumps(obs.to_dict())) == obs.to_dict(), f"{where}: Observation.to_dict() must be JSON-safe")
    hyp2, hyp3 = theory.get(h2), theory.get(h3)
    require(tuple(hyp2.specific) == C.S_HAND and tuples(hyp2.general) == (C.S_HAND,) and T.converged(hyp2),
            f"h2 after the two predictions: S {hyp2.specific}, G {hyp2.general}")
    require(hyp2.positives == ("r1", "r4") and hyp2.negatives == ("r2", "r3", "r5") and hyp2.contradictions == ("r5",),
            f"h2 examples: E+ {hyp2.positives}, E- {hyp2.negatives}, contradictions {hyp2.contradictions}")
    require(tuple(hyp3.specific) == C.S_X4 and tuples(hyp3.general) == ((C.INT_ALL,),)
            and (hyp3.fail_kind, hyp3.behavior_shape, tuple(hyp3.interventions)) == ("wrong_result", "extra_only", ())
            and hyp3.positives == ("r3",) and hyp3.negatives == ("r2", "r4"),
            f"h3: {hyp3.to_dict()}")
    require([h.hypothesis_id for h in theory.hypotheses] == [h2, h3], "Theory.hypotheses keeps the order of creation")
    require(theory.residual.to_dict() == {C.UNITS["x5"]: {"tested": 2, "unexplained": 0},
                                          C.UNITS["x6"]: {"tested": 1, "unexplained": 1}},
            f"R counts only what no hypothesis covers: {theory.residual.to_dict()}")
    require(theory.validity.counts(C.CLASSES["x1"], ORACLE) == (7, 0) and theory.validity.counts(C.CLASSES["plain"], ORACLE) == (1, 1)
            and theory.validity.counts(C.CLASSES["x6"], ORACLE) == (1, 0),
            f"K^v sees every experiment: {theory.validity.to_dict()}")
    require(close(theory.predict(phi("x6"), ORACLE).p_fail_valid, 2 / 101), "an unexplained failure raises rho of its unit")

    # an invalid experiment touches K^v and nothing else
    before = state_without(theory, "validity")
    version = theory.version
    obs = theory.observe(phi("x1"), invalid_label("timeout"), "r10")
    require(obs.triage == "invalid" and obs.surprise is None and obs.effects == () and state_without(theory, "validity") == before
            and theory.version != version, "invalid: only K^v moves (and the version with it)")

    # the whole run is a function of its inputs, and the state is complete
    again, seen_again = scripted_walk(T)
    twin, _ = scripted_walk(T)
    require([o.to_dict() for o in seen_again] == [o.to_dict() for o in seen], "the same script twice gives the same observations")
    state = again.to_dict()
    require(json.loads(json.dumps(state, sort_keys=True)) == state and state == twin.to_dict() and again.version == twin.version,
            "Theory.to_dict() is JSON-safe and the same for the same history; so is Theory.version")
    require(isinstance(again.version, str) and again.version and again.version != T.Theory().version,
            "Theory.version names the state")
    restored = T.Theory.from_dict(json.loads(json.dumps(state)))
    require(restored.to_dict() == state and restored.version == again.version, "Theory must round-trip through JSON")
    tail = [("x4", fail_label("df_extra"), "s1"), ("x7", fail_label("df_missing"), "s2"), ("joinq", pass_label(), "s3"),
            ("plain", fail_label("df_both"), "s4"), ("x3", pass_label(), "s5")]
    for name, label, record in tail:
        a = again.observe(phi(name), label, record)
        b = restored.observe(phi(name), label, record)
        require(a.to_dict() == b.to_dict(), f"after a reload the theory answers as before ({name})")
    require(restored.to_dict() == again.to_dict(), "after a reload the theory learns as before")
    for bad in ({}, {**state, "schema": 2}, {**state, "vocab": "0" * 64}, {**state, "extra": 1}, [state]):
        expect_raises((ValueError, KeyError, TypeError), lambda b=bad: T.Theory.from_dict(b), "Theory.from_dict with a bad state")

    # an explicit prediction is the one made before the experiment
    left, right = T.Theory(), T.Theory()
    for name, label, record in (("x1", fail_label("df_missing"), "p1"), ("x3", pass_label(), "p2"), ("x4", fail_label("df_extra"), "p3")):
        prediction = left.predict(phi(name), ORACLE)
        a = left.observe(phi(name), label, record, prediction=prediction)
        b = right.observe(phi(name), label, record)
        require(a.to_dict() == b.to_dict() and a.prediction == prediction, f"observe() with and without the prediction ({name})")
    expect_raises(ValueError, lambda: left.observe(phi("x1"), fail_label("df_missing"), "p9",
                                                   prediction=left.predict(phi("x1"), "tlp")),
                  "observe with a prediction made for another oracle")
    # the deterministic start: with no hand-written h2, left_has_dups still enters G, next to its twin
    deterministic = left.get(left.hypotheses[0].hypothesis_id)
    require(tuple(deterministic.specific) == C.S_X1
            and tuples(deterministic.general) == (C.sort_conj(C.EXC_ALL, C.L_DUPS), C.sort_conj(C.EXC_ALL, C.T_DUPS)),
            f"without the hand-written S: G is {tuples(deterministic.general)}")
    require(len(left.hypotheses) == 2 and left.hypotheses[1].behavior_shape == "extra_only",
            "the INTERSECT ALL failure has another behavior shape: the profile comparison alone opens the new family")

    # triage follows the size of the surprise, also where the residual has moved
    unit = "duckdb|tlp|plain|scan|plain"
    plain = phi("plain", engine="duckdb")
    drift = [(30, "fail", "new_family"), (40, "fail", "boundary_move"), (300, "fail", "duplicate"), (300, "pass", "unexpected_pass")]
    for failures, outcome, kind in drift:
        theory = T.Theory()
        for _ in range(failures):
            theory.residual.observe(unit, "fail")
        label = fail_label("df_missing_raw", oracle="tlp") if outcome == "fail" else pass_label("tlp")
        obs = theory.observe(plain, label, "d1")
        rate = (failures + 1) / (failures + 100)
        require(obs.prediction.zone == "unexplored" and obs.prediction.hypothesis_id is None and obs.triage == kind
                and close(obs.surprise, bits(rate if outcome == "fail" else 1 - rate)),
                f"{failures} unexplained failures then a {outcome}: {obs.to_dict()}, expected {kind}")

    # an example that lacks a layer S mentions teaches the hypothesis nothing
    theory = T.Theory()
    theory.put(hand_hypothesis(C.S_HAND, C.TOP, hypothesis_id="h-a"))
    obs = theory.observe(phi((C.EXC_ALL, C.SELECT), layers=C.AST_ONLY), pass_label(), "u1")
    require(obs.prediction.zone == "unexplored" and obs.effects == () and tuples(theory.get("h-a").general) == C.TOP
            and theory.residual.counts("datafusion|cross_dbms|set_op_all|none|unknown") == (1, 0),
            f"an ast-only pass: {obs.to_dict()}")
    # a failure whose identity cannot be decided is not learned from either
    theory = T.Theory()
    theory.put(hand_hypothesis((C.SELECT,), C.TOP, hypothesis_id="h-f1", identity="h_f1", engine="duckdb", oracle="plan_variant"))
    obs = theory.observe(phi("plain", engine="duckdb"), fail_label("f1_raw"), "k1")
    require(tuple(tuple(e) for e in obs.effects) == (("h-f1", "unknown_identity"),) and obs.opened is None and obs.unexplained is True
            and theory.get("h-f1").positives == (), f"unknown identity: {obs.to_dict()}")

    # put(): what a theory accepts
    theory = T.Theory()
    theory.put(hand_hypothesis((C.L_DUPS, C.EXC_ALL, C.SET_ALL), ((C.D_SETOP, C.L_DUPS), ()), hypothesis_id="h-a"))
    stored = theory.get("h-a")
    require(tuple(stored.specific) == C.S_HAND and tuples(stored.general) == C.TOP,
            f"put() stores the canonical form: S {stored.specific}, G {stored.general}")
    theory.put(hand_hypothesis(C.S_HAND, ((C.L_DUPS,),), hypothesis_id="h-a"))
    require(len(theory.hypotheses) == 1 and tuples(theory.get("h-a").general) == ((C.L_DUPS,),), "put() with a known id replaces")
    bad_puts = [
        ("no oracle", dataclasses.replace(hand_hypothesis(C.S_HAND, C.TOP), oracle=None)),
        ("an unknown feature", hand_hypothesis(("ast:no_such_feature",), C.TOP)),
        ("a G member that is not more general than S", hand_hypothesis(C.S_HAND, ((C.INT_ALL,),))),
        ("an unknown feature in G", hand_hypothesis(C.S_HAND, (("nope:x",),))),
    ]
    for what, hypothesis in bad_puts:
        expect_raises(ValueError, lambda h=hypothesis: theory.put(h), f"put() with {what}")
    expect_raises(ValueError, lambda: theory.put("h-a"), "put() with something that is not a hypothesis")
    expect_raises(KeyError, lambda: theory.get("h-missing"), "get() with an unknown id")
    for what, call in (("a dict for phi", lambda: theory.observe(phi("x1").to_dict(), pass_label(), "z")),
                       ("a dict for the label", lambda: theory.observe(phi("x1"), pass_label().to_dict(), "z")),
                       ("an empty record id", lambda: theory.observe(phi("x1"), pass_label(), ""))):
        expect_raises(ValueError, call, f"observe() with {what}")
    return (f"{len(seen)} scripted experiments: 6.64 -> family, 1.00 x 2 -> G moves and a second family, 0.07 duplicate, "
            "4.32 unexpected pass, 0.01 no information, invalid, unexplained failure; replay, reload and determinism; "
            f"{len(drift)} drifted-residual cases; {len(bad_puts) + 2} bad calls rejected")


# ---- manifest ------------------------------------------------------------------

def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module)
        elif isinstance(node, ast.ImportFrom) and node.level > 0:
            package = list(path.parent.relative_to(FRAMEWORK).parts)
            base = package[:len(package) - (node.level - 1)]
            found.add(".".join(base + ([node.module] if node.module else [])))
    return found


def check_manifest() -> str:
    from surprise.features import limits
    from surprise.harness.ledger import Ledger
    from surprise.harness.manifest import build_manifest, verify_manifest

    T = theory_api()
    F = features_api()
    section = T.theory_manifest()
    require(json.loads(json.dumps(section, sort_keys=True)) == section, "theory_manifest() must be JSON-safe")
    require(section.get("schema") == 1 and section.get("constants") == C.CONSTANTS,
            f"the theory section carries the constants: {section.get('constants')}")
    code = section.get("code", {})
    files = code.get("files", {})
    on_disk = sorted(p.relative_to(FRAMEWORK).as_posix() for p in (FRAMEWORK / "surprise" / "theory").rglob("*.py"))
    require(code.get("algorithm") == "sha256" and isinstance(code.get("hash"), str) and len(code["hash"]) == 64
            and sorted(files) == on_disk, f"the theory code is hashed file by file: {sorted(files)} vs {on_disk}")
    features = section.get("features", {})
    require(features.get("vocab") == F.default_registry().digest(), "the theory section names the vocabulary")
    require(features.get("limits") == {"MAX_TABLE_ROWS": limits.MAX_TABLE_ROWS, "PROBE_TIMEOUT_S": limits.PROBE_TIMEOUT_S,
                                       "ISOLATION_TIMEOUT_S": limits.ISOLATION_TIMEOUT_S},
            f"and the bounds phi was extracted under: {features.get('limits')}")
    feature_files = sorted(p.relative_to(FRAMEWORK).as_posix() for p in (FRAMEWORK / "surprise" / "features").rglob("*.py"))
    require(sorted(features.get("code", {}).get("files", {})) == feature_files, "the feature code is hashed too")
    require(T.theory_manifest() == section, "theory_manifest() is stable")
    for command, expected in (("manifest", section), ("constants", C.CONSTANTS)):
        run = subprocess.run([sys.executable, "-m", "surprise.theory", command], cwd=FRAMEWORK, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, timeout=120.0, encoding="utf-8", errors="replace")
        require(run.returncode == 0, f"`python -m surprise.theory {command}` failed: {_ascii(run.stderr.strip()[-300:])}")
        require(json.loads(run.stdout) == expected and run.stdout.isascii(),
                f"`python -m surprise.theory {command}` must print the same JSON another process computes")

    base = build_manifest("s06-gate")
    snapshot = json.loads(json.dumps(base))
    extended = T.extend_manifest(base)
    require(base == snapshot, "extend_manifest() must not change the manifest it is given")
    require(extended.get("theory") == section and {k: v for k, v in extended.items() if k != "theory"} == base,
            "extend_manifest() adds the key 'theory' and nothing else")
    require(verify_manifest(extended) == [], f"the harness part still verifies: {verify_manifest(extended)}")
    require(set(extended["constants"]) == set(base["constants"]) and not set(C.CONSTANTS) & set(extended["constants"]),
            "the frozen harness constants are left as they are")
    expect_raises(ValueError, lambda: T.extend_manifest(extended), "extending a manifest that already has a theory section")
    expect_raises(ValueError, lambda: T.extend_manifest({"run_id": "x"}), "extending something that is not a run manifest")
    frozen = json.loads(FROZEN_S04.read_text(encoding="utf-8"))
    require(verify_manifest(frozen) == [], f"S6 leaves the frozen harness alone: {verify_manifest(frozen)[:3]}")
    with tempfile.TemporaryDirectory(prefix="s06-gate-") as tmp:
        ledger = Ledger(Path(tmp) / "ledger.sqlite")
        try:
            ledger.start_run("s06-gate", extended)
            stored = ledger.run_manifest("s06-gate")
        finally:
            ledger.close()
    require(stored.get("theory", {}).get("constants") == C.CONSTANTS and stored == extended,
            "the ledger keeps the theory constants with the run")
    problems = T.verify_theory_manifest(extended)
    require(problems == [], f"verify_theory_manifest on a fresh manifest: {problems}")
    tampered = json.loads(json.dumps(extended))
    tampered["theory"]["constants"]["P_PENDING"] = 0.6
    tampered["theory"]["code"]["files"][on_disk[0]] = "0" * 64
    problems = T.verify_theory_manifest(tampered)
    require(any("P_PENDING" in line for line in problems) and any(on_disk[0] in line for line in problems)
            and all(line.isascii() for line in problems), f"a changed constant and a changed file are both reported: {problems}")
    expect_raises(ValueError, lambda: T.verify_theory_manifest(base), "verifying a manifest without a theory section")

    # the theory core is deterministic code: no model client, no old main loop
    offenders = []
    for path in sorted((FRAMEWORK / "surprise" / "theory").rglob("*.py")):
        for module in imported_modules(path):
            if any(module == banned or module.startswith(banned + ".") for banned in FORBIDDEN_IMPORTS):
                offenders.append(f"{path.name}: {module}")
    require(not offenders, f"the theory layer must not import {offenders}")
    return (f"theory section: {len(C.CONSTANTS)} constants, {len(files)} theory files and {len(feature_files)} feature files hashed, "
            "vocabulary and limits; harness part and the S4 freeze verify unchanged; stored with a run; tampering reported")


# ---- walkthrough ---------------------------------------------------------------

def real_case(name: str) -> Any:
    from surprise.harness.contracts import SqlCase

    setup, query = C.SQL[name]
    return SqlCase(engine=ENGINE, setup=setup, query=query)


def check_walkthrough() -> str:
    from surprise.harness.evaluate import evaluate_final
    from surprise.harness.ledger import Ledger
    from surprise.harness.manifest import build_manifest, verify_manifest

    T = theory_api()
    F = features_api()
    prior = C.CONSTANTS["RESIDUAL_PRIOR_FAILS"] / C.CONSTANTS["RESIDUAL_PRIOR_TESTS"]
    run_id = "s06-walkthrough"
    theory = T.Theory()
    taken: list[tuple[str, Any, Any, Any]] = []   # name, phi, record, observation

    with tempfile.TemporaryDirectory(prefix="s06-gate-") as tmp:
        ledger = Ledger(Path(tmp) / "ledger.sqlite")
        try:
            ledger.start_run(run_id, T.extend_manifest(build_manifest(run_id)))

            def experiment(name: str, purpose: str) -> Any:
                case = real_case(name)
                example = F.extract(case)
                require(tuple(example.features) == tuple(sorted(C.PHI[name])) and dict(example.layers) == C.ALL_OK,
                        f"{name}: phi on the engine is {example.features}, the gate tables assume {tuple(sorted(C.PHI[name]))}")
                prediction = theory.predict(example, ORACLE)
                owner = prediction.hypothesis_id
                options: dict[str, Any] = {"diagnose": True} if owner is None else {
                    "hypothesis": T.attribution_request(theory.get(owner))}
                record = evaluate_final(case, ORACLE, ledger=ledger, run_id=run_id, purpose=purpose, phi=example.to_dict(),
                                        theory_version=theory.version, p_t=prediction.p_fail_valid, **options)
                observation = theory.observe(example, record.label, record.record_id, prediction=prediction)
                taken.append((name, example, record, observation))
                return observation

            # 1. the first surprise: an unexplored failure
            obs = experiment("x1", "explore")
            label = taken[-1][2].label
            require(label.y == "fail" and label.cve.get("tier") == 3, f"DF-A must be a profiled failure: {label.to_dict()}")
            require(obs.prediction.zone == "unexplored" and close(obs.surprise, bits(prior)) and 6.5 < obs.surprise < 6.7
                    and obs.triage == "new_family" and obs.opened, f"step 1: {obs.to_dict()}")
            h2 = obs.opened
            born = theory.get(h2)
            require((tuple(born.interventions), born.fail_kind, born.error_class, born.behavior_shape)
                    == ((), "wrong_result", None, "missing_only") and born.versions.get("ladder") == "longstanding"
                    and tuple(born.specific) == C.S_X1 and tuples(born.general) == C.TOP,
                    f"step 1: the family starts from the CVE profile: {born.to_dict()}")
            # 2. a hand-written h2 stands in for the LLM: "EXCEPT ALL and the left input has duplicates"
            theory.put(dataclasses.replace(born, specific=C.S_HAND, source="hand-written"))
            # 3. first prediction: without the left duplicates it passes
            obs = experiment("x3", "refine")
            require(taken[-1][2].label.y == "pass" and obs.prediction.zone == "pending" and obs.prediction.hypothesis_id == h2
                    and close(obs.surprise, 1.0) and obs.triage == "boundary_move", f"step 3: {obs.to_dict()}")
            require(tuples(theory.get(h2).general) == ((C.L_DUPS,),),
                    f"step 3: left_has_dups must enter G, G is {tuples(theory.get(h2).general)}")
            # 4. second prediction: INTERSECT ALL fails too ...
            obs = experiment("x4", "generalize")
            label = taken[-1][2].label
            require(label.y == "fail" and obs.prediction.zone == "pending" and close(obs.surprise, 1.0)
                    and obs.triage == "boundary_move", f"step 4: {obs.to_dict()}")
            # 5. ... but not as the same bug
            attribution = label.cve.get("attribution", {})
            require(attribution.get("hypothesis_id") == h2 and attribution.get("consistent") is False
                    and label.cve.get("profile", {}).get("behavior_shape") == "extra_only",
                    f"step 5: the attribution test must find another identity: {label.cve.get('attribution')}")
            h3 = obs.opened
            require(isinstance(h3, str) and h3 not in ("", h2), f"step 5: the identity mismatch opens a new family: {obs.to_dict()}")
            require(tuples(theory.get(h2).general) == (C.S_HAND,) and T.converged(theory.get(h2))
                    and theory.get(h2).positives == (taken[0][2].record_id,),
                    f"step 5: for h2 this is a negative example, G excludes INTERSECT ALL: {tuples(theory.get(h2).general)}")
            new = theory.get(h3)
            require(tuple(new.specific) == C.S_X4 and new.behavior_shape == "extra_only"
                    and tuples(new.general) == ((C.INT_ALL,), (C.L_DUPS,), (C.T_DUPS,)),
                    f"step 5: h3 starts from the profile, carved by the pass seen before: {new.to_dict()}")
            # beyond the gate's letter: the remaining rows of the triage table on the same engine
            obs = experiment("x1", "duplicate")
            require(taken[-1][2].label.cve.get("tier") == 2 and obs.prediction.zone == "confirmed"
                    and close(obs.surprise, bits(0.95)) and obs.triage == "duplicate"
                    and tuple(tuple(e) for e in obs.effects) == ((h2, "duplicate"), (h3, "specialized"))
                    and tuples(theory.get(h3).general) == ((C.INT_ALL,),), f"DF-A again is a cheap duplicate: {obs.to_dict()}")
            obs = experiment("x8", "refine")
            require(taken[-1][2].label.y == "pass" and obs.prediction.zone == "confirmed" and close(obs.surprise, bits(0.05))
                    and obs.triage == "unexpected_pass" and theory.get(h2).contradictions == (taken[-1][2].record_id,),
                    f"balanced duplicates pass inside S: {obs.to_dict()}")
            obs = experiment("x5", "explore")
            require(taken[-1][2].label.y == "pass" and obs.prediction.zone == "unexplored" and close(obs.surprise, bits(1 - prior))
                    and obs.triage == "no_information" and theory.residual.counts(C.UNITS["x5"]) == (1, 0),
                    f"UNION ALL passes outside every hypothesis: {obs.to_dict()}")

            # everything needed to recompute the surprise is in the ledger
            records = ledger.records(run_id=run_id)
            require(len(records) == len(taken) == 6, f"one record per experiment, got {len(records)}")
            for record, (name, example, written, observation) in zip(records, taken):
                require(record == written and record.phi == example.to_dict() and record.p_t == observation.prediction.p_fail_valid,
                        f"{name}: the record keeps phi and the probability the theory gave before execution")
                recomputed = T.surprise_bits(record.p_t, record.label.y)
                require(close(recomputed, observation.surprise), f"{name}: surprise from the ledger {recomputed!r} vs {observation.surprise!r}")
            versions = [record.theory_version for record in records]
            require(len(set(versions)) == len(versions), "the theory changed between any two experiments, and so did its version")
            stored = ledger.run_manifest(run_id)
            require(stored["theory"]["constants"] == C.CONSTANTS and verify_manifest(stored) == []
                    and T.verify_theory_manifest(stored) == [], "the run manifest verifies, harness and theory")
        finally:
            ledger.close()

    # the same labels without a hand-written h2: the deterministic rules alone
    plain = T.Theory()
    for name, example, record, _obs in taken[:3]:
        plain.observe(example, record.label, record.record_id)
    first, second = plain.hypotheses
    require(first.hypothesis_id == h2 and tuple(first.specific) == C.S_X1
            and tuples(first.general) == (C.sort_conj(C.EXC_ALL, C.L_DUPS), C.sort_conj(C.EXC_ALL, C.T_DUPS))
            and second.behavior_shape == "extra_only",
            f"with S = phi(DF-A): G is {tuples(first.general)}, second family {second.to_dict()}")
    surprises = ", ".join("-" if obs.surprise is None else f"{obs.surprise:.2f}" for _n, _p, _r, obs in taken)
    return (f"DF-A {bits(prior):.2f} bits opens h2; two predictions at 1.00 bit: left_has_dups enters G, INTERSECT ALL fails "
            f"with another identity and opens h3; surprises {surprises}; 6 records, surprise recomputed from the ledger")


GROUPS: dict[str, Callable[[], str]] = {
    "constants": check_constants,
    "language": check_language,
    "vspace": check_vspace,
    "hypothesis": check_hypothesis,
    "identity": check_identity,
    "residual": check_residual,
    "validity": check_validity,
    "predict": check_predict,
    "triage": check_triage,
    "theory": check_theory,
    "manifest": check_manifest,
    "walkthrough": check_walkthrough,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S6 gate (theory T core)")
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
    print(f"S06 GATE{scope}: {'PASS' if not failed else 'FAIL'}"
          f" ({len(selected) - failed}/{len(selected)} groups passed)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
