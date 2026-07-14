"""SSE (Server-Sent Events) routes for real-time streaming.

Provides a Flask blueprint with an SSE endpoint that polls the
:class:`EventBus` and streams events to connected clients.

Events are wrapped with ``TaskRun``-shaped fields for standardization
(see ``tradingagents.astock.schemas.ops_audit.TaskRun``).

Scheduler CRUD has been moved to ``routes_scheduler.py``.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Generator

from flask import Blueprint, Response, current_app, jsonify

from tradingagents.astock.execution.infrastructure.event_bus import EventBus
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
    """Wrap a raw EventBus event dict with ``TaskRun``-shaped fields."""
    import datetime as _dt
    now = _dt.datetime.now(tz=_dt.timezone.utc).isoformat()
    event_type = event.get("type", "unknown")
    task_type = _TASK_TYPE_MAP.get(event_type, TaskType.DATA_REFRESH)
    task_id: str = event.get("task_id") or f"sse-{uuid.uuid4().hex[:8]}"

    status_map: dict[str, str] = {
        "cycle_start": "running",
        "cycle_complete": "success",
        "cycle_error": "failed",
        "error": "failed",
        "trade": "success",
        "idle": "idle",
    }
    status = status_map.get(event_type, "running")

    ts = event.get("timestamp", now)
    finished_at: str | None
    if status in ("success", "failed"):
        finished_at = ts
    else:
        finished_at = None

    error: dict[str, Any] | None = None
    if status == "failed" and "message" in event:
        error = {"message": event["message"], "timestamp": ts}

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

    result = dict(event)
    result.update(task_run_fields)
    return result


# ---------------------------------------------------------------------------
# GET /api/v1/sse/paper-progress
# ---------------------------------------------------------------------------


@bp.route("/sse/paper-progress")
def paper_progress_sse() -> Response:
    """SSE streaming endpoint for paper trading progress."""
    poll_interval = current_app.config.get(
        "SSE_POLL_INTERVAL", _DEFAULT_POLL_INTERVAL
    )
    subscriber_id = EventBus.subscribe()

    def generate() -> Generator[str, None, None]:
        try:
            while True:
                events_sent = 0
                while events_sent < _MAX_EVENTS_PER_POLL:
                    event = EventBus.poll_subscriber(subscriber_id)
                    if event is None:
                        break
                    normalized = _to_task_run(event)
                    yield f"data: {json.dumps(normalized, ensure_ascii=False)}\n\n"
                    events_sent += 1

                if events_sent == 0:
                    heartbeat = _to_task_run({
                        "type": "idle",
                        "timestamp": time.time(),
                    })
                    yield f"data: {json.dumps(heartbeat, ensure_ascii=False)}\n\n"

                time.sleep(poll_interval)
        finally:
            EventBus.unsubscribe(subscriber_id)

    return Response(generate(), mimetype="text/event-stream")


# ---------------------------------------------------------------------------
# GET /api/v1/sse/events
# ---------------------------------------------------------------------------


@bp.route("/sse/events")
def all_events() -> tuple[Response, int]:
    """Return all buffered events as a JSON array (non-streaming)."""
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
