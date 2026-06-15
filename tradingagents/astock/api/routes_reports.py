"""Reports API routes for AStock — Phase 17.

Provides PPTX report generation endpoint that uses ReportGenerator.
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

from flask import Blueprint, jsonify, Response, request

from tradingagents.astock.reporting.ppt import ReportGenerator, HAS_PPTX

logger = logging.getLogger(__name__)

bp = Blueprint("reports", __name__)


@bp.route("/reports/pptx", methods=["GET"])
def report_pptx() -> Response:
    """Generate and return a PPTX report for a given symbol.

    Query parameters
    ----------------
    symbol : str
        Stock symbol (e.g. ``600519.SH``).
    trade_date : str, optional
        Trade date (default: latest).

    Returns
    -------
    Response
        PPTX file as binary download, or JSON error.
    """
    symbol = request.args.get("symbol", "600519.SH")
    trade_date = request.args.get("trade_date", "")

    # Build a minimal report dict
    store = None
    from flask import current_app

    try:
        store = current_app.config.get("STORE")
    except RuntimeError:
        pass

    # Try to fetch research data from the store
    report_data = {
        "symbol": symbol,
        "normalized_symbol": symbol,
        "trade_date": trade_date or "N/A",
        "source": "api",
        "status": "ok",
        "summary": "AStock research report generated via API.",
        "investment_plan": "",
        "runtime_profile": "api",
        "runtime_trace": [],
        "provider_coverage": {},
        "missing_data_notes": [],
        "degradation_notes": [],
        "research_conclusion": {
            "recommendation": "N/A",
            "confidence": "N/A",
            "summary": "Report generated from API endpoint.",
        },
        "trader_proposal": {},
        "risk_decision": {},
        "portfolio_decision": {},
        "metadata": {},
    }

    # Try to enrich from store
    if store:
        try:
            from tradingagents.astock.store.schema import AStockStore

            s: AStockStore = store
            # Attempt to read research data
            if hasattr(s, "get_research"):
                research = s.get_research(symbol, limit=1)
                if research:
                    report_data["summary"] = research[0].get("summary", report_data["summary"])
                    report_data["investment_plan"] = research[0].get("investment_plan", "")
                    if research[0].get("research_conclusion"):
                        report_data["research_conclusion"] = research[0]["research_conclusion"]

            if hasattr(s, "get_runtime_profile"):
                profile = s.get_runtime_profile(symbol)
                if profile:
                    report_data["runtime_profile"] = str(profile)
        except Exception as exc:
            logger.warning("Could not enrich report from store: %s", exc)

    if not HAS_PPTX:
        return jsonify({
            "error": "python-pptx is not installed",
            "detail": "Install with: pip install python-pptx",
            "report_data": report_data,
        }), 501

    try:
        gen = ReportGenerator()
        with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp:
            gen.to_pptx(report_data, tmp.name)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as f:
            pptx_bytes = f.read()
        Path(tmp_path).unlink(missing_ok=True)

        return Response(
            pptx_bytes,
            mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={
                "Content-Disposition": f'attachment; filename="{symbol}_report.pptx"',
            },
        )
    except Exception as exc:
        logger.exception("PPTX generation failed")
        return jsonify({"error": f"PPTX generation failed: {exc}"}), 500


__all__ = ["bp"]
