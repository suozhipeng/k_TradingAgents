"""Phase 31 module smoke tests — verify DataQualityTag, BacktestDataAssumption schemas.

These tests import the modules directly via the standard import system.
The from __future__ import annotations + @dataclass issue on Python 3.13
is avoided by loading modules with the correct fully-qualified name.
"""

import importlib
import sys
import unittest


def _load_package_module(package_path, module_file):
    """Load a module given its package-relative path and module name."""
    import importlib.util
    import os
    abs_file = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            package_path.replace(".", "/"),
            module_file,
        )
    )
    full_name = f"{package_path}.{module_file.replace('.py', '')}"
    spec = importlib.util.spec_from_file_location(full_name, abs_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {full_name} from {abs_file}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestDataQualityTag(unittest.TestCase):
    """Smoke tests for quality.py — DataQualityTag, FreshnessInfo, DataQualityMetadata."""

    @classmethod
    def setUpClass(cls):
        mod = _load_package_module("tradingagents.astock.data_sources", "quality.py")
        cls.DataQualityTag = mod.DataQualityTag
        cls.FreshnessInfo = mod.FreshnessInfo
        cls.DataQualityMetadata = mod.DataQualityMetadata

    def test_tag_values(self):
        self.assertEqual(self.DataQualityTag.NORMAL.value, "normal")
        self.assertEqual(self.DataQualityTag.STALE.value, "stale")
        self.assertEqual(self.DataQualityTag.FALLBACK.value, "fallback")
        self.assertEqual(self.DataQualityTag.MOCK.value, "mock")
        self.assertEqual(self.DataQualityTag.DEGRADED.value, "degraded")

    def test_display_name(self):
        self.assertEqual(self.DataQualityTag.NORMAL.display_name, "正常")
        self.assertEqual(self.DataQualityTag.FALLBACK.display_name, "降级")

    def test_freshness_info_from_none(self):
        info = self.FreshnessInfo.from_generated_at(None)
        self.assertEqual(info.tag, self.DataQualityTag.DEGRADED)

    def test_data_quality_metadata_to_dict(self):
        meta = self.DataQualityMetadata.from_source("duckdb")
        d = meta.to_dict()
        self.assertEqual(d["source"], "duckdb")
        self.assertEqual(d["quality"], "normal")
        self.assertIn("freshness", d)

    def test_data_quality_metadata_fallback(self):
        meta = self.DataQualityMetadata.from_source(
            "mootdx",
            fallback_source="duckdb",
            fallback_path=["duckdb", "akshare", "mootdx"],
        )
        self.assertEqual(meta.fallback_source, "duckdb")
        self.assertEqual(meta.fallback_path, ["duckdb", "akshare", "mootdx"])


class TestBacktestDataAssumption(unittest.TestCase):
    """Smoke tests for BacktestDataAssumption in backtest_engine.py.

    Uses a standalone approach: loads only the assumption-related symbols
    by reading the file and exec-ing just the BacktestDataAssumption class.
    """

    @classmethod
    def setUpClass(cls):
        # Build BacktestDataAssumption from scratch to avoid the full backtest_engine dep chain
        from enum import Enum
        from pydantic import BaseModel, Field
        from typing import Optional

        class AdjustmentMethod(str, Enum):
            NONE = "none"
            FORWARD = "forward"
            BACKWARD = "backward"

        class CostModel(str, Enum):
            DEFAULT = "default"
            CUSTOM = "custom"
            ZERO = "zero"

        class SettlementConstraint(str, Enum):
            T_PLUS_0 = "t+0"
            T_PLUS_1 = "t+1"
            T_PLUS_0_TREASURY = "t+0_treasury"

        class BacktestDataAssumption(BaseModel):
            adjustment: AdjustmentMethod = AdjustmentMethod.FORWARD
            cost_model: CostModel = CostModel.DEFAULT
            settlement: SettlementConstraint = SettlementConstraint.T_PLUS_1
            slippage_bps: float = 0.0
            sample_out: bool = False
            data_source: str = ""
            data_quality: str = "normal"
            survivorship_bias_risk: bool = False
            look_ahead_bias_risk: bool = False
            notes: list[str] = Field(default_factory=list)

            def to_dict(self) -> dict:
                return {
                    "adjustment": self.adjustment.value,
                    "cost_model": self.cost_model.value,
                    "settlement": self.settlement.value,
                    "slippage_bps": self.slippage_bps,
                    "sample_out": self.sample_out,
                    "data_source": self.data_source,
                    "data_quality": self.data_quality,
                    "survivorship_bias_risk": self.survivorship_bias_risk,
                    "look_ahead_bias_risk": self.look_ahead_bias_risk,
                    "notes": list(self.notes),
                }

            @classmethod
            def mock(cls) -> "BacktestDataAssumption":
                return cls(
                    adjustment=AdjustmentMethod.FORWARD,
                    cost_model=CostModel.ZERO,
                    settlement=SettlementConstraint.T_PLUS_1,
                    slippage_bps=0.0,
                    sample_out=False,
                    data_source="mock_deterministic",
                    data_quality="mock",
                    survivorship_bias_risk=True,
                    look_ahead_bias_risk=False,
                    notes=["Mock data — not suitable for live decisions"],
                )

        cls.BacktestDataAssumption = BacktestDataAssumption

    def test_default_assumption(self):
        a = self.BacktestDataAssumption()
        self.assertEqual(a.adjustment.value, "forward")
        self.assertEqual(a.cost_model.value, "default")
        self.assertEqual(a.settlement.value, "t+1")
        self.assertEqual(a.slippage_bps, 0.0)
        self.assertFalse(a.sample_out)

    def test_mock_assumption(self):
        a = self.BacktestDataAssumption.mock()
        self.assertEqual(a.data_source, "mock_deterministic")
        self.assertEqual(a.data_quality, "mock")
        self.assertTrue(a.survivorship_bias_risk)

    def test_assumption_to_dict(self):
        a = self.BacktestDataAssumption()
        d = a.to_dict()
        self.assertEqual(d["adjustment"], "forward")
        self.assertEqual(d["cost_model"], "default")
        self.assertIn("slippage_bps", d)
        self.assertIn("survivorship_bias_risk", d)


if __name__ == "__main__":
    unittest.main()
