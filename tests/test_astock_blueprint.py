import unittest

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
        self.assertIn("expanded graph wiring beyond the minimal research bridge", payload["data_entrypoint"]["upper_layer_bridge"]["todo"])

    def test_provider_status_tracks_verification_boundaries(self):
        status = build_blueprint_payload()["data_entrypoint"]["provider_status"]
        self.assertIn("valuation", status["akshare"]["implemented"])
        self.assertIn("valuation", status["akshare"]["live_verified"])
        self.assertTrue(status["iwencai"]["requires_credentials"])
        self.assertEqual(status["iwencai"]["live_verified"], [])
        self.assertIn("mootdx", status["mootdx"]["optional_dependency"])
        self.assertIn("f10", status["mootdx"]["fixture_verified"])
        self.assertIn("f10", status["mootdx"]["live_verified"])

    def test_benchmark_map_includes_a_share_suffixes(self):
        benchmark_map = DEFAULT_CONFIG["benchmark_map"]
        self.assertEqual(benchmark_map[".SH"], "000001.SS")
        self.assertEqual(benchmark_map[".SZ"], "399001.SZ")
        self.assertEqual(benchmark_map[".BJ"], "000001.SS")


if __name__ == "__main__":
    unittest.main()
