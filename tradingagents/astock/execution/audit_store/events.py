"""Event API implementations for AuditStore."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4


def record_event_impl(store, event: Any) -> str:
    """Record an audit event.  Returns ``event_id``."""
    d = store._to_event_dict(event)
    if not d.get("event_id"):
        d["event_id"] = f"evt_{uuid4().hex[:12]}"
    if not d.get("created_at"):
        d["created_at"] = datetime.utcnow().isoformat()

    with store._lock:
        store._audit_events[d["event_id"]] = d
        store._event_log.append(d)

    store._persist_event(d)
    return d["event_id"]


def list_events_impl(
    store,
    actor: str | None = None,
    action: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List audit events with optional filters."""
    with store._lock:
        items = list(store._event_log)

    if actor is not None:
        items = [e for e in items if e.get("actor") == actor]
    if action is not None:
        items = [e for e in items if e.get("action") == action]

    items.reverse()
    return items[:limit]
