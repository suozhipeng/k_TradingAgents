"""DuckDB DDL for market review, analysis and backtest tables (V1.5)."""

from __future__ import annotations


def ensure_review_tables(conn) -> None:
    """Create all V1.5-required review, analysis and backtest tables if missing."""
    cur = conn.cursor()

    # -- Market Review Runs (top-level run) --
    cur.execute("""CREATE TABLE IF NOT EXISTS market_review_runs (
        run_id VARCHAR PRIMARY KEY,
        review_date DATE NOT NULL,
        source_table VARCHAR,
        index_count INTEGER,
        sector_count INTEGER,
        breadth_available BOOLEAN DEFAULT FALSE,
        sentiment_available BOOLEAN DEFAULT FALSE,
        sector_available BOOLEAN DEFAULT FALSE,
        result_json VARCHAR,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS market_review_snapshots (
        run_id VARCHAR NOT NULL,
        snapshot_type VARCHAR NOT NULL,  -- 'breadth' | 'sentiment' | 'sector' | 'leaders'
        snapshot_json VARCHAR NOT NULL,
        data_state VARCHAR DEFAULT 'available',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # -- Index Daily --
    cur.execute("""CREATE TABLE IF NOT EXISTS market_index_daily (
        trade_date DATE NOT NULL,
        symbol VARCHAR NOT NULL,
        name VARCHAR,
        open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE,
        change_pct DOUBLE,
        volume DOUBLE, amount DOUBLE,
        ma5 DOUBLE, ma20 DOUBLE,
        data_state VARCHAR DEFAULT 'available',
        PRIMARY KEY (trade_date, symbol)
    )""")

    # -- Market Breadth Daily --
    cur.execute("""CREATE TABLE IF NOT EXISTS market_breadth_daily (
        trade_date DATE PRIMARY KEY,
        advancing INTEGER, declining INTEGER, unchanged INTEGER,
        advance_ratio DOUBLE,
        gain_ge_5pct INTEGER, loss_le_5pct INTEGER,
        new_high INTEGER, new_low INTEGER,
        median_change_pct DOUBLE,
        total_traded INTEGER,
        data_state VARCHAR DEFAULT 'available'
    )""")

    # -- Market Sentiment Daily --
    cur.execute("""CREATE TABLE IF NOT EXISTS market_sentiment_daily (
        trade_date DATE PRIMARY KEY,
        limit_up INTEGER, limit_down INTEGER,
        first_board INTEGER, second_board INTEGER, third_plus_board INTEGER,
        max_ladder_height INTEGER,
        gap_up_count INTEGER, gap_up_rate DOUBLE,
        yesterday_limit_up_avg_pct DOUBLE,
        yesterday_ladder_avg_pct DOUBLE,
        profit_score DOUBLE, loss_score DOUBLE,
        cycle_phase VARCHAR,  -- 'ice'|'repair'|'start'|'ferment'|'climax'|'divergence'|'ebb'
        cycle_version VARCHAR,
        data_state VARCHAR DEFAULT 'available'
    )""")

    # -- Sector Performance Daily --
    cur.execute("""CREATE TABLE IF NOT EXISTS sector_performance_daily (
        trade_date DATE NOT NULL,
        sector_name VARCHAR NOT NULL,
        sector_type VARCHAR,  -- 'industry' | 'concept'
        change_pct DOUBLE,
        amount DOUBLE,
        capital_inflow DOUBLE, capital_outflow DOUBLE,
        limit_up_count INTEGER,
        strength_score DOUBLE,
        continuity INTEGER,
        rotation_direction VARCHAR,
        PRIMARY KEY (trade_date, sector_name)
    )""")

    # -- Limit-up/down --
    cur.execute("""CREATE TABLE IF NOT EXISTS limit_up_daily (
        trade_date DATE NOT NULL,
        symbol VARCHAR NOT NULL,
        name VARCHAR,
        ladder_height INTEGER,
        board_type VARCHAR,  -- 'first' | 'second' | 'third_plus'
        sector VARCHAR,
        open_limit BOOLEAN,
        gap_up_pct DOUBLE,
        turnover_rate DOUBLE,
        data_state VARCHAR DEFAULT 'available',
        PRIMARY KEY (trade_date, symbol)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS limit_down_daily (
        trade_date DATE NOT NULL,
        symbol VARCHAR NOT NULL,
        name VARCHAR,
        consecutive_days INTEGER,
        sector VARCHAR,
        open_limit BOOLEAN,
        turnover_rate DOUBLE,
        data_state VARCHAR DEFAULT 'available',
        PRIMARY KEY (trade_date, symbol)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS limit_up_ladders (
        trade_date DATE NOT NULL,
        symbol VARCHAR NOT NULL,
        ladder_height INTEGER NOT NULL,
        sector VARCHAR,
        first_date DATE,
        data_state VARCHAR DEFAULT 'available',
        PRIMARY KEY (trade_date, symbol)
    )""")

    # -- Leaders --
    cur.execute("""CREATE TABLE IF NOT EXISTS market_leaders_daily (
        trade_date DATE NOT NULL,
        symbol VARCHAR NOT NULL,
        leader_type VARCHAR,  -- 'volume'|'turnover'|'gain'|'new_high'|'gap_up'
        rank INTEGER,
        change_pct DOUBLE,
        amount DOUBLE,
        turnover_rate DOUBLE,
        sector VARCHAR,
        data_state VARCHAR DEFAULT 'available',
        PRIMARY KEY (trade_date, symbol, leader_type)
    )""")

    # -- Stock Analysis --
    cur.execute("""CREATE TABLE IF NOT EXISTS stock_analysis_runs (
        run_id VARCHAR PRIMARY KEY,
        symbol VARCHAR NOT NULL,
        trade_date DATE,
        dimension_mask VARCHAR,
        dimensions_available VARCHAR,
        llm_interpretation BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    # stock_analysis_facts — already created by StockFactsEngine; ensure here too
    cur.execute("""CREATE TABLE IF NOT EXISTS stock_analysis_facts (
        run_id VARCHAR NOT NULL,
        symbol VARCHAR NOT NULL,
        fact_id VARCHAR,
        dimension VARCHAR,
        metric VARCHAR,
        value DOUBLE,
        unit VARCHAR,
        as_of TIMESTAMP,
        source VARCHAR,
        quality_tag VARCHAR,
        calculation_version VARCHAR,
        data_hash VARCHAR,
        PRIMARY KEY (run_id, symbol, fact_id)
    )""")
    # stock_risk_signals — already created by StockFactsEngine; ensure here too
    cur.execute("""CREATE TABLE IF NOT EXISTS stock_risk_signals (
        run_id VARCHAR NOT NULL,
        symbol VARCHAR NOT NULL,
        signal_type VARCHAR,
        severity VARCHAR,
        description VARCHAR,
        PRIMARY KEY (run_id, symbol, signal_type)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS stock_analysis_reports (
        run_id VARCHAR NOT NULL,
        dimension VARCHAR NOT NULL,
        report_json VARCHAR NOT NULL,
        llm_interpretation BOOLEAN DEFAULT FALSE,
        based_on_fact_ids VARCHAR,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    # stock_risk_signals already created by StockFactsEngine

    # -- Technical Indicator Snapshots --
    cur.execute("""CREATE TABLE IF NOT EXISTS technical_indicator_snapshots (
        symbol VARCHAR NOT NULL,
        trade_date DATE NOT NULL,
        ma5 DOUBLE, ma10 DOUBLE, ma20 DOUBLE, ma60 DOUBLE,
        macd_line DOUBLE, signal_line DOUBLE, macd_histogram DOUBLE,
        rsi_14 DOUBLE,
        k DOUBLE, d DOUBLE, j DOUBLE,
        boll_upper DOUBLE, boll_mid DOUBLE, boll_lower DOUBLE,
        atr_14 DOUBLE,
        support_price DOUBLE, resistance_price DOUBLE,
        trend_direction VARCHAR,
        breakout_status VARCHAR,
        data_state VARCHAR DEFAULT 'available',
        PRIMARY KEY (symbol, trade_date)
    )""")
    # backtest tables — ensure canonical definition here
    cur.execute("""CREATE TABLE IF NOT EXISTS backtest_runs (
        run_id VARCHAR PRIMARY KEY, symbol VARCHAR, strategy_version VARCHAR,
        source_table VARCHAR, data_start DATE, data_end DATE,
        initial_cash DOUBLE, final_value DOUBLE, return_rate DOUBLE,
        result_json VARCHAR, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS backtest_trades (
        run_id VARCHAR, trade_date DATE, side VARCHAR, price DOUBLE,
        shares INTEGER, fee DOUBLE, forced_exit BOOLEAN DEFAULT FALSE
    )""")

    # -- Data Quality and Ingestion --
    cur.execute("""CREATE TABLE IF NOT EXISTS data_quality_results (
        check_id VARCHAR PRIMARY KEY,
        table_name VARCHAR NOT NULL,
        check_type VARCHAR NOT NULL,
        passed BOOLEAN,
        detail_json VARCHAR,
        checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS data_quarantine (
        row_id VARCHAR PRIMARY KEY,
        table_name VARCHAR NOT NULL,
        symbol VARCHAR,
        trade_date DATE,
        reason VARCHAR,
        raw_data_json VARCHAR,
        quarantined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS ingestion_runs (
        run_id VARCHAR PRIMARY KEY,
        provider VARCHAR,
        table_name VARCHAR,
        symbol VARCHAR,
        rows_inserted INTEGER,
        rows_updated INTEGER,
        rows_quarantined INTEGER,
        status VARCHAR,
        started_at TIMESTAMP,
        finished_at TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS ingestion_run_items (
        run_id VARCHAR NOT NULL,
        item_type VARCHAR NOT NULL,
        item_id VARCHAR,
        detail_json VARCHAR
    )""")

    # V1.6 Provider tables
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS provider_health_snapshots (
        snapshot_id VARCHAR PRIMARY KEY,
        provider VARCHAR NOT NULL,
        capability VARCHAR NOT NULL,
        state VARCHAR NOT NULL,
        checked_at TIMESTAMP,
        latency_ms INTEGER,
        permission_hint VARCHAR,
        error_code VARCHAR,
        detail_rows INTEGER
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS provider_capability_status (
        provider VARCHAR NOT NULL,
        capability VARCHAR NOT NULL,
        state VARCHAR NOT NULL,
        checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (provider, capability)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS provider_request_audit (
        audit_id VARCHAR PRIMARY KEY,
        provider VARCHAR NOT NULL,
        api_name VARCHAR,
        capability VARCHAR,
        requested_at TIMESTAMP,
        latency_ms INTEGER,
        row_count INTEGER,
        state VARCHAR,
        error_code VARCHAR,
        request_params_hash VARCHAR
    )""")
    # provider_field_lineage created by provider_lineage.record_field_lineage
    conn.commit()
