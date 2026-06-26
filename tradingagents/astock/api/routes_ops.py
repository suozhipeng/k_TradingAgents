"""Ops and audit API routes — Phase 37.

Provides REST endpoints for querying the AuditStore: tasks, events, and
aggregated stats.  Uses a module-level singleton AuditStore instance.

Error responses follow ``{"error": ..., "status": N}``.
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, Response, jsonify, request

bp = Blueprint("ops", __name__)

# Module-level AuditStore singleton (lazily initialised)
_audit_store: Any = None


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


__all__ = ["bp"]
