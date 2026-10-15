"""Oracle inventor: propose a rewrite template, keep it only when engines agree.

The prompt is a pure function of the frozen rules, the accepted library, and the
engine names. Record ids, hypothesis ids, run ids, clocks, random values, and
absolute paths never enter it. A template is not a label. The harness decides.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Sequence

from surprise.harness.constants import QUERY_TIMEOUT_S
from surprise.harness.oracles.rewrites import (
    LIBRARY_RULE_PREFIX,
    LIBRARY_SCHEMA,
    RULES,
    apply_template,
    load_library,
    template_problem,
)

from .base import Role, RoleContext
from .constants import (
    ORACLE_ACCEPT_ENGINES,
    ORACLE_ACCEPT_INSTANCES,
    ORACLE_ACCEPT_MIN_ENGINES,
    ORACLE_CALLS_PER_RUN,
    ORACLE_EVERY,
    ORACLE_MAX_TOKENS,
    ORACLE_RULES_PER_CALL,
    ORACLE_SCAN_MAX,
    ORACLE_TEMPERATURE,
    ORACLE_TIER,
)

# A 0-row or 1-row agreement cannot tell LIMIT or DISTINCT from an identity.
_MIN_RESULT_ROWS = 2
_NAME = re.compile(r"^[a-z0-9_]{1,36}$")
_PROPOSER = "oracle_inventor"
_LIBRARY_NAME = "rewrites.json"
_BOOK_NAME = "rewrites.jsonl"

_DML = (
    "ALTER", "CALL", "COPY", "CREATE", "DELETE", "DROP", "EXECUTE", "GRANT",
    "INSERT", "MERGE", "REVOKE", "TRUNCATE", "UPDATE",
)

_CORPUS: list[Any] | None = None


def build(ctx: RoleContext) -> OracleInventor:
    """The plugin entry. The runtime calls this only when the role is on."""
    return OracleInventor(ctx)


def oracle_prompt(*, library: dict, engines, call: int | None = None) -> str:
    """One English prompt. Same library, engines, and call round give the same text.

    ``call`` is the 1-based round of this inventor call. The gateway caches a
    reply by prompt text, and two rounds can share a library, so the round
    keeps those calls distinct. It is not a record id.
    """
    names = _engine_names(engines)
    lines = [
        "Invent SQL rewrites for metamorphic testing.",
        "A rewrite must leave the result multiset unchanged under bag semantics,",
        "SQL three-valued logic, and duplicate rows.",
        "It must hold on every engine listed here:",
        ", ".join(names) if names else "(none)",
        "",
        "The harness already has these frozen rules. Do not propose their names.",
    ]
    for name, entry in RULES.items():
        lines.append(f"- {name}: {entry['proof']}")
    lines.extend([
        "",
        "Propose templates of only two kinds.",
        "query_wrap contains exactly one {q}, and {q} stands for the whole statement.",
        "predicate_wrap contains one, two, or three {p}.",
        "Each {p} stands for the top-level WHERE predicate.",
        "When a predicate template is applied, that predicate is wrapped in parentheses.",
        "A template must not contain a semicolon, a comment (-- or /*),",
        "a data-modifying keyword (" + ", ".join(_DML) + "),",
        "or any brace other than the placeholders.",
        "query_wrap must not contain {p}. predicate_wrap must not contain {q}.",
        "Examples:",
        "query_wrap: SELECT * FROM ({q}) AS llm_sub",
        "query_wrap: WITH llm_cte AS ({q}) SELECT * FROM llm_cte",
        "predicate_wrap: ({p}) IS TRUE",
        "",
        "Rules already accepted, in acceptance order.",
        "Do not repeat a rule id, and do not repeat the same kind and template.",
    ])
    rows = _library_rows(library)
    if not rows:
        lines.append("(none)")
    for rule_id, kind, template in rows:
        lines.append(f"- {rule_id} | {kind} | {template}")
    lines.extend([
        "",
        f"Propose at most {ORACLE_RULES_PER_CALL} rules.",
        "Reply with one JSON object and no other text.",
        "Use this shape:",
        '{"rules": [{"name": "snake_case", "kind": "query_wrap", '
        '"template": "...", "argument": "why the multiset is unchanged"}], '
        '"prediction": [{"rule": "snake_case", "equivalent_on": '
        + json.dumps(names)
        + ', "why": "..."}]}',
        "name is 1 to 36 characters from lowercase letters, digits, and underscores.",
        "kind is query_wrap or predicate_wrap.",
        "argument is a non-empty string.",
    ])
    if call is not None:
        lines.append(f"This is proposal round {int(call)} of {ORACLE_CALLS_PER_RUN}.")
    return "\n".join(lines)


def accept_template(
    kind: str,
    template: str,
    *,
    engines: Sequence[str] | None = None,
    scan_max: int | None = None,
    seeds: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Accept ``template`` when enough corpus instances agree on at least three engines.

    ``seeds`` defaults to the seed corpus in file order. Tests may pass a short
    corpus. One dissenting engine rejects the template immediately.
    An instance counts only when at least ``ORACLE_ACCEPT_MIN_ENGINES`` engines
    agree and every agreeing engine returned at least two rows.
    """
    chosen = list(ORACLE_ACCEPT_ENGINES if engines is None else engines)
    limit = ORACLE_SCAN_MAX if scan_max is None else scan_max
    corpus = list(_default_seeds() if seeds is None else seeds)
    fac = _factories(chosen)
    instances: list[dict[str, Any]] = []
    scanned = 0
    for index, seed in enumerate(corpus):
        if scanned >= limit:
            break
        scanned += 1
        parts = _seed_parts(seed)
        if parts is None:
            continue
        setup, query = parts
        rewritten = apply_template(query, kind, template)
        if rewritten is None:
            continue
        votes = {
            engine: _vote(fac.get(engine), setup, query, rewritten) for engine in chosen
        }
        instance = _instance(index, query, chosen, votes)
        if instance.get("disagree"):
            instances.append(instance)
            return _verdict(False, "disagree", instances, chosen, scanned)
        if _counts(instance, votes):
            instances.append(instance)
            if len(instances) >= ORACLE_ACCEPT_INSTANCES:
                return _verdict(True, None, instances, chosen, scanned)
    return _verdict(False, "too_few_instances", instances, chosen, scanned)


class OracleInventor(Role):
    """Propose rewrite templates and append the ones the engines accept."""

    name = "oracle_inventor"

    def __init__(self, ctx: RoleContext, *, seeds: Sequence[Any] | None = None) -> None:
        self._ctx = ctx
        self.library_path = ctx.llm_dir / _LIBRARY_NAME
        self._book_path = ctx.llm_dir / _BOOK_NAME
        # None loads the real corpus. Tests may set this before after().
        self.seeds = seeds
        self._seen = 0
        self._calls = 0
        self._proposed = 0
        self._accepted: list[dict[str, Any]] = []
        self._rejected: dict[str, int] = {}
        self._step: list[list[Any]] = []

    def after(self, wb, record, outcome) -> None:
        """Count one experiment. Call the gateway on the configured periods."""
        self._seen += 1
        if "equivalent_query" not in self._ctx.oracles:
            return
        if (self._seen - 1) % ORACLE_EVERY != 0:
            return
        if self._calls >= ORACLE_CALLS_PER_RUN:
            return
        self._call()

    def rules(self) -> tuple[str, ...]:
        """Accepted rule ids, in the order they were committed."""
        return tuple(item["rule_id"] for item in self._accepted)

    def step(self) -> dict:
        """Proposals since the previous step, then clear that window."""
        proposed = self._step
        self._step = []
        return {"proposed": proposed}

    def report(self) -> dict:
        """Totals for the whole run."""
        return {
            "calls": self._calls,
            "proposed": self._proposed,
            "accepted": [item["rule_id"] for item in self._accepted],
            "rejected": dict(self._rejected),
        }

    def manifest(self) -> dict:
        """Engines that can accept a template, and the library file name."""
        return {"engines": list(ORACLE_ACCEPT_ENGINES), "library": _LIBRARY_NAME}

    def _call(self) -> None:
        library = {
            "schema": LIBRARY_SCHEMA,
            "rules": [
                {"rule_id": item["rule_id"], "kind": item["kind"], "template": item["template"]}
                for item in self._accepted
            ],
        }
        prompt = oracle_prompt(
            library=library,
            engines=list(ORACLE_ACCEPT_ENGINES),
            call=self._calls + 1,
        )
        reply = self._ctx.gateway.call(
            self.name,
            prompt,
            tier=ORACLE_TIER,
            seed=self._ctx.seed,
            temperature=ORACLE_TEMPERATURE,
            max_tokens=ORACLE_MAX_TOKENS,
        )
        self._calls += 1
        self._write({
            "type": "call",
            "status": reply.status,
            "reason": reply.reason,
            "key": reply.key,
        })
        if reply.status != "ok" or not isinstance(reply.data, dict):
            return
        rules = reply.data.get("rules")
        if not isinstance(rules, list):
            return
        predictions = reply.data.get("prediction")
        for index, item in enumerate(rules):
            self._consider(item, predictions, over_max=index >= ORACLE_RULES_PER_CALL)

    def _consider(self, item: Any, predictions: Any, *, over_max: bool) -> None:
        name = item.get("name") if isinstance(item, dict) else None
        kind = item.get("kind") if isinstance(item, dict) else None
        template = item.get("template") if isinstance(item, dict) else None
        argument = item.get("argument") if isinstance(item, dict) else None
        prediction = _prediction_for(predictions, name)
        rule_id = LIBRARY_RULE_PREFIX + name if isinstance(name, str) and _NAME.fullmatch(name) else None
        acceptance = None
        if over_max:
            reason: str | None = "over_max"
        elif rule_id is None:
            reason = "name"
        elif not isinstance(kind, str) or not isinstance(template, str) or template_problem(kind, template) is not None:
            reason = "template"
        elif self._duplicate(rule_id, kind, template):
            reason = "duplicate"
        elif not isinstance(argument, str) or argument == "":
            reason = "argument"
        else:
            acceptance = accept_template(kind, template, seeds=self.seeds)
            if not acceptance["accepted"]:
                reason = acceptance["reason"]
            elif self._commit(rule_id, kind, template, argument, acceptance):
                reason = None
            else:
                reason = "library_refused"
        status = "accepted" if reason is None else "rejected"
        self._note(rule_id, name, kind, template, status, reason, acceptance, prediction)

    def _duplicate(self, rule_id: str, kind: str, template: str) -> bool:
        for item in self._accepted:
            if item["rule_id"] == rule_id:
                return True
            if item["kind"] == kind and item["template"] == template:
                return True
        return False

    def _commit(self, rule_id: str, kind: str, template: str, argument: str, acceptance: dict) -> bool:
        """Append one rule and keep it only when load_library reads it back."""
        stored = {
            "rule_id": rule_id,
            "kind": kind,
            "template": template,
            "argument": argument,
            "proposer": _PROPOSER,
            "acceptance": acceptance,
        }
        path = self.library_path
        previous = path.read_bytes() if path.is_file() else None
        _atomic_write(path, _library_bytes([*self._accepted, stored]))
        loaded = load_library(path)
        wanted = [item["rule_id"] for item in self._accepted] + [rule_id]
        fresh = loaded.get(rule_id)
        if (
            all(one in loaded for one in wanted)
            and isinstance(fresh, dict)
            and fresh.get("kind") == kind
            and fresh.get("template") == template
        ):
            self._accepted.append(stored)
            return True
        if previous is None:
            if path.is_file():
                path.unlink()
        else:
            _atomic_write(path, previous)
        return False

    def _note(
        self,
        rule_id: str | None,
        name: Any,
        kind: Any,
        template: Any,
        status: str,
        reason: str | None,
        acceptance: dict | None,
        prediction: dict | None,
    ) -> None:
        self._proposed += 1
        if reason is not None:
            self._rejected[reason] = self._rejected.get(reason, 0) + 1
        shown = rule_id if rule_id is not None else (name if isinstance(name, str) else None)
        self._step.append([shown, status, reason])
        self._write({
            "type": "proposal",
            "rule_id": rule_id,
            "name": name if isinstance(name, str) else None,
            "kind": kind if isinstance(kind, str) else None,
            "template": template if isinstance(template, str) else None,
            "status": status,
            "reason": reason,
            "acceptance": acceptance,
            "prediction": prediction,
        })

    def _write(self, row: dict) -> None:
        path = self._book_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")
            handle.flush()


def _prediction_for(predictions: Any, name: Any) -> dict | None:
    """The reply's prediction for this rule name, or None when it has none."""
    if not isinstance(name, str) or not isinstance(predictions, list):
        return None
    for item in predictions:
        if isinstance(item, dict) and item.get("rule") == name:
            return dict(item)
    return None


def _engine_names(engines: Any) -> list[str]:
    if isinstance(engines, str):
        return [engines]
    return [str(engine) for engine in engines]


def _library_rows(library: dict) -> list[tuple[str, str, str]]:
    """(rule_id, kind, template) in library order."""
    if not isinstance(library, dict):
        return []
    rules = library.get("rules")
    rows: list[tuple[str, str, str]] = []
    if isinstance(rules, list):
        for item in rules:
            row = _row(item.get("rule_id") if isinstance(item, dict) else None, item)
            if row is not None:
                rows.append(row)
        return rows
    for rule_id, item in library.items():
        row = _row(rule_id, item)
        if row is not None:
            rows.append(row)
    return rows


def _row(rule_id: Any, item: Any) -> tuple[str, str, str] | None:
    if not isinstance(rule_id, str) or not isinstance(item, dict):
        return None
    kind = item.get("kind")
    template = item.get("template")
    if not isinstance(kind, str) or not isinstance(template, str):
        return None
    return rule_id, kind, template


def _default_seeds() -> list[Any]:
    global _CORPUS
    if _CORPUS is None:
        from seeds.store import SeedCorpus

        path = Path(__file__).resolve().parents[2] / "seeds" / "corpus.json"
        _CORPUS = list(SeedCorpus.load(path).seeds)
    return _CORPUS


def _seed_parts(seed: Any) -> tuple[list[str], str] | None:
    if isinstance(seed, dict):
        query = seed.get("query")
        setup = seed.get("setup_sqls")
    else:
        query = getattr(seed, "query", None)
        setup = getattr(seed, "setup_sqls", None)
    if not isinstance(query, str):
        return None
    if setup is None:
        setup = []
    if not isinstance(setup, (list, tuple)) or not all(isinstance(item, str) for item in setup):
        return None
    return list(setup), query


def _factories(engines: Sequence[str]) -> dict[str, Any]:
    from surprise.harness.oracles.cross_dbms import default_reference_factories
    from surprise.harness.oracles.registry import runner_factory_for

    refs = default_reference_factories("duckdb")
    found: dict[str, Any] = {}
    for engine in engines:
        if engine in ("duckdb", "datafusion"):
            found[engine] = runner_factory_for(engine)
        else:
            found[engine] = refs.get(engine)
    return found


def _vote(factory: Any, setup: list[str], query: str, rewritten: str) -> tuple[str, int]:
    """One engine: skipped, error, agree, or disagree, plus the original row count."""
    if factory is None:
        return "skipped", 0
    from oracles.db_runner import QueryResult, bags_equal

    runner = None
    left_ok = False
    left_rows = 0
    try:
        runner = factory()
        outcomes = runner.setup(list(setup))
        for _statement, error in outcomes:
            if error is not None:
                return "skipped", 0
        left = runner.run(query, timeout_s=QUERY_TIMEOUT_S)
        if not _succeeded(left, QueryResult):
            return "skipped", 0
        left_ok = True
        left_rows = len(left.rows)
        right = runner.run(rewritten, timeout_s=QUERY_TIMEOUT_S)
        if not _succeeded(right, QueryResult):
            return "error", left_rows
        if bags_equal(left, right):
            return "agree", left_rows
        return "disagree", left_rows
    except Exception:
        return ("error", left_rows) if left_ok else ("skipped", 0)
    finally:
        if runner is not None:
            try:
                runner.close()
            except Exception:
                pass


def _succeeded(result: Any, result_type: type) -> bool:
    return isinstance(result, result_type) and result.ok and not result.timed_out


def _instance(index: int, query: str, engines: Sequence[str], votes: dict[str, tuple[str, int]]) -> dict[str, Any]:
    record: dict[str, Any] = {
        "seed": index,
        "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
        "agree": [engine for engine in engines if votes[engine][0] == "agree"],
        "error": [engine for engine in engines if votes[engine][0] == "error"],
        "skipped": [engine for engine in engines if votes[engine][0] == "skipped"],
    }
    disagree = [engine for engine in engines if votes[engine][0] == "disagree"]
    if disagree:
        record["disagree"] = disagree
    return record


def _counts(instance: dict[str, Any], votes: dict[str, tuple[str, int]]) -> bool:
    agree = instance["agree"]
    if len(agree) < ORACLE_ACCEPT_MIN_ENGINES:
        return False
    return all(votes[engine][1] >= _MIN_RESULT_ROWS for engine in agree)


def _verdict(
    accepted: bool,
    reason: str | None,
    instances: list[dict[str, Any]],
    engines: list[str],
    scanned: int,
) -> dict[str, Any]:
    return {
        "accepted": accepted,
        "reason": reason,
        "instances": instances,
        "engines": list(engines),
        "scanned": scanned,
    }


def _library_bytes(rules: list[dict[str, Any]]) -> bytes:
    payload = {"schema": LIBRARY_SCHEMA, "rules": rules}
    return (json.dumps(payload, ensure_ascii=True, indent=1) + "\n").encode("utf-8")


def _atomic_write(path: Path, data: bytes) -> None:
    """Write ``path`` by replacing a temporary file in the same directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
