"""S9 gate: the LLM gateway, the implementer and the hypothesis conjecturer.

Usage (from ``framework/``)::

    python -m surprise.gates.s09                         # everything
    python -m surprise.gates.s09 --only cache reject cap

Exit code 0 = pass. Groups, following the S9 section of SESSIONS.md:

``isolation``          the roles import no model client until a real transport is built;
                       the loop, the Hunter and the Diagnoser never import the roles;
                       the transport reuses agents/base_agent.py and llm/ledger.py;
``constants``          the gateway and role constants have the planned values;
``cache``              key = prompt hash + model + seed; a cache hit makes no network
                       call and a replay gives the same reply; the call ledger;
``reject``             a reply without the prediction field is refused, live and replayed;
``cap``                the per-session call cap, and the environment ceiling;
``source``             the read-only source reader and the two pinned engine checkouts;
``implementer``        spec -> schema, data, query, accepted by the phi check (scripted replies);
``conjecturer``        mechanism, trigger and falsifiable predictions on DF-A, registered as
                       pending experiments and proposed through the workbench (scripted replies);
``wiring``             the loop with every role off is S8's loop; with roles on it records
                       their work; with a cap of 0 it still runs;
``implementer_report`` the phi-check pass rate of the implementer over 30 specs (pinned replies);
``dfa``                the conjecturer's real hypothesis on DF-A with its predictions (pinned reply);
``replay``             a recorded run of the loop with roles on, replayed from its cache with no
                       network: same experiments, same conjectures.

The last three read replies the orchestrator recorded once with real calls and committed
under ``gates/s09_llm/``; they fail until then. Tables live in ``s09_cases.py``. Output is
ASCII only. No group makes a network call.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from . import s09_cases as C
from .s06 import GateFailure, _ascii, require

FRAMEWORK = Path(__file__).resolve().parents[2]
LLM_DIR = Path(__file__).resolve().parent / "s09_llm"
DUMMY_KEY = "sk-s09gate" + "0123456789abcdef0123456789"


def roles() -> Any:
    import surprise.roles as R

    return R


def theory() -> Any:
    from surprise import theory as T

    return T


def features() -> Any:
    from surprise import features as F

    return F


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def tmpdir(tag: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=f"s09-{tag}-"))


def run_probe(code: str, *, env: dict[str, str] | None = None, timeout: int = 900) -> dict:
    proc = subprocess.run([sys.executable, "-c", code], cwd=FRAMEWORK, capture_output=True, text=True,
                          timeout=timeout, env=env)
    require(proc.returncode == 0, f"probe failed: {proc.stderr[-800:]}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def clean_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k.upper() not in ("DEEPSEEK_API_KEY", C.CONSTANTS["CAP_ENV"])}
    return env


class Script:
    """A transport that answers from a list (or by role) and remembers every request."""

    def __init__(self, replies: Any = ()) -> None:
        self.replies = replies if callable(replies) or isinstance(replies, dict) else list(replies)
        self.calls: list[dict[str, Any]] = []

    def complete(self, *, model: str, prompt: str, temperature: float, max_tokens: int, role: str) -> Any:
        self.calls.append({"model": model, "prompt": prompt, "temperature": temperature,
                           "max_tokens": max_tokens, "role": role})
        if isinstance(self.replies, dict):
            reply = self.replies[role]
        elif callable(self.replies):
            reply = self.replies(prompt)
        else:
            reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return roles().Completion(text=text, input_tokens=len(prompt) // 4, output_tokens=len(text) // 4)


class Refuse:
    """A transport that must never be reached: replays use the cache only."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, **_: Any) -> Any:
        self.calls += 1
        raise RuntimeError("the network was used during a replay")


def gateway(root: Path, transport: Any, *, max_calls: int | None = 20, ledger: bool = True) -> Any:
    return roles().Gateway(cache_dir=root / "cache", ledger_path=(root / "calls.jsonl") if ledger else None,
                           max_calls=max_calls, transport=transport)


def ledger_lines(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def scan_for(root: Path, needle: str) -> list[str]:
    found = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and needle in path.read_text(encoding="utf-8", errors="replace"):
            found.append(path.name)
    return found


def rows_of(path: Path, drop: tuple[str, ...] = ("elapsed_s",)) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            for key in drop:
                row.pop(key, None)
            rows.append(row)
    return rows


def rows_hash(rows: list[dict[str, Any]]) -> str:
    return sha(json.dumps(rows, sort_keys=True, separators=(",", ":")))


# ---- isolation, constants ---------------------------------------------------------------

def check_isolation() -> str:
    modules = list(C.LLM_MODULES)
    roles_probe = ("import sys, json\n"
                   "import surprise.roles, surprise.roles.gateway, surprise.roles.cache, surprise.roles.source\n"
                   "import surprise.roles.constants, surprise.roles.implementer, surprise.roles.conjecturer\n"
                   "import surprise.roles.runtime\n"
                   f"print(json.dumps(sorted(m for m in {modules!r} if m in sys.modules)))\n")
    bad = run_probe(roles_probe, env=clean_env())
    require(bad == [], f"importing the roles must not load a model client or old agent code: {bad}")
    loop_probe = ("import sys, json\n"
                  "import surprise.hunter, surprise.diagnoser, surprise.experiments.loop, surprise.harness.evaluate\n"
                  "print(json.dumps(sorted(m for m in sys.modules if m == 'surprise.roles' or m.startswith('surprise.roles.'))))\n")
    loaded = run_probe(loop_probe, env=clean_env())
    require(loaded == [], f"the loop, the Hunter, the Diagnoser and the harness must not import the roles: {loaded}")
    transport_probe = ("import sys, json\n"
                       "import surprise.roles.transport as t\n"
                       "from agents.base_agent import BaseAgent\n"
                       "print(json.dumps({'reuse': ['agents.base_agent' in sys.modules, 'llm.ledger' in sys.modules],\n"
                       "                  'agent': any(isinstance(v, type) and v is not BaseAgent and issubclass(v, BaseAgent)\n"
                       "                               for v in vars(t).values())}))\n")
    reuse = run_probe(transport_probe, env=clean_env())
    require(reuse["reuse"] == [True, True], "the DeepSeek transport reuses agents/base_agent.py and llm/ledger.py")
    require(reuse["agent"], "the transport builds on BaseAgent (old code reused, not copied)")
    harness = [p.name for p in (FRAMEWORK / "surprise" / "harness").rglob("*.py")
               if "surprise.roles" in p.read_text(encoding="utf-8") or "from ..roles" in p.read_text(encoding="utf-8")]
    require(harness == [], f"the label path (harness) never reaches the roles: {harness}")
    return "roles load no model client until a transport is built; loop, Hunter, Diagnoser, harness never import them; transport reuses BaseAgent and the old ledger"


def check_constants() -> str:
    R = roles()
    have = R.constants.as_dict()
    for name, value in C.CONSTANTS.items():
        require(name in have and have[name] == value and type(have[name]) is type(value),
                f"roles constant {name} must be {value!r}, got {have.get(name)!r}")
    tiers = have["TIERS"]
    require(len(tiers) >= 2 and len(set(tiers.values())) == len(tiers), f"at least two distinct model tiers: {tiers}")
    tmp = tmpdir("const")
    manifest = gateway(tmp, Script()).manifest()
    require(manifest.get("tiers") == C.TIERS and manifest.get("max_calls") == 20,
            f"the gateway manifest records tiers and the cap: {manifest}")
    saved = os.environ.pop(C.CONSTANTS["CAP_ENV"], None)
    try:
        default = roles().Gateway(cache_dir=tmp / "default", transport=None)
        require(default.max_calls == C.CONSTANTS["DEFAULT_MAX_CALLS"], f"the default cap: {default.max_calls}")
    finally:
        if saved is not None:
            os.environ[C.CONSTANTS["CAP_ENV"]] = saved
    require(isinstance(manifest.get("constants"), dict) and manifest["constants"].get("TIERS") == C.TIERS,
            "the gateway manifest carries the constants")
    return f"{len(C.CONSTANTS)} constants as planned; tiers {tiers}"


# ---- cache, reject, cap ------------------------------------------------------------

def check_cache() -> str:
    R = roles()
    tmp = tmpdir("cache")
    prompt = "Write a query. Reply in JSON with a prediction."
    good = {"query": "SELECT 1", "prediction": {"expect": "pass"}}
    script = Script([good, good, good, good])
    saved = os.environ.get("DEEPSEEK_API_KEY")
    os.environ["DEEPSEEK_API_KEY"] = DUMMY_KEY
    try:
        gw = gateway(tmp, script)
        r1 = gw.call("implementer", prompt, tier="fast", seed=0)
        r2 = gw.call("implementer", prompt, tier="fast", seed=0)
        r3 = gw.call("implementer", prompt, tier="fast", seed=1)
        r4 = gw.call("conjecturer", prompt, tier="strong", seed=0)
    finally:
        if saved is None:
            os.environ.pop("DEEPSEEK_API_KEY", None)
        else:
            os.environ["DEEPSEEK_API_KEY"] = saved
    require((r1.status, r1.source, r2.status, r2.source) == ("ok", "network", "ok", "cache"),
            f"the second identical call is a cache hit: {(r1.status, r1.source, r2.status, r2.source)}")
    require(r1.data == r2.data == good and r1.text == r2.text, "a cache hit returns the same reply")
    require(r3.source == "network" and r4.source == "network" and len(script.calls) == 3,
            f"a new seed or a new model is a new call: {len(script.calls)} transport calls")
    require([c["model"] for c in script.calls] == [C.TIERS["fast"], C.TIERS["fast"], C.TIERS["strong"]],
            f"the tier picks the model: {[c['model'] for c in script.calls]}")
    expected_key = sha(f"{sha(prompt)}\n{C.TIERS['fast']}\n0")
    require(r1.key == expected_key == R.cache_key(prompt, C.TIERS["fast"], 0), "key = sha256(prompt sha256, model, seed)")
    require(r1.key != r3.key != r4.key, "seed and model change the key")
    entry_path = tmp / "cache" / r1.key[:2] / f"{r1.key}.json"
    require(entry_path.is_file(), f"cache entry at <cache>/<key[:2]>/<key>.json: {entry_path}")
    entry = json.loads(entry_path.read_text(encoding="utf-8"))
    require(set(C.CACHE_ENTRY_KEYS) <= set(entry) and entry["prompt"] == prompt and entry["text"] == r1.text
            and entry["model"] == C.TIERS["fast"] and entry["seed"] == 0, f"cache entry fields: {sorted(entry)}")
    # replay: a fresh gateway on the same cache, a transport that must not be used
    refuse = Refuse()
    gw2 = gateway(tmp, refuse, ledger=False)
    again = [gw2.call("implementer", prompt, tier="fast", seed=0), gw2.call("implementer", prompt, tier="fast", seed=1),
             gw2.call("conjecturer", prompt, tier="strong", seed=0)]
    require(refuse.calls == 0 and gw2.network_calls == 0, "a replay from the cache makes no network call")
    require([(a.status, a.source, a.key, a.text, a.data) for a in again]
            == [(b.status, "cache", b.key, b.text, b.data) for b in (r1, r3, r4)], "a replay gives the same replies")
    offline = gateway(tmp, None, ledger=False)
    hit, miss = offline.call("implementer", prompt, tier="fast", seed=0), offline.call("implementer", "new", tier="fast", seed=0)
    require((hit.status, hit.source) == ("ok", "cache") and (miss.status, miss.source) == ("miss", None),
            f"offline: hits served, misses reported: {(hit.status, hit.source, miss.status, miss.source)}")
    # an entry that does not belong to its request is not served
    forged = dict(entry, prompt="something else")
    entry_path.write_text(json.dumps(forged), encoding="utf-8")
    forged_reply = gateway(tmp, None, ledger=False).call("implementer", prompt, tier="fast", seed=0)
    require(forged_reply.status == "miss", f"an entry whose prompt does not hash to its key is not served: {forged_reply.status}")
    # ledger and accounting
    lines = ledger_lines(tmp / "calls.jsonl")
    require(len(lines) == 4 and all(set(line) == set(C.LEDGER_KEYS) for line in lines),
            f"one ledger line per call with keys {C.LEDGER_KEYS}: {[sorted(l) for l in lines[:1]]}")
    require([l["source"] for l in lines] == ["network", "cache", "network", "network"]
            and [l["seq"] for l in lines] == [1, 2, 3, 4], f"ledger sources: {[l['source'] for l in lines]}")
    totals = gw.totals()
    impl = totals["by_role"]["implementer"]
    require(set(C.ROLE_TOTAL_KEYS) <= set(impl) and (impl["calls"], impl["network"], impl["cache"], impl["ok"]) == (3, 2, 1, 3)
            and totals["by_role"]["conjecturer"]["network"] == 1 and totals["network"] == 3 == gw.network_calls,
            f"accounting by role: {totals}")
    leaked = scan_for(tmp, DUMMY_KEY)
    require(leaked == [], f"the key never reaches the cache or the ledger: {leaked}")
    return "key = prompt hash + model + seed; hits make no call; replay identical; forged entry refused; ledger and per-role totals"


def check_reject() -> str:
    R = roles()
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
    for text, data, reason in cases:
        got = R.parse_reply(text)
        require(tuple(got) == (data, reason), f"parse_reply({text!r}) = {got}, expected {(data, reason)}")
    tmp = tmpdir("reject")
    script = Script([text for text, _, _ in cases])
    gw = gateway(tmp, script)
    live = [gw.call("implementer", f"prompt {i}", tier="fast", seed=0) for i in range(len(cases))]
    want = ["rejected" if data is None else "ok" for _, data, _ in cases]
    require([r.status for r in live] == want, f"live statuses {[r.status for r in live]}, expected {want}")
    require(all(r.data is None and r.reason == reason for r, (_, data, reason) in zip(live, cases) if data is None),
            "a refused reply carries no data and says why")
    replay = gateway(tmp, Refuse(), ledger=False)
    again = [replay.call("implementer", f"prompt {i}", tier="fast", seed=0) for i in range(len(cases))]
    require([(r.status, r.source, r.reason) for r in again] == [(r.status, "cache", r.reason) for r in live],
            "a refused reply is refused again on replay, from the cache")
    require(gw.totals()["by_role"]["implementer"]["rejected"] == want.count("rejected"), "refusals are counted per role")
    # role level: the implementer never extracts phi from a refused reply
    def no_extract(_case: Any) -> Any:
        raise GateFailure("phi was extracted from a refused reply")

    impl = R.Implementer(gateway=gateway(tmpdir("reject-impl"), Script(['{"query": "SELECT 1"}'] * 2)),
                         extract=no_extract, seed=0)
    attempt = impl.implement(spec_dict(["ast:stmt:select"]))
    require(attempt.status == "rejected" and not attempt.ok and attempt.case is None and attempt.tries == 2,
            f"implementer: a reply without a prediction is refused on every try: {attempt.status}, {attempt.tries} tries")
    bad_expect = {"setup": [], "query": "SELECT 1", "predicate": None, "prediction": {"expect": "maybe"}}
    attempt = R.Implementer(gateway=gateway(tmpdir("reject-impl2"), Script([bad_expect] * 2)),
                            extract=no_extract, seed=0).implement(spec_dict(["ast:stmt:select"]))
    require(attempt.status == "rejected", f"implementer: prediction.expect must be pass or fail: {attempt.status}")
    return f"{len(cases)} replies parsed as planned; refusals replay as refusals; the implementer refuses before phi"


def check_cap() -> str:
    tmp = tmpdir("cap")
    script = Script([{"prediction": "a"}, {"prediction": "b"}, {"prediction": "c"}])
    gw = gateway(tmp, script, max_calls=2)
    got = [gw.call("implementer", p, tier="fast", seed=0) for p in ("p1", "p2", "p3")]
    require([r.status for r in got] == ["ok", "ok", "blocked"] and got[2].source is None and len(script.calls) == 2,
            f"the third distinct call is blocked: {[r.status for r in got]}, {len(script.calls)} transport calls")
    hit = gw.call("implementer", "p1", tier="fast", seed=0)
    require((hit.status, hit.source) == ("ok", "cache"), "a cache hit is served after the cap is reached")
    require(gw.totals()["by_role"]["implementer"]["blocked"] == 1 and gw.max_calls == 2, "blocked calls are counted")
    zero = Script([{"prediction": "a"}])
    blocked = gateway(tmpdir("cap0"), zero, max_calls=0).call("implementer", "p", tier="fast", seed=0)
    require(blocked.status == "blocked" and zero.calls == [], "max_calls 0 makes no call at all")
    env = C.CONSTANTS["CAP_ENV"]
    saved = os.environ.get(env)
    os.environ[env] = "1"
    try:
        script = Script([{"prediction": "a"}, {"prediction": "b"}])
        capped = gateway(tmpdir("capenv"), script, max_calls=5)
        statuses = [capped.call("implementer", p, tier="fast", seed=0).status for p in ("p1", "p2")]
        require(statuses == ["ok", "blocked"] and capped.max_calls == 1 and capped.manifest()["max_calls"] == 1,
                f"{env}=1 lowers a cap of 5 to 1: {statuses}, {capped.max_calls}")
    finally:
        if saved is None:
            os.environ.pop(env, None)
        else:
            os.environ[env] = saved
    flaky = Script([RuntimeError("boom"), {"prediction": "ok"}])
    fg = gateway(tmpdir("caperr"), flaky, max_calls=5)
    first, second = fg.call("implementer", "p", tier="fast", seed=0), fg.call("implementer", "p", tier="fast", seed=0)
    require((first.status, first.source, second.status, second.source) == ("error", "network", "ok", "network")
            and fg.network_calls == 2, "a failed call counts against the cap and is not cached")
    try:
        gateway(tmpdir("cap-tier2"), Script([{"prediction": 1}])).call("implementer", "p", tier="huge", seed=0)
    except ValueError:
        pass
    else:
        raise GateFailure("an unknown tier is a ValueError")
    return "cap 2 blocks the third call; cache served past the cap; cap 0 calls nothing; env ceiling; errors count, not cached"


def spec_dict(required: list[str], forbidden: list[str] = (), *, engine: str = "duckdb",
              oracle: str = "plan_variant") -> dict[str, Any]:
    return {"engine": engine, "oracle": oracle, "required": list(required), "forbidden": list(forbidden),
            "data_properties": []}


# ---- source -----------------------------------------------------------------------

def check_source() -> str:
    R = roles()
    root = tmpdir("src")
    (root / "src" / "a").mkdir(parents=True)
    (root / "src" / "a" / "b.cpp").write_text("\n".join(f"line {i} needle" if i == 7 else f"line {i}" for i in range(1, 11)) + "\n",
                                              encoding="utf-8")
    (root / "src" / "c.rs").write_text("fn needle() {}\n", encoding="utf-8")
    outside = root.parent / f"{root.name}-outside.txt"
    outside.write_text("secret\n", encoding="utf-8")
    reader = R.SourceReader(root)
    snip = reader.read("src/a/b.cpp", 2, 4)
    require((snip.path, snip.start, snip.end, snip.text) == ("src/a/b.cpp", 2, 4, "line 2\nline 3\nline 4"),
            f"read returns exact lines: {snip}")
    tail = reader.read("src/a/b.cpp", 9, 50)
    require((tail.end, tail.text) == (10, "line 9\nline 10"), f"read clips at the end of the file: {tail}")
    hits = reader.grep("needle", under="src")
    require([(h.path, h.line, h.text) for h in hits] == [("src/a/b.cpp", 7, "line 7 needle"), ("src/c.rs", 1, "fn needle() {}")],
            f"grep finds both, in path order: {hits}")
    require(reader.exists("src/c.rs") and not reader.exists("src/none.rs"), "exists")
    for bad in ("../" + outside.name, str(outside), "src/../../" + outside.name, "src/none.cpp", "src/a/b.cpp\x00"):
        try:
            reader.read(bad)
        except R.SourceError as exc:
            require(isinstance(exc, ValueError), "SourceError is a ValueError")
        else:
            raise GateFailure(f"read({bad!r}) must raise SourceError")
    try:
        reader.read("src/a/b.cpp", 0, 3)
    except R.SourceError:
        pass
    else:
        raise GateFailure("a start line below 1 is a SourceError")
    require(outside.read_text(encoding="utf-8") == "secret\n", "nothing outside the root was touched")
    readers = R.open_sources()
    require(set(readers) == {"duckdb", "datafusion"}, f"two engine checkouts: {sorted(readers)}")
    for engine, reader in readers.items():
        require(reader.commit == C.CONSTANTS["SOURCE_COMMITS"][engine],
                f"{engine} checkout at the pinned commit: {reader.commit}")
    require(C.DFA_SOURCE_MARK in "\n".join(h.text for h in readers["datafusion"].grep(C.DFA_SOURCE_MARK, under="datafusion/expr")),
            "the DataFusion checkout has the set-operation lowering")
    require(readers["duckdb"].exists(C.DUCKDB_SOURCE_PATH), f"the DuckDB checkout has {C.DUCKDB_SOURCE_PATH}")
    return f"confined, exact, read-only; checkouts at {', '.join(f'{e} {r.commit[:12]}' for e, r in sorted(readers.items()))}"


# ---- implementer --------------------------------------------------------------------

DFA_LIKE_SETUP = ["CREATE TABLE t(v INTEGER)", "INSERT INTO t VALUES (1),(1),(2)", "CREATE TABLE u(v INTEGER)",
                  "INSERT INTO u VALUES (1)"]


def impl_reply(query: str, expect: str = "pass", setup: list[str] | None = None) -> dict[str, Any]:
    return {"setup": list(DFA_LIKE_SETUP if setup is None else setup), "query": query, "predicate": None,
            "prediction": {"expect": expect}}


def check_implementer() -> str:
    R = roles()
    F = features()
    spec = spec_dict(["ast:set_op:except_all", "data:setop:left_has_dups"])
    good = impl_reply("SELECT v FROM t EXCEPT ALL SELECT v FROM u")
    union = impl_reply("SELECT v FROM t UNION ALL SELECT v FROM u")
    bad_case = {"setup": [], "query": "", "predicate": None, "prediction": {"expect": "pass"}}

    def make(script: Any, tag: str, **kw: Any) -> Any:
        return R.Implementer(gateway=gateway(tmpdir(tag), script, **kw), extract=F.extract, seed=0)

    a = make(Script([good]), "impl-a").implement(spec)
    require(a.ok and a.status == "ok" and a.tries == 1 and a.first_ok and a.case is not None
            and a.case.query == good["query"] and a.phi is not None and a.phi.engine == "duckdb"
            and a.missing == () and a.forbidden == () and a.expect == "pass",
            f"a reply that meets the spec is accepted at once: {a.status}, tries {a.tries}, missing {a.missing}")
    require(set(C.ATTEMPT_STATUSES) >= {a.status} and a.spec == spec, "attempt carries its spec")
    script_b = Script([union, good])
    root_b = tmpdir("impl-b")
    b = R.Implementer(gateway=gateway(root_b, script_b), extract=F.extract, seed=0).implement(spec)
    require(b.ok and b.tries == 2 and not b.first_ok and len(script_b.calls) == 2,
            f"spec unmet, then met on the retry: ok {b.ok}, tries {b.tries}")
    p1, p2 = script_b.calls[0]["prompt"], script_b.calls[1]["prompt"]
    require(p1 != p2 and union["query"] in p2 and "ast:set_op:except_all" in p2,
            "the retry prompt quotes the previous query and names what was missing")
    require(script_b.calls[0]["model"] == C.TIERS[C.CONSTANTS["IMPLEMENTER_TIER"]]
            and script_b.calls[0]["temperature"] == C.CONSTANTS["IMPLEMENTER_TEMPERATURE"]
            and script_b.calls[0]["max_tokens"] == C.CONSTANTS["IMPLEMENTER_MAX_TOKENS"],
            f"the implementer uses its tier and settings: {script_b.calls[0]['model']}")
    require(R.implementer_prompt(spec) == R.implementer_prompt(dict(spec)) == p1,
            "the first prompt is a pure function of the spec")
    c = make(Script([union, union]), "impl-c").implement(spec)
    require((c.ok, c.status, c.tries) == (False, "spec_unmet", 2) and "ast:set_op:except_all" in c.missing,
            f"unmet on both tries: {c.status}, missing {c.missing}")
    d = make(Script([bad_case, bad_case]), "impl-d").implement(spec)
    require((d.ok, d.status, d.case) == (False, "bad_case", None), f"an unusable case: {d.status}")
    e = R.Implementer(gateway=gateway(root_b, Refuse(), ledger=False), extract=F.extract, seed=0).implement(spec)
    require((e.ok, e.tries, e.case, e.missing, e.keys) == (b.ok, b.tries, b.case, b.missing, b.keys),
            "the same attempt replays from the cache with no network")
    f = make(Script([good]), "impl-f", max_calls=0).implement(spec)
    require((f.status, f.tries, f.ok) == ("blocked", 1, False), f"blocked at the cap stops at once: {f.status}, {f.tries}")
    return "accepted, retried with feedback, unmet, bad case, replayed, blocked"


# ---- conjecturer --------------------------------------------------------------------

_DFA: dict[str, Any] = {}


def dfa() -> dict[str, Any]:
    """DF-A on the real engines: a fresh workbench where it opens a family."""
    if _DFA:
        return _DFA
    from surprise.harness.evaluate import evaluate_final
    from surprise.harness.ledger import Ledger
    from surprise.harness.manifest import build_manifest

    from . import s04 as G4

    T, F = theory(), features()
    tmp = tmpdir("dfa")
    wb = T.Workbench.create(tmp / "theory")
    ledger = Ledger(tmp / "ledger.sqlite")
    run_id = "s09-dfa"
    try:
        ledger.start_run(run_id, T.extend_manifest(build_manifest(run_id)))
        case = G4.load(C.DFA_CASE)
        example = F.extract(case)
        prediction = wb.predict(example, C.DFA_ORACLE)
        record = evaluate_final(case, C.DFA_ORACLE, ledger=ledger, run_id=run_id, purpose="bootstrap",
                                phi=example.to_dict(), theory_version=wb.theory.version,
                                p_t=prediction.p_fail_valid, diagnose=True)
        outcome = wb.observe(example, record.label, record.record_id, prediction=prediction)
    finally:
        ledger.close()
    require(record.label.y == "fail" and outcome.observation.opened is not None,
            f"DF-A must fail and open a family: {record.label.y}, opened {outcome.observation.opened}")
    _DFA.update(tmp=tmp, theory=tmp / "theory", record=record, outcome=outcome, phi=example)
    return _DFA


def bench_copy(tag: str) -> Any:
    ctx = dfa()
    target = tmpdir(tag) / "theory"
    shutil.copytree(ctx["theory"], target)
    return theory().Workbench.open(target)


def conjecture_reply(trigger: Any = None, predictions: Any = None, mechanism: Any = C.MECHANISM) -> dict[str, Any]:
    reply: dict[str, Any] = {}
    if mechanism is not None:
        reply["mechanism"] = mechanism
    reply["trigger"] = list(C.GOOD_TRIGGER if trigger is None else trigger)
    if predictions is not False:
        reply["prediction"] = [dict(p) for p in (C.GOOD_PREDICTIONS if predictions is None else predictions)]
    return reply


def conjecturer(script: Any, tag: str, *, book_path: Path | None = None, max_calls: int = 20) -> tuple[Any, Any]:
    R = roles()
    root = tmpdir(tag)
    book = R.ConjectureBook(book_path if book_path is not None else root / "conjectures.jsonl")
    agent = R.Conjecturer(gateway=gateway(root, script, max_calls=max_calls), extract=features().extract, book=book,
                          sources=R.open_sources(), seed=C.CONJECTURE_SEED)
    return agent, book


def check_conjecturer() -> str:
    R, T, F = roles(), theory(), features()
    ctx = dfa()
    record, outcome = ctx["record"], ctx["outcome"]
    readers = R.open_sources()
    # source selection
    wb0 = bench_copy("sel")
    hypothesis = wb0.theory.get(outcome.observation.opened)
    picked = R.select_sources("datafusion", hypothesis, ctx["phi"], readers)
    require(picked == R.select_sources("datafusion", hypothesis, ctx["phi"], readers), "source selection is deterministic")
    require(any(s.path == C.DFA_SOURCE_PATH and C.DFA_SOURCE_MARK in s.text for s in picked),
            f"DF-A: the selection includes {C.DFA_SOURCE_MARK} in {C.DFA_SOURCE_PATH}: {[s.path for s in picked]}")
    require(len({s.path for s in picked}) <= C.CONSTANTS["SOURCE_MAX_FILES"]
            and sum(s.end - s.start + 1 for s in picked) <= C.CONSTANTS["SOURCE_MAX_LINES"],
            "the selection stays within its file and line budget")
    duck = dataclasses.replace(hypothesis, engine="duckdb", interventions=C.DUCKDB_FIX)
    duck_phi = F.make_phi("duckdb", ("ast:stmt:select", "ast:clause:where"), {"ast": "ok", "plan": "ok", "data": "ok"})
    picked_duck = R.select_sources("duckdb", duck, duck_phi, readers)
    require(any(s.path == C.DUCKDB_SOURCE_PATH for s in picked_duck),
            f"DuckDB fix set {C.DUCKDB_FIX}: the selection includes {C.DUCKDB_SOURCE_PATH}: {[s.path for s in picked_duck]}")
    # no new family: nothing to do
    script = Script([conjecture_reply()])
    agent, book = conjecturer(script, "none")
    quiet = SimpleNamespace(observation=SimpleNamespace(opened=None))
    require(agent.after(bench_copy("none"), record, quiet) is None and script.calls == [], "no new family, no call")
    # a good conjecture
    script = Script([conjecture_reply()])
    agent, book = conjecturer(script, "good")
    wb = bench_copy("good")
    before = len(wb.edits())
    conj = agent.after(wb, record, outcome)
    require(conj is not None and conj.status == "registered", f"registered: {getattr(conj, 'status', None)} {getattr(conj, 'reason', None)}")
    prompt = script.calls[0]["prompt"]
    require(script.calls[0]["model"] == C.TIERS[C.CONSTANTS["CONJECTURER_TIER"]]
            and script.calls[0]["max_tokens"] == C.CONSTANTS["CONJECTURER_MAX_TOKENS"], "the conjecturer uses its tier")
    require(C.DFA_SOURCE_PATH in prompt and C.DFA_SOURCE_MARK in prompt and "EXCEPT ALL" in prompt.upper(),
            "the prompt carries the case and the selected DataFusion source")
    require(record.record_id not in prompt and outcome.observation.opened not in prompt.split(),
            "the prompt carries no record or hypothesis id (the cache key must not depend on them)")
    reg = None
    want = [{"spec": T.Spec(engine="datafusion", oracle=C.DFA_ORACLE, required=tuple(p["required"]),
                            forbidden=tuple(p["forbidden"]), data_properties=tuple(p["data_properties"])).to_dict(),
             "expect": p["expect"], "why": p["why"]} for p in C.GOOD_PREDICTIONS]
    require([dict(p) for p in conj.predictions] == want, f"predictions as specs on the hypothesis scope: {conj.predictions}")
    require(tuple(conj.trigger) == tuple(T.reduce_conjunction(C.GOOD_TRIGGER, reg)) and conj.mechanism == C.MECHANISM
            and conj.engine == "datafusion" and conj.oracle == C.DFA_ORACLE and conj.record_id == record.record_id,
            f"trigger and mechanism kept: {conj.trigger}")
    edits = wb.edits()
    require(len(edits) == before + 1, f"one proposal through the workbench: {len(edits) - before}")
    edit = edits[-1]
    require(edit.proposer == "conjecturer" and edit.kind == "revise" and conj.edit_id == edit.edit_id
            and conj.accepted == (edit.decision == "accepted")
            and [dict(b) for b in edit.bets] == [{"spec": p["spec"], "expect": p["expect"]} for p in want],
            f"the proposal is a revise whose bets are the predictions: {edit.kind} {edit.proposer} {edit.decision}")
    pending = book.pending()
    require([(p.conjecture_id, p.index, p.state, p.expect) for p in pending]
            == [(conj.conjecture_id, 0, "open", "fail"), (conj.conjecture_id, 1, "open", "pass")],
            f"the predictions are registered as pending experiments: {pending}")
    # settle them
    layers = {"ast": "ok", "plan": "ok", "data": "ok"}
    from surprise.harness.contracts import Label

    hit0 = F.make_phi("datafusion", ("ast:stmt:select", "ast:set_op:intersect_all", "data:setop:left_has_dups"), layers)
    hit1 = F.make_phi("datafusion", ("ast:stmt:select", "ast:set_op:except_all"), layers)
    settled = book.observe(hit0, Label(y="fail", oracle=C.DFA_ORACLE, fail_kind="wrong_result"), "rec-a")
    require([(p.index, p.state, p.record_id) for p in settled] == [(0, "kept", "rec-a")], f"first prediction kept: {settled}")
    require(book.observe(hit1, Label(y="invalid", oracle=C.DFA_ORACLE, invalid_reason="query_error"), "rec-b") == (),
            "an invalid experiment settles nothing")
    require(book.observe(hit1, Label(y="pass", oracle="tlp"), "rec-c") == (), "another oracle settles nothing")
    settled = book.observe(hit1, Label(y="fail", oracle=C.DFA_ORACLE, fail_kind="wrong_result"), "rec-d")
    require([(p.index, p.state) for p in settled] == [(1, "broken")], f"second prediction broken: {settled}")
    summary = book.summary()
    require({k: summary.get(k) for k in ("conjectures", "predictions", "open", "kept", "broken")}
            == {"conjectures": 1, "predictions": 2, "open": 0, "kept": 1, "broken": 1}, f"book summary: {summary}")
    reopened = R.ConjectureBook(book.path)
    require(reopened.summary() == summary and [p.state for p in reopened.pending(state=None)] == ["kept", "broken"],
            "the book reopens from its file")
    # refusals
    for tag, reply, reason in (
        ("nopred", conjecture_reply(predictions=False), "missing prediction"),
        ("nomech", conjecture_reply(mechanism=None), "missing mechanism"),
        ("badtrig", conjecture_reply(trigger=["ast:bogus"]), "unknown trigger feature"),
        ("allbad", conjecture_reply(predictions=[{"required": ["ast:bogus"], "forbidden": [], "data_properties": [],
                                                  "expect": "fail", "why": "x"},
                                                 dict(C.GOOD_PREDICTIONS[0], expect="maybe")]), "no valid prediction"),
    ):
        script = Script([reply])
        agent, book = conjecturer(script, tag)
        wb = bench_copy(tag)
        before = len(wb.edits())
        conj = agent.after(wb, record, outcome)
        require(conj is not None and conj.status == "rejected" and book.pending() == ()
                and book.summary().get("conjectures") == 0 and len(wb.edits()) == before,
                f"{reason}: refused, nothing registered or proposed: {getattr(conj, 'status', None)}")
    # one bad prediction is dropped, the rest kept
    script = Script([conjecture_reply(predictions=[C.GOOD_PREDICTIONS[0], {"required": ["ast:bogus"], "forbidden": [],
                                                                            "data_properties": [], "expect": "fail", "why": "x"}])])
    agent, book = conjecturer(script, "drop")
    conj = agent.after(bench_copy("drop"), record, outcome)
    require(conj.status == "registered" and len(conj.predictions) == 1 and len(conj.dropped) == 1,
            f"an invalid prediction is dropped: {len(conj.predictions)} kept, {len(conj.dropped)} dropped")
    # a trigger that does not cover the failure it explains: registered, not proposed
    script = Script([conjecture_reply(trigger=["ast:set_op:intersect_all"])])
    agent, book = conjecturer(script, "cover")
    wb = bench_copy("cover")
    before = len(wb.edits())
    conj = agent.after(wb, record, outcome)
    require(conj.status == "registered" and conj.edit_id is None and conj.edit_reason == "not_covering"
            and len(wb.edits()) == before and len(book.pending()) == 2,
            f"not covering: registered without a proposal: {conj.status}, {conj.edit_reason}")
    # blocked at the cap
    agent, book = conjecturer(Script([conjecture_reply()]), "cap", max_calls=0)
    conj = agent.after(bench_copy("cap"), record, outcome)
    require(conj.status == "blocked" and book.pending() == (), f"blocked: {conj.status}")
    return (f"selection picks {C.DFA_SOURCE_PATH} for DF-A and {C.DUCKDB_SOURCE_PATH} for {C.DUCKDB_FIX}; "
            "registered with a revise whose bets are its predictions; settled by experiments; refusals, drops, "
            "not covering, blocked")


# ---- wiring -------------------------------------------------------------------------

def check_wiring() -> str:
    from . import s04 as G4

    # roles off: S8's loop, row for row, with no role module loaded
    out = tmpdir("off") / "run"
    probe = ("import sys, json\n"
             "from surprise.experiments import loop\n"
             f"loop.run({str(out)!r}, seed={C.OFF_PREFIX['seed']}, engines={C.OFF_PREFIX['engines']!r}, "
             f"max_experiments={C.OFF_PREFIX['experiments']})\n"
             "print(json.dumps(sorted(m for m in sys.modules if m.startswith('surprise.roles'))))\n")
    loaded = run_probe(probe, env=clean_env())
    require(loaded == [], f"with every role off the loop loads no role module: {loaded}")
    rows = rows_of(out / "progress.jsonl")
    require(len(rows) == C.OFF_PREFIX["experiments"], f"{len(rows)} rows")
    raw = json.loads((out / "progress.jsonl").read_text(encoding="utf-8").splitlines()[0])
    require(tuple(sorted(raw)) == tuple(sorted(C.OFF_PREFIX["keys"])), f"row keys are S8's: {sorted(raw)}")
    require(rows_hash(rows) == C.OFF_PREFIX["sha256"],
            "with every role off the first 40 experiments are S8's, row for row (results/s08/longrun)")
    config = json.loads((out / "config.json").read_text(encoding="utf-8"))
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    from surprise.harness.ledger import Ledger

    ledger = Ledger(out / "ledger.sqlite")
    try:
        manifest = ledger.run_manifest(f"loop-s{C.OFF_PREFIX['seed']}")
    finally:
        ledger.close()
    require("llm" not in config and "llm" not in report and "llm" not in manifest, "roles off: no llm section anywhere")
    # roles on, scripted
    f1 = G4.load("F1")
    implementer_text = {"setup": list(f1.setup), "query": f1.query, "predicate": None, "prediction": {"expect": "fail"}}
    conj_text = {"mechanism": "a correlated EXISTS under a LEFT JOIN is decorrelated through a delim join that drops rows",
                 "trigger": ["ast:subquery:exists", "ast:subquery_trait:correlated"],
                 "prediction": [{"required": ["ast:subquery:exists", "ast:subquery_trait:correlated", "ast:join:left"],
                                 "forbidden": [], "data_properties": [], "expect": "fail", "why": "same decorrelation"}]}
    script = Script({"implementer": implementer_text, "conjecturer": conj_text})
    from surprise.experiments import loop

    base = tmpdir("on")
    llm = {"roles": list(C.ROLES), "cache": str(base / "cache"), "max_calls": 50, "network": False, "transport": script}
    boot = [{"case": f1.to_dict(), "oracle": "plan_variant", "rule": None}]
    run_dir = base / "run"
    rep = loop.run(run_dir, seed=0, engines=("duckdb",), oracles=("plan_variant", "tlp"), max_experiments=8,
                   bootstrap=boot, llm=llm)
    require(rep["status"] == "budget_experiments", f"the run with roles on ends at its budget: {rep['status']}")
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    require(config.get("llm") == {"roles": list(C.ROLES), "cache": str(base / "cache"), "max_calls": 50, "network": False},
            f"config.json records the roles: {config.get('llm')}")
    ledger = Ledger(run_dir / "ledger.sqlite")
    try:
        manifest = ledger.run_manifest("loop-s0")
        records = {r.record_id: r for r in ledger.records(run_id="loop-s0")}
    finally:
        ledger.close()
    section = manifest.get("llm") or {}
    require(section.get("tiers") == C.TIERS and section.get("roles") == list(C.ROLES)
            and {e: (section.get("sources") or {}).get(e, {}).get("commit") for e in ("duckdb", "datafusion")}
            == C.CONSTANTS["SOURCE_COMMITS"] and (section.get("constants") or {}).get("TIERS") == C.TIERS,
            f"the run manifest's llm section: {sorted(section)}")
    llm_report = rep.get("llm") or {}
    by_role = (llm_report.get("calls") or {}).get("by_role") or {}
    require(by_role.get("conjecturer", {}).get("calls", 0) >= 1 and by_role.get("implementer", {}).get("calls", 0) >= 1,
            f"both roles were called: {by_role}")
    require((llm_report.get("book") or {}).get("conjectures", 0) >= 1, f"the F1 family got a conjecture: {llm_report.get('book')}")
    lines = [json.loads(l) for l in (run_dir / "progress.jsonl").read_text(encoding="utf-8").splitlines()]
    require(all("llm" in row for row in lines), "every row records the roles' work of its step")
    F, T = features(), theory()
    implemented = 0
    for row in lines:
        if row["lane"] in ("implement", "bet"):
            implemented += 1
            require(row["op"] == "implementer" and row["target"], f"an implementer row names its target: {row['op']}")
            record = records[row["record_id"]]
            check = F.check_spec(F.Phi.from_dict(record.phi), T.Spec.from_dict(row["target"]))
            require(check.ok, f"an implementer candidate meets its spec: {row['record_id']} {check}")
    for name in ("calls.jsonl", "conjectures.jsonl", "implementer.jsonl"):
        require((run_dir / "llm" / name).is_file(), f"llm/{name} is written")
    calls = ledger_lines(run_dir / "llm" / "calls.jsonl")
    require(len(calls) == sum(v.get("calls", 0) for v in by_role.values()) == len(script.calls) + sum(
        1 for c in calls if c["source"] == "cache"), "every call is in the run's call ledger")
    # cap 0: the loop still runs, every call blocked
    zero = Script({"implementer": implementer_text, "conjecturer": conj_text})
    llm0 = dict(llm, cache=str(base / "cache0"), max_calls=0, transport=zero)
    rep0 = loop.run(base / "run0", seed=0, engines=("duckdb",), oracles=("plan_variant", "tlp"), max_experiments=4,
                    bootstrap=boot, llm=llm0)
    statuses = {k for role in (rep0.get("llm", {}).get("calls", {}).get("by_role") or {}).values()
                for k, v in role.items() if k in C.STATUSES and v}
    require(rep0["status"] == "budget_experiments" and zero.calls == [] and statuses <= {"blocked"},
            f"cap 0: no call, the run completes: {rep0['status']}, {statuses}")
    return (f"off: 40 rows identical to S8, no role loaded; on: {len(script.calls)} scripted calls, "
            f"{implemented} implementer experiments meeting their specs; cap 0 completes")


# ---- pinned real replies --------------------------------------------------------------

def pinned_dir(name: str) -> Path:
    path = LLM_DIR / name
    require(path.is_dir(), f"gates/s09_llm/{name} is missing: the orchestrator records it with real calls after the merge")
    return path


def copy_cache(name: str) -> Path:
    source = pinned_dir(name) / "cache"
    require(source.is_dir() and any(source.rglob("*.json")), f"gates/s09_llm/{name}/cache holds the recorded replies")
    target = tmpdir(f"pin-{name}") / "cache"
    shutil.copytree(source, target)
    return target


def check_implementer_report() -> str:
    R, F = roles(), features()
    cache = copy_cache("implementer")
    expected = json.loads((pinned_dir("implementer") / "report.json").read_text(encoding="utf-8"))
    refuse = Refuse()
    gw = R.Gateway(cache_dir=cache, ledger_path=None, max_calls=0, transport=refuse)
    impl = R.Implementer(gateway=gw, extract=F.extract, seed=C.IMPLEMENTER_SEED)
    report = R.implementer_report(C.IMPLEMENTER_SPECS, impl)
    require(set(C.REPORT_KEYS) <= set(report) and report["specs"] == len(C.IMPLEMENTER_SPECS),
            f"report keys {sorted(report)}")
    require(all(set(C.REPORT_ROW_KEYS) <= set(row) for row in report["rows"])
            and [row["id"] for row in report["rows"]] == [s["id"] for s in C.IMPLEMENTER_SPECS], "one row per spec")
    require(refuse.calls == 0 and gw.network_calls == 0, "the report replays with no network call")
    totals = gw.totals()["by_role"].get("implementer", {})
    require(totals.get("miss", 0) == 0 and totals.get("blocked", 0) == 0, f"every reply came from the cache: {totals}")
    for key in ("specs", "first_ok", "final_ok", "first_rate", "final_rate", "by_kind", "rows"):
        require(report[key] == expected[key], f"replayed {key} differs from the recorded report")
    kinds = ", ".join(f"{k} {v['final_ok']}/{v['specs']}" for k, v in sorted(report["by_kind"].items()))
    return (f"phi-check pass rate {report['first_rate']:.2f} at the first try, {report['final_rate']:.2f} after "
            f"{C.CONSTANTS['IMPLEMENTER_ATTEMPTS']} tries ({report['final_ok']}/{report['specs']}); {kinds}")


def check_dfa() -> str:
    R, T = roles(), theory()
    ctx = dfa()
    expected = json.loads((pinned_dir("dfa") / "conjecture.json").read_text(encoding="utf-8"))
    results = []
    for round_ in (1, 2):
        cache = copy_cache("dfa")
        refuse = Refuse()
        root = tmpdir(f"dfa-replay{round_}")
        book = R.ConjectureBook(root / "conjectures.jsonl")
        gw = R.Gateway(cache_dir=cache, ledger_path=None, max_calls=0, transport=refuse)
        agent = R.Conjecturer(gateway=gw, extract=features().extract, book=book, sources=R.open_sources(),
                              seed=C.CONJECTURE_SEED)
        wb = bench_copy(f"dfa-replay{round_}")
        conj = agent.after(wb, ctx["record"], ctx["outcome"])
        require(refuse.calls == 0 and gw.network_calls == 0, "the DF-A conjecture replays with no network call")
        results.append((conj, book, wb))
    conj, book, wb = results[0]
    require(conj.to_dict() == results[1][0].to_dict(), "two replays give the same conjecture")
    require(conj.to_dict() == expected, "the replay gives the recorded conjecture")
    require(conj.status == "registered" and conj.mechanism and conj.trigger and len(conj.predictions) >= 1,
            f"a hypothesis with a mechanism, a trigger and predictions: {conj.status} {conj.reason}")
    from surprise.harness.contracts import ORACLE_IDS

    for p in conj.predictions:
        spec = T.Spec.from_dict(p["spec"])
        require(spec.engine == "datafusion" and spec.oracle in ORACLE_IDS and p["expect"] in ("pass", "fail"),
                f"a prediction is a checkable spec with an expected label: {p}")
    open_ = book.pending()
    require(len(open_) == len(conj.predictions) and all(p.state == "open" for p in open_),
            f"every prediction is registered as a pending experiment: {len(open_)}")
    if conj.edit_id is not None:
        edit = wb.edit(conj.edit_id)
        require(edit.proposer == "conjecturer" and len(edit.bets) == len(conj.predictions), "the proposal carries the bets")
        fate = f"proposed as {conj.edit_id}, {edit.decision}"
    else:
        fate = f"not proposed ({conj.edit_reason})"
    preds = "; ".join(f"{p['expect']} on {'+'.join(T.Spec.from_dict(p['spec']).required)}"
                      + (f" without {'+'.join(T.Spec.from_dict(p['spec']).forbidden)}" if T.Spec.from_dict(p['spec']).forbidden else "")
                      for p in conj.predictions)
    return f"mechanism: {conj.mechanism[:160]}; trigger {list(conj.trigger)}; {len(conj.predictions)} predictions ({preds}); {fate}"


def check_replay() -> str:
    from . import s04 as G4

    pinned = pinned_dir("loop")
    expected_dir = pinned / "expected"
    cache = copy_cache("loop")
    base = cache.parent
    boot = [{"case": G4.load(item["case"]).to_dict(), "oracle": item["oracle"], "rule": item["rule"]}
            for item in C.LOOP_RUN["bootstrap"]]
    (base / "bootstrap.json").write_text(json.dumps(boot), encoding="utf-8")
    out = base / "run"
    argv = [sys.executable, "-m", "surprise.experiments.loop", "--out", str(out), "--seed", str(C.LOOP_RUN["seed"]),
            "--max-experiments", str(C.LOOP_RUN["max_experiments"]), "--bootstrap", str(base / "bootstrap.json"),
            "--llm-cache", str(cache), "--llm-offline"]
    for engine in C.LOOP_RUN["engines"]:
        argv += ["--engine", engine]
    for oracle in C.LOOP_RUN["oracles"]:
        argv += ["--oracle", oracle]
    for role in C.LOOP_RUN["roles"]:
        argv += ["--llm", role]
    proc = subprocess.run(argv, cwd=FRAMEWORK, capture_output=True, text=True, timeout=3600, env=clean_env())
    require(proc.returncode == 0, f"the replay run failed: {proc.stderr[-800:]}")
    got, want = rows_of(out / "progress.jsonl"), rows_of(expected_dir / "progress.jsonl")
    for index, (a, b) in enumerate(zip(got, want)):
        require(a == b, f"replayed row {index} differs in {[k for k in b if a.get(k) != b.get(k)]}")
    require(len(got) == len(want), f"{len(got)} replayed rows, {len(want)} recorded")
    conj_got = rows_of(out / "llm" / "conjectures.jsonl", drop=())
    conj_want = rows_of(expected_dir / "conjectures.jsonl", drop=())
    require(conj_got == conj_want, "the replay registers the same conjectures and settles the same predictions")
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    recorded = json.loads((expected_dir / "report.json").read_text(encoding="utf-8"))
    for key in C.REPORT_COMPARED:
        require(report.get(key) == recorded.get(key), f"report {key}: {report.get(key)} vs recorded {recorded.get(key)}")
    require(report["llm"]["book"] == recorded["llm"]["book"], "the same book summary")
    calls = ledger_lines(out / "llm" / "calls.jsonl")
    require(calls and all(c["source"] == "cache" and c["status"] != "miss" for c in calls),
            f"every call of the replay came from the cache: {sorted({(c['source'], c['status']) for c in calls})}")
    recorded_calls = ledger_lines(expected_dir / "calls.jsonl")
    require([c["key"] for c in calls] == [c["key"] for c in recorded_calls], "the replay asks the same questions in the same order")
    lanes = report.get("lanes")
    return (f"{len(got)} experiments and {len(calls)} calls replayed from the cache, identical; lanes {lanes}; "
            f"book {report['llm']['book']}")


GROUPS: dict[str, Callable[[], str]] = {
    "isolation": check_isolation,
    "constants": check_constants,
    "cache": check_cache,
    "reject": check_reject,
    "cap": check_cap,
    "source": check_source,
    "implementer": check_implementer,
    "conjecturer": check_conjecturer,
    "wiring": check_wiring,
    "implementer_report": check_implementer_report,
    "dfa": check_dfa,
    "replay": check_replay,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S9 gate (LLM gateway, implementer, conjecturer)")
    parser.add_argument("--only", nargs="+", choices=list(GROUPS), metavar="GROUP",
                        help="run only these groups (the gate proper is all of them)")
    args = parser.parse_args(argv)
    selected = args.only or list(GROUPS)
    failed = 0
    for name in selected:
        started = time.monotonic()
        try:
            detail = GROUPS[name]()
            print(f"[PASS] {name}: {_ascii(detail)} ({time.monotonic() - started:.0f}s)", flush=True)
        except GateFailure as exc:
            failed += 1
            print(f"[FAIL] {name}: {_ascii(exc)}", flush=True)
        except Exception as exc:  # noqa: BLE001 - a crashing check is a failed check
            failed += 1
            print(f"[FAIL] {name}: {type(exc).__name__}: {_ascii(exc)}", flush=True)
    scope = "" if not args.only else f" [only: {', '.join(selected)}]"
    print(f"S09 GATE{scope}: {'PASS' if not failed else 'FAIL'}"
          f" ({len(selected) - failed}/{len(selected)} groups passed)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
