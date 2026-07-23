"""Tests for Canonical DuckDB-backed market review API with V1.7 envelope."""

from types import SimpleNamespace

import duckdb
from flask import Flask

from tradingagents.astock.api.routes_market_review import bp
from tradingagents.astock.api.envelope import assert_success


def _client():
    conn = duckdb.connect(":memory:")
    conn.execute("""
        CREATE TABLE kline_bars (
            symbol VARCHAR, trade_date DATE, close DOUBLE,
            sector VARCHAR, bar_time TIMESTAMP,
            interval VARCHAR DEFAULT '1d'
        )
    """)
    conn.execute("""
        INSERT INTO kline_bars(symbol, trade_date, close, sector, bar_time) VALUES
        ('AAA', '2024-01-01', 10, '科技', '2024-01-01'),
        ('AAA', '2024-01-02', 11, '科技', '2024-01-02'),
        ('BBB', '2024-01-01', 10, '金融', '2024-01-01'),
        ('BBB', '2024-01-02', 9, '金融', '2024-01-02')
    """)
    app = Flask(__name__)
    app.config["STORE"] = SimpleNamespace(conn=conn)
    app.register_blueprint(bp, url_prefix="/api/v1")
    return app.test_client()


def test_market_review_reads_canonical_rows_and_returns_lineage():
    client = _client()
    response = client.post("/api/v1/market/review?as_of=2024-01-02")
    payload = assert_success(response.get_json())
    data = payload["data"]
    assert data["status"] == "ok"
    assert data["as_of"] == "2024-01-02"
    assert data["llm_used"] is False
    assert data["facts"]
    assert all(f["source_table"] == "kline_bars" for f in data["facts"])


def test_market_review_persists_and_can_be_read_after_request():
    client = _client()
    first = client.get("/api/v1/market/review?as_of=2024-01-02").get_json()
    data = first["data"]
    loaded = client.get(f"/api/v1/market/review/{data['run_id']}")
    assert loaded.status_code == 200
    loaded_data = loaded.get_json()["data"]
    assert loaded_data["run_id"] == data["run_id"]


def test_market_review_empty_canonical_store_is_explicit():
    client = _client()
    response = client.post("/api/v1/market/review?as_of=2020-01-01")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["meta"]["data_state"] == "unavailable"
    assert payload["data"]["status"] == "not_initialized"
