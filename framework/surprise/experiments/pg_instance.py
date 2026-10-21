"""Disposable, password-authenticated PostgreSQL servers for experiment cells."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import tempfile
import time

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import make_dsn

from surprise.harness.oracles.pg_target import TARGET_DSN_ENV, OLD_DSN_ENV

KINDS = ("target", "old")
VERSIONS = {"target": "16.15", "old": "15.19"}
BIN_ENV = {"target": "COEVO_PG_BIN", "old": "COEVO_PG_OLD_BIN"}
TARGET_ROLE = "coevo_target"


def _executable(name: str) -> str:
    return name + (".exe" if os.name == "nt" else "")


def bin_dir(kind: str) -> Path:
    if kind not in KINDS:
        raise ValueError(f"Unknown PostgreSQL kind: {kind}")
    override = os.environ.get(BIN_ENV[kind])
    if override is not None:
        candidates = [Path(override).resolve()]
    else:
        checkout = Path(__file__).resolve().parents[3]
        common = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=checkout, capture_output=True, check=True, timeout=60,
        ).stdout.decode("utf-8").strip()
        root = Path(common).parent
        prefix = root / ".orch" / ("pg16" if kind == "target" else "pg15")
        candidates = [prefix / "pgsql" / "bin", prefix / "binaries" / "pgsql" / "bin"]
    for candidate in candidates:
        if (candidate / _executable("postgres")).is_file():
            return candidate
    raise FileNotFoundError(f"No postgres executable for {BIN_ENV[kind]} in {candidates}")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _control(binaries: Path, data: Path, mode: str) -> bool:
    return subprocess.run(
        [str(binaries / _executable("pg_ctl")), "-D", str(data), "stop", "-m", mode, "-w", "-t", "60"],
        capture_output=True, timeout=70,
    ).returncode == 0


def _status(binaries: Path, data: Path) -> bool:
    return subprocess.run(
        [str(binaries / _executable("pg_ctl")), "-D", str(data), "status"],
        capture_output=True, timeout=10,
    ).returncode == 0


def _kill(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM if os.name == "nt" else signal.SIGKILL)
    except ProcessLookupError:
        pass


class PgInstance:
    def __init__(self, directory: str | Path, kind: str = "target") -> None:
        if kind not in KINDS:
            raise ValueError(f"Unknown PostgreSQL kind: {kind}")
        self.directory = Path(directory).resolve()
        self.kind = kind
        self.data_dir = self.directory / "data"
        self.log = self.directory / "server.log"
        self.passfile = self.directory / "pgpass"
        self._bin = bin_dir(kind)
        self._process: subprocess.Popen | None = None
        self._port: int | None = None
        self._version: str | None = None

    @property
    def port(self) -> int | None:
        return self._port

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process is not None else None

    @property
    def version(self) -> str | None:
        return self._version

    def _dsn(self, user: str) -> str:
        return make_dsn(host="127.0.0.1", port=self.port, user=user, dbname="postgres",
                        passfile=str(self.passfile), connect_timeout=10)

    @property
    def dsn(self) -> str:
        return self._dsn(TARGET_ROLE)

    @property
    def admin_dsn(self) -> str:
        return self._dsn("coevo")

    @property
    def running(self) -> bool:
        if self._process is None or self._process.poll() is not None:
            return False
        try:
            psycopg2.connect(self.admin_dsn).close()
            return True
        except psycopg2.Error:
            return False

    def _passwords(self, fresh: bool) -> tuple[str, str]:
        if fresh:
            return secrets.token_hex(32), secrets.token_hex(32)
        # Generated passwords contain no passfile separators or escapes.
        entries = {line.split(":")[3]: line.split(":")[4]
                   for line in self.passfile.read_text(encoding="utf-8").splitlines()}
        return entries["coevo"], entries[TARGET_ROLE]

    def _write_passfile(self, admin: str, target: str) -> None:
        with os.fdopen(os.open(self.passfile, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600),
                       "w", encoding="utf-8") as stream:
            for user, password in (("coevo", admin), (TARGET_ROLE, target)):
                stream.write(f"127.0.0.1:{self.port}:*:{user}:{password}\n")
        if os.name != "nt":
            self.passfile.chmod(0o600)

    def start(self) -> PgInstance:
        if self.running:
            return self
        self.directory.mkdir(parents=True, exist_ok=True)
        fresh = not self.data_dir.exists()
        admin, target = self._passwords(fresh)
        try:
            if fresh:
                descriptor, password_path = tempfile.mkstemp(prefix="coevo-initdb-")
                try:
                    with os.fdopen(descriptor, "w", encoding="ascii") as stream:
                        stream.write(admin + "\n")
                    initialized = subprocess.run(
                        [str(self._bin / _executable("initdb")), "-D", str(self.data_dir),
                         "-U", "coevo", "--encoding=UTF8", "--locale=C", "--auth=scram-sha-256",
                         "--pwfile=" + password_path], capture_output=True, timeout=120,
                    )
                    if initialized.returncode:
                        raise RuntimeError("initdb failed: " + initialized.stderr.decode("utf-8", "replace"))
                finally:
                    Path(password_path).unlink(missing_ok=True)
            for attempt in range(3):
                self._port = _free_port()
                self._write_passfile(admin, target)
                with (self.data_dir / "postgresql.conf").open("a", encoding="utf-8") as config:
                    config.write("\n" + "\n".join([
                        "listen_addresses = '127.0.0.1'", f"port = {self.port}",
                        "unix_socket_directories = ''", "fsync = off", "synchronous_commit = off",
                        "full_page_writes = off", "autovacuum = off", "max_connections = 50",
                        "timezone = 'Australia/Sydney'", "log_timezone = 'Australia/Sydney'",
                        "datestyle = 'iso, mdy'", "default_text_search_config = 'pg_catalog.english'",
                        "lc_messages = 'C'",
                    ]) + "\n")
                with self.log.open("ab") as output:
                    log_offset = output.tell()
                    self._process = subprocess.Popen(
                        [str(self._bin / _executable("postgres")), "-D", str(self.data_dir)],
                        stdout=output, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                    )
                deadline = time.monotonic() + 60
                connection = None
                while time.monotonic() < deadline and self._process.poll() is None:
                    try:
                        connection = psycopg2.connect(self.admin_dsn)
                        break
                    except psycopg2.OperationalError:
                        time.sleep(0.1)
                if connection is not None:
                    break
                self.stop()
                with self.log.open("rb") as output:
                    output.seek(log_offset)
                    failure = output.read().decode("utf-8", "replace")
                if attempt == 2 or not any(marker in failure.lower() for marker in
                                           ("address already in use", "could not bind", "only one usage")):
                    raise RuntimeError("PostgreSQL did not become ready within 60 seconds: " + failure[-2000:])
            try:
                connection.autocommit = True
                with connection.cursor() as cursor:
                    cursor.execute("SHOW server_version")
                    self._version = cursor.fetchone()[0]
                    if self.version != VERSIONS[self.kind]:
                        raise RuntimeError(f"Expected PostgreSQL {VERSIONS[self.kind]}, got {self.version}")
                    cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (TARGET_ROLE,))
                    if cursor.fetchone() is None:
                        cursor.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEROLE CREATEDB PASSWORD %s")
                                       .format(sql.Identifier(TARGET_ROLE)), (target,))
                    cursor.execute(sql.SQL("GRANT CREATE ON DATABASE postgres TO {}").format(sql.Identifier(TARGET_ROLE)))
                info = dict(kind=self.kind, version=self.version, port=self.port, pid=self.pid,
                            data_dir=str(self.data_dir), bin_dir=str(self._bin), log=str(self.log))
                (self.directory / "instance.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
            finally:
                connection.close()
            return self
        except BaseException:
            self.stop()
            raise

    def stop(self) -> None:
        if self._process is None:
            return
        if self._process.poll() is None:
            try:
                if not _control(self._bin, self.data_dir, "fast"):
                    _control(self._bin, self.data_dir, "immediate")
            finally:
                if self._process.poll() is None:
                    self._process.kill()
                self._process.wait(timeout=10)

    def remove(self) -> None:
        self.stop()
        data = self.data_dir.resolve()
        if data.parent != self.directory or data.name != "data":
            raise ValueError("Data directory escaped the instance directory")
        if data.exists():
            shutil.rmtree(data)
        self.passfile.unlink(missing_ok=True)


@contextmanager
def running(directory: str | Path, *, old: bool = True, keep: bool = False):
    saved = {name: os.environ.get(name) for name in (TARGET_DSN_ENV, OLD_DSN_ENV)}
    instances = []
    try:
        dsns = {}
        for kind in KINDS if old else ("target",):
            instance = PgInstance(Path(directory) / kind, kind)
            instances.append(instance)
            instance.start()
            dsns[kind] = instance.dsn
            os.environ[TARGET_DSN_ENV if kind == "target" else OLD_DSN_ENV] = instance.dsn
        yield dsns
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        # ExitStack semantics: attempt all cleanups even if one fails.
        from contextlib import ExitStack
        with ExitStack() as cleanup:
            for instance in instances:
                cleanup.callback(instance.stop if keep else instance.remove)


@contextmanager
def ensure(directory: str | Path, *, old: bool = True):
    names = {"target": TARGET_DSN_ENV, **({"old": OLD_DSN_ENV} if old else {})}
    if all(os.environ.get(name) for name in names.values()):
        yield {kind: os.environ[name] for kind, name in names.items()}
    else:
        with running(directory, old=old) as dsns:
            yield dsns


def stop_all(directory: str | Path) -> list[Path]:
    stopped = []
    root = Path(directory).resolve()
    for pidfile in root.rglob("postmaster.pid"):
        data = pidfile.parent.resolve()
        if not data.is_relative_to(root):
            raise ValueError("Data directory escaped the cleanup directory")
        fields = pidfile.read_text(encoding="utf-8").splitlines()
        if len(fields) < 2 or Path(fields[1]).resolve() != data:
            continue
        info_path = data.parent / "instance.json"
        if info_path.exists():
            binaries = Path(json.loads(info_path.read_text(encoding="utf-8"))["bin_dir"])
        else:
            binaries = bin_dir("old" if data.parent.name == "old" else "target")
        if _status(binaries, data):
            try:
                if not _control(binaries, data, "immediate"):
                    _kill(int(fields[0]))
            except subprocess.TimeoutExpired:
                _kill(int(fields[0]))
            stopped.append(data)
    return stopped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["check"])
    parser.parse_args()
    try:
        with tempfile.TemporaryDirectory(prefix="coevo-pg-check-") as directory:
            with running(directory) as dsns:
                for kind, dsn in dsns.items():
                    with psycopg2.connect(dsn) as connection:
                        with connection.cursor() as cursor:
                            cursor.execute("SHOW server_version")
                            version = cursor.fetchone()[0]
                            cursor.execute("SHOW port")
                            port = cursor.fetchone()[0]
                    connection.close()
                    print(f"{kind} {version} port={port}")
        return 0
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}".encode("ascii", "backslashreplace").decode("ascii"))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
