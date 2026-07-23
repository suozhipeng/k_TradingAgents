"""V1.7 Market Review V2 — risk list generator.

Flags stocks with risk signals based on deterministic rules.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


RISK_CATEGORIES = {
    "high_divergence": "高位分歧",
    "consecutive_limit_down": "连续跌停",
    "abnormal_volatility": "异常波动",
    "delisting_st": "退市/ST",
    "share_reduction": "减持",
    "material_announcement": "重大公告",
    "sector_recession": "板块退潮",
    "liquidity_insufficient": "流动性不足",
    "data_incomplete": "数据不完整",
}


def generate_risk_list(frame: pd.DataFrame, latest_date: str) -> list[dict[str, Any]]:
    """Generate market risk list from kline data.

    Args:
        frame: kline_bars DataFrame with symbol, trade_date, close, volume, pct_chg.
        latest_date: The review date.

    Returns:
        List of risk entries.
    """
    if frame.empty:
        return []

    risks: list[dict[str, Any]] = []
    df = frame.copy()
    if "trade_date" in df.columns:
        df["trade_date"] = pd.to_datetime(df["trade_date"])
    latest = df[df["trade_date"] == pd.Timestamp(latest_date)]
    if latest.empty:
        return []

    # Group by symbol
    for sym, group in df[df["symbol"].notna()].groupby("symbol"):
        grp = group.sort_values("trade_date").tail(30)
        if len(grp) < 3:
            continue

        closes = grp["close"].astype(float).values
        vols = grp["volume"].astype(float).values if "volume" in grp.columns else None

        # 1. 高位分歧: recent drop after significant rise
        latest_close = float(grp.iloc[-1]["close"])
        high_20 = max(closes)
        pct_from_high = (latest_close - high_20) / high_20 if high_20 > 0 else 0
        if pct_from_high < -0.10 and high_20 > 0:
            risks.append({
                "symbol": sym,
                "category": "high_divergence",
                "label": RISK_CATEGORIES["high_divergence"],
                "detail": f"距20日高点回落{abs(pct_from_high)*100:.1f}%",
                "severity": "high" if pct_from_high < -0.20 else "medium",
            })

        # 2. 连续跌停: consecutive close ≈ limit_down
        pct_chgs = []
        for i in range(1, len(grp)):
            prev = float(grp.iloc[i - 1]["close"])
            cur = float(grp.iloc[i]["close"])
            if prev > 0:
                pct_chgs.append((cur - prev) / prev)
        consecutive_down = sum(1 for c in pct_chgs[-3:] if c < -0.095) if pct_chgs else 0
        if consecutive_down >= 2:
            risks.append({
                "symbol": sym,
                "category": "consecutive_limit_down",
                "label": RISK_CATEGORIES["consecutive_limit_down"],
                "detail": f"连续{consecutive_down}个交易日跌幅>=9.5%",
                "severity": "critical" if consecutive_down >= 3 else "high",
            })

        # 3. 流动性不足
        if vols is not None and len(vols) >= 5:
            vol_ma5 = vols[-5:].mean()
            if vol_ma5 > 0 and vols[-1] / vol_ma5 < 0.3:
                risks.append({
                    "symbol": sym,
                    "category": "liquidity_insufficient",
                    "label": RISK_CATEGORIES["liquidity_insufficient"],
                    "detail": f"当日成交量仅为5日均量的{vols[-1]/vol_ma5*100:.0f}%",
                    "severity": "medium",
                })

    # 4. 数据不完整: aggregate
    total_symbols = df["symbol"].nunique() if "symbol" in df.columns else 0
    if total_symbols < 10:
        risks.append({
            "symbol": "*",
            "category": "data_incomplete",
            "label": RISK_CATEGORIES["data_incomplete"],
            "detail": f"当日仅{total_symbols}只股票有数据",
            "severity": "high",
        })

    return risks
