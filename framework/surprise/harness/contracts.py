"""Contracts the harness writes: a SQL case, its label, and the experiment record.

The theory layer may import this module. This module does not import the theory
layer, or any pre-surprise package.
"""

from __future__ import annotations

import json
from dataclasses import MISSING, dataclass, field, fields
from datetime import datetime
from typing import Any

SCHEMA_VERSION = 1

# pass: the two forms agree; fail: a confirmed discrepancy; invalid: no conclusion.
LABELS = ("pass", "fail", "invalid")

# Seven oracle ids (PLAN section 3): ternary logic partitioning, NoREC, plan variant, index presence, equivalent query, version differential, cross-DBMS differential.
ORACLE_IDS = (
    "tlp",
    "norec",
    "plan_variant",
    "index_presence",
    "equivalent_query",
    "version_differential",
    "cross_dbms",
)

# wrong_result: the two forms disagree; error_mismatch: one form errors (and the error is not value-dependent) while the other succeeds; crash: an internal engine error.
FAIL_KINDS = ("wrong_result", "error_mismatch", "crash")

# setup_error: a setup or insert statement failed; nondeterministic: the result depends on unspecified order or a random function; not_applicable: the oracle's premises do not hold; query_error: the query or predicate itself is broken; value_dependent_error: a runtime error (overflow, cast failure, and the like) whose occurrence depends on evaluation order; timeout: timed out, so there is no conclusion; harness_error: the harness itself raised while judging; untrusted_rewrite: the rewrite is not from the frozen rule library (and is not a verified LLM rewrite); direction_unknown: a version mismatch with no independent evidence of which side is the regression; insufficient_engines: cross-DBMS quorum smaller than three independent engines; non_unique_outlier: the target is not the unique dissenting engine.
INVALID_REASONS = (
    "setup_error",
    "nondeterministic",
    "not_applicable",
    "query_error",
    "value_dependent_error",
    "timeout",
    "harness_error",
    "untrusted_rewrite",
    "direction_unknown",
    "insufficient_engines",
    "non_unique_outlier",
)


class _Serializable:
    """JSON round-trip shared by the harness and theory contracts.

    Subclasses normalise ``tuple`` fields in ``__post_init__``. ``to_dict``
    emits only JSON-native values: tuples become lists and nested contracts
    become objects.
    """

    def to_dict(self) -> dict[str, Any]:
        exported: dict[str, Any] = {}
        for item in fields(type(self)):
            exported[item.name] = _export(getattr(self, item.name), item.name)
        return exported

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @classmethod
    def from_dict(cls, data: Any) -> _Serializable:
        if not isinstance(data, dict):
            raise ValueError(f"{cls.__name__}: expected a JSON object, got {data!r}")
        for key in data:
            if not isinstance(key, str):
                raise ValueError(
                    f"{cls.__name__}: JSON object keys must be strings, got {key!r}"
                )
        known = {item.name for item in fields(cls)}
        unknown = sorted(set(data) - known)
        if unknown:
            raise ValueError(f"{cls.__name__}: unknown keys {unknown}, got {data!r}")
        kwargs: dict[str, Any] = {}
        nested = cls._nested_fields()
        for item in fields(cls):
            if item.name not in data:
                if item.default is MISSING and item.default_factory is MISSING:
                    raise ValueError(
                        f"{cls.__name__}: missing required key {item.name!r}, got keys {sorted(data)!r}"
                    )
                continue
            kwargs[item.name] = _decode_nested(nested, item.name, data[item.name])
        return cls(**kwargs)

    @classmethod
    def from_json(cls, text: str) -> _Serializable:
        if not isinstance(text, str):
            raise ValueError(f"{cls.__name__}: expected a JSON string, got {text!r}")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            shown = text if len(text) <= 200 else text[:200] + "..."
            raise ValueError(f"{cls.__name__}: invalid JSON: {exc.msg}: {shown!r}") from None
        return cls.from_dict(data)

    @classmethod
    def _nested_fields(cls) -> dict[str, type[_Serializable]]:
        return {}


def _export(value: Any, field_name: str) -> Any:
    if isinstance(value, _Serializable):
        return value.to_dict()
    return _json_copy(value, field_name)


def _decode_nested(nested: dict[str, type[_Serializable]], name: str, value: Any) -> Any:
    factory = nested.get(name)
    if factory is None:
        return value
    if isinstance(value, factory):
        return value
    if isinstance(value, dict):
        return factory.from_dict(value)
    raise ValueError(f"{name}: expected a {factory.__name__} object, got {value!r}")


def _json_copy(value: Any, field_name: str) -> Any:
    """Deep-copy ``value`` into JSON-native form. Tuples become lists."""
    if value is None or isinstance(value, str) or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError(f"{field_name}: must be a finite number, got {value!r}")
        return value
    if isinstance(value, (list, tuple)):
        return [_json_copy(item, field_name) for item in value]
    if isinstance(value, dict):
        copied: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{field_name}: JSON object keys must be strings, got {key!r}")
            copied[key] = _json_copy(item, field_name)
        return copied
    raise ValueError(f"{field_name}: value is not JSON-safe, got {value!r}")


def _require_str(value: Any, field_name: str, *, nonempty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: must be a string, got {value!r}")
    if nonempty and value == "":
        raise ValueError(f"{field_name}: must be a non-empty string, got {value!r}")
    return value


def _optional_str(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_str(value, field_name)


def _require_choice(value: Any, choices: tuple[str, ...], field_name: str) -> Any:
    if value not in choices:
        raise ValueError(f"{field_name}: must be one of {choices}, got {value!r}")
    return value


def _require_absent(value: Any, field_name: str, y: str) -> None:
    if value is not None:
        raise ValueError(f"{field_name}: must be None when y is {y!r}, got {value!r}")


def _require_object(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name}: expected a JSON object, got {value!r}")
    return _json_copy(value, field_name)


def _optional_object(value: Any, field_name: str) -> dict[str, Any] | None:
    if value is None:
        return None
    return _require_object(value, field_name)


def _freeze_strings(value: Any, field_name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name}: expected a list or tuple of strings, got {value!r}")
    frozen: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field_name}: expected strings, got {item!r}")
        frozen.append(item)
    return tuple(frozen)


def _freeze_string_groups(value: Any, field_name: str) -> tuple[tuple[str, ...], ...]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ValueError(
            f"{field_name}: expected a list or tuple of string lists, got {value!r}"
        )
    return tuple(_freeze_strings(item, field_name) for item in value)


def _freeze_objects(value: Any, field_name: str) -> tuple[dict[str, Any], ...]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name}: expected a list or tuple of JSON objects, got {value!r}")
    frozen: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"{field_name}: expected JSON objects, got {item!r}")
        frozen.append(_json_copy(item, field_name))
    return tuple(frozen)


def _require_seq(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"seq: must be an integer >= 1, got {value!r}")
    return value


def _require_number(value: Any, field_name: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name}: must be a number, got {value!r}")
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        raise ValueError(f"{field_name}: must be a finite number, got {value!r}")
    return value


def _optional_number(value: Any, field_name: str) -> int | float | None:
    if value is None:
        return None
    return _require_number(value, field_name)


def _require_unit_interval(value: Any) -> int | float | None:
    if value is None:
        return None
    number = _require_number(value, "p_t")
    if not 0 <= number <= 1:
        raise ValueError(f"p_t: must be between 0 and 1 inclusive, got {value!r}")
    return number


def _require_timestamp(value: Any) -> str:
    text = _require_str(value, "created_at", nonempty=True)
    try:
        datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(f"created_at: must be an ISO 8601 timestamp, got {value!r}") from None
    return text


@dataclass(frozen=True)
class SqlCase(_Serializable):
    """One executable test case, the x of an experiment record."""

    engine: str
    setup: tuple[str, ...]
    query: str
    predicate: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "engine", _require_str(self.engine, "engine", nonempty=True))
        object.__setattr__(self, "setup", _freeze_strings(self.setup, "setup"))
        object.__setattr__(self, "query", _require_str(self.query, "query", nonempty=True))
        object.__setattr__(self, "predicate", _optional_str(self.predicate, "predicate"))


@dataclass(frozen=True)
class IdentityEvidence(_Serializable):
    """What made two executions the same bug: switches, error class, behavior shape."""

    switches: tuple[str, ...] = ()
    error_class: str | None = None
    behavior: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "switches", _freeze_strings(self.switches, "switches"))
        object.__setattr__(self, "error_class", _optional_str(self.error_class, "error_class"))
        object.__setattr__(self, "behavior", _require_object(self.behavior, "behavior"))


@dataclass(frozen=True)
class Label(_Serializable):
    """The oracle verdict y plus the evidence behind it.

    ``fail_kind`` is set only when y is ``fail``. ``invalid_reason`` is set only
    when y is ``invalid``. Both are ``None`` when y is ``pass``. ``cve`` stays
    empty until the CVE pipeline fills it.
    """

    y: str
    oracle: str
    fail_kind: str | None = None
    invalid_reason: str | None = None
    identity: IdentityEvidence = field(default_factory=IdentityEvidence)
    cve: dict[str, Any] = field(default_factory=dict)
    detail: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_choice(self.y, LABELS, "y")
        _require_choice(self.oracle, ORACLE_IDS, "oracle")
        if not isinstance(self.identity, IdentityEvidence):
            raise ValueError(f"identity: expected IdentityEvidence, got {self.identity!r}")
        object.__setattr__(self, "cve", _require_object(self.cve, "cve"))
        object.__setattr__(self, "detail", _require_object(self.detail, "detail"))
        if self.y == "pass":
            _require_absent(self.fail_kind, "fail_kind", "pass")
            _require_absent(self.invalid_reason, "invalid_reason", "pass")
        elif self.y == "fail":
            _require_choice(self.fail_kind, FAIL_KINDS, "fail_kind")
            _require_absent(self.invalid_reason, "invalid_reason", "fail")
        else:
            _require_choice(self.invalid_reason, INVALID_REASONS, "invalid_reason")
            _require_absent(self.fail_kind, "fail_kind", "invalid")

    @classmethod
    def _nested_fields(cls) -> dict[str, type[_Serializable]]:
        return {"identity": IdentityEvidence}


@dataclass(frozen=True)
class ExperimentRecord(_Serializable):
    """One execution, including pass and invalid. Append-only in the ledger.

    ``spec`` is a serialised spec dict so this module does not import the theory
    layer. ``p_t``, when present, is the theory's probability before execution
    and lies in ``[0, 1]``.
    """

    record_id: str
    run_id: str
    seq: int
    case: SqlCase
    label: Label
    purpose: str
    created_at: str
    spec: dict[str, Any] | None = None
    phi: dict[str, Any] | None = None
    theory_version: str | None = None
    p_t: float | None = None
    surprise: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "record_id", _require_str(self.record_id, "record_id", nonempty=True)
        )
        object.__setattr__(self, "run_id", _require_str(self.run_id, "run_id", nonempty=True))
        object.__setattr__(self, "seq", _require_seq(self.seq))
        if not isinstance(self.case, SqlCase):
            raise ValueError(f"case: expected SqlCase, got {self.case!r}")
        if not isinstance(self.label, Label):
            raise ValueError(f"label: expected Label, got {self.label!r}")
        object.__setattr__(self, "purpose", _require_str(self.purpose, "purpose", nonempty=True))
        object.__setattr__(self, "created_at", _require_timestamp(self.created_at))
        object.__setattr__(self, "spec", _optional_object(self.spec, "spec"))
        object.__setattr__(self, "phi", _optional_object(self.phi, "phi"))
        object.__setattr__(
            self, "theory_version", _optional_str(self.theory_version, "theory_version")
        )
        object.__setattr__(self, "p_t", _require_unit_interval(self.p_t))
        object.__setattr__(self, "surprise", _optional_number(self.surprise, "surprise"))

    @classmethod
    def _nested_fields(cls) -> dict[str, type[_Serializable]]:
        return {"case": SqlCase, "label": Label}
