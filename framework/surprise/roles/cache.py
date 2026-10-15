"""On-disk response cache keyed by prompt hash, model, and seed."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cache_key(prompt: str, model: str, seed: int) -> str:
    """Hex digest of ``sha256(prompt)``, the model name, and the seed."""
    return _sha256_text(f"{_sha256_text(prompt)}\n{model}\n{seed}")


class ResponseCache:
    """One JSON file per cache key, under ``<root>/<key[:2]>/<key>.json``."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        return self._root / key[:2] / f"{key}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        path = self.path(key)
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return None
        if not isinstance(entry, dict):
            return None
        try:
            if entry.get("key") != key:
                return None
            prompt = entry["prompt"]
            if _sha256_text(prompt) != entry.get("prompt_sha256"):
                return None
            if cache_key(prompt, entry["model"], entry["seed"]) != key:
                return None
        except (KeyError, TypeError, ValueError):
            return None
        return entry

    def put(self, entry: dict[str, Any]) -> None:
        key = entry["key"]
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(entry, ensure_ascii=False)
        handle, tmp = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(payload)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
