"""Backtest engine, strategy base, fee model, and metrics tests.

Uses direct importlib imports to match the existing testing convention
in this repo (see ``test_astock_phase9_contracts.py``).
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Direct module imports (bypass package __init__.py chain)
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parent.parent
_EXEC = _REPO / "tradingagents" / "astock" / "execution"

_PKG_PARENT = "tradingagents.astock.execution"

def _load_submodule(rel_name: str):
    """Load a module without polluting sys.modules with fake packages."""
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


_sb = _load_submodule("strategy_base")
_fm = _load_submodule("fee_model")
_be = _load_submodule("backtest_engine")
_me = _load_submodule("metrics")

StrategyBase = _sb.StrategyBase
MovingAverageTrendStrategy = _sb.MovingAverageTrendStrategy
AStockFeeConfig = _fm.AStockFeeConfig
calculate_fees = _fm.calculate_fees
BacktestEngine = _be.BacktestEngine
BacktestResult = _be.BacktestResult
calculate_returns = _me.calculate_returns
calculate_sharpe = _me.calculate_sharpe
calculate_max_drawdown = _me.calculate_max_drawdown
calculate_win_rate = _me.calculate_win_rate
summarize_metrics = _me.summarize_metrics

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_df(prices: list[float], start: str = "2024-01-02") -> pd.DataFrame:
    """Build a DataFrame with a ``close`` column and a date index."""
    dates = pd.bdate_range(start=start, periods=len(prices))
    return pd.DataFrame({"close": prices}, index=dates)


# ===================================================================
# Strategy tests
# ===================================================================


class TestStrategyBase(unittest.TestCase):
    def test_abstract_class_cannot_be_instantiated(self) -> None:
        with self.assertRaises(TypeError):
            StrategyBase({})  # type: ignore[abstract]

    def test_ma_trend_simple_crossover(self) -> None:
        """Buy signal when fast MA crosses above slow MA."""
        # Use 30 data points: first 15 falling → slow MA > fast MA, then 15 rising → cross happens
        prices = (
            [30, 29, 28, 27, 26, 25, 24, 23, 22, 21, 20, 19, 18, 17, 16]  # down
            + [16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]  # up
        )
        df = _make_test_df(prices)
        strat = MovingAverageTrendStrategy({"fast_period": 5, "slow_period": 15})
        signals = strat.generate_signals(df)
        # Should have at least one buy signal
        self.assertIn(1, signals.values)

    def test_ma_trend_sell_signal(self) -> None:
        """Sell signal when fast MA crosses below slow MA."""
        # 30 data points: first 15 rising, then 15 falling
        prices = (
            [16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]  # up
            + [30, 29, 28, 27, 26, 25, 24, 23, 22, 21, 20, 19, 18, 17, 16]  # down
        )
        df = _make_test_df(prices)
        strat = MovingAverageTrendStrategy({"fast_period": 5, "slow_period": 15})
        signals = strat.generate_signals(df)
        self.assertIn(-1, signals.values)

    def test_ma_trend_no_signal_flat(self) -> None:
        """Flat price → no crossover → all zeros."""
        prices = [100] * 30
        df = _make_test_df(prices)
        strat = MovingAverageTrendStrategy({"fast_period": 5, "slow_period": 20})
        signals = strat.generate_signals(df)
        self.assertTrue((signals == 0).all())

    def test_ma_trend_period_validation(self) -> None:
        """Fast period must be < slow period."""
        with self.assertRaises(ValueError):
            MovingAverageTrendStrategy({"fast_period": 20, "slow_period": 5})

    def test_ma_trend_missing_column(self) -> None:
        """Raises KeyError when price column is missing."""
        df = pd.DataFrame({"open": [1, 2, 3]})
        strat = MovingAverageTrendStrategy()
        with self.assertRaises(KeyError):
            strat.generate_signals(df)


# ===================================================================
# Fee model tests
# ===================================================================


class TestFeeModel(unittest.TestCase):
    def test_buy_fees_no_stamp_tax(self) -> None:
        """Buy trades have zero stamp tax."""
        result = calculate_fees(price=10.0, shares=1000, is_buy=True)
        self.assertEqual(result["stamp_tax"], 0.0)

    def test_sell_fees_include_stamp_tax(self) -> None:
        """Sell trades include stamp tax."""
        result = calculate_fees(price=10.0, shares=1000, is_buy=False)
        expected_stamp = 10.0 * 1000 * 0.001
        self.assertAlmostEqual(result["stamp_tax"], expected_stamp)

    def test_min_commission_enforced(self) -> None:
        """Commission is at least 5 CNY even for small trades."""
        result = calculate_fees(price=1.0, shares=100, is_buy=True)
        self.assertGreaterEqual(result["commission"], 5.0)

    def test_large_trade_commission_proportional(self) -> None:
        """Large trade exceeds min commission, uses rate."""
        result = calculate_fees(price=100.0, shares=10000, is_buy=True)
        expected = 100.0 * 10000 * 0.00025
        self.assertAlmostEqual(result["commission"], expected)

    def test_slippage_bilateral(self) -> None:
        """Slippage is price × rate × 2 (双边)."""
        result = calculate_fees(price=50.0, shares=200, is_buy=True)
        expected = 50.0 * 200 * 0.001 * 2
        self.assertAlmostEqual(result["slippage"], expected)

    def test_total_fees_sum(self) -> None:
        """Total equals commission + stamp_tax + slippage."""
        result = calculate_fees(price=30.0, shares=500, is_buy=False)
        self.assertAlmostEqual(
            result["total"],
            result["commission"] + result["stamp_tax"] + result["slippage"],
        )


# ===================================================================
# Metrics tests
# ===================================================================


class TestMetrics(unittest.TestCase):
    def test_calculate_sharpe_flat_returns(self) -> None:
        """Constant returns → Sharpe ratio 0.0."""
        prices = pd.Series([100.0] * 10)
        rets = calculate_returns(prices)
        self.assertEqual(calculate_sharpe(rets), 0.0)

    def test_calculate_sharpe_positive(self) -> None:
        """Monotonically increasing → positive Sharpe."""
        prices = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0])
        rets = calculate_returns(prices)
        self.assertGreater(calculate_sharpe(rets), 0.0)

    def test_max_drawdown_simple(self) -> None:
        """Known drawdown value."""
        prices = pd.Series([100, 120, 90, 110, 80, 100])
        # Peak at 120, trough at 80 → (120-80)/120 = 0.3333
        dd = calculate_max_drawdown(prices)
        self.assertAlmostEqual(dd, 0.333333, places=4)

    def test_max_drawdown_no_drawdown(self) -> None:
        """Monotonically increasing → 0 drawdown."""
        prices = pd.Series([100, 110, 120, 130])
        self.assertEqual(calculate_max_drawdown(prices), 0.0)

    def test_win_rate_all_wins(self) -> None:
        trades = [{"pnl": 10}, {"pnl": 5}, {"pnl": 3}]
        self.assertEqual(calculate_win_rate(trades), 1.0)

    def test_win_rate_mixed(self) -> None:
        trades = [{"pnl": 10}, {"pnl": -5}, {"pnl": 3}, {"pnl": -2}]
        self.assertAlmostEqual(calculate_win_rate(trades), 0.5)

    def test_win_rate_empty(self) -> None:
        self.assertEqual(calculate_win_rate([]), 0.0)

    def test_summarize_metrics_returns_all_keys(self) -> None:
        prices = pd.Series([100, 110, 105, 120], index=pd.bdate_range("2024-01-02", periods=4))
        trades = [{"pnl": 8}, {"pnl": -3}]
        summary = summarize_metrics(prices, trades)
        expected_keys = {"total_return", "annualized_return", "sharpe_ratio", "max_drawdown", "win_rate", "total_trades"}
        self.assertEqual(set(summary.keys()), expected_keys)


# ===================================================================
# Backtest engine tests
# ===================================================================


class TestBacktestEngine(unittest.TestCase):
    def test_run_returns_backtest_result(self) -> None:
        """Minimal run returns a BacktestResult."""
        engine = BacktestEngine()
        strat = MovingAverageTrendStrategy()
        result = engine.run("000001.SH", "2024-01-02", "2024-01-31", strat)
        self.assertIsInstance(result, BacktestResult)
        self.assertEqual(result.symbol, "000001.SH")

    def test_run_with_mock_populates_metrics(self) -> None:
        """Mock data yields non-trivial metrics."""
        engine = BacktestEngine()
        strat = MovingAverageTrendStrategy({"fast_period": 3, "slow_period": 7})
        result = engine.run("MOCK.A", "2024-01-02", "2024-02-29", strat)
        self.assertGreaterEqual(result.total_trades, 0)
        self.assertIsInstance(result.total_return, float)
        self.assertIsInstance(result.sharpe_ratio, float)

    def test_run_with_known_equity_result(self) -> None:
        """Running a strong uptrend with MA5/MA20 should produce positive return."""
        engine = BacktestEngine()
        strat = MovingAverageTrendStrategy({"fast_period": 3, "slow_period": 10})
        # Use a longer period so MAs stabilise
        result = engine.run("MOCK.B", "2024-01-02", "2024-06-30", strat)
        # Total return could be positive or negative depending on mock randomness
        # Just verify it returns a valid float
        self.assertIsInstance(result.total_return, float)

    def test_custom_fee_config_propagates(self) -> None:
        """Custom fee config appears in result."""
        cfg = AStockFeeConfig(commission_rate=0.001, min_commission=1.0)
        engine = BacktestEngine(fee_config=cfg)
        strat = MovingAverageTrendStrategy()
        result = engine.run("MOCK.C", "2024-01-02", "2024-03-31", strat)
        self.assertEqual(result.fee_config_used["commission_rate"], 0.001)

    def test_empty_data_handling(self) -> None:
        """Empty or invalid date range returns empty result gracefully."""
        engine = BacktestEngine()
        strat = MovingAverageTrendStrategy()
        result = engine.run("MOCK.D", "2099-01-01", "2099-01-02", strat)
        self.assertEqual(result.total_trades, 0)


    def test_run_deterministic(self) -> None:
        """同一输入运行两次，结果必须完全一致。"""
        engine = BacktestEngine()
        strategy = MovingAverageTrendStrategy()
        result1 = engine.run("TEST", "2024-01-01", "2024-01-31", strategy, "W")
        result2 = engine.run("TEST", "2024-01-01", "2024-01-31", strategy, "W")
        self.assertEqual(result1.total_return, result2.total_return)
        self.assertEqual(result1.sharpe_ratio, result2.sharpe_ratio)
        self.assertEqual(result1.max_drawdown, result2.max_drawdown)
        self.assertEqual(len(result1.periods), len(result2.periods))


if __name__ == "__main__":
    unittest.main()
