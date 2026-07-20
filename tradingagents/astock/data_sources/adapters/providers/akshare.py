"""Akshare provider adapter for A-share data."""

from __future__ import annotations

import importlib
import inspect
import json
import logging
import queue
import threading
import time
from datetime import datetime
from tradingagents.astock.time_utils import utc_now
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import AStockAdapterBase

logger = logging.getLogger(__name__)
from ..common import (
    _coerce_bool,
    _coerce_float,
    _coerce_int,
    _env,
    _ensure_records,
    _filter_by_code,
    _first_non_null,
    _format_timestamp,
    _random_sleep,
    _records_from_payload,
    _retry_with_backoff,
    _tencent_code,
    _temporarily_disable_proxies,
)
from ...errors import AStockNoDataError, AStockSourceUnavailableError
from ...schema import AStockRequest, _as_records
from ...symbols import astock_code, normalize_astock_symbol
from .tencent import TencentFinanceAdapter


class AkshareAdapter(AStockAdapterBase):
    name = "akshare"

    def __init__(self, module: Any = None, timeout: Optional[float] = None, **config: Any):
        super(AkshareAdapter, self).__init__(module=module, timeout=timeout, **config)
        self._module = module
        self.timeout = timeout if timeout is not None else _coerce_float(config.get("timeout")) or 10.0
        self.allow_tencent_valuation_supplement = _coerce_bool(
            config.get("allow_tencent_valuation_supplement", _env("ASTOCK_AKSHARE_ALLOW_TENCENT_SUPPLEMENT")),
            default=False,
        )
        self._tencent_adapter = config.get("tencent_adapter")
        # Circuit breaker & anti-crawling state
        self._failure_count: Dict[str, int] = {}
        self._last_failure_time: Dict[str, float] = {}
        self._circuit_open_until: Dict[str, float] = {}
        self._max_failures = int(config.get("circuit_breaker_max_failures", _env("ASTOCK_AKSHARE_CB_MAX_FAILURES", "3")))
        self._window_seconds = float(config.get("circuit_breaker_window", _env("ASTOCK_AKSHARE_CB_WINDOW", "60")))
        self._cooldown_seconds = float(config.get("circuit_breaker_cooldown", _env("ASTOCK_AKSHARE_CB_COOLDOWN", "30")))
        self._max_daily_calls = int(config.get("max_daily_calls", _env("ASTOCK_AKSHARE_MAX_DAILY_CALLS", "5000")))
        self._call_count = 0
        self._last_reset_day = datetime.now().strftime("%Y-%m-%d")
        # File-based counter so the limit survives process restarts
        # (akshare enforces the limit server-side regardless of our process state)
        self._counter_file = config.get(
            "call_counter_file",
            str(Path.home() / ".tradingagents" / "astock" / "akshare_call_count.json"),
        )
        self._load_call_counter()

    def _load_call_counter(self) -> None:
        """Restore call count from disk if the file exists and is from today."""
        try:
            p = Path(self._counter_file)
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                if data.get("date") == datetime.now().strftime("%Y-%m-%d"):
                    self._call_count = int(data.get("count", 0))
                    self._last_reset_day = data.get("date", self._last_reset_day)
        except Exception:
            pass

    def _persist_call_counter(self) -> None:
        """Write current call count to disk for process restart resilience."""
        try:
            p = Path(self._counter_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(
                json.dumps({
                    "date": self._last_reset_day,
                    "count": self._call_count,
                }, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass  # Non-critical — if we can't write, we just reset on restart

    def _load(self):
        if self._module is not None:
            return self._module
        try:
            self._module = importlib.import_module("akshare")
            return self._module
        except Exception as exc:  # pragma: no cover - optional dependency
            raise AStockSourceUnavailableError(self.name, "akshare import failed: {0}".format(exc))

    def _code(self, request: AStockRequest) -> str:
        return astock_code(request.symbol)

    def _call(self, request: AStockRequest, func_name: str, **kwargs: Any):
        module = self._load()
        func = getattr(module, func_name, None)
        if func is None:
            raise AStockSourceUnavailableError(self.name, "akshare function missing: {0}".format(func_name), capability=request.capability)
        try:
            signature = inspect.signature(func)
            if "timeout" in signature.parameters and "timeout" not in kwargs:
                kwargs["timeout"] = self.timeout
        except Exception:
            pass

        # Daily call limit
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._last_reset_day:
            self._call_count = 0
            self._last_reset_day = today
        self._call_count += 1
        if self._call_count > self._max_daily_calls:
            raise AStockSourceUnavailableError(
                self.name,
                "daily call limit ({0}) exceeded for {1}".format(self._max_daily_calls, func_name),
                capability=request.capability,
            )
        # Persist to disk periodically (every 100 calls) to survive restarts
        if self._call_count % 100 == 0:
            self._persist_call_counter()

        # Circuit breaker check
        now = time.time()
        if func_name in self._circuit_open_until:
            if now < self._circuit_open_until[func_name]:
                raise AStockSourceUnavailableError(
                    self.name,
                    "circuit breaker open for {0}, cooldown {1:.0f}s remaining".format(
                        func_name, self._circuit_open_until[func_name] - now,
                    ),
                    capability=request.capability,
                )
            else:
                # Cooldown expired, auto-reset
                self._circuit_open_until.pop(func_name, None)
                self._failure_count.pop(func_name, None)
                self._last_failure_time.pop(func_name, None)

        # Anti-crawling: adaptive random delay
        failure_count = self._failure_count.get(func_name, 0)
        if failure_count > 0:
            _random_sleep(1.0, 3.0)
        else:
            _random_sleep(0.5, 2.0)

        def _do_call():
            try:
                with _temporarily_disable_proxies(bool(self.config.get("disable_env_proxy", True))):
                    return func(**kwargs)
            except ValueError as exc:
                msg = str(exc)
                # Akshare's stock_zh_a_daily raises JSONDecodeError (a subclass
                # of ValueError) when the symbol is an exchange index rather than
                # a stock.  Treat this as "no data" rather than retrying 3 times
                # with backoff (~5s).
                if "No value to decode" in msg:
                    raise AStockNoDataError(
                        request.raw_symbol,
                        request.symbol,
                        "akshare stock API does not support index-level symbols",
                        source=self.name,
                        capability=request.capability,
                    )
                raise

        try:
            # Many AkShare functions do not expose a network timeout.  Run the
            # full retry sequence behind one hard caller deadline so a broken
            # upstream cannot stall an API request or the research graph.
            result = self._call_with_deadline(
                lambda: _retry_with_backoff(
                    _do_call, max_retries=2, base_delay=1.0,
                    name="akshare." + func_name,
                ),
                func_name,
            )
            # Success - reset circuit breaker for this function
            self._failure_count.pop(func_name, None)
            self._last_failure_time.pop(func_name, None)
            self._circuit_open_until.pop(func_name, None)
            return result
        except AStockNoDataError:
            raise
        except AStockSourceUnavailableError:
            self._record_failure(func_name)
            raise
        except Exception as exc:
            self._record_failure(func_name)
            raise AStockSourceUnavailableError(
                self.name, "{0} failed after retries: {1}".format(func_name, exc),
                capability=request.capability,
            )

    def _call_with_deadline(self, operation: Any, func_name: str) -> Any:
        """Return an AkShare result or fail after the adapter-wide deadline.

        The upstream library owns its HTTP sessions and not every function
        accepts a timeout argument.  A daemon worker is deliberately used as
        a containment boundary: once the deadline expires callers can fall
        back immediately and the stuck upstream call cannot keep the local
        product or pytest process alive.
        """
        result: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

        def run() -> None:
            try:
                result.put((True, operation()))
            except BaseException as exc:  # propagate provider failures intact
                result.put((False, exc))

        worker = threading.Thread(target=run, name="akshare-call", daemon=True)
        worker.start()
        try:
            succeeded, value = result.get(timeout=max(0.1, float(self.timeout)))
        except queue.Empty as exc:
            raise TimeoutError(
                "akshare.{0} exceeded {1:.1f}s deadline".format(func_name, self.timeout)
            ) from exc
        if succeeded:
            return value
        raise value

    def _record_failure(self, func_name: str) -> None:
        """Record a failure and open circuit if threshold exceeded."""
        now = time.time()
        last_failure = self._last_failure_time.get(func_name)
        if last_failure is not None and (now - last_failure) > self._window_seconds:
            # Window expired, reset counter
            self._failure_count[func_name] = 1
        else:
            self._failure_count[func_name] = self._failure_count.get(func_name, 0) + 1
        self._last_failure_time[func_name] = now
        if self._failure_count[func_name] >= self._max_failures:
            self._circuit_open_until[func_name] = now + self._cooldown_seconds

    def _parse_kline(self, request: AStockRequest, payload: Any) -> Dict[str, Any]:
        records = _ensure_records(_records_from_payload(payload), request, self.name, "akshare stock_zh_a_hist returned no rows")
        bars: List[Dict[str, Any]] = []
        for row in records:
            bars.append(
                {
                    "date": _format_timestamp(_first_non_null(row, ("日期", "date", "日期时间"))),
                    "open": _coerce_float(_first_non_null(row, ("开盘", "open"))),
                    "high": _coerce_float(_first_non_null(row, ("最高", "high"))),
                    "low": _coerce_float(_first_non_null(row, ("最低", "low"))),
                    "close": _coerce_float(_first_non_null(row, ("收盘", "close"))),
                    "volume": _coerce_float(_first_non_null(row, ("成交量", "volume"))),
                    "amount": _coerce_float(_first_non_null(row, ("成交额", "amount"))),
                    "turnover_rate": _coerce_float(_first_non_null(row, ("换手率", "turnover_rate"))),
                }
            )
        return {"bars": bars, "symbol": request.symbol, "interval": request.interval}

    def _parse_spot_valuation(self, request: AStockRequest, payload: Any) -> Dict[str, Any]:
        records = _records_from_payload(payload)
        records = _filter_by_code(records, request, "代码", "股票代码", "symbol")
        records = _ensure_records(records, request, self.name, "akshare stock_zh_a_spot_em returned no matching rows")
        row = records[0]
        source_function = str(request.extras.get("source_function") or "akshare.stock_zh_a_spot_em")
        values = {
            "symbol": request.symbol,
            "name": _first_non_null(row, ("名称", "股票简称", "name")),
            "price": _coerce_float(_first_non_null(row, ("最新价", "最新", "price"))),
            "open": _coerce_float(_first_non_null(row, ("今开", "开盘", "open"))),
            "pre_close": _coerce_float(_first_non_null(row, ("昨收", "昨收价", "pre_close"))),
            "high": _coerce_float(_first_non_null(row, ("最高", "high"))),
            "low": _coerce_float(_first_non_null(row, ("最低", "low"))),
            "volume": _coerce_float(_first_non_null(row, ("成交量", "volume"))),
            "amount": _coerce_float(_first_non_null(row, ("成交额", "amount"))),
            "turnover_rate": _coerce_float(_first_non_null(row, ("换手率", "turnover_rate"))),
            "pe": _coerce_float(_first_non_null(row, ("市盈率-动态", "市盈率", "pe"))),
            "pb": _coerce_float(_first_non_null(row, ("市净率", "pb"))),
            "market_cap": _coerce_float(_first_non_null(row, ("总市值", "market_cap"))),
            "circulating_market_cap": _coerce_float(_first_non_null(row, ("流通市值", "circulating_market_cap"))),
        }
        values["meta"] = {
            "provider": "akshare",
            "tencent_supplement_enabled": self.allow_tencent_valuation_supplement,
            "field_sources": {
                key: source_function
                for key, value in values.items()
                if key != "meta" and value is not None
            },
        }
        return values

    def _parse_news(self, request: AStockRequest, payload: Any) -> Dict[str, Any]:
        records = _ensure_records(_records_from_payload(payload), request, self.name, "akshare stock_news_em returned no rows")
        items: List[Dict[str, Any]] = []
        for row in records:
            items.append(
                {
                    "symbol": request.symbol,
                    "title": _first_non_null(row, ("新闻标题", "title", "标题")),
                    "content": _first_non_null(row, ("新闻内容", "content", "摘要"), ""),
                    "published_at": _format_timestamp(_first_non_null(row, ("发布时间", "date", "publish_time"))),
                    "source": _first_non_null(row, ("文章来源", "mediaName", "source")),
                    "url": _first_non_null(row, ("新闻链接", "url", "链接")),
                }
            )
        return {"items": items, "count": len(items)}

    def _parse_research(self, request: AStockRequest, payload: Any) -> Dict[str, Any]:
        records = _ensure_records(_records_from_payload(payload), request, self.name, "akshare stock_research_report_em returned no rows")
        items: List[Dict[str, Any]] = []
        for row in records:
            items.append(
                {
                    "symbol": normalize_astock_symbol(str(_first_non_null(row, ("股票代码", "stockCode", "代码"), astock_code(request.symbol)))),
                    "name": _first_non_null(row, ("股票简称", "stockName", "名称")),
                    "title": _first_non_null(row, ("报告名称", "title")),
                    "institution": _first_non_null(row, ("机构", "orgSName", "orgName")),
                    "published_at": _format_timestamp(_first_non_null(row, ("日期", "publishDate"))),
                    "rating": _first_non_null(row, ("东财评级", "投资评级", "rating")),
                    "pdf_url": _first_non_null(row, ("pdfUrl", "pdf_url", "url")),
                }
            )
        return {"items": items, "count": len(items)}

    def _parse_financials(self, request: AStockRequest, payload: Any) -> Dict[str, Any]:
        records = _ensure_records(_records_from_payload(payload), request, self.name, "akshare stock_financial_analysis_indicator returned no rows")
        items: List[Dict[str, Any]] = []
        for row in records:
            normalized = {"period": _format_timestamp(_first_non_null(row, ("日期", "报告期", "period")))}
            for key, value in row.items():
                if key in {"日期", "报告期", "period"}:
                    continue
                normalized[str(key)] = _coerce_float(value) if _coerce_float(value) is not None else None
            items.append(normalized)
        return {"items": items, "count": len(items)}

    def _parse_expectation(self, request: AStockRequest, payload: Any) -> Dict[str, Any]:
        records = _records_from_payload(payload)
        records = _filter_by_code(records, request, "代码", "股票代码", "symbol")
        records = _ensure_records(records, request, self.name, "akshare stock_profit_forecast_em returned no matching rows")
        items: List[Dict[str, Any]] = []
        for row in records:
            normalized = {
                "symbol": normalize_astock_symbol(str(_first_non_null(row, ("代码", "股票代码"), astock_code(request.symbol)))),
                "name": _first_non_null(row, ("名称", "股票简称")),
                "institution_count": _coerce_int(_first_non_null(row, ("研报数", "机构数", "RATING_ORG_NUM"))),
            }
            for key, value in row.items():
                if key in {"代码", "股票代码", "名称", "股票简称", "研报数", "机构数"}:
                    continue
                normalized[str(key)] = _coerce_float(value) if _coerce_float(value) is not None else None
            items.append(normalized)
        return {"items": items, "count": len(items)}

    def get_kline(self, request: AStockRequest):
        interval = (request.interval or "1d").lower()
        if interval in {"1d", "daily", "day"}:
            symbol = _tencent_code(request.symbol)
            module = self._load()
            if hasattr(module, "stock_zh_a_daily"):
                payload = self._call(
                    request,
                    "stock_zh_a_daily",
                    symbol=symbol,
                    start_date=(request.start_date or "19900101").replace("-", ""),
                    end_date=(request.end_date or "21000101").replace("-", ""),
                    adjust=self.config.get("adjust", "qfq"),
                )
                return self._parse_kline(request, payload)
        period_map = {
            "1d": "daily",
            "daily": "daily",
            "day": "daily",
            "1w": "weekly",
            "weekly": "weekly",
            "1mo": "monthly",
            "monthly": "monthly",
        }
        period = period_map.get(interval, "daily")
        payload = self._call(
            request,
            "stock_zh_a_hist",
            symbol=self._code(request),
            period=period,
            start_date=(request.start_date or "19700101").replace("-", ""),
            end_date=(request.end_date or "20500101").replace("-", ""),
            adjust=self.config.get("adjust", "qfq"),
        )
        return self._parse_kline(request, payload)

    def get_valuation(self, request: AStockRequest):
        valuation = None
        source_function = "akshare.stock_zh_a_spot_em"
        try:
            if hasattr(self._load(), "stock_zh_a_spot_em"):
                spot_payload = self._call(request, "stock_zh_a_spot_em")
                valuation = self._parse_spot_valuation(request, spot_payload)
        except AStockSourceUnavailableError:
            valuation = None
        if valuation is None:
            module = self._load()
            if hasattr(module, "stock_zh_a_spot"):
                try:
                    spot_payload = self._call(request, "stock_zh_a_spot")
                    valuation = self._parse_spot_valuation(request, spot_payload)
                    source_function = "akshare.stock_zh_a_spot"
                    field_sources = valuation.setdefault("meta", {}).setdefault("field_sources", {})
                    for key, value in valuation.items():
                        if key not in {"meta", "notes"} and value is not None:
                            field_sources[key] = source_function
                except AStockSourceUnavailableError:
                    valuation = None
        if valuation is None:
            if not self.allow_tencent_valuation_supplement:
                raise AStockSourceUnavailableError(
                    self.name,
                    "akshare valuation endpoints unavailable and Tencent supplement disabled (default false; set allow_tencent_valuation_supplement=True or ASTOCK_AKSHARE_ALLOW_TENCENT_SUPPLEMENT=1)",
                    capability=request.capability,
                )
            try:
                tencent_adapter = self._tencent_adapter or TencentFinanceAdapter(timeout=self.timeout, retries=1)
                valuation = dict(tencent_adapter.get_valuation(request))
                valuation["meta"] = {
                    "provider": "akshare+tencent",
                    "akshare_source_function": None,
                    "tencent_supplement_enabled": True,
                    "field_sources": {
                        key: "tencent.qt.gtimg.cn"
                        for key, value in valuation.items()
                        if key not in {"meta", "notes"} and value is not None
                    },
                }
                valuation["notes"] = ["valuation-source:akshare-unavailable", "valuation-supplement:tencent"]
                return valuation
            except Exception as exc:
                raise AStockSourceUnavailableError(self.name, "valuation fallback failed: {0}".format(exc), capability=request.capability)
        meta = valuation.setdefault("meta", {})
        meta["provider"] = "akshare"
        meta["akshare_source_function"] = source_function
        meta["tencent_supplement_enabled"] = self.allow_tencent_valuation_supplement
        field_sources = meta.setdefault("field_sources", {})
        for key, value in valuation.items():
            if key not in {"meta", "notes"} and value is not None and key not in field_sources:
                field_sources[key] = source_function
        if valuation.get("market_cap") is None:
            try:
                info_payload = self._call(request, "stock_individual_info_em", symbol=self._code(request))
                info_records = _records_from_payload(info_payload)
                info_map = {str(item.get("item")): item.get("value") for item in info_records}
                for field_name, info_key in (
                    ("market_cap", "总市值"),
                    ("circulating_market_cap", "流通市值"),
                ):
                    if valuation.get(field_name) is None:
                        value = _coerce_float(info_map.get(info_key))
                        if value is not None:
                            valuation[field_name] = value
                            field_sources[field_name] = "akshare.stock_individual_info_em"
            except AStockSourceUnavailableError:
                pass
        missing_supplement_fields = [key for key in ("turnover_rate", "pe", "pb", "market_cap") if valuation.get(key) is None]
        if missing_supplement_fields and self.allow_tencent_valuation_supplement:
            try:
                tencent_adapter = self._tencent_adapter or TencentFinanceAdapter(timeout=self.timeout, retries=1)
                tencent_valuation = tencent_adapter.get_valuation(request)
                supplemented: List[str] = []
                for key in ("turnover_rate", "pe", "pb", "market_cap", "circulating_market_cap", "timestamp"):
                    if valuation.get(key) is None and tencent_valuation.get(key) is not None:
                        valuation[key] = tencent_valuation.get(key)
                        field_sources[key] = "tencent.qt.gtimg.cn"
                        supplemented.append(key)
                if supplemented:
                    meta["provider"] = "akshare+tencent"
                    meta["supplemented_fields"] = supplemented
                    valuation["notes"] = list(valuation.get("notes", [])) + ["valuation-supplement:tencent"]
            except Exception as exc:
                valuation["notes"] = list(valuation.get("notes", [])) + ["valuation-supplement:tencent-failed:{0}".format(type(exc).__name__)]
        return valuation

    def get_stock_news(self, request: AStockRequest):
        payload = self._call(request, "stock_news_em", symbol=self._code(request))
        return self._parse_news(request, payload)

    def get_research_list(self, request: AStockRequest):
        payload = self._call(request, "stock_research_report_em", symbol=self._code(request))
        return self._parse_research(request, payload)

    def download_research_pdf(self, request: AStockRequest):
        research = self.get_research_list(request)
        items = research.get("items", [])
        if not items:
            raise AStockNoDataError(request.raw_symbol, request.symbol, "no research pdf available", source=self.name, capability=request.capability)
        preferred_title = str(request.extras.get("title") or request.query or "").strip()
        chosen = items[0]
        if preferred_title:
            for item in items:
                if preferred_title in str(item.get("title", "")):
                    chosen = item
                    break
        return {
            "symbol": request.symbol,
            "title": chosen.get("title"),
            "pdf_url": chosen.get("pdf_url"),
            "published_at": chosen.get("published_at"),
            "institution": chosen.get("institution"),
        }

    def get_institution_expectation(self, request: AStockRequest):
        payload = self._call(request, "stock_profit_forecast_em", symbol="")
        return self._parse_expectation(request, payload)

    def search_research(self, request: AStockRequest):
        query = str(request.query or request.raw_symbol or "").strip()
        research = self.get_research_list(request)
        if not query:
            return research
        items = [
            item
            for item in research.get("items", [])
            if query in str(item.get("title", "")) or query in str(item.get("institution", ""))
        ]
        if not items:
            raise AStockNoDataError(request.raw_symbol, request.symbol, "no matching research rows for query {0!r}".format(query), source=self.name, capability=request.capability)
        return {"items": items, "count": len(items), "query": query}

    def get_quarterly_financials(self, request: AStockRequest):
        default_start_year = str(utc_now().year - 6)
        payload = self._call(
            request,
            "stock_financial_analysis_indicator",
            symbol=self._code(request),
            start_year=str(request.extras.get("start_year", self.config.get("start_year", default_start_year))),
        )
        return self._parse_financials(request, payload)

    def get_fundamentals(self, request: AStockRequest):
        return self.get_quarterly_financials(request)

    def get_price_limit_status(self, request: AStockRequest):
        """Check if a symbol is at its daily price limit.

        Delegates to :func:`suspension.is_at_price_limit_external` which
        uses akshare's EastMoney 涨停/跌停 pools with fallback to the
        EastMoney push2 real-time API.

        Returns a dict with ``is_limited`` and ``direction``.
        """
        from ...suspension import is_at_price_limit_external
        limited, direction = is_at_price_limit_external(
            request.symbol,
            date=request.start_date or None,
        )
        return {
            "symbol": request.symbol,
            "is_limited": limited,
            "direction": direction,
            "source": self.name,
        }

    # ------------------------------------------------------------------
    # 快讯 & 全球新闻 — 多源实时财经快讯
    # ------------------------------------------------------------------

    _FLASH_NEWS_SOURCES = {
        "em": "stock_info_global_em",
        "sina": "stock_info_global_sina",
        "futu": "stock_info_global_futu",
        "ths": "stock_info_global_ths",
    }

    def _parse_flash_news(self, request: AStockRequest, payload: Any, source_name: str = "") -> Dict[str, Any]:
        """Parse flash news from any supported source into standardized items."""
        detail = "akshare {0} returned no rows".format(source_name or "flash_news")
        records = _ensure_records(_records_from_payload(payload), request, self.name, detail)
        items: List[Dict[str, Any]] = []
        limit = request.limit
        for i, row in enumerate(records):
            if limit is not None and i >= limit:
                break
            items.append({
                "title": _first_non_null(row, ("标题", "title", "内容", "content"), ""),
                "content": _first_non_null(row, ("摘要", "内容", "content", "summary"), ""),
                "published_at": _format_timestamp(_first_non_null(row, ("发布时间", "时间", "date", "time"))),
                "url": _first_non_null(row, ("链接", "url"), ""),
            })
        return {"items": items, "count": len(items), "source": source_name or "em"}

    def get_flash_news(self, request: AStockRequest):
        news_source = str(request.extras.get("news_source", "em")).lower().strip()
        func_name = self._FLASH_NEWS_SOURCES.get(news_source, "stock_info_global_em")
        payload = self._call(request, func_name)
        return self._parse_flash_news(request, payload, source_name=news_source)

    def get_global_news(self, request: AStockRequest):
        payload = self._call(request, "stock_info_global_em")
        return self._parse_flash_news(request, payload, source_name="em")

    def get_sector_data(self, request: AStockRequest):
        """Fetch industry sector ranking via akshare (THS board data)."""
        indicator = str(request.extras.get("indicator", "industry")).lower().strip()
        if indicator == "concept":
            func_name = "stock_board_concept_spot_em"
        else:
            func_name = "stock_board_industry_summary_ths"
        payload = self._call(request, func_name)
        items: List[Dict[str, Any]] = []
        records = _as_records(payload)
        for row in records:
            items.append({
                "sector_code": _first_non_null(row, ("序号", "code"), ""),
                "sector_name": _first_non_null(row, ("板块", "name"), ""),
                "change_pct": _coerce_float(_first_non_null(row, ("涨跌幅", "change_pct"), 0.0)),
                "volume": _coerce_float(_first_non_null(row, ("总成交量", "volume"), 0.0)),
                "amount": _coerce_float(_first_non_null(row, ("总成交额", "amount"), 0.0)),
                "net_inflow": _coerce_float(_first_non_null(row, ("净流入", "net_inflow"), 0.0)),
                "advancers": _coerce_int(_first_non_null(row, ("上涨家数", "advancers"), 0)),
                "decliners": _coerce_int(_first_non_null(row, ("下跌家数", "decliners"), 0)),
                "avg_price": _coerce_float(_first_non_null(row, ("均价", "avg_price"), 0.0)),
                "leading_stock": _first_non_null(row, ("领涨股", "leading_stock"), ""),
                "leading_stock_price": _coerce_float(_first_non_null(row, ("领涨股-最新价", "leading_stock_price"), 0.0)),
                "leading_stock_change": _coerce_float(_first_non_null(row, ("领涨股-涨跌幅", "leading_stock_change"), 0.0)),
            })
        return {"items": items, "count": len(items), "indicator": indicator, "source": self.name}
