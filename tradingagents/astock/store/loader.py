"""Provider → DuckDB data loaders.

Each loader class wraps an ``AStockStore`` and an ``AStockDataFacade`` (provider
router), fetching data from providers and writing it into DuckDB tables with
``INSERT OR REPLACE`` semantics for automatic deduplication.
"""

from __future__ import annotations

import logging
import os
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
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
    elif isinstance(exc, TimeoutError) or "deadline exceeded" in text or " timed out" in text:
        code, retryable = "timeout", True
    elif isinstance(exc, AStockNoDataError):
        code, retryable = "no_data", False
    elif isinstance(exc, AStockSourceUnavailableError):
        code, retryable = "source_unavailable", True
    elif isinstance(exc, ConnectionError):
        code, retryable = "network_error", True
    elif isinstance(exc, AStockDataError):
        code, retryable = str(exc.error_code).lower(), False
    else:
        code, retryable = "unexpected_error", False
    message = str(exc).replace("\n", " ").strip()[:300]
    return {"code": code, "message": message or code, "retryable": retryable}


def run_with_timeout_retries(
    operation: Any, *, retries: int, deadline: float | None = None
) -> tuple[Any, int]:
    """Retry only timeout failures, without allowing retries past *deadline*."""
    retries = max(0, min(int(retries), 3))
    attempt = 0
    while True:
        try:
            return operation(), attempt
        except Exception as exc:
            # Keep the actual retry count available to structured callers even
            # when the final failure is a provider-specific exception.
            try:
                setattr(exc, "retry_count", attempt)
            except Exception:
                pass
            if serialize_load_error(exc)["code"] != "timeout" or attempt >= retries:
                raise
            delay = 0.25 * (2 ** attempt)
            if deadline is not None and time.monotonic() + delay >= deadline:
                raise
            if os.getenv("ASTOCK_TESTING") != "1":
                time.sleep(delay)
            attempt += 1


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

    def fetch_response(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        interval: str = "1d",
    ) -> Any:
        """Fetch a K-line response without touching the shared DuckDB store."""
        try:
            return self._facade.fetch(
                capability="kline",
                symbol=symbol,
                start_date=start,
                end_date=end,
                interval=interval,
            )
        except AttributeError:
            return self._facade.get_kline(
                symbol=symbol,
                start_date=start,
                end_date=end,
                interval=interval,
            )

    def load(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        interval: str = "1d",
        source: str = "",
        deadline: float | None = None,
    ) -> int:
        """Fetch K-line for *symbol* and insert into DuckDB.

        Returns the number of rows inserted / replaced.
        """
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError("kline load deadline exceeded before provider request")
        response = self.fetch_response(symbol, start, end, interval)
        return self.write_response(
            symbol, response, interval=interval, source=source, deadline=deadline
        )

    def write_response(
        self,
        symbol: str,
        response: Any,
        *,
        interval: str = "1d",
        source: str = "",
        deadline: float | None = None,
    ) -> int:
        """Persist an already-fetched response from the caller thread only."""
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError("kline load deadline exceeded before database write")
        if response is None:
            logger.warning("No kline response for %s", symbol)
            return 0
        _raise_response_error(response, symbol, "kline")

        data = response.data if hasattr(response, "data") else response
        if isinstance(data, dict):
            bars = data.get("bars") or data.get("items") or data.get("kline")
        elif isinstance(data, pd.DataFrame):
            bars = data
        else:
            bars = None
        if bars is None:
            logger.warning("No kline bars in response for %s", symbol)
            return 0

        if isinstance(bars, pd.DataFrame):
            df = bars
        elif isinstance(bars, list) and bars and isinstance(bars[0], dict):
            df = pd.DataFrame(bars)
        else:
            df = None
        if df is None or df.empty:
            return 0

        if not source:
            source = getattr(response, "source", "") or ""
        return self._store.insert_kline(symbol, df, interval=interval, source=source)


# ---------------------------------------------------------------------------
# ValuationLoader
# ---------------------------------------------------------------------------


class ValuationLoader:
    """Load valuation data from providers into DuckDB."""

    def __init__(self, store: AStockStore, data_facade: Any) -> None:
        self._store = store
        self._facade = data_facade

    def fetch_response(
        self, symbol: str, start: str | None = None, end: str | None = None
    ) -> Any:
        """Fetch a valuation response without touching the shared DuckDB store."""
        try:
            return self._facade.fetch(
                capability="valuation",
                symbol=symbol,
                start_date=start,
                end_date=end,
            )
        except AttributeError:
            return self._facade.get_valuation(
                symbol=symbol, start_date=start, end_date=end
            )

    def load(
        self, symbol: str, start: str | None = None, end: str | None = None, source: str = ""
    ) -> int:
        """Fetch valuation data for *symbol* and insert into DuckDB."""
        response = self.fetch_response(symbol, start, end)
        return self.write_response(symbol, response, source=source)

    def write_response(self, symbol: str, response: Any, *, source: str = "") -> int:
        """Persist an already-fetched response from the caller thread only."""
        if response is None:
            return 0
        _raise_response_error(response, symbol, "valuation")

        data = response.data if hasattr(response, "data") else response
        if isinstance(data, dict):
            items = data.get("items") or data.get("valuations")
            if items is None and any(
                key in data for key in ("pe", "pb", "market_cap", "price", "symbol")
            ):
                items = [data]
        elif isinstance(data, pd.DataFrame):
            items = data
        else:
            items = None
        if items is None:
            return 0

        if isinstance(items, pd.DataFrame):
            df = items
        elif isinstance(items, list) and items and isinstance(items[0], dict):
            df = pd.DataFrame(items)
        else:
            df = None
        if df is None or df.empty:
            return 0

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
    MAX_CONCURRENT_WORKERS = 5

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
        configured_workers = max_workers or int(os.getenv("ASTOCK_NETWORK_MAX_CONCURRENCY", str(self.MAX_CONCURRENT_WORKERS)))
        self._max_workers = max(1, min(configured_workers, 5))

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
        details = self.load_kline_requests(
            [{"symbol": symbol, "start": start, "end": end, "interval": interval} for symbol in symbols],
            concurrent=True,
            source=source,
        )
        return {
            symbol: int(details[f"{symbol}:{interval}"].get("rows_upserted", -1))
            if details[f"{symbol}:{interval}"].get("status") == "succeeded" else -1
            for symbol in symbols
        }

    def load_kline_requests(
        self, requests: list[dict[str, Any]], *, concurrent: bool = False,
        timeout_seconds: float | None = None, timeout_retries: int | None = None,
        source: str = "",
    ) -> dict[str, dict[str, Any]]:
        """Execute distinct K-line requests and retain per-item failures.

        This is intentionally separate from the legacy ``dict[str, int]``
        batch APIs so existing callers retain their compatibility contract.
        """
        timeout = max(1.0, float(timeout_seconds if timeout_seconds is not None else os.getenv("ASTOCK_JOB_TIMEOUT_SECONDS", "300")))
        deadline = time.monotonic() + timeout
        retries = int(timeout_retries if timeout_retries is not None else os.getenv("ASTOCK_KLINE_TIMEOUT_RETRIES", "3"))

        def execute(item: dict[str, Any]) -> tuple[str, dict[str, Any], Any | None]:
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
                response, result["retry_count"] = run_with_timeout_retries(
                    lambda: self._kline_loader.fetch_response(
                        symbol, item.get("start"), item.get("end"), interval
                    ),
                    retries=retries, deadline=deadline,
                )
                return key, result, response
            except Exception as exc:
                result.update({"status": "failed", "retry_count": getattr(exc, "retry_count", 0), "error": serialize_load_error(exc)})
                return key, result, None

        results: dict[str, dict[str, Any]] = {}
        # Even a one-symbol refresh uses this bounded executor so a provider
        # call can be reported as timed out instead of blocking the job route
        # indefinitely.  The underlying adapters also set socket timeouts.
        executor = ThreadPoolExecutor(max_workers=self._max_workers if concurrent else 1)
        futures = {executor.submit(execute, item): item for item in requests}
        pending = set(futures)
        try:
            while pending and time.monotonic() < deadline:
                done, pending = wait(
                    pending,
                    timeout=min(0.25, max(0.0, deadline - time.monotonic())),
                    return_when=FIRST_COMPLETED,
                )
                for future in done:
                    key, result, response = future.result()
                    if result["status"] == "succeeded":
                        item = futures[future]
                        try:
                            result["rows_upserted"] = self._kline_loader.write_response(
                                str(item["symbol"]),
                                response,
                                interval=str(item.get("interval", "1d")),
                                source=source,
                                deadline=deadline,
                            )
                        except Exception as exc:
                            result.update({
                                "status": "failed",
                                "error": serialize_load_error(exc),
                            })
                    results[key] = result
            for future in pending:
                item = futures[future]
                key = "{0}:{1}".format(item["symbol"], item.get("interval", "1d"))
                future.cancel()
                results[key] = {
                    "requested_start": item.get("start"), "requested_end": item.get("end"),
                    "rows_upserted": 0, "status": "failed", "retry_count": 0,
                    "error": {"code": "timeout", "message": "refresh job deadline exceeded", "retryable": True},
                }
        finally:
            # Do not block the request thread on a third-party call that has
            # already exceeded its deadline; HTTP adapters still carry their
            # own socket timeouts.
            executor.shutdown(wait=False, cancel_futures=True)
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
            future_map = {
                executor.submit(self._valuation_loader.fetch_response, sym, start, end): sym
                for sym in symbols
            }
            for future in as_completed(future_map):
                sym = future_map[future]
                try:
                    response = future.result()
                    results[sym] = self._valuation_loader.write_response(
                        sym, response, source=source
                    )
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
