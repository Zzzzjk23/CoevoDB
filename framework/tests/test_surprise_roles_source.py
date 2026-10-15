"""Offline tests for the confined, read-only source reader."""

from __future__ import annotations

from pathlib import Path

import pytest

from surprise.gates import s09_cases as C
from surprise.roles import Hit, Snippet, SourceError, SourceReader, constants, open_sources, source_roots
from surprise.roles.constants import SOURCE_MAX_FILE_BYTES, SOURCE_ROOT_ENV


def _tree(root: Path) -> SourceReader:
    (root / "src" / "a").mkdir(parents=True)
    lines = [f"line {i} needle" if i == 7 else f"line {i}" for i in range(1, 11)]
    (root / "src" / "a" / "b.cpp").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / "src" / "c.rs").write_text("fn needle() {}\n", encoding="utf-8")
    (root / "src" / "notes.txt").write_text("needle in txt\n", encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".git" / "hidden.cpp").write_text("needle in git\n", encoding="utf-8")
    return SourceReader(root)


def test_source_reader_requires_an_existing_directory(tmp_path: Path) -> None:
    with pytest.raises(SourceError):
        SourceReader(tmp_path / "missing")
    (tmp_path / "a-file").write_text("x", encoding="utf-8")
    with pytest.raises(SourceError):
        SourceReader(tmp_path / "a-file")


def test_read_exact_lines_and_clip(tmp_path: Path) -> None:
    reader = _tree(tmp_path)
    snip = reader.read("src/a/b.cpp", 2, 4)
    assert (snip.path, snip.start, snip.end, snip.text) == (
        "src/a/b.cpp",
        2,
        4,
        "line 2\nline 3\nline 4",
    )
    assert isinstance(snip, Snippet)
    tail = reader.read("src/a/b.cpp", 9, 50)
    assert (tail.end, tail.text) == (10, "line 9\nline 10")
    whole = reader.read("src/a/b.cpp")
    assert whole.start == 1 and whole.end == 10
    one = reader.read("src/a/b.cpp", 7, 7)
    assert one.text == "line 7 needle"


def test_grep_path_order_suffixes_and_git_skip(tmp_path: Path) -> None:
    reader = _tree(tmp_path)
    hits = reader.grep("needle", under="src")
    assert [(h.path, h.line, h.text) for h in hits] == [
        ("src/a/b.cpp", 7, "line 7 needle"),
        ("src/c.rs", 1, "fn needle() {}"),
    ]
    assert all(isinstance(hit, Hit) for hit in hits)
    txt = reader.grep("needle", suffixes=[".txt"])
    assert [(h.path, h.line) for h in txt] == [("src/notes.txt", 1)]
    limited = reader.grep("needle", under="src", max_hits=1)
    assert len(limited) == 1 and limited[0].path == "src/a/b.cpp"
    none = reader.grep("needle", under="src/a", suffixes=[".rs"])
    assert none == ()


def test_exists_and_confinement(tmp_path: Path) -> None:
    reader = _tree(tmp_path)
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    outside.write_text("secret\n", encoding="utf-8")
    assert reader.exists("src/c.rs")
    assert not reader.exists("src/none.rs")
    assert not reader.exists("../" + outside.name)
    assert not reader.exists(str(outside))
    assert not reader.exists("src/../../" + outside.name)
    assert not reader.exists("src/a/b.cpp\x00")
    for bad in ("../" + outside.name, str(outside), "src/../../" + outside.name, "src/none.cpp", "src/a/b.cpp\x00"):
        with pytest.raises(SourceError) as info:
            reader.read(bad)
        assert isinstance(info.value, ValueError)
    with pytest.raises(SourceError):
        reader.read("src/a/b.cpp", 0, 3)
    with pytest.raises(SourceError):
        reader.read("src/a/b.cpp", 3, 2)
    with pytest.raises(SourceError):
        reader.grep("needle", under="../" + outside.name)
    assert outside.read_text(encoding="utf-8") == "secret\n"
    assert reader.root == tmp_path.resolve()


def test_read_rejects_oversize_and_directories(tmp_path: Path) -> None:
    reader = _tree(tmp_path)
    with pytest.raises(SourceError):
        reader.read("src")
    huge = tmp_path / "src" / "huge.cpp"
    huge.write_bytes(b"x" * (SOURCE_MAX_FILE_BYTES + 1))
    with pytest.raises(SourceError):
        reader.read("src/huge.cpp")
    assert reader.grep("x", under="src") == ()


def test_commit_detached_ref_and_packed(tmp_path: Path) -> None:
    sha = "d8cdaa33fda8df955cc76ef58a280f68f4cd43fa"
    other = "45d943dfb8699dc9cb9ef2320e955b73e3e6c03b"
    detached = tmp_path / "detached"
    detached.mkdir()
    (detached / ".git").mkdir()
    (detached / ".git" / "HEAD").write_text(sha + "\n", encoding="utf-8")
    assert SourceReader(detached).commit == sha
    named = tmp_path / "named"
    named.mkdir()
    (named / ".git" / "refs" / "heads").mkdir(parents=True)
    (named / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (named / ".git" / "refs" / "heads" / "main").write_text(other + "\n", encoding="utf-8")
    assert SourceReader(named).commit == other
    packed = tmp_path / "packed"
    packed.mkdir()
    (packed / ".git").mkdir()
    (packed / ".git" / "HEAD").write_text("ref: refs/heads/v1\n", encoding="utf-8")
    (packed / ".git" / "packed-refs").write_text(
        "# pack-refs with: peeled fully-peeled sorted\n"
        f"{sha} refs/heads/other\n"
        f"{other} refs/heads/v1\n",
        encoding="utf-8",
    )
    assert SourceReader(packed).commit == other
    empty = tmp_path / "empty"
    empty.mkdir()
    assert SourceReader(empty).commit is None


def test_source_roots_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SOURCE_ROOT_ENV, str(tmp_path))
    roots = source_roots()
    assert set(roots) == {"duckdb", "datafusion"}
    assert roots["duckdb"] == tmp_path / C.CONSTANTS["SOURCE_DIRS"]["duckdb"]
    assert roots["datafusion"] == tmp_path / C.CONSTANTS["SOURCE_DIRS"]["datafusion"]
    (tmp_path / "duckdb-v1.5.5").mkdir()
    (tmp_path / "datafusion-54.0.0").mkdir()
    readers = open_sources(verify=False)
    assert set(readers) == {"duckdb", "datafusion"}
    with pytest.raises(SourceError):
        open_sources(verify=True)


def test_open_sources_pinned_checkouts() -> None:
    readers = open_sources()
    assert set(readers) == {"duckdb", "datafusion"}
    for engine, reader in readers.items():
        assert reader.commit == C.CONSTANTS["SOURCE_COMMITS"][engine]
        assert reader.commit == constants.SOURCE_COMMITS[engine]
    assert readers["duckdb"].exists(C.DUCKDB_SOURCE_PATH)
    hits = readers["datafusion"].grep(C.DFA_SOURCE_MARK, under="datafusion/expr")
    assert C.DFA_SOURCE_MARK in "\n".join(hit.text for hit in hits)
    roots = source_roots()
    assert roots["duckdb"].name == "duckdb-v1.5.5"
    assert roots["datafusion"].name == "datafusion-54.0.0"
