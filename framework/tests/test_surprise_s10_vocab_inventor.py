"""Vocabulary inventor: trigger, holdout prompt, and deterministic acceptance."""

from __future__ import annotations

import json
import time
from pathlib import Path

from surprise.features.ast import extract_ast
from surprise.features.phi import make_phi
from surprise.features.registry import Registry, default_registry
from surprise.gates.s10 import fake_record, observed, synthetic_fail, synthetic_label
from surprise.harness.contracts import SqlCase
from surprise.gates.s10_cases import (
    VOCAB_BAD,
    VOCAB_ENGINE,
    VOCAB_GOOD,
    VOCAB_HELD,
    VOCAB_ORACLE,
    VOCAB_PARENT,
    VOCAB_PHI,
    VOCAB_RECORDS,
    VOCAB_SETUP,
    VOCAB_TRAIN,
)
from surprise.roles.base import RoleContext
from surprise.roles.conjecturer import ConjectureBook
from surprise.roles.constants import (
    VOCAB_MAX_TOKENS,
    VOCAB_SCAN_TIMEOUT_S,
    VOCAB_TEMPERATURE,
    VOCAB_TIER,
    TIERS,
)
from surprise.roles.gateway import Completion, Gateway
from surprise.roles.runtime import build_roles
from surprise.roles.vocab_inventor import VocabInventor, build, split_holdout, vocab_prompt
from surprise.theory.workbench import Workbench

LAYERS = {"ast": "ok", "plan": "ok", "data": "ok"}
_ROW_KEYS = {
    "type", "family", "hypothesis_id", "status", "reason", "detail",
    "feature_id", "pattern", "prediction_kept", "key",
}


class Script:
    """Per-role scripted transport, same pop rule as gates/s10.py."""

    def __init__(self, replies) -> None:
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


def _proposals(role: VocabInventor) -> list[dict]:
    return [row for row in _lines(role._book_path) if row.get("type") == "proposal"]


def _reply(pattern: str, *, feature_id: str = VOCAB_GOOD["id"], parent: str = VOCAB_PARENT,
           matches: list[str] | None = None, excludes: list[str] | None = None) -> dict:
    return {
        "feature": {
            "id": feature_id,
            "parent": parent,
            "description": "two different tables around EXCEPT ALL",
            "pattern": pattern,
        },
        "prediction": {
            "matches": ["P1"] if matches is None else matches,
            "excludes": ["C1"] if excludes is None else excludes,
            "why": "scripted",
        },
    }


def _role(tmp_path: Path, transport, *, max_calls: int = 10, registry=None) -> tuple[VocabInventor, Registry]:
    llm = tmp_path / "llm"
    llm.mkdir(parents=True, exist_ok=True)
    active = default_registry() if registry is None else registry
    gateway = Gateway(
        cache_dir=tmp_path / "cache",
        ledger_path=llm / "calls.jsonl",
        max_calls=max_calls,
        transport=transport,
    )
    ctx = RoleContext(
        gateway=gateway,
        book=ConjectureBook(llm / "conjectures.jsonl"),
        extract=lambda case: None,
        registry=active,
        readers={},
        engines=(VOCAB_ENGINE,),
        oracles=(VOCAB_ORACLE,),
        seed=0,
        run_dir=tmp_path,
        llm_dir=llm,
    )
    return build(ctx), active


def _calls(role: VocabInventor) -> int:
    stats = role._ctx.gateway.totals()["by_role"].get(role.name, {})
    return int(stats.get("calls", 0))


def _drive(tmp_path: Path, reply, records=VOCAB_RECORDS, *, engine: str = VOCAB_ENGINE, max_calls: int = 10):
    script = Script({"vocab_inventor": reply})
    role, registry = _role(tmp_path, script, max_calls=max_calls)
    wb = Workbench.create(tmp_path / "theory", registry)
    digest = registry.digest()
    calls_after: list[int] = []
    for seq, (record_id, y, query) in enumerate(records, start=1):
        case = SqlCase(engine=engine, setup=VOCAB_SETUP, query=query, predicate=None)
        label = synthetic_fail(VOCAB_ORACLE) if y == "fail" else synthetic_label("pass", VOCAB_ORACLE)
        phi = make_phi(engine, VOCAB_PHI, LAYERS, registry)
        prediction = wb.predict(phi, VOCAB_ORACLE)
        outcome = wb.observe(phi, label, record_id, prediction=prediction)
        version = wb.theory.version
        record = fake_record(record_id, seq, case, label, phi)
        role.observe(observed(wb, phi, record, outcome, prediction, index=seq))
        role.after(wb, record, outcome)
        assert wb.theory.version == version
        assert registry.digest() == digest
        calls_after.append(_calls(role))
    return role, script, wb, registry, calls_after


def test_split_holdout_keeps_the_tail() -> None:
    assert split_holdout([]) == ([], [])
    assert split_holdout([1]) == ([], [1])
    assert split_holdout([1, 2]) == ([1], [2])
    assert split_holdout([1, 2, 3]) == ([1, 2], [3])
    assert split_holdout([1, 2, 3, 4, 5]) == ([1, 2, 3], [4, 5])
    again = split_holdout([1, 2, 3])
    assert again == ([1, 2], [3])


def test_prompt_lists_s_training_statements_and_ast_classes_without_ids() -> None:
    registry = default_registry()

    class Hypothesis:
        specific = ("ast:set_op:except_all", "ast:stmt:select")
        hypothesis_id = "h9"

    text = vocab_prompt(
        hypothesis=Hypothesis(),
        train_positives=["SELECT v FROM vt EXCEPT ALL SELECT v FROM vu", "SELECT kept"],
        train_contradictions=["SELECT v FROM vt EXCEPT ALL SELECT v FROM vt"],
        registry=registry,
    )
    assert text == vocab_prompt(
        hypothesis=Hypothesis(),
        train_positives=["SELECT v FROM vt EXCEPT ALL SELECT v FROM vu", "SELECT kept"],
        train_contradictions=["SELECT v FROM vt EXCEPT ALL SELECT v FROM vt"],
        registry=default_registry(),
    )
    assert "P1: SELECT v FROM vt EXCEPT ALL SELECT v FROM vu" in text
    assert "P2: SELECT kept" in text
    assert "C1: SELECT v FROM vt EXCEPT ALL SELECT v FROM vt" in text
    assert "SELECT held out" not in text
    assert "h9" not in text
    assert "vocab-r1" not in text
    assert "s10-gate" not in text
    assert "datafusion|h9" not in text
    assert "re.search(pattern, statement, re.IGNORECASE)" in text
    assert "one JSON object" in text
    assert '"feature"' in text and '"prediction"' in text
    classes = [
        feature_id for feature_id in registry.ids()
        if registry.get(feature_id).kind == "class" and registry.get(feature_id).layer == "ast"
    ]
    positions = []
    for feature_id in classes:
        assert feature_id in text
        assert registry.get(feature_id).description in text
        positions.append(text.index(f"- {feature_id}\n"))
    assert positions == sorted(positions)
    assert "ast:set_op:except_all" in text
    assert "EXCEPT ALL." in text


def test_called_once_on_the_second_unexpected_pass_and_the_good_feature_lands(tmp_path: Path) -> None:
    role, script, wb, registry, calls_after = _drive(tmp_path, _reply(VOCAB_GOOD["pattern"]))
    assert role.name == "vocab_inventor"
    assert calls_after == [0, 0, 0, 0, 1]
    assert len(script.calls) == 1
    call = script.calls[0]
    assert call["model"] == TIERS[VOCAB_TIER]
    assert call["temperature"] == VOCAB_TEMPERATURE
    assert call["max_tokens"] == VOCAB_MAX_TOKENS
    assert call["role"] == "vocab_inventor"
    queries = {record_id: query for record_id, _y, query in VOCAB_RECORDS}
    prompt = call["prompt"]
    hypothesis = wb.theory.hypotheses[0]
    train_pos = [queries[record_id] for record_id in ("vocab-r1", "vocab-r3")]
    train_con = [queries["vocab-r2"]]
    assert prompt == vocab_prompt(
        hypothesis=hypothesis,
        train_positives=train_pos,
        train_contradictions=train_con,
        registry=registry,
    )
    assert all(queries[record_id] in prompt for record_id in VOCAB_TRAIN)
    assert not any(queries[record_id] in prompt for record_id in VOCAB_HELD)
    assert not any(record_id in prompt for record_id, _y, _query in VOCAB_RECORDS)
    assert hypothesis.hypothesis_id not in prompt
    assert wb.family_of(hypothesis.hypothesis_id) not in prompt
    assert "s10-gate" not in prompt
    rows = _proposals(role)
    assert len(rows) == 1
    row = rows[0]
    assert set(row) == _ROW_KEYS
    assert row["status"] == "accepted"
    assert row["reason"] is None
    assert row["feature_id"] == VOCAB_GOOD["id"]
    assert row["pattern"] == VOCAB_GOOD["pattern"]
    assert row["prediction_kept"] is False
    assert row["family"] == "datafusion|h1"
    assert row["hypothesis_id"] == "h1"
    assert isinstance(row["key"], str) and row["key"]
    loaded = Registry.load(role.vocabulary_path)
    definition = loaded.get(VOCAB_GOOD["id"])
    assert definition.accepted is True
    assert definition.parent == VOCAB_PARENT
    assert definition.layer == "ast"
    assert definition.source == "llm:vocab_inventor"
    assert definition.definition == {"kind": "regex", "pattern": VOCAB_GOOD["pattern"]}
    acceptance = definition.acceptance
    assert acceptance["family"] == "datafusion|h1"
    assert acceptance["hypothesis_id"] == "h1"
    assert acceptance["train"] == {"positives": 2, "contradictions": 1, "excluded": 1}
    assert acceptance["holdout"] == {"positives": 1, "matched": 1, "contradictions": 1, "excluded": 1}
    assert acceptance["prediction_kept"] is False
    assert 0.0 <= acceptance["corpus_share"] <= 0.5
    assert role.accepted() == (VOCAB_GOOD["id"],)
    assert role.manifest() == {"vocabulary": "vocabulary.json"}
    family = wb.family_of(hypothesis.hypothesis_id)
    assert role.step() == {"proposed": [[family, "accepted", None]]}
    assert role.step() == {"proposed": []}
    assert role.report() == {
        "proposals": 1,
        "accepted": [VOCAB_GOOD["id"]],
        "rejected": {},
    }
    hit, _status = extract_ast(queries["vocab-r1"], VOCAB_ENGINE, loaded)
    miss, _status = extract_ast(queries["vocab-r2"], VOCAB_ENGINE, loaded)
    assert VOCAB_GOOD["id"] in hit
    assert VOCAB_GOOD["id"] not in miss
    assert not registry.known(VOCAB_GOOD["id"])
    digest = registry.digest()
    _extra_pass(role, wb, registry, "vocab-r6", "SELECT v FROM vu EXCEPT ALL SELECT v FROM vu")
    assert _calls(role) == 1
    assert len(_proposals(role)) == 1
    assert registry.digest() == digest
    assert not registry.known(VOCAB_GOOD["id"])


def test_a_correct_prediction_is_recorded_and_still_not_required(tmp_path: Path) -> None:
    role, _script, _wb, registry, calls_after = _drive(
        tmp_path,
        _reply(VOCAB_GOOD["pattern"], matches=["P1", "P2"], excludes=["C1"]),
    )
    assert calls_after == [0, 0, 0, 0, 1]
    row = _proposals(role)[0]
    assert row["status"] == "accepted" and row["prediction_kept"] is True
    assert Registry.load(role.vocabulary_path).get(VOCAB_GOOD["id"]).acceptance["prediction_kept"] is True
    assert not registry.known(VOCAB_GOOD["id"])


def test_each_refusal_reason_writes_nothing(tmp_path: Path) -> None:
    cases = dict(VOCAB_BAD)
    cases["data_layer"] = (VOCAB_GOOD["pattern"], "definition")
    cases["broken"] = ("(", "pattern")
    cases["star"] = ("a*", "pattern")
    cases["known"] = (VOCAB_GOOD["pattern"], "definition")
    for tag, (pattern, reason) in cases.items():
        feature_id = VOCAB_GOOD["id"]
        parent = VOCAB_PARENT
        if tag == "data_layer":
            feature_id = "data:setop:two_tables"
            parent = "data:setop"
        elif tag == "known":
            feature_id = "ast:set_op:except_all"
        started = time.monotonic()
        role, script, _wb, registry, calls_after = _drive(
            tmp_path / tag,
            _reply(pattern, feature_id=feature_id, parent=parent),
        )
        assert calls_after == [0, 0, 0, 0, 1]
        assert len(script.calls) == 1
        rows = _proposals(role)
        assert len(rows) == 1
        assert rows[0]["status"] == "rejected"
        assert rows[0]["reason"] == reason
        assert set(rows[0]) == _ROW_KEYS
        assert role.accepted() == ()
        assert not role.vocabulary_path.is_file()
        assert role.report()["rejected"] == {reason: 1}
        assert role.step()["proposed"] == [[rows[0]["family"], "rejected", reason]]
        assert not registry.known(feature_id) or tag == "known"
        if tag == "catastrophic":
            assert rows[0]["detail"] == "timeout"
            assert time.monotonic() - started < VOCAB_SCAN_TIMEOUT_S + 60
        if tag == "everything":
            assert rows[0]["detail"] == "corpus_share"
        if tag == "empty":
            assert rows[0]["detail"] == "empty"
        if tag == "long":
            assert rows[0]["detail"] == "length"
        if tag == "no_exclusion":
            assert rows[0]["detail"] == "no_exclusion"
        if tag == "train_only":
            assert rows[0]["detail"] == "missed_positive"
        if tag == "data_layer":
            assert rows[0]["detail"] == "parent"


def test_gateway_failures_are_replies_and_consume_the_attempt(tmp_path: Path) -> None:
    role, script, wb, registry, calls_after = _drive(tmp_path / "bad", "not json")
    assert calls_after == [0, 0, 0, 0, 1]
    row = _proposals(role)[0]
    assert row["status"] == "rejected" and row["reason"] == "reply" and row["detail"] == "no_json"
    assert role.accepted() == ()
    assert not role.vocabulary_path.is_file()
    _extra_pass(role, wb, registry, "vocab-r6", "SELECT v FROM vu EXCEPT ALL SELECT v FROM vu")
    assert len(script.calls) == 1

    missed, _registry = _role(tmp_path / "miss", None)
    missed_wb = Workbench.create(tmp_path / "miss" / "theory", missed._ctx.registry)
    _feed(missed, missed_wb)
    row = _proposals(missed)[0]
    assert row["status"] == "miss" and row["reason"] == "reply" and row["detail"] == "miss"
    assert missed.report()["rejected"] == {"reply": 1}
    assert not missed.vocabulary_path.is_file()

    blocked_script = Script({"vocab_inventor": _reply(VOCAB_GOOD["pattern"])})
    blocked, blocked_registry = _role(tmp_path / "blocked", blocked_script, max_calls=0)
    blocked_wb = Workbench.create(tmp_path / "blocked" / "theory", blocked_registry)
    _feed(blocked, blocked_wb)
    row = _proposals(blocked)[0]
    assert row["status"] == "blocked" and row["reason"] == "reply" and row["detail"] == "cap"
    assert blocked_script.calls == []

    class Boom:
        def complete(self, **_kwargs):
            raise RuntimeError("down")

    errored, errored_registry = _role(tmp_path / "error", Boom())
    errored_wb = Workbench.create(tmp_path / "error" / "theory", errored_registry)
    _feed(errored, errored_wb)
    row = _proposals(errored)[0]
    assert row["status"] == "error" and row["reason"] == "reply" and row["detail"] == "RuntimeError"
    assert "down" not in json.dumps(row)


def test_two_families_accumulate_and_leave_the_run_registry_alone(tmp_path: Path) -> None:
    second_id = "ast:set_op:two_different_tables"
    script = Script({"vocab_inventor": [
        _reply(VOCAB_GOOD["pattern"]),
        _reply(VOCAB_GOOD["pattern"], feature_id=second_id),
    ]})
    role, registry = _role(tmp_path, script)
    digest = registry.digest()
    wb = Workbench.create(tmp_path / "theory", registry)
    _feed(role, wb)
    duck_records = (
        ("duck-r1", "fail", "SELECT v FROM dt EXCEPT ALL SELECT v FROM du"),
        ("duck-r2", "pass", "SELECT v FROM dt EXCEPT ALL SELECT v FROM dt"),
        ("duck-r3", "fail", "SELECT v FROM dw EXCEPT ALL SELECT v FROM du"),
        ("duck-r4", "fail", "SELECT v FROM dt EXCEPT ALL SELECT v FROM dw"),
        ("duck-r5", "pass", "SELECT v FROM dw EXCEPT ALL SELECT v FROM dw"),
    )
    _feed(role, wb, duck_records, engine="duckdb")
    assert len(script.calls) == 2
    first, second = script.calls
    duck_train = (
        "SELECT v FROM dt EXCEPT ALL SELECT v FROM du",
        "SELECT v FROM dw EXCEPT ALL SELECT v FROM du",
        "SELECT v FROM dt EXCEPT ALL SELECT v FROM dt",
    )
    duck_held = (
        "SELECT v FROM dt EXCEPT ALL SELECT v FROM dw",
        "SELECT v FROM dw EXCEPT ALL SELECT v FROM dw",
    )
    assert all(query in second["prompt"] for query in duck_train)
    assert not any(query in second["prompt"] for query in duck_held)
    assert not any(query in first["prompt"] for query in duck_train + duck_held)
    assert "h1" not in first["prompt"] and "h2" not in second["prompt"]
    assert "duck-r1" not in second["prompt"]
    assert "datafusion|h1" not in first["prompt"]
    assert "duckdb|h2" not in second["prompt"]
    assert role.accepted() == (VOCAB_GOOD["id"], second_id)
    loaded = Registry.load(role.vocabulary_path)
    assert loaded.get(VOCAB_GOOD["id"]).accepted is True
    assert loaded.get(second_id).accepted is True
    hit, _status = extract_ast(duck_records[0][2], "duckdb", loaded)
    assert second_id in hit and VOCAB_GOOD["id"] in hit
    same, _status = extract_ast(duck_records[1][2], "duckdb", loaded)
    assert second_id not in same
    assert registry.digest() == digest
    assert not registry.known(VOCAB_GOOD["id"])
    assert not registry.known(second_id)
    _extra_pass(role, wb, registry, "vocab-r6", "SELECT v FROM vu EXCEPT ALL SELECT v FROM vu")
    _extra_pass(role, wb, registry, "duck-r6", "SELECT v FROM du EXCEPT ALL SELECT v FROM du", engine="duckdb")
    assert len(script.calls) == 2
    assert role.report()["proposals"] == 2
    assert role.report()["accepted"] == [VOCAB_GOOD["id"], second_id]


def test_build_roles_returns_the_inventor(tmp_path: Path) -> None:
    script = Script({"vocab_inventor": _reply(VOCAB_GOOD["pattern"])})
    made = build_roles(
        {
            "roles": ["vocab_inventor"],
            "cache": str(tmp_path / "cache"),
            "max_calls": 4,
            "network": False,
            "transport": script,
        },
        run_dir=tmp_path / "run",
        extract=lambda case: None,
        registry=default_registry(),
        engines=(VOCAB_ENGINE,),
        seed=0,
        oracles=(VOCAB_ORACLE,),
    )
    try:
        role = made.plugins["vocab_inventor"]
        assert isinstance(role, VocabInventor)
        assert role.name == "vocab_inventor"
        assert role.manifest() == {"vocabulary": "vocabulary.json"}
        assert made.report()["vocab_inventor"]["proposals"] == 0
    finally:
        made.close()


def _feed(role, wb, records=VOCAB_RECORDS, *, engine: str = VOCAB_ENGINE) -> None:
    for seq, (record_id, y, query) in enumerate(records, start=1):
        case = SqlCase(engine=engine, setup=VOCAB_SETUP, query=query, predicate=None)
        label = synthetic_fail(VOCAB_ORACLE) if y == "fail" else synthetic_label("pass", VOCAB_ORACLE)
        phi = make_phi(engine, VOCAB_PHI, LAYERS, wb._registry)
        prediction = wb.predict(phi, VOCAB_ORACLE)
        outcome = wb.observe(phi, label, record_id, prediction=prediction)
        version = wb.theory.version
        record = fake_record(record_id, seq, case, label, phi)
        role.observe(observed(wb, phi, record, outcome, prediction, index=seq))
        role.after(wb, record, outcome)
        assert wb.theory.version == version


def _extra_pass(role, wb, registry, record_id: str, query: str, *, engine: str = VOCAB_ENGINE) -> None:
    case = SqlCase(engine=engine, setup=VOCAB_SETUP, query=query, predicate=None)
    label = synthetic_label("pass", VOCAB_ORACLE)
    phi = make_phi(engine, VOCAB_PHI, LAYERS, registry)
    prediction = wb.predict(phi, VOCAB_ORACLE)
    outcome = wb.observe(phi, label, record_id, prediction=prediction)
    assert outcome.observation.triage == "unexpected_pass"
    version = wb.theory.version
    record = fake_record(record_id, 6, case, label, phi)
    role.observe(observed(wb, phi, record, outcome, prediction, index=6))
    role.after(wb, record, outcome)
    assert wb.theory.version == version
