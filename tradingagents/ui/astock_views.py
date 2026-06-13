from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping, Sequence

from tradingagents.astock import AStockGraphReport
from .read_only_shell import VIEWER_METRIC_ORDER, VIEWER_SECTION_ORDER, render_readonly_report_shell

ASTOCK_SECTION_ORDER: tuple[str, ...] = (
    "market",
    "news",
    "fundamentals",
    "announcements",
    "research",
)


@dataclass(frozen=True)
class AStockUiRow:
    name: str
    status: str
    source: str
    has_data: bool
    summary: str


@dataclass(frozen=True)
class AStockUiModel:
    ticker: str
    symbol: str
    normalized_symbol: str
    trade_date: str | None
    runtime_mode: str
    status: str
    decision_scope: str
    actionable: bool
    runtime_profile: str
    analyst_summary: str
    bull_view: str
    bear_view: str
    research_manager_conclusion: str
    advisory_blocks: tuple[tuple[str, str], ...]
    section_rows: tuple[AStockUiRow, ...]
    provider_rows: tuple[dict[str, Any], ...]
    missing_data_notes: tuple[str, ...]
    degradation_notes: tuple[str, ...]
    runtime_trace: tuple[str, ...]
    raw: dict[str, Any]


class _FallbackExpander:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FallbackColumn:
    def __init__(self, st_like: Any) -> None:
        self._st = st_like

    def metric(self, *args: Any, **kwargs: Any) -> Any:
        metric = getattr(self._st, "metric", None)
        if callable(metric):
            return metric(*args, **kwargs)
        return None


def _extract_payload(report: AStockGraphReport | Mapping[str, Any]) -> dict[str, Any]:
    if hasattr(report, "to_dict"):
        payload = report.to_dict()  # type: ignore[assignment]
    elif isinstance(report, Mapping):
        payload = dict(report)
    else:
        raise TypeError(f"Unsupported report payload: {type(report)!r}")
    if not isinstance(payload, MutableMapping):
        payload = dict(payload)
    return dict(payload)


def is_astock_report_payload(payload: Any) -> bool:
    if isinstance(payload, AStockGraphReport):
        return True
    if not isinstance(payload, Mapping):
        return False
    return str(payload.get("runtime_mode") or payload.get("mode") or "") == "astock_research_bridge"


def _normalize_section_rows(payload: Mapping[str, Any]) -> tuple[AStockUiRow, ...]:
    section_results = payload.get("section_results") or {}
    rows: list[AStockUiRow] = []
    for section_name in ASTOCK_SECTION_ORDER:
        item = section_results.get(section_name, {}) if isinstance(section_results, Mapping) else {}
        rows.append(
            AStockUiRow(
                name=section_name,
                status=str(item.get("status", "-")),
                source=str(item.get("source", "-")),
                has_data=bool(item.get("has_data", False)),
                summary=str(item.get("summary") or item.get("error") or "-"),
            )
        )
    return tuple(rows)


def _normalize_provider_rows(payload: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    provider_coverage = payload.get("provider_coverage") or {}
    rows: list[dict[str, Any]] = []
    for section_name in ASTOCK_SECTION_ORDER:
        item = provider_coverage.get(section_name, {}) if isinstance(provider_coverage, Mapping) else {}
        rows.append(
            {
                "section": section_name,
                "source": item.get("source", "-"),
                "status": item.get("status", "-"),
                "available": bool(item.get("available", False)),
            }
        )
    return tuple(rows)


def build_astock_ui_model(report: AStockGraphReport | Mapping[str, Any]) -> AStockUiModel:
    payload = _extract_payload(report)
    advisory_blocks: list[tuple[str, str]] = []
    if payload.get("research_conclusion"):
        rc = payload["research_conclusion"]
        advisory_blocks.append(
            (
                "Research Conclusion",
                "\n".join(
                    [
                        f"- Recommendation: {rc.get('recommendation', '-')}",
                        f"- Confidence: {rc.get('confidence', '-')}",
                        f"- Summary: {rc.get('summary', '-')}",
                    ]
                ),
            )
        )
    if payload.get("trader_proposal"):
        tp = payload["trader_proposal"]
        advisory_blocks.append(
            (
                "Trader Proposal",
                "\n".join(
                    [
                        f"- Candidate Action: {tp.get('candidate_action', '-')}",
                        f"- Position Cap: {tp.get('position_cap_pct', '-')}",
                        f"- Rationale: {tp.get('rationale', '-')}",
                    ]
                ),
            )
        )
    if payload.get("risk_decision"):
        rd = payload["risk_decision"]
        advisory_blocks.append(
            (
                "Risk Decision",
                "\n".join(
                    [
                        f"- Verdict: {rd.get('verdict', '-')}",
                        f"- Risk Level: {rd.get('risk_level', '-')}",
                        f"- Constraints: {', '.join(rd.get('constraints', []) or ['-'])}",
                    ]
                ),
            )
        )
    if payload.get("portfolio_decision"):
        pd = payload["portfolio_decision"]
        advisory_blocks.append(
            (
                "Portfolio Decision",
                "\n".join(
                    [
                        f"- Disposition: {pd.get('disposition', '-')}",
                        f"- Exposure Cap: {pd.get('exposure_cap_pct', '-')}",
                        f"- Notes: {pd.get('portfolio_notes', '-')}",
                    ]
                ),
            )
        )

    return AStockUiModel(
        ticker=str(payload.get("ticker") or payload.get("symbol") or "-"),
        symbol=str(payload.get("symbol") or payload.get("ticker") or "-"),
        normalized_symbol=str(payload.get("normalized_symbol") or payload.get("symbol") or payload.get("ticker") or "-"),
        trade_date=payload.get("trade_date"),
        runtime_mode=str(payload.get("runtime_mode") or payload.get("mode") or "-"),
        status=str(payload.get("status") or "-"),
        decision_scope=str(payload.get("decision_scope") or "research_only"),
        actionable=bool(payload.get("actionable", False)),
        runtime_profile=str(payload.get("runtime_profile") or "-"),
        analyst_summary=str(payload.get("analyst_summary") or payload.get("summary") or "-"),
        bull_view=str(payload.get("bull_view") or "-"),
        bear_view=str(payload.get("bear_view") or "-"),
        research_manager_conclusion=str(
            payload.get("research_manager_conclusion")
            or payload.get("final_trade_decision")
            or payload.get("investment_plan")
            or "-"
        ),
        advisory_blocks=tuple(advisory_blocks),
        section_rows=_normalize_section_rows(payload),
        provider_rows=_normalize_provider_rows(payload),
        missing_data_notes=tuple(str(item) for item in payload.get("missing_data_notes", []) or []),
        degradation_notes=tuple(str(item) for item in payload.get("degradation_notes", []) or []),
        runtime_trace=tuple(str(item) for item in payload.get("runtime_trace", []) or []),
        raw=payload,
    )


def _table_like_rows(model: AStockUiModel) -> list[dict[str, Any]]:
    return [
        {
            "section": row.name,
            "status": row.status,
            "source": row.source,
            "has_data": row.has_data,
            "summary": row.summary,
        }
        for row in model.section_rows
    ]


def _notes_or_placeholder(notes: Sequence[str], empty_text: str) -> str:
    if not notes:
        return empty_text
    return "\n".join(f"- {note}" for note in notes)


def _with_expander(st: Any, label: str, expanded: bool = False):
    expander = getattr(st, "expander", None)
    if callable(expander):
        return expander(label, expanded=expanded)
    return _FallbackExpander()


def _columns(st: Any, count: int):
    columns = getattr(st, "columns", None)
    if callable(columns):
        return columns(count)
    return tuple(_FallbackColumn(st) for _ in range(count))


def _render_markdown_block(st: Any, body: str) -> None:
    markdown = getattr(st, "markdown", None)
    write = getattr(st, "write", None)
    if callable(markdown):
        markdown(body)
    elif callable(write):
        write(body)


def render_astock_report_page(st: Any, report: AStockGraphReport | Mapping[str, Any]) -> AStockUiModel:
    model = build_astock_ui_model(report)
    render_readonly_report_shell(
        st,
        title=f"A 股 Analysis Report · {model.ticker}",
        caption=f"{model.symbol} · {model.normalized_symbol}",
        metrics=[
            ("Ticker", model.ticker),
            ("Trade Date", model.trade_date or "-"),
            ("Runtime Mode", model.runtime_mode),
            ("Runtime Profile", model.runtime_profile),
            ("Status", model.status),
            ("Decision Scope", model.decision_scope),
            ("Actionable", "Yes" if model.actionable else "No"),
        ],
        core_summary=model.analyst_summary,
        structured_rows=_table_like_rows(model),
        secondary_blocks=[
            ("Bull View", model.bull_view),
            ("Bear View", model.bear_view),
            ("Research Manager Conclusion", model.research_manager_conclusion),
            *list(model.advisory_blocks),
        ],
        coverage_rows=list(model.provider_rows),
        coverage_notes=model.missing_data_notes,
        degradation_notes=model.degradation_notes,
        runtime_trace=model.runtime_trace,
        raw_payload=model.raw,
        coverage_empty_message="No A 股 provider coverage details available.",
    )
    return model


def render_legacy_placeholder_page(st: Any, payload: Any) -> dict[str, Any]:
    title = getattr(st, "title", None)
    if callable(title):
        title("TradingAgents Report Viewer")
    info = getattr(st, "info", None)
    if callable(info):
        info("Legacy non-A 股 report payload received. Existing generic pages can wire their own renderer here.")
    json_block = getattr(st, "json", None)
    if callable(json_block):
        json_block(payload)
    return {"mode": "legacy", "payload": payload}


def render_report_page(st: Any, payload: Any, legacy_renderer: Any | None = None):
    if is_astock_report_payload(payload):
        return render_astock_report_page(st, payload)
    if callable(legacy_renderer):
        return legacy_renderer(st, payload)
    return render_legacy_placeholder_page(st, payload)


__all__ = [
    "ASTOCK_SECTION_ORDER",
    "AStockUiModel",
    "AStockUiRow",
    "build_astock_ui_model",
    "is_astock_report_payload",
    "render_astock_report_page",
    "render_legacy_placeholder_page",
    "render_report_page",
]
