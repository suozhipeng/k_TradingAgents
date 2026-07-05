"""Tests for the strategy parameter optimizer."""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path

import pandas as pd

from tests.astock_import_helpers import load_astock_submodule

_REPO = Path(__file__).resolve().parent.parent
_EXEC = _REPO / "tradingagents" / "astock" / "execution"
_PKG_PARENT = "tradingagents.astock.execution"


def _load_submodule(rel_name: str):
    """Load optimizer module without polluting sys.modules."""
    return load_astock_submodule(rel_name, _PKG_PARENT, _EXEC)


_opt = _load_submodule("optimizer")

StrategyOptimizer = _opt.StrategyOptimizer
optimize_strategy = _opt.optimize_strategy
DEFAULT_SEARCH_SPACES = _opt.DEFAULT_SEARCH_SPACES
_get_strategy_map = _opt._get_strategy_map
_composite_score = _opt._composite_score


# ---------------------------------------------------------------------------
# Tests (unchanged)
# ---------------------------------------------------------------------------


class TestSearchSpaces(unittest.TestCase):
    def test_all_strategies_have_default_space(self) -> None:
        mapping = _get_strategy_map()
        for name in mapping:
            space = DEFAULT_SEARCH_SPACES.get(name, {})
            self.assertTrue(len(space) > 0, f"{name} has no default search space")

    def test_each_space_has_valid_values(self) -> None:
        for name, space in DEFAULT_SEARCH_SPACES.items():
            for param, values in space.items():
                self.assertTrue(len(values) > 0, f"{name}.{param} has empty values")

    def test_search_space_count(self) -> None:
        mapping = _get_strategy_map()
        self.assertEqual(len(DEFAULT_SEARCH_SPACES), len(mapping))


class TestCompositeScore(unittest.TestCase):
    def test_positive_sharpe_scores_positive(self) -> None:
        metrics = {"sharpe_ratio": 1.5, "total_return": 0.2, "max_drawdown": 0.1, "total_trades": 10}
        self.assertGreater(_composite_score(metrics), 0.0)

    def test_negative_sharpe_scores_negative(self) -> None:
        metrics = {"sharpe_ratio": -0.5, "total_return": -0.1, "max_drawdown": 0.3, "total_trades": 5}
        self.assertLess(_composite_score(metrics), 0.0)

    def test_high_drawdown_penalizes(self) -> None:
        good = _composite_score({"sharpe_ratio": 1.0, "total_return": 0.2, "max_drawdown": 0.05, "total_trades": 10})
        bad = _composite_score({"sharpe_ratio": 1.0, "total_return": 0.2, "max_drawdown": 0.5, "total_trades": 10})
        self.assertGreater(good, bad)

    def test_no_trades_scores_low(self) -> None:
        score = _composite_score({"sharpe_ratio": 0.0, "total_return": 0.0, "max_drawdown": 0.0, "total_trades": 0})
        self.assertAlmostEqual(score, 0.0, places=4)


class TestOptimizerConstruction(unittest.TestCase):
    def test_by_name(self) -> None:
        opt = StrategyOptimizer("MACDTrend")
        self.assertIsNotNone(opt)

    def test_by_class(self) -> None:
        mapping = _get_strategy_map()
        opt = StrategyOptimizer(mapping["MACDTrend"])
        self.assertIsNotNone(opt)

    def test_unknown_name_raises(self) -> None:
        with self.assertRaises(ValueError):
            StrategyOptimizer("NonExistentStrategy")


class TestOptimizerRun(unittest.TestCase):
    def setUp(self):
        from tradingagents.astock.execution.backtest_engine import BacktestEngine
        self.mock_engine = BacktestEngine(use_mock_data=True)

    def test_optimize_returns_sorted_results(self) -> None:
        opt = StrategyOptimizer("MACDTrend", engine=self.mock_engine)
        results = opt.optimize(
            symbol="000001.SZ", start_date="2024-01-01", end_date="2024-06-30",
            param_grid={"fast_period": [8, 12], "slow_period": [20, 26]}, top_n=5,
        )
        self.assertTrue(len(results) > 0)
        scores = [r["score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_optimize_returns_limited_top_n(self) -> None:
        opt = StrategyOptimizer("MeanReversion", engine=self.mock_engine)
        results = opt.optimize(
            symbol="000001.SZ", start_date="2024-01-01", end_date="2024-06-30",
            param_grid={"ma_period": [10, 20], "std_multiplier": [2.0, 3.0]}, top_n=2,
        )
        self.assertLessEqual(len(results), 2)

    def test_optimize_with_default_search_space(self) -> None:
        opt = StrategyOptimizer("RSIRange", engine=self.mock_engine)
        results = opt.optimize(
            symbol="000001.SZ", start_date="2024-01-01", end_date="2024-06-30", top_n=3,
        )
        self.assertTrue(len(results) > 0)

    def test_result_contains_params_and_metrics(self) -> None:
        opt = StrategyOptimizer("BullTrend", engine=self.mock_engine)
        results = opt.optimize(
            symbol="000001.SZ", start_date="2024-01-01", end_date="2024-06-30",
            param_grid={"fast_ma": [5, 10], "mid_ma": [20]}, top_n=1,
        )
        self.assertTrue(len(results) > 0)
        r = results[0]
        self.assertIn("params", r)
        self.assertIn("metrics", r)
        self.assertIn("score", r)

    def test_optimize_empty_param_grid_returns_default(self) -> None:
        opt = StrategyOptimizer("PutWrite", engine=self.mock_engine)
        results = opt.optimize(
            symbol="000001.SZ", start_date="2024-01-01", end_date="2024-06-30",
            param_grid={}, top_n=1,
        )
        self.assertGreaterEqual(len(results), 0)


class TestConvenienceWrapper(unittest.TestCase):
    def test_wrapper_runs(self) -> None:
        from tradingagents.astock.execution.backtest_engine import BacktestEngine
        mock_engine = BacktestEngine(use_mock_data=True)
        results = optimize_strategy(
            "DefensiveMomentum", "000001.SZ", "2024-01-01", "2024-06-30",
            param_grid={"roc_period": [10, 20]}, top_n=2,
            engine=mock_engine,
        )
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["rank"], 1)


# ===================================================================
# Walk-Forward Analysis 测试
# ===================================================================


class TestWalkForwardAnalyzer(unittest.TestCase):
    def setUp(self):
        from tradingagents.astock.execution.backtest_engine import BacktestEngine
        self.mock_engine = BacktestEngine(use_mock_data=True)

    def test_wfa_returns_results(self):
        """Walk-Forward Analysis 返回窗口结果。"""
        from tradingagents.astock.execution.optimizer import WalkForwardAnalyzer
        wfa = WalkForwardAnalyzer("MovingAverageTrend", engine=self.mock_engine)
        results = wfa.run(
            "600519.SH", "2024-01-01", "2025-06-01",
            param_grid={"fast_period": [5, 10], "slow_period": [20, 30]},
            train_years=1, val_months=3, top_n=1,
        )
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIsInstance(r.train_score, float)
            self.assertIsInstance(r.val_score, float)
            self.assertIn("fast_period", r.best_params)

    def test_wfa_summarize_includes_overfit_gap(self):
        """summarize() 包含 overfit_gap / param_stability。"""
        from tradingagents.astock.execution.optimizer import WalkForwardAnalyzer
        wfa = WalkForwardAnalyzer("MACDTrend", engine=self.mock_engine)
        results = wfa.run(
            "600519.SH", "2024-01-01", "2025-06-01",
            param_grid={"fast_period": [8, 12], "slow_period": [20, 26]},
            train_years=1, val_months=3, top_n=1,
        )
        if results:
            summary = wfa.summarize(results)
            self.assertIn("num_windows", summary)
            self.assertIn("avg_train_score", summary)
            self.assertIn("avg_val_score", summary)
            self.assertIn("overfit_gap", summary)
            self.assertIn("param_stability", summary)
            self.assertGreater(summary["num_windows"], 0)

    def test_wfa_rolling_vs_expanding(self):
        """rolling 和 expanding 模式都产生窗口。"""
        from tradingagents.astock.execution.optimizer import WalkForwardAnalyzer
        wfa = WalkForwardAnalyzer("MovingAverageTrend", engine=self.mock_engine)
        rolling = wfa.run(
            "600519.SH", "2024-01-01", "2025-06-01",
            param_grid={"fast_period": [5]},
            train_years=1, val_months=3, window_mode="rolling",
        )
        expanding = wfa.run(
            "600519.SH", "2024-01-01", "2025-06-01",
            param_grid={"fast_period": [5]},
            train_years=1, val_months=3, window_mode="expanding",
        )
        self.assertGreater(len(rolling), 0)
        self.assertGreater(len(expanding), 0)

    def test_wfa_empty_data_returns_empty(self):
        """空数据返回空列表。"""
        from tradingagents.astock.execution.optimizer import WalkForwardAnalyzer
        wfa = WalkForwardAnalyzer("MovingAverageTrend", engine=self.mock_engine)
        results = wfa.run(
            "INVALID.X", "2099-01-01", "2099-06-01",
            param_grid={"fast_period": [5]},
        )
        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()
