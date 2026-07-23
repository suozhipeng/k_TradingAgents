"""Stock analysis engine — multi-dimension deterministic analysis."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd

# All V1.5 dimensions
DIMENSIONS = [
    "technical",
    "fundamental",
    "valuation",
    "capital_flow",
    "news",
    "sector",
    "sentiment",
    "risk",
]


def compute_analysis(frame: pd.DataFrame, symbol: str) -> dict[str, Any]:
    """Compute per-dimension stock analysis, marking unavailable where data is missing.

    Parameters
    ----------
    frame : pd.DataFrame
        Canonical kline_bars for the symbol.  Must have trade_date, open, close.
    symbol : str
        Stock symbol.

    Returns
    -------
    dict with per-dimension facts and data_state.
    """
    required = {"trade_date", "open", "close"}
    if not required.issubset(frame.columns):
        return {
            "symbol": symbol, "data_state": "unavailable",
            "dimensions": {d: {"data_state": "unavailable", "reason": "missing columns"} for d in DIMENSIONS},
        }

    df = frame.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["open"] = pd.to_numeric(df["open"], errors="coerce")
    df = df.dropna(subset=["trade_date", "close"]).reset_index(drop=True)

    if df.empty or len(df) < 5:
        return {
            "symbol": symbol, "data_state": "unavailable",
            "dimensions": {d: {"data_state": "unavailable", "reason": "insufficient bars"} for d in DIMENSIONS},
        }

    close = df["close"]
    latest = close.iloc[-1]
    latest_date = str(df["trade_date"].iloc[-1].date())

    # Technical — always available from kline_bars
    close_series = close.values
    ma5 = float(close.tail(5).mean())
    ma10 = float(close.tail(10).mean()) if len(close) >= 10 else None
    ma20 = float(close.tail(20).mean()) if len(close) >= 20 else None
    ma60 = float(close.tail(60).mean()) if len(close) >= 60 else None

    # MACD
    ema12 = close.ewm(span=12).mean().values
    ema26 = close.ewm(span=26).mean().values
    macd_line = float(ema12[-1] - ema26[-1])
    signal = float(pd.Series(ema12 - ema26).ewm(span=9).mean().values[-1])
    macd_hist = macd_line - signal

    # RSI(14)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean().values[-1]
    loss = (-delta.clip(upper=0)).rolling(14).mean().values[-1]
    rsi = 50.0
    if loss != 0:
        rs = gain / loss
        rsi = round(float(100 - 100 / (1 + rs)), 2) if not pd.isna(rs) else 50.0

    # Bollinger (20, 2)
    boll_mid = ma20 or float(close.mean())
    boll_std = float(close.tail(20).std()) if len(close) >= 20 else float(close.std())
    boll_upper = round(boll_mid + 2 * boll_std, 4)
    boll_lower = round(boll_mid - 2 * boll_std, 4)

    # Trend direction
    ma5_val = ma5
    ma20_val = ma20 or ma5  # fallback when insufficient data
    trend = "up" if ma5_val > ma20_val else ("down" if ma5_val < ma20_val else "sideways")

    # Support/resistance (simplified)
    recent = close.tail(20)
    support = float(recent.min())
    resistance = float(recent.max())

    technical_facts = {
        "data_state": "available",
        "latest_close": round(float(latest), 4),
        "ma5": round(ma5, 4), "ma10": round(ma10, 4) if ma10 else None,
        "ma20": round(ma20, 4) if ma20 else None, "ma60": round(ma60, 4) if ma60 else None,
        "macd_line": round(macd_line, 4), "signal_line": round(signal, 4),
        "macd_histogram": round(macd_hist, 4), "rsi_14": rsi,
        "boll_upper": boll_upper, "boll_mid": round(boll_mid, 4), "boll_lower": boll_lower,
        "support": round(float(support), 4), "resistance": round(float(resistance), 4),
        "trend_direction": trend,
        "breakout_status": "above_resistance" if latest > resistance * 1.02 else (
            "below_support" if latest < support * 0.98 else "within_range"),
    }

    # Risk signals (from stock_facts logic)
    returns = close.pct_change().dropna()
    risk_facts = {"data_state": "available", "signals": []}
    if len(returns) > 1 and float(returns.std()) >= 0.05:
        risk_facts["signals"].append({"code": "high_volatility", "severity": "warning"})
    if latest < (ma20 or float("inf")):
        risk_facts["signals"].append({"code": "below_ma20", "severity": "info"})
    if len(close) >= 2 and close.iloc[-1] < close.iloc[-2] * 0.95:
        risk_facts["signals"].append({"code": "sharp_decline", "severity": "warning"})

    # Other dimensions — unavailable without provider data
    unavailable = lambda name: {"data_state": "unavailable", "reason": f"requires {name} provider"}

    dimensions = {
        "technical": technical_facts,
        "fundamental": unavailable("fundamental_data"),
        "valuation": unavailable("valuation_data"),
        "capital_flow": unavailable("capital_flow_data"),
        "news": unavailable("news_data"),
        "sector": unavailable("sector_map"),
        "sentiment": {"data_state": "available", "note": "see market sentiment analysis"},
        "risk": risk_facts,
    }

    seed = json.dumps({"symbol": symbol, "date": latest_date, "close": round(float(latest), 2)}, sort_keys=True)
    run_id = "analysis_" + hashlib.sha256(seed.encode()).hexdigest()[:20]

    return {
        "run_id": run_id,
        "symbol": symbol,
        "data_state": "available",
        "trade_date": latest_date,
        "dimensions": dimensions,
        "dimensions_available": ",".join(d for d in DIMENSIONS if dimensions[d]["data_state"] == "available"),
        "llm_used": False,
    }
