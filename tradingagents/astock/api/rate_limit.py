"""Bounded, dependency-free fixed-window request limiter.

This is intentionally process-local.  It protects a standalone API process;
deployments with multiple workers must configure a shared edge/Redis limiter.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict


class FixedWindowRateLimiter:
    def __init__(self, limit: int = 300, window_seconds: float = 60, max_keys: int = 10000) -> None:
        self.limit = max(1, int(limit))
        self.window_seconds = max(1.0, float(window_seconds))
        self.max_keys = max(1, int(max_keys))
        self._entries: OrderedDict[str, tuple[float, int]] = OrderedDict()
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int | None = None) -> tuple[bool, int]:
        now = time.monotonic()
        effective_limit = self.limit if limit is None else max(1, int(limit))
        with self._lock:
            start, count = self._entries.get(key, (now, 0))
            if now - start >= self.window_seconds:
                start, count = now, 0
            count += 1
            self._entries[key] = (start, count)
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_keys:
                self._entries.popitem(last=False)
            return count <= effective_limit, max(0, int(self.window_seconds - (now - start)) + 1)
