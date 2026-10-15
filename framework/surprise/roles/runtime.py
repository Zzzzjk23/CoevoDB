"""Role set for one run: the conjecturer, the implementer, and the Hunter's source.

``s09-wire`` calls :func:`build_roles` and then ``observe``, ``after``, ``step``,
``manifest``, ``report``, and ``close``. This module does not import a transport
until ``build_roles`` is asked for the network.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from surprise.features.vocabulary import layer_of
from surprise.theory.contracts import Spec
from surprise.theory.vspace import reduce_conjunction

from . import constants
from .conjecturer import ConjectureBook, Conjecturer
from .constants import IMPLEMENTER_PER_CHOICE, TIERS
from .gateway import Gateway
from .implementer import Implementer
from .source import SourceError, open_sources

_CALL_STATUSES = ("ok", "rejected", "blocked", "miss", "error")
_ROLES = ("implementer", "conjecturer")


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

    def candidates(self, wb: Any, *, index: int, round: int) -> list:
        """At most ``per_choice`` new specs on the first round of this index.

        A later round does not mark the index. An index already served returns
        nothing. Specs already implemented are skipped and do not count.
        """
        if round > 1:
            return []
        if index in self._served:
            return []
        self._served.add(index)
        from surprise.hunter.hunter import Candidate
        from surprise.hunter.operators import oracle_options

        produced: list[Any] = []
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
            produced.append(
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
        return produced

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
    ) -> None:
        self._roles = list(roles)
        self._gateway = gateway
        self._book = book
        self._implementer = implementer
        self._conjecturer = conjecturer
        self._seed = seed
        self._network = network
        self._readers = readers
        llm = Path(run_dir) / "llm"
        llm.mkdir(parents=True, exist_ok=True)
        self._impl_handle = (llm / "implementer.jsonl").open("a", encoding="utf-8")
        self._attempt_count = 0
        self._attempt_ok = 0
        self._attempt_first = 0
        self._by_status: dict[str, int] = {}
        self._calls_snap: dict[str, dict[str, int]] = {}
        self._step_conjecture: Any = None
        self._step_settled: list[list[Any]] = []
        self._step_attempts: list[str] = []
        if implementer is None:
            self.sources: tuple[Any, ...] = ()
        else:
            self.sources = (
                ImplementerSource(
                    implementer,
                    book,
                    engines=engines,
                    registry=implementer.registry,
                    on_attempt=self._note_attempt,
                ),
            )

    def observe(self, phi: Any, label: Any, record_id: str) -> tuple:
        """Settle the book. Returns the predictions this experiment settled."""
        settled = self._book.observe(phi, label, record_id)
        for item in settled:
            self._step_settled.append([item.conjecture_id, item.index, item.state])
        return settled

    def after(self, wb: Any, record: Any, outcome: Any) -> Any:
        """The conjecturer, when it is on. ``None`` when it is off or nothing opened."""
        if self._conjecturer is None:
            return None
        conjecture = self._conjecturer.after(wb, record, outcome)
        if conjecture is not None:
            self._step_conjecture = conjecture
        return conjecture

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
        return {
            "roles": list(self._roles),
            "tiers": dict(TIERS),
            "max_calls": self._gateway.max_calls,
            "network": self._network,
            "seed": self._seed,
            "constants": constants.as_dict(),
            "sources": sources,
        }

    def report(self) -> dict[str, Any]:
        """Totals for the whole run, not just the last step."""
        return {
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

    def close(self) -> None:
        """Close the implementer log. The book flushes on every write."""
        handle = self._impl_handle
        if handle is not None and not handle.closed:
            handle.flush()
            handle.close()

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
) -> RoleSet:
    """One ``RoleSet`` for ``config``. The transport is built only when the network is on."""
    chosen: list[str] = []
    seen: set[str] = set()
    for role in config["roles"]:
        if role not in _ROLES:
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
    )
    return roleset
