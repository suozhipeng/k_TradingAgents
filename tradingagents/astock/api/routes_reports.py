"""Reports API routes for AStock — Phase 17 / Web-P2.

Provides:
- GET  /reports/pptx    → PPTX report download
- GET  /reports/list    → filterable report archive listing
"""

from __future__ import annotations

import difflib
import json
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, Response, request

from tradingagents.astock.reporting.ppt import ReportGenerator, HAS_PPTX

logger = logging.getLogger(__name__)

bp = Blueprint("reports", __name__)


# ---------------------------------------------------------------------------
# HELPERS: report store (JSON file, temp)
# ---------------------------------------------------------------------------

REPORT_INDEX_PATH = Path.home() / ".tradingagents" / "report_index.json"


def _load_report_index() -> list[dict[str, Any]]:
    if not REPORT_INDEX_PATH.exists():
        return []
    try:
        with open(REPORT_INDEX_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_report_index(items: list[dict[str, Any]]) -> None:
    REPORT_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# GET /reports/list
# ---------------------------------------------------------------------------


@bp.route("/reports/list")
def report_list() -> tuple[Response, int]:
    """Return filterable report archive listing.

    Query params:
        type     — filter by report_type (market / watchlist / single / all)
        source   — filter by provider/source
        limit    — max results (default 50)
        offset   — pagination offset (default 0)
    """
    rpt_type = request.args.get("type", "all")
    source = request.args.get("source", "")
    limit = int(request.args.get("limit", "50"))
    offset = int(request.args.get("offset", "0"))

    items = _load_report_index()

    # Apply filters
    if rpt_type and rpt_type != "all":
        items = [it for it in items if it.get("report_type") == rpt_type]
    if source:
        items = [it for it in items if (it.get("source") or "").lower() == source.lower()]

    total = len(items)
    # Sort by created_at descending
    items.sort(key=lambda it: it.get("created_at", ""), reverse=True)
    page = items[offset : offset + limit]

    return jsonify(
        {
            "items": page,
            "total": total,
            "limit": limit,
            "offset": offset,
            "status": "ok",
        }
    ), 200


# ---------------------------------------------------------------------------
# POST /reports/save — save a report to the archive
# ---------------------------------------------------------------------------


@bp.route("/reports/save", methods=["POST"])
def report_save() -> tuple[Response, int]:
    """Save a generated report to the archive index.

    Body (JSON):
        symbol          — stock symbol
        report_type     — market / watchlist / single
        source          — provider/model name
        summary         — report summary text
        research_data   — full research data dict
        advisory_only   — bool, advisory vs actionable
    """
    data = request.get_json(silent=True) or {}
    required = ("symbol", "report_type")
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}", "status": 400}), 400

    entry = {
        "symbol": data.get("symbol", "").upper(),
        "report_type": data.get("report_type", "single"),
        "source": data.get("source", "api"),
        "summary": data.get("summary", ""),
        "investment_plan": data.get("investment_plan", ""),
        "research_conclusion": data.get("research_conclusion"),
        "created_at": datetime.now().isoformat(),
        "advisory_only": bool(data.get("advisory_only", True)),
        "actionable": not bool(data.get("advisory_only", True)),
        "data_snapshot": data.get("data_snapshot", None),
        "trade_date": data.get("trade_date", ""),
    }

    items = _load_report_index()
    items.append(entry)
    _save_report_index(items)

    return jsonify({"item": entry, "count": len(items), "status": "ok"}), 201


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


# ---------------------------------------------------------------------------
# POST /reports/compare — compare two archived reports
# ---------------------------------------------------------------------------


@bp.route("/reports/compare", methods=["POST"])
def report_compare() -> tuple[Response, int]:
    """Compare two archived reports and return a structured diff.

    Body (JSON):
        symbol_a    — first stock symbol
        symbol_b    — second stock symbol
        trade_date  — optional trade date filter
    """
    data = request.get_json(silent=True) or {}
    symbol_a = (data.get("symbol_a") or "").strip().upper()
    symbol_b = (data.get("symbol_b") or "").strip().upper()
    trade_date = (data.get("trade_date") or "").strip()

    if not symbol_a or not symbol_b:
        return jsonify({"error": "symbol_a and symbol_b are required", "status": 400}), 400

    items = _load_report_index()

    def _find_report(sym: str, date: str) -> dict | None:
        candidates = [it for it in items if it.get("symbol", "").upper() == sym]
        if date:
            candidates = [it for it in candidates if it.get("trade_date", "") == date]
        candidates.sort(key=lambda it: it.get("created_at", ""), reverse=True)
        return candidates[0] if candidates else None

    report_a = _find_report(symbol_a, trade_date)
    report_b = _find_report(symbol_b, trade_date)

    if not report_a and not report_b:
        return jsonify({"error": "Neither report found", "status": 404}), 404

    # Build comparison fields — metadata
    meta_fields = ["symbol", "report_type", "source", "advisory_only", "trade_date"]
    diff: list[dict] = []
    for field in meta_fields:
        val_a = report_a.get(field) if report_a else "--"
        val_b = report_b.get(field) if report_b else "--"
        diff.append({
            "field": field,
            "a": val_a,
            "b": val_b,
            "same": val_a == val_b,
        })

    # Body comparison — unified diff for text fields
    summary_a_text = (report_a.get("summary") or "") if report_a else ""
    summary_b_text = (report_b.get("summary") or "") if report_b else ""
    if summary_a_text or summary_b_text:
        summary_diff = list(difflib.unified_diff(
            summary_a_text.splitlines(keepends=True),
            summary_b_text.splitlines(keepends=True),
            fromfile="A",
            tofile="B",
            n=3,
        ))
        diff.append({
            "field": "summary",
            "type": "unified_diff",
            "diff_text": "".join(summary_diff),
            "a_len": len(summary_a_text),
            "b_len": len(summary_b_text),
            "same": summary_a_text == summary_b_text,
        })
    else:
        diff.append({"field": "summary", "type": "unified_diff", "diff_text": "", "a_len": 0, "b_len": 0, "same": True})

    # Body comparison — investment_plan (unified diff)
    ip_a_text = (report_a.get("investment_plan") or "") if report_a else ""
    ip_b_text = (report_b.get("investment_plan") or "") if report_b else ""
    if ip_a_text or ip_b_text:
        ip_diff = list(difflib.unified_diff(
            ip_a_text.splitlines(keepends=True),
            ip_b_text.splitlines(keepends=True),
            fromfile="A",
            tofile="B",
            n=3,
        ))
        diff.append({
            "field": "investment_plan",
            "type": "unified_diff",
            "diff_text": "".join(ip_diff),
            "a_len": len(ip_a_text),
            "b_len": len(ip_b_text),
            "same": ip_a_text == ip_b_text,
        })
    else:
        diff.append({"field": "investment_plan", "type": "unified_diff", "diff_text": "", "a_len": 0, "b_len": 0, "same": True})

    # Body comparison — research_conclusion (structured field diff)
    rc_a = report_a.get("research_conclusion") or {} if report_a else {}
    rc_b = report_b.get("research_conclusion") or {} if report_b else {}
    rc_all_keys = sorted(set(list(rc_a.keys()) + list(rc_b.keys())))
    rc_items = []
    for key in rc_all_keys:
        val_a = rc_a.get(key)
        val_b = rc_b.get(key)
        rc_items.append({
            "key": key,
            "a": val_a,
            "b": val_b,
            "same": val_a == val_b,
        })
    diff.append({
        "field": "research_conclusion",
        "type": "structured_diff",
        "items": rc_items,
        "same": all(it["same"] for it in rc_items),
    })

    return jsonify({
        "report_a": report_a,
        "report_b": report_b,
        "diff": diff,
        "status": "ok",
    }), 200


# ---------------------------------------------------------------------------
# PATCH /reports/<report_id>/audit — AI audit annotation
# ---------------------------------------------------------------------------


@bp.route("/reports/<report_id>/audit", methods=["PATCH"])
def report_audit(report_id: str) -> tuple[Response, int]:
    """Add an AI audit result to an archived report.

    Body (JSON):
        audit_status  — passed / flagged / reviewed
        audit_notes   — free-text audit notes
        auditor       — model or human name
    """
    data = request.get_json(silent=True) or {}
    audit_status = (data.get("audit_status") or "").strip().lower()
    audit_notes = (data.get("audit_notes") or "").strip()
    auditor = (data.get("auditor") or "ai").strip()

    if audit_status not in ("passed", "flagged", "reviewed"):
        return jsonify({"error": "audit_status must be passed/flagged/reviewed", "status": 400}), 400

    items = _load_report_index()
    # Find by created_at timestamp (used as report_id) or symbol match
    target = None
    for it in items:
        if it.get("created_at") == report_id:
            target = it
            break
    if target is None:
        # Fallback: use symbol as report_id
        candidates = [it for it in items if it.get("symbol", "").upper() == report_id.upper()]
        candidates.sort(key=lambda it: it.get("created_at", ""), reverse=True)
        target = candidates[0] if candidates else None

    if target is None:
        return jsonify({"error": f"Report not found: {report_id}", "status": 404}), 404

    target["ai_audit"] = {
        "status": audit_status,
        "notes": audit_notes,
        "auditor": auditor,
        "audited_at": datetime.now().isoformat(),
    }
    _save_report_index(items)

    return jsonify({"item": target, "status": "ok"}), 200


__all__ = ["bp"]
