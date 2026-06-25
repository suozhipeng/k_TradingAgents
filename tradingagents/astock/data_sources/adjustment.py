"""A-share price adjustment utilities (复权处理).

Provides functions to adjust OHLCV data using akshare's adjustment factors,
with a fallback to the raw (unchanged) data when factors are unavailable.

Supported adjustment methods are defined in
``tradingagents.astock.execution.backtest_engine.AdjustmentMethod``:

- ``forward`` — 前复权 (adjust past prices to today's value)
- ``backward`` — 后复权 (adjust today's price to past value)
- ``none`` — 不复权 (raw data)
"""

from __future__ import annotations

import datetime
from typing import Any, Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Factor cache — avoid re-fetching for repeated symbols in the same session
# ---------------------------------------------------------------------------
_factor_cache: dict[str, pd.DataFrame] = {}


def _fetch_adjust_factors(symbol: str) -> pd.DataFrame:
    """Fetch adjustment factors for *symbol* via akshare (cached per session)."""
    if symbol in _factor_cache:
        return _factor_cache[symbol]

    try:
        import akshare as ak

        factors = ak.stock_zh_a_adjust(symbol=symbol, start_date="19900101")
        if factors is not None and not factors.empty:
            _factor_cache[symbol] = factors
            return factors
    except Exception:
        pass

    return pd.DataFrame()


def _adjust_factor_for_date(factors: pd.DataFrame, date: datetime.date) -> Optional[float]:
    """Get the cumulative adjustment factor for *date*.

    The factor is the value by which to divide the *raw* price to get the
    adjusted price.  If no factor is available for the given date, returns
    the most recent prior factor or 1.0 if none.
    """
    if factors.empty:
        return None

    date_str = date.isoformat()
    if "date" in factors.columns:
        match = factors[factors["date"].astype(str).str.startswith(date_str)]
        if not match.empty:
            return float(match.iloc[0].get("adjust_factor", 1.0))

    # No exact match — use the most recent prior factor
    if "date" in factors.columns:
        factors_dates = pd.to_datetime(factors["date"])
        prior = factors_dates[factors_dates <= pd.Timestamp(date)]
        if not prior.empty:
            idx = prior.idxmax()
            return float(factors.loc[idx].get("adjust_factor", 1.0))

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def adjust_series(
    series: pd.Series,
    factor: Optional[float],
    method: str = "forward",
) -> pd.Series:
    """Apply an adjustment factor to a price series.

    Parameters
    ----------
    series : pd.Series
        Raw price values.
    factor : float or None
        Adjustment factor.  If None, returns the series unchanged.
    method : str
        One of ``\"forward\"``, ``\"backward\"``, ``\"none\"``.

    Returns
    -------
    pd.Series
        Adjusted price series (same index as input).
    """
    if factor is None or factor <= 0 or method == "none":
        return series.copy()

    if method == "forward":
        return series / factor
    elif method == "backward":
        return series * factor

    return series.copy()


def adjust_bars(
    df: pd.DataFrame,
    symbol: str,
    method: str = "forward",
) -> pd.DataFrame:
    """Adjust all OHLCV columns in a DataFrame using the given method.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV data with a DatetimeIndex.
    symbol : str
        A-share symbol (e.g. ``\"600519.SH\"``).
    method : str
        Adjustment method (``\"forward\"``, ``\"backward\"``, ``\"none\"``).

    Returns
    -------
    pd.DataFrame
        Adjusted data (same shape and index as input).
    """
    if method == "none" or df.empty:
        return df.copy()

    factors = _fetch_adjust_factors(symbol)

    price_cols = [c for c in ("open", "high", "low", "close") if c in df.columns]

    result = df.copy()
    for idx in result.index:
        dt = idx.date() if hasattr(idx, "date") else idx
        if isinstance(dt, pd.Timestamp):
            dt = dt.date()
        factor = _adjust_factor_for_date(factors, dt)
        if factor is not None and factor > 0:
            for col in price_cols:
                result.at[idx, col] = result.at[idx, col] / factor

    return result
