"""Strategy parameter optimizer — grid search over config space.

Usage
-----
>>> from tradingagents.astock.execution.optimizer import StrategyOptimizer
>>> from tradingagents.astock.execution.strategy_base import MACDTrendStrategy
>>> optimizer = StrategyOptimizer(strategy_cls=MACDTrendStrategy)
>>> params = {"fast_period": [8, 12, 16], "slow_period": [20, 26, 32]}
>>> results = optimizer.optimize("600519.SH", "2024-01-01", "2025-12-31", params)
>>> results[0]["params"]  # best parameter set
"""

from .config import DEFAULT_SEARCH_SPACES, optimize_strategy
from .optimizer import StrategyOptimizer
from .walk_forward import WalkForwardAnalyzer

__all__ = ["StrategyOptimizer", "WalkForwardAnalyzer", "DEFAULT_SEARCH_SPACES", "optimize_strategy"]
