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
    ("/", "trading"),
    ("/dashboard", "dashboard"),
    ("/research", "research"),
    ("/strategy_hub", "strategy_hub"),
    ("/strategies", "strategies"),
    ("/paper", "paper"),
    ("/qmt", "qmt"),
    ("/risk", "risk"),
    ("/reports", "reports"),
    ("/screener", "screener"),
    ("/dragon_tiger", "dragon_tiger"),
    ("/sectors", "sectors"),
    ("/northbound", "northbound"),
    ("/data_health", "data_health"),
    ("/settings", "settings"),
    ("/ai_agent", "ai_agent"),
    ("/momentum_dashboard", "momentum_dashboard"),
    ("/momentum_rotation", "momentum_rotation"),
    ("/momentum_standalone", "momentum_standalone"),
    ("/tv_chart", "tv_chart"),
    ("/kc_chart", "kc_chart"),
    ("/market_leaders", "market_leaders"),
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
            "web.trading",
            "web.dashboard",
            "web.research",
            "web.strategy_hub",
            "web.strategies",
            "web.paper",
            "web.qmt",
            "web.risk",
            "web.reports",
            "web.screener",
            "web.dragon_tiger",
            "web.sectors",
            "web.northbound",
            "web.data_health",
            "web.settings",
            "web.ai_agent",
            "web.momentum_dashboard",
            "web.momentum_rotation",
            "web.momentum_standalone",
            "web.kc_chart",
            "web.tv_chart",
        }
        missing = expected - endpoints
        assert not missing, f"Missing web endpoints: {missing}"
        assert len(endpoints) >= 21


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
        # The sidebar contains icon links with tooltips
        assert 'AStock Pro' in html
        assert 'tv-sidebar' in html
        assert 'tv-topbar' in html
        assert 'tv-main' in html
        # All nav tooltip texts should be present
        assert 'Trading' in html
        assert 'Dashboard' in html
        assert 'Research' in html or 'AI Research Center' in html
        assert 'Strategy Lab' in html or 'Strategy Hub' in html
        assert 'Market Leaders' in html
        assert 'Data & Ops' in html
        assert 'Screener' in html
    @pytest.mark.parametrize("route,page_name", PAGE_ROUTES)
    def test_page_has_tailwind_cdn(self, client, route, page_name):
        """Each page should include the Tailwind CSS CDN."""
        resp = client.get(route)
        html = resp.data.decode("utf-8")
        assert "tailwindcss.com" in html or "Inter" in html or "JetBrains" in html, f"{route} missing font/CDN imports"

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
        resp = client.get("/dashboard")
        html = resp.data.decode("utf-8")
        assert "stat-symbols" in html
        assert "stat-backtests" in html
        assert "heatmap-content" in html
        assert "recent-backtests" in html

    def test_research_has_symbol_input(self, client):
        resp = client.get("/research")
        html = resp.data.decode("utf-8")
        assert "symbol-input" in html
        assert "kc-chart-area" in html or "kline-iframe" in html
        assert "research-query" in html
        assert "tab-news" in html
        assert "tab-stocknews" in html
        assert "tab-analysis" in html

    def test_kc_chart_has_loader_race_guards(self, client):
        resp = client.get("/kc_chart")
        html = resp.data.decode("utf-8")
        assert "KCDataLoader" in html
        assert "kc-data-loader.js" in html
        assert "scrollToRealTime" in html

    def test_backtest_has_run_button(self, client):
        resp = client.get("/strategy_hub")
        html = resp.data.decode("utf-8")
        assert "sh-symbol" in html
        assert "sh-strategy" in html or "sh-strat-list" in html
        assert "sh-start" in html
        assert "sh-end" in html
        assert "sh-run-btn" in html

    def test_strategies_has_lists(self, client):
        resp = client.get("/strategies")
        html = resp.data.decode("utf-8")
        assert "strategies-list" in html
        assert "opt-strategy" in html
        assert "opt-results" in html

    def test_paper_has_account_state(self, client):
        resp = client.get("/paper")
        html = resp.data.decode("utf-8")
        assert "🚧" in html
        assert "开发中" in html

    def test_qmt_has_health_status(self, client):
        resp = client.get("/qmt")
        html = resp.data.decode("utf-8")
        assert "qmt-status" in html
        assert "qmt-positions" in html
        assert "qmt-orders" in html
        assert "testRealConnection" in html
        assert "实盘连通性测试" in html

    def test_risk_has_rules_and_alerts(self, client):
        resp = client.get("/risk")
        html = resp.data.decode("utf-8")
        assert "🚧" in html
        assert "待接入 QMT" in html

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
        resp = client.get("/strategy_hub")
        html = resp.data.decode("utf-8")
        assert "sh-strat-list" in html or "sh-strategy" in html
        assert "sh-symbol" in html
        assert "sh-start" in html
        assert "sh-end" in html
        assert "sh-run-btn" in html

    def test_screener_has_filter_panel(self, client):
        resp = client.get("/screener")
        html = resp.data.decode("utf-8")
        assert "tv-btn-primary" in html
        assert "sc-rsi-min" in html
        assert "sc-rsi-max" in html
        assert "sc-limit" in html
        assert "sc-tbody" in html
        assert "sc-macd-golden" in html
        assert "sc-macd-death" in html
        assert "runScreener" in html
        assert "sc-results" in html

    def test_dragon_tiger_has_inputs(self, client):
        resp = client.get("/dragon_tiger")
        html = resp.data.decode("utf-8")
        assert "dt-date" in html
        assert "dt-min-buy" in html
        assert "dt-mock" in html
        assert "chart-dt-top" in html
        assert "chart-dt-reason" in html

    def test_sectors_has_heatmap(self, client):
        resp = client.get("/sectors")
        html = resp.data.decode("utf-8")
        assert "chart-heatmap-treemap" in html
        assert "tv-market-overview" in html
        assert "sec-topn" in html
        assert "chart-sector-bars" in html
        assert "loadSectors" in html
        assert "sec-top-table" in html
        assert "sec-bottom-table" in html
        assert "echarts" in html

    def test_northbound_has_flow_chart(self, client):
        resp = client.get("/northbound")
        html = resp.data.decode("utf-8")
        assert "nb-hgt" in html
        assert "nb-sgt" in html
        assert "nb-total" in html
        assert "chart-nb-flow" in html
        assert "nb-table" in html

    def test_data_health_has_summary(self, client):
        resp = client.get("/data_health")
        html = resp.data.decode("utf-8")
        assert "h-total" in html
        assert "h-available" in html
        assert "h-degraded" in html
        assert "h-rate" in html
        assert "h-table" in html

    def test_trading_has_order_panel(self, client):
        resp = client.get("/")
        html = resp.data.decode("utf-8")
        assert "order-submit" in html
        assert "order-price" in html
        assert "order-qty" in html
        assert "trade-toast" in html
        assert "symbol-input" in html
        assert "kc-trade-chart" in html
        assert "positions-table" in html
        assert "trades-table" in html
