"""Resident phi worker: cache, timeout degrade, restart, and close."""

from __future__ import annotations

import json
import sys

from surprise.features.ast import extract_ast
from surprise.features.phi import make_phi
from surprise.harness.contracts import SqlCase
from surprise.harness.oracles.forms import full_query
from surprise.hunter.extractor import PhiExtractor
from surprise.hunter.operators import case_digest


def _case(query: str = "SELECT 1") -> SqlCase:
    return SqlCase(engine="duckdb", setup=(), query=query)


def _degraded(case: SqlCase):
    ast_features, ast_status = extract_ast(full_query(case), case.engine)
    return make_phi(case.engine, ast_features, {"ast": ast_status, "plan": "unavailable", "data": "unavailable"})


def test_extractor_caches_and_does_not_start_on_init() -> None:
    extractor = PhiExtractor()
    try:
        assert extractor._proc is None
        first = extractor.extract(_case())
        second = extractor.extract(_case())
        assert first == second
        assert extractor.stats["calls"] == 2
        assert extractor.stats["cache_hits"] == 1
        assert extractor.stats["timeouts"] == 0
        assert first.layers["plan"] in ("ok", "unavailable")
        other = extractor.extract(_case("SELECT 2"))
        assert extractor.stats["calls"] == 3
        assert extractor.stats["cache_hits"] == 1
        assert case_digest(_case()) != case_digest(_case("SELECT 2"))
        assert other.engine == "duckdb"
    finally:
        extractor.close()
        extractor.close()


def test_timeout_degrades_restarts_and_caches_the_fallback(tmp_path) -> None:
    script = tmp_path / "slow_worker.py"
    script.write_text(
        "import json, sys, time\n"
        "for line in sys.stdin:\n"
        "    time.sleep(30)\n"
        "    req = json.loads(line)\n"
        "    sys.stdout.write(json.dumps({'id': req['id'], 'error': 'RuntimeError: late'}) + '\\n')\n"
        "    sys.stdout.flush()\n",
        encoding="utf-8",
    )
    extractor = PhiExtractor(timeout_s=0.2)
    extractor._command = [sys.executable, str(script)]
    try:
        case = _case("SELECT 1")
        got = extractor.extract(case)
        assert got == _degraded(case)
        assert dict(got.layers) == {"ast": got.layers["ast"], "plan": "unavailable", "data": "unavailable"}
        assert extractor.stats["timeouts"] >= 1
        assert extractor.stats["restarts"] >= 1
        again = extractor.extract(case)
        assert again == got
        assert extractor.stats["cache_hits"] >= 1
        other = extractor.extract(_case("SELECT 2"))
        assert other == _degraded(_case("SELECT 2"))
        assert extractor.stats["timeouts"] >= 2
        assert extractor.stats["restarts"] >= 2
    finally:
        extractor.close()


def test_worker_error_degrades_and_close_then_extract(tmp_path) -> None:
    script = tmp_path / "err_worker.py"
    script.write_text(
        "import json, sys\n"
        "for line in sys.stdin:\n"
        "    req = json.loads(line)\n"
        "    sys.stdout.write(json.dumps({'id': req['id'], 'error': 'RuntimeError: boom'}) + '\\n')\n"
        "    sys.stdout.flush()\n",
        encoding="utf-8",
    )
    extractor = PhiExtractor(timeout_s=5.0)
    extractor._command = [sys.executable, str(script)]
    try:
        case = _case("SELECT 1")
        got = extractor.extract(case)
        assert got == _degraded(case)
        assert extractor.stats["errors"] >= 1
        assert extractor.stats["restarts"] >= 1
    finally:
        extractor.close()
    later = extractor.extract(_case("SELECT 3"))
    try:
        assert later == _degraded(_case("SELECT 3"))
    finally:
        extractor.close()


def test_phi_worker_module_roundtrip() -> None:
    import subprocess
    from pathlib import Path

    framework = Path(__file__).resolve().parents[1]
    case = _case("SELECT 1")
    payload = json.dumps({"id": 7, "case": case.to_dict()}) + "\n"
    proc = subprocess.run(
        [sys.executable, "-m", "surprise.hunter.phi_worker"],
        cwd=str(framework),
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    reply = json.loads(proc.stdout.strip().splitlines()[-1])
    assert reply["id"] == 7
    assert "phi" in reply
    assert "error" not in reply
