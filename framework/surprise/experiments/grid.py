"""Configuration-driven experiment grid: arm x seed x budget x repeat.

One cell is one child process. Cells that share a repeat, a seed and an
engine set form a block, and up to ``concurrency`` cells run at once, started
in block order. A minute budget plus ``kill_grace_minutes`` is a wall-clock
deadline: the child is interrupted, then its process tree is killed if it
stays up. A cell whose ``cell.json`` says ``done`` is left untouched,
including one that was killed. Anything else already in that directory is
renamed to ``<cell>.stale-<k>`` and the cell runs again.

    python -m surprise.experiments.grid run CONFIG --out DIR [--only ARM]...
    python -m surprise.experiments.grid status DIR

``status`` prints one line per cell and a summary ``done X/Y``. Exit 0 from
``run`` means every selected cell is done. A failed cell does not stop the
others; ``run`` then exits 1.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import signal
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from surprise.baselines import sqlancer
from surprise.baselines.old_no_llm import OLD_MODES
from surprise.harness.contracts import ORACLE_IDS, SqlCase
from surprise.harness.oracles.registry import TARGET_ENGINES

FRAMEWORK = Path(__file__).resolve().parents[2]

# Same names as surprise.roles.runtime.ROLES. Hardcoded so importing the grid
# does not import the role stack.
_LLM_ROLES = (
    "implementer",
    "conjecturer",
    "prior",
    "translator",
    "vocab_inventor",
    "oracle_inventor",
)
_FREEZE_OK = ("theory", "diagnoser")
_HUNTER_OK = ("value", "random")
# Roles that do not edit the theory. A frozen arm may turn only these on.
_FROZEN_ROLES = ("implementer", "prior")
_NAME = re.compile(r"[a-z0-9_-]+")
_TIERS = ("fast", "strong", "glm-flash")
_UNLIMITED = "unlimited"
# Engines a running SQLancer arm may name. S16–S18 extend this.
_SQLANCER_RUN_ENGINES = ("duckdb", "postgres")
_SQLANCER_ORACLES = ("NOREC", "WHERE")
# DuckDB 1.5.5 on Linux reads this as its default thread count
# (.src/duckdb-v1.5.5/src/main/config.cpp, DBConfig::GetSystemMaxThreads).
_THREADS_ENV = "SLURM_CPUS_ON_NODE"
# Seconds after the interrupt before the whole process tree is killed.
# Read on each check so a test can patch it for one run.
HARD_KILL_AFTER_S = 120.0
_POLL_S = 0.05
_TOP_KEYS = {
    "schema",
    "name",
    "budget",
    "seeds",
    "repeats",
    "reference",
    "window",
    "known",
    "prices",
    "concurrency",
    "cpus_per_cell",
    "engine_threads",
    "kill_grace_minutes",
    "arms",
}
_ARM_KEYS = {
    "surprise": {
        "name",
        "kind",
        "budget",
        "engines",
        "oracles",
        "bootstrap",
        "freeze",
        "hunter",
        "theory_from",
        "select_from",
        "vocabulary",
        "beta",
        "llm",
        "tier",
        "python",
        "network",
    },
    "old_coevodb": {"name", "kind", "budget", "mode", "python", "network"},
    "pure_llm": {"name", "kind", "budget", "engine", "oracles", "llm", "tier", "python", "network"},
    "sqlancer": {"name", "kind", "summary", "engine", "network", "run", "budget"},
}
# Dropped from every child that does not need the network.
_SECRET_ENV = {"DEEPSEEK_API_KEY", "SURPRISE_LLM_MAX_CALLS"}


def load_config(path: str | Path) -> dict[str, Any]:
    """Read a grid config, check it, and fill defaults. Unqualified input raises ``ValueError``."""
    file = Path(path)
    if not file.is_file():
        raise ValueError(f"config: file does not exist: {file}")
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"config: not JSON: {file}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"config: expected an object, got {type(raw).__name__}")
    return _normalise(raw)


def run_grid(config: Mapping[str, Any], out: str | Path, *, only: Sequence[str] | None = None) -> int:
    """Run the selected cells under ``out``. Return 0 when all of them are done, else 1.

    ``config`` is the dict :func:`load_config` returned. The first run writes
    ``out/grid.json``. A later run whose config differs raises ``ValueError``
    and does not touch a cell.
    """
    if not isinstance(config, Mapping) or config.get("schema") != 1 or "arms" not in config:
        raise ValueError("config: expected the dict returned by load_config")
    destination = Path(out)
    if destination.exists() and not destination.is_dir():
        raise ValueError(f"out: not a directory: {destination}")
    _known_only(config, only)
    saved_path = destination / "grid.json"
    if saved_path.is_file():
        previous = _read_json(saved_path, "grid.json")
        if previous != config:
            raise ValueError("grid.json does not match this config")
    elif saved_path.exists():
        raise ValueError("grid.json: not a file")
    else:
        destination.mkdir(parents=True, exist_ok=True)
        _write_json(saved_path, config)
    chosen = None if not only else set(only)
    pending = [
        (arm, seed, rep)
        for arm, seed, rep in _block_order(_expected_cells(config))
        if chosen is None or arm["name"] in chosen
    ]
    plan = _cpu_plan(config)
    return _run_pending(destination, config, pending, plan)


def status_text(out: str | Path) -> str:
    """One line per expected cell, then ``done X/Y``.

    ``Y`` counts every cell, including a running SQLancer arm. A summary-only
    SQLancer arm has no cells. A cell that was interrupted is ``done (killed)``.
    """
    destination = Path(out)
    path = destination / "grid.json"
    if not path.is_file():
        raise ValueError(f"grid.json: file does not exist: {path}")
    config = _read_json(path, "grid.json")
    if not isinstance(config, dict):
        raise ValueError("grid.json: expected an object")
    lines: list[str] = []
    done = 0
    cells = _expected_cells(config)
    for arm, seed, rep in cells:
        state = _cell_state(_cell_directory(destination, arm["name"], seed, rep))
        if state == "done" or state == "done (killed)":
            done += 1
        lines.append(f"{arm['name']}/s{seed}-r{rep} {state}")
    lines.append(f"done {done}/{len(cells)}")
    return "\n".join(lines) + "\n"


def command_for(arm: Mapping[str, Any], *, out: Path, seed: int, rep: int) -> list[str]:
    """Argv of one cell. A repeat uses the same seed; ``rep`` only names the directory.

    Tests replace this with a stand-in. The real commands are the loop, the
    pure-LLM baseline, the old CoevoDB baseline, and a running SQLancer arm.
    """
    if type(rep) is not int:
        raise ValueError(f"rep: expected an integer, got {rep!r}")
    kind = arm["kind"]
    python = arm.get("python") or sys.executable
    if kind == "surprise":
        return _surprise_command(arm, python=python, out=out, seed=seed)
    if kind == "pure_llm":
        return _pure_command(arm, python=python, out=out, seed=seed)
    if kind == "old_coevodb":
        return _old_command(arm, python=python, out=out, seed=seed)
    if kind == "sqlancer" and "run" in arm:
        return _sqlancer_command(arm, python=python, out=out, seed=seed)
    raise ValueError(f"kind: {kind!r} has no cell")


def main(argv: list[str] | None = None) -> int:
    """Command line. 0 when the request succeeded, 2 for a bad request, 1 when a cell failed."""
    parser = argparse.ArgumentParser(prog="python -m surprise.experiments.grid")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run", help="run a grid config")
    run_parser.add_argument("config")
    run_parser.add_argument("--out", required=True)
    run_parser.add_argument("--only", action="append", default=None, metavar="ARM")
    status_parser = sub.add_parser("status", help="print cell status")
    status_parser.add_argument("out")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 2
    try:
        if args.command == "status":
            sys.stdout.write(status_text(args.out))
            return 0
        config = load_config(args.config)
        return run_grid(config, args.out, only=args.only)
    except ValueError as exc:
        print(f"error: {_ascii(exc)}", file=sys.stderr)
        return 2


# ---- config -------------------------------------------------------------------------------------


def _normalise(raw: Mapping[str, Any]) -> dict[str, Any]:
    unknown = sorted(str(key) for key in raw if key not in _TOP_KEYS)
    if unknown:
        raise ValueError(f"config: unknown keys {unknown}")
    missing = [key for key in ("schema", "name", "budget", "seeds", "arms") if key not in raw]
    if missing:
        raise ValueError(f"config: missing {', '.join(missing)}")
    if type(raw["schema"]) is not int or raw["schema"] != 1:
        raise ValueError(f"schema: expected 1, got {raw['schema']!r}")
    name = _require_name(raw["name"], "name")
    budget = _require_budget(raw.get("budget"), "budget")
    seeds = _require_seeds(raw.get("seeds"))
    repeats = 1 if _absent(raw, "repeats") else _require_whole(raw["repeats"], "repeats", minimum=1)
    window = 10 if _absent(raw, "window") else _require_whole(raw["window"], "window", minimum=1)
    known = None if _absent(raw, "known") else _require_text(raw["known"], "known")
    prices = _require_prices(raw.get("prices") if not _absent(raw, "prices") else None)
    concurrency = _require_whole(raw.get("concurrency", 1), "concurrency", minimum=1)
    cpus_per_cell = (
        None if _absent(raw, "cpus_per_cell") else _require_whole(raw["cpus_per_cell"], "cpus_per_cell", minimum=1)
    )
    engine_threads = (
        None if _absent(raw, "engine_threads") else _require_whole(raw["engine_threads"], "engine_threads", minimum=1)
    )
    kill_grace_minutes = _require_minutes(raw.get("kill_grace_minutes", 10.0), "kill_grace_minutes")
    arms_raw = raw.get("arms")
    if isinstance(arms_raw, str) or not isinstance(arms_raw, list) or not arms_raw:
        raise ValueError(f"arms: expected a non-empty list, got {arms_raw!r}")
    arms: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(arms_raw):
        arm = _normalise_arm(item, index, budget)
        if arm["name"] in seen:
            raise ValueError(f"arms: duplicate name {arm['name']!r}")
        seen.add(arm["name"])
        arms.append(arm)
    if _absent(raw, "reference"):
        reference = arms[0]["name"]
    else:
        reference = raw["reference"]
        if not isinstance(reference, str) or reference not in seen:
            raise ValueError(f"reference: unknown arm {reference!r}")
    return {
        "schema": 1,
        "name": name,
        "budget": budget,
        "seeds": seeds,
        "repeats": repeats,
        "reference": reference,
        "window": window,
        "known": known,
        "prices": prices,
        "concurrency": concurrency,
        "cpus_per_cell": cpus_per_cell,
        "engine_threads": engine_threads,
        "kill_grace_minutes": kill_grace_minutes,
        "arms": arms,
    }


def _normalise_arm(raw: object, index: int, top_budget: dict[str, Any]) -> dict[str, Any]:
    where = f"arms[{index}]"
    if not isinstance(raw, dict):
        raise ValueError(f"{where}: expected an object, got {raw!r}")
    kind = raw.get("kind")
    if kind not in _ARM_KEYS:
        raise ValueError(f"{where}.kind: unknown {kind!r}")
    allowed = _ARM_KEYS[kind]
    # A summary-only SQLancer arm keeps its old keys. budget belongs to run mode.
    if kind == "sqlancer" and _absent(raw, "run"):
        allowed = allowed - {"budget"}
    unknown = sorted(str(key) for key in raw if key not in allowed)
    if unknown:
        raise ValueError(f"{where}: unknown keys {unknown}")
    if "name" not in raw:
        raise ValueError(f"{where}: missing name")
    name = _require_name(raw.get("name"), f"{where}.name")
    if kind == "surprise":
        body = _arm_surprise(raw, where, top_budget)
    elif kind == "old_coevodb":
        body = _arm_old(raw, where, top_budget)
    elif kind == "pure_llm":
        body = _arm_pure(raw, where, top_budget)
    else:
        body = _arm_sqlancer(raw, where, top_budget)
    _check_network(raw, f"{where}.network", body["network"])
    arm = {"name": name, "kind": kind}
    arm.update(body)
    return arm


def _arm_surprise(raw: Mapping[str, Any], where: str, top_budget: dict[str, Any]) -> dict[str, Any]:
    budget = _arm_budget(raw, where, top_budget)
    engines = (
        ["duckdb"]
        if _absent(raw, "engines")
        else _string_list(raw["engines"], f"{where}.engines", allowed=TARGET_ENGINES)
    )
    oracles = (
        list(ORACLE_IDS)
        if _absent(raw, "oracles")
        else _string_list(raw["oracles"], f"{where}.oracles", allowed=ORACLE_IDS)
    )
    bootstrap = None if _absent(raw, "bootstrap") else _require_bootstrap(raw["bootstrap"], where)
    freeze = None if _absent(raw, "freeze") else _require_choice(raw["freeze"], f"{where}.freeze", _FREEZE_OK)
    hunter = None if _absent(raw, "hunter") else _require_choice(raw["hunter"], f"{where}.hunter", _HUNTER_OK)
    # "value" is the default hunter, the same as leaving the switch out.
    if hunter == "value":
        hunter = None
    theory_from = None if _absent(raw, "theory_from") else _require_run_at(raw["theory_from"], f"{where}.theory_from")
    select_from = None if _absent(raw, "select_from") else _require_run_at(raw["select_from"], f"{where}.select_from")
    vocabulary = None if _absent(raw, "vocabulary") else _require_file(raw["vocabulary"], f"{where}.vocabulary")
    beta = None if _absent(raw, "beta") else _require_positive(raw["beta"], f"{where}.beta")
    llm = None if _absent(raw, "llm") else _surprise_llm(raw["llm"], f"{where}.llm")
    tier = _require_tier(raw, where)
    if tier is not None and llm is None:
        raise ValueError(f"{where}.tier: requires an llm block")
    if freeze is not None and llm is not None:
        bad = [role for role in llm["roles"] if role not in _FROZEN_ROLES]
        if bad:
            raise ValueError(f"{where}.llm.roles: freeze allows only implementer and prior, got {bad!r}")
    python = _optional_python(raw, f"{where}.python")
    return {
        "budget": budget,
        "engines": engines,
        "oracles": oracles,
        "bootstrap": bootstrap,
        "freeze": freeze,
        "hunter": hunter,
        "theory_from": theory_from,
        "select_from": select_from,
        "vocabulary": vocabulary,
        "beta": beta,
        "llm": llm,
        "tier": tier,
        "python": python,
        "network": llm is not None and not llm["offline"],
    }


def _arm_old(raw: Mapping[str, Any], where: str, top_budget: dict[str, Any]) -> dict[str, Any]:
    budget = _arm_budget(raw, where, top_budget)
    if "minutes" not in budget:
        raise ValueError(f"{where}: old_coevodb requires a minutes budget")
    if _absent(raw, "mode"):
        mode = "no_llm"
    else:
        mode = raw["mode"]
        if mode not in OLD_MODES:
            raise ValueError(f"{where}.mode: expected one of {', '.join(OLD_MODES)}, got {mode!r}")
    return {
        "budget": budget,
        "mode": mode,
        "python": _optional_python(raw, f"{where}.python"),
        "network": mode != "no_llm",
    }


def _arm_pure(raw: Mapping[str, Any], where: str, top_budget: dict[str, Any]) -> dict[str, Any]:
    budget = _arm_budget(raw, where, top_budget)
    engine = (
        "duckdb"
        if _absent(raw, "engine")
        else _one_string(raw["engine"], f"{where}.engine", allowed=TARGET_ENGINES)
    )
    oracles = (
        list(ORACLE_IDS)
        if _absent(raw, "oracles")
        else _string_list(raw["oracles"], f"{where}.oracles", allowed=ORACLE_IDS)
    )
    llm = _pure_llm(None if _absent(raw, "llm") else raw["llm"], f"{where}.llm")
    return {
        "budget": budget,
        "engine": engine,
        "oracles": oracles,
        "llm": llm,
        "tier": _require_tier(raw, where),
        "python": _optional_python(raw, f"{where}.python"),
        "network": not llm["offline"],
    }


def _arm_sqlancer(raw: Mapping[str, Any], where: str, top_budget: dict[str, Any]) -> dict[str, Any]:
    if _absent(raw, "run"):
        if _absent(raw, "summary"):
            summary_path: str | Path = sqlancer.SUMMARY_PATH
            stored = str(sqlancer.SUMMARY_PATH)
        else:
            stored = _require_text(raw["summary"], f"{where}.summary")
            summary_path = stored
        try:
            summary = sqlancer.load(summary_path)
        except ValueError as exc:
            raise ValueError(f"{where}.summary: {exc}") from exc
        engine = "duckdb" if _absent(raw, "engine") else raw["engine"]
        if not isinstance(engine, str) or engine not in summary["engines"]:
            raise ValueError(f"{where}.engine: unknown {engine!r}")
        return {"summary": stored, "engine": engine, "network": False}
    if "summary" in raw:
        raise ValueError(f"{where}.summary: not valid when run is set")
    run = _sqlancer_run(raw["run"], f"{where}.run")
    if _absent(raw, "engine"):
        engine = "duckdb"
    else:
        engine = raw["engine"]
        if not isinstance(engine, str) or engine not in _SQLANCER_RUN_ENGINES:
            raise ValueError(
                f"{where}.engine: expected one of {', '.join(_SQLANCER_RUN_ENGINES)}, got {engine!r}"
            )
    budget = _arm_budget(raw, where, top_budget)
    if "minutes" not in budget:
        raise ValueError(f"{where}.budget: sqlancer run requires a minutes budget")
    return {"engine": engine, "run": run, "budget": budget, "network": False}


def _sqlancer_run(value: object, where: str) -> dict[str, Any]:
    if value is True:
        return {"oracles": list(_SQLANCER_ORACLES), "threads": 1}
    if value is False or not isinstance(value, dict):
        raise ValueError(f"{where}: expected true or an object, got {value!r}")
    unknown = sorted(set(value) - {"oracles", "threads"})
    if unknown:
        raise ValueError(f"{where}: unknown keys {unknown}")
    if "oracles" not in value:
        oracles = list(_SQLANCER_ORACLES)
    else:
        oracles = _string_list(value["oracles"], f"{where}.oracles", allowed=_SQLANCER_ORACLES)
    threads = _require_whole(value.get("threads", 1), f"{where}.threads", minimum=1)
    return {"oracles": oracles, "threads": threads}


def _arm_budget(raw: Mapping[str, Any], where: str, top_budget: dict[str, Any]) -> dict[str, Any]:
    if _absent(raw, "budget"):
        return dict(top_budget)
    return _require_budget(raw["budget"], f"{where}.budget")


def _surprise_llm(value: object, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{where}: expected an object, got {value!r}")
    unknown = sorted(set(value) - {"roles", "cache", "max_calls", "offline"})
    if unknown:
        raise ValueError(f"{where}: unknown keys {unknown}")
    if "roles" not in value or "cache" not in value:
        raise ValueError(f"{where}: missing roles or cache")
    roles = _string_list(value["roles"], f"{where}.roles", allowed=_LLM_ROLES)
    cache = _require_text(value["cache"], f"{where}.cache")
    if "max_calls" not in value or value["max_calls"] is None:
        raise ValueError(f"{where}.max_calls: required when roles are set")
    max_calls = _require_max_calls(value["max_calls"], f"{where}.max_calls")
    offline = False if _absent(value, "offline") else _require_bool(value["offline"], f"{where}.offline")
    return {"roles": roles, "cache": cache, "max_calls": max_calls, "offline": offline}


def _pure_llm(value: object, where: str) -> dict[str, Any]:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError(f"{where}: expected an object, got {value!r}")
    unknown = sorted(set(value) - {"cache", "max_calls", "offline"})
    if unknown:
        raise ValueError(f"{where}: unknown keys {unknown}")
    if _absent(value, "cache"):
        cache = None
    else:
        cache = _require_text(value["cache"], f"{where}.cache")
    offline = False if _absent(value, "offline") else _require_bool(value["offline"], f"{where}.offline")
    if _absent(value, "max_calls"):
        max_calls = None
    else:
        max_calls = _require_max_calls(value["max_calls"], f"{where}.max_calls")
    if not offline and max_calls is None:
        raise ValueError(f"{where}.max_calls: required when not offline")
    return {"cache": cache, "max_calls": max_calls, "offline": offline}


def _require_bootstrap(value: object, where: str) -> list[dict[str, Any]] | None:
    if isinstance(value, str) or not isinstance(value, list):
        raise ValueError(f"{where}.bootstrap: expected a list, got {value!r}")
    if not value:
        return None
    items: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        spot = f"{where}.bootstrap[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{spot}: expected an object")
        unknown = sorted(set(item) - {"case", "oracle", "rule"})
        if unknown or {"case", "oracle", "rule"} - set(item):
            raise ValueError(f"{spot}: keys must be case, oracle, rule")
        try:
            case = SqlCase.from_dict(item["case"]).to_dict()
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{spot}.case: not a SqlCase") from exc
        oracle = item["oracle"]
        if not isinstance(oracle, str) or oracle not in ORACLE_IDS:
            raise ValueError(f"{spot}.oracle: unknown {oracle!r}")
        rule = item["rule"]
        if rule is not None and (not isinstance(rule, str) or rule == ""):
            raise ValueError(f"{spot}.rule: expected a string or null, got {rule!r}")
        items.append({"case": case, "oracle": oracle, "rule": rule})
    return items


def _require_budget(value: object, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{where}: expected an object with minutes or experiments, got {value!r}")
    unknown = sorted(set(value) - {"minutes", "experiments"})
    if unknown or len(value) != 1:
        raise ValueError(f"{where}: expected exactly one of minutes, experiments")
    if "minutes" in value:
        return {"minutes": _require_minutes(value["minutes"], f"{where}.minutes")}
    return {"experiments": _require_whole(value["experiments"], f"{where}.experiments", minimum=1)}


def _require_seeds(value: object) -> list[int]:
    if isinstance(value, str) or not isinstance(value, list) or not value:
        raise ValueError(f"seeds: expected a non-empty list of integers, got {value!r}")
    seeds: list[int] = []
    seen: set[int] = set()
    for item in value:
        number = _require_int(item, "seeds")
        if number in seen:
            raise ValueError(f"seeds: duplicate {number}")
        seen.add(number)
        seeds.append(number)
    return seeds


def _require_prices(value: object) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"prices: expected an object or null, got {type(value).__name__}")
    try:
        copied = json.loads(json.dumps(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("prices: expected a JSON object") from exc
    if not isinstance(copied, dict):
        raise ValueError("prices: expected an object or null")
    return copied


def _require_name(value: object, where: str) -> str:
    if not isinstance(value, str) or _NAME.fullmatch(value) is None:
        raise ValueError(f"{where}: expected a name matching [a-z0-9_-]+, got {value!r}")
    return value


def _require_text(value: object, where: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{where}: expected a non-empty string, got {value!r}")
    return value


def _require_file(value: object, where: str) -> str:
    text = _require_text(value, where)
    if not Path(text).is_file():
        raise ValueError(f"{where}: file does not exist: {text}")
    return text


def _require_int(value: object, where: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{where}: expected an integer, got {value!r}")
    return value


def _require_whole(value: object, where: str, *, minimum: int) -> int:
    number = _require_int(value, where)
    if number < minimum:
        raise ValueError(f"{where}: expected an integer >= {minimum}, got {value!r}")
    return number


def _require_max_calls(value: object, where: str) -> int | str:
    if value == _UNLIMITED:
        return _UNLIMITED
    return _require_whole(value, where, minimum=0)


def _require_tier(raw: Mapping[str, Any], where: str) -> str | None:
    if _absent(raw, "tier"):
        return None
    return _require_choice(raw["tier"], f"{where}.tier", _TIERS)


def _require_minutes(value: object, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{where}: expected a number > 0, got {value!r}")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{where}: expected a number > 0, got {value!r}")
    return number


def _require_positive(value: object, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{where}: expected a number > 0, got {value!r}")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{where}: expected a number > 0, got {value!r}")
    return number


def _require_bool(value: object, where: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{where}: expected a bool, got {value!r}")
    return value


def _require_choice(value: object, where: str, choices: tuple[str, ...]) -> str:
    if not isinstance(value, str) or value not in choices:
        raise ValueError(f"{where}: expected one of {', '.join(choices)}, got {value!r}")
    return value


def _require_run_at(value: object, where: str) -> str:
    if not isinstance(value, str) or "@" not in value:
        raise ValueError(f"{where}: expected RUN@GEN, got {value!r}")
    run, generation = value.rsplit("@", 1)
    if run == "" or generation == "":
        raise ValueError(f"{where}: expected RUN@GEN, got {value!r}")
    return value


def _string_list(value: object, where: str, *, allowed: Sequence[str]) -> list[str]:
    if isinstance(value, str) or not isinstance(value, list) or not value:
        raise ValueError(f"{where}: expected a non-empty list of strings, got {value!r}")
    items: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or item == "":
            raise ValueError(f"{where}: expected non-empty strings, got {item!r}")
        if item not in allowed:
            raise ValueError(f"{where}: unknown {item!r}")
        if item in seen:
            raise ValueError(f"{where}: duplicate {item!r}")
        seen.add(item)
        items.append(item)
    return items


def _one_string(value: object, where: str, *, allowed: Sequence[str]) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{where}: expected a non-empty string, got {value!r}")
    if value not in allowed:
        raise ValueError(f"{where}: unknown {value!r}")
    return value


def _optional_python(raw: Mapping[str, Any], where: str) -> str | None:
    if _absent(raw, "python"):
        return None
    return _require_text(raw["python"], where)


def _check_network(raw: Mapping[str, Any], where: str, computed: bool) -> None:
    if _absent(raw, "network"):
        return
    if raw["network"] is not computed:
        raise ValueError(f"{where}: computed {computed}, got {raw['network']!r}")


def _absent(raw: Mapping[str, Any], key: str) -> bool:
    return key not in raw or raw[key] is None


# ---- running ------------------------------------------------------------------------------------


def _expected_cells(config: Mapping[str, Any]) -> list[tuple[dict[str, Any], int, int]]:
    cells: list[tuple[dict[str, Any], int, int]] = []
    for rep in range(int(config["repeats"])):
        for seed in config["seeds"]:
            for arm in config["arms"]:
                if arm["kind"] == "sqlancer" and "run" not in arm:
                    continue
                cells.append((arm, int(seed), rep))
    return cells


def _engine_key(arm: Mapping[str, Any]) -> tuple[str, ...]:
    kind = arm["kind"]
    if kind == "surprise":
        return tuple(arm["engines"])
    if kind in ("pure_llm", "sqlancer"):
        return (arm["engine"],)
    return ("duckdb",)


def _block_order(
    cells: Sequence[tuple[dict[str, Any], int, int]],
) -> list[tuple[dict[str, Any], int, int]]:
    """Group by (repeat, seed, engine set), first-seen order, arms in config order."""
    groups: dict[tuple[Any, ...], list[tuple[dict[str, Any], int, int]]] = {}
    order: list[tuple[Any, ...]] = []
    for arm, seed, rep in cells:
        key = (rep, seed, _engine_key(arm))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((arm, seed, rep))
    return [item for key in order for item in groups[key]]


def _known_only(config: Mapping[str, Any], only: Sequence[str] | None) -> None:
    if not only:
        return
    if isinstance(only, str):
        raise ValueError(f"only: expected arm names, got {only!r}")
    names = {arm["name"] for arm in config["arms"]}
    for name in only:
        if name not in names:
            raise ValueError(f"only: unknown arm {name!r}")


class _CellProc:
    """One child process and the bookkeeping the poll loop needs."""

    def __init__(
        self,
        proc: subprocess.Popen[bytes],
        log: object,
        slot: int,
        arm: Mapping[str, Any],
        seed: int,
        rep: int,
        argv: list[str],
        started: datetime,
        clock: float,
        deadline_s: float | None,
        cpus: list[int] | None,
        engine_threads: int | None,
        directory: Path,
    ) -> None:
        self.proc = proc
        self.log = log
        self.slot = slot
        self.arm = arm
        self.seed = seed
        self.rep = rep
        self.argv = argv
        self.started = started
        self.clock = clock
        self.deadline_s = deadline_s
        self.cpus = cpus
        self.engine_threads = engine_threads
        self.directory = directory
        self.interrupted = False
        self.interrupted_at = 0.0
        self.hard_killed = False

    @property
    def label(self) -> str:
        return f"{self.arm['name']}/s{self.seed}-r{self.rep}"


def _run_pending(
    out: Path,
    config: Mapping[str, Any],
    pending: Sequence[tuple[dict[str, Any], int, int]],
    plan: dict[int, list[int]] | None,
) -> int:
    """Poll children on this thread. Return 1 when any selected cell failed."""
    concurrency = int(config.get("concurrency", 1))
    grace = float(config.get("kill_grace_minutes", 10.0))
    threads = config.get("engine_threads")
    running: dict[int, _CellProc] = {}
    failed = False
    index = 0
    previous_break = _ignore_console_break()
    try:
        while index < len(pending) or running:
            while index < len(pending) and len(running) < concurrency:
                arm, seed, rep = pending[index]
                index += 1
                directory = _cell_directory(out, arm["name"], seed, rep)
                label = f"{arm['name']}/s{seed}-r{rep}"
                # A done cell is not opened for writing, and its log and bootstrap file stay as they are.
                if _is_done(directory):
                    print(label + " done", flush=True)
                    continue
                slot = _free_slot(running, concurrency)
                cpus = None if plan is None else list(plan[slot])
                cell = _launch(arm, seed, rep, directory, slot, cpus, threads, grace)
                if cell is None:
                    failed = True
                    continue
                running[slot] = cell
            if not running:
                continue
            _supervise(running)
            # Record cells that have already exited before waiting on a hard kill,
            # so one stuck tree does not stretch another cell's wall clock.
            for slot in [slot for slot, cell in running.items() if cell.proc.poll() is not None]:
                if _finish(running.pop(slot)) == "failed":
                    failed = True
            for cell in running.values():
                if cell.hard_killed and cell.proc.poll() is None:
                    try:
                        cell.proc.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        _kill_tree(cell.proc)
            if running:
                time.sleep(_POLL_S)
    finally:
        for cell in running.values():
            if cell.proc.poll() is None:
                _kill_tree(cell.proc)
                try:
                    cell.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
            if sys.platform != "win32":
                _kill_group(cell.proc.pid)
            if hasattr(cell.log, "close"):
                cell.log.close()
        _restore_console_break(previous_break)
    return 1 if failed else 0


def _launch(
    arm: Mapping[str, Any],
    seed: int,
    rep: int,
    directory: Path,
    slot: int,
    cpus: list[int] | None,
    engine_threads: int | None,
    grace: float,
) -> _CellProc | None:
    if directory.exists():
        _retire(directory)
    directory.parent.mkdir(parents=True, exist_ok=True)
    if arm.get("bootstrap"):
        # Beside the cell directory: the loop refuses a non-empty output directory.
        _write_json(_bootstrap_file(directory), arm["bootstrap"])
    argv = command_for(arm, out=directory, seed=seed, rep=rep)
    deadline = _deadline_s(arm, grace)
    env = _child_env(bool(arm["network"]), engine_threads)
    started = datetime.now(timezone.utc)
    clock = time.monotonic()
    log_path = _cell_log(directory)
    try:
        log = log_path.open("wb")
    except OSError as exc:
        _write_cell(directory, arm, seed, rep, argv, started, clock, None, slot, cpus, engine_threads, deadline, False, False)
        _note_log(log_path, exc)
        print(f"{arm['name']}/s{seed}-r{rep} failed", flush=True)
        return None
    try:
        proc = subprocess.Popen(argv, **_popen_kwargs(env, log, cpus))
    except OSError as exc:
        _note_log_handle(log, exc)
        log.close()
        _write_cell(directory, arm, seed, rep, argv, started, clock, None, slot, cpus, engine_threads, deadline, False, False)
        print(f"{arm['name']}/s{seed}-r{rep} failed", flush=True)
        return None
    return _CellProc(proc, log, slot, arm, seed, rep, argv, started, clock, deadline, cpus, engine_threads, directory)


def _popen_kwargs(env: dict[str, str], log: object, cpus: list[int] | None) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "cwd": str(FRAMEWORK),
        "env": env,
        "stdin": subprocess.DEVNULL,
        "stdout": log,
        "stderr": subprocess.STDOUT,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
        if cpus:
            kwargs["preexec_fn"] = _bind_cpus(cpus)
    return kwargs


def _bind_cpus(cpus: Sequence[int]):
    pinned = list(cpus)

    def bind() -> None:
        os.sched_setaffinity(0, pinned)

    return bind


def _supervise(running: Mapping[int, _CellProc]) -> None:
    now = time.monotonic()
    for cell in running.values():
        if cell.proc.poll() is not None or cell.deadline_s is None or cell.hard_killed:
            continue
        if not cell.interrupted:
            if now - cell.clock >= cell.deadline_s and _send_interrupt(cell.proc):
                cell.interrupted = True
                cell.interrupted_at = time.monotonic()
            continue
        # HARD_KILL_AFTER_S is a module global so a test can patch it between checks.
        if time.monotonic() - cell.interrupted_at >= HARD_KILL_AFTER_S:
            _kill_tree(cell.proc)
            cell.hard_killed = True


def _finish(cell: _CellProc) -> str:
    """Write ``cell.json`` after the child has exited. Return the printed result word."""
    try:
        if cell.proc.poll() is None:
            try:
                cell.proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                _kill_tree(cell.proc)
                cell.hard_killed = True
                cell.interrupted = True
                cell.proc.wait(timeout=30)
        code: int | None = cell.proc.returncode
    finally:
        log = cell.log
        if hasattr(log, "close"):
            log.close()
    if sys.platform != "win32":
        _kill_group(cell.proc.pid)
    from surprise.experiments.pg_instance import stop_all

    stopped = stop_all(cell.directory)
    if stopped:
        with _cell_log(cell.directory).open("ab") as log:
            log.write(f"Stopped {len(stopped)} residual PostgreSQL servers\n".encode("ascii"))
    if cell.interrupted:
        status = "done"
        word = "done (killed)"
    elif code == 0:
        status = "done"
        word = "done"
    else:
        status = "failed"
        word = "failed"
    _write_cell(
        cell.directory,
        cell.arm,
        cell.seed,
        cell.rep,
        cell.argv,
        cell.started,
        cell.clock,
        code,
        cell.slot,
        cell.cpus,
        cell.engine_threads,
        cell.deadline_s,
        cell.interrupted,
        cell.hard_killed,
        status=status,
    )
    print(f"{cell.label} {word}", flush=True)
    return word


def _write_cell(
    directory: Path,
    arm: Mapping[str, Any],
    seed: int,
    rep: int,
    argv: list[str],
    started: datetime,
    clock: float,
    code: int | None,
    slot: int,
    cpus: list[int] | None,
    engine_threads: int | None,
    deadline_s: float | None,
    killed: bool,
    hard_killed: bool,
    *,
    status: str | None = None,
) -> None:
    if status is None:
        status = "done" if code == 0 else "failed"
    payload = {
        "arm": arm["name"],
        "kind": arm["kind"],
        "seed": seed,
        "rep": rep,
        "status": status,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "wall_s": time.monotonic() - clock,
        "returncode": code,
        "command": list(argv),
        "slot": slot,
        "cpus": cpus,
        "engine_threads": engine_threads,
        "deadline_s": deadline_s,
        "killed": killed,
        "hard_killed": hard_killed,
    }
    directory.mkdir(parents=True, exist_ok=True)
    _write_json(directory / "cell.json", payload)


def _deadline_s(arm: Mapping[str, Any], grace: float) -> float | None:
    budget = arm.get("budget")
    if not isinstance(budget, Mapping) or "minutes" not in budget:
        return None
    return 60.0 * (float(budget["minutes"]) + grace)


def _cpu_plan(config: Mapping[str, Any]) -> dict[int, list[int]] | None:
    count = config.get("cpus_per_cell")
    if count is None:
        return None
    if not hasattr(os, "sched_setaffinity") or not hasattr(os, "sched_getaffinity"):
        print(
            "cpus_per_cell is set but os.sched_setaffinity is unavailable; cells will not be pinned",
            flush=True,
        )
        return None
    pool = sorted(os.sched_getaffinity(0))
    concurrency = int(config["concurrency"])
    need = concurrency * int(count)
    if need > len(pool):
        raise ValueError(
            f"cpus_per_cell: {concurrency} * {count} = {need} CPUs, only {len(pool)} available"
        )
    return {slot: list(pool[slot * int(count):(slot + 1) * int(count)]) for slot in range(concurrency)}


def _free_slot(running: Mapping[int, object], concurrency: int) -> int:
    for slot in range(concurrency):
        if slot not in running:
            return slot
    raise RuntimeError("no free slot")


def _send_interrupt(proc: subprocess.Popen[bytes]) -> bool:
    """Interrupt the cell's main process. False when it has already exited."""
    if proc.poll() is not None:
        return False
    try:
        if sys.platform == "win32":
            os.kill(proc.pid, signal.CTRL_BREAK_EVENT)
        else:
            os.kill(proc.pid, signal.SIGINT)
    except OSError:
        return proc.poll() is None
    return True


def _kill_tree(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return
    _kill_group(proc.pid)


def _kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        pass


def _ignore_console_break() -> Any:
    """Guard the grid against console breaks while supervising child groups.

    Children install their own handler; the grid's handler is restored when
    the run returns.
    """
    if sys.platform != "win32" or not hasattr(signal, "SIGBREAK"):
        return None
    return signal.signal(signal.SIGBREAK, signal.SIG_IGN)


def _restore_console_break(previous: Any) -> None:
    if previous is None:
        return
    # Let a break that was already queued land while it is still ignored.
    time.sleep(0.05)
    signal.signal(signal.SIGBREAK, previous)


def _note_log(path: Path, exc: BaseException) -> None:
    note = f"{type(exc).__name__}: {_ascii(exc)}\n".encode("ascii")
    try:
        with path.open("ab") as handle:
            handle.write(note)
    except OSError:
        pass


def _note_log_handle(log: Any, exc: BaseException) -> None:
    note = f"{type(exc).__name__}: {_ascii(exc)}\n".encode("ascii")
    try:
        log.write(note)
    except OSError:
        pass


def _child_env(network: bool, engine_threads: int | None = None) -> dict[str, str]:
    if network:
        env = dict(os.environ)
    else:
        env = {key: value for key, value in os.environ.items() if key.upper() not in _SECRET_ENV}
    if engine_threads is not None:
        env[_THREADS_ENV] = str(engine_threads)
    return env


def _is_done(directory: Path) -> bool:
    path = directory / "cell.json"
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return isinstance(data, dict) and data.get("status") == "done"


def _cell_record(directory: Path) -> dict[str, Any] | None:
    path = directory / "cell.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _cell_state(directory: Path) -> str:
    data = _cell_record(directory)
    if data is not None and data.get("status") == "done":
        if data.get("killed") is True:
            return "done (killed)"
        return "done"
    if not directory.exists():
        return "missing"
    return "failed"


def _retire(directory: Path) -> None:
    k = 1
    while True:
        dest = directory.with_name(f"{directory.name}.stale-{k}")
        if not dest.exists():
            directory.rename(dest)
            return
        k += 1


def _cell_directory(out: Path, arm: str, seed: int, rep: int) -> Path:
    return out / "cells" / arm / f"s{seed}-r{rep}"


def _cell_log(directory: Path) -> Path:
    return directory.parent / f"{directory.name}.log"


def _bootstrap_file(directory: Path) -> Path:
    return directory.parent / f"{directory.name}.bootstrap.json"


def _surprise_command(arm: Mapping[str, Any], *, python: str, out: Path, seed: int) -> list[str]:
    argv = [python, "-m", "surprise.experiments.loop", "--out", str(out), "--seed", str(seed)]
    argv += _budget_flags(arm["budget"], minutes="--max-minutes", experiments="--max-experiments")
    for engine in arm["engines"]:
        argv += ["--engine", engine]
    for oracle in arm["oracles"]:
        argv += ["--oracle", oracle]
    if arm.get("bootstrap"):
        argv += ["--bootstrap", str(_bootstrap_file(out))]
    if arm.get("vocabulary"):
        argv += ["--vocabulary", arm["vocabulary"]]
    if arm.get("beta") is not None:
        argv += ["--beta", _cli_number(arm["beta"])]
    if arm.get("freeze"):
        argv += ["--freeze", arm["freeze"]]
    if arm.get("hunter"):
        argv += ["--hunter", arm["hunter"]]
    if arm.get("theory_from"):
        argv += ["--theory-from", arm["theory_from"]]
    if arm.get("select_from"):
        argv += ["--select-from", arm["select_from"]]
    llm = arm.get("llm")
    if llm:
        for role in llm["roles"]:
            argv += ["--llm", role]
        argv += ["--llm-cache", llm["cache"]]
        argv += ["--llm-max-calls", str(llm["max_calls"])]
        if llm["offline"]:
            argv += ["--llm-offline"]
        if arm.get("tier"):
            argv += ["--llm-tier", arm["tier"]]
    return argv


def _pure_command(arm: Mapping[str, Any], *, python: str, out: Path, seed: int) -> list[str]:
    argv = [
        python,
        "-m",
        "surprise.baselines.pure_llm",
        "--out",
        str(out),
        "--seed",
        str(seed),
        "--engine",
        arm["engine"],
    ]
    for oracle in arm["oracles"]:
        argv += ["--oracle", oracle]
    argv += _budget_flags(arm["budget"], minutes="--max-minutes", experiments="--max-experiments")
    llm = arm["llm"]
    if llm.get("cache"):
        argv += ["--llm-cache", llm["cache"]]
    if llm.get("max_calls") is not None:
        argv += ["--llm-max-calls", str(llm["max_calls"])]
    if llm.get("offline"):
        argv += ["--llm-offline"]
    if arm.get("tier"):
        argv += ["--llm-tier", arm["tier"]]
    return argv


def _old_command(arm: Mapping[str, Any], *, python: str, out: Path, seed: int) -> list[str]:
    return [
        python,
        "-m",
        "surprise.baselines.old_no_llm",
        "--out",
        str(out),
        "--minutes",
        _cli_number(arm["budget"]["minutes"]),
        "--seed",
        str(seed),
        "--mode",
        arm["mode"],
    ]


def _sqlancer_command(arm: Mapping[str, Any], *, python: str, out: Path, seed: int) -> list[str]:
    run = arm["run"]
    argv = [
        python,
        "-m",
        "surprise.baselines.sqlancer_run",
        "--out",
        str(out),
        "--seed",
        str(seed),
        "--engine",
        arm["engine"],
        "--max-minutes",
        _cli_number(arm["budget"]["minutes"]),
    ]
    for oracle in run["oracles"]:
        argv += ["--oracle", oracle]
    argv += ["--threads", str(run["threads"])]
    return argv


def _budget_flags(budget: Mapping[str, Any], *, minutes: str, experiments: str) -> list[str]:
    if "minutes" in budget:
        return [minutes, _cli_number(budget["minutes"])]
    return [experiments, str(budget["experiments"])]


def _cli_number(value: float) -> str:
    return json.dumps(float(value))


def _read_json(path: Path, where: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{where}: not JSON") from exc


def _write_json(path: Path, payload: object) -> None:
    text = json.dumps(payload, ensure_ascii=True, indent=2) + "\n"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)


def _ascii(text: object) -> str:
    return str(text).encode("ascii", "backslashreplace").decode("ascii")


if __name__ == "__main__":
    sys.exit(main())
