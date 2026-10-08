"""Oracle dispatch: seven ids, two target engines, registered handlers.

``judge`` validates the request, screens later oracles for setup and
determinism, then calls the matching handler. Sound oracles keep the S2
setup-determinism-premise-adapter flow inside ``sound``.
"""

from __future__ import annotations

from oracles.determinism import is_usable_for_oracles

from surprise.harness.constants import QUERY_TIMEOUT_S
from surprise.harness.contracts import ORACLE_IDS, Label, SqlCase

from .common import invalid_label
from .forms import full_query
from .registry import (
    SOUND_ORACLE_IDS,
    get_handler,
    make_options,
    runner_factory_for,
    validate_request,
)

# Registers tlp, norec, and plan_variant. Later handlers load on demand.
from . import sound as _sound  # noqa: F401

IMPLEMENTED = ORACLE_IDS


def judge(
    case: SqlCase,
    oracle: str,
    *,
    runner_factory=None,
    timeout_s: float = QUERY_TIMEOUT_S,
    rewrite_rule: str | None = None,
    paired_query: str | None = None,
    old_python: str | None = None,
    reference_factories=None,
) -> Label:
    """Label ``case`` with one of the seven oracles.

    Unknown oracles, unsupported target engines, and illegal options raise
    before any runner opens. The same accepted input judged twice returns
    labels whose ``to_dict()`` are equal. Exceptions from a runner or handler
    propagate; ``evaluate`` records those as ``harness_error``.
    """
    options = make_options(
        rewrite_rule=rewrite_rule,
        paired_query=paired_query,
        old_python=old_python,
        reference_factories=reference_factories,
    )
    validate_request(case, oracle, options)
    factory = runner_factory if runner_factory is not None else runner_factory_for(case.engine)

    if oracle in SOUND_ORACLE_IDS:
        return get_handler(oracle)(
            case, factory=factory, timeout_s=timeout_s, options=options
        )

    early = _public_screen(case, oracle, factory)
    if early is not None:
        return early
    return get_handler(oracle)(
        case, factory=factory, timeout_s=timeout_s, options=options
    )


def _public_screen(case: SqlCase, oracle: str, factory) -> Label | None:
    """Setup and determinism for later oracles. Does not load their modules."""
    full = full_query(case)
    screen = factory()
    try:
        outcomes = screen.setup(list(case.setup))
        for _statement, error in outcomes:
            if error is not None:
                return invalid_label(oracle, "setup_error", full, error=error)
        if not is_usable_for_oracles(full, screen, list(case.setup)):
            return invalid_label(oracle, "nondeterministic", full)
    finally:
        screen.close()
    return None
