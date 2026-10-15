"""Exploration prior: scripted transport, Brier calibration, Hunter U. No network."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from surprise.features.phi import make_phi
from surprise.features.units import _CONSTRUCTS
from surprise.gates import s10_cases as C
from surprise.gates.s10 import (
    Script,
    context,
    prior_event,
    prior_reply,
    price_of,
)
from surprise.hunter import Hunter
from surprise.hunter import scoring as scoring
from surprise.roles.constants import (
    PRIOR_INITIAL_WEIGHT,
    PRIOR_MAX_TOKENS,
    PRIOR_MIN_SETTLED,
    PRIOR_STRENGTH,
    PRIOR_TEMPERATURE,
    PRIOR_TIER,
    PRIOR_UNITS_PER_CALL,
    TIERS,
)
from surprise.roles.prior import (
    _CONSTRUCT_PATTERNS,
    calibrated_weight,
    prior_evidence,
    prior_prompt,
)
from surprise.roles.runtime import build_roles
from surprise.roles.source import Hit
from surprise.theory.constants import RESIDUAL_PRIOR_FAILS, RESIDUAL_PRIOR_TESTS
from surprise.theory.workbench import Workbench

LAYERS = {"ast": "ok", "plan": "ok", "data": "ok"}
_UNIT_RE = re.compile(r"^UNIT (\S+)$", flags=re.MULTILINE)
_IDS = ("loop-s", "record_id", "hypothesis_id", "run_id")


class FakeReader:
    def __init__(self, hits: list[Hit] | None = None) -> None:
        self.hits = list(hits or [])
        self.calls: list[dict[str, Any]] = []

    def grep(self, pattern: str, *, under: str = "", suffixes=None, max_hits: int = 50):
        self.calls.append(
            {"pattern": pattern, "under": under, "suffixes": suffixes, "max_hits": max_hits}
        )
        return tuple(self.hits[:max_hits])


class Boom:
    def complete(self, *, model: str, prompt: str, temperature: float, max_tokens: int, role: str):
        raise RuntimeError("network")


class _FixedPhi:
    def extract(self, case):
        return make_phi(case.engine, ("ast:stmt:select",), LAYERS)

    def close(self) -> None:
        return None


def _units_in(prompt: str) -> list[str]:
    return _UNIT_RE.findall(prompt)


def _corpus(path: Path) -> Path:
    path.write_text(
        json.dumps(
            [
                {
                    "setup_sqls": ["CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1), (2)"],
                    "query": "SELECT a FROM t WHERE a > 0",
                    "source": "s10-prior",
                    "engine": "duckdb",
                    "tags": [],
                }
            ]
        ),
        encoding="utf-8",
    )
    return path


def _role(tmp: Path, script: Any, *, max_calls: int = 50, readers: Any = None):
    from surprise.roles.prior import build

    root = tmp / "run"
    ctx = context(
        root,
        script,
        engines=("datafusion",),
        oracles=("cross_dbms",),
        max_calls=max_calls,
        readers={} if readers is None else readers,
    )
    return build(ctx)


def _book(tmp: Path) -> list[dict[str, Any]]:
    path = tmp / "run" / "llm" / "prior.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_construct_patterns_cover_units() -> None:
    names = {name for name, _needles in _CONSTRUCTS} | {"plain"}
    assert set(_CONSTRUCT_PATTERNS) == names
    assert _CONSTRUCT_PATTERNS["plain"] is None
    assert "EXCEPT ALL" in _CONSTRUCT_PATTERNS["set_op_all"]
    assert "OVER" in _CONSTRUCT_PATTERNS["window"]
    assert "ASOF" in _CONSTRUCT_PATTERNS["asof_join"]


def test_evidence_format_determinism_and_empty_readers() -> None:
    units = [
        "datafusion|cross_dbms|window|window|plain",
        "datafusion|cross_dbms|set_op_all|join|dups",
        "duckdb|tlp|join|join|plain",
        "datafusion|cross_dbms|window|sort|dups",
        "datafusion|cross_dbms|plain|scan|plain",
    ]
    assert prior_evidence(units, {}) == ()
    assert prior_evidence(units, None) == ()
    df_hits = [
        Hit(path="dev/changelog/11.0.0.md", line=12, text="  window function crash  "),
        Hit(path="dev/changelog/11.0.0.md", line=40, text="OVER (ORDER BY a) " + ("x" * 250)),
    ]
    dk_hits = [Hit(path="test/issues/general/j.test", line=3, text="INNER JOIN t")]
    readers = {"datafusion": FakeReader(df_hits), "duckdb": FakeReader(dk_hits)}
    first = prior_evidence(units, readers)
    df_calls = list(readers["datafusion"].calls)
    dk_calls = list(readers["duckdb"].calls)
    second = prior_evidence(units, readers)
    assert first == second
    assert first
    assert all(line.startswith("EVIDENCE ") for line in first)
    assert not any(
        word in line for line in first for word in ("manual_findings", "FAMILY_LEDGER", "recall_repros")
    )
    window_lines = [line for line in first if line.startswith("EVIDENCE datafusion ")]
    assert window_lines[0] == "EVIDENCE datafusion dev/changelog/11.0.0.md:12 window function crash"
    clipped = window_lines[1].split(" ", 3)[-1]
    assert len(clipped) == 200 and clipped.startswith("OVER (ORDER BY a)")
    assert any(line.startswith("EVIDENCE duckdb test/issues/general/j.test:3") for line in first)
    engines = [line.split()[1] for line in first]
    assert engines == sorted(engines)
    unders = {call["under"] for call in df_calls}
    assert unders == {"dev/changelog"}
    assert all(call["suffixes"] == (".md",) for call in df_calls)
    assert all(call["max_hits"] == C.CONSTANTS["PRIOR_EVIDENCE_PER_CONSTRUCT"] for call in df_calls)
    assert all(call["pattern"].startswith("(?i)") for call in df_calls)
    assert len(df_calls) == 2
    assert len(dk_calls) == 1
    assert dk_calls[0]["under"] == "test/issues"
    assert dk_calls[0]["suffixes"] == (".test",)


def test_prompt_is_pure_and_has_no_ids() -> None:
    units = (
        "datafusion|cross_dbms|set_op_all|join|dups",
        "datafusion|cross_dbms|window|window|plain",
    )
    evidence = (
        "EVIDENCE datafusion dev/changelog/10.0.0.md:4 UNION ALL",
        "EVIDENCE duckdb test/issues/general/t.test:1 OVER (",
    )
    text = prior_prompt(units, evidence)
    assert text == prior_prompt(list(units), list(evidence))
    assert _units_in(text) == list(units)
    for line in evidence:
        assert line in text.splitlines()
    assert "one JSON object" in text
    assert "p_fail" in text
    assert "engine|oracle|construct|plan class|data class" in text
    assert "1 time in 100" in text
    lower = text.lower()
    assert "defect" in lower or "fail" in lower
    for needle in _IDS:
        assert needle not in text
    assert not re.search(r"[A-Za-z]:[\\/]", text)
    assert "C:\\" not in text and "D:\\" not in text
    assert "/home/" not in text and "/Users/" not in text


def test_prepare_sorts_batches_and_one_call_per_choice(tmp_path: Path) -> None:
    script = Script({"prior": prior_reply})
    role = _role(tmp_path, script)
    wb = Workbench.create(tmp_path / "theory")
    units = list(C.PRIOR_UNITS)
    try:
        role.prepare(wb, units, index=1)
        role.prepare(wb, units, index=1)
        assert len(script.calls) == 1
        first = script.calls[0]
        assert _units_in(first["prompt"]) == sorted(units)[:PRIOR_UNITS_PER_CALL]
        assert first["model"] == TIERS[PRIOR_TIER]
        assert first["temperature"] == PRIOR_TEMPERATURE
        assert first["max_tokens"] == PRIOR_MAX_TOKENS
        assert first["role"] == "prior"
        role.prepare(wb, units, index=2)
        assert len(script.calls) == 2
        assert _units_in(script.calls[1]["prompt"]) == sorted(units)[PRIOR_UNITS_PER_CALL:]
        role.prepare(wb, units, index=3)
        assert len(script.calls) == 2
        k = PRIOR_STRENGTH
        w0 = PRIOR_INITIAL_WEIGHT
        ref = RESIDUAL_PRIOR_FAILS / RESIDUAL_PRIOR_TESTS
        for unit in units:
            p_eff = w0 * price_of(unit) + (1 - w0) * ref
            got = role.pseudo(unit)
            assert got is not None
            assert got[0] == pytest.approx(p_eff * k)
            assert got[1] == pytest.approx(k)
        assert role.pseudo("datafusion|tlp|plain|scan|plain") is None
        assert set(role.priced()) == set(units)
    finally:
        role.close()


def test_asked_units_are_not_asked_again(tmp_path: Path) -> None:
    odd = list(C.PRIOR_UNITS[:3])
    script = Script(
        {
            "prior": {
                "prediction": [
                    {"unit": odd[0], "p_fail": 1.5, "why": "x"},
                    {"unit": odd[1], "p_fail": "high", "why": "x"},
                ]
            }
        }
    )
    role = _role(tmp_path, script)
    wb = Workbench.create(tmp_path / "theory")
    try:
        role.prepare(wb, odd, index=1)
        assert role.pseudo(odd[0]) is None and role.pseudo(odd[1]) is None
        role.prepare(wb, odd, index=2)
        assert len(script.calls) == 1
        assert role.report()["asked"] == 3
        assert role.report()["priced"] == 0
    finally:
        role.close()


def test_bad_reply_drops_out_of_range_non_numeric_and_unasked(tmp_path: Path) -> None:
    odd = list(C.PRIOR_UNITS[:3])
    script = Script(
        {
            "prior": {
                "prediction": [
                    {"unit": odd[0], "p_fail": 1.5, "why": "x"},
                    {"unit": odd[1], "p_fail": "high", "why": "x"},
                    {"unit": "datafusion|tlp|nowhere|scan|plain", "p_fail": 0.2, "why": "x"},
                    {"unit": odd[2], "p_fail": 0.0, "why": "x"},
                    {"unit": odd[2], "p_fail": 0.9, "why": "second"},
                    {"unit": odd[1], "p_fail": True, "why": "bool"},
                ]
            }
        }
    )
    role = _role(tmp_path, script)
    wb = Workbench.create(tmp_path / "theory")
    try:
        role.prepare(wb, odd, index=1)
        assert role.pseudo(odd[0]) is None
        assert role.pseudo(odd[1]) is None
        assert role.pseudo(odd[2]) is not None
        assert role.priced()[odd[2]] == 0.0
        assert role.pseudo("datafusion|tlp|nowhere|scan|plain") is None
        rows = _book(tmp_path)
        unpriced = {row["unit"]: row["reason"] for row in rows if row.get("type") == "unpriced"}
        assert unpriced[odd[0]] == "out_of_range"
        assert unpriced[odd[1]] == "not_number"
        assert "datafusion|tlp|nowhere|scan|plain" not in unpriced
    finally:
        role.close()


def test_non_string_unit_in_reply_is_skipped(tmp_path: Path) -> None:
    odd = list(C.PRIOR_UNITS[:3])
    script = Script(
        {
            "prior": {
                "prediction": [
                    {"unit": ["a"], "p_fail": 0.1, "why": "list"},
                    {"unit": {"name": odd[0]}, "p_fail": 0.2, "why": "dict"},
                    {"unit": 3, "p_fail": 0.3, "why": "number"},
                    {"unit": odd[2], "p_fail": 0.4, "why": "ok"},
                ]
            }
        }
    )
    role = _role(tmp_path, script)
    wb = Workbench.create(tmp_path / "theory")
    try:
        role.prepare(wb, odd, index=1)
        assert role.priced() == {odd[2]: 0.4}
        assert role.pseudo(odd[0]) is None
        assert role.pseudo(odd[1]) is None
        assert role.pseudo(odd[2]) is not None
        unpriced = {row["unit"]: row["reason"] for row in _book(tmp_path) if row.get("type") == "unpriced"}
        assert set(unpriced) == {odd[0], odd[1]}
    finally:
        role.close()


def test_rejected_blocked_miss_error_leave_batch_unpriced(tmp_path: Path) -> None:
    odd = list(C.PRIOR_UNITS[:2])
    wb = Workbench.create(tmp_path / "theory")

    rejected = Script({"prior": "not-json"})
    role_r = _role(tmp_path / "rej", rejected)
    try:
        role_r.prepare(wb, odd, index=1)
        assert role_r.pseudo(odd[0]) is None and role_r.pseudo(odd[1]) is None
        assert rejected.calls and role_r.report()["asked"] == 2
        assert any(row.get("type") == "call" and row.get("status") == "rejected" for row in _book(tmp_path / "rej"))
    finally:
        role_r.close()

    blocked = Script({"prior": prior_reply})
    role_b = _role(tmp_path / "blk", blocked, max_calls=0)
    try:
        role_b.prepare(wb, odd, index=1)
        assert blocked.calls == []
        assert role_b.pseudo(odd[0]) is None
        assert role_b.report()["asked"] == 2
        assert any(row.get("status") == "blocked" for row in _book(tmp_path / "blk") if row.get("type") == "call")
    finally:
        role_b.close()

    from surprise.roles.base import RoleContext
    from surprise.roles.conjecturer import ConjectureBook
    from surprise.roles.gateway import Gateway
    from surprise.roles.prior import build
    from surprise.features import extract, default_registry

    miss_root = tmp_path / "miss"
    llm = miss_root / "llm"
    llm.mkdir(parents=True)
    gw = Gateway(cache_dir=miss_root / "cache", ledger_path=llm / "calls.jsonl", max_calls=10, transport=None)
    ctx = RoleContext(
        gateway=gw,
        book=ConjectureBook(llm / "conjectures.jsonl"),
        extract=extract,
        registry=default_registry(),
        readers={},
        engines=("datafusion",),
        oracles=("cross_dbms",),
        seed=0,
        run_dir=miss_root,
        llm_dir=llm,
    )
    role_m = build(ctx)
    try:
        role_m.prepare(wb, odd, index=1)
        assert role_m.pseudo(odd[0]) is None
        miss_rows = [
            json.loads(line)
            for line in (llm / "prior.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert any(row.get("status") == "miss" for row in miss_rows if row.get("type") == "call")
    finally:
        role_m.close()

    err_root = tmp_path / "err"
    llm_e = err_root / "llm"
    llm_e.mkdir(parents=True)
    gw_e = Gateway(cache_dir=err_root / "cache", ledger_path=llm_e / "calls.jsonl", max_calls=10, transport=Boom())
    ctx_e = RoleContext(
        gateway=gw_e,
        book=ConjectureBook(llm_e / "conjectures.jsonl"),
        extract=extract,
        registry=default_registry(),
        readers={},
        engines=("datafusion",),
        oracles=("cross_dbms",),
        seed=0,
        run_dir=err_root,
        llm_dir=llm_e,
    )
    role_e = build(ctx_e)
    try:
        role_e.prepare(wb, odd, index=1)
        assert role_e.pseudo(odd[0]) is None
        err_rows = [
            json.loads(line)
            for line in (llm_e / "prior.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert any(row.get("status") == "error" for row in err_rows if row.get("type") == "call")
    finally:
        role_e.close()


def test_pseudo_weight_initial_calibrated_and_zero_reference() -> None:
    assert calibrated_weight(0.0, 0.0) == 1.0
    assert calibrated_weight(0.25, 0.0) == 0.0
    assert calibrated_weight(0.0, 0.5) == 1.0
    assert calibrated_weight(0.25, 0.5) == pytest.approx(0.5)
    assert calibrated_weight(1.0, 0.1) == 0.0
    ref = RESIDUAL_PRIOR_FAILS / RESIDUAL_PRIOR_TESTS
    minimum = PRIOR_MIN_SETTLED
    want_ref = (minimum // 2 * (1 - ref) ** 2 + minimum // 2 * ref ** 2) / minimum
    want_w = max(0.0, min(1.0, 1.0 - 0.25 / want_ref))
    assert calibrated_weight(0.25, want_ref) == pytest.approx(want_w)


def test_observe_settles_only_unexplored_priced_valid(tmp_path: Path) -> None:
    script = Script({"prior": prior_reply})
    role = _role(tmp_path, script)
    wb = Workbench.create(tmp_path / "theory")
    units = list(C.PRIOR_UNITS)
    unit = next(u for u in units if u.split("|")[2] == "set_op_all")
    w0 = PRIOR_INITIAL_WEIGHT
    k = PRIOR_STRENGTH
    ref = RESIDUAL_PRIOR_FAILS / RESIDUAL_PRIOR_TESTS
    minimum = PRIOR_MIN_SETTLED
    try:
        role.prepare(wb, units, index=1)
        role.observe(prior_event(unit, "invalid", seq=900))
        role.observe(prior_event(unit, "pass", zone="confirmed", seq=901))
        role.observe(prior_event("datafusion|tlp|plain|scan|plain", "pass", seq=902))
        assert role.brier()["settled"] == 0
        assert role.weight() == pytest.approx(w0)
        for i in range(minimum - 1):
            role.observe(prior_event(unit, "pass", seq=i + 1))
        assert role.weight() == pytest.approx(w0)
        role.observe(prior_event(unit, "pass", seq=minimum))
        brier = role.brier()
        p = price_of(unit)
        assert brier["settled"] == minimum
        assert brier["llm"] == pytest.approx(p * p)
        assert brier["reference"] == pytest.approx(ref * ref)
        assert role.weight() == pytest.approx(0.0)
        assert role.pseudo(unit)[0] == pytest.approx(ref * k)
    finally:
        role.close()

    useful = Script({"prior": {"prediction": [{"unit": unit, "p_fail": 0.5, "why": "x"}]}})
    role3 = _role(tmp_path / "useful", useful)
    try:
        role3.prepare(wb, [unit], index=1)
        for i in range(minimum):
            role3.observe(prior_event(unit, "fail" if i % 2 == 0 else "pass", seq=i + 1))
        b3 = role3.brier()
        want_ref = (minimum // 2 * (1 - ref) ** 2 + minimum // 2 * ref ** 2) / minimum
        want_w = calibrated_weight(0.25, want_ref)
        assert b3["llm"] == pytest.approx(0.25)
        assert b3["reference"] == pytest.approx(want_ref)
        assert role3.weight() == pytest.approx(want_w)
    finally:
        role3.close()


def test_book_step_report_manifest(tmp_path: Path) -> None:
    script = Script({"prior": prior_reply})
    role = _role(tmp_path, script)
    wb = Workbench.create(tmp_path / "theory")
    units = list(C.PRIOR_UNITS[:4])
    try:
        role.prepare(wb, units, index=1)
        unit = sorted(units)[0]
        role.observe(prior_event(unit, "pass", seq=1))
        step = role.step()
        assert list(step) == ["priced", "settled", "weight"]
        assert step["priced"] == sorted(units)
        assert step["settled"] == 1
        assert step["weight"] == pytest.approx(PRIOR_INITIAL_WEIGHT)
        again = role.step()
        assert again["priced"] == [] and again["settled"] == 0
        report = role.report()
        assert report["priced"] == 4 and report["asked"] == 4 and report["calls"] == 1
        assert report["brier"]["settled"] == 1
        manifest = role.manifest()
        assert manifest == {
            "reference_rate": RESIDUAL_PRIOR_FAILS / RESIDUAL_PRIOR_TESTS,
            "strength": PRIOR_STRENGTH,
        }
        types = {row.get("type") for row in _book(tmp_path)}
        assert {"call", "price", "settle"} <= types
        for row in _book(tmp_path):
            assert "latency" not in row and "input_tokens" not in row and "output_tokens" not in row
    finally:
        role.close()


def test_build_roles_prior_is_the_plugin_and_hunter_moves_u(tmp_path: Path) -> None:
    script = Script({"prior": prior_reply})
    made = build_roles(
        {
            "roles": ["prior"],
            "cache": str(tmp_path / "cache"),
            "max_calls": 20,
            "network": False,
            "transport": script,
        },
        run_dir=tmp_path / "run",
        extract=lambda case: make_phi(case.engine, ("ast:stmt:select",), LAYERS),
        registry=None,
        engines=("duckdb",),
        seed=0,
        oracles=("plan_variant",),
    )
    try:
        role = made.prior
        assert role is not None
        assert role.name == "prior"
        assert made.plugins["prior"] is role
        wb = Workbench.create(tmp_path / "theory")
        corpus = _corpus(tmp_path / "corpus.json")
        hunt = Hunter(
            engines=("duckdb",),
            oracles=("plan_variant",),
            seed=3,
            corpus_path=corpus,
            extractor=_FixedPhi(),
            prior=role,
        )
        try:
            choice = hunt.choose(wb)
            assert choice is not None
            assert script.calls
            assert role.priced()
            phi = make_phi("duckdb", ("ast:stmt:select",), LAYERS)
            plain = scoring.score(wb, phi, "plan_variant", beta=1.0, probes={}, units=frozenset())
            primed = scoring.score(
                wb, phi, "plan_variant", beta=1.0, probes={}, units=frozenset(), prior=role
            )
            assert plain.prediction.zone == "unexplored"
            assert role.pseudo(primed.prediction.unit) is not None
            assert primed.U > plain.U
            if choice.scored.prediction.zone == "unexplored":
                assert role.pseudo(choice.scored.prediction.unit) is not None
                assert choice.scored.U > scoring.score(
                    wb,
                    choice.scored.phi,
                    choice.scored.candidate.oracle,
                    beta=1.0,
                    probes={},
                    units=frozenset(),
                ).U
        finally:
            hunt.close()
    finally:
        made.close()
