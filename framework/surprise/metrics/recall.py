"""Recall of known bugs: certify each one here, then match its identity to a run's families."""

from __future__ import annotations

import argparse
import importlib.metadata as importlib_metadata
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from surprise.features.registry import Registry
from surprise.harness.contracts import SqlCase
from surprise.harness.cve.certify import certify
from surprise.harness.cve.shape import behavior_shape

from .dups import identity_key, new_families, run_registry


def _engine_versions() -> dict[str, str]:
    # importlib, not ``import duckdb``: a directory of that name at the repo root masks the package.
    return {
        "duckdb": importlib_metadata.version("duckdb"),
        "datafusion": importlib_metadata.version("datafusion"),
    }


def _fix_set(label: Any) -> list[str] | None:
    profile = label.cve.get("profile") if isinstance(label.cve, dict) else None
    if not isinstance(profile, dict) or profile.get("status") != "ran":
        return None
    return list(profile.get("fix_set") or [])


def known_bugs(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Certify each item in this interpreter. ``key`` is set only for a profiled failure."""
    certified: list[dict[str, Any]] = []
    for item in items:
        case = SqlCase.from_dict(item["case"])
        label = certify(case, item["oracle"], diagnose=True, rewrite_rule=item["rule"])
        fix_set = _fix_set(label)
        key = None
        if label.y == "fail" and fix_set is not None:
            key = identity_key(
                case.engine,
                fix_set,
                label.fail_kind,
                label.identity.error_class,
                behavior_shape(label.identity.behavior),
            )
        certified.append(
            {
                "name": item["name"],
                "oracle": item["oracle"],
                "y": label.y,
                "fail_kind": label.fail_kind,
                "invalid_reason": label.invalid_reason,
                "fix_set": fix_set,
                "key": key,
            }
        )
    return {"engines": _engine_versions(), "items": certified}


def score(
    known: Mapping[str, Any],
    store_dir: str | Path,
    registry: Registry | None = None,
) -> dict[str, Any]:
    """Which profiled failures in ``known`` share an identity with a family in ``store_dir``.

    The same inputs produce the same dict, including key order.
    """
    families = new_families(store_dir, registry=registry)
    present = [item for item in known["items"] if item["y"] == "fail" and item["key"] is not None]
    recalled: list[str] = []
    missed: list[str] = []
    first: dict[str, str | None] = {}
    for item in present:
        match = next((family for family in families if family["key"] == item["key"]), None)
        if match is None:
            missed.append(item["name"])
            continue
        recalled.append(item["name"])
        first[item["name"]] = match["first_record"]
    return {
        "known": [item["name"] for item in present],
        "recalled": recalled,
        "missed": missed,
        "recall": None if not present else len(recalled) / len(present),
        "families": len(families),
        "first": first,
    }


def _json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=True, indent=1) + "\n"


def _read_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m surprise.metrics.recall")
    sub = parser.add_subparsers(dest="command", required=True)
    known_cmd = sub.add_parser("known", help="certify a JSON list of cases")
    known_cmd.add_argument("--cases", required=True)
    known_cmd.add_argument("--out", required=True)
    score_cmd = sub.add_parser("score", help="score a known-bug file against a run")
    score_cmd.add_argument("--known", required=True)
    score_cmd.add_argument("--run", required=True)
    score_cmd.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "known":
        payload = known_bugs(_read_json(args.cases))
    else:
        payload = score(
            _read_json(args.known),
            Path(args.run) / "theory",
            registry=run_registry(args.run),
        )
    Path(args.out).write_text(_json(payload), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
