"""Tests for price adjustment (复权) utilities."""
from __future__ import annotations

import unittest
from datetime import date

import pandas as pd

from tradingagents.astock.data_sources.adjustment import adjust_series


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


if __name__ == "__main__":
    unittest.main()
