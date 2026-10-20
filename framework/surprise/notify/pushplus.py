"""Send a plain-text pushplus one-to-one message without exposing credentials."""

from __future__ import annotations

import argparse
import os

import httpx

TOKEN_ENV = "PUSHPLUS_TOKEN"
URL = "https://www.pushplus.plus/send"


class PushPlus:
    def __init__(self, token: str | None = None, *, timeout_s: float = 10.0):
        self._token = os.environ.get(TOKEN_ENV, "") if token is None else token
        self._stopped = False
        self._sent = 0
        self._timeout_s = timeout_s

    @property
    def enabled(self) -> bool:
        return bool(self._token) and not self._stopped

    @property
    def sent(self) -> int:
        return self._sent

    def send(self, title: str, content: str) -> bool:
        if not self.enabled:
            return False
        try:
            with httpx.Client(timeout=self._timeout_s) as client:
                response = client.post(URL, json={
                    "token": self._token, "title": title[:100],
                    "content": content[:4000], "template": "txt",
                })
            if response.status_code != 200:
                return False
            body = response.json()
        except (httpx.HTTPError, ValueError):
            # Exception messages and response bodies can contain the credential.
            return False
        if not isinstance(body, dict):
            return False
        code = body.get("code")
        if code in (900, 905, 888):
            self._stopped = True
        if code != 200:
            return False
        self._sent += 1
        return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send a pushplus one-to-one text message")
    parser.add_argument("title")
    parser.add_argument("content")
    args = parser.parse_args(argv)
    sender = PushPlus()
    if not sender.enabled:
        print("PUSHPLUS_TOKEN is not set; no notification sent.")
        return 2
    if sender.send(args.title, args.content):
        print("Notification sent.")
        return 0
    print("Notification failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
