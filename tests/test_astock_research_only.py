"""Research-only boundary tests for P0-B1 product-scope enforcement.

Verifies:
- AC-1: /trading /paper /qmt /portfolio /risk → 302 /dashboard (default)
- AC-2: /api/v1/trade/xxx /api/v1/paper/xxx /api/v1/qmt/xxx /api/v1/portfolio/xxx → 410 (default)
- AC-3: /api/v1/market/quote works in research-only mode
- AC-4: ASTOCK_RESEARCH_ONLY=false preserves legacy behavior
- AC-5: Dashboard overview doesn't return paper fields in research-only mode
- AC-6: Legacy test fixture compatibility (other test files pass)
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest

# ── Research-only default app ──────────────────────────────────────


@pytest.fixture
def research_app():
    from tradingagents.astock.api import create_app
    app = create_app(db_path=":memory:", cors_origin="*")
    app.config["TESTING"] = True
    return app


@pytest.fixture
def research_client(research_app):
    return research_app.test_client()


# ── Compat mode app (ASTOCK_RESEARCH_ONLY=false) ───────────────────


@pytest.fixture
def compat_app():
    from tradingagents.astock.api import create_app
    app = create_app(db_path=":memory:", cors_origin="*",
                     test_config={"ASTOCK_RESEARCH_ONLY": False})
    app.config["TESTING"] = True
    return app


@pytest.fixture
def compat_client(compat_app):
    return compat_app.test_client()


# ===================================================================
# AC-1: Page redirects (research-only → 302 /dashboard)
# ===================================================================

EXECUTION_PAGES = ["/trading", "/paper", "/qmt", "/portfolio", "/risk"]


class TestResearchOnlyPageRedirects:
    """AC-1: Given default config, when requesting execution pages, all 302."""

    @pytest.mark.parametrize("path", EXECUTION_PAGES)
    def test_execution_page_redirects(self, research_client, path):
        resp = research_client.get(path)
        assert resp.status_code == 302, f"{path} should redirect, got {resp.status_code}"
        assert "/dashboard" in resp.headers.get("Location", ""), (
            f"{path} should redirect to /dashboard, got {resp.headers.get('Location')}"
        )

    def test_non_execution_pages_still_render(self, research_client):
        """Research pages and core tools keep working."""
        for path in ["/dashboard", "/research", "/strategy_hub", "/screener",
                     "/watchlist", "/data_health", "/market_leaders", "/kc_chart", "/reports"]:
            resp = research_client.get(path)
            assert resp.status_code == 200, f"{path} returned {resp.status_code}"


# ===================================================================
# AC-2: API 410 responses (research-only)
# ===================================================================

EXECUTION_API_PREFIXES = [
    "/api/v1/trade/order", "/api/v1/trade/quote", "/api/v1/trade/state",
    "/api/v1/paper/cycle", "/api/v1/paper/state", "/api/v1/paper/trades",
    "/api/v1/qmt/health", "/api/v1/qmt/positions", "/api/v1/qmt/orders",
    "/api/v1/portfolio/risk", "/api/v1/portfolio/attribution",
]


class TestResearchOnlyApiGuard:
    """AC-2: Given default config, execution API endpoints return 410."""

    @pytest.mark.parametrize("path", EXECUTION_API_PREFIXES)
    def test_execution_api_returns_410(self, research_app, path):
        with research_app.test_client() as client:
            resp = client.get(path)
            assert resp.status_code == 410, f"{path} should 410, got {resp.status_code}"
            body = resp.get_json()
            assert body is not None
            assert body.get("error") == "research_only"

    def test_non_execution_api_still_works(self, research_app):
        with research_app.test_client() as client:
            resp = client.get("/api/v1/health")
            assert resp.status_code == 200
            resp = client.get("/api/v1/kline?symbol=600519.SH")
            # May error if no data in in-memory store; that's fine — just shouldn't 410
            assert resp.status_code != 410


# ===================================================================
# AC-3: /api/v1/market/quote works in research-only mode
# ===================================================================

class TestResearchOnlyMarketQuote:
    """AC-3: Given default config, market quote endpoint returns data."""

    def test_market_quote_exists(self, research_client):
        resp = research_client.get("/api/v1/market/quote?symbol=600519.SH")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body is not None
        assert body["ok"] is True
        data = body["data"]
        assert "last_price" in data or "symbol" in data

    def test_research_html_uses_market_quote_not_legacy_trade_quote(self, research_client):
        """Research UI must migrate before the old /trade prefix is disabled."""
        html = research_client.get("/research").get_data(as_text=True)
        assert "/api/v1/market/quote" in html
        assert "/api/v1/trade/quote" not in html


# ===================================================================
# AC-4: Compat mode preserves legacy behavior
# ===================================================================

class TestCompatMode:
    """AC-4: Given explicit ASTOCK_RESEARCH_ONLY=false, legacy paths work."""

    def test_environment_variable_can_explicitly_disable_research_only(self, monkeypatch):
        """Local compatibility mode must not require a test-only config injection."""
        monkeypatch.setenv("ASTOCK_RESEARCH_ONLY", "false")
        from tradingagents.astock.api import create_app

        app = create_app(db_path=":memory:", cors_origin="*")
        assert app.config["ASTOCK_RESEARCH_ONLY"] is False
        assert app.test_client().get("/trading").status_code == 200

    def test_compat_execution_page_renders(self, compat_client):
        resp = compat_client.get("/trading")
        assert resp.status_code == 200, f"compat /trading should 200, got {resp.status_code}"

    def test_compat_api_still_works(self, compat_app):
        with compat_app.test_client() as client:
            resp = client.get("/api/v1/trade/state")
            assert resp.status_code != 410


# ===================================================================
# AC-5: Dashboard overview doesn't return paper fields (research-only)
# ===================================================================

class TestResearchOnlyDashboard:
    """AC-5: Dashboard API doesn't return execution data in research-only mode."""

    def test_dashboard_has_no_paper_fields(self, research_app):
        with research_app.test_client() as client:
            store = research_app.config["STORE"]
            store.init_schema()
            resp = client.get("/api/v1/dashboard/overview")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body is not None
        assert body["ok"] is True
        data = body["data"]
        # Core research fields should remain
        assert "statistics" in data
        assert "symbols_tracked" in data["statistics"]
        assert "backtests_total" in data["statistics"]
        # Paper/execution fields must NOT be present
        assert "paper_positions" not in data, "paper_positions must not appear in research-only mode"
        assert "recent_trades" not in data, "recent_trades must not appear in research-only mode"
        assert "paper_equity_curve" not in data, "paper_equity_curve must not appear"
        assert "latest_equity_curve" in data  # backtest equity curve is research data

    def test_rendered_dashboard_has_no_execution_links_or_paper_scripts(self, research_client):
        """FR-4 removes execution navigation and Dashboard paper DOM/scripts, not CSS-hides them."""
        html = research_client.get("/dashboard").get_data(as_text=True)
        for path in ("/trading", "/paper", "/qmt", "/portfolio", "/risk"):
            assert f'href="{path}"' not in html
            assert f'data-url="{path}"' not in html
        for token in (
            "m-nav",
            "m-positions",
            "paper_equity_curve",
            "recent_trades",
            "renderEquityCurve",
            "renderRecentTrades",
            "交易 Trading",
        ):
            assert token not in html
