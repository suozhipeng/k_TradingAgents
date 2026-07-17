"""Flask request/response hooks for the A-stock API.

Registers ``before_request`` and ``after_request`` handlers plus error
handlers.  These are applied inside ``create_app()`` after the store and
blueprints are configured.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
import uuid
from typing import Any

from flask import Flask, Response, g, jsonify, request
from .envelope import stable_error_code
from .idempotency import IdempotencyRegistry
from .key_resolver import build_rate_limiter, resolve_api_key

logger = logging.getLogger(__name__)

_WRITE_METHODS = frozenset(("POST", "PUT", "DELETE", "PATCH"))
_WRITE_ROLES = frozenset(("admin", "operator", "writer"))
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
_IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_EXECUTION_PREFIXES = frozenset((
    "/api/v1/trade/", "/api/v1/paper/", "/api/v1/qmt/", "/api/v1/portfolio/",
    "/api/v1/sse/scheduler/",
))
_LOCAL_RELEASE_DISABLED_PREFIXES = _EXECUTION_PREFIXES | frozenset((
    "/api/v1/scheduler/", "/api/v1/ops/scheduler/", "/api/v1/sse/paper-progress",
))
_LOCAL_RELEASE_ALLOWED_PREFIXES = (
    "/api/v1/health", "/api/v1/dashboard/", "/api/v1/data/health",
    "/api/v1/data/refresh/", "/api/v1/data/jobs", "/api/v1/market/",
    "/api/v1/watchlist", "/api/v1/reports", "/api/v1/backtest/",
    "/api/v1/tv/", "/api/v1/screener", "/api/v1/analysis/",
    "/api/v1/daily/", "/api/v1/strategies/", "/api/v1/alerts",
    "/api/v1/kline", "/api/v1/valuation", "/api/v1/orderbook",
    "/api/v1/news", "/api/v1/research", "/api/v1/fundamentals", "/api/v1/f10",
    # The local AI Research Center is a supported loopback-only workflow.
    "/api/v1/ai/analyze",
)


def _is_local_release_api_allowed(path: str) -> bool:
    """Keep the no-auth local workbench on a deliberate, narrow API surface."""
    if path == "/api/v1/data/jobs/import-database":
        return False
    return any(path.startswith(prefix) for prefix in _LOCAL_RELEASE_ALLOWED_PREFIXES)


def _is_canonical_api_envelope(payload: Any) -> bool:
    """Return whether *payload* already conforms to the current API schema."""
    if not isinstance(payload, dict) or not isinstance(payload.get("ok"), bool):
        return False
    if payload["ok"]:
        return set(payload) == {"ok", "data"}
    return (
        {"ok", "error", "message", "status"}.issubset(payload)
        and set(payload).issubset({"ok", "error", "message", "status", "details"})
    )


def _normalise_api_json_response(response: Any) -> Any:
    """Apply the v1 JSON envelope to every non-streaming JSON API response.

    Route modules historically returned a mix of ``jsonify(payload)``, shared
    helpers, and JSON arrays.  Centralising the migration keeps every API
    response coherent without changing each route's business logic.  The
    contract is deliberately non-compatible: successful payloads exist only
    under ``data``. Streaming SSE, downloads, redirects and no-content
    responses deliberately bypass it.
    """
    if (
        not request.path.startswith("/api/v1/")
        or response.is_streamed
        or response.status_code in (204, 304)
        or not response.is_json
    ):
        return response
    payload = response.get_json(silent=True)
    if _is_canonical_api_envelope(payload):
        return response

    if 200 <= response.status_code < 400:
        body: dict[str, Any] = {"ok": True, "data": payload}
    else:
        raw_details = payload if isinstance(payload, dict) else {"value": payload}
        message = str(raw_details.get("message") or raw_details.get("error") or "request_failed")
        body = {
            "ok": False,
            "error": stable_error_code(str(raw_details.get("error") or message), response.status_code),
            "message": message,
            "status": response.status_code,
        }
        details = {
            key: value for key, value in raw_details.items()
            if key not in {"ok", "error", "message", "status"}
        }
        if details:
            body["details"] = details

    response.set_data(json.dumps(body, ensure_ascii=False, default=str, separators=(",", ":")))
    response.mimetype = "application/json"
    return response


def register_hooks(app: Flask) -> None:
    """Attach before_request / after_request / errorhandler callbacks."""

    app.extensions["astock_idempotency"] = IdempotencyRegistry(
        app.config.get("ASTOCK_IDEMPOTENCY_TTL_SECONDS", 300),
        app.config.get("ASTOCK_IDEMPOTENCY_MAX_ENTRIES", 1000),
    )
    # One limiter protects every route.  It is Redis-backed when configured,
    # avoiding the previous split where only decorator-protected routes shared
    # rate-limit state across workers.
    app.extensions["astock_rate_limiter"] = build_rate_limiter()
    from .lifecycle import request_gate
    request_gate(app)
    _register_before_request(app)
    _register_request_teardown(app)
    _register_after_request(app)
    _register_error_handlers(app)


# ---------------------------------------------------------------------------
# before_request
# ---------------------------------------------------------------------------

def _register_before_request(app: Flask) -> None:
    @app.before_request
    def _admit_request() -> tuple[Any, int] | None:
        from .lifecycle import request_gate

        if request_gate(app).enter():
            g.astock_request_admitted = True
            return None
        return jsonify({
            "error": "application_shutting_down",
            "message": "The application is shutting down",
            "status": 503,
        }), 503

    @app.before_request
    def _start_request_timer() -> None:
        g.request_started_at = time.perf_counter()
        supplied = request.headers.get("X-Request-ID", "").strip()
        g.request_id = supplied if _REQUEST_ID_RE.fullmatch(supplied) else uuid.uuid4().hex

    @app.before_request
    def _block_execution_in_research_only() -> tuple[Any, int] | None:
        """Return 410 if RESEARCH_ONLY and path matches an execution prefix."""
        if app.config.get("ASTOCK_LOCAL_RELEASE", False):
            if request.path.startswith("/api/v1/") and (
                any(request.path.startswith(p) for p in _LOCAL_RELEASE_DISABLED_PREFIXES)
                or not _is_local_release_api_allowed(request.path)
            ):
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
    def _authenticate_request() -> tuple[Any, int] | None:
        """Resolve a supplied bearer key before global rate limiting.

        This gives every request the same key identity for shared limiting.
        Write requests still require a valid writer-capable key; anonymous
        reads remain supported where routes allow them.
        """
        auth = request.headers.get("Authorization", "")
        is_write = request.method in _WRITE_METHODS and not request.path.startswith("/api/v1/health")
        if not auth.startswith("Bearer "):
            if not app.config.get("ASTOCK_REQUIRE_AUTH", True) or not is_write:
                return None
            return jsonify({"error": "missing_auth",
                            "message": "Bearer token required for write operations"}), 401

        key_hash = hashlib.sha256(auth[7:].encode()).hexdigest()
        store = app.config.get("PG_STORE") or app.config.get("STORE")

        record = resolve_api_key(store, key_hash)

        if record is None:
            if not app.config.get("ASTOCK_REQUIRE_AUTH", True) and not is_write:
                return None
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
        if app.config.get("ASTOCK_REQUIRE_AUTH", True) and is_write and g.role not in _WRITE_ROLES:
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
        limiter = app.extensions["astock_rate_limiter"]
        if hasattr(limiter, "allow"):
            allowed, retry_after = limiter.allow(identity, getattr(g, "rate_limit", None))
        else:
            allowed, _remaining = limiter.consume(identity, getattr(g, "rate_limit", None))
            retry_after = 60
        if allowed:
            return None
        response = jsonify({"error": "rate_limited", "status": 429, "retry_after_seconds": retry_after})
        response.headers["Retry-After"] = str(retry_after)
        return response, 429


def _register_request_teardown(app: Flask) -> None:
    @app.teardown_request
    def _release_request(_error: BaseException | None) -> None:
        if not getattr(g, "astock_request_admitted", False):
            return
        from .lifecycle import request_gate

        request_gate(app).leave()
        g.astock_request_admitted = False


# ---------------------------------------------------------------------------
# after_request
# ---------------------------------------------------------------------------

def _register_after_request(app: Flask) -> None:
    @app.after_request
    def _security_and_idempotency(response: Any) -> Any:
        # The local workbench still contains legacy inline handlers and a
        # small number of chart CDN imports.  Keep that compatibility scoped
        # to loopback local release; non-local API processes retain the strict
        # policy.  The follow-up migration can remove this exception once all
        # templates use external modules and event listeners.
        if app.config.get("ASTOCK_LOCAL_RELEASE", False):
            csp = (
                "default-src 'self'; base-uri 'self'; object-src 'none'; "
                "frame-ancestors 'none'; img-src 'self' data:; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com "
                "https://cdn.jsdelivr.net; connect-src 'self'"
            )
        else:
            csp = (
                "default-src 'self'; base-uri 'self'; object-src 'none'; "
                "frame-ancestors 'none'; img-src 'self' data:; "
                "style-src 'self' 'unsafe-inline'; connect-src 'self'"
            )
        response.headers.setdefault(
            "Content-Security-Policy",
            csp,
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response = _normalise_api_json_response(response)
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
            payload = response.get_json(silent=True) if response.is_json else None
            if _is_canonical_api_envelope(payload):
                return response
            logger.error("API request failed: %s %s -> %s", request.method, request.path, response.status_code)
            # Keep the global safety boundary while using the same error
            # schema as route-level handlers.  Do not reflect route exception
            # messages in an untrusted 5xx response.
            from .envelope import error_response
            error_body, status_code = error_response(
                "internal_server_error", response.status_code
            )
            error_body.status_code = status_code
            return error_body
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
