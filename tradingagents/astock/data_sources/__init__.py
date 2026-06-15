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
from .router import AStockDataFacade, AStockDataRouter, CAPABILITY_TO_METHOD, DEFAULT_ELIMINATED_SOURCES, DEFAULT_ROUTE_POLICY
from .schema import AStockRequest, AStockResponse, normalize_capability_payload
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
    "AStockDataFacade",
    "AStockDataRouter",
    "CAPABILITY_TO_METHOD",
    "DEFAULT_ELIMINATED_SOURCES",
    "DEFAULT_ROUTE_POLICY",
    "AStockRequest",
    "AStockResponse",
    "normalize_capability_payload",
    "astock_code",
    "normalize_astock_symbol",
    "split_astock_symbol",
]
