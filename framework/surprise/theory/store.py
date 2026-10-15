"""One directory for a theory: a file per hypothesis, append-only logs, generation snapshots."""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from surprise.features.phi import Phi
from surprise.features.registry import Registry, default_registry
from surprise.harness.contracts import ORACLE_IDS

from .contracts import Hypothesis, TheoryEdit
from .residual import Residual
from .theory import Theory
from .validity import Validity

# A hypothesis id or an engine name, safe as one path segment.
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_HEAD_KEYS = {"schema", "vocab", "generation", "next_id", "hypotheses", "version"}
_SNAPSHOT_KEYS = {"schema", "generation", "cause", "journal_seq", "version", "theory"}
_LOGS = ("journal.jsonl", "edits.jsonl", "negative.jsonl")
# os.replace on Windows can fail while another process still has the file open.
_REPLACE_ATTEMPTS = 6
_REPLACE_DELAYS = (0.05, 0.1, 0.2, 0.4, 0.8)


class StoreError(ValueError):
    """The store is missing, damaged, or does not match the value being saved."""


def _is_safe_id(value: object) -> bool:
    return isinstance(value, str) and _SAFE_ID.match(value) is not None


def _whole(value: object, minimum: int) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value >= minimum


def _one_line(text: object) -> str:
    flat = " ".join(str(text).split())
    return flat.encode("ascii", "backslashreplace").decode("ascii")


def _json_text(data: Any) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False, indent=1) + "\n"


def _jsonl_line(data: Any) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"


def _jsonl_text(rows: list[Any]) -> str:
    return "".join(_jsonl_line(row) for row in rows)


def _phi_token(phi: Phi) -> str:
    return json.dumps(phi.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _read_text(path: Path, label: str) -> str:
    try:
        with path.open("r", encoding="utf-8", newline="\n") as handle:
            return handle.read()
    except (OSError, UnicodeError) as exc:
        raise StoreError(f"{label}: {exc}") from exc


def _read_json(path: Path, label: str) -> Any:
    text = _read_text(path, label)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise StoreError(f"{label}: {exc}") from exc


def _read_jsonl(path: Path, label: str) -> list[Any]:
    text = _read_text(path, label)
    if text == "":
        return []
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    rows: list[Any] = []
    for index, line in enumerate(lines, start=1):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise StoreError(f"{label}: line {index}: {exc}") from exc
    return rows


def _write_text(path: Path, text: str) -> None:
    """Replace ``path`` only when the bytes would change. A ``.tmp`` sibling is removed."""
    if path.is_file():
        try:
            with path.open("r", encoding="utf-8", newline="\n") as handle:
                current = handle.read()
        except (OSError, UnicodeError):
            current = None
        if current == text:
            return
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        for attempt in range(_REPLACE_ATTEMPTS):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == _REPLACE_ATTEMPTS - 1:
                    raise
                time.sleep(_REPLACE_DELAYS[attempt])
    finally:
        if temporary.exists():
            temporary.unlink()


def _append_line(path: Path, data: Any) -> None:
    line = _jsonl_line(data)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)


def _split_pass_name(name: str) -> tuple[str, str] | None:
    if not name.endswith(".jsonl"):
        return None
    stem = name[: -len(".jsonl")]
    found: tuple[str, str] | None = None
    for oracle in ORACLE_IDS:
        suffix = f"__{oracle}"
        if not stem.endswith(suffix):
            continue
        engine = stem[: -len(suffix)]
        if not _is_safe_id(engine):
            continue
        if found is None or len(oracle) > len(found[1]):
            found = (engine, oracle)
    return found


class TheoryStore:
    """The files under one root. Build one with :meth:`create` or :meth:`open`.

    One store directory is written by one ``TheoryStore`` instance at a time.
    The journal sequence lives on that instance: ``append_journal``, ``last_seq``
    and ``close_generation`` do not read the journal file again.
    """

    def __init__(self, root: Path, registry: Registry) -> None:
        self._root = root
        self._registry = registry
        self._last_seq = 0

    @property
    def root(self) -> Path:
        return self._root

    @property
    def last_seq(self) -> int:
        """Sequence of the last journal line. An empty journal is 0."""
        return self._last_seq

    @classmethod
    def create(cls, root: str | Path, registry: Registry | None = None) -> TheoryStore:
        """Create an empty store. ``root`` must be missing or an empty directory."""
        active = default_registry() if registry is None else registry
        directory = Path(root)
        if directory.exists():
            if not directory.is_dir() or any(directory.iterdir()):
                raise StoreError(f"{directory} is not an empty directory")
        else:
            directory.mkdir(parents=True)
        (directory / "hypotheses").mkdir()
        (directory / "passes").mkdir()
        (directory / "generations").mkdir()
        for name in _LOGS:
            with (directory / name).open("w", encoding="utf-8", newline="\n") as handle:
                handle.write("")
        store = cls(directory, active)
        theory = Theory(active)
        store._write_live(theory, store._check_storable(theory), 0)
        return store

    @classmethod
    def open(cls, root: str | Path, registry: Registry | None = None) -> TheoryStore:
        """Open a store. ``head.json`` is checked, and the journal is read for its last sequence."""
        active = default_registry() if registry is None else registry
        directory = Path(root)
        if not (directory / "head.json").is_file():
            raise StoreError("head.json does not exist")
        store = cls(directory, active)
        store.head()
        rows = store._journal_rows()
        store._last_seq = rows[-1]["seq"] if rows else 0
        return store

    def head(self) -> dict[str, Any]:
        """Read and check ``head.json``. The six keys, the vocabulary and the id list must hold."""
        data = _read_json(self._root / "head.json", "head.json")
        if not isinstance(data, dict) or set(data) != _HEAD_KEYS:
            raise StoreError(f"head.json: expected keys {sorted(_HEAD_KEYS)}")
        if isinstance(data["schema"], bool) or data["schema"] != 1:
            raise StoreError(f"head.json: schema must be 1, got {data['schema']!r}")
        if data["vocab"] != self._registry.digest():
            raise StoreError("head.json: vocabulary does not match the registry")
        if not _whole(data["generation"], 0):
            raise StoreError(
                f"head.json: generation must be an integer >= 0, got {data['generation']!r}"
            )
        if not _whole(data["next_id"], 1):
            raise StoreError(f"head.json: next_id must be an integer >= 1, got {data['next_id']!r}")
        hypotheses = data["hypotheses"]
        if not isinstance(hypotheses, list):
            raise StoreError(f"head.json: hypotheses must be a list, got {hypotheses!r}")
        try:
            distinct = len(set(hypotheses)) == len(hypotheses)
        except TypeError as exc:
            raise StoreError(f"head.json: {exc}") from exc
        if not distinct:
            raise StoreError("head.json: hypotheses must be distinct")
        for hypothesis_id in hypotheses:
            if not _is_safe_id(hypothesis_id):
                raise StoreError(f"head.json: illegal hypothesis id {hypothesis_id!r}")
        if not isinstance(data["version"], str):
            raise StoreError(f"head.json: version must be a string, got {data['version']!r}")
        return data

    def save(self, theory: Theory) -> None:
        """Write ``theory`` over the live files. ``generation`` stays where head left it.

        An id or an engine that cannot be a file name raises :class:`StoreError` before any
        file is written.
        """
        state = self._check_storable(theory)
        generation = self.head()["generation"]
        self._write_live(theory, state, generation)

    def load(self) -> Theory:
        """Read the live theory. A file that is not the canonical saved state is refused."""
        head = self.head()
        raw_by_id = self._read_hypotheses(head["hypotheses"])
        passes = self._read_passes()
        residual = self._read_model("residual.json", Residual.from_dict)
        validity = self._read_model("validity.json", Validity.from_dict)
        state = {
            "schema": 1,
            "vocab": head["vocab"],
            "hypotheses": [raw_by_id[hypothesis_id] for hypothesis_id in head["hypotheses"]],
            "residual": residual,
            "validity": validity,
            "passes": passes,
            "next_id": head["next_id"],
        }
        try:
            theory = Theory.from_dict(state, self._registry)
        except ValueError as exc:
            raise StoreError(f"head.json: {exc}") from exc
        for hypothesis_id in head["hypotheses"]:
            label = f"hypotheses/{hypothesis_id}.json"
            try:
                stored = theory.get(hypothesis_id).to_dict()
            except KeyError as exc:
                raise StoreError(f"{label}: {exc}") from exc
            if stored != raw_by_id[hypothesis_id]:
                raise StoreError(f"{label} is not in canonical form")
        if theory.version != head["version"]:
            raise StoreError(
                f"head.json: version is {head['version']!r}, theory is {theory.version!r}"
            )
        return theory

    def append_journal(self, entry: object) -> int:
        """Append one event and return its sequence, starting at 1. ``entry`` must not carry ``seq``."""
        if not isinstance(entry, dict) or "seq" in entry or not isinstance(entry.get("kind"), str):
            raise ValueError(
                f"journal entry must be an object with a string kind and no seq, got {entry!r}"
            )
        seq = self._last_seq + 1
        stored = dict(entry)
        stored["seq"] = seq
        _append_line(self._root / "journal.jsonl", stored)
        self._last_seq = seq
        return seq

    def journal(self, after: int = 0) -> list[dict[str, Any]]:
        """Journal lines whose sequence is greater than ``after``, in order."""
        return [row for row in self._journal_rows() if row["seq"] > after]

    def append_edit(self, edit: object) -> None:
        """Append one state of an edit. The same id may be written again later."""
        if not isinstance(edit, TheoryEdit):
            raise ValueError(f"edit must be a TheoryEdit, got {type(edit).__name__}")
        _append_line(self._root / "edits.jsonl", edit.to_dict())

    def edit_history(self) -> list[TheoryEdit]:
        """Every logged state, in the order it was appended."""
        rows = _read_jsonl(self._root / "edits.jsonl", "edits.jsonl")
        history: list[TheoryEdit] = []
        for index, row in enumerate(rows, start=1):
            try:
                history.append(TheoryEdit.from_dict(row))
            except ValueError as exc:
                raise StoreError(f"edits.jsonl: line {index}: {exc}") from exc
        return history

    def edits(self) -> list[TheoryEdit]:
        """Latest state of each edit, in the order that edit id first appeared."""
        latest: dict[str, TheoryEdit] = {}
        order: list[str] = []
        for edit in self.edit_history():
            if edit.edit_id not in latest:
                order.append(edit.edit_id)
            latest[edit.edit_id] = edit
        return [latest[edit_id] for edit_id in order]

    def append_negative(self, entry: object) -> None:
        """Append one negative-memory record. ``fingerprint`` must be a non-empty string."""
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("fingerprint"), str)
            or entry["fingerprint"] == ""
        ):
            raise ValueError(
                f"negative entry must be an object with a non-empty fingerprint, got {entry!r}"
            )
        _append_line(self._root / "negative.jsonl", dict(entry))

    def negatives(self) -> list[dict[str, Any]]:
        """Every negative-memory record, in the order it was appended."""
        rows = _read_jsonl(self._root / "negative.jsonl", "negative.jsonl")
        found: list[dict[str, Any]] = []
        for index, row in enumerate(rows, start=1):
            if (
                not isinstance(row, dict)
                or not isinstance(row.get("fingerprint"), str)
                or row["fingerprint"] == ""
            ):
                raise StoreError(f"negative.jsonl: line {index} has no fingerprint")
            found.append(row)
        return found

    def close_generation(self, theory: Theory, *, cause: object) -> int:
        """Snapshot ``theory`` as the closing state of the open generation, then start the next one.

        The live hypothesis files, residual, validity, passes and the other head fields stay as the
        last :meth:`save` wrote them. An existing snapshot for this generation is left untouched.
        """
        if not isinstance(cause, str) or cause == "":
            raise ValueError(f"cause must be a non-empty string, got {cause!r}")
        head = self.head()
        generation = head["generation"]
        label = f"generations/g{generation:06d}.json"
        path = self._root / "generations" / f"g{generation:06d}.json"
        if path.exists():
            raise StoreError(f"{label} already exists")
        snapshot = {
            "schema": 1,
            "generation": generation,
            "cause": cause,
            "journal_seq": self.last_seq,
            "version": theory.version,
            "theory": theory.to_dict(),
        }
        _write_text(path, _json_text(snapshot))
        updated = dict(head)
        updated["generation"] = generation + 1
        _write_text(self._root / "head.json", _json_text(updated))
        return generation

    def generations(self) -> list[dict[str, Any]]:
        """One summary per closed generation, in order of the generation number."""
        listed = []
        for number in range(self.head()["generation"]):
            data = self._read_snapshot(number)
            listed.append(
                {
                    "generation": data["generation"],
                    "cause": data["cause"],
                    "journal_seq": data["journal_seq"],
                    "version": data["version"],
                }
            )
        return listed

    def load_generation(self, generation: object) -> Theory:
        """The theory that closed ``generation``. The open generation has no snapshot."""
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 0:
            raise ValueError(f"generation: expected an integer >= 0, got {generation!r}")
        data = self._read_snapshot(generation)
        label = f"generations/g{generation:06d}.json"
        try:
            theory = Theory.from_dict(data["theory"], self._registry)
        except ValueError as exc:
            raise StoreError(f"{label}: {exc}") from exc
        if theory.version != data["version"]:
            raise StoreError(
                f"{label}: version is {data['version']!r}, theory is {theory.version!r}"
            )
        return theory

    def verify(self) -> list[str]:
        """Every problem found in the store, one ASCII line each. An empty list means none."""
        problems: list[str] = []

        def attempt(call: Callable[[], Any]) -> Any:
            try:
                return call()
            except StoreError as exc:
                problems.append(_one_line(exc))
                return None

        attempt(self.load)
        attempt(self.journal)
        attempt(self.edit_history)
        attempt(self.negatives)
        head = attempt(self.head)
        if not isinstance(head, dict):
            return problems
        generation = head["generation"]
        directory = self._root / "generations"
        try:
            present = sorted(path.name for path in directory.iterdir() if path.is_file())
        except OSError as exc:
            problems.append(_one_line(f"generations: {exc}"))
            present = None
        expected = [f"g{number:06d}.json" for number in range(generation)]
        if present is not None and present != expected:
            problems.append(
                _one_line(f"generation files: expected {expected}, found {present}")
            )
        for number in range(generation):
            attempt(lambda number=number: self.load_generation(number))
        return problems

    def _check_storable(self, theory: Theory) -> dict[str, Any]:
        state = theory.to_dict()
        if state["vocab"] != self._registry.digest():
            raise StoreError("vocabulary does not match the store")
        for hypothesis in theory.hypotheses:
            if not _is_safe_id(hypothesis.hypothesis_id):
                raise StoreError(
                    f"hypothesis_id {hypothesis.hypothesis_id!r} cannot be a file name"
                )
            if not _is_safe_id(hypothesis.engine):
                raise StoreError(f"engine {hypothesis.engine!r} cannot be a file name")
        for scope in state["passes"]:
            engine, separator, oracle = scope.partition("|")
            if separator != "|" or oracle not in ORACLE_IDS or not _is_safe_id(engine):
                raise StoreError(f"passes scope {scope!r} cannot be a file name")
        return state

    def _write_live(self, theory: Theory, state: dict[str, Any], generation: int) -> None:
        hypothesis_dir = self._root / "hypotheses"
        ids = [hypothesis.hypothesis_id for hypothesis in theory.hypotheses]
        for hypothesis in theory.hypotheses:
            _write_text(
                hypothesis_dir / f"{hypothesis.hypothesis_id}.json",
                _json_text(hypothesis.to_dict()),
            )
        expected = {f"{hypothesis_id}.json" for hypothesis_id in ids}
        for path in hypothesis_dir.iterdir():
            if path.is_file() and path.suffix == ".json" and path.name not in expected:
                path.unlink()
        _write_text(self._root / "residual.json", _json_text(theory.residual.to_dict()))
        _write_text(self._root / "validity.json", _json_text(theory.validity.to_dict()))
        passes_dir = self._root / "passes"
        expected_passes: set[str] = set()
        for scope, rows in state["passes"].items():
            engine, _, oracle = scope.partition("|")
            name = f"{engine}__{oracle}.jsonl"
            expected_passes.add(name)
            _write_text(passes_dir / name, _jsonl_text(rows))
        for path in passes_dir.iterdir():
            if path.is_file() and path.suffix == ".jsonl" and path.name not in expected_passes:
                path.unlink()
        head = {
            "schema": 1,
            "vocab": state["vocab"],
            "generation": generation,
            "next_id": state["next_id"],
            "hypotheses": ids,
            "version": theory.version,
        }
        _write_text(self._root / "head.json", _json_text(head))

    def _read_hypotheses(self, expected: list[str]) -> dict[str, Any]:
        directory = self._root / "hypotheses"
        try:
            paths = [path for path in directory.iterdir() if path.is_file() and path.suffix == ".json"]
        except OSError as exc:
            raise StoreError(f"hypotheses: {exc}") from exc
        found = [path.stem for path in paths]
        if sorted(found) != sorted(expected):
            raise StoreError(f"hypotheses: files {sorted(found)} != head {list(expected)}")
        raw_by_id: dict[str, Any] = {}
        for hypothesis_id in expected:
            label = f"hypotheses/{hypothesis_id}.json"
            data = _read_json(directory / f"{hypothesis_id}.json", label)
            try:
                hypothesis = Hypothesis.from_dict(data)
            except ValueError as exc:
                raise StoreError(f"{label}: {exc}") from exc
            if hypothesis.hypothesis_id != hypothesis_id:
                raise StoreError(f"{label}: hypothesis_id is {hypothesis.hypothesis_id!r}")
            raw_by_id[hypothesis_id] = data
        return raw_by_id

    def _read_passes(self) -> dict[str, list[Any]]:
        directory = self._root / "passes"
        try:
            paths = sorted(
                path for path in directory.iterdir() if path.is_file() and path.suffix == ".jsonl"
            )
        except OSError as exc:
            raise StoreError(f"passes: {exc}") from exc
        digest = self._registry.digest()
        loaded: dict[str, list[Any]] = {}
        for path in paths:
            label = f"passes/{path.name}"
            parsed = _split_pass_name(path.name)
            if parsed is None:
                raise StoreError(f"{label}: expected <engine>__<oracle>.jsonl")
            engine, oracle = parsed
            scope = f"{engine}|{oracle}"
            if scope in loaded:
                raise StoreError(f"{label}: duplicate scope {scope}")
            seen: set[str] = set()
            rows: list[Any] = []
            for index, row in enumerate(_read_jsonl(path, label), start=1):
                line = f"{label}: line {index}"
                if not isinstance(row, dict) or set(row) != {"phi", "record_id"}:
                    raise StoreError(f"{line}: expected phi and record_id")
                record_id = row["record_id"]
                if not isinstance(record_id, str) or record_id == "":
                    raise StoreError(f"{line}: record_id must be a non-empty string")
                try:
                    phi = Phi.from_dict(row["phi"])
                except ValueError as exc:
                    raise StoreError(f"{line}: {exc}") from exc
                if phi.vocab != digest:
                    raise StoreError(f"{line}: vocabulary does not match")
                if phi.engine != engine:
                    raise StoreError(f"{line}: engine is {phi.engine!r}")
                token = _phi_token(phi)
                if token in seen:
                    raise StoreError(f"{line}: duplicate phi")
                seen.add(token)
                rows.append(row)
            if rows:
                loaded[scope] = rows
        return loaded

    def _read_model(self, filename: str, loader: Callable[[Any], Any]) -> Any:
        data = _read_json(self._root / filename, filename)
        try:
            loader(data)
        except ValueError as exc:
            raise StoreError(f"{filename}: {exc}") from exc
        return data

    def _journal_rows(self) -> list[dict[str, Any]]:
        rows = _read_jsonl(self._root / "journal.jsonl", "journal.jsonl")
        checked: list[dict[str, Any]] = []
        for index, row in enumerate(rows, start=1):
            seq = row.get("seq") if isinstance(row, dict) else None
            kind = row.get("kind") if isinstance(row, dict) else None
            if (
                not isinstance(row, dict)
                or not isinstance(kind, str)
                or isinstance(seq, bool)
                or seq != index
            ):
                raise StoreError(f"journal.jsonl: line {index} has seq {seq!r}")
            checked.append(row)
        return checked

    def _read_snapshot(self, generation: int) -> dict[str, Any]:
        label = f"generations/g{generation:06d}.json"
        path = self._root / "generations" / f"g{generation:06d}.json"
        if not path.is_file():
            raise StoreError(f"{label} does not exist")
        data = _read_json(path, label)
        if not isinstance(data, dict) or set(data) != _SNAPSHOT_KEYS:
            raise StoreError(f"{label}: expected keys {sorted(_SNAPSHOT_KEYS)}")
        if isinstance(data["schema"], bool) or data["schema"] != 1:
            raise StoreError(f"{label}: schema must be 1, got {data['schema']!r}")
        if isinstance(data["generation"], bool) or data["generation"] != generation:
            raise StoreError(f"{label}: generation is {data['generation']!r}")
        if not isinstance(data["cause"], str) or data["cause"] == "":
            raise StoreError(f"{label}: cause must be a non-empty string")
        journal_seq = data["journal_seq"]
        if isinstance(journal_seq, bool) or not isinstance(journal_seq, int) or journal_seq < 0:
            raise StoreError(f"{label}: journal_seq must be an integer >= 0, got {journal_seq!r}")
        if not isinstance(data["version"], str):
            raise StoreError(f"{label}: version must be a string, got {data['version']!r}")
        return data
