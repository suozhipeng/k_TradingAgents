"""Stats implementations for AuditStore."""

from __future__ import annotations

from typing import Any


def get_stats_impl(store) -> dict[str, Any]:
    """Get aggregated statistics."""
    with store._lock:
        tasks = list(store._tasks.values())
        events = list(store._event_log)

    total_tasks = len(tasks)
    total_events = len(events)

    tasks_by_type: dict[str, int] = {}
    tasks_by_status: dict[str, int] = {}
    for t in tasks:
        tt = t.get("task_type", "unknown")
        tasks_by_type[tt] = tasks_by_type.get(tt, 0) + 1
        st = t.get("status", "unknown")
        tasks_by_status[st] = tasks_by_status.get(st, 0) + 1

    events_by_action: dict[str, int] = {}
    for e in events:
        act = e.get("action", "unknown")
        events_by_action[act] = events_by_action.get(act, 0) + 1

    # last 10 failed tasks
    failed = [t for t in tasks if t.get("status") == "failed"]
    failed.sort(key=lambda t: t.get("finished_at") or t.get("started_at") or "", reverse=True)
    recent_errors = failed[:10]

    return {
        "total_tasks": total_tasks,
        "total_events": total_events,
        "tasks_by_type": tasks_by_type,
        "tasks_by_status": tasks_by_status,
        "events_by_action": events_by_action,
        "recent_errors": recent_errors,
    }
