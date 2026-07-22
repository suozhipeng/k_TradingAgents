"""Tests for V1.5 review schema table creation."""

import duckdb

from tradingagents.astock.review.schema import ensure_review_tables


REQUIRED_TABLES = [
    "market_review_runs",
    "market_review_snapshots",
    "market_index_daily",
    "market_breadth_daily",
    "market_sentiment_daily",
    "sector_performance_daily",
    "limit_up_daily",
    "limit_down_daily",
    "limit_up_ladders",
    "market_leaders_daily",
    "stock_analysis_runs",
    "stock_analysis_facts",
    "stock_analysis_reports",
    "stock_risk_signals",
    "technical_indicator_snapshots",
    "backtest_runs",
    "backtest_trades",
    "data_quality_results",
    "data_quarantine",
    "ingestion_runs",
    "ingestion_run_items",
]


def test_all_v15_tables_created():
    conn = duckdb.connect(":memory:")
    ensure_review_tables(conn)
    existing = set(row[0] for row in conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall())
    for tbl in REQUIRED_TABLES:
        assert tbl in existing, f"missing table: {tbl}"


def test_tables_idempotent():
    conn = duckdb.connect(":memory:")
    ensure_review_tables(conn)
    ensure_review_tables(conn)
    existing = set(row[0] for row in conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall())
    for tbl in REQUIRED_TABLES:
        assert tbl in existing


def test_tables_have_expected_columns():
    conn = duckdb.connect(":memory:")
    ensure_review_tables(conn)
    cols = set(conn.execute("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema='main'").fetchall())
    assert ("market_breadth_daily", "advancing") in cols
    assert ("market_sentiment_daily", "cycle_phase") in cols
    assert ("market_review_runs", "run_id") in cols
    assert ("sector_performance_daily", "rotation_direction") in cols
