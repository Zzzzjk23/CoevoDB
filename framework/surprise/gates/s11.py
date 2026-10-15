"""S11 gate: the evaluation pipeline (M4 smoke).

Usage (from ``framework/``)::

    python -m surprise.gates.s11                         # everything
    python -m surprise.gates.s11 --only stats runmetrics

Exit code 0 = pass. Groups, following the S11 section of SESSIONS.md and the items S9/S10 left
for the start of S11:

``constants``     the metric, transport and pure-LLM constants as planned;
``store``         the theory store survives transient PermissionErrors when it replaces files;
``loop_error``    a run that dies keeps its original exception: raised to the caller and written
                  to error.txt, even when writing the report fails too;
``deadline``      the DeepSeek transport gives up on a request after a total deadline, also while
                  the server keeps the connection alive; the gateway books it as an error;
``vocabulary``    the metrics read a run that used an extended vocabulary;
``stats``         median, Mann-Whitney U (exact and asymptotic) and Vargha-Delaney A12;
``runmetrics``    per-run metrics of a short DuckDB run, each recomputed here from the ledger,
                  the progress rows and the theory store; the run directory is not modified;
``ciao``          the CIAO matrix and the theory length per generation on the S8 long run;
``llm_metrics``   conjecture survival, LLM prediction accuracy over time, families reached
                  through LLM lanes, calls and tokens per family, on a replay of the M3 cache;
``rq6``           boundary agreement with an upstream fix, the fix-condition table, pair
                  agreement of two partitions, recall passed through;
``arms``          the ablation switches of the loop: frozen theory, frozen Diagnoser, random
                  Hunter, a theory started from another run, a Hunter that selects with another
                  run's theory;
``pure_llm_script`` the pure-LLM baseline with scripted replies: cases run through the same
                  oracles and CVE, bad replies and bad cases are logged and skipped, budgets hold;
``pure_llm``      a recorded pure-LLM run replayed from its cache with no network;
``dedup``         the offline comparison of the old sigma key and the pre-execution membership
                  test against the full-profile identity;
``coverage``      replay of parsed upstream regression tests on DuckDB 1.5.5 and 1.1.3 (labels
                  only from the harness);
``sqlancer``      the SQLancer baseline transcribed from docs/FINAL_REPORT.md;
``grid``          M4 smoke: a 2 arms x 2 seeds grid runs and resumes; one command writes every
                  RQ1-RQ6 metric, the statistics and the figures.

``ciao`` reads the S8 long run pinned in ``s08_runs.json``; ``pure_llm`` reads replies the
orchestrator records once with real calls under ``gates/s11_llm/`` and fails until then.
Tables live in ``s11_cases.py``. Output is ASCII only. No group makes a network call.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import http.server
import importlib
import itertools
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from . import s11_cases as C
from .s06 import GateFailure, _ascii, require

FRAMEWORK = Path(__file__).resolve().parents[2]
REPO = FRAMEWORK.parent
LLM_DIR = Path(__file__).resolve().parent / "s11_llm"
S10_LLM_DIR = Path(__file__).resolve().parent / "s10_llm"


# ---- helpers ------------------------------------------------------------------------------------

def tmpdir(tag: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=f"s11-{tag}-"))


def close(a: Any, b: float | None, tol: float = 1e-9) -> bool:
    if b is None:
        return a is None
    return isinstance(a, (int, float)) and not isinstance(a, bool) and abs(float(a) - float(b)) <= tol


def clean_env() -> dict[str, str]:
    drop = {"DEEPSEEK_API_KEY", "SURPRISE_LLM_MAX_CALLS"}
    return {k: v for k, v in os.environ.items() if k.upper() not in drop}


def lines_of(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def rows_of(path: Path, drop: tuple[str, ...] = ("elapsed_s",)) -> list[dict[str, Any]]:
    rows = lines_of(path)
    for row in rows:
        for key in drop:
            row.pop(key, None)
    return rows


def tree_digest(root: Path) -> dict[str, str]:
    found = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            found[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def load_case(name: str) -> Any:
    from . import s04 as G4

    return G4.load(name)


def bootstrap_file(directory: Path, names: tuple[tuple[str, str], ...]) -> Path:
    items = [{"case": load_case(name).to_dict(), "oracle": oracle, "rule": None} for name, oracle in names]
    path = directory / "bootstrap.json"
    path.write_text(json.dumps(items, indent=1), encoding="utf-8")
    return path


def run_cli(argv: list[str], *, timeout: float = 3600, env: dict[str, str] | None = None,
            python: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([python or sys.executable, *argv], cwd=FRAMEWORK, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout, env=env or clean_env())


def loop_argv(out: Path, *, seed: int, experiments: int, engines: tuple[str, ...], oracles: tuple[str, ...] = (),
              bootstrap: Path | None = None, extra: tuple[str, ...] = ()) -> list[str]:
    argv = ["-m", "surprise.experiments.loop", "--out", str(out), "--seed", str(seed),
            "--max-experiments", str(experiments)]
    for engine in engines:
        argv += ["--engine", engine]
    for oracle in oracles:
        argv += ["--oracle", oracle]
    if bootstrap is not None:
        argv += ["--bootstrap", str(bootstrap)]
    return argv + list(extra)


def open_records(out: Path) -> tuple[str, list[Any], dict[str, Any]]:
    from surprise.harness.ledger import Ledger

    ledger = Ledger(out / "ledger.sqlite")
    try:
        run_ids = ledger.run_ids()
        require(len(run_ids) == 1, f"{out}: one run per ledger, found {run_ids}")
        records = ledger.records(run_id=run_ids[0])
        manifest = ledger.run_manifest(run_ids[0])
    finally:
        ledger.close()
    return run_ids[0], sorted(records, key=lambda r: r.seq), manifest


def module(name: str) -> Any:
    return importlib.import_module(name)


def metrics() -> Any:
    return module("surprise.metrics.rq")


@functools.lru_cache(maxsize=None)
def short_run() -> Path:
    """The short DuckDB run shared by runmetrics, rq6 and dedup (run once per gate process)."""
    spec = C.SHORT_RUN
    root = tmpdir("short")
    out = root / "run"
    proc = run_cli(loop_argv(out, seed=spec["seed"], experiments=spec["experiments"], engines=spec["engines"],
                             bootstrap=bootstrap_file(root, spec["bootstrap"])))
    require(proc.returncode == 0, f"the short run failed: {proc.stderr[-800:]}")
    return out


# ---- reference computations (the gate's own, from the ledger and the store) ----------------

def ref_key(record: Any) -> str | None:
    from surprise.harness.cve.shape import behavior_shape
    from surprise.metrics.dups import identity_key

    label = record.label
    if label.y != "fail" or not isinstance(label.cve, dict):
        return None
    profile = label.cve.get("profile")
    if not isinstance(profile, dict) or profile.get("status") != "ran":
        return None
    return identity_key(record.case.engine, list(profile.get("fix_set") or []), label.fail_kind,
                        label.identity.error_class, behavior_shape(label.identity.behavior))


def ref_families(records: list[Any]) -> list[tuple[str, str, int]]:
    seen: set[str] = set()
    found = []
    for record in records:
        key = ref_key(record)
        if key is not None and key not in seen:
            seen.add(key)
            found.append((key, record.record_id, record.seq))
    return found


def ref_valid(records: list[Any]) -> list[Any]:
    return [r for r in records if r.label.y in ("pass", "fail") and r.p_t is not None]


def ref_brier(records: list[Any]) -> tuple[float | None, float | None]:
    valid = ref_valid(records)
    if not valid:
        return None, None
    outcomes = [1.0 if r.label.y == "fail" else 0.0 for r in valid]
    brier = sum((r.p_t - o) ** 2 for r, o in zip(valid, outcomes)) / len(valid)
    rate = sum(outcomes) / len(outcomes)
    return brier, rate * (1.0 - rate)


def ref_calibration(records: list[Any]) -> list[dict[str, Any]]:
    edges = C.METRICS_CONSTANTS["CALIBRATION_EDGES"]
    bins = []
    valid = ref_valid(records)
    for index in range(len(edges) - 1):
        lo, hi = edges[index], edges[index + 1]
        last = index == len(edges) - 2
        members = [r for r in valid if lo <= r.p_t < hi or (last and r.p_t == hi)]
        count = len(members)
        bins.append({
            "lo": lo, "hi": hi, "count": count,
            "mean_p": None if not count else sum(r.p_t for r in members) / count,
            "fail_rate": None if not count else sum(1 for r in members if r.label.y == "fail") / count,
        })
    return bins


def ref_surprise(record: Any) -> float | None:
    from surprise.theory.predict import surprise_bits

    if record.label.y == "invalid" or record.p_t is None:
        return None
    return surprise_bits(record.p_t, record.label.y)


def ref_batches(wb: Any) -> dict[int, list[str]]:
    """Valid record ids by the generation that was open when they were observed."""
    closes = [g["journal_seq"] for g in wb.store.generations()]
    batches: dict[int, list[str]] = {}
    valid = {s.record_id for s in wb.records() if s.label.y != "invalid"}
    for row in wb.store.journal():
        if row.get("kind") != "observe" or row.get("record_id") not in valid:
            continue
        generation = sum(1 for seq in closes if seq < row["seq"])
        batches.setdefault(generation, []).append(row["record_id"])
    return batches


def ref_spread(total: int, count: int) -> list[int]:
    if total <= count:
        return list(range(total))
    picked = []
    for k in range(count):
        index = int(math.floor(k * (total - 1) / (count - 1) + 0.5))
        if index not in picked:
            picked.append(index)
    return picked


def ref_sample(ids: list[str]) -> list[str]:
    cap = C.METRICS_CONSTANTS["CIAO_BATCH_SAMPLE"]
    return [ids[i] for i in ref_spread(len(ids), cap)]


def ref_mwu(x: tuple, y: tuple) -> tuple[float, str, float]:
    n1, n2 = len(x), len(y)
    u = sum(1.0 if a > b else 0.5 if a == b else 0.0 for a in x for b in y)
    values = list(x) + list(y)
    ties = len(set(values)) < len(values)
    if not ties and n1 + n2 <= 20:
        ranks = sorted(values)
        counts: dict[float, int] = {}
        for chosen in itertools.combinations(range(n1 + n2), n1):
            picked = [ranks[i] for i in chosen]
            rest = [ranks[i] for i in range(n1 + n2) if i not in chosen]
            value = sum(1.0 for a in picked for b in rest if a > b)
            counts[value] = counts.get(value, 0) + 1
        total = sum(counts.values())
        low = sum(c for v, c in counts.items() if v <= u) / total
        high = sum(c for v, c in counts.items() if v >= u) / total
        return u, "exact", min(1.0, 2 * min(low, high))
    n = n1 + n2
    tie_counts: dict[float, int] = {}
    for v in values:
        tie_counts[v] = tie_counts.get(v, 0) + 1
    tie_term = sum(t ** 3 - t for t in tie_counts.values())
    sigma = math.sqrt(n1 * n2 / 12.0 * ((n + 1) - tie_term / (n * (n - 1))))
    if sigma == 0:
        return u, "asymptotic", 1.0
    mu = n1 * n2 / 2.0
    big = max(u, n1 * n2 - u)
    z = (big - mu - 0.5) / sigma
    p = min(1.0, 2.0 * 0.5 * math.erfc(z / math.sqrt(2.0)))
    return u, "asymptotic", p


# ---- constants ----------------------------------------------------------------------------------

def check_constants() -> str:
    MC = module("surprise.metrics.constants")
    have = MC.as_dict()
    for name, value in C.METRICS_CONSTANTS.items():
        require(name in have and have[name] == value and type(have[name]) is type(value),
                f"metrics constant {name} must be {value!r}, got {have.get(name)!r}")
    RC = module("surprise.roles.constants")
    rc = RC.as_dict()
    for name, value in C.ROLE_CONSTANTS.items():
        require(rc.get(name) == value and type(rc.get(name)) is type(value), f"roles constant {name} must be {value!r}, got {rc.get(name)!r}")
    P = module("surprise.baselines.pure_llm")
    for name, value in C.PURE_LLM_CONSTANTS.items():
        got = getattr(P, name, None)
        require(got == value and type(got) is type(value), f"pure_llm.{name} must be {value!r}, got {got!r}")
    topics = getattr(P, "PURE_LLM_TOPICS", None)
    require(isinstance(topics, tuple) and len(topics) >= C.PURE_LLM_MIN_TOPICS and len(set(topics)) == len(topics)
            and all(isinstance(t, str) and t.strip() for t in topics),
            f"PURE_LLM_TOPICS is a tuple of at least {C.PURE_LLM_MIN_TOPICS} distinct topics: {topics!r}")
    require(rc.get("TIERS", {}).get(C.PURE_LLM_CONSTANTS["PURE_LLM_TIER"]) is not None, "the pure-LLM tier is a gateway tier")
    return f"{len(C.METRICS_CONSTANTS)} metric constants, request deadline {rc['REQUEST_DEADLINE_S']} s, pure-LLM constants and {len(topics)} topics"


# ---- fixes --------------------------------------------------------------------------------------

def check_store() -> str:
    from surprise import theory as T

    real = os.replace
    calls = {"n": 0}

    def flaky(src: Any, dst: Any) -> None:
        calls["n"] += 1
        if calls["n"] <= C.STORE_TRANSIENT_FAILURES:
            raise PermissionError(13, "simulated: the file is open in another process")
        real(src, dst)

    root = tmpdir("store")
    os.replace = flaky
    try:
        started = time.monotonic()
        wb = T.Workbench.create(root / "theory")
        took = time.monotonic() - started
    finally:
        os.replace = real
    require(calls["n"] > C.STORE_TRANSIENT_FAILURES, f"the store retried after the failures ({calls['n']} replace calls)")
    reopened = T.Workbench.open(root / "theory")
    require(reopened.theory.version == wb.theory.version, "the store written through transient failures reads back")
    require(not list((root / "theory").rglob("*.tmp")), "no temporary file is left behind")

    def broken(src: Any, dst: Any) -> None:
        raise PermissionError(13, "simulated: always")

    os.replace = broken
    try:
        try:
            T.Workbench.create(root / "theory2")
            raised = None
        except PermissionError as exc:
            raised = exc
        except Exception as exc:  # noqa: BLE001 - the type is what is checked
            raised = exc
    finally:
        os.replace = real
    require(isinstance(raised, PermissionError), f"a lasting failure surfaces as the PermissionError itself, got {raised!r}")
    return f"{calls['n']} replace calls for {C.STORE_TRANSIENT_FAILURES} transient failures ({took:.2f}s); a lasting failure raises PermissionError"


def check_loop_error() -> str:
    from surprise.experiments import loop

    def drive(state: Any) -> None:
        raise ValueError("s11-gate-drive")

    def report(state: Any) -> dict:
        raise RuntimeError("s11-gate-report")

    root = tmpdir("loop-error")
    saved = (loop._drive, loop._write_report)
    outcomes = []
    for tag, patch_report in (("both", True), ("drive", False)):
        out = root / tag
        loop._drive = drive
        if patch_report:
            loop._write_report = report
        try:
            try:
                loop.run(out, seed=1, engines=("duckdb",), oracles=("tlp",), max_experiments=1)
                raised = None
            except BaseException as exc:  # noqa: BLE001 - the type is what is checked
                raised = exc
        finally:
            loop._drive, loop._write_report = saved
        require(isinstance(raised, ValueError) and "s11-gate-drive" in str(raised),
                f"{tag}: the caller gets the original exception, got {raised!r}")
        text = (out / "error.txt").read_text(encoding="utf-8") if (out / "error.txt").is_file() else ""
        require("s11-gate-drive" in text and "ValueError" in text, f"{tag}: error.txt holds the original traceback")
        if patch_report:
            require("s11-gate-report" in text, f"{tag}: error.txt also holds the report failure")
        else:
            payload = json.loads((out / "report.json").read_text(encoding="utf-8"))
            require(payload.get("status") == "error", f"{tag}: the report says status error: {payload.get('status')}")
        outcomes.append(tag)
    return f"original exception kept and written to error.txt ({', '.join(outcomes)})"


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True


def _serve(mode: str) -> tuple[_Server, str]:
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:
            return

        def do_POST(self) -> None:  # noqa: N802 - http.server API
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            if mode == "ok":
                body = json.dumps({"choices": [{"message": {"content": "{\"prediction\": \"ok\"}"}}],
                                   "usage": {"prompt_tokens": 3, "completion_tokens": 4}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            started = time.monotonic()
            try:
                while time.monotonic() - started < 30:
                    if mode == "trickle":
                        self.wfile.write(b" \n")
                        self.wfile.flush()
                    time.sleep(0.25)
            except OSError:
                return

    server = _Server(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/v1"


def check_deadline() -> str:
    R = module("surprise.roles")
    transport_mod = module("surprise.roles.transport")
    saved = os.environ.get("DEEPSEEK_API_KEY")
    os.environ["DEEPSEEK_API_KEY"] = C.DUMMY_KEY
    found = []
    try:
        server, url = _serve("ok")
        try:
            tr = transport_mod.DeepSeekTransport(base_url=url, deadline_s=C.DEADLINE_TEST_S)
            done = tr.complete(model="deepseek-flash", prompt="x", temperature=0.0, max_tokens=10, role="gate")
            require(done.text == "{\"prediction\": \"ok\"}" and done.output_tokens == 4, f"a prompt answer passes: {done!r}")
        finally:
            server.shutdown()
        for mode in ("trickle", "silent"):
            server, url = _serve(mode)
            try:
                tr = transport_mod.DeepSeekTransport(base_url=url, deadline_s=C.DEADLINE_TEST_S)
                started = time.monotonic()
                try:
                    tr.complete(model="deepseek-flash", prompt="x", temperature=0.0, max_tokens=10, role="gate")
                    raised = None
                except Exception as exc:  # noqa: BLE001 - the type is what is checked
                    raised = exc
                took = time.monotonic() - started
                require(isinstance(raised, R.TransportError), f"{mode}: the request ends in TransportError, got {raised!r}")
                require(took <= C.DEADLINE_TEST_S + C.DEADLINE_SLACK_S, f"{mode}: gave up after {took:.1f}s")
                require(C.DUMMY_KEY not in str(raised), f"{mode}: the error message does not carry the key")
                root = tmpdir(f"deadline-{mode}")
                gw = R.Gateway(cache_dir=root / "cache", ledger_path=root / "calls.jsonl", max_calls=5,
                               transport=transport_mod.DeepSeekTransport(base_url=url, deadline_s=C.DEADLINE_TEST_S))
                reply = gw.call("gate", "hello", tier="fast", seed=0)
                require(reply.status == "error", f"{mode}: the gateway books an error: {reply.status}")
                require(not any((root / "cache").rglob("*.json")), f"{mode}: an error is not cached")
                totals = gw.totals()["by_role"]["gate"]
                require(totals["error"] == 1 and totals["network"] == 1, f"{mode}: accounted as one network error: {totals}")
                found.append(f"{mode} {took:.1f}s")
            finally:
                server.shutdown()
    finally:
        if saved is None:
            os.environ.pop("DEEPSEEK_API_KEY", None)
        else:
            os.environ["DEEPSEEK_API_KEY"] = saved
    tr = transport_mod.DeepSeekTransport()
    deadline = getattr(tr, "deadline_s", None)
    require(deadline == C.ROLE_CONSTANTS["REQUEST_DEADLINE_S"], f"the default deadline is REQUEST_DEADLINE_S: {deadline!r}")
    return f"normal answer passes; deadline {C.DEADLINE_TEST_S}s held ({', '.join(found)}); errors booked, not cached"


def check_vocabulary() -> str:
    from surprise import theory as T
    from surprise.experiments import loop
    from surprise.features import default_registry
    from surprise.features.vocabulary import FeatureDef

    D = module("surprise.metrics.dups")
    RE = module("surprise.metrics.recall")
    RD = module("surprise.metrics.rundata")
    from . import s10_cases as C10

    root = tmpdir("vocab")
    registry = default_registry()
    registry.register(FeatureDef(feature_id=C10.VOCAB_GOOD["id"], kind="leaf", parent=C10.VOCAB_PARENT, layer="ast",
                                 description="the two sides of EXCEPT ALL read different tables", source="llm:gate",
                                 definition={"kind": "regex", "pattern": C10.VOCAB_GOOD["pattern"]}, accepted=False,
                                 acceptance=None))
    registry.accept(C10.VOCAB_GOOD["id"], {"gate": True})
    vocab = root / "vocabulary.json"
    registry.save(vocab)
    out = root / "run"
    boot = [{"case": load_case("DF-A").to_dict(), "oracle": "cross_dbms", "rule": None}]
    loop.run(out, seed=0, engines=("datafusion",), oracles=("cross_dbms",), max_experiments=0, bootstrap=boot,
             vocabulary=str(vocab))
    reg = D.run_registry(out)
    require(reg is not None and reg.digest() == registry.digest(), "run_registry reads the run's vocabulary")
    require(D.run_registry(short_run()) is None, "a run without a vocabulary has no run registry")
    try:
        D.new_families(out / "theory")
        plain_ok = True
    except Exception:  # noqa: BLE001 - expected: the default vocabulary does not open this store
        plain_ok = False
    require(not plain_ok, "the store of an extended-vocabulary run does not open with the default vocabulary")
    families = D.new_families(out / "theory", registry=reg)
    require(len(families) == 1 and families[0]["first_record"] == "loop-s0:1", f"new_families with the run registry: {families}")
    old = root / "old"
    (old / "results" / "r").mkdir(parents=True)
    (old / "old_run.json").write_text(json.dumps({"run_dir": "results/r"}), encoding="utf-8")
    report = {"signature": None, "candidate": {"kind": "tlp"}, "root_key": "abc"}
    (old / "results" / "r" / "bugs.jsonl").write_text(json.dumps(report) + "\n" + json.dumps(report) + "\n", encoding="utf-8")
    compared = D.compare(out, old)
    require(compared["new"]["families"] == families and compared["old"]["rate"] == 0.5, f"compare reads the run vocabulary: {compared['new']}")
    score = RE.score({"items": []}, out / "theory", registry=reg)
    require(score["families"] == 1, f"recall.score takes the registry: {score}")
    data = RD.RunData.open(out)
    require(data.registry.digest() == registry.digest(), "RunData carries the run's vocabulary")
    wb = data.workbench()
    require(wb is not None and len(wb.theory.hypotheses) == 1, "RunData opens the store with it")
    M = metrics().run_metrics(out)
    require(M["rq1"]["family_count"] == 1, f"run_metrics on an extended-vocabulary run: {M['rq1']['family_count']}")
    return "run_registry, new_families, compare, recall.score, RunData and run_metrics all read the run's vocabulary"


# ---- stats --------------------------------------------------------------------------------------

def check_stats() -> str:
    S = module("surprise.metrics.stats")
    for x, y, u, method, p in C.MWU_EXACT:
        got = S.mann_whitney_u(list(x), list(y))
        require(close(got["u"], u) and got["method"] == method and close(got["p"], p, 1e-12),
                f"MWU {x} vs {y}: want u={u} {method} p={p}, got {got}")
        ref = ref_mwu(x, y)
        require(close(ref[0], u) and close(ref[2], p, 1e-12), f"(the gate's own reference agrees: {ref})")
    for x, y in C.MWU_TIES + [C.MWU_LARGE]:
        u, method, p = ref_mwu(x, y)
        got = S.mann_whitney_u(list(x), list(y))
        require(close(got["u"], u) and got["method"] == method == "asymptotic" and close(got["p"], p, 1e-9),
                f"MWU {x} vs {y}: want u={u} {method} p={p}, got {got}")
    same = S.mann_whitney_u(list(C.MWU_SAME[0]), list(C.MWU_SAME[1]))
    require(close(same["p"], 1.0), f"identical samples give p 1.0: {same}")
    require(S.mann_whitney_u([], [1.0]) is None and S.mann_whitney_u([1.0], []) is None, "an empty sample gives None")
    for x, y, value in C.A12:
        require(close(S.a12(list(x), list(y)), value), f"A12 {x} vs {y}: want {value}, got {S.a12(list(x), list(y))}")
    require(close(S.a12(list(C.MWU_SAME[0]), list(C.MWU_SAME[1])), 0.5) and S.a12([], [1.0]) is None, "A12 edge cases")
    for values, value in C.MEDIAN:
        require(close(S.median(list(values)), value), f"median {values}: want {value}, got {S.median(list(values))}")
    summary = S.summarize([3.0, None, 1.0, 2.0])
    require(summary == {"n": 3, "median": 2.0, "min": 1.0, "max": 3.0}, f"summarize drops None: {summary}")
    require(S.summarize([]) == {"n": 0, "median": None, "min": None, "max": None}, "summarize of nothing")
    try:
        import scipy.stats as SS
    except ImportError:
        return "exact and asymptotic MWU, A12, median as hand-computed (scipy not installed: cross-check skipped)"
    for x, y in C.MWU_TIES + [C.MWU_LARGE]:
        theirs = SS.mannwhitneyu(list(x), list(y), alternative="two-sided", method="asymptotic", use_continuity=True)
        require(close(S.mann_whitney_u(list(x), list(y))["p"], float(theirs.pvalue), 1e-9), f"scipy agrees on {x} vs {y}")
    return "exact and asymptotic MWU (scipy agrees), A12, median, summarize as hand-computed"


# ---- runmetrics ---------------------------------------------------------------------------------

def check_runmetrics() -> str:
    from surprise import theory as T
    from surprise.metrics.curve import surprise_curve, teeth
    from surprise.metrics.dups import duplicate_rate, new_families
    from surprise.theory.length import theory_length

    out = short_run()
    before = tree_digest(out)
    M = metrics().run_metrics(out)
    again = metrics().run_metrics(out)
    require(M == again, "run_metrics is deterministic")
    require(tree_digest(out) == before, "run_metrics does not modify the run directory")
    for key in C.RQ_KEYS + ("run",):
        require(key in M, f"run_metrics has '{key}'")
    run_id, records, manifest = open_records(out)
    progress = {row["record_id"]: row for row in lines_of(out / "progress.jsonl")}
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    wb = T.Workbench.open(out / "theory")
    run = M["run"]
    require(run["run_id"] == run_id and run["kind"] == "surprise" and run["experiments"] == len(records)
            and run["seed"] == C.SHORT_RUN["seed"] and run["status"] == report["status"], f"run summary: {run}")
    # RQ1
    rq1 = M["rq1"]
    fams = ref_families(records)
    require([(f["key"], f["record_id"], f["seq"]) for f in rq1["families"]] == fams, f"ledger families: {rq1['families']} vs {fams}")
    require(all(close(f["elapsed_s"], progress[f["record_id"]]["elapsed_s"]) for f in rq1["families"]), "family elapsed_s from progress")
    require(rq1["executions"] == len(records) and rq1["family_count"] == len(fams), "executions and family count")
    require(close(rq1["families_per_1000"], 1000.0 * len(fams) / len(records)), "families per 1000 executions")
    require(close(rq1["families_per_hour"], len(fams) / (report["wall_s"] / 3600.0)), "families per hour of wall time")
    first = rq1["first_family"]
    require(fams and first["seq"] == fams[0][2], f"first family: {first}")
    theory_keys = [row["key"] for row in new_families(out / "theory")]
    require(rq1["theory_families"] == theory_keys and close(rq1["duplicate_rate"], duplicate_rate(theory_keys)),
            "theory families and the S8 duplicate rate")
    # RQ2
    rq2 = M["rq2"]
    brier, reference = ref_brier(records)
    require(rq2["valid"] == len(ref_valid(records)) and close(rq2["brier"], brier) and close(rq2["brier_reference"], reference),
            f"Brier {rq2['brier']} vs {brier}, reference {rq2['brier_reference']} vs {reference}")
    want_bins = ref_calibration(records)
    require(len(rq2["calibration"]) == len(want_bins), "one calibration bin per edge interval")
    for got, want in zip(rq2["calibration"], want_bins):
        require(got["count"] == want["count"] and close(got["lo"], want["lo"]) and close(got["hi"], want["hi"])
                and close(got["mean_p"], want["mean_p"]) and close(got["fail_rate"], want["fail_rate"]), f"calibration bin {got} vs {want}")
    threshold = C.METRICS_CONSTANTS["HIGH_SURPRISE_BITS"]
    high = [r for r in records if (ref_surprise(r) or 0.0) >= threshold]
    new = [r for r in high if progress[r.record_id]["triage"] == "new_family"]
    hs = rq2["high_surprise"]
    require(hs["threshold"] == threshold and hs["count"] == len(high) and hs["new_family"] == len(new)
            and close(hs["share"], None if not high else len(new) / len(high)), f"high surprise: {hs}")
    window = C.METRICS_CONSTANTS["CURVE_WINDOW"]
    curve = surprise_curve(records, window=window)
    require(rq2["window"] == window and rq2["curve"] == curve and rq2["teeth"] == teeth(curve), "surprise curve and teeth")
    small = metrics().run_metrics(out, window=5)["rq2"]
    require(small["window"] == 5 and small["curve"] == surprise_curve(records, window=5), "the window can be set")
    # RQ4
    rq4 = M["rq4"]
    invalid = [r for r in records if r.label.y == "invalid"]
    by_reason: dict[str, int] = {}
    by_oracle: dict[str, int] = {}
    for r in invalid:
        by_reason[r.label.invalid_reason] = by_reason.get(r.label.invalid_reason, 0) + 1
        by_oracle[r.label.oracle] = by_oracle.get(r.label.oracle, 0) + 1
    require(rq4["invalid"]["count"] == len(invalid) and close(rq4["invalid"]["rate"], len(invalid) / len(records))
            and rq4["invalid"]["by_reason"] == by_reason and rq4["invalid"]["by_oracle"] == by_oracle, f"invalid: {rq4['invalid']}")
    lengths = rq4["theory_length"]
    require(lengths and lengths[-1]["live"] is True and close(lengths[-1]["length"], theory_length(wb.theory))
            and lengths[-1]["hypotheses"] == len(wb.theory.hypotheses) and lengths[-1]["generation"] == wb.generation,
            f"live theory length: {lengths[-1] if lengths else None}")
    tally = {"accepted": 0, "rejected": 0, "rolled_back": 0}
    accepted = []
    for edit in wb.edits():
        if edit.decision in tally:
            tally[edit.decision] += 1
        if edit.decision == "accepted" and edit.surprise_delta_in is not None and edit.surprise_delta_out is not None:
            accepted.append(edit)
    require(rq4["edits"] == tally, f"edit tally {rq4['edits']} vs {tally}")
    io = rq4["in_out"]
    if accepted:
        mean_in = sum(e.surprise_delta_in for e in accepted) / len(accepted)
        mean_out = sum(e.surprise_delta_out for e in accepted) / len(accepted)
        require(io["edits"] == len(accepted) and close(io["mean_in"], mean_in) and close(io["mean_out"], mean_out)
                and close(io["gap"], mean_out - mean_in), f"in/out gap: {io}")
    else:
        require(io == {"edits": 0, "mean_in": None, "mean_out": None, "gap": None}, f"no accepted edit: {io}")
    # RQ5 (one open generation on a short run)
    ciao = M["rq5"]["ciao"]
    batches = ref_batches(wb)
    require(ciao["generations"] == [wb.generation] and ciao["batches"] == [wb.generation], f"one generation: {ciao}")
    ids = ref_sample(batches.get(wb.generation, []))
    want = wb.surprise_under(wb.generation, ids) if ids else None
    require(close(ciao["matrix"][0][0], want), f"CIAO entry {ciao['matrix']} vs {want}")
    # RQ6 and cost
    require(M["rq6"]["recall"] is None and M["rq6"]["boundary"] == [], f"no known file, no fixed bug in this run: {M['rq6']}")
    cost = M["cost"]
    require(cost["executions"] == len(records) and cost["llm_calls"] == 0 and cost["usd"] is None
            and close(cost["per_family"]["executions"], len(records) / len(fams)), f"cost: {cost}")
    return (f"{len(records)} records, {len(fams)} ledger families, Brier {rq2['brier']:.4f}, {hs['count']} high-surprise "
            f"records, invalid {len(invalid)}, theory length {lengths[-1]['length']}; all recomputed")


def check_ciao() -> str:
    from surprise import theory as T
    from surprise.theory.length import theory_length

    from . import s08 as G8

    out = G8.pinned_dir(G8.pinned("longrun"))
    wb = T.Workbench.open(out / "theory")
    started = time.monotonic()
    got = metrics().ciao(wb)
    took = time.monotonic() - started
    total = wb.generation + 1
    picked = ref_spread(total, C.METRICS_CONSTANTS["CIAO_MAX_GENERATIONS"])
    require(got["generations"] == picked and got["batches"] == picked, f"selected generations {got['generations']} vs {picked}")
    matrix = got["matrix"]
    require(len(matrix) == len(picked) and all(len(row) == len(picked) for row in matrix), "a square matrix")
    batches = ref_batches(wb)
    for a, b in ((0, 0), (len(picked) - 1, 0), (0, len(picked) - 1), (len(picked) // 2, len(picked) // 2)):
        ids = ref_sample(batches.get(picked[b], []))
        want = wb.surprise_under(picked[a], ids) if ids else None
        require(close(matrix[a][b], want, 1e-9), f"CIAO[{picked[a]}][{picked[b]}] = {matrix[a][b]} vs {want}")

    def mean(cells: list[float | None]) -> float | None:
        values = [v for v in cells if v is not None]
        return None if not values else sum(values) / len(values)

    n = len(picked)
    require(close(got["diagonal_mean"], mean([matrix[i][i] for i in range(n)]), 1e-9)
            and close(got["below_mean"], mean([matrix[i][j] for i in range(n) for j in range(n) if i > j]), 1e-9)
            and close(got["above_mean"], mean([matrix[i][j] for i in range(n) for j in range(n) if i < j]), 1e-9),
            "diagonal, below and above means")
    lengths = metrics().theory_lengths(wb)
    require(len(lengths) == total and [row["generation"] for row in lengths] == list(range(total)), "one length per generation")
    for g in (0, total // 2, total - 2):
        require(close(lengths[g]["length"], theory_length(wb.store.load_generation(g))) and lengths[g]["live"] is False,
                f"length of generation {g}")
    require(lengths[-1]["live"] is True and close(lengths[-1]["length"], theory_length(wb.theory)), "the live theory last")
    return (f"{total} generations, {n}x{n} matrix in {took:.0f}s; diagonal {got['diagonal_mean']:.3f}, new theory on old "
            f"batches {got['below_mean']:.3f}, old theory on new batches {got['above_mean']:.3f}")


# ---- llm metrics --------------------------------------------------------------------------------

def check_llm_metrics() -> str:
    spec = C.LLM_RUN
    source = S10_LLM_DIR / "m3" / "cache"
    require(source.is_dir(), "gates/s10_llm/m3/cache is present")
    root = tmpdir("llm")
    cache = root / "cache"
    shutil.copytree(source, cache)
    out = root / "run"
    extra = ["--llm-cache", str(cache), "--llm-offline"]
    for role in spec["roles"]:
        extra += ["--llm", role]
    proc = run_cli(loop_argv(out, seed=spec["seed"], experiments=spec["experiments"], engines=spec["engines"],
                             oracles=spec["oracles"], bootstrap=bootstrap_file(root, spec["bootstrap"]), extra=tuple(extra)))
    require(proc.returncode == 0, f"the replay run failed: {proc.stderr[-800:]}")
    M = metrics().run_metrics(out)
    rq3 = M["rq3"]
    _, records, _ = open_records(out)
    by_id = {r.record_id: r for r in records}
    progress = {row["record_id"]: row for row in lines_of(out / "progress.jsonl")}
    book = lines_of(out / "llm" / "conjectures.jsonl")
    conj = [row for row in book if row.get("type") == "conjecture"]
    settles = [row for row in book if row.get("type") == "settle"]
    registered = [c for c in conj if c["status"] == "registered"]
    states: dict[str, list[str]] = {c["conjecture_id"]: [] for c in registered}
    for s in settles:
        states.setdefault(s["conjecture_id"], []).append(s["state"])
    with_settled = [cid for cid, st in states.items() if any(x in ("kept", "broken") for x in st)]
    survived = [cid for cid in with_settled if "broken" not in states[cid]]
    want_c = {"registered": len(registered), "rejected": sum(1 for c in conj if c["status"] == "rejected"),
              "with_settled": len(with_settled), "survived": len(survived),
              "survival_rate": None if not with_settled else len(survived) / len(with_settled)}
    got_c = rq3["conjectures"]
    require({k: got_c[k] for k in want_c if k != "survival_rate"} == {k: v for k, v in want_c.items() if k != "survival_rate"}
            and close(got_c["survival_rate"], want_c["survival_rate"]), f"conjectures {got_c} vs {want_c}")
    total = sum(len(c.get("predictions") or []) for c in registered)
    kept = sum(1 for s in settles if s["state"] == "kept")
    broken = sum(1 for s in settles if s["state"] == "broken")
    void = sum(1 for s in settles if s["state"] == "void")
    pred = rq3["predictions"]
    require(pred["total"] == total and pred["kept"] == kept and pred["broken"] == broken and pred["void"] == void
            and pred["open"] == total - kept - broken - void
            and close(pred["accuracy"], None if not kept + broken else kept / (kept + broken)), f"predictions {pred}")
    timeline = rq3["timeline"]
    want_t = sorted(((by_id[s["record_id"]].seq, s["state"] == "kept") for s in settles if s["state"] in ("kept", "broken")),
                    key=lambda item: item[0])
    require([(row["seq"], row["kept"]) for row in timeline] == want_t and all(row["source"] == "conjecture" for row in timeline),
            f"timeline {[(row['seq'], row['kept']) for row in timeline]} vs {want_t}")
    running = 0
    for index, row in enumerate(timeline, start=1):
        running += 1 if row["kept"] else 0
        require(close(row["accuracy"], running / index), f"cumulative accuracy at {row}")
    fams = ref_families(records)
    via = {"implement": 0, "bet": 0, "translate": 0, "llm_rule": 0, "invented_feature": 0}
    for _, record_id, _ in fams:
        row = progress[record_id]
        if row["lane"] in ("implement", "bet", "translate"):
            via[row["lane"]] += 1
        if (row.get("rule") or "").startswith("llm:"):
            via["llm_rule"] += 1
    require({k: v for k, v in rq3["families_via"].items() if k != "invented_feature"}
            == {k: v for k, v in via.items() if k != "invented_feature"} and rq3["families_via"]["invented_feature"] == 0,
            f"families via LLM lanes {rq3['families_via']} vs {via}")
    calls = lines_of(out / "llm" / "calls.jsonl")
    by_role: dict[str, dict[str, int]] = {}
    for row in calls:
        entry = by_role.setdefault(row["role"], {"calls": 0, "network": 0, "input_tokens": 0, "output_tokens": 0})
        entry["calls"] += 1
        entry["network"] += 1 if row["source"] == "network" else 0
        entry["input_tokens"] += int(row.get("input_tokens") or 0)
        entry["output_tokens"] += int(row.get("output_tokens") or 0)
    require(rq3["calls"]["by_role"] == by_role and rq3["calls"]["total"] == len(calls) and rq3["calls"]["network"] == 0,
            f"calls by role {rq3['calls']} vs {by_role}")
    tokens = sum(e["input_tokens"] + e["output_tokens"] for e in by_role.values())
    require(close(rq3["calls_per_family"], None if not fams else len(calls) / len(fams))
            and close(rq3["tokens_per_family"], None if not fams else tokens / len(fams)), "calls and tokens per family")
    require(M["cost"]["llm_calls"] == len(calls), "cost counts the calls")
    return (f"{len(records)} experiments replayed; {len(registered)} conjectures, survival {got_c['survival_rate']}, "
            f"accuracy {pred['accuracy']} over {len(timeline)} settled bets; families via {rq3['families_via']}; "
            f"{len(calls)} calls")


# ---- rq6 ----------------------------------------------------------------------------------------

def check_rq6() -> str:
    from surprise.features import default_registry

    B = module("surprise.metrics.boundary")
    P = module("surprise.metrics.partition")
    for specific, conditions, want in C.CLASSIFY:
        got = B.classify(set(specific), set(conditions))
        require(got == want, f"classify({sorted(specific)}, {sorted(conditions)}) = {got}, want {want}")
    entries = B.load_fix_conditions()
    f2 = [e for e in entries if e["name"] == C.F2_FIX["name"]]
    require(len(f2) == 1, f"the fix-condition table has F2: {[e['name'] for e in entries]}")
    entry = f2[0]
    require(entry["engine"] == C.F2_FIX["engine"] and entry["key"] == C.F2_FIX["key"] and entry["fix"] == C.F2_FIX["fix"]
            and tuple(sorted(entry["conditions"])) == C.F2_FIX["conditions"], f"F2 entry: {entry}")
    registry = default_registry()
    for e in entries:
        require(all(registry.known(c) for c in e["conditions"]) and e["conditions"], f"{e['name']}: conditions are known features")
    got = P.pair_agreement(C.PARTITION_PRED, C.PARTITION_TRUTH)
    for name, value in C.PARTITION_EXPECTED.items():
        require(close(got[name], value), f"pair agreement {name}: {got[name]} vs {value}")
    got = P.pair_agreement(C.PARTITION_NONE_PRED, C.PARTITION_TRUTH)
    for name, value in C.PARTITION_NONE_EXPECTED.items():
        require(close(got[name], value), f"pair agreement with singletons {name}: {got[name]} vs {value}")
    # boundary on a theory that holds the F2 family: a one-record run bootstrapped with F2
    root = tmpdir("rq6")
    out = root / "run"
    proc = run_cli(loop_argv(out, seed=0, experiments=0, engines=("duckdb",), oracles=("plan_variant",),
                             bootstrap=bootstrap_file(root, (("F2", "plan_variant"),))))
    require(proc.returncode == 0, f"the F2 run failed: {proc.stderr[-800:]}")
    from surprise import theory as T

    wb = T.Workbench.open(out / "theory")
    require(len(wb.theory.hypotheses) == 1, "F2 opened one hypothesis")
    specific = set(wb.theory.hypotheses[0].specific)
    conditions = set(C.F2_FIX["conditions"])
    M = metrics().run_metrics(out)
    rows = M["rq6"]["boundary"]
    require(len(rows) == 1 and rows[0]["name"] == "F2" and rows[0]["classification"] == B.classify(specific, conditions)
            and sorted(rows[0]["missing"]) == sorted(conditions - specific) and sorted(rows[0]["extra"]) == sorted(specific - conditions),
            f"boundary row for F2: {rows}")
    key = M["rq1"]["families"][0]["key"]
    known = {"engines": {}, "items": [{"name": "F2", "y": "fail", "key": key}, {"name": "ghost", "y": "fail", "key": "fix|duckdb|nothing"}]}
    from surprise.metrics.recall import score

    with_known = metrics().run_metrics(out, known=known)["rq6"]["recall"]
    require(with_known == score(known, out / "theory") and close(with_known["recall"], 0.5), f"recall passed through: {with_known}")
    return (f"classify, F2 fix conditions ({len(entries)} entries), pair agreement as hand-computed; F2 hypothesis "
            f"{rows[0]['classification']} (missing {rows[0]['missing']}, extra {len(rows[0]['extra'])} literals); recall 0.5")


# ---- arms ---------------------------------------------------------------------------------------

def check_arms() -> str:
    from surprise import theory as T
    from surprise.experiments import loop
    from surprise.features import Phi

    spec = C.ARMS_RUN
    root = tmpdir("arms")
    boot = bootstrap_file(root, spec["bootstrap"])

    def arm(name: str, *extra: str, bootstrap: Path | None = boot) -> Path:
        out = root / name
        proc = run_cli(loop_argv(out, seed=spec["seed"], experiments=spec["experiments"], engines=spec["engines"],
                                 oracles=spec["oracles"], bootstrap=bootstrap, extra=extra))
        require(proc.returncode == 0, f"{name} failed: {proc.stderr[-800:]}")
        return out

    base = arm("value")
    base_rows = rows_of(base / "progress.jsonl")
    require("arm" not in json.loads((base / "config.json").read_text(encoding="utf-8")), "a default run's config.json has no arm")
    require("select_p" not in base_rows[-1], "a default run's rows are as before")
    rand = arm("random", "--hunter", "random")
    rand2 = arm("random2", "--hunter", "random")
    rand_rows = rows_of(rand / "progress.jsonl")
    require(rand_rows == rows_of(rand2 / "progress.jsonl"), "the random Hunter is deterministic for a seed")
    require([r["case_digest"] for r in rand_rows] != [r["case_digest"] for r in base_rows], "the random Hunter chooses differently")
    config = json.loads((rand / "config.json").read_text(encoding="utf-8"))
    require(config.get("arm", {}).get("hunter") == "random" and json.loads((rand / "report.json").read_text(encoding="utf-8"))
            .get("arm", {}).get("hunter") == "random", "config.json and report.json record the arm")
    # frozen theory
    frozen = arm("freeze-theory", "--freeze", "theory")
    empty = T.Workbench.create(root / "empty-theory")
    head = T.Workbench.open(frozen / "theory")
    require(head.theory.version == empty.theory.version and not head.theory.hypotheses, "a frozen theory never changes")
    _, records, _ = open_records(frozen)
    rows = lines_of(frozen / "progress.jsonl")
    require(all(r["triage"] is None and r["opened"] is None and r["owner"] is None and r["edits"] == [] for r in rows),
            "frozen-theory rows carry no triage, family or edit")
    fails = [r for r in records if r.label.y == "fail"]
    require(fails and all(r.label.cve.get("tier") == 3 for r in fails), "with nothing known every failure gets the full profile")
    # frozen Diagnoser
    still = arm("freeze-diagnoser", "--freeze", "diagnoser")
    wb = T.Workbench.open(still / "theory")
    require(wb.families() and not wb.edits(), f"a frozen Diagnoser proposes no edit; families still open: {list(wb.families())}")
    require(all(r["edits"] == [] for r in lines_of(still / "progress.jsonl")), "no edit in any row")
    # a theory started from another run
    source_head = T.Workbench.open(base / "theory").theory.version
    started = arm("theory-from", "--theory-from", f"{base}@head", bootstrap=None)
    first = lines_of(started / "progress.jsonl")[0]
    cfg = json.loads((started / "config.json").read_text(encoding="utf-8"))["arm"]["theory_from"]
    require(cfg["generation"] == "head" and cfg["version"] == source_head and Path(cfg["run"]) == base.resolve(),
            f"config records the source theory: {cfg}")
    require(first["theory_version"] == source_head, "the first experiment runs under the source theory")
    # a Hunter that selects with another run's theory, while this run's theory is empty and frozen
    paired = arm("select-from", "--select-from", f"{base}@head", "--freeze", "theory", bootstrap=None)
    _, records, _ = open_records(paired)
    rows = {r["record_id"]: r for r in lines_of(paired / "progress.jsonl")}
    fresh = T.Workbench.create(root / "fresh-theory")
    for record in records:
        want = fresh.predict(Phi.from_dict(record.phi), record.label.oracle).p_fail_valid
        require(close(record.p_t, want, 1e-12), f"{record.record_id}: p_t comes from this run's theory ({record.p_t} vs {want})")
    differs = [r for r in rows.values() if isinstance(r.get("select_p"), float) and not close(r["select_p"], r["p_fail_valid"], 1e-12)]
    require(differs, "some choice was scored by the selecting theory differently from this run's theory")
    lanes = {r["lane"] for r in rows.values()}
    require(lanes & {"refine", "generalize"}, f"the selecting theory's hypotheses drive refine/generalize: {lanes}")
    # usage errors
    errors = 0
    for kwargs in ({"freeze": "everything"}, {"hunter": "greedy"}, {"theory_from": "nowhere@x"},
                   {"freeze": "diagnoser", "llm": {"roles": ["conjecturer"], "cache": str(root / "c"), "max_calls": 1}}):
        try:
            loop.run(root / f"bad-{errors}", seed=1, engines=("duckdb",), oracles=("tlp",), max_experiments=1, **kwargs)
            raised = None
        except Exception as exc:  # noqa: BLE001 - the type is what is checked
            raised = exc
        require(isinstance(raised, loop.UsageError), f"{kwargs}: UsageError, got {raised!r}")
        errors += 1
    vocab_err = None
    try:
        from surprise.features import default_registry

        other = default_registry()
        other_path = root / "other-vocab.json"
        from . import s10_cases as C10
        from surprise.features.vocabulary import FeatureDef

        other.register(FeatureDef(feature_id=C10.VOCAB_GOOD["id"], kind="leaf", parent=C10.VOCAB_PARENT, layer="ast",
                                  description="gate", source="llm:gate",
                                  definition={"kind": "regex", "pattern": C10.VOCAB_GOOD["pattern"]}, accepted=False,
                                  acceptance=None))
        other.accept(C10.VOCAB_GOOD["id"], {"gate": True})
        other.save(other_path)
        loop.run(root / "bad-vocab", seed=1, engines=("duckdb",), oracles=("tlp",), max_experiments=1,
                 theory_from=f"{base}@head", vocabulary=str(other_path))
    except Exception as exc:  # noqa: BLE001 - the type is what is checked
        vocab_err = exc
    require(isinstance(vocab_err, loop.UsageError), f"a source theory in another vocabulary is refused: {vocab_err!r}")
    return (f"random Hunter deterministic and different; frozen theory unchanged ({len(fails)} failures fully profiled); "
            f"frozen Diagnoser no edits; theory-from and select-from ({len(differs)} choices scored differently); "
            f"{errors + 1} usage errors refused")


# ---- pure LLM -----------------------------------------------------------------------------------

class Script:
    def __init__(self, replies: list[Any]) -> None:
        self.replies = list(replies)
        self.prompts: list[str] = []

    def complete(self, *, model: str, prompt: str, temperature: float, max_tokens: int, role: str) -> Any:
        R = module("surprise.roles")
        self.prompts.append(prompt)
        reply = self.replies.pop(0)
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return R.Completion(text=text, input_tokens=len(prompt) // 4, output_tokens=len(text) // 4)


GOOD_SETUP = ["CREATE TABLE t(a INT, b INT)", "INSERT INTO t VALUES (1, 10), (2, 20), (NULL, 30)"]


def good_case(oracle: str, predicate: str = "a > 1") -> dict[str, Any]:
    return {"setup": GOOD_SETUP, "query": "SELECT a, b FROM t", "predicate": predicate, "oracle": oracle, "expect": "pass"}


def check_pure_llm_script() -> str:
    P = module("surprise.baselines.pure_llm")
    root = tmpdir("pure-script")
    first = {"prediction": "both pass", "cases": [good_case("tlp"), good_case("norec"),
                                                   {**good_case("tlp"), "oracle": "bogus"},
                                                   {**good_case("tlp"), "setup": "not a list"}]}
    second = {"cases": [good_case("tlp")]}
    third = {"prediction": "pass", "cases": [good_case("tlp", "b > 15"), good_case("norec", "b > 15")]}
    script = Script([first, second, third])
    out = root / "run"
    report = P.run(out, seed=3, engine="duckdb", oracles=("tlp", "norec"), max_experiments=10, max_calls=3,
                   cache=root / "cache", transport=script)
    run_id, records, manifest = open_records(out)
    require(len(script.prompts) == 3, f"three calls before the cap: {len(script.prompts)}")
    require(report["status"] == "llm_exhausted" and report["experiments"] == 4, f"stops when the gateway refuses: {report}")
    require(len(records) == 4 and all(r.purpose == "pure_llm" and r.p_t is None and r.theory_version is None for r in records),
            "four records, purpose pure_llm, no theory")
    require([r.label.oracle for r in records] == ["tlp", "norec", "tlp", "norec"], "cases in reply order")
    require(all(r.spec and r.spec.get("expect") == "pass" and "batch" in r.spec and "index" in r.spec for r in records),
            "each record keeps the LLM's prediction, batch and index")
    require(all(r.phi is not None for r in records), "phi is extracted for every case")
    book = lines_of(out / "llm" / "pure_llm.jsonl")
    require([b["status"] for b in book] == ["ok", "rejected", "ok"], f"pure_llm.jsonl statuses: {[b['status'] for b in book]}")
    require(book[0]["skipped"] == 2 and book[0]["cases"] == 2, f"bad cases are skipped and counted: {book[0]}")
    require(manifest.get("baseline") == "pure_llm", "the manifest names the baseline")
    progress = lines_of(out / "progress.jsonl")
    require(len(progress) == 4 and all(p["expect"] == "pass" and p["y"] in ("pass", "fail", "invalid") for p in progress), "progress rows")
    require(script.prompts[0] != script.prompts[1] and "duckdb" in script.prompts[0].lower()
            and "tlp" in script.prompts[0] and "norec" in script.prompts[0], "prompts name the engine and the oracles and differ by batch")
    # determinism of prompts
    script2 = Script([first, second, third])
    P.run(root / "run2", seed=3, engine="duckdb", oracles=("tlp", "norec"), max_experiments=10, max_calls=3,
          cache=root / "cache2", transport=script2)
    require(script2.prompts == script.prompts, "the same seed gives the same prompts")
    # budget mid-batch
    script3 = Script([first])
    budget = P.run(root / "run3", seed=3, engine="duckdb", oracles=("tlp", "norec"), max_experiments=1, max_calls=3,
                   cache=root / "cache3", transport=script3)
    require(budget["status"] == "budget_experiments" and budget["experiments"] == 1, f"the experiment budget holds mid-batch: {budget}")
    return f"4 cases executed from 3 calls (1 reply rejected, 2 bad cases skipped); prompts deterministic; budget holds"


def check_pure_llm() -> str:
    P = module("surprise.baselines.pure_llm")
    pinned = LLM_DIR / "pure_llm"
    require((pinned / "cache").is_dir() and any((pinned / "cache").rglob("*.json")),
            "gates/s11_llm/pure_llm is missing: the orchestrator records it with real calls after the merge")
    root = tmpdir("pure")
    shutil.copytree(pinned / "cache", root / "cache")
    spec = C.PURE_RUN
    out = root / "run"
    argv = ["-m", "surprise.baselines.pure_llm", "--out", str(out), "--seed", str(spec["seed"]), "--engine", spec["engine"],
            "--max-experiments", str(spec["experiments"]), "--llm-cache", str(root / "cache"), "--llm-offline",
            "--llm-max-calls", str(spec["max_calls"])]
    proc = run_cli(argv)
    require(proc.returncode == 0, f"the replay failed: {proc.stderr[-800:]}")
    got, want = rows_of(out / "progress.jsonl"), rows_of(pinned / "expected" / "progress.jsonl")
    require(got == want, f"replayed rows differ from the recording ({len(got)} vs {len(want)})")
    calls = lines_of(out / "llm" / "calls.jsonl")
    require(calls and all(c["source"] == "cache" and c["status"] != "miss" for c in calls), "every call came from the cache")
    _, records, _ = open_records(out)
    fails = [r for r in records if r.label.y == "fail"]
    require(all(r.label.cve.get("tier") == 3 for r in fails), "every failure got the full profile")
    M = metrics().run_metrics(out)
    require(M["run"]["kind"] == "pure_llm" and M["rq2"]["brier"] is None and M["rq3"]["pure_llm"]["total"] == len(records),
            f"run_metrics on the pure-LLM run: {M['run']}, {M['rq3'].get('pure_llm')}")
    labels: dict[str, int] = {}
    for r in records:
        labels[r.label.y] = labels.get(r.label.y, 0) + 1
    return f"{len(records)} cases from {len(calls)} cached calls replayed identically; labels {labels}; {len(M['rq1']['families'])} families"


# ---- dedup and coverage -------------------------------------------------------------------------

def check_dedup() -> str:
    from diagnosis.signature import SignatureEngine

    D = module("surprise.metrics.dedup")
    out = short_run()
    before = tree_digest(out)
    got = D.compare_dedup(out)
    require(tree_digest(out) == before, "the comparison does not modify the run directory")
    _, records, _ = open_records(out)
    progress = {row["record_id"]: row for row in lines_of(out / "progress.jsonl")}
    fails = [r for r in records if r.label.y == "fail"]
    rows = got["rows"]
    require([row["record_id"] for row in rows] == [r.record_id for r in fails], "one row per failure, in order")
    engine = SignatureEngine(runner_factory=lambda: None, checker=None)
    truth_seen: set[str] = set()
    sigma_seen: set[str] = set()
    counts = {"sigma": [0, 0, 0], "membership": [0, 0, 0]}
    for record, row in zip(fails, rows):
        if ref_key(record) is not None:
            require(row["truth_key"] == ref_key(record) and row["reprofiled"] is False, f"{record.record_id}: the run's own profile is the truth")
        require(row["zone"] == progress[record.record_id]["zone"], f"{record.record_id}: zone from the progress row")
        truth_dup = row["truth_key"] in truth_seen
        truth_seen.add(row["truth_key"])
        require(row["truth_dup"] is truth_dup, f"{record.record_id}: truth duplicate")
        member_dup = row["zone"] == "confirmed"
        require(row["member_dup"] is member_dup, f"{record.record_id}: membership decision")
        profile = row["profile"]
        minimal = row["minimal"]
        candidate = SimpleNamespace(r1_summary=None, r2_summary=None, notes=row["error_class"] or "",
                                    schema_sqls=[], inserts=[], q1="", q2="")
        sigma = engine._signature(fix_kind=profile["fix_kind"], fix_set=list(profile["fix_set"]),
                                  plan_diff=list(profile["plan_diff"]), nu=profile["version_ladder"],
                                  executions=int(profile["executions"]), candidate=candidate,
                                  minimal={"schema_sqls": list(minimal["setup"]), "inserts": [], "q1": minimal["query"],
                                           "q2": minimal["predicate"] or ""})
        if record.label.cve.get("minimize", {}).get("status") == "ran" and not row["reprofiled"]:
            require(minimal == record.label.cve["minimize"]["case"] | {}, f"{record.record_id}: sigma reads the minimized case")
        require(row["error_class"] == record.label.identity.error_class, f"{record.record_id}: error class from the label")
        require(row["sigma_key"] == sigma["key"], f"{record.record_id}: sigma key from the old SignatureEngine")
        sigma_dup = row["sigma_key"] in sigma_seen
        sigma_seen.add(row["sigma_key"])
        require(row["sigma_dup"] is sigma_dup, f"{record.record_id}: sigma duplicate")
        for name, decided in (("sigma", sigma_dup), ("membership", member_dup)):
            if decided and truth_dup:
                counts[name][0] += 1
            elif decided:
                counts[name][1] += 1
            elif truth_dup:
                counts[name][2] += 1
    for name, (tp, fp, fn) in counts.items():
        part = got[name]
        require(part["tp"] == tp and part["fp"] == fp and part["fn"] == fn
                and close(part["precision"], None if not tp + fp else tp / (tp + fp))
                and close(part["recall"], None if not tp + fn else tp / (tp + fn)), f"{name}: {part} vs tp/fp/fn {tp}/{fp}/{fn}")
    require(got["failures"] == len(fails) and got["truth_duplicates"] == sum(1 for r in rows if r["truth_dup"]), "totals")
    require(got["sigma"]["executions"] == sum(int(r["profile"]["executions"]) for r in rows), "sigma pays the profile's executions")
    return (f"{len(fails)} failures, {got['truth_duplicates']} true duplicates; sigma p/r {got['sigma']['precision']}/"
            f"{got['sigma']['recall']}, membership p/r {got['membership']['precision']}/{got['membership']['recall']}")


def check_coverage() -> str:
    from surprise.harness.cve.certify import certify
    from surprise.harness.contracts import SqlCase

    V = module("surprise.metrics.coverage")
    spec = C.COVERAGE
    root = tmpdir("coverage")
    files = {}
    old_python = REPO / ".venvs" / C.OLD_FULL_VENV / "Scripts" / "python.exe"
    if not old_python.is_file():
        old_python = REPO / ".venvs" / C.OLD_FULL_VENV / "bin" / "python"
    require(old_python.is_file(), f".venvs/{C.OLD_FULL_VENV} is present (S8 built it for DuckDB 1.1.3 runs)")
    for tag, python in (("new", None), ("old", str(old_python))):
        path = root / f"{tag}.json"
        argv = ["-m", "surprise.metrics.coverage", "run", "--out", str(path), "--prefix", spec["prefix"],
                "--limit", str(spec["limit"])]
        for oracle in spec["oracles"]:
            argv += ["--oracle", oracle]
        proc = run_cli(argv, python=python)
        require(proc.returncode == 0, f"coverage run ({tag}) failed: {proc.stderr[-800:]}")
        files[tag] = json.loads(path.read_text(encoding="utf-8"))
    new, old = files["new"], files["old"]
    require(new["engine"] == "duckdb" and new["version"] == "1.5.5" and old["version"] == "1.1.3", "versions recorded")
    seeds = V.select(spec["prefix"], spec["limit"])
    require(len(seeds) == spec["limit"] and all(s["source"].startswith(spec["prefix"]) for s in seeds), "seeds selected by prefix")
    require(len(new["items"]) == spec["limit"] * len(spec["oracles"]) == len(old["items"]), "one item per seed and oracle")
    for item in new["items"][:2]:
        seed = seeds[item["index"]]
        case = SqlCase(engine="duckdb", setup=tuple(seed["setup_sqls"]), query=seed["query"], predicate=None)
        label = certify(case, item["oracle"])
        require(label.y == item["y"], f"{item['source']} {item['oracle']}: {item['y']} vs a direct certify {label.y}")
    merged = V.compare(old, new)
    for oracle in spec["oracles"]:
        entry = merged["oracles"][oracle]
        for tag, data in (("old", old), ("new", new)):
            counts: dict[str, int] = {}
            for item in data["items"]:
                if item["oracle"] == oracle:
                    counts[item["y"]] = counts.get(item["y"], 0) + 1
            require(entry[tag] == counts, f"{oracle} {tag} counts {entry[tag]} vs {counts}")
        pairs = {(i["index"], i["oracle"]): i["y"] for i in old["items"]}
        flips = sorted(i["index"] for i in new["items"] if i["oracle"] == oracle and i["y"] == "pass"
                       and pairs.get((i["index"], oracle)) == "fail")
        require(sorted(entry["fail_old_pass_new"]) == flips, f"{oracle}: fail on 1.1.3, pass on 1.5.5")
    again = run_cli(["-m", "surprise.metrics.coverage", "run", "--out", str(root / "again.json"), "--prefix", spec["prefix"],
                     "--limit", str(spec["limit"])] + [x for o in spec["oracles"] for x in ("--oracle", o)])
    require(again.returncode == 0 and [(i["index"], i["oracle"], i["y"]) for i in json.loads((root / "again.json")
            .read_text(encoding="utf-8"))["items"]] == [(i["index"], i["oracle"], i["y"]) for i in new["items"]], "a replay is repeatable")
    return f"{spec['limit']} upstream regression seeds x {len(spec['oracles'])} oracles on 1.5.5 and 1.1.3; {merged['oracles']}"


def check_sqlancer() -> str:
    Q = module("surprise.baselines.sqlancer")
    summary = Q.load()
    require(summary["tool"] == C.SQLANCER["tool"] and summary["runs"] == C.SQLANCER["runs"]
            and summary["total_bugs"] == C.SQLANCER["total_bugs"] and summary["transcribed"] is True
            and "docs/FINAL_REPORT.md" in summary["source"], f"summary header: {summary}")
    text = (REPO / "docs" / "FINAL_REPORT.md").read_text(encoding="utf-8")
    for engine, want in C.SQLANCER["engines"].items():
        row = summary["engines"][engine]
        require(row["version"] == want["version"] and row["oracles"] == want["oracles"] and row["bugs"] == want["bugs"],
                f"{engine}: {row}")
        line = f"| {engine} {'v' if engine == 'duckdb' else ''}{want['version']} | — | {want['oracles']} | ~{row['checks'] / 1e6:.1f}M | {want['bugs']} |"
        require(line in text, f"{engine}: the row matches docs/FINAL_REPORT.md ({line})")
    got = Q.metrics(summary, engine="duckdb")
    require(got["family_count"] == 0 and got["checks"] == summary["engines"]["duckdb"]["checks"]
            and close(got["families_per_1000"], 0.0), f"metrics row: {got}")
    return f"{summary['runs']} runs, {summary['total_bugs']} bugs; per engine rows match docs/FINAL_REPORT.md"


# ---- grid (M4 smoke) ----------------------------------------------------------------------------

def check_grid() -> str:
    root = tmpdir("grid")
    config = root / "smoke.json"
    config.write_text(json.dumps(C.GRID_CONFIG, indent=1), encoding="utf-8")
    out = root / "grid"
    started = time.monotonic()
    proc = run_cli(["-m", "surprise.experiments.grid", "run", str(config), "--out", str(out)])
    took = time.monotonic() - started
    require(proc.returncode == 0, f"the grid failed: {proc.stderr[-1200:]}")
    cells = {}
    for name in C.GRID_CELLS:
        path = out / "cells" / name
        meta = json.loads((path / "cell.json").read_text(encoding="utf-8"))
        require(meta["status"] == "done", f"{name}: {meta}")
        cells[name] = (path, meta)
        if name.startswith("surprise/"):
            require((path / "ledger.sqlite").is_file() and (path / "report.json").is_file(), f"{name} is a loop run")
        else:
            require((path / "old_run.json").is_file(), f"{name} is an old CoevoDB run")
    snapshot = {name: (path / "cell.json").read_bytes() for name, (path, _) in cells.items()}
    resumed = time.monotonic()
    proc = run_cli(["-m", "surprise.experiments.grid", "run", str(config), "--out", str(out)])
    require(proc.returncode == 0 and time.monotonic() - resumed <= C.RESUME_MAX_S, "a rerun resumes without running the cells again")
    require(all((path / "cell.json").read_bytes() == snapshot[name] for name, (path, _) in cells.items()), "done cells are untouched")
    status = run_cli(["-m", "surprise.experiments.grid", "status", str(out)])
    require(status.returncode == 0 and "4/4" in status.stdout, f"status reports 4/4 done: {status.stdout[-400:]}")
    proc = run_cli(["-m", "surprise.metrics.report", str(out)])
    require(proc.returncode == 0, f"the report failed: {proc.stderr[-1200:]}")
    rdir = out / "report"
    report = json.loads((rdir / "report.json").read_text(encoding="utf-8"))
    for key in C.REPORT_KEYS:
        require(key in report, f"report.json has '{key}'")
    require(sorted(report["arms"]) == ["old", "surprise"] and report["reference"] == "surprise", f"arms {sorted(report['arms'])}")
    require(sorted(report["cells"]) == sorted(C.GRID_CELLS), f"cells {sorted(report['cells'])}")
    for arm in ("surprise", "old"):
        entry = report["rq1"]["arms"][arm]["families_per_hour"]
        require(entry["n"] == 2, f"rq1 {arm} families_per_hour over two seeds: {entry}")
    pair = [s for s in report["stats"] if s["metric"] == "families_per_hour" and {s["a"], s["b"]} == {"surprise", "old"}]
    require(len(pair) == 1 and "p" in pair[0] and "a12" in pair[0] and pair[0]["n_a"] == 2 and pair[0]["n_b"] == 2,
            f"MWU and A12 for families_per_hour: {pair}")
    for section in ("rq2", "rq3", "rq4", "rq5", "rq6"):
        require(isinstance(report[section], dict) and report[section], f"{section} is filled")
    require(report["rq5"].get("ciao"), "rq5 has the CIAO matrices of the reference arm")
    require(report["external"]["sqlancer"]["family_count"] == 0, "the SQLancer row is in the report")
    for cell in ("surprise/s0-r0", "surprise/s1-r0"):
        metrics_file = cells[cell][0] / "metrics.json"
        require(report["cells"][cell]["metrics"]["rq1"]["family_count"] == metrics().run_metrics(cells[cell][0], window=10)["rq1"]["family_count"],
                f"{cell}: the report's metrics are run_metrics")
    markdown = (rdir / "report.md").read_text(encoding="utf-8")
    require(all(f"RQ{i}" in markdown for i in range(1, 7)), "report.md has a section per RQ")
    for name in C.FIGURES:
        path = rdir / "figures" / name
        require(path.is_file() and path.stat().st_size > 1000 and path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", f"figure {name}")
    proc = run_cli(["-m", "surprise.metrics.report", str(out)])
    require(proc.returncode == 0 and json.loads((rdir / "report.json").read_text(encoding="utf-8")) == report,
            "the report is deterministic")
    fph = {arm: report["rq1"]["arms"][arm]["families_per_hour"]["median"] for arm in ("surprise", "old")}
    return (f"2 arms x 2 seeds in {took / 60:.1f} min, resumed, report and {len(C.FIGURES)} figures in one command; "
            f"median families/hour {fph}; p {pair[0]['p']}, A12 {pair[0]['a12']}")


GROUPS: dict[str, Callable[[], str]] = {
    "constants": check_constants,
    "store": check_store,
    "loop_error": check_loop_error,
    "deadline": check_deadline,
    "vocabulary": check_vocabulary,
    "stats": check_stats,
    "runmetrics": check_runmetrics,
    "ciao": check_ciao,
    "llm_metrics": check_llm_metrics,
    "rq6": check_rq6,
    "arms": check_arms,
    "pure_llm_script": check_pure_llm_script,
    "pure_llm": check_pure_llm,
    "dedup": check_dedup,
    "coverage": check_coverage,
    "sqlancer": check_sqlancer,
    "grid": check_grid,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S11 gate (evaluation pipeline, M4 smoke)")
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
    print(f"S11 GATE{scope}: {'PASS' if not failed else 'FAIL'}"
          f" ({len(selected) - failed}/{len(selected)} groups passed)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
