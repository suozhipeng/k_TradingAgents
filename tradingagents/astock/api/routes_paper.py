"""Paper trading API routes — trigger and query simulated trading state.

All routes return JSON.  Error responses follow ``{"error": ..., "status": N}``.

Uses lazy imports for ``tradingagents.astock.execution.paper_trader``.
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, Response, jsonify, request

bp = Blueprint("paper", __name__)

# Global paper trader instance (lazily initialised)
_paper_trader: Any = None


def _get_trader() -> Any:
    global _paper_trader
    if _paper_trader is None:
        from tradingagents.astock.execution.paper_trader import PaperTrader

        _paper_trader = PaperTrader()
    return _paper_trader


# ---------------------------------------------------------------------------
# POST /api/v1/paper/cycle
# ---------------------------------------------------------------------------


@bp.route("/paper/cycle", methods=["POST"])
def paper_cycle() -> tuple[Response, int]:
    """Trigger one paper trading cycle.

    JSON body:
        signals (dict[str, float]) — symbol → signal (1, -1, 0)
        prices (dict[str, float])  — symbol → last price
    """
    data = request.get_json(silent=True) or {}
    signals = data.get("signals", {})
    prices = data.get("prices", {})

    if not signals:
        return jsonify({"error": "signals dict is required", "status": 400}), 400
    if not prices:
        return jsonify({"error": "prices dict is required", "status": 400}), 400

    try:
        trader = _get_trader()
        state = trader.execute_cycle(signals, prices)
        return jsonify(
            {
                "positions": state.positions,
                "cash": state.cash,
                "total_value": state.total_value,
                "pnl": state.pnl,
                "trade_count": len(state.trades),
                "last_updated": state.last_updated,
            }
        ), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# GET /api/v1/paper/state
# ---------------------------------------------------------------------------


@bp.route("/paper/state")
def paper_state() -> tuple[Response, int]:
    """Return current paper trading state."""
    try:
        trader = _get_trader()
        state = trader.get_state()
        return jsonify(
            {
                "positions": state.positions,
                "cash": state.cash,
                "total_value": state.total_value,
                "pnl": state.pnl,
                "trade_count": len(state.trades),
                "last_updated": state.last_updated,
                "execution_signal": state.execution_signal,
                "decision_scope": state.decision_scope,
            }
        ), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# GET /api/v1/paper/trades
# ---------------------------------------------------------------------------


@bp.route("/paper/trades")
def paper_trades() -> tuple[Response, int]:
    """Return all historical paper trades."""
    try:
        trader = _get_trader()
        state = trader.get_state()
        return jsonify({"trades": state.trades}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500
