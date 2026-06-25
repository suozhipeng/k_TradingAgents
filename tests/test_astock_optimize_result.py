"""Tests for OptimizeResult schema."""
from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
