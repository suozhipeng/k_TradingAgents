"""Trade execution API routes — individual order placement and quote lookup.

All routes return JSON.  Error responses follow ``{"error": ..., "status": N}``.

Uses lazy imports for ``tradingagents.astock.execution.paper_trader``.
"""

from __future__ import annotations

import re
from datetime import datetime
from hashlib import sha256
from threading import Lock
from typing import Any

import requests
from flask import Blueprint, Response, jsonify, request

bp = Blueprint("trade", __name__)

# Global paper trader instance (shared with paper blueprint)
_trader: Any = None

# ── 实时报价缓存 ───────────────────────────────────────────────────────

_quote_cache: dict[str, dict[str, Any]] = {}   # symbol → quote dict
_cache_lock = Lock()
_CACHE_TTL_SECONDS = 60                          # 缓存有效期 60 秒

EM_QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"
SINA_QUOTE_URL = "https://hq.sinajs.cn/list={code}"

EM_FIELDS = (
    "f43,f44,f45,f46,f47,f48,f50,f51,f57,f58,"
    "f60,f116,f117,f162,f169,f170,f171,f19,f39"
)

# EastMoney secid: 1.600519 for SH, 0.300750 for SZ
def _em_secid(symbol: str) -> str:
    code = symbol.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    if symbol.endswith(".SH"):
        return f"1.{code}"
    else:
        return f"0.{code}"


def _fetch_quote_eastmoney(symbol: str) -> dict[str, Any] | None:
    """从东方财富 push2 拉取实时报价。"""
    try:
        params = {"secid": _em_secid(symbol), "fields": EM_FIELDS}
        resp = requests.get(EM_QUOTE_URL, params=params, timeout=6,
                           headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return None
        data = resp.json()
        d = data.get("data")
        if not d:
            return None
        return {
            "symbol": symbol,
            "last_price": float(d.get("f43", 0)),
            "open": float(d.get("f46", 0)),
            "high": float(d.get("f44", 0)),
            "low": float(d.get("f45", 0)),
            "change": float(d.get("f169", 0)),
            "change_pct": float(d.get("f170", 0)),
            "volume": int(d.get("f47", 0)),
            "bid": float(d.get("f19", 0)) if d.get("f19") else float(d.get("f43", 0)),
            "ask": float(d.get("f39", 0)) if d.get("f39") else float(d.get("f43", 0)),
            "turnover_rate": float(d.get("f168", 0)),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception:
        return None


def _fetch_quote_sina(symbol: str) -> dict[str, Any] | None:
    """从新浪财经拉取实时报价（fallback）。"""
    try:
        code = symbol.split(".")[0]
        market = "sh" if symbol.endswith(".SH") else "sz"
        url = SINA_QUOTE_URL.format(code=f"{market}{code}")
        resp = requests.get(url, timeout=6,
                           headers={"Referer": "https://finance.sina.com.cn"})
        if resp.status_code != 200:
            return None
        text = resp.text
        # Parse: var hq_str_sh600666="name,open,close,price,high,low,..."
        match = re.search(r'"([^"]*)"', text)
        if not match:
            return None
        fields = match.group(1).split(",")
        if len(fields) < 10:
            return None
        name = fields[0]
        open_price = float(fields[1]) if fields[1] else 0
        close_yesterday = float(fields[2]) if fields[2] else 0
        price = float(fields[3]) if fields[3] else 0
        high = float(fields[4]) if fields[4] else 0
        low = float(fields[5]) if fields[5] else 0
        bid = float(fields[6]) if fields[6] else 0
        ask = float(fields[7]) if fields[7] else 0
        volume = int(fields[8]) if fields[8] else 0
        change = round(price - close_yesterday, 2)
        change_pct = round((change / close_yesterday) * 100, 2) if close_yesterday > 0 else 0
        return {
            "symbol": symbol,
            "name": name,
            "last_price": price,
            "open": open_price,
            "high": high,
            "low": low,
            "change": change,
            "change_pct": change_pct,
            "volume": volume,
            "bid": bid if bid > 0 else price,
            "ask": ask if ask > 0 else price,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception:
        return None


def _fetch_realtime_quote(symbol: str) -> dict[str, Any] | None:
    """双源降级：新浪（格式标准）→ 东方财富 → DuckDB store → deterministic fallback"""
    result = _fetch_quote_sina(symbol)
    if result and result.get("last_price", 0) > 0:
        return result
    result = _fetch_quote_eastmoney(symbol)
    if result and result.get("last_price", 0) > 0:
        return result
    # All live APIs failed — try DuckDB store for last known price
    return _fetch_quote_from_store(symbol)


def _fetch_quote_from_store(symbol: str) -> dict[str, Any] | None:
    """从 DuckDB store 查询最近一次真实报价作为降级源。"""
    from flask import current_app
    store = current_app.config.get("STORE") if current_app else None
    if store is None:
        return None
    try:
        kline_df = store.query_kline(symbol, limit=1)
        if kline_df is not None and not kline_df.empty:
            row = kline_df.iloc[-1]
            close = float(row.get("close", 0) or 0)
            if close > 0:
                return {
                    "symbol": symbol,
                    "last_price": close,
                    "open": float(row.get("open", close)),
                    "high": float(row.get("high", close)),
                    "low": float(row.get("low", close)),
                    "volume": float(row.get("volume", 0)),
                    "change": 0.0,
                    "change_pct": 0.0,
                    "timestamp": str(row.get("trade_date", "")),
                    "source": "store",
                }
    except Exception as exc:
        logger.debug("DuckDB quote fallback failed for %s: %s", symbol, exc)
    return None


def _build_deterministic_quote(symbol: str) -> dict[str, Any]:
    """Return a stable synthetic quote for offline tests and local fallback."""
    digest = sha256(symbol.encode("utf-8")).hexdigest()
    seed = int(digest[:8], 16)
    base = 20 + (seed % 3000) / 10
    open_price = round(base * 0.995, 2)
    last_price = round(base, 2)
    high = round(base * 1.01, 2)
    low = round(base * 0.99, 2)
    change = round(last_price - open_price, 2)
    change_pct = round((change / open_price) * 100, 2) if open_price > 0 else 0.0
    volume = 100000 + (seed % 900000)
    return {
        "symbol": symbol,
        "name": symbol,
        "last_price": last_price,
        "open": open_price,
        "high": high,
        "low": low,
        "change": change,
        "change_pct": change_pct,
        "volume": volume,
        "bid": round(last_price * 0.999, 2),
        "ask": round(last_price * 1.001, 2),
        "timestamp": datetime.now().isoformat(),
    }


def _load_cached_quote(symbol: str) -> dict[str, Any] | None:
    """读取缓存（TTL 内有效）。"""
    with _cache_lock:
        cached = _quote_cache.get(symbol)
        if cached is None:
            return None
        age = (datetime.now() - cached["cached_at"]).total_seconds()
        if age > _CACHE_TTL_SECONDS:
            return None
        return dict(cached["data"])


def _save_to_cache(symbol: str, quote: dict[str, Any]) -> None:
    """写入缓存。"""
    with _cache_lock:
        _quote_cache[symbol] = {
            "data": quote,
            "cached_at": datetime.now(),
        }


def _serialize_order(result: Any) -> dict[str, Any]:
    """Keep the richer Phase 35 order model while preserving legacy API fields."""
    payload = result.model_dump()
    status_value = payload.get("status")
    if hasattr(status_value, "value"):
        status_value = status_value.value
    payload["status"] = status_value
    payload["filled"] = status_value == "filled"
    payload["quantity"] = int(payload.get("quantity", 0))
    return payload


def _get_trader() -> Any:
    global _trader
    if _trader is None:
        from tradingagents.astock.execution.paper_trader import PaperTrader

        _trader = PaperTrader()
    return _trader


# ---------------------------------------------------------------------------
# POST /api/v1/trade/order — Place an individual order
# ---------------------------------------------------------------------------


@bp.route("/trade/order", methods=["POST"])
def place_order() -> tuple[Response, int]:
    """Place a buy or sell order with specified quantity."""
    data = request.get_json(silent=True) or {}
    symbol = data.get("symbol", "").strip()
    side = data.get("side", "").strip().lower()
    price = data.get("price")
    quantity = data.get("quantity")

    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    if side not in ("buy", "sell"):
        return jsonify({"error": "side must be 'buy' or 'sell'", "status": 400}), 400
    if not isinstance(price, (int, float)) or price <= 0:
        return jsonify({"error": "price must be positive", "status": 400}), 400
    if not isinstance(quantity, int) or quantity <= 0:
        return jsonify({"error": "quantity must be a positive integer", "status": 400}), 400

    try:
        trader = _get_trader()
        # RiskGate pre-check
        from ..execution.risk_gate import RiskGate
        proposal = {
            "symbol": symbol,
            "signal": 1 if side == "buy" else -1,
            "actionable": False,
            "decision_scope": "webui_trade",
        }
        gate_result = RiskGate.check(proposal=proposal)
        if not gate_result.allowed:
            return jsonify({
                "error": f"Risk gate blocked: {gate_result.reason}",
                "status": 403,
                "blocked_by": gate_result.blocked_by,
            }), 403

        result = trader.place_order(symbol, side, float(price), int(quantity))
        return jsonify({"status": "ok", "order": _serialize_order(result)}), 200
    except ValueError as exc:
        return jsonify({"error": str(exc), "status": 400}), 400
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# GET /api/v1/trade/quote — 实时行情 (东方财富→新浪→缓存降级)
# ---------------------------------------------------------------------------


@bp.route("/trade/quote")
def get_quote() -> tuple[Response, int]:
    """GET /api/v1/trade/quote?symbol=600519.SH

    三级降级：实时拉取（东方财富）→ 实时拉取（新浪）→ 本地缓存 → 空数据
    成功拉取的实时数据自动写入缓存。
    """
    symbol = request.args.get("symbol", "").strip()
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400

    # 1. 先看缓存（TTL 内快速返回）
    cached = _load_cached_quote(symbol)
    if cached:
        return jsonify({**cached, "source": "cache"}), 200

    # 2. 实时拉取
    live = _fetch_realtime_quote(symbol)
    if live:
        _save_to_cache(symbol, live)
        return jsonify({**live, "source": "live"}), 200

    # 3. 离线兜底：返回确定性 mock quote，避免 API 在受限环境下完全不可用
    synthetic = _build_deterministic_quote(symbol)
    _save_to_cache(symbol, synthetic)
    return jsonify({**synthetic, "source": "mock"}), 200


# ---------------------------------------------------------------------------
# GET /api/v1/trade/state — Current trading state (positions, cash, P&L)
# ---------------------------------------------------------------------------


@bp.route("/trade/state")
def trade_state() -> tuple[Response, int]:
    """Return current paper trading state for the trading page."""
    try:
        trader = _get_trader()
        state = trader.get_state()
        enriched_positions = []
        for sym, shares in state.positions.items():
            # 用实际持仓价格为每条持仓查行情
            quote = _load_cached_quote(sym)
            if quote is None:
                quote = _fetch_realtime_quote(sym)
                if quote:
                    _save_to_cache(sym, quote)
            mock_price = quote["last_price"] if quote else 50.0
            cost_basis = trader._cost_basis.get(sym, 0.0)
            avg_cost = round(cost_basis / shares, 2) if shares > 0 else 0
            mkt_val = round(shares * mock_price, 2)
            pnl = round(mkt_val - cost_basis, 2)
            pnl_pct = round((pnl / cost_basis) * 100, 2) if cost_basis > 0 else 0.0
            enriched_positions.append({
                "symbol": sym,
                "shares": round(shares, 4),
                "avg_cost": avg_cost,
                "current_price": mock_price,
                "market_value": mkt_val,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "quantity": round(shares, 4),
            })

        return jsonify({
            "cash": state.cash,
            "total_value": state.total_value,
            "pnl": state.pnl,
            "positions": enriched_positions,
            "trade_count": len(state.trades),
        }), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


__all__ = ["bp"]
