"""Strategy base class and simple moving-average trend strategy."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class StrategyBase(ABC):
    """Abstract base class for backtest strategies.

    Subclasses must implement :meth:`generate_signals`.
    """

    def __init__(self, config: dict) -> None:
        self.config = dict(config)

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate trading signals from price/volume data.

        Parameters
        ----------
        data : pd.DataFrame
            Must contain at least ``close`` (and optionally ``open``, ``high``,
            ``low``, ``volume``) indexed by date.

        Returns
        -------
        pd.Series
            Integer signal series with the same index as *data*:
            ``1`` = buy, ``-1`` = sell, ``0`` = hold.
        """
        ...


class MovingAverageTrendStrategy(StrategyBase):
    """Simple dual-moving-average trend-following strategy.

    Config keys (all optional):
        fast_period : int
            Fast MA window (default ``5``).
        slow_period : int
            Slow MA window (default ``20``).
        price_col : str
            Column in *data* used for MA calculation (default ``"close"``).

    Signal logic
        - Fast MA crosses **above** slow MA  →  ``+1`` (buy)
        - Fast MA crosses **below** slow MA  →  ``-1`` (sell)
        - Otherwise                          →  ``0``  (hold)
    """

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config or {})
        self.fast_period: int = int(self.config.get("fast_period", 5))
        self.slow_period: int = int(self.config.get("slow_period", 20))
        self.price_col: str = str(self.config.get("price_col", "close"))

        if self.fast_period >= self.slow_period:
            raise ValueError(
                f"fast_period ({self.fast_period}) must be < slow_period ({self.slow_period})"
            )

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        if self.price_col not in data.columns:
            raise KeyError(
                f"Column '{self.price_col}' not found in data; "
                f"available columns: {list(data.columns)}"
            )

        prices = data[self.price_col]
        fast_ma = prices.rolling(window=self.fast_period).mean()
        slow_ma = prices.rolling(window=self.slow_period).mean()

        # Crossover detection: previous state vs current state
        prev_fast = fast_ma.shift(1)
        prev_slow = slow_ma.shift(1)

        signals = pd.Series(0, index=data.index, dtype=int)

        # Build valid-mask: both MAs have non-NaN current *and* previous values
        valid = fast_ma.notna() & slow_ma.notna() & prev_fast.notna() & prev_slow.notna()

        # Buy when fast crosses above slow (or first time fast > slow after both MAs are available)
        buy_condition = (fast_ma > slow_ma) & (prev_fast <= prev_slow)
        # Also trigger buy on the *first* period where fast_ma > slow_ma
        # (handles NaN boundary — prev_slow is NaN, so normal check misses it)
        first_buy = (fast_ma > slow_ma) & prev_fast.notna() & prev_slow.isna()
        buy_mask = valid & buy_condition
        signals[buy_mask] = 1
        # Apply first-buy as an independent condition (not NaN-gated)
        signals[first_buy] = 1

        # Sell when fast crosses below slow (or first time fast < slow after both MAs available)
        sell_condition = (fast_ma < slow_ma) & (prev_fast >= prev_slow)
        first_sell = (fast_ma < slow_ma) & prev_fast.notna() & prev_slow.isna()
        sell_mask = valid & sell_condition
        signals[sell_mask] = -1
        signals[first_sell] = -1

        # NaN regions (before both MAs are available) stay as 0
        signals = signals.fillna(0).astype(int)
        return signals
