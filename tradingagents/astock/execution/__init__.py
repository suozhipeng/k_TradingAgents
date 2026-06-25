"""A-share execution subpackage — backtest, paper trading, risk gate, and QMT bridge.

All models in this subpackage carry ``actionable=false`` and
``execution_signal=\"ResearchOnly\"`` unless the Phase 11 QMT execution
engine is explicitly configured.  No code here may place a real order
without going through the ``QmtExecutionEngine`` safety gates.
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
from .optimizer import StrategyOptimizer, optimize_strategy
from .paper_trader import PaperTradeState, PaperTrader
from .qmt_bridge import QmtBridge, QmtBridgeConfig
from .qmt_execution import ExecutionMode, QmtExecutionConfig, QmtExecutionEngine
from .risk_gate import (
    ATRStopLoss,
    RiskGate,
    RiskGateResult,
    RiskReasonCode,
    TrailingStop,
    calculate_atr,
)
from .kill_switch import KillSwitch, kill_switch
from .strategy_base import (
    BollingerBandsReversionStrategy,
    BullTrendStrategy,
    DefensiveMomentumStrategy,
    GridTradingStrategy,
    MACDTrendStrategy,
    MeanReversionStrategy,
    MovingAverageTrendStrategy,
    PutWriteStrategy,
    RSIRangeStrategy,
    StrategyBase,
    ValueAverageStrategy,
)

__all__ = [
    "StrategyBase",
    "MovingAverageTrendStrategy",
    "BullTrendStrategy",
    "ValueAverageStrategy",
    "MeanReversionStrategy",
    "RSIRangeStrategy",
    "DefensiveMomentumStrategy",
    "PutWriteStrategy",
    "MACDTrendStrategy",
    "BollingerBandsReversionStrategy",
    "GridTradingStrategy",
    "StrategyOptimizer",
    "optimize_strategy",
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
    "RiskReasonCode",
    "ATRStopLoss",
    "TrailingStop",
    "calculate_atr",
    "QmtBridge",
    "QmtBridgeConfig",
    "QmtExecutionConfig",
    "QmtExecutionEngine",
    "ExecutionMode",
    "KillSwitch",
    "kill_switch",
]
