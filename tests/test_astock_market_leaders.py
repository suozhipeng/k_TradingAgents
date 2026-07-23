"""Tests for market leaders — limit-up ladders, volume leaders, new high/low."""

import duckdb
import pandas as pd

from tradingagents.astock.review.leaders import compute_leaders, persist_leaders


def _frame(n_stocks=20, days=60):
    dates = pd.date_range("2024-01-01", periods=days, freq="D")
    rows = []
    for i in range(n_stocks):
        for d in dates:
            base = 10 + (i % 5) * 2
            # Some stocks get a big jump (limit-up like)
            change = 10.5 if i < 3 and d == dates[-1] else (i % 7 - 3) * 0.5
            rows.append({"symbol": f"S{i:03d}", "trade_date": d.date(),
                         "open": base, "close": base + change, "amount": 1e6 + i * 1e5})
    return pd.DataFrame(rows)


def test_leaders_detects_limit_up():
    result = compute_leaders(_frame())
    assert result["data_state"] == "available"
    assert len(result["limit_up_stocks"]) >= 2  # at least 2 stocks got the big jump


def test_leaders_persists():
    conn = duckdb.connect(":memory:")
    result = compute_leaders(_frame())
    persist_leaders(conn, result)
    assert conn.execute("SELECT COUNT(*) FROM limit_up_daily").fetchone()[0] >= 2
    assert conn.execute("SELECT COUNT(*) FROM limit_up_ladders").fetchone()[0] >= 0
    assert conn.execute("SELECT COUNT(*) FROM market_leaders_daily").fetchone()[0] >= 2


def test_leaders_empty_frame():
    result = compute_leaders(pd.DataFrame())
    assert result["data_state"] == "unavailable"


def test_leaders_missing_columns():
    result = compute_leaders(pd.DataFrame({"a": [1]}))
    assert result["data_state"] == "unavailable"
