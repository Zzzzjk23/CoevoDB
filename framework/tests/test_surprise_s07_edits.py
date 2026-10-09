"""Proposals, claims, fingerprints, bets, and the held-out sample."""

from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from surprise.features.registry import default_registry
from surprise.harness.contracts import IdentityEvidence, Label
from surprise.theory import (
    EDIT_KINDS,
    Proposal,
    Seen,
    bet_matches,
    claim,
    default_bets,
    fingerprint,
    holdout_sample,
)
from surprise.theory.constants import ACCEPT_HOLDOUT_MAX

from test_surprise_s06_common import (
    AST_ONLY,
    EXC_ALL,
    INT_ALL,
    L_DUPS,
    S_HAND,
    X1,
    X3,
    hypothesis,
    phi,
)

ORACLE = "cross_dbms"
ENGINE = "datafusion"


def _pass(oracle: str = ORACLE) -> Label:
    return Label(y="pass", oracle=oracle)


def _fail() -> Label:
    return Label(
        y="fail",
        oracle=ORACLE,
        fail_kind="wrong_result",
        identity=IdentityEvidence(error_class=None, behavior={"missing": 1}),
    )


def _invalid() -> Label:
    return Label(y="invalid", oracle=ORACLE, invalid_reason="query_error")


def _bet(required, forbidden=(), expect="fail", *, engine=ENGINE, oracle=ORACLE):
    from surprise.theory import Spec

    return {
        "spec": Spec(
            engine=engine, oracle=oracle, required=tuple(required), forbidden=tuple(forbidden)
        ).to_dict(),
        "expect": expect,
    }


def _proposal(**overrides) -> Proposal:
    base = hypothesis()
    fields = dict(
        kind="revise",
        rationale="why",
        proposer="test",
        removes=("h1",),
        adds=(base,),
        bets=(_bet([EXC_ALL]),),
        trigger=("r1",),
    )
    fields.update(overrides)
    return Proposal(**fields)


def test_proposal_keeps_normalised_bets_and_allows_each_kind():
    base = hypothesis()
    proposal = _proposal()
    assert proposal.removes == ("h1",)
    assert proposal.trigger == ("r1",)
    assert proposal.bets == (_bet([EXC_ALL]),)
    assert proposal.adds == (base,)
    assert Proposal(kind="retire", rationale="why", proposer="test", removes=("h1",)).adds == ()
    assert Proposal(kind="revise", rationale="why", proposer="test", removes=("h1",), adds=(base,)).bets == ()
    for kind, removes, adds in (
        ("add", (), (base,)),
        ("split", ("h1",), (base, base, base)),
        ("merge", ("h1", "h2", "h3"), (base,)),
        ("retire", ("h1",), ()),
    ):
        Proposal(kind=kind, rationale="why", proposer="test", removes=removes, adds=adds)
    assert EDIT_KINDS == ("add", "revise", "split", "merge", "retire")


def test_proposal_rejects_each_malformed_shape():
    base = hypothesis()
    bad = [
        {"kind": "rewrite"},
        {"rationale": ""},
        {"proposer": ""},
        {"removes": ()},
        {"removes": ("h1", "h2")},
        {"adds": ()},
        {"adds": (base, base)},
        {"kind": "add"},
        {"kind": "split"},
        {"kind": "merge"},
        {"kind": "retire"},
        {"kind": "merge", "removes": ("h1", "h1")},
        {"trigger": ("r1", "r1")},
        {"adds": (base.to_dict(),)},
        {"bets": ({"spec": _bet([EXC_ALL])["spec"]},)},
        {"bets": ({"spec": _bet([EXC_ALL])["spec"], "expect": "invalid"},)},
        {"bets": ({"spec": {"engine": ENGINE}, "expect": "fail"},)},
        {"bets": ({"spec": _bet([EXC_ALL])["spec"], "expect": "fail", "weight": 2},)},
        {"bets": _bet([EXC_ALL])},
        {"trigger": "r1"},
        {"removes": "h1"},
    ]
    for change in bad:
        with pytest.raises(ValueError):
            _proposal(**change)


def test_claim_and_fingerprint_ignore_identity_of_the_wording():
    registry = default_registry()
    base = hypothesis(specific=(L_DUPS, EXC_ALL, "ast"))
    got = claim(base, registry)
    assert got == [
        ENGINE,
        ORACLE,
        [],
        "wrong_result",
        None,
        "missing_only",
        list(S_HAND),
    ]
    same = replace(
        base,
        hypothesis_id="other",
        general=((L_DUPS,),),
        positives=("r1",),
        negatives=("r2",),
        source="llm",
        specific=(EXC_ALL, L_DUPS, EXC_ALL),
        plan_delta=("x",),
        versions={"a": 1},
    )
    assert claim(same, registry) == got
    mark = fingerprint((), (base,), registry)
    assert len(mark) == 16 and all(c in "0123456789abcdef" for c in mark)
    replaced = hypothesis(specific=(INT_ALL,), hypothesis_id="gone")
    assert fingerprint((replaced,), (same,), registry) == mark
    assert fingerprint((base,), (), registry) != mark
    assert fingerprint((base,), (), registry) == fingerprint((same,), (), registry)
    other = hypothesis(specific=(INT_ALL,), behavior_shape="extra_only")
    assert fingerprint((), (base, other), registry) == fingerprint((), (other, base), registry) != mark
    changed = [
        replace(base, specific=(EXC_ALL,)),
        replace(base, behavior_shape="extra_only"),
        replace(base, oracle="tlp"),
        replace(base, engine="duckdb"),
        replace(base, interventions=("filter_pushdown",)),
        replace(base, error_class="X"),
    ]
    marks = {fingerprint((), (item,), registry) for item in changed}
    assert mark not in marks and len(marks) == len(changed)


def test_default_bets_follow_the_added_or_the_retired_hypotheses():
    registry = default_registry()
    added = hypothesis(specific=(L_DUPS, EXC_ALL, "ast"))
    other = hypothesis(specific=(INT_ALL,), hypothesis_id="h2", behavior_shape="extra_only")
    assert default_bets((), (added, other), registry) == (_bet(S_HAND), _bet((INT_ALL,)))
    assert default_bets((added,), (), registry) == (_bet(S_HAND, (), "pass"),)


def test_bet_matches_misses_invalid_oracle_engine_and_undecided_layers():
    registry = default_registry()
    bet = _bet([EXC_ALL], [L_DUPS], "pass")
    assert bet_matches(bet, phi(X3), _pass(), registry) is True
    assert bet_matches(bet, phi(X3), _fail(), registry) is True
    assert bet_matches(bet, phi(X1), _pass(), registry) is False
    assert bet_matches(bet, phi(X3), _invalid(), registry) is False
    assert bet_matches(bet, phi(X3), _pass("tlp"), registry) is False
    blind = phi((EXC_ALL,), layers=AST_ONLY)
    assert bet_matches(bet, blind, _pass(), registry) is False
    assert bet_matches(_bet([EXC_ALL]), blind, _pass(), registry) is True
    assert bet_matches(_bet([EXC_ALL], engine="duckdb"), phi(X3), _pass(), registry) is False


def test_holdout_sample_keeps_order_and_truncates_by_id_hash():
    records = [
        Seen(
            f"r{i}",
            phi(X3 if i % 2 else X1),
            _pass() if i % 2 else _fail(),
        )
        for i in range(40)
    ]
    records += [
        Seen("inv", phi(X3), _invalid()),
        Seen("tlp", phi(X3), _pass("tlp")),
        Seen("duck", phi(X3, engine="duckdb"), _pass()),
    ]
    scope = {(ENGINE, ORACLE)}
    kept = holdout_sample(records, scope, ["r3", "r4"])
    assert [item.record_id for item in kept] == [f"r{i}" for i in range(40) if i not in (3, 4)]
    cut = holdout_sample(records, scope, [], limit=7)
    wanted = sorted(
        sorted((f"r{i}" for i in range(40)), key=lambda record_id: hashlib.sha256(record_id.encode("utf-8")).hexdigest())[:7],
        key=lambda record_id: int(record_id[1:]),
    )
    assert [item.record_id for item in cut] == wanted
    assert len(holdout_sample(records, scope, [])) == 40
    assert holdout_sample(records, {("duckdb", ORACLE)}, []) == (records[-1],)
    assert ACCEPT_HOLDOUT_MAX == 1000


def test_hypothesis_objects_are_not_accepted_as_dict_payloads():
    with pytest.raises(ValueError):
        Proposal(
            kind="add",
            rationale="why",
            proposer="test",
            adds=(hypothesis().to_dict(),),  # type: ignore[arg-type]
        )
