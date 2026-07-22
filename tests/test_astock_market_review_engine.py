"""Tests for deterministic, persisted market review facts."""

from types import SimpleNamespace

import duckdb
import pandas as pd

from tradingagents.astock.review import MarketReviewEngine


def _frame() -> pd.DataFrame:
    return pd.DataFrame([
        {"symbol": "AAA", "trade_date": "2024-01-01", "close": 10, "sector": "科技"},
        {"symbol": "AAA", "trade_date": "2024-01-02", "close": 11, "sector": "科技"},
        {"symbol": "BBB", "trade_date": "2024-01-01", "close": 10, "sector": "金融"},
        {"symbol": "BBB", "trade_date": "2024-01-02", "close": 9, "sector": "金融"},
        {"symbol": "CCC", "trade_date": "2024-01-01", "close": 10, "sector": "消费"},
        {"symbol": "CCC", "trade_date": "2024-01-02", "close": 10, "sector": "消费"},
    ])


def test_market_review_is_deterministic_and_fact_cited():
    report = MarketReviewEngine().compute(_frame(), as_of="2024-01-02")
    assert report["run_id"] == MarketReviewEngine().compute(_frame(), as_of="2024-01-02")["run_id"]
    assert report["sentiment_state"] == "震荡"
    assert report["market_breadth"] == {
        "advancing": 1, "declining": 1, "unchanged": 1, "breadth": 0.0
    }
    assert report["llm_used"] is False
    assert report["facts"]
    assert all(f["source_table"] == "kline_bars" for f in report["facts"])
    assert all(f["as_of"] == "2024-01-02" for f in report["facts"])


def test_market_review_persistence_is_idempotent():
    conn = duckdb.connect(":memory:")
    engine = MarketReviewEngine(SimpleNamespace(conn=conn))
    first = engine.run(_frame(), as_of="2024-01-02")
    second = engine.run(_frame(), as_of="2024-01-02")
    assert first["run_id"] == second["run_id"]
    assert conn.execute("SELECT COUNT(*) FROM market_review_runs").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM market_review_facts").fetchone()[0] == 6


def test_market_review_rejects_missing_canonical_columns():
    import pytest
    with pytest.raises(ValueError, match="missing market review columns"):
        MarketReviewEngine().compute(pd.DataFrame({"symbol": ["AAA"]}))
