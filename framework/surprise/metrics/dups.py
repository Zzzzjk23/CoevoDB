"""Identity keys shared by the new families and the old system's bug reports.

A fix set is the identity. Without one, the new system uses the failure's
shape and the old system keeps its own sigma key, which never collides with
another report.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from surprise.theory.workbench import Workbench


def identity_key(
    engine: str,
    fix_set: Iterable[str],
    fail_kind: str | None,
    error_class: str | None,
    behavior_shape: str | None,
) -> str:
    """``fix|<engine>|<sorted fixes>``, or the shape key when ``fix_set`` is empty."""
    fixes = list(fix_set)
    if fixes:
        return "fix|" + engine + "|" + ",".join(sorted(fixes))
    return "shape|{engine}|{fail}|{error}|{shape}".format(
        engine=engine,
        fail=fail_kind or "-",
        error=error_class or "-",
        shape=behavior_shape or "-",
    )


def new_families(store_dir: str | Path) -> list[dict[str, Any]]:
    """One dict per family in ``store_dir``.

    Families that own a failure come first, in the order of that failure in
    ``partition()``. A family that owns nothing follows, in ``families()`` order.
    The key is the identity of the family's first hypothesis.
    """
    bench = Workbench.open(store_dir)
    grouped = bench.families()
    owned = bench.partition()
    first_of: dict[str, str] = {}
    for record_id, family in owned.items():
        if family is not None and family not in first_of:
            first_of[family] = record_id
    order = {record_id: index for index, record_id in enumerate(owned)}
    rows: list[dict[str, Any]] = []
    for name, hypothesis_ids in grouped.items():
        first = bench.theory.get(hypothesis_ids[0])
        rows.append(
            {
                "family": name,
                "hypotheses": list(hypothesis_ids),
                "engine": first.engine,
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


def _strings(value: object, where: str) -> list[str]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{where}: expected a list of strings, got {value!r}")
    if not all(isinstance(item, str) for item in value):
        raise ValueError(f"{where}: expected strings, got {value!r}")
    return list(value)


def _one_report(payload: object, line_no: int) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"bugs.jsonl line {line_no}: expected an object, got {type(payload).__name__}")
    signature = payload.get("signature")
    if signature is None:
        engine = "duckdb"
        fix_kind = None
        fix_set: list[str] = []
    elif isinstance(signature, dict):
        engine = signature.get("engine")
        if not isinstance(engine, str) or engine == "":
            raise ValueError(f"bugs.jsonl line {line_no}: signature.engine is missing")
        fix_kind = signature.get("fix_kind")
        if fix_kind is not None and not isinstance(fix_kind, str):
            raise ValueError(f"bugs.jsonl line {line_no}: fix_kind must be a string, got {fix_kind!r}")
        fix_set = _strings(signature.get("fix_set", []), f"bugs.jsonl line {line_no} fix_set")
    else:
        raise ValueError(f"bugs.jsonl line {line_no}: signature must be an object or null")
    candidate = payload.get("candidate")
    if not isinstance(candidate, dict) or not isinstance(candidate.get("kind"), str):
        raise ValueError(f"bugs.jsonl line {line_no}: candidate.kind is missing")
    root_key = payload.get("root_key")
    if not isinstance(root_key, str):
        raise ValueError(f"bugs.jsonl line {line_no}: root_key must be a string, got {root_key!r}")
    if signature is not None and fix_kind in ("single", "minimal_set") and fix_set:
        key = identity_key(engine, fix_set, None, None, None)
    else:
        key = "sigma|" + root_key
    return {
        "root_key": root_key,
        "engine": engine,
        "fix_kind": fix_kind,
        "fix_set": fix_set,
        "origin": payload.get("origin"),
        "iteration": payload.get("iteration"),
        "kind": candidate["kind"],
        "key": key,
    }


def old_reports(bugs_jsonl: str | Path) -> list[dict[str, Any]]:
    """Reports in an old ``bugs.jsonl``. A truncated last line is ignored; a broken earlier line is not."""
    lines = Path(bugs_jsonl).read_text(encoding="utf-8").splitlines()
    reports: list[dict[str, Any]] = []
    last = len(lines) - 1
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            if index == last:
                continue
            raise ValueError(f"bugs.jsonl line {index + 1}: invalid JSON") from None
        reports.append(_one_report(payload, index + 1))
    return reports


def duplicate_rate(keys: Sequence[str]) -> float | None:
    """Share of ``keys`` that repeat an earlier key. An empty sequence is ``None``."""
    count = len(keys)
    if count == 0:
        return None
    return (count - len(set(keys))) / count


def _json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=True, indent=1) + "\n"


def compare(run_dir: str | Path, old_dir: str | Path) -> dict[str, Any]:
    """Families of ``run_dir/theory`` beside the reports of the old run pinned in ``old_dir``."""
    old_root = Path(old_dir)
    meta = json.loads((old_root / "old_run.json").read_text(encoding="utf-8"))
    families = new_families(Path(run_dir) / "theory")
    reports = old_reports(old_root / meta["run_dir"] / "bugs.jsonl")
    return {
        "new": {"families": families, "rate": duplicate_rate([row["key"] for row in families])},
        "old": {"reports": reports, "rate": duplicate_rate([row["key"] for row in reports])},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m surprise.metrics.dups")
    parser.add_argument("--new", required=True, help="run directory whose theory/ is read")
    parser.add_argument("--old", required=True, help="directory that holds old_run.json")
    parser.add_argument("--out", help="write the JSON here instead of stdout")
    args = parser.parse_args(argv)
    text = _json(compare(args.new, args.old))
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
