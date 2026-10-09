"""The theory in use: a store, a journal, bets, rollback, and MDL edits.

One workbench writes one store. Reopening it rebuilds the same records, edits
and bets, and the next observation does the same thing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from surprise.features.phi import Phi
from surprise.features.registry import Registry, default_registry
from surprise.harness.contracts import Label

from .contracts import Hypothesis, TheoryEdit
from .edits import (
    Assessment,
    Proposal,
    Seen,
    assess_edit,
    bet_matches,
    build_added,
    claim,
    default_bets,
)
from .predict import Prediction, surprise_bits
from .store import TheoryStore
from .theory import Observation, Theory
from .vspace import common_conjunction, covers, generalize, reduce_conjunction

_COMPRESS_LIMIT = 100
_CALLER_REASONS = ("bet_broken", "manual")


def _public_label(label: Label) -> Label:
    """The label the journal keeps. ``detail`` is dropped; ``cve`` stays."""
    data = label.to_dict()
    data["detail"] = {}
    return Label.from_dict(data)


def _edit_order(edit_id: str) -> tuple[int, int | str]:
    if edit_id.startswith("e") and edit_id[1:].isdigit():
        return (0, int(edit_id[1:]))
    return (1, edit_id)


def _same_identity(first: Hypothesis, second: Hypothesis) -> bool:
    """Fix sets when both name one; otherwise the three identity fields. Mixed pairs differ."""
    if bool(first.interventions) != bool(second.interventions):
        return False
    if first.interventions:
        return set(first.interventions) == set(second.interventions)
    return (
        first.fail_kind == second.fail_kind
        and first.error_class == second.error_class
        and first.behavior_shape == second.behavior_shape
    )


def _cluster(
    positives: Sequence[Seen],
    contradictions: Sequence[Seen],
    registry: Registry,
) -> list[tuple[str, ...]]:
    """Greedy clusters of positives. A cluster may not grow to cover a new contradicting pass."""
    clusters: list[tuple[str, ...]] = []
    for record in positives:
        own = reduce_conjunction(record.phi.features, registry)
        if not own:
            continue
        placed = False
        for index, cluster in enumerate(clusters):
            widened = generalize(cluster, record.phi, registry)
            if not widened:
                continue
            blocked = any(
                covers(widened, contra.phi, registry) and not covers(cluster, contra.phi, registry)
                for contra in contradictions
            )
            if blocked:
                continue
            clusters[index] = widened
            placed = True
            break
        if not placed:
            clusters.append(own)
    return clusters


def _memory_claims(payload: dict[str, Any], registry: Registry) -> list[Any]:
    raw = payload["added"] if payload["added"] else payload["removed"]
    return [claim(Hypothesis.from_dict(row), registry) for row in raw]


@dataclass(frozen=True)
class Outcome:
    """What one observation did: the theory's own report, then the bets it settled."""

    observation: Observation
    seq: int
    owner: str | None
    bets: tuple[tuple[str, int, str], ...]
    rolled_back: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "bets", tuple(tuple(item) for item in self.bets))
        object.__setattr__(self, "rolled_back", tuple(self.rolled_back))


class Workbench:
    """The live theory, its store, and the edits that have been proposed to it."""

    def __init__(self, store: TheoryStore, theory: Theory, registry: Registry) -> None:
        self.store = store
        self.theory = theory
        self._registry = registry
        self._records: list[Seen] = []
        self._by_id: dict[str, Seen] = {}
        self._edits: dict[str, TheoryEdit] = {}
        self._edit_ids: list[str] = []

    @classmethod
    def create(cls, root: str | Path, registry: Registry | None = None) -> Workbench:
        """A new store and an empty theory."""
        active = default_registry() if registry is None else registry
        store = TheoryStore.create(root, active)
        return cls(store, store.load(), active)

    @classmethod
    def open(cls, root: str | Path, registry: Registry | None = None) -> Workbench:
        """Open a store and rebuild records and edits from its logs."""
        active = default_registry() if registry is None else registry
        store = TheoryStore.open(root, active)
        bench = cls(store, store.load(), active)
        for entry in store.journal():
            if entry.get("kind") != "observe":
                continue
            seen = Seen(
                entry["record_id"],
                Phi.from_dict(entry["phi"]),
                Label.from_dict(entry["label"]),
            )
            bench._records.append(seen)
            bench._by_id[seen.record_id] = seen
        for edit in store.edits():
            bench._edit_ids.append(edit.edit_id)
            bench._edits[edit.edit_id] = edit
        return bench

    @property
    def generation(self) -> int:
        """The open generation. Closed ones are ``0 .. generation - 1``."""
        return self.store.head()["generation"]

    def predict(self, phi: Phi, oracle: str) -> Prediction:
        """Same prediction the live theory would give."""
        return self.theory.predict(phi, oracle)

    def records(self) -> tuple[Seen, ...]:
        """Observations in the order they were made."""
        return tuple(self._records)

    def seen(self, record_id: str) -> Seen:
        """The observation of ``record_id``. Unknown ids raise ``KeyError``."""
        try:
            return self._by_id[record_id]
        except KeyError:
            raise KeyError(record_id) from None

    def edits(self) -> tuple[TheoryEdit, ...]:
        """Latest state of each edit, in order of first appearance."""
        return tuple(self._edits[edit_id] for edit_id in self._edit_ids)

    def edit(self, edit_id: str) -> TheoryEdit:
        """Latest state of one edit. Unknown ids raise ``KeyError``."""
        try:
            return self._edits[edit_id]
        except KeyError:
            raise KeyError(edit_id) from None

    def negatives(self) -> tuple[dict[str, Any], ...]:
        """Negative memory, oldest first."""
        return tuple(self.store.negatives())

    def open_bets(self) -> tuple[tuple[str, int, dict[str, Any]], ...]:
        """Open bets of accepted edits, in edit order then bet order."""
        found: list[tuple[str, int, dict[str, Any]]] = []
        for edit in self.edits():
            if edit.decision != "accepted":
                continue
            for index, (bet, state) in enumerate(zip(edit.bets, edit.payload["bets_state"])):
                if state["status"] == "open":
                    found.append((edit.edit_id, index, bet))
        return tuple(found)

    def surprise_under(self, generation: int, record_ids: Sequence[str]) -> float:
        """Mean surprise of these records under one generation of the theory."""
        if isinstance(generation, bool) or not isinstance(generation, int):
            self.store.load_generation(generation)
        if isinstance(record_ids, str) or not isinstance(record_ids, Sequence) or len(record_ids) == 0:
            raise ValueError(f"record_ids: expected a non-empty sequence, got {record_ids!r}")
        if generation == self.generation:
            theory = self.theory
        else:
            theory = self.store.load_generation(generation)
        total = 0.0
        for record_id in record_ids:
            record = self.seen(record_id)
            if record.label.y == "invalid":
                raise ValueError(f"{record_id}: an invalid record has no surprise")
            predicted = theory.predict(record.phi, record.label.oracle)
            value = surprise_bits(predicted.p_fail_valid, record.label.y)
            if value is None:
                raise ValueError(f"{record_id}: an invalid record has no surprise")
            total += value
        return total / len(record_ids)

    def observe(
        self,
        phi: Phi,
        label: Label,
        record_id: str,
        *,
        prediction: Prediction | None = None,
    ) -> Outcome:
        """Record one experiment, settle bets, and roll back an edit whose bet is lost."""
        if record_id in self._by_id:
            raise ValueError(f"record_id {record_id!r} was already observed")
        observation = self.theory.observe(phi, label, record_id, prediction=prediction)
        public = _public_label(label)
        seen = Seen(record_id, phi, public)
        self._by_id[record_id] = seen
        self._records.append(seen)
        owner = self._owner_id(seen)
        seq = self.store.append_journal(
            {
                "kind": "observe",
                "record_id": record_id,
                "phi": phi.to_dict(),
                "label": public.to_dict(),
            }
        )
        bets, rolled = self._settle(phi, label, record_id)
        if not rolled:
            self.store.save(self.theory)
        return Outcome(
            observation=observation,
            seq=seq,
            owner=owner,
            bets=bets,
            rolled_back=rolled,
        )

    def assess(self, proposal: object) -> Assessment:
        """The acceptance test. The theory, the logs and the id counter stay as they are."""
        if not isinstance(proposal, Proposal):
            raise ValueError(f"proposal must be a Proposal, got {type(proposal).__name__}")
        removed, triggers = self._prepare(proposal)
        added = build_added(
            self.theory,
            removed,
            proposal.adds,
            self.records(),
            self._placeholders(len(proposal.adds), "_assess"),
            self._registry,
        )
        return self._judge(proposal, removed, added, triggers)

    def propose(self, proposal: object) -> TheoryEdit:
        """Log one edit. An accepted edit is applied; a refused one changes nothing else."""
        if not isinstance(proposal, Proposal):
            raise ValueError(f"proposal must be a Proposal, got {type(proposal).__name__}")
        removed, triggers = self._prepare(proposal)
        edit_id = f"e{len(self._edit_ids) + 1}"
        added = build_added(
            self.theory,
            removed,
            proposal.adds,
            self.records(),
            self._placeholders(len(proposal.adds), edit_id),
            self._registry,
        )
        verdict = self._judge(proposal, removed, added, triggers)
        version = self.theory.version
        removed_dicts = [hypothesis.to_dict() for hypothesis in removed]
        if not verdict.accepted:
            edit = self._make_edit(
                proposal,
                edit_id,
                version,
                verdict,
                removed_dicts,
                adds=[],
                added=[hypothesis.to_dict() for hypothesis in added],
                generation=None,
                journal_seq=None,
            )
            self._store_edit(edit)
            if verdict.reason in ("trigger", "holdout"):
                self._append_negative(edit, verdict.reason, None)
            return edit
        generation = self.store.close_generation(self.theory, cause=f"edit:{edit_id}")
        real_ids = tuple(self.theory.reserve_id() for _ in proposal.adds)
        rebuilt = build_added(
            self.theory,
            removed,
            proposal.adds,
            self.records(),
            real_ids,
            self._registry,
        )
        for hypothesis_id in proposal.removes:
            self.theory.remove(hypothesis_id)
        for hypothesis in rebuilt:
            self.theory.put(hypothesis)
        journal_seq = self.store.append_journal(
            {"kind": "edit", "edit_id": edit_id, "generation": generation}
        )
        self.store.save(self.theory)
        stored = [self.theory.get(hypothesis_id).to_dict() for hypothesis_id in real_ids]
        edit = self._make_edit(
            proposal,
            edit_id,
            version,
            verdict,
            removed_dicts,
            adds=list(real_ids),
            added=stored,
            generation=generation,
            journal_seq=journal_seq,
        )
        self._store_edit(edit)
        return edit

    def rollback(
        self,
        edit_id: str,
        *,
        reason: str = "manual",
        record_id: str | None = None,
    ) -> tuple[TheoryEdit, ...]:
        """Undo an accepted edit and every accepted edit that was built on top of it.

        The id counter does not go backwards. Observations made since the edit
        are replayed onto the theory as it stood before the edit.
        """
        if reason not in _CALLER_REASONS:
            raise ValueError(f"reason: must be one of {_CALLER_REASONS}, got {reason!r}")
        edit = self._edits.get(edit_id)
        if edit is None or edit.decision != "accepted":
            raise ValueError(f"edit {edit_id!r} is not an accepted edit")
        closed = self.store.close_generation(self.theory, cause=f"rollback:{edit_id}")
        snapshot = self.store.load_generation(edit.payload["generation"])
        state = snapshot.to_dict()
        state["next_id"] = self.theory.next_id
        restored = Theory.from_dict(state, self._registry)
        journal_seq = edit.payload["journal_seq"]
        for entry in self.store.journal(after=journal_seq):
            if entry.get("kind") != "observe":
                continue
            restored.observe(
                Phi.from_dict(entry["phi"]),
                Label.from_dict(entry["label"]),
                entry["record_id"],
            )
        cascaded = [
            other
            for other in self.edits()
            if other.edit_id != edit_id
            and other.decision == "accepted"
            and other.payload["journal_seq"] > journal_seq
        ]
        cascaded.sort(key=lambda item: _edit_order(item.edit_id))
        self.theory = restored
        cascade_ids = [item.edit_id for item in cascaded]
        self.store.append_journal(
            {
                "kind": "rollback",
                "edit_id": edit_id,
                "reason": reason,
                "generation": closed,
                "cascade": cascade_ids,
            }
        )
        self.store.save(self.theory)
        primary = self._mark_rolled(edit_id, reason, record_id, closed)
        self.store.append_edit(primary)
        updated = [primary]
        for other in cascaded:
            marked = self._mark_rolled(other.edit_id, "cascade", None, closed)
            self.store.append_edit(marked)
            updated.append(marked)
        self._append_negative(primary, reason, record_id)
        return tuple(updated)

    def checkpoint(self, note: str) -> int:
        """Close the open generation. Returns the generation number that was closed."""
        if not isinstance(note, str) or note == "":
            raise ValueError(f"note: must be a non-empty string, got {note!r}")
        closed = self.store.close_generation(self.theory, cause=f"checkpoint:{note}")
        self.store.append_journal({"kind": "checkpoint", "note": note, "generation": closed})
        return closed

    def merge_candidates(self) -> tuple[Proposal, ...]:
        """Pairs of the same identity whose shared conjunction is not empty."""
        hypotheses = self.theory.hypotheses
        found: list[Proposal] = []
        for index, first in enumerate(hypotheses):
            for second in hypotheses[index + 1 :]:
                if (first.engine, first.oracle) != (second.engine, second.oracle):
                    continue
                if not _same_identity(first, second):
                    continue
                shared = common_conjunction(first.specific, second.specific, self._registry)
                if not shared:
                    continue
                template = replace(first, specific=shared, source="mdl")
                found.append(
                    Proposal(
                        kind="merge",
                        rationale=(
                            f"{first.hypothesis_id} and {second.hypothesis_id} "
                            "share an identity and a common conjunction"
                        ),
                        proposer="mdl",
                        removes=(first.hypothesis_id, second.hypothesis_id),
                        adds=(template,),
                        bets=default_bets((first, second), (template,), self._registry),
                    )
                )
        return tuple(found)

    def repair_candidates(self) -> tuple[Proposal, ...]:
        """Tighten or split a hypothesis whose positives can avoid the passes inside S."""
        found: list[Proposal] = []
        for hypothesis in self.theory.hypotheses:
            positives = [
                self._by_id[record_id]
                for record_id in hypothesis.positives
                if record_id in self._by_id
            ]
            contradictions = [
                self._by_id[record_id]
                for record_id in hypothesis.contradictions
                if record_id in self._by_id and self._by_id[record_id].label.y == "pass"
            ]
            if not positives or not contradictions:
                continue
            clusters = _cluster(positives, contradictions, self._registry)
            if not clusters or (len(clusters) == 1 and clusters[0] == hypothesis.specific):
                continue
            kind = "revise" if len(clusters) == 1 else "split"
            templates = tuple(
                replace(hypothesis, specific=cluster, source="mdl") for cluster in clusters
            )
            verb = "tightened" if kind == "revise" else "split"
            found.append(
                Proposal(
                    kind=kind,
                    rationale=f"{hypothesis.hypothesis_id} {verb} along its positives",
                    proposer="mdl",
                    removes=(hypothesis.hypothesis_id,),
                    adds=templates,
                    bets=default_bets((hypothesis,), templates, self._registry),
                    trigger=tuple(record.record_id for record in contradictions),
                )
            )
        return tuple(found)

    def compress(self) -> tuple[TheoryEdit, ...]:
        """Apply the first acceptable repair, then merge, and repeat. Refused candidates are not logged."""
        applied: list[TheoryEdit] = []
        for _ in range(_COMPRESS_LIMIT):
            chosen: Proposal | None = None
            for proposal in (*self.repair_candidates(), *self.merge_candidates()):
                if self.assess(proposal).accepted:
                    chosen = proposal
                    break
            if chosen is None:
                return tuple(applied)
            applied.append(self.propose(chosen))
        return tuple(applied)

    def owner_of(self, record_id: str) -> str | None:
        """Who owns this record in the theory as it stands. Unknown records raise ``KeyError``."""
        return self._owner_id(self.seen(record_id))

    def family_of(self, hypothesis_id: str) -> str:
        """A fix set names one family across oracles. Without one, the hypothesis is the family."""
        hypothesis = self.theory.get(hypothesis_id)
        if hypothesis.interventions:
            fixes = "+".join(sorted(hypothesis.interventions))
            return f"{hypothesis.engine}|fix:{fixes}"
        return f"{hypothesis.engine}|{hypothesis.hypothesis_id}"

    def families(self) -> dict[str, tuple[str, ...]]:
        """Family name to hypothesis ids, families in the order they first appear."""
        grouped: dict[str, list[str]] = {}
        for hypothesis in self.theory.hypotheses:
            name = self.family_of(hypothesis.hypothesis_id)
            grouped.setdefault(name, []).append(hypothesis.hypothesis_id)
        return {name: tuple(ids) for name, ids in grouped.items()}

    def partition(self) -> dict[str, str | None]:
        """Each failure, in the order observed, and the family of its owner."""
        found: dict[str, str | None] = {}
        for record in self._records:
            if record.label.y != "fail":
                continue
            owner = self._owner_id(record)
            found[record.record_id] = None if owner is None else self.family_of(owner)
        return found

    def _prepare(self, proposal: Proposal) -> tuple[tuple[Hypothesis, ...], tuple[Seen, ...]]:
        removed = tuple(self.theory.get(hypothesis_id) for hypothesis_id in proposal.removes)
        scopes = {(hypothesis.engine, hypothesis.oracle) for hypothesis in (*removed, *proposal.adds)}
        if len(scopes) > 1:
            raise ValueError("removed and added hypotheses are not in one scope")
        triggers: list[Seen] = []
        for record_id in proposal.trigger:
            try:
                record = self._by_id[record_id]
            except KeyError:
                raise ValueError(f"trigger {record_id!r} was not observed") from None
            if record.label.y == "invalid":
                raise ValueError(f"trigger {record_id!r} is invalid")
            triggers.append(record)
        for template in proposal.adds:
            if template.oracle is None or not reduce_conjunction(template.specific, self._registry):
                raise ValueError("reduced S is empty or the template has no oracle")
        return removed, tuple(triggers)

    def _judge(
        self,
        proposal: Proposal,
        removed: tuple[Hypothesis, ...],
        added: tuple[Hypothesis, ...],
        triggers: tuple[Seen, ...],
    ) -> Assessment:
        marks = (entry["fingerprint"] for entry in self.store.negatives())
        return assess_edit(
            self.theory,
            removed,
            added,
            proposal.bets,
            triggers,
            self.records(),
            marks,
            self._registry,
        )

    def _placeholders(self, count: int, stem: str) -> tuple[str, ...]:
        occupied = {hypothesis.hypothesis_id for hypothesis in self.theory.hypotheses}
        found: list[str] = []
        number = 1
        while len(found) < count:
            candidate = f"{stem}.{number}"
            number += 1
            if candidate in occupied or candidate in found:
                continue
            found.append(candidate)
        return tuple(found)

    def _make_edit(
        self,
        proposal: Proposal,
        edit_id: str,
        version: str,
        verdict: Assessment,
        removed_dicts: list[dict[str, Any]],
        *,
        adds: list[str],
        added: list[dict[str, Any]],
        generation: int | None,
        journal_seq: int | None,
    ) -> TheoryEdit:
        if verdict.accepted:
            bets_state = [{"status": "open", "record_id": None} for _ in proposal.bets]
        else:
            bets_state = [{"status": "void", "record_id": None} for _ in proposal.bets]
        payload = {
            "reason": verdict.reason,
            "fingerprint": verdict.fingerprint,
            "trigger": list(proposal.trigger),
            "holdout": len(verdict.holdout),
            "length_delta": verdict.delta_length,
            "removes": list(proposal.removes),
            "removed": removed_dicts,
            "adds": adds,
            "added": added,
            "generation": generation,
            "journal_seq": journal_seq,
            "bets_state": bets_state,
            "rollback": None,
        }
        return TheoryEdit(
            edit_id=edit_id,
            kind=proposal.kind,
            rationale=proposal.rationale,
            bets=proposal.bets,
            surprise_delta_in=verdict.delta_in,
            surprise_delta_out=verdict.delta_out,
            decision="accepted" if verdict.accepted else "rolled_back",
            proposer=proposal.proposer,
            theory_version=version,
            payload=payload,
        )

    def _store_edit(self, edit: TheoryEdit) -> None:
        if edit.edit_id not in self._edits:
            self._edit_ids.append(edit.edit_id)
        self._edits[edit.edit_id] = edit
        self.store.append_edit(edit)

    def _with_bets(self, edit: TheoryEdit, states: list[dict[str, Any]]) -> TheoryEdit:
        payload = dict(edit.payload)
        payload["bets_state"] = states
        updated = replace(edit, payload=payload)
        self._edits[edit.edit_id] = updated
        return updated

    def _mark_rolled(
        self,
        edit_id: str,
        reason: str,
        record_id: str | None,
        generation: int,
    ) -> TheoryEdit:
        current = self._edits[edit_id]
        payload = dict(current.payload)
        payload["bets_state"] = [
            {"status": "void", "record_id": None} if item["status"] == "open" else dict(item)
            for item in current.payload["bets_state"]
        ]
        payload["rollback"] = {"reason": reason, "record_id": record_id, "generation": generation}
        updated = replace(current, decision="rolled_back", payload=payload)
        self._edits[edit_id] = updated
        return updated

    def _append_negative(self, edit: TheoryEdit, reason: str, record_id: str | None) -> None:
        self.store.append_negative(
            {
                "fingerprint": edit.payload["fingerprint"],
                "edit_id": edit.edit_id,
                "kind": edit.kind,
                "reason": reason,
                "record_id": record_id,
                "claims": _memory_claims(edit.payload, self._registry),
            }
        )

    def _settle(
        self,
        phi: Phi,
        label: Label,
        record_id: str,
    ) -> tuple[tuple[tuple[str, int, str], ...], tuple[str, ...]]:
        settled: list[tuple[str, int, str]] = []
        for edit in self.edits():
            if edit.decision != "accepted":
                continue
            states = [
                {"status": item["status"], "record_id": item["record_id"]}
                for item in edit.payload["bets_state"]
            ]
            changed = False
            broken = False
            for index, (bet, state) in enumerate(zip(edit.bets, states)):
                if state["status"] != "open":
                    continue
                if not bet_matches(bet, phi, label, self._registry):
                    continue
                state["status"] = "kept" if label.y == bet["expect"] else "broken"
                state["record_id"] = record_id
                settled.append((edit.edit_id, index, state["status"]))
                changed = True
                if state["status"] == "broken":
                    broken = True
                    break
            if not changed:
                continue
            self._with_bets(edit, states)
            if broken:
                rolled = self.rollback(edit.edit_id, reason="bet_broken", record_id=record_id)
                return tuple(settled), tuple(item.edit_id for item in rolled)
            self.store.append_edit(self._edits[edit.edit_id])
        return tuple(settled), ()

    def _owner_id(self, record: Seen) -> str | None:
        if record.label.y != "fail":
            return None
        holders = [
            hypothesis.hypothesis_id
            for hypothesis in self.theory.hypotheses
            if record.record_id in hypothesis.positives
        ]
        if not holders:
            return None
        attribution = record.label.cve.get("attribution")
        if (
            isinstance(attribution, dict)
            and attribution.get("status") == "ran"
            and attribution.get("consistent") is True
            and attribution.get("hypothesis_id") in holders
        ):
            return str(attribution["hypothesis_id"])
        return holders[0]
