"""Version differential: a newer engine is a regression only with direction.

The same statement runs on the current target and on an older interpreter.
Matching successful bags are a pass, including when both bags are wrong.
Query failures are not that case: both sides raising is invalid. A mismatch
is a fail only when the old result has two independent engines behind it and
the new result is the only dissenter, or when TLP, NoREC, plan variant, or
index presence fails on the new version. Otherwise the label is invalid. An
old crash is not itself a new regression.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from oracles.db_runner import QueryResult
from oracles.errors import is_value_dependent_error
from oracles.normalize import is_internal_error, loose_rows_equal, normalize_rows

from surprise.harness.contracts import IdentityEvidence, Label, SqlCase

from .common import invalid_label, multiset_difference, pass_label
from .cross_dbms import collect_reference_results, default_reference_factories
from .forms import full_query
from .norec import norec_applies
from .pg_target import OLD_DSN_ENV, PostgresTargetRunner
from .registry import OracleOptions, register
from .tlp import tlp_form

_ORACLE = "version_differential"
_WITNESSES = ("tlp", "norec", "plan_variant", "index_presence")
_INDEX_MODULE = "surprise.harness.oracles.index_presence"
_OLD_VENVS = {
    "duckdb": "duckdb-1.1.3",
    "datafusion": "datafusion-50.0.0",
}
_WORKER = Path(__file__).with_name("version_worker.py")
_CHECKOUT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class _OldResult:
    version: str | None
    rows: list[list[Any]]
    error: str | None
    setup_error: str | None
    protocol_error: str | None


def judge_case(
    case: SqlCase,
    *,
    factory,
    timeout_s: float,
    options: OracleOptions,
) -> Label:
    """Label ``case`` by comparing the current engine with its older build."""
    full = full_query(case)
    new_version, new_result, new_setup = _run_new(case, factory, timeout_s, full)
    new_rows = _rows_of(new_result, case.engine)
    if new_setup is not None:
        return _invalid(
            "setup_error",
            full,
            old_version=None,
            new_version=new_version,
            old_rows=[],
            new_rows=[],
            error=new_setup,
        )
    if new_result is not None and new_result.timed_out:
        return _invalid(
            "timeout",
            full,
            old_version=None,
            new_version=new_version,
            old_rows=[],
            new_rows=new_rows,
            error=new_result.error,
        )

    postgres = case.engine == "postgres"
    python = None if postgres else _resolve_old_python(case.engine, options.old_python)
    if (postgres and not os.environ.get(OLD_DSN_ENV)) or (not postgres and python is None):
        return _invalid(
            "harness_error",
            full,
            old_version=None,
            new_version=new_version,
            old_rows=[],
            new_rows=new_rows,
            error="old server is missing" if postgres else "old interpreter is missing",
        )
    try:
        if postgres:
            old = _query_old_postgres(list(case.setup), full, timeout_s)
        else:
            old = _query_old(python, case.engine, list(case.setup), full, timeout_s)
    except subprocess.TimeoutExpired:
        return _invalid(
            "timeout",
            full,
            old_version=None,
            new_version=new_version,
            old_rows=[],
            new_rows=new_rows,
            error="old execution timed out",
        )
    if old.protocol_error is not None:
        return _invalid(
            "harness_error",
            full,
            old_version=old.version,
            new_version=new_version,
            old_rows=[],
            new_rows=new_rows,
            error=old.protocol_error,
        )
    if old.setup_error is not None:
        return _invalid(
            "setup_error",
            full,
            old_version=old.version,
            new_version=new_version,
            old_rows=[],
            new_rows=new_rows,
            error=old.setup_error,
        )

    assert new_result is not None
    if old.error is not None and not new_result.ok:
        # Both sides failed to return a bag. That is not "the same wrong result".
        reason = (
            "value_dependent_error"
            if _both_value_dependent(old, new_result)
            else "query_error"
        )
        error = new_result.error or old.error
        return _invalid(
            reason,
            full,
            old_version=old.version,
            new_version=new_version,
            old_rows=old.rows,
            new_rows=new_rows,
            error=error,
        )
    if _same_outcome(old, new_result, new_rows):
        return pass_label(
            _ORACLE,
            full,
            extra=_fields(
                old.version,
                new_version,
                old.rows,
                new_rows,
                "agree",
                {},
            ),
        )
    if _value_dependent_split(old, new_result):
        error = new_result.error if new_result.error else old.error
        return _invalid(
            "value_dependent_error",
            full,
            old_version=old.version,
            new_version=new_version,
            old_rows=old.rows,
            new_rows=new_rows,
            error=error,
        )

    evidence, witnesses = _direction(case, factory, timeout_s, options, old, new_result)
    if not evidence:
        return _invalid(
            "direction_unknown",
            full,
            old_version=old.version,
            new_version=new_version,
            old_rows=old.rows,
            new_rows=new_rows,
        )
    kind, behavior, error_class = _fail_parts(old, new_result, new_rows, witnesses)
    return Label(
        y="fail",
        oracle=_ORACLE,
        fail_kind=kind,
        identity=IdentityEvidence(
            switches=_switches(witnesses),
            error_class=error_class,
            behavior=behavior,
        ),
        detail={
            "full_query": full,
            **_fields(old.version, new_version, old.rows, new_rows, "regression", evidence),
        },
    )


def _direction(
    case: SqlCase,
    factory,
    timeout_s: float,
    options: OracleOptions,
    old: _OldResult,
    new_result: QueryResult,
) -> tuple[dict[str, Any], list[Label]]:
    """Majority support for the old rows, and sound failures of the new engine."""
    evidence: dict[str, Any] = {}
    supporters = _majority_supporters(case, timeout_s, options, old, new_result)
    if supporters:
        evidence["majority"] = supporters
    witnesses = _collect_witnesses(case, factory, timeout_s)
    if witnesses:
        evidence["witnesses"] = [_witness_record(label) for label in witnesses]
    if not new_result.ok and old.error is None and not supporters and not witnesses:
        return {}, []
    if new_result.ok and old.error is not None and not witnesses:
        # The old engine failed and the new one returned rows. That is not a
        # regression of the new engine unless a sound oracle fails the new one.
        return {}, []
    return evidence, witnesses


def _majority_supporters(
    case: SqlCase,
    timeout_s: float,
    options: OracleOptions,
    old: _OldResult,
    new_result: QueryResult,
) -> list[str]:
    """Engines that match the old rows, when the new result is the only dissenter."""
    if old.error is not None:
        return []
    supplied = options.reference_factories
    factories = default_reference_factories(case.engine) if supplied is None else supplied
    results = collect_reference_results(case, factories, timeout_s=timeout_s)
    old_bag_matches = []
    dissenters = []
    for engine in sorted(results):
        result = results[engine]
        if not _votable(result):
            continue
        rows = normalize_rows(result.rows)
        if loose_rows_equal(rows, old.rows):
            old_bag_matches.append(engine)
        else:
            dissenters.append(engine)
    if len(old_bag_matches) >= 2 and not dissenters:
        return old_bag_matches
    return []


def _collect_witnesses(case: SqlCase, factory, timeout_s: float) -> list[Label]:
    """Sound failures of the new version. A missing index-presence module is skipped."""
    found: list[Label] = []
    for oracle_id in _WITNESSES:
        if oracle_id == "index_presence" and not _index_presence_available():
            continue
        if not _premise(case, oracle_id):
            continue
        try:
            label = _call_public_judge(case, oracle_id, factory, timeout_s)
        except ModuleNotFoundError as exc:
            # Only the optional oracle module itself may be absent. A missing
            # dependency imported by that module is a real harness failure.
            if oracle_id == "index_presence" and exc.name == _INDEX_MODULE:
                continue
            raise
        if label.y == "fail":
            found.append(label)
    return found


def _call_public_judge(case: SqlCase, oracle_id: str, factory, timeout_s: float) -> Label:
    from surprise.harness.oracles import judge as public_judge

    return public_judge(
        case,
        oracle_id,
        runner_factory=factory,
        timeout_s=timeout_s,
    )


def _index_presence_available() -> bool:
    try:
        spec = importlib.util.find_spec(_INDEX_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name == _INDEX_MODULE:
            return False
        raise
    return spec is not None


def _premise(case: SqlCase, oracle_id: str) -> bool:
    if oracle_id == "tlp":
        return tlp_form(case) is not None
    if oracle_id == "norec":
        return norec_applies(case)
    return True


def _fail_parts(
    old: _OldResult,
    new_result: QueryResult,
    new_rows: list[list[Any]],
    witnesses: list[Label],
) -> tuple[str, dict[str, Any], str | None]:
    """fail_kind, behavior, and error class for a directed regression."""
    if old.error is None and new_result.ok:
        return "wrong_result", _behavior(old.rows, new_rows), None
    if old.error is None and _internal(new_result):
        return "crash", {}, _error_class(new_result.error)
    if old.error is None and not new_result.ok:
        return "error_mismatch", {}, _error_class(new_result.error)
    witness = witnesses[0]
    if witness.fail_kind == "wrong_result":
        return "wrong_result", dict(witness.identity.behavior), None
    return witness.fail_kind or "wrong_result", {}, witness.identity.error_class


def _witness_record(label: Label) -> dict[str, Any]:
    """Flat identity plus the witness label, including its detail and SQL."""
    return {
        "oracle": label.oracle,
        "y": label.y,
        "fail_kind": label.fail_kind,
        "switches": list(label.identity.switches),
        "error_class": label.identity.error_class,
        "behavior": dict(label.identity.behavior),
        "label": label.to_dict(),
    }


def _switches(witnesses: list[Label]) -> tuple[str, ...]:
    ordered: list[str] = []
    for label in witnesses:
        for switch in label.identity.switches:
            if switch not in ordered:
                ordered.append(switch)
    return tuple(ordered)


def _behavior(old_rows: list[list[Any]], new_rows: list[list[Any]]) -> dict[str, int]:
    return multiset_difference(QueryResult(rows=old_rows), QueryResult(rows=new_rows))


def _same_outcome(old: _OldResult, new_result: QueryResult, new_rows: list[list[Any]]) -> bool:
    """True when both sides successfully returned the same bag."""
    if old.error is not None or not new_result.ok:
        return False
    return loose_rows_equal(old.rows, new_rows)


def _both_value_dependent(old: _OldResult, new_result: QueryResult) -> bool:
    return is_value_dependent_error(old.error) and is_value_dependent_error(new_result.error)


def _value_dependent_split(old: _OldResult, new_result: QueryResult) -> bool:
    """One side succeeded and the other failed in a value-dependent way."""
    if old.error is None and not new_result.ok:
        return is_value_dependent_error(new_result.error)
    if old.error is not None and new_result.ok:
        return is_value_dependent_error(old.error)
    return False


def _votable(result: QueryResult) -> bool:
    if result.timed_out or not result.ok:
        return False
    return not _internal(result)


def _internal(result: QueryResult) -> bool:
    return bool(result.is_internal_error or is_internal_error(result.error))


def _rows_of(result: QueryResult | None, engine: str) -> list[list[Any]]:
    if result is None or not result.ok or result.timed_out:
        return []
    return _compatible_rows(engine, result.rows)


def _compatible_rows(engine: str, rows: list[list[Any]]) -> list[list[Any]]:
    """Convert cells the way the target runner does, then use shared normalize.

    DataFusion's runner stringifies dates and prefixes bytes before the shared
    normalizer runs. The old worker still sends typed values; applying that
    same ``_norm`` here keeps the two sides comparable. Strings are not parsed
    back into dates or bytes.
    """
    if engine == "datafusion":
        from targets.datafusion_runner import _norm

        rows = [[_norm(cell) for cell in row] for row in rows]
    return normalize_rows(rows)


def _canonical_rows(rows: list[list[Any]]) -> list[list[Any]]:
    """Stable bag order. Duplicates, NULL, and value types stay as they are."""
    copied = [list(row) for row in rows]
    return sorted(copied, key=lambda row: json.dumps(row, sort_keys=True, default=str))


def _error_class(error: str | None) -> str | None:
    if not error:
        return None
    return error.split(":", 1)[0]


def _run_new(
    case: SqlCase,
    factory,
    timeout_s: float,
    full: str,
) -> tuple[str | None, QueryResult | None, str | None]:
    runner = factory()
    try:
        version = _version_of(case.engine, runner)
        outcomes = runner.setup(list(case.setup))
        setup_error = _first_setup_error(outcomes)
        if setup_error is not None:
            return version, None, setup_error
        result = runner.run(full, timeout_s=timeout_s)
        if not isinstance(result, QueryResult):
            raise RuntimeError("target run did not return QueryResult")
        if result.error is not None:
            result.error = str(result.error)
        return version, result, None
    finally:
        close = getattr(runner, "close", None)
        if close is not None:
            close()


def _query_old_postgres(setup: list[str], query: str, timeout_s: float) -> _OldResult:
    """Execute the old PG server in a private schema, shared with CVE tier 3."""
    import psycopg2

    runner = PostgresTargetRunner(env=OLD_DSN_ENV)
    version = None
    try:
        version = runner.engine_version
        error = _first_setup_error(runner.setup(setup))
        if error is not None:
            if error.startswith("TimeoutError:"):
                raise subprocess.TimeoutExpired("old PostgreSQL execution", timeout_s)
            return _OldResult(version, [], None, error, None)
        result = runner.run(query, timeout_s=timeout_s)
        if result.timed_out:
            raise subprocess.TimeoutExpired("old PostgreSQL execution", timeout_s)
        return _OldResult(version, normalize_rows(result.rows) if result.ok else [],
                          result.error, None, None)
    except psycopg2.Error:
        # Connection errors can contain DSN fields; keep protocol text fixed.
        return _OldResult(version, [], None, None, "old server execution failed")
    finally:
        runner.close()


def _query_old(
    python: Path,
    engine: str,
    setup: list[str],
    query: str,
    timeout_s: float,
) -> _OldResult:
    payload = {"setup": setup, "query": query, "engine": engine}
    completed = _run_worker(python, payload, timeout_s)
    if completed.returncode != 0:
        return _OldResult(None, [], None, None, "worker process failed")
    text = (completed.stdout or "").strip()
    try:
        document = json.loads(text) if text else None
    except json.JSONDecodeError:
        document = None
    if not isinstance(document, dict):
        return _OldResult(None, [], None, None, "worker output is not valid JSON")
    if document.get("protocol_error"):
        return _OldResult(None, [], None, None, "worker output is not valid JSON")
    version = document.get("engine_version")
    if version is not None and not isinstance(version, str):
        return _OldResult(None, [], None, None, "worker output is not valid JSON")
    version_text = version.strip() if isinstance(version, str) and version.strip() else None
    setup_error = document.get("setup_error")
    error = document.get("error")
    if setup_error is not None and not isinstance(setup_error, str):
        return _OldResult(version_text, [], None, None, "worker output is not valid JSON")
    if error is not None and not isinstance(error, str):
        return _OldResult(version_text, [], None, None, "worker output is not valid JSON")
    if setup_error:
        return _OldResult(version_text, [], None, setup_error, None)
    if version_text is None:
        return _OldResult(None, [], None, None, "worker output is missing engine_version")
    if error:
        return _OldResult(version_text, [], error, None, None)
    try:
        decoded = _decode_rows(document.get("rows"))
    except (TypeError, ValueError, ArithmeticError):
        # A damaged tagged cell, such as a non-decimal decimal string, is a
        # protocol failure. The message stays fixed so the bad text is not echoed.
        return _OldResult(version_text, [], None, None, "worker output is not valid JSON")
    return _OldResult(version_text, _compatible_rows(engine, decoded), None, None, None)


def _run_worker(python: Path, payload: dict[str, Any], timeout_s: float) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if key.upper() != "DEEPSEEK_API_KEY"}
    with tempfile.TemporaryDirectory(prefix="coevo-version-") as empty:
        return subprocess.run(
            [str(python), "-I", str(_WORKER)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            cwd=empty,
            env=env,
            check=False,
        )


def _decode_rows(raw: Any) -> list[list[Any]]:
    if not isinstance(raw, list):
        raise TypeError("rows must be a list")
    decoded: list[list[Any]] = []
    for row in raw:
        if not isinstance(row, list):
            raise TypeError("row must be a list")
        decoded.append([_decode_value(cell) for cell in row])
    return decoded


def _decode_value(cell: Any) -> Any:
    if not isinstance(cell, dict) or not isinstance(cell.get("t"), str):
        raise TypeError("cell is not tagged")
    tag = cell["t"]
    if tag == "null":
        return None
    value = cell.get("v")
    if tag == "bool":
        if not isinstance(value, bool):
            raise TypeError("bool tag")
        return value
    if tag == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("int tag")
        return value
    if tag == "float":
        if value == "nan":
            return float("nan")
        if value == "inf":
            return float("inf")
        if value == "-inf":
            return float("-inf")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("float tag")
        return float(value)
    if tag == "decimal":
        if not isinstance(value, str):
            raise TypeError("decimal tag")
        return Decimal(value)
    if tag == "date":
        if not isinstance(value, str):
            raise TypeError("date tag")
        return date.fromisoformat(value)
    if tag == "datetime":
        if not isinstance(value, str):
            raise TypeError("datetime tag")
        return datetime.fromisoformat(value)
    if tag == "time":
        if not isinstance(value, str):
            raise TypeError("time tag")
        return time.fromisoformat(value)
    if tag == "timedelta":
        if (
            not isinstance(value, list)
            or len(value) != 3
            or any(isinstance(part, bool) or not isinstance(part, int) for part in value)
        ):
            raise TypeError("timedelta tag")
        return timedelta(days=value[0], seconds=value[1], microseconds=value[2])
    if tag == "bytes":
        if not isinstance(value, str):
            raise TypeError("bytes tag")
        return bytes.fromhex(value)
    if tag == "str":
        if not isinstance(value, str):
            raise TypeError("str tag")
        return value
    if tag == "list":
        if not isinstance(value, list):
            raise TypeError("list tag")
        return [_decode_value(item) for item in value]
    if tag == "dict":
        if not isinstance(value, dict):
            raise TypeError("dict tag")
        return {str(key): _decode_value(item) for key, item in value.items()}
    raise ValueError(f"unknown tag {tag}")


def _resolve_old_python(engine: str, explicit: str | None) -> Path | None:
    if explicit is not None:
        candidate = Path(explicit)
        return candidate if candidate.is_file() else None
    root = _venvs_dir() / _OLD_VENVS[engine]
    for relative in ("Scripts/python.exe", "bin/python"):
        candidate = root / relative
        if candidate.is_file():
            return candidate
    return None


def _venvs_dir() -> Path:
    override = os.environ.get("COEVO_VENVS")
    if override:
        return Path(override)
    env = {key: value for key, value in os.environ.items() if key.upper() != "DEEPSEEK_API_KEY"}
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=_CHECKOUT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            env=env,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return _CHECKOUT / ".venvs"
    common = proc.stdout.strip()
    if proc.returncode == 0 and common:
        return Path(common).parent / ".venvs"
    return _CHECKOUT / ".venvs"


def _version_of(engine: str, runner: Any) -> str | None:
    try:
        value = getattr(runner, "engine_version", None)
        if callable(value):
            value = value()
    except Exception:
        value = None
    if isinstance(value, str) and value.strip():
        return value.strip()
    try:
        if engine == "duckdb":
            import duckdb

            return str(duckdb.__version__)
        if engine == "datafusion":
            import datafusion

            return str(datafusion.__version__)
    except Exception:
        return None
    return None


def _first_setup_error(outcomes: Any) -> str | None:
    for item in outcomes:
        _statement, error = item
        if error is not None:
            return str(error)
    return None


def _fields(
    old_version: str | None,
    new_version: str | None,
    old_rows: list[list[Any]],
    new_rows: list[list[Any]],
    direction: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "old_version": old_version,
        "new_version": new_version,
        "old_rows": _canonical_rows(old_rows),
        "new_rows": _canonical_rows(new_rows),
        "direction": direction,
        "direction_evidence": evidence,
    }


def _invalid(
    reason: str,
    full: str,
    *,
    old_version: str | None,
    new_version: str | None,
    old_rows: list[list[Any]],
    new_rows: list[list[Any]],
    error: str | None = None,
) -> Label:
    return invalid_label(
        _ORACLE,
        reason,
        full,
        error=error,
        extra=_fields(old_version, new_version, old_rows, new_rows, "unknown", {}),
    )


register(_ORACLE, judge_case)
