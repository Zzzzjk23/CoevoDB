"""Resident phi-extraction process: one JSON request per stdin line."""

from __future__ import annotations

import argparse
import json
import sys

from surprise.features.extract import extract
from surprise.features.registry import Registry
from surprise.harness.contracts import SqlCase


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="surprise.hunter.phi_worker")
    parser.add_argument("--registry", default=None)
    args = parser.parse_args(argv)
    registry = None if args.registry is None else Registry.load(args.registry)
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        req_id = None
        try:
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError("request must be a JSON object")
            req_id = payload["id"]
            case = SqlCase.from_dict(payload["case"])
            phi = extract(case) if registry is None else extract(case, registry=registry)
            reply = {"id": req_id, "phi": phi.to_dict()}
        except Exception as exc:  # noqa: BLE001 - every failure is an error reply
            reply = {"id": req_id, "error": f"{type(exc).__name__}: {exc}"}
        sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
