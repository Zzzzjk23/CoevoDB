"""Theory layer: hypotheses, residual and validity models, predictions, triage, and storage."""

from . import constants
from .contracts import EDIT_DECISIONS, Hypothesis, Spec, TheoryEdit
from .hypothesis import (
    Update,
    apply_negative,
    apply_positive,
    attribution_request,
    converged,
    new_family,
    position,
)
from .identity import identity_match
from .manifest import extend_manifest, theory_manifest, verify_theory_manifest
from .predict import TRIAGE_KINDS, ZONES, Prediction, surprise_bits, triage
from .residual import Residual
from .theory import Observation, Theory
from .validity import Validity, experiment_class
from .vspace import common_conjunction, covers, generalize, reduce_conjunction, specialize
from .length import hypothesis_length, theory_length
from .store import StoreError, TheoryStore

__all__ = [
    "EDIT_DECISIONS",
    "Hypothesis",
    "Observation",
    "Prediction",
    "Residual",
    "Spec",
    "StoreError",
    "TRIAGE_KINDS",
    "Theory",
    "TheoryEdit",
    "TheoryStore",
    "Update",
    "Validity",
    "ZONES",
    "apply_negative",
    "apply_positive",
    "attribution_request",
    "common_conjunction",
    "constants",
    "converged",
    "covers",
    "experiment_class",
    "extend_manifest",
    "generalize",
    "hypothesis_length",
    "identity_match",
    "new_family",
    "position",
    "reduce_conjunction",
    "specialize",
    "surprise_bits",
    "theory_length",
    "theory_manifest",
    "triage",
    "verify_theory_manifest",
]
