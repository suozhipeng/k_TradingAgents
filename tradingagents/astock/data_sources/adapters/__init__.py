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
from .registry import PROVIDER_ENV_VARS, build_default_adapters
from .providers.akshare import AkshareAdapter
from .providers.tencent import TencentFinanceAdapter
from .providers.cninfo import CninfoAdapter
from .providers.mootdx import MootdxAdapter
from .providers.iwencai import IwencaiAdapter
from .providers.qmt import QMTAdapter
from .providers.baostock import BaoStockAdapter

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
