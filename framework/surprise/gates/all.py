"""Run every session gate in order.

Usage (from ``framework/``)::

    python -m surprise.gates.all

Each ``gates/sNN.py`` runs as its own process (``python -m
surprise.gates.sNN``) so one gate cannot leak imports or state into the next.
All gates run even when an earlier one fails. Exit code 0 = every gate passed.
Output is ASCII only: the executors' shell garbles anything else.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

GATES_DIR = Path(__file__).resolve().parent
FRAMEWORK = GATES_DIR.parents[1]
GATE_RE = re.compile(r"^s\d{2}\.py$")


def gate_names() -> list[str]:
    return sorted(p.stem for p in GATES_DIR.iterdir() if GATE_RE.match(p.name))


def main() -> int:
    names = gate_names()
    if not names:
        print("no gates found in", GATES_DIR)
        return 1
    results: list[tuple[str, int]] = []
    for name in names:
        print(f"=== gate {name} ===", flush=True)
        proc = subprocess.run(
            [sys.executable, "-m", f"surprise.gates.{name}"], cwd=FRAMEWORK)
        results.append((name, proc.returncode))
    print("=== summary ===")
    for name, code in results:
        print(f"{name}: {'PASS' if code == 0 else f'FAIL (exit {code})'}")
    failed = [name for name, code in results if code != 0]
    print(f"GATES: {'PASS' if not failed else 'FAIL'}"
          f" ({len(results) - len(failed)}/{len(results)} passed)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
