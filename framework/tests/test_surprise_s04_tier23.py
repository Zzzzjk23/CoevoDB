"""Tier 2 attribution and tier 3 minimisation, with runners a child can import."""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from oracles.db_runner import QueryResult
from surprise.harness.contracts import SqlCase
from surprise.harness.cve import CVE_STEPS, certify
from surprise.harness.cve.criterion import RunContext, is_insert, order_like, reproduces
from surprise.harness.cve.hypothesis import parse_hypothesis
import sys

from surprise.harness.cve.isolate import call_worker

certify_impl = sys.modules["surprise.harness.cve.certify"]

TARGET = "SELECT a FROM t"
SETUP = (
    "CREATE TABLE zz_noise(k INT)",
    "INSERT INTO zz_noise VALUES (1)",
    "CREATE TABLE t(a INT)",
    "INSERT INTO t VALUES (1)",
)
_DISABLED = re.compile(r"disabled_optimizers\s*=\s*'([^']*)'", re.IGNORECASE)
_NO_OPT = re.compile(r"^\s*pragma\s+disable_optimizer\b", re.IGNORECASE)
LADDERS = ("longstanding", "recent", "unknown", "unavailable")

H_ALPHA = {"hypothesis_id": "h-alpha", "engine": "duckdb", "interventions": ["alpha"]}
H_BETA = {"hypothesis_id": "h-beta", "engine": "duckdb", "interventions": ["beta"]}
H_BOTH = {
    "hypothesis_id": "h-both",
    "engine": "duckdb",
    "interventions": [],
    "fail_kind": "wrong_result",
    "error_class": None,
    "behavior_shape": "both",
}
H_MISSING = {
    "hypothesis_id": "h-missing",
    "engine": "duckdb",
    "interventions": [],
    "fail_kind": "wrong_result",
    "error_class": None,
    "behavior_shape": "missing_only",
}


def _case(query: str = TARGET) -> SqlCase:
    return SqlCase("duckdb", SETUP, query)


class _Flags:
    """One connection. ``alpha`` or ``PRAGMA disable_optimizer`` is the bug switch."""

    def __init__(self) -> None:
        self.disabled: set[str] = set()
        self.no_opt = False
        self.setup_text = ""

    def setup(self, statements: Any) -> list[tuple[str, None]]:
        self.disabled = set()
        self.no_opt = False
        statements = list(statements)
        self.setup_text = "\n".join(statements).lower()
        for statement in statements:
            self.observe(statement)
        return [(statement, None) for statement in statements]

    def observe(self, sql: str) -> None:
        if _NO_OPT.match(sql):
            self.no_opt = True
        found = _DISABLED.search(sql)
        if found:
            self.disabled = {part.strip() for part in found.group(1).split(",") if part.strip()}

    def buggy(self) -> bool:
        has_table = "create table t" in self.setup_text
        has_insert = "insert into t" in self.setup_text
        if not has_table or not has_insert:
            return False
        return self.no_opt or "alpha" in self.disabled

    def close(self) -> None:
        pass


class WrongRows(_Flags):
    """Default plan returns ``[[1]]``. The bug switch returns ``[[2]]``."""

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        self.observe(sql)
        if "duckdb_optimizers" in sql.lower():
            return QueryResult(rows=[["alpha"], ["beta"]], columns=["name"])
        if sql.strip().upper().startswith("EXPLAIN"):
            name = "SEQ_SCAN" if self.no_opt or "alpha" in self.disabled else "HASH_JOIN"
            payload = json.dumps([{"name": name}])
            return QueryResult(rows=[["explain", payload]], columns=["key", "value"])
        if sql.strip().rstrip(";") == TARGET and self.buggy():
            return QueryResult(rows=[[2]], columns=["a"])
        return QueryResult(rows=[[1]], columns=["a"])


class CrashRows(_Flags):
    """The bug switch raises ``InternalException``. The default plan returns a row."""

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        self.observe(sql)
        if "duckdb_optimizers" in sql.lower():
            return QueryResult(rows=[["alpha"], ["beta"]], columns=["name"])
        if sql.strip().upper().startswith("EXPLAIN"):
            return QueryResult(rows=[["explain", json.dumps([{"name": "HASH_JOIN"}])]])
        if sql.strip().rstrip(";") == TARGET and self.buggy():
            return QueryResult(
                rows=[],
                error="InternalException: INTERNAL Error: boom",
                is_internal_error=True,
            )
        return QueryResult(rows=[[1]], columns=["a"])


class FlakyRows(WrongRows):
    """The discrepancy exists on the first witnessed execution and then disappears."""

    seen = 0

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        if sql.strip().rstrip(";") == TARGET and self.no_opt:
            FlakyRows.seen += 1
            if FlakyRows.seen > 1:
                return QueryResult(rows=[[1]], columns=["a"])
        return super().run(sql, timeout_s=timeout_s)


class _AlwaysError:
    def setup(self, statements: Any) -> list[tuple[str, None]]:
        return [(statement, None) for statement in statements]

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        return QueryResult(rows=[], error="InternalException: INTERNAL Error: boom", is_internal_error=True)

    def close(self) -> None:
        pass


class _SetupError:
    def setup(self, statements: Any) -> list[tuple[str, str]]:
        return [(statement, "Catalog Error: missing") for statement in statements]

    def run(self, sql: str, timeout_s: float = 10.0) -> QueryResult:
        raise AssertionError("a failed setup must not run the query")

    def close(self) -> None:
        pass


def _context(factory: Any, switches: tuple[str, ...] = ("no_optimizer",)) -> RunContext:
    return RunContext(
        oracle="plan_variant",
        factory=factory,
        timeout_s=1.0,
        switches=switches,
        predicate=None,
    )


def test_reproduction_treats_matching_crashes_as_agreement() -> None:
    agreed = reproduces(_context(_AlwaysError), "duckdb", [], TARGET, None, [])
    assert agreed is False
    disagreed = reproduces(_context(CrashRows), "duckdb", list(SETUP), TARGET, None, [])
    assert disagreed is True
    assert reproduces(_context(_SetupError), "duckdb", list(SETUP), TARGET, None, []) is False


def test_hypothesis_rejects_bad_shapes_before_any_runner() -> None:
    opened: list[int] = []

    class Spy(WrongRows):
        def __init__(self) -> None:
            opened.append(1)
            super().__init__()

    case = _case()
    with pytest.raises(ValueError):
        parse_hypothesis("h-f1", "duckdb")
    with pytest.raises(ValueError):
        parse_hypothesis({"engine": "duckdb", "interventions": []}, "duckdb")
    with pytest.raises(ValueError):
        parse_hypothesis({"hypothesis_id": "h", "engine": "duckdb", "interventions": "alpha"}, "duckdb")
    with pytest.raises(ValueError):
        parse_hypothesis({"hypothesis_id": "h", "engine": "duckdb", "interventions": []}, "duckdb")
    with pytest.raises(ValueError):
        certify(
            case, "plan_variant",
            hypothesis={"hypothesis_id": "h", "engine": "datafusion", "interventions": ["alpha"]},
            runner_factory=Spy, isolation="inline",
        )
    assert opened == []
    with pytest.raises(ValueError):
        certify(
            case, "plan_variant",
            hypothesis={"hypothesis_id": "h", "engine": "duckdb", "interventions": ["no_such"]},
            runner_factory=Spy, isolation="inline",
        )
    assert opened
    parsed = parse_hypothesis(dict(H_ALPHA, note="ignored", plan_delta=["HASH_JOIN"]), "duckdb")
    assert parsed.interventions == ("alpha",)
    assert is_insert("  INSERT INTO t VALUES (1)") is True
    assert is_insert("CREATE TABLE t(a INT)") is False
    assert order_like(SETUP, ["CREATE TABLE t(a INT)"], ["INSERT INTO t VALUES (1)"]) == [
        "CREATE TABLE t(a INT)",
        "INSERT INTO t VALUES (1)",
    ]


def test_fix_set_attribution_consistent_and_inconsistent() -> None:
    case = _case()
    held = certify(case, "plan_variant", hypothesis=H_ALPHA, runner_factory=WrongRows, isolation="inline")
    assert (held.y, held.fail_kind) == ("fail", "wrong_result")
    assert held.cve["tier"] == 2
    attribution = held.cve["attribution"]
    assert attribution["status"] == "ran" and attribution["consistent"] is True
    assert attribution["hypothesis_id"] == "h-alpha" and attribution["method"] == "fix_set"
    assert attribution["executions"] == 1
    assert held.cve["minimize"] == {"status": "skipped", "reason": "attributed"}
    assert held.cve["profile"] == {"status": "skipped", "reason": "attributed"}
    assert tuple(held.identity.switches) == ("no_optimizer",)

    also = certify(
        case, "plan_variant", hypothesis=H_ALPHA, diagnose=True,
        runner_factory=WrongRows, isolation="inline",
    )
    assert also.cve["tier"] == 2 and also.cve["minimize"]["reason"] == "attributed"

    missed = certify(case, "plan_variant", hypothesis=H_BETA, runner_factory=WrongRows, isolation="inline")
    assert missed.cve["tier"] == 3 and missed.cve["attribution"]["consistent"] is False
    assert missed.cve["profile"]["fix_set"] == ["alpha"]
    assert tuple(missed.identity.switches) == ("alpha",)
    assert missed.cve["profile"]["witness_switches"] == ["no_optimizer"]
    assert missed.cve["profile"]["behavior_shape"] == "both"


def test_profile_attribution_and_a_pass_skip_tier_3() -> None:
    case = _case()
    held = certify(case, "plan_variant", hypothesis=H_BOTH, runner_factory=WrongRows, isolation="inline")
    assert held.cve["tier"] == 2
    assert held.cve["attribution"]["method"] == "profile"
    assert held.cve["attribution"]["consistent"] is True
    assert held.cve["attribution"]["executions"] == 0

    missed = certify(case, "plan_variant", hypothesis=H_MISSING, runner_factory=WrongRows, isolation="inline")
    assert missed.cve["attribution"]["consistent"] is False and missed.cve["tier"] == 3
    assert missed.cve["profile"]["behavior_shape"] == "both"

    clean = certify(
        _case("SELECT 1"), "plan_variant", hypothesis=H_ALPHA, diagnose=True,
        runner_factory=WrongRows, isolation="inline",
    )
    assert clean.y == "pass" and clean.cve["tier"] == 0
    for name in CVE_STEPS:
        assert clean.cve[name] == {"status": "skipped", "reason": "not_a_candidate"}


def test_minimize_drops_unused_table_and_keeps_a_subsequence() -> None:
    case = _case()
    first = certify(case, "plan_variant", diagnose=True, runner_factory=WrongRows, isolation="inline")
    second = certify(case, "plan_variant", diagnose=True, runner_factory=WrongRows, isolation="inline")
    assert first.to_dict() == second.to_dict()
    assert first.y == "fail" and first.cve["tier"] == 3
    assert first.cve["attribution"] == {"status": "skipped", "reason": "not_requested"}
    minimize = first.cve["minimize"]
    profile = first.cve["profile"]
    assert minimize["reproduced"] is True
    assert minimize["setup_before"] == len(SETUP)
    kept = minimize["case"]["setup"]
    assert minimize["setup_after"] == len(kept)
    assert "zz_noise" not in " ".join(kept).lower()
    assert any(is_insert(statement) and "into t" in statement.lower() for statement in kept)
    position = 0
    for statement in kept:
        position = list(SETUP).index(statement, position) + 1
    assert profile["fix_kind"] == "single" and profile["fix_set"] == ["alpha"]
    assert profile["error_class"] is None and profile["behavior_shape"] == "both"
    assert profile["witness_switches"] == ["no_optimizer"]
    assert isinstance(profile["plan_diff"], list) and profile["plan_diff"]
    assert all(isinstance(op, str) for op in profile["plan_diff"])
    assert profile["version_ladder"] in LADDERS
    assert isinstance(profile["executions"], int) and profile["executions"] > 0
    assert tuple(first.identity.switches) == ("alpha",)


def test_crash_fix_agrees_on_both_forms() -> None:
    case = _case()
    held = certify(case, "plan_variant", hypothesis=H_ALPHA, runner_factory=CrashRows, isolation="inline")
    assert (held.y, held.fail_kind) == ("fail", "crash")
    assert held.identity.error_class == "InternalException"
    assert held.cve["tier"] == 2 and held.cve["attribution"]["consistent"] is True
    assert held.cve["profile"]["status"] == "skipped"

    missed = certify(case, "plan_variant", hypothesis=H_BETA, runner_factory=CrashRows, isolation="inline")
    assert missed.cve["tier"] == 3
    assert missed.cve["profile"]["fix_set"] == ["alpha"]
    assert missed.cve["profile"]["behavior_shape"] is None
    assert missed.cve["profile"]["error_class"] == "InternalException"
    assert missed.cve["profile"]["witness_switches"] == ["no_optimizer"]
    assert tuple(missed.identity.switches) == ("alpha",)


def test_minimiser_that_loses_the_bug_is_invalid() -> None:
    state = {"stopped": False}

    class Sticky(WrongRows):
        def setup(self, statements: Any) -> list[tuple[str, None]]:
            if len(list(statements)) < len(SETUP):
                state["stopped"] = True
            return super().setup(statements)

        def buggy(self) -> bool:
            if state["stopped"]:
                return False
            return super().buggy()

    label = certify(_case(), "plan_variant", diagnose=True, runner_factory=Sticky, isolation="inline")
    assert (label.y, label.invalid_reason) == ("invalid", "not_reproduced_minimized")
    assert state["stopped"] is True
    assert label.cve["tier"] == 3
    assert label.cve["minimize"]["status"] == "ran" and label.cve["minimize"]["reproduced"] is False
    assert label.cve["profile"] == {"status": "skipped", "reason": "not_reproduced_minimized"}
    assert tuple(label.identity.switches) == ()


def test_tier1_downgrade_does_not_run_tier3() -> None:
    FlakyRows.seen = 0
    label = certify(_case(), "plan_variant", diagnose=True, runner_factory=FlakyRows, isolation="inline")
    assert (label.y, label.invalid_reason) == ("invalid", "unstable_rerun")
    assert label.cve["minimize"] == {"status": "skipped", "reason": "not_requested"}
    assert label.cve["profile"] == {"status": "skipped", "reason": "not_requested"}


def test_process_attribution_and_a_dead_child_stay_at_tier_1(monkeypatch: pytest.MonkeyPatch) -> None:
    case = _case()
    label = certify(case, "plan_variant", hypothesis=H_ALPHA, runner_factory=WrongRows, isolation="process")
    assert label.cve["tier"] == 2 and label.cve["attribution"]["consistent"] is True
    assert label.cve["isolation"] == "process"

    real = call_worker

    def wrapped(payload: dict[str, Any], wall: float) -> dict[str, Any]:
        if payload.get("op") == "diagnose":
            return {"kind": "timeout"}
        return real(payload, wall)

    monkeypatch.setattr(certify_impl, "call_worker", wrapped)
    timed = certify(case, "plan_variant", diagnose=True, runner_factory=WrongRows, isolation="process")
    assert timed.y == "fail" and timed.cve["tier"] == 1
    assert timed.cve["minimize"] == {"status": "skipped", "reason": "timeout"}
    assert timed.cve["profile"] == {"status": "skipped", "reason": "timeout"}
    assert tuple(timed.identity.switches) == ("no_optimizer",)

    def crash_attribute(payload: dict[str, Any], wall: float) -> dict[str, Any]:
        if payload.get("op") == "attribute":
            return {"kind": "crash", "exit_code": 1}
        return real(payload, wall)

    monkeypatch.setattr(certify_impl, "call_worker", crash_attribute)
    crashed = certify(case, "plan_variant", hypothesis=H_ALPHA, runner_factory=WrongRows, isolation="process")
    assert crashed.y == "fail" and crashed.cve["tier"] == 1
    assert crashed.cve["attribution"] == {"status": "skipped", "reason": "crash"}
    assert crashed.cve["minimize"] == {"status": "skipped", "reason": "not_requested"}
