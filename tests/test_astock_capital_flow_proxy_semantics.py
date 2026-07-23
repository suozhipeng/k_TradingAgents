"""Tests for derived metrics — capital flow proxy semantics."""

import pandas as pd
from tradingagents.astock.analysis.derived_metrics import (
    compute_derived_pe, compute_volume_price_proxy,
)


def test_derived_pe_returns_proxy_type():
    df = pd.DataFrame({"close": [10, 11, 12]})
    result = compute_derived_pe(df)
    assert result["metric_type"] == "derived_proxy"


def test_volume_price_proxy_available():
    df = pd.DataFrame({"close": [10, 11, 12, 13, 14, 15],
                        "volume": [100, 200, 150, 300, 250, 400]})
    result = compute_volume_price_proxy(df)
    assert result["data_state"] == "available"
    assert result["metric_type"] == "derived_proxy"
    assert result["provider_reported_equivalent"] is False
    assert "proxy_score" in result


def test_volume_price_proxy_unavailable_insufficient():
    result = compute_volume_price_proxy(pd.DataFrame({"close": [10]}))
    assert result["data_state"] == "unavailable"


def test_volume_price_proxy_missing_columns():
    result = compute_volume_price_proxy(pd.DataFrame({"a": [1]}))
    assert result["data_state"] == "unavailable"


def test_derived_pe_does_not_claim_provider_source():
    result = compute_derived_pe(pd.DataFrame())
    assert "metric_type" in result


def test_volume_price_proxy_no_main_force_terminology():
    df = pd.DataFrame({"close": [10, 11, 12], "volume": [100, 200, 150]})
    result = compute_volume_price_proxy(df)
    text = str(result).lower()
    assert "主力" not in text
    assert "main force" not in text
