"""
A-share suspension (停复牌) and price limit (涨跌停) data sources.

Provides:
- SuspensionRecord schema for daily suspension/resumption events
- PriceLimitRecord schema for stocks at daily price limits
- fetch_suspension_list() via multiple backends (akshare, EastMoney)
- fetch_price_limit_pool() for real-time 涨停/跌停 data (akshare → EastMoney)
- get_price_limit_pct() — per-stock limit percentage (10% normal, 5% ST/*ST)
- is_suspended_today() — real-time suspension check
- is_at_price_limit_external() — external price limit check via live pools

API resilience: all external calls use retry with exponential backoff.
"""

from .common import SuspensionRecord, PriceLimitRecord, _retry, _normalize_code, _make_symbol, get_price_limit_pct, get_price_limit_prices
from .suspension import (
    is_suspended,
    fetch_suspension_list,
    fetch_suspension_via_akshare,
    fetch_suspension_via_eastmoney,
    is_symbol_suspended_akshare,
    is_symbol_suspended_via_trading_pool,
)
from .price_limit import (
    is_at_price_limit_external,
    get_price_limited_symbols,
    fetch_price_limit_pool_via_akshare,
    fetch_price_limit_via_eastmoney_push2,
    fetch_price_limit_pool,
)

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
]
