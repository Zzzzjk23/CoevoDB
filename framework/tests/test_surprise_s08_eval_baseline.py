"""The old no_llm baseline: a real budget, and stand-in commands for the other endings."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from surprise.baselines import old_no_llm as baseline

FRAMEWORK = Path(__file__).resolve().parents[1]
EXIT_SCRIPT = """
import json, os, pathlib, sys
out = pathlib.Path(sys.argv[1])
run = out / "results" / "only"
run.mkdir(parents=True)
lines = [
    json.dumps({"root_key": "aa", "origin": "hunter", "iteration": 1,
                "candidate": {"kind": "plan_variant"},
                "signature": {"engine": "duckdb", "fix_kind": "single", "fix_set": ["join_order"]}}),
    json.dumps({"root_key": "bb", "origin": "dce", "iteration": 2,
                "candidate": {"kind": "norec"}, "signature": None}),
    '{"root_key":',
]
(run / "bugs.jsonl").write_text("\\n".join(lines) + "\\n", encoding="utf-8")
if "DEEPSEEK_API_KEY" in os.environ:
    sys.stderr.write("key-present\\n")
    raise SystemExit(7)
raise SystemExit(0)
"""
SLEEP_SCRIPT = """
import pathlib, sys, time
out = pathlib.Path(sys.argv[1])
run = out / "results" / "sleeper"
run.mkdir(parents=True)
(run / "bugs.jsonl").write_text("", encoding="utf-8")
time.sleep(120)
"""
TWO_DIRS = """
import pathlib, sys
out = pathlib.Path(sys.argv[1])
(out / "results" / "one").mkdir(parents=True)
(out / "results" / "two").mkdir()
"""
NO_DIR = """
import sys
raise SystemExit(0)
"""


def _stand_in(script: str):
    def fake(out, *, seed, python):
        interpreter = sys.executable if python is None else python
        return [interpreter, "-c", script, str(out)]

    return fake


def _aware(text: str) -> datetime:
    parsed = datetime.fromisoformat(text)
    assert parsed.tzinfo is not None
    return parsed


def test_exited_stand_in_strips_the_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                            capsys: pytest.CaptureFixture[str]) -> None:
    token = "token-" + "z" * 12
    monkeypatch.setenv("DEEPSEEK_API_KEY", token)
    monkeypatch.setattr(baseline, "command", _stand_in(EXIT_SCRIPT))
    out = tmp_path / "old"
    out.mkdir()
    found = baseline.run(out, minutes=1, seed=3)
    assert found["ended"] == "exited"
    assert found["returncode"] == 0
    assert found["mode"] == "no_llm" and found["engine"] == "duckdb"
    assert found["seed"] == 3 and found["minutes"] == 1
    assert found["run_dir"] == "results/only"
    assert (out / found["run_dir"]).is_dir()
    assert found["reports"] == 2
    assert 0 <= found["wall_s"] < 30
    assert _aware(found["finished_at"]) >= _aware(found["started_at"])
    stored = json.loads((out / "old_run.json").read_text(encoding="utf-8"))
    assert stored == found
    console = (out / "console.txt").read_text(encoding="utf-8")
    assert token not in console and "key-present" not in console
    assert token not in (out / "old_run.json").read_text(encoding="utf-8")

    code = baseline.main(["--out", str(tmp_path / "printed"), "--minutes", "1", "--seed", "4"])
    assert code == 0
    printed = capsys.readouterr().out
    assert printed.isascii()
    assert json.loads(printed)["ended"] == "exited"
    assert json.loads(printed) == json.loads((tmp_path / "printed" / "old_run.json").read_text(encoding="utf-8"))


def test_killed_stand_in_stops_the_child(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(baseline, "command", _stand_in(SLEEP_SCRIPT))
    out = tmp_path / "old"
    found = baseline.run(out, minutes=0.05, seed=1)
    assert found["ended"] == "killed"
    assert isinstance(found["returncode"], int)
    assert found["run_dir"] == "results/sleeper"
    assert found["reports"] == 0
    assert found["wall_s"] >= 0.05 * 60 - 1


def test_run_dir_must_be_unique_and_out_must_be_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(baseline, "command", _stand_in(TWO_DIRS))
    with pytest.raises(RuntimeError):
        baseline.run(tmp_path / "two", minutes=1, seed=0)
    monkeypatch.setattr(baseline, "command", _stand_in(NO_DIR))
    with pytest.raises(RuntimeError):
        baseline.run(tmp_path / "none", minutes=1, seed=0)

    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "already").write_text("x", encoding="utf-8")

    def boom(*_args, **_kwargs):
        raise AssertionError("command was built")

    monkeypatch.setattr(baseline, "command", boom)
    with pytest.raises(ValueError):
        baseline.run(occupied, minutes=1, seed=0)
    with pytest.raises(ValueError):
        baseline.run(occupied / "already", minutes=1, seed=0)


def test_real_no_llm_is_killed_at_the_budget(tmp_path: Path) -> None:
    out = tmp_path / "old"
    seed = 0
    found = baseline.run(out, minutes=0.5, seed=seed)
    assert found["ended"] == "killed"
    assert found["mode"] == "no_llm" and found["engine"] == "duckdb"
    assert found["seed"] == seed and found["minutes"] == 0.5
    assert isinstance(found["returncode"], int)
    assert isinstance(found["reports"], int) and found["reports"] >= 0
    assert found["wall_s"] >= 0.5 * 60 - 1
    name = Path(found["run_dir"]).name
    assert name.startswith("duckdb_no_llm_") and name.endswith(f"_s08_old_s{seed}")
    assert (out / found["run_dir"]).is_dir()
    assert (out / "console.txt").is_file()
    stored = json.loads((out / "old_run.json").read_text(encoding="utf-8"))
    assert stored == found
    assert _aware(stored["started_at"]) <= _aware(stored["finished_at"])


def test_eval_modules_import_no_model_client() -> None:
    probe = (
        "import sys, surprise.metrics.curve, surprise.metrics.dups, "
        "surprise.metrics.recall, surprise.baselines.old_no_llm\n"
        "bad=[m for m in ('openai','httpx','httpx2','agents','llm','guidelines','evolution.co_evolution') "
        "if m in sys.modules]\n"
        "print('LLM-FREE' if not bad else bad)\n"
    )
    proc = subprocess.run([sys.executable, "-c", probe], cwd=FRAMEWORK, capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, proc.stderr[-800:]
    assert proc.stdout.strip().splitlines()[-1] == "LLM-FREE"
