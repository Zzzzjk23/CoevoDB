"""Replay parsed upstream regression tests and compare oracle labels.

Measurement only: labels come from the harness, nothing is written to a
ledger, and no LLM is called. The DuckDB version is read from package
metadata so a checkout directory named ``duckdb`` cannot shadow the install.
The same seeds and oracles produce the same labels.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from seeds.store import SeedCorpus

from surprise.harness.contracts import ORACLE_IDS, SqlCase
from surprise.harness.cve.certify import certify

_CORPUS = Path(__file__).resolve().parents[2] / "seeds" / "corpus.json"


def select(prefix: str = "duckdb:test/", limit: int | None = None) -> list[dict[str, Any]]:
    """Corpus entries whose ``source`` starts with ``prefix``, in file order."""
    if not isinstance(prefix, str):
        raise ValueError(f"prefix: expected a string, got {prefix!r}")
    limit = _limit(limit)
    chosen = [seed.to_dict() for seed in SeedCorpus.load(_CORPUS).seeds if seed.source.startswith(prefix)]
    if limit is not None:
        return chosen[:limit]
    return chosen


def replay(
    seeds: Sequence[dict[str, Any]],
    oracles: Sequence[str],
    *,
    prefix: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Label every seed with every oracle. ``certify`` uses its default arguments.

    ``prefix`` and ``limit`` are recorded as given so two replays can be
    checked for the same selection. They do not filter ``seeds`` again.
    """
    chosen = _oracles(oracles)
    items: list[dict[str, Any]] = []
    for index, seed in enumerate(seeds):
        case = SqlCase(
            engine="duckdb",
            setup=tuple(seed["setup_sqls"]),
            query=seed["query"],
            predicate=None,
        )
        for oracle in chosen:
            label = certify(case, oracle)
            items.append(
                {
                    "index": index,
                    "source": seed["source"],
                    "oracle": oracle,
                    "y": label.y,
                    "fail_kind": label.fail_kind,
                    "invalid_reason": label.invalid_reason,
                }
            )
    return {
        "engine": "duckdb",
        "version": _duckdb_version(),
        "prefix": prefix,
        "limit": _limit(limit) if limit is not None else None,
        "oracles": chosen,
        "items": items,
    }


def compare(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Label counts and the three failure lists for one pair of replays.

    ``old`` is the older engine and ``new`` is the newer one. Both must name
    the same engine, prefix, limit, and oracles. ``fail_old_pass_new`` failed
    on the old version and passed on the new one. ``fail_both`` failed on
    both. ``fail_new_only`` failed only on the new version.
    """
    _require_same_scope(old, new)
    per_oracle: dict[str, dict[str, Any]] = {}
    for oracle in old["oracles"]:
        old_y = _index_labels(old, oracle)
        new_y = _index_labels(new, oracle)
        if set(old_y) != set(new_y):
            raise ValueError(f"{oracle}: the two replays do not cover the same seeds")
        fail_old_pass_new = []
        fail_both = []
        fail_new_only = []
        for index in sorted(old_y):
            before = old_y[index]
            after = new_y[index]
            if before == "fail" and after == "pass":
                fail_old_pass_new.append(index)
            if before == "fail" and after == "fail":
                fail_both.append(index)
            if after == "fail" and before != "fail":
                fail_new_only.append(index)
        per_oracle[oracle] = {
            "old": _counts(old_y.values()),
            "new": _counts(new_y.values()),
            "fail_old_pass_new": fail_old_pass_new,
            "fail_both": fail_both,
            "fail_new_only": fail_new_only,
        }
    return {
        "old_version": old["version"],
        "new_version": new["version"],
        "oracles": per_oracle,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m surprise.metrics.coverage")
    sub = parser.add_subparsers(dest="command", required=True)
    run_cmd = sub.add_parser("run", help="replay seeds on the DuckDB in this interpreter")
    run_cmd.add_argument("--out", required=True)
    run_cmd.add_argument("--prefix", default="duckdb:test/")
    run_cmd.add_argument("--limit", type=int, default=None)
    run_cmd.add_argument("--oracle", action="append", default=None)
    compare_cmd = sub.add_parser("compare", help="compare an older replay with a newer one")
    compare_cmd.add_argument("old")
    compare_cmd.add_argument("new")
    compare_cmd.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "run":
        oracles = _oracles(args.oracle)
        seeds = select(args.prefix, args.limit)
        payload = replay(seeds, oracles, prefix=args.prefix, limit=args.limit)
    else:
        payload = compare(_read_json(args.old), _read_json(args.new))
    Path(args.out).write_text(_json(payload), encoding="utf-8", newline="\n")
    return 0


def _oracles(names: Sequence[str] | None) -> list[str]:
    if not names:
        return list(ORACLE_IDS)
    found: list[str] = []
    allowed = set(ORACLE_IDS)
    for name in names:
        if name not in allowed:
            raise ValueError(f"oracle: must be one of {ORACLE_IDS}, got {name!r}")
        found.append(name)
    return found


def _index_labels(payload: dict[str, Any], oracle: str) -> dict[int, str]:
    found: dict[int, str] = {}
    for item in payload["items"]:
        if item["oracle"] != oracle:
            continue
        index = item["index"]
        if index in found:
            raise ValueError(f"{oracle}: duplicate seed index {index}")
        found[index] = item["y"]
    return found


def _counts(labels: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    return counts


def _require_same_scope(old: dict[str, Any], new: dict[str, Any]) -> None:
    for key in ("engine", "prefix", "limit", "oracles"):
        if old.get(key) != new.get(key):
            raise ValueError(f"replay results differ in {key}: {old.get(key)!r} vs {new.get(key)!r}")


def _duckdb_version() -> str:
    try:
        return importlib.metadata.version("duckdb")
    except importlib.metadata.PackageNotFoundError as exc:
        raise RuntimeError("duckdb is not installed") from exc


def _limit(value: int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"limit: expected an integer >= 0, got {value!r}")
    return value


def _read_json(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return payload


def _json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=True, indent=1) + "\n"


if __name__ == "__main__":
    sys.exit(main())
