"""Archive integrity, bounded reads and verify-before-delete grid pruning."""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from surprise.experiments import archive

FRAMEWORK = Path(__file__).resolve().parents[1]


def _write(root: Path, name: str, data: bytes = b"{}\n") -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _files(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def _directories(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_dir()}


def _manifest(dest: Path) -> dict:
    return json.loads(Path(str(dest) + ".json").read_text(encoding="utf-8"))


def _save_manifest(dest: Path, manifest: dict) -> None:
    Path(str(dest) + ".json").write_text(json.dumps(manifest), encoding="utf-8")


@pytest.fixture
def grid(tmp_path: Path) -> Path:
    root = tmp_path / "grid"
    for name in ("grid.json", "report/report.json", "report/nested/ledger.sqlite", "extra.txt", "misc/raw.bin"):
        _write(root, name)
    (root / "report/empty").mkdir()
    for arm in ("a", "b"):
        for cell in ("s1-r0", "s2-r0"):
            base = f"cells/{arm}/{cell}"
            for name in ("cell.json", "config.json", "report.json", "error.txt", "theory/head.json",
                         "progress.jsonl", "llm/calls.jsonl", "sqlancer/log.txt"):
                _write(root, f"{base}/{name}", f"{base}/{name}\n".encode())
            _write(root, f"{base}/ledger.sqlite", bytes(range(256)) * 65)
            (root / base / "empty").mkdir()
            _write(root, f"cells/{arm}/{cell}.log", b"log\n")
            _write(root, f"cells/{arm}/{cell}.bootstrap.json")
            _write(root, f"cells/{arm}/{cell}.stale-1/cell.json")
            _write(root, f"cells/{arm}/{cell}.stale-1/theory/head.json")
    return root


def _pack(root: Path, tmp_path: Path) -> Path:
    dest = tmp_path / "grid.tar.gz"
    assert archive.main(["pack", str(root), "--dest", str(dest)]) == 0
    return dest


def test_pack_manifest_order_and_round_trip(grid: Path, tmp_path: Path) -> None:
    before = _files(grid)
    directories = _directories(grid)
    dest = _pack(grid, tmp_path)
    manifest = _manifest(dest)
    assert manifest == {
        "schema": 1, "root": "grid",
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in before.items()},
        "tar_sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
    }
    with tarfile.open(dest) as packed:
        members = packed.getmembers()
        assert all(member.isfile() or member.isdir() for member in members)
        assert [member.name for member in members] == ["grid"] + [
            f"grid/{name}" for name in sorted(set(before) | directories)
        ]
        unpacked = tmp_path / "unpacked"
        packed.extractall(unpacked, filter="data")
    assert _files(unpacked / "grid") == before
    assert _directories(unpacked / "grid") == directories
    assert archive.main(["verify", str(dest)]) == 0
    assert archive.main(["verify", str(dest), "--against", str(grid)]) == 0


def test_prune_keeps_exact_summaries_and_reports(grid: Path, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    before = _files(grid)
    dest = _pack(grid, tmp_path)
    expected = {"grid.json", "report/report.json", "report/nested/ledger.sqlite"}
    for arm in ("a", "b"):
        for cell in ("s1-r0", "s2-r0"):
            expected.update(f"cells/{arm}/{cell}/{name}" for name in ("cell.json", "config.json", "report.json", "error.txt"))
    capsys.readouterr()
    assert archive.main(["prune", str(grid), "--archive", str(dest)]) == 0
    freed = sum(len(value) for name, value in before.items() if name not in expected)
    assert capsys.readouterr().out == f"Pruned {len(before) - len(expected)} files; freed {freed} bytes\n"
    assert _files(grid) == {name: before[name] for name in expected}
    assert _directories(grid) == {
        "report", "report/nested", "report/empty", "cells", "cells/a", "cells/b",
        "cells/a/s1-r0", "cells/a/s2-r0", "cells/b/s1-r0", "cells/b/s2-r0",
    }
    assert archive.main(["verify", str(dest), "--against", str(grid)]) == 0
    assert archive.main(["prune", str(grid), "--archive", str(dest)]) == 0
    assert _files(grid) == {name: before[name] for name in expected}


@pytest.mark.parametrize("change", ["changed", "added"])
def test_prune_mismatch_deletes_nothing(grid: Path, tmp_path: Path, change: str) -> None:
    dest = _pack(grid, tmp_path)
    if change == "changed":
        ledger = grid / "cells/a/s1-r0/ledger.sqlite"
        data = bytearray(ledger.read_bytes())
        data[5] ^= 1
        ledger.write_bytes(data)
    else:
        _write(grid, "cells/b/s2-r0/new.txt", b"not archived")
    before, directories = _files(grid), _directories(grid)
    assert archive.main(["verify", str(dest), "--against", str(grid)]) == 1
    assert archive.main(["prune", str(grid), "--archive", str(dest)]) == 1
    assert _files(grid) == before
    assert _directories(grid) == directories


def test_corrupt_archive_refuses_verify_and_prune(grid: Path, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    dest = _pack(grid, tmp_path)
    data = bytearray(dest.read_bytes())
    data[len(data) // 2] ^= 1
    dest.write_bytes(data)
    before, directories = _files(grid), _directories(grid)
    assert archive.main(["verify", str(dest)]) == 1
    assert "archive SHA-256 mismatch" in capsys.readouterr().err
    assert archive.main(["prune", str(grid), "--archive", str(dest)]) == 1
    assert _files(grid) == before
    assert _directories(grid) == directories


@pytest.mark.parametrize("fault", ["content", "missing", "extra", "duplicate", "symlink", "hardlink", "traversal", "wrong-root"])
def test_archive_members_are_checked_independently_of_tar_hash(grid: Path, tmp_path: Path, fault: str) -> None:
    dest = _pack(grid, tmp_path)
    before, directories = _files(grid), _directories(grid)
    manifest = _manifest(dest)
    # Recompute the outer checksum after tampering, forcing member-level checks.
    with tarfile.open(dest, "w:gz") as packed:
        root = tarfile.TarInfo("grid")
        root.type = tarfile.DIRTYPE
        packed.addfile(root)
        for name, value in before.items():
            if name == "grid.json":
                if fault == "missing":
                    continue
                if fault == "content":
                    value = b"XX\n"
            member = tarfile.TarInfo(f"grid/{name}")
            member.size = len(value)
            packed.addfile(member, io.BytesIO(value))
        if fault in {"extra", "duplicate", "symlink", "hardlink", "traversal", "wrong-root"}:
            name = {"duplicate": "grid/grid.json", "traversal": "grid/../escape", "wrong-root": "other/file"}.get(fault, "grid/extra")
            member = tarfile.TarInfo(name)
            if fault in {"symlink", "hardlink"}:
                member.type = tarfile.SYMTYPE if fault == "symlink" else tarfile.LNKTYPE
                member.linkname = "grid/grid.json"
            packed.addfile(member)
    manifest["tar_sha256"] = hashlib.sha256(dest.read_bytes()).hexdigest()
    _save_manifest(dest, manifest)
    assert archive.main(["verify", str(dest)]) == 1
    assert archive.main(["prune", str(grid), "--archive", str(dest)]) == 1
    assert _files(grid) == before
    assert _directories(grid) == directories


@pytest.mark.parametrize("fault", ["missing", "json", "schema", "files", "root", "digest", "duplicate-key"])
def test_invalid_manifest_refuses_without_deleting(grid: Path, tmp_path: Path, fault: str) -> None:
    dest = _pack(grid, tmp_path)
    manifest = _manifest(dest)
    sidecar = Path(str(dest) + ".json")
    if fault == "missing":
        sidecar.unlink()
    elif fault == "json":
        sidecar.write_text("{", encoding="utf-8")
    elif fault == "duplicate-key":
        sidecar.write_text(json.dumps(manifest)[:-1] + ', "schema": 1}', encoding="utf-8")
    else:
        key, value = {"schema": ("schema", True), "files": ("files", []),
                      "root": ("root", "../grid"), "digest": ("tar_sha256", "bad")}[fault]
        manifest[key] = value
        _save_manifest(dest, manifest)
    before, directories = _files(grid), _directories(grid)
    assert archive.main(["prune", str(grid), "--archive", str(dest)]) == 1
    assert _files(grid) == before
    assert _directories(grid) == directories


def test_existing_outputs_and_internal_destination_are_refused(grid: Path, tmp_path: Path) -> None:
    dest = _pack(grid, tmp_path)
    original, sidecar = dest.read_bytes(), Path(str(dest) + ".json").read_bytes()
    assert archive.main(["pack", str(grid), "--dest", str(dest)]) == 1
    assert dest.read_bytes() == original
    assert Path(str(dest) + ".json").read_bytes() == sidecar
    dest.unlink()
    assert archive.main(["pack", str(grid), "--dest", str(dest)]) == 1
    assert not dest.exists()
    assert Path(str(dest) + ".json").read_bytes() == sidecar
    inside = grid / "nested.tar.gz"
    assert archive.main(["pack", str(grid), "--dest", str(inside)]) == 1
    assert not inside.exists()
    assert not Path(str(inside) + ".json").exists()


@pytest.mark.parametrize("target_kind", ["file", "directory", "dangling"])
def test_symbolic_links_refuse_pack_and_prune_if_supported(grid: Path, tmp_path: Path, target_kind: str) -> None:
    dest = _pack(grid, tmp_path)
    link = grid / "link"
    target = {"file": grid / "grid.json", "directory": grid / "report", "dangling": tmp_path / "absent"}[target_kind]
    created = False
    try:
        os.symlink(target, link, target_is_directory=target_kind == "directory")
        created = True
    except OSError:
        # Windows may not grant symlink creation. The remaining test still runs.
        pass
    if created:
        other = tmp_path / "linked.tar.gz"
        assert archive.main(["pack", str(grid), "--dest", str(other)]) == 1
        assert not other.exists()
        assert not Path(str(other) + ".json").exists()
        before = (grid / "cells/a/s1-r0/ledger.sqlite").read_bytes()
        assert archive.main(["verify", str(dest), "--against", str(grid)]) == 1
        assert archive.main(["prune", str(grid), "--archive", str(dest)]) == 1
        assert (grid / "cells/a/s1-r0/ledger.sqlite").read_bytes() == before
        assert link.is_symlink()
        link.unlink()
    assert archive.main(["verify", str(dest), "--against", str(grid)]) == 0


def test_large_file_reads_are_bounded(grid: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    large = grid / "cells/a/s1-r0/ledger.sqlite"
    with large.open("wb") as stream:
        for _ in range(49):
            stream.write(bytes(range(256)) * 256)
    original_open = Path.open
    reads = []

    class BoundedReader:
        def __init__(self, stream):
            self.stream = stream

        def read(self, size=-1):
            assert 0 < size <= 1024 * 1024, f"unbounded binary read: {size}"
            reads.append(size)
            return self.stream.read(size)

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

    def bounded_open(path, mode="r", *args, **kwargs):
        stream = original_open(path, mode, *args, **kwargs)
        return BoundedReader(stream) if mode == "rb" else stream

    monkeypatch.setattr(Path, "open", bounded_open)
    dest = _pack(grid, tmp_path)
    assert archive.main(["verify", str(dest), "--against", str(grid)]) == 0
    assert len(reads) > 49


def test_failed_pack_removes_only_its_partial_outputs(grid: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dest = tmp_path / "failed.tar.gz"
    before = _files(grid)

    def fail(*args, **kwargs):
        raise OSError("simulated write failure")

    monkeypatch.setattr(tarfile.TarFile, "addfile", fail)
    assert archive.main(["pack", str(grid), "--dest", str(dest)]) == 1
    assert not dest.exists()
    assert not Path(str(dest) + ".json").exists()
    assert _files(grid) == before


def test_cli_help_exit_codes_and_commands(grid: Path, tmp_path: Path) -> None:
    def run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-m", "surprise.experiments.archive", *args],
                              cwd=FRAMEWORK, capture_output=True, text=True, timeout=10)

    assert run("--help").returncode == 0
    for args in ((), ("pack", str(grid)), ("verify",), ("prune", str(grid)), ("unknown",)):
        result = run(*args)
        assert result.returncode == 2
        assert "usage:" in result.stderr
    dest = tmp_path / "cli.tar.gz"
    assert run("pack", str(grid), "--dest", str(dest)).returncode == 0
    assert run("verify", str(dest), "--against", str(grid)).returncode == 0
    assert run("prune", str(grid), "--archive", str(dest)).returncode == 0
    assert run("verify", str(tmp_path / "absent.tar.gz")).returncode == 1
