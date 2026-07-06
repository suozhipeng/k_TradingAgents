"""Notification / push settings API — thin route layer."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import requests as http_requests
from flask import Blueprint, jsonify, request

from ._notification_delivery import send_desktop
from ._notification_runtime import runtime

logger = logging.getLogger(__name__)
bp = Blueprint("notifications", __name__)


def set_notification_store(store: Any) -> None:
    """Inject the AStockStore for persistence. Called from create_app."""
    runtime.set_store(store)


@bp.route("/notifications/test-webhook", methods=["POST"])
def test_webhook() -> tuple[Any, int]:
    """Test a webhook URL by sending a test payload."""
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    message = data.get("message", "AStock Pro notification test")

    if not url:
        return jsonify({"error": "url is required", "status": 400}), 400

    payload = {
        "source": "astock-pro",
        "type": "test",
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }

    try:
        resp = http_requests.post(url, json=payload, headers={"User-Agent": "AStockPro/1.0"}, timeout=10)
        if resp.ok:
            logger.info("Webhook test OK: %s -> %s", url, resp.status_code)
            return jsonify({"status": "ok", "http_status": resp.status_code}), 200
        logger.warning("Webhook test failed: %s -> %s", url, resp.status_code)
        return jsonify({"status": "error", "http_status": resp.status_code}), 502
    except Exception as exc:
        logger.warning("Webhook test error: %s - %s", url, exc)
        return jsonify({"status": "error", "error": str(exc)[:200]}), 502


@bp.route("/notifications/dingtalk", methods=["POST"])
def send_dingtalk() -> tuple[Any, int]:
    """Send a DingTalk webhook notification directly."""
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    title = data.get("title", "AStock Pro notification")
    message = data.get("message", "System notification")

    if not url:
        return jsonify({"error": "url is required", "status": 400}), 400

    payload = {"msgtype": "markdown", "markdown": {"title": title, "text": message}}
    try:
        resp = http_requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
        if resp.ok:
            return jsonify({"status": "ok"}), 200
        logger.warning("DingTalk send failed: %s -> %s", url, resp.status_code)
        return jsonify({"status": "error", "http_status": resp.status_code}), 502
    except Exception as exc:
        logger.warning("DingTalk send error: %s - %s", url, exc)
        return jsonify({"status": "error", "error": str(exc)[:200]}), 502


@bp.route("/notifications/email", methods=["POST"])
def send_email_notification() -> tuple[Any, int]:
    """Send a test email notification."""
    data = request.get_json(silent=True) or {}
    smtp_host = data.get("smtp_host", "smtp.gmail.com")
    smtp_port = data.get("smtp_port", 587)
    smtp_user = data.get("smtp_user", "")
    smtp_pass = data.get("smtp_pass", "")
    to_address = data.get("to_address", "")
    subject = data.get("subject", "AStock Pro test email")
    body = data.get("body", "This is a test email from AStock Pro.")

    if not smtp_user or not smtp_pass or not to_address:
        return jsonify({"error": "smtp_user, smtp_pass, and to_address are required", "status": 400}), 400

    import smtplib
    import ssl
    from email.mime.text import MIMEText

    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_address

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [to_address], msg.as_string())
        logger.info("Test email sent to %s", to_address)
        return jsonify({"status": "ok"}), 200
    except Exception as exc:
        logger.warning("Email send failed: %s", exc)
        return jsonify({"status": "error", "error": str(exc)[:200]}), 502


@bp.route("/notifications/desktop", methods=["POST"])
def send_desktop_notification() -> tuple[Any, int]:
    """Send a desktop notification (for testing)."""
    data = request.get_json(silent=True) or {}
    title = data.get("title", "AStock Pro")
    message = data.get("message", "System notification")
    channel = {"name": "test-desktop", "kind": "desktop", "urgency": data.get("urgency", "normal")}
    event = {"type": "test", "title": title, "message": message, "timestamp": datetime.now().isoformat()}
    try:
        send_desktop(channel, event)
        return jsonify({"status": "ok"}), 200
    except Exception as exc:
        logger.warning("Desktop notification failed: %s", exc)
        return jsonify({"status": "error", "error": str(exc)[:200]}), 502


@bp.route("/notifications/dispatchers")
def list_dispatchers() -> tuple[Any, int]:
    """List configured notification channels."""
    return jsonify(
        {
            "dispatchers": runtime.list_channels(),
            "consumer_running": runtime.is_consumer_running(),
        }
    ), 200


@bp.route("/notifications/dispatchers", methods=["POST"])
def register_dispatcher() -> tuple[Any, int]:
    """Register a notification channel."""
    data = request.get_json(silent=True) or {}
    name = data.get("name") or ""
    kind = data.get("kind", "generic")
    url = data.get("url", "")

    if not name:
        return jsonify({"error": "name is required", "status": 400}), 400

    channel = {
        "name": name,
        "kind": kind,
        "url": url,
        "enabled": True,
        **{k: v for k, v in data.items() if k not in ("name", "kind", "url")},
    }
    runtime.register_channel(channel)
    logger.info("Registered notification dispatcher: %s (kind=%s)", name, kind)
    return jsonify({"status": "ok", "dispatcher": channel}), 201


@bp.route("/notifications/dispatchers/<name>", methods=["PUT"])
def update_dispatcher(name: str) -> tuple[Any, int]:
    """Update a notification channel."""
    data = request.get_json(silent=True) or {}
    channel = runtime.update_channel(name, data)
    if channel is None:
        return jsonify({"error": f"Dispatcher not found: {name}", "status": 404}), 404
    logger.info("Updated notification dispatcher: %s", name)
    return jsonify({"status": "ok", "dispatcher": channel}), 200


@bp.route("/notifications/dispatchers/<name>", methods=["DELETE"])
def delete_dispatcher(name: str) -> tuple[Any, int]:
    """Delete a notification channel by name."""
    runtime.delete_channel(name)
    logger.info("Deleted notification dispatcher: %s", name)
    return jsonify({"status": "ok"}), 200


@bp.route("/notifications/events")
def list_notification_events() -> tuple[Any, int]:
    """Return recent filtered events from the EventBus ring buffer."""
    return jsonify({"events": runtime.recent_events()}), 200


@bp.route("/notifications/consumer/start", methods=["POST"])
def start_consumer() -> tuple[Any, int]:
    """Start the notification consumer thread."""
    runtime.start_consumer()
    return jsonify({"status": "ok", "running": True}), 200


@bp.route("/notifications/consumer/stop", methods=["POST"])
def stop_consumer_route() -> tuple[Any, int]:
    """Stop the notification consumer thread."""
    runtime.stop_consumer()
    return jsonify({"status": "ok", "running": False}), 200


_channels = runtime.channels
_channels_lock = runtime.channels_lock
_start_consumer = runtime.start_consumer
_stop_consumer = runtime.stop_consumer

__all__ = ["bp", "_channels", "_channels_lock", "_start_consumer", "_stop_consumer", "set_notification_store"]
