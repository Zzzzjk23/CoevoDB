"""Real PostgreSQL instance lifecycle and authentication contracts."""

import json
import os
from pathlib import Path
import subprocess
import sys

import psycopg2
import pytest
from psycopg2.extensions import make_dsn, parse_dsn

from surprise.experiments import pg_instance as P


@pytest.fixture(scope="module")
def instances(tmp_path_factory):
    root = tmp_path_factory.mktemp("s16-instances")
    with P.running(root) as dsns:
        yield root, dsns


def query(dsn, statement):
    connection = psycopg2.connect(dsn)
    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute(statement)
            return cursor.fetchall()
    finally:
        connection.close()


@pytest.mark.parametrize("kind", P.KINDS)
def test_binaries_and_override(kind, monkeypatch, tmp_path):
    binaries = P.bin_dir(kind)
    assert (binaries / ("postgres.exe" if os.name == "nt" else "postgres")).is_file()
    monkeypatch.setenv(P.BIN_ENV[kind], str(binaries))
    assert P.bin_dir(kind) == binaries
    monkeypatch.setenv(P.BIN_ENV[kind], str(tmp_path))
    with pytest.raises(FileNotFoundError):
        P.bin_dir(kind)


@pytest.mark.parametrize("kind", P.KINDS)
def test_versions_settings_role_and_metadata(instances, kind):
    root, dsns = instances
    dsn = dsns[kind]
    assert os.environ[P.TARGET_DSN_ENV if kind == "target" else P.OLD_DSN_ENV] == dsn
    parsed = parse_dsn(dsn)
    assert "password" not in parsed
    assert Path(parsed["passfile"]).is_absolute()
    assert query(dsn, "SELECT current_user, current_setting('server_version')") == [(P.TARGET_ROLE, P.VERSIONS[kind])]
    expected = {
        "server_encoding": "UTF8", "lc_messages": "C", "TimeZone": "Australia/Sydney",
        "log_timezone": "Australia/Sydney", "DateStyle": "ISO, MDY",
        "default_text_search_config": "pg_catalog.english", "listen_addresses": "127.0.0.1",
        "unix_socket_directories": "", "fsync": "off", "synchronous_commit": "off",
        "full_page_writes": "off", "autovacuum": "off", "max_connections": "50",
    }
    for setting, value in expected.items():
        assert query(make_dsn(dsn, user="coevo"), f"SHOW {setting}") == [(value,)]
    assert query(dsn, "SELECT datcollate, datctype FROM pg_database WHERE datname = current_database()") == [("C", "C")]
    assert query(dsn, "SELECT rolsuper, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = current_user") == [(False, False, True)]
    assert query(dsn, "SELECT has_database_privilege(current_user, 'postgres', 'CREATE')") == [(True,)]
    info = json.loads((root / kind / "instance.json").read_text(encoding="utf-8"))
    assert set(info) == {"kind", "version", "port", "pid", "data_dir", "bin_dir", "log"}
    assert info["kind"] == kind and info["version"] == P.VERSIONS[kind]
    assert info["port"] == int(parsed["port"]) and info["pid"] > 0
    passfile = Path(parsed["passfile"])
    assert len(passfile.read_text(encoding="utf-8").splitlines()) == 2
    if os.name != "nt":
        assert passfile.stat().st_mode & 0o777 == 0o600
    # The passfile, rather than trust authentication, is required.
    without_passfile = dict(parsed, password="deliberately-wrong")
    with pytest.raises(psycopg2.OperationalError):
        psycopg2.connect(**without_passfile)


def test_ensure_reuses_without_creating_directory(instances, tmp_path):
    _, dsns = instances
    unused = tmp_path / "unused"
    with P.ensure(unused) as reused:
        assert reused == dsns
    assert not unused.exists()
    with P.ensure(unused, old=False) as reused:
        assert reused == {"target": dsns["target"]}
    assert not unused.exists()


def test_environment_exception_cleanup_and_keep(tmp_path, monkeypatch):
    monkeypatch.setenv(P.TARGET_DSN_ENV, "previous-target")
    monkeypatch.delenv(P.OLD_DSN_ENV, raising=False)
    with pytest.raises(RuntimeError, match="body failure"):
        with P.running(tmp_path, old=False, keep=True) as dsns:
            assert set(dsns) == {"target"}
            assert os.environ[P.TARGET_DSN_ENV] == dsns["target"]
            assert P.OLD_DSN_ENV not in os.environ
            raise RuntimeError("body failure")
    assert os.environ[P.TARGET_DSN_ENV] == "previous-target"
    assert P.OLD_DSN_ENV not in os.environ
    with pytest.raises(psycopg2.OperationalError):
        psycopg2.connect(dsns["target"])
    directory = tmp_path / "target"
    assert (directory / "data").exists()
    restarted = P.PgInstance(directory)
    try:
        assert restarted.start() is restarted
        assert restarted.running
        assert restarted.version == "16.15"
        assert restarted.start() is restarted
        assert query(restarted.admin_dsn, "SELECT current_user") == [("coevo",)]
    finally:
        restarted.remove()
    restarted.stop()
    restarted.remove()
    assert not restarted.running
    assert not (directory / "data").exists()
    assert not (directory / "pgpass").exists()
    assert (directory / "server.log").exists()
    assert (directory / "instance.json").exists()


def test_ensure_missing_old_creates_and_restores(tmp_path, monkeypatch):
    monkeypatch.setenv(P.TARGET_DSN_ENV, "existing-target")
    monkeypatch.delenv(P.OLD_DSN_ENV, raising=False)
    with P.ensure(tmp_path) as dsns:
        assert set(dsns) == {"target", "old"}
        assert dsns["target"] != "existing-target"
    assert os.environ[P.TARGET_DSN_ENV] == "existing-target"
    assert P.OLD_DSN_ENV not in os.environ
    for kind in P.KINDS:
        assert not (tmp_path / kind / "data").exists()
        assert not (tmp_path / kind / "pgpass").exists()


def test_stop_all(tmp_path):
    instance = P.PgInstance(tmp_path / "target").start()
    try:
        assert instance.running
        assert P.stop_all(tmp_path) == [instance.data_dir]
        assert not instance.running
        assert P.stop_all(tmp_path) == []
    finally:
        instance.remove()


def test_cli_check():
    proc = subprocess.run([sys.executable, "-m", "surprise.experiments.pg_instance", "check"],
                          capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = proc.stdout.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("target 16.15 port=")
    assert lines[1].startswith("old 15.19 port=")
    assert proc.stdout.isascii()
