"""Three-valued adapters for the sound oracles that ship in S2.

``judge`` screens a case, then asks the matching old oracle whether the two
forms differ. It does not catch exceptions from the runner or the old oracle.
"""

from __future__ import annotations

from typing import Any

from oracles.determinism import is_usable_for_oracles
from targets.duckdb_runner import DuckDBRunner

from surprise.harness.constants import QUERY_TIMEOUT_S
from surprise.harness.contracts import Label, SqlCase

from .common import RecordingRunner, invalid_label
from .forms import full_query
from .norec import judge_norec, norec_applies
from .plan_variant import judge_plan_variant
from .tlp import judge_tlp, tlp_form

IMPLEMENTED = ("tlp", "norec", "plan_variant")


def judge(case: SqlCase, oracle: str, *, runner_factory=None,
          timeout_s: float = QUERY_TIMEOUT_S) -> Label:
    """Label ``case`` with one sound oracle.

    The same input judged twice returns labels whose ``to_dict()`` are equal.
    ``runner_factory`` is called once for screening and, when the oracle runs,
    once more for the recorded execution. Each returned runner is closed.
    """
    if oracle not in IMPLEMENTED:
        raise ValueError(f"oracle: must be one of {IMPLEMENTED}, got {oracle!r}")
    if case.engine != "duckdb":
        raise ValueError(f"engine: only 'duckdb' is supported, got {case.engine!r}")

    full = full_query(case)
    factory = runner_factory if runner_factory is not None else DuckDBRunner

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
