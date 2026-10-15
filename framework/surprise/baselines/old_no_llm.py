"""Run the old system in ``no_llm`` mode for a wall-clock budget.

The old entry point is a child process. This module does not import it.
``command`` is the argv of that child; tests replace it with a stand-in.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from surprise.metrics.dups import old_reports

FRAMEWORK = Path(__file__).resolve().parents[2]


def command(out: Path, *, seed: int, python: str | None) -> list[str]:
    """Argv of one old ``no_llm`` run. ``out / "results"`` is the results root."""
    interpreter = sys.executable if python is None else python
    return [
        interpreter,
        str(FRAMEWORK / "main.py"),
        "--engine",
        "duckdb",
        "--mode",
        "no_llm",
        "--iterations",
        "100000000",
        "--stagnation-limit",
        "100000000",
        "--seed",
        str(seed),
        "--results-root",
        str(out / "results"),
        "--label",
        f"s08_old_s{seed}",
    ]


def _prepare_out(out: Path) -> None:
    if out.exists():
        if not out.is_dir() or any(out.iterdir()):
            raise ValueError(f"{out} exists and is not empty")
        return
    out.mkdir(parents=True)


def _kill_tree(proc: subprocess.Popen[bytes]) -> None:
    """Stop ``proc`` and every process it started, then wait until it is gone."""
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        except OSError:
            proc.kill()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=30)


def _wait(proc: subprocess.Popen[bytes], timeout_s: float) -> str:
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        return "killed"
    return "exited"


def _child_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("DEEPSEEK_API_KEY", None)
    return env


def _run_dir(out: Path) -> str:
    results = out / "results"
    if not results.is_dir():
        raise RuntimeError(f"{results} does not exist")
    children = [path for path in results.iterdir() if path.is_dir()]
    if len(children) != 1:
        raise RuntimeError(f"expected one run directory under {results}, found {len(children)}")
    return children[0].relative_to(out).as_posix()


def _json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=True, indent=1) + "\n"


def run(out: str | Path, *, minutes: float, seed: int, python: str | None = None) -> dict[str, Any]:
    """Run until the child exits or ``minutes`` have passed. Write ``old_run.json`` and return it."""
    destination = Path(out)
    _prepare_out(destination)
    argv = command(destination, seed=seed, python=python)
    log_path = destination / "console.txt"
    started = datetime.now(timezone.utc)
    clock = time.monotonic()
    popen: dict[str, Any] = {}
    if os.name != "nt":
        popen["start_new_session"] = True
    with log_path.open("wb") as handle:
        proc = subprocess.Popen(
            argv,
            cwd=str(FRAMEWORK),
            env=_child_env(),
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=subprocess.STDOUT,
            **popen,
        )
        ended = _wait(proc, minutes * 60.0)
    finished = datetime.now(timezone.utc)
    run_dir = _run_dir(destination)
    bugs = destination / run_dir / "bugs.jsonl"
    # A killed run may not have archived a bug yet, so the file was never created.
    reports = len(old_reports(bugs)) if bugs.is_file() else 0
    payload = {
        "mode": "no_llm",
        "engine": "duckdb",
        "seed": seed,
        "minutes": minutes,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "wall_s": time.monotonic() - clock,
        "ended": ended,
        "returncode": proc.returncode,
        "run_dir": run_dir,
        "reports": reports,
    }
    (destination / "old_run.json").write_text(_json(payload), encoding="utf-8", newline="\n")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m surprise.baselines.old_no_llm")
    parser.add_argument("--out", required=True)
    parser.add_argument("--minutes", required=True, type=float)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--python", default=None)
    args = parser.parse_args(argv)
    run(args.out, minutes=args.minutes, seed=args.seed, python=args.python)
    sys.stdout.write((Path(args.out) / "old_run.json").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
