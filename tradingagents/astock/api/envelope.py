"""V1.7 unified API response envelope.

Usage::

    from .envelope import ok, fail

    @bp.route("/example")
    def example():
        if bad_thing:
            return fail("missing field", status=400)
        return ok({"key": "value"})
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

# V1.7 error codes
ERROR_CODES = {
    400: "INVALID_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "UNPROCESSABLE_ENTITY",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    503: "PROVIDER_UNAVAILABLE",
    504: "PROVIDER_TIMEOUT",
}

NON_RETRYABLE = frozenset({
    "INVALID_REQUEST", "UNAUTHORIZED", "FORBIDDEN", "NOT_FOUND", "CONFLICT",
})


def _request_id() -> str:
    ts = int(time.time() * 1000000)
    rand = os.urandom(4).hex()
    return f"req_{ts:x}{rand}"


def _ts() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def ok(data: Any, *, status: int = 200, data_state: str = "available",
       schema_version: str = "1.0") -> tuple:
    """Return a V1.7 unified success response dict + status."""
    return ({
        "ok": True,
        "data": data,
        "meta": {
            "request_id": _request_id(),
            "timestamp": _ts(),
            "data_state": data_state,
            "schema_version": schema_version,
        },
        "error": None,
    }, status)


def fail(message: str, status: int = 500, *,
         code: str | None = None,
         details: dict[str, Any] | None = None,
         retryable: bool | None = None) -> tuple:
    """Return a V1.7 unified error response dict + status."""
    if code is None:
        code = ERROR_CODES.get(status, "INTERNAL_ERROR")
    if retryable is None:
        retryable = code not in NON_RETRYABLE
    if status >= 500 and code == "INTERNAL_ERROR":
        logger.error("API error: status=%s code=%s msg=%s", status, code, message)
    return ({
        "ok": False,
        "data": None,
        "meta": {"request_id": _request_id(), "timestamp": _ts()},
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "retryable": retryable,
        },
    }, status)


def created(data: Any, **kw: Any) -> tuple:
    return ok(data, status=201, **kw)


# Legacy aliases — old code uses success_response/error_response
def success_response(data: Any, *, status: int = 200) -> tuple:
    return ok(data, status=status)


def error_response(message: str, status: int = 500, *,
                   detail: str | None = None,
                   code: str | None = None) -> tuple:
    details = {"detail": detail} if detail else None
    return fail(message, status=status, code=code, details=details)


# ── Contract test helpers (no Flask app context needed) ──────────────────────


def assert_success(payload: dict, expected_status: int = 200) -> dict:
    assert payload.get("ok") is True, f"ok should be True: {payload}"
    assert "data" in payload, "missing data"
    assert payload.get("error") is None, f"error should be None: {payload}"
    meta = payload.get("meta", {})
    rid = meta.get("request_id", "")
    assert rid.startswith("req_"), f"bad request_id: {rid}"
    assert "timestamp" in meta
    assert meta.get("schema_version") == "1.0", f"bad schema_version: {meta}"
    return payload


def assert_error(payload: dict, expected_code: str | None = None) -> dict:
    assert payload.get("ok") is False, f"ok should be False: {payload}"
    assert payload.get("data") is None
    err = payload.get("error", {})
    if expected_code:
        assert err.get("code") == expected_code, f"expected {expected_code} got {err.get('code')}"
    assert "message" in err
    assert "retryable" in err
    return payload
