"""QMT status API routes — read-only bridge health, positions, and orders.

All routes return JSON.  Error responses follow ``{"error": ..., "status": N}``.

Uses lazy imports for ``tradingagents.astock.execution.qmt_bridge``.
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, Response, jsonify

bp = Blueprint("qmt", __name__)

# Global QMT bridge instance (lazily created; mock mode supported)
_qmt_bridge: Any = None


def _get_bridge() -> Any:
    global _qmt_bridge
    if _qmt_bridge is None:
        from tradingagents.astock.execution.qmt_bridge import QmtBridge

        _qmt_bridge = QmtBridge(use_mock=True)
    return _qmt_bridge


# ---------------------------------------------------------------------------
# GET /api/v1/qmt/health
# ---------------------------------------------------------------------------


@bp.route("/qmt/health")
def qmt_health() -> tuple[Response, int]:
    """QMT bridge health check."""
    try:
        bridge = _get_bridge()
        ok = bridge.health_check()
        return jsonify(
            {
                "healthy": ok,
                "mock_mode": bridge.is_mock,
                "host": bridge.config.host,
                "port": bridge.config.port,
            }
        ), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500, "healthy": False}), 500


# ---------------------------------------------------------------------------
# GET /api/v1/qmt/positions
# ---------------------------------------------------------------------------


@bp.route("/qmt/positions")
def qmt_positions() -> tuple[Response, int]:
    """QMT current positions (read-only)."""
    try:
        bridge = _get_bridge()
        positions = bridge.get_positions()
        return jsonify({"positions": positions, "mock_mode": bridge.is_mock}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# GET /api/v1/qmt/orders
# ---------------------------------------------------------------------------


@bp.route("/qmt/orders")
def qmt_orders() -> tuple[Response, int]:
    """QMT open / pending orders (read-only, mock)."""
    try:
        bridge = _get_bridge()
        account_info = bridge.get_account_info()
        return jsonify(
            {
                "orders": [
                    {
                        "account_id": account_info.get("account_id", ""),
                        "total_asset": account_info.get("total_asset", 0),
                        "cash": account_info.get("cash", 0),
                        "market_value": account_info.get("market_value", 0),
                        "frozen_cash": account_info.get("frozen_cash", 0),
                        "available_cash": account_info.get("available_cash", 0),
                    }
                ],
                "mock_mode": bridge.is_mock,
            }
        ), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500
