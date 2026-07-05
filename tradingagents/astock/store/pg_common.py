"""PostgreSQL/TimescaleDB production database layer for AStock TradingAgents.

Replaces DuckDB as the write-primary for multi-user concurrent access.
Backed by SQLAlchemy 2.0 + asyncpg with an async-first design.
Mirrors the AStockStore API from schema.py.

Usage:
    config = PGConfig(host="localhost", database="astock", user="astock", password="astock")
    store = PGStore(config)
    await store.connect()
    await store.init_schema()
    rows = await store.insert_kline("000001.SZ", df)
    df = await store.query_kline("000001.SZ")
    await store.close()
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import logging
import os
import time as _time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    and_,
    or_,
    select,
    text,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import QueuePool

from . import schema_defs

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported kline intervals (from schema_defs SSOT)
# ---------------------------------------------------------------------------
SUPPORTED_KLINE_INTERVALS = schema_defs.SUPPORTED_KLINE_INTERVALS

# ---------------------------------------------------------------------------
# Column name remaps (mirrors schema.py)
# ---------------------------------------------------------------------------
KLINE_COLUMN_MAP: dict[str, str] = {
    "bar_time": "bar_time",
    "date": "bar_time",
    "datetime": "bar_time",
    "time": "bar_time",
    "trade_date": "trade_date",
    "symbol": "symbol",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "volume": "volume",
    "amount": "amount",
    "turnover": "turnover_rate",
    "turnover_rate": "turnover_rate",
    "interval": "interval",
    "adjust": "adjust",
    "quality": "quality",
    "source": "source",
}

VALUATION_COLUMN_MAP: dict[str, str] = {
    "symbol": "symbol",
    "date": "trade_date",
    "trade_date": "trade_date",
    "pe": "pe",
    "pe_ttm": "pe",
    "pb": "pb",
    "market_cap": "market_cap",
    "market_value": "market_cap",
    "source": "source",
}

# ---------------------------------------------------------------------------
# SQLAlchemy ORM Base (re-exported from models package)
# ---------------------------------------------------------------------------

from .models import Base

# Import all ORM model classes from the models package
from .models import (
    DatabaseStorageProfile,
    SecurityMaster,
    TradingCalendar,
    SecurityStatusHistory,
    IndustryClassificationHistory,
    SuspensionEvent,
    PriceLimitRule,
    KlineBar,
    Valuation,
    CorporateAction,
    AdjustFactor,
    OrderBookSnapshot,
    TradeTape,
    ResearchReport,
    NewsItem,
    Announcement,
    BacktestResult,
    PaperTrade,
    MarketIndicator,
    TechnicalIndicator,
    DataSource,
    DataQualityCheck,
    DataSnapshot,
    DataPartition,
    DataIngestionJob,
    DataIngestionJobEvent,
    MigrationVersion,
    AuditLog,
    ApiKey,
    DataQualityRule,
    DataQuarantine,
    NotificationChannel,
)

# ---------------------------------------------------------------------------
# Aggregated model list (used by init_schema, _get_pk_columns, etc.)
# ---------------------------------------------------------------------------

ALL_MODEL_CLASSES: list[type[Base]] = [
    DatabaseStorageProfile,
    SecurityMaster,
    TradingCalendar,
    SecurityStatusHistory,
    IndustryClassificationHistory,
    SuspensionEvent,
    PriceLimitRule,
    KlineBar,
    Valuation,
    CorporateAction,
    AdjustFactor,
    OrderBookSnapshot,
    TradeTape,
    ResearchReport,
    NewsItem,
    Announcement,
    BacktestResult,
    PaperTrade,
    MarketIndicator,
    TechnicalIndicator,
    DataSource,
    DataQualityCheck,
    DataSnapshot,
    DataPartition,
    DataIngestionJob,
    DataIngestionJobEvent,
    MigrationVersion,
    AuditLog,
    ApiKey,
    DataQualityRule,
    DataQuarantine,
    NotificationChannel,
]

ALL_TABLE_NAMES: list[str] = [cls.__tablename__ for cls in ALL_MODEL_CLASSES]

# PostgreSQL index definitions — imported from schema_defs (SSOT)
from .schema_defs import DEFAULT_INDEX_DEFS as INDEX_DEFS

# ---------------------------------------------------------------------------
# PGConfig
# ---------------------------------------------------------------------------


@dataclass
class PGConfig:
    """Configuration for the PostgreSQL/TimescaleDB connection."""

    host: str = "localhost"
    port: int = 5432
    database: str = "astock"
    user: str = "astock"
    password: str = "astock"
    pool_size: int = 10
    use_timescaledb: bool = True
    schema: str = "public"
    application_name: str = "tradingagents_astock"

    @property
    def dsn(self) -> str:
        """Return the async DSN string."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    @property
    def sync_dsn(self) -> str:
        """Return the sync DSN string."""
        return f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


# ---------------------------------------------------------------------------
# PGStore
# ---------------------------------------------------------------------------

__all__ = [name for name in globals() if not name.startswith("__")]
