"""Unified A-share data sources.

This package exposes a stable, provider-agnostic interface for the five-layer
A-share data stack while keeping concrete providers behind lazy exports.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


_LAZY_EXPORTS = {
    "AStockAdapterBase": ("tradingagents.astock.data_sources.adapters", "AStockAdapterBase"),
    "AkshareAdapter": ("tradingagents.astock.data_sources.adapters", "AkshareAdapter"),
    "BaoStockAdapter": ("tradingagents.astock.data_sources.adapters", "BaoStockAdapter"),
    "CninfoAdapter": ("tradingagents.astock.data_sources.adapters", "CninfoAdapter"),
    "IwencaiAdapter": ("tradingagents.astock.data_sources.adapters", "IwencaiAdapter"),
    "MootdxAdapter": ("tradingagents.astock.data_sources.adapters", "MootdxAdapter"),
    "PROVIDER_ENV_VARS": ("tradingagents.astock.data_sources.adapters", "PROVIDER_ENV_VARS"),
    "QMTAdapter": ("tradingagents.astock.data_sources.adapters", "QMTAdapter"),
    "TencentFinanceAdapter": ("tradingagents.astock.data_sources.adapters", "TencentFinanceAdapter"),
    "build_default_adapters": ("tradingagents.astock.data_sources.adapters.registry", "build_default_adapters"),
    "TdxProvider": ("tradingagents.astock.data_sources.tdx_provider", "TdxProvider"),
    "TdxVipdocReader": ("tradingagents.astock.data_sources.tdx_vipdoc", "TdxVipdocReader"),
    "create_vipdoc_reader": ("tradingagents.astock.data_sources.tdx_vipdoc", "create_vipdoc_reader"),
    "TdxCache": ("tradingagents.astock.data_sources.tdx_cache", "TdxCache"),
    "AStockCachePolicy": ("tradingagents.astock.data_sources.cache", "AStockCachePolicy"),
    "FileAStockCache": ("tradingagents.astock.data_sources.cache", "FileAStockCache"),
    "InMemoryAStockCache": ("tradingagents.astock.data_sources.cache", "InMemoryAStockCache"),
    "AStockDataError": ("tradingagents.astock.data_sources.errors", "AStockDataError"),
    "AStockNoDataError": ("tradingagents.astock.data_sources.errors", "AStockNoDataError"),
    "AStockRouteNote": ("tradingagents.astock.data_sources.errors", "AStockRouteNote"),
    "AStockSchemaError": ("tradingagents.astock.data_sources.errors", "AStockSchemaError"),
    "AStockSourceUnavailableError": ("tradingagents.astock.data_sources.errors", "AStockSourceUnavailableError"),
    "DataQualityTag": ("tradingagents.astock.data_sources.quality", "DataQualityTag"),
    "FreshnessInfo": ("tradingagents.astock.data_sources.quality", "FreshnessInfo"),
    "DataQualityMetadata": ("tradingagents.astock.data_sources.quality", "DataQualityMetadata"),
    "DataQualityBanner": ("tradingagents.astock.data_sources.quality", "DataQualityBanner"),
    "AStockDataFacade": ("tradingagents.astock.data_sources.router", "AStockDataFacade"),
    "AStockDataRouter": ("tradingagents.astock.data_sources.router", "AStockDataRouter"),
    "CAPABILITY_TO_METHOD": ("tradingagents.astock.data_sources.router", "CAPABILITY_TO_METHOD"),
    "DEFAULT_ELIMINATED_SOURCES": ("tradingagents.astock.data_sources.router", "DEFAULT_ELIMINATED_SOURCES"),
    "DEFAULT_ROUTE_POLICY": ("tradingagents.astock.data_sources.router", "DEFAULT_ROUTE_POLICY"),
    "AStockRequest": ("tradingagents.astock.data_sources.schema", "AStockRequest"),
    "AStockResponse": ("tradingagents.astock.data_sources.schema", "AStockResponse"),
    "normalize_capability_payload": ("tradingagents.astock.data_sources.schema", "normalize_capability_payload"),
    "PriceLimitRecord": ("tradingagents.astock.data_sources.suspension", "PriceLimitRecord"),
    "SuspensionRecord": ("tradingagents.astock.data_sources.suspension", "SuspensionRecord"),
    "fetch_price_limit_pool": ("tradingagents.astock.data_sources.suspension", "fetch_price_limit_pool"),
    "fetch_price_limit_pool_via_akshare": ("tradingagents.astock.data_sources.suspension", "fetch_price_limit_pool_via_akshare"),
    "fetch_price_limit_via_eastmoney_push2": ("tradingagents.astock.data_sources.suspension", "fetch_price_limit_via_eastmoney_push2"),
    "fetch_suspension_list": ("tradingagents.astock.data_sources.suspension", "fetch_suspension_list"),
    "fetch_suspension_via_akshare": ("tradingagents.astock.data_sources.suspension", "fetch_suspension_via_akshare"),
    "fetch_suspension_via_eastmoney": ("tradingagents.astock.data_sources.suspension", "fetch_suspension_via_eastmoney"),
    "get_price_limit_pct": ("tradingagents.astock.data_sources.suspension", "get_price_limit_pct"),
    "get_price_limit_prices": ("tradingagents.astock.data_sources.suspension", "get_price_limit_prices"),
    "get_price_limited_symbols": ("tradingagents.astock.data_sources.suspension", "get_price_limited_symbols"),
    "is_at_price_limit_external": ("tradingagents.astock.data_sources.suspension", "is_at_price_limit_external"),
    "is_suspended": ("tradingagents.astock.data_sources.suspension", "is_suspended"),
    "is_symbol_suspended_akshare": ("tradingagents.astock.data_sources.suspension", "is_symbol_suspended_akshare"),
    "is_symbol_suspended_via_trading_pool": ("tradingagents.astock.data_sources.suspension", "is_symbol_suspended_via_trading_pool"),
    "fetch_adjust_factors": ("tradingagents.astock.data_sources.adjustment", "fetch_adjust_factors"),
    "fetch_adjust_via_eastmoney": ("tradingagents.astock.data_sources.adjustment", "fetch_adjust_via_eastmoney"),
    "fetch_adjust_via_akshare_hist": ("tradingagents.astock.data_sources.adjustment", "fetch_adjust_via_akshare_hist"),
    "adjust_series": ("tradingagents.astock.data_sources.adjustment", "adjust_series"),
    "adjust_bars": ("tradingagents.astock.data_sources.adjustment", "adjust_bars"),
    "_adjust_factor_for_date": ("tradingagents.astock.data_sources.adjustment", "_adjust_factor_for_date"),
    "_set_duckdb": ("tradingagents.astock.data_sources.adjustment", "_set_duckdb"),
    "clear_cache": ("tradingagents.astock.data_sources.adjustment", "clear_cache"),
    "astock_code": ("tradingagents.astock.data_sources.symbols", "astock_code"),
    "normalize_astock_symbol": ("tradingagents.astock.data_sources.symbols", "normalize_astock_symbol"),
    "split_astock_symbol": ("tradingagents.astock.data_sources.symbols", "split_astock_symbol"),
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(name)
    module_name, attr_name = _LAZY_EXPORTS[name]
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
