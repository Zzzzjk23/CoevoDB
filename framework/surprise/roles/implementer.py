"""Implementer: one spec in, one SQL case out, accepted only when phi agrees.

The prompt is a pure function of the spec, the vocabulary, and optional feedback
from the previous try. The seed is a cache-key input and never enters the prompt.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from surprise.features.registry import Registry, default_registry
from surprise.features.spec import check_spec
from surprise.features.vocabulary import layer_of
from surprise.harness.contracts import SqlCase
from surprise.theory.contracts import Spec

from .constants import (
    IMPLEMENTER_ATTEMPTS,
    IMPLEMENTER_MAX_TOKENS,
    IMPLEMENTER_TEMPERATURE,
    IMPLEMENTER_TIER,
)
from .gateway import Gateway

_STOP = frozenset({"blocked", "miss", "error"})

# Extra writing notes for ids whose one-line description is easy to miss.
_HINTS: dict[str, str] = {
    "ast:stmt:select": "The statement is a SELECT, including a set operation of SELECTs.",
    "ast:stmt:merge": "Write one MERGE statement, not an INSERT plus an UPDATE.",
    "ast:set_op:except_all": "Write `SELECT ... EXCEPT ALL SELECT ...` with the same number of columns on each side.",
    "ast:set_op:intersect_all": "Write `SELECT ... INTERSECT ALL SELECT ...` with the same number of columns on each side.",
    "ast:set_op:union_all": "Write `SELECT ... UNION ALL SELECT ...`.",
    "ast:set_op:except": "Write `EXCEPT` with no ALL keyword.",
    "ast:set_op:intersect": "Write `INTERSECT` with no ALL keyword.",
    "ast:set_op:union": "Write `UNION` with no ALL keyword.",
    "ast:join:inner": "Write INNER JOIN (or JOIN) with a condition.",
    "ast:join:left": "Write LEFT JOIN.",
    "ast:join:right": "Write RIGHT JOIN.",
    "ast:join:full": "Write FULL JOIN.",
    "ast:join:cross": "Write CROSS JOIN.",
    "ast:join:asof": "Write ASOF JOIN. The ON clause is `alias.column <comparison> other.column`.",
    "ast:join_cond:on": "The join condition is an ON clause.",
    "ast:join_cond:using": "Write USING (column), not ON.",
    "ast:join_cond:natural": "Write NATURAL JOIN.",
    "ast:join_trait:self": "Name the same base table at least twice in the statement.",
    "ast:join_trait:non_equi": "A join ON condition uses <, <=, >, >=, or <>.",
    "ast:subquery:exists": "Write EXISTS (SELECT ...).",
    "ast:subquery:not_exists": "Write NOT EXISTS (SELECT ...).",
    "ast:subquery:in": "Write expr IN (SELECT ...).",
    "ast:subquery:scalar": "Use a parenthesised SELECT as a value.",
    "ast:subquery:all": "Write a comparison against ALL (SELECT ...), for example col > ALL (SELECT other FROM t).",
    "ast:subquery:any": "Write a comparison against ANY (SELECT ...).",
    "ast:subquery:derived": "Use a SELECT in FROM or JOIN as a table.",
    "ast:subquery_pos:select": "Put a subquery in the select list.",
    "ast:subquery_pos:where": "Put the subquery in WHERE.",
    "ast:subquery_pos:from": "Put the subquery in FROM.",
    "ast:subquery_trait:correlated": "The subquery references a qualified column of the outer query, such as outer.col.",
    "ast:corr_cmp:eq": "Inside a correlated subquery, compare an inner column to an outer column with =.",
    "ast:corr_cmp:neq": "Inside a correlated subquery, compare an inner column to an outer column with <> or !=.",
    "ast:window_fn:aggregate": "Write an aggregate with OVER, for example SUM(v) OVER (...).",
    "ast:window_fn:ranking": "Write row_number, rank, or dense_rank with OVER.",
    "ast:window_spec:partition": "OVER contains PARTITION BY. Do not add a frame.",
    "ast:window_spec:order": "OVER contains ORDER BY. Do not add a frame.",
    "ast:window_spec:empty": "Write OVER () with nothing between the parentheses. Do not add a frame.",
    "ast:window_spec:frame": "An explicit frame is judged undetermined. Do not write ROWS, RANGE, or GROUPS.",
    "ast:window_trait:dup_partition_key": "PARTITION BY names the same expression twice, for example PARTITION BY k, k.",
    "ast:window_trait:multiple": "The statement contains two window calls.",
    "ast:clause:where": "Write a WHERE clause on the outer query.",
    "ast:clause:distinct": "Write SELECT DISTINCT.",
    "ast:clause:order_by": "Write ORDER BY on the query itself, not inside OVER and not inside an aggregate.",
    "ast:clause:limit": "Write LIMIT.",
    "ast:bool:and": "Connect two predicates with AND.",
    "ast:bool:or": "Connect two predicates with OR.",
    "ast:cmp:eq": "Use = between two values.",
    "ast:cmp:neq": "Use <> or !=.",
    "ast:cmp:lt": "Use <.",
    "ast:cmp:le": "Use <=.",
    "ast:cmp:gt": "Use >.",
    "ast:cmp:ge": "Use >=.",
    "ast:pred:is_null": "Write IS NULL.",
    "ast:pred:is_not_null": "Write IS NOT NULL.",
    "ast:expr:arith": "Use binary +, -, *, /, or % on numbers.",
    "ast:expr:case": "Write a CASE expression.",
    "ast:expr:interval": "Write an INTERVAL literal, for example INTERVAL 1 DAY.",
    "ast:expr:date_arith": "Add or subtract a DATE value and an INTERVAL literal.",
    "ast:merge:matched": "MERGE has WHEN MATCHED.",
    "ast:merge:not_matched": "MERGE has WHEN NOT MATCHED.",
    "ast:merge:not_matched_by_source": "MERGE has WHEN NOT MATCHED BY SOURCE.",
    "ast:merge:update": "A MERGE action is THEN UPDATE.",
    "ast:merge:delete": "A MERGE action is THEN DELETE.",
    "ast:merge:insert": "A MERGE action is THEN INSERT.",
    "data:table:empty": "One referenced base table has no rows.",
    "data:table:single_row": "One referenced base table has exactly one row. If another feature needs duplicates, use a second table.",
    "data:table:dup_rows": "One referenced base table contains two identical rows. Insert the same tuple twice.",
    "data:table:has_null": "One referenced base table contains a NULL.",
    "data:type:integer": "A referenced table has an INTEGER column.",
    "data:type:date": "A referenced table has a DATE column. Insert a date literal such as DATE '2020-01-01'.",
    "data:type:float": "A referenced table has a DOUBLE or REAL column.",
    "data:type:string": "A referenced table has a VARCHAR column.",
    "data:setop:left_has_dups": "The left input of the set operation returns two identical rows.",
    "data:setop:right_has_dups": "The right input of the set operation returns two identical rows.",
    "data:setop:left_has_null": "The left input of the set operation returns a NULL.",
    "data:setop:right_has_null": "The right input of the set operation returns a NULL.",
}

_DIALECT = {
    "duckdb": "DuckDB SQL. MERGE, QUALIFY, ASOF JOIN, and EXCEPT ALL are available.",
    "datafusion": "DataFusion SQL. EXCEPT ALL, INTERSECT ALL, UNION ALL, and RIGHT JOIN are available.",
}


@dataclass(frozen=True)
class Attempt:
    """One spec's implementation, after at most ``attempts`` gateway calls."""

    spec: dict
    status: str
    ok: bool
    case: SqlCase | None
    phi: Any
    missing: tuple[str, ...]
    forbidden: tuple[str, ...]
    undetermined: tuple[str, ...]
    expect: str | None
    tries: int
    first_ok: bool
    keys: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": dict(self.spec),
            "status": self.status,
            "ok": self.ok,
            "case": None if self.case is None else self.case.to_dict(),
            "phi": None if self.phi is None else self.phi.to_dict(),
            "missing": list(self.missing),
            "forbidden": list(self.forbidden),
            "undetermined": list(self.undetermined),
            "expect": self.expect,
            "tries": self.tries,
            "first_ok": self.first_ok,
            "keys": list(self.keys),
        }


def _as_spec(spec: Spec | dict) -> Spec:
    if isinstance(spec, Spec):
        return spec
    return Spec.from_dict(spec)


def _active(registry: Registry | None) -> Registry:
    return default_registry() if registry is None else registry


def _description(registry: Registry, feature_id: str) -> str:
    if not registry.known(feature_id):
        return "unknown feature"
    return registry.get(feature_id).description


def _feature_lines(registry: Registry, ids: tuple[str, ...], *, frame_banned: bool) -> list[str]:
    lines: list[str] = []
    for feature_id in ids:
        lines.append(f"- {feature_id}: {_description(registry, feature_id)}")
        hint = _HINTS.get(feature_id)
        if frame_banned and feature_id.startswith("ast:window") and feature_id != "ast:window_spec:frame":
            extra = "Do not write an explicit frame (ROWS, RANGE, or GROUPS)."
            hint = extra if hint is None else f"{hint} {extra}"
        if hint:
            lines.append(f"  {hint}")
    return lines


def implementer_prompt(spec: Spec | dict, registry: Registry | None = None, feedback: dict | None = None) -> str:
    """The implementer's prompt. ``feedback`` describes the previous try, if any."""
    target = _as_spec(spec)
    words = _active(registry)
    frame_banned = "ast:window_spec:frame" not in target.required
    dialect = _DIALECT.get(target.engine, f"{target.engine} SQL.")
    lines = [
        "You write one SQL test for a database engine.",
        "Reply with one JSON object and no other text.",
        f"Target engine: {target.engine}",
        f"Dialect: {dialect}",
        f"Target oracle: {target.oracle}",
        "The statement must have every feature in required and every feature in data_properties.",
        "The statement must have none of the features in forbidden.",
        "A feature that the checker cannot decide is a failure, the same as a missing feature.",
        "Required features:",
    ]
    if target.required:
        lines.extend(_feature_lines(words, target.required, frame_banned=frame_banned))
    else:
        lines.append("- (none)")
    lines.append("Data properties:")
    if target.data_properties:
        lines.extend(_feature_lines(words, target.data_properties, frame_banned=frame_banned))
    else:
        lines.append("- (none)")
    lines.append("Forbidden features:")
    if target.forbidden:
        lines.extend(_feature_lines(words, target.forbidden, frame_banned=frame_banned))
    else:
        lines.append("- (none)")
    lines.extend(
        [
            "Known pitfalls on this machine:",
            "- Do not write an explicit frame clause on a window function (ROWS, RANGE, or GROUPS). An explicit frame is always judged undetermined.",
            "- For an ASOF join, write the ON clause as `left_alias.column <comparison> right_alias.column`.",
            "- When the target oracle is tlp and the shape is one TLP does not recognise, put the filter in the query and set predicate to null.",
            "setup is a list of statements that create tables and insert rows. Use small tables, a few rows to a few dozen.",
            "When a data feature is required, the INSERT statements must create that situation. Do not leave setup empty in that case.",
            "query is one statement the engine can execute, usually one SELECT. Put every required feature in that one statement.",
            "predicate is a SQL expression or null. Use null unless the oracle is tlp or norec.",
            'prediction.expect is your bet that this case passes or fails under the target oracle. It is "pass" or "fail".',
            "prediction.why is one sentence.",
            "JSON shape:",
            '{"setup": ["statement"], "query": "statement", "predicate": null, "prediction": {"expect": "pass", "why": "reason"}}',
            "Spec:",
            json.dumps(target.to_dict(), sort_keys=True, ensure_ascii=True),
        ]
    )
    if feedback:
        lines.append("Previous attempt:")
        query = feedback.get("query")
        if isinstance(query, str) and query != "":
            lines.append("query:")
            lines.append(query)
        for name in ("missing", "forbidden", "undetermined"):
            values = feedback.get(name) or ()
            if values:
                lines.append(f"{name}: " + ", ".join(str(item) for item in values))
        reason = feedback.get("reason")
        if isinstance(reason, str) and reason != "":
            lines.append("reason: " + reason)
    return "\n".join(lines)


def _field_error(data: dict) -> str | None:
    """Why this object is not a usable implementer reply. None when it is usable."""
    setup = data.get("setup")
    if not isinstance(setup, list) or any(not isinstance(item, str) for item in setup):
        return "setup must be a list of strings"
    if not isinstance(data.get("query"), str):
        return "query must be a string"
    if "predicate" not in data:
        return "predicate must be a string or null"
    predicate = data.get("predicate")
    if predicate is not None and not isinstance(predicate, str):
        return "predicate must be a string or null"
    prediction = data.get("prediction")
    if not isinstance(prediction, dict) or prediction.get("expect") not in ("pass", "fail"):
        return "prediction.expect must be pass or fail"
    return None


class Implementer:
    """Calls the gateway until a case satisfies the spec, or the attempt budget ends."""

    def __init__(
        self,
        *,
        gateway: Gateway,
        extract: Callable[[SqlCase], Any],
        registry: Registry | None = None,
        seed: int,
        tier: str | None = None,
        attempts: int | None = None,
    ) -> None:
        self.gateway = gateway
        self.extract = extract
        self.registry = registry
        self.seed = seed
        self.tier = IMPLEMENTER_TIER if tier is None else tier
        self.attempts = IMPLEMENTER_ATTEMPTS if attempts is None else attempts

    def implement(self, spec: Spec | dict) -> Attempt:
        target = _as_spec(spec)
        stored = target.to_dict()
        status = "error"
        case: SqlCase | None = None
        phi = None
        missing: tuple[str, ...] = ()
        forbidden: tuple[str, ...] = ()
        undetermined: tuple[str, ...] = ()
        expect: str | None = None
        keys: list[str] = []
        first_ok = False
        tries = 0
        feedback: dict | None = None
        for _ in range(self.attempts):
            prompt = implementer_prompt(spec, self.registry, feedback)
            reply = self.gateway.call(
                "implementer",
                prompt,
                tier=self.tier,
                seed=self.seed,
                temperature=IMPLEMENTER_TEMPERATURE,
                max_tokens=IMPLEMENTER_MAX_TOKENS,
            )
            tries += 1
            keys.append(reply.key)
            if reply.status in _STOP:
                status = reply.status
                break
            if reply.status != "ok" or not isinstance(reply.data, dict):
                status = "rejected"
                feedback = {"reason": reply.reason or "rejected"}
                continue
            data = reply.data
            problem = _field_error(data)
            if problem is not None:
                status = "rejected"
                note: dict[str, Any] = {"reason": problem}
                if isinstance(data.get("query"), str):
                    note["query"] = data["query"]
                feedback = note
                continue
            expect = data["prediction"]["expect"]
            try:
                built = SqlCase(
                    engine=target.engine,
                    setup=tuple(data["setup"]),
                    query=data["query"],
                    predicate=data["predicate"],
                )
            except ValueError as exc:
                status = "bad_case"
                feedback = {"query": data["query"], "reason": str(exc)}
                continue
            case = built
            phi = self.extract(case)
            check = check_spec(phi, target, self.registry)
            missing = check.missing
            forbidden = check.forbidden
            undetermined = check.undetermined
            if check.ok:
                status = "ok"
                first_ok = tries == 1
                break
            status = "spec_unmet"
            feedback = {
                "query": case.query,
                "missing": missing,
                "forbidden": forbidden,
                "undetermined": undetermined,
            }
        return Attempt(
            spec=stored,
            status=status,
            ok=status == "ok",
            case=case,
            phi=phi,
            missing=missing,
            forbidden=forbidden,
            undetermined=undetermined,
            expect=expect,
            tries=tries,
            first_ok=first_ok,
            keys=tuple(keys),
        )


def _kind_of(spec_id: str) -> str:
    if "/" not in spec_id:
        return spec_id
    return spec_id.split("/", 1)[1]


def implementer_report(specs: list[dict], implementer: Implementer) -> dict[str, Any]:
    """Run ``implement`` on each ``{"id", "spec"}`` row and summarise the phi checks."""
    rows: list[dict[str, Any]] = []
    by_kind: dict[str, dict[str, int]] = {}
    first_ok = 0
    final_ok = 0
    for item in specs:
        attempt = implementer.implement(item["spec"])
        if attempt.first_ok:
            first_ok += 1
        if attempt.ok:
            final_ok += 1
        kind = _kind_of(item["id"])
        bucket = by_kind.setdefault(kind, {"specs": 0, "first_ok": 0, "final_ok": 0})
        bucket["specs"] += 1
        bucket["first_ok"] += int(attempt.first_ok)
        bucket["final_ok"] += int(attempt.ok)
        rows.append(
            {
                "id": item["id"],
                "status": attempt.status,
                "tries": attempt.tries,
                "first_ok": attempt.first_ok,
                "ok": attempt.ok,
                "missing": list(attempt.missing),
                "forbidden": list(attempt.forbidden),
                "undetermined": list(attempt.undetermined),
                "expect": attempt.expect,
            }
        )
    count = len(specs)
    calls = implementer.gateway.totals()["by_role"].get("implementer", {})
    return {
        "specs": count,
        "first_ok": first_ok,
        "final_ok": final_ok,
        "first_rate": 0.0 if count == 0 else first_ok / count,
        "final_rate": 0.0 if count == 0 else final_ok / count,
        "by_kind": by_kind,
        "rows": rows,
        "calls": calls,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="surprise.roles.implementer")
    parser.add_argument("--specs", required=True, help="JSON list of {id, spec}")
    parser.add_argument("--cache", required=True, help="gateway cache directory")
    parser.add_argument("--out", required=True, help="report JSON path")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-calls", type=int, default=None)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)
    specs = json.loads(Path(args.specs).read_text(encoding="utf-8"))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.offline:
        transport = None
    else:
        from surprise.roles.transport import DeepSeekTransport

        transport = DeepSeekTransport()
    from surprise.features.extract import extract

    gateway = Gateway(
        cache_dir=args.cache,
        ledger_path=out.with_name(out.stem + ".calls.jsonl"),
        max_calls=args.max_calls,
        transport=transport,
    )
    report = implementer_report(
        specs,
        Implementer(gateway=gateway, extract=extract, seed=args.seed),
    )
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"specs={report['specs']} first_ok={report['first_ok']} final_ok={report['final_ok']} "
        f"first_rate={report['first_rate']:.4f} final_rate={report['final_rate']:.4f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
