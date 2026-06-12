"""Read-only UI helpers for TradingAgents reports."""

from .dispatcher import (
    AStockUiModel,
    LegacyUiModel,
    build_astock_ui_model,
    build_legacy_ui_model,
    is_astock_report_payload,
    is_legacy_report_payload,
    render_astock_report_page,
    render_legacy_report_page,
    render_report_page,
)
from .astock_views import ASTOCK_SECTION_ORDER
from .legacy_views import LEGACY_ANALYST_ORDER, LEGACY_TEAM_ORDER

__all__ = [
    "ASTOCK_SECTION_ORDER",
    "LEGACY_ANALYST_ORDER",
    "LEGACY_TEAM_ORDER",
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
