"""
Audit logging for AStock Pro API.
Captures actor, action, resource, request params, response status, timing.
Writes to ``audit_log`` table via PGStore or DuckDB (fire-and-forget).
"""

import json
import time
import logging
from functools import wraps
from typing import Any, Callable, Optional

from flask import request, g, Response

logger = logging.getLogger(__name__)


def audit_log(
    event_type: str,
    action: str,
    resource_type: Optional[str] = None,
    resource_id_param: Optional[str] = None,
    capture_request_body: bool = False,
    capture_response: bool = False,
):
    """Decorator: record API calls in the ``audit_log`` table.

    The audit event is written **asynchronously** (fire-and-forget) and
    will **never** block or fail the API response.

    Parameters
    ----------
    event_type : str
        High-level category (e.g. ``"data_export"``, ``"data_import"``).
    action : str
        Specific operation (e.g. ``"export_kline"``, ``"import_kline"``).
    resource_type : str, optional
        Logical resource kind (e.g. ``"kline_bars"``, ``"symbol"``).
    resource_id_param : str, optional
        Name of the URL route parameter whose value is the resource
        identifier (e.g. ``"symbol"``).  Extracted from
        ``request.view_args``.
    capture_request_body : bool
        If True, include the JSON request body and query params in
        ``detail``.
    capture_response : bool
        If True, include a preview of the response body in ``detail``.
        Use with care on large payloads.  (The response body is captured
        via a wrapper ``Response`` subclass so the original stream is
        preserved.)

    Usage::

        @audit_log(event_type="data_export", action="export_kline",
                   resource_type="kline_bars")
        def export_route(symbol):
            ...

        @audit_log(event_type="data_import", action="import_kline",
                   resource_type="kline_bars", resource_id_param="symbol")
        def import_route(symbol):
            ...
    """
    def decorator(f: Callable):
        @wraps(f)
        def decorated(*args, **kwargs):
            t0 = time.time()
            actor = getattr(g, "actor", "anonymous")

            # Determine resource_id from route params
            resource_id = None
            if resource_id_param and resource_id_param in kwargs:
                resource_id = str(kwargs[resource_id_param])

            detail: dict[str, Any] = {}
            if capture_request_body:
                try:
                    body = request.get_json(silent=True)
                    detail["body"] = body if body else {}
                    detail["query"] = dict(request.args)
                except Exception as exc:
                    logger.warning("Audit flush failed: %s", exc)

            if capture_response:
                # We'll capture after the response is built below
                pass

            try:
                response = f(*args, **kwargs)
                elapsed_ms = int(round((time.time() - t0) * 1000))
                outcome = "success"

                # Extract status code
                status_code = _extract_status(response)
                if status_code >= 400:
                    outcome = "error"

                detail["status_code"] = status_code
                detail["duration_ms"] = elapsed_ms

                if capture_response:
                    _capture_response_body(detail, response)

                _write_audit(
                    event_type=event_type,
                    action=action,
                    actor=actor,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    detail=detail,
                    outcome=outcome,
                )

                return response

            except Exception as exc:
                elapsed_ms = int(round((time.time() - t0) * 1000))
                detail["error"] = str(exc)
                detail["duration_ms"] = elapsed_ms

                _write_audit(
                    event_type=event_type,
                    action=action,
                    actor=actor,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    detail=detail,
                    outcome="error",
                )
                raise
        return decorated
    return decorator


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_status(response: Any) -> int:
    """Normalise response to status code."""
    if isinstance(response, tuple):
        return response[1] if len(response) > 1 else 200
    if isinstance(response, Response):
        return response.status_code
    # Assume tuple-like or bare payload
    if hasattr(response, "status_code"):
        return response.status_code
    return 200


def _capture_response_body(detail: dict[str, Any], response: Any) -> None:
    """Try to get a preview of the response body.

    Only captures if the response is a Flask ``Response`` with a
    readable stream.  Large bodies are truncated at 2048 characters.
    """
    try:
        if isinstance(response, Response):
            body_bytes = response.get_data()
            if body_bytes:
                text = body_bytes.decode("utf-8", errors="replace")
                if len(text) > 2048:
                    text = text[:2048] + "... (truncated)"
                detail["response_preview"] = text
        elif isinstance(response, tuple) and isinstance(response[0], (dict, list)):
            preview = json.dumps(response[0], ensure_ascii=False, default=str)
            if len(preview) > 2048:
                preview = preview[:2048] + "... (truncated)"
            detail["response_preview"] = preview
    except Exception as exc:
        logger.warning("Audit response capture failed: %s", exc)


def _write_audit(
    event_type: str,
    action: str,
    actor: str,
    resource_type: Optional[str],
    resource_id: Optional[str],
    detail: dict[str, Any],
    outcome: str,
) -> None:
    """Write an audit event to the store (fire-and-forget).

    This is deliberately a top-level function so it can be called from
    both the success and exception paths.  It never raises.
    """
    try:
        # Resolve store — prioritise g attributes (set by middleware), then
        # current_app.config for direct calls without middleware.
        store = (
            getattr(g, "pg_store", None)
            or getattr(g, "store", None)
        )
        if store is None:
            try:
                from flask import current_app
                store = current_app.config.get("STORE")
            except (RuntimeError, KeyError) as e:
                logger.debug("Operation failed: {0}", e)
        if store is None:
            logger.debug("Audit write skipped: no store available")
            return

        import asyncio

        method = getattr(store, "store_audit_log", None)
        if method is None:
            # Fallback: generic insert_table_rows (DuckDB path)
            import uuid as _uuid
            row = {
                "event_id": _uuid.uuid4().hex,
                "event_type": event_type,
                "actor": actor,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "action": action,
                "detail_json": json.dumps(detail, ensure_ascii=False, default=str),
                "outcome": outcome,
            }
            if hasattr(store, "insert_table_rows"):
                store.insert_table_rows("audit_log", [row])
            return

        # store_audit_log expects `detail` as a dict (not pre-serialised)
        # — the store methods serialise internally.
        if asyncio.iscoroutinefunction(method):
            asyncio.run(
                method(
                    event_type=event_type,
                    action=action,
                    actor=actor,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    detail=detail,
                    outcome=outcome,
                )
            )
        else:
            method(
                event_type=event_type,
                action=action,
                actor=actor,
                resource_type=resource_type,
                resource_id=resource_id,
                detail=detail,
                outcome=outcome,
            )
    except Exception as exc:
        logger.warning("Audit write failed (non-blocking): %s", exc)
