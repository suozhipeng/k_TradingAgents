"""DuckDB persistence implementations for AuditStore."""

from __future__ import annotations

import json
from typing import Any


def _persist_task_impl(store, task: dict[str, Any]) -> None:
    if store._conn is None:
        return

    store._conn.execute(
        """
        INSERT INTO audit_tasks
            (task_id, task_type, status, progress,
             started_at, finished_at, error, result)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (task_id) DO UPDATE SET
            status      = EXCLUDED.status,
            progress    = EXCLUDED.progress,
            started_at  = EXCLUDED.started_at,
            finished_at = EXCLUDED.finished_at,
            error       = EXCLUDED.error,
            result      = EXCLUDED.result
        """,
        [
            task.get("task_id"),
            task.get("task_type"),
            task.get("status"),
            task.get("progress", 0.0),
            task.get("started_at"),
            task.get("finished_at"),
            json.dumps(task.get("error")) if task.get("error") else None,
            json.dumps(task.get("result")) if task.get("result") else None,
        ],
    )


def _persist_event_impl(store, event: dict[str, Any]) -> None:
    if store._conn is None:
        return

    store._conn.execute(
        """
        INSERT INTO audit_events
            (event_id, actor, action, input_snapshot, output_snapshot,
             model, confirmation_required, confirmed_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (event_id) DO NOTHING
        """,
        [
            event.get("event_id"),
            event.get("actor"),
            event.get("action"),
            json.dumps(event.get("input_snapshot", {})),
            json.dumps(event.get("output_snapshot", {})),
            event.get("model"),
            event.get("confirmation_required", False),
            event.get("confirmed_by"),
            event.get("created_at"),
        ],
    )
