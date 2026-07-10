"""Alert REST API — BL-309 条件告警规则.

All routes are mounted under ``/api/v1/alerts``.

Endpoints
---------
GET    /api/v1/alerts              — list open/recent alert events
GET    /api/v1/alerts/rules         — list alert rules
POST   /api/v1/alerts/rules         — create a new rule
PATCH  /api/v1/alerts/rules/<id>    — update a rule
DELETE /api/v1/alerts/rules/<id>    — delete a rule
POST   /api/v1/alerts/<id>/ack      — acknowledge an alert
GET    /api/v1/alerts/check         — check all enabled rules (scheduler)
"""

from __future__ import annotations

import logging

from datetime import datetime
from enum import Enum
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request

from tradingagents.astock.alert.alert_store import (
    AlertEvent,
    AlertRule,
    AlertStore,
    TriggerDirection,
    TriggerType,
)
from ._helpers import _as_bool

bp = Blueprint("alerts", __name__)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# AlertStore accessor
# ---------------------------------------------------------------------------


def _alert_store() -> AlertStore:
    """Return the app-level AlertStore singleton (lazy init)."""
    store: AlertStore | None = current_app.config.get("ALERT_STORE")
    if store is None:
        db_path = current_app.config.get("DB_PATH", "")
        store = AlertStore(db_path=db_path)
        current_app.config["ALERT_STORE"] = store
    return store


# ---------------------------------------------------------------------------
# GET /api/v1/alerts
# ---------------------------------------------------------------------------


@bp.route("/alerts")
def list_alerts() -> tuple[Response, int]:
    """Return open / recent alert events.

    Query params:
        limit (int, default 20)
        status (str, optional) — filter by status
    """
    try:
        limit = int(request.args.get("limit", 20))
        status_filter = request.args.get("status", "").strip().lower()
        store = _alert_store()

        if status_filter:
            events = store.list_events(limit=limit)
            events = [e for e in events if e.status == status_filter]
        else:
            events = store.get_open_alerts(limit=limit)

        return jsonify(
            {
                "alerts": [asdict_safe(e) for e in events],
                "total": len(events),
                "status": "ok",
            }
        ), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500, "alerts": [], "total": 0}), 500


# ---------------------------------------------------------------------------
# POST /api/v1/alerts  — create a direct alert event (e.g. from strategy hook)
# ---------------------------------------------------------------------------


@bp.route("/alerts", methods=["POST"])
def create_alert() -> tuple[Response, int]:
    """Create a direct alert event (not rule-triggered).

    JSON body::
        {
            "symbol": "000001.SH",
            "trigger_type": "strategy|risk",
            "severity": "info|warn|critical",
            "message": "...",
            "current_value": 123.45
        }
    """
    try:
        body: dict[str, Any] = request.get_json(force=True, silent=True) or {}
        if not body.get("symbol"):
            return jsonify({"error": "symbol is required", "status": 400}), 400
        trigger_type = body.get("trigger_type", TriggerType.STRATEGY.value)
        if trigger_type not in {t.value for t in TriggerType}:
            return jsonify({"error": f"invalid trigger_type: {trigger_type}", "status": 400}), 400
        severity = body.get("severity", "info")
        if severity not in ("info", "warn", "critical"):
            return jsonify({"error": f"invalid severity: {severity}", "status": 400}), 400
        from tradingagents.astock.alert.alert_store import AlertEvent

        event = AlertEvent(
            rule_id=body.get("rule_id", "direct"),
            symbol=body["symbol"],
            trigger_type=trigger_type,
            severity=severity,
            message=str(body.get("message", "")),
            current_value=float(body.get("current_value", 0.0)),
            threshold=float(body.get("threshold", 0.0)),
            source=body.get("source", "strategy_hook"),
        )
        store = _alert_store()
        created = store.create_event(event)
        return jsonify({"alert": asdict_safe(created), "status": "created"}), 201
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# GET /api/v1/alerts/rules

@bp.route("/alerts/rules")
def list_rules() -> tuple[Response, int]:
    """List all alert rules (optionally only enabled ones)."""
    try:
        enabled_only = request.args.get("enabled", "").lower() in ("1", "true", "yes")
        store = _alert_store()
        rules = store.list_rules(enabled_only=enabled_only)
        return jsonify(
            {
                "rules": [asdict_safe(r) for r in rules],
                "total": len(rules),
                "status": "ok",
            }
        ), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500, "rules": [], "total": 0}), 500


# ---------------------------------------------------------------------------
# POST /api/v1/alerts/rules
# ---------------------------------------------------------------------------


@bp.route("/alerts/rules", methods=["POST"])
def create_rule() -> tuple[Response, int]:
    """Create a new alert rule.

    JSON body::
        {
            "symbol": "000001.SH",
            "trigger_type": "price|pct|volume|strategy|risk",
            "threshold": 3200.0,
            "direction": "above|below",
            "severity": "info|warn|critical",
            "label": "上证指数突破3200",
            "enabled": true
        }
    """
    try:
        body: dict[str, Any] = request.get_json(force=True, silent=True) or {}
        if not body.get("symbol"):
            return jsonify({"error": "symbol is required", "status": 400}), 400
        if "threshold" not in body:
            return jsonify({"error": "threshold is required", "status": 400}), 400

        # Validate trigger_type
        trigger_type = str(body.get("trigger_type", TriggerType.PRICE.value)).strip().lower()
        valid_types = {t.value for t in TriggerType}
        if trigger_type not in valid_types:
            return jsonify({"error": f"invalid trigger_type, must be one of {valid_types}", "status": 400}), 400

        direction = str(body.get("direction", TriggerDirection.ABOVE.value)).strip().lower()
        valid_dirs = {d.value for d in TriggerDirection}
        if direction not in valid_dirs:
            return jsonify({"error": f"invalid direction, must be one of {valid_dirs}", "status": 400}), 400

        severity = str(body.get("severity", "warn")).strip().lower()
        valid_sev = {"info", "warn", "critical"}
        if severity not in valid_sev:
            return jsonify({"error": f"invalid severity, must be one of {valid_sev}", "status": 400}), 400

        rule = AlertRule(
            symbol=body["symbol"],
            trigger_type=trigger_type,
            threshold=float(body["threshold"]),
            direction=direction,
            severity=severity,
            label=str(body.get("label", "")),
            enabled=_as_bool(body.get("enabled"), True),
        )
        store = _alert_store()
        created = store.create_rule(rule)
        return jsonify({"rule": asdict_safe(created), "status": "created"}), 201
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# PATCH /api/v1/alerts/rules/<rule_id>
# ---------------------------------------------------------------------------


@bp.route("/alerts/rules/<rule_id>", methods=["PATCH"])
def update_rule(rule_id: str) -> tuple[Response, int]:
    """Update fields on an existing alert rule."""
    try:
        body: dict[str, Any] = request.get_json(force=True, silent=True) or {}
        allowed = {"threshold", "direction", "severity", "label", "enabled", "trigger_type"}
        updates = {k: v for k, v in body.items() if k in allowed}

        if not updates:
            return jsonify({"error": "no valid fields to update", "status": 400}), 400

        store = _alert_store()
        updated = store.update_rule(rule_id, updates)
        if updated is None:
            return jsonify({"error": "rule not found", "status": 404}), 404
        return jsonify({"rule": asdict_safe(updated), "status": "updated"}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# DELETE /api/v1/alerts/rules/<rule_id>
# ---------------------------------------------------------------------------


@bp.route("/alerts/rules/<rule_id>", methods=["DELETE"])
def delete_rule(rule_id: str) -> tuple[Response, int]:
    """Delete an alert rule (and its events)."""
    try:
        store = _alert_store()
        ok = store.delete_rule(rule_id)
        if not ok:
            return jsonify({"error": "rule not found", "status": 404}), 404
        return jsonify({"status": "deleted"}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# POST /api/v1/alerts/<alert_id>/ack
# ---------------------------------------------------------------------------


@bp.route("/alerts/<alert_id>/ack", methods=["POST"])
def acknowledge_alert(alert_id: str) -> tuple[Response, int]:
    """Mark an alert as acknowledged."""
    try:
        store = _alert_store()
        event = store.acknowledge(alert_id)
        if event is None:
            return jsonify({"error": "alert not found", "status": 404}), 404
        return jsonify({"alert": asdict_safe(event), "status": "acknowledged"}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# GET /api/v1/alerts/check
# ---------------------------------------------------------------------------


@bp.route("/alerts/check")
def check_alerts() -> tuple[Response, int]:
    """Check all enabled rules against current market data.

    This is the engine endpoint — called by scheduler or manually.
    It iterates enabled rules, fetches current data for each symbol,
    and fires AlertEvent records for any threshold breaches.
    """
    try:
        store = _alert_store()
        rules = store.list_rules(enabled_only=True)
        triggered: list[dict[str, Any]] = []

        # Try to get a data source; gracefully degrade
        facade = current_app.config.get("DATA_FACADE")
        if not facade:
            # No facade — cannot check price-based rules; return gracefully
            return jsonify(
                {
                    "checked": len(rules),
                    "triggered": 0,
                    "alerts": [],
                    "message": "no data facade available — cannot check price/volume rules",
                    "status": "ok",
                }
            ), 200

        for rule in rules:
            try:
                event = _evaluate_rule(rule, facade)
                if event:
                    store.create_event(event)
                    triggered.append(asdict_safe(event))
            except Exception as exc:
                logger.debug("Failed to evaluate rule %s: %s", rule.rule_id, exc)

        return jsonify(
            {
                "checked": len(rules),
                "triggered": len(triggered),
                "alerts": triggered,
                "status": "ok",
            }
        ), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "checked": 0, "triggered": 0, "status": 500}), 500


# ---------------------------------------------------------------------------
# Internal — rule evaluation
# ---------------------------------------------------------------------------


def _evaluate_rule(rule: AlertRule, facade: Any) -> AlertEvent | None:
    """Check *rule* against current data from *facade*.

    Returns an AlertEvent if triggered, None otherwise.
    """
    symbol = rule.symbol
    trigger_type = rule.trigger_type
    threshold = rule.threshold
    direction = rule.direction
    severity = rule.severity

    try:
        if trigger_type in (TriggerType.PRICE.value, TriggerType.PCT.value):
            # Fetch latest kline for price/pct checks
            resp = facade.get_kline(symbol=symbol, interval="1d", limit=5)
            if resp.status != "ok" or not resp.data or not resp.data.get("bars"):
                return None
            bars = resp.data["bars"]
            if not bars:
                return None

            latest = bars[-1]
            close = float(latest.get("close", 0) or 0)

            if trigger_type == TriggerType.PRICE.value:
                if _breached(close, threshold, direction):
                    return AlertEvent(
                        rule_id=rule.rule_id,
                        symbol=symbol,
                        trigger_type=trigger_type,
                        severity=severity,
                        message=f"价格 {close:.2f} {'≥' if direction == 'above' else '≤'} 阈值 {threshold}",
                        current_value=close,
                        threshold=threshold,
                        source=resp.source or "facade",
                    )

            elif trigger_type == TriggerType.PCT.value and len(bars) >= 2:
                prev_close = float(bars[-2].get("close", 0) or 0)
                if prev_close != 0:
                    change_pct = ((close - prev_close) / prev_close) * 100.0
                    if _breached(change_pct, threshold, direction):
                        return AlertEvent(
                            rule_id=rule.rule_id,
                            symbol=symbol,
                            trigger_type=trigger_type,
                            severity=severity,
                            message=f"涨幅 {change_pct:+.2f}% {'≥' if direction == 'above' else '≤'} 阈值 {threshold}%",
                            current_value=round(change_pct, 2),
                            threshold=threshold,
                            source=resp.source or "facade",
                        )

        elif trigger_type == TriggerType.VOLUME.value:
            # Fetch kline with enough bars to get a volume average
            resp = facade.get_kline(symbol=symbol, interval="1d", limit=25)
            if resp.status != "ok" or not resp.data or not resp.data.get("bars"):
                return None
            bars = resp.data["bars"]
            if len(bars) < 2:
                return None

            latest_vol = float(bars[-1].get("volume", 0) or 0)
            # Average volume excluding the latest bar
            vols = [float(b.get("volume", 0) or 0) for b in bars[:-1]]
            avg_vol = sum(vols) / len(vols) if vols else 1.0
            vol_ratio = (latest_vol / avg_vol * 100) if avg_vol > 0 else 0

            if _breached(vol_ratio, threshold, direction):
                return AlertEvent(
                    rule_id=rule.rule_id,
                    symbol=symbol,
                    trigger_type=trigger_type,
                    severity=severity,
                    message=f"量比 {vol_ratio:.1f}% {'≥' if direction == 'above' else '≤'} 阈值 {threshold}%",
                    current_value=round(vol_ratio, 1),
                    threshold=threshold,
                    source=resp.source or "facade",
                )

        elif trigger_type == TriggerType.STRATEGY.value:
            # Strategy-based alerts: check if any backtest result meets criteria
            from flask import current_app
            store = current_app.config.get("STORE") if current_app else None
            if store:
                try:
                    bt_df = store.get_backtest_results()
                    if bt_df is not None and not bt_df.empty:
                        symbol_bts = bt_df[bt_df["symbol"] == symbol]
                        if not symbol_bts.empty:
                            latest_bt = symbol_bts.iloc[-1]
                            total_ret = float(latest_bt.get("total_return", 0) or 0)
                            max_dd = float(latest_bt.get("max_drawdown", 0) or 0)
                            if direction == TriggerDirection.ABOVE.value:
                                if total_ret >= threshold:
                                    return AlertEvent(
                                        rule_id=rule.rule_id,
                                        symbol=symbol,
                                        trigger_type=trigger_type,
                                        severity=severity,
                                        message=f"策略收益 {total_ret*100:.1f}% ≥ 阈值 {threshold}%",
                                        current_value=round(total_ret * 100, 2),
                                        threshold=threshold,
                                        source="strategy_backtest",
                                    )
                            else:
                                if total_ret <= threshold:
                                    return AlertEvent(
                                        rule_id=rule.rule_id,
                                        symbol=symbol,
                                        trigger_type=trigger_type,
                                        severity=severity,
                                        message=f"策略收益 {total_ret*100:.1f}% ≤ 阈值 {threshold}%",
                                        current_value=round(total_ret * 100, 2),
                                        threshold=threshold,
                                        source="strategy_backtest",
                                    )
                except Exception as exc:
                    logger.debug("Failed to check strategy alert for %s: %s", symbol, exc)

        elif trigger_type == TriggerType.RISK.value:
            # Risk-based alerts: check portfolio risk metrics
            from flask import current_app
            store = current_app.config.get("STORE") if current_app else None
            if store:
                try:
                    trades_df = store.get_paper_trades()
                    if trades_df is not None and not trades_df.empty:
                        symbol_trades = trades_df[trades_df["symbol"] == symbol]
                        if not symbol_trades.empty:
                            # Check if max drawdown exceeds threshold
                            latest_trade = symbol_trades.iloc[-1]
                            pnl = float(latest_trade.get("pnl", 0) or 0)
                            if direction == TriggerDirection.ABOVE.value:
                                if pnl >= threshold:
                                    return AlertEvent(
                                        rule_id=rule.rule_id,
                                        symbol=symbol,
                                        trigger_type=trigger_type,
                                        severity=severity,
                                        message=f"持仓盈亏 {pnl:.2f} ≥ 阈值 {threshold}",
                                        current_value=round(pnl, 2),
                                        threshold=threshold,
                                        source="risk_monitor",
                                    )
                            else:
                                if pnl <= threshold:
                                    return AlertEvent(
                                        rule_id=rule.rule_id,
                                        symbol=symbol,
                                        trigger_type=trigger_type,
                                        severity=severity,
                                        message=f"持仓盈亏 {pnl:.2f} ≤ 阈值 {threshold}",
                                        current_value=round(pnl, 2),
                                        threshold=threshold,
                                        source="risk_monitor",
                                    )
                except Exception as exc:
                    logger.debug("Failed to check risk alert for %s: %s", symbol, exc)

    except Exception as exc:
        logger.debug("Rule evaluation failed for %s: %s", rule.symbol, exc)
        return None

    return None


def _breached(value: float, threshold: float, direction: str) -> bool:
    """Return True if *value* breaches *threshold* in *direction*."""
    if direction == TriggerDirection.ABOVE.value:
        return value >= threshold
    return value <= threshold


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def asdict_safe(obj: Any) -> dict[str, Any]:
    """Convert a dataclass instance to a plain dict, handling Enums."""
    d = {}
    for field_name in dir(obj):
        if field_name.startswith("_"):
            continue
        val = getattr(obj, field_name, None)
        if callable(val):
            continue
        if isinstance(val, Enum):
            val = val.value
        d[field_name] = val
    return d
