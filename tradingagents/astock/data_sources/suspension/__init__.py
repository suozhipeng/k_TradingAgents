"""A-share suspension and price-limit facade.

The implementation is split across focused modules, while this package entry
remains the stable integration point for callers and tests.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any, Optional

import pandas as pd

from . import price_limit as _price_limit_backend
from . import suspension as _suspension_backend
from .common import (
    PriceLimitRecord,
    SuspensionRecord,
    _make_symbol,
    _normalize_code,
    _retry,
    get_price_limit_pct,
    get_price_limit_prices,
)
from ..errors import AStockSourceUnavailableError

logger = logging.getLogger(__name__)

fetch_suspension_via_akshare = _suspension_backend.fetch_suspension_via_akshare
fetch_suspension_via_eastmoney = _suspension_backend.fetch_suspension_via_eastmoney
fetch_price_limit_via_eastmoney_push2 = (
    _price_limit_backend.fetch_price_limit_via_eastmoney_push2
)


def fetch_suspension_list(
    date: Optional[str] = None,
    source: str = "akshare",
) -> list[SuspensionRecord]:
    """Fetch daily suspension list from a named backend."""
    source_map: dict[str, Any] = {
        "akshare": fetch_suspension_via_akshare,
        "eastmoney": fetch_suspension_via_eastmoney,
    }
    fetcher = source_map.get(source)
    if fetcher is None:
        raise ValueError(
            f"Unknown suspension source {source!r}. "
            f"Available: {list(source_map)}",
        )
    return fetcher(date)


def is_symbol_suspended_akshare(
    symbol: str,
    date: str | None = None,
) -> tuple[bool, Optional[str]]:
    """Check a single symbol against the akshare suspension list."""
    try:
        check_date = date or datetime.date.today().isoformat()
        records = fetch_suspension_via_akshare(check_date)
        code = _normalize_code(symbol)
        for rec in records:
            if rec.code == code:
                return True, rec.reason or "suspended_akshare"
        return False, None
    except Exception:
        return False, None


def is_symbol_suspended_via_trading_pool(
    symbol: str,
    date: str | None = None,
) -> tuple[bool, Optional[str]]:
    """Infer suspension from active trading pools as a best-effort fallback."""
    if date is None:
        date = datetime.date.today().isoformat()

    code = _normalize_code(symbol)
    if not code:
        return False, None

    try:
        dt = datetime.date.fromisoformat(date)
        if dt.weekday() >= 5:
            return False, None
    except (ValueError, TypeError):
        return False, None

    seen_codes: set[str] = set()
    for pool_fn_name in (
        "stock_zt_pool_em",
        "stock_zt_pool_dtgc_em",
        "stock_zt_pool_strong_em",
    ):
        try:
            import akshare as ak

            pool_fn = getattr(ak, pool_fn_name, None)
            if pool_fn is None:
                continue

            def _fetch_pool(fn=pool_fn, d=date):
                return fn(date=d)

            df = _retry(_fetch_pool, max_attempts=2, base_delay=0.5)
            if df is not None and not df.empty:
                for col in ("code", "代码", "股票代码"):
                    if col in df.columns:
                        for c in df[col].dropna():
                            seen_codes.add(_normalize_code(str(c)))
                        break
        except Exception:
            continue

    if not seen_codes:
        return False, None
    if code not in seen_codes:
        return True, "suspended_trading_pool"
    return False, None


def is_suspended(
    symbol: str,
    source: str = "akshare",
    date: str | None = None,
) -> tuple[bool, Optional[str]]:
    """Check whether a symbol is suspended via the facade fallback chain."""
    check_date = date or datetime.date.today().isoformat()
    sources = ["akshare", "eastmoney"]

    if source in sources:
        sources.remove(source)
        sources.insert(0, source)

    for src in sources:
        try:
            if src == "akshare":
                suspended, reason = is_symbol_suspended_akshare(symbol, check_date)
            else:
                code = _normalize_code(symbol)
                records = fetch_suspension_via_eastmoney(check_date)
                suspended = False
                reason = None
                for rec in records:
                    if rec.code == code:
                        suspended = True
                        reason = rec.reason or "suspended_eastmoney"
                        break
            if suspended:
                return True, reason or f"suspended_{src}"
            return False, None
        except Exception:
            continue

    try:
        if date is None or date == datetime.date.today().isoformat():
            suspended, reason = is_symbol_suspended_via_trading_pool(symbol, check_date)
            if suspended:
                return True, reason
    except Exception:
        pass

    return False, None


def fetch_price_limit_pool_via_akshare(
    date: Optional[str] = None,
) -> list[PriceLimitRecord]:
    """Fetch limit-up and limit-down pools from akshare."""
    if date is None:
        date = datetime.date.today().isoformat()

    records: list[PriceLimitRecord] = []

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
            records.append(
                PriceLimitRecord(
                    symbol=_make_symbol(code),
                    code=code,
                    name=str(row.get("名称", "")) or None,
                    price=float(row["最新价"]) if pd.notna(row.get("最新价")) else None,
                    change_pct=float(row["涨跌幅"]) if pd.notna(row.get("涨跌幅")) else None,
                    direction="up",
                    consecutive=int(row.get("连板数", 0)) if pd.notna(row.get("连板数")) else 0,
                    source="akshare",
                ),
            )

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
            records.append(
                PriceLimitRecord(
                    symbol=_make_symbol(code),
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


def fetch_price_limit_pool(
    date: Optional[str] = None,
    source: str = "akshare",
) -> list[PriceLimitRecord]:
    """Fetch price-limit pool via primary source then fallback."""
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
    """Check if a stock appears in external limit-up/down pools."""
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


def get_price_limited_symbols(
    date: Optional[str] = None,
    direction: Optional[str] = None,
) -> set[str]:
    """Return normalized symbols currently at price limit."""
    records = fetch_price_limit_pool(date)
    result: set[str] = set()
    for rec in records:
        if direction is None or rec.direction == direction:
            result.add(rec.symbol)
    return result

__all__ = [
    "SuspensionRecord",
    "PriceLimitRecord",
    "is_suspended",
    "is_at_price_limit_external",
    "get_price_limited_symbols",
    "get_price_limit_pct",
    "get_price_limit_prices",
    "fetch_suspension_list",
    "fetch_suspension_via_akshare",
    "fetch_suspension_via_eastmoney",
    "is_symbol_suspended_akshare",
    "is_symbol_suspended_via_trading_pool",
    "fetch_price_limit_pool_via_akshare",
    "fetch_price_limit_via_eastmoney_push2",
    "fetch_price_limit_pool",
    "_retry",
    "_normalize_code",
    "_make_symbol",
    "AStockSourceUnavailableError",
]
