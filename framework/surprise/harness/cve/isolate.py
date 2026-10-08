"""Fresh-process executor.

The child is ``python -m surprise.harness.cve.worker``. It speaks one JSON
object on stdin and one JSON object on stdout. The parent's environment is
inherited except ``DEEPSEEK_API_KEY``, and the child is given the parent's
``sys.path``. A child that exits without a result is a crash. A child that
outlives the wall clock is killed and reported as a timeout.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from surprise.harness.constants import CVE_WALL_TIMEOUT_S, QUERY_TIMEOUT_S
from surprise.harness.contracts import SqlCase
from surprise.harness.oracles.forms import full_query

from .session import json_rows

_FRAMEWORK = Path(__file__).resolve().parents[3]
_STATUSES = ("ok", "error", "timeout", "crash")


@dataclass(frozen=True)
class IsolatedResult:
    """What one fresh process returned. ``to_dict`` is JSON-safe."""

    status: str
    rows: list[Any]
    error: str | None
    exit_code: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "rows": json_rows(self.rows),
            "error": self.error,
            "exit_code": self.exit_code,
        }


def execute_isolated(
    case: SqlCase,
    *,
    prelude: tuple[str, ...] | list[str] = (),
    timeout_s: float = QUERY_TIMEOUT_S,
    wall_timeout_s: float | None = None,
    runner_factory: Any = None,
) -> IsolatedResult:
    """Run setup, ``prelude``, and the full query in a new process.

    Engine failures become a result. They do not propagate.
    """
    factory_ref = None
    if runner_factory is not None:
        factory_ref = ensure_importable(runner_factory, "runner_factory")
    payload = {
        "op": "execute",
        "sys_path": list(sys.path),
        "engine": case.engine,
        "setup": list(case.setup),
        "prelude": list(prelude),
        "query": full_query(case),
        "timeout_s": timeout_s,
        "factory": factory_ref,
    }
    wall = CVE_WALL_TIMEOUT_S if wall_timeout_s is None else wall_timeout_s
    outcome = call_worker(payload, wall)
    if outcome["kind"] == "timeout":
        return IsolatedResult("timeout", [], "wall timeout", None)
    if outcome["kind"] == "crash":
        code = outcome["exit_code"]
        return IsolatedResult("crash", [], f"process exited with code {code}", code)
    data = outcome["data"]
    if data.get("op") == "raise":
        message = _redact(str(data.get("message") or "worker failed"))
        return IsolatedResult("error", [], message, None)
    status = data.get("status")
    if status not in _STATUSES:
        return IsolatedResult("error", [], "worker returned an unknown status", None)
    rows = data.get("rows") if status == "ok" else []
    if not isinstance(rows, list):
        rows = []
    error = data.get("error")
    if error is not None and not isinstance(error, str):
        error = str(error)
    exit_code = data.get("exit_code")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        exit_code = None
    return IsolatedResult(status, rows, error, exit_code)


def call_worker(payload: dict[str, Any], wall_timeout_s: float) -> dict[str, Any]:
    """Run one worker payload. The result is ``timeout``, ``crash``, or ``ok``."""
    env = {key: value for key, value in os.environ.items() if key.upper() != "DEEPSEEK_API_KEY"}
    kwargs: dict[str, Any] = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(
        [sys.executable, "-m", "surprise.harness.cve.worker"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(_FRAMEWORK),
        env=env,
        **kwargs,
    )
    blob = json.dumps(payload).encode("utf-8")
    try:
        try:
            stdout, _stderr = proc.communicate(input=blob, timeout=wall_timeout_s)
        except subprocess.TimeoutExpired:
            _kill(proc)
            try:
                proc.communicate(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                pass
            return {"kind": "timeout"}
        data = _parse_json(stdout)
        if data is not None:
            return {"kind": "ok", "data": data}
        # No parseable result, including a clean exit 0, is a crash. The
        # caller must get a result rather than an exception.
        code = proc.returncode
        if isinstance(code, bool) or not isinstance(code, int):
            code = 0
        return {"kind": "crash", "exit_code": int(code)}
    finally:
        if proc.poll() is None:
            _kill(proc)


def ensure_importable(fn: Any, what: str) -> str:
    """Return ``module:qualname`` or raise ``ValueError`` before ``fn`` is called.

    Lambdas, closures, and local classes cannot be imported by a child.
    """
    module = getattr(fn, "__module__", None)
    qualname = getattr(fn, "__qualname__", None)
    if not isinstance(module, str) or not module or not isinstance(qualname, str) or not qualname:
        raise ValueError(f"{what}: must be an importable module-level callable")
    if "<" in module or "<" in qualname:
        raise ValueError(f"{what}: must be an importable module-level callable, got {qualname!r}")
    try:
        loaded = load_callable(f"{module}:{qualname}")
    except Exception as exc:
        raise ValueError(f"{what}: cannot be imported by a child process") from exc
    if loaded is not fn:
        raise ValueError(f"{what}: import did not resolve to the same object")
    if not callable(loaded):
        raise ValueError(f"{what}: must be callable")
    return f"{module}:{qualname}"


def load_callable(ref: str) -> Any:
    module_name, qualname = ref.split(":", 1)
    module = importlib.import_module(module_name)
    obj: Any = module
    for part in qualname.split("."):
        obj = getattr(obj, part)
    return obj


def _parse_json(blob: bytes) -> dict[str, Any] | None:
    text = blob.decode("utf-8", "replace").strip()
    if not text:
        return None
    data: Any = None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        for line in reversed(text.splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                data = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
    if not isinstance(data, dict):
        return None
    return data


def _kill(proc: subprocess.Popen[bytes]) -> None:
    """Stop ``proc`` and wait until it is gone. On Windows, kill the tree."""
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
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            return


def _redact(text: str) -> str:
    secret = os.environ.get("DEEPSEEK_API_KEY")
    if secret:
        return text.replace(secret, "<hidden>")
    return text
