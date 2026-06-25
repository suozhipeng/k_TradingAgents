"""Unified A-share data sources.

This package exposes a stable, provider-agnostic interface for the five-layer
A-share data stack: market, research, news, fundamentals, and announcements.
"""

from __future__ import annotations

from .adapters import (
    AStockAdapterBase,
    AkshareAdapter,
    BaoStockAdapter,
    CninfoAdapter,
    IwencaiAdapter,
    MootdxAdapter,
    PROVIDER_ENV_VARS,
    QMTAdapter,
    TencentFinanceAdapter,
    build_default_adapters,
)
from .cache import AStockCachePolicy, FileAStockCache, InMemoryAStockCache
from .errors import AStockDataError, AStockNoDataError, AStockRouteNote, AStockSchemaError, AStockSourceUnavailableError
from .quality import DataQualityTag, FreshnessInfo, DataQualityMetadata
from .adjustment import (
    fetch_adjust_factors,
    fetch_adjust_via_eastmoney,
    fetch_adjust_via_akshare_hist,
    adjust_series,
    adjust_bars,
    _adjust_factor_for_date,
    _set_duckdb,
    clear_cache,
)
from .router import AStockDataFacade, AStockDataRouter, CAPABILITY_TO_METHOD, DEFAULT_ELIMINATED_SOURCES, DEFAULT_ROUTE_POLICY
from .schema import AStockRequest, AStockResponse, normalize_capability_payload
from .suspension import (
    PriceLimitRecord,
    SuspensionRecord,
    fetch_price_limit_pool,
    fetch_price_limit_pool_via_akshare,
    fetch_price_limit_via_eastmoney_push2,
    fetch_suspension_list,
    fetch_suspension_via_akshare,
    fetch_suspension_via_eastmoney,
    get_price_limit_pct,
    get_price_limit_prices,
    get_price_limited_symbols,
    is_at_price_limit_external,
    is_suspended,
    is_symbol_suspended_akshare,
    is_symbol_suspended_via_trading_pool,
)
from .symbols import astock_code, normalize_astock_symbol, split_astock_symbol

__all__ = [
    "AStockAdapterBase",
    "AkshareAdapter",
    "CninfoAdapter",
    "IwencaiAdapter",
    "MootdxAdapter",
    "PROVIDER_ENV_VARS",
    "QMTAdapter",
    "TencentFinanceAdapter",
    "build_default_adapters",
    "AStockCachePolicy",
    "FileAStockCache",
    "InMemoryAStockCache",
    "AStockDataError",
    "AStockNoDataError",
    "AStockRouteNote",
    "AStockSchemaError",
    "AStockSourceUnavailableError",
    "DataQualityTag",
    "FreshnessInfo",
    "DataQualityMetadata",
    "AStockDataFacade",
    "AStockDataRouter",
    "CAPABILITY_TO_METHOD",
    "DEFAULT_ELIMINATED_SOURCES",
    "DEFAULT_ROUTE_POLICY",
    "AStockRequest",
    "AStockResponse",
    "normalize_capability_payload",
    "PriceLimitRecord",
    "SuspensionRecord",
    "fetch_price_limit_pool",
    "fetch_price_limit_pool_via_akshare",
    "fetch_price_limit_via_eastmoney_push2",
    "fetch_suspension_list",
    "fetch_suspension_via_akshare",
    "fetch_suspension_via_eastmoney",
    "get_price_limit_pct",
    "get_price_limit_prices",
    "get_price_limited_symbols",
    "is_at_price_limit_external",
    "is_suspended",
    "is_symbol_suspended_akshare",
    "is_symbol_suspended_via_trading_pool",
    "fetch_adjust_factors",
    "fetch_adjust_via_eastmoney",
    "fetch_adjust_via_akshare_hist",
    "adjust_series",
    "adjust_bars",
    "astock_code",
    "normalize_astock_symbol",
    "split_astock_symbol",
]
