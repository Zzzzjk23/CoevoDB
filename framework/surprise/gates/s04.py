"""S4 gate (milestone M1): the CVE pipeline and the frozen harness.

Usage (from ``framework/``)::

    python -m surprise.gates.s04                       # everything
    python -m surprise.gates.s04 --only tier1 premise

Exit code 0 = pass. Groups, following the S4 section of SESSIONS.md:

``contracts``    new invalid sources and constants are registered; the raw
                 oracle entry points still return ``cve == {}``; ``certify``
                 rejects bad requests before anything executes;
``isolation``    the fresh-process executor: ok, error, timeout and crash are
                 told apart, a dying child does not take the caller with it,
                 every rerun is a different OS process;
``tier1``        every discrepancy candidate is rerun in fresh processes and
                 is ``fail`` only when the outcome is stable; flaky and
                 unspecified results are ``invalid``;
``premise``      oracle premises: ASOF ties, statements that write, result
                 representations that cannot be compared across engines;
``environment``  the manifest records old engines, the PostgreSQL reference
                 and indirect packages; every old module the harness imports
                 is hashed;
``tier2``        the attribution interface, driven by hand-written hypotheses;
``tier3``        minimisation and the full profile: fix set, plan diff,
                 version ladder;
``m1``           the M1 table of HANDOFF.md through ``evaluate_final`` into
                 the ledger;
``freeze``       the frozen manifest matches the tree.

Cases and expectations live in ``s04_cases.py`` and were measured before the
pipeline existed; runner fixtures live in ``s04_fixtures.py``. ``--only``
exists so a work package can run the groups it delivers; the gate proper is
all groups. PostgreSQL reference: COEVO_REFERENCE_PG_DSN or local port 55432
(see HANDOFF). Output is ASCII only.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from . import s04_cases as C

FRAMEWORK = Path(__file__).resolve().parents[2]
CHECKOUT = FRAMEWORK.parent
FROZEN = Path(__file__).with_name("s04_frozen.json")

S3_INVALID_REASONS = (
    "setup_error", "nondeterministic", "not_applicable", "query_error", "value_dependent_error",
    "timeout", "harness_error", "untrusted_rewrite", "direction_unknown", "insufficient_engines",
    "non_unique_outlier",
)
# Top-level packages of the pre-surprise code base.
LEGACY_PACKAGES = ("oracles", "targets", "diagnosis", "agents", "scripts", "seeds", "evolution",
                   "coverage", "util", "llm", "coevo", "campaigns", "guidelines", "repair_bench")
# Never imported by the labelling code: LLM clients, and the prototype that S12 archives.
FORBIDDEN_IMPORTS = ("llm", "coevo", "openai", "anthropic", "httpx", "requests")


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


# ---- cases -----------------------------------------------------------------

_RECALL: dict[str, Any] | None = None


def recall() -> dict[str, Any]:
    global _RECALL
    if _RECALL is None:
        _RECALL = json.loads((CHECKOUT / "docs" / "recall_repros.json").read_text(encoding="utf-8"))
    return _RECALL


def load(name: str, *, extra_setup: tuple[str, ...] = ()) -> Any:
    """The named case as a SqlCase; ``recall:`` entries are read from the repo."""
    from surprise.harness.contracts import SqlCase

    engine, setup, query, predicate = C.CASES[name]
    if isinstance(setup, str):
        entry = recall()[setup.split(":", 1)[1].split("+", 1)[0]]
        statements = [statement.strip().rstrip(";") for statement in entry["setup"]]
        if setup.endswith("+data"):
            statements.append(C.F6_DATA)
        query = query or entry["q"].strip().rstrip(";")
        setup = tuple(statements)
    return SqlCase(engine=engine, setup=tuple(setup) + tuple(extra_setup), query=query,
                   predicate=predicate)


def certify(case: Any, oracle: str, **kwargs: Any) -> Any:
    from surprise.harness.cve import certify as implementation

    return implementation(load(case) if isinstance(case, str) else case, oracle, **kwargs)


def _kind(label: Any) -> str | None:
    return label.fail_kind if label.y == "fail" else label.invalid_reason


def _show(label: Any) -> str:
    return _ascii(f"{label.y}/{_kind(label)} switches={list(label.identity.switches)} "
                  f"cve={json.dumps(label.cve, sort_keys=True, default=str)[:700]}")


def cve_of(label: Any, where: str) -> dict[str, Any]:
    """Check the shape every final label shares, and return ``label.cve``."""
    from surprise.harness.contracts import LABELS

    cve = label.cve
    require(isinstance(cve, dict) and cve.get("schema") == 1, f"{where}: cve.schema must be 1: {_show(label)}")
    require(cve.get("tier") in (0, 1, 2, 3), f"{where}: cve.tier must be 0..3: {_show(label)}")
    require(cve.get("isolation") in ("process", "inline"), f"{where}: cve.isolation missing")
    raw = cve.get("raw")
    require(isinstance(raw, dict) and raw.get("y") in LABELS, f"{where}: cve.raw must carry the raw y")
    for name in C.CVE_STEPS:
        step = cve.get(name)
        require(isinstance(step, dict) and step.get("status") in ("ran", "skipped"),
                f"{where}: cve.{name}.status must be ran or skipped: {_show(label)}")
        if step["status"] == "skipped":
            require(isinstance(step.get("reason"), str) and step["reason"],
                    f"{where}: skipped step {name} must say why")
    json.dumps(label.to_dict())
    return cve


def expect_label(label: Any, y: str, kind: str | None, where: str) -> dict[str, Any]:
    require((label.y, _kind(label)) == (y, kind), f"{where}: expected {y}/{kind}, got {_show(label)}")
    return cve_of(label, where)


def ran(cve: dict[str, Any], *names: str) -> bool:
    return all(cve[name]["status"] == "ran" for name in names)


def skipped(cve: dict[str, Any], *names: str) -> bool:
    return all(cve[name]["status"] == "skipped" for name in names)


def rerun_counts() -> tuple[int, int]:
    from surprise.harness import constants

    return constants.CVE_RERUN_ATTEMPTS, constants.CVE_RERUN_EXTENDED


def expect_stable_rerun(cve: dict[str, Any], where: str) -> None:
    attempts, extended = rerun_counts()
    rerun = cve["rerun"]
    require(rerun["status"] == "ran", f"{where}: a candidate must be rerun: {rerun}")
    require(rerun.get("attempts") in (attempts, attempts + extended),
            f"{where}: rerun.attempts is {rerun.get('attempts')!r}")
    require(rerun.get("reproduced") == rerun["attempts"] and rerun.get("stable") is True,
            f"{where}: expected a stable rerun, got {rerun}")
    require(rerun.get("extended") is (rerun["attempts"] == attempts + extended),
            f"{where}: rerun.extended disagrees with attempts: {rerun}")


# ---- probes (dangerous checks run in a process of their own) ---------------

def _probe_exit() -> dict[str, Any]:
    from surprise.gates import s04_fixtures as X
    from surprise.harness.contracts import SqlCase

    case = SqlCase("duckdb", C.T_SETUP, f"SELECT a, b FROM t WHERE b > {X.EXIT_MARK}")
    label = certify(case, "plan_variant", runner_factory=X.ExitingRunner)
    return {"label": label.to_dict()}


def _probe_sleep() -> dict[str, Any]:
    from surprise.gates import s04_fixtures as X
    from surprise.harness.contracts import SqlCase

    case = SqlCase("duckdb", C.T_SETUP, f"SELECT a, b FROM t WHERE b > {X.SLEEP_MARK}")
    started = time.monotonic()
    label = certify(case, "plan_variant", runner_factory=X.SleepingRunner, wall_timeout_s=5.0)
    return {"label": label.to_dict(), "elapsed": time.monotonic() - started}


def _probe_refexit() -> dict[str, Any]:
    from surprise.gates import s04_fixtures as X

    label = certify("DF-A", "cross_dbms", reference_factories={
        "duckdb": X.ExitingReference, "postgres": X.ExceptAllReference})
    return {"label": label.to_dict()}


PROBES: dict[str, Callable[[], dict[str, Any]]] = {
    "exit": _probe_exit, "sleep": _probe_sleep, "refexit": _probe_refexit,
}


def run_probe(name: str, timeout_s: float = 300.0) -> tuple[Any, dict[str, Any]]:
    """Run one probe in a child of the gate; return its label and its payload.

    A wrong pipeline that executes the fixture in the calling process kills
    only that child; the gate reports it instead of dying.
    """
    from surprise.harness.contracts import Label

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "surprise.gates.s04", "--probe", name], cwd=FRAMEWORK,
            timeout=timeout_s, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        raise GateFailure(f"probe {name}: still running after {timeout_s:g}s; "
                          "a hung child was not terminated") from None
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("PROBE=")), None)
    require(proc.returncode == 0 and line is not None,
            f"probe {name}: the calling process exited with code {proc.returncode} and no result "
            f"(the pipeline ran the target in its own process?): {_ascii(proc.stdout.strip()[-300:])}")
    payload = json.loads(line[len("PROBE="):])
    return Label.from_dict(payload["label"]), payload


# ---- contracts -------------------------------------------------------------

def check_contracts() -> str:
    from surprise.harness import constants, cve
    from surprise.harness import contracts as hc
    from surprise.harness.evaluate import evaluate
    from surprise.harness.ledger import Ledger
    from surprise.harness.manifest import build_manifest
    from surprise.harness.oracles import judge

    require(tuple(hc.LABELS) == ("pass", "fail", "invalid"), f"LABELS is {hc.LABELS!r}")
    require(tuple(hc.FAIL_KINDS) == ("wrong_result", "error_mismatch", "crash"),
            f"FAIL_KINDS is {hc.FAIL_KINDS!r}")
    require(tuple(hc.INVALID_REASONS[:11]) == S3_INVALID_REASONS,
            "the eleven invalid sources of S3 must keep their order")
    require(tuple(hc.INVALID_REASONS[11:]) == C.NEW_INVALID_REASONS,
            f"new invalid sources must be {C.NEW_INVALID_REASONS}, got {hc.INVALID_REASONS[11:]!r}")
    require(tuple(cve.CVE_STEPS) == C.CVE_STEPS, f"CVE_STEPS is {cve.CVE_STEPS!r}")
    shapes = [({"missing": 1, "extra": 0}, "missing_only"), ({"missing": 0, "extra": 2}, "extra_only"),
              ({"missing": 1, "extra": 1}, "both"), ({"missing": 0, "extra": 0}, "none"), ({}, "none")]
    for behavior, shape in shapes:
        require(cve.behavior_shape(behavior) == shape,
                f"behavior_shape({behavior}) is {cve.behavior_shape(behavior)!r}, expected {shape!r}")

    listed = constants.as_dict()
    require(listed.get("QUERY_TIMEOUT_S") == 10.0, "QUERY_TIMEOUT_S must stay 10.0")
    require(listed.get("CVE_RERUN_ATTEMPTS") == 5 and listed.get("CVE_RERUN_EXTENDED") == 15,
            f"CVE_RERUN_ATTEMPTS / CVE_RERUN_EXTENDED must be 5 / 15, got {listed}")
    cve_constants = sorted(name for name in listed if name.startswith("CVE_"))
    require(len(cve_constants) >= 3, f"CVE budgets and time limits belong in constants.py: {cve_constants}")
    require(build_manifest("gate-s04")["constants"] == listed, "manifest.constants differs from as_dict()")

    # The raw oracle layer keeps its S2/S3 contract; CVE has its own entry.
    plain, f1 = load("plain"), load("F1")
    raw_fail = judge(f1, "plan_variant")
    require((raw_fail.y, raw_fail.cve) == ("fail", {}), "judge() must stay raw: cve == {}")
    with tempfile.TemporaryDirectory(prefix="s04-gate-") as tmp:
        with Ledger(Path(tmp) / "ledger.sqlite") as ledger:
            ledger.start_run("raw", {"gate": "s04"})
            record = evaluate(f1, "plan_variant", ledger=ledger, run_id="raw", purpose="gate")
            require(record.label.to_dict() == raw_fail.to_dict(), "evaluate() must stay raw")
    final = certify(plain, "tlp")
    cve_of(final, "plain/tlp")
    require(final.y == "pass" and final.cve != {}, "certify() must fill cve even for a pass")
    require(hc.Label.from_dict(json.loads(final.to_json())) == final, "a final label must round-trip")

    def never() -> Any:
        opened.append(1)
        raise AssertionError("factory must not be called")

    opened: list[int] = []
    alien = hc.SqlCase(engine="sqlite", setup=plain.setup, query=plain.query, predicate=plain.predicate)
    bad_requests = [
        ("unknown oracle", lambda: certify(plain, "no_such_oracle")),
        ("unsupported target", lambda: certify(alien, "tlp")),
        ("unknown isolation", lambda: certify(plain, "tlp", isolation="thread")),
        ("factory a child cannot import", lambda: certify(plain, "tlp", runner_factory=never)),
        ("version alias as reference", lambda: certify(plain, "cross_dbms",
                                                       reference_factories={"duckdb_old": never})),
    ]
    for what, call in bad_requests:
        expect_raises(ValueError, call, f"certify with {what}")
    require(not opened, "a rejected certify() request must not execute anything")
    return (f"{len(hc.INVALID_REASONS)} invalid sources, {len(cve_constants)} CVE constants in the manifest; "
            f"raw entry points untouched; {len(bad_requests)} bad requests rejected before execution")


# ---- isolation -------------------------------------------------------------

def check_isolation() -> str:
    from oracles.db_runner import QueryResult
    from targets.duckdb_runner import DuckDBRunner

    from surprise.gates import s04_fixtures as X
    from surprise.harness.contracts import SqlCase
    from surprise.harness.cve import execute_isolated
    from surprise.harness.oracles.forms import full_query

    attempts, _extended = rerun_counts()
    plain = load("plain")
    done = execute_isolated(plain)
    require(done.status == "ok" and done.error is None, f"plain query: {done.to_dict()}")
    runner = DuckDBRunner()
    try:
        runner.setup(list(plain.setup))
        local = runner.run(full_query(plain))
    finally:
        runner.close()
    require(QueryResult(rows=done.rows).bag() == local.bag(),
            "execute_isolated must return the rows the target runner returns")
    json.dumps(done.to_dict())

    broken = execute_isolated(SqlCase("duckdb", C.T_SETUP, "SELECT missing FROM t"))
    require(broken.status == "error" and "Binder" in (broken.error or ""),
            f"a binder error is status error: {broken.to_dict()}")

    # A statement that kills DuckDB 1.5.5 outright: the child dies, the caller lives.
    for name in C.FATAL:
        dead = execute_isolated(load(name))
        require(dead.status == "crash" and dead.exit_code not in (None, 0),
                f"{name}: expected status crash with the child's exit code, got {dead.to_dict()}")

    slow = SqlCase("duckdb", (), "SELECT count(*) FROM range(100000000) a, range(100000000) b "
                                 "WHERE a.range + b.range < 0")
    started = time.monotonic()
    hung = execute_isolated(slow, timeout_s=120.0, wall_timeout_s=3.0)
    require(hung.status == "timeout" and time.monotonic() - started < 60,
            f"wall-clock limit: expected timeout, got {hung.to_dict()}")
    interrupted = execute_isolated(slow, timeout_s=1.0, wall_timeout_s=120.0)
    require(interrupted.status == "timeout", f"statement timeout: got {interrupted.to_dict()}")

    f11 = load("F11")
    require(execute_isolated(f11).status == "ok", "F11 MERGE succeeds on the default plan")
    forced = execute_isolated(f11, prelude=("SET disabled_optimizers='build_side_probe_side'",))
    require(forced.status == "error" and "INTERNAL" in (forced.error or ""),
            f"prelude statements must run after setup and before the query: {forced.to_dict()}")

    # Every rerun of a candidate is a different OS process, never the caller's.
    with tempfile.TemporaryDirectory(prefix="s04-gate-") as tmp:
        log = Path(tmp) / "tokens.log"
        os.environ[X.TOKEN_LOG_ENV] = str(log)
        try:
            label = certify("F1", "plan_variant", runner_factory=X.TokenLogRunner)
        finally:
            del os.environ[X.TOKEN_LOG_ENV]
        cve = expect_label(label, "fail", "wrong_result", "F1 with a logging runner")
        require(cve["isolation"] == "process", "process isolation must be the default")
        tokens = set(log.read_text(encoding="ascii").split())
    require(X.PROCESS_TOKEN not in tokens, "the target ran in the calling process")
    require(len(tokens) >= 1 + attempts,
            f"expected at least {1 + attempts} distinct processes (first run + reruns), saw {len(tokens)}")

    crashed, _ = run_probe("exit")
    cve = expect_label(crashed, "fail", "crash", "a runner that kills its process")
    require(crashed.identity.error_class == "ProcessExit",
            f"a dead process has error_class ProcessExit, got {crashed.identity.error_class!r}")
    expect_stable_rerun(cve, "process crash")

    timed, payload = run_probe("sleep")
    cve = expect_label(timed, "invalid", "timeout", "a runner that never returns")
    require(payload["elapsed"] < 120, f"the hung child was not terminated promptly: {payload['elapsed']:.0f}s")
    require(cve["raw"].get("invalid_reason") == "timeout", f"raw verdict of a hang: {cve['raw']}")

    orphan, _ = run_probe("refexit")
    require(orphan.y == "invalid" and orphan.invalid_reason in ("unattributed_crash", "insufficient_engines"),
            f"a dying reference engine must not become a target failure: {_show(orphan)}")
    cve_of(orphan, "dying reference")
    return (f"ok / error / timeout x2 / crash x{len(C.FATAL)} told apart; {len(tokens)} distinct processes "
            "for one candidate; process death, hang and dying reference contained")


# ---- tier 1 ----------------------------------------------------------------

STABLE_TIER1 = ("F1", "F2", "F7", "F9", "F11", "F6")


def _inline(case: Any, wrong_rows: list[list[Any]], **script: Any) -> tuple[Any, dict[str, Any]]:
    from surprise.gates import s04_fixtures as X

    factory, state = X.scripted_factory(case.query, wrong_rows, **script)
    label = certify(case, "plan_variant", runner_factory=factory, isolation="inline")
    return label, state


def check_tier1() -> str:
    from surprise.harness.oracles import judge

    attempts, extended = rerun_counts()
    for name in STABLE_TIER1:
        oracle, kind, _switches, _fix, _ladder, error_class = C.CONFIRMED[name]
        case = load(name)
        raw = judge(case, oracle)
        label = certify(case, oracle)
        cve = expect_label(label, "fail", kind, name)
        require(cve["tier"] == 1 and cve["raw"].get("y") == "fail", f"{name}: tier 1 on a raw fail: {_show(label)}")
        expect_stable_rerun(cve, name)
        require(cve["premise"]["status"] == "ran" and cve["premise"].get("violations") == [],
                f"{name}: premises must be checked and hold: {cve['premise']}")
        require(skipped(cve, "attribution", "minimize", "profile"),
                f"{name}: tiers 2 and 3 were not requested: {_show(label)}")
        require(label.identity.to_dict() == raw.identity.to_dict(),
                f"{name}: tier 1 keeps the raw identity evidence")
        require(label.identity.error_class == error_class, f"{name}: error_class {label.identity.error_class!r}")
    twice = [certify("F1", "plan_variant").to_dict() for _ in range(2)]
    require(twice[0] == twice[1], "the same stable input certified twice must give equal labels "
            "(no process ids or timings in the label)")

    # F8: the engine picks an arbitrary case variant per run; every process answers differently.
    f8 = certify("F8", "plan_variant")
    cve = expect_label(f8, "invalid", "unstable_rerun", "F8")
    rerun = cve["rerun"]
    require(rerun["status"] == "ran" and rerun.get("stable") is False
            and rerun.get("attempts") == attempts and rerun.get("reproduced") < attempts,
            f"F8: expected an unstable rerun with the observed counts, got {rerun}")
    require(cve["raw"].get("y") == "fail" and tuple(f8.identity.switches) == (),
            "a downgraded label keeps the raw verdict in cve.raw and carries no identity")

    # F5: a race. Fresh processes mostly do not reproduce it; a lucky raw pass is allowed, a fail is not.
    observed = None
    for attempt in range(10):
        f5 = certify("F5", "plan_variant")
        cve = cve_of(f5, "F5")
        require(f5.y != "fail", f"F5 (flaky) was certified as fail on attempt {attempt + 1}: {_show(f5)}")
        if f5.y == "invalid":
            require(f5.invalid_reason == "unstable_rerun", f"F5: {_show(f5)}")
            rerun = cve["rerun"]
            require(rerun["status"] == "ran" and rerun.get("stable") is False
                    and 0 <= rerun.get("reproduced") < rerun.get("attempts"),
                    f"F5: the observed ratio must be recorded: {rerun}")
            observed = f"{rerun['reproduced']}/{rerun['attempts']}"
            break
    require(observed is not None, "F5 never produced a candidate in 10 attempts")

    for name, oracle, y, kind in (("plain", "tlp", "pass", None),
                                  ("vd_partial", "tlp", "invalid", "value_dependent_error")):
        label = certify(name, oracle)
        cve = expect_label(label, y, kind, name)
        require(cve["tier"] == 0 and skipped(cve, *C.CVE_STEPS),
                f"{name}: not a candidate, every step is skipped: {_show(label)}")
        require(label.detail == judge(load(name), oracle).detail, f"{name}: detail differs from the raw label")

    # Scripted discrepancies: the rerun rule itself, independent of any engine bug.
    inject = load("inject")
    wrong = [[2, 0]]
    label, state = _inline(inject, wrong)
    cve = expect_label(label, "fail", "wrong_result", "scripted, always")
    rerun = cve["rerun"]
    require(cve["isolation"] == "inline" and rerun.get("attempts") == attempts
            and rerun.get("reproduced") == attempts and rerun.get("extended") is False,
            f"scripted, always: {rerun}")
    require(rerun.get("single_thread") == {"ran": True, "reproduced": True},
            f"scripted, always: the single-thread rerun must be recorded: {rerun}")
    require(state["default_runs"] >= 1 + attempts and state["single_runs"] >= 1,
            f"scripted, always: expected {1 + attempts} default judgements and a single-thread one: {state}")

    label, _ = _inline(inject, wrong, single_thread_reproduces=False)
    cve = expect_label(label, "fail", "wrong_result", "scripted, parallel only")
    rerun = cve["rerun"]
    require(rerun.get("single_thread") == {"ran": True, "reproduced": False}
            and rerun.get("extended") is True and rerun.get("attempts") == attempts + extended
            and rerun.get("reproduced") == attempts + extended,
            f"a candidate that vanishes on one thread needs the extended rerun: {rerun}")

    label, _ = _inline(inject, wrong, single_thread_reproduces=False,
                       reproduces=lambda n: n != attempts + 3)
    cve = expect_label(label, "invalid", "unstable_rerun", "scripted, misses once in the extended rerun")
    rerun = cve["rerun"]
    require(rerun.get("attempts") == attempts + extended
            and rerun.get("reproduced") == attempts + extended - 1 and rerun.get("stable") is False,
            f"one miss among the extended reruns is unstable: {rerun}")

    for script, reproduced in ((lambda n: n <= 2, 1), (lambda n: n == 1, 0)):
        label, _ = _inline(inject, wrong, reproduces=script)
        cve = expect_label(label, "invalid", "unstable_rerun", f"scripted, reproduces {reproduced} time(s)")
        rerun = cve["rerun"]
        require(rerun.get("attempts") == attempts and rerun.get("reproduced") == reproduced,
                f"all {attempts} reruns must run and be counted, got {rerun}")

    # Row order alone is not a difference: bags decide.
    label, state = _inline(inject, [[2, 0], [3, -4]], permute=True)
    cve = expect_label(label, "fail", "wrong_result", "scripted, row order reversed every second run")
    expect_stable_rerun(cve, "reversed row order")
    require(state["reversed"] > 0, "the fixture never reversed a result")
    return (f"{len(STABLE_TIER1)} stable families fail after {attempts} fresh reruns; F8 unstable; "
            f"F5 reproduced {observed}; 6 scripted rerun schedules")


# ---- premises --------------------------------------------------------------

def check_premise() -> str:
    from targets.datafusion_runner import DataFusionRunner
    from targets.sqlite_runner import SQLiteRunner

    from surprise.harness.oracles import judge

    def violated(name: str, oracle: str, reason: str, **kwargs: Any) -> None:
        raw = judge(load(name), oracle, **kwargs)
        require(raw.y == "fail", f"{name}: the raw oracle must still report the candidate, got {raw.y}")
        label = certify(name, oracle, **kwargs)
        cve = expect_label(label, "invalid", reason, name)
        require(cve["premise"]["status"] == "ran" and cve["premise"].get("violations") == [reason],
                f"{name}: premise evidence must name {reason}: {cve['premise']}")
        require(cve["rerun"]["status"] == "skipped", f"{name}: no rerun is spent on a violated premise")
        require(cve["tier"] == 1 and cve["raw"].get("y") == "fail", f"{name}: {_show(label)}")

    # ASOF: which right-hand row matches is unspecified when the right side has ties.
    violated("F3", "plan_variant", "unspecified_semantics")
    asof = load("asof_no_ties")
    label, _ = _inline(asof, [[10], [30]])
    cve = expect_label(label, "fail", "wrong_result", "ASOF without ties, scripted discrepancy")
    require(cve["premise"].get("violations") == [], "a tie-free ASOF join violates no premise")

    # Statements that write: later variants see changed data. Only a crash counts.
    violated("delete_returning", "plan_variant", "side_effecting_statement")
    violated("update_returning", "plan_variant", "side_effecting_statement")
    merge = certify("F11", "plan_variant")
    cve = expect_label(merge, "fail", "crash", "F11 MERGE")
    require(cve["premise"].get("violations") == [], "a crash of a writing statement is accepted")

    # Cross-DBMS: the same DATE rendered as text by one runner and as a temporal value by another.
    violated("date_df", "cross_dbms", "incomparable_results")
    violated("date_duck", "cross_dbms", "incomparable_results",
             reference_factories={"datafusion": DataFusionRunner, "sqlite": SQLiteRunner})
    for name in ("DF-A", "DF-D"):
        label = certify(name, "cross_dbms")
        cve = expect_label(label, "fail", "wrong_result", name)
        require(cve["premise"].get("violations") == [], f"{name}: comparable results, {cve['premise']}")
    return ("ASOF ties, writing statements and incomparable cross-engine values are invalid; "
            "their tie-free, crashing and comparable counterparts stay fail")


# ---- environment -----------------------------------------------------------

def _direct_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def check_environment() -> str:
    from surprise.harness.manifest import build_manifest, verify_manifest

    manifest = build_manifest("gate-s04")
    require(json.dumps(manifest).isascii(), "the manifest must be ASCII JSON")
    environment = manifest["environment"]
    require(environment.get("old_engines") == {"duckdb": "1.1.3", "datafusion": "50.0.0"},
            f"environment.old_engines is {environment.get('old_engines')!r}")
    postgres = (environment.get("references") or {}).get("postgres")
    require(isinstance(postgres, str) and postgres.startswith("16."),
            f"environment.references.postgres is {postgres!r} (is the reference server running?)")
    packages = environment.get("packages")
    require(isinstance(packages, dict) and all(isinstance(packages.get(name), str) and packages[name]
                                               for name in ("pyarrow", "psycopg2-binary")),
            f"environment.packages must list pyarrow and psycopg2-binary: {packages!r}")
    for key in ("python", "platform", "engines"):
        require(key in environment, f"environment.{key} must stay")
    require(verify_manifest(manifest) == [], "a fresh manifest must verify")

    hashed = set(manifest["harness"]["files"])
    harness = sorted(p for p in (FRAMEWORK / "surprise" / "harness").rglob("*.py")
                     if "__pycache__" not in p.parts)
    legacy: dict[str, str] = {}
    for path in harness:
        for module in _direct_imports(path):
            top = module.split(".", 1)[0]
            require(top not in FORBIDDEN_IMPORTS,
                    f"{path.relative_to(FRAMEWORK).as_posix()} imports {module}: not allowed in the harness")
            if top in LEGACY_PACKAGES:
                candidate = FRAMEWORK / (module.replace(".", "/") + ".py")
                if candidate.is_file():
                    legacy[candidate.relative_to(FRAMEWORK).as_posix()] = path.name
    missing = sorted(set(legacy) - hashed)
    require(not missing, f"old modules imported by the harness but not hashed: {missing}")
    return (f"{len(hashed)} files hashed, {len(legacy)} imported old modules all covered; "
            f"old engines, PostgreSQL {postgres} and {len(packages)} packages recorded")


# ---- tier 2 ----------------------------------------------------------------

def check_tier2() -> str:
    def attributed(name: str, oracle: str, hypothesis: dict[str, Any], method: str) -> None:
        label = certify(name, oracle, hypothesis=hypothesis)
        cve = cve_of(label, name)
        require(label.y == "fail" and cve["tier"] == 2, f"{name}: expected a tier-2 fail, got {_show(label)}")
        attribution = cve["attribution"]
        require(attribution["status"] == "ran" and attribution.get("consistent") is True
                and attribution.get("hypothesis_id") == hypothesis["hypothesis_id"]
                and attribution.get("method") == method,
                f"{name}: expected an instance of {hypothesis['hypothesis_id']}: {attribution}")
        require(skipped(cve, "minimize", "profile"),
                f"{name}: a consistent attribution must not pay for tier 3: {_show(label)}")
        expect_stable_rerun(cve, name)

    # Engines with switches: disabling the hypothesis's fix set must resolve the discrepancy.
    attributed("F1", "plan_variant", C.H_F1, "fix_set")
    attributed("F6", "plan_variant", C.H_F1, "fix_set")
    attributed("F6_predicate", "tlp", C.H_F1, "fix_set")
    escalated = certify("F2", "plan_variant", hypothesis=C.H_F1)
    cve = expect_label(escalated, "fail", "wrong_result", "F2 predicted as an F1 instance")
    require(cve["attribution"]["status"] == "ran" and cve["attribution"].get("consistent") is False,
            f"F2 is not resolved by the F1 fix set: {cve['attribution']}")
    require(cve["tier"] == 3 and ran(cve, "minimize", "profile"),
            f"an inconsistent identity escalates to tier 3: {_show(escalated)}")
    require(cve["profile"].get("fix_set") == ["window_self_join"]
            and tuple(escalated.identity.switches) == ("window_self_join",),
            f"the escalated profile must find the real fix set: {cve['profile']}")

    # Engines without switches: error class and the shape of the difference.
    attributed("DF-A", "cross_dbms", C.H_DFA, "profile")
    other = certify("DF-B", "cross_dbms", hypothesis=C.H_DFA)
    cve = expect_label(other, "fail", "wrong_result", "DF-B predicted as a DF-A instance")
    require(cve["attribution"].get("consistent") is False and cve["tier"] == 3 and ran(cve, "profile"),
            f"DF-B has another behavior shape and must escalate: {_show(other)}")
    require(cve["profile"].get("behavior_shape") == "extra_only" and cve["profile"].get("fix_set") == [],
            f"DF-B profile: {cve['profile']}")

    # A prediction that does not come true is not a candidate at all.
    clean = certify("plain", "plan_variant", hypothesis=C.H_F1)
    cve = expect_label(clean, "pass", None, "plain predicted as an F1 instance")
    require(cve["tier"] == 0 and skipped(cve, *C.CVE_STEPS), f"a pass skips every step: {_show(clean)}")

    plain = load("plain")
    bad = [({"engine": "duckdb", "interventions": []}, "no hypothesis_id"),
           ({"hypothesis_id": "h", "engine": "datafusion", "interventions": []}, "another engine"),
           ({"hypothesis_id": "h", "engine": "duckdb", "interventions": "deliminator"}, "interventions not a list"),
           ({"hypothesis_id": "h", "engine": "duckdb", "interventions": ["no_such_switch"]}, "unknown switch"),
           ("h-f1", "not a mapping")]
    for hypothesis, what in bad:
        expect_raises(ValueError, lambda h=hypothesis: certify(plain, "plan_variant", hypothesis=h),
                      f"certify with a hypothesis that has {what}")
    extra = dict(C.H_F1, plan_delta=["HASH_JOIN"], status="accepted", source="hand")
    require(certify("F1", "plan_variant", hypothesis=extra).cve["attribution"].get("consistent") is True,
            "keys the harness does not use (a serialised theory Hypothesis) must be ignored")
    return ("fix-set attribution: F1, F6, F6 via TLP consistent, F2 escalated; "
            "profile attribution: DF-A consistent, DF-B escalated; 5 malformed hypotheses rejected")


# ---- tier 3 ----------------------------------------------------------------

def _is_subsequence(part: list[str], whole: list[str]) -> bool:
    position = 0
    for item in part:
        try:
            position = whole.index(item, position) + 1
        except ValueError:
            return False
    return True


def expect_profile(name: str, label: Any, case: Any) -> dict[str, Any]:
    from surprise.harness.contracts import SqlCase

    oracle, kind, switches, fix_set, ladder, error_class = C.CONFIRMED[name]
    cve = expect_label(label, "fail", kind, name)
    require(cve["tier"] == 3 and ran(cve, "rerun", "premise", "minimize", "profile"),
            f"{name}: diagnose=True runs tiers 1 and 3: {_show(label)}")
    require(cve["attribution"]["status"] == "skipped", f"{name}: no hypothesis was given")
    profile, minimize = cve["profile"], cve["minimize"]
    require(profile.get("fix_set") == fix_set,
            f"{name}: fix set {profile.get('fix_set')!r}, expected {fix_set!r}; profile {profile}")
    require(list(label.identity.switches) == switches,
            f"{name}: identity.switches {list(label.identity.switches)!r}, expected {switches!r}")
    require(label.identity.error_class == error_class and profile.get("error_class") == error_class,
            f"{name}: error class {label.identity.error_class!r} / {profile.get('error_class')!r}")
    require(profile.get("version_ladder") == ladder,
            f"{name}: version ladder {profile.get('version_ladder')!r}, expected {ladder!r}")
    require(isinstance(profile.get("fix_kind"), str) and profile["fix_kind"],
            f"{name}: profile.fix_kind missing")
    plan_diff = profile.get("plan_diff")
    require(isinstance(plan_diff, list) and all(isinstance(op, str) for op in plan_diff),
            f"{name}: profile.plan_diff must be a list of operator names: {plan_diff!r}")
    require(isinstance(profile.get("witness_switches"), list), f"{name}: profile.witness_switches missing")
    if kind == "wrong_result":
        require(profile.get("behavior_shape") in ("missing_only", "extra_only", "both"),
                f"{name}: profile.behavior_shape {profile.get('behavior_shape')!r}")
    require(minimize.get("reproduced") is True, f"{name}: the minimised case must reproduce: {minimize}")
    smaller = SqlCase.from_dict(minimize.get("case"))
    require(smaller.engine == case.engine and _is_subsequence(list(smaller.setup), list(case.setup)),
            f"{name}: the minimised setup must be a subsequence of the original: {smaller.setup!r}")
    require(minimize.get("setup_before") == len(case.setup) and minimize.get("setup_after") == len(smaller.setup),
            f"{name}: minimize counts disagree with the case: {minimize}")
    return cve


def check_tier3() -> str:
    for name, (oracle, *_rest) in C.CONFIRMED.items():
        case = load(name)
        cve = expect_profile(name, certify(case, oracle, diagnose=True), case)
        if name in C.RECALL_FIX_SETS:
            require(cve["profile"]["fix_set"] == sorted(recall()[name]["fix_set"]),
                    f"{name}: fix set differs from docs/recall_repros.json")
        if name in ("F1", "F2"):
            require(cve["profile"]["plan_diff"], f"{name}: the optimizer changes the plan; plan_diff is empty")
        if name == "F9":
            require(cve["profile"]["witness_switches"] == ["window_combine"], f"F9: {cve['profile']}")
        if name == "F6":
            kept = " ".join(cve["minimize"]["case"]["setup"]).lower()
            require("accounts" not in kept, "F6: the unused table must be minimised away")
    require(C.CONFIRMED["F6"][3] == C.CONFIRMED["F1"][3], "F6 is recorded as the F1 mechanism")

    noisy = load("F1", extra_setup=C.NOISE)
    cve = expect_profile("F1", certify(noisy, "plan_variant", diagnose=True), noisy)
    kept = " ".join(cve["minimize"]["case"]["setup"]).lower()
    require("zz_noise" not in kept and cve["minimize"]["setup_after"] < len(noisy.setup),
            f"an unrelated table and its rows must be minimised away: {cve['minimize']}")
    twice = [certify("F7", "plan_variant", diagnose=True).to_dict() for _ in range(2)]
    require(twice[0] == twice[1], "tier 3 on the same input twice must give equal labels")

    # A candidate that stops reproducing while it is being minimised.
    inject = load("inject")
    label, state = _inline_diagnose(inject, [[2, 0]], stop_when_reduced_below=len(inject.setup))
    cve = expect_label(label, "invalid", "not_reproduced_minimized", "scripted, lost during minimisation")
    require(state["stopped"], "the minimiser never tried a smaller setup")
    require(cve["minimize"]["status"] == "ran" and cve["minimize"].get("reproduced") is False
            and cve["profile"]["status"] == "skipped" and tuple(label.identity.switches) == (),
            f"a lost candidate is invalid, recorded, and not profiled: {_show(label)}")
    label, _ = _inline_diagnose(inject, [[2, 0]])
    cve = expect_label(label, "fail", "wrong_result", "scripted, stable through tier 3")
    require(ran(cve, "minimize", "profile") and cve["minimize"].get("reproduced") is True,
            f"scripted stable candidate: {_show(label)}")

    clean = certify("plain", "plan_variant", diagnose=True)
    cve = expect_label(clean, "pass", None, "plain with diagnose=True")
    require(cve["tier"] == 0 and skipped(cve, *C.CVE_STEPS), "nothing to diagnose on a pass")
    unstable = certify("F8", "plan_variant", diagnose=True)
    cve = expect_label(unstable, "invalid", "unstable_rerun", "F8 with diagnose=True")
    require(skipped(cve, "minimize", "profile"), "tier 3 is not spent on a candidate that failed tier 1")
    return (f"{len(C.CONFIRMED)} confirmed cases profiled: fix sets as measured and as in recall_repros.json, "
            "version ladder, minimised subsequence; noise removed; lost candidate downgraded")


def _inline_diagnose(case: Any, wrong_rows: list[list[Any]], **script: Any) -> tuple[Any, dict[str, Any]]:
    from surprise.gates import s04_fixtures as X

    factory, state = X.scripted_factory(case.query, wrong_rows, **script)
    label = certify(case, "plan_variant", runner_factory=factory, isolation="inline", diagnose=True)
    return label, state


# ---- M1 --------------------------------------------------------------------

def check_m1() -> str:
    from surprise.harness.cve import behavior_shape
    from surprise.harness.evaluate import evaluate_final
    from surprise.harness.ledger import Ledger
    from surprise.harness.manifest import build_manifest

    run = "gate-s04-m1"
    counts = {"pass": 0, "fail": 0, "invalid": 0}
    with tempfile.TemporaryDirectory(prefix="s04-gate-") as tmp:
        path = Path(tmp) / "ledger.sqlite"
        with Ledger(path) as ledger:
            ledger.start_run(run, build_manifest(run))
            written = 0

            def final(name: str, oracle: str, **kwargs: Any) -> Any:
                nonlocal written
                case = load(name)
                record = evaluate_final(case, oracle, ledger=ledger, run_id=run, purpose="m1", **kwargs)
                written += 1
                require(ledger.count(run_id=run) == written,
                        f"{name}/{oracle}: evaluate_final must write exactly one record")
                require((record.seq, record.case, record.purpose) == (written, case, "m1"),
                        f"{name}/{oracle}: record header wrong")
                cve_of(record.label, f"{name}/{oracle}")
                counts[record.label.y] += 1
                return record.label

            # Confirmed families: fail, with the measured identity (tier 3).
            for name, (oracle, *_rest) in C.CONFIRMED.items():
                expect_profile(name, final(name, oracle, diagnose=True), load(name))
            for name, (kind, shape, error_class) in C.DF_CONFIRMED.items():
                label = final(name, "cross_dbms")
                expect_label(label, "fail", kind, name)
                require(label.identity.error_class == error_class, f"{name}: error class")
                if shape is not None:
                    require(behavior_shape(label.identity.behavior) == shape,
                            f"{name}: behavior shape {behavior_shape(label.identity.behavior)!r}, expected {shape!r}")
                    require(label.detail.get("outliers") == ["datafusion"]
                            and len(label.detail.get("voters", [])) >= 3,
                            f"{name}: needs three independent engines and the target as the only outlier")
            # Unspecified semantics, flaky results, screened or erroring queries: invalid.
            for name, (oracle, reason) in C.INVALID.items():
                expect_label(final(name, oracle), "invalid", reason, name)
            f5 = final("F5", "plan_variant")
            require(f5.y != "fail" and (f5.y == "pass" or f5.invalid_reason == "unstable_rerun"),
                    f"F5 must never be fail: {_show(f5)}")
            untrusted = final("rewrite_base", "equivalent_query", paired_query="SELECT a FROM t")
            expect_label(untrusted, "invalid", "untrusted_rewrite", "inequivalent rewrite")
            # Ordinary queries and the .sql variants that do not reproduce: pass.
            for name, oracle in C.PASS:
                expect_label(final(name, oracle), "pass", None, f"{name}/{oracle}")

            # The pipeline itself failing is still an entry, and bad arguments still are not.
            def exploding() -> Any:
                raise RuntimeError("runner exploded (injected by the gate)")

            broken = evaluate_final(load("plain"), "tlp", ledger=ledger, run_id=run, purpose="m1",
                                    runner_factory=exploding, isolation="inline")
            written += 1
            counts["invalid"] += 1
            expect_label(broken.label, "invalid", "harness_error", "exploding runner")
            total = ledger.count()
            for bad in ({"purpose": ""}, {"p_t": 1.5}, {"run_id": "never-started"}):
                kwargs = {"ledger": ledger, "run_id": run, "purpose": "m1", **bad}
                expect_raises(Exception, lambda kw=kwargs: evaluate_final(load("plain"), "tlp", **kw),
                              f"evaluate_final with {bad}")
            require(ledger.count() == total == written, "a rejected evaluate_final() call left a record")
            require(ledger.label_counts(run_id=run) == counts,
                    f"ledger label counts {ledger.label_counts(run_id=run)!r}, expected {counts!r}")
            require(min(counts.values()) > 0, "M1 must put pass, fail and invalid in the ledger")
        with Ledger(path) as reopened:
            stored = reopened.records(run_id=run)
            require(len(stored) == written and all(r.label.cve.get("schema") == 1 for r in stored),
                    "every stored record must carry the CVE evidence after reopening the ledger")
    gaps = ", ".join(sorted(C.RECALL_GAPS))
    return (f"{written} final labels in the ledger ({counts['fail']} fail, {counts['invalid']} invalid, "
            f"{counts['pass']} pass); known recall gaps: {gaps}")


# ---- freeze ----------------------------------------------------------------

def check_freeze() -> str:
    from surprise.harness import constants
    from surprise.harness.manifest import harness_hash, verify_manifest

    require(FROZEN.is_file(), f"{FROZEN.name} is missing: the harness has not been frozen yet")
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    problems = verify_manifest(frozen)
    require(not problems, f"the harness changed after the freeze: {problems[:6]}")
    require(frozen["harness"]["hash"] == harness_hash()["hash"], "frozen hash differs from the tree")
    require(frozen.get("constants") == constants.as_dict(),
            "harness constants differ from the frozen manifest")
    harness_files = [path for path in frozen["harness"]["files"] if path.startswith("surprise/harness/")]
    require(any(path.startswith("surprise/harness/cve/") for path in harness_files),
            "the frozen manifest predates the CVE pipeline")
    return (f"{len(frozen['harness']['files'])} files ({len(harness_files)} in the harness), "
            f"hash {frozen['harness']['hash'][:12]}, {len(frozen['constants'])} constants match")


GROUPS: dict[str, Callable[[], str]] = {
    "contracts": check_contracts,
    "isolation": check_isolation,
    "tier1": check_tier1,
    "premise": check_premise,
    "environment": check_environment,
    "tier2": check_tier2,
    "tier3": check_tier3,
    "m1": check_m1,
    "freeze": check_freeze,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S4 gate (M1)")
    parser.add_argument("--only", nargs="+", choices=list(GROUPS), metavar="GROUP",
                        help="run only these groups (the gate proper is all of them)")
    parser.add_argument("--probe", choices=list(PROBES), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.probe:
        print("PROBE=" + json.dumps(PROBES[args.probe]()), flush=True)
        return 0
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
    print(f"S04 GATE{scope}: {'PASS' if not failed else 'FAIL'}"
          f" ({len(selected) - failed}/{len(selected)} groups passed)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
