"""GLM tier routing, accounting and run configuration; no external requests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from surprise.baselines import pure_llm
from surprise.experiments import grid, loop
from surprise.harness.ledger import Ledger
from surprise.metrics.rq import _usd
from surprise.roles.cache import cache_key
from surprise.roles.constants import CAP_ENV, TIERS, as_dict
from surprise.roles.gateway import Gateway, TransportError
from surprise.roles.providers import EXTRA_TIERS
from surprise.roles.transport import DeepSeekTransport

MODEL = "z-ai/glm-5.3-flash"
PROFILE = {
    "model": MODEL,
    "base_url": "https://openrouter.ai/api/v1",
    "providers": ["sail-research/fp4", "open-inference/fp4", "sail-research/us"],
    "body": {
        "reasoning": {"effort": "medium"},
    },
}


@pytest.fixture
def wire(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "s19-test-credential")
    monkeypatch.setenv("OPENROUTER_API_KEY", "s19-unused-credential")
    monkeypatch.delenv(CAP_ENV, raising=False)
    state = SimpleNamespace(requests=[], status=200, content='{"prediction": "x"}')

    def handle(_transport, request):
        request.read()
        state.requests.append(request)
        body = {
            "choices": [{"message": {
                "content": state.content,
                "reasoning": "ignored",
                "reasoning_details": [{"type": "reasoning.text", "text": "ignored"}],
            }}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 22,
                      "completion_tokens_details": {"reasoning_tokens": 15}},
        }
        return httpx.Response(state.status, json=body, request=request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handle)
    return state


def _complete(transport, model=MODEL):
    return transport.complete(model=model, prompt="prompt", temperature=0.2,
                              max_tokens=100, role="implementer")


def _rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _manifest(out):
    with Ledger(out / "ledger.sqlite") as ledger:
        return ledger.run_manifest(ledger.run_ids()[0])


def test_transport_routes_mixed_models_and_preserves_deepseek_bytes(wire):
    assert EXTRA_TIERS == {"glm-flash": PROFILE}
    assert TIERS == {"fast": "deepseek-flash", "strong": "deepseek-v4-pro"}
    transport = DeepSeekTransport()
    try:
        for model in (TIERS["fast"], MODEL, TIERS["strong"], MODEL, TIERS["fast"]):
            reply = _complete(transport, model)
            assert (reply.text, reply.input_tokens, reply.output_tokens) == (wire.content, 11, 22)
            request = wire.requests[-1]
            expected = {"model": model, "messages": [{"role": "user", "content": "prompt"}],
                        "temperature": 0.2, "max_tokens": 100}
            if model == MODEL:
                expected.update(PROFILE["body"])
                expected["provider"] = {"only": [PROFILE["providers"][0]], "allow_fallbacks": False}
                url = "https://openrouter.ai/api/v1/chat/completions"
            else:
                url = "https://api.deepseek.com/v1/chat/completions"
            assert request.method == "POST"
            assert str(request.url) == url
            assert request.headers["authorization"] == "Bearer s19-test-credential"
            assert request.content == json.dumps(expected, ensure_ascii=False, separators=(",", ":")).encode()
    finally:
        transport.close_client()
    assert len(wire.requests) == 5


@pytest.mark.parametrize("status", [402, 429, 500])
def test_transport_keeps_http_status_and_hides_response(wire, status):
    wire.status = status
    transport = DeepSeekTransport(rate_limit_waits_s=())
    try:
        with pytest.raises(TransportError, match=f"^HTTPStatusError {status}$"):
            _complete(transport)
    finally:
        transport.close_client()


def test_transport_rejects_null_content(wire):
    wire.content = None
    transport = DeepSeekTransport()
    try:
        with pytest.raises(TransportError, match="^TypeError$"):
            _complete(transport)
    finally:
        transport.close_client()


def test_transport_requires_original_key_variable(wire, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    with pytest.raises(TransportError, match="DEEPSEEK_API_KEY is not set"):
        _complete(DeepSeekTransport())
    assert wire.requests == []


def test_gateway_separates_cache_and_records_forced_tier(tmp_path, wire):
    transport = DeepSeekTransport()
    cache = tmp_path / "cache"
    old = Gateway(cache_dir=cache, transport=transport)
    glm = Gateway(cache_dir=cache, ledger_path=tmp_path / "calls.jsonl",
                  tier="glm-flash", transport=transport)
    try:
        previous = old.call("implementer", "prompt", tier="fast", seed=3)
        reply = glm.call("implementer", "prompt", tier="fast", seed=3)
        cached = glm.call("conjecturer", "prompt", tier="strong", seed=3)
    finally:
        transport.close_client()
    assert previous.model == TIERS["fast"]
    assert reply.model == cached.model == MODEL
    assert reply.tier == cached.tier == "glm-flash"
    assert reply.key == cache_key("prompt", MODEL, 3) != previous.key
    assert (reply.source, cached.source) == ("network", "cache")
    assert len(wire.requests) == 2
    rows = _rows(tmp_path / "calls.jsonl")
    assert len(rows) == 2
    assert all(row["model"] == MODEL and row["tier"] == "glm-flash" for row in rows)
    assert glm.manifest() == {**old.manifest(), "tier": "glm-flash", "endpoint": PROFILE}
    assert old.manifest() == {"tiers": dict(TIERS), "max_calls": old.max_calls, "constants": as_dict()}
    assert Gateway(cache_dir=cache, tier="strong").manifest() == {**old.manifest(), "tier": "strong"}
    # A caller editing its manifest must not change a later request's endpoint.
    glm.manifest()["endpoint"]["providers"].clear()
    assert glm.manifest()["endpoint"] == PROFILE


@pytest.mark.parametrize("bad", ["medium", "glm", MODEL])
def test_unknown_tiers_still_fail(tmp_path, bad):
    with pytest.raises(ValueError):
        Gateway(cache_dir=tmp_path / "cache", tier=bad)


@pytest.mark.parametrize("kind", ["surprise", "pure_llm"])
def test_grid_passes_glm_tier_and_rejects_unknown(tmp_path, kind):
    arm = {"name": "glm", "kind": kind, "tier": "glm-flash",
           "llm": {"cache": "cache", "max_calls": "unlimited"}}
    if kind == "surprise":
        arm.update(engines=["duckdb"], llm={"roles": ["implementer"], "cache": "cache",
                                          "max_calls": "unlimited"})
    else:
        arm["engine"] = "duckdb"
    config = {"schema": 1, "name": "glm", "budget": {"minutes": 1}, "seeds": [1], "arms": [arm]}
    path = tmp_path / "grid.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    checked = grid.load_config(path)
    argv = grid.command_for(checked["arms"][0], out=tmp_path / "out", seed=1, rep=0)
    assert argv[argv.index("--llm-tier") + 1] == "glm-flash"
    for bad in ("medium", MODEL):
        arm["tier"] = bad
        path.write_text(json.dumps(config), encoding="utf-8")
        with pytest.raises(ValueError):
            grid.load_config(path)


@pytest.mark.parametrize("kind", ["loop", "pure"])
def test_cli_and_run_config_accept_glm_offline(tmp_path, wire, kind):
    out = tmp_path / kind
    argv = ["--out", str(out), "--seed", "1", "--max-experiments", "0",
            "--llm-tier", "glm-flash", "--llm-offline", "--llm-cache", str(tmp_path / "cache")]
    if kind == "loop":
        argv += ["--llm", "implementer", "--engine", "duckdb", "--oracle", "tlp"]
        assert loop.main(argv) == 0
        section = _manifest(out)["llm"]
        assert section["endpoint"] == PROFILE
        assert section["tiers"] == TIERS
    else:
        assert pure_llm.main(argv) == 0
        section = _manifest(out)["pure_llm"]
    assert section["tier"] == "glm-flash"
    assert json.loads((out / "config.json").read_text(encoding="utf-8"))["llm"]["tier"] == "glm-flash"
    assert wire.requests == []


def test_pure_llm_calls_use_glm_model(tmp_path, wire):
    out = tmp_path / "pure"
    pure_llm.run(out, seed=4, engine="duckdb", oracles=("tlp",), max_experiments=1,
                 max_calls=1, tier="glm-flash", cache=tmp_path / "cache")
    assert len(wire.requests) == 1
    assert json.loads(wire.requests[0].content)["model"] == MODEL
    rows = _rows(out / "llm" / "calls.jsonl")
    assert rows and all(row["model"] == MODEL and row["tier"] == "glm-flash" for row in rows)


def test_prices_are_dated_and_cost_glm_tokens():
    path = Path(__file__).resolve().parents[1] / "surprise/metrics/data/prices_openrouter.json"
    prices = json.loads(path.read_text(encoding="utf-8"))
    assert prices == {
        "retrieved": "2026-10-21",
        "source": "https://openrouter.ai/api/v1/models/z-ai/glm-5.3-flash/endpoints",
        "unit": "USD per 1M tokens",
        "models": {MODEL: {"providers": {
            "sail-research/fp4": {"input": 0.09, "output": 0.15, "input_cache_read": 0.0261},
            "open-inference/fp4": {"input": 0.041191, "output": 0.12, "input_cache_read": 0.00375},
            "sail-research/us": {"input": 0.09, "output": 0.15, "input_cache_read": 0.0261},
        }}},
        "grid": {MODEL: {"input": 0.09, "output": 0.15}},
    }
    assert _usd([{"model": MODEL, "input_tokens": 1_000_000, "output_tokens": 2_000_000}],
                prices["grid"]) == pytest.approx(0.39)
