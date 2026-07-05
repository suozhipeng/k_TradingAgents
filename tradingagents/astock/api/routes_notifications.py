"""Notification / push settings API — Web-P2 (FR-14 enhanced).

Provides:
- POST /notifications/test-webhook  -> test a webhook URL
- POST /notifications/dingtalk      -> send DingTalk webhook notification
- POST /notifications/email         -> send email notification
- POST /notifications/desktop       -> send desktop notification (macOS/Linux/Windows)
- GET  /notifications/dispatchers   -> list configured notification channels
- POST /notifications/dispatchers   -> register a notification channel
- PUT  /notifications/dispatchers/<name> -> update a notification channel
- DELETE /notifications/dispatchers/<name> -> delete a notification channel
- GET  /notifications/events        -> poll notification events from EventBus
- POST /notifications/consumer/start -> start the consumer thread
- POST /notifications/consumer/stop  -> stop the consumer thread

Channels are persisted to the DuckDB ``notification_channels`` table
and loaded on app startup. The consumer thread bridges EventBus -> channels.
"""

from __future__ import annotations

import json
import logging
import smtplib
import ssl
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any

import requests as http_requests
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

bp = Blueprint("notifications", __name__)

# ---------------------------------------------------------------------------
# In-memory channel store (synced to DB on CRUD)
# ---------------------------------------------------------------------------

_channels: dict[str, dict[str, Any]] = {}
_channels_lock = threading.Lock()

# ---------------------------------------------------------------------------
# EventBus consumer thread — bridges EventBus -> notification channels
# ---------------------------------------------------------------------------

_consumer_stop = threading.Event()
_consumer_thread: threading.Thread | None = None
_store: Any = None  # AStockStore (set by create_app)


def set_notification_store(store: Any) -> None:
    """Inject the AStockStore for persistence. Called from create_app."""
    global _store
    _store = store
    if store is not None:
        _load_channels_from_db()


def _load_channels_from_db() -> None:
    """Load persisted channels from DuckDB on startup."""
    if _store is None:
        return
    try:
        df = _store.conn.execute(
            'SELECT name, kind, url, enabled, config_json FROM notification_channels WHERE enabled = TRUE'
        ).fetchdf()
        for _, row in df.iterrows():
            name = str(row["name"])
            cfg = {}
            cj = row.get("config_json")
            if isinstance(cj, str) and cj.strip():
                try:
                    cfg = json.loads(cj)
                except (json.JSONDecodeError, TypeError):
                    cfg = {}
            _channels[name] = {
                "name": name,
                "kind": str(row.get("kind", "generic")),
                "url": str(row.get("url", "")),
                "enabled": bool(row.get("enabled", True)),
                **cfg,
            }
        logger.info("Loaded %d notification channels from DB", len(_channels))
    except Exception as exc:
        logger.warning("Failed to load notification channels from DB: %s", exc)


def _persist_channel(channel: dict[str, Any]) -> None:
    """Persist a single channel to DuckDB."""
    if _store is None:
        return
    try:
        name = channel["name"]
        kind = channel.get("kind", "generic")
        url = channel.get("url", "")
        enabled = channel.get("enabled", True)
        config_json = json.dumps({k: v for k, v in channel.items() if k not in ("name", "kind", "url", "enabled")}, ensure_ascii=False)

        _store.conn.execute(
            """INSERT INTO notification_channels (name, kind, url, enabled, config_json, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET
                   kind=excluded.kind, url=excluded.url, enabled=excluded.enabled,
                   config_json=excluded.config_json, updated_at=excluded.updated_at""",
            [name, kind, url, enabled, config_json, datetime.utcnow().isoformat()],
        )
    except Exception as exc:
        logger.warning("Failed to persist channel %s: %s", channel.get("name"), exc)


def _delete_channel_from_db(name: str) -> None:
    if _store is None:
        return
    try:
        _store.conn.execute("DELETE FROM notification_channels WHERE name = ?", [name])
    except Exception as exc:
        logger.warning("Failed to delete channel %s from DB: %s", name, exc)


# ---------------------------------------------------------------------------
# Consumer thread
# ---------------------------------------------------------------------------


def _notification_consumer() -> None:
    """Background thread that polls EventBus and dispatches to channels."""
    from tradingagents.astock.execution.event_bus import EventBus

    while not _consumer_stop.is_set():
        try:
            event = EventBus.poll()
            if event is None:
                _consumer_stop.wait(timeout=1.0)
                continue

            evt_type = event.get("type", "")
            if evt_type not in ("error", "cycle_error", "cycle_start", "cycle_complete", "task_failed"):
                continue

            with _channels_lock:
                channels = [ch for ch in _channels.values() if ch.get("enabled", True)]

            for ch in channels:
                try:
                    _dispatch_event(ch, event)
                except Exception as exc:
                    logger.warning("Notification dispatch failed for %s: %s", ch["name"], exc)
        except Exception:
            _consumer_stop.wait(timeout=1.0)


def _start_consumer() -> None:
    global _consumer_thread
    if _consumer_thread is not None and _consumer_thread.is_alive():
        return
    _consumer_stop.clear()
    _consumer_thread = threading.Thread(target=_notification_consumer, daemon=True, name="notify-consumer")
    _consumer_thread.start()


def _stop_consumer() -> None:
    global _consumer_thread
    _consumer_stop.set()
    t = _consumer_thread
    if t is not None:
        t.join(timeout=3)
        _consumer_thread = None


# ---------------------------------------------------------------------------
# Dispatchers
# ---------------------------------------------------------------------------


def _dispatch_event(channel: dict[str, Any], event: dict[str, Any]) -> None:
    """Send an event to a notification channel."""
    url = channel.get("url", "")
    kind = channel.get("kind", "generic")

    if kind == "dingtalk":
        payload = _build_dingtalk_payload(event)
        http_requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
    elif kind == "feishu":
        payload = _build_feishu_payload(event)
        http_requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
    elif kind == "work_weixin":
        payload = _build_work_weixin_payload(event)
        http_requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
    elif kind == "email":
        _send_email(channel, event)
    elif kind == "desktop":
        _send_desktop(channel, event)
    else:
        # Generic webhook
        http_requests.post(url, json=event, headers={"Content-Type": "application/json"}, timeout=10)


def _send_email(channel: dict[str, Any], event: dict[str, Any]) -> None:
    """Send an email notification using SMTP."""
    smtp_host = channel.get("smtp_host", "smtp.gmail.com")
    smtp_port = channel.get("smtp_port", 587)
    smtp_user = channel.get("smtp_user", "")
    smtp_pass = channel.get("smtp_pass", "")
    to_addrs = channel.get("to_addresses", [])
    from_addr = channel.get("from_address", smtp_user)

    if not to_addrs:
        to_addrs = [channel.get("to_address", "")]
    to_addrs = [a.strip() for a in to_addrs if a.strip()] if isinstance(to_addrs, list) else [a.strip() for a in str(to_addrs).split(",") if a.strip()]
    if not to_addrs:
        logger.warning("No email recipients configured for channel %s", channel.get("name"))
        return

    subject = _build_email_subject(event)
    body = _build_email_body(event)

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


def _build_email_subject(event: dict[str, Any]) -> str:
    evt_type = event.get("type", "notification")
    if evt_type == "error":
        return f"[AStock Pro] Error: {event.get('message', 'System error')}"
    elif evt_type == "cycle_complete":
        cycle = event.get("cycle", "?")
        trades = event.get("trade_count", 0)
        return f"[AStock Pro] Cycle {cycle} completed — {trades} trades"
    elif evt_type == "cycle_start":
        return f"[AStock Pro] Cycle {event.get('cycle', '?')} started"
    elif evt_type == "task_failed":
        return f"[AStock Pro] Task failed: {event.get('message', 'Unknown')}"
    return f"[AStock Pro] System notification: {evt_type}"


def _build_email_body(event: dict[str, Any]) -> str:
    evt_type = event.get("type", "unknown")
    ts = event.get("timestamp", "")
    html = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
      <h2 style="color: {'#dc2626' if evt_type == 'error' else '#16a34a'};">
        {'\U0001F6A8 System Error' if evt_type == 'error' else
          '\u2705 Cycle Complete' if evt_type == 'cycle_complete' else
          '\U0001F504 Cycle Started' if evt_type == 'cycle_start' else
          '\U0001F4EC Notification'}
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


def _send_desktop(channel: dict[str, Any], event: dict[str, Any]) -> None:
    """Send a native desktop notification via platform tools."""
    title = event.get("title", "AStock Pro")
    body = _build_desktop_body(event)
    urgency = channel.get("urgency", "normal")  # low, normal, critical

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
        # Fallback: use platform-native commands
        import platform
        system = platform.system()
        if system == "Darwin":
            _send_desktop_macos(title, body)
        elif system == "Linux":
            _send_desktop_linux(title, body)
        else:
            logger.info("Desktop notification (Windows): %s - %s", title, body)
    except Exception as exc:
        logger.warning("Desktop notification failed: %s", exc)


def _send_desktop_macos(title: str, body: str) -> None:
    import subprocess
    subprocess.run(
        ["osascript", "-e", f'display notification "{body}" with title "{title}"'],
        capture_output=True,
        timeout=5,
    )


def _send_desktop_linux(title: str, body: str) -> None:
    import subprocess
    subprocess.run(["notify-send", title, body], capture_output=True, timeout=5)


def _build_desktop_body(event: dict[str, Any]) -> str:
    evt_type = event.get("type", "notification")
    if evt_type == "error":
        return event.get("message", "System error occurred")
    elif evt_type == "cycle_complete":
        cycle = event.get("cycle", "?")
        trades = event.get("trade_count", 0)
        total = event.get("total_value", 0)
        return f"Cycle {cycle}: {trades} trades, Total: {total:.2f}"
    elif evt_type == "cycle_start":
        return f"Cycle {event.get('cycle', '?')} started"
    elif evt_type == "task_failed":
        return event.get("message", "Task failed")
    return json.dumps(event, ensure_ascii=False)


def _build_dingtalk_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Build DingTalk Markdown webhook payload."""
    msg_type = event.get("type", "unknown")
    ts = event.get("timestamp", "")

    if msg_type == "error":
        title = "\U0001F6A8 System Error"
        content = f"**Event**: {msg_type}\n**Details**: {event.get('message', 'N/A')}\n**Time**: {ts}"
    elif msg_type == "cycle_start":
        title = "\U0001F504 Schedule Cycle Start"
        content = f"**Cycle**: {event.get('cycle', '?')}\n**Time**: {ts}"
    elif msg_type == "cycle_complete":
        trades = event.get("trade_count", 0)
        total = event.get("total_value", 0)
        title = "\u2705 Schedule Cycle Complete"
        content = f"**Cycle**: {event.get('cycle', '?')}\n**Trades**: {trades}\n**Total Value**: {total:.2f}\n**Time**: {ts}"
    else:
        title = "\U0001F4EC System Notification"
        content = f"**Type**: {msg_type}\n**Details**: {json.dumps(event, ensure_ascii=False)}\n**Time**: {ts}"

    return {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": content},
        "at": {"isAllAt": False},
    }


def _build_feishu_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Build Feishu/Lark interactive card payload."""
    msg_type = event.get("type", "unknown")
    ts = event.get("timestamp", "")

    if msg_type == "error":
        title_text = "\U0001F6A8 System Error"
        content_lines = [
            {"tag": "div", "text": {"content": f"**Details**: {event.get('message', 'N/A')}\n**Time**: {ts}", "tag": "lark_md"}},
        ]
    else:
        title_text = "\U0001F4EC Notification"
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


def _build_work_weixin_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Build WeChat Work (企业微信) bot webhook payload."""
    msg_type = event.get("type", "unknown")
    ts = event.get("timestamp", "")

    if msg_type == "error":
        title = "🚨 System Error"
        body = f"**{title}**\n> Details: {event.get('message', 'N/A')}\n> Time: {ts}"
    elif msg_type == "cycle_start":
        body = f"**🔄 Schedule Cycle Start**\n> Cycle: {event.get('cycle', '?')}\n> Time: {ts}"
    elif msg_type == "cycle_complete":
        trades = event.get("trade_count", 0)
        total = event.get("total_value", 0)
        body = f"**✅ Schedule Cycle Complete**\n> Cycle: {event.get('cycle', '?')}\n> Trades: {trades}\n> Total Value: {total:.2f}\n> Time: {ts}"
    elif msg_type == "task_failed":
        body = f"**❌ Task Failed**\n> Message: {event.get('message', 'Unknown')}\n> Time: {ts}"
    else:
        body = f"**📬 System Notification**\n> Type: {msg_type}\n> Details: {json.dumps(event, ensure_ascii=False)}\n> Time: {ts}"

    return {
        "msgtype": "markdown",
        "markdown": {"content": body},
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


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
        "timestamp": __import__("datetime").datetime.now().isoformat(),
    }

    try:
        resp = http_requests.post(url, json=payload, headers={"User-Agent": "AStockPro/1.0"}, timeout=10)
        if resp.ok:
            logger.info("Webhook test OK: %s -> %s", url, resp.status_code)
            return jsonify({"status": "ok", "http_status": resp.status_code}), 200
        else:
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
        else:
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
    event = {"type": "test", "title": title, "message": message, "timestamp": __import__("datetime").datetime.now().isoformat()}
    try:
        _send_desktop(channel, event)
        return jsonify({"status": "ok"}), 200
    except Exception as exc:
        logger.warning("Desktop notification failed: %s", exc)
        return jsonify({"status": "error", "error": str(exc)[:200]}), 502


@bp.route("/notifications/dispatchers")
def list_dispatchers() -> tuple[Any, int]:
    """List configured notification channels."""
    with _channels_lock:
        channels = list(_channels.values())
    return jsonify({
        "dispatchers": channels,
        "consumer_running": _consumer_thread is not None and _consumer_thread.is_alive(),
    }), 200


@bp.route("/notifications/dispatchers", methods=["POST"])
def register_dispatcher() -> tuple[Any, int]:
    """Register a notification channel."""
    data = request.get_json(silent=True) or {}
    name = data.get("name") or ""
    kind = data.get("kind", "generic")
    url = data.get("url", "")

    if not name:
        return jsonify({"error": "name is required", "status": 400}), 400

    channel = {"name": name, "kind": kind, "url": url, "enabled": True, **{k: v for k, v in data.items() if k not in ("name", "kind", "url")}}

    with _channels_lock:
        _channels[name] = channel

    _persist_channel(channel)
    _start_consumer()
    logger.info("Registered notification dispatcher: %s (kind=%s)", name, kind)

    return jsonify({"status": "ok", "dispatcher": channel}), 201


@bp.route("/notifications/dispatchers/<name>", methods=["PUT"])
def update_dispatcher(name: str) -> tuple[Any, int]:
    """Update a notification channel."""
    data = request.get_json(silent=True) or {}

    with _channels_lock:
        existing = _channels.get(name)
        if existing is None:
            return jsonify({"error": f"Dispatcher not found: {name}", "status": 404}), 404
        for key, val in data.items():
            existing[key] = val

    channel = dict(_channels[name])
    _persist_channel(channel)
    logger.info("Updated notification dispatcher: %s", name)
    return jsonify({"status": "ok", "dispatcher": channel}), 200


@bp.route("/notifications/dispatchers/<name>", methods=["DELETE"])
def delete_dispatcher(name: str) -> tuple[Any, int]:
    """Delete a notification channel by name."""
    with _channels_lock:
        _channels.pop(name, None)

    _delete_channel_from_db(name)
    logger.info("Deleted notification dispatcher: %s", name)
    return jsonify({"status": "ok"}), 200


@bp.route("/notifications/events")
def list_notification_events() -> tuple[Any, int]:
    """Return recent events from the EventBus ring buffer (filtered by type)."""
    from tradingagents.astock.execution.event_bus import EventBus

    events = EventBus.peek_all()
    filtered = [e for e in events if e.get("type") in ("error", "cycle_start", "cycle_complete", "cycle_error", "task_failed")]
    return jsonify({"events": filtered[-50:]}), 200


@bp.route("/notifications/consumer/start", methods=["POST"])
def start_consumer() -> tuple[Any, int]:
    """Start the notification consumer thread."""
    _start_consumer()
    return jsonify({"status": "ok", "running": True}), 200


@bp.route("/notifications/consumer/stop", methods=["POST"])
def stop_consumer_route() -> tuple[Any, int]:
    """Stop the notification consumer thread."""
    _stop_consumer()
    return jsonify({"status": "ok", "running": False}), 200


__all__ = ["bp", "_channels", "_start_consumer", "_stop_consumer", "set_notification_store"]
