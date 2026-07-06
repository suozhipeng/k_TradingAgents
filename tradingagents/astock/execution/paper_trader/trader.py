"""Paper trading simulator for A-share strategies.

Phase 11 extension
------------------
The ``PaperTrader`` now optionally supports a ``QmtExecutionEngine`` for
real (or mock) order placement via the QMT bridge.  When an engine is
injected, the ``execute_with_qmt`` method routes signals through the
QMT controlled-execution layer instead of the simulated in-process
execution.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from ..backtest.fee_model import AStockFeeConfig, calculate_fees
from ..qmt_execution import QmtExecutionEngine
from ..risk_gate import RiskGate, RiskGateResult
from ...schemas.trading_execution import (
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    OrderTradeMode,
)
from .state import PaperTradeState
from .qmt_integration import QmtIntegrationMixin

_EXECUTION_SIGNAL: str = "ResearchOnly"


class PaperTrader(QmtIntegrationMixin):
    """Simulated paper trading executor.

    Parameters
    ----------
    initial_cash : float
        Starting cash balance (default 100 000).
    fee_config : AStockFeeConfig or None
        Custom fee configuration.
    qmt_execution_engine : QmtExecutionEngine or None
        Optional QMT execution engine for real/mock order placement.
    """

    def __init__(
        self,
        initial_cash: float = 100000.0,
        fee_config: AStockFeeConfig | None = None,
        qmt_execution_engine: QmtExecutionEngine | None = None,
        t_plus_1: bool = False,
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
        # T+1 settlement: purchase date per symbol (YYYY-MM-DD)
        self._purchase_dates: dict[str, str] = {}
        self._t_plus_1 = t_plus_1
        # Phase 11: optional QMT execution engine
        self._qmt_engine: QmtExecutionEngine | None = qmt_execution_engine

    # -- Standard paper trading (unchanged from Phase 10) -------------------

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

        # Record purchase date for T+1 settlement check
        if self._t_plus_1:
            self._purchase_dates[symbol] = datetime.utcnow().strftime("%Y-%m-%d")

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

    def _check_t_plus_1(self, symbol: str) -> bool:
        """Check T+1 settlement: return True if sell is allowed (not same day).

        Only enforced when ``t_plus_1=True`` was passed at construction.
        """
        if not self._t_plus_1:
            return True
        today = datetime.utcnow().strftime("%Y-%m-%d")
        purchase_date = self._purchase_dates.get(symbol)
        return purchase_date is None or purchase_date != today

    def _execute_sell(self, symbol: str, price: float) -> None:
        """Execute a sell trade (liquidate entire position).

        Blocked if T+1 settlement constraint is active (same-day sell).
        """
        if not self._check_t_plus_1(symbol):
            return
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

    # -- Public accessors for portfolio risk (Phase 36) --------------------

    def cost_basis(self, symbol: str) -> float:
        """Return the total cost basis for *symbol* (public accessor)."""
        return self._cost_basis.get(symbol, 0.0)

    def current_value(self, symbol: str) -> float:
        """Return the estimated current per-share price for *symbol*.

        Falls back to ``avg_cost`` when no live price is available.
        """
        shares = self._state.positions.get(symbol, 0)
        cost = self._cost_basis.get(symbol, 0.0)
        return round(cost / shares, 2) if shares > 0 else 0.0

    # -- Individual order placement (WebUI trading page) --------------------

    def place_order(
        self,
        symbol: str,
        side: str,
        price: float,
        quantity: int,
    ) -> Order:
        """Place an individual order with specified quantity.

        Parameters
        ----------
        symbol : str
            Stock symbol (e.g. ``"600519.SH"``).
        side : str
            ``"buy"`` or ``"sell"``.
        price : float
            Limit / market price per share.
        quantity : int
            Number of shares to buy or sell.

        Returns
        -------
        Order
            Order with status and embedded Fill(s).

        Raises
        ------
        ValueError
            Invalid side or insufficient cash/position.
        """
        side = side.lower().strip()
        if side not in ("buy", "sell"):
            raise ValueError(f"Invalid side: {side!r}; expected 'buy' or 'sell'")
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if price <= 0:
            raise ValueError("price must be positive")

        if side == "buy":
            return self._place_buy_order(symbol, price, quantity)
        else:
            return self._place_sell_order(symbol, price, quantity)

    def _place_buy_order(self, symbol: str, price: float, quantity: int) -> Order:
        fees = calculate_fees(price, quantity, is_buy=True, config=self._fee_config)
        total_cost = quantity * price + fees["total"]

        if total_cost > self._state.cash:
            raise ValueError(
                f"Insufficient cash: need ¥{total_cost:,.2f} but have ¥{self._state.cash:,.2f}"
            )

        self._state.cash = round(self._state.cash - total_cost, 2)
        self._state.positions[symbol] = round(
            self._state.positions.get(symbol, 0.0) + quantity, 4
        )

        old_basis = self._cost_basis.get(symbol, 0.0)
        old_shares = self._state.positions.get(symbol, 0.0) - quantity
        if old_shares > 0:
            self._cost_basis[symbol] = old_basis + total_cost
        else:
            self._cost_basis[symbol] = total_cost

        # Record purchase date for T+1 settlement check
        if self._t_plus_1:
            self._purchase_dates[symbol] = datetime.utcnow().strftime("%Y-%m-%d")

        trade = {
            "symbol": symbol,
            "type": "buy",
            "price": price,
            "shares": quantity,
            "fees": fees["total"],
            "actionable": False,
            "decision_scope": "paper_trading_only",
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._state.trades.append(trade)
        self._state.total_value = round(self._state.cash + quantity * price, 2)
        self._state.last_updated = datetime.utcnow().isoformat()

        order_id = f"po-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{hash(symbol) % 10000:04d}"
        fill = Fill(
            fill_id=f"{order_id}-f1",
            order_id=order_id,
            symbol=symbol,
            side=OrderSide.BUY,
            quantity=float(quantity),
            price=price,
            fees=round(fees["total"], 2),
            timestamp=datetime.utcnow().isoformat(),
        )
        return Order(
            order_id=order_id,
            mode=OrderTradeMode.PAPER,
            symbol=symbol,
            side=OrderSide.BUY,
            quantity=float(quantity),
            price=price,
            status=OrderStatus.FILLED,
            risk_status="allowed",
            created_at=datetime.utcnow().isoformat(),
        )

    def _place_sell_order(self, symbol: str, price: float, quantity: int) -> Order:
        # T+1 settlement check: block same-day sell (automated cycle only;
        # manual place_order is exempt so users can override via WebUI)
        current_shares = self._state.positions.get(symbol, 0.0)
        if current_shares < quantity:
            raise ValueError(
                f"Insufficient shares: have {current_shares:.0f} but trying to sell {quantity}"
            )

        fees = calculate_fees(price, quantity, is_buy=False, config=self._fee_config)
        proceeds = quantity * price - fees["total"]

        # Proportional cost basis
        total_basis = self._cost_basis.get(symbol, 0.0)
        sold_basis = total_basis * (quantity / current_shares) if current_shares > 0 else 0
        trade_pnl = proceeds - sold_basis

        self._state.cash = round(self._state.cash + proceeds, 2)
        self._state.pnl = round(self._state.pnl + trade_pnl, 2)

        remaining = current_shares - quantity
        if remaining <= 0.0001:
            del self._state.positions[symbol]
            self._cost_basis.pop(symbol, None)
        else:
            self._state.positions[symbol] = round(remaining, 4)
            self._cost_basis[symbol] = round(total_basis - sold_basis, 2)

        trade = {
            "symbol": symbol,
            "type": "sell",
            "price": price,
            "shares": quantity,
            "fees": fees["total"],
            "pnl": round(trade_pnl, 2),
            "actionable": False,
            "decision_scope": "paper_trading_only",
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._state.trades.append(trade)
        self._state.last_updated = datetime.utcnow().isoformat()

        order_id = f"po-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{hash(symbol) % 10000:04d}"
        return Order(
            order_id=order_id,
            mode=OrderTradeMode.PAPER,
            symbol=symbol,
            side=OrderSide.SELL,
            quantity=float(quantity),
            price=price,
            status=OrderStatus.FILLED,
            risk_status="allowed",
            created_at=datetime.utcnow().isoformat(),
        )
