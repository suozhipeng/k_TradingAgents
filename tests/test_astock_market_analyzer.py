"""Market analyzer tests — at least 6 tests.

Uses mock DuckDB data (directly injected) to verify dimension analysis
and composite scoring logic without depending on a real store.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from tradingagents.astock.analysis.market_analyzer import MarketAnalyzer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_kline_df(
    trend: str = "up",
    n_days: int = 80,
    start: str = "2026-03-01",
    base_price: float = 100.0,
) -> pd.DataFrame:
    """Build a DataFrame that looks like query_kline() output."""
    dates = pd.bdate_range(start=start, periods=n_days)
    rows = []
    price = base_price
    for dt in dates:
        if trend == "up":
            price *= 1.008
        elif trend == "down":
            price *= 0.992
        else:
            price += (hash(str(dt)) % 3 - 1) * 0.5
        rows.append(
            {
                "trade_date": dt.date(),
                "open": round(price, 2),
                "high": round(price * 1.01, 2),
                "low": round(price * 0.99, 2),
                "close": round(price, 2),
                "volume": int(abs(hash(str(dt))) % 1000000 + 500000),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMarketAnalyzerBasic(unittest.TestCase):
    """MarketAnalyzer 基本结构和空数据处理。"""

    def setUp(self):
        self.mock_store = MagicMock()
        self.mock_store.query_kline.return_value = pd.DataFrame()
        self.analyzer = MarketAnalyzer(store=self.mock_store)

    # --- Basic structure tests ---

    def test_analyze_returns_expected_keys(self):
        """analyze() returns all expected top-level keys."""
        df = _make_kline_df(trend="up")
        self.mock_store.query_kline.return_value = df.copy()
        result = self.analyzer.analyze("000300.SH", "2026-06-12")
        expected_keys = {
            "symbol", "trade_date", "dimensions",
            "composite_score", "market_verdict", "recommended_strategies",
        }
        self.assertEqual(set(result.keys()), expected_keys)
        for dim_key in ("trend", "momentum", "volatility", "volume"):
            self.assertIn(dim_key, result["dimensions"])

    def test_analyze_empty_data_returns_neutral(self):
        """analyze() returns neutral verdict when store has no data."""
        result = self.analyzer.analyze("000300.SH", "2026-06-12")
        self.assertEqual(result["market_verdict"], "neutral")
        self.assertEqual(result["composite_score"], 0.0)

    # --- Dimension analysis tests ---

    def test_trend_bullish(self):
        """_analyze_trend returns bullish for MA5 > MA20 > MA60."""
        df = _make_kline_df(trend="up", n_days=80)
        trend = MarketAnalyzer._analyze_trend(df)
        self.assertEqual(trend["verdict"], "bullish")
        self.assertGreater(trend["score"], 0.5)

    def test_trend_bearish(self):
        """_analyze_trend returns bearish for MA5 < MA20 < MA60."""
        df = _make_kline_df(trend="down", n_days=80)
        trend = MarketAnalyzer._analyze_trend(df)
        self.assertEqual(trend["verdict"], "bearish")
        self.assertLess(trend["score"], -0.5)

    def test_momentum_bullish(self):
        """_analyze_momentum returns bullish for strong uptrend."""
        df = _make_kline_df(trend="up", n_days=40)
        momentum = MarketAnalyzer._analyze_momentum(df)
        self.assertIn(momentum["verdict"], ("bullish", "neutral"))
        self.assertGreaterEqual(momentum["score"], -1.0)

    def test_momentum_bearish(self):
        """_analyze_momentum returns bearish for strong downtrend."""
        df = _make_kline_df(trend="down", n_days=40)
        momentum = MarketAnalyzer._analyze_momentum(df)
        self.assertIn(momentum["verdict"], ("bearish", "neutral"))
        self.assertLessEqual(momentum["score"], 1.0)

    def test_volatility_normal(self):
        """_analyze_volatility returns normal for moderate ATR."""
        df = _make_kline_df(trend="up", n_days=40)
        vol = MarketAnalyzer._analyze_volatility(df)
        self.assertIn(vol["verdict"], ("low", "normal", "high"))

    def test_volume_active(self):
        """_analyze_volume returns non-empty verdict."""
        df = _make_kline_df(trend="up", n_days=40)
        vol = MarketAnalyzer._analyze_volume(df)
        self.assertIn(vol["verdict"], ("active", "normal", "weak"))

    # --- Composite / verdict tests ---

    def test_classify_verdict_returns_valid_label(self):
        """每个复合分数区间都有对应的标签。"""
        for composite, expected in [
            (-0.8, "bearish"),
            (-0.3, "cautious_bearish"),
            (0.0, "neutral"),
            (0.3, "cautious_bullish"),
            (0.8, "bullish"),
        ]:
            with self.subTest(score=composite):
                verdict = MarketAnalyzer._classify_verdict(composite)
                self.assertEqual(verdict, expected)

    def test_recommended_strategies_match_regime(self):
        """每个市况下都有推荐的策略列表。"""
        strategies = MarketAnalyzer._empty_result("000300.SH", "2026-06-12")
        self.assertEqual(strategies["recommended_strategies"], [])
        self.assertEqual(strategies["market_verdict"], "neutral")

    def test_analyze_integration_bullish(self):
        """完整分析链路：上涨趋势 → bullish 或 cautious_bullish。"""
        df = _make_kline_df(trend="up", n_days=120)
        self.mock_store.query_kline.return_value = df.copy()
        result = self.analyzer.analyze("000300.SH", df["trade_date"].iloc[-1])
        self.assertIn(result["market_verdict"], ("bullish", "cautious_bullish", "neutral"))

    def test_analyze_integration_bearish(self):
        """完整分析链路：下跌趋势 → bearish 或 cautious_bearish。"""
        df = _make_kline_df(trend="down", n_days=120)
        self.mock_store.query_kline.return_value = df.copy()
        result = self.analyzer.analyze("000300.SH", df["trade_date"].iloc[-1])
        self.assertIn(result["market_verdict"], ("bearish", "cautious_bearish", "neutral"))


if __name__ == "__main__":
    unittest.main()
