"""Flask request/response hooks for the A-stock API.

Registers ``before_request`` and ``after_request`` handlers plus error
handlers.  These are applied inside ``create_app()`` after the store and
blueprints are configured.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
import uuid
from typing import Any

from flask import Flask, Response, g, jsonify, request
from .idempotency import IdempotencyRegistry
from .rate_limit import FixedWindowRateLimiter

logger = logging.getLogger(__name__)

_WRITE_METHODS = frozenset(("POST", "PUT", "DELETE", "PATCH"))
_WRITE_ROLES = frozenset(("admin", "operator", "writer"))
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
_IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_EXECUTION_PREFIXES = frozenset((
    "/api/v1/trade/", "/api/v1/paper/", "/api/v1/qmt/", "/api/v1/portfolio/",
))
_LOCAL_RELEASE_DISABLED_PREFIXES = _EXECUTION_PREFIXES | frozenset((
    "/api/v1/scheduler/", "/api/v1/ops/scheduler/", "/api/v1/sse/paper-progress",
))


def register_hooks(app: Flask) -> None:
    """Attach before_request / after_request / errorhandler callbacks."""

    app.extensions["astock_idempotency"] = IdempotencyRegistry(
        app.config.get("ASTOCK_IDEMPOTENCY_TTL_SECONDS", 300),
        app.config.get("ASTOCK_IDEMPOTENCY_MAX_ENTRIES", 1000),
    )
    app.extensions["astock_rate_limiter"] = FixedWindowRateLimiter(
        app.config.get("ASTOCK_RATE_LIMIT_PER_MINUTE", 300), 60,
        app.config.get("ASTOCK_RATE_LIMIT_MAX_KEYS", 10000),
    )
    _register_before_request(app)
    _register_after_request(app)
    _register_error_handlers(app)


# ---------------------------------------------------------------------------
# before_request
# ---------------------------------------------------------------------------

def _register_before_request(app: Flask) -> None:
    @app.before_request
    def _start_request_timer() -> None:
        g.request_started_at = time.perf_counter()
        supplied = request.headers.get("X-Request-ID", "").strip()
        g.request_id = supplied if _REQUEST_ID_RE.fullmatch(supplied) else uuid.uuid4().hex

    @app.before_request
    def _block_execution_in_research_only() -> tuple[Any, int] | None:
        """Return 410 if RESEARCH_ONLY and path matches an execution prefix."""
        if app.config.get("ASTOCK_LOCAL_RELEASE", False):
            if any(request.path.startswith(p) for p in _LOCAL_RELEASE_DISABLED_PREFIXES):
                return jsonify({
                    "error": "local_release_disabled",
                    "message": "This endpoint is unavailable in the local analysis and backtest release.",
                    "status": 410,
                }), 410
        if not app.config.get("ASTOCK_RESEARCH_ONLY", True):
            return None
        if not any(request.path.startswith(p) for p in _EXECUTION_PREFIXES):
            return None
        return jsonify({
            "error": "research_only",
            "message": "This endpoint is disabled in research-only mode. "
                       "Set ASTOCK_RESEARCH_ONLY=false to re-enable.",
            "status": 410,
        }), 410

    @app.before_request
    def _inject_globals() -> None:
        g.store = app.config.get("STORE")
        g.pg_store = app.config.get("PG_STORE")
        g.backend_mgr = app.config.get("BACKEND_MGR")
        g.actor = "anonymous"
        g.role = "public"
        g.key_id = ""
        g.allowed_capabilities = ""
        g.rate_limit = int(app.config.get("ASTOCK_RATE_LIMIT_PER_MINUTE", 300))

    @app.before_request
    def _require_auth_on_write_routes() -> tuple[Any, int] | None:
        if not app.config.get("ASTOCK_REQUIRE_AUTH", True):
            return None
        if request.method not in _WRITE_METHODS:
            return None
        if any(request.path.startswith(p) for p in ("/api/v1/health",)):
            return None

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "missing_auth",
                            "message": "Bearer token required for write operations"}), 401

        key_hash = hashlib.sha256(auth[7:].encode()).hexdigest()
        store = app.config.get("PG_STORE") or app.config.get("STORE")

        record = None
        if store and hasattr(store, "validate_api_key"):
            try:
                if asyncio.iscoroutinefunction(store.validate_api_key):
                    # Run async validation in a new event loop to avoid
                    # asyncio.run() creating a new policy that may conflict
                    # with the current process.  We create/close the loop
                    # manually so it doesn't block the request thread.
                    loop = asyncio.new_event_loop()
                    try:
                        record = loop.run_until_complete(store.validate_api_key(key_hash))
                    finally:
                        loop.close()
                else:
                    record = store.validate_api_key(key_hash)
            except Exception as exc:
                logger.warning("API key validation failed: %s", exc)
                record = None

        if record is None:
            return jsonify({"error": "invalid_key",
                            "message": "Invalid or expired API key"}), 401

        g.actor = record.get("key_id", "unknown")
        g.role = record.get("role", "readonly")
        g.key_id = record.get("key_id", "")
        g.allowed_capabilities = record.get("allowed_capabilities", "")
        try:
            g.rate_limit = max(1, int(record.get("rate_limit", g.rate_limit)))
        except (TypeError, ValueError):
            pass
        if request.method in _WRITE_METHODS and g.role not in _WRITE_ROLES:
            return jsonify({
                "error": "forbidden",
                "message": "A writer, operator, or admin API key is required for write operations",
            }), 403
        return None

    @app.before_request
    def _claim_idempotency_key() -> Response | tuple[Any, int] | None:
        if request.method not in _WRITE_METHODS:
            return None
        supplied = request.headers.get("Idempotency-Key", "").strip()
        if not supplied:
            return None
        if not _IDEMPOTENCY_KEY_RE.fullmatch(supplied):
            return jsonify({"error": "invalid_idempotency_key", "status": 400}), 400
        body = request.get_data(cache=True) or b""
        fingerprint = hashlib.sha256(
            b"\0".join((request.method.encode(), request.path.encode(), body))
        ).hexdigest()
        registry: IdempotencyRegistry = app.extensions["astock_idempotency"]
        registry_key = f"{getattr(g, 'actor', 'anonymous')}:{supplied}"
        state, replay = registry.claim(registry_key, fingerprint)
        if state == "replay" and replay:
            status, cached_body, content_type = replay
            response = Response(cached_body, status=status, content_type=content_type)
            response.headers["Idempotency-Replayed"] = "true"
            return response
        if state == "conflict":
            return jsonify({"error": "idempotency_key_reused_with_different_request", "status": 409}), 409
        if state == "pending":
            return jsonify({"error": "idempotency_request_in_progress", "status": 409}), 409
        g.idempotency_registry_key = registry_key
        return None

    @app.before_request
    def _limit_request_rate() -> tuple[Any, int] | None:
        if request.path.startswith("/api/v1/health"):
            return None
        actor = getattr(g, "actor", "anonymous")
        identity = actor if actor != "anonymous" else (request.remote_addr or "unknown")
        allowed, retry_after = app.extensions["astock_rate_limiter"].allow(
            identity, getattr(g, "rate_limit", None)
        )
        if allowed:
            return None
        response = jsonify({"error": "rate_limited", "status": 429, "retry_after_seconds": retry_after})
        response.headers["Retry-After"] = str(retry_after)
        return response, 429


# ---------------------------------------------------------------------------
# after_request
# ---------------------------------------------------------------------------

def _register_after_request(app: Flask) -> None:
    @app.after_request
    def _security_and_idempotency(response: Any) -> Any:
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
            "img-src 'self' data:; style-src 'self' 'unsafe-inline'; connect-src 'self'",
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("X-Frame-Options", "DENY")
        key = getattr(g, "idempotency_registry_key", None)
        if key:
            registry: IdempotencyRegistry = app.extensions["astock_idempotency"]
            # Only successful operations are replay-safe.  In particular a
            # transient 429 must not reserve an idempotency key after the
            # rate-limit window has elapsed.
            if 200 <= response.status_code < 400 and not response.is_streamed:
                registry.complete(key, response.status_code, response.get_data(), response.content_type)
                response.headers["Idempotency-Replayed"] = "false"
            else:
                registry.abandon(key)
        return response

    @app.after_request
    def _record_request_timing(response: Any) -> Any:
        started = getattr(g, "request_started_at", None)
        if started is None:
            return response
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        from .metrics import record_request
        route = getattr(getattr(request, "url_rule", None), "rule", request.path)
        record_request(request.method, route, response.status_code, elapsed_ms)
        if elapsed_ms >= float(app.config.get("ASTOCK_SLOW_REQUEST_MS", 1000)):
            logger.warning(
                "Slow API request %.1fms request_id=%s: %s %s -> %s",
                elapsed_ms, getattr(g, "request_id", ""), request.method, request.path, response.status_code,
            )
        else:
            logger.debug(
                "API request %.1fms request_id=%s: %s %s -> %s",
                elapsed_ms, getattr(g, "request_id", ""), request.method, request.path, response.status_code,
            )
        return response

    @app.after_request
    def _audit_write_operations(response: Any) -> Any:
        """Non-blocking audit for all POST/PUT/DELETE/PATCH operations."""
        if response.status_code >= 500 and response.status_code != 501:
            logger.error("API request failed: %s %s -> %s", request.method, request.path, response.status_code)
            error_response = jsonify({"error": "internal_server_error", "status": response.status_code})
            error_response.status_code = response.status_code
            return error_response
        if request.method not in ("POST", "PUT", "DELETE", "PATCH"):
            return response
        if request.path.startswith("/api/v1/health"):
            return response

        store = app.config.get("STORE")
        if store is None:
            return response

        try:
            actor = getattr(g, "actor", "anonymous")
            status_code = response.status_code if hasattr(response, "status_code") else 200

            detail = {
                "path": request.path,
                "method": request.method,
                "status": status_code,
                "query": dict(request.args),
            }
            try:
                body = request.get_json(silent=True)
                if body:
                    detail["body_keys"] = list(body.keys())[:20]
            except Exception as e:
                logger.debug("Operation failed: {0}", e)

            segs = request.path.strip("/").split("/")
            resource_type = segs[2] if len(segs) > 2 else "api"

            audit_data = {
                "actor": actor,
                "resource_type": resource_type,
                "resource_id": segs[-1] if segs else "",
                "detail": detail,
                "outcome": "success" if status_code < 400 else "error",
            }

            insert_fn = getattr(store, "store_audit_log", None)
            if insert_fn is not None:
                if asyncio.iscoroutinefunction(insert_fn):
                    try:
                        asyncio.run(insert_fn("api_write", f"{request.method} {request.path}", **audit_data))
                    except RuntimeError as e:
                        logger.debug("Operation failed: {0}", e)
                else:
                    insert_fn("api_write", f"{request.method} {request.path}", **audit_data)
        except Exception as exc:
            logger.warning("Audit write failed: %s", exc)
        return response


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(400)
    def bad_request(_e: Any) -> tuple[Any, int]:
        return jsonify({"error": "Bad request", "status": 400}), 400

    @app.errorhandler(401)
    def unauthorized(_e: Any) -> tuple[Any, int]:
        return jsonify({"error": "Unauthorized", "status": 401}), 401

    @app.errorhandler(403)
    def forbidden(_e: Any) -> tuple[Any, int]:
        return jsonify({"error": "Forbidden", "status": 403}), 403

    @app.errorhandler(404)
    def not_found(_e: Any) -> tuple[Any, int]:
        return jsonify({"error": "Not found", "status": 404}), 404

    @app.errorhandler(429)
    def rate_limited(_e: Any) -> tuple[Any, int]:
        return jsonify({"error": "Rate limited", "status": 429}), 429

    @app.errorhandler(500)
    def server_error(_e: Any) -> tuple[Any, int]:
        return jsonify({"error": "Internal server error", "status": 500}), 500
