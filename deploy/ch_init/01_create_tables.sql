-- Create database if not exists
CREATE DATABASE IF NOT EXISTS astock;

-- K-line bars (main OLAP table)
CREATE TABLE IF NOT EXISTS astock.kline_bars_ch
(
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
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(trade_date)
ORDER BY (symbol, interval, bar_time)
TTL trade_date + INTERVAL 5 YEAR DELETE
SETTINGS index_granularity = 8192;

-- Valuations
CREATE TABLE IF NOT EXISTS astock.valuations_ch
(
    symbol String,
    trade_date Date,
    pe Nullable(Float64),
    pb Nullable(Float64),
    market_cap Nullable(Float64),
    source String,
    ingestion_time DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(trade_date)
ORDER BY (symbol, trade_date)
TTL trade_date + INTERVAL 3 YEAR DELETE;

-- Order book snapshots
CREATE TABLE IF NOT EXISTS astock.order_book_snapshots_ch
(
    symbol String,
    timestamp DateTime,
    bid_price Float64,
    bid_volume Float64,
    ask_price Float64,
    ask_volume Float64,
    source String,
    ingestion_time DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (symbol, timestamp)
TTL timestamp + INTERVAL 3 MONTH DELETE;

-- Trade tape (tick data, short retention)
CREATE TABLE IF NOT EXISTS astock.trade_tape_ch
(
    symbol String,
    timestamp DateTime,
    price Float64,
    volume Float64,
    direction String,
    source String,
    ingestion_time DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (symbol, timestamp)
TTL timestamp + INTERVAL 1 MONTH DELETE;

-- Market indicators
CREATE TABLE IF NOT EXISTS astock.market_indicators_ch
(
    symbol String,
    trade_date Date,
    ma_5 Float64,
    ma_20 Float64,
    ma_60 Float64,
    rsi_14 Float64,
    atr_14 Float64,
    volume_ma_5 Float64,
    ingestion_time DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(trade_date)
ORDER BY (symbol, trade_date)
TTL trade_date + INTERVAL 2 YEAR DELETE;

-- Technical indicators
CREATE TABLE IF NOT EXISTS astock.technical_indicators_ch
(
    symbol String,
    bar_time DateTime,
    trade_date Date,
    interval String,
    indicator String,
    value_json String,
    ingestion_time DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(trade_date)
ORDER BY (symbol, interval, indicator, bar_time)
TTL trade_date + INTERVAL 1 YEAR DELETE;

-- Adjust factors
CREATE TABLE IF NOT EXISTS astock.adjust_factors_ch
(
    symbol String,
    trade_date Date,
    adjust String,
    factor Float64,
    source String,
    ingestion_time DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(trade_date)
ORDER BY (symbol, trade_date, adjust)
TTL trade_date + INTERVAL 10 YEAR DELETE;

-- Security status history
CREATE TABLE IF NOT EXISTS astock.security_status_history_ch
(
    symbol String,
    effective_date Date,
    status String,
    is_st UInt8 DEFAULT 0,
    reason Nullable(String),
    source String,
    ingestion_time DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(effective_date)
ORDER BY (symbol, effective_date)
TTL effective_date + INTERVAL 10 YEAR DELETE;

-- Industry classification history
CREATE TABLE IF NOT EXISTS astock.industry_classification_history_ch
(
    symbol String,
    effective_date Date,
    classification String,
    level Int32 DEFAULT 1,
    industry_code Nullable(String),
    industry_name Nullable(String),
    source String,
    ingestion_time DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(effective_date)
ORDER BY (symbol, effective_date, classification, level)
TTL effective_date + INTERVAL 10 YEAR DELETE;

-- Suspension events
CREATE TABLE IF NOT EXISTS astock.suspension_events_ch
(
    symbol String,
    start_date Date,
    end_date Nullable(Date),
    reason Nullable(String),
    source String,
    ingestion_time DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(start_date)
ORDER BY (symbol, start_date)
TTL start_date + INTERVAL 10 YEAR DELETE;

-- Corporate actions
CREATE TABLE IF NOT EXISTS astock.corporate_actions_ch
(
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
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(action_date)
ORDER BY (action_id)
TTL action_date + INTERVAL 10 YEAR DELETE;

-- Data quality checks
CREATE TABLE IF NOT EXISTS astock.data_quality_checks_ch
(
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
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(ingestion_time)
ORDER BY (dataset, check_id, ingestion_time)
TTL ingestion_time + INTERVAL 3 YEAR DELETE
SETTINGS index_granularity = 8192;
