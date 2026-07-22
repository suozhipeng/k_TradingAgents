"""Tests for Canonical backtest API."""

from types import SimpleNamespace

import duckdb
import pandas as pd
from flask import Flask

from tradingagents.astock.api.routes_backtest import bp


def test_canonical_backtest_api_runs_and_persists():
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE TABLE kline_bars(symbol VARCHAR, trade_date DATE, open DOUBLE, close DOUBLE)")
    dates = pd.date_range("2024-01-01", periods=40, freq="D")
    half = 20
    prices = [10 + i * 0.1 for i in range(half)] + [12 - i * 0.2 for i in range(20)]
    for day, price in zip(dates, prices):
        conn.execute("INSERT INTO kline_bars VALUES (?, ?, ?, ?)", ["AAA", day.date(), price, price])
    app = Flask(__name__)
    app.config["STORE"] = SimpleNamespace(conn=conn)
    app.register_blueprint(bp, url_prefix="/api/v1")

    response = app.test_client().post("/api/v1/backtest/canonical", json={"symbol": "AAA"})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["source_table"] == "kline_bars"
    assert payload["no_lookahead"] is True
    assert conn.execute("SELECT COUNT(*) FROM backtest_runs").fetchone()[0] == 1


def test_canonical_backtest_api_requires_symbol():
    app = Flask(__name__)
    app.config["STORE"] = SimpleNamespace(conn=duckdb.connect(":memory:"))
    app.register_blueprint(bp, url_prefix="/api/v1")
    response = app.test_client().post("/api/v1/backtest/canonical", json={})
    assert response.status_code == 400
