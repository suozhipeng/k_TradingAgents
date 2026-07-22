"""Tests for market breadth and sentiment calculators."""

import duckdb
import pandas as pd

from tradingagents.astock.review.breadth import compute_breadth, persist_breadth
from tradingagents.astock.review.sentiment import compute_sentiment, persist_sentiment


def _market_frame(n_stocks=20, days=40):
    dates = pd.date_range("2024-01-01", periods=days, freq="D")
    rows = []
    for i in range(n_stocks):
        for d in dates:
            base = 10 + (i % 5) * 2
            change = (i % 7 - 3) * 0.5
            rows.append({"symbol": f"STOCK{i:03d}", "trade_date": d.date(), "open": base, "close": base + change})
    return pd.DataFrame(rows)


def test_breadth_advancing_declining():
    result = compute_breadth(_market_frame())
    assert result["data_state"] == "available"
    assert result["advancing"] + result["declining"] + result["unchanged"] > 0
    assert result["gain_ge_5pct"] >= 0
    assert result["loss_le_5pct"] >= 0


def test_breadth_empty_frame():
    result = compute_breadth(pd.DataFrame())
    assert result["data_state"] == "unavailable"


def test_breadth_missing_columns():
    result = compute_breadth(pd.DataFrame({"symbol": ["A"]}))
    assert result["data_state"] == "unavailable"


def test_breadth_persists():
    conn = duckdb.connect(":memory:")
    persist_breadth(conn, compute_breadth(_market_frame()))
    assert conn.execute("SELECT COUNT(*) FROM market_breadth_daily").fetchone()[0] == 1
    persist_breadth(conn, compute_breadth(_market_frame()))
    assert conn.execute("SELECT COUNT(*) FROM market_breadth_daily").fetchone()[0] == 1  # idempotent


def test_sentiment_state_machine_all_phases():
    """Cover all 7 states: ice, ebb, divergence, repair, start, ferment, climax."""
    tests = [
        {"limit_up": 5, "limit_down": 20, "advance_ratio": 0.15, "profit": -35, "expected": "ice"},
        {"limit_up": 10, "limit_down": 12, "advance_ratio": 0.30, "profit": -20, "expected": "ebb"},
        {"limit_up": 10, "limit_down": 8, "advance_ratio": 0.25, "profit": -25, "expected": "divergence"},
        {"limit_up": 12, "limit_down": 6, "advance_ratio": 0.38, "profit": -12, "expected": "repair"},
        {"limit_up": 18, "limit_down": 8, "advance_ratio": 0.45, "profit": -5, "expected": "start"},
        {"limit_up": 25, "limit_down": 5, "advance_ratio": 0.55, "profit": 5, "expected": "ferment"},
        {"limit_up": 40, "limit_down": 3, "advance_ratio": 0.65, "profit": 15, "expected": "climax"},
    ]
    for tc in tests:
        b = {"data_state": "available", "trade_date": "2024-01-15", "advance_ratio": tc["advance_ratio"]}
        s = compute_sentiment(b, limit_up_count=tc["limit_up"], limit_down_count=tc["limit_down"])
        assert s["cycle_phase"] == tc["expected"], f"expected {tc['expected']} got {s['cycle_phase']} for {tc}"
        assert s["cycle_version"] == "v1.0"


def test_sentiment_unavailable_when_breadth_unavailable():
    b = {"data_state": "unavailable", "reason": "no data"}
    s = compute_sentiment(b)
    assert s["data_state"] == "unavailable"


def test_sentiment_persists():
    conn = duckdb.connect(":memory:")
    b = {"data_state": "available", "trade_date": "2024-01-15", "advance_ratio": 0.55}
    s = compute_sentiment(b, limit_up_count=30, limit_down_count=5)
    persist_sentiment(conn, s)
    assert conn.execute("SELECT COUNT(*) FROM market_sentiment_daily").fetchone()[0] == 1
    assert conn.execute("SELECT cycle_phase FROM market_sentiment_daily").fetchone()[0] == "climax"
