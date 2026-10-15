"""Read-only view of one run directory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from surprise.features.registry import Registry, default_registry
from surprise.harness.ledger import Ledger
from surprise.theory.workbench import Workbench

_UNOPENED = object()


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


class RunData:
    """One run's config, report, progress, ledger and, on demand, its theory.

    Opening a run does not create or rewrite any file in the directory.
    """

    def __init__(
        self,
        path: Path,
        config: dict[str, Any],
        report: dict[str, Any] | None,
        progress: list[dict[str, Any]],
        manifest: dict[str, Any],
        records: list[Any],
        kind: str,
        registry: Registry,
        run_id: str,
    ) -> None:
        self.path = path
        self.config = config
        self.report = report
        self.progress = progress
        self.manifest = manifest
        self.records = records
        self.kind = kind
        self.registry = registry
        self.run_id = run_id
        self._rows: dict[str, dict[str, Any]] = {}
        for row in progress:
            record_id = row.get("record_id") if isinstance(row, dict) else None
            if isinstance(record_id, str):
                self._rows[record_id] = row
        self._workbench: Any = _UNOPENED

    @classmethod
    def open(cls, path: str | Path) -> RunData:
        """Read ``path``. The ledger is closed before this returns."""
        root = Path(path)
        config = _object(root / "config.json")
        report_path = root / "report.json"
        report = _object(report_path) if report_path.is_file() else None
        progress = _lines(root / "progress.jsonl")
        ledger_path = root / "ledger.sqlite"
        if not ledger_path.is_file():
            raise FileNotFoundError(f"ledger not found: {ledger_path}")
        ledger = Ledger(ledger_path)
        try:
            run_ids = ledger.run_ids()
            if len(run_ids) != 1:
                raise ValueError(f"expected one run in the ledger, found {run_ids}")
            run_id = run_ids[0]
            records = sorted(ledger.records(run_id=run_id), key=lambda record: record.seq)
            manifest = ledger.run_manifest(run_id)
        finally:
            ledger.close()
        kind = "pure_llm" if manifest.get("baseline") == "pure_llm" else "surprise"
        vocabulary = config.get("vocabulary")
        if isinstance(vocabulary, str) and vocabulary != "":
            registry = Registry.load(vocabulary)
        else:
            registry = default_registry()
        return cls(root, config, report, progress, manifest, records, kind, registry, run_id)

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
