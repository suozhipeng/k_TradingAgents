from __future__ import annotations

from typing import Any, Mapping, Sequence

VIEWER_METRIC_ORDER: tuple[str, ...] = ("Ticker", "Trade Date", "Runtime Mode", "Status")
VIEWER_SECTION_ORDER: tuple[str, ...] = (
    "Core Summary",
    "Structured Status",
    "Secondary Outputs",
    "Coverage / Degradation",
    "Runtime Trace",
    "Raw Payload",
)


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


def _subheader(st: Any, title: str) -> None:
    subheader = getattr(st, "subheader", None)
    if callable(subheader):
        subheader(title)


def _markdown(st: Any, body: str) -> None:
    markdown = getattr(st, "markdown", None)
    write = getattr(st, "write", None)
    if callable(markdown):
        markdown(body)
    elif callable(write):
        write(body)


def _table(st: Any, rows: Sequence[Mapping[str, Any]]) -> None:
    table = getattr(st, "table", None)
    if callable(table):
        table(list(rows))


def _columns(st: Any, count: int):
    columns = getattr(st, "columns", None)
    if callable(columns):
        return columns(count)
    return tuple(_FallbackColumn(st) for _ in range(count))


def _with_expander(st: Any, label: str, expanded: bool = False):
    expander = getattr(st, "expander", None)
    if callable(expander):
        return expander(label, expanded=expanded)
    return _FallbackExpander()


def _divider(st: Any) -> None:
    divider = getattr(st, "divider", None)
    if callable(divider):
        divider()


def _render_notes(st: Any, notes: Sequence[str], empty_message: str) -> None:
    if not notes:
        info = getattr(st, "info", None)
        if callable(info):
            info(empty_message)
        return
    warning = getattr(st, "warning", None)
    info = getattr(st, "info", None)
    message = "\n".join(f"- {note}" for note in notes)
    if callable(warning):
        warning(message)
    elif callable(info):
        info(message)


def render_readonly_report_shell(
    st: Any,
    *,
    title: str,
    caption: str | None,
    metrics: Sequence[tuple[str, Any]],
    core_summary: str,
    structured_rows: Sequence[Mapping[str, Any]],
    secondary_blocks: Sequence[tuple[str, str]],
    coverage_rows: Sequence[Mapping[str, Any]],
    coverage_notes: Sequence[str] = (),
    degradation_notes: Sequence[str] = (),
    runtime_trace: Sequence[str] = (),
    raw_payload: Mapping[str, Any] | Any | None = None,
    structured_section_title: str = "Structured Status",
    secondary_section_title: str = "Secondary Outputs",
    coverage_section_title: str = "Coverage / Degradation",
    runtime_trace_title: str = "Runtime Trace",
    raw_payload_title: str = "Raw Payload",
    raw_payload_expander_label: str = "Raw Payload",
    coverage_empty_message: str = "No coverage details available.",
) -> None:
    title_fn = getattr(st, "title", None)
    if callable(title_fn):
        title_fn(title)

    caption_fn = getattr(st, "caption", None)
    if callable(caption_fn) and caption:
        caption_fn(caption)

    metric_cols = _columns(st, max(len(metrics), len(VIEWER_METRIC_ORDER)))
    for col, (label, value) in zip(metric_cols, metrics, strict=False):
        metric = getattr(col, "metric", None)
        if callable(metric):
            metric(label, value)

    _subheader(st, "Core Summary")
    _markdown(st, core_summary)
    _divider(st)

    _subheader(st, structured_section_title)
    _table(st, structured_rows)
    _divider(st)

    _subheader(st, secondary_section_title)
    for heading, body in secondary_blocks:
        with _with_expander(st, heading, expanded=True):
            _markdown(st, body)
    _divider(st)

    _subheader(st, coverage_section_title)
    if coverage_rows:
        _table(st, coverage_rows)
    else:
        info = getattr(st, "info", None)
        if callable(info):
            info(coverage_empty_message)
    _render_notes(st, coverage_notes, "No coverage notes.")
    _render_notes(st, degradation_notes, "No degradation notes.")
    _divider(st)

    if runtime_trace:
        _subheader(st, runtime_trace_title)
        _markdown(st, "\n".join(f"- {step}" for step in runtime_trace))
        _divider(st)

    if raw_payload is not None:
        _subheader(st, raw_payload_title)
        json_block = getattr(st, "json", None)
        if callable(json_block):
            with _with_expander(st, raw_payload_expander_label, expanded=False):
                json_block(raw_payload)


__all__ = ["VIEWER_METRIC_ORDER", "VIEWER_SECTION_ORDER", "render_readonly_report_shell"]
