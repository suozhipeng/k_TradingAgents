"""
ClickHouse schema for AStock Pro — commercial OLAP replica.

High-volume historical market data scans. MergeTree engine with monthly
partitioning.  All tables use ``MergeTree()`` for single-node deployments;
standalone deployments can drop the ``/clickhouse/tables/{shard}/`` prefix
and use plain ``MergeTree`` instead.

TTL policy: 5-year rolling window on trade_date.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Partition & TTL strategy
# ---------------------------------------------------------------------------

CH_PARTITION_STRATEGY: dict[str, str] = {
    "kline_bars": "toYYYYMM(trade_date)",
    "valuations": "toYYYYMM(trade_date)",
    "order_book_snapshots": "toYYYYMM(timestamp)",
    "trade_tape": "toYYYYMM(timestamp)",
    "market_indicators": "toYYYYMM(trade_date)",
    "technical_indicators": "toYYYYMM(trade_date)",
    "adjust_factors": "toYYYYMM(trade_date)",
    "security_status_history": "toYYYYMM(effective_date)",
    "industry_classification_history": "toYYYYMM(effective_date)",
    "suspension_events": "toYYYYMM(start_date)",
    "corporate_actions": "toYYYYMM(action_date)",
    "data_quality_checks": "toYYYYMM(created_at)",
}

CH_TTL_POLICY: dict[str, str] = {
    "kline_bars": "trade_date + INTERVAL 5 YEAR",
    "valuations": "trade_date + INTERVAL 5 YEAR",
    "order_book_snapshots": "timestamp + INTERVAL 2 YEAR",
    "trade_tape": "timestamp + INTERVAL 2 YEAR",
    "market_indicators": "trade_date + INTERVAL 5 YEAR",
    "technical_indicators": "trade_date + INTERVAL 3 YEAR",
    "adjust_factors": "trade_date + INTERVAL 10 YEAR",
    "security_status_history": "effective_date + INTERVAL 10 YEAR",
    "industry_classification_history": "effective_date + INTERVAL 10 YEAR",
    "suspension_events": "start_date + INTERVAL 10 YEAR",
    "corporate_actions": "action_date + INTERVAL 10 YEAR",
    "data_quality_checks": "created_at + INTERVAL 3 YEAR",
}

# ---------------------------------------------------------------------------
# Common engine tail
# ---------------------------------------------------------------------------
_CH_ENGINE_TAIL = (
    "ENGINE = MergeTree()"
)
_CH_SETTINGS = (
    "SETTINGS index_granularity = 8192, min_rows_for_wide_part = 0"
)

# ---------------------------------------------------------------------------
# DDL: kline_bars_ch
# ---------------------------------------------------------------------------

CREATE_KLINE_BARS_CH = """
CREATE TABLE IF NOT EXISTS astock.kline_bars_ch (
    symbol String,
    bar_time DateTime,
    trade_date Date,
    open Float64,
    high Float64,
    low Float64,
    close Float64,
    volume Float64,
    amount Float64,
    turnover_rate Nullable(Float64),
    interval String DEFAULT '1d',
    adjust String DEFAULT 'none',
    quality String DEFAULT 'normal',
    source String,
    ingestion_time DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(trade_date)
ORDER BY (symbol, interval, bar_time)
TTL trade_date + INTERVAL 5 YEAR DELETE
SETTINGS index_granularity = 8192, min_rows_for_wide_part = 0
"""

# ---------------------------------------------------------------------------
# DDL: valuations_ch
# ---------------------------------------------------------------------------

CREATE_VALUATIONS_CH = """
CREATE TABLE IF NOT EXISTS astock.valuations_ch (
    symbol String,
    trade_date Date,
    pe Nullable(Float64),
    pb Nullable(Float64),
    market_cap Nullable(Float64),
    source String,
    ingestion_time DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(trade_date)
ORDER BY (symbol, trade_date)
TTL trade_date + INTERVAL 5 YEAR DELETE
SETTINGS index_granularity = 8192, min_rows_for_wide_part = 0
"""

# ---------------------------------------------------------------------------
# DDL: order_book_snapshots_ch
# ---------------------------------------------------------------------------

CREATE_ORDER_BOOK_CH = """
CREATE TABLE IF NOT EXISTS astock.order_book_snapshots_ch (
    symbol String,
    timestamp DateTime,
    bid_price Float64,
    bid_volume Float64,
    ask_price Float64,
    ask_volume Float64,
    source String,
    ingestion_time DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (symbol, timestamp)
TTL timestamp + INTERVAL 2 YEAR DELETE
SETTINGS index_granularity = 8192, min_rows_for_wide_part = 0
"""

# ---------------------------------------------------------------------------
# DDL: trade_tape_ch
# ---------------------------------------------------------------------------

CREATE_TRADE_TAPE_CH = """
CREATE TABLE IF NOT EXISTS astock.trade_tape_ch (
    symbol String,
    timestamp DateTime,
    price Float64,
    volume Float64,
    direction String,
    source String,
    ingestion_time DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (symbol, timestamp)
TTL timestamp + INTERVAL 2 YEAR DELETE
SETTINGS index_granularity = 8192, min_rows_for_wide_part = 0
"""

# ---------------------------------------------------------------------------
# DDL: market_indicators_ch
# ---------------------------------------------------------------------------

CREATE_MARKET_INDICATORS_CH = """
CREATE TABLE IF NOT EXISTS astock.market_indicators_ch (
    symbol String,
    trade_date Date,
    ma_5 Nullable(Float64),
    ma_20 Nullable(Float64),
    ma_60 Nullable(Float64),
    rsi_14 Nullable(Float64),
    atr_14 Nullable(Float64),
    volume_ma_5 Nullable(Float64),
    ingestion_time DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(trade_date)
ORDER BY (symbol, trade_date)
TTL trade_date + INTERVAL 5 YEAR DELETE
SETTINGS index_granularity = 8192, min_rows_for_wide_part = 0
"""

# ---------------------------------------------------------------------------
# DDL: technical_indicators_ch
# ---------------------------------------------------------------------------

CREATE_TECHNICAL_INDICATORS_CH = """
CREATE TABLE IF NOT EXISTS astock.technical_indicators_ch (
    symbol String,
    bar_time DateTime,
    trade_date Date,
    interval String,
    indicator String,
    params_hash String,
    params_json Nullable(String),
    value_json String,
    source_snapshot_id Nullable(String),
    ingestion_time DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(trade_date)
ORDER BY (symbol, interval, indicator, bar_time)
TTL trade_date + INTERVAL 3 YEAR DELETE
SETTINGS index_granularity = 8192, min_rows_for_wide_part = 0
"""

# ---------------------------------------------------------------------------
# DDL: adjust_factors_ch
# ---------------------------------------------------------------------------

CREATE_ADJUST_FACTORS_CH = """
CREATE TABLE IF NOT EXISTS astock.adjust_factors_ch (
    symbol String,
    trade_date Date,
    adjust String,
    factor Float64,
    source String,
    ingestion_time DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(trade_date)
ORDER BY (symbol, trade_date, adjust)
TTL trade_date + INTERVAL 10 YEAR DELETE
SETTINGS index_granularity = 8192, min_rows_for_wide_part = 0
"""

# ---------------------------------------------------------------------------
# DDL: security_status_history_ch
# ---------------------------------------------------------------------------

CREATE_SECURITY_STATUS_HISTORY_CH = """
CREATE TABLE IF NOT EXISTS astock.security_status_history_ch (
    symbol String,
    effective_date Date,
    status String,
    is_st UInt8 DEFAULT 0,
    reason Nullable(String),
    source String,
    ingestion_time DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(effective_date)
ORDER BY (symbol, effective_date)
TTL effective_date + INTERVAL 10 YEAR DELETE
SETTINGS index_granularity = 8192, min_rows_for_wide_part = 0
"""

# ---------------------------------------------------------------------------
# DDL: industry_classification_history_ch
# ---------------------------------------------------------------------------

CREATE_INDUSTRY_CLASSIFICATION_HISTORY_CH = """
CREATE TABLE IF NOT EXISTS astock.industry_classification_history_ch (
    symbol String,
    effective_date Date,
    classification String,
    level Int32 DEFAULT 1,
    industry_code Nullable(String),
    industry_name Nullable(String),
    source String,
    ingestion_time DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(effective_date)
ORDER BY (symbol, effective_date, classification, level)
TTL effective_date + INTERVAL 10 YEAR DELETE
SETTINGS index_granularity = 8192, min_rows_for_wide_part = 0
"""

# ---------------------------------------------------------------------------
# DDL: suspension_events_ch
# ---------------------------------------------------------------------------

CREATE_SUSPENSION_EVENTS_CH = """
CREATE TABLE IF NOT EXISTS astock.suspension_events_ch (
    symbol String,
    start_date Date,
    end_date Nullable(Date),
    reason Nullable(String),
    source String,
    ingestion_time DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(start_date)
ORDER BY (symbol, start_date)
TTL start_date + INTERVAL 10 YEAR DELETE
SETTINGS index_granularity = 8192, min_rows_for_wide_part = 0
"""

# ---------------------------------------------------------------------------
# DDL: corporate_actions_ch
# ---------------------------------------------------------------------------

CREATE_CORPORATE_ACTIONS_CH = """
CREATE TABLE IF NOT EXISTS astock.corporate_actions_ch (
    action_id String,
    symbol String,
    action_date Date,
    ex_date Nullable(Date),
    action_type String,
    cash_dividend Nullable(Float64),
    stock_dividend_ratio Nullable(Float64),
    split_ratio Nullable(Float64),
    rights_issue_price Nullable(Float64),
    raw_json Nullable(String),
    source String,
    ingestion_time DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(action_date)
ORDER BY (action_id)
TTL action_date + INTERVAL 10 YEAR DELETE
SETTINGS index_granularity = 8192, min_rows_for_wide_part = 0
"""

# ---------------------------------------------------------------------------
# DDL: data_quality_checks_ch
# ---------------------------------------------------------------------------

CREATE_DATA_QUALITY_CHECKS_CH = """
CREATE TABLE IF NOT EXISTS astock.data_quality_checks_ch (
    check_id String,
    dataset String,
    symbol Nullable(String),
    interval Nullable(String),
    start_time Nullable(DateTime),
    end_time Nullable(DateTime),
    rule_version Nullable(String),
    status String,
    missing_count Int64 DEFAULT 0,
    invalid_count Int64 DEFAULT 0,
    duplicate_count Int64 DEFAULT 0,
    fallback_path_json Nullable(String),
    details_json Nullable(String),
    ingestion_time DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(ingestion_time)
ORDER BY (dataset, check_id, ingestion_time)
TTL ingestion_time + INTERVAL 3 YEAR DELETE
SETTINGS index_granularity = 8192, min_rows_for_wide_part = 0
"""

# ---------------------------------------------------------------------------
# All DDL statements mapped by table name
# ---------------------------------------------------------------------------

ALL_CH_TABLE_DEFS: dict[str, str] = {
    "kline_bars_ch": CREATE_KLINE_BARS_CH,
    "valuations_ch": CREATE_VALUATIONS_CH,
    "order_book_snapshots_ch": CREATE_ORDER_BOOK_CH,
    "trade_tape_ch": CREATE_TRADE_TAPE_CH,
    "market_indicators_ch": CREATE_MARKET_INDICATORS_CH,
    "technical_indicators_ch": CREATE_TECHNICAL_INDICATORS_CH,
    "adjust_factors_ch": CREATE_ADJUST_FACTORS_CH,
    "security_status_history_ch": CREATE_SECURITY_STATUS_HISTORY_CH,
    "industry_classification_history_ch": CREATE_INDUSTRY_CLASSIFICATION_HISTORY_CH,
    "suspension_events_ch": CREATE_SUSPENSION_EVENTS_CH,
    "corporate_actions_ch": CREATE_CORPORATE_ACTIONS_CH,
    "data_quality_checks_ch": CREATE_DATA_QUALITY_CHECKS_CH,
}

# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def pg_to_ch_schema() -> str:
    """Return all ClickHouse DDL statements as one concatenated string."""
    parts: list[str] = []
    for name, ddl in ALL_CH_TABLE_DEFS.items():
        parts.append(f"-- Table: {name}")
        parts.append(ddl.strip())
        parts.append("")
    return "\n".join(parts)


def export_ch_sql(output_path: Optional[str] = None) -> str:
    """Write all CH DDL to a file, or return as string.

    Parameters
    ----------
    output_path : str, optional
        If provided, write the DDL to this file path.

    Returns
    -------
    str
        The full DDL string.
    """
    schema = pg_to_ch_schema()
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(schema, encoding="utf-8")
    return schema
