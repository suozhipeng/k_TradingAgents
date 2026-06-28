"""DuckDB local database storage layer for A-share market data.

Provides AStockStore — a DuckDB-backed local database for structured query,
export/import, and persistence of all A-share data tables.

Also provides PGStore — a PostgreSQL/TimescaleDB production database layer
for multi-user concurrent access.

Tables
------
kline_bars, valuations, order_book_snapshots, trade_tape,
research_reports, news_items, announcements, backtest_results,
paper_trades, market_indicators

Plus PostgreSQL/TimescaleDB production schema and ClickHouse OLAP replica.
"""

from __future__ import annotations

from .loader import (
    BatchLoader,
    KlineLoader,
    ValuationLoader,
)
from .schema import AStockStore, init_astock_db

# Production PostgreSQL/TimescaleDB store
try:
    from .pg_store import PGConfig, PGStore
except ImportError:
    PGConfig = None  # type: ignore[assignment]
    PGStore = None  # type: ignore[assignment]

# ClickHouse OLAP replica schema
try:
    from .clickhouse_schema import (
        CH_PARTITION_STRATEGY,
        CH_TTL_POLICY,
        export_ch_sql,
        pg_to_ch_schema,
    )
except ImportError:
    CH_PARTITION_STRATEGY = {}
    CH_TTL_POLICY = {}
    export_ch_sql = None  # type: ignore[assignment]
    pg_to_ch_schema = None  # type: ignore[assignment]

# Migration runner
try:
    from .migrations import MigrationRunner
except ImportError:
    MigrationRunner = None  # type: ignore[assignment]

# Runtime backend switch
from .backend import BackendConfig, BackendManager, backend_mgr

__all__ = [
    "AStockStore",
    "init_astock_db",
    "KlineLoader",
    "ValuationLoader",
    "BatchLoader",
    # PostgreSQL production
    "PGConfig",
    "PGStore",
    # Migration
    "MigrationRunner",
    # ClickHouse
    "CH_PARTITION_STRATEGY",
    "CH_TTL_POLICY",
    "export_ch_sql",
    "pg_to_ch_schema",
    # Backend switch
    "BackendConfig",
    "BackendManager",
    "backend_mgr",
]
