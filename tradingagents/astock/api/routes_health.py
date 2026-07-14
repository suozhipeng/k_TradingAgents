"""Lightweight health-check endpoint — GET /api/v1/health."""

from __future__ import annotations

import logging
import time
from typing import Any

from flask import Blueprint, Response, current_app, jsonify

bp = Blueprint("health", __name__)
logger = logging.getLogger(__name__)


@bp.route("/health/live")
def liveness_check() -> tuple[Response, int]:
    """Return process liveness without touching external dependencies."""
    uptime = round(time.time() - current_app.config.get("_START_TIME", time.time()), 1)
    return jsonify({"status": "ok", "uptime_seconds": uptime, "version": "0.3.0"}), 200


def _readiness_payload() -> tuple[dict[str, Any], int]:
    """Probe the active and canonical K-line stores for readiness."""
    try:
        store = current_app.config.get("STORE")
        store_connected = store is not None
        if store_connected:
            if hasattr(store, "query_sql"):
                store.query_sql("SELECT 1 AS ready")
            else:
                raise RuntimeError("active store has no query probe")
        # Try to infer backend from the store's inner store attribute
        inner = getattr(store, "inner_store", store)
        backend = getattr(inner, "backend_name", "duckdb") if store_connected else "unknown"
    except Exception as exc:
        logger.warning("health check store probe failed: %s", exc)
        store_connected = False
        backend = "unknown"

    uptime = round(time.time() - current_app.config.get("_START_TIME", time.time()), 1)

    permanent_ready = True
    if store_connected and current_app.config.get("ASTOCK_PERMANENT_KLINE_ENABLED", True):
        try:
            from tradingagents.astock.store.permanent_kline import get_permanent_kline_store
            permanent = get_permanent_kline_store(
                current_app.config.get("ASTOCK_PERMANENT_KLINE_DB_PATH", "kline/kline.duckdb")
            )
            permanent.query_sql("SELECT 1 AS ready")
        except Exception as exc:
            logger.warning("health check permanent-store probe failed: %s", exc)
            permanent_ready = False
    status_code = 200 if store_connected and permanent_ready else 503
    return {
        "status": "ok" if store_connected and permanent_ready else "degraded",
        "backend": backend,
        "store_connected": store_connected,
        "mock_data_enabled": bool(current_app.config.get("ASTOCK_MOCK_DATA_ENABLED", False)),
        "uptime_seconds": uptime,
        "version": "0.3.0",
        "permanent_store_ready": permanent_ready,
    }, status_code


@bp.route("/health/ready")
@bp.route("/health")
def health_check() -> tuple[Response, int]:
    """Return readiness for load balancers and dependent API traffic."""
    payload, status_code = _readiness_payload()
    return jsonify(payload), status_code
