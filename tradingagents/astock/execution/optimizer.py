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

from __future__ import annotations

import copy
import itertools
import logging
from typing import Any

from .backtest_engine import BacktestEngine
from .strategy_base import StrategyBase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default search spaces for each strategy
# Int / float ranges: define which parameter values to try.
# Keys that are not listed keep their default from the strategy __init__.
# ---------------------------------------------------------------------------

DEFAULT_SEARCH_SPACES: dict[str, dict[str, list[Any]]] = {
    "MovingAverageTrend": {
        "fast_period": [5, 10, 15, 20],
        "slow_period": [20, 30, 50, 60],
    },
    "BullTrend": {
        "fast_ma": [5, 10],
        "mid_ma": [20, 30],
        "slow_ma": [60, 80],
        "volume_ratio": [1.0, 1.5, 2.0],
    },
    "ValueAverage": {
        "pe_low_pct": [20, 30, 40],
        "pe_high_pct": [60, 70, 80],
    },
    "MeanReversion": {
        "std_multiplier": [1.5, 2.0, 2.5, 3.0],
        "ma_period": [10, 20, 30],
    },
    "RSIRange": {
        "rsi_period": [7, 14, 21],
        "oversold": [20, 25, 30],
        "overbought": [70, 75, 80],
    },
    "DefensiveMomentum": {
        "roc_period": [10, 20, 30],
        "vol_threshold": [0.015, 0.02, 0.03],
    },
    "PutWrite": {
        "fast_ma": [5, 10],
        "mid_ma": [20, 30],
        "slow_ma": [60, 80],
    },
    "MACDTrend": {
        "fast_period": [8, 12, 16],
        "slow_period": [20, 26, 32],
        "signal_period": [5, 9, 14],
    },
    "BollingerBands": {
        "ma_period": [10, 20, 30],
        "num_std": [1.5, 2.0, 2.5, 3.0],
    },
    "GridTrading": {
        "grid_levels": [3, 5, 8],
        "grid_spacing": [0.02, 0.03, 0.05],
    },
}

DEFAULT_STRATEGY_NAME_TO_CLASS: dict[str, type[StrategyBase]] = {}

# Lazy registry populated on first access


def _get_strategy_map() -> dict[str, type[StrategyBase]]:
    if DEFAULT_STRATEGY_NAME_TO_CLASS:
        return DEFAULT_STRATEGY_NAME_TO_CLASS
    from .strategy_base import (  # noqa: F401
        BollingerBandsReversionStrategy,
        BullTrendStrategy,
        DefensiveMomentumStrategy,
        GridTradingStrategy,
        MACDTrendStrategy,
        MeanReversionStrategy,
        MovingAverageTrendStrategy,
        PutWriteStrategy,
        RSIRangeStrategy,
        ValueAverageStrategy,
    )

    mapping = {
        "MovingAverageTrend": MovingAverageTrendStrategy,
        "BullTrend": BullTrendStrategy,
        "ValueAverage": ValueAverageStrategy,
        "MeanReversion": MeanReversionStrategy,
        "RSIRange": RSIRangeStrategy,
        "DefensiveMomentum": DefensiveMomentumStrategy,
        "PutWrite": PutWriteStrategy,
        "MACDTrend": MACDTrendStrategy,
        "BollingerBands": BollingerBandsReversionStrategy,
        "GridTrading": GridTradingStrategy,
    }
    DEFAULT_STRATEGY_NAME_TO_CLASS.update(mapping)
    return DEFAULT_STRATEGY_NAME_TO_CLASS


def _get_default_search_space(name: str) -> dict[str, list[Any]]:
    """Return the default search space for *name*, or empty dict if unknown."""
    return dict(DEFAULT_SEARCH_SPACES.get(name, {}))


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _composite_score(metrics: dict[str, Any]) -> float:
    """Composite score in [-1, 1] for ranking parameter sets.

    Higher is better.  Combines Sharpe, return, drawdown penalty, and
    trade count bonus using a simple weighted formula.
    """
    sharpe = metrics.get("sharpe_ratio", 0.0)
    total_return = metrics.get("total_return", 0.0)
    max_dd = metrics.get("max_drawdown", 0.0)
    total_trades = metrics.get("total_trades", 0)

    # Sharpe contribution (bounded)
    sharpe_score = max(min(sharpe / 3.0, 1.0), -1.0)

    # Return contribution (bounded)
    return_score = max(min(total_return * 2.0, 1.0), -1.0) if total_return > 0 else max(total_return, -1.0)

    # Drawdown penalty (0 → no penalty, 0.5+ → heavy penalty)
    dd_penalty = min(max_dd * 2.0, 1.0)

    # Trade count bonus (avoid zero-trade scenarios)
    trade_bonus = min(total_trades / 50.0, 0.2)

    score = (
        0.35 * sharpe_score
        + 0.30 * return_score
        - 0.25 * dd_penalty
        + 0.10 * trade_bonus
    )
    return round(score, 4)


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------


class StrategyOptimizer:
    """Grid-search parameter optimizer for backtest strategies.

    Parameters
    ----------
    strategy_cls : type[StrategyBase] or str
        Strategy class or registered name (e.g. ``"MACDTrend"``).
    engine : BacktestEngine or None
        Backtest engine instance.  Created fresh if omitted.
    rebalance_freq : str
        Rebalance frequency passed to ``BacktestEngine.run``.
    initial_cash : float
        Starting capital passed to ``BacktestEngine.run``.
    """

    def __init__(
        self,
        strategy_cls: type[StrategyBase] | str,
        engine: BacktestEngine | None = None,
        rebalance_freq: str = "M",
        initial_cash: float = 100000.0,
    ) -> None:
        if isinstance(strategy_cls, str):
            mapping = _get_strategy_map()
            resolved = mapping.get(strategy_cls)
            if resolved is None:
                raise ValueError(
                    f"Unknown strategy name {strategy_cls!r}. "
                    f"Available: {list(mapping)}"
                )
            strategy_cls = resolved
        self.strategy_cls: type[StrategyBase] = strategy_cls
        self.engine = engine or BacktestEngine()
        self.rebalance_freq = rebalance_freq
        self.initial_cash = initial_cash

    def optimize(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        param_grid: dict[str, list[Any]] | None = None,
        *,
        top_n: int = 5,
        metric: str = "composite",
        progress_callback: Any = None,
    ) -> list[dict[str, Any]]:
        """Run grid search over *param_grid* and return top-N results.

        Parameters
        ----------
        symbol : str
            A-share symbol.
        start_date, end_date : str
            Backtest date range.
        param_grid : dict or None
            Parameter search space: ``{param_name: [values]``.
            Uses ``DEFAULT_SEARCH_SPACES`` when ``None``.
        top_n : int
            Number of top results to return (default 5).
        metric : str
            Scoring metric.  ``"composite"`` (default) uses ``_composite_score``.
            ``"sharpe"``, ``"total_return"`` also accepted.
        progress_callback : callable or None
            ``fn(current, total, params)`` called after each trial.

        Returns
        -------
        list[dict]
            Each entry: ``{"rank", "params", "metrics", "score"}``,
            sorted best-first.
        """
        if param_grid is None:
            # Auto-detect from default search space
            name = self.strategy_cls.__name__.replace("Strategy", "")
            param_grid = _get_default_search_space(name)

        if not param_grid:
            # No search space defined — run with defaults only
            result = self._run_trial(symbol, start_date, end_date, {})
            if result is None:
                return []
            return [{"rank": 1, "params": {}, **result}]

        # Build all parameter combinations
        keys = list(param_grid.keys())
        value_lists = [param_grid[k] for k in keys]
        combinations = list(itertools.product(*value_lists))
        total = len(combinations)

        results: list[dict[str, Any]] = []
        for idx, combo in enumerate(combinations):
            params = dict(zip(keys, combo))
            trial_result = self._run_trial(symbol, start_date, end_date, params)
            if progress_callback:
                progress_callback(idx + 1, total, params)
            if trial_result is None:
                continue
            trial_result["params"] = params
            trial_result["score"] = _composite_score(trial_result["metrics"])
            results.append(trial_result)

        if not results:
            return []

        # Sort by score descending
        results.sort(key=lambda r: r["score"], reverse=True)

        # Rank and return top-N
        for i, r in enumerate(results[:top_n]):
            r["rank"] = i + 1

        return results[:top_n]

    def _run_trial(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        params: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Run a single backtest trial with *params*."""
        try:
            strategy = self.strategy_cls(params)
            result = self.engine.run(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                strategy=strategy,
                rebalance_freq=self.rebalance_freq,
                initial_cash=self.initial_cash,
            )
            return {
                "metrics": {
                    "total_return": result.total_return,
                    "annualized_return": result.annualized_return,
                    "sharpe_ratio": result.sharpe_ratio,
                    "max_drawdown": result.max_drawdown,
                    "win_rate": result.win_rate,
                    "total_trades": result.total_trades,
                },
            }
        except Exception as exc:
            logger.debug("Trial failed for params %s: %s", params, exc)
            return None


def optimize_strategy(
    strategy_name: str,
    symbol: str,
    start_date: str,
    end_date: str,
    param_grid: dict[str, list[Any]] | None = None,
    *,
    top_n: int = 5,
) -> list[dict[str, Any]]:
    """Convenience wrapper — create an optimizer and run it in one call."""
    optimizer = StrategyOptimizer(strategy_name)
    return optimizer.optimize(symbol, start_date, end_date, param_grid, top_n=top_n)
