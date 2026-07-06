"""QMT integration for PaperTrader.

Phase 11 extension
------------------
Provides ``set_qmt_engine`` and ``execute_with_qmt`` methods that route
signals through the QMT controlled-execution layer when an engine is
injected.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..backtest.fee_model import AStockFeeConfig, calculate_fees
from ..qmt_execution import QmtExecutionEngine
from ..risk_gate import RiskGate
from ...schemas.trading_execution import (
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    OrderTradeMode,
)
from .state import PaperTradeState


class QmtIntegrationMixin:
    """Mixin providing QMT execution integration for PaperTrader.

    This mixin adds QMT-specific methods without duplicating the core
    paper trading logic.
    """

    def set_qmt_engine(self, engine: QmtExecutionEngine) -> None:
        """Inject a QMT execution engine at runtime.

        Parameters
        ----------
        engine : QmtExecutionEngine
            The controlled execution engine to use for order placement.
        """
        self._qmt_engine = engine

    @property
    def qmt_execution_engine(self) -> QmtExecutionEngine | None:
        """Return the injected QMT execution engine, if any."""
        return self._qmt_engine

    def execute_with_qmt(
        self,
        signal: dict[str, Any],
        price: float,
        volume: int,
        *,
        confirmed: bool = False,
    ) -> dict[str, Any]:
        """Execute a signal through the QMT execution engine if available.

        Falls back to virtual (in-process) execution when no engine is
        injected.

        Parameters
        ----------
        signal : dict
            Signal dict with ``"symbol"`` and ``"signal"``.
        price : float
            Execution price.
        volume : int
            Number of shares.
        confirmed : bool
            Human confirmation flag (required in SAFETY mode).

        Returns
        -------
        dict
            Execution result.
        """
        if self._qmt_engine is not None:
            return self._qmt_engine.execute(signal, price, volume, confirmed=confirmed)

        # Fallback: traditional virtual execution
        symbol = signal.get("symbol", "")
        signal_value = signal.get("signal", 0)

        if signal_value == 1:
            self._execute_buy(symbol, price)
        elif signal_value == -1:
            self._execute_sell(symbol, price)

        return {
            "filled": signal_value != 0,
            "symbol": symbol,
            "price": price,
            "mode": "paper_fallback",
        }
