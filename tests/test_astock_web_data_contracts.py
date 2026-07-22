"""Regression tests for Web-facing AStock data contracts."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _reset_paper_trader() -> None:
    from tradingagents.astock.api import _paper_service

    _paper_service._paper_trader = None
    yield
    _paper_service._paper_trader = None


def _app(*, require_auth: bool = False):
    from tradingagents.astock.api import create_app
    return create_app(
        db_path=":memory:",
        cors_origin="*",
        test_config={"ASTOCK_REQUIRE_AUTH": require_auth, "ASTOCK_SCHEDULER_ENABLED": False, "ASTOCK_RESEARCH_ONLY": False},
    )


def test_order_state_is_shared_by_trading_paper_and_dashboard() -> None:
    app = _app()
    with app.test_client() as client:
        order = client.post(
            "/api/v1/trade/order",
            json={"symbol": "600519.SH", "side": "buy", "price": 100.0, "quantity": 100},
        )
        assert order.status_code == 200

        trading = client.get("/api/v1/trade/state").get_json()
        paper = client.get("/api/v1/paper/state").get_json()
        overview = client.get("/api/v1/dashboard/overview").get_json()

    assert trading["positions"] == paper["positions"]
    assert paper["positions"][0]["price_source"] == "cost_basis"
    assert paper["total_value"] == 100000.0
    assert overview["statistics"]["paper_positions"] == 1
    assert overview["recent_trades"][0]["side"] == "buy"


def test_public_display_reads_remain_available_when_write_auth_is_enabled() -> None:
    app = _app(require_auth=True)
    with app.test_client() as client:
        assert client.get("/api/v1/paper/state").status_code == 200
        assert client.get("/api/v1/qmt/health").status_code == 200
        assert client.get("/api/v1/ops/audit").status_code == 403


def test_default_leader_pool_is_not_labelled_as_real_market_data() -> None:
    from tradingagents.astock.api import _market_data_helpers as helpers

    with patch.object(
        helpers,
        "get_dynamic_leading_pool",
        return_value=([{"symbol": "600519.SH", "name": "贵州茅台", "sector": "消费", "price": 100.0}], "default"),
    ), patch.object(helpers.router, "get_valuation", side_effect=RuntimeError("offline")):
        stocks = helpers.compute_momentum_scores(helpers.fetch_real_momentum())

    assert stocks[0]["pool_source"] == "default"
    assert stocks[0]["source"] == "fallback"
