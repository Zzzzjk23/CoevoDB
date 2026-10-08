"""Contracts the theory layer owns: specs, hypotheses, and theory edits.

These types are still only shape and serialisation. Later sessions fill in the
version-space rules. Importing the harness contracts is allowed; the harness
does not import this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..harness.contracts import (
    ORACLE_IDS,
    _Serializable,
    _freeze_objects,
    _freeze_string_groups,
    _freeze_strings,
    _optional_number,
    _optional_str,
    _require_choice,
    _require_object,
    _require_str,
)

# pending: not yet decided; accepted: written into the theory; rolled_back: rejected and kept as negative memory.
EDIT_DECISIONS = ("pending", "accepted", "rolled_back")


@dataclass(frozen=True)
class Spec(_Serializable):
    """Constraints on phi: required and forbidden features, data properties, target."""

    engine: str
    oracle: str
    required: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()
    data_properties: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "engine", _require_str(self.engine, "engine"))
        _require_choice(self.oracle, ORACLE_IDS, "oracle")
        object.__setattr__(self, "required", _freeze_strings(self.required, "required"))
        object.__setattr__(self, "forbidden", _freeze_strings(self.forbidden, "forbidden"))
        object.__setattr__(
            self, "data_properties", _freeze_strings(self.data_properties, "data_properties")
        )


@dataclass(frozen=True)
class Hypothesis(_Serializable):
    """h = (I, delta-P, V, S, G, E+, E-) plus where it came from and its status.

    ``general`` is a tuple of conjunctions. ``positives`` and ``negatives`` are
    experiment-record ids.
    """

    hypothesis_id: str
    engine: str
    interventions: tuple[str, ...]
    plan_delta: tuple[str, ...]
    versions: dict[str, Any]
    specific: tuple[str, ...]
    general: tuple[tuple[str, ...], ...]
    positives: tuple[str, ...]
    negatives: tuple[str, ...]
    source: str
    status: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "hypothesis_id", _require_str(self.hypothesis_id, "hypothesis_id")
        )
        object.__setattr__(self, "engine", _require_str(self.engine, "engine"))
        object.__setattr__(
            self, "interventions", _freeze_strings(self.interventions, "interventions")
        )
        object.__setattr__(self, "plan_delta", _freeze_strings(self.plan_delta, "plan_delta"))
        object.__setattr__(self, "versions", _require_object(self.versions, "versions"))
        object.__setattr__(self, "specific", _freeze_strings(self.specific, "specific"))
        object.__setattr__(self, "general", _freeze_string_groups(self.general, "general"))
        object.__setattr__(self, "positives", _freeze_strings(self.positives, "positives"))
        object.__setattr__(self, "negatives", _freeze_strings(self.negatives, "negatives"))
        object.__setattr__(self, "source", _require_str(self.source, "source"))
        object.__setattr__(self, "status", _require_str(self.status, "status"))


@dataclass(frozen=True)
class TheoryEdit(_Serializable):
    """One proposed edit of the theory, with the bets that justify it."""

    edit_id: str
    kind: str
    rationale: str
    bets: tuple[dict[str, Any], ...]
    surprise_delta_in: float | None
    surprise_delta_out: float | None
    decision: str
    proposer: str
    theory_version: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "edit_id", _require_str(self.edit_id, "edit_id"))
        object.__setattr__(self, "kind", _require_str(self.kind, "kind"))
        object.__setattr__(self, "rationale", _require_str(self.rationale, "rationale"))
        object.__setattr__(self, "bets", _freeze_objects(self.bets, "bets"))
        object.__setattr__(
            self, "surprise_delta_in", _optional_number(self.surprise_delta_in, "surprise_delta_in")
        )
        object.__setattr__(
            self,
            "surprise_delta_out",
            _optional_number(self.surprise_delta_out, "surprise_delta_out"),
        )
        _require_choice(self.decision, EDIT_DECISIONS, "decision")
        object.__setattr__(self, "proposer", _require_str(self.proposer, "proposer"))
        object.__setattr__(
            self, "theory_version", _optional_str(self.theory_version, "theory_version")
        )
        object.__setattr__(self, "payload", _require_object(self.payload, "payload"))
