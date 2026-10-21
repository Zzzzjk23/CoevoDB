"""Ordered provider retries, provenance and cache compatibility, entirely offline."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from llm.ledger import LLMLedger
from surprise.roles import transport as transport_module
from surprise.roles.constants import CAP_ENV, RATE_LIMIT_WAITS_S, RETRY_STATUSES, as_dict
from surprise.roles.gateway import Completion, Gateway, TransportError
from surprise.roles.providers import endpoint_for_model, endpoint_for_tier
from surprise.roles.transport import DeepSeekTransport

MODEL = "z-ai/glm-5.3-flash"
PROVIDERS = ["sail-research/fp4", "open-inference/fp4", "sail-research/us"]
ANSWER = '{"prediction": "provider answered"}'
LEDGER_KEYS = {"seq", "role", "tier", "model", "seed", "key", "prompt_sha256", "status",
               "source", "reason", "input_tokens", "output_tokens", "latency_s"}
CACHE_KEYS = {"key", "prompt_sha256", "model", "seed", "role", "tier", "prompt", "text",
              "input_tokens", "output_tokens", "temperature", "max_tokens", "created_at"}


@pytest.fixture
def wire(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "s19-offline-provider-credential")
    monkeypatch.delenv(CAP_ENV, raising=False)
    state = SimpleNamespace(requests=[], queues={}, down={}, sleeps=[], clock=0.0,
                            ledger=LLMLedger())
    monkeypatch.setattr(transport_module, "ledger", state.ledger)

    def handle(_transport, request):
        request.read()
        state.requests.append(request)
        state.clock += 0.25
        body = json.loads(request.content)
        provider = body.get("provider", {}).get("only", [None])[0]
        queue = state.queues.get(provider, [])
        status = queue.pop(0) if queue else state.down.get(provider, 200)
        if isinstance(status, Exception):
            raise status
        return httpx.Response(status, request=request, json={
            "choices": [{"message": {"content": ANSWER}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 22},
        })

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handle)
    return state


@pytest.fixture
def make_transport(wire):
    clients = []

    def make(**kwargs):
        kwargs.setdefault("sleep", wire.sleeps.append)
        client = DeepSeekTransport(**kwargs)
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.close_client()


def _complete(client, model=MODEL):
    return client.complete(model=model, prompt="prompt", temperature=0.2,
                           max_tokens=100, role="implementer")


def _asked(wire):
    return [json.loads(r.content).get("provider", {}).get("only", [None])[0]
            for r in wire.requests]


def _rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _event(wire, status, retries):
    assert len(wire.ledger._events) == 1
    event = wire.ledger._events[0]
    assert (event["status"], event["retries"]) == (status, retries)


def _retry(provider, status, attempt, wait):
    return (f"surprise.roles.transport: HTTP {status} for role implementer, model {MODEL} via {provider}; "
            f"retry {attempt}/4 in {wait:g} s")


def _switch(provider, nxt, status=503):
    return (f"surprise.roles.transport: HTTP {status} for role implementer, model {MODEL} via {provider}; "
            f"retries used up, switching to {nxt}")


def test_profiles_and_retry_manifest_are_detached():
    assert RETRY_STATUSES == [429, 503]
    manifest = as_dict()
    manifest["RETRY_STATUSES"].clear()
    assert as_dict()["RETRY_STATUSES"] == [429, 503]
    for get_profile, arg in ((endpoint_for_tier, "glm-flash"), (endpoint_for_model, MODEL)):
        profile = get_profile(arg)
        assert profile["providers"] == PROVIDERS
        assert profile["body"] == {"reasoning": {"effort": "low"}}
        profile["providers"].clear()
        profile["body"]["reasoning"]["effort"] = "high"
        assert get_profile(arg)["providers"] == PROVIDERS
        assert get_profile(arg)["body"] == {"reasoning": {"effort": "low"}}


def test_first_provider_503_then_success(wire, make_transport, capsys):
    wire.queues = {PROVIDERS[0]: [503, 200]}
    reply = _complete(make_transport())
    assert (reply.text, reply.input_tokens, reply.output_tokens, reply.provider) == (ANSWER, 11, 22, PROVIDERS[0])
    assert _asked(wire) == [PROVIDERS[0]] * 2
    assert wire.requests[0].content == wire.requests[1].content
    assert wire.sleeps == [10.0]
    assert capsys.readouterr().err.splitlines() == [_retry(PROVIDERS[0], 503, 1, 10)]
    _event(wire, "ok", 1)


def test_second_provider_restarts_waits_and_next_call_starts_at_first(wire, make_transport, capsys):
    first, second, _ = PROVIDERS
    wire.down = {first: 503}
    wire.queues = {second: [429, 200]}
    client = make_transport()
    assert _complete(client).provider == second
    assert _asked(wire) == [first] * 5 + [second] * 2
    assert wire.sleeps == RATE_LIMIT_WAITS_S + [10.0]
    assert capsys.readouterr().err.splitlines() == [
        *[_retry(first, 503, i, w) for i, w in enumerate(RATE_LIMIT_WAITS_S, 1)],
        _switch(first, second), _retry(second, 429, 1, 10),
    ]
    for request, provider in zip(wire.requests, _asked(wire)):
        expected = {"model": MODEL, "messages": [{"role": "user", "content": "prompt"}],
                    "temperature": 0.2, "max_tokens": 100, "reasoning": {"effort": "low"},
                    "provider": {"only": [provider], "allow_fallbacks": False}}
        assert request.content == json.dumps(expected, separators=(",", ":")).encode()
    _event(wire, "ok", 6)
    wire.down.clear()
    assert _complete(client).provider == first
    assert _asked(wire)[-1] == first
    assert wire.ledger._events[-1]["retries"] == 0


def test_third_provider_can_answer(wire, make_transport):
    first, second, third = PROVIDERS
    wire.down = {first: 503, second: 429}
    assert _complete(make_transport()).provider == third
    assert _asked(wire) == [first] * 5 + [second] * 5 + [third]
    assert wire.sleeps == RATE_LIMIT_WAITS_S * 2
    _event(wire, "ok", 10)


def test_all_providers_exhausted(wire, make_transport, capsys):
    wire.down = dict.fromkeys(PROVIDERS, 503)
    with pytest.raises(TransportError, match="^HTTPStatusError 503$"):
        _complete(make_transport())
    assert _asked(wire) == [p for p in PROVIDERS for _ in range(5)]
    assert wire.sleeps == RATE_LIMIT_WAITS_S * 3
    expected = []
    for index, provider in enumerate(PROVIDERS):
        expected.extend(_retry(provider, 503, i, w) for i, w in enumerate(RATE_LIMIT_WAITS_S, 1))
        if index < 2:
            expected.append(_switch(provider, PROVIDERS[index + 1]))
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.splitlines() == expected
    assert "s19-offline-provider-credential" not in captured.err
    assert ANSWER not in captured.err
    _event(wire, "error", 14)


@pytest.mark.parametrize("switched", [False, True])
def test_503_then_402_stops_without_further_switch(wire, make_transport, capsys, switched):
    current = PROVIDERS[int(switched)]
    if switched:
        wire.down = {PROVIDERS[0]: 503}
    wire.queues = {current: [503, 402, 200]}
    with pytest.raises(TransportError, match="^HTTPStatusError 402$"):
        _complete(make_transport())
    assert _asked(wire) == ([PROVIDERS[0]] * 5 if switched else []) + [current] * 2
    assert wire.sleeps == (RATE_LIMIT_WAITS_S if switched else []) + [10.0]
    assert capsys.readouterr().err.splitlines()[-1] == _retry(current, 503, 1, 10)
    _event(wire, "error", 6 if switched else 1)


@pytest.mark.parametrize("status", [429, 503])
@pytest.mark.parametrize("exhausted", [False, True])
def test_no_waits_switches_immediately(wire, make_transport, capsys, status, exhausted):
    wire.down = dict.fromkeys(PROVIDERS if exhausted else PROVIDERS[:1], status)
    client = make_transport(rate_limit_waits_s=())
    if exhausted:
        with pytest.raises(TransportError, match=f"^HTTPStatusError {status}$"):
            _complete(client)
    else:
        assert _complete(client).provider == PROVIDERS[1]
    assert _asked(wire) == (PROVIDERS if exhausted else PROVIDERS[:2])
    assert wire.sleeps == []
    assert capsys.readouterr().err.splitlines() == [
        _switch(PROVIDERS[i], PROVIDERS[i + 1], status) for i in range(2 if exhausted else 1)
    ]
    _event(wire, "error" if exhausted else "ok", 2 if exhausted else 1)


def test_switch_keeps_full_deadline(wire, make_transport, monkeypatch):
    def sleep(wait):
        wire.sleeps.append(wait)
        wire.clock += wait

    monkeypatch.setattr(transport_module, "time", SimpleNamespace(monotonic=lambda: wire.clock, sleep=sleep))
    wire.down = {PROVIDERS[0]: 503}
    wire.queues = {PROVIDERS[1]: [503, 200]}
    assert _complete(make_transport(deadline_s=0.5, sleep=sleep)).provider == PROVIDERS[1]
    assert wire.clock == sum(RATE_LIMIT_WAITS_S) + 10.0 + 7 * 0.25
    _event(wire, "ok", 6)


def test_gateway_records_and_replays_answering_provider(wire, make_transport, tmp_path):
    wire.down = {PROVIDERS[0]: 503}
    cache = tmp_path / "cache"
    path = tmp_path / "calls.jsonl"
    gateway = Gateway(cache_dir=cache, ledger_path=path, max_calls=1,
                      tier="glm-flash", transport=make_transport())
    reply = gateway.call("implementer", "prompt", tier="fast", seed=1)
    assert (reply.status, reply.source, reply.provider) == ("ok", "network", PROVIDERS[1])
    entry_path, = cache.rglob("*.json")
    entry = json.loads(entry_path.read_text(encoding="utf-8"))
    assert set(entry) == CACHE_KEYS | {"provider"}
    assert entry["provider"] == PROVIDERS[1]
    assert set(_rows(path)[0]) == LEDGER_KEYS | {"provider"}
    assert _rows(path)[0]["provider"] == PROVIDERS[1]
    _event(wire, "ok", 5)
    assert gateway.network_calls == gateway.totals()["network"] == 1
    assert gateway.totals()["by_role"]["implementer"]["input_tokens"] == 11
    blocked = gateway.call("implementer", "other", tier="fast", seed=1)
    assert blocked.status == "blocked" and blocked.provider is None
    assert set(_rows(path)[1]) == LEDGER_KEYS
    replay = Gateway(cache_dir=cache, ledger_path=path, tier="glm-flash")
    cached = replay.call("implementer", "prompt", tier="fast", seed=1)
    assert (cached.source, cached.provider) == ("cache", PROVIDERS[1])
    assert _rows(path)[2]["provider"] == PROVIDERS[1]
    assert replay.network_calls == 0
    assert len(wire.requests) == 6
    assert len(wire.ledger._events) == 1


@pytest.mark.parametrize("provider", [None, 7, [], {}])
def test_cache_without_string_provider_returns_none(wire, make_transport, tmp_path, provider):
    gateway = Gateway(cache_dir=tmp_path, tier="glm-flash", transport=make_transport())
    gateway.call("implementer", "prompt", tier="fast", seed=1)
    entry_path, = tmp_path.rglob("*.json")
    entry = json.loads(entry_path.read_text(encoding="utf-8"))
    if provider is None:
        del entry["provider"]
    else:
        entry["provider"] = provider
    entry_path.write_text(json.dumps(entry), encoding="utf-8")
    reply = gateway.call("implementer", "prompt", tier="fast", seed=1)
    assert reply.source == "cache" and reply.provider is None
    assert len(wire.requests) == 1


def test_deepseek_and_legacy_completion_preserve_keys(wire, make_transport, tmp_path):
    assert Completion(ANSWER).provider is None
    for name, transport in (("deepseek", make_transport()), ("legacy", SimpleNamespace(
        complete=lambda **kwargs: SimpleNamespace(text=ANSWER, input_tokens=11, output_tokens=22),
    ))):
        cache = tmp_path / name
        path = tmp_path / f"{name}.jsonl"
        gateway = Gateway(cache_dir=cache, ledger_path=path, transport=transport)
        for _ in range(2):
            reply = gateway.call("implementer", "prompt", tier="fast", seed=1)
            assert reply.status == "ok" and reply.provider is None
        assert [r["source"] for r in _rows(path)] == ["network", "cache"]
        assert all(set(row) == LEDGER_KEYS for row in _rows(path))
        entry_path, = cache.rglob("*.json")
        assert set(json.loads(entry_path.read_text(encoding="utf-8"))) == CACHE_KEYS
    assert _asked(wire) == [None]


@pytest.mark.parametrize("status", [429, 503])
def test_deepseek_without_waits_never_switches(wire, make_transport, capsys, status):
    wire.down = {None: status}
    with pytest.raises(TransportError, match=f"^HTTPStatusError {status}$"):
        _complete(make_transport(rate_limit_waits_s=()), "deepseek-flash")
    assert _asked(wire) == [None]
    assert wire.sleeps == []
    assert capsys.readouterr() == ("", "")
    _event(wire, "error", 0)


@pytest.mark.parametrize("status", ["error", "miss", "blocked"])
def test_gateway_failures_have_no_provider(wire, make_transport, tmp_path, status):
    wire.down = dict.fromkeys(PROVIDERS, 503)
    path = tmp_path / "calls.jsonl"
    gateway = Gateway(cache_dir=tmp_path / "cache", ledger_path=path, tier="glm-flash",
                      max_calls=0 if status == "blocked" else 1,
                      transport=None if status == "miss" else make_transport(rate_limit_waits_s=()))
    reply = gateway.call("implementer", "prompt", tier="fast", seed=1)
    assert reply.status == status and reply.provider is None
    assert set(_rows(path)[0]) == LEDGER_KEYS
    assert list((tmp_path / "cache").rglob("*.json")) == []
