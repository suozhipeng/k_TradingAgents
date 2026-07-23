"""Tests for sector rotation and strength analysis."""

import duckdb
import pandas as pd

from tradingagents.astock.review.sector import compute_sectors, persist_sectors


def _frame():
    dates = pd.date_range("2024-01-15", periods=1, freq="D")
    rows = []
    for i in range(30):
        for d in dates:
            rows.append({"symbol": f"S{i:03d}", "trade_date": d.date(), "open": 10 + i * 0.1, "close": 10 + i * 0.1 + (i % 5 - 2) * 0.3})
    return pd.DataFrame(rows)


def test_sector_returns_partial_without_map():
    result = compute_sectors(_frame())
    assert result["data_state"] == "partial"
    assert result["market_strength"] != 0


def test_sector_missing_columns():
    result = compute_sectors(pd.DataFrame({"a": [1]}))
    assert result["data_state"] == "unavailable"


def test_sector_empty_frame():
    result = compute_sectors(pd.DataFrame())
    assert result["data_state"] == "unavailable"


def test_sector_persists():
    conn = duckdb.connect(":memory:")
    result = compute_sectors(_frame())
    persist_sectors(conn, result)
    assert conn.execute("SELECT COUNT(*) FROM sector_performance_daily").fetchone()[0] == 0  # no sector map → no rows
