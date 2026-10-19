"""Run SQLancer and submit its reported cases to the common harness/CVE judge.

SQLancer's assertion is evidence to replay, never a label. Replay mode uses the
same parser and judge without starting Java.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import signal
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.tokens import TokenType

from surprise.harness.contracts import SqlCase
from surprise.harness.evaluate import evaluate_final
from surprise.harness.ledger import Ledger
from surprise.harness.manifest import build_manifest
from surprise.hunter.extractor import PhiExtractor


class UsageError(ValueError):
    """A request cannot start a run."""


@dataclass
class ParsedReport:
    row: dict[str, Any]
    case: SqlCase | None


def checkout_root() -> Path:
    repo = Path(__file__).resolve().parents[3]
    common = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"], cwd=repo,
        capture_output=True, text=True, check=True, timeout=30,
    ).stdout.strip()
    return (repo / common).resolve().parent


def classpath(home: Path) -> list[Path]:
    """Order explicit jars, replacing lib artifacts by their override artifact."""
    overrides = sorted((home / "override").glob("*.jar"))
    artifact = lambda path: re.sub(r"-\d[^/]*\.jar$", "", path.name)
    replaced = {artifact(path) for path in overrides}
    main = sorted(home.glob("sqlancer-*.jar"))
    if len(main) != 1:
        raise RuntimeError(f"expected one sqlancer-*.jar in {home}, found {len(main)}")
    libs = [path for path in sorted((home / "lib").glob("*.jar")) if artifact(path) not in replaced]
    return overrides + main + libs


def find_tools() -> tuple[Path, Path]:
    root = checkout_root()
    if os.environ.get("COEVO_JAVA"):
        java = Path(os.environ["COEVO_JAVA"]).resolve()
    else:
        candidates = sorted((root / ".orch" / "jdk").glob("*/bin/java.exe" if os.name == "nt" else "*/bin/java"))
        if len(candidates) != 1:
            raise RuntimeError(f"expected one .orch/jdk/*/bin/java, found {len(candidates)}")
        java = candidates[0]
    home = Path(os.environ.get("COEVO_SQLANCER_HOME", root / ".orch" / "sqlancer")).resolve()
    if not java.is_file():
        raise RuntimeError(f"Java executable does not exist: {java}")
    if not home.is_dir():
        raise RuntimeError(f"SQLancer home does not exist: {home}")
    return java, home


def _unescape(text: str) -> str:
    # SQLLoggableFactory escapes only physical line endings, not SQL backslashes.
    return text.replace(r"\n", "\n").replace(r"\r", "\r")


def _uncomment(line: str) -> str:
    return re.sub(r"^(?:--\s*)+", "", line).strip()


def _top_tokens(sql: str):
    depth = 0
    for token in sqlglot.Dialect.get_or_raise("duckdb").tokenize(sql):
        if token.token_type == TokenType.R_PAREN:
            depth -= 1
        if depth == 0:
            yield token
        if token.token_type == TokenType.L_PAREN:
            depth += 1


def _queries(lines: list[str]) -> list[str]:
    """Read query lines in exception messages and the final commented reproducer."""
    result = []
    for line in lines:
        text = _uncomment(line)
        # TLP's header quotes the queries, sometimes followed by cardinalities.
        quoted = re.match(r'(?:First|Second) query\s*:\s*"(.*)"(?:, whose cardinality.*)?$', text)
        if quoted:
            text = quoted.group(1)
            # Content mismatch embeds a second commented query in the message.
            if text.startswith("--"):
                text = _uncomment(text)
        else:
            text = re.sub(r"^[\w.$]+AssertionError:\s*", "", text)
        if not re.match(r"SELECT\b", text, re.I):
            continue
        try:
            boundaries = [t.start for t in _top_tokens(text) if t.token_type == TokenType.SEMICOLON]
        except SqlglotError:
            boundaries = []
        start = 0
        for end in boundaries + [len(text)]:
            part = text[start:end].strip()
            if re.match(r"SELECT\b", part, re.I) and part not in result:
                result.append(part)
            start = end + 1
    return result


def _parts(sql: str) -> tuple[str, str, str | None]:
    """Validate with the AST, slice with token offsets to preserve the source SQL."""
    tree = sqlglot.parse_one(sql, read="duckdb")
    if not isinstance(tree, exp.Select):
        raise ValueError("unsupported_shape")
    forbidden = ("group", "having", "order", "limit", "offset", "distinct", "qualify", "windows", "with_", "into", "locks")
    if any(tree.args.get(key) for key in forbidden):
        raise ValueError("unsupported_shape")
    if any(node.find_ancestor(exp.Select) is tree for node in tree.find_all(exp.Window)):
        raise ValueError("unsupported_shape")
    tokens = list(_top_tokens(sql))
    select = next((t for t in tokens if t.token_type == TokenType.SELECT), None)
    from_ = next((t for t in tokens if t.token_type == TokenType.FROM), None)
    where = next((t for t in tokens if t.token_type == TokenType.WHERE), None)
    if select is None or from_ is None or select.start != 0:
        raise ValueError("unsupported_shape")
    columns = sql[select.end + 1:from_.start].strip()
    source = sql[from_.end + 1:where.start if where else len(sql)].strip()
    predicate = sql[where.end + 1:].strip() if where else None
    if not columns or not source or predicate == "":
        raise ValueError("unsupported_shape")
    return columns, source, predicate


def _first_partition(sql: str) -> str:
    # SQLancer can log the three TLP partitions as one UNION ALL query. This
    # union belongs to its oracle; the original query still must be a SELECT.
    for token in _top_tokens(sql):
        if token.token_type == TokenType.UNION:
            return sql[:token.start].strip()
    return sql


def parse_log(path: Path) -> ParsedReport:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    seed_index = next((i for i, line in enumerate(lines) if re.match(r"^--\s*seed value:", line)), len(lines))
    header = "\n".join(lines[:seed_index])
    first = _uncomment(lines[0]) if lines else ""
    assertion = re.match(r"(?:[\w$]+\.)*AssertionError(?::\s*(.*))?$", first)
    message = assertion.group(1) or "" if assertion else ""
    mismatch = message.startswith(("the counts mismatch", "The size of the result sets mismatch", "The content of the result sets mismatch"))
    kind = "mismatch" if assertion and mismatch else "unexpected_error" if assertion else "tool_error"
    sqlancer_oracle = "NOREC" if "NoRECOracle" in header else "WHERE" if "TLPWhereOracle" in header else None
    version = re.search(r"^--\s*Database version:\s*(.+)$", header, re.M)
    seed_match = re.match(r"^--\s*seed value:\s*(-?\d+)", lines[seed_index]) if seed_index < len(lines) else None
    setup = [_unescape(line.strip().removesuffix(";")) for line in lines[seed_index + 1:]
             if line.strip() and not line.startswith("--")]
    oracle = {"NOREC": "norec", "WHERE": "tlp"}.get(sqlancer_oracle)
    row = {"log": path.name, "kind": kind, "sqlancer_oracle": sqlancer_oracle,
           "database_version": version.group(1).strip() if version else None,
           "seed": int(seed_match.group(1)) if seed_match else None,
           "oracle": oracle, "converted": False, "reason": None, "record_id": None}
    if kind == "tool_error":
        row["reason"] = "tool_error"
        return ParsedReport(row, None)
    query_lines = lines[:seed_index] + [line for line in lines[seed_index + 1:] if line.startswith("--")]
    expanded = [part for line in query_lines for part in _unescape(line).splitlines()]
    queries = _queries(expanded)
    if not queries or oracle is None:
        row["reason"] = "not_a_query"
        return ParsedReport(row, None)
    try:
        columns, source, predicate = _parts(queries[0])
        if oracle == "tlp" and predicate is None:
            if len(queries) < 2:
                raise ValueError("unsupported_shape")
            _, _, predicate = _parts(_first_partition(queries[1]))
        if predicate is None:
            raise ValueError("unsupported_shape")
    except (SqlglotError, ValueError):
        row["reason"] = "unsupported_shape"
        return ParsedReport(row, None)
    query = f"SELECT {'*' if oracle == 'norec' else columns} FROM {source}"
    row["converted"] = True
    return ParsedReport(row, SqlCase(engine="duckdb", setup=setup, query=query, predicate=predicate))


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=1, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")


def _append(handle, row: dict[str, Any]) -> None:
    handle.write(json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n")
    handle.flush()


def _stop_java(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=30)


def _executions(path: Path) -> int:
    # Stream stdout: large campaigns need not fit their log into memory.
    count = 0
    if path.is_file():
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                for match in re.finditer(r"Executed (\d+) queries", line):
                    count = int(match.group(1))
    return count


def run(out, *, seed: int, engine: str = "duckdb", max_minutes: float | None = None,
        oracles=("NOREC", "WHERE"), threads: int = 1, replay_logs=None,
        run_id: str | None = None) -> dict[str, Any]:
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise UsageError("seed must be an integer")
    if engine != "duckdb":
        raise UsageError("engine must be duckdb")
    if isinstance(threads, bool) or not isinstance(threads, int) or threads < 1:
        raise UsageError("threads must be a positive integer")
    if isinstance(oracles, str) or not oracles or any(o not in ("NOREC", "WHERE") for o in oracles):
        raise UsageError("oracles must contain NOREC or WHERE")
    oracles = tuple(dict.fromkeys(oracles))
    if max_minutes is not None and (isinstance(max_minutes, bool) or not isinstance(max_minutes, (int, float))
                                    or not math.isfinite(max_minutes) or max_minutes <= 0):
        raise UsageError("max_minutes must be finite and positive")
    if replay_logs is None and max_minutes is None:
        raise UsageError("max_minutes is required without replay_logs")
    replay = Path(replay_logs).resolve() if replay_logs is not None else None
    if replay is not None and not replay.is_dir():
        raise UsageError("replay_logs must be a directory")
    if run_id is not None and (not isinstance(run_id, str) or not run_id.strip()):
        raise UsageError("run_id must be non-empty")
    run_id = run_id if run_id is not None else f"sqlancer-s{seed}"
    directory = Path(out).resolve()
    if directory.exists() and (not directory.is_dir() or any(directory.iterdir())):
        raise UsageError("out must not exist or must be empty")
    directory.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    start = time.monotonic()
    deadline = start + max_minutes * 60 if max_minutes is not None else math.inf
    work = directory / "sqlancer"
    work.mkdir()
    stdout_path = work / "stdout.txt"
    config = {"kind": "sqlancer", "engine": engine, "seed": seed, "oracles": list(oracles),
              "threads": threads, "max_minutes": max_minutes, "replay": replay is not None}
    _write_json(directory / "config.json", config)
    stats: dict[str, Any] = {"commit": None, "jar_sha256": None, "jdbc": [], "java": None,
                             "command": None, "oracles": list(oracles), "threads": threads,
                             "reports": 0, "kinds": {k: 0 for k in ("mismatch", "unexpected_error", "tool_error")},
                             "converted": 0, "judged": 0, "unjudged": 0, "pid": None}
    proc = None
    ledger = None
    pending: BaseException | None = None
    error_text = ""
    status = "error"
    seen: dict[Path, ParsedReport] = {}
    sizes: dict[Path, int] = {}
    labels: dict[str, int] = {}
    log_dir = replay if replay is not None else work / "logs" / engine
    extractor = PhiExtractor()

    def paths() -> list[Path]:
        pattern = "*.log" if replay is not None else "database*.log"
        return sorted(p for p in log_dir.glob(pattern) if not p.name.endswith("-cur.log"))

    def collect(*, finished: bool, judge: bool) -> None:
        for path in paths():
            if path in seen:
                continue
            size = path.stat().st_size
            stable = sizes.get(path) == size
            sizes[path] = size
            if not finished and not stable:
                continue
            parsed = parse_log(path)
            seen[path] = parsed
            if parsed.case is None or not judge or time.monotonic() >= deadline:
                continue
            assert ledger is not None
            row = parsed.row
            record = evaluate_final(
                parsed.case, row["oracle"], ledger=ledger, run_id=run_id, purpose="sqlancer",
                spec={key: row[key] for key in ("log", "sqlancer_oracle", "kind")},
                phi=extractor.extract(parsed.case).to_dict(), theory_version=None, p_t=None, diagnose=True,
            )
            row["record_id"] = record.record_id
            label = record.label
            labels[label.y] = labels.get(label.y, 0) + 1
            kind = label.fail_kind if label.y == "fail" else label.invalid_reason if label.y == "invalid" else None
            _append(progress, {"seq": record.seq, "record_id": record.record_id, "oracle": row["oracle"],
                               "y": label.y, "kind": kind, "log": path.name,
                               "elapsed_s": round(time.monotonic() - start, 2)})

    with (directory / "progress.jsonl").open("w", encoding="utf-8", newline="\n") as progress:
        try:
            java, home = find_tools()
            jars = classpath(home)
            main_jar = next(p for p in jars if p.parent == home)
            with main_jar.open("rb") as jar_file:
                jar_sha256 = hashlib.file_digest(jar_file, "sha256").hexdigest()
            stats.update(commit=(home / "COMMIT").read_text(encoding="utf-8").strip(),
                         jar_sha256=jar_sha256,
                         jdbc=sorted(p.name for p in jars if "jdbc" in p.name.lower()))
            if replay is None:
                version = subprocess.run([str(java), "-version"], capture_output=True, text=True, check=True, timeout=30)
                stats["java"] = (version.stderr or version.stdout).splitlines()[0]
            ledger = Ledger(directory / "ledger.sqlite")
            manifest = build_manifest(run_id)
            manifest.update(baseline="sqlancer", sqlancer={k: stats[k] for k in ("commit", "jar_sha256", "jdbc", "oracles", "threads")})
            ledger.start_run(run_id, manifest)
            if replay is not None:
                collect(finished=True, judge=True)
                status = "replayed"
            else:
                command = [str(java), "-cp", os.pathsep.join(map(str, jars)), "sqlancer.Main",
                           "--random-seed", str(seed), "--num-threads", str(threads),
                           "--timeout-seconds", str(max(1, math.ceil(max_minutes * 60))),
                           "--num-tries", "1000000", "--log-each-select", "false",
                           "--log-execution-time", "false", engine]
                for oracle in oracles:
                    command.extend(["--oracle", oracle])
                stats["command"] = command
                with stdout_path.open("w", encoding="utf-8") as stdout:
                    proc = subprocess.Popen(command, cwd=work, stdout=stdout, stderr=subprocess.STDOUT,
                                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
                    stats["pid"] = proc.pid
                    while time.monotonic() < deadline:
                        exited = proc.poll() is not None
                        collect(finished=exited, judge=True)
                        if exited:
                            if proc.returncode != 0:
                                raise RuntimeError(f"SQLancer exited with code {proc.returncode}; see sqlancer/stdout.txt")
                            break
                        time.sleep(min(2.0, max(0, deadline - time.monotonic())))
                status = "budget_minutes"
        except KeyboardInterrupt as exc:
            status, pending = "interrupted", exc
        except Exception as exc:
            status, pending = "error", exc
            error_text = traceback.format_exc()
        finally:
            try:
                _stop_java(proc)
                collect(finished=True, judge=False)
            except Exception as exc:
                error_text += traceback.format_exc()
                if pending is None:
                    status, pending = "error", exc
            finally:
                if ledger is not None:
                    ledger.close()

    with (work / "reports.jsonl").open("w", encoding="utf-8", newline="\n") as reports:
        for parsed in seen.values():
            row = parsed.row
            _append(reports, row)
            stats["kinds"][row["kind"]] += 1
            stats["converted"] += int(row["converted"])
            stats["judged"] += int(row["record_id"] is not None)
    stats["reports"] = len(seen)
    stats["unjudged"] = stats["converted"] - stats["judged"]
    finished = datetime.now(timezone.utc)
    report = {"run_id": run_id, "seed": seed, "engine": engine, "status": status,
              "executions": None if replay is not None else _executions(stdout_path),
              "started_at": started.isoformat(), "finished_at": finished.isoformat(),
              "wall_s": round(time.monotonic() - start, 2), "labels": labels, "sqlancer": stats}
    _write_json(directory / "report.json", report)
    if error_text:
        (directory / "error.txt").write_text(error_text, encoding="utf-8")
    if pending is not None:
        raise pending
    return report


def main(argv: list[str] | None = None) -> int:
    def interrupt(*_):
        raise KeyboardInterrupt

    for name in ("SIGBREAK", "SIGTERM"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), interrupt)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--engine", choices=["duckdb"], default="duckdb")
    parser.add_argument("--max-minutes", type=float)
    parser.add_argument("--oracle", choices=["NOREC", "WHERE"], action="append", dest="oracles")
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--replay-logs")
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    if args.oracles is None:
        args.oracles = ("NOREC", "WHERE")
    try:
        report = run(**vars(args))
    except UsageError as exc:
        parser.error(str(exc))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {str(exc).encode('ascii', 'replace').decode('ascii')}", file=sys.stderr)
        return 1
    print(f"{report['status']} {report['executions']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
