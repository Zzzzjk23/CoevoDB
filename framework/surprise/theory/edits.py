"""Edits of a theory: what a proposal claims, and whether the records accept it.

Pure functions and frozen values. Nothing here reads or writes a file. The
feature spec check is imported inside :func:`bet_matches` so this module can
load before ``surprise.features.spec``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from typing import Any

from surprise.features.phi import Phi
from surprise.features.registry import Registry
from surprise.harness.contracts import Label

from .constants import ACCEPT_HOLDOUT_MAX, ACCEPT_TOLERANCE_BITS
from .contracts import Hypothesis, Spec
from .hypothesis import apply_negative, position
from .identity import identity_match
from .length import theory_length
from .predict import surprise_bits
from .theory import Theory
from .vspace import reduce_conjunction

EDIT_KINDS = ("add", "revise", "split", "merge", "retire")
REJECT_REASONS = ("negative_memory", "no_bets", "trigger", "holdout", "no_gain")
ROLLBACK_REASONS = ("bet_broken", "manual", "cascade")
BET_STATES = ("open", "kept", "broken", "void")

_EXPECTATIONS = ("pass", "fail")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _distinct_strings(value: object, name: str) -> tuple[str, ...]:
    """Non-empty distinct strings. A bare string is not a sequence of strings."""
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{name}: expected a list or tuple of strings, got {value!r}")
    found: list[str] = []
    for item in value:
        if not isinstance(item, str) or item == "":
            raise ValueError(f"{name}: expected non-empty strings, got {item!r}")
        if item in found:
            raise ValueError(f"{name}: duplicate {item!r}")
        found.append(item)
    return tuple(found)


def _hypotheses(value: object, name: str) -> tuple[Hypothesis, ...]:
    if isinstance(value, (str, Hypothesis)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{name}: expected a list or tuple of hypotheses, got {value!r}")
    found: list[Hypothesis] = []
    for item in value:
        if not isinstance(item, Hypothesis):
            raise ValueError(f"{name}: expected a Hypothesis, got {item!r}")
        found.append(item)
    return tuple(found)


def _bet_sequence(value: object) -> tuple[object, ...]:
    if isinstance(value, (str, dict)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"bets: expected a list or tuple of bets, got {value!r}")
    return tuple(value)


def _normalise_bet(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"spec", "expect"}:
        raise ValueError(f"bet: expected spec and expect, got {value!r}")
    expect = value["expect"]
    if expect not in _EXPECTATIONS:
        raise ValueError(f"expect: must be one of {_EXPECTATIONS}, got {expect!r}")
    spec = Spec.from_dict(value["spec"])
    return {"spec": spec.to_dict(), "expect": expect}


def _check_shape(kind: str, removes: tuple[str, ...], adds: tuple[Hypothesis, ...]) -> None:
    removed, added = len(removes), len(adds)
    ok = (
        (kind == "add" and removed == 0 and added == 1)
        or (kind == "revise" and removed == 1 and added == 1)
        or (kind == "split" and removed == 1 and added >= 2)
        or (kind == "merge" and removed >= 2 and added == 1)
        or (kind == "retire" and removed == 1 and added == 0)
    )
    if not ok:
        raise ValueError(f"{kind}: removes {removed} and adds {added}")


@dataclass(frozen=True)
class Proposal:
    """One edit a proposer hands to the workbench. ``adds`` are templates, not stored hypotheses."""

    kind: str
    rationale: str
    proposer: str
    removes: tuple[str, ...] = ()
    adds: tuple[Hypothesis, ...] = ()
    bets: tuple[dict[str, Any], ...] = ()
    trigger: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in EDIT_KINDS:
            raise ValueError(f"kind: must be one of {EDIT_KINDS}, got {self.kind!r}")
        if not isinstance(self.rationale, str) or self.rationale == "":
            raise ValueError(f"rationale: must be a non-empty string, got {self.rationale!r}")
        if not isinstance(self.proposer, str) or self.proposer == "":
            raise ValueError(f"proposer: must be a non-empty string, got {self.proposer!r}")
        removes = _distinct_strings(self.removes, "removes")
        adds = _hypotheses(self.adds, "adds")
        bets = tuple(_normalise_bet(bet) for bet in _bet_sequence(self.bets))
        trigger = _distinct_strings(self.trigger, "trigger")
        _check_shape(self.kind, removes, adds)
        object.__setattr__(self, "removes", removes)
        object.__setattr__(self, "adds", adds)
        object.__setattr__(self, "bets", bets)
        object.__setattr__(self, "trigger", trigger)


@dataclass(frozen=True)
class Seen:
    """One observation the workbench kept: a record id, its phi, and its label."""

    record_id: str
    phi: Phi
    label: Label


@dataclass(frozen=True)
class Assessment:
    """Result of one acceptance test. ``reason`` is ``None`` when the edit is accepted."""

    accepted: bool
    reason: str | None
    fingerprint: str
    delta_in: float | None
    delta_out: float | None
    delta_length: float | None
    holdout: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.reason is not None and self.reason not in REJECT_REASONS:
            raise ValueError(f"reason: must be one of {REJECT_REASONS}, got {self.reason!r}")
        object.__setattr__(self, "holdout", tuple(self.holdout))


def claim(hypothesis: Hypothesis, registry: Registry | None = None) -> list[Any]:
    """What a hypothesis asserts. Identity of the wording, not of the evidence or the id."""
    return [
        hypothesis.engine,
        hypothesis.oracle,
        sorted(hypothesis.interventions),
        hypothesis.fail_kind,
        hypothesis.error_class,
        hypothesis.behavior_shape,
        list(reduce_conjunction(hypothesis.specific, registry)),
    ]


def _sorted_claims(hypotheses: Sequence[Hypothesis], registry: Registry | None) -> list[list[Any]]:
    claims = [claim(hypothesis, registry) for hypothesis in hypotheses]
    return sorted(claims, key=_canonical_json)


def fingerprint(
    removed: Sequence[Hypothesis],
    added: Sequence[Hypothesis],
    registry: Registry | None = None,
) -> str:
    """16 hex digits of the claims an edit adds, or of the claims a retirement withdraws."""
    body = {
        "adds": _sorted_claims(added, registry),
        "retire": [] if added else _sorted_claims(removed, registry),
    }
    digest = hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()
    return digest[:16]


def _bet_for(hypothesis: Hypothesis, expect: str, registry: Registry | None) -> dict[str, Any]:
    required = reduce_conjunction(hypothesis.specific, registry)
    spec = Spec(engine=hypothesis.engine, oracle=hypothesis.oracle, required=required)
    return {"spec": spec.to_dict(), "expect": expect}


def default_bets(
    removed: Sequence[Hypothesis],
    added: Sequence[Hypothesis],
    registry: Registry | None = None,
) -> tuple[dict[str, Any], ...]:
    """One bet per added hypothesis that its S fails, or per removed hypothesis that the old S passes."""
    if added:
        return tuple(_bet_for(hypothesis, "fail", registry) for hypothesis in added)
    return tuple(_bet_for(hypothesis, "pass", registry) for hypothesis in removed)


def bet_matches(bet: dict[str, Any], phi: Phi, label: Label, registry: Registry | None = None) -> bool:
    """Whether this valid experiment is one the bet speaks about."""
    if label.y == "invalid":
        return False
    spec = Spec.from_dict(bet["spec"])
    if spec.oracle != label.oracle:
        return False
    from surprise.features.spec import check_spec

    return check_spec(phi, spec, registry).ok


def holdout_sample(
    records: Sequence[Seen],
    scopes: Iterable[tuple[str, str]],
    exclude: Iterable[str],
    limit: int = ACCEPT_HOLDOUT_MAX,
) -> tuple[Seen, ...]:
    """Valid records in ``scopes``, skipping ``exclude``, in the order observed.

    Past ``limit``, keep the records whose id hashes are smallest, still in the
    order they were observed.
    """
    scope_set = set(scopes)
    excluded = set(exclude)
    chosen = [
        record
        for record in records
        if record.label.y != "invalid"
        and (record.phi.engine, record.label.oracle) in scope_set
        and record.record_id not in excluded
    ]
    if len(chosen) <= limit:
        return tuple(chosen)
    ranked = sorted(
        chosen,
        key=lambda record: hashlib.sha256(record.record_id.encode("utf-8")).hexdigest(),
    )
    keep = {record.record_id for record in ranked[:limit]}
    return tuple(record for record in chosen if record.record_id in keep)


def build_added(
    theory: Theory,
    removed: Sequence[Hypothesis],
    templates: Sequence[Hypothesis],
    records: Sequence[Seen],
    ids: Sequence[str],
    registry: Registry | None = None,
) -> tuple[Hypothesis, ...]:
    """Hypotheses an edit would add. Evidence is recomputed; the template only supplies identity and S."""
    if not templates:
        return ()
    if len(ids) != len(templates):
        raise ValueError(f"ids: expected {len(templates)}, got {len(ids)}")
    by_id = {record.record_id: record for record in records}
    built: list[Hypothesis] = []
    for template, hypothesis_id in zip(templates, ids):
        specific = reduce_conjunction(template.specific, registry)
        if not specific or template.oracle is None:
            raise ValueError("reduced S is empty or the template has no oracle")
        hypothesis = Hypothesis(
            hypothesis_id=hypothesis_id,
            engine=template.engine,
            interventions=template.interventions,
            plan_delta=template.plan_delta,
            versions=template.versions,
            specific=specific,
            general=((),),
            positives=(),
            negatives=(),
            source=template.source,
            status="active",
            oracle=template.oracle,
            fail_kind=template.fail_kind,
            error_class=template.error_class,
            behavior_shape=template.behavior_shape,
            contradictions=(),
            truncated=False,
        )
        hypothesis = _with_positives(hypothesis, removed, records, by_id, registry)
        for example, record_id in theory.passes(hypothesis.engine, hypothesis.oracle):
            hypothesis = apply_negative(hypothesis, example, record_id, registry).hypothesis
        built.append(hypothesis)
    scratch = Theory(registry)
    for hypothesis in built:
        scratch.put(hypothesis)
    return tuple(scratch.get(hypothesis.hypothesis_id) for hypothesis in built)


def _with_positives(
    hypothesis: Hypothesis,
    removed: Sequence[Hypothesis],
    records: Sequence[Seen],
    by_id: dict[str, Seen],
    registry: Registry | None,
) -> Hypothesis:
    if removed:
        candidate_ids: list[str] = []
        seen: set[str] = set()
        for old in removed:
            for record_id in old.positives:
                if record_id in seen or record_id not in by_id:
                    continue
                seen.add(record_id)
                candidate_ids.append(record_id)
    else:
        candidate_ids = []
        for record in records:
            label = record.label
            if label.y != "fail":
                continue
            if record.phi.engine != hypothesis.engine or label.oracle != hypothesis.oracle:
                continue
            if identity_match(hypothesis, label) is True:
                candidate_ids.append(record.record_id)
    positives: list[str] = []
    for record_id in candidate_ids:
        record = by_id[record_id]
        if position(hypothesis, record.phi, hypothesis.oracle, registry) == "confirmed":
            if record_id not in positives:
                positives.append(record_id)
    return replace(hypothesis, positives=tuple(positives))


def _refused(mark: str, reason: str) -> Assessment:
    return Assessment(
        accepted=False,
        reason=reason,
        fingerprint=mark,
        delta_in=None,
        delta_out=None,
        delta_length=None,
        holdout=(),
    )


def _surprise(theory: Theory, record: Seen) -> float:
    predicted = theory.predict(record.phi, record.label.oracle)
    value = surprise_bits(predicted.p_fail_valid, record.label.y)
    if value is None:
        raise ValueError(f"{record.record_id}: an invalid record has no surprise")
    return value


def _sum_surprise(theory: Theory, records: Sequence[Seen]) -> float:
    total = 0.0
    for record in records:
        total += _surprise(theory, record)
    return total


def _hypothetical(
    before: Theory,
    removed: Sequence[Hypothesis],
    added: Sequence[Hypothesis],
    registry: Registry | None,
) -> Theory:
    """Theory after the edit, for prediction only. Residual and validity are shared, passes are not."""
    after = Theory(registry)
    after.residual = before.residual
    after.validity = before.validity
    removed_ids = {hypothesis.hypothesis_id for hypothesis in removed}
    for hypothesis in before.hypotheses:
        if hypothesis.hypothesis_id not in removed_ids:
            after.put(hypothesis)
    for hypothesis in added:
        after.put(hypothesis)
    return after


def assess_edit(
    before: Theory,
    removed: Sequence[Hypothesis],
    added: Sequence[Hypothesis],
    bets: Sequence[dict[str, Any]],
    triggers: Sequence[Seen],
    records: Sequence[Seen],
    negative_fingerprints: Iterable[str],
    registry: Registry | None = None,
) -> Assessment:
    """Accept only when the edit is not worse on the records and strictly shorter in surprise plus length."""
    mark = fingerprint(removed, added, registry)
    if mark in set(negative_fingerprints):
        return _refused(mark, "negative_memory")
    if not bets:
        return _refused(mark, "no_bets")
    for record in triggers:
        if record.label.y == "invalid":
            raise ValueError(f"trigger {record.record_id!r} is invalid")
    after = _hypothetical(before, removed, added, registry)
    scopes = {(hypothesis.engine, hypothesis.oracle) for hypothesis in (*removed, *added)}
    holdout = holdout_sample(records, scopes, [record.record_id for record in triggers])
    before_in = _sum_surprise(before, triggers)
    after_in = _sum_surprise(after, triggers)
    before_out = _sum_surprise(before, holdout)
    after_out = _sum_surprise(after, holdout)
    delta_in = after_in - before_in
    delta_out = after_out - before_out
    delta_length = theory_length(after) - theory_length(before)
    holdout_ids = tuple(record.record_id for record in holdout)
    if delta_in > ACCEPT_TOLERANCE_BITS:
        reason = "trigger"
    elif delta_out > ACCEPT_TOLERANCE_BITS:
        reason = "holdout"
    elif delta_in + delta_out + delta_length >= -ACCEPT_TOLERANCE_BITS:
        reason = "no_gain"
    else:
        reason = None
    return Assessment(
        accepted=reason is None,
        reason=reason,
        fingerprint=mark,
        delta_in=delta_in,
        delta_out=delta_out,
        delta_length=delta_length,
        holdout=holdout_ids,
    )
