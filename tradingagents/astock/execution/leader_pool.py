"""Phase 34 — Market Leaders candidate pool schema."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any, Optional


class LeaderPoolEntry(BaseModel):
    """A single candidate in the market leaders candidate pool.

    Attributes
    ----------
    symbol : str
        Stock symbol.
    name : str
        Stock name.
    reason : str
        Why this stock entered the pool (e.g. ``"dragon_tiger"``, ``"momentum_top"``,
        ``"northbound_inflow"``, ``"sector_leader"``).
    score : float
        Composite score (0.0–100.0).
    source : str
        Data source (``"eastmoney"``, ``"sina"``, ``"mock"``, etc.).
    refreshed_at : str
        ISO timestamp of last refresh.
    entry_reason : str
        Detailed entry rationale.
    exit_reason : str or None
        Exit rationale if no longer in pool.
    """

    symbol: str = ""
    name: str = ""
    reason: str = ""
    score: float = 0.0
    source: str = ""
    refreshed_at: str = ""
    entry_reason: str = ""
    exit_reason: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "LeaderPoolEntry",
]
