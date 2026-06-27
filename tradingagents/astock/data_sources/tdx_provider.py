"""TDX (通达信) market data provider adapter.

Uses ``pytdx`` to connect to TDX online quote servers for real-time quotes,
kline data, and index data.  Designed as an alternative/fallback data source
in the A-share router chain.

Capabilities implemented
------------------------
- ``kline`` (daily + intraday via pytdx)
- ``order_book`` (real-time snapshots / 盘口)
- ``trade_tape`` (逐笔成交)

Cache / persistence
-------------------
Delegate caching to the router-level cache layer; this adapter is stateless.

Graceful degradation
--------------------
- If pytdx is not installed: raise ``AStockSourceUnavailableError`` at runtime.
- If connection to TDX servers fails: raise ``AStockSourceUnavailableError``.
- Every public method catches all exceptions and maps to ``AStockSourceUnavailableError``.

Configuration (env vars)
------------------------
- ``ASTOCK_TDX_HOST``       — TDX server host (default: 119.147.212.81)
- ``ASTOCK_TDX_PORT``       — TDX server port (default: 7709)
- ``ASTOCK_TDX_TIMEOUT``    — connection timeout in seconds (default: 5)
- ``ASTOCK_TDX_MULTICAST``  — use multicast server address (default: false)
- ``ASTOCK_TDX_BACKUP_HOSTS`` — comma-separated fallback hosts
"""

from __future__ import annotations

import logging
import math
import os
import random
import time as _time
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from .errors import AStockNoDataError, AStockSourceUnavailableError
from .schema import AStockRequest
from .symbols import astock_code, split_astock_symbol

logger = logging.getLogger(__name__)

# ── Self-contained helpers (copied from adapters.py to avoid circular import) ──


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
    try:
        return float(text)
    except ValueError:
        return None


def _coerce_int(value: Any) -> Optional[int]:
    number = _coerce_float(value)
    if number is None:
        return None
    return int(number)


def _first_non_null(row: Dict[str, Any], keys: Sequence[str], default: Any = None) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, "", "--", "-"):
            return row[key]
    return default


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _random_sleep(min_s: float = 0.3, max_s: float = 1.5) -> None:
    if os.environ.get("ASTOCK_TESTING") == "1":
        return
    _time.sleep(random.uniform(min_s, max_s))


def _retry_with_backoff(
    func,
    max_retries: int = 3,
    base_delay: float = 1.0,
    name: str = "request",
):
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                if os.environ.get("ASTOCK_TESTING") != "1":
                    delay = base_delay * (2**attempt) + random.uniform(0, 0.5)
                    _time.sleep(delay)
    raise last_exc  # type: ignore[misc]


_TDX_MARKET_MAP = {
    "SH": 1,  # 上海
    "SZ": 0,  # 深圳
    "BJ": 2,  # 北京
}


def _market_code(symbol: str) -> int:
    """Map exchange from symbol suffix to pytdx market code (0=SZ, 1=SH, 2=BJ)."""
    _, exchange = split_astock_symbol(symbol)
    return _TDX_MARKET_MAP.get((exchange or "SH").upper(), 1)


# ── Adapter base (imported lazily to break circular dependency) ──────


def _get_base_class():
    """Lazy import of AStockAdapterBase to avoid circular imports with adapters.py."""
    from .adapters import AStockAdapterBase  # noqa: PLC0415
    return AStockAdapterBase


# ── Adapter ──────────────────────────────────────────────────────────


class TdxProvider:
    """TDX (通达信) market data provider via pytdx.

    This adapter implements the ``AStockAdapterBase`` capability interface
    so the router can use it as a drop-in alternative data source.
    """

    name = "tdx"

    def __init__(
        self,
        client: Any = None,
        timeout: Optional[float] = None,
        **config: Any,
    ):
        base = _get_base_class()
        base.__init__(self, client=client, timeout=timeout, **config)
        self._client = client
        self.timeout = (
            timeout
            if timeout is not None
            else _coerce_float(config.get("timeout") or _env("ASTOCK_TDX_TIMEOUT", "5"))
            or 5.0
        )
        self._host = config.get("host") or _env("ASTOCK_TDX_HOST", "119.147.212.81")
        self._port = int(config.get("port") or _env("ASTOCK_TDX_PORT", "7709") or 7709)
        self._use_multicast = (config.get("multicast") or _env("ASTOCK_TDX_MULTICAST", "false")).lower() == "true"
        # Pool of server addresses for fallback
        self._backup_hosts = (
            _env("ASTOCK_TDX_BACKUP_HOSTS")
            and [h.strip() for h in _env("ASTOCK_TDX_BACKUP_HOSTS").split(",")]
        ) or [
            "119.147.212.81",   # 主站
            "40.73.36.115",     # 备用
            "47.107.75.198",    # 备用
        ]

    def _unavailable(self, request: AStockRequest, detail: str = ""):
        raise AStockSourceUnavailableError(self.name, detail or "adapter not implemented", capability=request.capability)

    # ── Connection management ────────────────────────────────────────

    def _load_client(self) -> Any:
        """Lazy-load and connect the pytdx client.

        Returns
        -------
        Connected ``pytdx.hq.TdxHq_API`` instance.
        """
        if self._client is not None:
            return self._client

        try:
            from pytdx.hq import TdxHq_API  # type: ignore
        except ImportError:
            raise AStockSourceUnavailableError(
                self.name,
                "pytdx package is not installed — run 'pip install pytdx'",
            )

        # Try primary host first, then backup hosts
        hosts_to_try = [self._host] + [
            h for h in self._backup_hosts if h != self._host
        ]

        last_error: Optional[Exception] = None
        for host in hosts_to_try:
            try:
                api = TdxHq_API(multifast=not self._use_multicast)
                api.connect(host=host, port=self._port, timeout=self.timeout)
                self._client = api
                logger.info("tdx_provider: connected to %s:%s", host, self._port)
                return self._client
            except Exception as exc:
                last_error = exc
                logger.warning("tdx_provider: failed to connect to %s:%s — %s", host, self._port, exc)
                continue

        raise AStockSourceUnavailableError(
            self.name,
            "could not connect to any TDX server (tried {0}): {1}".format(
                len(hosts_to_try), last_error or "unknown"
            ),
        )

    def _disconnect(self) -> None:
        """Disconnect the pytdx client if connected."""
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception:
                pass
            self._client = None

    def _call(self, request: AStockRequest, method_name: str, **kwargs: Any) -> Any:
        """Execute a pytdx method with retry and backoff."""
        api = self._load_client()

        # Reconnect if connection was dropped
        try:
            api.get_security_list(1, 0)  # quick health check
        except Exception:
            logger.info("tdx_provider: reconnecting (health check failed)")
            self._disconnect()
            api = self._load_client()

        method = getattr(api, method_name, None)
        if method is None:
            raise AStockSourceUnavailableError(
                self.name,
                "pytdx method missing: {0}".format(method_name),
                capability=request.capability,
            )

        # Anti-crawling courtesy delay
        _random_sleep(0.2, 0.8)

        def _do_call() -> Any:
            return method(**kwargs)

        try:
            return _retry_with_backoff(
                _do_call,
                max_retries=2,
                base_delay=0.5,
                name="tdx." + method_name,
            )
        except AStockNoDataError:
            raise
        except AStockSourceUnavailableError:
            raise
        except Exception as exc:
            raise AStockSourceUnavailableError(
                self.name,
                "tdx {0} failed after retries: {1}".format(method_name, exc),
                capability=request.capability,
            )

    # ── Payload parsers ──────────────────────────────────────────────

    @staticmethod
    def _parse_tdx_bars(raw_bars: Any, request: AStockRequest) -> Dict[str, Any]:
        """Parse pytdx kline result into normalized bar dicts."""
        if not raw_bars:
            raise AStockNoDataError(
                request.raw_symbol,
                request.symbol,
                "tdx bars returned no rows",
                source="tdx",
                capability=request.capability,
            )

        bars: List[Dict[str, Any]] = []
        for row in raw_bars:
            if not row:
                continue
            # Determine if this is intraday (has hour/minute)
            year = getattr(row, "year", 0) or 0
            month = getattr(row, "month", 0) or 0
            day = getattr(row, "day", 0) or 0
            hour = getattr(row, "hour", 0) or 0
            minute = getattr(row, "minute", 0) or 0

            if hour or minute:
                date_str = "{0:04d}-{1:02d}-{2:02d} {3:02d}:{4:02d}:00".format(
                    year, month, day, hour, minute
                )
            else:
                date_str = "{0:04d}-{1:02d}-{2:02d}".format(year, month, day)

            open_px = _coerce_float(getattr(row, "open", None))
            high_px = _coerce_float(getattr(row, "high", None))
            low_px = _coerce_float(getattr(row, "low", None))
            close_px = _coerce_float(getattr(row, "close", None))
            vol = _coerce_float(getattr(row, "vol", None)) or _coerce_float(getattr(row, "volume", None))
            amt = _coerce_float(getattr(row, "amount", None))

            bars.append(
                {
                    "date": date_str,
                    "open": open_px,
                    "high": high_px,
                    "low": low_px,
                    "close": close_px,
                    "volume": vol,
                    "amount": amt,
                }
            )

        return {"bars": bars, "symbol": request.symbol, "interval": request.interval, "count": len(bars)}

    def _parse_quote_snapshot(self, raw_quote: Any, request: AStockRequest) -> Dict[str, Any]:
        """Parse a single pytdx quote result into a normalized snapshot dict."""
        if not raw_quote:
            raise AStockNoDataError(
                request.raw_symbol,
                request.symbol,
                "tdx quotes returned no data",
                source="tdx",
                capability=request.capability,
            )

        # pytdx get_security_quotes returns a list
        if isinstance(raw_quote, (list, tuple)) and len(raw_quote) > 0:
            row = raw_quote[0]
        else:
            row = raw_quote

        # Extract bid/ask levels
        bids: List[Dict[str, Any]] = []
        asks: List[Dict[str, Any]] = []
        for i in range(1, 6):
            bid_price = _coerce_float(
                _first_non_null(row, ("bid{0}".format(i), "bid_price{0}".format(i)))
            )
            bid_vol = _coerce_int(
                _first_non_null(row, ("bid_vol{0}".format(i), "bid_volume{0}".format(i)))
            )
            ask_price = _coerce_float(
                _first_non_null(row, ("ask{0}".format(i), "ask_price{0}".format(i)))
            )
            ask_vol = _coerce_int(
                _first_non_null(row, ("ask_vol{0}".format(i), "ask_volume{0}".format(i)))
            )
            if bid_price is not None:
                bids.append({"level": i, "price": bid_price, "volume": bid_vol or 0})
            if ask_price is not None:
                asks.append({"level": i, "price": ask_price, "volume": ask_vol or 0})

        return {
            "symbol": request.symbol,
            "code": _first_non_null(row, ("code", "stock_code"), astock_code(request.symbol)),
            "name": _first_non_null(row, ("name", "stock_name")),
            "price": _coerce_float(_first_non_null(row, ("price", "last_close", "close"))),
            "open": _coerce_float(_first_non_null(row, ("open",))),
            "pre_close": _coerce_float(_first_non_null(row, ("last_close", "pre_close", "y_close"))),
            "high": _coerce_float(_first_non_null(row, ("high",))),
            "low": _coerce_float(_first_non_null(row, ("low",))),
            "volume": _coerce_float(_first_non_null(row, ("vol", "volume", "cur_vol"))),
            "amount": _coerce_float(_first_non_null(row, ("amount", "turnover", "amt"))),
            "bids": bids,
            "asks": asks,
        }

    def _parse_transactions(self, raw_trans: Any, request: AStockRequest) -> Dict[str, Any]:
        """Parse pytdx transaction records."""
        if not raw_trans:
            raise AStockNoDataError(
                request.raw_symbol,
                request.symbol,
                "tdx transactions returned no rows",
                source="tdx",
                capability=request.capability,
            )

        items: List[Dict[str, Any]] = []
        for row in raw_trans:
            if not row:
                continue
            items.append(
                {
                    "time": "{0:02d}:{1:02d}".format(
                        getattr(row, "hour", 0) or 0,
                        getattr(row, "minute", 0) or 0,
                    ),
                    "price": _coerce_float(getattr(row, "price", None)),
                    "volume": _coerce_int(getattr(row, "vol", None)) or _coerce_int(getattr(row, "volume", None)),
                    "amount": _coerce_float(getattr(row, "amount", None)),
                }
            )

        return {"items": items, "count": len(items)}

    # ── Capability methods ───────────────────────────────────────────

    def get_kline(self, request: AStockRequest) -> Dict[str, Any]:
        """Fetch kline (historical bars) from TDX.

        Daily: uses ``get_k_data`` (adjusted). Intraday: uses
        ``get_minute_time_data`` / ``get_history_minute_time_data``.
        """
        code = astock_code(request.symbol)
        market = _market_code(request.symbol)
        interval = (request.interval or "1d").lower()

        if interval in ("1d", "day", "daily"):
            start_date = request.start_date or ""
            end_date = request.end_date or ""
            raw = self._call(
                request,
                "get_k_data",
                market=market,
                code=code,
                start=start_date,
                end=end_date,
                adjust="qfq",  # 前复权
            )
            return self._parse_tdx_bars(raw, request)

        # Intraday
        date_str = (request.end_date or datetime.now().strftime("%Y-%m-%d")).replace("-", "")
        try:
            raw = self._call(
                request,
                "get_minute_time_data",
                market=market,
                code=code,
                date=int(date_str) if date_str.isdigit() else 0,
            )
        except AStockSourceUnavailableError:
            try:
                raw = self._call(
                    request,
                    "get_history_minute_time_data",
                    market=market,
                    code=code,
                    date=int(date_str) if date_str.isdigit() else 0,
                )
            except Exception:
                # Fallback to daily kline
                raw = self._call(
                    request,
                    "get_k_data",
                    market=market,
                    code=code,
                    start=request.start_date or "",
                    end=request.end_date or "",
                    adjust="qfq",
                )
                return self._parse_tdx_bars(raw, request)

        return self._parse_tdx_bars(raw, request)

    def get_order_book(self, request: AStockRequest) -> Dict[str, Any]:
        """Fetch real-time snapshot / 盘口 from TDX."""
        code = astock_code(request.symbol)
        market = _market_code(request.symbol)

        raw = self._call(
            request,
            "get_security_quotes",
            codes=[(market, code)],
        )
        return self._parse_quote_snapshot(raw, request)

    def get_trade_tape(self, request: AStockRequest) -> Dict[str, Any]:
        """Fetch 逐笔成交 (transaction records) from TDX."""
        code = astock_code(request.symbol)
        market = _market_code(request.symbol)
        date_str = (request.extras.get("date") or datetime.now().strftime("%Y-%m-%d")).replace("-", "")
        start = int(request.extras.get("start", 0))
        limit = request.limit or request.extras.get("offset", 200)

        raw = self._call(
            request,
            "get_transaction_data",
            market=market,
            code=code,
            start=start,
            count=limit,
            date=int(date_str) if date_str.isdigit() else 0,
        )
        return self._parse_transactions(raw, request)

    # ── Stub methods required by router dispatch ─────────────────────

    def get_valuation(self, request: AStockRequest):
        return self._unavailable(request, "valuation not supported via TDX")

    def get_research_list(self, request: AStockRequest):
        return self._unavailable(request, "research not supported via TDX")

    def download_research_pdf(self, request: AStockRequest):
        return self._unavailable(request, "research not supported via TDX")

    def get_institution_expectation(self, request: AStockRequest):
        return self._unavailable(request, "research not supported via TDX")

    def search_research(self, request: AStockRequest):
        return self._unavailable(request, "research not supported via TDX")

    def get_stock_news(self, request: AStockRequest):
        return self._unavailable(request, "news not supported via TDX")

    def get_flash_news(self, request: AStockRequest):
        return self._unavailable(request, "news not supported via TDX")

    def get_global_news(self, request: AStockRequest):
        return self._unavailable(request, "news not supported via TDX")

    def get_quarterly_financials(self, request: AStockRequest):
        return self._unavailable(request, "financials not supported via TDX")

    def get_f10(self, request: AStockRequest):
        return self._unavailable(request, "F10 not supported via TDX")

    def get_fundamentals(self, request: AStockRequest):
        return self._unavailable(request, "fundamentals not supported via TDX")

    def get_announcement_full(self, request: AStockRequest):
        return self._unavailable(request, "announcements not supported via TDX")

    def get_announcement_summary(self, request: AStockRequest):
        return self._unavailable(request, "announcements not supported via TDX")

    def get_price_limit_status(self, request: AStockRequest):
        return self._unavailable(request, "price limit not supported via TDX")

    # ── Cleanup ──────────────────────────────────────────────────────

    def __del__(self):
        """Ensure connection is closed on garbage collection."""
        self._disconnect()
