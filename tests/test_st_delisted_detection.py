"""Tests for ST/delisted detection in the backtest engine.

Tests cover:
1. _detect_st_delisted — ST symbol prefix detection
2. _detect_st_delisted — delisted detection (data gap >60 trading days)
3. _detect_st_delisted — empty DataFrame edge case
4. _is_at_price_limit — normal stock ±10% limit
5. _is_at_price_limit — ST stock ±5% limit
6. _is_at_price_limit — below-threshold changes (no limit)
7. BacktestDataAssumption — st_stock and delisted fields
8. BacktestDataAssumption — to_dict() serializes both fields
9. Integration: run() with ST symbol → data_assumption has st_stock=True
10. Integration: _is_at_price_limit receives st_stock flag during run()
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
_EXEC = _REPO / "tradingagents" / "astock" / "execution"
_PKG_PARENT = "tradingagents.astock.execution"


def _load_submodule(rel_name: str):
    import importlib

    fname = rel_name + ".py"
    full_name = f"{_PKG_PARENT}.{rel_name}"
    path = str(_EXEC / fname)
    spec = importlib.util.spec_from_file_location(full_name, path)
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
    exec_pkg = sys.modules.get(_PKG_PARENT)
    if exec_pkg:
        exec_pkg.__path__ = [str(_EXEC)]
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = _PKG_PARENT
    mod.__name__ = full_name
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


_be = _load_submodule("backtest_engine")
_sb = _load_submodule("strategy_base")

BacktestEngine = _be.BacktestEngine
BacktestDataAssumption = _be.BacktestDataAssumption
BacktestResult = _be.BacktestResult
MovingAverageTrendStrategy = _sb.MovingAverageTrendStrategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ohlcv_df(
    n_bars: int,
    start: str = "2024-01-02",
    close_start: float = 100.0,
    close_step: float = 0.5,
) -> pd.DataFrame:
    """Build a DataFrame with OHLCV columns and a date index."""
    dates = pd.bdate_range(start=start, periods=n_bars)
    closes = [round(close_start + i * close_step, 2) for i in range(n_bars)]
    df = pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": [1000000] * n_bars,
        },
        index=dates,
    )
    return df


# ===================================================================
# Tests for _detect_st_delisted
# ===================================================================


class TestDetectStDelisted(unittest.TestCase):
    """Test the static method _detect_st_delisted."""

    def setUp(self):
        self.engine = BacktestEngine(use_mock_data=True)

    def test_normal_stock_not_delisted(self):
        """Normal symbol, full data range → neither ST nor delisted."""
        df = _make_ohlcv_df(60, start="2024-01-01")
        result = BacktestEngine._detect_st_delisted(
            df, "600519.SH", "2024-01-01", "2024-04-01"
        )
        self.assertFalse(result["st_stock"])
        self.assertFalse(result["delisted"])

    def test_st_prefix_detected(self):
        """Symbol starting with ST → st_stock=True."""
        df = _make_ohlcv_df(60, start="2024-01-01")
        result = BacktestEngine._detect_st_delisted(
            df, "ST600519.SH", "2024-01-01", "2024-04-01"
        )
        self.assertTrue(result["st_stock"])
        self.assertFalse(result["delisted"])

    def test_astrisk_st_prefix_detected(self):
        """Symbol starting with *ST → st_stock=True."""
        df = _make_ohlcv_df(60, start="2024-01-01")
        result = BacktestEngine._detect_st_delisted(
            df, "*ST600519.SH", "2024-01-01", "2024-04-01"
        )
        self.assertTrue(result["st_stock"])

    def test_sst_prefix_detected(self):
        """Symbol starting with SST → st_stock=True."""
        df = _make_ohlcv_df(60, start="2024-01-01")
        result = BacktestEngine._detect_st_delisted(
            df, "SST600519.SH", "2024-01-01", "2024-04-01"
        )
        self.assertTrue(result["st_stock"])

    def test_s_astrisk_st_prefix_detected(self):
        """Symbol starting with S*ST → st_stock=True."""
        df = _make_ohlcv_df(60, start="2024-01-01")
        result = BacktestEngine._detect_st_delisted(
            df, "S*ST600519.SH", "2024-01-01", "2024-04-01"
        )
        self.assertTrue(result["st_stock"])

    def test_delisted_detected(self):
        """Data ending 61 trading days before end_date → delisted=True."""
        # Generate data ending at 2024-02-15, request end_date=2024-05-15
        # That's ~65 business days gap → exceeds 60
        df = _make_ohlcv_df(30, start="2024-01-02")
        # Last bar is around 2024-02-12 (30 business days from Jan 2)
        result = BacktestEngine._detect_st_delisted(
            df, "600519.SH", "2024-01-02", "2024-05-15"
        )
        self.assertTrue(result["delisted"])
        self.assertFalse(result["st_stock"])

    def test_not_delisted_when_data_covers_range(self):
        """Data covering entire range → not delisted."""
        df = _make_ohlcv_df(100, start="2024-01-01")
        result = BacktestEngine._detect_st_delisted(
            df, "600519.SH", "2024-01-01", "2024-04-30"
        )
        self.assertFalse(result["delisted"])

    def test_not_delisted_small_gap(self):
        """Data gap of 30 trading days (<60 threshold) → not delisted."""
        df = _make_ohlcv_df(30, start="2024-01-02")
        # Last bar ~Feb 12, end_date = Mar 15 → ~23 trading days gap
        result = BacktestEngine._detect_st_delisted(
            df, "600519.SH", "2024-01-02", "2024-03-15"
        )
        self.assertFalse(result["delisted"])

    def test_empty_dataframe(self):
        """Empty DataFrame → both False."""
        df = pd.DataFrame()
        result = BacktestEngine._detect_st_delisted(
            df, "ST600519.SH", "2024-01-01", "2024-04-01"
        )
        self.assertFalse(result["st_stock"])
        self.assertFalse(result["delisted"])

    def test_both_st_and_delisted(self):
        """ST symbol that is also delisted → both True."""
        df = _make_ohlcv_df(20, start="2024-01-02")
        # Short data range + ST prefix
        result = BacktestEngine._detect_st_delisted(
            df, "*ST600519.SH", "2024-01-02", "2024-05-15"
        )
        self.assertTrue(result["st_stock"])
        self.assertTrue(result["delisted"])


# ===================================================================
# Tests for _is_at_price_limit
# ===================================================================


class TestIsAtPriceLimit(unittest.TestCase):
    """Test the price limit detection with ST/normal thresholds."""

    def make_period(self, closes: list[float], start: str = "2024-01-02") -> pd.DataFrame:
        """Build a period DataFrame with close column only."""
        dates = pd.bdate_range(start=start, periods=len(closes))
        return pd.DataFrame(
            {"close": closes, "volume": [1000000] * len(closes)},
            index=dates,
        )

    # --- Normal stock (±10% limit) ---

    def test_normal_up_limit(self):
        """Normal stock at 9.5%+ change → price_limit_up."""
        period = self.make_period([100.0, 109.6])
        limited, reason = BacktestEngine._is_at_price_limit(period, st_stock=False)
        self.assertTrue(limited)
        self.assertEqual(reason, "price_limit_up")

    def test_normal_down_limit(self):
        """Normal stock at -9.5%+ change → price_limit_down."""
        period = self.make_period([100.0, 90.4])
        limited, reason = BacktestEngine._is_at_price_limit(period, st_stock=False)
        self.assertTrue(limited)
        self.assertEqual(reason, "price_limit_down")

    def test_normal_below_threshold(self):
        """Normal stock with 9.0% change → no limit."""
        period = self.make_period([100.0, 109.0])
        limited, reason = BacktestEngine._is_at_price_limit(period, st_stock=False)
        self.assertFalse(limited)
        self.assertEqual(reason, "")

    def test_normal_exact_9_5_up(self):
        """Normal stock exactly at 9.5% threshold → limit."""
        period = self.make_period([100.0, 109.5])
        limited, reason = BacktestEngine._is_at_price_limit(period, st_stock=False)
        self.assertTrue(limited)
        self.assertEqual(reason, "price_limit_up")

    def test_normal_exact_9_5_down(self):
        """Normal stock exactly at -9.5% threshold → limit."""
        period = self.make_period([100.0, 90.5])
        limited, reason = BacktestEngine._is_at_price_limit(period, st_stock=False)
        self.assertTrue(limited)
        self.assertEqual(reason, "price_limit_down")

    # --- ST stock (±5% limit) ---

    def test_st_up_limit(self):
        """ST stock at 4.5%+ change → st_price_limit_up."""
        period = self.make_period([100.0, 104.6])
        limited, reason = BacktestEngine._is_at_price_limit(period, st_stock=True)
        self.assertTrue(limited)
        self.assertEqual(reason, "st_price_limit_up")

    def test_st_down_limit(self):
        """ST stock at -4.5%+ change → st_price_limit_down."""
        period = self.make_period([100.0, 95.4])
        limited, reason = BacktestEngine._is_at_price_limit(period, st_stock=True)
        self.assertTrue(limited)
        self.assertEqual(reason, "st_price_limit_down")

    def test_st_below_threshold(self):
        """ST stock with 4.0% change → no limit."""
        period = self.make_period([100.0, 104.0])
        limited, reason = BacktestEngine._is_at_price_limit(period, st_stock=True)
        self.assertFalse(limited)
        self.assertEqual(reason, "")

    def test_st_exact_4_5_up(self):
        """ST stock exactly at 4.5% threshold → limit."""
        period = self.make_period([100.0, 104.5])
        limited, reason = BacktestEngine._is_at_price_limit(period, st_stock=True)
        self.assertTrue(limited)
        self.assertEqual(reason, "st_price_limit_up")

    def test_st_exact_4_5_down(self):
        """ST stock exactly at -4.5% threshold → limit."""
        period = self.make_period([100.0, 95.5])
        limited, reason = BacktestEngine._is_at_price_limit(period, st_stock=True)
        self.assertTrue(limited)
        self.assertEqual(reason, "st_price_limit_down")

    # --- Edge cases ---

    def test_single_row_no_limit(self):
        """Single data point → no limit."""
        period = self.make_period([100.0])
        limited, reason = BacktestEngine._is_at_price_limit(period)
        self.assertFalse(limited)

    def test_prev_close_zero_no_limit(self):
        """Previous close <= 0 → no limit."""
        period = self.make_period([0.0, 100.0])
        limited, reason = BacktestEngine._is_at_price_limit(period)
        self.assertFalse(limited)


# ===================================================================
# Tests for BacktestDataAssumption fields
# ===================================================================


class TestBacktestDataAssumptionST(unittest.TestCase):
    """Test the new fields in BacktestDataAssumption."""

    def test_default_values(self):
        """st_stock and delisted default to False."""
        assumption = BacktestDataAssumption()
        self.assertFalse(assumption.st_stock)
        self.assertFalse(assumption.delisted)

    def test_can_set_st_stock(self):
        """Can set st_stock=True."""
        assumption = BacktestDataAssumption(st_stock=True)
        self.assertTrue(assumption.st_stock)

    def test_can_set_delisted(self):
        """Can set delisted=True."""
        assumption = BacktestDataAssumption(delisted=True)
        self.assertTrue(assumption.delisted)

    def test_to_dict_includes_st_stock(self):
        """to_dict() includes st_stock key."""
        assumption = BacktestDataAssumption(st_stock=True)
        d = assumption.to_dict()
        self.assertIn("st_stock", d)
        self.assertTrue(d["st_stock"])

    def test_to_dict_includes_delisted(self):
        """to_dict() includes delisted key."""
        assumption = BacktestDataAssumption(delisted=True)
        d = assumption.to_dict()
        self.assertIn("delisted", d)
        self.assertTrue(d["delisted"])

    def test_to_dict_defaults_false(self):
        """to_dict() includes both keys with False by default."""
        assumption = BacktestDataAssumption()
        d = assumption.to_dict()
        self.assertFalse(d["st_stock"])
        self.assertFalse(d["delisted"])


# ===================================================================
# Integration tests
# ===================================================================


class TestBacktestEngineSTIntegration(unittest.TestCase):
    """Integration tests: ST detection flows through run()."""

    def test_stock_result_has_default_assumption(self):
        """Normal mock backtest → st_stock=False and delisted=False."""
        engine = BacktestEngine(use_mock_data=True)
        strategy = MovingAverageTrendStrategy()
        result = engine.run("NORMAL.SH", "2024-01-02", "2024-01-31", strategy)
        self.assertFalse(result.data_assumption.get("st_stock", True))
        self.assertFalse(result.data_assumption.get("delisted", True))

    def test_data_assumption_contains_keys(self):
        """data_assumption dict includes st_stock and delisted keys."""
        engine = BacktestEngine(use_mock_data=True)
        strategy = MovingAverageTrendStrategy()
        result = engine.run("TEST.A", "2024-01-02", "2024-03-29", strategy)
        self.assertIn("st_stock", result.data_assumption)
        self.assertIn("delisted", result.data_assumption)


if __name__ == "__main__":
    unittest.main()
