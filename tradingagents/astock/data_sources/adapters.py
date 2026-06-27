"""Provider adapters for the A-share data layer.

This module keeps vendor specifics inside adapters and returns normalized raw
payloads (``{"bars": ...}``, ``{"items": ...}``, flat valuation dicts) that the
router can wrap into the stable ``AStockResponse`` schema.
"""

from __future__ import annotations

import importlib
import inspect
import json
import math
import os
import re
import time
from contextlib import contextmanager
from datetime import datetime
from html import unescape
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlencode

from .errors import AStockNoDataError, AStockSourceUnavailableError
from .schema import AStockRequest
from .symbols import astock_code, normalize_astock_symbol, split_astock_symbol
from .tdx_provider import TdxProvider


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


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        result = float(value)
        return None if math.isnan(result) else result
    text = str(value).strip()
    if not text or text in {"-", "--", "None", "null", "nan"}:
        return None
    multiplier = 1.0
    text = text.replace(",", "")
    if text.endswith("亿"):
        multiplier = 1.0
        text = text[:-1]
    elif text.endswith("万"):
        multiplier = 0.0001
        text = text[:-1]
    elif text.endswith("%"):
        text = text[:-1]
    try:
        return float(text) * multiplier
    except ValueError:
        return None


def _coerce_int(value: Any) -> Optional[int]:
    number = _coerce_float(value)
    if number is None:
        return None
    return int(number)


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _strip_html(value: Any) -> str:
    text = unescape(str(value or ""))
    return re.sub(r"<[^>]+>", "", text).strip()


def _format_timestamp(value: Any, *, input_format: Optional[str] = None) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if isinstance(value, (int, float)) or text.isdigit():
        if len(text) == 13:
            return datetime.utcfromtimestamp(int(text) / 1000).strftime("%Y-%m-%d %H:%M:%S")
        if len(text) == 14:
            try:
                return datetime.strptime(text, "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                return text
        if len(text) == 8:
            try:
                return datetime.strptime(text, "%Y%m%d").strftime("%Y-%m-%d")
            except ValueError:
                return text
    if input_format:
        try:
            return datetime.strptime(text, input_format).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return text
    return text


def _records_from_payload(payload: Any) -> List[Dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [dict(item) if isinstance(item, dict) else {"value": item} for item in payload]
    if isinstance(payload, tuple):
        return _records_from_payload(list(payload))
    if isinstance(payload, dict):
        return [dict(payload)]
    to_dict = getattr(payload, "to_dict", None)
    if callable(to_dict):
        try:
            records = to_dict(orient="records")
            return [dict(item) if isinstance(item, dict) else {"value": item} for item in records]
        except TypeError:
            try:
                raw = to_dict()
                if isinstance(raw, dict):
                    return [dict(raw)]
            except Exception:
                pass
    return [{"value": payload}]


def _ensure_records(records: List[Dict[str, Any]], request: AStockRequest, source: str, detail: str) -> List[Dict[str, Any]]:
    if records:
        return records
    raise AStockNoDataError(request.raw_symbol, request.symbol, detail, source=source, capability=request.capability)


def _filter_by_code(records: List[Dict[str, Any]], request: AStockRequest, *candidate_keys: str) -> List[Dict[str, Any]]:
    code = astock_code(request.symbol)
    if not candidate_keys:
        return records
    matched: List[Dict[str, Any]] = []
    for row in records:
        for key in candidate_keys:
            value = row.get(key)
            if value is None:
                continue
            if astock_code(str(value)) == code:
                matched.append(row)
                break
    return matched or records


def _first_non_null(row: Dict[str, Any], keys: Sequence[str], default: Any = None) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, "", "--", "-"):
            return row[key]
    return default


def _interval_to_tdx_frequency(interval: str) -> int:
    mapping = {
        "1m": 8,
        "5m": 0,
        "15m": 1,
        "30m": 2,
        "60m": 3,
        "1d": 9,
        "day": 9,
        "daily": 9,
        "1w": 5,
        "weekly": 5,
        "1mo": 6,
        "monthly": 6,
    }
    return mapping.get((interval or "1d").lower(), 9)


def _tencent_code(symbol: str) -> str:
    code, exchange = split_astock_symbol(symbol)
    if not code:
        return symbol.lower()
    exchange = (exchange or "SH").lower()
    return "{0}{1}".format(exchange, code)


def _tencent_side(flag: str) -> str:
    text = str(flag or "").upper()
    if text == "B":
        return "buy"
    if text == "S":
        return "sell"
    return "neutral"


@contextmanager
def _temporarily_disable_proxies(enabled: bool = True):
    if not enabled:
        yield
        return
    keys = ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]
    original = {key: os.environ.get(key) for key in keys}
    no_proxy_original = os.environ.get("NO_PROXY")
    no_proxy_lower_original = os.environ.get("no_proxy")
    try:
        for key in keys:
            os.environ.pop(key, None)
        os.environ["NO_PROXY"] = "*"
        os.environ["no_proxy"] = "*"
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        if no_proxy_original is None:
            os.environ.pop("NO_PROXY", None)
        else:
            os.environ["NO_PROXY"] = no_proxy_original
        if no_proxy_lower_original is None:
            os.environ.pop("no_proxy", None)
        else:
            os.environ["no_proxy"] = no_proxy_lower_original


# ===================================================================
# Anti-crawling 工具集
# ===================================================================

import random
import time as _time


def _random_sleep(min_s: float = 0.3, max_s: float = 1.5) -> None:
    """随机延迟，降低被封概率。

    测试环境中（ASTOCK_TESTING=1）跳过延迟以加速测试。
    """
    if os.environ.get("ASTOCK_TESTING") == "1":
        return
    _time.sleep(random.uniform(min_s, max_s))


def _retry_with_backoff(
    func, max_retries: int = 3, base_delay: float = 1.0,
    name: str = "request",
):
    """带指数退避的重试包装器。

    Args:
        func: 无参 callable（闭包捕获外部状态）
        max_retries: 最大重试次数
        base_delay: 初始延迟秒数
        name: 日志用名称

    Returns:
        func() 的返回值

    Raises:
        最后一次失败的异常
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                # 测试环境中不延迟
                if os.environ.get("ASTOCK_TESTING") != "1":
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                    _time.sleep(delay)
    raise last_exc  # type: ignore[misc]


_DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def _common_headers(referer: str = "https://finance.sina.com.cn/") -> dict:
    """返回一组常见的请求头，降低被识别为爬虫的概率。"""
    from collections import OrderedDict

    return OrderedDict([
        ("User-Agent", _DEFAULT_UA),
        ("Accept", "text/html,application/json,*/*"),
        ("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8"),
        ("Referer", referer),
        ("Connection", "keep-alive"),
    ])


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
            with _temporarily_disable_proxies(bool(self.config.get("disable_env_proxy", True))):
                return func(**kwargs)

        try:
            result = _retry_with_backoff(_do_call, max_retries=2, base_delay=1.0, name="akshare." + func_name)
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
        default_start_year = str(datetime.utcnow().year - 6)
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
        from .suspension import is_at_price_limit_external
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


class TencentFinanceAdapter(AStockAdapterBase):
    name = "tencent"

    def __init__(self, session: Any = None, timeout: Optional[float] = None, headers: Optional[Dict[str, str]] = None, retries: Optional[int] = None, retry_backoff: Optional[float] = None, **config: Any):
        super(TencentFinanceAdapter, self).__init__(session=session, timeout=timeout, headers=headers, retries=retries, retry_backoff=retry_backoff, **config)
        self._session = session
        self.timeout = timeout if timeout is not None else _coerce_float(config.get("timeout") or _env("ASTOCK_TENCENT_TIMEOUT", "5")) or 5.0
        self.retries = int(retries if retries is not None else config.get("retries", 2))
        self.retry_backoff = float(retry_backoff if retry_backoff is not None else config.get("retry_backoff", 0.2))
        env_headers = _env("ASTOCK_TENCENT_HEADERS_JSON")
        parsed_headers = json.loads(env_headers) if env_headers else {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 TradingAgents/astock",
            "Referer": "https://gu.qq.com/",
            "Accept": "*/*",
        }
        self.headers.update(parsed_headers)
        if headers:
            self.headers.update(headers)

    def _get_session(self):
        if self._session is not None:
            return self._session
        try:
            import requests  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise AStockSourceUnavailableError(self.name, "requests import failed: {0}".format(exc))
        self._session = requests.Session()
        return self._session

    def _request_text(self, request: AStockRequest, url: str, *, encoding: str = "gbk") -> str:
        session = self._get_session()
        last_error: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            try:
                response = session.get(url, headers=self.headers, timeout=self.timeout)
                if hasattr(response, "raise_for_status"):
                    response.raise_for_status()
                text = getattr(response, "text", None)
                if text is None:
                    content = getattr(response, "content", b"")
                    text = content.decode(encoding, errors="ignore")
                if not str(text).strip():
                    raise AStockNoDataError(request.raw_symbol, request.symbol, "empty response body", source=self.name, capability=request.capability)
                return str(text)
            except AStockNoDataError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(self.retry_backoff)
        raise AStockSourceUnavailableError(self.name, "request failed: {0}".format(last_error), capability=request.capability)

    def _snapshot_url(self, request: AStockRequest) -> str:
        return "https://qt.gtimg.cn/q={0}".format(_tencent_code(request.symbol))

    def _trade_tape_url(self, request: AStockRequest) -> str:
        page = request.page or int(self.config.get("default_page", 1))
        return "https://stock.gtimg.cn/data/index.php?appn=detail&action=data&c={0}&p={1}".format(_tencent_code(request.symbol), page)

    def _extract_snapshot_fields(self, request: AStockRequest, text: str) -> List[str]:
        match = re.search(r'="(?P<body>.*)";?$', text.strip())
        if not match:
            raise AStockSourceUnavailableError(self.name, "unexpected Tencent snapshot format", capability=request.capability)
        fields = match.group("body").split("~")
        if len(fields) < 40:
            raise AStockSourceUnavailableError(self.name, "Tencent snapshot payload too short", capability=request.capability)
        return fields

    def _parse_snapshot(self, request: AStockRequest, text: str) -> Dict[str, Any]:
        fields = self._extract_snapshot_fields(request, text)
        combined = fields[35].split("/") if len(fields) > 35 and fields[35] else []
        amount = _coerce_float(combined[2]) if len(combined) >= 3 else _coerce_float(fields[37] if len(fields) > 37 else None)
        bids = []
        asks = []
        for i in range(5):
            bid_price = _coerce_float(fields[9 + i * 2] if len(fields) > 9 + i * 2 else None)
            bid_volume = _coerce_int(fields[10 + i * 2] if len(fields) > 10 + i * 2 else None)
            ask_price = _coerce_float(fields[19 + i * 2] if len(fields) > 19 + i * 2 else None)
            ask_volume = _coerce_int(fields[20 + i * 2] if len(fields) > 20 + i * 2 else None)
            if bid_price is not None:
                bids.append({"level": i + 1, "price": bid_price, "volume": bid_volume})
            if ask_price is not None:
                asks.append({"level": i + 1, "price": ask_price, "volume": ask_volume})
        return {
            "symbol": request.symbol,
            "code": fields[2],
            "name": fields[1],
            "price": _coerce_float(fields[3]),
            "pre_close": _coerce_float(fields[4]),
            "open": _coerce_float(fields[5]),
            "volume": _coerce_float(fields[36] if len(fields) > 36 else fields[6]),
            "amount": amount,
            "change": _coerce_float(fields[31] if len(fields) > 31 else None),
            "pct_change": _coerce_float(fields[32] if len(fields) > 32 else None),
            "high": _coerce_float(fields[33] if len(fields) > 33 else None),
            "low": _coerce_float(fields[34] if len(fields) > 34 else None),
            "turnover_rate": _coerce_float(fields[38] if len(fields) > 38 else None),
            "market_cap": _coerce_float(fields[45] if len(fields) > 45 else None),
            "circulating_market_cap": _coerce_float(fields[46] if len(fields) > 46 else None),
            "pb": _coerce_float(fields[53] if len(fields) > 53 else None),
            "pe": _coerce_float(fields[54] if len(fields) > 54 else None),
            "timestamp": _format_timestamp(fields[30] if len(fields) > 30 else None),
            "bids": bids,
            "asks": asks,
        }

    def _parse_trade_tape(self, request: AStockRequest, text: str) -> Dict[str, Any]:
        match = re.search(r'\[(?P<page>\d+),"(?P<body>.*)"\];?$', text.strip())
        if not match:
            raise AStockSourceUnavailableError(self.name, "unexpected Tencent trade tape format", capability=request.capability)
        body = match.group("body")
        if not body:
            raise AStockNoDataError(request.raw_symbol, request.symbol, "Tencent trade tape empty", source=self.name, capability=request.capability)
        items: List[Dict[str, Any]] = []
        for chunk in body.split("|"):
            parts = chunk.split("/")
            if len(parts) < 7:
                continue
            items.append(
                {
                    "seq": _coerce_int(parts[0]),
                    "time": parts[1],
                    "price": _coerce_float(parts[2]),
                    "change": _coerce_float(parts[3]),
                    "volume": _coerce_int(parts[4]),
                    "amount": _coerce_float(parts[5]),
                    "side": _tencent_side(parts[6]),
                }
            )
        items = _ensure_records(items, request, self.name, "Tencent trade tape returned no rows")
        return {"items": items, "count": len(items), "page": _coerce_int(match.group("page"))}

    def get_kline(self, request: AStockRequest):
        return self._unavailable(request, "Tencent kline endpoint not implemented in this stage")

    def get_order_book(self, request: AStockRequest):
        snapshot = self._parse_snapshot(request, self._request_text(request, self._snapshot_url(request)))
        return {
            "symbol": snapshot["symbol"],
            "code": snapshot["code"],
            "name": snapshot["name"],
            "price": snapshot["price"],
            "open": snapshot["open"],
            "pre_close": snapshot["pre_close"],
            "high": snapshot["high"],
            "low": snapshot["low"],
            "timestamp": snapshot["timestamp"],
            "bids": snapshot["bids"],
            "asks": snapshot["asks"],
        }

    def get_trade_tape(self, request: AStockRequest):
        return self._parse_trade_tape(request, self._request_text(request, self._trade_tape_url(request)))

    def get_valuation(self, request: AStockRequest):
        snapshot = self._parse_snapshot(request, self._request_text(request, self._snapshot_url(request)))
        return {
            "symbol": snapshot["symbol"],
            "name": snapshot["name"],
            "price": snapshot["price"],
            "turnover_rate": snapshot["turnover_rate"],
            "market_cap": snapshot["market_cap"],
            "circulating_market_cap": snapshot["circulating_market_cap"],
            "pb": snapshot["pb"],
            "pe": snapshot["pe"],
            "timestamp": snapshot["timestamp"],
        }


class CninfoAdapter(AStockAdapterBase):
    name = "cninfo"

    def __init__(self, session: Any = None, timeout: Optional[float] = None, headers: Optional[Dict[str, str]] = None, cookie: Optional[str] = None, csrf_token: Optional[str] = None, **config: Any):
        super(CninfoAdapter, self).__init__(session=session, timeout=timeout, headers=headers, cookie=cookie, csrf_token=csrf_token, **config)
        self._session = session
        self.timeout = timeout if timeout is not None else _coerce_float(config.get("timeout") or _env("ASTOCK_CNINFO_TIMEOUT", "10")) or 10.0
        self.cookie = cookie if cookie is not None else _env("ASTOCK_CNINFO_COOKIE")
        self.csrf_token = csrf_token if csrf_token is not None else _env("ASTOCK_CNINFO_CSRF_TOKEN")
        self.headers = {
            "User-Agent": _env("ASTOCK_CNINFO_USER_AGENT", "Mozilla/5.0 TradingAgents/astock"),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/search",
            "X-Requested-With": "XMLHttpRequest",
        }
        if self.cookie:
            self.headers["Cookie"] = self.cookie
        if self.csrf_token:
            self.headers["X-CSRF-TOKEN"] = self.csrf_token
        if headers:
            self.headers.update(headers)
        self._org_cache: Dict[str, str] = {}

    def _get_session(self):
        if self._session is not None:
            return self._session
        try:
            import requests  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise AStockSourceUnavailableError(self.name, "requests import failed: {0}".format(exc))
        self._session = requests.Session()
        return self._session

    def _request_json(self, request: AStockRequest, method: str, url: str, **kwargs: Any) -> Dict[str, Any]:
        session = self._get_session()
        # Anti-crawling: random delay before each request
        _random_sleep(0.5, 2.0)

        def _do_request():
            response = getattr(session, method.lower())(url, headers=self.headers, timeout=self.timeout, **kwargs)
            if hasattr(response, "raise_for_status"):
                response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("cninfo response is not a JSON object")
            return data

        try:
            return _retry_with_backoff(_do_request, max_retries=2, base_delay=1.0, name="cninfo." + method)
        except AStockNoDataError:
            raise
        except Exception as exc:
            raise AStockSourceUnavailableError(
                self.name, "cninfo request failed after retries: {0}".format(exc),
                capability=request.capability,
            )

    def _exchange_meta(self, request: AStockRequest) -> Dict[str, str]:
        code, exchange = split_astock_symbol(request.symbol)
        exchange = exchange or "SH"
        mapping = {
            "SH": {"column": "sse", "plate": "sh", "stock_list": "https://www.cninfo.com.cn/new/data/sse_stock.json"},
            "SZ": {"column": "szse", "plate": "sz", "stock_list": "https://www.cninfo.com.cn/new/data/szse_stock.json"},
            "BJ": {"column": "bjse", "plate": "bj", "stock_list": "https://www.cninfo.com.cn/new/data/bjse_stock.json"},
        }
        return mapping.get(exchange, mapping["SH"])

    def _get_org_id(self, request: AStockRequest) -> str:
        code = astock_code(request.symbol)
        if code in self._org_cache:
            return self._org_cache[code]
        meta = self._exchange_meta(request)
        data = self._request_json(request, "GET", meta["stock_list"])
        stock_list = data.get("stockList") or []
        for item in stock_list:
            if str(item.get("code")) == code and item.get("orgId"):
                self._org_cache[code] = str(item["orgId"])
                return self._org_cache[code]
        raise AStockNoDataError(request.raw_symbol, request.symbol, "cninfo orgId not found", source=self.name, capability=request.capability)

    def _query_announcements(self, request: AStockRequest) -> Dict[str, Any]:
        meta = self._exchange_meta(request)
        org_id = ""
        try:
            org_id = self._get_org_id(request)
        except Exception:
            org_id = ""
        payload = {
            "pageNum": request.page or 1,
            "pageSize": request.limit or int(self.config.get("page_size", 20)),
            "tabName": "fulltext",
            "column": meta["column"],
            "plate": meta["plate"],
            "stock": "{0},{1}".format(astock_code(request.symbol), org_id) if org_id else "",
            "searchkey": request.query or astock_code(request.symbol) or self.config.get("searchkey", ""),
            "secid": request.extras.get("secid", ""),
            "seDate": request.extras.get("seDate", self.config.get("seDate", "")),
            "sortName": request.extras.get("sortName", ""),
            "sortType": request.extras.get("sortType", ""),
            "isHLtitle": "true",
        }
        return self._request_json(request, "POST", "https://www.cninfo.com.cn/new/hisAnnouncement/query", data=payload)

    def _normalize_announcements(self, request: AStockRequest, payload: Dict[str, Any]) -> Dict[str, Any]:
        raw_items = payload.get("announcements") or []
        if not raw_items:
            raise AStockNoDataError(request.raw_symbol, request.symbol, "cninfo announcement list empty", source=self.name, capability=request.capability)
        items: List[Dict[str, Any]] = []
        for row in raw_items:
            adjunct = str(row.get("adjunctUrl") or "").lstrip("/")
            download_url = "https://static.cninfo.com.cn/{0}".format(adjunct) if adjunct else None
            items.append(
                {
                    "announcement_id": str(row.get("announcementId") or ""),
                    "symbol": normalize_astock_symbol(str(row.get("secCode") or request.symbol)),
                    "name": _strip_html(row.get("secName")),
                    "title": _strip_html(row.get("announcementTitle") or row.get("shortTitle")),
                    "published_at": _format_timestamp(row.get("announcementTime")),
                    "pdf_url": download_url,
                    "download_url": download_url,
                    "adjunct_size_kb": _coerce_float(row.get("adjunctSize")),
                    "adjunct_type": row.get("adjunctType"),
                    "page_column": row.get("pageColumn"),
                    "announcement_type": row.get("announcementType"),
                    "org_id": row.get("orgId"),
                }
            )
        return {
            "items": items,
            "count": len(items),
            "total": payload.get("totalAnnouncement") or len(items),
            "total_pages": payload.get("totalpages"),
            "has_more": bool(payload.get("hasMore")),
        }

    def get_announcement_summary(self, request: AStockRequest):
        payload = self._query_announcements(request)
        return self._normalize_announcements(request, payload)

    def get_announcement_full(self, request: AStockRequest):
        summary = self.get_announcement_summary(request)
        announcement_id = str(request.extras.get("announcement_id") or request.query or "").strip()
        items = summary.get("items", [])
        chosen = items[0]
        if announcement_id:
            for item in items:
                if str(item.get("announcement_id")) == announcement_id:
                    chosen = item
                    break
        return dict(chosen)


class MootdxAdapter(AStockAdapterBase):
    name = "mootdx"

    def __init__(self, client: Any = None, timeout: Optional[float] = None, **config: Any):
        super(MootdxAdapter, self).__init__(client=client, timeout=timeout, **config)
        self._client = client
        self.timeout = timeout if timeout is not None else _coerce_float(config.get("timeout") or _env("ASTOCK_MOOTDX_TIMEOUT", "5")) or 5.0

    def _load_client(self):
        if self._client is not None:
            return self._client
        try:
            from mootdx.quotes import Quotes  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise AStockSourceUnavailableError(self.name, "mootdx import failed: {0}".format(exc))
        kwargs: Dict[str, Any] = {}
        host = self.config.get("host") or _env("ASTOCK_MOOTDX_HOST")
        port = self.config.get("port") or _env("ASTOCK_MOOTDX_PORT")
        if host:
            kwargs["host"] = host
        if port:
            kwargs["port"] = int(port)
        try:
            self._client = Quotes.factory(market=self.config.get("market") or _env("ASTOCK_MOOTDX_MARKET", "std"), **kwargs)
            return self._client
        except Exception as exc:
            raise AStockSourceUnavailableError(self.name, "mootdx connection failed: {0}".format(exc))

    def _call(self, request: AStockRequest, method_name: str, **kwargs: Any):
        client = self._load_client()
        method = getattr(client, method_name, None)
        if method is None:
            raise AStockSourceUnavailableError(self.name, "mootdx method missing: {0}".format(method_name), capability=request.capability)

        # Anti-crawling: mootdx 连接 TDX 服务器，礼貌性延迟
        _random_sleep(0.2, 0.8)

        def _do_call():
            return method(**kwargs)

        try:
            return _retry_with_backoff(_do_call, max_retries=2, base_delay=0.5, name="mootdx." + method_name)
        except AStockNoDataError:
            raise
        except Exception as exc:
            raise AStockSourceUnavailableError(
                self.name, "mootdx {0} failed after retries: {1}".format(method_name, exc),
                capability=request.capability,
            )

    def _parse_bars(self, request: AStockRequest, payload: Any) -> Dict[str, Any]:
        records = _ensure_records(_records_from_payload(payload), request, self.name, "mootdx bars returned no rows")
        bars: List[Dict[str, Any]] = []
        for row in records:
            bars.append(
                {
                    "date": _format_timestamp(_first_non_null(row, ("date", "datetime", "trade_date", "time"))),
                    "open": _coerce_float(_first_non_null(row, ("open", "open_price"))),
                    "high": _coerce_float(_first_non_null(row, ("high", "high_price"))),
                    "low": _coerce_float(_first_non_null(row, ("low", "low_price"))),
                    "close": _coerce_float(_first_non_null(row, ("close", "price"))),
                    "volume": _coerce_float(_first_non_null(row, ("volume", "vol", "cur_vol"))),
                    "amount": _coerce_float(_first_non_null(row, ("amount", "amt"))),
                }
            )
        return {"bars": bars, "symbol": request.symbol, "interval": request.interval}

    def _parse_quotes(self, request: AStockRequest, payload: Any) -> Dict[str, Any]:
        records = _ensure_records(_records_from_payload(payload), request, self.name, "mootdx quotes returned no rows")
        row = records[0]
        bids = []
        asks = []
        for i in range(1, 6):
            bid_price = _coerce_float(row.get("bid{0}".format(i)))
            bid_volume = _coerce_int(row.get("bid_vol{0}".format(i)))
            ask_price = _coerce_float(row.get("ask{0}".format(i)))
            ask_volume = _coerce_int(row.get("ask_vol{0}".format(i)))
            if bid_price is not None:
                bids.append({"level": i, "price": bid_price, "volume": bid_volume})
            if ask_price is not None:
                asks.append({"level": i, "price": ask_price, "volume": ask_volume})
        return {
            "symbol": request.symbol,
            "code": _first_non_null(row, ("code", "symbol"), astock_code(request.symbol)),
            "name": _first_non_null(row, ("name", "stock_name")),
            "price": _coerce_float(_first_non_null(row, ("price", "last", "close"))),
            "open": _coerce_float(_first_non_null(row, ("open",))),
            "pre_close": _coerce_float(_first_non_null(row, ("last_close", "pre_close"))),
            "high": _coerce_float(_first_non_null(row, ("high",))),
            "low": _coerce_float(_first_non_null(row, ("low",))),
            "volume": _coerce_float(_first_non_null(row, ("cur_vol", "volume", "vol"))),
            "amount": _coerce_float(_first_non_null(row, ("amount", "amt"))),
            "bids": bids,
            "asks": asks,
        }

    def _parse_transactions(self, request: AStockRequest, payload: Any) -> Dict[str, Any]:
        records = _ensure_records(_records_from_payload(payload), request, self.name, "mootdx transactions returned no rows")
        items: List[Dict[str, Any]] = []
        for row in records:
            items.append(
                {
                    "time": _first_non_null(row, ("time", "datetime")),
                    "price": _coerce_float(_first_non_null(row, ("price",))),
                    "volume": _coerce_int(_first_non_null(row, ("vol", "volume"))),
                    "amount": _coerce_float(_first_non_null(row, ("num", "amount"))),
                    "side": _tencent_side(_first_non_null(row, ("buyorsell", "side"), "M")),
                }
            )
        return {"items": items, "count": len(items)}

    def get_kline(self, request: AStockRequest):
        payload = self._call(
            request,
            "bars",
            symbol=astock_code(request.symbol),
            frequency=_interval_to_tdx_frequency(request.interval),
            start=int(request.extras.get("start", 0)),
            offset=int(request.limit or request.extras.get("offset", 800)),
        )
        return self._parse_bars(request, payload)

    def get_order_book(self, request: AStockRequest):
        payload = self._call(request, "quotes", symbol=[astock_code(request.symbol)])
        return self._parse_quotes(request, payload)

    def get_trade_tape(self, request: AStockRequest):
        payload = self._call(
            request,
            "transactions",
            symbol=astock_code(request.symbol),
            start=int(request.extras.get("start", 0)),
            offset=int(request.limit or request.extras.get("offset", 80)),
            date=str(request.extras.get("date", datetime.utcnow().strftime("%Y%m%d"))),
        )
        return self._parse_transactions(request, payload)

    def get_f10(self, request: AStockRequest):
        payload = self._call(request, "finance", symbol=astock_code(request.symbol))
        records = _records_from_payload(payload)
        records = _ensure_records(records, request, self.name, "mootdx finance returned no rows")
        row = records[0]
        return {
            "code": _first_non_null(row, ("code",), astock_code(request.symbol)),
            "name": _first_non_null(row, ("name", "stock_name")),
            "industry": _first_non_null(row, ("industry", "行业")),
            "province": _first_non_null(row, ("province", "地区")),
            "total_shares": _coerce_float(_first_non_null(row, ("zongguben", "总股本"))),
            "float_shares": _coerce_float(_first_non_null(row, ("liutongguben", "流通股本"))),
            "updated_at": _format_timestamp(_first_non_null(row, ("updated_at", "日期"))),
        }


class IwencaiAdapter(AStockAdapterBase):
    name = "iwencai"

    def __init__(self, wencai_module: Any = None, cookie: Optional[str] = None, user_agent: Optional[str] = None, retry: Optional[int] = None, sleep: Optional[float] = None, **config: Any):
        super(IwencaiAdapter, self).__init__(wencai_module=wencai_module, cookie=cookie, user_agent=user_agent, retry=retry, sleep=sleep, **config)
        self._module = wencai_module
        self.cookie = cookie if cookie is not None else _env("ASTOCK_IWENCAI_COOKIE")
        self.user_agent = user_agent if user_agent is not None else _env("ASTOCK_IWENCAI_USER_AGENT")
        self.retry = int(retry if retry is not None else config.get("retry", _env("ASTOCK_IWENCAI_RETRY", "2")))
        self.sleep = float(sleep if sleep is not None else config.get("sleep", _env("ASTOCK_IWENCAI_SLEEP", "0.2")))

    def _load(self):
        if self._module is not None:
            return self._module
        try:
            self._module = importlib.import_module("pywencai")
            return self._module
        except Exception as exc:  # pragma: no cover
            raise AStockSourceUnavailableError(self.name, "pywencai import failed: {0}".format(exc))

    def _call(self, request: AStockRequest, query: str):
        if not self.cookie:
            raise AStockSourceUnavailableError(self.name, "iwencai cookie not configured; set ASTOCK_IWENCAI_COOKIE", capability=request.capability)
        module = self._load()
        getter = getattr(module, "get", None)
        if getter is None:
            raise AStockSourceUnavailableError(self.name, "pywencai.get missing", capability=request.capability)
        try:
            return getter(
                query=query,
                loop=False,
                cookie=self.cookie,
                user_agent=self.user_agent,
                retry=self.retry,
                sleep=self.sleep,
                query_type=self.config.get("query_type", "stock"),
                request_params={"timeout": (5, 10)},
            )
        except Exception as exc:
            raise AStockSourceUnavailableError(self.name, "pywencai query failed: {0}".format(exc), capability=request.capability)

    def _parse_search(self, request: AStockRequest, payload: Any) -> Dict[str, Any]:
        records = _ensure_records(_records_from_payload(payload), request, self.name, "iwencai search returned no rows")
        items: List[Dict[str, Any]] = []
        for row in records:
            symbol = normalize_astock_symbol(str(_first_non_null(row, ("股票代码", "code", "symbol"), request.symbol)))
            items.append(
                {
                    "symbol": symbol,
                    "name": _first_non_null(row, ("股票简称", "name", "名称")),
                    "price": _coerce_float(_first_non_null(row, ("最新价", "price"))),
                    "pct_change": _coerce_float(_first_non_null(row, ("涨跌幅", "pct_change"))),
                    "keyword": _first_non_null(row, ("问财关键词", "query", "关键词"), request.query or request.raw_symbol),
                }
            )
        return {"items": items, "count": len(items), "query": request.query or request.raw_symbol}

    def _parse_expectation(self, request: AStockRequest, payload: Any) -> Dict[str, Any]:
        records = _ensure_records(_records_from_payload(payload), request, self.name, "iwencai expectation returned no rows")
        items: List[Dict[str, Any]] = []
        for row in records:
            items.append(
                {
                    "symbol": normalize_astock_symbol(str(_first_non_null(row, ("股票代码", "code", "symbol"), request.symbol))),
                    "name": _first_non_null(row, ("股票简称", "name", "名称")),
                    "institution_count": _coerce_int(_first_non_null(row, ("机构数", "机构家数", "report_count"))),
                    "consensus_rating": _first_non_null(row, ("一致预期评级", "评级", "rating")),
                    "eps_2026": _coerce_float(_first_non_null(row, ("2026预测每股收益", "2026E每股收益"))),
                }
            )
        return {"items": items, "count": len(items), "query": request.query or request.raw_symbol}

    def get_institution_expectation(self, request: AStockRequest):
        query = str(request.query or (request.raw_symbol + " 机构预期")).strip()
        return self._parse_expectation(request, self._call(request, query))

    def search_research(self, request: AStockRequest):
        query = str(request.query or request.raw_symbol).strip()
        if not query:
            raise AStockSourceUnavailableError(self.name, "iwencai query empty", capability=request.capability)
        return self._parse_search(request, self._call(request, query))


class QMTAdapter(AStockAdapterBase):
    """QMT bridge adapter with real HTTP bridge calls and mock fallback.

    Handles all read-only data operations (kline, order book, trade tape,
    valuation) through the ``QmtBridge`` HTTP client.  When the bridge is
    unreachable or ``QmtBridge`` is not importable, falls back to
    raising ``AStockNoDataError``.

    Fundamentals are not available through QMT; ``get_fundamentals``
    remains a placeholder as in Phase 09.
    """

    name = "qmt"

    def __init__(self, **config: Any):
        super().__init__(**config)
        self._bridge = None
        self._bridge_import_error: Optional[str] = None
        try:
            # Late import to avoid circular dependency and to handle
            # environments where the execution subpackage is not installed.
            from tradingagents.astock.execution.qmt_bridge import QmtBridge as _QmtBridge

            self._bridge_class = _QmtBridge
        except ImportError as exc:
            self._bridge_import_error = str(exc)
            self._bridge_class = None

    def _get_bridge(self, request: AStockRequest):
        """Lazy-init and return the QmtBridge instance.

        Returns ``None`` when the bridge cannot be loaded, which triggers
        the ``_no_data`` fallback.
        """
        if self._bridge is not None:
            return self._bridge
        if self._bridge_class is None:
            return None
        try:
            host = self.config.get("host", "127.0.0.1")
            port = int(self.config.get("port", 58609))
            timeout = float(self.config.get("timeout", 10.0))
            self._bridge = self._bridge_class(
                config=type("cfg", (), {"host": host, "port": port, "timeout": timeout})(),
                use_mock=False,
            )
            # Quick health check — if it fails, use mock fallback
            if not self._bridge.health_check():
                self._bridge = self._bridge_class(use_mock=True)
            return self._bridge
        except Exception:
            self._bridge = self._bridge_class(use_mock=True) if self._bridge_class else None
            return self._bridge

    def _no_data(self, request: AStockRequest, detail: str = ""):
        raise AStockNoDataError(
            request.raw_symbol, request.symbol,
            detail or "QMT bridge unavailable",
            source=self.name,
            capability=request.capability,
        )

    def get_kline(self, request: AStockRequest):
        bridge = self._get_bridge(request)
        if bridge is None:
            self._no_data(request, "QMT bridge not importable")
        try:
            bars = bridge.get_kline(
                symbol=request.symbol,
                start=request.start_date or "",
                end=request.end_date or "",
                period=request.interval or "1d",
            )
            if not bars:
                self._no_data(request)
            return {"bars": bars, "count": len(bars)}
        except (ConnectionError, ValueError, RuntimeError) as exc:
            self._no_data(request, str(exc))

    def get_order_book(self, request: AStockRequest):
        bridge = self._get_bridge(request)
        if bridge is None:
            self._no_data(request, "QMT bridge not importable")
        try:
            return bridge.get_order_book(symbol=request.symbol)
        except (ConnectionError, ValueError, RuntimeError) as exc:
            self._no_data(request, str(exc))

    def get_trade_tape(self, request: AStockRequest):
        bridge = self._get_bridge(request)
        if bridge is None:
            self._no_data(request, "QMT bridge not importable")
        try:
            ticks = bridge.get_trade_tape(symbol=request.symbol)
            if not ticks:
                self._no_data(request)
            return {"ticks": ticks, "count": len(ticks)}
        except (ConnectionError, ValueError, RuntimeError) as exc:
            self._no_data(request, str(exc))

    def get_valuation(self, request: AStockRequest):
        bridge = self._get_bridge(request)
        if bridge is None:
            self._no_data(request, "QMT bridge not importable")
        try:
            return bridge.get_valuation(symbol=request.symbol)
        except (ConnectionError, ValueError, RuntimeError) as exc:
            self._no_data(request, str(exc))

    def get_fundamentals(self, request: AStockRequest):
        self._no_data(request, "QMT bridge does not provide fundamental data")


# ===================================================================
# Baostock adapter — 免费、无需注册、无限流
# ===================================================================


class BaoStockAdapter(AStockAdapterBase):
    """Baostock 数据源适配器 — 免费开源证券数据平台。

    支持能力:
        - kline (日K, 后复权 adjustflag=2)
        - 无需 API Key, 无需注册, 无限流量

    Baostock 的 symbol 格式为 ``sh.600519`` / ``sz.000001``。
    ``AStockRequest.symbol`` 已标准化为 ``600519.SH``，适配器内部转换。
    """

    name = "baostock"

    def __init__(self, **config: Any) -> None:
        super().__init__(**config)
        self._logged_in = False

    def _login(self) -> None:
        if self._logged_in:
            return
        try:
            import baostock as bs  # type: ignore
        except ImportError:
            raise AStockSourceUnavailableError(
                self.name, "baostock package not installed. Run: pip install baostock"
            )
        import socket

        socket.setdefaulttimeout(5.0)
        try:
            lg = bs.login()
        finally:
            socket.setdefaulttimeout(None)
        if lg.error_code != "0":
            raise AStockSourceUnavailableError(
                self.name, "baostock login failed: {0}".format(lg.error_msg)
            )
        self._logged_in = True

    def _logout(self) -> None:
        if self._logged_in:
            try:
                import baostock as bs

                bs.logout()
            except Exception:
                pass
            self._logged_in = False

    @staticmethod
    def _to_bs_symbol(symbol: str) -> str:
        """Convert ``600519.SH`` → ``sh.600519``."""
        code, market = symbol.upper().split(".")
        if market == "SH":
            return "sh." + code
        return "sz." + code

    def get_kline(self, request: AStockRequest) -> dict:
        """获取日 K 线数据（后复权）。

        Baostock 的 adjustflag:
            1=前复权  2=后复权  3=不复权
        """
        self._login()
        bs_symbol = self._to_bs_symbol(request.symbol)
        start = request.start_date or "2000-01-01"
        end = request.end_date or "2026-12-31"

        # Anti-crawling: baostock 虽然免费，但礼貌性延迟
        _random_sleep(0.3, 1.0)

        try:
            import baostock as bs
            import pandas as pd  # noqa: F811
        except ImportError:
            raise AStockSourceUnavailableError(
                self.name, "baostock package not installed"
            )

        def _do_query():
            rs = bs.query_history_k_data_plus(
                bs_symbol,
                fields="date,open,high,low,close,preclose,volume,amount,pctChg",
                start_date=start,
                end_date=end,
                frequency="d",
                adjustflag="2",  # 后复权
            )
            if rs.error_code != "0":
                raise AStockNoDataError(
                    request.raw_symbol,
                    request.symbol,
                    "baostock query failed: {0}".format(rs.error_msg),
                    source=self.name,
                    capability=request.capability,
                )
            bars = []
            while rs.next():
                row = rs.get_row_data()
                date_str = row[0]
                if not date_str:
                    continue
                try:
                    bar = {
                        "date": date_str,
                        "open": float(row[1]) if row[1] else 0.0,
                        "high": float(row[2]) if row[2] else 0.0,
                        "low": float(row[3]) if row[3] else 0.0,
                        "close": float(row[4]) if row[4] else 0.0,
                        "preclose": float(row[5]) if row[5] else 0.0,
                        "volume": float(row[6]) if row[6] else 0.0,
                        "amount": float(row[7]) if row[7] else 0.0,
                        "pctChg": float(row[8]) if row[8] else 0.0,
                    }
                    bars.append(bar)
                except (ValueError, IndexError):
                    continue
            if not bars:
                raise AStockNoDataError(
                    request.raw_symbol,
                    request.symbol,
                    "no kline data from baostock",
                    source=self.name,
                    capability=request.capability,
                )
            return {"bars": bars, "count": len(bars)}

        return _retry_with_backoff(_do_query, max_retries=2, base_delay=0.5, name="baostock.kline")

    def __del__(self):
        self._logout()


DEFAULT_ADAPTER_FACTORIES = {
    "akshare": AkshareAdapter,
    "mootdx": MootdxAdapter,
    "tdx": TdxProvider,
    "tencent": TencentFinanceAdapter,
    "iwencai": IwencaiAdapter,
    "cninfo": CninfoAdapter,
    "qmt": QMTAdapter,
    "baostock": BaoStockAdapter,
}


def build_default_adapters(**configs: Any) -> Dict[str, AStockAdapterBase]:
    """Create the default provider adapters with optional per-source config."""
    adapters: Dict[str, AStockAdapterBase] = {}
    for name, factory in DEFAULT_ADAPTER_FACTORIES.items():
        adapters[name] = factory(**dict(configs.get(name, {})))
    return adapters
