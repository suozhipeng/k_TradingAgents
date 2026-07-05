"""Dashboard overview API — aggregated data for the home page.

Provides a single ``GET /api/v1/dashboard/overview`` endpoint that returns
all the data the dashboard page needs: statistics, paper trading state,
recent backtests, recent trades, equity curves, and a global decision
summary (buy/hold/sell) from technical analysis of the watchlist.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, Response, current_app, jsonify

logger = logging.getLogger(__name__)

bp = Blueprint("dashboard", __name__)


def _sanitize_nan(records: list[dict]) -> None:
    """Replace NaN/Inf with None in-place for valid JSON."""
    import math
    from datetime import datetime

    for record in records:
        for k, v in record.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                record[k] = None
            elif isinstance(v, datetime):
                record[k] = v.strftime("%Y-%m-%d")
            elif hasattr(v, "isoformat"):
                record[k] = v.isoformat()


def _store() -> Any:
    return current_app.config["STORE"]


def _get_paper_trader() -> Any:
    """Lazy import + instantiate PaperTrader (shared with routes_paper)."""
    # Reuse the global paper trader from routes_paper module
    from tradingagents.astock.api.routes_paper import _get_trader as _paper_get_trader
    return _paper_get_trader()


def _get_paper_state() -> dict[str, Any]:
    """Return paper state as a plain dict, or empty defaults on error."""
    try:
        trader = _get_paper_trader()
        state = trader.get_state()
        if hasattr(state, "model_dump"):
            return state.model_dump()
        if isinstance(state, dict):
            return state
        return {
            "positions": getattr(state, "positions", {}),
            "cash": getattr(state, "cash", 0.0),
            "total_value": getattr(state, "total_value", 0.0),
            "pnl": getattr(state, "pnl", 0.0),
            "trades": getattr(state, "trades", []),
        }
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# GET /api/v1/dashboard/overview
# ---------------------------------------------------------------------------


@bp.route("/dashboard/overview")
def dashboard_overview() -> tuple[Response, int]:
    """Aggregated dashboard data.

    Returns JSON with:
        statistics (dict) — counts & summary numbers
        paper_state (dict) — paper trading account snapshot
        recent_backtests (list) — latest 5 backtest results
        recent_trades (list) — latest 10 paper trades
        latest_equity_curve (list) — equity curve of the most recent backtest
    """
    try:
        store = _store()
        stats = store.get_table_stats() if hasattr(store, "get_table_stats") else {}

        # Count unique symbols across kline, valuation tables
        symbols_tracked = 0
        for table in ("kline_bars", "valuations"):
            t_stats = stats.get(table, {})
            if t_stats.get("rows", 0) > 0:
                try:
                    df = store.query_sql(f'SELECT count(DISTINCT symbol) as cnt FROM "{table}"')
                    symbols_tracked += int(df.iloc[0]["cnt"]) if not df.empty else 0
                except Exception:
                    symbols_tracked += 1 if t_stats.get("rows", 0) > 0 else 0

        backtests_total = stats.get("backtest_results", {}).get("rows", 0) if stats else 0

        # Paper state
        paper_positions = 0
        paper_return_pct = 0.0
        paper_total_value = 0.0
        try:
            pstate = _get_paper_state()
            if pstate:
                positions = pstate.get("positions", {})
                paper_positions = len(positions) if isinstance(positions, dict) else len(positions) if isinstance(positions, (list, tuple)) else 0
                pnl_val = pstate.get("pnl", 0.0) or 0.0
                cash = pstate.get("cash", 100000.0) or 100000.0
                total_value = pstate.get("total_value", 0.0) or 0.0
                paper_total_value = total_value
                paper_return_pct = pnl_val / (total_value - pnl_val) if (total_value - pnl_val) > 0 else 0.0
        except Exception:
            pass

        # Recent backtests (latest 5)
        recent_backtests = []
        try:
            bt_df = store.get_backtest_results()
            if bt_df is not None and not bt_df.empty:
                bt_list = bt_df.sort_values("end_date", ascending=False).head(5)
                recent_backtests = bt_list.to_dict(orient="records")
                _sanitize_nan(recent_backtests)
        except Exception:
            pass

        # Latest equity curve from most recent backtest (periods stored in params_json)
        import json as _json
        latest_equity_curve = []
        if recent_backtests:
            latest = recent_backtests[0]
            periods = []
            # Try direct periods column first, then extract from params_json
            if "periods" in latest and latest["periods"]:
                periods = latest["periods"]
            elif latest.get("params_json"):
                try:
                    pj = _json.loads(latest["params_json"]) if isinstance(latest["params_json"], str) else latest["params_json"]
                    periods = pj.get("periods", [])
                except (_json.JSONDecodeError, TypeError, AttributeError):
                    periods = []
            if isinstance(periods, str):
                try:
                    periods = _json.loads(periods)
                except (_json.JSONDecodeError, TypeError):
                    periods = []
            latest_equity_curve = [
                {"period": p["period"], "value": p["end_value"]}
                for p in (periods or [])
            ][-30:]  # last 30 periods for mini chart

        # Recent paper trades
        recent_trades = []
        try:
            trades_df = store.get_paper_trades()
            if trades_df is not None and not trades_df.empty:
                trades_list = trades_df.sort_values(
                    "trade_date", ascending=False
                ).head(10)
                recent_trades = trades_list.to_dict(orient="records")
                _sanitize_nan(recent_trades)
        except Exception:
            pass

        # Paper positions (for pie chart) — from paper state
        paper_positions_detail = []
        try:
            pstate = _get_paper_state()
            if pstate:
                positions = pstate.get("positions", {})
                if isinstance(positions, dict):
                    paper_positions_detail = [
                        {
                            "symbol": sym,
                            "value": abs(qty) * 100.0,
                            "pnl": 0,
                            "quantity": qty,
                        }
                        for sym, qty in positions.items()
                        if qty > 0
                    ]
                elif isinstance(positions, list):
                    paper_positions_detail = [
                        {
                            "symbol": p.get("symbol", "?"),
                            "value": abs(p.get("quantity", 0) * p.get("current_price", 0)),
                            "pnl": p.get("pnl", 0),
                            "quantity": p.get("quantity", 0),
                        }
                        for p in positions
                        if p.get("quantity", 0) > 0
                    ]
        except Exception:
            pass

        # Paper equity curve from stored trades
        paper_equity_curve = _compute_paper_equity_curve(store)

        # Global decision summary from watchlist technical analysis
        decision_summary = _get_decision_summary()

        return jsonify(
            {
                "statistics": {
                    "symbols_tracked": symbols_tracked,
                    "backtests_total": backtests_total,
                    "paper_positions": paper_positions,
                    "paper_return_pct": paper_return_pct,
                    "paper_total_value": paper_total_value,
                },
                "paper_positions": paper_positions_detail,
                "recent_backtests": _sanitize(recent_backtests),
                "recent_trades": _sanitize(recent_trades),
                "latest_equity_curve": latest_equity_curve,
                "paper_equity_curve": paper_equity_curve,
                "decision_summary": decision_summary,
            }
        ), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


def _compute_paper_equity_curve(store: Any) -> list[dict]:
    """Build an equity curve from stored paper trades.

    Walks all trades chronologically, starting with 100 000 cash,
    and computes total_value = cash + position_value at each trade date.
    Position value is marked at the trade price of that date.
    """
    import pandas as pd

    try:
        df = store.get_paper_trades()
        if df is None or df.empty:
            return []
        df = df.sort_values("trade_date").reset_index(drop=True)

        initial_cash = 100000.0
        cash = initial_cash
        positions: dict[str, float] = {}
        cost_basis: dict[str, float] = {}
        latest_prices: dict[str, float] = {}
        curve = []

        for _, row in df.iterrows():
            symbol = row.get("symbol", "")
            direction = str(row.get("direction", "")).lower()
            price = float(row.get("price", 0))
            volume = float(row.get("volume", 0))
            fees = float(row.get("fees", 0))
            date_str = str(row.get("trade_date", ""))[:10]

            # Update latest known price for this symbol
            latest_prices[symbol] = price

            if direction == "buy":
                cost = price * volume + fees
                cash -= cost
                positions[symbol] = positions.get(symbol, 0) + volume
                old_basis = cost_basis.get(symbol, 0)
                total_shares = positions[symbol]
                cost_basis[symbol] = old_basis + cost
            elif direction == "sell":
                revenue = price * volume - fees
                cash += revenue
                current_shares = positions.get(symbol, 0)
                sold = min(volume, current_shares)
                positions[symbol] = current_shares - sold
                if positions[symbol] <= 0:
                    positions.pop(symbol, None)
                    cost_basis.pop(symbol, None)

            # Mark position value using each symbol's latest price
            pos_value = sum(
                positions[s] * latest_prices.get(s, 0)
                for s in list(positions.keys())
            )
            total_value = cash + pos_value
            curve.append({"period": date_str, "value": round(total_value, 2)})

        return curve[-60:]  # last 60 points
    except Exception:
        return []


def _sanitize(rows: list[dict]) -> list[dict]:
    """Convert non-serializable objects in a list of dicts."""
    import datetime
    import decimal

    clean: list[dict] = []
    for row in rows:
        safe = {}
        for k, v in row.items():
            if isinstance(v, (datetime.datetime, datetime.date)):
                safe[k] = v.isoformat()
            elif isinstance(v, decimal.Decimal):
                safe[k] = float(v)
            elif isinstance(v, bytes):
                safe[k] = v.decode("utf-8", errors="replace")
            else:
                try:
                    # Test serializability
                    import json

                    json.dumps({k: v})
                    safe[k] = v
                except (TypeError, OverflowError, ValueError):
                    safe[k] = str(v)
        clean.append(safe)
    return clean


# ---------------------------------------------------------------------------
# Decision summary helper
# ---------------------------------------------------------------------------


def _get_decision_summary() -> dict[str, Any]:
    """Compute buy/hold/sell summary from watchlist technical analysis.

    Reuses the same logic as routes_analysis but returns a lightweight
    summary dict suitable for the dashboard overview.
    """
    counts = {"buy": 0, "hold": 0, "sell": 0}
    top_picks: list[dict] = []

    try:
        from tradingagents.astock.api.routes_analysis import _load_watchlist, _analyze_stock_symbol

        items = _load_watchlist()
        if items:
            for item in items:
                symbol = item.get("symbol", "").strip()
                name = item.get("name", symbol)
                if not symbol:
                    continue
                result = _analyze_stock_symbol(symbol, name)
                rating = result.get("rating", "hold")
                if rating in counts:
                    counts[rating] += 1
                if rating == "buy" and len(top_picks) < 5:
                    top_picks.append({
                        "symbol": result["symbol"],
                        "name": result["name"],
                        "score": result["score"],
                        "signal": result["signal"],
                    })
    except Exception as exc:
        logger.warning("Failed to compute decision summary: %s", exc)

    total = counts["buy"] + counts["hold"] + counts["sell"]
    return {
        "total": total,
        "counts": counts,
        "top_picks": top_picks,
        "dominant": max(counts, key=counts.get) if total > 0 else "hold",
        "research_only": True,
        "actionable": False,
    }
