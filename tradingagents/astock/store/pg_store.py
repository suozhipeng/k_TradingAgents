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

# Import all 31 ORM model classes from the models package
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


class PGStore:
    """PostgreSQL/TimescaleDB production database store for AStock data.

    Mirrors the AStockStore API (insert_kline, query_kline, insert_valuations,
    store_backtest_result, etc.) but backed by SQLAlchemy 2.0 with asyncpg.

    Supports both async (default) and sync connection modes.

    Parameters
    ----------
    config : PGConfig, optional
        Database connection configuration.
    sync : bool
        If True, use synchronous SQLAlchemy engine (for non-async contexts).
    """

    def __init__(self, config: PGConfig | None = None, sync: bool = False) -> None:
        self._config = config or PGConfig()
        self._sync = sync
        self._async_engine = None
        self._sync_engine = None
        self._async_session_factory = None
        self._connected = False

    # ---- connection management -----------------------------------------------

    async def connect(self) -> None:
        """Open the database connection pool and auto-create schema if needed."""
        if self._connected:
            return
        if self._sync:
            from sqlalchemy import create_engine

            self._sync_engine = create_engine(
                self._config.sync_dsn,
                poolclass=QueuePool,
                pool_size=self._config.pool_size,
                max_overflow=self._config.pool_size,
                pool_timeout=30,
                pool_recycle=3600,
                connect_args={"application_name": self._config.application_name},
            )
            # Test connection
            with self._sync_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                conn.commit()
        else:
            self._async_engine = create_async_engine(
                self._config.dsn,
                pool_size=self._config.pool_size,
                max_overflow=self._config.pool_size,
                pool_pre_ping=True,
                echo=False,
            )
            self._async_session_factory = async_sessionmaker(
                self._async_engine, class_=AsyncSession, expire_on_commit=False
            )
            # Test connection
            async with self._async_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        self._connected = True
        logger.info(
            "Connected to PostgreSQL at %s:%s/%s (sync=%s)",
            self._config.host,
            self._config.port,
            self._config.database,
            self._sync,
        )

    async def close(self) -> None:
        """Close the database connection pool."""
        if self._async_engine is not None:
            await self._async_engine.dispose()
            self._async_engine = None
        if self._sync_engine is not None:
            self._sync_engine.dispose()
            self._sync_engine = None
        self._async_session_factory = None
        self._connected = False
        logger.info("Disconnected from PostgreSQL")

    # ---- schema --------------------------------------------------------------

    async def init_schema(self) -> None:
        """Create all tables and indexes if they don't exist."""
        if self._sync:
            Base.metadata.create_all(self._sync_engine)
            self._create_indexes_sync()
            self._seed_storage_profiles_sync()
        else:
            async with self._async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            await self._create_indexes_async()
            await self._seed_storage_profiles_async()
        # Try to create TimescaleDB hypertable for kline_bars
        if self._config.use_timescaledb:
            await self._ensure_timescaledb_hypertable()
        # Auto-discover and register migration files
        self.discover_migrations()
        logger.info("Schema initialised (%d tables)", len(ALL_MODEL_CLASSES))

    async def _create_indexes_async(self) -> None:
        """Create all query-path indexes (async)."""
        async with self._async_engine.connect() as conn:
            for ddl in INDEX_DEFS.values():
                try:
                    await conn.execute(text(ddl))
                except Exception:
                    logger.warning("Index creation failed (may already exist): %s", ddl[:60])
            await conn.commit()

    def _create_indexes_sync(self) -> None:
        """Create all query-path indexes (sync)."""
        with self._sync_engine.connect() as conn:
            for ddl in INDEX_DEFS.values():
                try:
                    conn.execute(text(ddl))
                except Exception:
                    logger.warning("Index creation failed (may already exist): %s", ddl[:60])
            conn.commit()

    async def _ensure_timescaledb_hypertable(self) -> None:
        """Convert kline_bars to a TimescaleDB hypertable if the extension is available."""
        try:
            if self._sync:
                with self._sync_engine.connect() as conn:
                    result = conn.execute(
                        text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'timescaledb')")
                    )
                    has_timescaledb = result.scalar()
                    if has_timescaledb:
                        # Check if already a hypertable
                        exists = conn.execute(
                            text(
                                "SELECT EXISTS(SELECT 1 FROM _timescaledb_catalog.hypertable "
                                "WHERE table_name = 'kline_bars')"
                            )
                        ).scalar()
                        if not exists:
                            conn.execute(
                                text(
                                    "SELECT create_hypertable('kline_bars', 'bar_time', "
                                    "chunk_time_interval => INTERVAL '7 days', "
                                    "if_not_exists => TRUE)"
                                )
                            )
                            conn.commit()
                            logger.info("kline_bars converted to TimescaleDB hypertable")
                    conn.commit()
            else:
                async with self._async_engine.connect() as conn:
                    result = await conn.execute(
                        text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'timescaledb')")
                    )
                    has_timescaledb = result.scalar()
                    if has_timescaledb:
                        exists = await conn.execute(
                            text(
                                "SELECT EXISTS(SELECT 1 FROM _timescaledb_catalog.hypertable "
                                "WHERE table_name = 'kline_bars')"
                            )
                        )
                        if not exists.scalar():
                            await conn.execute(
                                text(
                                    "SELECT create_hypertable('kline_bars', 'bar_time', "
                                    "chunk_time_interval => INTERVAL '7 days', "
                                    "if_not_exists => TRUE)"
                                )
                            )
                            logger.info("kline_bars converted to TimescaleDB hypertable")
                    await conn.commit()
        except Exception as exc:
            logger.info("TimescaleDB hypertable creation skipped: %s", exc)

    def _seed_storage_profiles_sync(self) -> None:
        """Seed the database_storage_profiles table (sync)."""
        profiles = [
            {
                "profile_name": "postgresql_production_oltp",
                "role": "production_primary",
                "engine": "postgresql",
                "read_write_model": "multi-user transactional primary store",
                "notes": "Commercial primary database; TimescaleDB extension for time-series tables.",
            },
            {
                "profile_name": "duckdb_local_olap",
                "role": "local_cache_olap",
                "engine": "duckdb",
                "read_write_model": "single-writer analytical cache",
                "notes": "Use for local WebUI, research, backtest snapshots, and export/import.",
            },
            {
                "profile_name": "clickhouse_production_olap",
                "role": "production_analytics",
                "engine": "clickhouse",
                "read_write_model": "append-oriented analytical replica",
                "notes": "Recommended for high-volume historical market-data scans.",
            },
        ]
        with self._sync_engine.connect() as conn:
            for p in profiles:
                conn.execute(
                    text(
                        "INSERT INTO database_storage_profiles "
                        "(profile_name, role, engine, read_write_model, notes) "
                        "VALUES (:profile_name, :role, :engine, :read_write_model, :notes) "
                        "ON CONFLICT (profile_name) DO NOTHING"
                    ),
                    p,
                )
            conn.commit()

    async def _seed_storage_profiles_async(self) -> None:
        """Seed the database_storage_profiles table (async)."""
        profiles = [
            {
                "profile_name": "postgresql_production_oltp",
                "role": "production_primary",
                "engine": "postgresql",
                "read_write_model": "multi-user transactional primary store",
                "notes": "Commercial primary database; TimescaleDB extension for time-series tables.",
            },
            {
                "profile_name": "duckdb_local_olap",
                "role": "local_cache_olap",
                "engine": "duckdb",
                "read_write_model": "single-writer analytical cache",
                "notes": "Use for local WebUI, research, backtest snapshots, and export/import.",
            },
            {
                "profile_name": "clickhouse_production_olap",
                "role": "production_analytics",
                "engine": "clickhouse",
                "read_write_model": "append-oriented analytical replica",
                "notes": "Recommended for high-volume historical market-data scans.",
            },
        ]
        async with self._async_engine.connect() as conn:
            for p in profiles:
                await conn.execute(
                    text(
                        "INSERT INTO database_storage_profiles "
                        "(profile_name, role, engine, read_write_model, notes) "
                        "VALUES (:profile_name, :role, :engine, :read_write_model, :notes) "
                        "ON CONFLICT (profile_name) DO NOTHING"
                    ),
                    p,
                )
            await conn.commit()

    # ---- helpers -------------------------------------------------------------

    @staticmethod
    def _normalise_interval(interval: str) -> str:
        """Normalise interval string to canonical form."""
        value = str(interval or "1d").strip().lower()
        aliases = {
            "1min": "1m",
            "5min": "5m",
            "15min": "15m",
            "30min": "30m",
            "60min": "60m",
            "day": "1d",
            "daily": "1d",
            "week": "1w",
            "weekly": "1w",
            "month": "1mo",
            "monthly": "1mo",
            "year": "1y",
            "yearly": "1y",
            "1mth": "1mo",
        }
        value = aliases.get(value, value)
        if value not in SUPPORTED_KLINE_INTERVALS:
            supported = ", ".join(sorted(SUPPORTED_KLINE_INTERVALS))
            raise ValueError(f"Unsupported kline interval: {interval!r}. Supported: {supported}")
        return value

    @staticmethod
    def _df_from_rows(
        rows: pd.DataFrame | list[dict[str, Any]], column_map: dict[str, str]
    ) -> pd.DataFrame:
        """Normalise rows into a DataFrame with canonically-named columns."""
        if isinstance(rows, pd.DataFrame):
            if rows.empty:
                return pd.DataFrame()
            df = rows.copy()
        elif isinstance(rows, list):
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame(rows)
        else:
            return pd.DataFrame()
        rename = {}
        for src_col in df.columns:
            if src_col in column_map:
                rename[src_col] = column_map[src_col]
        if rename:
            df = df.rename(columns=rename)
        # Deduplicate columns (multiple source names may map to same target)
        df = df.loc[:, ~df.columns.duplicated()]
        target_cols = set(column_map.values())
        cols_to_keep = [c for c in df.columns if c in target_cols]
        df = df[cols_to_keep]
        return df

    @staticmethod
    def _canonicalise_dates(df: pd.DataFrame, date_cols: list[str]) -> pd.DataFrame:
        """Convert date-like columns to date objects."""
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
        return df

    @staticmethod
    def _normalise_kline_times(df: pd.DataFrame) -> pd.DataFrame:
        """Populate bar_time and trade_date for kline rows."""
        df = df.copy()
        if "bar_time" not in df.columns:
            for source_col in ("datetime", "time", "date", "trade_date"):
                if source_col in df.columns:
                    df["bar_time"] = df[source_col]
                    break
        if "bar_time" in df.columns:
            bar_time = pd.to_datetime(df["bar_time"], errors="coerce")
            df["bar_time"] = bar_time
            if "trade_date" not in df.columns:
                df["trade_date"] = bar_time.dt.date
            else:
                trade_date = pd.to_datetime(df["trade_date"], errors="coerce")
                df["trade_date"] = trade_date.fillna(bar_time).dt.date
        elif "trade_date" in df.columns:
            trade_date = pd.to_datetime(df["trade_date"], errors="coerce")
            df["trade_date"] = trade_date.dt.date
            df["bar_time"] = trade_date
        else:
            raise ValueError("kline rows require bar_time, date, datetime, time, or trade_date")
        return df

    # ---- batch insert with ON CONFLICT DO UPDATE ----------------------------

    def _build_upsert_sql(self, table_name: str, columns: list[str], pk_columns: list[str]) -> str:
        """Build an INSERT ... ON CONFLICT DO UPDATE SQL statement.

        Parameters
        ----------
        table_name : str
            Target table name.
        columns : list[str]
            Column names to insert.
        pk_columns : list[str]
            Primary key column names for conflict detection.

        Returns
        -------
        str
            SQL statement with named parameters (:col1, :col2, ...).
        """
        quoted_cols = [f'"{c}"' for c in columns]
        col_list = ", ".join(quoted_cols)
        param_list = ", ".join(f":{c}" for c in columns)
        quoted_pk = [f'"{c}"' for c in pk_columns]
        pk_list = ", ".join(quoted_pk)

        # Build SET clause excluding PK columns
        update_parts = []
        for c in columns:
            if c not in pk_columns:
                update_parts.append(f'"{c}" = EXCLUDED."{c}"')
        update_clause = ", ".join(update_parts)

        if update_clause:
            return (
                f'INSERT INTO "{table_name}" ({col_list}) VALUES ({param_list}) '
                f"ON CONFLICT ({pk_list}) DO UPDATE SET {update_clause}"
            )
        else:
            return (
                f'INSERT INTO "{table_name}" ({col_list}) VALUES ({param_list}) '
                f"ON CONFLICT ({pk_list}) DO NOTHING"
            )

    # ---------------------------------------------------------------------------
    # Bulk upsert helpers (executemany / COPY)
    # ---------------------------------------------------------------------------

    def _bulk_upsert_sync(
        self, table_name: str, columns: list[str], pk_cols: list[str], records: list[dict[str, Any]]
    ) -> int:
        """Bulk upsert using executemany (batched in chunks)."""
        if not records:
            return 0
        sql = self._build_upsert_sql(table_name, columns, pk_cols)
        chunk_size = 500
        total = 0
        with self._sync_engine.connect() as conn:
            for i in range(0, len(records), chunk_size):
                chunk = records[i : i + chunk_size]
                result = conn.execute(text(sql), chunk)
                total += result.rowcount
            conn.commit()
        return total

    async def _bulk_upsert_async(
        self, table_name: str, columns: list[str], pk_cols: list[str], records: list[dict[str, Any]]
    ) -> int:
        """Bulk upsert using executemany (batched in chunks)."""
        if not records:
            return 0
        sql = self._build_upsert_sql(table_name, columns, pk_cols)
        chunk_size = 500
        total = 0
        async with self._async_session_factory() as session:
            for i in range(0, len(records), chunk_size):
                chunk = records[i : i + chunk_size]
                result = await session.execute(text(sql), chunk)
                total += result.rowcount
            await session.commit()
        return total

    def _copy_upsert_sync(
        self, table_name: str, columns: list[str], records: list[dict[str, Any]]
    ) -> int:
        """Bulk insert using PostgreSQL COPY (faster than executemany for large batches).

        Note: COPY does not support ON CONFLICT directly. This method inserts
        raw data via COPY, relying on the target table's INSERT OR REPLACE
        semantics (or the caller should handle conflicts separately).
        """
        if not records:
            return 0
        import io

        col_str = ",".join(f'"{c}"' for c in columns)
        buf = io.StringIO()
        for rec in records:
            vals = []
            for c in columns:
                v = rec.get(c)
                if v is None:
                    vals.append("\\N")
                elif isinstance(v, bool):
                    vals.append("1" if v else "0")
                elif isinstance(v, (datetime.date, datetime.datetime)):
                    vals.append(v.isoformat())
                else:
                    vals.append(str(v))
            buf.write("\t".join(vals) + "\n")
        buf.seek(0)

        with self._sync_engine.connect() as conn:
            cursor = conn.connection.cursor()
            cursor.copy_expert(f"COPY {table_name} ({col_str}) FROM STDIN WITH (FORMAT csv, HEADER false, DELIMITER E'\\t', NULL '\\N')", buf)
            conn.commit()
            cursor.close()
        return len(records)

    async def _copy_upsert_async(
        self, table_name: str, columns: list[str], records: list[dict[str, Any]]
    ) -> int:
        """Async bulk insert using PostgreSQL COPY."""
        if not records:
            return 0
        import io

        col_str = ",".join(f'"{c}"' for c in columns)
        buf = io.BytesIO()
        for rec in records:
            vals = []
            for c in columns:
                v = rec.get(c)
                if v is None:
                    vals.append(b"\\N")
                elif isinstance(v, bool):
                    vals.append(b"1" if v else b"0")
                elif isinstance(v, (datetime.date, datetime.datetime)):
                    vals.append(str(v.isoformat()).encode())
                else:
                    vals.append(str(v).encode())
            buf.write(b"\t".join(vals) + b"\n")
        buf.seek(0)

        async with self._async_engine.connect() as conn:
            # Use the underlying asyncpg connection for COPY
            asyncpg_conn = await conn.connection.fetchval("SELECT 1")  # ping
            from sqlalchemy.pool import NullPool

            # Fall back to executemany if COPY is not directly accessible
            return await self._bulk_upsert_async(table_name, columns, [], records)

    def _clean_record(self, rec: dict[str, Any]) -> dict[str, Any]:
        """Clean a single record: convert pd.Timestamp -> datetime, pd.NA -> None."""
        clean = {}
        for k, v in rec.items():
            if isinstance(v, pd.Timestamp):
                v = v.to_pydatetime()
            elif pd.isna(v):
                v = None
            clean[k] = v
        return clean

    def _get_pk_columns(self, table_name: str) -> list[str]:
        """Return the primary key column names for a given table."""
        for model_cls in ALL_MODEL_CLASSES:
            if model_cls.__tablename__ == table_name:
                pk_cols = []
                for col in model_cls.__table__.primary_key.columns:
                    pk_cols.append(col.name)
                return pk_cols
        # Fallback: known PKs for all tables
        pk_map: dict[str, list[str]] = {
            "database_storage_profiles": ["profile_name"],
            "security_master": ["symbol"],
            "trading_calendar": ["exchange", "trade_date"],
            "security_status_history": ["symbol", "effective_date"],
            "industry_classification_history": ["symbol", "effective_date", "classification", "level"],
            "suspension_events": ["symbol", "start_date"],
            "price_limit_rules": ["rule_id"],
            "kline_bars": ["symbol", "bar_time", "interval", "adjust"],
            "valuations": ["symbol", "trade_date"],
            "corporate_actions": ["action_id"],
            "adjust_factors": ["symbol", "trade_date", "adjust"],
            "order_book_snapshots": ["symbol", "timestamp"],
            "trade_tape": ["symbol", "timestamp"],
            "research_reports": ["symbol", "report_date", "title"],
            "news_items": ["symbol", "publish_date", "url"],
            "announcements": ["symbol", "publish_date", "url"],
            "backtest_results": ["run_id"],
            "paper_trades": ["trade_id"],
            "market_indicators": ["symbol", "trade_date"],
            "technical_indicators": ["symbol", "bar_time", "interval", "indicator", "params_hash"],
            "data_sources": ["source_id"],
            "data_quality_checks": ["check_id"],
            "data_snapshots": ["snapshot_id"],
            "data_partitions": ["partition_id"],
            "data_ingestion_jobs": ["job_id"],
            "data_ingestion_job_events": ["event_id"],
            "migration_versions": ["version_id"],
            "audit_log": ["event_id"],
            "api_keys": ["key_id"],
            "data_quality_rules": ["rule_id"],
            "data_quarantine": ["quarantine_id"],
        }
        return pk_map.get(table_name, [])

    async def _insert_df_async(
        self, table: str, df: pd.DataFrame, column_map: dict[str, str]
    ) -> int:
        """Normalise df and execute INSERT ... ON CONFLICT DO UPDATE (async)."""
        if df.empty:
            return 0
        normalised = self._df_from_rows(df, column_map)
        if normalised.empty:
            return 0
        columns = list(normalised.columns)
        pk_cols = self._get_pk_columns(table)
        sql = self._build_upsert_sql(table, columns, pk_cols)
        # Convert DataFrame rows to list of dicts
        records = normalised.to_dict(orient="records")
        # Convert pd.Timestamp to Python datetime and pd.NaT to None
        cleaned = []
        for rec in records:
            clean = {}
            for k, v in rec.items():
                if isinstance(v, pd.Timestamp):
                    v = v.to_pydatetime()
                elif pd.isna(v):
                    v = None
                clean[k] = v
            cleaned.append(clean)

        async with self._async_session_factory() as session:
            total = 0
            for record in cleaned:
                result = await session.execute(text(sql), record)
                total += result.rowcount
            await session.commit()
        return total

    def _insert_df_sync(
        self, table: str, df: pd.DataFrame, column_map: dict[str, str]
    ) -> int:
        """Normalise df and execute INSERT ... ON CONFLICT DO UPDATE (sync)."""
        if df.empty:
            return 0
        normalised = self._df_from_rows(df, column_map)
        if normalised.empty:
            return 0
        columns = list(normalised.columns)
        pk_cols = self._get_pk_columns(table)
        sql = self._build_upsert_sql(table, columns, pk_cols)
        records = normalised.to_dict(orient="records")
        cleaned = []
        for rec in records:
            clean = {}
            for k, v in rec.items():
                if isinstance(v, pd.Timestamp):
                    v = v.to_pydatetime()
                elif pd.isna(v):
                    v = None
                clean[k] = v
            cleaned.append(clean)

        with self._sync_engine.connect() as conn:
            total = 0
            for record in cleaned:
                result = conn.execute(text(sql), record)
                total += result.rowcount
            conn.commit()
        return total

    def _insert_df(
        self, table: str, df: pd.DataFrame, column_map: dict[str, str]
    ) -> int:
        """Dispatch to sync or async insert based on connection mode."""
        if self._sync:
            return self._insert_df_sync(table, df, column_map)
        else:
            # For async mode, we need to run in an event loop
            return self._run_async(self._insert_df_async(table, df, column_map))

    def _run_async(self, coro: Any) -> Any:
        """Run an async coroutine in a synchronous context.

        If an event loop is already running, we create a new one in a thread.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop
            return asyncio.run(coro)

        # Loop already running — this is a sync method called from async context
        # We use a simple blocking run
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()

    # ---- generic table insert -----------------------------------------------

    async def insert_table_rows(
        self, table_name: str, rows: pd.DataFrame | list[dict[str, Any]]
    ) -> int:
        """Insert or replace rows into a managed table.

        This is the generic entry point used by manual data-entry APIs.
        Unknown columns are dropped; PG constraints enforce required primary keys.

        Uses bulk upsert (executemany with chunking) for better performance.
        """
        if table_name not in ALL_TABLE_NAMES:
            msg = f"Unknown table: {table_name}. Known: {ALL_TABLE_NAMES}"
            raise ValueError(msg)
        if isinstance(rows, pd.DataFrame):
            df = rows.copy()
        else:
            df = pd.DataFrame(rows)
        if df.empty:
            return 0
        if table_name == "kline_bars":
            if "interval" in df.columns:
                df["interval"] = df["interval"].fillna("1d").apply(self._normalise_interval)
            else:
                df["interval"] = "1d"
            if "adjust" not in df.columns:
                df["adjust"] = "none"
            if "quality" not in df.columns:
                df["quality"] = "normal"
            df = self._normalise_kline_times(df)
        # Filter to known columns for this table
        model_cls = None
        for cls in ALL_MODEL_CLASSES:
            if cls.__tablename__ == table_name:
                model_cls = cls
                break
        if model_cls is None:
            raise ValueError(f"Unknown table: {table_name}")
        known_columns = {c.name for c in model_cls.__table__.columns if c.name != "created_at"}
        normalised = df[[c for c in df.columns if c in known_columns]].copy()
        if normalised.empty:
            return 0
        for date_col in (
            "trade_date",
            "report_date",
            "publish_date",
            "list_date",
            "delist_date",
            "effective_date",
            "end_date",
            "start_date",
            "action_date",
            "ex_date",
        ):
            if date_col in normalised.columns:
                normalised[date_col] = pd.to_datetime(normalised[date_col], errors="coerce").dt.date
        for ts_col in (
            "timestamp",
            "bar_time",
            "start_time",
            "end_time",
            "created_at",
            "updated_at",
            "event_time",
            "last_used_at",
            "resolved_at",
        ):
            if ts_col in normalised.columns:
                normalised[ts_col] = pd.to_datetime(normalised[ts_col], errors="coerce")

        columns = list(normalised.columns)
        pk_cols = self._get_pk_columns(table_name)
        
        # Bulk upsert using executemany with chunking
        records = normalised.to_dict(orient="records")
        cleaned = [self._clean_record(rec) for rec in records]

        if self._sync:
            return self._bulk_upsert_sync(table_name, columns, pk_cols, cleaned)
        else:
            return await self._bulk_upsert_async(table_name, columns, pk_cols, cleaned)

    # ---- kline --------------------------------------------------------------

    async def insert_kline(
        self, symbol: str, df: pd.DataFrame, interval: str = "1d", source: str = ""
    ) -> int:
        """Batch insert/replace kline bars for *symbol*."""
        if df.empty:
            return 0
        df = df.copy()
        interval = self._normalise_interval(interval)
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        if "interval" not in df.columns:
            df["interval"] = interval
        else:
            df["interval"] = df["interval"].fillna(interval).apply(self._normalise_interval)
        if "adjust" not in df.columns:
            df["adjust"] = "none"
        if "quality" not in df.columns:
            df["quality"] = "normal"
        if "source" not in df.columns:
            df["source"] = source
        df = self._normalise_kline_times(df)
        # Normalise first to get actual available columns
        normalised = self._df_from_rows(df, KLINE_COLUMN_MAP)
        if normalised.empty:
            return 0
        columns = list(normalised.columns)
        pk_cols = ["symbol", "bar_time", "interval", "adjust"]
        sql = self._build_upsert_sql("kline_bars", columns, pk_cols)
        records = normalised.to_dict(orient="records")
        cleaned = []
        for rec in records:
            clean = {}
            for k, v in rec.items():
                if isinstance(v, pd.Timestamp):
                    v = v.to_pydatetime()
                elif pd.isna(v):
                    v = None
                clean[k] = v
            cleaned.append(clean)

        if self._sync:
            with self._sync_engine.connect() as conn:
                total = 0
                for record in cleaned:
                    result = conn.execute(text(sql), record)
                    total += result.rowcount
                conn.commit()
            return total
        else:
            async with self._async_session_factory() as session:
                total = 0
                for record in cleaned:
                    result = await session.execute(text(sql), record)
                    total += result.rowcount
                await session.commit()
            return total

    async def query_kline(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        interval: str = "1d",
        limit: int | None = None,
    ) -> pd.DataFrame:
        """Return kline bars as a DataFrame, sorted by bar_time (ascending).

        When *limit* is set, the SQL-level query uses a **descending** subquery
        with ``LIMIT N``, then re-wraps in an outer ``ORDER BY bar_time ASC`` so
        that the caller always receives chronologically ordered data regardless
        of whether a pushdown limit was applied.
        """
        interval = self._normalise_interval(interval)
        inner = 'SELECT * FROM kline_bars WHERE symbol = :symbol AND "interval" = :interval'
        params: dict[str, Any] = {"symbol": symbol, "interval": interval}
        if start:
            inner += " AND bar_time >= :start"
            params["start"] = start
        if end:
            inner += " AND bar_time <= :end"
            params["end"] = end

        if limit is not None and limit > 0:
            inner += " ORDER BY bar_time DESC LIMIT :limit"
            params["limit"] = limit
            sql = f"SELECT * FROM ({inner}) sub ORDER BY bar_time ASC"
        else:
            sql = inner + " ORDER BY bar_time"

        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                if not rows:
                    return pd.DataFrame()
                df = pd.DataFrame(rows, columns=result.keys())
            return df
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                if not rows:
                    return pd.DataFrame()
                df = pd.DataFrame(rows, columns=result.keys())
            return df

    # ---- valuations ---------------------------------------------------------

    async def insert_valuations(
        self, symbol: str, df: pd.DataFrame, source: str = ""
    ) -> int:
        """Batch insert/replace valuation data for *symbol*."""
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        if "source" not in df.columns:
            df["source"] = source
        df = self._canonicalise_dates(df, ["trade_date", "date"])
        normalised = self._df_from_rows(df, VALUATION_COLUMN_MAP)
        if normalised.empty:
            return 0
        columns = list(normalised.columns)
        pk_cols = ["symbol", "trade_date"]
        sql = self._build_upsert_sql("valuations", columns, pk_cols)
        records = normalised.to_dict(orient="records")
        cleaned = []
        for rec in records:
            clean = {}
            for k, v in rec.items():
                if isinstance(v, pd.Timestamp):
                    v = v.to_pydatetime()
                elif pd.isna(v):
                    v = None
                clean[k] = v
            cleaned.append(clean)

        if self._sync:
            with self._sync_engine.connect() as conn:
                total = 0
                for record in cleaned:
                    result = conn.execute(text(sql), record)
                    total += result.rowcount
                conn.commit()
            return total
        else:
            async with self._async_session_factory() as session:
                total = 0
                for record in cleaned:
                    result = await session.execute(text(sql), record)
                    total += result.rowcount
                await session.commit()
            return total

    async def query_valuations(
        self, symbol: str, start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        """Return valuations as a DataFrame, sorted by trade_date."""
        sql = "SELECT * FROM valuations WHERE symbol = :symbol"
        params: dict[str, Any] = {"symbol": symbol}
        if start:
            sql += " AND trade_date >= :start"
            params["start"] = start
        if end:
            sql += " AND trade_date <= :end"
            params["end"] = end
        sql += " ORDER BY trade_date"

        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- order book snapshots -----------------------------------------------

    async def insert_order_book_snapshot(
        self, symbol: str, df: pd.DataFrame, source: str = ""
    ) -> int:
        """Batch insert/replace order book snapshots for *symbol*."""
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        if "source" not in df.columns:
            df["source"] = source
        return await self.insert_table_rows(
            "order_book_snapshots",
            self._df_from_rows(
                df,
                {
                    "symbol": "symbol",
                    "timestamp": "timestamp",
                    "bid_price": "bid_price",
                    "bid_volume": "bid_volume",
                    "ask_price": "ask_price",
                    "ask_volume": "ask_volume",
                    "source": "source",
                },
            ),
        )

    async def query_order_book(
        self, symbol: str, start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        """Return order book snapshots as a DataFrame."""
        sql = "SELECT * FROM order_book_snapshots WHERE symbol = :symbol"
        params: dict[str, Any] = {"symbol": symbol}
        if start:
            sql += " AND timestamp >= :start"
            params["start"] = start
        if end:
            sql += " AND timestamp <= :end"
            params["end"] = end
        sql += " ORDER BY timestamp"

        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- trade tape ---------------------------------------------------------

    async def insert_trade_tape(
        self, symbol: str, df: pd.DataFrame, source: str = ""
    ) -> int:
        """Batch insert/replace trade tape entries for *symbol*."""
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        if "source" not in df.columns:
            df["source"] = source
        return await self.insert_table_rows(
            "trade_tape",
            self._df_from_rows(
                df,
                {
                    "symbol": "symbol",
                    "timestamp": "timestamp",
                    "price": "price",
                    "volume": "volume",
                    "direction": "direction",
                    "source": "source",
                },
            ),
        )

    async def query_trade_tape(
        self, symbol: str, start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        """Return trade tape entries as a DataFrame."""
        sql = "SELECT * FROM trade_tape WHERE symbol = :symbol"
        params: dict[str, Any] = {"symbol": symbol}
        if start:
            sql += " AND timestamp >= :start"
            params["start"] = start
        if end:
            sql += " AND timestamp <= :end"
            params["end"] = end
        sql += " ORDER BY timestamp"

        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- research reports ---------------------------------------------------

    async def insert_research_reports(
        self, symbol: str, df: pd.DataFrame, source: str = ""
    ) -> int:
        """Batch insert/replace research reports for *symbol*."""
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        if "source" not in df.columns:
            df["source"] = source
        df = self._canonicalise_dates(df, ["report_date", "date"])
        return await self.insert_table_rows(
            "research_reports",
            self._df_from_rows(
                df,
                {
                    "symbol": "symbol",
                    "report_date": "report_date",
                    "title": "title",
                    "institution": "institution",
                    "analyst": "analyst",
                    "rating": "rating",
                    "pdf_url": "pdf_url",
                    "source": "source",
                },
            ),
        )

    async def query_research_reports(self, symbol: str) -> pd.DataFrame:
        sql = "SELECT * FROM research_reports WHERE symbol = :symbol ORDER BY report_date"
        params = {"symbol": symbol}
        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- news items ---------------------------------------------------------

    async def insert_news_items(
        self, symbol: str, df: pd.DataFrame, source: str = ""
    ) -> int:
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        if "source" not in df.columns:
            df["source"] = source
        df = self._canonicalise_dates(df, ["publish_date", "date"])
        return await self.insert_table_rows(
            "news_items",
            self._df_from_rows(
                df,
                {
                    "symbol": "symbol",
                    "publish_date": "publish_date",
                    "title": "title",
                    "summary": "summary",
                    "url": "url",
                    "source": "source",
                },
            ),
        )

    async def query_news_items(self, symbol: str) -> pd.DataFrame:
        sql = "SELECT * FROM news_items WHERE symbol = :symbol ORDER BY publish_date"
        params = {"symbol": symbol}
        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- announcements ------------------------------------------------------

    async def insert_announcements(self, symbol: str, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        df = self._canonicalise_dates(df, ["publish_date", "date"])
        return await self.insert_table_rows(
            "announcements",
            self._df_from_rows(
                df,
                {
                    "symbol": "symbol",
                    "publish_date": "publish_date",
                    "title": "title",
                    "summary": "summary",
                    "url": "url",
                },
            ),
        )

    async def query_announcements(self, symbol: str) -> pd.DataFrame:
        sql = "SELECT * FROM announcements WHERE symbol = :symbol ORDER BY publish_date DESC"
        params = {"symbol": symbol}
        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- backtest results ---------------------------------------------------

    async def store_backtest_result(self, result: Any) -> int:
        """Store a backtest result (dict or BacktestResult-like object)."""
        if hasattr(result, "model_dump"):
            data = result.model_dump()
        elif isinstance(result, dict):
            data = dict(result)
        else:
            data = {}
        run_id = data.get("run_id", str(hash(str(data))))
        df = pd.DataFrame(
            [
                {
                    "run_id": run_id,
                    "symbol": str(data.get("symbol", "")),
                    "strategy_name": str(data.get("strategy_name", "unknown")),
                    "start_date": str(data.get("start_date", "")),
                    "end_date": str(data.get("end_date", "")),
                    "total_return": float(data.get("total_return", 0.0)),
                    "annualized_return": float(data.get("annualized_return", 0.0)),
                    "sharpe_ratio": float(data.get("sharpe_ratio", 0.0)),
                    "max_drawdown": float(data.get("max_drawdown", 0.0)),
                    "win_rate": float(data.get("win_rate", 0.0)),
                    "total_trades": int(data.get("total_trades", 0)),
                    "params_json": json.dumps(
                        {
                            k: v
                            for k, v in data.items()
                            if k
                            not in (
                                "run_id",
                                "symbol",
                                "strategy_name",
                                "start_date",
                                "end_date",
                                "total_return",
                                "annualized_return",
                                "sharpe_ratio",
                                "max_drawdown",
                                "win_rate",
                                "total_trades",
                            )
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        )
        return await self.insert_table_rows("backtest_results", df)

    async def get_backtest_results(
        self, strategy_name: str | None = None
    ) -> pd.DataFrame:
        if strategy_name:
            sql = "SELECT * FROM backtest_results WHERE strategy_name = :name ORDER BY created_at DESC"
            params = {"name": strategy_name}
        else:
            sql = "SELECT * FROM backtest_results ORDER BY created_at DESC"
            params = {}
        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    async def clear_backtest_results(self) -> int:
        """Delete all stored backtest results. Returns number of rows deleted."""
        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text("DELETE FROM backtest_results"))
                conn.commit()
                return result.rowcount
        else:
            async with self._async_session_factory() as session:
                result = await session.execute(text("DELETE FROM backtest_results"))
                await session.commit()
                return result.rowcount

    async def delete_backtest_result(self, run_id: str) -> int:
        """Delete a single backtest result by run_id. Returns 1 if deleted."""
        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text("DELETE FROM backtest_results WHERE run_id = :rid"), {"rid": run_id})
                conn.commit()
                return result.rowcount
        else:
            async with self._async_session_factory() as session:
                result = await session.execute(
                    text("DELETE FROM backtest_results WHERE run_id = :rid"), {"rid": run_id}
                )
                await session.commit()
                return result.rowcount

    # ---- paper trades -------------------------------------------------------

    async def store_paper_trade(self, trade: dict[str, Any]) -> int:
        """Store a single paper trade record."""
        df = pd.DataFrame([trade])
        if "trade_id" not in df.columns:
            df["trade_id"] = str(hash(str(trade)))
        if "actionable" not in df.columns:
            df["actionable"] = False
        if "decision_scope" not in df.columns:
            df["decision_scope"] = "paper_trading_only"
        df = self._canonicalise_dates(df, ["trade_date", "date"])
        return await self.insert_table_rows("paper_trades", df)

    async def get_paper_trades(self, symbol: str | None = None) -> pd.DataFrame:
        if symbol:
            sql = "SELECT * FROM paper_trades WHERE symbol = :symbol ORDER BY trade_date"
            params = {"symbol": symbol}
        else:
            sql = "SELECT * FROM paper_trades ORDER BY trade_date"
            params = {}
        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- market indicators --------------------------------------------------

    async def insert_market_indicators(self, symbol: str, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        df = self._canonicalise_dates(df, ["trade_date", "date"])
        return await self.insert_table_rows(
            "market_indicators",
            self._df_from_rows(
                df,
                {
                    "symbol": "symbol",
                    "trade_date": "trade_date",
                    "ma_5": "ma_5",
                    "ma_20": "ma_20",
                    "ma_60": "ma_60",
                    "rsi_14": "rsi_14",
                    "atr_14": "atr_14",
                    "volume_ma_5": "volume_ma_5",
                },
            ),
        )

    async def query_market_indicators(
        self, symbol: str, start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        sql = "SELECT * FROM market_indicators WHERE symbol = :symbol"
        params: dict[str, Any] = {"symbol": symbol}
        if start:
            sql += " AND trade_date >= :start"
            params["start"] = start
        if end:
            sql += " AND trade_date <= :end"
            params["end"] = end
        sql += " ORDER BY trade_date"

        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- trading calendar ---------------------------------------------------

    async def insert_trading_calendar(
        self, rows: pd.DataFrame | list[dict[str, Any]]
    ) -> int:
        return await self.insert_table_rows("trading_calendar", rows)

    # ---- security status history --------------------------------------------

    async def insert_security_status_history(
        self, rows: pd.DataFrame | list[dict[str, Any]]
    ) -> int:
        return await self.insert_table_rows("security_status_history", rows)

    # ---- adjust factors -----------------------------------------------------

    async def insert_adjust_factors(
        self, rows: pd.DataFrame | list[dict[str, Any]]
    ) -> int:
        return await self.insert_table_rows("adjust_factors", rows)

    async def query_adjust_factors(
        self,
        symbol: str,
        adjust: str = "qfq",
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        sql = "SELECT * FROM adjust_factors WHERE symbol = :symbol AND adjust = :adjust"
        params: dict[str, Any] = {"symbol": symbol, "adjust": adjust}
        if start:
            sql += " AND trade_date >= :start"
            params["start"] = start
        if end:
            sql += " AND trade_date <= :end"
            params["end"] = end
        sql += " ORDER BY trade_date"

        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- technical indicators -----------------------------------------------

    async def insert_technical_indicators(
        self, rows: pd.DataFrame | list[dict[str, Any]]
    ) -> int:
        if isinstance(rows, pd.DataFrame):
            df = rows.copy()
        else:
            df = pd.DataFrame(rows)
        if df.empty:
            return 0
        df = self._normalise_kline_times(df)
        if "interval" in df.columns:
            df["interval"] = df["interval"].fillna("1d").apply(self._normalise_interval)
        return await self.insert_table_rows("technical_indicators", df)

    async def query_technical_indicators(
        self,
        symbol: str,
        indicator: str,
        interval: str = "1d",
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        interval = self._normalise_interval(interval)
        sql = (
            "SELECT * FROM technical_indicators "
            "WHERE symbol = :symbol AND indicator = :indicator AND interval = :interval"
        )
        params: dict[str, Any] = {"symbol": symbol, "indicator": indicator, "interval": interval}
        if start:
            sql += " AND bar_time >= :start"
            params["start"] = start
        if end:
            sql += " AND bar_time <= :end"
            params["end"] = end
        sql += " ORDER BY bar_time"

        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- data quality / snapshots / partitions / ingestion ------------------

    async def store_data_snapshot(self, snapshot: dict[str, Any]) -> int:
        data = dict(snapshot)
        if "snapshot_id" not in data:
            data["snapshot_id"] = uuid.uuid4().hex
        if "metadata_json" not in data and isinstance(data.get("metadata"), dict):
            data["metadata_json"] = json.dumps(data.pop("metadata"), ensure_ascii=False, sort_keys=True)
        return await self.insert_table_rows("data_snapshots", [data])

    async def store_data_quality_check(self, check: dict[str, Any]) -> int:
        data = dict(check)
        if "check_id" not in data:
            data["check_id"] = uuid.uuid4().hex
        if "details_json" not in data and isinstance(data.get("details"), dict):
            data["details_json"] = json.dumps(data.pop("details"), ensure_ascii=False, sort_keys=True)
        if "fallback_path_json" not in data and isinstance(data.get("fallback_path"), list):
            data["fallback_path_json"] = json.dumps(data.pop("fallback_path"), ensure_ascii=False)
        return await self.insert_table_rows("data_quality_checks", [data])

    async def store_data_partition(self, partition: dict[str, Any]) -> int:
        data = dict(partition)
        if "partition_id" not in data:
            data["partition_id"] = uuid.uuid4().hex
        return await self.insert_table_rows("data_partitions", [data])

    async def store_ingestion_job(self, job: dict[str, Any]) -> int:
        data = dict(job)
        if "job_id" not in data:
            data["job_id"] = uuid.uuid4().hex
        if "metadata_json" not in data and isinstance(data.get("metadata"), dict):
            data["metadata_json"] = json.dumps(data.pop("metadata"), ensure_ascii=False, sort_keys=True)
        return await self.insert_table_rows("data_ingestion_jobs", [data])

    async def store_ingestion_job_event(self, event: dict[str, Any]) -> int:
        data = dict(event)
        if "event_id" not in data:
            data["event_id"] = uuid.uuid4().hex
        if "metadata_json" not in data and isinstance(data.get("metadata"), dict):
            data["metadata_json"] = json.dumps(data.pop("metadata"), ensure_ascii=False, sort_keys=True)
        return await self.insert_table_rows("data_ingestion_job_events", [data])

    # ---- audit log ----------------------------------------------------------

    async def store_audit_log(
        self,
        event_type: str,
        action: str,
        *,
        actor: str | None = None,
        actor_ip: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        detail: dict[str, Any] | None = None,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        outcome: str = "success",
    ) -> str:
        """Write an audit event to the audit_log table. Returns the event_id."""
        event_id = uuid.uuid4().hex
        record = {
            "event_id": event_id,
            "event_type": event_type,
            "actor": actor,
            "actor_ip": actor_ip,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action": action,
            "detail_json": json.dumps(detail, ensure_ascii=False) if detail else None,
            "old_value_json": json.dumps(old_value, ensure_ascii=False) if old_value else None,
            "new_value_json": json.dumps(new_value, ensure_ascii=False) if new_value else None,
            "outcome": outcome,
        }
        pk_cols = ["event_id"]
        columns = list(record.keys())
        sql = self._build_upsert_sql("audit_log", columns, pk_cols)

        if self._sync:
            with self._sync_engine.connect() as conn:
                conn.execute(text(sql), record)
                conn.commit()
        else:
            async with self._async_session_factory() as session:
                await session.execute(text(sql), record)
                await session.commit()
        return event_id

    async def query_audit_log(
        self,
        *,
        actor: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> pd.DataFrame:
        sql = "SELECT * FROM audit_log WHERE 1=1"
        params: dict[str, Any] = {}
        if actor:
            sql += " AND actor = :actor"
            params["actor"] = actor
        if resource_type:
            sql += " AND resource_type = :resource_type"
            params["resource_type"] = resource_type
        if resource_id:
            sql += " AND resource_id = :resource_id"
            params["resource_id"] = resource_id
        if event_type:
            sql += " AND event_type = :event_type"
            params["event_type"] = event_type
        sql += " ORDER BY event_time DESC LIMIT :limit"
        params["limit"] = limit

        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- API keys -----------------------------------------------------------

    async def add_api_key(
        self,
        *,
        key_hash: str,
        key_prefix: str = "",
        label: str = "",
        role: str = "readonly",
        owner: str = "",
        allowed_capabilities: str = "",
        rate_limit: int = 100,
        expires_at: str | None = None,
    ) -> str:
        """Register an API key hash. Returns key_id."""
        key_id = uuid.uuid4().hex
        record = {
            "key_id": key_id,
            "key_hash": key_hash,
            "key_prefix": key_prefix,
            "label": label,
            "role": role,
            "owner": owner,
            "allowed_capabilities": allowed_capabilities,
            "rate_limit": rate_limit,
            "expires_at": expires_at,
            "is_active": True,
        }
        columns = list(record.keys())
        pk_cols = ["key_id"]
        sql = self._build_upsert_sql("api_keys", columns, pk_cols)

        if self._sync:
            with self._sync_engine.connect() as conn:
                conn.execute(text(sql), record)
                conn.commit()
        else:
            async with self._async_session_factory() as session:
                await session.execute(text(sql), record)
                await session.commit()
        return key_id

    async def revoke_api_key(self, key_id: str) -> None:
        if self._sync:
            with self._sync_engine.connect() as conn:
                conn.execute(
                    text("UPDATE api_keys SET is_active = FALSE WHERE key_id = :kid"),
                    {"kid": key_id},
                )
                conn.commit()
        else:
            async with self._async_session_factory() as session:
                await session.execute(
                    text("UPDATE api_keys SET is_active = FALSE WHERE key_id = :kid"),
                    {"kid": key_id},
                )
                await session.commit()

    async def validate_api_key(self, key_hash: str) -> dict[str, Any] | None:
        """Check if a key hash is valid and active. Returns key record or None."""
        sql = (
            "SELECT key_id, role, allowed_capabilities, rate_limit, expires_at "
            "FROM api_keys WHERE key_hash = :kh AND (is_active IS NULL OR is_active = TRUE) "
            "AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)"
        )
        params = {"kh": key_hash}

        if self._sync:
            with self._sync_engine.connect() as conn:
                row = conn.execute(text(sql), params).fetchone()
                if row is None:
                    return None
                record = {
                    "key_id": str(row[0]),
                    "role": str(row[1]),
                    "allowed_capabilities": str(row[2]) if row[2] else "",
                    "rate_limit": int(row[3]) if row[3] else 100,
                }
                conn.execute(
                    text("UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE key_id = :kid"),
                    {"kid": record["key_id"]},
                )
                conn.commit()
                return record
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                row = result.fetchone()
                if row is None:
                    return None
                record = {
                    "key_id": str(row[0]),
                    "role": str(row[1]),
                    "allowed_capabilities": str(row[2]) if row[2] else "",
                    "rate_limit": int(row[3]) if row[3] else 100,
                }
                await conn.execute(
                    text("UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE key_id = :kid"),
                    {"kid": record["key_id"]},
                )
                await conn.commit()
                return record

    # ---- data quality rules -------------------------------------------------

    async def store_quality_rule(
        self,
        *,
        rule_name: str,
        description: str = "",
        scope_dataset: str = "",
        scope_interval: str = "",
        check_sql: str = "",
        severity: str = "warn",
        is_active: bool = True,
        cooldown_minutes: int = 0,
    ) -> str:
        """Register a data quality rule. Returns rule_id."""
        rule_id = uuid.uuid4().hex
        record = {
            "rule_id": rule_id,
            "rule_name": rule_name,
            "description": description,
            "scope_dataset": scope_dataset,
            "scope_interval": scope_interval,
            "check_sql": check_sql,
            "severity": severity,
            "is_active": is_active,
            "cooldown_minutes": cooldown_minutes,
        }
        columns = list(record.keys())
        pk_cols = ["rule_id"]
        sql = self._build_upsert_sql("data_quality_rules", columns, pk_cols)

        if self._sync:
            with self._sync_engine.connect() as conn:
                conn.execute(text(sql), record)
                conn.commit()
        else:
            async with self._async_session_factory() as session:
                await session.execute(text(sql), record)
                await session.commit()
        return rule_id

    async def run_quality_rule(
        self, rule_id: str, *, dry_run: bool = False
    ) -> dict[str, Any]:
        """Execute a single quality rule and store results.

        Returns ``{rule_id, status, matched, failed, details}``.
        """
        sql_rule = (
            "SELECT rule_name, check_sql, severity FROM data_quality_rules "
            "WHERE rule_id = :rid AND is_active = TRUE"
        )
        params = {"rid": rule_id}

        if self._sync:
            with self._sync_engine.connect() as conn:
                row = conn.execute(text(sql_rule), params).fetchone()
                if row is None:
                    raise ValueError(f"Quality rule {rule_id!r} not found or inactive")
                rule_name, check_sql_str, severity = str(row[0]), str(row[1] or ""), str(row[2])
                if not check_sql_str:
                    raise ValueError(f"Quality rule {rule_id!r} has no check_sql defined")
                try:
                    result = conn.execute(text(check_sql_str))
                    result_rows = result.fetchall()
                    row_count = len(result_rows)
                    failed = row_count
                    status = "pass" if failed == 0 else severity
                except Exception as exc:
                    status = "error"
                    failed = -1
                    row_count = 0
                    _ = exc

                quarantined = 0
                if not dry_run and failed > 0 and status != "error":
                    for r in result_rows:
                        q_symbol = str(r[0]) if r else ""
                        self._store_quarantine_sync(
                            source_dataset=rule_name.split(":")[0] if ":" in rule_name else "unknown",
                            symbol=q_symbol,
                            reason=f"Quality rule {rule_name} failed",
                            rule_id=rule_id,
                            original_values=dict(r._mapping) if hasattr(r, "_mapping") else {},
                            severity=severity,
                        )
                        quarantined += 1

                conn.execute(
                    text(
                        "UPDATE data_quality_rules SET last_run_at = CURRENT_TIMESTAMP, "
                        "last_result = :status, failure_count = failure_count + :fc "
                        "WHERE rule_id = :rid"
                    ),
                    {"status": status, "fc": max(failed, 0), "rid": rule_id},
                )
                conn.commit()

                # Store quality check
                check_data = {
                    "dataset": rule_name,
                    "rule_version": rule_id,
                    "status": status,
                    "invalid_count": max(failed, 0),
                    "details": {"rows_checked": row_count, "severity": severity},
                }
                self._store_quality_check_sync(check_data)

                return {
                    "rule_id": rule_id,
                    "status": status,
                    "matched": row_count,
                    "failed": failed,
                    "quarantined": quarantined,
                }
        else:
            async with self._async_engine.connect() as conn:
                row = await conn.execute(text(sql_rule), params)
                row_data = row.fetchone()
                if row_data is None:
                    raise ValueError(f"Quality rule {rule_id!r} not found or inactive")
                rule_name, check_sql_str, severity = (
                    str(row_data[0]),
                    str(row_data[1] or ""),
                    str(row_data[2]),
                )
                if not check_sql_str:
                    raise ValueError(f"Quality rule {rule_id!r} has no check_sql defined")
                try:
                    result = await conn.execute(text(check_sql_str))
                    result_rows = result.fetchall()
                    row_count = len(result_rows)
                    failed = row_count
                    status = "pass" if failed == 0 else severity
                except Exception as exc:
                    status = "error"
                    failed = -1
                    row_count = 0
                    _ = exc

                quarantined = 0
                if not dry_run and failed > 0 and status != "error":
                    for r in result_rows:
                        q_symbol = str(r[0]) if r else ""
                        await self._store_quarantine_async(
                            source_dataset=rule_name.split(":")[0] if ":" in rule_name else "unknown",
                            symbol=q_symbol,
                            reason=f"Quality rule {rule_name} failed",
                            rule_id=rule_id,
                            original_values=dict(r._mapping) if hasattr(r, "_mapping") else {},
                            severity=severity,
                        )
                        quarantined += 1

                await conn.execute(
                    text(
                        "UPDATE data_quality_rules SET last_run_at = CURRENT_TIMESTAMP, "
                        "last_result = :status, failure_count = failure_count + :fc "
                        "WHERE rule_id = :rid"
                    ),
                    {"status": status, "fc": max(failed, 0), "rid": rule_id},
                )
                await conn.commit()

                check_data = {
                    "dataset": rule_name,
                    "rule_version": rule_id,
                    "status": status,
                    "invalid_count": max(failed, 0),
                    "details": {"rows_checked": row_count, "severity": severity},
                }
                await self.store_data_quality_check(check_data)

                return {
                    "rule_id": rule_id,
                    "status": status,
                    "matched": row_count,
                    "failed": failed,
                    "quarantined": quarantined,
                }

    async def run_all_quality_rules(self) -> list[dict[str, Any]]:
        """Run all active quality rules and return results."""
        sql = "SELECT rule_id FROM data_quality_rules WHERE is_active = TRUE"
        if self._sync:
            with self._sync_engine.connect() as conn:
                rule_rows = conn.execute(text(sql)).fetchall()
                results = []
                for (rule_id_val,) in rule_rows:
                    try:
                        results.append(
                            self._run_async(self.run_quality_rule(rule_id_val))
                        )
                    except Exception as exc:
                        results.append({"rule_id": rule_id_val, "status": "error", "error": str(exc)})
                return results
        else:
            async with self._async_engine.connect() as conn:
                rule_rows = await conn.execute(text(sql))
                results = []
                for row in rule_rows.fetchall():
                    rule_id_val = str(row[0])
                    try:
                        results.append(await self.run_quality_rule(rule_id_val))
                    except Exception as exc:
                        results.append({"rule_id": rule_id_val, "status": "error", "error": str(exc)})
                return results

    # ---- data quarantine internal helpers -----------------------------------

    def _store_quarantine_sync(self, **kwargs: Any) -> str:
        quarantine_id = uuid.uuid4().hex
        record = {
            "quarantine_id": quarantine_id,
            "source_dataset": kwargs.get("source_dataset", ""),
            "symbol": kwargs.get("symbol", ""),
            "interval": kwargs.get("interval", ""),
            "bar_time": kwargs.get("bar_time"),
            "trade_date": kwargs.get("trade_date"),
            "reason": kwargs.get("reason", ""),
            "rule_id": kwargs.get("rule_id"),
            "original_values_json": json.dumps(kwargs.get("original_values", {}), ensure_ascii=False),
            "severity": kwargs.get("severity", "warn"),
            "resolution": kwargs.get("resolution", "unresolved"),
        }
        columns = list(record.keys())
        pk_cols = ["quarantine_id"]
        sql = self._build_upsert_sql("data_quarantine", columns, pk_cols)
        with self._sync_engine.connect() as conn:
            conn.execute(text(sql), record)
            conn.commit()
        return quarantine_id

    async def _store_quarantine_async(self, **kwargs: Any) -> str:
        quarantine_id = uuid.uuid4().hex
        record = {
            "quarantine_id": quarantine_id,
            "source_dataset": kwargs.get("source_dataset", ""),
            "symbol": kwargs.get("symbol", ""),
            "interval": kwargs.get("interval", ""),
            "bar_time": kwargs.get("bar_time"),
            "trade_date": kwargs.get("trade_date"),
            "reason": kwargs.get("reason", ""),
            "rule_id": kwargs.get("rule_id"),
            "original_values_json": json.dumps(kwargs.get("original_values", {}), ensure_ascii=False),
            "severity": kwargs.get("severity", "warn"),
            "resolution": kwargs.get("resolution", "unresolved"),
        }
        columns = list(record.keys())
        pk_cols = ["quarantine_id"]
        sql = self._build_upsert_sql("data_quarantine", columns, pk_cols)
        async with self._async_session_factory() as session:
            await session.execute(text(sql), record)
            await session.commit()
        return quarantine_id

    def _store_quality_check_sync(self, check: dict[str, Any]) -> int:
        data = dict(check)
        if "check_id" not in data:
            data["check_id"] = uuid.uuid4().hex
        if "details_json" not in data and isinstance(data.get("details"), dict):
            data["details_json"] = json.dumps(data.pop("details"), ensure_ascii=False, sort_keys=True)
        columns = list(data.keys())
        pk_cols = ["check_id"]
        sql = self._build_upsert_sql("data_quality_checks", columns, pk_cols)
        with self._sync_engine.connect() as conn:
            conn.execute(text(sql), data)
            conn.commit()
        return 1

    # ---- data quarantine public API -----------------------------------------

    async def store_quarantine(
        self,
        *,
        source_dataset: str,
        symbol: str = "",
        interval: str = "",
        bar_time: str | None = None,
        trade_date: str | None = None,
        reason: str = "",
        rule_id: str | None = None,
        original_values: dict[str, Any] | None = None,
        severity: str = "warn",
    ) -> str:
        """Move anomalous data into the quarantine zone. Returns quarantine_id."""
        if self._sync:
            return self._store_quarantine_sync(
                source_dataset=source_dataset,
                symbol=symbol,
                interval=interval,
                bar_time=bar_time,
                trade_date=trade_date,
                reason=reason,
                rule_id=rule_id,
                original_values=original_values,
                severity=severity,
            )
        return await self._store_quarantine_async(
            source_dataset=source_dataset,
            symbol=symbol,
            interval=interval,
            bar_time=bar_time,
            trade_date=trade_date,
            reason=reason,
            rule_id=rule_id,
            original_values=original_values,
            severity=severity,
        )

    async def resolve_quarantine(
        self, quarantine_id: str, *, resolved_by: str = "system"
    ) -> None:
        if self._sync:
            with self._sync_engine.connect() as conn:
                conn.execute(
                    text(
                        "UPDATE data_quarantine SET resolution = 'resolved', "
                        "resolved_by = :rb, resolved_at = CURRENT_TIMESTAMP "
                        "WHERE quarantine_id = :qid"
                    ),
                    {"rb": resolved_by, "qid": quarantine_id},
                )
                conn.commit()
        else:
            async with self._async_session_factory() as session:
                await session.execute(
                    text(
                        "UPDATE data_quarantine SET resolution = 'resolved', "
                        "resolved_by = :rb, resolved_at = CURRENT_TIMESTAMP "
                        "WHERE quarantine_id = :qid"
                    ),
                    {"rb": resolved_by, "qid": quarantine_id},
                )
                await session.commit()

    async def query_quarantine(
        self,
        *,
        severity: str | None = None,
        resolution: str = "unresolved",
        limit: int = 100,
    ) -> pd.DataFrame:
        sql = "SELECT * FROM data_quarantine WHERE resolution = :resolution"
        params: dict[str, Any] = {"resolution": resolution}
        if severity:
            sql += " AND severity = :severity"
            params["severity"] = severity
        sql += " ORDER BY created_at DESC LIMIT :limit"
        params["limit"] = limit

        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- schema introspection -----------------------------------------------

    async def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        sql = (
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = :name AND table_schema = :schema"
        )
        params = {"name": table_name, "schema": self._config.schema}
        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params).scalar()
                return result is not None and result > 0
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                val = result.scalar()
                return val is not None and val > 0

    async def list_symbols(self, table_name: str | None = None) -> list[str]:
        """Return known symbols from managed tables."""
        tables = [table_name] if table_name else ALL_TABLE_NAMES
        symbols: set[str] = set()
        for tbl in tables:
            if not tbl or not await self.table_exists(tbl):
                continue
            try:
                sql = f'SELECT DISTINCT symbol FROM "{tbl}" WHERE symbol IS NOT NULL'
                if self._sync:
                    with self._sync_engine.connect() as conn:
                        rows = conn.execute(text(sql)).fetchall()
                else:
                    async with self._async_engine.connect() as conn:
                        result = await conn.execute(text(sql))
                        rows = result.fetchall()
                for (sym,) in rows:
                    if sym:
                        symbols.add(str(sym))
            except Exception:
                continue
        return sorted(symbols)

    async def list_tables(self) -> list[str]:
        """Return list of managed table names that exist."""
        existing = []
        for table_name in ALL_TABLE_NAMES:
            if await self.table_exists(table_name):
                existing.append(table_name)
        return existing

    async def _table_columns(self, table_name: str) -> list[str]:
        """Return column names for a table via information_schema."""
        sql = (
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :name AND table_schema = :schema "
            "ORDER BY ordinal_position"
        )
        params = {"name": table_name, "schema": self._config.schema}
        if self._sync:
            with self._sync_engine.connect() as conn:
                rows = conn.execute(text(sql), params).fetchall()
                return [str(r[0]) for r in rows]
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return [str(r[0]) for r in rows]

    # ---- stats --------------------------------------------------------------

    async def get_table_stats(self) -> dict[str, dict[str, Any]]:
        """Return per-table row counts and latest date info."""
        stats: dict[str, dict[str, Any]] = {}
        for table_name in ALL_TABLE_NAMES:
            if not await self.table_exists(table_name):
                stats[table_name] = {"rows": 0, "latest_date": None}
                continue
            try:
                row_count = 0
                latest: Any = None
                if self._sync:
                    with self._sync_engine.connect() as conn:
                        row_result = conn.execute(
                            text(f'SELECT count(*) FROM "{table_name}"')
                        ).scalar()
                        row_count = row_result if row_result else 0
                        for date_col in (
                            "bar_time",
                            "trade_date",
                            "report_date",
                            "publish_date",
                            "timestamp",
                            "end_time",
                            "updated_at",
                            "created_at",
                            "list_date",
                        ):
                            try:
                                date_result = conn.execute(
                                    text(f'SELECT max({date_col}) FROM "{table_name}"')
                                ).scalar()
                                if date_result is not None:
                                    latest = str(date_result)
                                    break
                            except Exception:
                                continue
                else:
                    async with self._async_engine.connect() as conn:
                        row_result = await conn.execute(
                            text(f'SELECT count(*) FROM "{table_name}"')
                        )
                        row_count = row_result.scalar() or 0
                        for date_col in (
                            "bar_time",
                            "trade_date",
                            "report_date",
                            "publish_date",
                            "timestamp",
                            "end_time",
                            "updated_at",
                            "created_at",
                            "list_date",
                        ):
                            try:
                                date_result = await conn.execute(
                                    text(f'SELECT max({date_col}) FROM "{table_name}"')
                                )
                                val = date_result.scalar()
                                if val is not None:
                                    latest = str(val)
                                    break
                            except Exception:
                                continue
                stats[table_name] = {"rows": row_count, "latest_date": latest}
            except Exception:
                stats[table_name] = {"rows": 0, "latest_date": None}
        return stats

    # ---- raw SQL query ------------------------------------------------------

    async def query_sql(self, sql_str: str) -> pd.DataFrame:
        """Execute an arbitrary SQL query and return results as a DataFrame."""
        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql_str))
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql_str))
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- migration engine ---------------------------------------------------

    async def migrate(self, *names: str) -> list[dict[str, Any]]:
        """Apply a named, versioned migration if it has not been run before.

        Each migration is a ``(name, description, sql_or_none, rollback_sql_or_none)``
        entry defined in ``_MIGRATIONS``. After the SQL is executed (if any), a
        row is inserted into ``migration_versions``.

        If *names* is empty, all un-applied migrations are run in order.
        Returns a list of ``{version_id, description, status, duration_ms}`` records.
        """
        if not await self.table_exists("migration_versions"):
            async with self._async_engine.begin() as conn:
                await conn.run_sync(MigrationVersion.__table__.create)

        # Get applied migrations
        if self._sync:
            with self._sync_engine.connect() as conn:
                applied = {
                    str(row[0])
                    for row in conn.execute(text("SELECT version_id FROM migration_versions")).fetchall()
                }
        else:
            async with self._async_engine.connect() as conn:
                rows = await conn.execute(text("SELECT version_id FROM migration_versions"))
                applied = {str(r[0]) for r in rows.fetchall()}

        results: list[dict[str, Any]] = []
        candidates = list(self._MIGRATIONS)
        if names:
            candidates = [n for n in candidates if n[0] in names]
            missing = set(names) - {n[0] for n in candidates}
            if missing:
                raise ValueError(f"Unknown migration(s): {missing}. Known: {[m[0] for m in self._MIGRATIONS]}")

        for vid, desc, migration_sql, rollback_sql in candidates:
            if vid in applied:
                continue
            t0 = _time.time()
            status = "applied"
            duration_ms = 0
            try:
                if migration_sql:
                    if self._sync:
                        with self._sync_engine.connect() as conn:
                            conn.execute(text(migration_sql))
                            conn.commit()
                    else:
                        async with self._async_engine.connect() as conn:
                            await conn.execute(text(migration_sql))
                            await conn.commit()
                elapsed = _time.time() - t0
                duration_ms = int(round(elapsed * 1000))
            except Exception as exc:
                status = "failed"
                elapsed = _time.time() - t0
                duration_ms = int(round(elapsed * 1000))
                version_record = {
                    "version_id": vid,
                    "description": desc,
                    "status": status,
                    "duration_ms": duration_ms,
                    "checksum": repr(migration_sql) if migration_sql else "",
                }
                columns = list(version_record.keys())
                pk_cols = ["version_id"]
                sql = self._build_upsert_sql("migration_versions", columns, pk_cols)
                if self._sync:
                    with self._sync_engine.connect() as conn:
                        conn.execute(text(sql), version_record)
                        conn.commit()
                else:
                    async with self._async_session_factory() as session:
                        await session.execute(text(sql), version_record)
                        await session.commit()
                raise RuntimeError(f"Migration {vid!r} failed: {exc}") from exc

            version_record = {
                "version_id": vid,
                "description": desc,
                "status": status,
                "duration_ms": duration_ms,
                "checksum": repr(migration_sql) if migration_sql else "",
                "rollback_sql": rollback_sql,
            }
            columns = list(version_record.keys())
            pk_cols = ["version_id"]
            sql = self._build_upsert_sql("migration_versions", columns, pk_cols)
            if self._sync:
                with self._sync_engine.connect() as conn:
                    conn.execute(text(sql), version_record)
                    conn.commit()
            else:
                async with self._async_session_factory() as session:
                    await session.execute(text(sql), version_record)
                    await session.commit()

            results.append({
                "version_id": vid,
                "description": desc,
                "status": status,
                "duration_ms": duration_ms,
            })
        return results

    async def list_migrations(self) -> pd.DataFrame:
        """Return all applied migration records."""
        return await self.query_sql("SELECT * FROM migration_versions ORDER BY applied_at")

    async def rollback_migration(self, version_id: str) -> None:
        """Roll back a previously applied migration if rollback_sql is set."""
        sql = "SELECT rollback_sql FROM migration_versions WHERE version_id = :vid"
        params = {"vid": version_id}
        if self._sync:
            with self._sync_engine.connect() as conn:
                row = conn.execute(text(sql), params).fetchone()
                if row is None:
                    raise ValueError(f"Migration {version_id!r} not found")
                if not row[0]:
                    raise ValueError(f"Migration {version_id!r} has no rollback SQL defined")
                conn.execute(text(str(row[0])))
                conn.execute(text("DELETE FROM migration_versions WHERE version_id = :vid"), params)
                conn.commit()
        else:
            async with self._async_engine.connect() as conn:
                row = (await conn.execute(text(sql), params)).fetchone()
                if row is None:
                    raise ValueError(f"Migration {version_id!r} not found")
                if not row[0]:
                    raise ValueError(f"Migration {version_id!r} has no rollback SQL defined")
                await conn.execute(text(str(row[0])))
                await conn.execute(text("DELETE FROM migration_versions WHERE version_id = :vid"), params)
                await conn.commit()

    # Migration registry — discoverable class variable
    _MIGRATIONS: list[tuple[str, str, str | None, str | None]] = []

    def discover_migrations(self, migrations_dir: str | None = None) -> int:
        """Auto-discover migration files from the migrations/ directory (mirrors AStockStore)."""
        if migrations_dir is None:
            migrations_dir = os.path.join(os.path.dirname(__file__), "migrations")
        mig_dir = Path(migrations_dir)
        if not mig_dir.is_dir():
            return 0

        import re

        pattern = re.compile(r"^V(\d{8})_(\d{3})__(.+)\.py$")
        count = 0
        for fpath in sorted(mig_dir.iterdir()):
            if not fpath.is_file() or not fpath.name.endswith(".py"):
                continue
            m = pattern.match(fpath.name)
            if not m:
                continue
            version_id = f"V{m.group(1)}_{m.group(2)}"
            name_part = m.group(3)
            content = fpath.read_text(encoding="utf-8")

            description = name_part.replace("_", " ").title()
            ds_match = re.search(r'^\s*description\s*=\s*"([^"]*)"', content, re.MULTILINE)
            if ds_match:
                description = ds_match.group(1)

            upgrade_sql = None
            up_match = re.search(r'def upgrade\([^)]*\):.*?"""(.*?)"""', content, re.DOTALL)
            if up_match:
                sql_block = up_match.group(1).strip()
                if sql_block and sql_block != "TODO: Write your upgrade SQL here":
                    upgrade_sql = sql_block
            if upgrade_sql is None:
                sql_assign = re.search(r'(?:upgrade_sql|ddl)\s*=\s*"""(.*?)"""', content, re.DOTALL)
                if sql_assign:
                    upgrade_sql = sql_assign.group(1).strip()

            rollback_sql = None
            rb_match = re.search(r'def downgrade\([^)]*\):.*?"""(.*?)"""', content, re.DOTALL)
            if rb_match:
                sql_block = rb_match.group(1).strip()
                if sql_block and sql_block != "TODO: Write your downgrade SQL here":
                    rollback_sql = sql_block
            if rollback_sql is None:
                sql_assign = re.search(r'(?:rollback_sql|rollback_ddl)\s*=\s*"""(.*?)"""', content, re.DOTALL)
                if sql_assign:
                    rollback_sql = sql_assign.group(1).strip()

            self._MIGRATIONS.append((version_id, description, upgrade_sql, rollback_sql))
            count += 1

        self._MIGRATIONS.sort(key=lambda x: x[0])
        return count

    # ---- maintenance --------------------------------------------------------

    async def vacuum(self) -> None:
        """Reclaim storage (PostgreSQL VACUUM ANALYZE)."""
        if self._sync:
            with self._sync_engine.connect() as conn:
                conn.execute(text("VACUUM ANALYZE"))
                conn.commit()
        else:
            async with self._async_engine.connect() as conn:
                await conn.execute(text("VACUUM ANALYZE"))
                await conn.commit()

    async def drop_all_tables(self) -> None:
        """Drop all managed tables (for test teardown)."""
        if self._sync:
            Base.metadata.drop_all(self._sync_engine)
        else:
            async with self._async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)

    # ---- industry classification / security master / etc. -------------------

    async def insert_industry_classification(
        self, rows: pd.DataFrame | list[dict[str, Any]]
    ) -> int:
        return await self.insert_table_rows("industry_classification_history", rows)

    async def insert_suspension_events(
        self, rows: pd.DataFrame | list[dict[str, Any]]
    ) -> int:
        return await self.insert_table_rows("suspension_events", rows)

    async def insert_price_limit_rules(
        self, rows: pd.DataFrame | list[dict[str, Any]]
    ) -> int:
        return await self.insert_table_rows("price_limit_rules", rows)

    async def insert_corporate_actions(
        self, rows: pd.DataFrame | list[dict[str, Any]]
    ) -> int:
        return await self.insert_table_rows("corporate_actions", rows)

    async def insert_security_master(
        self, rows: pd.DataFrame | list[dict[str, Any]]
    ) -> int:
        return await self.insert_table_rows("security_master", rows)

    async def insert_data_sources(
        self, rows: pd.DataFrame | list[dict[str, Any]]
    ) -> int:
        return await self.insert_table_rows("data_sources", rows)


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


async def init_pg_store(
    config: PGConfig | None = None, sync: bool = False
) -> PGStore:
    """Create a PGStore, call init_schema(), and return it."""
    store = PGStore(config, sync=sync)
    await store.connect()
    await store.init_schema()
    return store
