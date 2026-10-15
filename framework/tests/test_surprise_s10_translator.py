"""Migration translator: scripted transport, settlement, and the role wiring. No network."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from surprise.features.phi import make_phi
from surprise.features.registry import default_registry
from surprise.features.spec import check_spec
from surprise.harness.contracts import SqlCase
from surprise.hunter.operators import case_digest, oracle_options
from surprise.roles.base import RoleContext
from surprise.roles.conjecturer import Conjecture, ConjectureBook
from surprise.roles.constants import (
    TRANSLATOR_ATTEMPTS,
    TRANSLATOR_MAX_TOKENS,
    TRANSLATOR_PER_CHOICE,
    TRANSLATOR_TEMPERATURE,
    TRANSLATOR_TIER,
    TIERS,
)
from surprise.roles.gateway import Completion, Gateway
from surprise.roles.runtime import build_roles
from surprise.roles.sources_map import DUCKDB_OPTIMIZER_FILES
from surprise.roles.translator import (
    Translator,
    TranslatorSource,
    allowed_switches,
    build,
    translator_prompt,
)
from surprise.theory.contracts import Spec

LAYERS = {"ast": "ok", "plan": "ok", "data": "ok"}
_SOURCE_QUERY = "SELECT v FROM t EXCEPT ALL SELECT v FROM u"
_SOURCE_SETUP = "CREATE TABLE marked_src(v INT)"
_RECORD = "s09-dfa:1"
_FAMILY = "datafusion|h1"
_SEED = 424242

_TRANSLATION_KEYS = {
    "type",
    "translation_id",
    "hypothesis_id",
    "family",
    "source_engine",
    "target_engine",
    "oracle",
    "status",
    "case",
    "case_digest",
    "expect",
    "switches",
    "behavior",
    "tries",
    "keys",
    "parent",
}
_SETTLE_KEYS = {"type", "translation_id", "state", "identity", "record_id"}


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
        if callable(reply):
            reply = reply(prompt)
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return Completion(text=text, input_tokens=len(prompt) // 4, output_tokens=len(text) // 4)


class Boom:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, **kwargs: Any):
        self.calls += 1
        raise RuntimeError("network down")


class FixedExtract:
    def __init__(self, features: tuple[str, ...] = ("ast:stmt:select",)) -> None:
        self.features = features
        self.calls = 0

    def __call__(self, case: SqlCase):
        self.calls += 1
        return make_phi(case.engine, self.features, LAYERS)


class QueryExtract:
    """Adds EXCEPT ALL only when the statement writes it."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, case: SqlCase):
        self.calls += 1
        features = ["ast:stmt:select"]
        if "EXCEPT ALL" in case.query.upper():
            features.append("ast:set_op:except_all")
        return make_phi(case.engine, features, LAYERS)


def hyp(**overrides: Any) -> SimpleNamespace:
    data: dict[str, Any] = {
        "hypothesis_id": "h1",
        "engine": "datafusion",
        "oracle": "cross_dbms",
        "positives": (_RECORD,),
        "specific": ("ast:stmt:select",),
        "interventions": (),
        "plan_delta": (),
        "fail_kind": "wrong_result",
        "error_class": None,
        "behavior_shape": "missing_only",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


class Bench:
    def __init__(self, hypotheses: tuple, family: dict[str, str] | None = None) -> None:
        self.theory = SimpleNamespace(hypotheses=tuple(hypotheses))
        self._family = {} if family is None else family

    def family_of(self, hypothesis_id: str) -> str:
        return self._family.get(hypothesis_id, hypothesis_id)


class Theory:
    def __init__(self, hypotheses: tuple) -> None:
        self.hypotheses = tuple(hypotheses)
        self._by_id = {item.hypothesis_id: item for item in hypotheses}

    def get(self, hypothesis_id: str):
        if hypothesis_id not in self._by_id:
            raise KeyError(hypothesis_id)
        return self._by_id[hypothesis_id]


def reply(
    query: str = "SELECT v FROM t",
    *,
    expect: str = "pass",
    switches: list[str] | None = None,
    behavior: str | None = None,
    predicate: str | None = None,
    setup: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "setup": ["CREATE TABLE t(v INT)"] if setup is None else setup,
        "query": query,
        "predicate": predicate,
        "prediction": {
            "expect": expect,
            "switches": [] if switches is None else switches,
            "behavior": behavior,
            "why": "scripted",
        },
    }


def ctx_for(
    tmp: Path,
    transport: Any,
    *,
    engines: tuple[str, ...] = ("datafusion", "duckdb"),
    seed: int = _SEED,
    extract: Any = None,
    max_calls: int = 20,
    oracles: tuple[str, ...] = ("cross_dbms",),
) -> RoleContext:
    root = tmp / "run"
    llm = root / "llm"
    llm.mkdir(parents=True, exist_ok=True)
    gateway = Gateway(
        cache_dir=root / "cache",
        ledger_path=llm / "calls.jsonl",
        max_calls=max_calls,
        transport=transport,
    )
    return RoleContext(
        gateway=gateway,
        book=ConjectureBook(llm / "conjectures.jsonl"),
        extract=FixedExtract() if extract is None else extract,
        registry=default_registry(),
        readers={},
        engines=tuple(engines),
        oracles=tuple(oracles),
        seed=seed,
        run_dir=root,
        llm_dir=llm,
    )


@contextmanager
def opened(tmp: Path, transport: Any, **kwargs: Any):
    ctx = ctx_for(tmp, transport, **kwargs)
    role = build(ctx)
    try:
        yield role, ctx
    finally:
        role.close()


def remember(role: Translator, record_id: str, query: str, *, engine: str = "datafusion") -> SqlCase:
    case = SqlCase(engine=engine, setup=(_SOURCE_SETUP,), query=query, predicate=None)
    role.observe(
        SimpleNamespace(
            wb=None,
            record=SimpleNamespace(
                record_id=record_id,
                case=case,
                label=SimpleNamespace(y="fail", oracle="cross_dbms", cve={}, identity=None),
            ),
            prediction=None,
            outcome=None,
        )
    )
    return case


def book_text(role: Translator) -> str:
    path = role.ctx.llm_dir / "translations.jsonl"
    return path.read_text(encoding="utf-8")


def parsed_book(role: Translator) -> list[dict[str, Any]]:
    return [json.loads(line) for line in book_text(role).splitlines() if line.strip()]


_UNSET = object()


def label(
    y: str,
    oracle: str = "cross_dbms",
    *,
    cve: dict | None = None,
    behavior: dict | None = None,
    identity: Any = _UNSET,
) -> SimpleNamespace:
    if identity is _UNSET:
        identity = SimpleNamespace(behavior={} if behavior is None else behavior)
    return SimpleNamespace(
        y=y,
        oracle=oracle,
        cve={} if cve is None else cve,
        identity=identity,
    )


def settle(role: Translator, candidate: Any, seen: Any, *, record_id: str = "out-1", wb: Any = None) -> dict:
    role.observe(
        SimpleNamespace(
            wb=wb,
            record=SimpleNamespace(record_id=record_id, case=candidate.case, label=seen),
            prediction=SimpleNamespace(zone="unexplored", unit=""),
            outcome=SimpleNamespace(),
        )
    )
    return role.translations()[-1]


def choose(role: Translator, hypotheses, *, index: int = 1, round: int = 1, family: dict[str, str] | None = None):
    return role.sources()[0].candidates(Bench(tuple(hypotheses), family), index=index, round=round)


def translation_rows(role: Translator) -> list[dict[str, Any]]:
    return [row for row in role.translations() if row.get("type") == "translation"]


class RaisingBench:
    def __init__(self) -> None:
        self.theory = SimpleNamespace(hypotheses=(hyp(),))
        self.asked = False

    def family_of(self, hypothesis_id: str) -> str:
        self.asked = True
        raise AssertionError(hypothesis_id)


class ScanTheory:
    """``get`` misses; the hypothesis is visible only by scanning."""

    def __init__(self, hypotheses) -> None:
        self.hypotheses = tuple(hypotheses)

    def get(self, hypothesis_id: str):
        raise KeyError(hypothesis_id)


def add_conjecture(book: ConjectureBook, hypothesis_id: str, status: str, mechanism: str | None, number: int) -> None:
    book.add(
        Conjecture(
            conjecture_id=f"c{number}",
            record_id=f"CONJ-RECORD-{number}",
            hypothesis_id=hypothesis_id,
            engine="datafusion",
            oracle="cross_dbms",
            status=status,
            reason=None,
            mechanism=mechanism,
            trigger=(),
            predictions=(),
            dropped=(),
            edit_id=None,
            accepted=None,
            edit_reason=None,
            key=None,
            sources=(),
        )
    )


def test_allowed_switches_are_sorted_duckdb_names() -> None:
    names = allowed_switches("duckdb")
    assert names == tuple(sorted(DUCKDB_OPTIMIZER_FILES))
    assert names == tuple(sorted(names))
    assert "filter_pushdown" in names
    assert "join_order" in names
    assert allowed_switches("datafusion") == ()
    assert allowed_switches("sqlite") == ()
    assert allowed_switches("postgres") == ()
    assert allowed_switches("DuckDB") == ()


def test_prompt_is_pure_and_carries_no_ids() -> None:
    registry = default_registry()
    hypothesis = hyp(
        hypothesis_id="h1",
        interventions=("filter_pushdown",),
        plan_delta=("HashJoin",),
        fail_kind="wrong_result",
        error_class="mismatch",
        behavior_shape="missing_only",
    )
    case = SqlCase(engine="datafusion", setup=(_SOURCE_SETUP,), query=_SOURCE_QUERY, predicate=None)
    spec = Spec(engine="duckdb", oracle="cross_dbms", required=("ast:stmt:select", "ast:set_op:except_all"))
    first = translator_prompt(
        hypothesis=hypothesis,
        source_case=case,
        target_engine="duckdb",
        spec=spec,
        mechanism=None,
        registry=registry,
    )
    second = translator_prompt(
        hypothesis=hypothesis,
        source_case=case,
        target_engine="duckdb",
        spec=spec.to_dict(),
        mechanism=None,
        registry=registry,
        feedback=None,
    )
    assert first == second
    assert "EXCEPT ALL" in first.upper()
    assert "Source engine: datafusion" in first
    assert "Target engine: duckdb" in first
    assert "DuckDB SQL." in first
    assert "Oracle: cross_dbms" in first
    assert "Failure class: wrong_result" in first
    assert "Error class: mismatch" in first
    assert "Behavior shape: missing_only" in first
    assert "Source fix set: filter_pushdown" in first
    assert "Source plan differences: HashJoin" in first
    assert _SOURCE_SETUP in first
    assert _SOURCE_QUERY in first
    assert "Source predicate: (none)" in first
    assert "Mechanism: (none)" in first
    assert "- filter_pushdown" in first
    assert "The target engine has no switches" not in first
    assert "Reply with one JSON object and no other text." in first
    assert '"switches"' in first and '"behavior"' in first
    description = registry.get("ast:set_op:except_all").description
    assert "ast:set_op:except_all" in first
    assert description in first
    assert "h1" not in first.split()
    assert _RECORD not in first
    assert _FAMILY not in first
    assert str(_SEED) not in first
    bare = translator_prompt(
        hypothesis=hyp(engine="duckdb", interventions=(), plan_delta=()),
        source_case=case,
        target_engine="datafusion",
        spec=Spec(engine="datafusion", oracle="cross_dbms", required=("ast:stmt:select",)),
        mechanism="LAST-MECHANISM",
        registry=registry,
    )
    assert "The target engine has no switches. Identity is the behavior shape." in bare
    assert "filter_pushdown" not in bare
    assert "Mechanism: LAST-MECHANISM" in bare
    feedback = translator_prompt(
        hypothesis=hypothesis,
        source_case=case,
        target_engine="duckdb",
        spec=spec,
        mechanism=None,
        registry=registry,
        feedback={
            "query": "SELECT v FROM t UNION ALL SELECT v FROM u",
            "missing": ("ast:set_op:except_all",),
            "forbidden": ("ast:clause:limit",),
            "undetermined": ("data:type:integer",),
            "switch": "no_such_optimizer",
            "reason": "query must be a string",
        },
    )
    assert "Missing features:" in feedback
    assert "ast:set_op:except_all" in feedback
    assert "Extra features:" in feedback
    assert "ast:clause:limit" in feedback
    assert "Undetermined features:" in feedback
    assert "data:type:integer" in feedback
    assert "Unrecognised switch: no_such_optimizer" in feedback
    assert "Field problem: query must be a string" in feedback
    assert "SELECT v FROM t UNION ALL SELECT v FROM u" in feedback
    assert "Missing features:" not in first


def test_timing_serves_each_index_once_on_round_one(tmp_path: Path) -> None:
    assert TRANSLATOR_PER_CHOICE == 1
    script = Script({"translator": reply()})
    with opened(tmp_path, script) as (role, _ctx):
        assert role.report() == {
            "translations": 0,
            "by_status": {},
            "settled": {"kept": 0, "broken": 0, "void": 0},
            "identity": {"match": 0, "mismatch": 0, "unknown": 0},
        }
        assert book_text(role) == ""
        remember(role, _RECORD, _SOURCE_QUERY)
        assert role.translations() == []
        assert book_text(role) == ""
        src = role.sources()[0]
        assert isinstance(src, TranslatorSource)
        wb = Bench((hyp(), hyp(hypothesis_id="h2")), {"h1": "shared", "h2": "shared"})
        assert src.candidates(wb, index=1, round=2) == []
        assert script.calls == []
        assert 1 not in src._served
        first = src.candidates(wb, index=1, round=1)
        assert len(first) == 1 and first[0].hypothesis_id == "h1"
        assert len(script.calls) == 1
        again = src.candidates(wb, index=1, round=1)
        assert [item.case for item in again] == [first[0].case]
        assert len(script.calls) == 1
        later = src.candidates(wb, index=2, round=1)
        assert [item.case for item in later] == [first[0].case]
        assert len(script.calls) == 1
        later.clear()
        assert len(src.candidates(wb, index=3, round=1)) == 1
        assert len(script.calls) == 1


def test_distinct_families_take_distinct_choices(tmp_path: Path) -> None:
    script = Script({"translator": reply()})
    family = {"h1": "fam-a", "h2": "fam-b"}
    hyps = (
        hyp(positives=("rec-a",)),
        hyp(hypothesis_id="h2", positives=("rec-b",)),
    )
    with opened(tmp_path, script) as (role, _ctx):
        remember(role, "rec-a", "SELECT ONLYFAMILYA")
        remember(role, "rec-b", "SELECT ONLYFAMILYB")
        first = choose(role, hyps, family=family)
        assert [item.hypothesis_id for item in first] == ["h1"]
        assert len(script.calls) == 1
        assert "ONLYFAMILYA" in script.calls[0]["prompt"]
        second = choose(role, hyps, index=2, family=family)
        assert [item.hypothesis_id for item in second] == ["h1", "h2"]
        assert len(script.calls) == 2
        assert "ONLYFAMILYB" in script.calls[1]["prompt"]
        third = choose(role, hyps, index=3, family=family)
        assert [item.hypothesis_id for item in third] == ["h1", "h2"]
        assert len(script.calls) == 2


def test_one_engine_makes_no_call(tmp_path: Path) -> None:
    script = Script({"translator": reply()})
    wb = RaisingBench()
    with opened(tmp_path, script, engines=("datafusion",)) as (role, _ctx):
        remember(role, _RECORD, _SOURCE_QUERY)
        src = role.sources()[0]
        assert src.candidates(wb, index=1, round=1) == []
        assert script.calls == []
        assert wb.asked is False
        assert src._served == set()
        assert role.translations() == []


def test_skipped_hypotheses_do_not_consume_the_choice(tmp_path: Path) -> None:
    script = Script({"translator": reply()})
    hyps = (
        hyp(hypothesis_id="h-other", engine="sqlite"),
        hyp(hypothesis_id="h-none", oracle=None),
        hyp(hypothesis_id="h-unseen", positives=("never-seen",)),
        hyp(hypothesis_id="h-ok"),
    )
    with opened(tmp_path, script) as (role, _ctx):
        remember(role, _RECORD, _SOURCE_QUERY)
        made = choose(role, hyps)
        assert [item.hypothesis_id for item in made] == ["h-ok"]
        assert len(script.calls) == 1
        assert [row["hypothesis_id"] for row in translation_rows(role)] == ["h-ok"]


def test_empty_spec_consumes_the_choice(tmp_path: Path) -> None:
    script = Script({"translator": reply()})
    hyps = (
        hyp(hypothesis_id="h-empty", specific=("plan:not_a_real_feature",)),
        hyp(hypothesis_id="h-ok"),
    )
    with opened(tmp_path, script) as (role, _ctx):
        remember(role, _RECORD, _SOURCE_QUERY)
        assert choose(role, hyps) == []
        assert script.calls == []
        row = translation_rows(role)[0]
        assert set(row) == _TRANSLATION_KEYS
        assert row["translation_id"] == "t1"
        assert row["status"] == "empty_spec"
        assert row["hypothesis_id"] == "h-empty"
        assert row["tries"] == 0
        assert row["keys"] == []
        assert row["case"] is None and row["case_digest"] is None
        assert row["expect"] is None and row["switches"] is None and row["behavior"] is None
        made = choose(role, hyps, index=2)
        assert [item.hypothesis_id for item in made] == ["h-ok"]
        assert len(script.calls) == 1
        assert [item["translation_id"] for item in translation_rows(role)] == ["t1", "t2"]


def test_plan_literals_stay_out_of_the_spec(tmp_path: Path) -> None:
    script = Script({"translator": reply()})
    extract = FixedExtract(("ast:stmt:select", "data:type:integer"))
    hypothesis = hyp(specific=("plan:not_a_real_feature", "data:type:integer", "ast:stmt:select"))
    with opened(tmp_path, script, extract=extract) as (role, _ctx):
        remember(role, _RECORD, _SOURCE_QUERY)
        made = choose(role, (hypothesis,))
        assert len(made) == 1
        target = made[0].target
        assert target["required"] == ["ast:stmt:select", "data:type:integer"]
        assert target["data_properties"] == []
        assert "plan:not_a_real_feature" not in json.dumps(target)
        assert "plan:not_a_real_feature" not in script.calls[0]["prompt"]
        assert check_spec(extract(made[0].case), Spec.from_dict(target)).ok


def test_two_targets_follow_engine_order(tmp_path: Path) -> None:
    script = Script({"translator": reply()})
    engines = ("sqlite", "duckdb", "datafusion")
    with opened(tmp_path, script, engines=engines) as (role, _ctx):
        remember(role, _RECORD, _SOURCE_QUERY)
        first = choose(role, (hyp(),))
        assert [item.case.engine for item in first] == ["sqlite"]
        second = choose(role, (hyp(),), index=2)
        assert [item.case.engine for item in second] == ["sqlite", "duckdb"]
        third = choose(role, (hyp(),), index=3)
        assert [item.case.engine for item in third] == ["sqlite", "duckdb"]
        assert len(script.calls) == 2
        assert "Target engine: sqlite" in script.calls[0]["prompt"]
        assert "Target engine: duckdb" in script.calls[1]["prompt"]
        assert list(role.manifest()["switches"]) == ["sqlite", "duckdb", "datafusion"]
        assert role.manifest()["switches"]["sqlite"] == []
        assert role.manifest()["switches"]["duckdb"] == list(allowed_switches("duckdb"))


def test_source_case_is_the_last_remembered_positive(tmp_path: Path) -> None:
    script = Script({"translator": reply()})
    with opened(tmp_path, script) as (role, _ctx):
        remember(role, "rec-a", "SELECT ONLYFIRSTMARKER")
        remember(role, "rec-b", "SELECT ONLYLASTMARKER")
        made = choose(role, (hyp(positives=("rec-a", "missing", "rec-b")),))
        assert len(made) == 1
        assert made[0].parent == "rec-b"
        prompt = script.calls[0]["prompt"]
        assert "ONLYLASTMARKER" in prompt
        assert "ONLYFIRSTMARKER" not in prompt


def test_mechanism_is_the_last_registered_conjecture(tmp_path: Path) -> None:
    script = Script({"translator": reply()})
    with opened(tmp_path, script) as (role, ctx):
        add_conjecture(ctx.book, "h1", "registered", "FIRST-MECHANISM", 1)
        add_conjecture(ctx.book, "h1", "registered", "LAST-MECHANISM", 2)
        add_conjecture(ctx.book, "h2", "registered", "OTHER-MECHANISM", 3)
        add_conjecture(ctx.book, "h1", "rejected", "REJECTED-MECHANISM", 4)
        remember(role, _RECORD, _SOURCE_QUERY)
        choose(role, (hyp(),))
        prompt = script.calls[0]["prompt"]
        assert "Mechanism: LAST-MECHANISM" in prompt
        assert "FIRST-MECHANISM" not in prompt
        assert "OTHER-MECHANISM" not in prompt
        assert "REJECTED-MECHANISM" not in prompt
        assert "CONJ-RECORD" not in prompt


def test_ok_translation_records_the_candidate_and_the_call(tmp_path: Path) -> None:
    script = Script({"translator": reply(query="SELECT 'caf\u00e9'")})
    extract = FixedExtract()
    with opened(tmp_path, script, extract=extract) as (role, _ctx):
        remember(role, _RECORD, _SOURCE_QUERY)
        made = choose(role, (hyp(),), family={"h1": _FAMILY})
        assert len(made) == 1 and extract.calls == 1
        cand = made[0]
        assert cand.case.engine == "duckdb"
        assert cand.case.query == "SELECT 'caf\u00e9'"
        assert cand.oracle == "cross_dbms" and cand.rule is None
        assert cand.lane == "translate" and cand.op == "translator"
        assert cand.hypothesis_id == "h1" and cand.parent == _RECORD
        assert cand.target["engine"] == "duckdb"
        assert check_spec(extract(cand.case), Spec.from_dict(cand.target)).ok
        call = script.calls[0]
        assert call["role"] == "translator"
        assert call["model"] == TIERS[TRANSLATOR_TIER]
        assert call["temperature"] == TRANSLATOR_TEMPERATURE
        assert call["max_tokens"] == TRANSLATOR_MAX_TOKENS
        assert _RECORD not in call["prompt"]
        assert "h1" not in call["prompt"].split()
        assert _FAMILY not in call["prompt"]
        assert str(_SEED) not in call["prompt"]
        row = translation_rows(role)[0]
        assert set(row) == _TRANSLATION_KEYS
        assert row["translation_id"] == "t1" and row["status"] == "ok"
        assert row["family"] == _FAMILY and row["parent"] == _RECORD
        assert row["source_engine"] == "datafusion" and row["target_engine"] == "duckdb"
        assert row["expect"] == "pass" and row["switches"] == [] and row["behavior"] is None
        assert row["tries"] == 1 and len(row["keys"]) == 1 and isinstance(row["keys"][0], str)
        assert row["case"] == json.loads(json.dumps(cand.case.to_dict()))
        assert row["case_digest"] == case_digest(cand.case)
        assert parsed_book(role) == role.translations()
        raw = book_text(role)
        assert "\\u00e9" in raw and "\u00e9" not in raw
        assert "latency" not in raw and "token" not in raw


def test_spec_unmet_retries_with_the_missing_feature(tmp_path: Path) -> None:
    script = Script({
        "translator": [
            reply(query="SELECT v FROM t UNION ALL SELECT v FROM u"),
            reply(query="SELECT v FROM t EXCEPT ALL SELECT v FROM u"),
        ]
    })
    extract = QueryExtract()
    hypothesis = hyp(specific=("ast:stmt:select", "ast:set_op:except_all"))
    with opened(tmp_path, script, extract=extract) as (role, _ctx):
        remember(role, _RECORD, _SOURCE_QUERY)
        made = choose(role, (hypothesis,))
        assert len(made) == 1 and len(script.calls) == 2 and extract.calls == 2
        assert "EXCEPT ALL" in made[0].case.query.upper()
        assert "Missing features:" not in script.calls[0]["prompt"]
        retried = script.calls[1]["prompt"].split("Missing features:", 1)[1]
        assert "ast:set_op:except_all" in retried
        row = translation_rows(role)[0]
        assert row["status"] == "ok" and row["tries"] == 2 and len(row["keys"]) == 2


def test_bad_switch_retries_then_is_not_offered_again(tmp_path: Path) -> None:
    script = Script({
        "translator": reply(expect="fail", switches=["no_such_optimizer"], behavior="missing_only")
    })
    with opened(tmp_path, script) as (role, _ctx):
        remember(role, _RECORD, _SOURCE_QUERY)
        assert choose(role, (hyp(),)) == []
        assert len(script.calls) == TRANSLATOR_ATTEMPTS
        row = translation_rows(role)[0]
        assert row["status"] == "bad_switch" and row["tries"] == TRANSLATOR_ATTEMPTS
        assert row["case"] is None and row["case_digest"] is None
        assert row["switches"] == ["no_such_optimizer"]
        assert row["expect"] == "fail" and row["behavior"] == "missing_only"
        assert "Unrecognised switch: no_such_optimizer" in script.calls[1]["prompt"]
        assert choose(role, (hyp(),), index=2) == []
        assert len(script.calls) == TRANSLATOR_ATTEMPTS


def test_bad_switch_then_a_legal_reply_is_ok(tmp_path: Path) -> None:
    script = Script({
        "translator": [
            reply(expect="fail", switches=["no_such_optimizer"], behavior="missing_only"),
            reply(),
        ]
    })
    with opened(tmp_path, script) as (role, _ctx):
        remember(role, _RECORD, _SOURCE_QUERY)
        made = choose(role, (hyp(),))
        assert len(made) == 1 and len(script.calls) == 2
        row = translation_rows(role)[0]
        assert row["status"] == "ok" and row["tries"] == 2
        assert row["expect"] == "pass" and row["switches"] == [] and row["behavior"] is None


def test_not_applicable_does_not_retry_or_extract(tmp_path: Path) -> None:
    script = Script({"translator": reply(predicate=None)})
    extract = FixedExtract()
    with opened(tmp_path, script, extract=extract) as (role, _ctx):
        remember(role, _RECORD, _SOURCE_QUERY)
        assert choose(role, (hyp(oracle="tlp"),)) == []
        assert extract.calls == 0 and len(script.calls) == 1
        row = translation_rows(role)[0]
        assert row["status"] == "not_applicable" and row["tries"] == 1
        assert row["case"]["engine"] == "duckdb"
        assert row["case"]["predicate"] is None
        assert row["case_digest"] == case_digest(SqlCase(
            engine="duckdb", setup=("CREATE TABLE t(v INT)",), query="SELECT v FROM t", predicate=None
        ))


def test_equivalent_query_keeps_the_first_rule(tmp_path: Path) -> None:
    script = Script({"translator": reply()})
    with opened(tmp_path, script) as (role, _ctx):
        remember(role, _RECORD, _SOURCE_QUERY)
        made = choose(role, (hyp(oracle="equivalent_query"),))
        assert len(made) == 1
        options = oracle_options(made[0].case, ["equivalent_query"])
        assert options[0][1] == "double_negation"
        assert made[0].rule == options[0][1]
        assert made[0].oracle == "equivalent_query"


def test_bad_case_and_gateway_rejection_retry(tmp_path: Path) -> None:
    empty = Script({"translator": reply(query="")})
    with opened(tmp_path / "empty", empty) as (role, _ctx):
        remember(role, _RECORD, _SOURCE_QUERY)
        assert choose(role, (hyp(),)) == []
        assert len(empty.calls) == TRANSLATOR_ATTEMPTS
        row = translation_rows(role)[0]
        assert row["status"] == "bad_case" and row["tries"] == TRANSLATOR_ATTEMPTS
        assert row["case"] is None
        assert "must be a non-empty string" in empty.calls[1]["prompt"]
    junk = Script({"translator": "this is not json"})
    with opened(tmp_path / "junk", junk) as (role, _ctx):
        remember(role, _RECORD, _SOURCE_QUERY)
        assert choose(role, (hyp(),)) == []
        row = translation_rows(role)[0]
        assert row["status"] == "rejected" and row["tries"] == TRANSLATOR_ATTEMPTS
        assert row["expect"] is None and row["switches"] is None and row["behavior"] is None
        assert "no_json" in junk.calls[1]["prompt"]


def test_field_errors_are_checked_before_switch_names(tmp_path: Path) -> None:
    missing = reply(switches=["no_such_optimizer"])
    del missing["prediction"]["behavior"]
    script = Script({"translator": missing})
    with opened(tmp_path / "missing", script) as (role, _ctx):
        remember(role, _RECORD, _SOURCE_QUERY)
        assert choose(role, (hyp(),)) == []
        row = translation_rows(role)[0]
        assert row["status"] == "rejected" and row["tries"] == TRANSLATOR_ATTEMPTS
        assert "prediction.behavior must be" in script.calls[1]["prompt"]
        assert "Unrecognised switch" not in script.calls[1]["prompt"]
    text = reply()
    text["prediction"]["switches"] = "filter_pushdown"
    script = Script({"translator": text})
    with opened(tmp_path / "text", script) as (role, _ctx):
        remember(role, _RECORD, _SOURCE_QUERY)
        assert choose(role, (hyp(),)) == []
        assert translation_rows(role)[0]["status"] == "rejected"
        assert "prediction.switches must be a list of strings" in script.calls[1]["prompt"]
        assert "Unrecognised switch" not in script.calls[1]["prompt"]
    script = Script({
        "translator": reply(switches=["no_such_optimizer"], behavior="sideways")
    })
    with opened(tmp_path / "switch-first", script) as (role, _ctx):
        remember(role, _RECORD, _SOURCE_QUERY)
        assert choose(role, (hyp(),)) == []
        assert translation_rows(role)[0]["status"] == "bad_switch"
        assert "Unrecognised switch: no_such_optimizer" in script.calls[1]["prompt"]
    script = Script({"translator": reply(switches=["filter_pushdown"], behavior="sideways")})
    with opened(tmp_path / "behavior", script) as (role, _ctx):
        remember(role, _RECORD, _SOURCE_QUERY)
        assert choose(role, (hyp(),)) == []
        assert translation_rows(role)[0]["status"] == "rejected"
        assert "prediction.behavior must be" in script.calls[1]["prompt"]


def test_gateway_stop_statuses_do_not_retry(tmp_path: Path) -> None:
    script = Script({"translator": reply()})
    with opened(tmp_path / "blocked", script, max_calls=0) as (role, _ctx):
        remember(role, _RECORD, _SOURCE_QUERY)
        assert choose(role, (hyp(),)) == []
        assert script.calls == []
        row = translation_rows(role)[0]
        assert row["status"] == "blocked" and row["tries"] == 1
    with opened(tmp_path / "miss", None) as (role, _ctx):
        remember(role, _RECORD, _SOURCE_QUERY)
        assert choose(role, (hyp(),)) == []
        row = translation_rows(role)[0]
        assert row["status"] == "miss" and row["tries"] == 1
    boom = Boom()
    with opened(tmp_path / "error", boom) as (role, _ctx):
        remember(role, _RECORD, _SOURCE_QUERY)
        assert choose(role, (hyp(),)) == []
        assert boom.calls == 1
        row = translation_rows(role)[0]
        assert row["status"] == "error" and row["tries"] == 1


def test_unknown_ast_feature_is_not_swallowed(tmp_path: Path) -> None:
    script = Script({"translator": reply()})
    with opened(tmp_path, script) as (role, _ctx):
        remember(role, _RECORD, _SOURCE_QUERY)
        with pytest.raises(ValueError, match="unknown feature"):
            choose(role, (hyp(specific=("ast:not_a_real_feature",)),))
        assert script.calls == []


def test_settlement_states_and_identity(tmp_path: Path) -> None:
    plain = reply()
    passed = reply(expect="pass", switches=["filter_pushdown"], behavior="missing_only")
    failed = reply(expect="fail", switches=["filter_pushdown"], behavior="missing_only")
    shaped = reply(expect="fail", switches=[], behavior="missing_only")
    unnamed = reply(expect="fail", switches=[], behavior=None)
    matched = {"profile": {"status": "ran", "fix_set": ["filter_pushdown"]}}
    profile_wins = {
        "profile": {"status": "ran", "fix_set": ["filter_pushdown"]},
        "attribution": {"status": "ran", "consistent": False, "hypothesis_id": "h1"},
    }
    empty_profile = {
        "profile": {"status": "ran", "fix_set": []},
        "attribution": {"status": "ran", "consistent": True, "hypothesis_id": "h1"},
    }
    denied = {"attribution": {"status": "ran", "consistent": False, "hypothesis_id": "h1"}}
    credited = {"attribution": {"status": "ran", "consistent": True, "hypothesis_id": "h1"}}
    same = SimpleNamespace(theory=Theory((hyp(interventions=("filter_pushdown",)),)))
    other = SimpleNamespace(theory=Theory((hyp(interventions=("join_order",)),)))
    absent = SimpleNamespace(theory=Theory(()))
    scanned = SimpleNamespace(theory=ScanTheory((hyp(interventions=("filter_pushdown",)),)))
    text_fix = SimpleNamespace(theory=Theory((hyp(interventions="filter_pushdown"),)))
    cases = (
        ("pass-kept", plain, label("pass"), None, ("kept", None)),
        ("pass-ignores-profile", passed, label("pass", cve={"profile": {"status": "ran", "fix_set": ["join_order"]}}), None, ("kept", None)),
        ("fail-against-pass", passed, label("fail", cve=matched), None, ("broken", None)),
        ("pass-against-fail", failed, label("pass"), None, ("broken", None)),
        ("invalid", failed, label("invalid", cve=matched), None, ("void", None)),
        ("profile-match", failed, label("fail", cve=matched), None, ("kept", "match")),
        ("profile-mismatch", failed, label("fail", cve={"profile": {"status": "ran", "fix_set": ["join_order"]}}), None, ("kept", "mismatch")),
        ("profile-wins", failed, label("fail", cve=profile_wins), None, ("kept", "match")),
        ("empty-fix-set", failed, label("fail", cve=empty_profile), same, ("kept", "mismatch")),
        ("attribution-false", failed, label("fail", cve=denied), None, ("kept", "mismatch")),
        ("attribution-no-wb", failed, label("fail", cve=credited), None, ("kept", "unknown")),
        ("attribution-match", failed, label("fail", cve=credited), same, ("kept", "match")),
        ("attribution-mismatch", failed, label("fail", cve=credited), other, ("kept", "mismatch")),
        ("attribution-missing", failed, label("fail", cve=credited), absent, ("kept", "unknown")),
        ("attribution-scan", failed, label("fail", cve=credited), scanned, ("kept", "match")),
        ("interventions-not-a-list", failed, label("fail", cve=credited), text_fix, ("kept", "unknown")),
        ("no-cve", failed, label("fail"), None, ("kept", "unknown")),
        ("behavior-unknown", unnamed, label("fail"), None, ("kept", "unknown")),
        ("behavior-match", shaped, label("fail", behavior={"missing": 1, "extra": 0}), None, ("kept", "match")),
        ("behavior-mismatch", shaped, label("fail", behavior={"missing": 0, "extra": 1}), None, ("kept", "mismatch")),
        ("behavior-no-identity", shaped, label("fail", identity=None), None, ("kept", "mismatch")),
    )
    for name, payload, seen, wb, want in cases:
        script = Script({"translator": payload})
        with opened(tmp_path / name, script) as (role, _ctx):
            remember(role, _RECORD, _SOURCE_QUERY)
            made = choose(role, (hyp(),))
            assert len(made) == 1, name
            row = settle(role, made[0], seen, wb=wb)
            assert (row["type"], row["state"], row["identity"], row["record_id"]) == ("settle", want[0], want[1], "out-1"), name
            assert set(row) == _SETTLE_KEYS
            report = role.report()
            assert report["translations"] == 1 and report["by_status"] == {"ok": 1}
            settled = {"kept": 0, "broken": 0, "void": 0}
            settled[want[0]] = 1
            identity = {"match": 0, "mismatch": 0, "unknown": 0}
            if want[1] in identity:
                identity[want[1]] = 1
            assert report["settled"] == settled and report["identity"] == identity
            assert len(role.translations()) == 2
            settle(role, made[0], seen, record_id="out-2", wb=wb)
            assert len(role.translations()) == 2
            assert role.report() == report


def test_a_different_oracle_does_not_settle(tmp_path: Path) -> None:
    script = Script({"translator": reply()})
    with opened(tmp_path, script) as (role, _ctx):
        remember(role, _RECORD, _SOURCE_QUERY)
        made = choose(role, (hyp(),))
        before = len(role.translations())
        role.observe(
            SimpleNamespace(
                wb=None,
                record=SimpleNamespace(record_id="other", case=made[0].case, label=label("pass", oracle="tlp")),
                prediction=None,
                outcome=None,
            )
        )
        assert len(role.translations()) == before
        assert role.report()["settled"] == {"kept": 0, "broken": 0, "void": 0}
        row = settle(role, made[0], label("pass"))
        assert row["state"] == "kept" and row["identity"] is None


def test_step_window_clears_and_rows_are_detached(tmp_path: Path) -> None:
    script = Script({"translator": reply()})
    with opened(tmp_path, script) as (role, _ctx):
        assert role.step() == {"translated": [], "settled": []}
        remember(role, _RECORD, _SOURCE_QUERY)
        made = choose(role, (hyp(),))
        assert role.step() == {"translated": [["t1", "ok"]], "settled": []}
        assert role.step() == {"translated": [], "settled": []}
        settle(role, made[0], label("pass"))
        window = role.step()
        assert window == {"translated": [], "settled": [["t1", "kept", None]]}
        window["settled"][0][1] = "changed"
        assert role.step() == {"translated": [], "settled": []}
        copied = role.translations()
        copied[0]["status"] = "changed"
        copied.append({"type": "extra"})
        assert role.translations()[0]["status"] == "ok"
        assert len(role.translations()) == 2
        assert parsed_book(role) == role.translations()


def test_replay_continues_ids_and_can_settle(tmp_path: Path) -> None:
    script = Script({"translator": [reply(query="SELECT v FROM t"), reply(query="SELECT v FROM u")]})
    ctx = ctx_for(tmp_path, script)
    role = build(ctx)
    remember(role, _RECORD, _SOURCE_QUERY)
    made = choose(role, (hyp(),))
    saved = role.translations()
    saved_report = role.report()
    assert saved[0]["translation_id"] == "t1" and saved_report["translations"] == 1
    role.close()
    role.close()
    role2 = build(ctx)
    try:
        assert role2.translations() == saved
        assert role2.report() == saved_report
        assert role2.step() == {"translated": [], "settled": []}
        row = settle(role2, made[0], label("pass"))
        assert (row["state"], row["identity"]) == ("kept", None)
        assert len(role2.translations()) == 2
        settle(role2, made[0], label("pass"), record_id="out-2")
        assert len(role2.translations()) == 2
        remember(role2, "rec-b", "SELECT ONLYSECOND")
        more = choose(role2, (hyp(hypothesis_id="h2", positives=("rec-b",)),))
        assert len(more) == 1
        assert [item["translation_id"] for item in translation_rows(role2)] == ["t1", "t2"]
        assert role2.report()["translations"] == 2
        role2.close()
        replayed = role2.translations()
        replayed_report = role2.report()
        role3 = build(ctx)
        try:
            assert role3.translations() == replayed
            assert role3.report() == replayed_report
            assert role3.step() == {"translated": [], "settled": []}
        finally:
            role3.close()
    finally:
        role2.close()


def test_replay_rejects_a_non_object(tmp_path: Path) -> None:
    ctx = ctx_for(tmp_path, Script({"translator": reply()}))
    path = ctx.llm_dir / "translations.jsonl"
    path.write_text("[1]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="object"):
        build(ctx)


def test_build_roles_wires_the_translator_source(tmp_path: Path) -> None:
    script = Script({"translator": reply()})
    extract = FixedExtract()
    made = build_roles(
        {
            "roles": ["translator"],
            "cache": str(tmp_path / "cache"),
            "max_calls": 20,
            "network": False,
            "transport": script,
        },
        run_dir=tmp_path / "run",
        extract=extract,
        registry=None,
        engines=("datafusion", "duckdb"),
        seed=0,
        oracles=("cross_dbms",),
    )
    try:
        assert isinstance(made.sources, tuple) and len(made.sources) == 1
        assert isinstance(made.sources[0], TranslatorSource)
        role = made.plugins["translator"]
        assert role.name == "translator"
        assert role.sources() == (made.sources[0],)
        switches = made.manifest()["plugins"]["translator"]["switches"]
        assert list(switches) == ["datafusion", "duckdb"]
        assert switches["duckdb"] == list(allowed_switches("duckdb"))
        assert switches["datafusion"] == []
    finally:
        made.close()
