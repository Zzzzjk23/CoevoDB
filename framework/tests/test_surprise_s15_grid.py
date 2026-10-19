"""Grid concurrency, block order, CPU share, engine threads, and wall-clock kill."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from surprise.baselines import sqlancer
from surprise.experiments import grid
from surprise.gates import s15_cases as cases
from surprise.harness.contracts import ORACLE_IDS

FRAMEWORK = Path(__file__).resolve().parents[1]
REPO = FRAMEWORK.parent
SMOKE = REPO / "framework" / "surprise" / "docs" / "grids" / "s14_smoke.json"

_STAMP = (
    "import json, os, sys, time\n"
    "out, seconds, var = sys.argv[1], float(sys.argv[2]), sys.argv[3]\n"
    "os.makedirs(out, exist_ok=True)\n"
    "start = time.time()\n"
    "time.sleep(seconds)\n"
    "affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None\n"
    "json.dump({'start': start, 'end': time.time(), 'threads': os.environ.get(var),"
    " 'affinity': affinity, 'key': 'DEEPSEEK_API_KEY' in os.environ},"
    " open(os.path.join(out, 'stamp.json'), 'w'))\n"
)
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
_IGNORE = (
    "import signal\n"
    "for name in ('SIGINT', 'SIGBREAK', 'SIGTERM'):\n"
    "    if hasattr(signal, name):\n        signal.signal(getattr(signal, name), signal.SIG_IGN)\n"
)
_IGNORES = (
    _IGNORE
    + "import os, subprocess, sys, time\n"
    "out = sys.argv[1]; os.makedirs(out, exist_ok=True)\n"
    "child = subprocess.Popen([sys.executable, '-c', "
    + repr(_IGNORE + "import time\nwhile True: time.sleep(1)\n")
    + "])\n"
    "open(os.path.join(out, 'grandchild.pid'), 'w').write(str(child.pid))\n"
    "while True:\n    time.sleep(0.2)\n"
)
_QUICK = "import os, sys, time\nos.makedirs(sys.argv[1], exist_ok=True)\ntime.sleep(0.4)\n"


def _write(tmp_path: Path, body: dict, name: str = "grid.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def _base(**extra: object) -> dict:
    body = {
        "schema": 1,
        "name": "s15",
        "budget": {"minutes": 1},
        "seeds": [1],
        "arms": [{"name": "a", "kind": "surprise", "engines": ["duckdb"]}],
    }
    body.update(extra)
    return body


def _files(root: Path) -> dict[str, bytes]:
    found = {}
    if not root.exists():
        return found
    for path in sorted(root.rglob("*")):
        if path.is_file():
            found[path.relative_to(root).as_posix()] = path.read_bytes()
    return found


def _overlap(spans: list[tuple[float, float]]) -> int:
    events = sorted(
        [(start, 1) for start, _ in spans] + [(end, -1) for _, end in spans],
        key=lambda event: (event[0], event[1]),
    )
    best = current = 0
    for _, delta in events:
        current += delta
        best = max(best, current)
    return best


def _alive(pid: int) -> bool:
    if sys.platform == "win32":
        import ctypes

        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        code = ctypes.c_ulong()
        kernel.GetExitCodeProcess(handle, ctypes.byref(code))
        kernel.CloseHandle(handle)
        return code.value == 259
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def test_new_keys_default_and_round_trip(tmp_path: Path) -> None:
    config = grid.load_config(_write(tmp_path, _base()))
    assert config["concurrency"] == 1
    assert config["cpus_per_cell"] is None
    assert config["engine_threads"] is None
    assert config["kill_grace_minutes"] == 10.0
    assert config["arms"][0]["tier"] is None
    again = _write(tmp_path, config, "again.json")
    assert grid.load_config(again) == config

    explicit = grid.load_config(_write(tmp_path, _base(
        concurrency=4, cpus_per_cell=2, engine_threads=2, kill_grace_minutes=10,
    ), "explicit.json"))
    assert explicit["concurrency"] == 4
    assert explicit["cpus_per_cell"] == 2
    assert explicit["engine_threads"] == 2
    assert explicit["kill_grace_minutes"] == 10.0


@pytest.mark.parametrize(
    "key,value",
    [
        ("concurrency", 0),
        ("concurrency", 1.5),
        ("concurrency", "4"),
        ("concurrency", True),
        ("concurrency", None),
        ("cpus_per_cell", 0),
        ("cpus_per_cell", True),
        ("cpus_per_cell", 1.5),
        ("cpus_per_cell", "2"),
        ("engine_threads", 0),
        ("engine_threads", "2"),
        ("engine_threads", True),
        ("engine_threads", 1.5),
        ("kill_grace_minutes", 0),
        ("kill_grace_minutes", -1),
        ("kill_grace_minutes", "x"),
        ("kill_grace_minutes", True),
        ("kill_grace_minutes", None),
        ("kill_grace_minutes", float("inf")),
        ("kill_grace_minutes", float("nan")),
    ],
)
def test_new_top_keys_reject_bad_values(tmp_path: Path, key: str, value: object) -> None:
    body = _base()
    body[key] = value
    with pytest.raises(ValueError):
        grid.load_config(_write(tmp_path, body))


def test_tier_and_unlimited_calls(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    llm = {"roles": ["implementer"], "cache": str(cache), "max_calls": "unlimited"}
    config = grid.load_config(_write(tmp_path, {
        "schema": 1,
        "name": "tiers",
        "budget": {"minutes": 1},
        "seeds": [1],
        "arms": [
            {"name": "full", "kind": "surprise", "engines": ["duckdb"], "llm": llm},
            {"name": "strong", "kind": "surprise", "engines": ["duckdb"], "tier": "strong", "llm": llm},
            {"name": "pure", "kind": "pure_llm", "llm": {"cache": str(cache), "max_calls": "unlimited"}},
            {"name": "pfast", "kind": "pure_llm", "tier": "fast", "llm": {"max_calls": 0, "offline": True}},
        ],
    }))
    arms = {arm["name"]: arm for arm in config["arms"]}
    assert arms["full"]["llm"]["max_calls"] == "unlimited" and arms["full"]["tier"] is None
    assert arms["strong"]["tier"] == "strong" and arms["pure"]["llm"]["max_calls"] == "unlimited"
    assert arms["pfast"]["tier"] == "fast" and arms["pfast"]["llm"]["max_calls"] == 0
    again = _write(tmp_path, config, "norm.json")
    assert grid.load_config(again) == config

    bad = [
        {"name": "x", "kind": "surprise", "llm": dict(llm, max_calls="lots")},
        {"name": "x", "kind": "surprise", "llm": dict(llm, max_calls=-1)},
        {"name": "x", "kind": "surprise", "llm": dict(llm, max_calls=True)},
        {"name": "x", "kind": "surprise", "llm": dict(llm, max_calls=1.5)},
        {"name": "x", "kind": "surprise", "tier": "medium", "llm": llm},
        {"name": "x", "kind": "surprise", "tier": "strong"},
        {"name": "x", "kind": "pure_llm", "tier": "medium", "llm": {"max_calls": 1, "offline": True}},
        {"name": "x", "kind": "pure_llm", "llm": {"offline": False}},
    ]
    for arm in bad:
        body = _base()
        body["arms"] = [arm]
        with pytest.raises(ValueError):
            grid.load_config(_write(tmp_path, body, "bad.json"))


def test_sqlancer_run_normalises_and_summary_stays_the_same(tmp_path: Path) -> None:
    summary = grid.load_config(_write(tmp_path, {
        "schema": 1, "name": "q", "budget": {"minutes": 1}, "seeds": [1],
        "arms": [{"name": "q", "kind": "sqlancer", "engine": "duckdb"}],
    }))
    assert set(summary["arms"][0]) == {"name", "kind", "summary", "engine", "network"}
    assert summary["arms"][0]["summary"] == str(sqlancer.SUMMARY_PATH)

    running = grid.load_config(_write(tmp_path, {
        "schema": 1, "name": "q", "budget": {"minutes": 2}, "seeds": [1],
        "arms": [{
            "name": "live", "kind": "sqlancer", "run": {"oracles": ["WHERE"], "threads": 3},
            "budget": {"minutes": 4},
        }],
    }, "run.json"))
    arm = running["arms"][0]
    assert set(arm) == {"name", "kind", "engine", "run", "budget", "network"}
    assert arm["engine"] == "duckdb" and arm["network"] is False
    assert arm["run"] == {"oracles": ["WHERE"], "threads": 3}
    assert arm["budget"] == {"minutes": 4.0}
    bare = grid.load_config(_write(tmp_path, {
        "schema": 1, "name": "q", "budget": {"minutes": 1}, "seeds": [1],
        "arms": [{"name": "live", "kind": "sqlancer", "run": True}],
    }, "bare.json"))
    assert bare["arms"][0]["run"] == {"oracles": ["NOREC", "WHERE"], "threads": 1}
    assert bare["arms"][0]["budget"] == {"minutes": 1.0}

    bad = [
        {"name": "x", "kind": "sqlancer", "budget": {"minutes": 1}},
        {"name": "x", "kind": "sqlancer", "run": None, "budget": None},
        {"name": "x", "kind": "sqlancer", "engine": "duckdb", "run": False},
        {"name": "x", "kind": "sqlancer", "engine": "duckdb", "run": True, "tier": "strong"},
        {"name": "x", "kind": "sqlancer", "engine": "duckdb", "run": True, "summary": str(tmp_path / "nope.json")},
        {"name": "x", "kind": "sqlancer", "run": True, "summary": None},
        {"name": "x", "kind": "sqlancer", "engine": "datafusion", "run": True},
        {"name": "x", "kind": "sqlancer", "engine": "duckdb", "run": {"oracles": ["PQS"]}},
        {"name": "x", "kind": "sqlancer", "engine": "duckdb", "run": {"oracles": ["NOREC", "NOREC"]}},
        {"name": "x", "kind": "sqlancer", "run": {"oracles": []}},
        {"name": "x", "kind": "sqlancer", "run": {"oracles": None}},
        {"name": "x", "kind": "sqlancer", "engine": "duckdb", "run": {"threads": 0}},
        {"name": "x", "kind": "sqlancer", "run": {"threads": None}},
        {"name": "x", "kind": "sqlancer", "run": {"threads": True}},
        {"name": "x", "kind": "sqlancer", "run": {"threads": 1.5}},
        {"name": "x", "kind": "sqlancer", "run": {"threads": "2"}},
        {"name": "x", "kind": "sqlancer", "run": 1},
        {"name": "x", "kind": "sqlancer", "engine": "duckdb", "run": {"extra": 1}},
        {"name": "x", "kind": "sqlancer", "engine": "duckdb", "run": True, "budget": {"experiments": 10}},
        {"name": "x", "kind": "sqlancer", "run": True, "llm": {"max_calls": 1}},
    ]
    for arm in bad:
        body = {"schema": 1, "name": "q", "budget": {"minutes": 1}, "seeds": [1], "arms": [arm]}
        with pytest.raises(ValueError):
            grid.load_config(_write(tmp_path, body, "bad.json"))


def test_s14_smoke_gains_only_the_new_defaults() -> None:
    config = grid.load_config(SMOKE)
    assert config["concurrency"] == 1
    assert config["cpus_per_cell"] is None
    assert config["engine_threads"] is None
    assert config["kill_grace_minutes"] == 10.0
    nollm, sq = config["arms"]
    assert nollm["tier"] is None
    assert set(sq) == {"name", "kind", "summary", "engine", "network"}
    assert sq["summary"] == str(sqlancer.SUMMARY_PATH) and sq["engine"] == "duckdb" and sq["network"] is False
    assert nollm == {
        "name": "nollm",
        "kind": "surprise",
        "budget": {"minutes": 1.0},
        "engines": ["duckdb"],
        "oracles": list(ORACLE_IDS),
        "bootstrap": None,
        "freeze": None,
        "hunter": None,
        "theory_from": None,
        "select_from": None,
        "vocabulary": None,
        "beta": None,
        "llm": None,
        "tier": None,
        "python": None,
        "network": False,
    }
    cell = SMOKE.parent / "unused-cell"
    assert grid.command_for(nollm, out=cell, seed=7, rep=0) == [
        sys.executable, "-m", "surprise.experiments.loop",
        "--out", str(cell), "--seed", "7", "--max-minutes", "1.0", "--engine", "duckdb",
    ] + [token for oracle in nollm["oracles"] for token in ("--oracle", oracle)]


def test_commands_pass_tier_unlimited_and_sqlancer_run(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    llm = {"roles": ["prior"], "cache": str(cache), "max_calls": "unlimited", "offline": True}
    config = grid.load_config(_write(tmp_path, {
        "schema": 1,
        "name": "argv",
        "budget": {"minutes": 1.5},
        "seeds": [3],
        "arms": [
            {"name": "full", "kind": "surprise", "engines": ["duckdb"], "oracles": ["tlp"], "llm": llm},
            {"name": "strong", "kind": "surprise", "engines": ["duckdb"], "oracles": ["tlp"],
             "tier": "strong", "llm": dict(llm, max_calls=5)},
            {"name": "pure", "kind": "pure_llm", "engine": "datafusion", "oracles": ["norec"],
             "llm": {"cache": str(cache), "max_calls": "unlimited"}},
            {"name": "pfast", "kind": "pure_llm", "engine": "duckdb", "oracles": ["norec"], "tier": "fast",
             "llm": {"max_calls": 2, "offline": True}, "budget": {"experiments": 4}},
            {"name": "live", "kind": "sqlancer", "run": {"oracles": ["WHERE", "NOREC"], "threads": 2}},
        ],
    }))
    arms = {arm["name"]: arm for arm in config["arms"]}

    def argv(name: str) -> list[str]:
        return grid.command_for(arms[name], out=tmp_path / name, seed=3, rep=0)

    full, strong, pure, pfast, live = argv("full"), argv("strong"), argv("pure"), argv("pfast"), argv("live")
    assert full[full.index("--llm-max-calls") + 1] == "unlimited" and "--llm-tier" not in full
    assert strong[strong.index("--llm-tier") + 1] == "strong"
    assert strong.index("--llm-tier") > strong.index("--llm-offline")
    assert pure[pure.index("--llm-max-calls") + 1] == "unlimited" and "--llm-tier" not in pure
    assert pfast[pfast.index("--llm-tier") + 1] == "fast"
    assert pfast[pfast.index("--llm-max-calls") + 1] == "2"
    assert live == [
        sys.executable, "-m", "surprise.baselines.sqlancer_run",
        "--out", str(tmp_path / "live"), "--seed", "3", "--engine", "duckdb",
        "--max-minutes", "1.5", "--oracle", "WHERE", "--oracle", "NOREC", "--threads", "2",
    ]
    with pytest.raises(ValueError):
        grid.command_for(grid.load_config(_write(tmp_path, {
            "schema": 1, "name": "q", "budget": {"minutes": 1}, "seeds": [1],
            "arms": [{"name": "q", "kind": "sqlancer"}],
        }, "summary.json"))["arms"][0], out=tmp_path / "q", seed=1, rep=0)


def test_blocks_slots_and_sqlancer_cells(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[tuple[int, int, str]] = []

    def fake(arm, *, out, seed, rep):
        order.append((rep, seed, arm["name"]))
        return [sys.executable, "-c", _STAMP, str(out), "0", grid._THREADS_ENV]

    monkeypatch.setattr(grid, "command_for", fake)
    monkeypatch.delenv(grid._THREADS_ENV, raising=False)
    config = grid.load_config(_write(tmp_path, {
        "schema": 1,
        "name": "blocks",
        "budget": {"minutes": 1},
        "seeds": [1, 2],
        "concurrency": 1,
        "engine_threads": 3,
        "arms": [
            {"name": "duck", "kind": "surprise", "engines": ["duckdb"]},
            {"name": "fusion", "kind": "surprise", "engines": ["datafusion"]},
            {"name": "live", "kind": "sqlancer", "run": True, "engine": "duckdb"},
            {"name": "old", "kind": "old_coevodb"},
            {"name": "pure", "kind": "pure_llm", "engine": "datafusion", "llm": {"offline": True}},
            {"name": "summary", "kind": "sqlancer"},
        ],
    }))
    out = tmp_path / "out"
    assert grid.run_grid(config, out) == 0
    assert order == [
        (0, 1, "duck"), (0, 1, "live"), (0, 1, "old"), (0, 1, "fusion"), (0, 1, "pure"),
        (0, 2, "duck"), (0, 2, "live"), (0, 2, "old"), (0, 2, "fusion"), (0, 2, "pure"),
    ]
    assert not (out / "cells" / "summary").exists()
    lines = grid.status_text(out).strip().split("\n")
    assert lines[-1] == "done 10/10"
    assert "summary/s1-r0" not in grid.status_text(out)
    sample = json.loads((out / "cells" / "duck" / "s1-r0" / "cell.json").read_text(encoding="utf-8"))
    assert sample["slot"] == 0 and sample["engine_threads"] == 3 and sample["killed"] is False
    assert sample["hard_killed"] is False and sample["deadline_s"] == 60.0 * 11
    stamp = json.loads((out / "cells" / "live" / "s1-r0" / "stamp.json").read_text(encoding="utf-8"))
    assert stamp["threads"] == "3" and stamp["key"] is False
    counted = grid.load_config(_write(tmp_path, {
        "schema": 1, "name": "count", "budget": {"experiments": 3}, "seeds": [1],
        "arms": [{"name": "a", "kind": "surprise", "engines": ["duckdb"]}],
    }, "count.json"))
    assert grid.run_grid(counted, tmp_path / "count") == 0
    meta = json.loads((tmp_path / "count" / "cells" / "a" / "s1-r0" / "cell.json").read_text(encoding="utf-8"))
    assert meta["deadline_s"] is None and meta["killed"] is False and meta["engine_threads"] is None


def test_concurrency_limit_and_smallest_slot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps = {"a": "0.4", "b": "1.1", "c": "0.4", "d": "0.4"}

    def fake(arm, *, out, seed, rep):
        del seed, rep
        return [sys.executable, "-c", _STAMP, str(out), sleeps[arm["name"]], grid._THREADS_ENV]

    monkeypatch.setattr(grid, "command_for", fake)
    config = grid.load_config(_write(tmp_path, {
        "schema": 1,
        "name": "slots",
        "budget": {"minutes": 1},
        "seeds": [1, 2],
        "concurrency": 2,
        "arms": [{"name": name, "kind": "surprise", "engines": ["duckdb"]} for name in "abcd"],
    }))
    out = tmp_path / "out"
    assert grid.run_grid(config, out) == 0
    spans = []
    slots = {}
    for name in "abcd":
        for seed in (1, 2):
            directory = out / "cells" / name / f"s{seed}-r0"
            meta = json.loads((directory / "cell.json").read_text(encoding="utf-8"))
            stamp = json.loads((directory / "stamp.json").read_text(encoding="utf-8"))
            slots[(name, seed)] = meta["slot"]
            spans.append((stamp["start"], stamp["end"]))
            assert meta["slot"] in (0, 1)
            if not hasattr(os, "sched_setaffinity"):
                assert meta["cpus"] is None
    assert _overlap(spans) == 2
    assert slots[("a", 1)] == 0 and slots[("b", 1)] == 1
    assert slots[("c", 1)] == 0 and slots[("d", 1)] == 0
    first = [json.loads((out / "cells" / name / "s1-r0" / "stamp.json").read_text(encoding="utf-8"))["start"] for name in "abcd"]
    second = [json.loads((out / "cells" / name / "s2-r0" / "stamp.json").read_text(encoding="utf-8"))["start"] for name in "abcd"]
    assert max(first) <= min(second)


def test_cpu_share_is_null_without_affinity_and_pinned_on_linux(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    def fake(arm, *, out, seed, rep):
        del arm, seed, rep
        return [sys.executable, "-c", _STAMP, str(out), "0.3", grid._THREADS_ENV]

    monkeypatch.setattr(grid, "command_for", fake)
    linux = hasattr(os, "sched_setaffinity") and hasattr(os, "sched_getaffinity")
    width = 2 if linux and len(os.sched_getaffinity(0)) >= 2 else 1
    config = grid.load_config(_write(tmp_path, {
        "schema": 1,
        "name": "cpus",
        "budget": {"minutes": 1},
        "seeds": [1],
        "concurrency": width,
        "cpus_per_cell": 1,
        "arms": [{"name": name, "kind": "surprise", "engines": ["duckdb"]} for name in "ab"[:width]],
    }))
    out = tmp_path / "out"
    assert grid.run_grid(config, out) == 0
    metas = []
    stamps = []
    for name in "ab"[:width]:
        directory = out / "cells" / name / "s1-r0"
        metas.append(json.loads((directory / "cell.json").read_text(encoding="utf-8")))
        stamps.append(json.loads((directory / "stamp.json").read_text(encoding="utf-8")))
    text = capsys.readouterr().out
    if linux:
        assert "sched_setaffinity is unavailable" not in text
        assert all(meta["cpus"] == stamp["affinity"] and len(meta["cpus"]) == 1 for meta, stamp in zip(metas, stamps))
        if width == 2:
            assert set(metas[0]["cpus"]).isdisjoint(metas[1]["cpus"])
    else:
        assert "sched_setaffinity is unavailable" in text
        assert all(meta["cpus"] is None for meta in metas)

    monkeypatch.setattr(os, "sched_getaffinity", lambda _pid: {0}, raising=False)
    monkeypatch.setattr(os, "sched_setaffinity", lambda _pid, _cpus: None, raising=False)
    tight = grid.load_config(_write(tmp_path, _base(concurrency=2, cpus_per_cell=1), "tight.json"))
    with pytest.raises(ValueError, match="cpus_per_cell"):
        grid.run_grid(tight, tmp_path / "tight")
    assert not (tmp_path / "tight" / "cells").exists()


def test_wall_clock_kill_marks_done_and_is_not_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    scripts = {"handles": _HANDLES, "ignores": _IGNORES, "quick": _QUICK}
    spawned: list[str] = []

    def fake(arm, *, out, seed, rep):
        del seed, rep
        spawned.append(arm["name"])
        return [sys.executable, "-c", scripts[arm["name"]], str(out)]

    monkeypatch.setattr(grid, "command_for", fake)
    monkeypatch.setattr(grid, "HARD_KILL_AFTER_S", 3.0)
    config = grid.load_config(_write(tmp_path, {
        "schema": 1,
        "name": "kill",
        "budget": {"minutes": 0.05},
        "seeds": [1],
        "concurrency": 3,
        "kill_grace_minutes": 0.05,
        "arms": [{"name": name, "kind": "surprise", "engines": ["duckdb"]} for name in ("handles", "ignores", "quick")],
    }))
    out = tmp_path / "out"
    assert grid.run_grid(config, out) == 0
    info = {
        name: json.loads((out / "cells" / name / "s1-r0" / "cell.json").read_text(encoding="utf-8"))
        for name in scripts
    }
    handles, ignores, quick = info["handles"], info["ignores"], info["quick"]
    assert handles["status"] == "done" and handles["killed"] is True and handles["hard_killed"] is False
    assert handles["returncode"] == 130
    assert 5.0 <= handles["wall_s"] <= 30.0
    assert abs(handles["deadline_s"] - 6.0) < 0.01
    report = json.loads((out / "cells" / "handles" / "s1-r0" / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "interrupted"
    assert ignores["status"] == "done" and ignores["killed"] is True and ignores["hard_killed"] is True
    assert 8.0 <= ignores["wall_s"] <= 45.0
    assert quick["status"] == "done" and quick["killed"] is False and quick["hard_killed"] is False
    assert quick["returncode"] == 0
    grandchild = int((out / "cells" / "ignores" / "s1-r0" / "grandchild.pid").read_text(encoding="utf-8"))
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and _alive(grandchild):
        time.sleep(0.2)
    assert not _alive(grandchild)
    assert grid.status_text(out).strip().split("\n") == [
        "handles/s1-r0 done (killed)",
        "ignores/s1-r0 done (killed)",
        "quick/s1-r0 done",
        "done 3/3",
    ]
    first = capsys.readouterr().out
    assert "handles/s1-r0 done (killed)" in first and "ignores/s1-r0 done (killed)" in first
    before = _files(out)
    spawned_before = len(spawned)
    assert grid.run_grid(config, out) == 0
    assert spawned == ["handles", "ignores", "quick"] and len(spawned) == spawned_before
    assert _files(out) == before
    second = capsys.readouterr().out
    assert "done (killed)" not in second
    assert "handles/s1-r0 done" in second and "ignores/s1-r0 done" in second


def test_price_table_matches_the_gate() -> None:
    path = REPO / cases.PRICES_FILE
    assert json.loads(path.read_text(encoding="utf-8")) == cases.PRICES


def test_engine_threads_preserve_the_inherited_setting_unless_overridden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake(arm, *, out, seed, rep):
        return [sys.executable, "-c", _STAMP, str(out), "0", grid._THREADS_ENV]

    monkeypatch.setattr(grid, "command_for", fake)
    monkeypatch.setenv(grid._THREADS_ENV, "7")
    config = grid.load_config(_write(tmp_path, _base()))
    out = tmp_path / "out"
    assert grid.run_grid(config, out) == 0
    stamp = json.loads((out / "cells/a/s1-r0/stamp.json").read_text(encoding="utf-8"))
    assert stamp["threads"] == "7"
    assert grid._child_env(False, 3)[grid._THREADS_ENV] == "3"
    assert os.environ[grid._THREADS_ENV] == "7"


@pytest.mark.parametrize("interrupted,hard_killed", [(False, False), (True, False), (True, True)])
def test_posix_exit_cleans_up_the_group_even_after_a_graceful_interrupt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interrupted: bool, hard_killed: bool,
) -> None:
    groups = []
    monkeypatch.setattr(grid, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(grid, "_kill_group", groups.append)
    proc = SimpleNamespace(pid=12345, poll=lambda: 130 if interrupted else 0,
                           returncode=130 if interrupted else 0)
    log = BytesIO()
    cell = grid._CellProc(proc, log, 0, {"name": "a", "kind": "surprise"}, 1, 0,
                          ["stand-in"], datetime.now(timezone.utc), time.monotonic(),
                          6.0, None, None, tmp_path / "cell")
    cell.interrupted = interrupted
    cell.hard_killed = hard_killed
    assert grid._finish(cell) == ("done (killed)" if interrupted else "done")
    assert groups == [proc.pid]
    assert log.closed


def test_posix_launch_creates_a_session_and_binds_in_the_child(monkeypatch: pytest.MonkeyPatch) -> None:
    bound = []
    monkeypatch.setattr(grid, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(os, "sched_setaffinity", lambda pid, cpus: bound.append((pid, cpus)), raising=False)
    kwargs = grid._popen_kwargs({}, None, [2, 4])
    assert kwargs["start_new_session"] is True
    assert "creationflags" not in kwargs
    assert bound == []
    kwargs["preexec_fn"]()
    assert bound == [(0, [2, 4])]
