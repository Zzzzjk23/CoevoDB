"""Plugin protocol for the four roles that join the loop after S9.

A plugin module exposes ``build(ctx) -> Role``. This module does not import
those modules, and it does not import a model client.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from surprise.features.phi import Phi
from surprise.features.registry import Registry

from .conjecturer import ConjectureBook
from .gateway import Gateway

# Import path of each new role. A role that is off is never imported.
PLUGINS = {
    "prior": "surprise.roles.prior",
    "translator": "surprise.roles.translator",
    "vocab_inventor": "surprise.roles.vocab_inventor",
    "oracle_inventor": "surprise.roles.oracle_inventor",
}


@dataclass(frozen=True)
class RoleContext:
    """Everything a plugin may use, shared with the rest of the run."""

    gateway: Gateway
    book: ConjectureBook
    extract: Callable
    registry: Registry
    readers: dict
    engines: tuple[str, ...]
    oracles: tuple[str, ...]
    seed: int
    run_dir: Path
    llm_dir: Path


@dataclass(frozen=True)
class Observed:
    """One executed experiment, as the roles see it after the Diagnoser."""

    wb: Any
    phi: Phi
    record: Any
    outcome: Any
    prediction: Any
    lane: str
    op: str
    hypothesis: str | None
    target: dict | None
    index: int


class Role:
    """Base class with no-op defaults. A plugin module exposes ``build(ctx) -> Role``."""

    name: str = ""

    def sources(self) -> tuple:
        """Objects with ``candidates(wb, *, index, round)``. Empty by default."""
        return ()

    def observe(self, event: Observed) -> None:
        """See one executed experiment. The default does nothing."""

    def after(self, wb, record, outcome) -> None:
        """Run after ``observe`` and after the S9 conjecturer. The default does nothing."""

    def step(self) -> dict:
        """This step's summary. JSON-safe, with no timings."""
        return {}

    def report(self) -> dict:
        """Totals for the whole run."""
        return {}

    def manifest(self) -> dict:
        """The plugin's section of the run manifest."""
        return {}

    def close(self) -> None:
        """Release resources. The default does nothing."""
