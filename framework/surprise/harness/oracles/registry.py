"""Shared oracle handler registry, runner mapping, and option validation.

Handlers for the four later oracles are imported on first lookup so those
packages can register themselves without editing this package's ``__init__``.
A missing implementation module raises; it is never treated as a pass.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Callable

from surprise.harness.contracts import ORACLE_IDS, Label, SqlCase

TARGET_ENGINES = ("duckdb", "datafusion", "postgres")
REFERENCE_ENGINES = ("duckdb", "datafusion", "sqlite", "postgres")
SOUND_ORACLE_IDS = ("tlp", "norec", "plan_variant")

# Modules that call ``register`` on import. Sound handlers live in ``sound``
# and are imported by this package; the four later ones load on demand.
_LAZY_MODULES = {
    "tlp": "surprise.harness.oracles.sound",
    "norec": "surprise.harness.oracles.sound",
    "plan_variant": "surprise.harness.oracles.sound",
    "index_presence": "surprise.harness.oracles.index_presence",
    "equivalent_query": "surprise.harness.oracles.equivalent_query",
    "cross_dbms": "surprise.harness.oracles.cross_dbms",
    "version_differential": "surprise.harness.oracles.version_differential",
}

Handler = Callable[..., Label]
_HANDLERS: dict[str, Handler] = {}


@dataclass(frozen=True)
class OracleOptions:
    """Optional arguments shared by every registered handler.

    ``reference_factories`` is ``None`` for the default reference set and an
    empty dict for no references. Keys, when present, are independent engine
    ids; the target and version aliases are rejected before any handler runs.
    """

    rewrite_rule: str | None = None
    paired_query: str | None = None
    old_python: str | None = None
    reference_factories: dict[str, Any] | None = None


def register(oracle_id: str, handler: Handler) -> None:
    """Record ``handler`` for ``oracle_id``. Already-registered ids are rejected."""
    if oracle_id not in ORACLE_IDS:
        raise ValueError(f"oracle: must be one of {ORACLE_IDS}, got {oracle_id!r}")
    if not callable(handler):
        raise ValueError(f"handler: must be callable, got {handler!r}")
    if oracle_id in _HANDLERS:
        raise ValueError(f"register: handler already registered for {oracle_id!r}")
    _HANDLERS[oracle_id] = handler


def get_handler(oracle_id: str) -> Handler:
    """Return the handler for ``oracle_id``, importing its module if needed.

    Unknown ids raise ``ValueError``. A missing later module raises
    ``ImportError``; this function does not invent a pass label.
    """
    if oracle_id not in ORACLE_IDS:
        raise ValueError(f"oracle: must be one of {ORACLE_IDS}, got {oracle_id!r}")
    handler = _HANDLERS.get(oracle_id)
    if handler is not None:
        return handler
    module_name = _LAZY_MODULES[oracle_id]
    importlib.import_module(module_name)
    handler = _HANDLERS.get(oracle_id)
    if handler is None:
        raise RuntimeError(f"{module_name} did not register {oracle_id!r}")
    return handler


def runner_factory_for(engine: str):
    """Default runner factory for a target engine. Unknown targets raise."""
    if engine == "duckdb":
        from targets.duckdb_runner import DuckDBRunner

        return DuckDBRunner
    if engine == "datafusion":
        from targets.datafusion_runner import DataFusionRunner

        return DataFusionRunner
    if engine == "postgres":
        from surprise.harness.oracles.pg_target import PostgresTargetRunner

        return PostgresTargetRunner
    raise ValueError(
        f"engine: only {TARGET_ENGINES} are supported as targets, got {engine!r}"
    )


def make_options(
    *,
    rewrite_rule: str | None = None,
    paired_query: str | None = None,
    old_python: str | None = None,
    reference_factories: dict[str, Any] | None = None,
) -> OracleOptions:
    """Build options, copying ``reference_factories`` so callers keep their dict."""
    if reference_factories is not None and not isinstance(reference_factories, dict):
        raise ValueError(
            f"reference_factories: expected a dict or None, got {reference_factories!r}"
        )
    copied = None if reference_factories is None else dict(reference_factories)
    return OracleOptions(
        rewrite_rule=rewrite_rule,
        paired_query=paired_query,
        old_python=old_python,
        reference_factories=copied,
    )


def validate_options(options: OracleOptions, *, target_engine: str) -> None:
    """Reject option values that later handlers must not see."""
    for name in ("rewrite_rule", "paired_query", "old_python"):
        value = getattr(options, name)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{name}: must be a string or None, got {value!r}")
    refs = options.reference_factories
    if refs is None:
        return
    if not isinstance(refs, dict):
        raise ValueError(f"reference_factories: expected a dict or None, got {refs!r}")
    for engine_id, factory in refs.items():
        if engine_id not in REFERENCE_ENGINES:
            raise ValueError(
                f"reference_factories: engine ids must be one of {REFERENCE_ENGINES}, "
                f"got {engine_id!r}"
            )
        if engine_id == target_engine:
            raise ValueError(
                f"reference_factories: target engine {target_engine!r} "
                "cannot appear as a reference"
            )
        if not callable(factory):
            raise ValueError(
                f"reference_factories: factory for {engine_id!r} must be callable, "
                f"got {factory!r}"
            )


def validate_request(case: SqlCase, oracle: str, options: OracleOptions) -> None:
    """Raise ``ValueError`` for an unknown oracle, unsupported target, or bad options."""
    if oracle not in ORACLE_IDS:
        raise ValueError(f"oracle: must be one of {ORACLE_IDS}, got {oracle!r}")
    if case.engine not in TARGET_ENGINES:
        raise ValueError(
            f"engine: only {TARGET_ENGINES} are supported as targets, got {case.engine!r}"
        )
    validate_options(options, target_engine=case.engine)
