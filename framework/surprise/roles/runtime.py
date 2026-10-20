"""Role set for one run: the conjecturer, the implementer, and the Hunter's source.

``s09-wire`` calls :func:`build_roles` and then ``observe``, ``after``, ``step``,
``manifest``, ``report``, and ``close``. This module does not import a transport
until ``build_roles`` is asked for the network.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

from surprise.features.registry import default_registry
from surprise.features.vocabulary import layer_of
from surprise.theory.contracts import Spec
from surprise.theory.vspace import reduce_conjunction

from . import constants
from .base import PLUGINS, RoleContext
from .conjecturer import ConjectureBook, Conjecturer
from .constants import IMPLEMENTER_PER_CHOICE, TIERS
from .gateway import UNLIMITED, Gateway
from .implementer import Implementer
from .providers import endpoint_for_tier
from .source import SourceError, open_sources

_CALL_STATUSES = ("ok", "rejected", "blocked", "miss", "error")
ROLES = ("implementer", "conjecturer", "prior", "translator", "vocab_inventor", "oracle_inventor")


def _spec_key(spec: dict) -> str:
    """Identity of a spec: ``Spec.to_dict()`` with key order ignored and list order kept."""
    canonical = Spec.from_dict(spec).to_dict()
    return json.dumps(canonical, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


class ImplementerSource:
    """Turns open bets, then boundary specs, into implementer candidates."""

    def __init__(
        self,
        implementer: Implementer,
        book: ConjectureBook,
        *,
        engines: Any,
        per_choice: int | None = None,
        registry: Any = None,
        on_attempt: Any = None,
    ) -> None:
        self.implementer = implementer
        self.book = book
        self._engines = frozenset(engines)
        self._per_choice = IMPLEMENTER_PER_CHOICE if per_choice is None else per_choice
        self._registry = registry
        self._on_attempt = on_attempt
        self._done: set[str] = set()
        self._served: set[int] = set()
        self._ok: list[Any] = []

    def candidates(self, wb: Any, *, index: int, round: int) -> list:
        """Every ok attempt so far, in attempt order, on every call.

        A new spec is implemented only on round 1 of an index that has not been
        served, and at most ``per_choice`` of them. A later round does not mark
        the index. The Hunter drops cases it has already run; this source does not.
        """
        if round <= 1 and index not in self._served:
            self._served.add(index)
            self._implement_new(wb, index)
        return list(self._ok)

    def _implement_new(self, wb: Any, index: int) -> None:
        from surprise.hunter.hunter import Candidate
        from surprise.hunter.operators import oracle_options

        made = 0
        for item in self._queue(wb):
            if made >= self._per_choice:
                break
            spec = item["spec"]
            key = _spec_key(spec)
            if key in self._done:
                continue
            attempt = self.implementer.implement(spec)
            self._done.add(key)
            made += 1
            if self._on_attempt is not None:
                self._on_attempt(attempt, item["lane"], index)
            if not attempt.ok or attempt.case is None:
                continue
            oracle = spec["oracle"]
            rule = None
            if oracle == "equivalent_query":
                options = oracle_options(attempt.case, [oracle])
                if not options:
                    continue
                rule = options[0][1]
            self._ok.append(
                Candidate(
                    case=attempt.case,
                    oracle=oracle,
                    rule=rule,
                    lane=item["lane"],
                    hypothesis_id=item["hypothesis_id"],
                    parent=None,
                    op="implementer",
                    target=attempt.spec,
                )
            )

    def _queue(self, wb: Any) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        owners = {
            row.get("conjecture_id"): row.get("hypothesis_id") for row in self.book.conjectures()
        }
        for pending in self.book.pending(state="open"):
            spec = pending.spec
            if spec.get("engine") not in self._engines:
                continue
            items.append(
                {
                    "spec": spec,
                    "lane": "bet",
                    "hypothesis_id": owners.get(pending.conjecture_id),
                }
            )
        for hypothesis in wb.theory.hypotheses:
            if hypothesis.engine not in self._engines or hypothesis.oracle is None:
                continue
            literals = tuple(
                sorted(
                    feature_id
                    for feature_id in hypothesis.specific
                    if layer_of(feature_id) in ("ast", "data")
                )
            )
            for literal in literals:
                others = tuple(feature_id for feature_id in literals if feature_id != literal)
                required = reduce_conjunction(others, self._registry)
                if not required:
                    continue
                spec = Spec(
                    engine=hypothesis.engine,
                    oracle=hypothesis.oracle,
                    required=required,
                    forbidden=(literal,),
                ).to_dict()
                items.append(
                    {
                        "spec": spec,
                        "lane": "implement",
                        "hypothesis_id": hypothesis.hypothesis_id,
                    }
                )
        return items


class RoleSet:
    """One gateway, one conjecture book, and the roles switched on for this run."""

    def __init__(
        self,
        *,
        roles: list[str],
        gateway: Gateway,
        book: ConjectureBook,
        implementer: Implementer | None,
        conjecturer: Conjecturer | None,
        seed: int,
        network: bool,
        readers: dict[str, Any],
        engines: Any,
        run_dir: Path | str,
        plugins: dict[str, Any] | None = None,
    ) -> None:
        self._roles = list(roles)
        self._gateway = gateway
        self._book = book
        self._implementer = implementer
        self._conjecturer = conjecturer
        self._seed = seed
        self._network = network
        self._readers = readers
        self.plugins = {} if plugins is None else dict(plugins)
        self.prior = self.plugins.get("prior")
        llm = Path(run_dir) / "llm"
        llm.mkdir(parents=True, exist_ok=True)
        self.rewrite_library = (llm / "rewrites.json") if "oracle_inventor" in self.plugins else None
        self._impl_handle = (llm / "implementer.jsonl").open("a", encoding="utf-8")
        self._attempt_count = 0
        self._attempt_ok = 0
        self._attempt_first = 0
        self._by_status: dict[str, int] = {}
        self._calls_snap: dict[str, dict[str, int]] = {}
        self._step_conjecture: Any = None
        self._step_settled: list[list[Any]] = []
        self._step_attempts: list[str] = []
        found: list[Any] = []
        if implementer is not None:
            found.append(
                ImplementerSource(
                    implementer,
                    book,
                    engines=engines,
                    registry=implementer.registry,
                    on_attempt=self._note_attempt,
                )
            )
        for role in self.plugins.values():
            found.extend(role.sources())
        self.sources = tuple(found)

    def observe(self, phi: Any, label: Any, record_id: str, *, event: Any = None) -> tuple:
        """Settle the book, then tell each plugin. Returns the settled predictions."""
        settled = self._book.observe(phi, label, record_id)
        for item in settled:
            self._step_settled.append([item.conjecture_id, item.index, item.state])
        if event is not None:
            for role in self.plugins.values():
                role.observe(event)
        return settled

    def after(self, wb: Any, record: Any, outcome: Any) -> Any:
        """The conjecturer, when it is on, then each plugin.

        The return value is the conjecturer's, or ``None`` when it is off or
        nothing opened. Plugin return values are ignored.
        """
        if self._conjecturer is None:
            conjecture = None
        else:
            conjecture = self._conjecturer.after(wb, record, outcome)
            if conjecture is not None:
                self._step_conjecture = conjecture
        for role in self.plugins.values():
            role.after(wb, record, outcome)
        return conjecture

    def rewrite_rules(self) -> tuple:
        """Rule ids the oracle inventor has accepted. Empty when that role is off."""
        role = self.plugins.get("oracle_inventor")
        if role is None:
            return ()
        return tuple(role.rules())

    def step(self) -> dict[str, Any]:
        """What the roles did since the previous step, then clear that window.

        No source, elapsed time, or token counts: those change on replay.
        """
        current = self._status_snapshot()
        calls: dict[str, dict[str, int]] = {}
        for role, stats in current.items():
            previous = self._calls_snap.get(role, {})
            delta: dict[str, int] = {}
            for name in _CALL_STATUSES:
                count = stats[name] - previous.get(name, 0)
                if count > 0:
                    delta[name] = count
            if delta:
                calls[role] = delta
        conjecture = None
        if self._step_conjecture is not None:
            conjecture = [self._step_conjecture.conjecture_id, self._step_conjecture.status]
        result = {
            "calls": calls,
            "conjecture": conjecture,
            "settled": [list(item) for item in self._step_settled],
            "attempts": list(self._step_attempts),
        }
        for name, role in self.plugins.items():
            result[name] = role.step()
        self._calls_snap = current
        self._step_conjecture = None
        self._step_settled = []
        self._step_attempts = []
        return result

    def manifest(self) -> dict[str, Any]:
        """The run manifest's ``llm`` section, without timings."""
        sources: dict[str, dict[str, Any]] = {}
        for engine, reader in self._readers.items():
            root = getattr(reader, "root", None)
            commit = getattr(reader, "commit", None)
            sources[engine] = {
                "dir": "" if root is None else root.name,
                "commit": commit or None,
            }
        cap = self._gateway.max_calls
        result = {
            "roles": list(self._roles),
            "tiers": dict(TIERS),
            "max_calls": UNLIMITED if cap is None else cap,
            "network": self._network,
            "seed": self._seed,
            "constants": constants.as_dict(),
            "sources": sources,
        }
        if self._gateway.tier is not None:
            result["tier"] = self._gateway.tier
            endpoint = endpoint_for_tier(self._gateway.tier)
            if endpoint is not None:
                result["endpoint"] = endpoint
        if self.plugins:
            result["plugins"] = {name: role.manifest() for name, role in self.plugins.items()}
        return result

    def report(self) -> dict[str, Any]:
        """Totals for the whole run, not just the last step."""
        result = {
            "roles": list(self._roles),
            "calls": self._gateway.totals(),
            "book": self._book.summary(),
            "implementer": {
                "attempts": self._attempt_count,
                "ok": self._attempt_ok,
                "first_ok": self._attempt_first,
                "by_status": dict(self._by_status),
            },
        }
        for name, role in self.plugins.items():
            result[name] = role.report()
        return result

    def close(self) -> None:
        """Close the implementer log, then each plugin. The first error is re-raised."""
        first: Exception | None = None
        handle = self._impl_handle
        if handle is not None and not handle.closed:
            try:
                handle.flush()
                handle.close()
            except Exception as exc:
                first = exc
        for role in self.plugins.values():
            try:
                role.close()
            except Exception as exc:
                if first is None:
                    first = exc
        if first is not None:
            raise first

    def _note_attempt(self, attempt: Any, lane: str, index: int) -> None:
        row = attempt.to_dict()
        row["lane"] = lane
        row["index"] = index
        self._impl_handle.write(json.dumps(row, ensure_ascii=True) + "\n")
        self._impl_handle.flush()
        self._attempt_count += 1
        self._attempt_ok += int(attempt.ok)
        self._attempt_first += int(attempt.first_ok)
        self._by_status[attempt.status] = self._by_status.get(attempt.status, 0) + 1
        self._step_attempts.append(attempt.status)

    def _status_snapshot(self) -> dict[str, dict[str, int]]:
        snap: dict[str, dict[str, int]] = {}
        for role, stats in self._gateway.totals()["by_role"].items():
            snap[role] = {name: int(stats.get(name, 0)) for name in _CALL_STATUSES}
        return snap


def build_roles(
    config: dict,
    *,
    run_dir: Path | str,
    extract: Any,
    registry: Any,
    engines: Any,
    seed: int,
    oracles: Any = (),
) -> RoleSet:
    """One ``RoleSet`` for ``config``. The transport is built only when the network is on.

    A new role's module is imported only when that role is on. A missing module
    raises ``ValueError``; it is not treated as "off".
    """
    chosen: list[str] = []
    seen: set[str] = set()
    for role in config["roles"]:
        if role not in ROLES:
            raise ValueError(f"unknown role: {role!r}")
        if role in seen:
            continue
        seen.add(role)
        chosen.append(role)
    if not chosen:
        raise ValueError("roles must be a non-empty subset of 'implementer' and 'conjecturer'")
    if "transport" in config:
        transport = config["transport"]
    elif config["network"]:
        from .transport import DeepSeekTransport

        transport = DeepSeekTransport()
    else:
        transport = None
    root = Path(run_dir)
    llm = root / "llm"
    llm.mkdir(parents=True, exist_ok=True)
    gateway = Gateway(
        cache_dir=config["cache"],
        ledger_path=llm / "calls.jsonl",
        max_calls=config["max_calls"],
        transport=transport,
        tier=config.get("tier"),
    )
    book = ConjectureBook(llm / "conjectures.jsonl")
    try:
        readers = open_sources()
    except SourceError:
        readers = {}
    implementer = None
    conjecturer = None
    if "implementer" in chosen:
        implementer = Implementer(
            gateway=gateway, extract=extract, registry=registry, seed=seed
        )
    if "conjecturer" in chosen:
        conjecturer = Conjecturer(
            gateway=gateway,
            extract=extract,
            book=book,
            registry=registry,
            sources=readers,
            seed=seed,
        )
    active = registry if registry is not None else default_registry()
    ctx = RoleContext(
        gateway=gateway,
        book=book,
        extract=extract,
        registry=active,
        readers=readers,
        engines=tuple(engines),
        oracles=tuple(oracles),
        seed=int(seed),
        run_dir=root,
        llm_dir=llm,
    )
    plugins = _load_plugins(chosen, ctx)
    roleset = RoleSet(
        roles=chosen,
        gateway=gateway,
        book=book,
        implementer=implementer,
        conjecturer=conjecturer,
        seed=seed,
        network=bool(config["network"]),
        readers=readers,
        engines=engines,
        run_dir=root,
        plugins=plugins,
    )
    return roleset


def _load_plugins(chosen: list[str], ctx: RoleContext) -> dict[str, Any]:
    """Import and build each new role that is on, in ``ROLES`` order.

    A module that is not on is not imported. A module that is on but missing
    raises ``ValueError``.
    """
    selected = set(chosen)
    plugins: dict[str, Any] = {}
    built: list[Any] = []
    try:
        for name in ROLES:
            if name not in PLUGINS or name not in selected:
                continue
            module_name = PLUGINS[name]
            try:
                module = importlib.import_module(module_name)
            except ImportError as exc:
                raise ValueError(f"role {name!r} is not available: {exc}") from exc
            build = getattr(module, "build", None)
            if not callable(build):
                raise ValueError(f"role {name!r} is not available: {module_name} has no build(ctx)")
            role = build(ctx)
            built.append(role)
            plugins[name] = role
    except Exception:
        for role in built:
            try:
                role.close()
            except Exception:
                pass
        raise
    return plugins
