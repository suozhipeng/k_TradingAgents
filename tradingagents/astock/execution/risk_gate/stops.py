"""ATR calculation and stop-loss helpers for the risk gate."""

from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

from .gate import RiskGateResult, _EXECUTION_SIGNAL


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
        self._activated: dict[str, bool] = {}
        self._highest: dict[str, float] = {}
        self._stop_prices: dict[str, float] = {}

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
