"""Mock data helpers for backtest engine testing."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

# ---------------------------------------------------------------------------
# Mock data storage
# ---------------------------------------------------------------------------

_MOCK_OHLCV: dict[str, list[dict]] = {}

_SYMBOLS_MOCKED: set[str] = set()


def _generate_mock_bars(
    symbol: str,
    start_date: str,
    end_date: str,
    *,
    base_price: float = 100.0,
    volatility: float = 0.01,
) -> list[dict]:
    """Deterministic OHLCV sequence for testing."""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    bars: list[dict] = []
    price = base_price
    current = start
    while current <= end:
        if current.weekday() < 5:  # trading day
            change = price * volatility * (hash(f"{symbol}:{current}") % 200 - 100) / 100.0
            open_p = round(price, 2)
            close_p = round(price + change, 2)
            high_p = round(max(open_p, close_p) * (1 + abs(change) / price / 2), 2)
            low_p = round(min(open_p, close_p) * (1 - abs(change) / price / 2), 2)
            bar = {
                "date": current.strftime("%Y-%m-%d"),
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "volume": 1000000,
            }
            bars.append(bar)
            price = close_p
        current += timedelta(days=1)

    _MOCK_OHLCV[symbol] = bars
    _SYMBOLS_MOCKED.add(symbol)
    return bars


def _mock_fallback(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Generate mock OHLCV data for testing / fallback."""
    bars = _generate_mock_bars(symbol, start_date, end_date)
    df = pd.DataFrame(bars)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df
