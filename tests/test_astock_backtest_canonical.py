"""Tests for Canonical DuckDB-only A-share backtest."""

from types import SimpleNamespace

import duckdb
import pandas as pd

from tradingagents.astock.backtest.canonical import CanonicalBacktest


def _bars(n=40):
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    # Long uptrend followed by downtrend creates a cross without external data.
    half = n // 2
    closes = [10 + i * 0.1 for i in range(half)] + [10 + half * 0.1 - i * 0.2 for i in range(n - half)]
    return pd.DataFrame({"trade_date": dates, "open": closes, "close": closes, "symbol": "AAA"})


def test_canonical_backtest_is_reproducible_and_no_lookahead():
    engine = CanonicalBacktest()
    first = engine.run_frame(_bars(), symbol="AAA")
    second = engine.run_frame(_bars(), symbol="AAA")
    assert first["run_id"] == second["run_id"]
    assert first["no_lookahead"] is True
    assert first["source_table"] == "kline_bars"
    assert first["a_share_rules"] == {"lot_size": 100, "t_plus_one": True, "fees": True, "slippage": True}
    assert all(t["shares"] % 100 == 0 for t in first["trades"])


def test_canonical_backtest_persists_idempotently():
    conn = duckdb.connect(":memory:")
    store = SimpleNamespace(conn=conn)
    engine = CanonicalBacktest()
    result = engine.run_frame(_bars(), symbol="AAA")
    engine.persist(store, result)
    engine.persist(store, result)
    assert conn.execute("SELECT COUNT(*) FROM backtest_runs").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM backtest_trades").fetchone()[0] == len(result["trades"])


def test_backtest_rejects_insufficient_canonical_bars():
    import pytest
    with pytest.raises(ValueError, match="at least 22"):
        CanonicalBacktest().run_frame(_bars(10), symbol="AAA")
