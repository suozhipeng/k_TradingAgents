"""Stock screener API — scan stocks by technical conditions.

Provides ``GET /api/v1/market/screener`` that scans all tracked symbols
and returns those matching the specified technical criteria.
"""

from __future__ import annotations

import logging

from typing import Any

import numpy as np
from flask import Blueprint, Response, current_app, jsonify, request
from .envelope import error_response

from ._helpers import _as_bool, bounded_float_arg, bounded_int_arg, get_store, mock_data_enabled
logger = logging.getLogger(__name__)

bp = Blueprint("screener", __name__)


# ---------------------------------------------------------------------------
# Technical indicator helpers
# ---------------------------------------------------------------------------


def _rsi(prices: list[float], period: int = 14) -> float:
    """Compute RSI for the given price series."""
    if len(prices) < period + 1:
        return 50.0
    arr = np.array(prices[-period - 1:], dtype=float)
    diffs = np.diff(arr)
    gains = np.where(diffs > 0, diffs, 0)
    losses = np.where(diffs < 0, -diffs, 0)
    avg_gain = gains.mean()
    avg_loss = losses.mean()
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _ma(data: list[float], period: int) -> list[float]:
    """Simple moving average."""
    if len(data) < period:
        return []
    arr = np.array(data, dtype=float)
    return list(np.convolve(arr, np.ones(period) / period, mode="valid"))


def _ema(data: list[float], period: int) -> list[float]:
    """Exponential moving average."""
    if len(data) < period:
        return []
    arr = np.array(data, dtype=float)
    ema = [arr[:period].mean()]
    multiplier = 2.0 / (period + 1)
    for v in arr[period:]:
        ema.append((v - ema[-1]) * multiplier + ema[-1])
    return ema


def _macd(prices: list[float]) -> dict[str, Any]:
    """Compute MACD line, signal line, and histogram."""
    if len(prices) < 26:
        return {"macd": 0, "signal": 0, "histogram": 0, "golden_cross": False, "death_cross": False}
    ema12 = _ema(prices, 12)
    ema26 = _ema(prices, 26)
    if len(ema12) < 2 or len(ema26) < 2:
        return {"macd": 0, "signal": 0, "histogram": 0, "golden_cross": False, "death_cross": False}
    # Align lengths
    macd_line = [e12 - e26 for e12, e26 in zip(ema12, ema26)]
    signal_line = _ema(macd_line, 9)
    if len(signal_line) < 2:
        return {"macd": 0, "signal": 0, "histogram": 0, "golden_cross": False, "death_cross": False}
    # Align to same length
    min_len = min(len(macd_line), len(signal_line))
    macd_line = macd_line[-min_len:]
    signal_line = signal_line[-min_len:]
    histogram = macd_line[-1] - signal_line[-1]
    prev_hist = macd_line[-2] - signal_line[-2] if len(macd_line) >= 2 else 0
    return {
        "macd": round(macd_line[-1], 4),
        "signal": round(signal_line[-1], 4),
        "histogram": round(histogram, 4),
        "golden_cross": macd_line[-2] < signal_line[-2] and macd_line[-1] >= signal_line[-1],
        "death_cross": macd_line[-2] > signal_line[-2] and macd_line[-1] <= signal_line[-1],
    }


def _volume_ratio(volumes: list[float], period: int = 20) -> float:
    """Current volume / average volume ratio."""
    if len(volumes) < period + 1:
        return 1.0
    recent = volumes[-period:]
    avg = sum(recent) / len(recent)
    return volumes[-1] / avg if avg > 0 else 1.0


# ---------------------------------------------------------------------------
# GET /api/v1/market/screener
# ---------------------------------------------------------------------------


@bp.route("/market/screener")
def screener() -> tuple[Response, int]:
    """Scan stocks by technical conditions.

    Query params (all optional filters):
        rsi_min (float) — minimum RSI (default 0)
        rsi_max (float) — maximum RSI (default 100)
        ma_golden_cross (bool) — MA5 crosses above MA20
        ma_death_cross (bool) — MA5 crosses below MA20
        macd_golden (bool) — MACD line crosses above signal
        macd_death (bool) — MACD line crosses below signal
        volume_ratio_min (float) — min volume surge ratio (default 0)
        limit (int) — max results (default 50)
        mock (bool) — use synthetic data for testing
    """
    try:
        limit = bounded_int_arg("limit", 50, minimum=1, maximum=200)
        scan_limit = bounded_int_arg("scan_limit", 2000, minimum=1, maximum=5000)
        rsi_min = bounded_float_arg("rsi_min", 0, minimum=0, maximum=100)
        rsi_max = bounded_float_arg("rsi_max", 100, minimum=0, maximum=100)
        vol_ratio_min = bounded_float_arg("volume_ratio_min", 0, minimum=0, maximum=100)
        if rsi_min > rsi_max:
            return error_response("invalid_rsi_range", 400)
        store = get_store()
        use_mock = mock_data_enabled() or _as_bool(request.args.get("mock"), False)

        # Get symbols to scan
        if use_mock:
            symbols = ["600519.SH", "000858.SZ", "601318.SH", "000333.SZ", "600036.SH",
                       "002415.SZ", "601166.SH", "000651.SZ", "600887.SH", "002594.SZ"]
            kline_by_symbol: dict[str, Any] = {}
        else:
            try:
                # One window query replaces N individual ``query_kline`` calls.
                # The scan cap makes a full-market request bounded even if a
                # user has imported every A-share history locally.
                df = store.query_sql(
                    f"""WITH selected AS (
                           SELECT symbol FROM kline_bars WHERE "interval" = '1d'
                           GROUP BY symbol ORDER BY symbol LIMIT {scan_limit}
                       ), ranked AS (
                           SELECT k.*, row_number() OVER (
                               PARTITION BY k.symbol ORDER BY k.bar_time DESC
                           ) AS rn
                           FROM kline_bars k JOIN selected s USING (symbol)
                           WHERE k."interval" = '1d'
                       )
                       SELECT * EXCLUDE (rn) FROM ranked WHERE rn <= 120
                       ORDER BY symbol, bar_time""",
                )
                symbols = df["symbol"].drop_duplicates().tolist() if not df.empty else []
                kline_by_symbol = {symbol: frame for symbol, frame in df.groupby("symbol", sort=False)}
            except Exception:
                symbols = []
                kline_by_symbol = {}

        if not symbols:
            return jsonify({"results": [], "total": 0, "message": "No symbols found in store."}), 200

        # Parse filter params
        ma_golden = _as_bool(request.args.get("ma_golden_cross"), False)
        ma_death = _as_bool(request.args.get("ma_death_cross"), False)
        macd_golden = _as_bool(request.args.get("macd_golden"), False)
        macd_death = _as_bool(request.args.get("macd_death"), False)

        any_filter = any([rsi_min > 0, rsi_max < 100, ma_golden, ma_death,
                          macd_golden, macd_death, vol_ratio_min > 0])

        results = []
        failed_symbols = 0
        for symbol in symbols:
            try:
                if use_mock:
                    # Generate synthetic kline data for testing
                    import random
                    n = 120
                    closes = [100.0]
                    for _ in range(n - 1):
                        closes.append(closes[-1] * (1 + random.uniform(-0.03, 0.03)))
                    volumes = [random.randint(500000, 5000000) for _ in range(n)]
                else:
                    kline_df = kline_by_symbol.get(symbol)
                    if kline_df is None or kline_df.empty:
                        continue
                    closes = kline_df["close"].tolist() if "close" in kline_df.columns else []
                    volumes = kline_df["volume"].tolist() if "volume" in kline_df.columns else []

                if len(closes) < 30:
                    continue

                # Compute indicators
                rsi_val = _rsi(closes, 14)
                ma5 = _ma(closes, 5)[-1] if len(_ma(closes, 5)) > 0 else closes[-1]
                ma20 = _ma(closes, 20)[-1] if len(_ma(closes, 20)) > 0 else closes[-1]
                ma60 = _ma(closes, 60)[-1] if len(_ma(closes, 60)) > 0 else closes[-1]
                macd_info = _macd(closes)
                vol_ratio = _volume_ratio(volumes)

                last_close = closes[-1]
                last_ma5 = ma5
                last_ma20 = ma20

                ma5_series = _ma(closes, 5)
                ma20_series = _ma(closes, 20)
                ma_golden_cross = False
                ma_death_cross = False
                if len(ma5_series) >= 2 and len(ma20_series) >= 2:
                    # Align to same index
                    n5, n20 = len(ma5_series), len(ma20_series)
                    offset = n5 - n20
                    if offset >= 0:
                        ma5_slice = ma5_series[offset:]
                        if len(ma5_slice) >= 2 and len(ma20_series) >= 2:
                            ma_golden_cross = ma5_slice[-2] <= ma20_series[-2] and ma5_slice[-1] > ma20_series[-1]
                            ma_death_cross = ma5_slice[-2] >= ma20_series[-2] and ma5_slice[-1] < ma20_series[-1]

                # Apply filters
                if rsi_val < rsi_min or rsi_val > rsi_max:
                    continue
                if ma_golden and not ma_golden_cross:
                    continue
                if ma_death and not ma_death_cross:
                    continue
                if macd_golden and not macd_info["golden_cross"]:
                    continue
                if macd_death and not macd_info["death_cross"]:
                    continue
                if vol_ratio < vol_ratio_min:
                    continue
                if any_filter and not any([rsi_val < rsi_min or rsi_val > rsi_max,
                                           ma_golden and ma_golden_cross,
                                           ma_death and ma_death_cross,
                                           macd_golden and macd_info["golden_cross"],
                                           macd_death and macd_info["death_cross"],
                                           vol_ratio < vol_ratio_min]):
                    # Re-check: if any filters active, ensure at least one matches
                    pass  # Already filtered above

                # Score: composite technical score
                score = 0.0
                score += 0.3 * max(0, (rsi_val - 50) / 50)  # RSI momentum
                score += 0.3 * (1 if last_close > last_ma5 else -0.5)  # MA trend
                score += 0.2 * (1 if last_ma5 > last_ma20 else -0.5)  # MA cross
                score += 0.1 * (1 if macd_info["golden_cross"] else (-1 if macd_info["death_cross"] else 0))
                score += 0.1 * min(3, vol_ratio - 1)  # Volume surge

                results.append({
                    "symbol": symbol,
                    "price": float(round(last_close, 2)),
                    "rsi_14": float(round(rsi_val, 1)),
                    "ma5": float(round(last_ma5, 2)),
                    "ma20": float(round(last_ma20, 2)),
                    "ma60": float(round(ma60, 2)),
                    "macd": float(macd_info["macd"]),
                    "macd_signal": float(macd_info["signal"]),
                    "macd_histogram": float(macd_info["histogram"]),
                    "golden_cross": bool(ma_golden_cross),
                    "death_cross": bool(ma_death_cross),
                    "macd_golden": bool(macd_info["golden_cross"]),
                    "macd_death": bool(macd_info["death_cross"]),
                    "volume_ratio": round(vol_ratio, 2),
                    "score": round(float(score), 3),
                })

            except Exception as exc:
                failed_symbols += 1
                logger.debug("Screener calculation failed for %s: %s", symbol, exc)
                continue

        # Sort by score descending
        results.sort(key=lambda r: r["score"], reverse=True)

        return jsonify({
            "results": results[:limit],
            "total": len(results),
            "filters": {
                "rsi_min": rsi_min,
                "rsi_max": rsi_max,
                "ma_golden_cross": ma_golden,
                "ma_death_cross": ma_death,
                "macd_golden": macd_golden,
                "macd_death": macd_death,
                "volume_ratio_min": vol_ratio_min,
                "scan_limit": scan_limit,
            },
            "scan": {"requested": len(symbols), "failed": failed_symbols},
        }), 200

    except ValueError:
        return error_response("invalid_screener_parameter", 400)
    except Exception as exc:
        return error_response(str(exc), 500)
