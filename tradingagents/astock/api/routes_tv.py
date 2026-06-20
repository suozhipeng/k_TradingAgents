"""TradingView Charting Library data API — serves bars in TV-expected JSON format.

GET /api/v1/tv/history?symbol=600519.SH&resolution=5&from=1696000000&to=1697000000
  → returns {s: "ok", t: [...], o: [...], h: [...], l: [...], c: [...], v: [...]}

GET /api/v1/tv/symbols?symbol=600519.SH
  → returns TV symbol info object

Resolution mapping:
  1, 5, 15, 30, 60  → 1m, 5m, 15m, 30m, 60m
  240               → 1d  (4h = 240m, also D, 1D)
  1W, 1M             → 1w, 1mo
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request

bp = Blueprint("tv", __name__)
logger = logging.getLogger(__name__)

from ._helpers import df_to_json  # noqa: E402

# Backward-compatible alias
_df_to_json = df_to_json

RESOLUTION_MAP: dict[str, str] = {
    "1": "1m", "5": "5m", "15": "15m", "30": "30m", "60": "60m",
    "240": "1d", "1440": "1d", "D": "1d", "1D": "1d", "1d": "1d",
    "1W": "1w", "W": "1w", "10080": "1w",
    "1M": "1mo", "M": "1mo", "43200": "1mo",
}


def _store() -> Any:
    return current_app.config["STORE"]


def _router() -> Any:
    return current_app.config.get("DATA_FACADE")


def _tv_resolution(resolution: str) -> str:
    """Convert TradingView resolution to internal interval string."""
    return RESOLUTION_MAP.get(resolution, "1d")


def _aggregate_bars(daily_bars: list[dict[str, Any]], interval: str) -> list[dict[str, Any]]:
    """Aggregate daily bars into weekly (1w) or monthly (1mo) bars."""
    from datetime import datetime

    grouped: dict[str, dict[str, Any]] = {}
    for bar in daily_bars:
        td = bar.get("trade_date") or bar.get("date") or ""
        if not td:
            continue
        dt = datetime.strptime(td[:10], "%Y-%m-%d")
        if interval == "1w":
            # ISO week: year + '-' + week number
            iso = dt.isocalendar()
            key = f"{iso[0]}-W{iso[1]:02d}"
        else:
            # Monthly: year + '-' + month
            key = f"{dt.year}-{dt.month:02d}"

        if key not in grouped:
            grouped[key] = {
                "open": bar.get("open", 0),
                "high": bar.get("high", 0),
                "low": bar.get("low", 0),
                "close": bar.get("close", 0),
                "volume": float(bar.get("volume", 0)),
                "trade_date": td[:10],
            }
        else:
            g = grouped[key]
            g["high"] = max(g["high"], bar.get("high", 0))
            g["low"] = min(g["low"], bar.get("low", 0))
            g["close"] = bar.get("close", 0)
            g["volume"] = g["volume"] + float(bar.get("volume", 0))
            g["trade_date"] = td[:10]  # keep last date as the bar date

    return sorted(grouped.values(), key=lambda b: b["trade_date"])


# ---------------------------------------------------------------------------
# GET /api/v1/tv/symbols
# ---------------------------------------------------------------------------


@bp.route("/tv/symbols")
def tv_symbols() -> tuple[Response, int]:
    """Return TradingView symbol info for a given symbol."""
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400

    try:
        store = _store()
        df = store.query_kline(symbol, interval="1d", limit=1)
        bars = _df_to_json(df)
        last_price = bars[-1]["close"] if bars else 100.0
        prev_close = bars[-2]["close"] if len(bars) > 1 else last_price
    except Exception:
        last_price = 100.0
        prev_close = 100.0

    parts = symbol.upper().split(".")
    ticker = parts[0]
    exchange = parts[1] if len(parts) > 1 else "SSE"

    return jsonify({
        "symbol": symbol,
        "ticker": ticker,
        "name": symbol,
        "full_name": f"{exchange}:{ticker}",
        "description": f"{symbol} - A-Share Stock",
        "exchange": exchange,
        "type": "stock",
        "session": "0930-1130,1300-1500",
        "timezone": "Asia/Shanghai",
        "minmov": 1,
        "pricescale": 100,
        "minmove2": 0,
        "fractional": False,
        "has_intraday": True,
        "has_daily": True,
        "has_weekly_and_monthly": True,
        "supported_resolutions": [
            "1", "5", "15", "30", "60", "240", "D", "W", "M"
        ],
        "intraday_multipliers": ["1", "5", "15", "30", "60"],
        "volume_precision": 0,
        "data_status": "streaming",
        "prices": [],
    }), 200


# ---------------------------------------------------------------------------
# GET /api/v1/tv/history
# ---------------------------------------------------------------------------


@bp.route("/tv/debug_mootdx")
def tv_debug_mootdx() -> tuple[Response, int]:
    """Debug endpoint to check mootdx fallback."""
    symbol = request.args.get("symbol", "600519.SH")
    interval = "5m"
    router = _router()
    result = {
        "router_type": type(router).__name__ if router else None,
        "symbol": symbol,
        "interval": interval,
    }
    if router is None:
        result["error"] = "router is None"
    else:
        try:
            resp = router.get_kline(symbol, interval=interval, source="mootdx", limit=5)
            result["resp_status"] = resp.status
            result["has_data"] = resp.data is not None
            if resp.data:
                items = resp.data.get("bars") or resp.data.get("items", [])
                result["items_type"] = type(items).__name__
                result["items_count"] = len(items)
                if items:
                    result["sample"] = items[0]
        except Exception as exc:
            result["exception"] = str(exc)
            import traceback
            result["traceback"] = traceback.format_exc()
    return jsonify(result), 200


@bp.route("/tv/history")
def tv_history() -> tuple[Response, int]:
    """Return OHLCV bars for TradingView.

    Query params:
        symbol  (str)    — e.g. 600519.SH
        resolution (str) — e.g. 5 (minutes), D (daily)
        from    (int)    — UTC timestamp (seconds)
        to      (int)    — UTC timestamp (seconds)
    """
    symbol = request.args.get("symbol", "")
    resolution = request.args.get("resolution", "D")
    from_ts = request.args.get("from", type=int)
    to_ts = request.args.get("to", type=int)

    if not symbol:
        return jsonify({"s": "error", "errmsg": "symbol required"}), 400

    interval = _tv_resolution(resolution)

    try:
        store = _store()
        start_str = __import__("datetime").datetime.utcfromtimestamp(from_ts).strftime("%Y-%m-%d") if from_ts else None  # noqa: E501
        end_str = __import__("datetime").datetime.utcfromtimestamp(to_ts).strftime("%Y-%m-%d") if to_ts else None
        df = store.query_kline(symbol, interval=interval, start=start_str, end=end_str)
        bars = _df_to_json(df)

        # Weekly/Monthly: aggregate from daily data
        if not bars and interval in ("1w", "1mo"):
            df_daily = store.query_kline(symbol, interval="1d", start=start_str, end=end_str)
            daily_bars = _df_to_json(df_daily)
            if daily_bars:
                bars = _aggregate_bars(daily_bars, interval)
        elif not bars and interval not in ("1d", "daily", "day"):
            router = _router()
            if router is not None:
                try:
                    resp = router.get_kline(symbol, interval=interval, source="mootdx", limit=400)
                    if resp.status == "ok" and resp.data:
                        items = resp.data.get("bars") or resp.data.get("items", [])
                        if isinstance(items, list) and len(items) > 0:
                            # Copy to avoid mutating cached source data (mootdx reuses objects)
                            items = [dict(item) for item in items]
                            first_date = items[0].get("date") or ""
                            if " " in str(first_date):
                                for item in items:
                                    if "date" in item and "trade_date" not in item:
                                        item["trade_date"] = item.pop("date")
                                bars = items
                except Exception:
                    logger.warning("TV intraday fetch failed for %s", symbol, exc_info=True)

        if not bars:
            return jsonify({"s": "no_data", "nextTime": int(to_ts or 0)}), 200

        # Build TV OHLCV arrays
        times: list[int] = []
        opens: list[float] = []
        highs: list[float] = []
        lows: list[float] = []
        closes: list[float] = []
        volumes: list[float] = []

        for b in bars:
            td = b.get("trade_date") or b.get("date") or ""
            if not td:
                continue
            if len(td) <= 10:
                dt = __import__("datetime").datetime.strptime(td, "%Y-%m-%d")
                ts = int(dt.timestamp())
            else:
                try:
                    dt = __import__("datetime").datetime.strptime(td, "%Y-%m-%d %H:%M")
                    ts = int(dt.timestamp())
                except ValueError:
                    continue

            if from_ts and ts < from_ts:
                continue
            if to_ts and ts > to_ts:
                continue

            times.append(ts)
            opens.append(float(b.get("open", 0)))
            highs.append(float(b.get("high", 0)))
            lows.append(float(b.get("low", 0)))
            closes.append(float(b.get("close", 0)))
            volumes.append(float(b.get("volume", 0)))

        if not times:
            return jsonify({"s": "no_data", "nextTime": int(to_ts or 0)}), 200

        times, opens, highs, lows, closes, volumes = zip(
            *sorted(zip(times, opens, highs, lows, closes, volumes))
        )

        return jsonify({
            "s": "ok",
            "t": list(times),
            "o": list(opens),
            "h": list(highs),
            "l": list(lows),
            "c": list(closes),
            "v": list(volumes),
        }), 200

    except Exception as exc:
        logger.error("TV history error: %s", exc)
        return jsonify({"s": "error", "errmsg": str(exc)}), 500
