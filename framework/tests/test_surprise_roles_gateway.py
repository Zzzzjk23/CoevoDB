"""Offline tests for the LLM gateway, cache, schema, and DeepSeek transport."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from surprise.gates import s09_cases as C
from surprise.roles import (
    Completion,
    Gateway,
    Reply,
    ResponseCache,
    TransportError,
    cache_key,
    constants,
    parse_reply,
)
from surprise.roles.cache import ResponseCache as CacheClass
from surprise.roles.gateway import Gateway as GatewayClass

FRAMEWORK = Path(__file__).resolve().parents[1]
FAKE_KEY = "sk-test-gateway-secret-value-not-real"


class Script:
    """A transport that answers from a list (or by role) and remembers every request."""

    def __init__(self, replies: Any = ()) -> None:
        self.replies = replies if callable(replies) or isinstance(replies, dict) else list(replies)
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
        if isinstance(self.replies, dict):
            reply = self.replies[role]
        elif callable(self.replies):
            reply = self.replies(prompt)
        else:
            reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return Completion(text=text, input_tokens=len(prompt) // 4, output_tokens=len(text) // 4)


class Refuse:
    """A transport that must never be reached."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, **_: Any) -> Any:
        self.calls += 1
        raise RuntimeError("the network was used during a replay")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _gateway(root: Path, transport: Any, *, max_calls: int | None = 20, ledger: bool = True) -> Gateway:
    return Gateway(
        cache_dir=root / "cache",
        ledger_path=(root / "calls.jsonl") if ledger else None,
        max_calls=max_calls,
        transport=transport,
    )


def _ledger_lines(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture
def no_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(C.CONSTANTS["CAP_ENV"], raising=False)


def test_constants_match_the_gate_table() -> None:
    have = constants.as_dict()
    for name, value in C.CONSTANTS.items():
        assert name in have
        assert have[name] == value
        assert type(have[name]) is type(value)
    detached = constants.as_dict()
    detached["DEFAULT_MAX_CALLS"] = 0
    detached["TIERS"]["fast"] = "other"
    assert constants.as_dict() == have
    assert constants.TIERS["fast"] == "deepseek-flash"
    assert len(have["TIERS"]) >= 2
    assert len(set(have["TIERS"].values())) == len(have["TIERS"])


def test_parse_reply_cases() -> None:
    cases = [
        ('{"answer": 1}', None, "no_prediction"),
        ("not json at all", None, "no_json"),
        ("[1, 2]", None, "not_object"),
        ('{"prediction": ""}', None, "no_prediction"),
        ('{"prediction": []}', None, "no_prediction"),
        ('{"prediction": {}}', None, "no_prediction"),
        ('{"prediction": null}', None, "no_prediction"),
        ('```json\n{"prediction": {"expect": "fail"}}\n```', {"prediction": {"expect": "fail"}}, None),
        ('Here it is: {"prediction": "x", "q": 1} -- done', {"prediction": "x", "q": 1}, None),
        ('{"prediction": 0}', {"prediction": 0}, None),
        ('{"prediction": false}', {"prediction": False}, None),
        ("", None, "no_json"),
        ("```\nnot json\n```", None, "no_json"),
        ("true", None, "not_object"),
    ]
    for text, data, reason in cases:
        assert tuple(parse_reply(text)) == (data, reason)


def test_cache_key_is_sha_of_prompt_sha_model_and_seed() -> None:
    prompt = "Write a query. Reply in JSON with a prediction."
    key = cache_key(prompt, C.TIERS["fast"], 0)
    assert key == _sha(f"{_sha(prompt)}\n{C.TIERS['fast']}\n0")
    assert key != cache_key(prompt, C.TIERS["fast"], 1)
    assert key != cache_key(prompt, C.TIERS["strong"], 0)


def test_response_cache_put_get_and_forged_entry(tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path / "missing" / "cache")
    prompt = "hello"
    key = cache_key(prompt, "m", 0)
    entry = {
        "key": key,
        "prompt_sha256": _sha(prompt),
        "model": "m",
        "seed": 0,
        "role": "implementer",
        "tier": "fast",
        "prompt": prompt,
        "text": '{"prediction": 1}',
        "input_tokens": 3,
        "output_tokens": 4,
        "temperature": 0.2,
        "max_tokens": 10,
        "created_at": "2020-01-01T00:00:00+00:00",
    }
    cache.put(entry)
    path = cache.path(key)
    assert path == tmp_path / "missing" / "cache" / key[:2] / f"{key}.json"
    assert path.is_file()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert set(C.CACHE_ENTRY_KEYS) <= set(loaded)
    assert cache.get(key) == loaded
    forged = dict(loaded, prompt="something else")
    path.write_text(json.dumps(forged), encoding="utf-8")
    assert cache.get(key) is None
    path.write_text("{", encoding="utf-8")
    assert cache.get(key) is None
    assert cache.get("0" * 64) is None


def test_gateway_cache_hit_replay_offline_ledger_and_totals(tmp_path: Path, no_cap: None) -> None:
    prompt = "Write a query. Reply in JSON with a prediction."
    good = {"query": "SELECT 1", "prediction": {"expect": "pass"}}
    script = Script([good, good, good, good])
    gw = _gateway(tmp_path, script)
    r1 = gw.call("implementer", prompt, tier="fast", seed=0)
    r2 = gw.call("implementer", prompt, tier="fast", seed=0)
    r3 = gw.call("implementer", prompt, tier="fast", seed=1)
    r4 = gw.call("conjecturer", prompt, tier="strong", seed=0)
    assert (r1.status, r1.source, r2.status, r2.source) == ("ok", "network", "ok", "cache")
    assert r1.data == r2.data == good
    assert r1.text == r2.text
    assert r3.source == "network" and r4.source == "network"
    assert len(script.calls) == 3
    assert [c["model"] for c in script.calls] == [
        constants.TIERS["fast"],
        constants.TIERS["fast"],
        constants.TIERS["strong"],
    ]
    expected_key = _sha(f"{_sha(prompt)}\n{constants.TIERS['fast']}\n0")
    assert r1.key == expected_key == cache_key(prompt, constants.TIERS["fast"], 0)
    assert r1.key != r3.key != r4.key
    entry_path = tmp_path / "cache" / r1.key[:2] / f"{r1.key}.json"
    assert entry_path.is_file()
    entry = json.loads(entry_path.read_text(encoding="utf-8"))
    assert set(C.CACHE_ENTRY_KEYS) <= set(entry)
    assert entry["prompt"] == prompt and entry["text"] == r1.text
    assert entry["model"] == constants.TIERS["fast"] and entry["seed"] == 0
    refuse = Refuse()
    gw2 = _gateway(tmp_path, refuse, ledger=False)
    again = [
        gw2.call("implementer", prompt, tier="fast", seed=0),
        gw2.call("implementer", prompt, tier="fast", seed=1),
        gw2.call("conjecturer", prompt, tier="strong", seed=0),
    ]
    assert refuse.calls == 0 and gw2.network_calls == 0
    assert [(a.status, a.source, a.key, a.text, a.data) for a in again] == [
        (b.status, "cache", b.key, b.text, b.data) for b in (r1, r3, r4)
    ]
    offline = _gateway(tmp_path, None, ledger=False)
    hit = offline.call("implementer", prompt, tier="fast", seed=0)
    miss = offline.call("implementer", "new", tier="fast", seed=0)
    assert (hit.status, hit.source) == ("ok", "cache")
    assert (miss.status, miss.source, miss.reason) == ("miss", None, "miss")
    forged = dict(entry, prompt="something else")
    entry_path.write_text(json.dumps(forged), encoding="utf-8")
    forged_reply = _gateway(tmp_path, None, ledger=False).call("implementer", prompt, tier="fast", seed=0)
    assert forged_reply.status == "miss"
    lines = _ledger_lines(tmp_path / "calls.jsonl")
    assert len(lines) == 4
    assert all(set(line) == set(C.LEDGER_KEYS) for line in lines)
    assert [line["source"] for line in lines] == ["network", "cache", "network", "network"]
    assert [line["seq"] for line in lines] == [1, 2, 3, 4]
    for line in lines:
        assert prompt not in json.dumps(line)
        assert r1.text not in json.dumps(line)
    totals = gw.totals()
    impl = totals["by_role"]["implementer"]
    assert set(C.ROLE_TOTAL_KEYS) <= set(impl)
    assert (impl["calls"], impl["network"], impl["cache"], impl["ok"]) == (3, 2, 1, 3)
    assert totals["by_role"]["conjecturer"]["network"] == 1
    assert totals["network"] == 3 == gw.network_calls
    blob = json.dumps(gw.manifest())
    assert json.loads(blob) == gw.manifest()
    assert gw.manifest()["tiers"] == constants.TIERS
    assert gw.manifest()["constants"]["TIERS"] == constants.TIERS


def test_gateway_does_not_write_an_env_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_cap: None) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", FAKE_KEY)
    script = Script([{"prediction": "a"}])
    gw = _gateway(tmp_path, script)
    gw.call("implementer", "prompt", tier="fast", seed=0)
    found = []
    for path in tmp_path.rglob("*"):
        if path.is_file() and FAKE_KEY in path.read_text(encoding="utf-8", errors="replace"):
            found.append(path.name)
    assert found == []


def test_reject_live_and_replay(tmp_path: Path, no_cap: None) -> None:
    cases = [
        ('{"answer": 1}', None, "no_prediction"),
        ("not json at all", None, "no_json"),
        ("[1, 2]", None, "not_object"),
        ('{"prediction": ""}', None, "no_prediction"),
        ('{"prediction": []}', None, "no_prediction"),
        ('{"prediction": {}}', None, "no_prediction"),
        ('{"prediction": null}', None, "no_prediction"),
        ('```json\n{"prediction": {"expect": "fail"}}\n```', {"prediction": {"expect": "fail"}}, None),
        ('Here it is: {"prediction": "x", "q": 1} -- done', {"prediction": "x", "q": 1}, None),
    ]
    script = Script([text for text, _, _ in cases])
    gw = _gateway(tmp_path, script)
    live = [gw.call("implementer", f"prompt {i}", tier="fast", seed=0) for i in range(len(cases))]
    want = ["rejected" if data is None else "ok" for _, data, _ in cases]
    assert [r.status for r in live] == want
    for reply, (_, data, reason) in zip(live, cases):
        if data is None:
            assert reply.data is None and reply.reason == reason and reply.text is not None
        else:
            assert reply.data == data and reply.reason is None
    replay = _gateway(tmp_path, Refuse(), ledger=False)
    again = [replay.call("implementer", f"prompt {i}", tier="fast", seed=0) for i in range(len(cases))]
    assert [(r.status, r.source, r.reason) for r in again] == [
        (r.status, "cache", r.reason) for r in live
    ]
    assert gw.totals()["by_role"]["implementer"]["rejected"] == want.count("rejected")


def test_cap_blocks_then_serves_cache_and_counts_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(C.CONSTANTS["CAP_ENV"], raising=False)
    script = Script([{"prediction": "a"}, {"prediction": "b"}, {"prediction": "c"}])
    gw = _gateway(tmp_path, script, max_calls=2)
    got = [gw.call("implementer", p, tier="fast", seed=0) for p in ("p1", "p2", "p3")]
    assert [r.status for r in got] == ["ok", "ok", "blocked"]
    assert got[2].source is None and got[2].reason == "cap"
    assert len(script.calls) == 2
    hit = gw.call("implementer", "p1", tier="fast", seed=0)
    assert (hit.status, hit.source) == ("ok", "cache")
    assert gw.totals()["by_role"]["implementer"]["blocked"] == 1
    assert gw.max_calls == 2
    zero = Script([{"prediction": "a"}])
    blocked = _gateway(tmp_path / "cap0", zero, max_calls=0).call("implementer", "p", tier="fast", seed=0)
    assert blocked.status == "blocked" and zero.calls == []
    monkeypatch.setenv(C.CONSTANTS["CAP_ENV"], "1")
    script = Script([{"prediction": "a"}, {"prediction": "b"}])
    capped = _gateway(tmp_path / "capenv", script, max_calls=5)
    statuses = [capped.call("implementer", p, tier="fast", seed=0).status for p in ("p1", "p2")]
    assert statuses == ["ok", "blocked"]
    assert capped.max_calls == 1
    assert capped.manifest()["max_calls"] == 1
    monkeypatch.delenv(C.CONSTANTS["CAP_ENV"], raising=False)
    flaky = Script([RuntimeError("boom"), {"prediction": "ok"}])
    fg = _gateway(tmp_path / "caperr", flaky, max_calls=5)
    first = fg.call("implementer", "p", tier="fast", seed=0)
    second = fg.call("implementer", "p", tier="fast", seed=0)
    assert (first.status, first.source, first.reason) == ("error", "network", "RuntimeError")
    assert (second.status, second.source) == ("ok", "network")
    assert fg.network_calls == 2
    assert first.text is None and first.data is None
    with pytest.raises(ValueError):
        _gateway(tmp_path / "cap-tier", Script([{"prediction": 1}])).call(
            "implementer", "p", tier="huge", seed=0
        )


def test_default_cap_is_the_constant(tmp_path: Path, no_cap: None) -> None:
    gw = Gateway(cache_dir=tmp_path / "default", transport=None)
    assert gw.max_calls == C.CONSTANTS["DEFAULT_MAX_CALLS"]
    assert gw.manifest()["max_calls"] == C.CONSTANTS["DEFAULT_MAX_CALLS"]


def test_totals_count_network_tokens_only(tmp_path: Path, no_cap: None) -> None:
    script = Script([{"prediction": "a"}])
    gw = _gateway(tmp_path, script)
    first = gw.call("implementer", "p", tier="fast", seed=0)
    gw.call("implementer", "p", tier="fast", seed=0)
    impl = gw.totals()["by_role"]["implementer"]
    assert impl["input_tokens"] == first.input_tokens
    assert impl["output_tokens"] == first.output_tokens
    assert impl["network"] == 1 and impl["cache"] == 1 and impl["calls"] == 2


def test_package_exports_and_does_not_load_transport() -> None:
    import surprise.roles as R

    assert R.constants is constants
    assert R.Gateway is GatewayClass
    assert R.ResponseCache is CacheClass
    assert R.Completion is Completion
    assert R.Reply is Reply
    assert R.TransportError is TransportError
    assert "transport" not in R.__all__
    from surprise.roles.implementer import Implementer as ImplementerClass

    assert R.Implementer is ImplementerClass
    probe = (
        "import json, sys\n"
        "import surprise.roles, surprise.roles.gateway, surprise.roles.cache, "
        "surprise.roles.source, surprise.roles.constants, surprise.roles.schema\n"
        "mods = sorted(m for m in "
        + repr(list(C.LLM_MODULES))
        + " if m in sys.modules)\n"
        "print(json.dumps({'mods': mods, 'transport': 'surprise.roles.transport' in sys.modules}))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=FRAMEWORK,
        capture_output=True,
        text=True,
        timeout=60,
        env={k: v for k, v in os.environ.items() if k.upper() != "DEEPSEEK_API_KEY"},
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    assert payload["mods"] == []
    assert payload["transport"] is False


def test_roles_modules_do_not_mention_clients() -> None:
    roles = FRAMEWORK / "surprise" / "roles"
    banned = ("httpx", "openai", "anthropic", "agents.base_agent", "llm.ledger")
    for name in ("__init__.py", "gateway.py", "cache.py", "schema.py", "constants.py", "source.py"):
        text = (roles / name).read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, f"{name} mentions {token}"
        assert "from .transport" not in text
        assert "import transport" not in text


def test_transport_without_key_does_not_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    from surprise.roles.transport import DeepSeekTransport

    transport = DeepSeekTransport(base_url="http://127.0.0.1:9")
    with pytest.raises(TransportError, match="DEEPSEEK_API_KEY is not set"):
        transport.complete(
            model="deepseek-flash",
            prompt="hi",
            temperature=0.0,
            max_tokens=8,
            role="implementer",
        )
    with pytest.raises(NotImplementedError):
        transport.execute({})
    with pytest.raises(NotImplementedError):
        transport.learn_from_feedback({})


def test_transport_error_hides_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", FAKE_KEY)
    from surprise.roles.transport import DeepSeekTransport

    transport = DeepSeekTransport(base_url="http://127.0.0.1:9")
    with pytest.raises(TransportError) as info:
        transport.complete(
            model="deepseek-flash",
            prompt="hi",
            temperature=0.0,
            max_tokens=8,
            role="implementer",
        )
    message = str(info.value)
    assert FAKE_KEY not in message
    assert FAKE_KEY not in repr(info.value)
    assert "Authorization" not in message
    assert "hi" not in message
    assert info.value.__cause__ is None
    assert type(info.value).__name__ == "TransportError"
    parts = message.split()
    assert parts and parts[0].isidentifier()
    assert len(parts) == 1 or (len(parts) == 2 and parts[1].isdigit())
