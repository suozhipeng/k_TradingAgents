"""Standardised API response envelope.

Every JSON API endpoint should return one of:

    {"ok": true,  "data": <payload>, ...legacy payload fields}  # success
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

from typing import Any

from flask import jsonify


def success_response(data: Any, *, status: int = 200) -> tuple:
    """Return a transitional standardised success envelope.

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
    # API v1 clients read result fields directly (for example
    # ``total_return`` and ``results``). Keep those fields during the
    # migration while exposing the canonical ``data`` object for new clients.
    body: dict[str, Any] = {"ok": True, "data": data}
    if isinstance(data, dict):
        body.update({key: value for key, value in data.items() if key not in body})
    return jsonify(body), status


def error_response(
    message: str,
    status: int = 500,
    *,
    detail: str | None = None,
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

    Returns
    -------
    tuple[Response, int]
        ``(jsonify(...), status)`` ready for a Flask route handler.
    """
    body: dict[str, Any] = {
        "ok": False,
        "error": message,
        # Retain the legacy field while routes migrate to the shared helper.
        "message": detail or message,
        "status": status,
    }
    if detail is not None:
        body["detail"] = detail
    return jsonify(body), status


def created_response(data: Any) -> tuple:
    """Shorthand for a 201-created success response."""
    return success_response(data, status=201)


def deleted_response() -> tuple:
    """Shorthand for a 200-deleted success response."""
    return success_response({"deleted": True}, status=200)
