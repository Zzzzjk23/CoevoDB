"""S15 gate: experiment infrastructure. Exit 0 = pass.

Groups (SESSIONS S15):
  config     the grid accepts concurrency, CPU share, engine threads, kill grace, unlimited LLM calls,
             a model tier and a running SQLancer arm, rejects bad values, keeps old defaults, and
             loads every E1/E3 arm of EXPERIMENT.md section 9
  parallel   stand-in cells run four at a time in block order with their slot, CPUs and engine
             threads; then a real 4-cell parallel smoke (four no-LLM DuckDB arms, one minute each)
  kill       wall-clock kill: an overrunning cell is interrupted at budget + grace, hard-killed with
             its whole process tree when it ignores that, marked done (killed) and never rerun
  interrupt  the real loop and the SQLancer driver answer the grid's interrupt with status
             "interrupted" and exit code 130
  stream     run_metrics streams the ledger: the same output as before S15 on a frozen long run,
             a peak below the cap, and almost no growth when the ledger doubles
  llm        unlimited LLM calls and the tier switch, through the gateway and through cache
             replays of the loop (S10 M3) and the pure-LLM baseline (S11)
  sqlancer   SQLancer logs become cases that the same CVE pipeline judges (fixtures, including a
             NoREC failure whose family key equals the loop's), and a 10-minute live run on DuckDB
             1.5.5 through the grid and the report
  prices     the DeepSeek price table, dated, as the grid's prices
  archive    pack, verify and prune a grid directory
  docs       SERVER.md covers parallel grids, archiving and SQLancer; HANDOFF has S15
  scope      changes since s14-done-r2 stay in scope; harness and the lower layers are untouched
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from . import s15_cases as C
from .s06 import GateFailure, _ascii, require

FRAMEWORK = Path(__file__).resolve().parents[2]
REPO = FRAMEWORK.parent
DATA = REPO / C.DATA
WINDOWS = sys.platform == "win32"
LINUX = sys.platform.startswith("linux")
_TMP_ROOT = Path(tempfile.gettempdir()) / "coevo-s15-gate"


# ---- helpers ------------------------------------------------------------------------------------

def git(*args: str, check: bool = True) -> str:
    proc = subprocess.run(["git", *args], cwd=REPO, capture_output=True, timeout=300)
    if check:
        require(proc.returncode == 0, f"git {' '.join(args)}: {proc.stderr.decode('utf-8', 'replace')[-300:]}")
    return proc.stdout.decode("utf-8", "replace")


def tmpdir(name: str) -> Path:
    path = _TMP_ROOT / name
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    return path


def clean_env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k.upper() not in ("DEEPSEEK_API_KEY", C.CAP_ENV)}
    env.update(extra)
    return env


def py(argv: list[str], *, timeout: float, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *argv], cwd=FRAMEWORK, capture_output=True, text=True,
                          timeout=timeout, env=env or clean_env())


def load_json(path: Path, what: str) -> Any:
    require(path.is_file(), f"{what}: missing ({path})")
    return json.loads(path.read_text(encoding="utf-8"))


def lines_of(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def rows_of(path: Path) -> list[dict[str, Any]]:
    rows = lines_of(path)
    for row in rows:
        row.pop("elapsed_s", None)
    return rows


def write_config(path: Path, raw: dict[str, Any]) -> Path:
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def grid_module() -> Any:
    from surprise.experiments import grid

    return grid


@contextlib.contextmanager
def patched(module: Any, **values: Any) -> Iterator[None]:
    saved = {name: getattr(module, name) for name in values}
    try:
        for name, value in values.items():
            setattr(module, name, value)
        yield
    finally:
        for name, value in saved.items():
            setattr(module, name, value)


@contextlib.contextmanager
def env_var(name: str, value: str | None) -> Iterator[None]:
    saved = os.environ.get(name)
    try:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
        yield
    finally:
        if saved is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = saved


def pid_alive(pid: int) -> bool:
    if WINDOWS:
        import ctypes

        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        kernel.GetExitCodeProcess(handle, ctypes.byref(code))
        kernel.CloseHandle(handle)
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def new_group_kwargs() -> dict[str, Any]:
    if WINDOWS:
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def send_interrupt(proc: subprocess.Popen) -> None:
    if WINDOWS:
        os.kill(proc.pid, signal.CTRL_BREAK_EVENT)
    else:
        os.kill(proc.pid, signal.SIGINT)


def wait_for(predicate: Callable[[], bool], timeout: float, what: str) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.5)
    raise GateFailure(f"timed out after {timeout:.0f}s waiting for {what}")


def iso_seconds(text: str) -> float:
    from datetime import datetime

    return datetime.fromisoformat(text).timestamp()


def experiment_arms() -> dict[str, Any]:
    text = (REPO / "framework/surprise/docs/EXPERIMENT.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    tail = text.split("## 9. 机读清单", 1)[1]
    match = re.search(r"```json\n(.*?)\n```", tail, re.S)
    require(match is not None, "EXPERIMENT.md: no JSON block in section 9")
    return json.loads(match.group(1))["arms"]


def grid_arm_from_spec(name: str, spec: dict[str, Any], cache: Path) -> dict[str, Any]:
    arm = {key: value for key, value in spec.items() if key not in ("needs", "pairs", "hours")}
    arm["name"] = name.lower().replace("_", "-") if name != "pure_llm" else "pure-llm"
    if isinstance(arm.get("llm"), dict) and arm["llm"].get("cache") == "per-cell":
        arm["llm"] = dict(arm["llm"], cache=str(cache / name))
    if "run" in spec.get("needs", {}):
        arm["run"] = True
    if arm["kind"] == "surprise":
        arm.setdefault("engines", ["duckdb"])
    else:
        arm.setdefault("engine", "duckdb")
    return arm


# ---- config -------------------------------------------------------------------------------------

def check_config() -> str:
    grid = grid_module()
    tmp = tmpdir("config")
    cache = tmp / "cache"
    cache.mkdir()
    roles = list(grid._LLM_ROLES)
    llm = {"roles": roles, "cache": str(cache), "max_calls": C.UNLIMITED}
    raw = {"schema": 1, "name": "s15-config", "budget": {"minutes": 1.0}, "seeds": [1001],
           "concurrency": 4, "cpus_per_cell": 2, "engine_threads": 2, "kill_grace_minutes": 10,
           "prices": C.PRICES["grid"],
           "arms": [
               {"name": "full", "kind": "surprise", "engines": ["duckdb"], "llm": llm},
               {"name": "nollm", "kind": "surprise", "engines": ["duckdb"]},
               {"name": "pure-llm", "kind": "pure_llm", "engine": "duckdb",
                "llm": {"cache": str(cache), "max_calls": C.UNLIMITED}},
               {"name": "pure-strong", "kind": "pure_llm", "engine": "duckdb", "tier": "strong",
                "llm": {"cache": str(cache), "max_calls": 5}},
               {"name": "sqlancer", "kind": "sqlancer", "engine": "duckdb", "run": True},
               {"name": "a11", "kind": "surprise", "engines": ["duckdb"], "tier": "strong", "llm": llm},
           ]}

    def load(config: dict[str, Any]) -> dict[str, Any]:
        return grid.load_config(write_config(tmp / "grid.json", config))

    cfg = load(raw)
    for key, value in (("concurrency", 4), ("cpus_per_cell", 2), ("engine_threads", 2), ("kill_grace_minutes", 10.0)):
        require(cfg.get(key) == value, f"config: {key} is {cfg.get(key)!r}, set to {value!r}")
    arms = {arm["name"]: arm for arm in cfg["arms"]}
    require(arms["full"]["llm"]["max_calls"] == C.UNLIMITED and arms["pure-llm"]["llm"]["max_calls"] == C.UNLIMITED,
            "max_calls 'unlimited' is not kept")
    require(arms["a11"].get("tier") == "strong" and arms["pure-strong"].get("tier") == "strong",
            "tier 'strong' is not kept")
    require(arms["full"].get("tier", "missing") is None and arms["nollm"].get("tier", "missing") is None,
            "an arm without tier must read tier None")
    sq = arms["sqlancer"]
    require(sq.get("run") == C.SQLANCER_DEFAULT_RUN and "summary" not in sq and sq.get("budget") == {"minutes": 1.0}
            and sq.get("network") is False, f"sqlancer run arm normalised to {sq}")

    def argv(name: str) -> list[str]:
        return grid.command_for(arms[name], out=tmp / "cells" / name, seed=1001, rep=0)

    def flag(args: list[str], name: str) -> str | None:
        return args[args.index(name) + 1] if name in args else None

    full, a11, pure, strong, sql = argv("full"), argv("a11"), argv("pure-llm"), argv("pure-strong"), argv("sqlancer")
    require(flag(full, "--llm-max-calls") == C.UNLIMITED and "--llm-tier" not in full,
            f"full arm argv: {full[3:]}")
    require(flag(a11, "--llm-tier") == "strong", f"a11 argv lacks --llm-tier strong: {a11[3:]}")
    require(flag(pure, "--llm-max-calls") == C.UNLIMITED and "--llm-tier" not in pure, f"pure argv: {pure[3:]}")
    require(flag(strong, "--llm-tier") == "strong" and flag(strong, "--llm-max-calls") == "5", f"pure strong argv: {strong[3:]}")
    require(sql[1:3] == ["-m", C.SQLANCER_MODULE], f"sqlancer cell runs {sql[1:3]}")
    oracles = [sql[i + 1] for i, item in enumerate(sql) if item == "--oracle"]
    require(flag(sql, "--engine") == "duckdb" and flag(sql, "--seed") == "1001" and flag(sql, "--max-minutes") == "1.0"
            and flag(sql, "--threads") == "1" and oracles == C.SQLANCER_DEFAULT_RUN["oracles"]
            and flag(sql, "--out") == str(tmp / "cells" / "sqlancer"), f"sqlancer argv: {sql[3:]}")

    bad_top = [("concurrency", 0), ("concurrency", 1.5), ("concurrency", "4"), ("concurrency", True),
               ("cpus_per_cell", 0), ("engine_threads", 0), ("engine_threads", "2"),
               ("kill_grace_minutes", 0), ("kill_grace_minutes", -1), ("kill_grace_minutes", "x")]
    rejected = 0
    for key, value in bad_top:
        variant = json.loads(json.dumps(raw))
        variant[key] = value
        try:
            load(variant)
        except ValueError:
            rejected += 1
            continue
        raise GateFailure(f"config: {key}={value!r} was accepted")
    bad_arms = [
        {"name": "x", "kind": "surprise", "llm": dict(llm, max_calls="lots")},
        {"name": "x", "kind": "surprise", "llm": dict(llm, max_calls=-1)},
        {"name": "x", "kind": "surprise", "tier": "medium", "llm": llm},
        {"name": "x", "kind": "surprise", "tier": "strong"},
        {"name": "x", "kind": "pure_llm", "tier": "medium", "llm": {"cache": str(cache), "max_calls": 1}},
        {"name": "x", "kind": "sqlancer", "engine": "duckdb", "run": True, "tier": "strong"},
        {"name": "x", "kind": "sqlancer", "engine": "duckdb", "run": True, "summary": str(tmp / "nope.json")},
        {"name": "x", "kind": "sqlancer", "engine": "datafusion", "run": True},
        {"name": "x", "kind": "sqlancer", "engine": "duckdb", "run": {"oracles": ["PQS"]}},
        {"name": "x", "kind": "sqlancer", "engine": "duckdb", "run": {"threads": 0}},
        {"name": "x", "kind": "sqlancer", "engine": "duckdb", "run": True, "budget": {"experiments": 10}},
    ]
    for arm in bad_arms:
        variant = json.loads(json.dumps(raw))
        variant["arms"] = [arm]
        try:
            load(variant)
        except ValueError:
            rejected += 1
            continue
        raise GateFailure(f"config: arm {arm} was accepted")

    smoke = grid.load_config(REPO / "framework/surprise/docs/grids/s14_smoke.json")
    for key, value in C.TOP_DEFAULTS.items():
        require(key in smoke and smoke[key] == value, f"default {key}: {smoke.get(key, 'missing')!r} != {value!r}")
    smoke_arms = {arm["name"]: arm for arm in smoke["arms"]}
    require(smoke_arms["nollm"].get("tier", "missing") is None, "surprise arm default tier must be None")
    require(set(smoke_arms["sqlancer"]) == {"name", "kind", "summary", "engine", "network"},
            f"a summary-only sqlancer arm keeps its old keys: {sorted(smoke_arms['sqlancer'])}")
    require(grid.command_for(smoke_arms["nollm"], out=tmp / "n", seed=7, rep=0)
            == [sys.executable, "-m", "surprise.experiments.loop", "--out", str(tmp / "n"), "--seed", "7",
                "--max-minutes", "1.0", "--engine", "duckdb"]
            + [token for oracle in smoke_arms["nollm"]["oracles"] for token in ("--oracle", oracle)],
            "a default surprise arm's argv changed")

    spec = experiment_arms()
    names = ["full", "nollm", "pure_llm", "sqlancer"] + [f"A{i}" for i in range(2, 12)]
    from_spec = {"schema": 1, "name": "s15-e1-e3", "budget": {"minutes": 1440.0}, "seeds": [1001, 1002],
                 "concurrency": 8, "cpus_per_cell": 2, "engine_threads": 2,
                 "arms": [grid_arm_from_spec(name, spec[name], cache) for name in names]}
    loaded = load(from_spec)
    require(len(loaded["arms"]) == len(names), "EXPERIMENT.md arms did not all load")
    return (f"new keys kept and passed to the cells; {rejected} bad values rejected; old defaults unchanged; "
            f"{len(names)} E1/E3 arms from EXPERIMENT.md load")


# ---- parallel -----------------------------------------------------------------------------------

_STAND_IN = (
    "import json, os, sys, time\n"
    "out = sys.argv[1]; os.makedirs(out, exist_ok=True)\n"
    "start = time.time(); time.sleep(float(sys.argv[2]))\n"
    "json.dump({'start': start, 'end': time.time(), 'threads': os.environ.get(sys.argv[3])},"
    " open(os.path.join(out, 'stand_in.json'), 'w'))\n"
)


def max_overlap(spans: list[tuple[float, float]]) -> int:
    events = sorted([(start, 1) for start, _ in spans] + [(end, -1) for _, end in spans], key=lambda e: (e[0], e[1]))
    best = current = 0
    for _, delta in events:
        current += delta
        best = max(best, current)
    return best


def check_parallel() -> str:
    grid = grid_module()
    tmp = tmpdir("parallel")
    arms = [{"name": name, "kind": "surprise", "engines": ["duckdb"]} for name in ("a", "b", "c", "d")]
    raw = {"schema": 1, "name": "s15-stand-in", "budget": {"minutes": 1.0}, "seeds": [1, 2],
           "concurrency": 4, "cpus_per_cell": 1, "engine_threads": 3, "arms": arms}
    config = grid.load_config(write_config(tmp / "stand_in.json", raw))

    def fake(arm: Any, *, out: Path, seed: int, rep: int) -> list[str]:
        return [sys.executable, "-c", _STAND_IN, str(out), "3", C.THREADS_ENV]

    out = tmp / "stand-in"
    with patched(grid, command_for=fake):
        code = grid.run_grid(config, out)
    require(code == 0, f"stand-in grid exited {code}")
    spans: dict[str, tuple[float, float]] = {}
    cells: dict[str, dict[str, Any]] = {}
    for arm in "abcd":
        for seed in (1, 2):
            label = f"{arm}/s{seed}-r0"
            directory = out / "cells" / arm / f"s{seed}-r0"
            info = load_json(directory / "cell.json", f"{label} cell.json")
            mark = load_json(directory / "stand_in.json", f"{label} stand-in record")
            require(info.get("status") == "done" and info.get("killed") is False, f"{label}: {info.get('status')}")
            require(mark["threads"] == "3", f"{label}: engine threads env {mark['threads']!r}")
            require(info.get("engine_threads") == 3 and info.get("slot") in range(4), f"{label}: slot/threads {info}")
            spans[label] = (mark["start"], mark["end"])
            cells[label] = info
    overlap = max_overlap(list(spans.values()))
    require(overlap == 4, f"stand-ins ran {overlap} at a time, concurrency is 4")
    first_block = [spans[f"{arm}/s1-r0"][0] for arm in "abcd"]
    second_block = [spans[f"{arm}/s2-r0"][0] for arm in "abcd"]
    require(max(first_block) <= min(second_block), "a cell of seed 2 started before every seed 1 cell had started")
    if LINUX:
        for a in spans:
            for b in spans:
                if a < b and spans[a][0] < spans[b][1] and spans[b][0] < spans[a][1]:
                    require(not set(cells[a]["cpus"]) & set(cells[b]["cpus"]), f"{a} and {b} share CPUs")
        require(all(len(info["cpus"]) == 1 for info in cells.values()), "cpus_per_cell 1 not applied")
    else:
        require(all(info.get("cpus", "missing") is None for info in cells.values()),
                "without CPU affinity support cell.json must record cpus null")

    real = tmp / "real"
    raw_real = {"schema": 1, "name": "s15-parallel", "budget": {"minutes": C.PARALLEL_MINUTES},
                "seeds": [C.PARALLEL_SEED], "concurrency": 4, "cpus_per_cell": 2, "engine_threads": 2,
                "arms": list(C.PARALLEL_ARMS)}
    cfg_path = write_config(tmp / "real.json", raw_real)
    proc = py(["-m", "surprise.experiments.grid", "run", str(cfg_path), "--out", str(real)], timeout=1200)
    require(proc.returncode == 0, f"parallel smoke exited {proc.returncode}: {proc.stderr[-600:]}")
    status = py(["-m", "surprise.experiments.grid", "status", str(real)], timeout=120).stdout.split("\n")
    require("done 4/4" in status, f"status: {status[-3:]}")
    starts, ends = [], []
    for arm in C.PARALLEL_ARMS:
        label = f"{arm['name']}/s{C.PARALLEL_SEED}-r0"
        directory = real / "cells" / arm["name"] / f"s{C.PARALLEL_SEED}-r0"
        info = load_json(directory / "cell.json", f"{label} cell.json")
        report = load_json(directory / "report.json", f"{label} report.json")
        require(info.get("returncode") == 0 and info.get("killed") is False, f"{label}: {info.get('returncode')}")
        wall = info.get("wall_s")
        require(C.PARALLEL_WALL_S[0] <= wall <= C.PARALLEL_WALL_S[1], f"{label}: wall {wall}")
        require(report.get("status") == "budget_minutes" and report.get("experiments", 0) > 0,
                f"{label}: report {report.get('status')} / {report.get('experiments')}")
        starts.append(iso_seconds(info["started_at"]))
        ends.append(iso_seconds(info["finished_at"]))
    spread = max(starts) - min(starts)
    require(spread <= C.PARALLEL_START_SPREAD_S, f"the four cells started {spread:.0f}s apart")
    require(max(starts) < min(ends), "the four cells did not all run at the same time")
    return (f"8 stand-ins, 4 at a time in block order with slots{', CPUs' if LINUX else ''} and engine threads; "
            f"4 real DuckDB cells ran together (start spread {spread:.0f}s)")


# ---- kill ---------------------------------------------------------------------------------------

_HANDLES = (
    "import json, os, signal, sys, time\n"
    "out = sys.argv[1]; os.makedirs(out, exist_ok=True)\n"
    "def stop(*_):\n    raise KeyboardInterrupt\n"
    "if hasattr(signal, 'SIGBREAK'):\n    signal.signal(signal.SIGBREAK, stop)\n"
    "try:\n    while True:\n        time.sleep(0.2)\n"
    "except KeyboardInterrupt:\n"
    "    json.dump({'status': 'interrupted'}, open(os.path.join(out, 'report.json'), 'w'))\n"
    "    sys.exit(130)\n"
)
_IGNORE_SIGNALS = (
    "import signal\n"
    "for name in ('SIGINT', 'SIGBREAK', 'SIGTERM'):\n"
    "    if hasattr(signal, name):\n        signal.signal(getattr(signal, name), signal.SIG_IGN)\n"
)
_IGNORES = (
    _IGNORE_SIGNALS
    + "import os, subprocess, sys, time\n"
    "out = sys.argv[1]; os.makedirs(out, exist_ok=True)\n"
    "child = subprocess.Popen([sys.executable, '-c', " + repr(_IGNORE_SIGNALS + "import time\nwhile True: time.sleep(1)\n") + "])\n"
    "open(os.path.join(out, 'grandchild.pid'), 'w').write(str(child.pid))\n"
    "while True:\n    time.sleep(0.2)\n"
)
_QUICK = "import os, sys, time\nos.makedirs(sys.argv[1], exist_ok=True)\ntime.sleep(0.5)\n"


def check_kill() -> str:
    grid = grid_module()
    require(hasattr(grid, C.HARD_KILL_CONSTANT), f"grid has no {C.HARD_KILL_CONSTANT}")
    tmp = tmpdir("kill")
    arms = [{"name": name, "kind": "surprise", "engines": ["duckdb"]} for name in ("handles", "ignores", "quick")]
    raw = {"schema": 1, "name": "s15-kill", "budget": {"minutes": 0.05}, "seeds": [1], "concurrency": 3,
           "kill_grace_minutes": 0.05, "arms": arms}
    config = grid.load_config(write_config(tmp / "kill.json", raw))
    scripts = {"handles": _HANDLES, "ignores": _IGNORES, "quick": _QUICK}
    spawned: list[str] = []

    def fake(arm: Any, *, out: Path, seed: int, rep: int) -> list[str]:
        spawned.append(arm["name"])
        return [sys.executable, "-c", scripts[arm["name"]], str(out)]

    out = tmp / "out"
    with patched(grid, command_for=fake, **{C.HARD_KILL_CONSTANT: 3.0}):
        code = grid.run_grid(config, out)
        require(code == 0, f"kill grid exited {code}")
        info = {name: load_json(out / "cells" / name / "s1-r0" / "cell.json", f"{name} cell.json") for name in scripts}
        handles, ignores, quick = info["handles"], info["ignores"], info["quick"]
        require(handles.get("status") == "done" and handles.get("killed") is True and handles.get("hard_killed") is False
                and handles.get("returncode") == 130, f"interrupted cell: {handles}")
        require(5.0 <= handles["wall_s"] <= 30.0, f"interrupted cell ran {handles['wall_s']:.1f}s, deadline is 6s")
        require(load_json(out / "cells" / "handles" / "s1-r0" / "report.json", "child report")["status"] == "interrupted",
                "the interrupted child did not get to write its report")
        require(ignores.get("status") == "done" and ignores.get("killed") is True and ignores.get("hard_killed") is True,
                f"hard-killed cell: {ignores}")
        require(8.0 <= ignores["wall_s"] <= 45.0, f"hard-killed cell ran {ignores['wall_s']:.1f}s, expected about 9s")
        require(quick.get("status") == "done" and quick.get("killed") is False and quick.get("hard_killed") is False
                and quick.get("returncode") == 0, f"quick cell: {quick}")
        require(abs(handles.get("deadline_s", 0) - 6.0) < 0.01, f"deadline_s {handles.get('deadline_s')}, budget+grace is 6s")
        grandchild = int((out / "cells" / "ignores" / "s1-r0" / "grandchild.pid").read_text(encoding="utf-8"))
        wait_for(lambda: not pid_alive(grandchild), 20, f"the hard-killed cell's grandchild {grandchild} to die")
        lines = grid.status_text(out).strip().split("\n")
        require(lines == ["handles/s1-r0 done (killed)", "ignores/s1-r0 done (killed)", "quick/s1-r0 done", "done 3/3"],
                f"status: {lines}")
        before = len(spawned)
        require(grid.run_grid(config, out) == 0 and len(spawned) == before, "a killed cell was run again")
    return "interrupt at budget+grace (report written, exit 130), hard kill of the tree after the delay, done (killed), not rerun"


# ---- interrupt ----------------------------------------------------------------------------------

def _interrupt_run(argv: list[str], out: Path, ready: Callable[[], bool], what: str) -> dict[str, Any]:
    proc = subprocess.Popen([sys.executable, *argv], cwd=FRAMEWORK, env=clean_env(), stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, **new_group_kwargs())
    try:
        wait_for(lambda: ready() or proc.poll() is not None, 180, f"{what} to start working")
        require(proc.poll() is None, f"{what} ended before the interrupt: {proc.stderr.read()[-600:] if proc.stderr else ''}")
        send_interrupt(proc)
        code = proc.wait(timeout=240)
    finally:
        if proc.poll() is None:
            proc.kill()
    require(code == 130, f"{what} exited {code} after the interrupt, expected 130")
    report = load_json(out / "report.json", f"{what} report.json")
    require(report.get("status") == "interrupted", f"{what} report status {report.get('status')!r}")
    return report


def check_interrupt() -> str:
    tmp = tmpdir("interrupt")
    loop_out = tmp / "loop"
    loop = _interrupt_run(
        ["-m", "surprise.experiments.loop", "--out", str(loop_out), "--seed", "3", "--max-minutes", "5",
         "--engine", "duckdb", "--oracle", "tlp", "--oracle", "norec"],
        loop_out, lambda: len(lines_of(loop_out / "progress.jsonl")) >= 3, "the loop")
    sq_out = tmp / "sqlancer"
    sq = _interrupt_run(
        ["-m", C.SQLANCER_MODULE, "--out", str(sq_out), "--seed", "3", "--engine", "duckdb", "--max-minutes", "5"],
        sq_out, lambda: (sq_out / "sqlancer").is_dir() and time.sleep(20) is None, "the SQLancer driver")
    pid = (sq.get("sqlancer") or {}).get("pid")
    require(isinstance(pid, int), f"SQLancer driver report has no sqlancer.pid: {sq.get('sqlancer')}")
    wait_for(lambda: not pid_alive(pid), 30, f"the SQLancer java process {pid} to end")
    return f"loop interrupted after {loop.get('experiments')} experiments; SQLancer driver and its java process stopped"


# ---- stream -------------------------------------------------------------------------------------

_PEAK = r'''
import json, sys
def peak_mb():
    if sys.platform == "win32":
        import ctypes, ctypes.wintypes as wt
        class P(ctypes.Structure):
            _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD)] + [(n, ctypes.c_size_t) for n in
                ("PeakWorkingSetSize", "WorkingSetSize", "q1", "q2", "q3", "q4", "PagefileUsage", "PeakPagefileUsage")]
        p = P(); p.cb = ctypes.sizeof(P)
        k = ctypes.windll.kernel32; k.GetCurrentProcess.restype = ctypes.c_void_p
        ps = ctypes.windll.psapi; ps.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wt.DWORD]
        ps.GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(p), p.cb)
        return p.PeakWorkingSetSize / 2**20
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
from surprise.metrics.rq import run_metrics
m = run_metrics(sys.argv[1])
if len(sys.argv) > 2:
    open(sys.argv[2], "w", encoding="utf-8").write(json.dumps(m, sort_keys=True, ensure_ascii=True, separators=(",", ":")))
print(json.dumps({"peak_mb": peak_mb(), "executions": m["rq1"]["executions"]}))
'''


def _metrics_peak(run: Path, dump: Path | None = None) -> dict[str, Any]:
    argv = ["-c", _PEAK, str(run)] + ([str(dump)] if dump else [])
    proc = py(argv, timeout=3600)
    require(proc.returncode == 0, f"run_metrics on {run.name} failed: {proc.stderr[-800:]}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _double_run(source: Path, target: Path) -> None:
    target.mkdir(parents=True)
    for name in ("config.json", "report.json"):
        shutil.copyfile(source / name, target / name)
    progress = lines_of(source / "progress.jsonl")
    with (target / "progress.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in progress:
            handle.write(json.dumps(row) + "\n")
        for row in progress:
            twin = dict(row)
            if isinstance(twin.get("record_id"), str):
                twin["record_id"] += "-d"
            if isinstance(twin.get("seq"), int):
                twin["seq"] += 1_000_000
            handle.write(json.dumps(twin) + "\n")
    shutil.copyfile(source / "ledger.sqlite", target / "ledger.sqlite")
    with contextlib.closing(sqlite3.connect(target / "ledger.sqlite")) as db:
        rid, blob = db.execute("SELECT record_id, record_json FROM records LIMIT 1").fetchone()
        inner = json.loads(blob)
        require(inner.get("record_id") == rid and "seq" in inner, "ledger record_json does not carry record_id and seq")
        db.execute(
            "INSERT INTO records (record_id, run_id, seq, oracle, y, theory_version, purpose, created_at, record_json) "
            "SELECT record_id || '-d', run_id, seq + 1000000, oracle, y, theory_version, purpose, created_at, "
            "json_set(record_json, '$.record_id', record_id || '-d', '$.seq', seq + 1000000) FROM records")
        db.commit()


def check_stream() -> str:
    run = REPO / C.STREAM_RUN
    require((run / "ledger.sqlite").is_file(), f"{C.STREAM_RUN} is missing (kept by S11, not in git)")
    tmp = tmpdir("stream")
    single = _metrics_peak(run, tmp / "metrics.json")
    blob = (tmp / "metrics.json").read_text(encoding="utf-8")
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    if digest != C.STREAM_SHA256:
        got, want = json.loads(blob), load_json(DATA / "stream_expected.json", "stream_expected.json")
        differ = sorted(k for k in set(got) | set(want) if got.get(k) != want.get(k))
        sub = {k: sorted(s for s in set(got.get(k) or {}) | set(want.get(k) or {})
                         if (got.get(k) or {}).get(s) != (want.get(k) or {}).get(s)) for k in differ}
        raise GateFailure(f"run_metrics output changed: sections {differ}, keys {sub}")
    require(single["executions"] == C.STREAM_RECORDS, f"{single['executions']} executions, expected {C.STREAM_RECORDS}")
    require(single["peak_mb"] <= C.STREAM_PEAK_MB, f"run_metrics peak {single['peak_mb']:.0f} MB > {C.STREAM_PEAK_MB} MB")
    doubled = tmp / "doubled"
    _double_run(run, doubled)
    twice = _metrics_peak(doubled)
    require(twice["executions"] == 2 * C.STREAM_RECORDS, f"doubled run has {twice['executions']} executions")
    growth = twice["peak_mb"] - single["peak_mb"]
    require(growth <= C.STREAM_GROWTH_MB, f"doubling the ledger added {growth:.0f} MB (cap {C.STREAM_GROWTH_MB})")
    return (f"same metrics as before S15 on {C.STREAM_RECORDS} records; peak {single['peak_mb']:.0f} MB "
            f"(before: 3.3 GB on 8600); doubled ledger adds {growth:.0f} MB")


# ---- llm ----------------------------------------------------------------------------------------

class _Echo:
    def __init__(self) -> None:
        self.models: list[str] = []

    def complete(self, *, model: str, prompt: str, temperature: float, max_tokens: int, role: str) -> Any:
        from surprise.roles.gateway import Completion

        self.models.append(model)
        return Completion(text=json.dumps({"prediction": "x"}), input_tokens=1, output_tokens=1)


def _m3_argv(out: Path, cache: Path, boot: Path, extra: list[str]) -> list[str]:
    from . import s10_cases as C10

    spec = C10.M3_RUN
    argv = ["-m", "surprise.experiments.loop", "--out", str(out), "--seed", str(spec["seed"]),
            "--max-experiments", str(spec["max_experiments"]), "--bootstrap", str(boot), "--llm-cache", str(cache),
            "--llm-offline"]
    for engine in spec["engines"]:
        argv += ["--engine", engine]
    for oracle in spec["oracles"]:
        argv += ["--oracle", oracle]
    for role in spec["roles"]:
        argv += ["--llm", role]
    return argv + extra


def check_llm() -> str:
    from surprise.roles.gateway import Gateway

    from . import s04 as G4
    from . import s10_cases as C10
    from . import s11_cases as C11

    tmp = tmpdir("llm")
    with env_var(C.CAP_ENV, None):
        require(Gateway(cache_dir=tmp / "g0").max_calls == C.DEFAULT_MAX_CALLS, "default cap changed")
        unlimited = Gateway(cache_dir=tmp / "g1", max_calls=C.UNLIMITED)
        require(unlimited.max_calls is None and unlimited.manifest()["max_calls"] == C.UNLIMITED
                and unlimited.totals()["max_calls"] == C.UNLIMITED, "unlimited gateway: max_calls/manifest/totals")
        require(Gateway(cache_dir=tmp / "g2", max_calls=5).max_calls == 5, "explicit cap changed")
        for bad in ("lots", "5"):
            try:
                Gateway(cache_dir=tmp / "g3", max_calls=bad)
            except ValueError:
                continue
            raise GateFailure(f"Gateway accepted max_calls={bad!r}")
        echo = _Echo()
        strong = Gateway(cache_dir=tmp / "g4", transport=echo, tier="strong")
        reply = strong.call("implementer", "prompt", tier="fast", seed=0)
        require(echo.models == [C.MODELS["strong"]] and reply.tier == "strong" and reply.model == C.MODELS["strong"],
                f"tier override: transport saw {echo.models}, reply {reply.tier}/{reply.model}")
        require(strong.manifest().get("tier") == "strong" and Gateway(cache_dir=tmp / "g5").manifest().get("tier", "x") is None,
                "manifest must record the tier override (None by default)")
        plain = Gateway(cache_dir=tmp / "g6", transport=echo)
        plain.call("implementer", "prompt", tier="fast", seed=0)
        require(echo.models[-1] == C.MODELS["fast"], "without an override the role's tier must be used")
        try:
            Gateway(cache_dir=tmp / "g7", tier="medium")
        except ValueError:
            pass
        else:
            raise GateFailure("Gateway accepted tier='medium'")
    with env_var(C.CAP_ENV, "2"):
        require(Gateway(cache_dir=tmp / "g8", max_calls=C.UNLIMITED).max_calls == 2, "the environment ceiling must cap unlimited")

    m3 = REPO / "framework/surprise/gates/s10_llm/m3"
    boot = tmp / "bootstrap.json"
    boot.write_text(json.dumps([{"case": G4.load(item["case"]).to_dict(), "oracle": item["oracle"], "rule": item["rule"]}
                                for item in C10.M3_RUN["bootstrap"]]), encoding="utf-8")
    shutil.copytree(m3 / "cache", tmp / "cache-u")
    out_u = tmp / "m3-unlimited"
    proc = py(_m3_argv(out_u, tmp / "cache-u", boot, ["--llm-max-calls", C.UNLIMITED]), timeout=3600)
    require(proc.returncode == 0, f"M3 replay with unlimited calls failed: {proc.stderr[-800:]}")
    require(rows_of(out_u / "progress.jsonl") == rows_of(m3 / "expected" / "progress.jsonl"),
            "M3 replay with unlimited calls differs from the recording")
    require(load_json(out_u / "config.json", "config.json")["llm"]["max_calls"] == C.UNLIMITED,
            "config.json does not record max_calls unlimited")
    shutil.copytree(m3 / "cache", tmp / "cache-s")
    out_s = tmp / "m3-strong"
    proc = py(_m3_argv(out_s, tmp / "cache-s", boot, ["--llm-tier", "strong"]), timeout=3600)
    require(proc.returncode == 0, f"M3 replay on the strong tier failed: {proc.stderr[-800:]}")
    calls = lines_of(out_s / "llm" / "calls.jsonl")
    require(calls and all(c.get("model") == C.MODELS["strong"] and c.get("tier") == "strong" and c.get("source") != "cache"
                          for c in calls), "strong tier: every call must ask deepseek-v4-pro and miss the fast cache")
    require(load_json(out_s / "config.json", "config.json")["llm"].get("tier") == "strong", "config.json lacks tier strong")

    pure = REPO / "framework/surprise/gates/s11_llm/pure_llm"
    spec = C11.PURE_RUN
    for name, extra in (("pure-unlimited", ["--llm-max-calls", C.UNLIMITED]), ("pure-strong", ["--llm-tier", "strong"])):
        shutil.copytree(pure / "cache", tmp / f"cache-{name}")
        out = tmp / name
        argv = ["-m", "surprise.baselines.pure_llm", "--out", str(out), "--seed", str(spec["seed"]), "--engine",
                spec["engine"], "--max-experiments", str(spec["experiments"]), "--llm-cache", str(tmp / f"cache-{name}"),
                "--llm-offline"] + extra
        proc = py(argv, timeout=3600)
        require(proc.returncode == 0, f"pure-LLM {name} failed: {proc.stderr[-800:]}")
        rows = lines_of(out / "llm" / "calls.jsonl")
        if name == "pure-unlimited":
            require(rows_of(out / "progress.jsonl") == rows_of(pure / "expected" / "progress.jsonl"),
                    "pure-LLM replay with unlimited calls differs from the recording")
        else:
            require(rows and all(r.get("model") == C.MODELS["strong"] for r in rows), "pure-LLM strong tier model")
    for argv in (["-m", "surprise.experiments.loop", "--out", str(tmp / "bad1"), "--seed", "0", "--llm-max-calls", "lots"],
                 ["-m", "surprise.experiments.loop", "--out", str(tmp / "bad2"), "--seed", "0", "--llm-tier", "medium"]):
        proc = py(argv, timeout=300)
        require(proc.returncode == 2, f"{argv[-2:]} exited {proc.returncode}, expected 2")
    return (f"gateway: unlimited, env ceiling, tier override; M3 replay identical with unlimited calls; "
            f"{len(calls)} strong-tier calls went to deepseek-v4-pro; pure-LLM the same")


# ---- sqlancer -----------------------------------------------------------------------------------

def check_sqlancer() -> str:
    from surprise.harness.ledger import Ledger
    from surprise.metrics.rq import label_key, run_metrics
    from surprise.metrics.rundata import RunData

    patch = REPO / C.SQLANCER_PATCH
    require(patch.is_file() and "logEachSelect() && getOptions().logExecutionTime()" in patch.read_text(encoding="utf-8"),
            "the SQLancer log-each-select patch is not in docs/sqlancer")
    tmp = tmpdir("sqlancer")
    logs = tmp / "logs"
    logs.mkdir()
    for name in C.SQLANCER_FIXTURES:
        text = (DATA / "sqlancer" / name).read_text(encoding="utf-8").replace("\r\n", "\n")
        (logs / name).write_text(text, encoding="utf-8", newline="\n")
    out = tmp / "replay"
    proc = py(["-m", C.SQLANCER_MODULE, "--out", str(out), "--seed", "7", "--engine", "duckdb", "--replay-logs", str(logs)],
              timeout=1800)
    require(proc.returncode == 0, f"replay of the SQLancer fixtures failed: {proc.stderr[-800:]}")
    report = load_json(out / "report.json", "replay report.json")
    stats = report.get("sqlancer") or {}
    kinds: dict[str, int] = {}
    for spec in C.SQLANCER_FIXTURES.values():
        kinds[spec["kind"]] = kinds.get(spec["kind"], 0) + 1
    require(stats.get("reports") == len(C.SQLANCER_FIXTURES) and stats.get("kinds") == kinds
            and stats.get("converted") == 1 and stats.get("judged") == 1 and stats.get("unjudged") == 0,
            f"replay counts: {stats}")
    rows = {Path(row["log"]).name: row for row in lines_of(out / "sqlancer" / "reports.jsonl")}
    for name, spec in C.SQLANCER_FIXTURES.items():
        row = rows.get(name)
        require(row is not None, f"reports.jsonl has no line for {name}")
        for key, value in spec.items():
            require(row.get(key) == value, f"{name}: {key} is {row.get(key)!r}, expected {value!r}")
    with Ledger(out / "ledger.sqlite") as ledger:
        run_ids = ledger.run_ids()
        records = list(ledger.records(run_id=run_ids[0]))
        manifest = ledger.run_manifest(run_ids[0])
    require(manifest.get("baseline") == "sqlancer", f"ledger manifest baseline {manifest.get('baseline')!r}")
    require(len(records) == 1, f"{len(records)} ledger records, expected 1")
    record = records[0]
    require(record.case.to_dict() == C.NOREC_CASE, f"converted case {record.case.to_dict()}")
    require(record.label.oracle == "norec" and record.label.y == "fail", f"judged {record.label.oracle}/{record.label.y}")
    key = label_key(record)
    require(key == C.NOREC_KEY, f"family key {key!r}, the loop's is {C.NOREC_KEY!r}")
    require(rows["norec_mismatch.log"].get("record_id") == record.record_id, "reports.jsonl does not point at the record")
    require(RunData.open(out).kind == "sqlancer", "RunData does not see a sqlancer run")
    replay_metrics = run_metrics(out)
    require(replay_metrics["rq1"]["family_count"] == 1, f"run_metrics family_count {replay_metrics['rq1']['family_count']}")

    live = tmp / "live"
    raw = {"schema": 1, "name": "s15-sqlancer", "budget": {"minutes": C.SQLANCER_LIVE_MINUTES}, "seeds": [7],
           "arms": [{"name": "sqlancer", "kind": "sqlancer", "engine": "duckdb", "run": True}]}
    cfg = write_config(tmp / "live.json", raw)
    proc = py(["-m", "surprise.experiments.grid", "run", str(cfg), "--out", str(live)],
              timeout=C.SQLANCER_LIVE_MINUTES * 60 + 1800)
    require(proc.returncode == 0, f"live SQLancer grid exited {proc.returncode}: {proc.stderr[-600:]}")
    cell = live / "cells" / "sqlancer" / "s7-r0"
    info = load_json(cell / "cell.json", "live cell.json")
    require(info.get("status") == "done" and info.get("killed") is False, f"live cell: {info.get('status')} {info.get('killed')}")
    report = load_json(cell / "report.json", "live report.json")
    stats = report.get("sqlancer") or {}
    require(report.get("status") == "budget_minutes", f"live status {report.get('status')!r}")
    require(isinstance(report.get("executions"), int) and report["executions"] >= C.SQLANCER_MIN_EXECUTIONS,
            f"SQLancer executed {report.get('executions')} queries")
    require(stats.get("commit") == C.SQLANCER_COMMIT, f"SQLancer commit {stats.get('commit')!r}")
    jdbc = stats.get("jdbc") or []
    require(f"duckdb_jdbc-{C.DUCKDB_JDBC}.jar" in jdbc and not any("1.3.0.0" in jar for jar in jdbc),
            f"JDBC drivers {jdbc}")
    require(sum((stats.get("kinds") or {}).values()) == stats.get("reports")
            and stats.get("judged", 0) + stats.get("unjudged", 0) == stats.get("converted"), f"live counts: {stats}")
    size = sum(path.stat().st_size for path in (cell / "sqlancer").rglob("*") if path.is_file())
    require(size <= C.SQLANCER_MAX_LOG_MB * 2**20, f"SQLancer logs take {size / 2**20:.0f} MB")
    proc = py(["-m", "surprise.metrics.report", str(live)], timeout=1800)
    require(proc.returncode == 0, f"report on the live grid failed: {proc.stderr[-600:]}")
    grid_report = load_json(live / "report" / "report.json", "live grid report")
    require(grid_report["arms"]["sqlancer"]["cells"] == ["sqlancer/s7-r0"], "the report does not read the SQLancer cell")
    require(grid_report["rq1"]["arms"]["sqlancer"]["families_per_hour"]["n"] == 1,
            "the SQLancer arm's families per hour must come from the run")
    return (f"4 fixtures classified, the NoREC one judged fail with the loop's key {C.NOREC_KEY}; live run: "
            f"{report['executions']} queries, {stats.get('reports')} reports, {stats.get('judged')} judged, "
            f"{size / 2**20:.1f} MB of logs")


# ---- prices -------------------------------------------------------------------------------------

def check_prices() -> str:
    from surprise.metrics.rq import _usd

    data = load_json(REPO / C.PRICES_FILE, "price table")
    require(data == C.PRICES, f"price table differs from the page read on {C.PRICES['retrieved']}: "
            f"{sorted(k for k in set(data) | set(C.PRICES) if data.get(k) != C.PRICES.get(k))}")
    grid = grid_module()
    tmp = tmpdir("prices")
    cfg = grid.load_config(write_config(tmp / "p.json", {
        "schema": 1, "name": "p", "budget": {"minutes": 1.0}, "seeds": [1], "prices": data["grid"],
        "arms": [{"name": "nollm", "kind": "surprise"}]}))
    require(cfg["prices"] == data["grid"], "grid did not keep the prices")
    rows = [{"model": "deepseek-flash", "input_tokens": 1_000_000, "output_tokens": 2_000_000},
            {"model": "deepseek-v4-pro", "input_tokens": 500_000, "output_tokens": 100_000}]
    want = 0.3 + 2 * 1.2 + 0.5 * 1.32 + 0.1 * 3.96
    got = _usd(rows, cfg["prices"])
    require(abs(got - want) < 1e-9, f"cost {got} != {want}")
    return f"DeepSeek prices of {data['retrieved']} (peak cache-miss input, peak output) price both tiers"


# ---- archive ------------------------------------------------------------------------------------

_FAKE_CELL = (
    "import json, os, sys\n"
    "out = sys.argv[1]; os.makedirs(os.path.join(out, 'theory'), exist_ok=True)\n"
    "open(os.path.join(out, 'ledger.sqlite'), 'wb').write(os.urandom(200000))\n"
    "open(os.path.join(out, 'theory', 'head.json'), 'w').write('{}')\n"
    "open(os.path.join(out, 'progress.jsonl'), 'w').write('{}\\n')\n"
    "json.dump({'status': 'budget_minutes'}, open(os.path.join(out, 'report.json'), 'w'))\n"
    "json.dump({'seed': 1}, open(os.path.join(out, 'config.json'), 'w'))\n"
)


def _tree(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}


def check_archive() -> str:
    grid = grid_module()
    tmp = tmpdir("archive")
    raw = {"schema": 1, "name": "s15-archive", "budget": {"minutes": 1.0}, "seeds": [1, 2],
           "arms": [{"name": "a", "kind": "surprise"}, {"name": "b", "kind": "surprise"}]}
    config = grid.load_config(write_config(tmp / "a.json", raw))
    out = tmp / "grid"

    def fake(arm: Any, *, out: Path, seed: int, rep: int) -> list[str]:
        return [sys.executable, "-c", _FAKE_CELL, str(out)]

    with patched(grid, command_for=fake):
        require(grid.run_grid(config, out) == 0, "archive fixture grid failed")
    (out / "report").mkdir()
    (out / "report" / "report.json").write_text("{}", encoding="utf-8")
    before = _tree(out)
    twin = tmp / "twin"
    shutil.copytree(out, twin)
    dest = tmp / "grid.tar.gz"
    proc = py(["-m", C.ARCHIVE_MODULE, "pack", str(out), "--dest", str(dest)], timeout=600)
    require(proc.returncode == 0 and dest.is_file() and Path(str(dest) + ".json").is_file(),
            f"pack failed: {proc.returncode} {proc.stderr[-400:]}")
    manifest = load_json(Path(str(dest) + ".json"), "archive manifest")
    require(set(manifest.get("files", {})) == before, "the manifest does not list every file of the grid")
    require(manifest.get("tar_sha256") == hashlib.sha256(dest.read_bytes()).hexdigest(), "tar_sha256 is wrong")
    require(py(["-m", C.ARCHIVE_MODULE, "verify", str(dest)], timeout=600).returncode == 0, "verify failed on a good archive")
    bad = tmp / "bad.tar.gz"
    blob = bytearray(dest.read_bytes())
    blob[len(blob) // 2] ^= 0xFF
    bad.write_bytes(bytes(blob))
    shutil.copyfile(Path(str(dest) + ".json"), Path(str(bad) + ".json"))
    require(py(["-m", C.ARCHIVE_MODULE, "verify", str(bad)], timeout=600).returncode != 0, "verify passed a corrupted archive")
    (twin / "cells" / "a" / "s1-r0" / "ledger.sqlite").write_bytes(b"changed")
    proc = py(["-m", C.ARCHIVE_MODULE, "prune", str(twin), "--archive", str(dest)], timeout=600)
    require(proc.returncode != 0 and (twin / "cells" / "b" / "s1-r0" / "ledger.sqlite").is_file(),
            "prune must refuse, and delete nothing, when the directory does not match the archive")
    proc = py(["-m", C.ARCHIVE_MODULE, "prune", str(out), "--archive", str(dest)], timeout=600)
    require(proc.returncode == 0, f"prune failed: {proc.stderr[-400:]}")
    after = _tree(out)
    kept_names = {Path(name).name for name in after}
    require(not any(Path(name).parts[-1] in C.ARCHIVE_DROP or "theory" in Path(name).parts for name in after),
            f"prune left raw data: {sorted(after)[:8]}")
    require("grid.json" in after and "report/report.json" in after and kept_names <= set(C.ARCHIVE_KEEP),
            f"prune kept {sorted(after)}")
    require(all(f"cells/{arm}/s{seed}-r0/cell.json" in after for arm in "ab" for seed in (1, 2)), "prune dropped cell.json")
    import tarfile

    unpacked = tmp / "unpacked"
    with tarfile.open(dest) as archive:
        archive.extractall(unpacked, filter="data")
    root = unpacked / manifest["root"]
    require(_tree(root) == before, "the archive does not hold the whole grid directory")
    sample = "cells/a/s1-r0/ledger.sqlite"
    require(hashlib.sha256((root / sample).read_bytes()).hexdigest() == manifest["files"][sample], "unpacked ledger hash")
    return f"{len(before)} files packed and verified; corruption detected; prune refuses a mismatch and keeps the summaries"


# ---- docs and scope -----------------------------------------------------------------------------

def check_docs() -> str:
    server = (REPO / C.SERVER).read_text(encoding="utf-8").replace("\r\n", "\n")
    for heading in C.SERVER_HEADINGS:
        require(re.search(rf"^{re.escape(heading)}", server, re.M) is not None, f"SERVER.md: no heading {heading!r}")
    require(C.SQLANCER_COMMIT in server and C.SQLANCER_PATCH.split("framework/surprise/docs/", 1)[1] in server,
            "SERVER.md must name the SQLancer commit and the patch")
    for module in (C.ARCHIVE_MODULE, C.SQLANCER_MODULE):
        proc = py(["-m", module, "--help"], timeout=300)
        require(proc.returncode == 0, f"{module} --help exited {proc.returncode}")
    handoff = (REPO / C.HANDOFF).read_text(encoding="utf-8")
    require(re.search(r"^\| S15 \|", handoff, re.M) is not None, "HANDOFF.md has no S15 row")
    return f"SERVER.md has {len(C.SERVER_HEADINGS)} new sections and the SQLancer build; modules answer --help; HANDOFF has S15"


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
    outside = [path for path in changed if not any(path.startswith(prefix) or path == prefix for prefix in C.ALLOWED_CHANGES)]
    require(not outside, f"changes outside S15 scope ({where}): {outside[:10]}")
    return f"{len(changed)} paths changed ({where}), all in scope; harness and lower layers untouched"


# ---- main ---------------------------------------------------------------------------------------

GROUPS: dict[str, Callable[[], str]] = {
    "config": check_config,
    "parallel": check_parallel,
    "kill": check_kill,
    "interrupt": check_interrupt,
    "stream": check_stream,
    "llm": check_llm,
    "sqlancer": check_sqlancer,
    "prices": check_prices,
    "archive": check_archive,
    "docs": check_docs,
    "scope": check_scope,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S15 gate (experiment infrastructure)")
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
    print(f"S15 GATE{label}: {'PASS' if failed == 0 else 'FAIL'} ({passed}/{len(selected)} groups passed)", flush=True)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
