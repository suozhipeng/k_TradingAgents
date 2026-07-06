"""A-share execution subpackage — backtest, paper trading, risk gate, and QMT bridge.

All models in this subpackage carry ``actionable=false`` and
``execution_signal=\"ResearchOnly\"`` unless the Phase 11 QMT execution
engine is explicitly configured.  No code here may place a real order
without going through the ``QmtExecutionEngine`` safety gates.

Structure (v2.4 decoupling)
---------------------------
- ``backtest/`` — engine, fee models, metrics
- ``strategies/`` — concrete strategy implementations + schemas
- ``infrastructure/`` — EventBus, KillSwitch, StrategyRegistry
- ``backtest_engine/`` — legacy alias (deprecated, use ``backtest/``)
- ``paper_trader/`` — paper trading engine
- ``qmt_bridge/``, ``qmt_execution/`` — QMT integration
- ``risk_gate/`` — risk management gates
- ``scheduler/`` — APScheduler integration
- ``batch_backtest/`` — batch backtest runner
- ``optimizer/`` — strategy optimizer
- ``portfolio_risk/`` — VaR, industry exposure, attribution
- ``strategy_base/`` — base classes and strategy definitions

Backward-compatible re-exports are maintained so existing imports continue to work.
"""

from __future__ import annotations

# Backward-compatible re-exports from new locations
from .backtest import (  # noqa: F401
    AStockFeeConfig,
    calculate_fees,
    calculate_max_drawdown,
    calculate_returns,
    calculate_sharpe,
    calculate_win_rate,
    summarize_metrics,
)
from .backtest_engine import BacktestEngine, BacktestResult, BacktestDataAssumption  # noqa: F401
from .infrastructure import (  # noqa: F401
    KillSwitch,
    kill_switch,
    StrategyRegistryEntry,
    get_registry,
    get_strategy,
    list_strategies,
    register,
    EventBus,
)
from .strategies.schemas import LeaderPoolEntry  # noqa: F401
from .optimizer import StrategyOptimizer, WalkForwardAnalyzer, optimize_strategy  # noqa: F401
from .paper_trader import PaperTradeState, PaperTrader  # noqa: F401
from .portfolio_risk import (  # noqa: F401
    calculate_var,
    calculate_industry_exposure,
    calculate_attribution,
    calculate_risk_exposure,
)
from .qmt_bridge import QmtBridge, QmtBridgeConfig  # noqa: F401
from .qmt_execution import ExecutionMode, QmtExecutionConfig, QmtExecutionEngine  # noqa: F401
from .risk_gate import (  # noqa: F401
    ATRStopLoss,
    RiskGate,
    RiskGateResult,
    RiskReasonCode,
    TrailingStop,
    calculate_atr,
)
from .strategy_base import (  # noqa: F401
    BollingerBandsReversionStrategy,
    BullTrendStrategy,
    DefensiveMomentumStrategy,
    GridTradingStrategy,
    MACDTrendStrategy,
    MeanReversionStrategy,
    MomentumRotationStrategy,
    MovingAverageTrendStrategy,
    PortfolioStrategyBase,
    PutWriteStrategy,
    RSIRangeStrategy,
    StockFlow,
    StrategyBase,
    ValueAverageStrategy,
)
from .strategies import (  # noqa: F401
    get_leading_stocks,
    refresh_leading_stocks,
    run_momentum_rotation,
    BENCHMARK_SYMBOL,
    BENCHMARK_NAME,
    LEADING_STOCKS,
    MomentumRotationResult,
)

__all__ = [
    "StrategyBase",
    "PortfolioStrategyBase",
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
    "MomentumRotationStrategy",
    "StockFlow",
    "WalkForwardAnalyzer",
    "StrategyOptimizer",
    "optimize_strategy",
    "AStockFeeConfig",
    "calculate_fees",
    "BacktestEngine",
    "BacktestResult",
    "BacktestDataAssumption",
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
    "calculate_var",
    "calculate_industry_exposure",
    "calculate_attribution",
    "calculate_risk_exposure",
    "StrategyRegistryEntry",
    "get_registry",
    "get_strategy",
    "list_strategies",
    "register",
    "LeaderPoolEntry",
    "EventBus",
    "get_leading_stocks",
    "refresh_leading_stocks",
    "run_momentum_rotation",
    "BENCHMARK_SYMBOL",
    "BENCHMARK_NAME",
    "LEADING_STOCKS",
    "MomentumRotationResult",
]
