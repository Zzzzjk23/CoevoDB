"""Unlimited LLM calls, a run-wide tier, and break-signal interrupts."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

import surprise.baselines.pure_llm as pure_llm
import surprise.experiments.loop as loop
from surprise.gates.s09 import Script
from surprise.harness.ledger import Ledger
from surprise.roles.cache import cache_key
from surprise.roles.constants import CAP_ENV, DEFAULT_MAX_CALLS, TIERS
from surprise.roles.gateway import UNLIMITED, Gateway

FRAMEWORK = Path(__file__).resolve().parents[1]
_PAST_THE_DEFAULT = DEFAULT_MAX_CALLS + 1


def _no_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(CAP_ENV, raising=False)


def _reply(prompt: str) -> dict[str, str]:
    return {"prediction": "x"}


def _lines(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _manifest(out: Path) -> dict:
    ledger = Ledger(out / "ledger.sqlite")
    try:
        run_ids = ledger.run_ids()
        assert len(run_ids) == 1
        return ledger.run_manifest(run_ids[0])
    finally:
        ledger.close()


def test_default_cap_stays_200_and_manifest_has_no_tier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _no_cap(monkeypatch)
    gateway = Gateway(cache_dir=tmp_path / "default")
    assert DEFAULT_MAX_CALLS == 200
    assert gateway.max_calls == 200
    assert gateway.tier is None
    assert gateway.manifest()["max_calls"] == 200
    assert gateway.totals()["max_calls"] == 200
    assert list(gateway.manifest()) == ["tiers", "max_calls", "constants"]
    assert "UNLIMITED" not in gateway.manifest()["constants"]


def test_unlimited_has_no_cap_and_never_blocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _no_cap(monkeypatch)
    script = Script(_reply)
    gateway = Gateway(cache_dir=tmp_path / "cache", transport=script, max_calls=UNLIMITED)
    statuses = [
        gateway.call("implementer", f"prompt {i}", tier="fast", seed=0).status for i in range(_PAST_THE_DEFAULT)
    ]
    assert statuses == ["ok"] * _PAST_THE_DEFAULT
    assert gateway.network_calls == _PAST_THE_DEFAULT
    assert gateway.max_calls is None
    assert gateway.manifest()["max_calls"] == UNLIMITED
    assert gateway.totals()["max_calls"] == UNLIMITED
    assert len(script.calls) == _PAST_THE_DEFAULT


def test_environment_ceiling_caps_unlimited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _no_cap(monkeypatch)
    monkeypatch.setenv(CAP_ENV, "2")
    script = Script(_reply)
    gateway = Gateway(cache_dir=tmp_path / "capped", transport=script, max_calls=UNLIMITED)
    statuses = [gateway.call("implementer", f"p{i}", tier="fast", seed=0).status for i in range(3)]
    assert statuses == ["ok", "ok", "blocked"]
    assert gateway.max_calls == 2
    assert gateway.manifest()["max_calls"] == 2
    assert gateway.totals()["max_calls"] == 2
    assert Gateway(cache_dir=tmp_path / "lower", max_calls=5).max_calls == 2
    monkeypatch.setenv(CAP_ENV, "nope")
    left = Gateway(cache_dir=tmp_path / "open", max_calls=UNLIMITED)
    assert left.max_calls is None
    assert left.manifest()["max_calls"] == UNLIMITED


@pytest.mark.parametrize("bad", ["lots", "5", -1, 1.5, True, False, ""])
def test_gateway_rejects_a_bad_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad: object) -> None:
    _no_cap(monkeypatch)
    with pytest.raises(ValueError):
        Gateway(cache_dir=tmp_path / "bad", max_calls=bad)


def test_tier_override_is_what_the_transport_and_the_ledger_see(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_cap(monkeypatch)
    script = Script(_reply)
    ledger = tmp_path / "calls.jsonl"
    gateway = Gateway(
        cache_dir=tmp_path / "cache",
        ledger_path=ledger,
        transport=script,
        tier="strong",
    )
    reply = gateway.call("implementer", "prompt", tier="fast", seed=3)
    assert script.calls[0]["model"] == TIERS["strong"] == "deepseek-v4-pro"
    assert reply.tier == "strong"
    assert reply.model == TIERS["strong"]
    assert reply.key == cache_key("prompt", TIERS["strong"], 3)
    assert gateway.manifest()["tier"] == "strong"
    rows = _lines(ledger)
    assert len(rows) == 1
    assert rows[0]["tier"] == "strong" and rows[0]["model"] == TIERS["strong"]
    plain = Gateway(cache_dir=tmp_path / "plain", transport=script)
    plain_reply = plain.call("implementer", "prompt", tier="fast", seed=0)
    assert script.calls[-1]["model"] == TIERS["fast"]
    assert plain_reply.tier == "fast" and plain_reply.model == TIERS["fast"]
    assert "tier" not in plain.manifest()
    forced_fast = Gateway(cache_dir=tmp_path / "fast", transport=script, tier="fast")
    forced_fast.call("implementer", "prompt", tier="strong", seed=1)
    assert script.calls[-1]["model"] == TIERS["fast"]


def test_gateway_rejects_an_unknown_tier(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        Gateway(cache_dir=tmp_path / "tier", tier="medium")


def test_loop_rejects_a_bad_llm_switch_before_the_run(tmp_path: Path) -> None:
    cache = str(tmp_path / "cache")
    base = {"roles": ["implementer"], "cache": cache}
    for llm in (
        {**base, "max_calls": "5"},
        {**base, "max_calls": "lots"},
        {**base, "max_calls": -1},
        {**base, "max_calls": 1.5},
        {**base, "max_calls": True},
        {**base, "tier": "medium"},
        {**base, "tier": ""},
    ):
        out = tmp_path / "out"
        with pytest.raises(loop.UsageError):
            loop.run(out, seed=1, max_experiments=1, llm=llm)
        assert not out.exists()


def test_loop_records_unlimited_and_omits_a_null_tier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _no_cap(monkeypatch)
    cache = str(tmp_path / "cache")
    out = tmp_path / "run"
    loop.run(
        out,
        seed=1,
        engines=("duckdb",),
        oracles=("tlp",),
        max_experiments=0,
        llm={"roles": ["implementer"], "cache": cache, "max_calls": UNLIMITED, "network": False, "tier": None},
    )
    config = json.loads((out / "config.json").read_text(encoding="utf-8"))
    assert config["llm"]["max_calls"] == UNLIMITED
    assert "tier" not in config["llm"]
    section = _manifest(out)["llm"]
    assert section["max_calls"] == UNLIMITED
    assert "tier" not in section


def test_loop_records_a_tier_and_keeps_the_default_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _no_cap(monkeypatch)
    cache = str(tmp_path / "cache")
    out = tmp_path / "run"
    loop.run(
        out,
        seed=2,
        engines=("duckdb",),
        oracles=("tlp",),
        max_experiments=0,
        llm={"roles": ["implementer"], "cache": cache, "network": False, "tier": "strong"},
    )
    config = json.loads((out / "config.json").read_text(encoding="utf-8"))
    assert config["llm"]["max_calls"] is None
    assert config["llm"]["tier"] == "strong"
    section = _manifest(out)["llm"]
    assert section["max_calls"] == DEFAULT_MAX_CALLS
    assert section["tier"] == "strong"


def test_loop_cli_accepts_the_new_flags_and_rejects_bad_ones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict = {}

    def fake_run(out, **kwargs):
        seen["llm"] = kwargs["llm"]
        return {"status": "budget_experiments", "experiments": 0}

    def explode(*_args, **_kwargs):
        raise AssertionError("run should not start")

    monkeypatch.setattr(loop, "run", fake_run)
    cache = str(tmp_path / "cache")
    out = str(tmp_path / "out")
    code = loop.main(
        [
            "--out",
            out,
            "--seed",
            "1",
            "--max-experiments",
            "0",
            "--llm",
            "implementer",
            "--llm-cache",
            cache,
            "--llm-max-calls",
            "unlimited",
            "--llm-tier",
            "strong",
        ]
    )
    assert code == 0
    assert seen["llm"] == {
        "roles": ["implementer"],
        "cache": cache,
        "max_calls": "unlimited",
        "network": True,
        "tier": "strong",
    }
    code = loop.main(
        ["--out", out, "--seed", "1", "--max-experiments", "0", "--llm", "implementer", "--llm-cache", cache]
    )
    assert code == 0
    assert "tier" not in seen["llm"]
    assert seen["llm"]["max_calls"] is None

    monkeypatch.setattr(loop, "run", explode)
    base = ["--out", out, "--seed", "1", "--max-experiments", "1"]
    rejected = [
        base + ["--llm-max-calls", "lots"],
        base + ["--llm-tier", "medium"],
        base + ["--llm-max-calls", "-1"],
        base + ["--llm-max-calls", "1.5"],
        base + ["--llm-tier", "strong"],
        base + ["--llm-max-calls", "unlimited"],
        base + ["--llm", "implementer", "--llm-cache", cache, "--llm-tier", "medium"],
    ]
    for argv in rejected:
        assert loop.main(argv) == 2, argv


def test_pure_llm_rejects_a_bad_cap_or_tier_before_the_run(tmp_path: Path) -> None:
    for kwargs in (
        {"max_calls": "5"},
        {"max_calls": "lots"},
        {"max_calls": -1},
        {"max_calls": True},
        {"max_calls": 1.5},
        {"tier": "medium"},
    ):
        out = tmp_path / "out"
        with pytest.raises(pure_llm.UsageError):
            pure_llm.run(out, seed=1, max_experiments=1, offline=True, **kwargs)
        assert not out.exists()


def test_pure_llm_records_unlimited_only_when_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _no_cap(monkeypatch)
    out = tmp_path / "open"
    report = pure_llm.run(out, seed=1, max_experiments=0, max_calls=UNLIMITED, offline=True)
    config = json.loads((out / "config.json").read_text(encoding="utf-8"))
    assert config["llm"]["max_calls"] == UNLIMITED
    assert "tier" not in config["llm"]
    section = _manifest(out)["pure_llm"]
    assert section["max_calls"] == UNLIMITED
    assert "tier" not in section
    assert report["llm"]["max_calls"] == UNLIMITED

    plain = tmp_path / "plain"
    pure_llm.run(plain, seed=1, max_experiments=0, offline=True)
    plain_config = json.loads((plain / "config.json").read_text(encoding="utf-8"))
    assert plain_config["llm"]["max_calls"] is None
    assert "tier" not in plain_config["llm"]
    assert "tier" not in _manifest(plain)["pure_llm"]


def test_pure_llm_tier_reaches_the_transport_and_the_files(tmp_path: Path) -> None:
    script = Script(_reply)
    out = tmp_path / "strong"
    pure_llm.run(
        out,
        seed=4,
        engine="duckdb",
        oracles=("tlp",),
        max_experiments=5,
        max_calls=1,
        tier="strong",
        transport=script,
    )
    assert len(script.calls) == 1
    assert script.calls[0]["model"] == TIERS["strong"]
    rows = _lines(out / "llm" / "calls.jsonl")
    assert rows and all(row["tier"] == "strong" and row["model"] == TIERS["strong"] for row in rows)
    config = json.loads((out / "config.json").read_text(encoding="utf-8"))
    assert config["llm"]["tier"] == "strong"
    assert _manifest(out)["pure_llm"]["tier"] == "strong"


def test_pure_llm_cli_accepts_the_new_flags_and_rejects_bad_ones(tmp_path: Path) -> None:
    out = tmp_path / "cli"
    code = pure_llm.main(
        [
            "--out",
            str(out),
            "--seed",
            "1",
            "--max-experiments",
            "0",
            "--llm-max-calls",
            "unlimited",
            "--llm-tier",
            "fast",
            "--llm-offline",
        ]
    )
    assert code == 0
    config = json.loads((out / "config.json").read_text(encoding="utf-8"))
    assert config["llm"]["max_calls"] == "unlimited"
    assert config["llm"]["tier"] == "fast"
    assert _manifest(out)["pure_llm"]["tier"] == "fast"
    base = ["--out", str(tmp_path / "bad"), "--seed", "1", "--max-experiments", "0"]
    for argv in (
        base + ["--llm-max-calls", "lots"],
        base + ["--llm-tier", "medium"],
        base + ["--llm-max-calls", "-1"],
        base + ["--llm-max-calls", "1.5"],
    ):
        assert pure_llm.main(argv) == 2, argv
        assert not (tmp_path / "bad").exists()


def test_import_does_not_install_the_break_handler() -> None:
    name = "SIGBREAK" if sys.platform == "win32" else "SIGTERM"
    code = (
        "import json, signal\n"
        "import surprise.experiments.loop\n"
        "import surprise.baselines.pure_llm\n"
        f"handler = signal.getsignal(getattr(signal, {name!r}))\n"
        "print(json.dumps(handler == signal.SIG_DFL))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=FRAMEWORK,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.returncode == 0, proc.stderr[-500:]
    assert proc.stdout.strip().splitlines()[-1] == "true"


def _progress_count(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return 0
    return sum(1 for line in text.splitlines() if line.strip())


def _stop_process(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
    else:
        proc.kill()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_main_loop_interrupt_writes_an_interrupted_report(tmp_path: Path) -> None:
    out = tmp_path / "loop"
    argv = [
        sys.executable,
        "-m",
        "surprise.experiments.loop",
        "--out",
        str(out),
        "--seed",
        "3",
        "--max-minutes",
        "2",
        "--engine",
        "duckdb",
        "--oracle",
        "tlp",
        "--oracle",
        "norec",
    ]
    env = {key: value for key, value in os.environ.items() if key.upper() != "DEEPSEEK_API_KEY"}
    env["PYTHONUNBUFFERED"] = "1"
    err_path = tmp_path / "stderr.txt"
    err_handle = err_path.open("w", encoding="utf-8")
    kwargs: dict = {
        "cwd": str(FRAMEWORK),
        "env": env,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": err_handle,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(argv, **kwargs)
    progress = out / "progress.jsonl"
    code: int | None = None
    previous = None
    try:
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            if _progress_count(progress) >= 2:
                break
            time.sleep(0.25)
        assert proc.poll() is None, err_path.read_text(encoding="utf-8", errors="replace")[-800:]
        assert _progress_count(progress) >= 2
        if sys.platform == "win32":
            previous = signal.getsignal(signal.SIGBREAK)
            signal.signal(signal.SIGBREAK, signal.SIG_IGN)
            os.kill(proc.pid, signal.CTRL_BREAK_EVENT)
        else:
            os.kill(proc.pid, signal.SIGTERM)
        code = proc.wait(timeout=90)
    finally:
        err_handle.close()
        if previous is not None:
            signal.signal(signal.SIGBREAK, previous)
        _stop_process(proc)
    err = err_path.read_text(encoding="utf-8", errors="replace")[-800:]
    assert code == 130, err
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "interrupted"
