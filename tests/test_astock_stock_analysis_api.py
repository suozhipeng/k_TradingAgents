"""Tests for stock analysis API fact lineage."""

from types import SimpleNamespace

import duckdb
from flask import Flask

from tradingagents.astock.api.routes_analysis import bp


def _client():
    conn = duckdb.connect(":memory:")
    conn.execute("""
        CREATE TABLE kline_bars (
            symbol VARCHAR, trade_date DATE, close DOUBLE,
            volume DOUBLE, bar_time TIMESTAMP,
            interval VARCHAR DEFAULT '1d'
        )
    """)
    conn.execute("""
        INSERT INTO kline_bars(symbol, trade_date, close, volume, bar_time) VALUES
        ('AAA', '2024-01-01', 10, 100, '2024-01-01'),
        ('AAA', '2024-01-02', 11, 120, '2024-01-02'),
        ('AAA', '2024-01-03', 10.5, 130, '2024-01-03')
    """)
    app = Flask(__name__)
    app.config["STORE"] = SimpleNamespace(conn=conn)
    app.register_blueprint(bp, url_prefix="/api/v1")
    return app.test_client()


def test_stock_analysis_api_returns_facts_and_risks():
    response = _client().get("/api/v1/analysis/stock/AAA?as_of=2024-01-03")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["symbol"] == "AAA"
    assert payload["llm_used"] is False
    assert payload["facts"]
    assert all(f["fact_id"].startswith("stock_fact_") for f in payload["facts"])
    assert all(f["source_table"] == "kline_bars" for f in payload["facts"])


def test_stock_analysis_api_explicitly_reports_missing_symbol_data():
    response = _client().get("/api/v1/analysis/stock/UNKNOWN")
    assert response.status_code == 200
    assert response.get_json()["status"] == "not_initialized"
    assert response.get_json()["facts"] == []
