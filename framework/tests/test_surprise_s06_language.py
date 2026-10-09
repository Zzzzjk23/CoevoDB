"""Conjunction language: reduction, coverage, generalisation, specialisation."""

from __future__ import annotations

import pytest

from surprise.features.registry import default_registry
from surprise.features.vocabulary import FeatureDef
from surprise.theory import covers, generalize, reduce_conjunction, specialize

from test_surprise_s06_common import (
    D_SETOP,
    D_TABLE,
    EXC_ALL,
    HJ,
    INT_ALL,
    JOINQ,
    L_DUPS,
    PLAIN,
    S_HAND,
    SELECT,
    SET_ALL,
    SET_OP,
    SRC,
    T_DUPS,
    TOP,
    UNION_EXEC,
    X1,
    X4,
    X5,
    X6,
    X7,
    phi,
)


def test_reduce_drops_layer_roots_ancestors_and_duplicates() -> None:
    # Empty, and a set made only of layer roots, both reduce to nothing.
    assert reduce_conjunction(()) == ()
    assert reduce_conjunction(("ast", "plan", "data")) == ()
    assert reduce_conjunction(("plan",)) == ()

    # A more specific id implies its ancestors, including a class above a leaf.
    assert reduce_conjunction((EXC_ALL, SET_ALL, SET_OP, "ast")) == (EXC_ALL,)
    assert reduce_conjunction((SET_ALL, EXC_ALL, INT_ALL)) == tuple(sorted((EXC_ALL, INT_ALL)))

    # Sibling leaves stay; only the shared class is dropped.
    assert reduce_conjunction((L_DUPS, "data:setop:left_has_null", D_SETOP)) == tuple(
        sorted((L_DUPS, "data:setop:left_has_null"))
    )

    # Duplicates collapse, and the result is sorted rather than left in input order.
    assert reduce_conjunction((HJ, SRC, HJ, EXC_ALL)) == tuple(sorted((EXC_ALL, SRC, HJ)))
    assert reduce_conjunction([HJ, SRC, HJ, EXC_ALL]) == reduce_conjunction((EXC_ALL, SRC, HJ))
    assert reduce_conjunction({HJ, SRC, EXC_ALL}) == tuple(sorted((EXC_ALL, SRC, HJ)))


def test_reduce_is_idempotent_and_ignores_order() -> None:
    ids = (L_DUPS, SET_ALL, "ast", L_DUPS, SET_OP)
    reduced = reduce_conjunction(ids)
    assert reduce_conjunction(reduced) == reduced
    assert reduce_conjunction(tuple(reversed(ids))) == reduced
    assert reduce_conjunction(list(ids)) == reduced


def test_reduce_rejects_a_bare_string_a_non_string_and_an_unknown_id() -> None:
    with pytest.raises(ValueError):
        reduce_conjunction(EXC_ALL)
    with pytest.raises(ValueError):
        reduce_conjunction((EXC_ALL, 3))
    with pytest.raises(ValueError):
        reduce_conjunction(("ast:no_such_feature",))
    with pytest.raises(ValueError):
        reduce_conjunction(("nope:x",))
    with pytest.raises(ValueError):
        reduce_conjunction(("ast:fn:",))
    with pytest.raises(ValueError):
        reduce_conjunction(None)


def test_reduce_uses_the_registry_argument() -> None:
    registry = default_registry()
    registry.register(
        FeatureDef(
            feature_id="ast:expr:marker",
            kind="leaf",
            parent="ast:expr",
            layer="ast",
            description="marker",
            source="test",
            definition={"kind": "regex", "pattern": "marker"},
            accepted=False,
            acceptance=None,
        )
    )
    assert reduce_conjunction(("ast:expr:marker", "ast:expr"), registry) == ("ast:expr:marker",)
    with pytest.raises(ValueError):
        reduce_conjunction(("ast:expr:marker",))


def test_open_family_member_is_a_literal_and_its_layer_root_is_not() -> None:
    # plan:HashJoinExec's only ancestor is the layer root, so the member stays.
    assert reduce_conjunction((HJ, "plan")) == (HJ,)
    assert reduce_conjunction(("ast:fn:upper", "ast:fn")) == ("ast:fn:upper",)
    assert covers((HJ,), phi((SELECT, HJ))) is True
    assert covers((HJ,), phi((SELECT, UNION_EXEC))) is False
    assert covers(("ast:fn",), phi(("ast:fn:upper",))) is True


def test_covers_is_the_closure_and_rejects_an_unknown_id() -> None:
    example = phi(X1)
    assert covers((), example) is True
    assert covers((EXC_ALL,), example) is True
    assert covers((SET_ALL,), example) is True
    assert covers((SET_OP, D_SETOP), example) is True
    assert covers((INT_ALL,), example) is False
    assert covers((EXC_ALL, L_DUPS), phi(X7)) is True
    assert covers((D_TABLE,), phi(PLAIN)) is False
    with pytest.raises(ValueError):
        covers(("ast:no_such_feature",), example)


def test_generalize_drops_features_and_climbs_one_class_then_another() -> None:
    # Features the positive example lacks are deleted; shared leaves stay.
    dropped = generalize(tuple(sorted(X1)), phi(X7))
    assert dropped == tuple(sorted(X7))
    assert L_DUPS in dropped and "data:setop:left_has_null" not in dropped

    # except_all and intersect_all meet at ast:set_op:all.
    climbed = generalize(S_HAND, phi(X4))
    assert climbed == tuple(sorted((SET_ALL, L_DUPS)))

    # ast:set_op:all and the distinct except meet one class further up.
    climbed_again = generalize(climbed, phi(X6))
    assert climbed_again == tuple(sorted((SET_OP, L_DUPS)))
    assert generalize(climbed_again, phi(X6)) == climbed_again

    # Nothing but the layer roots is shared, and those do not enter a conjunction.
    assert generalize(S_HAND, phi(PLAIN)) == ()
    assert generalize((), phi(X1)) == ()


def test_generalize_of_two_plan_operators_keeps_only_the_shared_literal() -> None:
    shared = generalize((HJ, SELECT), phi((UNION_EXEC, SELECT)))
    assert shared == (SELECT,)


def test_specialize_takes_the_excluding_ancestor_not_the_leaf() -> None:
    # A query with no set operation is excluded by ast:set_op, not by except_all.
    got = specialize(TOP, tuple(sorted(X1)), phi(PLAIN))
    assert got == ((SET_OP,), (D_SETOP,), (D_TABLE,), (HJ,))
    assert all(EXC_ALL not in member for member in got)


def test_specialize_keeps_a_member_that_already_excludes_the_negative() -> None:
    got = specialize(((INT_ALL,), (L_DUPS,), (T_DUPS,)), tuple(sorted(X4)), phi(X1))
    assert got == ((INT_ALL,),)
    assert specialize(((EXC_ALL,),), tuple(sorted(X1)), phi(X4)) == ((EXC_ALL,),)


def test_specialize_drops_redundant_members_and_sorts_by_length_then_text() -> None:
    broad = specialize(TOP, tuple(sorted(X1)), phi(PLAIN))
    narrowed = specialize(broad, tuple(sorted(X1)), phi(JOINQ))
    assert narrowed == ((SET_OP,), (D_SETOP,), (T_DUPS,))

    # Length 1 comes before length 2; equal lengths are lexicographic.
    ordered = specialize(((SET_ALL,),), tuple(sorted(X1)), phi(X5))
    assert ordered == ((EXC_ALL,), tuple(sorted((SET_ALL, HJ))))
    assert [len(member) for member in ordered] == [1, 2]


def test_specialize_of_a_class_literal_climbs_only_as_far_as_the_negative_requires() -> None:
    specific = tuple(sorted((SET_ALL, L_DUPS)))
    # The whole set-operation branch is absent, so the class climbs to ast:set_op.
    assert specialize(TOP, specific, phi(PLAIN)) == ((SET_OP,), (D_SETOP,))
    # A distinct EXCEPT is outside ast:set_op:all but still inside ast:set_op.
    assert specialize(TOP, specific, phi(X6)) == ((SET_ALL,),)


def test_specialize_of_an_open_family_member_uses_only_that_member() -> None:
    specific = tuple(sorted((HJ, SELECT)))
    got = specialize(TOP, specific, phi((UNION_EXEC, SELECT)))
    assert got == ((HJ,),)


def test_specialize_rejects_a_negative_inside_the_specific_boundary() -> None:
    inside = phi((EXC_ALL, L_DUPS, SELECT))
    with pytest.raises(ValueError):
        specialize(TOP, S_HAND, inside)
