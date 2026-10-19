"""LLM gateway: cache, cap, per-role ledger. No model client of its own."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cache import ResponseCache, cache_key
from .constants import CAP_ENV, DEFAULT_MAX_CALLS, TIERS, as_dict
from .schema import parse_reply

# Not a name in roles.constants: as_dict() would copy every uppercase constant
# into the manifest of every run.
UNLIMITED = "unlimited"

_ROLE_TOTAL_KEYS = (
    "calls",
    "network",
    "cache",
    "ok",
    "rejected",
    "blocked",
    "miss",
    "error",
    "input_tokens",
    "output_tokens",
)


@dataclass(frozen=True)
class Completion:
    """What a transport returns."""

    text: str
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class Reply:
    """One ``Gateway.call`` result."""

    role: str
    tier: str
    model: str
    seed: int
    key: str
    status: str
    source: str | None
    data: dict | None
    text: str | None
    reason: str | None
    input_tokens: int
    output_tokens: int


class TransportError(RuntimeError):
    """A transport failed; the message holds only a class name and optional HTTP status."""


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _resolve_max_calls(max_calls: object) -> int | None:
    """Effective network cap, or None when the gateway itself has no cap.

    ``None`` asks for ``DEFAULT_MAX_CALLS``. ``UNLIMITED`` asks for no cap.
    A negative, a bool, a float, or any other string is rejected. ``CAP_ENV``,
    when it holds an integer, lowers a numeric cap and is the cap of an
    unlimited gateway.
    """
    if max_calls is None:
        configured: int | None = DEFAULT_MAX_CALLS
    elif isinstance(max_calls, str) and max_calls == UNLIMITED:
        configured = None
    elif isinstance(max_calls, bool) or not isinstance(max_calls, int) or max_calls < 0:
        raise ValueError(
            f"max_calls must be an integer >= 0, null, or {UNLIMITED!r}, got {max_calls!r}"
        )
    else:
        configured = max_calls
    raw = os.environ.get(CAP_ENV)
    if raw is None:
        return configured
    try:
        ceiling = int(raw)
    except (TypeError, ValueError):
        return configured
    if configured is None:
        return ceiling
    return min(configured, ceiling)


def _resolve_tier(tier: object) -> str | None:
    """A tier forced on every call, or None to keep the tier the caller passed."""
    if tier is None:
        return None
    if isinstance(tier, str) and tier in TIERS:
        return tier
    raise ValueError(f"tier must be one of {', '.join(TIERS)} or null, got {tier!r}")


def _blank_role() -> dict[str, int]:
    return {name: 0 for name in _ROLE_TOTAL_KEYS}


class Gateway:
    """Cached, capped, accounted calls to a transport (or to the cache alone)."""

    def __init__(
        self,
        *,
        cache_dir: Path | str,
        ledger_path: Path | str | None = None,
        max_calls: int | str | None = None,
        transport: Any = None,
        tier: str | None = None,
    ) -> None:
        resolved_cap = _resolve_max_calls(max_calls)
        resolved_tier = _resolve_tier(tier)
        self._cache = ResponseCache(cache_dir)
        self._ledger_path = Path(ledger_path) if ledger_path is not None else None
        self._max_calls = resolved_cap
        self._tier = resolved_tier
        self._transport = transport
        self._network_calls = 0
        self._seq = 0
        self._by_role: dict[str, dict[str, int]] = {}
        if self._ledger_path is not None:
            self._ledger_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def network_calls(self) -> int:
        return self._network_calls

    @property
    def max_calls(self) -> int | None:
        """The effective cap, or None when nothing caps this gateway."""
        return self._max_calls

    @property
    def tier(self) -> str | None:
        """The tier forced on every call, or None when each call keeps its own."""
        return self._tier

    def _published_max_calls(self) -> int | str:
        """What ``totals`` and ``manifest`` record: an int, or ``UNLIMITED``."""
        if self._max_calls is None:
            return UNLIMITED
        return self._max_calls

    def call(
        self,
        role: str,
        prompt: str,
        *,
        tier: str,
        seed: int,
        temperature: float = 0.0,
        max_tokens: int = 4000,
    ) -> Reply:
        if self._tier is not None:
            tier = self._tier
        if tier not in TIERS:
            raise ValueError(f"unknown tier: {tier!r}")
        model = TIERS[tier]
        key = cache_key(prompt, model, seed)
        started = time.perf_counter()
        reply = self._invoke(
            role=role,
            prompt=prompt,
            tier=tier,
            model=model,
            seed=seed,
            key=key,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self._account(reply, prompt, time.perf_counter() - started)
        return reply

    def totals(self) -> dict[str, Any]:
        return {
            "by_role": {role: dict(stats) for role, stats in self._by_role.items()},
            "network": self._network_calls,
            "max_calls": self._published_max_calls(),
        }

    def manifest(self) -> dict[str, Any]:
        result = {
            "tiers": dict(TIERS),
            "max_calls": self._published_max_calls(),
            "constants": as_dict(),
        }
        if self._tier is not None:
            result["tier"] = self._tier
        return result

    def _invoke(
        self,
        *,
        role: str,
        prompt: str,
        tier: str,
        model: str,
        seed: int,
        key: str,
        temperature: float,
        max_tokens: int,
    ) -> Reply:
        entry = self._cache.get(key)
        if entry is not None:
            text = entry.get("text")
            text = text if isinstance(text, str) else ""
            data, reason = parse_reply(text)
            return Reply(
                role=role,
                tier=tier,
                model=model,
                seed=seed,
                key=key,
                status="ok" if reason is None else "rejected",
                source="cache",
                data=data,
                text=text,
                reason=reason,
                input_tokens=int(entry.get("input_tokens") or 0),
                output_tokens=int(entry.get("output_tokens") or 0),
            )
        if self._transport is None:
            return Reply(
                role=role,
                tier=tier,
                model=model,
                seed=seed,
                key=key,
                status="miss",
                source=None,
                data=None,
                text=None,
                reason="miss",
                input_tokens=0,
                output_tokens=0,
            )
        if self._max_calls is not None and self._network_calls >= self._max_calls:
            return Reply(
                role=role,
                tier=tier,
                model=model,
                seed=seed,
                key=key,
                status="blocked",
                source=None,
                data=None,
                text=None,
                reason="cap",
                input_tokens=0,
                output_tokens=0,
            )
        self._network_calls += 1
        try:
            completion = self._transport.complete(
                model=model,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                role=role,
            )
            text = completion.text
            input_tokens = int(completion.input_tokens)
            output_tokens = int(completion.output_tokens)
        except Exception as exc:
            return Reply(
                role=role,
                tier=tier,
                model=model,
                seed=seed,
                key=key,
                status="error",
                source="network",
                data=None,
                text=None,
                reason=type(exc).__name__,
                input_tokens=0,
                output_tokens=0,
            )
        self._cache.put(
            {
                "key": key,
                "prompt_sha256": _sha256_text(prompt),
                "model": model,
                "seed": seed,
                "role": role,
                "tier": tier,
                "prompt": prompt,
                "text": text,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "created_at": _now_iso(),
            }
        )
        data, reason = parse_reply(text)
        return Reply(
            role=role,
            tier=tier,
            model=model,
            seed=seed,
            key=key,
            status="ok" if reason is None else "rejected",
            source="network",
            data=data,
            text=text,
            reason=reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def _account(self, reply: Reply, prompt: str, latency_s: float) -> None:
        stats = self._by_role.setdefault(reply.role, _blank_role())
        stats["calls"] += 1
        stats[reply.status] += 1
        if reply.source == "network":
            stats["network"] += 1
            stats["input_tokens"] += reply.input_tokens
            stats["output_tokens"] += reply.output_tokens
        elif reply.source == "cache":
            stats["cache"] += 1
        self._seq += 1
        if self._ledger_path is None:
            return
        row = {
            "seq": self._seq,
            "role": reply.role,
            "tier": reply.tier,
            "model": reply.model,
            "seed": reply.seed,
            "key": reply.key,
            "prompt_sha256": _sha256_text(prompt),
            "status": reply.status,
            "source": reply.source,
            "reason": reply.reason,
            "input_tokens": reply.input_tokens,
            "output_tokens": reply.output_tokens,
            "latency_s": latency_s,
        }
        with self._ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
