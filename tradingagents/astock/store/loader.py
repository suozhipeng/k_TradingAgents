"""Provider → DuckDB data loaders.

Each loader class wraps an ``AStockStore`` and an ``AStockDataFacade`` (provider
router), fetching data from providers and writing it into DuckDB tables with
``INSERT OR REPLACE`` semantics for automatic deduplication.
"""

from __future__ import annotations

import logging
import multiprocessing
import os
import json
import pickle
import tempfile
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from queue import Empty
from typing import Any, Callable, Optional

import pandas as pd

from tradingagents.astock.data_sources.errors import (
    AStockDataError,
    AStockNoDataError,
    AStockSourceUnavailableError,
)
from .schema import AStockStore

logger = logging.getLogger(__name__)

_provider_process_gate: Any | None = None
_provider_process_gate_lock = threading.Lock()


def _get_provider_process_gate() -> threading.BoundedSemaphore:
    """Return the parent-owned cap for isolated provider processes.

    A spawned router has its own in-memory governor and cache.  Holding this
    lease in the API process keeps all child requests under one conservative
    upstream budget until a shared external governor is introduced.
    """
    global _provider_process_gate
    with _provider_process_gate_lock:
        if _provider_process_gate is None:
            limit = max(1, int(os.getenv("ASTOCK_ISOLATED_PROVIDER_MAX_CONCURRENCY", "1")))
            _provider_process_gate = threading.BoundedSemaphore(limit)
        return _provider_process_gate


def _fetch_response_worker(
    capability: str,
    symbol: str,
    start: str | None,
    end: str | None,
    interval: str,
    retries: int,
    timeout_seconds: float,
    output: Any,
    result_path: str,
) -> None:
    """Fetch in a fresh interpreter so a stuck provider can be terminated."""
    try:
        # Do not inherit a live router, DuckDB handle, or provider locks from
        # the web worker.  ``spawn`` imports this module afresh and the facade
        # is constructed from the canonical runtime configuration.
        from tradingagents.astock.data_sources.router import AStockDataFacade

        facade = AStockDataFacade()
        request_args = {
            "capability": capability,
            "symbol": symbol,
            "start_date": start,
            "end_date": end,
        }
        if capability == "kline":
            request_args["interval"] = interval
        response, retry_count = run_with_timeout_retries(
            lambda: facade.fetch(**request_args),
            retries=retries,
            deadline=time.monotonic() + timeout_seconds,
        )
        # Queue pipes are small; sending a DataFrame/report through one can
        # block process exit while the parent is waiting in join().  Persist
        # the payload first and keep Queue traffic to a tiny status message.
        # Prefer JSON for serializable data; fall back to pickle for
        # non-serializable types (numpy, pandas, etc.).
        try:
            with open(result_path, "w", encoding="utf-8") as handle:
                json.dump(response, handle, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            with open(result_path, "wb") as handle:
                pickle.dump(response, handle, protocol=pickle.HIGHEST_PROTOCOL)
        output.put(("ok", retry_count))
    except Exception as exc:
        output.put(("error", serialize_load_error(exc), getattr(exc, "retry_count", 0)))


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

    def __init__(self, store: AStockStore, data_facade: Any, *, permanent_store: Any = None) -> None:
        self._store = store
        self._facade = data_facade
        self._permanent_store = permanent_store

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
        rows = self._store.insert_kline(symbol, df, interval=interval, source=source)
        if self._permanent_store is not None and self._permanent_store is not self._store:
            from .permanent_kline import mirror_kline_frame
            mirror_kline_frame(self._permanent_store, symbol, df, interval=interval, source=source)
        return rows


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
        permanent_store: Any = None,
    ) -> None:
        self._store = store
        self._facade = data_facade
        self._kline_loader = KlineLoader(store, data_facade, permanent_store=permanent_store)
        self._valuation_loader = ValuationLoader(store, data_facade)
        configured_workers = max_workers or int(os.getenv("ASTOCK_NETWORK_MAX_CONCURRENCY", str(self.MAX_CONCURRENT_WORKERS)))
        self._max_workers = max(1, min(configured_workers, 5))

    def _fetch_response_isolated(
        self,
        symbol: str,
        start: str | None,
        end: str | None,
        interval: str,
        retries: int,
        timeout_seconds: float,
        cancelled: Callable[[], bool] | None = None,
        capability: str = "kline",
    ) -> tuple[Any, int]:
        """Fetch through a killable child process without inheriting locks.

        Thread cancellation cannot stop a provider call that has already
        started.  A short-lived forked worker gives the request deadline a
        real termination boundary while keeping DuckDB writes in the parent.
        """
        if (
            os.getenv("ASTOCK_TESTING") == "1"
            or os.getenv("ASTOCK_PROVIDER_PROCESS_ISOLATION", "true").lower() in {"0", "false", "no", "off"}
        ):
            return run_with_timeout_retries(
                lambda: (
                    self._kline_loader.fetch_response(symbol, start, end, interval)
                    if capability == "kline"
                    else self._valuation_loader.fetch_response(symbol, start, end)
                ),
                retries=retries,
                deadline=time.monotonic() + timeout_seconds,
            )
        context = multiprocessing.get_context("spawn")
        output = context.Queue(maxsize=1)
        result_file = tempfile.NamedTemporaryFile(prefix="astock-provider-", suffix=".pickle", delete=False)
        result_path = result_file.name
        result_file.close()
        gate = _get_provider_process_gate()
        if not gate.acquire(timeout=max(0.1, timeout_seconds)):
            os.unlink(result_path)
            raise TimeoutError("provider fetch timed out waiting for isolated capacity")
        worker = context.Process(
            target=_fetch_response_worker,
            args=(capability, symbol, start, end, interval, retries, timeout_seconds, output, result_path),
            daemon=True,
        )
        try:
            worker.start()
            deadline = time.monotonic() + timeout_seconds
            # Poll rather than a single blocking join so a cancelled data job
            # terminates an already-running provider request promptly.
            while worker.is_alive() and time.monotonic() < deadline:
                if cancelled is not None and cancelled():
                    worker.terminate()
                    worker.join(timeout=1)
                    raise TimeoutError("provider fetch cancelled")
                worker.join(timeout=min(0.1, max(0.0, deadline - time.monotonic())))
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=1)
                raise TimeoutError("provider fetch timed out")
            try:
                packet = output.get(timeout=0.2)
            except Empty as exc:
                raise RuntimeError("provider worker exited without a response") from exc
        finally:
            output.close()
            output.join_thread()
            gate.release()
            if "packet" not in locals() or packet[0] != "ok":
                if os.path.exists(result_path):
                    os.unlink(result_path)
        status = packet[0]
        if status == "ok":
            try:
                with open(result_path, "r", encoding="utf-8") as handle:
                    return json.load(handle), int(packet[1])
            except (json.JSONDecodeError, ValueError):
                with open(result_path, "rb") as handle:
                    return pickle.load(handle), int(packet[1])
            finally:
                if os.path.exists(result_path):
                    os.unlink(result_path)
        error = RuntimeError(str(packet[1].get("message", "provider fetch failed")))
        setattr(error, "retry_count", packet[2])
        raise error

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
        source: str = "", cancelled: Callable[[], bool] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Execute distinct K-line requests and retain per-item failures.

        This is intentionally separate from the legacy ``dict[str, int]``
        batch APIs so existing callers retain their compatibility contract.
        """
        timeout = max(1.0, float(timeout_seconds if timeout_seconds is not None else os.getenv("ASTOCK_JOB_TIMEOUT_SECONDS", "300")))
        deadline = time.monotonic() + timeout
        retries = int(timeout_retries if timeout_retries is not None else os.getenv("ASTOCK_KLINE_TIMEOUT_RETRIES", "3"))
        is_cancelled = cancelled or (lambda: False)

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
                if is_cancelled():
                    raise TimeoutError("provider fetch cancelled")
                response, result["retry_count"] = self._fetch_response_isolated(
                    symbol, item.get("start"), item.get("end"), interval,
                    retries, max(0.1, deadline - time.monotonic()), is_cancelled,
                )
                return key, result, response
            except Exception as exc:
                result.update({"status": "failed", "retry_count": getattr(exc, "retry_count", 0), "error": serialize_load_error(exc)})
                return key, result, None

        results: dict[str, dict[str, Any]] = {}
        # Threads coordinate concurrent jobs; each provider call itself runs
        # in a killable child process so timeout does not leave a blocked
        # third-party worker behind.
        executor = ThreadPoolExecutor(max_workers=self._max_workers if concurrent else 1)
        futures = {executor.submit(execute, item): item for item in requests}
        pending = set(futures)
        try:
            while pending and time.monotonic() < deadline:
                if is_cancelled():
                    break
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
                            if is_cancelled():
                                raise TimeoutError("provider fetch cancelled")
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
                    "error": {"code": "cancelled" if is_cancelled() else "timeout", "message": "refresh job cancelled" if is_cancelled() else "refresh job deadline exceeded", "retryable": not is_cancelled()},
                }
        finally:
            # Each executing task polls the cancellation callback and kills
            # its child process before this method returns.  Waiting here
            # prevents a cancelled job from retaining hidden provider work.
            executor.shutdown(wait=True, cancel_futures=True)
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
