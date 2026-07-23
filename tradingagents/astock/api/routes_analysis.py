"""Watchlist technical analysis API — thin wrapper around _analysis_engine.

POST /api/v1/analysis/watchlist  — analyze all watchlist stocks using
  pure technical indicators (RSI, MA crossover, volume).  No LLM calls.

All core logic lives in ``_analysis_engine.py`` so that
``routes_dashboard`` and ``routes_watchlist`` can reuse the same functions.

Summary response includes ``research_only`` count for stocks with
insufficient data or analysis errors (rating = "hold" with signal
in ("数据不足", "分析异常")).
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, Response, jsonify, request

from ._analysis_engine import analyze_stock_symbol, load_watchlist
from ._helpers import get_store
from .envelope import error_response
from tradingagents.astock.analysis.stock_facts import StockFactsEngine

logger = logging.getLogger(__name__)

bp = Blueprint("analysis", __name__)


# ---------------------------------------------------------------------------
# POST /api/v1/analysis/watchlist
# ---------------------------------------------------------------------------


@bp.route("/analysis/watchlist", methods=["POST"])
def analyze_watchlist() -> tuple[Response, int]:
    items = load_watchlist()
    if not items:
        return jsonify({
            "stocks": [],
            "summary": {"total": 0, "buy": 0, "hold": 0, "sell": 0, "research_only": 0},
            "message": "暂无自选股",
        }), 200

    results: list[dict[str, Any]] = []
    for item in items:
        symbol = item.get("symbol", "").strip()
        name = item.get("name", symbol)
        if not symbol:
            continue
        result = analyze_stock_symbol(symbol, name)
        results.append(result)

    counts = {"buy": 0, "hold": 0, "sell": 0}
    research_only_count = 0
    for r in results:
        rating = r.get("rating", "hold")
        if rating in counts:
            counts[rating] += 1
        else:
            research_only_count += 1
        if rating == "hold":
            signal = r.get("signal", "")
            if signal in ("数据不足", "分析异常"):
                research_only_count += 1

    rating_order = {"buy": 0, "hold": 1, "sell": 2}
    results.sort(key=lambda r: (rating_order.get(r.get("rating", "hold"), 9), -r.get("score", 0)))

    return jsonify({
        "stocks": results,
        "summary": {
            "total": len(results),
            "buy": counts["buy"],
            "hold": counts["hold"],
            "sell": counts["sell"],
            "research_only": research_only_count,
        },
    }), 200


@bp.route("/analysis/stock/<symbol>", methods=["GET", "POST"])
def analyze_stock(symbol: str) -> tuple[Response, int]:
    """Return deterministic stock facts from Canonical DuckDB only."""
    from .envelope import ok, fail
    symbol = symbol.strip()
    if not symbol:
        return fail("symbol is required", 400)
    payload = request.get_json(silent=True) or {}
    as_of = request.args.get("as_of") or payload.get("as_of")
    store = get_store()
    try:
        sql = 'SELECT * FROM "kline_bars" WHERE symbol = ?'
        params: list[str] = [symbol]
        if as_of:
            sql += " AND trade_date <= ?"
            params.append(as_of)
        sql += " ORDER BY trade_date"
        frame = store.conn.execute(sql, params).fetchdf()
        if frame.empty:
            return ok({"status": "not_initialized", "symbol": symbol, "facts": [], "risk_signals": []})
        report = StockFactsEngine(store).run(frame, symbol=symbol, as_of=as_of)
        return ok(report)
    except ValueError as exc:
        return fail(str(exc), 400)
    except Exception as exc:
        logger.exception("stock analysis failed for %s", symbol)
        return fail(f"stock analysis failed: {exc}", 500)


# V1.7 POST /api/v1/analysis/stocks — batch single-symbol analysis
@bp.route("/analysis/stocks", methods=["POST"])
def analyze_stocks() -> tuple[Response, int]:
    """Analyze one or more stocks. Accepts {symbol} or {symbols: [...]}."""
    from .envelope import ok, fail
    body = request.get_json(silent=True) or {}
    symbols = body.get("symbols") or [body.get("symbol")] if body.get("symbol") else []
    if not symbols:
        return fail("symbol or symbols is required", 400)
    store = get_store()
    results = []
    for sym in symbols[:10]:  # max 10 per request
        try:
            sql = 'SELECT * FROM "kline_bars" WHERE symbol = ? ORDER BY trade_date'
            frame = store.conn.execute(sql, [sym]).fetchdf()
            if frame.empty:
                results.append({"symbol": sym, "status": "not_initialized"})
                continue
            report = StockFactsEngine(store).run(frame, symbol=sym)
            report["status"] = "ok"
            results.append(report)
        except Exception as exc:
            results.append({"symbol": sym, "status": "error", "error": str(exc)[:100]})
    return ok({"results": results, "count": len(results)})
