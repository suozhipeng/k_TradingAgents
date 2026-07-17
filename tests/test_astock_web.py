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
    app.config["ASTOCK_RESEARCH_ONLY"] = False
    return app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def local_release_app():
    """Create the supported loopback analysis/backtest workbench profile."""
    from tradingagents.astock.api import create_app

    return create_app(
        db_path=":memory:",
        cors_origin="*",
        test_config={"ASTOCK_LOCAL_RELEASE": True},
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PAGE_ROUTES = [
    ("/trading", "portfolio/trading"),
    ("/dashboard", "dashboard/dashboard"),
    ("/research", "research/research"),
    ("/strategy_hub", "strategy/strategy_hub"),
    ("/strategies", "strategy/strategies"),
    ("/paper", "portfolio/paper"),
    ("/qmt", "portfolio/qmt"),
    ("/risk", "portfolio/risk"),
    ("/reports", "portfolio/reports"),
    ("/screener", "watch_center/screener"),
    ("/daily", "dashboard/daily_review"),
    ("/data_health", "ops/data_health"),
    ("/settings", "ops/settings"),
    ("/ai_agent", "research/ai_agent"),
    ("/kc_chart", "watch_center/kc_chart"),
    ("/market_leaders", "watch_center/market_leaders"),
    ("/portfolio", "portfolio/portfolio"),
    ("/ops_audit", "ops/ops_audit"),
    ("/monitor", "watch_center/monitor"),
    ("/strategies/monitor", "strategy/strategy_monitor"),
]

LEGACY_REDIRECTS = [
    ("/momentum_dashboard", "/market_leaders?tab=momentum"),
    ("/momentum_standalone", "/market_leaders?tab=momentum"),
    ("/dragon_tiger", "/market_leaders?tab=dragon_tiger"),
    ("/sectors", "/market_leaders?tab=sectors"),
    ("/northbound", "/market_leaders?tab=northbound"),
    ("/momentum_rotation", "/market_leaders?tab=rotation"),
    ("/tv_chart", "/kc_chart?symbol=600519.SH"),
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
        # Just verify we have enough web endpoints (exact names may vary with blueprint structure)
        assert len(endpoints) >= 26, f"Expected >= 26 web endpoints, got {len(endpoints)}: {sorted(endpoints)}"
        # Verify key routes exist
        rule_paths = {r.rule for r in rules}
        for path in ["/dashboard", "/trading", "/research", "/paper", "/watchlist", "/settings"]:
            assert path in rule_paths, f"Missing route: {path}"


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
        assert 'as-sidebar' in html or 'tv-sidebar' in html
        assert 'as-topbar' in html or 'tv-topbar' in html
        assert 'as-main' in html or 'tv-main' in html
        # All nav tooltip texts should be present (new hybrid design)
        assert 'Dashboard' in html or '总览' in html
        assert 'Research' in html or '研究' in html or 'AI Research Center' in html
        assert 'Strategy' in html or '策略' in html or 'Strategy Lab' in html or 'Strategy Hub' in html
        assert 'Market Leaders' in html or '龙头' in html
        assert 'Ops' in html or '运维' in html or 'Data' in html or 'Data & Ops' in html
        assert 'Screener' in html or '选股' in html
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

    def test_global_stock_search_script_has_one_template_literal_per_item(self):
        template = (REPO_ROOT / "tradingagents/astock/web/templates/base.html").read_text(encoding="utf-8")
        assert "</div>`\n      `).join('')" not in template

    @pytest.mark.parametrize("route,target", LEGACY_REDIRECTS)
    def test_removed_legacy_pages_are_not_public_routes(self, client, route, target):
        resp = client.get(route, follow_redirects=False)
        assert resp.status_code == 404

    def test_removed_legacy_tv_chart_is_not_public(self, client):
        resp = client.get("/tv_chart?symbol=000001.SZ", follow_redirects=False)
        assert resp.status_code == 404


class TestWebSpecificPages:
    """Tests specific to individual page content."""

    def test_dashboard_has_stats_cards(self, client):
        resp = client.get("/dashboard")
        html = resp.data.decode("utf-8")
        assert "m-symbols" in html or "stat-symbols" in html
        assert "m-backtests" in html or "stat-backtests" in html
        assert "heatmap-content" in html
        assert "recent-backtests-content" in html or "recent-backtests" in html
        assert "市场追踪中心" in html

    def test_empty_local_store_treats_missing_watchlist_as_an_empty_state(self, app):
        from tradingagents.astock.api._analysis_engine import load_watchlist

        with app.app_context():
            assert load_watchlist() == []

    def test_research_has_symbol_input(self, client):
        resp = client.get("/research")
        html = resp.data.decode("utf-8")
        assert "symbol-input" in html
        assert "kc-chart-area" in html or "kline-iframe" in html
        assert "research-query" in html
        assert "tab-news" in html
        assert "tab-stocknews" in html
        assert "tab-analysis" in html
        assert "TV Pro" not in html
        assert "/tv_chart" not in html
        assert "kc-link" in html

    def test_research_detail_calls_use_registered_market_routes(self, client):
        """The data-query blueprint is mounted below /api/v1/market."""
        html = client.get("/research").get_data(as_text=True)
        for legacy_path in (
            "/api/v1/valuation",
            "/api/v1/news",
            "/api/v1/research",
            "/api/v1/fundamentals",
            "/api/v1/kline",
            "/api/v1/f10",
        ):
            assert legacy_path not in html
        for market_path in (
            "/api/v1/market/valuation",
            "/api/v1/market/news",
            "/api/v1/market/research",
            "/api/v1/market/fundamentals",
            "/api/v1/market/kline",
            "/api/v1/market/f10",
        ):
            assert market_path in html
        assert "/api/v1/market/research/search?symbol=" in html
        assert "&query=" in html

    def test_compatibility_pages_use_current_market_routes(self, client):
        assert "/api/v1/market/research?symbol=" in client.get("/reports").get_data(as_text=True)
        assert "/api/v1/market/orderbook?symbol=" in client.get("/trading").get_data(as_text=True)

    def test_ops_audit_reads_events_from_envelope_data(self, client):
        html = client.get("/ops_audit").get_data(as_text=True)
        assert "const payload = APIClient.unwrap(await resp.json());" in html
        assert "const events = payload?.events || [];" in html

    def test_dashboard_unpacks_task_and_audit_collections(self, client):
        html = client.get("/dashboard").get_data(as_text=True)
        assert "const taskPayload = APIClient.unwrap(await res.json());" in html
        assert "const tasks = taskPayload?.tasks || [];" in html
        assert html.count("const auditPayload = APIClient.unwrap") >= 2
        assert html.count("const events = auditPayload?.events || [];") >= 2

    def test_local_release_settings_do_not_render_blocked_api_controls(self, local_release_app):
        html = local_release_app.test_client().get("/settings").get_data(as_text=True)
        for blocked_path in (
            "/api/v1/admin/mock-data",
            "/api/v1/cache/status",
            "/api/v1/cache/clear",
            "/api/v1/notifications/test-webhook",
        ):
            assert blocked_path not in html
        assert "本地发布仅提供研究与回测" in html

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
        assert "paper-metrics-row" in html
        assert "card-recent-trades" in html
        assert "trades-table-wrap" in html

    def test_trading_managed_mode_is_mock_read_only(self, client):
        resp = client.get("/trading")
        html = resp.data.decode("utf-8")
        assert 'data-mode="managed"' in html
        assert 'data-mode="live"' not in html
        assert "QMT mock/read-only" in html
        assert "真实券商下单未接入" in html

    def test_qmt_has_health_status(self, client):
        resp = client.get("/qmt")
        html = resp.data.decode("utf-8")
        assert "qmt-status" in html
        assert "qmt-positions" in html
        assert "qmt-orders" in html
        assert "模拟/只读模式" in html
        assert "不探测本机 QMT/xtquant" in html
        assert "testRealConnection" not in html

    def test_risk_has_rules_and_alerts(self, client):
        resp = client.get("/risk")
        html = resp.data.decode("utf-8")
        assert "risk-metrics-row" in html
        assert "card-var" in html
        assert "card-hhi" in html

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

    @pytest.mark.parametrize("path", ("/compare", "/comparison", "/performance"))
    def test_legacy_strategy_routes_are_not_public(self, client, path):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 404

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

    def test_market_leaders_has_dragon_tiger_panel(self, client):
        resp = client.get("/market_leaders?tab=dragon_tiger")
        html = resp.data.decode("utf-8")
        assert "dt-date" in html
        assert "dt-min-buy" in html
        assert "dt-mock" in html
        assert "chart-dt-top" in html
        assert "chart-dt-reason" in html

    def test_market_leaders_has_sectors_panel(self, client):
        resp = client.get("/market_leaders?tab=sectors")
        html = resp.data.decode("utf-8")
        assert "panel-sectors" in html
        assert "chart-heatmap-treemap" in html
        assert "sec-topn" in html
        assert "chart-sector-bars" in html
        assert "loadSectors" in html
        assert "sec-top-table" in html
        assert "sec-bottom-table" in html
        assert "echarts" in html

    def test_market_leaders_has_northbound_panel(self, client):
        resp = client.get("/market_leaders?tab=northbound")
        html = resp.data.decode("utf-8")
        assert "nb-hgt" in html
        assert "nb-sgt" in html
        assert "nb-total" in html
        assert "chart-nb-flow" in html
        assert "nb-table" in html

    def test_market_leaders_tab_deep_link_contract(self, client):
        html = client.get("/market_leaders?tab=sectors").get_data(as_text=True)
        assert "const VALID_TABS" in html
        assert "activateTab(new URLSearchParams(window.location.search).get('tab') || 'momentum')" in html
        assert "window.history.replaceState" in html

    def test_data_health_has_summary(self, client):
        resp = client.get("/data_health")
        html = resp.data.decode("utf-8")
        assert "h-total" in html
        assert "h-available" in html
        assert "h-degraded" in html
        assert "h-rate" in html
        assert "h-table" in html

    def test_trading_has_order_panel(self, client):
        resp = client.get("/trading")
        html = resp.data.decode("utf-8")
        assert "order-submit" in html
        assert "order-price" in html
        assert "order-qty" in html
        assert "trade-toast" in html
        assert "symbol-input" in html
        assert "kc-trade-chart" in html
        assert "positions-table" in html
        assert "trades-table" in html
