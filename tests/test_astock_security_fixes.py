"""Regression coverage for API security and dashboard correctness fixes."""

from __future__ import annotations

import hashlib
from unittest.mock import patch


def _app(*, require_auth: bool):
    from tradingagents.astock.api import create_app

    app = create_app(
        db_path=":memory:",
        cors_origin="*",
        test_config={"ASTOCK_REQUIRE_AUTH": require_auth, "ASTOCK_SCHEDULER_ENABLED": False},
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
            dispatcher = response.get_json()["dispatcher"]
            assert "smtp_pass" not in dispatcher
            assert dispatcher["url"] == "https://8.8.8.8/hook"

            listing = client.get("/api/v1/notifications/dispatchers").get_json()
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
