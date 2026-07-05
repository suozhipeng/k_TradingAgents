"""Parametric Value-at-Risk (VaR) computation for a portfolio.

Provides ``calculate_var`` which estimates potential loss at a given
confidence level using a simplified parametric approach.
"""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import List

from tradingagents.astock.schemas.trading_execution import Position


def _norm_ppf(p: float) -> float:
    """Standard normal inverse CDF (z-score) via ``NormalDist``.

    Parameters
    ----------
    p : float
        Cumulative probability in ``(0, 1)``.

    Returns
    -------
    float
        The z-score such that ``Φ(z) ≈ p``.

    Raises
    ------
    ValueError
        If *p* is not in ``(0, 1)``.
    """
    _NORMAL = NormalDist()

    if not 0 < p < 1:
        msg = f"confidence must be in (0, 1), got {p}"
        raise ValueError(msg)
    return _NORMAL.inv_cdf(p)


def _portfolio_value(positions: List[Position], cash: float) -> float:
    """Total NAV = sum of position market values + cash."""
    return sum(p.market_value for p in positions) + cash


def calculate_var(
    positions: List[Position],
    cash: float,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Compute parametric Value-at-Risk for the portfolio.

    Uses a simple parametric approach: estimates the standard deviation
    of portfolio returns from position-level P&L data, then computes
    ``VaR = z * sigma * nav`` where *z* is the normal quantile at the
    given confidence level.

    Parameters
    ----------
    positions : list[Position]
        Current open positions.
    cash : float
        Cash held.
    confidence : float
        Confidence level in ``(0, 1)`` (default ``0.95``).

    Returns
    -------
    tuple[float, float]
        ``(var_value, var_pct)`` where both are **positive** numbers
        representing potential loss (e.g. ``var_value=12500`` means a
        possible loss of ¥12 500).  ``var_pct`` is relative to NAV.
    """
    nav = _portfolio_value(positions, cash)
    if nav <= 0 or not positions:
        return 0.0, 0.0

    # Compute per-position returns and weights
    weights: List[float] = []
    returns: List[float] = []
    for p in positions:
        cost_basis = p.market_value - p.pnl
        ret = p.pnl / cost_basis if cost_basis != 0 else 0.0
        w = p.market_value / nav
        weights.append(w)
        returns.append(ret)

    # Portfolio expected return (weighted average)
    portfolio_return = sum(w * r for w, r in zip(weights, returns, strict=False))

    # Variance of portfolio returns
    n = len(returns)
    if n < 2:
        sigma = abs(portfolio_return) if portfolio_return != 0 else 0.01
    else:
        mean_ret = sum(returns) / n
        variance = sum(w * (r - mean_ret) ** 2 for w, r in zip(weights, returns, strict=False))
        variance *= n / max(n - 1, 1)
        sigma = math.sqrt(variance) if variance > 0 else 0.01

    z = _norm_ppf(confidence)
    var_value = z * sigma * nav
    var_pct = z * sigma

    return round(var_value, 2), round(var_pct, 6)
