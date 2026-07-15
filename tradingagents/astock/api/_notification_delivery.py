"""Notification delivery helpers shared by the notification routes/runtime."""

from __future__ import annotations

import json
import hmac
import hashlib
import logging
from datetime import datetime, timezone
import smtplib
import socket
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import requests as http_requests

logger = logging.getLogger(__name__)


def validate_public_host(host: str) -> None:
    """Reject hosts that resolve to loopback, private, or reserved addresses."""
    if not host:
        raise ValueError("A host is required")
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Unable to resolve host: {host}") from exc
    for _, _, _, _, sockaddr in infos:
        address = ip_address(sockaddr[0])
        if not address.is_global:
            raise ValueError(f"Blocked non-public host: {host}")


def validate_public_url(url: str) -> None:
    """Validate an HTTP(S) destination before it is stored or requested."""
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Only absolute http/https URLs are allowed")
    validate_public_host(parsed.hostname)


def safe_http_request(url: str, **kwargs: Any) -> Any:
    """Send an outbound HTTP request without following unvalidated redirects."""
    validate_public_url(url)
    kwargs.setdefault("timeout", 10)
    kwargs["allow_redirects"] = False
    return http_requests.request(urlsplit(url).scheme, url, **kwargs)


def dispatch_event(channel: dict[str, Any], event: dict[str, Any]) -> None:
    """Send an event to a configured notification channel."""
    url = channel.get("url", "")
    kind = channel.get("kind", "generic")

    if kind == "dingtalk":
        payload = build_dingtalk_payload(event)
        _post_webhook(url, payload, channel.get("signing_secret", ""))
    elif kind == "feishu":
        payload = build_feishu_payload(event)
        _post_webhook(url, payload, channel.get("signing_secret", ""))
    elif kind == "work_weixin":
        payload = build_work_weixin_payload(event)
        _post_webhook(url, payload, channel.get("signing_secret", ""))
    elif kind == "email":
        send_email(channel, event)
    elif kind == "desktop":
        send_desktop(channel, event)
    else:
        _post_webhook(url, event, channel.get("signing_secret", ""))


def _post_webhook(url: str, payload: dict[str, Any], signing_secret: str = "") -> None:
    """POST canonical JSON and optional HMAC with replay-prevention metadata."""
    payload = dict(payload)
    timestamp = str(payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat()))
    event_id = str(payload.setdefault("event_id", uuid4().hex))
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if signing_secret:
        digest = hmac.new(str(signing_secret).encode("utf-8"), body, hashlib.sha256).hexdigest()
        headers["X-AStock-Signature"] = f"sha256={digest}"
        headers["X-AStock-Timestamp"] = timestamp
        headers["X-AStock-Event-ID"] = event_id
    safe_http_request(url, data=body, headers=headers)


def send_email(channel: dict[str, Any], event: dict[str, Any]) -> None:
    """Send an email notification using SMTP."""
    smtp_host = channel.get("smtp_host", "smtp.gmail.com")
    smtp_port = channel.get("smtp_port", 587)
    smtp_user = channel.get("smtp_user", "")
    smtp_pass = channel.get("smtp_pass", "")
    to_addrs = channel.get("to_addresses", [])
    from_addr = channel.get("from_address", smtp_user)

    if not to_addrs:
        to_addrs = [channel.get("to_address", "")]
    if isinstance(to_addrs, list):
        to_addrs = [addr.strip() for addr in to_addrs if addr.strip()]
    else:
        to_addrs = [addr.strip() for addr in str(to_addrs).split(",") if addr.strip()]
    if not to_addrs:
        logger.warning("No email recipients configured for channel %s", channel.get("name"))
        return

    subject = build_email_subject(event)
    body = build_email_body(event)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    msg.attach(MIMEText(body, "html", "utf-8"))

    validate_public_host(smtp_host)
    ctx = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls(context=ctx)
        server.ehlo()
        server.login(smtp_user, smtp_pass)
        server.sendmail(from_addr, to_addrs, msg.as_string())

    logger.info("Email notification sent to %s: %s", to_addrs, subject)


def build_email_subject(event: dict[str, Any]) -> str:
    evt_type = event.get("type", "notification")
    if evt_type == "error":
        return f"[AStock Pro] Error: {event.get('message', 'System error')}"
    if evt_type == "cycle_complete":
        cycle = event.get("cycle", "?")
        trades = event.get("trade_count", 0)
        return f"[AStock Pro] Cycle {cycle} completed - {trades} trades"
    if evt_type == "cycle_start":
        return f"[AStock Pro] Cycle {event.get('cycle', '?')} started"
    if evt_type == "task_failed":
        return f"[AStock Pro] Task failed: {event.get('message', 'Unknown')}"
    return f"[AStock Pro] System notification: {evt_type}"


def build_email_body(event: dict[str, Any]) -> str:
    evt_type = str(event.get("type", "unknown"))
    ts = str(event.get("timestamp", ""))
    html = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
      <h2 style="color: {'#dc2626' if evt_type == 'error' else '#16a34a'};">
        {'System Error' if evt_type == 'error' else
          'Cycle Complete' if evt_type == 'cycle_complete' else
          'Cycle Started' if evt_type == 'cycle_start' else
          'Notification'}
      </h2>
      <table style="border-collapse: collapse; width: 100%;">
        <tr><td style="padding: 6px 10px; border: 1px solid #ddd; font-weight: bold;">Type</td>
            <td style="padding: 6px 10px; border: 1px solid #ddd;">{escape(evt_type)}</td></tr>
        <tr><td style="padding: 6px 10px; border: 1px solid #ddd; font-weight: bold;">Time</td>
            <td style="padding: 6px 10px; border: 1px solid #ddd;">{escape(ts)}</td></tr>
    """
    if evt_type == "cycle_complete":
        html += f"""
        <tr><td style="padding: 6px 10px; border: 1px solid #ddd; font-weight: bold;">Cycle</td>
            <td style="padding: 6px 10px; border: 1px solid #ddd;">{escape(str(event.get('cycle', '?')))}</td></tr>
        <tr><td style="padding: 6px 10px; border: 1px solid #ddd; font-weight: bold;">Trades</td>
            <td style="padding: 6px 10px; border: 1px solid #ddd;">{event.get('trade_count', 0)}</td></tr>
        <tr><td style="padding: 6px 10px; border: 1px solid #ddd; font-weight: bold;">Total Value</td>
            <td style="padding: 6px 10px; border: 1px solid #ddd;">{event.get('total_value', 0):.2f}</td></tr>
        """
    if evt_type == "error":
        html += f"""
        <tr><td style="padding: 6px 10px; border: 1px solid #ddd; font-weight: bold;">Message</td>
            <td style="padding: 6px 10px; border: 1px solid #ddd;">{escape(str(event.get('message', 'N/A')))}</td></tr>
        """
    html += """
      </table>
      <p style="margin-top: 16px; color: #888; font-size: 12px;">Sent by AStock Pro Trading System</p>
    </div>
    """
    return html


def send_desktop(channel: dict[str, Any], event: dict[str, Any]) -> None:
    """Send a desktop notification using plyer or native platform tools."""
    title = event.get("title", "AStock Pro")
    body = build_desktop_body(event)
    urgency = channel.get("urgency", "normal")

    try:
        from plyer import notification

        notification.notify(
            title=title,
            message=body,
            app_name="AStock Pro",
            timeout=10,
            urgency=urgency,
        )
        logger.info("Desktop notification sent: %s", title)
    except ImportError:
        import platform

        system = platform.system()
        if system == "Darwin":
            send_desktop_macos(title, body)
        elif system == "Linux":
            send_desktop_linux(title, body)
        else:
            logger.info("Desktop notification (Windows): %s - %s", title, body)
    except Exception as exc:
        logger.warning("Desktop notification failed: %s", exc)


def send_desktop_macos(title: str, body: str) -> None:
    import subprocess

    # Pass values as argv so user-controlled text cannot alter AppleScript.
    script = "on run argv\n display notification item 1 of argv with title item 2 of argv\nend run"
    subprocess.run(
        ["osascript", "-e", script, body, title],
        capture_output=True,
        timeout=5,
    )


def send_desktop_linux(title: str, body: str) -> None:
    import subprocess

    subprocess.run(["notify-send", title, body], capture_output=True, timeout=5)


def build_desktop_body(event: dict[str, Any]) -> str:
    evt_type = event.get("type", "notification")
    if evt_type == "error":
        return event.get("message", "System error occurred")
    if evt_type == "cycle_complete":
        cycle = event.get("cycle", "?")
        trades = event.get("trade_count", 0)
        total = event.get("total_value", 0)
        return f"Cycle {cycle}: {trades} trades, Total: {total:.2f}"
    if evt_type == "cycle_start":
        return f"Cycle {event.get('cycle', '?')} started"
    if evt_type == "task_failed":
        return event.get("message", "Task failed")
    return json.dumps(event, ensure_ascii=False)


def build_dingtalk_payload(event: dict[str, Any]) -> dict[str, Any]:
    msg_type = event.get("type", "unknown")
    ts = event.get("timestamp", "")

    if msg_type == "error":
        title = "System Error"
        content = f"**Event**: {msg_type}\n**Details**: {event.get('message', 'N/A')}\n**Time**: {ts}"
    elif msg_type == "cycle_start":
        title = "Schedule Cycle Start"
        content = f"**Cycle**: {event.get('cycle', '?')}\n**Time**: {ts}"
    elif msg_type == "cycle_complete":
        trades = event.get("trade_count", 0)
        total = event.get("total_value", 0)
        title = "Schedule Cycle Complete"
        content = f"**Cycle**: {event.get('cycle', '?')}\n**Trades**: {trades}\n**Total Value**: {total:.2f}\n**Time**: {ts}"
    else:
        title = "System Notification"
        content = f"**Type**: {msg_type}\n**Details**: {json.dumps(event, ensure_ascii=False)}\n**Time**: {ts}"

    return {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": content},
        "at": {"isAllAt": False},
    }


def build_feishu_payload(event: dict[str, Any]) -> dict[str, Any]:
    msg_type = event.get("type", "unknown")
    ts = event.get("timestamp", "")

    if msg_type == "error":
        title_text = "System Error"
        content_lines = [
            {"tag": "div", "text": {"content": f"**Details**: {event.get('message', 'N/A')}\n**Time**: {ts}", "tag": "lark_md"}},
        ]
    else:
        title_text = "Notification"
        content_lines = [
            {"tag": "div", "text": {"content": f"**Type**: {msg_type}\n**Time**: {ts}", "tag": "lark_md"}},
        ]

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title_text},
                "template": "red" if msg_type == "error" else "blue",
            },
            "elements": content_lines,
        },
    }


def build_work_weixin_payload(event: dict[str, Any]) -> dict[str, Any]:
    msg_type = event.get("type", "unknown")
    ts = event.get("timestamp", "")

    if msg_type == "error":
        body = f"**System Error**\n> Details: {event.get('message', 'N/A')}\n> Time: {ts}"
    elif msg_type == "cycle_start":
        body = f"**Schedule Cycle Start**\n> Cycle: {event.get('cycle', '?')}\n> Time: {ts}"
    elif msg_type == "cycle_complete":
        trades = event.get("trade_count", 0)
        total = event.get("total_value", 0)
        body = f"**Schedule Cycle Complete**\n> Cycle: {event.get('cycle', '?')}\n> Trades: {trades}\n> Total Value: {total:.2f}\n> Time: {ts}"
    elif msg_type == "task_failed":
        body = f"**Task Failed**\n> Message: {event.get('message', 'Unknown')}\n> Time: {ts}"
    else:
        body = f"**System Notification**\n> Type: {msg_type}\n> Details: {json.dumps(event, ensure_ascii=False)}\n> Time: {ts}"

    return {
        "msgtype": "markdown",
        "markdown": {"content": body},
    }
