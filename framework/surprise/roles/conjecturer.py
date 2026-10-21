"""Hypothesis conjecturer: mechanism, trigger, and falsifiable predictions.

The prompt is a pure function of the failure, the hypothesis wording, and the
source snippets. Record ids and hypothesis ids never enter it. The book keeps
every reply, including refusals, and settles predictions when an experiment hits.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from surprise.features.phi import Phi
from surprise.features.registry import Registry, default_registry
from surprise.features.vocabulary import layer_of
from surprise.harness.contracts import ORACLE_IDS
from surprise.theory.contracts import Spec
from surprise.theory.edits import Proposal, bet_matches
from surprise.theory.vspace import reduce_conjunction

from .constants import (
    CONJECTURER_MAX_PREDICTIONS,
    CONJECTURER_MAX_TOKENS,
    CONJECTURER_TEMPERATURE,
    CONJECTURER_TIER,
    SOURCE_MAX_FILES,
    SOURCE_MAX_LINES,
)
from .gateway import Gateway
from .source import Snippet, SourceError
from .sources_map import (
    DATAFUSION_SOURCE_RULES,
    DUCKDB_OPTIMIZER_FILES,
    POSTGRES_GUC_FILES,
    POSTGRES_SOURCE_RULES,
)

# Lines of context on each side of a DataFusion hit. Window and aggregate overlap; a
# set-operation hit a hundred lines later stays its own span unless the gap is one line.
_FEATURE_RADIUS = 45
_EXPECTATIONS = frozenset({"pass", "fail"})
_COPY_STATUSES = frozenset({"blocked", "miss", "error", "rejected"})


@dataclass(frozen=True)
class Conjecture:
    """One conjecturer reply, registered or refused, after it has a book id."""

    conjecture_id: str
    record_id: str
    hypothesis_id: str
    engine: str
    oracle: str
    status: str
    reason: str | None
    mechanism: str | None
    trigger: tuple[str, ...]
    predictions: tuple[dict, ...]
    dropped: tuple[dict, ...]
    edit_id: str | None
    accepted: bool | None
    edit_reason: str | None
    key: str | None
    sources: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "conjecture_id": self.conjecture_id,
            "record_id": self.record_id,
            "hypothesis_id": self.hypothesis_id,
            "engine": self.engine,
            "oracle": self.oracle,
            "status": self.status,
            "reason": self.reason,
            "mechanism": self.mechanism,
            "trigger": list(self.trigger),
            "predictions": [dict(item) for item in self.predictions],
            "dropped": [dict(item) for item in self.dropped],
            "edit_id": self.edit_id,
            "accepted": self.accepted,
            "edit_reason": self.edit_reason,
            "key": self.key,
            "sources": list(self.sources),
        }


@dataclass(frozen=True)
class Pending:
    """One prediction waiting for, or settled by, an experiment."""

    conjecture_id: str
    index: int
    spec: dict
    expect: str
    state: str
    record_id: str | None


class ConjectureBook:
    """Append-only JSONL of conjectures and the experiments that settled them."""

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = None if path is None else Path(path)
        self._rows: list[dict[str, Any]] = []
        self._pending: list[Pending] = []
        self._at: dict[tuple[str, int], int] = {}
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if not self._path.exists():
                self._path.write_text("", encoding="utf-8")
            self._replay()

    @property
    def path(self) -> Path | None:
        return self._path

    def next_id(self) -> str:
        """``c1``, ``c2``, ... from how many conjectures the book has received."""
        return f"c{len(self._rows) + 1}"

    def add(self, conjecture: Conjecture) -> None:
        """Remember every status. Only a registered conjecture opens experiments."""
        row = conjecture.to_dict()
        self._rows.append(row)
        if conjecture.status == "registered":
            self._open_predictions(conjecture.conjecture_id, conjecture.predictions)
        self._append({"type": "conjecture", **row})

    def conjectures(self) -> tuple[dict, ...]:
        """``to_dict()`` of every conjecture received, in order."""
        return tuple(json.loads(json.dumps(row)) for row in self._rows)

    def pending(self, state: str | None = "open") -> tuple[Pending, ...]:
        """Pending experiments. ``state=None`` returns every state, in book order."""
        if state is None:
            return tuple(self._pending)
        return tuple(item for item in self._pending if item.state == state)

    def observe(self, phi: Phi, label: Any, record_id: str) -> tuple[Pending, ...]:
        """Settle open predictions this experiment hits. Already settled ones stay."""
        settled: list[Pending] = []
        for item in self._pending:
            if item.state != "open":
                continue
            bet = {"spec": item.spec, "expect": item.expect}
            if not bet_matches(bet, phi, label):
                continue
            state = "kept" if label.y == item.expect else "broken"
            updated = dataclasses.replace(item, state=state, record_id=record_id)
            self._pending[self._at[(item.conjecture_id, item.index)]] = updated
            self._append(
                {
                    "type": "settle",
                    "conjecture_id": item.conjecture_id,
                    "index": item.index,
                    "state": state,
                    "record_id": record_id,
                }
            )
            settled.append(updated)
        return tuple(settled)

    def summary(self) -> dict[str, int]:
        """Registered count, every other status, and the prediction states."""
        registered = sum(1 for row in self._rows if row.get("status") == "registered")
        counts = {"open": 0, "kept": 0, "broken": 0}
        for item in self._pending:
            counts[item.state] = counts.get(item.state, 0) + 1
        return {
            "conjectures": registered,
            "rejected": len(self._rows) - registered,
            "predictions": len(self._pending),
            "open": counts["open"],
            "kept": counts["kept"],
            "broken": counts["broken"],
        }

    def _open_predictions(self, conjecture_id: str, predictions: tuple[dict, ...] | list) -> None:
        for index, pred in enumerate(predictions):
            pending = Pending(
                conjecture_id=conjecture_id,
                index=index,
                spec=dict(pred["spec"]),
                expect=pred["expect"],
                state="open",
                record_id=None,
            )
            self._at[(conjecture_id, index)] = len(self._pending)
            self._pending.append(pending)

    def _append(self, row: dict[str, Any]) -> None:
        if self._path is None:
            return
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")
            handle.flush()

    def _replay(self) -> None:
        text = self._path.read_text(encoding="utf-8") if self._path is not None else ""
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError("conjecture book line is not JSON") from exc
            if not isinstance(row, dict):
                raise ValueError("conjecture book line must be an object")
            kind = row.get("type")
            if kind == "conjecture":
                stored = {key: value for key, value in row.items() if key != "type"}
                self._rows.append(stored)
                if stored.get("status") == "registered":
                    self._open_predictions(stored["conjecture_id"], stored.get("predictions") or [])
            elif kind == "settle":
                self._apply_settle(row)
            else:
                raise ValueError(f"unknown conjecture book line: {kind!r}")

    def _apply_settle(self, row: dict[str, Any]) -> None:
        conjecture_id = row.get("conjecture_id")
        index = row.get("index")
        state = row.get("state")
        if not isinstance(conjecture_id, str) or isinstance(index, bool) or not isinstance(index, int):
            raise ValueError(f"settle line is missing conjecture_id or index: {row!r}")
        if state not in ("kept", "broken"):
            raise ValueError(f"settle state must be kept or broken, got {state!r}")
        place = self._at.get((conjecture_id, index))
        if place is None:
            raise ValueError(f"settle names an unknown prediction: {conjecture_id!r} {index!r}")
        current = self._pending[place]
        if current.state != "open":
            return
        record_id = row.get("record_id")
        if record_id is not None and not isinstance(record_id, str):
            raise ValueError(f"settle record_id must be a string or null, got {record_id!r}")
        self._pending[place] = dataclasses.replace(current, state=state, record_id=record_id)


def _feature_ids(phi: Any) -> tuple[str, ...]:
    if phi is None:
        return ()
    if isinstance(phi, dict):
        raw = phi.get("features") or ()
    else:
        raw = getattr(phi, "features", ()) or ()
    if isinstance(raw, str):
        return ()
    return tuple(item for item in raw if isinstance(item, str))


def _merge_spans(spans: list[tuple[str, int, int]]) -> list[tuple[str, int, int]]:
    """Same file, first-seen file order. Overlap, a shared edge, or a one-line gap merges."""
    groups: list[list[Any]] = []
    index: dict[str, int] = {}
    for path, start, end in spans:
        if path not in index:
            index[path] = len(groups)
            groups.append([path, []])
        groups[index[path]][1].append((start, end))
    merged: list[tuple[str, int, int]] = []
    for path, ranges in groups:
        ranges.sort()
        cur_start, cur_end = ranges[0]
        for start, end in ranges[1:]:
            if start <= cur_end + 2:
                cur_end = max(cur_end, end)
            else:
                merged.append((path, cur_start, cur_end))
                cur_start, cur_end = start, end
        merged.append((path, cur_start, cur_end))
    return merged


def _pack(reader: Any, spans: list[tuple[str, int, int]]) -> tuple[Snippet, ...]:
    """Keep the file cap and the line cap. The last snippet is shortened to fit."""
    chosen: list[Snippet] = []
    files: list[str] = []
    used = 0
    for path, start, end in spans:
        if path not in files and len(files) >= SOURCE_MAX_FILES:
            break
        room = SOURCE_MAX_LINES - used
        if room <= 0:
            break
        if end - start + 1 > room:
            end = start + room - 1
        try:
            snippet = reader.read(path, start, end)
        except SourceError:
            continue
        length = snippet.end - snippet.start + 1
        if length <= 0:
            continue
        if length > room:
            try:
                snippet = reader.read(path, snippet.start, snippet.start + room - 1)
            except SourceError:
                continue
            length = snippet.end - snippet.start + 1
        chosen.append(snippet)
        used += length
        if path not in files:
            files.append(path)
        if used >= SOURCE_MAX_LINES:
            break
    return tuple(chosen)


def _postgres_sources(reader: Any, interventions: tuple, phi: Any) -> tuple[Snippet, ...]:
    if interventions:
        wanted = set(interventions)
        paths: list[str] = []
        for name, candidates in POSTGRES_GUC_FILES.items():
            if name not in wanted:
                continue
            for path in candidates:
                try:
                    if path in paths or not reader.exists(path):
                        continue
                except SourceError:
                    continue
                paths.append(path)
        paths = paths[:SOURCE_MAX_FILES]
        if not paths:
            return ()
        head = SOURCE_MAX_LINES // len(paths)
        return _pack(reader, [(path, 1, head) for path in paths])
    features = _feature_ids(phi)
    cache: dict[tuple[str, str], tuple] = {}
    raw: list[tuple[str, int, int]] = []
    for prefix, regex, under in POSTGRES_SOURCE_RULES:
        if not any(feature_id.startswith(prefix) for feature_id in features):
            continue
        key = (regex, under)
        if key not in cache:
            try:
                cache[key] = tuple(reader.grep(regex, under=under, max_hits=1))
            except SourceError:
                cache[key] = ()
        hits = cache[key]
        if not hits:
            continue
        hit = hits[0]
        raw.append((hit.path, max(1, hit.line - _FEATURE_RADIUS), hit.line + _FEATURE_RADIUS))
    return _pack(reader, _merge_spans(raw))


def select_sources(engine: str, hypothesis: Any, phi: Any, readers: Any) -> tuple[Snippet, ...]:
    """Read-only snippets for one failure. A missing checkout yields an empty tuple.

    DuckDB with a fix set walks the optimizer map in enum order. The first
    ``SOURCE_MAX_FILES`` hits each contribute their share of the line budget,
    from line 1. DataFusion, and a DuckDB hypothesis with an empty fix set,
    walk the feature-prefix table. Unreadable paths are skipped.
    """
    if not readers or engine not in readers:
        return ()
    reader = readers[engine]
    interventions = tuple(getattr(hypothesis, "interventions", ()) or ())
    if engine == "postgres":
        return _postgres_sources(reader, interventions, phi)
    if engine == "duckdb" and interventions:
        wanted = set(interventions)
        paths: list[str] = []
        for name, path in DUCKDB_OPTIMIZER_FILES.items():
            if name not in wanted:
                continue
            try:
                if not reader.exists(path):
                    continue
            except SourceError:
                continue
            paths.append(path)
        paths = paths[:SOURCE_MAX_FILES]
        if not paths:
            return ()
        head = SOURCE_MAX_LINES // len(paths)
        return _pack(reader, [(path, 1, head) for path in paths])
    features = _feature_ids(phi)
    cache: dict[tuple[str, str], tuple] = {}
    raw: list[tuple[str, int, int]] = []
    for prefix, regex, under in DATAFUSION_SOURCE_RULES:
        if not any(feature_id.startswith(prefix) for feature_id in features):
            continue
        key = (regex, under)
        if key not in cache:
            try:
                cache[key] = tuple(reader.grep(regex, under=under, max_hits=1))
            except SourceError:
                cache[key] = ()
        hits = cache[key]
        if not hits:
            continue
        hit = hits[0]
        raw.append((hit.path, max(1, hit.line - _FEATURE_RADIUS), hit.line + _FEATURE_RADIUS))
    return _pack(reader, _merge_spans(raw))


def _active(registry: Registry | None) -> Registry:
    return default_registry() if registry is None else registry


def _reduced_features(phi: Any, registry: Registry | None) -> tuple[str, ...]:
    if isinstance(phi, dict):
        raw = Phi.from_dict(phi).features
    else:
        raw = _feature_ids(phi)
    if not raw:
        return ()
    return reduce_conjunction(raw, registry)


def _vocab_ids(registry: Registry, feature_ids: tuple[str, ...]) -> tuple[str, ...]:
    """Leaves that appear, plus sibling leaves, so a prediction can vary one condition."""
    chosen: set[str] = set()
    for feature_id in feature_ids:
        if not registry.known(feature_id):
            continue
        definition = registry.get(feature_id)
        if definition.kind == "leaf":
            chosen.add(feature_id)
        for sibling in registry.siblings(feature_id):
            chosen.add(sibling)
    return tuple(sorted(chosen))


def _minimized_case(label: Any) -> tuple[list, str] | None:
    cve = getattr(label, "cve", None)
    if not isinstance(cve, dict):
        return None
    minimize = cve.get("minimize")
    if (
        not isinstance(minimize, dict)
        or minimize.get("status") != "ran"
        or minimize.get("reproduced") is not True
    ):
        return None
    case = minimize.get("case")
    if not isinstance(case, dict):
        return None
    setup = case.get("setup")
    query = case.get("query")
    if not isinstance(setup, list) or not isinstance(query, str) or query == "":
        return None
    return setup, query


def conjecturer_prompt(
    *,
    engine: str,
    oracle: str,
    label: Any,
    case: Any,
    minimized: Any,
    phi: Any,
    hypothesis: Any,
    snippets: tuple[Snippet, ...] | list[Snippet],
    registry: Registry | None = None,
) -> str:
    """The conjecturer's prompt. Ids of records and hypotheses are not inputs."""
    words = _active(registry)
    features = _reduced_features(phi, registry)
    identity = getattr(label, "identity", None)
    error_class = getattr(identity, "error_class", None)
    behavior = getattr(identity, "behavior", {}) or {}
    if not isinstance(behavior, dict):
        behavior = {"value": str(behavior)}
    switches = list(getattr(identity, "switches", ()) or ())
    lines = [
        "You explain one database bug and propose experiments that could falsify the explanation.",
        "Reply with one JSON object and no other text. Do not wrap it in markdown.",
        f"Target engine: {engine}",
        f"Target oracle: {oracle}",
        "Failure kind: " + json.dumps(getattr(label, "fail_kind", None), ensure_ascii=True),
        "Error class: " + json.dumps(error_class, ensure_ascii=True),
        "Behavior: " + json.dumps(behavior, sort_keys=True, ensure_ascii=True, default=str),
        "Switches: " + json.dumps(switches, ensure_ascii=True),
        "Executed setup:",
    ]
    setup = tuple(getattr(case, "setup", ()) or ())
    if setup:
        lines.extend(str(statement) for statement in setup)
    else:
        lines.append("(none)")
    lines.append("Executed query:")
    lines.append(str(getattr(case, "query", "")))
    predicate = getattr(case, "predicate", None)
    if predicate is not None:
        lines.append("Executed predicate:")
        lines.append(str(predicate))
    if minimized is not None:
        lines.append("Minimised setup:")
        min_setup, min_query = minimized
        if min_setup:
            lines.extend(str(statement) for statement in min_setup)
        else:
            lines.append("(none)")
        lines.append("Minimised query:")
        lines.append(str(min_query))
    lines.extend(
        [
            "Fix set: " + json.dumps(list(getattr(hypothesis, "interventions", ()) or ()), ensure_ascii=True),
            "Plan delta: " + json.dumps(list(getattr(hypothesis, "plan_delta", ()) or ()), ensure_ascii=True),
            "Versions: "
            + json.dumps(
                getattr(hypothesis, "versions", {}) or {},
                sort_keys=True,
                ensure_ascii=True,
                default=str,
            ),
            "Failure features (the reduced conjunction of the failing statement):",
        ]
    )
    if features:
        lines.extend(f"- {feature_id}" for feature_id in features)
    else:
        lines.append("- (none)")
    lines.append("Source snippets:")
    if snippets:
        for snippet in snippets:
            lines.append(f"--- {engine}:{snippet.path} lines {snippet.start}-{snippet.end} ---")
            lines.append(snippet.text)
    else:
        lines.append("(none)")
    lines.append("Feature ids you may use, with their meanings:")
    vocab = _vocab_ids(words, features)
    if vocab:
        for feature_id in vocab:
            lines.append(f"- {feature_id}: {words.get(feature_id).description}")
    else:
        lines.append("- (none)")
    lines.extend(
        [
            "JSON shape:",
            '{"mechanism": "why the engine is wrong", "trigger": ["feature_id"], '
            '"prediction": [{"required": ["feature_id"], "forbidden": [], "data_properties": [], '
            '"expect": "fail", "why": "what this experiment shows"}]}',
            "mechanism is one sentence. Name the operator or function in the snippets when you have them.",
            "Write the JSON object first. Do not analyse at length before the JSON.",
            "trigger is the conjunction of feature ids required to hit the bug. Every id must be one of the failure features above. Use at least one.",
            "prediction is a non-empty list of experiments that have not been run. Each one is a spec plus the label you expect.",
            "Put feature ids in required and forbidden. Leave data_properties as an empty list.",
            "required holds the features the statement must have. forbidden holds features it must not have.",
            f"Write at most {CONJECTURER_MAX_PREDICTIONS} predictions.",
            'Include one prediction with expect "fail" (a nearby statement that should still be wrong) and one with expect "pass" (the same statement with one condition removed, which should be right).',
            "oracle is optional. Omit it to use the target oracle above. expect is \"pass\" or \"fail\". why is one sentence.",
            "Use only feature ids from the list above. Do not invent ids.",
        ]
    )
    return "\n".join(lines)


def _string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _prediction_problem(item: Any, registry: Registry, default_oracle: str | None) -> str | None:
    """Why this prediction is dropped. None when it can be kept."""
    if not isinstance(item, dict):
        return "not_object"
    if item.get("expect") not in _EXPECTATIONS:
        return "bad_expect"
    if any(not _string_list(item.get(name)) for name in ("required", "forbidden", "data_properties")):
        return "bad_lists"
    for name in ("required", "forbidden", "data_properties"):
        for feature_id in item[name]:
            if not registry.known(feature_id):
                return "unknown_id"
    for feature_id in item["data_properties"]:
        if layer_of(feature_id) != "data":
            return "data_layer"
    if "oracle" in item and item["oracle"] is not None:
        if item["oracle"] not in ORACLE_IDS:
            return "bad_oracle"
        oracle = item["oracle"]
    else:
        oracle = default_oracle
    if oracle not in ORACLE_IDS:
        return "bad_oracle"
    if not item["required"] and not item["data_properties"]:
        return "empty_spec"
    return None


def _trigger_of(raw: Any, registry: Registry) -> tuple[str | None, tuple[str, ...]]:
    if not isinstance(raw, list) or not raw or any(not isinstance(item, str) for item in raw):
        return "trigger", ()
    for item in raw:
        if not registry.known(item):
            return "unknown_id", ()
    reduced = reduce_conjunction(raw, registry)
    if not reduced:
        return "empty_trigger", ()
    return None, reduced


def _hypothesis_for(wb: Any, record: Any, opened: str) -> Any:
    owner: str | None
    try:
        owner = wb.owner_of(record.record_id)
    except KeyError:
        owner = None
    if owner is not None:
        try:
            return wb.theory.get(owner)
        except KeyError:
            owner = None
    try:
        return wb.theory.get(opened)
    except KeyError:
        return None


class Conjecturer:
    """One structured call when an experiment opens a family, then a workbench proposal."""

    def __init__(
        self,
        *,
        gateway: Gateway,
        extract: Any,
        book: ConjectureBook,
        registry: Registry | None = None,
        sources: Any = None,
        seed: int,
        tier: str | None = None,
    ) -> None:
        self.gateway = gateway
        self.extract = extract
        self.book = book
        self.registry = registry
        self.sources = {} if sources is None else sources
        self.seed = seed
        self.tier = CONJECTURER_TIER if tier is None else tier

    def after(self, wb: Any, record: Any, outcome: Any) -> Conjecture | None:
        """Conjecture for a new family. ``None`` when this experiment opened nothing."""
        opened = getattr(getattr(outcome, "observation", None), "opened", None)
        if opened is None:
            return None
        hypothesis = _hypothesis_for(wb, record, opened)
        if hypothesis is None:
            return None
        engine = hypothesis.engine
        oracle = hypothesis.oracle if isinstance(hypothesis.oracle, str) else ""
        phi = getattr(record, "phi", None)
        snippets = select_sources(engine, hypothesis, phi, self.sources)
        source_names = tuple(f"{engine}:{item.path}:{item.start}-{item.end}" for item in snippets)
        minimized = _minimized_case(record.label)
        prompt = conjecturer_prompt(
            engine=engine,
            oracle=oracle,
            label=record.label,
            case=record.case,
            minimized=minimized,
            phi=phi,
            hypothesis=hypothesis,
            snippets=snippets,
            registry=self.registry,
        )
        reply = self.gateway.call(
            "conjecturer",
            prompt,
            tier=self.tier,
            seed=self.seed,
            temperature=CONJECTURER_TEMPERATURE,
            max_tokens=CONJECTURER_MAX_TOKENS,
        )
        conjecture_id = self.book.next_id()
        mechanism, trigger, predictions, dropped, status, reason = _read_reply(
            reply, hypothesis, self.registry
        )
        edit_id: str | None = None
        accepted: bool | None = None
        edit_reason: str | None = None
        if status == "registered":
            edit_id, accepted, edit_reason = _propose(
                wb, record, hypothesis, mechanism or "", trigger, predictions, self.registry
            )
        else:
            trigger = ()
            predictions = ()
        conjecture = Conjecture(
            conjecture_id=conjecture_id,
            record_id=record.record_id,
            hypothesis_id=hypothesis.hypothesis_id,
            engine=engine,
            oracle=oracle,
            status=status,
            reason=reason,
            mechanism=mechanism,
            trigger=trigger,
            predictions=tuple(predictions),
            dropped=tuple(dropped),
            edit_id=edit_id,
            accepted=accepted,
            edit_reason=edit_reason,
            key=reply.key,
            sources=source_names,
        )
        self.book.add(conjecture)
        return conjecture


def _read_reply(
    reply: Any, hypothesis: Any, registry: Registry | None
) -> tuple[str | None, tuple[str, ...], tuple[dict, ...], tuple[dict, ...], str, str | None]:
    """Mechanism, trigger, kept predictions, drops, status, and reason."""
    if reply.status != "ok" or not isinstance(reply.data, dict):
        status = reply.status if reply.status in _COPY_STATUSES else "rejected"
        return None, (), (), (), status, reply.reason
    data = reply.data
    mechanism = data.get("mechanism")
    if not isinstance(mechanism, str) or mechanism == "":
        return None, (), (), (), "rejected", "mechanism"
    words = _active(registry)
    problem, trigger = _trigger_of(data.get("trigger"), words)
    if problem is not None:
        return mechanism, (), (), (), "rejected", problem
    raw = data.get("prediction")
    if not isinstance(raw, list):
        return mechanism, (), (), (), "rejected", "prediction"
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    default_oracle = hypothesis.oracle if isinstance(hypothesis.oracle, str) else None
    for index, item in enumerate(raw):
        why_drop = _prediction_problem(item, words, default_oracle)
        if why_drop is not None:
            dropped.append({"index": index, "reason": why_drop})
            continue
        if len(kept) >= CONJECTURER_MAX_PREDICTIONS:
            dropped.append({"index": index, "reason": "over_max"})
            continue
        if "oracle" in item and item["oracle"] is not None:
            oracle = item["oracle"]
        else:
            oracle = default_oracle
        why = item.get("why")
        if not isinstance(why, str):
            why = ""
        spec = Spec(
            engine=hypothesis.engine,
            oracle=oracle,
            required=tuple(item["required"]),
            forbidden=tuple(item["forbidden"]),
            data_properties=tuple(item["data_properties"]),
        )
        kept.append({"spec": spec.to_dict(), "expect": item["expect"], "why": why})
    if not kept:
        return mechanism, (), (), tuple(dropped), "rejected", "no_valid_prediction"
    return mechanism, trigger, tuple(kept), tuple(dropped), "registered", None


def _propose(
    wb: Any,
    record: Any,
    hypothesis: Any,
    mechanism: str,
    trigger: tuple[str, ...],
    predictions: tuple[dict, ...],
    registry: Registry | None,
) -> tuple[str | None, bool | None, str | None]:
    phi_raw = getattr(record, "phi", None)
    covered = False
    if isinstance(phi_raw, dict):
        try:
            phi = Phi.from_dict(phi_raw)
        except ValueError:
            phi = None
        if phi is not None:
            closed = _active(registry).closure(phi.features)
            covered = all(literal in closed for literal in trigger)
    elif phi_raw is not None and hasattr(phi_raw, "features"):
        closed = _active(registry).closure(phi_raw.features)
        covered = all(literal in closed for literal in trigger)
    if not covered:
        return None, None, "not_covering"
    try:
        template = dataclasses.replace(hypothesis, specific=trigger, source="conjecturer")
        proposal = Proposal(
            kind="revise",
            proposer="conjecturer",
            removes=(hypothesis.hypothesis_id,),
            adds=(template,),
            bets=tuple({"spec": item["spec"], "expect": item["expect"]} for item in predictions),
            trigger=(record.record_id,),
            rationale=mechanism,
        )
        edit = wb.propose(proposal)
    except ValueError:
        return None, None, "proposal_error"
    accepted = edit.decision == "accepted"
    reason = None if accepted else edit.payload.get("reason")
    return edit.edit_id, accepted, reason
