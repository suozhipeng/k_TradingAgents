"""Provider adapters for the A-share data layer."""

from __future__ import annotations

import importlib
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from .errors import AStockNoDataError, AStockSourceUnavailableError
from .schema import AStockRequest
from .symbols import astock_code


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


class _LazyModuleAdapter(AStockAdapterBase):
    module_name = ""
    module_alias = ""

    def _load_module(self):
        try:
            return importlib.import_module(self.module_name)
        except Exception as exc:  # pragma: no cover - depends on local env
            raise AStockSourceUnavailableError(self.name, "module import failed: {0}".format(exc), capability=None)


class AkshareAdapter(AStockAdapterBase):
    name = "akshare"

    def _load(self):
        try:
            return importlib.import_module("akshare")
        except Exception as exc:  # pragma: no cover - optional dependency
            raise AStockSourceUnavailableError(self.name, "akshare not installed or import failed: {0}".format(exc))

    def _call_first(self, candidates: Sequence[str], *args: Any, **kwargs: Any):
        module = self._load()
        last_error: Optional[Exception] = None
        for func_name in candidates:
            func = getattr(module, func_name, None)
            if func is None:
                continue
            try:
                return func(*args, **kwargs)
            except TypeError as exc:
                last_error = exc
                continue
        if last_error is not None:
            raise AStockSourceUnavailableError(self.name, "akshare signature mismatch: {0}".format(last_error))
        raise AStockSourceUnavailableError(self.name, "akshare function not available: {0}".format(", ".join(candidates)))

    def _code(self, request: AStockRequest) -> str:
        return astock_code(request.symbol)

    def get_kline(self, request: AStockRequest):
        period_map = {
            "1m": "1",
            "5m": "5",
            "15m": "15",
            "30m": "30",
            "60m": "60",
            "1d": "daily",
            "daily": "daily",
            "day": "daily",
            "weekly": "weekly",
            "1w": "weekly",
            "monthly": "monthly",
            "1mo": "monthly",
        }
        period = period_map.get((request.interval or "1d").lower(), request.interval or "daily")
        kwargs = {
            "symbol": self._code(request),
            "period": period,
            "adjust": self.config.get("adjust", "qfq"),
        }
        if request.start_date:
            kwargs["start_date"] = request.start_date.replace("-", "")
        if request.end_date:
            kwargs["end_date"] = request.end_date.replace("-", "")
        return self._call_first(("stock_zh_a_hist", "stock_zh_a_hist_tx", "stock_zh_a_hist_sina"), **kwargs)

    def get_order_book(self, request: AStockRequest):
        return self._call_first(("stock_bid_ask_em", "stock_zh_a_spot_em"), symbol=self._code(request))

    def get_trade_tape(self, request: AStockRequest):
        return self._call_first(("stock_intraday_em", "stock_zh_a_tick_tx"), symbol=self._code(request))

    def get_valuation(self, request: AStockRequest):
        return self._call_first(("stock_a_indicator_lg", "stock_financial_analysis_indicator", "stock_individual_info_em"), symbol=self._code(request))

    def get_stock_news(self, request: AStockRequest):
        return self._call_first(("stock_news_em", "stock_news_cctv"), symbol=self._code(request))

    def get_flash_news(self, request: AStockRequest):
        return self._call_first(("stock_news_em", "stock_news_cctv"), symbol=self._code(request))

    def get_global_news(self, request: AStockRequest):
        return self._call_first(("news_cctv", "news_world_em", "stock_news_em"), symbol=self._code(request))

    def get_research_list(self, request: AStockRequest):
        return self._call_first(("stock_research_report_em", "stock_research_report"), symbol=self._code(request))

    def download_research_pdf(self, request: AStockRequest):
        return self._call_first(("stock_research_report_em", "stock_research_report"), symbol=self._code(request))

    def get_institution_expectation(self, request: AStockRequest):
        return self._call_first(("stock_profit_forecast_em", "stock_a_lg_indicator"), symbol=self._code(request))

    def search_research(self, request: AStockRequest):
        return self._call_first(("stock_research_report_em", "stock_profit_forecast_em"), symbol=self._code(request), keyword=request.query or request.raw_symbol)

    def get_quarterly_financials(self, request: AStockRequest):
        return self._call_first(("stock_financial_report_sina", "stock_financial_analysis_indicator"), symbol=self._code(request))

    def get_f10(self, request: AStockRequest):
        return self._call_first(("stock_fundamental_analysis_indicator", "stock_individual_info_em", "stock_financial_analysis_indicator"), symbol=self._code(request))

    def get_fundamentals(self, request: AStockRequest):
        return self._call_first(("stock_financial_analysis_indicator", "stock_a_indicator_lg", "stock_financial_report_sina"), symbol=self._code(request))

    def get_announcement_full(self, request: AStockRequest):
        return self._call_first(("stock_notice_report", "stock_notice_report_em"), symbol=self._code(request))

    def get_announcement_summary(self, request: AStockRequest):
        return self._call_first(("stock_notice_report", "stock_notice_report_em"), symbol=self._code(request))


class MootdxAdapter(AStockAdapterBase):
    """TODO: wire a verified mootdx client/bridge for local TDX data."""

    name = "mootdx"

    def _hint(self, request: AStockRequest, method: str):
        endpoint = self.config.get("endpoint")
        if endpoint:
            return self._unavailable(request, "mootdx bridge endpoint not wired: {0}".format(endpoint))
        return self._unavailable(request, "mootdx bridge not configured for {0}".format(method))

    def get_kline(self, request: AStockRequest):
        return self._hint(request, "get_kline")

    def get_order_book(self, request: AStockRequest):
        return self._hint(request, "get_order_book")

    def get_trade_tape(self, request: AStockRequest):
        return self._hint(request, "get_trade_tape")

    def get_f10(self, request: AStockRequest):
        return self._hint(request, "get_f10")

    def get_announcement_full(self, request: AStockRequest):
        return self._hint(request, "get_announcement_full")

    def get_announcement_summary(self, request: AStockRequest):
        return self._hint(request, "get_announcement_summary")


class TencentFinanceAdapter(AStockAdapterBase):
    """TODO: wire Tencent Finance HTTP endpoints and response parsers."""

    name = "tencent"

    def _hint(self, request: AStockRequest, method: str):
        return self._unavailable(request, "Tencent Finance source not configured for {0}".format(method))

    def get_kline(self, request: AStockRequest):
        return self._hint(request, "get_kline")

    def get_order_book(self, request: AStockRequest):
        return self._hint(request, "get_order_book")

    def get_trade_tape(self, request: AStockRequest):
        return self._hint(request, "get_trade_tape")

    def get_stock_news(self, request: AStockRequest):
        return self._hint(request, "get_stock_news")

    def get_flash_news(self, request: AStockRequest):
        return self._hint(request, "get_flash_news")


class IwencaiAdapter(AStockAdapterBase):
    """TODO: wire iwencai search/research endpoints with explicit config."""

    name = "iwencai"

    def _hint(self, request: AStockRequest, method: str):
        return self._unavailable(request, "iwencai source not configured for {0}".format(method))

    def get_research_list(self, request: AStockRequest):
        return self._hint(request, "get_research_list")

    def download_research_pdf(self, request: AStockRequest):
        return self._hint(request, "download_research_pdf")

    def get_institution_expectation(self, request: AStockRequest):
        return self._hint(request, "get_institution_expectation")

    def search_research(self, request: AStockRequest):
        return self._hint(request, "search_research")


class CninfoAdapter(AStockAdapterBase):
    """TODO: wire cninfo announcement search/download endpoints."""

    name = "cninfo"

    def _hint(self, request: AStockRequest, method: str):
        return self._unavailable(request, "cninfo source not configured for {0}".format(method))

    def get_announcement_full(self, request: AStockRequest):
        return self._hint(request, "get_announcement_full")

    def get_announcement_summary(self, request: AStockRequest):
        return self._hint(request, "get_announcement_summary")


class QMTAdapter(AStockAdapterBase):
    """TODO: keep QMT as a read-only bridge until execution is explicitly added."""

    name = "qmt"

    def _hint(self, request: AStockRequest, method: str):
        return self._unavailable(request, "QMT bridge is reserved for read-only/bridge use in this task: {0}".format(method))

    def get_kline(self, request: AStockRequest):
        return self._hint(request, "get_kline")

    def get_order_book(self, request: AStockRequest):
        return self._hint(request, "get_order_book")

    def get_trade_tape(self, request: AStockRequest):
        return self._hint(request, "get_trade_tape")

    def get_valuation(self, request: AStockRequest):
        return self._hint(request, "get_valuation")

    def get_fundamentals(self, request: AStockRequest):
        return self._hint(request, "get_fundamentals")


DEFAULT_ADAPTER_FACTORIES = {
    "akshare": AkshareAdapter,
    "mootdx": MootdxAdapter,
    "tencent": TencentFinanceAdapter,
    "iwencai": IwencaiAdapter,
    "cninfo": CninfoAdapter,
    "qmt": QMTAdapter,
}


def build_default_adapters(**configs: Any) -> Dict[str, AStockAdapterBase]:
    """Create the default provider adapters with optional per-source config."""
    adapters: Dict[str, AStockAdapterBase] = {}
    for name, factory in DEFAULT_ADAPTER_FACTORIES.items():
        adapters[name] = factory(**dict(configs.get(name, {})))
    return adapters
