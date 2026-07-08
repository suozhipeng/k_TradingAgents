"""Daily market review API routes — FR-11.

Provides a composite daily review endpoint aggregating:
- Major A-share index snapshots (5 indices)
- Sector rotation with performance ranking
- Advance/decline statistics (market breadth)
- Northbound capital flow
- Dragon & tiger board highlights
- Top gainers/losers

All routes return JSON.  Error responses follow ``{"error": ..., "status": N}``.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request

logger = logging.getLogger(__name__)

bp = Blueprint("daily", __name__)

_INDEX_MAP: dict[str, str] = {
    "000001.SH": "上证指数",
    "399001.SZ": "深证成指",
    "399006.SZ": "创业板指",
    "000300.SH": "沪深300",
    "000016.SH": "上证50",
}


def _facade() -> Any:
    """Return the app's AStockDataFacade instance (or None)."""
    return current_app.config.get("DATA_FACADE")


# ---------------------------------------------------------------------------
# GET /api/v1/daily/review?date=2026-07-05
# ---------------------------------------------------------------------------


@bp.route("/daily/review")
def daily_review() -> tuple[Response, int]:
    """Aggregate daily market review for major A-share indexes.

    Query params:
        date (str, optional) — trade date in ``YYYY-MM-DD`` format
            (defaults to today).

    Returns
    -------
    JSON with:
        - ``date`` — the review date
        - ``indices`` — 5 major index snapshots
        - ``sectors`` — sector performance ranking (top 20)
        - ``breadth`` — advance/decline/limit_up/limit_down counts
        - ``northbound`` — HGT/SGT flow data
        - ``dragon_tiger`` — top net buyers/sellers
        - ``top_gainers`` — top 10 gainers
        - ``top_losers`` — top 10 losers
        - ``regime`` — market regime verdict (if available)
    """
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    facade = _facade()

    # ── Collect all sections in parallel ──
    indices_data = _collect_indices(facade)
    sectors_data = _collect_sectors(facade)
    breadth_data = _collect_breadth(facade)
    northbound_data = _collect_northbound(facade)
    dragon_tiger_data = _collect_dragon_tiger(facade)
    top_gainers, top_losers = _collect_movers(facade)
    regime_data = _collect_regime(facade)

    return jsonify({
        "date": date_str,
        "indices": indices_data,
        "sectors": sectors_data,
        "breadth": breadth_data,
        "northbound": northbound_data,
        "dragon_tiger": dragon_tiger_data,
        "top_gainers": top_gainers,
        "top_losers": top_losers,
        "regime": regime_data,
    }), 200


# ---------------------------------------------------------------------------
# Data collection helpers
# ---------------------------------------------------------------------------


def _collect_indices(facade: Any) -> list[dict[str, Any]]:
    """Collect snapshots for all 5 major indices."""
    indices: list[dict[str, Any]] = []
    for symbol, name_cn in _INDEX_MAP.items():
        try:
            if facade:
                resp = facade.get_market_summary(symbol=symbol)
                if resp.status == "ok" and resp.data:
                    d: dict[str, Any] = {
                        "symbol": symbol,
                        "name": name_cn,
                    }
                    d["current"] = resp.data.get("current", resp.data.get("price", 0))
                    d["change"] = resp.data.get("change", resp.data.get("change_pct", 0))
                    d["change_pct"] = resp.data.get("change_pct", 0)
                    d["volume"] = resp.data.get("volume", 0)
                    d["amount"] = resp.data.get("amount", 0)
                    d["high"] = resp.data.get("high", 0)
                    d["low"] = resp.data.get("low", 0)
                    d["open"] = resp.data.get("open", 0)
                    d["pre_close"] = resp.data.get("pre_close", 0)
                    indices.append(d)
                else:
                    indices.append(fallback_index(symbol, name_cn))
            else:
                indices.append(fallback_index(symbol, name_cn))
        except Exception:
            indices.append(fallback_index(symbol, name_cn))
    return indices


def _collect_sectors(facade: Any) -> list[dict[str, Any]]:
    """Collect sector performance ranking (top 20)."""
    sectors: list[dict[str, Any]] = []
    try:
        # Try facade sector ranking first
        if facade:
            try:
                sec_resp = facade.get_sector_ranking(limit=20)
                if sec_resp.status == "ok" and sec_resp.data:
                    raw = sec_resp.data
                    if isinstance(raw, list):
                        sectors = raw[:20]
                    elif isinstance(raw, dict):
                        sectors = raw.get("sectors", raw.get("items", []))[:20]
            except (AttributeError, TypeError):
                # get_sector_ranking may not exist on older facade versions
                pass

        # Fallback: try routes_market_data sectors endpoint via store
        if not sectors:
            store = current_app.config.get("STORE")
            if store:
                try:
                    df = store.query_sql(
                        'SELECT symbol, name, change_pct, leader, up_count, down_count '
                        'FROM sectors ORDER BY change_pct DESC LIMIT 20'
                    )
                    if df is not None and not df.empty:
                        sectors = df.to_dict(orient="records")
                except Exception:
                    pass
    except Exception as exc:
        logger.warning("Failed to collect sectors: %s", exc)

    return sectors[:20] if sectors else []


def _collect_breadth(facade: Any) -> dict[str, Any]:
    """Collect market breadth (advance/decline/limit-up/limit-down)."""
    try:
        store = current_app.config.get("STORE")
        if store:
            try:
                df = store.query_sql(
                    'SELECT '
                    'SUM(CASE WHEN change_pct > 0.02 THEN 1 ELSE 0 END) as advancing, '
                    'SUM(CASE WHEN change_pct < -0.02 THEN 1 ELSE 0 END) as declining, '
                    'SUM(CASE WHEN change_pct >= 0.095 THEN 1 ELSE 0 END) as limit_up, '
                    'SUM(CASE WHEN change_pct <= -0.095 THEN 1 ELSE 0 END) as limit_down, '
                    'COUNT(*) as total '
                    'FROM valuations WHERE trade_date = (SELECT MAX(trade_date) FROM valuations)'
                )
                if df is not None and not df.empty:
                    row = df.iloc[0]
                    return {
                        "advancing": int(row.get("advancing", 0)),
                        "declining": int(row.get("declining", 0)),
                        "limit_up": int(row.get("limit_up", 0)),
                        "limit_down": int(row.get("limit_down", 0)),
                        "total": int(row.get("total", 0)),
                        "ratio": round(
                            row.get("advancing", 0) / max(row.get("declining", 0), 1), 2
                        ),
                    }
            except Exception:
                pass
    except Exception as exc:
        logger.warning("Failed to collect breadth: %s", exc)

    # Fallback: mock breadth
    return {
        "advancing": 0,
        "declining": 0,
        "limit_up": 0,
        "limit_down": 0,
        "total": 0,
        "ratio": 0,
        "mock": True,
    }


def _collect_northbound(facade: Any) -> list[dict[str, Any]]:
    """Collect northbound capital flow (HGT/SGT)."""
    try:
        store = current_app.config.get("STORE")
        if store:
            try:
                df = store.query_sql(
                    'SELECT trade_date, hgt_yi, sgt_yi, hgt_accum, sgt_accum '
                    'FROM northbound_flow ORDER BY trade_date DESC LIMIT 5'
                )
                if df is not None and not df.empty:
                    return df.to_dict(orient="records")
            except Exception:
                pass
    except Exception as exc:
        logger.warning("Failed to collect northbound: %s", exc)
    return []


def _collect_dragon_tiger(facade: Any) -> dict[str, Any]:
    """Collect dragon & tiger board highlights."""
    try:
        store = current_app.config.get("STORE")
        if store:
            try:
                df = store.query_sql(
                    'SELECT symbol, name, net_buy, buy_amount, sell_amount, frequency '
                    'FROM dragon_tiger ORDER BY net_buy DESC LIMIT 5'
                )
                top_buyers = df.to_dict(orient="records") if df is not None and not df.empty else []

                df2 = store.query_sql(
                    'SELECT symbol, name, net_buy, buy_amount, sell_amount, frequency '
                    'FROM dragon_tiger ORDER BY net_buy ASC LIMIT 5'
                )
                top_sellers = df2.to_dict(orient="records") if df2 is not None and not df2.empty else []

                return {"top_buyers": top_buyers, "top_sellers": top_sellers}
            except Exception:
                pass
    except Exception as exc:
        logger.warning("Failed to collect dragon_tiger: %s", exc)
    return {"top_buyers": [], "top_sellers": []}


def _collect_movers(facade: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Collect top gainers and losers."""
    top_gainers: list[dict[str, Any]] = []
    top_losers: list[dict[str, Any]] = []
    try:
        store = current_app.config.get("STORE")
        if store:
            try:
                df = store.query_sql(
                    'SELECT symbol, name, change_pct, price '
                    'FROM valuations ORDER BY change_pct DESC LIMIT 10'
                )
                if df is not None and not df.empty:
                    top_gainers = df.to_dict(orient="records")

                df2 = store.query_sql(
                    'SELECT symbol, name, change_pct, price '
                    'FROM valuations ORDER BY change_pct ASC LIMIT 10'
                )
                if df2 is not None and not df2.empty:
                    top_losers = df2.to_dict(orient="records")
            except Exception:
                pass
    except Exception as exc:
        logger.warning("Failed to collect movers: %s", exc)
    return top_gainers, top_losers


def _collect_regime(facade: Any) -> dict[str, Any]:
    """Collect market regime analysis."""
    try:
        if facade:
            try:
                resp = facade.get_market_regime(symbol="000001.SH", lookback="60d")
                if resp.status == "ok" and resp.data:
                    return resp.data
            except (AttributeError, TypeError):
                pass
    except Exception as exc:
        logger.warning("Failed to collect regime: %s", exc)
    return {}


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
