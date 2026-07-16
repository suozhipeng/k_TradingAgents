"""Phase 37 — Ops & Audit Center: audit event persistence layer.

Thread-safe in-memory store for TaskRun and AuditEvent records with
optional DuckDB persistence.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

from ...schemas.ops_audit import AuditEvent, TaskRun, TaskType
from .tasks import record_task_impl, update_task_impl, cancel_task_impl, get_task_impl, list_tasks_impl
from .events import record_event_impl, list_events_impl
from .stats import get_stats_impl
from .persistence import _persist_task_impl, _persist_event_impl


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
        return record_task_impl(self, task)

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
            New status value (e.g. ``"running"``, ``"completed"``,
            ``"failed"``).
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
        return update_task_impl(self, task_id, status, progress, error, result)

    def cancel_task(self, task_id: str) -> dict[str, Any] | None:
        """Cancel an existing task.  Sets status to 'cancelled'.

        Returns
        -------
        dict or None
            The updated task dict, or ``None`` if no task exists.
        """
        return cancel_task_impl(self, task_id)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        """Get a task by ID.  Returns ``None`` if not found."""
        return get_task_impl(self, task_id)

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
        return list_tasks_impl(self, task_type, limit, offset)

    # ------------------------------------------------------------------
    # Event API
    # ------------------------------------------------------------------

    def record_event(self, event: AuditEvent | dict[str, Any]) -> str:
        """Record an audit event.  Returns ``event_id``.

        If the provided *event* (or dict) does not have an ``event_id``,
        one will be generated automatically.  If ``created_at`` is empty,
        the current UTC timestamp is used.
        """
        return record_event_impl(self, event)

    def list_events(
        self,
        actor: str | None = None,
        action: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List audit events with optional filters.

        Returns events newest-first from the ordered event log.
        """
        return list_events_impl(self, actor, action, limit)

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
        return get_stats_impl(self)

    # ------------------------------------------------------------------
    # DuckDB persistence (private helpers)
    # ------------------------------------------------------------------

    def _persist_task(self, task: dict[str, Any]) -> None:
        _persist_task_impl(self, task)

    def _persist_event(self, event: dict[str, Any]) -> None:
        _persist_event_impl(self, event)

    # ---- Lifecycle --------------------------------------------------------

    def close(self) -> None:
        """Close the DuckDB connection if open."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                logger.debug("AuditStore: failed to close DuckDB connection", exc_info=True)
            self._conn = None

    def __enter__(self) -> "AuditStore":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


__all__ = [
    "AuditStore",
]
