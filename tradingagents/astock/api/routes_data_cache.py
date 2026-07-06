"""Cache management API routes.

Routes: /cache/status, /cache/clear
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, Response, jsonify

bp = Blueprint("data_cache", __name__)
logger = logging.getLogger(__name__)


def _router() -> Any:
    return current_app.config.get("DATA_FACADE")  # type: ignore[name-defined]


@bp.route("/cache/status")
def cache_status() -> tuple[Response, int]:
    try:
        router = _router()
        if not router or not hasattr(router, 'router'):
            return jsonify({"cache": {"enabled": False}}), 200
        cache = router.router.cache if hasattr(router, 'router') else None
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
        return jsonify({"error": str(exc), "status": 500}), 500


@bp.route("/cache/clear", methods=["POST"])
def cache_clear() -> tuple[Response, int]:
    try:
        router = _router()
        if not router:
            return jsonify({"status": "ok", "cleared": False, "reason": "no router"}), 200
        cache = router.router.cache if hasattr(router, 'router') else None
        if cache and hasattr(cache, "clear"):
            cache.clear()
            return jsonify({"status": "ok", "cleared": True}), 200
        return jsonify({"status": "ok", "cleared": False, "reason": "cache has no clear()"}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500
