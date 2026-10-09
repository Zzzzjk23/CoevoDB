"""The theory section of a run manifest, and the constants command."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from surprise.features.limits import ISOLATION_TIMEOUT_S, MAX_TABLE_ROWS, PROBE_TIMEOUT_S
from surprise.features.registry import default_registry
from surprise.theory import extend_manifest, theory_manifest, verify_theory_manifest
from surprise.theory import constants

FRAMEWORK = Path(__file__).resolve().parents[1]


def _base() -> dict:
    return {"harness": {"hash": "abc"}, "constants": {"A": 1}, "run_id": "s06"}


def test_theory_manifest_carries_constants_code_vocab_and_limits() -> None:
    section = theory_manifest()
    assert json.loads(json.dumps(section)) == section
    assert section["schema"] == 1
    assert section["constants"] == constants.as_dict()
    assert section["code"]["algorithm"] == "sha256"
    assert len(section["code"]["hash"]) == 64
    on_disk = sorted(path.relative_to(FRAMEWORK).as_posix() for path in (FRAMEWORK / "surprise" / "theory").rglob("*.py"))
    assert sorted(section["code"]["files"]) == on_disk
    features = section["features"]
    assert features["vocab"] == default_registry().digest()
    assert features["limits"] == {
        "MAX_TABLE_ROWS": MAX_TABLE_ROWS,
        "PROBE_TIMEOUT_S": PROBE_TIMEOUT_S,
        "ISOLATION_TIMEOUT_S": ISOLATION_TIMEOUT_S,
    }
    feature_files = sorted(
        path.relative_to(FRAMEWORK).as_posix() for path in (FRAMEWORK / "surprise" / "features").rglob("*.py")
    )
    assert sorted(features["code"]["files"]) == feature_files
    assert theory_manifest() == section


def test_extend_manifest_adds_one_key_and_copies() -> None:
    base = _base()
    extended = extend_manifest(base)
    assert "theory" not in base
    assert base["harness"]["hash"] == "abc"
    extended["harness"]["hash"] = "changed"
    extended["theory"]["constants"]["P_PENDING"] = 0.0
    base["constants"]["A"] = 2
    assert extended["harness"]["hash"] == "changed"
    assert base["harness"]["hash"] == "abc"
    assert base["constants"]["A"] == 2
    again = extend_manifest(_base())
    assert again["constants"]["A"] == 1
    assert again["theory"] == theory_manifest()
    assert {key: value for key, value in again.items() if key != "theory"} == _base()
    with pytest.raises(ValueError):
        extend_manifest(again)
    with pytest.raises(ValueError):
        extend_manifest({"run_id": "x"})
    with pytest.raises(ValueError):
        extend_manifest({"harness": {}, "run_id": "x"})


def test_verify_reports_constants_files_vocab_and_limits() -> None:
    manifest = extend_manifest(_base())
    assert verify_theory_manifest(manifest) == []
    tampered = json.loads(json.dumps(manifest))
    tampered["theory"]["constants"]["P_PENDING"] = 0.6
    path = sorted(tampered["theory"]["code"]["files"])[0]
    tampered["theory"]["code"]["files"][path] = "0" * 64
    missing = sorted(tampered["theory"]["code"]["files"])[-1]
    del tampered["theory"]["code"]["files"][missing]
    tampered["theory"]["features"]["code"]["files"]["surprise/features/extra.py"] = "ab" * 32
    tampered["theory"]["features"]["vocab"] = "0" * 64
    tampered["theory"]["features"]["limits"]["MAX_TABLE_ROWS"] = 1
    problems = verify_theory_manifest(tampered)
    assert any("P_PENDING" in line for line in problems)
    assert any(path in line for line in problems)
    assert any(missing in line for line in problems)
    assert any("surprise/features/extra.py" in line for line in problems)
    assert any("vocab" in line for line in problems)
    assert any("MAX_TABLE_ROWS" in line for line in problems)
    assert all(line.isascii() and "\n" not in line for line in problems)
    with pytest.raises(ValueError):
        verify_theory_manifest(_base())
    with pytest.raises(ValueError):
        verify_theory_manifest({"theory": []})


def test_theory_command_prints_the_same_json() -> None:
    for command, expected in (("constants", constants.as_dict()), ("manifest", theory_manifest())):
        run = subprocess.run(
            [sys.executable, "-m", "surprise.theory", command],
            cwd=FRAMEWORK,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        assert run.returncode == 0, run.stderr
        assert json.loads(run.stdout) == expected
        assert run.stdout.isascii()
