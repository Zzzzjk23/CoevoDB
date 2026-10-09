"""Command line for the feature package."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from surprise.harness.contracts import SqlCase
from surprise.harness.oracles.registry import runner_factory_for

from .extract import extract
from .registry import Registry, default_registry
from .units import unit_parts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m surprise.features")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("vocab", help="print the base vocabulary digest and entry count")
    sub.add_parser("phi", help="read one case from stdin and print its phi")
    corpus = sub.add_parser("corpus", help="unit distribution of a seed corpus")
    corpus.add_argument("--corpus", required=True, help="path of a JSON list of seeds")
    corpus.add_argument("--out", help="write the report as sorted-key JSON")
    corpus.add_argument("--limit", type=int, help="use only the first N seeds")
    args = parser.parse_args(argv)
    if args.command == "vocab":
        registry = default_registry()
        print(f"{registry.digest()} {len(registry.ids())}")
        return 0
    if args.command == "phi":
        return _phi_command()
    if args.command == "corpus":
        return _corpus_command(args)
    return 2


def _phi_command() -> int:
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else None
    except json.JSONDecodeError as exc:
        print(f"invalid JSON: {exc.msg}", file=sys.stderr)
        return 2
    if not isinstance(data, dict):
        print("expected a JSON object", file=sys.stderr)
        return 2
    unknown = sorted(set(data) - {"case", "layers", "registry"})
    if unknown or "case" not in data:
        print("expected keys case, and optionally layers and registry", file=sys.stderr)
        return 2
    try:
        case = SqlCase.from_dict(data["case"])
    except (ValueError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    layers = data.get("layers", ["ast", "plan", "data"])
    if not isinstance(layers, list) or any(not isinstance(item, str) for item in layers):
        print("layers must be a list of strings", file=sys.stderr)
        return 2
    registry = None
    if "registry" in data:
        path = data["registry"]
        if not isinstance(path, str) or not path:
            print("registry must be a file path", file=sys.stderr)
            return 2
        try:
            registry = Registry.load(path)
        except (OSError, ValueError, json.JSONDecodeError, TypeError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
    try:
        phi = extract(case, layers=tuple(layers), registry=registry)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(phi.to_dict(), sort_keys=True, separators=(",", ":")))
    return 0


def _corpus_command(args) -> int:
    if args.limit is not None and args.limit < 0:
        print("limit must be zero or greater", file=sys.stderr)
        return 2
    try:
        payload = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"corpus: {exc}", file=sys.stderr)
        return 2
    if not isinstance(payload, list):
        print("corpus must be a JSON list", file=sys.stderr)
        return 2
    seeds = payload if args.limit is None else payload[: args.limit]
    try:
        report = build_corpus_report(seeds)
    except (ValueError, TypeError, KeyError) as exc:
        print(f"corpus: {exc}", file=sys.stderr)
        return 2
    if args.out:
        text = json.dumps(report, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
        try:
            Path(args.out).write_text(text, encoding="utf-8")
        except OSError as exc:
            print(f"corpus: {exc}", file=sys.stderr)
            return 2
    sys.stdout.write(_summary(report) + "\n")
    return 0


def build_corpus_report(seeds: list) -> dict:
    """Distribution of phi over ``seeds``. No timestamps and no durations."""
    by_engine: Counter = Counter()
    layers: dict[str, Counter] = {name: Counter() for name in ("ast", "plan", "data")}
    units: Counter = Counter()
    constructs: Counter = Counter()
    plan_classes: Counter = Counter()
    data_classes: Counter = Counter()
    factories: dict[str, object | None] = {}
    for seed in seeds:
        case = _case_of(seed)
        by_engine[case.engine] += 1
        if case.engine not in factories:
            factories[case.engine] = _factory_for(case.engine)
        factory = factories[case.engine]
        if factory is None:
            phi = extract(case, layers=("ast",))
        else:
            phi = extract(case, runner_factory=factory)
        for name in ("ast", "plan", "data"):
            layers[name][phi.layers[name]] += 1
        construct, plan_class, data_class = unit_parts(phi)
        units[f"{phi.engine}|{construct}|{plan_class}|{data_class}"] += 1
        constructs[construct] += 1
        plan_classes[plan_class] += 1
        data_classes[data_class] += 1
    registry = default_registry()
    leaves = sum(1 for feature_id in registry.ids() if registry.get(feature_id).kind == "leaf")
    return {
        "total": len(seeds),
        "by_engine": dict(by_engine),
        "layers": {name: _positive(layers[name]) for name in ("ast", "plan", "data")},
        "units": dict(units),
        "distinct_units": len(units),
        "constructs": dict(constructs),
        "plan_classes": dict(plan_classes),
        "data_classes": dict(data_classes),
        "vocab": {"digest": registry.digest(), "entries": len(registry.ids()), "leaves": leaves},
    }


def _case_of(seed) -> SqlCase:
    if not isinstance(seed, dict):
        raise ValueError("each seed must be an object")
    for key in ("engine", "query", "setup_sqls"):
        if key not in seed:
            raise ValueError(f"seed is missing {key}")
    return SqlCase(engine=seed["engine"], setup=tuple(seed["setup_sqls"]), query=seed["query"])


def _factory_for(engine: str):
    try:
        return runner_factory_for(engine)
    except ValueError:
        return None


def _positive(counter: Counter) -> dict:
    return {key: counter[key] for key in counter if counter[key] > 0}


def _summary(report: dict) -> str:
    lines = [f"total {report['total']}"]
    engines = " ".join(f"{name}={count}" for name, count in sorted(report["by_engine"].items()))
    lines.append(f"engines {engines}".rstrip())
    for name in ("ast", "plan", "data"):
        counts = report["layers"].get(name, {})
        parts = " ".join(f"{status}={counts[status]}" for status in sorted(counts))
        lines.append(f"layer {name} {parts}".rstrip())
    lines.append("top_units")
    ranked = sorted(report["units"].items(), key=lambda item: (-item[1], item[0]))[:10]
    for key, count in ranked:
        lines.append(f"{count} {key}")
    return "\n".join(lines).encode("ascii", "backslashreplace").decode("ascii")


if __name__ == "__main__":
    sys.exit(main())
