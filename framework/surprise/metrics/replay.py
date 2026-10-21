"""Stratified replay of an old ledger against the current frozen harness."""

from __future__ import annotations

import argparse
import json
import multiprocessing
import random
import sqlite3
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any

from surprise.harness import cve
from surprise.harness.contracts import ExperimentRecord, Label
from surprise.harness.manifest import file_digest, harness_hash
from surprise.metrics.rundata import RunData

_FRAMEWORK = Path(__file__).resolve().parents[2]


def _allocation(counts: dict[str, int], sample: int) -> dict[str, int]:
    """Largest remainders, constrained to at least one per nonempty stratum.

    Ties use the stratum key. If the lower bounds overfill the usual Hamilton
    allocation, remove seats from the most overrepresented eligible stratum.
    A request smaller than the number of strata cannot satisfy the bounds.
    Integer quota numerators avoid floating-point tie breaking.
    """
    total = sum(counts.values())
    target = min(sample, total)
    if target < len(counts):
        raise ValueError(f"sample must be at least the number of nonempty strata ({len(counts)})")
    if not counts:
        return {}
    quotas = {key: target * count for key, count in counts.items()}
    allocated = {key: max(1, quota // total) for key, quota in quotas.items()}
    while sum(allocated.values()) > target:
        key = min(
            (key for key in counts if allocated[key] > 1),
            key=lambda key: (quotas[key] - allocated[key] * total, key),
        )
        allocated[key] -= 1
    while sum(allocated.values()) < target:
        key = min(
            (key for key in counts if allocated[key] < counts[key]),
            key=lambda key: (allocated[key] * total - quotas[key], key),
        )
        allocated[key] += 1
    return allocated


def sample_records(
    data: RunData, sample: int, seed: int
) -> tuple[list[ExperimentRecord], dict[str, dict[str, int]]]:
    """Two streaming passes; retain only the requested reservoirs, without detail."""
    if sample < 1:
        raise ValueError("sample must be positive")
    counts: Counter[str] = Counter()
    for record in data.iter_records(keep_detail=False):
        counts[f"{record.label.oracle}|{record.label.y}"] += 1
    counts = dict(sorted(counts.items()))
    allocation = _allocation(counts, sample)
    reservoirs: dict[str, list[ExperimentRecord]] = {key: [] for key in counts}
    seen: Counter[str] = Counter()
    rng = random.Random(seed)
    for record in data.iter_records(keep_detail=False):
        key = f"{record.label.oracle}|{record.label.y}"
        seen[key] += 1
        bucket = reservoirs[key]
        size = allocation[key]
        slot = len(bucket) if len(bucket) < size else rng.randrange(seen[key])
        if slot < size:
            # RunData only strips very large details; none are needed in replay.
            slim = replace(record, label=replace(record.label, detail={}))
            if len(bucket) < size:
                bucket.append(slim)
            else:
                bucket[slot] = slim
    records = sorted((record for bucket in reservoirs.values() for record in bucket), key=lambda r: r.seq)
    strata = {key: {"records": counts[key], "sampled": allocation[key]} for key in counts}
    return records, strata


def _ran(label: Label, step: str) -> bool:
    return label.cve.get(step, {}).get("status") == "ran"


def compare_labels(old: Label, new: Label) -> dict[str, Any]:
    """Compare the evidence required by EXPERIMENT section 8."""
    if old.invalid_reason in ("unstable_rerun", "timeout"):
        return {} if new.y == "invalid" else {"y": [old.y, new.y]}
    fields: dict[str, Any] = {}
    for name in ("y", "oracle", "fail_kind", "invalid_reason", "identity"):
        before, after = getattr(old, name), getattr(new, name)
        if name == "identity":
            before, after = before.to_dict(), after.to_dict()
        if before != after:
            fields[name] = [before, after]
    steps = ["rerun", "premise"]
    if not _ran(old, "attribution"):
        steps.extend(("attribution", "tier"))
    if _ran(old, "profile"):
        steps.extend(("minimize", "profile"))
    for name in steps:
        before, after = old.cve.get(name), new.cve.get(name)
        if before != after:
            fields[f"cve.{name}"] = [before, after]
    return fields


def _replay_record(record: ExperimentRecord) -> dict[str, Any]:
    try:
        label = cve.certify(
            record.case,
            record.label.oracle,
            diagnose=_ran(record.label, "profile"),
            rewrite_rule=(record.spec or {}).get("rule"),
        )
    except Exception as exc:
        # A replay failure is evidence of a difference, never a passing record.
        return {"exception": f"{type(exc).__name__}: {exc}"}
    return compare_labels(record.label, label)


def _run_dir(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(_FRAMEWORK).as_posix()
    except ValueError:
        return str(resolved)


def replay(run_dir: str | Path, *, sample: int, seed: int, workers: int = 1) -> dict[str, Any]:
    """Replay sampled records in worker processes and return the JSON report."""
    if workers < 1:
        raise ValueError("workers must be positive")
    started = time.perf_counter()
    data = RunData.open(run_dir)
    records, strata = sample_records(data, sample, seed)
    report: dict[str, Any] = {
        "schema": 1,
        "harness": harness_hash()["hash"],
        "source": {
            "run_dir": _run_dir(data.path),
            "ledger_sha256": file_digest(data.path / "ledger.sqlite"),
            "records": sum(row["records"] for row in strata.values()),
        },
        "sample": sample,
        "seed": seed,
        "sampled": len(records),
        "strata": strata,
        "same": 0,
        "invalid_kept": 0,
        "attribution_not_replayed": sum(_ran(record.label, "attribution") for record in records),
        "different": [],
    }
    if records:
        with ProcessPoolExecutor(
            max_workers=workers, mp_context=multiprocessing.get_context("spawn")
        ) as pool:
            for record, fields in zip(records, pool.map(_replay_record, records)):
                if fields:
                    report["different"].append({
                        "record_id": record.record_id,
                        "seq": record.seq,
                        "oracle": record.label.oracle,
                        "fields": fields,
                    })
                else:
                    report["same"] += 1
                    if record.label.invalid_reason in ("unstable_rerun", "timeout"):
                        report["invalid_kept"] += 1
    report["elapsed_s"] = time.perf_counter() - started
    return report


def _positive(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--sample", type=_positive, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=_positive, default=1)
    args = parser.parse_args(argv)
    try:
        report = replay(args.run_dir, sample=args.sample, seed=args.seed, workers=args.workers)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="ascii")
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.error(str(exc).encode("ascii", "backslashreplace").decode("ascii"))
    print(
        f"replay sampled={report['sampled']} same={report['same']} "
        f"invalid_kept={report['invalid_kept']} different={len(report['different'])}"
    )
    return int(bool(report["different"]))


if __name__ == "__main__":
    raise SystemExit(main())
