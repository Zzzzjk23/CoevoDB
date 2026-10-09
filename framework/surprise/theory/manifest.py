"""Theory section of a run manifest. The frozen harness manifest is not modified."""

from __future__ import annotations

import copy
from typing import Any

from surprise.features.limits import ISOLATION_TIMEOUT_S, MAX_TABLE_ROWS, PROBE_TIMEOUT_S
from surprise.features.registry import default_registry
from surprise.harness.manifest import harness_hash

from . import constants

_THEORY_CODE = ("surprise/theory/**/*.py",)
_FEATURE_CODE = ("surprise/features/**/*.py",)
_LIMITS = {
    "MAX_TABLE_ROWS": MAX_TABLE_ROWS,
    "PROBE_TIMEOUT_S": PROBE_TIMEOUT_S,
    "ISOLATION_TIMEOUT_S": ISOLATION_TIMEOUT_S,
}


def theory_manifest() -> dict[str, Any]:
    """Constants, vocabulary, limits, and a hash of the theory and feature code."""
    return {
        "schema": 1,
        "constants": constants.as_dict(),
        "code": harness_hash(patterns=_THEORY_CODE),
        "features": {
            "vocab": default_registry().digest(),
            "limits": dict(_LIMITS),
            "code": harness_hash(patterns=_FEATURE_CODE),
        },
    }


def extend_manifest(manifest: dict) -> dict:
    """Deep copy of ``manifest`` with a ``theory`` section added."""
    if not isinstance(manifest, dict) or "harness" not in manifest or "constants" not in manifest:
        raise ValueError("manifest must be an object with harness and constants")
    if "theory" in manifest:
        raise ValueError("manifest already has a theory section")
    extended = copy.deepcopy(manifest)
    extended["theory"] = theory_manifest()
    return extended


def verify_theory_manifest(manifest: dict) -> list[str]:
    """Compare the stored theory section with the code and constants on disk.

    An empty list means nothing changed. Each finding is one ASCII line. A
    changed constant names that constant; a changed, added, or missing file
    names that file.
    """
    if not isinstance(manifest, dict) or "theory" not in manifest:
        raise ValueError("manifest has no theory section")
    section = manifest["theory"]
    if not isinstance(section, dict):
        raise ValueError("manifest theory section is not an object")
    current = theory_manifest()
    problems: list[str] = []
    if section.get("schema") != 1:
        problems.append(_finding(f"schema changed: {section.get('schema')!r}"))
    problems.extend(_constant_problems(section.get("constants"), current["constants"]))
    problems.extend(_file_problems(section.get("code"), current["code"]))
    problems.extend(_feature_problems(section.get("features"), current["features"]))
    return problems


def _constant_problems(recorded: object, current: dict[str, Any]) -> list[str]:
    if not isinstance(recorded, dict):
        return [_finding(f"constant missing: {name}") for name in sorted(current)]
    problems: list[str] = []
    for name in sorted(set(recorded) | set(current)):
        if name not in recorded:
            problems.append(_finding(f"constant missing: {name}"))
        elif name not in current:
            problems.append(_finding(f"constant added: {name}"))
        elif recorded[name] != current[name]:
            problems.append(_finding(f"constant changed: {name}"))
    return problems


def _feature_problems(recorded: object, current: dict[str, Any]) -> list[str]:
    if not isinstance(recorded, dict):
        problems = [_finding("vocab changed")]
        problems.extend(_finding(f"limit changed: {name}") for name in sorted(current["limits"]))
        problems.extend(_file_problems(None, current["code"]))
        return problems
    problems = []
    if recorded.get("vocab") != current["vocab"]:
        problems.append(_finding("vocab changed"))
    recorded_limits = recorded.get("limits")
    if not isinstance(recorded_limits, dict):
        recorded_limits = {}
    for name in sorted(set(recorded_limits) | set(current["limits"])):
        if recorded_limits.get(name) != current["limits"].get(name):
            problems.append(_finding(f"limit changed: {name}"))
    problems.extend(_file_problems(recorded.get("code"), current["code"]))
    return problems


def _file_problems(recorded: object, current: dict[str, Any]) -> list[str]:
    recorded_files: dict[object, object] = {}
    recorded_hash: object = None
    if isinstance(recorded, dict):
        files = recorded.get("files")
        if isinstance(files, dict):
            recorded_files = files
        recorded_hash = recorded.get("hash")
    current_files = current["files"]
    problems: list[str] = []
    for path in sorted(set(recorded_files) | set(current_files), key=str):
        safe = _finding(path)
        if path in recorded_files and path in current_files:
            if recorded_files[path] != current_files[path]:
                problems.append(_finding(f"changed: {safe}"))
        elif path in recorded_files:
            problems.append(_finding(f"missing: {safe}"))
        else:
            problems.append(_finding(f"added: {safe}"))
    if recorded_hash != current["hash"]:
        shown = recorded_hash[:12] if isinstance(recorded_hash, str) else "?"
        problems.append(_finding(f"hash mismatch: manifest {shown} current {current['hash'][:12]}"))
    return problems


def _finding(text: object) -> str:
    flat = " ".join(str(text).split())
    return flat.encode("ascii", "backslashreplace").decode("ascii")
