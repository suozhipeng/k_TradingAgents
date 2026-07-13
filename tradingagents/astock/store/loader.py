"""Provider → DuckDB data loaders.

Each loader class wraps an ``AStockStore`` and an ``AStockDataFacade`` (provider
router), fetching data from providers and writing it into DuckDB tables with
``INSERT OR REPLACE`` semantics for automatic deduplication.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

import pandas as pd

from tradingagents.astock.data_sources.errors import (
    AStockDataError,
    AStockNoDataError,
    AStockSourceUnavailableError,
)
from .schema import AStockStore

logger = logging.getLogger(__name__)


def serialize_load_error(exc: Exception) -> dict[str, Any]:
    """Return a stable, safe error envelope for async refresh clients."""
    text = str(exc).lower()
    if any(token in text for token in ("429", "rate limit", "too many request", "请求过于频繁", "访问频繁")):
        code, retryable = "rate_limited", True
    elif isinstance(exc, AStockNoDataError):
        code, retryable = "no_data", False
    elif isinstance(exc, AStockSourceUnavailableError):
        code, retryable = "source_unavailable", True
    elif isinstance(exc, (TimeoutError, ConnectionError)):
        code, retryable = "network_error", True
    elif isinstance(exc, AStockDataError):
        code, retryable = str(exc.error_code).lower(), False
    else:
        code, retryable = "unexpected_error", False
    message = str(exc).replace("\n", " ").strip()[:300]
    return {"code": code, "message": message or code, "retryable": retryable}


def _raise_response_error(response: Any, symbol: str, capability: str) -> None:
    status = getattr(response, "status", None)
    if status == "empty":
        raise AStockNoDataError(
            symbol,
            detail=str(getattr(response, "error_message", None) or "provider returned no rows"),
            source=getattr(response, "source", None),
            capability=capability,
        )
    if status != "error":
        return
    source = getattr(response, "source", None) or "router"
    detail = getattr(response, "error_message", None) or "provider request failed"
    raise AStockSourceUnavailableError(str(source), str(detail), capability=capability)

# ---------------------------------------------------------------------------
# KlineLoader
# ---------------------------------------------------------------------------


class KlineLoader:
    """Load K-line data from providers into DuckDB.

    Parameters
    ----------
    store : AStockStore
        Target DuckDB database.
    data_facade : Any
        An ``AStockDataFacade`` (or compatible object) that has ``fetch()``
        or ``get_kline()`` capabilities.
    """

    def __init__(self, store: AStockStore, data_facade: Any) -> None:
        self._store = store
        self._facade = data_facade

    def load(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        interval: str = "1d",
        source: str = "",
    ) -> int:
        """Fetch K-line for *symbol* and insert into DuckDB.

        Returns the number of rows inserted / replaced.
        """
        try:
            response = self._facade.fetch(
                capability="kline",
                symbol=symbol,
                start_date=start,
                end_date=end,
                interval=interval,
            )
        except AttributeError:
            # Fallback: try get_kline directly
            response = self._facade.get_kline(
                symbol=symbol,
                start_date=start,
                end_date=end,
                interval=interval,
            )

        if response is None:
            logger.warning("No kline response for %s", symbol)
            return 0
        _raise_response_error(response, symbol, "kline")

        data = response
        if hasattr(response, "data"):
            data = response.data

        bars = None
        if isinstance(data, dict):
            bars = data.get("bars") or data.get("items")
            if bars is None:
                # try direct dict with date keys
                bars = data.get("kline")
        elif isinstance(data, pd.DataFrame):
            bars = data

        if bars is None:
            logger.warning("No kline bars in response for %s", symbol)
            return 0

        df: pd.DataFrame | None = None
        if isinstance(bars, pd.DataFrame):
            df = bars
        elif isinstance(bars, list) and len(bars) > 0:
            if isinstance(bars[0], dict):
                df = pd.DataFrame(bars)

        if df is None or df.empty:
            return 0

        # Ensure source
        if not source:
            try:
                if hasattr(response, "source") and response.source:
                    source = response.source
            except Exception:
                pass

        return self._store.insert_kline(
            symbol, df, interval=interval, source=source
        )


# ---------------------------------------------------------------------------
# ValuationLoader
# ---------------------------------------------------------------------------


class ValuationLoader:
    """Load valuation data from providers into DuckDB."""

    def __init__(self, store: AStockStore, data_facade: Any) -> None:
        self._store = store
        self._facade = data_facade

    def load(
        self, symbol: str, start: str | None = None, end: str | None = None, source: str = ""
    ) -> int:
        """Fetch valuation data for *symbol* and insert into DuckDB."""
        try:
            response = self._facade.fetch(
                capability="valuation",
                symbol=symbol,
                start_date=start,
                end_date=end,
            )
        except AttributeError:
            response = self._facade.get_valuation(
                symbol=symbol, start_date=start, end_date=end
            )

        if response is None:
            return 0
        _raise_response_error(response, symbol, "valuation")

        data = response
        if hasattr(response, "data"):
            data = response.data

        items = None
        if isinstance(data, dict):
            items = data.get("items") or data.get("valuations")
            # Flat dict (single snapshot) — wrap as single-row list
            if items is None and any(
                k in data for k in ("pe", "pb", "market_cap", "price", "symbol")
            ):
                items = [data]
        elif isinstance(data, pd.DataFrame):
            items = data

        if items is None:
            return 0

        df: pd.DataFrame | None = None
        if isinstance(items, pd.DataFrame):
            df = items
        elif isinstance(items, list) and len(items) > 0:
            if isinstance(items[0], dict):
                df = pd.DataFrame(items)

        if df is None or df.empty:
            return 0

        # Flat-snapshot records may not have trade_date — add today's date
        if "trade_date" not in df.columns and "date" not in df.columns:
            from datetime import date
            df["trade_date"] = date.today()

        return self._store.insert_valuations(symbol, df, source=source)


# ---------------------------------------------------------------------------
# BatchLoader
# ---------------------------------------------------------------------------


class BatchLoader:
    """Batch-load multiple symbols / time ranges into DuckDB.

    Parameters
    ----------
    store : AStockStore
    data_facade : Any
    """

    # Workers improve throughput; the router owns provider-wide request
    # concurrency and pacing, so a batch cannot bypass anti-crawl limits.
    MAX_CONCURRENT_WORKERS = 4

    def __init__(
        self,
        store: AStockStore,
        data_facade: Any,
        *,
        max_workers: int | None = None,
    ) -> None:
        self._store = store
        self._facade = data_facade
        self._kline_loader = KlineLoader(store, data_facade)
        self._valuation_loader = ValuationLoader(store, data_facade)
        self._max_workers = max_workers or self.MAX_CONCURRENT_WORKERS

    def load_kline_batch(
        self,
        symbols: list[str],
        start: str | None = None,
        end: str | None = None,
        interval: str = "1d",
        source: str = "",
    ) -> dict[str, int]:
        """Load K-line for multiple symbols (serial).

        Returns ``{symbol: row_count}``.
        """
        results: dict[str, int] = {}
        for symbol in symbols:
            try:
                count = self._kline_loader.load(symbol, start, end, interval, source)
                results[symbol] = count
            except Exception as exc:
                logger.warning("Failed to load kline for %s: %s", symbol, exc)
                results[symbol] = -1
        return results

    def load_kline_batch_concurrent(
        self,
        symbols: list[str],
        start: str | None = None,
        end: str | None = None,
        interval: str = "1d",
        source: str = "",
    ) -> dict[str, int]:
        """Load K-line for multiple symbols (concurrent).

        Each symbol is fetched in a separate thread. The shared provider
        governor applies the actual upstream concurrency and pacing limits.

        Returns ``{symbol: row_count}``.
        """
        results: dict[str, int] = {}

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_map: dict[Any, str] = {}
            for sym in symbols:
                future_map[
                    executor.submit(
                        self._kline_loader.load, sym, start, end, interval, source
                    )
                ] = sym

            for future in as_completed(future_map):
                sym = future_map[future]
                try:
                    results[sym] = future.result()
                except Exception as exc:
                    logger.warning("Failed to load kline for %s: %s", sym, exc)
                    results[sym] = -1
        return results

    def load_kline_requests(
        self, requests: list[dict[str, Any]], *, concurrent: bool = False
    ) -> dict[str, dict[str, Any]]:
        """Execute distinct K-line requests and retain per-item failures.

        This is intentionally separate from the legacy ``dict[str, int]``
        batch APIs so existing callers retain their compatibility contract.
        """
        def execute(item: dict[str, Any]) -> tuple[str, dict[str, Any]]:
            symbol = str(item["symbol"])
            interval = str(item.get("interval", "1d"))
            key = f"{symbol}:{interval}"
            result = {
                "requested_start": item.get("start"),
                "requested_end": item.get("end"),
                "rows_upserted": 0,
                "status": "succeeded",
            }
            try:
                result["rows_upserted"] = self._kline_loader.load(
                    symbol, item.get("start"), item.get("end"), interval
                )
            except Exception as exc:
                result.update({"status": "failed", "error": serialize_load_error(exc)})
            return key, result

        results: dict[str, dict[str, Any]] = {}
        if not concurrent:
            for item in requests:
                key, result = execute(item)
                results[key] = result
            return results
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futures = [executor.submit(execute, item) for item in requests]
            for future in as_completed(futures):
                key, result = future.result()
                results[key] = result
        return results

    def load_valuations_batch(
        self,
        symbols: list[str],
        start: str | None = None,
        end: str | None = None,
        source: str = "",
    ) -> dict[str, int]:
        """Load valuations for multiple symbols (serial)."""
        results: dict[str, int] = {}
        for symbol in symbols:
            try:
                count = self._valuation_loader.load(symbol, start, end, source)
                results[symbol] = count
            except Exception as exc:
                logger.warning("Failed to load valuations for %s: %s", symbol, exc)
                results[symbol] = -1
        return results

    def load_valuations_batch_concurrent(
        self,
        symbols: list[str],
        start: str | None = None,
        end: str | None = None,
        source: str = "",
    ) -> dict[str, int]:
        """Load valuations for multiple symbols (concurrent)."""
        results: dict[str, int] = {}

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_map: dict[Any, str] = {}
            for sym in symbols:
                future_map[
                    executor.submit(
                        self._valuation_loader.load, sym, start, end, source
                    )
                ] = sym

            for future in as_completed(future_map):
                sym = future_map[future]
                try:
                    results[sym] = future.result()
                except Exception as exc:
                    logger.warning("Failed to load valuations for %s: %s", sym, exc)
                    results[sym] = -1
        return results

    def load_all(
        self,
        symbols: list[str],
        kline_start: str | None = None,
        kline_end: str | None = None,
        interval: str = "1d",
        concurrent: bool = False,
    ) -> dict[str, Any]:
        """Load both K-line and valuations for all symbols.

        Parameters
        ----------
        concurrent : bool
            If True, use ``ThreadPoolExecutor`` to fetch symbols in parallel.
            Each thread still respects per-adapter anti-crawl delays, so
            concurrency speeds up total wall-clock time without triggering
            rate limits.
        """
        kline_fn = (
            self.load_kline_batch_concurrent
            if concurrent
            else self.load_kline_batch
        )
        val_fn = (
            self.load_valuations_batch_concurrent
            if concurrent
            else self.load_valuations_batch
        )
        return {
            "kline": kline_fn(symbols, kline_start, kline_end, interval),
            "valuations": val_fn(symbols, kline_start, kline_end),
        }
