"""Tests for multi-dimension stock analysis engine."""

import pandas as pd

from tradingagents.astock.analysis.engine import compute_analysis, DIMENSIONS


def _frame(n=60):
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    closes = [50 + i * 0.3 for i in range(n)]
    return pd.DataFrame({"trade_date": dates, "open": closes, "close": closes, "symbol": "TEST"})


def test_technical_dimension_available():
    result = compute_analysis(_frame(), "TEST")
    assert result["data_state"] == "available"
    assert result["dimensions"]["technical"]["data_state"] == "available"
    assert "ma5" in result["dimensions"]["technical"]
    assert "macd_line" in result["dimensions"]["technical"]
    assert "rsi_14" in result["dimensions"]["technical"]
    assert "boll_upper" in result["dimensions"]["technical"]


def test_fundamental_unavailable():
    result = compute_analysis(_frame(), "TEST")
    assert result["dimensions"]["fundamental"]["data_state"] == "unavailable"


def test_risk_signals_available():
    result = compute_analysis(_frame(), "TEST")
    assert result["dimensions"]["risk"]["data_state"] == "available"


def test_all_dimensions_present():
    result = compute_analysis(_frame(), "TEST")
    for d in DIMENSIONS:
        assert d in result["dimensions"], f"missing dimension: {d}"


def test_insufficient_bars():
    result = compute_analysis(_frame(3), "TEST")
    assert result["data_state"] == "unavailable"


def test_missing_columns():
    result = compute_analysis(pd.DataFrame({"a": [1]}), "TEST")
    assert result["data_state"] == "unavailable"
