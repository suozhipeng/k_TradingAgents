from __future__ import annotations

import json
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping, Sequence

from tradingagents.astock import AStockGraphReport

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
    analyst_summary: str
    bull_view: str
    bear_view: str
    research_manager_conclusion: str
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
    return AStockUiModel(
        ticker=str(payload.get("ticker") or payload.get("symbol") or "-"),
        symbol=str(payload.get("symbol") or payload.get("ticker") or "-"),
        normalized_symbol=str(payload.get("normalized_symbol") or payload.get("symbol") or payload.get("ticker") or "-"),
        trade_date=payload.get("trade_date"),
        runtime_mode=str(payload.get("runtime_mode") or payload.get("mode") or "-"),
        status=str(payload.get("status") or "-"),
        analyst_summary=str(payload.get("analyst_summary") or payload.get("summary") or "-"),
        bull_view=str(payload.get("bull_view") or "-"),
        bear_view=str(payload.get("bear_view") or "-"),
        research_manager_conclusion=str(
            payload.get("research_manager_conclusion")
            or payload.get("final_trade_decision")
            or payload.get("investment_plan")
            or "-"
        ),
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


def render_astock_report_page(st: Any, report: AStockGraphReport | Mapping[str, Any]) -> AStockUiModel:
    model = build_astock_ui_model(report)

    title = getattr(st, "title", None)
    if callable(title):
        title(f"A 股 Analysis Report · {model.ticker}")

    caption = getattr(st, "caption", None)
    if callable(caption):
        caption(f"{model.symbol} · {model.normalized_symbol}")

    cols = _columns(st, 4)
    metric_labels = [
        ("Ticker", model.ticker),
        ("Trade Date", model.trade_date or "-"),
        ("Runtime Mode", model.runtime_mode),
        ("Status", model.status),
    ]
    for col, (label, value) in zip(cols, metric_labels, strict=False):
        metric = getattr(col, "metric", None)
        if callable(metric):
            metric(label, value)

    subheader = getattr(st, "subheader", None)
    if callable(subheader):
        subheader("Five-layer Section Status")
    table = getattr(st, "table", None)
    if callable(table):
        table(_table_like_rows(model))

    for heading, body in [
        ("Analyst Summary", model.analyst_summary),
        ("Bull View", model.bull_view),
        ("Bear View", model.bear_view),
        ("Research Manager Conclusion", model.research_manager_conclusion),
    ]:
        with _with_expander(st, heading, expanded=True):
            markdown = getattr(st, "markdown", None)
            write = getattr(st, "write", None)
            if callable(markdown):
                markdown(body)
            elif callable(write):
                write(body)

    if callable(subheader):
        subheader("Provider Coverage")
    provider_table = getattr(st, "table", None)
    if callable(provider_table):
        provider_table(list(model.provider_rows))

    warning = getattr(st, "warning", None)
    info = getattr(st, "info", None)
    if model.missing_data_notes:
        if callable(warning):
            warning(_notes_or_placeholder(model.missing_data_notes, "- None"))
        elif callable(info):
            info(_notes_or_placeholder(model.missing_data_notes, "- None"))
    if model.degradation_notes:
        if callable(warning):
            warning(_notes_or_placeholder(model.degradation_notes, "- None"))
        elif callable(info):
            info(_notes_or_placeholder(model.degradation_notes, "- None"))

    json_block = getattr(st, "json", None)
    if callable(json_block):
        with _with_expander(st, "Raw A 股 report payload", expanded=False):
            json_block(model.raw)

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
