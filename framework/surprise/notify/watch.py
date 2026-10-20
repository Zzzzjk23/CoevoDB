"""Watch one grid's result directory, keeping all monitoring state in memory."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import socket
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

from surprise.experiments.grid import _cell_directory, _cell_log, _expected_cells

from .pushplus import PushPlus, TOKEN_ENV

KEY_INFO_URL = "https://openrouter.ai/api/v1/key"
_ORDER = ("start", "llm_errors", "llm_blocked", "cell_failed", "stall", "balance", "finished", "exited")


@dataclass(frozen=True)
class Event:
    kind: str
    cell: str | None
    cause: str | None
    text: str


def classify(reason: str | None) -> str:
    reason = reason or ""
    for codes, cause in (((402,), "credit"), ((401, 403), "auth"), ((429,), "rate")):
        if any(re.search(rf"\b{code}\b", reason) for code in codes):
            return cause
    if "DeadlineExceeded" in reason:
        return "timeout"
    if "is not set" in reason:
        return "nokey"
    return "other"


@dataclass
class _Cell:
    label: str
    directory: Path
    offset: int = 0
    errors: int = 0
    errors_reported: bool = False
    blocked: bool = False
    ended: bool = False
    stalled_at: float | None = None


def _safe_text(text: str) -> str:
    for name in (TOKEN_ENV, "DEEPSEEK_API_KEY"):
        secret = os.environ.get(name)
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text


class Watcher:
    def __init__(self, out, *, notifier=None, streak=5, stall_minutes=30.0, balance_usd=1.0,
                 balance_every_minutes=30.0, max_per_day=30, clock=time.time):
        self.out = Path(out).resolve()
        config = json.loads((self.out / "grid.json").read_text(encoding="utf-8"))
        self._cells = [
            _Cell(f"{arm['name']}/s{seed}-r{rep}", _cell_directory(self.out, arm["name"], seed, rep))
            for arm, seed, rep in _expected_cells(config)
        ]
        self._glm = any(arm.get("tier") == "glm-flash" for arm in config["arms"])
        self.notifier = PushPlus() if notifier is None else notifier
        self.clock = clock
        self.streak = streak
        self.stall_minutes = stall_minutes
        self.balance_usd = balance_usd
        self.balance_every_minutes = balance_every_minutes
        self.max_per_day = max_per_day
        self._started = False
        self._finished = False
        self._last_balance: float | None = None
        self._balance_reported: set[str] = set()
        self._day = None
        self._daily_sent = 0
        self._pid: int | None = None

    def _snapshot(self):
        snapshot = []
        for cell in self._cells:
            marker = cell.directory / "cell.json"
            if marker.is_file():
                try:
                    info = json.loads(marker.read_text(encoding="utf-8"))
                    if not isinstance(info, dict):
                        raise ValueError("cell metadata must be an object")
                except (OSError, ValueError):
                    # A writer may not have finished its cell.json yet. Retry next poll.
                    print("Cell metadata is not readable yet.", flush=True)
                    snapshot.append((cell, "running", {}))
                else:
                    snapshot.append((cell, "done" if info.get("status") == "done" else "failed", info))
            else:
                snapshot.append((cell, "running" if cell.directory.is_dir() else "pending", {}))
        return snapshot

    @staticmethod
    def _summary(snapshot) -> str:
        counts = {state: sum(status == state for _, status, _ in snapshot)
                  for state in ("done", "failed", "running", "pending")}
        failed = ", ".join(cell.label for cell, status, _ in snapshot if status == "failed") or "无"
        return (f"完成 {counts['done']}，失败 {counts['failed']}，在跑 {counts['running']}，"
                f"未开始 {counts['pending']}；失败格：{failed}")

    def _calls(self, cell: _Cell) -> list[Event]:
        events = []
        path = cell.directory / "llm" / "calls.jsonl"
        if not path.is_file():
            return events
        with path.open("rb") as handle:
            handle.seek(cell.offset)
            while True:
                line = handle.readline()
                if not line.endswith(b"\n"):
                    break
                cell.offset = handle.tell()
                try:
                    row = json.loads(line)
                except (ValueError, UnicodeDecodeError):
                    print("Ignoring an invalid completed calls.jsonl line.", flush=True)
                    continue
                if not isinstance(row, dict):
                    continue
                status = row.get("status")
                if status in ("ok", "rejected"):
                    cell.errors = 0
                    cell.errors_reported = False
                elif status == "error":
                    cell.errors += 1
                    if cell.errors >= self.streak and not cell.errors_reported:
                        reason = row.get("reason")
                        events.append(Event("llm_errors", cell.label, classify(reason),
                                            f"连续 {cell.errors} 次 LLM 调用失败：{reason}"))
                        cell.errors_reported = True
                elif status == "blocked" and not cell.blocked:
                    events.append(Event("llm_blocked", cell.label, None, "LLM 调用上限已用完"))
                    cell.blocked = True
        return events

    @staticmethod
    def _failure(cell: _Cell, info) -> Event:
        try:
            with _cell_log(cell.directory).open(encoding="utf-8", errors="replace") as handle:
                tail = " | ".join(line.rstrip("\r\n")[:300] for line in deque(handle, maxlen=3))
        except FileNotFoundError:
            tail = "无日志"
        return Event("cell_failed", cell.label, None,
                     f"格运行失败，returncode={info.get('returncode')}；日志最后三行：{tail}")

    def _stall(self, cell: _Cell, now: float) -> list[Event]:
        paths = list(cell.directory.iterdir())
        llm = cell.directory / "llm"
        if llm.is_dir():
            paths.extend(llm.iterdir())
        paths.append(_cell_log(cell.directory))
        mtimes = [path.stat().st_mtime for path in paths if path.is_file()]
        if not mtimes:
            return []
        latest = max(mtimes)
        if cell.stalled_at is not None and latest > cell.stalled_at:
            cell.stalled_at = None
        if cell.stalled_at is None and now - latest > self.stall_minutes * 60:
            cell.stalled_at = now
            return [Event("stall", cell.label, None, f"超过 {self.stall_minutes:g} 分钟没有文件活动")]
        return []

    def _balance(self, now: float) -> tuple[list[Event], str]:
        key = os.environ.get("DEEPSEEK_API_KEY")
        if not self._glm or not key:
            return [], ""
        if self._last_balance is not None and now - self._last_balance < self.balance_every_minutes * 60:
            return [], ""
        self._last_balance = now
        cause = None
        detail = "额度检查失败，只能靠调用失败发现欠费"
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(KEY_INFO_URL, headers={"Authorization": f"Bearer {key}"})
            if response.status_code in (401, 403):
                cause = "auth"
                detail = f"额度检查认证失败，HTTP {response.status_code}"
            else:
                response.raise_for_status()
                body = response.json()
                data = body.get("data") if isinstance(body, dict) else None
                if not isinstance(data, dict) or "limit_remaining" not in data:
                    raise ValueError("invalid key info")
                remaining = data["limit_remaining"]
                if remaining is None:
                    detail = "key 没设额度上限，只能靠调用失败发现欠费"
                elif isinstance(remaining, (int, float)) and not isinstance(remaining, bool) and math.isfinite(remaining):
                    detail = f"key 剩余额度 ${remaining:g}"
                    if remaining <= 0:
                        cause = "empty"
                    elif remaining < self.balance_usd:
                        cause = "low"
                else:
                    raise ValueError("invalid remaining limit")
        except (httpx.HTTPError, ValueError):
            print("Balance check failed; will retry at the next interval.", flush=True)
        if cause is not None and cause not in self._balance_reported:
            self._balance_reported.add(cause)
            return [Event("balance", None, cause, detail)], detail
        return [], detail

    def _publish(self, events: list[Event], now: float) -> list[Event]:
        if not events:
            return []
        events = [Event(e.kind, e.cell, e.cause, _safe_text(e.text)) for e in events]
        stamp = datetime.fromtimestamp(now, timezone.utc)
        for event in events:
            text = " ".join(event.text.splitlines())
            print(f"{stamp.isoformat()} {event.kind} {event.cell or '-'} {event.cause or '-'} {text}", flush=True)
        if stamp.date() != self._day:
            self._day = stamp.date()
            self._daily_sent = 0
        if self._daily_sent >= self.max_per_day:
            return events
        chosen = next((e for e in events if e.kind != "start"), events[0])
        headline = "额度不足" if chosen.cause == "credit" else chosen.text
        suffix = f"（共 {len(events)} 条）" if len(events) > 1 else ""
        title = "[CoevoDB] " + headline[:100 - len("[CoevoDB] ") - len(suffix)] + suffix
        content = "\n".join(f"{e.cell or '-'} {e.kind} {e.cause or '-'} {e.text}" for e in events)
        self._daily_sent += 1  # Count attempts, including failures, to bound requests.
        if self._daily_sent == self.max_per_day:
            note = "今天的推送已到上限，之后的事件只写日志"
            content = content[:4000 - len(note) - 1] + "\n" + note
        try:
            sent = self.notifier.send(title, content)
        except Exception:
            # Only this optional delivery step may fail without stopping monitoring.
            sent = False
        if not sent:
            print("Notification failed; monitoring continues.", flush=True)
        return events

    def poll(self) -> list[Event]:
        if self._finished:
            return []
        now = self.clock()
        exited = self._pid is not None and not _pid_alive(self._pid)
        snapshot = self._snapshot()
        events = []
        for cell, status, info in snapshot:
            ended = status in ("done", "failed")
            if not cell.ended and (status == "running" or (self._started and ended)):
                events.extend(self._calls(cell))
            if ended:
                if self._started and not cell.ended and status == "failed":
                    events.append(self._failure(cell, info))
                cell.ended = True
            elif status == "running":
                events.extend(self._stall(cell, now))
        balance_events, balance_detail = self._balance(now)
        events.extend(balance_events)
        if not self._started:
            text = f"开始看守，主机 {socket.gethostname()}，OUT={self.out}；{self._summary(snapshot)}"
            if balance_detail:
                text += f"；{balance_detail}"
            events.append(Event("start", None, None, text))
            self._started = True
        if all(status in ("done", "failed") for _, status, _ in snapshot):
            events.append(Event("finished", None, None, f"网格已结束；{self._summary(snapshot)}"))
            self._finished = True
        elif exited:
            events.append(Event("exited", None, None, f"网格进程已退出；{self._summary(snapshot)}"))
            self._finished = True
        events.sort(key=lambda event: _ORDER.index(event.kind))
        return self._publish(events, now)

    def run(self, *, pid: int | None = None, interval_s: float = 60.0) -> int:
        self._pid = pid
        while not self._finished:
            self.poll()
            if self._finished:
                break
            time.sleep(interval_s)
        return 0


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel.GetExitCodeProcess.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5  # Access denied does not prove exit.
        try:
            code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only grid watcher with pushplus alerts")
    parser.add_argument("out")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--interval", type=float, default=60.0)
    parser.add_argument("--streak", type=int, default=5)
    parser.add_argument("--stall-minutes", type=float, default=30.0)
    parser.add_argument("--balance-usd", type=float, default=1.0)
    parser.add_argument("--balance-every-minutes", type=float, default=30.0)
    parser.add_argument("--max-per-day", type=int, default=30)
    args = parser.parse_args(argv)
    if not (Path(args.out) / "grid.json").is_file():
        print("OUT must contain grid.json.")
        return 2
    watcher = Watcher(args.out, streak=args.streak, stall_minutes=args.stall_minutes,
                      balance_usd=args.balance_usd, balance_every_minutes=args.balance_every_minutes,
                      max_per_day=args.max_per_day)
    return watcher.run(pid=args.pid, interval_s=args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
