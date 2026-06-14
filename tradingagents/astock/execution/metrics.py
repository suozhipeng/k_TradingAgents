"""Performance metric calculations (pure functions)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


def calculate_returns(prices: pd.Series) -> pd.Series:
    """Calculate daily (periodic) returns from a price series.

    Parameters
    ----------
    prices : pd.Series
        Price series indexed by date.

    Returns
    -------
    pd.Series
        Fractional returns (``pct_change``).
    """
    return prices.pct_change().fillna(0.0)


def calculate_sharpe(returns: pd.Series, rf_rate: float = 0.02) -> float:
    """Annualised Sharpe ratio.

    Parameters
    ----------
    returns : pd.Series
        Periodic (daily) returns.
    rf_rate : float
        Annual risk-free rate (default 0.02 = 2 %).

    Returns
    -------
    float
        Annualised Sharpe ratio.  Returns ``0.0`` if std is zero or data empty.
    """
    if len(returns) < 2:
        return 0.0
    # Infer periods per year from index length (rough estimate: 252 trading days)
    n = float(len(returns))
    periods_per_year = 252.0

    excess = returns - rf_rate / periods_per_year
    mean_excess = float(np.mean(excess))
    std_excess = float(np.std(excess, ddof=1))

    if std_excess == 0.0:
        return 0.0
    return round(mean_excess / std_excess * math.sqrt(periods_per_year), 6)


def calculate_max_drawdown(prices: pd.Series) -> float:
    """Maximum drawdown as a positive fraction (e.g. 0.25 = 25 % loss).

    Parameters
    ----------
    prices : pd.Series
        Price series indexed by date.

    Returns
    -------
    float
        Maximum drawdown as a non-negative fraction.
    """
    if len(prices) < 2:
        return 0.0
    cumulative_max = prices.cummax()
    drawdown = (prices - cumulative_max) / cumulative_max
    min_dd = float(drawdown.min())
    return round(abs(min_dd), 6) if min_dd < 0 else 0.0


def calculate_win_rate(trades: list[dict]) -> float:
    """Fraction of winning trades (PnL > 0).

    Parameters
    ----------
    trades : list[dict]
        List of trade records.  Each dict must have a ``"pnl"`` key.

    Returns
    -------
    float
        Win rate in ``[0.0, 1.0]``.  Returns ``0.0`` when no trades.
    """
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t.get("pnl", 0) > 0)
    return round(wins / len(trades), 6)


def summarize_metrics(prices: pd.Series, trades: list[dict]) -> dict[str, Any]:
    """Aggregate all performance metrics into a single dict.

    Parameters
    ----------
    prices : pd.Series
        Portfolio value / equity curve indexed by date.
    trades : list[dict]
        List of trade records.

    Returns
    -------
    dict
        ``{"total_return", "annualized_return", "sharpe_ratio",
        "max_drawdown", "win_rate", "total_trades"}``
    """
    returns = calculate_returns(prices)
    total_return = float(prices.iloc[-1] / prices.iloc[0] - 1) if len(prices) >= 2 else 0.0
    n = float(len(prices))
    periods_per_year = 252.0
    annualized_return = (1.0 + total_return) ** (periods_per_year / max(n, 1.0)) - 1.0 if n > 0 else 0.0

    return {
        "total_return": round(total_return, 6),
        "annualized_return": round(annualized_return, 6),
        "sharpe_ratio": calculate_sharpe(returns),
        "max_drawdown": calculate_max_drawdown(prices),
        "win_rate": calculate_win_rate(trades),
        "total_trades": len(trades),
    }
