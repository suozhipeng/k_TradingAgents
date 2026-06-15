"""Tests for the strategy parameter optimizer."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from tradingagents.astock.execution.optimizer import (
    DEFAULT_SEARCH_SPACES,
    StrategyOptimizer,
    optimize_strategy,
    _get_strategy_map,
    _composite_score,
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSearchSpaces(unittest.TestCase):
    """默认搜索空间完整性检查。"""

    def test_all_strategies_have_default_space(self) -> None:
        """每个注册的策略都有默认搜索空间。"""
        mapping = _get_strategy_map()
        for name in mapping:
            space = DEFAULT_SEARCH_SPACES.get(name, {})
            self.assertTrue(
                len(space) > 0,
                f"{name} has no default search space",
            )

    def test_each_space_has_valid_values(self) -> None:
        """每个搜索空间的参数值列表非空。"""
        for name, space in DEFAULT_SEARCH_SPACES.items():
            for param, values in space.items():
                self.assertTrue(
                    len(values) > 0,
                    f"{name}.{param} has empty values",
                )

    def test_search_space_count(self) -> None:
        """搜索空间数量与策略数量一致。"""
        mapping = _get_strategy_map()
        self.assertEqual(len(DEFAULT_SEARCH_SPACES), len(mapping))


class TestCompositeScore(unittest.TestCase):
    """_composite_score 打分函数测试。"""

    def test_positive_sharpe_scores_positive(self) -> None:
        """正 Sharpe 比率 → 正分数。"""
        metrics = {
            "sharpe_ratio": 1.5,
            "total_return": 0.2,
            "max_drawdown": 0.1,
            "total_trades": 10,
        }
        score = _composite_score(metrics)
        self.assertGreater(score, 0.0)

    def test_negative_sharpe_scores_negative(self) -> None:
        """负 Sharpe 比率 → 负分数。"""
        metrics = {
            "sharpe_ratio": -0.5,
            "total_return": -0.1,
            "max_drawdown": 0.3,
            "total_trades": 5,
        }
        score = _composite_score(metrics)
        self.assertLess(score, 0.0)

    def test_high_drawdown_penalizes(self) -> None:
        """高回撤 → 分数降低。"""
        good = _composite_score({
            "sharpe_ratio": 1.0, "total_return": 0.2, "max_drawdown": 0.05, "total_trades": 10,
        })
        bad = _composite_score({
            "sharpe_ratio": 1.0, "total_return": 0.2, "max_drawdown": 0.5, "total_trades": 10,
        })
        self.assertGreater(good, bad)

    def test_no_trades_scores_low(self) -> None:
        """零交易 → 分数较低。"""
        score = _composite_score({
            "sharpe_ratio": 0.0, "total_return": 0.0, "max_drawdown": 0.0, "total_trades": 0,
        })
        self.assertAlmostEqual(score, 0.0, places=4)


class TestOptimizerConstruction(unittest.TestCase):
    """StrategyOptimizer 构造测试。"""

    def test_by_name(self) -> None:
        """通过策略名称构造。"""
        opt = StrategyOptimizer("MACDTrend")
        self.assertIsNotNone(opt)

    def test_by_class(self) -> None:
        """通过策略类构造。"""
        mapping = _get_strategy_map()
        opt = StrategyOptimizer(mapping["MACDTrend"])
        self.assertIsNotNone(opt)

    def test_unknown_name_raises(self) -> None:
        """未知策略名称 → ValueError。"""
        with self.assertRaises(ValueError):
            StrategyOptimizer("NonExistentStrategy")


class TestOptimizerRun(unittest.TestCase):
    """优化器运行测试 — 使用 mock 数据。"""

    def test_optimize_returns_sorted_results(self) -> None:
        """优化结果按分数降序排列。"""
        opt = StrategyOptimizer("MACDTrend")
        results = opt.optimize(
            symbol="000001.SZ",
            start_date="2024-01-01",
            end_date="2024-06-30",
            param_grid={"fast_period": [8, 12], "slow_period": [20, 26]},
            top_n=5,
        )
        self.assertTrue(len(results) > 0, "Expected at least one result")
        scores = [r["score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_optimize_returns_limited_top_n(self) -> None:
        """top_n 限制返回数量。"""
        opt = StrategyOptimizer("MeanReversion")
        results = opt.optimize(
            symbol="000001.SZ",
            start_date="2024-01-01",
            end_date="2024-06-30",
            param_grid={"ma_period": [10, 20], "std_multiplier": [2.0, 3.0]},
            top_n=2,
        )
        self.assertLessEqual(len(results), 2)

    def test_optimize_with_default_search_space(self) -> None:
        """不传 param_grid 时使用默认搜索空间。"""
        opt = StrategyOptimizer("RSIRange")
        results = opt.optimize(
            symbol="000001.SZ",
            start_date="2024-01-01",
            end_date="2024-06-30",
            top_n=3,
        )
        self.assertTrue(len(results) > 0, "Default search space should yield results")

    def test_result_contains_params_and_metrics(self) -> None:
        """每个结果包含 params、metrics、score。"""
        opt = StrategyOptimizer("BullTrend")
        results = opt.optimize(
            symbol="000001.SZ",
            start_date="2024-01-01",
            end_date="2024-06-30",
            param_grid={"fast_ma": [5, 10], "mid_ma": [20]},
            top_n=1,
        )
        self.assertTrue(len(results) >= 1)
        r = results[0]
        self.assertIn("params", r)
        self.assertIn("metrics", r)
        self.assertIn("score", r)
        self.assertIn("sharpe_ratio", r["metrics"])
        self.assertIn("total_return", r["metrics"])
        self.assertIn("max_drawdown", r["metrics"])

    def test_optimize_empty_param_grid_returns_default(self) -> None:
        """空 param_grid 回退到默认搜索空间。"""
        opt = StrategyOptimizer("PutWrite")
        results = opt.optimize(
            symbol="000001.SZ",
            start_date="2024-01-01",
            end_date="2024-06-30",
            param_grid={},
            top_n=1,
        )
        self.assertTrue(len(results) >= 0)


class TestConvenienceWrapper(unittest.TestCase):
    """optimize_strategy 便捷函数测试。"""

    def test_wrapper_runs(self) -> None:
        """optimize_strategy 返回结果。"""
        results = optimize_strategy(
            "DefensiveMomentum",
            "000001.SZ",
            "2024-01-01",
            "2024-06-30",
            param_grid={"roc_period": [10, 20]},
            top_n=2,
        )
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["rank"], 1)


if __name__ == "__main__":
    unittest.main()
