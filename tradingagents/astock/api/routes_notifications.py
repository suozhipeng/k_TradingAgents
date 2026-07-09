"""Notification / push settings API — thin route layer."""

from __future__ import annotations

import logging
import socket
import struct
import threading
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Any

import requests as http_requests
from flask import Blueprint, jsonify, request

from ._notification_delivery import send_desktop
from ._notification_runtime import runtime

logger = logging.getLogger(__name__)
bp = Blueprint("notifications", __name__)

# ---------------------------------------------------------------------------
# SSRF protection helpers
# ---------------------------------------------------------------------------

_PRIVATE_RANGES = (
    "10.0.0.0/8",
    "100.64.0.0/10",
    "127.0.0.0/8",
    "169.254.0.0/16",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "::1/128",
    "fc00::/7",
    "fe80::/10",
)


def _is_private_or_reserved(host: str) -> bool:
    """Return True if *host* resolves to a private / reserved IP address."""
    try:
        addr = ip_address(host)
        if addr.is_private or addr.is_loopback or addr.is_link_local:
            return True
    except ValueError:
        # Could not parse as IP — it's a hostname; resolve it
        try:
            infos = socket.getaddrinfo(host, None, socket.AF_INET)
            for _, _, _, _, sockaddr in infos:
                addr = IPv4Address(sockaddr[0])
                if addr.is_private or addr.is_loopback or addr.is_link_local:
                    return True
        except socket.gaierror as e:
            logger.debug("Operation failed: {0}", e)
    return False


def _safe_http_request(url: str, **kwargs: Any) -> Any:
    """Send an HTTP request with SSRF protection.

    Blocks requests to private / loopback / link-local addresses.
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    if not parsed.scheme.startswith(("http", "https")):
        raise ValueError("Only http/https schemes are allowed")

    if _is_private_or_reserved(hostname):
        raise ValueError(f"Blocked SSRF attempt to private/reserved host: {hostname}")

    # Apply default timeout if not specified
    kwargs.setdefault("timeout", 10)
    return http_requests.request(parsed.scheme.split("+")[0], url, **kwargs)


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
        resp = _safe_http_request(url, json=payload, headers={"User-Agent": "AStockPro/1.0"})
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
        resp = _safe_http_request(url, json=payload, headers={"Content-Type": "application/json"})
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
        if _is_private_or_reserved(smtp_host):
            logger.warning("Blocked SMTP to private/reserved host: %s", smtp_host)
            return jsonify({"status": "error", "error": "SMTP host must be a public mail server"}), 400

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
