"""Base adapter for A-share data sources."""

from __future__ import annotations

from typing import Any

from ..errors import AStockSourceUnavailableError
from ..schema import AStockRequest


class AStockAdapterBase(object):
    """Base adapter: concrete providers override the capability methods."""

    name = "base"

    def __init__(self, **config: Any):
        self.config = dict(config)

    def _unavailable(self, request: AStockRequest, detail: str = ""):
        raise AStockSourceUnavailableError(self.name, detail or "adapter not implemented", capability=request.capability)

    def get_kline(self, request: AStockRequest):
        return self._unavailable(request, "historical kline endpoint not implemented")

    def get_order_book(self, request: AStockRequest):
        return self._unavailable(request, "order book endpoint not implemented")

    def get_trade_tape(self, request: AStockRequest):
        return self._unavailable(request, "trade tape endpoint not implemented")

    def get_valuation(self, request: AStockRequest):
        return self._unavailable(request, "valuation endpoint not implemented")

    def get_research_list(self, request: AStockRequest):
        return self._unavailable(request, "research list endpoint not implemented")

    def download_research_pdf(self, request: AStockRequest):
        return self._unavailable(request, "research PDF endpoint not implemented")

    def get_institution_expectation(self, request: AStockRequest):
        return self._unavailable(request, "institution expectation endpoint not implemented")

    def search_research(self, request: AStockRequest):
        return self._unavailable(request, "semantic search endpoint not implemented")

    def get_stock_news(self, request: AStockRequest):
        return self._unavailable(request, "stock news endpoint not implemented")

    def get_flash_news(self, request: AStockRequest):
        return self._unavailable(request, "flash news endpoint not implemented")

    def get_global_news(self, request: AStockRequest):
        return self._unavailable(request, "global news endpoint not implemented")

    def get_quarterly_financials(self, request: AStockRequest):
        return self._unavailable(request, "quarterly financial endpoint not implemented")

    def get_f10(self, request: AStockRequest):
        return self._unavailable(request, "F10 endpoint not implemented")

    def get_fundamentals(self, request: AStockRequest):
        return self._unavailable(request, "fundamentals endpoint not implemented")

    def get_announcement_full(self, request: AStockRequest):
        return self._unavailable(request, "announcement endpoint not implemented")

    def get_announcement_summary(self, request: AStockRequest):
        return self._unavailable(request, "announcement summary endpoint not implemented")

    def get_sector_data(self, request: AStockRequest):
        return self._unavailable(request, "sector data endpoint not implemented")
