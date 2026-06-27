"""Watchlist technical analysis API — 三色决策卡 (three-color decision cards).

POST /api/v1/analysis/watchlist  —  analyze all watchlist stocks using
  pure technical indicators (RSI, MA crossover, volume).  No LLM calls.

Returns
-------
{
  "stocks": [
    {
      "symbol": str,
      "name": str,
      "price": float,
      "score": int,        # 0-100
      "rating": str,       # "buy" | "hold" | "sell"
      "signal": str,       # human-readable signal
      "reasons": [str],    # why the rating was given
    },
    ...
  ],
  "summary": {"total": int, "buy": int, "hold": int, "sell": int},
}
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from flask import Blueprint, Response, current_app, jsonify

logger = logging.getLogger(__name__)

bp = Blueprint("analysis", __name__)

WATCHLIST_PATH = Path.home() / ".tradingagents" / "watchlist.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_watchlist() -> list[dict[str, Any]]:
    """Load watchlist from JSON file (same as routes_watchlist)."""
    if not WATCHLIST_PATH.exists():
        return []
    try:
        with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load watchlist: %s", exc)
        return []


def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def _analyze_stock_symbol(
    symbol: str,
    name: str,
) -> dict[str, Any]:
    """Run technical analysis on a single symbol, return a decision card dict."""
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
        store = current_app.config.get("STORE")
        kline_df = store.query_kline(symbol) if store else pd.DataFrame()

        # If store has no data, try live facade
        if kline_df.empty:
            try:
                from tradingagents.astock.data_sources import AStockDataFacade

                facade = AStockDataFacade()
                resp = facade.get_kline(symbol=symbol, interval="1d", limit=120)
                if resp.status == "ok" and resp.data and resp.data.get("bars"):
                    bars = resp.data["bars"]
                    kline_df = pd.DataFrame(bars)
                    # Normalise column names
                    col_map = {
                        "date": "trade_date",
                        "datetime": "trade_date",
                        "time": "trade_date",
                    }
                    kline_df.rename(columns=col_map, inplace=True)
            except Exception as exc:
                logger.warning("Live data unavailable for %s: %s", symbol, exc)

        if kline_df.empty or len(kline_df) < 20:
            return default

        # Ensure numeric columns
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

        # ── Indicators ─────────────────────────────────────────────────
        reasons: list[str] = []
        score = 50  # neutral baseline

        # MA5 / MA20
        ma5 = pd.Series(closes).rolling(window=5).mean().values
        ma20 = pd.Series(closes).rolling(window=20).mean().values

        # RSI(14)
        rsi_series = _compute_rsi(pd.Series(closes), period=14)
        latest_rsi = float(rsi_series.values[-1]) if len(rsi_series) > 0 else 50.0

        # Volume average (20-day)
        avg_volume = float(np.mean(volumes[-20:])) if len(volumes) >= 20 else 0.0
        latest_volume = float(volumes[-1]) if len(volumes) > 0 else 0.0
        volume_ratio = latest_volume / avg_volume if avg_volume > 0 else 1.0

        # ── Signal logic ───────────────────────────────────────────────

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

        # Clamp score
        score = max(0, min(100, int(round(score))))

        # Rating
        if score >= 65:
            rating = "buy"
            signal = "看多"
        elif score >= 40:
            rating = "hold"
            signal = "观望"
        else:
            rating = "sell"
            signal = "看空"

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


# ---------------------------------------------------------------------------
# POST /api/v1/analysis/watchlist
# ---------------------------------------------------------------------------


@bp.route("/analysis/watchlist", methods=["POST"])
def analyze_watchlist() -> tuple[Response, int]:
    """Analyze all watchlist stocks and return decision cards."""
    items = _load_watchlist()
    if not items:
        return jsonify(
            {
                "stocks": [],
                "summary": {"total": 0, "buy": 0, "hold": 0, "sell": 0},
                "message": "暂无自选股",
            }
        ), 200

    # Build results from all watchlist items
    results: list[dict[str, Any]] = []
    for item in items:
        symbol = item.get("symbol", "").strip()
        name = item.get("name", symbol)
        if not symbol:
            continue
        result = _analyze_stock_symbol(symbol, name)
        results.append(result)

    # Summary
    counts = {"buy": 0, "hold": 0, "sell": 0}
    for r in results:
        rating = r.get("rating", "hold")
        if rating in counts:
            counts[rating] += 1

    # Sort: buy first, then hold, then sell, then by score descending
    rating_order = {"buy": 0, "hold": 1, "sell": 2}
    results.sort(key=lambda r: (rating_order.get(r.get("rating", "hold"), 9), -r.get("score", 0)))

    return jsonify(
        {
            "stocks": results,
            "summary": {
                "total": len(results),
                "buy": counts["buy"],
                "hold": counts["hold"],
                "sell": counts["sell"],
            },
        }
    ), 200


__all__ = ["bp"]
