"""Backtest engine models for A-share strategies.

Uses ``AStockDataFacade`` for real data when available, falling back
to deterministic mock OHLCV data for testability.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

EXECUTION_SIGNAL: str = "ResearchOnly"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AdjustmentMethod(str, Enum):
    """复权方法"""
    NONE = "none"          # 未复权
    FORWARD = "forward"    # 前复权
    BACKWARD = "backward"  # 后复权


class CostModel(str, Enum):
    """成本模型"""
    DEFAULT = "default"       # 默认（千分之一印花税 + 万分之一佣金）
    CUSTOM = "custom"         # 自定义费率
    ZERO = "zero"             # 零成本（仅 mock/测试）


class SettlementConstraint(str, Enum):
    """成交约束"""
    T_PLUS_0 = "t+0"        # T+0
    T_PLUS_1 = "t+1"        # T+1（A 股默认）
    T_PLUS_0_TREASURY = "t+0_treasury"  # T+0 国债


# ---------------------------------------------------------------------------
# BacktestDataAssumption
# ---------------------------------------------------------------------------


class BacktestDataAssumption(BaseModel):
    """回测数据假设 — 说明回测使用的数据配置和约束。

    Attributes
    ----------
    adjustment : AdjustmentMethod
        复权方法（默认 forward）。
    cost_model : CostModel
        成本模型（默认 default）。
    settlement : SettlementConstraint
        成交约束（默认 t+1）。
    slippage_bps : float
        滑点（基点，默认 0 = 无滑点）。
    sample_out : bool
        是否使用样本外数据（默认 False）。
    data_source : str
        数据来源描述（如 ``"duckdb_live"``, ``"mock_deterministic"``）。
    data_quality : str
        数据质量标签（如 ``"normal"``, ``"mock"``, ``"partial"``）。
    survivorship_bias_risk : bool
        是否存在幸存者偏差风险（默认 False）。
    look_ahead_bias_risk : bool
        是否存在前视偏差风险（默认 False）。
    notes : list[str]
        额外的假设说明。
    """

    adjustment: AdjustmentMethod = AdjustmentMethod.FORWARD
    cost_model: CostModel = CostModel.DEFAULT
    settlement: SettlementConstraint = SettlementConstraint.T_PLUS_1
    slippage_bps: float = 0.0
    sample_out: bool = False
    data_source: str = ""
    data_quality: str = "normal"
    survivorship_bias_risk: bool = False
    look_ahead_bias_risk: bool = False
    volume_cap_pct: float = Field(
        default=25.0,
        description="成交量容量约束：单笔交易量不超过当日成交量的百分比。0=不限制。",
    )
    price_limit_check: bool = Field(
        default=True,
        description="是否启用涨跌停价格约束（默认开启）。",
    )
    suspension_check: bool = Field(
        default=True,
        description="是否启用停牌不可成交约束（默认开启）。",
    )
    st_stock: bool = Field(
        default=False,
        description="是否为 ST/*ST 股票（5% 涨跌幅限制）。",
    )
    delisted: bool = Field(
        default=False,
        description="是否为已退市股票（数据截断点标记）。",
    )
    notes: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "adjustment": self.adjustment.value,
            "cost_model": self.cost_model.value,
            "settlement": self.settlement.value,
            "slippage_bps": self.slippage_bps,
            "sample_out": self.sample_out,
            "data_source": self.data_source,
            "data_quality": self.data_quality,
            "survivorship_bias_risk": self.survivorship_bias_risk,
            "look_ahead_bias_risk": self.look_ahead_bias_risk,
            "volume_cap_pct": self.volume_cap_pct,
            "price_limit_check": self.price_limit_check,
            "suspension_check": self.suspension_check,
            "st_stock": self.st_stock,
            "delisted": self.delisted,
            "notes": list(self.notes),
        }

    @classmethod
    def mock(cls) -> BacktestDataAssumption:
        """Pre-built mock/test assumption."""
        return cls(
            adjustment=AdjustmentMethod.FORWARD,
            cost_model=CostModel.ZERO,
            settlement=SettlementConstraint.T_PLUS_1,
            slippage_bps=0.0,
            sample_out=False,
            data_source="mock_deterministic",
            data_quality="mock",
            survivorship_bias_risk=True,
            look_ahead_bias_risk=False,
            notes=["Mock data — not suitable for live decisions"],
        )


# ---------------------------------------------------------------------------
# BacktestResult model
# ---------------------------------------------------------------------------


class BacktestResult(BaseModel):
    """Result of a completed backtest run.

    Attributes
    ----------
    symbol : str
    strategy_name : str
    start_date : str
    end_date : str
    total_return : float
    annualized_return : float
    sharpe_ratio : float
    max_drawdown : float
    win_rate : float
    total_trades : int
    periods : list[dict]
        Per-period account snapshots (beginning portfolio value, signal,
        trade, ending value, fees).
    fee_config_used : dict
        Snapshot of the fee config used.
    execution_signal : str
        Always ``"ResearchOnly"``.
    """

    symbol: str
    strategy_name: str = ""
    start_date: str
    end_date: str
    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    trades: list[dict] = Field(default_factory=list)
    periods: list[dict] = Field(default_factory=list)
    fee_config_used: dict = Field(default_factory=dict)
    execution_signal: str = EXECUTION_SIGNAL
    decision_scope: str = "backtest_only"
    run_id: str = ""
    data_assumption: dict = Field(default_factory=dict)
    data_lineage: dict = Field(default_factory=dict)
    reproducibility: dict = Field(default_factory=dict)
    benchmark_symbol: str = ""
    benchmark_return: float = 0.0
    benchmark_max_drawdown: float = 0.0
    alpha: float = 0.0
    beta: float = 0.0
    cost_breakdown: dict = Field(
        default_factory=lambda: {
            "total_fees": 0.0,
            "commission": 0.0,
            "stamp_tax": 0.0,
            "slippage": 0.0,
        },
        description="Cost breakdown summed from all trades: total_fees, commission, stamp_tax, slippage.",
    )
