"""Configuration-driven experiment grid: arm x seed x budget x repeat.

One cell is one child process, run one at a time so a wall-clock budget is
shared fairly. A cell whose ``cell.json`` says ``done`` is left untouched.
Anything else already in that directory is renamed to ``<cell>.stale-<k>``
and the cell runs again.

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
        "python",
        "network",
    },
    "old_coevodb": {"name", "kind", "budget", "mode", "python", "network"},
    "pure_llm": {"name", "kind", "budget", "engine", "oracles", "llm", "python", "network"},
    "sqlancer": {"name", "kind", "summary", "engine", "network"},
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
    failed = False
    chosen = None if not only else set(only)
    for arm, seed, rep in _expected_cells(config):
        if chosen is not None and arm["name"] not in chosen:
            continue
        if _run_cell(destination, arm, seed, rep):
            failed = True
    return 1 if failed else 0


def status_text(out: str | Path) -> str:
    """One line per expected cell, then ``done X/Y``. ``Y`` counts every non-SQLancer cell."""
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
        if state == "done":
            done += 1
        lines.append(f"{arm['name']}/s{seed}-r{rep} {state}")
    lines.append(f"done {done}/{len(cells)}")
    return "\n".join(lines) + "\n"


def command_for(arm: Mapping[str, Any], *, out: Path, seed: int, rep: int) -> list[str]:
    """Argv of one cell. A repeat uses the same seed; ``rep`` only names the directory.

    Tests replace this with a stand-in. The real commands are the loop, the
    pure-LLM baseline, and the old CoevoDB baseline.
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
        "arms": arms,
    }


def _normalise_arm(raw: object, index: int, top_budget: dict[str, Any]) -> dict[str, Any]:
    where = f"arms[{index}]"
    if not isinstance(raw, dict):
        raise ValueError(f"{where}: expected an object, got {raw!r}")
    kind = raw.get("kind")
    if kind not in _ARM_KEYS:
        raise ValueError(f"{where}.kind: unknown {kind!r}")
    unknown = sorted(str(key) for key in raw if key not in _ARM_KEYS[kind])
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
        body = _arm_sqlancer(raw, where)
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
        "python": _optional_python(raw, f"{where}.python"),
        "network": not llm["offline"],
    }


def _arm_sqlancer(raw: Mapping[str, Any], where: str) -> dict[str, Any]:
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
    max_calls = _require_whole(value["max_calls"], f"{where}.max_calls", minimum=0)
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
        max_calls = _require_whole(value["max_calls"], f"{where}.max_calls", minimum=0)
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
                if arm["kind"] == "sqlancer":
                    continue
                cells.append((arm, int(seed), rep))
    return cells


def _known_only(config: Mapping[str, Any], only: Sequence[str] | None) -> None:
    if not only:
        return
    if isinstance(only, str):
        raise ValueError(f"only: expected arm names, got {only!r}")
    names = {arm["name"] for arm in config["arms"]}
    for name in only:
        if name not in names:
            raise ValueError(f"only: unknown arm {name!r}")


def _run_cell(out: Path, arm: Mapping[str, Any], seed: int, rep: int) -> bool:
    """Run one cell unless it is already done. Return True when this attempt failed."""
    directory = _cell_directory(out, arm["name"], seed, rep)
    label = f"{arm['name']}/s{seed}-r{rep}"
    # A done cell is not opened for writing, and its log and bootstrap file stay as they are.
    if _is_done(directory):
        print(label + " done", flush=True)
        return False
    if directory.exists():
        _retire(directory)
    directory.parent.mkdir(parents=True, exist_ok=True)
    if arm.get("bootstrap"):
        # Beside the cell directory: the loop refuses a non-empty output directory.
        _write_json(_bootstrap_file(directory), arm["bootstrap"])
    argv = command_for(arm, out=directory, seed=seed, rep=rep)
    code = _spawn(directory, argv, _child_env(bool(arm["network"])), arm, seed, rep)
    failed = code != 0
    print(f"{label} {'failed' if failed else 'done'}", flush=True)
    return failed


def _spawn(
    directory: Path,
    argv: list[str],
    env: dict[str, str],
    arm: Mapping[str, Any],
    seed: int,
    rep: int,
) -> int | None:
    log_path = _cell_log(directory)
    code: int | None = None
    started = datetime.now(timezone.utc)
    clock = time.monotonic()
    try:
        with log_path.open("wb") as handle:
            proc = subprocess.run(
                argv,
                cwd=str(FRAMEWORK),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False,
            )
            code = proc.returncode
    except OSError as exc:
        code = None
        note = f"{type(exc).__name__}: {_ascii(exc)}\n".encode("ascii")
        try:
            with log_path.open("ab") as handle:
                handle.write(note)
        except OSError:
            pass
    finally:
        payload = {
            "arm": arm["name"],
            "kind": arm["kind"],
            "seed": seed,
            "rep": rep,
            "status": "done" if code == 0 else "failed",
            "started_at": started.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "wall_s": time.monotonic() - clock,
            "returncode": code,
            "command": list(argv),
        }
        directory.mkdir(parents=True, exist_ok=True)
        _write_json(directory / "cell.json", payload)
    return code


def _child_env(network: bool) -> dict[str, str]:
    if network:
        return dict(os.environ)
    return {key: value for key, value in os.environ.items() if key.upper() not in _SECRET_ENV}


def _is_done(directory: Path) -> bool:
    path = directory / "cell.json"
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return isinstance(data, dict) and data.get("status") == "done"


def _cell_state(directory: Path) -> str:
    if _is_done(directory):
        return "done"
    if not directory.exists():
        return "missing"
    path = directory / "cell.json"
    if not path.is_file():
        return "failed"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "failed"
    if isinstance(data, dict) and data.get("status") == "failed":
        return "failed"
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
