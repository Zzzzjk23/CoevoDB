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
from .edits import (
    BET_STATES,
    EDIT_KINDS,
    REJECT_REASONS,
    ROLLBACK_REASONS,
    Assessment,
    Proposal,
    Seen,
    bet_matches,
    claim,
    default_bets,
    fingerprint,
    holdout_sample,
)
from .workbench import Outcome, Workbench

__all__ = [
    "Assessment",
    "BET_STATES",
    "EDIT_DECISIONS",
    "EDIT_KINDS",
    "Hypothesis",
    "Observation",
    "Outcome",
    "Prediction",
    "Proposal",
    "REJECT_REASONS",
    "ROLLBACK_REASONS",
    "Residual",
    "Seen",
    "Spec",
    "StoreError",
    "TRIAGE_KINDS",
    "Theory",
    "TheoryEdit",
    "TheoryStore",
    "Workbench",
    "Update",
    "Validity",
    "ZONES",
    "apply_negative",
    "apply_positive",
    "attribution_request",
    "bet_matches",
    "claim",
    "common_conjunction",
    "default_bets",
    "constants",
    "converged",
    "covers",
    "experiment_class",
    "extend_manifest",
    "fingerprint",
    "generalize",
    "holdout_sample",
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
