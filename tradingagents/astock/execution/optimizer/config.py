"""Configuration, scoring, and search-space defaults for strategy optimization."""

from __future__ import annotations

import logging
from typing import Any

from ..backtest_engine import BacktestEngine
from ..strategy_base import StrategyBase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default search spaces for each strategy
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
    "MomentumRotation": {
        "n": [10, 20, 30],
        "k": [5, 10, 20],
        "l": [3, 5, 8],
    },
}

DEFAULT_STRATEGY_NAME_TO_CLASS: dict[str, type[StrategyBase]] = {}


def _get_strategy_map() -> dict[str, type[StrategyBase]]:
    """Lazy-populate and return the strategy name-to-class mapping."""
    if DEFAULT_STRATEGY_NAME_TO_CLASS:
        return DEFAULT_STRATEGY_NAME_TO_CLASS
    from ..strategy_base import (  # noqa: F401
        BollingerBandsReversionStrategy,
        BullTrendStrategy,
        DefensiveMomentumStrategy,
        GridTradingStrategy,
        MACDTrendStrategy,
        MeanReversionStrategy,
        MomentumRotationStrategy,
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
        "MomentumRotation": MomentumRotationStrategy,
    }
    DEFAULT_STRATEGY_NAME_TO_CLASS.update(mapping)
    return DEFAULT_STRATEGY_NAME_TO_CLASS


def _get_default_search_space(name: str) -> dict[str, list[Any]]:
    """Return the default search space for *name*, or empty dict if unknown."""
    return dict(DEFAULT_SEARCH_SPACES.get(name, {}))


def _composite_score(metrics: dict[str, Any]) -> float:
    """Composite score in [-1, 1] for ranking parameter sets.

    Higher is better.  Combines Sharpe, return, drawdown penalty, and
    trade count bonus using a simple weighted formula.
    Treats None/NaN metrics as 0.
    """
    sharpe = metrics.get("sharpe_ratio", 0.0) or 0.0
    total_return = metrics.get("total_return", 0.0) or 0.0
    max_dd = metrics.get("max_drawdown", 0.0) or 0.0
    total_trades = metrics.get("total_trades", 0) or 0

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


def optimize_strategy(
    strategy_name: str,
    symbol: str,
    start_date: str,
    end_date: str,
    param_grid: dict[str, list[Any]] | None = None,
    *,
    top_n: int = 5,
    engine: BacktestEngine | None = None,
) -> list[dict[str, Any]]:
    """Convenience wrapper — create an optimizer and run it in one call."""
    from .optimizer import StrategyOptimizer

    optimizer = StrategyOptimizer(strategy_name, engine=engine)
    return optimizer.optimize(symbol, start_date, end_date, param_grid, top_n=top_n)
