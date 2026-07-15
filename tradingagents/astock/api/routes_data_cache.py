"""Cache management API routes.

Routes: /cache/status, /cache/clear
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, Response, current_app, jsonify
from .envelope import error_response

bp = Blueprint("data_cache", __name__)
logger = logging.getLogger(__name__)


def _router() -> Any:
    return current_app.config.get("DATA_FACADE")  # type: ignore[name-defined]


@bp.route("/cache/status")
def cache_status() -> tuple[Response, int]:
    try:
        router = _router()
        if not router:
            return jsonify({"cache": {"enabled": False, "reason": "no router"}}), 200
        if not hasattr(router, 'router'):
            return jsonify({"cache": {"enabled": False, "reason": "router has no inner router"}}), 200
        inner_router = router.router
        if not hasattr(inner_router, 'cache'):
            return jsonify({"cache": {"enabled": False, "reason": "router has no cache"}}), 200
        cache = inner_router.cache
        if cache is None:
            return jsonify({"cache": {"enabled": False}}), 200
        info = {"enabled": True, "type": type(cache).__name__}
        if hasattr(cache, "_snapshots"):
            info["snapshots"] = len(cache._snapshots)
        if hasattr(cache, "_history_ranges"):
            info["history_ranges"] = len(cache._history_ranges)
        if hasattr(cache, "_summaries"):
            info["summaries"] = len(cache._summaries)
        return jsonify({"cache": info}), 200
    except Exception as exc:
        logger.warning("Cache status failed: %s", exc)
        return error_response("cache_status_unavailable", 503, code="cache_status_unavailable")


@bp.route("/cache/clear", methods=["POST"])
def cache_clear() -> tuple[Response, int]:
    try:
        router = _router()
        if not router:
            return jsonify({"status": "ok", "cleared": False, "reason": "no router"}), 200
        if not hasattr(router, 'router'):
            return jsonify({"status": "ok", "cleared": False, "reason": "router has no inner router"}), 200
        inner_router = router.router
        if not hasattr(inner_router, 'cache'):
            return jsonify({"status": "ok", "cleared": False, "reason": "router has no cache"}), 200
        cache = inner_router.cache
        if cache and hasattr(cache, "clear"):
            cache.clear()
            return jsonify({"status": "ok", "cleared": True}), 200
        return jsonify({"status": "ok", "cleared": False, "reason": "cache has no clear()"}), 200
    except Exception as exc:
        logger.warning("Cache clear failed: %s", exc)
        return error_response("cache_clear_failed", 500, code="cache_clear_failed")
