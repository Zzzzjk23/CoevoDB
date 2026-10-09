"""Compose a phi from the statement, its plan, and the data it reads.

``extract`` runs in this process. ``extract_isolated`` runs the ``phi`` command
in a child process whose environment has no ``DEEPSEEK_API_KEY``. A child that
crashes, times out, or prints nothing usable still yields a phi: the statement
layer is computed here, and plan and data are unavailable.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from surprise.harness.contracts import SqlCase
from surprise.harness.oracles.forms import full_query
from surprise.harness.oracles.registry import runner_factory_for

from .ast import extract_ast
from .data import extract_data
from .limits import ISOLATION_TIMEOUT_S
from .plan import extract_plan
from .phi import Phi, make_phi
from .registry import Registry, default_registry

_LAYER_NAMES = ("ast", "plan", "data")
_FRAMEWORK = Path(__file__).resolve().parents[2]


def extract(
    case: SqlCase,
    *,
    layers: Iterable[str] = _LAYER_NAMES,
    runner_factory=None,
    registry: Registry | None = None,
) -> Phi:
    """Build a phi for ``case``. ``layers`` must include ``ast``."""
    selected = _selected_layers(layers)
    query = full_query(case)
    ast_features, ast_status = extract_ast(query, case.engine, registry)
    status = {
        "ast": ast_status,
        "plan": "ok" if "plan" in selected else "skipped",
        "data": "ok" if "data" in selected else "skipped",
    }
    features: set[str] = set(ast_features)
    if "plan" not in selected and "data" not in selected:
        return make_phi(case.engine, features, status, registry)

    factory = runner_factory if runner_factory is not None else runner_factory_for(case.engine)
    runner = factory()
    try:
        if _setup_failed(runner, case):
            _mark_unavailable(status, selected)
            return make_phi(case.engine, features, status, registry)
        if "plan" in selected:
            plan_features, plan_status = extract_plan(runner, query, case.engine)
            status["plan"] = plan_status
            if plan_status == "ok":
                features.update(_known_leaves(plan_features, registry))
        if "data" in selected:
            data_features, data_status = extract_data(runner, query, case.engine)
            status["data"] = data_status
            if data_status == "ok":
                features.update(_known_leaves(data_features, registry))
        return make_phi(case.engine, features, status, registry)
    finally:
        _close(runner)


def extract_isolated(
    case: SqlCase,
    *,
    layers: Iterable[str] = _LAYER_NAMES,
    timeout_s: float | None = None,
    registry_path: str | None = None,
) -> Phi:
    """``extract`` in a child process. On failure, keep only the statement layer."""
    selected = _selected_layers(layers)
    timeout = ISOLATION_TIMEOUT_S if timeout_s is None else timeout_s
    registry = _load_registry(registry_path)
    payload: dict = {"case": case.to_dict(), "layers": [name for name in _LAYER_NAMES if name in selected]}
    if registry_path is not None:
        payload["registry"] = registry_path
    env = os.environ.copy()
    env.pop("DEEPSEEK_API_KEY", None)
    proc = subprocess.Popen(
        [sys.executable, "-m", "surprise.features", "phi"],
        cwd=_FRAMEWORK,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        stdout, _stderr = proc.communicate(json.dumps(payload).encode("utf-8"), timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill(proc)
        try:
            proc.communicate(timeout=15)
        except Exception:
            pass
        return _degrade(case, selected, registry)
    if proc.returncode != 0:
        return _degrade(case, selected, registry)
    phi = _parse_phi(stdout)
    if phi is None:
        return _degrade(case, selected, registry)
    return phi


def _selected_layers(layers: Iterable[str]) -> frozenset[str]:
    if isinstance(layers, (str, bytes)) or not isinstance(layers, Iterable):
        raise ValueError("layers must contain ast and only the names ast, plan, data")
    names = tuple(layers)
    if any(not isinstance(name, str) for name in names):
        raise ValueError("layers must contain ast and only the names ast, plan, data")
    allowed = set(_LAYER_NAMES)
    if "ast" not in names or any(name not in allowed for name in names):
        raise ValueError("layers must contain ast and only the names ast, plan, data")
    return frozenset(names)


def _setup_failed(runner, case: SqlCase) -> bool:
    try:
        outcomes = runner.setup(list(case.setup))
    except Exception:
        return True
    if outcomes is None:
        return False
    try:
        pairs = list(outcomes)
    except TypeError:
        return True
    for item in pairs:
        if not isinstance(item, tuple) or len(item) < 2 or item[1] is not None:
            return True
    return False


def _mark_unavailable(status: dict[str, str], selected: frozenset[str]) -> None:
    for name in ("plan", "data"):
        if name in selected:
            status[name] = "unavailable"


def _known_leaves(features: set[str], registry: Registry | None) -> set[str]:
    active = default_registry() if registry is None else registry
    kept: set[str] = set()
    for feature_id in features:
        if not active.known(feature_id):
            continue
        definition = active.get(feature_id)
        if definition.kind == "leaf" and definition.accepted and definition.layer == feature_id.split(":", 1)[0]:
            kept.add(feature_id)
    return kept


def _degrade(case: SqlCase, selected: frozenset[str], registry: Registry | None) -> Phi:
    query = full_query(case)
    ast_features, ast_status = extract_ast(query, case.engine, registry)
    status = {
        "ast": ast_status,
        "plan": "unavailable" if "plan" in selected else "skipped",
        "data": "unavailable" if "data" in selected else "skipped",
    }
    return make_phi(case.engine, ast_features, status, registry)


def _load_registry(path: str | None) -> Registry | None:
    if path is None:
        return None
    try:
        return Registry.load(path)
    except (OSError, ValueError, json.JSONDecodeError, TypeError):
        return None


def _parse_phi(blob: bytes | None) -> Phi | None:
    if not blob:
        return None
    text = blob.decode("utf-8", "replace").strip()
    if not text:
        return None
    data = None
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
    try:
        return Phi.from_dict(data)
    except (ValueError, TypeError, KeyError):
        return None


def _close(runner) -> None:
    close = getattr(runner, "close", None)
    if not callable(close):
        return
    try:
        close()
    except Exception:
        return


def _kill(proc: subprocess.Popen) -> None:
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
