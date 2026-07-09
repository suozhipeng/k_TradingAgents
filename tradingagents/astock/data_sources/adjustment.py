"""
A-share price adjustment utilities (复权处理).

Provides functions to adjust OHLCV data using adjustment factors from
akshare (EastMoney-backed) with fallback to derived factors from
stock_zh_a_hist, and DuckDB persistence for caching.

Supported adjustment methods:
- ``forward`` — 前复权 (adjust past prices to today's value)
- ``backward`` — 后复权 (adjust today's price to past value)
- ``none`` — 不复权 (raw data)
"""

from __future__ import annotations

import datetime
import json
from typing import Any, Optional

import pandas as pd

from .errors import AStockSourceUnavailableError
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try to import _retry from suspension (fallback to simple retry if unavailable)
# ---------------------------------------------------------------------------

try:
    from .suspension import _retry
except ImportError:
    import time
    _RETRYABLE_EXCEPTIONS = (ConnectionError, TimeoutError, OSError)

    def _retry(fn, max_attempts=3, base_delay=1.0, backoff=2.0):
        last_exc = None
        for attempt in range(max_attempts):
            try:
                return fn()
            except _RETRYABLE_EXCEPTIONS:
                if attempt < max_attempts - 1:
                    time.sleep(base_delay * (backoff ** attempt))
                continue
            except Exception as exc:
                last_exc = exc
                raise
        if last_exc is not None:
            raise AStockSourceUnavailableError("retry", f"All {max_attempts} attempts failed: {last_exc}")
        raise AStockSourceUnavailableError("retry", f"All {max_attempts} attempts failed.")

# ---------------------------------------------------------------------------
# Factor cache — in-memory + optional DuckDB persistence
# ---------------------------------------------------------------------------
_factor_cache: dict[str, pd.DataFrame] = {}
_duckdb_conn: Any = None


def _set_duckdb(conn: Any) -> None:
    """Register a DuckDB connection for persistent factor caching."""
    global _duckdb_conn
    _duckdb_conn = conn


# ---------------------------------------------------------------------------
# EastMoney datacenter API — adjustment factors (复权因子)
# ---------------------------------------------------------------------------

EM_ADJUST_URL = "https://datacenter.eastmoney.com/securities/api/data/v1/get"


def fetch_adjust_via_eastmoney(symbol: str) -> pd.DataFrame:
    """Fetch adjustment factors from EastMoney datacenter API.

    Parameters
    ----------
    symbol : str
        Normalized A-share symbol (e.g. ``"600519.SH"``).

    Returns
    -------
    pd.DataFrame
        DataFrame with columns ``trade_date``, ``adjust_factor``.
        Empty DataFrame on failure.
    """
    import requests

    # Extract raw code
    code = symbol.replace(".SH", "").replace(".SZ", "")

    params = {
        "reportName": "RPT_F10_FINANCE_ADJUST",
        "columns": "SECUCODE,TRADE_DATE,ADJUST_FACTOR",
        "filter": f'(SECUCODE="{code}.{("SH" if symbol.endswith(".SH") else "SZ")}")',
        "pageNumber": 1,
        "pageSize": 5000,
        "sortTypes": -1,
        "sortColumns": "TRADE_DATE",
        "source": "WEB",
        "client": "WEB",
    }

    def _do_fetch():
        resp = requests.get(
            EM_ADJUST_URL,
            params=params,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://data.eastmoney.com/",
            },
            timeout=15,
        )
        return resp.json()

    try:
        data = _retry(_do_fetch, max_attempts=3, base_delay=1.0)
    except Exception:
        return pd.DataFrame()

    rows = None
    if isinstance(data, dict):
        result = data.get("result") or data.get("data") or {}
        if isinstance(result, dict):
            rows = result.get("list") or result.get("data") or []
        elif isinstance(result, list):
            rows = result
    if not rows:
        rows = data.get("list") or data.get("data") or []

    if not rows:
        return pd.DataFrame()

    records = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        date_val = row.get("TRADE_DATE") or row.get("trade_date") or ""
        factor_val = row.get("ADJUST_FACTOR") or row.get("adjust_factor")
        if date_val and factor_val is not None:
            try:
                records.append({
                    "date": str(date_val)[:10],
                    "adjust_factor": float(factor_val),
                })
            except (ValueError, TypeError):
                continue

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Akshare — derive factors from stock_zh_a_hist (adjusted vs unadjusted)
# ---------------------------------------------------------------------------


def fetch_adjust_via_akshare_hist(symbol: str) -> pd.DataFrame:
    """Derive adjustment factors by comparing adjusted vs unadjusted prices.

    Uses ``ak.stock_zh_a_hist()`` with ``adjust='qfq'`` and no adjust to
    compute the cumulative factor.

    Parameters
    ----------
    symbol : str
        Normalized A-share symbol.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns ``date``, ``adjust_factor``.
        Empty DataFrame on failure.
    """
    code = symbol.replace(".SH", "").replace(".SZ", "")

    try:
        import akshare as ak

        def _fetch_adj():
            return ak.stock_zh_a_hist(symbol=code, period="daily", start_date="19900101", adjust="qfq")

        def _fetch_raw():
            return ak.stock_zh_a_hist(symbol=code, period="daily", start_date="19900101", adjust="")

        df_adj = _retry(_fetch_adj, max_attempts=2, base_delay=1.0)
        df_raw = _retry(_fetch_raw, max_attempts=2, base_delay=1.0)
    except Exception:
        return pd.DataFrame()

    if df_adj is None or df_raw is None or df_adj.empty or df_raw.empty:
        return pd.DataFrame()

    # Map columns
    date_col = None
    for c in ("日期", "date", "trade_date"):
        if c in df_adj.columns:
            date_col = c
            break
    if date_col is None:
        return pd.DataFrame()

    close_col = None
    for c in ("收盘", "close"):
        if c in df_adj.columns:
            close_col = c
            break
    if close_col is None:
        return pd.DataFrame()

    # Merge on date
    merged = df_adj[[date_col, close_col]].merge(
        df_raw[[date_col, close_col]],
        on=date_col,
        suffixes=("_adj", "_raw"),
    )

    records = []
    for _, row in merged.iterrows():
        adj_close = row.get(f"{close_col}_adj")
        raw_close = row.get(f"{close_col}_raw")
        if adj_close is not None and raw_close is not None and raw_close > 0:
            factor = float(adj_close) / float(raw_close)
            records.append({
                "date": str(row[date_col])[:10],
                "adjust_factor": round(factor, 6),
            })

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Unified fetcher with fallback
# ---------------------------------------------------------------------------


def fetch_adjust_factors(symbol: str) -> pd.DataFrame:
    """Fetch adjustment factors with fallback chain.

    Fallback chain:
    1. In-memory cache
    2. DuckDB persistent cache (if registered)
    3. EastMoney datacenter API
    4. Akshare derived factors (from stock_zh_a_hist comparison)

    Parameters
    ----------
    symbol : str
        Normalized A-share symbol.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns ``date``, ``adjust_factor``.
    """
    # 1. In-memory cache
    if symbol in _factor_cache:
        return _factor_cache[symbol]

    # 2. DuckDB cache
    if _duckdb_conn is not None:
        try:
            query = (
                "SELECT DISTINCT trade_date AS date, adjust_factor "
                "FROM adjustment_factors WHERE symbol = ? "
                "ORDER BY trade_date"
            )
            df = _duckdb_conn.execute(query, [symbol]).fetchdf()
            if df is not None and not df.empty:
                _factor_cache[symbol] = df
                return df
        except Exception as e:

            logger.debug("Operation failed: {0}", e)


    # 3+4. External sources with fallback
    sources = [
        ("eastmoney", fetch_adjust_via_eastmoney),
        ("akshare_hist", fetch_adjust_via_akshare_hist),
    ]
    for name, fetcher in sources:
        try:
            df = fetcher(symbol)
            if df is not None and not df.empty:
                _factor_cache[symbol] = df
                # Persist to DuckDB if available
                if _duckdb_conn is not None:
                    try:
                        _persist_to_duckdb(symbol, df)
                    except Exception as e:

                        logger.debug("Operation failed: {0}", e)

                return df
        except Exception:
            continue

    return pd.DataFrame()


def _persist_to_duckdb(symbol: str, df: pd.DataFrame) -> None:
    """Store adjustment factors in DuckDB for persistent caching."""
    if _duckdb_conn is None or df.empty:
        return
    try:
        _duckdb_conn.execute(
            "CREATE TABLE IF NOT EXISTS adjustment_factors ("
            "  symbol VARCHAR,"
            "  trade_date DATE,"
            "  adjust_factor DOUBLE,"
            "  PRIMARY KEY (symbol, trade_date)"
            ")"
        )
        for _, row in df.iterrows():
            _duckdb_conn.execute(
                "INSERT OR REPLACE INTO adjustment_factors (symbol, trade_date, adjust_factor) "
                "VALUES (?, ?, ?)",
                [symbol, row["date"], float(row["adjust_factor"])],
            )
    except Exception as e:

        logger.debug("Operation failed: {0}", e)



# ---------------------------------------------------------------------------
# Factor lookup for a specific date
# ---------------------------------------------------------------------------


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
# Public API — adjust price series/bars
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
        One of ``"forward"``, ``"backward"``, ``"none"``.

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
        A-share symbol (e.g. ``"600519.SH"``).
    method : str
        Adjustment method (``"forward"``, ``"backward"``, ``"none"``).

    Returns
    -------
    pd.DataFrame
        Adjusted data (same shape and index as input).
    """
    if method == "none" or df.empty:
        return df.copy()

    factors = fetch_adjust_factors(symbol)

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


# ---------------------------------------------------------------------------
# Clear cache (for testing)
# ---------------------------------------------------------------------------


def clear_cache() -> None:
    """Clear the in-memory factor cache."""
    _factor_cache.clear()


__all__ = [
    "fetch_adjust_factors",
    "fetch_adjust_via_eastmoney",
    "fetch_adjust_via_akshare_hist",
    "_adjust_factor_for_date",
    "adjust_series",
    "adjust_bars",
    "_set_duckdb",
    "clear_cache",
]
