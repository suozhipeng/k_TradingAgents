"""Tests for price adjustment (复权) utilities."""
from __future__ import annotations

import unittest
from datetime import date

import pandas as pd
from unittest.mock import patch

from tradingagents.astock.data_sources.adjustment import (
    _adjust_factor_for_date,
    adjust_series,
    clear_cache,
    fetch_adjust_via_akshare_hist,
)


class TestAdjustment(unittest.TestCase):
    """Price adjustment tests — stateless, no network calls."""

    def setUp(self):
        self.prices = pd.Series([100.0, 102.0, 105.0, 103.0], name="close")

    def test_adjust_series_no_factor_returns_unchanged(self):
        result = adjust_series(self.prices, None, "forward")
        pd.testing.assert_series_equal(result, self.prices)

    def test_adjust_series_forward_divides(self):
        result = adjust_series(self.prices, 1.5, "forward")
        expected = pd.Series([66.6667, 68.0, 70.0, 68.6667], name="close")
        pd.testing.assert_series_equal(result, expected, atol=0.01)

    def test_adjust_series_backward_multiplies(self):
        result = adjust_series(self.prices, 1.5, "backward")
        expected = pd.Series([150.0, 153.0, 157.5, 154.5], name="close")
        pd.testing.assert_series_equal(result, expected)

    def test_adjust_series_none_returns_unchanged(self):
        result = adjust_series(self.prices, 1.5, "none")
        pd.testing.assert_series_equal(result, self.prices)

    def test_adjust_series_zero_factor_returns_unchanged(self):
        result = adjust_series(self.prices, 0.0, "forward")
        pd.testing.assert_series_equal(result, self.prices)

    def test_adjust_series_negative_factor_returns_unchanged(self):
        result = adjust_series(self.prices, -1.0, "forward")
        pd.testing.assert_series_equal(result, self.prices)


# ---------------------------------------------------------------------------
# Tests: _adjust_factor_for_date
# ---------------------------------------------------------------------------


class TestAdjustFactorForDate(unittest.TestCase):
    """_adjust_factor_for_date — stateless factor lookup."""

    def setUp(self):
        self.factors = pd.DataFrame({
            "date": ["2024-01-01", "2024-01-05", "2024-01-10"],
            "adjust_factor": [1.0, 1.5, 2.0],
        })

    def test_exact_date_match(self):
        result = _adjust_factor_for_date(self.factors, date(2024, 1, 5))
        self.assertAlmostEqual(result, 1.5)

    def test_prior_date_fallback(self):
        result = _adjust_factor_for_date(self.factors, date(2024, 1, 3))
        self.assertAlmostEqual(result, 1.0)

    def test_date_before_all_returns_none(self):
        result = _adjust_factor_for_date(self.factors, date(2023, 12, 1))
        self.assertIsNone(result)

    def test_empty_factors_returns_none(self):
        result = _adjust_factor_for_date(pd.DataFrame(), date(2024, 1, 5))
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Tests: clear_cache
# ---------------------------------------------------------------------------


class TestAdjustClearCache(unittest.TestCase):
    """clear_cache — reset in-memory state."""

    def test_clear_cache_runs(self):
        clear_cache()
        self.assertTrue(True)


# ---------------------------------------------------------------------------
# Tests: fetch_adjust_via_akshare_hist (mocked)
# ---------------------------------------------------------------------------


class TestFetchAdjustAkshareHist(unittest.TestCase):
    """fetch_adjust_via_akshare_hist with mocked DataFrames."""

    @patch("tradingagents.astock.data_sources.adjustment._retry")
    def test_derive_factors_from_adj_vs_raw(self, mock_retry):
        adj_df = pd.DataFrame({
            "日期": ["2024-01-02", "2024-01-03"],
            "收盘": [150.0, 160.0],
        })
        raw_df = pd.DataFrame({
            "日期": ["2024-01-02", "2024-01-03"],
            "收盘": [100.0, 100.0],
        })
        mock_retry.side_effect = [adj_df, raw_df]

        result = fetch_adjust_via_akshare_hist("600519.SH")
        self.assertIsNotNone(result)
        self.assertFalse(result.empty)
        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(result.iloc[0]["adjust_factor"], 1.5)
        self.assertAlmostEqual(result.iloc[1]["adjust_factor"], 1.6)


if __name__ == "__main__":
    unittest.main()
