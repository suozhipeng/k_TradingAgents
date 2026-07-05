"""PostgreSQL/TimescaleDB production database layer for AStock TradingAgents.

This module is the public compatibility entry for ``PGStore``. The store's
implementation is split by responsibility into focused mixins:

- ``pg_connection``: connection management and schema initialization
- ``pg_io``: DataFrame normalization and bulk upsert helpers
- ``pg_market_data``: market/research/backtest/paper-trade data APIs
- ``pg_governance``: audit, API keys, quality rules, and quarantine
- ``pg_admin``: introspection, raw SQL, migrations, and maintenance
"""

from __future__ import annotations

from .pg_common import *
from .pg_admin import PGAdminMixin
from .pg_connection import PGConnectionMixin
from .pg_governance import PGGovernanceMixin
from .pg_io import PGDataFrameIOMixin
from .pg_market_data import PGMarketDataMixin


class PGStore(
    PGConnectionMixin,
    PGDataFrameIOMixin,
    PGMarketDataMixin,
    PGGovernanceMixin,
    PGAdminMixin,
):
    """PostgreSQL/TimescaleDB production database store for AStock data.

    Mirrors the AStockStore API (insert_kline, query_kline, insert_valuations,
    store_backtest_result, etc.) but backed by SQLAlchemy 2.0 with asyncpg.
    """


async def init_pg_store(
    config: PGConfig | None = None, sync: bool = False
) -> PGStore:
    """Create a PGStore, call init_schema(), and return it."""
    store = PGStore(config, sync=sync)
    await store.connect()
    await store.init_schema()
    return store
