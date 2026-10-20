"""Personal alerts and read-only grid monitoring, entirely offline."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest

from surprise.experiments import grid
from surprise.notify import pushplus, watch
from surprise.roles.gateway import Gateway, TransportError


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.delenv("PUSHPLUS_TOKEN", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("SURPRISE_LLM_MAX_CALLS", raising=False)

    def unexpected(_transport, request):
        raise AssertionError("Unexpected network request")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", unexpected)


@pytest.fixture
def wire(monkeypatch):
    state = SimpleNamespace(requests=[], status=200, body={"code": 200}, raw=None, error=None)

    def handle(_transport, request):
        request.read()
        state.requests.append(request)
        if state.error:
            raise state.error("synthetic transport failure", request=request)
        if state.raw is not None:
            return httpx.Response(state.status, content=state.raw, request=request)
        return httpx.Response(state.status, json=state.body, request=request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handle)
    return state


class Inbox:
    def __init__(self, result=True, error=None):
        self.messages = []
        self.result = result
        self.error = error

    def send(self, title, content):
        self.messages.append((title, content))
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def setup(tmp_path):
    raw = {"schema": 1, "name": "notify", "budget": {"minutes": 1.0}, "seeds": [1, 2],
           "arms": [{"name": "full", "kind": "surprise", "engines": ["duckdb"],
                     "tier": "glm-flash",
                     "llm": {"roles": ["implementer"], "cache": "cache", "max_calls": "unlimited"}},
                    {"name": "nollm", "kind": "surprise", "engines": ["duckdb"]}]}
    source = tmp_path / "config.json"
    source.write_text(json.dumps(raw), encoding="utf-8")
    config = grid.load_config(source)
    out = tmp_path / "out"
    out.mkdir()
    (out / "grid.json").write_text(json.dumps(config), encoding="utf-8")
    now = [datetime(2026, 10, 21, 23, 59, tzinfo=timezone.utc).timestamp()]
    inbox = Inbox()
    watcher = watch.Watcher(out, notifier=inbox, clock=lambda: now[0])
    return SimpleNamespace(out=out, now=now, inbox=inbox, watcher=watcher)


def cell(setup, label="full/s1-r0"):
    directory = setup.out / "cells" / label
    (directory / "llm").mkdir(parents=True, exist_ok=True)
    progress = directory / "progress.jsonl"
    progress.touch()
    os.utime(progress, (setup.now[0], setup.now[0]))
    return directory


def append(directory, *statuses, reason="TransportError: HTTPStatusError 402", raw=b""):
    with (directory / "llm" / "calls.jsonl").open("ab") as handle:
        for status in statuses:
            handle.write((json.dumps({"status": status, "reason": reason}, ensure_ascii=False) + "\n").encode())
        handle.write(raw)


def end(setup, label="full/s1-r0", status="done", returncode=0):
    directory = cell(setup, label)
    (directory / "cell.json").write_text(json.dumps({"status": status, "returncode": returncode}), encoding="utf-8")
    return directory


def poll(setup, watcher=None):
    def tree():
        return {str(p.relative_to(setup.out)): (p.stat().st_size, p.stat().st_mtime_ns)
                for p in setup.out.rglob("*")}

    before = tree()
    events = (watcher or setup.watcher).poll()
    assert tree() == before
    return events


def kinds(events):
    return [(e.kind, e.cell, e.cause) for e in events]


def test_pushplus_wire_limits_environment_and_success_count(monkeypatch, wire, capsys):
    monkeypatch.setenv("PUSHPLUS_TOKEN", "synthetic-push-credential")
    sender = pushplus.PushPlus(timeout_s=2.5)
    monkeypatch.setenv("PUSHPLUS_TOKEN", "changed-after-construction")
    assert sender.send("题" * 110, "文" * 4100)
    request = wire.requests[-1]
    assert (request.method, str(request.url)) == ("POST", pushplus.URL)
    assert json.loads(request.content) == {
        "token": "synthetic-push-credential", "title": "题" * 100,
        "content": "文" * 4000, "template": "txt",
    }
    assert request.extensions["timeout"] == dict.fromkeys(("connect", "read", "write", "pool"), 2.5)
    assert "authorization" not in request.headers
    assert sender.enabled and sender.sent == 1
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("code", [900, 905, 888])
def test_pushplus_stop_codes_are_permanent_for_object(wire, code):
    wire.body = {"code": code}
    sender = pushplus.PushPlus("synthetic")
    assert not sender.send("title", "body")
    wire.body = {"code": 200}
    assert not sender.enabled and not sender.send("title", "body")
    assert len(wire.requests) == 1 and sender.sent == 0


@pytest.mark.parametrize("status,body,raw,error", [
    (500, {"code": 200}, None, None), (200, {"code": 999}, None, None),
    (200, {"code": "200"}, None, None), (200, [], None, None),
    (200, None, None, None), (200, {}, b"not json", None),
    (200, {}, None, httpx.ConnectError), (200, {}, None, httpx.ReadTimeout),
])
def test_pushplus_transient_failures_do_not_disable(wire, status, body, raw, error):
    wire.status, wire.body, wire.raw, wire.error = status, body, raw, error
    sender = pushplus.PushPlus("synthetic")
    assert not sender.send("title", "body") and sender.enabled and sender.sent == 0
    wire.status, wire.body, wire.raw, wire.error = 200, {"code": 200}, None, None
    assert sender.send("title", "body") and sender.sent == 1


def test_pushplus_no_token_and_cli_exit_codes(monkeypatch, wire, capsys):
    assert not pushplus.PushPlus().enabled
    assert not pushplus.PushPlus().send("title", "body")
    assert pushplus.main(["title", "body"]) == 2 and not wire.requests
    monkeypatch.setenv("PUSHPLUS_TOKEN", "synthetic")
    assert not pushplus.PushPlus("").send("title", "body")
    assert pushplus.main(["title", "body"]) == 0
    wire.status = 500
    assert pushplus.main(["title", "body"]) == 1
    assert "synthetic" not in capsys.readouterr().out


@pytest.mark.parametrize("reason,cause", [
    (None, "other"), ("TransportError", "other"), ("RuntimeError", "other"),
    ("HTTPStatusError 402", "credit"), ("(401)", "auth"), ("HTTP 403", "auth"),
    ("HTTP 429", "rate"), ("DeadlineExceeded", "timeout"),
    ("DEEPSEEK_API_KEY is not set", "nokey"), ("HTTP 500", "other"),
    ("1402", "other"), ("4020", "other"), ("x402", "other"),
])
def test_classify_independent_status_codes(reason, cause):
    assert watch.classify(reason) == cause


@pytest.mark.parametrize("error,reason", [
    (TransportError("HTTPStatusError 402"), "TransportError: HTTPStatusError 402"),
    (TransportError(""), "TransportError"), (RuntimeError("private detail"), "RuntimeError"),
])
def test_gateway_keeps_only_transport_details(tmp_path, error, reason):
    class Broken:
        def complete(self, **kwargs):
            raise error

    path = tmp_path / "calls.jsonl"
    gateway = Gateway(cache_dir=tmp_path / "cache", ledger_path=path, transport=Broken())
    reply = gateway.call("implementer", "prompt", tier="fast", seed=0)
    assert reply.status == "error" and reply.reason == reason
    assert json.loads(path.read_text())["reason"] == reason


def test_start_existing_failures_and_terminal_summary(setup, capsys):
    for label in ("full/s1-r0", "full/s2-r0", "nollm/s1-r0", "nollm/s2-r0"):
        end(setup, label, status="failed" if label == "full/s1-r0" else "done", returncode=1)
    append(setup.out / "cells/full/s1-r0", *(["error"] * 5))
    events = poll(setup)
    assert kinds(events) == [("start", None, None), ("finished", None, None)]
    assert all("full/s1-r0" in event.text for event in events)
    assert "完成 3，失败 1" in events[0].text
    assert str(setup.out) in events[0].text and watch.socket.gethostname() in events[0].text
    title, body = setup.inbox.messages[0]
    assert title.startswith("[CoevoDB]") and title.endswith("（共 2 条）")
    assert "网格已结束" in title and "finished" in body
    assert poll(setup) == [] and setup.watcher.run(interval_s=0) == 0
    assert len(capsys.readouterr().out.splitlines()) == 2
    with pytest.raises(FrozenInstanceError):
        events[0].kind = "modified"


def test_incremental_utf8_streaks_miss_rejected_and_blocked(setup):
    directory = cell(setup)
    setup.watcher.streak = 3
    append(directory, "error", "miss", "error", "error")
    assert kinds(poll(setup)) == [("start", None, None), ("llm_errors", "full/s1-r0", "credit")]
    title, body = setup.inbox.messages[0]
    assert "额度不足" in title and title.endswith("（共 2 条）")
    assert "full/s1-r0" in body and "TransportError: HTTPStatusError 402" in body
    append(directory, "error", "blocked", "blocked")
    assert kinds(poll(setup)) == [("llm_blocked", "full/s1-r0", None)]
    append(directory, "rejected", "error", "miss", "error")
    assert poll(setup) == []
    line = (json.dumps({"status": "error", "reason": "中文 DeadlineExceeded"}, ensure_ascii=False) + "\n").encode()
    split = line.index("中".encode()) + 1
    append(directory, raw=line[:split])
    assert poll(setup) == []
    append(directory, raw=line[split:])
    assert kinds(poll(setup)) == [("llm_errors", "full/s1-r0", "timeout")]
    assert poll(setup) == []
    append(directory, "ok", "error", "error", "error", reason="HTTP 429")
    assert kinds(poll(setup)) == [("llm_errors", "full/s1-r0", "rate")]


def test_newly_finished_cell_reads_final_calls_and_failure_tail_once(setup):
    poll(setup)
    directory = end(setup, status="failed", returncode=7)
    grid._cell_log(directory).write_text("discard\n" + "x" * 350 + "\nValueError: boom\nlast\n", encoding="utf-8")
    append(directory, *(["error"] * 5), "blocked")
    events = poll(setup)
    assert kinds(events) == [("llm_errors", "full/s1-r0", "credit"),
                             ("llm_blocked", "full/s1-r0", None), ("cell_failed", "full/s1-r0", None)]
    assert "returncode=7" in events[-1].text and "ValueError: boom" in events[-1].text
    assert "discard" not in events[-1].text and "x" * 301 not in events[-1].text
    assert len(setup.inbox.messages) == 2
    append(directory, "ok", *(["error"] * 5))
    assert poll(setup) == []


def test_stall_ignores_directories_rearms_only_after_alert_time(setup):
    directory = cell(setup)
    progress = directory / "progress.jsonl"
    old = setup.now[0] - 31 * 60
    os.utime(progress, (old, old))
    assert kinds(poll(setup)) == [("start", None, None), ("stall", "full/s1-r0", None)]
    setup.now[0] += 10
    os.utime(directory, (setup.now[0], setup.now[0]))
    os.utime(progress, (setup.now[0] - 20, setup.now[0] - 20))
    assert poll(setup) == []  # Newer than old mtime, but older than the alarm.
    os.utime(progress, (setup.now[0], setup.now[0]))
    assert poll(setup) == []
    setup.now[0] += 31 * 60
    assert kinds(poll(setup)) == [("stall", "full/s1-r0", None)]


@pytest.mark.parametrize("activity", ["cell", "llm", "log"])
def test_stall_considers_each_file_source(setup, activity):
    directory = cell(setup)
    old = setup.now[0] - 31 * 60
    os.utime(directory / "progress.jsonl", (old, old))
    path = {"cell": directory / "other.json", "llm": directory / "llm/other.json",
            "log": grid._cell_log(directory)}[activity]
    path.write_text("activity", encoding="utf-8")
    os.utime(path, (setup.now[0], setup.now[0]))
    assert kinds(poll(setup)) == [("start", None, None)]


@pytest.mark.parametrize("error,result", [(None, False), (RuntimeError("private credential"), True)])
def test_failed_notifier_is_bounded_and_does_not_stop_monitoring(setup, error, result, capsys):
    inbox = Inbox(result=result, error=error)
    watcher = watch.Watcher(setup.out, notifier=inbox, max_per_day=1, clock=lambda: setup.now[0])
    assert kinds(poll(setup, watcher)) == [("start", None, None)]
    assert inbox.messages[-1][1].endswith("今天的推送已到上限，之后的事件只写日志")
    end(setup, status="failed")
    assert kinds(poll(setup, watcher)) == [("cell_failed", "full/s1-r0", None)]
    assert len(inbox.messages) == 1
    setup.now[0] += 120  # Cross UTC midnight without waiting a full day.
    end(setup, "full/s2-r0", status="failed")
    assert kinds(poll(setup, watcher)) == [("cell_failed", "full/s2-r0", None)]
    assert len(inbox.messages) == 2
    output = capsys.readouterr().out
    assert "Notification failed" in output and "private credential" not in output


def test_daily_zero_cap_keeps_events_without_sending(setup):
    setup.watcher.max_per_day = 0
    assert kinds(poll(setup)) == [("start", None, None)]
    assert not setup.inbox.messages


def test_balance_levels_interval_auth_and_timeout(setup, monkeypatch, wire, capsys):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "synthetic-key")
    wire.body = {"data": {"limit_remaining": 0.5}}
    events = poll(setup)
    assert kinds(events) == [("start", None, None), ("balance", None, "low")]
    assert "$0.5" in events[0].text
    request = wire.requests[0]
    assert (request.method, str(request.url)) == ("GET", watch.KEY_INFO_URL)
    assert request.headers["authorization"] == "Bearer synthetic-key"
    assert request.extensions["timeout"]["read"] == 10.0
    assert poll(setup) == [] and len(wire.requests) == 1
    for remaining, expected in [(0, "empty"), (-1, None), (0.5, None)]:
        setup.now[0] += 30 * 60
        wire.body = {"data": {"limit_remaining": remaining}}
        assert kinds(poll(setup)) == ([("balance", None, expected)] if expected else [])
    for status, expected in [(403, "auth"), (401, None)]:
        setup.now[0] += 30 * 60
        wire.status = status
        assert kinds(poll(setup)) == ([("balance", None, expected)] if expected else [])
    setup.now[0] += 30 * 60
    wire.error = httpx.ReadTimeout
    assert poll(setup) == []
    assert "synthetic-key" not in capsys.readouterr().out


@pytest.mark.parametrize("body,raw,status", [
    ({"data": {"limit_remaining": None}}, None, 200),
    ({"data": {"limit_remaining": 1.0}}, None, 200),
    ({"data": {"limit_remaining": True}}, None, 200),
    ({"data": {}}, None, 200), ([], None, 200), ({}, b"bad json", 200),
    ({"data": {"limit_remaining": 0}}, None, 500),
])
def test_balance_unlimited_threshold_and_invalid_replies(setup, monkeypatch, wire, body, raw, status):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "synthetic-key")
    wire.body, wire.raw, wire.status = body, raw, status
    events = poll(setup)
    assert kinds(events) == [("start", None, None)]
    if body == {"data": {"limit_remaining": None}}:
        assert "key 没设额度上限" in events[0].text
        assert "只能靠调用失败发现欠费" in events[0].text


def test_balance_requires_both_key_and_glm_tier(setup, monkeypatch, wire):
    poll(setup)
    assert wire.requests == []
    config_path = setup.out / "grid.json"
    config = json.loads(config_path.read_text())
    config["arms"][0].pop("tier")
    config_path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "synthetic-key")
    poll(setup, watch.Watcher(setup.out, notifier=Inbox()))
    assert wire.requests == []


def test_watcher_redacts_environment_secrets_from_event_text(setup, monkeypatch, capsys):
    monkeypatch.setenv("PUSHPLUS_TOKEN", "synthetic-secret")
    directory = cell(setup)
    append(directory, *(["error"] * 5), reason="synthetic-secret HTTP 402")
    events = poll(setup)
    assert "synthetic-secret" not in repr(events)
    assert "synthetic-secret" not in repr(setup.inbox.messages)
    assert "synthetic-secret" not in capsys.readouterr().out


def test_run_detects_exit_and_keeps_pending_summary(setup, monkeypatch):
    end(setup, status="failed")
    calls = []
    monkeypatch.setattr(watch, "_pid_alive", lambda pid: calls.append(pid) or False)
    monkeypatch.setattr(watch.time, "sleep", lambda _: pytest.fail("must exit without sleeping"))
    assert setup.watcher.run(pid=123, interval_s=0) == 0
    assert calls == [123]
    assert len(setup.inbox.messages) == 1
    assert setup.inbox.messages[0][0].endswith("（共 2 条）")
    assert "exited" in setup.inbox.messages[-1][1] and "full/s1-r0" in setup.inbox.messages[-1][1]
    assert poll(setup) == []


def test_run_poll_loop_exits_when_all_cells_complete(setup, monkeypatch):
    def finish(interval):
        assert interval == 0.25
        for label in ("full/s1-r0", "full/s2-r0", "nollm/s1-r0", "nollm/s2-r0"):
            end(setup, label)

    monkeypatch.setattr(watch.time, "sleep", finish)
    assert setup.watcher.run(interval_s=0.25) == 0
    assert "finished" in setup.inbox.messages[-1][1]


def test_pid_check_preserves_real_child(monkeypatch):
    if os.name == "nt":
        monkeypatch.setattr(watch.os, "kill", lambda *_: pytest.fail("Windows PID check must not call os.kill"))
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1)"])
    try:
        assert watch._pid_alive(child.pid)
        assert child.poll() is None
        assert child.wait(timeout=20) == 0
        assert not watch._pid_alive(child.pid)
        assert not watch._pid_alive(-1)
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=20)


@pytest.mark.parametrize("error,alive", [(None, True), (ProcessLookupError, False), (PermissionError, True)])
def test_posix_pid_check_uses_signal_zero(monkeypatch, error, alive):
    calls = []

    def kill(pid, signal):
        calls.append((pid, signal))
        if error:
            raise error

    monkeypatch.setattr(watch, "os", SimpleNamespace(name="posix", kill=kill))
    assert watch._pid_alive(123) is alive
    assert calls == [(123, 0)]


def test_watch_cli_missing_out_and_options(setup, monkeypatch):
    assert watch.main([str(setup.out / "missing")]) == 2
    assert watch.main([str(setup.out.parent)]) == 2
    captured = {}

    def run(self, *, pid, interval_s):
        captured.update(pid=pid, interval=interval_s, streak=self.streak, stall=self.stall_minutes,
                        balance=self.balance_usd, every=self.balance_every_minutes, cap=self.max_per_day)
        return 0

    monkeypatch.setattr(watch.Watcher, "run", run)
    assert watch.main([str(setup.out), "--pid", "123", "--interval", "2", "--streak", "3",
                       "--stall-minutes", "4", "--balance-usd", "5", "--balance-every-minutes", "6",
                       "--max-per-day", "7"]) == 0
    assert captured == dict(pid=123, interval=2, streak=3, stall=4, balance=5, every=6, cap=7)
