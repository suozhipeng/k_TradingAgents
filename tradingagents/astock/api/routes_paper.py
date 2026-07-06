"""Paper trading API routes — trigger and query simulated trading state.

All routes return JSON.  Error responses follow ``{"error": ..., "status": N}``.

Uses lazy imports for ``tradingagents.astock.execution.paper_trader``.
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, Response, jsonify, request

from ._paper_service import get_paper_trader

bp = Blueprint("paper", __name__)


# ---------------------------------------------------------------------------
# POST /api/v1/paper/cycle
# ---------------------------------------------------------------------------


@bp.route("/paper/cycle", methods=["POST"])
def paper_cycle() -> tuple[Response, int]:
    data = request.get_json(silent=True) or {}
    signals = data.get("signals", {})
    prices = data.get("prices", {})

    if not signals:
        return jsonify({"error": "signals dict is required", "status": 400}), 400
    if not prices:
        return jsonify({"error": "prices dict is required", "status": 400}), 400

    try:
        trader = get_paper_trader()
        state = trader.execute_cycle(signals, prices)
        return jsonify({
            "positions": state.positions, "cash": state.cash,
            "total_value": state.total_value, "pnl": state.pnl,
            "trade_count": len(state.trades), "last_updated": state.last_updated,
        }), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# GET /api/v1/paper/state
# ---------------------------------------------------------------------------


@bp.route("/paper/state")
def paper_state() -> tuple[Response, int]:
    try:
        trader = get_paper_trader()
        state = trader.get_state()
        return jsonify({
            "positions": state.positions, "cash": state.cash,
            "total_value": state.total_value, "pnl": state.pnl,
            "trade_count": len(state.trades), "last_updated": state.last_updated,
            "execution_signal": state.execution_signal,
            "decision_scope": state.decision_scope,
        }), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# GET /api/v1/paper/trades
# ---------------------------------------------------------------------------


@bp.route("/paper/trades")
def paper_trades() -> tuple[Response, int]:
    try:
        limit = int(request.args.get("limit", "0"))
        trader = get_paper_trader()
        state = trader.get_state()
        trades = state.trades
        count = len(trades)
        if limit > 0:
            trades = trades[-limit:]
        return jsonify({
            "trades": trades, "count": count, "limit": limit or count,
        }), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500
