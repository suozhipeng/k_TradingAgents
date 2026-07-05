"""Provider registry and default adapter factory."""

from __future__ import annotations

from typing import Any, Dict, Tuple

from .base import AStockAdapterBase


PROVIDER_ENV_VARS: Dict[str, Tuple[str, ...]] = {
    "akshare": ("ASTOCK_AKSHARE_DISABLE_ENV_PROXY", "ASTOCK_AKSHARE_ALLOW_TENCENT_SUPPLEMENT"),
    "tencent": ("ASTOCK_TENCENT_TIMEOUT", "ASTOCK_TENCENT_HEADERS_JSON"),
    "cninfo": (
        "ASTOCK_CNINFO_COOKIE",
        "ASTOCK_CNINFO_CSRF_TOKEN",
        "ASTOCK_CNINFO_USER_AGENT",
        "ASTOCK_CNINFO_TIMEOUT",
        "ASTOCK_CNINFO_HEADERS_JSON",
    ),
    "mootdx": ("ASTOCK_MOOTDX_HOST", "ASTOCK_MOOTDX_PORT", "ASTOCK_MOOTDX_TIMEOUT", "ASTOCK_MOOTDX_MARKET"),
    "tdx": ("ASTOCK_TDX_HOST", "ASTOCK_TDX_PORT", "ASTOCK_TDX_TIMEOUT", "ASTOCK_TDX_BACKUP_HOSTS", "ASTOCK_TDX_MULTICAST"),
    "iwencai": (
        "ASTOCK_IWENCAI_COOKIE",
        "ASTOCK_IWENCAI_USER_AGENT",
        "ASTOCK_IWENCAI_RETRY",
        "ASTOCK_IWENCAI_SLEEP",
        "ASTOCK_IWENCAI_TIMEOUT",
        "ASTOCK_IWENCAI_PER_PAGE",
    ),
    "qmt": tuple(),
    "baostock": tuple(),
}


DEFAULT_ADAPTER_FACTORIES = {
    "akshare": None,  # imported lazily
    "mootdx": None,
    "tdx": None,
    "tencent": None,
    "iwencai": None,
    "cninfo": None,
    "qmt": None,
    "baostock": None,
}


def build_default_adapters(**configs: Any) -> Dict[str, AStockAdapterBase]:
    """Create the default provider adapters with optional per-source config."""
    from .providers.akshare import AkshareAdapter
    from .providers.tencent import TencentFinanceAdapter
    from .providers.cninfo import CninfoAdapter
    from .providers.mootdx import MootdxAdapter
    from .providers.iwencai import IwencaiAdapter
    from .providers.qmt import QMTAdapter
    from .providers.baostock import BaoStockAdapter
    from .tdx_provider import TdxProvider

    factories = {
        "akshare": AkshareAdapter,
        "mootdx": MootdxAdapter,
        "tdx": TdxProvider,
        "tencent": TencentFinanceAdapter,
        "iwencai": IwencaiAdapter,
        "cninfo": CninfoAdapter,
        "qmt": QMTAdapter,
        "baostock": BaoStockAdapter,
    }

    adapters: Dict[str, AStockAdapterBase] = {}
    for name, factory in factories.items():
        adapters[name] = factory(**dict(configs.get(name, {})))
    return adapters
