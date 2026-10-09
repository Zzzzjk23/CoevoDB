"""Constants, description length, and the small Theory and conjunction additions."""

from __future__ import annotations

import pytest

from surprise.harness.contracts import Label
from surprise.theory import (
    Theory,
    common_conjunction,
    generalize,
    hypothesis_length,
    reduce_conjunction,
    theory_length,
)
from surprise.theory import constants
from surprise.theory.constants import MDL_HYPOTHESIS_BITS, MDL_LITERAL_BITS

from test_surprise_s06_common import (
    AST_ONLY,
    EXC_ALL,
    INT_ALL,
    L_DUPS,
    PLAIN,
    S_HAND,
    SELECT,
    SET_ALL,
    X1,
    X3,
    X4,
    fail_label,
    hypothesis,
    phi,
)


ORACLE = "cross_dbms"


def _pass(oracle: str = ORACLE) -> Label:
    return Label(y="pass", oracle=oracle)


def _profiled(shape: str = "missing") -> Label:
    behavior = {"missing": 1, "extra": 0} if shape == "missing" else {"missing": 0, "extra": 1}
    profile = {
        "status": "ran",
        "reason": None,
        "fix_kind": "non_optimizer",
        "fix_set": [],
        "plan_diff": [],
        "version_ladder": "longstanding",
        "witness_switches": [],
    }
    return fail_label(behavior=behavior, cve={"profile": profile})


def test_the_four_new_constants_have_their_values_and_types() -> None:
    expected = {
        "MDL_HYPOTHESIS_BITS": (8.0, float),
        "MDL_LITERAL_BITS": (7.4, float),
        "ACCEPT_HOLDOUT_MAX": (1000, int),
        "ACCEPT_TOLERANCE_BITS": (1e-9, float),
    }
    found = constants.as_dict()
    for name, (value, kind) in expected.items():
        assert getattr(constants, name) == value
        assert type(getattr(constants, name)) is kind
        assert found[name] == value
        assert type(found[name]) is kind


def test_length_counts_only_literals_of_s() -> None:
    one = hypothesis(specific=S_HAND)
    two = hypothesis(hypothesis_id="h-b", specific=(SELECT,), general=((SELECT,),))
    wider = hypothesis(
        specific=S_HAND,
        general=((L_DUPS,), (EXC_ALL,)),
        positives=("a", "b"),
        negatives=("c",),
        source="other",
    )
    assert hypothesis_length(one) == MDL_HYPOTHESIS_BITS + MDL_LITERAL_BITS * 2
    assert hypothesis_length(two) == MDL_HYPOTHESIS_BITS + MDL_LITERAL_BITS
    assert hypothesis_length(wider) == hypothesis_length(one)
    theory = Theory()
    assert theory_length(theory) == 0.0
    assert isinstance(theory_length(theory), float)
    theory.put(one)
    theory.put(two)
    assert theory_length(theory) == hypothesis_length(one) + hypothesis_length(two)
    assert theory_length((one, two)) == theory_length(theory)
    assert theory_length([]) == 0.0


def test_next_id_remove_and_passes() -> None:
    theory = Theory()
    theory.put(hypothesis(hypothesis_id="h1", specific=(EXC_ALL,), general=((EXC_ALL,),)))
    theory.put(
        hypothesis(
            hypothesis_id="h2",
            specific=(INT_ALL,),
            general=((INT_ALL,),),
            behavior_shape="extra_only",
        )
    )
    theory.put(hypothesis(hypothesis_id="h3", specific=(SELECT,), general=((SELECT,),)))
    assert theory.next_id == theory.to_dict()["next_id"] == 1
    gone = theory.remove("h2")
    assert gone.hypothesis_id == "h2"
    assert [item.hypothesis_id for item in theory.hypotheses] == ["h1", "h3"]
    assert theory.next_id == 1
    with pytest.raises(KeyError):
        theory.remove("h2")
    with pytest.raises(KeyError):
        theory.get("h2")
    theory.observe(phi(PLAIN), _pass(), "p1")
    theory.observe(phi(X1), _pass(), "p2")
    remembered = theory.passes("datafusion", ORACLE)
    stored = theory.to_dict()["passes"]["datafusion|cross_dbms"]
    assert isinstance(remembered, tuple)
    assert [(item.to_dict(), record_id) for item, record_id in remembered] == [
        (row["phi"], row["record_id"]) for row in stored
    ]
    assert [record_id for _phi, record_id in remembered] == ["p1", "p2"]
    assert theory.passes("duckdb", "tlp") == ()


def test_reserve_id_and_a_new_family_never_share_an_id() -> None:
    theory = Theory()
    theory.put(
        hypothesis(
            hypothesis_id="h2",
            specific=(INT_ALL,),
            general=((INT_ALL,),),
            behavior_shape="extra_only",
        )
    )
    assert theory.reserve_id() == "h1"
    assert theory.next_id == 2
    assert [item.hypothesis_id for item in theory.hypotheses] == ["h2"]
    assert theory.reserve_id() == "h3"
    opened = theory.observe(phi(PLAIN), _profiled(), "f1").opened
    assert opened == "h4"
    theory.put(hypothesis(hypothesis_id="h5", specific=(SELECT,), general=((SELECT,),)))
    assert theory.reserve_id() == "h6"
    again = theory.observe(phi((SELECT,), engine="postgres", layers=AST_ONLY), _profiled("extra"), "f2").opened
    assert again == "h7"
    assert len({opened, again, "h1", "h2", "h3", "h5", "h6"}) == 7
    # an id minted by hand is skipped by the next family too
    fresh = Theory()
    reserved = fresh.reserve_id()
    family = fresh.observe(phi((SELECT,), layers=AST_ONLY), _profiled(), "f3").opened
    assert reserved == "h1"
    assert family == "h2"
    assert fresh.next_id == 3


def test_common_conjunction_is_what_both_imply() -> None:
    assert common_conjunction(S_HAND, S_HAND) == S_HAND
    assert common_conjunction(S_HAND, ()) == ()
    assert common_conjunction((), S_HAND) == ()
    assert common_conjunction((EXC_ALL,), (INT_ALL,)) == (SET_ALL,)
    assert common_conjunction((INT_ALL,), (EXC_ALL,)) == (SET_ALL,)
    left = reduce_conjunction(phi(X1).features)
    shared = common_conjunction(S_HAND, left)
    assert shared == common_conjunction(left, S_HAND)
    assert shared == generalize(S_HAND, phi(X1))
    assert common_conjunction(S_HAND, reduce_conjunction(phi(X4).features)) == generalize(S_HAND, phi(X4))
    assert common_conjunction(X3, X3) == reduce_conjunction(X3)
    with pytest.raises(ValueError):
        common_conjunction(("no:such:feature",), S_HAND)
    with pytest.raises(ValueError):
        common_conjunction(S_HAND, ("no:such:feature",))
