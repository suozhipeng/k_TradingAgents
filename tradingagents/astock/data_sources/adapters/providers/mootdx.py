"""Mootdx provider adapter for A-share data."""

from __future__ import annotations

from datetime import datetime
from tradingagents.astock.time_utils import utc_now
from typing import Any, Dict, List, Optional

from ..base import AStockAdapterBase
from ..common import (
    _coerce_float,
    _coerce_int,
    _env,
    _ensure_records,
    _first_non_null,
    _format_timestamp,
    _interval_to_tdx_frequency,
    _random_sleep,
    _records_from_payload,
    _retry_with_backoff,
    _tencent_side,
)
from ...errors import AStockNoDataError, AStockSourceUnavailableError
from ...schema import AStockRequest
from ...symbols import astock_code
from ...tdx_provider import TdxProvider


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
            # Note: keep this provider import path lightweight. The current
            # repo temporarily disables Gemini because langchain-google-genai
            # wants a newer httpx, while mootdx 0.11.7 still constrains
            # httpx < 0.26.0 in the shared environment.
            from mootdx.quotes import Quotes  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise AStockSourceUnavailableError(self.name, "mootdx import failed: {0}".format(exc))
        kwargs: Dict[str, Any] = {}
        host = self.config.get("host") or _env("ASTOCK_MOOTDX_HOST")
        port = self.config.get("port") or _env("ASTOCK_MOOTDX_PORT")
        # mootdx forwards arbitrary keyword arguments to BaseSocketClient.
        # That client does not accept ``host``/``port``; its supported explicit
        # endpoint is the ``server=(host, port)`` tuple instead.
        if host:
            kwargs["server"] = (str(host), int(port or 7709))
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
            try:
                return method(**kwargs)
            except ValueError as exc:
                msg = str(exc)
                # mootdx internally calls pd.to_datetime on TDX response data.
                # For some symbols (e.g. SZ exchange indices) the server returns
                # garbled datetime strings that pandas cannot parse.  Treat this
                # as "no data available" for the symbol rather than a transient
                # error that would trigger retries + backoff (~4.6s).
                if "doesn't match format" in msg or "time data" in msg:
                    raise AStockNoDataError(
                        request.raw_symbol,
                        request.symbol,
                        "mootdx returned garbled data for this symbol",
                        source=self.name,
                        capability=request.capability,
                    )
                raise

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
        # TDX's ``bars`` API accepts an offset, not a date range.  The router
        # still supplies the local watermark for an incremental refresh, so
        # honour it before handing rows to the loader.  This prevents the
        # provider's trailing window from being presented as a full reload or
        # repeatedly upserted as such.  Date strings emitted by
        # ``_format_timestamp`` are ISO-like and therefore sort correctly on
        # their calendar portion.
        start_date = str(request.start_date or "")[:10]
        end_date = str(request.end_date or "")[:10]
        if start_date or end_date:
            bars = [
                bar for bar in bars
                if (not start_date or str(bar.get("date") or "")[:10] >= start_date)
                and (not end_date or str(bar.get("date") or "")[:10] <= end_date)
            ]
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
            date=str(request.extras.get("date", utc_now().strftime("%Y%m%d"))),
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
