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

RESOLUTION_MAP: dict[str, str] = {
    "1": "1m", "5": "5m", "15": "15m", "30": "30m", "60": "60m",
    "240": "1d", "D": "1d", "1D": "1d", "1d": "1d",
    "1W": "1w", "W": "1w", "1M": "1mo", "M": "1mo",
}


def _store() -> Any:
    return current_app.config["STORE"]


def _router() -> Any:
    return current_app.config.get("DATA_FACADE")


def _tv_resolution(resolution: str) -> str:
    """Convert TradingView resolution to internal interval string."""
    return RESOLUTION_MAP.get(resolution, "1d")


# ---------------------------------------------------------------------------
# GET /api/v1/tv/symbols
# ---------------------------------------------------------------------------

@bp.route("/tv/symbols")
def tv_symbols() -> tuple[Response, int]:
    """Return TradingView symbol info for a given symbol."""
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400

    # Get the latest kline bar to determine price data
    try:
        store = _store()
        df = store.query_kline(symbol, interval="1d", limit=1)
        bars = _df_to_json(df)
        last_price = bars[-1]["close"] if bars else 100.0
        prev_close = bars[-2]["close"] if len(bars) > 1 else last_price
    except Exception:
        last_price = 100.0
        prev_close = 100.0

    # Determine exchange and ticker from symbol format (600519.SH)
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
    limit = 5000

    try:
        store = _store()
        # Convert UNIX timestamps to date strings for efficient DB query
        start_str = __import__("datetime").datetime.utcfromtimestamp(from_ts).strftime("%Y-%m-%d") if from_ts else None
        end_str = __import__("datetime").datetime.utcfromtimestamp(to_ts).strftime("%Y-%m-%d") if to_ts else None
        df = store.query_kline(symbol, interval=interval, start=start_str, end=end_str)
        bars = _df_to_json(df)

        # If no data for intraday, try live fetch via facade
        if not bars and interval not in ("1d", "daily", "day"):
            router = _router()
            if router is not None:
                try:
                    resp = router.get_kline(symbol, interval=interval, source="mootdx", limit=400)
                    if resp.status == "ok" and resp.data:
                        items = resp.data.get("bars") or resp.data.get("items", [])
                        if isinstance(items, list) and len(items) > 0:
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
            # Convert trade_date to UTC timestamp
            if len(td) <= 10:
                # Date format: YYYY-MM-DD
                dt = __import__("datetime").datetime.strptime(td, "%Y-%m-%d")
                ts = int(dt.timestamp())
            else:
                # Datetime format: YYYY-MM-DD HH:MM
                try:
                    dt = __import__("datetime").datetime.strptime(td, "%Y-%m-%d %H:%M")
                    ts = int(dt.timestamp())
                except ValueError:
                    continue

            # Filter by time range
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

        # TV expects ascending time order
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
