"""S11 opening fixes: store replace retry, loop error.txt, request deadline, vocabulary."""

from __future__ import annotations

import http.server
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from surprise.experiments import loop
from surprise.features.registry import default_registry
from surprise.features.vocabulary import FeatureDef
from surprise.gates.s10_cases import VOCAB_GOOD, VOCAB_PARENT
from surprise.metrics.dups import compare, new_families, run_registry
from surprise.metrics.recall import score
from surprise.roles import Gateway, TransportError
from surprise.roles.constants import REQUEST_DEADLINE_S
from surprise.theory import StoreError, Workbench


DUMMY_KEY = "sk-test-dummy"
DEADLINE_S = 1.5
DEADLINE_SLACK_S = 3.0


def test_store_retries_transient_permissionerror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from surprise.theory import store as store_mod

    real = os.replace
    calls = {"n": 0}

    def flaky(src: Any, dst: Any) -> None:
        calls["n"] += 1
        if calls["n"] <= 3:
            raise PermissionError(13, "simulated: the file is open in another process")
        real(src, dst)

    monkeypatch.setattr(os, "replace", flaky)
    monkeypatch.setattr(store_mod.time, "sleep", lambda _seconds: None)
    wb = Workbench.create(tmp_path / "theory")
    assert calls["n"] > 3
    reopened = Workbench.open(tmp_path / "theory")
    assert reopened.theory.version == wb.theory.version
    assert not list((tmp_path / "theory").rglob("*.tmp"))


def test_store_lasting_permissionerror_is_raised(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from surprise.theory import store as store_mod

    def broken(src: Any, dst: Any) -> None:
        raise PermissionError(13, "simulated: always")

    monkeypatch.setattr(os, "replace", broken)
    monkeypatch.setattr(store_mod.time, "sleep", lambda _seconds: None)
    with pytest.raises(PermissionError):
        Workbench.create(tmp_path / "theory")
    leftover = list((tmp_path / "theory").rglob("*.tmp")) if (tmp_path / "theory").exists() else []
    assert leftover == []


def test_loop_keeps_drive_error_when_report_succeeds(tmp_path: Path) -> None:
    def drive(_state: Any) -> None:
        raise ValueError("s11-test-drive")

    out = tmp_path / "drive"
    saved = loop._drive
    loop._drive = drive
    try:
        with pytest.raises(ValueError, match="s11-test-drive"):
            loop.run(out, seed=1, engines=("duckdb",), oracles=("tlp",), max_experiments=1)
    finally:
        loop._drive = saved
    text = (out / "error.txt").read_text(encoding="utf-8")
    assert "s11-test-drive" in text and "ValueError" in text
    payload = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert payload["status"] == "error"


def test_loop_keeps_drive_error_when_report_fails(tmp_path: Path) -> None:
    def drive(_state: Any) -> None:
        raise ValueError("s11-test-drive")

    def report(_state: Any) -> dict:
        raise RuntimeError("s11-test-report")

    out = tmp_path / "both"
    saved = (loop._drive, loop._write_report)
    loop._drive = drive
    loop._write_report = report
    try:
        with pytest.raises(ValueError, match="s11-test-drive"):
            loop.run(out, seed=1, engines=("duckdb",), oracles=("tlp",), max_experiments=1)
    finally:
        loop._drive, loop._write_report = saved
    text = (out / "error.txt").read_text(encoding="utf-8")
    assert "s11-test-drive" in text and "ValueError" in text
    assert "s11-test-report" in text
    assert "--- while writing the report ---" in text


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True


def _serve(mode: str) -> tuple[_Server, str]:
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:
            return

        def do_POST(self) -> None:  # noqa: N802 - http.server API
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            if mode == "ok":
                body = json.dumps(
                    {
                        "choices": [{"message": {"content": '{"prediction": "ok"}'}}],
                        "usage": {"prompt_tokens": 3, "completion_tokens": 4},
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            started = time.monotonic()
            try:
                while time.monotonic() - started < 30:
                    if mode == "trickle":
                        self.wfile.write(b" \n")
                        self.wfile.flush()
                    time.sleep(0.25)
            except OSError:
                return

    server = _Server(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/v1"


def _complete(url: str) -> Any:
    from surprise.roles.transport import DeepSeekTransport

    transport = DeepSeekTransport(base_url=url, deadline_s=DEADLINE_S)
    return transport.complete(
        model="deepseek-flash",
        prompt="x",
        temperature=0.0,
        max_tokens=10,
        role="gate",
    )


def test_transport_normal_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    from surprise.roles.transport import DeepSeekTransport

    monkeypatch.setenv("DEEPSEEK_API_KEY", DUMMY_KEY)
    server, url = _serve("ok")
    try:
        done = _complete(url)
        assert done.text == '{"prediction": "ok"}' and done.output_tokens == 4
    finally:
        server.shutdown()
    assert DeepSeekTransport().deadline_s == REQUEST_DEADLINE_S


def test_transport_deadline_on_keep_alive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from surprise.roles.transport import DeepSeekTransport

    monkeypatch.setenv("DEEPSEEK_API_KEY", DUMMY_KEY)
    server, url = _serve("trickle")
    try:
        started = time.monotonic()
        with pytest.raises(TransportError) as info:
            _complete(url)
        took = time.monotonic() - started
        assert took <= DEADLINE_S + DEADLINE_SLACK_S
        assert DUMMY_KEY not in str(info.value)
        gw = Gateway(
            cache_dir=tmp_path / "cache",
            ledger_path=tmp_path / "calls.jsonl",
            max_calls=5,
            transport=DeepSeekTransport(base_url=url, deadline_s=DEADLINE_S),
        )
        reply = gw.call("gate", "hello", tier="fast", seed=0)
        assert reply.status == "error"
        assert not any((tmp_path / "cache").rglob("*.json"))
        totals = gw.totals()["by_role"]["gate"]
        assert totals["error"] == 1 and totals["network"] == 1
    finally:
        server.shutdown()


def test_transport_deadline_on_silence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from surprise.roles.transport import DeepSeekTransport

    monkeypatch.setenv("DEEPSEEK_API_KEY", DUMMY_KEY)
    server, url = _serve("silent")
    try:
        started = time.monotonic()
        with pytest.raises(TransportError) as info:
            _complete(url)
        took = time.monotonic() - started
        assert took <= DEADLINE_S + DEADLINE_SLACK_S
        assert DUMMY_KEY not in str(info.value)
        gw = Gateway(
            cache_dir=tmp_path / "cache",
            ledger_path=tmp_path / "calls.jsonl",
            max_calls=5,
            transport=DeepSeekTransport(base_url=url, deadline_s=DEADLINE_S),
        )
        reply = gw.call("gate", "hello", tier="fast", seed=0)
        assert reply.status == "error"
        assert not any((tmp_path / "cache").rglob("*.json"))
        totals = gw.totals()["by_role"]["gate"]
        assert totals["error"] == 1 and totals["network"] == 1
    finally:
        server.shutdown()


def _extended_registry(path: Path):
    registry = default_registry()
    registry.register(
        FeatureDef(
            feature_id=VOCAB_GOOD["id"],
            kind="leaf",
            parent=VOCAB_PARENT,
            layer="ast",
            description="s11-fixes test",
            source="llm:test",
            definition={"kind": "regex", "pattern": VOCAB_GOOD["pattern"]},
            accepted=False,
            acceptance=None,
        )
    )
    registry.accept(VOCAB_GOOD["id"], {"test": True})
    registry.save(path)
    return registry


def test_metrics_read_run_vocabulary(tmp_path: Path) -> None:
    vocab = tmp_path / "vocabulary.json"
    registry = _extended_registry(vocab)
    run_dir = tmp_path / "run"
    theory = run_dir / "theory"
    Workbench.create(theory, registry=registry)
    (run_dir / "config.json").write_text(
        json.dumps({"vocabulary": str(vocab)}),
        encoding="utf-8",
    )
    loaded = run_registry(run_dir)
    assert loaded is not None and loaded.digest() == registry.digest()
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "config.json").write_text("{}", encoding="utf-8")
    assert run_registry(plain) is None
    with pytest.raises(StoreError):
        new_families(theory)
    families = new_families(theory, registry=loaded)
    assert families == []
    old = tmp_path / "old"
    (old / "results" / "r").mkdir(parents=True)
    (old / "old_run.json").write_text(json.dumps({"run_dir": "results/r"}), encoding="utf-8")
    report = {"signature": None, "candidate": {"kind": "tlp"}, "root_key": "abc"}
    (old / "results" / "r" / "bugs.jsonl").write_text(
        json.dumps(report) + "\n" + json.dumps(report) + "\n",
        encoding="utf-8",
    )
    compared = compare(run_dir, old)
    assert compared["new"]["families"] == families
    assert compared["old"]["rate"] == 0.5
    found = score({"items": []}, theory, registry=loaded)
    assert found["families"] == 0
