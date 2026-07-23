"""Tests for V1.7 Market Review V2 risk list."""

import pandas as pd
from tradingagents.astock.review.risk import generate_risk_list


def _frame():
    """Create a kline frame with one stock that peaked 20% above current close."""
    import numpy as np
    dates = pd.date_range("2026-06-01", "2026-07-22")
    closes = np.linspace(100, 120, len(dates))[:len(dates)-10]
    closes = list(closes) + [115, 112, 108, 105, 102, 100, 98, 96, 95, 94]
    return pd.DataFrame({
        "symbol": ["AAA"] * len(dates),
        "trade_date": dates,
        "close": closes[:len(dates)],
        "volume": [1_000_000] * len(dates),
    })


def test_risk_high_divergence_detected():
    risks = generate_risk_list(_frame(), "2026-07-22")
    codes = [r["category"] for r in risks]
    assert "high_divergence" in codes


def test_risk_returns_list():
    risks = generate_risk_list(_frame(), "2026-07-22")
    assert isinstance(risks, list)


def test_risk_empty_on_empty_frame():
    assert generate_risk_list(pd.DataFrame(), "2026-07-22") == []
