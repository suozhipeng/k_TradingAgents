"""Simple in-process event bus for SSE streaming.

Provides a lightweight publish/subscribe pattern so that paper trading
cycles can broadcast progress events to SSE endpoints without coupling.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)


class EventBus:
    """In-memory ring-buffer event bus for SSE.

    Thread-safe: publish / poll / subscribe use a per-subscriber deque
    protected by a ``threading.RLock`` (reentrant lock).

    Usage::

        EventBus.publish({"type": "trade", "symbol": "600519.SH", ...})
        event = EventBus.poll()   # oldest unseen event or None
    """

    _lock = threading.RLock()
    _buffer: deque[dict[str, Any]] = deque(maxlen=1000)
    _subscribers: dict[str, deque[dict[str, Any]]] = {}
    # Tracks when each subscriber was last polled (for stale cleanup)
    _subscriber_last_seen: dict[str, float] = {}
    # Per-subscriber locks to protect individual deque mutations during poll
    _subscriber_locks: dict[str, threading.Lock] = {}

    MAX_EVENTS: int = 1000
    MAX_SUBSCRIBERS: int = 50
    STALE_TIMEOUT_SECONDS: float = 300.0  # 5 minutes

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @classmethod
    def _get_subscriber_lock(cls, subscriber_id: str) -> threading.Lock:
        """Return (or create) a per-subscriber lock."""
        with cls._lock:
            if subscriber_id not in cls._subscriber_locks:
                cls._subscriber_locks[subscriber_id] = threading.Lock()
            return cls._subscriber_locks[subscriber_id]

    @classmethod
    def _cleanup_stale_subscribers(cls) -> None:
        """Remove subscribers that haven't been polled within STALE_TIMEOUT."""
        now = time.monotonic()
        stale_ids: list[str] = []
        with cls._lock:
            for sid, last_seen in cls._subscriber_last_seen.items():
                if now - last_seen > cls.STALE_TIMEOUT_SECONDS:
                    stale_ids.append(sid)
            for sid in stale_ids:
                cls._subscribers.pop(sid, None)
                cls._subscriber_locks.pop(sid, None)
                cls._subscriber_last_seen.pop(sid, None)
        for sid in stale_ids:
            logger.debug("Removed stale SSE subscriber: %s", sid)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def publish(cls, event: dict[str, Any]) -> None:
        """Push an event into the ring buffer.

        Parameters
        ----------
        event : dict
            Arbitrary JSON-serialisable event payload.
        """
        with cls._lock:
            item = dict(event)
            cls._buffer.append(item)
            for queue in cls._subscribers.values():
                queue.append(dict(item))

    @classmethod
    def subscribe(cls, max_subscribers: int | None = None) -> str | None:
        """Create an independent event cursor for one SSE client."""
        subscriber_id = uuid.uuid4().hex
        with cls._lock:
            limit = cls.MAX_SUBSCRIBERS if max_subscribers is None else max(1, int(max_subscribers))
            if len(cls._subscribers) >= limit:
                return None
            cls._cleanup_stale_subscribers()
            # Copy current buffer contents into a new bounded deque
            snapshot = list(cls._buffer)
            cls._subscribers[subscriber_id] = deque(snapshot, maxlen=cls.MAX_EVENTS)
            cls._subscriber_last_seen[subscriber_id] = time.monotonic()
        return subscriber_id

    @classmethod
    def poll_subscriber(cls, subscriber_id: str) -> dict[str, Any] | None:
        """Poll the next event for a specific subscriber."""
        sub_lock = cls._get_subscriber_lock(subscriber_id)
        with sub_lock:
            queue = cls._subscribers.get(subscriber_id)
            if queue is None:
                return None
            item = queue.popleft() if queue else None
        # Update last-seen outside the sub-lock to avoid holding it too long
        with cls._lock:
            cls._subscriber_last_seen[subscriber_id] = time.monotonic()
        return item

    @classmethod
    def unsubscribe(cls, subscriber_id: str) -> None:
        """Remove a subscriber and its lock."""
        with cls._lock:
            cls._subscribers.pop(subscriber_id, None)
            cls._subscriber_locks.pop(subscriber_id, None)
            cls._subscriber_last_seen.pop(subscriber_id, None)

    @classmethod
    def poll(cls) -> dict[str, Any] | None:
        """Pop the oldest unseen event from the buffer.

        Returns
        -------
        dict or None
            The oldest event, or ``None`` if the buffer is empty.
        """
        with cls._lock:
            if cls._buffer:
                return cls._buffer.popleft()
            return None

    @classmethod
    def peek_all(cls) -> list[dict[str, Any]]:
        """Return a copy of all buffered events without removing them.

        Returns
        -------
        list[dict]
            All buffered events (oldest first).
        """
        with cls._lock:
            return list(cls._buffer)

    @classmethod
    def clear(cls) -> None:
        """Clear all buffered events and remove all subscribers."""
        with cls._lock:
            cls._buffer.clear()
            for queue in cls._subscribers.values():
                queue.clear()
            cls._subscribers.clear()
            cls._subscriber_last_seen.clear()
            cls._subscriber_locks.clear()

    @classmethod
    def size(cls) -> int:
        """Return the number of buffered events."""
        with cls._lock:
            return len(cls._buffer)

    @classmethod
    def subscriber_count(cls) -> int:
        with cls._lock:
            return len(cls._subscribers)

    @classmethod
    def to_json_list(cls) -> str:
        """Return all buffered events as a JSON array string."""
        events = cls.peek_all()
        return json.dumps(events, ensure_ascii=False)
