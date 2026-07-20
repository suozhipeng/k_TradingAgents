"""Unified router for A-share data sources.

The router owns symbol normalization, source ordering, fallback semantics,
cache lookups, and unified response/error handling. Upper layers should only
call the router/facade, never vendor SDKs directly.
"""

from __future__ import annotations

import logging

from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

from .adapters.registry import build_default_adapters
from .cache import FileAStockCache, InMemoryAStockCache
from .errors import AStockDataError, AStockNoDataError, AStockSourceUnavailableError
from .quality import DataQualityTag
from .request_governor import ProviderRequestGovernor, get_provider_request_governor
from .schema import AStockRequest, AStockResponse, normalize_capability_payload
from .symbols import normalize_astock_symbol
logger = logging.getLogger(__name__)


DEFAULT_ELIMINATED_SOURCES = frozenset(("tushare", "ashare"))

DEFAULT_ROUTE_POLICY = {
    # 行情层
    # mootdx is the fastest source for SH-listed stocks.  Akshare covers SZ/BJ
    # stocks where mootdx returns garbled data.  Baostock is a last resort
    # because its synchronous login() can block for 20+ seconds.
    "kline": ("mootdx", "akshare", "qmt", "tdx", "tencent", "baostock"),
    "order_book": ("mootdx", "tencent", "qmt", "tdx"),
    "trade_tape": ("mootdx", "tencent", "qmt", "tdx"),
    "valuation": ("tencent", "akshare", "mootdx"),
    "pe_pb": ("tencent", "akshare", "mootdx"),
    "market_cap": ("tencent", "akshare", "mootdx"),
    "turnover_rate": ("tencent", "akshare", "mootdx"),
    # 研报层
    "research_list": ("iwencai", "akshare"),
    "download_research_pdf": ("iwencai", "akshare"),
    "institution_expectation": ("iwencai", "akshare", "mootdx"),
    "search_research": ("iwencai", "akshare"),
    # 新闻层
    "stock_news": ("akshare", "tencent"),
    "flash_news": ("akshare", "tencent"),
    "global_news": ("akshare", "tencent"),
    # 涨跌停层
    "price_limit": ("akshare", "eastmoney"),
    # 基础数据层
    "quarterly_financials": ("akshare", "mootdx"),
    "f10": ("mootdx", "akshare"),
    "fundamentals": ("akshare", "mootdx"),
    # 公告层
    "announcement_full": ("cninfo", "mootdx"),
    "announcement_summary": ("cninfo", "mootdx"),
    # 大盘/指数层
    "market_summary": ("tencent", "akshare"),
    # 板块层
    "sector": ("akshare",),
}

CAPABILITY_TO_METHOD = {
    "kline": "get_kline",
    "order_book": "get_order_book",
    "trade_tape": "get_trade_tape",
    "valuation": "get_valuation",
    "pe_pb": "get_valuation",
    "market_cap": "get_valuation",
    "turnover_rate": "get_valuation",
    "research_list": "get_research_list",
    "download_research_pdf": "download_research_pdf",
    "institution_expectation": "get_institution_expectation",
    "search_research": "search_research",
    "stock_news": "get_stock_news",
    "flash_news": "get_flash_news",
    "global_news": "get_global_news",
    "price_limit": "get_price_limit_status",
    "quarterly_financials": "get_quarterly_financials",
    "f10": "get_f10",
    "fundamentals": "get_fundamentals",
    "announcement_full": "get_announcement_full",
    "announcement_summary": "get_announcement_summary",
    "market_summary": "get_market_summary",
    "sector": "get_sector_data",
}

HISTORY_CAPABILITIES = frozenset(("kline",))
SNAPSHOT_CAPABILITIES = frozenset(("order_book", "trade_tape", "valuation", "pe_pb", "market_cap", "turnover_rate"))
SUMMARY_CAPABILITIES = frozenset(tuple(CAPABILITY_TO_METHOD.keys()) ) - HISTORY_CAPABILITIES - SNAPSHOT_CAPABILITIES


def _normalize_source_id(source: Optional[str]) -> Optional[str]:
    if source is None:
        return None
    return str(source).strip().lower()


def _dedupe_sources(sources: Iterable[str]) -> Tuple[str, ...]:
    seen = set()
    ordered: List[str] = []
    for source in sources:
        normalized = _normalize_source_id(source)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


class AStockDataRouter(object):
    """Source router with unified fallback and cache semantics."""

    def __init__(
        self,
        adapters: Optional[Mapping[str, Any]] = None,
        cache: Optional[Any] = None,
        route_policy: Optional[Mapping[str, Sequence[str]]] = None,
        eliminated_sources: Optional[Iterable[str]] = None,
        default_adapter_configs: Optional[Mapping[str, Dict[str, Any]]] = None,
        request_governor: Optional[ProviderRequestGovernor] = None,
    ):
        if adapters is None:
            adapter_configs = dict(default_adapter_configs or {})
            adapters = build_default_adapters(**adapter_configs)
            self.adapters = adapters
        else:
            self.adapters: Mapping[str, Any] = { _normalize_source_id(name): adapter for name, adapter in adapters.items() }
        self.cache = cache or InMemoryAStockCache()
        self.route_policy = dict(route_policy or DEFAULT_ROUTE_POLICY)
        self.eliminated_sources = frozenset(_normalize_source_id(source) for source in (eliminated_sources or DEFAULT_ELIMINATED_SOURCES))
        # A router is shared by the API process; keep the governor on it so
        # concurrent jobs use the same provider budget.
        self.request_governor = request_governor or get_provider_request_governor()

    def _request(self, capability: str, symbol: str, **kwargs: Any) -> AStockRequest:
        normalized = normalize_astock_symbol(symbol)
        fields = kwargs.pop("fields", ())
        if fields is None:
            fields = ()
        if isinstance(fields, str):
            fields = (fields,)
        extras = dict(kwargs.pop("extras", {}))
        extras.update(kwargs)
        return AStockRequest(
            capability=capability,
            raw_symbol=symbol,
            symbol=normalized,
            start_date=extras.pop("start_date", None),
            end_date=extras.pop("end_date", None),
            interval=extras.pop("interval", "1d"),
            limit=extras.pop("limit", None),
            page=extras.pop("page", None),
            query=extras.pop("query", None),
            fields=tuple(fields),
            source_hint=_normalize_source_id(extras.pop("source", None)),
            extras=extras,
        )

    def _cache_key(self, bucket: str, request: AStockRequest) -> Tuple[Any, ...]:
        return (bucket, request.cache_key())

    def _cache_bucket(self, capability: str) -> str:
        if capability in HISTORY_CAPABILITIES:
            return "history"
        if capability in SNAPSHOT_CAPABILITIES:
            return "snapshot"
        return "summary"

    def _get_cached_response(self, bucket: str, request: AStockRequest) -> Optional[AStockResponse]:
        key = self._cache_key(bucket, request)
        getter = None
        if bucket == "history":
            getter = getattr(self.cache, "get_history_range", None)
        elif bucket == "snapshot":
            getter = getattr(self.cache, "get_snapshot", None)
        else:
            getter = getattr(self.cache, "get_summary", None)
        if getter is None:
            getter = getattr(self.cache, "get", None)
        if getter is None:
            return None
        try:
            cached = getter(key)
        except Exception:
            logger.warning(
                "Cache read failed for capability=%s symbol=%s bucket=%s; "
                "falling through to live sources",
                request.capability, request.symbol, bucket,
                exc_info=True,
            )
            return None
        if cached is None:
            return None
        if isinstance(cached, AStockResponse):
            return cached.with_cached(True)
        if isinstance(cached, dict):
            response = AStockResponse(
                status=cached.get("status", "ok"),
                capability=cached.get("capability", request.capability),
                symbol=cached.get("symbol", request.symbol),
                raw_symbol=cached.get("raw_symbol", request.raw_symbol),
                source=cached.get("source"),
                sources_tried=tuple(cached.get("sources_tried", ())),
                data=cached.get("data"),
                meta=cached.get("meta", {}),
                cached=True,
                empty=cached.get("empty", False),
                error_code=cached.get("error_code"),
                error_message=cached.get("error_message"),
                request=cached.get("request"),
                notes=tuple(cached.get("notes", ())),
            )
            return response
        return None

    def _store_cache(self, bucket: str, request: AStockRequest, response: AStockResponse) -> None:
        if response.status != "ok":
            return
        key = self._cache_key(bucket, request)
        setter = None
        if bucket == "history":
            setter = getattr(self.cache, "set_history_range", None)
        elif bucket == "snapshot":
            setter = getattr(self.cache, "set_snapshot", None)
        else:
            setter = getattr(self.cache, "set_summary", None)
        if setter is None:
            setter = getattr(self.cache, "set", None)
        if setter is None:
            return
        try:
            setter(key, response)
        except Exception:
            # Cache failures must never poison the primary data path, but they
            # should be visible so a persistently broken cache is noticed.
            logger.warning(
                "Cache write failed for capability=%s symbol=%s bucket=%s",
                request.capability, request.symbol, bucket,
                exc_info=True,
            )
            return

    def _candidate_sources(self, capability: str, request: AStockRequest) -> Tuple[str, ...]:
        configured = self.route_policy.get(capability, ())
        default_order = DEFAULT_ROUTE_POLICY.get(capability, ())
        ordered = list(configured or default_order)
        if request.source_hint:
            ordered = [request.source_hint] + [source for source in ordered if _normalize_source_id(source) != request.source_hint]
        # Fill in any remaining adapters so fallback is clear and deterministic.
        for source in default_order:
            if _normalize_source_id(source) not in [_normalize_source_id(item) for item in ordered]:
                ordered.append(source)
        for source in self.adapters.keys():
            if source not in [_normalize_source_id(item) for item in ordered]:
                ordered.append(source)
        return _dedupe_sources(ordered)

    def _call_adapter(self, adapter: Any, method_name: str, request: AStockRequest):
        method = getattr(adapter, method_name, None)
        if method is None:
            raise AStockSourceUnavailableError(str(getattr(adapter, "name", "unknown")), "method {0} missing".format(method_name), capability=request.capability)
        source = str(getattr(adapter, "name", "unknown"))
        return self.request_governor.call(source, lambda: method(request))

    @staticmethod
    def _quality_for_source(source: str, sources_tried: Sequence[str], capability: str) -> str:
        """Determine DataQualityTag value based on source position in the route order.

        The first successfully attempted source gets ``normal``; subsequent
        sources (fallbacks after a prior source failed) get ``fallback``.
        """
        return (
            DataQualityTag.NORMAL.value
            if len(sources_tried) <= 1
            else DataQualityTag.FALLBACK.value
        )

    def _build_response_from_payload(
        self,
        capability: str,
        request: AStockRequest,
        source: str,
        sources_tried: Sequence[str],
        raw_payload: Any,
    ) -> AStockResponse:
        if isinstance(raw_payload, AStockResponse):
            payload = raw_payload.with_cached(False)
            if payload.source != source:
                payload = AStockResponse(
                    status=payload.status,
                    capability=payload.capability,
                    symbol=payload.symbol or request.symbol,
                    raw_symbol=payload.raw_symbol or request.raw_symbol,
                    source=source,
                    sources_tried=tuple(sources_tried),
                    data=payload.data,
                    meta=payload.meta,
                    cached=False,
                    empty=payload.empty,
                    error_code=payload.error_code,
                    error_message=payload.error_message,
                    request=request.to_dict(),
                    notes=payload.notes,
                )
            return payload

        data, meta, empty = normalize_capability_payload(capability, raw_payload, request, source)
        meta["quality"] = self._quality_for_source(source, sources_tried, capability)
        provider_notes = tuple(str(item) for item in meta.get("provider_notes", ())) if isinstance(meta, dict) else ()
        if empty or data is None:
            message = "NO_DATA_AVAILABLE: no data returned for {0} via {1}".format(request.symbol, source)
            return AStockResponse.empty_result(
                capability=capability,
                symbol=request.symbol,
                raw_symbol=request.raw_symbol,
                error_code="NO_DATA_AVAILABLE",
                error_message=message,
                source=source,
                sources_tried=sources_tried,
                request=request,
                meta=meta,
                notes=("normalized-empty",) + provider_notes,
            )

        return AStockResponse.ok(
            capability=capability,
            symbol=request.symbol,
            raw_symbol=request.raw_symbol,
            source=source,
            data=data,
            meta=meta,
            sources_tried=sources_tried,
            request=request,
            notes=provider_notes,
        )

    def query(self, capability: str, symbol: str, **kwargs: Any) -> AStockResponse:
        capability = str(capability).strip().lower()
        if capability not in CAPABILITY_TO_METHOD:
            return AStockResponse.error_result(
                capability=capability,
                symbol=normalize_astock_symbol(symbol),
                raw_symbol=symbol,
                error_code="UNSUPPORTED_CAPABILITY",
                error_message="Capability {0!r} is not implemented in the A-stock router".format(capability),
                request=self._request(capability, symbol, **kwargs),
            )

        request = self._request(capability, symbol, **kwargs)
        bucket = self._cache_bucket(capability)
        cached = self._get_cached_response(bucket, request)
        if cached is not None:
            return cached

        sources_tried: List[str] = []
        notes: List[str] = []
        no_data_errors: List[AStockNoDataError] = []
        first_error: Optional[Exception] = None
        candidates = self._candidate_sources(capability, request)
        method_name = CAPABILITY_TO_METHOD[capability]

        for source in candidates:
            if source in self.eliminated_sources:
                notes.append("skipped-eliminated:{0}".format(source))
                continue
            adapter = self.adapters.get(source)
            if adapter is None:
                notes.append("missing-adapter:{0}".format(source))
                continue
            sources_tried.append(source)
            try:
                raw_payload = self._call_adapter(adapter, method_name, request)
                response = self._build_response_from_payload(capability, request, source, tuple(sources_tried), raw_payload)
                if response.status == "ok":
                    if notes:
                        response = AStockResponse(
                            status=response.status,
                            capability=response.capability,
                            symbol=response.symbol,
                            raw_symbol=response.raw_symbol,
                            source=response.source,
                            sources_tried=response.sources_tried,
                            data=response.data,
                            meta=response.meta,
                            cached=response.cached,
                            empty=response.empty,
                            error_code=response.error_code,
                            error_message=response.error_message,
                            request=response.request,
                            notes=tuple(list(response.notes) + notes),
                        )
                    self._store_cache(bucket, request, response)
                    return response
                if response.status == "empty":
                    no_data_errors.append(AStockNoDataError(request.raw_symbol, request.symbol, response.error_message or "" , source=source, capability=capability))
                    continue
                if first_error is None:
                    first_error = AStockSourceUnavailableError(source, response.error_message or "adapter returned non-ok status", capability=capability)
            except AStockNoDataError as exc:
                no_data_errors.append(exc)
                continue
            except AStockSourceUnavailableError as exc:
                if first_error is None:
                    first_error = exc
                continue
            except Exception as exc:  # pragma: no cover - defensive fallback
                if first_error is None:
                    first_error = exc
                continue

        if no_data_errors:
            message = no_data_errors[-1].detail or str(no_data_errors[-1])
            return AStockResponse.empty_result(
                capability=capability,
                symbol=request.symbol,
                raw_symbol=request.raw_symbol,
                error_code="NO_DATA_AVAILABLE",
                error_message="NO_DATA_AVAILABLE: {0}".format(message),
                source=sources_tried[-1] if sources_tried else None,
                sources_tried=tuple(sources_tried),
                request=request,
                meta={"quality": DataQualityTag.DEGRADED.value, "notes": notes},
                notes=tuple(notes),
            )

        if first_error is not None:
            return AStockResponse.error_result(
                capability=capability,
                symbol=request.symbol,
                raw_symbol=request.raw_symbol,
                error_code=getattr(first_error, "error_code", "UPSTREAM_ERROR"),
                error_message=str(first_error),
                source=sources_tried[-1] if sources_tried else None,
                sources_tried=tuple(sources_tried),
                request=request,
                meta={"quality": DataQualityTag.DEGRADED.value, "notes": notes},
                notes=tuple(notes),
            )

        return AStockResponse.error_result(
            capability=capability,
            symbol=request.symbol,
            raw_symbol=request.raw_symbol,
            error_code="NO_SOURCE_AVAILABLE",
            error_message="No configured source could satisfy capability {0!r}".format(capability),
            source=None,
            sources_tried=tuple(sources_tried),
            request=request,
            meta={"quality": DataQualityTag.DEGRADED.value, "notes": notes},
            notes=tuple(notes),
        )

    # Convenience wrappers for the five-layer capability matrix.
    def get_kline(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.query("kline", symbol, **kwargs)

    def get_order_book(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.query("order_book", symbol, **kwargs)

    def get_trade_tape(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.query("trade_tape", symbol, **kwargs)

    def get_valuation(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.query("valuation", symbol, **kwargs)

    def get_pe_pb(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.query("pe_pb", symbol, **kwargs)

    def get_market_cap(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.query("market_cap", symbol, **kwargs)

    def get_turnover_rate(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.query("turnover_rate", symbol, **kwargs)

    def get_research_list(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.query("research_list", symbol, **kwargs)

    def download_research_pdf(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.query("download_research_pdf", symbol, **kwargs)

    def get_institution_expectation(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.query("institution_expectation", symbol, **kwargs)

    def search_research(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.query("search_research", symbol, **kwargs)

    def get_stock_news(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.query("stock_news", symbol, **kwargs)

    def get_flash_news(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.query("flash_news", symbol, **kwargs)

    def get_global_news(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.query("global_news", symbol, **kwargs)

    def get_quarterly_financials(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.query("quarterly_financials", symbol, **kwargs)

    def get_f10(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.query("f10", symbol, **kwargs)

    def get_fundamentals(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.query("fundamentals", symbol, **kwargs)

    def get_announcement_full(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.query("announcement_full", symbol, **kwargs)

    def get_announcement_summary(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.query("announcement_summary", symbol, **kwargs)

    def get_price_limit_status(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.query("price_limit", symbol, **kwargs)

    def get_market_summary(self, symbol: str = "000001.SH", **kwargs: Any) -> AStockResponse:
        return self.query("market_summary", symbol, **kwargs)

    def get_sector_data(self, symbol: str = "all", **kwargs: Any) -> AStockResponse:
        return self.query("sector", symbol, **kwargs)


class AStockDataFacade(object):
    """Thin convenience wrapper that keeps the upper layers router-agnostic."""

    def __init__(self, router: Optional[AStockDataRouter] = None, **router_kwargs: Any):
        self.router = router or AStockDataRouter(**router_kwargs)

    def query(self, capability: str, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.router.query(capability, symbol, **kwargs)

    def fetch(self, capability: str, symbol: str, **kwargs: Any) -> AStockResponse:
        """Compatibility-neutral loader entry point for a capability request.

        Store loaders operate on capabilities rather than bespoke facade
        methods.  Keeping that abstraction here prevents the request-time
        K-line refresh worker from selecting a different data path than the
        rest of the local product.
        """
        return self.query(capability, symbol, **kwargs)

    def get_kline(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.router.get_kline(symbol, **kwargs)

    def get_order_book(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.router.get_order_book(symbol, **kwargs)

    def get_trade_tape(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.router.get_trade_tape(symbol, **kwargs)

    def get_valuation(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.router.get_valuation(symbol, **kwargs)

    def get_pe_pb(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.router.get_pe_pb(symbol, **kwargs)

    def get_market_cap(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.router.get_market_cap(symbol, **kwargs)

    def get_turnover_rate(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.router.get_turnover_rate(symbol, **kwargs)

    def get_research_list(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.router.get_research_list(symbol, **kwargs)

    def download_research_pdf(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.router.download_research_pdf(symbol, **kwargs)

    def get_institution_expectation(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.router.get_institution_expectation(symbol, **kwargs)

    def search_research(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.router.search_research(symbol, **kwargs)

    def get_stock_news(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.router.get_stock_news(symbol, **kwargs)

    def get_flash_news(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.router.get_flash_news(symbol, **kwargs)

    def get_global_news(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.router.get_global_news(symbol, **kwargs)

    def get_quarterly_financials(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.router.get_quarterly_financials(symbol, **kwargs)

    def get_f10(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.router.get_f10(symbol, **kwargs)

    def get_fundamentals(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.router.get_fundamentals(symbol, **kwargs)

    def get_announcement_full(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.router.get_announcement_full(symbol, **kwargs)

    def get_announcement_summary(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.router.get_announcement_summary(symbol, **kwargs)

    def get_price_limit_status(self, symbol: str, **kwargs: Any) -> AStockResponse:
        return self.router.get_price_limit_status(symbol, **kwargs)

    def get_market_summary(self, symbol: str = "000001.SH", **kwargs: Any) -> AStockResponse:
        return self.router.get_market_summary(symbol, **kwargs)

    def get_sector_data(self, symbol: str = "all", **kwargs: Any) -> AStockResponse:
        return self.router.get_sector_data(symbol, **kwargs)
