"""A-share execution subpackage — backtest, paper trading, and risk gate.

All models in this subpackage carry ``actionable=false`` and
``execution_signal="ResearchOnly"``.  No code here may place a real order.
"""

from __future__ import annotations

from .backtest_engine import BacktestEngine, BacktestResult
from .fee_model import AStockFeeConfig, calculate_fees
from .metrics import (
    calculate_max_drawdown,
    calculate_returns,
    calculate_sharpe,
    calculate_win_rate,
    summarize_metrics,
)
from .paper_trader import PaperTradeState, PaperTrader
from .risk_gate import RiskGate, RiskGateResult
from .strategy_base import MovingAverageTrendStrategy, StrategyBase

__all__ = [
    "StrategyBase",
    "MovingAverageTrendStrategy",
    "AStockFeeConfig",
    "calculate_fees",
    "BacktestEngine",
    "BacktestResult",
    "calculate_returns",
    "calculate_sharpe",
    "calculate_max_drawdown",
    "calculate_win_rate",
    "summarize_metrics",
    "PaperTradeState",
    "PaperTrader",
    "RiskGate",
    "RiskGateResult",
]
