"""S2 gate: contracts, ledger, manifest, and the three sound oracles.

Usage (from ``framework/``)::

    python -m surprise.gates.s02                     # everything
    python -m surprise.gates.s02 --only contracts ledger

Exit code 0 = pass. Groups, following the S2 section of SESSIONS.md:

``contracts``  the five data contracts serialise and validate;
``ledger``     the SQLite ledger keeps every record and answers by run and by
               theory version;
``manifest``   the run manifest records the harness hash and the verify
               command notices a changed file;
``oracles``    TLP (WHERE, GROUP BY and DISTINCT forms), NoREC and plan variant
               give three-valued labels: the same input is judged the same way
               twice, the known repros these oracles can catch are ``fail``,
               value-dependent errors are ``invalid``;
``evaluate``   every execution, ``pass`` and ``invalid`` included, lands in
               the ledger.

The cases and their expected labels live in ``s02_cases.py``; they were
measured with the old oracles before the adapters existed. ``--only`` exists so
a work package can run the groups it delivers; the gate itself is all groups.
Output is ASCII only: the executors' shell garbles anything else.
"""
from __future__ import annotations

import argparse
import copy
import dataclasses
import json
import platform
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from . import s02_cases as C

FRAMEWORK = Path(__file__).resolve().parents[2]
CHECKOUT = FRAMEWORK.parent

SEVEN_ORACLES = ("tlp", "norec", "plan_variant", "index_presence", "equivalent_query",
                 "version_differential", "cross_dbms")
S2_ORACLES = ("tlp", "norec", "plan_variant")
S2_FAIL_KINDS = {"wrong_result", "error_mismatch", "crash"}
S2_INVALID_REASONS = {"setup_error", "nondeterministic", "not_applicable", "query_error",
                      "value_dependent_error", "timeout", "harness_error"}
# Old modules whose code decides labels; the harness hash must cover them.
REUSED_OLD_MODULES = (
    "oracles/tlp.py", "oracles/tlp_groupby.py", "oracles/norec.py", "oracles/plan_variant.py",
    "oracles/errors.py", "oracles/determinism.py", "oracles/normalize.py", "oracles/models.py",
    "oracles/db_runner.py", "targets/duckdb_runner.py",
)


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
        raise GateFailure(f"{what}: raised {type(exc).__name__}, not the expected error") from exc
    raise GateFailure(f"{what}: no error raised")


def _tail(text: str, lines: int = 5) -> str:
    return " | ".join(ln.strip() for ln in text.strip().splitlines()[-lines:])


def _cli(*args: str, cwd: Path = FRAMEWORK) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "surprise.harness.manifest", *args], cwd=cwd, timeout=300,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")


def load_cases() -> dict[str, Any]:
    """The fixed cases as SqlCase objects, recall repros included."""
    from surprise.harness.contracts import SqlCase

    raw = dict(C.CASES)
    recall = json.loads((CHECKOUT / "docs" / "recall_repros.json").read_text(encoding="utf-8"))
    for name, family in C.RECALL_CASES.items():
        raw[name] = (tuple(recall[family]["setup"]), recall[family]["q"], None)
    return {name: SqlCase(engine="duckdb", setup=setup, query=query, predicate=predicate)
            for name, (setup, query, predicate) in raw.items()}


def _kind(label: Any) -> str | None:
    return label.fail_kind if label.y == "fail" else label.invalid_reason


# ---- contracts --------------------------------------------------------------

def check_contracts() -> str:
    from surprise.harness import contracts as hc
    from surprise.theory import contracts as tc

    require(tuple(hc.LABELS) == ("pass", "fail", "invalid"), f"LABELS is {hc.LABELS!r}")
    require(tuple(hc.ORACLE_IDS) == SEVEN_ORACLES, f"ORACLE_IDS is {hc.ORACLE_IDS!r}")
    require(S2_FAIL_KINDS <= set(hc.FAIL_KINDS), f"FAIL_KINDS lacks {S2_FAIL_KINDS - set(hc.FAIL_KINDS)}")
    require(S2_INVALID_REASONS <= set(hc.INVALID_REASONS),
            f"INVALID_REASONS lacks {S2_INVALID_REASONS - set(hc.INVALID_REASONS)}")
    require(isinstance(hc.SCHEMA_VERSION, int), "SCHEMA_VERSION must be an int")

    case = hc.SqlCase(engine="duckdb",
                      setup=["CREATE TABLE t(a INT, s VARCHAR)", "INSERT INTO t VALUES (1, '中文')"],
                      query="SELECT a FROM t", predicate="s <> '中文'")
    require(case.setup == ("CREATE TABLE t(a INT, s VARCHAR)", "INSERT INTO t VALUES (1, '中文')"),
            "SqlCase.setup must be stored as a tuple of statements")
    require(hc.SqlCase(engine="duckdb", setup=(), query="SELECT 1").predicate is None,
            "SqlCase.predicate must default to None")
    identity = hc.IdentityEvidence(switches=["no_optimizer"], error_class="InternalException",
                                   behavior={"missing": 1, "extra": 0})
    require(identity.switches == ("no_optimizer",), "IdentityEvidence.switches must be a tuple")
    labels = [
        hc.Label(y="pass", oracle="tlp", detail={"form": "where"}),
        hc.Label(y="fail", oracle="plan_variant", fail_kind="wrong_result", identity=identity,
                 cve={"rerun": {"stable": True}}, detail={"notes": "x", "queries": ["q1", "q2"]}),
        hc.Label(y="invalid", oracle="norec", invalid_reason="value_dependent_error",
                 detail={"error": "ConversionException: Conversion Error"}),
    ]
    require(labels[0].identity == hc.IdentityEvidence() and labels[0].cve == {},
            "Label.identity / Label.cve must default to empty")
    record = hc.ExperimentRecord(
        record_id="run-1:1", run_id="run-1", seq=1, case=case, label=labels[1], purpose="gate",
        created_at="2026-10-08T00:00:00+00:00",
        spec={"engine": "duckdb", "oracle": "tlp", "required": ["correlated_exists"]},
        phi={"ast": ["SELECT", "EXISTS"]}, theory_version="T0", p_t=0.25, surprise=2.0)
    bare = hc.ExperimentRecord(record_id="run-1:2", run_id="run-1", seq=2, case=case,
                               label=labels[0], purpose="gate",
                               created_at="2026-10-08T00:00:01+00:00")
    require((bare.spec, bare.phi, bare.theory_version, bare.p_t, bare.surprise)
            == (None, None, None, None, None), "optional ExperimentRecord fields must default to None")
    spec = tc.Spec(engine="duckdb", oracle="tlp", required=["correlated_exists"],
                   forbidden=["limit"], data_properties=["left_has_dups"])
    hypothesis = tc.Hypothesis(
        hypothesis_id="h1", engine="duckdb", interventions=["deliminator", "filter_pushdown"],
        plan_delta=["HASH_JOIN"], versions={"1.1.3": "fail", "1.5.5": "fail"},
        specific=["correlated_exists", "neq"], general=[["correlated_exists"], ["neq"]],
        positives=["run-1:1"], negatives=[], source="deterministic", status="proposed")
    require(hypothesis.general == (("correlated_exists",), ("neq",)),
            "Hypothesis.general must be a tuple of tuples")
    edit = tc.TheoryEdit(
        edit_id="e1", kind="new_hypothesis", rationale="理由",
        bets=[{"spec": spec.to_dict(), "predicted": "fail"}], surprise_delta_in=-1.5,
        surprise_delta_out=0.0, decision="accepted", proposer="deterministic",
        theory_version="T1", payload={"hypothesis": "h1"})

    objects = [case, identity, *labels, record, bare, spec, hypothesis, edit]
    for obj in objects:
        cls, name = type(obj), type(obj).__name__
        as_dict = obj.to_dict()
        text = json.dumps(as_dict, sort_keys=True)  # raises if not JSON-safe
        require(cls.from_dict(json.loads(text)) == obj, f"{name}: from_dict(to_dict()) differs")
        require(json.loads(obj.to_json()) == as_dict, f"{name}: to_json() disagrees with to_dict()")
        require(cls.from_json(obj.to_json()) == obj, f"{name}: from_json(to_json()) differs")
        require(cls.from_json(obj.to_json()).to_json() == obj.to_json(),
                f"{name}: to_json() is not stable across a round trip")

    bad_labels = [
        dict(y="maybe", oracle="tlp"),
        dict(y="pass", oracle="no_such_oracle"),
        dict(y="fail", oracle="tlp"),
        dict(y="fail", oracle="tlp", fail_kind="bogus"),
        dict(y="invalid", oracle="tlp"),
        dict(y="invalid", oracle="tlp", invalid_reason="bogus"),
        dict(y="pass", oracle="tlp", fail_kind="crash"),
        dict(y="fail", oracle="tlp", fail_kind="crash", invalid_reason="timeout"),
    ]
    for kwargs in bad_labels:
        expect_raises(ValueError, lambda kw=kwargs: hc.Label(**kw), f"Label({kwargs})")
    expect_raises(ValueError, lambda: tc.Spec(engine="duckdb", oracle="no_such_oracle"),
                  "Spec with an unknown oracle")
    expect_raises(ValueError, lambda: tc.TheoryEdit(
        edit_id="e2", kind="k", rationale="r", bets=[], surprise_delta_in=None,
        surprise_delta_out=None, decision="maybe", proposer="p"), "TheoryEdit with a bad decision")
    return f"{len(objects)} objects round-trip, {len(bad_labels) + 2} invalid ones rejected"


# ---- ledger -----------------------------------------------------------------

def _sample_records() -> list[Any]:
    from surprise.harness.contracts import ExperimentRecord, Label, SqlCase

    case = SqlCase(engine="duckdb", setup=("CREATE TABLE t(a INT)",), query="SELECT a FROM t",
                   predicate="a > 0")
    plan = [  # run, seq, oracle, y, kind, theory version
        ("run-a", 1, "tlp", "pass", None, "T0"),
        ("run-a", 2, "plan_variant", "fail", "wrong_result", "T0"),
        ("run-a", 3, "norec", "invalid", "value_dependent_error", "T1"),
        ("run-b", 1, "norec", "pass", None, "T1"),
        ("run-b", 2, "tlp", "invalid", "not_applicable", None),
    ]
    records = []
    for run, seq, oracle, y, kind, theory in plan:
        label = Label(y=y, oracle=oracle, fail_kind=kind if y == "fail" else None,
                      invalid_reason=kind if y == "invalid" else None)
        records.append(ExperimentRecord(
            record_id=f"{run}:{seq}", run_id=run, seq=seq, case=case, label=label,
            purpose="gate", created_at=f"2026-10-08T00:00:0{seq}+00:00", theory_version=theory))
    return records


def check_ledger() -> str:
    from surprise.harness.ledger import Ledger, LedgerError

    records = _sample_records()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ledger.sqlite"
        ledger = Ledger(path)
        try:
            ledger.start_run("run-a", {"note": "gate", "n": 1})
            ledger.start_run("run-b", {"note": "second"})
            require(ledger.run_ids() == ["run-a", "run-b"], f"run_ids() is {ledger.run_ids()!r}")
            require(ledger.run_manifest("run-a") == {"note": "gate", "n": 1}, "run_manifest differs")
            require(ledger.next_seq("run-a") == 1, "next_seq of an empty run must be 1")
            for record in records:
                ledger.append(record)
            require(ledger.next_seq("run-a") == 4, "next_seq must follow the last record")
            require(ledger.count() == 5, f"count() is {ledger.count()}")
            require(ledger.count(run_id="run-a") == 3, "count(run_id=) wrong")
            require(ledger.count(theory_version="T1") == 2, "count(theory_version=) wrong")
            require(ledger.count(y="invalid") == 2, "count(y=) wrong")
            require(ledger.count(oracle="tlp") == 2, "count(oracle=) wrong")
            require(ledger.count(run_id="run-a", y="pass") == 1, "combined filters wrong")
            require(ledger.records() == records, "records() must return every record, runs in "
                    "creation order, then seq")
            require(ledger.records(run_id="run-a") == records[:3], "records(run_id=) wrong")
            require(ledger.records(theory_version="T1") == records[2:4],
                    "records(theory_version=) wrong")
            require(ledger.records(y="fail") == records[1:2], "records(y=) wrong")
            require(ledger.label_counts() == {"pass": 2, "fail": 1, "invalid": 2},
                    f"label_counts() is {ledger.label_counts()!r}")
            require(ledger.label_counts(run_id="run-b") == {"pass": 1, "fail": 0, "invalid": 1},
                    "label_counts(run_id=) must list all three labels")
            expect_raises(LedgerError, lambda: ledger.append(records[0]), "appending a duplicate")
            orphan = dataclasses.replace(records[0], record_id="nope:1", run_id="nope")
            expect_raises(LedgerError, lambda: ledger.append(orphan), "appending to an unknown run")
            expect_raises(LedgerError, lambda: ledger.start_run("run-a", {}), "restarting a run")
            expect_raises(LedgerError, lambda: ledger.run_manifest("nope"), "manifest of unknown run")
            require(ledger.count() == 5, "a rejected write must not leave a record")
            mutators = [n for n in ("delete", "update", "remove", "clear", "truncate")
                        if hasattr(ledger, n)]
            require(not mutators, f"the ledger is append-only; found {mutators}")
            # A record must be on disk when append() returns, not when close() runs.
            other = Ledger(path)
            try:
                require(other.records() == records, "a second connection does not see the records")
            finally:
                other.close()
        finally:
            ledger.close()
        reopened = Ledger(path)
        try:
            require(reopened.records() == records, "records differ after reopening the file")
            require(reopened.run_manifest("run-b") == {"note": "second"}, "manifest lost on reopen")
        finally:
            reopened.close()
    return "5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected"


# ---- manifest ---------------------------------------------------------------

def check_manifest() -> str:
    import duckdb

    from surprise.harness import constants
    from surprise.harness import manifest as m

    first, second = m.harness_hash(), m.harness_hash()
    require(first == second, "harness_hash() differs between two calls")
    require(first.get("algorithm") == "sha256" and len(first.get("hash", "")) == 64,
            "harness_hash() must report a sha256 hex digest")
    files = first["files"]
    harness_py = {p.relative_to(FRAMEWORK).as_posix()
                  for p in (FRAMEWORK / "surprise" / "harness").rglob("*.py")
                  if "__pycache__" not in p.parts}
    missing = sorted((harness_py | set(REUSED_OLD_MODULES)) - set(files))
    require(not missing, f"harness hash does not cover: {missing[:5]}")
    require(all(len(d) == 64 for d in files.values()), "per-file digests must be sha256 hex")

    with tempfile.TemporaryDirectory() as tmp:
        lf, crlf, other = (Path(tmp) / n for n in ("lf.py", "crlf.py", "other.py"))
        lf.write_bytes(b"a = 1\nb = 2\n")
        crlf.write_bytes(b"a = 1\r\nb = 2\r\n")
        other.write_bytes(b"a = 1\nb = 3\n")
        require(m.file_digest(lf) == m.file_digest(crlf),
                "file_digest must not depend on line endings (git may check out either)")
        require(m.file_digest(lf) != m.file_digest(other), "file_digest ignores content")

    manifest = m.build_manifest("gate-s02")
    json.dumps(manifest)  # raises if not JSON-safe
    require(manifest.get("run_id") == "gate-s02", "manifest.run_id wrong")
    datetime.fromisoformat(manifest["created_at"])
    require(manifest.get("harness") == first, "manifest.harness must be harness_hash()")
    require(manifest.get("constants") == constants.as_dict(), "manifest.constants wrong")
    require(constants.as_dict().get("QUERY_TIMEOUT_S") == 10.0, "QUERY_TIMEOUT_S must be 10.0")
    environment = manifest.get("environment", {})
    require(environment.get("python") == platform.python_version(), "environment.python wrong")
    require(environment.get("engines", {}).get("duckdb") == duckdb.__version__,
            "environment.engines.duckdb wrong")
    require(m.verify_manifest(manifest) == [], f"fresh manifest fails: {m.verify_manifest(manifest)}")

    victim = "oracles/tlp.py"
    changed = copy.deepcopy(manifest)
    changed["harness"]["files"][victim] = "0" * 64
    dropped = copy.deepcopy(manifest)
    del dropped["harness"]["files"][victim]
    ghost = copy.deepcopy(manifest)
    ghost["harness"]["files"]["oracles/ghost.py"] = "1" * 64
    for name, tampered, path in (("changed digest", changed, victim),
                                 ("file not in manifest", dropped, victim),
                                 ("file gone from disk", ghost, "oracles/ghost.py")):
        problems = m.verify_manifest(tampered)
        require(problems and any(path in p for p in problems),
                f"verify_manifest misses a {name}: {problems}")

    hashed = _cli("hash")
    require(hashed.returncode == 0 and hashed.stdout.strip().splitlines()[-1].strip() == first["hash"],
            f"`manifest hash` exit {hashed.returncode}: {_tail(hashed.stdout)}")
    with tempfile.TemporaryDirectory() as tmp:
        good, bad = Path(tmp) / "manifest.json", Path(tmp) / "tampered.json"
        written = _cli("write", str(good), "--run-id", "gate-cli")
        require(written.returncode == 0 and good.is_file(),
                f"`manifest write` exit {written.returncode}: {_tail(written.stdout)}")
        on_disk = json.loads(good.read_text(encoding="utf-8"))
        require(on_disk.get("run_id") == "gate-cli" and on_disk.get("harness") == first,
                "`manifest write` wrote a different manifest")
        verified = _cli("verify", str(good))
        require(verified.returncode == 0, f"`manifest verify` exit {verified.returncode} on a "
                f"fresh manifest: {_tail(verified.stdout)}")
        bad.write_text(json.dumps(changed), encoding="utf-8")
        rejected = _cli("verify", str(bad))
        require(rejected.returncode == 1 and victim in rejected.stdout,
                f"`manifest verify` exit {rejected.returncode} on a changed file, expected 1 "
                f"and the path: {_tail(rejected.stdout)}")
        absent = _cli("verify", str(Path(tmp) / "absent.json"))
        require(absent.returncode == 2, f"`manifest verify` on a missing file: exit "
                f"{absent.returncode}, expected 2")
    return f"{len(files)} files hashed ({first['hash'][:12]}); verify catches 3 kinds of change"


# ---- oracles ----------------------------------------------------------------

class _Injecting:
    """A real DuckDB runner that answers chosen statements with a canned result.

    ``when(runner, sql)`` picks the statements. The runner notes whether the
    session is currently under ``PRAGMA disable_optimizer`` so a rule can
    target the first plan variant without counting executions.
    """

    def __init__(self, when: Callable[[Any, str], bool], result: Any):
        from oracles.db_runner import DuckDBRunner

        self._inner, self._when, self._result = DuckDBRunner(), when, result
        self.no_optimizer = False

    def run(self, sql: str, timeout_s: float = 10.0) -> Any:
        if sql.strip().upper().startswith("PRAGMA DISABLE_OPTIMIZER"):
            self.no_optimizer = True
        elif sql.strip().upper().startswith("PRAGMA ENABLE_OPTIMIZER"):
            self.no_optimizer = False
        if self._when(self, sql):
            return copy.copy(self._result)
        return self._inner.run(sql, timeout_s=timeout_s)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def _old_oracle_hit(case: Any, oracle: str, full: str) -> bool | None:
    """What the old oracle says, or None when it does not apply to the case."""
    from oracles.db_runner import DuckDBRunner
    from oracles.norec import NoRECOracle, norec_applicable
    from oracles.plan_variant import PlanVariantOracle
    from oracles.tlp import TLPOracle, tlp_applicable

    setup = list(case.setup)
    runner = DuckDBRunner()
    try:
        runner.setup(setup)
        if oracle == "tlp":
            if not tlp_applicable(case.query, case.predicate):
                return None
            return TLPOracle().check(runner, case.query, case.predicate, setup, []) is not None
        if oracle == "norec":
            if not norec_applicable(case.query, case.predicate):
                return None
            return NoRECOracle().check(runner, case.query, case.predicate, setup, []) is not None
        return PlanVariantOracle(engine="duckdb").check(runner, full, setup, []) is not None
    finally:
        runner.close()


def check_oracles() -> str:
    from oracles.db_runner import QueryResult

    from surprise.harness.contracts import SqlCase
    from surprise.harness.oracles import IMPLEMENTED, judge
    from surprise.harness.oracles.forms import full_query

    require(set(S2_ORACLES) <= set(IMPLEMENTED), f"IMPLEMENTED is {IMPLEMENTED!r}")
    cases = load_cases()
    require(set(cases) == set(C.EXPECT), "case table and expectation table disagree")
    for name, expected_sql in C.FULL_QUERIES.items():
        got = full_query(cases[name])
        require(got == expected_sql, f"full_query({name}) is {got!r}, expected {expected_sql!r}")

    judged = fails = invalids = 0
    for name, case in cases.items():
        for oracle in S2_ORACLES:
            where = f"{name}/{oracle}"
            first, second = judge(case, oracle), judge(case, oracle)
            require(first.to_dict() == second.to_dict(),
                    f"{where}: two judgements of the same input differ")
            json.dumps(first.to_dict())
            expected = C.EXPECT[name][oracle]
            require((first.y, _kind(first)) == expected,
                    f"{where}: got {(first.y, _kind(first))}, expected {expected}; "
                    f"detail {str(first.detail)[:160]}")
            require(first.oracle == oracle, f"{where}: label.oracle is {first.oracle!r}")
            if oracle == "tlp" and name in C.TLP_FORMS:
                require(first.detail.get("form") == C.TLP_FORMS[name],
                        f"{where}: form {first.detail.get('form')!r}, expected {C.TLP_FORMS[name]!r}")
            if first.y == "fail":
                require((name, oracle) in C.IDENTITY, f"{where}: unexpected fail")
                switches, missing, extra = C.IDENTITY[(name, oracle)]
                require(tuple(first.identity.switches) == switches,
                        f"{where}: switches {first.identity.switches!r}, expected {switches!r}")
                if missing is not None:
                    behavior = first.identity.behavior
                    require((behavior.get("missing"), behavior.get("extra")) == (missing, extra),
                            f"{where}: behavior {behavior!r}, expected missing={missing} extra={extra}")
                fails += 1
            else:
                require(tuple(first.identity.switches) == (),
                        f"{where}: a {first.y} label must not carry switches")
                invalids += first.y == "invalid"
            if oracle == "plan_variant" and first.y == "pass":
                require(first.detail.get("variants_compared", 0) >= 1,
                        f"{where}: a plan-variant pass must have compared at least one variant")
            # The adapters wrap the old oracles: a fail is exactly an old-oracle hit.
            if first.y in ("pass", "fail"):
                old = _old_oracle_hit(case, oracle, full_query(case))
                require(old is None or old == (first.y == "fail"),
                        f"{where}: label {first.y} but the old oracle "
                        f"{'reports' if old else 'does not report'} a discrepancy "
                        "(if this is a known repro, the environment may have changed)")
            judged += 1

    plain = cases["plain"]
    internal = QueryResult(error="InternalException: INTERNAL Error: injected by the gate",
                           is_internal_error=True)
    binder = QueryResult(error="BinderException: Binder Error: injected by the gate")
    timed_out = QueryResult(error="TimeoutError: injected by the gate", timed_out=True)
    full_plain = full_query(plain)

    def null_partition(_runner: Any, sql: str) -> bool:
        return "IS NULL" in sql.upper()

    def under_no_optimizer(runner: Any, sql: str) -> bool:
        return runner.no_optimizer and sql == full_plain

    crash = judge(plain, "tlp", runner_factory=lambda: _Injecting(null_partition, internal))
    require((crash.y, crash.fail_kind) == ("fail", "crash"),
            f"internal error in a TLP partition: got {(crash.y, _kind(crash))}, expected fail/crash")
    require(crash.identity.error_class == "InternalException",
            f"crash error_class is {crash.identity.error_class!r}, expected 'InternalException'")
    stalled = judge(plain, "tlp", runner_factory=lambda: _Injecting(null_partition, timed_out))
    require((stalled.y, stalled.invalid_reason) == ("invalid", "timeout"),
            f"timed-out TLP partition: got {(stalled.y, _kind(stalled))}, expected invalid/timeout")
    mismatch = judge(plain, "plan_variant",
                     runner_factory=lambda: _Injecting(under_no_optimizer, binder))
    require((mismatch.y, mismatch.fail_kind) == ("fail", "error_mismatch"),
            f"variant-only error: got {(mismatch.y, _kind(mismatch))}, expected fail/error_mismatch")
    require(tuple(mismatch.identity.switches) == ("no_optimizer",)
            and mismatch.identity.error_class == "BinderException",
            f"variant-only error identity: {mismatch.identity!r}")
    skipped = judge(plain, "plan_variant",
                    runner_factory=lambda: _Injecting(under_no_optimizer, timed_out))
    require(skipped.y == "pass" and "no_optimizer" in skipped.detail.get("variants_skipped", ()),
            "a timed-out variant is skipped, not a failure: expected pass with no_optimizer in "
            f"detail['variants_skipped'], got {(skipped.y, _kind(skipped))} {str(skipped.detail)[:120]}")

    expect_raises(ValueError, lambda: judge(plain, "no_such_oracle"), "judge with an unknown oracle")
    alien = SqlCase(engine="no_such_engine", setup=plain.setup, query=plain.query,
                    predicate=plain.predicate)
    expect_raises(ValueError, lambda: judge(alien, "tlp"), "judge on an unsupported engine")
    return (f"{judged} judgements stable and as expected ({fails} fail, {invalids} invalid); "
            "crash, error mismatch and timeout paths ok")


# ---- evaluate ---------------------------------------------------------------

EVALUATION_PLAN = (
    ("plain", "tlp"), ("plain", "norec"), ("plain", "plan_variant"), ("grouped", "tlp"),
    ("metrics_small", "tlp"), ("metrics_small", "norec"), ("inv_delim", "plan_variant"),
    ("vd_partial", "tlp"), ("nondeterministic_random", "norec"), ("broken_setup", "plan_variant"),
)


def check_evaluate() -> str:
    from surprise.harness.evaluate import evaluate
    from surprise.harness.ledger import Ledger
    from surprise.harness.oracles import judge

    cases = load_cases()
    run = "gate-s02"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ledger.sqlite"
        ledger = Ledger(path)
        try:
            ledger.start_run(run, {"gate": "s02"})
            returned = []
            for index, (name, oracle) in enumerate(EVALUATION_PLAN):
                theory = "T0" if index % 2 == 0 else None
                record = evaluate(cases[name], oracle, ledger=ledger, run_id=run, purpose="gate",
                                  theory_version=theory)
                where = f"{name}/{oracle}"
                require(ledger.count(run_id=run) == index + 1,
                        f"{where}: the record is not in the ledger when evaluate() returns")
                require((record.run_id, record.seq, record.purpose, record.theory_version)
                        == (run, index + 1, "gate", theory), f"{where}: record header wrong")
                require(record.case == cases[name], f"{where}: record.case differs from the input")
                require(record.label.to_dict() == judge(cases[name], oracle).to_dict(),
                        f"{where}: recorded label differs from judge()")
                require(record.surprise is None and record.p_t is None,
                        f"{where}: no theory yet, p_t and surprise must stay None")
                datetime.fromisoformat(record.created_at)
                returned.append(record)
            stored = ledger.records(run_id=run)
            require(stored == returned, "ledger.records() differs from what evaluate() returned")
            require(len({r.record_id for r in stored}) == len(stored), "record ids are not unique")
            expected_counts = {"pass": 0, "fail": 0, "invalid": 0}
            for name, oracle in EVALUATION_PLAN:
                expected_counts[C.EXPECT[name][oracle][0]] += 1
            require(min(expected_counts.values()) > 0, "gate plan must cover all three labels")
            require(ledger.label_counts(run_id=run) == expected_counts,
                    f"label counts {ledger.label_counts(run_id=run)!r}, expected {expected_counts!r}")
            require(len(ledger.records(theory_version="T0")) == 5, "theory-version query wrong")

            def exploding() -> Any:
                raise RuntimeError("runner exploded (injected by the gate)")

            broken = evaluate(cases["plain"], "tlp", ledger=ledger, run_id=run, purpose="gate",
                              runner_factory=exploding)
            require((broken.label.y, broken.label.invalid_reason) == ("invalid", "harness_error"),
                    "an exception while judging must be recorded as invalid/harness_error, got "
                    f"{(broken.label.y, _kind(broken.label))}")
            require(ledger.count(run_id=run) == len(EVALUATION_PLAN) + 1,
                    "the harness_error execution is missing from the ledger")
            total = ledger.count()
            expect_raises(ValueError, lambda: evaluate(
                cases["plain"], "no_such_oracle", ledger=ledger, run_id=run, purpose="gate"),
                "evaluate with an unknown oracle")
            expect_raises(Exception, lambda: evaluate(
                cases["plain"], "tlp", ledger=ledger, run_id="never-started", purpose="gate"),
                "evaluate on a run that was never started")
            require(ledger.count() == total, "a rejected evaluate() call left a record behind")
            # Arguments the record would reject must be refused before anything
            # runs: otherwise an execution happens and no record of it exists.
            opened = []

            def counting() -> Any:
                from oracles.db_runner import DuckDBRunner

                opened.append(1)
                return DuckDBRunner()

            for bad in ({"purpose": ""}, {"p_t": 1.5}, {"spec": {"weights": {1, 2}}}):
                kwargs = {"purpose": "gate", **bad}
                expect_raises(ValueError, lambda kw=kwargs: evaluate(
                    cases["plain"], "tlp", ledger=ledger, run_id=run, runner_factory=counting,
                    **kw), f"evaluate with {bad}")
            require(not opened, "evaluate() executed a case whose arguments it then rejected "
                    f"({len(opened)} runner(s) opened): validate before judging")
            require(ledger.count() == total, "a rejected evaluate() call left a record behind")
            returned.append(broken)
        finally:
            ledger.close()
        reopened = Ledger(path)
        try:
            require(reopened.records(run_id=run) == returned, "records differ after reopening")
        finally:
            reopened.close()
    return (f"{len(EVALUATION_PLAN) + 1} executions, {len(EVALUATION_PLAN) + 1} ledger records "
            f"({expected_counts['pass']} pass, {expected_counts['fail']} fail, "
            f"{expected_counts['invalid'] + 1} invalid)")


GROUPS: dict[str, Callable[[], str]] = {
    "contracts": check_contracts,
    "ledger": check_ledger,
    "manifest": check_manifest,
    "oracles": check_oracles,
    "evaluate": check_evaluate,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S2 gate")
    parser.add_argument("--only", nargs="+", choices=list(GROUPS), metavar="GROUP",
                        help="run only these groups (the gate proper is all of them)")
    args = parser.parse_args(argv)
    selected = args.only or list(GROUPS)
    failed = 0
    for name in selected:
        try:
            print(f"[PASS] {name}: {GROUPS[name]()}", flush=True)
        except GateFailure as exc:
            failed += 1
            print(f"[FAIL] {name}: {exc}", flush=True)
        except Exception as exc:  # noqa: BLE001 - a crashing check is a failed check
            failed += 1
            print(f"[FAIL] {name}: {type(exc).__name__}: {exc}", flush=True)
    scope = "" if not args.only else f" [only: {', '.join(selected)}]"
    print(f"S02 GATE{scope}: {'PASS' if not failed else 'FAIL'}"
          f" ({len(selected) - failed}/{len(selected)} groups passed)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
