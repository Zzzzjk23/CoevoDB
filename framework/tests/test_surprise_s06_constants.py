"""Theory constants, and the import order between features and theory."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from surprise.harness import constants as harness_constants
from surprise.theory import constants

FRAMEWORK = Path(__file__).resolve().parents[1]
THEORY = FRAMEWORK / "surprise" / "theory"

EXPECTED = {
    "P_CONFIRMED": 0.95,
    "P_PENDING": 0.5,
    "RESIDUAL_PRIOR_FAILS": 1.0,
    "RESIDUAL_PRIOR_TESTS": 100.0,
    "VALIDITY_PRIOR_INVALID": 1.0,
    "VALIDITY_PRIOR_TESTS": 10.0,
    "TRIAGE_LOW_BITS": 0.5,
    "TRIAGE_HIGH_BITS": 2.0,
    "VS_MAX_GENERAL": 64,
    "MDL_HYPOTHESIS_BITS": 8.0,
    "MDL_LITERAL_BITS": 7.4,
    "ACCEPT_HOLDOUT_MAX": 1000,
    "ACCEPT_TOLERANCE_BITS": 1e-9,
    "BETA": 1.0,
}


def test_constants_have_the_frozen_values_and_types() -> None:
    assert constants.as_dict() == EXPECTED
    for name, value in EXPECTED.items():
        assert getattr(constants, name) == value
        assert type(getattr(constants, name)) is type(value)
    detached = constants.as_dict()
    detached["P_CONFIRMED"] = 0.0
    assert constants.as_dict() == EXPECTED
    assert constants.P_CONFIRMED == 0.95
    assert set(EXPECTED).isdisjoint(harness_constants.as_dict())


def test_features_and_theory_import_in_either_order() -> None:
    orders = (
        "import surprise.features, surprise.theory",
        "import surprise.theory, surprise.features",
        "import surprise.theory.contracts, surprise.features.spec, surprise.theory",
    )
    for order in orders:
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                order + "; from surprise.theory import constants; print(sorted(constants.as_dict()))",
            ],
            cwd=FRAMEWORK,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert completed.returncode == 0, completed.stderr
        assert "P_CONFIRMED" in completed.stdout


def test_theory_imports_feature_submodules_rather_than_the_package() -> None:
    for path in THEORY.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "from surprise.features import" not in text, path.name
        assert "import surprise.features\n" not in text, path.name
        for banned in ("duckdb", "datafusion", "sqlglot", "surprise.gates", "llm", "coevo", "agents", "evolution"):
            assert banned not in text, f"{path.name} mentions {banned}"
