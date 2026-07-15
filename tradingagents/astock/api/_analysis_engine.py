"""Shared service: technical analysis engine for watchlist/dashboard.

Extracted from ``routes_analysis.py`` so that ``routes_dashboard``,
``routes_watchlist``, and ``routes_analysis`` all reuse the same logic
instead of each carrying their own copy.

Exported functions
------------------
- ``analyze_stock_symbol(symbol, name)`` — single-stock technical analysis
- ``load_watchlist()`` — load watchlist from DuckDB
"""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

def load_watchlist() -> list[dict[str, Any]]:
    """Load watchlist from the configured DuckDB store."""
    from flask import current_app
    store = current_app.config.get("STORE") if current_app else None
    return _load_from_duckdb(store)


def _load_from_duckdb(store: Any) -> list[dict[str, Any]]:
    """Load watchlist from DuckDB; propagate backend failures."""
    try:
        if store is None:
            raise RuntimeError("watchlist store unavailable")
        df = store.query_sql('SELECT symbol, name, added_at, source FROM watchlist ORDER BY added_at DESC')
        if df is None or df.empty:
            return []
        return df.to_dict(orient="records")
    except Exception as exc:
        logger.exception("DuckDB watchlist load failed")
        raise RuntimeError("watchlist store unavailable") from exc


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def analyze_stock_symbol(symbol: str, name: str) -> dict[str, Any]:
    """Run technical analysis on a single symbol, return a decision card dict.

    Uses RSI(14) + MA5/MA20 crossover + volume surge logic.
    """
    default = {
        "symbol": symbol,
        "name": name,
        "price": 0.0,
        "score": 50,
        "rating": "hold",
        "signal": "数据不足",
        "reasons": ["暂无足够数据进行分析"],
    }

    try:
        store = None
        from flask import current_app
        if current_app:
            store = current_app.config.get("STORE")
        # RSI/MA20 only need a bounded recent window; never materialise a
        # symbol's complete minute-history for a technical decision card.
        kline_df = store.query_kline(symbol, interval="1d", limit=250) if store else pd.DataFrame()

        # If store has no data, try live facade
        if kline_df.empty:
            try:
                facade = current_app.config.get("DATA_FACADE")
                if facade is None:
                    raise RuntimeError("data facade unavailable")
                resp = facade.get_kline(symbol=symbol, interval="1d", limit=120)
                if resp.status == "ok" and resp.data and resp.data.get("bars"):
                    bars = resp.data["bars"]
                    kline_df = pd.DataFrame(bars)
                    col_map = {"date": "trade_date", "datetime": "trade_date", "time": "trade_date"}
                    kline_df.rename(columns=col_map, inplace=True)
            except Exception as exc:
                logger.warning("Live data unavailable for %s: %s", symbol, exc)

        if kline_df.empty or len(kline_df) < 20:
            return default

        for col in ("open", "high", "low", "close", "volume"):
            if col in kline_df.columns:
                kline_df[col] = pd.to_numeric(kline_df[col], errors="coerce")
        kline_df.sort_values("trade_date", inplace=True)
        kline_df.reset_index(drop=True, inplace=True)

        closes = kline_df["close"].values.astype(float)
        volumes = (
            kline_df["volume"].values.astype(float) if "volume" in kline_df.columns else np.array([])
        )
        latest_price = float(closes[-1]) if len(closes) > 0 else 0.0

        reasons: list[str] = []
        score = 50

        # MA5 / MA20
        ma5 = pd.Series(closes).rolling(window=5).mean().values
        ma20 = pd.Series(closes).rolling(window=20).mean().values

        # RSI(14)
        rsi_series = compute_rsi(pd.Series(closes), period=14)
        latest_rsi = float(rsi_series.values[-1]) if len(rsi_series) > 0 else 50.0

        # Volume average (20-day)
        avg_volume = float(np.mean(volumes[-20:])) if len(volumes) >= 20 else 0.0
        latest_volume = float(volumes[-1]) if len(volumes) > 0 else 0.0
        volume_ratio = latest_volume / avg_volume if avg_volume > 0 else 1.0

        # RSI-based signals
        if latest_rsi < 30:
            reasons.append(f"RSI({latest_rsi:.0f}) 超卖")
            score += 20
        elif latest_rsi > 70:
            reasons.append(f"RSI({latest_rsi:.0f}) 超买")
            score -= 20
        elif 30 <= latest_rsi <= 40:
            score += 10
            reasons.append(f"RSI({latest_rsi:.0f}) 偏弱")
        elif 60 <= latest_rsi <= 70:
            score -= 10
            reasons.append(f"RSI({latest_rsi:.0f}) 偏强")
        else:
            reasons.append(f"RSI({latest_rsi:.0f}) 中性")

        # MA crossover (trend)
        if not np.isnan(ma5[-1]) and not np.isnan(ma20[-1]):
            if ma5[-1] > ma20[-1]:
                score += 15
                reasons.append("MA5 > MA20 趋势偏多")
            else:
                score -= 10
                reasons.append("MA5 < MA20 趋势偏空")

        # Price vs MA20
        if not np.isnan(ma20[-1]) and len(closes) > 0:
            pct_from_ma20 = (latest_price - ma20[-1]) / ma20[-1] * 100
            if latest_rsi < 30 and latest_price > ma20[-1]:
                score += 10
                reasons.append("价格站上MA20+超卖 → 买入信号")
            elif latest_rsi > 70 and latest_price < ma20[-1]:
                score -= 10
                reasons.append("价格跌破MA20+超买 → 卖出信号")

        # Volume surge
        if volume_ratio > 1.5 and len(closes) > 1:
            prev_close = closes[-2]
            price_change_pct = (latest_price - prev_close) / prev_close * 100
            if price_change_pct > 0:
                reasons.append(f"放量上涨(量比{volume_ratio:.1f}x)")
                score += 8
            else:
                reasons.append(f"放量下跌(量比{volume_ratio:.1f}x)")
                score -= 8

        score = max(0, min(100, int(round(score))))

        if score >= 65:
            rating, signal = "buy", "看多"
        elif score >= 40:
            rating, signal = "hold", "观望"
        else:
            rating, signal = "sell", "看空"

        return {
            "symbol": symbol,
            "name": name,
            "price": round(latest_price, 2),
            "score": score,
            "rating": rating,
            "signal": signal,
            "reasons": reasons,
        }

    except Exception as exc:
        logger.error("Analysis error for %s: %s", symbol, exc)
        return {
            "symbol": symbol,
            "name": name,
            "price": 0.0,
            "score": 50,
            "rating": "hold",
            "signal": "分析异常",
            "reasons": [f"分析出错: {str(exc)}"],
        }
