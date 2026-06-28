"""DuckDB table definitions and AStockStore — the local database storage layer.

All tables use ``INSERT OR REPLACE`` semantics for upsert-style writes, with
``PRIMARY KEY`` constraints ensuring idempotent re-insertion.
"""

from __future__ import annotations

import csv
import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

import duckdb
import pandas as pd

# ---------------------------------------------------------------------------
# DDL for each table (IF NOT EXISTS, created in init_schema)
# ---------------------------------------------------------------------------

CREATE_KLINE_BARS = """
CREATE TABLE IF NOT EXISTS kline_bars (
    symbol VARCHAR NOT NULL,
    bar_time TIMESTAMP NOT NULL,
    trade_date DATE NOT NULL,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume DOUBLE,
    amount DOUBLE,
    turnover_rate DOUBLE,
    interval VARCHAR DEFAULT '1d',
    adjust VARCHAR DEFAULT 'none',
    quality VARCHAR DEFAULT 'normal',
    source VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, bar_time, interval, adjust),
    CHECK (interval IN ('1m', '5m', '15m', '30m', '60m', '1d', '1w', '1mo', '1y')),
    CHECK (open IS NULL OR open >= 0),
    CHECK (high IS NULL OR high >= 0),
    CHECK (low IS NULL OR low >= 0),
    CHECK (close IS NULL OR close >= 0),
    CHECK (high IS NULL OR low IS NULL OR high >= low),
    CHECK (volume IS NULL OR volume >= 0),
    CHECK (amount IS NULL OR amount >= 0)
)
"""

SUPPORTED_KLINE_INTERVALS = frozenset(("1m", "5m", "15m", "30m", "60m", "1d", "1w", "1mo", "1y"))

CREATE_DATABASE_STORAGE_PROFILES = """
CREATE TABLE IF NOT EXISTS database_storage_profiles (
    profile_name VARCHAR NOT NULL,
    role VARCHAR NOT NULL,
    engine VARCHAR NOT NULL,
    read_write_model VARCHAR,
    notes VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (profile_name)
)
"""

CREATE_SECURITY_MASTER = """
CREATE TABLE IF NOT EXISTS security_master (
    symbol VARCHAR NOT NULL,
    raw_symbol VARCHAR,
    name VARCHAR,
    exchange VARCHAR,
    board VARCHAR,
    currency VARCHAR DEFAULT 'CNY',
    list_date DATE,
    delist_date DATE,
    status VARCHAR DEFAULT 'active',
    is_st BOOLEAN DEFAULT FALSE,
    source VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol)
)
"""

CREATE_TRADING_CALENDAR = """
CREATE TABLE IF NOT EXISTS trading_calendar (
    exchange VARCHAR NOT NULL,
    trade_date DATE NOT NULL,
    is_open BOOLEAN NOT NULL,
    session_open TIMESTAMP,
    session_close TIMESTAMP,
    session_break_json VARCHAR,
    source VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (exchange, trade_date)
)
"""

CREATE_SECURITY_STATUS_HISTORY = """
CREATE TABLE IF NOT EXISTS security_status_history (
    symbol VARCHAR NOT NULL,
    effective_date DATE NOT NULL,
    status VARCHAR NOT NULL,
    is_st BOOLEAN DEFAULT FALSE,
    reason VARCHAR,
    source VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, effective_date)
)
"""

CREATE_INDUSTRY_CLASSIFICATION_HISTORY = """
CREATE TABLE IF NOT EXISTS industry_classification_history (
    symbol VARCHAR NOT NULL,
    effective_date DATE NOT NULL,
    classification VARCHAR NOT NULL,
    industry_code VARCHAR,
    industry_name VARCHAR,
    level INTEGER DEFAULT 1,
    source VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, effective_date, classification, level)
)
"""

CREATE_SUSPENSION_EVENTS = """
CREATE TABLE IF NOT EXISTS suspension_events (
    symbol VARCHAR NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    reason VARCHAR,
    source VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, start_date)
)
"""

CREATE_PRICE_LIMIT_RULES = """
CREATE TABLE IF NOT EXISTS price_limit_rules (
    rule_id VARCHAR NOT NULL,
    exchange VARCHAR,
    board VARCHAR,
    effective_date DATE NOT NULL,
    end_date DATE,
    up_limit_pct DOUBLE,
    down_limit_pct DOUBLE,
    source VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (rule_id)
)
"""

CREATE_VALUATIONS = """
CREATE TABLE IF NOT EXISTS valuations (
    symbol VARCHAR,
    trade_date DATE,
    pe DOUBLE,
    pb DOUBLE,
    market_cap DOUBLE,
    source VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, trade_date)
)
"""

CREATE_CORPORATE_ACTIONS = """
CREATE TABLE IF NOT EXISTS corporate_actions (
    action_id VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    action_date DATE NOT NULL,
    ex_date DATE,
    action_type VARCHAR NOT NULL,
    cash_dividend DOUBLE,
    stock_dividend_ratio DOUBLE,
    split_ratio DOUBLE,
    rights_issue_price DOUBLE,
    raw_json VARCHAR,
    source VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (action_id)
)
"""

CREATE_ADJUST_FACTORS = """
CREATE TABLE IF NOT EXISTS adjust_factors (
    symbol VARCHAR NOT NULL,
    trade_date DATE NOT NULL,
    adjust VARCHAR NOT NULL,
    factor DOUBLE NOT NULL,
    source VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, trade_date, adjust),
    CHECK (adjust IN ('none', 'qfq', 'hfq')),
    CHECK (factor > 0)
)
"""

CREATE_ORDER_BOOK_SNAPSHOTS = """
CREATE TABLE IF NOT EXISTS order_book_snapshots (
    symbol VARCHAR,
    timestamp TIMESTAMP,
    bid_price DOUBLE,
    bid_volume DOUBLE,
    ask_price DOUBLE,
    ask_volume DOUBLE,
    source VARCHAR,
    PRIMARY KEY (symbol, timestamp)
)
"""

CREATE_TRADE_TAPE = """
CREATE TABLE IF NOT EXISTS trade_tape (
    symbol VARCHAR,
    timestamp TIMESTAMP,
    price DOUBLE,
    volume DOUBLE,
    direction VARCHAR,
    source VARCHAR,
    PRIMARY KEY (symbol, timestamp)
)
"""

CREATE_RESEARCH_REPORTS = """
CREATE TABLE IF NOT EXISTS research_reports (
    symbol VARCHAR,
    report_date DATE,
    title VARCHAR,
    institution VARCHAR,
    analyst VARCHAR,
    rating VARCHAR,
    pdf_url VARCHAR,
    source VARCHAR,
    PRIMARY KEY (symbol, report_date, title)
)
"""

CREATE_NEWS_ITEMS = """
CREATE TABLE IF NOT EXISTS news_items (
    symbol VARCHAR,
    publish_date DATE,
    title VARCHAR,
    summary VARCHAR,
    url VARCHAR,
    source VARCHAR,
    PRIMARY KEY (symbol, publish_date, url)
)
"""

CREATE_ANNOUNCEMENTS = """
CREATE TABLE IF NOT EXISTS announcements (
    symbol VARCHAR,
    publish_date DATE,
    title VARCHAR,
    summary VARCHAR,
    url VARCHAR,
    PRIMARY KEY (symbol, publish_date, url)
)
"""

CREATE_BACKTEST_RESULTS = """
CREATE TABLE IF NOT EXISTS backtest_results (
    run_id VARCHAR,
    symbol VARCHAR,
    strategy_name VARCHAR,
    start_date DATE,
    end_date DATE,
    total_return DOUBLE,
    annualized_return DOUBLE,
    sharpe_ratio DOUBLE,
    max_drawdown DOUBLE,
    win_rate DOUBLE,
    total_trades INTEGER,
    params_json VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id)
)
"""

CREATE_PAPER_TRADES = """
CREATE TABLE IF NOT EXISTS paper_trades (
    trade_id VARCHAR,
    symbol VARCHAR,
    direction VARCHAR,
    price DOUBLE,
    volume DOUBLE,
    fees DOUBLE,
    trade_date DATE,
    strategy_name VARCHAR,
    actionable BOOLEAN DEFAULT FALSE,
    decision_scope VARCHAR DEFAULT 'paper_trading_only',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (trade_id)
)
"""

CREATE_MARKET_INDICATORS = """
CREATE TABLE IF NOT EXISTS market_indicators (
    symbol VARCHAR,
    trade_date DATE,
    ma_5 DOUBLE,
    ma_20 DOUBLE,
    ma_60 DOUBLE,
    rsi_14 DOUBLE,
    atr_14 DOUBLE,
    volume_ma_5 DOUBLE,
    PRIMARY KEY (symbol, trade_date)
)
"""

CREATE_TECHNICAL_INDICATORS = """
CREATE TABLE IF NOT EXISTS technical_indicators (
    symbol VARCHAR NOT NULL,
    bar_time TIMESTAMP NOT NULL,
    trade_date DATE NOT NULL,
    interval VARCHAR NOT NULL,
    indicator VARCHAR NOT NULL,
    params_hash VARCHAR NOT NULL,
    params_json VARCHAR,
    value_json VARCHAR NOT NULL,
    source_snapshot_id VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, bar_time, interval, indicator, params_hash),
    CHECK (interval IN ('1m', '5m', '15m', '30m', '60m', '1d', '1w', '1mo', '1y'))
)
"""

CREATE_DATA_SOURCES = """
CREATE TABLE IF NOT EXISTS data_sources (
    source_id VARCHAR NOT NULL,
    provider VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    priority INTEGER DEFAULT 100,
    license_status VARCHAR DEFAULT 'unknown',
    rate_limit_json VARCHAR,
    auth_required BOOLEAN DEFAULT FALSE,
    enabled BOOLEAN DEFAULT TRUE,
    notes VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_id)
)
"""

CREATE_DATA_QUALITY_CHECKS = """
CREATE TABLE IF NOT EXISTS data_quality_checks (
    check_id VARCHAR NOT NULL,
    dataset VARCHAR NOT NULL,
    symbol VARCHAR,
    interval VARCHAR,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    rule_version VARCHAR,
    status VARCHAR NOT NULL,
    missing_count BIGINT DEFAULT 0,
    invalid_count BIGINT DEFAULT 0,
    duplicate_count BIGINT DEFAULT 0,
    fallback_path_json VARCHAR,
    details_json VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (check_id)
)
"""

CREATE_DATA_SNAPSHOTS = """
CREATE TABLE IF NOT EXISTS data_snapshots (
    snapshot_id VARCHAR NOT NULL,
    dataset VARCHAR NOT NULL,
    symbol VARCHAR,
    interval VARCHAR,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    row_count BIGINT DEFAULT 0,
    source VARCHAR,
    quality VARCHAR DEFAULT 'normal',
    metadata_json VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (snapshot_id)
)
"""

CREATE_DATA_PARTITIONS = """
CREATE TABLE IF NOT EXISTS data_partitions (
    partition_id VARCHAR NOT NULL,
    dataset VARCHAR NOT NULL,
    symbol VARCHAR,
    interval VARCHAR,
    partition_key VARCHAR NOT NULL,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    storage_tier VARCHAR DEFAULT 'hot',
    uri VARCHAR,
    row_count BIGINT DEFAULT 0,
    status VARCHAR DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (partition_id)
)
"""

CREATE_DATA_INGESTION_JOBS = """
CREATE TABLE IF NOT EXISTS data_ingestion_jobs (
    job_id VARCHAR NOT NULL,
    job_type VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'queued',
    target_table VARCHAR,
    source_uri VARCHAR,
    total_rows BIGINT DEFAULT 0,
    processed_rows BIGINT DEFAULT 0,
    error_message VARCHAR,
    metadata_json VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (job_id)
)
"""

CREATE_DATA_INGESTION_JOB_EVENTS = """
CREATE TABLE IF NOT EXISTS data_ingestion_job_events (
    event_id VARCHAR NOT NULL,
    job_id VARCHAR NOT NULL,
    event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR NOT NULL,
    processed_rows BIGINT DEFAULT 0,
    message VARCHAR,
    error_message VARCHAR,
    metadata_json VARCHAR,
    PRIMARY KEY (event_id)
)
"""
CREATE_MIGRATION_VERSIONS = """
CREATE TABLE IF NOT EXISTS migration_versions (
    version_id VARCHAR NOT NULL,
    description VARCHAR,
    applied_by VARCHAR,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checksum VARCHAR,
    duration_ms BIGINT DEFAULT 0,
    status VARCHAR DEFAULT 'applied',
    rollback_sql VARCHAR,
    PRIMARY KEY (version_id)
)
"""

CREATE_AUDIT_LOG = """
CREATE TABLE IF NOT EXISTS audit_log (
    event_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    actor VARCHAR,
    actor_ip VARCHAR,
    resource_type VARCHAR,
    resource_id VARCHAR,
    action VARCHAR NOT NULL,
    detail_json VARCHAR,
    old_value_json VARCHAR,
    new_value_json VARCHAR,
    outcome VARCHAR DEFAULT 'success',
    event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (event_id)
)
"""

CREATE_API_KEYS = """
CREATE TABLE IF NOT EXISTS api_keys (
    key_id VARCHAR NOT NULL,
    key_hash VARCHAR NOT NULL,
    key_prefix VARCHAR(8),
    label VARCHAR,
    role VARCHAR DEFAULT 'readonly',
    owner VARCHAR,
    allowed_capabilities VARCHAR,
    rate_limit INTEGER DEFAULT 100,
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (key_id)
)
"""

CREATE_DATA_QUALITY_RULES = """
CREATE TABLE IF NOT EXISTS data_quality_rules (
    rule_id VARCHAR NOT NULL,
    rule_name VARCHAR NOT NULL,
    description VARCHAR,
    scope_dataset VARCHAR,
    scope_interval VARCHAR,
    check_sql VARCHAR,
    severity VARCHAR DEFAULT 'warn',
    is_active BOOLEAN DEFAULT TRUE,
    cooldown_minutes INTEGER DEFAULT 0,
    last_run_at TIMESTAMP,
    last_result VARCHAR,
    failure_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (rule_id)
)
"""

CREATE_DATA_QUARANTINE = """
CREATE TABLE IF NOT EXISTS data_quarantine (
    quarantine_id VARCHAR NOT NULL,
    source_dataset VARCHAR NOT NULL,
    symbol VARCHAR,
    interval VARCHAR,
    bar_time TIMESTAMP,
    trade_date DATE,
    reason VARCHAR NOT NULL,
    rule_id VARCHAR,
    original_values_json VARCHAR NOT NULL,
    severity VARCHAR DEFAULT 'warn',
    resolution VARCHAR DEFAULT 'unresolved',
    resolved_by VARCHAR,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (quarantine_id)
)
"""

# All tables in creation order
ALL_TABLE_DEFS: dict[str, str] = {
    "database_storage_profiles": CREATE_DATABASE_STORAGE_PROFILES,
    "security_master": CREATE_SECURITY_MASTER,
    "trading_calendar": CREATE_TRADING_CALENDAR,
    "security_status_history": CREATE_SECURITY_STATUS_HISTORY,
    "industry_classification_history": CREATE_INDUSTRY_CLASSIFICATION_HISTORY,
    "suspension_events": CREATE_SUSPENSION_EVENTS,
    "price_limit_rules": CREATE_PRICE_LIMIT_RULES,
    "kline_bars": CREATE_KLINE_BARS,
    "valuations": CREATE_VALUATIONS,
    "corporate_actions": CREATE_CORPORATE_ACTIONS,
    "adjust_factors": CREATE_ADJUST_FACTORS,
    "order_book_snapshots": CREATE_ORDER_BOOK_SNAPSHOTS,
    "trade_tape": CREATE_TRADE_TAPE,
    "research_reports": CREATE_RESEARCH_REPORTS,
    "news_items": CREATE_NEWS_ITEMS,
    "announcements": CREATE_ANNOUNCEMENTS,
    "backtest_results": CREATE_BACKTEST_RESULTS,
    "paper_trades": CREATE_PAPER_TRADES,
    "market_indicators": CREATE_MARKET_INDICATORS,
    "technical_indicators": CREATE_TECHNICAL_INDICATORS,
    "data_sources": CREATE_DATA_SOURCES,
    "data_quality_checks": CREATE_DATA_QUALITY_CHECKS,
    "data_snapshots": CREATE_DATA_SNAPSHOTS,
    "data_partitions": CREATE_DATA_PARTITIONS,
    "data_ingestion_jobs": CREATE_DATA_INGESTION_JOBS,
    "data_ingestion_job_events": CREATE_DATA_INGESTION_JOB_EVENTS,
    # ── Phase 13: commercial-grade additions ──────────────────────────
    "migration_versions": CREATE_MIGRATION_VERSIONS,
    "audit_log": CREATE_AUDIT_LOG,
    "api_keys": CREATE_API_KEYS,
    "data_quality_rules": CREATE_DATA_QUALITY_RULES,
    "data_quarantine": CREATE_DATA_QUARANTINE,
}

INDEX_DEFS: dict[str, str] = {
    "idx_kline_symbol_interval_time": 'CREATE INDEX IF NOT EXISTS idx_kline_symbol_interval_time ON kline_bars(symbol, interval, bar_time)',
    "idx_kline_trade_date": 'CREATE INDEX IF NOT EXISTS idx_kline_trade_date ON kline_bars(trade_date)',
    "idx_valuation_symbol_date": 'CREATE INDEX IF NOT EXISTS idx_valuation_symbol_date ON valuations(symbol, trade_date)',
    "idx_calendar_exchange_date": 'CREATE INDEX IF NOT EXISTS idx_calendar_exchange_date ON trading_calendar(exchange, trade_date)',
    "idx_status_symbol_date": 'CREATE INDEX IF NOT EXISTS idx_status_symbol_date ON security_status_history(symbol, effective_date)',
    "idx_industry_symbol_date": 'CREATE INDEX IF NOT EXISTS idx_industry_symbol_date ON industry_classification_history(symbol, effective_date)',
    "idx_suspend_symbol_date": 'CREATE INDEX IF NOT EXISTS idx_suspend_symbol_date ON suspension_events(symbol, start_date)',
    "idx_adjust_symbol_date": 'CREATE INDEX IF NOT EXISTS idx_adjust_symbol_date ON adjust_factors(symbol, trade_date, adjust)',
    "idx_corp_action_symbol_date": 'CREATE INDEX IF NOT EXISTS idx_corp_action_symbol_date ON corporate_actions(symbol, action_date)',
    "idx_orderbook_symbol_time": 'CREATE INDEX IF NOT EXISTS idx_orderbook_symbol_time ON order_book_snapshots(symbol, timestamp)',
    "idx_trade_tape_symbol_time": 'CREATE INDEX IF NOT EXISTS idx_trade_tape_symbol_time ON trade_tape(symbol, timestamp)',
    "idx_news_symbol_date": 'CREATE INDEX IF NOT EXISTS idx_news_symbol_date ON news_items(symbol, publish_date)',
    "idx_ann_symbol_date": 'CREATE INDEX IF NOT EXISTS idx_ann_symbol_date ON announcements(symbol, publish_date)',
    "idx_indicators_symbol_date": 'CREATE INDEX IF NOT EXISTS idx_indicators_symbol_date ON market_indicators(symbol, trade_date)',
    "idx_technical_indicator_lookup": 'CREATE INDEX IF NOT EXISTS idx_technical_indicator_lookup ON technical_indicators(symbol, interval, indicator, bar_time)',
    "idx_quality_dataset_symbol": 'CREATE INDEX IF NOT EXISTS idx_quality_dataset_symbol ON data_quality_checks(dataset, symbol, created_at)',
    "idx_snapshots_dataset_symbol": 'CREATE INDEX IF NOT EXISTS idx_snapshots_dataset_symbol ON data_snapshots(dataset, symbol, created_at)',
    "idx_partitions_dataset_key": 'CREATE INDEX IF NOT EXISTS idx_partitions_dataset_key ON data_partitions(dataset, partition_key, storage_tier)',
    "idx_ingestion_status": 'CREATE INDEX IF NOT EXISTS idx_ingestion_status ON data_ingestion_jobs(status, updated_at)',
    "idx_ingestion_events_job_time": 'CREATE INDEX IF NOT EXISTS idx_ingestion_events_job_time ON data_ingestion_job_events(job_id, event_time)',
    # ── Phase 13 indexes ──────────────────────────────────────────────
    "idx_migration_version_applied": 'CREATE INDEX IF NOT EXISTS idx_migration_version_applied ON migration_versions(version_id, applied_at)',
    "idx_audit_event_time": 'CREATE INDEX IF NOT EXISTS idx_audit_event_time ON audit_log(event_time)',
    "idx_audit_actor": 'CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor, event_time)',
    "idx_audit_resource": 'CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_log(resource_type, resource_id, event_time)',
    "idx_api_keys_active": 'CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active, expires_at)',
    "idx_quality_rules_active": 'CREATE INDEX IF NOT EXISTS idx_quality_rules_active ON data_quality_rules(is_active, scope_dataset)',
    "idx_quarantine_resolution": 'CREATE INDEX IF NOT EXISTS idx_quarantine_resolution ON data_quarantine(resolution, severity, created_at)',
}

# Column name remaps from provider payloads → DuckDB column names
# (dataframe column -> table column)
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
# AStockStore
# ---------------------------------------------------------------------------


class AStockStore:
    """DuckDB-backed local database for A-share data.

    Uses ``:memory:`` (testing) or a file path for persistence.
    All write operations are thread-safe via an internal ``threading.Lock``.

    Parameters
    ----------
    db_path : str
        Path to DuckDB file. Use ``':memory:'`` for in-memory (testing).
    """

    def __init__(self, db_path: str = "~/.tradingagents/astock/astock.duckdb") -> None:
        resolved = os.path.expanduser(db_path)
        self._db_path = resolved
        self._conn: duckdb.DuckDBPyConnection | None = None
        self._lock = threading.Lock()
        self._owns_conn = False

    # ---- connection management -------------------------------------------

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            self.connect()
        assert self._conn is not None
        return self._conn

    @property
    def db_path(self) -> str:
        return self._db_path

    def connect(self) -> None:
        """Open (or reuse) the DuckDB connection."""
        if self._conn is not None:
            return
        self._conn = duckdb.connect(self._db_path)
        self._owns_conn = True

    def close(self) -> None:
        """Close the DuckDB connection if owned."""
        if self._conn is not None and self._owns_conn:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = None
        self._owns_conn = False

    def __enter__(self) -> AStockStore:
        self.connect()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ---- schema ----------------------------------------------------------

    def init_schema(self) -> None:
        """Create the current production schema for a fresh database."""
        for ddl in ALL_TABLE_DEFS.values():
            self.conn.execute(ddl)
        self.create_indexes()
        self._seed_storage_profiles()

    def _table_columns(self, table_name: str) -> list[str]:
        if not self.table_exists(table_name):
            return []
        return [
            str(row[1])
            for row in self.conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        ]

    def create_indexes(self) -> None:
        """Create query-path indexes for the production schema."""
        for ddl in INDEX_DEFS.values():
            self.conn.execute(ddl)

    def _seed_storage_profiles(self) -> None:
        """Record the intended commercial storage topology."""
        self.insert_table_rows(
            "database_storage_profiles",
            [
                {
                    "profile_name": "duckdb_local_olap",
                    "role": "local_cache_olap",
                    "engine": "duckdb",
                    "read_write_model": "single-writer analytical cache",
                    "notes": "Use for local WebUI, research, backtest snapshots, and export/import. Not the high-concurrency production write store.",
                },
                {
                    "profile_name": "postgresql_production_oltp",
                    "role": "production_primary",
                    "engine": "postgresql",
                    "read_write_model": "multi-user transactional primary store",
                    "notes": "Recommended commercial primary database; TimescaleDB extension can be layered on time-series tables.",
                },
                {
                    "profile_name": "clickhouse_production_olap",
                    "role": "production_analytics",
                    "engine": "clickhouse",
                    "read_write_model": "append-oriented analytical replica",
                    "notes": "Recommended for high-volume historical market-data scans after ingestion from the primary store.",
                },
            ],
        )

    # ── migration engine --------------------------------------------------

    def migrate(self, *names: str) -> list[dict[str, Any]]:
        """Apply a named, versioned migration if it has not been run before.

        Each migration is a ``(name, description, sql_or_none, rollback_sql_or_none)``
        entry defined in ``_MIGRATIONS``. After the SQL is executed (if any), a
        row is inserted into ``migration_versions``.

        If *names* is empty, all un-applied migrations are run in order.
        Returns a list of ``{version_id, description, status, duration_ms}`` records.
        """
        if not self.table_exists("migration_versions"):
            self.conn.execute(CREATE_MIGRATION_VERSIONS)

        applied = {
            str(row[0])
            for row in self.conn.execute(
                "SELECT version_id FROM migration_versions"
            ).fetchall()
        }

        results: list[dict[str, Any]] = []
        candidates = list(self._MIGRATIONS)
        if names:
            candidates = [n for n in candidates if n in names]
            missing = set(names) - {n for n in candidates}
            if missing:
                msg = f"Unknown migration(s): {missing}. Known: {list(self._MIGRATIONS)}"
                raise ValueError(msg)

        for vid, desc, sql, rollback_sql in candidates:
            if vid in applied:
                continue
            import time as _time
            t0 = _time.time()
            status = "applied"
            duration_ms = 0
            try:
                if sql:
                    self.conn.execute(sql)
                elapsed = _time.time() - t0
                duration_ms = int(round(elapsed * 1000))
            except Exception as exc:
                status = "failed"
                elapsed = _time.time() - t0
                duration_ms = int(round(elapsed * 1000))
                msg = f"Migration {vid!r} failed: {exc}"
                self.conn.execute(
                    "INSERT INTO migration_versions (version_id, description, status, duration_ms, checksum) "
                    "VALUES (?, ?, ?, ?, ?)",
                    [vid, desc, status, duration_ms, repr(sql) if sql else ""],
                )
                raise RuntimeError(msg) from exc

            self.conn.execute(
                "INSERT INTO migration_versions (version_id, description, status, duration_ms, checksum, rollback_sql) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [vid, desc, status, duration_ms, repr(sql) if sql else "", rollback_sql],
            )
            results.append({
                "version_id": vid,
                "description": desc,
                "status": status,
                "duration_ms": duration_ms,
            })
        return results

    def list_migrations(self) -> pd.DataFrame:
        """Return all applied migration records."""
        return self.conn.execute(
            "SELECT * FROM migration_versions ORDER BY applied_at"
        ).fetchdf()

    def rollback_migration(self, version_id: str) -> None:
        """Roll back a previously applied migration if rollback_sql is set."""
        row = self.conn.execute(
            "SELECT rollback_sql FROM migration_versions WHERE version_id = ?",
            [version_id],
        ).fetchone()
        if row is None:
            raise ValueError(f"Migration {version_id!r} not found")
        if not row[0]:
            raise ValueError(f"Migration {version_id!r} has no rollback SQL defined")
        self.conn.execute(row[0])
        self.conn.execute("DELETE FROM migration_versions WHERE version_id = ?", [version_id])

    # Defined as class variable for discoverability — (version_id, description, sql, rollback_sql)
    _MIGRATIONS: list[tuple[str, str, str | None, str | None]] = []

    # ── schema ----------------------------------------------------------

    def schema_sql(self, target: str = "duckdb") -> str:
        """Return DDL for the current schema.

        ``duckdb`` is executable locally. ``postgresql`` is a production-primary
        starting point that preserves table names, keys, checks, and indexes.
        """
        target_normalized = str(target or "duckdb").lower()
        if target_normalized not in ("duckdb", "postgresql"):
            raise ValueError("target must be one of: duckdb, postgresql")
        statements = list(ALL_TABLE_DEFS.values()) + list(INDEX_DEFS.values())
        sql = ";\n\n".join(stmt.strip().rstrip(";") for stmt in statements) + ";\n"
        if target_normalized == "duckdb":
            return sql
        replacements = {
            "DOUBLE": "DOUBLE PRECISION",
            "VARCHAR": "TEXT",
            "CREATE INDEX IF NOT EXISTS": "CREATE INDEX IF NOT EXISTS",
        }
        for old, new in replacements.items():
            sql = sql.replace(old, new)
        return sql

    def drop_all_tables(self) -> None:
        """Drop all managed tables (for test teardown)."""
        for table_name in ALL_TABLE_DEFS:
            self.conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        result = self.conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
            [table_name],
        ).fetchone()
        return result is not None and result[0] > 0

    def list_symbols(self, table_name: str | None = None) -> list[str]:
        """Return known symbols from managed tables.

        If *table_name* is omitted, all managed tables with a ``symbol`` column
        are scanned and the result is de-duplicated.
        """
        tables = [table_name] if table_name else list(ALL_TABLE_DEFS)
        symbols: set[str] = set()
        for table in tables:
            if not table or table not in ALL_TABLE_DEFS or not self.table_exists(table):
                continue
            try:
                columns = {
                    str(row[1])
                    for row in self.conn.execute(f'PRAGMA table_info("{table}")').fetchall()
                }
                if "symbol" not in columns:
                    continue
                rows = self.conn.execute(
                    f'SELECT DISTINCT symbol FROM "{table}" WHERE symbol IS NOT NULL'
                ).fetchall()
                symbols.update(str(row[0]) for row in rows if row and row[0])
            except Exception:
                continue
        return sorted(symbols)

    # ── audit log ---------------------------------------------------------

    def store_audit_log(
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
        import uuid, json
        event_id = uuid.uuid4().hex
        self.conn.execute(
            "INSERT INTO audit_log "
            "(event_id, event_type, actor, actor_ip, resource_type, resource_id, "
            " action, detail_json, old_value_json, new_value_json, outcome) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                event_id,
                event_type,
                actor,
                actor_ip,
                resource_type,
                resource_id,
                action,
                json.dumps(detail, ensure_ascii=False) if detail else None,
                json.dumps(old_value, ensure_ascii=False) if old_value else None,
                json.dumps(new_value, ensure_ascii=False) if new_value else None,
                outcome,
            ],
        )
        return event_id

    def query_audit_log(
        self,
        *,
        actor: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> pd.DataFrame:
        """Search audit log with optional filters."""
        sql = "SELECT * FROM audit_log WHERE 1=1"
        params: list[Any] = []
        if actor:
            sql += " AND actor = ?"
            params.append(actor)
        if resource_type:
            sql += " AND resource_type = ?"
            params.append(resource_type)
        if resource_id:
            sql += " AND resource_id = ?"
            params.append(resource_id)
        if event_type:
            sql += " AND event_type = ?"
            params.append(event_type)
        sql += " ORDER BY event_time DESC LIMIT ?"
        params.append(limit)
        return self.conn.execute(sql, params).fetchdf()

    # ── API keys ----------------------------------------------------------

    def add_api_key(
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
        import uuid
        key_id = uuid.uuid4().hex
        self.conn.execute(
            "INSERT INTO api_keys (key_id, key_hash, key_prefix, label, role, owner, "
            "allowed_capabilities, rate_limit, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [key_id, key_hash, key_prefix, label, role, owner,
             allowed_capabilities, rate_limit, expires_at],
        )
        return key_id

    def revoke_api_key(self, key_id: str) -> None:
        """Soft-revoke an API key."""
        self.conn.execute(
            "UPDATE api_keys SET is_active = FALSE WHERE key_id = ?", [key_id]
        )

    def validate_api_key(self, key_hash: str) -> dict[str, Any] | None:
        """Check if a key hash is valid and active. Returns key record or None."""
        row = self.conn.execute(
            "SELECT key_id, role, allowed_capabilities, rate_limit, expires_at "
            "FROM api_keys WHERE key_hash = ? AND is_active = TRUE "
            "AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)",
            [key_hash],
        ).fetchone()
        if row is None:
            return None
        record = {
            "key_id": str(row[0]),
            "role": str(row[1]),
            "allowed_capabilities": str(row[2]) if row[2] else "",
            "rate_limit": int(row[3]) if row[3] else 100,
        }
        # Update last_used_at
        self.conn.execute(
            "UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE key_id = ?",
            [record["key_id"]],
        )
        return record

    # ── data quality rules ------------------------------------------------

    def store_quality_rule(
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
        import uuid
        rule_id = uuid.uuid4().hex
        self.conn.execute(
            "INSERT INTO data_quality_rules "
            "(rule_id, rule_name, description, scope_dataset, scope_interval, "
            " check_sql, severity, is_active, cooldown_minutes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [rule_id, rule_name, description, scope_dataset, scope_interval,
             check_sql, severity, is_active, cooldown_minutes],
        )
        return rule_id

    def run_quality_rule(
        self, rule_id: str, *, dry_run: bool = False
    ) -> dict[str, Any]:
        """Execute a single quality rule and store results.

        Returns ``{rule_id, status, matched, failed, details}``.
        """
        rule = self.conn.execute(
            "SELECT rule_name, check_sql, severity FROM data_quality_rules "
            "WHERE rule_id = ? AND is_active = TRUE",
            [rule_id],
        ).fetchone()
        if rule is None:
            raise ValueError(f"Quality rule {rule_id!r} not found or inactive")
        rule_name, check_sql, severity = str(rule[0]), str(rule[1] or ""), str(rule[2])
        if not check_sql:
            raise ValueError(f"Quality rule {rule_id!r} has no check_sql defined")

        try:
            result_df = self.conn.execute(check_sql).fetchdf()
            row_count = len(result_df)
            failed = int(result_df.iloc[0]["violations"]) if not result_df.empty and "violations" in result_df.columns else row_count
            status = "pass" if failed == 0 else severity
        except Exception as exc:
            result_df = pd.DataFrame()
            status = "error"
            failed = -1
            row_count = 0
            _ = exc  # suppress unused

        # quarantine bad rows if violations found and not dry_run
        quarantined = 0
        if not dry_run and failed > 0 and not result_df.empty:
            for _, row in result_df.iterrows():
                self.store_quarantine(
                    source_dataset=rule_name.split(":")[0] if ":" in rule_name else "unknown",
                    symbol=str(row.get("symbol", "")),
                    interval=str(row.get("interval", "")),
                    reason=f"Quality rule {rule_name} failed",
                    rule_id=rule_id,
                    original_values=row.to_dict(),
                    severity=severity,
                )
                quarantined += 1

        self.conn.execute(
            "UPDATE data_quality_rules SET last_run_at = CURRENT_TIMESTAMP, "
            "last_result = ?, failure_count = failure_count + ? "
            "WHERE rule_id = ?",
            [status, max(failed, 0), rule_id],
        )

        self.store_data_quality_check({
            "dataset": rule_name,
            "rule_version": rule_id,
            "status": status,
            "invalid_count": max(failed, 0),
            "details": {"rows_checked": row_count, "severity": severity},
        })

        return {"rule_id": rule_id, "status": status, "matched": row_count, "failed": failed, "quarantined": quarantined}

    def run_all_quality_rules(self) -> list[dict[str, Any]]:
        """Run all active quality rules and return results."""
        rules = self.conn.execute(
            "SELECT rule_id FROM data_quality_rules WHERE is_active = TRUE"
        ).fetchall()
        results = []
        for (rule_id,) in rules:
            try:
                results.append(self.run_quality_rule(rule_id))
            except Exception as exc:
                results.append({"rule_id": rule_id, "status": "error", "error": str(exc)})
        return results

    # ── data quarantine ---------------------------------------------------

    def store_quarantine(
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
        import uuid, json
        quarantine_id = uuid.uuid4().hex
        self.conn.execute(
            "INSERT INTO data_quarantine "
            "(quarantine_id, source_dataset, symbol, interval, bar_time, trade_date, "
            " reason, rule_id, original_values_json, severity) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                quarantine_id,
                source_dataset,
                symbol or None,
                interval or None,
                bar_time,
                trade_date,
                reason,
                rule_id,
                json.dumps(original_values, ensure_ascii=False) if original_values else "{}",
                severity,
            ],
        )
        return quarantine_id

    def resolve_quarantine(
        self, quarantine_id: str, *, resolved_by: str = "system"
    ) -> None:
        """Mark a quarantined record as resolved (data was fixed or reviewed)."""
        self.conn.execute(
            "UPDATE data_quarantine SET resolution = 'resolved', resolved_by = ?, "
            "resolved_at = CURRENT_TIMESTAMP WHERE quarantine_id = ?",
            [resolved_by, quarantine_id],
        )

    def query_quarantine(
        self, *, severity: str | None = None, resolution: str = "unresolved", limit: int = 100
    ) -> pd.DataFrame:
        sql = "SELECT * FROM data_quarantine WHERE resolution = ?"
        params: list[Any] = [resolution]
        if severity:
            sql += " AND severity = ?"
            params.append(severity)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return self.conn.execute(sql, params).fetchdf()

    # ---- helpers ---------------------------------------------------------

    @staticmethod
    def _df_from_rows(
        rows: pd.DataFrame | list[dict[str, Any]], column_map: dict[str, str]
    ) -> pd.DataFrame:
        """Normalise rows (DataFrame or list of dicts) into a DataFrame whose
        columns are the DuckDB column names (mapped via *column_map*)."""
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
        # Rename known columns
        rename = {}
        for src_col in df.columns:
            if src_col in column_map:
                rename[src_col] = column_map[src_col]
        if rename:
            df = df.rename(columns=rename)
        # Drop duplicate columns after rename (e.g. ``date`` + ``datetime`` both → ``bar_time``)
        df = df.loc[:, ~df.columns.duplicated()]
        # Keep only columns that exist in the column_map *values*
        target_cols = set(column_map.values())
        cols_to_keep = [c for c in df.columns if c in target_cols]
        df = df[cols_to_keep]
        return df

    @staticmethod
    def _canonicalise_dates(df: pd.DataFrame, date_cols: list[str]) -> pd.DataFrame:
        """Convert date-like columns to ``datetime.date``."""
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
        return df

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        """Return a safely quoted SQL identifier."""
        return '"' + str(identifier).replace('"', '""') + '"'

    @staticmethod
    def _normalise_interval(interval: str) -> str:
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
    def _normalise_kline_times(df: pd.DataFrame) -> pd.DataFrame:
        """Populate bar_time and trade_date for date/minute kline rows."""
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

    # ---- batch insert (INSERT OR REPLACE) --------------------------------

    def _insert_df(
        self, table: str, df: pd.DataFrame, column_map: dict[str, str]
    ) -> int:
        """Normalise *df* via ``column_map`` and execute INSERT OR REPLACE.

        Returns the number of rows affected.
        """
        if df.empty:
            return 0
        normalised = self._df_from_rows(df, column_map)
        if normalised.empty:
            return 0
        # Build explicit column list matching the DataFrame columns
        # This avoids positional-mismatch errors and skips auto-generated columns
        # like ``created_at`` (which has DEFAULT CURRENT_TIMESTAMP in the DDL).
        cols = ", ".join(f'"{c}"' for c in normalised.columns)
        with self._lock:
            self.conn.register("_tmp_df", normalised)
            row_count = self.conn.execute(
                f'INSERT OR REPLACE INTO "{table}" ({cols}) SELECT * FROM _tmp_df'
            ).fetchone()
            self.conn.unregister("_tmp_df")
        return (row_count[0] if row_count else 0) if row_count else 0

    def insert_table_rows(self, table_name: str, rows: pd.DataFrame | list[dict[str, Any]]) -> int:
        """Insert or replace rows into a managed table.

        This is the generic entry point used by manual data-entry APIs. Unknown
        columns are dropped; DuckDB constraints still enforce required primary
        keys and data types.
        """
        if table_name not in ALL_TABLE_DEFS:
            msg = f"Unknown table: {table_name}. Known: {list(ALL_TABLE_DEFS)}"
            raise ValueError(msg)
        if isinstance(rows, pd.DataFrame):
            df = rows.copy()
        else:
            df = pd.DataFrame(rows)
        if df.empty:
            return 0
        if table_name == "kline_bars":
            if "interval" in df.columns:
                df["interval"] = df["interval"].fillna("1d").map(self._normalise_interval)
            else:
                df["interval"] = "1d"
            if "adjust" not in df.columns:
                df["adjust"] = "none"
            if "quality" not in df.columns:
                df["quality"] = "normal"
            df = self._normalise_kline_times(df)
        columns = [
            str(row[1])
            for row in self.conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
            if str(row[1]) != "created_at"
        ]
        normalised = df[[column for column in df.columns if column in columns]].copy()
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
        for ts_col in ("timestamp", "bar_time", "start_time", "end_time", "created_at", "updated_at"):
            if ts_col in normalised.columns:
                normalised[ts_col] = pd.to_datetime(normalised[ts_col], errors="coerce")
        cols = ", ".join(f'"{c}"' for c in normalised.columns)
        with self._lock:
            self.conn.register("_tmp_manual_df", normalised)
            row_count = self.conn.execute(
                f'INSERT OR REPLACE INTO "{table_name}" ({cols}) SELECT * FROM _tmp_manual_df'
            ).fetchone()
            self.conn.unregister("_tmp_manual_df")
        return row_count[0] if row_count else 0

    # ---- kline -----------------------------------------------------------

    def insert_kline(
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
            df["interval"] = df["interval"].fillna(interval).map(self._normalise_interval)
        if "adjust" not in df.columns:
            df["adjust"] = "none"
        if "quality" not in df.columns:
            df["quality"] = "normal"
        if "source" not in df.columns:
            df["source"] = source
        df = self._normalise_kline_times(df)
        return self._insert_df("kline_bars", df, KLINE_COLUMN_MAP)

    def query_kline(
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
        inner = 'SELECT * FROM kline_bars WHERE symbol = ? AND "interval" = ?'
        params: list[Any] = [symbol, interval]
        if start:
            inner += " AND bar_time >= ?"
            params.append(start)
        if end:
            inner += " AND bar_time <= ?"
            params.append(end)

        if limit is not None and limit > 0:
            # Descending limit pushdown → outer re-sort
            inner += " ORDER BY bar_time DESC LIMIT ?"
            params.append(limit)
            sql = f"SELECT * FROM ({inner}) sub ORDER BY bar_time ASC"
        else:
            sql = inner + " ORDER BY bar_time"

        return self.conn.execute(sql, params).fetchdf()

    # ---- valuations ------------------------------------------------------

    def insert_valuations(
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
        return self._insert_df("valuations", df, VALUATION_COLUMN_MAP)

    def query_valuations(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        """Return valuations as a DataFrame, sorted by trade_date."""
        sql = "SELECT * FROM valuations WHERE symbol = ?"
        params: list[Any] = [symbol]
        if start:
            sql += " AND trade_date >= ?"
            params.append(start)
        if end:
            sql += " AND trade_date <= ?"
            params.append(end)
        sql += " ORDER BY trade_date"
        return self.conn.execute(sql, params).fetchdf()

    # ---- order book snapshots --------------------------------------------

    def insert_order_book_snapshot(
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
        return self._insert_df("order_book_snapshots", df, {
            "symbol": "symbol",
            "timestamp": "timestamp",
            "bid_price": "bid_price",
            "bid_volume": "bid_volume",
            "ask_price": "ask_price",
            "ask_volume": "ask_volume",
            "source": "source",
        })

    def query_order_book(
        self, symbol: str, start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        sql = "SELECT * FROM order_book_snapshots WHERE symbol = ?"
        params: list[Any] = [symbol]
        if start:
            sql += " AND timestamp >= ?"
            params.append(start)
        if end:
            sql += " AND timestamp <= ?"
            params.append(end)
        sql += " ORDER BY timestamp"
        return self.conn.execute(sql, params).fetchdf()

    # ---- trade tape ------------------------------------------------------

    def insert_trade_tape(self, symbol: str, df: pd.DataFrame, source: str = "") -> int:
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        if "source" not in df.columns:
            df["source"] = source
        return self._insert_df("trade_tape", df, {
            "symbol": "symbol",
            "timestamp": "timestamp",
            "price": "price",
            "volume": "volume",
            "direction": "direction",
            "source": "source",
        })

    def query_trade_tape(
        self, symbol: str, start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        sql = "SELECT * FROM trade_tape WHERE symbol = ?"
        params: list[Any] = [symbol]
        if start:
            sql += " AND timestamp >= ?"
            params.append(start)
        if end:
            sql += " AND timestamp <= ?"
            params.append(end)
        sql += " ORDER BY timestamp"
        return self.conn.execute(sql, params).fetchdf()

    # ---- research reports -------------------------------------------------

    def insert_research_reports(
        self, symbol: str, df: pd.DataFrame, source: str = ""
    ) -> int:
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        if "source" not in df.columns:
            df["source"] = source
        df = self._canonicalise_dates(df, ["report_date", "date"])
        return self._insert_df("research_reports", df, {
            "symbol": "symbol",
            "report_date": "report_date",
            "title": "title",
            "institution": "institution",
            "analyst": "analyst",
            "rating": "rating",
            "pdf_url": "pdf_url",
            "source": "source",
        })

    def query_research_reports(self, symbol: str) -> pd.DataFrame:
        return self.conn.execute(
            "SELECT * FROM research_reports WHERE symbol = ? ORDER BY report_date",
            [symbol],
        ).fetchdf()

    # ---- news items -------------------------------------------------------

    def insert_news_items(self, symbol: str, df: pd.DataFrame, source: str = "") -> int:
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        if "source" not in df.columns:
            df["source"] = source
        df = self._canonicalise_dates(df, ["publish_date", "date"])
        return self._insert_df("news_items", df, {
            "symbol": "symbol",
            "publish_date": "publish_date",
            "title": "title",
            "summary": "summary",
            "url": "url",
            "source": "source",
        })

    def query_news_items(self, symbol: str) -> pd.DataFrame:
        return self.conn.execute(
            "SELECT * FROM news_items WHERE symbol = ? ORDER BY publish_date",
            [symbol],
        ).fetchdf()

    # ---- announcements ----------------------------------------------------

    def insert_announcements(self, symbol: str, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        df = self._canonicalise_dates(df, ["publish_date", "date"])
        return self._insert_df("announcements", df, {
            "symbol": "symbol",
            "publish_date": "publish_date",
            "title": "title",
            "summary": "summary",
            "url": "url",
        })

    def query_announcements(self, symbol: str) -> pd.DataFrame:
        return self.conn.execute(
            "SELECT * FROM announcements WHERE symbol = ? ORDER BY publish_date DESC",
            [symbol],
        ).fetchdf()

    # ---- backtest results -------------------------------------------------

    def store_backtest_result(self, result: Any) -> int:
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
                                "fee_config_used",
                                "execution_signal",
                                "decision_scope",
                                "trades",
                                "data_assumption",
                                "benchmark_symbol",
                                "benchmark_return",
                                "benchmark_max_drawdown",
                                "alpha",
                                "beta",
                                "cost_breakdown",
                            )
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        )
        return self._insert_df(
            "backtest_results",
            df,
            {
                "run_id": "run_id",
                "symbol": "symbol",
                "strategy_name": "strategy_name",
                "start_date": "start_date",
                "end_date": "end_date",
                "total_return": "total_return",
                "annualized_return": "annualized_return",
                "sharpe_ratio": "sharpe_ratio",
                "max_drawdown": "max_drawdown",
                "win_rate": "win_rate",
                "total_trades": "total_trades",
                "params_json": "params_json",
            },
        )

    def get_backtest_results(
        self, strategy_name: str | None = None
    ) -> pd.DataFrame:
        if strategy_name:
            return self.conn.execute(
                "SELECT * FROM backtest_results WHERE strategy_name = ? ORDER BY created_at DESC",
                [strategy_name],
            ).fetchdf()
        return self.conn.execute(
            "SELECT * FROM backtest_results ORDER BY created_at DESC"
        ).fetchdf()

    def clear_backtest_results(self) -> int:
        """Delete all stored backtest results. Returns number of rows deleted."""
        result = self.conn.execute("DELETE FROM backtest_results")
        row = result.fetchone()
        return row[0] if row else 0

    def delete_backtest_result(self, run_id: str) -> int:
        """Delete a single backtest result by run_id. Returns 1 if deleted."""
        result = self.conn.execute(
            "DELETE FROM backtest_results WHERE run_id = ?", [run_id]
        )
        row = result.fetchone()
        return row[0] if row else 0

    # ---- paper trades -----------------------------------------------------

    def store_paper_trade(self, trade: dict[str, Any]) -> int:
        """Store a single paper trade record."""
        df = pd.DataFrame([trade])
        # fields expected: trade_id, symbol, direction, price, volume, fees,
        # trade_date, strategy_name, actionable, decision_scope
        if "trade_id" not in df.columns:
            df["trade_id"] = str(hash(str(trade)))
        if "actionable" not in df.columns:
            df["actionable"] = False
        if "decision_scope" not in df.columns:
            df["decision_scope"] = "paper_trading_only"
        df = self._canonicalise_dates(df, ["trade_date", "date"])
        return self._insert_df(
            "paper_trades",
            df,
            {
                "trade_id": "trade_id",
                "symbol": "symbol",
                "direction": "direction",
                "price": "price",
                "volume": "volume",
                "fees": "fees",
                "trade_date": "trade_date",
                "strategy_name": "strategy_name",
                "actionable": "actionable",
                "decision_scope": "decision_scope",
            },
        )

    def get_paper_trades(self, symbol: str | None = None) -> pd.DataFrame:
        if symbol:
            return self.conn.execute(
                "SELECT * FROM paper_trades WHERE symbol = ? ORDER BY trade_date",
                [symbol],
            ).fetchdf()
        return self.conn.execute(
            "SELECT * FROM paper_trades ORDER BY trade_date"
        ).fetchdf()

    # ---- market indicators ------------------------------------------------

    def insert_market_indicators(self, symbol: str, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        df = self._canonicalise_dates(df, ["trade_date", "date"])
        return self._insert_df(
            "market_indicators",
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
        )

    def query_market_indicators(
        self, symbol: str, start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        sql = "SELECT * FROM market_indicators WHERE symbol = ?"
        params: list[Any] = [symbol]
        if start:
            sql += " AND trade_date >= ?"
            params.append(start)
        if end:
            sql += " AND trade_date <= ?"
            params.append(end)
        sql += " ORDER BY trade_date"
        return self.conn.execute(sql, params).fetchdf()

    def insert_trading_calendar(self, rows: pd.DataFrame | list[dict[str, Any]]) -> int:
        """Insert exchange trading-calendar rows."""
        return self.insert_table_rows("trading_calendar", rows)

    def insert_security_status_history(self, rows: pd.DataFrame | list[dict[str, Any]]) -> int:
        """Insert symbol status/ST history rows."""
        return self.insert_table_rows("security_status_history", rows)

    def insert_adjust_factors(self, rows: pd.DataFrame | list[dict[str, Any]]) -> int:
        """Insert qfq/hfq adjustment factors."""
        return self.insert_table_rows("adjust_factors", rows)

    def query_adjust_factors(
        self,
        symbol: str,
        adjust: str = "qfq",
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        sql = "SELECT * FROM adjust_factors WHERE symbol = ? AND adjust = ?"
        params: list[Any] = [symbol, adjust]
        if start:
            sql += " AND trade_date >= ?"
            params.append(start)
        if end:
            sql += " AND trade_date <= ?"
            params.append(end)
        sql += " ORDER BY trade_date"
        return self.conn.execute(sql, params).fetchdf()

    def insert_technical_indicators(self, rows: pd.DataFrame | list[dict[str, Any]]) -> int:
        """Insert generic technical-indicator rows."""
        if isinstance(rows, pd.DataFrame):
            df = rows.copy()
        else:
            df = pd.DataFrame(rows)
        if df.empty:
            return 0
        df = self._normalise_kline_times(df)
        if "interval" in df.columns:
            df["interval"] = df["interval"].fillna("1d").map(self._normalise_interval)
        return self.insert_table_rows("technical_indicators", df)

    def query_technical_indicators(
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
            "WHERE symbol = ? AND indicator = ? AND interval = ?"
        )
        params: list[Any] = [symbol, indicator, interval]
        if start:
            sql += " AND bar_time >= ?"
            params.append(start)
        if end:
            sql += " AND bar_time <= ?"
            params.append(end)
        sql += " ORDER BY bar_time"
        return self.conn.execute(sql, params).fetchdf()

    # ---- metadata / maintenance ------------------------------------------

    def store_data_snapshot(self, snapshot: dict[str, Any]) -> int:
        """Store a dataset snapshot record for lineage and reproducibility."""
        data = dict(snapshot)
        if "snapshot_id" not in data:
            import uuid

            data["snapshot_id"] = uuid.uuid4().hex
        if "metadata_json" not in data and isinstance(data.get("metadata"), dict):
            data["metadata_json"] = json.dumps(data.pop("metadata"), ensure_ascii=False, sort_keys=True)
        return self.insert_table_rows("data_snapshots", [data])

    def store_data_quality_check(self, check: dict[str, Any]) -> int:
        """Store a data-quality check result for commercial data governance."""
        data = dict(check)
        if "check_id" not in data:
            import uuid

            data["check_id"] = uuid.uuid4().hex
        if "details_json" not in data and isinstance(data.get("details"), dict):
            data["details_json"] = json.dumps(data.pop("details"), ensure_ascii=False, sort_keys=True)
        if "fallback_path_json" not in data and isinstance(data.get("fallback_path"), list):
            data["fallback_path_json"] = json.dumps(data.pop("fallback_path"), ensure_ascii=False)
        return self.insert_table_rows("data_quality_checks", [data])

    def store_data_partition(self, partition: dict[str, Any]) -> int:
        """Store a logical data partition record for hot/cold maintenance."""
        data = dict(partition)
        if "partition_id" not in data:
            import uuid

            data["partition_id"] = uuid.uuid4().hex
        return self.insert_table_rows("data_partitions", [data])

    def store_ingestion_job(self, job: dict[str, Any]) -> int:
        """Store or update a database-level ingestion/import job record."""
        data = dict(job)
        if "job_id" not in data:
            import uuid

            data["job_id"] = uuid.uuid4().hex
        if "metadata_json" not in data and isinstance(data.get("metadata"), dict):
            data["metadata_json"] = json.dumps(data.pop("metadata"), ensure_ascii=False, sort_keys=True)
        return self.insert_table_rows("data_ingestion_jobs", [data])

    def store_ingestion_job_event(self, event: dict[str, Any]) -> int:
        """Append a durable ingestion-job progress event."""
        data = dict(event)
        if "event_id" not in data:
            import uuid

            data["event_id"] = uuid.uuid4().hex
        if "metadata_json" not in data and isinstance(data.get("metadata"), dict):
            data["metadata_json"] = json.dumps(data.pop("metadata"), ensure_ascii=False, sort_keys=True)
        return self.insert_table_rows("data_ingestion_job_events", [data])

    # ---- export / import (COPY TO / COPY FROM) ---------------------------

    EXPORT_FORMAT_MAP = {
        "csv": ("(FORMAT CSV, HEADER true)", ".csv"),
        "parquet": ("(FORMAT PARQUET)", ".parquet"),
        "json": ("(FORMAT JSON)", ".json"),
    }

    def export_table(
        self,
        table_name: str,
        fmt: str = "csv",
        output_path: str | None = None,
    ) -> str:
        """Export *table_name* to a file via DuckDB COPY TO.

        Parameters
        ----------
        table_name : str
            Table to export.
        fmt : str
            One of ``'csv'``, ``'parquet'``, ``'json'``.
        output_path : str | None
            Output file path. If None, auto-generated from table name + format.

        Returns
        -------
        str
            Path to the exported file.
        """
        if table_name not in ALL_TABLE_DEFS:
            msg = f"Unknown table: {table_name}. Known: {list(ALL_TABLE_DEFS)}"
            raise ValueError(msg)
        if fmt not in self.EXPORT_FORMAT_MAP:
            msg = f"Unsupported format: {fmt}. Supported: {list(self.EXPORT_FORMAT_MAP)}"
            raise ValueError(msg)

        opts, ext = self.EXPORT_FORMAT_MAP[fmt]
        if output_path is None:
            output_path = f"{table_name}{ext}"
        else:
            # ensure extension
            p = Path(output_path)
            if p.suffix != ext:
                p = p.with_suffix(ext)
            output_path = str(p)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn.execute(
            f'COPY (SELECT * FROM "{table_name}") TO ? {opts}',
            [output_path],
        )
        return output_path

    def import_table(
        self,
        table_name: str,
        fmt: str = "csv",
        file_path: str = "",
    ) -> int:
        """Import data from a file into *table_name* via DuckDB COPY FROM.

        Parameters
        ----------
        table_name : str
            Target table.
        fmt : str
            One of ``'csv'``, ``'parquet'``, ``'json'``.
        file_path : str
            Path to the source file.

        Returns
        -------
        int
            Number of rows imported.
        """
        if table_name not in ALL_TABLE_DEFS:
            msg = f"Unknown table: {table_name}. Known: {list(ALL_TABLE_DEFS)}"
            raise ValueError(msg)
        if fmt not in self.EXPORT_FORMAT_MAP:
            msg = f"Unsupported format: {fmt}. Supported: {list(self.EXPORT_FORMAT_MAP)}"
            raise ValueError(msg)

        opts, _ext = self.EXPORT_FORMAT_MAP[fmt]
        reader_fn = {
            "csv": "read_csv_auto",
            "parquet": "read_parquet",
            "json": "read_json_auto",
        }[fmt]
        df = self.conn.execute(f"SELECT * FROM {reader_fn}(?)", [file_path]).fetchdf()
        return self.insert_table_rows(table_name, df)

    def export_tables(
        self,
        table_names: list[str] | None = None,
        fmt: str = "csv",
        output_dir: str = ".",
    ) -> dict[str, str]:
        """Export multiple managed tables into *output_dir*."""
        names = table_names or list(ALL_TABLE_DEFS)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        exported: dict[str, str] = {}
        for table_name in names:
            if table_name not in ALL_TABLE_DEFS:
                msg = f"Unknown table: {table_name}. Known: {list(ALL_TABLE_DEFS)}"
                raise ValueError(msg)
            _, ext = self.EXPORT_FORMAT_MAP.get(fmt, ("", ""))
            output_path = str(Path(output_dir) / f"{table_name}{ext}")
            exported[table_name] = self.export_table(table_name, fmt=fmt, output_path=output_path)
        return exported

    def import_tables(
        self,
        table_files: dict[str, str],
        fmt: str = "csv",
    ) -> dict[str, int]:
        """Import multiple managed tables from ``{table_name: file_path}``."""
        imported: dict[str, int] = {}
        for table_name, file_path in table_files.items():
            imported[table_name] = self.import_table(table_name, fmt=fmt, file_path=file_path)
        return imported

    def import_from_database(
        self,
        *,
        source_db_path: str,
        source_table: str,
        target_table: str,
        source_type: str = "auto",
        symbol: str | None = None,
        start: str | None = None,
        end: str | None = None,
        symbol_column: str = "symbol",
        date_column: str = "trade_date",
    ) -> int:
        """Import rows from a DuckDB or SQLite database into a managed table."""
        if target_table not in ALL_TABLE_DEFS:
            msg = f"Unknown target table: {target_table}. Known: {list(ALL_TABLE_DEFS)}"
            raise ValueError(msg)
        path = os.path.expanduser(source_db_path)
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        inferred = Path(path).suffix.lower()
        db_type = source_type.lower()
        if db_type == "auto":
            db_type = "sqlite" if inferred in (".sqlite", ".sqlite3", ".db") else "duckdb"
        if db_type not in ("duckdb", "sqlite"):
            raise ValueError("source_type must be one of: auto, duckdb, sqlite")

        where_parts: list[str] = []
        params: list[Any] = []
        symbol_ident = self._quote_identifier(symbol_column)
        date_ident = self._quote_identifier(date_column)
        if symbol:
            where_parts.append(f"{symbol_ident} = ?")
            params.append(symbol)
        if start:
            where_parts.append(f"{date_ident} >= ?")
            params.append(start)
        if end:
            where_parts.append(f"{date_ident} <= ?")
            params.append(end)
        where_sql = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""
        sql = f"SELECT * FROM {self._quote_identifier(source_table)}{where_sql}"

        if db_type == "duckdb":
            source_conn = duckdb.connect(path, read_only=True)
            try:
                df = source_conn.execute(sql, params).fetchdf()
            finally:
                source_conn.close()
        else:
            with sqlite3.connect(path) as source_conn:
                df = pd.read_sql_query(sql, source_conn, params=params)
        return self.insert_table_rows(target_table, df)

    # ---- stats -----------------------------------------------------------

    def get_table_stats(self) -> dict[str, dict[str, Any]]:
        """Return per-table row counts and latest date info.

        Returns
        -------
        dict
            ``{table_name: {"rows": int, "latest_date": str or None}}``
        """
        stats: dict[str, dict[str, Any]] = {}
        for table_name in ALL_TABLE_DEFS:
            if not self.table_exists(table_name):
                stats[table_name] = {"rows": 0, "latest_date": None}
                continue
            row_result = self.conn.execute(
                f'SELECT count(*) FROM "{table_name}"'
            ).fetchone()
            row_count = row_result[0] if row_result else 0
            # Try to find the "latest date" column
            latest: Any = None
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
                    date_result = self.conn.execute(
                        f'SELECT max({date_col}) FROM "{table_name}"'
                    ).fetchone()
                    if date_result and date_result[0] is not None:
                        latest = str(date_result[0])
                        break
                except Exception:
                    continue
            stats[table_name] = {"rows": row_count, "latest_date": latest}
        return stats

    # ---- vacuum ----------------------------------------------------------

    def vacuum(self) -> None:
        """Reclaim storage by checkpointing and truncating WAL."""
        self.conn.execute("CHECKPOINT")
        self.conn.execute("ANALYZE")

    # ---- raw SQL query ---------------------------------------------------

    def query_sql(self, sql: str) -> pd.DataFrame:
        """Execute an arbitrary SQL query and return results as a DataFrame."""
        return self.conn.execute(sql).fetchdf()

    def list_tables(self) -> list[str]:
        """Return list of managed table names that exist."""
        existing = []
        for table_name in ALL_TABLE_DEFS:
            if self.table_exists(table_name):
                existing.append(table_name)
        return existing


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


def init_astock_db(db_path: str = "~/.tradingagents/astock/astock.duckdb") -> AStockStore:
    """Create an ``AStockStore``, call ``init_schema()``, and return it."""
    store = AStockStore(db_path)
    store.connect()
    store.init_schema()
    return store
