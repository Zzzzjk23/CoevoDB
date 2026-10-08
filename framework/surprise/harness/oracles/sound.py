"""Registered handlers for TLP, NoREC, and plan variant.

Each handler keeps the S2 flow: setup, determinism, the oracle premise, then
the existing adapter. This module only calls those adapters; it does not
reimplement comparison.
"""

from __future__ import annotations

from typing import Any

from oracles.determinism import is_usable_for_oracles

from surprise.harness.contracts import Label, SqlCase

from .common import RecordingRunner, invalid_label
from .forms import full_query
from .norec import judge_norec, norec_applies
from .plan_variant import judge_plan_variant
from .registry import OracleOptions, register
from .tlp import judge_tlp, tlp_form


def judge_tlp_case(
    case: SqlCase, *, factory, timeout_s: float, options: OracleOptions
) -> Label:
    return _judge_sound(case, "tlp", factory, timeout_s)


def judge_norec_case(
    case: SqlCase, *, factory, timeout_s: float, options: OracleOptions
) -> Label:
    return _judge_sound(case, "norec", factory, timeout_s)


def judge_plan_variant_case(
    case: SqlCase, *, factory, timeout_s: float, options: OracleOptions
) -> Label:
    return _judge_sound(case, "plan_variant", factory, timeout_s)


def _judge_sound(case: SqlCase, oracle: str, factory, timeout_s: float) -> Label:
    """Setup, determinism, premise, then the matching old adapter.

    ``factory`` is called once for screening and, when the oracle runs, once
    more for the recorded execution. Each returned runner is closed.
    """
    full = full_query(case)
    screen = factory()
    try:
        early = _screen(case, oracle, screen, full)
    finally:
        screen.close()
    if early is not None:
        return early

    runner = factory()
    try:
        runner.setup(list(case.setup))
        recorded = RecordingRunner(runner)
        return _dispatch(case, oracle, recorded, timeout_s, full)
    finally:
        runner.close()


def _screen(case: SqlCase, oracle: str, runner: Any, full: str) -> Label | None:
    """Setup, determinism, and the oracle premise. Does not call ``check``."""
    outcomes = runner.setup(list(case.setup))
    for _statement, error in outcomes:
        if error is not None:
            return invalid_label(oracle, "setup_error", full, error=error)
    if not is_usable_for_oracles(full, runner, list(case.setup)):
        return invalid_label(oracle, "nondeterministic", full)
    if not _applies(case, oracle):
        return invalid_label(oracle, "not_applicable", full)
    return None


def _applies(case: SqlCase, oracle: str) -> bool:
    if oracle == "tlp":
        return tlp_form(case) is not None
    if oracle == "norec":
        return norec_applies(case)
    return True


def _dispatch(
    case: SqlCase,
    oracle: str,
    recorded: RecordingRunner,
    timeout_s: float,
    full: str,
) -> Label:
    if oracle == "tlp":
        form = tlp_form(case)
        if form is None:
            raise RuntimeError("tlp premise failed after screening accepted it")
        return judge_tlp(case, recorded, timeout_s, full, form)
    if oracle == "norec":
        return judge_norec(case, recorded, timeout_s, full)
    return judge_plan_variant(case, recorded, timeout_s, full)


register("tlp", judge_tlp_case)
register("norec", judge_norec_case)
register("plan_variant", judge_plan_variant_case)
