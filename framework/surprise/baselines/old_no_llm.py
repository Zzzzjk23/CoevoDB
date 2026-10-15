"""Run the old system for a wall-clock budget.

The old entry point is a child process. This module does not import it.
``command`` is the argv of that child; tests replace it with a stand-in.

``mode="no_llm"`` is the S8 baseline: the argv, the label and ``old_run.json``
stay as they were, and the child environment has no ``DEEPSEEK_API_KEY``.
Any other mode keeps that variable and labels the run ``s11_old_<mode>_s<seed>``.
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

# The choices of ``main.py --mode``. ``no_llm`` is the S8 baseline.
OLD_MODES = (
    "full",
    "random_category",
    "no_llm",
    "coverage_only",
    "dce_only",
    "shuffled_diag",
    "coevo",
    "coevo_warm",
    "coevo_frozen",
)


def command(out: Path, *, seed: int, python: str | None, mode: str = "no_llm") -> list[str]:
    """Argv of one old run. ``out / "results"`` is the results root.

    ``mode="no_llm"`` (the default) returns the same list this function returned
    before other modes existed. ``run`` calls it without ``mode`` in that case,
    so a stand-in written against the old signature still works.
    """
    if mode not in OLD_MODES:
        raise ValueError(f"mode: expected one of {', '.join(OLD_MODES)}, got {mode!r}")
    interpreter = sys.executable if python is None else python
    label = f"s08_old_s{seed}" if mode == "no_llm" else f"s11_old_{mode}_s{seed}"
    return [
        interpreter,
        str(FRAMEWORK / "main.py"),
        "--engine",
        "duckdb",
        "--mode",
        mode,
        "--iterations",
        "100000000",
        "--stagnation-limit",
        "100000000",
        "--seed",
        str(seed),
        "--results-root",
        str(out / "results"),
        "--label",
        label,
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


def _child_env(mode: str = "no_llm") -> dict[str, str]:
    env = os.environ.copy()
    if mode == "no_llm":
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


def run(
    out: str | Path,
    *,
    minutes: float,
    seed: int,
    python: str | None = None,
    mode: str = "no_llm",
) -> dict[str, Any]:
    """Run until the child exits or ``minutes`` have passed. Write ``old_run.json`` and return it."""
    if mode not in OLD_MODES:
        raise ValueError(f"mode: expected one of {', '.join(OLD_MODES)}, got {mode!r}")
    destination = Path(out)
    _prepare_out(destination)
    # ``no_llm`` keeps the call the S8 stand-ins replace: they take ``seed`` and ``python`` only.
    if mode == "no_llm":
        argv = command(destination, seed=seed, python=python)
    else:
        argv = command(destination, seed=seed, python=python, mode=mode)
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
            env=_child_env(mode),
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
        "mode": mode,
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
    parser.add_argument("--mode", default="no_llm")
    args = parser.parse_args(argv)
    if args.mode not in OLD_MODES:
        print(
            f"error: mode: expected one of {', '.join(OLD_MODES)}, got {args.mode!r}",
            file=sys.stderr,
        )
        return 2
    run(args.out, minutes=args.minutes, seed=args.seed, python=args.python, mode=args.mode)
    sys.stdout.write((Path(args.out) / "old_run.json").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
