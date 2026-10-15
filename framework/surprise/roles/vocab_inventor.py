"""Vocabulary inventor: propose one regex feature when passes land inside S.

The prompt is a pure function of the hypothesis's specific features, the
training statements, and the registry. Record ids, hypothesis ids, family ids,
run ids, clocks, and absolute paths never enter it. A feature is not a label.
Acceptance is a deterministic check, and this run's theory and registry stay
as they are. An accepted feature is written for a later ``--vocabulary`` run.
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from surprise.features.ast import extract_ast
from surprise.features.registry import Registry, default_registry
from surprise.features.vocabulary import FeatureDef, is_feature_id
from surprise.harness.oracles.forms import full_query

from .base import Role, RoleContext
from .constants import (
    VOCAB_ATTEMPTS_PER_FAMILY,
    VOCAB_HOLDOUT_DIVISOR,
    VOCAB_MAX_CORPUS_SHARE,
    VOCAB_MAX_PATTERN_CHARS,
    VOCAB_MAX_TOKENS,
    VOCAB_MIN_POSITIVES,
    VOCAB_SCAN_TIMEOUT_S,
    VOCAB_TEMPERATURE,
    VOCAB_TIER,
    VOCAB_TRIGGER_CONTRADICTIONS,
)

_SOURCE = "llm:vocab_inventor"
_VOCAB_NAME = "vocabulary.json"
_BOOK_NAME = "vocabulary.jsonl"
_TOKEN = re.compile(r"[a-z0-9_]+")
_GATEWAY_STATUS = ("blocked", "miss", "error")
_CORPUS: list[str] | None = None

# Reads JSON from stdin and writes JSON to stdout. The pattern never goes
# through the shell. A slow match is killed by the parent.
_SCAN_PROGRAM = """
import json
import re
import sys

request = json.load(sys.stdin.buffer)
pattern = request["pattern"]
corpus = request["corpus"]
extra = request["extra"]
hits = 0
for statement in corpus:
    if re.search(pattern, statement, re.IGNORECASE):
        hits += 1
extra_hits = []
for statement in extra:
    extra_hits.append(re.search(pattern, statement, re.IGNORECASE) is not None)
sys.stdout.buffer.write(
    json.dumps({"corpus_hits": hits, "corpus_n": len(corpus), "extra_hits": extra_hits}).encode("utf-8")
)
"""


def build(ctx: RoleContext) -> VocabInventor:
    """The plugin entry. The runtime calls this only when the role is on."""
    return VocabInventor(ctx)


def split_holdout(items: list) -> tuple[list, list]:
    """``(train, held)`` with the last ``ceil(n / VOCAB_HOLDOUT_DIVISOR)`` held out."""
    rows = list(items)
    count = len(rows)
    if count == 0:
        return [], []
    held_count = math.ceil(count / VOCAB_HOLDOUT_DIVISOR)
    if held_count >= count:
        return [], rows
    return rows[:-held_count], rows[-held_count:]


def vocab_prompt(*, hypothesis, train_positives, train_contradictions, registry) -> str:
    """One English prompt. The same inputs always produce the same text."""
    lines = [
        "Invent one new executable feature for a SQL hypothesis.",
        "The feature is one more word in the hypothesis. It is not a label.",
        "A separate deterministic check decides whether to keep it.",
        "",
        "Every positive statement below failed inside the hypothesis.",
        "Every contradicting pass below also landed inside it.",
        "The specific features S cannot separate the positives from those passes.",
        "S, one feature id and one line of what it means:",
    ]
    specific = getattr(hypothesis, "specific", ())
    if not specific:
        lines.append("(none)")
    for feature_id in specific:
        lines.append(f"- {feature_id}")
        lines.append(f"  {_description(registry, feature_id)}")
    lines.extend([
        "",
        "Training positives. The feature must match every one.",
        "Matching means re.search(pattern, statement, re.IGNORECASE).",
        "Each statement is the full text.",
    ])
    _numbered(lines, "P", train_positives)
    lines.extend([
        "",
        "Training contradicting passes. The feature must miss at least one.",
        "Each statement is the full text.",
    ])
    _numbered(lines, "C", train_contradictions)
    lines.extend([
        "",
        "Propose one new feature at the AST layer.",
        "Define it with one Python regular expression.",
        "The extractor applies re.search(pattern, statement, re.IGNORECASE).",
        f"The pattern is at most {VOCAB_MAX_PATTERN_CHARS} characters.",
        "It must not match the empty string:",
        're.search(pattern, "", re.IGNORECASE) is None.',
        "Do not nest quantifiers, and do not write any other form that",
        "backtracks catastrophically on ordinary SQL.",
        "The parent must be one of the AST classes listed below.",
        "The id is that parent id, a colon, and one lowercase token.",
        "A token uses only lowercase letters, digits, and underscores.",
        "Example id: ast:set_op:two_tables with parent ast:set_op.",
        "",
        "AST classes you may use as the parent, sorted by id.",
        "Each line is the id, and the next line says what the class means.",
    ])
    classes = _ast_classes(registry)
    if not classes:
        lines.append("(none)")
    for feature_id, description in classes:
        lines.append(f"- {feature_id}")
        lines.append(f"  {description}")
    lines.extend([
        "",
        "Reply with one JSON object and no other text.",
        "Use this shape:",
        '{"feature": {"id": "<parent>:<token>", "parent": "<parent>", '
        '"description": "what the feature means", "pattern": "<python regex>"}, '
        '"prediction": {"matches": ["P1"], "excludes": ["C1"], "why": "why these statements differ"}}',
        "matches lists every training positive the pattern hits, as P1, P2, and so on.",
        "excludes lists every training contradicting pass the pattern misses, as C1, C2, and so on.",
        "description and why are non-empty strings.",
    ])
    return "\n".join(lines)


class VocabInventor(Role):
    """Propose a regex feature and keep it only when the held-out statements agree."""

    name = "vocab_inventor"

    def __init__(self, ctx: RoleContext) -> None:
        self._ctx = ctx
        self.vocabulary_path = ctx.llm_dir / _VOCAB_NAME
        self._book_path = ctx.llm_dir / _BOOK_NAME
        self._memory: list[dict[str, Any]] = []
        self._attempts: dict[str, int] = {}
        self._accepted: list[str] = []
        self._proposals = 0
        self._rejected: dict[str, int] = {}
        self._step: list[list[Any]] = []

    def observe(self, event) -> None:
        """Remember the statement and the engine, in arrival order."""
        record = event.record
        record_id = record.record_id
        if any(item["record_id"] == record_id for item in self._memory):
            return
        self._memory.append({
            "record_id": record_id,
            "sql": full_query(record.case),
            "engine": record.case.engine,
        })

    def after(self, wb, record, outcome) -> None:
        """On an unexpected pass, maybe ask for one feature for each ready family."""
        if outcome.observation.triage != "unexpected_pass":
            return
        record_id = record.record_id
        for hypothesis in wb.theory.hypotheses:
            if record_id not in hypothesis.contradictions:
                continue
            family = wb.family_of(hypothesis.hypothesis_id)
            if self._attempts.get(family, 0) >= VOCAB_ATTEMPTS_PER_FAMILY:
                continue
            positives = self._remembered(hypothesis.positives)
            contradictions = self._remembered(hypothesis.contradictions)
            if len(contradictions) < VOCAB_TRIGGER_CONTRADICTIONS or len(positives) < VOCAB_MIN_POSITIVES:
                continue
            self._attempts[family] = self._attempts.get(family, 0) + 1
            self._propose(hypothesis, family, positives, contradictions)

    def accepted(self) -> tuple[str, ...]:
        """Feature ids kept in this run, in the order they were kept."""
        return tuple(self._accepted)

    def step(self) -> dict:
        """Proposals since the previous step, then clear that window."""
        proposed = self._step
        self._step = []
        return {"proposed": proposed}

    def report(self) -> dict:
        """Totals for the whole run."""
        return {
            "proposals": self._proposals,
            "accepted": list(self._accepted),
            "rejected": dict(self._rejected),
        }

    def manifest(self) -> dict:
        """The vocabulary file a later run can load."""
        return {"vocabulary": _VOCAB_NAME}

    def _remembered(self, record_ids) -> list[dict[str, Any]]:
        """Statements we saw, in arrival order, limited to these record ids."""
        wanted = set(record_ids)
        return [item for item in self._memory if item["record_id"] in wanted]

    def _propose(self, hypothesis, family: str, positives: list[dict[str, Any]], contradictions: list[dict[str, Any]]) -> None:
        train_pos, held_pos = split_holdout(positives)
        train_con, held_con = split_holdout(contradictions)
        prompt = vocab_prompt(
            hypothesis=hypothesis,
            train_positives=[item["sql"] for item in train_pos],
            train_contradictions=[item["sql"] for item in train_con],
            registry=self._ctx.registry,
        )
        reply = self._ctx.gateway.call(
            self.name,
            prompt,
            tier=VOCAB_TIER,
            seed=self._ctx.seed,
            temperature=VOCAB_TEMPERATURE,
            max_tokens=VOCAB_MAX_TOKENS,
        )
        if reply.status != "ok" or not isinstance(reply.data, dict):
            status = reply.status if reply.status in _GATEWAY_STATUS else "rejected"
            self._note(
                family=family,
                hypothesis_id=hypothesis.hypothesis_id,
                status=status,
                reason="reply",
                detail=reply.reason,
                feature_id=None,
                pattern=None,
                prediction_kept=None,
                key=reply.key,
            )
            return
        self._judge(hypothesis, family, reply, train_pos, held_pos, train_con, held_con)

    def _judge(self, hypothesis, family, reply, train_pos, held_pos, train_con, held_con) -> None:
        feature = reply.data.get("feature")
        detail, feature_id, pattern = self._definition_problem(feature)
        if detail is not None:
            self._refuse(hypothesis, family, reply, "definition", detail, feature_id, pattern, None)
            return
        detail = _pattern_problem(pattern)
        if detail is not None:
            self._refuse(hypothesis, family, reply, "pattern", detail, feature_id, pattern, None)
            return
        description = feature["description"]
        parent = feature["parent"]
        draft = self._draft()
        try:
            draft.register(_leaf(feature_id, parent, description, pattern))
        except ValueError:
            self._refuse(hypothesis, family, reply, "definition", "register", feature_id, pattern, None)
            return
        scanned = _scan(pattern, [item["sql"] for item in self._memory])
        if scanned["detail"] is not None:
            self._refuse(hypothesis, family, reply, "scan", scanned["detail"], feature_id, pattern, None)
            return
        share = scanned["share"]
        if share > VOCAB_MAX_CORPUS_SHARE:
            self._refuse(hypothesis, family, reply, "scan", "corpus_share", feature_id, pattern, None)
            return
        trial = Registry(dict(draft._defs))
        trial.accept(feature_id, {"stage": "check"})
        pos_hits = _hits(trial, train_pos, feature_id)
        con_hits = _hits(trial, train_con, feature_id)
        held_pos_hits = _hits(trial, held_pos, feature_id)
        held_con_hits = _hits(trial, held_con, feature_id)
        kept = _prediction_kept(reply.data.get("prediction"), pos_hits, con_hits)
        if not all(pos_hits):
            self._refuse(hypothesis, family, reply, "train", "missed_positive", feature_id, pattern, kept)
            return
        excluded_train = sum(1 for hit in con_hits if not hit)
        if excluded_train < 1:
            self._refuse(hypothesis, family, reply, "train", "no_exclusion", feature_id, pattern, kept)
            return
        matched_held = sum(1 for hit in held_pos_hits if hit)
        if matched_held != len(held_pos):
            self._refuse(hypothesis, family, reply, "holdout", "missed_positive", feature_id, pattern, kept)
            return
        acceptance = {
            "family": family,
            "hypothesis_id": hypothesis.hypothesis_id,
            "train": {
                "positives": len(train_pos),
                "contradictions": len(train_con),
                "excluded": excluded_train,
            },
            "holdout": {
                "positives": len(held_pos),
                "matched": matched_held,
                "contradictions": len(held_con),
                "excluded": sum(1 for hit in held_con_hits if not hit),
            },
            "corpus_share": share,
            "prediction_kept": kept,
        }
        draft.accept(feature_id, acceptance)
        draft.save(self.vocabulary_path)
        self._note(
            family=family,
            hypothesis_id=hypothesis.hypothesis_id,
            status="accepted",
            reason=None,
            detail=None,
            feature_id=feature_id,
            pattern=pattern,
            prediction_kept=kept,
            key=reply.key,
        )

    def _definition_problem(self, feature: Any) -> tuple[str | None, str | None, str | None]:
        """The first definition failure, plus the id and pattern when they are strings."""
        if not isinstance(feature, dict):
            return "feature", None, None
        feature_id = feature.get("id")
        parent = feature.get("parent")
        description = feature.get("description")
        pattern = feature.get("pattern")
        shown_id = feature_id if isinstance(feature_id, str) and feature_id else None
        shown_pattern = pattern if isinstance(pattern, str) else None
        if (
            not isinstance(feature_id, str) or feature_id == ""
            or not isinstance(parent, str) or parent == ""
            or not isinstance(description, str) or description == ""
            or not isinstance(pattern, str)
        ):
            return "fields", shown_id, shown_pattern
        registry = self._ctx.registry
        if not _is_ast_class(registry, parent):
            return "parent", shown_id, shown_pattern
        if not is_feature_id(feature_id) or not _token_ok(feature_id, parent):
            return "id", shown_id, shown_pattern
        if self._taken(feature_id):
            return "known", shown_id, shown_pattern
        return None, feature_id, pattern

    def _taken(self, feature_id: str) -> bool:
        if feature_id in self._accepted or self._ctx.registry.known(feature_id):
            return True
        if self.vocabulary_path.is_file() and Registry.load(self.vocabulary_path).known(feature_id):
            return True
        return False

    def _draft(self) -> Registry:
        """The vocabulary file so far, or the base vocabulary. Never ``ctx.registry``."""
        if self.vocabulary_path.is_file():
            return Registry.load(self.vocabulary_path)
        return default_registry()

    def _refuse(self, hypothesis, family, reply, reason, detail, feature_id, pattern, prediction_kept) -> None:
        self._note(
            family=family,
            hypothesis_id=hypothesis.hypothesis_id,
            status="rejected",
            reason=reason,
            detail=detail,
            feature_id=feature_id,
            pattern=pattern,
            prediction_kept=prediction_kept,
            key=reply.key,
        )

    def _note(
        self,
        *,
        family: str,
        hypothesis_id: str,
        status: str,
        reason: str | None,
        detail: str | None,
        feature_id: str | None,
        pattern: str | None,
        prediction_kept: bool | None,
        key: str,
    ) -> None:
        self._proposals += 1
        if status == "accepted" and isinstance(feature_id, str):
            self._accepted.append(feature_id)
        elif reason is not None:
            self._rejected[reason] = self._rejected.get(reason, 0) + 1
        self._step.append([family, status, reason])
        self._write({
            "type": "proposal",
            "family": family,
            "hypothesis_id": hypothesis_id,
            "status": status,
            "reason": reason,
            "detail": detail,
            "feature_id": feature_id,
            "pattern": pattern,
            "prediction_kept": prediction_kept,
            "key": key,
        })

    def _write(self, row: dict) -> None:
        path = self._book_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")
            handle.flush()


def _numbered(lines: list[str], prefix: str, statements) -> None:
    rows = list(statements)
    if not rows:
        lines.append("(none)")
        return
    for index, statement in enumerate(rows, start=1):
        lines.append(f"{prefix}{index}: {statement}")


def _description(registry, feature_id: str) -> str:
    if not isinstance(feature_id, str) or not registry.known(feature_id):
        return ""
    text = registry.get(feature_id).description
    if not isinstance(text, str):
        return ""
    return " ".join(text.split())


def _ast_classes(registry) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for feature_id in registry.ids():
        definition = registry.get(feature_id)
        if definition.kind == "class" and definition.layer == "ast":
            rows.append((feature_id, _description(registry, feature_id)))
    return rows


def _is_ast_class(registry, feature_id: str) -> bool:
    if not registry.known(feature_id):
        return False
    definition = registry.get(feature_id)
    return definition.kind == "class" and definition.layer == "ast"


def _token_ok(feature_id: str, parent: str) -> bool:
    prefix = parent + ":"
    if not feature_id.startswith(prefix):
        return False
    return _TOKEN.fullmatch(feature_id[len(prefix):]) is not None


def _pattern_problem(pattern: str) -> str | None:
    try:
        re.compile(pattern)
    except re.error:
        return "compile"
    if len(pattern) > VOCAB_MAX_PATTERN_CHARS:
        return "length"
    if re.search(pattern, "", re.IGNORECASE) is not None:
        return "empty"
    return None


def _leaf(feature_id: str, parent: str, description: str, pattern: str) -> FeatureDef:
    return FeatureDef(
        feature_id=feature_id,
        kind="leaf",
        parent=parent,
        layer="ast",
        description=description,
        source=_SOURCE,
        definition={"kind": "regex", "pattern": pattern},
        accepted=False,
        acceptance=None,
    )


def _hits(registry: Registry, items: list[dict[str, Any]], feature_id: str) -> list[bool]:
    found: list[bool] = []
    for item in items:
        leaves, _status = extract_ast(item["sql"], item["engine"], registry)
        found.append(feature_id in leaves)
    return found


def _prediction_kept(prediction: Any, pos_hits: list[bool], con_hits: list[bool]) -> bool:
    """Whether the reply's training matches and excludes agree with the pattern."""
    if not isinstance(prediction, dict):
        return False
    matches = prediction.get("matches")
    excludes = prediction.get("excludes")
    if not _string_list(matches) or not _string_list(excludes):
        return False
    actual_matches = {f"P{index}" for index, hit in enumerate(pos_hits, start=1) if hit}
    actual_excludes = {f"C{index}" for index, hit in enumerate(con_hits, start=1) if not hit}
    return set(matches) == actual_matches and set(excludes) == actual_excludes


def _string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _corpus_statements() -> list[str]:
    global _CORPUS
    if _CORPUS is None:
        from seeds.store import SeedCorpus

        path = Path(__file__).resolve().parents[2] / "seeds" / "corpus.json"
        if not path.is_file():
            raise FileNotFoundError("seed corpus is missing")
        loaded = SeedCorpus.load(path)
        _CORPUS = [seed.query for seed in loaded.seeds if isinstance(seed.query, str) and seed.query]
        if not _CORPUS:
            raise RuntimeError("seed corpus is empty")
    return _CORPUS


def _child_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("DEEPSEEK_API_KEY", None)
    return env


def _kill(proc: subprocess.Popen) -> None:
    proc.kill()
    try:
        proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def _scan(pattern: str, extra: list[str]) -> dict[str, Any]:
    """Corpus share of ``pattern``, or a ``detail`` when the scan does not finish."""
    corpus = _corpus_statements()
    proc = subprocess.Popen(
        [sys.executable, "-c", _SCAN_PROGRAM],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_child_env(),
    )
    payload = json.dumps(
        {"pattern": pattern, "corpus": corpus, "extra": extra},
        ensure_ascii=False,
    ).encode("utf-8")
    try:
        stdout, _stderr = proc.communicate(payload, timeout=VOCAB_SCAN_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        _kill(proc)
        return {"detail": "timeout", "share": None}
    if proc.returncode != 0:
        return {"detail": "error", "share": None}
    try:
        data = json.loads(stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError, TypeError):
        return {"detail": "error", "share": None}
    hits = data.get("corpus_hits") if isinstance(data, dict) else None
    total = data.get("corpus_n") if isinstance(data, dict) else None
    if (
        isinstance(hits, bool) or not isinstance(hits, int)
        or isinstance(total, bool) or not isinstance(total, int)
        or total < 0 or hits < 0
    ):
        return {"detail": "error", "share": None}
    share = 0.0 if total == 0 else hits / total
    return {"detail": None, "share": share}
