"""Standardised API response envelope.

Every JSON API endpoint returns one of:

    {"ok": true,  "data": <payload>}  # success
    {"ok": false, "error": <code>, "message": <human text>, "status": <code>}  # failure

This avoids scattered patterns like ``{"error": "...", "status": 400}`` vs
``{"error": "forbidden", "message": "..."}`` and makes client-side parsing
predictable.

Usage::

    from .envelope import error_response, success_response

    @bp.route("/example")
    def example():
        if bad_thing:
            return error_response("missing field", 400)
        return success_response({"key": "value"})
"""

from __future__ import annotations

import re
import logging
from typing import Any

from flask import jsonify

logger = logging.getLogger(__name__)

_STABLE_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_]*$")
_STATUS_ERROR_CODES = {
    400: "invalid_request", 401: "unauthorized", 403: "forbidden",
    404: "not_found", 405: "method_not_allowed", 409: "conflict",
    413: "payload_too_large", 422: "unprocessable_entity", 429: "rate_limited",
}


def stable_error_code(message: str, status: int) -> str:
    """Return a public machine code without deriving it from dynamic text."""
    if status >= 500:
        return "internal_server_error"
    return message if _STABLE_ERROR_CODE.fullmatch(message) else _STATUS_ERROR_CODES.get(status, "request_failed")


def success_response(data: Any, *, status: int = 200) -> tuple:
    """Return the standardised success envelope.

    Parameters
    ----------
    data:
        Serialisable payload (dict, list, str, etc.).
    status:
        HTTP status code (default 200).

    Returns
    -------
    tuple[Response, int]
        ``(jsonify(...), status)`` ready for a Flask route handler.
    """
    return jsonify({"ok": True, "data": data}), status


def error_response(
    message: str,
    status: int = 500,
    *,
    detail: str | None = None,
    code: str | None = None,
) -> tuple:
    """Return a standardised error envelope.

    Parameters
    ----------
    message:
        Human-readable error summary.
    status:
        HTTP status code (default 500).
    detail:
        Optional machine-readable / debug detail.
    code:
        Stable public error code. Required to expose a distinct 5xx error;
        otherwise 5xx responses are deliberately sanitised.

    Returns
    -------
    tuple[Response, int]
        ``(jsonify(...), status)`` ready for a Flask route handler.
    """
    if code is None:
        if status >= 500:
            logger.error("API error response: status=%s code=%s detail=%s", status, code or "internal_server_error", message)
            code = stable_error_code(message, status)
            message = "internal_server_error"
            detail = None
        else:
            code = stable_error_code(message, status)
    body: dict[str, Any] = {
        "ok": False,
        "error": code or message,
        "message": message,
        "status": status,
    }
    if detail is not None:
        body["details"] = {"detail": detail}
    return jsonify(body), status


def created_response(data: Any) -> tuple:
    """Shorthand for a 201-created success response."""
    return success_response(data, status=201)


def deleted_response() -> tuple:
    """Shorthand for a 200-deleted success response."""
    return success_response({"deleted": True}, status=200)
