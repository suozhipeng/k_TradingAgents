"""Unified schema definitions for AStock Pro.

This module is the **single source of truth** for all table definitions,
column mappings, and index definitions.  Both the DuckDB layer
(``schema.py``) and the PostgreSQL layer (``pg_store.py``) import from
here so that DDL, ORM models, and indexes stay in sync.

Each table is described as a ``TableDef`` dataclass containing:
- ``name``          – table name
- ``columns``       – ordered list of ``ColumnDef``
- ``primary_key``   – list of PK column names
- ``checks``        – CHECK constraints (DuckDB-specific)
- ``indexes``       – list of index DDL fragments

The helper functions ``generate_ddl()`` and ``generate_index_ddl()``
produce executable SQL for a given target dialect.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Column definition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ColumnDef:
    """Describes a single table column."""

    name: str
    type_duckdb: str
    type_postgresql: str
    nullable: bool = True
    default: str | None = None
    check: str | None = None


# ---------------------------------------------------------------------------
# Table definition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TableDef:
    """Describes a single table."""

    name: str
    columns: list[ColumnDef] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)
    indexes: list[str] = field(default_factory=list)

    def create_ddl(self, dialect: str = "duckdb") -> str:
        """Generate CREATE TABLE DDL for the given dialect."""
        type_map = {"duckdb": "type_duckdb", "postgresql": "type_postgresql"}
        key = type_map.get(dialect, "type_duckdb")

        col_defs = []
        for col in self.columns:
            parts = [f'    "{col.name}" {getattr(col, key)}']
            if not col.nullable:
                parts.append("NOT NULL")
            if col.default is not None:
                parts.append(f"DEFAULT {col.default}")
            col_defs.append(" ".join(parts))

        if self.primary_key:
            pk_cols = ', '.join(f'"{c}"' for c in self.primary_key)
            col_defs.append(f"    PRIMARY KEY ({pk_cols})")

        # Add CHECK constraints
        all_checks = list(self.checks)
        for col in self.columns:
            if col.check:
                all_checks.append(f"    CHECK ({col.check})")
        if all_checks:
            col_defs.extend(all_checks)

        body = ",\n".join(col_defs)
        return f'CREATE TABLE IF NOT EXISTS "{self.name}" (\n{body}\n)'

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]


# ---------------------------------------------------------------------------
# Core table definitions
# ---------------------------------------------------------------------------

TABLE_DEFS: dict[str, TableDef] = {}


def _register(table: TableDef) -> TableDef:
    TABLE_DEFS[table.name] = table
    return table


# --- kline_bars ---
_register(TableDef(
    name="kline_bars",
    columns=[
        ColumnDef("symbol", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("bar_time", "TIMESTAMP", "TIMESTAMP", nullable=False),
        ColumnDef("trade_date", "DATE", "DATE", nullable=False),
        ColumnDef("open", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("high", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("low", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("close", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("volume", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("amount", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("turnover_rate", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("interval", "VARCHAR", "TEXT", nullable=True, default="'1d'"),
        ColumnDef("adjust", "VARCHAR", "TEXT", nullable=True, default="'none'"),
        ColumnDef("quality", "VARCHAR", "TEXT", nullable=True, default="'normal'"),
        ColumnDef("source", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("created_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
        ColumnDef("updated_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["symbol", "bar_time", "interval", "adjust"],
    checks=[
        'CHECK (interval IN (\'1m\', \'5m\', \'15m\', \'30m\', \'60m\', \'1d\', \'1w\', \'1mo\', \'1y\'))',
        "CHECK (open IS NULL OR open >= 0)",
        "CHECK (high IS NULL OR high >= 0)",
        "CHECK (low IS NULL OR low >= 0)",
        "CHECK (close IS NULL OR close >= 0)",
        "CHECK (high IS NULL OR low IS NULL OR high >= low)",
        "CHECK (volume IS NULL OR volume >= 0)",
        "CHECK (amount IS NULL OR amount >= 0)",
    ],
))

# --- security_master ---
_register(TableDef(
    name="security_master",
    columns=[
        ColumnDef("symbol", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("raw_symbol", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("name", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("exchange", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("board", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("currency", "VARCHAR", "TEXT", nullable=True, default="'CNY'"),
        ColumnDef("list_date", "DATE", "DATE", nullable=True),
        ColumnDef("delist_date", "DATE", "DATE", nullable=True),
        ColumnDef("status", "VARCHAR", "TEXT", nullable=True, default="'active'"),
        ColumnDef("is_st", "BOOLEAN", "BOOLEAN", nullable=True, default="FALSE"),
        ColumnDef("source", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("created_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
        ColumnDef("updated_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["symbol"],
))

# --- trading_calendar ---
_register(TableDef(
    name="trading_calendar",
    columns=[
        ColumnDef("exchange", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("trade_date", "DATE", "DATE", nullable=False),
        ColumnDef("is_open", "BOOLEAN", "BOOLEAN", nullable=False),
        ColumnDef("session_open", "TIMESTAMP", "TIMESTAMP", nullable=True),
        ColumnDef("session_close", "TIMESTAMP", "TIMESTAMP", nullable=True),
        ColumnDef("session_break_json", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("source", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("created_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
        ColumnDef("updated_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["exchange", "trade_date"],
))

# --- valuations ---
_register(TableDef(
    name="valuations",
    columns=[
        ColumnDef("symbol", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("trade_date", "DATE", "DATE", nullable=True),
        ColumnDef("pe", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("pb", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("market_cap", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("source", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("created_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["symbol", "trade_date"],
))

# --- adjust_factors ---
_register(TableDef(
    name="adjust_factors",
    columns=[
        ColumnDef("symbol", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("trade_date", "DATE", "DATE", nullable=False),
        ColumnDef("adjust", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("factor", "DOUBLE", "DOUBLE PRECISION", nullable=False),
        ColumnDef("source", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("created_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["symbol", "trade_date", "adjust"],
    checks=["CHECK (adjust IN ('none', 'qfq', 'hfq'))", "CHECK (factor > 0)"],
))

# --- corporate_actions ---
_register(TableDef(
    name="corporate_actions",
    columns=[
        ColumnDef("action_id", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("symbol", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("action_date", "DATE", "DATE", nullable=False),
        ColumnDef("ex_date", "DATE", "DATE", nullable=True),
        ColumnDef("action_type", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("cash_dividend", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("stock_dividend_ratio", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("split_ratio", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("rights_issue_price", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("raw_json", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("source", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("created_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["action_id"],
))

# --- order_book_snapshots ---
_register(TableDef(
    name="order_book_snapshots",
    columns=[
        ColumnDef("symbol", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("timestamp", "TIMESTAMP", "TIMESTAMP", nullable=True),
        ColumnDef("bid_price", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("bid_volume", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("ask_price", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("ask_volume", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("source", "VARCHAR", "TEXT", nullable=True),
    ],
    primary_key=["symbol", "timestamp"],
))

# --- trade_tape ---
_register(TableDef(
    name="trade_tape",
    columns=[
        ColumnDef("symbol", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("timestamp", "TIMESTAMP", "TIMESTAMP", nullable=True),
        ColumnDef("price", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("volume", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("direction", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("source", "VARCHAR", "TEXT", nullable=True),
    ],
    primary_key=["symbol", "timestamp"],
))

# --- technical_indicators ---
_register(TableDef(
    name="technical_indicators",
    columns=[
        ColumnDef("symbol", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("bar_time", "TIMESTAMP", "TIMESTAMP", nullable=False),
        ColumnDef("trade_date", "DATE", "DATE", nullable=True),
        ColumnDef("interval", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("indicator", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("params_hash", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("params_json", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("value_json", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("source_snapshot_id", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("created_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["symbol", "bar_time", "interval", "indicator", "params_hash"],
    checks=["CHECK (interval IN ('1m', '5m', '15m', '30m', '60m', '1d', '1w', '1mo', '1y'))"],
))

# --- market_indicators ---
_register(TableDef(
    name="market_indicators",
    columns=[
        ColumnDef("symbol", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("trade_date", "DATE", "DATE", nullable=True),
        ColumnDef("ma_5", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("ma_20", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("ma_60", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("rsi_14", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("atr_14", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("volume_ma_5", "DOUBLE", "DOUBLE PRECISION", nullable=True),
    ],
    primary_key=["symbol", "trade_date"],
))

# --- security_status_history ---
_register(TableDef(
    name="security_status_history",
    columns=[
        ColumnDef("symbol", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("effective_date", "DATE", "DATE", nullable=False),
        ColumnDef("status", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("is_st", "BOOLEAN", "BOOLEAN", nullable=True, default="FALSE"),
        ColumnDef("reason", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("source", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("created_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["symbol", "effective_date"],
))

# --- industry_classification_history ---
_register(TableDef(
    name="industry_classification_history",
    columns=[
        ColumnDef("symbol", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("effective_date", "DATE", "DATE", nullable=False),
        ColumnDef("classification", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("industry_code", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("industry_name", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("level", "INTEGER", "INTEGER", nullable=True, default="1"),
        ColumnDef("source", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("created_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["symbol", "effective_date", "classification", "level"],
))

# --- suspension_events ---
_register(TableDef(
    name="suspension_events",
    columns=[
        ColumnDef("symbol", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("start_date", "DATE", "DATE", nullable=False),
        ColumnDef("end_date", "DATE", "DATE", nullable=True),
        ColumnDef("reason", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("source", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("created_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["symbol", "start_date"],
))

# --- price_limit_rules ---
_register(TableDef(
    name="price_limit_rules",
    columns=[
        ColumnDef("rule_id", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("exchange", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("board", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("effective_date", "DATE", "DATE", nullable=False),
        ColumnDef("end_date", "DATE", "DATE", nullable=True),
        ColumnDef("up_limit_pct", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("down_limit_pct", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("source", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("created_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["rule_id"],
))

# --- research_reports ---
_register(TableDef(
    name="research_reports",
    columns=[
        ColumnDef("symbol", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("report_date", "DATE", "DATE", nullable=True),
        ColumnDef("title", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("institution", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("analyst", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("rating", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("pdf_url", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("source", "VARCHAR", "TEXT", nullable=True),
    ],
    primary_key=["symbol", "report_date", "title"],
))

# --- news_items ---
_register(TableDef(
    name="news_items",
    columns=[
        ColumnDef("symbol", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("publish_date", "DATE", "DATE", nullable=True),
        ColumnDef("title", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("summary", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("url", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("source", "VARCHAR", "TEXT", nullable=True),
    ],
    primary_key=["symbol", "publish_date", "url"],
))

# --- announcements ---
_register(TableDef(
    name="announcements",
    columns=[
        ColumnDef("symbol", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("publish_date", "DATE", "DATE", nullable=True),
        ColumnDef("title", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("summary", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("url", "VARCHAR", "TEXT", nullable=True),
    ],
    primary_key=["symbol", "publish_date", "url"],
))

# --- backtest_results ---
_register(TableDef(
    name="backtest_results",
    columns=[
        ColumnDef("run_id", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("symbol", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("strategy_name", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("start_date", "DATE", "DATE", nullable=True),
        ColumnDef("end_date", "DATE", "DATE", nullable=True),
        ColumnDef("total_return", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("annualized_return", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("sharpe_ratio", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("max_drawdown", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("win_rate", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("total_trades", "INTEGER", "INTEGER", nullable=True),
        ColumnDef("params_json", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("created_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["run_id"],
))

# --- paper_trades ---
_register(TableDef(
    name="paper_trades",
    columns=[
        ColumnDef("trade_id", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("symbol", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("direction", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("price", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("volume", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("fees", "DOUBLE", "DOUBLE PRECISION", nullable=True),
        ColumnDef("trade_date", "DATE", "DATE", nullable=True),
        ColumnDef("strategy_name", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("actionable", "BOOLEAN", "BOOLEAN", nullable=True, default="FALSE"),
        ColumnDef("decision_scope", "VARCHAR", "TEXT", nullable=True, default="'paper_trading_only'"),
        ColumnDef("created_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["trade_id"],
))

# --- database_storage_profiles ---
_register(TableDef(
    name="database_storage_profiles",
    columns=[
        ColumnDef("profile_name", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("role", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("engine", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("read_write_model", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("notes", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("created_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["profile_name"],
))

# --- data_sources ---
_register(TableDef(
    name="data_sources",
    columns=[
        ColumnDef("source_id", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("provider", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("category", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("priority", "INTEGER", "INTEGER", nullable=True, default="100"),
        ColumnDef("license_status", "VARCHAR", "TEXT", nullable=True, default="'unknown'"),
        ColumnDef("rate_limit_json", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("auth_required", "BOOLEAN", "BOOLEAN", nullable=True, default="FALSE"),
        ColumnDef("enabled", "BOOLEAN", "BOOLEAN", nullable=True, default="TRUE"),
        ColumnDef("notes", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("created_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
        ColumnDef("updated_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["source_id"],
))

# --- data_quality_checks ---
_register(TableDef(
    name="data_quality_checks",
    columns=[
        ColumnDef("check_id", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("dataset", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("symbol", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("interval", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("start_time", "TIMESTAMP", "TIMESTAMP", nullable=True),
        ColumnDef("end_time", "TIMESTAMP", "TIMESTAMP", nullable=True),
        ColumnDef("rule_version", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("status", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("missing_count", "BIGINT", "BIGINT", nullable=True, default="0"),
        ColumnDef("invalid_count", "BIGINT", "BIGINT", nullable=True, default="0"),
        ColumnDef("duplicate_count", "BIGINT", "BIGINT", nullable=True, default="0"),
        ColumnDef("fallback_path_json", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("details_json", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("created_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["check_id"],
))

# --- data_snapshots ---
_register(TableDef(
    name="data_snapshots",
    columns=[
        ColumnDef("snapshot_id", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("dataset", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("symbol", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("interval", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("start_time", "TIMESTAMP", "TIMESTAMP", nullable=True),
        ColumnDef("end_time", "TIMESTAMP", "TIMESTAMP", nullable=True),
        ColumnDef("row_count", "BIGINT", "BIGINT", nullable=True, default="0"),
        ColumnDef("source", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("quality", "VARCHAR", "TEXT", nullable=True, default="'normal'"),
        ColumnDef("metadata_json", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("created_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["snapshot_id"],
))

# --- data_partitions ---
_register(TableDef(
    name="data_partitions",
    columns=[
        ColumnDef("partition_id", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("dataset", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("symbol", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("interval", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("partition_key", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("start_time", "TIMESTAMP", "TIMESTAMP", nullable=True),
        ColumnDef("end_time", "TIMESTAMP", "TIMESTAMP", nullable=True),
        ColumnDef("storage_tier", "VARCHAR", "TEXT", nullable=True, default="'hot'"),
        ColumnDef("uri", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("row_count", "BIGINT", "BIGINT", nullable=True, default="0"),
        ColumnDef("status", "VARCHAR", "TEXT", nullable=True, default="'active'"),
        ColumnDef("created_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
        ColumnDef("updated_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["partition_id"],
))

# --- data_ingestion_jobs ---
_register(TableDef(
    name="data_ingestion_jobs",
    columns=[
        ColumnDef("job_id", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("job_type", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("status", "VARCHAR", "TEXT", nullable=True, default="'queued'"),
        ColumnDef("target_table", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("source_uri", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("total_rows", "BIGINT", "BIGINT", nullable=True, default="0"),
        ColumnDef("processed_rows", "BIGINT", "BIGINT", nullable=True, default="0"),
        ColumnDef("error_message", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("metadata_json", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("created_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
        ColumnDef("updated_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["job_id"],
))

# --- data_ingestion_job_events ---
_register(TableDef(
    name="data_ingestion_job_events",
    columns=[
        ColumnDef("event_id", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("job_id", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("event_time", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
        ColumnDef("status", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("processed_rows", "BIGINT", "BIGINT", nullable=True, default="0"),
        ColumnDef("message", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("error_message", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("metadata_json", "VARCHAR", "TEXT", nullable=True),
    ],
    primary_key=["event_id"],
))

# --- migration_versions ---
_register(TableDef(
    name="migration_versions",
    columns=[
        ColumnDef("version_id", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("description", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("applied_by", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("applied_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
        ColumnDef("checksum", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("duration_ms", "BIGINT", "BIGINT", nullable=True, default="0"),
        ColumnDef("status", "VARCHAR", "TEXT", nullable=True, default="'applied'"),
        ColumnDef("rollback_sql", "VARCHAR", "TEXT", nullable=True),
    ],
    primary_key=["version_id"],
))

# --- audit_log ---
_register(TableDef(
    name="audit_log",
    columns=[
        ColumnDef("event_id", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("event_type", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("actor", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("actor_ip", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("resource_type", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("resource_id", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("action", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("detail_json", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("old_value_json", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("new_value_json", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("outcome", "VARCHAR", "TEXT", nullable=True, default="'success'"),
        ColumnDef("event_time", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["event_id"],
))

# --- api_keys ---
_register(TableDef(
    name="api_keys",
    columns=[
        ColumnDef("key_id", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("key_hash", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("key_prefix", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("label", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("role", "VARCHAR", "TEXT", nullable=True, default="'readonly'"),
        ColumnDef("owner", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("allowed_capabilities", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("rate_limit", "INTEGER", "INTEGER", nullable=True, default="100"),
        ColumnDef("expires_at", "TIMESTAMP", "TIMESTAMP", nullable=True),
        ColumnDef("is_active", "BOOLEAN", "BOOLEAN", nullable=True, default="TRUE"),
        ColumnDef("last_used_at", "TIMESTAMP", "TIMESTAMP", nullable=True),
        ColumnDef("created_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["key_id"],
))

# --- data_quality_rules ---
_register(TableDef(
    name="data_quality_rules",
    columns=[
        ColumnDef("rule_id", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("rule_name", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("description", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("scope_dataset", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("scope_interval", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("check_sql", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("severity", "VARCHAR", "TEXT", nullable=True, default="'warn'"),
        ColumnDef("is_active", "BOOLEAN", "BOOLEAN", nullable=True, default="TRUE"),
        ColumnDef("cooldown_minutes", "INTEGER", "INTEGER", nullable=True, default="0"),
        ColumnDef("last_run_at", "TIMESTAMP", "TIMESTAMP", nullable=True),
        ColumnDef("last_result", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("failure_count", "INTEGER", "INTEGER", nullable=True, default="0"),
        ColumnDef("created_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
        ColumnDef("updated_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["rule_id"],
))

# --- data_quarantine ---
_register(TableDef(
    name="data_quarantine",
    columns=[
        ColumnDef("quarantine_id", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("source_dataset", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("symbol", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("interval", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("bar_time", "TIMESTAMP", "TIMESTAMP", nullable=True),
        ColumnDef("trade_date", "DATE", "DATE", nullable=True),
        ColumnDef("reason", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("rule_id", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("original_values_json", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("severity", "VARCHAR", "TEXT", nullable=True, default="'warn'"),
        ColumnDef("resolution", "VARCHAR", "TEXT", nullable=True, default="'unresolved'"),
        ColumnDef("resolved_by", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("resolved_at", "TIMESTAMP", "TIMESTAMP", nullable=True),
        ColumnDef("created_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["quarantine_id"],
))

# --- notification_channels ---
_register(TableDef(
    name="notification_channels",
    columns=[
        ColumnDef("name", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("kind", "VARCHAR", "TEXT", nullable=False, default="'generic'"),
        ColumnDef("url", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("enabled", "BOOLEAN", "BOOLEAN", nullable=True, default="TRUE"),
        ColumnDef("config_json", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("created_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
        ColumnDef("updated_at", "TIMESTAMP", "TIMESTAMP", nullable=True, default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["name"],
))

# --- watchlist ---
_register(TableDef(
    name="watchlist",
    columns=[
        ColumnDef("symbol", "VARCHAR", "TEXT", nullable=False),
        ColumnDef("name", "VARCHAR", "TEXT", nullable=True),
        ColumnDef("added_at", "TIMESTAMP", "TIMESTAMP", nullable=True),
        ColumnDef("source", "VARCHAR", "TEXT", nullable=True, default="'manual'"),
    ],
    primary_key=["symbol"],
))

# ---------------------------------------------------------------------------
# Index definitions (derived from TABLE_DEFS + explicit definitions)
# ---------------------------------------------------------------------------

DEFAULT_INDEX_DEFS: dict[str, str] = {
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
    "idx_migration_version_applied": 'CREATE INDEX IF NOT EXISTS idx_migration_version_applied ON migration_versions(version_id, applied_at)',
    "idx_audit_event_time": 'CREATE INDEX IF NOT EXISTS idx_audit_event_time ON audit_log(event_time)',
    "idx_audit_actor": 'CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor, event_time)',
    "idx_audit_resource": 'CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_log(resource_type, resource_id, event_time)',
    "idx_api_keys_active": 'CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active, expires_at)',
    "idx_quality_rules_active": 'CREATE INDEX IF NOT EXISTS idx_quality_rules_active ON data_quality_rules(is_active, scope_dataset)',
    "idx_quarantine_resolution": 'CREATE INDEX IF NOT EXISTS idx_quarantine_resolution ON data_quarantine(resolution, severity, created_at)',
}

# Supported kline intervals — shared constant
SUPPORTED_KLINE_INTERVALS = frozenset(("1m", "5m", "15m", "30m", "60m", "1d", "1w", "1mo", "1y"))
