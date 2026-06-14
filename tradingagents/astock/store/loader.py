"""Provider → DuckDB data loaders.

Each loader class wraps an ``AStockStore`` and an ``AStockDataFacade`` (provider
router), fetching data from providers and writing it into DuckDB tables with
``INSERT OR REPLACE`` semantics for automatic deduplication.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import pandas as pd

from .schema import AStockStore

logger = logging.getLogger(__name__)

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

        data = response
        if hasattr(response, "data"):
            data = response.data

        items = None
        if isinstance(data, dict):
            items = data.get("items") or data.get("valuations")
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

    def __init__(self, store: AStockStore, data_facade: Any) -> None:
        self._store = store
        self._facade = data_facade
        self._kline_loader = KlineLoader(store, data_facade)
        self._valuation_loader = ValuationLoader(store, data_facade)

    def load_kline_batch(
        self,
        symbols: list[str],
        start: str | None = None,
        end: str | None = None,
        interval: str = "1d",
        source: str = "",
    ) -> dict[str, int]:
        """Load K-line for multiple symbols.

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

    def load_valuations_batch(
        self,
        symbols: list[str],
        start: str | None = None,
        end: str | None = None,
        source: str = "",
    ) -> dict[str, int]:
        """Load valuations for multiple symbols."""
        results: dict[str, int] = {}
        for symbol in symbols:
            try:
                count = self._valuation_loader.load(symbol, start, end, source)
                results[symbol] = count
            except Exception as exc:
                logger.warning("Failed to load valuations for %s: %s", symbol, exc)
                results[symbol] = -1
        return results

    def load_all(
        self,
        symbols: list[str],
        kline_start: str | None = None,
        kline_end: str | None = None,
        interval: str = "1d",
    ) -> dict[str, Any]:
        """Load both K-line and valuations for all symbols."""
        return {
            "kline": self.load_kline_batch(symbols, kline_start, kline_end, interval),
            "valuations": self.load_valuations_batch(symbols, kline_start, kline_end),
        }
