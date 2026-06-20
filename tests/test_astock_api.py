"""Tests for the AStock Flask REST API (Phase 15).

Verifies:
- Flask app creation and route registration
- Data query endpoints (kline, valuation, orderbook, news, research, announcements, stats)
- Backtest run / results / compare endpoints
- Paper trading cycle / state / trades
- Market summary / strategies
- QMT health / positions / orders
- Error handling (400, 404, 500)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# Ensure the repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Create a Flask app instance with an in-memory DuckDB for testing."""
    from tradingagents.astock.api import create_app

    app = create_app(
        db_path=":memory:",
        cors_origin="*",
    )

    # Seed some test data
    store = app.config["STORE"]
    store.init_schema()

    # Seed kline bars
    import pandas as pd

    kline_df = pd.DataFrame(
        [
            {
                "trade_date": "2024-01-02",
                "open": 100.0,
                "high": 105.0,
                "low": 99.0,
                "close": 104.5,
                "volume": 1_000_000,
                "amount": 104_500_000,
            },
            {
                "trade_date": "2024-01-03",
                "open": 104.5,
                "high": 106.0,
                "low": 102.0,
                "close": 103.0,
                "volume": 900_000,
                "amount": 93_000_000,
            },
        ]
    )
    store.insert_kline("600519.SH", kline_df, interval="1d", source="test")

    # Seed valuations
    val_df = pd.DataFrame(
        [
            {
                "trade_date": "2024-01-02",
                "pe": 25.0,
                "pb": 3.5,
                "market_cap": 2_000_000_000_000.0,
            },
        ]
    )
    store.insert_valuations("600519.SH", val_df, source="test")

    # Seed news
    news_df = pd.DataFrame(
        [
            {
                "publish_date": "2024-01-02",
                "title": "Test news article",
                "summary": "A test summary",
                "url": "http://example.com/news/1",
                "source": "test",
            },
        ]
    )
    store.insert_news_items("600519.SH", news_df)

    # Seed research
    research_df = pd.DataFrame(
        [
            {
                "report_date": "2024-01-02",
                "title": "Test research report",
                "institution": "Test Bank",
                "analyst": "John Doe",
                "rating": "buy",
                "pdf_url": "http://example.com/research/1",
                "source": "test",
            },
        ]
    )
    store.insert_research_reports("600519.SH", research_df)

    # Seed announcements
    ann_df = pd.DataFrame(
        [
            {
                "publish_date": "2024-01-02",
                "title": "Test announcement",
                "summary": "Announcement summary",
                "url": "http://example.com/ann/1",
            },
        ]
    )
    store.insert_announcements("600519.SH", ann_df)

    with app.test_client() as client:
        yield client


# ---------------------------------------------------------------------------
# Test: app creation
# ---------------------------------------------------------------------------


def test_app_creation():
    """Verify the Flask app factory produces a working app."""
    from tradingagents.astock.api import create_app

    app = create_app(db_path=":memory:")
    assert app is not None
    assert app.config["STORE"] is not None


# ---------------------------------------------------------------------------
# Test: health endpoint
# ---------------------------------------------------------------------------


def test_health_endpoint(app):
    resp = app.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"


# ---------------------------------------------------------------------------
# Test: data query endpoints
# ---------------------------------------------------------------------------


class TestDataEndpoints:
    def test_get_kline(self, app):
        resp = app.get("/api/v1/kline?symbol=600519.SH")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["symbol"] == "600519.SH"
        assert len(data["bars"]) == 2

    def test_get_kline_with_limit(self, app):
        resp = app.get("/api/v1/kline?symbol=600519.SH&limit=1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["bars"]) == 1

    def test_get_kline_missing_symbol(self, app):
        resp = app.get("/api/v1/kline")
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_get_kline_with_dates(self, app):
        resp = app.get(
            "/api/v1/kline?symbol=600519.SH&start=2024-01-01&end=2024-01-10"
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["bars"]) == 2

    def test_get_valuation(self, app):
        resp = app.get("/api/v1/valuation?symbol=600519.SH")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["symbol"] == "600519.SH"
        assert len(data["valuations"]) == 1

    def test_get_valuation_with_limit(self, app):
        resp = app.get("/api/v1/valuation?symbol=600519.SH&limit=1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["valuations"]) == 1

    def test_get_valuation_missing_symbol(self, app):
        resp = app.get("/api/v1/valuation")
        assert resp.status_code == 400

    def test_get_orderbook(self, app):
        resp = app.get("/api/v1/orderbook?symbol=600519.SH")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "snapshots" in data

    def test_get_news(self, app):
        resp = app.get("/api/v1/news?symbol=600519.SH&limit=10")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["news"]) == 1
        assert data["news"][0]["title"] == "Test news article"

    def test_get_research(self, app):
        resp = app.get("/api/v1/research?symbol=600519.SH&limit=10")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["reports"]) == 1

    def test_market_blocks_mock(self, app):
        resp = app.get("/api/v1/market/blocks?symbol=600519.SH&mock=1&limit=1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["symbol"] == "600519.SH"
        assert data["count"] == 1
        assert data["items"][0]["name"] == "白酒"

    def test_get_announcements(self, app):
        resp = app.get("/api/v1/announcements?symbol=600519.SH&limit=10")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["announcements"]) == 1

    def test_get_store_stats(self, app):
        resp = app.get("/api/v1/store/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        stats = data["stats"]
        assert isinstance(stats, dict)
        # kline_bars should have 2 rows
        assert stats.get("kline_bars", {}).get("rows", 0) == 2


# ---------------------------------------------------------------------------
# Test: backtest endpoints
# ---------------------------------------------------------------------------


class TestBacktestEndpoints:
    def test_run_backtest(self, app):
        payload = {
            "symbol": "600519.SH",
            "strategy": "MovingAverageTrend",
            "start": "2024-01-01",
            "end": "2024-01-10",
            "mock_data": True,
        }
        resp = app.post(
            "/api/v1/backtest/run",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total_return" in data
        assert "sharpe_ratio" in data
        assert data["strategy_name"] == "MovingAverageTrend"

    def test_run_backtest_missing_params(self, app):
        resp = app.post(
            "/api/v1/backtest/run",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_run_backtest_unknown_strategy(self, app):
        payload = {
            "symbol": "600519.SH",
            "strategy": "NonExistent",
            "start": "2024-01-01",
            "end": "2024-01-10",
        }
        resp = app.post(
            "/api/v1/backtest/run",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "Unknown strategy" in data["error"]

    def test_get_backtest_results(self, app):
        # Run one first
        payload = {
            "symbol": "600519.SH",
            "strategy": "MeanReversion",
            "start": "2024-01-01",
            "end": "2024-01-10",
            "mock_data": True,
        }
        app.post(
            "/api/v1/backtest/run",
            data=json.dumps(payload),
            content_type="application/json",
        )

        resp = app.get("/api/v1/backtest/results")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "results" in data

    def test_compare_backtests(self, app):
        resp = app.get(
            "/api/v1/backtest/compare?strategies=BullTrend,MeanReversion&symbol=600519.SH&start=2024-01-01&end=2024-01-10&mock_data=1"
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "comparison" in data
        assert len(data["comparison"]) == 2

        # Verify enhanced compare fields
        for r in data["comparison"]:
            assert "equity_curve" in r, f"Missing equity_curve in {r['strategy_name']}"
            assert "returns" in r, f"Missing returns in {r['strategy_name']}"
            assert "rank" in r, f"Missing rank in {r['strategy_name']}"
            assert isinstance(r["equity_curve"], list)
            assert isinstance(r["returns"], list)
            assert r["rank"] in (1, 2)

        # Rankings should be ordered (rank 1 has highest composite score)
        assert data["comparison"][0]["rank"] == 1
        assert data["comparison"][1]["rank"] == 2


# ---------------------------------------------------------------------------
# Test: paper trading endpoints
# ---------------------------------------------------------------------------


class TestPaperEndpoints:
    def test_paper_cycle(self, app):
        payload = {
            "signals": {"600519.SH": 1},
            "prices": {"600519.SH": 100.0},
        }
        resp = app.post(
            "/api/v1/paper/cycle",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "positions" in data
        assert "cash" in data

    def test_paper_cycle_missing_params(self, app):
        resp = app.post(
            "/api/v1/paper/cycle",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_paper_state(self, app):
        resp = app.get("/api/v1/paper/state")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "positions" in data

    def test_paper_trades(self, app):
        # Execute a trade first
        payload = {
            "signals": {"600519.SH": 1},
            "prices": {"600519.SH": 100.0},
        }
        app.post(
            "/api/v1/paper/cycle",
            data=json.dumps(payload),
            content_type="application/json",
        )
        resp = app.get("/api/v1/paper/trades")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "trades" in data
        assert len(data["trades"]) >= 1


# ---------------------------------------------------------------------------
# Test: market endpoints
# ---------------------------------------------------------------------------


class TestMarketEndpoints:
    def test_market_summary(self, app):
        resp = app.get("/api/v1/market/summary?symbol=600519.SH")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["symbol"] == "600519.SH"
        assert "latest_price" in data

    def test_market_summary_missing_symbol(self, app):
        resp = app.get("/api/v1/market/summary")
        assert resp.status_code == 400

    def test_list_strategies(self, app):
        resp = app.get("/api/v1/market/strategies")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "strategies" in data
        assert len(data["strategies"]) >= 6


# ---------------------------------------------------------------------------
# Test: QMT endpoints
# ---------------------------------------------------------------------------


class TestQmtEndpoints:
    def test_qmt_health(self, app):
        resp = app.get("/api/v1/qmt/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "healthy" in data
        assert data["mock_mode"] is True

    def test_qmt_positions(self, app):
        resp = app.get("/api/v1/qmt/positions")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "positions" in data

    def test_qmt_orders(self, app):
        resp = app.get("/api/v1/qmt/orders")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "orders" in data


# ---------------------------------------------------------------------------
# Test: dashboard overview
# ---------------------------------------------------------------------------


class TestDashboardEndpoints:
    def test_dashboard_overview(self, app):
        resp = app.get("/api/v1/dashboard/overview")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "statistics" in data
        assert "paper_positions" in data
        assert "recent_backtests" in data
        assert "recent_trades" in data
        stats = data["statistics"]
        assert "symbols_tracked" in stats
        assert "backtests_total" in stats
        assert "paper_positions" in stats
        assert "paper_return_pct" in stats
        assert "paper_equity_curve" in data


# ---------------------------------------------------------------------------
# Test: stock screener
# ---------------------------------------------------------------------------


class TestScreenerEndpoints:
    def test_screener_mock(self, app):
        resp = app.get("/api/v1/market/screener?mock=1&limit=5")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "results" in data
        assert len(data["results"]) <= 5

        if data["results"]:
            r = data["results"][0]
            assert "symbol" in r
            assert "rsi_14" in r
            assert "price" in r
            assert "ma5" in r
            assert "golden_cross" in r
            assert "score" in r

    def test_screener_with_filters(self, app):
        resp = app.get(
            "/api/v1/market/screener?mock=1&rsi_min=40&rsi_max=60&limit=3"
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "filters" in data
        assert data["filters"]["rsi_min"] == 40
        assert data["filters"]["rsi_max"] == 60


# ---------------------------------------------------------------------------
# Test: trade API
# ---------------------------------------------------------------------------


class TestTradeEndpoints:
    def test_place_buy_order(self, app):
        resp = app.post(
            "/api/v1/trade/order",
            json={"symbol": "600519.SH", "side": "buy", "price": 100.0, "quantity": 100},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["order"]["filled"] is True
        assert data["order"]["symbol"] == "600519.SH"
        assert data["order"]["side"] == "buy"
        assert data["order"]["quantity"] == 100

    def test_place_sell_order(self, app):
        app.post(
            "/api/v1/trade/order",
            json={"symbol": "600519.SH", "side": "buy", "price": 100.0, "quantity": 200},
        )
        resp = app.post(
            "/api/v1/trade/order",
            json={"symbol": "600519.SH", "side": "sell", "price": 120.0, "quantity": 100},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["order"]["filled"] is True

    def test_place_order_missing_symbol(self, app):
        resp = app.post("/api/v1/trade/order", json={"side": "buy", "price": 100.0, "quantity": 100})
        assert resp.status_code == 400

    def test_place_order_invalid_side(self, app):
        resp = app.post(
            "/api/v1/trade/order",
            json={"symbol": "600519.SH", "side": "hold", "price": 100.0, "quantity": 100},
        )
        assert resp.status_code == 400

    def test_trade_quote(self, app):
        resp = app.get("/api/v1/trade/quote?symbol=600519.SH")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "last_price" in data
        assert "symbol" in data
        assert data["symbol"] == "600519.SH"
        assert data["last_price"] > 0

    def test_trade_quote_missing_symbol(self, app):
        resp = app.get("/api/v1/trade/quote")
        assert resp.status_code == 400

    def test_trade_state(self, app):
        resp = app.get("/api/v1/trade/state")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "cash" in data
        assert "total_value" in data
        assert "positions" in data


# ---------------------------------------------------------------------------
# Test: market data endpoints (dragon tiger, sectors, northbound)
# ---------------------------------------------------------------------------


class TestMarketDataEndpoints:
    def test_dragon_tiger_mock(self, app):
        resp = app.get("/api/v1/market/dragon-tiger?mock=1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "stocks" in data
        assert data["total_records"] > 0

    def test_sectors_mock(self, app):
        resp = app.get("/api/v1/market/sectors?mock=1&top_n=5")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "top" in data
        assert len(data["top"]) > 0
        assert "name" in data["top"][0]
        assert "change_pct" in data["top"][0]

    def test_sectors_sina_fallback(self, app):
        """Test that when EastMoney fails but Sina works, Sina data is returned."""
        import tradingagents.astock.api.routes_market_data as rm
        original_em = rm.em_industry_comparison
        def _broken(*a, **kw):
            raise ConnectionError("EM down")
        rm.em_industry_comparison = _broken
        try:
            resp = app.get("/api/v1/market/sectors?top_n=5")
            assert resp.status_code == 200
            data = resp.get_json()
            assert "_note" not in data  # real data, not mock
            assert len(data["top"]) > 0
            assert "name" in data["top"][0]
            assert "change_pct" in data["top"][0]
        finally:
            rm.em_industry_comparison = original_em

    def test_sectors_auto_fallback_returns_note(self, app):
        """Test that when all real sources fail, mock data with _note is returned."""
        import tradingagents.astock.api.routes_market_data as rm
        original_em = rm.em_industry_comparison
        original_sina = rm.sina_industry_comparison
        def _broken(*a, **kw):
            raise ConnectionError("Intentional test failure")
        rm.em_industry_comparison = _broken
        rm.sina_industry_comparison = _broken
        try:
            resp = app.get("/api/v1/market/sectors?top_n=5")
            assert resp.status_code == 200
            data = resp.get_json()
            assert "_note" in data
            assert "模拟数据" in data["_note"]
            assert len(data["top"]) > 0
        finally:
            rm.em_industry_comparison = original_em
            rm.sina_industry_comparison = original_sina

    def test_northbound_mock(self, app):
        resp = app.get("/api/v1/market/northbound?mock=1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "flow" in data
        assert len(data["flow"]) > 0

    def test_data_health_endpoint(self, app):
        resp = app.get("/api/v1/data/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "sources" in data
        assert "summary" in data
        assert data["summary"]["total"] > 0


# ---------------------------------------------------------------------------
# Test: error handling
# ---------------------------------------------------------------------------


def test_404_not_found(app):
    resp = app.get("/api/v1/nonexistent")
    assert resp.status_code == 404


# end of tests
