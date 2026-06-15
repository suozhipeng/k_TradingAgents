"""SSE (Server-Sent Events) routes for real-time streaming.

Provides a Flask blueprint with an SSE endpoint that polls the
:class:`EventBus` and streams events to connected clients.
"""

from __future__ import annotations

import json
import time
from typing import Any, Generator

from flask import Blueprint, Response, current_app

from tradingagents.astock.execution.event_bus import EventBus

bp = Blueprint("sse", __name__)

# Default SSE poll interval (seconds)
_DEFAULT_POLL_INTERVAL: float = 1.0
# Maximum events to send per poll
_MAX_EVENTS_PER_POLL: int = 10


# ---------------------------------------------------------------------------
# GET /api/v1/sse/paper-progress
# ---------------------------------------------------------------------------


@bp.route("/sse/paper-progress")
def paper_progress_sse() -> Response:
    """SSE streaming endpoint for paper trading progress.

    Yields ``text/event-stream`` data lines.  Each event is a JSON object
    with at least a ``type`` field.  When no events are available, an idle
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
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                events_sent += 1

            if events_sent == 0:
                # Idle heartbeat
                heartbeat = json.dumps({"type": "idle", "timestamp": time.time()})
                yield f"data: {heartbeat}\n\n"

            time.sleep(poll_interval)

    return Response(generate(), mimetype="text/event-stream")


# ---------------------------------------------------------------------------
# GET /api/v1/sse/events
# ---------------------------------------------------------------------------


@bp.route("/sse/events")
def all_events() -> tuple[Response, int]:
    """Return all buffered events as a JSON array (non-streaming).

    Useful for debugging or one-shot polling.
    """
    events = EventBus.peek_all()
    return (
        Response(
            json.dumps(events, ensure_ascii=False),
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
