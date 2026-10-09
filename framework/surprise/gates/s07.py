"""S7 gate: storing the theory, and the rules that decide which edits it accepts.

Usage (from ``framework/``)::

    python -m surprise.gates.s07                        # everything
    python -m surprise.gates.s07 --only constants length theory_api store generations

Exit code 0 = pass. Groups, following the S7 section of SESSIONS.md:

``constants``    the four constants S7 adds have the planned values and reach the
                 run manifest; the nine of S6 are untouched;
``length``       the description length of a hypothesis and of a theory;
``theory_api``   the small additions to ``Theory`` and to the conjunction language;
``store``        one structured file per hypothesis, a strict loader, append-only logs;
``generations``  a snapshot of the closing state of every generation;
``imports``      the new modules load in any order and reach for no model or old code;
``edits``        proposals, claims, fingerprints, bets;
``accept``       the acceptance test: no worse on the trigger records, no worse on
                 the held-out records, and shorter in surprise plus length;
``rollback``     a lost bet rolls the edit back, and what follows it, and the claim
                 enters the negative memory, which refuses it from then on;
``journal``      a reopened workbench is the same workbench;
``mdl``          merging, tightening and splitting hypotheses by description length;
``families``     which family a failure belongs to, across oracles and through edits;
``ciao``         mean surprise of old records under each generation;
``replay``       known reproductions and regenerated DCE probes fed offline on the
                 real engines: the five magnitudes, duplicates recognised before
                 execution, one deliberately wrong edit rolled back;
``ledger``       the family partition agrees with the manual ledger at least as well
                 as sigma, the family key of the old system.

Tables live in ``s07_cases.py``; the hand-made phi and labels are those of the S6 gate.
``--only`` exists so a work package can run the groups it delivers. PostgreSQL
reference: COEVO_REFERENCE_PG_DSN or local port 55432 (see HANDOFF). Output is ASCII only.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from . import s06 as G6
from . import s06_cases as C6
from . import s07_cases as C
from .s06 import GateFailure, _ascii, bits, close, expect_raises, require, tuples

FRAMEWORK = Path(__file__).resolve().parents[2]
ENGINE, ORACLE = "datafusion", "cross_dbms"
NEW_MODULES = ("length", "store", "edits", "workbench")
IMPORT_ORDERS = (
    "import surprise.theory.workbench",
    "import surprise.theory.store, surprise.theory.edits",
    "import surprise.features, surprise.theory.workbench",
    "import surprise.features.spec, surprise.theory.edits, surprise.theory",
    "import surprise.harness.evaluate, surprise.theory.workbench, surprise.features",
)
# x1 with the duplicates on the right only; a UNION ALL that happens to be planned with a hash join
Z_RIGHT = (C6.EXC_ALL, C6.SELECT, C6.R_DUPS, C6.R_NULL, C6.INT, C6.SRC, C6.HJ)
W_UNION = (C6.UNI_ALL, C6.SELECT, C6.L_DUPS, C6.L_NULL, C6.R_NULL, C6.T_DUPS, C6.T_NULL, C6.INT, C6.SRC, C6.HJ)
NO_PLAN = (C6.EXC_ALL, C6.SELECT, C6.L_DUPS, C6.T_DUPS, C6.INT)
NO_PLAN_LAYERS = {"ast": "ok", "plan": "unavailable", "data": "ok"}

phi, fail_label, pass_label, invalid_label = G6.phi, G6.fail_label, G6.pass_label, G6.invalid_label


def api() -> Any:
    from surprise import theory

    return theory


def spec(required: Any, forbidden: Any = (), *, engine: str = ENGINE, oracle: str = ORACLE) -> dict[str, Any]:
    return api().Spec(engine=engine, oracle=oracle, required=tuple(required), forbidden=tuple(forbidden)).to_dict()


def bet(required: Any, forbidden: Any = (), expect: str = "fail", **scope: str) -> dict[str, Any]:
    return {"spec": spec(required, forbidden, **scope), "expect": expect}


def static_bits(theory: Any, example: Any, oracle: str, y: str) -> float:
    """Surprise of a past record under a theory as it stands, computed with the S6 primitives alone."""
    return api().surprise_bits(theory.predict(example, oracle).p_fail_valid, y)


def ids(theory: Any) -> tuple[str, ...]:
    return tuple(h.hypothesis_id for h in theory.hypotheses)


def reworded(wb: Any, hypothesis_id: str, specific: tuple[str, ...]) -> Any:
    return dataclasses.replace(wb.theory.get(hypothesis_id), specific=specific, source="hand-written")


H2_BETS = (bet([C6.EXC_ALL], [C6.L_DUPS], "pass"), bet([C6.INT_ALL, C6.L_DUPS], (), "fail"))


def opened_bench(tmp: str, name: str = "store") -> tuple[Any, str]:
    """A workbench that has seen DF-A once. Returns it with the id of the family that opened."""
    wb = api().Workbench.create(Path(tmp) / name)
    out = wb.observe(phi("x1"), fail_label("df_missing"), "r1")
    require(out.observation.opened and out.owner == out.observation.opened and wb.generation == 0,
            f"the first profiled failure opens a family and owns its record: {out}")
    return wb, out.observation.opened


def hand_h2(wb: Any, first: str) -> Any:
    """The hand-written h2 of the framework document, proposed as an edit with its two bets."""
    T = api()
    return wb.propose(T.Proposal(kind="revise", rationale="EXCEPT ALL is evaluated as a distinct EXCEPT", proposer="hand",
                                 removes=(first,), adds=(reworded(wb, first, C6.S_HAND),), bets=H2_BETS, trigger=("r1",)))


def settled_bench(tmp: str, name: str = "store") -> tuple[Any, str, str]:
    """DF-A, the hand-written h2, and both of its bets kept: x3 passes, INTERSECT ALL fails as another bug."""
    wb, first = opened_bench(tmp, name)
    edit = hand_h2(wb, first)
    require(edit.decision == "accepted", f"the hand-written h2 must be accepted: {edit.to_dict()}")
    h2 = edit.payload["adds"][0]
    wb.observe(phi("x3"), pass_label(), "r2")
    out = wb.observe(phi("x4"), fail_label("df_extra", attribution=(h2, False)), "r3")
    require(out.observation.opened, f"INTERSECT ALL opens its own family: {out}")
    return wb, h2, out.observation.opened


# ---- constants -----------------------------------------------------------------

def check_constants() -> str:
    from surprise.harness import constants as harness_constants
    from surprise.theory import constants

    T = api()
    got = constants.as_dict()
    require(G6.pinned(got) == C6.CONSTANTS, f"the nine constants of S6 must not move: {G6.pinned(got)}")
    for name, value in C.CONSTANTS.items():
        require(name in got and got[name] == value and type(getattr(constants, name)) is type(value),
                f"constants.{name} is {got.get(name)!r}, expected {value!r} of type {type(value).__name__}")
    require(not set(C.CONSTANTS) & set(harness_constants.as_dict()), "the new constants stay out of the frozen harness")
    section = T.theory_manifest()
    require(all(section["constants"].get(name) == value for name, value in C.CONSTANTS.items()),
            "the new constants must reach the theory section of the run manifest")
    require(T.verify_theory_manifest({"harness": {}, "constants": {}, "theory": section}) == [],
            "a manifest written now verifies")
    stale = json.loads(json.dumps(section))
    stale["constants"]["MDL_LITERAL_BITS"] = 1.0
    found = T.verify_theory_manifest({"harness": {}, "constants": {}, "theory": stale})
    require(any("MDL_LITERAL_BITS" in line for line in found), f"a changed S7 constant must be reported by name: {found}")
    cost = C.CONSTANTS["MDL_HYPOTHESIS_BITS"] + C.CONSTANTS["MDL_LITERAL_BITS"]
    require(bits(0.05) < cost < 4 * bits(0.05), "one contradiction never pays for a hypothesis, a handful does")
    return f"{len(C.CONSTANTS)} new constants beside the nine of S6, all in the manifest; a change is reported by name"


# ---- length --------------------------------------------------------------------

def check_length() -> str:
    T = api()
    per, lit = C.CONSTANTS["MDL_HYPOTHESIS_BITS"], C.CONSTANTS["MDL_LITERAL_BITS"]
    one = G6.hand_hypothesis(C6.S_X1, C6.TOP)
    two = G6.hand_hypothesis(C6.S_HAND, ((C6.L_DUPS,),), hypothesis_id="h-two")
    require(close(T.hypothesis_length(one), per + lit * 10, 1e-9) and close(T.hypothesis_length(two), per + lit * 2, 1e-9),
            f"length = {per} + {lit} per literal of S: {T.hypothesis_length(one)!r}, {T.hypothesis_length(two)!r}")
    wide = dataclasses.replace(two, general=((), (C6.L_DUPS,), (C6.EXC_ALL,)), positives=("a", "b"), negatives=("c",))
    require(T.hypothesis_length(wide) == T.hypothesis_length(two), "G and the evidence lists do not enter the length")
    theory = T.Theory()
    require(T.theory_length(theory) == 0.0 and isinstance(T.theory_length(theory), float), "an empty theory has length 0.0")
    theory.put(one)
    theory.put(two)
    require(close(T.theory_length(theory), 2 * per + 12 * lit, 1e-9) and close(T.theory_length([one, two]), 2 * per + 12 * lit, 1e-9),
            "the length of a theory is the sum over its hypotheses, given a Theory or a sequence")
    return f"hypothesis = {per} + {lit} x |S| bits; theory = sum"


# ---- theory_api ----------------------------------------------------------------

def check_theory_api() -> str:
    T = api()
    theory, _seen = G6.scripted_walk(T)
    first, second = ids(theory)
    start = theory.next_id
    require(start == theory.to_dict()["next_id"], "Theory.next_id mirrors the saved counter")
    minted = theory.reserve_id()
    require(minted == f"h{start}" and theory.next_id == start + 1 and ids(theory) == (first, second),
            f"reserve_id mints the id a new family would get and creates nothing: {minted!r}")
    theory.put(G6.hand_hypothesis(C6.S_X4, C6.TOP, hypothesis_id=f"h{start + 1}", identity="h_extra"))
    require(theory.reserve_id() == f"h{start + 2}", "reserve_id skips an id that is taken")
    gone = theory.remove(first)
    require(gone.hypothesis_id == first and first not in ids(theory) and len(ids(theory)) == 2,
            "remove returns the hypothesis it took out")
    expect_raises(KeyError, lambda: theory.remove(first), "removing an unknown id")
    expect_raises(KeyError, lambda: theory.get(first), "a removed hypothesis is gone")
    passes = theory.passes(ENGINE, ORACLE)
    stored = theory.to_dict()["passes"][f"{ENGINE}|{ORACLE}"]
    require([(p.to_dict(), r) for p, r in passes] == [(row["phi"], row["record_id"]) for row in stored]
            and isinstance(passes, tuple) and theory.passes("duckdb", "tlp") == (),
            "passes(engine, oracle) lists what the theory remembers for one scope, oldest first")
    # the least general conjunction two conjunctions share
    names = sorted(C6.PHI)
    for a in names:
        for b in names:
            left, right = T.reduce_conjunction(C6.PHI[a]), T.reduce_conjunction(C6.PHI[b])
            shared = T.common_conjunction(left, right)
            require(shared == T.generalize(left, phi(b)) == T.common_conjunction(right, left),
                    f"common_conjunction({a}, {b}) = {shared}, generalize says {T.generalize(left, phi(b))}")
            require(T.covers(shared, phi(a)) and T.covers(shared, phi(b)), f"the shared conjunction of {a}, {b} covers both")
    require(T.common_conjunction(C6.S_X1, C6.S_X1) == C6.S_X1 and T.common_conjunction(C6.S_X1, ()) == ()
            and T.common_conjunction((C6.EXC_ALL,), (C6.INT_ALL,)) == (C6.SET_ALL,),
            "idempotent; nothing shared with the empty conjunction; siblings meet at their class")
    expect_raises(ValueError, lambda: T.common_conjunction(("no:such:feature",), C6.S_X1), "an unknown feature")
    return f"remove, reserve_id, passes, next_id; common_conjunction agrees with generalize on {len(names) ** 2} pairs"


# ---- store ---------------------------------------------------------------------

def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, sort_keys=True, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def damaged(source: Path, tmp: str, name: str, change: Callable[[Path], None]) -> Any:
    """A copy of a good store with one thing wrong."""
    target = Path(tmp) / name
    shutil.copytree(source, target)
    change(target)
    return api().TheoryStore.open(target)


def check_store() -> str:
    T = api()
    theory, _seen = G6.scripted_walk(T)
    first, second = ids(theory)
    cases = 0
    with tempfile.TemporaryDirectory(prefix="s07-gate-") as tmp:
        root = Path(tmp) / "store"
        store = T.TheoryStore.create(root)
        require(issubclass(T.StoreError, ValueError) and store.root == root, "StoreError is a ValueError; the store knows its root")
        require((root / "head.json").is_file() and (root / "hypotheses").is_dir() and store.generations() == []
                and store.load().to_dict() == T.Theory().to_dict() and store.journal() == [] and store.edits() == []
                and store.negatives() == [] and store.verify() == [],
                "a new store holds an empty theory, empty logs and no closed generation")
        expect_raises(T.StoreError, lambda: T.TheoryStore.create(root), "creating over an existing store")
        expect_raises(T.StoreError, lambda: T.TheoryStore.open(Path(tmp) / "nowhere"), "opening a directory that is not a store")
        store.save(theory)
        files = sorted(path.name for path in (root / "hypotheses").iterdir())
        require(files == sorted(f"{name}.json" for name in (first, second)), f"one file per hypothesis, named by its id: {files}")
        for hypothesis in theory.hypotheses:
            require(read_json(root / "hypotheses" / f"{hypothesis.hypothesis_id}.json") == hypothesis.to_dict(),
                    f"{hypothesis.hypothesis_id}.json holds exactly Hypothesis.to_dict()")
        head = store.head()
        require(head["hypotheses"] == [first, second] and head["version"] == theory.version and head["generation"] == 0
                and head["next_id"] == theory.next_id and head["schema"] == 1, f"head.json describes the saved state: {head}")
        loaded = T.TheoryStore.open(root).load()
        require(loaded.to_dict() == theory.to_dict() and loaded.version == theory.version, "save then load is the identity")
        probe = phi("x7")
        require(loaded.predict(probe, ORACLE).to_dict() == theory.predict(probe, ORACLE).to_dict(), "a loaded theory predicts the same")
        leftovers = [path.name for path in root.rglob("*") if path.name.endswith(".tmp")]
        require(not leftovers, f"no temporary file is left behind: {leftovers}")
        # saving a smaller theory removes the file of the hypothesis that left
        smaller = T.Theory.from_dict(theory.to_dict())
        smaller.remove(first)
        store.save(smaller)
        require(sorted(path.name for path in (root / "hypotheses").iterdir()) == [f"{second}.json"]
                and store.load().to_dict() == smaller.to_dict(), "a hypothesis that left the theory leaves the directory")
        store.save(theory)
        # ids that cannot be file names never reach the disk
        for bad in ("../escape", "a/b", "a\\b", ".hidden", "x" * 80, "con:1"):
            odd = T.Theory.from_dict(theory.to_dict())
            odd.put(G6.hand_hypothesis(C6.S_X4, C6.TOP, hypothesis_id=bad, identity="h_extra"))
            expect_raises(T.StoreError, lambda odd=odd: store.save(odd), f"saving a hypothesis called {bad!r}")
            cases += 1
        require(not (Path(tmp) / "escape.json").exists() and store.load().to_dict() == theory.to_dict(),
                "a refused save writes nothing outside the store and leaves the saved state readable")

        # the strict loader: every one of these is a StoreError, never a quietly repaired theory
        def edit_file(relative: str, change: Callable[[Any], Any]) -> Callable[[Path], None]:
            def apply(target: Path) -> None:
                write_json(target / relative, change(read_json(target / relative)))
            return apply

        def swap(item: dict[str, Any]) -> dict[str, Any]:
            return {**item, "specific": list(reversed(item["specific"]))}

        def duplicate_pass(target: Path) -> None:
            path = next((target / "passes").iterdir())
            text = path.read_text(encoding="utf-8")
            path.write_text(text + text.split("\n")[0] + "\n", encoding="utf-8", newline="\n")

        def foreign_pass(target: Path) -> None:
            path = next((target / "passes").iterdir())
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line]
            rows[0]["phi"]["vocab"] = "0" * 64
            path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8", newline="\n")

        bad_stores: dict[str, Callable[[Path], None]] = {
            "a hypothesis file changed by hand": edit_file(f"hypotheses/{first}.json", lambda d: {**d, "specific": d["specific"][:-1]}),
            "a hypothesis file not in canonical form": edit_file(f"hypotheses/{first}.json", swap),
            "a hypothesis file missing": lambda target: (target / "hypotheses" / f"{first}.json").unlink(),
            "a stray hypothesis file": lambda target: shutil.copyfile(target / "hypotheses" / f"{first}.json",
                                                                      target / "hypotheses" / "h99.json"),
            "a file holding another id": edit_file(f"hypotheses/{first}.json", lambda d: {**d, "hypothesis_id": second}),
            "a hypothesis file that is not JSON": lambda target: (target / "hypotheses" / f"{first}.json").write_text("{", encoding="utf-8"),
            "the same pass twice": duplicate_pass,
            "a pass of another vocabulary": foreign_pass,
            "residual counts changed by hand": edit_file("residual.json", lambda d: {**d, "made|up|unit|x|y": {"tested": 3, "unexplained": 1}}),
            "an impossible residual row": edit_file("residual.json", lambda d: {**d, "u": {"tested": 1, "unexplained": 2}}),
            "next_id changed by hand": edit_file("head.json", lambda d: {**d, "next_id": d["next_id"] + 5}),
            "the list of hypotheses reordered": edit_file("head.json", lambda d: {**d, "hypotheses": list(reversed(d["hypotheses"]))}),
        }
        for what, change in bad_stores.items():
            broken = damaged(root, tmp, f"bad{cases}", change)
            expect_raises(T.StoreError, broken.load, what)
            problems = broken.verify()
            require(problems and all(isinstance(line, str) and line.isascii() for line in problems),
                    f"{what}: verify() must report it in ASCII, got {problems!r}")
            cases += 1
        bad_heads: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "a head of another schema": lambda d: {**d, "schema": 2},
            "a head of another vocabulary": lambda d: {**d, "vocab": "0" * 64},
            "a head with a key missing": lambda d: {k: v for k, v in d.items() if k != "version"},
            "a head naming a hypothesis twice": lambda d: {**d, "hypotheses": d["hypotheses"] + d["hypotheses"][:1]},
        }
        for what, change in bad_heads.items():
            target = Path(tmp) / f"bad{cases}"
            shutil.copytree(root, target)
            write_json(target / "head.json", change(read_json(target / "head.json")))
            expect_raises(T.StoreError, lambda target=target: T.TheoryStore.open(target).load(), what)
            cases += 1
        require(store.load().to_dict() == theory.to_dict() and store.verify() == [], "the original store is untouched and verifies")

        # append-only logs
        require(store.last_seq == 0 and store.append_journal({"kind": "note", "text": "a"}) == 1
                and store.append_journal({"kind": "note", "text": "b"}) == 2 and store.last_seq == 2, "journal entries are numbered from 1")
        require(store.journal() == [{"kind": "note", "text": "a", "seq": 1}, {"kind": "note", "text": "b", "seq": 2}]
                and store.journal(after=1) == [{"kind": "note", "text": "b", "seq": 2}], "journal(after=n) returns the later entries")
        for bad_entry in ({"text": "no kind"}, {"kind": "x", "seq": 9}, "text", {"kind": 3}):
            expect_raises(ValueError, lambda bad_entry=bad_entry: store.append_journal(bad_entry), f"journal entry {bad_entry!r}")
        reopened = T.TheoryStore.open(root)
        require(reopened.append_journal({"kind": "note", "text": "c"}) == 3 and len(store.journal()) == 3, "a reopened store continues the numbering")
        one = T.TheoryEdit(edit_id="e1", kind="revise", rationale="why", bets=({"spec": spec([C6.EXC_ALL]), "expect": "fail"},),
                           surprise_delta_in=-1.0, surprise_delta_out=0.0, decision="accepted", proposer="gate",
                           theory_version=theory.version, payload={"adds": ["h9"]})
        later = dataclasses.replace(one, decision="rolled_back")
        other = dataclasses.replace(one, edit_id="e2")
        for edit in (one, other, later):
            store.append_edit(edit)
        require(store.edit_history() == [one, other, later] and store.edits() == [later, other],
                "edits.jsonl keeps every line; edits() gives the latest state of each edit in order of first appearance")
        expect_raises(ValueError, lambda: store.append_edit(one.to_dict()), "append_edit takes a TheoryEdit")
        store.append_negative({"fingerprint": "abc", "edit_id": "e1"})
        require(store.negatives() == [{"fingerprint": "abc", "edit_id": "e1"}], "negative.jsonl returns what was appended")
        for bad_entry in ({}, {"fingerprint": ""}, {"fingerprint": 3}, "abc"):
            expect_raises(ValueError, lambda bad_entry=bad_entry: store.append_negative(bad_entry), f"negative entry {bad_entry!r}")
        lines = (root / "journal.jsonl").read_text(encoding="utf-8").split("\n")
        target = Path(tmp) / f"bad{cases}"
        shutil.copytree(root, target)
        (target / "journal.jsonl").write_text("\n".join(lines[1:]), encoding="utf-8", newline="\n")
        expect_raises(T.StoreError, lambda: T.TheoryStore.open(target), "a journal with its first line cut off")
        require(store.verify() == [], "the store with logs still verifies")
    return f"one file per hypothesis, save/load is the identity, {cases} damaged stores refused, logs append-only"


# ---- generations ---------------------------------------------------------------

def check_generations() -> str:
    T = api()
    theory, _seen = G6.scripted_walk(T)
    with tempfile.TemporaryDirectory(prefix="s07-gate-") as tmp:
        root = Path(tmp) / "store"
        store = T.TheoryStore.create(root)
        empty = T.Theory()
        store.append_journal({"kind": "note"})
        require(store.close_generation(empty, cause="edit:e1") == 0 and store.head()["generation"] == 1,
                "closing the first generation returns 0 and starts generation 1")
        require(store.load().to_dict() == empty.to_dict(), "closing a generation does not touch the live state")
        store.save(theory)
        store.append_journal({"kind": "note"})
        store.append_journal({"kind": "note"})
        require(store.close_generation(theory, cause="checkpoint:batch-1") == 1 and store.head()["generation"] == 2
                and store.head()["version"] == theory.version, "the second generation closes as 1")
        metas = store.generations()
        require(metas == [{"generation": 0, "cause": "edit:e1", "journal_seq": 1, "version": empty.version},
                          {"generation": 1, "cause": "checkpoint:batch-1", "journal_seq": 3, "version": theory.version}],
                f"generations() lists number, cause, the journal position and the version: {metas}")
        require(sorted(path.name for path in (root / "generations").iterdir()) == ["g000000.json", "g000001.json"],
                "one file per closed generation")
        require(store.load_generation(0).to_dict() == empty.to_dict() and store.load_generation(1).to_dict() == theory.to_dict()
                and store.load_generation(1).predict(phi("x7"), ORACLE).to_dict() == theory.predict(phi("x7"), ORACLE).to_dict(),
                "a generation loads as the theory it closed with, and predicts")
        expect_raises(T.StoreError, lambda: store.load_generation(2), "the open generation has no snapshot")
        for bad in (-1, True, "1", 1.0):
            expect_raises(ValueError, lambda bad=bad: store.load_generation(bad), f"generation {bad!r}")
        for bad in ("", None, 3):
            expect_raises(ValueError, lambda bad=bad: store.close_generation(theory, cause=bad), f"cause {bad!r}")
        require(store.verify() == [] and T.TheoryStore.open(root).generations() == metas, "the store verifies and reopens")
        path = root / "generations" / "g000001.json"
        data = read_json(path)
        data["theory"]["next_id"] += 1
        write_json(path, data)
        expect_raises(T.StoreError, lambda: store.load_generation(1), "a snapshot changed by hand")
        require(any("generation" in line for line in store.verify()), f"verify() reports the damaged snapshot: {store.verify()}")
        (root / "generations" / "g000000.json").unlink()
        require(store.verify(), "verify() reports a missing snapshot")
    return "closing a generation snapshots its last state and leaves the live state alone; snapshots load, predict and are checked"


# ---- imports -------------------------------------------------------------------

def check_imports() -> str:
    T = api()
    section = T.theory_manifest()
    files = section["code"]["files"]
    for name in NEW_MODULES:
        require(f"surprise/theory/{name}.py" in files, f"surprise/theory/{name}.py must be hashed into the run manifest")
    checked = 0
    for path in sorted((FRAMEWORK / "surprise" / "theory").rglob("*.py")):
        bad = sorted(module for module in G6.imported_modules(path)
                     if any(module == name or module.startswith(name + ".") for name in G6.FORBIDDEN_IMPORTS))
        require(not bad, f"{path.name} imports {bad}: the theory asks no model and does not reach into the old code")
        checked += 1
    for order in IMPORT_ORDERS:
        run = subprocess.run([sys.executable, "-c", order + "; from surprise.theory import Workbench, TheoryStore; print('ok')"],
                             cwd=FRAMEWORK, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120.0,
                             encoding="utf-8", errors="replace")
        require(run.returncode == 0 and "ok" in run.stdout, f"`{order}` in a fresh process: {_ascii(run.stderr.strip()[-300:])}")
    for name in ("Assessment", "BET_STATES", "EDIT_KINDS", "Outcome", "Proposal", "REJECT_REASONS", "ROLLBACK_REASONS", "Seen",
                 "StoreError", "TheoryStore", "Workbench", "bet_matches", "claim", "common_conjunction", "default_bets",
                 "fingerprint", "holdout_sample", "hypothesis_length", "theory_length"):
        require(hasattr(T, name) and name in T.__all__, f"surprise.theory must export {name}")
    require(T.EDIT_KINDS == C.EDIT_KINDS and T.REJECT_REASONS == C.REJECT_REASONS and T.ROLLBACK_REASONS == C.ROLLBACK_REASONS
            and T.BET_STATES == C.BET_STATES, "the four value tables")
    return f"{checked} theory files import no model and no old code; {len(IMPORT_ORDERS)} import orders load in fresh processes"


# ---- edits ---------------------------------------------------------------------

def check_edits() -> str:
    from surprise.features.registry import default_registry

    T = api()
    registry = default_registry()
    h = G6.hand_hypothesis(C6.S_HAND, C6.TOP)
    good = dict(kind="revise", rationale="why", proposer="gate", removes=("h1",), adds=(h,), bets=(bet([C6.EXC_ALL]),), trigger=("r1",))
    proposal = T.Proposal(**good)
    require(proposal.bets == (bet([C6.EXC_ALL]),) and proposal.removes == ("h1",) and proposal.trigger == ("r1",)
            and T.Proposal(kind="retire", rationale="why", proposer="gate", removes=("h1",)).adds == (),
            "a proposal keeps what it was given, bets normalised to spec dicts")
    bad: list[tuple[str, dict[str, Any]]] = [
        ("an unknown kind", {"kind": "rewrite"}), ("an empty rationale", {"rationale": ""}), ("no proposer", {"proposer": ""}),
        ("revise without a target", {"removes": ()}), ("revise with two targets", {"removes": ("h1", "h2")}),
        ("revise that adds nothing", {"adds": ()}), ("revise that adds two", {"adds": (h, h)}),
        ("add with a target", {"kind": "add"}), ("split into one", {"kind": "split"}),
        ("merge of one", {"kind": "merge"}), ("retire that adds", {"kind": "retire"}),
        ("a repeated target", {"kind": "merge", "removes": ("h1", "h1")}), ("a repeated trigger", {"trigger": ("r1", "r1")}),
        ("adds that are dicts", {"adds": (h.to_dict(),)}), ("a bet without expect", {"bets": ({"spec": spec([C6.EXC_ALL])},)}),
        ("a bet on 'invalid'", {"bets": ({"spec": spec([C6.EXC_ALL]), "expect": "invalid"},)}),
        ("a bet with a broken spec", {"bets": ({"spec": {"engine": ENGINE}, "expect": "fail"},)}),
        ("a bet with an extra key", {"bets": ({"spec": spec([C6.EXC_ALL]), "expect": "fail", "weight": 2},)}),
        ("bets given as one dict", {"bets": bet([C6.EXC_ALL])}), ("a trigger that is a string", {"trigger": "r1"}),
    ]
    for what, change in bad:
        expect_raises(ValueError, lambda change=change: T.Proposal(**{**good, **change}), what)
    require(T.Proposal(**{**good, "bets": ()}).bets == (), "a proposal without bets can be written down; the workbench refuses it")
    for kind, removes, adds in (("add", (), (h,)), ("split", ("h1",), (h, h, h)), ("merge", ("h1", "h2", "h3"), (h,)), ("retire", ("h1",), ())):
        T.Proposal(kind=kind, rationale="why", proposer="gate", removes=removes, adds=adds)

    # claims and fingerprints: what is asserted, not who asserts it or on what evidence
    base = T.claim(h, registry)
    require(base == [ENGINE, ORACLE, [], "wrong_result", None, "missing_only", list(C6.S_HAND)], f"claim of the hand-written h2: {base}")
    same = dataclasses.replace(h, hypothesis_id="other", general=((C6.L_DUPS,),), positives=("r1",), negatives=("r2",),
                               source="llm", specific=(C6.L_DUPS, C6.EXC_ALL, C6.SET_ALL, "ast"), plan_delta=("x",), versions={"a": 1})
    require(T.claim(same, registry) == base, "id, G, evidence, source, the order and redundancy of S do not change a claim")
    mark = T.fingerprint((), (h,), registry)
    require(isinstance(mark, str) and len(mark) == 16 and all(c in "0123456789abcdef" for c in mark)
            and mark == T.fingerprint((G6.hand_hypothesis(C6.S_X1, C6.TOP, hypothesis_id="gone"),), (same,), registry),
            "a fingerprint is 16 hex digits of the added claims; the hypotheses an edit replaces do not enter")
    different = [dataclasses.replace(h, specific=(C6.EXC_ALL,)), dataclasses.replace(h, behavior_shape="extra_only"),
                 dataclasses.replace(h, oracle="tlp"), dataclasses.replace(h, engine="duckdb"),
                 dataclasses.replace(h, interventions=("filter_pushdown",)), dataclasses.replace(h, error_class="X")]
    marks = {T.fingerprint((), (item,), registry) for item in different} | {mark}
    require(len(marks) == len(different) + 1, "S, the identity fields and the scope each change the fingerprint")
    x4 = G6.hand_hypothesis(C6.S_X4, C6.TOP, identity="h_extra")
    require(T.fingerprint((), (h, x4), registry) == T.fingerprint((), (x4, h), registry) != mark, "the order of the added hypotheses does not matter")
    require(T.fingerprint((h,), (), registry) != mark and T.fingerprint((h,), (), registry) == T.fingerprint((same,), (), registry),
            "a retirement is fingerprinted by the claim it withdraws")

    # bets
    require(T.default_bets((), (same, x4), registry) == (bet(C6.S_HAND), bet(C6.S_X4)),
            "default bets: inside the S of each added hypothesis an experiment fails")
    require(T.default_bets((h,), (), registry) == (bet(C6.S_HAND, (), "pass"),), "the default bet of a retirement is a pass inside the old S")
    first = bet([C6.EXC_ALL], [C6.L_DUPS], "pass")
    table = [
        ("x3", pass_label(), True), ("x3", fail_label("df_missing_raw"), True), ("x1", pass_label(), False),
        ("x4", pass_label(), False), ("x3", invalid_label(), False), ("x3", pass_label("tlp"), False),
    ]
    for name, label, expected in table:
        require(T.bet_matches(first, phi(name), label, registry) is expected, f"bet on EXCEPT ALL without left duplicates vs {name}/{label.y}/{label.oracle}")
    blind = G6.phi((C6.EXC_ALL, C6.SELECT), layers={"ast": "ok", "plan": "skipped", "data": "skipped"})
    require(T.bet_matches(first, blind, pass_label(), registry) is False and T.bet_matches(bet([C6.EXC_ALL]), blind, pass_label(), registry) is True,
            "a bet does not speak about an experiment whose phi cannot decide its spec")
    require(T.bet_matches(bet([C6.EXC_ALL], engine="duckdb"), phi("x3"), pass_label(), registry) is False, "another engine")

    # the held-out sample
    records = [T.Seen(f"r{i}", phi("x3" if i % 2 else "x1"), pass_label() if i % 2 else fail_label("df_missing_raw")) for i in range(40)]
    records += [T.Seen("inv", phi("plain"), invalid_label()), T.Seen("tlp", phi("x3"), pass_label("tlp")),
                T.Seen("duck", G6.phi("plain", engine="duckdb"), pass_label())]
    scope = {(ENGINE, ORACLE)}
    everything = T.holdout_sample(records, scope, ["r3", "r4"])
    require([s.record_id for s in everything] == [f"r{i}" for i in range(40) if i not in (3, 4)],
            "held out = valid records of the scope that are not trigger records, in the order observed")
    cut = T.holdout_sample(records, scope, [], limit=7)
    wanted = sorted(sorted((f"r{i}" for i in range(40)), key=lambda r: hashlib.sha256(r.encode("utf-8")).hexdigest())[:7],
                    key=lambda r: int(r[1:]))
    require([s.record_id for s in cut] == wanted, f"beyond the limit, keep the records whose id hashes lowest: {[s.record_id for s in cut]}")
    require(len(T.holdout_sample(records, scope, [])) == 40 and T.holdout_sample(records, {("duckdb", ORACLE)}, []) == (records[-1],),
            "the default limit is ACCEPT_HOLDOUT_MAX; scopes are (engine, oracle) pairs")
    return f"{len(bad)} malformed proposals refused; claims and fingerprints ignore ids and evidence; bets match by spec; held-out sample is deterministic"


# ---- accept --------------------------------------------------------------------

def check_accept() -> str:
    T = api()
    lit, per = C.CONSTANTS["MDL_LITERAL_BITS"], C.CONSTANTS["MDL_HYPOTHESIS_BITS"]
    with tempfile.TemporaryDirectory(prefix="s07-gate-") as tmp:
        wb, h1 = opened_bench(tmp)
        before = wb.theory.to_dict()
        version = wb.theory.version
        # a dry run changes nothing
        dry = T.Proposal(kind="revise", rationale="dry", proposer="hand", removes=(h1,), adds=(reworded(wb, h1, C6.S_HAND),),
                         bets=H2_BETS, trigger=("r1",))
        verdict = wb.assess(dry)
        require(verdict.accepted is True and verdict.reason is None and close(verdict.delta_length, -8 * lit, 1e-6)
                and verdict.delta_in == 0.0 and verdict.delta_out == 0.0 and verdict.holdout == (),
                f"assess: the hand-written h2 is acceptable: {verdict}")
        require(wb.edits() == () and wb.store.edit_history() == [] and wb.theory.to_dict() == before and wb.generation == 0,
                "assess() neither applies nor logs")
        # 1. the hand-written h2: same fit, shorter, two bets
        edit = hand_h2(wb, h1)
        h2 = edit.payload["adds"][0]
        new = wb.theory.get(h2)
        require(edit.edit_id == "e1" and edit.kind == "revise" and edit.decision == "accepted" and edit.proposer == "hand"
                and edit.theory_version == version and edit.surprise_delta_in == 0.0 and edit.surprise_delta_out == 0.0
                and edit.bets == H2_BETS and edit.rationale.startswith("EXCEPT ALL"), f"e1 as logged: {edit.to_dict()}")
        payload = edit.payload
        require(payload["reason"] is None and payload["removes"] == [h1] and payload["removed"] == [before["hypotheses"][0]]
                and payload["adds"] == [h2] and payload["added"] == [new.to_dict()] and payload["trigger"] == ["r1"]
                and payload["holdout"] == 0 and close(payload["length_delta"], -8 * lit, 1e-6) and payload["generation"] == 0
                and payload["journal_seq"] == 2 and payload["rollback"] is None
                and payload["bets_state"] == [{"status": "open", "record_id": None}] * 2
                and payload["fingerprint"] == verdict.fingerprint, f"e1 payload: {payload}")
        require(h2 not in (h1, "") and ids(wb.theory) == (h2,) and tuple(new.specific) == C6.S_HAND and tuples(new.general) == C6.TOP
                and new.positives == ("r1",) and new.negatives == () and new.source == "hand-written" and new.status == "active"
                and (new.fail_kind, new.error_class, new.behavior_shape, new.oracle) == ("wrong_result", None, "missing_only", ORACLE),
                f"the edit replaces h1 by a new id carrying the same identity and the evidence S still covers: {new.to_dict()}")
        require(wb.generation == 1 and wb.store.load_generation(0).to_dict() == before
                and wb.store.generations() == [{"generation": 0, "cause": "edit:e1", "journal_seq": 1, "version": version}],
                "accepting an edit closes the generation with the state just before it")
        require([entry["kind"] for entry in wb.store.journal()] == ["observe", "edit"] and wb.store.journal()[1]["edit_id"] == "e1"
                and sorted(p.name for p in (wb.store.root / "hypotheses").iterdir()) == [f"{h2}.json"]
                and wb.store.load().to_dict() == wb.theory.to_dict() and wb.store.edit_history() == [edit] and wb.edit("e1") == edit,
                "journal, files and edit log all show the edit")
        require(wb.open_bets() == (("e1", 0, H2_BETS[0]), ("e1", 1, H2_BETS[1])), f"both bets are open: {wb.open_bets()}")
        # 2. the two predictions of the framework document
        out = wb.observe(phi("x3"), pass_label(), "r2")
        require(out.bets == (("e1", 0, "kept"),) and out.rolled_back == () and out.owner is None and out.seq == 3
                and tuples(wb.theory.get(h2).general) == ((C6.L_DUPS,),) and close(out.observation.surprise, 1.0),
                f"without the left duplicates it passes: the bet is kept and left_has_dups enters G: {out}")
        out = wb.observe(phi("x4"), fail_label("df_extra", attribution=(h2, False)), "r3")
        h3 = out.observation.opened
        require(out.bets == (("e1", 1, "kept"),) and out.rolled_back == () and h3 and out.owner == h3 and wb.open_bets() == (),
                f"INTERSECT ALL fails as predicted, as another bug: {out}")
        done = wb.edit("e1")
        require(done.decision == "accepted" and done.payload["bets_state"] == [{"status": "kept", "record_id": "r2"},
                                                                               {"status": "kept", "record_id": "r3"}]
                and len(wb.store.edit_history()) == 3 and wb.store.edits() == [done],
                "each kept bet appends the edit's new state to the log")
        # 3. refuted by a held-out record
        state, generation, counter, negatives = wb.theory.to_dict(), wb.generation, wb.theory.next_id, len(wb.negatives())
        every = T.Proposal(kind="revise", rationale="every ALL set operation loses rows", proposer="hand", removes=(h2,),
                           adds=(reworded(wb, h2, (C6.SET_ALL,)),), bets=(bet([C6.UNI_ALL]),))
        e2 = wb.propose(every)
        after = T.Theory.from_dict(state)
        after.remove(h2)
        after.put(G6.hand_hypothesis((C6.SET_ALL,), C6.TOP, hypothesis_id="what-if"))
        expected = sum(static_bits(after, phi(n), ORACLE, y) - static_bits(wb.theory, phi(n), ORACLE, y)
                       for n, y in (("x1", "fail"), ("x3", "pass"), ("x4", "fail")))
        require(e2.decision == "rolled_back" and e2.payload["reason"] == "holdout" and e2.surprise_delta_in == 0.0
                and close(e2.surprise_delta_out, expected, 1e-9) and close(expected, bits(0.05) - bits(0.99), 1e-9)
                and e2.payload["holdout"] == 3 and e2.payload["adds"] == [] and e2.payload["generation"] is None
                and e2.payload["bets_state"] == [{"status": "void", "record_id": None}],
                f"the pass without duplicates would become a 4.3-bit surprise: {e2.to_dict()}")
        require(wb.theory.to_dict() == state and wb.generation == generation and wb.theory.next_id == counter
                and wb.store.load().to_dict() == state, "a refused edit changes nothing and burns no id")
        memory = wb.negatives()
        require(len(memory) == negatives + 1 and memory[-1]["fingerprint"] == e2.payload["fingerprint"] and memory[-1]["edit_id"] == "e2"
                and memory[-1]["reason"] == "holdout" and memory[-1]["record_id"] is None and memory[-1]["kind"] == "revise"
                and memory[-1]["claims"] == [[ENGINE, ORACLE, [], "wrong_result", None, "missing_only", [C6.SET_ALL]]],
                f"the refuted claim enters the negative memory: {memory[-1]}")
        require(wb.propose(every).payload["reason"] == "negative_memory" and len(wb.negatives()) == negatives + 1,
                "the same claim is refused from memory, without a second entry")
        # 4. refuted by its own trigger record
        narrow = T.Proposal(kind="revise", rationale="only with duplicates on both sides", proposer="hand", removes=(h2,),
                            adds=(reworded(wb, h2, (C6.EXC_ALL, C6.L_DUPS, C6.R_DUPS)),), bets=(bet([C6.EXC_ALL, C6.L_DUPS, C6.R_DUPS]),),
                            trigger=("r1",))
        e4 = wb.propose(narrow)
        require(e4.decision == "rolled_back" and e4.payload["reason"] == "trigger" and e4.surprise_delta_in > 0.9
                and wb.negatives()[-1]["edit_id"] == e4.edit_id and wb.negatives()[-1]["reason"] == "trigger",
                f"an edit that stops explaining its own trigger record is refuted: {e4.to_dict()}")
        # 5. no gain: same fit, same length. Not a refutation.
        sideways = T.Proposal(kind="revise", rationale="say it with the table instead", proposer="hand", removes=(h2,),
                              adds=(reworded(wb, h2, (C6.EXC_ALL, C6.T_DUPS)),), bets=(bet([C6.EXC_ALL, C6.T_DUPS]),))
        count = len(wb.negatives())
        e5 = wb.propose(sideways)
        require(e5.decision == "rolled_back" and e5.payload["reason"] == "no_gain" and e5.surprise_delta_in == 0.0
                and e5.surprise_delta_out == 0.0 and close(e5.payload["length_delta"], 0.0, 1e-9) and len(wb.negatives()) == count,
                f"an edit that neither fits better nor is shorter is declined, not remembered as wrong: {e5.to_dict()}")
        # 6. no bets
        e6 = wb.propose(T.Proposal(kind="revise", rationale="trust me", proposer="hand", removes=(h2,),
                                   adds=(reworded(wb, h2, (C6.L_DUPS,)),)))
        require(e6.decision == "rolled_back" and e6.payload["reason"] == "no_bets" and e6.surprise_delta_in is None
                and e6.surprise_delta_out is None and e6.payload["length_delta"] is None and len(wb.negatives()) == count,
                f"an edit without a prediction is refused before anything is computed: {e6.to_dict()}")
        require([e.edit_id for e in wb.edits()] == ["e1", "e2", "e3", "e4", "e5", "e6"] and wb.theory.to_dict() == state,
                "every proposal is logged, in order; none of the refused ones touched the theory")
        # 7. misuse is an error, not a logged refusal
        wb.observe(phi("plain"), invalid_label(), "r-invalid")
        logged = len(wb.edits())
        misuse = [
            ("an unknown hypothesis", dict(removes=("h-none",))), ("an unobserved trigger", dict(trigger=("r-none",))),
            ("an invalid trigger record", dict(trigger=("r-invalid",))),
            ("another scope", dict(adds=(dataclasses.replace(reworded(wb, h2, (C6.L_DUPS,)), oracle="tlp"),))),
            ("an empty S", dict(adds=(reworded(wb, h2, ("ast", "data")),))),
        ]
        for what, change in misuse:
            fields = dict(kind="revise", rationale="x", proposer="hand", removes=(h2,), adds=(reworded(wb, h2, (C6.L_DUPS,)),),
                          bets=(bet([C6.L_DUPS]),))
            expect_raises((ValueError, KeyError), lambda fields=fields, change=change: wb.propose(T.Proposal(**{**fields, **change})), what)
        expect_raises(ValueError, lambda: wb.propose(dry.__dict__), "a proposal that is not a Proposal")
        require(len(wb.edits()) == logged and wb.theory.to_dict()["hypotheses"] == state["hypotheses"], "misuse leaves no trace")

    # 8. a new hypothesis for failures nothing explains: one is not enough, four are
    with tempfile.TemporaryDirectory(prefix="s07-gate-") as tmp:
        wb, h1 = opened_bench(tmp)
        template = dataclasses.replace(G6.hand_hypothesis((C6.EXC,), C6.TOP, hypothesis_id="new"), behavior_shape="both")
        fed = 0
        for count in (1, 4):
            while fed < count:
                out = wb.observe(phi("x6"), fail_label("df_both"), f"u{fed}")
                require(out.observation.unexplained and out.owner is None and wb.owner_of(f"u{fed}") is None,
                        f"an unprofiled failure that no hypothesis absorbs is unexplained: {out}")
                fed += 1
            trigger = tuple(f"u{index}" for index in range(count))
            proposal = T.Proposal(kind="add", rationale="the distinct EXCEPT returns wrong rows too", proposer="hand", adds=(template,),
                                  bets=(bet([C6.EXC]),), trigger=trigger)
            verdict = wb.assess(proposal)
            gain = count * (static_bits(wb.theory, phi("x6"), ORACLE, "fail") - bits(0.95))
            require(close(verdict.delta_in, -gain, 1e-9) and close(verdict.delta_length, per + lit, 1e-9) and verdict.delta_out == 0.0,
                    f"{count} unexplained failures: delta_in {verdict.delta_in}, expected {-gain}")
            require(verdict.accepted is (gain > per + lit) and (count == 4) is verdict.accepted and (verdict.reason == "no_gain") is (count == 1),
                    f"{count} unexplained failures against {per + lit} bits of hypothesis: {verdict}")
        added = wb.propose(proposal)
        born = wb.theory.get(added.payload["adds"][0])
        require(added.decision == "accepted" and born.positives == trigger and tuple(born.specific) == (C6.EXC,)
                and ids(wb.theory) == (h1, born.hypothesis_id) and wb.predict(phi("x6"), ORACLE).zone == "confirmed"
                and all(wb.owner_of(r) == born.hypothesis_id for r in trigger),
                f"the added hypothesis collects the failures it explains, and owns them: {born.to_dict()}")
    return ("hand-written h2 accepted on length alone and both bets kept; a held-out pass, the trigger record, no gain, no bets "
            "each refuse an edit; only refutations enter the negative memory; 4 unexplained failures pay for a hypothesis, 1 does not")


# ---- rollback ------------------------------------------------------------------

def check_rollback() -> str:
    T = api()
    with tempfile.TemporaryDirectory(prefix="s07-gate-") as tmp:
        wb, h2, h3 = settled_bench(tmp)
        # 1. a deliberately wrong edit: accepted on the evidence so far, refuted by its own bet
        before = wb.theory.to_dict()
        wrong = T.Proposal(kind="revise", rationale="duplicates on the left are enough", proposer="hand", removes=(h2,),
                           adds=(reworded(wb, h2, (C6.L_DUPS,)),), bets=(bet([C6.UNI_ALL, C6.L_DUPS]),))
        edit = wb.propose(wrong)
        h4 = edit.payload["adds"][0]
        require(edit.decision == "accepted" and ids(wb.theory) == (h3, h4) and h4 not in (h2, h3)
                and close(edit.payload["length_delta"], -C.CONSTANTS["MDL_LITERAL_BITS"], 1e-6),
                f"nothing seen so far speaks against it, and it is shorter: {edit.to_dict()}")
        generation = wb.generation
        mid = wb.observe(phi("x1"), fail_label("df_missing_raw", attribution=(h4, True)), "r4")
        require(mid.owner == h4 and wb.owner_of("r4") == h4 and mid.rolled_back == (), f"while it stands, the edit's hypothesis owns new duplicates: {mid}")
        out = wb.observe(phi("x5"), pass_label(), "r5")
        require(out.bets == ((edit.edit_id, 0, "broken"),) and out.rolled_back == (edit.edit_id,)
                and out.observation.prediction.zone == "confirmed" and close(out.observation.surprise, bits(0.05))
                and out.observation.triage == "unexpected_pass",
                f"UNION ALL passes inside the edit's S: 4.3 bits, the bet is lost: {out}")
        expected = T.Theory.from_dict({**before, "next_id": before["next_id"] + 1})
        expected.observe(phi("x1"), fail_label("df_missing_raw", attribution=(h4, True)), "r4")
        expected.observe(phi("x5"), pass_label(), "r5")
        require(wb.theory.to_dict() == expected.to_dict() and ids(wb.theory) == (h2, h3) and wb.store.load().to_dict() == expected.to_dict(),
                "after the rollback the theory is the one before the edit, taught everything observed since")
        undone = wb.edit(edit.edit_id)
        require(undone.decision == "rolled_back" and undone.payload["bets_state"] == [{"status": "broken", "record_id": "r5"}]
                and undone.payload["rollback"] == {"reason": "bet_broken", "record_id": "r5", "generation": generation}
                and undone.payload["reason"] is None and undone.payload["adds"] == [h4],
                f"the edit log says why it was rolled back: {undone.to_dict()}")
        memory = wb.negatives()[-1]
        require(memory["fingerprint"] == edit.payload["fingerprint"] and memory["edit_id"] == edit.edit_id and memory["reason"] == "bet_broken"
                and memory["record_id"] == "r5" and memory["claims"] == [[ENGINE, ORACLE, [], "wrong_result", None, "missing_only", [C6.L_DUPS]]],
                f"the refuted claim enters the negative memory with the record that refuted it: {memory}")
        causes = [meta["cause"] for meta in wb.store.generations()]
        require(wb.generation == generation + 1 and causes[-2:] == [f"edit:{edit.edit_id}", f"rollback:{edit.edit_id}"]
                and h4 in ids(wb.store.load_generation(generation)) and wb.store.load_generation(generation - 1).to_dict() == before,
                f"the refuted state is kept as a closed generation: {causes}")
        kinds = [entry["kind"] for entry in wb.store.journal()]
        last = wb.store.journal()[-1]
        require(kinds[-4:] == ["edit", "observe", "observe", "rollback"] and last["edit_id"] == edit.edit_id and last["reason"] == "bet_broken"
                and last["cascade"] == [] and set(last) == {"kind", "seq", "edit_id", "reason", "generation", "cascade"},
                f"the journal records the rollback: {last}")
        require(wb.owner_of("r4") == h2 and wb.owner_of("r3") == h3 and wb.partition() == {"r1": f"{ENGINE}|{h2}", "r3": f"{ENGINE}|{h3}", "r4": f"{ENGINE}|{h2}"},
                f"records the refuted hypothesis owned go back to the restored one: {wb.partition()}")
        # the claim is refused from now on, whoever makes it and in whatever kind of edit
        again = wb.propose(wrong)
        as_add = wb.propose(T.Proposal(kind="add", rationale="same idea, new clothes", proposer="llm",
                                       adds=(G6.hand_hypothesis((C6.L_DUPS,), C6.TOP, hypothesis_id="x"),), bets=(bet([C6.L_DUPS]),)))
        require(again.payload["reason"] == "negative_memory" and as_add.payload["reason"] == "negative_memory"
                and wb.theory.to_dict() == expected.to_dict(), "the negative memory refuses the claim, under any kind and proposer")
        require(wb.theory.next_id > int(h4[1:]) and h4 not in ids(wb.theory), "the id of the refuted hypothesis is never handed out again")
        # 2. a settled edit is not rolled back by a later contradiction
        out = wb.observe(phi("x8"), pass_label(), "r6")
        require(out.rolled_back == () and out.bets == () and wb.edit("e1").decision == "accepted"
                and wb.theory.get(h2).contradictions == ("r6",), f"h2 kept both bets; a later pass inside S is a contradiction, not a rollback: {out}")
        require(wb.store.verify() == [], f"the store verifies: {wb.store.verify()}")
        # 3. rolling back by hand
        expect_raises(ValueError, lambda: wb.rollback(edit.edit_id), "rolling back twice")
        expect_raises(ValueError, lambda: wb.rollback("e-none"), "rolling back an unknown edit")
        expect_raises(ValueError, lambda: wb.rollback("e1", reason="cascade"), "cascade is not a reason one can give")
        snapshot = wb.store.load_generation(0).to_dict()
        seen = [(s.phi, s.label, s.record_id) for s in wb.records()][1:]
        done = wb.rollback("e1")
        manual = T.Theory.from_dict({**snapshot, "next_id": expected.next_id})
        for example, label, record_id in seen:
            manual.observe(example, label, record_id)
        require(len(done) == 1 and done[0].edit_id == "e1" and done[0].decision == "rolled_back"
                and done[0].payload["rollback"]["reason"] == "manual" and done[0].payload["rollback"]["record_id"] is None
                and done[0].payload["bets_state"] == [{"status": "kept", "record_id": "r2"}, {"status": "kept", "record_id": "r3"}]
                and wb.negatives()[-1]["edit_id"] == "e1" and wb.negatives()[-1]["reason"] == "manual",
                f"a manual rollback is logged and remembered: {done[0].to_dict()}")
        require(wb.theory.to_dict() == manual.to_dict() and h2 not in ids(wb.theory),
                "rolling back the first edit replays every observation since onto the state before it")

    # 4. what was accepted on top of a refuted edit falls with it, without being called wrong
    with tempfile.TemporaryDirectory(prefix="s07-gate-") as tmp:
        wb, h1 = opened_bench(tmp)
        duck = G6.phi("joinq", engine="duckdb")
        d1 = wb.observe(duck, fail_label("f1"), "d1").observation.opened
        bad_bet = T.Proposal(kind="revise", rationale="it fails without the duplicates too", proposer="hand", removes=(h1,),
                             adds=(reworded(wb, h1, C6.S_HAND),), bets=(bet([C6.EXC_ALL], [C6.L_DUPS], "fail"),), trigger=("r1",))
        first = wb.propose(bad_bet)
        other = T.Proposal(kind="revise", rationale="any inner join", proposer="hand", removes=(d1,),
                           adds=(reworded(wb, d1, ("ast:join:inner",)),), bets=(bet(["ast:join:inner"], engine="duckdb", oracle="plan_variant"),))
        second = wb.propose(other)
        require(first.decision == second.decision == "accepted" and len(wb.open_bets()) == 2, "two edits stand, in two scopes")
        out = wb.observe(phi("x3"), pass_label(), "r2")
        require(out.rolled_back == (first.edit_id, second.edit_id) and out.bets == ((first.edit_id, 0, "broken"),),
                f"the first edit loses its bet and takes the later one with it: {out}")
        fallen = wb.edit(second.edit_id)
        require(fallen.decision == "rolled_back" and fallen.payload["rollback"]["reason"] == "cascade"
                and fallen.payload["rollback"]["record_id"] is None and fallen.payload["bets_state"] == [{"status": "void", "record_id": None}]
                and [n["edit_id"] for n in wb.negatives()] == [first.edit_id] and wb.store.journal()[-1]["cascade"] == [second.edit_id]
                and ids(wb.theory) == (h1, d1) and wb.open_bets() == (),
                f"the later edit is undone as a cascade and stays out of the negative memory: {fallen.to_dict()}")
        retry = wb.propose(other)
        require(retry.decision == "accepted" and retry.edit_id not in (first.edit_id, second.edit_id)
                and retry.payload["adds"][0] not in second.payload["adds"], f"so it can be proposed again and gets a fresh id: {retry.to_dict()}")
        out = wb.observe(duck, fail_label("f1_raw", attribution=(retry.payload["adds"][0], True)), "d2")
        require(out.bets == ((retry.edit_id, 0, "kept"),) and wb.open_bets() == () and wb.store.verify() == [], f"and its bet can be kept: {out}")
    return ("a lost bet rolls back the edit and replays what was observed since; the claim enters the negative memory and is refused "
            "under any kind; a settled edit survives contradictions; later edits cascade without blame; manual rollback")


# ---- journal -------------------------------------------------------------------

def bench_state(wb: Any) -> dict[str, Any]:
    return {"theory": wb.theory.to_dict(), "edits": [e.to_dict() for e in wb.edits()], "negatives": list(wb.negatives()),
            "partition": wb.partition(), "bets": [list(b) for b in wb.open_bets()], "generation": wb.generation,
            "records": [(s.record_id, s.phi.to_dict(), s.label.to_dict()) for s in wb.records()]}


def check_journal() -> str:
    from surprise.features.phi import Phi
    from surprise.harness.contracts import Label

    T = api()
    with tempfile.TemporaryDirectory(prefix="s07-gate-") as tmp:
        wb, h2, h3 = settled_bench(tmp)
        wb.propose(T.Proposal(kind="revise", rationale="duplicates on the left are enough", proposer="hand", removes=(h2,),
                              adds=(reworded(wb, h2, (C6.L_DUPS,)),), bets=(bet([C6.UNI_ALL, C6.L_DUPS]),)))
        wb.observe(phi("x5"), pass_label(), "r4")
        pending = wb.propose(T.Proposal(kind="revise", rationale="with NULLs on the right", proposer="hand", removes=(h3,),
                                        adds=(reworded(wb, h3, (C6.INT_ALL, C6.R_NULL)),), bets=(bet([C6.INT_ALL, C6.R_NULL]),)))
        require(pending.decision == "accepted" and len(wb.open_bets()) == 1 and wb.checkpoint("batch-1") == wb.generation - 1,
                "an accepted edit with an open bet, then a checkpoint that closes a generation")
        expect_raises(ValueError, lambda: wb.checkpoint(""), "a checkpoint needs a note")
        expect_raises(ValueError, lambda: wb.observe(phi("x1"), fail_label("df_missing_raw"), "r1"), "a record id observed before")
        state = bench_state(wb)
        again = T.Workbench.open(wb.store.root)
        require(bench_state(again) == state, "a reopened workbench has the same theory, edits, memory, owners, bets and records")
        copy = Path(tmp) / "copy"
        shutil.copytree(wb.store.root, copy)
        twin = T.Workbench.open(copy)
        steps = [("x4", fail_label("df_extra"), "r5"),
                 ("x8", pass_label(), "r6"), ("x6", fail_label("df_missing_raw"), "r7")]
        for name, label, record_id in steps:
            a = wb.observe(phi(name), label, record_id)
            b = twin.observe(phi(name), label, record_id)
            require(a == b, f"{record_id}: the reopened copy and the original must react alike: {a} vs {b}")
        require(bench_state(twin) == bench_state(wb) and wb.store.verify() == [] and twin.store.verify() == [],
                "after the same three experiments the two are still equal, and both stores verify")
        require(wb.seen("r1").label.y == "fail" and [s.record_id for s in wb.records()][:3] == ["r1", "r2", "r3"], "records() in the order observed")
        expect_raises(KeyError, lambda: wb.seen("r-none"), "an unobserved record")
    # the journal alone carries everything the theory learns from
    with tempfile.TemporaryDirectory(prefix="s07-gate-") as tmp:
        wb = T.Workbench.create(Path(tmp) / "store")
        heavy = dataclasses.replace(fail_label("df_missing"), detail={"sql": "SELECT " + "x" * 4000, "rows": [[1, None]] * 50})
        script = [("x1", heavy, "r1"), ("x3", pass_label(), "r2"), ("x4", fail_label("df_extra"), "r3"),
                  ("x1", fail_label("df_missing_raw"), "r4"), ("x8", pass_label(), "r5"), ("x5", pass_label(), "r6"),
                  ("x5", pass_label(), "r7"), ("plain", invalid_label("query_error"), "r8"), ("x6", fail_label("df_missing_raw"), "r9")]
        plain = T.Theory()
        owners = []
        for name, label, record_id in script:
            out = wb.observe(phi(name), label, record_id)
            owners.append(out.owner)
            require(out.observation == plain.observe(phi(name), label, record_id), f"{record_id}: the workbench observes as the theory does")
        entries = wb.store.journal()
        require([e["kind"] for e in entries] == ["observe"] * 9 and [e["record_id"] for e in entries] == [s[2] for s in script]
                and all(set(e) == {"kind", "seq", "record_id", "phi", "label"} for e in entries),
                "one journal entry per observation: record id, phi, label")
        require(entries[0]["label"]["detail"] == {} and entries[0]["label"]["cve"] == heavy.cve and entries[0]["phi"] == phi("x1").to_dict()
                and (wb.store.root / "journal.jsonl").stat().st_size < 12000, "the journal keeps the label without its detail")
        replayed = T.Theory()
        for entry in entries:
            replayed.observe(Phi.from_dict(entry["phi"]), Label.from_dict(entry["label"]), entry["record_id"])
        require(replayed.to_dict() == plain.to_dict() == wb.theory.to_dict() == wb.store.load().to_dict(),
                "replaying the journal reproduces the theory, and the store holds it after every observation")
        first, second = ids(wb.theory)
        require(owners == [first, None, second, first, None, None, None, None, None]
                and owners == [wb.owner_of(record_id) for _n, _l, record_id in script],
                f"owner: the hypothesis that holds a failure as a positive; none for passes, invalid and unexplained: {owners}")
    return "reopening reproduces the workbench and it continues identically; the journal alone reproduces the theory; labels are kept without detail"


# ---- mdl -----------------------------------------------------------------------

def check_mdl() -> str:
    T = api()
    lit, per = C.CONSTANTS["MDL_LITERAL_BITS"], C.CONSTANTS["MDL_HYPOTHESIS_BITS"]
    # 1. two hypotheses of one identity that nothing separates: merged
    with tempfile.TemporaryDirectory(prefix="s07-gate-") as tmp:
        wb, h1 = opened_bench(tmp)
        blind = G6.phi(NO_PLAN, layers=NO_PLAN_LAYERS)
        out = wb.observe(blind, fail_label("df_missing"), "r2")
        h2 = out.observation.opened
        require(h2 and out.observation.effects == (), f"a phi without the plan layer cannot be placed against h1, so it opens a family: {out}")
        require(wb.repair_candidates() == (), "nothing to repair")
        (candidate,) = wb.merge_candidates()
        shared = T.common_conjunction(C6.S_X1, T.reduce_conjunction(NO_PLAN))
        require(candidate.kind == "merge" and candidate.removes == (h1, h2) and candidate.proposer == "mdl" and candidate.trigger == ()
                and tuple(candidate.adds[0].specific) == shared == T.reduce_conjunction(NO_PLAN) and candidate.bets == (bet(shared),),
                f"the merge candidate: both targets, their shared S, the default bet: {candidate}")
        verdict = wb.assess(candidate)
        require(verdict.accepted and verdict.delta_in == 0.0 and verdict.delta_out == 0.0
                and close(verdict.delta_length, -(per + 10 * lit), 1e-6), f"same fit, one hypothesis fewer: {verdict}")
        (merged,) = wb.compress()
        h3 = merged.payload["adds"][0]
        new = wb.theory.get(h3)
        require(merged.kind == "merge" and merged.decision == "accepted" and merged.proposer == "mdl" and ids(wb.theory) == (h3,)
                and new.positives == ("r1", "r2") and tuple(new.specific) == shared and new.source == "mdl",
                f"compress() applies it; the merged hypothesis keeps both positives: {new.to_dict()}")
        require(wb.owner_of("r1") == wb.owner_of("r2") == h3 and wb.partition() == {"r1": f"{ENGINE}|{h3}", "r2": f"{ENGINE}|{h3}"}
                and wb.families() == {f"{ENGINE}|{h3}": (h3,)}, f"both records now belong to one family: {wb.partition()}")
        require(wb.compress() == () and wb.merge_candidates() == (), "nothing more to compress")
        out = wb.observe(phi("x7"), fail_label("df_missing_raw", attribution=(h3, True)), "r3")
        require(out.bets == ((merged.edit_id, 0, "kept"),) and wb.open_bets() == (), f"the merge's bet is kept by the next failure inside S: {out}")

    # 1b. with a fix set, the fix set is the identity: the shape of the wrong result does not keep two hypotheses apart
    with tempfile.TemporaryDirectory(prefix="s07-gate-") as tmp:
        from surprise.harness.contracts import IdentityEvidence

        wb = T.Workbench.create(Path(tmp) / "store")
        duck = G6.phi("joinq", engine="duckdb")
        blind = G6.phi((C6.SELECT, "ast:join:inner", C6.T_NULL, C6.INT), engine="duckdb", layers=NO_PLAN_LAYERS)
        h1 = wb.observe(duck, fail_label("f1"), "d1").observation.opened
        other_shape = dataclasses.replace(fail_label("f1"), identity=IdentityEvidence(
            switches=("deliminator", "filter_pushdown"), error_class=None, behavior={"missing": 1, "extra": 1}))
        h2 = wb.observe(blind, other_shape, "d2").observation.opened
        require(h1 and h2 and wb.theory.get(h1).behavior_shape != wb.theory.get(h2).behavior_shape
                and wb.family_of(h1) == wb.family_of(h2), "two hypotheses of one fix set, of different shapes, in one scope")
        (candidate,) = wb.merge_candidates()
        require(candidate.removes == (h1, h2) and wb.assess(candidate).accepted, f"they are merge candidates: {candidate}")
        (merged,) = wb.compress()
        new = wb.theory.get(merged.payload["adds"][0])
        require(new.positives == ("d1", "d2") and new.interventions == wb.theory.get(new.hypothesis_id).interventions
                and (new.fail_kind, new.behavior_shape) == ("wrong_result", "missing_only") and len(wb.families()) == 1,
                f"the merged hypothesis carries the identity of the older one: {new.to_dict()}")
        loose = wb.observe(G6.phi("joinq", engine="duckdb"), fail_label("f9"), "d3")
        require(loose.observation.opened and wb.merge_candidates() == (),
                "a hypothesis without a fix set is never a merge candidate of one with a fix set")

    # 2. the same two identities with a known pass between them: not merged
    with tempfile.TemporaryDirectory(prefix="s07-gate-") as tmp:
        wb, h1 = opened_bench(tmp)
        wb.observe(phi("x3"), pass_label(), "r2")
        out = wb.observe(G6.phi(Z_RIGHT), fail_label("df_missing"), "r3")
        h2 = out.observation.opened
        require(h2 and out.observation.effects == ((h1, "outside"),), f"a failure of the same identity outside G opens a second family: {out}")
        (candidate,) = wb.merge_candidates()
        verdict = wb.assess(candidate)
        require(candidate.removes == (h1, h2) and verdict.accepted is False and verdict.reason == "holdout"
                and close(verdict.delta_out, bits(0.05) - bits(0.99), 1e-9),
                f"the pass without duplicates lies inside the merged S: {verdict}")
        logged = len(wb.store.edit_history())
        require(wb.compress() == () and ids(wb.theory) == (h1, h2) and len(wb.store.edit_history()) == logged and wb.negatives() == (),
                "compress() leaves them apart and writes nothing")
        require(wb.partition() == {"r1": f"{ENGINE}|{h1}", "r3": f"{ENGINE}|{h2}"}, "two families")

    # 3. an over-general S with passes inside it: tightened to what its positives share, once that pays
    with tempfile.TemporaryDirectory(prefix="s07-gate-") as tmp:
        wb, h1 = opened_bench(tmp)
        h2 = hand_h2(wb, h1).payload["adds"][0]
        for index in range(16):
            out = wb.observe(phi("x8"), pass_label(), f"c{index}")
            require(out.observation.triage == "unexpected_pass" and out.rolled_back == (), f"balanced duplicates pass inside S: {out}")
            if index in (4, 15):
                (candidate,) = wb.repair_candidates()
                verdict = wb.assess(candidate)
                require(candidate.kind == "revise" and candidate.removes == (h2,) and tuple(candidate.adds[0].specific) == C6.S_X1
                        and candidate.trigger == tuple(f"c{i}" for i in range(index + 1)) and candidate.bets == (bet(C6.S_X1),)
                        and close(verdict.delta_length, 8 * lit, 1e-6) and verdict.delta_in < -4.2 * (index + 1) and verdict.delta_out == 0.0,
                        f"after {index + 1} passes: tighten S to what the positives share: {candidate} {verdict}")
                require(verdict.accepted is (index == 15) and (verdict.reason == "no_gain") is (index == 4),
                        f"{index + 1} contradictions against {8 * lit:.1f} bits of extra literals: {verdict}")
        (tightened,) = wb.compress()
        h3 = tightened.payload["adds"][0]
        new = wb.theory.get(h3)
        require(tightened.kind == "revise" and tuple(new.specific) == C6.S_X1 and new.contradictions == () and new.positives == ("r1",)
                and wb.predict(phi("x8"), ORACLE).zone == "unexplored" and wb.owner_of("r1") == h3 and wb.compress() == (),
                f"after tightening, the passes are no longer inside S: {new.to_dict()}")

    # 4. one hypothesis that swallowed two kinds of failure, with passes in between: split
    with tempfile.TemporaryDirectory(prefix="s07-gate-") as tmp:
        wb, h1 = opened_bench(tmp)
        loose = wb.propose(T.Proposal(kind="revise", rationale="duplicates on the left are enough", proposer="hand", removes=(h1,),
                                      adds=(reworded(wb, h1, (C6.L_DUPS,)),), bets=(bet([C6.INT_ALL, C6.L_DUPS]),)))
        h2 = loose.payload["adds"][0]
        out = wb.observe(phi("x4"), fail_label("df_missing_raw", attribution=(h2, True)), "r2")
        require(out.owner == h2 and out.bets == ((loose.edit_id, 0, "kept"),), f"an INTERSECT ALL that loses rows is taken for the same bug: {out}")
        for index in range(40):
            wb.observe(G6.phi(W_UNION), pass_label(), f"c{index}")
            if index == 29:
                (candidate,) = wb.repair_candidates()
                require(candidate.kind == "split" and wb.assess(candidate).reason == "no_gain", "30 passes do not yet pay for a second hypothesis")
        (candidate,) = wb.repair_candidates()
        verdict = wb.assess(candidate)
        require(candidate.kind == "split" and candidate.removes == (h2,) and [tuple(a.specific) for a in candidate.adds] == [C6.S_X1, C6.S_X4]
                and candidate.bets == (bet(C6.S_X1), bet(C6.S_X4)) and len(candidate.trigger) == 40
                and verdict.accepted and close(verdict.delta_length, 2 * (per + 10 * lit) - (per + lit), 1e-6)
                and close(verdict.delta_in, 40 * (bits(0.99) - bits(0.05)), 1e-6),
                f"split along the positives so that no part covers the passes: {candidate} {verdict}")
        (split,) = wb.compress()
        a, b = split.payload["adds"]
        require(split.kind == "split" and ids(wb.theory) == (a, b) and wb.theory.get(a).positives == ("r1",) and wb.theory.get(b).positives == ("r2",)
                and wb.owner_of("r1") == a and wb.owner_of("r2") == b and wb.partition() == {"r1": f"{ENGINE}|{a}", "r2": f"{ENGINE}|{b}"},
                f"each part takes the positives it covers, and the records follow: {wb.partition()}")
        (back,) = wb.merge_candidates()
        require(back.removes == (a, b) and wb.assess(back).reason == "holdout" and wb.compress() == () and wb.repair_candidates() == (),
                "the parts are not merged back: the passes lie inside their shared S")
        require(all(e.proposer == "mdl" and e.decision == "accepted" for e in wb.edits()[1:]) and wb.store.verify() == [], "the store verifies")
    return ("merge when nothing separates two hypotheses of one identity, not when a known pass lies between them; tighten after 16 "
            "contradictions, split after 40, neither earlier; compress() reaches a fixed point and does not undo itself")


# ---- families ------------------------------------------------------------------

def check_families() -> str:
    from surprise.harness.contracts import IdentityEvidence, Label

    T = api()
    with tempfile.TemporaryDirectory(prefix="s07-gate-") as tmp:
        wb = T.Workbench.create(Path(tmp) / "store")
        duck = G6.phi("joinq", engine="duckdb")
        loose = wb.observe(duck, fail_label("f9"), "d1").observation.opened
        out = wb.observe(duck, fail_label("f1"), "d2")
        fixed = out.observation.opened
        require(loose and fixed and out.observation.effects == ((loose, "contradiction"),),
                f"a failure of another identity inside S is a counterexample that cannot be excluded: {out}")
        other = wb.observe(duck, fail_label("f1", oracle="tlp"), "d3").observation.opened
        df = wb.observe(phi("x1"), fail_label("df_missing"), "r1").observation.opened
        key = "duckdb|fix:deliminator+filter_pushdown"
        require(wb.family_of(fixed) == wb.family_of(other) == key and wb.family_of(loose) == f"duckdb|{loose}" and wb.family_of(df) == f"{ENGINE}|{df}",
                f"a fix set names a family across oracles; without one the hypothesis is the family: {wb.families()}")
        require(wb.families() == {f"duckdb|{loose}": (loose,), key: (fixed, other), f"{ENGINE}|{df}": (df,)}, f"families(): {wb.families()}")
        # a failure the harness attributed to the fix-set family, of a shape the loose hypothesis also accepts
        both = Label(y="fail", oracle="plan_variant", fail_kind="wrong_result",
                     identity=IdentityEvidence(switches=("no_optimizer",), error_class=None, behavior={"missing": 2, "extra": 2}),
                     cve={"schema": 1, "tier": 2, "isolation": "inline",
                          "attribution": {"status": "ran", "reason": None, "hypothesis_id": fixed, "method": "fix_set", "consistent": True, "executions": 1},
                          "minimize": {"status": "skipped", "reason": "attributed"}, "profile": {"status": "skipped", "reason": "attributed"}})
        out = wb.observe(duck, both, "d4")
        require(out.observation.effects == ((loose, "duplicate"), (fixed, "duplicate")) and out.owner == fixed and wb.owner_of("d4") == fixed,
                f"absorbed by two hypotheses, owned by the one the harness attributed it to: {out}")
        unexplained = wb.observe(phi("x6"), fail_label("df_both"), "r2")
        require(unexplained.owner is None and wb.owner_of("r2") is None, "an unexplained failure has no owner")
        require(wb.partition() == {"d1": f"duckdb|{loose}", "d2": key, "d3": key, "d4": key, "r1": f"{ENGINE}|{df}", "r2": None},
                f"partition(): every failure, its family or None: {wb.partition()}")
        expect_raises(KeyError, lambda: wb.owner_of("r-none"), "an unobserved record")
        expect_raises(KeyError, lambda: wb.family_of("h-none"), "an unknown hypothesis")
        # retiring a hypothesis goes through the same test: not while it alone explains a failure ...
        keep = wb.propose(T.Proposal(kind="retire", rationale="not a bug after all", proposer="hand", removes=(df,),
                                     bets=(bet(C6.S_X1, (), "pass"),)))
        require(keep.decision == "rolled_back" and keep.payload["reason"] == "holdout" and keep.surprise_delta_out > 6.0
                and wb.negatives()[-1]["claims"] == [[ENGINE, ORACLE, [], "wrong_result", None, "missing_only", list(C6.S_X1)]]
                and wb.owner_of("r1") == df, f"retiring the only explanation of a failure is refuted: {keep.to_dict()}")
        # ... but a hypothesis whose failures another one explains can go; its own records then have no owner
        joinq = T.reduce_conjunction(C6.PHI["joinq"])
        gone = wb.propose(T.Proposal(kind="retire", rationale="a debug setting, covered by the fix-set family", proposer="hand",
                                     removes=(loose,), bets=(bet(joinq, (), "pass", engine="duckdb", oracle="plan_variant"),)))
        require(gone.decision == "accepted" and gone.payload["adds"] == [] and gone.surprise_delta_out == 0.0 and loose not in ids(wb.theory)
                and gone.payload["removed"][0]["hypothesis_id"] == loose and wb.owner_of("d1") is None and wb.owner_of("d4") == fixed
                and wb.partition()["d1"] is None and len(wb.open_bets()) == 1,
                f"a retired hypothesis is kept in the edit log, and its records lose their owner: {gone.to_dict()}")
    return "fix-set families span oracles; a hypothesis without a fix set is its own family; owner = opened, attributed, or first absorber"


# ---- ciao ----------------------------------------------------------------------

def check_ciao() -> str:
    T = api()
    with tempfile.TemporaryDirectory(prefix="s07-gate-") as tmp:
        wb, h2, h3 = settled_bench(tmp)
        wb.checkpoint("after-the-bets")
        old = ["r1", "r3"]
        found = [wb.surprise_under(generation, old) for generation in range(wb.generation + 1)]
        expected = []
        for generation in range(wb.generation):
            theory = wb.store.load_generation(generation)
            expected.append((static_bits(theory, phi("x1"), ORACLE, "fail") + static_bits(theory, phi("x4"), ORACLE, "fail")) / 2)
        expected.append((static_bits(wb.theory, phi("x1"), ORACLE, "fail") + static_bits(wb.theory, phi("x4"), ORACLE, "fail")) / 2)
        require(len(found) == 3 and all(close(a, b, 1e-12) for a, b in zip(found, expected)),
                f"surprise_under(generation, records) is the mean static surprise: {found} vs {expected}")
        require(close(found[0], (bits(0.95) + 1.0) / 2) and close(found[1], bits(0.95)) and found[0] > found[1] == found[2],
                f"the theory of a later generation is less surprised by the old records: {found}")
        require(close(wb.surprise_under(1, ["r2"]), bits(0.99), 1e-9), "a pass outside every hypothesis: about 0.01 bits")
        expect_raises(ValueError, lambda: wb.surprise_under(0, []), "no records")
        expect_raises((ValueError, KeyError), lambda: wb.surprise_under(0, ["r-none"]), "an unobserved record")
        wb.observe(phi("plain"), invalid_label(), "r-invalid")
        expect_raises(ValueError, lambda: wb.surprise_under(0, ["r-invalid"]), "an invalid record has no surprise")
        expect_raises(T.StoreError, lambda: wb.surprise_under(wb.generation + 1, old), "a generation that does not exist yet")
    return f"mean surprise of the old records by generation: {', '.join(f'{value:.3f}' for value in found)} bits"


# ---- replay and ledger: the real engines ---------------------------------------------

_REPLAY: dict[str, Any] = {}


def case_of(source: str, query: str | None) -> Any:
    from surprise.harness.contracts import SqlCase

    from . import s04 as G4

    base = G4.load(source)
    return base if query is None else SqlCase(engine=base.engine, setup=base.setup, query=query, predicate=None)


def dce_probes(case: Any, limit: int) -> list[tuple[Any, str]]:
    """Neighbours of a known reproduction, regenerated with the old DCE operators, evenly thinned to ``limit``."""
    from evolution.dce import mutate_query_text, mutate_setup
    from surprise.harness.contracts import SqlCase

    found: list[tuple[Any, str]] = []
    seen = {(tuple(case.setup), case.query, case.predicate)}

    def add(setup: Any, query: str, predicate: str | None, op: str) -> None:
        key = (tuple(setup), query, predicate)
        if key not in seen:
            seen.add(key)
            found.append((SqlCase(engine=case.engine, setup=tuple(setup), query=query, predicate=predicate), op))

    for text, op in mutate_query_text(case.query):
        add(case.setup, text, case.predicate, op)
    for new_setup, op in mutate_setup(list(case.setup)):
        add(new_setup, case.query, case.predicate, op)
    if len(found) > limit:
        step = len(found) / limit
        found = [found[int(index * step)] for index in range(limit)]
    return found


def sigma_key(engine: str, label: Any) -> str:
    """The family key the old system would give this failure (diagnosis/signature.py, SignatureEngine._signature).

    The inputs are the same: the fix set and plan diff of the old bisect, the version ladder (DuckDB only in the
    old system), and the minimised case. Checked against two keys the manual ledger records, see ``ledger``.
    """
    from oracles.models import normalize_sql

    profile, minimal = label.cve["profile"], label.cve.get("minimize", {})
    fix_kind, fix_set, plan_diff = profile["fix_kind"], sorted(profile["fix_set"]), sorted(profile["plan_diff"])
    nu = profile["version_ladder"] if engine == "duckdb" else "unavailable"
    ident: dict[str, Any] = {"engine": engine, "fix_kind": fix_kind, "fix_set": fix_set, "plan_diff": plan_diff, "nu": nu}
    if (fix_kind in ("single", "minimal_set") and fix_set) or fix_kind == "flaky_parallel":
        ident = {"engine": engine, "fix_kind": fix_kind, "fix_set": fix_set, "plan_diff": plan_diff}
    elif not fix_set and not plan_diff and nu in ("unknown", "unavailable"):
        case = minimal.get("case") or {}
        sqls = list(case.get("setup") or []) + [case.get("query") or "", case.get("predicate") or ""]
        blob = "\n".join(normalize_sql(sql) for sql in sqls if sql)
        ident = {"engine": engine, "fix_kind": fix_kind, "unlocalized": True, "err_class": label.identity.error_class or "",
                 "case": hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]}
    return hashlib.sha256(json.dumps(ident, sort_keys=True).encode()).hexdigest()[:20]


def pair_scores(truth: dict[str, str], found: dict[str, str]) -> dict[str, float]:
    """Pair-counting agreement of two partitions of the same items: precision, recall, F1, adjusted Rand index."""
    items = sorted(truth)
    tp = fp = fn = tn = 0
    for index, a in enumerate(items):
        for b in items[index + 1:]:
            same_truth, same_found = truth[a] == truth[b], found[a] == found[b]
            tp += same_truth and same_found
            fp += (not same_truth) and same_found
            fn += same_truth and (not same_found)
            tn += (not same_truth) and (not same_found)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    total = tp + fp + fn + tn
    chance = (tp + fp) * (tp + fn) / total if total else 0.0
    best = ((tp + fp) + (tp + fn)) / 2
    ari = (tp - chance) / (best - chance) if best != chance else 1.0
    return {"precision": precision, "recall": recall, "f1": f1, "ari": ari}


def replay() -> dict[str, Any]:
    """Feed the known reproductions and their DCE probes once, on the real engines. Shared by ``replay`` and ``ledger``."""
    if _REPLAY:
        return _REPLAY
    from surprise import features as F
    from surprise.harness.contracts import SqlCase
    from surprise.harness.evaluate import evaluate_final
    from surprise.harness.ledger import Ledger
    from surprise.harness.manifest import build_manifest

    from . import s04 as G4

    T = api()
    run_id = "s07-replay"
    rows: list[dict[str, Any]] = []
    tmp = tempfile.mkdtemp(prefix="s07-gate-")
    wb = T.Workbench.create(Path(tmp) / "theory")
    ledger = Ledger(Path(tmp) / "ledger.sqlite")
    try:
        ledger.start_run(run_id, T.extend_manifest(build_manifest(run_id)))

        def experiment(tag: str, family: str, role: str, case: Any, oracle: str) -> dict[str, Any]:
            example = F.extract(case)
            prediction = wb.predict(example, oracle)
            owner = prediction.hypothesis_id
            options: dict[str, Any] = {"diagnose": True} if owner is None else {"hypothesis": T.attribution_request(wb.theory.get(owner))}
            record = evaluate_final(case, oracle, ledger=ledger, run_id=run_id, purpose=role, phi=example.to_dict(),
                                    theory_version=wb.theory.version, p_t=prediction.p_fail_valid, **options)
            outcome = wb.observe(example, record.label, record.record_id, prediction=prediction)
            row = {"tag": tag, "family": family, "role": role, "case": case, "oracle": oracle, "phi": example,
                   "prediction": prediction, "record": record, "outcome": outcome, "known": set(ids(wb.theory)) - {outcome.observation.opened}}
            rows.append(row)
            return row

        wrong: dict[str, Any] = {}
        for family in C.REPLAY_ORDER:
            base: tuple[str, Any, str] | None = None
            for tag, member, source, query, oracle in C.ADJUDICATED:
                if member != family:
                    continue
                case = case_of(source, query)
                experiment(tag, family, "known", case, oracle)
                base = base or (tag, case, oracle)
            assert base is not None
            for index, (probe, _op) in enumerate(dce_probes(base[1], C.PROBES[family])):
                experiment(f"{base[0]}#{index}", family, "probe", probe, base[2])
            again = experiment(f"{base[0]}@again", family, "again", base[1], base[2])
            if family == "DF-A":
                # a deliberately wrong edit, on real data: "a left input with duplicate rows is enough"
                target = again["outcome"].owner
                proposal = T.Proposal(
                    kind="revise", proposer="gate", removes=(target,), rationale="a set operation whose left input has duplicate rows loses rows",
                    adds=(dataclasses.replace(wb.theory.get(target), specific=(C6.L_DUPS,), source="gate"),),
                    bets=(bet([C6.UNI_ALL, C6.L_DUPS]),))
                wrong = {"target": target, "before": wb.theory.to_dict(), "proposal": proposal, "edit": wb.propose(proposal)}
                union = SqlCase(engine=ENGINE, setup=G4.load("DF-A").setup, query="SELECT v FROM t UNION ALL SELECT v FROM u")
                wrong["row"] = experiment("DF-A_union", "-", "bet", union, ORACLE)
                wrong["after"] = wb.theory.to_dict()
                wrong["retry"] = wb.propose(proposal)
                wrong["learned"] = experiment("DF-A_union@again", "-", "learned", union, ORACLE)
        records = ledger.records(run_id=run_id)
        manifest = ledger.run_manifest(run_id)
    finally:
        ledger.close()
    declined = [f"{p.kind}:{'+'.join(p.removes)}:{wb.assess(p).reason}" for p in (*wb.repair_candidates(), *wb.merge_candidates())]
    applied = wb.compress()
    _REPLAY.update(tmp=tmp, wb=wb, rows=rows, wrong=wrong, records=records, manifest=manifest, applied=applied, declined=declined)
    return _REPLAY


def check_replay() -> str:
    from surprise.harness.manifest import verify_manifest

    T = api()
    run = replay()
    wb, rows, wrong = run["wb"], run["rows"], run["wrong"]
    require(len(run["records"]) == len(rows) and [r.record_id for r in run["records"]] == [row["record"].record_id for row in rows],
            "one ledger record per experiment, in order")
    # 1. the five magnitudes
    seen: dict[tuple[str, str], int] = {}
    for row, stored in zip(rows, run["records"]):
        obs, label = row["outcome"].observation, row["record"].label
        require(stored.label == label and stored.phi == row["phi"].to_dict() and stored.p_t == row["prediction"].p_fail_valid
                and stored.theory_version is not None, f"{row['tag']}: the ledger keeps phi, the label and the probability given before execution")
        if label.y == "invalid":
            require(obs.surprise is None and obs.triage == "invalid" and row["outcome"].owner is None, f"{row['tag']}: an invalid experiment has no surprise")
            continue
        key = (row["prediction"].zone, label.y)
        kind, low, high = C.MAGNITUDES[key]
        require(obs.triage == kind and low <= obs.surprise <= high and close(T.surprise_bits(stored.p_t, label.y), obs.surprise),
                f"{row['tag']}: {key} gave {obs.surprise!r} bits as {obs.triage}, expected {kind} in [{low}, {high}], recomputable from the ledger")
        seen[key] = seen.get(key, 0) + 1
    for key in (("unexplored", "fail"), ("confirmed", "pass"), ("pending", "fail"), ("confirmed", "fail"), ("unexplored", "pass")):
        require(seen.get(key, 0) >= 1, f"the replay must show the magnitude of {key}; it showed {seen}")
    # 2. duplicates are recognised before execution, and then cost one attribution test
    for row in rows:
        if row["role"] != "again":
            continue
        label, obs, prediction = row["record"].label, row["outcome"].observation, row["prediction"]
        cve = label.cve
        require(prediction.zone == "confirmed" and prediction.hypothesis_id == row["outcome"].owner and label.y == "fail"
                and obs.triage == "duplicate" and cve.get("tier") == 2 and cve["attribution"].get("consistent") is True
                and cve["attribution"].get("hypothesis_id") == prediction.hypothesis_id and cve["minimize"].get("status") != "ran"
                and cve["profile"].get("status") != "ran",
                f"{row['tag']}: a known reproduction fed again must be predicted a duplicate and confirmed by one attribution test: "
                f"{prediction.zone} {label.y} tier {cve.get('tier')}")
    repeats = [row for row in rows if row["record"].label.y == "fail" and row["outcome"].owner in row["known"]]
    foreseen = [row for row in repeats if row["prediction"].zone == "confirmed"]
    cheap = [row for row in foreseen if row["record"].label.cve.get("tier") == 2]
    require(len(repeats) >= 40 and len(foreseen) >= 0.7 * len(repeats) and len(cheap) >= 0.95 * len(foreseen),
            f"of {len(repeats)} failures that joined a family already known, {len(foreseen)} were predicted duplicates before execution "
            f"and {len(cheap)} of those cost one attribution test")
    opened = [row for row in rows if row["outcome"].observation.opened]
    require(all(row["record"].label.cve.get("tier") == 3 for row in opened) and len(opened) >= len(C.REPLAY_ORDER),
            "every family was opened from a full profile")
    # 3. the deliberately wrong edit
    edit, bet_row = wrong["edit"], wrong["row"]
    require(edit.decision == "accepted" and edit.payload["length_delta"] < 0 and edit.surprise_delta_in == 0.0 and edit.surprise_delta_out == 0.0,
            f"nothing fed so far speaks against the wrong edit, and it is shorter: {edit.to_dict()}")
    out = bet_row["outcome"]
    require(bet_row["record"].label.y == "pass" and bet_row["prediction"].zone == "confirmed" and out.bets == ((edit.edit_id, 0, "broken"),)
            and out.rolled_back == (edit.edit_id,), f"UNION ALL passes on the engine, inside the edit's S: the bet is lost: {out}")
    expected = T.Theory.from_dict({**wrong["before"], "next_id": wrong["before"]["next_id"] + 1})
    expected.observe(bet_row["phi"], bet_row["record"].label, bet_row["record"].record_id)
    undone = wb.edit(edit.edit_id)
    require(wrong["after"] == expected.to_dict() and undone.decision == "rolled_back"
            and undone.payload["rollback"]["reason"] == "bet_broken" and undone.payload["rollback"]["record_id"] == bet_row["record"].record_id,
            "the edit is rolled back: the theory is the one before it, taught the pass")
    memory = [entry for entry in wb.negatives() if entry["edit_id"] == edit.edit_id]
    require(len(memory) == 1 and memory[0]["reason"] == "bet_broken" and memory[0]["record_id"] == bet_row["record"].record_id
            and wrong["retry"].decision == "rolled_back" and wrong["retry"].payload["reason"] == "negative_memory",
            f"the claim is in the negative memory and is refused when proposed again: {memory}")
    learned = wrong["learned"]
    require(learned["prediction"].zone == "unexplored" and learned["record"].label.y == "pass" and learned["outcome"].observation.surprise < 0.03,
            "fed again, the same UNION ALL no longer surprises the restored theory")
    # 4. the store after a real run
    require(wb.store.verify() == [], f"the store verifies: {wb.store.verify()}")
    again = T.Workbench.open(wb.store.root)
    require(again.theory.to_dict() == wb.theory.to_dict() and again.partition() == wb.partition()
            and sorted(p.stem for p in (wb.store.root / "hypotheses").iterdir()) == sorted(ids(wb.theory)),
            "reopened from disk it is the same theory, one file per hypothesis")
    require(verify_manifest(run["manifest"]) == [] and T.verify_theory_manifest(run["manifest"]) == []
            and all(run["manifest"]["theory"]["constants"].get(k) == v for k, v in C.CONSTANTS.items()), "the run manifest verifies, harness and theory")
    applied = run["applied"]
    require(all(e.decision == "accepted" and e.proposer == "mdl" and e.bets for e in applied) and wb.store.verify() == []
            and wb.compress() == (), "compress() on the real theory applied only accepted edits with bets, and reached a fixed point")
    compressed = [f"{e.kind}:{'+'.join(e.payload['removes'])}" for e in applied]
    fails = [row for row in rows if row["record"].label.y == "fail"]
    twice = [row["tag"] for row in fails if sum(1 for _h, what in row["outcome"].observation.effects if what in ("duplicate", "generalized")) > 1]
    shown = ", ".join(f"{zone} {y}: {count}" for (zone, y), count in sorted(seen.items()))
    return (f"{len(rows)} experiments, {len(wb.theory.hypotheses)} hypotheses; {shown}; {len(foreseen)}/{len(repeats)} repeats predicted "
            f"before execution, {len(cheap)} at tier 2; wrong edit {edit.edit_id} rolled back by {bet_row['record'].record_id}; "
            f"compress applied {compressed}, declined {run['declined']}; absorbed twice: {twice}")


def check_ledger() -> str:
    from surprise.harness.cve import certify

    run = replay()
    wb, rows = run["wb"], run["rows"]
    partition = wb.partition()
    truth: dict[str, str] = {}
    new: dict[str, str] = {}
    sigma: dict[str, str] = {}
    for row in rows:
        if row["role"] != "known":
            continue
        tag, label = row["tag"], row["record"].label
        require(label.y == "fail", f"{tag}: the manual ledger calls it a bug, the harness says {label.y}/{label.invalid_reason}")
        truth[tag] = row["family"]
        family = partition[row["record"].record_id]
        new[tag] = family if family is not None else f"unassigned:{tag}"
        if label.cve.get("profile", {}).get("status") != "ran":
            label = certify(row["case"], row["oracle"], diagnose=True)     # what sigma cost the old system for every repeat
            require(label.y == "fail" and label.cve["profile"].get("status") == "ran", f"{tag}: no profile to compute sigma from")
        sigma[tag] = sigma_key(row["case"].engine, label)
    require(len(truth) == len(C.ADJUDICATED) and len(set(truth.values())) == len(C.REPLAY_ORDER), "every adjudicated statement was fed")
    for tag, prefix in C.SIGMA_KNOWN.items():
        require(sigma[tag].startswith(prefix), f"{tag}: recomputed sigma {sigma[tag]} must be the key the manual ledger records, {prefix}")
    ours, theirs = pair_scores(truth, new), pair_scores(truth, sigma)
    require(ours["ari"] >= theirs["ari"] and ours["f1"] >= theirs["f1"],
            f"agreement with the manual ledger: new {ours}, sigma {theirs}")
    wrong_together = sorted(f"{a}+{b}" for a in truth for b in truth if a < b and truth[a] != truth[b] and new[a] == new[b])
    apart = sorted(f"{a}|{b}" for a in truth for b in truth if a < b and truth[a] == truth[b] and new[a] != new[b])
    return (f"{len(truth)} adjudicated failures in {len(set(truth.values()))} manual families: new framework {len(set(new.values()))} families, "
            f"ARI {ours['ari']:.3f}, pair F1 {ours['f1']:.3f} (P {ours['precision']:.2f} R {ours['recall']:.2f}); sigma {len(set(sigma.values()))} families, "
            f"ARI {theirs['ari']:.3f}, pair F1 {theirs['f1']:.3f} (P {theirs['precision']:.2f} R {theirs['recall']:.2f}); "
            f"merged against the ledger: {wrong_together}; split against it: {apart}")


GROUPS: dict[str, Callable[[], str]] = {
    "constants": check_constants,
    "length": check_length,
    "theory_api": check_theory_api,
    "store": check_store,
    "generations": check_generations,
    "imports": check_imports,
    "edits": check_edits,
    "accept": check_accept,
    "rollback": check_rollback,
    "journal": check_journal,
    "mdl": check_mdl,
    "families": check_families,
    "ciao": check_ciao,
    "replay": check_replay,
    "ledger": check_ledger,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S7 gate (theory store and acceptance rules)")
    parser.add_argument("--only", nargs="+", choices=list(GROUPS), metavar="GROUP",
                        help="run only these groups (the gate proper is all of them)")
    args = parser.parse_args(argv)
    selected = args.only or list(GROUPS)
    failed = 0
    try:
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
    finally:
        if _REPLAY.get("tmp"):
            shutil.rmtree(_REPLAY["tmp"], ignore_errors=True)
    scope = "" if not args.only else f" [only: {', '.join(selected)}]"
    print(f"S07 GATE{scope}: {'PASS' if not failed else 'FAIL'}"
          f" ({len(selected) - failed}/{len(selected)} groups passed)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
