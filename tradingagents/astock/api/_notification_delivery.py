"""Notification delivery helpers shared by the notification routes/runtime."""

from __future__ import annotations

import json
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import requests as http_requests

logger = logging.getLogger(__name__)


def dispatch_event(channel: dict[str, Any], event: dict[str, Any]) -> None:
    """Send an event to a configured notification channel."""
    url = channel.get("url", "")
    kind = channel.get("kind", "generic")

    if kind == "dingtalk":
        payload = build_dingtalk_payload(event)
        http_requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
    elif kind == "feishu":
        payload = build_feishu_payload(event)
        http_requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
    elif kind == "work_weixin":
        payload = build_work_weixin_payload(event)
        http_requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
    elif kind == "email":
        send_email(channel, event)
    elif kind == "desktop":
        send_desktop(channel, event)
    else:
        http_requests.post(url, json=event, headers={"Content-Type": "application/json"}, timeout=10)


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
    evt_type = event.get("type", "unknown")
    ts = event.get("timestamp", "")
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
            <td style="padding: 6px 10px; border: 1px solid #ddd;">{evt_type}</td></tr>
        <tr><td style="padding: 6px 10px; border: 1px solid #ddd; font-weight: bold;">Time</td>
            <td style="padding: 6px 10px; border: 1px solid #ddd;">{ts}</td></tr>
    """
    if evt_type == "cycle_complete":
        html += f"""
        <tr><td style="padding: 6px 10px; border: 1px solid #ddd; font-weight: bold;">Cycle</td>
            <td style="padding: 6px 10px; border: 1px solid #ddd;">{event.get('cycle', '?')}</td></tr>
        <tr><td style="padding: 6px 10px; border: 1px solid #ddd; font-weight: bold;">Trades</td>
            <td style="padding: 6px 10px; border: 1px solid #ddd;">{event.get('trade_count', 0)}</td></tr>
        <tr><td style="padding: 6px 10px; border: 1px solid #ddd; font-weight: bold;">Total Value</td>
            <td style="padding: 6px 10px; border: 1px solid #ddd;">{event.get('total_value', 0):.2f}</td></tr>
        """
    if evt_type == "error":
        html += f"""
        <tr><td style="padding: 6px 10px; border: 1px solid #ddd; font-weight: bold;">Message</td>
            <td style="padding: 6px 10px; border: 1px solid #ddd;">{event.get('message', 'N/A')}</td></tr>
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

    subprocess.run(
        ["osascript", "-e", f'display notification "{body}" with title "{title}"'],
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
