"""Old-engine subprocess for version differential.

The parent runs this file by path under the old interpreter:

    <old python> -I version_worker.py

stdin is one JSON object: setup statements, the full query, and the engine
name (``duckdb`` or ``datafusion``). stdout is one JSON object with the real
library version and tagged cell values. This process does not judge labels,
does not read secrets, and does not import the harness.

Decimal, date, datetime, time, timedelta, and bytes are tagged so the parent
can rebuild the Python values and normalize them. The duckdb path imports
only duckdb and the standard library. The datafusion path imports only
datafusion and the standard library.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        result = _execute(payload)
    except Exception as exc:  # noqa: BLE001 - protocol failure, still JSON
        result = {"protocol_error": f"{type(exc).__name__}: {exc}"}
    json.dump(result, sys.stdout, allow_nan=False)
    sys.stdout.write("\n")
    return 0


def _execute(payload: object) -> dict:
    if not isinstance(payload, dict):
        return {"protocol_error": "payload must be a JSON object"}
    engine = payload.get("engine")
    setup = payload.get("setup")
    query = payload.get("query")
    if engine not in ("duckdb", "datafusion"):
        return {"protocol_error": "engine must be duckdb or datafusion"}
    if not isinstance(setup, list) or not all(isinstance(item, str) for item in setup):
        return {"protocol_error": "setup must be a list of strings"}
    if not isinstance(query, str):
        return {"protocol_error": "query must be a string"}
    if engine == "duckdb":
        return _run_duckdb(setup, query)
    return _run_datafusion(setup, query)


def _run_duckdb(setup: list[str], query: str) -> dict:
    import duckdb

    version = str(duckdb.__version__)
    conn = duckdb.connect(":memory:")
    try:
        for statement in setup:
            sql = statement.strip().rstrip(";")
            if not sql:
                continue
            try:
                conn.execute(sql)
            except Exception as exc:  # noqa: BLE001 - reported, not judged
                return _failure(version, setup_error=_error_text(exc))
        try:
            cursor = conn.execute(query)
            rows = cursor.fetchall()
            columns = [item[0] for item in (cursor.description or [])]
        except Exception as exc:  # noqa: BLE001 - reported, not judged
            return _failure(version, error=_error_text(exc))
    finally:
        conn.close()
    return _success(version, rows, columns)


def _run_datafusion(setup: list[str], query: str) -> dict:
    import datafusion

    version = str(datafusion.__version__)
    ctx = datafusion.SessionContext()
    for statement in setup:
        try:
            ctx.sql(statement).collect()
        except Exception as exc:  # noqa: BLE001 - reported, not judged
            return _failure(version, setup_error=_error_text(exc))
    try:
        batches = ctx.sql(query).collect()
    except Exception as exc:  # noqa: BLE001 - reported, not judged
        return _failure(version, error=_error_text(exc))
    columns: list[str] = []
    rows: list[list] = []
    for batch in batches:
        if not columns:
            columns = list(batch.schema.names)
        extracted = [batch.column(index).to_pylist() for index in range(batch.num_columns)]
        for row_index in range(batch.num_rows):
            rows.append([column[row_index] for column in extracted])
    return _success(version, rows, columns)


def _success(version: str, rows: list, columns: list[str]) -> dict:
    return {
        "engine_version": version,
        "setup_error": None,
        "error": None,
        "columns": columns,
        "rows": [_encode_row(row) for row in rows],
    }


def _failure(version: str, *, setup_error: str | None = None, error: str | None = None) -> dict:
    return {
        "engine_version": version,
        "setup_error": setup_error,
        "error": error,
        "columns": [],
        "rows": [],
    }


def _error_text(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def _encode_row(row: object) -> list:
    return [_encode(value) for value in row]


def _encode(value: object) -> dict:
    """Tag one cell. Datetime is checked before date because it is a subclass."""
    if value is None:
        return {"t": "null"}
    if isinstance(value, bool):
        return {"t": "bool", "v": value}
    if isinstance(value, int):
        return {"t": "int", "v": value}
    if isinstance(value, float):
        if math.isnan(value):
            return {"t": "float", "v": "nan"}
        if math.isinf(value):
            return {"t": "float", "v": "inf" if value > 0 else "-inf"}
        return {"t": "float", "v": value}
    if isinstance(value, Decimal):
        return {"t": "decimal", "v": format(value, "f")}
    if isinstance(value, datetime):
        return {"t": "datetime", "v": value.isoformat()}
    if isinstance(value, date):
        return {"t": "date", "v": value.isoformat()}
    if isinstance(value, time):
        return {"t": "time", "v": value.isoformat()}
    if isinstance(value, timedelta):
        return {
            "t": "timedelta",
            "v": [value.days, value.seconds, value.microseconds],
        }
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"t": "bytes", "v": bytes(value).hex()}
    if isinstance(value, str):
        return {"t": "str", "v": value}
    if isinstance(value, (list, tuple)):
        return {"t": "list", "v": [_encode(item) for item in value]}
    if isinstance(value, dict):
        return {"t": "dict", "v": {str(key): _encode(item) for key, item in value.items()}}
    raise TypeError(f"unsupported cell type {type(value).__name__}")


if __name__ == "__main__":
    sys.exit(main())
