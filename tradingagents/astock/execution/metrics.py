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


def _sanitize_metric_value(v: Any, key: str) -> Any:
    """Clamp a single metric to a valid range; NaN/Inf → 0.0.

    Returns a float (never None), so callers can safely pass the result
    into Pydantic models that require ``float``.

    Parameters
    ----------
    v : any
        Raw metric value.
    key : str
        Metric key name (``\"sharpe_ratio\"``, ``\"total_return\"``, etc.).

    Returns
    -------
    float
        Cleaned value (0.0 for invalid, clamped for extremes).
    """
    if v is None:
        return 0.0
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return 0.0
        # Extreme outlier guard — clamp to reasonable bounds
        if key == "sharpe_ratio":
            return max(-20.0, min(20.0, v))
        if key in ("total_return", "annualized_return", "max_drawdown"):
            return max(-10.0, min(10.0, v))
        if key == "win_rate":
            return max(0.0, min(1.0, v))
    elif not isinstance(v, (int, float)):
        return 0.0
    return float(v)


def summarize_metrics(prices: pd.Series, trades: list[dict]) -> dict[str, Any]:
    """Aggregate all performance metrics into a single dict.

    Each metric passes through ``_sanitize_metric_value`` so NaN/Inf/extremes
    are clipped before the caller sees them — no separate sanitisation step
    needed at the route layer.

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

    raw = {
        "total_return": round(total_return, 6),
        "annualized_return": round(annualized_return, 6),
        "sharpe_ratio": calculate_sharpe(returns),
        "max_drawdown": calculate_max_drawdown(prices),
        "win_rate": calculate_win_rate(trades),
        "total_trades": len(trades),
    }
    return {k: _sanitize_metric_value(v, k) for k, v in raw.items()}
