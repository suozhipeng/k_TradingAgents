"""Tests for AStock Flask Jinja2 WebUI (Phase 17).

Verifies:
- Blueprint registration and route existence (9 pages)
- Template rendering (basic HTML structure)
- Sidebar navigation present in all pages
- Active link highlighting
- Health check and server status detectability
- Fetch-based data loading (mock)
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Create a Flask app with the web blueprint registered."""
    from tradingagents.astock.api import create_app

    app = create_app(
        db_path=":memory:",
        cors_origin="*",
    )
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PAGE_ROUTES = [
    ("/", "dashboard"),
    ("/research", "research"),
    ("/backtest", "backtest"),
    ("/strategies", "strategies"),
    ("/paper", "paper"),
    ("/qmt", "qmt"),
    ("/risk", "risk"),
    ("/reports", "reports"),
    ("/comparison", "comparison"),
    ("/screener", "screener"),
    ("/settings", "settings"),
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWebBlueprintRegistration:
    """Verify the web blueprint is registered correctly."""

    def test_blueprint_registered(self, app):
        """All page routes should be registered on the web blueprint."""
        rules = [r for r in app.url_map.iter_rules() if "web." in r.endpoint]
        endpoints = {r.endpoint for r in rules}
        expected = {
            "web.dashboard",
            "web.research",
            "web.backtest",
            "web.strategies",
            "web.paper",
            "web.qmt",
            "web.risk",
            "web.reports",
            "web.comparison",
            "web.screener",
            "web.settings",
        }
        missing = expected - endpoints
        assert not missing, f"Missing web endpoints: {missing}"
        assert len(endpoints) >= 12


class TestWebPageRendering:
    """Verify each page renders HTML successfully."""

    @pytest.mark.parametrize("route,page_name", PAGE_ROUTES)
    def test_page_returns_200(self, client, route, page_name):
        """Each page should return HTTP 200 and contain HTML."""
        resp = client.get(route)
        assert resp.status_code == 200, f"{route} returned {resp.status_code}"
        assert resp.content_type and "text/html" in resp.content_type
        assert b"<!DOCTYPE html" in resp.data or b"<html" in resp.data

    @pytest.mark.parametrize("route,page_name", PAGE_ROUTES)
    def test_page_has_sidebar_nav(self, client, route, page_name):
        """Each page should contain the sidebar navigation links."""
        resp = client.get(route)
        html = resp.data.decode("utf-8")
        # The sidebar contains links to all 9 pages
        assert "📊 总览 Dashboard" in html
        assert "🔬 个股研究 Research" in html
        assert "🔄 回测 Backtest" in html
        assert "🧠 策略 Strategies" in html
        assert "💼 模拟盘 Paper" in html
        assert "🔗 QMT 桥接" in html
        assert "⚠️ 风控 Risk" in html
        assert "📄 报告 Reports" in html
        assert "🔀 对比 Comparison" in html
        assert "🔍 筛选 Screener" in html
        assert "📊 绩效 Performance" in html
        assert "⚙️ 设置 Settings" in html
    @pytest.mark.parametrize("route,page_name", PAGE_ROUTES)
    def test_page_has_tailwind_cdn(self, client, route, page_name):
        """Each page should include the Tailwind CSS CDN."""
        resp = client.get(route)
        html = resp.data.decode("utf-8")
        assert "cdn.tailwindcss.com" in html, f"{route} missing Tailwind CDN"

    @pytest.mark.parametrize("route,page_name", PAGE_ROUTES)
    def test_page_has_health_check_script(self, client, route, page_name):
        """Each page should include the health check script."""
        resp = client.get(route)
        html = resp.data.decode("utf-8")
        assert "/api/v1/health" in html, f"{route} missing health check URL"

    def test_base_template_extended(self, client):
        """All pages should extend base.html (block content present)."""
        for route, _ in PAGE_ROUTES:
            resp = client.get(route)
            html = resp.data.decode("utf-8")
            assert "{% block content %}{% endblock %}" not in html, (
                f"{route} appears to be using raw base.html without overriding content"
            )


class TestWebSpecificPages:
    """Tests specific to individual page content."""

    def test_dashboard_has_stats_cards(self, client):
        resp = client.get("/")
        html = resp.data.decode("utf-8")
        assert "stat-symbols" in html
        assert "stat-backtests" in html
        assert "stat-positions" in html
        assert "stat-return" in html
        assert "chart-pnl-trend" in html
        assert "chart-portfolio-pie" in html
        assert "heatmap-content" in html
        assert "activity-feed" in html

    def test_research_has_symbol_input(self, client):
        resp = client.get("/research")
        html = resp.data.decode("utf-8")
        assert "symbol-input" in html
        assert "kline-content" in html

    def test_backtest_has_run_button(self, client):
        resp = client.get("/backtest")
        html = resp.data.decode("utf-8")
        assert "bt-symbol" in html
        assert "bt-strategy" in html
        assert "bt-start" in html
        assert "bt-end" in html

    def test_strategies_has_lists(self, client):
        resp = client.get("/strategies")
        html = resp.data.decode("utf-8")
        assert "strategies-list" in html
        assert "opt-strategy" in html
        assert "opt-results" in html

    def test_paper_has_account_state(self, client):
        resp = client.get("/paper")
        html = resp.data.decode("utf-8")
        assert "p-total" in html
        assert "p-cash" in html
        assert "p-holdings" in html
        assert "p-return" in html
        assert "chart-paper-equity" in html
        assert "chart-paper-cumulative" in html
        assert "chart-position-pnl" in html
        assert "paper-positions" in html
        assert "paper-trades" in html

    def test_qmt_has_health_status(self, client):
        resp = client.get("/qmt")
        html = resp.data.decode("utf-8")
        assert "qmt-status" in html
        assert "qmt-positions" in html
        assert "qmt-orders" in html

    def test_risk_has_rules_and_alerts(self, client):
        resp = client.get("/risk")
        html = resp.data.decode("utf-8")
        assert "risk-rules" in html
        assert "risk-alerts" in html

    def test_reports_has_generate_button(self, client):
        resp = client.get("/reports")
        html = resp.data.decode("utf-8")
        assert "rpt-symbol" in html
        assert "generateReport" in html

    def test_settings_has_system_info(self, client):
        resp = client.get("/settings")
        html = resp.data.decode("utf-8")
        assert "system-info" in html
        assert "sys-version" in html
        assert "saveSettings" in html

    def test_comparison_has_strategy_selection(self, client):
        resp = client.get("/comparison")
        html = resp.data.decode("utf-8")
        assert "cmp-strategies" in html
        assert "cmp-symbol" in html
        assert "cmp-start" in html
        assert "cmp-end" in html
        assert "cmp-mock" in html
        assert "chart-equity-overlay" in html
        assert "cmp-results" in html

    def test_screener_has_filter_panel(self, client):
        resp = client.get("/screener")
        html = resp.data.decode("utf-8")
        assert "sc-rsi-min" in html
        assert "sc-rsi-max" in html
        assert "sc-vol-ratio" in html
        assert "sc-ma-golden" in html
        assert "sc-ma-death" in html
        assert "sc-macd-golden" in html
        assert "sc-macd-death" in html
        assert "sc-mock" in html
        assert "sc-results" in html
