"""Process-wide courtesy limits for third-party A-share data providers.

The adapters retain their own retries and fallback behaviour.  This governor
adds a small shared boundary around every adapter call so parallel refresh
jobs cannot unintentionally turn those retries into a request burst.
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict
from typing import Any, Callable


def _is_rate_limited(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None)
    if status == 429:
        return True
    text = str(exc).lower()
    return any(token in text for token in ("429", "rate limit", "rate-limit", "too many request", "请求过于频繁", "访问频繁"))


class ProviderRequestGovernor:
    """Limit simultaneous requests and pace calls separately per provider."""

    def __init__(
        self,
        *,
        max_concurrent: int | None = None,
        min_interval_seconds: float | None = None,
        cooldown_seconds: float | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._max_concurrent = max(1, int(max_concurrent or os.getenv("ASTOCK_PROVIDER_MAX_CONCURRENCY", "2")))
        self._min_interval = max(0.0, float(min_interval_seconds if min_interval_seconds is not None else os.getenv("ASTOCK_PROVIDER_MIN_INTERVAL_SECONDS", "0.25")))
        self._cooldown = max(0.0, float(cooldown_seconds if cooldown_seconds is not None else os.getenv("ASTOCK_PROVIDER_COOLDOWN_SECONDS", "15")))
        self._clock = clock
        self._sleeper = sleeper
        self._lock = threading.Lock()
        self._semaphores: dict[str, threading.BoundedSemaphore] = {}
        self._next_allowed: dict[str, float] = defaultdict(float)

    def _semaphore(self, source: str) -> threading.BoundedSemaphore:
        with self._lock:
            return self._semaphores.setdefault(source, threading.BoundedSemaphore(self._max_concurrent))

    def _wait_for_turn(self, source: str) -> None:
        with self._lock:
            now = self._clock()
            allowed = self._next_allowed[source]
            wait = max(0.0, allowed - now)
            self._next_allowed[source] = max(now, allowed) + self._min_interval
        if wait:
            self._sleeper(wait)

    def call(self, source: str, operation: Callable[[], Any]) -> Any:
        """Run *operation* under the source's shared concurrency policy."""
        source = str(source or "unknown").strip().lower() or "unknown"
        semaphore = self._semaphore(source)
        with semaphore:
            self._wait_for_turn(source)
            try:
                return operation()
            except Exception as exc:
                if _is_rate_limited(exc):
                    with self._lock:
                        self._next_allowed[source] = max(
                            self._next_allowed[source], self._clock() + self._cooldown
                        )
                raise
