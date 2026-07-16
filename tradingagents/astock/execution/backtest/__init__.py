"""Backtest core: engine, fee models, and metrics."""

from __future__ import annotations

# Backward-compatible re-exports
from tradingagents.astock.execution.backtest.fee_model import AStockFeeConfig, calculate_fees  # noqa: F401
from tradingagents.astock.execution.backtest.metrics import calculate_returns, calculate_sharpe, calculate_max_drawdown, calculate_win_rate, summarize_metrics  # noqa: F401

__all__ = [
    "AStockFeeConfig",
    "calculate_fees",
    "calculate_returns",
    "calculate_sharpe",
    "calculate_max_drawdown",
    "calculate_win_rate",
    "summarize_metrics",
]
