import re
import unittest
from datetime import date, timedelta
from pathlib import Path

from cli.models import AssetType
from cli.utils import detect_asset_type, filter_analysts_for_asset_type
from tradingagents.astock import ASTOCK_BLUEPRINT, build_blueprint_markdown, build_blueprint_payload
from tradingagents.default_config import DEFAULT_CONFIG


class AStockBlueprintTests(unittest.TestCase):
    def test_detects_a_share_tickers(self):
        for ticker in ("600519.SH", "000001.SZ", "830899.BJ", "600519"):
            self.assertEqual(detect_asset_type(ticker), AssetType.ASTOCK)

    def test_keeps_all_analysts_for_a_stock(self):
        analysts = ["market", "social", "news", "fundamentals"]
        self.assertEqual(
            filter_analysts_for_asset_type(analysts, AssetType.ASTOCK),
            analysts,
        )

    def test_blueprint_has_five_layers_and_thirteen_capabilities(self):
        self.assertEqual(len(ASTOCK_BLUEPRINT.layers), 5)
        self.assertEqual(ASTOCK_BLUEPRINT.capability_count(), 18)

    def test_blueprint_payload_is_serializable(self):
        payload = build_blueprint_payload()
        self.assertEqual(payload["title"], "TradingAgents-Astock")
        self.assertIn("五层能力", build_blueprint_markdown())
        self.assertIn("回测验证", build_blueprint_markdown())
        self.assertEqual(payload["data_entrypoint"]["upper_layer_bridge"]["class"], "AStockInterface")
        self.assertIn("market", payload["data_entrypoint"]["upper_layer_bridge"]["implemented"])
        self.assertIn("announcements", payload["data_entrypoint"]["upper_layer_bridge"]["implemented"])
        self.assertIn("research", payload["data_entrypoint"]["upper_layer_bridge"]["implemented"])
        self.assertNotIn("research", payload["data_entrypoint"]["upper_layer_bridge"]["todo"])
        self.assertNotIn("announcements", payload["data_entrypoint"]["upper_layer_bridge"]["todo"])
        self.assertEqual(payload["data_entrypoint"]["upper_layer_bridge"]["todo"], [])
        self.assertIn("CLI", payload["data_entrypoint"]["upper_layer_bridge"]["display_integrations"])
        self.assertIn(
            "Streamlit read-only UI",
            payload["data_entrypoint"]["upper_layer_bridge"]["display_integrations"],
        )
        self.assertIn(
            "Trader / Risk / Portfolio Manager advisory chain",
            payload["data_entrypoint"]["upper_layer_bridge"]["display_integrations"],
        )
        self.assertIn(
            "BacktestEngine / PaperTrader",
            payload["data_entrypoint"]["upper_layer_bridge"]["display_integrations"],
        )
        self.assertIn(
            "QMT bridge controlled execution (safety mode)",
            payload["data_entrypoint"]["upper_layer_bridge"]["display_integrations"],
        )

    def test_provider_status_tracks_verification_boundaries(self):
        status = build_blueprint_payload()["data_entrypoint"]["provider_status"]
        self.assertIn("valuation", status["akshare"]["implemented"])
        self.assertIn("valuation", status["akshare"]["live_verified"])
        lv = status["akshare"]["live_verification"]
        self.assertIn("verified_on", lv)
        self.assertIn("verified_at_commit", lv)
        self.assertIn("evidence_ref", lv)
        lv_evidence = lv["evidence_ref"]
        self.assertIsInstance(lv_evidence, str)
        self.assertGreater(len(lv_evidence), 0)
        self.assertTrue(status["iwencai"]["requires_credentials"])
        self.assertEqual(status["iwencai"]["live_verified"], [])
        iw_lv = status["iwencai"]["live_verification"]
        self.assertEqual(iw_lv["capabilities"], [])
        self.assertIn("mootdx", status["mootdx"]["optional_dependency"])
        self.assertIn("f10", status["mootdx"]["fixture_verified"])
        self.assertIn("f10", status["mootdx"]["live_verified"])

    def test_provider_live_verification_provenance_schema(self):
        """Validate provenance schema for all providers with non-empty live_verified."""
        status = build_blueprint_payload()["data_entrypoint"]["provider_status"]
        # Accept either "unknown" for unpersisted records or ISO date format
        known_or_iso_re = re.compile(r"^(unknown|\d{4}-\d{2}-\d{2})$")
        for pname, ps in status.items():
            lv = ps.get("live_verification", {})
            live_verified = ps.get("live_verified", [])
            if not live_verified:
                # Providers without live capabilities may still have a provenance
                # frame with empty capabilities — that's valid.
                self.assertEqual(lv.get("capabilities"), [])
                continue
            verified_on = lv.get("verified_on", "")
            self.assertRegex(verified_on, known_or_iso_re)
            caps = lv.get("capabilities", [])
            self.assertIsInstance(caps, list)
            # When a real date is present, enforce richer fields
            if verified_on != "unknown":
                self.assertNotEqual(lv.get("verified_at_commit", ""), "")
                self.assertNotEqual(lv.get("test_command", ""), "")
                self.assertNotEqual(lv.get("platform", ""), "")

    def test_benchmark_map_includes_a_share_suffixes(self):
        benchmark_map = DEFAULT_CONFIG["benchmark_map"]
        self.assertEqual(benchmark_map[".SH"], "000001.SS")
        self.assertEqual(benchmark_map[".SZ"], "399001.SZ")
        self.assertEqual(benchmark_map[".BJ"], "000001.SS")


if __name__ == "__main__":
    unittest.main()
