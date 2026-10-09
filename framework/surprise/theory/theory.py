"""Theory T = (H, R, K^v): predict, then learn from one labelled experiment."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from typing import Any

from surprise.features.phi import Phi
from surprise.features.registry import Registry, default_registry
from surprise.features.units import unit_of
from surprise.harness.contracts import ORACLE_IDS, Label

from .constants import P_CONFIRMED, P_PENDING
from .contracts import Hypothesis
from .hypothesis import apply_negative, apply_positive, new_family, position
from .identity import identity_match
from .predict import Prediction, surprise_bits, triage
from .residual import Residual
from .validity import Validity, experiment_class
from .vspace import _canonical, _drop_redundant, reduce_conjunction

_STATE_KEYS = ("schema", "vocab", "hypotheses", "residual", "validity", "passes", "next_id")
_SCHEMA = 1


def _phi_token(phi: Phi) -> str:
    """Identity of a phi. ``Phi`` itself is unhashable because its layers are a mapping."""
    return json.dumps(phi.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _scope(engine: str, oracle: str) -> str:
    return f"{engine}|{oracle}"


def _profile_ran(label: Label) -> bool:
    """True only for a dict profile whose status is ``ran``. Anything else counts as absent."""
    profile = label.cve.get("profile") if isinstance(label.cve, dict) else None
    return isinstance(profile, dict) and profile.get("status") == "ran"


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name}: expected an integer >= 1, got {value!r}")
    return value


@dataclass(frozen=True)
class Observation:
    """What one experiment did to the theory. ``surprise`` is ``None`` when the label is invalid."""

    prediction: Prediction
    y: str
    surprise: float | None
    triage: str
    effects: tuple[tuple[str, str], ...]
    opened: str | None
    unexplained: bool

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe copy. ``effects`` becomes a list of pairs."""
        return {
            "prediction": self.prediction.to_dict(),
            "y": self.y,
            "surprise": self.surprise,
            "triage": self.triage,
            "effects": [list(effect) for effect in self.effects],
            "opened": self.opened,
            "unexplained": self.unexplained,
        }


class Theory:
    """The version space, the residual, and the validity model, updated together."""

    def __init__(self, registry: Registry | None = None) -> None:
        self._registry = default_registry() if registry is None else registry
        self.residual = Residual()
        self.validity = Validity()
        self._hypotheses: list[Hypothesis] = []
        self._passes: dict[str, list[tuple[Phi, str]]] = {}
        self._seen_passes: dict[str, set[str]] = {}
        self._next_id = 1

    @property
    def hypotheses(self) -> tuple[Hypothesis, ...]:
        """Every hypothesis, in the order it was first stored."""
        return tuple(self._hypotheses)

    def get(self, hypothesis_id: str) -> Hypothesis:
        """Return the hypothesis with this id. Unknown ids raise ``KeyError``."""
        for hypothesis in self._hypotheses:
            if hypothesis.hypothesis_id == hypothesis_id:
                return hypothesis
        raise KeyError(hypothesis_id)

    def put(self, hypothesis: Hypothesis) -> None:
        """Store ``hypothesis`` in canonical form, replacing an id already present."""
        stored = self._canonical_hypothesis(hypothesis)
        for index, current in enumerate(self._hypotheses):
            if current.hypothesis_id == stored.hypothesis_id:
                self._hypotheses[index] = stored
                return
        self._hypotheses.append(stored)

    def predict(self, phi: Phi, oracle: str) -> Prediction:
        """Zone and probabilities for ``phi`` under ``oracle``. Does not change state.

        A confirmed hypothesis wins over a pending one. Anything else, including
        ``undetermined`` and ``out_of_scope``, leaves the zone unexplored.
        """
        self._check_example(phi, oracle)
        confirmed: list[str] = []
        pending: list[str] = []
        for hypothesis in self._hypotheses:
            where = position(hypothesis, phi, oracle, self._registry)
            if where == "confirmed":
                confirmed.append(hypothesis.hypothesis_id)
            elif where == "pending":
                pending.append(hypothesis.hypothesis_id)
        unit = unit_of(phi, oracle, self._registry)
        klass = experiment_class(phi, self._registry)
        if confirmed:
            zone = "confirmed"
            owner: str | None = confirmed[0]
            p_fail_valid = P_CONFIRMED
        elif pending:
            zone = "pending"
            owner = pending[0]
            p_fail_valid = P_PENDING
        else:
            zone = "unexplored"
            owner = None
            p_fail_valid = self.residual.rate(unit)
        return Prediction(
            engine=phi.engine,
            oracle=oracle,
            unit=unit,
            experiment_class=klass,
            zone=zone,
            hypothesis_id=owner,
            confirmed=tuple(confirmed),
            pending=tuple(pending),
            p_fail_valid=p_fail_valid,
            p_invalid=self.validity.rate(klass, oracle),
        )

    def observe(
        self,
        phi: Phi,
        label: Label,
        record_id: str,
        *,
        prediction: Prediction | None = None,
    ) -> Observation:
        """Learn ``label``. The prediction is the one made before any update."""
        prepared = self._prepare(phi, label, record_id, prediction)
        self.validity.observe(prepared.experiment_class, label.oracle, label.y, label.invalid_reason)
        if label.y == "invalid":
            return Observation(
                prediction=prepared,
                y=label.y,
                surprise=None,
                triage="invalid",
                effects=(),
                opened=None,
                unexplained=False,
            )
        surprise = surprise_bits(prepared.p_fail_valid, label.y)
        kind = triage(label.y, surprise)
        effects, absorbed = self._update_hypotheses(phi, label, record_id)
        opened: str | None = None
        unexplained = False
        if label.y == "fail" and not absorbed:
            if _profile_ran(label):
                opened = self._open_family(phi, label, record_id)
            else:
                unexplained = True
                self.residual.observe(prepared.unit, "fail")
        elif label.y == "pass":
            if prepared.zone == "unexplored":
                self.residual.observe(prepared.unit, "pass")
            self._remember_pass(phi, label.oracle, record_id)
        return Observation(
            prediction=prepared,
            y=label.y,
            surprise=surprise,
            triage=kind,
            effects=tuple(effects),
            opened=opened,
            unexplained=unexplained,
        )

    def to_dict(self) -> dict[str, Any]:
        """Complete state. The same history yields an equal dict."""
        passes: dict[str, list[dict[str, Any]]] = {}
        for scope in sorted(self._passes):
            passes[scope] = [
                {"phi": seen.to_dict(), "record_id": record_id}
                for seen, record_id in self._passes[scope]
            ]
        return {
            "schema": _SCHEMA,
            "vocab": self._registry.digest(),
            "hypotheses": [hypothesis.to_dict() for hypothesis in self._hypotheses],
            "residual": self.residual.to_dict(),
            "validity": self.validity.to_dict(),
            "passes": passes,
            "next_id": self._next_id,
        }

    @classmethod
    def from_dict(cls, data: Any, registry: Registry | None = None) -> Theory:
        """Restore a theory that learns exactly as the saved one would."""
        if not isinstance(data, dict) or set(data) != set(_STATE_KEYS):
            raise ValueError(f"theory: expected keys {_STATE_KEYS}, got {data!r}")
        if isinstance(data["schema"], bool) or data["schema"] != _SCHEMA:
            raise ValueError(f"theory: schema must be 1, got {data['schema']!r}")
        theory = cls(registry)
        if data["vocab"] != theory._registry.digest():
            raise ValueError("theory: vocabulary does not match the registry")
        theory._next_id = _positive_int(data["next_id"], "next_id")
        theory.residual = Residual.from_dict(data["residual"])
        theory.validity = Validity.from_dict(data["validity"])
        theory._load_passes(data["passes"])
        hypotheses = data["hypotheses"]
        if not isinstance(hypotheses, list):
            raise ValueError(f"theory: hypotheses must be a list, got {hypotheses!r}")
        for item in hypotheses:
            theory.put(Hypothesis.from_dict(item))
        return theory

    @property
    def version(self) -> str:
        """``T-`` plus the first 12 hex digits of the canonical state. It changes with the state."""
        blob = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        return "T-" + digest[:12]

    def _prepare(self, phi: object, label: object, record_id: object, prediction: object) -> Prediction:
        if not isinstance(phi, Phi):
            raise ValueError(f"phi: expected Phi, got {type(phi).__name__}")
        if phi.vocab != self._registry.digest():
            raise ValueError("phi vocabulary does not match the theory")
        if not isinstance(label, Label):
            raise ValueError(f"label: expected Label, got {type(label).__name__}")
        if not isinstance(record_id, str) or record_id == "":
            raise ValueError(f"record_id: expected a non-empty string, got {record_id!r}")
        if prediction is None:
            return self.predict(phi, label.oracle)
        if not isinstance(prediction, Prediction):
            raise ValueError(f"prediction: expected Prediction, got {type(prediction).__name__}")
        if (prediction.engine, prediction.oracle) != (phi.engine, label.oracle):
            raise ValueError(
                "prediction was made for "
                f"{prediction.engine!r}/{prediction.oracle!r}, not {phi.engine!r}/{label.oracle!r}"
            )
        return prediction

    def _check_example(self, phi: object, oracle: object) -> None:
        if not isinstance(phi, Phi):
            raise ValueError(f"phi: expected Phi, got {type(phi).__name__}")
        if phi.vocab != self._registry.digest():
            raise ValueError("phi vocabulary does not match the theory")
        if oracle not in ORACLE_IDS:
            raise ValueError(f"oracle: must be one of {ORACLE_IDS}, got {oracle!r}")

    def _canonical_hypothesis(self, hypothesis: object) -> Hypothesis:
        if not isinstance(hypothesis, Hypothesis):
            raise ValueError(f"hypothesis: expected Hypothesis, got {type(hypothesis).__name__}")
        if hypothesis.hypothesis_id == "" or hypothesis.engine == "":
            raise ValueError("hypothesis_id and engine must be non-empty")
        if hypothesis.oracle not in ORACLE_IDS:
            raise ValueError(f"oracle: must be one of {ORACLE_IDS}, got {hypothesis.oracle!r}")
        specific = reduce_conjunction(hypothesis.specific, self._registry)
        closed = self._registry.closure(specific)
        reduced: list[tuple[str, ...]] = []
        for member in hypothesis.general:
            literals = reduce_conjunction(member, self._registry)
            if any(literal not in closed for literal in literals):
                raise ValueError(f"general member {literals!r} is not more general than S {specific!r}")
            reduced.append(literals)
        general = _canonical(_drop_redundant(reduced, self._registry))
        return replace(hypothesis, specific=specific, general=general)

    def _update_hypotheses(
        self, phi: Phi, label: Label, record_id: str
    ) -> tuple[list[tuple[str, str]], bool]:
        """Apply the example to the hypotheses that already existed. Returns effects and whether a failure was absorbed."""
        effects: list[tuple[str, str]] = []
        absorbed = False
        for hypothesis in tuple(self._hypotheses):
            where = position(hypothesis, phi, label.oracle, self._registry)
            if where in ("out_of_scope", "undetermined"):
                continue
            if label.y == "pass":
                if where == "outside":
                    continue
                update = apply_negative(hypothesis, phi, record_id, self._registry)
                self._replace(hypothesis.hypothesis_id, update.hypothesis)
                effects.append((hypothesis.hypothesis_id, update.outcome))
                continue
            match = identity_match(hypothesis, label)
            if match is None:
                if where != "outside":
                    effects.append((hypothesis.hypothesis_id, "unknown_identity"))
                continue
            if match:
                if where == "outside":
                    effects.append((hypothesis.hypothesis_id, "outside"))
                    continue
                update = apply_positive(hypothesis, phi, record_id, self._registry)
                self._replace(hypothesis.hypothesis_id, update.hypothesis)
                effects.append((hypothesis.hypothesis_id, update.outcome))
                absorbed = True
                continue
            if where == "outside":
                continue
            update = apply_negative(hypothesis, phi, record_id, self._registry)
            self._replace(hypothesis.hypothesis_id, update.hypothesis)
            effects.append((hypothesis.hypothesis_id, update.outcome))
        return effects, absorbed

    def _replace(self, hypothesis_id: str, hypothesis: Hypothesis) -> None:
        for index, current in enumerate(self._hypotheses):
            if current.hypothesis_id == hypothesis_id:
                self._hypotheses[index] = hypothesis
                return
        raise KeyError(hypothesis_id)

    def _open_family(self, phi: Phi, label: Label, record_id: str) -> str:
        """Mint ``h{n}``, skipping ids already stored. Used numbers are not recycled."""
        occupied = {hypothesis.hypothesis_id for hypothesis in self._hypotheses}
        number = self._next_id
        while f"h{number}" in occupied:
            number += 1
        hypothesis_id = f"h{number}"
        family = new_family(
            hypothesis_id,
            phi,
            label,
            record_id,
            negatives=tuple(self._passes.get(_scope(phi.engine, label.oracle), ())),
            registry=self._registry,
        )
        self._next_id = number + 1
        self._hypotheses.append(family)
        return hypothesis_id

    def _remember_pass(self, phi: Phi, oracle: str, record_id: str) -> None:
        scope = _scope(phi.engine, oracle)
        token = _phi_token(phi)
        seen = self._seen_passes.setdefault(scope, set())
        if token in seen:
            return
        seen.add(token)
        self._passes.setdefault(scope, []).append((phi, record_id))

    def _load_passes(self, data: object) -> None:
        if not isinstance(data, dict):
            raise ValueError(f"passes: expected an object, got {data!r}")
        for scope, rows in data.items():
            if not isinstance(scope, str):
                raise ValueError(f"passes: expected a string scope, got {scope!r}")
            engine, separator, oracle = scope.partition("|")
            if separator != "|" or engine == "" or oracle not in ORACLE_IDS:
                raise ValueError(f"passes: expected 'engine|oracle', got {scope!r}")
            if not isinstance(rows, list):
                raise ValueError(f"passes: {scope!r} must be a list, got {rows!r}")
            loaded: list[tuple[Phi, str]] = []
            seen: set[str] = set()
            for row in rows:
                if not isinstance(row, dict) or set(row) != {"phi", "record_id"}:
                    raise ValueError(f"passes: expected phi and record_id, got {row!r}")
                record_id = row["record_id"]
                if not isinstance(record_id, str) or record_id == "":
                    raise ValueError(f"passes: record_id must be a non-empty string, got {record_id!r}")
                phi = Phi.from_dict(row["phi"])
                if phi.engine != engine:
                    raise ValueError(f"passes: {scope!r} holds a phi of engine {phi.engine!r}")
                loaded.append((phi, record_id))
                seen.add(_phi_token(phi))
            if loaded:
                self._passes[scope] = loaded
                self._seen_passes[scope] = seen
