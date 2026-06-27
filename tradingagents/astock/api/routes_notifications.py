"""Notification / push settings API — Web-P2.

Provides:
- POST /notifications/test-webhook  → test a webhook URL
"""

from __future__ import annotations

import logging
from typing import Any

import requests as http_requests
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

bp = Blueprint("notifications", __name__)


@bp.route("/notifications/test-webhook", methods=["POST"])
def test_webhook() -> tuple[Any, int]:
    """Test a webhook URL by sending a test payload.

    Body (JSON):
        url        — webhook URL
        message    — test message text
    """
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    message = data.get("message", "AStock Pro 通知测试")

    if not url:
        return jsonify({"error": "url is required", "status": 400}), 400

    payload = {
        "source": "astock-pro",
        "type": "test",
        "message": message,
        "timestamp": __import__("datetime").datetime.now().isoformat(),
    }

    try:
        resp = http_requests.post(
            url,
            json=payload,
            headers={"User-Agent": "AStockPro/1.0"},
            timeout=10,
        )
        if resp.ok:
            logger.info("Webhook test OK: %s → %s", url, resp.status_code)
            return jsonify({"status": "ok", "http_status": resp.status_code}), 200
        else:
            logger.warning("Webhook test failed: %s → %s", url, resp.status_code)
            return jsonify({"status": "error", "http_status": resp.status_code}), 502
    except Exception as exc:
        logger.warning("Webhook test error: %s — %s", url, exc)
        return jsonify({"status": "error", "error": str(exc)[:200]}), 502


__all__ = ["bp"]
