"""Conjecturer, conjecture book, and source selection. No engine execution."""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from surprise.features.phi import make_phi
from surprise.gates import s09_cases as C
from surprise.harness.contracts import IdentityEvidence, Label, SqlCase
from surprise.roles.constants import (
    CONJECTURER_MAX_PREDICTIONS,
    CONJECTURER_MAX_TOKENS,
    CONJECTURER_TIER,
    TIERS,
)
from surprise.roles.conjecturer import (
    Conjecture,
    ConjectureBook,
    Conjecturer,
    conjecturer_prompt,
    select_sources,
)
from surprise.roles.gateway import Completion, Gateway
from surprise.roles.source import Hit, Snippet, SourceError, open_sources
from surprise.roles.sources_map import DATAFUSION_SOURCE_RULES, DUCKDB_OPTIMIZER_FILES
from surprise.theory.contracts import Spec
from surprise.theory.workbench import Workbench

LAYERS = {"ast": "ok", "plan": "ok", "data": "ok"}
RECORD_ID = "REC-UNIQUE-909"


class Script:
    def __init__(self, replies: Any) -> None:
        self.replies = replies if callable(replies) else list(replies)
        self.calls: list[dict[str, Any]] = []

    def complete(self, *, model: str, prompt: str, temperature: float, max_tokens: int, role: str) -> Any:
        self.calls.append(
            {"model": model, "prompt": prompt, "temperature": temperature, "max_tokens": max_tokens, "role": role}
        )
        reply = self.replies(prompt) if callable(self.replies) else self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return Completion(text=text, input_tokens=1, output_tokens=1)


class FakeReader:
    def __init__(self, files: dict[str, list[str]]) -> None:
        self.files = files

    def exists(self, path: str) -> bool:
        return path in self.files

    def read(self, path: str, start: int = 1, end: int | None = None) -> Snippet:
        if path not in self.files:
            raise SourceError(path)
        lines = self.files[path]
        last = len(lines)
        actual = last if end is None or end > last else end
        if start < 1 or actual < start:
            raise SourceError("range")
        return Snippet(path=path, start=start, end=actual, text="\n".join(lines[start - 1 : actual]))

    def grep(self, pattern: str, *, under: str = "", max_hits: int = 50) -> tuple[Hit, ...]:
        compiled = re.compile(pattern)
        prefix = under.rstrip("/")
        hits: list[Hit] = []
        for path in sorted(self.files):
            if prefix and path != prefix and not path.startswith(prefix + "/"):
                continue
            for number, line in enumerate(self.files[path], start=1):
                if compiled.search(line):
                    hits.append(Hit(path=path, line=number, text=line))
                    if len(hits) >= max_hits:
                        return tuple(hits)
        return tuple(hits)


def lines(marks: dict[int, str], length: int) -> list[str]:
    body = [f"line {number}" for number in range(1, length + 1)]
    for number, text in marks.items():
        body[number - 1] = text
    return body


def fail_label(oracle: str = "cross_dbms", *, minimized: dict | None = None) -> Label:
    cve: dict[str, Any] = {
        "profile": {
            "status": "ran",
            "fix_kind": "non_optimizer",
            "fix_set": [],
            "plan_diff": ["HashJoin"],
            "version_ladder": "longstanding",
            "witness_switches": ["switch-a"],
        }
    }
    if minimized is not None:
        cve["minimize"] = minimized
    return Label(
        y="fail",
        oracle=oracle,
        fail_kind="wrong_result",
        identity=IdentityEvidence(switches=("switch-a",), error_class="mismatch", behavior={"missing": 1}),
        cve=cve,
    )


def family(tmp: Path, features: tuple[str, ...], *, engine: str = "datafusion", oracle: str = "cross_dbms",
           record_id: str = RECORD_ID, minimized: dict | None = None) -> dict[str, Any]:
    wb = Workbench.create(tmp / "theory")
    phi = make_phi(engine, features, LAYERS)
    label = fail_label(oracle, minimized=minimized)
    case = SqlCase(engine=engine, setup=("CREATE TABLE t(v INTEGER)",), query="SELECT v FROM t EXCEPT ALL SELECT v FROM u")
    outcome = wb.observe(phi, label, record_id)
    record = SimpleNamespace(record_id=record_id, phi=phi.to_dict(), case=case, label=label)
    return {"wb": wb, "phi": phi, "label": label, "record": record, "outcome": outcome}


def agent(tmp: Path, script: Any, *, max_calls: int = 20, sources: Any | None = None) -> tuple[Conjecturer, ConjectureBook]:
    book = ConjectureBook(tmp / "conjectures.jsonl")
    made = Conjecturer(
        gateway=Gateway(cache_dir=tmp / "cache", ledger_path=tmp / "calls.jsonl", max_calls=max_calls, transport=script),
        extract=lambda case: case,
        book=book,
        sources={} if sources is None else sources,
        seed=0,
    )
    return made, book


def good_reply(trigger: list[str] | None = None, predictions: list[dict] | None = None, mechanism: str | None = "the join drops duplicates") -> dict[str, Any]:
    body: dict[str, Any] = {
        "trigger": ["ast:stmt:select", "ast:set_op:except_all"] if trigger is None else trigger,
        "prediction": [
            {"required": ["ast:set_op:intersect_all"], "forbidden": [], "data_properties": [], "expect": "fail", "why": "same lowering"},
            {"required": ["ast:stmt:select"], "forbidden": ["ast:set_op:except_all"], "data_properties": [], "expect": "pass", "why": "no set operation"},
        ] if predictions is None else predictions,
    }
    if mechanism is not None:
        body["mechanism"] = mechanism
    return body


def test_book_registers_settles_replays_and_refuses_unknown_lines(tmp_path: Path) -> None:
    memory = ConjectureBook()
    assert memory.path is None and memory.next_id() == "c1" and memory.summary()["conjectures"] == 0
    spec = Spec(engine="datafusion", oracle="cross_dbms", required=("ast:stmt:select",)).to_dict()
    other = Spec(engine="datafusion", oracle="cross_dbms", required=("ast:set_op:except_all",)).to_dict()
    registered = Conjecture(
        conjecture_id=memory.next_id(), record_id="r1", hypothesis_id="h1", engine="datafusion", oracle="cross_dbms",
        status="registered", reason=None, mechanism="caf\u00e9", trigger=("ast:stmt:select",),
        predictions=({"spec": spec, "expect": "fail", "why": "w"}, {"spec": other, "expect": "pass", "why": "z"}),
        dropped=(), edit_id=None, accepted=None, edit_reason=None, key="k", sources=(),
    )
    memory.add(registered)
    refused = Conjecture(
        conjecture_id=memory.next_id(), record_id="r2", hypothesis_id="h1", engine="datafusion", oracle="cross_dbms",
        status="rejected", reason="mechanism", mechanism=None, trigger=(), predictions=(), dropped=(),
        edit_id=None, accepted=None, edit_reason=None, key=None, sources=(),
    )
    memory.add(refused)
    assert memory.next_id() == "c3"
    assert [(item.index, item.state) for item in memory.pending()] == [(0, "open"), (1, "open")]
    assert memory.summary() == {"conjectures": 1, "rejected": 1, "predictions": 2, "open": 2, "kept": 0, "broken": 0}
    hit = make_phi("datafusion", ("ast:stmt:select",), LAYERS)
    label = Label(y="fail", oracle="cross_dbms", fail_kind="wrong_result")
    settled = memory.observe(hit, label, "rec-a")
    assert [(item.index, item.state, item.record_id) for item in settled] == [(0, "kept", "rec-a")]
    assert memory.observe(hit, Label(y="invalid", oracle="cross_dbms", invalid_reason="query_error"), "rec-b") == ()
    assert memory.observe(hit, Label(y="fail", oracle="tlp", fail_kind="wrong_result"), "rec-c") == ()
    again = memory.observe(hit, Label(y="pass", oracle="cross_dbms"), "rec-d")
    assert again == () and memory.pending(state=None)[0].state == "kept" and memory.pending(state=None)[0].record_id == "rec-a"
    broken = memory.observe(make_phi("datafusion", ("ast:stmt:select", "ast:set_op:except_all"), LAYERS), Label(y="fail", oracle="cross_dbms", fail_kind="wrong_result"), "rec-e")
    assert [(item.index, item.state) for item in broken] == [(1, "broken")]
    path = tmp_path / "book" / "conjectures.jsonl"
    stored = ConjectureBook(path)
    stored.add(registered)
    stored.observe(hit, label, "rec-a")
    text = path.read_text(encoding="utf-8")
    assert "caf\u00e9" not in text and "\\u00e9" in text
    assert text.splitlines()[0].startswith('{"type": "conjecture"')
    assert '"type": "settle"' in text
    reopened = ConjectureBook(path)
    assert reopened.summary() == stored.summary()
    assert [item.state for item in reopened.pending(state=None)] == ["kept", "open"]
    assert reopened.conjectures()[0]["mechanism"] == "caf\u00e9"
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"type": "nope"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="unknown"):
        ConjectureBook(bad)
    missing = tmp_path / "missing.jsonl"
    missing.write_text('{"type": "settle", "conjecture_id": "c1", "index": 0, "state": "kept", "record_id": "x"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="unknown prediction"):
        ConjectureBook(missing)


def test_source_selection_merges_caps_and_skips_unreadable() -> None:
    path = "datafusion/expr/src/logical_plan/builder.rs"
    far = lines(
        {
            50: "pub fn sort(",
            170: "pub fn join(",
            290: "pub fn window(",
            410: "fn intersect_or_except",
            530: "pub fn exists(",
        },
        600,
    )
    reader = FakeReader({path: far})
    phi = SimpleNamespace(
        features=(
            "ast:clause:order_by",
            "ast:join:inner",
            "ast:window_fn:aggregate",
            "ast:set_op:except_all",
            "ast:subquery:exists",
        )
    )
    hypothesis = SimpleNamespace(interventions=())
    picked = select_sources("datafusion", hypothesis, phi, {"datafusion": reader})
    assert picked == select_sources("datafusion", hypothesis, phi, {"datafusion": reader})
    assert len({item.path for item in picked}) == 1
    assert sum(item.end - item.start + 1 for item in picked) == 400
    assert picked[-1].start == 485 and picked[-1].end == 520
    close = lines({10: "pub fn sort(", 102: "pub fn window("}, 220)
    merged = select_sources(
        "datafusion",
        hypothesis,
        SimpleNamespace(features=("ast:clause:order_by", "ast:window_fn:aggregate")),
        {"datafusion": FakeReader({path: close})},
    )
    assert len(merged) == 1 and merged[0].start == 1 and merged[0].end == 147
    apart = lines({10: "pub fn sort(", 111: "pub fn window("}, 220)
    separate = select_sources(
        "datafusion",
        hypothesis,
        SimpleNamespace(features=("ast:clause:order_by", "ast:window_fn:aggregate")),
        {"datafusion": FakeReader({path: apart})},
    )
    assert [(item.start, item.end) for item in separate] == [(1, 55), (66, 156)]
    names = (
        "expression_rewriter",
        "filter_pullup",
        "filter_pushdown",
        "empty_result_pullup",
        "cte_filter_pusher",
    )
    files = {DUCKDB_OPTIMIZER_FILES[name]: [f"row {i}" for i in range(1, 101)] for name in names}
    duck = select_sources("duckdb", SimpleNamespace(interventions=names), None, {"duckdb": FakeReader(files)})
    assert len(duck) == 4
    assert [item.path for item in duck] == [DUCKDB_OPTIMIZER_FILES[name] for name in names[:4]]
    assert sum(item.end - item.start + 1 for item in duck) == 400
    assert select_sources("missing", hypothesis, phi, {}) == ()
    assert select_sources("duckdb", SimpleNamespace(interventions=("extension",)), None, {"duckdb": FakeReader({})}) == ()

    class Boom(FakeReader):
        def read(self, path: str, start: int = 1, end: int | None = None) -> Snippet:
            raise SourceError("unreadable")

    assert select_sources("datafusion", hypothesis, SimpleNamespace(features=("ast:set_op:except_all",)), {"datafusion": Boom({path: far})}) == ()
    assert DATAFUSION_SOURCE_RULES[0][0] == "ast:set_op:"


def test_real_checkouts_match_the_optimizer_map_and_the_set_operation() -> None:
    readers = open_sources()
    missing = [path for path in DUCKDB_OPTIMIZER_FILES.values() if not readers["duckdb"].exists(path)]
    assert missing == []
    for name, path in DUCKDB_OPTIMIZER_FILES.items():
        picked = select_sources("duckdb", SimpleNamespace(interventions=(name,)), None, readers)
        assert any(item.path == path for item in picked), name
    phi = make_phi("datafusion", ("ast:stmt:select", "ast:set_op:except_all", "data:setop:left_has_dups"), LAYERS)
    picked = select_sources("datafusion", SimpleNamespace(interventions=()), phi, readers)
    assert any(item.path == C.DFA_SOURCE_PATH and C.DFA_SOURCE_MARK in item.text for item in picked)
    assert "h1" not in "\n".join(item.text for item in picked).split()
    empty = select_sources("duckdb", SimpleNamespace(interventions=()), phi, readers)
    assert all(item.path != C.DUCKDB_SOURCE_PATH for item in empty)


def test_no_family_and_a_missing_hypothesis_do_not_call(tmp_path: Path) -> None:
    opened = family(tmp_path / "fam", ("ast:stmt:select", "ast:set_op:except_all", "data:setop:left_has_dups"))
    script = Script([good_reply()])
    made, book = agent(tmp_path / "none", script)
    quiet = SimpleNamespace(observation=SimpleNamespace(opened=None))
    assert made.after(opened["wb"], opened["record"], quiet) is None and script.calls == []
    opened["wb"].theory.remove(opened["outcome"].observation.opened)
    missing = SimpleNamespace(observation=SimpleNamespace(opened="no-such-hypothesis"))
    assert made.after(opened["wb"], opened["record"], missing) is None and script.calls == []
    assert book.conjectures() == ()


def test_registered_conjecture_proposes_and_the_prompt_has_no_ids(tmp_path: Path) -> None:
    opened = family(
        tmp_path / "fam",
        ("ast:stmt:select", "ast:set_op:except_all", "data:setop:left_has_dups"),
        minimized={
            "status": "ran",
            "reproduced": True,
            "case": {"setup": ["CREATE TABLE m(v INTEGER)"], "query": "SELECT minimized_marker FROM m"},
        },
    )
    path = "datafusion/expr/src/logical_plan/builder.rs"
    reader = FakeReader({path: lines({20: "fn intersect_or_except"}, 40)})
    script = Script([good_reply()])
    made, book = agent(tmp_path / "run", script, sources={"datafusion": reader})
    before = len(opened["wb"].edits())
    hypothesis = opened["wb"].theory.get(opened["outcome"].observation.opened)
    conjecture = made.after(opened["wb"], opened["record"], opened["outcome"])
    assert conjecture is not None and conjecture.status == "registered" and conjecture.reason is None
    assert conjecture.conjecture_id == "c1" and conjecture.hypothesis_id == opened["outcome"].observation.opened
    assert conjecture.record_id == RECORD_ID
    assert tuple(conjecture.trigger) == ("ast:set_op:except_all", "ast:stmt:select")
    assert conjecture.predictions[0]["spec"]["required"] == ["ast:set_op:intersect_all"]
    assert conjecture.predictions[1]["spec"]["forbidden"] == ["ast:set_op:except_all"]
    assert conjecture.predictions[0]["spec"]["data_properties"] == []
    assert conjecture.edit_id is not None and conjecture.accepted == (opened["wb"].edits()[-1].decision == "accepted")
    assert len(opened["wb"].edits()) == before + 1
    assert opened["wb"].edits()[-1].proposer == "conjecturer"
    assert [item.expect for item in book.pending()] == ["fail", "pass"]
    prompt = script.calls[0]["prompt"]
    assert script.calls[0]["model"] == TIERS[CONJECTURER_TIER]
    assert script.calls[0]["max_tokens"] == CONJECTURER_MAX_TOKENS
    assert RECORD_ID not in prompt
    assert opened["outcome"].observation.opened not in prompt.split()
    assert "EXCEPT ALL" in prompt.upper()
    assert "SELECT minimized_marker FROM m" in prompt
    assert f"--- datafusion:{path} lines " in prompt and "fn intersect_or_except" in prompt
    assert str(CONJECTURER_MAX_PREDICTIONS) in prompt
    assert "data_properties" in prompt
    hidden = family(
        tmp_path / "hidden",
        ("ast:stmt:select",),
        minimized={"status": "ran", "reproduced": False, "case": {"setup": [], "query": "SELECT minimized_marker FROM m"}},
    )
    quiet_script = Script([good_reply(trigger=["ast:stmt:select"], predictions=[{
        "required": ["ast:stmt:select"], "forbidden": [], "data_properties": [], "expect": "fail", "why": "x",
    }])])
    quiet_agent, _book = agent(tmp_path / "hidden-run", quiet_script)
    quiet_agent.after(hidden["wb"], hidden["record"], hidden["outcome"])
    assert "minimized_marker" not in quiet_script.calls[0]["prompt"]
    direct = conjecturer_prompt(
        engine="datafusion", oracle="cross_dbms", label=opened["label"], case=opened["record"].case,
        minimized=None, phi=opened["phi"], hypothesis=hypothesis, snippets=(),
    )
    assert direct == conjecturer_prompt(
        engine="datafusion", oracle="cross_dbms", label=opened["label"], case=opened["record"].case,
        minimized=None, phi=opened["record"].phi, hypothesis=hypothesis, snippets=(),
    )


def test_owner_is_preferred_and_a_key_error_falls_back(tmp_path: Path) -> None:
    opened = family(tmp_path / "fam", ("ast:stmt:select", "ast:set_op:except_all"))
    hypothesis_id = opened["outcome"].observation.opened
    script = Script([good_reply(trigger=["ast:stmt:select", "ast:set_op:except_all"])])
    made, _book = agent(tmp_path / "run", script)
    opened["wb"].owner_of = lambda record_id: hypothesis_id
    outcome = SimpleNamespace(observation=SimpleNamespace(opened="not-the-owner"))
    conjecture = made.after(opened["wb"], opened["record"], outcome)
    assert conjecture is not None and conjecture.hypothesis_id == hypothesis_id
    script2 = Script([good_reply(trigger=["ast:stmt:select", "ast:set_op:except_all"])])
    made2, _book2 = agent(tmp_path / "fall", script2)
    opened["wb"].owner_of = lambda record_id: (_ for _ in ()).throw(KeyError(record_id))
    fallback = SimpleNamespace(observation=SimpleNamespace(opened=hypothesis_id))
    conjecture = made2.after(opened["wb"], opened["record"], fallback)
    assert conjecture is not None and conjecture.hypothesis_id == hypothesis_id


def test_refusals_drops_empty_trigger_and_proposal_errors(tmp_path: Path) -> None:
    features = ("ast:stmt:select", "ast:set_op:except_all", "data:setop:left_has_dups")
    cases = [
        ("nomech", good_reply(mechanism=None), "mechanism"),
        ("badtrig", good_reply(trigger=["ast:bogus"]), "unknown_id"),
        ("empty", good_reply(trigger=["ast", "data"]), "empty_trigger"),
        ("notlist", {"mechanism": "because", "trigger": ["ast:stmt:select"], "prediction": {"expect": "fail"}}, "prediction"),
        ("allbad", good_reply(predictions=[
            {"required": ["ast:bogus"], "forbidden": [], "data_properties": [], "expect": "fail", "why": "x"},
            {"required": ["ast:stmt:select"], "forbidden": [], "data_properties": [], "expect": "maybe", "why": "y"},
        ]), "no_valid_prediction"),
    ]
    for name, reply, reason in cases:
        opened = family(tmp_path / name, features)
        script = Script([reply])
        made, book = agent(tmp_path / f"{name}-run", script)
        before = len(opened["wb"].edits())
        conjecture = made.after(opened["wb"], opened["record"], opened["outcome"])
        assert conjecture is not None and conjecture.status == "rejected" and conjecture.reason == reason
        assert conjecture.trigger == () and conjecture.predictions == ()
        assert book.pending() == () and book.summary()["conjectures"] == 0
        assert len(opened["wb"].edits()) == before
        assert conjecture.conjecture_id == "c1"
    opened = family(tmp_path / "drop", features)
    mixed = [
        {"required": ["not-an-id"], "forbidden": [], "data_properties": [], "expect": "fail", "why": "x"},
        {"required": ["ast:stmt:select"], "forbidden": [], "data_properties": [], "expect": "fail", "why": "keep"},
        {"required": "ast:stmt:select", "forbidden": [], "data_properties": [], "expect": "pass", "why": "y"},
        {"required": ["ast:stmt:select"], "forbidden": [], "data_properties": ["ast:stmt:select"], "expect": "pass", "why": "z"},
        {"required": [], "forbidden": ["ast:stmt:select"], "data_properties": [], "expect": "pass", "why": "e"},
        {"required": ["ast:stmt:select"], "forbidden": [], "data_properties": [], "oracle": "nope", "expect": "fail", "why": "o"},
        {"required": ["ast:stmt:select"], "forbidden": [], "data_properties": [], "expect": "pass", "why": "second"},
    ]
    script = Script([good_reply(predictions=mixed)])
    made, book = agent(tmp_path / "drop-run", script)
    conjecture = made.after(opened["wb"], opened["record"], opened["outcome"])
    assert conjecture is not None and conjecture.status == "registered" and len(conjecture.predictions) == 2
    assert [item["reason"] for item in conjecture.dropped] == [
        "unknown_id", "bad_lists", "data_layer", "empty_spec", "bad_oracle",
    ]
    assert book.pending()[0].expect == "fail" and book.pending()[1].expect == "pass"
    extra = [
        {"required": ["ast:stmt:select"], "forbidden": [], "data_properties": [], "expect": "fail", "why": str(i)}
        for i in range(CONJECTURER_MAX_PREDICTIONS + 1)
    ]
    opened = family(tmp_path / "max", features)
    made, _book = agent(tmp_path / "max-run", Script([good_reply(predictions=extra)]))
    conjecture = made.after(opened["wb"], opened["record"], opened["outcome"])
    assert conjecture is not None and len(conjecture.predictions) == CONJECTURER_MAX_PREDICTIONS
    assert conjecture.dropped == ({"index": CONJECTURER_MAX_PREDICTIONS, "reason": "over_max"},)
    opened = family(tmp_path / "cover", features)
    made, book = agent(tmp_path / "cover-run", Script([good_reply(trigger=["ast:set_op:intersect_all"])]))
    before = len(opened["wb"].edits())
    conjecture = made.after(opened["wb"], opened["record"], opened["outcome"])
    assert conjecture is not None and conjecture.status == "registered" and conjecture.edit_reason == "not_covering"
    assert conjecture.edit_id is None and len(opened["wb"].edits()) == before and len(book.pending()) == 2
    opened = family(tmp_path / "err", features)
    made, book = agent(tmp_path / "err-run", Script([good_reply()]))

    def boom(_proposal: Any) -> Any:
        raise ValueError("shape")

    opened["wb"].propose = boom
    conjecture = made.after(opened["wb"], opened["record"], opened["outcome"])
    assert conjecture is not None and conjecture.status == "registered" and conjecture.edit_reason == "proposal_error"
    assert len(book.pending()) == 2
    made, book = agent(tmp_path / "cap", Script([good_reply()]), max_calls=0)
    opened = family(tmp_path / "capfam", features)
    conjecture = made.after(opened["wb"], opened["record"], opened["outcome"])
    assert conjecture is not None and conjecture.status == "blocked" and book.pending() == ()
    made, book = agent(tmp_path / "miss", None)
    opened = family(tmp_path / "missfam", features)
    conjecture = made.after(opened["wb"], opened["record"], opened["outcome"])
    assert conjecture is not None and conjecture.status == "miss"
    made, book = agent(tmp_path / "boom", Script([RuntimeError("boom")]))
    opened = family(tmp_path / "boomfam", features)
    conjecture = made.after(opened["wb"], opened["record"], opened["outcome"])
    assert conjecture is not None and conjecture.status == "error" and conjecture.reason == "RuntimeError"


def test_prediction_lists_are_copied_in_reply_order() -> None:
    target = Spec(
        engine="datafusion", oracle="cross_dbms",
        required=("data:setop:left_has_dups", "ast:set_op:intersect_all"),
        forbidden=(), data_properties=(),
    ).to_dict()
    assert target["required"] == ["data:setop:left_has_dups", "ast:set_op:intersect_all"]
