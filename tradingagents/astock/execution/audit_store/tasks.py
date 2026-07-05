"""Task API implementations for AuditStore."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4


def record_task_impl(store, task: Any) -> str:
    """Record a task run.  Returns ``task_id``."""
    d = store._to_task_dict(task)
    if not d.get("task_id"):
        d["task_id"] = f"task_{uuid4().hex[:12]}"

    with store._lock:
        store._tasks[d["task_id"]] = d

    store._persist_task(d)
    return d["task_id"]


def update_task_impl(
    store,
    task_id: str,
    status: str,
    progress: float | None = None,
    error: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Update an existing task."""
    with store._lock:
        task = store._tasks.get(task_id)
        if task is None:
            return None

        task["status"] = status
        if progress is not None:
            task["progress"] = progress
        if error is not None:
            task["error"] = error
        if result is not None:
            task["result"] = result

        if status in ("completed", "failed", "cancelled") and not task.get("finished_at"):
            task["finished_at"] = datetime.utcnow().isoformat()
        if status in ("running", "queued") and not task.get("started_at"):
            task["started_at"] = datetime.utcnow().isoformat()

    store._persist_task(task)
    return task


def cancel_task_impl(store, task_id: str) -> dict[str, Any] | None:
    """Cancel an existing task.  Sets status to 'cancelled'."""
    return update_task_impl(store, task_id, status="cancelled")


def get_task_impl(store, task_id: str) -> dict[str, Any] | None:
    """Get a task by ID.  Returns ``None`` if not found."""
    with store._lock:
        return store._tasks.get(task_id)


def list_tasks_impl(
    store,
    task_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List tasks with optional type filter."""
    with store._lock:
        items: list[dict[str, Any]] = list(store._tasks.values())

    if task_type is not None:
        items = [t for t in items if t.get("task_type") == task_type]

    # Reverse so newest is first
    items.reverse()
    return items[offset : offset + limit]
