"""Provider adapters for the A-share data layer.

This package keeps vendor specifics inside adapters and returns normalized raw
payloads (``{"bars": ...}``, ``{"items": ...}``, flat valuation dicts) that the
router can wrap into the stable ``AStockResponse`` schema.
"""

from .base import AStockAdapterBase
from .common import (
    _env,
    _coerce_float,
    _coerce_int,
    _coerce_bool,
    _strip_html,
    _format_timestamp,
    _records_from_payload,
    _ensure_records,
    _filter_by_code,
    _first_non_null,
    _interval_to_tdx_frequency,
    _tencent_code,
    _tencent_side,
    _temporarily_disable_proxies,
    _random_sleep,
    _retry_with_backoff,
    _common_headers,
)
from .registry import LazyAdapterMapping, PROVIDER_ENV_VARS, build_default_adapters

_LAZY_EXPORTS = {
    "AkshareAdapter": ("tradingagents.astock.data_sources.adapters.providers.akshare", "AkshareAdapter"),
    "TencentFinanceAdapter": ("tradingagents.astock.data_sources.adapters.providers.tencent", "TencentFinanceAdapter"),
    "CninfoAdapter": ("tradingagents.astock.data_sources.adapters.providers.cninfo", "CninfoAdapter"),
    "MootdxAdapter": ("tradingagents.astock.data_sources.adapters.providers.mootdx", "MootdxAdapter"),
    "IwencaiAdapter": ("tradingagents.astock.data_sources.adapters.providers.iwencai", "IwencaiAdapter"),
    "QMTAdapter": ("tradingagents.astock.data_sources.adapters.providers.qmt", "QMTAdapter"),
    "BaoStockAdapter": ("tradingagents.astock.data_sources.adapters.providers.baostock", "BaoStockAdapter"),
}


def __getattr__(name: str):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(name)
    from importlib import import_module

    module_name, attr_name = _LAZY_EXPORTS[name]
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value

__all__ = [
    "AStockAdapterBase",
    "AkshareAdapter",
    "TencentFinanceAdapter",
    "CninfoAdapter",
    "MootdxAdapter",
    "IwencaiAdapter",
    "QMTAdapter",
    "BaoStockAdapter",
    "PROVIDER_ENV_VARS",
    "LazyAdapterMapping",
    "build_default_adapters",
    "_env",
    "_coerce_float",
    "_coerce_int",
    "_coerce_bool",
    "_strip_html",
    "_format_timestamp",
    "_records_from_payload",
    "_ensure_records",
    "_filter_by_code",
    "_first_non_null",
    "_interval_to_tdx_frequency",
    "_tencent_code",
    "_tencent_side",
    "_temporarily_disable_proxies",
    "_random_sleep",
    "_retry_with_backoff",
    "_common_headers",
]
