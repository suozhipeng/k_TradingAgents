"""Paper trade scheduler — periodic cycle executor using threading.Timer.

Provides a lightweight timed loop that reads the latest data from DuckDB,
scores it with strategies, generates signals, and executes them through
the :class:`PaperTrader`.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any

from .event_bus import EventBus
from .paper_trader import PaperTrader
from .strategy_base import StrategyBase

logger = logging.getLogger(__name__)


class PaperTradeScheduler:
    """Timed paper trading scheduler.

    Parameters
    ----------
    paper_trader : PaperTrader
        The paper trading engine to execute signals through.
    store : AStockStore
        DuckDB-backed store used to fetch kline data.
    interval_minutes : int
        Interval between scheduled cycles (default ``30``).
    strategies : list[StrategyBase] or None
        Strategies to evaluate each cycle.  If ``None``, uses a default
        set of all available strategies.
    symbols : list[str] or None
        Symbols to monitor.  If ``None``, uses a small default set.
    """

    def __init__(
        self,
        paper_trader: PaperTrader,
        store: Any,
        interval_minutes: int = 30,
        strategies: list[StrategyBase] | None = None,
        symbols: list[str] | None = None,
    ) -> None:
        self._trader = paper_trader
        self._store = store
        self._interval = max(1, interval_minutes) * 60.0  # seconds
        self._strategies = strategies or self._default_strategies()
        self._symbols = symbols or ["000300.SH", "000001.SH", "399001.SZ", "600519.SH", "000858.SZ"]
        self._timer: threading.Timer | None = None
        self._running = False
        self._lock = threading.Lock()
        self._cycle_count = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the scheduler loop.

        The first cycle runs immediately; subsequent cycles fire at
        *interval_minutes* intervals.
        """
        with self._lock:
            if self._running:
                logger.warning("PaperTradeScheduler is already running")
                return
            self._running = True

        logger.info(
            "PaperTradeScheduler started (interval=%ds, symbols=%s, strategies=%d)",
            self._interval,
            self._symbols,
            len(self._strategies),
        )
        # Run first cycle immediately
        self._schedule_next()

    def stop(self) -> None:
        """Stop the scheduler loop."""
        with self._lock:
            self._running = False
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        logger.info("PaperTradeScheduler stopped (cycles=%d)", self._cycle_count)

    @property
    def running(self) -> bool:
        return self._running

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def _schedule_next(self) -> None:
        """Kick off the next cycle."""
        # Run the cycle synchronously (short-lived), then schedule next
        try:
            self.execute_scheduled_cycle()
        except Exception as exc:
            logger.error("Scheduled cycle failed: %s", exc, exc_info=True)
            EventBus.publish({
                "type": "error",
                "message": str(exc),
                "timestamp": datetime.utcnow().isoformat(),
            })

        with self._lock:
            if self._running:
                self._timer = threading.Timer(self._interval, self._schedule_next)
                self._timer.daemon = True
                self._timer.start()

    def execute_scheduled_cycle(self) -> None:
        """Execute one full scheduled cycle.

        Steps:
        1. Fetch latest kline data from DuckDB for each symbol.
        2. Score each symbol using each strategy.
        3. Aggregate signals (majority vote or first non-zero).
        4. Execute through PaperTrader.
        5. Publish progress events via EventBus.
        """
        self._cycle_count += 1
        cycle_id = self._cycle_count
        logger.info("Scheduled cycle #%d starting", cycle_id)

        EventBus.publish({
            "type": "cycle_start",
            "cycle": cycle_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        signals: dict[str, float] = {}
        prices: dict[str, float] = {}

        for symbol in self._symbols:
            try:
                # Fetch data from DuckDB
                df = self._fetch_latest(symbol)
                if df.empty:
                    continue

                price = float(df["close"].iloc[-1])
                prices[symbol] = price

                # Score with all strategies → aggregate by majority
                symbol_signals: list[int] = []
                for strategy in self._strategies:
                    sig_series = strategy.generate_signals(df)
                    non_zero = sig_series[sig_series != 0]
                    sig = int(non_zero.iloc[-1]) if not non_zero.empty else 0
                    symbol_signals.append(sig)

                # Majority vote: sum > 0 → buy, sum < 0 → sell
                total_sig = sum(symbol_signals)
                if total_sig > 0:
                    signals[symbol] = 1.0
                elif total_sig < 0:
                    signals[symbol] = -1.0
                else:
                    signals[symbol] = 0.0

            except Exception as exc:
                logger.warning("Error processing symbol %s: %s", symbol, exc)
                continue

        # Execute signals through paper trader
        if signals:
            state = self._trader.execute_cycle(signals, prices)
            trade_count = len(state.trades)

            # Track the last trades in the event bus
            for trade in state.trades[-5:]:  # last 5 trades
                EventBus.publish({
                    "type": "trade",
                    "cycle": cycle_id,
                    "symbol": trade.get("symbol", ""),
                    "direction": trade.get("type", ""),
                    "price": trade.get("price", 0.0),
                    "volume": trade.get("shares", 0.0),
                    "timestamp": datetime.utcnow().isoformat(),
                })

            EventBus.publish({
                "type": "cycle_end",
                "cycle": cycle_id,
                "total_value": state.total_value,
                "cash": state.cash,
                "trade_count": trade_count,
                "symbol_count": len(signals),
                "timestamp": datetime.utcnow().isoformat(),
            })

            logger.info(
                "Cycle #%d done: %d symbols, %d trades, total_value=%.2f",
                cycle_id,
                len(signals),
                trade_count,
                state.total_value,
            )
        else:
            EventBus.publish({
                "type": "cycle_end",
                "cycle": cycle_id,
                "total_value": 0.0,
                "cash": 0.0,
                "trade_count": 0,
                "symbol_count": 0,
                "note": "no_signals",
                "timestamp": datetime.utcnow().isoformat(),
            })
            logger.info("Cycle #%d done: no signals generated", cycle_id)

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _fetch_latest(self, symbol: str, lookback: int = 100) -> Any:
        """Fetch the most recent *lookback* kline bars from DuckDB."""
        if not hasattr(self._store, "query_kline"):
            return pd.DataFrame()

        try:
            df = self._store.query_kline(symbol=symbol)
            if not isinstance(df, pd.DataFrame) or df.empty:
                return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
            df = df.copy()
            if "trade_date" in df.columns and "date" not in df.columns:
                df["date"] = pd.to_datetime(df["trade_date"])
            if "date" in df.columns:
                df = df.set_index("date").sort_index()
            for col in ("open", "high", "low", "close", "volume"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            if len(df) > lookback:
                df = df.iloc[-lookback:]
            return df
        except Exception:
            return pd.DataFrame()

    @staticmethod
    def _default_strategies() -> list[StrategyBase]:
        """Build a default set of strategy instances."""
        from .strategy_base import (
            BullTrendStrategy,
            MeanReversionStrategy,
            MovingAverageTrendStrategy,
            RSIRangeStrategy,
        )

        return [
            MovingAverageTrendStrategy(),
            BullTrendStrategy(),
            MeanReversionStrategy(),
            RSIRangeStrategy(),
        ]


# To avoid circular imports at top of file
import pandas as pd  # noqa: E402
