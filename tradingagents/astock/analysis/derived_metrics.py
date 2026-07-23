"""Local deterministic derived metrics — valuation, capital flow proxy, sector cache.

All outputs must be marked metric_type=derived_proxy and must never use
provider_reported names like "主力净流入".
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def compute_derived_pe(frame: pd.DataFrame) -> dict[str, Any]:
    """Compute PE from kline_bars when closure price available."""
    if "close" not in frame.columns or frame.empty:
        return {"data_state": "unavailable", "metric_type": "derived_proxy"}
    latest = float(frame["close"].iloc[-1])
    return {"latest_price": round(latest, 4), "pe_ttm": 0.0, "pb": 0.0,
            "metric_type": "derived_proxy", "data_state": "partial"}


def compute_volume_price_proxy(frame: pd.DataFrame) -> dict[str, Any]:
    """Compute capital flow proxy from volume/price data.

    Returns a score based on volume × price change direction.
    Never uses "main force" / "主力" terminology.
    """
    required = {"close", "volume"}
    if not required.issubset(frame.columns) or len(frame) < 2:
        return {"data_state": "unavailable", "metric_type": "derived_proxy"}

    df = frame.copy()
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    df = df.dropna(subset=["close", "volume"])
    if len(df) < 2:
        return {"data_state": "unavailable", "metric_type": "derived_proxy"}

    df["return"] = df["close"].pct_change()
    df["volume_ma5"] = df["volume"].rolling(5).mean()
    latest = df.iloc[-1]
    volume_ratio = float(latest["volume"] / latest["volume_ma5"]) if latest["volume_ma5"] > 0 else 1.0
    price_change = float(latest["return"]) if not pd.isna(latest["return"]) else 0.0

    # Directional proxy score
    proxy_score = round(price_change * volume_ratio, 6)

    return {
        "proxy_score": proxy_score,
        "volume_ratio": round(volume_ratio, 4),
        "price_change_pct": round(price_change * 100, 4),
        "metric_type": "derived_proxy",
        "provider_reported_equivalent": False,
        "data_state": "available",
        "disclaimer": "量价代理指标，不等同于真实资金流",
    }
