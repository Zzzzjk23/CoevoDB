"""S13 gate: the formal experiment protocol (documents only).

Usage (from ``framework/``)::

    python -m surprise.gates.s13                 # everything
    python -m surprise.gates.s13 --only spec cells

Exit code 0 = pass. Groups, following the S13 section of SESSIONS.md and the user's decisions of
2026-10-19 (PLAN section 9):

``scope``     S13 changed only ``framework/surprise/docs/`` and its own two gate files: the work
              tree (or the ``s13-done`` tag once it exists) against ``s12-done-r2``;
``sections``  EXPERIMENT.md has its sections in order, ends with a machine-readable JSON spec, and
              states the cell totals that the spec adds up to;
``arms``      every config key of every spec arm is one the experiment grid accepts today, or the
              arm names the session that adds it (``needs``); LLM roles, hunter and freeze values
              are valid; a frozen arm turns on only the roles a frozen arm may; the ablation arms
              drop exactly the roles the protocol says; every arm is used and every used arm exists;
``engines``   every engine is a target (or a reference) today, or names the session that brings it
              in; every milestone lists, among its prerequisites, the sessions its engines and arms
              need; single-engine kinds run on one engine per cell;
``cells``     the cell counts recomputed from the spec equal the counts it declares, per milestone
              and in total;
``seeds``     formal and pilot seeds are distinct, and none of them appears in the gates or tests at
              ``s12-done-r2``;
``sessions``  SESSIONS.md has a section for S13 to S25, every prerequisite and run session of a
              milestone has one, prerequisites come earlier, PLAN.md has section 9 and HANDOFF.md
              a status row for S13.

Tables live in ``s13_cases.py``. Output is ASCII only. No group runs an engine or makes a network
call.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from . import s13_cases as C
from .s06 import GateFailure, _ascii, require

FRAMEWORK = Path(__file__).resolve().parents[2]
REPO = FRAMEWORK.parent
SESSION_RE = re.compile(r"^S\d{2}$")


# ---- helpers ------------------------------------------------------------------------------------

def git(*args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=REPO, capture_output=True, timeout=300)
    require(proc.returncode == 0, f"git {' '.join(args)}: {proc.stderr.decode('utf-8', 'replace')[-300:]}")
    return proc.stdout.decode("utf-8", "replace")


def read(relative: str) -> str:
    path = REPO / relative
    require(path.is_file(), f"{relative}: missing")
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def spec() -> dict[str, Any]:
    text = read(C.EXPERIMENT)
    require(C.SPEC_HEADING in text, f"EXPERIMENT.md: no heading {C.SPEC_HEADING!r}")
    tail = text.split(C.SPEC_HEADING, 1)[1]
    match = re.search(r"```json\n(.*?)\n```", tail, re.S)
    require(match is not None, "EXPERIMENT.md: no ```json block under the spec heading")
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise GateFailure(f"EXPERIMENT.md spec is not JSON: {exc}") from exc
    require(isinstance(data, dict) and data.get("schema") == 1, "spec: schema must be 1")
    for key in ("hours", "seeds", "engines", "arms", "milestones", "totals"):
        require(key in data, f"spec: missing {key!r}")
    return data


def session_headings() -> set[str]:
    text = read(C.SESSIONS)
    return set(re.findall(r"^## (S\d{2}) ·", text, re.M))


def grid_tables() -> dict[str, Any]:
    sys.path.insert(0, str(FRAMEWORK))
    from surprise.experiments import grid  # noqa: PLC0415 - imported only for its tables
    from surprise.harness.oracles import registry  # noqa: PLC0415
    return {
        "arm_keys": grid._ARM_KEYS,
        "roles": tuple(grid._LLM_ROLES),
        "hunter": tuple(grid._HUNTER_OK),
        "freeze": tuple(grid._FREEZE_OK),
        "frozen_roles": tuple(grid._FROZEN_ROLES),
        "targets": tuple(registry.TARGET_ENGINES),
        "references": tuple(registry.REFERENCE_ENGINES),
    }


def requires_closure(milestone: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> set[str]:
    seen: set[str] = set()
    stack = list(milestone.get("requires", []))
    while stack:
        item = stack.pop()
        if item in seen:
            continue
        seen.add(item)
        if item in by_id:
            stack.extend(by_id[item].get("requires", []))
    return seen


# ---- groups -------------------------------------------------------------------------------------

def check_scope() -> str:
    tags = git("tag", "--list", C.DONE_TAG).split()
    if C.DONE_TAG in tags:
        changed = git("diff", "--name-only", C.BASE_TAG, C.DONE_TAG).split("\n")
        where = f"{C.BASE_TAG}..{C.DONE_TAG}"
    else:
        changed = git("diff", "--name-only", C.BASE_TAG).split("\n")
        changed += git("ls-files", "--others", "--exclude-standard").split("\n")
        where = f"{C.BASE_TAG}..work tree"
    changed = sorted({path.strip() for path in changed if path.strip()})
    outside = [path for path in changed
               if not any(path == allowed or (allowed.endswith("/") and path.startswith(allowed))
                          for allowed in C.ALLOWED_CHANGES)]
    require(not outside, f"changes outside the S13 scope ({where}): {outside[:10]}")
    require(C.EXPERIMENT in changed, f"{C.EXPERIMENT} is not among the changes ({where})")
    return f"{len(changed)} paths changed ({where}), all under the docs or the S13 gate"


def check_sections() -> str:
    text = read(C.EXPERIMENT)
    position = -1
    for heading in C.SECTIONS:
        found = re.search(rf"^{re.escape(heading)}", text[position + 1:], re.M)
        require(found is not None, f"EXPERIMENT.md: heading {heading!r} missing or out of order")
        position += 1 + found.start()
    data = spec()
    totals = data["totals"]
    stated = re.findall(r"(\d+) 个 24 小时格加 (\d+) 个 1 小时格", text)
    require(stated, "EXPERIMENT.md never states the cell totals")
    expected = (str(totals["cells_24h"]), str(totals["cells_1h"]))
    wrong = [pair for pair in stated if pair != expected]
    require(not wrong, f"EXPERIMENT.md states totals {wrong}, the spec says {expected}")
    return f"{len(C.SECTIONS)} headings in order; spec parses; totals stated {len(stated)}x, all match"


def check_arms() -> str:
    data, tables = spec(), grid_tables()
    sessions = session_headings()
    arms: dict[str, Any] = data["arms"]
    used = {arm for milestone in data["milestones"] for group in milestone["groups"] for arm in group["arms"]}
    require(used <= set(arms), f"groups use undefined arms: {sorted(used - set(arms))}")
    require(set(arms) <= used, f"arms defined but never run: {sorted(set(arms) - used)}")
    for name, arm in arms.items():
        kind = arm.get("kind")
        require(kind in tables["arm_keys"], f"{name}: unknown kind {kind!r}")
        needs: dict[str, str] = arm.get("needs", {})
        for key, session in needs.items():
            require(isinstance(session, str) and SESSION_RE.match(session) and session in sessions,
                    f"{name}: needs[{key!r}] names {session!r}, which has no section in SESSIONS.md")
        allowed = set(tables["arm_keys"][kind]) | C.META_KEYS
        for key in arm:
            require(key in allowed or key in needs,
                    f"{name}: key {key!r} is not a {kind} grid key and no session is named for it")
        llm = arm.get("llm")
        if llm is not None:
            require(kind in C.LLM_KEYS, f"{name}: kind {kind} takes no llm block")
            for key in llm:
                require(key in C.LLM_KEYS[kind], f"{name}: llm key {key!r} is not valid for {kind}")
            roles = llm.get("roles", [])
            bad = [role for role in roles if role not in tables["roles"]]
            require(not bad, f"{name}: unknown roles {bad}")
            require(len(set(roles)) == len(roles), f"{name}: duplicate roles")
            calls = llm.get("max_calls")
            require(isinstance(calls, int) and calls >= 0
                    or (calls == C.UNLIMITED and "llm.max_calls" in needs),
                    f"{name}: max_calls must be a whole number, or {C.UNLIMITED!r} with a session named")
        if "hunter" in arm and "hunter" not in needs:
            require(arm["hunter"] in tables["hunter"], f"{name}: hunter {arm['hunter']!r}")
        if "freeze" in arm:
            require(arm["freeze"] in tables["freeze"], f"{name}: freeze {arm['freeze']!r}")
            if llm is not None:
                extra = [r for r in llm.get("roles", []) if r not in tables["frozen_roles"]]
                require(not extra, f"{name}: a frozen arm may not turn on {extra}")
    full_roles = list(arms["full"]["llm"]["roles"])
    require(sorted(full_roles) == sorted(tables["roles"]), "full: must turn on every LLM role")
    for name, dropped in C.LEAVE_ONE_OUT.items():
        roles = arms[name]["llm"]["roles"]
        require(sorted(roles) == sorted(r for r in full_roles if r != dropped),
                f"{name}: must be full without {dropped}")
    require(sorted(arms[C.NO_TRANSLATOR]["llm"]["roles"]) == sorted(r for r in full_roles if r != "translator"),
            f"{C.NO_TRANSLATOR}: must be full without translator")
    require(sorted(arms[C.MULTI_ENGINE_FULL]["llm"]["roles"]) == sorted(full_roles),
            f"{C.MULTI_ENGINE_FULL}: must turn on every role")
    return f"{len(arms)} arms valid against grid.py or named sessions; ablations drop the stated roles"


def check_engines() -> str:
    data, tables = spec(), grid_tables()
    sessions = session_headings()
    engines: dict[str, Any] = data["engines"]
    for name, engine in engines.items():
        role, session = engine.get("role"), engine.get("session")
        require(role in ("target", "reference"), f"engine {name}: role {role!r}")
        if session is None:
            known = tables["targets"] if role == "target" else tables["references"]
            require(name in known, f"engine {name}: not a {role} today and no session named")
        else:
            require(session in sessions, f"engine {name}: session {session!r} has no section in SESSIONS.md")
    by_id = {m["id"]: m for m in data["milestones"]}
    checked = 0
    for milestone in data["milestones"]:
        closure = requires_closure(milestone, by_id)
        for group in milestone["groups"]:
            for engine_set in group["engine_sets"]:
                for engine in engine_set:
                    require(engine in engines and engines[engine]["role"] == "target",
                            f"{milestone['id']}: {engine} is not a target engine in the spec")
                    session = engines[engine]["session"]
                    require(session is None or session in closure,
                            f"{milestone['id']}: {engine} needs {session}, not among its prerequisites")
                for arm_name in group["arms"]:
                    arm = data["arms"][arm_name]
                    if arm["kind"] in C.SINGLE_ENGINE_KINDS:
                        require(len(engine_set) == 1,
                                f"{milestone['id']}: {arm_name} ({arm['kind']}) runs on one engine per cell")
                    for key, session in arm.get("needs", {}).items():
                        require(session in closure,
                                f"{milestone['id']}: {arm_name} needs {session} for {key!r}, not a prerequisite")
                    checked += 1
    return f"{len(engines)} engines; {checked} milestone arm placements have their prerequisites"


def check_cells() -> str:
    data = spec()
    seeds = len(data["seeds"]["formal"])
    cell_hours = data["hours"]["cell"]
    total_24 = total_1 = 0
    for milestone in data["milestones"]:
        got = {"cells_24h": 0, "cells_1h": 0}
        for group in milestone["groups"]:
            for arm_name in group["arms"]:
                arm = data["arms"][arm_name]
                count = len(group["engine_sets"]) * seeds * int(arm.get("pairs", 1))
                hours = int(arm.get("hours", cell_hours))
                require(hours in (cell_hours, 1), f"{arm_name}: unexpected hours {hours}")
                got["cells_24h" if hours == cell_hours else "cells_1h"] += count
        for key, value in got.items():
            require(milestone.get(key) == value,
                    f"{milestone['id']}: {key} declared {milestone.get(key)}, spec adds up to {value}")
        total_24 += got["cells_24h"]
        total_1 += got["cells_1h"]
    require(data["totals"] == {"cells_24h": total_24, "cells_1h": total_1},
            f"totals declared {data['totals']}, milestones add up to {total_24} x 24h + {total_1} x 1h")
    return f"{len(data['milestones'])} milestones; {total_24} cells of 24h and {total_1} of 1h, as declared"


def check_seeds() -> str:
    data = spec()
    formal, pilot = list(data["seeds"]["formal"]), list(data["seeds"]["pilot"])
    require(all(isinstance(s, int) for s in formal + pilot), "seeds must be integers")
    require(len(set(formal)) == len(formal) == 5, f"formal seeds: five distinct, got {formal}")
    require(len(set(pilot)) == len(pilot) >= 1, f"pilot seeds: distinct, got {pilot}")
    require(not set(formal) & set(pilot), "formal and pilot seeds overlap")
    lines = git("grep", "-h", "-i", "-E", "seed", C.BASE_TAG, "--", *C.SEED_SCAN_PATHS).splitlines()
    used: set[int] = set()
    for line in lines:
        for match in re.finditer(r"(?i)seed", line):
            window = line[match.end(): match.end() + C.SEED_WINDOW]
            used.update(int(n) for n in re.findall(r"\b\d+\b", window))
    clash = sorted((set(formal) | set(pilot)) & used)
    require(not clash, f"seeds already used at {C.BASE_TAG}: {clash}")
    return f"formal {formal}, pilot {pilot}; none among {len(used)} numbers near 'seed' at {C.BASE_TAG}"


def check_sessions() -> str:
    data = spec()
    sessions = session_headings()
    expected = {f"S{n}" for n in range(C.FIRST_SESSION, C.LAST_SESSION + 1)}
    require(expected <= sessions, f"SESSIONS.md lacks sections {sorted(expected - sessions)}")
    order = [m["id"] for m in data["milestones"]]
    last_run = 0
    for index, milestone in enumerate(data["milestones"]):
        run = milestone["run_session"]
        require(run in sessions, f"{milestone['id']}: run session {run} has no section")
        number = int(run[1:])
        require(number > last_run, f"{milestone['id']}: run sessions must increase with the milestones")
        last_run = number
        for item in milestone["requires"]:
            if SESSION_RE.match(item):
                require(item in sessions, f"{milestone['id']}: prerequisite {item} has no section")
                require(int(item[1:]) < number, f"{milestone['id']}: prerequisite {item} comes after {run}")
            else:
                require(item in order[:index], f"{milestone['id']}: prerequisite {item} is not an earlier milestone")
    require(re.search(rf"^{re.escape(C.PLAN_SECTION)}", read(C.PLAN), re.M) is not None,
            f"PLAN.md has no heading {C.PLAN_SECTION!r}")
    require(any(line.startswith(C.HANDOFF_ROW) for line in read(C.HANDOFF).splitlines()),
            "HANDOFF.md status table has no S13 row")
    return f"SESSIONS.md has S{C.FIRST_SESSION}-S{C.LAST_SESSION}; {len(order)} milestones ordered; PLAN section 9 and HANDOFF row present"


GROUPS = {
    "scope": check_scope,
    "sections": check_sections,
    "arms": check_arms,
    "engines": check_engines,
    "cells": check_cells,
    "seeds": check_seeds,
    "sessions": check_sessions,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S13 gate (formal experiment protocol)")
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
    print(f"S13 GATE{scope}: {'PASS' if not failed else 'FAIL'}"
          f" ({len(selected) - failed}/{len(selected)} groups passed)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
