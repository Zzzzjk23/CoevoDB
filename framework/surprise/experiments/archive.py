"""Pack, verify and prune experiment grids without loading large files into memory.

    python -m surprise.experiments.archive pack OUT --dest FILE
    python -m surprise.experiments.archive verify FILE [--against OUT]
    python -m surprise.experiments.archive prune OUT --archive FILE

An archive travels with its ``FILE.json`` SHA-256 manifest. Stop the grid before
packing or pruning: verification and deletion require an unchanged directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
import tarfile
import zlib
from pathlib import Path, PurePosixPath
from typing import BinaryIO

_BLOCK_BYTES = 1024 * 1024
_SUMMARIES = {"cell.json", "config.json", "report.json", "error.txt"}


def _sha256(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    while block := stream.read(_BLOCK_BYTES):
        digest.update(block)
    return digest.hexdigest()


def _file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return _sha256(stream)


def _kind(path: Path) -> bool:
    """Return whether a path is a directory; reject links and special files."""
    mode = path.lstat().st_mode
    if stat.S_ISLNK(mode) or path.is_junction():
        raise ValueError(f"symbolic link or junction is not allowed: {path}")
    if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
        raise ValueError(f"not a regular file or directory: {path}")
    return stat.S_ISDIR(mode)


def _directory(path: Path) -> Path:
    if not _kind(path):
        raise ValueError(f"not a directory: {path}")
    root = path.resolve(strict=True)
    if not root.name:
        raise ValueError("a filesystem root cannot be a grid directory")
    return root


def _entries(root: Path) -> list[Path]:
    """Inventory the tree without following symbolic links or Windows junctions."""
    entries = []
    pending = [root]
    while pending:
        for path in pending.pop().iterdir():
            if _kind(path):
                pending.append(path)
            entries.append(path)
    return sorted(entries, key=lambda path: path.relative_to(root).as_posix())


def _sidecar(archive: Path) -> Path:
    return Path(str(archive) + ".json")


def _refuse_existing(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError(f"already exists: {path}")


class _HashingReader:
    """Hash exactly the bytes tarfile copies, including for multi-GB ledgers."""

    def __init__(self, stream: BinaryIO):
        self.stream = stream
        self.digest = hashlib.sha256()

    def read(self, size: int) -> bytes:
        block = self.stream.read(size)
        self.digest.update(block)
        return block


def pack(out: Path, dest: Path) -> None:
    root = _directory(out)
    manifest_path = _sidecar(dest)
    if dest.resolve().is_relative_to(root):
        raise ValueError(f"archive destination is inside the grid: {dest}")
    _refuse_existing(dest)
    _refuse_existing(manifest_path)
    entries = _entries(root)  # Reject every link before creating either output.
    files = {}
    made_archive = made_manifest = complete = False
    try:
        with dest.open("xb") as output:
            made_archive = True
            # Store hard-linked regular files independently; never emit tar links.
            with tarfile.open(fileobj=output, mode="w:gz", dereference=True) as archive:
                for path in [root, *entries]:
                    is_directory = _kind(path)
                    relative = path.relative_to(root).as_posix()
                    name = root.name if path == root else f"{root.name}/{relative}"
                    info = archive.gettarinfo(str(path), arcname=name)
                    if is_directory:
                        archive.addfile(info)
                    else:
                        with path.open("rb") as stream:
                            reader = _HashingReader(stream)
                            archive.addfile(info, reader)
                            files[relative] = reader.digest.hexdigest()
        manifest = {"schema": 1, "root": root.name, "files": files, "tar_sha256": _file_hash(dest)}
        with manifest_path.open("x", encoding="utf-8", newline="\n") as stream:
            made_manifest = True
            json.dump(manifest, stream, ensure_ascii=True, indent=2)
            stream.write("\n")
        complete = True
    finally:
        if not complete:
            if made_manifest:
                manifest_path.unlink(missing_ok=True)
            if made_archive:
                dest.unlink(missing_ok=True)
    print(f"Packed {len(files)} files: {dest}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate manifest key: {key!r}")
        result[key] = value
    return result


def _relative_name(name: object) -> bool:
    return (isinstance(name, str) and bool(name) and "\\" not in name
            and "\0" not in name and not PurePosixPath(name).is_absolute()
            and PurePosixPath(name).as_posix() == name
            and ".." not in PurePosixPath(name).parts and name != ".")


def _digest(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def _manifest(archive: Path) -> dict:
    manifest = json.loads(_sidecar(archive).read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    if not isinstance(manifest, dict) or type(manifest.get("schema")) is not int or manifest["schema"] != 1:
        raise ValueError("manifest schema must be 1")
    root = manifest.get("root")
    if not _relative_name(root) or "/" in root:
        raise ValueError("manifest root must be a directory name")
    files = manifest.get("files")
    if not isinstance(files, dict) or not all(_relative_name(name) and _digest(value) for name, value in files.items()):
        raise ValueError("manifest files must map relative POSIX paths to SHA-256 hashes")
    if not _digest(manifest.get("tar_sha256")):
        raise ValueError("manifest tar_sha256 must be a SHA-256 hash")
    return manifest


def verify(file: Path, against: Path | None = None) -> list[Path]:
    """Verify the archive and optionally return a verified local tree inventory.

    The local files may be a subset of the manifest, so a pruned grid can still
    be checked. Unexpected, changed or linked local entries always fail.
    """
    manifest = _manifest(file)
    if _file_hash(file) != manifest["tar_sha256"]:
        raise ValueError("archive SHA-256 mismatch")
    root = manifest["root"]
    files = manifest["files"]
    seen = set()
    found = set()
    with tarfile.open(file, mode="r|gz") as archive:
        for member in archive:
            name = member.name
            if not _relative_name(name) or not (name == root or name.startswith(root + "/")):
                raise ValueError(f"archive member has an invalid root or path: {name!r}")
            if name in seen:
                raise ValueError(f"duplicate archive member: {name!r}")
            seen.add(name)
            if member.isdir():
                if name != root and name[len(root) + 1:] in files:
                    raise ValueError(f"manifest file is an archive directory: {name!r}")
                continue
            if not member.isreg() or name == root:
                raise ValueError(f"archive member is not a regular file or directory: {name!r}")
            relative = name[len(root) + 1:]
            if relative not in files:
                raise ValueError(f"unexpected archive file: {relative}")
            with archive.extractfile(member) as stream:
                if _sha256(stream) != files[relative]:
                    raise ValueError(f"archive member SHA-256 mismatch: {relative}")
            found.add(relative)
    if root not in seen:
        raise ValueError("archive has no root directory")
    missing = files.keys() - found
    if missing:
        raise ValueError(f"archive is missing manifest files: {sorted(missing)[:5]}")
    entries = []
    if against is not None:
        directory = _directory(against)
        entries = _entries(directory)
        for path in entries:
            if not _kind(path):
                relative = path.relative_to(directory).as_posix()
                if relative not in files:
                    raise ValueError(f"local file is not in the manifest: {relative}")
                if _file_hash(path) != files[relative]:
                    raise ValueError(f"local file SHA-256 mismatch: {relative}")
    return entries


def _keep(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts
    directory = _kind(path)
    if parts[0] == "report" and (root / "report").is_dir():
        return True
    if parts == ("grid.json",):
        return not directory
    if parts[0] != "cells":
        return False
    if len(parts) >= 3:
        _, marker, suffix = parts[2].rpartition(".stale-")
        if marker and suffix.isdigit():
            return False
    return (directory and len(parts) <= 3) or (not directory and len(parts) == 4 and parts[3] in _SUMMARIES)


def prune(out: Path, file: Path) -> None:
    root = _directory(out)
    if file.resolve().is_relative_to(root):
        raise ValueError("the archive must be outside the grid before pruning")
    entries = verify(file, against=root)
    # Every target comes from the checked, resolved root. Plan and count before
    # deleting anything; remove directories bottom-up without recursive traversal.
    drops = [path for path in entries if not _keep(path, root)]
    sizes = {path: path.stat().st_size for path in drops if not _kind(path)}
    for path in sorted(drops, key=lambda path: len(path.relative_to(root).parts), reverse=True):
        if path in sizes:
            path.unlink()
        else:
            path.rmdir()
    print(f"Pruned {len(sizes)} files; freed {sum(sizes.values())} bytes")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pack, verify or prune an experiment grid")
    commands = parser.add_subparsers(dest="command", required=True)
    packing = commands.add_parser("pack", help="archive an entire grid with a SHA-256 manifest")
    packing.add_argument("out", type=Path, metavar="OUT")
    packing.add_argument("--dest", type=Path, required=True, metavar="FILE")
    checking = commands.add_parser("verify", help="verify an archive and optionally the local grid")
    checking.add_argument("file", type=Path, metavar="FILE")
    checking.add_argument("--against", type=Path, metavar="OUT")
    pruning = commands.add_parser("prune", help="verify, then retain only reports and summaries")
    pruning.add_argument("out", type=Path, metavar="OUT")
    pruning.add_argument("--archive", type=Path, required=True, metavar="FILE")
    args = parser.parse_args(argv)
    try:
        if args.command == "pack":
            pack(args.out, args.dest)
        elif args.command == "verify":
            verify(args.file, args.against)
            print(f"Verified: {args.file}")
        else:
            prune(args.out, args.archive)
    except (OSError, ValueError, tarfile.TarError, EOFError, zlib.error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
