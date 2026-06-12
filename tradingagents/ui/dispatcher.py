from __future__ import annotations

from typing import Any

from .astock_views import AStockUiModel, build_astock_ui_model, is_astock_report_payload, render_astock_report_page
from .legacy_views import LegacyUiModel, build_legacy_ui_model, is_legacy_report_payload, render_legacy_report_page


def render_report_page(st: Any, payload: Any, legacy_renderer: Any | None = None):
    if is_astock_report_payload(payload):
        return render_astock_report_page(st, payload)
    if callable(legacy_renderer):
        return legacy_renderer(st, payload)
    if is_legacy_report_payload(payload):
        return render_legacy_report_page(st, payload)
    return render_legacy_report_page(st, payload)


__all__ = [
    "AStockUiModel",
    "LegacyUiModel",
    "build_astock_ui_model",
    "build_legacy_ui_model",
    "is_astock_report_payload",
    "is_legacy_report_payload",
    "render_astock_report_page",
    "render_legacy_report_page",
    "render_report_page",
]
