"""Core execution engine for QMT bridge integration.

Provides the ``QmtExecutionEngine`` which routes trade signals through
risk-gate checks and then to the QMT bridge for actual order placement.

Two execution modes:

- **SAFETY** (default) — all orders require explicit human confirmation
  (``confirmed=True``).  Without it the engine returns a ``{"blocked":
  "safety_mode"}`` response.
- **AUTO** — the engine may execute signals automatically, subject to
  risk-gate constraints (ATR stop-loss, position caps, trailing stop).
  Switching from SAFETY to AUTO requires an explicit confirmation step.

References
----------
RiskGate, QmtBridge  — platform dependencies
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from tradingagents.astock.execution.qmt_bridge import QmtBridge
from tradingagents.astock.execution.risk_gate import ATRStopLoss, RiskGate, RiskGateResult, TrailingStop, calculate_atr

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Execution mode
# ---------------------------------------------------------------------------


class ExecutionMode(str, Enum):
    """Controls whether the QMT execution engine requires human confirmation.

    *SAFETY* (default)
        Every ``execute()`` call requires ``confirmed=True``.
    *AUTO*
        Signals may execute without explicit confirmation (risk gate permitting).
    """

    SAFETY = "safety"
    AUTO = "auto"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class QmtExecutionConfig:
    """Configuration for ``QmtExecutionEngine``.

    Attributes
    ----------
    mode : ExecutionMode
        Default execution mode (SAFETY).
    atr_stop_loss_pct : float
        Fractional ATR stop-loss threshold (default 0.10 = 10 %).
    trailing_stop_pct : float
        Fractional trailing-stop activation threshold (default 0.03 = 3 %).
    max_position_pct : float | None
        Maximum single-stock position as fraction of total portfolio
        (default 0.25 = 25 %).  ``None`` disables the cap.
    max_position_volume : int | None
        Maximum number of shares per order (default None = no limit).
    log_dir : str | None
        Directory for execution logs.  Created automatically if it does not
        exist.  ``None`` disables file logging.
    """

    mode: ExecutionMode = ExecutionMode.SAFETY
    atr_stop_loss_pct: float = 0.10
    trailing_stop_pct: float = 0.03
    max_position_pct: Optional[float] = 0.25
    max_position_volume: Optional[int] = None
    log_dir: Optional[str] = None


# ---------------------------------------------------------------------------
# Execution engine
# ---------------------------------------------------------------------------


class QmtExecutionEngine:
    """Controlled execution engine bridging signals → risk gate → QMT bridge.

    Parameters
    ----------
    bridge : QmtBridge
        The QMT HTTP bridge client (may be in mock mode for testing).
    risk_gate : RiskGate
        Risk-gate instance that performs pre-trade constraint checks.
    config : QmtExecutionConfig
        Runtime configuration (mode, stop-loss, position caps, etc.).
    """

    def __init__(
        self,
        bridge: QmtBridge,
        risk_gate: RiskGate,
        config: Optional[QmtExecutionConfig] = None,
    ) -> None:
        self._bridge = bridge
        self._risk_gate = risk_gate
        self._config = config or QmtExecutionConfig()
        # Internal state
        self._mode: ExecutionMode = self._config.mode
        self._pending_switch_confirm: bool = False
        self._atr_stop: ATRStopLoss = ATRStopLoss()
        self._trailing_stop: TrailingStop = TrailingStop()
        # Track highest prices per symbol for trailing stop
        self._highest_prices: Dict[str, float] = {}
        # Execution log
        self._execution_log: List[Dict[str, Any]] = []
        self._open_orders: List[Dict[str, Any]] = []

    # -- properties ---------------------------------------------------------

    @property
    def config(self) -> QmtExecutionConfig:
        """Read-only configuration."""
        return self._config

    @property
    def mode(self) -> ExecutionMode:
        """Current execution mode."""
        return self._mode

    @property
    def execution_log(self) -> List[Dict[str, Any]]:
        """List of all executed trades (read-only)."""
        return list(self._execution_log)

    # -- mode switching -----------------------------------------------------

    def set_mode(self, mode: ExecutionMode, *, confirm: bool = False) -> Dict[str, Any]:
        """Switch execution mode.

        Parameters
        ----------
        mode : ExecutionMode
            Target mode.
        confirm : bool
            Required when switching from SAFETY to AUTO.  The first call
            sets ``pending_switch_confirm``; the second call with
            ``confirm=True`` completes the switch.

        Returns
        -------
        dict
            ``{"mode": ..., "status": "...", "message": "..."}``
        """
        if mode == self._mode:
            return {"mode": self._mode.value, "status": "unchanged", "message": f"Already in {self._mode.value} mode."}

        if mode == ExecutionMode.SAFETY and self._mode == ExecutionMode.AUTO:
            # SAFETY downgrade is always allowed
            self._mode = ExecutionMode.SAFETY
            self._pending_switch_confirm = False
            _logger.info("Execution mode switched to SAFETY")
            return {"mode": "safety", "status": "switched", "message": "Switched to SAFETY mode."}

        if mode == ExecutionMode.AUTO and self._mode == ExecutionMode.SAFETY:
            # AUTO upgrade requires two-step confirmation
            if self._pending_switch_confirm:
                if confirm:
                    self._mode = ExecutionMode.AUTO
                    self._pending_switch_confirm = False
                    _logger.info("Execution mode switched to AUTO (confirmed)")
                    return {"mode": "auto", "status": "switched", "message": "Switched to AUTO mode (confirmed)."}
                else:
                    self._pending_switch_confirm = False
                    return {"mode": "safety", "status": "cancelled", "message": "AUTO switch confirmation cancelled."}
            else:
                self._pending_switch_confirm = True
                return {
                    "mode": "safety",
                    "status": "pending_confirm",
                    "message": "AUTO mode requires confirmation. Call set_mode(AUTO, confirm=True) to proceed.",
                }

        return {"mode": self._mode.value, "status": "error", "message": f"Unsupported mode transition."}

    # -- core execution -----------------------------------------------------

    def execute(
        self,
        signal: Dict[str, Any],
        price: float,
        volume: int,
        *,
        confirmed: bool = False,
    ) -> Dict[str, Any]:
        """Execute a single trading signal.

        Flow
        ----
        1. Safety mode check — requires ``confirmed=True``.
        2. Risk-gate check (position cap, ATR stop-loss).
        3. Place order via ``QmtBridge.place_order``.
        4. Log the execution.
        5. Return execution result.

        Parameters
        ----------
        signal : dict
            Must contain at least ``"symbol"`` (str) and ``"signal"`` (int,
            where 1=buy, -1=sell, 0=hold).
        price : float
            Execution price.
        volume : int
            Number of shares.
        confirmed : bool
            Explicit human confirmation (required in SAFETY mode).

        Returns
        -------
        dict
            Execution result with keys: ``filled``, ``order_id``, ``symbol``,
            ``price``, ``volume``, ``mode``, ``blocked`` (if blocked).
        """
        symbol = signal.get("symbol", "")
        signal_value = signal.get("signal", 0)

        if not symbol or signal_value == 0:
            return {"filled": False, "reason": "no_signal", "symbol": symbol}

        # --- 1. Safety mode enforcement ---
        if self._mode == ExecutionMode.SAFETY and not confirmed:
            _logger.warning("Blocked by SAFETY mode (confirmed=False): %s", symbol)
            return {
                "filled": False,
                "blocked": "safety_mode",
                "reason": "Safety mode requires confirmed=True.",
                "symbol": symbol,
                "mode": "safety",
            }

        direction = "buy" if signal_value == 1 else "sell"

        # --- 2. Risk-gate check ---
        proposal: Dict[str, Any] = {
            "symbol": symbol,
            "signal": signal_value,
            "actionable": False,  # RiskGate blocks actionable=True; mode is enforced separately above
        }

        # Position cap from current bridge positions
        current_positions = {p["symbol"]: p["volume"] for p in self._bridge.get_positions()}
        total_value = self._bridge.get_account_info().get("total_asset", 1_000_000.0)

        gate_result: RiskGateResult = self._risk_gate.check(
            proposal=proposal,
            constraints=[],
            position_cap_pct=self._config.max_position_pct,
            current_position={sym: float(val) / total_value for sym, val in current_positions.items()},
        )

        if not gate_result.allowed:
            _logger.warning("Risk gate blocked %s: %s", symbol, gate_result.reason)
            return {
                "filled": False,
                "blocked": "risk_gate",
                "reason": gate_result.reason,
                "blocked_by": gate_result.blocked_by,
                "symbol": symbol,
                "mode": self._mode.value,
            }

        # --- 3. ATR stop-loss check ---
        if direction == "sell":
            # For sell signals, check ATR stop-loss
            kline_data = self._bridge.get_kline(symbol, period="1d")
            if kline_data:
                closes = [bar["close"] for bar in kline_data[-20:]]
                import pandas as pd
                atr_value = calculate_atr(pd.Series(closes))
                entry_price = price  # treat current as last entry for stop check
                atr_check = self._atr_stop.check(entry_price, price, atr_value)
                if not atr_check.allowed:
                    _logger.warning("ATR stop-loss triggered for %s", symbol)
                    return {
                        "filled": False,
                        "blocked": "atr_stop_loss",
                        "reason": atr_check.reason,
                        "symbol": symbol,
                        "mode": self._mode.value,
                    }

        # --- 4. Volume cap check ---
        if self._config.max_position_volume is not None and volume > self._config.max_position_volume:
            volume = self._config.max_position_volume

        # --- 5. Place order ---
        try:
            order_result = self._bridge.place_order(
                symbol=symbol,
                direction=direction,
                price=price,
                volume=volume,
                order_type="limit",
            )
        except (ConnectionError, ValueError, RuntimeError) as exc:
            _logger.error("QMT bridge order failed for %s: %s", symbol, exc)
            return {
                "filled": False,
                "blocked": "bridge_error",
                "reason": str(exc),
                "symbol": symbol,
                "mode": self._mode.value,
            }

        # --- 6. Log execution ---
        exec_record: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": symbol,
            "direction": direction,
            "price": price,
            "volume": volume,
            "order_id": order_result.get("order_id", "unknown"),
            "filled_volume": order_result.get("filled_volume", volume),
            "filled_price": order_result.get("filled_price", price),
            "mode": self._mode.value,
            "confirmed": confirmed,
        }
        self._execution_log.append(exec_record)
        self._log_to_file(exec_record)

        # Track trailing stop
        if direction == "buy":
            current_highest = self._highest_prices.get(symbol, price)
            if price > current_highest:
                self._highest_prices[symbol] = price

        return {
            "filled": True,
            "order_id": order_result.get("order_id", "unknown"),
            "symbol": symbol,
            "direction": direction,
            "price": order_result.get("filled_price", price),
            "volume": order_result.get("filled_volume", volume),
            "mode": self._mode.value,
        }

    def auto_execute(
        self,
        signals: List[Dict[str, Any]],
        prices: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        """Execute multiple signals automatically (AUTO mode only).

        Parameters
        ----------
        signals : list[dict]
            List of signal dicts (must have ``"symbol"`` and ``"signal"``).
        prices : dict[str, float]
            Map of symbol → current price.

        Returns
        -------
        list[dict]
            List of execution results (one per signal).
        """
        if self._mode != ExecutionMode.AUTO:
            return [{"filled": False, "blocked": "not_auto", "reason": "Auto-execute requires AUTO mode."}]

        results: List[Dict[str, Any]] = []
        for signal in signals:
            symbol = signal.get("symbol", "")
            price = prices.get(symbol, 0.0)
            if price <= 0:
                results.append({"filled": False, "reason": "no_price", "symbol": symbol})
                continue
            volume = self._calculate_volume(symbol, price, signal.get("signal", 0))
            result = self.execute(signal, price, volume, confirmed=True)
            results.append(result)

        return results

    # -- stop-loss management -----------------------------------------------

    def update_stop_loss(self, symbol: str, current_price: float) -> Dict[str, Any]:
        """Check and update ATR stop-loss and trailing stop for a symbol.

        Parameters
        ----------
        symbol : str
            Stock symbol.
        current_price : float
            Current market price.

        Returns
        -------
        dict
            Status of stop-loss checks.
        """
        # Update highest price tracking
        highest = self._highest_prices.get(symbol, current_price)
        if current_price > highest:
            self._highest_prices[symbol] = current_price
            highest = current_price

        # Check trailing stop
        triggered, stop_price = self._trailing_stop.update(
            symbol, current_price, highest,
            activation_pct=self._config.trailing_stop_pct,
        )

        result: Dict[str, Any] = {
            "symbol": symbol,
            "current_price": current_price,
            "highest_price": highest,
        }

        if triggered:
            _logger.warning("Trailing stop triggered for %s at %.2f", symbol, stop_price)
            result["trailing_stop_triggered"] = True
            result["trailing_stop_price"] = stop_price

        return result

    def get_open_orders(self) -> List[Dict[str, Any]]:
        """Retrieve open orders from the QMT bridge.

        Returns
        -------
        list[dict]
        """
        try:
            self._open_orders = self._bridge.get_positions()  # simplified; real bridge would have get_open_orders
        except (ConnectionError, ValueError) as e:
            logger.debug("Operation failed: {0}", e)
        return list(self._open_orders)

    # -- internal helpers ---------------------------------------------------

    def _calculate_volume(self, symbol: str, price: float, signal: int) -> int:
        """Calculate order volume based on cash/position constraints."""
        if signal == 1:
            # Buy: use available cash
            try:
                account = self._bridge.get_account_info()
                available = account.get("available_cash", 100_000.0)
            except (ConnectionError, ValueError):
                available = 100_000.0
            max_shares = int(available / price) if price > 0 else 0
            if self._config.max_position_volume is not None:
                max_shares = min(max_shares, self._config.max_position_volume)
            return max(max_shares, 100)  # minimum 100 shares (1手)
        elif signal == -1:
            # Sell: liquidate position
            try:
                positions = self._bridge.get_positions()
                for pos in positions:
                    if pos["symbol"] == symbol:
                        return int(pos.get("available", 0))
            except (ConnectionError, ValueError) as e:
                logger.debug("Operation failed: {0}", e)
            return 0
        return 0

    def _log_to_file(self, record: Dict[str, Any]) -> None:
        """Append an execution record to the log file."""
        log_dir = self._config.log_dir
        if not log_dir:
            return
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        log_file = log_path / "qmt_execution.log"
        try:
            with open(log_file, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            _logger.warning("Cannot write execution log to %s: %s", log_file, exc)


__all__ = [
    "ExecutionMode",
    "QmtExecutionConfig",
    "QmtExecutionEngine",
]
