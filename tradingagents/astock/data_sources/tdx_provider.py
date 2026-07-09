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
from .tdx_vipdoc import TdxVipdocReader
from .tdx_cache import TdxCache

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
        vipdoc_path: Optional[str] = None,
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
        # VIPDOC reader for local file access
        self._vipdoc_reader: Optional[TdxVipdocReader] = None
        self._vipdoc_path = vipdoc_path or os.environ.get("ASTOCK_TDX_VIPDOC_PATH")
        # Cache layer
        self._cache: Optional[TdxCache] = None
        self._cache_enabled = True
        if os.environ.get("ASTOCK_TDX_CACHE_DISABLE", "").lower() in ("1", "true", "yes"):
            self._cache_enabled = False

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
                api = TdxHq_API()
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

    def _get_vipdoc_reader(self) -> Optional[TdxVipdocReader]:
        """Lazy-init the local vipdoc reader.

        Returns ``None`` if the vipdoc path is not configured or the directory
        does not exist, so callers can degrade gracefully.
        """
        if self._vipdoc_reader is not None:
            return self._vipdoc_reader

        if not self._vipdoc_path:
            return None

        try:
            self._vipdoc_reader = TdxVipdocReader(tdx_path=self._vipdoc_path)
            # Quick probe to verify the path is valid
            _ = self._vipdoc_reader.base_path
            return self._vipdoc_reader
        except Exception as exc:
            logger.debug("tdx_provider: vipdoc reader init skipped (%s)", exc)
            return None

    def _get_cache(self) -> Optional[TdxCache]:
        """Lazy-init the local TDX cache layer.

        Returns ``None`` if caching is disabled or init fails.
        """
        if not self._cache_enabled:
            return None
        if self._cache is not None:
            return self._cache
        try:
            self._cache = TdxCache()
            return self._cache
        except Exception as exc:
            logger.debug("tdx_provider: cache init skipped (%s)", exc)
            return None

    def _disconnect(self) -> None:
        """Disconnect the pytdx client if connected."""
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception as e:

                logger.debug("Operation failed: {0}", e)

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

        Resolution order (daily only):
          1. Local vipdoc file (fastest, no network)
          2. Local cache (SQLite/CSV)
          3. pytdx online query
          4. Write successful online result to cache

        Intraday data is fetched via pytdx online only (vipdoc minute
        files are less commonly available in standard installations).
        """
        code = astock_code(request.symbol)
        market = _market_code(request.symbol)
        interval = (request.interval or "1d").lower()
        is_daily = interval in ("1d", "day", "daily")

        # ── Try 1: Local vipdoc file (daily only) ─────────────────────
        if is_daily:
            vipdoc_reader = self._get_vipdoc_reader()
            if vipdoc_reader is not None:
                try:
                    logger.debug(
                        "tdx_provider: trying vipdoc for %s %s",
                        request.symbol, interval,
                    )
                    records = vipdoc_reader.read_daily_kline(request.symbol)
                    # Filter by date range if specified
                    from .tdx_vipdoc import _filter_by_date_range as _vipdoc_filter
                    if request.start_date or request.end_date:
                        records = _vipdoc_filter(
                            records, request.start_date or "", request.end_date or ""
                        )
                    if records:
                        result = {
                            "bars": records,
                            "count": len(records),
                            "symbol": request.symbol,
                            "interval": interval,
                            "source": "tdx_vipdoc",
                        }
                        logger.info(
                            "tdx_provider: vipdoc hit for %s (%d bars)",
                            request.symbol, len(records),
                        )
                        return result
                except (AStockNoDataError, AStockSourceUnavailableError) as exc:
                    logger.debug(
                        "tdx_provider: vipdoc miss for %s — %s",
                        request.symbol, exc,
                    )
                except Exception as exc:
                    logger.debug(
                        "tdx_provider: vipdoc error for %s — %s",
                        request.symbol, exc,
                    )

        # ── Try 2: Local cache ────────────────────────────────────────
        cache = self._get_cache()
        if cache is not None:
            try:
                cached_data = cache.get(request.symbol, "kline", interval)
                if cached_data is not None:
                    # Strip _meta before returning
                    meta = cached_data.pop("_meta", None)
                    source_label = (meta or {}).get("source", "cache")
                    bars = cached_data.get("bars", [])
                    if bars:
                        logger.info(
                            "tdx_provider: cache hit for %s %s (%d bars, source=%s)",
                            request.symbol, interval, len(bars), source_label,
                        )
                        return {
                            "bars": bars,
                            "count": len(bars),
                            "symbol": request.symbol,
                            "interval": interval,
                            "source": source_label,
                            "cached": True,
                        }
            except Exception as exc:
                logger.debug("tdx_provider: cache read error — %s", exc)

        # ── Try 3: pytdx online query ─────────────────────────────────
        if is_daily:
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
            result = self._parse_tdx_bars(raw, request)

            # Write to cache after successful online fetch
            if cache is not None:
                try:
                    cache.set(
                        request.symbol, "kline", interval, result, source="tdx_pytdx"
                    )
                    logger.debug(
                        "tdx_provider: cached online result for %s %s",
                        request.symbol, interval,
                    )
                except Exception as exc:
                    logger.debug("tdx_provider: cache write error — %s", exc)

            return result

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
                result = self._parse_tdx_bars(raw, request)
                # Also cache the fallback daily result
                if cache is not None:
                    try:
                        cache.set(
                            request.symbol, "kline", "1d", result, source="tdx_pytdx"
                        )
                    except Exception as e:

                        logger.debug("Operation failed: {0}", e)

                return result

        result = self._parse_tdx_bars(raw, request)

        # Cache intraday results too
        if cache is not None:
            try:
                cache.set(
                    request.symbol, "kline", interval, result, source="tdx_pytdx"
                )
            except Exception as e:

                logger.debug("Operation failed: {0}", e)


        return result

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

    # ── Capability methods: valuation / price_limit / f10 / fundamentals ──

    def get_valuation(self, request: AStockRequest):
        """Fetch PE, PB, market cap from TDX via get_security_quotes."""
        code = astock_code(request.symbol)
        market = _market_code(request.symbol)
        raw = self._call(request, "get_security_quotes", codes=[(market, code)])
        if isinstance(raw, (list, tuple)) and len(raw) > 0:
            row = raw[0]
        else:
            row = raw

        last_close = _coerce_float(_first_non_null(row, ("last_close",)))
        capitalization = _coerce_float(_first_non_null(row, ("capitalization",)))
        flow_capitalization = _coerce_float(_first_non_null(row, ("flow_capitalization",)))

        market_cap = capitalization * last_close if capitalization and last_close else None
        float_cap = flow_capitalization * last_close if flow_capitalization and last_close else None

        return {
            "symbol": request.symbol,
            "pe": _coerce_float(_first_non_null(row, ("pe",))),
            "pb": _coerce_float(_first_non_null(row, ("pb",))),
            "market_cap": market_cap,
            "float_cap": float_cap,
            "capitalization": capitalization,
            "flow_capitalization": flow_capitalization,
            "last_close": last_close,
        }

    def get_price_limit_status(self, request: AStockRequest):
        """Fetch 涨跌停 prices from TDX via get_security_quotes."""
        code = astock_code(request.symbol)
        market = _market_code(request.symbol)
        raw = self._call(request, "get_security_quotes", codes=[(market, code)])
        if isinstance(raw, (list, tuple)) and len(raw) > 0:
            row = raw[0]
        else:
            row = raw

        up_price = _coerce_float(_first_non_null(row, ("up_limit",)))
        down_price = _coerce_float(_first_non_null(row, ("down_limit",)))
        price = _coerce_float(_first_non_null(row, ("price", "last_close", "close")))

        return {
            "symbol": request.symbol,
            "up_price": up_price,
            "down_price": down_price,
            "is_limit_up": price is not None and up_price is not None and price >= up_price,
            "is_limit_down": price is not None and down_price is not None and price <= down_price,
            "price": price,
        }

    def get_f10(self, request: AStockRequest):
        """Fetch F10 company profile via pytdx get_company_info_Ex + get_finance_info."""
        code = astock_code(request.symbol)
        market = _market_code(request.symbol)

        company_info = self._call(request, "get_company_info_Ex", market=market, code=code)
        finance_info = self._call(request, "get_finance_info", market=market, code=code)

        result: Dict[str, Any] = {"symbol": request.symbol, "code": code}

        if company_info:
            crow = company_info[0] if isinstance(company_info, (list, tuple)) and len(company_info) > 0 else company_info
            result["company_name"] = _first_non_null(crow, ("name", "company_name", "zqmc"), "")
            result["listing_date"] = _first_non_null(crow, ("listing_date", "ssrq"), "")
            result["industry"] = _first_non_null(crow, ("industry", "hy"), "")
            result["business_scope"] = _first_non_null(crow, ("business_scope", "jyfw"), "")
            result["total_shares"] = _coerce_float(_first_non_null(crow, ("total_shares", "zgb")))

        if finance_info:
            frow = finance_info[0] if isinstance(finance_info, (list, tuple)) and len(finance_info) > 0 else finance_info
            result["eps"] = _coerce_float(_first_non_null(frow, ("eps", "meigu")))
            result["net_asset_per_share"] = _coerce_float(_first_non_null(frow, ("net_asset_per_share", "jingzichan")))
            result["total_equity"] = _coerce_float(_first_non_null(frow, ("total_equity", "jingli", "gudong")))
            result["total_revenue"] = _coerce_float(_first_non_null(frow, ("total_revenue", "shouyi")))
            result["net_profit"] = _coerce_float(_first_non_null(frow, ("net_profit", "jinglilirun")))
            result["operating_revenue"] = _coerce_float(_first_non_null(frow, ("operating_revenue", "zhuyinglirun")))

        return result

    def get_fundamentals(self, request: AStockRequest):
        """Fetch fundamental indicators via pytdx get_finance_info."""
        code = astock_code(request.symbol)
        market = _market_code(request.symbol)

        raw = self._call(request, "get_finance_info", market=market, code=code)
        if isinstance(raw, (list, tuple)) and len(raw) > 0:
            row = raw[0]
        else:
            row = raw

        return {
            "symbol": request.symbol,
            "eps": _coerce_float(_first_non_null(row, ("eps", "meigu"))),
            "net_asset_per_share": _coerce_float(_first_non_null(row, ("net_asset_per_share", "jingzichan"))),
            "total_equity": _coerce_float(_first_non_null(row, ("total_equity", "jingli", "gudong"))),
            "total_revenue": _coerce_float(_first_non_null(row, ("total_revenue", "shouyi"))),
            "net_profit": _coerce_float(_first_non_null(row, ("net_profit", "jinglilirun"))),
            "total_shares": _coerce_float(_first_non_null(row, ("total_shares", "zongguben"))),
            "current_assets": _coerce_float(_first_non_null(row, ("current_assets", "liudong"))),
            "total_liabilities": _coerce_float(_first_non_null(row, ("total_liabilities", "fuzhai"))),
            "investment_income": _coerce_float(_first_non_null(row, ("investment_income", "touzishouyi"))),
            "operating_profit": _coerce_float(_first_non_null(row, ("operating_profit", "yingyeshang"))),
        }

    def get_quarterly_financials(self, request: AStockRequest):
        """Fetch quarterly financial data via pytdx get_finance_info."""
        code = astock_code(request.symbol)
        market = _market_code(request.symbol)

        raw = self._call(request, "get_finance_info", market=market, code=code)
        if isinstance(raw, (list, tuple)) and len(raw) > 0:
            row = raw[0]
        else:
            row = raw

        return {
            "symbol": request.symbol,
            "total_revenue": _coerce_float(_first_non_null(row, ("total_revenue", "shouyi"))),
            "net_profit": _coerce_float(_first_non_null(row, ("net_profit", "jinglilirun"))),
            "operating_revenue": _coerce_float(_first_non_null(row, ("operating_revenue", "zhuyinglirun"))),
            "investment_income": _coerce_float(_first_non_null(row, ("investment_income", "touzishouyi"))),
            "total_assets": _coerce_float(_first_non_null(row, ("total_assets", "zichanghd"))),
            "total_equity": _coerce_float(_first_non_null(row, ("total_equity", "jingli"))),
            "total_liabilities": _coerce_float(_first_non_null(row, ("total_liabilities", "fuzhai"))),
            "eps": _coerce_float(_first_non_null(row, ("eps", "meigu"))),
            "retained_earnings": _coerce_float(_first_non_null(row, ("retained_earnings", "baoliu1"))),
        }

    # ── Announcement / news via pytdx ────────────────────────────────

    def get_announcement_full(self, request: AStockRequest):
        """Fetch full announcements/news via pytdx get_company_news_content."""
        code = astock_code(request.symbol)
        market = _market_code(request.symbol)

        news_count = self._call(request, "get_company_news_count", market=market, code=code)
        total = (
            _coerce_int(news_count)
            if not isinstance(news_count, (list, tuple))
            else _coerce_int(news_count[0]) if news_count else 0
        ) or 0

        page = request.page or 1
        limit = request.limit or 20

        news_content = self._call(
            request, "get_company_news_content", market=market, code=code, page=page, count=limit
        )

        items: List[Dict[str, Any]] = []
        if news_content:
            rows = news_content if isinstance(news_content, (list, tuple)) else [news_content]
            for row in rows:
                if not row:
                    continue
                items.append({
                    "title": _first_non_null(row, ("title",), ""),
                    "date": _first_non_null(row, ("datetime", "date"), ""),
                    "content": _first_non_null(row, ("content",), ""),
                    "url": _first_non_null(row, ("url",), ""),
                })

        return {"items": items, "count": len(items), "total": total or len(items)}

    def get_announcement_summary(self, request: AStockRequest):
        """Fetch announcement summary/news headlines via pytdx."""
        code = astock_code(request.symbol)
        market = _market_code(request.symbol)

        news_count = self._call(request, "get_company_news_count", market=market, code=code)
        total = (
            _coerce_int(news_count)
            if not isinstance(news_count, (list, tuple))
            else _coerce_int(news_count[0]) if news_count else 0
        ) or 0

        page = request.page or 1
        limit = request.limit or 20

        news_content = self._call(
            request, "get_company_news_content", market=market, code=code, page=page, count=limit
        )

        items: List[Dict[str, Any]] = []
        if news_content:
            rows = news_content if isinstance(news_content, (list, tuple)) else [news_content]
            for row in rows:
                if not row:
                    continue
                content = _first_non_null(row, ("content",), "")
                items.append({
                    "title": _first_non_null(row, ("title",), ""),
                    "date": _first_non_null(row, ("datetime", "date"), ""),
                    "summary": content[:200] if content else "",
                })

        return {"items": items, "count": len(items), "total": total or len(items)}

    # ── Index / market summary ───────────────────────────────────────

    def get_market_summary(self, request: AStockRequest):
        """Fetch major index summaries via pytdx get_security_quotes."""
        indices = [
            (1, "000001"),  # 上证指数
            (0, "399001"),  # 深证成指
            (0, "399300"),  # 沪深300
            (0, "399006"),  # 创业板指
        ]

        raw = self._call(request, "get_security_quotes", codes=indices)

        items: List[Dict[str, Any]] = []
        if raw:
            for row in raw if isinstance(raw, (list, tuple)) else [raw]:
                if not row:
                    continue
                name = _first_non_null(row, ("name",), "")
                price = _coerce_float(_first_non_null(row, ("price",)))
                last_close = _coerce_float(_first_non_null(row, ("last_close",)))
                change_pct = (
                    round((price - last_close) / last_close * 100, 2)
                    if price is not None and last_close is not None and last_close != 0
                    else None
                )
                items.append({
                    "code": _first_non_null(row, ("code",), ""),
                    "name": name,
                    "price": price,
                    "change_pct": change_pct,
                    "open": _coerce_float(_first_non_null(row, ("open",))),
                    "high": _coerce_float(_first_non_null(row, ("high",))),
                    "low": _coerce_float(_first_non_null(row, ("low",))),
                    "volume": _coerce_float(_first_non_null(row, ("vol", "volume"))),
                    "amount": _coerce_float(_first_non_null(row, ("amount",))),
                })

        return {"items": items, "count": len(items)}

    # ── Sector / industry data ───────────────────────────────────────

    def get_sector_data(self, request: AStockRequest):
        """Fetch sector/industry list via pytdx get_and_parse_block_info."""
        raw = self._call(request, "get_and_parse_block_info")

        items: List[Dict[str, Any]] = []
        if raw:
            for row in raw if isinstance(raw, (list, tuple)) else [raw]:
                if not row:
                    continue
                items.append({
                    "sector_code": _first_non_null(row, ("code", "block_code"), ""),
                    "sector_name": _first_non_null(row, ("name", "block_name"), ""),
                    "sector_type": _first_non_null(row, ("type", "block_type"), ""),
                })

        return {"items": items, "count": len(items)}

    # ── Stub methods — TDX can't provide these, keep as _unavailable ─
    # (research, news, etc.)

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

    # ── Cleanup ──────────────────────────────────────────────────────

    def __del__(self):
        """Ensure connection is closed on garbage collection."""
        self._disconnect()
