"""Read-only view of one run directory."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from surprise.features.registry import Registry, default_registry
from surprise.harness.contracts import ExperimentRecord
from surprise.theory.workbench import Workbench

_UNOPENED = object()

# Metric scans can omit result bags; a single detail in the S8 ledger is 483 MB.
# The ordinary iterator always returns the complete record.
_SLIM_ABOVE = 32 * 1024 * 1024
_CHUNK = 1024 * 1024
_JSON_TOKENS = re.compile(rb'["\\{}\[\]:,]')
_DETAIL_TOKENS = re.compile(rb'["\\{}]')

_FULL_SQL = (
    "SELECT records.record_json FROM records "
    "JOIN runs ON runs.run_id = records.run_id "
    "WHERE records.run_id = ? "
    "ORDER BY runs.created_order, records.seq"
)
_ROWIDS_SQL = (
    "SELECT records.rowid FROM records "
    "JOIN runs ON runs.run_id = records.run_id "
    "WHERE records.run_id = ? "
    "ORDER BY runs.created_order, records.seq"
)
_COUNT_SQL = "SELECT COUNT(*) FROM records WHERE run_id = ?"
_RUNS_SQL = "SELECT run_id FROM runs ORDER BY created_order"
_MANIFEST_SQL = "SELECT manifest_json FROM runs WHERE run_id = ?"


def _lines(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name}: expected a JSON object")
    return payload


def _kind(manifest: dict[str, Any]) -> str:
    baseline = manifest.get("baseline")
    if baseline == "pure_llm":
        return "pure_llm"
    if baseline == "sqlancer":
        return "sqlancer"
    return "surprise"


def _ro_connect(path: Path) -> sqlite3.Connection:
    """Open ``ledger.sqlite`` read-only. The file must already exist."""
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=30.0)
    conn.execute("PRAGMA query_only = ON")
    return conn


def _ledger_meta(path: Path) -> tuple[str, dict[str, Any], int]:
    conn = _ro_connect(path)
    try:
        run_ids = [row[0] for row in conn.execute(_RUNS_SQL)]
        if len(run_ids) != 1:
            raise ValueError(f"expected one run in the ledger, found {run_ids}")
        run_id = run_ids[0]
        row = conn.execute(_MANIFEST_SQL, (run_id,)).fetchone()
        manifest = json.loads(row[0])
        if not isinstance(manifest, dict):
            raise ValueError(f"run manifest is not a JSON object: {run_id!r}")
        count = int(conn.execute(_COUNT_SQL, (run_id,)).fetchone()[0])
        return run_id, manifest, count
    finally:
        conn.close()


def _read_range(blob: sqlite3.Blob, start: int, stop: int) -> bytes:
    resume = blob.tell()
    try:
        blob.seek(start)
        return blob.read(stop - start)
    finally:
        blob.seek(resume)


def _detail_bounds(blob: sqlite3.Blob) -> tuple[int, int] | None:
    """Locate the label.detail object without loading it into memory.

    Scan JSON punctuation in bounded byte chunks, tracking strings, escapes and
    nesting. Only object keys at the root and inside label are decoded. This
    does not depend on key order, whitespace, detail size or fixed head/tail
    lengths. The ledger has already validated the record when appending it.
    """
    stack: list[int] = []
    keys: dict[int, str] = {}
    want_key: dict[int, bool] = {}
    label_depth: int | None = None
    in_string = False
    escaped_at = -1
    key_start: int | None = None
    detail_start: int | None = None
    detail_depth = 0
    offset = 0
    while chunk := blob.read(_CHUNK):
        index = 0
        while True:
            tokens = _DETAIL_TOKENS if detail_start is not None else _JSON_TOKENS
            match = tokens.search(chunk, index)
            if match is None:
                break
            index = match.end()
            pos = offset + match.start()
            char = chunk[match.start()]
            if in_string:
                if pos == escaped_at:
                    continue
                if char == 92:  # backslash
                    escaped_at = pos + 1
                elif char == 34:  # quote
                    in_string = False
                    if key_start is not None:
                        keys[len(stack)] = json.loads(_read_range(blob, key_start, pos + 1))
                        key_start = None
                continue
            if char == 34:
                in_string = True
                depth = len(stack)
                if detail_start is None and want_key.get(depth) and (
                    depth == 1 or depth == label_depth
                ):
                    key_start = pos
                continue
            if detail_start is not None:
                if char == 123:
                    detail_depth += 1
                elif char == 125:
                    detail_depth -= 1
                    if detail_depth == 0:
                        return detail_start, pos + 1
                continue
            depth = len(stack)
            if char in (123, 91):  # object or array
                if char == 123 and depth == label_depth and keys.get(depth) == "detail":
                    detail_start, detail_depth = pos, 1
                    continue
                if char == 123 and depth == 1 and keys.get(depth) == "label":
                    label_depth = depth + 1
                stack.append(char)
                want_key[len(stack)] = char == 123
                keys.pop(len(stack), None)
            elif char in (125, 93):
                stack.pop()
                if label_depth is not None and len(stack) < label_depth:
                    label_depth = None
            elif char == 58:
                want_key[depth] = False
            elif char == 44:
                want_key[depth] = bool(stack and stack[-1] == 123)
                keys.pop(depth, None)
        offset += len(chunk)
    return None


def _metric_record(conn: sqlite3.Connection, rowid: int) -> ExperimentRecord:
    with conn.blobopen("records", "record_json", rowid, readonly=True) as blob:
        bounds = _detail_bounds(blob) if len(blob) > _SLIM_ABOVE else None
        if bounds is None:
            blob.seek(0)
            body = blob.read()
        else:
            start, stop = bounds
            body = _read_range(blob, 0, start) + b"{}" + _read_range(blob, stop, len(blob))
    return ExperimentRecord.from_json(body.decode("utf-8"))


class RunData:
    """One run's config, report, progress, ledger and, on demand, its theory.

    Opening a run does not create or rewrite any file in the directory, and
    does not read the ledger rows. ``iter_records`` yields them one at a time.
    ``records`` materialises that stream on first access.
    """

    def __init__(
        self,
        path: Path,
        config: dict[str, Any],
        report: dict[str, Any] | None,
        progress: list[dict[str, Any]],
        manifest: dict[str, Any],
        record_count: int,
        kind: str,
        registry: Registry,
        run_id: str,
    ) -> None:
        self.path = path
        self.config = config
        self.report = report
        self.progress = progress
        self.manifest = manifest
        self.record_count = record_count
        self.kind = kind
        self.registry = registry
        self.run_id = run_id
        self._materialized: list[Any] | None = None
        self._rows: dict[str, dict[str, Any]] = {}
        for row in progress:
            record_id = row.get("record_id") if isinstance(row, dict) else None
            if isinstance(record_id, str):
                self._rows[record_id] = row
        self._workbench: Any = _UNOPENED

    @classmethod
    def open(cls, path: str | Path) -> RunData:
        """Read ``path``. The ledger is closed before this returns.

        Record bodies stay on disk. ``record_count`` is ``SELECT COUNT(*)``.
        """
        root = Path(path)
        config = _object(root / "config.json")
        report_path = root / "report.json"
        report = _object(report_path) if report_path.is_file() else None
        progress = _lines(root / "progress.jsonl")
        ledger_path = root / "ledger.sqlite"
        if not ledger_path.is_file():
            raise FileNotFoundError(f"ledger not found: {ledger_path}")
        run_id, manifest, record_count = _ledger_meta(ledger_path)
        vocabulary = config.get("vocabulary")
        if isinstance(vocabulary, str) and vocabulary != "":
            registry = Registry.load(vocabulary)
        else:
            registry = default_registry()
        return cls(
            root,
            config,
            report,
            progress,
            manifest,
            record_count,
            _kind(manifest),
            registry,
            run_id,
        )

    def iter_records(self, *, keep_detail: bool = True) -> Iterator[ExperimentRecord]:
        """Yield ledger rows in ``seq`` order, one ``ExperimentRecord`` at a time.

        The filter and order match ``Ledger.records(run_id=...)``. The connection
        is read-only and closed when the iterator finishes. ``keep_detail`` is
        false for metric scans: a row larger than ``_SLIM_ABOVE`` is parsed with
        ``label.detail`` replaced by ``{}`` so the result bags never enter Python.
        """
        conn = _ro_connect(self.path / "ledger.sqlite")
        try:
            if keep_detail:
                cursor = conn.execute(_FULL_SQL, (self.run_id,))
                for (body,) in cursor:
                    record = ExperimentRecord.from_json(body)
                    del body
                    yield record
                    del record
                return
            cursor = conn.execute(_ROWIDS_SQL, (self.run_id,))
            for (rowid,) in cursor:
                yield _metric_record(conn, rowid)
        finally:
            conn.close()

    @property
    def records(self) -> list[Any]:
        """Every record, in ``seq`` order. The list is built on first access."""
        if self._materialized is None:
            self._materialized = list(self.iter_records())
        return self._materialized

    def workbench(self) -> Workbench | None:
        """The run's theory, opened once with this run's vocabulary. Missing is ``None``."""
        if self._workbench is not _UNOPENED:
            return self._workbench
        theory = self.path / "theory"
        if not (theory / "head.json").is_file():
            self._workbench = None
            return None
        self._workbench = Workbench.open(theory, registry=self.registry)
        return self._workbench

    def book(self, name: str) -> list[dict[str, Any]]:
        """Lines of ``llm/<name>.jsonl``. A missing file is an empty list."""
        return _lines(self.path / "llm" / f"{name}.jsonl")

    def row(self, record_id: str) -> dict[str, Any] | None:
        """The progress line of ``record_id``, or ``None`` when it was not written."""
        return self._rows.get(record_id)
