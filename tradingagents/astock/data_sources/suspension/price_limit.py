"""
Price limit (涨跌停) related functions for A-share stocks.
"""

from __future__ import annotations

import datetime
import json
import logging
import time
from typing import Any, Optional

import pandas as pd

from .common import _retry, PriceLimitRecord, _normalize_code, _make_symbol, get_price_limit_pct, get_price_limit_prices
from ..errors import AStockNoDataError, AStockSourceUnavailableError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Akshare backend — price limit pools (涨停/跌停)
# ---------------------------------------------------------------------------


def fetch_price_limit_pool_via_akshare(
    date: Optional[str] = None,
) -> list[PriceLimitRecord]:
    """Fetch real-time 涨停 (limit-up) and 跌停 (limit-down) stocks from
    akshare's EastMoney-backed APIs.

    Uses:
    - ``ak.stock_zt_pool_em()`` — 涨停股池
    - ``ak.stock_zt_pool_dtgc_em()`` — 跌停股池

    Parameters
    ----------
    date : str or None
        Date in ``"YYYY-MM-DD"`` format.  Defaults to today.

    Returns
    -------
    list[PriceLimitRecord]
    """
    if date is None:
        date = datetime.date.today().isoformat()

    records: list[PriceLimitRecord] = []

    # ── 涨停 (limit-up) pool ──
    try:
        import akshare as ak

        def _fetch_up():
            return ak.stock_zt_pool_em(date=date)

        df_up = _retry(_fetch_up, max_attempts=3, base_delay=1.0)
    except Exception:
        df_up = None

    if df_up is not None and not df_up.empty:
        for _, row in df_up.iterrows():
            code = _normalize_code(str(row.get("代码", "")))
            if not code:
                continue
            symbol = _make_symbol(code)
            records.append(
                PriceLimitRecord(
                    symbol=symbol,
                    code=code,
                    name=str(row.get("名称", "")) or None,
                    price=float(row["最新价"]) if pd.notna(row.get("最新价")) else None,
                    change_pct=float(row["涨跌幅"]) if pd.notna(row.get("涨跌幅")) else None,
                    direction="up",
                    consecutive=int(row.get("连板数", 0)) if pd.notna(row.get("连板数")) else 0,
                    source="akshare",
                ),
            )

    # ── 跌停 (limit-down) pool ──
    try:
        def _fetch_down():
            return ak.stock_zt_pool_dtgc_em(date=date)

        df_down = _retry(_fetch_down, max_attempts=3, base_delay=1.0)
    except Exception:
        df_down = None

    if df_down is not None and not df_down.empty:
        for _, row in df_down.iterrows():
            code = _normalize_code(str(row.get("代码", "")))
            if not code:
                continue
            symbol = _make_symbol(code)
            records.append(
                PriceLimitRecord(
                    symbol=symbol,
                    code=code,
                    name=str(row.get("名称", "")) or None,
                    price=float(row["最新价"]) if pd.notna(row.get("最新价")) else None,
                    change_pct=float(row["涨跌幅"]) if pd.notna(row.get("涨跌幅")) else None,
                    direction="down",
                    consecutive=int(row.get("连板数", 0)) if pd.notna(row.get("连板数")) else 0,
                    source="akshare",
                ),
            )

    return records


# ---------------------------------------------------------------------------
# EastMoney backend — price limit via push2 real-time market data
# ---------------------------------------------------------------------------

EM_PUSH2_QUOTE_URL = "https://push2.eastmoney.com/api/qt/clist/get"


def fetch_price_limit_via_eastmoney_push2(
    date: Optional[str] = None,
) -> list[PriceLimitRecord]:
    """Fetch price limit stocks from EastMoney push2 real-time API.

    Uses the push2 quote list API with a filter for stocks whose change
    percentage is near the daily limit (±9.5% for normal, ±4.5% for ST).

    This is a **fallback** for when akshare's price limit pool is unavailable.

    Parameters
    ----------
    date : str or None
        Ignored (the API always returns real-time data).

    Returns
    -------
    list[PriceLimitRecord]
    """
    from .eastmoney import em_get

    # Market: 1=SH A, 0=SZ A. Fetch both.
    all_records: list[PriceLimitRecord] = []
    limit_threshold = 9.5  # percentage

    for market_id in (1, 0):
        params = {
            "pn": 1,
            "pz": 2000,
            "po": 1,
            "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2,
            "invt": 2,
            "fid": "f3",  # sort by change_pct
            "fs": f"m:{market_id}+t:1",  # A-shares only
            "fields": "f12,f14,f2,f3,f4",
            "_": int(time.time() * 1000),
        }

        try:
            resp = em_get(
                EM_PUSH2_QUOTE_URL,
                params=params,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Referer": "https://quote.eastmoney.com/",
                },
                timeout=10,
            )
            data = resp.json()
        except Exception:
            continue

        items = data.get("data", {}).get("diff", []) if isinstance(data, dict) else []
        if not items:
            continue

        for item in items:
            if not isinstance(item, dict):
                continue
            code = _normalize_code(str(item.get("f12", "")))
            if not code:
                continue
            change_pct = item.get("f3")
            if change_pct is None:
                continue
            try:
                change_pct = float(change_pct)
            except (ValueError, TypeError):
                continue

            # Determine direction: near limit-up or limit-down
            direction: Optional[str] = None
            if change_pct >= limit_threshold:
                direction = "up"
            elif change_pct <= -limit_threshold:
                direction = "down"
            else:
                continue

            current_price = item.get("f2")
            try:
                current_price = float(current_price) if current_price is not None else None
            except (ValueError, TypeError):
                current_price = None

            symbol = _make_symbol(code)
            all_records.append(
                PriceLimitRecord(
                    symbol=symbol,
                    code=code,
                    name=str(item.get("f14", "")) or None,
                    price=current_price,
                    change_pct=change_pct,
                    direction=direction,
                    consecutive=0,
                    source="eastmoney",
                ),
            )

    return all_records


# ---------------------------------------------------------------------------
# Unified facade — price limit (涨跌停)
# ---------------------------------------------------------------------------


def fetch_price_limit_pool(
    date: Optional[str] = None,
    source: str = "akshare",
) -> list[PriceLimitRecord]:
    """Fetch real-time price limit pool with fallback.

    Fallback chain:
    1. Primary source (akshare EastMoney pools)
    2. EastMoney push2 real-time API

    Parameters
    ----------
    date : str or None
        Date in ``"YYYY-MM-DD"`` format.  Defaults to today.
    source : str
        Primary source (``"akshare"`` or ``"eastmoney"``).

    Returns
    -------
    list[PriceLimitRecord]
    """
    if date is None:
        date = datetime.date.today().isoformat()

    if source == "akshare":
        fetcher = fetch_price_limit_pool_via_akshare
        fallback = fetch_price_limit_via_eastmoney_push2
    else:
        fetcher = fetch_price_limit_via_eastmoney_push2
        fallback = fetch_price_limit_pool_via_akshare

    try:
        records = fetcher(date)
        if records:
            return records
    except Exception:
        logger.debug("Primary price limit source %s failed, trying fallback", source)

    try:
        return fallback(date)
    except Exception:
        return []


def is_at_price_limit_external(
    symbol: str,
    date: str | None = None,
) -> tuple[bool, Optional[str]]:
    """Check if a stock is at its price limit (涨停/跌停) via external pools.

    Uses :func:`fetch_price_limit_pool` and checks whether the symbol appears
    in either the limit-up or limit-down pool.

    Parameters
    ----------
    symbol : str
        Normalized A-share symbol.
    date : str or None
        Date in ``"YYYY-MM-DD"`` format.  Defaults to today.

    Returns
    -------
    (is_limited, direction) : tuple[bool, str | None]
        ``(True, "price_limit_up")`` or ``(True, "price_limit_down")``.
        ``(False, None)`` when not found at limit.
    """
    check_date = date or datetime.date.today().isoformat()
    code = _normalize_code(symbol)

    if not code:
        return False, None

    records = fetch_price_limit_pool(check_date)
    for rec in records:
        if rec.code == code:
            direction = "price_limit_up" if rec.direction == "up" else "price_limit_down"
            return True, direction

    return False, None


# ---------------------------------------------------------------------------
# Convenience: build a lookup set of symbols currently at price limit
# ---------------------------------------------------------------------------


def get_price_limited_symbols(
    date: Optional[str] = None,
    direction: Optional[str] = None,
) -> set[str]:
    """Return a set of symbols currently at price limit.

    Parameters
    ----------
    date : str or None
        Date in ``"YYYY-MM-DD"`` format.  Defaults to today.
    direction : str or None
        ``"up"`` or ``"down"``.  ``None`` returns both directions.

    Returns
    -------
    set[str]
        Set of normalized symbols at price limit.
    """
    records = fetch_price_limit_pool(date)
    result: set[str] = set()
    for rec in records:
        if direction is None or rec.direction == direction:
            result.add(rec.symbol)
    return result
