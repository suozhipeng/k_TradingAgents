"""Simple in-process event bus for SSE streaming.

Provides a lightweight publish/subscribe pattern so that paper trading
cycles can broadcast progress events to SSE endpoints without coupling.
"""

from __future__ import annotations

import json
import threading
from collections import deque
from typing import Any


class EventBus:
    """In-memory ring-buffer event bus for SSE.

    Thread-safe: publish / poll / subscribe use a per-subscriber deque
    protected by a ``threading.Lock``.

    Usage::

        EventBus.publish({"type": "trade", "symbol": "600519.SH", ...})
        event = EventBus.poll()   # oldest unseen event or None
    """

    _lock = threading.Lock()
    _buffer: deque[dict[str, Any]] = deque(maxlen=1000)
    _subscribers: dict[str, deque[dict[str, Any]]] = {}

    MAX_EVENTS: int = 1000
    MAX_SUBSCRIBERS: int = 50

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
        import uuid

        subscriber_id = uuid.uuid4().hex
        with cls._lock:
            limit = cls.MAX_SUBSCRIBERS if max_subscribers is None else max(1, int(max_subscribers))
            if len(cls._subscribers) >= limit:
                return None
            # New clients receive the current retained context once, then only
            # their own subsequent events.  The bounded deque prevents a slow
            # browser from consuming unbounded process memory.
            cls._subscribers[subscriber_id] = deque(cls._buffer, maxlen=cls.MAX_EVENTS)
        return subscriber_id

    @classmethod
    def poll_subscriber(cls, subscriber_id: str) -> dict[str, Any] | None:
        with cls._lock:
            queue = cls._subscribers.get(subscriber_id)
            return queue.popleft() if queue else None

    @classmethod
    def unsubscribe(cls, subscriber_id: str) -> None:
        with cls._lock:
            cls._subscribers.pop(subscriber_id, None)

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
        """Clear all buffered events."""
        with cls._lock:
            cls._buffer.clear()
            for queue in cls._subscribers.values():
                queue.clear()

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
