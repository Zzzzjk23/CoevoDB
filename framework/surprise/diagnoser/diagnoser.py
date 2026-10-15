"""Diagnoser without an LLM: tighten S from a minimised reproduction, and keep the theory's beats.

Minimisation and the fix set already happened in the frozen harness. Version-space
updates happen in ``Theory.observe``. Accepting or rolling back an edit is the
workbench's decision. This agent only proposes the tighter conjunction and fires
the two periodic beats.
"""

from __future__ import annotations

import dataclasses

from surprise.harness.contracts import SqlCase
from surprise.theory import (
    Proposal,
    TheoryEdit,
    common_conjunction,
    default_bets,
    reduce_conjunction,
)

from .constants import CHECKPOINT_EVERY, COMPRESS_EVERY


class Diagnoser:
    """Proposes revisions from minimised failures and runs compress plus checkpoint."""

    def __init__(self, *, phi, registry) -> None:
        self.phi = phi
        self.registry = registry

    def after(self, wb, record, outcome) -> tuple[TheoryEdit, ...]:
        """Propose one revision when the minimised case keeps a strictly smaller S.

        Returns the edit the workbench logged, including one the acceptance test
        refused. Returns an empty tuple when there is nothing to propose.
        """
        opened = outcome.observation.opened
        if opened is None:
            return ()
        cve = record.label.cve
        minimize = cve.get("minimize") if isinstance(cve, dict) else None
        if (
            not isinstance(minimize, dict)
            or minimize.get("status") != "ran"
            or minimize.get("reproduced") is not True
            or not minimize.get("case")
        ):
            return ()
        try:
            hypothesis = wb.theory.get(opened)
        except KeyError:
            return ()
        phi_min = self.phi(SqlCase.from_dict(minimize["case"]))
        reduced_min = reduce_conjunction(phi_min.features, self.registry)
        new_s = common_conjunction(hypothesis.specific, reduced_min, self.registry)
        if not new_s or new_s == reduce_conjunction(hypothesis.specific, self.registry):
            return ()
        template = dataclasses.replace(hypothesis, specific=new_s, source="diagnoser")
        proposal = Proposal(
            kind="revise",
            proposer="diagnoser",
            removes=(hypothesis.hypothesis_id,),
            adds=(template,),
            bets=default_bets((hypothesis,), (template,), self.registry),
            trigger=(record.record_id,),
            rationale=(
                f"the minimised reproduction of {record.record_id} keeps "
                f"{len(new_s)} of the {len(hypothesis.specific)} literals of S"
            ),
        )
        return (wb.propose(proposal),)

    def periodic(self, wb, done) -> tuple[TheoryEdit, ...]:
        """Compress and checkpoint when ``done`` lands on those beats. ``done`` includes this experiment."""
        if done % COMPRESS_EVERY == 0:
            edits = wb.compress()
        else:
            edits = ()
        if done % CHECKPOINT_EVERY == 0:
            wb.checkpoint(f"after {done} experiments")
        return edits

    def checkpoint_only(self, wb, done) -> tuple[TheoryEdit, ...]:
        """Close a generation on the checkpoint beat. Does not compress.

        The note and the beat match :meth:`periodic`. Nothing is proposed.
        """
        if done % CHECKPOINT_EVERY == 0:
            wb.checkpoint(f"after {done} experiments")
        return ()
