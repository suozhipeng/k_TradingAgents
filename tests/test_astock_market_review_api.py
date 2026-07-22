"""Tests for Canonical DuckDB-backed market review API."""

from types import SimpleNamespace

import duckdb
from flask import Flask

from tradingagents.astock.api.routes_market_review import bp


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
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["as_of"] == "2024-01-02"
    assert payload["llm_used"] is False
    assert payload["facts"]
    assert all(f["source_table"] == "kline_bars" for f in payload["facts"])


def test_market_review_persists_and_can_be_read_after_request():
    client = _client()
    report = client.get("/api/v1/market/review?as_of=2024-01-02").get_json()
    loaded = client.get(f"/api/v1/market/review/{report['run_id']}")
    assert loaded.status_code == 200
    assert loaded.get_json()["run_id"] == report["run_id"]


def test_market_review_empty_canonical_store_is_explicit():
    client = _client()
    # The fixture has data; an unknown future cutoff still returns an explicit report.
    response = client.post("/api/v1/market/review?as_of=2020-01-01")
    assert response.status_code == 200
    assert response.get_json()["status"] == "not_initialized"
