from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping, Sequence

LEGACY_ANALYST_ORDER: tuple[str, ...] = (
    "market_report",
    "sentiment_report",
    "news_report",
    "fundamentals_report",
)

LEGACY_TEAM_ORDER: tuple[str, ...] = (
    "investment_debate_state",
    "trader_investment_plan",
    "risk_debate_state",
)


@dataclass(frozen=True)
class LegacyReportRow:
    group: str
    name: str
    status: str
    has_data: bool
    summary: str


@dataclass(frozen=True)
class LegacyUiModel:
    ticker: str
    company_of_interest: str
    market_label: str
    runtime_mode: str
    asset_type: str
    trade_date: str | None
    status: str
    summary: str
    analyst_rows: tuple[LegacyReportRow, ...]
    team_rows: tuple[LegacyReportRow, ...]
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


def _extract_payload(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    if hasattr(payload, "to_dict"):
        payload = payload.to_dict()  # type: ignore[assignment]
    elif not isinstance(payload, Mapping):
        raise TypeError(f"Unsupported legacy payload: {type(payload)!r}")
    if not isinstance(payload, MutableMapping):
        payload = dict(payload)
    return dict(payload)


def is_legacy_report_payload(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        return False
    legacy_keys = (
        "market_report",
        "sentiment_report",
        "news_report",
        "fundamentals_report",
        "investment_debate_state",
        "trader_investment_plan",
        "risk_debate_state",
    )
    return any(key in payload for key in legacy_keys)


def _row_status(value: Any) -> str:
    if isinstance(value, Mapping):
        status = value.get("status")
        if status:
            return str(status)
        if value.get("judge_decision"):
            return "ok"
        if value.get("current_response"):
            return "ok"
        if value.get("history"):
            return "ok"
        return "empty"
    if isinstance(value, str) and value.strip():
        return "ok"
    return "empty"


def _row_summary(value: Any) -> str:
    if isinstance(value, Mapping):
        for key in (
            "summary",
            "judge_decision",
            "current_response",
            "bull_history",
            "bear_history",
            "aggressive_history",
            "conservative_history",
            "neutral_history",
            "history",
            "content",
        ):
            text = value.get(key)
            if isinstance(text, str) and text.strip():
                return text.strip()
        return json.dumps(value, ensure_ascii=False, indent=2)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "-"


def _row_has_data(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            bool(value.get(key))
            for key in ("summary", "judge_decision", "current_response", "history", "content")
        )
    return isinstance(value, str) and bool(value.strip())


def _collect_row_notes(prefix: str, row_name: str, value: Any) -> list[str]:
    if _row_has_data(value):
        return []
    return [f"{prefix}: {row_name} unavailable"]


def build_legacy_ui_model(payload: Mapping[str, Any] | Any) -> LegacyUiModel:
    data = _extract_payload(payload)
    company_of_interest = str(data.get("company_of_interest") or data.get("ticker") or data.get("symbol") or "-")
    ticker = str(data.get("ticker") or company_of_interest)
    runtime_mode = str(data.get("runtime_mode") or data.get("mode") or "legacy")
    asset_type = str(data.get("asset_type") or data.get("market_profile") or "stock")
    market_label = str(data.get("market_profile") or data.get("market") or "legacy")
    trade_date = data.get("trade_date") or data.get("curr_date")
    status = str(data.get("status") or "ok")

    analyst_rows = tuple(
        LegacyReportRow(
            group="Analyst Team",
            name=key,
            status=_row_status(data.get(key)),
            has_data=_row_has_data(data.get(key)),
            summary=_row_summary(data.get(key)),
        )
        for key in LEGACY_ANALYST_ORDER
    )

    investment_debate_state = data.get("investment_debate_state") or {}
    risk_debate_state = data.get("risk_debate_state") or {}
    team_rows = (
        LegacyReportRow(
            group="Research Team",
            name="investment_debate_state",
            status=_row_status(investment_debate_state),
            has_data=_row_has_data(investment_debate_state),
            summary=_row_summary(investment_debate_state),
        ),
        LegacyReportRow(
            group="Trading Team",
            name="trader_investment_plan",
            status=_row_status(data.get("trader_investment_plan")),
            has_data=_row_has_data(data.get("trader_investment_plan")),
            summary=_row_summary(data.get("trader_investment_plan")),
        ),
        LegacyReportRow(
            group="Risk Management Team",
            name="risk_debate_state",
            status=_row_status(risk_debate_state),
            has_data=_row_has_data(risk_debate_state),
            summary=_row_summary(risk_debate_state),
        ),
        LegacyReportRow(
            group="Portfolio Manager",
            name="portfolio_manager",
            status=_row_status(risk_debate_state.get("judge_decision") if isinstance(risk_debate_state, Mapping) else None),
            has_data=_row_has_data(risk_debate_state.get("judge_decision") if isinstance(risk_debate_state, Mapping) else None),
            summary=_row_summary(risk_debate_state.get("judge_decision") if isinstance(risk_debate_state, Mapping) else None),
        ),
    )

    missing_notes: list[str] = []
    degradation_notes: list[str] = []
    for key in LEGACY_ANALYST_ORDER:
        missing_notes.extend(_collect_row_notes("analyst", key, data.get(key)))
        if not _row_has_data(data.get(key)):
            degradation_notes.append(f"analyst [empty]: {key}")
    if not _row_has_data(investment_debate_state):
        missing_notes.append("research team: investment debate unavailable")
        degradation_notes.append("research [empty]: investment_debate_state")
    if not _row_has_data(data.get("trader_investment_plan")):
        missing_notes.append("trader: investment plan unavailable")
        degradation_notes.append("trading [empty]: trader_investment_plan")
    if not _row_has_data(risk_debate_state):
        missing_notes.append("risk management: risk debate unavailable")
        degradation_notes.append("risk [empty]: risk_debate_state")

    summary = str(
        data.get("summary")
        or data.get("final_trade_decision")
        or data.get("investment_plan")
        or data.get("trader_investment_plan")
        or _row_summary(risk_debate_state.get("judge_decision") if isinstance(risk_debate_state, Mapping) else None)
        or "Legacy report ready"
    )
    runtime_trace = tuple(
        str(item)
        for item in data.get("runtime_trace", []) or []
    )

    return LegacyUiModel(
        ticker=ticker,
        company_of_interest=company_of_interest,
        market_label=market_label,
        runtime_mode=runtime_mode,
        asset_type=asset_type,
        trade_date=trade_date if trade_date is None or isinstance(trade_date, str) else str(trade_date),
        status=status,
        summary=summary,
        analyst_rows=analyst_rows,
        team_rows=team_rows,
        missing_data_notes=tuple(dict.fromkeys(missing_notes)),
        degradation_notes=tuple(dict.fromkeys(degradation_notes)),
        runtime_trace=runtime_trace,
        raw=data,
    )


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


def _render_rows(st: Any, title: str, rows: Sequence[LegacyReportRow]) -> None:
    subheader = getattr(st, "subheader", None)
    if callable(subheader):
        subheader(title)
    table = getattr(st, "table", None)
    if callable(table):
        table(
            [
                {
                    "group": row.group,
                    "name": row.name,
                    "status": row.status,
                    "has_data": row.has_data,
                    "summary": row.summary,
                }
                for row in rows
            ]
        )
    for row in rows:
        with _with_expander(st, f"{row.group}: {row.name}", expanded=False):
            markdown = getattr(st, "markdown", None)
            write = getattr(st, "write", None)
            if callable(markdown):
                markdown(row.summary)
            elif callable(write):
                write(row.summary)


def render_legacy_report_page(st: Any, payload: Mapping[str, Any] | Any) -> LegacyUiModel:
    model = build_legacy_ui_model(payload)

    title = getattr(st, "title", None)
    if callable(title):
        title(f"TradingAgents Legacy Report · {model.ticker}")

    caption = getattr(st, "caption", None)
    if callable(caption):
        caption(f"{model.market_label} · {model.runtime_mode} · {model.asset_type}")

    cols = _columns(st, 4)
    metric_labels = [
        ("Ticker", model.ticker),
        ("Market", model.market_label),
        ("Runtime Mode", model.runtime_mode),
        ("Status", model.status),
    ]
    for col, (label, value) in zip(cols, metric_labels, strict=False):
        metric = getattr(col, "metric", None)
        if callable(metric):
            metric(label, value)

    subheader = getattr(st, "subheader", None)
    if callable(subheader):
        subheader("Legacy Summary")
    markdown = getattr(st, "markdown", None)
    if callable(markdown):
        markdown(model.summary)

    _render_rows(st, "Analyst Team Output", model.analyst_rows)
    _render_rows(st, "Team Output", model.team_rows)

    warning = getattr(st, "warning", None)
    info = getattr(st, "info", None)
    if model.missing_data_notes:
        msg = "\n".join(f"- {note}" for note in model.missing_data_notes)
        if callable(warning):
            warning(msg)
        elif callable(info):
            info(msg)
    if model.degradation_notes:
        msg = "\n".join(f"- {note}" for note in model.degradation_notes)
        if callable(warning):
            warning(msg)
        elif callable(info):
            info(msg)

    json_block = getattr(st, "json", None)
    if callable(json_block):
        with _with_expander(st, "Raw legacy payload", expanded=False):
            json_block(model.raw)

    return model


__all__ = [
    "LEGACY_ANALYST_ORDER",
    "LEGACY_TEAM_ORDER",
    "LegacyReportRow",
    "LegacyUiModel",
    "build_legacy_ui_model",
    "is_legacy_report_payload",
    "render_legacy_report_page",
]
