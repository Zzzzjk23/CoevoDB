"""Theory layer: hypotheses and the version space over conjunctions of phi literals."""

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
from .vspace import covers, generalize, reduce_conjunction, specialize

__all__ = [
    "EDIT_DECISIONS",
    "Hypothesis",
    "Spec",
    "TheoryEdit",
    "Update",
    "apply_negative",
    "apply_positive",
    "attribution_request",
    "constants",
    "converged",
    "covers",
    "generalize",
    "identity_match",
    "new_family",
    "position",
    "reduce_conjunction",
    "specialize",
]
