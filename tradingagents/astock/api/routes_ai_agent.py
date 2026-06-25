"""AI Agent analysis API routes — Phase 33 AI Research Center.

Each analysis response includes ResearchTask and ResearchAudit metadata
for traceability.  All AI outputs default to ``advisory: true``.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from flask import Blueprint, Response, jsonify, request

from tradingagents.astock.schemas.research_task import ResearchAudit
from tradingagents.astock.schemas import ResearchContext

logger = logging.getLogger(__name__)

bp = Blueprint("ai_agent", __name__)


@bp.route("/ai/analyze", methods=["POST"])
def ai_analyze() -> tuple[Response, int]:
    """Run AI agent analysis on a stock symbol.

    JSON body:
        symbol (str) — A-share stock symbol, e.g. "600519.SH"
        analysis_type (str) — "full" (default), "technical", "fundamental", "news"
        prompt_version (str, optional) — override prompt version tag

    Returns a JSON object with:
        - symbol, analysis_type, timestamp (existing)
        - context (existing, enriched with provenance meta)
        - llm_analysis (existing, or degraded fallback)
        - task_id, status, advisory (Phase 33 ResearchTask metadata)
        - audit (Phase 33 ResearchAudit metadata)
    """
    body = request.get_json(silent=True) or {}
    symbol = str(body.get("symbol", "")).strip()
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    if not symbol.endswith((".SH", ".SZ")):
        symbol += ".SH"

    try:
        result = _run_analysis(
            symbol,
            body.get("analysis_type", "full"),
            body.get("prompt_version", ""),
        )
        return jsonify(result), 200
    except Exception as exc:
        logger.warning("AI analysis failed for %s: %s", symbol, exc)
        return jsonify({"error": str(exc), "status": 500}), 500


def _generate_task_id() -> str:
    """Generate a unique ResearchTask ID."""
    return f"ai-{uuid.uuid4().hex[:12]}"


def _build_audit(
    symbol: str,
    task_id: str,
    model: str,
    provider: str,
    prompt_version: str,
    input_snapshot: dict[str, Any] | None,
    output_summary: str,
) -> ResearchAudit:
    """Build a ResearchAudit record for the analysis."""
    return ResearchAudit(
        audit_id=f"audit-{uuid.uuid4().hex[:12]}",
        task_id=task_id,
        symbol=symbol,
        model=model,
        prompt_text="",  # Full prompt not returned in API response by default
        prompt_version=prompt_version or "v1",
        input_snapshot=input_snapshot or {},
        output_summary=output_summary[:500] if output_summary else "",
        advisory=True,
        generated_at=datetime.now().isoformat(),
    )


def _run_analysis(
    symbol: str,
    analysis_type: str = "full",
    prompt_version: str = "",
) -> dict[str, Any]:
    """Run analysis pipeline and return structured results with audit trail."""

    task_id = _generate_task_id()
    now = datetime.now().isoformat()

    # ── Gather context data ──
    raw_context = _gather_context(symbol)
    ctx = ResearchContext.from_gathered_dict(symbol, raw_context, gathered_at=now)

    # ── Try LLM reasoning (optional) ──
    llm_analysis = ""
    model_name = ""
    provider_name = ""
    llm_error: str | None = None

    try:
        llm_result = _try_llm_analysis(symbol, ctx, analysis_type)
        llm_analysis = llm_result.get("text", "")
        model_name = llm_result.get("model", "")
        provider_name = llm_result.get("provider", "")
    except Exception as exc:
        llm_error = str(exc)
        llm_analysis = f"LLM analysis unavailable: {exc}"
        logger.info("LLM analysis degraded for %s: %s", symbol, exc)

    # ── Build audit trail ──
    audit = _build_audit(
        symbol=symbol,
        task_id=task_id,
        model=model_name,
        provider=provider_name,
        prompt_version=prompt_version,
        input_snapshot=ctx.model_dump() if hasattr(ctx, "model_dump") else {},
        output_summary=llm_analysis,
    )

    # ── Build response (backward-compatible + Phase 33 metadata) ──
    return {
        # Existing fields (backward-compatible)
        "symbol": symbol,
        "analysis_type": analysis_type,
        "timestamp": now,
        "context": raw_context,
        "llm_analysis": llm_analysis,
        # Phase 33 ResearchTask fields
        "task_id": task_id,
        "status": "success" if not llm_error else "degraded",
        "advisory": True,
        "llm_error": llm_error,
        # Phase 33 ResearchAudit fields
        "audit": {
            "audit_id": audit.audit_id,
            "model": audit.model,
            "provider": provider_name,
            "prompt_version": audit.prompt_version,
            "advisory": audit.advisory,
            "generated_at": audit.generated_at,
        },
    }


def _gather_context(symbol: str) -> dict[str, Any]:
    """Gather market data context for the symbol (returns ad-hoc dict).

    The result is consumed by ``ResearchContext.from_gathered_dict()``
    for structured processing, and also passed through in the raw form
    for backward compatibility.
    """
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
    symbol: str, context: ResearchContext, analysis_type: str
) -> dict[str, str]:
    """Try to run LLM-based analysis.

    Returns a dict with ``text``, ``model``, ``provider`` keys, or raises.

    Structured ``ResearchAudit`` is built by the caller with the returned
    model/provider info.
    """
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

    # Format context from structured ResearchContext
    info = context.stock_info.raw or {}
    info_text = (
        f"名称: {info.get('name','?')} ({info.get('code','?')})"
        f"\n行业: {info.get('industry','?')}"
        f"\n板块: {info.get('board','?')}"
    )

    bars = (context.kline_latest.raw or {}).get("bars", [])
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
    text = response.content if hasattr(response, "content") else str(response)

    return {
        "text": text,
        "model": model,
        "provider": provider,
    }
