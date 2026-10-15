"""Offline comparison of sigma dedup and the pre-execution membership test.

Reads one run directory and does not write it. A failure whose stored profile
did not run is certified again in this process when ``reprofile`` is set; that
call is not written back to the ledger. No LLM.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from diagnosis.signature import SignatureEngine

from surprise.harness.cve.certify import certify
from surprise.harness.contracts import Label, SqlCase
from surprise.metrics.rq import label_key
from surprise.metrics.rundata import RunData


def compare_dedup(run_dir: str | Path, *, limit: int | None = None, reprofile: bool = True) -> dict[str, Any]:
    """Compare sigma and the pre-execution membership test on one run's failures.

    Failures are ledger rows with ``y == "fail"``, in ``seq`` order. ``limit``
    keeps the first that many. Truth is the full-profile identity. Sigma is the
    old ``SignatureEngine`` key of that same profile. Membership is the
    progress row's zone: ``confirmed`` means the failure was already in a
    known family before it ran.
    """
    limit = _limit(limit)
    data = RunData.open(run_dir)
    failures = [record for record in data.records if record.label.y == "fail"]
    if limit is not None:
        failures = failures[:limit]
    pending = [record for record in failures if not _profile_ran(record.label)]
    if pending and reprofile:
        _require_same_versions(data.manifest, [record.case.engine for record in pending])

    rows: list[dict[str, Any]] = []
    truth_seen: set[str] = set()
    sigma_seen: set[str] = set()
    sigma_executions = 0
    attribution_executions = 0
    engine = SignatureEngine(runner_factory=lambda: None, checker=None)
    for record in failures:
        progress = data.row(record.record_id)
        zone = None if progress is None else progress.get("zone")
        rule = None if progress is None else progress.get("rule")
        used = record.label
        did_reprofile = False
        if not _profile_ran(used):
            if reprofile:
                used = certify(record.case, record.label.oracle, diagnose=True, rewrite_rule=rule)
                did_reprofile = True
            else:
                used = None
        row = _row(record, zone=zone, label=used, reprofiled=did_reprofile, engine=engine)
        if row["truth_key"] is None:
            row["truth_dup"] = None
        else:
            row["truth_dup"] = row["truth_key"] in truth_seen
            truth_seen.add(row["truth_key"])
        if row["sigma_key"] is None:
            row["sigma_dup"] = None
        else:
            row["sigma_dup"] = row["sigma_key"] in sigma_seen
            sigma_seen.add(row["sigma_key"])
        if isinstance(row["profile"], dict) and row["truth_key"] is not None:
            sigma_executions += int(row["profile"]["executions"])
        # Membership was decided during the run. Reprofiling does not repeat
        # the attribution test, so its cost stays on the stored label.
        attribution_executions += _attribution_executions(record.label)
        rows.append(row)

    skipped = sum(1 for row in rows if row["truth_key"] is None)
    return {
        "run": str(Path(run_dir).resolve()),
        "failures": len(rows),
        "skipped": skipped,
        "truth_duplicates": sum(1 for row in rows if row["truth_dup"] is True),
        "sigma": _scores(rows, "sigma_dup", sigma_executions),
        "membership": _scores(rows, "member_dup", 0),
        "attribution_executions": attribution_executions,
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m surprise.metrics.dedup")
    parser.add_argument("run_dir")
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-reprofile", action="store_true")
    args = parser.parse_args(argv)
    payload = compare_dedup(args.run_dir, limit=args.limit, reprofile=not args.no_reprofile)
    Path(args.out).write_text(_json(payload), encoding="utf-8", newline="\n")
    return 0


def _row(
    record: Any,
    *,
    zone: Any,
    label: Label | None,
    reprofiled: bool,
    engine: SignatureEngine,
) -> dict[str, Any]:
    """One failure. ``label`` is the profiled label, or None when truth is skipped."""
    base = {
        "record_id": record.record_id,
        "seq": record.seq,
        "zone": zone,
        "member_dup": zone == "confirmed",
        "profile": None,
        "truth_key": None,
        "truth_dup": None,
        "minimal": _minimal(record.label, record.case),
        "error_class": record.label.identity.error_class,
        "sigma_key": None,
        "sigma_dup": None,
        "reprofiled": reprofiled,
    }
    if label is None or label.y != "fail" or not _profile_ran(label):
        return base
    profile = dict(label.cve["profile"])
    minimal = _minimal(label, record.case)
    # The gate compares this field with the stored label on every row, including
    # one whose profile was rebuilt. Sigma's notes use the same value.
    base["profile"] = profile
    base["minimal"] = minimal
    base["truth_key"] = label_key(SimpleNamespace(case=record.case, label=label))
    base["sigma_key"] = _sigma_key(engine, profile, minimal, base["error_class"])
    return base


def _sigma_key(
    engine: SignatureEngine,
    profile: dict[str, Any],
    minimal: dict[str, Any],
    error_class: str | None,
) -> str:
    """The old sigma identity. The rule lives in ``SignatureEngine._signature``."""
    candidate = SimpleNamespace(
        r1_summary=None,
        r2_summary=None,
        notes=error_class or "",
        schema_sqls=[],
        inserts=[],
        q1="",
        q2="",
    )
    signed = engine._signature(
        fix_kind=profile["fix_kind"],
        fix_set=list(profile["fix_set"]),
        plan_diff=list(profile["plan_diff"]),
        nu=profile["version_ladder"],
        executions=int(profile["executions"]),
        candidate=candidate,
        minimal={
            "schema_sqls": list(minimal["setup"]),
            "inserts": [],
            "q1": minimal["query"],
            "q2": minimal["predicate"] or "",
        },
    )
    return signed["key"]


def _minimal(label: Label, case: SqlCase) -> dict[str, Any]:
    cve = label.cve if isinstance(label.cve, dict) else {}
    minimize = cve.get("minimize") if isinstance(cve, dict) else None
    if isinstance(minimize, dict) and minimize.get("status") == "ran" and isinstance(minimize.get("case"), dict):
        return dict(minimize["case"])
    return case.to_dict()


def _profile_ran(label: Label) -> bool:
    cve = label.cve
    if not isinstance(cve, dict):
        return False
    profile = cve.get("profile")
    return isinstance(profile, dict) and profile.get("status") == "ran"


def _attribution_executions(label: Label) -> int:
    """Executions recorded on a harness attribution step. Absent means zero."""
    cve = label.cve
    if not isinstance(cve, dict):
        return 0
    attribution = cve.get("attribution")
    if not isinstance(attribution, dict):
        return 0
    executions = attribution.get("executions")
    if isinstance(executions, bool) or not isinstance(executions, int):
        return 0
    return executions


def _scores(rows: list[dict[str, Any]], decision: str, executions: int) -> dict[str, Any]:
    """Precision and recall of ``decision`` against ``truth_dup``. Unknown truth is left out."""
    tp = fp = fn = 0
    for row in rows:
        truth = row["truth_dup"]
        if truth is None:
            continue
        decided = row[decision]
        if decided is None:
            continue
        if decided and truth:
            tp += 1
        elif decided:
            fp += 1
        elif truth:
            fn += 1
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": None if tp + fp == 0 else tp / (tp + fp),
        "recall": None if tp + fn == 0 else tp / (tp + fn),
        "executions": executions,
    }


def _require_same_versions(manifest: dict[str, Any], engines: list[str]) -> None:
    """The profile is only meaningful on the engine version that produced the run."""
    seen: set[str] = set()
    for engine_name in engines:
        if engine_name in seen:
            continue
        seen.add(engine_name)
        recorded = _recorded_version(manifest, engine_name)
        current = _installed_version(engine_name)
        if not isinstance(recorded, str) or recorded == "" or recorded != current:
            raise ValueError(
                f"{engine_name} version in this interpreter is {current!r}, "
                f"the run manifest records {recorded!r}"
            )


def _recorded_version(manifest: dict[str, Any], engine_name: str) -> Any:
    environment = manifest.get("environment")
    if not isinstance(environment, dict):
        return None
    engines = environment.get("engines")
    if not isinstance(engines, dict):
        return None
    return engines.get(engine_name)


def _installed_version(engine_name: str) -> str | None:
    if engine_name == "sqlite":
        return sqlite3.sqlite_version
    try:
        return importlib.metadata.version(engine_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _limit(value: int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"limit: expected an integer >= 0, got {value!r}")
    return value


def _json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=True, indent=1) + "\n"


if __name__ == "__main__":
    sys.exit(main())
