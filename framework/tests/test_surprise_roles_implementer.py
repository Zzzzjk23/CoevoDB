"""Implementer: scripted replies, phi checks, the report, and the offline command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from surprise.features.extract import extract
from surprise.harness.contracts import SqlCase
from surprise.roles.constants import (
    IMPLEMENTER_MAX_TOKENS,
    IMPLEMENTER_TEMPERATURE,
    IMPLEMENTER_TIER,
    TIERS,
)
from surprise.roles.gateway import Gateway
from surprise.roles.implementer import (
    Implementer,
    implementer_prompt,
    implementer_report,
    main,
)
from surprise.theory.contracts import Spec

SETUP = [
    "CREATE TABLE t(v INTEGER)",
    "INSERT INTO t VALUES (1),(1),(2)",
    "CREATE TABLE u(v INTEGER)",
    "INSERT INTO u VALUES (1)",
]
GOOD_QUERY = "SELECT v FROM t EXCEPT ALL SELECT v FROM u"
UNION_QUERY = "SELECT v FROM t UNION ALL SELECT v FROM u"


class Script:
    def __init__(self, replies: Any) -> None:
        self.replies = replies if callable(replies) else list(replies)
        self.calls: list[dict[str, Any]] = []

    def complete(self, *, model: str, prompt: str, temperature: float, max_tokens: int, role: str) -> Any:
        self.calls.append(
            {
                "model": model,
                "prompt": prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "role": role,
            }
        )
        reply = self.replies(prompt) if callable(self.replies) else self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        text = reply if isinstance(reply, str) else json.dumps(reply)
        from surprise.roles.gateway import Completion

        return Completion(text=text, input_tokens=1, output_tokens=1)


def gateway(tmp: Path, script: Any, *, max_calls: int | None = 20) -> Gateway:
    return Gateway(
        cache_dir=tmp / "cache",
        ledger_path=tmp / "calls.jsonl",
        max_calls=max_calls,
        transport=script,
    )


def spec() -> dict[str, Any]:
    return {
        "engine": "duckdb",
        "oracle": "plan_variant",
        "required": ["ast:set_op:except_all", "data:setop:left_has_dups"],
        "forbidden": [],
        "data_properties": [],
    }


def reply(query: str, expect: str = "pass", setup: list[str] | None = None, **extra: Any) -> dict[str, Any]:
    body = {
        "setup": list(SETUP if setup is None else setup),
        "query": query,
        "predicate": None,
        "prediction": {"expect": expect, "why": "because"},
    }
    body.update(extra)
    return body


def implement(tmp: Path, script: Any, target: dict | None = None, **kw: Any) -> Any:
    agent = Implementer(gateway=gateway(tmp, script, max_calls=kw.pop("max_calls", 20)), extract=extract, seed=kw.pop("seed", 0), **kw)
    return agent.implement(spec() if target is None else target)


def test_prompt_lists_features_and_pitfalls_and_ignores_seed(tmp_path: Path) -> None:
    target = spec()
    text = implementer_prompt(target)
    assert text == implementer_prompt(dict(target))
    assert text == implementer_prompt(Spec.from_dict(target))
    assert "EXCEPT ALL" in text
    assert "ast:set_op:except_all" in text
    assert "data:setop:left_has_dups" in text
    assert "ROWS, RANGE, or GROUPS" in text
    assert "ASOF" in text
    assert "predicate to null" in text
    assert "Do not leave setup empty" in text
    assert "one JSON object" in text
    feedback = {"query": UNION_QUERY, "missing": ("ast:set_op:except_all",), "reason": ""}
    retry = implementer_prompt(target, feedback=feedback)
    assert UNION_QUERY in retry
    assert "missing: ast:set_op:except_all" in retry
    assert retry != text
    one = Script([reply(GOOD_QUERY)])
    two = Script([reply(GOOD_QUERY)])
    implement(tmp_path / "a", one, seed=1)
    implement(tmp_path / "b", two, seed=2)
    assert one.calls[0]["prompt"] == two.calls[0]["prompt"] == text
    assert one.calls[0]["model"] == TIERS[IMPLEMENTER_TIER]
    assert one.calls[0]["temperature"] == IMPLEMENTER_TEMPERATURE
    assert one.calls[0]["max_tokens"] == IMPLEMENTER_MAX_TOKENS
    assert one.calls[0]["role"] == "implementer"


def test_accepts_a_case_whose_phi_meets_the_spec(tmp_path: Path) -> None:
    script = Script([reply(GOOD_QUERY)])
    attempt = implement(tmp_path, script)
    assert attempt.ok and attempt.status == "ok" and attempt.first_ok and attempt.tries == 1
    assert attempt.case is not None and attempt.case.query == GOOD_QUERY
    assert attempt.phi is not None and attempt.phi.engine == "duckdb"
    assert attempt.missing == () and attempt.forbidden == () and attempt.undetermined == ()
    assert attempt.expect == "pass" and attempt.keys and attempt.spec == spec()
    stored = json.loads((tmp_path / "calls.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert stored["role"] == "implementer" and stored["status"] == "ok"


def test_retry_quotes_the_query_then_unmet_and_blocked_stop(tmp_path: Path) -> None:
    script = Script([reply(UNION_QUERY), reply(GOOD_QUERY)])
    attempt = implement(tmp_path / "retry", script)
    assert attempt.ok and attempt.tries == 2 and not attempt.first_ok
    assert UNION_QUERY in script.calls[1]["prompt"]
    assert "ast:set_op:except_all" in script.calls[1]["prompt"]
    unmet = implement(tmp_path / "unmet", Script([reply(UNION_QUERY), reply(UNION_QUERY)]))
    assert (unmet.ok, unmet.status, unmet.tries) == (False, "spec_unmet", 2)
    assert "ast:set_op:except_all" in unmet.missing
    assert unmet.case is not None and unmet.case.query == UNION_QUERY
    blocked = implement(tmp_path / "cap", Script([reply(GOOD_QUERY)]), max_calls=0)
    assert (blocked.status, blocked.tries, blocked.ok, blocked.case) == ("blocked", 1, False, None)


def test_second_call_blocked_keeps_the_parsed_case(tmp_path: Path) -> None:
    attempt = implement(tmp_path, Script([reply(UNION_QUERY), reply(GOOD_QUERY)]), max_calls=1)
    assert attempt.status == "blocked" and attempt.tries == 2 and not attempt.ok
    assert attempt.case is not None and attempt.case.query == UNION_QUERY
    assert "ast:set_op:except_all" in attempt.missing


def test_empty_query_is_a_bad_case_and_field_errors_are_rejected(tmp_path: Path) -> None:
    def no_extract(_case: SqlCase) -> Any:
        raise AssertionError("phi extracted from a refused reply")

    empty = {"setup": [], "query": "", "predicate": None, "prediction": {"expect": "pass"}}
    attempt = Implementer(
        gateway=gateway(tmp_path / "empty", Script([empty, reply(GOOD_QUERY)])),
        extract=extract,
        seed=0,
    ).implement(spec())
    assert attempt.status == "ok" and attempt.tries == 2 and not attempt.first_ok
    refused = [
        {"query": "SELECT 1"},
        {"setup": [1], "query": "SELECT 1", "predicate": None, "prediction": {"expect": "pass"}},
        {"setup": [], "query": 1, "predicate": None, "prediction": {"expect": "pass"}},
        {"setup": [], "query": "SELECT 1", "prediction": {"expect": "pass"}},
        {"setup": [], "query": "SELECT 1", "predicate": 1, "prediction": {"expect": "pass"}},
        {"setup": [], "query": "SELECT 1", "predicate": None, "prediction": {"expect": "maybe"}},
        "not json",
    ]
    for index, bad in enumerate(refused):
        seen = Implementer(
            gateway=gateway(tmp_path / f"bad{index}", Script([bad, bad])),
            extract=no_extract,
            seed=0,
        ).implement(spec())
        assert seen.status == "rejected" and seen.tries == 2 and seen.case is None, bad


def test_miss_and_error_stop_and_a_later_reject_keeps_the_last_check(tmp_path: Path) -> None:
    missed = implement(tmp_path / "miss", Script([reply(UNION_QUERY), {"prediction": "x"}]))
    # The second reply parses (prediction is present) but fails the field check, so it is rejected.
    assert missed.status == "rejected" and missed.tries == 2
    assert missed.case is not None and "ast:set_op:except_all" in missed.missing
    assert missed.expect == "pass"
    transport = Script([RuntimeError("boom")])
    agent = Implementer(gateway=gateway(tmp_path / "err", transport), extract=extract, seed=0)
    failed = agent.implement(spec())
    assert failed.status == "error" and failed.tries == 1 and failed.case is None
    offline = Implementer(
        gateway=Gateway(cache_dir=tmp_path / "off" / "cache", ledger_path=None, max_calls=5, transport=None),
        extract=extract,
        seed=0,
    )
    missed_only = offline.implement(spec())
    assert missed_only.status == "miss" and missed_only.tries == 1


def test_report_groups_by_kind_and_empty_input_is_zero(tmp_path: Path) -> None:
    union_spec = {
        "engine": "duckdb",
        "oracle": "plan_variant",
        "required": ["ast:set_op:union_all"],
        "forbidden": [],
        "data_properties": [],
    }
    limit_spec = {
        "engine": "duckdb",
        "oracle": "plan_variant",
        "required": ["ast:clause:limit"],
        "forbidden": [],
        "data_properties": [],
    }
    rows = [
        {"id": "F1/whole", "spec": spec()},
        {"id": "F1/core", "spec": union_spec},
        {"id": "DF-A/boundary", "spec": limit_spec},
    ]
    script = Script([
        reply(GOOD_QUERY),
        reply(GOOD_QUERY),
        reply(UNION_QUERY),
        reply("SELECT 1"),
        reply("SELECT 1"),
    ])
    agent = Implementer(gateway=gateway(tmp_path, script), extract=extract, seed=0)
    report = implementer_report(rows, agent)
    assert report["specs"] == 3
    assert report["first_ok"] == 1 and report["final_ok"] == 2
    assert report["first_rate"] == 1 / 3 and report["final_rate"] == 2 / 3
    assert list(report["by_kind"]) == ["whole", "core", "boundary"]
    assert report["by_kind"]["whole"] == {"specs": 1, "first_ok": 1, "final_ok": 1}
    assert report["by_kind"]["core"] == {"specs": 1, "first_ok": 0, "final_ok": 1}
    assert report["by_kind"]["boundary"] == {"specs": 1, "first_ok": 0, "final_ok": 0}
    assert [row["id"] for row in report["rows"]] == ["F1/whole", "F1/core", "DF-A/boundary"]
    assert report["rows"][2]["status"] == "spec_unmet"
    assert isinstance(report["rows"][0]["missing"], list)
    assert report["calls"]["ok"] >= 1
    empty = implementer_report([], agent)
    assert empty["specs"] == 0 and empty["first_rate"] == 0.0 and empty["final_rate"] == 0.0
    assert empty["by_kind"] == {} and empty["rows"] == []


def test_cli_offline_writes_a_report_and_an_ascii_line(tmp_path: Path, capsys: Any) -> None:
    specs_path = tmp_path / "specs.json"
    specs_path.write_text(json.dumps([{"id": "F1/core", "spec": spec()}]), encoding="utf-8")
    out = tmp_path / "nested" / "report.json"
    code = main(
        ["--specs", str(specs_path), "--cache", str(tmp_path / "cache"), "--out", str(out), "--offline", "--seed", "3"]
    )
    assert code == 0
    line = capsys.readouterr().out.strip()
    assert line.startswith("specs=1 ") and "first_ok=0" in line and "final_ok=0" in line
    assert line.isascii()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["rows"][0]["status"] == "miss" and report["rows"][0]["tries"] == 1
    ledger = out.with_name("report.calls.jsonl")
    assert ledger.is_file()
    assert json.loads(ledger.read_text(encoding="utf-8").splitlines()[0])["status"] == "miss"
