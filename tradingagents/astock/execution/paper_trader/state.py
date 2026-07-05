"""Paper trading state models.

Phase 11 extension
------------------
The ``PaperTradeState`` carries the execution signal constant
``"ResearchOnly"`` so that all state instances carry
``execution_signal="ResearchOnly"`` and ``decision_scope="paper_trading_only"``
unless explicitly changed.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

_EXECUTION_SIGNAL: str = "ResearchOnly"


class PaperTradeState(BaseModel):
    """Current state of the paper trading portfolio.

    Attributes
    ----------
    positions : dict[str, float]
        Map of symbol → shares held.
    cash : float
        Remaining cash balance.
    total_value : float
        Total portfolio value (cash + positions at last mark).
    trades : list[dict]
        Historical trade records.
    pnl : float
        Realised P&L.
    last_updated : str
        ISO-formatted timestamp of last update.
    execution_signal : str
        Always ``"ResearchOnly"``.
    """

    positions: dict[str, float] = Field(default_factory=dict)
    cash: float = 0.0
    total_value: float = 0.0
    trades: list[dict] = Field(default_factory=list)
    pnl: float = 0.0
    last_updated: str = ""
    execution_signal: str = _EXECUTION_SIGNAL
    decision_scope: str = "paper_trading_only"
