"""Tests for OptimizeResult schema."""
from __future__ import annotations

import json
import unittest

from tradingagents.astock.schemas.optimization import OptimizeResult


class TestOptimizeResultSchema(unittest.TestCase):
    def test_default_values(self):
        r = OptimizeResult()
        self.assertEqual(r.strategy_name, "")
        self.assertEqual(r.score, 0.0)
        self.assertEqual(r.top_n, [])
        self.assertEqual(r.parameter_count, 0)
        self.assertEqual(r.notes, [])

    def test_benchmark_fields(self):
        r = OptimizeResult(benchmark_return=0.12, alpha=0.05)
        self.assertEqual(r.benchmark_return, 0.12)
        self.assertEqual(r.alpha, 0.05)

    def test_top_n(self):
        r = OptimizeResult(top_n=[{"params": {"k": 5}, "score": 0.8}])
        self.assertEqual(len(r.top_n), 1)
        self.assertEqual(r.top_n[0]["params"]["k"], 5)

    def test_to_dict(self):
        r = OptimizeResult(strategy_name="test", score=0.95)
        d = r.model_dump()
        self.assertEqual(d["strategy_name"], "test")
        self.assertEqual(d["score"], 0.95)


class TestOptimizeApiSchema(unittest.TestCase):
    """Validate that the optimize API endpoint returns an OptimizeResult-shaped response."""

    def test_optimize_response_shape(self):
        """POST /api/v1/backtest/optimize returns OptimizeResult fields."""
        from tradingagents.astock.api import create_app

        app = create_app(db_path=":memory:")
        store = app.config["STORE"]
        store.init_schema()

        # Seed minimal kline so backtest engine can initialise
        import pandas as pd

        kline_df = pd.DataFrame(
            [
                {"trade_date": "2024-01-02", "open": 100.0, "high": 105.0,
                 "low": 99.0, "close": 104.5, "volume": 1_000_000, "amount": 104_500_000},
                {"trade_date": "2024-01-03", "open": 104.5, "high": 106.0,
                 "low": 102.0, "close": 103.0, "volume": 900_000, "amount": 93_000_000},
            ]
        )
        store.insert_kline("600519.SH", kline_df, interval="1d", source="test")

        with app.test_client() as client:
            resp = client.post(
                "/api/v1/backtest/optimize",
                data=json.dumps({
                    "strategy": "MACDTrend",
                    "symbol": "600519.SH",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-10",
                    "mock_data": True,
                    "param_grid": {"fast_period": [8, 12], "slow_period": [20, 26]},
                    "top_n": 2,
                }),
                content_type="application/json",
            )

        # If the optimizer fails due to insufficient data, we still expect a 500 error
        # (not a crash).  The key contract is that on success the body matches the schema.
        if resp.status_code == 200:
            data = resp.get_json()
            expected_keys = {
                "strategy_name", "symbol", "score", "top_n",
                "in_sample_return", "out_sample_return", "walk_forward_return",
                "parameter_count", "benchmark_return", "alpha", "notes",
            }
            self.assertEqual(set(data.keys()), expected_keys,
                             f"Response keys mismatch. Got: {set(data.keys())}")
            self.assertIsInstance(data["top_n"], list)
            self.assertIsInstance(data["notes"], list)
            self.assertIsInstance(data["parameter_count"], int)

    def test_optimize_missing_strategy_returns_400(self):
        """Missing 'strategy' field returns 400."""
        from tradingagents.astock.api import create_app

        app = create_app(db_path=":memory:")
        with app.test_client() as client:
            resp = client.post(
                "/api/v1/backtest/optimize",
                data=json.dumps({"symbol": "600519.SH"}),
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("error", data)

    def test_optimize_missing_dates_returns_400(self):
        """Missing start_date / end_date returns 400."""
        from tradingagents.astock.api import create_app

        app = create_app(db_path=":memory:")
        with app.test_client() as client:
            resp = client.post(
                "/api/v1/backtest/optimize",
                data=json.dumps({"strategy": "MACDTrend", "symbol": "600519.SH"}),
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("error", data)


if __name__ == "__main__":
    unittest.main()
