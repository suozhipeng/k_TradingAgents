"""Provider registry and default adapter factory.

The router needs a complete provider key set for deterministic fallback order,
but it should not import and instantiate every vendor SDK at startup. This
module keeps provider discovery separate from provider construction.
"""

from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from importlib import import_module
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
    "akshare": ("tradingagents.astock.data_sources.adapters.providers.akshare", "AkshareAdapter"),
    "mootdx": ("tradingagents.astock.data_sources.adapters.providers.mootdx", "MootdxAdapter"),
    "tdx": ("tradingagents.astock.data_sources.tdx_provider", "TdxProvider"),
    "tencent": ("tradingagents.astock.data_sources.adapters.providers.tencent", "TencentFinanceAdapter"),
    "iwencai": ("tradingagents.astock.data_sources.adapters.providers.iwencai", "IwencaiAdapter"),
    "cninfo": ("tradingagents.astock.data_sources.adapters.providers.cninfo", "CninfoAdapter"),
    "qmt": ("tradingagents.astock.data_sources.adapters.providers.qmt", "QMTAdapter"),
    "baostock": ("tradingagents.astock.data_sources.adapters.providers.baostock", "BaoStockAdapter"),
}


def _load_adapter_factory(source: str) -> type[AStockAdapterBase]:
    """Load a provider class by source id."""
    try:
        module_name, class_name = DEFAULT_ADAPTER_FACTORIES[source]
    except KeyError as exc:
        raise KeyError(f"Unknown A-share adapter source: {source}") from exc
    module = import_module(module_name)
    return getattr(module, class_name)


class LazyAdapterMapping(MutableMapping[str, AStockAdapterBase]):
    """Mapping that instantiates provider adapters only when accessed."""

    def __init__(self, configs: Dict[str, Dict[str, Any]] | None = None) -> None:
        self._configs = {str(k).strip().lower(): dict(v) for k, v in (configs or {}).items()}
        self._instances: Dict[str, AStockAdapterBase] = {}

    def __getitem__(self, key: str) -> AStockAdapterBase:
        source = str(key).strip().lower()
        if source not in DEFAULT_ADAPTER_FACTORIES:
            raise KeyError(source)
        if source not in self._instances:
            factory = _load_adapter_factory(source)
            self._instances[source] = factory(**dict(self._configs.get(source, {})))
        return self._instances[source]

    def __setitem__(self, key: str, value: AStockAdapterBase) -> None:
        source = str(key).strip().lower()
        self._instances[source] = value

    def __delitem__(self, key: str) -> None:
        source = str(key).strip().lower()
        if source in self._instances:
            del self._instances[source]
            return
        if source in DEFAULT_ADAPTER_FACTORIES:
            return
        raise KeyError(source)

    def __iter__(self) -> Iterator[str]:
        yield from DEFAULT_ADAPTER_FACTORIES.keys()
        for source in self._instances:
            if source not in DEFAULT_ADAPTER_FACTORIES:
                yield source

    def __len__(self) -> int:
        return len(set(DEFAULT_ADAPTER_FACTORIES) | set(self._instances))

    def get(self, key: str, default: Any = None) -> AStockAdapterBase | Any:
        try:
            return self[key]
        except KeyError:
            return default


def build_default_adapters(**configs: Any) -> LazyAdapterMapping:
    """Return the default provider adapter mapping.

    The returned object behaves like a mapping but lazily imports and creates
    each adapter on first use.
    """
    return LazyAdapterMapping({str(k).strip().lower(): dict(v) for k, v in configs.items()})
