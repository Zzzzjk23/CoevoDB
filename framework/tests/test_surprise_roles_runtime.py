"""RoleSet and ImplementerSource. Scripted transport, DuckDB phi checks, no network."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from surprise.features.extract import extract
from surprise.features.phi import make_phi
from surprise.harness.contracts import IdentityEvidence, Label, SqlCase
from surprise.hunter.operators import oracle_options
from surprise.roles.constants import CONJECTURER_TIER, SOURCE_COMMITS, TIERS
from surprise.roles.conjecturer import Conjecture
from surprise.roles.runtime import build_roles
from surprise.theory.contracts import Spec
from surprise.theory.workbench import Workbench

LAYERS = {"ast": "ok", "plan": "ok", "data": "ok"}


class Script:
    def __init__(self, replies: Any) -> None:
        self.replies = replies if callable(replies) or isinstance(replies, dict) else list(replies)
        self.calls: list[dict[str, Any]] = []

    def complete(self, *, model: str, prompt: str, temperature: float, max_tokens: int, role: str) -> Any:
        self.calls.append({"model": model, "prompt": prompt, "role": role})
        if isinstance(self.replies, dict):
            reply = self.replies[role]
        elif callable(self.replies):
            reply = self.replies(prompt)
        else:
            reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        text = reply if isinstance(reply, str) else json.dumps(reply)
        from surprise.roles.gateway import Completion

        return Completion(text=text, input_tokens=1, output_tokens=1)


def fail_label(oracle: str = "plan_variant") -> Label:
    return Label(
        y="fail",
        oracle=oracle,
        fail_kind="wrong_result",
        identity=IdentityEvidence(error_class=None, behavior={"missing": 1}),
        cve={
            "profile": {
                "status": "ran",
                "fix_kind": "non_optimizer",
                "fix_set": [],
                "plan_diff": [],
                "version_ladder": "longstanding",
                "witness_switches": [],
            }
        },
    )


def open_family(tmp: Path, features: tuple[str, ...], *, oracle: str = "plan_variant", record_id: str = "rec-1") -> dict[str, Any]:
    wb = Workbench.create(tmp / "theory")
    phi = make_phi("duckdb", features, LAYERS)
    label = fail_label(oracle)
    case = SqlCase(engine="duckdb", setup=(), query="SELECT 1")
    outcome = wb.observe(phi, label, record_id)
    record = SimpleNamespace(record_id=record_id, phi=phi.to_dict(), case=case, label=label)
    return {"wb": wb, "phi": phi, "label": label, "record": record, "outcome": outcome}


def roles(tmp: Path, script: Any, *, which: tuple[str, ...] = ("implementer", "conjecturer"), network: bool = False,
          max_calls: int = 20, transport: bool = True, engines: tuple[str, ...] = ("duckdb",)) -> Any:
    config: dict[str, Any] = {
        "roles": list(which),
        "cache": str(tmp / "cache"),
        "max_calls": max_calls,
        "network": network,
    }
    if transport:
        config["transport"] = script
    return build_roles(config, run_dir=tmp / "run", extract=extract, registry=None, engines=engines, seed=4)


def select_sql(prompt: str) -> dict[str, Any]:
    raw = prompt.split("Spec:\n", 1)[1]
    body = raw.split("\nPrevious attempt:", 1)[0]
    target = json.loads(body)
    if "ast:clause:where" in target["forbidden"]:
        query = "SELECT 1"
    else:
        query = "SELECT 1 FROM t WHERE v = 1"
    return {"setup": [], "query": query, "predicate": None, "prediction": {"expect": "pass", "why": "phi"}}


def conjecture_text() -> dict[str, Any]:
    return {
        "mechanism": "the filter is applied too early",
        "trigger": ["ast:stmt:select"],
        "prediction": [
            {"required": ["ast:stmt:select"], "forbidden": [], "data_properties": [], "expect": "fail", "why": "still a select"},
            {"required": ["ast:clause:limit"], "forbidden": [], "data_properties": [], "expect": "pass", "why": "a limit is a different statement"},
        ],
    }


def test_build_roles_rejects_unknown_and_empty_and_dedupes(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown role"):
        roles(tmp_path / "bad", Script([]), which=("diagnoser",))
    with pytest.raises(ValueError, match="non-empty"):
        roles(tmp_path / "empty", Script([]), which=())
    made = roles(tmp_path / "dup", Script([]), which=("conjecturer", "implementer", "conjecturer"))
    assert made.manifest()["roles"] == ["conjecturer", "implementer"]
    assert made.manifest()["seed"] == 4
    assert made.manifest()["network"] is False
    assert made.manifest()["tiers"] == TIERS
    assert made.manifest()["constants"]["CONJECTURER_TIER"] == CONJECTURER_TIER == "fast"
    assert made.manifest()["max_calls"] == made._gateway.max_calls
    sources = made.manifest()["sources"]
    if sources:
        assert sources["duckdb"]["commit"] == SOURCE_COMMITS["duckdb"]
        assert sources["datafusion"]["dir"] == "datafusion-54.0.0"
    made.close()
    made.close()


def test_offline_does_not_construct_a_transport(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import surprise.roles.transport as transport

    def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("DeepSeekTransport was constructed")

    monkeypatch.setattr(transport, "DeepSeekTransport", boom)
    made = roles(tmp_path, None, which=("conjecturer",), network=False, transport=False)
    opened = open_family(tmp_path / "fam", ("ast:stmt:select",))
    conjecture = made.after(opened["wb"], opened["record"], opened["outcome"])
    assert conjecture is not None and conjecture.status == "miss"
    assert made.sources == ()
    with pytest.raises(AssertionError, match="constructed"):
        roles(tmp_path / "net", None, which=("conjecturer",), network=True, transport=False)


def test_only_implementer_skips_after_and_only_conjecturer_has_no_source(tmp_path: Path) -> None:
    script = Script([conjecture_text()])
    conj = roles(tmp_path / "conj", script, which=("conjecturer",))
    assert conj.sources == ()
    opened = open_family(tmp_path / "fam", ("ast:stmt:select", "ast:clause:where"))
    assert conj.after(opened["wb"], opened["record"], opened["outcome"]) is not None
    impl = roles(tmp_path / "impl", Script([]), which=("implementer",))
    assert len(impl.sources) == 1
    assert impl.after(opened["wb"], opened["record"], opened["outcome"]) is None
    assert impl._book.summary()["conjectures"] == 0
    assert (tmp_path / "impl" / "run" / "llm" / "implementer.jsonl").is_file()
    assert (tmp_path / "conj" / "run" / "llm" / "conjectures.jsonl").is_file()


def test_step_records_the_window_and_a_none_does_not_clear_it(tmp_path: Path) -> None:
    script = Script({"conjecturer": conjecture_text(), "implementer": select_sql})
    made = roles(tmp_path, script, network=True)
    assert made.manifest()["network"] is True
    opened = open_family(tmp_path / "fam", ("ast:stmt:select", "ast:clause:where"))
    first = made.after(opened["wb"], opened["record"], opened["outcome"])
    assert first is not None and first.status == "registered"
    assert made.after(opened["wb"], opened["record"], SimpleNamespace(observation=SimpleNamespace(opened=None))) is None
    row = made.step()
    assert set(row) == {"calls", "conjecture", "settled", "attempts"}
    assert row["conjecture"] == [first.conjecture_id, "registered"]
    assert row["calls"] == {"conjecturer": {"ok": 1}}
    assert row["settled"] == [] and row["attempts"] == []
    assert "source" not in row and "tokens" not in json.dumps(row)
    assert made.step() == {"calls": {}, "conjecture": None, "settled": [], "attempts": []}
    settled = made.observe(opened["phi"], opened["label"], "later")
    assert [(item.index, item.state) for item in settled] == [(0, "kept")]
    assert made.step()["settled"] == [[first.conjecture_id, 0, "kept"]]
    report = made.report()
    assert report["book"]["kept"] == 1 and report["book"]["conjectures"] == 1
    assert report["calls"]["by_role"]["conjecturer"]["ok"] == 1
    made.close()


def test_candidates_serve_bets_then_boundaries_once(tmp_path: Path) -> None:
    opened = open_family(tmp_path / "fam", ("ast:stmt:select", "ast:clause:where"))
    hypothesis_id = opened["outcome"].observation.opened
    bet = Spec(
        engine="duckdb", oracle="plan_variant", required=("ast:stmt:select",), forbidden=("ast:clause:where",)
    ).to_dict()
    made = roles(tmp_path, Script(select_sql))
    source = made.sources[0]
    source.book.add(
        Conjecture(
            conjecture_id="c1", record_id="rec-1", hypothesis_id=hypothesis_id, engine="duckdb", oracle="plan_variant",
            status="registered", reason=None, mechanism="m", trigger=("ast:stmt:select",),
            predictions=(
                {"spec": bet, "expect": "fail", "why": "bet"},
                {"spec": dict(bet, engine="postgres"), "expect": "fail", "why": "other engine"},
            ),
            dropped=(), edit_id=None, accepted=None, edit_reason=None, key=None, sources=(),
        )
    )
    # The book's next id follows what it has received. This row was inserted as c1.
    found = source.candidates(opened["wb"], index=0, round=1)
    assert [item.lane for item in found] == ["bet"]
    assert found[0].op == "implementer" and found[0].parent is None
    assert found[0].hypothesis_id == hypothesis_id
    assert found[0].case.query == "SELECT 1"
    assert found[0].rule is None and found[0].oracle == "plan_variant"
    assert found[0].target["forbidden"] == ["ast:clause:where"]
    assert source.candidates(opened["wb"], index=0, round=1) == []
    assert source.candidates(opened["wb"], index=7, round=2) == []
    assert source.candidates(opened["wb"], index=7, round=1) == []
    lines = (tmp_path / "run" / "llm" / "implementer.jsonl").read_text(encoding="utf-8").splitlines()
    logged = [json.loads(line) for line in lines]
    assert [(row["lane"], row["index"], row["status"]) for row in logged] == [
        ("bet", 0, "ok"),
        ("implement", 7, "spec_unmet"),
    ]
    assert logged[1]["spec"]["forbidden"] == ["ast:stmt:select"]
    plain = roles(tmp_path / "plain", Script(select_sql))
    boundary = plain.sources[0].candidates(opened["wb"], index=3, round=1)
    assert len(boundary) == 1 and boundary[0].lane == "implement" and boundary[0].case.query == "SELECT 1"
    row = made.step()
    assert row["attempts"] == ["ok", "spec_unmet"]
    assert row["calls"]["implementer"]["ok"] == 3
    assert made.report()["implementer"] == {
        "attempts": 2, "ok": 1, "first_ok": 1, "by_status": {"ok": 1, "spec_unmet": 1},
    }
    single = open_family(tmp_path / "one", ("ast:stmt:select",))
    quiet = roles(tmp_path / "quiet", Script(select_sql))
    assert quiet.sources[0].candidates(single["wb"], index=0, round=1) == []
    assert quiet.sources[0]._served == {0}
    assert Script(select_sql).calls == []


def test_equivalent_query_uses_the_first_rule_and_drops_a_case_with_none(tmp_path: Path) -> None:
    opened = open_family(tmp_path / "fam", ("ast:stmt:select",), oracle="equivalent_query")
    bet = Spec(engine="duckdb", oracle="equivalent_query", required=("ast:stmt:select",)).to_dict()
    made = roles(tmp_path, Script(select_sql), engines=("duckdb",))
    made.sources[0].book.add(
        Conjecture(
            conjecture_id="c9", record_id="rec-1", hypothesis_id="h1", engine="duckdb", oracle="equivalent_query",
            status="registered", reason=None, mechanism="m", trigger=("ast:stmt:select",),
            predictions=({"spec": bet, "expect": "fail", "why": "w"},),
            dropped=(), edit_id=None, accepted=None, edit_reason=None, key=None, sources=(),
        )
    )
    found = made.sources[0].candidates(opened["wb"], index=1, round=1)
    assert len(found) == 1 and found[0].rule
    assert found[0].rule == oracle_options(found[0].case, ["equivalent_query"])[0][1]
    made2 = roles(tmp_path / "none", Script(select_sql))
    made2.sources[0].book.add(
        Conjecture(
            conjecture_id="c9", record_id="rec-1", hypothesis_id="h1", engine="duckdb", oracle="equivalent_query",
            status="registered", reason=None, mechanism="m", trigger=("ast:stmt:select",),
            predictions=({"spec": bet, "expect": "fail", "why": "w"},),
            dropped=(), edit_id=None, accepted=None, edit_reason=None, key=None, sources=(),
        )
    )
    with patch("surprise.hunter.operators.oracle_options", return_value=[]):
        assert made2.sources[0].candidates(opened["wb"], index=1, round=1) == []
    logged = json.loads((tmp_path / "none" / "run" / "llm" / "implementer.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert logged["status"] == "ok" and logged["lane"] == "bet"


def test_boundary_queue_skips_plan_literals_and_empty_required(tmp_path: Path) -> None:
    made = roles(tmp_path, Script([]))
    hypothesis = SimpleNamespace(
        engine="duckdb",
        oracle="plan_variant",
        hypothesis_id="h9",
        specific=("plan:not-a-leaf", "ast:stmt:select", "ast:clause:where"),
    )
    bench = SimpleNamespace(theory=SimpleNamespace(hypotheses=(hypothesis,)))
    queue = made.sources[0]._queue(bench)
    assert queue and all(item["lane"] == "implement" for item in queue)
    assert all("plan:not-a-leaf" not in json.dumps(item["spec"]) for item in queue)
    alone = SimpleNamespace(
        engine="duckdb", oracle="plan_variant", hypothesis_id="h1", specific=("ast:stmt:select",)
    )
    assert made.sources[0]._queue(SimpleNamespace(theory=SimpleNamespace(hypotheses=(alone,)))) == []
    skipped = SimpleNamespace(
        engine="sqlite", oracle="plan_variant", hypothesis_id="h2",
        specific=("ast:stmt:select", "ast:clause:where"),
    )
    assert made.sources[0]._queue(SimpleNamespace(theory=SimpleNamespace(hypotheses=(skipped,)))) == []
