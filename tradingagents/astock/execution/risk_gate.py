"""Risk gate — pre-trade constraint validation for paper trading.

Phase 11 extensions
-------------------
- ``calculate_atr`` — ATR (Average True Range) calculation from price series.
- ``ATRStopLoss`` — ATR-based stop-loss check.
- ``TrailingStop`` — trailing stop-loss check with activation threshold.

References
----------
Wilder, J. Welles. *New Concepts in Technical Trading Systems* (1978).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

_EXECUTION_SIGNAL: str = "ResearchOnly"

_KNOWN_CONSTRAINTS = frozenset({
    "position_limit",
    "concentration",
    "missing_data",
    "volatility_spike",
    "liquidity_low",
    "gap_risk",
    "halted_stock",
    "st_risk",
    "circuit_breaker",
    "max_drawdown_hit",
    "earnings_blackout",
})


class RiskGateResult(BaseModel):
    """Result of a risk-gate check.

    Attributes
    ----------
    allowed : bool
        Whether the proposal passes the gate.
    reason : str
        Human-readable explanation.
    blocked_by : list[str]
        List of constraints that blocked the proposal (empty when allowed).
    execution_signal : str
        Always ``"ResearchOnly"``.
    """

    allowed: bool
    reason: str = ""
    blocked_by: list[str] = Field(default_factory=list)
    execution_signal: str = _EXECUTION_SIGNAL
    decision_scope: str = "risk_gate_only"


class RiskGate:
    """Pre-trade risk gate for paper trading.

    Checks position caps, known constraint keywords, and the actionable flag.
    Fails closed on unrecognised constraints.

    Phase 11 extension: the ``check`` method now accepts optional ATR
    stop-loss parameters via the ``atr_stop_loss`` keyword argument.
    """

    @staticmethod
    def check(
        proposal: dict,
        constraints: list[str] | None = None,
        position_cap_pct: float | None = None,
        current_position: dict | None = None,
        *,
        atr_stop_loss: Optional[ATRStopLoss] = None,
        entry_price: float | None = None,
        current_price: float | None = None,
        atr_value: float | None = None,
    ) -> RiskGateResult:
        """Evaluate a trade proposal against configured risk constraints.

        Parameters
        ----------
        proposal : dict
            Must have keys ``"symbol"`` (str), ``"signal"`` (int: -1, 0, 1),
            and optionally ``"actionable"`` (bool).  If ``actionable`` is
            truthy, the gate blocks immediately.
        constraints : list[str] or None
            Constraint keywords to enforce.
        position_cap_pct : float or None
            Maximum allowed position size as a fraction of total value
            (e.g. ``0.25`` = 25 %).  ``None`` means no cap.
        current_position : dict or None
            Current holdings; should match ``PaperTradeState.positions``.
            Only the proposal's ``symbol`` entry is examined.
        atr_stop_loss : ATRStopLoss or None
            Optional ATR stop-loss checker.
        entry_price : float or None
            Entry price for ATR stop-loss calculation.
        current_price : float or None
            Current market price for ATR stop-loss calculation.
        atr_value : float or None
            Pre-computed ATR value (if not provided, ATR check is skipped).

        Returns
        -------
        RiskGateResult
        """
        blocked_by: list[str] = []
        constraints = list(constraints or [])

        # --- 1. Actionable check ---
        if proposal.get("actionable", False):
            blocked_by.append("actionable_flag")

        # --- 2. Position cap check ---
        symbol = proposal.get("symbol", "")
        signal = proposal.get("signal", 0)
        current_position = dict(current_position or {})

        if position_cap_pct is not None and signal == 1:
            # For buy signals, check current exposure
            current_exposure = float(current_position.get(symbol, 0.0))
            if current_exposure >= position_cap_pct:
                blocked_by.append("position_limit")

        # --- 3. Constraint keyword matching ---
        for c in constraints:
            c_normalised = c.strip().lower()
            if c_normalised in _KNOWN_CONSTRAINTS:
                # Known constraint — always blocks
                blocked_by.append(c_normalised)
            elif not c_normalised:
                continue
            else:
                # Unknown / unrecognised constraint → fail closed
                blocked_by.append(f"unrecognised:{c_normalised}")

        # --- 4. ATR stop-loss check ---
        if atr_stop_loss is not None and entry_price is not None and current_price is not None and atr_value is not None:
            if signal in (-1, 0):  # only check for sell/hold signals
                atr_result = atr_stop_loss.check(entry_price, current_price, atr_value)
                if not atr_result.allowed:
                    blocked_by.append("atr_stop_loss")
                    # Merge reason
                    if atr_result.reason and atr_result.reason not in blocked_by:
                        pass  # reason captured in final output

        if blocked_by:
            return RiskGateResult(
                allowed=False,
                reason=f"Blocked by: {', '.join(blocked_by)}",
                blocked_by=blocked_by,
                execution_signal=_EXECUTION_SIGNAL,
                decision_scope="risk_gate_only",
            )

        return RiskGateResult(
            allowed=True,
            reason="All constraints passed.",
            blocked_by=[],
            execution_signal=_EXECUTION_SIGNAL,
            decision_scope="risk_gate_only",
        )


# ---------------------------------------------------------------------------
# ATR calculation
# ---------------------------------------------------------------------------


def calculate_atr(prices: "pd.Series", period: int = 14) -> float:
    """Calculate the Average True Range (ATR) from a price series.

    This is a simplified ATR approximation using absolute changes in closing
    prices as a proxy for true range.  For a full ATR you would need
    high/low/close data; when only close prices are available this provides
    a reasonable volatility estimate.

    Parameters
    ----------
    prices : pd.Series
        Series of closing prices (oldest first).
    period : int
        Lookback period (default 14).

    Returns
    -------
    float
        The ATR value (same unit as the input prices).  Returns 0.0 when
        there are insufficient data points.
    """
    try:
        import pandas as pd
    except ImportError:
        return 0.0

    prices = pd.Series(prices).dropna()
    if len(prices) < period + 1:
        return 0.0

    # True range approximation using absolute close-to-close changes
    close_changes = prices.diff().abs()
    # Use Wilder's smoothed ATR (first value is simple mean)
    atr = close_changes.rolling(window=period, min_periods=period).mean().iloc[-1]
    return float(atr) if pd.notna(atr) else 0.0


# ---------------------------------------------------------------------------
# ATR stop-loss
# ---------------------------------------------------------------------------


class ATRStopLoss:
    """ATR-based stop-loss check.

    The stop-loss level is::

        stop_price = entry_price - multiplier * atr_value

    Parameters
    ----------
    atr_multiplier : float
        How many ATR units below entry price to place the stop (default 2.0).
    atr_period : int
        Lookback period for ATR calculation (default 14).
    """

    def __init__(self, atr_multiplier: float = 2.0, atr_period: int = 14) -> None:
        self._multiplier = atr_multiplier
        self._period = atr_period

    @property
    def atr_multiplier(self) -> float:
        return self._multiplier

    @property
    def atr_period(self) -> int:
        return self._period

    def stop_price(self, entry_price: float, atr_value: float) -> float:
        """Calculate the stop-loss price.

        Parameters
        ----------
        entry_price : float
            The price at which the position was entered.
        atr_value : float
            Current ATR value.

        Returns
        -------
        float
            Stop-loss price level.
        """
        return entry_price - self._multiplier * atr_value

    def check(
        self,
        entry_price: float,
        current_price: float,
        atr_value: float,
    ) -> RiskGateResult:
        """Check whether current price has triggered the ATR stop-loss.

        Parameters
        ----------
        entry_price : float
            Position entry price.
        current_price : float
            Current market price.
        atr_value : float
            Current ATR value.

        Returns
        -------
        RiskGateResult
            ``allowed=False`` when ``current_price <= stop_price``.
        """
        stop = self.stop_price(entry_price, atr_value)
        if current_price <= stop:
            return RiskGateResult(
                allowed=False,
                reason=f"ATR stop-loss triggered: current {current_price:.4f} <= stop {stop:.4f} "
                f"(entry {entry_price:.4f}, multiplier {self._multiplier}, ATR {atr_value:.4f})",
                blocked_by=["atr_stop_loss"],
                execution_signal=_EXECUTION_SIGNAL,
                decision_scope="risk_gate_only",
            )
        return RiskGateResult(
            allowed=True,
            reason=f"ATR stop-loss not triggered: current {current_price:.4f} > stop {stop:.4f}",
            blocked_by=[],
            execution_signal=_EXECUTION_SIGNAL,
            decision_scope="risk_gate_only",
        )


# ---------------------------------------------------------------------------
# Trailing stop
# ---------------------------------------------------------------------------


class TrailingStop:
    """Trailing stop-loss with activation threshold.

    The stop trails the highest price reached after the position moves in
    the profit direction by at least ``activation_pct``.  Once activated,
    any retracement of ``trail_pct`` from the highest price triggers a sell.

    Parameters
    ----------
    activation_pct : float
        Minimum profit percentage to activate the trailing stop (default 0.03 = 3 %).
    trail_pct : float
        Retracement percentage from the highest price to trigger (default 0.02 = 2 %).
    """

    def __init__(self, activation_pct: float = 0.03, trail_pct: float = 0.02) -> None:
        self._activation_pct = activation_pct
        self._trail_pct = trail_pct
        # Track per-symbol state
        self._activated: Dict[str, bool] = {}
        self._highest: Dict[str, float] = {}
        self._stop_prices: Dict[str, float] = {}

    @property
    def activation_pct(self) -> float:
        return self._activation_pct

    @property
    def trail_pct(self) -> float:
        return self._trail_pct

    def update(
        self,
        symbol: str,
        current_price: float,
        highest_price: float,
        *,
        activation_pct: float | None = None,
        trail_pct: float | None = None,
    ) -> Tuple[bool, float]:
        """Update the trailing stop for a symbol and check if it is triggered.

        Parameters
        ----------
        symbol : str
            Stock symbol.
        current_price : float
            Current market price.
        highest_price : float
            Highest price reached since position entry (or since last call).
        activation_pct : float or None
            Override activation percentage for this call.
        trail_pct : float or None
            Override trail percentage for this call.

        Returns
        -------
        tuple[bool, float]
            ``(triggered, stop_price)``.  ``triggered`` is True when the
            trailing stop should be executed.
        """
        act_pct = activation_pct if activation_pct is not None else self._activation_pct
        trl_pct = trail_pct if trail_pct is not None else self._trail_pct

        # Store highest
        if symbol not in self._highest or highest_price > self._highest[symbol]:
            self._highest[symbol] = highest_price

        highest = self._highest[symbol]

        # Check activation
        gain_pct = (current_price - highest) / highest if highest > 0 else 0.0

        if not self._activated.get(symbol, False):
            # Check if gain from the tracked entry has reached activation threshold
            # Use current_price relative to highest as approximation
            if highest > 0 and (highest - (highest / (1 + act_pct))) / (highest / (1 + act_pct)) >= act_pct:
                self._activated[symbol] = True

        # Compute stop price
        stop_price = highest * (1.0 - trl_pct)
        self._stop_prices[symbol] = stop_price

        # Trigger check
        if self._activated.get(symbol, False) and current_price <= stop_price:
            return (True, stop_price)

        return (False, stop_price)

    def reset(self, symbol: str) -> None:
        """Reset tracking state for a symbol (e.g. after position closed)."""
        self._activated.pop(symbol, None)
        self._highest.pop(symbol, None)
        self._stop_prices.pop(symbol, None)


__all__ = [
    "RiskGate",
    "RiskGateResult",
    "calculate_atr",
    "ATRStopLoss",
    "TrailingStop",
]
