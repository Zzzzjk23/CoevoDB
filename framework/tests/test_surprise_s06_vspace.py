"""Positions, version-space updates, the cap on G, and convergence."""

from __future__ import annotations

import itertools

from surprise.theory import apply_negative, apply_positive, converged, position
from surprise.theory.constants import VS_MAX_GENERAL
from surprise.theory.vspace import specialize

from test_surprise_s06_common import (
    AST_FALLBACK,
    AST_ONLY,
    EXC_ALL,
    HJ,
    L_DUPS,
    NO_DATA,
    PLAIN,
    S_HAND,
    SELECT,
    SET_ALL,
    T_NULL,
    TOP,
    X1,
    X3,
    X4,
    X7,
    hypothesis,
    phi,
)


def _snapshot(item):
    return item.to_dict()


def test_position_has_five_results() -> None:
    fresh = hypothesis()
    assert position(fresh, phi(X1), "cross_dbms") == "confirmed"
    assert position(fresh, phi(X3), "cross_dbms") == "pending"
    narrowed = hypothesis(general=((L_DUPS,),))
    assert position(narrowed, phi(X4), "cross_dbms") == "pending"
    assert position(narrowed, phi(PLAIN), "cross_dbms") == "outside"
    assert position(narrowed, phi(X1), "tlp") == "out_of_scope"
    assert position(narrowed, phi(X1, engine="duckdb"), "cross_dbms") == "out_of_scope"
    assert position(narrowed, phi((EXC_ALL, SELECT), layers=NO_DATA), "cross_dbms") == "undetermined"
    assert position(narrowed, phi((EXC_ALL, SELECT), layers=AST_ONLY), "cross_dbms") == "undetermined"

    # A fallback ast layer was computed. A hypothesis that only mentions ast can be judged.
    ast_only = hypothesis(specific=(EXC_ALL,), general=TOP)
    fallback = phi((EXC_ALL, SELECT), layers=AST_FALLBACK)
    assert position(ast_only, fallback, "cross_dbms") == "confirmed"
    assert position(ast_only, phi((EXC_ALL, SELECT), layers=AST_ONLY), "cross_dbms") == "confirmed"


def test_apply_positive_each_position_and_record_order() -> None:
    fresh = hypothesis()
    before = _snapshot(fresh)

    duplicate = apply_positive(fresh, phi(X1), "b")
    assert duplicate.outcome == "duplicate"
    assert duplicate.hypothesis.specific == S_HAND
    assert duplicate.hypothesis.general == TOP
    assert duplicate.hypothesis.positives == ("b",)
    assert _snapshot(fresh) == before

    again = apply_positive(duplicate.hypothesis, phi(X1), "b")
    assert again.outcome == "duplicate"
    assert again.hypothesis.positives == ("b",)
    extended = apply_positive(again.hypothesis, phi(X1), "a")
    assert extended.hypothesis.positives == ("b", "a")

    pending = apply_positive(fresh, phi(X4), "r1")
    assert pending.outcome == "generalized"
    assert pending.hypothesis.specific == tuple(sorted((SET_ALL, L_DUPS)))
    assert pending.hypothesis.general == TOP
    assert pending.hypothesis.positives == ("r1",)
    assert apply_positive(fresh, phi(X4), "r1") == pending

    # A positive example drops the G member that required a NULL.
    branched = hypothesis(specific=tuple(sorted(X1)), general=((L_DUPS,), (T_NULL,), (HJ,)))
    moved = apply_positive(branched, phi(X7), "r7")
    assert moved.outcome == "generalized"
    assert moved.hypothesis.specific == tuple(sorted(X7))
    assert moved.hypothesis.general == ((L_DUPS,), (HJ,))

    outside = apply_positive(hypothesis(general=((L_DUPS,),)), phi(PLAIN), "r0")
    assert outside.outcome == "outside"
    assert outside.hypothesis == hypothesis(general=((L_DUPS,),))

    undetermined = apply_positive(fresh, phi((EXC_ALL, SELECT), layers=AST_ONLY), "r9")
    assert undetermined.outcome == "undetermined"
    assert undetermined.hypothesis == fresh

    foreign = apply_positive(fresh, phi(X1, engine="duckdb"), "r8")
    assert foreign.outcome == "out_of_scope"
    assert foreign.hypothesis == fresh


def test_apply_negative_each_position_and_record_order() -> None:
    fresh = hypothesis()
    specialized = apply_negative(fresh, phi(X3), "b")
    assert specialized.outcome == "specialized"
    assert specialized.hypothesis.specific == S_HAND
    assert specialized.hypothesis.general == ((L_DUPS,),)
    assert specialized.hypothesis.negatives == ("b",)
    assert specialized.hypothesis.contradictions == ()
    assert specialized.hypothesis.truncated is False
    assert apply_negative(fresh, phi(X3), "b") == specialized

    again = apply_negative(specialized.hypothesis, phi(PLAIN), "b")
    assert again.outcome == "outside"
    assert again.hypothesis.negatives == ("b",)

    added = apply_negative(specialized.hypothesis, phi(X4), "a")
    assert added.outcome == "specialized"
    assert added.hypothesis.negatives == ("b", "a")
    assert added.hypothesis.general == (S_HAND,)

    # A pass inside S is recorded in both E- and contradictions, once.
    conflict = apply_negative(added.hypothesis, phi(X1), "c")
    assert conflict.outcome == "contradiction"
    assert conflict.hypothesis.specific == S_HAND
    assert conflict.hypothesis.general == (S_HAND,)
    assert conflict.hypothesis.negatives == ("b", "a", "c")
    assert conflict.hypothesis.contradictions == ("c",)
    repeated = apply_negative(conflict.hypothesis, phi(X1), "c")
    assert repeated.outcome == "contradiction"
    assert repeated.hypothesis.negatives == ("b", "a", "c")
    assert repeated.hypothesis.contradictions == ("c",)

    undetermined = apply_negative(fresh, phi((EXC_ALL, SELECT), layers=NO_DATA), "r9")
    assert undetermined.outcome == "undetermined"
    assert undetermined.hypothesis == fresh
    assert apply_negative(fresh, phi(X1, engine="sqlite"), "r8").outcome == "out_of_scope"


def test_truncated_stays_set_when_a_later_specialisation_fits() -> None:
    marked = hypothesis(general=((L_DUPS,),), truncated=True)
    update = apply_negative(marked, phi(X4), "r2")
    assert update.outcome == "specialized"
    assert update.hypothesis.general == (S_HAND,)
    assert update.hypothesis.truncated is True


def test_g_is_capped_at_vs_max_general_and_marked() -> None:
    leaves = tuple(f"plan:P{index:02d}" for index in range(1, 15))
    current = hypothesis(specific=leaves, general=TOP, engine="duckdb")
    assert VS_MAX_GENERAL == 64
    for count in range(1, 8):
        missing = set(leaves[2 * (count - 1):2 * count])
        example = phi(tuple(leaf for leaf in leaves if leaf not in missing), engine="duckdb")
        full = specialize(current.general, current.specific, example)
        update = apply_negative(current, example, f"n{count}")
        current = update.hypothesis
        pairs = [leaves[2 * i:2 * i + 2] for i in range(count)]
        members = tuple(sorted(tuple(sorted(choice)) for choice in itertools.product(*pairs)))
        if len(members) <= VS_MAX_GENERAL:
            assert full == members
            assert current.general == members
            assert current.truncated is False
        else:
            assert len(full) == len(members) > VS_MAX_GENERAL
            assert current.general == members[:VS_MAX_GENERAL]
            assert current.truncated is True
        assert update.outcome == "specialized"


def test_converged_means_g_has_shrunk_onto_s() -> None:
    assert converged(hypothesis(general=(S_HAND,))) is True
    assert converged(hypothesis()) is False
    assert converged(hypothesis(general=((L_DUPS,),))) is False
    # The longer member is implied by S, so it does not keep the version space open.
    extra = tuple(sorted((EXC_ALL, L_DUPS, SELECT)))
    assert converged(hypothesis(general=(extra, S_HAND))) is True


def test_one_hand_written_sequence_matches_each_rule() -> None:
    current = hypothesis()
    steps = (
        ("-", X3, "specialized", S_HAND, ((L_DUPS,),)),
        ("-", X4, "specialized", S_HAND, (S_HAND,)),
        ("-", X1, "contradiction", S_HAND, (S_HAND,)),
        ("+", X1, "duplicate", S_HAND, (S_HAND,)),
        ("+", X4, "outside", S_HAND, (S_HAND,)),
    )
    for index, (kind, features, outcome, specific, general) in enumerate(steps, start=1):
        apply = apply_positive if kind == "+" else apply_negative
        update = apply(current, phi(features), f"r{index}")
        assert update.outcome == outcome
        assert update.hypothesis.specific == specific
        assert update.hypothesis.general == general
        current = update.hypothesis
    assert current.positives == ("r4",)
    assert current.negatives == ("r1", "r2", "r3")
    assert current.contradictions == ("r3",)
