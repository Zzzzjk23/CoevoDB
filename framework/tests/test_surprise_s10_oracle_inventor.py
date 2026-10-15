"""Oracle inventor: call rhythm, template checks, and multi-engine acceptance."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from surprise.harness.contracts import SqlCase
from surprise.harness.cve.certify import certify
from surprise.harness.oracles.rewrites import RULES, load_library
from surprise.roles.base import RoleContext
from surprise.roles.conjecturer import ConjectureBook
from surprise.roles.constants import (
    ORACLE_ACCEPT_ENGINES,
    ORACLE_ACCEPT_INSTANCES,
    ORACLE_ACCEPT_MIN_ENGINES,
    ORACLE_CALLS_PER_RUN,
    ORACLE_EVERY,
    ORACLE_MAX_TOKENS,
    ORACLE_RULES_PER_CALL,
    ORACLE_TEMPERATURE,
    ORACLE_TIER,
    TIERS,
)
from surprise.roles.gateway import Completion, Gateway
from surprise.roles.oracle_inventor import OracleInventor, accept_template, oracle_prompt
from surprise.roles.runtime import build_roles

_WRAP = "SELECT * FROM ({q}) AS llm_sub"
_LIMIT = "SELECT * FROM ({q}) AS llm_sub LIMIT 1"
_IS_TRUE = "({p}) IS TRUE"
_ENGINES = ["duckdb", "datafusion", "sqlite", "postgres"]


class Script:
    """Per-role scripted transport, same pop rule as gates/s10.py."""

    def __init__(self, replies: dict) -> None:
        self.replies = {
            role: (list(reply) if isinstance(reply, list) else reply) for role, reply in replies.items()
        }
        self.calls: list[dict] = []

    def complete(self, *, model: str, prompt: str, temperature: float, max_tokens: int, role: str):
        self.calls.append({
            "model": model,
            "prompt": prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "role": role,
        })
        reply = self.replies[role]
        if isinstance(reply, list):
            reply = reply.pop(0) if len(reply) > 1 else reply[0]
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return Completion(text=text, input_tokens=1, output_tokens=1)


def _lines(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _prediction(name: str) -> dict:
    return {"rule": name, "equivalent_on": list(_ENGINES), "why": "scripted"}


def _reply(rules: list) -> dict:
    return {"rules": rules, "prediction": [_prediction(rule["name"]) for rule in rules if isinstance(rule, dict) and isinstance(rule.get("name"), str)]}


def _rule(name: str, template: str, *, kind: str = "query_wrap", argument: str = "the bag is unchanged") -> dict:
    return {"name": name, "kind": kind, "template": template, "argument": argument}


def _seeds(n: int, *, where: str | None = None, values: tuple[int, ...] = (1, 2, 3)) -> list[dict]:
    query = "SELECT a FROM t" if where is None else f"SELECT a FROM t WHERE {where}"
    inserted = ", ".join(f"({value})" for value in values)
    return [
        {
            "setup_sqls": ["CREATE TABLE t(a INTEGER)", f"INSERT INTO t VALUES {inserted}"],
            "query": query,
        }
        for _ in range(n)
    ]


def _role(tmp_path: Path, script: Script, *, oracles: tuple[str, ...] = ("equivalent_query",), seeds=None, max_calls: int = 10):
    llm = tmp_path / "llm"
    llm.mkdir(parents=True, exist_ok=True)
    gateway = Gateway(
        cache_dir=tmp_path / "cache",
        ledger_path=llm / "calls.jsonl",
        max_calls=max_calls,
        transport=script,
    )
    ctx = RoleContext(
        gateway=gateway,
        book=ConjectureBook(llm / "conjectures.jsonl"),
        extract=lambda case: None,
        registry=object(),
        readers={},
        engines=("duckdb",),
        oracles=oracles,
        seed=0,
        run_dir=tmp_path,
        llm_dir=llm,
    )
    return OracleInventor(ctx, seeds=seeds)


def _proposals(role: OracleInventor) -> list[dict]:
    return [row for row in _lines(role._book_path) if row.get("type") == "proposal"]


def test_prompt_lists_frozen_rules_templates_and_the_library() -> None:
    library = {
        "schema": 1,
        "rules": [
            {"rule_id": "llm:wrap_sub", "kind": "query_wrap", "template": _WRAP},
            {"rule_id": "llm:is_true", "kind": "predicate_wrap", "template": _IS_TRUE},
        ],
    }
    text = oracle_prompt(library=library, engines=tuple(ORACLE_ACCEPT_ENGINES))
    assert text == oracle_prompt(library=library, engines=list(ORACLE_ACCEPT_ENGINES))
    for name, entry in RULES.items():
        assert name in text
        assert entry["proof"] in text
    assert "{q}" in text and "{p}" in text
    assert _WRAP in text and _IS_TRUE in text
    assert "query_wrap" in text and "predicate_wrap" in text
    assert f"at most {ORACLE_RULES_PER_CALL}" in text
    assert "one JSON object" in text
    for engine in ORACLE_ACCEPT_ENGINES:
        assert engine in text
    wrap_at = text.index("llm:wrap_sub")
    true_at = text.index("llm:is_true")
    assert wrap_at < true_at
    assert "o-r1" not in text and "h1" not in text and "loop-s0" not in text
    assert ":\\" not in text and "seeds" not in text.split()


def test_calls_land_on_the_period_and_stop_at_the_cap(tmp_path: Path) -> None:
    script = Script({"oracle_inventor": _reply([_rule("Bad-Name", _WRAP)])})
    role = _role(tmp_path, script)
    record = SimpleNamespace(record_id="o-r1", seq=1)
    outcome = SimpleNamespace(hypothesis_id="h1", run_id="loop-s0")
    role.after(None, record, outcome)
    assert len(script.calls) == 1
    call = script.calls[0]
    assert call["model"] == TIERS[ORACLE_TIER]
    assert call["temperature"] == ORACLE_TEMPERATURE
    assert call["max_tokens"] == ORACLE_MAX_TOKENS
    assert call["role"] == "oracle_inventor"
    prompt = call["prompt"]
    assert prompt == oracle_prompt(
        library={"schema": 1, "rules": []}, engines=list(ORACLE_ACCEPT_ENGINES), call=1
    )
    assert "proposal round 1 of 3" in prompt
    assert "proposal round 2 of 3" not in prompt
    assert "o-r1" not in prompt and "h1" not in prompt and "loop-s0" not in prompt
    assert str(tmp_path) not in prompt
    for n in range(2, ORACLE_EVERY + 1):
        role.after(None, SimpleNamespace(record_id=f"o-r{n}"), outcome)
    assert len(script.calls) == 1
    for n in range(ORACLE_EVERY + 1, 4 * ORACLE_EVERY + 2):
        role.after(None, SimpleNamespace(record_id=f"o-r{n}"), outcome)
    assert len(script.calls) == ORACLE_CALLS_PER_RUN
    quiet = Script({"oracle_inventor": _reply([_rule("wrap_sub", _WRAP)])})
    off = _role(tmp_path / "off", quiet, oracles=("cross_dbms",))
    off.after(None, record, outcome)
    assert quiet.calls == []
    assert off.rules() == ()
    assert off.report()["calls"] == 0


def test_static_refusals_use_the_gate_reasons(tmp_path: Path) -> None:
    rules = [
        "nope",
        _rule("drop_t", "DELETE FROM t WHERE EXISTS ({q})", argument="writes"),
        _rule("empty_arg", _WRAP, argument=""),
        _rule("extra_rule", _WRAP),
    ]
    role = _role(tmp_path, Script({"oracle_inventor": _reply(rules)}))
    role.after(None, None, None)
    proposals = _proposals(role)
    assert [row["reason"] for row in proposals] == ["name", "template", "argument", "over_max"]
    assert proposals[0]["rule_id"] is None and proposals[0]["status"] == "rejected"
    assert proposals[1]["rule_id"] == "llm:drop_t"
    assert proposals[2]["acceptance"] is None
    assert all(row["acceptance"] is None for row in proposals)
    assert role.step()["proposed"] == [
        [None, "rejected", "name"],
        ["llm:drop_t", "rejected", "template"],
        ["llm:empty_arg", "rejected", "argument"],
        ["llm:extra_rule", "rejected", "over_max"],
    ]
    assert role.step() == {"proposed": []}
    report = role.report()
    assert report["calls"] == 1 and report["proposed"] == 4 and report["accepted"] == []
    assert report["rejected"] == {"name": 1, "template": 1, "argument": 1, "over_max": 1}
    assert role.rules() == ()
    assert not role.library_path.is_file()
    calls = [row for row in _lines(role._book_path) if row.get("type") == "call"]
    assert len(calls) == 1 and calls[0]["status"] == "ok" and calls[0]["reason"] is None
    assert isinstance(calls[0]["key"], str) and calls[0]["key"]


def test_a_failed_gateway_call_accepts_nothing(tmp_path: Path) -> None:
    role = _role(tmp_path, Script({"oracle_inventor": "not json"}))
    role.after(None, None, None)
    rows = _lines(role._book_path)
    assert [row["type"] for row in rows] == ["call"]
    assert rows[0]["status"] == "rejected" and rows[0]["reason"] == "no_json"
    assert role.rules() == () and role.report()["proposed"] == 0
    assert not role.library_path.is_file()
    assert role.manifest() == {"engines": list(ORACLE_ACCEPT_ENGINES), "library": "rewrites.json"}
    role.manifest()["engines"].append("nope")
    assert role.manifest()["engines"] == list(ORACLE_ACCEPT_ENGINES)


def test_one_row_agreements_do_not_count_and_a_short_scan_is_too_few() -> None:
    one_row = accept_template("query_wrap", _WRAP, seeds=_seeds(1, where="a = 1"))
    assert one_row["accepted"] is False and one_row["reason"] == "too_few_instances"
    assert one_row["instances"] == [] and one_row["scanned"] == 1
    assert one_row["engines"] == list(ORACLE_ACCEPT_ENGINES)
    short = accept_template("query_wrap", _WRAP, seeds=_seeds(1))
    assert short["reason"] == "too_few_instances" and len(short["instances"]) == 1
    assert len(short["instances"][0]["agree"]) >= ORACLE_ACCEPT_MIN_ENGINES
    assert "disagree" not in short["instances"][0]
    capped = accept_template("query_wrap", _WRAP, seeds=_seeds(5), scan_max=2)
    assert capped["reason"] == "too_few_instances" and capped["scanned"] == 2
    assert len(capped["instances"]) == 2
    unread = accept_template(
        "query_wrap",
        _WRAP,
        seeds=[{"setup_sqls": [], "query": "DELETE FROM t"}],
    )
    assert unread["instances"] == [] and unread["scanned"] == 1 and unread["reason"] == "too_few_instances"


def test_wrap_is_accepted_and_a_duplicate_is_refused(tmp_path: Path) -> None:
    first = _reply([
        _rule("wrap_sub", _WRAP, argument="a derived table returns the same rows"),
        _rule("alias_wrap", _WRAP, argument="same template"),
        _rule("wrap_sub", "WITH llm_cte AS ({q}) SELECT * FROM llm_cte", argument="a cte keeps the rows"),
    ])
    second = _reply([_rule("wrap_sub", _WRAP)])
    script = Script({"oracle_inventor": [first, second]})
    role = _role(tmp_path, script, seeds=_seeds(5))
    role.after(None, SimpleNamespace(record_id="o-r1"), None)
    assert role.rules() == ("llm:wrap_sub",)
    proposals = _proposals(role)
    assert [row["status"] for row in proposals] == ["accepted", "rejected", "rejected"]
    assert [row["reason"] for row in proposals] == [None, "duplicate", "duplicate"]
    good = proposals[0]
    assert good["rule_id"] == "llm:wrap_sub"
    assert good["prediction"]["rule"] == "wrap_sub"
    instances = good["acceptance"]["instances"]
    assert good["acceptance"]["accepted"] is True and good["acceptance"]["reason"] is None
    assert len(instances) == ORACLE_ACCEPT_INSTANCES
    assert all(
        len(item["agree"]) >= ORACLE_ACCEPT_MIN_ENGINES and "disagree" not in item and len(item["query_sha256"]) == 64
        for item in instances
    )
    library = load_library(role.library_path)
    assert list(library) == ["llm:wrap_sub"]
    assert library["llm:wrap_sub"]["kind"] == "query_wrap"
    assert library["llm:wrap_sub"]["template"] == _WRAP
    assert library["llm:wrap_sub"]["argument"] == "a derived table returns the same rows"
    assert library["llm:wrap_sub"]["proposer"] == "oracle_inventor"
    assert not (role.library_path.parent / ".rewrites.json.tmp").exists()
    for _ in range(ORACLE_EVERY - 1):
        role.after(None, None, None)
    assert len(script.calls) == 1
    role.after(None, None, None)
    assert len(script.calls) == 2
    assert "llm:wrap_sub" in script.calls[1]["prompt"]
    assert "o-r1" not in script.calls[1]["prompt"]
    assert _proposals(role)[-1]["reason"] == "duplicate"
    assert role.rules() == ("llm:wrap_sub",)


def test_limit_is_refused_because_an_engine_disagrees(tmp_path: Path) -> None:
    role = _role(tmp_path, Script({"oracle_inventor": _reply([_rule("first_row", _LIMIT, argument="drops rows")])}), seeds=_seeds(1))
    role.after(None, None, None)
    proposal = _proposals(role)[-1]
    assert proposal["status"] == "rejected" and proposal["reason"] == "disagree"
    last = proposal["acceptance"]["instances"][-1]
    assert last["disagree"]
    assert role.rules() == () and not role.library_path.is_file()
    direct = accept_template("query_wrap", _LIMIT, seeds=_seeds(1))
    assert direct["accepted"] is False and direct["reason"] == "disagree"
    assert direct["instances"][-1]["disagree"]


def test_a_role_records_too_few_instances(tmp_path: Path) -> None:
    role = _role(tmp_path, Script({"oracle_inventor": _reply([_rule("wrap_sub", _WRAP)])}), seeds=_seeds(1))
    role.after(None, None, None)
    proposal = _proposals(role)[-1]
    assert proposal["reason"] == "too_few_instances"
    assert len(proposal["acceptance"]["instances"]) == 1
    assert role.rules() == () and not role.library_path.is_file()


def test_a_frozen_rule_name_is_library_refused(tmp_path: Path) -> None:
    role = _role(
        tmp_path,
        Script({"oracle_inventor": _reply([_rule("double_negation", _WRAP, argument="same rows")])}),
        seeds=_seeds(5),
    )
    role.after(None, None, None)
    proposal = _proposals(role)[-1]
    assert proposal["status"] == "rejected" and proposal["reason"] == "library_refused"
    assert proposal["acceptance"]["accepted"] is True
    assert role.rules() == ()
    assert role.report()["rejected"]["library_refused"] == 1
    assert not role.library_path.is_file()
    assert load_library(role.library_path) == {}


def test_predicate_wrap_is_accepted_on_real_engines(tmp_path: Path) -> None:
    role = _role(
        tmp_path,
        Script({"oracle_inventor": _reply([_rule("is_true", _IS_TRUE, kind="predicate_wrap", argument="WHERE keeps only TRUE")])}),
        seeds=_seeds(5, where="a > 1"),
    )
    role.after(None, None, None)
    assert role.rules() == ("llm:is_true",)
    loaded = load_library(role.library_path)
    assert loaded["llm:is_true"]["kind"] == "predicate_wrap"
    assert loaded["llm:is_true"]["template"] == _IS_TRUE


def test_rewrite_rules_match_and_the_harness_passes_the_library(tmp_path, monkeypatch) -> None:
    script = Script({"oracle_inventor": _reply([_rule("wrap_sub", _WRAP, argument="same rows")])})
    made = build_roles(
        {
            "roles": ["oracle_inventor"],
            "cache": str(tmp_path / "cache"),
            "max_calls": 4,
            "network": False,
            "transport": script,
        },
        run_dir=tmp_path / "run",
        extract=lambda case: None,
        registry=None,
        engines=("duckdb",),
        seed=0,
        oracles=("equivalent_query",),
    )
    try:
        role = made.plugins["oracle_inventor"]
        assert made.rewrite_rules() == role.rules() == ()
        role.seeds = _seeds(5)
        role.after(None, None, None)
        assert made.rewrite_rules() == role.rules() == ("llm:wrap_sub",)
        monkeypatch.setenv("SURPRISE_REWRITE_LIBRARY", str(role.library_path))
        case = SqlCase(
            engine="duckdb",
            setup=(
                "CREATE TABLE lib_t(a INTEGER, b INTEGER)",
                "INSERT INTO lib_t VALUES (1, 10), (2, 20), (3, 30), (NULL, 40)",
            ),
            query="SELECT a, b FROM lib_t WHERE a > 1",
            predicate=None,
        )
        label = certify(case, "equivalent_query", rewrite_rule="llm:wrap_sub")
        assert label.y == "pass" and label.detail.get("layer") == "library"
    finally:
        made.close()
