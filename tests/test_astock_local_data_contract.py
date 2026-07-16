"""Local-first K-line storage and malformed-ingestion regressions."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from tradingagents.astock.api import create_app
from tradingagents.astock.store.loader import KlineLoader
from tradingagents.astock.store.permanent_kline import get_permanent_kline_store
from tradingagents.astock.store.schema import AStockStore


def test_market_kline_reads_permanent_local_warehouse_before_network(tmp_path) -> None:
    """A cold hot-cache still serves durable local bars without a provider call."""
    permanent_path = tmp_path / "permanent-kline.duckdb"
    app = create_app(
        db_path=":memory:",
        test_config={
            "ASTOCK_REQUIRE_AUTH": False,
            "ASTOCK_SCHEDULER_ENABLED": False,
            "ASTOCK_PERMANENT_KLINE_ENABLED": True,
            "ASTOCK_PERMANENT_KLINE_DB_PATH": str(permanent_path),
            "ASTOCK_AUTO_REFRESH_DAILY_KLINE": False,
        },
    )
    permanent = get_permanent_kline_store(str(permanent_path))
    permanent.insert_kline(
        "000001.SZ",
        pd.DataFrame([{
            "trade_date": "2024-01-02", "open": 10.0, "high": 11.0,
            "low": 9.0, "close": 10.5,
        }]),
        interval="1d", source="local-test",
    )

    class ProviderMustNotRun:
        def fetch(self, **_kwargs):
            raise AssertionError("a permanent local hit must not call a provider")

    app.config["DATA_FACADE"] = ProviderMustNotRun()
    response = app.test_client().get("/api/v1/market/kline?symbol=000001.SZ")

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["local_source"] == "permanent"
    assert payload["count"] == 1


def test_malformed_provider_kline_is_rejected_without_partial_local_write() -> None:
    """A malformed cache fill is reported and leaves the local series empty."""
    store = AStockStore(":memory:")
    store.init_schema()
    loader = KlineLoader(store, data_facade=object())
    response = SimpleNamespace(
        status="ok",
        source="malformed-test",
        data={"bars": [{"date": "2024-01-02", "high": 11.0, "low": 9.0, "close": 10.5}]},
    )

    try:
        with pytest.raises(ValueError, match="missing required field\\(s\\): open"):
            loader.write_response("000001.SZ", response)
        assert store.query_kline("000001.SZ").empty
    finally:
        store.close()
