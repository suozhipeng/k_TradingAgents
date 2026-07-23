"""Regression coverage for API security and dashboard correctness fixes."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from unittest.mock import patch

import pytest

# Auth/security tests require ASTOCK_REQUIRE_AUTH=true (off by default in local-release)
pytestmark = pytest.mark.skipif(
    not os.environ.get("ASTOCK_REQUIRE_AUTH", "").lower() in ("1", "true", "yes"),
    reason="requires ASTOCK_REQUIRE_AUTH=true (local-release disables auth)",
)


def _app(*, require_auth: bool):
    from tradingagents.astock.api import create_app

    return create_app(
        db_path=":memory:",
        cors_origin="*",
        test_config={
            "ASTOCK_REQUIRE_AUTH": require_auth,
            "ASTOCK_SCHEDULER_ENABLED": False,
            "ASTOCK_MOCK_DATA_ENABLED": False,
            "ASTOCK_RESEARCH_ONLY": False,
        },
    )
    app.config["STORE"].init_schema()
    return app


def test_write_routes_require_a_writer_key() -> None:
    app = _app(require_auth=True)
    payload = {
        "symbol": "000001.SZ",
        "trade_date": "2024-01-02",
        "record": {"open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5},
    }
    with app.test_client() as client:
        assert client.post("/api/v1/data/manual/kline_bars", json=payload).status_code == 401

        readonly_key = "readonly-key"
        app.config["STORE"].add_api_key(
            key_hash=hashlib.sha256(readonly_key.encode()).hexdigest(), role="readonly"
        )
        assert client.post(
            "/api/v1/data/manual/kline_bars",
            json=payload,
            headers={"Authorization": f"Bearer {readonly_key}"},
        ).status_code == 403

        writer_key = "writer-key"
        app.config["STORE"].add_api_key(
            key_hash=hashlib.sha256(writer_key.encode()).hexdigest(), role="writer"
        )
        assert client.post(
            "/api/v1/data/manual/kline_bars",
            json=payload,
            headers={"Authorization": f"Bearer {writer_key}"},
        ).status_code == 200


def test_admin_read_routes_require_an_admin_key() -> None:
    app = _app(require_auth=True)
    with app.test_client() as client:
        assert client.get("/api/v1/admin/backend/config").status_code == 401

        admin_key = "admin-key"
        app.config["STORE"].add_api_key(
            key_hash=hashlib.sha256(admin_key.encode()).hexdigest(), role="admin"
        )
        assert client.get(
            "/api/v1/admin/backend/config",
            headers={"Authorization": f"Bearer {admin_key}"},
        ).status_code == 200


def test_global_mock_data_setting_defaults_off_and_requires_admin() -> None:
    app = _app(require_auth=True)
    with app.test_client() as client:
        assert client.get("/api/v1/health").get_json()["data"]["mock_data_enabled"] is False
        assert client.put("/api/v1/admin/mock-data", json={"enabled": True}).status_code == 401

        admin_key = "mock-admin-key"
        app.config["STORE"].add_api_key(
            key_hash=hashlib.sha256(admin_key.encode()).hexdigest(), role="admin"
        )
        manager = app.config["BACKEND_MGR"]
        previous = manager.config.mock_data_enabled
        with patch.object(manager.config, "save"):
            response = client.put(
                "/api/v1/admin/mock-data",
                json={"enabled": True},
                headers={"Authorization": f"Bearer {admin_key}"},
            )
        assert response.status_code == 200
        assert response.get_json() == {
            "ok": True,
            "data": {"enabled": True, "persistent": True},
        }
        assert client.get("/api/v1/health").get_json()["data"]["mock_data_enabled"] is True
        screener = client.get("/api/v1/market/screener")
        assert screener.status_code == 200
        assert screener.get_json()["data"]["total"] == 10
        manager.config.mock_data_enabled = previous


def test_api_5xx_responses_do_not_expose_exception_text() -> None:
    app = _app(require_auth=False)
    with patch("tradingagents.astock.api.routes_data_query.get_store", side_effect=RuntimeError("secret detail")):
        with app.test_client() as client:
            response = client.get("/api/v1/market/kline?symbol=600519.SH")
    assert response.status_code == 500
    assert response.get_json() == {
        "ok": False,
        "error": "internal_server_error",
        "message": "internal_server_error",
        "status": 500,
    }


def test_scheduler_and_data_import_require_operator_capabilities() -> None:
    app = _app(require_auth=True)
    writer_key = "writer-key-without-ops-cap"
    app.config["STORE"].add_api_key(
        key_hash=hashlib.sha256(writer_key.encode()).hexdigest(), role="writer"
    )
    headers = {"Authorization": f"Bearer {writer_key}"}
    with app.test_client() as client:
        assert client.post("/api/v1/sse/scheduler/start", headers=headers).status_code == 403
        assert client.post("/api/v1/data/jobs/import-database", json={
            "source_db_path": "data/imports/source.db", "source_table": "kline_bars",
        }, headers=headers).status_code == 403


def test_cancelled_data_job_cannot_be_overwritten_as_succeeded() -> None:
    from tradingagents.astock.store.jobs import DataJobManager

    started = threading.Event()
    release = threading.Event()
    manager = DataJobManager(max_workers=1)
    try:
        job = manager.submit(
            "test",
            lambda _update: (started.set(), release.wait(timeout=2), {"done": True})[-1],
        )
        assert started.wait(timeout=1)
        assert manager.cancel(job.job_id) is True
        release.set()
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline and manager.get(job.job_id).status != "cancelled":
            time.sleep(0.01)
        assert manager.get(job.job_id).status == "cancelled"
    finally:
        manager.shutdown()


def test_queued_data_job_cancel_is_terminal_before_worker_starts() -> None:
    """Cancellation in the submit/start window must not resurrect the job."""
    from tradingagents.astock.store.jobs import DataJobManager

    blocker_started = threading.Event()
    unblock = threading.Event()
    target_started = threading.Event()
    manager = DataJobManager(max_workers=1)
    try:
        blocker = manager.submit(
            "blocker",
            lambda _update: (blocker_started.set(), unblock.wait(timeout=2), {})[-1],
        )
        assert blocker_started.wait(timeout=1)
        target = manager.submit("target", lambda _update: (target_started.set(), {})[-1])
        assert manager.cancel(target.job_id) is True
        unblock.set()
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline and manager.get(target.job_id).status != "cancelled":
            time.sleep(0.01)
        assert manager.get(target.job_id).status == "cancelled"
        assert not target_started.is_set()
        assert manager.cancel(target.job_id) is False
    finally:
        manager.shutdown()


def test_api_boolean_parser_accepts_only_explicit_true_values() -> None:
    from tradingagents.astock.api._helpers import _as_bool

    assert _as_bool("true") is True
    assert _as_bool("1") is True
    assert _as_bool("false", True) is False
    assert _as_bool("0", True) is False


def test_dispatcher_responses_redact_credentials_and_webhook_query() -> None:
    from tradingagents.astock.api import routes_notifications

    routes_notifications._stop_consumer()
    with routes_notifications._channels_lock:
        routes_notifications._channels.clear()
    app = _app(require_auth=False)
    try:
        with app.test_client() as client:
            response = client.post(
                "/api/v1/notifications/dispatchers",
                json={
                    "name": "safe-hook",
                    "kind": "generic",
                    "url": "https://8.8.8.8/hook?token=secret-value",
                    "smtp_pass": "secret-value",
                },
            )
            assert response.status_code == 201
            dispatcher = response.get_json()["data"]["dispatcher"]
            assert "smtp_pass" not in dispatcher
            assert dispatcher["url"] == "https://8.8.8.8/hook"

            listing = client.get("/api/v1/notifications/dispatchers").get_json()["data"]
            assert "secret-value" not in str(listing)
    finally:
        routes_notifications._stop_consumer()
        with routes_notifications._channels_lock:
            routes_notifications._channels.clear()


def test_outbound_requests_reject_private_hosts_and_disable_redirects() -> None:
    from tradingagents.astock.api._notification_delivery import safe_http_request

    try:
        safe_http_request("http://127.0.0.1/hook")
    except ValueError as exc:
        assert "Blocked non-public host" in str(exc)
    else:
        raise AssertionError("private destination was not blocked")

    with patch("tradingagents.astock.api._notification_delivery.http_requests.request") as request:
        safe_http_request("https://8.8.8.8/hook")
    assert request.call_args.kwargs["allow_redirects"] is False


def test_webhook_signature_uses_canonical_json() -> None:
    from tradingagents.astock.api._notification_delivery import dispatch_event

    with patch("tradingagents.astock.api._notification_delivery.http_requests.request") as request:
        dispatch_event(
            {"kind": "generic", "url": "https://8.8.8.8/hook", "signing_secret": "secret"},
            {"b": 2, "a": 1},
        )
    kwargs = request.call_args.kwargs
    assert kwargs["headers"]["X-AStock-Signature"].startswith("sha256=")
    assert kwargs["headers"]["X-AStock-Timestamp"]
    assert kwargs["headers"]["X-AStock-Event-ID"]
    assert json.loads(kwargs["data"]) == {"a": 1, "b": 2, "timestamp": kwargs["headers"]["X-AStock-Timestamp"], "event_id": kwargs["headers"]["X-AStock-Event-ID"]}


def test_email_body_escapes_event_content() -> None:
    from tradingagents.astock.api._notification_delivery import build_email_body

    body = build_email_body({"type": "error", "message": "<script>alert(1)</script>"})
    assert "<script>" not in body
    assert "&lt;script&gt;" in body


def test_idempotency_key_replays_completed_write_response() -> None:
    app = _app(require_auth=False)
    payload = {
        "symbol": "000001.SZ", "trade_date": "2024-01-02",
        "record": {"open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5},
    }
    headers = {"Idempotency-Key": "manual-kline-retry-001"}
    with app.test_client() as client:
        first = client.post("/api/v1/data/manual/kline_bars", json=payload, headers=headers)
        second = client.post("/api/v1/data/manual/kline_bars", json=payload, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.headers["Idempotency-Replayed"] == "true"
    assert second.get_json() == first.get_json()


def test_rate_limit_is_enforced_without_limiting_health_checks() -> None:
    app = _app(require_auth=False)
    from tradingagents.astock.api.rate_limit import FixedWindowRateLimiter

    app.config["ASTOCK_RATE_LIMIT_PER_MINUTE"] = 1
    app.extensions["astock_rate_limiter"] = FixedWindowRateLimiter(1, 60)
    with app.test_client() as client:
        assert client.get("/api/v1/health/live").status_code == 200
        assert client.get("/api/v1/cache/status").status_code == 200
        limited = client.get("/api/v1/cache/status")
    assert limited.status_code == 429
    assert limited.headers["Retry-After"]


def test_macos_desktop_notification_passes_untrusted_text_as_arguments() -> None:
    from tradingagents.astock.api._notification_delivery import send_desktop_macos

    with patch("subprocess.run") as run:
        send_desktop_macos('title"; do shell script "bad"', 'body"; do shell script "bad"')
    command = run.call_args.args[0]
    assert command[0] == "osascript"
    assert command[-2:] == ['body"; do shell script "bad"', 'title"; do shell script "bad"']


def test_dashboard_research_only_hold_is_counted_once() -> None:
    from tradingagents.astock.api import routes_dashboard

    with patch.object(routes_dashboard, "load_watchlist", return_value=[{"symbol": "000001.SZ"}]), patch.object(
        routes_dashboard,
        "analyze_stock_symbol",
        return_value={"rating": "hold", "signal": "数据不足", "symbol": "000001.SZ", "name": "x"},
    ):
        summary = routes_dashboard._get_decision_summary()
    assert summary["total"] == 1
    assert summary["counts"]["hold"] == 0
    assert summary["research_only"] == 1
