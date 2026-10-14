"""Resident phi-extraction process: one JSON request per stdin line."""

from __future__ import annotations

import json
import sys

from surprise.features.extract import extract
from surprise.harness.contracts import SqlCase


def main() -> None:
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
            phi = extract(case)
            reply = {"id": req_id, "phi": phi.to_dict()}
        except Exception as exc:  # noqa: BLE001 - every failure is an error reply
            reply = {"id": req_id, "error": f"{type(exc).__name__}: {exc}"}
        sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
