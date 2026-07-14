"""Ops and audit API routes — Phase 37.

Provides REST endpoints for querying the AuditStore: tasks, events, and
aggregated stats.  Uses a module-level singleton AuditStore instance.

Error responses follow ``{"error": ..., "status": N}``.
"""

from __future__ import annotations

import logging

import threading
from typing import Any

from flask import Blueprint, Response, jsonify, request
logger = logging.getLogger(__name__)

bp = Blueprint("ops", __name__)

# Module-level AuditStore singleton (lazily initialised, thread-safe)
_audit_store: Any = None
_audit_store_lock = threading.Lock()


def _safe_int(val: str | None, default: int) -> int:
    """Convert *val* to int, returning *default* on failure."""
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _get_audit_store() -> Any:
    global _audit_store
    if _audit_store is None:
        from tradingagents.astock.execution.audit_store import AuditStore
        with _audit_store_lock:
            if _audit_store is None:
                _audit_store = AuditStore()
    return _audit_store


# ---------------------------------------------------------------------------
# GET /api/v1/ops/audit — List audit events
# ---------------------------------------------------------------------------


@bp.route("/ops/audit")
def list_audit_events() -> tuple[Response, int]:
    """List audit events with optional filters.

    Query parameters
    ----------------
    actor : str, optional
        Filter by actor name.
    action : str, optional
        Filter by action name.
    limit : int, optional
        Max number of events to return (default 50).

    Returns
    -------
    JSON list of audit event dicts.
    """
    try:
        store = _get_audit_store()
        actor = request.args.get("actor")
        action = request.args.get("action")
        limit = _safe_int(request.args.get("limit"), 50)
        events = store.list_events(actor=actor, action=action, limit=limit)
        return jsonify(events), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# GET /api/v1/ops/tasks — List task runs
# ---------------------------------------------------------------------------


@bp.route("/ops/tasks")
def list_tasks() -> tuple[Response, int]:
    """List task runs with optional type filter.

    Query parameters
    ----------------
    type : str, optional
        Filter by task type.
    limit : int, optional
        Max number of tasks to return (default 50).

    Returns
    -------
    JSON list of task dicts.
    """
    try:
        store = _get_audit_store()
        task_type = request.args.get("type")
        limit = _safe_int(request.args.get("limit"), 50)
        tasks = store.list_tasks(task_type=task_type, limit=limit)
        return jsonify(tasks), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# GET /api/v1/ops/tasks/<task_id> — Single task query
# ---------------------------------------------------------------------------


@bp.route("/ops/tasks/<task_id>")
def get_task(task_id: str) -> tuple[Response, int]:
    """Get a single task by ID.

    Returns
    -------
    JSON dict with the task record, or 404 if not found.
    """
    try:
        store = _get_audit_store()
        task = store.get_task(task_id)
        if task is None:
            return jsonify({"error": f"Task not found: {task_id}", "status": 404}), 404
        return jsonify(task), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# POST /api/v1/ops/tasks/<task_id>/cancel — Cancel a task
# ---------------------------------------------------------------------------


@bp.route("/ops/tasks/<task_id>/cancel", methods=["POST"])
def cancel_task_endpoint(task_id: str) -> tuple[Response, int]:
    """Cancel an existing task.

    Returns
    -------
    JSON dict with the updated task record, or 404 if not found.
    """
    try:
        store = _get_audit_store()
        task = store.cancel_task(task_id)
        if task is None:
            return jsonify({"error": f"Task not found: {task_id}", "status": 404}), 404
        return jsonify(task), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# GET /api/v1/ops/stats — Ops dashboard statistics
# ---------------------------------------------------------------------------


@bp.route("/ops/stats")
def ops_stats() -> tuple[Response, int]:
    """Get aggregated ops dashboard statistics.

    Returns
    -------
    JSON dict with ``total_tasks``, ``total_events``, ``tasks_by_type``,
    ``tasks_by_status``, ``events_by_action``, ``recent_errors``.
    """
    try:
        store = _get_audit_store()
        stats = store.get_stats()
        return jsonify(stats), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


@bp.route("/ops/metrics")
def ops_metrics() -> tuple[Response, int]:
    """Return request counts/latency plus in-process data-job state."""
    from flask import current_app
    from .metrics import snapshot

    payload = snapshot()
    manager = current_app.config.get("DATA_JOB_MANAGER")
    if manager is not None:
        jobs = manager.list(limit=1000)
        payload["data_jobs"] = {
            "queued": sum(job.status == "queued" for job in jobs),
            "running": sum(job.status == "running" for job in jobs),
            "failed": sum(job.status == "failed" for job in jobs),
        }
    return jsonify(payload), 200


# ---------------------------------------------------------------------------
# GET /api/v1/ops/scheduler/status — PaperTradeScheduler lifecycle status
# ---------------------------------------------------------------------------


@bp.route("/ops/scheduler/status")
def scheduler_status() -> tuple[Response, int]:
    """Return scheduler lifecycle status from EventBus and AuditStore.

    Returns scheduler state: running/paused/stopped, cycle count,
    last activity, and recent task lifecycle events.
    """
    try:
        # Query recent cycle events from audit store
        store = _get_audit_store()
        events = store.list_events(limit=20) or []
        tasks = store.list_tasks(limit=10) or []

        # Filter scheduler-related events
        cycle_events = [
            e for e in events
            if (e.get("action") or "").startswith("scheduler.")
            or (e.get("action") or "") in ("cycle_start", "cycle_complete", "cycle_error")
        ]

        # Count recent cycle events
        cycle_count = sum(
            1 for e in events
            if (e.get("action") or "") == "cycle_complete"
        )

        # Determine scheduler state from recent events
        latest_cycle = None
        for e in reversed(events):
            if (e.get("action") or "") in ("cycle_start", "cycle_complete", "cycle_error"):
                latest_cycle = e
                break

        return jsonify({
            "running": bool(latest_cycle and latest_cycle.get("action") != "cycle_error"),
            "cycle_count": cycle_count,
            "last_activity": latest_cycle.get("timestamp") if latest_cycle else None,
            "recent_cycles": cycle_events[:5],
            "active_tasks": [
                t for t in tasks if t.get("status") in ("queued", "running")
            ][:5],
            "status": "ok",
        }), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


__all__ = ["bp"]
