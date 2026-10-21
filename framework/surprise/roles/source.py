"""Read-only source reader confined to a root directory."""

from __future__ import annotations

import os
import re
import stat
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .constants import SOURCE_COMMITS, SOURCE_DIRS, SOURCE_MAX_FILE_BYTES, SOURCE_ROOT_ENV
from .sources_map import EXTRA_SOURCE_COMMITS, EXTRA_SOURCE_DIRS

_DEFAULT_SUFFIXES = (".cpp", ".hpp", ".h", ".c", ".rs")


class SourceError(ValueError):
    """A path or range the source reader will not serve."""


@dataclass(frozen=True)
class Snippet:
    path: str
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class Hit:
    path: str
    line: int
    text: str


def _rel_parts(path: str) -> list[str] | None:
    if "\x00" in path:
        return None
    candidate = Path(path)
    if candidate.is_absolute() or candidate.drive:
        return None
    parts: list[str] = []
    for part in path.replace("\\", "/").split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            return None
        parts.append(part)
    return parts


class SourceReader:
    """Serve files under ``root`` only. Never writes."""

    def __init__(self, root: Path | str) -> None:
        path = Path(root)
        if not path.is_dir():
            raise SourceError(f"source root is not a directory: {root}")
        self._root = path.resolve()

    @property
    def root(self) -> Path:
        return self._root

    @property
    def commit(self) -> str | None:
        return _commit_of(self._root)

    def exists(self, path: str) -> bool:
        resolved = self._resolve(path, strict=False)
        return resolved is not None and resolved.exists()

    def read(self, path: str, start: int = 1, end: int | None = None) -> Snippet:
        resolved = self._resolve(path, strict=True)
        if resolved is None:
            raise SourceError(f"path is outside the source root: {path!r}")
        try:
            info = resolved.stat()
        except OSError as exc:
            raise SourceError(f"cannot read {path!r}") from exc
        if not stat.S_ISREG(info.st_mode):
            raise SourceError(f"not a regular file: {path!r}")
        if info.st_size > SOURCE_MAX_FILE_BYTES:
            raise SourceError(f"file exceeds SOURCE_MAX_FILE_BYTES: {path!r}")
        if start < 1:
            raise SourceError("start line must be >= 1")
        if end is not None and end < start:
            raise SourceError("end line must be >= start")
        text = resolved.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        last = len(lines)
        actual_end = last if end is None or end > last else end
        if actual_end < start:
            raise SourceError("start line is past the end of the file")
        snippet = "\n".join(lines[start - 1 : actual_end])
        rel = resolved.relative_to(self._root).as_posix()
        return Snippet(path=rel, start=start, end=actual_end, text=snippet)

    def grep(
        self,
        pattern: str,
        *,
        under: str = "",
        suffixes: list[str] | tuple[str, ...] | None = None,
        max_hits: int = 50,
    ) -> tuple[Hit, ...]:
        compiled = re.compile(pattern)
        if under == "":
            base = self._root
        else:
            resolved = self._resolve(under, strict=True)
            if resolved is None or not resolved.is_dir():
                raise SourceError(f"grep under is not a directory inside the root: {under!r}")
            base = resolved
        allowed = _DEFAULT_SUFFIXES if suffixes is None else tuple(suffixes)
        files: list[tuple[str, Path]] = []
        for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
            dirnames[:] = [name for name in dirnames if name != ".git"]
            dirnames.sort()
            for name in filenames:
                full = Path(dirpath) / name
                try:
                    target = full.resolve()
                    target.relative_to(self._root)
                    info = target.stat()
                except (OSError, ValueError):
                    continue
                if not stat.S_ISREG(info.st_mode) or info.st_size > SOURCE_MAX_FILE_BYTES:
                    continue
                suffix = Path(name).suffix
                if suffix not in allowed:
                    continue
                rel = target.relative_to(self._root).as_posix()
                files.append((rel, target))
        files.sort(key=lambda item: item[0])
        hits: list[Hit] = []
        for rel, target in files:
            try:
                lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for index, line in enumerate(lines, start=1):
                if compiled.search(line):
                    hits.append(Hit(path=rel, line=index, text=line))
                    if len(hits) >= max_hits:
                        return tuple(hits)
        return tuple(hits)

    def _resolve(self, path: str, *, strict: bool) -> Path | None:
        parts = _rel_parts(path)
        if parts is None:
            if strict:
                raise SourceError(f"path is not a confined relative path: {path!r}")
            return None
        candidate = self._root.joinpath(*parts) if parts else self._root
        try:
            resolved = candidate.resolve()
            resolved.relative_to(self._root)
        except (OSError, ValueError, RuntimeError):
            if strict:
                raise SourceError(f"path is outside the source root: {path!r}")
            return None
        return resolved


def source_roots() -> dict[str, Path]:
    override = os.environ.get(SOURCE_ROOT_ENV)
    parent = Path(override) if override else _default_source_parent()
    return {engine: parent / directory for engine, directory in SOURCE_DIRS.items()}


def open_sources(*, verify: bool = True) -> dict[str, SourceReader]:
    readers: dict[str, SourceReader] = {}
    for engine, root in source_roots().items():
        if not root.is_dir():
            raise SourceError(f"missing source checkout for {engine}: {root}")
        reader = SourceReader(root)
        if verify:
            commit = reader.commit
            expected = SOURCE_COMMITS[engine]
            if commit != expected:
                raise SourceError(
                    f"{engine} checkout commit {commit!r} does not match {expected!r}"
                )
        readers[engine] = reader
    return readers


def open_extra_sources(engines: Iterable[str], *, verify: bool = True) -> dict[str, SourceReader]:
    """Open requested optional checkouts; their absence never blocks other engines."""
    requested = set(engines) & EXTRA_SOURCE_DIRS.keys()
    if not requested:
        return {}
    override = os.environ.get(SOURCE_ROOT_ENV)
    parent = Path(override) if override else _default_source_parent()
    readers: dict[str, SourceReader] = {}
    for engine, directory in EXTRA_SOURCE_DIRS.items():
        if engine not in requested:
            continue
        try:
            reader = SourceReader(parent / directory)
            if verify and reader.commit != EXTRA_SOURCE_COMMITS[engine]:
                raise SourceError("commit mismatch")
        except SourceError:
            print(f"optional source checkout unavailable for {engine}: missing directory or commit mismatch", file=sys.stderr)
            continue
        readers[engine] = reader
    return readers


def readers_for(engines: Iterable[str]) -> dict[str, SourceReader]:
    """Keep the legacy readers and add only the requested optional engines."""
    try:
        readers = open_sources()
    except SourceError:
        readers = {}
    readers.update(open_extra_sources(engines))
    return readers


def _default_source_parent() -> Path:
    framework = Path(__file__).resolve().parents[2]
    checkout = framework.parent
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=str(framework),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=60,
            check=False,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return checkout / ".src"
    common = proc.stdout.strip()
    if proc.returncode == 0 and common:
        return Path(common).parent / ".src"
    return checkout / ".src"


def _commit_of(root: Path) -> str | None:
    git_dir = root / ".git"
    head_file = git_dir / "HEAD"
    if not head_file.is_file():
        return None
    try:
        head = head_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if _is_sha(head):
        return head
    if head.startswith("ref:"):
        ref = head[4:].strip()
        ref_file = git_dir / ref
        if ref_file.is_file():
            try:
                value = ref_file.read_text(encoding="utf-8").strip()
            except OSError:
                value = ""
            if _is_sha(value):
                return value
        packed = git_dir / "packed-refs"
        if packed.is_file():
            try:
                for line in packed.read_text(encoding="utf-8").splitlines():
                    if not line or line.startswith("#") or line.startswith("^"):
                        continue
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] == ref and _is_sha(parts[0]):
                        return parts[0]
            except OSError:
                return None
    return None


def _is_sha(value: str) -> bool:
    if len(value) != 40:
        return False
    hexdigits = "0123456789abcdefABCDEF"
    return all(char in hexdigits for char in value)
