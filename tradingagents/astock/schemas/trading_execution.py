"""Phase 35 — Trading Execution Control schemas.

- ``OrderStatus``, ``OrderSide``, ``OrderTradeMode`` — order enums
- ``Order`` — a trade order
- ``Fill`` — a trade fill (may be partial)
- ``Position`` — a trading position
- ``Reconciliation`` — local vs broker state comparison
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


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
    """A trade order — compatible with both paper and managed execution modes."""

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


__all__ = [
    "OrderStatus",
    "OrderSide",
    "OrderTradeMode",
    "Order",
    "Fill",
    "Position",
    "Reconciliation",
]
