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
# Test: error handling
# ---------------------------------------------------------------------------


def test_404_not_found(app):
    resp = app.get("/api/v1/nonexistent")
    assert resp.status_code == 404


# end of tests
