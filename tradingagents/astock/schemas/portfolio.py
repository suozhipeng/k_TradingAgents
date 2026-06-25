"""Phase 36 — Portfolio Risk & Attribution schemas.

- ``Portfolio`` — portfolio-level summary
- ``RiskExposure`` — risk exposure metrics
- ``Attribution`` — performance attribution breakdown
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .trading_execution import Position


class Portfolio(BaseModel):
    """Portfolio-level summary."""

    portfolio_id: str = ""
    holdings: list[Position] = Field(default_factory=list)
    cash: float = 0.0
    nav: float = 0.0
    pnl_total: float = 0.0
    last_updated: str = ""


class RiskExposure(BaseModel):
    """Risk exposure metrics for a portfolio."""

    industry_concentration: float = 0.0
    top_holding_pct: float = 0.0
    beta: float = 0.0
    liquidity_score: float = 0.0
    var_95: float = 0.0
    max_drawdown: float = 0.0
    stress_loss_pct: float = 0.0


class Attribution(BaseModel):
    """Performance attribution breakdown."""

    benchmark_return: float = 0.0
    selection_effect: float = 0.0
    timing_effect: float = 0.0
    cost_impact: float = 0.0
    slippage_impact: float = 0.0
    residual: float = 0.0


__all__ = [
    "Portfolio",
    "RiskExposure",
    "Attribution",
]
