"""Acceptance tests for the analysis-and-backtest-only local release."""

from __future__ import annotations

import pytest


@pytest.fixture
def app():
    from tradingagents.astock.api import create_app

    return create_app(
        db_path=":memory:",
        cors_origin="*",
        test_config={
            "ASTOCK_LOCAL_RELEASE": True,
            "ASTOCK_RESEARCH_ONLY": False,
            "ASTOCK_SCHEDULER_ENABLED": True,
        },
    )


def test_local_release_enforces_scope_and_disables_scheduler(app):
    assert app.config["ASTOCK_LOCAL_RELEASE"] is True
    assert app.config["ASTOCK_RESEARCH_ONLY"] is True
    assert app.config["ASTOCK_SCHEDULER_ENABLED"] is False
    assert app.config["ASTOCK_REQUIRE_AUTH"] is False
    assert app.config["ASTOCK_AUTO_REFRESH_DAILY_KLINE"] is False


def test_local_release_allows_same_origin_data_refresh_without_bearer_token(app):
    response = app.test_client().post("/api/v1/data/jobs/refresh", json={"symbols": ["600519.SH"]})
    assert response.status_code != 401


def test_local_release_serves_analysis_and_backtest_pages_only(app):
    client = app.test_client()
    assert client.get("/").status_code == 302
    for path in ("/dashboard", "/research", "/strategy_hub", "/reports", "/data_health", "/settings"):
        assert client.get(path).status_code == 200, path
    for path in ("/trading", "/paper", "/qmt", "/risk", "/portfolio", "/ops_audit"):
        assert client.get(path).status_code == 404, path
    assert "开发中" not in client.get("/settings").get_data(as_text=True)
    assert "/ops_audit" not in client.get("/settings").get_data(as_text=True)
    assert "/ops_audit" not in client.get("/dashboard").get_data(as_text=True)
    assert client.get("/not-a-workbench-route").status_code == 404
    assert client.get("/web/static/js/api-client.js").status_code == 200


@pytest.mark.parametrize("path", (
    "/api/v1/trade/state",
    "/api/v1/paper/state",
    "/api/v1/qmt/health",
    "/api/v1/portfolio/risk",
    "/api/v1/scheduler/status",
    "/api/v1/sse/scheduler/status",
    "/api/v1/sse/paper-progress",
    "/api/v1/notifications/test-webhook",
    "/api/v1/data/maintenance",
    "/api/v1/admin/mock-data",
    "/api/v1/ops/tasks",
))
def test_local_release_blocks_execution_surfaces(app, path):
    response = app.test_client().get(path)
    assert response.status_code == 410
    assert response.get_json()["error"] == "local_release_disabled"


def test_local_release_keeps_explicit_data_refresh_available(app):
    client = app.test_client()
    assert client.post("/api/v1/data/refresh/kline", json={}).status_code == 400


def test_local_release_keeps_analysis_and_backtest_api_available(app):
    client = app.test_client()
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/market/quote?symbol=600519.SH").status_code != 410
    assert client.get("/api/v1/backtest/results").status_code != 410
    assert client.post("/api/v1/ai/analyze", json={}).status_code == 400


def test_local_release_market_summary_does_not_fetch_live_data(app, monkeypatch):
    from tradingagents.astock import data_sources

    def fail_if_constructed():
        raise AssertionError("local release must not fetch providers on dashboard load")

    monkeypatch.setattr(data_sources, "AStockDataFacade", fail_if_constructed)
    response = app.test_client().get("/api/v1/market/summary?symbol=000001.SH")
    assert response.status_code == 200
    assert response.get_json()["data"]["source"] == "store"


def test_research_only_disables_scheduler_and_scheduler_routes():
    from tradingagents.astock.api import create_app

    app = create_app(
        db_path=":memory:", cors_origin="*",
        test_config={"ASTOCK_RESEARCH_ONLY": True, "ASTOCK_SCHEDULER_ENABLED": True},
    )
    assert app.config["ASTOCK_SCHEDULER_ENABLED"] is False
    assert app.test_client().post("/api/v1/sse/scheduler/start").status_code == 410
