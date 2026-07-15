"""Market / analysis API routes — composite snapshots and strategy listing.

All routes return JSON.  Error responses follow ``{"error": ..., "status": N}``.

No heavy ``tradingagents.astock`` imports at module level.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import pandas as pd
from flask import Blueprint, Response, current_app, jsonify, request
from .envelope import error_response

from ._helpers import bounded_int_arg, df_to_json, get_store, sanitise_records

logger = logging.getLogger(__name__)

bp = Blueprint("market", __name__)

AVAILABLE_STRATEGIES = [
    {"name": "MovingAverageTrend", "description": "Dual moving average trend following"},
    {"name": "BullTrend", "description": "Bull market trend strategy"},
    {"name": "ValueAverage", "description": "Value averaging strategy"},
    {"name": "MeanReversion", "description": "Mean reversion trading"},
    {"name": "RSIRange", "description": "RSI range-bound trading"},
    {"name": "DefensiveMomentum", "description": "Defensive momentum strategy"},
    {"name": "PutWrite", "description": "Put write / cash-secured put strategy"},
    {"name": "MACDTrend", "description": "MACD golden/death cross trend following"},
    {"name": "BollingerBands", "description": "Bollinger Bands mean reversion"},
    {"name": "GridTrading", "description": "Fixed grid-level trading strategy"},
    {"name": "StockFlow", "description": "Multi-strategy signal cascade (AND/OR/MAJORITY/CASCADE)"},
    {"name": "MomentumRotation", "description": "Leading stock momentum rotation (portfolio)"},
]


# ---------------------------------------------------------------------------
# Source inference helpers
# ---------------------------------------------------------------------------


def _resolve_source(
    store: Any,
    symbol: str,
    kline_bars: list[dict[str, Any]],
    valuations: list[dict[str, Any]],
) -> str:
    """Try to determine the data source for *symbol*."""
    if kline_bars:
        src = kline_bars[-1].get("source") or ""
        if src:
            return str(src)
    if valuations:
        src = valuations[-1].get("source") or ""
        if src:
            return str(src)
    return "store"


def _resolve_updated_at(
    kline_bars: list[dict[str, Any]],
    valuations: list[dict[str, Any]],
) -> str:
    """Return the most recent ``created_at`` timestamp, or empty string."""
    ts = ""
    for src in (kline_bars, valuations):
        if src:
            ts = (src[-1].get("created_at") or "") or ts
            if ts:
                if isinstance(ts, datetime):
                    ts = ts.isoformat()
                break
    return str(ts) if ts else ""


# ---------------------------------------------------------------------------
# GET /api/v1/market/summary
# ---------------------------------------------------------------------------


@bp.route("/market/summary")
def market_summary() -> tuple[Response, int]:
    """Composite market snapshot for a symbol.

    Query params:
        symbol (str) — required
    """
    symbol = request.args.get("symbol", "")
    if not symbol:
        return error_response("symbol is required", 400)

    try:
        store = get_store()
        # Summary views only need a bounded recent window.  Loading an entire
        # intraday history here would inflate both DuckDB work and JSON output.
        try:
            kline_limit = bounded_int_arg("kline_limit", 120, minimum=1, maximum=500)
        except ValueError:
            return error_response("invalid_kline_limit", 400)
        kline_df = store.query_kline(symbol, interval="1d", limit=kline_limit)
        val_df = store.query_valuations(symbol)
        indicators_df = store.query_market_indicators(symbol)

        kline_bars = df_to_json(kline_df)
        valuations = df_to_json(val_df)
        indicators = df_to_json(indicators_df)

        # If store has no data, try live provider chain
        if not kline_bars:
            try:
                from tradingagents.astock.data_sources import AStockDataFacade
                facade = AStockDataFacade()
                # Get kline
                kr = facade.get_kline(symbol=symbol, interval="1d", limit=120)
                if kr.status == "ok" and kr.data and kr.data.get("bars"):
                    kline_bars = kr.data["bars"]
                # Get valuation
                vr = facade.get_valuation(symbol=symbol)
                if vr.status == "ok" and vr.data:
                    valuations = [vr.data]
                # Mark source
                source_tag = kr.meta.get("source", "live") if kr.status == "ok" else "store"
            except Exception as provider_err:
                source_tag = "store"
        else:
            source_tag = _resolve_source(store, symbol, kline_bars, valuations)

        # Latest close price & basic stats
        latest_bar = kline_bars[-1] if kline_bars else {}
        latest_val = valuations[-1] if valuations else {}

        return jsonify(
            {
                "symbol": symbol,
                "latest_price": latest_bar.get("close", 0),
                "latest_date": latest_bar.get("trade_date", ""),
                "source": source_tag,
                "updated_at": _resolve_updated_at(kline_bars, valuations),
                "kline_bars": kline_bars,
                "kline_limit": kline_limit,
                "valuations": valuations[-10:] if len(valuations) > 10 else valuations,
                "indicators": indicators[-10:] if len(indicators) > 10 else indicators,
                "pe": latest_val.get("pe", 0),
                "pb": latest_val.get("pb", 0),
                "market_cap": latest_val.get("market_cap", 0),
            }
        ), 200
    except Exception as exc:
        return error_response(str(exc), 500)


# ---------------------------------------------------------------------------
# GET /api/v1/market/strategies
# ---------------------------------------------------------------------------


@bp.route("/market/strategies")
def list_strategies() -> tuple[Response, int]:
    """Return the list of available backtest strategies."""
    return jsonify({"strategies": AVAILABLE_STRATEGIES}), 200


# ---------------------------------------------------------------------------
# GET /api/v1/market/regime?symbol=000300.SH
# ---------------------------------------------------------------------------


@bp.route("/market/regime")
def market_regime() -> tuple[Response, int]:
    """实时市场状态分析（4 维度）。

    Query params:
        symbol : str  指数代码（默认 000300.SH 沪深 300）。
        lookback : int  回溯天数（默认 120）。

    Returns
    -------
    JSON with ``composite_score``, ``verdict``, ``recommended_strategies``, ``dimensions``.
    """
    symbol = request.args.get("symbol", "000300.SH").strip()
    try:
        lookback = int(request.args.get("lookback", 120))
    except (TypeError, ValueError):
        return error_response("invalid_lookback", 400)
    if lookback < 1 or lookback > 1000:
        return error_response("invalid_lookback", 400)
    end_date = datetime.now().strftime("%Y-%m-%d")

    try:
        from tradingagents.astock.data_sources import AStockDataFacade

        facade = AStockDataFacade()
        resp = facade.get_kline(symbol=symbol, interval="1d")
        if resp.status != "ok" or not resp.data or not resp.data.get("bars"):
            return error_response(
                "market_regime_data_unavailable", 503, code="market_regime_data_unavailable"
            )

        bars = resp.data["bars"]
        df = pd.DataFrame(bars)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()
        for col in ("open", "high", "low", "close", "volume"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        if lookback and len(df) > lookback:
            df = df.iloc[-lookback:]

        from tradingagents.astock.analysis.market_analyzer import analyze_regime_from_df

        regime = analyze_regime_from_df(df)
        return jsonify(regime), 200

    except Exception as exc:
        logger.exception("Market regime analysis failed for %s", symbol)
        return error_response("market_regime_failed", 500, code="market_regime_failed")


# ---------------------------------------------------------------------------
# GET /api/v1/market/recap — Daily market recap report
# ---------------------------------------------------------------------------

MAJOR_INDICES = [
    {"symbol": "000001.SH", "name": "上证指数"},
    {"symbol": "399001.SZ", "name": "深证成指"},
    {"symbol": "399006.SZ", "name": "创业板指"},
    {"symbol": "000300.SH", "name": "沪深300"},
    {"symbol": "000016.SH", "name": "上证50"},
]


@bp.route("/market/recap", methods=["GET", "POST"])
def daily_market_recap() -> tuple[Response, int]:
    """Generate a structured daily market recap report.

    GET — returns recap for the most recent trading day.
    POST — accepts a specific trade_date.

    Query params:
        trade_date (str, optional) — YYYY-MM-DD
    """
    try:
        if request.method == "POST":
            body = request.get_json(silent=True) or {}
            trade_date = body.get("trade_date")
        else:
            trade_date = request.args.get("trade_date")

        from tradingagents.astock.data_sources import AStockDataFacade

        facade = AStockDataFacade()
        indices_data = []
        total_adv = {"up": 0, "down": 0, "flat": 0}
        sector_strength = []
        risk_flags = []

        for idx in MAJOR_INDICES:
            symbol = idx["symbol"]
            name = idx["name"]
            try:
                resp = facade.get_kline(symbol=symbol, interval="1d", limit=5)
                if resp.status == "ok" and resp.data and resp.data.get("bars"):
                    bars = resp.data["bars"]
                    latest = bars[-1]
                    prev = bars[-2] if len(bars) >= 2 else latest
                    close = float(latest.get("close", 0) or 0)
                    prev_close = float(prev.get("close", 0) or 0)
                    change_pct = ((close - prev_close) / prev_close * 100) if prev_close > 0 else 0
                    volume = float(latest.get("volume", 0) or 0)

                    indices_data.append({
                        "symbol": symbol,
                        "name": name,
                        "close": round(close, 2),
                        "change_pct": round(change_pct, 2),
                        "volume": volume,
                        "source": resp.source or "facade",
                    })

                    if change_pct > 0.1:
                        total_adv["up"] += 1
                    elif change_pct < -0.1:
                        total_adv["down"] += 1
                    else:
                        total_adv["flat"] += 1
            except Exception as exc:
                logger.debug("Failed to fetch sector data: %s", exc)

        # Sector strength
        try:
            sector_resp = facade.get_sector_ranking()
            if sector_resp.status == "ok" and sector_resp.data:
                sectors = sector_resp.data.get("sectors", [])
                sorted_sectors = sorted(
                    sectors,
                    key=lambda s: float(s.get("change_pct", 0) or 0),
                    reverse=True,
                )
                sector_strength = [
                    {
                        "name": s.get("name", ""),
                        "change_pct": round(float(s.get("change_pct", 0) or 0), 2),
                        "lead_stock": s.get("lead_stock", ""),
                    }
                    for s in sorted_sectors[:10]
                ]
        except Exception as exc:
            logger.debug("Failed to fetch risk flag data: %s", exc)

        # Risk flags
        if indices_data:
            sh = next((i for i in indices_data if i["symbol"] == "000001.SH"), None)
            if sh and sh["change_pct"] < -1.5:
                risk_flags.append("上证指数跌幅超过1.5%，注意风险控制")

        recap_date = trade_date or date.today().isoformat()

        return jsonify({
            "trade_date": recap_date,
            "generated_at": datetime.now().isoformat(),
            "indices": indices_data,
            "advance_decline": total_adv,
            "sector_strength": sector_strength,
            "risk_flags": risk_flags,
            "status": "ok",
            "research_only": True,
        }), 200
    except Exception as exc:
        logger.exception("daily_market_recap failed")
        return error_response(str(exc), 500)
