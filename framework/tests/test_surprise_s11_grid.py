"""Config-driven grid, old CoevoDB modes, and the transcribed SQLancer summary."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from surprise.baselines import old_no_llm as baseline
from surprise.baselines import sqlancer
from surprise.experiments import grid
from surprise.harness.contracts import ORACLE_IDS

FRAMEWORK = Path(__file__).resolve().parents[1]
REPO = FRAMEWORK.parent


def _base() -> dict:
    return {
        "schema": 1,
        "name": "s11-smoke",
        "budget": {"minutes": 1},
        "seeds": [0],
        "arms": [{"name": "surprise", "kind": "surprise"}],
    }


def _apply(fn):
    def apply(body):
        fn(body)
        return body

    return apply


def _write(tmp_path: Path, body) -> Path:
    path = tmp_path / "grid.json"
    if isinstance(body, str):
        path.write_text(body, encoding="utf-8")
    else:
        path.write_text(json.dumps(body), encoding="utf-8")
    return path


def _load(tmp_path: Path, body) -> dict:
    return grid.load_config(_write(tmp_path, body))


def _script(code: int) -> str:
    return (
        "import json, os, pathlib, sys\n"
        "out = pathlib.Path(sys.argv[sys.argv.index('--out') + 1])\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "(out / 'marker.txt').write_text('ok', encoding='utf-8')\n"
        "flags = {'key': 'DEEPSEEK_API_KEY' in os.environ,"
        " 'cap': 'SURPRISE_LLM_MAX_CALLS' in os.environ}\n"
        "(out / 'env.json').write_text(json.dumps(flags), encoding='utf-8')\n"
        "sys.stdout.write('hello-cell\\n')\n"
        f"raise SystemExit({int(code)})\n"
    )


def _stand_in(order: list, code: int = 0):
    def fake(arm, *, out, seed, rep):
        order.append((rep, seed, arm["name"]))
        return [sys.executable, "-c", _script(code), "--out", str(out)]

    return fake


def _files(root: Path) -> dict[str, tuple[bytes, int]]:
    found = {}
    if not root.exists():
        return found
    for path in sorted(root.rglob("*")):
        if path.is_file():
            found[path.relative_to(root).as_posix()] = (path.read_bytes(), path.stat().st_mtime_ns)
    return found


_ERRORS = [
    ("not-json", lambda _b: "not-json", "not JSON"),
    ("not-object", lambda _b: [1], "object"),
    ("schema", _apply(lambda b: b.update(schema=2)), "schema"),
    ("schema-bool", _apply(lambda b: b.update(schema=True)), "schema"),
    ("missing-name", _apply(lambda b: b.pop("name")), "missing"),
    ("bad-name", _apply(lambda b: b.update(name="S11")), "name"),
    ("empty-name", _apply(lambda b: b.update(name="")), "name"),
    ("budget-both", _apply(lambda b: b.update(budget={"minutes": 1, "experiments": 2})), "budget"),
    ("budget-empty", _apply(lambda b: b.update(budget={})), "budget"),
    ("budget-minutes-zero", _apply(lambda b: b.update(budget={"minutes": 0})), "minutes"),
    ("budget-minutes-bool", _apply(lambda b: b.update(budget={"minutes": True})), "minutes"),
    ("budget-minutes-string", _apply(lambda b: b.update(budget={"minutes": "1"})), "minutes"),
    ("budget-experiments-zero", _apply(lambda b: b.update(budget={"experiments": 0})), "experiments"),
    ("budget-experiments-float", _apply(lambda b: b.update(budget={"experiments": 1.5})), "experiments"),
    ("budget-experiments-bool", _apply(lambda b: b.update(budget={"experiments": True})), "experiments"),
    ("seeds-empty", _apply(lambda b: b.update(seeds=[])), "seeds"),
    ("seeds-string", _apply(lambda b: b.update(seeds="0")), "seeds"),
    ("seeds-bool", _apply(lambda b: b.update(seeds=[True])), "seeds"),
    ("seeds-duplicate", _apply(lambda b: b.update(seeds=[0, 0])), "duplicate"),
    ("repeats-zero", _apply(lambda b: b.update(repeats=0)), "repeats"),
    ("repeats-bool", _apply(lambda b: b.update(repeats=True)), "repeats"),
    ("reference", _apply(lambda b: b.update(reference="nope")), "reference"),
    ("window-zero", _apply(lambda b: b.update(window=0)), "window"),
    ("window-float", _apply(lambda b: b.update(window=1.5)), "window"),
    ("known-number", _apply(lambda b: b.update(known=1)), "known"),
    ("known-empty", _apply(lambda b: b.update(known="")), "known"),
    ("prices-list", _apply(lambda b: b.update(prices=[])), "prices"),
    ("prices-string", _apply(lambda b: b.update(prices="x")), "prices"),
    ("arms-empty", _apply(lambda b: b.update(arms=[])), "arms"),
    ("arms-object", _apply(lambda b: b.update(arms={})), "arms"),
    ("arm-not-object", _apply(lambda b: b.update(arms=[1])), "object"),
    ("kind", _apply(lambda b: b["arms"][0].update(kind="nope")), "kind"),
    ("arm-name", _apply(lambda b: b["arms"][0].update(name="Surprise")), "name"),
    (
        "duplicate-arm",
        _apply(lambda b: b.update(arms=[
            {"name": "a", "kind": "surprise"},
            {"name": "a", "kind": "surprise"},
        ])),
        "duplicate",
    ),
    ("unknown-top", _apply(lambda b: b.update(extra=1)), "unknown"),
    ("unknown-arm", _apply(lambda b: b["arms"][0].update(extra=1)), "unknown"),
    ("engine", _apply(lambda b: b["arms"][0].update(engines=["sqlite"])), "engines"),
    ("duplicate-engine", _apply(lambda b: b["arms"][0].update(engines=["duckdb", "duckdb"])), "duplicate"),
    ("oracle", _apply(lambda b: b["arms"][0].update(oracles=["nope"])), "oracles"),
    ("oracles-empty", _apply(lambda b: b["arms"][0].update(oracles=[])), "oracles"),
    ("bootstrap-string", _apply(lambda b: b["arms"][0].update(bootstrap="x")), "bootstrap"),
    (
        "bootstrap-keys",
        _apply(lambda b: b["arms"][0].update(bootstrap=[{"case": {}, "oracle": "tlp"}])),
        "bootstrap",
    ),
    (
        "bootstrap-case",
        _apply(lambda b: b["arms"][0].update(bootstrap=[{"case": {}, "oracle": "tlp", "rule": None}])),
        "SqlCase",
    ),
    (
        "bootstrap-oracle",
        _apply(lambda b: b["arms"][0].update(bootstrap=[{
            "case": {"engine": "duckdb", "setup": [], "query": "select 1"},
            "oracle": "nope",
            "rule": None,
        }])),
        "oracle",
    ),
    (
        "bootstrap-rule",
        _apply(lambda b: b["arms"][0].update(bootstrap=[{
            "case": {"engine": "duckdb", "setup": [], "query": "select 1"},
            "oracle": "tlp",
            "rule": "",
        }])),
        "rule",
    ),
    ("freeze", _apply(lambda b: b["arms"][0].update(freeze="everything")), "freeze"),
    ("hunter", _apply(lambda b: b["arms"][0].update(hunter="greedy")), "hunter"),
    ("theory-from", _apply(lambda b: b["arms"][0].update(theory_from="nowhere")), "theory_from"),
    ("theory-from-empty-run", _apply(lambda b: b["arms"][0].update(theory_from="@head")), "theory_from"),
    ("theory-from-empty-gen", _apply(lambda b: b["arms"][0].update(theory_from="run@")), "theory_from"),
    ("select-from", _apply(lambda b: b["arms"][0].update(select_from="no-at")), "select_from"),
    ("vocabulary-empty", _apply(lambda b: b["arms"][0].update(vocabulary="")), "vocabulary"),
    ("vocabulary-missing", _apply(lambda b: b["arms"][0].update(vocabulary="Z:/no/such-vocab.json")), "vocabulary"),
    ("beta-zero", _apply(lambda b: b["arms"][0].update(beta=0)), "beta"),
    ("beta-bool", _apply(lambda b: b["arms"][0].update(beta=True)), "beta"),
    ("llm-string", _apply(lambda b: b["arms"][0].update(llm="on")), "llm"),
    ("llm-roles-empty", _apply(lambda b: b["arms"][0].update(llm={"roles": [], "cache": "c", "max_calls": 1})), "roles"),
    (
        "llm-role",
        _apply(lambda b: b["arms"][0].update(llm={"roles": ["wizard"], "cache": "c", "max_calls": 1})),
        "roles",
    ),
    (
        "llm-duplicate-role",
        _apply(lambda b: b["arms"][0].update(
            llm={"roles": ["implementer", "implementer"], "cache": "c", "max_calls": 1}
        )),
        "duplicate",
    ),
    (
        "llm-max-calls",
        _apply(lambda b: b["arms"][0].update(llm={"roles": ["implementer"], "cache": "c"})),
        "max_calls",
    ),
    (
        "llm-max-calls-negative",
        _apply(lambda b: b["arms"][0].update(llm={"roles": ["implementer"], "cache": "c", "max_calls": -1})),
        "max_calls",
    ),
    (
        "llm-max-calls-bool",
        _apply(lambda b: b["arms"][0].update(llm={"roles": ["implementer"], "cache": "c", "max_calls": True})),
        "max_calls",
    ),
    (
        "llm-offline",
        _apply(lambda b: b["arms"][0].update(
            llm={"roles": ["implementer"], "cache": "c", "max_calls": 1, "offline": "yes"}
        )),
        "offline",
    ),
    (
        "llm-cache",
        _apply(lambda b: b["arms"][0].update(llm={"roles": ["implementer"], "cache": "", "max_calls": 1})),
        "cache",
    ),
    (
        "llm-unknown",
        _apply(lambda b: b["arms"][0].update(
            llm={"roles": ["implementer"], "cache": "c", "max_calls": 1, "transport": "x"}
        )),
        "unknown",
    ),
    (
        "freeze-role",
        _apply(lambda b: b["arms"][0].update(
            freeze="theory",
            llm={"roles": ["conjecturer"], "cache": "c", "max_calls": 1, "offline": True},
        )),
        "freeze",
    ),
    ("python", _apply(lambda b: b["arms"][0].update(python="")), "python"),
    (
        "old-mode",
        _apply(lambda b: b.update(arms=[{"name": "old", "kind": "old_coevodb", "mode": "nope"}])),
        "mode",
    ),
    (
        "old-experiments",
        _apply(lambda b: b.update(budget={"experiments": 3}, arms=[{"name": "old", "kind": "old_coevodb"}])),
        "minutes",
    ),
    (
        "old-arm-experiments",
        _apply(lambda b: b.update(arms=[{
            "name": "old", "kind": "old_coevodb", "budget": {"experiments": 2},
        }])),
        "minutes",
    ),
    (
        "pure-needs-cap",
        _apply(lambda b: b.update(arms=[{"name": "pure", "kind": "pure_llm"}])),
        "max_calls",
    ),
    (
        "pure-online",
        _apply(lambda b: b.update(arms=[{"name": "pure", "kind": "pure_llm", "llm": {"offline": False}}])),
        "max_calls",
    ),
    (
        "pure-engine",
        _apply(lambda b: b.update(arms=[{
            "name": "pure", "kind": "pure_llm", "engine": "sqlite", "llm": {"offline": True},
        }])),
        "engine",
    ),
    (
        "pure-unknown",
        _apply(lambda b: b.update(arms=[{
            "name": "pure", "kind": "pure_llm", "llm": {"offline": True, "roles": ["implementer"]},
        }])),
        "unknown",
    ),
    (
        "sqlancer-engine",
        _apply(lambda b: b.update(arms=[{"name": "q", "kind": "sqlancer", "engine": "mysql"}])),
        "engine",
    ),
    (
        "sqlancer-budget",
        _apply(lambda b: b.update(arms=[{
            "name": "q", "kind": "sqlancer", "budget": {"minutes": 1},
        }])),
        "unknown",
    ),
    (
        "sqlancer-summary",
        _apply(lambda b: b.update(arms=[{
            "name": "q", "kind": "sqlancer", "summary": "Z:/no/such-summary.json",
        }])),
        "summary",
    ),
    ("network", _apply(lambda b: b["arms"][0].update(network=True)), "network"),
    ("missing-schema", _apply(lambda b: b.pop("schema")), "missing"),
]


@pytest.mark.parametrize("label,mutate,match", _ERRORS, ids=[item[0] for item in _ERRORS])
def test_config_rejects(tmp_path: Path, label: str, mutate, match: str) -> None:
    del label
    with pytest.raises(ValueError, match=match):
        _load(tmp_path, mutate(_base()))


def test_missing_config_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="config"):
        grid.load_config(tmp_path / "missing.json")


def test_defaults_round_trip_and_network(tmp_path: Path) -> None:
    vocab = tmp_path / "vocab.json"
    vocab.write_text("{}", encoding="utf-8")
    prices = {"deepseek-flash": {"input": 0.1, "output": 0.2}}
    case = {
        "case": {"engine": "duckdb", "setup": ["CREATE TABLE t(a INT)"], "query": "SELECT 1"},
        "oracle": "tlp",
        "rule": None,
    }
    body = {
        "schema": 1,
        "name": "s11-smoke",
        "budget": {"experiments": 4},
        "seeds": [0, -1],
        "arms": [
            {
                "name": "surprise",
                "kind": "surprise",
                "engines": ["datafusion", "duckdb"],
                "oracles": ["tlp", "norec"],
                "bootstrap": [case],
                "freeze": "diagnoser",
                "hunter": "random",
                "theory_from": "runs/base@head",
                "select_from": "runs/base@3",
                "vocabulary": str(vocab),
                "beta": 1,
                "llm": {
                    "roles": ["implementer", "prior"],
                    "cache": "llm-cache",
                    "max_calls": 2,
                    "offline": True,
                },
                "python": sys.executable,
            },
            {"name": "old", "kind": "old_coevodb", "mode": "full", "budget": {"minutes": 2}},
            {"name": "pure", "kind": "pure_llm", "llm": {"offline": True}},
            {"name": "q", "kind": "sqlancer", "engine": "sqlite3"},
        ],
        "known": None,
        "prices": prices,
    }
    config = _load(tmp_path, body)
    bare = _load(tmp_path, _base())
    assert bare["repeats"] == 1 and bare["reference"] == "surprise" and bare["window"] == 10
    assert bare["known"] is None and bare["prices"] is None
    assert bare["arms"][0]["engines"] == ["duckdb"]
    assert bare["arms"][0]["oracles"] == list(ORACLE_IDS)
    assert bare["arms"][0]["network"] is False and bare["arms"][0]["llm"] is None
    assert bare["budget"] == {"minutes": 1.0}
    assert config["reference"] == "surprise" and config["seeds"] == [0, -1]
    assert config["prices"] == prices
    surprise = config["arms"][0]
    assert surprise["network"] is False and surprise["beta"] == 1.0
    assert surprise["bootstrap"][0]["case"]["predicate"] is None
    assert surprise["bootstrap"][0]["case"]["query"] == "SELECT 1"
    assert config["arms"][1]["network"] is True and config["arms"][1]["budget"] == {"minutes": 2.0}
    assert config["arms"][1]["mode"] == "full"
    assert config["arms"][2]["network"] is False and config["arms"][2]["llm"]["offline"] is True
    assert config["arms"][2]["engine"] == "duckdb"
    assert config["arms"][3]["network"] is False and config["arms"][3]["engine"] == "sqlite3"
    assert config["arms"][3]["summary"] == str(sqlancer.SUMMARY_PATH)
    again = tmp_path / "norm.json"
    again.write_text(json.dumps(config), encoding="utf-8")
    assert grid.load_config(again) == config

    brief = {
        "schema": 1,
        "name": "s11-smoke",
        "budget": {"minutes": 1.0},
        "seeds": [0, 1],
        "repeats": 1,
        "reference": "surprise",
        "window": 10,
        "known": None,
        "prices": None,
        "arms": [
            {"name": "surprise", "kind": "surprise", "engines": ["duckdb"]},
            {"name": "old", "kind": "old_coevodb", "mode": "no_llm"},
        ],
    }
    gate = dict(brief)
    gate.pop("known")
    gate.pop("prices")
    assert _load(tmp_path, brief) == _load(tmp_path, gate)
    online = _load(tmp_path, {
        "schema": 1,
        "name": "net",
        "budget": {"minutes": 1},
        "seeds": [0],
        "arms": [{
            "name": "pure",
            "kind": "pure_llm",
            "llm": {"max_calls": 3, "cache": "c"},
        }],
    })
    assert online["arms"][0]["network"] is True and online["arms"][0]["llm"]["offline"] is False


def test_commands_translate_the_arm(tmp_path: Path) -> None:
    vocab = tmp_path / "vocab.json"
    vocab.write_text("{}", encoding="utf-8")
    cell = tmp_path / "cells" / "surprise" / "s0-r0"
    config = _load(tmp_path, {
        "schema": 1,
        "name": "cmds",
        "budget": {"experiments": 3},
        "seeds": [0],
        "arms": [
            {
                "name": "surprise",
                "kind": "surprise",
                "budget": {"minutes": 1.5},
                "engines": ["duckdb"],
                "oracles": ["tlp"],
                "bootstrap": [{
                    "case": {"engine": "duckdb", "setup": [], "query": "SELECT 1"},
                    "oracle": "tlp",
                    "rule": "r",
                }],
                "freeze": "theory",
                "hunter": "random",
                "theory_from": "runs/base@head",
                "select_from": "runs/other@3",
                "vocabulary": str(vocab),
                "beta": 0.5,
                "llm": {
                    "roles": ["prior", "implementer"],
                    "cache": "cache-dir",
                    "max_calls": 4,
                    "offline": True,
                },
                "python": sys.executable,
            },
            {"name": "old", "kind": "old_coevodb", "budget": {"minutes": 2.5}},
            {
                "name": "pure",
                "kind": "pure_llm",
                "engine": "datafusion",
                "oracles": ["norec"],
                "llm": {"offline": True, "cache": "pure-cache"},
                "budget": {"experiments": 2},
            },
        ],
    })
    surprise, old, pure = config["arms"]
    argv = grid.command_for(surprise, out=cell, seed=0, rep=1)
    boot = cell.parent / "s0-r0.bootstrap.json"
    assert argv == [
        sys.executable, "-m", "surprise.experiments.loop",
        "--out", str(cell), "--seed", "0", "--max-minutes", "1.5",
        "--engine", "duckdb", "--oracle", "tlp",
        "--bootstrap", str(boot),
        "--vocabulary", str(vocab),
        "--beta", "0.5",
        "--freeze", "theory",
        "--hunter", "random",
        "--theory-from", "runs/base@head",
        "--select-from", "runs/other@3",
        "--llm", "prior", "--llm", "implementer",
        "--llm-cache", "cache-dir",
        "--llm-max-calls", "4",
        "--llm-offline",
    ]
    assert boot.parent == cell.parent and boot != cell / "bootstrap.json"
    assert grid.command_for(surprise, out=cell, seed=0, rep=0) == argv
    old_argv = grid.command_for(old, out=tmp_path / "cells" / "old" / "s0-r0", seed=7, rep=0)
    assert old_argv == [
        sys.executable, "-m", "surprise.baselines.old_no_llm",
        "--out", str(tmp_path / "cells" / "old" / "s0-r0"),
        "--minutes", "2.5", "--seed", "7", "--mode", "no_llm",
    ]
    assert "--python" not in old_argv
    pure_argv = grid.command_for(pure, out=tmp_path / "cells" / "pure" / "s0-r0", seed=-1, rep=0)
    assert pure_argv == [
        sys.executable, "-m", "surprise.baselines.pure_llm",
        "--out", str(tmp_path / "cells" / "pure" / "s0-r0"),
        "--seed", "-1", "--engine", "datafusion", "--oracle", "norec",
        "--max-experiments", "2",
        "--llm-cache", "pure-cache",
        "--llm-offline",
    ]
    assert "--llm-max-calls" not in pure_argv


def test_grid_layout_order_keys_and_bootstrap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    token = "token-" + "z" * 12
    monkeypatch.setenv("DEEPSEEK_API_KEY", token)
    monkeypatch.setenv("SURPRISE_LLM_MAX_CALLS", "9")
    order: list = []
    monkeypatch.setattr(grid, "command_for", _stand_in(order))
    config = _load(tmp_path, {
        "schema": 1,
        "name": "layout",
        "budget": {"minutes": 1},
        "seeds": [0, 1],
        "repeats": 2,
        "arms": [
            {"name": "b", "kind": "old_coevodb"},
            {
                "name": "a",
                "kind": "surprise",
                "bootstrap": [{
                    "case": {"engine": "duckdb", "setup": [], "query": "SELECT 1"},
                    "oracle": "tlp",
                    "rule": None,
                }],
                "llm": {"roles": ["implementer"], "cache": "c", "max_calls": 1, "offline": False},
            },
            {"name": "q", "kind": "sqlancer"},
        ],
    })
    out = tmp_path / "out"
    assert grid.run_grid(config, out) == 0
    assert order == [
        (0, 0, "b"), (0, 0, "a"),
        (0, 1, "b"), (0, 1, "a"),
        (1, 0, "b"), (1, 0, "a"),
        (1, 1, "b"), (1, 1, "a"),
    ]
    assert not (out / "cells" / "q").exists()
    cell = out / "cells" / "a" / "s0-r0"
    meta = json.loads((cell / "cell.json").read_text(encoding="utf-8"))
    assert meta["status"] == "done" and meta["arm"] == "a" and meta["kind"] == "surprise"
    assert meta["seed"] == 0 and meta["rep"] == 0 and meta["returncode"] == 0
    assert meta["command"][0] == sys.executable
    assert "hello-cell" in (out / "cells" / "a" / "s0-r0.log").read_text(encoding="utf-8")
    boot = json.loads((out / "cells" / "a" / "s0-r0.bootstrap.json").read_text(encoding="utf-8"))
    assert boot[0]["oracle"] == "tlp" and not (cell / "s0-r0.bootstrap.json").exists()
    online = json.loads((cell / "env.json").read_text(encoding="utf-8"))
    offline = json.loads((out / "cells" / "b" / "s0-r0" / "env.json").read_text(encoding="utf-8"))
    assert online == {"key": True, "cap": True}
    assert offline == {"key": False, "cap": False}
    blob = b"".join(path.read_bytes() for path in out.rglob("*") if path.is_file())
    assert token.encode("ascii") not in blob
    saved = json.loads((out / "grid.json").read_text(encoding="utf-8"))
    assert saved == config


def test_done_cells_are_not_touched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    order: list = []
    monkeypatch.setattr(grid, "command_for", _stand_in(order))
    config = _load(tmp_path, _base())
    out = tmp_path / "out"
    assert grid.run_grid(config, out) == 0
    before = _files(out)

    def boom(*_args, **_kwargs):
        raise AssertionError("ran a done cell")

    monkeypatch.setattr(grid, "command_for", boom)
    assert grid.run_grid(config, out) == 0
    assert _files(out) == before


def test_incomplete_cells_are_renamed_and_rerun(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = {"n": 0}

    def fake(arm, *, out, seed, rep):
        del arm, seed, rep
        state["n"] += 1
        return [sys.executable, "-c", _script(0 if state["n"] >= 3 else 1), "--out", str(out)]

    monkeypatch.setattr(grid, "command_for", fake)
    config = _load(tmp_path, _base())
    out = tmp_path / "out"
    assert grid.run_grid(config, out) == 1
    assert grid.run_grid(config, out) == 1
    assert grid.run_grid(config, out) == 0
    root = out / "cells" / "surprise"
    assert json.loads((root / "s0-r0.stale-1" / "cell.json").read_text(encoding="utf-8"))["status"] == "failed"
    assert json.loads((root / "s0-r0.stale-2" / "cell.json").read_text(encoding="utf-8"))["status"] == "failed"
    assert json.loads((root / "s0-r0" / "cell.json").read_text(encoding="utf-8"))["status"] == "done"
    junk_root = tmp_path / "partial"
    partial = junk_root / "cells" / "surprise" / "s0-r0"
    partial.mkdir(parents=True)
    (partial / "junk.txt").write_text("keep", encoding="utf-8")
    (junk_root / "grid.json").write_text(json.dumps(config), encoding="utf-8")
    state["n"] = 3
    assert grid.run_grid(config, junk_root) == 0
    assert (junk_root / "cells" / "surprise" / "s0-r0.stale-1" / "junk.txt").read_text(encoding="utf-8") == "keep"
    assert json.loads((junk_root / "cells" / "surprise" / "s0-r0" / "cell.json").read_text(encoding="utf-8"))["status"] == "done"


def test_status_only_and_config_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    order: list = []
    monkeypatch.setattr(grid, "command_for", _stand_in(order))
    config = _load(tmp_path, {
        "schema": 1,
        "name": "only",
        "budget": {"minutes": 1},
        "seeds": [0, 1],
        "arms": [
            {"name": "surprise", "kind": "surprise"},
            {"name": "old", "kind": "old_coevodb"},
        ],
    })
    out = tmp_path / "out"
    assert grid.run_grid(config, out, only=["surprise"]) == 0
    assert order == [(0, 0, "surprise"), (0, 1, "surprise")]
    text = grid.status_text(out)
    assert text == "surprise/s0-r0 done\nold/s0-r0 missing\nsurprise/s1-r0 done\nold/s1-r0 missing\ndone 2/4\n"
    assert grid.main(["status", str(out)]) == 0
    proc = subprocess.run(
        [sys.executable, "-m", "surprise.experiments.grid", "status", str(out)],
        cwd=FRAMEWORK, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0 and "done 2/4" in proc.stdout
    before = _files(out)
    changed = json.loads(json.dumps(config))
    changed["seeds"] = [0]
    with pytest.raises(ValueError, match="grid.json"):
        grid.run_grid(changed, out)
    assert _files(out) == before
    with pytest.raises(ValueError, match="only"):
        grid.run_grid(config, out, only=["nope"])
    assert grid.main(["run", str(_write(tmp_path, {"schema": 2})), "--out", str(tmp_path / "bad")]) == 2


def test_sqlancer_arm_has_no_cells(tmp_path: Path) -> None:
    config = _load(tmp_path, {
        "schema": 1,
        "name": "q",
        "budget": {"minutes": 1},
        "seeds": [0, 1],
        "repeats": 3,
        "arms": [{"name": "q", "kind": "sqlancer"}],
    })
    out = tmp_path / "out"
    assert grid.run_grid(config, out) == 0
    assert grid.status_text(out) == "done 0/0\n"
    assert not (out / "cells").exists()


def test_role_names_match_the_runtime() -> None:
    from surprise.roles.runtime import ROLES

    assert grid._LLM_ROLES == ROLES


def test_no_llm_command_is_unchanged(tmp_path: Path) -> None:
    out = tmp_path / "old"
    argv = baseline.command(out, seed=3, python=None)
    assert argv == [
        sys.executable,
        str(baseline.FRAMEWORK / "main.py"),
        "--engine",
        "duckdb",
        "--mode",
        "no_llm",
        "--iterations",
        "100000000",
        "--stagnation-limit",
        "100000000",
        "--seed",
        "3",
        "--results-root",
        str(out / "results"),
        "--label",
        "s08_old_s3",
    ]
    assert baseline.command(out, seed=3, python=None, mode="no_llm") == argv
    assert baseline.command(out, seed=3, python="C:/Interpreter/python.exe")[0] == "C:/Interpreter/python.exe"
    other = baseline.command(out, seed=3, python=None, mode="coverage_only")
    assert other[other.index("--mode") + 1] == "coverage_only"
    assert other[-1] == "s11_old_coverage_only_s3"
    assert [part for part in other if part not in ("coverage_only", "s11_old_coverage_only_s3")] == [
        part for part in argv if part not in ("no_llm", "s08_old_s3")
    ]
    with pytest.raises(ValueError, match="mode"):
        baseline.command(out, seed=0, python=None, mode="nope")
    text = (FRAMEWORK / "surprise" / "baselines" / "coevodb_v1" / "main.py").read_text(encoding="utf-8")
    start = text.index('["full", "random_category", "no_llm"')
    end = text.index("]", start) + 1
    assert json.loads(text[start:end]) == list(baseline.OLD_MODES)


OLD_SCRIPT = """
import json, os, pathlib, sys
out = pathlib.Path(sys.argv[1])
run = out / "results" / "only"
run.mkdir(parents=True)
(run / "bugs.jsonl").write_text("", encoding="utf-8")
(out / "env.json").write_text(json.dumps({"key": "DEEPSEEK_API_KEY" in os.environ}), encoding="utf-8")
raise SystemExit(0)
"""


def test_no_llm_run_keeps_the_old_command_signature(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    token = "token-" + "q" * 12
    monkeypatch.setenv("DEEPSEEK_API_KEY", token)

    def fake(out, *, seed, python):
        assert seed == 3 and python is None
        return [sys.executable, "-c", OLD_SCRIPT, str(out)]

    monkeypatch.setattr(baseline, "command", fake)
    found = baseline.run(tmp_path / "old", minutes=1, seed=3, mode="no_llm")
    assert found["mode"] == "no_llm" and found["ended"] == "exited" and found["returncode"] == 0
    env = json.loads((tmp_path / "old" / "env.json").read_text(encoding="utf-8"))
    assert env == {"key": False}
    stored = (tmp_path / "old" / "old_run.json").read_text(encoding="utf-8")
    assert token not in stored and token not in (tmp_path / "old" / "console.txt").read_text(encoding="utf-8")
    code = baseline.main(["--out", str(tmp_path / "cli"), "--minutes", "1", "--seed", "3", "--mode", "no_llm"])
    assert code == 0
    assert json.loads((tmp_path / "cli" / "old_run.json").read_text(encoding="utf-8"))["mode"] == "no_llm"


def test_other_mode_keeps_the_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                      capsys: pytest.CaptureFixture[str]) -> None:
    token = "token-" + "q" * 12
    monkeypatch.setenv("DEEPSEEK_API_KEY", token)

    def fake(out, *, seed, python, mode="no_llm"):
        assert mode == "coverage_only" and python is None and seed == 5
        return [sys.executable, "-c", OLD_SCRIPT, str(out)]

    monkeypatch.setattr(baseline, "command", fake)
    found = baseline.run(tmp_path / "old", minutes=1, seed=5, mode="coverage_only")
    assert found["mode"] == "coverage_only"
    assert json.loads((tmp_path / "old" / "env.json").read_text(encoding="utf-8")) == {"key": True}
    blob = (tmp_path / "old" / "old_run.json").read_text(encoding="utf-8")
    assert token not in blob
    code = baseline.main(["--out", str(tmp_path / "nope"), "--minutes", "1", "--seed", "1", "--mode", "nope"])
    assert code == 2
    assert "mode" in capsys.readouterr().err
    assert not (tmp_path / "nope").exists()


def test_sqlancer_transcript_matches_the_report() -> None:
    summary = sqlancer.load()
    assert sqlancer.load(sqlancer.SUMMARY_PATH) == summary
    text = (REPO / "docs" / "FINAL_REPORT.md").read_text(encoding="utf-8")
    assert summary["tool"] == "SQLancer 2.0.0 @9eb1db82"
    assert summary["runs"] == 35 and summary["total_bugs"] == 0 and summary["total_checks"] == 90300000
    assert summary["transcribed"] is True and summary["approximate_checks"] is True
    assert "docs/FINAL_REPORT.md" in summary["source"]
    rows = (
        ("duckdb", "1.5.5", 6, 7300000, 0),
        ("postgres", "16.2", 5, 10100000, 0),
        ("sqlite3", "3.49.1", 5, 72900000, 0),
    )
    for engine, version, oracles, checks, bugs in rows:
        row = summary["engines"][engine]
        assert row == {"version": version, "oracles": oracles, "checks": checks, "bugs": bugs}
        prefix = "v" if engine == "duckdb" else ""
        line = f"| {engine} {prefix}{version} | \u2014 | {oracles} | ~{checks / 1e6:.1f}M | {bugs} |"
        assert line in text
    got = sqlancer.metrics(summary)
    assert got == {
        "kind": "sqlancer",
        "engine": "duckdb",
        "version": "1.5.5",
        "checks": 7300000,
        "family_count": 0,
        "families_per_1000": 0.0,
        "transcribed": True,
    }
    postgres = sqlancer.metrics(summary, engine="postgres")
    assert postgres["checks"] == 10100000 and postgres["version"] == "16.2" and postgres["family_count"] == 0
    tweaked = json.loads(json.dumps(summary))
    tweaked["engines"]["duckdb"]["bugs"] = 2
    tweaked["engines"]["duckdb"]["checks"] = 500
    rated = sqlancer.metrics(tweaked)
    assert rated["family_count"] == 2 and rated["families_per_1000"] == 4.0
    with pytest.raises(ValueError, match="engine"):
        sqlancer.metrics(summary, engine="mysql")


def test_sqlancer_load_rejects_a_bad_file(tmp_path: Path) -> None:
    good = json.loads(sqlancer.SUMMARY_PATH.read_text(encoding="utf-8"))
    bad = json.loads(json.dumps(good))
    bad["transcribed"] = False
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="transcribed"):
        sqlancer.load(path)
    bad = json.loads(json.dumps(good))
    bad["total_checks"] = 1
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="total_checks"):
        sqlancer.load(path)
    bad = json.loads(json.dumps(good))
    bad["extra"] = 1
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown"):
        sqlancer.load(path)
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="object"):
        sqlancer.load(path)
    with pytest.raises(ValueError, match="summary"):
        sqlancer.load(tmp_path / "missing.json")


def test_hunter_value_matches_the_omitted_hunter(tmp_path: Path) -> None:
    bare = _load(tmp_path, _base())
    explicit = _load(tmp_path, {
        "schema": 1,
        "name": "s11-smoke",
        "budget": {"minutes": 1},
        "seeds": [0],
        "arms": [{"name": "surprise", "kind": "surprise", "hunter": "value"}],
    })
    assert explicit == bare
    assert explicit["arms"][0]["hunter"] is None
    cell = tmp_path / "cells" / "surprise" / "s0-r0"
    argv = grid.command_for(explicit["arms"][0], out=cell, seed=0, rep=0)
    assert "--hunter" not in argv
    random_arm = _load(tmp_path, {
        "schema": 1,
        "name": "s11-smoke",
        "budget": {"minutes": 1},
        "seeds": [0],
        "arms": [{"name": "surprise", "kind": "surprise", "hunter": "random"}],
    })["arms"][0]
    random_argv = grid.command_for(random_arm, out=cell, seed=0, rep=0)
    assert random_argv[random_argv.index("--hunter") + 1] == "random"
