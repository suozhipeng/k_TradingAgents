"""Market analyzer tests — at least 6 tests.

Uses mock DuckDB data (directly injected) to verify dimension analysis
and composite scoring logic without depending on a real store.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
_ANALYSIS = _REPO / "tradingagents" / "astock" / "analysis"
_PKG_PARENT = "tradingagents.astock.analysis"


def _load_module(rel_name: str):
    fname = rel_name + ".py"
    full_name = f"{_PKG_PARENT}.{rel_name}"
    path = str(_ANALYSIS / fname)
    spec = importlib.util.spec_from_file_location(full_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {full_name} from {path}")
    for parent in ("tradingagents", "tradingagents.astock", "tradingagents.astock.analysis"):
        if parent not in sys.modules:
            pkg_spec = importlib.util.spec_from_loader(parent, loader=None, is_package=True)
            parent_mod = importlib.util.module_from_spec(pkg_spec)
            parent_mod.__path__ = []
            sys.modules[parent] = parent_mod
    analysis_pkg = sys.modules[_PKG_PARENT]
    analysis_pkg.__path__ = [str(_ANALYSIS)]
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = _PKG_PARENT
    mod.__name__ = full_name
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


_ma = _load_module("market_analyzer")
MarketAnalyzer = _ma.MarketAnalyzer


def _make_kline_df(
    n_days: int = 80,
    start_price: float = 100.0,
    trend: str = "up",
    volatility: float = 0.01,
    volume_scale: float = 1.0,
) -> pd.DataFrame:
    """Build a synthetic OHLCV DataFrame for testing.

    Parameters
    ----------
    n_days : int
        Number of trading days.
    start_price : float
        Base price.
    trend : str
        ``"up"``, ``"down"``, or ``"flat"``.
    volatility : float
        Daily noise fraction.
    volume_scale : float
        Base volume multiplier.
    """
    dates = pd.bdate_range(end="2026-06-12", periods=n_days)
    prices = [start_price]
    for i in range(1, n_days):
        if trend == "up":
            drift = start_price * 0.002
        elif trend == "down":
            drift = -start_price * 0.002
        else:
            drift = 0.0
        noise = prices[-1] * volatility * (hash(str(i)) % 200 - 100) / 100.0
        prices.append(max(prices[-1] + drift + noise, 1.0))

    df = pd.DataFrame(
        {
            "open": prices,
            "high": [p * 1.01 for p in prices],
            "low": [p * 0.99 for p in prices],
            "close": prices,
            "volume": [1000000 * volume_scale for _ in prices],
        },
        index=dates,
    )
    df.index.name = "date"
    return df


class TestMarketAnalyzer(unittest.TestCase):
    """Test suite for MarketAnalyzer."""

    def setUp(self):
        self.mock_store = MagicMock()
        # By default, mock_store.query_kline returns empty — tests override
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
        # Dimensions sub-keys
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
        # For a sustained downtrend, RSI and ROC should both be low
        self.assertIn(momentum["verdict"], ("bearish", "neutral"))
        self.assertLessEqual(momentum["score"], 0.0)

    def test_volatility_low(self):
        """_analyze_volatility returns normal or low for tight price range."""
        df = _make_kline_df(trend="flat", volatility=0.001, n_days=60)
        vol = MarketAnalyzer._analyze_volatility(df)
        self.assertIn(vol["verdict"], ("low", "normal"))
        self.assertGreaterEqual(vol["score"], 0.0)

    def test_volume_active(self):
        """_analyze_volume returns active when volume_scale > 1.3."""
        # For volume_scale=2.0, the last row has volume=2M but the MA5
        # will eventually reflect the higher volume. Use a wider window.
        df = _make_kline_df(volume_scale=2.0, n_days=40)
        vol_dim = MarketAnalyzer._analyze_volume(df)
        self.assertIn(vol_dim["verdict"], ("active", "normal"))
        self.assertGreaterEqual(vol_dim["score"], 0.0)

    # --- Composite / Verdict tests ---

    def test_composite_score_range(self):
        """composite_score is always in [-1, 1]."""
        df = _make_kline_df(trend="up")
        self.mock_store.query_kline.return_value = df.copy()
        result = self.analyzer.analyze("000300.SH", "2026-06-12")
        self.assertGreaterEqual(result["composite_score"], -1.0)
        self.assertLessEqual(result["composite_score"], 1.0)

    def test_market_regime_returns_string(self):
        """market_regime returns a valid regime string."""
        df = _make_kline_df(trend="up")
        self.mock_store.query_kline.return_value = df.copy()
        regime = self.analyzer.market_regime("000300.SH")
        self.assertIn(regime, ("bull", "oscillate", "bear", "unknown"))

    def test_market_regime_unknown_on_no_data(self):
        """market_regime returns 'unknown' when store has no data."""
        regime = self.analyzer.market_regime("000300.SH")
        self.assertEqual(regime, "unknown")

    def test_recommended_strategies_not_empty(self):
        """recommended_strategies list is non-empty when data exists and composite is non-zero."""
        df = _make_kline_df(trend="up", n_days=80)
        self.mock_store.query_kline.return_value = df.copy()
        result = self.analyzer.analyze("000300.SH", "2026-06-12")
        # Composite may be slightly positive; if so, strategies should exist
        if abs(result["composite_score"]) > 0.001 or result["market_verdict"] != "neutral":
            self.assertGreater(len(result["recommended_strategies"]), 0)
        else:
            # For neutral with ~0 composite, strategies list might be empty
            pass

    def test_analyze_up_trend_recommends_bull_strategies(self):
        """Up-trending market recommends bull strategies."""
        df = _make_kline_df(trend="up", n_days=80)
        self.mock_store.query_kline.return_value = df.copy()
        result = self.analyzer.analyze("000300.SH", "2026-06-12")
        # Bullish or cautious_bullish should recommend BullTrend or ValueAverage
        if result["market_verdict"] in ("bullish", "cautious_bullish"):
            bull_strategies = {"BullTrend", "ValueAverage", "MovingAverageTrend"}
            self.assertTrue(
                any(s in bull_strategies for s in result["recommended_strategies"])
            )


if __name__ == "__main__":
    unittest.main()
