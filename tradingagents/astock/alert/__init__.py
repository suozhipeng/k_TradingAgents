"""Alert & notification framework for AStock — Phase BL-309.

Components
----------
alert_store
    Rule and event persistence (DuckDB-backed dict store).
routes_alerts
    REST API endpoints mounted under ``/api/v1/alerts/``.
"""

from __future__ import annotations

from .alert_store import AlertEvent, AlertRule, AlertSeverity, AlertStatus, AlertStore, TriggerDirection, TriggerType

__all__ = [
    "AlertRule",
    "AlertEvent",
    "AlertStore",
    "TriggerType",
    "TriggerDirection",
    "AlertSeverity",
    "AlertStatus",
]
