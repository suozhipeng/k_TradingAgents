"""Phase 37 — Ops & Audit Center: audit event persistence layer.

Thread-safe in-memory store for TaskRun and AuditEvent records with
optional DuckDB persistence.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any
from uuid import uuid4

from ..schemas.ops_audit import AuditEvent, TaskRun, TaskType


class AuditStore:
    """Thread-safe in-memory audit store with optional DuckDB persistence.

    Stores TaskRun and AuditEvent records in-memory (dicts keyed by ID,
    plus an ordered event log).  Optionally persists to DuckDB when a
    ``db_path`` is provided on construction.

    Parameters
    ----------
    db_path : str or None
        Path to a DuckDB database file.  If ``None``, no persistence
        is used.
    """

    def __init__(self, db_path: str | None = None):
        self._lock = threading.Lock()
        self._tasks: dict[str, dict[str, Any]] = {}
        self._audit_events: dict[str, dict[str, Any]] = {}
        self._event_log: list[dict[str, Any]] = []
        self._conn = None  # optional DuckDB connection

        if db_path is not None:
            try:
                import duckdb

                self._conn = duckdb.connect(db_path)
                self._ensure_tables()
            except ImportError:
                import warnings

                warnings.warn(
                    "duckdb is not installed; AuditStore will run in "
                    "memory-only mode."
                )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_tables(self) -> None:
        """Create tables if they don't already exist."""
        if self._conn is None:
            return
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_tasks (
                task_id    VARCHAR PRIMARY KEY,
                task_type  VARCHAR NOT NULL,
                status     VARCHAR NOT NULL,
                progress   DOUBLE DEFAULT 0.0,
                started_at VARCHAR,
                finished_at VARCHAR,
                error      VARCHAR,
                result     VARCHAR
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id              VARCHAR PRIMARY KEY,
                actor                 VARCHAR NOT NULL,
                action                VARCHAR NOT NULL,
                input_snapshot        VARCHAR,
                output_snapshot       VARCHAR,
                model                 VARCHAR,
                confirmation_required BOOLEAN DEFAULT FALSE,
                confirmed_by          VARCHAR,
                created_at            VARCHAR NOT NULL
            )
            """
        )

    @staticmethod
    def _to_task_dict(task: TaskRun | dict[str, Any]) -> dict[str, Any]:
        if isinstance(task, TaskRun):
            return task.model_dump()
        return task

    @staticmethod
    def _to_event_dict(event: AuditEvent | dict[str, Any]) -> dict[str, Any]:
        if isinstance(event, AuditEvent):
            return event.model_dump()
        return event

    # ------------------------------------------------------------------
    # Task API
    # ------------------------------------------------------------------

    def record_task(self, task: TaskRun | dict[str, Any]) -> str:
        """Record a task run.  Returns ``task_id``.

        If the provided *task* (or dict) does not have a ``task_id``,
        one will be generated automatically.
        """
        d = self._to_task_dict(task)
        if not d.get("task_id"):
            d["task_id"] = f"task_{uuid4().hex[:12]}"

        with self._lock:
            self._tasks[d["task_id"]] = d

        self._persist_task(d)
        return d["task_id"]

    def update_task(
        self,
        task_id: str,
        status: str,
        progress: float | None = None,
        error: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Update an existing task.

        Parameters
        ----------
        task_id : str
            The task to update.
        status : str
            New status value (e.g. ``\"running\"``, ``\"completed\"``,
            ``\"failed\"``).
        progress : float or None
            Progress percentage (0.0–100.0).  ``None`` leaves the
            existing value unchanged.
        error : dict or None
            Error detail dict.  ``None`` leaves the existing value
            unchanged.
        result : dict or None
            Result payload.  ``None`` leaves the existing value
            unchanged.

        Returns
        -------
        dict or None
            The updated task dict, or ``None`` if no task exists with
            that ID.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None

            task["status"] = status
            if progress is not None:
                task["progress"] = progress
            if error is not None:
                task["error"] = error
            if result is not None:
                task["result"] = result

            if status in ("completed", "failed") and not task.get("finished_at"):
                task["finished_at"] = datetime.utcnow().isoformat()
            if status == "running" and not task.get("started_at"):
                task["started_at"] = datetime.utcnow().isoformat()

        self._persist_task(task)
        return task

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        """Get a task by ID.  Returns ``None`` if not found."""
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(
        self,
        task_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List tasks with optional type filter.

        Tasks are ordered newest-first by insertion order (the dict is
        insertion-ordered in Python 3.7+).
        """
        with self._lock:
            items: list[dict[str, Any]] = list(self._tasks.values())

        if task_type is not None:
            items = [t for t in items if t.get("task_type") == task_type]

        # Reverse so newest is first
        items.reverse()
        return items[offset : offset + limit]

    # ------------------------------------------------------------------
    # Event API
    # ------------------------------------------------------------------

    def record_event(self, event: AuditEvent | dict[str, Any]) -> str:
        """Record an audit event.  Returns ``event_id``.

        If the provided *event* (or dict) does not have an ``event_id``,
        one will be generated automatically.  If ``created_at`` is empty,
        the current UTC timestamp is used.
        """
        d = self._to_event_dict(event)
        if not d.get("event_id"):
            d["event_id"] = f"evt_{uuid4().hex[:12]}"
        if not d.get("created_at"):
            d["created_at"] = datetime.utcnow().isoformat()

        with self._lock:
            self._audit_events[d["event_id"]] = d
            self._event_log.append(d)

        self._persist_event(d)
        return d["event_id"]

    def list_events(
        self,
        actor: str | None = None,
        action: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List audit events with optional filters.

        Returns events newest-first from the ordered event log.
        """
        with self._lock:
            items = list(self._event_log)

        if actor is not None:
            items = [e for e in items if e.get("actor") == actor]
        if action is not None:
            items = [e for e in items if e.get("action") == action]

        items.reverse()
        return items[:limit]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Get aggregated statistics.

        Returns
        -------
        dict
            ``total_tasks``, ``total_events``,
            ``tasks_by_type`` (``{task_type: count}``),
            ``tasks_by_status`` (``{status: count}``),
            ``events_by_action`` (``{action: count}``),
            ``recent_errors`` — list of the last 10 failed task dicts.
        """
        with self._lock:
            tasks = list(self._tasks.values())
            events = list(self._event_log)

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

    # ------------------------------------------------------------------
    # DuckDB persistence (private helpers)
    # ------------------------------------------------------------------

    def _persist_task(self, task: dict[str, Any]) -> None:
        if self._conn is None:
            return
        import json

        self._conn.execute(
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

    def _persist_event(self, event: dict[str, Any]) -> None:
        if self._conn is None:
            return
        import json

        self._conn.execute(
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


__all__ = [
    "AuditStore",
]
