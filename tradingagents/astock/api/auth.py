"""
API key authentication for AStock Pro.
Supports Bearer token -> api_keys lookup (PGStore -> DuckDB fallback).
Rate limiting via token bucket (sliding window).
"""

import hashlib
import time
import logging
from functools import wraps
from typing import Any, Callable, Optional

from flask import request, g, jsonify, current_app

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Token bucket rate limiter (sliding window, per-process, in-memory)
# ---------------------------------------------------------------------------

class TokenBucket:
    """Per-key sliding-window rate limiter.

    The window is 60 seconds wide.  Each key gets at most ``rate`` tokens
    per window.  Tokens are consumed at a granularity of 1 request = 1 token.
    The implementation uses a **sliding window log** approach — the list of
    request timestamps is pruned to the last ``rate`` entries within the past
    60 s, keeping memory bounded to O(rate) per active key.

    Thread-safe for GIL-guarded CPython usage (Flask default).  Not safe
    across multiple processes; use Redis-backed limiter for multi-worker deploys.
    """

    _WINDOW: float = 60.0  # sliding window width in seconds

    def __init__(self) -> None:
        # {key_id: [timestamp_of_last_N_requests, ...]}
        # Timestamps are pruned opportunistically on each consume() call.
        self._buckets: dict[str, list[float]] = {}

    def consume(self, key_id: str, rate: int = 100) -> tuple[bool, int]:
        """Attempt to consume 1 token for *key_id*.

        Parameters
        ----------
        key_id : str
            Unique API key identifier.
        rate : int
            Maximum allowed tokens per 60-second window.  Default 100.

        Returns
        -------
        (allowed, remaining)
            allowed : bool
                True if the request is within rate limits.
            remaining : int
                Number of tokens remaining in the current window (>= 0).
        """
        if rate <= 0:
            return False, 0

        now = time.monotonic()
        window = self._WINDOW
        cutoff = now - window

        # Get or create the request log for this key
        log = self._buckets.get(key_id)
        if log is None:
            log = []
            self._buckets[key_id] = log

        # Prune entries outside the window
        # Since the log is time-ordered (monotonic insertion), we can
        # binary-search for the first entry >= cutoff and drop everything
        # before it.  A linear scan from the front is also fine because
        # the list is bounded by *rate* entries at most.
        while log and log[0] <= cutoff:
            log.pop(0)

        # Check limit
        if len(log) >= rate:
            # Rate exceeded — return the number of tokens available when the
            # oldest entry slides out.
            oldest = log[0]
            wait_time = oldest + window - now
            # remaining will be 0 when at capacity
            return False, 0

        # Allow — record timestamp
        log.append(now)

        remaining = rate - len(log)
        return True, remaining

    def get_remaining(self, key_id: str, rate: int = 100) -> int:
        """Return how many tokens are still available (without consuming)."""
        now = time.monotonic()
        cutoff = now - self._WINDOW
        log = self._buckets.get(key_id)
        if log is None:
            return rate
        # Prune stale entries for accurate count
        while log and log[0] <= cutoff:
            log.pop(0)
        return max(0, rate - len(log))

    def reset(self, key_id: str) -> None:
        """Manually clear the bucket for *key_id* (e.g. after key rotation)."""
        self._buckets.pop(key_id, None)


# Module-level singleton
bucket = TokenBucket()


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def require_auth(roles: Optional[list[str]] = None):
    """Decorator: require a valid API key with optional role check.

    Extracts ``Authorization: Bearer <key>`` from the request header,
    SHA-256 hashes it, and looks it up in the store (PGStore -> DuckDB).

    On success populates::

        g.actor      — key_id
        g.role       — role string (e.g. "admin", "readonly")
        g.key_id     — same as g.actor
        g.allowed_capabilities — capability string from the key record

    Usage::

        @require_auth(roles=["admin"])
        def admin_route():
            ...

        @require_auth()
        def any_authenticated_route():
            ...
    """
    def decorator(f: Callable):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({
                    "error": "missing_auth",
                    "message": "Authorization: Bearer <key> required"
                }), 401

            api_key = auth_header[7:]
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()

            # Try PGStore first, fall back to DuckDB
            store = getattr(g, "pg_store", None) or getattr(g, "store", None)
            if store is None:
                store = current_app.config.get("STORE")
            if store is None:
                return jsonify({
                    "error": "no_store",
                    "message": "Database not connected"
                }), 500

            # validate_api_key is sync (DuckDB) or async (PG) — handle both
            try:
                import asyncio
                if asyncio.iscoroutinefunction(store.validate_api_key):
                    record = asyncio.run(store.validate_api_key(key_hash))
                else:
                    record = store.validate_api_key(key_hash)
            except Exception:
                logger.exception("validate_api_key failed")
                record = None

            if record is None:
                return jsonify({
                    "error": "invalid_key",
                    "message": "Invalid or expired API key"
                }), 401

            # Role check
            key_role = record.get("role", "readonly")
            if roles and key_role not in roles:
                return jsonify({
                    "error": "forbidden",
                    "message": f"Requires one of: {roles}"
                }), 403

            # Rate limit check
            rate_limit = record.get("rate_limit", 100)
            if isinstance(rate_limit, str):
                try:
                    rate_limit = int(rate_limit)
                except (ValueError, TypeError):
                    rate_limit = 100
            allowed, _ = bucket.consume(record["key_id"], rate_limit)
            if not allowed:
                return jsonify({
                    "error": "rate_limited",
                    "message": "Rate limit exceeded"
                }), 429

            # Populate g
            g.actor = record.get("key_id", "unknown")
            g.role = key_role
            g.key_id = record.get("key_id", "")
            g.allowed_capabilities = record.get("allowed_capabilities", "")

            return f(*args, **kwargs)
        return decorated
    return decorator


def optional_auth(f: Callable):
    """Decorator: populate ``g.actor`` / ``g.role`` if a Bearer token is
    present and valid, but never block the request.

    Sets safe defaults::

        g.actor = "anonymous"
        g.role  = "public"
        g.key_id = ""

    If a valid key is found, those fields are replaced with the key record
    values.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        g.actor = "anonymous"
        g.role = "public"
        g.key_id = ""
        g.allowed_capabilities = ""

        # Try to extract identity from header but don't fail
        try:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                key_hash = hashlib.sha256(auth_header[7:].encode()).hexdigest()
                store = getattr(g, "pg_store", None) or getattr(g, "store", None)
                if store is None:
                    store = current_app.config.get("STORE")
                if store:
                    import asyncio
                    if asyncio.iscoroutinefunction(store.validate_api_key):
                        record = asyncio.run(store.validate_api_key(key_hash))
                    else:
                        record = store.validate_api_key(key_hash)
                    if record:
                        g.actor = record["key_id"]
                        g.role = record.get("role", "public")
                        g.key_id = record["key_id"]
                        g.allowed_capabilities = record.get("allowed_capabilities", "")
        except Exception:
            pass
        return f(*args, **kwargs)
    return decorated
