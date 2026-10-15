"""Pure-LLM baseline: the model writes SQL, and the harness labels it.

No theory and no surprise score. Each batch asks the gateway for cases on one
topic, drops cases that are not executable, and sends the rest through
``evaluate_final`` with the same oracles and CVE path as the other arms.
The model's ``expect`` is stored on the record and does not become the label.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import random
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from surprise.harness.contracts import ORACLE_IDS, SqlCase
from surprise.harness.evaluate import evaluate_final
from surprise.harness.ledger import Ledger
from surprise.harness.manifest import build_manifest
from surprise.harness.oracles.registry import TARGET_ENGINES
from surprise.hunter.extractor import PhiExtractor
from surprise.roles.gateway import Gateway

# fast tier; reasoning tokens on deepseek-flash count toward max_tokens, and
# 8000 truncated real replies in S9/S10.
PURE_LLM_TIER = "fast"
PURE_LLM_TEMPERATURE = 0.8
PURE_LLM_MAX_TOKENS = 16000
PURE_LLM_CASES_PER_CALL = 8
PURE_LLM_TOPICS = (
    "set operations with ALL",
    "window functions with PARTITION BY and frames",
    "outer joins and NULL handling",
    "correlated subqueries",
    "GROUP BY with aggregates and HAVING",
    "CTEs and recursive CTEs",
    "type casts and numeric edge values",
    "string functions and collations",
    "ORDER BY, LIMIT and OFFSET",
    "DATE and TIMESTAMP arithmetic",
)

# One sentence each: what the oracle decides, and what a case must look like.
_ORACLE_TEXT = {
    "tlp": (
        "Ternary logic partitioning checks that predicate p, NOT p, and p IS NULL "
        "together rebuild the unfiltered rows, so put p only in predicate and keep "
        "WHERE out of query (plain SELECT-FROM, or GROUP BY / DISTINCT when the WHERE form does not apply)."
    ),
    "norec": (
        "NoREC checks that COUNT(*) WHERE p equals SUM(CASE WHEN p THEN 1 ELSE 0 END), "
        "so put p only in predicate, keep WHERE out of query, and use a FROM clause "
        "without GROUP BY, HAVING, LIMIT, OFFSET, FETCH, set operations, QUALIFY, or WINDOW."
    ),
    "plan_variant": (
        "Plan variant checks that one deterministic read-only statement returns the same "
        "rows under different planner settings; an optional predicate is inserted as the top-level WHERE."
    ),
    "index_presence": (
        "Index presence (DuckDB only) checks that a read-only SELECT over a base table "
        "created in setup returns the same rows with and without a secondary ART index; "
        "an optional predicate is inserted as the top-level WHERE."
    ),
    "equivalent_query": (
        "Equivalent query rewrites the statement with the frozen double-negation rule, "
        "wrapping the whole top-level WHERE predicate p as NOT (NOT (p)), so write a "
        "read-only SELECT whose WHERE is that p (in query, or in predicate so it is inserted)."
    ),
    "version_differential": (
        "Version differential runs the same statement on the current engine and an older "
        "build (DuckDB 1.1.3 or DataFusion 50.0.0) and needs SQL both versions accept; "
        "an optional predicate is inserted as the top-level WHERE."
    ),
    "cross_dbms": (
        "Cross-DBMS runs one statement as the same SQL on DuckDB, DataFusion, SQLite, and "
        "PostgreSQL and treats the target as a bug only when it is the only engine that "
        "disagrees; an optional predicate is inserted as the top-level WHERE."
    ),
}

if set(_ORACLE_TEXT) != set(ORACLE_IDS):
    raise RuntimeError("pure_llm oracle text does not match ORACLE_IDS")


class UsageError(ValueError):
    """The arguments of ``run`` or the command line cannot start a run."""


class _Run:
    """Mutable bookkeeping for one pure-LLM run."""

    def __init__(
        self,
        *,
        directory: Path,
        seed: int,
        engine: str,
        oracles: tuple[str, ...],
        max_experiments: int | None,
        max_minutes: float | None,
        max_calls: int | None,
        offline: bool,
        cache_dir: Path,
        run_id: str,
        started_at: datetime,
        started_mono: float,
    ) -> None:
        self.directory = directory
        self.seed = seed
        self.engine = engine
        self.oracles = oracles
        self.max_experiments = max_experiments
        self.max_minutes = max_minutes
        self.max_calls = max_calls
        self.offline = offline
        self.cache_dir = cache_dir
        self.run_id = run_id
        self.started_at = started_at
        self.started_mono = started_mono
        self.engine_version = _engine_version(engine)
        self.status = "error"
        self.exc: BaseException | None = None
        self.error_text = ""
        self.calls = 0
        self.done = 0
        self.rng = random.Random(seed)
        self.gateway: Gateway | None = None
        self.extractor: PhiExtractor | None = None
        self.ledger: Ledger | None = None
        self.progress = None
        self.book = None
        self.run_started = False
        self.report: dict[str, Any] | None = None


def _monotonic() -> float:
    """Wall clock for the budget. Tests replace this; the stdlib clock stays put."""
    return time.monotonic()


def _engine_version(engine: str) -> str:
    """Installed distribution version.

    Do not import the engine. A checkout directory of the same name can shadow
    the package and report a version the harness is not running.
    """
    try:
        found = importlib.metadata.version(engine)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"
    if not isinstance(found, str) or not found.strip():
        return "unknown"
    return found


def _prompt(state: _Run, *, topic: str, batch: int) -> str:
    """One batch's prompt. It depends only on the seed, the batch, and the engine."""
    oracles = "\n".join(f"- {name}: {_ORACLE_TEXT[name]}" for name in state.oracles)
    return (
        "Find logical bugs in a SQL database engine. You write SQL cases; a fixed harness\n"
        "runs them and assigns every label. Do not claim a result the harness did not report.\n"
        f"Target engine: {state.engine} {state.engine_version}.\n"
        "Oracles available in this run:\n"
        f"{oracles}\n"
        f"Topic for this batch: {topic}.\n"
        f"Batch: {batch}.\n"
        f"Seed: {state.seed}.\n"
        f"Return JSON with exactly {PURE_LLM_CASES_PER_CALL} cases on this topic.\n"
        "The JSON object has two fields. prediction is one non-empty sentence saying what you\n"
        "expect to find. cases is an array of objects:\n"
        '{"prediction": "<one sentence>", "cases": [{"setup": ["CREATE ...", "INSERT ..."], '
        '"query": "SELECT ...", "predicate": null, "oracle": "<oracle name>", "expect": "pass"}]}\n'
        "setup is an array of SQL strings. query is one non-empty SQL string. predicate is null\n"
        'or a boolean expression and does not include the WHERE keyword. oracle is one of the\n'
        'names above. expect is "pass" or "fail" and is only your prediction.\n'
    )


def _case_problem(item: object, allowed: tuple[str, ...]) -> str | None:
    """Why ``item`` cannot be executed, or None when it can."""
    if not isinstance(item, dict):
        return "not_object"
    setup = item.get("setup")
    if not isinstance(setup, list) or any(not isinstance(part, str) for part in setup):
        return "setup"
    query = item.get("query")
    if not isinstance(query, str) or query == "":
        return "query"
    if "predicate" in item and item["predicate"] is not None and not isinstance(item["predicate"], str):
        return "predicate"
    oracle = item.get("oracle")
    if not isinstance(oracle, str) or oracle not in allowed:
        return "oracle"
    if item.get("expect") not in ("pass", "fail"):
        return "expect"
    return None


def _partition(data: dict, allowed: tuple[str, ...]) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
    """Split a reply into executable cases and a count of the ones dropped."""
    raw = data.get("cases")
    if not isinstance(raw, list):
        return [], 1, {"cases": 1}
    accepted: list[dict[str, Any]] = []
    reasons: dict[str, int] = {}
    for index, item in enumerate(raw):
        problem = _case_problem(item, allowed)
        if problem is not None:
            reasons[problem] = reasons.get(problem, 0) + 1
            continue
        assert isinstance(item, dict)
        accepted.append(
            {
                "index": index,
                "setup": item["setup"],
                "query": item["query"],
                "predicate": item["predicate"] if "predicate" in item else None,
                "oracle": item["oracle"],
                "expect": item["expect"],
            }
        )
    return accepted, len(raw) - len(accepted), reasons


def run(
    out,
    *,
    seed,
    engine: str = "duckdb",
    oracles: tuple[str, ...] = ORACLE_IDS,
    max_experiments: int | None = None,
    max_minutes: float | None = None,
    cache=None,
    max_calls: int | None = None,
    offline: bool = False,
    run_id: str | None = None,
    transport=None,
) -> dict[str, Any]:
    """Run the pure-LLM baseline into ``out`` and return the report.

    ``transport`` is a scripted stand-in when the caller supplies one. With
    ``offline`` and no transport, the gateway answers from the cache only.
    """
    checked = _check_args(
        seed=seed,
        engine=engine,
        oracles=oracles,
        max_experiments=max_experiments,
        max_minutes=max_minutes,
        cache=cache,
        max_calls=max_calls,
        offline=offline,
        run_id=run_id,
    )
    directory = Path(out)
    _ensure_out(directory)
    cache_dir = checked["cache"] if checked["cache"] is not None else directory / "llm" / "cache"
    state = _Run(
        directory=directory,
        seed=checked["seed"],
        engine=checked["engine"],
        oracles=checked["oracles"],
        max_experiments=checked["max_experiments"],
        max_minutes=checked["max_minutes"],
        max_calls=checked["max_calls"],
        offline=checked["offline"],
        cache_dir=cache_dir,
        run_id=checked["run_id"],
        started_at=datetime.now(timezone.utc),
        started_mono=_monotonic(),
    )
    pending: BaseException | None = None
    try:
        try:
            _prepare(state, transport)
            _drive(state)
        except KeyboardInterrupt as exc:
            state.status = "interrupted"
            pending = exc
        except Exception as exc:
            state.status = "error"
            state.exc = exc
            state.error_text = traceback.format_exc()
            pending = exc
        try:
            state.report = _write_report(state)
        except Exception as exc:
            _write_error(state, extra=traceback.format_exc())
            if pending is None:
                pending = exc
        else:
            if state.error_text:
                _write_error(state, extra=None)
    finally:
        _close(state)
    if pending is not None:
        raise pending
    assert state.report is not None
    return state.report


def _check_args(
    *,
    seed: object,
    engine: object,
    oracles: object,
    max_experiments: object,
    max_minutes: object,
    cache: object,
    max_calls: object,
    offline: object,
    run_id: object,
) -> dict[str, Any]:
    seed_n = _require_int(seed, "seed")
    if not isinstance(engine, str) or engine == "":
        raise UsageError(f"engine: expected a non-empty string, got {engine!r}")
    if engine not in TARGET_ENGINES:
        raise UsageError(f"engine: unknown {engine!r}")
    oracle_names = _strings(oracles, "oracles", allowed=ORACLE_IDS)
    experiments = _optional_whole(max_experiments, "max_experiments")
    minutes = _optional_minutes(max_minutes)
    if experiments is None and minutes is None:
        raise UsageError("set max_experiments or max_minutes")
    if not isinstance(offline, bool):
        raise UsageError(f"offline: expected a bool, got {offline!r}")
    calls = _optional_whole(max_calls, "max_calls")
    cache_path = _optional_path(cache, "cache")
    if run_id is None:
        run_id = f"pure-s{seed_n}"
    elif not isinstance(run_id, str) or run_id == "":
        raise UsageError(f"run_id: expected a non-empty string, got {run_id!r}")
    return {
        "seed": seed_n,
        "engine": engine,
        "oracles": oracle_names,
        "max_experiments": experiments,
        "max_minutes": minutes,
        "max_calls": calls,
        "offline": offline,
        "cache": cache_path,
        "run_id": run_id,
    }


def _prepare(state: _Run, transport: object) -> None:
    _write_json(state.directory / "config.json", _config(state))
    state.extractor = PhiExtractor()
    if transport is not None:
        chosen = transport
    elif state.offline:
        chosen = None
    else:
        from surprise.roles.transport import DeepSeekTransport

        chosen = DeepSeekTransport()
    state.gateway = Gateway(
        cache_dir=state.cache_dir,
        ledger_path=state.directory / "llm" / "calls.jsonl",
        max_calls=state.max_calls,
        transport=chosen,
    )
    state.ledger = Ledger(state.directory / "ledger.sqlite")
    manifest = build_manifest(state.run_id)
    manifest["baseline"] = "pure_llm"
    manifest["pure_llm"] = {
        "PURE_LLM_TIER": PURE_LLM_TIER,
        "PURE_LLM_TEMPERATURE": PURE_LLM_TEMPERATURE,
        "PURE_LLM_MAX_TOKENS": PURE_LLM_MAX_TOKENS,
        "PURE_LLM_CASES_PER_CALL": PURE_LLM_CASES_PER_CALL,
        "PURE_LLM_TOPICS": list(PURE_LLM_TOPICS),
        "seed": state.seed,
        "engine": state.engine,
        "engine_version": state.engine_version,
        "oracles": list(state.oracles),
        "max_experiments": state.max_experiments,
        "max_minutes": state.max_minutes,
        "max_calls": state.max_calls,
        "offline": state.offline,
    }
    state.ledger.start_run(state.run_id, manifest)
    state.run_started = True
    state.progress = (state.directory / "progress.jsonl").open("w", encoding="utf-8", newline="\n")
    state.book = (state.directory / "llm" / "pure_llm.jsonl").open("w", encoding="utf-8", newline="\n")


def _drive(state: _Run) -> None:
    assert state.gateway is not None
    batch = 0
    while True:
        if _hit_experiments(state):
            state.status = "budget_experiments"
            return
        if _hit_minutes(state):
            state.status = "budget_minutes"
            return
        topic = state.rng.choice(PURE_LLM_TOPICS)
        prompt = _prompt(state, topic=topic, batch=batch)
        reply = state.gateway.call(
            "pure_llm",
            prompt,
            tier=PURE_LLM_TIER,
            seed=state.seed,
            temperature=PURE_LLM_TEMPERATURE,
            max_tokens=PURE_LLM_MAX_TOKENS,
        )
        state.calls += 1
        # The gateway ledger already records a cap refusal or a cache miss.
        # Those two end the run, so they are not another batch row.
        if reply.status in ("blocked", "miss"):
            state.status = "llm_exhausted"
            return
        if reply.status != "ok" or not isinstance(reply.data, dict):
            _write_book(state, batch=batch, topic=topic, status=reply.status, cases=0, skipped=0, reasons={})
            batch += 1
            continue
        accepted, skipped, reasons = _partition(reply.data, state.oracles)
        _write_book(
            state,
            batch=batch,
            topic=topic,
            status=reply.status,
            cases=len(accepted),
            skipped=skipped,
            reasons=reasons,
        )
        for item in accepted:
            if _hit_experiments(state):
                state.status = "budget_experiments"
                return
            if _hit_minutes(state):
                state.status = "budget_minutes"
                return
            _execute(state, batch=batch, topic=topic, item=item)
        batch += 1


def _execute(state: _Run, *, batch: int, topic: str, item: dict[str, Any]) -> None:
    assert state.extractor is not None and state.ledger is not None
    case = SqlCase(
        engine=state.engine,
        setup=item["setup"],
        query=item["query"],
        predicate=item["predicate"],
    )
    # expect is the model's prediction. The label comes only from the harness.
    record = evaluate_final(
        case,
        item["oracle"],
        ledger=state.ledger,
        run_id=state.run_id,
        purpose="pure_llm",
        spec={
            "batch": batch,
            "index": item["index"],
            "expect": item["expect"],
            "topic": topic,
        },
        phi=state.extractor.extract(case).to_dict(),
        theory_version=None,
        p_t=None,
        diagnose=True,
    )
    state.done += 1
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
        "batch": batch,
        "index": item["index"],
        "topic": topic,
        "oracle": item["oracle"],
        "y": label.y,
        "kind": kind,
        "expect": item["expect"],
        "elapsed_s": float(f"{_monotonic() - state.started_mono:.2f}"),
    }
    assert state.progress is not None
    state.progress.write(json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n")
    state.progress.flush()


def _write_book(
    state: _Run,
    *,
    batch: int,
    topic: str,
    status: str,
    cases: int,
    skipped: int,
    reasons: dict[str, int],
) -> None:
    row = {
        "batch": batch,
        "topic": topic,
        "status": status,
        "cases": cases,
        "skipped": skipped,
        "reasons": reasons,
    }
    assert state.book is not None
    state.book.write(json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n")
    state.book.flush()


def _hit_experiments(state: _Run) -> bool:
    return state.max_experiments is not None and state.done >= state.max_experiments


def _hit_minutes(state: _Run) -> bool:
    if state.max_minutes is None:
        return False
    return _monotonic() - state.started_mono >= state.max_minutes * 60.0


def _write_report(state: _Run) -> dict[str, Any]:
    finished = datetime.now(timezone.utc)
    records = _records(state)
    labels: dict[str, int] = {}
    for record in records:
        labels[record.label.y] = labels.get(record.label.y, 0) + 1
    report: dict[str, Any] = {
        "run_id": state.run_id,
        "seed": state.seed,
        "engine": state.engine,
        "oracles": list(state.oracles),
        "status": state.status,
        "experiments": len(records),
        "calls": state.calls,
        "started_at": state.started_at.isoformat(),
        "finished_at": finished.isoformat(),
        "wall_s": (finished - state.started_at).total_seconds(),
        "labels": labels,
        "llm": {} if state.gateway is None else state.gateway.totals(),
    }
    if state.status == "error":
        exc = state.exc
        report["error"] = {
            "type": type(exc).__name__ if exc is not None else "Exception",
            "message": "" if exc is None else str(exc),
        }
    _write_json(state.directory / "report.json", report)
    return report


def _records(state: _Run) -> list:
    if state.ledger is None or not state.run_started:
        return []
    return state.ledger.records(run_id=state.run_id)


def _config(state: _Run) -> dict[str, Any]:
    return {
        "seed": state.seed,
        "engine": state.engine,
        "oracles": list(state.oracles),
        "max_experiments": state.max_experiments,
        "max_minutes": state.max_minutes,
        "run_id": state.run_id,
        "llm": {
            "cache": str(state.cache_dir),
            "max_calls": state.max_calls,
            "network": not state.offline,
        },
    }


def _write_error(state: _Run, *, extra: str | None) -> None:
    chunks: list[str] = []
    if state.error_text:
        chunks.append(state.error_text.rstrip("\n"))
    if extra:
        chunks.append(extra.rstrip("\n"))
    if not chunks:
        return
    (state.directory / "error.txt").write_text("\n\n".join(chunks) + "\n", encoding="utf-8", newline="\n")


def _close(state: _Run) -> None:
    """Close the batch log, the progress file, the phi worker, and the ledger."""
    first: Exception | None = None
    for attr in ("book", "progress", "extractor", "ledger"):
        obj = getattr(state, attr)
        if obj is None:
            continue
        setattr(state, attr, None)
        try:
            obj.close()
        except Exception as exc:
            if first is None:
                first = exc
    if first is not None:
        raise first


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


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
    if not _finite(number) or number < 0:
        raise UsageError(f"max_minutes: expected a number >= 0, got {value!r}")
    return number


def _finite(number: float) -> bool:
    return number == number and number not in (float("inf"), float("-inf"))


def _optional_path(value: object, name: str) -> Path | None:
    if value is None:
        return None
    if isinstance(value, Path):
        return value
    if isinstance(value, str) and value != "":
        return Path(value)
    raise UsageError(f"{name}: expected a path, got {value!r}")


def _strings(value: object, name: str, *, allowed: tuple[str, ...]) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)) or len(value) == 0:
        raise UsageError(f"{name}: expected a non-empty sequence of strings, got {value!r}")
    items = tuple(value)
    for item in items:
        if not isinstance(item, str) or item == "":
            raise UsageError(f"{name}: expected non-empty strings, got {item!r}")
        if item not in allowed:
            raise UsageError(f"{name}: unknown {item!r}")
    return items


def _ascii(text: object) -> str:
    return str(text).encode("ascii", "backslashreplace").decode("ascii")


def main(argv: list[str] | None = None) -> int:
    """Command line. Returns 0, 2 for bad arguments, 1 for a run that raised, 130 for an interrupt."""
    parser = argparse.ArgumentParser(prog="python -m surprise.baselines.pure_llm")
    parser.add_argument("--out", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--engine", default="duckdb")
    parser.add_argument("--oracle", action="append", default=None, dest="oracles")
    parser.add_argument("--max-experiments", type=int, default=None)
    parser.add_argument("--max-minutes", type=float, default=None)
    parser.add_argument("--llm-cache", default=None)
    parser.add_argument("--llm-max-calls", type=int, default=None)
    parser.add_argument("--llm-offline", action="store_true")
    parser.add_argument("--run-id", default=None)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 2
    try:
        report = run(
            args.out,
            seed=args.seed,
            engine=args.engine,
            oracles=tuple(args.oracles) if args.oracles else ORACLE_IDS,
            max_experiments=args.max_experiments,
            max_minutes=args.max_minutes,
            cache=args.llm_cache,
            max_calls=args.llm_max_calls,
            offline=args.llm_offline,
            run_id=args.run_id,
        )
    except UsageError as exc:
        print(f"error: {_ascii(exc)}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {_ascii(exc)}", file=sys.stderr)
        return 1
    print(f"{report['status']} {report['experiments']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
