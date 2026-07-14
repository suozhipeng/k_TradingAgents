"""Common utility functions for A-share data adapters."""

from __future__ import annotations

import logging

import json
import math
import os
import random
import re
import time
from contextlib import contextmanager
from datetime import datetime
from html import unescape
from typing import Any, Dict, Iterator, List, Optional, Sequence

from ..schema import AStockRequest
from ..symbols import astock_code, normalize_astock_symbol, split_astock_symbol
logger = logging.getLogger(__name__)


# ── Type coercion ───────────────────────────────────────────────────────

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


# ── Text / timestamp processing ─────────────────────────────────────────

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


# ── Data parsing helpers ────────────────────────────────────────────────

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
    from ..errors import AStockNoDataError
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


# ── TDX-specific ────────────────────────────────────────────────────────

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


# ── Tencent-specific ────────────────────────────────────────────────────

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


# ── Anti-crawling ───────────────────────────────────────────────────────

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


def _random_sleep(min_s: float = 0.3, max_s: float = 1.5) -> None:
    """随机延迟，降低被封概率。

    测试环境中（ASTOCK_TESTING=1）跳过延迟以加速测试。
    """
    if os.environ.get("ASTOCK_TESTING") == "1":
        return
    time.sleep(random.uniform(min_s, max_s))


def _retry_with_backoff(
    func, max_retries: int = 3, base_delay: float = 1.0,
    name: str = "request", deadline: float | None = None,
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
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError("{0} deadline exceeded before attempt {1}".format(name, attempt + 1))
        try:
            return func()
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                # 测试环境中不延迟
                if os.environ.get("ASTOCK_TESTING") != "1":
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                    if deadline is not None:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise TimeoutError("{0} deadline exceeded during retry".format(name))
                        delay = min(delay, remaining)
                    time.sleep(delay)
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
