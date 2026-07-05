"""Tencent Finance provider adapter for A-share data."""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional

from ..base import AStockAdapterBase
from ..common import (
    _coerce_float,
    _coerce_int,
    _coerce_bool,
    _env,
    _ensure_records,
    _first_non_null,
    _format_timestamp,
    _records_from_payload,
    _tencent_code,
    _tencent_side,
)
from ...errors import AStockNoDataError, AStockSourceUnavailableError
from ...schema import AStockRequest


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
        match = re.search(r'\[(?P<page>\d+),(?P<body>".*")\];?$', text.strip())
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
