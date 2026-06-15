"""Market analyzer tests — at least 6 tests.

Uses mock DuckDB data (directly injected) to verify dimension analysis
and composite scoring logic without depending on a real store.
"""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
_ANALYSIS = _REPO / "tradingagents" / "astock" / "analysis"
_PKG_PARENT = "tradingagents.astock.analysis"


def _load_module(rel_name: str):
    """Load market_analyzer module without polluting sys.modules."""
    import importlib.util as util

    fname = rel_name + ".py"
    full_name = f"{_PKG_PARENT}.{rel_name}"
    path = str(_ANALYSIS / fname)
    spec = util.spec_from_file_location(full_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {full_name} from {path}")

    for parent in ("tradingagents", "tradingagents.astock", _PKG_PARENT):
        mod = sys.modules.get(parent)
        if mod is not None and hasattr(mod, "__path__") and not getattr(mod, "__path__", []):
            del sys.modules[parent]
        if parent not in sys.modules:
            try:
                importlib.import_module(parent)
            except ImportError:
                pass

    analysis_pkg = sys.modules.get(_PKG_PARENT)
    if analysis_pkg:
        analysis_pkg.__path__ = [str(_ANALYSIS)]

    mod = util.module_from_spec(spec)
    mod.__package__ = _PKG_PARENT
    mod.__name__ = full_name
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


_ma = _load_module("market_analyzer")
MarketAnalyzer = _ma.MarketAnalyzer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_kline_df(
    trend: str = "up", n_days: int = 80, start: str = "2026-03-01", base_price: float = 100.0,
) -> pd.DataFrame:
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
        rows.append({
            "trade_date": dt.date(), "open": round(price, 2),
            "high": round(price * 1.01, 2), "low": round(price * 0.99, 2),
            "close": round(price, 2),
            "volume": int(abs(hash(str(dt))) % 1000000 + 500000),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMarketAnalyzerBasic(unittest.TestCase):
    def setUp(self):
        self.mock_store = MagicMock()
        self.mock_store.query_kline.return_value = pd.DataFrame()
        self.analyzer = MarketAnalyzer(store=self.mock_store)

    def test_analyze_returns_expected_keys(self):
        df = _make_kline_df(trend="up")
        self.mock_store.query_kline.return_value = df.copy()
        result = self.analyzer.analyze("000300.SH", "2026-06-12")
        expected_keys = {"symbol", "trade_date", "dimensions", "composite_score", "market_verdict", "recommended_strategies"}
        self.assertEqual(set(result.keys()), expected_keys)
        for dim_key in ("trend", "momentum", "volatility", "volume"):
            self.assertIn(dim_key, result["dimensions"])

    def test_analyze_empty_data_returns_neutral(self):
        result = self.analyzer.analyze("000300.SH", "2026-06-12")
        self.assertEqual(result["market_verdict"], "neutral")
        self.assertEqual(result["composite_score"], 0.0)

    def test_trend_bullish(self):
        df = _make_kline_df(trend="up", n_days=80)
        trend = MarketAnalyzer._analyze_trend(df)
        self.assertEqual(trend["verdict"], "bullish")
        self.assertGreater(trend["score"], 0.5)

    def test_trend_bearish(self):
        df = _make_kline_df(trend="down", n_days=80)
        trend = MarketAnalyzer._analyze_trend(df)
        self.assertEqual(trend["verdict"], "bearish")
        self.assertLess(trend["score"], -0.5)

    def test_momentum_bullish(self):
        df = _make_kline_df(trend="up", n_days=40)
        momentum = MarketAnalyzer._analyze_momentum(df)
        self.assertIn(momentum["verdict"], ("bullish", "neutral"))
        self.assertGreaterEqual(momentum["score"], -1.0)

    def test_momentum_bearish(self):
        df = _make_kline_df(trend="down", n_days=40)
        momentum = MarketAnalyzer._analyze_momentum(df)
        self.assertIn(momentum["verdict"], ("bearish", "neutral"))
        self.assertLessEqual(momentum["score"], 1.0)

    def test_classify_verdict_returns_valid_label(self):
        for composite, expected in [(-0.8, "bearish"), (-0.3, "cautious_bearish"), (0.0, "neutral"), (0.3, "cautious_bullish"), (0.8, "bullish")]:
            with self.subTest(score=composite):
                self.assertEqual(MarketAnalyzer._classify_verdict(composite), expected)

    def test_analyze_integration_bullish(self):
        df = _make_kline_df(trend="up", n_days=120)
        self.mock_store.query_kline.return_value = df.copy()
        result = self.analyzer.analyze("000300.SH", df["trade_date"].iloc[-1])
        self.assertIn(result["market_verdict"], ("bullish", "cautious_bullish", "neutral"))

    def test_analyze_integration_bearish(self):
        df = _make_kline_df(trend="down", n_days=120)
        self.mock_store.query_kline.return_value = df.copy()
        result = self.analyzer.analyze("000300.SH", df["trade_date"].iloc[-1])
        self.assertIn(result["market_verdict"], ("bearish", "cautious_bearish", "neutral"))


if __name__ == "__main__":
    unittest.main()
