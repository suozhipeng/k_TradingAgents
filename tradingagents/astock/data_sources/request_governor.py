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


class ProviderRequestTimeoutError(TimeoutError):
    """Raised when a request cannot obtain a provider slot before its deadline."""


def _is_rate_limited(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None)
    if status == 429:
        return True
    text = str(exc).lower()
    return any(token in text for token in ("429", "rate limit", "rate-limit", "too many request", "请求过于频繁", "访问频繁"))


class ProviderRequestGovernor:
    """Apply shared global and per-provider courtesy limits.

    The global limit protects local resources while the per-provider limit
    prevents a five-worker refresh from bursting a single third-party source.
    """

    def __init__(
        self,
        *,
        max_concurrent: int | None = None,
        provider_max_concurrent: int | None = None,
        min_interval_seconds: float | None = None,
        cooldown_seconds: float | None = None,
        request_timeout_seconds: float | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._max_concurrent = max(1, int(max_concurrent or os.getenv("ASTOCK_NETWORK_MAX_CONCURRENCY", "5")))
        self._provider_max_concurrent = max(1, int(provider_max_concurrent or os.getenv("ASTOCK_PROVIDER_MAX_CONCURRENCY", "1")))
        self._min_interval = max(0.0, float(min_interval_seconds if min_interval_seconds is not None else os.getenv("ASTOCK_PROVIDER_MIN_INTERVAL_SECONDS", "0.25")))
        self._cooldown = max(0.0, float(cooldown_seconds if cooldown_seconds is not None else os.getenv("ASTOCK_PROVIDER_COOLDOWN_SECONDS", "15")))
        self._request_timeout = max(0.1, float(request_timeout_seconds if request_timeout_seconds is not None else os.getenv("ASTOCK_PROVIDER_REQUEST_TIMEOUT_SECONDS", "30")))
        self._clock = clock
        self._sleeper = sleeper
        self._lock = threading.Lock()
        self._semaphores: dict[str, threading.BoundedSemaphore] = {}
        self._global_semaphore = threading.BoundedSemaphore(self._max_concurrent)
        self._next_allowed: dict[str, float] = defaultdict(float)

    def _semaphore(self, source: str) -> threading.BoundedSemaphore:
        with self._lock:
            return self._semaphores.setdefault(source, threading.BoundedSemaphore(self._provider_max_concurrent))

    def _wait_for_turn(self, source: str, deadline: float) -> None:
        with self._lock:
            now = self._clock()
            allowed = self._next_allowed[source]
            wait = max(0.0, allowed - now)
            if wait > max(0.0, deadline - now):
                raise ProviderRequestTimeoutError("request deadline exceeded while pacing {0}".format(source))
            self._next_allowed[source] = max(now, allowed) + self._min_interval
        if wait:
            self._sleeper(wait)

    def call(self, source: str, operation: Callable[[], Any], *, timeout_seconds: float | None = None) -> Any:
        """Run *operation* under the source's shared concurrency policy."""
        source = str(source or "unknown").strip().lower() or "unknown"
        timeout = self._request_timeout if timeout_seconds is None else max(0.1, float(timeout_seconds))
        deadline = self._clock() + timeout
        semaphore = self._semaphore(source)
        if not self._global_semaphore.acquire(timeout=max(0.0, deadline - self._clock())):
            raise ProviderRequestTimeoutError("request deadline exceeded waiting for global network capacity")
        try:
            if not semaphore.acquire(timeout=max(0.0, deadline - self._clock())):
                raise ProviderRequestTimeoutError("request deadline exceeded waiting for provider capacity: {0}".format(source))
            try:
                self._wait_for_turn(source, deadline)
                if self._clock() >= deadline:
                    raise ProviderRequestTimeoutError("request deadline exceeded before provider call: {0}".format(source))
                return operation()
            except Exception as exc:
                if _is_rate_limited(exc):
                    with self._lock:
                        self._next_allowed[source] = max(
                            self._next_allowed[source], self._clock() + self._cooldown
                        )
                raise
            finally:
                semaphore.release()
        finally:
            self._global_semaphore.release()


_shared_governor: ProviderRequestGovernor | None = None
_shared_governor_lock = threading.Lock()


def get_provider_request_governor() -> ProviderRequestGovernor:
    """Return the single governor shared by every router in this process."""
    global _shared_governor
    with _shared_governor_lock:
        if _shared_governor is None:
            _shared_governor = ProviderRequestGovernor()
        return _shared_governor
