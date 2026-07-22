"""Tests for deterministic stock-analysis facts and risk persistence."""

from types import SimpleNamespace

import duckdb
import pandas as pd

from tradingagents.astock.analysis.stock_facts import StockFactsEngine


def _frame():
    return pd.DataFrame([
        {"symbol": "AAA", "trade_date": "2024-01-01", "close": 10, "volume": 100},
        {"symbol": "AAA", "trade_date": "2024-01-02", "close": 11, "volume": 120},
        {"symbol": "AAA", "trade_date": "2024-01-03", "close": 10.5, "volume": 130},
    ])


def test_stock_facts_have_lineage_and_no_llm_dependency():
    report = StockFactsEngine().compute(_frame(), symbol="AAA", as_of="2024-01-03")
    assert report["symbol"] == "AAA"
    assert report["llm_used"] is False
    assert {f["metric"] for f in report["facts"]} >= {"latest_close", "ma5", "ma20", "momentum", "volatility"}
    assert all(f["fact_id"].startswith("stock_fact_") for f in report["facts"])
    assert all(f["source_table"] == "kline_bars" for f in report["facts"])
    assert all(f["as_of"] == "2024-01-03" for f in report["facts"])


def test_stock_facts_persist_idempotently_with_risk_signals():
    conn = duckdb.connect(":memory:")
    engine = StockFactsEngine(SimpleNamespace(conn=conn))
    first = engine.run(_frame(), symbol="AAA", as_of="2024-01-03")
    second = engine.run(_frame(), symbol="AAA", as_of="2024-01-03")
    assert first["run_id"] == second["run_id"]
    assert conn.execute("SELECT COUNT(*) FROM stock_analysis_runs").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM stock_analysis_facts").fetchone()[0] == 6


def test_stock_facts_reject_missing_columns():
    import pytest
    with pytest.raises(ValueError, match="missing stock analysis columns"):
        StockFactsEngine().compute(pd.DataFrame({"symbol": ["AAA"], "close": [1]}))
