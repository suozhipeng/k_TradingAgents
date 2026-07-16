"""Shared service: PaperTrader singleton for API routes.

Routes that need the paper trader instance should import ``get_paper_trader()``
from this module instead of reaching into ``routes_paper``.

This eliminates the circular import pattern::

    routes_dashboard  -->  routes_paper._get_trader()
    routes_portfolio  -->  routes_paper._get_trader()
"""

from __future__ import annotations

import threading
from typing import Any

_paper_trader: Any = None
_paper_trader_lock = threading.Lock()


def get_paper_trader() -> Any:
    """Return the app-scoped PaperTrader, with a fallback for non-Flask callers."""
    global _paper_trader
    try:
        from flask import current_app

        trader = current_app.config.get("PAPER_TRADER")
        if trader is None:
            # The factory normally creates this dependency. The lock covers
            # research-only/disabled-scheduler apps where the first request
            # may lazily initialise it from several request threads.
            lock = current_app.extensions.setdefault(
                "astock_paper_trader_init_lock", threading.Lock()
            )
            with lock:
                trader = current_app.config.get("PAPER_TRADER")
                if trader is None:
                    from tradingagents.astock.execution.paper_trader import PaperTrader

                    trader = PaperTrader()
                    current_app.config["PAPER_TRADER"] = trader
        return trader
    except RuntimeError:
        # Scheduler/unit callers may run outside a Flask application context.
        pass

    if _paper_trader is None:
        with _paper_trader_lock:
            if _paper_trader is None:
                from tradingagents.astock.execution.paper_trader import PaperTrader

                _paper_trader = PaperTrader()
    return _paper_trader


def serialize_paper_state(trader: Any | None = None) -> dict[str, Any]:
    """Return one Web/API-facing paper portfolio schema for all consumers."""
    trader = trader or get_paper_trader()
    state = trader.get_state()
    positions = []
    unrealized_pnl = 0.0

    for symbol, shares in state.positions.items():
        if shares <= 0:
            continue
        cost_basis = float(trader.cost_basis(symbol))
        avg_cost = round(cost_basis / shares, 2) if shares else 0.0
        # PaperTrader has no market-data dependency.  Its current value is the
        # cost basis until a separate mark-to-market feed is introduced.
        current_price = float(trader.current_value(symbol) or avg_cost)
        market_value = round(shares * current_price, 2)
        pnl = round(market_value - cost_basis, 2)
        unrealized_pnl += pnl
        positions.append(
            {
                "symbol": symbol,
                "quantity": round(shares, 4),
                "shares": round(shares, 4),
                "avg_cost": avg_cost,
                "cost_price": avg_cost,
                "current_price": current_price,
                "price": current_price,
                "price_source": "cost_basis",
                "market_value": market_value,
                "pnl": pnl,
                "pnl_pct": round((pnl / cost_basis) * 100, 2) if cost_basis else 0.0,
            }
        )

    realised_pnl = float(state.pnl)
    total_pnl = round(realised_pnl + unrealized_pnl, 2)
    initial_capital = round(float(state.cash) + sum(item["market_value"] for item in positions) - total_pnl, 2)
    total_value = round(float(state.cash) + sum(item["market_value"] for item in positions), 2)
    return {
        "positions": positions,
        "positions_map": dict(state.positions),
        "cash": round(float(state.cash), 2),
        "total_value": total_value,
        "portfolio_value": total_value,
        "initial_capital": initial_capital,
        "pnl": total_pnl,
        "realized_pnl": realised_pnl,
        "unrealized_pnl": round(unrealized_pnl, 2),
        "pnl_pct": round((total_pnl / initial_capital) * 100, 2) if initial_capital else 0.0,
        "trade_count": len(state.trades),
        "last_updated": state.last_updated,
        "execution_signal": state.execution_signal,
        "decision_scope": state.decision_scope,
    }


def serialize_paper_trades(trader: Any | None = None) -> list[dict[str, Any]]:
    """Expose the same trade field names across trading and paper pages."""
    trader = trader or get_paper_trader()
    records = []
    for trade in trader.get_state().trades:
        record = dict(trade)
        record["side"] = record.get("side") or record.get("type", "")
        record["quantity"] = record.get("quantity", record.get("shares", 0))
        records.append(record)
    return records
