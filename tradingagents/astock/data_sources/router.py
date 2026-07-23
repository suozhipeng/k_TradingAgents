"""V1.7 Router — refactored fetch facade.

Keeps the fetch methods needed by KlineLoader and existing routes,
but removes old routing/ordering/cache/quality logic.
The V1.7 DataFacade (router_v17.py) is the new entry point for capability probing.
"""

from __future__ import annotations

import logging
from typing import Any

from .adapters.registry import build_default_adapters
from .symbols import normalize_astock_symbol

logger = logging.getLogger(__name__)

# DEPRECATED — V1.7 uses config/provider_policy.yaml instead of this dict
DEFAULT_ELIMINATED_SOURCES = frozenset()
DEFAULT_ROUTE_POLICY: dict[str, tuple[str, ...]] = {}
CAPABILITY_TO_METHOD: dict[str, str] = {}


class AStockDataFacade:
    """Data fetch facade — delegates to configured adapters.

    DEPRECATED: New code should use DataFacade (router_v17.py) + Canonical Store.
    Kept alive for KlineLoader and legacy route fallbacks.
    """

    def __init__(self) -> None:
        self._adapters = build_default_adapters()
        self._store = None
        logger.warning("AStockDataFacade (old Router) instantiated — consider migrating to router_v17.DataFacade")

    def set_store(self, store: Any) -> None:
        self._store = store

    def _fetch(self, method: str, symbol: str, **kwargs: Any):
        for name, adapter in self._adapters.items():
            if hasattr(adapter, method) and callable(getattr(adapter, method, None)):
                try:
                    return getattr(adapter, method)(symbol, **kwargs)
                except Exception as exc:
                    logger.debug("adapter %s %s failed: %s", name, method, exc)
        logger.warning("no adapter found for %s(%s)", method, symbol)
        return None

    def get_kline(self, symbol: str, **kwargs: Any) -> Any:
        return self._fetch("get_kline", symbol, **kwargs)

    def get_valuation(self, symbol: str, **kwargs: Any) -> Any:
        return self._fetch("get_valuation", symbol, **kwargs)

    def get_order_book(self, symbol: str, **kwargs: Any) -> Any:
        return self._fetch("get_order_book", symbol, **kwargs)

    def get_trade_tape(self, symbol: str, **kwargs: Any) -> Any:
        return self._fetch("get_trade_tape", symbol, **kwargs)

    def get_pe_pb(self, symbol: str, **kwargs: Any) -> Any:
        return self._fetch("get_pe_pb", symbol, **kwargs)

    def get_market_cap(self, symbol: str, **kwargs: Any) -> Any:
        return self._fetch("get_market_cap", symbol, **kwargs)

    def get_turnover_rate(self, symbol: str, **kwargs: Any) -> Any:
        return self._fetch("get_turnover_rate", symbol, **kwargs)

    def get_research_list(self, symbol: str, **kwargs: Any) -> Any:
        return self._fetch("get_research_list", symbol, **kwargs)

    def get_institution_expectation(self, symbol: str, **kwargs: Any) -> Any:
        return self._fetch("get_institution_expectation", symbol, **kwargs)

    def get_stock_news(self, symbol: str, **kwargs: Any) -> Any:
        return self._fetch("get_stock_news", symbol, **kwargs)

    def get_flash_news(self, symbol: str, **kwargs: Any) -> Any:
        return self._fetch("get_flash_news", symbol, **kwargs)

    def get_global_news(self, symbol: str, **kwargs: Any) -> Any:
        return self._fetch("get_global_news", symbol, **kwargs)

    def get_quarterly_financials(self, symbol: str, **kwargs: Any) -> Any:
        return self._fetch("get_quarterly_financials", symbol, **kwargs)

    def get_f10(self, symbol: str, **kwargs: Any) -> Any:
        return self._fetch("get_f10", symbol, **kwargs)

    def get_fundamentals(self, symbol: str, **kwargs: Any) -> Any:
        return self._fetch("get_fundamentals", symbol, **kwargs)

    def get_announcement_full(self, symbol: str, **kwargs: Any) -> Any:
        return self._fetch("get_announcement_full", symbol, **kwargs)

    def get_announcement_summary(self, symbol: str, **kwargs: Any) -> Any:
        return self._fetch("get_announcement_summary", symbol, **kwargs)

    def get_price_limit_status(self, symbol: str, **kwargs: Any) -> Any:
        return self._fetch("get_price_limit_status", symbol, **kwargs)

    def get_market_summary(self, symbol: str = "000001.SH", **kwargs: Any) -> Any:
        return self._fetch("get_market_summary", symbol, **kwargs)

    def get_sector_data(self, symbol: str = "all", **kwargs: Any) -> Any:
        return self._fetch("get_sector_data", symbol, **kwargs)
