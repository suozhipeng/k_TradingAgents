"""Paper trading simulator for A-share strategies."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .fee_model import AStockFeeConfig, calculate_fees
from .risk_gate import RiskGate, RiskGateResult

EXECUTION_SIGNAL: str = "ResearchOnly"


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
    execution_signal: str = EXECUTION_SIGNAL
    decision_scope: str = "paper_trading_only"


class PaperTrader:
    """Simulated paper trading executor.

    Parameters
    ----------
    initial_cash : float
        Starting cash balance (default 100 000).
    fee_config : AStockFeeConfig or None
        Custom fee configuration.
    """

    def __init__(
        self,
        initial_cash: float = 100000.0,
        fee_config: AStockFeeConfig | None = None,
    ) -> None:
        self._state = PaperTradeState(
            positions={},
            cash=initial_cash,
            total_value=initial_cash,
            trades=[],
            pnl=0.0,
            last_updated=datetime.utcnow().isoformat(),
        )
        self._fee_config = fee_config or AStockFeeConfig()
        self._risk_gate = RiskGate()
        # Track cost basis per symbol for P&L computation
        self._cost_basis: dict[str, float] = {}

    def execute_cycle(
        self,
        signals: dict[str, float],
        prices: dict[str, float],
        *,
        risk_constraints: list[str] | None = None,
        position_cap_pct: float | None = None,
    ) -> PaperTradeState:
        """Execute one trading cycle from signal dict.

        Every trade record carries ``"actionable": false`` in its metadata.

        Parameters
        ----------
        signals : dict[str, float]
            ``symbol → signal`` where signal is ``1`` (buy), ``-1`` (sell),
            or ``0`` (hold).
        prices : dict[str, float]
            ``symbol → last price`` for trade execution.
        risk_constraints : list[str] or None
            Additional risk constraints forwarded to ``RiskGate``.
        position_cap_pct : float or None
            Position cap forwarded to ``RiskGate``.

        Returns
        -------
        PaperTradeState
            Updated state after this cycle.
        """
        for symbol, signal in signals.items():
            price = prices.get(symbol)
            if price is None or price <= 0:
                continue

            proposal: dict[str, Any] = {
                "symbol": symbol,
                "signal": signal,
                "actionable": False,
                "decision_scope": "paper_trading_only",
            }

            # Risk gate check
            gate_result = self._risk_gate.check(
                proposal=proposal,
                constraints=risk_constraints,
                position_cap_pct=position_cap_pct,
                current_position=self._state.positions,
            )

            if not gate_result.allowed:
                continue

            if signal == 1:
                self._execute_buy(symbol, price)
            elif signal == -1:
                self._execute_sell(symbol, price)
            # signal == 0 → skip

        # Mark-to-market
        total_position_value = 0.0
        for sym, shs in self._state.positions.items():
            mkt_price = prices.get(sym, 0.0)
            total_position_value += shs * mkt_price

        self._state.total_value = round(self._state.cash + total_position_value, 2)
        self._state.last_updated = datetime.utcnow().isoformat()
        return self._state

    def _execute_buy(self, symbol: str, price: float) -> None:
        """Execute a buy trade with all available cash."""
        cash = self._state.cash
        if cash <= 0:
            return

        # Calculate max affordable shares after accounting for fees (iterative)
        shares = cash / price
        for _ in range(3):  # converge in a few iterations
            fees = calculate_fees(price, shares, is_buy=True, config=self._fee_config)
            total_cost = shares * price + fees["total"]
            if total_cost <= cash:
                break
            # Scale down proportionally
            shares *= cash / total_cost

        # Final computation
        fees = calculate_fees(price, shares, is_buy=True, config=self._fee_config)
        total_cost = shares * price + fees["total"]

        # If still over budget after convergence, clamp
        if total_cost > cash:
            shares *= cash / total_cost
            fees = calculate_fees(price, shares, is_buy=True, config=self._fee_config)
            total_cost = shares * price + fees["total"]

        self._state.cash = round(self._state.cash - total_cost, 2)
        self._state.positions[symbol] = round(
            self._state.positions.get(symbol, 0.0) + shares, 4
        )
        # Track cost basis
        old_basis = self._cost_basis.get(symbol, 0.0)
        old_shares = self._state.positions.get(symbol, 0.0) - shares  # before adding
        if old_shares > 0:
            self._cost_basis[symbol] = old_basis + total_cost
        else:
            self._cost_basis[symbol] = total_cost

        self._state.trades.append({
            "symbol": symbol,
            "type": "buy",
            "price": price,
            "shares": round(shares, 4),
            "fees": fees["total"],
            "actionable": False,
            "decision_scope": "paper_trading_only",
            "timestamp": datetime.utcnow().isoformat(),
        })

    def _execute_sell(self, symbol: str, price: float) -> None:
        """Execute a sell trade (liquidate entire position)."""
        shares = self._state.positions.get(symbol, 0.0)
        if shares <= 0:
            return
        sell_value = shares * price
        fees = calculate_fees(price, shares, is_buy=False, config=self._fee_config)
        proceeds = sell_value - fees["total"]

        # Cost basis: total amount spent to acquire these shares
        cost_basis = self._cost_basis.pop(symbol, 0.0)
        trade_pnl = proceeds - cost_basis

        self._state.cash = round(self._state.cash + proceeds, 2)
        self._state.pnl = round(self._state.pnl + trade_pnl, 2)
        del self._state.positions[symbol]
        self._state.trades.append({
            "symbol": symbol,
            "type": "sell",
            "price": price,
            "shares": round(shares, 4),
            "fees": fees["total"],
            "pnl": round(trade_pnl, 2),
            "actionable": False,
            "decision_scope": "paper_trading_only",
            "timestamp": datetime.utcnow().isoformat(),
        })

    def get_state(self) -> PaperTradeState:
        """Return a copy of the current portfolio state."""
        return self._state.model_copy(deep=True)
