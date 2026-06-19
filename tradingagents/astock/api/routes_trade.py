"""Trade execution API routes — individual order placement and quote lookup.

All routes return JSON.  Error responses follow ``{"error": ..., "status": N}``.

Uses lazy imports for ``tradingagents.astock.execution.paper_trader``.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any

from flask import Blueprint, Response, jsonify, request

bp = Blueprint("trade", __name__)

# Global paper trader instance (shared with paper blueprint)
_trader: Any = None


def _get_trader() -> Any:
    global _trader
    if _trader is None:
        from tradingagents.astock.execution.paper_trader import PaperTrader

        _trader = PaperTrader()
    return _trader


# ---------------------------------------------------------------------------
# POST /api/v1/trade/order — Place an individual order
# ---------------------------------------------------------------------------


@bp.route("/trade/order", methods=["POST"])
def place_order() -> tuple[Response, int]:
    """Place a buy or sell order with specified quantity.

    JSON body:
        symbol (str) — stock symbol
        side (str) — "buy" or "sell"
        price (float) — price per share
        quantity (int) — number of shares

    Returns filled order details or error.
    """
    data = request.get_json(silent=True) or {}
    symbol = data.get("symbol", "").strip()
    side = data.get("side", "").strip().lower()
    price = data.get("price")
    quantity = data.get("quantity")

    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    if side not in ("buy", "sell"):
        return jsonify({"error": "side must be 'buy' or 'sell'", "status": 400}), 400
    if not isinstance(price, (int, float)) or price <= 0:
        return jsonify({"error": "price must be positive", "status": 400}), 400
    if not isinstance(quantity, int) or quantity <= 0:
        return jsonify({"error": "quantity must be a positive integer", "status": 400}), 400

    try:
        trader = _get_trader()
        result = trader.place_order(symbol, side, float(price), int(quantity))
        return jsonify({"status": "ok", "order": result}), 200
    except ValueError as exc:
        return jsonify({"error": str(exc), "status": 400}), 400
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# GET /api/v1/trade/quote — Mock real-time quote for a symbol
# ---------------------------------------------------------------------------


@bp.route("/trade/quote")
def get_quote() -> tuple[Response, int]:
    """GET /api/v1/trade/quote?symbol=600519.SH

    Returns a synthetic mock quote (last price, change, volume, bid/ask).
    """
    symbol = request.args.get("symbol", "").strip()
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400

    # Generate a deterministic-but-varying mock quote
    seed = hash(symbol + datetime.now().strftime("%Y%m%d%H"))
    rng = random.Random(seed)

    base_price: float
    if symbol.startswith("600") or symbol.startswith("000"):
        # Known A-share large caps
        base_prices = {
            "600519.SH": 1680.0,
            "000001.SZ": 13.5,
            "300750.SZ": 235.0,
            "000858.SZ": 145.0,
            "601318.SH": 52.0,
            "600036.SH": 38.0,
            "002475.SZ": 38.5,
            "000333.SZ": 72.0,
        }
        base_price = base_prices.get(symbol, 50.0)
    else:
        base_price = 50.0

    change_pct = rng.uniform(-3.5, 3.5)
    last_price = round(base_price * (1 + change_pct / 100), 2)
    change = round(last_price - base_price, 2)
    volume = rng.randint(100000, 5000000)
    bid = round(last_price - rng.uniform(0.01, 0.5), 2)
    ask = round(last_price + rng.uniform(0.01, 0.5), 2)
    high = round(last_price * (1 + rng.uniform(0, 0.02)), 2)
    low = round(last_price * (1 - rng.uniform(0, 0.02)), 2)
    open_price = round(last_price * (1 + rng.uniform(-0.01, 0.01)), 2)

    return jsonify({
        "symbol": symbol,
        "last_price": last_price,
        "open": open_price,
        "high": high,
        "low": low,
        "change": change,
        "change_pct": round(change_pct, 2),
        "volume": volume,
        "bid": bid,
        "ask": ask,
        "timestamp": datetime.utcnow().isoformat(),
    }), 200


# ---------------------------------------------------------------------------
# GET /api/v1/trade/state — Current trading state (positions, cash, P&L)
# ---------------------------------------------------------------------------


@bp.route("/trade/state")
def trade_state() -> tuple[Response, int]:
    """Return current paper trading state for the trading page."""
    try:
        trader = _get_trader()
        state = trader.get_state()
        # Enrich positions with mock current prices for P&L computation
        enriched_positions = []
        for sym, shares in state.positions.items():
            seed = hash(sym + datetime.now().strftime("%Y%m%d%H"))
            rng = random.Random(seed)
            mock_price = round(rng.uniform(10.0, 2000.0), 2)
            cost_basis = trader._cost_basis.get(sym, 0.0)
            avg_cost = round(cost_basis / shares, 2) if shares > 0 else 0
            mkt_val = round(shares * mock_price, 2)
            pnl = round(mkt_val - cost_basis, 2)
            pnl_pct = round((pnl / cost_basis) * 100, 2) if cost_basis > 0 else 0.0
            enriched_positions.append({
                "symbol": sym,
                "shares": round(shares, 4),
                "avg_cost": avg_cost,
                "current_price": mock_price,
                "market_value": mkt_val,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
            })

        return jsonify({
            "cash": state.cash,
            "total_value": state.total_value,
            "pnl": state.pnl,
            "positions": enriched_positions,
            "trade_count": len(state.trades),
        }), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


__all__ = ["bp"]
