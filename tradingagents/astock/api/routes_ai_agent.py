"""AI Agent analysis API routes — Phase 33 AI Research Center.

Each analysis response includes ResearchTask and ResearchAudit metadata
for traceability.  All AI outputs default to ``advisory: true``.
"""

from __future__ import annotations

import logging
import copy
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request

from tradingagents.astock.schemas.research_task import ResearchAudit
from tradingagents.astock.schemas import ResearchContext

logger = logging.getLogger(__name__)

_report_cache_lock = threading.Lock()
_report_cache: dict[tuple[str, str, str], tuple[float, dict[str, Any]]] = {}
_report_flights: dict[tuple[str, str, str], Future[dict[str, Any]]] = {}

bp = Blueprint("ai_agent", __name__)


@bp.route("/ai/analyze", methods=["POST"])
def ai_analyze() -> tuple[Response, int]:
    """Run AI agent analysis on one or more stock symbols.

    JSON body:
        symbol (str, optional) — single A-share stock symbol, e.g. "600519.SH"
        symbols (list[str] or str, optional) — multi-symbol override
        analysis_type (str) — "full" (default), "technical", "fundamental", "news"
        prompt_version (str, optional) — override prompt version tag

    Returns a JSON object with:
        - symbol, analysis_type, timestamp (existing)
        - symbols (list) — full list of requested symbols
        - context, llm_analysis (existing)
        - task_id, status, advisory (Phase 33 ResearchTask metadata)
        - audit (Phase 33 ResearchAudit metadata)
    """
    body = request.get_json(silent=True) or {}
    single_symbol = str(body.get("symbol", "")).strip()
    symbols_raw = body.get("symbols", [])

    # Resolve symbol list
    symbols: list[str] = []
    if single_symbol:
        symbols.append(single_symbol)
    if isinstance(symbols_raw, str):
        symbols.extend([s.strip() for s in symbols_raw.replace("，", ",").split(",") if s.strip()])
    elif isinstance(symbols_raw, list):
        symbols.extend([str(s).strip() for s in symbols_raw if str(s).strip()])

    if not symbols:
        return jsonify({"error": "symbol or symbols is required", "status": 400}), 400

    # Normalize each symbol
    # Normalize each symbol — infer exchange from stock code prefix
    def _normalize_symbol(s: str) -> str:
        s = s.strip()
        if s.endswith((".SH", ".SZ")):
            return s.upper()
        # A-share code prefix rules: 6=SH, 0/3=SZ
        code = s.lstrip("0")  # strip leading zeros for prefix check
        if not code:
            code = s
        first = code[0]
        if first in ("6",):
            return s.upper() + ".SH"
        else:
            return s.upper() + ".SZ"

    symbols = [_normalize_symbol(s) for s in symbols]

    # Primary symbol for analysis (first one)
    primary = symbols[0]
    analysis_type = str(body.get("analysis_type", "full"))
    prompt_version = str(body.get("prompt_version", ""))
    force_refresh = bool(body.get("force_refresh", False))

    try:
        # Data is always refreshed first; only the expensive research/LLM
        # result is reusable when no new daily bars were written.
        from .routes_data_query import _refresh_daily_kline_incrementally
        daily_refresh = _refresh_daily_kline_incrementally(primary)
        key = (primary, analysis_type, prompt_version)
        if force_refresh or int(daily_refresh.get("rows_upserted", 0)):
            with _report_cache_lock:
                _report_cache.pop(key, None)
        if not force_refresh and not int(daily_refresh.get("rows_upserted", 0)):
            cached = _get_cached_report(key)
            if cached is not None:
                cached["cache"] = {"hit": True, "daily_refresh": daily_refresh}
                return jsonify(cached), 200
        result = _run_analysis_singleflight(
            key, primary, analysis_type, prompt_version, symbols, daily_refresh,
        )
        result["cache"] = {"hit": False, "daily_refresh": daily_refresh}
        if not int(daily_refresh.get("rows_upserted", 0)) and result.get("status") in {"success", "degraded"}:
            _set_cached_report(key, result)
        return jsonify(result), 200
    except Exception as exc:
        logger.warning("AI analysis failed for %s: %s", symbols, exc)
        return jsonify({"error": str(exc), "status": 500}), 500


def _generate_task_id() -> str:
    """Generate a unique ResearchTask ID."""
    return f"ai-{uuid.uuid4().hex[:12]}"


def _report_cache_ttl_seconds() -> float:
    """Use a short intraday TTL; after close, expire at the next weekday open."""
    ttl = max(1.0, float(current_app.config.get("ASTOCK_LLM_REPORT_TTL_SECONDS", 600)))
    now = datetime.now()
    if now.weekday() < 5 and (now.hour, now.minute) < (15, 0):
        return ttl
    next_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    if now >= next_open:
        from datetime import timedelta
        next_open += timedelta(days=1)
    while next_open.weekday() >= 5:
        from datetime import timedelta
        next_open += timedelta(days=1)
    return max(ttl, (next_open - now).total_seconds())


def _get_cached_report(key: tuple[str, str, str]) -> dict[str, Any] | None:
    with _report_cache_lock:
        item = _report_cache.get(key)
        if item is None or item[0] <= time.monotonic():
            _report_cache.pop(key, None)
            return None
        return copy.deepcopy(item[1])


def _set_cached_report(key: tuple[str, str, str], payload: dict[str, Any]) -> None:
    with _report_cache_lock:
        _report_cache[key] = (time.monotonic() + _report_cache_ttl_seconds(), copy.deepcopy(payload))


def _run_analysis_singleflight(
    key: tuple[str, str, str], symbol: str, analysis_type: str, prompt_version: str,
    symbols: list[str], daily_refresh: dict[str, Any],
) -> dict[str, Any]:
    """Coalesce identical concurrent research requests into one LLM pipeline."""
    with _report_cache_lock:
        future = _report_flights.get(key)
        if future is None:
            future = Future()
            _report_flights[key] = future
            leader = True
        else:
            leader = False
    if not leader:
        timeout = max(1.0, float(current_app.config.get("ASTOCK_MAIN_ANALYSIS_TIMEOUT_SECONDS", 45)))
        try:
            shared = copy.deepcopy(future.result(timeout=timeout))
            shared["coalesced"] = True
            return shared
        except FuturesTimeoutError:
            return {
                "symbol": symbol, "symbols": symbols, "analysis_type": analysis_type,
                "status": "pending", "advisory": True,
                "message": "identical analysis is already running", "coalesced": True,
            }
    try:
        result = _run_analysis(
            symbol, analysis_type, prompt_version, symbols=symbols,
            daily_refresh=daily_refresh,
        )
        future.set_result(copy.deepcopy(result))
        return result
    except Exception as exc:
        future.set_exception(exc)
        raise
    finally:
        with _report_cache_lock:
            _report_flights.pop(key, None)


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
    symbols: list[str] | None = None,
    daily_refresh: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run analysis pipeline and return structured results with audit trail."""

    task_id = _generate_task_id()
    now = datetime.now().isoformat()

    # Always run the complete research-only main chain, even when the caller
    # selected a narrow view such as "technical".  The selected view only
    # changes the final presentation prompt; it must not bypass market, news,
    # fundamentals, debate, risk, or portfolio-review stages.
    main_pipeline = _run_main_pipeline(symbol, daily_refresh=daily_refresh)

    # ── Gather context data ──
    raw_context = _gather_context(symbol, main_pipeline)
    ctx = ResearchContext.from_gathered_dict(symbol, raw_context, gathered_at=now)

    # ── Try LLM reasoning (optional) ──
    llm_analysis = ""
    model_name = ""
    provider_name = ""
    llm_error: str | None = None

    try:
        llm_result = _run_llm_analysis_bounded(symbol, ctx, analysis_type)
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
    all_symbols = list(dict.fromkeys(symbols or [symbol]))
    return {
        # Existing fields (backward-compatible)
        "symbol": symbol,
        "symbols": all_symbols,
        "analysis_type": analysis_type,
        "timestamp": now,
        "context": raw_context,
        "llm_analysis": llm_analysis,
        # Phase 33 ResearchTask fields
        "task_id": task_id,
        "status": "success" if not llm_error else "degraded",
        "advisory": True,
        "llm_error": llm_error,
        "main_pipeline": main_pipeline,
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


def _run_main_pipeline(symbol: str, *, daily_refresh: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run the full A-share chain with an HTTP-safe request deadline."""
    from tradingagents.astock import AStockGraphRuntime, AStockInterface
    from .routes_data_query import _refresh_daily_kline_incrementally

    facade = current_app.config.get("DATA_FACADE")
    interface = AStockInterface(facade=facade) if facade is not None else None
    daily_refresh = daily_refresh or _refresh_daily_kline_incrementally(symbol)
    timeout = max(1.0, float(current_app.config.get("ASTOCK_MAIN_ANALYSIS_TIMEOUT_SECONDS", 45)))
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="astock-main-analysis")
    future = executor.submit(
        lambda: AStockGraphRuntime(
            symbol=symbol, interface=interface, source="ai_indicator_query"
        ).run().to_dict()
    )
    try:
        report = future.result(timeout=timeout)
        return {
            "status": "completed", "timeout_seconds": timeout,
            "daily_refresh": daily_refresh, "report": report,
        }
    except FuturesTimeoutError:
        future.cancel()
        logger.warning("main analysis timed out for %s after %.1fs", symbol, timeout)
        return {
            "status": "timed_out", "timeout_seconds": timeout,
            "daily_refresh": daily_refresh,
            "error": "main analysis deadline exceeded; partial data may still be available",
        }
    except Exception as exc:
        logger.warning("main analysis failed for %s: %s", symbol, exc)
        return {
            "status": "failed", "timeout_seconds": timeout,
            "daily_refresh": daily_refresh, "error": str(exc)[:300],
        }
    finally:
        # Never make the request thread wait for a stalled provider worker.
        executor.shutdown(wait=False, cancel_futures=True)


def _run_llm_analysis_bounded(
    symbol: str, context: ResearchContext, analysis_type: str
) -> dict[str, str]:
    timeout = min(20.0, max(1.0, float(current_app.config.get("ASTOCK_MAIN_ANALYSIS_TIMEOUT_SECONDS", 45))))
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="astock-presentation-llm")
    future = executor.submit(_try_llm_analysis, symbol, context, analysis_type)
    try:
        return future.result(timeout=timeout)
    except FuturesTimeoutError as exc:
        future.cancel()
        raise TimeoutError(f"LLM presentation deadline exceeded after {timeout:.0f}s") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _gather_context(symbol: str, main_pipeline: dict[str, Any]) -> dict[str, Any]:
    """Build presentation context from the already-completed main pipeline.

    This deliberately avoids loopback HTTP calls.  Besides saving three
    serial requests per analysis, it prevents the presentation layer from
    triggering another K-line refresh after the main chain has just done one.
    """
    report = main_pipeline.get("report", {}) if isinstance(main_pipeline, dict) else {}
    sections = report.get("astock_sections", {}) if isinstance(report, dict) else {}
    market = sections.get("market", {}) if isinstance(sections, dict) else {}
    responses = market.get("responses", {}) if isinstance(market, dict) else {}
    kline = responses.get("kline", {}) if isinstance(responses, dict) else {}
    kline_data = kline.get("data", {}) if isinstance(kline, dict) else {}
    return {
        "stock_info": {"symbol": symbol, "source": "main_pipeline"},
        "market_summary": market if isinstance(market, dict) else {},
        "kline_latest": kline_data if isinstance(kline_data, dict) else {},
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
