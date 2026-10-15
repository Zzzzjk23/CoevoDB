"""DeepSeek transport: reuses BaseAgent and the old global ledger."""

from __future__ import annotations

import json
import threading
import time
from typing import Any

from agents.base_agent import BaseAgent
from llm.ledger import ledger

from .constants import REQUEST_DEADLINE_S, TIERS
from .gateway import Completion, TransportError


class DeepSeekTransport(BaseAgent):
    """POST /chat/completions through BaseAgent's HTTP client."""

    def __init__(self, *, base_url: str | None = None, deadline_s: float | None = None) -> None:
        super().__init__(
            {
                "api_key": "${DEEPSEEK_API_KEY}",
                "base_url": base_url or "https://api.deepseek.com/v1",
                "model": TIERS["fast"],
            }
        )
        self.deadline_s = REQUEST_DEADLINE_S if deadline_s is None else deadline_s

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def learn_from_feedback(self, feedback: dict[str, Any]) -> None:
        raise NotImplementedError

    def complete(
        self,
        *,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
        role: str,
    ) -> Completion:
        if not self.api_key:
            raise TransportError("DEEPSEEK_API_KEY is not set")
        agent = "surprise.roles." + role
        try:
            client = self.setup_api_client()
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            body = _read_with_deadline(client, payload, self.deadline_s, self.close_client)
            content = body["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("content")
            usage = body.get("usage") or {}
            input_tokens = int(usage.get("prompt_tokens") or 0)
            output_tokens = int(usage.get("completion_tokens") or 0)
        except TransportError:
            ledger.record(
                agent=agent,
                event=role,
                model=model,
                prompt=prompt,
                status="error",
            )
            raise
        except Exception as exc:
            ledger.record(
                agent=agent,
                event=role,
                model=model,
                prompt=prompt,
                status="error",
            )
            raise _to_transport_error(exc) from None
        ledger.record(
            agent=agent,
            event=role,
            model=model,
            prompt=prompt,
            response=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            status="ok",
        )
        return Completion(text=content, input_tokens=input_tokens, output_tokens=output_tokens)


def _read_with_deadline(client: Any, payload: dict[str, Any], deadline_s: float, closer: Any) -> dict[str, Any]:
    """POST and read the JSON body, giving up when ``deadline_s`` has elapsed."""
    started = time.monotonic()
    box: dict[str, Any] = {}

    def worker() -> None:
        try:
            left = deadline_s - (time.monotonic() - started)
            if left <= 0:
                raise TransportError("DeadlineExceeded")
            chunks: list[bytes] = []
            with client.stream("POST", "/chat/completions", json=payload, timeout=left) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes():
                    if time.monotonic() - started >= deadline_s:
                        raise TransportError("DeadlineExceeded")
                    chunks.append(chunk)
            if time.monotonic() - started >= deadline_s:
                raise TransportError("DeadlineExceeded")
            box["body"] = json.loads(b"".join(chunks))
        except BaseException as exc:
            box["exc"] = exc

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout=max(0.0, deadline_s))
    if thread.is_alive():
        closer()
        raise TransportError("DeadlineExceeded")
    if "exc" in box:
        raise box["exc"]
    return box["body"]


def _to_transport_error(exc: BaseException) -> TransportError:
    name = type(exc).__name__
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None) if response is not None else None
    if status is None:
        return TransportError(name)
    return TransportError(f"{name} {status}")
