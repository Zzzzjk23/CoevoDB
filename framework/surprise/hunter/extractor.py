"""Phi extraction in a resident child process, with a wall-clock budget per call."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

from surprise.features.ast import extract_ast
from surprise.features.phi import Phi, make_phi
from surprise.harness.contracts import SqlCase
from surprise.harness.oracles.forms import full_query
from .constants import PHI_TIMEOUT_S
from .operators import case_digest

_FRAMEWORK = Path(__file__).resolve().parents[2]


class PhiExtractor:
    """Cached phi extraction. The child starts on the first miss and dies on close."""

    def __init__(self, *, timeout_s: float = PHI_TIMEOUT_S) -> None:
        self.timeout_s = float(timeout_s)
        self._command = [sys.executable, "-m", "surprise.hunter.phi_worker"]
        self._proc: subprocess.Popen[str] | None = None
        self._cache: dict[str, Phi] = {}
        self._next_id = 1
        self._stats = {"calls": 0, "cache_hits": 0, "timeouts": 0, "restarts": 0, "errors": 0}

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)

    def extract(self, case: SqlCase) -> Phi:
        self._stats["calls"] += 1
        digest = case_digest(case)
        cached = self._cache.get(digest)
        if cached is not None:
            self._stats["cache_hits"] += 1
            return cached
        req_id = self._next_id
        self._next_id += 1
        try:
            phi = self._ask(req_id, case)
        except _Timeout:
            self._stats["timeouts"] += 1
            self._stop(kill=True)
            phi = _degrade(case)
        except _WorkerError:
            self._stats["errors"] += 1
            self._stop(kill=True)
            phi = _degrade(case)
        self._cache[digest] = phi
        return phi

    def close(self) -> None:
        self._stop(kill=False)

    def _ask(self, req_id: int, case: SqlCase) -> Phi:
        proc = self._ensure()
        payload = json.dumps({"id": req_id, "case": case.to_dict()}, ensure_ascii=False)
        try:
            assert proc.stdin is not None
            proc.stdin.write(payload + "\n")
            proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise _WorkerError("worker stdin closed") from exc
        if proc.poll() is not None:
            raise _WorkerError("worker exited")
        line = self._readline(proc, self.timeout_s)
        if line is None:
            raise _Timeout()
        if line == "":
            raise _WorkerError("worker exited")
        try:
            reply = json.loads(line)
        except json.JSONDecodeError as exc:
            raise _WorkerError("reply is not JSON") from exc
        if not isinstance(reply, dict):
            raise _WorkerError("reply is not an object")
        if reply.get("id") != req_id:
            raise _WorkerError("reply id does not match")
        if "error" in reply:
            raise _WorkerError(str(reply.get("error")))
        try:
            return Phi.from_dict(reply["phi"])
        except (KeyError, TypeError, ValueError) as exc:
            raise _WorkerError("reply phi is not valid") from exc

    def _ensure(self) -> subprocess.Popen[str]:
        proc = self._proc
        if proc is not None and proc.poll() is None:
            return proc
        if proc is not None:
            self._stats["restarts"] += 1
            self._proc = None
        env = os.environ.copy()
        env.pop("DEEPSEEK_API_KEY", None)
        started = subprocess.Popen(
            self._command,
            cwd=str(_FRAMEWORK),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self._proc = started
        return started

    def _readline(self, proc: subprocess.Popen[str], timeout_s: float) -> str | None:
        """Read one stdout line. Windows pipes have no timeout, so a thread waits."""
        if proc.stdout is None:
            return None
        box: queue.Queue[str | None] = queue.Queue(maxsize=1)

        def _read() -> None:
            try:
                line = proc.stdout.readline()
            except Exception:
                box.put(None)
                return
            box.put(line)

        thread = threading.Thread(target=_read, daemon=True)
        thread.start()
        try:
            line = box.get(timeout=timeout_s)
        except queue.Empty:
            return None
        if line is None:
            return None
        return line

    def _stop(self, *, kill: bool) -> None:
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        if kill:
            self._stats["restarts"] += 1
            _kill(proc)
            try:
                proc.wait(timeout=15)
            except (subprocess.TimeoutExpired, Exception):
                pass
            return
        if proc.stdin is not None:
            try:
                proc.stdin.close()
            except Exception:
                pass
        if proc.poll() is None:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _kill(proc)
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    pass
        else:
            try:
                proc.wait(timeout=1)
            except Exception:
                pass


class _Timeout(Exception):
    """The worker did not answer within the wall-clock budget."""


class _WorkerError(Exception):
    """The worker exited, returned junk, or reported an extraction error."""


def _degrade(case: SqlCase) -> Phi:
    query = full_query(case)
    ast_features, ast_status = extract_ast(query, case.engine)
    status = {"ast": ast_status, "plan": "unavailable", "data": "unavailable"}
    return make_phi(case.engine, ast_features, status)


def _kill(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
    else:
        proc.kill()
