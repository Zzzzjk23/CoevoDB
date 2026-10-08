"""S5 gate: the shared language phi.

Usage (from ``framework/``)::

    python -m surprise.gates.s05                    # everything
    python -m surprise.gates.s05 --only vocab spec units

Exit code 0 = pass. Groups, following the S5 section of SESSIONS.md:

``vocab``        the base vocabulary of ``s05_cases.CORE_VOCAB`` with its
                 class hierarchy, the registry (ancestors, siblings, closure,
                 open families, invented features with provenance), and the
                 phi container;
``spec``         phi |= spec on hand-written feature sets;
``units``        the coarse projection of phi on hand-written feature sets;
``ast``          the ast layer on hand-written SQL and on the known families;
``dynamic``      the plan and data layers on real engines;
``stable``       phi is the same in two separate processes and in-process;
``distinguish``  the minimal repros of DF-A, DF-B and DuckDB F1-F11 are
                 pairwise distinguishable, with the measured units;
``specs``        the spec checker is right on every hand-written spec / SQL pair;
``corpus``       the unit distribution report over ``seeds/corpus.json``.

Tables live in ``s05_cases.py``. ``--only`` exists so a work package can run
the groups it delivers; the gate proper is all groups. Output is ASCII only.
"""
from __future__ import annotations

import argparse
import itertools
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from . import s04 as S4
from . import s05_cases as C

FRAMEWORK = Path(__file__).resolve().parents[2]
CHECKOUT = FRAMEWORK.parent
LAYERS = ("ast", "plan", "data")


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


def features_api() -> Any:
    from surprise import features

    return features


def case_of(name: str) -> Any:
    """A SqlCase by name: an S4 gate case, or one of the data probes."""
    from surprise.harness.contracts import SqlCase

    if name in C.DATA_PROBES:
        engine, setup, query, _have, _lack = C.DATA_PROBES[name]
        return SqlCase(engine=engine, setup=tuple(setup), query=query)
    return S4.load(name)


def full_sql(case: Any) -> str:
    from surprise.harness.oracles.forms import full_query

    return full_query(case)


def layer_of(feature: str) -> str:
    return feature.split(":", 1)[0]


def hand_phi(engine: str, features: tuple[str, ...], layers: dict[str, str]) -> Any:
    return features_api().make_phi(engine, features, dict(layers))


def cli(*args: str, stdin: str | None = None, timeout: float = 600.0) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "surprise.features", *args], cwd=FRAMEWORK, input=stdin,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
                          encoding="utf-8", errors="replace")


# ---- vocab -----------------------------------------------------------------

def check_vocab() -> str:
    F = features_api()
    registry = F.default_registry()
    for feature_id, (kind, parent, _meaning) in C.CORE_VOCAB.items():
        require(registry.known(feature_id), f"vocabulary lacks {feature_id}")
        definition = registry.get(feature_id)
        require((definition.kind, definition.parent) == (kind, parent),
                f"{feature_id}: kind/parent is {(definition.kind, definition.parent)}, expected {(kind, parent)}")
        require(definition.layer == layer_of(feature_id) == registry.layer(feature_id),
                f"{feature_id}: layer is {definition.layer!r}")
        require(definition.source == "base" and definition.accepted is True, f"{feature_id}: base features are accepted")
        require(isinstance(definition.description, str) and definition.description, f"{feature_id}: needs a description")
    for feature_id in registry.ids():
        definition = registry.get(feature_id)
        require(definition.parent is None or registry.get(definition.parent).kind in ("class", "family"),
                f"{feature_id}: parent {definition.parent!r} is not a class")
    for feature_id, expected in C.ANCESTORS.items():
        require(tuple(registry.ancestors(feature_id)) == expected,
                f"ancestors({feature_id}) is {registry.ancestors(feature_id)!r}, expected {expected!r}")
    for feature_id, expected in C.SIBLINGS.items():
        siblings = tuple(registry.siblings(feature_id))
        require(set(expected) <= set(siblings) and feature_id not in siblings and list(siblings) == sorted(siblings),
                f"siblings({feature_id}) is {siblings!r}, expected at least {expected!r}, sorted, without itself")
    require(set(registry.children("ast:set_op:all")) >= {"ast:set_op:union_all", "ast:set_op:except_all",
                                                           "ast:set_op:intersect_all"}, "children(ast:set_op:all) wrong")
    closure = registry.closure(["ast:set_op:except_all", "plan:HASH_JOIN", "data:setop:left_has_dups"])
    require(closure == frozenset({"ast:set_op:except_all", "ast:set_op:all", "ast:set_op", "ast", "plan:HASH_JOIN", "plan",
                                  "data:setop:left_has_dups", "data:setop", "data"}),
            f"closure adds every ancestor and nothing else, got {sorted(closure)}")
    # open families: any token under them is a leaf; nothing else is invented on the fly
    for member, family in (("plan:HASH_JOIN", "plan"), ("plan:HashJoinExec", "plan"), ("ast:fn:upper", "ast:fn")):
        require(registry.known(member), f"{member} belongs to the open family {family}")
        definition = registry.get(member)
        require((definition.kind, definition.parent, definition.layer) == ("leaf", family, layer_of(member)),
                f"{member}: {(definition.kind, definition.parent, definition.layer)}")
    for stranger in ("ast:no_such_feature", "plan", "nope:x", "data:setop:middle_has_dups", "ast:fn", "ast:fn:"):
        if stranger in ("plan", "ast:fn"):
            require(registry.get(stranger).kind == "family", f"{stranger} is a family, not a leaf")
        else:
            require(not registry.known(stranger), f"{stranger} must not be a known feature")
            expect_raises((KeyError, ValueError), lambda s=stranger: registry.get(s), f"get({stranger})")

    digest = registry.digest()
    require(isinstance(digest, str) and len(digest) == 64 and digest == F.default_registry().digest(),
            "digest must be a stable sha256 hex string")
    other = cli("vocab")
    require(other.returncode == 0 and digest in other.stdout, f"`features vocab` in another process: {other.stdout.strip()[-200:]} "
            f"{_ascii(other.stderr.strip()[-200:])}")

    # invented features: recorded with where they came from and how they were accepted
    invented = F.FeatureDef(feature_id="ast:expr:gate_marker", kind="leaf", parent="ast:expr", layer="ast",
                            description="mentions gate_marker", source="llm:vocabulary_inventor:gate",
                            definition={"kind": "regex", "pattern": r"\bgate_marker\b"}, accepted=False, acceptance=None)
    mine = F.default_registry()
    mine.register(invented)
    require(mine.known("ast:expr:gate_marker") and not registry.known("ast:expr:gate_marker"),
            "register() changes that registry only")
    require(mine.get("ast:expr:gate_marker").accepted is False and mine.digest() != digest,
            "an invented feature starts unaccepted and changes the digest")
    require("ast:expr:gate_marker" in mine.siblings("ast:expr:case"), "an invented leaf joins its class")
    bad = [
        ("a duplicate id", invented),
        ("a base source", F.FeatureDef(feature_id="ast:expr:other_marker", kind="leaf", parent="ast:expr", layer="ast",
                                       description="x", source="base", definition={"kind": "regex", "pattern": "x"},
                                       accepted=False, acceptance=None)),
        ("an unknown parent", F.FeatureDef(feature_id="ast:nowhere:x", kind="leaf", parent="ast:nowhere", layer="ast",
                                           description="x", source="llm:t", definition={"kind": "regex", "pattern": "x"},
                                           accepted=False, acceptance=None)),
        ("a parent in another layer", F.FeatureDef(feature_id="ast:expr:cross", kind="leaf", parent="data:table", layer="ast",
                                                   description="x", source="llm:t",
                                                   definition={"kind": "regex", "pattern": "x"}, accepted=False,
                                                   acceptance=None)),
        ("a leaf as parent", F.FeatureDef(feature_id="ast:expr:case:deep", kind="leaf", parent="ast:expr:case", layer="ast",
                                          description="x", source="llm:t", definition={"kind": "regex", "pattern": "x"},
                                          accepted=False, acceptance=None)),
        ("no executable definition", F.FeatureDef(feature_id="ast:expr:vague", kind="leaf", parent="ast:expr", layer="ast",
                                                  description="x", source="llm:t", definition=None, accepted=False,
                                                  acceptance=None)),
        ("a broken pattern", F.FeatureDef(feature_id="ast:expr:broken", kind="leaf", parent="ast:expr", layer="ast",
                                          description="x", source="llm:t", definition={"kind": "regex", "pattern": "("},
                                          accepted=False, acceptance=None)),
        ("an id outside its layer", F.FeatureDef(feature_id="plan:expr:x", kind="leaf", parent="ast:expr", layer="ast",
                                                 description="x", source="llm:t",
                                                 definition={"kind": "regex", "pattern": "x"}, accepted=False,
                                                 acceptance=None)),
    ]
    for what, definition in bad:
        expect_raises(ValueError, lambda d=definition: mine.register(d), f"register with {what}")
    acceptance = {"holdout": {"surprise_delta": -0.4, "records": 12}, "decided_by": "gate"}
    mine.accept("ast:expr:gate_marker", acceptance)
    accepted = mine.get("ast:expr:gate_marker")
    require(accepted.accepted is True and accepted.acceptance == acceptance and accepted.source.startswith("llm:"),
            "accept() records the acceptance result and keeps the provenance")
    expect_raises((KeyError, ValueError), lambda: mine.accept("ast:expr:case", acceptance), "accepting a base feature")
    with tempfile.TemporaryDirectory(prefix="s05-gate-") as tmp:
        path = Path(tmp) / "invented.json"
        mine.save(path)
        json.loads(path.read_text(encoding="utf-8"))
        loaded = F.Registry.load(path)
        require(loaded.digest() == mine.digest() and loaded.get("ast:expr:gate_marker") == accepted,
                "save / load must round-trip invented features with their acceptance")
        require(set(C.CORE_VOCAB) <= set(loaded.ids()), "a loaded registry still has the base vocabulary")

    # the phi container
    phi = F.make_phi("duckdb", ("plan:HASH_JOIN", "ast:set_op:except_all", "ast:stmt:select", "ast:set_op:except_all"),
                     {"ast": "ok", "plan": "ok", "data": "unavailable"})
    require(phi.features == ("ast:set_op:except_all", "ast:stmt:select", "plan:HASH_JOIN"),
            f"phi.features must be sorted and unique, got {phi.features!r}")
    require(phi.engine == "duckdb" and phi.vocab == digest and dict(phi.layers) == {"ast": "ok", "plan": "ok",
                                                                                 "data": "unavailable"}, "phi header wrong")
    as_dict = phi.to_dict()
    require(json.loads(json.dumps(as_dict, sort_keys=True)) == as_dict and F.Phi.from_dict(as_dict) == phi,
            "phi must round-trip through JSON")
    require(set(as_dict) == {"schema", "engine", "features", "layers", "vocab"} and as_dict["schema"] == 1,
            f"phi.to_dict() keys are {sorted(as_dict)}")
    bad_phis = [
        ("an unknown feature", ("ast:no_such_feature",), C.ALL_OK),
        ("a class instead of a leaf", ("ast:set_op:all",), C.ALL_OK),
        ("a family instead of a leaf", ("plan",), C.ALL_OK),
        ("a missing layer", ("ast:stmt:select",), {"ast": "ok", "plan": "ok"}),
        ("an unknown layer status", ("ast:stmt:select",), {"ast": "ok", "plan": "maybe", "data": "ok"}),
        ("fallback on a layer other than ast", ("ast:stmt:select",), {"ast": "ok", "plan": "fallback", "data": "ok"}),
        ("a feature of a layer that was not computed", ("ast:stmt:select", "plan:HASH_JOIN"),
         {"ast": "ok", "plan": "skipped", "data": "ok"}),
    ]
    for what, features, layers in bad_phis:
        expect_raises(ValueError, lambda f=features, l=layers: F.make_phi("duckdb", f, dict(l)), f"make_phi with {what}")
    leaves = sum(1 for _id, (kind, _p, _m) in C.CORE_VOCAB.items() if kind == "leaf")
    return (f"{len(C.CORE_VOCAB)} core entries ({leaves} leaves) with hierarchy; open families; digest {digest[:12]} stable "
            f"across processes; invented feature registered, {len(bad)} bad ones rejected, saved and loaded; phi container")


# ---- spec ------------------------------------------------------------------

def make_spec(fields: dict) -> Any:
    from surprise.theory.contracts import Spec

    return Spec(**fields)


def check_spec_group() -> str:
    F = features_api()
    for index, (engine, features, layers, fields, expected) in enumerate(C.SPEC_PROBES):
        result = F.check_spec(hand_phi(engine, features, layers), make_spec(fields))
        got = (result.ok, tuple(result.missing), tuple(result.forbidden), tuple(result.undetermined))
        require(got == expected, f"spec probe {index} {fields}: got {got}, expected {expected}")
        require(result.engine_ok is (fields["engine"] == engine), f"spec probe {index}: engine_ok is {result.engine_ok}")
    phi = hand_phi("duckdb", ("ast:stmt:select",), C.ALL_OK)
    for bad in (dict(required=("ast:no_such_feature",)), dict(forbidden=("nope",)), dict(data_properties=("ast:clause:where",))):
        expect_raises(ValueError, lambda b=bad: F.check_spec(phi, make_spec(dict(engine="duckdb", oracle="tlp", **b))),
                      f"check_spec with {bad}")
    return f"{len(C.SPEC_PROBES)} hand-written phi / spec pairs judged as expected; 3 malformed specs rejected"


# ---- units -----------------------------------------------------------------

def check_units() -> str:
    F = features_api()
    for engine, oracle, features, layers, expected in C.UNIT_PROBES:
        got = F.unit_of(hand_phi(engine, features, layers), oracle)
        require(got == expected, f"unit_of({engine}, {oracle}, {features}) is {got!r}, expected {expected!r}")
    phi = hand_phi("duckdb", ("ast:stmt:select",), C.ALL_OK)
    expect_raises(ValueError, lambda: F.unit_of(phi, "no_such_oracle"), "unit_of with an unknown oracle")
    return f"{len(C.UNIT_PROBES)} hand-written feature sets project onto the expected units"


# ---- ast -------------------------------------------------------------------

def ast_of(sql: str, engine: str, registry: Any = None) -> tuple[frozenset, str]:
    F = features_api()
    features, status = F.extract_ast(sql, engine) if registry is None else F.extract_ast(sql, engine, registry=registry)
    return frozenset(features), status


def family_ast() -> dict[str, frozenset]:
    out = {}
    for family, (case_name, _expected) in C.FAMILIES.items():
        case = case_of(case_name)
        features, status = ast_of(full_sql(case), case.engine)
        require(status == "ok", f"{family}: sqlglot parses the minimal repro, status is {status!r}")
        out[family] = features
    return out


def check_pairwise(by_family: dict[str, frozenset], what: str) -> int:
    pairs = 0
    for left, right in itertools.combinations(sorted(by_family), 2):
        require(by_family[left] != by_family[right],
                f"{what}: {left} and {right} have the same features: {sorted(by_family[left])}")
        pairs += 1
    return pairs


def check_ast() -> str:
    F = features_api()
    registry = F.default_registry()
    for engine, sql, have, lack in C.AST_PROBES:
        features, status = ast_of(sql, engine)
        where = f"ast probe {sql[:70]!r}"
        require(status == "ok", f"{where}: status is {status!r}")
        for feature in features:
            require(registry.known(feature) and registry.get(feature).kind == "leaf" and layer_of(feature) == "ast",
                    f"{where}: emitted {feature!r}, which is not an ast leaf of the vocabulary")
        missing = sorted(set(have) - features)
        unwanted = sorted(set(lack) & features)
        require(not missing and not unwanted,
                f"{where}: missing {missing}, unwanted {unwanted}; got {sorted(features)}")
        require(("ast:parse:fallback" in features) is False, f"{where}: parsed statements are not marked fallback")
        again, _ = ast_of(sql, engine)
        require(again == features, f"{where}: two extractions differ")
    for engine, sql, ids in C.FALLBACK_PROBES:
        features, status = ast_of(sql, engine)
        closure = registry.closure(features)
        require(status == "fallback" and set(ids) <= closure,
                f"fallback probe {sql[:60]!r}: status {status!r}, closure lacks {sorted(set(ids) - closure)}")
    for left, right in C.AST_INVARIANT:
        a, _ = ast_of(left, "duckdb")
        b, _ = ast_of(right, "duckdb")
        require(a == b, f"names, case, layout and comments are not features: {sorted(a ^ b)} differ for {left[:50]!r}")
    by_family = family_ast()
    for family, (_case, expected) in C.FAMILIES.items():
        missing = sorted(set(expected) - by_family[family])
        require(not missing, f"{family}: ast features lack {missing}; got {sorted(by_family[family])}")
    pairs = check_pairwise(by_family, "ast layer")
    require(by_family["DF-A"] ^ by_family["DF-B"] == {"ast:set_op:except_all", "ast:set_op:intersect_all"},
            f"DF-A and DF-B differ in the set operation only: {sorted(by_family['DF-A'] ^ by_family['DF-B'])}")
    # an invented feature is emitted only once it has been accepted
    mine = F.default_registry()
    mine.register(F.FeatureDef(feature_id="ast:expr:gate_marker", kind="leaf", parent="ast:expr", layer="ast",
                               description="mentions gate_marker", source="llm:vocabulary_inventor:gate",
                               definition={"kind": "regex", "pattern": r"\bgate_marker\b"}, accepted=False, acceptance=None))
    marked = "SELECT gate_marker FROM t"
    require("ast:expr:gate_marker" not in ast_of(marked, "duckdb", mine)[0], "an unaccepted feature must not be emitted")
    mine.accept("ast:expr:gate_marker", {"decided_by": "gate"})
    require("ast:expr:gate_marker" in ast_of(marked, "duckdb", mine)[0]
            and "ast:expr:gate_marker" not in ast_of("SELECT a FROM t", "duckdb", mine)[0]
            and "ast:expr:gate_marker" not in ast_of(marked, "duckdb")[0],
            "an accepted regex feature is emitted exactly where its pattern matches, by its own registry")
    return (f"{len(C.AST_PROBES)} probes, {len(C.FALLBACK_PROBES)} fallbacks, {len(C.AST_INVARIANT)} invariance pairs; "
            f"{len(by_family)} families show their core features and are pairwise distinct ({pairs} pairs)")


# ---- dynamic ---------------------------------------------------------------

def phi_of(name: str, **kwargs: Any) -> Any:
    return features_api().extract(case_of(name), **kwargs)


def check_dynamic() -> str:
    from surprise.harness.contracts import SqlCase

    F = features_api()
    registry = F.default_registry()
    for name, (_engine, _setup, _query, have, lack) in C.DATA_PROBES.items():
        phi = phi_of(name)
        features = set(phi.features)
        require(dict(phi.layers) == C.ALL_OK, f"data probe {name}: layers are {dict(phi.layers)}")
        missing = sorted(set(have) - features)
        unwanted = sorted(set(lack) & features)
        require(not missing and not unwanted, f"data probe {name}: missing {missing}, unwanted {unwanted}; "
                f"data features {sorted(f for f in features if f.startswith('data:'))}")
        for feature in features:
            require(registry.known(feature) and registry.get(feature).kind == "leaf",
                    f"data probe {name}: {feature!r} is not a leaf of the vocabulary")
        require(phi_of(name) == phi, f"data probe {name}: two extractions differ")
    for name, expected in C.PLAN_FEATURES.items():
        phi = phi_of(name)
        missing = sorted(set(expected) - set(phi.features))
        require(phi.layers["plan"] == "ok" and not missing,
                f"plan of {name}: missing {missing}; got {sorted(f for f in phi.features if f.startswith('plan:'))}")
    engine, setup, query = C.BROKEN_SETUP
    broken = F.extract(SqlCase(engine=engine, setup=setup, query=query))
    require(dict(broken.layers) == {"ast": "ok", "plan": "unavailable", "data": "unavailable"}
            and all(f.startswith("ast:") for f in broken.features) and "ast:clause:where" in broken.features,
            f"a failing setup leaves only the ast layer: {broken.to_dict()}")
    only_ast = F.extract(case_of("F1"), layers=("ast",))
    require(dict(only_ast.layers) == {"ast": "ok", "plan": "skipped", "data": "skipped"}
            and all(f.startswith("ast:") for f in only_ast.features), f"layers=('ast',): {only_ast.to_dict()}")
    foreign = F.extract(SqlCase(engine="postgres", setup=(), query="SELECT a FROM t JOIN u USING (k)"), layers=("ast",))
    require(foreign.engine == "postgres" and "ast:join_cond:using" in foreign.features,
            "the ast layer works for engines that have no runner here")
    expect_raises(ValueError, lambda: F.extract(SqlCase(engine="postgres", setup=(), query="SELECT 1")),
                  "plan and data layers for an engine without a runner")
    # the calling process survives a statement that kills the engine
    fatal = case_of("F10_q1")
    isolated = F.extract_isolated(fatal)
    require(isolated.layers["ast"] == "ok" and "ast:window_trait:ordered_arg" in isolated.features,
            f"extract_isolated on the fatal F10 statement: {isolated.to_dict()}")
    same = F.extract_isolated(case_of("DF-A"))
    require(same == phi_of("DF-A"), "extract_isolated must equal extract on a harmless case")
    return (f"{len(C.DATA_PROBES)} data probes on two engines, {len(C.PLAN_FEATURES)} measured plans; failing setup, "
            "ast-only and isolated extraction behave")


# ---- stable ----------------------------------------------------------------

def corpus_seeds() -> list[dict]:
    return json.loads((FRAMEWORK / "seeds" / "corpus.json").read_text(encoding="utf-8"))


def check_stable() -> str:
    from surprise.harness.contracts import SqlCase

    F = features_api()
    cases = [case_of(case_name) for case_name, _expected in C.FAMILIES.values()]
    duckdb_seeds = [seed for seed in corpus_seeds() if seed["engine"] == "duckdb"]
    for seed in duckdb_seeds[::65]:
        cases.append(SqlCase(engine="duckdb", setup=tuple(seed["setup_sqls"]), query=seed["query"]))
    checked = 0
    for case in cases:
        request = json.dumps({"case": case.to_dict()})
        runs = [cli("phi", stdin=request, timeout=120.0) for _ in range(2)]
        for run in runs:
            require(run.returncode == 0, f"`features phi` failed on {case.query[:60]!r}: {_ascii(run.stderr.strip()[-300:])}")
        first, second = (run.stdout.strip().splitlines()[-1] for run in runs)
        require(first == second, f"phi differs between two processes for {case.query[:60]!r}")
        here = F.extract(case)
        require(json.loads(first) == here.to_dict(), f"phi in another process differs from phi here for {case.query[:60]!r}")
        require(first == json.dumps(here.to_dict(), sort_keys=True, separators=(",", ":")),
                "`features phi` prints canonical JSON: sorted keys, no spaces")
        checked += 1
    return f"{checked} cases ({len(C.FAMILIES)} families, {checked - len(C.FAMILIES)} corpus seeds): two processes and this one agree"


# ---- distinguish -----------------------------------------------------------

def check_distinguish() -> str:
    F = features_api()
    registry = F.default_registry()
    phis = {family: phi_of(case_name) for family, (case_name, _expected) in C.FAMILIES.items()}
    for family, phi in phis.items():
        require(dict(phi.layers) == C.ALL_OK, f"{family}: every layer must be computed, got {dict(phi.layers)}")
        missing = sorted(set(C.FAMILIES[family][1]) - set(phi.features))
        require(not missing, f"{family}: phi lacks {missing}")
    ast_only = {family: frozenset(f for f in phi.features if f.startswith("ast:")) for family, phi in phis.items()}
    pairs = check_pairwise(ast_only, "statement text alone")
    check_pairwise({family: frozenset(phi.features) for family, phi in phis.items()}, "phi")
    # the two DataFusion families: one swap inside a feature class turns one phi into the other
    a, b = set(phis["DF-A"].features), set(phis["DF-B"].features)
    require("ast:set_op:intersect_all" in registry.siblings("ast:set_op:except_all"), "INTERSECT ALL is a sibling of EXCEPT ALL")
    require((a - {"ast:set_op:except_all"}) | {"ast:set_op:intersect_all"} == b,
            f"swapping the set operation in phi(DF-A) must give phi(DF-B); they differ by {sorted(a ^ b)}")
    require("data:setop:left_has_dups" in a and "data:setop:left_has_dups" not in set(phi_of("no_dups").features),
            "left_has_dups follows the data, not the statement")
    for family, (oracle, expected) in C.UNITS.items():
        got = F.unit_of(phis[family], oracle)
        require(got == expected, f"unit of {family} is {got!r}, expected {expected!r}")
    require(F.unit_of(phis["DF-A"], "cross_dbms") == F.unit_of(phis["DF-B"], "cross_dbms"),
            "a unit is coarser than phi: DF-A and DF-B share one")
    return (f"{len(phis)} families: pairwise distinct by statement text alone ({pairs} pairs) and by phi; "
            f"DF-A -> DF-B is one sibling swap; {len(C.UNITS)} measured units")


# ---- specs -----------------------------------------------------------------

def check_specs() -> str:
    F = features_api()
    cache: dict[str, Any] = {}
    wrong = []
    for name, fields, expected in C.SPEC_PAIRS:
        if name not in cache:
            cache[name] = phi_of(name)
        result = F.check_spec(cache[name], make_spec(fields))
        if result.ok is not expected:
            wrong.append((name, fields, result.ok, tuple(result.missing), tuple(result.forbidden), tuple(result.undetermined)))
    require(not wrong, f"{len(wrong)} of {len(C.SPEC_PAIRS)} spec / SQL pairs judged wrongly, first: {wrong[:2]}")
    return f"{len(C.SPEC_PAIRS)} hand-written spec / SQL pairs, all judged correctly"


# ---- corpus ----------------------------------------------------------------

def check_corpus() -> str:
    with tempfile.TemporaryDirectory(prefix="s05-gate-") as tmp:
        out = Path(tmp) / "units.json"
        started = time.monotonic()
        run = cli("corpus", "--corpus", str(FRAMEWORK / "seeds" / "corpus.json"), "--out", str(out), timeout=1800.0)
        elapsed = time.monotonic() - started
        require(run.returncode == 0 and out.is_file(), f"`features corpus` failed: {_ascii(run.stderr.strip()[-400:])}")
        report = json.loads(out.read_text(encoding="utf-8"))
        again = cli("corpus", "--corpus", str(FRAMEWORK / "seeds" / "corpus.json"), "--out", str(Path(tmp) / "again.json"),
                    timeout=1800.0)
        require(again.returncode == 0 and json.loads((Path(tmp) / "again.json").read_text(encoding="utf-8")) == report,
                "the corpus report must be the same on a second run")
    expected = C.CORPUS
    require(report.get("total") == expected["total"]
            and report.get("by_engine") == {"duckdb": expected["duckdb"], "postgres": expected["postgres"]},
            f"corpus size: {report.get('total')} {report.get('by_engine')}")
    layers = report.get("layers", {})
    ast = layers.get("ast", {})
    require(ast.get("ok", 0) + ast.get("fallback", 0) == expected["total"]
            and 17 <= ast.get("fallback", 0) <= expected["sqlglot_failures"],
            f"ast layer over the corpus: {ast} (sqlglot alone fails on {expected['sqlglot_failures']})")
    plan, data = layers.get("plan", {}), layers.get("data", {})
    for name, counts in (("plan", plan), ("data", data)):
        require(sum(counts.values()) == expected["total"] and counts.get("skipped") == expected["postgres"],
                f"{name} layer: every postgres seed is skipped, every seed is counted: {counts}")
    require(450 <= data.get("ok", 0) <= expected["duckdb_setup_ok"],
            f"data layer ok for {data.get('ok')} seeds; {expected['duckdb_setup_ok']} seeds have a clean setup")
    require(400 <= plan.get("ok", 0) <= expected["duckdb_setup_ok"], f"plan layer ok for {plan.get('ok')} seeds")
    units = report.get("units", {})
    require(sum(units.values()) == expected["total"] and report.get("distinct_units") == len(units),
            "every seed falls into exactly one unit")
    for unit in units:
        parts = unit.split("|")
        require(len(parts) == 4 and parts[0] in ("duckdb", "postgres"), f"unit key {unit!r} is engine|construct|plan|data")
    constructs = report.get("constructs", {})
    require(sum(constructs.values()) == expected["total"] and len(constructs) >= 7,
            f"the corpus should spread over at least 7 constructs, got {constructs}")
    biggest = max(units.values())
    require(biggest < 0.5 * expected["total"], f"one unit holds {biggest} of {expected['total']} seeds: the projection is degenerate")
    top = sorted(units.items(), key=lambda item: (-item[1], item[0]))[:3]
    return (f"{expected['total']} seeds in {len(units)} units over {len(constructs)} constructs; ast fallback {ast.get('fallback')}, "
            f"plan ok {plan.get('ok')}, data ok {data.get('ok')}; top {top}; {elapsed:.0f}s")


GROUPS: dict[str, Callable[[], str]] = {
    "vocab": check_vocab,
    "spec": check_spec_group,
    "units": check_units,
    "ast": check_ast,
    "dynamic": check_dynamic,
    "stable": check_stable,
    "distinguish": check_distinguish,
    "specs": check_specs,
    "corpus": check_corpus,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S5 gate (phi)")
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
    print(f"S05 GATE{scope}: {'PASS' if not failed else 'FAIL'}"
          f" ({len(selected) - failed}/{len(selected)} groups passed)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
