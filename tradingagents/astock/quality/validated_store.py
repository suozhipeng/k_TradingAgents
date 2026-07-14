"""ValidatedStore — quality-gated proxy around AStockStore/PGStore.

All insert operations are intercepted and run through
``QualityExecutor.validate_and_import_*`` before reaching the real store.

If validation fails (severity == "error"):
    1. Bad rows are written to ``data_quarantine``
    2. A ``BlockedImportError`` is raised
    3. The write is NOT committed to the target table
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Callable

from tradingagents.astock.quality.executor import (
    BlockedImportError,
    QualityExecutor,
)

logger = logging.getLogger(__name__)


def _sync_run(fn: Callable, *args: Any, **kwargs: Any) -> Any:
    """Execute a function whether it is sync or async, returning the
    result directly.  This is a module-level helper so that ``ValidatedStore``
    methods stay synchronous (callers like Flask routes are sync).

    Safely handles the case where we're already inside an event loop
    (e.g. Flask-SSE thread with asyncio background tasks).
    """
    if not asyncio.iscoroutinefunction(fn):
        return fn(*args, **kwargs)

    coro = fn(*args, **kwargs)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running event loop — safe to use asyncio.run
        return asyncio.run(coro)

    # Inside a running loop — dispatch in a new thread to avoid
    # "cannot run_until_complete on a running loop" error.
    result: list[Any] = [None]
    exception: list[Exception | None] = [None]

    def _run():
        try:
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                result[0] = new_loop.run_until_complete(coro)
            finally:
                new_loop.close()
        except Exception as exc:
            exception[0] = exc

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join()
    if exception[0]:
        raise exception[0]
    return result[0]


class ValidatedStore:
    """Proxy that wraps a store and runs quality checks before every
    insert/write operation.  Non-write methods pass through untouched."""

    # Methods that bypass validation (read / admin)
    _READ_METHODS = frozenset({
        "query_kline", "query_valuations", "query_order_book",
        "query_trade_tape", "query_research_reports", "query_news_items",
        "query_announcements", "query_market_indicators",
        "query_technical_indicators", "query_adjust_factors",
        "query_audit_log", "query_quarantine", "query_sql",
        "get_backtest_results", "get_paper_trades", "list_tables",
        "list_symbols", "table_exists", "get_table_stats",
        "list_migrations", "validate_api_key",
    })

    def __init__(self, store: Any, executor: QualityExecutor | None = None) -> None:
        self._store = store
        self._executor = executor or QualityExecutor(store)
        self._drop_validate: set[str] = set()

    # ── Intercepted write methods ────────────────────────────────────

    def insert_kline(self, symbol: str, df: Any, interval: str = "1d", source: str = "") -> int:
        if "insert_kline" in self._drop_validate:
            return _sync_run(self._store.insert_kline, symbol, df, interval=interval, source=source)
        try:
            return self._executor.validate_and_import_kline(symbol, df, interval=interval, source=source)
        except BlockedImportError:
            raise
        except Exception as exc:
            logger.error("Validation failed for %s: %s", symbol, exc)
            raise  # fail-closed: don't let bad data through

    def insert_valuations(self, symbol: str, df: Any, source: str = "") -> int:
        if "insert_valuations" in self._drop_validate:
            return _sync_run(self._store.insert_valuations, symbol, df, source=source)
        try:
            return self._executor.validate_and_import_valuations(symbol, df, source=source)
        except BlockedImportError:
            raise
        except Exception as exc:
            logger.error("Validation failed for valuations %s: %s", symbol, exc)
            raise  # fail-closed

    def insert_table_rows(self, table_name: str, rows: Any) -> int:
        if table_name in self._drop_validate:
            return _sync_run(self._store.insert_table_rows, table_name, rows)

        # Only validate kline_bars and valuations tables
        if table_name not in ("kline_bars", "valuations"):
            return _sync_run(self._store.insert_table_rows, table_name, rows)

        import pandas as pd
        df = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
        if df.empty:
            return 0

        symbol = "unknown"
        if "symbol" in df.columns and len(df) > 0:
            symbol = str(df["symbol"].iloc[0])
        elif len(df) > 0:
            symbol = "unknown"

        try:
            if table_name == "kline_bars":
                interval = "1d"
                if "interval" in df.columns:
                    iv = str(df["interval"].iloc[0]) if len(df) > 0 else "1d"
                    if iv and iv != "nan":
                        interval = iv
                return self._executor.validate_and_import_kline(symbol, df, interval=interval)
            elif table_name == "valuations":
                return self._executor.validate_and_import_valuations(symbol, df)
        except BlockedImportError:
            raise
        except Exception:
            logger.exception("Table rows validation failed for %s", table_name)
            raise  # fail-closed

    # ── Passthrough methods (no validation needed) ────────────────────

    def store_backtest_result(self, result: Any) -> Any:
        return _sync_run(self._store.store_backtest_result, result)

    def store_paper_trade(self, trade: dict) -> Any:
        return _sync_run(self._store.store_paper_trade, trade)

    def store_audit_log(self, *args: Any, **kwargs: Any) -> Any:
        return _sync_run(self._store.store_audit_log, *args, **kwargs)

    def store_quarantine(self, *args: Any, **kwargs: Any) -> Any:
        return _sync_run(self._store.store_quarantine, *args, **kwargs)

    def store_quality_rule(self, *args: Any, **kwargs: Any) -> Any:
        return _sync_run(self._store.store_quality_rule, *args, **kwargs)

    def add_api_key(self, *args: Any, **kwargs: Any) -> Any:
        return _sync_run(self._store.add_api_key, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        """Fallback: delegate any unhandled method to the real store.
        Wraps async results for synchronous callers."""
        if name.startswith("_"):
            raise AttributeError(name)
        attr = getattr(self._store, name, None)
        if attr is None:
            raise AttributeError(f"'{type(self._store).__name__}' has no attribute '{name}'")
        # If the underlying method is a coroutine function but we're being
        # called synchronously, use _sync_run to handle event loop conflicts
        if asyncio.iscoroutinefunction(attr):
            def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                return _sync_run(attr, *args, **kwargs)
            return _sync_wrapper
        return attr

    def drop_validation_for(self, *method_names: str) -> None:
        self._drop_validate.update(method_names)

    def __repr__(self) -> str:
        return f"ValidatedStore({self._store!r})"
