"""Shared API-key resolution and a multi-process-safe rate limiter.

Two concerns were previously duplicated/insecure across the auth layer:

1. ``validate_api_key`` was invoked from three places (``require_auth``,
   ``optional_auth`` and the write-route ``before_request`` hook), each with
   its own copy of the sync/async detection and ``asyncio`` handling. Any
   divergence produced inconsistent auth behaviour. ``resolve_api_key`` is now
   the single entry point.

2. The token-bucket limiter was process-local, so multi-worker deployments
   (gunicorn/uwsgi) effectively had no shared limit. ``build_rate_limiter``
   returns a Redis-backed limiter when ``ASTOCK_REDIS_URL`` is configured and
   reachable, and transparently falls back to the in-memory limiter otherwise.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# API key resolution (single source of truth)
# ---------------------------------------------------------------------------

def resolve_api_key(store: Any, key_hash: str) -> Optional[dict]:
    """Validate ``key_hash`` against ``store`` regardless of sync/async API.

    Returns the key record dict on success, or ``None`` when the store is
    missing, lacks ``validate_api_key``, the key is invalid, or validation
    raises. Failures are logged (never silently swallowed) so operators can
    audit auth problems.
    """
    if store is None or not hasattr(store, "validate_api_key"):
        return None

    validate = store.validate_api_key
    try:
        if asyncio.iscoroutinefunction(validate):
            # Never rely on asyncio.run() here: it fails inside an already
            # running loop and mutates the global loop policy. Use a private
            # loop that we own and close deterministically.
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(validate(key_hash))
            finally:
                loop.close()
        return validate(key_hash)
    except Exception:
        logger.exception("validate_api_key failed for key_hash=%s…", key_hash[:8])
        return None


# ---------------------------------------------------------------------------
# Rate limiters
# ---------------------------------------------------------------------------

class InMemoryRateLimiter:
    """Process-local sliding-window limiter. Safe under the CPython GIL only."""

    _WINDOW = 60.0

    def __init__(self) -> None:
        self._buckets: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def consume(self, key_id: str, rate: int = 100) -> tuple[bool, int]:
        if rate <= 0:
            return False, 0
        now = time.monotonic()
        cutoff = now - self._WINDOW
        with self._lock:
            log = self._buckets.setdefault(key_id, [])
            while log and log[0] <= cutoff:
                log.pop(0)
            if len(log) >= rate:
                return False, 0
            log.append(now)
            return True, rate - len(log)

    def reset(self, key_id: str) -> None:
        with self._lock:
            self._buckets.pop(key_id, None)


class RedisRateLimiter:
    """Shared sliding-window limiter backed by Redis sorted sets.

    Safe across multiple processes/workers. Each key maps to a ZSET of request
    timestamps; expired members are trimmed on every ``consume`` call and the
    key is given a TTL so idle keys are reclaimed automatically.
    """

    _WINDOW = 60.0

    def __init__(self, client: Any) -> None:
        self._redis = client

    def consume(self, key_id: str, rate: int = 100) -> tuple[bool, int]:
        if rate <= 0:
            return False, 0
        now = time.time()
        cutoff = now - self._WINDOW
        redis_key = f"ratelimit:{key_id}"
        try:
            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(redis_key, 0, cutoff)
            pipe.zadd(redis_key, {f"{now}:{os.getpid()}": now})
            pipe.zcard(redis_key)
            pipe.expire(redis_key, int(self._WINDOW) + 1)
            results = pipe.execute()
            count = int(results[2])
        except Exception:
            # Failing open silently removes the only shared limit in a
            # multi-worker deployment. Reject until Redis recovers instead.
            logger.exception("Redis rate-limit check failed; rejecting request")
            return False, 0
        if count > rate:
            return False, 0
        return True, max(0, rate - count)

    def reset(self, key_id: str) -> None:
        try:
            self._redis.delete(f"ratelimit:{key_id}")
        except Exception:
            logger.exception("Redis rate-limit reset failed")


def build_rate_limiter(redis_url: Optional[str] = None) -> Any:
    """Return a Redis-backed limiter when reachable, else the in-memory one.

    ``redis_url`` defaults to the ``ASTOCK_REDIS_URL`` environment variable.
    When unset or the connection fails, the process-local limiter is returned
    with a warning, preserving single-process behaviour.
    """
    url = redis_url or os.environ.get("ASTOCK_REDIS_URL")
    if not url:
        return InMemoryRateLimiter()
    try:
        import redis  # local import; redis is a hard dependency but optional at runtime

        client = redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        logger.info("Rate limiter using Redis backend at %s", url)
        return RedisRateLimiter(client)
    except Exception:
        logger.warning(
            "ASTOCK_REDIS_URL set but Redis is unavailable; falling back to "
            "process-local rate limiter (NOT safe for multi-worker deploys)",
            exc_info=True,
        )
        return InMemoryRateLimiter()
