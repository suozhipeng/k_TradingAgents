"""Phase 33-37 shared schemas — task, audit, research, order, and portfolio types.

This module collects schemas for:

- Phase 33: ``ResearchTask``, ``ResearchAudit``
- Phase 35: ``Order``, ``Fill``, ``Position``, ``Reconciliation``
- Phase 36: ``Portfolio``, ``RiskExposure``, ``Attribution``
- Phase 37: ``TaskRun``, ``AuditEvent``

These are Pydantic v2 models defined for Phase 30-38 readiness.
They are **standalone definitions** — not wired into runtime logic yet.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════
# Phase 33 — AI Research Center
# ═══════════════════════════════════════════════════════════════════════


class ResearchTaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResearchTask(BaseModel):
    """An AI research task — represents a single research execution.

    Attributes
    ----------
    task_id : str
        Unique task identifier.
    symbol : str
        Target stock symbol.
    mode : str
        Research mode (``"live_research"``, ``"deterministic"``).
    status : ResearchTaskStatus
        Current execution status.
    prompt_version : str
        LLM prompt version used.
    provider : str
        LLM provider name (e.g. ``"deepseek"``, ``"openai"``).
    model : str
        Model name used.
    snapshot : dict
        Input data snapshot at research time.
    result : dict or None
        Research output (set on completion).
    error : str or None
        Error message on failure.
    started_at : str or None
        ISO timestamp of start.
    finished_at : str or None
        ISO timestamp of completion.
    """

    task_id: str = ""
    symbol: str = ""
    mode: str = "live_research"
    status: ResearchTaskStatus = ResearchTaskStatus.QUEUED
    prompt_version: str = ""
    provider: str = ""
    model: str = ""
    snapshot: dict = Field(default_factory=dict)
    result: Optional[dict] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class ResearchAudit(BaseModel):
    """Audit trail for a single research output.

    Every AI conclusion is traceable to its model, prompt, input
    snapshot, and generation time.  The ``advisory`` flag must be
    ``True`` for all Phase 33 outputs.
    """

    audit_id: str = ""
    task_id: str = ""
    symbol: str = ""
    model: str = ""
    prompt_text: str = ""
    prompt_version: str = ""
    input_snapshot: dict = Field(default_factory=dict)
    output_summary: str = ""
    citations: list[str] = Field(default_factory=list)
    advisory: bool = True
    generated_at: str = ""


# ═══════════════════════════════════════════════════════════════════════
# Phase 35 — Trading Execution Control
# ═══════════════════════════════════════════════════════════════════════


class OrderStatus(str, Enum):
    CREATED = "created"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    PARTIAL_FILLED = "partial_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ERROR = "error"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderTradeMode(str, Enum):
    PAPER = "paper"
    MANAGED = "managed"
    LIVE_READY = "live-ready"


class Order(BaseModel):
    """A trade order.

    Compatible with both paper and managed execution modes.
    """

    order_id: str = ""
    broker_order_id: Optional[str] = None
    mode: OrderTradeMode = OrderTradeMode.PAPER
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    quantity: float = 0.0
    price: float = 0.0
    status: OrderStatus = OrderStatus.CREATED
    risk_status: str = "pending"
    confirmation_status: str = "not_required"
    audit_event_id: str = ""
    created_at: str = ""


class Fill(BaseModel):
    """A trade fill — may be partial."""

    fill_id: str = ""
    order_id: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    quantity: float = 0.0
    price: float = 0.0
    fees: float = 0.0
    timestamp: str = ""


class Position(BaseModel):
    """A trading position — shared by paper and managed modes."""

    symbol: str = ""
    quantity: float = 0.0
    avg_cost: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0


class Reconciliation(BaseModel):
    """Reconciliation between local state and broker/external report."""

    symbol: str = ""
    local_quantity: float = 0.0
    external_quantity: float = 0.0
    local_cost: float = 0.0
    external_cost: float = 0.0
    matched: bool = False
    discrepancy: float = 0.0
    notes: str = ""


# ═══════════════════════════════════════════════════════════════════════
# Phase 36 — Portfolio Risk & Attribution
# ═══════════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════════
# Phase 37 — Ops & Audit Center
# ═══════════════════════════════════════════════════════════════════════


class TaskType(str, Enum):
    DATA_REFRESH = "data_refresh"
    RESEARCH = "research"
    BACKTEST = "backtest"
    REPORT = "report"
    TRADE = "trade"


class TaskRun(BaseModel):
    """A generic task run — used for tracking all long-running operations."""

    task_id: str = ""
    task_type: TaskType = TaskType.DATA_REFRESH
    status: str = "queued"
    progress: float = 0.0
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[dict] = None
    result: Optional[dict] = None


class AuditEvent(BaseModel):
    """An auditable action event — covers all user/system actions."""

    event_id: str = ""
    actor: str = ""
    action: str = ""
    input_snapshot: dict = Field(default_factory=dict)
    output_snapshot: dict = Field(default_factory=dict)
    model: Optional[str] = None
    confirmation_required: bool = False
    confirmed_by: Optional[str] = None
    created_at: str = ""


__all__ = [
    # Phase 33
    "ResearchTaskStatus",
    "ResearchTask",
    "ResearchAudit",
    # Phase 35
    "OrderStatus",
    "OrderSide",
    "OrderTradeMode",
    "Order",
    "Fill",
    "Position",
    "Reconciliation",
    # Phase 36
    "Portfolio",
    "RiskExposure",
    "Attribution",
    # Phase 37
    "TaskType",
    "TaskRun",
    "AuditEvent",
]
