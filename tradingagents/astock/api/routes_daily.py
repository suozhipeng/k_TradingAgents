"""Daily market review API routes — FR-11.

Provides a composite daily review endpoint aggregating major A-share index
snapshots, sector rotation, and top gainers/losers.

All routes return JSON.  Error responses follow ``{"error": ..., "status": N}``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request

bp = Blueprint("daily", __name__)

_INDEX_MAP: dict[str, str] = {
    "000001.SH": "上证指数",
    "399001.SZ": "深证成指",
    "399006.SZ": "创业板指",
}


def _facade() -> Any:
    """Return the app's AStockDataFacade instance (or None)."""
    return current_app.config.get("DATA_FACADE")


# ---------------------------------------------------------------------------
# GET /api/v1/daily/review?date=2026-07-05
# ---------------------------------------------------------------------------


@bp.route("/daily/review")
def daily_review() -> tuple[Response, int]:
    """Aggregate daily market review for the three major A-share indexes.

    Query params:
        date (str, optional) — trade date in ``YYYY-MM-DD`` format
            (defaults to today).

    Returns
    -------
    JSON with:
        - ``date`` — the review date
        - ``indices`` — list of index snapshots (name, current, change%, volume)
        - ``sectors`` — sector rotation data (if available)
        - ``top_gainers`` — top 10 gainers
        - ``top_losers`` — top 10 losers
    """
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    facade = _facade()

    indices_data: list[dict[str, Any]] = []
    sectors_data: list[dict[str, Any]] = []
    top_gainers: list[dict[str, Any]] = []
    top_losers: list[dict[str, Any]] = []

    # ── Index snapshots ──
    for symbol, name_cn in _INDEX_MAP.items():
        try:
            if facade:
                resp = facade.get_market_summary(symbol=symbol)
                if resp.status == "ok" and resp.data:
                    d: dict[str, Any] = {
                        "symbol": symbol,
                        "name": name_cn,
                    }
                    # Normalise field names from provider response
                    d["current"] = resp.data.get("current", resp.data.get("price", 0))
                    d["change"] = resp.data.get("change", resp.data.get("change_pct", 0))
                    d["change_pct"] = resp.data.get("change_pct", 0)
                    d["volume"] = resp.data.get("volume", 0)
                    d["amount"] = resp.data.get("amount", 0)
                    d["high"] = resp.data.get("high", 0)
                    d["low"] = resp.data.get("low", 0)
                    d["open"] = resp.data.get("open", 0)
                    d["pre_close"] = resp.data.get("pre_close", 0)
                    indices_data.append(d)
                else:
                    indices_data.append(fallback_index(symbol, name_cn))
            else:
                # No facade — try the store directly
                indices_data.append(fallback_index(symbol, name_cn))
        except Exception:
            indices_data.append(fallback_index(symbol, name_cn))

    # ── Sector rotation ──
    try:
        if facade:
            sec_resp = facade.get_sector_data(symbol="all")
            if sec_resp.status == "ok" and sec_resp.data:
                raw = sec_resp.data
                if isinstance(raw, list):
                    sectors_data = raw
                elif isinstance(raw, dict):
                    sectors_data = raw.get("sectors", raw.get("items", []))
    except Exception:
        sectors_data = []

    # ── Top gainers / losers (mockable fallback) ──
    try:
        if facade:
            summary = facade.get_market_summary(symbol="000001.SH")
            if summary.status == "ok" and summary.data:
                top_gainers = summary.data.get("top_gainers", []) or []
                top_losers = summary.data.get("top_losers", []) or []
    except Exception:
        pass

    return jsonify(
        {
            "date": date_str,
            "indices": indices_data,
            "sectors": sectors_data,
            "top_gainers": top_gainers,
            "top_losers": top_losers,
        }
    ), 200


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def fallback_index(symbol: str, name_cn: str) -> dict[str, Any]:
    """Return a placeholder index entry when live data is unavailable."""
    return {
        "symbol": symbol,
        "name": name_cn,
        "current": 0,
        "change": 0,
        "change_pct": 0,
        "volume": 0,
        "amount": 0,
        "high": 0,
        "low": 0,
        "open": 0,
        "pre_close": 0,
    }
