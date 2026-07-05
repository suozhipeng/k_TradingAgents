"""SSE (Server-Sent Events) routes for real-time streaming.

Provides a Flask blueprint with an SSE endpoint that polls the
:class:`EventBus` and streams events to connected clients.

Events are wrapped with ``TaskRun``-shaped fields for standardization
(see ``tradingagents.astock.schemas.ops_audit.TaskRun``).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Generator

from flask import Blueprint, Response, current_app, jsonify, request

from tradingagents.astock.execution.event_bus import EventBus
from tradingagents.astock.schemas.ops_audit import TaskType

bp = Blueprint("sse", __name__)

logger = logging.getLogger(__name__)

# Default SSE poll interval (seconds)
_DEFAULT_POLL_INTERVAL: float = 1.0
# Maximum events to send per poll
_MAX_EVENTS_PER_POLL: int = 10

# ── Type → TaskRun mapping ─────────────────────────────────────────────

_TASK_TYPE_MAP: dict[str, TaskType] = {
    "cycle_start": TaskType.RESEARCH,
    "cycle_complete": TaskType.RESEARCH,
    "cycle_error": TaskType.RESEARCH,
    "trade": TaskType.TRADE,
    "error": TaskType.DATA_REFRESH,
}

_TASK_RUN_FIELDS = frozenset({
    "task_id", "task_type", "status", "progress",
    "started_at", "finished_at", "error", "result",
})


def _to_task_run(event: dict[str, Any]) -> dict[str, Any]:
    """Wrap a raw EventBus event dict with ``TaskRun``-shaped fields.

    The original event keys are preserved so downstream consumers are
    not broken; standard ``TaskRun`` fields are overlayed on top.
    """
    now = datetime.utcnow().isoformat()
    event_type = event.get("type", "unknown")
    task_type = _TASK_TYPE_MAP.get(event_type, TaskType.DATA_REFRESH)
    task_id: str = event.get("task_id") or f"sse-{uuid.uuid4().hex[:8]}"

    # Determine status from event type
    status_map: dict[str, str] = {
        "cycle_start": "running",
        "cycle_complete": "success",
        "cycle_error": "failed",
        "error": "failed",
        "trade": "success",
        "idle": "idle",
    }
    status = status_map.get(event_type, "running")

    # Extract temporal fields
    ts = event.get("timestamp", now)
    finished_at: str | None
    if status in ("success", "failed"):
        finished_at = ts
    else:
        finished_at = None

    # Build error block for failures
    error: dict[str, Any] | None = None
    if status == "failed" and "message" in event:
        error = {"message": event["message"], "timestamp": ts}

    # Assemble TaskRun fields, then merge original non-TaskRun keys
    task_run_fields = {
        "task_id": task_id,
        "task_type": task_type.value,
        "status": status,
        "progress": float(event.get("progress", 0)),
        "started_at": ts,
        "finished_at": finished_at,
        "error": error,
        "result": event.get("result"),
    }

    # Merge: TaskRun fields take priority, but keep any original keys
    # that aren't in the TaskRun spec so nothing is lost.
    result = dict(event)
    result.update(task_run_fields)
    return result


# ---------------------------------------------------------------------------
# GET /api/v1/sse/paper-progress
# ---------------------------------------------------------------------------


@bp.route("/sse/paper-progress")
def paper_progress_sse() -> Response:
    """SSE streaming endpoint for paper trading progress.

    Yields ``text/event-stream`` data lines.  Each event is a JSON object
    with standard ``TaskRun`` fields.  When no events are available, an idle
    heartbeat is sent every second.

    Returns
    -------
    Response
        Flask ``Response`` with ``mimetype="text/event-stream"``.
    """
    poll_interval = current_app.config.get(
        "SSE_POLL_INTERVAL", _DEFAULT_POLL_INTERVAL
    )

    def generate() -> Generator[str, None, None]:
        while True:
            events_sent = 0
            while events_sent < _MAX_EVENTS_PER_POLL:
                event = EventBus.poll()
                if event is None:
                    break
                normalized = _to_task_run(event)
                yield f"data: {json.dumps(normalized, ensure_ascii=False)}\n\n"
                events_sent += 1

            if events_sent == 0:
                # Idle heartbeat
                heartbeat = _to_task_run({
                    "type": "idle",
                    "timestamp": time.time(),
                })
                yield f"data: {json.dumps(heartbeat, ensure_ascii=False)}\n\n"

            time.sleep(poll_interval)

    return Response(generate(), mimetype="text/event-stream")


# ---------------------------------------------------------------------------
# GET /api/v1/sse/events
# ---------------------------------------------------------------------------


@bp.route("/sse/events")
def all_events() -> tuple[Response, int]:
    """Return all buffered events as a JSON array (non-streaming).

    Each event is wrapped with ``TaskRun`` fields.
    Useful for debugging or one-shot polling.
    """
    raw_events = EventBus.peek_all()
    normalized = [_to_task_run(e) for e in raw_events]
    return (
        Response(
            json.dumps(normalized, ensure_ascii=False),
            mimetype="application/json",
        ),
        200,
    )


# ---------------------------------------------------------------------------
# DELETE /api/v1/sse/events
# ---------------------------------------------------------------------------


@bp.route("/sse/events", methods=["DELETE"])
def clear_events() -> tuple[Response, int]:
    """Clear all buffered events."""
    EventBus.clear()
    return (
        Response(
            json.dumps({"status": "cleared"}),
            mimetype="application/json",
        ),
        200,
    )


# ---------------------------------------------------------------------------
# Scheduler control endpoints (FR-15)
# ---------------------------------------------------------------------------


@bp.route("/sse/scheduler/status")
def scheduler_status() -> tuple[Response, int]:
    """Return scheduler lifecycle status."""
    from tradingagents.astock.execution.scheduler import get_scheduler

    sched = get_scheduler()
    if sched is None:
        return Response(
            json.dumps({"status": "not_configured"}),
            mimetype="application/json",
        ), 200

    return jsonify({
        "running": sched.running,
        "paused": sched.paused,
        "enabled": sched.enabled,
        "cycle_count": sched.cycle_count,
        "next_run_time": sched.next_run_time,
        "interval_minutes": sched._interval_minutes,
    }), 200


@bp.route("/sse/scheduler/start", methods=["POST"])
def scheduler_start() -> tuple[Response, int]:
    """Start the scheduler."""
    from tradingagents.astock.execution.scheduler import get_scheduler

    sched = get_scheduler()
    if sched is None:
        return jsonify({"error": "scheduler not configured", "status": 500}), 500
    sched.start()
    return jsonify({"status": "started", "running": sched.running}), 200


@bp.route("/sse/scheduler/stop", methods=["POST"])
def scheduler_stop() -> tuple[Response, int]:
    """Stop the scheduler."""
    from tradingagents.astock.execution.scheduler import get_scheduler

    sched = get_scheduler()
    if sched is None:
        return jsonify({"error": "scheduler not configured", "status": 500}), 500
    sched.stop()
    return jsonify({"status": "stopped", "running": sched.running}), 200


@bp.route("/sse/scheduler/pause", methods=["POST"])
def scheduler_pause() -> tuple[Response, int]:
    """Pause the scheduler."""
    from tradingagents.astock.execution.scheduler import get_scheduler

    sched = get_scheduler()
    if sched is None:
        return jsonify({"error": "scheduler not configured", "status": 500}), 500
    sched.pause()
    return jsonify({"status": "paused", "paused": sched.paused}), 200


@bp.route("/sse/scheduler/resume", methods=["POST"])
def scheduler_resume() -> tuple[Response, int]:
    """Resume the scheduler after pause."""
    from tradingagents.astock.execution.scheduler import get_scheduler

    sched = get_scheduler()
    if sched is None:
        return jsonify({"error": "scheduler not configured", "status": 500}), 500
    sched.resume()
    return jsonify({"status": "resumed", "paused": sched.paused}), 200


@bp.route("/sse/scheduler/jobs", methods=["GET"])
def list_scheduler_jobs() -> tuple[Response, int]:
    """List all scheduled jobs."""
    from tradingagents.astock.execution.scheduler import get_scheduler

    sched = get_scheduler()
    if sched is None:
        return jsonify({"error": "scheduler not configured", "status": 500}), 500
    return jsonify({"jobs": sched.list_jobs()}), 200


@bp.route("/sse/scheduler/jobs", methods=["POST"])
def add_scheduler_job() -> tuple[Response, int]:
    """Add a new scheduled job.

    Body (JSON):
        job_id      — unique job ID (required)
        job_type    — "cron" | "interval" (default: "cron")
        trigger_type — "cron" | "interval"
        trigger_args — dict of trigger params (required)
        enabled     — bool (default: true)
    """
    from tradingagents.astock.execution.scheduler import get_scheduler

    sched = get_scheduler()
    if sched is None:
        return jsonify({"error": "scheduler not configured", "status": 500}), 500

    data = request.get_json(silent=True) or {}
    job_id = data.get("job_id", "")
    job_type = data.get("job_type", "cron")
    trigger_type = data.get("trigger_type", "cron")
    trigger_args = data.get("trigger_args", {})
    enabled = data.get("enabled", True)

    if not job_id:
        return jsonify({"error": "job_id is required", "status": 400}), 400

    try:
        if job_type == "interval":
            minutes = trigger_args.get("minutes", 5)
            sched.add_interval_job(job_id=job_id, minutes=minutes, enabled=enabled)
        else:
            hour = trigger_args.get("hour", "*")
            minute = trigger_args.get("minute", "0")
            day_of_week = trigger_args.get("day_of_week", "*")
            sched.add_cron_job(job_id=job_id, hour=hour, minute=minute, day_of_week=day_of_week, enabled=enabled)
        return jsonify({"status": "ok", "job_id": job_id}), 201
    except Exception as exc:
        logger.warning("Failed to add scheduler job: %s", exc)
        return jsonify({"error": str(exc), "status": 500}), 500


@bp.route("/sse/scheduler/jobs/<job_id>", methods=["DELETE"])
def remove_scheduler_job(job_id: str) -> tuple[Response, int]:
    """Remove a scheduled job by ID."""
    from tradingagents.astock.execution.scheduler import get_scheduler

    sched = get_scheduler()
    if sched is None:
        return jsonify({"error": "scheduler not configured", "status": 500}), 500

    removed = sched.remove_job(job_id)
    if not removed:
        return jsonify({"error": f"Job not found: {job_id}", "status": 404}), 404
    return jsonify({"status": "removed", "job_id": job_id}), 200


@bp.route("/sse/scheduler/jobs/<job_id>/toggle", methods=["POST"])
def toggle_scheduler_job(job_id: str) -> tuple[Response, int]:
    """Toggle a job enabled/disabled."""
    from tradingagents.astock.execution.scheduler import get_scheduler

    sched = get_scheduler()
    if sched is None:
        return jsonify({"error": "scheduler not configured", "status": 500}), 500

    data = request.get_json(silent=True) or {}
    enabled = data.get("enabled", True)
    toggled = sched.toggle_job(job_id, enabled)
    if not toggled:
        return jsonify({"error": f"Job not found: {job_id}", "status": 404}), 404
    return jsonify({"status": "ok", "job_id": job_id, "enabled": enabled}), 200
