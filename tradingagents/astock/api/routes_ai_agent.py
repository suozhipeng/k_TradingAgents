"""AI Agent analysis API routes."""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, Response, jsonify, request

logger = logging.getLogger(__name__)

bp = Blueprint("ai_agent", __name__)


@bp.route("/ai/analyze", methods=["POST"])
def ai_analyze() -> tuple[Response, int]:
    """Run AI agent analysis on a stock symbol.

    JSON body:
        symbol (str) — A-share stock symbol, e.g. "600519.SH"
        analysis_type (str) — "full" (default), "technical", "fundamental", "news"
    """
    body = request.get_json(silent=True) or {}
    symbol = str(body.get("symbol", "")).strip()
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    if not symbol.endswith((".SH", ".SZ")):
        symbol += ".SH"

    try:
        result = _run_analysis(symbol, body.get("analysis_type", "full"))
        return jsonify(result), 200
    except Exception as exc:
        logger.warning("AI analysis failed for %s: %s", symbol, exc)
        return jsonify({"error": str(exc), "status": 500}), 500


def _run_analysis(symbol: str, analysis_type: str = "full") -> dict[str, Any]:
    """Run analysis pipeline and return structured results."""
    from datetime import datetime

    # ── Gather context data ──
    context = _gather_context(symbol)

    # ── Try LLM reasoning (optional) ──
    llm_analysis = ""
    try:
        llm_analysis = _try_llm_analysis(symbol, context, analysis_type)
    except Exception as exc:
        llm_analysis = f"LLM analysis unavailable: {exc}"

    # ── Build response ──
    return {
        "symbol": symbol,
        "analysis_type": analysis_type,
        "timestamp": datetime.now().isoformat(),
        "context": context,
        "llm_analysis": llm_analysis,
    }


def _gather_context(symbol: str) -> dict[str, Any]:
    """Gather market data context for the symbol."""
    import json
    import urllib.request

    base = "http://127.0.0.1:5001/api/v1"

    def _fetch(path: str) -> Any:
        try:
            with urllib.request.urlopen(f"{base}{path}", timeout=10) as r:
                return json.loads(r.read().decode())
        except Exception:
            return None

    return {
        "stock_info": _fetch(f"/tv/stock-info?symbol={symbol}"),
        "market_summary": _fetch(f"/market/summary?symbol={symbol}"),
        "kline_latest": _fetch(f"/kline?symbol={symbol}&interval=1d&limit=5"),
    }


def _try_llm_analysis(
    symbol: str, context: dict[str, Any], analysis_type: str
) -> str:
    """Try to run LLM-based analysis. Returns analysis text or raises."""
    import os

    provider = os.environ.get("TRADINGAGENTS_LLM_PROVIDER", "")
    if not provider:
        raise RuntimeError("LLM not configured. Set TRADINGAGENTS_LLM_PROVIDER and API key.")

    from tradingagents.llm_clients import create_llm_client

    model = os.environ.get("TRADINGAGENTS_QUICK_THINK_LLM", "")
    if not model:
        model = os.environ.get("TRADINGAGENTS_DEEP_THINK_LLM", "gpt-4o-mini")

    client = create_llm_client(provider, model)
    llm = client.get_llm()

    # Format context
    info = context.get("stock_info") or {}
    info_text = f"名称: {info.get('name','?')} ({info.get('code','?')})\n行业: {info.get('industry','?')}\n板块: {info.get('board','?')}"

    bars = (context.get("kline_latest") or {}).get("bars", [])
    if bars:
        last = bars[-1]
        kline_text = f"最新价: {last.get('close','?')}  涨跌幅: {last.get('change_pct', 0):+.2f}%"
    else:
        kline_text = "暂无K线数据"

    focus = {
        "full": "全面的技术面、基本面、新闻情绪分析",
        "technical": "技术面分析（趋势、支撑阻力、成交量）",
        "fundamental": "基本面分析（估值、财务指标）",
        "news": "新闻情绪和舆情分析",
    }.get(analysis_type, "全面分析")

    prompt = f"""你是一位专业的A股市场分析师。请对以下股票进行{focus}。

{info_text}

{kline_text}

分析要点：
1. 当前趋势判断
2. 关键支撑/阻力位
3. 风险和机会
4. 综合评级（买入/持有/卖出/观望）

请用中文回答，简洁专业。"""

    response = llm.invoke(prompt)
    return response.content if hasattr(response, "content") else str(response)
