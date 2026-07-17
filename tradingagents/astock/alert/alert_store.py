"""Alert rule + event store — DuckDB-backed dict store.

Trigger types
-------------
price    — compare latest price against threshold
pct      — compare % change against threshold
volume   — compare volume against historical average
strategy — strategy-generated signal / recommendation
risk     — risk control threshold breach
"""

from __future__ import annotations

import logging

import json
import os
import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import duckdb
import pandas as pd
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TriggerType(str, Enum):
    PRICE = "price"
    PCT = "pct"
    VOLUME = "volume"
    STRATEGY = "strategy"
    RISK = "risk"


class TriggerDirection(str, Enum):
    ABOVE = "above"
    BELOW = "below"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARN = "warn"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class AlertRule:
    """A user-defined alert rule that fires when a condition is met."""

    rule_id: str = ""
    symbol: str = ""
    trigger_type: str = TriggerType.PRICE.value
    threshold: float = 0.0
    direction: str = TriggerDirection.ABOVE.value
    severity: str = AlertSeverity.WARN.value
    label: str = ""  # Human-readable label
    enabled: bool = True
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.rule_id:
            self.rule_id = str(uuid.uuid4())[:8]
        if not self.created_at:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class AlertEvent:
    """A fired alert instance tied to a rule."""

    alert_id: str = ""
    rule_id: str = ""
    symbol: str = ""
    trigger_type: str = TriggerType.PRICE.value
    severity: str = AlertSeverity.WARN.value
    status: str = AlertStatus.OPEN.value
    message: str = ""
    current_value: float = 0.0
    threshold: float = 0.0
    source: str = "store"
    triggered_at: str = ""
    acknowledged_at: str = ""
    resolved_at: str = ""

    def __post_init__(self) -> None:
        if not self.alert_id:
            self.alert_id = str(uuid.uuid4())[:8]
        if not self.triggered_at:
            self.triggered_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# DuckDB-backed alert store
# ---------------------------------------------------------------------------


CREATE_ALERT_RULES = """
CREATE TABLE IF NOT EXISTS alert_rules (
    rule_id VARCHAR PRIMARY KEY,
    symbol VARCHAR NOT NULL,
    trigger_type VARCHAR NOT NULL,
    threshold DOUBLE NOT NULL,
    direction VARCHAR NOT NULL DEFAULT 'above',
    severity VARCHAR NOT NULL DEFAULT 'warn',
    label VARCHAR DEFAULT '',
    enabled BOOLEAN DEFAULT TRUE,
    created_at VARCHAR DEFAULT ''
)
"""

CREATE_ALERT_EVENTS = """
CREATE TABLE IF NOT EXISTS alert_events (
    alert_id VARCHAR PRIMARY KEY,
    rule_id VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    trigger_type VARCHAR NOT NULL,
    severity VARCHAR NOT NULL DEFAULT 'warn',
    status VARCHAR NOT NULL DEFAULT 'open',
    message VARCHAR DEFAULT '',
    current_value DOUBLE DEFAULT 0.0,
    threshold DOUBLE DEFAULT 0.0,
    source VARCHAR DEFAULT 'store',
    triggered_at VARCHAR DEFAULT '',
    acknowledged_at VARCHAR DEFAULT '',
    resolved_at VARCHAR DEFAULT ''
)
"""


class AlertStore:
    """Persistent alert rule + event store backed by DuckDB.

    Thread-safe via an internal lock. Falls back to in-memory dict if
    DuckDB is unavailable.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._lock = threading.Lock()
        self._db_path: str | None = db_path
        self._conn: duckdb.DuckDBPyConnection | None = None
        self._mem_rules: dict[str, dict[str, Any]] = {}
        self._mem_events: dict[str, dict[str, Any]] = {}
        self._use_db = False

        if db_path:
            try:
                resolved = os.path.expanduser(db_path) if "~" in db_path else db_path
                self._conn = duckdb.connect(resolved)
                self._conn.execute(CREATE_ALERT_RULES)
                self._conn.execute(CREATE_ALERT_EVENTS)
                self._use_db = True
            except Exception:
                self._use_db = False

    # ---- helpers ----------------------------------------------------------

    def _rule_to_row(self, rule: AlertRule) -> dict[str, Any]:
        return asdict(rule)

    def _event_to_row(self, event: AlertEvent) -> dict[str, Any]:
        return asdict(event)

    def _row_to_rule(self, row: dict[str, Any]) -> AlertRule:
        return AlertRule(**row)

    def _row_to_event(self, row: dict[str, Any]) -> AlertEvent:
        return AlertEvent(**row)

    # ---- rules ------------------------------------------------------------

    def create_rule(self, rule: AlertRule) -> AlertRule:
        with self._lock:
            row = self._rule_to_row(rule)
            if self._use_db and self._conn:
                self._conn.execute(
                    "INSERT OR REPLACE INTO alert_rules VALUES (?,?,?,?,?,?,?,?,?)",
                    [
                        row["rule_id"],
                        row["symbol"],
                        row["trigger_type"],
                        row["threshold"],
                        row["direction"],
                        row["severity"],
                        row["label"],
                        row["enabled"],
                        row["created_at"],
                    ],
                )
            self._mem_rules[rule.rule_id] = row
        return rule

    def get_rule(self, rule_id: str) -> AlertRule | None:
        with self._lock:
            if self._use_db and self._conn:
                try:
                    df = self._conn.execute(
                        "SELECT * FROM alert_rules WHERE rule_id = ?", [rule_id]
                    ).fetchdf()
                    if not df.empty:
                        return self._row_to_rule(df.iloc[0].to_dict())
                except Exception as e:
                    logger.debug("AlertStore: get_rule failed for %s: %s", rule_id, e)
            row = self._mem_rules.get(rule_id)
            return self._row_to_rule(row) if row else None

    def list_rules(self, enabled_only: bool = False) -> list[AlertRule]:
        with self._lock:
            rules: list[AlertRule] = []
            if self._use_db and self._conn:
                try:
                    sql = "SELECT * FROM alert_rules"
                    if enabled_only:
                        sql += " WHERE enabled = TRUE"
                    df = self._conn.execute(sql).fetchdf()
                    if not df.empty:
                        for _, row in df.iterrows():
                            rules.append(self._row_to_rule(row.to_dict()))
                except Exception as e:
                    logger.debug("AlertStore: list_rules failed: %s", e)
            # Fallback to memory if DB failed or returned empty
            if not rules:
                for row in self._mem_rules.values():
                    if enabled_only and not row.get("enabled", True):
                        continue
                    rules.append(self._row_to_rule(row))
            return rules

    def update_rule(self, rule_id: str, updates: dict[str, Any]) -> AlertRule | None:
        rule = self.get_rule(rule_id)
        if rule is None:
            return None
        for k, v in updates.items():
            if hasattr(rule, k) and k != "rule_id":
                setattr(rule, k, v)
        with self._lock:
            row = self._rule_to_row(rule)
            if self._use_db and self._conn:
                self._conn.execute(
                    "INSERT OR REPLACE INTO alert_rules VALUES (?,?,?,?,?,?,?,?,?)",
                    [
                        row["rule_id"],
                        row["symbol"],
                        row["trigger_type"],
                        row["threshold"],
                        row["direction"],
                        row["severity"],
                        row["label"],
                        row["enabled"],
                        row["created_at"],
                    ],
                )
            self._mem_rules[rule_id] = row
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        with self._lock:
            if self._use_db and self._conn:
                self._conn.execute("DELETE FROM alert_rules WHERE rule_id = ?", [rule_id])
                self._conn.execute("DELETE FROM alert_events WHERE rule_id = ?", [rule_id])
            self._mem_rules.pop(rule_id, None)
            # Also clean up events for this rule
            to_delete = [k for k in self._mem_events if self._mem_events[k].get("rule_id") == rule_id]
            for k in to_delete:
                self._mem_events.pop(k, None)
        return True

    # ---- events -----------------------------------------------------------

    def create_event(self, event: AlertEvent) -> AlertEvent:
        with self._lock:
            row = self._event_to_row(event)
            if self._use_db and self._conn:
                self._conn.execute(
                    "INSERT OR REPLACE INTO alert_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [
                        row["alert_id"],
                        row["rule_id"],
                        row["symbol"],
                        row["trigger_type"],
                        row["severity"],
                        row["status"],
                        row["message"],
                        row["current_value"],
                        row["threshold"],
                        row["source"],
                        row["triggered_at"],
                        row["acknowledged_at"],
                        row["resolved_at"],
                    ],
                )
            self._mem_events[event.alert_id] = row
        return event

    def get_open_alerts(self, limit: int = 20) -> list[AlertEvent]:
        with self._lock:
            events: list[AlertEvent] = []
            if self._use_db and self._conn:
                try:
                    df = self._conn.execute(
                        "SELECT * FROM alert_events WHERE status IN ('open','acknowledged') ORDER BY triggered_at DESC LIMIT ?",
                        [limit],
                    ).fetchdf()
                    if not df.empty:
                        for _, row in df.iterrows():
                            events.append(self._row_to_event(row.to_dict()))
                except Exception as e:
                    logger.debug("AlertStore: get_open_alerts failed: %s", e)
            if not events:
                all_events = sorted(
                    self._mem_events.values(),
                    key=lambda r: r.get("triggered_at", ""),
                    reverse=True,
                )
                count = 0
                for row in all_events:
                    if row.get("status") in ("open", "acknowledged"):
                        events.append(self._row_to_event(row))
                        count += 1
                        if count >= limit:
                            break
            return events

    def list_events(self, limit: int = 50) -> list[AlertEvent]:
        with self._lock:
            events: list[AlertEvent] = []
            if self._use_db and self._conn:
                try:
                    df = self._conn.execute(
                        "SELECT * FROM alert_events ORDER BY triggered_at DESC LIMIT ?",
                        [limit],
                    ).fetchdf()
                    if not df.empty:
                        for _, row in df.iterrows():
                            events.append(self._row_to_event(row.to_dict()))
                except Exception as e:
                    logger.debug("AlertStore: list_events failed: %s", e)
            if not events:
                all_events = sorted(
                    self._mem_events.values(),
                    key=lambda r: r.get("triggered_at", ""),
                    reverse=True,
                )
                for row in all_events[:limit]:
                    events.append(self._row_to_event(row))
            return events

    def acknowledge(self, alert_id: str) -> AlertEvent | None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            if self._use_db and self._conn:
                self._conn.execute(
                    "UPDATE alert_events SET status = 'acknowledged', acknowledged_at = ? WHERE alert_id = ?",
                    [now, alert_id],
                )
            row = self._mem_events.get(alert_id)
            if row:
                row["status"] = AlertStatus.ACKNOWLEDGED.value
                row["acknowledged_at"] = now
                return self._row_to_event(row)
            return None

    def resolve(self, alert_id: str) -> AlertEvent | None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            if self._use_db and self._conn:
                self._conn.execute(
                    "UPDATE alert_events SET status = 'resolved', resolved_at = ? WHERE alert_id = ?",
                    [now, alert_id],
                )
            row = self._mem_events.get(alert_id)
            if row:
                row["status"] = AlertStatus.RESOLVED.value
                row["resolved_at"] = now
                return self._row_to_event(row)
            return None

    # ---- Lifecycle --------------------------------------------------------

    def close(self) -> None:
        """Close the DuckDB connection if open."""
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    logger.debug("AlertStore: failed to close DuckDB connection", exc_info=True)
                self._conn = None
                self._use_db = False

    def __enter__(self) -> "AlertStore":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
