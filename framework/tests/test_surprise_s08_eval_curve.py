"""Surprise of one record, the windowed curve, and its teeth."""

from __future__ import annotations

import math

import pytest

from surprise.harness.contracts import ExperimentRecord, Label, SqlCase
from surprise.metrics.curve import record_surprise, surprise_curve, teeth
from surprise.theory.predict import surprise_bits


def record(y: str, p_t: float | None, *, seq: int = 1, reason: str = "query_error") -> ExperimentRecord:
    if y == "fail":
        label = Label(y="fail", oracle="tlp", fail_kind="wrong_result")
    elif y == "pass":
        label = Label(y="pass", oracle="tlp")
    else:
        label = Label(y="invalid", oracle="tlp", invalid_reason=reason)
    return ExperimentRecord(
        record_id=f"r{seq}",
        run_id="run",
        seq=seq,
        case=SqlCase(engine="duckdb", setup=(), query="select 1"),
        label=label,
        purpose="curve",
        created_at="2026-10-15T00:00:00+00:00",
        p_t=p_t,
    )


def test_record_surprise_skips_invalid_and_missing_predictions() -> None:
    assert record_surprise(record("invalid", 0.5)) is None
    assert record_surprise(record("invalid", None)) is None
    assert record_surprise(record("fail", None)) is None
    assert record_surprise(record("pass", None)) is None
    assert record_surprise(record("fail", 0.25)) == surprise_bits(0.25, "fail")
    assert record_surprise(record("pass", 0.25)) == surprise_bits(0.25, "pass")
    assert record_surprise(record("fail", 0.5)) == 1.0
    assert record_surprise(record("pass", 0.5)) == 1.0


def test_curve_uses_whole_windows_in_the_given_order() -> None:
    # seq is deliberately not the list order: the curve follows the sequence it is given.
    rows = [
        record("fail", 0.25, seq=5),
        record("invalid", 0.01, seq=1),
        record("fail", None, seq=4),
        record("pass", 0.5, seq=2),
        record("fail", 0.01, seq=3),
    ]
    curve = surprise_curve(rows, window=2)
    assert len(curve) == 2
    assert curve[0] == pytest.approx(surprise_bits(0.25, "fail"))
    assert curve[1] == pytest.approx(1.0)
    assert surprise_curve(rows, window=4) == [pytest.approx((surprise_bits(0.25, "fail") + 1.0) / 2)]
    assert surprise_curve(rows, window=1)[0] == pytest.approx(2.0)
    assert surprise_curve(rows, window=len(rows) + 1) == []
    assert surprise_curve([], window=100) == []


def test_curve_window_of_only_invalid_executions_is_none() -> None:
    rows = [
        record("invalid", 0.5, seq=1),
        record("pass", None, seq=2),
        record("fail", 0.5, seq=3),
        record("fail", 0.5, seq=4),
    ]
    assert surprise_curve(rows, window=2) == [None, 1.0]


def test_curve_rejects_a_bad_window() -> None:
    for window in (0, -1, True, 1.5):
        with pytest.raises(ValueError):
            surprise_curve([], window=window)


def test_teeth_require_a_rise_and_a_fall() -> None:
    assert teeth([0.0, 0.0, 1.0], amplitude=0.25, width=1) == []
    assert teeth([1.0, 0.0, 0.0], amplitude=0.25, width=1) == []
    assert teeth([0.0, 1.0, 0.5], amplitude=0.25, width=1) == [1]
    assert teeth([0.0, 1.0, 0.9], amplitude=0.25, width=1) == []
    assert teeth([0.5, 0.5, 0.5], amplitude=0.25, width=1) == []
    assert teeth([], amplitude=0.25, width=1) == []
    assert teeth([1.0], amplitude=0.25, width=5) == []
    assert teeth([0.0, 1.0], amplitude=0.25, width=5) == []
    assert teeth([1.0, 0.0], amplitude=0.25, width=5) == []


def test_teeth_amplitude_boundary_and_plateau() -> None:
    short = 0.25 - 1e-12
    assert teeth([0.0, short, 0.0], amplitude=0.25, width=1) == [1]
    assert teeth([0.0, math.nextafter(short, 0.0), 0.0], amplitude=0.25, width=1) == []
    assert teeth([0.0, 0.25, 0.0], amplitude=0.25, width=1) == [1]
    # Equal neighbours on the right: the leftmost index of the plateau is the tooth.
    assert teeth([0.0, 1.0, 1.0, 0.0], amplitude=0.25, width=2) == [1]
    assert teeth([0.0, 1.0, 0.0, 1.0, 0.0], amplitude=0.25, width=1) == [1, 3]


def test_teeth_ignore_none_and_values_outside_the_width() -> None:
    assert teeth([0.0, None, 1.0, None, 0.0], amplitude=0.25, width=2) == [2]
    assert teeth([0.0, None, 1.0, None, 0.0], amplitude=0.25, width=1) == []
    assert teeth([None, 1.0, None], amplitude=0.25, width=1) == []
    assert teeth([0.0, 1.0, 0.9, 0.9, 0.0], amplitude=0.25, width=1) == []
    assert teeth([0.0, 1.0, 0.9, 0.9, 0.0], amplitude=0.25, width=3) == [1]
    assert teeth([0.0, None, 1.0], amplitude=0.25, width=2) == []
