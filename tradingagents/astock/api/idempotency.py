"""Small, bounded idempotency registry for retried API write requests.

The registry intentionally only retains completed HTTP responses for a short
period.  It prevents a client retry from running a costly write twice inside
one API process; multi-worker deployments should replace it with Redis.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass


@dataclass
class _Entry:
    fingerprint: str
    expires_at: float
    response: tuple[int, bytes, str] | None = None


class IdempotencyRegistry:
    def __init__(self, ttl_seconds: float = 300, max_entries: int = 1000) -> None:
        self.ttl_seconds = max(1.0, float(ttl_seconds))
        self.max_entries = max(1, int(max_entries))
        self._entries: OrderedDict[str, _Entry] = OrderedDict()
        self._lock = threading.Lock()

    def claim(self, key: str, fingerprint: str) -> tuple[str, tuple[int, bytes, str] | None]:
        now = time.monotonic()
        with self._lock:
            for stale in [k for k, v in self._entries.items() if v.expires_at <= now]:
                self._entries.pop(stale, None)
            entry = self._entries.get(key)
            if entry:
                self._entries.move_to_end(key)
                if entry.fingerprint != fingerprint:
                    return "conflict", None
                return ("replay", entry.response) if entry.response else ("pending", None)
            self._entries[key] = _Entry(fingerprint, now + self.ttl_seconds)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
            return "claimed", None

    def complete(self, key: str, status: int, body: bytes, content_type: str) -> None:
        with self._lock:
            entry = self._entries.get(key)
            if entry:
                entry.response = (status, body, content_type)

    def abandon(self, key: str) -> None:
        with self._lock:
            self._entries.pop(key, None)
