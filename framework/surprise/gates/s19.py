"""S19 gate. Exit 0 = pass.

S19 runs E1 (SESSIONS S19). On 2026-10-20 the user also asked, during S19, to switch the LLM roles
from DeepSeek to GLM 5.3 Flash on OpenRouter (provider open-inference/fp4, no fallbacks, reasoning
on; the key stays in DEEPSEEK_API_KEY). These groups check that switch, offline (no network):

  transport  the new model goes to OpenRouter's chat completions with the provider and reasoning
             fields and the same key; DeepSeek models still get the old request, unchanged; HTTP
             errors and empty answers stay TransportError; no OpenAI SDK
  gateway    tier glm-flash forces the new model on every call and is recorded (calls.jsonl, cache
             key, manifest with the endpoint); without it the gateway and its manifest are as before
  replay     the M3 loop replay and the pure-LLM replay run offline with --llm-tier glm-flash: every
             call asks the new model and misses the DeepSeek cache; the run manifest records it
  grid       grid arms take tier glm-flash and pass --llm-tier glm-flash; unknown tiers still fail
  prices     the OpenRouter price table, dated, as the grid's prices; the DeepSeek table unchanged
  scope      changes since s15-done-r3 stay in scope; harness and roles/constants.py untouched

On 2026-10-21 the user asked for alerts on low credit and errors through pushplus one-to-one
messages (token in PUSHPLUS_TOKEN). A watcher process reads a grid's result directory and never
writes to it; experiments/ and the S8 pin stay as they are. These groups check it, offline:

  pushplus   the sender posts a txt message with the token in the body; codes 900/905/888 stop it;
             other failures do not raise; no token, no request; the token is never printed
  reason     a failed call records the transport's message (HTTP status kept, no key); the watcher
             maps reasons to causes (credit, auth, rate, timeout, nokey, other)
  watch      start, LLM failure streaks, blocked/failed/stalled cells and the end of the grid, one
             message per poll, a daily cap, read-only on the grid directory
  balance    OpenRouter's key endpoint on glm-flash grids: low and empty credit once each, 401 too
  cli        python -m surprise.notify.pushplus and python -m surprise.notify.watch (--pid)

The E1 result groups (SESSIONS S19) are added when the formal results are copied back.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from . import s19_cases as C
from .s06 import GateFailure, _ascii, require
from .s15 import _Echo, _m3_argv, env_var, git, load_json, py, write_config

FRAMEWORK = Path(__file__).resolve().parents[2]
REPO = FRAMEWORK.parent
_TMP_ROOT = Path(tempfile.gettempdir()) / "coevo-s19-gate"
_PROMPT = "Reply with JSON."
_ANSWER = json.dumps({"prediction": "x"})


# ---- helpers ------------------------------------------------------------------------------------

def tmpdir(name: str) -> Path:
    path = _TMP_ROOT / name
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    return path


def lines_of(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _completion(content: Any) -> dict[str, Any]:
    """An OpenRouter-style answer with reasoning, as the user's example returns it."""
    return {
        "id": "gen-s19",
        "model": C.NEW_MODEL,
        "choices": [{
            "index": 0,
            "finish_reason": "stop",
            "message": {
                "role": "assistant",
                "content": content,
                "reasoning": "thinking",
                "reasoning_details": [{"type": "reasoning.text", "text": "thinking"}],
            },
        }],
        "usage": {"prompt_tokens": 11, "completion_tokens": 22, "total_tokens": 33,
                  "completion_tokens_details": {"reasoning_tokens": 15}},
    }


class _Wire:
    """Stands in for the network: every httpx request is recorded and answered here."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.status = 200
        self.content: Any = _ANSWER

    @contextlib.contextmanager
    def on(self) -> Iterator["_Wire"]:
        import httpx

        saved = httpx.HTTPTransport.handle_request
        wire = self

        def handle(_transport: Any, request: Any) -> Any:
            body = request.read()
            wire.requests.append({
                "method": request.method,
                "url": str(request.url),
                "auth": request.headers.get("authorization"),
                "body": json.loads(body) if body else None,
            })
            if wire.status != 200:
                return httpx.Response(wire.status, json={"error": {"code": wire.status, "message": "gate"}},
                                      request=request)
            return httpx.Response(200, json=_completion(wire.content), request=request)

        httpx.HTTPTransport.handle_request = handle
        try:
            yield self
        finally:
            httpx.HTTPTransport.handle_request = saved


def _old_body(model: str) -> dict[str, Any]:
    return {"model": model, "messages": [{"role": "user", "content": _PROMPT}], "temperature": 0.2, "max_tokens": 100}


# ---- transport ----------------------------------------------------------------------------------

def check_transport() -> str:
    from surprise.roles.gateway import TransportError

    key = "gate-s19-dummy-key"
    wire = _Wire()
    with env_var(C.KEY_ENV, key), env_var(C.DECOY_ENV, "gate-s19-decoy"), wire.on():
        from surprise.roles.transport import DeepSeekTransport

        transport = DeepSeekTransport()
        done = transport.complete(model=C.NEW_MODEL, prompt=_PROMPT, temperature=0.2, max_tokens=100, role="implementer")
        require(len(wire.requests) == 1, f"{len(wire.requests)} requests for one call")
        sent = wire.requests[-1]
        require(sent["method"] == "POST" and sent["url"] == C.NEW_URL, f"new model went to {sent['method']} {sent['url']}")
        require(sent["auth"] == f"Bearer {key}", f"the new model must use the key in {C.KEY_ENV}")
        want = {**_old_body(C.NEW_MODEL), **C.NEW_PROFILE["body"]}
        require(sent["body"] == want, f"request body {sent['body']} != {want}")
        require((done.text, done.input_tokens, done.output_tokens) == (_ANSWER, 11, 22),
                f"answer read as {(done.text, done.input_tokens, done.output_tokens)}")

        for model in C.OLD_TIERS.values():
            transport.complete(model=model, prompt=_PROMPT, temperature=0.2, max_tokens=100, role="implementer")
            sent = wire.requests[-1]
            require(sent["url"] == C.OLD_URL and sent["auth"] == f"Bearer {key}", f"{model} went to {sent['url']}")
            require(sent["body"] == _old_body(model), f"{model}: request body changed: {sent['body']}")
        fresh = DeepSeekTransport()
        fresh.complete(model="deepseek-flash", prompt=_PROMPT, temperature=0.2, max_tokens=100, role="implementer")
        require(wire.requests[-1]["url"] == C.OLD_URL and wire.requests[-1]["body"] == _old_body("deepseek-flash"),
                "a fresh transport's DeepSeek request changed")

        for status in (402, 429):
            wire.status = status
            try:
                transport.complete(model=C.NEW_MODEL, prompt=_PROMPT, temperature=0.2, max_tokens=100, role="implementer")
            except TransportError as exc:
                require(str(status) in str(exc), f"HTTP {status} lost its status: {exc}")
            else:
                raise GateFailure(f"HTTP {status} from OpenRouter did not raise TransportError")
        wire.status = 200
        wire.content = None
        try:
            transport.complete(model=C.NEW_MODEL, prompt=_PROMPT, temperature=0.2, max_tokens=100, role="implementer")
        except TransportError:
            pass
        else:
            raise GateFailure("an answer with null content did not raise TransportError")
    require("openai" not in sys.modules, "the OpenAI SDK was imported; the transport stays on httpx")
    return (f"{C.NEW_MODEL} -> {C.NEW_URL} with provider/reasoning and the {C.KEY_ENV} key; DeepSeek requests "
            f"unchanged; 402/429/null content raise TransportError; {len(wire.requests)} requests, none on the network")


# ---- gateway ------------------------------------------------------------------------------------

def check_gateway() -> str:
    from surprise.roles.constants import TIERS
    from surprise.roles.gateway import Gateway

    require(dict(TIERS) == C.OLD_TIERS, f"roles.constants.TIERS changed: {TIERS}")
    tmp = tmpdir("gateway")
    with env_var(C.CAP_ENV, None):
        echo = _Echo()
        glm = Gateway(cache_dir=tmp / "g1", ledger_path=tmp / "g1" / "calls.jsonl", transport=echo, tier=C.NEW_TIER)
        reply = glm.call("implementer", "prompt", tier="fast", seed=0)
        require(echo.models == [C.NEW_MODEL] and reply.tier == C.NEW_TIER and reply.model == C.NEW_MODEL,
                f"tier {C.NEW_TIER}: transport saw {echo.models}, reply {reply.tier}/{reply.model}")
        rows = lines_of(tmp / "g1" / "calls.jsonl")
        require(rows and rows[-1].get("model") == C.NEW_MODEL and rows[-1].get("tier") == C.NEW_TIER,
                f"calls.jsonl does not record the new model and tier: {rows[-1:]}")
        manifest = glm.manifest()
        require(manifest.get("tier") == C.NEW_TIER and manifest.get("endpoint") == C.NEW_PROFILE,
                f"manifest must record tier and endpoint: {manifest.get('tier')!r}, {manifest.get('endpoint')!r}")
        require(manifest.get("tiers") == C.OLD_TIERS, f"manifest tiers changed: {manifest.get('tiers')}")

        plain = Gateway(cache_dir=tmp / "g2", transport=echo)
        old = plain.call("implementer", "prompt", tier="fast", seed=0)
        require(echo.models[-1] == C.OLD_TIERS["fast"], "without an override the role's tier must be used")
        require(old.key != reply.key, "the new model must not share the DeepSeek cache key")
        require(set(plain.manifest()) == C.OLD_MANIFEST_KEYS,
                f"manifest without an override has keys {sorted(plain.manifest())}")
        strong = Gateway(cache_dir=tmp / "g3", tier="strong").manifest()
        require(strong.get("tier") == "strong" and "endpoint" not in strong, f"strong-tier manifest: {sorted(strong)}")
        for bad in ("medium", "glm", C.NEW_MODEL):
            try:
                Gateway(cache_dir=tmp / "g4", tier=bad)
            except ValueError:
                continue
            raise GateFailure(f"Gateway accepted tier={bad!r}")
    return (f"tier {C.NEW_TIER} -> {C.NEW_MODEL} on every call, own cache key, recorded with its endpoint; "
            f"no override: DeepSeek and the old manifest keys")


# ---- replay -------------------------------------------------------------------------------------

def check_replay() -> str:
    from surprise.harness.ledger import Ledger

    from . import s04 as G4
    from . import s10_cases as C10
    from . import s11_cases as C11

    tmp = tmpdir("replay")
    m3 = REPO / "framework/surprise/gates/s10_llm/m3"
    boot = tmp / "bootstrap.json"
    boot.write_text(json.dumps([{"case": G4.load(item["case"]).to_dict(), "oracle": item["oracle"], "rule": item["rule"]}
                                for item in C10.M3_RUN["bootstrap"]]), encoding="utf-8")
    shutil.copytree(m3 / "cache", tmp / "cache")
    out = tmp / "m3-glm"
    proc = py(_m3_argv(out, tmp / "cache", boot, ["--llm-tier", C.NEW_TIER]), timeout=3600)
    require(proc.returncode == 0, f"M3 replay on tier {C.NEW_TIER} failed: {proc.stderr[-800:]}")
    calls = lines_of(out / "llm" / "calls.jsonl")
    require(calls and all(c.get("model") == C.NEW_MODEL and c.get("tier") == C.NEW_TIER and c.get("source") != "cache"
                          for c in calls), f"tier {C.NEW_TIER}: every call must ask {C.NEW_MODEL} and miss the cache")
    require(load_json(out / "config.json", "config.json")["llm"].get("tier") == C.NEW_TIER,
            f"config.json lacks tier {C.NEW_TIER}")
    with Ledger(out / "ledger.sqlite") as ledger:
        llm = ledger.run_manifest(ledger.run_ids()[0]).get("llm") or {}
    require(llm.get("tier") == C.NEW_TIER and llm.get("endpoint") == C.NEW_PROFILE,
            f"run manifest llm section: tier {llm.get('tier')!r}, endpoint {llm.get('endpoint')!r}")
    require(llm.get("tiers") == C.OLD_TIERS, f"run manifest tiers changed: {llm.get('tiers')}")

    pure = REPO / "framework/surprise/gates/s11_llm/pure_llm"
    spec = C11.PURE_RUN
    shutil.copytree(pure / "cache", tmp / "cache-pure")
    out_p = tmp / "pure-glm"
    proc = py(["-m", "surprise.baselines.pure_llm", "--out", str(out_p), "--seed", str(spec["seed"]), "--engine",
               spec["engine"], "--max-experiments", str(spec["experiments"]), "--llm-cache", str(tmp / "cache-pure"),
               "--llm-offline", "--llm-tier", C.NEW_TIER], timeout=3600)
    require(proc.returncode == 0, f"pure-LLM on tier {C.NEW_TIER} failed: {proc.stderr[-800:]}")
    rows = lines_of(out_p / "llm" / "calls.jsonl")
    require(rows and all(r.get("model") == C.NEW_MODEL and r.get("tier") == C.NEW_TIER for r in rows),
            f"pure-LLM tier {C.NEW_TIER}: calls ask {sorted({r.get('model') for r in rows})}")
    for module in ("surprise.experiments.loop", "surprise.baselines.pure_llm"):
        proc = py(["-m", module, "--out", str(tmp / "bad"), "--seed", "0", "--llm-tier", "medium"], timeout=300)
        require(proc.returncode == 2, f"{module} --llm-tier medium exited {proc.returncode}, expected 2")
    return (f"M3 replay: {len(calls)} calls on {C.NEW_MODEL}, all cache misses, manifest records the endpoint; "
            f"pure-LLM: {len(rows)} calls on {C.NEW_MODEL}")


# ---- grid ---------------------------------------------------------------------------------------

def check_grid() -> str:
    from surprise.experiments import grid

    tmp = tmpdir("grid")

    def config(tier: str) -> dict[str, Any]:
        return {"schema": 1, "name": "g", "budget": {"minutes": 1.0}, "seeds": [1], "arms": [
            {"name": "full", "kind": "surprise", "engines": ["duckdb"], "tier": tier,
             "llm": {"roles": ["implementer"], "cache": "c-full", "max_calls": "unlimited"}},
            {"name": "pure", "kind": "pure_llm", "engine": "duckdb", "tier": tier,
             "llm": {"cache": "c-pure", "max_calls": "unlimited"}}]}

    cfg = grid.load_config(write_config(tmp / "g.json", config(C.NEW_TIER)))
    for arm in cfg["arms"]:
        argv = grid.command_for(arm, out=tmp / "o", seed=1, rep=0)
        require("--llm-tier" in argv and argv[argv.index("--llm-tier") + 1] == C.NEW_TIER,
                f"arm {arm['name']}: command lacks --llm-tier {C.NEW_TIER}: {argv}")
    for bad in ("medium", C.NEW_MODEL):
        try:
            grid.load_config(write_config(tmp / "bad.json", config(bad)))
        except ValueError:
            continue
        raise GateFailure(f"the grid accepted tier {bad!r}")
    return f"surprise and pure-LLM arms pass --llm-tier {C.NEW_TIER}; unknown tiers rejected"


# ---- prices -------------------------------------------------------------------------------------

def check_prices() -> str:
    from surprise.metrics.rq import _usd

    data = load_json(REPO / C.PRICES_FILE, "OpenRouter price table")
    require(data == C.PRICES, f"price table differs from the endpoint list read on {C.PRICES['retrieved']}")
    rows = [{"model": C.NEW_MODEL, "input_tokens": 1_000_000, "output_tokens": 2_000_000}]
    want = C.PRICES["grid"][C.NEW_MODEL]["input"] + 2 * C.PRICES["grid"][C.NEW_MODEL]["output"]
    got = _usd(rows, data["grid"])
    require(abs(got - want) < 1e-9, f"cost {got} != {want}")
    require(not git("diff", "--name-only", C.BASE_TAG, "--", C.OLD_PRICES_FILE).strip(), "the DeepSeek price table changed")
    return f"OpenRouter prices of {data['retrieved']} price {C.NEW_MODEL}; DeepSeek table unchanged"


# ---- alerts: helpers ----------------------------------------------------------------------------

_PUSH_TOKEN = "gate-s19-push-token"
_KEY = "gate-s19-dummy-key"


class _Net:
    """Stands in for pushplus and OpenRouter's key endpoint; every httpx request is recorded."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.push: tuple[int, Any] = (200, {"code": 200, "msg": "ok", "data": "gate"})
        self.key: tuple[int, Any] = (200, {"data": {"limit": 5.0, "limit_remaining": 4.0, "usage": 1.0}})
        self.broken = False

    @contextlib.contextmanager
    def on(self) -> Iterator["_Net"]:
        import httpx

        saved = httpx.HTTPTransport.handle_request
        net = self

        def handle(_transport: Any, request: Any) -> Any:
            body = request.read()
            url = str(request.url)
            net.requests.append({
                "method": request.method,
                "url": url,
                "auth": request.headers.get("authorization"),
                "body": json.loads(body) if body else None,
            })
            if net.broken:
                raise httpx.ConnectError("gate", request=request)
            if url == C.PUSH_URL:
                status, payload = net.push
            elif url == C.KEY_INFO_URL:
                status, payload = net.key
            else:
                status, payload = 404, {"error": "not in the gate"}
            return httpx.Response(status, json=payload, request=request)

        httpx.HTTPTransport.handle_request = handle
        try:
            yield self
        finally:
            httpx.HTTPTransport.handle_request = saved

    def to(self, url: str) -> list[dict[str, Any]]:
        return [r for r in self.requests if r["url"] == url]


class _Inbox:
    """A notifier that keeps what it is asked to send."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def send(self, title: str, content: str) -> bool:
        self.messages.append((title, content))
        return True


def _grid_dir(root: Path, *, glm: bool = True) -> Path:
    """A grid result directory as ``grid run`` leaves it: grid.json, no cells yet."""
    from surprise.experiments import grid

    arms: list[dict[str, Any]] = [{"name": "nollm", "kind": "surprise", "engines": ["duckdb"]}]
    if glm:
        arms += [
            {"name": "full", "kind": "surprise", "engines": ["duckdb"], "tier": C.NEW_TIER,
             "llm": {"roles": ["implementer"], "cache": "c-full", "max_calls": "unlimited"}},
            {"name": "pure", "kind": "pure_llm", "engine": "duckdb", "tier": C.NEW_TIER,
             "llm": {"cache": "c-pure", "max_calls": "unlimited"}},
        ]
    raw = {"schema": 1, "name": "g", "budget": {"minutes": 1.0}, "seeds": [1, 2], "arms": arms}
    config = grid.load_config(write_config(root / "raw.json", raw))
    out = root / "grid"
    out.mkdir()
    (out / "grid.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    return out


def _labels(out: Path) -> list[str]:
    config = json.loads((out / "grid.json").read_text(encoding="utf-8"))
    return [f"{arm['name']}/s{seed}-r0" for seed in config["seeds"] for arm in config["arms"]]


def _cell(out: Path, label: str, *, log: str = "started\n") -> Path:
    arm, rest = label.split("/")
    directory = out / "cells" / arm / rest
    (directory / "llm").mkdir(parents=True, exist_ok=True)
    (directory / "progress.jsonl").touch()
    log_path = directory.parent / f"{rest}.log"
    if not log_path.exists():
        log_path.write_text(log, encoding="utf-8")
    return directory


def _end(out: Path, label: str, status: str, code: int) -> None:
    directory = _cell(out, label)
    (directory / "cell.json").write_text(json.dumps({"status": status, "returncode": code, "killed": False}),
                                         encoding="utf-8")


def _row(status: str, reason: str | None = None) -> dict[str, Any]:
    source = "network" if status in ("ok", "rejected", "error") else None
    return {"seq": 0, "role": "implementer", "tier": C.NEW_TIER, "model": C.NEW_MODEL, "status": status,
            "source": source, "reason": reason, "input_tokens": 0, "output_tokens": 0, "latency_s": 0.1}


def _append(directory: Path, rows: list[dict[str, Any]], *, raw: str = "") -> None:
    with (directory / "llm" / "calls.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("".join(json.dumps(row) + "\n" for row in rows) + raw)


def _tree(root: Path) -> dict[str, tuple[int, int]]:
    return {str(p.relative_to(root)): (p.stat().st_size if p.is_file() else 0, p.stat().st_mtime_ns)
            for p in sorted(root.rglob("*"))}


def _poll(watcher: Any, out: Path) -> list[tuple[str, str | None, str | None]]:
    """One poll, which must leave the grid directory as it was."""
    before = _tree(out)
    events = watcher.poll()
    require(_tree(out) == before, "the watcher changed the grid directory")
    for event in events:
        require(event.kind in C.KINDS, f"unknown event kind {event.kind!r}")
    return [(e.kind, e.cell, e.cause) for e in events]


# ---- pushplus -----------------------------------------------------------------------------------

def check_pushplus() -> str:
    import io

    from surprise.notify import pushplus as P

    require(P.TOKEN_ENV == C.PUSH_ENV and P.URL == C.PUSH_URL, f"sender reads {P.TOKEN_ENV} and posts to {P.URL}")
    net = _Net()
    printed = io.StringIO()
    with env_var(C.PUSH_ENV, _PUSH_TOKEN), net.on(), contextlib.redirect_stdout(printed), \
            contextlib.redirect_stderr(printed):
        sender = P.PushPlus()
        require(sender.enabled, "a sender with the token set must be enabled")
        require(sender.send("t", "c") is True, "a 200/code 200 answer must count as sent")
        sent = net.requests[-1]
        require(sent["method"] == "POST" and sent["url"] == C.PUSH_URL, f"sent {sent['method']} {sent['url']}")
        require(sent["body"] == {"token": _PUSH_TOKEN, "title": "t", "content": "c", "template": C.PUSH_TEMPLATE},
                f"request body {sent['body']}")
        require(sender.sent == 1, f"sent counter {sender.sent}")

        for code in C.PUSH_STOP_CODES:
            stopped = P.PushPlus()
            net.push = (200, {"code": code, "msg": "gate", "data": None})
            before = len(net.requests)
            require(stopped.send("t", "c") is False and not stopped.enabled, f"code {code} must stop the sender")
            require(stopped.send("t", "c") is False and len(net.requests) == before + 1,
                    f"a stopped sender (code {code}) must not send again")
        net.push = (200, {"code": 999, "msg": "gate", "data": None})
        other = P.PushPlus()
        require(other.send("t", "c") is False and other.enabled, "another code fails this message only")
        net.push = (500, {"msg": "gate"})
        require(other.send("t", "c") is False and other.enabled, "HTTP 500 fails this message only")
        net.broken = True
        require(other.send("t", "c") is False and other.enabled, "a connection error fails this message only")
        net.broken = False
        net.push = (200, {"code": 200, "msg": "ok", "data": "gate"})
        require(other.send("t", "c") is True, "the sender works again after a failure")
    with env_var(C.PUSH_ENV, None), net.on():
        before = len(net.requests)
        silent = P.PushPlus()
        require(not silent.enabled and silent.send("t", "c") is False and len(net.requests) == before,
                f"without {C.PUSH_ENV} nothing may be sent")
    require(all(C.PUSH_URL == r["url"] for r in net.requests), "the sender called another address")
    require(all(_PUSH_TOKEN not in r["url"] for r in net.requests), "the token went into the URL")
    require(_PUSH_TOKEN not in printed.getvalue(), "the token was printed")
    return (f"one-to-one txt message to {C.PUSH_URL} with the {C.PUSH_ENV} token in the body; codes "
            f"{list(C.PUSH_STOP_CODES)} stop the sender, other failures do not; no token, no request")


# ---- reason -------------------------------------------------------------------------------------

def check_reason() -> str:
    from surprise.notify.watch import classify
    from surprise.roles.gateway import Gateway

    tmp = tmpdir("reason")
    wire = _Wire()
    want = "TransportError: HTTPStatusError 402"
    with env_var(C.KEY_ENV, _KEY), env_var(C.CAP_ENV, None), wire.on():
        from surprise.roles.transport import DeepSeekTransport

        gateway = Gateway(cache_dir=tmp / "cache", ledger_path=tmp / "calls.jsonl", transport=DeepSeekTransport(),
                          tier=C.NEW_TIER)
        wire.status = 402
        reply = gateway.call("implementer", _PROMPT, tier="fast", seed=0)
        require((reply.status, reply.reason) == ("error", want), f"402: reply {reply.status}/{reply.reason!r}")
        wire.status = 200
        good = gateway.call("implementer", _PROMPT + " again", tier="fast", seed=0)
        require(good.status == "ok" and good.reason is None, f"200: reply {good.status}/{good.reason!r}")
    rows = lines_of(tmp / "calls.jsonl")
    require([r.get("reason") for r in rows] == [want, None], f"calls.jsonl reasons {[r.get('reason') for r in rows]}")
    for path in tmp.rglob("*"):
        if path.is_file():
            require(_KEY not in path.read_text(encoding="utf-8", errors="replace"), f"the key is in {path.name}")

    class _Boom:
        def complete(self, **_: Any) -> Any:
            raise RuntimeError("boom")

    other = Gateway(cache_dir=tmp / "cache2", transport=_Boom()).call("implementer", _PROMPT, tier="fast", seed=0)
    require(other.reason == "RuntimeError", f"a non-transport exception is recorded as {other.reason!r}")
    wrong = {reason: classify(reason) for reason, cause in C.CAUSES.items() if classify(reason) != cause}
    require(not wrong, f"causes: {wrong}")
    return (f"a failed call records {want!r} (status kept, no key); other exceptions as before; "
            f"{len(C.CAUSES)} reasons classified")


# ---- watch --------------------------------------------------------------------------------------

def check_watch() -> str:
    import io

    from surprise.notify import watch as W

    tmp = tmpdir("watch")
    out = _grid_dir(tmp)
    inbox = _Inbox()
    now = [time.time()]
    printed = io.StringIO()
    net = _Net()
    with env_var(C.PUSH_ENV, _PUSH_TOKEN), env_var(C.KEY_ENV, None), net.on(), contextlib.redirect_stdout(printed):
        w = W.Watcher(out, notifier=inbox, clock=lambda: now[0])
        full1 = _cell(out, "full/s1-r0")
        _append(full1, [_row("ok")] * 3 + [_row("error", "TransportError: HTTPStatusError 402")] * 5)
        first = _poll(w, out)
        require(first[:1] == [("start", None, None)], f"the first poll must start with 'start': {first}")
        require(("llm_errors", "full/s1-r0", "credit") in first, f"five 402s in a row: {first}")
        require(len(inbox.messages) == 1, f"one poll sends one message, got {len(inbox.messages)}")
        require("full/s1-r0" in inbox.messages[-1][1] and "402" in inbox.messages[-1][1],
                f"the message names the cell and the status: {inbox.messages[-1]}")
        require(_poll(w, out) == [] and len(inbox.messages) == 1, "nothing new must send nothing")

        _append(full1, [_row("error", "TransportError: HTTPStatusError 402")] * 2)
        require(_poll(w, out) == [], "a streak is reported once")
        _append(full1, [_row("ok")] + [_row("error", "TransportError: DeadlineExceeded")] * 4)
        require(_poll(w, out) == [], "four failures after a success are not yet a streak")
        line = json.dumps(_row("error", "TransportError: DeadlineExceeded")) + "\n"
        _append(full1, [], raw=line[:15])
        require(_poll(w, out) == [], "half a line is not read")
        _append(full1, [], raw=line[15:])
        require(_poll(w, out) == [("llm_errors", "full/s1-r0", "timeout")], "the fifth timeout opens a new streak")

        _cell(out, "full/s2-r0", log="Traceback (most recent call last):\nValueError: boom\n")
        _end(out, "full/s2-r0", "failed", 1)
        _append(_cell(out, "pure/s1-r0"), [_row("blocked", "cap"), _row("blocked", "cap")])
        stalled = _cell(out, "pure/s2-r0")
        old = now[0] - 31 * 60
        for path in (stalled / "progress.jsonl", stalled / "llm", stalled, stalled.parent / "s2-r0.log"):
            os.utime(path, (old, old))
        sent = len(inbox.messages)
        got = set(_poll(w, out))
        want = {("cell_failed", "full/s2-r0", None), ("llm_blocked", "pure/s1-r0", None), ("stall", "pure/s2-r0", None)}
        require(got == want, f"failed, blocked and stalled cells: {sorted(got, key=str)}")
        require(len(inbox.messages) == sent + 1, "three events in one poll are one message")
        content = inbox.messages[-1][1]
        require(all(label in content for label in ("full/s2-r0", "pure/s1-r0", "pure/s2-r0")) and "boom" in content,
                f"the message names every cell and the log tail: {content!r}")
        _append(_cell(out, "pure/s1-r0"), [_row("blocked", "cap")])
        require(_poll(w, out) == [], "blocked and stalled cells are reported once")

        for label in _labels(out):
            if label != "full/s2-r0":
                _end(out, label, "done", 0)
        last = _poll(w, out)
        require(last == [("finished", None, None)], f"every cell has cell.json: {last}")
        require("full/s2-r0" in inbox.messages[-1][1], "the summary lists the failed cell")
        require(_poll(w, out) == [], "nothing after 'finished'")

        cap_out = _grid_dir(tmpdir("watch-cap"))
        capped = _Inbox()
        c = W.Watcher(cap_out, notifier=capped, clock=lambda: now[0], max_per_day=2)
        require(_poll(c, cap_out)[:1] == [("start", None, None)], "start")
        _append(_cell(cap_out, "full/s1-r0"), [_row("error", "TransportError: HTTPStatusError 429")] * 5)
        require(_poll(c, cap_out) == [("llm_errors", "full/s1-r0", "rate")], "429 streak")
        _end(cap_out, "pure/s1-r0", "failed", 1)
        require(_poll(c, cap_out) == [("cell_failed", "pure/s1-r0", None)] and len(capped.messages) == 2,
                f"over the daily cap the event is kept but not sent: {len(capped.messages)} messages")
        _end(cap_out, "full/s1-r0", "done", 0)  # no running cell left to look stalled a day later
        require(_poll(c, cap_out) == [], "a done cell is no event")
        now[0] += 86400
        _end(cap_out, "pure/s2-r0", "failed", 1)
        require(_poll(c, cap_out) == [("cell_failed", "pure/s2-r0", None)] and len(capped.messages) == 3,
                "a new day sends again")
    require(not net.requests, f"the watcher went on the network without a key: {net.requests[:2]}")
    text = printed.getvalue()
    require(_PUSH_TOKEN not in text, "the token was printed")
    require(all(kind in text for kind in ("start", "llm_errors", "cell_failed", "stall", "finished")),
            "every event is printed as a line")
    return ("start, 402/timeout/429 streaks (once each, re-armed by a success), failed/blocked/stalled cells, "
            "finished; one message per poll, daily cap; the grid directory untouched")


# ---- balance ------------------------------------------------------------------------------------

def check_balance() -> str:
    from surprise.notify import watch as W

    tmp = tmpdir("balance")
    out = _grid_dir(tmp)
    now = [time.time()]
    net = _Net()
    with env_var(C.KEY_ENV, _KEY), env_var(C.PUSH_ENV, None), net.on():
        net.key = (200, {"data": {"limit": 5.0, "limit_remaining": 0.5, "usage": 4.5}})
        w = W.Watcher(out, notifier=_Inbox(), clock=lambda: now[0], balance_usd=1.0, balance_every_minutes=30)
        first = _poll(w, out)
        require(("balance", None, "low") in first, f"$0.5 left under a $1 threshold: {first}")
        asks = net.to(C.KEY_INFO_URL)
        require(len(asks) == 1 and asks[0]["method"] == "GET" and asks[0]["auth"] == f"Bearer {_KEY}",
                f"key info request: {asks}")
        require(_poll(w, out) == [] and len(net.to(C.KEY_INFO_URL)) == 1, "no second check inside the interval")
        now[0] += 31 * 60
        net.key = (200, {"data": {"limit": 5.0, "limit_remaining": 0.0, "usage": 5.0}})
        require(_poll(w, out) == [("balance", None, "empty")], "nothing left")
        now[0] += 31 * 60
        require(_poll(w, out) == [] and len(net.to(C.KEY_INFO_URL)) == 3, "each level is reported once")

        net.key = (200, {"data": {"limit": None, "limit_remaining": None, "usage": 1.0}})
        unlimited = W.Watcher(_grid_dir(tmpdir("balance-null")), notifier=_Inbox(), clock=lambda: now[0])
        require([e for e in unlimited.poll() if e.kind == "balance"] == [], "a key without a limit raises no alarm")
        net.key = (401, {"error": {"code": 401, "message": "gate"}})
        bad = W.Watcher(_grid_dir(tmpdir("balance-401")), notifier=_Inbox(), clock=lambda: now[0])
        require(("balance", None, "auth") in [(e.kind, e.cell, e.cause) for e in bad.poll()], "401 on the key check")
        net.broken = True
        down = W.Watcher(_grid_dir(tmpdir("balance-down")), notifier=_Inbox(), clock=lambda: now[0])
        require([e for e in down.poll() if e.kind == "balance"] == [], "an unreachable endpoint is no balance alarm")
        net.broken = False
        before = len(net.requests)
        W.Watcher(_grid_dir(tmpdir("balance-nollm"), glm=False), notifier=_Inbox(), clock=lambda: now[0]).poll()
        require(len(net.requests) == before, f"a grid without a {C.NEW_TIER} arm must not ask for the balance")
    with env_var(C.KEY_ENV, None), env_var(C.PUSH_ENV, None), net.on():
        before = len(net.requests)
        W.Watcher(_grid_dir(tmpdir("balance-nokey")), notifier=_Inbox(), clock=lambda: now[0]).poll()
        require(len(net.requests) == before, "without a key there is no balance check")
    require(all(r["url"] == C.KEY_INFO_URL for r in net.requests), "the watcher called another address")
    return (f"{C.KEY_INFO_URL} with the {C.KEY_ENV} key every 30 minutes on {C.NEW_TIER} grids: low and empty "
            f"once each, 401 reported, no limit or no answer is no alarm")


# ---- cli ----------------------------------------------------------------------------------------

def check_cli() -> str:
    import subprocess

    from .s15 import clean_env

    env = {k: v for k, v in clean_env().items() if k.upper() != C.PUSH_ENV}
    proc = py(["-m", "surprise.notify.pushplus", "t", "c"], timeout=120, env=env)
    require(proc.returncode == 2, f"pushplus without a token exited {proc.returncode}, expected 2")

    tmp = tmpdir("cli")
    out = _grid_dir(tmp)
    for label in _labels(out):
        _end(out, label, "done", 0)
    before = _tree(out)
    proc = py(["-m", "surprise.notify.watch", str(out), "--interval", "1"], timeout=120, env=env)
    require(proc.returncode == 0 and "finished" in proc.stdout, f"watch on a finished grid: {proc.returncode} "
            f"{proc.stdout[-300:]} {proc.stderr[-300:]}")
    require(_tree(out) == before, "the watcher changed the grid directory")

    pending = _grid_dir(tmpdir("cli-pid"))
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3)"])
    # Reap the child as soon as it ends, as the shell does for the grid; a zombie still has its PID.
    threading.Thread(target=child.wait, daemon=True).start()
    started = time.monotonic()
    try:
        proc = py(["-m", "surprise.notify.watch", str(pending), "--pid", str(child.pid), "--interval", "1"],
                  timeout=120, env=env)
    finally:
        child.wait(timeout=30)
    require(proc.returncode == 0 and "exited" in proc.stdout, f"watch --pid: {proc.returncode} {proc.stdout[-300:]} "
            f"{proc.stderr[-300:]}")
    require(time.monotonic() - started < 60, "the watcher took too long to see the process end")
    return "pushplus CLI exits 2 without a token; watch exits on 'finished' and on the grid process ending (--pid)"


# ---- scope --------------------------------------------------------------------------------------

def check_scope() -> str:
    tags = git("tag", "--list", C.DONE_TAG).split()
    if C.DONE_TAG in tags:
        changed = git("diff", "--name-only", C.BASE_TAG, C.DONE_TAG).split("\n")
        frozen = git("diff", "--name-only", C.BASE_TAG, C.DONE_TAG, "--", *C.FROZEN_PATHS).split("\n")
        where = f"{C.BASE_TAG}..{C.DONE_TAG}"
    else:
        changed = git("diff", "--name-only", C.BASE_TAG).split("\n")
        changed += git("ls-files", "--others", "--exclude-standard").split("\n")
        frozen = git("diff", "--name-only", C.BASE_TAG, "--", *C.FROZEN_PATHS).split("\n")
        where = f"{C.BASE_TAG}..work tree"
    changed = sorted({path.strip() for path in changed if path.strip()})
    frozen = sorted({path.strip() for path in frozen if path.strip()})
    require(not frozen, f"frozen paths changed ({where}): {frozen[:10]}")
    outside = [path for path in changed if not any(path.startswith(prefix) for prefix in C.ALLOWED_CHANGES)]
    require(not outside, f"changes outside S19 scope ({where}): {outside[:10]}")
    return f"{len(changed)} paths changed ({where}), all in scope; harness and roles/constants.py untouched"


# ---- main ---------------------------------------------------------------------------------------

GROUPS: dict[str, Callable[[], str]] = {
    "transport": check_transport,
    "gateway": check_gateway,
    "replay": check_replay,
    "grid": check_grid,
    "prices": check_prices,
    "pushplus": check_pushplus,
    "reason": check_reason,
    "watch": check_watch,
    "balance": check_balance,
    "cli": check_cli,
    "scope": check_scope,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S19 gate (GLM 5.3 Flash on OpenRouter; pushplus alerts)")
    parser.add_argument("--only", nargs="+", choices=list(GROUPS), metavar="GROUP")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(FRAMEWORK))
    selected = args.only or list(GROUPS)
    failed = 0
    for name in selected:
        started = time.monotonic()
        try:
            detail = GROUPS[name]()
        except GateFailure as exc:
            failed += 1
            print(f"[FAIL] {name}: {_ascii(exc)}", flush=True)
        except Exception as exc:  # noqa: BLE001 - a crash in a check is a failure, reported with its type
            failed += 1
            print(f"[FAIL] {name}: {type(exc).__name__}: {_ascii(exc)}", flush=True)
        else:
            print(f"[PASS] {name}: {_ascii(detail)} ({time.monotonic() - started:.0f}s)", flush=True)
    passed = len(selected) - failed
    label = "" if not args.only else f" [only: {', '.join(selected)}]"
    print(f"S19 GATE{label}: {'PASS' if failed == 0 else 'FAIL'} ({passed}/{len(selected)} groups passed)", flush=True)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
