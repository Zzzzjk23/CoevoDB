"""Main loop: Hunter, CVE, surprise, Diagnoser, accept or roll back.

One run writes ``config.json``, ``ledger.sqlite``, ``theory/``, ``progress.jsonl``
and ``report.json`` under ``--out``. The same arguments and seed produce the same
experiments, labels and theory; only the wall-clock fields differ.

LLM roles are off unless ``--llm`` is set. With every role off the files above
match a run that has no role code loaded.

    python -m surprise.experiments.loop --out DIR --seed N
        [--engine E]... [--oracle O]...
        [--max-experiments N] [--max-minutes M]
        [--beta B] [--bootstrap FILE] [--run-id ID]
        [--llm ROLE]... [--llm-cache DIR] [--llm-max-calls N] [--llm-offline]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from surprise.diagnoser import Diagnoser
from surprise.diagnoser import constants as diagnoser_constants
from surprise.features.registry import default_registry
from surprise.harness.contracts import ORACLE_IDS, SqlCase
from surprise.harness.evaluate import evaluate_final
from surprise.harness.ledger import Ledger
from surprise.harness.manifest import build_manifest
from surprise.hunter import Hunter
from surprise.hunter.operators import case_digest
from surprise.metrics.curve import surprise_curve, teeth
from surprise.metrics.dups import new_families
from surprise.theory import attribution_request, extend_manifest
from surprise.theory.constants import BETA

_FRAMEWORK = Path(__file__).resolve().parents[2]
_CODE_DIRS = ("surprise/hunter", "surprise/diagnoser", "surprise/experiments")
_LLM_ROLES = ("implementer", "conjecturer")
_LLM_KEYS = ("roles", "cache", "max_calls", "network", "transport")
_PROGRESS_KEYS = (
    "seq",
    "record_id",
    "index",
    "slot",
    "lane",
    "oracle",
    "rule",
    "case_digest",
    "hypothesis",
    "parent",
    "op",
    "target",
    "zone",
    "predicted",
    "p_fail_valid",
    "p_invalid",
    "D",
    "U",
    "adjacent",
    "probes",
    "value",
    "y",
    "kind",
    "surprise",
    "triage",
    "opened",
    "owner",
    "rolled_back",
    "bets",
    "edits",
    "pool",
    "theory_version",
    "elapsed_s",
)


class UsageError(ValueError):
    """The arguments of ``run`` or the command line cannot start a run."""


def code_digests() -> dict[str, str]:
    """sha256 of every .py file the loop runs, with CRLF read as LF, keyed by path relative to framework/."""
    digests: dict[str, str] = {}
    for folder in _CODE_DIRS:
        for path in sorted((_FRAMEWORK / folder).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            blob = path.read_bytes().replace(b"\r\n", b"\n")
            digests[path.relative_to(_FRAMEWORK).as_posix()] = hashlib.sha256(blob).hexdigest()
    return digests


def _build_roles(config, *, run_dir, extract, registry, engines, seed):
    from surprise.roles.runtime import build_roles  # imported here, never at module level

    return build_roles(
        config,
        run_dir=run_dir,
        extract=extract,
        registry=registry,
        engines=engines,
        seed=seed,
    )


def run(
    out,
    *,
    seed,
    engines: Sequence[str] = ("duckdb",),
    oracles: Sequence[str] = ORACLE_IDS,
    max_experiments: int | None = None,
    max_minutes: float | None = None,
    beta: float | None = None,
    bootstrap: Sequence[dict] = (),
    run_id: str | None = None,
    echo: bool = False,
    llm=None,
) -> dict[str, Any]:
    """Run the loop into ``out`` and return the report. ``echo`` prints one ASCII line per experiment.

    ``echo`` is for the command line. A library caller leaves it false.
    ``llm`` is None, or a dict that turns on a subset of the LLM roles.
    """
    seed = _require_int(seed, "seed")
    engines = _strings(engines, "engines")
    oracles = _strings(oracles, "oracles", allowed=ORACLE_IDS)
    max_experiments = _optional_whole(max_experiments, "max_experiments")
    max_minutes = _optional_minutes(max_minutes)
    if max_experiments is None and max_minutes is None:
        raise UsageError("set max_experiments or max_minutes")
    used_beta = _resolve_beta(beta)
    items = _normalise_bootstrap(bootstrap)
    if run_id is None:
        run_id = f"loop-s{seed}"
    elif not isinstance(run_id, str) or run_id == "":
        raise UsageError(f"run_id: expected a non-empty string, got {run_id!r}")
    llm_config = _normalise_llm(llm)

    directory = Path(out)
    _ensure_out(directory)
    started_at = datetime.now(timezone.utc)
    state = _State(
        directory=directory,
        seed=seed,
        engines=engines,
        oracles=oracles,
        max_experiments=max_experiments,
        max_minutes=max_minutes,
        beta=used_beta,
        bootstrap=items,
        run_id=run_id,
        started_at=started_at,
        echo=echo,
        llm=llm_config,
    )
    pending: BaseException | None = None
    try:
        try:
            _prepare(state)
            _drive(state)
        except KeyboardInterrupt as exc:
            state.status = "interrupted"
            pending = exc
        except Exception as exc:
            state.status = "error"
            state.exc = exc
            pending = exc
        state.report = _write_report(state)
    finally:
        _close(state)
    if pending is not None:
        raise pending
    return state.report


def main(argv: list[str] | None = None) -> int:
    """Command line. Returns 0, 2 for bad arguments, 1 for a run that raised, 130 for an interrupt."""
    parser = argparse.ArgumentParser(description="Hunter loop, with optional LLM roles")
    parser.add_argument("--out", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--engine", action="append", default=None, dest="engines")
    parser.add_argument("--oracle", action="append", default=None, dest="oracles")
    parser.add_argument("--max-experiments", type=int, default=None)
    parser.add_argument("--max-minutes", type=float, default=None)
    parser.add_argument("--beta", type=float, default=None)
    parser.add_argument("--bootstrap", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--llm",
        action="append",
        default=None,
        choices=_LLM_ROLES,
        dest="llm_roles",
        help="turn on one LLM role (repeatable)",
    )
    parser.add_argument("--llm-cache", default=None, help="directory for the role response cache")
    parser.add_argument("--llm-max-calls", type=int, default=None, help="cap on role calls")
    parser.add_argument("--llm-offline", action="store_true", help="answer roles from the cache only")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) else 2
    try:
        loaded = () if args.bootstrap is None else _read_bootstrap_file(args.bootstrap)
        report = run(
            args.out,
            seed=args.seed,
            engines=tuple(args.engines) if args.engines else ("duckdb",),
            oracles=tuple(args.oracles) if args.oracles else ORACLE_IDS,
            max_experiments=args.max_experiments,
            max_minutes=args.max_minutes,
            beta=args.beta,
            bootstrap=loaded,
            run_id=args.run_id,
            echo=True,
            llm=_llm_from_args(args),
        )
    except UsageError as exc:
        print(f"error: {_ascii(exc)}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        _print_saved_summary(args.out)
        return 130
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {_ascii(exc)}", file=sys.stderr)
        _print_saved_summary(args.out)
        return 1
    print(f"{report['status']} {report['experiments']}", flush=True)
    return 0


class _State:
    """Mutable bookkeeping for one run. The theory and the ledger stay on this object."""

    def __init__(
        self,
        *,
        directory: Path,
        seed: int,
        engines: tuple[str, ...],
        oracles: tuple[str, ...],
        max_experiments: int | None,
        max_minutes: float | None,
        beta: float,
        bootstrap: tuple[dict, ...],
        run_id: str,
        started_at: datetime,
        echo: bool,
        llm: dict[str, Any] | None = None,
    ) -> None:
        self.directory = directory
        self.seed = seed
        self.engines = engines
        self.oracles = oracles
        self.max_experiments = max_experiments
        self.max_minutes = max_minutes
        self.beta = beta
        self.bootstrap = bootstrap
        self.run_id = run_id
        self.started_at = started_at
        self.echo = echo
        self.llm = llm
        self.roles = None
        self.status = "error"
        self.exc: BaseException | None = None
        self.choices = 0
        self.done = 0
        self.rows: list[dict[str, Any]] = []
        self.extractor = None
        self.hunter = None
        self.diagnoser = None
        self.wb = None
        self.ledger = None
        self.progress = None
        self.run_started = False
        self.report: dict[str, Any] | None = None


class _Step:
    """One experiment, bootstrap or chosen, before it is executed."""

    def __init__(
        self,
        *,
        case: SqlCase,
        oracle: str,
        rule: str | None,
        phi,
        prediction,
        lane: str,
        slot: str,
        index: int,
        hypothesis: str | None,
        parent: str | None,
        op: str,
        target: dict | None,
        value: float | None,
        disagreement: float | None,
        uncertainty: float | None,
        adjacent: bool | None,
        probes: int | None,
        pool: dict[str, int],
    ) -> None:
        self.case = case
        self.oracle = oracle
        self.rule = rule
        self.phi = phi
        self.prediction = prediction
        self.lane = lane
        self.slot = slot
        self.index = index
        self.hypothesis = hypothesis
        self.parent = parent
        self.op = op
        self.target = target
        self.value = value
        self.disagreement = disagreement
        self.uncertainty = uncertainty
        self.adjacent = adjacent
        self.probes = probes
        self.pool = pool


def _prepare(state: _State) -> None:
    _write_json(state.directory / "config.json", _config(state))
    state.extractor = _open_extractor()
    sources = ()
    if state.llm is not None:
        state.roles = _build_roles(
            state.llm,
            run_dir=state.directory,
            extract=state.extractor.extract,
            registry=default_registry(),
            engines=state.engines,
            seed=state.seed,
        )
        sources = tuple(state.roles.sources)
    state.hunter = Hunter(
        engines=state.engines,
        oracles=state.oracles,
        seed=state.seed,
        beta=state.beta,
        extractor=state.extractor,
        sources=sources,
    )
    registry = default_registry()
    state.diagnoser = Diagnoser(phi=state.hunter.phi, registry=registry)
    state.wb = _open_workbench(state.directory / "theory")
    state.ledger = Ledger(state.directory / "ledger.sqlite")
    manifest = extend_manifest(build_manifest(state.run_id))
    manifest["hunter"] = {
        **state.hunter.manifest(),
        "diagnoser": diagnoser_constants.as_dict(),
        "code": code_digests(),
    }
    if state.roles is not None:
        manifest["llm"] = state.roles.manifest()
    state.ledger.start_run(state.run_id, manifest)
    state.run_started = True
    state.progress = (state.directory / "progress.jsonl").open("w", encoding="utf-8", newline="\n")


def _open_extractor():
    from surprise.hunter import PhiExtractor

    return PhiExtractor()


def _open_workbench(root: Path):
    from surprise.theory import Workbench

    return Workbench.create(root)


def _drive(state: _State) -> None:
    for item in state.bootstrap:
        _execute(state, _bootstrap_step(state, item))
    while True:
        if state.max_experiments is not None and state.choices >= state.max_experiments:
            state.status = "budget_experiments"
            return
        if state.max_minutes is not None and _wall_s(state) >= state.max_minutes * 60.0:
            state.status = "budget_minutes"
            return
        choice = state.hunter.choose(state.wb)
        if choice is None:
            state.status = "exhausted"
            return
        state.choices += 1
        _execute(state, _choice_step(choice))


def _bootstrap_step(state: _State, item: dict) -> _Step:
    case = SqlCase.from_dict(item["case"])
    oracle = item["oracle"]
    rule = item["rule"]
    example = state.hunter.phi(case)
    prediction = state.wb.predict(example, oracle)
    return _Step(
        case=case,
        oracle=oracle,
        rule=rule,
        phi=example,
        prediction=prediction,
        lane="bootstrap",
        slot="bootstrap",
        index=0,
        hypothesis=None,
        parent=None,
        op="bootstrap",
        target=None,
        value=None,
        disagreement=None,
        uncertainty=None,
        adjacent=None,
        probes=None,
        pool={},
    )


def _choice_step(choice) -> _Step:
    scored = choice.scored
    candidate = scored.candidate
    return _Step(
        case=candidate.case,
        oracle=candidate.oracle,
        rule=candidate.rule,
        phi=scored.phi,
        prediction=scored.prediction,
        lane=candidate.lane,
        slot=choice.slot,
        index=choice.index,
        hypothesis=candidate.hypothesis_id,
        parent=candidate.parent,
        op=candidate.op,
        target=candidate.target,
        value=scored.value,
        disagreement=scored.D,
        uncertainty=scored.U,
        adjacent=scored.adjacent,
        probes=scored.probes,
        pool=dict(choice.pool),
    )


def _execute(state: _State, step: _Step) -> None:
    state.done += 1
    if step.prediction.hypothesis_id is None:
        options: dict[str, Any] = {"diagnose": True}
    else:
        options = {
            "hypothesis": attribution_request(state.wb.theory.get(step.prediction.hypothesis_id))
        }
    spec = {
        "lane": step.lane,
        "slot": step.slot,
        "index": step.index,
        "hypothesis": step.hypothesis,
        "parent": step.parent,
        "op": step.op,
        "target": step.target,
        "rule": step.rule,
        "zone": step.prediction.zone,
        "value": step.value,
        "D": step.disagreement,
        "U": step.uncertainty,
        "adjacent": step.adjacent,
        "probes": step.probes,
    }
    record = evaluate_final(
        step.case,
        step.oracle,
        ledger=state.ledger,
        run_id=state.run_id,
        purpose=step.lane,
        spec=spec,
        phi=step.phi.to_dict(),
        theory_version=state.wb.theory.version,
        p_t=step.prediction.p_fail_valid,
        rewrite_rule=step.rule,
        **options,
    )
    outcome = state.wb.observe(step.phi, record.label, record.record_id, prediction=step.prediction)
    state.hunter.record(record, rule=step.rule, prediction=step.prediction)
    edits = state.diagnoser.after(state.wb, record, outcome) + state.diagnoser.periodic(
        state.wb, state.done
    )
    # Roles see the experiment only after the Diagnoser has revised.
    if state.roles is not None:
        state.roles.observe(step.phi, record.label, record.record_id)
        state.roles.after(state.wb, record, outcome)
    row = _progress_row(state, step, record, outcome, edits)
    state.rows.append(row)
    state.progress.write(json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n")
    state.progress.flush()
    if state.echo:
        print(_brief(row), flush=True)


def _progress_row(state: _State, step: _Step, record, outcome, edits) -> dict[str, Any]:
    label = record.label
    if label.y == "fail":
        kind = label.fail_kind
    elif label.y == "invalid":
        kind = label.invalid_reason
    else:
        kind = None
    row = {
        "seq": record.seq,
        "record_id": record.record_id,
        "index": step.index,
        "slot": step.slot,
        "lane": step.lane,
        "oracle": step.oracle,
        "rule": step.rule,
        "case_digest": case_digest(step.case),
        "hypothesis": step.hypothesis,
        "parent": step.parent,
        "op": step.op,
        "target": step.target,
        "zone": step.prediction.zone,
        "predicted": step.prediction.hypothesis_id,
        "p_fail_valid": step.prediction.p_fail_valid,
        "p_invalid": step.prediction.p_invalid,
        "D": step.disagreement,
        "U": step.uncertainty,
        "adjacent": step.adjacent,
        "probes": step.probes,
        "value": step.value,
        "y": label.y,
        "kind": kind,
        "surprise": outcome.observation.surprise,
        "triage": outcome.observation.triage,
        "opened": outcome.observation.opened,
        "owner": outcome.owner,
        "rolled_back": list(outcome.rolled_back),
        "bets": [list(item) for item in outcome.bets],
        "edits": [
            {
                "edit_id": edit.edit_id,
                "kind": edit.kind,
                "proposer": edit.proposer,
                "decision": edit.decision,
                "reason": edit.payload.get("reason"),
            }
            for edit in edits
        ],
        "pool": step.pool,
        "theory_version": state.wb.theory.version,
        "elapsed_s": float(f"{_wall_s(state):.2f}"),
    }
    if tuple(row) != _PROGRESS_KEYS:
        raise RuntimeError("progress row keys drifted from the loop contract")
    if state.roles is not None:
        row["llm"] = state.roles.step()
    return row


def _write_report(state: _State) -> dict[str, Any]:
    finished_at = datetime.now(timezone.utc)
    records = _records(state)
    labels = _tally(record.label.y for record in records)
    lanes = _tally(record.purpose for record in records)
    triage = _tally(row["triage"] for row in state.rows)
    curve = surprise_curve(records, 100)
    report: dict[str, Any] = {
        "run_id": state.run_id,
        "seed": state.seed,
        "engines": list(state.engines),
        "oracles": list(state.oracles),
        "beta": state.beta,
        "status": state.status,
        "experiments": len(records),
        "choices": state.choices,
        "started_at": state.started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "wall_s": (finished_at - state.started_at).total_seconds(),
        "labels": labels,
        "lanes": lanes,
        "triage": triage,
        "hypotheses": 0 if state.wb is None else len(state.wb.theory.hypotheses),
        "families": 0 if state.wb is None else len(state.wb.families()),
        "edits": _edit_tally(state),
        "curve": curve,
        "teeth": teeth(curve),
        "new_families": _new_family_count(state.directory / "theory"),
        "extractor": {} if state.extractor is None else state.extractor.stats,
    }
    if state.status == "error":
        exc = state.exc
        report["error"] = {
            "type": type(exc).__name__ if exc is not None else "Exception",
            "message": "" if exc is None else str(exc),
        }
    if state.roles is not None:
        report["llm"] = state.roles.report()
    _write_json(state.directory / "report.json", report)
    return report


def _records(state: _State) -> list:
    if state.ledger is None or not state.run_started:
        return []
    return state.ledger.records(run_id=state.run_id)


def _edit_tally(state: _State) -> dict[str, int]:
    """Count each edit by its latest state.

    A refused proposal is stored with decision ``rolled_back`` and no rollback
    record. The report calls that rejected. An edit that was accepted and later
    undone carries ``payload["rollback"]`` and counts as rolled back.
    """
    counts = {"accepted": 0, "rejected": 0, "rolled_back": 0}
    if state.wb is None:
        return counts
    for edit in state.wb.edits():
        if edit.decision == "accepted":
            counts["accepted"] += 1
        elif edit.payload.get("rollback"):
            counts["rolled_back"] += 1
        else:
            counts["rejected"] += 1
    return counts


def _new_family_count(theory: Path) -> int:
    if not (theory / "head.json").is_file():
        return 0
    return len(new_families(theory))


def _config(state: _State) -> dict[str, Any]:
    payload = {
        "seed": state.seed,
        "engines": list(state.engines),
        "oracles": list(state.oracles),
        "max_experiments": state.max_experiments,
        "max_minutes": state.max_minutes,
        "beta": state.beta,
        "bootstrap": [dict(item) for item in state.bootstrap],
        "run_id": state.run_id,
    }
    if state.llm is not None:
        payload["llm"] = _llm_public(state.llm)
    return payload


def _close(state: _State) -> None:
    """Close the progress file, the roles, the phi worker and the ledger. The first failure is re-raised."""
    first: Exception | None = None
    if state.progress is not None:
        try:
            state.progress.close()
        except Exception as exc:
            first = exc
        state.progress = None
    if state.roles is not None:
        try:
            state.roles.close()
        except Exception as exc:
            if first is None:
                first = exc
        state.roles = None
    if state.extractor is not None:
        try:
            state.extractor.close()
        except Exception as exc:
            if first is None:
                first = exc
        state.extractor = None
    if state.ledger is not None:
        try:
            state.ledger.close()
        except Exception as exc:
            if first is None:
                first = exc
        state.ledger = None
    if first is not None:
        raise first


def _wall_s(state: _State) -> float:
    return (datetime.now(timezone.utc) - state.started_at).total_seconds()


def _tally(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _brief(row: dict[str, Any]) -> str:
    surprise = row["surprise"]
    shown = "-" if surprise is None else f"{surprise:.2f}"
    return f"{row['seq']} {row['lane']} {row['oracle']} {row['y']} {shown} {row['triage']}"


def _print_saved_summary(out) -> None:
    path = Path(out) / "report.json"
    if not path.is_file():
        return
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return
    if "status" in report and "experiments" in report:
        print(f"{report['status']} {report['experiments']}", flush=True)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _ascii(text: object) -> str:
    return str(text).encode("ascii", "backslashreplace").decode("ascii")


def _ensure_out(path: Path) -> None:
    if path.exists():
        if not path.is_dir():
            raise UsageError(f"out is not a directory: {path}")
        if any(path.iterdir()):
            raise UsageError(f"out directory is not empty: {path}")
    else:
        path.mkdir(parents=True)


def _require_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise UsageError(f"{name}: expected an integer, got {value!r}")
    return value


def _optional_whole(value: object, name: str) -> int | None:
    if value is None:
        return None
    number = _require_int(value, name)
    if number < 0:
        raise UsageError(f"{name}: expected an integer >= 0, got {value!r}")
    return number


def _optional_minutes(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UsageError(f"max_minutes: expected a number >= 0, got {value!r}")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise UsageError(f"max_minutes: expected a number >= 0, got {value!r}")
    return number


def _resolve_beta(beta: object) -> float:
    if beta is None:
        return float(BETA)
    if isinstance(beta, bool) or not isinstance(beta, (int, float)):
        raise UsageError(f"beta: expected a number > 0, got {beta!r}")
    number = float(beta)
    if not math.isfinite(number) or number <= 0:
        raise UsageError(f"beta: expected a number > 0, got {beta!r}")
    return number


def _normalise_llm(llm: object) -> dict[str, Any] | None:
    """Check a role switch. None leaves the loop exactly as it is without roles."""
    if llm is None:
        return None
    if not isinstance(llm, dict):
        raise UsageError(f"llm: expected a dict, got {type(llm).__name__}")
    unknown = sorted(str(key) for key in llm if key not in _LLM_KEYS)
    if unknown:
        raise UsageError(f"llm: unknown keys {unknown}")
    missing = [name for name in ("roles", "cache") if name not in llm]
    if missing:
        raise UsageError(f"llm: missing {', '.join(missing)}")
    roles = llm["roles"]
    if isinstance(roles, str) or not isinstance(roles, (list, tuple)) or len(roles) == 0:
        raise UsageError(
            "llm: roles must be a non-empty list or tuple drawn from "
            f"{', '.join(_LLM_ROLES)}, got {roles!r}"
        )
    seen: set[str] = set()
    for role in roles:
        if not isinstance(role, str) or role not in _LLM_ROLES:
            raise UsageError(f"llm: unknown role {role!r}")
        if role in seen:
            raise UsageError(f"llm: duplicate role {role!r}")
        seen.add(role)
    cache = llm["cache"]
    if not isinstance(cache, str) or cache == "":
        raise UsageError(f"llm: cache must be a non-empty string, got {cache!r}")
    if "max_calls" in llm:
        max_calls = llm["max_calls"]
    else:
        max_calls = None
    if max_calls is not None and (isinstance(max_calls, bool) or not isinstance(max_calls, int) or max_calls < 0):
        raise UsageError(f"llm: max_calls must be an integer >= 0 or null, got {max_calls!r}")
    if "network" in llm:
        network = llm["network"]
        if not isinstance(network, bool):
            raise UsageError(f"llm: network must be a bool, got {network!r}")
    else:
        network = True
    config: dict[str, Any] = {
        "roles": list(roles),
        "cache": cache,
        "max_calls": max_calls,
        "network": network,
    }
    if "transport" in llm:
        config["transport"] = llm["transport"]
    return config


def _llm_public(llm: dict[str, Any]) -> dict[str, Any]:
    """The role switch as stored in config.json. ``transport`` stays in the process."""
    return {
        "roles": list(llm["roles"]),
        "cache": llm["cache"],
        "max_calls": llm["max_calls"],
        "network": llm["network"],
    }


def _llm_from_args(args: argparse.Namespace) -> dict[str, Any] | None:
    roles = args.llm_roles
    cache = args.llm_cache
    max_calls = args.llm_max_calls
    offline = args.llm_offline
    if roles:
        if not isinstance(cache, str) or cache == "":
            raise UsageError("--llm requires --llm-cache")
        return {
            "roles": list(roles),
            "cache": cache,
            "max_calls": max_calls,
            "network": not offline,
        }
    if cache is not None or max_calls is not None or offline:
        raise UsageError("--llm-cache, --llm-max-calls and --llm-offline require --llm")
    return None


def _strings(value: object, name: str, *, allowed: Sequence[str] | None = None) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence) or len(value) == 0:
        raise UsageError(f"{name}: expected a non-empty sequence of strings, got {value!r}")
    items = tuple(value)
    for item in items:
        if not isinstance(item, str) or item == "":
            raise UsageError(f"{name}: expected non-empty strings, got {item!r}")
        if allowed is not None and item not in allowed:
            raise UsageError(f"{name}: unknown {item!r}")
    return items


def _normalise_bootstrap(bootstrap: object) -> tuple[dict, ...]:
    if bootstrap is None:
        return ()
    if isinstance(bootstrap, (str, bytes)) or not isinstance(bootstrap, Sequence):
        raise UsageError(f"bootstrap: expected a sequence of objects, got {type(bootstrap).__name__}")
    items: list[dict] = []
    for index, item in enumerate(bootstrap):
        if not isinstance(item, dict):
            raise UsageError(f"bootstrap[{index}]: expected an object")
        unknown = sorted(set(item) - {"case", "oracle", "rule"})
        if unknown or {"case", "oracle", "rule"} - set(item):
            raise UsageError(f"bootstrap[{index}]: keys must be case, oracle, rule")
        try:
            case = SqlCase.from_dict(item["case"])
        except (TypeError, ValueError) as exc:
            raise UsageError(f"bootstrap[{index}]: case is not a SqlCase") from exc
        oracle = item["oracle"]
        rule = item["rule"]
        if not isinstance(oracle, str) or oracle not in ORACLE_IDS:
            raise UsageError(f"bootstrap[{index}]: unknown oracle {oracle!r}")
        if rule is not None and (not isinstance(rule, str) or rule == ""):
            raise UsageError(f"bootstrap[{index}]: rule must be a string or null")
        items.append({"case": case.to_dict(), "oracle": oracle, "rule": rule})
    return tuple(items)


def _read_bootstrap_file(path: str) -> list:
    file = Path(path)
    if not file.is_file():
        raise UsageError(f"bootstrap file does not exist: {file}")
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise UsageError("bootstrap file is not JSON") from exc
    if not isinstance(data, list):
        raise UsageError("bootstrap file must contain a JSON list")
    return data


if __name__ == "__main__":
    sys.exit(main())
