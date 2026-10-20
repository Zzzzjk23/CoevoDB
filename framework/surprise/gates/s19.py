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

The E1 result groups (SESSIONS S19) are added when the formal results are copied back.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import shutil
import sys
import tempfile
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
    "scope": check_scope,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S19 gate (GLM 5.3 Flash on OpenRouter)")
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
