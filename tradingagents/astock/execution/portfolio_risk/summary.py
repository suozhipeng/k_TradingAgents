"""Aggregate risk exposure summary for a portfolio.

Provides ``calculate_risk_exposure`` which combines VaR, industry
concentration, liquidity, and stress metrics into a single dict.
"""

from __future__ import annotations

import logging

from typing import Any, List, Optional

from tradingagents.astock.schemas.trading_execution import Position
from .var import calculate_var, _portfolio_value
from .exposure import calculate_industry_exposure
logger = logging.getLogger(__name__)


def calculate_risk_exposure(
    positions: List[Position],
    cash: float,
    historical_returns: Any = None,
) -> Dict[str, Any]:
    """Aggregate risk exposure summary for a portfolio.

    Combines VaR, industry concentration, liquidity, and stress metrics
    into a single dict matching the
    :class:`~tradingagents.astock.schemas.portfolio.RiskExposure` schema.

    Parameters
    ----------
    positions : list[Position]
        Current open positions.
    cash : float
        Cash held.
    historical_returns : Any, optional
        A sequence of historical portfolio returns (``pd.Series``, ``list``,
        or ``None``).  Used for max-drawdown calculation.  ``None`` yields
        ``max_drawdown=0``.

    Returns
    -------
    dict
        Keys match :class:`~tradingagents.astock.schemas.portfolio.RiskExposure`
        field names: ``industry_concentration``, ``top_holding_pct``,
        ``beta``, ``liquidity_score``, ``var_95``, ``max_drawdown``,
        ``stress_loss_pct``.
    """
    nav = _portfolio_value(positions, cash)

    # --- VaR ---
    var_value, var_pct = calculate_var(positions, cash, confidence=0.95)

    # --- Industry exposure & concentration ---
    industry_exposure = calculate_industry_exposure(positions)
    if industry_exposure:
        hhi = sum(v * v for v in industry_exposure.values())
        n = len(industry_exposure)
        industry_concentration = (hhi - 1.0 / n) / (1.0 - 1.0 / n) if n > 1 else 1.0
    else:
        industry_concentration = 0.0

    # --- Top holding concentration ---
    if positions and nav > 0:
        top_holding_pct = max(p.market_value / nav for p in positions)
    else:
        top_holding_pct = 0.0

    # --- Max drawdown ---
    if historical_returns is not None:
        try:
            values = list(historical_returns)
            if len(values) >= 2:
                peak = values[0]
                max_dd = 0.0
                for v in values:
                    if v > peak:
                        peak = v
                    dd = (peak - v) / peak if peak != 0 else 0.0
                    if dd > max_dd:
                        max_dd = dd
            else:
                max_dd = 0.0
        except Exception:
            max_dd = 0.0
    else:
        max_dd = 0.0

    # --- Liquidity score ---
    if positions and nav > 0:
        weights = [p.market_value / nav for p in positions]
        hhi_positions = sum(w * w for w in weights)
        n_pos = len(weights)
        min_hhi = 1.0 / max(n_pos, 1)
        concentration = (hhi_positions - min_hhi) / (1.0 - min_hhi) if n_pos > 1 else 1.0
        liquidity_score = round(max(0.0, 1.0 - concentration), 6)
    else:
        liquidity_score = 0.0

    # --- Stress loss (2.5 × VaR_95) ---
    stress_loss_pct = round(var_pct * 2.5, 6)

    return {
        "industry_concentration": round(industry_concentration, 6),
        "top_holding_pct": round(top_holding_pct, 6),
        "beta": 1.0,
        "liquidity_score": liquidity_score,
        "var_95": round(var_value, 2),
        "max_drawdown": round(max_dd, 6),
        "stress_loss_pct": stress_loss_pct,
    }
