"""RQ1–RQ6 metrics of one run, computed from its ledger, theory and LLM books.

Nothing here writes into the run directory. ``ciao`` reads only the theory
store it is given, not the experiment ledger.
"""

from __future__ import annotations

import inspect
import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from surprise.harness.cve.shape import behavior_shape
from surprise.metrics.boundary import compare
from surprise.metrics.constants import (
    CALIBRATION_EDGES,
    CIAO_BATCH_SAMPLE,
    CIAO_MAX_GENERATIONS,
    CURVE_WINDOW,
    HIGH_SURPRISE_BITS,
    TEETH_AMPLITUDE,
    TEETH_WIDTH,
)
from surprise.metrics.curve import surprise_curve, teeth
from surprise.metrics.dups import duplicate_rate, identity_key, old_reports
from surprise.metrics.recall import score as recall_score
from surprise.metrics.rundata import RunData
from surprise.theory.length import theory_length
from surprise.theory.predict import surprise_bits

_LANES = ("implement", "bet", "translate")
_VIA = ("implement", "bet", "translate", "llm_rule", "invented_feature")
_EDIT_DECISIONS = ("accepted", "rejected", "rolled_back")


def label_key(record: Any) -> str | None:
    """Identity of a profiled failure. Anything else, including an unprofiled failure, is ``None``."""
    label = record.label
    if label.y != "fail" or not isinstance(label.cve, dict):
        return None
    profile = label.cve.get("profile")
    if not isinstance(profile, dict) or profile.get("status") != "ran":
        return None
    return identity_key(
        record.case.engine,
        list(profile.get("fix_set") or []),
        label.fail_kind,
        label.identity.error_class,
        behavior_shape(label.identity.behavior),
    )


def ledger_families(records: Sequence[Any], progress: Sequence[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """First occurrence of each profiled-failure key, in ``seq`` order.

    ``elapsed_s`` comes from that record's progress line, and is ``None`` when
    the line, or the field, is missing. The same definition is used for every arm.
    """
    by_id: dict[str, dict[str, Any]] = {}
    for row in progress or ():
        if isinstance(row, dict) and isinstance(row.get("record_id"), str):
            by_id[row["record_id"]] = row
    seen: set[str] = set()
    found: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda item: item.seq):
        key = label_key(record)
        if key is None or key in seen:
            continue
        seen.add(key)
        row = by_id.get(record.record_id)
        found.append(
            {
                "key": key,
                "record_id": record.record_id,
                "seq": record.seq,
                "elapsed_s": None if row is None else row.get("elapsed_s"),
            }
        )
    return found


def _family_rows(wb: Any) -> list[dict[str, Any]]:
    """Theory families in the same order and with the same keys as ``dups.new_families``."""
    grouped = wb.families()
    owned = wb.partition()
    first_of: dict[str, str] = {}
    for record_id, family in owned.items():
        if family is not None and family not in first_of:
            first_of[family] = record_id
    order = {record_id: index for index, record_id in enumerate(owned)}
    rows: list[dict[str, Any]] = []
    for name, hypothesis_ids in grouped.items():
        first = wb.theory.get(hypothesis_ids[0])
        rows.append(
            {
                "family": name,
                "hypotheses": list(hypothesis_ids),
                "key": identity_key(
                    first.engine,
                    first.interventions,
                    first.fail_kind,
                    first.error_class,
                    first.behavior_shape,
                ),
                "first_record": first_of.get(name),
            }
        )

    def sort_key(item: tuple[int, dict[str, Any]]) -> tuple[int, int]:
        index, row = item
        record_id = row["first_record"]
        if record_id is None:
            return (1, index)
        return (0, order[record_id])

    return [row for _, row in sorted(enumerate(rows), key=sort_key)]


def theory_lengths(wb: Any) -> list[dict[str, Any]]:
    """Description length of every closed generation, then the live theory."""
    rows: list[dict[str, Any]] = []
    for generation in range(wb.generation):
        theory = wb.store.load_generation(generation)
        rows.append(
            {
                "generation": generation,
                "length": theory_length(theory),
                "hypotheses": len(theory.hypotheses),
                "live": False,
            }
        )
    rows.append(
        {
            "generation": wb.generation,
            "length": theory_length(wb.theory),
            "hypotheses": len(wb.theory.hypotheses),
            "live": True,
        }
    )
    return rows


def _spread(total: int, count: int) -> list[int]:
    """Evenly spaced indexes in ``0 .. total-1``, matching the S11 gate's ``ref_spread``."""
    if count <= 0 or total <= 0:
        return []
    if total <= count:
        return list(range(total))
    if count == 1:
        return [0]
    picked: list[int] = []
    for k in range(count):
        index = int(math.floor(k * (total - 1) / (count - 1) + 0.5))
        if index not in picked:
            picked.append(index)
    return picked


def _batches(wb: Any) -> dict[int, list[str]]:
    """Valid record ids by the generation that was open when they were observed."""
    closes = [generation["journal_seq"] for generation in wb.store.generations()]
    valid = {seen.record_id for seen in wb.records() if seen.label.y != "invalid"}
    batches: dict[int, list[str]] = {}
    for row in wb.store.journal():
        if row.get("kind") != "observe" or row.get("record_id") not in valid:
            continue
        generation = sum(1 for seq in closes if seq < row["seq"])
        batches.setdefault(generation, []).append(row["record_id"])
    return batches


def _mean(values: Sequence[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present) / len(present)


def ciao(
    wb: Any,
    *,
    max_generations: int = CIAO_MAX_GENERATIONS,
    sample: int = CIAO_BATCH_SAMPLE,
) -> dict[str, Any] | None:
    """CIAO matrix: generation ``a``'s theory scored on generation ``b``'s batch.

    Rows and columns are the same sampled generations. An empty batch is
    ``None``. The whole result is ``None`` when the store has no valid observation.
    ``below_mean`` is newer theories on older batches; ``above_mean`` is the reverse.
    """
    batches = _batches(wb)
    if not batches:
        return None
    total = wb.generation + 1
    gens = _spread(total, max_generations)
    matrix: list[list[float | None]] = []
    for generation in gens:
        row: list[float | None] = []
        for batch_generation in gens:
            batch = batches.get(batch_generation, [])
            ids = [batch[index] for index in _spread(len(batch), sample)]
            row.append(None if not ids else wb.surprise_under(generation, ids))
        matrix.append(row)
    width = len(gens)
    return {
        "generations": gens,
        "batches": list(gens),
        "matrix": matrix,
        "diagonal_mean": _mean([matrix[i][i] for i in range(width)]),
        "below_mean": _mean([matrix[i][j] for i in range(width) for j in range(width) if i > j]),
        "above_mean": _mean([matrix[i][j] for i in range(width) for j in range(width) if i < j]),
    }


def _surprise(record: Any) -> float | None:
    if record.label.y == "invalid" or record.p_t is None:
        return None
    # surprise_bits rejects 0 and 1. Those endpoints still belong in the calibration bins.
    if not 0.0 < record.p_t < 1.0:
        return None
    return surprise_bits(record.p_t, record.label.y)


def _valid(records: Sequence[Any]) -> list[Any]:
    return [record for record in records if record.label.y in ("pass", "fail") and record.p_t is not None]


def _calibration(records: Sequence[Any]) -> list[dict[str, Any]]:
    valid = _valid(records)
    last_index = len(CALIBRATION_EDGES) - 2
    bins: list[dict[str, Any]] = []
    for index in range(len(CALIBRATION_EDGES) - 1):
        lo, hi = CALIBRATION_EDGES[index], CALIBRATION_EDGES[index + 1]
        last = index == last_index
        members = [record for record in valid if lo <= record.p_t < hi or (last and record.p_t == hi)]
        count = len(members)
        bins.append(
            {
                "lo": lo,
                "hi": hi,
                "count": count,
                "mean_p": None if count == 0 else sum(record.p_t for record in members) / count,
                "fail_rate": None if count == 0 else sum(1 for record in members if record.label.y == "fail") / count,
            }
        )
    return bins


def _brier(records: Sequence[Any]) -> tuple[float | None, float | None]:
    valid = _valid(records)
    if not valid:
        return None, None
    outcomes = [1.0 if record.label.y == "fail" else 0.0 for record in valid]
    brier = sum((record.p_t - outcome) ** 2 for record, outcome in zip(valid, outcomes)) / len(valid)
    rate = sum(outcomes) / len(outcomes)
    return brier, rate * (1.0 - rate)


def _high_surprise(records: Sequence[Any], progress: dict[str, dict[str, Any]]) -> dict[str, Any]:
    count = 0
    fresh = 0
    for record in records:
        bits = _surprise(record)
        if bits is None or bits < HIGH_SURPRISE_BITS:
            continue
        count += 1
        row = progress.get(record.record_id)
        if row is not None and row.get("triage") == "new_family":
            fresh += 1
    return {
        "threshold": HIGH_SURPRISE_BITS,
        "count": count,
        "new_family": fresh,
        "share": None if count == 0 else fresh / count,
    }


def _frozen(arm: Any) -> bool:
    return isinstance(arm, dict) and arm.get("freeze") == "theory"


def _profiled_keys(records: Sequence[Any]) -> list[str]:
    keys: list[str] = []
    for record in sorted(records, key=lambda item: item.seq):
        key = label_key(record)
        if key is not None:
            keys.append(key)
    return keys


def _per_hour(count: int, wall_s: float | None) -> float | None:
    if wall_s is None or wall_s == 0:
        return None
    return count / (wall_s / 3600.0)


def _llm_features(registry: Any) -> set[str]:
    found: set[str] = set()
    for feature_id in registry.ids():
        source = registry.get(feature_id).source
        if isinstance(source, str) and source.startswith("llm"):
            found.add(feature_id)
    return found


def _phi_features(record: Any) -> list[str]:
    phi = record.phi
    if not isinstance(phi, dict):
        return []
    features = phi.get("features")
    if not isinstance(features, list):
        return []
    return [item for item in features if isinstance(item, str)]


def _conjectures(book: Sequence[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    conjectures = [row for row in book if isinstance(row, dict) and row.get("type") == "conjecture"]
    settles = [row for row in book if isinstance(row, dict) and row.get("type") == "settle"]
    registered = [row for row in conjectures if row.get("status") == "registered"]
    states: dict[str, list[Any]] = {row["conjecture_id"]: [] for row in registered}
    for row in settles:
        states.setdefault(row["conjecture_id"], []).append(row.get("state"))
    with_settled = [cid for cid, states_of in states.items() if any(item in ("kept", "broken") for item in states_of)]
    survived = [cid for cid in with_settled if "broken" not in states[cid]]
    summary = {
        "registered": len(registered),
        "rejected": sum(1 for row in conjectures if row.get("status") == "rejected"),
        "with_settled": len(with_settled),
        "survived": len(survived),
        "survival_rate": None if not with_settled else len(survived) / len(with_settled),
    }
    kept = sum(1 for row in settles if row.get("state") == "kept")
    broken = sum(1 for row in settles if row.get("state") == "broken")
    void = sum(1 for row in settles if row.get("state") == "void")
    total = sum(len(row.get("predictions") or []) for row in registered)
    predictions = {
        "total": total,
        "kept": kept,
        "broken": broken,
        "void": void,
        "open": total - kept - broken - void,
        "accuracy": None if kept + broken == 0 else kept / (kept + broken),
    }
    timeline = [
        row for row in settles if row.get("state") in ("kept", "broken")
    ]
    return summary, predictions, timeline


def _translations(book: Sequence[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    settles = [row for row in book if isinstance(row, dict) and row.get("type") == "settle"]
    kept = sum(1 for row in settles if row.get("state") == "kept")
    broken = sum(1 for row in settles if row.get("state") == "broken")
    summary = {
        "total": len(settles),
        "kept": kept,
        "broken": broken,
        "accuracy": None if kept + broken == 0 else kept / (kept + broken),
    }
    timeline = [row for row in settles if row.get("state") in ("kept", "broken")]
    return summary, timeline


def _timeline(
    conjecture_rows: Sequence[dict[str, Any]],
    translation_rows: Sequence[dict[str, Any]],
    seq_of: dict[str, int],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for source, rows in (("conjecture", conjecture_rows), ("translation", translation_rows)):
        for row in rows:
            events.append(
                {
                    "seq": seq_of[row["record_id"]],
                    "source": source,
                    "kept": row.get("state") == "kept",
                }
            )
    events.sort(key=lambda item: item["seq"])
    kept = 0
    for index, event in enumerate(events, start=1):
        if event["kept"]:
            kept += 1
        event["accuracy"] = kept / index
    return events


def _calls(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    by_role: dict[str, dict[str, int]] = {}
    network = 0
    input_tokens = 0
    output_tokens = 0
    for row in rows:
        entry = by_role.setdefault(
            row["role"],
            {"calls": 0, "network": 0, "input_tokens": 0, "output_tokens": 0},
        )
        entry["calls"] += 1
        if row.get("source") == "network":
            entry["network"] += 1
            network += 1
        incoming = int(row.get("input_tokens") or 0)
        outgoing = int(row.get("output_tokens") or 0)
        entry["input_tokens"] += incoming
        entry["output_tokens"] += outgoing
        input_tokens += incoming
        output_tokens += outgoing
    return {
        "by_role": by_role,
        "total": len(rows),
        "network": network,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def _usd(rows: Sequence[dict[str, Any]], prices: dict[str, dict[str, float]] | None) -> float | None:
    if prices is None:
        return None
    total = 0.0
    for row in rows:
        model = row.get("model")
        quote = prices.get(model) if isinstance(prices, dict) else None
        if not isinstance(quote, dict):
            raise ValueError(f"no price for model {model!r}")
        incoming = int(row.get("input_tokens") or 0)
        outgoing = int(row.get("output_tokens") or 0)
        total += incoming / 1_000_000 * float(quote["input"]) + outgoing / 1_000_000 * float(quote["output"])
    return total


def _families_via(records: Sequence[Any], progress: dict[str, dict[str, Any]], invented: set[str]) -> dict[str, int]:
    via = {name: 0 for name in _VIA}
    by_id = {record.record_id: record for record in records}
    for family in ledger_families(records, list(progress.values())):
        record = by_id[family["record_id"]]
        row = progress.get(record.record_id)
        if row is not None:
            lane = row.get("lane")
            if lane in _LANES:
                via[lane] += 1
            rule = row.get("rule") or ""
            if isinstance(rule, str) and rule.startswith("llm:"):
                via["llm_rule"] += 1
        if invented and any(feature in invented for feature in _phi_features(record)):
            via["invented_feature"] += 1
    return via


def _pure_llm(records: Sequence[Any]) -> dict[str, Any]:
    kept = 0
    broken = 0
    for record in records:
        spec = record.spec if isinstance(record.spec, dict) else None
        expect = None if spec is None else spec.get("expect")
        outcome = record.label.y
        if expect == outcome:
            kept += 1
        elif expect in ("pass", "fail") and expect != outcome:
            broken += 1
    return {
        "total": len(records),
        "kept": kept,
        "broken": broken,
        "accuracy": None if kept + broken == 0 else kept / (kept + broken),
    }


def _recall(known: Any, store_dir: Path, registry: Any) -> dict[str, Any]:
    if "registry" in inspect.signature(recall_score).parameters:
        return recall_score(known, store_dir, registry=registry)
    return recall_score(known, store_dir)


def _edits(wb: Any) -> tuple[dict[str, int], dict[str, Any]]:
    tally = {name: 0 for name in _EDIT_DECISIONS}
    accepted: list[Any] = []
    if wb is not None:
        for edit in wb.edits():
            if edit.decision in tally:
                tally[edit.decision] += 1
            if edit.decision == "accepted" and edit.surprise_delta_in is not None and edit.surprise_delta_out is not None:
                accepted.append(edit)
    if not accepted:
        gap = {"edits": 0, "mean_in": None, "mean_out": None, "gap": None}
    else:
        mean_in = sum(edit.surprise_delta_in for edit in accepted) / len(accepted)
        mean_out = sum(edit.surprise_delta_out for edit in accepted) / len(accepted)
        gap = {"edits": len(accepted), "mean_in": mean_in, "mean_out": mean_out, "gap": mean_out - mean_in}
    return tally, gap


def _invalid(records: Sequence[Any], executions: int) -> dict[str, Any]:
    invalid = [record for record in records if record.label.y == "invalid"]
    by_reason: dict[str, int] = {}
    by_oracle: dict[str, int] = {}
    for record in invalid:
        reason = record.label.invalid_reason
        oracle = record.label.oracle
        by_reason[reason] = by_reason.get(reason, 0) + 1
        by_oracle[oracle] = by_oracle.get(oracle, 0) + 1
    return {
        "count": len(invalid),
        "rate": None if executions == 0 else len(invalid) / executions,
        "by_reason": by_reason,
        "by_oracle": by_oracle,
    }


def _roles(config: dict[str, Any]) -> list[Any]:
    llm = config.get("llm")
    if not isinstance(llm, dict):
        return []
    roles = llm.get("roles", [])
    if isinstance(roles, list):
        return list(roles)
    return []


def _engines(config: dict[str, Any], kind: str) -> list[Any]:
    if kind == "pure_llm":
        return [config["engine"]]
    raw = config.get("engines")
    if isinstance(raw, (list, tuple)):
        return list(raw)
    return []


def _oracles(config: dict[str, Any]) -> list[Any]:
    raw = config.get("oracles")
    if isinstance(raw, (list, tuple)):
        return list(raw)
    return []


def _per_family(executions: int, family_count: int, llm_calls: int, tokens: int, usd: float | None) -> dict[str, Any]:
    if family_count == 0:
        return {"executions": None, "llm_calls": None, "tokens": None, "usd": None}
    return {
        "executions": executions / family_count,
        "llm_calls": llm_calls / family_count,
        "tokens": tokens / family_count,
        "usd": None if usd is None else usd / family_count,
    }


def run_metrics(
    run_dir: str | Path,
    *,
    known: Any = None,
    prices: dict[str, dict[str, float]] | None = None,
    window: int | None = None,
) -> dict[str, Any]:
    """Every RQ1–RQ6 metric of ``run_dir``. The same directory yields the same dict."""
    data = RunData.open(run_dir)
    records = data.records
    config = data.config
    report = data.report
    arm = config.get("arm")
    executions = len(records)
    wall_s = None if report is None else report.get("wall_s")
    families = ledger_families(records, data.progress)
    family_count = len(families)
    progress = {row["record_id"]: row for row in data.progress if isinstance(row, dict) and isinstance(row.get("record_id"), str)}
    wb = data.workbench()
    rows = _family_rows(wb) if wb is not None else []
    theory_keys = None if wb is None or _frozen(arm) else [row["key"] for row in rows]
    if theory_keys is not None:
        rate = duplicate_rate(theory_keys)
    else:
        rate = duplicate_rate(_profiled_keys(records))
    first = None if not families else {"seq": families[0]["seq"], "elapsed_s": families[0]["elapsed_s"]}
    brier, reference = _brier(records)
    used_window = CURVE_WINDOW if window is None else window
    curve = surprise_curve(records, window=used_window)
    conjecture_summary, predictions, conjecture_timeline = _conjectures(data.book("conjectures"))
    translation_summary, translation_timeline = _translations(data.book("translations"))
    calls = _calls(data.book("calls"))
    tokens = calls["input_tokens"] + calls["output_tokens"]
    usd = _usd(data.book("calls"), prices)
    edits, gap = _edits(wb)
    known_score = None
    if known is not None and wb is not None:
        known_score = _recall(known, data.path / "theory", data.registry)
    ratio = None if family_count == 0 else calls["total"] / family_count
    token_ratio = None if family_count == 0 else tokens / family_count
    return {
        "run": {
            "run_id": data.run_id,
            "kind": data.kind,
            "seed": config.get("seed"),
            "engines": _engines(config, data.kind),
            "oracles": _oracles(config),
            "status": None if report is None else report.get("status"),
            "experiments": executions,
            "wall_s": wall_s,
            "arm": arm,
            "llm_roles": _roles(config),
        },
        "rq1": {
            "executions": executions,
            "families": families,
            "family_count": family_count,
            "families_per_1000": None if executions == 0 else 1000.0 * family_count / executions,
            "families_per_hour": _per_hour(family_count, wall_s),
            "first_family": first,
            "theory_families": theory_keys,
            "duplicate_rate": rate,
        },
        "rq2": {
            "valid": len(_valid(records)),
            "brier": brier,
            "brier_reference": reference,
            "mean_surprise": _mean([_surprise(record) for record in records]),
            "calibration": _calibration(records),
            "high_surprise": _high_surprise(records, progress),
            "window": used_window,
            "curve": curve,
            "teeth": teeth(curve, TEETH_AMPLITUDE, TEETH_WIDTH),
        },
        "rq3": {
            "conjectures": conjecture_summary,
            "predictions": predictions,
            "translations": translation_summary,
            "timeline": _timeline(conjecture_timeline, translation_timeline, {record.record_id: record.seq for record in records}),
            "families_via": _families_via(records, progress, _llm_features(data.registry)),
            "calls": calls,
            "calls_per_family": ratio,
            "tokens_per_family": token_ratio,
            "pure_llm": _pure_llm(records) if data.kind == "pure_llm" else None,
        },
        "rq4": {
            "invalid": _invalid(records, executions),
            "duplicate_rate": rate,
            "theory_length": [] if wb is None else theory_lengths(wb),
            "edits": edits,
            "in_out": gap,
        },
        "rq5": {
            "ciao": None if wb is None else ciao(wb),
            "arm": arm,
        },
        "rq6": {
            "recall": known_score,
            "boundary": None if wb is None else compare(wb, rows),
        },
        "cost": {
            "executions": executions,
            "wall_s": wall_s,
            "llm_calls": calls["total"],
            "input_tokens": calls["input_tokens"],
            "output_tokens": calls["output_tokens"],
            "usd": usd,
            "per_family": _per_family(executions, family_count, calls["total"], tokens, usd),
        },
    }


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name}: expected a JSON object")
    return payload


def old_metrics(old_dir: str | Path) -> dict[str, Any]:
    """Metrics of one original CoevoDB run, from ``old_run.json`` and its ``bugs.jsonl``.

    A killed run may never create ``bugs.jsonl``. That is zero reports, the same
    count ``old_no_llm`` stores. A missing ``run_dir`` is still an error.
    """
    root = Path(old_dir)
    meta = _read_json(root / "old_run.json")
    run_dir = root / meta["run_dir"]
    if not run_dir.is_dir():
        raise FileNotFoundError(run_dir)
    bugs = run_dir / "bugs.jsonl"
    reports = old_reports(bugs) if bugs.is_file() else []
    seen: set[str] = set()
    families: list[dict[str, Any]] = []
    keys: list[str] = []
    for index, report in enumerate(reports, start=1):
        key = report["key"]
        keys.append(key)
        if key in seen:
            continue
        seen.add(key)
        families.append(
            {
                "key": key,
                "record_id": report["root_key"],
                "seq": index,
                "elapsed_s": None,
            }
        )
    wall_s = meta["wall_s"]
    family_count = len(families)
    first = None if not families else {"seq": families[0]["seq"], "elapsed_s": None}
    return {
        "run": {
            "run_id": None,
            "kind": "old_coevodb",
            "seed": meta["seed"],
            "mode": meta["mode"],
            "engines": None,
            "oracles": None,
            "status": meta["ended"],
            "experiments": None,
            "wall_s": wall_s,
            "arm": None,
            "llm_roles": None,
        },
        "rq1": {
            "executions": None,
            "families": families,
            "family_count": family_count,
            "families_per_1000": None,
            "families_per_hour": _per_hour(family_count, wall_s),
            "first_family": first,
            "theory_families": None,
            "duplicate_rate": duplicate_rate(keys),
        },
        "rq2": None,
        "rq3": None,
        "rq4": None,
        "rq5": None,
        "rq6": None,
        "cost": {
            "executions": None,
            "wall_s": wall_s,
            "llm_calls": None,
            "input_tokens": None,
            "output_tokens": None,
            "usd": None,
            "per_family": None,
        },
    }
