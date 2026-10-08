"""Child process for one isolated execution or one oracle judgement.

stdin: one JSON object. stdout: one JSON object. The API key is not read.
"""

from __future__ import annotations

import json
import sys
from typing import Any


def main() -> int:
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        if not isinstance(payload, dict):
            result = _failure("RuntimeError", "payload must be a JSON object")
        else:
            _apply_sys_path(payload.get("sys_path"))
            result = _dispatch(payload)
    except Exception as exc:  # noqa: BLE001 - the parent turns this into a result
        result = _failure(type(exc).__name__, str(exc), type(exc).__module__)
    sys.stdout.write(json.dumps(result, default=str))
    sys.stdout.write("\n")
    sys.stdout.flush()
    return 0


def _dispatch(payload: dict[str, Any]) -> dict[str, Any]:
    op = payload.get("op")
    if op == "execute":
        return _execute(payload)
    if op == "judge":
        return _judge(payload)
    if op == "interventions":
        from surprise.harness.cve.criterion import interventions_from_payload

        return interventions_from_payload(payload)
    if op == "attribute":
        from surprise.harness.cve.criterion import attribute_from_payload

        return attribute_from_payload(payload)
    if op == "diagnose":
        from surprise.harness.cve.tier3 import diagnose_from_payload

        return diagnose_from_payload(payload)
    return _failure("RuntimeError", f"unknown op {op!r}")


def _execute(payload: dict[str, Any]) -> dict[str, Any]:
    from surprise.harness.cve.isolate import IsolatedResult, load_callable
    from surprise.harness.oracles.registry import runner_factory_for

    factory_ref = payload.get("factory")
    if isinstance(factory_ref, str) and factory_ref:
        factory = load_callable(factory_ref)
    else:
        engine = payload.get("engine")
        if not isinstance(engine, str):
            return {"op": "execute", **IsolatedResult("error", [], "engine missing", None).to_dict()}
        factory = runner_factory_for(engine)
    engine = payload.get("engine")
    setup = payload.get("setup")
    prelude = payload.get("prelude")
    query = payload.get("query")
    timeout_s = payload.get("timeout_s")
    if not isinstance(engine, str) or not isinstance(setup, list) or not isinstance(prelude, list):
        return {"op": "execute", **IsolatedResult("error", [], "malformed execute payload", None).to_dict()}
    if not isinstance(query, str) or isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)):
        return {"op": "execute", **IsolatedResult("error", [], "malformed execute payload", None).to_dict()}
    try:
        runner = factory()
    except Exception as exc:  # noqa: BLE001 - engine construction is a result
        return {"op": "execute", **IsolatedResult("error", [], f"{type(exc).__name__}: {exc}", None).to_dict()}
    try:
        return {"op": "execute", **_run_statements(runner, setup, prelude, query, float(timeout_s)).to_dict()}
    finally:
        try:
            runner.close()
        except Exception:
            pass


def _run_statements(runner: Any, setup: list[Any], prelude: list[Any], query: str, timeout_s: float) -> Any:
    from surprise.harness.cve.isolate import IsolatedResult
    from surprise.harness.cve.session import json_rows

    try:
        outcomes = runner.setup(list(setup))
    except Exception as exc:  # noqa: BLE001
        return IsolatedResult("error", [], f"{type(exc).__name__}: {exc}", None)
    for item in outcomes:
        error = item[1] if isinstance(item, (list, tuple)) and len(item) >= 2 else "setup failed"
        if error is not None:
            return IsolatedResult("error", [], str(error), None)
    for statement in prelude:
        if not isinstance(statement, str):
            return IsolatedResult("error", [], "prelude statement must be a string", None)
        failed, _rows = _one_statement(runner, statement, timeout_s)
        if failed is not None:
            return failed
    failed, rows = _one_statement(runner, query, timeout_s)
    if failed is not None:
        return failed
    return IsolatedResult("ok", json_rows(rows), None, None)


def _one_statement(runner: Any, sql: str, timeout_s: float) -> tuple[Any, list[Any]]:
    """Return ``(failure, rows)``. ``failure`` is an ``IsolatedResult`` or None."""
    from surprise.harness.cve.isolate import IsolatedResult

    try:
        result = runner.run(sql, timeout_s=timeout_s)
    except Exception as exc:  # noqa: BLE001
        return IsolatedResult("error", [], f"{type(exc).__name__}: {exc}", None), []
    if bool(getattr(result, "timed_out", False)):
        error = getattr(result, "error", None)
        text = error if isinstance(error, str) else None
        return IsolatedResult("timeout", [], text, None), []
    error = getattr(result, "error", None)
    if error is not None:
        return IsolatedResult("error", [], str(error), None), []
    return None, list(getattr(result, "rows", []) or [])


def _judge(payload: dict[str, Any]) -> dict[str, Any]:
    from surprise.harness.contracts import SqlCase
    from surprise.harness.cve.isolate import load_callable
    from surprise.harness.cve.session import run_judge
    from surprise.harness.oracles.registry import runner_factory_for

    try:
        case = SqlCase.from_dict(payload.get("case"))
    except (TypeError, ValueError) as exc:
        return _failure("ValueError", str(exc))
    oracle = payload.get("oracle")
    timeout_s = payload.get("timeout_s")
    if not isinstance(oracle, str) or isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)):
        return _failure("ValueError", "malformed judge payload")
    factory_ref = payload.get("runner_factory")
    if isinstance(factory_ref, str) and factory_ref:
        factory = load_callable(factory_ref)
    else:
        factory = runner_factory_for(case.engine)
    refs = payload.get("reference_factories")
    reference_factories = None
    if refs is not None:
        if not isinstance(refs, dict):
            return _failure("ValueError", "reference_factories must be an object")
        reference_factories = {str(engine): load_callable(ref) for engine, ref in refs.items()}
    prelude = payload.get("prelude")
    if prelude is None:
        prelude = []
    if not isinstance(prelude, list) or not all(isinstance(item, str) for item in prelude):
        return _failure("ValueError", "prelude must be a list of strings")
    try:
        label, transcript = run_judge(
            case,
            oracle,
            factory=factory,
            timeout_s=float(timeout_s),
            prelude=tuple(prelude),
            rewrite_rule=payload.get("rewrite_rule"),
            paired_query=payload.get("paired_query"),
            old_python=payload.get("old_python"),
            reference_factories=reference_factories,
        )
    except Exception as exc:  # noqa: BLE001 - the parent re-raises this
        return _failure(type(exc).__name__, str(exc), type(exc).__module__)
    return {"op": "judge", "label": label.to_dict(), "transcript": transcript}


def _apply_sys_path(entries: Any) -> None:
    if not isinstance(entries, list):
        return
    for entry in reversed(entries):
        if not isinstance(entry, str) or entry == "":
            continue
        try:
            sys.path.remove(entry)
        except ValueError:
            pass
        sys.path.insert(0, entry)


def _failure(name: str, message: str, module: str = "builtins") -> dict[str, str]:
    return {"op": "raise", "type": name, "module": module, "message": message}


if __name__ == "__main__":
    sys.exit(main())
