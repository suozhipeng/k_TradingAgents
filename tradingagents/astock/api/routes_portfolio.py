"""Portfolio risk and attribution API routes — Phase 36.

Returns portfolio risk exposure and Brinson-style performance attribution
as JSON.  Uses lazy imports for the paper trader and portfolio risk engine.
Shares PaperTrader singleton with routes_paper.

Error responses follow ``{"error": ..., "status": N}``.
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, Response, jsonify

bp = Blueprint("portfolio", __name__)


def _positions_from_state(state: Any) -> list[Any]:
    """Convert paper trader state positions to ``Position`` schema objects.

    Uses ``state.positions`` for share counts and ``state.initial_capital``
    to derive P&L.  ``current_price`` is estimated from market value when
    live prices are unavailable.
    """
    from tradingagents.astock.schemas.trading_execution import Position

    trader = _get_trader()
    positions: list[Any] = []
    for sym, shares in state.positions.items():
        if shares <= 0:
            continue
        cost_basis = trader.cost_basis(sym)
        avg_cost = round(cost_basis / shares, 2)
        # Estimate market value from PaperTrader's internal state
        mkt_val_each = trader.current_value(sym)
        mkt_val = round(shares * mkt_val_each, 2) if mkt_val_each > 0 else round(cost_basis, 2)
        pnl = round(mkt_val - cost_basis, 2)
        positions.append(
            Position(
                symbol=sym,
                quantity=round(shares, 4),
                avg_cost=avg_cost,
                current_price=mkt_val_each or avg_cost,
                market_value=mkt_val,
                pnl=pnl,
                pnl_pct=round((pnl / cost_basis) * 100, 2) if cost_basis > 0 else 0.0,
            )
        )
    return positions


# ---------------------------------------------------------------------------
# PaperTrader singleton — shared with routes_paper blueprint
# ---------------------------------------------------------------------------


def _get_trader() -> Any:
    """Get or create the shared PaperTrader singleton."""
    from .routes_paper import _get_trader as _paper_get_trader
    return _paper_get_trader()


# ---------------------------------------------------------------------------
# GET /api/v1/portfolio/risk — Portfolio risk exposure
# ---------------------------------------------------------------------------


@bp.route("/portfolio/risk")
def portfolio_risk() -> tuple[Response, int]:
    """Get portfolio risk exposure (VaR, concentration, stress).

    Returns
    -------
    JSON with keys matching :class:`~tradingagents.astock.schemas.portfolio.RiskExposure`:
    ``industry_concentration``, ``top_holding_pct``, ``beta``,
    ``liquidity_score``, ``var_95``, ``max_drawdown``, ``stress_loss_pct``.
    """
    try:
        trader = _get_trader()
        state = trader.get_state()
        positions = _positions_from_state(state)
        cash = state.cash

        from tradingagents.astock.execution.portfolio_risk import (
            calculate_risk_exposure,
        )

        risk = calculate_risk_exposure(positions, cash)
        return jsonify(risk), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# GET /api/v1/portfolio/attribution — Performance attribution
# ---------------------------------------------------------------------------


@bp.route("/portfolio/attribution")
def portfolio_attribution() -> tuple[Response, int]:
    """Get portfolio performance attribution (Brinson-style).

    Returns
    -------
    JSON with keys matching :class:`~tradingagents.astock.schemas.portfolio.Attribution`:
    ``benchmark_return``, ``selection_effect``, ``timing_effect``,
    ``cost_impact``, ``slippage_impact``, ``residual``.
    """
    try:
        trader = _get_trader()
        state = trader.get_state()
        positions = _positions_from_state(state)

        from tradingagents.astock.execution.portfolio_risk import (
            calculate_attribution,
        )

        attribution = calculate_attribution(positions)
        return jsonify(attribution), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


__all__ = ["bp"]
