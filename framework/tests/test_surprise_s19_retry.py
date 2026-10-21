"""HTTP 429/503 backoff stays inside one accounted call; requests and waits are offline."""

from __future__ import annotations

import contextlib
import io
import json
from types import SimpleNamespace

import httpx
import pytest

from llm.ledger import LLMLedger
from surprise.roles import transport as transport_module
from surprise.roles.constants import CAP_ENV, RATE_LIMIT_WAITS_S, as_dict
from surprise.roles.gateway import Gateway, TransportError
from surprise.roles.transport import DeepSeekTransport

MODEL = "z-ai/glm-5.3-flash"
PROVIDERS = ["sail-research/fp4", "open-inference/fp4", "sail-research/us"]
ANSWER = '{"prediction": "retry succeeded"}'
RETRY_LINE = (
    "surprise.roles.transport: HTTP {status} for role {role}, model {model}; "
    "retry {attempt}/{retries} in {wait:g} s"
)
RETRY_LINE_VIA = (
    "surprise.roles.transport: HTTP {status} for role {role}, model {model} via {provider}; "
    "retry {attempt}/{retries} in {wait:g} s"
)
SWITCH_LINE = (
    "surprise.roles.transport: HTTP {status} for role {role}, model {model} via {provider}; "
    "retries used up, switching to {next}"
)


@pytest.fixture
def wire(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "s19-offline-credential")
    monkeypatch.delenv(CAP_ENV, raising=False)
    state = SimpleNamespace(
        requests=[], queue=[], status=200, content=ANSWER, missing=False,
        sleeps=[], ledger=LLMLedger(), clock=0.0,
    )
    monkeypatch.setattr(transport_module, "ledger", state.ledger)

    def handle(_transport, request):
        request.read()
        state.requests.append(request)
        state.clock += 0.25
        status = state.queue.pop(0) if state.queue else state.status
        if isinstance(status, Exception):
            raise status
        message = {} if state.missing else {"content": state.content}
        return httpx.Response(status, request=request, json={
            "choices": [{"message": message}],
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


def _complete(client, model=MODEL, role="implementer"):
    return client.complete(model=model, prompt="prompt", temperature=0.2,
                           max_tokens=100, role=role)


def _lines(waits, *, model=MODEL, role="implementer", retries=None, status=429, provider=PROVIDERS[0]):
    template = RETRY_LINE_VIA if model == MODEL else RETRY_LINE
    return [template.format(status=status, role=role, model=model, provider=provider, attempt=i,
                              retries=len(waits) if retries is None else retries, wait=wait)
            for i, wait in enumerate(waits, 1)]


def _exhausted_lines(waits):
    lines = []
    for index, provider in enumerate(PROVIDERS):
        lines.extend(_lines(waits, provider=provider))
        if index + 1 < len(PROVIDERS):
            lines.append(SWITCH_LINE.format(status=429, role="implementer", model=MODEL,
                                          provider=provider, next=PROVIDERS[index + 1]))
    return lines


def _event(wire, status, retries):
    assert len(wire.ledger._events) == 1
    event = wire.ledger._events[0]
    assert (event["status"], event["retries"]) == (status, retries)
    assert event["agent"] == "surprise.roles.implementer"
    assert event["event"] == "implementer"
    return event


def test_wait_configuration_is_detached_float_tuple(make_transport):
    assert RATE_LIMIT_WAITS_S == [10.0, 30.0, 60.0, 120.0]
    default = make_transport()
    assert default.rate_limit_waits_s == (10.0, 30.0, 60.0, 120.0)
    assert type(default.rate_limit_waits_s) is tuple
    assert all(type(wait) is float for wait in default.rate_limit_waits_s)
    waits = [1, 2]
    custom = make_transport(rate_limit_waits_s=waits)
    waits.clear()
    assert custom.rate_limit_waits_s == (1.0, 2.0)
    assert all(type(wait) is float for wait in custom.rate_limit_waits_s)
    manifest = as_dict()
    manifest["RATE_LIMIT_WAITS_S"].clear()
    assert as_dict()["RATE_LIMIT_WAITS_S"] == RATE_LIMIT_WAITS_S


@pytest.mark.parametrize("model", [MODEL, "deepseek-flash", "deepseek-v4-pro"])
@pytest.mark.parametrize("status", [429, 503])
def test_two_rate_limits_then_success_keep_request_and_record_once(wire, make_transport, model, status):
    wire.queue = [status, status, 200]
    stderr = io.StringIO()

    def sleep(wait):
        # The diagnostic must already be written when the wait starts.
        wire.sleeps.append(wait)
        assert stderr.getvalue().splitlines() == _lines(
            wire.sleeps, model=model, retries=len(RATE_LIMIT_WAITS_S), status=status)

    client = make_transport(sleep=sleep)
    with contextlib.redirect_stderr(stderr):
        reply = _complete(client, model)
    assert (reply.text, reply.input_tokens, reply.output_tokens) == (ANSWER, 11, 22)
    assert wire.sleeps == [10.0, 30.0]
    assert len(wire.requests) == 3
    expected = {"model": model, "messages": [{"role": "user", "content": "prompt"}],
                "temperature": 0.2, "max_tokens": 100}
    if model == MODEL:
        expected.update(reasoning={"effort": "medium"},
                        provider={"only": [PROVIDERS[0]], "allow_fallbacks": False})
        url = "https://openrouter.ai/api/v1/chat/completions"
    else:
        url = "https://api.deepseek.com/v1/chat/completions"
    for request in wire.requests:
        assert request.method == "POST"
        assert str(request.url) == url
        assert request.content == json.dumps(expected, ensure_ascii=False, separators=(",", ":")).encode()
        assert request.headers["authorization"] == "Bearer s19-offline-credential"
    event = _event(wire, "ok", 2)
    assert (event["input_tokens"], event["output_tokens"]) == (11, 22)


@pytest.mark.parametrize("waits", [None, (), (0.5,)])
def test_exhausted_rate_limits_keep_error_and_actual_retry_count(wire, make_transport, capsys, waits):
    client = make_transport(rate_limit_waits_s=waits)
    wire.status = 429
    with pytest.raises(TransportError, match="^HTTPStatusError 429$"):
        _complete(client)
    expected = RATE_LIMIT_WAITS_S if waits is None else list(waits)
    attempts = len(PROVIDERS) * (len(expected) + 1)
    assert len(wire.requests) == attempts
    assert wire.sleeps == expected * len(PROVIDERS)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.splitlines() == _exhausted_lines(expected)
    assert "s19-offline-credential" not in captured.err
    assert ANSWER not in captured.err
    _event(wire, "error", attempts - 1)


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404, 500, 502])
def test_other_http_statuses_are_not_retried(wire, make_transport, capsys, status):
    wire.status = status
    with pytest.raises(TransportError, match=f"^HTTPStatusError {status}$"):
        _complete(make_transport())
    assert len(wire.requests) == 1
    assert wire.sleeps == []
    assert capsys.readouterr() == ("", "")
    _event(wire, "error", 0)


@pytest.mark.parametrize("kind,reason", [
    ("connection", "ConnectError"), ("deadline", "DeadlineExceeded"),
    ("null", "TypeError"), ("missing", "KeyError"),
])
def test_other_failures_are_not_retried(wire, make_transport, capsys, kind, reason):
    if kind == "connection":
        wire.queue = [httpx.ConnectError("private failure details")]
    elif kind == "deadline":
        wire.queue = [TransportError("DeadlineExceeded")]
    elif kind == "null":
        wire.content = None
    else:
        wire.missing = True
    with pytest.raises(TransportError, match=f"^{reason}$"):
        _complete(make_transport())
    assert len(wire.requests) == 1
    assert wire.sleeps == []
    assert capsys.readouterr() == ("", "")
    _event(wire, "error", 0)


def test_non_rate_error_after_retry_stops_and_records_retries(wire, make_transport, capsys):
    wire.queue = [429, 402, 200]
    with pytest.raises(TransportError, match="^HTTPStatusError 402$"):
        _complete(make_transport())
    assert len(wire.requests) == 2
    assert wire.sleeps == [10.0]
    assert capsys.readouterr().err.splitlines() == _lines([10.0], retries=4)
    _event(wire, "error", 1)


def test_retry_gets_full_deadline_after_wait(wire, make_transport, monkeypatch):
    def sleep(wait):
        wire.sleeps.append(wait)
        wire.clock += wait

    monkeypatch.setattr(transport_module, "time", SimpleNamespace(
        monotonic=lambda: wire.clock, sleep=sleep))
    wire.queue = [429, 429, 200]
    # Each request takes 0.25 s on the fake clock; each wait exceeds the deadline.
    client = make_transport(deadline_s=0.5, sleep=sleep)
    assert _complete(client).text == ANSWER
    assert wire.clock == 40.75
    assert wire.sleeps == [10.0, 30.0]
    _event(wire, "ok", 2)


@pytest.mark.parametrize("exhausted", [False, True])
def test_gateway_counts_one_call_row_and_cap_unit(wire, make_transport, tmp_path, exhausted):
    wire.queue = [429] * (15 if exhausted else 2)
    path = tmp_path / "calls.jsonl"
    gateway = Gateway(cache_dir=tmp_path / "cache", ledger_path=path, max_calls=1,
                      tier="glm-flash", transport=make_transport())
    first = gateway.call("implementer", "prompt", tier="fast", seed=1)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert first.status == rows[0]["status"] == ("error" if exhausted else "ok")
    assert first.source == rows[0]["source"] == "network"
    if exhausted:
        assert first.reason == "TransportError: HTTPStatusError 429"
    assert gateway.network_calls == gateway.totals()["network"] == 1
    totals = gateway.totals()["by_role"]["implementer"]
    assert (totals["calls"], totals["network"]) == (1, 1)
    assert len(wire.requests) == (15 if exhausted else 3)
    _event(wire, "error" if exhausted else "ok", 14 if exhausted else 2)
    second = gateway.call("implementer", "different prompt", tier="fast", seed=1)
    assert second.status == "blocked"
    assert gateway.network_calls == 1
    assert len(wire.requests) == (15 if exhausted else 3)
    assert len(wire.ledger._events) == 1
