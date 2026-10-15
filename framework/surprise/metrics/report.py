"""One command writes the RQ1–RQ6 report of a finished experiment grid.

    python -m surprise.metrics.report GRID_DIR [--out DIR] [--dedup FILE] [--coverage FILE]

The grid is read only. Files are written under ``--out`` (default
``GRID_DIR/report``). The same grid produces the same ``report.json``.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from surprise.baselines import sqlancer
from surprise.metrics.constants import CALIBRATION_EDGES
from surprise.metrics.rq import old_metrics, run_metrics
from surprise.metrics.stats import a12, mann_whitney_u, summarize

SCHEMA = 1
FIGSIZE = (8.0, 4.8)
DPI = 120
PALETTE = (
    "#4C78A8",
    "#F58518",
    "#54A24B",
    "#E45756",
    "#72B7B2",
    "#EECA3B",
    "#B279A2",
    "#FF9DA6",
    "#9D755D",
    "#BAB0AC",
)
RQ_METRICS = {
    "rq1": (
        "family_count",
        "families_per_1000",
        "families_per_hour",
        "first_family_minutes",
        "duplicate_rate",
    ),
    "rq2": ("brier", "brier_reference", "high_surprise_share", "teeth"),
    "rq3": (
        "survival_rate",
        "prediction_accuracy",
        "calls_per_family",
        "tokens_per_family",
        "pure_llm_accuracy",
    ),
    "rq4": (
        "invalid_rate",
        "duplicate_rate",
        "theory_length_final",
        "in_out_gap",
        "edits_accepted",
    ),
    "rq6": ("recall",),
}
RQ_SECTIONS = (
    ("rq1", "RQ1 发现", ("rq1_families.png",)),
    ("rq2", "RQ2 校准", ("rq2_surprise.png", "rq2_calibration.png")),
    ("rq3", "RQ3 LLM 猜想", ("rq3_llm.png",)),
    ("rq4", "RQ4 Harness", ("rq4_quality.png",)),
    ("rq5", "RQ5 协同进化", ("rq5_ciao.png",)),
    ("rq6", "RQ6 理论质量", ("rq6_recall.png",)),
)
_NO_LLM = "no LLM predictions in this grid"
_NO_CIAO = "no CIAO matrix for the reference arm"
_NO_RECALL = "no known-bug file for this grid"
_RUN_KINDS = ("surprise", "pure_llm")


def build(
    grid_dir: str | Path,
    out: str | Path | None = None,
    *,
    dedup: str | Path | None = None,
    coverage: str | Path | None = None,
) -> dict[str, Any]:
    """Read ``grid_dir`` and write ``report.json``, ``report.md`` and seven figures.

    ``dedup`` and ``coverage`` override ``GRID_DIR/extras/dedup.json`` and
    ``coverage.json`` when both are present. The parsed JSON is stored as it is.
    """
    root = Path(grid_dir)
    if not root.is_dir():
        raise ValueError(f"grid: not a directory: {root}")
    destination = root / "report" if out is None else Path(out)
    if destination.exists() and not destination.is_dir():
        raise ValueError(f"out: not a directory: {destination}")
    config = _load_grid(root)
    known = _load_known(config)
    report = _assemble(root, config, known=known, prices=config.get("prices"), window=_window(config))
    extras = _extras(root, dedup, coverage)
    if extras:
        report["extras"] = extras
    _write(destination, report, known_present=config.get("known") is not None)
    return report


def main(argv: list[str] | None = None) -> int:
    """Command line. 0 when the report was written, 2 for a bad request."""
    parser = argparse.ArgumentParser(prog="python -m surprise.metrics.report")
    parser.add_argument("grid_dir")
    parser.add_argument("--out", default=None)
    parser.add_argument("--dedup", default=None)
    parser.add_argument("--coverage", default=None)
    args = parser.parse_args(argv)
    try:
        build(args.grid_dir, args.out, dedup=args.dedup, coverage=args.coverage)
    except ValueError as exc:
        print(f"error: {_ascii(exc)}", file=sys.stderr)
        return 2
    return 0


# ---- assembly -----------------------------------------------------------------------------------


def _assemble(
    root: Path,
    config: dict[str, Any],
    *,
    known: Any,
    prices: Any,
    window: int,
) -> dict[str, Any]:
    arms = config["arms"]
    names = [arm["name"] for arm in arms]
    samples = {
        name: {rq: {metric: [] for metric in metrics} for rq, metrics in RQ_METRICS.items()}
        for name in names
    }
    arm_cells = {name: [] for name in names}
    cells: dict[str, dict[str, Any]] = {}
    curves: dict[str, list] = {}
    timelines: dict[str, Any] = {}
    lengths: dict[str, Any] = {}
    boundaries: dict[str, Any] = {}
    ciao: dict[str, Any] = {}
    reference = config["reference"]

    for arm in arms:
        if arm.get("kind") == "sqlancer":
            _collect(samples[arm["name"]], _sqlancer_row(arm), "sqlancer")

    for arm, seed, rep in _iter_cells(config):
        name = _cell_name(arm["name"], seed, rep)
        meta = _read_cell(_cell_dir(root, arm["name"], seed, rep))
        status = meta["status"]
        arm_cells[arm["name"]].append(name)
        metrics = None
        if status == "done":
            metrics = _metrics_for(arm["kind"], _cell_dir(root, arm["name"], seed, rep), known=known, prices=prices, window=window)
            _collect(samples[arm["name"]], metrics, arm["kind"])
            curves[name] = _family_curve(metrics, arm["kind"])
            timelines[name] = _section_field(metrics, "rq3", "timeline")
            lengths[name] = _section_field(metrics, "rq4", "theory_length")
            boundaries[name] = _section_field(metrics, "rq6", "boundary")
            if arm["name"] == reference:
                matrix = _section_field(metrics, "rq5", "ciao")
                if isinstance(matrix, dict):
                    ciao[name] = matrix
        cells[name] = {
            "arm": arm["name"],
            "seed": seed,
            "rep": rep,
            "status": status,
            "metrics": metrics,
        }

    blocks = {
        rq: {
            "metrics": list(metrics),
            "arms": {
                name: {metric: summarize(samples[name][rq][metric]) for metric in metrics}
                for name in names
            },
        }
        for rq, metrics in RQ_METRICS.items()
    }
    blocks["rq1"]["curves"] = curves
    blocks["rq2"]["calibration"] = {
        name: _merge_bins(_calibration_of(name, cells)) for name in names
    }
    blocks["rq3"]["timeline"] = timelines
    blocks["rq4"]["theory_length"] = lengths
    blocks["rq6"]["boundary"] = boundaries
    blocks["rq6"]["partition"] = None
    return {
        "schema": SCHEMA,
        "grid": config["name"],
        "reference": reference,
        "arms": {
            arm["name"]: {"kind": arm["kind"], "cells": arm_cells[arm["name"]], "options": arm}
            for arm in arms
        },
        "cells": cells,
        "rq1": blocks["rq1"],
        "rq2": blocks["rq2"],
        "rq3": blocks["rq3"],
        "rq4": blocks["rq4"],
        "rq5": _rq5(config, arm_cells, cells, ciao, blocks, samples),
        "rq6": blocks["rq6"],
        "stats": _stats(names, samples, blocks),
        "external": {"sqlancer": sqlancer.metrics(sqlancer.load(), engine="duckdb")},
    }


def _rq5(
    config: dict[str, Any],
    arm_cells: dict[str, list[str]],
    cells: dict[str, dict[str, Any]],
    ciao: dict[str, Any],
    blocks: dict[str, dict[str, Any]],
    samples: dict[str, dict[str, dict[str, list]]],
) -> dict[str, Any]:
    reference = config["reference"]
    freezing = []
    pairing = []
    for arm in config["arms"]:
        name = arm["name"]
        if arm.get("kind") == "surprise" and (arm.get("freeze") or arm.get("hunter") == "random"):
            freezing.append({
                "arm": name,
                "freeze": arm.get("freeze"),
                "hunter": arm.get("hunter"),
                "vs": reference,
                "delta": {
                    "family_count": _delta(blocks["rq1"]["arms"][name]["family_count"], blocks["rq1"]["arms"][reference]["family_count"]),
                    "families_per_hour": _delta(blocks["rq1"]["arms"][name]["families_per_hour"], blocks["rq1"]["arms"][reference]["families_per_hour"]),
                    "brier": _delta(blocks["rq2"]["arms"][name]["brier"], blocks["rq2"]["arms"][reference]["brier"]),
                },
            })
        if arm.get("theory_from") or arm.get("select_from"):
            means = [
                _mean_surprise(cells[cell]["metrics"])
                for cell in arm_cells[name]
                if cells[cell]["metrics"] is not None
            ]
            pairing.append({
                "arm": name,
                "theory_from": arm.get("theory_from"),
                "select_from": arm.get("select_from"),
                "family_count": summarize(samples[name]["rq1"]["family_count"]),
                "mean_surprise": summarize(means),
            })
    return {"ciao": ciao, "freezing": freezing, "pairing": pairing}


def _mean_surprise(metrics: dict[str, Any] | None) -> float | None:
    """Mean surprise of one cell's valid records.

    ``run_metrics`` does not report that mean. ``rq2.curve`` is a windowed
    series, so it is not used as a substitute.
    """
    if not isinstance(metrics, dict):
        return None
    return None


def _delta(arm: dict[str, Any], reference: dict[str, Any]) -> float | None:
    left = arm["median"]
    right = reference["median"]
    if left is None or right is None:
        return None
    return left - right


def _stats(
    names: list[str],
    samples: dict[str, dict[str, dict[str, list]]],
    blocks: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for rq, metrics in RQ_METRICS.items():
        for metric in metrics:
            for index, left in enumerate(names):
                for right in names[index + 1 :]:
                    xs = samples[left][rq][metric]
                    ys = samples[right][rq][metric]
                    if not xs or not ys:
                        continue
                    test = mann_whitney_u(xs, ys)
                    summary_a = blocks[rq]["arms"][left][metric]
                    summary_b = blocks[rq]["arms"][right][metric]
                    rows.append({
                        "rq": rq,
                        "metric": metric,
                        "a": left,
                        "b": right,
                        "n_a": summary_a["n"],
                        "n_b": summary_b["n"],
                        "median_a": summary_a["median"],
                        "median_b": summary_b["median"],
                        "u": None if test is None else test["u"],
                        "p": None if test is None else test["p"],
                        "method": None if test is None else test["method"],
                        "a12": a12(xs, ys),
                    })
    rows.sort(key=lambda row: (row["rq"], row["metric"], row["a"], row["b"]))
    return rows


def _collect(bucket: dict[str, dict[str, list]], metrics: dict[str, Any] | None, kind: str) -> None:
    for rq, metrics_of in RQ_METRICS.items():
        for metric in metrics_of:
            value = _scalar(metrics, kind, rq, metric)
            if value is not None:
                bucket[rq][metric].append(value)


def _scalar(metrics: dict[str, Any] | None, kind: str, rq: str, metric: str) -> float | None:
    if metrics is None:
        return None
    if kind == "sqlancer":
        if rq == "rq1" and metric in ("family_count", "families_per_1000"):
            return _number(metrics.get(metric))
        return None
    section = metrics.get(rq)
    if not isinstance(section, dict):
        return None
    if metric == "first_family_minutes":
        elapsed = _dig(section, "first_family", "elapsed_s")
        number = _number(elapsed)
        return None if number is None else number / 60.0
    if metric == "high_surprise_share":
        return _number(_dig(section, "high_surprise", "share"))
    if metric == "teeth":
        teeth = section.get("teeth")
        return None if not isinstance(teeth, list) else float(len(teeth))
    if metric == "survival_rate":
        return _number(_dig(section, "conjectures", "survival_rate"))
    if metric == "prediction_accuracy":
        return _number(_dig(section, "predictions", "accuracy"))
    if metric == "pure_llm_accuracy":
        return _number(_dig(section, "pure_llm", "accuracy"))
    if metric == "invalid_rate":
        return _number(_dig(section, "invalid", "rate"))
    if metric == "theory_length_final":
        rows = section.get("theory_length")
        if not isinstance(rows, list) or not rows or not isinstance(rows[-1], dict):
            return None
        return _number(rows[-1].get("length"))
    if metric == "in_out_gap":
        return _number(_dig(section, "in_out", "gap"))
    if metric == "edits_accepted":
        return _number(_dig(section, "edits", "accepted"))
    if metric == "recall":
        return _number(_dig(section, "recall", "recall"))
    return _number(section.get(metric))


def _family_curve(metrics: dict[str, Any], kind: str) -> list[list[float]]:
    section = metrics.get("rq1")
    if not isinstance(section, dict):
        return []
    if kind == "old_coevodb":
        wall = _number(_dig(metrics, "run", "wall_s"))
        count = section.get("family_count")
        if wall is None or isinstance(count, bool) or not isinstance(count, (int, float)):
            return []
        return [[wall / 60.0, count]]
    families = section.get("families")
    if not isinstance(families, list):
        return []
    points: list[list[float]] = []
    cumulative = 0
    for family in families:
        if not isinstance(family, dict):
            continue
        cumulative += 1
        elapsed = _number(family.get("elapsed_s"))
        if elapsed is None:
            continue
        points.append([elapsed / 60.0, cumulative])
    return points


def _calibration_of(arm: str, cells: dict[str, dict[str, Any]]) -> list[list[dict[str, Any]]]:
    found = []
    for entry in cells.values():
        if entry["arm"] != arm or not isinstance(entry["metrics"], dict):
            continue
        section = entry["metrics"].get("rq2")
        if not isinstance(section, dict):
            continue
        bins = section.get("calibration")
        if isinstance(bins, list) and bins:
            found.append(bins)
    return found


def _merge_bins(groups: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    if not groups:
        return _empty_bins()
    merged = []
    for index in range(len(groups[0])):
        total = 0
        sum_p = 0.0
        sum_f = 0.0
        weight_p = 0
        weight_f = 0
        lo = groups[0][index]["lo"]
        hi = groups[0][index]["hi"]
        for bins in groups:
            item = bins[index]
            count = item.get("count")
            if isinstance(count, bool) or not isinstance(count, int):
                count = 0
            total += count
            if count and item.get("mean_p") is not None:
                sum_p += float(item["mean_p"]) * count
                weight_p += count
            if count and item.get("fail_rate") is not None:
                sum_f += float(item["fail_rate"]) * count
                weight_f += count
        merged.append({
            "lo": lo,
            "hi": hi,
            "count": total,
            "mean_p": None if weight_p == 0 else sum_p / weight_p,
            "fail_rate": None if weight_f == 0 else sum_f / weight_f,
        })
    return merged


def _empty_bins() -> list[dict[str, Any]]:
    rows = []
    last = len(CALIBRATION_EDGES) - 1
    for index in range(last):
        rows.append({
            "lo": CALIBRATION_EDGES[index],
            "hi": CALIBRATION_EDGES[index + 1],
            "count": 0,
            "mean_p": None,
            "fail_rate": None,
        })
    return rows


def _section_field(metrics: dict[str, Any], rq: str, field: str) -> Any:
    section = metrics.get(rq)
    if not isinstance(section, dict):
        return None
    value = section.get(field)
    if field in ("timeline", "theory_length") and not isinstance(value, list):
        return None
    return value


# ---- markdown -----------------------------------------------------------------------------------


def _markdown(report: dict[str, Any]) -> str:
    lines = [f"# {report['grid']}", ""]
    for key, heading, figures in RQ_SECTIONS:
        lines.extend(_rq_section(report, key, heading, figures))
    lines.extend(_baseline_section(report))
    lines.extend(_extras_section(report))
    return "\n".join(lines).rstrip() + "\n"


def _rq_section(report: dict[str, Any], key: str, heading: str, figures: tuple[str, ...]) -> list[str]:
    lines = [f"## {heading}", ""]
    block = report[key]
    if key == "rq5":
        lines.extend(_rq5_tables(block))
    else:
        metrics = block["metrics"]
        rows = [
            [name, *[_median_cell(summaries[metric]) for metric in metrics]]
            for name, summaries in block["arms"].items()
        ]
        lines.extend(_table(["arm", *metrics], rows))
        lines.append("")
        stats = [row for row in report["stats"] if row["rq"] == key]
        if stats:
            lines.extend(_table(
                ["metric", "a", "b", "p", "A12"],
                [[row["metric"], row["a"], row["b"], _fmt(row["p"]), _fmt(row["a12"])] for row in stats],
            ))
        else:
            lines.append("No pair has values for both arms.")
        lines.append("")
    for name in figures:
        lines.append(f"[figures/{name}](figures/{name})")
    lines.append("")
    return lines


def _rq5_tables(block: dict[str, Any]) -> list[str]:
    headers = ["arm", "freeze", "hunter", "vs", "family_count", "families_per_hour", "brier"]
    rows = []
    for item in block["freezing"]:
        delta = item["delta"]
        rows.append([
            str(item["arm"]),
            _fmt(item.get("freeze")),
            _fmt(item.get("hunter")),
            str(item["vs"]),
            _fmt(delta["family_count"]),
            _fmt(delta["families_per_hour"]),
            _fmt(delta["brier"]),
        ])
    if not rows:
        rows.append(["none", "n/a", "n/a", "n/a", "n/a", "n/a", "n/a"])
    lines = _table(headers, rows)
    lines.append("")
    pair_rows = []
    for item in block["pairing"]:
        pair_rows.append([
            str(item["arm"]),
            _fmt(item.get("theory_from")),
            _fmt(item.get("select_from")),
            _median_cell(item["family_count"]),
            _median_cell(item["mean_surprise"]),
        ])
    if not pair_rows:
        pair_rows.append(["none", "n/a", "n/a", "n/a", "n/a"])
    lines.extend(_table(["arm", "theory_from", "select_from", "family_count", "mean_surprise"], pair_rows))
    lines.append("")
    return lines


def _baseline_section(report: dict[str, Any]) -> list[str]:
    row = report["external"]["sqlancer"]
    return [
        "## 对照组",
        "",
        *_table(
            ["engine", "version", "checks", "family_count", "families_per_1000"],
            [[str(row["engine"]), str(row["version"]), str(row["checks"]), str(row["family_count"]), _fmt(row["families_per_1000"])]],
        ),
        "",
    ]


def _extras_section(report: dict[str, Any]) -> list[str]:
    extras = report.get("extras") if isinstance(report.get("extras"), dict) else {}
    lines = ["## 附加结果", ""]
    for key, title in (("dedup", "去重"), ("coverage", "覆盖度")):
        lines.append(f"### {title}")
        lines.append("")
        lines.append("无" if key not in extras else _describe(extras[key]))
        lines.append("")
    return lines


def _describe(value: Any) -> str:
    if isinstance(value, dict):
        parts = []
        for key in sorted(value, key=str):
            item = value[key]
            if isinstance(item, bool):
                parts.append(f"{key}={'true' if item else 'false'}")
            elif isinstance(item, (str, int, float)):
                parts.append(f"{key}={item}")
            elif item is None:
                parts.append(f"{key}=null")
        if parts:
            return ", ".join(parts)
        return "keys: " + ", ".join(sorted(str(key) for key in value))
    if isinstance(value, list):
        return f"{len(value)} rows"
    return "included"


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def _median_cell(summary: dict[str, Any]) -> str:
    return f"{_fmt(summary['median'])} (n={summary['n']})"


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


# ---- figures ------------------------------------------------------------------------------------


def _figures(directory: Path, report: dict[str, Any], *, known_present: bool) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    colors = {
        name: PALETTE[index % len(PALETTE)]
        for index, name in enumerate(report["arms"])
    }
    _fig_families(directory / "rq1_families.png", report, colors)
    _fig_surprise(directory / "rq2_surprise.png", report, colors)
    _fig_calibration(directory / "rq2_calibration.png", report, colors)
    _fig_llm(directory / "rq3_llm.png", report, colors)
    _fig_quality(directory / "rq4_quality.png", report, colors)
    _fig_ciao(directory / "rq5_ciao.png", report)
    _fig_recall(directory / "rq6_recall.png", report, colors, known_present)


def _fig_families(path: Path, report: dict[str, Any], colors: dict[str, str]) -> None:
    fig, ax = _axes("RQ1 cumulative families")
    ax.set_xlabel("minutes")
    ax.set_ylabel("cumulative families")
    seen: set[str] = set()
    for name, points in report["rq1"]["curves"].items():
        arm = report["cells"][name]["arm"]
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        if not xs:
            continue
        label = None if arm in seen else arm
        seen.add(arm)
        ax.plot(xs, ys, color=colors[arm], marker="o", markersize=3, linewidth=1.4, label=label)
    _legend(ax)
    _grid(ax)
    _savefig(fig, path)


def _fig_surprise(path: Path, report: dict[str, Any], colors: dict[str, str]) -> None:
    fig, ax = _axes("RQ2 surprise")
    reference = report["reference"]
    color = colors[reference]
    styles = ("-", "--", ":", "-.")
    window = None
    tooth_labeled = False
    drawn = 0
    for name in report["arms"][reference]["cells"]:
        metrics = report["cells"][name]["metrics"]
        if not isinstance(metrics, dict):
            continue
        section = metrics.get("rq2")
        if not isinstance(section, dict) or not isinstance(section.get("curve"), list):
            continue
        if window is None and isinstance(section.get("window"), int) and not isinstance(section.get("window"), bool):
            window = section["window"]
        curve = section["curve"]
        style = styles[drawn % len(styles)]
        labeled = False
        xs: list[int] = []
        ys: list[float] = []

        def flush() -> None:
            nonlocal labeled
            if not xs:
                return
            ax.plot(xs, ys, color=color, linestyle=style, linewidth=1.4, label=None if labeled else name)
            labeled = True
            xs.clear()
            ys.clear()

        for index, value in enumerate(curve):
            if value is None:
                flush()
                continue
            xs.append(index)
            ys.append(value)
        flush()
        teeth = section.get("teeth")
        if isinstance(teeth, list):
            tx = []
            ty = []
            for index in teeth:
                if isinstance(index, bool) or not isinstance(index, int):
                    continue
                if 0 <= index < len(curve) and curve[index] is not None:
                    tx.append(index)
                    ty.append(curve[index])
            if tx:
                ax.scatter(
                    tx, ty, color=color, marker="v", s=36, zorder=3,
                    label=None if tooth_labeled else "tooth",
                )
                tooth_labeled = True
        drawn += 1
    if window is not None:
        ax.set_title(f"RQ2 surprise (window {window})")
    ax.set_xlabel("window")
    ax.set_ylabel("mean surprise (bits)")
    _legend(ax)
    _grid(ax)
    _savefig(fig, path)


def _fig_calibration(path: Path, report: dict[str, Any], colors: dict[str, str]) -> None:
    fig, ax = _axes("RQ2 calibration")
    ax.plot([0, 1], [0, 1], color="#444444", linestyle="--", linewidth=1, label="diagonal")
    for name, bins in report["rq2"]["calibration"].items():
        xs = []
        ys = []
        for item in bins:
            if not item.get("count") or item.get("mean_p") is None or item.get("fail_rate") is None:
                continue
            xs.append(item["mean_p"])
            ys.append(item["fail_rate"])
        if xs:
            ax.plot(xs, ys, marker="o", color=colors[name], label=name)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("mean predicted probability")
    ax.set_ylabel("fail rate")
    _legend(ax)
    _savefig(fig, path)


def _fig_llm(path: Path, report: dict[str, Any], colors: dict[str, str]) -> None:
    timelines = report["rq3"]["timeline"]
    if not any(isinstance(rows, list) and rows for rows in timelines.values()):
        _empty(path, _NO_LLM)
        return
    fig, ax = _axes("RQ3 LLM prediction accuracy")
    for name, rows in timelines.items():
        if not isinstance(rows, list) or not rows:
            continue
        arm = report["cells"][name]["arm"]
        ax.plot(
            [row["seq"] for row in rows],
            [row["accuracy"] for row in rows],
            color=colors[arm],
            marker="o",
            markersize=3,
            label=name,
        )
    ax.set_xlabel("seq")
    ax.set_ylabel("cumulative accuracy")
    ax.set_ylim(0, 1)
    _legend(ax)
    _savefig(fig, path)


def _fig_quality(path: Path, report: dict[str, Any], colors: dict[str, str]) -> None:
    fig, ax = _axes("RQ4 invalid rate and duplicate rate")
    names = list(report["arms"])
    width = 0.36
    for index, name in enumerate(names):
        summaries = report["rq4"]["arms"][name]
        invalid = summaries["invalid_rate"]["median"]
        duplicate = summaries["duplicate_rate"]["median"]
        if invalid is not None:
            ax.bar(index - width / 2, invalid, width, color=colors[name])
        if duplicate is not None:
            ax.bar(index + width / 2, duplicate, width, color=colors[name], hatch="//")
    ax.set_xticks(range(len(names)), names)
    ax.set_ylabel("median")
    ax.set_ylim(bottom=0)
    ax.legend(
        handles=[
            Patch(facecolor="#666666", label="invalid_rate"),
            Patch(facecolor="#666666", hatch="//", label="duplicate_rate"),
        ],
        fontsize=8,
    )
    _savefig(fig, path)


def _fig_ciao(path: Path, report: dict[str, Any]) -> None:
    reference = report["reference"]
    cells = report["arms"][reference]["cells"]
    ciao = None if not cells else report["rq5"]["ciao"].get(cells[0])
    matrix = None if not isinstance(ciao, dict) else ciao.get("matrix")
    if not isinstance(matrix, list) or not matrix:
        _empty(path, _NO_CIAO)
        return
    fig, ax = _axes("RQ5 CIAO")
    numeric = [[math.nan if value is None else float(value) for value in row] for row in matrix]
    cmap = plt.get_cmap("YlOrRd").copy()
    cmap.set_bad("#f0f0f0")
    image = ax.imshow(numeric, cmap=cmap, aspect="equal")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    for row_index, row in enumerate(matrix):
        for col_index, value in enumerate(row):
            if value is None:
                continue
            ax.text(col_index, row_index, f"{float(value):.2f}", ha="center", va="center", color="black", fontsize=8)
    batches = [str(item) for item in ciao.get("batches", [])]
    generations = [str(item) for item in ciao.get("generations", [])]
    ax.set_xticks(range(len(batches)), batches)
    ax.set_yticks(range(len(generations)), generations)
    ax.set_xlabel("batch")
    ax.set_ylabel("theory generation")
    _savefig(fig, path)


def _fig_recall(path: Path, report: dict[str, Any], colors: dict[str, str], known_present: bool) -> None:
    if not known_present:
        _empty(path, _NO_RECALL)
        return
    fig, ax = _axes("RQ6 recall")
    names = list(report["arms"])
    for index, name in enumerate(names):
        median = report["rq6"]["arms"][name]["recall"]["median"]
        if median is None:
            continue
        ax.bar(index, median, color=colors[name])
    ax.set_xticks(range(len(names)), names)
    ax.set_ylabel("median recall")
    ax.set_ylim(0, 1)
    _savefig(fig, path)


def _axes(title: str) -> tuple[Any, Any]:
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI, constrained_layout=True)
    ax.set_title(title)
    return fig, ax


def _empty(path: Path, message: str) -> None:
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("#666666")
    ax.text(0.5, 0.55, message, ha="center", va="center", fontsize=14, color="#222222")
    ax.set_xlabel(" ")
    ax.set_ylabel(" ")
    _savefig(fig, path)


def _legend(ax: Any) -> None:
    _handles, labels = ax.get_legend_handles_labels()
    if labels:
        ax.legend(loc="best", fontsize=8)


def _grid(ax: Any) -> None:
    ax.grid(True, axis="both", linestyle=":", linewidth=0.6, color="#cccccc")


def _savefig(fig: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fig.savefig(path, dpi=DPI, facecolor="white")
    finally:
        plt.close(fig)


def _write(destination: Path, report: dict[str, Any], *, known_present: bool) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, sort_keys=True, indent=1, ensure_ascii=True) + "\n"
    (destination / "report.json").write_text(text, encoding="utf-8", newline="\n")
    (destination / "report.md").write_text(_markdown(report), encoding="utf-8", newline="\n")
    _figures(destination / "figures", report, known_present=known_present)


# ---- inputs -------------------------------------------------------------------------------------


def _load_grid(root: Path) -> dict[str, Any]:
    path = root / "grid.json"
    data = _read_json(path, "grid.json")
    if not isinstance(data, dict):
        raise ValueError("grid.json: expected an object")
    missing = [key for key in ("schema", "name", "reference", "seeds", "repeats", "window", "arms") if key not in data]
    if missing:
        raise ValueError(f"grid.json: missing {', '.join(missing)}")
    if data.get("schema") != SCHEMA:
        raise ValueError(f"schema: expected {SCHEMA}, got {data.get('schema')!r}")
    arms = data["arms"]
    if isinstance(arms, str) or not isinstance(arms, list) or not arms:
        raise ValueError(f"arms: expected a non-empty list, got {arms!r}")
    names = []
    for arm in arms:
        if not isinstance(arm, dict) or "name" not in arm or "kind" not in arm:
            raise ValueError(f"arms: expected name and kind, got {arm!r}")
        names.append(arm["name"])
    if len(names) != len(set(names)):
        raise ValueError("arms: duplicate name")
    if data["reference"] not in names:
        raise ValueError(f"reference: unknown arm {data['reference']!r}")
    return data


def _load_known(config: dict[str, Any]) -> Any:
    path = config.get("known")
    if path is None:
        return None
    if not isinstance(path, str) or path == "":
        raise ValueError(f"known: expected a file path, got {path!r}")
    return _read_json(Path(path), "known")


def _window(config: dict[str, Any]) -> int:
    value = config["window"]
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"window: expected an integer >= 1, got {value!r}")
    return value


def _extras(root: Path, dedup: str | Path | None, coverage: str | Path | None) -> dict[str, Any]:
    found: dict[str, Any] = {}
    for key, given in (("dedup", dedup), ("coverage", coverage)):
        if given is not None:
            found[key] = _read_json(Path(given), key)
            continue
        path = root / "extras" / f"{key}.json"
        if path.is_file():
            found[key] = _read_json(path, key)
    return found


def _iter_cells(config: dict[str, Any]):
    for rep in range(int(config["repeats"])):
        for seed in config["seeds"]:
            for arm in config["arms"]:
                if arm.get("kind") == "sqlancer":
                    continue
                yield arm, int(seed), int(rep)


def _metrics_for(kind: str, directory: Path, *, known: Any, prices: Any, window: int) -> dict[str, Any]:
    if kind in _RUN_KINDS:
        return run_metrics(directory, known=known, prices=prices, window=window)
    if kind == "old_coevodb":
        return _old_cell_metrics(directory)
    raise ValueError(f"kind: {kind!r} has no cell")


def _old_cell_metrics(directory: Path) -> dict[str, Any]:
    """``old_metrics`` for one cell.

    A killed original run with zero reports never creates ``bugs.jsonl``
    (``old_no_llm`` records ``reports: 0`` in that case). ``old_metrics``
    requires the file, so the same ``old_run.json`` is scored against an empty
    file in a temporary directory. The cell itself is not written.
    """
    meta_path = directory / "old_run.json"
    if not meta_path.is_file():
        return old_metrics(directory)
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return old_metrics(directory)
    run_dir = meta.get("run_dir") if isinstance(meta, dict) else None
    if not isinstance(run_dir, str) or run_dir == "":
        return old_metrics(directory)
    relative = Path(run_dir)
    if relative.is_absolute() or any(part == ".." for part in relative.parts):
        return old_metrics(directory)
    if (directory / relative / "bugs.jsonl").is_file():
        return old_metrics(directory)
    if meta.get("reports") not in (0, None):
        return old_metrics(directory)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        target = root / relative
        target.mkdir(parents=True)
        (target / "bugs.jsonl").write_text("", encoding="utf-8", newline="\n")
        (root / "old_run.json").write_bytes(meta_path.read_bytes())
        return old_metrics(root)


def _sqlancer_row(arm: dict[str, Any]) -> dict[str, Any]:
    engine = arm.get("engine") or "duckdb"
    return sqlancer.metrics(sqlancer.load(arm.get("summary")), engine=engine)


def _read_cell(directory: Path) -> dict[str, Any]:
    path = directory / "cell.json"
    data = _read_json(path, "cell.json")
    if not isinstance(data, dict):
        raise ValueError(f"cell.json: expected an object: {path}")
    if data.get("status") not in ("done", "failed"):
        raise ValueError(f"cell.json: status must be done or failed: {path}")
    return data


def _cell_dir(root: Path, arm: str, seed: int, rep: int) -> Path:
    return root / "cells" / arm / f"s{seed}-r{rep}"


def _cell_name(arm: str, seed: int, rep: int) -> str:
    return f"{arm}/s{seed}-r{rep}"


def _read_json(path: Path, where: str) -> Any:
    if not path.is_file():
        raise ValueError(f"{where}: file does not exist: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{where}: not JSON: {path}") from exc


def _dig(obj: Any, *keys: str) -> Any:
    current = obj
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _ascii(text: object) -> str:
    return str(text).encode("ascii", "replace").decode("ascii")


if __name__ == "__main__":
    sys.exit(main())
