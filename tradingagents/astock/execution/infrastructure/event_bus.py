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
    _subscribers: list[str] = []  # subscriber IDs (for future use)

    MAX_EVENTS: int = 1000

    @classmethod
    def publish(cls, event: dict[str, Any]) -> None:
        """Push an event into the ring buffer.

        Parameters
        ----------
        event : dict
            Arbitrary JSON-serialisable event payload.
        """
        with cls._lock:
            cls._buffer.append(dict(event))

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

    @classmethod
    def size(cls) -> int:
        """Return the number of buffered events."""
        with cls._lock:
            return len(cls._buffer)

    @classmethod
    def to_json_list(cls) -> str:
        """Return all buffered events as a JSON array string."""
        events = cls.peek_all()
        return json.dumps(events, ensure_ascii=False)
