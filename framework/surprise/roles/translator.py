"""Migration translator: one hypothesis on one engine, one case on another.

The prompt is a pure function of the hypothesis wording, the source SQL, the
target spec, and optional feedback. Record ids, hypothesis ids, family ids,
run ids, and the seed never enter it. A translation is an experiment: the
harness labels it, and this role only records whether its prediction held.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from surprise.features.registry import Registry, default_registry
from surprise.features.spec import check_spec
from surprise.features.vocabulary import layer_of
from surprise.harness.contracts import SqlCase
from surprise.theory.contracts import Spec
from surprise.theory.vspace import reduce_conjunction

from .base import Role, RoleContext
from .constants import (
    TRANSLATOR_ATTEMPTS,
    TRANSLATOR_MAX_TOKENS,
    TRANSLATOR_PER_CHOICE,
    TRANSLATOR_TEMPERATURE,
    TRANSLATOR_TIER,
)
from .implementer import _DIALECT, _feature_lines
from .sources_map import DUCKDB_OPTIMIZER_FILES

_STOP = frozenset({"blocked", "miss", "error"})
_BEHAVIORS = frozenset({"missing_only", "extra_only", "both", None})
_CASE_STATUSES = frozenset({"ok", "spec_unmet", "not_applicable"})
_EXPECTATIONS = frozenset({"pass", "fail"})
_LAYERS = frozenset({"ast", "data"})


def allowed_switches(engine: str) -> tuple[str, ...]:
    """Switch names the translator may predict for ``engine``.

    DuckDB's names are the optimizer files, sorted. Every other engine has
    none: identity is the behavior shape.
    """
    if engine == "duckdb":
        return tuple(sorted(DUCKDB_OPTIMIZER_FILES))
    return ()


def _active(registry: Registry | None) -> Registry:
    return default_registry() if registry is None else registry


def _as_spec(spec: Spec | dict) -> Spec:
    if isinstance(spec, Spec):
        return spec
    return Spec.from_dict(spec)


def _read(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _text(value: Any) -> str:
    if isinstance(value, str) and value != "":
        return value
    return "(none)"


def _joined(value: Any) -> str:
    if isinstance(value, str) or not isinstance(value, (list, tuple)) or not value:
        return "(none)"
    parts = [item for item in value if isinstance(item, str) and item != ""]
    if not parts:
        return "(none)"
    return ", ".join(parts)


def _strings(value: Any) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def translator_prompt(
    *,
    hypothesis: Any,
    source_case: Any,
    target_engine: str,
    spec: Spec | dict,
    mechanism: str | None,
    registry: Registry | None = None,
    feedback: dict | None = None,
) -> str:
    """English prompt for one translation. Ids and the seed never enter it."""
    target = _as_spec(spec)
    words = _active(registry)
    dialect = _DIALECT.get(target_engine, f"{target_engine} SQL.")
    frame_banned = "ast:window_spec:frame" not in target.required
    lines = [
        "You translate one SQL test from a source engine to a target engine.",
        "Reply with one JSON object and no other text.",
        f"Source engine: {_read(hypothesis, 'engine', '')}",
        f"Target engine: {target_engine}",
        f"Dialect: {dialect}",
        f"Oracle: {target.oracle}",
        f"Failure class: {_text(_read(hypothesis, 'fail_kind'))}",
        f"Error class: {_text(_read(hypothesis, 'error_class'))}",
        f"Behavior shape: {_text(_read(hypothesis, 'behavior_shape'))}",
        f"Source fix set: {_joined(_read(hypothesis, 'interventions'))}",
        f"Source plan differences: {_joined(_read(hypothesis, 'plan_delta'))}",
        "The translated statement must have every feature in required and every feature in data_properties.",
        "The translated statement must have none of the features in forbidden.",
        "Required features:",
    ]
    if target.required:
        lines.extend(_feature_lines(words, target.required, frame_banned=frame_banned))
    else:
        lines.append("- (none)")
    lines.append("Data properties:")
    if target.data_properties:
        lines.extend(_feature_lines(words, target.data_properties, frame_banned=frame_banned))
    else:
        lines.append("- (none)")
    lines.append("Forbidden features:")
    if target.forbidden:
        lines.extend(_feature_lines(words, target.forbidden, frame_banned=frame_banned))
    else:
        lines.append("- (none)")
    lines.append("Source setup:")
    setup = _strings(_read(source_case, "setup"))
    if setup:
        lines.extend(setup)
    else:
        lines.append("(none)")
    lines.append("Source query:")
    lines.append(_text(_read(source_case, "query")))
    predicate = _read(source_case, "predicate")
    lines.append("Source predicate: " + ("(none)" if predicate is None or predicate == "" else str(predicate)))
    lines.append("Mechanism: " + _text(mechanism))
    switches = allowed_switches(target_engine)
    if switches:
        lines.append("Switches available on the target engine:")
        lines.extend(f"- {name}" for name in switches)
        lines.append("Name only switches from this list. Use an empty list when you predict no switch.")
    else:
        lines.append("The target engine has no switches. Identity is the behavior shape.")
    lines.extend(
        [
            "setup is a list of statements that create tables and insert rows. Use small tables.",
            "query is one statement the target engine can execute. Put every required feature in that statement.",
            "predicate is a SQL expression or null.",
            'prediction.expect is "pass" or "fail".',
            "prediction.switches is a list of switch names from the list above, or an empty list.",
            'prediction.behavior is "missing_only", "extra_only", "both", or null.',
            "prediction.why is one sentence.",
            "JSON shape:",
            '{"setup": ["statement"], "query": "statement", "predicate": null, '
            '"prediction": {"expect": "pass", "switches": [], "behavior": null, "why": "reason"}}',
            "Spec:",
            json.dumps(target.to_dict(), sort_keys=True, ensure_ascii=True),
        ]
    )
    if feedback:
        lines.append("Previous attempt:")
        query = feedback.get("query")
        if isinstance(query, str) and query != "":
            lines.append("query:")
            lines.append(query)
        missing = _strings(feedback.get("missing"))
        if missing:
            lines.append("Missing features:")
            lines.extend(_feature_lines(words, missing, frame_banned=frame_banned))
        extra = _strings(feedback.get("forbidden"))
        if extra:
            lines.append("Extra features:")
            lines.extend(_feature_lines(words, extra, frame_banned=frame_banned))
        undetermined = _strings(feedback.get("undetermined"))
        if undetermined:
            lines.append("Undetermined features:")
            lines.extend(_feature_lines(words, undetermined, frame_banned=frame_banned))
        switch = feedback.get("switch")
        if isinstance(switch, str) and switch != "":
            lines.append("Unrecognised switch: " + switch)
        reason = feedback.get("reason")
        if isinstance(reason, str) and reason != "":
            lines.append("Field problem: " + reason)
    return "\n".join(lines)


def _field_error(data: dict) -> str | None:
    """Why this object is not a usable translator reply. None when the shape is usable.

    The behavior value is checked later, after the switch subset, so a bad
    switch is reported before a bad behavior.
    """
    setup = data.get("setup")
    if not isinstance(setup, list) or any(not isinstance(item, str) for item in setup):
        return "setup must be a list of strings"
    if not isinstance(data.get("query"), str):
        return "query must be a string"
    if "predicate" not in data:
        return "predicate must be a string or null"
    predicate = data.get("predicate")
    if predicate is not None and not isinstance(predicate, str):
        return "predicate must be a string or null"
    prediction = data.get("prediction")
    if not isinstance(prediction, dict):
        return "prediction must be an object"
    if prediction.get("expect") not in _EXPECTATIONS:
        return "prediction.expect must be pass or fail"
    if "switches" not in prediction:
        return "prediction.switches must be a list of strings"
    switches = prediction.get("switches")
    if isinstance(switches, str) or not isinstance(switches, list) or any(not isinstance(item, str) for item in switches):
        return "prediction.switches must be a list of strings"
    if "behavior" not in prediction:
        return "prediction.behavior must be missing_only, extra_only, both, or null"
    return None


def _string_set(value: Any) -> set[str] | None:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        return None
    if not all(isinstance(item, str) for item in value):
        return None
    return set(value)


def _matches(found: Any, hypothesis_id: str) -> bool:
    return found is not None and getattr(found, "hypothesis_id", None) == hypothesis_id


def _hypothesis_of(wb: Any, hypothesis_id: Any) -> Any:
    """The hypothesis named by an attribution, or None when the theory has no such id."""
    if wb is None or not isinstance(hypothesis_id, str) or hypothesis_id == "":
        return None
    theory = getattr(wb, "theory", None)
    if theory is None:
        return None
    getter = getattr(theory, "get", None)
    found = None
    if callable(getter):
        try:
            found = getter(hypothesis_id)
        except KeyError:
            found = None
    if _matches(found, hypothesis_id):
        return found
    hypotheses = getattr(theory, "hypotheses", None)
    if isinstance(hypotheses, dict):
        found = hypotheses.get(hypothesis_id)
        return found if _matches(found, hypothesis_id) else None
    if isinstance(hypotheses, str) or hypotheses is None:
        return None
    for item in hypotheses:
        if _matches(item, hypothesis_id):
            return item
    return None


def _behavior_name(label: Any) -> str:
    from surprise.harness.cve.shape import behavior_shape

    identity = getattr(label, "identity", None)
    behavior = getattr(identity, "behavior", None) if identity is not None else None
    return behavior_shape(behavior if isinstance(behavior, dict) else {})


def _switch_identity(event: Any, switches: tuple[str, ...], label: Any) -> str:
    """Bisect when a profile ran, otherwise the attribution test."""
    cve = getattr(label, "cve", None)
    if not isinstance(cve, dict):
        cve = {}
    profile = cve.get("profile")
    if isinstance(profile, dict) and profile.get("status") == "ran":
        fix_set = _string_set(profile.get("fix_set"))
        if fix_set is not None and "fix_set" in profile:
            return "match" if fix_set == set(switches) else "mismatch"
    attribution = cve.get("attribution")
    if not isinstance(attribution, dict) or attribution.get("status") != "ran":
        return "unknown"
    consistent = attribution.get("consistent")
    if consistent is False:
        return "mismatch"
    if consistent is not True:
        return "unknown"
    hypothesis = _hypothesis_of(event.wb if event is not None else None, attribution.get("hypothesis_id"))
    if hypothesis is None:
        return "unknown"
    interventions = _string_set(getattr(hypothesis, "interventions", None))
    if interventions is None:
        return "unknown"
    return "match" if interventions == set(switches) else "mismatch"


def _identity_of(event: Any, switches: tuple[str, ...], behavior: str | None, label: Any) -> str:
    if switches:
        return _switch_identity(event, switches, label)
    if behavior is None:
        return "unknown"
    return "match" if _behavior_name(label) == behavior else "mismatch"


def _judge(event: Any, expect: str | None, switches: tuple[str, ...], behavior: str | None, label: Any) -> tuple[str, str | None]:
    y = getattr(label, "y", None)
    if y == "invalid":
        return "void", None
    state = "kept" if y == expect else "broken"
    if y == "fail" and expect == "fail":
        return state, _identity_of(event, switches, behavior, label)
    return state, None


@dataclass
class _Pending:
    """One successful translation that the harness has not settled yet."""

    translation_id: str
    oracle: str
    case_digest: str
    expect: str | None
    switches: tuple[str, ...]
    behavior: str | None
    settled: bool = False

    @classmethod
    def from_row(cls, row: dict) -> _Pending | None:
        translation_id = row.get("translation_id")
        oracle = row.get("oracle")
        digest = row.get("case_digest")
        if not isinstance(translation_id, str) or not isinstance(oracle, str) or not isinstance(digest, str):
            return None
        expect = row.get("expect")
        if expect not in _EXPECTATIONS:
            expect = None
        switches = _string_set(row.get("switches"))
        behavior = row.get("behavior")
        if behavior is not None and not isinstance(behavior, str):
            behavior = None
        return cls(
            translation_id=translation_id,
            oracle=oracle,
            case_digest=digest,
            expect=expect,
            switches=tuple(sorted(switches)) if switches is not None else (),
            behavior=behavior,
        )


class TranslatorSource:
    """Offers translated cases. The Hunter drops ones it has already run."""

    def __init__(self, role: Translator) -> None:
        self._role = role
        self._served: set[int] = set()
        self._done: set[tuple[str, str]] = set()
        self._ok: list[Any] = []

    def candidates(self, wb: Any, *, index: int, round: int) -> list:
        """Every successful translation so far.

        A new translation is made only on round 1 of an index that has not been
        served, and at most ``TRANSLATOR_PER_CHOICE`` of them. One engine has
        nothing to translate and makes no call.
        """
        if len(self._role.ctx.engines) <= 1:
            return list(self._ok)
        if round <= 1 and index not in self._served:
            self._served.add(index)
            self._translate_new(wb)
        return list(self._ok)

    def _translate_new(self, wb: Any) -> None:
        made = 0
        hypotheses = getattr(getattr(wb, "theory", None), "hypotheses", ())
        if isinstance(hypotheses, str):
            return
        for hypothesis in tuple(hypotheses):
            if made >= TRANSLATOR_PER_CHOICE:
                break
            engine = getattr(hypothesis, "engine", None)
            if engine not in self._role.ctx.engines or getattr(hypothesis, "oracle", None) is None:
                continue
            source_id = self._role._last_positive(hypothesis)
            if source_id is None:
                continue
            family = wb.family_of(hypothesis.hypothesis_id)
            for target in self._role.ctx.engines:
                if made >= TRANSLATOR_PER_CHOICE:
                    break
                if target == engine:
                    continue
                key = (family, target)
                if key in self._done:
                    continue
                self._done.add(key)
                candidate = self._role._translate(hypothesis, family, target, source_id)
                made += 1
                if candidate is not None:
                    self._ok.append(candidate)


class Translator(Role):
    """Translates a hypothesis onto each other engine, then settles the label."""

    name = "translator"

    def __init__(self, ctx: RoleContext) -> None:
        self.ctx = ctx
        self._cases: dict[str, Any] = {}
        self._rows: list[dict[str, Any]] = []
        self._pending: list[_Pending] = []
        self._by_status: dict[str, int] = {}
        self._settled_counts = {"kept": 0, "broken": 0, "void": 0}
        self._identity_counts = {"match": 0, "mismatch": 0, "unknown": 0}
        self._step_translated: list[list[Any]] = []
        self._step_settled: list[list[Any]] = []
        path = ctx.llm_dir / "translations.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        self._book = path.open("a", encoding="utf-8")
        self._source = TranslatorSource(self)
        try:
            self._replay(existing)
        except Exception:
            self.close()
            raise

    def sources(self) -> tuple:
        return (self._source,)

    def observe(self, event: Any) -> None:
        """Remember the case, then settle a translation this experiment matches."""
        record = getattr(event, "record", None)
        if record is not None:
            record_id = getattr(record, "record_id", None)
            case = getattr(record, "case", None)
            if isinstance(record_id, str) and record_id != "" and case is not None:
                self._cases[record_id] = case
        self._settle(event)

    def translations(self) -> list[dict[str, Any]]:
        """Every book row so far, translation rows and settle rows, in order."""
        return [json.loads(json.dumps(row)) for row in self._rows]

    def step(self) -> dict:
        result = {
            "translated": [list(item) for item in self._step_translated],
            "settled": [list(item) for item in self._step_settled],
        }
        self._step_translated = []
        self._step_settled = []
        return result

    def report(self) -> dict:
        return {
            "translations": sum(self._by_status.values()),
            "by_status": dict(self._by_status),
            "settled": dict(self._settled_counts),
            "identity": dict(self._identity_counts),
        }

    def manifest(self) -> dict:
        return {
            "switches": {engine: list(allowed_switches(engine)) for engine in self.ctx.engines}
        }

    def close(self) -> None:
        handle = self._book
        if handle is not None and not handle.closed:
            handle.flush()
            handle.close()

    def _last_positive(self, hypothesis: Any) -> str | None:
        positives = getattr(hypothesis, "positives", ())
        if isinstance(positives, str) or not isinstance(positives, (list, tuple)):
            return None
        found = None
        for record_id in positives:
            if isinstance(record_id, str) and record_id in self._cases:
                found = record_id
        return found

    def _mechanism(self, hypothesis_id: str) -> str | None:
        found = None
        for row in self.ctx.book.conjectures():
            if row.get("hypothesis_id") == hypothesis_id and row.get("status") == "registered":
                mechanism = row.get("mechanism")
                found = mechanism if isinstance(mechanism, str) else None
        return found

    def _translate(self, hypothesis: Any, family: str, target: str, source_id: str) -> Any:
        from surprise.hunter.hunter import Candidate
        from surprise.hunter.operators import oracle_options

        source_case = self._cases[source_id]
        specific = getattr(hypothesis, "specific", ())
        if isinstance(specific, str) or not isinstance(specific, (list, tuple)):
            specific = ()
        literals = tuple(
            feature_id for feature_id in specific if isinstance(feature_id, str) and layer_of(feature_id) in _LAYERS
        )
        required = reduce_conjunction(literals, self.ctx.registry)
        spec = Spec(engine=target, oracle=hypothesis.oracle, required=required)
        base = {
            "hypothesis_id": hypothesis.hypothesis_id,
            "family": family,
            "source_engine": hypothesis.engine,
            "target_engine": target,
            "oracle": hypothesis.oracle,
            "parent": source_id,
        }
        if not required:
            self._record(base, status="empty_spec", case=None, expect=None, switches=None, behavior=None, tries=0, keys=[])
            return None
        mechanism = self._mechanism(hypothesis.hypothesis_id)
        status = "error"
        case: SqlCase | None = None
        expect: str | None = None
        switches: tuple[str, ...] | None = None
        behavior: str | None = None
        keys: list[str] = []
        tries = 0
        feedback: dict | None = None
        candidate = None
        for _ in range(TRANSLATOR_ATTEMPTS):
            prompt = translator_prompt(
                hypothesis=hypothesis,
                source_case=source_case,
                target_engine=target,
                spec=spec,
                mechanism=mechanism,
                registry=self.ctx.registry,
                feedback=feedback,
            )
            reply = self.ctx.gateway.call(
                "translator",
                prompt,
                tier=TRANSLATOR_TIER,
                seed=self.ctx.seed,
                temperature=TRANSLATOR_TEMPERATURE,
                max_tokens=TRANSLATOR_MAX_TOKENS,
            )
            tries += 1
            keys.append(reply.key)
            if reply.status in _STOP:
                status = reply.status
                break
            if reply.status != "ok" or not isinstance(reply.data, dict):
                status = "rejected"
                feedback = {"reason": reply.reason or reply.status or "rejected"}
                continue
            data = reply.data
            problem = _field_error(data)
            if problem is not None:
                status = "rejected"
                note: dict[str, Any] = {"reason": problem}
                if isinstance(data.get("query"), str):
                    note["query"] = data["query"]
                feedback = note
                continue
            prediction = data["prediction"]
            expect = prediction["expect"]
            switches = tuple(prediction["switches"])
            behavior = prediction["behavior"]
            unknown = [name for name in switches if name not in allowed_switches(target)]
            if unknown:
                status = "bad_switch"
                feedback = {
                    "query": data["query"],
                    "switch": ", ".join(unknown),
                    "reason": "unrecognised switch: " + ", ".join(unknown),
                }
                continue
            if behavior not in _BEHAVIORS:
                status = "rejected"
                feedback = {
                    "query": data["query"],
                    "reason": "prediction.behavior must be missing_only, extra_only, both, or null",
                }
                continue
            try:
                built = SqlCase(
                    engine=target,
                    setup=tuple(data["setup"]),
                    query=data["query"],
                    predicate=data["predicate"],
                )
            except ValueError as exc:
                status = "bad_case"
                feedback = {"query": data["query"], "reason": str(exc)}
                continue
            case = built
            options = oracle_options(case, [hypothesis.oracle])
            if not options:
                status = "not_applicable"
                break
            phi = self.ctx.extract(case)
            check = check_spec(phi, spec, self.ctx.registry)
            if not check.ok:
                status = "spec_unmet"
                feedback = {
                    "query": case.query,
                    "missing": check.missing,
                    "forbidden": check.forbidden,
                    "undetermined": check.undetermined,
                }
                continue
            status = "ok"
            rule = options[0][1] if hypothesis.oracle == "equivalent_query" else None
            candidate = Candidate(
                case=case,
                oracle=hypothesis.oracle,
                rule=rule,
                lane="translate",
                hypothesis_id=hypothesis.hypothesis_id,
                parent=source_id,
                op="translator",
                target=spec.to_dict(),
            )
            break
        if status not in _CASE_STATUSES:
            case = None
        stored_switches = None if switches is None else list(switches)
        self._record(
            base,
            status=status,
            case=case,
            expect=expect,
            switches=stored_switches,
            behavior=behavior,
            tries=tries,
            keys=keys,
        )
        return candidate

    def _record(
        self,
        base: dict[str, Any],
        *,
        status: str,
        case: SqlCase | None,
        expect: str | None,
        switches: list[str] | None,
        behavior: str | None,
        tries: int,
        keys: list[str],
    ) -> None:
        from surprise.hunter.operators import case_digest

        count = sum(1 for row in self._rows if row.get("type") == "translation")
        translation_id = f"t{count + 1}"
        digest = None if case is None else case_digest(case)
        row = {
            "type": "translation",
            "translation_id": translation_id,
            "hypothesis_id": base["hypothesis_id"],
            "family": base["family"],
            "source_engine": base["source_engine"],
            "target_engine": base["target_engine"],
            "oracle": base["oracle"],
            "status": status,
            "case": None if case is None else case.to_dict(),
            "case_digest": digest,
            "expect": expect,
            "switches": switches,
            "behavior": behavior,
            "tries": tries,
            "keys": list(keys),
            "parent": base["parent"],
        }
        self._write(row)
        self._by_status[status] = self._by_status.get(status, 0) + 1
        self._step_translated.append([translation_id, status])
        if status == "ok" and isinstance(digest, str):
            pending = _Pending(
                translation_id=translation_id,
                oracle=base["oracle"],
                case_digest=digest,
                expect=expect,
                switches=tuple(switches or ()),
                behavior=behavior,
            )
            self._pending.append(pending)

    def _settle(self, event: Any) -> None:
        if not any(not item.settled for item in self._pending):
            return
        record = getattr(event, "record", None)
        if record is None:
            return
        case = getattr(record, "case", None)
        label = getattr(record, "label", None)
        if case is None or label is None:
            return
        oracle = getattr(label, "oracle", None)
        if not isinstance(oracle, str):
            return
        from surprise.hunter.operators import case_digest

        digest = case_digest(case)
        record_id = getattr(record, "record_id", None)
        for item in self._pending:
            if item.settled or item.case_digest != digest or item.oracle != oracle:
                continue
            state, identity = _judge(event, item.expect, item.switches, item.behavior, label)
            item.settled = True
            self._write(
                {
                    "type": "settle",
                    "translation_id": item.translation_id,
                    "state": state,
                    "identity": identity,
                    "record_id": record_id,
                }
            )
            if state in self._settled_counts:
                self._settled_counts[state] += 1
            if identity in self._identity_counts:
                self._identity_counts[identity] += 1
            self._step_settled.append([item.translation_id, state, identity])

    def _write(self, row: dict[str, Any]) -> None:
        self._rows.append(row)
        self._book.write(json.dumps(row, ensure_ascii=True) + "\n")
        self._book.flush()

    def _replay(self, text: str) -> None:
        rows: list[dict[str, Any]] = []
        settled: set[str] = set()
        for line in text.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("translations book line must be an object")
            rows.append(row)
            if row.get("type") == "settle" and isinstance(row.get("translation_id"), str):
                settled.add(row["translation_id"])
        for row in rows:
            self._rows.append(row)
            kind = row.get("type")
            if kind == "translation":
                status = row.get("status")
                if isinstance(status, str):
                    self._by_status[status] = self._by_status.get(status, 0) + 1
                if status == "ok" and row.get("translation_id") not in settled:
                    pending = _Pending.from_row(row)
                    if pending is not None:
                        self._pending.append(pending)
            elif kind == "settle":
                state = row.get("state")
                if state in self._settled_counts:
                    self._settled_counts[state] += 1
                identity = row.get("identity")
                if identity in self._identity_counts:
                    self._identity_counts[identity] += 1


def build(ctx: RoleContext) -> Translator:
    """Plugin entry: one translator bound to ``ctx``."""
    return Translator(ctx)
