"""Description length of a hypothesis and of a theory."""

from __future__ import annotations

from collections.abc import Iterable

from .constants import MDL_HYPOTHESIS_BITS, MDL_LITERAL_BITS
from .contracts import Hypothesis
from .theory import Theory


def hypothesis_length(hypothesis: Hypothesis) -> float:
    """Fixed cost of one hypothesis plus a cost for each literal of S.

    G, the evidence lists and the source are not counted.
    """
    return MDL_HYPOTHESIS_BITS + MDL_LITERAL_BITS * len(hypothesis.specific)


def theory_length(theory_or_hypotheses: Theory | Iterable[Hypothesis]) -> float:
    """Sum of :func:`hypothesis_length`. An empty theory is ``0.0``."""
    if isinstance(theory_or_hypotheses, Theory):
        hypotheses: Iterable[Hypothesis] = theory_or_hypotheses.hypotheses
    else:
        hypotheses = theory_or_hypotheses
    total = 0.0
    for hypothesis in hypotheses:
        total += hypothesis_length(hypothesis)
    return total
