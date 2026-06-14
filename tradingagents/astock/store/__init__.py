"""DuckDB local database storage layer for A-share market data.

Provides AStockStore — a DuckDB-backed local database for structured query,
export/import, and persistence of all A-share data tables.

Tables
------
kline_bars, valuations, order_book_snapshots, trade_tape,
research_reports, news_items, announcements, backtest_results,
paper_trades, market_indicators
"""

from __future__ import annotations

from .loader import (
    BatchLoader,
    KlineLoader,
    ValuationLoader,
)
from .schema import AStockStore, init_astock_db

__all__ = [
    "AStockStore",
    "init_astock_db",
    "KlineLoader",
    "ValuationLoader",
    "BatchLoader",
]
